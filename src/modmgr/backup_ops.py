"""backup_ops.py - Backup and restore operations for mod file mapping.

Implements Phase 7-12 of the implementation plan:
- Phase 7:  Version check — derive backup_id from appmanifest ACF LastUpdated
- Phase 8:  Directory tree creation — build dir tree with sha256
- Phase 9:  Pre-replacement gate — verify backup exists and is complete
- Phase 10: Differential backup — copy target files into backup directory
- Phase 11: Replacement execution — apply final_mapping to disk
- Phase 12: Restore from backup — recover original files
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from enum import IntEnum
from pathlib import Path
from typing import Any


class TreeNodeStatus(IntEnum):
    """Status of a node lookup in the backup tree.

    Values:
        NOT_FOUND:     node does not exist in tree at all
        NOT_BACKED_UP: node exists but isbackuped=False (not yet backed up)
        BACKED_UP:     node exists and isbackuped=True (already backed up)
    """
    NOT_FOUND = 0
    NOT_BACKED_UP = 1
    BACKED_UP = 2

from .acf_parser import get_workshop_timeupdated, get_workshop_latest_timeupdated, parse_appmanifest_acf
from .path_resolver import assert_directory_path, assert_file_path
from .paths import normalize_posix


# ── Hard-coded loop protection ──────────────────────────────────────────────
_HARDCODED_BACKUP_SKIP_SUFFIX = ".kmmbackup"


# ── Phase 7: Version check ────────────────────────────────────────────────────

def get_game_backup_id(steamlib_path: str, appid: str) -> tuple[bool, str | None, str]:
    """Return (ok, backup_id_hex, error_msg) for a game app.

    Reads ``steamlib_path/appmanifest_{appid}.acf``:
    1. Check ``AppState.StateFlags`` — must be in allowed set {4}
    2. Read ``AppState.buildid`` → hex ascii lowercase

    Returns:
        (True, hex_string, "") on success
        (False, None, error_msg) if unstable or missing fields
    """
    acf_path = Path(steamlib_path) / f"appmanifest_{appid}.acf"
    try:
        data = parse_appmanifest_acf(str(acf_path))
    except (FileNotFoundError, ValueError) as exc:
        return (False, None, f"E_BACKUP_STATE_UNSTABLE: cannot read appmanifest for {appid}: {exc}")

    # ── Stability check: StateFlags ────────────────────────────────
    ALLOWED_STATE_FLAGS = {4}  # 4 = StateFullyInstalled
    try:
        state_flags = int(str(data.get("StateFlags", "0")))
    except (ValueError, TypeError):
        state_flags = 0

    if state_flags not in ALLOWED_STATE_FLAGS:
        return (False, None,
                f"E_BACKUP_STATE_UNSTABLE: appid {appid} StateFlags={state_flags} (not in {ALLOWED_STATE_FLAGS})")

    # ── Version ID: buildid ────────────────────────────────────────
    build_id = str(data.get("buildid", ""))
    if not build_id:
        return (False, None, f"E_BACKUP_STATE_UNSTABLE: appid {appid} has no buildid")

    try:
        hex_id = format(int(build_id), "x")
    except (ValueError, TypeError):
        return (False, None, f"E_BACKUP_STATE_UNSTABLE: appid {appid} buildid '{build_id}' is not a valid integer")

    return (True, hex_id, "")


def get_workshop_timestamphex(steamapps_path: str, appid: str, contentid: str) -> tuple[bool, str | None, str]:
    """Return (ok, timestamphex, warning_msg) for a single workshop contentid.

    Reads ``steamapps_path/workshop/appworkshop_{appid}.acf``:
    1. T_local = AppWorkshop.WorkshopItemsInstalled.{contentid}.timeupdated
    2. T_remote = AppWorkshop.WorkshopItemDetails.{contentid}.latest_timeupdated
    3. If T_local >= T_remote → stable → return (True, hex(T_remote), "")
    4. If T_local < T_remote → unstable → return (False, None, warning)
    5. If fields missing → return (False, None, warning)

    Returns:
        (True, hex_string, "") on success
        (False, None, warning_msg) on failure
    """
    acf_path = Path(steamapps_path) / "workshop" / f"appworkshop_{appid}.acf"
    if not acf_path.exists():
        return (False, None, f"W_BACKUP_CONTENTID_SKIPPED: appworkshop_{appid}.acf not found for contentid {contentid}")

    t_local_str = get_workshop_timeupdated(str(steamapps_path), appid, contentid)
    t_remote_str = get_workshop_latest_timeupdated(str(steamapps_path), appid, contentid)

    if t_local_str == "0" or t_remote_str == "0":
        return (False, None,
                f"W_BACKUP_CONTENTID_SKIPPED: contentid {contentid} missing timeupdated or latest_timeupdated in ACF")

    try:
        t_local = int(t_local_str)
        t_remote = int(t_remote_str)
    except (ValueError, TypeError):
        return (False, None,
                f"W_BACKUP_CONTENTID_SKIPPED: contentid {contentid} invalid timestamp values")

    if t_local < t_remote:
        return (False, None,
                f"W_BACKUP_VERSION_LAGGED: contentid {contentid} T_local={t_local} < T_remote={t_remote}, waiting for Steam update")

    hex_id = format(t_remote, "x")
    return (True, hex_id, "")



# ── Phase 8: Dir tree creation ───────────────────────────────────────────────

def _sha256_file(path: Path) -> str:
    """Compute SHA256 of *path*. Returns "0" on I/O error."""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return "0"


def _normalized(path: str) -> str:
    return normalize_posix(path)


def _serialize_output_path(path: str, *, is_dir: bool) -> str:
    """Serialize a path for API output with idempotent slash rules.

    Rules:
    - directory path: exactly one trailing slash
    - file path: no trailing slash
    - duplicated separators are collapsed by normalize_posix
    """
    normalized = normalize_posix(path)
    stripped = normalized.rstrip("/")
    if is_dir:
        return stripped + "/" if stripped else "/"
    return stripped



def load_backup_info(backup_dir: str) -> dict[str, Any]:
    """Load *backupinfo.json* from *backup_dir*. Returns ``{}`` on any error."""
    info_path = Path(backup_dir) / "backupinfo.json"
    if not info_path.exists():
        return {}
    try:
        with open(info_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_backup_info(backup_dir: str, info: dict[str, Any]) -> None:
    backup_path = Path(backup_dir)
    backup_path.mkdir(parents=True, exist_ok=True)
    info_path = backup_path / "backupinfo.json"
    tmp = info_path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    tmp.replace(info_path)


# ── Phase 13: Dirty state and conflict governance ────────────────────────────

def _collect_backup_original_paths(backup_dir: str, content_root: str = "") -> list[str]:
    """Collect original paths for files in *backup_dir*.

    *content_root* is the root directory under which files were backed up.
    Defaults to the parent of *backup_dir* (matching ``run_differential_backup``).
    """
    if not content_root:
        content_root = str(Path(backup_dir).parent)
    backup_path = Path(backup_dir)
    cr = Path(content_root)
    originals: list[str] = []
    for bak_file in sorted(backup_path.rglob("*")):
        if not bak_file.is_file() or bak_file.name == "backupinfo.json":
            continue
        rel = bak_file.relative_to(backup_path)
        # Loop protection: skip files inside *.kmmbackup directories
        if any(part.endswith(_HARDCODED_BACKUP_SKIP_SUFFIX) for part in rel.parts):
            continue
        original = cr / rel
        originals.append(_normalized(str(original)))
    return originals


def detect_dirty_state(backup_dir: str) -> dict[str, Any]:
    """Detect incomplete/interrupted backup state conservatively.

    Returns::

        {
          "dirty": bool,
          "errors": [str],
          "partial_files": [str],
        }
    """
    assert_directory_path(backup_dir, label="backup_dir")
    backup_dir = _normalized(backup_dir)
    backup_path = Path(backup_dir)
    if not backup_path.exists():
        return {"dirty": False, "errors": [], "partial_files": []}

    partial_files = _collect_backup_original_paths(backup_dir)
    info = load_backup_info(backup_dir)

    if not info:
        if partial_files:
            return {
                "dirty": True,
                "errors": [f"E_BACKUP_DIRTY_STATE: {backup_dir}: metadata missing"],
                "partial_files": partial_files,
            }
        return {"dirty": False, "errors": [], "partial_files": []}

    if not info.get("tree"):
        return {
            "dirty": True,
            "errors": [f"E_BACKUP_DIRTY_STATE: {backup_dir}: tree missing"],
            "partial_files": partial_files,
        }
    return {"dirty": False, "errors": [], "partial_files": []}


def _flatten_tree_file_hashes(tree: dict[str, Any]) -> dict[str, str]:
    """Flatten a backupinfo tree to {relative_path: hashvalue}.
    
    Only includes file nodes where isbackuped=True and hashtype="sha256".
    Directory nodes are traversed, not included in output.
    
    Args:
        tree: Root DirNode from backupinfo.json tree ({"name": "...", "type": "dir", "children": [...]})
    
    Returns:
        Dict mapping relative file paths to their hashvalue hex strings.
    """
    result: dict[str, str] = {}
    _flatten_tree_node(tree, "", result)
    return result


def _flatten_tree_node(node: dict[str, Any], prefix: str, out: dict[str, str]) -> None:
    """Recursive helper — walk DirNode tree, collect file hashes."""
    children = node.get("children", [])
    for child in children:
        child_type = child.get("type", "")
        child_name = child.get("name", "")
        current = f"{prefix}{child_name}" if prefix else child_name
        
        if child_type == "dir":
            _flatten_tree_node(child, current + "/", out)
        elif child_type == "file":
            if child.get("isbackuped") and child.get("hashtype") == "sha256":
                out[current] = child.get("hashvalue", "")


def inspect_conflict(backup_dir: str, final_mapping: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Inspect logical/entity conflicts without mutating anything.

    Checks:
    1) backup tree integrity (tree hash vs file hash in backup dir)
    2) optional target drift (target differs from backup copy)
    """
    assert_directory_path(backup_dir, label="backup_dir")
    backup_dir = _normalized(backup_dir)
    final_mapping = final_mapping or []

    gate_errors = check_backup_gate(backup_dir)
    if gate_errors:
        return {"clean": False, "conflicts": gate_errors}

    backup_path = Path(backup_dir)
    info = load_backup_info(backup_dir)
    tree = info.get("tree") if isinstance(info, dict) else None
    if not isinstance(tree, dict):
        return {"clean": False, "conflicts": [f"E_TREE_CONFLICT: {backup_dir}: invalid tree"]}

    conflicts: list[str] = []
    expected = _flatten_tree_file_hashes(tree)

    for rel, expected_hash in sorted(expected.items()):
        if not rel:
            continue
        bak = backup_path / rel
        if not bak.exists():
            conflicts.append(f"E_ENTITY_CONFLICT: missing backup file: {bak}")
            continue
        actual_hash = _sha256_file(bak)
        if expected_hash not in {"", "0"} and actual_hash != expected_hash:
            conflicts.append(
                f"E_ENTITY_CONFLICT: hash mismatch: {bak}: expected={expected_hash}, actual={actual_hash}"
            )

    # Conservative target drift detection: only for files that were backed up.
    for entry in final_mapping:
        target = _normalized(str(entry.get("path", "")))
        if not target:
            continue
        rel = target.lstrip("/")
        bak = backup_path / rel
        tgt = Path(target)
        if not bak.exists() or not tgt.exists():
            continue
        bak_hash = _sha256_file(bak)
        tgt_hash = _sha256_file(tgt)
        if bak_hash != "0" and tgt_hash != "0" and bak_hash != tgt_hash:
            conflicts.append(f"E_TREE_CONFLICT_TARGET_DRIFT: {target}")

    return {"clean": not conflicts, "conflicts": conflicts}


# ── Phase 9: Pre-replacement gate ─────────────────────────────────────────────

def check_backup_gate(backup_dir: str) -> list[str]:
    """Return a list of error codes if the backup is incomplete.

    An empty list means the gate passes and replacement is safe.
    """
    assert_directory_path(backup_dir, label="backup_dir")
    errors: list[str] = []
    backup_path = Path(backup_dir)
    if not backup_path.exists():
        return [f"E_BACKUP_DIR_MISSING: {backup_dir}"]
    info = load_backup_info(backup_dir)
    if not info:
        errors.append(f"E_BACKUP_INFO_MISSING: {backup_dir}")
        return errors
    # 只检查新字段
    if not info.get("tree"):
        errors.append(f"E_BACKUP_TREE_MISSING: {backup_dir}")
    return errors


# ── Phase 10: Differential backup ─────────────────────────────────────────────

def run_differential_backup(
    backup_dir: str,
    files_to_backup: list[str],
    *,
    on_progress: Any = None,
    dry_run: bool = False,
    content_root: str = "",
    tree: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Copy each file in *files_to_backup* (if it exists) into *backup_dir*.

    Files are stored relative to *content_root* under *backup_dir*
    (e.g. ``/mnt/d/contentid/some/file.mod`` → ``<backup_dir>/some/file.mod``).

    If *tree* is provided, files whose tree node has ``isbackuped=true``
    are skipped (already backed up).

    Calls ``finalize_backup_dir`` after all copies to produce status=ready.

    Returns::

        {"ok": bool, "backed_up": [str], "skipped": [str], "errors": [str]}
    """
    # Derive content_root from backup_dir if not explicitly given
    if not content_root:
        content_root = str(Path(backup_dir).parent)
    cr = normalize_posix(content_root)
    dir_basename = Path(backup_dir).name  # e.g. "270150.15dcbe1.kmmbackup"

    if dry_run:
        would_backup: list[dict[str, Any]] = []
        would_skip: list[dict[str, Any]] = []
        for i, target in enumerate(files_to_backup):
            if on_progress:
                on_progress("backup", i + 1, len(files_to_backup), target)
            src = Path(target)
            norm = normalize_posix(str(src))
            rel = norm.removeprefix(cr).lstrip("/") if norm.startswith(cr) else norm.lstrip("/")
            if src.exists():
                is_dir = src.is_dir()
                path_out = _serialize_output_path(target, is_dir=is_dir)
                backup_path_out = _serialize_output_path(
                    f"{dir_basename}/{rel}",
                    is_dir=is_dir,
                )
                try:
                    st = src.stat()
                    would_backup.append({
                        "action": "copy",
                        "path": path_out,
                        "backup_path": backup_path_out,
                        "size": st.st_size,
                        "mtime": st.st_mtime,
                        "is_dir": is_dir,
                    })
                except OSError:
                    would_backup.append({
                        "action": "copy",
                        "path": path_out,
                        "backup_path": backup_path_out,
                        "size": 0,
                        "mtime": 0,
                        "is_dir": is_dir,
                    })
            else:
                would_skip.append({"path": target, "reason": "source not found"})
        return {"ok": True, "backed_up": would_backup, "skipped": would_skip, "errors": [], "dry_run": True}

    assert_directory_path(backup_dir, label="backup_dir")
    backup_path = Path(backup_dir)
    backed_up: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[str] = []

    # ── Preserve tree_created_time; only prep writes it ──────────
    _existing_info = load_backup_info(backup_dir)
    _tree_created_time = (
        _existing_info.get("tree_created_time")
        or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )

    for target in files_to_backup:
        if on_progress:
            on_progress("backup", len(backed_up) + len(skipped) + len(errors) + 1, len(files_to_backup), target)
        src = Path(target)

        # ── Tree check: skip if already backed up ─────────────────
        rel_for_tree = ""
        if tree is not None:
            rel_for_tree = normalize_posix(str(src)).removeprefix(cr).lstrip("/") if normalize_posix(str(src)).startswith(cr) else normalize_posix(str(src)).lstrip("/")
            status = _tree_node_status(tree, rel_for_tree)
            if status == TreeNodeStatus.BACKED_UP:
                skipped.append({"path": target, "reason": "already backed up (isbackuped=true in tree)"})
                continue
            elif status == TreeNodeStatus.NOT_FOUND:
                errors.append(f"W_BACKUP_NODE_NOT_IN_TREE: file not in backup tree: {rel_for_tree}")
                skipped.append({"path": target, "reason": "node not in backup tree"})
                continue

        if not src.exists():
            skipped.append({"path": target, "reason": "source not found"})
            continue
        norm = normalize_posix(str(src))
        rel = norm.removeprefix(cr).lstrip("/") if norm.startswith(cr) else norm.lstrip("/")
        dest = backup_path / rel
        is_dir = src.is_dir()
        path_out = _serialize_output_path(target, is_dir=is_dir)
        backup_path_out = _serialize_output_path(
            f"{dir_basename}/{rel}",
            is_dir=is_dir,
        )
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            _assert_is_file(src, "backup")
            shutil.copy2(str(src), str(dest))
            st = src.stat()
            backed_up.append({
                "action": "copy",
                "path": path_out,
                "backup_path": backup_path_out,
                "size": st.st_size,
                "mtime": st.st_mtime,
                "is_dir": is_dir,
            })

            # ── Update tree node after successful copy ─────────────
            if tree is not None and rel_for_tree:
                _update_tree_node(tree, rel_for_tree, "sha256", _sha256_file(dest))
                _write_backup_info(backup_dir, {
                    "schema_namespace": "KMM_BackupInfo",
                    "tree": tree,
                    "tree_created_time": _tree_created_time,
                    "last_modified_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "schema_version": "knighthana@0.1.0",
                })
        except OSError as exc:
            errors.append(f"E_BACKUP_COPY_FAILED: {target}: {exc}")

    return {"ok": not errors, "backed_up": backed_up, "skipped": skipped, "errors": errors}


# ── Phase 12: Restore from backup ─────────────────────────────────────────────

def restore_from_backup(
    backup_dir: str,
    target_files: list[str] | None = None,
    *,
    on_progress: Any = None,
    dry_run: bool = False,
    content_root: str = "",
) -> dict[str, Any]:
    """Restore files from *backup_dir* back to their original locations.

    Files whose SHA256 already matches the backup copy are skipped (no I/O).

    *content_root* is the root directory under which files were backed up
    (matching ``run_differential_backup``).  Defaults to the parent of
    *backup_dir* when not supplied.

    Args:
        backup_dir: Path to backup directory; gate must pass.
        target_files: Specific absolute paths to restore. ``None`` restores all
            backed-up files.

        Returns::

                {
                    "ok": bool,
                    "restored": [str],
                    "skipped": [str],
                    "errors": [str],
                    "orphans": [str],
                    "warnings": [str],
                }
    """
    if not content_root:
        content_root = str(Path(backup_dir).parent)
    cr = Path(content_root)

    assert_directory_path(backup_dir, label="backup_dir")
    gate_errors = check_backup_gate(backup_dir)
    if gate_errors:
        return {
            "ok": False,
            "restored": [],
            "skipped": [],
            "errors": gate_errors,
            "orphans": [],
            "warnings": [],
        }

    backup_path = Path(backup_dir)

    if dry_run:
        would_restore: list[dict[str, Any]] = []
        would_skip: list[dict[str, Any]] = []
        target_set: set[str] | None = None
        if target_files is not None:
            target_set = {normalize_posix(t) for t in target_files}
        bak_files = sorted([f for f in backup_path.rglob("*") if f.is_file() and f.name != "backupinfo.json"])
        for i, bak_file in enumerate(bak_files):
            rel = bak_file.relative_to(backup_path)
            if any(part.endswith(_HARDCODED_BACKUP_SKIP_SUFFIX) for part in rel.parts):
                continue
            original = cr / rel
            orig_norm = normalize_posix(str(original))
            if target_set is not None and orig_norm not in target_set:
                would_skip.append({"path": str(original), "reason": "not in target set"})
                continue
            if on_progress:
                on_progress("restore", i + 1, len(bak_files), str(original))
            if original.exists():
                try:
                    if _sha256_file(original) == _sha256_file(bak_file):
                        would_skip.append({"path": str(original), "reason": "already identical"})
                        continue
                except Exception:
                    pass
            try:
                st = bak_file.stat()
                would_restore.append({
                    "path": orig_norm,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                    "is_dir": False,
                })
            except OSError:
                would_restore.append({
                    "path": orig_norm,
                    "size": 0,
                    "mtime": 0,
                    "is_dir": False,
                })
        return {
            "ok": True,
            "restored": would_restore,
            "skipped": would_skip,
            "errors": [],
            "orphans": [],
            "warnings": [],
            "dry_run": True,
        }

    restored: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []

    target_set: set[str] | None = None
    if target_files is not None:
        target_set = {normalize_posix(t) for t in target_files}

    bak_files = sorted([f for f in backup_path.rglob("*") if f.is_file() and f.name != "backupinfo.json"])
    for i, bak_file in enumerate(bak_files):
        if on_progress:
            on_progress("restore", i + 1, len(bak_files), str(bak_file))
        rel = bak_file.relative_to(backup_path)
        # Loop protection: skip files inside *.kmmbackup directories
        if any(part.endswith(_HARDCODED_BACKUP_SKIP_SUFFIX) for part in rel.parts):
            continue
        original = cr / rel
        orig_norm = normalize_posix(str(original))

        if target_set is not None and orig_norm not in target_set:
            skipped.append(str(original))
            continue

        # Skip identical files to avoid redundant I/O
        if original.exists():
            if _sha256_file(original) == _sha256_file(bak_file):
                skipped.append(str(original))
                continue

        try:
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(bak_file), str(original))
            restored.append(orig_norm)
        except OSError as exc:
            errors.append(f"E_RESTORE_COPY_FAILED: {original}: {exc}")

    originals = _collect_backup_original_paths(backup_dir, content_root)
    orphans = _list_orphans(backup_dir, originals, target_set)
    warnings.extend([f"E_EXTERNAL_FILE_ORPHAN: {p}" for p in orphans])

    return {
        "ok": not errors,
        "restored": restored,
        "skipped": skipped,
        "errors": errors,
        "orphans": orphans,
        "warnings": warnings,
    }


def delete_orphan_files(orphan_paths: list[str]) -> dict[str, Any]:
    """Delete orphan files after explicit user confirmation."""
    deleted: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    for p in orphan_paths:
        norm = _normalized(p)
        fp = Path(norm)
        if not fp.exists():
            skipped.append(norm)
            continue
        try:
            fp.unlink()
            deleted.append(norm)
        except OSError as exc:
            errors.append(f"E_ORPHAN_DELETE_FAILED: {norm}: {exc}")

    return {"ok": not errors, "deleted": deleted, "skipped": skipped, "errors": errors}


def _assert_is_file(path: Path | str, context: str = "") -> None:
    """Raise IsADirectoryError if *path* is a directory (backup is file-to-file only)."""
    p = Path(path)
    if p.is_dir():
        label = f" ({context})" if context else ""
        raise IsADirectoryError(f"E_BACKUP_DIRECTORY_NOT_ALLOWED{label}: {p}")


def _tree_node_status(tree: dict[str, Any], rel_path: str) -> TreeNodeStatus:
    """Check tree node status for a relative path.

    Walks the tree by splitting *rel_path* on ``/`` and matching each
    component case-insensitively (Windows compatibility).

    Returns:
        NOT_FOUND:     node not in tree at all (or path traverses a non-dir,
                       or final node is a dir when a file was expected)
        NOT_BACKED_UP: node exists but isbackuped=False
        BACKED_UP:     node exists and isbackuped=True
    """
    parts = rel_path.split("/")
    node = tree
    for part in parts:
        if node.get("type") != "dir":
            return TreeNodeStatus.NOT_FOUND
        found = next(
            (c for c in node.get("children", [])
             if c.get("name", "").lower() == part.lower()),
            None
        )
        if found is None:
            return TreeNodeStatus.NOT_FOUND
        node = found
    # Reached the node at the end of the path
    if node.get("type") == "dir":
        # Path expected a file but found a directory
        return TreeNodeStatus.NOT_FOUND
    return TreeNodeStatus.BACKED_UP if node.get("isbackuped") else TreeNodeStatus.NOT_BACKED_UP


def _update_tree_node(tree: dict[str, Any], rel_path: str, hashtype: str, hashvalue: str) -> None:
    """Walk *tree* to the node at *rel_path* and update its backup fields.

    Matching is case-insensitive.
    Only updates if current values allow the transition.
    """
    parts = rel_path.split("/")
    node = tree
    for part in parts:
        found = next(
            (c for c in node.get("children", [])
             if c.get("name", "").lower() == part.lower()),
            None
        )
        if found is None:
            return
        node = found
    if node.get("isbackuped") is False:
        node["isbackuped"] = True
    if node.get("hashtype") == "invalid":
        node["hashtype"] = hashtype
    if node.get("hashvalue", "0") == "0":
        node["hashvalue"] = hashvalue


__all__ = [
    "get_game_backup_id",
    "get_workshop_timestamphex",
    "load_backup_info",
    "detect_dirty_state",
    "inspect_conflict",
    "check_backup_gate",
    "run_differential_backup",
    "restore_from_backup",
    "delete_orphan_files",
]

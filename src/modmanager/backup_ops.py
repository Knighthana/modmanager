"""backup_ops.py - Backup and restore operations for mod file mapping.

Implements Phase 7-12 of the implementation plan:
- Phase 7:  Version check — derive backup_id from appmanifest ACF LastUpdated
- Phase 8:  Directory tree creation — build filefoldertree with sha256
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
from pathlib import Path
from typing import Any

from .acf_parser import get_workshop_timeupdated, get_workshop_latest_timeupdated, parse_appmanifest_acf
from .path_resolver import assert_directory_path, assert_file_path
from .paths import normalize_posix


# ── Hard-coded loop protection ──────────────────────────────────────────────
_HARDCODED_BACKUP_SKIP_PREFIX = "kmmbackup_"


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


# ── Phase 8: Directory tree creation ──────────────────────────────────────────

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


def build_filefoldertree_with_hashes(
    root_dir: str,
    *,
    skip_names: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Scan *root_dir* recursively and build a filefoldertree dict.

    File nodes have ``isbackuped=True`` and a SHA256 hash (files inside a
    backup directory are by definition already backed up).
    *skip_names* defaults to ``{"backupinfo.json"}`` to exclude the metadata
    file from the tree.
    """
    if skip_names is None:
        skip_names = frozenset({"backupinfo.json"})

    def _scan(path: Path) -> dict[str, Any]:
        if path.is_file():
            return {
                "name": path.name,
                "type": "file",
                "isbackuped": True,
                "hashtype": "sha256",
                "hashvalue": _sha256_file(path),
            }
        children: list[dict[str, Any]] = []
        try:
            for child in sorted(path.iterdir()):
                if child.name in skip_names:
                    continue
                # Loop protection: skip kmmbackup_* sub-directories
                if child.name.startswith(_HARDCODED_BACKUP_SKIP_PREFIX):
                    continue
                children.append(_scan(child))
        except PermissionError:
            pass
        return {"name": path.name, "type": "folder", "children": children}

    return _scan(Path(root_dir))


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


def _flatten_tree_file_hashes(node: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Flatten filefoldertree into ``rel_path -> hashvalue`` mapping."""
    name = str(node.get("name", ""))
    node_type = str(node.get("type", ""))
    current = f"{prefix}/{name}" if prefix and name else (name or prefix)

    if node_type == "file":
        rel = current.lstrip("/")
        return {rel: str(node.get("hashvalue", "0"))} if rel else {}

    out: dict[str, str] = {}
    for child in node.get("children", []):
        if isinstance(child, dict):
            out.update(_flatten_tree_file_hashes(child, current))
    return out


def _collect_backup_original_paths(backup_dir: str) -> list[str]:
    backup_path = Path(backup_dir)
    originals: list[str] = []
    for bak_file in sorted(backup_path.rglob("*")):
        if not bak_file.is_file() or bak_file.name == "backupinfo.json":
            continue
        rel = bak_file.relative_to(backup_path)
        # Loop protection: skip files inside kmmbackup_* directories
        if any(part.startswith(_HARDCODED_BACKUP_SKIP_PREFIX) for part in rel.parts):
            continue
        original = Path("/") / rel
        originals.append(_normalized(str(original)))
    return originals


def _write_backup_info(backup_dir: str, info: dict[str, Any]) -> None:
    backup_path = Path(backup_dir)
    backup_path.mkdir(parents=True, exist_ok=True)
    info_path = backup_path / "backupinfo.json"
    tmp = info_path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    tmp.replace(info_path)


def init_backup_dir(backup_dir: str) -> None:
    """Create *backup_dir* and write an initial *backupinfo.json* (status=error).

    Status is set to ``"error"`` until ``finalize_backup_dir`` completes the
    tree scan and flips it to ``"ready"``.
    """
    assert_directory_path(backup_dir, label="backup_dir")
    _write_backup_info(backup_dir, {"filefoldertree_status": "error"})


def finalize_backup_dir(backup_dir: str) -> dict[str, Any]:
    """Scan *backup_dir*, build the filefoldertree with hashes, write status=ready.

    Returns the completed backupinfo dict.
    """
    assert_directory_path(backup_dir, label="backup_dir")
    tree = build_filefoldertree_with_hashes(backup_dir)
    info: dict[str, Any] = {"filefoldertree_status": "ready", "filefoldertree": tree}
    _write_backup_info(backup_dir, info)
    return info


# ── Phase 13: Dirty state and conflict governance ────────────────────────────

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

    status = str(info.get("filefoldertree_status", ""))
    if status == "error":
        return {
            "dirty": True,
            "errors": [f"E_BACKUP_DIRTY_STATE: {backup_dir}: status='error'"],
            "partial_files": partial_files,
        }

    if status == "ready" and "filefoldertree" not in info:
        return {
            "dirty": True,
            "errors": [f"E_BACKUP_DIRTY_STATE: {backup_dir}: ready but tree missing"],
            "partial_files": partial_files,
        }

    return {"dirty": False, "errors": [], "partial_files": []}


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
    tree = info.get("filefoldertree") if isinstance(info, dict) else None
    if not isinstance(tree, dict):
        return {"clean": False, "conflicts": [f"E_TREE_CONFLICT: {backup_dir}: invalid filefoldertree"]}

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
    if info.get("filefoldertree_status") != "ready":
        errors.append(
            f"E_BACKUP_TREE_INCOMPLETE: {backup_dir}: "
            f"status={info.get('filefoldertree_status')!r}"
        )
    if "filefoldertree" not in info:
        errors.append(f"E_BACKUP_TREE_MISSING: {backup_dir}")
    return errors


# ── Phase 10: Differential backup ─────────────────────────────────────────────

def run_differential_backup(
    backup_dir: str,
    files_to_backup: list[str],
    *,
    on_progress: Any = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Copy each file in *files_to_backup* (if it exists) into *backup_dir*.

    Files are stored preserving their full absolute path under *backup_dir*
    (e.g. ``/mnt/d/foo/bar.png`` → ``<backup_dir>/mnt/d/foo/bar.png``).

    Calls ``finalize_backup_dir`` after all copies to produce status=ready.

    Returns::

        {"ok": bool, "backed_up": [str], "skipped": [str], "errors": [str]}
    """
    if dry_run:
        would_backup: list[dict[str, Any]] = []
        would_skip: list[dict[str, Any]] = []
        for i, target in enumerate(files_to_backup):
            if on_progress:
                on_progress("backup", i + 1, len(files_to_backup), target)
            src = Path(target)
            if src.exists():
                try:
                    st = src.stat()
                    would_backup.append({
                        "path": target,
                        "size": st.st_size,
                        "mtime": st.st_mtime,
                        "is_dir": src.is_dir(),
                    })
                except OSError:
                    would_backup.append({
                        "path": target,
                        "size": 0,
                        "mtime": 0,
                        "is_dir": False,
                    })
            else:
                would_skip.append({"path": target, "reason": "source not found"})
        return {"ok": True, "backed_up": would_backup, "skipped": would_skip, "errors": [], "dry_run": True}

    assert_directory_path(backup_dir, label="backup_dir")
    init_backup_dir(backup_dir)
    backup_path = Path(backup_dir)
    backed_up: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    for target in files_to_backup:
        if on_progress:
            on_progress("backup", len(backed_up) + len(skipped) + len(errors) + 1, len(files_to_backup), target)
        src = Path(target)
        if not src.exists():
            skipped.append(target)
            continue
        norm = normalize_posix(str(src))
        rel = norm.lstrip("/")
        dest = backup_path / rel
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(str(src), str(dest), dirs_exist_ok=True)
            else:
                shutil.copy2(str(src), str(dest))
            backed_up.append(target)
        except OSError as exc:
            errors.append(f"E_BACKUP_COPY_FAILED: {target}: {exc}")

    finalize_backup_dir(backup_dir)
    return {"ok": not errors, "backed_up": backed_up, "skipped": skipped, "errors": errors}


# ── Phase 11: Replacement execution ───────────────────────────────────────────

def apply_final_mapping(
    final_mapping: list[dict[str, Any]],
    backup_dir: str,
    *,
    dry_run: bool = False,
    on_progress: Any = None,
) -> dict[str, Any]:
    """Apply *final_mapping* to disk after verifying the backup gate.

    Args:
        final_mapping: ``final_mapping`` list from ``compute_mapping``.
        backup_dir: Path to the backup directory; gate must pass before files
            are touched.
        dry_run: When ``True`` the gate is checked but no file operations are
            performed.

    Returns::

        {"ok": bool, "applied": [str], "skipped": [str], "errors": [str]}
    """
    assert_directory_path(backup_dir, label="backup_dir")
    gate_errors = check_backup_gate(backup_dir)
    if gate_errors:
        return {"ok": False, "applied": [], "skipped": [], "errors": gate_errors}

    if dry_run:
        would_apply: list[dict[str, Any]] = []
        would_skip: list[dict[str, Any]] = []
        would_errors: list[str] = []
        for i, entry in enumerate(final_mapping):
            target = entry.get("path", "")
            req = entry.get("request") or {}
            action = req.get("action", "")
            source = req.get("path", "")
            if on_progress:
                on_progress("apply", i + 1, len(final_mapping), target)
            if not target:
                would_errors.append("E_APPLY_MISSING_TARGET")
                continue
            if action == "delete":
                t = Path(target)
                if t.exists():
                    try:
                        st = t.stat()
                        would_apply.append({
                            "action": "delete",
                            "target": target,
                            "size": st.st_size,
                            "mtime": st.st_mtime,
                            "is_dir": t.is_dir(),
                        })
                    except OSError:
                        would_apply.append({
                            "action": "delete",
                            "target": target,
                            "size": 0,
                            "mtime": 0,
                            "is_dir": False,
                        })
                else:
                    would_skip.append({"action": "delete", "target": target, "reason": "target not found"})
                continue
            if not source or source == "!":
                would_errors.append(f"E_APPLY_MISSING_SOURCE: {target}")
                continue
            src_path = Path(source)
            if not src_path.exists():
                would_errors.append(f"E_SOURCE_NOT_FOUND: {source}")
                continue
            try:
                st = src_path.stat()
                would_apply.append({
                    "action": action,
                    "source": source,
                    "target": target,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                    "is_dir": src_path.is_dir(),
                })
            except OSError:
                would_apply.append({
                    "action": action,
                    "source": source,
                    "target": target,
                    "size": 0,
                    "mtime": 0,
                    "is_dir": False,
                })
        return {
            "ok": not would_errors,
            "applied": would_apply,
            "skipped": would_skip,
            "errors": would_errors,
            "dry_run": True,
        }

    applied: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    for i, entry in enumerate(final_mapping):
        target = entry.get("path", "")
        req = entry.get("request") or {}
        action = req.get("action", "")
        source = req.get("path", "")
        if on_progress:
            on_progress("apply", i + 1, len(final_mapping), target)

        if not target:
            errors.append("E_APPLY_MISSING_TARGET")
            continue

        # ── delete ──────────────────────────────────────────────────────────
        if action == "delete":
            t = Path(target)
            if t.exists():
                try:
                    t.unlink()
                    applied.append(target)
                except OSError as exc:
                    errors.append(f"E_DELETE_FAILED: {target}: {exc}")
            else:
                skipped.append(target)
            continue

        # ── copy-based actions ───────────────────────────────────────────────
        if not source or source == "!":
            errors.append(f"E_APPLY_MISSING_SOURCE: {target}")
            continue

        src_path = Path(source)
        if not src_path.exists():
            errors.append(f"E_SOURCE_NOT_FOUND: {source}")
            continue

        dest_path = Path(target)
        try:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            if src_path.is_dir():
                shutil.copytree(str(src_path), str(dest_path), dirs_exist_ok=True)
            else:
                shutil.copy2(str(src_path), str(dest_path))
            applied.append(target)
        except OSError as exc:
            errors.append(f"E_COPY_FAILED: {target}: {exc}")

    return {"ok": not errors, "applied": applied, "skipped": skipped, "errors": errors}


# ── Phase 12: Restore from backup ─────────────────────────────────────────────

def restore_from_backup(
    backup_dir: str,
    target_files: list[str] | None = None,
    *,
    on_progress: Any = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Restore files from *backup_dir* back to their original locations.

    Files whose SHA256 already matches the backup copy are skipped (no I/O).

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
            if any(part.startswith(_HARDCODED_BACKUP_SKIP_PREFIX) for part in rel.parts):
                continue
            original = Path("/") / rel
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
        # Loop protection: skip files inside kmmbackup_* directories
        if any(part.startswith(_HARDCODED_BACKUP_SKIP_PREFIX) for part in rel.parts):
            continue
        original = Path("/") / rel
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

    originals = _collect_backup_original_paths(backup_dir)
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


def _list_orphans(
    backup_dir: str,
    backed_files: list[str],
    target_set: set[str] | None,
) -> list[str]:
    """Return candidate orphan files conservatively.

    Rules:
    - Only scan parent dirs of backed files
    - Only include files newer than backup metadata write time
    - If target_set is provided, keep only files in target_set parents
    """
    backed_set = {_normalized(p) for p in backed_files}
    if not backed_set:
        return []

    info_path = Path(backup_dir) / "backupinfo.json"
    try:
        baseline = info_path.stat().st_mtime
    except OSError:
        baseline = time.time()

    allowed_dirs: set[str] | None = None
    if target_set is not None:
        allowed_dirs = {_normalized(str(Path(p).parent)) for p in target_set}

    scan_dirs = {_normalized(str(Path(p).parent)) for p in backed_set}
    out: set[str] = set()

    for d in sorted(scan_dirs):
        if allowed_dirs is not None and d not in allowed_dirs:
            continue
        dir_path = Path(d)
        if not dir_path.exists() or not dir_path.is_dir():
            continue
        for f in dir_path.rglob("*"):
            if not f.is_file():
                continue
            f_norm = _normalized(str(f))
            if f_norm in backed_set:
                continue
            try:
                if f.stat().st_mtime < baseline:
                    continue
            except OSError:
                continue
            out.add(f_norm)

    return sorted(out)


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


__all__ = [
    "get_game_backup_id",
    "get_workshop_timestamphex",
    "build_filefoldertree_with_hashes",
    "load_backup_info",
    "init_backup_dir",
    "finalize_backup_dir",
    "detect_dirty_state",
    "inspect_conflict",
    "check_backup_gate",
    "run_differential_backup",
    "apply_final_mapping",
    "restore_from_backup",
    "delete_orphan_files",
]

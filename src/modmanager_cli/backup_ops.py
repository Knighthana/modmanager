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
from pathlib import Path
from typing import Any

from .acf_parser import parse_appmanifest_acf
from .paths import normalize_posix


# ── Phase 7: Version check ────────────────────────────────────────────────────

def get_game_backup_id(steamlib_path: str, appid: str) -> str:
    """Return backup_id as lowercase hex of LastUpdated from appmanifest_<appid>.acf.

    Returns "0" if the ACF file is missing or the LastUpdated field is absent.
    """
    acf_path = Path(steamlib_path) / f"appmanifest_{appid}.acf"
    try:
        data = parse_appmanifest_acf(str(acf_path))
        raw = str(data.get("LastUpdated", "0"))
        try:
            ts = int(raw)
        except (ValueError, TypeError):
            ts = 0
        return format(ts, "x")
    except (FileNotFoundError, ValueError):
        return "0"


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
    _write_backup_info(backup_dir, {"filefoldertree_status": "error"})


def finalize_backup_dir(backup_dir: str) -> dict[str, Any]:
    """Scan *backup_dir*, build the filefoldertree with hashes, write status=ready.

    Returns the completed backupinfo dict.
    """
    tree = build_filefoldertree_with_hashes(backup_dir)
    info: dict[str, Any] = {"filefoldertree_status": "ready", "filefoldertree": tree}
    _write_backup_info(backup_dir, info)
    return info


# ── Phase 9: Pre-replacement gate ─────────────────────────────────────────────

def check_backup_gate(backup_dir: str) -> list[str]:
    """Return a list of error codes if the backup is incomplete.

    An empty list means the gate passes and replacement is safe.
    """
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
) -> dict[str, Any]:
    """Copy each file in *files_to_backup* (if it exists) into *backup_dir*.

    Files are stored preserving their full absolute path under *backup_dir*
    (e.g. ``/mnt/d/foo/bar.png`` → ``<backup_dir>/mnt/d/foo/bar.png``).

    Calls ``finalize_backup_dir`` after all copies to produce status=ready.

    Returns::

        {"ok": bool, "backed_up": [str], "skipped": [str], "errors": [str]}
    """
    init_backup_dir(backup_dir)
    backup_path = Path(backup_dir)
    backed_up: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    for target in files_to_backup:
        src = Path(target)
        if not src.exists():
            skipped.append(target)
            continue
        norm = normalize_posix(str(src))
        rel = norm.lstrip("/")
        dest = backup_path / rel
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dest))
            backed_up.append(target)
        except OSError as exc:
            errors.append(f"E_BACKUP_COPY_FAILED: {target}: {exc}")

    finalize_backup_dir(backup_dir)
    return {"ok": not errors, "backed_up": backed_up, "skipped": skipped, "errors": errors}


# ── Phase 11: Replacement execution ───────────────────────────────────────────

def _collect_clear_then_copy_dirs(final_mapping: list[dict[str, Any]]) -> set[str]:
    """Return set of destination directory paths for clear_then_copy entries."""
    dirs: set[str] = set()
    for entry in final_mapping:
        req = entry.get("request") or {}
        if req.get("action") == "clear_then_copy":
            target = entry.get("path", "")
            if target:
                dirs.add(normalize_posix(str(Path(target).parent)))
    return dirs


def apply_final_mapping(
    final_mapping: list[dict[str, Any]],
    backup_dir: str,
    *,
    dry_run: bool = False,
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
    gate_errors = check_backup_gate(backup_dir)
    if gate_errors:
        return {"ok": False, "applied": [], "skipped": [], "errors": gate_errors}

    if dry_run:
        return {"ok": True, "applied": [], "skipped": [], "errors": []}

    applied: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    # Pre-clear directories for clear_then_copy actions
    clear_dirs = _collect_clear_then_copy_dirs(final_mapping)
    for d in sorted(clear_dirs):
        dir_path = Path(d)
        if dir_path.exists():
            try:
                shutil.rmtree(str(dir_path))
                dir_path.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                errors.append(f"E_CLEAR_DIR_FAILED: {d}: {exc}")

    for entry in final_mapping:
        target = entry.get("path", "")
        req = entry.get("request") or {}
        action = req.get("action", "")
        source = req.get("path", "")

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
            shutil.copy2(str(src_path), str(dest_path))
            applied.append(target)
        except OSError as exc:
            errors.append(f"E_COPY_FAILED: {target}: {exc}")

    return {"ok": not errors, "applied": applied, "skipped": skipped, "errors": errors}


# ── Phase 12: Restore from backup ─────────────────────────────────────────────

def restore_from_backup(
    backup_dir: str,
    target_files: list[str] | None = None,
) -> dict[str, Any]:
    """Restore files from *backup_dir* back to their original locations.

    Files whose SHA256 already matches the backup copy are skipped (no I/O).

    Args:
        backup_dir: Path to backup directory; gate must pass.
        target_files: Specific absolute paths to restore. ``None`` restores all
            backed-up files.

    Returns::

        {"ok": bool, "restored": [str], "skipped": [str], "errors": [str]}
    """
    gate_errors = check_backup_gate(backup_dir)
    if gate_errors:
        return {"ok": False, "restored": [], "skipped": [], "errors": gate_errors}

    backup_path = Path(backup_dir)
    restored: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    target_set: set[str] | None = None
    if target_files is not None:
        target_set = {normalize_posix(t) for t in target_files}

    for bak_file in sorted(backup_path.rglob("*")):
        if not bak_file.is_file() or bak_file.name == "backupinfo.json":
            continue
        rel = bak_file.relative_to(backup_path)
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
            restored.append(str(original))
        except OSError as exc:
            errors.append(f"E_RESTORE_COPY_FAILED: {original}: {exc}")

    return {"ok": not errors, "restored": restored, "skipped": skipped, "errors": errors}


__all__ = [
    "get_game_backup_id",
    "build_filefoldertree_with_hashes",
    "load_backup_info",
    "init_backup_dir",
    "finalize_backup_dir",
    "check_backup_gate",
    "run_differential_backup",
    "apply_final_mapping",
    "restore_from_backup",
]

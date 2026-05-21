"""restore_ops.py — Pure restore primitive.

Executes file-to-file restore from backup directories.
Does NOT derive backup_dirs, does NOT handle directories, does NOT make decisions.
"""

from __future__ import annotations

import os
import shutil
from typing import Any, Callable

# ── Public API ──────────────────────────────────────────────────────────


def restore_entries(
    entries_by_backup_dir: dict[str, list[dict[str, Any]]],
    backupinfos: dict[str, dict[str, Any]],
    *,
    force: bool = False,
    on_progress: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Execute file-to-file restore.

    Args:
        entries_by_backup_dir: {backup_dir_path: [{path, request}, ...]}
        backupinfos: {backup_dir_path: backupinfo_dict} — pre-loaded by Planner.
        force: If True, skip hash verification.
        on_progress: Optional progress callback.

    Returns:
        dict with keys: ok, restored, skipped, orphans, errors, dry_run, force
    """
    restored: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    orphans: list[str] = []
    errors: list[str] = []
    warnings: list[str] = []

    total = sum(len(v) for v in entries_by_backup_dir.values())
    finished = 0

    for backup_dir, entries in entries_by_backup_dir.items():
        _notify(on_progress, "restore", finished, total, f"Restoring from {backup_dir}")

        backupinfo = backupinfos.get(backup_dir)
        if not backupinfo:
            errors.append(f"E_BACKUP_INFO_MISSING: no backupinfo for {backup_dir}")
            continue

        # Build a lookup of backed-up file hashes from the backupinfo tree
        hash_lookup: dict[str, tuple[str, str]] = {}
        _flatten_hash_lookup(backupinfo.get("tree", {}), backup_dir, hash_lookup)

        for entry in entries:
            target_path = entry["path"]
            request = entry.get("request")

            if request is None:
                skipped.append({"path": target_path, "reason": "no source (vacuous node)"})
                finished += 1
                continue

            # Resolve the backed-up file path (mirrors run_differential_backup's content_root logic)
            rel_path = _relative_to_backup_root(target_path, backup_dir)
            backup_file = os.path.join(backup_dir, rel_path)

            if not os.path.isfile(backup_file):
                warnings.append(f"W_RESTORE_NO_BACKUP_COPY: no backup copy found for {target_path}")
                finished += 1
                continue

            # ── Hash check (skip if force) ─────────────────────────────
            if not force:
                ht, hv = hash_lookup.get(rel_path, ("", ""))
                if ht and hv:
                    current_hash = _sha256_hex(target_path) if os.path.isfile(target_path) else ""
                    if current_hash == hv:
                        skipped.append({"path": target_path, "reason": "hash match — unchanged"})
                        finished += 1
                        continue

            # ── Execute restore ─────────────────────────────────────────
            try:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                shutil.copy2(backup_file, target_path)

                st = os.stat(target_path)
                restored.append({
                    "path": target_path,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                    "is_dir": False,
                })
            except PermissionError as exc:
                errors.append(f"E_RESTORE_PERMISSION: {target_path}: {exc}")
            except OSError as exc:
                errors.append(f"E_RESTORE_FAILED: {target_path}: {exc}")

            finished += 1
            _notify(on_progress, "restore", finished, total)

        # ── Detect orphans: files in backup_dir not in restore scope ──
        all_restore_targets = {
            e["path"] for entries in entries_by_backup_dir.values() for e in entries
        }
        for backup_dir in entries_by_backup_dir:
            if os.path.isdir(backup_dir):
                try:
                    for root, _dirs, files in os.walk(backup_dir):
                        for f in files:
                            if f == "backupinfo.json":
                                continue
                            full = os.path.join(root, f)
                            if full not in all_restore_targets:
                                orphans.append(full)
                except OSError:
                    pass
        if orphans:
            warnings.append(f"W_RESTORE_ORPHANS: {len(orphans)} orphan file(s) in backup_dir, not in restore scope")

    return {
        "ok": len(errors) == 0,
        "restored": restored,
        "skipped": skipped,
        "orphans": orphans,
        "errors": errors,
        "warnings": warnings,
        "dry_run": False,
        "force": force,
    }


# ── Internal helpers ────────────────────────────────────────────────────


def _flatten_hash_lookup(
    tree_node: dict[str, Any],
    base_dir: str,
    lookup: dict[str, tuple[str, str]],
    prefix: str = "",
    is_root: bool = True,
) -> None:
    """Walk the backupinfo tree and collect (hashtype, hashvalue) per file.

    Hash keys are relative paths matching the content_root-relative layout
    used by ``_relative_to_backup_root``.  The tree root's name is not
    included in keys — only paths below the source root are.
    """
    node_type = tree_node.get("type", "")
    name = tree_node.get("name", "")

    # Root node: skip its name, start from children
    if is_root:
        for child in tree_node.get("children", []):
            _flatten_hash_lookup(child, base_dir, lookup, prefix="", is_root=False)
        return

    current = f"{prefix}/{name}" if prefix else name

    if node_type == "file":
        ht = tree_node.get("hashtype", "")
        hv = tree_node.get("hashvalue", "")
        if ht and hv:
            lookup[current] = (ht, hv)
    elif node_type == "dir":
        for child in tree_node.get("children", []):
            _flatten_hash_lookup(child, base_dir, lookup, current, is_root=False)


def _relative_to_backup_root(target_path: str, backup_dir: str) -> str:
    """Compute the relative path of target_path within backup_dir.

    Mirrors run_differential_backup's derivation: content_root is the
    parent of backup_dir, and files are stored relative to it.
    """
    from pathlib import Path
    from .paths import normalize_posix

    content_root = str(Path(backup_dir).parent)
    rel = normalize_posix(target_path).removeprefix(
        normalize_posix(content_root)
    ).lstrip("/")
    return rel


def _sha256_hex(file_path: str) -> str:
    """Compute sha256 hex digest of a file."""
    import hashlib
    if not os.path.isfile(file_path):
        return ""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _notify(
    on_progress: Callable[..., None] | None,
    step: str,
    finished: int,
    total: int,
    message: str = "",
) -> None:
    if on_progress:
        on_progress(step, finished, total, message)

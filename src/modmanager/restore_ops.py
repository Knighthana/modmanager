"""restore_ops.py — Pure restore primitive.

Executes file-to-file restore from backup directories per DESIGN_RESTORE_OPS.md §四.
Does NOT derive backup_dirs, does NOT handle directories, does NOT make decisions.
"""

from __future__ import annotations

import os
import shutil
from typing import Any, Callable


def restore_entries(
    entries_by_backup_dir: dict[str, list[dict[str, Any]]],
    backupinfos: dict[str, dict[str, Any]],
    *,
    force: bool = False,
    dry_run: bool = False,
    on_progress: Callable[..., None] | None = None,
) -> dict[str, Any]:
    """Execute file-to-file restore per DESIGN_RESTORE_OPS.md §四.

    1. Load tree from backupinfo into memory.
    2. For each file in scope:
       - Tree has no node → DELETE source file directly.
       - isbackuped=false → skip + warning.
       - hashtype="invalid" or hashvalue="0" → skip + warning.
       - Hash same as tree → skip.
       - Hash different → add to batch operation list.
    3. After scope confirmed, execute batch (copy from backup_dir).

    Args:
        entries_by_backup_dir: {backup_dir_path: [{path, request}, ...]}
        backupinfos: {backup_dir_path: backupinfo_dict} — pre-loaded by Planner.
        force: If True, skip hash verification.
        dry_run: If True, simulate without modifying files.
        on_progress: Optional progress callback.

    Returns:
        dict with keys: ok, restored, skipped, orphans, errors, warnings, dry_run, force
    """
    restored: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    deleted: list[dict[str, Any]] = []
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

        tree = backupinfo.get("tree", {})

        # ── Phase 1: inspect tree, build batch list ────────────────
        batch: list[dict[str, Any]] = []

        for entry in entries:
            target_path = entry["path"]
            request = entry.get("request")

            if request is None:
                skipped.append({"path": target_path, "reason": "no source (vacuous node)"})
                finished += 1
                continue

            # Find node in tree by relative path
            rel_path = _relative_to_backup_root(target_path, backup_dir)
            node = _find_tree_node(tree, rel_path)

            # §四-3: tree 上无对应结点 → 直接删除源目录中的对应文件
            if node is None:
                try:
                    if not dry_run and os.path.isfile(target_path):
                        os.remove(target_path)
                    deleted.append({"action": "delete", "path": target_path, "reason": "node not in tree"})
                except OSError as exc:
                    errors.append(f"E_RESTORE_DELETE_FAILED: {target_path}: {exc}")
                finished += 1
                continue

            # §四-4: isbackuped=false → skip + warning
            if node.get("isbackuped") is False:
                warnings.append(f"W_RESTORE_NOT_BACKED_UP: {target_path} — isbackuped=false in tree")
                finished += 1
                continue

            # §四-4: hashtype="invalid" or hashvalue="0" → skip + warning
            ht = node.get("hashtype", "")
            hv = node.get("hashvalue", "")
            if ht == "invalid" or hv == "0" or not ht or not hv:
                warnings.append(f"W_RESTORE_INVALID_HASH: {target_path} — hashtype={ht}, hashvalue={hv}")
                finished += 1
                continue

            # §四-5: hash comparison
            if not force:
                current_hash = _sha256_hex(target_path) if os.path.isfile(target_path) else ""
                if current_hash == hv:
                    skipped.append({"path": target_path, "reason": "hash match — unchanged"})
                    finished += 1
                    continue

            # Hash mismatch or force=true → add to batch
            batch.append({"target_path": target_path, "backup_dir": backup_dir, "rel_path": rel_path})
            finished += 1

        # ── Phase 2: execute batch ─────────────────────────────────
        for item in batch:
            target_path = item["target_path"]
            backup_dir = item["backup_dir"]
            rel_path = item["rel_path"]
            backup_file = os.path.join(backup_dir, rel_path)

            if not os.path.isfile(backup_file):
                warnings.append(f"W_RESTORE_NO_BACKUP_COPY: no backup copy found for {target_path}")
                continue

            try:
                if not dry_run:
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    shutil.copy2(backup_file, target_path)

                st = os.stat(target_path if not dry_run else backup_file)
                restored.append({
                    "action": "restore",
                    "path": target_path,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                    "is_dir": False,
                })
            except PermissionError as exc:
                errors.append(f"E_RESTORE_PERMISSION: {target_path}: {exc}")
            except OSError as exc:
                errors.append(f"E_RESTORE_FAILED: {target_path}: {exc}")

        _notify(on_progress, "restore", total, total)

    return {
        "ok": len(errors) == 0,
        "restored": restored,
        "skipped": skipped,
        "deleted": deleted,
        "orphans": orphans,
        "errors": errors,
        "warnings": warnings,
        "dry_run": dry_run,
        "force": force,
    }


# ── Internal helpers ────────────────────────────────────────────────────


def _find_tree_node(tree: dict[str, Any], rel_path: str) -> dict[str, Any] | None:
    """Walk *tree* by *rel_path* components and return the leaf node, or None.

    Matching is case-insensitive — Windows game/mod files may have
    inconsistent casing between the file system and Steam metadata.
    """
    parts = rel_path.split("/")
    node = tree
    for part in parts:
        if node.get("type") != "dir":
            return None
        found = next(
            (c for c in node.get("children", [])
             if c.get("name", "").lower() == part.lower()),
            None
        )
        if found is None:
            return None
        node = found
    return node


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

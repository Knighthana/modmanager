"""User configuration lifecycle management — init (create/patch) + save (validate+sync)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .iojson import load_json_file, write_json_file
from .osplatform import defaultvalue as os_defaults

logger = logging.getLogger(__name__)

DEFAULTS: dict[str, Any] = {
    "schema_namespace": "KMM_UserConfig",
    "schema_version": "knighthana@0.1.0",
    "baksuffix": "kmmbackup",
    "bakignore": ["kmmbackup"],
    "rule_sources": {},
    "path_alias": [],
    "workspace_dir": None,
    "databases": {"default": {"path": ""}},
}
REQUIRED_KEYS = [k for k in DEFAULTS if k != "path_alias"]  # optional future-use field

_SCHEMA_PATH = Path(__file__).parent.parent.parent / "repo_spec" / "user_config.schema.json"


def userconfig_init(path: str) -> dict[str, Any]:
    """Create or patch user_config at *path*.

    - If file does not exist: create with all DEFAULTS, fill platform-specific
      workspace_dir and database path from os_defaults
    - If file exists with missing keys: fill from DEFAULTS (never overwrite)
    - If file exists but has invalid JSON: raise ValueError
    - If schema_namespace is wrong: raise ValueError (user corrupted the file)

    Returns:
        The complete user_config dict.
    """
    p = Path(path)

    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        pd = {
            "workspace_dir": os_defaults.workspace_dir_get(),
            "databases": {"default": {"path": os_defaults.database_path_get()}},
        }
        base = {**DEFAULTS, **pd}
        write_json_file(p, base)
        return base

    # File exists — load it
    try:
        config = load_json_file(p)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"Invalid JSON in user config: {path}") from exc

    if not isinstance(config, dict):
        raise ValueError(f"User config must be a dict: {path}")

    # Validate schema_namespace
    if config.get("schema_namespace") != DEFAULTS["schema_namespace"]:
        raise ValueError(f"Wrong schema_namespace in user config: {path}")

    # Fill missing keys from DEFAULTS — never overwrite existing values
    changed = False
    for key in REQUIRED_KEYS:
        if key not in config:
            config[key] = DEFAULTS[key]
            changed = True
        elif key == "workspace_dir" and (config[key] is None or config[key] == ""):
            config[key] = os_defaults.workspace_dir_get()
            changed = True

    # ── Migrate old rule_sources formats ──────────────────────────
    rs = config.get("rule_sources")
    if isinstance(rs, list):
        # Old format: ["~/path1", "~/path2"] → {"default": {"paths": [...]}}
        config["rule_sources"] = {"default": {"paths": rs}}
        changed = True
    elif isinstance(rs, dict):
        migrated = False
        new_rs: dict[str, Any] = {}
        for name, entry in rs.items():
            if isinstance(entry, dict):
                if "path" in entry and "paths" not in entry:
                    # Old format: {"name": {"path": "string"}} → {"name": {"paths": ["string"]}}
                    new_rs[name] = {"paths": [entry["path"]]}
                    migrated = True
                    continue
                elif "paths" in entry and isinstance(entry["paths"], list):
                    new_rs[name] = entry  # already correct
                    continue
            new_rs[name] = entry
        if migrated:
            config["rule_sources"] = new_rs
            changed = True

    if changed:
        write_json_file(p, config)

    return config


def userconfig_save(config_index: str, data: dict[str, Any]) -> None:
    """Save user_config at *config_index*.

    *config_index* is the opaque identifier returned by bootstrap — a file path.
    *data* is the complete user_config dict from the caller.

    Before writing:
    - Validate data against user_config.schema.json (if jsonschema available)
    - If baksuffix changed, sync bakignore: bakignore.append(new_baksuffix_value)

    Raises:
        ValueError: if schema validation fails
    """
    # Load existing data to detect baksuffix changes
    existing: dict[str, Any] = {}
    p = Path(config_index)
    if p.exists():
        try:
            existing = load_json_file(p)
        except (json.JSONDecodeError, ValueError):
            pass  # Will be overwritten anyway

    # -- Validate against schema --
    try:
        import jsonschema  # noqa: F811
    except ImportError:
        logger.warning("jsonschema not available; skipping schema validation for %s", config_index)
    else:
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(instance=data, schema=schema)
        except jsonschema.ValidationError as exc:
            # jsonschema error messages can be misleading — include the JSON path
            path_str = " → ".join(str(p) for p in exc.absolute_path) if exc.absolute_path else "(root)"
            raise ValueError(
                f"Schema validation failed for {config_index} at {path_str}: {exc.message}"
            ) from exc

    # -- Sync bakignore if baksuffix changed --
    old_baksuffix = existing.get("baksuffix")
    new_baksuffix = data.get("baksuffix")
    if old_baksuffix is not None and new_baksuffix is not None and old_baksuffix != new_baksuffix:
        bakignore = data.setdefault("bakignore", [])
        if new_baksuffix not in bakignore:
            bakignore.append(new_baksuffix)

    # -- Write --
    write_json_file(config_index, data)


__all__ = ["DEFAULTS", "REQUIRED_KEYS", "userconfig_init", "userconfig_save"]

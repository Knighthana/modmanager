"""Load and expose the compute_mapping output schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

_SCHEMA_PATH = Path(__file__).with_name("output_schema.json")

# Module-level cache – loaded once.
_SCHEMA: dict[str, Any] | None = None


def get_output_schema() -> dict[str, Any]:
    """Return the parsed JSON Schema for ComputeMappingOutput."""
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    
    if _SCHEMA is None:
        raise RuntimeError("Output schema failed to load")
     
    return _SCHEMA


def validate_output(data: Any) -> None:
    """Validate *data* against the ComputeMappingOutput schema.

    Raises :class:`jsonschema.ValidationError` on the first violation.
    """
    jsonschema.validate(instance=data, schema=get_output_schema())


def validate_output_collect(data: Any) -> list[str]:
    """Return all schema validation errors as a list of human-readable strings.

    Returns an empty list when *data* is valid.
    """
    validator = jsonschema.Draft7Validator(get_output_schema())
    return [
        f"{'.'.join(str(p) for p in err.absolute_path) or '<root>'}: {err.message}"
        for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    ]


__all__ = ["get_output_schema", "validate_output", "validate_output_collect"]

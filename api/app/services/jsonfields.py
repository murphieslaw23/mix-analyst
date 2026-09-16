"""Helpers for JSON columns whose driver may return raw strings.

Postgres JSON/JSONB deserializes on read, but values written as pre-encoded
strings (or SQLite TEXT fallbacks) can surface as `str`. Normalize at the
read boundary so response schemas always emit real arrays/objects.
"""

import json
from typing import Any


def parse_json_field(value: Any, default: Any = None) -> Any:
    """Return value parsed when it is a JSON string, else as-is."""
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            return default
    return value

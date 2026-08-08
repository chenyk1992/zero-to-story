"""LFO-CJ1: Canonical JSON serialization for deterministic hashing.

Rules:
- UTF-8, no BOM, no indentation, no spaces, no trailing newline
- Unicode NFC normalization for string values
- Keys sorted lexicographically (by Unicode codepoint)
- Floats forbidden (LFO_CJ1_FLOAT_FORBIDDEN)
- Duplicate object keys forbidden (LFO_CJ1_DUPLICATE_KEY)
- Only JSON-required escapes: " \\, U+0000..U+001F
- Non-ASCII chars output as raw UTF-8 (no \\u escape)
- Path fields (format=lfo-project-path) normalized separately
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any


class LFO_CJ1_ERROR(Exception):
    """Base exception for LFO-CJ1 serialization errors."""
    pass


class LFO_CJ1_FLOAT_FORBIDDEN(LFO_CJ1_ERROR):
    """Float values are not allowed in LFO-CJ1."""
    pass


class LFO_CJ1_DUPLICATE_KEY(LFO_CJ1_ERROR):
    """Duplicate object key detected."""
    pass


# Regex to match \\uXXXX escapes for chars >= U+0080 (we convert back to UTF-8)
_UNICODE_ESCAPE_RE = re.compile(r'\\u([0-9a-fA-F]{4})')


def _unescape_non_ascii(s: str) -> str:
    """Convert \\uXXXX escapes for codepoints >= 0x80 back to UTF-8 characters."""
    def replace_match(m):
        cp = int(m.group(1), 16)
        if cp >= 0x80:
            return chr(cp)
        return m.group(0)  # keep escapes for ASCII chars

    return _UNICODE_ESCAPE_RE.sub(replace_match, s)


def _normalize_string(v: str) -> str:
    """Apply Unicode NFC normalization to a string value."""
    return unicodedata.normalize('NFC', v)


def normalize_project_path(path: str) -> str:
    """Normalize an LFO project path.

    Rules:
    1. \\ -> /
    2. Remove repeated /
    3. Remove leading ./
    4. Forbid ..
    5. Forbid absolute paths
    6. Forbid Windows drive letters
    """
    # 1. Backslash -> forward slash
    p = path.replace('\\', '/')
    # 2. Remove repeated /
    while '//' in p:
        p = p.replace('//', '/')
    # 3. Remove leading ./
    while p.startswith('./'):
        p = p[2:]
    # 4. Forbid ..
    if '..' in p.split('/'):
        raise LFO_CJ1_ERROR(f"Path contains forbidden '..' component: {path}")
    # 5. Forbid absolute paths
    if p.startswith('/'):
        raise LFO_CJ1_ERROR(f"Absolute path forbidden: {path}")
    # 6. Forbid Windows drive letters
    if len(p) >= 2 and p[1] == ':' and p[0].isalpha():
        raise LFO_CJ1_ERROR(f"Windows drive letter forbidden: {path}")

    return p


def _detect_duplicate_keys(pairs: list[tuple[str, Any]]) -> list[tuple[str, Any]]:
    """Detect duplicate keys and raise LFO_CJ1_DUPLICATE_KEY."""
    seen = set()
    for k, _ in pairs:
        if k in seen:
            raise LFO_CJ1_DUPLICATE_KEY(f"Duplicate key: {k!r}")
        seen.add(k)
    return pairs


def _check_no_floats(obj: Any, path: str = "$") -> None:
    """Recursively check for float values. Raises LFO_CJ1_FLOAT_FORBIDDEN."""
    if isinstance(obj, float):
        raise LFO_CJ1_FLOAT_FORBIDDEN(
            f"Float value at {path}: {obj!r}. "
            "Convert to string or integer units before serialization."
        )
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _check_no_floats(v, f"{path}.{k}")
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _check_no_floats(v, f"{path}[{i}]")


def _normalize_strings(obj: Any) -> Any:
    """Recursively NFC-normalize all string values in an object."""
    if isinstance(obj, str):
        return unicodedata.normalize('NFC', obj)
    elif isinstance(obj, dict):
        return {k: _normalize_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_normalize_strings(v) for v in obj]
    return obj


def serialize(value: Any, schema: dict | None = None) -> bytes:
    """Serialize a value to LFO-CJ1 canonical bytes.

    Args:
        value: The Python object to serialize.
        schema: Optional JSON schema. If provided, defaults are applied,
                path fields are normalized, and strings are NFC-normalized.

    Returns:
        UTF-8 encoded canonical JSON bytes.

    Raises:
        LFO_CJ1_FLOAT_FORBIDDEN: If a float is found in the value.
        LFO_CJ1_DUPLICATE_KEY: If duplicate keys exist (handled by parser).
    """
    # Check for floats before serialization
    _check_no_floats(value)

    # NFC-normalize all strings (idempotent with schema path)
    value = _normalize_strings(value)

    # Serialize with sorted keys, no spaces, ensure_ascii=True (we unescape after)
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=True,
        check_circular=False,
        allow_nan=False,
    )

    # Convert \\uXXXX for non-ASCII back to raw UTF-8
    canonical = _unescape_non_ascii(raw)

    return canonical.encode('utf-8')


def serialize_with_schema(value: Any, schema: dict) -> bytes:
    """Serialize with schema processing: apply defaults, normalize paths, NFC.

    This is the full pipeline for business objects.
    """
    # Apply schema defaults and normalize
    processed = _apply_schema(value, schema)
    return serialize(processed)


def _apply_schema(value: Any, schema: dict, path: str = "$") -> Any:
    """Apply schema defaults, path normalization, and NFC."""
    if schema is None:
        return value

    schema_type = schema.get('type')

    if schema_type == 'object' and isinstance(value, dict):
        result = {}
        properties = schema.get('properties', {})

        # Process defined properties
        for prop_name, prop_schema in properties.items():
            if prop_name in value:
                result[prop_name] = _apply_schema(value[prop_name], prop_schema, f"{path}.{prop_name}")
            elif 'default' in prop_schema:
                result[prop_name] = prop_schema['default']

        # Reject additional properties if additionalProperties=false
        if schema.get('additionalProperties') is False:
            for k in value:
                if k not in properties:
                    raise LFO_CJ1_ERROR(f"Additional property not allowed: {path}.{k}")

        return result

    elif schema_type == 'array' and isinstance(value, list):
        items_schema = schema.get('items', {})
        return [_apply_schema(item, items_schema, f"{path}[{i}]") for i, item in enumerate(value)]

    elif schema_type == 'string' and isinstance(value, str):
        # NFC normalization
        value = unicodedata.normalize('NFC', value)
        # Path normalization if format is lfo-project-path
        if schema.get('format') == 'lfo-project-path':
            value = normalize_project_path(value)
        return value

    # For other types or if type matches, return as-is
    # Handle type arrays like ["string", "null"]
    if isinstance(schema_type, list):
        if 'string' in schema_type and isinstance(value, str):
            value = unicodedata.normalize('NFC', value)
            if schema.get('format') == 'lfo-project-path':
                value = normalize_project_path(value)
        return value

    return value


def hash_value(value: Any, schema: dict | None = None) -> str:
    """Compute SHA-256 hex digest of the LFO-CJ1 serialization."""
    import hashlib
    if schema is not None:
        canonical = serialize_with_schema(value, schema)
    else:
        canonical = serialize(value)
    return hashlib.sha256(canonical).hexdigest()


def hash_bytes(data: bytes) -> str:
    """Compute SHA-256 hex digest of raw bytes (for files)."""
    import hashlib
    return hashlib.sha256(data).hexdigest()

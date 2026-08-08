"""Hashing primitives for LFO entities.

LFO-WFJ1: Workflow JSON hash spec (distinct from LFO-CJ1).
- LFO-CJ1 forbids floats (for business entities).
- LFO-WFJ1 allows and normalizes floats (for ComfyUI workflows).
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from .canonical import hash_bytes, hash_value

# LFO-WFJ1 algorithm identifier
WORKFLOW_HASH_ALGORITHM = "lfo-wfj1-sha256-v1"


def compute_content_hash(entity: dict, schema: dict | None = None) -> str:
    """Compute the content hash of an entity.

    The content hash captures the semantic identity of the entity:
    same content → same hash, regardless of when/where it was computed.
    """
    return hash_value(entity, schema)


def compute_dependency_hash(upstream_hashes: list[str]) -> str:
    """Compute the dependency hash from a list of upstream content hashes.

    Represents the closure of all upstream entities. If any upstream changes,
    the dependency hash changes.
    """
    # Sort for determinism
    sorted_hashes = sorted(upstream_hashes)
    combined = "\n".join(sorted_hashes)
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def compute_params_hash(params: dict) -> str:
    """Compute the hash of execution parameters.

    These are parameters that don't affect the semantic identity but
    do affect the execution contract (seed, resolution, etc).
    """
    return hash_value(params)


def compute_idempotency_key(
    content_hash: str,
    dependency_hash: str,
    params_hash: str,
) -> str:
    """Compute the idempotency key.

    The idempotency_key uniquely identifies a generation attempt:
    same content + same upstream + same params → same key.
    This enables deduplication and safe retries.
    """
    combined = f"{content_hash}:{dependency_hash}:{params_hash}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def compute_compiler_identity(
    workflow_hash: str,
    compiler_version: str,
    adapter_version: str,
) -> str:
    """Compute the compiler identity hash.

    Captures the full compilation toolchain identity so that
    toolchain changes invalidate downstream results.
    """
    combined = f"{workflow_hash}:{compiler_version}:{adapter_version}"
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()


def _normalize_wfj1_numbers(obj: Any) -> Any:
    """Normalize numbers for LFO-WFJ1 serialization.

    Rules:
    - Floats equal to an integer (12.0, 1.0e2) → int (12, 100).
      This makes ``12.0`` and ``12`` produce identical hashes.
    - ``-0.0`` → ``0`` (canonical zero).
    - NaN / Infinity are rejected downstream by ``allow_nan=False``.
    - Other floats (0.4, 3.14) pass through unchanged.
    """
    if isinstance(obj, float):
        # Canonicalise -0.0 → 0 and integer-valued floats → int
        if math.isnan(obj) or math.isinf(obj):
            return obj  # let json.dumps(allow_nan=False) reject it
        if obj == 0.0:
            return 0
        if obj == int(obj):
            return int(obj)
        return obj
    if isinstance(obj, dict):
        return {k: _normalize_wfj1_numbers(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_wfj1_numbers(v) for v in obj]
    return obj


def compute_workflow_hash(workflow_json: dict) -> str:
    """Compute the LFO-WFJ1 hash of a ComfyUI workflow (API format).

    LFO-WFJ1 rules:
    - Object keys sorted lexicographically.
    - Array order preserved.
    - Floats with no fractional part normalised to int (12.0 → 12).
    - ``-0.0`` normalised to ``0``.
    - NaN / Infinity rejected (``ValueError``).
    - Unicode NFC for strings.
    - Compact JSON: UTF-8, no spaces, no newlines.
    - Algorithm: SHA-256, 64-char lowercase hex.
    """
    # Step 1: Normalise numbers in-place
    normalised = _normalize_wfj1_numbers(workflow_json)

    # Step 2: NFC-normalise strings
    from .canonical import _normalize_strings
    normalised = _normalize_strings(normalised)

    # Step 3: Serialise (allow_nan=False rejects NaN/Infinity)
    raw = json.dumps(
        normalised,
        sort_keys=True,
        separators=(',', ':'),
        ensure_ascii=False,
        check_circular=False,
        allow_nan=False,
    )
    return hash_bytes(raw.encode('utf-8'))


def compute_file_hash(file_path) -> str:
    """Compute SHA-256 hash of a file's contents."""
    import pathlib
    path = pathlib.Path(file_path)
    data = path.read_bytes()
    return hash_bytes(data)

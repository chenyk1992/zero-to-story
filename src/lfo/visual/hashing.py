"""Visual domain hashing — LFO-CJ1 via core/canonical + core/hashing.

Used for Provider/Profile/Contract/Manifest/Routing/Exchange meta and
Compiler Identity. NEVER use compute_workflow_hash() (that's LFO-WFJ1
for workflow JSON with floats).
"""
from __future__ import annotations

from lfo.core.canonical import serialize
from lfo.core.hashing import hash_bytes


def hash_visual_object(obj: dict) -> str:
    """Compute the LFO-CJ1 semantic hash of a visual-domain object.

    Uses serialize() for canonicalization (no floats, NFC, sorted keys)
    and hash_bytes() for the final SHA-256.

    Args:
        obj: A JSON-serializable dict with no float values.

    Returns:
        64-char lowercase hex SHA-256 digest.

    Raises:
        LFO_CJ1_FLOAT_FORBIDDEN: If a float value is found in obj.
    """
    canonical = serialize(obj)
    return hash_bytes(canonical)

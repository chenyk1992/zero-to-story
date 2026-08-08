"""Visual Bible hashing — reuses LFO-CJ1 infrastructure.

Processing order:
1. Schema validation
2. Serialize to dict (via VisualBible.to_dict)
3. LFO-CJ1 Canonicalization (via core/canonical.py::serialize)
4. hash_value() (via core/hashing.py)

NEVER use compute_workflow_hash() — that's for workflow JSON with floats.
"""
from __future__ import annotations

from lfo.core.canonical import serialize
from lfo.core.hashing import hash_bytes
from lfo.visual_bible.schema import VisualBible
from lfo.visual_bible.validate import validate_visual_bible


def compute_visual_bible_hash(vb: VisualBible) -> str:
    """Compute LFO-CJ1 semantic hash of a Visual Bible.

    Uses serialize() for canonicalization and hash_bytes() for the
    final SHA-256 — both from the LFO-CJ1 toolchain.
    """
    # 1. Validate
    valid, errors = validate_visual_bible(vb)
    if not valid:
        raise ValueError(f"Invalid visual bible: {'; '.join(errors)}")

    # 2. Serialize to dict
    data = vb.to_dict()

    # 3. Canonicalize (LFO-CJ1) — returns canonical UTF-8 bytes
    canonical = serialize(data)

    # 4. Hash
    return hash_bytes(canonical)

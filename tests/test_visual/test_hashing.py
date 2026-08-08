"""Tests for visual LFO-CJ1 hashing."""
from __future__ import annotations

import pytest

from lfo.core.canonical import LFO_CJ1_FLOAT_FORBIDDEN
from lfo.visual.hashing import hash_visual_object


def test_same_dict_reordered_keys_identical_hash():
    """Key order must not affect the CJ1 hash."""
    a = {"b": 2, "a": 1, "c": {"e": 5, "d": 4}}
    b = {"c": {"d": 4, "e": 5}, "a": 1, "b": 2}
    assert hash_visual_object(a) == hash_visual_object(b)


def test_different_dicts_different_hash():
    a = {"a": 1}
    b = {"a": 2}
    assert hash_visual_object(a) != hash_visual_object(b)


def test_hash_is_sha256_hex():
    """Hash must be a 64-char lowercase hex string."""
    import re
    h = hash_visual_object({"x": "hello"})
    assert re.match(r'^[0-9a-f]{64}$', h)


def test_empty_dict_stable_hash():
    h1 = hash_visual_object({})
    h2 = hash_visual_object({})
    assert h1 == h2


def test_unicode_nfc_normalization():
    """NFC-equivalent strings must hash identically."""
    # é as single codepoint vs e + combining accent
    a = {"name": "e\u0301"}  # decomposed
    b = {"name": "\u00e9"}    # composed
    assert hash_visual_object(a) == hash_visual_object(b)


def test_floats_rejected():
    """LFO-CJ1 must reject floats."""
    with pytest.raises(LFO_CJ1_FLOAT_FORBIDDEN):
        hash_visual_object({"v": 1.5})

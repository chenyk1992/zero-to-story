"""Tests for LFO-WFJ1 workflow hash spec.

Verifies float normalization, -0.0 handling, NaN rejection,
and the distinguishability of static vs runtime validation levels.
"""
import json

import pytest

from lfo.core.hashing import WORKFLOW_HASH_ALGORITHM, compute_workflow_hash


class TestWFJ1AlgorithmIdentifier:
    def test_algorithm_string_format(self):
        assert WORKFLOW_HASH_ALGORITHM == "lfo-wfj1-sha256-v1"

    def test_hash_is_sha256_hex(self):
        wf = {"1": {"class_type": "SaveVideo", "inputs": {}}}
        h = compute_workflow_hash(wf)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)


class TestWFJ1FloatNormalization:
    """12.0 and 12 must produce the same hash."""

    def test_integer_valued_float_equals_int(self):
        wf_a = {"1": {"class_type": "Test", "inputs": {"val": 12}}}
        wf_b = {"1": {"class_type": "Test", "inputs": {"val": 12.0}}}
        assert compute_workflow_hash(wf_a) == compute_workflow_hash(wf_b)

    def test_shift_video_common_value(self):
        """H3 workflow has shift_video: 12.0 — should hash same as 12."""
        wf_a = {"6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"shift_video": 12}}}
        wf_b = {"6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"shift_video": 12.0}}}
        assert compute_workflow_hash(wf_a) == compute_workflow_hash(wf_b)

    def test_fractional_float_preserved(self):
        """0.4 must NOT be equal to 0 or 1."""
        wf_a = {"1": {"class_type": "Test", "inputs": {"val": 0.4}}}
        wf_b = {"1": {"class_type": "Test", "inputs": {"val": 0}}}
        wf_c = {"1": {"class_type": "Test", "inputs": {"val": 1}}}
        ha = compute_workflow_hash(wf_a)
        assert ha != compute_workflow_hash(wf_b)
        assert ha != compute_workflow_hash(wf_c)

    def test_megapixels_point_four(self):
        """H3 workflow has megapixels: 0.4."""
        wf = {"6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"megapixels": 0.4}}}
        h = compute_workflow_hash(wf)
        assert len(h) == 64

    def test_negative_zero_equals_zero(self):
        """-0.0 must hash same as 0 and 0.0."""
        wf_a = {"1": {"class_type": "Test", "inputs": {"val": 0}}}
        wf_b = {"1": {"class_type": "Test", "inputs": {"val": 0.0}}}
        wf_c = {"1": {"class_type": "Test", "inputs": {"val": -0.0}}}
        assert compute_workflow_hash(wf_a) == compute_workflow_hash(wf_b)
        assert compute_workflow_hash(wf_a) == compute_workflow_hash(wf_c)

    def test_large_integer_valued_float(self):
        """1e6 (= 1000000.0) should hash same as 1000000."""
        wf_a = {"1": {"class_type": "Test", "inputs": {"val": 1000000}}}
        wf_b = {"1": {"class_type": "Test", "inputs": {"val": 1e6}}}
        assert compute_workflow_hash(wf_a) == compute_workflow_hash(wf_b)


class TestWFJ1NaNRejection:
    def test_nan_raises(self):
        wf = {"1": {"class_type": "Test", "inputs": {"val": float("nan")}}}
        with pytest.raises(ValueError):
            compute_workflow_hash(wf)

    def test_positive_infinity_raises(self):
        wf = {"1": {"class_type": "Test", "inputs": {"val": float("inf")}}}
        with pytest.raises(ValueError):
            compute_workflow_hash(wf)

    def test_negative_infinity_raises(self):
        wf = {"1": {"class_type": "Test", "inputs": {"val": float("-inf")}}}
        with pytest.raises(ValueError):
            compute_workflow_hash(wf)


class TestWFJ1KeyOrder:
    def test_key_order_invariant(self):
        wf_a = {"2": {"b": 1, "a": 2}, "1": {"x": 3}}
        wf_b = {"1": {"x": 3}, "2": {"a": 2, "b": 1}}
        assert compute_workflow_hash(wf_a) == compute_workflow_hash(wf_b)

    def test_nested_key_order_invariant(self):
        wf_a = {"1": {"class_type": "Test", "inputs": {"z": 1, "a": 2}}}
        wf_b = {"1": {"class_type": "Test", "inputs": {"a": 2, "z": 1}}}
        assert compute_workflow_hash(wf_a) == compute_workflow_hash(wf_b)


class TestWFJ1ArrayOrder:
    def test_array_order_matters(self):
        """Array order MUST be preserved — different order = different hash."""
        wf_a = {"1": {"inputs": {"list": [1, 2, 3]}}}
        wf_b = {"1": {"inputs": {"list": [3, 2, 1]}}}
        assert compute_workflow_hash(wf_a) != compute_workflow_hash(wf_b)

    def test_array_same_order_same_hash(self):
        wf_a = {"1": {"inputs": {"list": ["a", "b", "c"]}}}
        wf_b = {"1": {"inputs": {"list": ["a", "b", "c"]}}}
        assert compute_workflow_hash(wf_a) == compute_workflow_hash(wf_b)


class TestWFJ1RealWorkflowFragments:
    def test_h3_t2v_style_fragment(self):
        """Realistic H3 T2V fragment with shift_video and megapixels."""
        wf = {
            "6": {
                "class_type": "MiniMaxH3ImageToVideo",
                "inputs": {
                    "shift_video": 12.0,
                    "megapixels": 0.4,
                    "length": 124,
                    "prompt": "test",
                },
            },
            "12": {
                "class_type": "SaveVideo",
                "inputs": {"filename_prefix": "lfo/proj01/task01/att001/video"},
            },
        }
        h = compute_workflow_hash(wf)
        assert len(h) == 64

        # Now with shift_video as int 12 instead of 12.0
        wf2 = json.loads(json.dumps(wf))
        wf2["6"]["inputs"]["shift_video"] = 12
        h2 = compute_workflow_hash(wf2)
        assert h == h2


class TestWFJ1Determinism:
    def test_same_workflow_same_hash(self):
        wf = {
            "6": {"class_type": "MiniMaxH3ImageToVideo", "inputs": {"shift_video": 12.0}},
            "12": {"class_type": "SaveVideo", "inputs": {}},
        }
        h1 = compute_workflow_hash(wf)
        h2 = compute_workflow_hash(wf)
        assert h1 == h2

    def test_different_prompt_different_hash(self):
        wf_a = {"6": {"class_type": "Test", "inputs": {"prompt": "hello"}}}
        wf_b = {"6": {"class_type": "Test", "inputs": {"prompt": "world"}}}
        assert compute_workflow_hash(wf_a) != compute_workflow_hash(wf_b)

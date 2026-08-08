"""Tests for LFO-CJ1 canonical JSON serialization and hashing."""
import json
import pathlib

import pytest

from lfo.core.canonical import (
    LFO_CJ1_ERROR,
    LFO_CJ1_FLOAT_FORBIDDEN,
    hash_value,
    normalize_project_path,
    serialize,
)
from lfo.core.hashing import (
    compute_content_hash,
    compute_dependency_hash,
    compute_file_hash,
    compute_idempotency_key,
)

FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures"
VECTORS_FILE = FIXTURES_DIR / "lfo_cj1_vectors.json"


def load_vectors():
    with open(VECTORS_FILE, encoding="utf-8") as f:
        return json.load(f)["vectors"]


# --------------------------------------------------------------------------- #
# Vector tests
# --------------------------------------------------------------------------- #


class TestCJ1EmptyObject:
    def test_empty_object_hash(self):
        vectors = load_vectors()
        v = next(v for v in vectors if v["id"] == "empty_object")
        result = hash_value(v["input"])
        assert result == v["expected_sha256"]


class TestCJ1KeyOrder:
    def test_key_order_same_hash(self):
        vectors = load_vectors()
        va = next(v for v in vectors if v["id"] == "key_order_a")
        vb = next(v for v in vectors if v["id"] == "key_order_b")
        assert hash_value(va["input"]) == hash_value(vb["input"])
        assert hash_value(va["input"]) == va["expected_sha256"]


class TestCJ1UnicodeNFC:
    def test_nfc_equivalence(self):
        vectors = load_vectors()
        va = next(v for v in vectors if v["id"] == "unicode_nfc_single")
        vb = next(v for v in vectors if v["id"] == "unicode_nfc_decomposed")
        assert hash_value(va["input"]) == hash_value(vb["input"])
        assert hash_value(va["input"]) == va["expected_sha256"]


class TestCJ1FloatForbidden:
    def test_float_raises(self):
        vectors = load_vectors()
        v = next(v for v in vectors if v["id"] == "float_forbidden")
        with pytest.raises(LFO_CJ1_FLOAT_FORBIDDEN):
            hash_value(v["input"])


class TestCJ1DefaultNull:
    def test_default_null_equals_explicit(self):
        vectors = load_vectors()
        va = next(v for v in vectors if v["id"] == "default_null_vs_missing_with_schema")
        vb = next(v for v in vectors if v["id"] == "explicit_null_with_schema")
        schema = va["schema"]
        assert hash_value(va["input"], schema) == hash_value(vb["input"], schema)
        assert hash_value(va["input"], schema) == va["expected_sha256"]


class TestCJ1ProjectPath:
    def test_path_normalization(self):
        vectors = load_vectors()
        v = next(v for v in vectors if v["id"] == "project_path_backslash")
        schema = v["schema"]
        result = hash_value(v["input"], schema)
        assert result == v["expected_sha256"]


# --------------------------------------------------------------------------- #
# Behavior tests
# --------------------------------------------------------------------------- #


class TestCanonicalBytes:
    def test_no_indentation(self):
        result = serialize({"a": 1, "b": 2})
        assert b"  " not in result
        assert b"\n" not in result

    def test_sorted_keys(self):
        result = serialize({"z": 1, "a": 2})
        assert result.index(b'"a"') < result.index(b'"z"')

    def test_no_float(self):
        with pytest.raises(LFO_CJ1_FLOAT_FORBIDDEN):
            serialize({"v": 0.1})

    def test_nested_float(self):
        with pytest.raises(LFO_CJ1_FLOAT_FORBIDDEN):
            serialize({"outer": {"inner": 3.14}})

    def test_list_float(self):
        with pytest.raises(LFO_CJ1_FLOAT_FORBIDDEN):
            serialize({"values": [1.0, 2.0]})


class TestPathNormalization:
    def test_backslash_to_forward(self):
        assert normalize_project_path("a\\b.png") == "a/b.png"

    def test_remove_repeated_slashes(self):
        assert normalize_project_path("a//b.png") == "a/b.png"

    def test_remove_leading_dot_slash(self):
        assert normalize_project_path("./a/b.png") == "a/b.png"

    def test_forbid_double_dots(self):
        with pytest.raises(LFO_CJ1_ERROR):
            normalize_project_path("../secret.png")

    def test_forbid_absolute(self):
        with pytest.raises(LFO_CJ1_ERROR):
            normalize_project_path("/etc/passwd")

    def test_forbid_drive_letter(self):
        with pytest.raises(LFO_CJ1_ERROR):
            normalize_project_path("C:\\Windows\\test.png")


class TestContentHash:
    def test_same_content_same_hash(self):
        entity = {"type": "character", "name": "Mira", "age": 25}
        assert compute_content_hash(entity) == compute_content_hash(entity)

    def test_different_content_different_hash(self):
        a = {"type": "character", "name": "Mira"}
        b = {"type": "character", "name": "Kira"}
        assert compute_content_hash(a) != compute_content_hash(b)

    def test_order_independent(self):
        a = {"b": 1, "a": 2}
        b = {"a": 2, "b": 1}
        assert compute_content_hash(a) == compute_content_hash(b)


class TestDependencyHash:
    def test_same_upstream_same_hash(self):
        hashes = ["aaa", "bbb", "ccc"]
        assert compute_dependency_hash(hashes) == compute_dependency_hash(hashes)

    def test_order_independent(self):
        a = ["aaa", "bbb"]
        b = ["bbb", "aaa"]
        assert compute_dependency_hash(a) == compute_dependency_hash(b)

    def test_different_upstream_different_hash(self):
        a = ["aaa", "bbb"]
        b = ["aaa", "ccc"]
        assert compute_dependency_hash(a) != compute_dependency_hash(b)


class TestIdempotencyKey:
    def test_deterministic(self):
        key1 = compute_idempotency_key("c1", "d1", "p1")
        key2 = compute_idempotency_key("c1", "d1", "p1")
        assert key1 == key2

    def test_different_content_different_key(self):
        key1 = compute_idempotency_key("c1", "d1", "p1")
        key2 = compute_idempotency_key("c2", "d1", "p1")
        assert key1 != key2

    def test_different_params_different_key(self):
        key1 = compute_idempotency_key("c1", "d1", "p1")
        key2 = compute_idempotency_key("c1", "d1", "p2")
        assert key1 != key2


class TestFileHash:
    def test_same_file_same_hash(self, tmp_path):
        p = tmp_path / "test.txt"
        p.write_text("hello")
        assert compute_file_hash(p) == compute_file_hash(p)

    def test_different_files_different_hash(self, tmp_path):
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("hello")
        b.write_text("world")
        assert compute_file_hash(a) != compute_file_hash(b)

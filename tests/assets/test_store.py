"""Tests for content-addressed storage."""
from __future__ import annotations

import pathlib

import pytest

from lfo.assets.store import ContentAddressedStore


@pytest.fixture
def cas_tmp(tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path / "cas"


@pytest.fixture
def cas(cas_tmp: pathlib.Path) -> ContentAddressedStore:
    return ContentAddressedStore(cas_tmp)


class TestContentAddressedStore:
    def test_store_and_retrieve(self, cas: ContentAddressedStore, tmp_path: pathlib.Path) -> None:
        src = tmp_path / "test.png"
        src.write_bytes(b"fake image content")
        ref = cas.store_file(src, "hero.png")
        assert ref.blob_hash
        assert ref.size == len(b"fake image content")
        assert ref.path.is_file()
        assert ref.path.read_bytes() == b"fake image content"

    def test_deduplication(self, cas: ContentAddressedStore, tmp_path: pathlib.Path) -> None:
        """Same content → same blob path (de-dup)."""
        src1 = tmp_path / "a.png"
        src1.write_bytes(b"same content")
        src2 = tmp_path / "b.png"
        src2.write_bytes(b"same content")
        ref1 = cas.store_file(src1, "file1.png")
        ref2 = cas.store_file(src2, "file1.png")
        assert ref1.blob_hash == ref2.blob_hash

    def test_different_content_different_hash(self, cas: ContentAddressedStore, tmp_path: pathlib.Path) -> None:
        src1 = tmp_path / "a.png"
        src1.write_bytes(b"content A")
        src2 = tmp_path / "b.png"
        src2.write_bytes(b"content B")
        ref1 = cas.store_file(src1, "a.png")
        ref2 = cas.store_file(src2, "b.png")
        assert ref1.blob_hash != ref2.blob_hash

    def test_original_filename_preserved(self, cas: ContentAddressedStore, tmp_path: pathlib.Path) -> None:
        src = tmp_path / "tmpfile"
        src.write_bytes(b"data")
        ref = cas.store_file(src, "pretty_name.png")
        assert ref.path.name == "pretty_name.png"

    def test_has_blob(self, cas: ContentAddressedStore, tmp_path: pathlib.Path) -> None:
        src = tmp_path / "test.png"
        src.write_bytes(b"hello")
        ref = cas.store_file(src)
        assert cas.has_blob(ref.blob_hash) is True
        assert cas.has_blob("0" * 64) is False

    def test_resolve_blob(self, cas: ContentAddressedStore, tmp_path: pathlib.Path) -> None:
        src = tmp_path / "test.png"
        src.write_bytes(b"hello")
        ref = cas.store_file(src, "findme.png")
        resolved = cas.resolve_blob(ref.blob_hash, "findme.png")
        assert resolved == ref.path

    def test_resolve_blob_missing(self, cas: ContentAddressedStore) -> None:
        assert cas.resolve_blob("0" * 64, "nope.png") is None

    def test_source_deleted_after_import(self, cas: ContentAddressedStore, tmp_path: pathlib.Path) -> None:
        """After import, deleting the source must not affect the CAS."""
        src = tmp_path / "test.png"
        src.write_bytes(b"important data")
        ref = cas.store_file(src, "stored.png")
        src.unlink()  # delete source
        assert ref.path.is_file()
        assert ref.path.read_bytes() == b"important data"

    def test_empty_file_rejected(self, cas: ContentAddressedStore, tmp_path: pathlib.Path) -> None:
        src = tmp_path / "empty.png"
        src.write_bytes(b"")
        with pytest.raises(Exception, match="empty"):
            cas.store_file(src)

    def test_nonexistent_file_rejected(self, cas: ContentAddressedStore, tmp_path: pathlib.Path) -> None:
        with pytest.raises(Exception, match="does not exist"):
            cas.store_file(tmp_path / "ghost.png")

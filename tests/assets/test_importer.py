"""Tests for asset importer."""
from __future__ import annotations

import pathlib
from unittest import mock

import pytest

from lfo.assets.importer import AssetImporter, ImportResult
from lfo.assets.paths import PathSecurityError
from lfo.assets.probe import MediaProbe, ProbeResult
from lfo.assets.store import ContentAddressedStore


class TestAssetImporter:
    def test_import_png(
        self, tmp_path: pathlib.Path
    ) -> None:
        pkg = tmp_path / "package"
        assets = pkg / "assets"
        assets.mkdir(parents=True)
        (assets / "hero.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        cas = ContentAddressedStore(tmp_path / "cas")
        probe = MediaProbe(ffprobe_path=None)
        importer = AssetImporter(cas, probe)

        result = importer.import_asset(
            "hero.img", "assets/hero.png", pkg, declared_media_type="image"
        )
        assert result.asset_key == "hero.img"
        assert result.media_type == "image"
        assert result.blob_ref.path.is_file()
        assert result.blob_ref.path.read_bytes() == b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    def test_import_type_mismatch(
        self, tmp_path: pathlib.Path
    ) -> None:
        pkg = tmp_path / "package"
        assets = pkg / "assets"
        assets.mkdir(parents=True)
        (assets / "hero.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        cas = ContentAddressedStore(tmp_path / "cas")
        probe = MediaProbe(ffprobe_path=None)
        importer = AssetImporter(cas, probe)

        with pytest.raises(ValueError, match="mismatch"):
            importer.import_asset(
                "hero.img", "assets/hero.png", pkg, declared_media_type="video"
            )

    def test_import_unsafe_path(
        self, tmp_path: pathlib.Path
    ) -> None:
        pkg = tmp_path / "package"
        pkg.mkdir(parents=True)
        cas = ContentAddressedStore(tmp_path / "cas")
        probe = MediaProbe(ffprobe_path=None)
        importer = AssetImporter(cas, probe)

        with pytest.raises(PathSecurityError):
            importer.import_asset(
                "evil", "../../../etc/passwd", pkg
            )

    def test_import_missing_file(
        self, tmp_path: pathlib.Path
    ) -> None:
        pkg = tmp_path / "package"
        pkg.mkdir(parents=True)
        cas = ContentAddressedStore(tmp_path / "cas")
        probe = MediaProbe(ffprobe_path=None)
        importer = AssetImporter(cas, probe)

        with pytest.raises(Exception):
            importer.import_asset("x", "ghost.png", pkg)

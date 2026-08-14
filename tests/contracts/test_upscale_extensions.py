"""Contract tests for optional post-H3 upscale settings."""
from __future__ import annotations

from lfo.contracts.package import SCHEMA_ID, validate_package
from lfo.contracts.upscale import resolve_upscale_options


def _package(*, extensions: dict | None = None, clip_extensions: dict | None = None) -> dict:
    return {
        "schema": SCHEMA_ID,
        "package_id": "upscale-package",
        "revision": 1,
        "project": {"title": "Upscale", "project_id": "upscale-project"},
        "assets": [],
        "clips": [
            {
                "clip_id": "clip-1",
                "sequence": 1,
                "duration_ms": 5_000,
                "generation": {
                    "operation": "video.text_to_video",
                    "prompt": "A quiet test scene",
                    "requirements": {},
                },
                "extensions": clip_extensions or {},
            }
        ],
        "output": {},
        "extensions": extensions or {},
    }


def test_unrelated_extensions_remain_valid() -> None:
    result = validate_package(_package(extensions={"creative_notes": {"shot": "01"}}))
    assert result.ok


def test_clip_upscale_overlays_package_defaults() -> None:
    options = resolve_upscale_options(
        {"upscale": {"enabled": True, "scale_multiplier": 1.5, "seed": 42}},
        {"upscale": {"scale_multiplier": 2}},
    )
    assert options.enabled is True
    assert options.scale_multiplier == 2.0
    assert options.seed == 42

    disabled = resolve_upscale_options(
        {"upscale": {"enabled": True, "scale_multiplier": 2}},
        {"upscale": {"enabled": False}},
    )
    assert disabled.enabled is False


def test_upscale_defaults_to_disabled() -> None:
    options = resolve_upscale_options({}, {})
    assert options.enabled is False
    assert options.scale_multiplier == 2.0
    assert options.seed is None


def test_invalid_package_upscale_options_report_precise_paths() -> None:
    package = _package(
        extensions={"upscale": {"enabled": "yes", "scale_multiplier": 0}},
        clip_extensions={"upscale": {"seed": True}},
    )
    errors = {error.path for error in validate_package(package).errors()}
    assert "$.extensions.upscale.enabled" in errors
    assert "$.extensions.upscale.scale_multiplier" in errors
    assert "$.clips[0].extensions.upscale.seed" in errors


def test_upscale_config_must_be_an_object() -> None:
    package = _package(extensions={"upscale": "enabled"})
    errors = validate_package(package).errors()
    assert any(error.path == "$.extensions.upscale" for error in errors)

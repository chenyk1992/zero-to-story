"""Focused contract coverage for explicitly disabled subtitles."""

from __future__ import annotations

import json
from pathlib import Path

from lfo.contracts.timeline import OutputPolicy


def test_output_policy_accepts_and_serializes_none() -> None:
    output = OutputPolicy.from_dict({"subtitles_mode": "none"}, "$.output")

    assert output.subtitles_mode == "none"
    assert output.to_dict()["subtitles_mode"] == "none"


def test_json_schema_accepts_none() -> None:
    schema_path = (
        Path(__file__).parents[2]
        / "src"
        / "lfo"
        / "contracts"
        / "schemas"
        / "video-execution-v1.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    modes = schema["definitions"]["OutputPolicy"]["properties"]["subtitles_mode"]["enum"]
    assert "none" in modes

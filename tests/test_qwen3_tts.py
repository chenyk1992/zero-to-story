"""Skill helpers operate only on temporary audio; no Comfy or model execution."""

from __future__ import annotations

import array
import copy
import importlib.util
import json
import math
import shutil
import sys
import wave
from itertools import pairwise
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1] / ".agents/skills/qwen3-tts"
spec = importlib.util.spec_from_file_location("qwen_audio_tools", SKILL / "scripts/audio_tools.py")
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


@pytest.fixture
def tone(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg and ffprobe needed for deterministic media integration")
    path = tmp_path / "raw.wav"
    samples = array.array(
        "h", [int(12000 * math.sin(2 * math.pi * 440 * i / 24000)) for i in range(72000)]
    )
    if sys.byteorder != "little":
        samples.byteswap()
    with wave.open(str(path), "wb") as stream:
        stream.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        stream.writeframes(samples.tobytes())
    return path


def draft(name="eric-smoke.json"):
    return audio.read_json(SKILL / "assets" / name)


def clone(tone):
    value = draft("voice-clone.json")
    value["reference"].update(
        path=str(tone),
        source="synthetic-test-signal",
        authorization="test fixture only",
        listening_status="ACCEPT",
        transcript_verified=True,
    )
    value["inputs"]["ref_text"] = "Test transcript fixture, not speech evidence."
    return value


def schema_for(value):
    fields = {}
    for key, value_ in value["inputs"].items():
        kind = (
            "BOOLEAN"
            if isinstance(value_, bool)
            else "INT"
            if isinstance(value_, int)
            else "FLOAT"
            if isinstance(value_, float)
            else "STRING"
        )
        fields[key] = [kind]
    fields["model_choice"] = [["1.7B"]]
    fields["language"] = [audio.LANGUAGES]
    fields["ref_audio"] = ["AUDIO"]
    return {
        value["node_class"]: {"input": {"optional": fields}, "output": ["AUDIO"]},
        "SaveAudio": {
            "input": {"required": {"audio": ["AUDIO"], "filename_prefix": ["STRING"]}},
            "output": [],
        },
        "LoadAudio": {"input": {"required": {"audio": [["uploaded.wav"]]}}, "output": ["AUDIO"]},
    }


def raw_receipt(tone, tmp_path, name="eric-smoke.json"):
    receipt = tmp_path / "raw.json"
    audio.register(SKILL / "assets" / name, tone, "test-only-synthetic-tone", receipt)
    return receipt


@pytest.mark.parametrize(
    "name,mode", [("eric-smoke.json", "custom"), ("voice-design.json", "design")]
)
def test_mode_drafts_preserve_text_and_exclude_postprocessing(name, mode, tmp_path):
    value = draft(name)
    assert audio.validate(value, tmp_path)["mode"] == mode
    graph = audio.workflow(value, tmp_path, schema_for(value))
    assert graph["1"]["inputs"]["text"] == value["inputs"]["text"]
    assert "postprocess" not in graph["1"]["inputs"]


@pytest.mark.parametrize("speaker", audio.SPEAKERS)
def test_presets(speaker, tmp_path):
    value = draft()
    value["inputs"]["speaker"] = speaker
    assert audio.validate(value, tmp_path)["mode"] == "custom"


@pytest.mark.parametrize("language", audio.LANGUAGES)
def test_languages(language, tmp_path):
    value = draft()
    value["inputs"]["language"] = language
    assert audio.validate(value, tmp_path)["draft_valid"]


@pytest.mark.parametrize("key,value", [("tempo", 1.2), ("speaker", "Eric"), ("instruct", "angry")])
def test_clone_rejects_other_mode_parameters(key, value, tone, tmp_path):
    config = clone(tone)
    config["inputs"][key] = value
    with pytest.raises(ValueError, match="Unsupported"):
        audio.validate(config, tmp_path)


def test_design_requires_description_and_matching_model(tmp_path):
    config = draft("voice-design.json")
    config["inputs"]["instruct"] = ""
    with pytest.raises(ValueError, match="instruct"):
        audio.validate(config, tmp_path)
    config = draft("voice-design.json")
    config["model"] = draft()["model"]
    with pytest.raises(ValueError, match="Model and node"):
        audio.validate(config, tmp_path)


def test_reference_transcript_authorization_and_listening(tone, tmp_path):
    value = clone(tone)
    for key, empty in [
        ("authorization", ""),
        ("source", ""),
        ("transcript_verified", False),
        ("listening_status", "INCONCLUSIVE"),
    ]:
        broken = copy.deepcopy(value)
        broken["reference"][key] = empty
        with pytest.raises(ValueError):
            audio.validate(broken, tmp_path)
    value["inputs"]["ref_text"] = ""
    with pytest.raises(ValueError, match="ref_text"):
        audio.validate(value, tmp_path)
    value["inputs"]["x_vector_only"] = True
    assert audio.validate(value, tmp_path)["reference"]["sample_rate"] == 24000


def test_reference_workflow_requires_uploaded_enum_and_audio_type(tone, tmp_path):
    value = clone(tone)
    schema = schema_for(value)
    graph = audio.workflow(value, tmp_path, schema, "uploaded.wav")
    assert graph["1"]["inputs"]["ref_audio"] == ["3", 0]
    assert "text" not in graph["1"]["inputs"]
    assert graph["1"]["inputs"]["target_text"] == value["inputs"]["target_text"]
    with pytest.raises(ValueError, match="enum mismatch"):
        audio.workflow(value, tmp_path, schema, "not-uploaded.wav")
    schema["LoadAudio"]["output"] = ["IMAGE"]
    with pytest.raises(ValueError, match="connection"):
        audio.workflow(value, tmp_path, schema, "uploaded.wav")


def test_schema_missing_field_enum_required_and_output(tmp_path):
    value = draft()
    schema = schema_for(value)
    schema[value["node_class"]]["input"]["optional"].pop("language")
    with pytest.raises(ValueError, match="not advertised"):
        audio.workflow(value, tmp_path, schema)
    schema = schema_for(value)
    schema[value["node_class"]]["input"]["required"] = {"new_required": ["STRING"]}
    with pytest.raises(ValueError, match="Missing required"):
        audio.workflow(value, tmp_path, schema)
    schema = schema_for(value)
    schema[value["node_class"]]["output"] = ["VIDEO"]
    with pytest.raises(ValueError, match="AUDIO"):
        audio.workflow(value, tmp_path, schema)


@pytest.mark.parametrize("tempo", [0, -1, True, float("nan"), float("inf"), 2.1])
def test_bad_tempo_rejected(tempo, tmp_path):
    value = draft()
    value["postprocess"]["tempo"] = tempo
    with pytest.raises(ValueError, match="tempo"):
        audio.validate(value, tmp_path)


@pytest.mark.parametrize("tempo", [None, 1.0, 1.5])
def test_real_ffmpeg_delivery_duration_pitch_and_preservation(tone, tmp_path, tempo):
    original = tone.read_bytes()
    receipt = raw_receipt(tone, tmp_path)
    output = tmp_path / "delivery.flac"
    result = audio.deliver(receipt, output, tempo)
    factor = 1.2 if tempo is None else tempo
    assert result["tempo"] == factor
    assert result["delivery"]["duration_seconds"] == pytest.approx(3 / factor, abs=0.08)
    assert result["delivery"]["sample_rate"] == 24000
    assert result["delivery"]["channels"] == 1
    assert result["listening_status"] == "INCONCLUSIVE"
    assert tone.read_bytes() == original
    # Count positive zero crossings of the actual decoded derivative: pitch remains 440 Hz.
    import subprocess

    pcm = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(output), "-f", "s16le", "-"],
        capture_output=True,
        check=True,
    ).stdout
    samples = array.array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    crossings = sum(a <= 0 < b for a, b in pairwise(samples))
    assert crossings / (len(samples) / 24000) == pytest.approx(440, abs=2)
    with pytest.raises(ValueError, match="unused"):
        audio.deliver(receipt, output)
    with pytest.raises(ValueError, match="not a derivative"):
        audio.deliver(output.with_suffix(".flac.json"), tmp_path / "twice.flac")
    with pytest.raises(ValueError, match="cannot be registered"):
        audio.register(
            SKILL / "assets/eric-smoke.json", output, "not-raw", tmp_path / "false-raw.json"
        )


def test_tampered_raw_refused(tone, tmp_path):
    receipt = raw_receipt(tone, tmp_path)
    with tone.open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="changed"):
        audio.deliver(receipt, tmp_path / "delivery.flac")


def test_design_profile_to_clone_draft_uses_actual_delivery(tone, tmp_path):
    receipt = raw_receipt(tone, tmp_path, "voice-design.json")
    result = audio.deliver(receipt, tmp_path / "delivery.flac")
    manifest = tmp_path / "delivery.flac.json"
    pending = tmp_path / "pending.json"
    audio.profile(
        manifest, "test character", "fixture only", "synthetic test signal", False, pending
    )
    with pytest.raises(ValueError, match="listening"):
        audio.clone_draft(pending, "new text", "English", tmp_path / "blocked.json")
    accepted = tmp_path / "accepted.json"
    audio.profile(
        manifest, "test character", "fixture only", "synthetic test signal", True, accepted
    )
    config = audio.clone_draft(accepted, "new text", "English", tmp_path / "clone.json")
    assert config["reference"]["path"] == result["delivery"]["path"]
    assert config["reference"]["sha256"] == result["delivery"]["sha256"]
    assert config["inputs"]["target_text"] == "new text"
    assert config["inputs"]["ref_text"] == "fixture only"
    assert config["model"].endswith("-Base")
    assert audio.read_json(accepted)["embedding_cached"] is False
    # This checks deterministic config plumbing with a tone, not speech/clone quality.


def test_invalid_audio_and_no_overwrite(tmp_path):
    path = tmp_path / "bad.wav"
    path.write_text("not audio")
    import subprocess

    with pytest.raises(subprocess.CalledProcessError):
        audio.probe(path)
    output = tmp_path / "record.json"
    output.write_text("{}")
    with pytest.raises(FileExistsError):
        audio.write_json(output, {"changed": True})
    assert json.loads(output.read_text()) == {}


def test_reference_hash_mismatch(tone, tmp_path):
    value = clone(tone)
    value["reference"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="hash mismatch"):
        audio.validate(value, tmp_path)


def test_empty_clone_template_is_not_ready(tmp_path):
    with pytest.raises(ValueError, match="authorization"):
        audio.validate(draft("voice-clone.json"), tmp_path)


def test_preflight_modes_independent_and_empty_schema_fails(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(SKILL / "scripts"))
    preflight_spec = importlib.util.spec_from_file_location(
        "qwen_preflight", SKILL / "scripts/preflight.py"
    )
    preflight = importlib.util.module_from_spec(preflight_spec)
    preflight_spec.loader.exec_module(preflight)
    value = draft()
    schema = schema_for(value)
    assert preflight.inspect_mode("custom", schema)["schema_ready"] is True
    assert preflight.inspect_mode("design", schema)["schema_ready"] is False
    assert preflight.inspect_mode("clone", {})["schema_ready"] is False
    model_root = tmp_path / "models"
    (model_root / "empty-model").mkdir(parents=True)
    assert preflight.model_clues([model_root], "absent-model") == []
    assert preflight.model_clues([model_root], "empty-model")[0]["weight_files"] == []

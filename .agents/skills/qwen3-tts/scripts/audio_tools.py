"""Prepare Qwen TTS drafts and deterministic audio derivatives; never submit generation."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

MODES = {
    "custom": ("FB_Qwen3TTSCustomVoice", "CustomVoice"),
    "design": ("FB_Qwen3TTSVoiceDesign", "VoiceDesign"),
    "clone": ("FB_Qwen3TTSVoiceClone", "Base"),
}
SPEAKERS = ["Aiden", "Dylan", "Eric", "Ono_anna", "Ryan", "Serena", "Sohee", "Uncle_fu", "Vivian"]
LANGUAGES = [
    "Auto",
    "Chinese",
    "English",
    "Japanese",
    "Korean",
    "French",
    "German",
    "Spanish",
    "Portuguese",
    "Russian",
    "Italian",
]
COMMON = {
    "model_choice",
    "device",
    "precision",
    "language",
    "seed",
    "max_new_tokens",
    "top_p",
    "top_k",
    "temperature",
    "repetition_penalty",
    "attention",
    "unload_model_after_generate",
}


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def write_json(path: Path, value: dict) -> None:
    # Exclusive creation: never overwrite a user's draft or previous receipt.
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def nonempty(value, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be nonempty text")
    return value


def tempo_value(value) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0.5 <= value <= 2.0
    ):
        raise ValueError("tempo must be finite and between 0.5 and 2.0")
    return float(value)


def run(args: list[str]) -> str:
    result = subprocess.run(
        args, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    return result.stdout


def probe(path: Path) -> dict:
    path = path.resolve(strict=True)
    data = json.loads(
        run(
            [
                os.environ.get("LFO_FFPROBE", "ffprobe"),
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ]
        )
    )
    streams = data.get("streams", [])
    audio = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if len(audio) != 1 or any(stream.get("codec_type") == "video" for stream in streams):
        raise ValueError(
            "Require one audio stream and no video; extract an explicit reference first"
        )
    stream = audio[0]
    duration = float(stream.get("duration") or data.get("format", {}).get("duration", 0))
    rate, channels = int(stream.get("sample_rate", 0)), int(stream.get("channels", 0))
    if not math.isfinite(duration) or duration <= 0 or rate <= 0 or channels <= 0:
        raise ValueError("Invalid audio duration, rate or channels")
    # Decode the whole file, not only the container headers.
    run(
        [
            os.environ.get("LFO_FFMPEG", "ffmpeg"),
            "-hide_banner",
            "-loglevel",
            "error",
            "-xerror",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-f",
            "null",
            "-",
        ]
    )
    tags = {key.lower(): value for key, value in data.get("format", {}).get("tags", {}).items()}
    tags.update({key.lower(): value for key, value in stream.get("tags", {}).items()})
    return {
        "path": str(path),
        "sha256": sha256(path),
        "duration_seconds": duration,
        "sample_rate": rate,
        "channels": channels,
        "tags": tags,
    }


def verified_audio(record: dict) -> dict:
    actual = probe(Path(record["path"]))
    if actual["sha256"] != record["sha256"]:
        raise ValueError("Audio changed since recorded; do not reuse the old receipt")
    return actual


def mode_of(draft: dict) -> str:
    matches = [
        mode
        for mode, (node, family) in MODES.items()
        if draft.get("node_class") == node
        and draft.get("model") == f"Qwen/Qwen3-TTS-12Hz-1.7B-{family}"
    ]
    if len(matches) != 1:
        raise ValueError("Model and node_class must match a supported 1.7B mode")
    return matches[0]


def validate(draft: dict, base: Path, *, check_reference: bool = True) -> dict:
    mode = mode_of(draft)
    inputs = draft["inputs"]
    if not isinstance(inputs, dict):
        raise ValueError("inputs must be an object")
    allowed = COMMON | (
        {"text", "speaker", "instruct"}
        if mode == "custom"
        else {"text", "instruct"}
        if mode == "design"
        else {"target_text", "ref_text", "x_vector_only"}
    )
    if extra := set(inputs) - allowed:
        raise ValueError(f"Unsupported {mode} inputs: {sorted(extra)}")
    nonempty(inputs.get("target_text" if mode == "clone" else "text"), "text")
    for key, choices in {
        "model_choice": ["1.7B"],
        "device": ["auto", "cuda", "xpu", "mps", "cpu"],
        "precision": ["bf16", "fp32"],
        "language": LANGUAGES,
        "attention": ["auto", "sdpa", "eager", "flash_attn", "sage_attn"],
    }.items():
        if inputs.get(key) not in choices:
            raise ValueError(f"Invalid {key}: {inputs.get(key)}")
    if mode == "custom" and inputs.get("speaker") not in SPEAKERS:
        raise ValueError("Invalid speaker; use the Comfy enum spelling")
    if "instruct" in inputs and not isinstance(inputs["instruct"], str):
        raise ValueError("instruct must be text")
    if mode == "design":
        nonempty(inputs.get("instruct"), "VoiceDesign instruct")
    for key, low, high, integer in [
        ("seed", 0, 2**64 - 1, True),
        ("max_new_tokens", 512, 4096, True),
        ("top_p", 0, 1, False),
        ("top_k", 0, 100, True),
        ("temperature", 0.1, 2, False),
        ("repetition_penalty", 1, 2, False),
    ]:
        if key in inputs:
            value = inputs[key]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not low <= value <= high
                or (integer and not isinstance(value, int))
            ):
                raise ValueError(f"Invalid {key}")
    if "unload_model_after_generate" in inputs and not isinstance(
        inputs["unload_model_after_generate"], bool
    ):
        raise ValueError("unload_model_after_generate must be boolean")
    post = draft.get("postprocess", {})
    tempo_value(post.get("tempo", 1.2))
    for key, expected in {
        "backend": "ffmpeg",
        "preserve_pitch": True,
        "output_format": "flac",
        "preserve_original": True,
    }.items():
        if post.get(key, expected) != expected:
            raise ValueError(f"Unsupported postprocess {key}")
    result = {"mode": mode, "draft_valid": True, "generation_verified": False}
    if mode == "clone":
        xvec = inputs.get("x_vector_only", False)
        if not isinstance(xvec, bool):
            raise ValueError("x_vector_only must be boolean")
        reference = draft.get("reference", {})
        if not isinstance(reference, dict):
            raise ValueError("reference must be an object")
        nonempty(reference.get("authorization"), "reference.authorization")
        nonempty(reference.get("source"), "reference.source")
        nonempty(reference.get("path"), "reference.path")
        if reference.get("listening_status") != "ACCEPT":
            raise ValueError(
                "Reference listening is pending; do not infer ACCEPT from text or metadata"
            )
        if not xvec:
            nonempty(inputs.get("ref_text"), "ref_text")
            if reference.get("transcript_verified") is not True:
                raise ValueError("Reference transcript must be verified against the audio")
        if check_reference:
            path = (base / reference["path"]).resolve()
            media = probe(path)
            if reference.get("sha256") and reference["sha256"] != media["sha256"]:
                raise ValueError("Reference hash mismatch")
            result["reference"] = media
    return result


def validate_schema(workflow: dict, schema: dict) -> None:
    for node in workflow.values():
        name = node["class_type"]
        if name not in schema:
            raise ValueError(f"Node not advertised: {name}")
        node_schema = schema[name]
        groups = node_schema.get("input", {})
        fields = {**groups.get("required", {}), **groups.get("optional", {})}
        if set(groups.get("required", {})) - set(node["inputs"]):
            raise ValueError(f"Missing required inputs for {name}")
        for key, value in node["inputs"].items():
            if key not in fields:
                raise ValueError(f"{name}.{key} not advertised")
            kind = fields[key][0]
            if (
                isinstance(value, list)
                and len(value) == 2
                and isinstance(value[0], str)
                and isinstance(value[1], int)
            ):
                source = workflow.get(value[0])
                outputs = schema.get(source["class_type"], {}).get("output", []) if source else []
                if value[1] < 0 or value[1] >= len(outputs) or outputs[value[1]] != kind:
                    raise ValueError(f"Invalid connection for {name}.{key}")
            elif isinstance(kind, list) and value not in kind:
                raise ValueError(f"{name}.{key} enum mismatch")
            elif isinstance(kind, str):
                valid_type = {
                    "STRING": isinstance(value, str),
                    "BOOLEAN": isinstance(value, bool),
                    "INT": isinstance(value, int) and not isinstance(value, bool),
                    "FLOAT": isinstance(value, (int, float)) and not isinstance(value, bool),
                }
                if not valid_type.get(kind, False):
                    raise ValueError(f"{name}.{key} type mismatch")
                limits = fields[key][1] if len(fields[key]) > 1 else {}
                if kind in {"INT", "FLOAT"} and (
                    not math.isfinite(value)
                    or value < limits.get("min", -math.inf)
                    or value > limits.get("max", math.inf)
                ):
                    raise ValueError(f"{name}.{key} outside schema limits")
        outputs = node_schema.get("output", [])
        if name.startswith("FB_Qwen3TTS") and (not outputs or outputs[0] != "AUDIO"):
            raise ValueError(f"{name} must output AUDIO in slot zero")


def workflow(draft: dict, base: Path, schema: dict, uploaded_reference: str | None = None) -> dict:
    mode = validate(draft, base)["mode"]
    inputs = copy.deepcopy(draft["inputs"])
    graph = {
        "1": {"class_type": draft["node_class"], "inputs": inputs},
        "2": {
            "class_type": "SaveAudio",
            "inputs": {"audio": ["1", 0], "filename_prefix": f"audio/qwen3-tts/{mode}"},
        },
    }
    if mode == "clone":
        nonempty(uploaded_reference, "Canvas adapter uploaded reference filename")
        graph["3"] = {"class_type": "LoadAudio", "inputs": {"audio": uploaded_reference}}
        inputs["ref_audio"] = ["3", 0]
    validate_schema(graph, schema)
    return graph


def register(draft_path: Path, raw_path: Path, request_id: str, output: Path) -> dict:
    draft = read_json(draft_path)
    validate(draft, draft_path.parent)
    nonempty(request_id, "source request ID")
    media = probe(raw_path)
    if any(key.startswith("lfo_tts_") for key in media["tags"]):
        raise ValueError("Delivery audio cannot be registered as a new raw synthesis")
    record = {
        "kind": "qwen-tts-raw.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "request_id": request_id,
        "config": draft,
        "raw": media,
        "listening_status": "INCONCLUSIVE",
    }
    write_json(output, record)
    return record


def deliver(receipt_path: Path, output: Path, tempo: float | None = None) -> dict:
    receipt = read_json(receipt_path)
    if receipt.get("kind") != "qwen-tts-raw.v1":
        raise ValueError("Require original synthesis receipt, not a derivative")
    raw = verified_audio(receipt["raw"])
    if any(key.startswith("lfo_tts_") for key in raw["tags"]):
        raise ValueError("Raw audio already carries delivery processing metadata")
    value = tempo_value(
        tempo if tempo is not None else receipt["config"].get("postprocess", {}).get("tempo", 1.2)
    )
    output = output.resolve()
    manifest = output.with_suffix(output.suffix + ".json")
    if (
        output.suffix.lower() != ".flac"
        or output == Path(raw["path"])
        or output.exists()
        or manifest.exists()
    ):
        raise ValueError("Choose a new .flac output and unused sidecar path")
    # -n and an exclusive manifest ensure repeated calls never overwrite accepted audio.
    run(
        [
            os.environ.get("LFO_FFMPEG", "ffmpeg"),
            "-hide_banner",
            "-loglevel",
            "error",
            "-n",
            "-i",
            raw["path"],
            "-map",
            "0:a:0",
            "-af",
            f"atempo={value:g}",
            "-c:a",
            "flac",
            "-metadata",
            f"LFO_TTS_TEMPO={value:g}",
            "-metadata",
            f"LFO_TTS_RAW_SHA256={raw['sha256']}",
            str(output),
        ]
    )
    media = probe(output)
    if media["sample_rate"] != raw["sample_rate"] or media["channels"] != raw["channels"]:
        raise ValueError("Unexpected rate/channel change; inspect output, do not reuse")
    expected = raw["duration_seconds"] / value
    if abs(media["duration_seconds"] - expected) > max(0.15, expected * 0.03):
        raise ValueError("Unexpected atempo duration; inspect output, do not reuse")
    result = {
        "kind": "qwen-tts-delivery.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "request_id": receipt["request_id"],
        "config": receipt["config"],
        "raw": raw,
        "delivery": media,
        "tempo": value,
        "processing_passes": 1,
        "listening_status": "INCONCLUSIVE",
    }
    write_json(manifest, result)
    return result


def profile(
    manifest_path: Path,
    name: str,
    transcript: str,
    authorization: str,
    accepted: bool,
    output: Path,
) -> dict:
    manifest = read_json(manifest_path)
    if manifest.get("kind") != "qwen-tts-delivery.v1":
        raise ValueError("Use the actual delivery manifest")
    nonempty(name, "voice name")
    nonempty(authorization, "authorization")
    nonempty(transcript, "reference transcript")
    media = verified_audio(manifest["delivery"])
    result = {
        "kind": "qwen-tts-voice-profile.v1",
        "name": name,
        "reference": {
            **media,
            "source": manifest["request_id"],
            "authorization": authorization,
            "transcript_verified": accepted,
            "listening_status": "ACCEPT" if accepted else "INCONCLUSIVE",
        },
        "ref_text": transcript,
        "source_config": manifest["config"],
        "reference_tempo": manifest["tempo"],
        "embedding_cached": False,
    }
    write_json(output, result)
    return result


def clone_draft(profile_path: Path, text: str, language: str, output: Path) -> dict:
    voice = read_json(profile_path)
    if voice.get("kind") != "qwen-tts-voice-profile.v1":
        raise ValueError("Expected voice profile")
    asset = Path(__file__).resolve().parents[1] / "assets" / "voice-clone.json"
    draft = read_json(asset)
    draft["reference"] = voice["reference"]
    draft["inputs"].update(target_text=text, language=language, ref_text=voice["ref_text"])
    validate(draft, profile_path.parent)
    write_json(output, draft)
    return draft


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "workflow"):
        item = sub.add_parser(command)
        item.add_argument("config", type=Path)
        if command == "workflow":
            item.add_argument(
                "--schema",
                type=Path,
                required=True,
                help="Fresh /object_info JSON, not preflight report",
            )
            item.add_argument("--uploaded-reference")
            item.add_argument("--output", type=Path, required=True)
    item = sub.add_parser("probe")
    item.add_argument("audio", type=Path)
    item = sub.add_parser("register")
    item.add_argument("config", type=Path)
    item.add_argument("audio", type=Path)
    item.add_argument("--request-id", required=True)
    item.add_argument("--output", type=Path, required=True)
    item = sub.add_parser("deliver")
    item.add_argument("receipt", type=Path)
    item.add_argument("--output", type=Path, required=True)
    item.add_argument("--tempo", type=float)
    item = sub.add_parser("profile")
    item.add_argument("manifest", type=Path)
    item.add_argument("--name", required=True)
    item.add_argument("--transcript", required=True)
    item.add_argument("--authorization", required=True)
    item.add_argument(
        "--listened-and-verified",
        action="store_true",
        help="Only after actual listening and transcript verification",
    )
    item.add_argument("--output", type=Path, required=True)
    item = sub.add_parser("clone-draft")
    item.add_argument("profile", type=Path)
    item.add_argument("--text", required=True)
    item.add_argument("--language", default="Chinese", choices=LANGUAGES)
    item.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            result = validate(read_json(args.config), args.config.parent)
        elif args.command == "workflow":
            result = workflow(
                read_json(args.config),
                args.config.parent,
                read_json(args.schema),
                args.uploaded_reference,
            )
            write_json(args.output, result)
        elif args.command == "probe":
            result = probe(args.audio)
        elif args.command == "register":
            result = register(args.config, args.audio, args.request_id, args.output)
        elif args.command == "deliver":
            result = deliver(args.receipt, args.output, args.tempo)
        elif args.command == "profile":
            result = profile(
                args.manifest,
                args.name,
                args.transcript,
                args.authorization,
                args.listened_and_verified,
                args.output,
            )
        else:
            result = clone_draft(args.profile, args.text, args.language, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(json.dumps({"error": str(error), "generation_submitted": False}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

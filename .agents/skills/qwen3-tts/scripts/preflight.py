"""Read-only Comfy schemas and local model clues; never submits or downloads."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.request import urlopen

from audio_tools import MODES, validate_schema


def model_clues(roots: list[Path], name: str) -> list[dict]:
    result = []
    for root in roots:
        for path in (root / name, root / "Qwen" / name):
            if path.is_dir():
                weights = [item for item in path.glob("*.safetensors") if item.is_file()]
                result.append(
                    {
                        "path": str(path),
                        "config_present": (path / "config.json").is_file(),
                        "weight_files": [
                            {"name": item.name, "bytes": item.stat().st_size} for item in weights
                        ],
                    }
                )
    return result


def inspect_mode(mode: str, schema: dict) -> dict:
    node, family = MODES[mode]
    inputs = {
        "model_choice": "1.7B",
        "device": "cuda",
        "precision": "bf16",
        "language": "Chinese",
        "attention": "sdpa",
    }
    if mode == "custom":
        inputs.update(text="你好。", speaker="Eric", instruct="")
    elif mode == "design":
        inputs.update(text="你好。", instruct="温暖清楚的成年女声。")
    else:
        inputs.update(target_text="你好。", ref_text="参考语句。", x_vector_only=False)
    graph = {
        "1": {"class_type": node, "inputs": inputs},
        "2": {
            "class_type": "SaveAudio",
            "inputs": {"audio": ["1", 0], "filename_prefix": "audio/qwen3-tts/preflight"},
        },
    }
    issues = []
    if mode == "clone":
        load = schema.get("LoadAudio", {})
        groups = load.get("input", {})
        fields = {**groups.get("required", {}), **groups.get("optional", {})}
        field = fields.get("audio", [None])[0]
        if "AUDIO" not in load.get("output", []) or field is None:
            issues.append("LoadAudio audio input/AUDIO output unavailable")
        # No upload is performed. Empty input-file choices do not mean model incompatibility.
        schema = dict(schema)
        schema["__reference_probe__"] = {"input": {"required": {}}, "output": ["AUDIO"]}
        graph["3"] = {"class_type": "__reference_probe__", "inputs": {}}
        inputs["ref_audio"] = ["3", 0]
    try:
        validate_schema(graph, schema)
    except (ValueError, KeyError, TypeError, IndexError) as error:
        issues.append(str(error))
    return {
        "model": f"Qwen/Qwen3-TTS-12Hz-1.7B-{family}",
        "node_class": node,
        "schema_ready": not issues,
        "generation_verified": False,
        "issues": issues,
        "node_schema": schema.get(node),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", default=os.environ.get("LFO_COMFY_BASE_URL", "http://127.0.0.1:8188")
    )
    parser.add_argument("--comfy-root", type=Path)
    parser.add_argument("--model-root", type=Path, action="append", default=[])
    parser.add_argument("--mode", choices=["all", *MODES], default="all")
    parser.add_argument(
        "--schema-output",
        type=Path,
        help="Save fresh object_info for workflow validation; refuses overwrite",
    )
    args = parser.parse_args()
    report = {"read_only": True, "generation_verified": False, "canvas_audio_verified": False}
    issues, schema = [], {}
    for endpoint in ("system_stats", "object_info"):
        try:
            with urlopen(args.base_url.rstrip("/") + "/" + endpoint, timeout=5) as response:
                data = json.load(response)
            if not isinstance(data, dict):
                raise ValueError("Expected object response")
            if endpoint == "system_stats":
                report["runtime"] = {
                    key: data.get("system", {}).get(key)
                    for key in ("python_version", "pytorch_version", "comfyui_version")
                }
                report["devices"] = data.get("devices", [])
            else:
                schema = data
                if args.schema_output:
                    with args.schema_output.open("x", encoding="utf-8") as stream:
                        json.dump(schema, stream, ensure_ascii=False, indent=2)
        except (OSError, ValueError) as error:
            issues.append(f"{endpoint}: {error}")
    modes = list(MODES) if args.mode == "all" else [args.mode]
    report["modes"] = {mode: inspect_mode(mode, schema) for mode in modes}
    roots = list(args.model_root)
    if args.comfy_root:
        report["plugin_directory_exists"] = (
            args.comfy_root / "custom_nodes" / "ComfyUI-Qwen-TTS"
        ).is_dir()
        roots.append(args.comfy_root / "models" / "qwen-tts")
    names = [f"Qwen3-TTS-12Hz-1.7B-{MODES[mode][1]}" for mode in modes] + [
        "Qwen3-TTS-Tokenizer-12Hz"
    ]
    report["model_directory_clues"] = {name: model_clues(roots, name) for name in names}
    report["model_note"] = (
        "File presence is not integrity, loading or generation verification. Custom roots may be elsewhere. No model is loaded."
    )
    report["issues"] = issues
    report["node_schema_ready"] = not issues and all(
        item["schema_ready"] for item in report["modes"].values()
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["node_schema_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

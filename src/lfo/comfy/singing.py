"""Canvas-only vocal separation via local Comfy MCP."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lfo.canvas.input_contract import validate_input_contract
from lfo.comfy import transport
from lfo.comfy.qwen_tts import upload_reference
from lfo.media._ffmpeg import probe_audio

SKILL_ROOT = Path(__file__).resolve().parents[3] / ".agents/skills/comfy-singing-executor"


def prepare_workflow(snapshot: dict[str, Any], tokens: list[str]) -> tuple[dict, dict]:
    if (snapshot.get("node_type"), snapshot.get("provider")) != ("audio", "comfy-singing"):
        raise ValueError("Expected a Canvas Comfy singing audio request")
    mode = snapshot.get("mode")
    if mode != "separate":
        raise ValueError("Singing mode has been retired; only vocal separation is available")
    if snapshot.get("model") != "melband-seedvc-44k":
        raise ValueError("Unsupported separator model")
    capability = json.loads((SKILL_ROOT / "capability.json").read_text(encoding="utf-8"))
    validate_input_contract(snapshot, capability)
    refs = snapshot.get("inputs", {}).get("reference_audios", [])
    if len(refs) != 1 or len(tokens) != 1:
        raise ValueError("Separation needs one source audio")
    if any(r.get("kind") != "audio" for r in refs):
        raise ValueError("All references must be audio")
    if not snapshot.get("request_id") or not snapshot.get("prompt", "").strip():
        raise ValueError("Missing frozen request identity or description")
    p = snapshot["parameters"]
    prefix = hashlib.sha256(snapshot["request_id"].encode()).hexdigest()[:24]
    workflow = {"1": {"class_type": "LoadAudio", "inputs": {"audio": tokens[0]}}}
    if mode == "separate":
        workflow.update({
            "2": {"class_type": "MelBandRoFormerModelLoader", "inputs": {
                "model_name": p.get("separator_model", "MelBandRoformer_fp16.safetensors")}},
            "3": {"class_type": "MelBandRoFormerSampler", "inputs": {
                "model": ["2", 0], "audio": ["1", 0]}},
            "4": {"class_type": "SaveAudio", "inputs": {
                "audio": ["3", 0], "filename_prefix": f"canvas/singing/{prefix}/vocals"}},
            "5": {"class_type": "SaveAudio", "inputs": {
                "audio": ["3", 1], "filename_prefix": f"canvas/singing/{prefix}/instruments"}},
        })
    return workflow, {"mode": mode, "request_id": snapshot["request_id"],
                      "model": snapshot["model"], "parameters": p, "sources": refs}


def materialize_audio(result, output_dir: Path, normalized: dict) -> list[dict]:
    if normalized["mode"] != "separate":
        raise ValueError("Only separation outputs can be collected")
    names = ["vocals", "instruments"]
    refs = [r for r in result.outputs
            if r.file_type in {"output", "absolute"} and Path(r.filename).suffix.lower() == ".flac"]
    if len(refs) != len(names):
        raise ValueError("Unexpected number of audio outputs")
    outputs = []
    for name in names:
        output_node = {"vocals": "4", "instruments": "5"}[name]
        matches = [r for r in refs if r.node_id == output_node]
        if not matches:
            # Preserve roles even when the official downloader flattens filenames.
            from urllib.parse import parse_qs, urlparse

            def source_name(ref):
                url = ref.source_url or ""
                parsed = urlparse(url)
                return Path(parse_qs(parsed.query).get("filename", [url])[0]).name

            matches = [r for r in refs if source_name(r).startswith(name + "_")]
        if not matches and len(names) == len(refs) == 1:
            matches = refs
        if len(matches) != 1:
            raise ValueError(f"Missing unambiguous {name} output")
        source = Path(matches[0].filename).resolve(strict=True)
        metadata = probe_audio(source)
        if metadata["codec"] != "flac" or metadata["duration_ms"] <= 0:
            raise ValueError("Invalid FLAC output")
        expected = probe_audio(Path(normalized["sources"][0]["path"]))["duration_ms"]
        if abs(metadata["duration_ms"] - expected) > 150:
            raise ValueError("Separated audio timing drift exceeds 150ms")
        target = output_dir / f"{name}.flac"
        if target.exists():
            raise ValueError("Refusing to overwrite an existing output")
        shutil.copyfile(source, target)
        with target.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        outputs.append({"path": str(target.resolve()), "kind": "audio", "name": f"{name}.flac",
                        "metadata": {**metadata, "sha256": digest, "listening_status": "INCONCLUSIVE"}})
    return outputs


def execute_snapshot(snapshot, output_dir: Path, config, *, emit=None) -> dict:
    emit = emit or (lambda e: print(json.dumps(e, ensure_ascii=False), flush=True))
    stage, result = "input_validation", None
    try:
        refs = snapshot.get("inputs", {}).get("reference_audios", [])
        # Validate all semantic fields before opening a provider session.
        prepare_workflow(snapshot, ["preflight.flac"] * len(refs))
        from lfo.comfy.admission import VideoSubmissionGuard

        output_dir.mkdir(parents=True, exist_ok=True)
        with VideoSubmissionGuard(config.base_url, request_id=snapshot["request_id"]) as guard, transport.ready_session(config) as session:
            workflow_path = output_dir / "workflow.json"
            if workflow_path.exists():
                raise ValueError("This request already has a workflow; do not resubmit")
            tokens = [upload_reference(Path(r["path"]), session) for r in refs]
            workflow, normalized = prepare_workflow(snapshot, tokens)
            workflow_path.write_text(json.dumps(workflow, ensure_ascii=False), encoding="utf-8")
            (output_dir / "conditions.json").write_text(json.dumps(normalized, ensure_ascii=False), encoding="utf-8")
            if normalized["mode"] == "separate":
                selected = workflow["2"]["inputs"]["model_name"]
                if selected not in transport.model_files(session, "diffusion_models"):
                    raise ValueError("Separator model is not installed")
            transport.preflight_workflow(workflow, workflow_path, session)
            stage = "submit"
            emit({"stage": stage})
            result = transport.run_workflow(workflow_path, output_dir, config, session, guard=guard, emit=emit)
        stage = "collection"
        emit({"stage": stage, "remote_finished": True, "provider_task_id": result.provider_task_id})
        outputs = materialize_audio(result, output_dir, normalized)
        receipt = {"kind": "singing-delivery.v1", "created_at": datetime.now(UTC).isoformat(),
                   "provider_task_id": result.provider_task_id, "config": normalized, "outputs": outputs}
        (output_dir / "delivery.json").write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8")
        return {"status": "succeeded", "stage": "media_validation", "outputs": outputs,
                "provider_task_id": result.provider_task_id}
    except Exception as exc:
        if not isinstance(exc, transport.ExecutorError):
            exc = transport.ExecutorError(str(exc), status="unknown" if stage == "submit" and result is None else "failed")
        exc.stage = stage
        if result is not None:
            exc.provider_task_id = result.provider_task_id
        raise exc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Internal Canvas singing worker")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        snapshot = json.loads(args.input.read_text(encoding="utf-8-sig"))
        result = execute_snapshot(snapshot, args.output_dir, transport.load_runtime_config())
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc), "status": getattr(exc, "status", "failed"),
                          "stage": getattr(exc, "stage", "input_validation"),
                          "provider_task_id": getattr(exc, "provider_task_id", None)}, ensure_ascii=False), flush=True)
        return 1

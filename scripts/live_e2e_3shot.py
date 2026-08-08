"""Live 3-Shot E2E: T2V → I2V → I2V with continuity.

Validates the full multi-shot pipeline:
- Shot 1: T2V (no first frame)
- Shot 2: I2V (uses Shot 1's end frame)
- Shot 3: I2V (uses Shot 2's end frame)

Each shot goes through: submit → monitor → collect → QC → extract end frame.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lfo.comfy.client import ComfyApiClient
from lfo.comfy.collect import ComfyOutputCollector
from lfo.comfy.monitor import ComfyMonitor
from lfo.core.database import Database
from lfo.services.end_frame_extractor import EndFrameExtractor
from lfo.services.technical_qc_service import QCSpec, TechnicalQCService

# Shot definitions
SHOTS = [
    {
        "shot_id": "shot_001",
        "description": "A lone samurai standing on a cliff edge at sunset, dramatic sky, wide shot, cinematic lighting",
        "workflow": "h3_standard_t2v",
        "prompt_layer": "integrated",
    },
    {
        "shot_id": "shot_002",
        "description": "The samurai slowly draws from the sheath, medium close-up, tension building, golden hour backlight",
        "workflow": "h3_standard_i2v",
        "prompt_layer": "integrated",
    },
    {
        "shot_id": "shot_003",
        "description": "Sweeping action as the samurai strikes, fabric swirling, dynamic camera, slow motion, dust particles",
        "workflow": "h3_standard_i2v",
        "prompt_layer": "integrated",
    },
]

OUTPUT_ROOT = Path("D:/cyuiEnv/output")
PROJECT_ID = "proj-3shot-e2e"


def load_workflow(workflow_name: str) -> dict:
    """Load workflow JSON from fixtures."""
    wf_path = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "workflows" / f"{workflow_name}.json"
    return json.loads(wf_path.read_text(encoding="utf-8"))


def find_latest_output(output_root: Path, shot_id: str) -> Path | None:
    """Find the newest output file matching the shot prefix."""
    # Look for files with pattern video_*.mp4 (ComfyUI default naming)
    candidates = list(output_root.rglob("video_*.mp4"))
    if not candidates:
        return None
    # Return the newest
    return max(candidates, key=lambda p: p.stat().st_mtime)


def run_shot(
    shot: dict,
    shot_index: int,
    first_frame_path: Path | None,
    client: ComfyApiClient,
    monitor: ComfyMonitor,
    db: Database,
    qc_spec: QCSpec,
) -> dict:
    """Run a single shot through the full pipeline.

    Returns:
        dict with shot result, including end_frame_path for next shot.
    """
    shot_id = shot["shot_id"]
    print(f"\n{'='*60}")
    print(f"SHOT {shot_index + 1}/3: {shot_id}")
    print(f"  Workflow: {shot['workflow']}")
    print(f"  First frame: {first_frame_path.name if first_frame_path else 'None (T2V)'}")
    print(f"{'='*60}")

    result = {"shot_id": shot_id, "success": False}

    # 1. Load workflow
    workflow = load_workflow(shot["workflow"])
    print(f"[1/6] Workflow loaded: {shot['workflow']}")

    # 2. Set prompt and first frame
    if shot["workflow"] == "h3_standard_t2v":
        # T2V: set prompt on node 6
        workflow["6"]["inputs"]["prompt"] = shot["description"]
        workflow["12"]["inputs"]["filename_prefix"] = f"video/3shot_{shot_id}"
        print("[2/6] T2V prompt set")
    else:
        # I2V: set prompt on node 8, first frame on node 6
        workflow["8"]["inputs"]["prompt"] = shot["description"]
        workflow["14"]["inputs"]["filename_prefix"] = f"video/3shot_{shot_id}"
        if first_frame_path:
            # Upload first frame to ComfyUI input
            upload_result = client.upload_image(first_frame_path)
            image_name = upload_result["name"]
            workflow["6"]["inputs"]["image"] = image_name
            print(f"[2/6] I2V prompt + first frame uploaded: {image_name}")
        else:
            print("[2/6] I2V prompt set (no first frame — will fail)")

    # 3. Submit to ComfyUI
    submit_result = client.submit_prompt(workflow, client_id=f"lfo-3shot-{shot_id}")
    prompt_id = submit_result["prompt_id"]
    print(f"[3/6] Submitted: prompt_id={prompt_id}")

    # 4. Monitor until done
    print("[4/6] Monitoring execution...")
    start_time = time.time()
    final_status = monitor.poll_until_done(
        prompt_id,
        interval=5.0,
        timeout=1200.0,
        on_tick=lambda s: print(f"      ... {s.get('status', '?')} ({time.time() - start_time:.0f}s)", end="\r"),
    )
    elapsed = time.time() - start_time
    print()
    print(f"      Completed in {elapsed:.0f}s, status: {final_status.get('status')}")

    if not final_status.get("completed"):
        result["error"] = f"Execution failed: {final_status.get('error', 'unknown')}"
        print(f"  ERROR: {result['error']}")
        return result

    # 5. Collect output
    print("[5/6] Collecting output...")
    history = client.get_history(prompt_id)
    entry = history.get(prompt_id, {})
    outputs = entry.get("outputs", {})

    target_file = None
    for node_id, node_output in outputs.items():
        media_list = node_output.get("images", []) or node_output.get("video", [])
        if media_list:
            media_info = media_list[0]
            filename = media_info.get("filename", "")
            subfolder = media_info.get("subfolder", "")
            full_path = OUTPUT_ROOT / subfolder / filename if subfolder else OUTPUT_ROOT / filename
            if full_path.exists():
                target_file = full_path
                break

    # Fallback: newest video file
    if target_file is None:
        candidates = list(OUTPUT_ROOT.rglob("video_*.mp4"))
        if candidates:
            target_file = max(candidates, key=lambda p: p.stat().st_mtime)

    if target_file is None:
        result["error"] = "No output file found"
        print(f"  ERROR: {result['error']}")
        return result

    print(f"      Output: {target_file.name}")
    print(f"      Size: {target_file.stat().st_size / 1024 / 1024:.1f} MB")

    # Validate media
    collector = ComfyOutputCollector(OUTPUT_ROOT)
    media_info = collector.validate_media(target_file)
    print(f"      {media_info.width}x{media_info.height}, {media_info.fps}fps, "
          f"{media_info.duration}s, audio={'yes' if media_info.has_audio else 'no'}")

    # 6. QC
    print("[6/6] Running QC + extracting end frame...")

    # Register task/attempt/asset in DB
    task_id = f"task-{shot_id}"
    attempt_id = f"att-{shot_id}"
    asset_id = f"asset-{shot_id}"

    db.execute(
        """INSERT INTO tasks (task_id, project_id, task_type, status, params_hash, dependency_hash, idempotency_key)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (task_id, PROJECT_ID, "video.h3", "RUNNING", "ph", "dh", f"ik-{shot_id}"),
    )
    db.execute(
        """INSERT INTO attempts (attempt_id, task_id, idempotency_key, status, params, content_hash, dependency_hash, params_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (attempt_id, task_id, f"ik-{shot_id}", "COMPLETED", "{}", "ch", "dh", "ph"),
    )
    db.execute(
        """INSERT INTO assets (asset_id, task_id, attempt_id, asset_type, file_path, metadata, width, height, duration, frame_count)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            asset_id, task_id, attempt_id, "video", str(target_file),
            json.dumps({"codec": "h264", "fps": media_info.fps, "has_audio": media_info.has_audio}),
            media_info.width, media_info.height, media_info.duration, media_info.frames,
        ),
    )

    # QC
    qc_service = TechnicalQCService(db)
    qc_result = qc_service.check_asset(asset_id, qc_spec)
    print(f"      QC: {qc_result.status}")
    for check in qc_result.checks:
        symbol = "PASS" if check.passed else "FAIL"
        print(f"        [{symbol}] {check.name}: expected={check.expected}, actual={check.actual}")

    # End frame extraction
    extractor = EndFrameExtractor(db, output_dir=str(Path(__file__).resolve().parent.parent / "end_frames"))
    frame_result = extractor.extract(asset_id)
    end_frame_path = None
    if frame_result.success:
        end_frame_path = Path(frame_result.file_path)
        print(f"      End frame: {end_frame_path.name}")
    else:
        print(f"      End frame extraction failed: {frame_result.error}")

    result["success"] = True
    result["qc_passed"] = qc_result.passed
    result["output_file"] = str(target_file)
    result["end_frame_path"] = end_frame_path
    result["media_info"] = {
        "width": media_info.width,
        "height": media_info.height,
        "fps": media_info.fps,
        "duration": media_info.duration,
        "audio": media_info.has_audio,
    }

    return result


def main():
    print("=" * 60)
    print("3-Shot Live E2E: T2V → I2V → I2V (with continuity)")
    print("=" * 60)

    # Check ComfyUI
    client = ComfyApiClient("http://127.0.0.1:8188")
    monitor = ComfyMonitor(client)

    stats = client.get_system_stats()
    vram = stats["devices"][0]["vram_free"] / 1024**3
    print(f"ComfyUI ready — VRAM free: {vram:.1f} GB")

    # DB
    db = Database(":memory:")
    db.init_schema()

    # QC Spec per workflow type
    qc_spec_t2v = QCSpec(
        width=864,
        height=480,
        fps=24.0,
        duration_sec=5.0,
        requires_audio=True,
        expected_video_codec="h264",
        duration_tolerance_sec=1.0,
    )
    qc_spec_i2v = QCSpec(
        width=640,
        height=640,
        fps=24.0,
        duration_sec=5.0,
        requires_audio=True,
        expected_video_codec="h264",
        duration_tolerance_sec=1.0,
    )

    # Run shots sequentially
    results = []
    first_frame = None
    total_start = time.time()

    for i, shot in enumerate(SHOTS):
        spec = qc_spec_i2v if shot["workflow"] == "h3_standard_i2v" else qc_spec_t2v
        shot_result = run_shot(shot, i, first_frame, client, monitor, db, spec)
        results.append(shot_result)

        if not shot_result["success"]:
            print(f"\n  SHOT {i+1} FAILED — stopping pipeline")
            break

        # Extract end frame for next shot's first frame
        end_frame = shot_result.get("end_frame_path")
        if end_frame and end_frame.exists():
            first_frame = end_frame
        else:
            print(f"  WARNING: No end frame for shot {i+1}, next shot will be T2V")
            first_frame = None

    total_elapsed = time.time() - total_start

    # Summary
    print(f"\n{'='*60}")
    print("3-SHOT E2E SUMMARY")
    print(f"{'='*60}")
    print(f"  Total time: {total_elapsed / 60:.1f} minutes")
    for r in results:
        status = "OK" if r["success"] else "FAIL"
        shot_id = r["shot_id"]
        qc = "PASS" if r.get("qc_passed") else "FAIL"
        audio = r.get("media_info", {}).get("audio", "?")
        print(f"  {shot_id}: {status} | QC: {qc} | Audio: {audio}")

    all_passed = all(r["success"] for r in results) and all(r.get("qc_passed") for r in results)
    print(f"  Overall: {'PASS' if all_passed else 'FAIL'}")
    print(f"{'='*60}")

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

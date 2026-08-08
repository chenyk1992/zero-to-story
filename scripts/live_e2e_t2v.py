"""Live E2E test: T2V generation → collect → QC → end frame.

Runs the full pipeline against a real ComfyUI instance.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lfo.comfy.client import ComfyApiClient
from lfo.comfy.collect import ComfyOutputCollector
from lfo.comfy.monitor import ComfyMonitor
from lfo.core.database import Database
from lfo.services.end_frame_extractor import EndFrameExtractor
from lfo.services.media_service import MediaService
from lfo.services.technical_qc_service import QCSpec, TechnicalQCService


def main():
    print("=" * 60)
    print("Live E2E: T2V → Collect → QC → EndFrame")
    print("=" * 60)

    # 1. Load workflow
    wf_path = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "workflows" / "h3_standard_t2v.json"
    workflow = json.loads(wf_path.read_text(encoding="utf-8"))
    print(f"[1/7] Workflow loaded: {wf_path.name}")

    # 2. Set prompt
    workflow["6"]["inputs"]["prompt"] = (
        "A serene mountain landscape at sunrise, golden light peaks through clouds, "
        "camera slowly panning left, cinematic, 4K"
    )
    print(f"[2/7] Prompt set: {workflow['6']['inputs']['prompt'][:50]}...")

    # 3. Submit to ComfyUI
    client = ComfyApiClient("http://127.0.0.1:8188")
    monitor = ComfyMonitor(client)

    # Check system stats
    stats = client.get_system_stats()
    vram = stats["devices"][0]["vram_free"] / 1024**3
    print(f"[3/7] ComfyUI ready — VRAM free: {vram:.1f} GB")

    # Submit
    result = client.submit_prompt(workflow, client_id="lfo-e2e-test")
    prompt_id = result["prompt_id"]
    print(f"      Prompt ID: {prompt_id}")

    # 4. Monitor until done
    print("[4/7] Monitoring execution...")
    final_status = monitor.poll_until_done(
        prompt_id,
        interval=5.0,
        timeout=900.0,
        on_tick=lambda s: print(f"      ... status: {s.get('status', '?')}", end="\r"),
    )
    print()
    print(f"      Final status: {final_status.get('status')}")

    if not final_status.get("completed"):
        print("ERROR: Prompt did not complete successfully")
        print(f"  Error: {final_status.get('error')}")
        return False

    # 5. Collect output
    print("[5/7] Collecting output...")
    output_root = Path("D:/cyuiEnv/output")
    collector = ComfyOutputCollector(output_root)

    # Get outputs from history API
    history = client.get_history(prompt_id)
    entry = history.get(prompt_id, {})
    outputs = entry.get("outputs", {})

    # Find the SaveVideo output (node 12) — ComfyUI uses "images" key for video too
    target_file = None
    for node_id, node_output in outputs.items():
        # Check both "images" and "video" keys
        media_list = node_output.get("images", []) or node_output.get("video", [])
        if media_list:
            media_info = media_list[0]
            filename = media_info.get("filename", "")
            subfolder = media_info.get("subfolder", "")
            full_path = output_root / subfolder / filename if subfolder else output_root / filename
            if full_path.exists():
                target_file = full_path
                break

    # Fallback: scan for our specific filename prefix
    if target_file is None:
        candidates = list(output_root.rglob("test_t2v*.mp4"))
        if candidates:
            # Pick the newest
            target_file = max(candidates, key=lambda p: p.stat().st_mtime)

    if target_file is None:
        print("ERROR: No output files found")
        return False

    files = [target_file]
    print(f"      Target: {target_file.name}")

    # Validate
    media_info = collector.validate_media(target_file)
    print(f"      {media_info.width}x{media_info.height}, "
          f"{media_info.fps}fps, {media_info.duration}s, "
          f"audio={'yes' if media_info.has_audio else 'no'}")

    # 6. QC check
    print("[6/7] Running QC...")
    db = Database(":memory:")
    db.init_schema()
    qc_service = TechnicalQCService(db)

    spec = QCSpec(
        width=864,
        height=480,
        fps=24.0,
        duration_sec=5.0,
        requires_audio=True,
        expected_video_codec="h264",
        duration_tolerance_sec=1.0,
    )

    # Create task + attempt records (FK requirement)
    db.execute(
        """INSERT INTO tasks (task_id, project_id, task_type, status, params_hash, dependency_hash, idempotency_key)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("task-live", "proj-live", "video.h3", "RUNNING", "ph", "dh", "ik"),
    )
    db.execute(
        """INSERT INTO attempts (attempt_id, task_id, idempotency_key, status, params, content_hash, dependency_hash, params_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("att-live", "task-live", "ik", "COMPLETED", "{}", "ch", "dh", "ph"),
    )

    # Register the asset in DB (simulating VideoCollectService)
    asset_id = "live-e2e-asset-001"
    db.execute(
        """INSERT INTO assets (asset_id, task_id, attempt_id, asset_type, file_path, metadata, width, height, duration, frame_count)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            asset_id, "task-live", "att-live", "video", str(files[0]),
            json.dumps({"codec": "h264", "fps": 24.0, "has_audio": True}),
            media_info.width, media_info.height, media_info.duration, media_info.frames,
        ),
    )

    qc_result = qc_service.check_asset(asset_id, spec)
    print(f"      QC status: {qc_result.status}")
    for check in qc_result.checks:
        symbol = "PASS" if check.passed else "FAIL"
        print(f"        [{symbol}] {check.name}: expected={check.expected}, actual={check.actual}")

    # 7. Normalize
    print("[7/9] Normalizing...")
    media_service = MediaService(db, output_dir=str(Path(__file__).resolve().parent.parent / "normalized"))
    try:
        normalized = media_service.normalize(asset_id, "standard")
        print(f"      Normalized: {normalized.file_path}")
        print(f"      {normalized.width}x{normalized.height}, {normalized.fps}fps, "
              f"{normalized.duration_sec}s, audio={normalized.audio_codec}")
    except Exception as e:
        print(f"      Normalization failed: {e}")
        normalized = None

    # 8. Selected Clip (extract frames 100-124, last ~1 second)
    selected_clip = None
    if normalized:
        print("[8/9] Creating selected clip (last 24 frames)...")
        try:
            in_frame = max(0, (media_info.frames or 124) - 24)
            out_frame = media_info.frames or 124
            selected_clip = media_service.create_selected_clip(
                asset_id, in_frame, out_frame
            )
            print(f"      Clip: {selected_clip.file_path}")
            print(f"      Frames {in_frame}-{out_frame}, {selected_clip.duration_sec}s")
        except Exception as e:
            print(f"      Selected clip failed: {e}")

    # 9. End frame extraction
    print("[9/9] Extracting end frame...")
    extractor = EndFrameExtractor(db, output_dir=str(Path(__file__).resolve().parent.parent / "end_frames"))
    frame_result = extractor.extract(asset_id)

    if frame_result.success:
        print(f"      Frame extracted: {frame_result.file_path}")
        print(f"      Frame number: {frame_result.frame_number}")
    else:
        print(f"      Frame extraction failed: {frame_result.error}")

    # Summary
    print()
    print("=" * 60)
    print("E2E SUMMARY")
    print(f"  Generation:   {'OK' if final_status.get('completed') else 'FAIL'}")
    print(f"  Collection:   {'OK' if files else 'FAIL'}")
    print(f"  QC:           {qc_result.status}")
    print(f"  Normalize:    {'OK' if normalized else 'FAIL'}")
    print(f"  Selected Clip:{'OK' if selected_clip else 'FAIL'}")
    print(f"  End Frame:    {'OK' if frame_result.success else 'FAIL'}")
    print("=" * 60)

    return qc_result.passed and frame_result.success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

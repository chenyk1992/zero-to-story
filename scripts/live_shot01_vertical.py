"""Live E2E: Single T2V shot for 午夜不接单 (vertical 9:16, ~756P).

Shot 01: 俯拍走廊，暴雨夜，无人。
Workflow: h3_vertical_t2v
Resolution: 432x768 (9:16)
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


def main():
    print("=" * 60)
    print("午夜不接单 — Shot 01 T2V (Vertical 9:16, ~756P)")
    print("=" * 60)

    # 1. Load vertical workflow
    wf_path = Path(__file__).resolve().parent.parent / "src" / "lfo" / "registry" / "h3_vertical_t2v.json"
    workflow = json.loads(wf_path.read_text(encoding="utf-8"))
    print(f"[1/6] Workflow loaded: {wf_path.name}")

    # 2. Set prompt (H3 three-layer format)
    # Shot 01: 俯拍走廊，暴雨夜，湿地面反光，灯管闪烁，无人
    prompt = (
        "Scene: A narrow corridor in an old apartment building at night. "
        "Bird's eye view looking down the middle of the corridor. "
        "Wet floor reflecting dim light in the foreground, "
        "flickering fluorescent tube light in the midground going half-bright, "
        "rain-streaked window in the background with storm outside. "
        "No people. Cold blue-green fluorescent lighting, wet and oppressive atmosphere. "
        "Vertical 9:16 composition.\n"
        "Soundscape: Heavy rain hitting windows, fluorescent tube buzzing and flickering, "
        "dripping water echoing in the corridor, distant thunder rumble.\n"
        "Music: None — pure atmosphere."
    )
    # H3 vertical T2v uses node "6" for prompt (same as standard)
    workflow["6"]["inputs"]["prompt"] = prompt
    workflow["17"]["inputs"]["filename_prefix"] = "video/midnight_ep001_shot01_t2v"
    print(f"[2/6] Prompt set ({len(prompt)} chars)")
    print(f"      Prefix: {workflow['17']['inputs']['filename_prefix']}")

    # 3. Submit to ComfyUI
    client = ComfyApiClient("http://127.0.0.1:8188")
    monitor = ComfyMonitor(client)

    # Check system stats
    try:
        stats = client.get_system_stats()
        vram = stats["devices"][0]["vram_free"] / 1024**3
        print(f"[3/6] ComfyUI ready — VRAM free: {vram:.1f} GB")
    except Exception as e:
        print(f"[3/6] WARNING: Could not get system stats: {e}")
        print("      Make sure ComfyUI is running at http://127.0.0.1:8188")
        return False

    # Submit
    result = client.submit_prompt(workflow, client_id="midnight-shot01")
    prompt_id = result["prompt_id"]
    print(f"      Prompt ID: {prompt_id}")

    # 4. Monitor until done
    print("[4/6] Monitoring execution (timeout: 1200s)...")
    start_time = time.time()
    final_status = monitor.poll_until_done(
        prompt_id,
        interval=5.0,
        timeout=1200.0,
        on_tick=lambda s: print(f"      ... status: {s.get('status', '?')} ({time.time() - start_time:.0f}s)", end="\r"),
    )
    elapsed = time.time() - start_time
    print()
    print(f"      Final status: {final_status.get('status')} ({elapsed:.1f}s)")

    if not final_status.get("completed"):
        print("ERROR: Prompt did not complete successfully")
        print(f"  Error: {final_status.get('error')}")
        return False

    # 5. Collect output
    print("[5/6] Collecting output...")
    output_root = Path("D:/ComfyUI/Comfy-Desktop/ComfyUI/ComfyUI/output")
    collector = ComfyOutputCollector(output_root)

    # Get outputs from history API
    history = client.get_history(prompt_id)
    entry = history.get(prompt_id, {})
    outputs = entry.get("outputs", {})

    # Find the SaveVideo output (node 17)
    target_file = None
    for node_id, node_output in outputs.items():
        media_list = node_output.get("images", []) or node_output.get("video", [])
        if media_list:
            media_info_item = media_list[0]
            filename = media_info_item.get("filename", "")
            subfolder = media_info_item.get("subfolder", "")
            full_path = output_root / subfolder / filename if subfolder else output_root / filename
            if full_path.exists():
                target_file = full_path
                break

    # Fallback: scan for our filename prefix
    if target_file is None:
        candidates = list(output_root.rglob("midnight_ep001_shot01_t2v*.mp4"))
        if candidates:
            target_file = max(candidates, key=lambda p: p.stat().st_mtime)

    if target_file is None:
        print("ERROR: No output files found")
        print(f"  Searched in: {output_root}")
        return False

    print(f"      Output: {target_file}")
    print(f"      Size: {target_file.stat().st_size / 1024 / 1024:.1f} MB")

    # Validate
    media_info = collector.validate_media(target_file)
    print(f"      Resolution: {media_info.width}x{media_info.height}")
    print(f"      FPS: {media_info.fps}, Duration: {media_info.duration}s")
    print(f"      Audio: {'yes' if media_info.has_audio else 'no'}")

    # 6. QC check
    print("[6/6] Running QC...")
    db = Database(":memory:")
    db.init_schema()
    qc_service = TechnicalQCService(db)

    spec = QCSpec(
        width=448,
        height=800,
        fps=24.0,
        duration_sec=5.0,
        requires_audio=True,
        expected_video_codec="h264",
        duration_tolerance_sec=2.0,
    )

    # Create task + attempt records (FK requirement)
    db.execute(
        """INSERT INTO tasks (task_id, project_id, task_type, status, params_hash, dependency_hash, idempotency_key)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("task-shot01", "midnight-ch01", "video.h3", "RUNNING", "ph", "dh", "ik-shot01"),
    )
    db.execute(
        """INSERT INTO attempts (attempt_id, task_id, idempotency_key, status, params, content_hash, dependency_hash, params_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("att-shot01", "task-shot01", "ik-shot01", "COMPLETED", "{}", "ch", "dh", "ph"),
    )

    # Register the asset
    asset_id = "asset-shot01-t2v"
    db.execute(
        """INSERT INTO assets (asset_id, task_id, attempt_id, asset_type, file_path, metadata, width, height, duration, frame_count)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            asset_id, "task-shot01", "att-shot01", "video", str(target_file),
            json.dumps({"codec": "h264", "fps": media_info.fps, "has_audio": media_info.has_audio}),
            media_info.width, media_info.height, media_info.duration, media_info.frames,
        ),
    )

    qc_result = qc_service.check_asset(asset_id, spec)
    print(f"      QC status: {qc_result.status}")
    for check in qc_result.checks:
        symbol = "PASS" if check.passed else "FAIL"
        print(f"        [{symbol}] {check.name}: expected={check.expected}, actual={check.actual}")

    # Summary
    print()
    print("=" * 60)
    print("SHOT 01 RESULT")
    print(f"  Output:      {target_file.name}")
    print(f"  Resolution:  {media_info.width}x{media_info.height}")
    print(f"  Duration:    {media_info.duration}s ({media_info.frames} frames)")
    print(f"  FPS:         {media_info.fps}")
    print(f"  Audio:       {'yes' if media_info.has_audio else 'no'}")
    print(f"  QC:          {qc_result.status}")
    print(f"  Time:        {elapsed:.1f}s")
    print("=" * 60)

    return qc_result.passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
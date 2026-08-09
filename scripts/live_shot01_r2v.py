"""Live E2E: Shot 01 with R2V (reference to video) — using character sheet.

Uses h3_vertical_r2v to pass character reference image for identity consistency.
Storyboard BW sheet is also used as composition guide.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lfo.comfy.client import ComfyApiClient
from lfo.comfy.collect import ComfyOutputCollector
from lfo.comfy.monitor import ComfyMonitor
from lfo.core.database import Database
from lfo.services.technical_qc_service import QCSpec, TechnicalQCService


def main():
    print("=" * 60)
    print("午夜不接单 — Shot 01 R2V (with character reference)")
    print("=" * 60)

    # 1. Load vertical R2V workflow
    wf_path = Path(__file__).resolve().parent.parent / "src" / "lfo" / "registry" / "h3_vertical_r2v.json"
    workflow = json.loads(wf_path.read_text(encoding="utf-8"))
    print(f"[1/7] Workflow loaded: {wf_path.name}")

    # 2. Upload character reference to ComfyUI input (need 3 copies for r2v slots)
    client = ComfyApiClient("http://127.0.0.1:8188")
    ref_local = Path(r"E:\ideaProjects\zero-to-story\workspace\午夜不接单\chapter_01\outputs\refs\ref_0.png")
    if not ref_local.exists():
        print(f"ERROR: Reference image not found: {ref_local}")
        return False
    upload = client.upload_image(ref_local, subfolder="")
    uploaded_name = upload["name"]
    print(f"[2/7] Reference uploaded: {uploaded_name}")

    # 3. Set ALL 3 reference slots (R2V requires 3 valid images)
    # Node 6/7/8 = Reference01/02/03
    workflow["6"]["inputs"]["image"] = uploaded_name
    workflow["7"]["inputs"]["image"] = uploaded_name
    workflow["8"]["inputs"]["image"] = uploaded_name

    # 4. Set prompt with <Picture 1> reference
    prompt = (
        "Scene: A narrow corridor in an old apartment building at night. "
        "Bird's eye view looking down the middle of the corridor. "
        "Wet floor reflecting dim light in the foreground, "
        "flickering fluorescent tube light in the midground going half-bright, "
        "rain-streaked window in the background with storm outside. "
        "No people, no characters. "
        "Cold blue-green fluorescent lighting, wet and oppressive atmosphere. "
        "Vertical 9:16 composition, photorealistic cinematic.\n"
        "Soundscape: Heavy rain hitting windows, fluorescent tube buzzing and flickering, "
        "dripping water echoing in the corridor, distant thunder rumble.\n"
        "Music: None — pure atmosphere."
    )
    # Node 9 = Prompt (PrimitiveStringMultiline)
    workflow["9"]["inputs"]["value"] = prompt
    workflow["21"]["inputs"]["filename_prefix"] = "video/midnight_ep001_shot01_r2v"
    print(f"[3/7] Prompt set ({len(prompt)} chars)")

    # 5. Submit
    monitor = ComfyMonitor(client)
    print("[4/7] Submitting to ComfyUI...")
    try:
        stats = client.get_system_stats()
        vram = stats["devices"][0]["vram_free"] / 1024**3
        print(f"      VRAM free: {vram:.1f} GB")
    except Exception as e:
        print(f"      WARNING: stats error: {e}")

    result = client.submit_prompt(workflow, client_id="midnight-shot01-r2v")
    prompt_id = result["prompt_id"]
    print(f"      Prompt ID: {prompt_id}")

    # 6. Monitor
    print("[5/7] Monitoring execution (timeout: 1200s)...")
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

    # 7. Collect
    print("[6/7] Collecting output...")
    output_root = Path("D:/ComfyUI/Comfy-Desktop/ComfyUI/ComfyUI/output")
    collector = ComfyOutputCollector(output_root)

    history = client.get_history(prompt_id)
    entry = history.get(prompt_id, {})
    outputs = entry.get("outputs", {})

    target_file = None
    for node_id, node_output in outputs.items():
        media_list = node_output.get("images", []) or node_output.get("video", [])
        if media_list:
            filename = media_list[0].get("filename", "")
            subfolder = media_list[0].get("subfolder", "")
            full_path = output_root / subfolder / filename if subfolder else output_root / filename
            if full_path.exists():
                target_file = full_path
                break

    if target_file is None:
        candidates = list(output_root.rglob("midnight_ep001_shot01_r2v*.mp4"))
        if candidates:
            target_file = max(candidates, key=lambda p: p.stat().st_mtime)

    if target_file is None:
        print("ERROR: No output files found")
        return False

    print(f"      Output: {target_file.name}")
    print(f"      Size: {target_file.stat().st_size / 1024 / 1024:.1f} MB")

    media_info = collector.validate_media(target_file)
    print(f"      Resolution: {media_info.width}x{media_info.height}")
    print(f"      FPS: {media_info.fps}, Duration: {media_info.duration}s")
    print(f"      Audio: {'yes' if media_info.has_audio else 'no'}")

    # 8. QC
    print("[7/7] Running QC...")
    db = Database(":memory:")
    db.init_schema()
    qc_service = TechnicalQCService(db)
    spec = QCSpec(
        width=448, height=800, fps=24.0, duration_sec=5.0,
        requires_audio=True, expected_video_codec="h264",
        duration_tolerance_sec=2.0,
    )

    db.execute(
        """INSERT INTO tasks (task_id, project_id, task_type, status, params_hash, dependency_hash, idempotency_key)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        ("task-shot01-r2v", "midnight-ch01", "video.h3", "RUNNING", "ph", "dh", "ik-shot01-r2v"),
    )
    db.execute(
        """INSERT INTO attempts (attempt_id, task_id, idempotency_key, status, params, content_hash, dependency_hash, params_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("att-shot01-r2v", "task-shot01-r2v", "ik-shot01-r2v", "COMPLETED", "{}", "ch", "dh", "ph"),
    )
    asset_id = "asset-shot01-r2v"
    db.execute(
        """INSERT INTO assets (asset_id, task_id, attempt_id, asset_type, file_path, metadata, width, height, duration, frame_count)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            asset_id, "task-shot01-r2v", "att-shot01-r2v", "video", str(target_file),
            json.dumps({"codec": "h264", "fps": media_info.fps, "has_audio": media_info.has_audio}),
            media_info.width, media_info.height, media_info.duration, media_info.frames,
        ),
    )
    qc_result = qc_service.check_asset(asset_id, spec)
    print(f"      QC status: {qc_result.status}")
    for check in qc_result.checks:
        symbol = "PASS" if check.passed else "FAIL"
        print(f"        [{symbol}] {check.name}: expected={check.expected}, actual={check.actual}")

    # Copy to outputs
    final_dest = Path(r"E:\ideaProjects\zero-to-story\workspace\午夜不接单\chapter_01\outputs\shot_001_r2v.mp4")
    final_dest.parent.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2(target_file, final_dest)
    print(f"\n      Copied to: {final_dest}")

    print("\n" + "=" * 60)
    print("SHOT 01 R2V RESULT")
    print(f"  Output:      {target_file.name}")
    print(f"  Resolution:  {media_info.width}x{media_info.height}")
    print(f"  Duration:    {media_info.duration}s ({media_info.frames} frames)")
    print(f"  QC:          {qc_result.status}")
    print(f"  Time:        {elapsed:.1f}s")
    print("=" * 60)

    return qc_result.passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
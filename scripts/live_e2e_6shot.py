"""Live 6-Shot E2E: drive the LLM-decomposed storyboard through the
production pipeline (submit → monitor → collect → QC → extract end frame).

Each shot:
- shot_001: T2V (h3_standard_t2v), no first frame
- shot_002-006: I2V (h3_standard_i2v), first_frame = previous shot's end frame

Total expected runtime: ~30-40 minutes (6 × ~5min on RTX 5080).
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lfo.comfy.client import ComfyApiClient
from lfo.comfy.collect import ComfyOutputCollector
from lfo.comfy.monitor import ComfyMonitor
from lfo.core.database import Database
from lfo.services.end_frame_extractor import EndFrameExtractor
from lfo.services.technical_qc_service import QCSpec, TechnicalQCService


PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = PROJECT_ROOT / "workspace"
NOVEL_ID = "我今天不上班"
CHAPTER_ID = "chapter_01"
NOVEL_DIR = WORKSPACE / NOVEL_ID / CHAPTER_ID
STORYBOARD_PATH = NOVEL_DIR / "storyboard.decomposed.json"
COMFY_OUTPUT_ROOT = Path("D:/ComfyUI/Comfy-Desktop/ComfyUI/ComfyUI/output")
WORKFLOW_DIR = PROJECT_ROOT / "tests" / "fixtures" / "workflows"

OUTPUT_DIR = NOVEL_DIR / "outputs"
FINAL_DIR = NOVEL_DIR / "final"

PROJECT_ID = f"{NOVEL_ID}-{CHAPTER_ID}"

# Per-mode resolution + QC spec
# T2V (h3_standard_t2v with default LFO.Resolution) → 864x480
# I2V (h3_standard_i2v with megapixels=0.6 + 1:1) → 800x800 (H3 auto-computed)
SPECS = {
    "t2va": dict(width=864, height=480),
    "i2v":  dict(width=800, height=800),
}


def find_output_video(output_root: Path, prefix: str) -> Path | None:
    """Find the output video file matching the prefix pattern."""
    subfolder, _, base_name = prefix.rpartition("/")
    search_dir = output_root / subfolder if subfolder else output_root
    if not search_dir.exists():
        candidates = list(output_root.rglob(f"{base_name}*.mp4"))
    else:
        candidates = list(search_dir.glob(f"{base_name}*.mp4"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def build_prompt(shot: dict) -> str:
    """Build a single dense H3 prompt for the MiniMaxH3ImageToVideo node.

    Combines description + camera + character action. ComfyUI H3 wants a
    prose-style prompt (no scene|soundscape|music pipe format here — the
    model embeds audio from the same prompt's natural language).
    """
    desc = shot["description"].strip()
    cam = shot.get("camera", {})
    cam_part = f"{cam.get('shot_size', 'medium')} {cam.get('angle', 'eye_level')} {cam.get('movement', 'static')}"
    chars = shot.get("characters", [])
    char_part = ""
    if chars:
        actions = "; ".join(c.get("action", "") for c in chars if c.get("action"))
        expressions = "; ".join(c.get("expression", "") for c in chars if c.get("expression"))
        if actions:
            char_part = f" Characters: {actions}"
        if expressions:
            char_part += f" Expressions: {expressions}"
    return f"{cam_part}, {desc}{char_part}"


def run_shot(
    shot: dict,
    shot_index: int,
    first_frame_path: Path | None,
    client: ComfyApiClient,
    monitor: ComfyMonitor,
    db: Database,
) -> dict:
    """Run a single shot through the full pipeline. Returns dict with end_frame_path."""
    shot_id = shot["shot_id"]
    mode = shot.get("generation_hint", {}).get("preferred_mode", "t2va")
    workflow_name = "h3_standard_t2v" if mode == "t2va" else "h3_standard_i2v"

    duration_sec = shot["desired_duration_ms"] / 1000.0
    prompt = build_prompt(shot)
    spec = SPECS[mode]
    width, height = spec["width"], spec["height"]

    print(f"\n{'='*60}")
    print(f"SHOT {shot_index + 1}/6: {shot_id} [{mode.upper()}]")
    print(f"  Description: {shot['description'][:60]}...")
    print(f"  Duration:    {duration_sec}s, {width}x{height}")
    print(f"  First frame: {first_frame_path.name if first_frame_path else '(none — T2V)'}")
    print(f"{'='*60}")

    # 1. Load workflow
    workflow = json.loads((WORKFLOW_DIR / f"{workflow_name}.json").read_text(encoding="utf-8"))
    print(f"[1/6] Workflow loaded: {workflow_name}")

    # 2. Set parameters
    if mode == "t2va":
        # T2V: node 6 = duration, node 8 = prompt, node 17 = SaveVideo
        workflow["6"]["inputs"]["value"] = duration_sec
        workflow["8"]["inputs"]["prompt"] = prompt
        task_id = f"task-{shot_id}"
        attempt_id = f"att-{shot_id}"
        filename_prefix = f"lfo/{PROJECT_ID}/{task_id}/{attempt_id}/video"
        workflow["17"]["inputs"]["filename_prefix"] = filename_prefix
        print(f"[2/6] T2V params set: duration={duration_sec}, prompt=<{len(prompt)} chars>")
    else:
        # I2V: node 9 = duration, node 11 = prompt, node 6 = first_frame, node 20 = SaveVideo
        if not first_frame_path:
            raise RuntimeError(f"Shot {shot_id} is I2V but no first_frame_path provided")
        upload = client.upload_image(first_frame_path)
        image_name = upload["name"]
        workflow["9"]["inputs"]["value"] = duration_sec
        workflow["11"]["inputs"]["prompt"] = prompt
        workflow["6"]["inputs"]["image"] = image_name
        task_id = f"task-{shot_id}"
        attempt_id = f"att-{shot_id}"
        filename_prefix = f"lfo/{PROJECT_ID}/{task_id}/{attempt_id}/video"
        workflow["20"]["inputs"]["filename_prefix"] = filename_prefix
        print(f"[2/6] I2V params set: first_frame={image_name}, duration={duration_sec}, prompt=<{len(prompt)} chars>")

    # 3. Submit
    client_id = f"lfo-6shot-{shot_id}"
    submit_result = client.submit_prompt(workflow, client_id=client_id)
    prompt_id = submit_result["prompt_id"]
    print(f"[3/6] Submitted: prompt_id={prompt_id}")

    # 4. Monitor
    print("[4/6] Monitoring execution...")
    start = time.time()
    final = monitor.poll_until_done(
        prompt_id,
        interval=5.0,
        timeout=1500.0,
        on_tick=lambda s: print(f"      ... {s.get('status', '?')} ({time.time() - start:.0f}s)", end="\r"),
    )
    elapsed = time.time() - start
    print()
    print(f"      Completed in {elapsed:.0f}s, status: {final.get('status')}")
    if not final.get("completed"):
        return {"shot_id": shot_id, "success": False, "error": final.get("error", "not completed"), "elapsed": elapsed}

    # 5. Collect
    print("[5/6] Collecting output...")
    target_file = find_output_video(COMFY_OUTPUT_ROOT, filename_prefix)
    if target_file is None:
        candidates = list(COMFY_OUTPUT_ROOT.rglob("video_*.mp4"))
        if candidates:
            target_file = max(candidates, key=lambda p: p.stat().st_mtime)
    if target_file is None:
        return {"shot_id": shot_id, "success": False, "error": "no output file", "elapsed": elapsed}

    size_mb = target_file.stat().st_size / 1024 / 1024
    print(f"      Output: {target_file.name} ({size_mb:.1f} MB)")

    collector = ComfyOutputCollector(COMFY_OUTPUT_ROOT)
    media = collector.validate_media(target_file)
    print(f"      Media:  {media.width}x{media.height}, {media.fps}fps, {media.duration}s, audio={'yes' if media.has_audio else 'no'}")

    # 6. QC + copy + end frame
    print("[6/6] QC + end frame extraction...")
    asset_id = f"asset-{shot_id}"
    db.execute(
        "INSERT INTO tasks (task_id, project_id, task_type, status, params_hash, dependency_hash, idempotency_key) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (task_id, PROJECT_ID, "video.h3", "RUNNING", "ph", "dh", f"ik-{shot_id}"),
    )
    db.execute(
        "INSERT INTO attempts (attempt_id, task_id, idempotency_key, status, params, content_hash, dependency_hash, params_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (attempt_id, task_id, f"ik-{shot_id}", "COMPLETED", "{}", "ch", "dh", "ph"),
    )
    db.execute(
        "INSERT INTO assets (asset_id, task_id, attempt_id, asset_type, file_path, metadata, width, height, duration, frame_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (asset_id, task_id, attempt_id, "video", str(target_file),
         json.dumps({"codec": "h264", "fps": media.fps, "has_audio": media.has_audio}),
         media.width, media.height, media.duration, media.frames),
    )

    qc_spec = QCSpec(
        width=width, height=height, fps=24.0,
        duration_sec=duration_sec, requires_audio=True,
        expected_video_codec="h264", duration_tolerance_sec=1.5,
    )
    qc = TechnicalQCService(db).check_asset(asset_id, qc_spec)
    print(f"      QC: {qc.status} — {'/'.join('P' if c.passed else 'F' for c in qc.checks)}")

    # Copy to outputs/final
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    dest_out = OUTPUT_DIR / f"{shot_id}.mp4"
    shutil.copy2(target_file, dest_out)
    shutil.copy2(target_file, FINAL_DIR / f"{shot_id}.mp4")

    # End frame extraction
    extractor = EndFrameExtractor(db, output_dir=str(OUTPUT_DIR))
    frame_result = extractor.extract(asset_id)
    end_frame = None
    if frame_result.success:
        end_frame = Path(frame_result.file_path)
        print(f"      End frame: {end_frame.name}")
    else:
        print(f"      End frame FAILED: {frame_result.error}")

    return {
        "shot_id": shot_id,
        "success": True,
        "elapsed": elapsed,
        "qc_passed": qc.passed,
        "output": str(dest_out),
        "end_frame": end_frame,
        "media": {"width": media.width, "height": media.height, "fps": media.fps,
                  "duration": media.duration, "audio": media.has_audio},
    }


def main() -> int:
    print("=" * 60)
    print("6-Shot Live E2E — LLM-decomposed storyboard")
    print("=" * 60)
    print(f"Novel: {NOVEL_ID}")
    print(f"Storyboard: {STORYBOARD_PATH}")

    sb = json.loads(STORYBOARD_PATH.read_text(encoding="utf-8"))
    print(f"Shots: {len(sb['shots'])}")
    print(f"Expected total duration: {sum(s['desired_duration_ms'] for s in sb['shots'])/1000:.1f}s")

    client = ComfyApiClient("http://127.0.0.1:8188")
    monitor = ComfyMonitor(client)

    try:
        stats = client.get_system_stats()
        vram = stats["devices"][0]["vram_free"] / 1024**3
        print(f"ComfyUI ready — VRAM free: {vram:.1f} GB")
    except Exception as e:
        print(f"ERROR: ComfyUI not reachable: {e}")
        return 1

    db = Database(":memory:")
    db.init_schema()

    results = []
    first_frame = None
    total_start = time.time()

    for i, shot in enumerate(sb["shots"]):
        r = run_shot(shot, i, first_frame, client, monitor, db)
        results.append(r)
        if not r["success"]:
            print(f"\n  SHOT {i+1} FAILED: {r.get('error')}")
            print("  Stopping pipeline (would skip downstream shots in real run)")
            break
        end_frame = r.get("end_frame")
        if end_frame and end_frame.exists():
            first_frame = end_frame
        else:
            print(f"  WARNING: no end frame, next shot will fall back to T2V-like behavior")

    total_elapsed = time.time() - total_start

    # Summary
    print(f"\n{'='*60}")
    print("6-SHOT E2E SUMMARY")
    print(f"{'='*60}")
    print(f"Total time: {total_elapsed/60:.1f} minutes")
    for r in results:
        status = "OK" if r["success"] else "FAIL"
        qc = "PASS" if r.get("qc_passed") else "FAIL"
        media = r.get("media", {})
        audio = media.get("audio", "?")
        elapsed = r.get("elapsed", 0)
        print(f"  {r['shot_id']}: {status} | QC: {qc} | Audio: {audio} | {elapsed:.0f}s")
    all_pass = all(r["success"] and r.get("qc_passed") for r in results)
    print(f"\nOverall: {'PASS' if all_pass else 'FAIL'}")
    print(f"{'='*60}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())

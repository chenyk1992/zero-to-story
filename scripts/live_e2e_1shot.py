"""Live 1-Shot E2E: single T2V shot for user novel "我今天不上班".

Simplified end-to-end test:
- Load storyboard from workspace
- Pick shot_001 (T2V)
- Load H3 T2V workflow
- Set prompt, duration, filename_prefix on correct nodes
- Submit → monitor → collect → QC
- Copy output to workspace
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Ensure src/ is on path (src layout)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from lfo.comfy.client import ComfyApiClient
from lfo.comfy.collect import ComfyOutputCollector
from lfo.comfy.monitor import ComfyMonitor
from lfo.core.database import Database
from lfo.services.end_frame_extractor import EndFrameExtractor
from lfo.services.technical_qc_service import QCSpec, TechnicalQCService

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = PROJECT_ROOT / "workspace"
NOVEL_ID = "我今天不上班"
CHAPTER_ID = "chapter_01"
STORYBOARD_PATH = WORKSPACE / NOVEL_ID / CHAPTER_ID / "storyboard.json"

COMFY_OUTPUT_ROOT = Path("D:/ComfyUI/Comfy-Desktop/ComfyUI/ComfyUI/output")
WORKFLOW_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "workflows" / "h3_standard_t2v.json"

# Output destination
OUTPUT_DIR = WORKSPACE / NOVEL_ID / CHAPTER_ID / "outputs"
FINAL_DIR = WORKSPACE / NOVEL_ID / CHAPTER_ID / "final"


def load_storyboard() -> dict:
    """Load storyboard from workspace."""
    if not STORYBOARD_PATH.exists():
        raise FileNotFoundError(f"Storyboard not found: {STORYBOARD_PATH}")
    return json.loads(STORYBOARD_PATH.read_text(encoding="utf-8"))


def build_h3_prompt(shot: dict) -> str:
    """Build a 3-layer H3 prompt (scene / soundscape / music) from shot data."""
    desc = shot["description"]
    scene_id = shot.get("scene_id", "")

    # Layer 1: visual scene
    visual = desc

    # Layer 2: soundscape from audio_policy or default
    sfx = "footsteps, ambient noise"

    # Layer 3: music mood
    mood = shot.get("generation_hint", {}).get("notes", "cinematic ambient")

    # H3 format: scene | soundscape | music
    return f"{visual} | {sfx} | {mood}"


def find_output_video(output_root: Path, prefix: str) -> Path | None:
    """Find the output video file matching the prefix pattern."""
    # SaveVideo writes to output_root / filename_prefix / *.mp4
    # prefix is like "lfo/proj/task/att/video" → subfolder "lfo/proj/task/att", filename "video_*.mp4"
    subfolder, _, base_name = prefix.rpartition("/")
    if subfolder:
        search_dir = output_root / subfolder
    else:
        search_dir = output_root

    if not search_dir.exists():
        # Fallback: search globally
        candidates = list(output_root.rglob(f"{base_name}*.mp4"))
    else:
        candidates = list(search_dir.glob(f"{base_name}*.mp4"))

    if not candidates:
        return None

    # Return the newest
    return max(candidates, key=lambda p: p.stat().st_mtime)


def run_1shot():
    print("=" * 60)
    print("1-Shot Live E2E: T2V for novel '我今天不上班'")
    print("=" * 60)

    # 0. Load storyboard
    sb = load_storyboard()
    project_info = sb.get("project", {})
    novel_id = project_info.get("novel_id", NOVEL_ID)
    chapter_id = project_info.get("chapter_id", CHAPTER_ID)
    project_id = project_info.get("project_id", f"{novel_id}-{chapter_id}")
    shot = sb["shots"][0]  # First shot (T2V)

    shot_id = shot["shot_id"]
    print(f"\nStoryboard: {project_info.get('title', '?')}")
    print(f"Shot: {shot_id} — {shot['description'][:60]}...")
    print(f"Mode: {shot.get('generation_hint', {}).get('preferred_mode', 't2va')}")

    # Build prompt
    prompt = build_h3_prompt(shot)
    duration_sec = shot.get("desired_duration_ms", 6000) / 1000.0
    print(f"Duration: {duration_sec}s")
    print(f"Prompt: {prompt[:80]}...")

    # 1. Check ComfyUI
    client = ComfyApiClient("http://127.0.0.1:8188")
    monitor = ComfyMonitor(client)

    try:
        stats = client.get_system_stats()
        vram = stats["devices"][0]["vram_free"] / 1024**3
        print(f"\nComfyUI ready — VRAM free: {vram:.1f} GB")
    except Exception as e:
        print(f"\nERROR: ComfyUI not reachable: {e}")
        return False

    # 2. Load workflow
    if not WORKFLOW_FIXTURE.exists():
        print(f"\nERROR: Workflow fixture not found: {WORKFLOW_FIXTURE}")
        return False

    workflow = json.loads(WORKFLOW_FIXTURE.read_text(encoding="utf-8"))
    print(f"[1/5] Workflow loaded: h3_standard_t2v")

    # 3. Set parameters on correct nodes
    # Node "6" = PrimitiveFloat (duration in seconds)
    workflow["6"]["inputs"]["value"] = duration_sec

    # Node "8" = MiniMaxH3ImageToVideo (prompt)
    workflow["8"]["inputs"]["prompt"] = prompt

    # Node "17" = SaveVideo (filename_prefix)
    task_id = f"task-{shot_id}"
    attempt_id = f"att-{shot_id}"
    filename_prefix = f"lfo/{project_id}/{task_id}/{attempt_id}/video"
    workflow["17"]["inputs"]["filename_prefix"] = filename_prefix

    print(f"[2/5] Parameters set:")
    print(f"      duration = {duration_sec}s (node 6)")
    print(f"      prompt = {prompt[:50]}... (node 8)")
    print(f"      filename_prefix = {filename_prefix} (node 17)")

    # 4. Submit
    client_id = f"lfo-1shot-{shot_id}"
    submit_result = client.submit_prompt(workflow, client_id=client_id)
    prompt_id = submit_result["prompt_id"]
    print(f"[3/5] Submitted: prompt_id={prompt_id}")

    # 5. Monitor
    print("[4/5] Monitoring execution...")
    start_time = time.time()
    final_status = monitor.poll_until_done(
        prompt_id,
        interval=5.0,
        timeout=1200.0,
        on_tick=lambda s: print(
            f"      ... {s.get('status', '?')} ({time.time() - start_time:.0f}s)",
            end="\r",
        ),
    )
    elapsed = time.time() - start_time
    print()
    print(f"      Completed in {elapsed:.0f}s, status: {final_status.get('status')}")

    if not final_status.get("completed"):
        print(f"\nERROR: Execution failed: {final_status.get('error', 'unknown')}")
        return False

    # 6. Collect output
    print("[5/5] Collecting output...")

    # Find output video file
    target_file = find_output_video(COMFY_OUTPUT_ROOT, filename_prefix)

    # Fallback: search for newest video file
    if target_file is None:
        candidates = list(COMFY_OUTPUT_ROOT.rglob("video_*.mp4"))
        if candidates:
            target_file = max(candidates, key=lambda p: p.stat().st_mtime)

    if target_file is None:
        print("\nERROR: No output video file found")
        return False

    print(f"      Output: {target_file.name}")
    print(f"      Size: {target_file.stat().st_size / 1024 / 1024:.1f} MB")

    # Validate media
    collector = ComfyOutputCollector(COMFY_OUTPUT_ROOT)
    media_info = collector.validate_media(target_file)
    print(f"      {media_info.width}x{media_info.height}, {media_info.fps}fps, "
          f"{media_info.duration}s, audio={'yes' if media_info.has_audio else 'no'}")

    # 7. QC
    print("\nRunning QC...")
    db = Database(":memory:")
    db.init_schema()

    asset_id = f"asset-{shot_id}"
    db.execute(
        """INSERT INTO tasks (task_id, project_id, task_type, status, params_hash, dependency_hash, idempotency_key)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (task_id, project_id, "video.h3", "RUNNING", "ph", "dh", f"ik-{shot_id}"),
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

    qc_spec = QCSpec(
        width=864,
        height=480,
        fps=24.0,
        duration_sec=duration_sec,
        requires_audio=True,
        expected_video_codec="h264",
        duration_tolerance_sec=1.5,
    )
    qc_service = TechnicalQCService(db)
    qc_result = qc_service.check_asset(asset_id, qc_spec)

    print(f"QC: {qc_result.status}")
    for check in qc_result.checks:
        symbol = "PASS" if check.passed else "FAIL"
        print(f"  [{symbol}] {check.name}: expected={check.expected}, actual={check.actual}")

    # 8. Copy output to workspace
    print("\nCopying output to workspace...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    import shutil
    dest_file = OUTPUT_DIR / f"{shot_id}.mp4"
    shutil.copy2(target_file, dest_file)
    print(f"  → {dest_file}")

    # Also copy to final dir
    final_file = FINAL_DIR / f"{shot_id}.mp4"
    shutil.copy2(target_file, final_file)
    print(f"  → {final_file}")

    # 9. Extract end frame for continuity
    print("\nExtracting end frame...")
    extractor = EndFrameExtractor(db, output_dir=str(OUTPUT_DIR))
    frame_result = extractor.extract(asset_id)
    if frame_result.success:
        print(f"  End frame: {frame_result.file_path}")
    else:
        print(f"  End frame extraction failed: {frame_result.error}")

    # Summary
    print("\n" + "=" * 60)
    print("1-SHOT E2E SUMMARY")
    print("=" * 60)
    print(f"  Shot: {shot_id}")
    print(f"  Workflow: h3_standard_t2v (T2V)")
    print(f"  Status: {'PASS' if qc_result.passed else 'FAIL'}")
    print(f"  QC: {qc_result.status}")
    print(f"  Output: {dest_file}")
    print(f"  Duration: {elapsed:.0f}s")
    print(f"  Media: {media_info.width}x{media_info.height}, {media_info.fps}fps, "
          f"{media_info.duration}s, audio={'yes' if media_info.has_audio else 'no'}")
    print("=" * 60)

    return qc_result.passed


if __name__ == "__main__":
    success = run_1shot()
    sys.exit(0 if success else 1)

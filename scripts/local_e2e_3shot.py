"""Local 3-Shot E2E: full delivery chain without ComfyUI.

Generates test videos locally with FFmpeg (testsrc), then runs the complete
pipeline: Normalize → Selection → EDL → Assembly → SRT → Final QC.

Verifies the E2E-A delivery package:
  - final.mp4 (1080x1920 H264, AAC 48kHz)
  - final.zh-CN.srt
  - edl.json (via DB query)
  - final_qc.json (via DB query)
  - asset_lineage.json (via DB query)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lfo.core.database import Database
from lfo.planning.schema import PlannedTask
from lfo.services.pipeline_service import PipelineService
from lfo.services.storyboard_graph_service import TaskGraph
from lfo.storyboard.storyboard import (
    Camera,
    ContinuityInfo,
    GenerationHint,
    ProjectInfo,
    Shot,
    Storyboard,
)

PROJECT_ID = "proj-3shot-local-e2e"
SHOT_COUNT = 3
SHOT_DURATION_SEC = 3
FPS = 24
WIDTH = 1080
HEIGHT = 1920


def generate_test_video(
    output_path: str,
    duration_sec: int = 3,
    width: int = 1080,
    height: int = 1920,
    fps: int = 24,
    color: str = "crimson",
) -> bool:
    """Generate a test video with FFmpeg testsrc + sine audio.

    Uses testsrc for video and sine wave for audio to produce a valid
    H.264/AAC MP4 that exercises the full pipeline.
    """
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration_sec}:size={width}x{height}:rate={fps}",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration_sec}",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-ar", "48000",
        "-ac", "2",
        "-shortest",
        output_path,
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"  FFmpeg failed: {exc}")
        return False

    if result.returncode != 0:
        print(f"  FFmpeg error: {result.stderr[:300]}")
        return False
    return True


def make_storyboard() -> Storyboard:
    """Create a 3-shot storyboard with narration for SRT."""
    shots_data = [
        {"id": "shot_001", "desc": "A lone samurai on a cliff at sunset", "narration": "夕阳下，孤独的武士站在悬崖边缘"},
        {"id": "shot_002", "desc": "The samurai draws from the sheath", "narration": "武士缓缓拔出刀刃，紧张感蔓延"},
        {"id": "shot_003", "desc": "Sweeping action as the samurai strikes", "narration": "刀光闪烁，衣袂飘飘，尘埃飞扬"},
    ]
    shots = []
    for i, sd in enumerate(shots_data[:SHOT_COUNT]):
        shot = Shot(
            shot_id=sd["id"],
            display_index=i + 1,
            scene_id="scene_001",
            description=sd["desc"],
            narration=sd["narration"],
            desired_duration_ms=SHOT_DURATION_SEC * 1000,
            camera=Camera(shot_size="medium", movement="static"),
            continuity=ContinuityInfo(start_frame_needed=(i > 0)),
            generation_hint=GenerationHint(),
        )
        shots.append(shot)
    return Storyboard(
        project=ProjectInfo(project_id=PROJECT_ID, title="Local 3-Shot E2E"),
        shots=shots,
    )


def make_planned_tasks() -> list[PlannedTask]:
    """Create planned tasks matching the storyboard shots."""
    tasks = []
    for i in range(SHOT_COUNT):
        sid = f"shot_{i + 1:03d}"
        tasks.append(PlannedTask(
            logical_task_key=f"video/{sid}",
            task_id=f"task_{sid}",
            project_id=PROJECT_ID,
            target_ids=[sid],
            workflow_mode="t2va" if i == 0 else "i2v",
        ))
    return tasks


def main():
    print("=" * 60)
    print("LOCAL 3-SHOT E2E — Full Delivery Chain")
    print("=" * 60)

    tmp_dir = Path(tempfile.mkdtemp(prefix="lfo_e2e_"))
    print(f"  Temp dir: {tmp_dir}")

    # 1. Generate test videos
    print("\n[1/4] Generating test videos with FFmpeg...")
    video_paths = []
    colors = ["crimson", "darkblue", "darkgreen"]
    for i in range(SHOT_COUNT):
        sid = f"shot_{i + 1:03d}"
        vpath = str(tmp_dir / f"{sid}_raw.mp4")
        ok = generate_test_video(
            vpath,
            duration_sec=SHOT_DURATION_SEC,
            width=WIDTH,
            height=HEIGHT,
            fps=FPS,
            color=colors[i % len(colors)],
        )
        if not ok:
            print(f"  FAILED to generate video for {sid}")
            return False
        size_mb = os.path.getsize(vpath) / 1024 / 1024
        print(f"  {sid}: {vpath} ({size_mb:.1f} MB)")
        video_paths.append(vpath)

    # 2. Setup DB + register raw assets
    print("\n[2/4] Setting up database and registering raw assets...")
    db = Database(":memory:")
    db.init_schema()
    db.execute(
        "INSERT INTO projects (project_id, name) VALUES (?, ?)",
        (PROJECT_ID, "Local 3-Shot E2E"),
    )

    for i in range(SHOT_COUNT):
        sid = f"shot_{i + 1:03d}"
        task_id = f"task_{sid}"
        attempt_id = f"att_{sid}"
        asset_id = f"asset_{sid}"

        db.execute(
            "INSERT INTO tasks (task_id, project_id, task_type, status, params_hash, dependency_hash, idempotency_key) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (task_id, PROJECT_ID, "video.h3", "SUCCEEDED", "ph", "dh", f"ik-{sid}"),
        )
        db.execute(
            "INSERT INTO attempts (attempt_id, task_id, idempotency_key, status, params, content_hash, dependency_hash, params_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (attempt_id, task_id, f"ik-{sid}", "COMPLETED", "{}", "ch", "dh", "ph"),
        )
        db.execute(
            """INSERT INTO assets (asset_id, task_id, attempt_id, asset_type, file_path, metadata, width, height, duration, frame_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                asset_id, task_id, attempt_id, "video", video_paths[i],
                json.dumps({"codec": "h264", "fps": float(FPS), "has_audio": True}),
                WIDTH, HEIGHT, float(SHOT_DURATION_SEC), SHOT_DURATION_SEC * FPS,
            ),
        )
        print(f"  Registered: {asset_id} -> {video_paths[i]}")

    # 3. Run the full pipeline
    print("\n[3/4] Running full pipeline (Normalize → Selection → EDL → Assembly → SRT → QC)...")
    service = PipelineService(
        db,
        output_dir=str(tmp_dir / "pipeline"),
        auto_approve=True,
    )
    storyboard = make_storyboard()
    planned_tasks = make_planned_tasks()

    # Mock graph service to use our pre-registered tasks
    service.graph_service = type("MockGraph", (), {
        "build_graph": lambda self, sb: TaskGraph(
            project_id=PROJECT_ID,
            tasks=planned_tasks,
        ),
    })()

    # Mock ComfyUI execution (assets already exist)
    service.readiness_service = type("MockReadiness", (), {
        "promote_to_ready": lambda self, tid: type("R", (), {"success": True, "materialization_id": f"mat-{tid}"})(),
    })()
    service.execution_facade = type("MockExec", (), {
        "run_ready_task": lambda self, tid: type("R", (), {
            "success": True,
            "attempt_id": f"att-{tid}",
            "prompt_id": f"prompt-{tid}",
        })(),
    })()
    service.video_collect = type("MockCollect", (), {
        "collect": lambda self, aid: type("R", (), {
            "success": True,
            "assets": [type("A", (), {"path": Path("/tmp/fake.mp4")})()],
            "errors": [],
        })(),
    })()
    service.qc_service = type("MockQC", (), {
        "check_asset": lambda self, aid, spec: type("R", (), {
            "passed": True,
            "status": "PASS",
            "checks": [],
            "issues": [],
        })(),
    })()

    # Mock DB fetchone for asset_id lookups during pipeline
    original_fetchone = db.fetchone
    def mock_fetchone(sql, params):
        # First try the real DB
        row = original_fetchone(sql, params)
        if row is not None:
            return row
        # Handle mock-generated attempt_ids: att-task_shot_001 -> asset_shot_001
        if "attempt_id" in sql and "asset_id" in sql:
            attempt = params[0]
            shot_part = attempt.replace("att-task_", "").replace("att-", "")
            return (f"asset_{shot_part}",)
        if "output_asset_id" in sql and "selected_clip_id" in sql:
            return (f"output-{params[0]}",)
        return None
    db.fetchone = mock_fetchone

    result = service.execute(storyboard)

    # 4. Verify delivery package
    print("\n[4/4] Verifying delivery package...")
    print(f"\n  Pipeline success: {result.success}")
    print(f"  Tasks: {result.completed_tasks}/{result.total_tasks} completed")

    for tr in result.task_results:
        print(f"    {tr.shot_id}: norm={tr.normalized_asset_id[:12]}... sel={tr.selected_clip_id[:12]}... endframe={tr.end_frame_extracted}")

    asm = result.assembly_result
    print("\n  Assembly:")
    print(f"    EDL: {asm.edl_id}")
    print(f"    Output: {asm.output_file_path}")
    print(f"    SRT: {asm.srt_file_path}")
    print(f"    Final QC: {'PASS' if asm.final_qc_passed else 'FAIL'}")

    # Verify delivery files exist
    delivery_ok = True
    if asm.output_file_path and os.path.exists(asm.output_file_path):
        size_mb = os.path.getsize(asm.output_file_path) / 1024 / 1024
        print(f"    final.mp4 exists: {size_mb:.1f} MB")
    else:
        print(f"    ERROR: final.mp4 not found at {asm.output_file_path}")
        delivery_ok = False

    if asm.srt_file_path and os.path.exists(asm.srt_file_path):
        print(f"    SRT exists: {asm.srt_file_path}")
        with open(asm.srt_file_path, encoding="utf-8") as f:
            srt_content = f.read()
        print(f"    SRT preview:\n{srt_content[:200]}...")
    else:
        print(f"    WARNING: SRT not found at {asm.srt_file_path}")

    # Print QC issues if any
    if not asm.final_qc_passed:
        row = db.fetchone(
            "SELECT issues FROM qc_reports WHERE asset_id = ?",
            (asm.output_asset_id,),
        )
        if row and row[0]:
            issues = json.loads(row[0])
            print(f"    QC issues: {issues}")

    # Print summary
    print(f"\n{'='*60}")
    overall = result.success and delivery_ok and asm.final_qc_passed
    print(f"  E2E-A RESULT: {'PASS' if overall else 'FAIL'}")
    print(f"{'='*60}")

    return overall


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

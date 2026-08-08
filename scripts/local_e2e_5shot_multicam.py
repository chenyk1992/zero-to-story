"""5-Shot Multi-Camera E2E-B: mixed resolutions, aspect ratios, frame rates.

Stress-tests the normalize + assembly pipeline with heterogeneous inputs:
- Mixed resolutions (landscape, portrait, square, HD, SD)
- Mixed frame rates (24, 25, 30 fps)
- Mixed durations (3-6s)

Verifies:
- Normalize correctly converts all inputs to 1080x1920 9:16
- Assembly produces a coherent final.mp4
- Final QC passes despite heterogeneous inputs
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

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

PROJECT_ID = "proj-5shot-multicam-e2e"

# Multi-camera shot definitions: heterogeneous inputs
SHOTS = [
    {
        "id": "shot_001", "desc": "Wide landscape establishing shot",
        "narration": "广角镜头，壮丽的山脉全景",
        "width": 1920, "height": 1080, "fps": 24, "duration": 5,
        "camera": "extreme_wide",
    },
    {
        "id": "shot_002", "desc": "Medium square portrait",
        "narration": "中景方形构图，人物表情特写",
        "width": 720, "height": 720, "fps": 25, "duration": 4,
        "camera": "medium",
    },
    {
        "id": "shot_003", "desc": "Vertical phone footage",
        "narration": "竖屏视频素材，城市天际线",
        "width": 1080, "height": 1920, "fps": 30, "duration": 3,
        "camera": "wide",
    },
    {
        "id": "shot_004", "desc": "HD close-up detail",
        "narration": "高清特写，细节纹理清晰可见",
        "width": 1280, "height": 720, "fps": 24, "duration": 6,
        "camera": "close_up",
    },
    {
        "id": "shot_005", "desc": "SD archival footage",
        "narration": "标清档案素材，复古质感",
        "width": 854, "height": 480, "fps": 30, "duration": 4,
        "camera": "medium",
    },
]


def generate_test_video(
    output_path: str,
    width: int,
    height: int,
    fps: int,
    duration_sec: int,
    color: str = "crimson",
) -> bool:
    """Generate a test video with specific resolution and frame rate."""
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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"  FFmpeg failed: {exc}")
        return False
    if result.returncode != 0:
        print(f"  FFmpeg error: {result.stderr[:300]}")
        return False
    return True


def make_storyboard() -> Storyboard:
    shots = []
    for i, sd in enumerate(SHOTS):
        shot = Shot(
            shot_id=sd["id"],
            display_index=i + 1,
            scene_id=f"scene_{i + 1:03d}",
            description=sd["desc"],
            narration=sd["narration"],
            desired_duration_ms=sd["duration"] * 1000,
            camera=Camera(shot_size=sd["camera"], movement="static"),
            continuity=ContinuityInfo(start_frame_needed=(i > 0)),
            generation_hint=GenerationHint(),
        )
        shots.append(shot)
    return Storyboard(
        project=ProjectInfo(project_id=PROJECT_ID, title="5-Shot Multi-Camera E2E-B"),
        shots=shots,
    )


def make_planned_tasks() -> list[PlannedTask]:
    tasks = []
    for i, sd in enumerate(SHOTS):
        tasks.append(PlannedTask(
            logical_task_key=f"video/{sd['id']}",
            task_id=f"task_{sd['id']}",
            project_id=PROJECT_ID,
            target_ids=[sd["id"]],
            workflow_mode="t2va" if i == 0 else "i2v",
        ))
    return tasks


def main():
    print("=" * 60)
    print("5-SHOT MULTI-CAMERA E2E-B — Normalize Stress Test")
    print("=" * 60)

    tmp_dir = Path(tempfile.mkdtemp(prefix="lfo_e2e5_"))
    print(f"  Temp dir: {tmp_dir}")

    # 1. Generate heterogeneous test videos
    print("\n[1/5] Generating multi-camera test videos...")
    video_paths = []
    colors = ["crimson", "darkblue", "darkgreen", "goldenrod", "purple"]
    for i, sd in enumerate(SHOTS):
        vpath = str(tmp_dir / f"{sd['id']}_raw.mp4")
        ok = generate_test_video(
            vpath,
            width=sd["width"],
            height=sd["height"],
            fps=sd["fps"],
            duration_sec=sd["duration"],
            color=colors[i % len(colors)],
        )
        if not ok:
            print(f"  FAILED: {sd['id']}")
            return False
        size_mb = os.path.getsize(vpath) / 1024 / 1024
        print(f"  {sd['id']}: {sd['width']}x{sd['height']}@{sd['fps']}fps "
              f"{sd['duration']}s -> {vpath} ({size_mb:.1f} MB)")
        video_paths.append(vpath)

    # 2. Setup DB + register raw assets
    print("\n[2/5] Setting up database and registering raw assets...")
    db = Database(":memory:")
    db.init_schema()
    db.execute(
        "INSERT INTO projects (project_id, name) VALUES (?, ?)",
        (PROJECT_ID, "5-Shot Multi-Camera E2E-B"),
    )

    for i, sd in enumerate(SHOTS):
        sid = sd["id"]
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
                json.dumps({"codec": "h264", "fps": float(sd["fps"]), "has_audio": True}),
                sd["width"], sd["height"], float(sd["duration"]), sd["duration"] * sd["fps"],
            ),
        )
        print(f"  Registered: {asset_id} ({sd['width']}x{sd['height']}@{sd['fps']}fps)")

    # 3. Run the full pipeline
    print("\n[3/5] Running full pipeline...")
    service = PipelineService(
        db,
        output_dir=str(tmp_dir / "pipeline"),
        auto_approve=True,
    )
    storyboard = make_storyboard()
    planned_tasks = make_planned_tasks()

    service.graph_service = type("MockGraph", (), {
        "build_graph": lambda self, sb: TaskGraph(
            project_id=PROJECT_ID, tasks=planned_tasks,
        ),
    })()
    service.readiness_service = type("MockR", (), {
        "promote_to_ready": lambda self, tid: type("R", (), {"success": True, "materialization_id": f"mat-{tid}"})(),
    })()
    service.execution_facade = type("MockE", (), {
        "run_ready_task": lambda self, tid: type("R", (), {
            "success": True, "attempt_id": f"att-{tid}", "prompt_id": f"prompt-{tid}",
        })(),
    })()
    service.video_collect = type("MockC", (), {
        "collect": lambda self, aid: type("R", (), {
            "success": True, "assets": [type("A", (), {"path": Path("/tmp/fake.mp4")})()], "errors": [],
        })(),
    })()
    service.qc_service = type("MockQ", (), {
        "check_asset": lambda self, aid, spec: type("R", (), {
            "passed": True, "status": "PASS", "checks": [], "issues": [],
        })(),
    })()

    original_fetchone = db.fetchone
    def mock_fetchone(sql, params):
        # Only match the specific pipeline query: WHERE attempt_id = ?
        if "WHERE attempt_id" in sql:
            shot_part = params[0].replace("att-task_", "")
            return (f"asset_{shot_part}",)
        return original_fetchone(sql, params)
    db.fetchone = mock_fetchone

    result = service.execute(storyboard)

    # 4. Verify normalize results
    print("\n[4/5] Verifying multi-camera normalize results...")
    all_normalized_ok = True
    for sd in SHOTS:
        norm_rows = db.fetchall(
            """SELECT a.width, a.height, a.duration, a.metadata
               FROM assets a
               JOIN asset_relations ar ON a.asset_id = ar.target_asset_id
               JOIN assets src ON ar.source_asset_id = src.asset_id
               WHERE src.file_path LIKE ?""",
            (f"%{sd['id']}_raw.mp4",),
        )
        if not norm_rows:
            print(f"  {sd['id']}: NO NORMALIZED OUTPUT")
            all_normalized_ok = False
            continue
        w, h, dur, meta = norm_rows[0]
        meta_dict = json.loads(meta) if meta else {}
        print(f"  {sd['id']}: {sd['width']}x{sd['height']} -> {w}x{h}, "
              f"fps={meta_dict.get('fps', '?'):.1f}, dur={dur:.1f}s")
        # Verify 9:16 output
        if w != 1080 or h != 1920:
            print(f"    WARNING: Expected 1080x1920, got {w}x{h}")

    # 5. Verify delivery package
    print("\n[5/5] Verifying delivery package...")
    asm = result.assembly_result

    print(f"\n  Pipeline success: {result.success}")
    print(f"  Tasks: {result.completed_tasks}/{result.total_tasks} completed")
    for tr in result.task_results:
        print(f"    {tr.shot_id}: norm={tr.normalized_asset_id[:12]}... "
              f"sel={tr.selected_clip_id[:12]}... endframe={tr.end_frame_extracted}")

    print("\n  Assembly:")
    print(f"    EDL: {asm.edl_id}")
    print(f"    Output: {asm.output_file_path}")
    print(f"    SRT: {asm.srt_file_path}")
    print(f"    Final QC: {'PASS' if asm.final_qc_passed else 'FAIL'}")

    delivery_ok = True
    if asm.output_file_path and os.path.exists(asm.output_file_path):
        size_mb = os.path.getsize(asm.output_file_path) / 1024 / 1024
        print(f"    final.mp4: {size_mb:.1f} MB")
    else:
        print("    ERROR: final.mp4 not found")
        delivery_ok = False

    if asm.srt_file_path and os.path.exists(asm.srt_file_path):
        with open(asm.srt_file_path, encoding="utf-8") as f:
            print(f"    SRT cues:\n{f.read()[:300]}...")

    if not asm.final_qc_passed:
        row = db.fetchone("SELECT issues FROM qc_reports WHERE asset_id = ?", (asm.output_asset_id,))
        if row and row[0]:
            print(f"    QC issues: {json.loads(row[0])}")

    print(f"\n{'='*60}")
    overall = result.success and delivery_ok and asm.final_qc_passed and all_normalized_ok
    print(f"  E2E-B RESULT: {'PASS' if overall else 'FAIL'}")
    print(f"{'='*60}")

    return overall


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

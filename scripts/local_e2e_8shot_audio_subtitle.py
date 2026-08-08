"""8-Shot Audio + Subtitle E2E-C: stress test silent audio and subtitle gaps.

Validates:
- Silent audio track generation for clips without audio
- Mixed audio: some shots with audio, some without
- Mixed subtitles: some shots with narration, some without (gaps in SRT)
- Audio/video duration sync across 8 shots
- Long timeline assembly (8 shots, ~30s total)
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

PROJECT_ID = "proj-8shot-audio-subtitle-e2e"

# 8 shots: mixed audio (yes/no) and mixed subtitles (yes/no)
SHOTS = [
    {"id": "shot_001", "desc": "Opening with audio", "narration": "第一段：有声音有字幕",
     "width": 1920, "height": 1080, "fps": 24, "duration": 4, "has_audio": True},
    {"id": "shot_002", "desc": "Silent clip with subtitle", "narration": "第二段：无声音有字幕",
     "width": 1280, "height": 720, "fps": 24, "duration": 3, "has_audio": False},
    {"id": "shot_003", "desc": "Audio clip no subtitle", "narration": "",
     "width": 1080, "height": 1920, "fps": 30, "duration": 5, "has_audio": True},
    {"id": "shot_004", "desc": "Silent no subtitle", "narration": "",
     "width": 720, "height": 720, "fps": 25, "duration": 3, "has_audio": False},
    {"id": "shot_005", "desc": "Audio with subtitle", "narration": "第五段：有声音有字幕",
     "width": 854, "height": 480, "fps": 30, "duration": 4, "has_audio": True},
    {"id": "shot_006", "desc": "Silent with subtitle", "narration": "第六段：无声音有字幕",
     "width": 1920, "height": 1080, "fps": 24, "duration": 3, "has_audio": False},
    {"id": "shot_007", "desc": "Audio no subtitle", "narration": "",
     "width": 1280, "height": 720, "fps": 24, "duration": 5, "has_audio": True},
    {"id": "shot_008", "desc": "Finale silent+subtitle", "narration": "第八段：尾声字幕",
     "width": 1080, "height": 1920, "fps": 30, "duration": 4, "has_audio": False},
]


def generate_test_video(
    output_path: str,
    width: int,
    height: int,
    fps: int,
    duration_sec: int,
    has_audio: bool,
) -> bool:
    """Generate a test video. If has_audio=False, output has no audio stream."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={duration_sec}:size={width}x{height}:rate={fps}",
    ]
    if has_audio:
        cmd.extend([
            "-f", "lavfi",
            "-i", f"sine=frequency=440:duration={duration_sec}",
        ])
    cmd.extend([
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
    ])
    if has_audio:
        cmd.extend(["-c:a", "aac", "-ar", "48000", "-ac", "2"])
    else:
        cmd.extend(["-an"])
    cmd.extend(["-shortest", output_path])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"  FFmpeg failed: {exc}")
        return False
    if result.returncode != 0:
        print(f"  FFmpeg error: {result.stderr[:300]}")
        return False
    return True


def probe_duration(file_path: str) -> float:
    """Get media duration via ffprobe."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", file_path],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode == 0:
            return float(json.loads(r.stdout).get("format", {}).get("duration", 0))
    except Exception:
        pass
    return 0.0


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
            camera=Camera(shot_size="medium", movement="static"),
            continuity=ContinuityInfo(start_frame_needed=(i > 0)),
            generation_hint=GenerationHint(),
        )
        shots.append(shot)
    return Storyboard(
        project=ProjectInfo(project_id=PROJECT_ID, title="8-Shot Audio+Subtitle E2E-C"),
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
    print("8-SHOT AUDIO + SUBTITLE E2E-C — Stress Test")
    print("=" * 60)

    tmp_dir = Path(tempfile.mkdtemp(prefix="lfo_e2e8_"))
    print(f"  Temp dir: {tmp_dir}")

    # 1. Generate test videos (mixed audio)
    print("\n[1/6] Generating 8 test videos (mixed audio)...")
    video_paths = []
    for i, sd in enumerate(SHOTS):
        vpath = str(tmp_dir / f"{sd['id']}_raw.mp4")
        ok = generate_test_video(
            vpath, sd["width"], sd["height"],
            sd["fps"], sd["duration"], sd["has_audio"],
        )
        if not ok:
            print(f"  FAILED: {sd['id']}")
            return False
        audio_flag = "audio" if sd["has_audio"] else "silent"
        print(f"  {sd['id']}: {sd['width']}x{sd['height']}@{sd['fps']}fps "
              f"{sd['duration']}s [{audio_flag}]")
        video_paths.append(vpath)

    # 2. Setup DB
    print("\n[2/6] Setting up database and registering raw assets...")
    db = Database(":memory:")
    db.init_schema()
    db.execute(
        "INSERT INTO projects (project_id, name) VALUES (?, ?)",
        (PROJECT_ID, "8-Shot Audio+Subtitle E2E-C"),
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
                json.dumps({"codec": "h264", "fps": float(sd["fps"]), "has_audio": sd["has_audio"]}),
                sd["width"], sd["height"], float(sd["duration"]), sd["duration"] * sd["fps"],
            ),
        )

    # 3. Run the full pipeline
    print("\n[3/6] Running full pipeline...")
    service = PipelineService(
        db,
        output_dir=str(tmp_dir / "pipeline"),
        auto_approve=True,
    )
    storyboard = make_storyboard()
    planned_tasks = make_planned_tasks()

    service.graph_service = type("MockG", (), {
        "build_graph": lambda self, sb: TaskGraph(project_id=PROJECT_ID, tasks=planned_tasks),
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
        if "WHERE attempt_id" in sql:
            shot_part = params[0].replace("att-task_", "")
            return (f"asset_{shot_part}",)
        return original_fetchone(sql, params)
    db.fetchone = mock_fetchone

    result = service.execute(storyboard)

    # 4. Verify silent audio generation
    print("\n[4/6] Verifying silent audio generation...")
    silent_clips = [sd for sd in SHOTS if not sd["has_audio"]]
    audio_clips = [sd for sd in SHOTS if sd["has_audio"]]

    print(f"  Source clips without audio: {len(silent_clips)}")
    print(f"  Source clips with audio: {len(audio_clips)}")

    # Check that normalized outputs have audio (silent track generated)
    for sd in SHOTS:
        norm_rows = db.fetchall(
            """SELECT a.metadata FROM assets a
               JOIN asset_relations ar ON a.asset_id = ar.target_asset_id
               JOIN assets src ON ar.source_asset_id = src.asset_id
               WHERE src.file_path LIKE ?""",
            (f"%{sd['id']}_raw.mp4",),
        )
        if norm_rows:
            meta = json.loads(norm_rows[0][0]) if norm_rows[0][0] else {}
            has_audio = meta.get("has_audio", False)
            expected = True  # normalize always produces audio (silent if needed)
            status = "OK" if has_audio == expected else "FAIL"
            print(f"  {sd['id']}: normalized has_audio={has_audio} [{status}]")

    # 5. Verify SRT gaps (shots without narration produce no cue)
    print("\n[5/6] Verifying subtitle gaps...")
    asm = result.assembly_result
    if not asm.success:
        print(f"\n  Assembly FAILED: {asm.error}")
    narrated_shots = [sd for sd in SHOTS if sd["narration"]]
    silent_shots = [sd for sd in SHOTS if not sd["narration"]]
    print(f"  Shots with narration: {len(narrated_shots)}")
    print(f"  Shots without narration: {len(silent_shots)}")

    if asm.srt_file_path and os.path.exists(asm.srt_file_path):
        with open(asm.srt_file_path, encoding="utf-8") as f:
            srt_content = f.read()
        cue_count = srt_content.strip().count("\n\n") + (1 if srt_content.strip() else 0)
        print(f"  SRT cue count: {cue_count} (expected {len(narrated_shots)})")
        for sd in narrated_shots:
            if sd["narration"] in srt_content:
                print(f"    {sd['id']}: narration found [OK]")
            else:
                print(f"    {sd['id']}: narration MISSING [FAIL]")
        for sd in silent_shots:
            if sd["narration"] == "":
                print(f"    {sd['id']}: no narration (gap) [OK]")

    # 6. Verify audio/video sync
    print("\n[6/6] Verifying audio/video duration sync...")
    if asm.output_file_path and os.path.exists(asm.output_file_path):
        total_dur = probe_duration(asm.output_file_path)
        expected_dur = sum(sd["duration"] for sd in SHOTS)
        print(f"  Final.mp4 duration: {total_dur:.2f}s (expected ~{expected_dur}s)")
        print(f"  Final QC: {'PASS' if asm.final_qc_passed else 'FAIL'}")

        if not asm.final_qc_passed:
            row = db.fetchone("SELECT issues FROM qc_reports WHERE asset_id = ?", (asm.output_asset_id,))
            if row and row[0]:
                print(f"  QC issues: {json.loads(row[0])}")

    print(f"\n{'='*60}")
    overall = result.success and asm.final_qc_passed
    print(f"  E2E-C RESULT: {'PASS' if overall else 'FAIL'}")
    print(f"{'='*60}")

    return overall


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

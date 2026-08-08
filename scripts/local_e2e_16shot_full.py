"""16-Shot Full-Featured E2E-D: all stress dimensions combined.

Combines every stress scenario:
- Multi-camera: 8+ resolutions (landscape, portrait, square, HD, SD, 4K-ish)
- Variable speed: 4 frame rates (20, 24, 25, 30 fps)
- Audio tracks: ~50% silent (tests silent audio generation)
- Mixed subtitles: ~50% without narration (tests SRT gaps)
- Long timeline: ~50s total, stressing assembly concat
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

PROJECT_ID = "proj-16shot-full-stress-e2e"

# 16 shots combining all stress dimensions
SHOTS = [
    {"id": "shot_001", "narration": "开场：壮丽山川", "w": 1920, "h": 1080, "fps": 24, "dur": 3, "audio": True},
    {"id": "shot_002", "narration": "", "w": 1280, "h": 720, "fps": 24, "dur": 2, "audio": False},
    {"id": "shot_003", "narration": "第三段：城市夜景", "w": 1080, "h": 1920, "fps": 30, "dur": 4, "audio": True},
    {"id": "shot_004", "narration": "", "w": 720, "h": 720, "fps": 25, "dur": 3, "audio": False},
    {"id": "shot_005", "narration": "第五段：人物特写", "w": 854, "h": 480, "fps": 30, "dur": 3, "audio": True},
    {"id": "shot_006", "narration": "", "w": 1920, "h": 1080, "fps": 24, "dur": 2, "audio": False},
    {"id": "shot_007", "narration": "第七段：动作场景", "w": 1280, "h": 720, "fps": 24, "dur": 4, "audio": True},
    {"id": "shot_008", "narration": "", "w": 1080, "h": 1920, "fps": 30, "dur": 2, "audio": False},
    {"id": "shot_009", "narration": "第九段：回忆片段", "w": 720, "h": 720, "fps": 20, "dur": 3, "audio": True},
    {"id": "shot_010", "narration": "", "w": 854, "h": 480, "fps": 25, "dur": 3, "audio": False},
    {"id": "shot_011", "narration": "第十一段：追逐戏", "w": 1920, "h": 1080, "fps": 24, "dur": 4, "audio": True},
    {"id": "shot_012", "narration": "", "w": 1280, "h": 720, "fps": 30, "dur": 2, "audio": False},
    {"id": "shot_013", "narration": "第十三段：对话", "w": 1080, "h": 1920, "fps": 24, "dur": 3, "audio": True},
    {"id": "shot_014", "narration": "", "w": 720, "h": 720, "fps": 25, "dur": 3, "audio": False},
    {"id": "shot_015", "narration": "第十五段：高潮", "w": 854, "h": 480, "fps": 30, "dur": 4, "audio": True},
    {"id": "shot_016", "narration": "尾声：字幕落幕", "w": 1920, "h": 1080, "fps": 24, "dur": 3, "audio": False},
]


def generate_test_video(path, w, h, fps, dur, has_audio):
    cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', f'testsrc=duration={dur}:size={w}x{h}:rate={fps}']
    if has_audio:
        cmd += ['-f', 'lavfi', '-i', f'sine=frequency=440:duration={dur}']
    cmd += ['-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p']
    if has_audio:
        cmd += ['-c:a', 'aac', '-ar', '48000', '-ac', '2']
    else:
        cmd += ['-an']
    cmd += ['-shortest', path]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return r.returncode == 0


def probe_duration(path):
    try:
        r = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', path],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return float(json.loads(r.stdout).get('format', {}).get('duration', 0))
    except Exception:
        pass
    return 0.0


def make_storyboard():
    shots = []
    for i, sd in enumerate(SHOTS):
        shots.append(Shot(
            shot_id=sd["id"], display_index=i + 1, scene_id=f"scene_{i + 1:03d}",
            description=f"Shot {i + 1}", narration=sd["narration"],
            desired_duration_ms=sd["dur"] * 1000,
            camera=Camera(shot_size="medium", movement="static"),
            continuity=ContinuityInfo(start_frame_needed=(i > 0)),
            generation_hint=GenerationHint(),
        ))
    return Storyboard(project=ProjectInfo(project_id=PROJECT_ID, title="16-Shot Full Stress E2E-D"), shots=shots)


def make_planned_tasks():
    return [PlannedTask(
        logical_task_key=f"video/{sd['id']}", task_id=f"task_{sd['id']}",
        project_id=PROJECT_ID, target_ids=[sd["id"]], workflow_mode="t2va" if i == 0 else "i2v",
    ) for i, sd in enumerate(SHOTS)]


def main():
    print("=" * 60)
    print("16-SHOT FULL STRESS E2E-D — All Dimensions")
    print("=" * 60)

    tmp_dir = Path(tempfile.mkdtemp(prefix="lfo_e2e16_"))
    print(f"  Temp dir: {tmp_dir}")

    # 1. Generate test videos
    print(f"\n[1/5] Generating {len(SHOTS)} test videos...")
    video_paths = []
    for sd in SHOTS:
        vpath = str(tmp_dir / f"{sd['id']}_raw.mp4")
        if not generate_test_video(vpath, sd["w"], sd["h"], sd["fps"], sd["dur"], sd["audio"]):
            print(f"  FAILED: {sd['id']}")
            return False
        tag = "audio" if sd["audio"] else "silent"
        print(f"  {sd['id']}: {sd['w']}x{sd['h']}@{sd['fps']}fps {sd['dur']}s [{tag}]")
        video_paths.append(vpath)

    # 2. Setup DB
    print("\n[2/5] Setting up database...")
    db = Database(":memory:")
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES (?, ?)", (PROJECT_ID, "16-Shot E2E-D"))

    for i, sd in enumerate(SHOTS):
        sid = sd["id"]
        db.execute("INSERT INTO tasks (task_id, project_id, task_type, status, params_hash, dependency_hash, idempotency_key) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (f"task_{sid}", PROJECT_ID, "video.h3", "SUCCEEDED", "ph", "dh", f"ik-{sid}"))
        db.execute("INSERT INTO attempts (attempt_id, task_id, idempotency_key, status, params, content_hash, dependency_hash, params_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (f"att_{sid}", f"task_{sid}", f"ik-{sid}", "COMPLETED", "{}", "ch", "dh", "ph"))
        db.execute("INSERT INTO assets (asset_id, task_id, attempt_id, asset_type, file_path, metadata, width, height, duration, frame_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (f"asset_{sid}", f"task_{sid}", f"att_{sid}", "video", video_paths[i],
                    json.dumps({"codec": "h264", "fps": float(sd["fps"]), "has_audio": sd["audio"]}),
                    sd["w"], sd["h"], float(sd["dur"]), sd["dur"] * sd["fps"]))

    # 3. Run pipeline
    print("\n[3/5] Running full pipeline...")
    service = PipelineService(db, output_dir=str(tmp_dir / "pipeline"), auto_approve=True)
    storyboard = make_storyboard()
    planned_tasks = make_planned_tasks()

    service.graph_service = type("M", (), {"build_graph": lambda s, sb: TaskGraph(project_id=PROJECT_ID, tasks=planned_tasks)})()
    service.readiness_service = type("M", (), {"promote_to_ready": lambda s, t: type("R", (), {"success": True, "materialization_id": f"mat-{t}"})()})()
    service.execution_facade = type("M", (), {"run_ready_task": lambda s, t: type("R", (), {"success": True, "attempt_id": f"att-{t}", "prompt_id": f"prompt-{t}"})()})()
    service.video_collect = type("M", (), {"collect": lambda s, a: type("R", (), {"success": True, "assets": [type("A", (), {"path": Path("/tmp/f")})()], "errors": []})()})()
    service.qc_service = type("M", (), {"check_asset": lambda s, a, sp: type("R", (), {"passed": True, "status": "PASS", "checks": [], "issues": []})()})()

    orig_fetch = db.fetchone
    db.fetchone = lambda sql, params: (f"asset_{params[0].replace('att-task_', '')}",) if "WHERE attempt_id" in sql else orig_fetch(sql, params)

    result = service.execute(storyboard)

    # 4. Verify
    print("\n[4/5] Verifying results...")
    asm = result.assembly_result
    narrated = [sd for sd in SHOTS if sd["narration"]]
    silent_src = [sd for sd in SHOTS if not sd["audio"]]

    print(f"  Pipeline success: {result.success}")
    print(f"  Tasks: {result.completed_tasks}/{result.total_tasks}")
    print(f"  Narrated shots: {len(narrated)}, Silent source shots: {len(silent_src)}")

    # Check SRT cue count
    srt_ok = True
    if asm.srt_file_path and os.path.exists(asm.srt_file_path):
        with open(asm.srt_file_path, encoding="utf-8") as f:
            content = f.read()
        cues = [b for b in content.strip().split("\n\n") if b.strip()]
        print(f"  SRT cues: {len(cues)} (expected {len(narrated)})")
        if len(cues) != len(narrated):
            srt_ok = False

    # 5. Verify output
    print("\n[5/5] Verifying delivery...")
    if asm.output_file_path and os.path.exists(asm.output_file_path):
        dur = probe_duration(asm.output_file_path)
        expected = sum(sd["dur"] for sd in SHOTS)
        print(f"  final.mp4: {os.path.getsize(asm.output_file_path) / 1024 / 1024:.1f} MB")
        print(f"  Duration: {dur:.2f}s (expected ~{expected}s)")
    print(f"  Final QC: {'PASS' if asm.final_qc_passed else 'FAIL'}")
    if not asm.final_qc_passed:
        row = db.fetchone("SELECT issues FROM qc_reports WHERE asset_id = ?", (asm.output_asset_id,))
        if row and row[0]:
            print(f"  Issues: {json.loads(row[0])}")

    print(f"\n{'='*60}")
    overall = result.success and asm.final_qc_passed and srt_ok
    print(f"  E2E-D RESULT: {'PASS' if overall else 'FAIL'}")
    print(f"{'='*60}")
    return overall


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

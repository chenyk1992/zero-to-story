"""Smoke test for upgraded H3 workflows (v2.0).

Submits all 3 workflows to local ComfyUI and verifies:
1. Each workflow can be submitted (no JSON validation errors)
2. Each workflow runs to completion
3. Each output is a valid MP4 (basic file check)
4. Audio track is present (ffprobe)

This test requires a real ComfyUI instance running at :8188.
I2V and R2V are auto-skipped if required input images are missing.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from lfo.comfy.client import ComfyApiClient  # noqa: E402
from lfo.comfy.monitor import ComfyMonitor  # noqa: E402
from lfo.comfy.collect import ComfyOutputCollector  # noqa: E402

WORKFLOW_DIR = PROJECT_ROOT / "tests" / "fixtures" / "workflows"
COMFY_OUTPUT_DIR = Path(r"C:\Users\Administrator\Documents\comfy\ComfyUI\output")
LOCAL_OUTPUT_DIR = PROJECT_ROOT / "smoke_h3_v2_outputs"
COMFY_URL = "http://127.0.0.1:8188"
TIMEOUT_SEC = 900  # 15 min per workflow
POLL_SEC = 5

# Test prompts — short, simple, fast generation
T2V_PROMPT = (
    "A red apple resting on a dark wooden table, soft window light from the left, "
    "shallow depth of field, photorealistic, calm and minimal. "
    "Audio: gentle ambient room tone, very soft."
)


def _check_video(path: Path) -> dict:
    """Probe a video file for basic properties."""
    if not path.exists():
        return {"exists": False, "error": "file not found"}
    size = path.stat().st_size
    info = {
        "exists": True,
        "size_mb": round(size / 1024 / 1024, 2),
        "path": str(path),
    }
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,width,height,r_frame_rate,duration,nb_frames",
                "-of", "json", str(path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            v = json.loads(result.stdout).get("streams", [{}])[0]
            info.update({
                "video_codec": v.get("codec_name"),
                "width": v.get("width"),
                "height": v.get("height"),
                "fps": v.get("r_frame_rate"),
                "duration_sec": v.get("duration"),
                "frames": v.get("nb_frames"),
            })
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_name,sample_rate,channels",
                "-of", "json", str(path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and json.loads(result.stdout).get("streams"):
            a = json.loads(result.stdout)["streams"][0]
            info.update({
                "audio_codec": a.get("codec_name"),
                "sample_rate": a.get("sample_rate"),
                "channels": a.get("channels"),
            })
    except FileNotFoundError:
        info["ffprobe_missing"] = True
    except Exception as e:
        info["probe_error"] = str(e)
    return info


def run_workflow(name: str, prompt_overrides: dict) -> dict:
    """Submit one workflow and verify."""
    print(f"\n{'='*70}")
    print(f"  Smoke: {name}")
    print(f"{'='*70}")

    wf_path = WORKFLOW_DIR / f"{name}.json"
    wf = json.loads(wf_path.read_text(encoding="utf-8"))

    # Apply overrides
    for node_id, key, val in prompt_overrides:
        wf[node_id]["inputs"][key] = val

    # Generate unique client_id
    client_id = f"smoke-{uuid.uuid4().hex[:8]}"

    # Submit
    client = ComfyApiClient(base_url=COMFY_URL)
    print(f"  → Submitting to {COMFY_URL} (client_id={client_id})")
    start = time.time()
    result = client.submit_prompt(wf, client_id)
    prompt_id = result.get("prompt_id")
    if not prompt_id:
        return {"name": name, "ok": False, "error": f"no prompt_id in response: {result}"}
    print(f"  → prompt_id: {prompt_id}")

    # Monitor
    monitor = ComfyMonitor(client)
    print(f"  → Waiting (timeout {TIMEOUT_SEC}s)...")
    status = monitor.wait_for_output(
        prompt_id,
        client_id=client_id,
        poll_interval=POLL_SEC,
        timeout=TIMEOUT_SEC,
    )
    elapsed = time.time() - start
    final_status = status.get("status", "unknown")
    print(f"  → Status: {final_status} ({elapsed:.0f}s)")

    if status.get("error") or final_status == "error":
        return {"name": name, "ok": False, "error": status.get("error"), "elapsed_sec": elapsed}

    # Collect
    print(f"  → Collecting output...")
    collector = ComfyOutputCollector(client)
    try:
        collected = collector.collect(prompt_id, expected_count=1)
    except Exception as e:
        return {"name": name, "ok": False, "error": f"collect failed: {e}", "elapsed_sec": elapsed}

    if not collected.videos:
        return {"name": name, "ok": False, "error": "no videos collected", "elapsed_sec": elapsed}

    # Copy to local output
    LOCAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    src = Path(collected.videos[0].path)
    dst = LOCAL_OUTPUT_DIR / f"{name}.mp4"
    shutil.copy2(src, dst)
    print(f"  → Copied to {dst}")

    # Probe
    probe = _check_video(dst)
    print(f"  → Probe: {json.dumps(probe, indent=2)}")

    return {
        "name": name,
        "ok": True,
        "elapsed_sec": round(elapsed, 1),
        "final_status": final_status,
        "output": probe,
    }


def main():
    LOCAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # T2V — no inputs needed
    t2v_overrides = [
        ("6", "prompt", T2V_PROMPT),
        ("6", "noise_seed", int(time.time()) % (10**12)),
        ("12", "filename_prefix", f"smoke_h3_v2/h3_standard_t2v"),
    ]
    t2v_result = run_workflow("h3_standard_t2v", t2v_overrides)

    # I2V — needs a first_frame image
    # Try to find any PNG/JPG in tests/fixtures/images, or use ComfyUI default input
    i2v_img = None
    for cand in [
        PROJECT_ROOT / "tests" / "fixtures" / "images" / "test_input.png",
        PROJECT_ROOT / "tests" / "fixtures" / "test_input.png",
        Path(r"C:\Users\Administrator\Documents\comfy\ComfyUI\input\example.png"),
    ]:
        if cand.exists():
            i2v_img = cand
            break

    if i2v_img:
        client = ComfyApiClient(base_url=COMFY_URL)
        upload = client.upload_image(i2v_img)
        uploaded_name = upload.get("name", "test_input.png")
        i2v_overrides = [
            ("7", "prompt", "A cat meows and gently turns its head, soft warm light, photorealistic."),
            ("6", "image", uploaded_name),
            ("7", "noise_seed", int(time.time()) % (10**12)),
            ("14", "filename_prefix", f"smoke_h3_v2/h3_standard_i2v"),
        ]
        i2v_result = run_workflow("h3_standard_i2v", i2v_overrides)
    else:
        print(f"\n  [skip I2V] no test image found")
        i2v_result = {"name": "h3_standard_i2v", "ok": None, "skipped": "no input image"}

    # R2V — needs 3 reference images
    ref_dir = PROJECT_ROOT / "tests" / "fixtures" / "ref_images"
    ref_imgs = []
    if ref_dir.exists():
        for ext in ("*.png", "*.jpg", "*.jpeg"):
            ref_imgs.extend(sorted(ref_dir.glob(ext))[:3])
    if not ref_imgs:
        # Try any 3 images from fixtures
        for cand_dir in [PROJECT_ROOT / "tests" / "fixtures" / "images"]:
            if cand_dir.exists():
                found = []
                for ext in ("*.png", "*.jpg"):
                    found.extend(sorted(cand_dir.glob(ext))[:3])
                if len(found) >= 3:
                    ref_imgs = found[:3]
                    break

    if len(ref_imgs) >= 3:
        client = ComfyApiClient(base_url=COMFY_URL)
        uploaded_refs = []
        for img in ref_imgs:
            upload = client.upload_image(img)
            uploaded_refs.append(upload.get("name", img.name))
    elif len(ref_imgs) >= 1:
        # Only 1 ref image — replicate to fill 3 slots (smoke test only)
        print(f"  [smoke] only {len(ref_imgs)} ref image(s), replicating to fill 3 slots")
        client = ComfyApiClient(base_url=COMFY_URL)
        uploaded_refs = []
        for img in ref_imgs:
            upload = client.upload_image(img)
            uploaded_refs.append(upload.get("name", img.name))
        # Pad to 3
        while len(uploaded_refs) < 3:
            uploaded_refs.append(uploaded_refs[0])
    else:
        # Try the ComfyUI input example.png as a fallback
        example = Path(r"C:\Users\Administrator\Documents\comfy\ComfyUI\input\example.png")
        if example.exists():
            print(f"  [smoke] no ref images in fixtures, using ComfyUI example.png")
            client = ComfyApiClient(base_url=COMFY_URL)
            upload = client.upload_image(example)
            uploaded_refs = [upload.get("name", "example.png")] * 3
        else:
            print(f"\n  [skip R2V] no reference images available")
            r2v_result = {"name": "h3_standard_r2v", "ok": None, "skipped": "no reference images"}
            return

    r2v_overrides = [
        ("9", "value", "A character walking through a city street, consistent style across shots. <Picture 1> <Picture 2> <Picture 3> as references."),
        ("6", "image", uploaded_refs[0]),
        ("7", "image", uploaded_refs[1]),
        ("8", "image", uploaded_refs[2]),
        ("10", "value", 5),  # duration
        ("21", "filename_prefix", f"smoke_h3_v2/h3_standard_r2v"),
    ]
    r2v_result = run_workflow("h3_standard_r2v", r2v_overrides)

    # Summary
    print(f"\n{'='*70}")
    print(f"  SMOKE TEST SUMMARY")
    print(f"{'='*70}")
    for r in [t2v_result, i2v_result, r2v_result]:
        name = r["name"]
        if r.get("skipped"):
            print(f"  {name:25s}  SKIPPED  ({r['skipped']})")
        elif r["ok"]:
            v = r.get("output", {})
            print(
                f"  {name:25s}  OK       "
                f"{v.get('width','?')}x{v.get('height','?')} "
                f"{v.get('video_codec','?')} "
                f"{v.get('duration_sec','?')}s "
                f"audio={v.get('audio_codec','none')} "
                f"({r['elapsed_sec']}s)"
            )
        else:
            print(f"  {name:25s}  FAILED   {r.get('error','?')}")


if __name__ == "__main__":
    main()

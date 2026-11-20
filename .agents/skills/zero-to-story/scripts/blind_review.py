"""Observe one local film with a fresh, fixed MiMo request; never accept it."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = SKILL_ROOT / "assets" / "blind_review_prompt.txt"
HELPER_PATH = SKILL_ROOT.parent / "mimo-video-understanding" / "scripts" / "mimo_video.py"
ENDPOINT = "https://api.xiaomimimo.com/v1/chat/completions"


def load_helper():
    spec = importlib.util.spec_from_file_location("story_mimo_observer", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Media observer helper unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def observe(
    video: Path,
    output: Path,
    *,
    prepare_only: bool = False,
    model: str = "mimo-v2.6-pro",
    fps: float = 2.0,
    max_tokens: int = 2000,
) -> dict:
    helper = load_helper()
    if model not in helper.CURRENT_MODELS or not 0.1 <= fps <= 10 or max_tokens <= 0:
        raise ValueError("Invalid observation model or sampling options")
    source = video.resolve(strict=True)
    helper.get_mime_type(str(source), "video")
    size = source.stat().st_size
    if not size or 4 * ((size + 2) // 3) > helper.BASE64_LIMIT_CHARS:
        raise ValueError("Media is empty or exceeds the existing observer input limit")
    destination = output.resolve()
    if destination == source:
        raise ValueError("Report cannot overwrite media")
    # Reserve a unique report before any network work. Existing observations are immutable.
    destination.parent.mkdir(parents=True, exist_ok=True)
    prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError("Neutral observation prompt is empty")
    report = {
        "schema": "story.blind-observation.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "status": "preparing",
        "source_path": str(source),
        "endpoint": ENDPOINT,
        "model": model,
        "fps": fps,
        "media_resolution": "default",
        "max_tokens": max_tokens,
        "prompt": prompt,
        "context": "single media snapshot and neutral prompt; no history or file tools",
        "limitations": [
            "Model observation is not human audiovisual acceptance or audience research.",
            "Sampling and audio coverage require assessment; no full-motion guarantee.",
        ],
    }
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)

    def save() -> None:
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    try:
        # Read a stable copy; its neutral filename/path never enters the remote prompt.
        with tempfile.TemporaryDirectory(prefix="story-observation-") as temporary:
            snapshot = Path(temporary) / ("media" + source.suffix.lower())
            before = digest(source)
            shutil.copyfile(source, snapshot)
            snapshot_hash = digest(snapshot)
            if snapshot_hash != before or digest(source) != before:
                raise ValueError("Media changed while preparing the observation")
            report["source_sha256"] = snapshot_hash
            report["source_bytes"] = snapshot.stat().st_size
            report["status"] = "prepared" if prepare_only else "requesting"
            save()
            if prepare_only:
                return report
            result = helper.analyze_video(
                str(snapshot), prompt=prompt, fps=fps, media_resolution="default",
                max_tokens=max_tokens, model=model, base_url=ENDPOINT, thinking="disabled",
            )
            report["observation"] = result
            report["status"] = "observed"
            report["completed_at"] = datetime.now(UTC).isoformat()
            report["source_still_matches"] = source.is_file() and digest(source) == snapshot_hash
            save()
            return report
    except Exception as exc:
        report["status"] = "failed"
        # Do not persist provider bodies, which could contain request data or credentials.
        report["error_type"] = type(exc).__name__
        report["note"] = "No acceptance decision; inspect this attempt before any new request."
        save()
        raise RuntimeError(f"Observation failed ({type(exc).__name__}); see report") from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New report path; never overwritten")
    parser.add_argument("--prepare-only", action="store_true", help="No network request")
    parser.add_argument("--model", choices=("mimo-v2.6-pro", "mimo-v2.6-flash"), default="mimo-v2.6-pro")
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--max-tokens", type=int, default=2000)
    args = parser.parse_args()
    try:
        report = observe(args.video, args.output, prepare_only=args.prepare_only,
                         model=args.model, fps=args.fps, max_tokens=args.max_tokens)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"{exc}\n")
    print(f"{report['status']}: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

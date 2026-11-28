"""Observe one local media file with a fresh, fixed MiMo request; never accept it."""

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
AD_ASSETS = SKILL_ROOT.parent / "advertising-creator" / "assets"
MUSIC_ASSETS = SKILL_ROOT.parent / "music-video-creator" / "assets"
PROFILES = {
    "story": ("video", SKILL_ROOT / "assets" / "blind_review_prompt.txt"),
    "ad": ("video", AD_ASSETS / "ad_blind_review_prompt.txt"),
    "promo": ("video", AD_ASSETS / "promo_blind_review_prompt.txt"),
    "song": ("audio", MUSIC_ASSETS / "song_blind_review_prompt.txt"),
    "instrumental": ("audio", MUSIC_ASSETS / "instrumental_blind_review_prompt.txt"),
    "mv": ("video", MUSIC_ASSETS / "mv_blind_review_prompt.txt"),
}
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
    media: Path,
    output: Path,
    *,
    prepare_only: bool = False,
    profile: str = "story",
    model: str = "mimo-v2.6-pro",
    fps: float | None = None,
    max_tokens: int = 2000,
) -> dict:
    if profile not in PROFILES:
        raise ValueError("Unknown blind observation profile")
    media_type, prompt_path = PROFILES[profile]
    sampling_options = {}
    if media_type == "video":
        fps = 2.0 if fps is None else fps
        if not 0.1 <= fps <= 10:
            raise ValueError("Video fps must be in [0.1, 10]")
        sampling_options = {"fps": fps, "media_resolution": "default"}
    elif fps is not None:
        raise ValueError("--fps is a video-only option")
    helper = load_helper()
    if model not in helper.CURRENT_MODELS or max_tokens <= 0:
        raise ValueError("Invalid observation model or token limit")
    source = media.resolve(strict=True)
    helper.get_mime_type(str(source), media_type)
    size = source.stat().st_size
    if not size or 4 * ((size + 2) // 3) > helper.BASE64_LIMIT_CHARS:
        raise ValueError("Media is empty or exceeds the existing observer input limit")
    destination = output.resolve()
    if destination == source:
        raise ValueError("Report cannot overwrite media")
    # Reserve a unique report before any network work. Existing observations are immutable.
    destination.parent.mkdir(parents=True, exist_ok=True)
    prompt = prompt_path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError("Neutral observation prompt is empty")
    report = {
        "schema": "story.blind-observation.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "status": "preparing",
        "profile": profile,
        "media_type": media_type,
        "source_path": str(source),
        "endpoint": ENDPOINT,
        "model": model,
        **sampling_options,
        "max_tokens": max_tokens,
        "prompt": prompt,
        "context": "single media snapshot and neutral prompt; no history or file tools",
        "limitations": [
            "Model observation is not human audiovisual acceptance or audience research.",
            (
                "Sampling and audio coverage require assessment; no full-motion guarantee."
                if media_type == "video" else "Audio coverage and intelligibility require assessment."
            ),
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
            analyze = helper.analyze_video if media_type == "video" else helper.analyze_audio
            report["observation"] = analyze(
                str(snapshot), prompt=prompt, max_tokens=max_tokens, model=model,
                base_url=ENDPOINT, thinking="disabled", **sampling_options,
            )
            report["status"] = "observed"
            report["completed_at"] = datetime.now(UTC).isoformat()
            report["source_still_matches"] = source.is_file() and digest(source) == snapshot_hash
            save()
            return report
    except Exception as exc:
        report["status"] = "failed"
        # Do not persist provider bodies, which could contain request data or credentials.
        report["error_type"] = type(exc).__name__
        if isinstance(exc, helper.MiMoResponseError):
            report["error_category"] = exc.category
            if exc.http_status is not None:
                report["http_status"] = exc.http_status
        report["note"] = "No acceptance decision; inspect this attempt before any new request."
        save()
        raise RuntimeError(f"Observation failed ({type(exc).__name__}); see report") from None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    media = parser.add_mutually_exclusive_group(required=True)
    media.add_argument("--video", type=Path)
    media.add_argument("--audio", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="New report path; never overwritten")
    parser.add_argument("--profile", choices=PROFILES, default="story")
    parser.add_argument("--prepare-only", action="store_true", help="No network request")
    parser.add_argument("--model", choices=("mimo-v2.6-pro", "mimo-v2.6-flash"), default="mimo-v2.6-pro")
    parser.add_argument("--fps", type=float, help="Video sampling rate (default: 2)")
    parser.add_argument("--max-tokens", type=int, default=2000)
    args = parser.parse_args()
    media_type, _ = PROFILES[args.profile]
    source = args.video if media_type == "video" else args.audio
    if source is None:
        parser.error(f"profile {args.profile} requires --{media_type}")
    if args.audio is not None and args.fps is not None:
        parser.error("--fps is a video-only option")
    try:
        report = observe(
            source, args.output, prepare_only=args.prepare_only, profile=args.profile,
            model=args.model, fps=args.fps, max_tokens=args.max_tokens,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"{exc}\n")
    print(f"{report['status']}: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

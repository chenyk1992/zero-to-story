"""Build objective media evidence for reviewing one clip boundary."""

from __future__ import annotations

import hashlib
import json
import math
import pathlib
import re
import tempfile
from dataclasses import asdict, dataclass
from typing import Any

from lfo.media._ffmpeg import MediaCommandError, atomic_replace, probe, run_command

_SSIM_ALL = re.compile(r"\bAll:([0-9.]+)")


@dataclass(frozen=True)
class BoundaryEvidenceSpec:
    """Inputs and sampling policy for a single adjacent-clip review."""

    boundary_id: str
    previous_path: str
    next_path: str
    output_directory: str
    previous_tail_ms: int = 2_000
    next_head_ms: int = 3_000
    contact_sheet_fps: float = 4.0
    previous_source_in_ms: int = 0
    previous_source_out_ms: int | None = None
    next_source_in_ms: int = 0
    next_source_out_ms: int | None = None

    def validate(self) -> None:
        if not self.boundary_id.strip():
            raise ValueError("boundary_id must be non-empty")
        if not str(self.previous_path).strip() or not str(self.next_path).strip():
            raise ValueError("Boundary source paths must be non-empty")
        if not str(self.output_directory).strip():
            raise ValueError("output_directory must be non-empty")
        if self.previous_tail_ms <= 0 or self.next_head_ms <= 0:
            raise ValueError("Boundary preview durations must be positive")
        if not 0 < self.contact_sheet_fps <= 12:
            raise ValueError("contact_sheet_fps must be in (0, 12]")
        for label, source_in, source_out in (
            ("previous", self.previous_source_in_ms, self.previous_source_out_ms),
            ("next", self.next_source_in_ms, self.next_source_out_ms),
        ):
            if source_in < 0:
                raise ValueError(f"{label}_source_in_ms must be >= 0")
            if source_out is not None and source_out <= source_in:
                raise ValueError(f"{label}_source_out_ms must be greater than source_in_ms")


@dataclass(frozen=True)
class BoundaryEvidence:
    """Paths and objective measurements created for director review."""

    boundary_id: str
    previous_tail_frame: str
    next_head_frame: str
    preview: str
    contact_sheet: str
    metrics: str
    previous_tail_start_ms: int
    previous_tail_end_ms: int
    next_head_start_ms: int
    next_head_end_ms: int
    frame_ssim: float | None
    preview_has_audio: bool


class BoundaryEvidenceBuilder:
    """Create a compact evidence package without making a semantic verdict."""

    def build(self, spec: BoundaryEvidenceSpec) -> BoundaryEvidence:
        spec.validate()
        previous = pathlib.Path(spec.previous_path).resolve(strict=True)
        following = pathlib.Path(spec.next_path).resolve(strict=True)
        previous_probe = probe(previous)
        next_probe = probe(following)
        self._require_video(previous, previous_probe)
        self._require_video(following, next_probe)

        previous_duration = int(previous_probe["duration_ms"])
        next_duration = int(next_probe["duration_ms"])
        previous_source_out = (
            spec.previous_source_out_ms
            if spec.previous_source_out_ms is not None
            else previous_duration
        )
        next_source_out = (
            spec.next_source_out_ms if spec.next_source_out_ms is not None else next_duration
        )
        if previous_source_out > previous_duration or spec.previous_source_in_ms >= previous_source_out:
            raise ValueError("Previous source range exceeds media duration")
        if next_source_out > next_duration or spec.next_source_in_ms >= next_source_out:
            raise ValueError("Next source range exceeds media duration")
        previous_tail_start = max(
            spec.previous_source_in_ms,
            previous_source_out - spec.previous_tail_ms,
        )
        next_head_end = min(next_source_out, spec.next_source_in_ms + spec.next_head_ms)
        previous_tail_ms = previous_source_out - previous_tail_start
        next_head_ms = next_head_end - spec.next_source_in_ms
        if previous_tail_ms <= 0 or next_head_ms <= 0:
            raise ValueError("Both boundary sources must have a positive duration")

        output = pathlib.Path(spec.output_directory).resolve(strict=False)
        if output.exists() and not output.is_dir():
            raise ValueError(f"output_directory is not a directory: {output}")
        output.mkdir(parents=True, exist_ok=True)
        tail_frame = output / "previous-tail-frame.png"
        head_frame = output / "next-head-frame.png"
        preview = output / "preview.mp4"
        contact_sheet = output / "contact-sheet.jpg"
        metrics_path = output / "metrics.json"

        with tempfile.TemporaryDirectory(prefix=".boundary-", dir=output) as temporary:
            temp = pathlib.Path(temporary)
            temp_tail = temp / tail_frame.name
            temp_head = temp / head_frame.name
            temp_preview = temp / preview.name
            temp_sheet = temp / contact_sheet.name

            self._extract_boundary_frames(
                previous,
                following,
                temp_tail,
                temp_head,
                previous_tail_start_ms=previous_tail_start,
                previous_tail_end_ms=previous_source_out,
                next_head_start_ms=spec.next_source_in_ms,
                next_head_end_ms=next_head_end,
            )
            previous_has_audio = bool(previous_probe.get("has_audio"))
            next_has_audio = bool(next_probe.get("has_audio"))
            preview_has_audio = previous_has_audio or next_has_audio
            self._build_preview(
                previous=previous,
                following=following,
                output=temp_preview,
                previous_probe=previous_probe,
                previous_tail_ms=previous_tail_ms,
                next_head_ms=next_head_ms,
                previous_tail_start_ms=previous_tail_start,
                previous_tail_end_ms=previous_source_out,
                next_head_start_ms=spec.next_source_in_ms,
                next_head_end_ms=next_head_end,
                include_audio=preview_has_audio,
                previous_has_audio=previous_has_audio,
                next_has_audio=next_has_audio,
            )
            self._build_contact_sheet(
                temp_preview,
                temp_sheet,
                duration_ms=previous_tail_ms + next_head_ms,
                fps=spec.contact_sheet_fps,
            )
            frame_ssim = self._measure_frame_ssim(
                temp_tail,
                temp_head,
                width=int(previous_probe["width"]),
                height=int(previous_probe["height"]),
            )

            atomic_replace(temp_tail, tail_frame)
            atomic_replace(temp_head, head_frame)
            atomic_replace(temp_preview, preview)
            atomic_replace(temp_sheet, contact_sheet)

        metrics: dict[str, Any] = {
            "version": "lfo.boundary-evidence.v1",
            "boundary_id": spec.boundary_id,
            "sources": {
                "previous": self._source_metadata(previous, previous_probe),
                "next": self._source_metadata(following, next_probe),
            },
            "window": {
                "previous_source_in_ms": spec.previous_source_in_ms,
                "previous_source_out_ms": previous_source_out,
                "previous_tail_start_ms": previous_tail_start,
                "previous_tail_end_ms": previous_source_out,
                "previous_tail_duration_ms": previous_tail_ms,
                "next_source_in_ms": spec.next_source_in_ms,
                "next_source_out_ms": next_source_out,
                "next_head_start_ms": spec.next_source_in_ms,
                "next_head_end_ms": next_head_end,
                "next_head_duration_ms": next_head_ms,
            },
            "measurements": {
                "frame_ssim": frame_ssim,
                "exact_frame_candidate": frame_ssim is not None and frame_ssim >= 0.98,
                "preview_has_audio": preview_has_audio,
            },
            "artifacts": {
                "previous_tail_frame": str(tail_frame),
                "next_head_frame": str(head_frame),
                "preview": str(preview),
                "contact_sheet": str(contact_sheet),
            },
        }
        self._write_json_atomic(metrics_path, metrics)
        return BoundaryEvidence(
            boundary_id=spec.boundary_id,
            previous_tail_frame=str(tail_frame),
            next_head_frame=str(head_frame),
            preview=str(preview),
            contact_sheet=str(contact_sheet),
            metrics=str(metrics_path),
            previous_tail_start_ms=previous_tail_start,
            previous_tail_end_ms=previous_source_out,
            next_head_start_ms=spec.next_source_in_ms,
            next_head_end_ms=next_head_end,
            frame_ssim=frame_ssim,
            preview_has_audio=preview_has_audio,
        )

    @staticmethod
    def _require_video(path: pathlib.Path, metadata: dict[str, Any]) -> None:
        if metadata.get("width") is None or metadata.get("height") is None:
            raise ValueError(f"Boundary source has no video stream: {path}")

    @staticmethod
    def _extract_boundary_frames(
        previous: pathlib.Path,
        following: pathlib.Path,
        tail_frame: pathlib.Path,
        head_frame: pathlib.Path,
        *,
        previous_tail_start_ms: int,
        previous_tail_end_ms: int,
        next_head_start_ms: int,
        next_head_end_ms: int,
    ) -> None:
        run_command(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(previous),
                "-vf",
                (
                    f"trim=start={previous_tail_start_ms / 1000:.3f}:"
                    f"end={previous_tail_end_ms / 1000:.3f},"
                    "setpts=PTS-STARTPTS,reverse"
                ),
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                str(tail_frame),
            ]
        )
        run_command(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(following),
                "-vf",
                (
                    f"trim=start={next_head_start_ms / 1000:.3f}:"
                    f"end={next_head_end_ms / 1000:.3f},"
                    "setpts=PTS-STARTPTS"
                ),
                "-map",
                "0:v:0",
                "-frames:v",
                "1",
                str(head_frame),
            ]
        )

    @staticmethod
    def _build_preview(
        *,
        previous: pathlib.Path,
        following: pathlib.Path,
        output: pathlib.Path,
        previous_probe: dict[str, Any],
        previous_tail_ms: int,
        next_head_ms: int,
        previous_tail_start_ms: int,
        previous_tail_end_ms: int,
        next_head_start_ms: int,
        next_head_end_ms: int,
        include_audio: bool,
        previous_has_audio: bool,
        next_has_audio: bool,
    ) -> None:
        width = int(previous_probe["width"])
        height = int(previous_probe["height"])
        fps = float(previous_probe.get("fps") or 24.0)
        fit = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,fps={fps},format=yuv420p"
        )
        video_filters = (
            f"[0:v]trim=start={previous_tail_start_ms / 1000:.3f}:"
            f"end={previous_tail_end_ms / 1000:.3f},setpts=PTS-STARTPTS,{fit}[v0];"
            f"[1:v]trim=start={next_head_start_ms / 1000:.3f}:"
            f"end={next_head_end_ms / 1000:.3f},setpts=PTS-STARTPTS,{fit}[v1]"
        )
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(previous),
            "-i",
            str(following),
        ]
        if include_audio:
            previous_audio = (
                f"[0:a]atrim=start={previous_tail_start_ms / 1000:.3f}:"
                f"end={previous_tail_end_ms / 1000:.3f},"
                "asetpts=PTS-STARTPTS,aresample=48000,"
                "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a0]"
                if previous_has_audio
                else (
                    f"anullsrc=r=48000:cl=stereo,atrim=duration={previous_tail_ms / 1000:.3f},"
                    "asetpts=PTS-STARTPTS[a0]"
                )
            )
            next_audio = (
                f"[1:a]atrim=start={next_head_start_ms / 1000:.3f}:"
                f"end={next_head_end_ms / 1000:.3f},"
                "asetpts=PTS-STARTPTS,aresample=48000,"
                "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a1]"
                if next_has_audio
                else (
                    f"anullsrc=r=48000:cl=stereo,atrim=duration={next_head_ms / 1000:.3f},"
                    "asetpts=PTS-STARTPTS[a1]"
                )
            )
            filters = (
                f"{video_filters};"
                f"{previous_audio};{next_audio};"
                "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"
            )
            command.extend(
                [
                    "-filter_complex",
                    filters,
                    "-map",
                    "[v]",
                    "-map",
                    "[a]",
                    "-c:a",
                    "aac",
                ]
            )
        else:
            filters = f"{video_filters};[v0][v1]concat=n=2:v=1:a=0[v]"
            command.extend(["-filter_complex", filters, "-map", "[v]", "-an"])
        command.extend(["-c:v", "libx264", "-crf", "18", "-movflags", "+faststart", str(output)])
        run_command(command)

    @staticmethod
    def _build_contact_sheet(
        preview: pathlib.Path,
        output: pathlib.Path,
        *,
        duration_ms: int,
        fps: float,
    ) -> None:
        frame_count = max(1, math.ceil(duration_ms / 1000 * fps))
        columns = min(5, frame_count)
        rows = math.ceil(frame_count / columns)
        run_command(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(preview),
                "-vf",
                f"fps={fps},scale=240:-2,tile={columns}x{rows}:padding=2:margin=2",
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(output),
            ]
        )

    @staticmethod
    def _measure_frame_ssim(
        tail_frame: pathlib.Path,
        head_frame: pathlib.Path,
        *,
        width: int,
        height: int,
    ) -> float | None:
        fit = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p"
        )
        try:
            result = run_command(
                [
                    "ffmpeg",
                    "-i",
                    str(tail_frame),
                    "-i",
                    str(head_frame),
                    "-filter_complex",
                    f"[0:v]{fit}[a];[1:v]{fit}[b];[a][b]ssim",
                    "-f",
                    "null",
                    "-",
                ]
            )
        except MediaCommandError:
            return None
        match = _SSIM_ALL.search(result.stderr or "")
        return float(match.group(1)) if match else None

    @staticmethod
    def _source_metadata(path: pathlib.Path, metadata: dict[str, Any]) -> dict[str, Any]:
        return {
            "path": str(path),
            "sha256": BoundaryEvidenceBuilder._sha256(path),
            **metadata,
        }

    @staticmethod
    def _sha256(path: pathlib.Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _write_json_atomic(path: pathlib.Path, payload: dict[str, Any]) -> None:
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(path)


def evidence_to_dict(evidence: BoundaryEvidence) -> dict[str, Any]:
    """Return a JSON-ready artifact summary for runtime handlers."""

    return asdict(evidence)

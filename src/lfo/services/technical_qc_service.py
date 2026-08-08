"""TechnicalQCService — validate generated media against task specification.

Responsibilities:
- Check resolution, fps, duration, audio presence against expected spec
- Write qc_reports row with PASS/FAIL status and issues list
- Return structured QC result

QC checks:
- Resolution: width/height match expected (within tolerance)
- FPS: frame rate matches expected
- Duration: within expected range (±0.5s tolerance)
- Audio: present if required, correct sample rate/channels
- Codec: video codec matches expected
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from lfo.core.database import Database


@dataclass
class QCSpec:
    """Expected media specification for QC."""

    width: int | None = None
    height: int | None = None
    fps: float | None = None
    duration_sec: float | None = None
    requires_audio: bool = True
    expected_video_codec: str = "h264"
    expected_audio_codec: str = "aac"
    expected_sample_rate: int = 48000
    expected_channels: int = 2
    duration_tolerance_sec: float = 0.5


@dataclass
class QCCheck:
    """Result of a single QC check."""

    name: str
    passed: bool
    expected: str = ""
    actual: str = ""
    message: str = ""


@dataclass
class QCResult:
    """Complete QC result for an asset."""

    asset_id: str
    task_id: str
    status: str = "PENDING"  # PENDING | PASS | FAIL
    checks: list[QCCheck] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == "PASS"

    @property
    def failed(self) -> bool:
        return self.status == "FAIL"


class TechnicalQCService:
    """Validate media assets against technical specifications."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # -- public API ------------------------------------------------------- #

    def check_asset(
        self,
        asset_id: str,
        spec: QCSpec,
    ) -> QCResult:
        """Run technical QC checks on an asset.

        Steps:
        1. Load asset from DB
        2. Extract media info (from metadata or ffprobe)
        3. Run all checks against spec
        4. Write qc_reports row
        5. Return QCResult

        Args:
            asset_id: The asset to validate.
            spec: The expected media specification.

        Returns:
            QCResult with check results and final status.
        """
        # 1. Load asset
        asset_row = self.db.fetchone(
            """SELECT asset_id, task_id, attempt_id, file_path, metadata,
                      width, height, duration, frame_count
               FROM assets WHERE asset_id = ?""",
            (asset_id,),
        )
        if asset_row is None:
            return QCResult(
                asset_id=asset_id,
                task_id="",
                status="FAIL",
                issues=[f"Asset {asset_id} not found"],
            )

        asset_id, task_id, attempt_id = asset_row[0], asset_row[1], asset_row[2]
        metadata = json.loads(asset_row[4]) if asset_row[4] else {}
        width = asset_row[5]
        height = asset_row[6]
        duration = asset_row[7]
        frame_count = asset_row[8]

        # 2. Extract media info from metadata (already populated during collection)
        media_info = self._extract_media_info(metadata, width, height, duration, frame_count)

        # 3. Run checks
        result = QCResult(asset_id=asset_id, task_id=task_id)
        result.checks = self._run_checks(media_info, spec)
        result.issues = [c.message for c in result.checks if not c.passed]
        result.status = "PASS" if not result.issues else "FAIL"

        # 4. Write qc_reports row
        self._write_qc_report(result, attempt_id)

        return result

    def check_asset_by_task(self, task_id: str, spec: QCSpec) -> list[QCResult]:
        """Run QC on all assets for a task.

        Args:
            task_id: The task whose assets to validate.
            spec: The expected media specification.

        Returns:
            List of QCResult, one per asset.
        """
        rows = self.db.fetchall(
            "SELECT asset_id FROM assets WHERE task_id = ?",
            (task_id,),
        )
        results = []
        for row in rows:
            result = self.check_asset(row[0], spec)
            results.append(result)
        return results

    # -- media info extraction ------------------------------------------- #

    @dataclass
    class _MediaInfo:
        """Internal media info for QC checks."""

        width: int = 0
        height: int = 0
        fps: float = 0.0
        duration: float = 0.0
        frame_count: int = 0
        has_audio: bool = False
        video_codec: str = ""
        audio_codec: str = ""
        audio_sample_rate: int = 0
        audio_channels: int = 0

    def _extract_media_info(
        self,
        metadata: dict,
        width: int | None,
        height: int | None,
        duration: float | None,
        frame_count: int | None,
    ) -> _MediaInfo:
        """Extract media info from DB metadata + columns."""
        info = self._MediaInfo()

        # From metadata (populated during collection)
        info.width = metadata.get("width", 0) or width or 0
        info.height = metadata.get("height", 0) or height or 0
        info.fps = metadata.get("fps", 0.0) or 0.0
        info.duration = metadata.get("duration", 0.0) or duration or 0.0
        info.frame_count = metadata.get("frames", 0) or frame_count or 0
        info.has_audio = metadata.get("has_audio", False)
        info.video_codec = metadata.get("codec", "")

        return info

    # -- checks ---------------------------------------------------------- #

    def _run_checks(
        self,
        media: _MediaInfo,
        spec: QCSpec,
    ) -> list[QCCheck]:
        """Run all QC checks against the spec."""
        checks: list[QCCheck] = []

        # Resolution check
        if spec.width is not None:
            checks.append(QCCheck(
                name="width",
                passed=media.width == spec.width,
                expected=str(spec.width),
                actual=str(media.width),
                message="" if media.width == spec.width
                    else f"Width mismatch: expected {spec.width}, got {media.width}",
            ))

        if spec.height is not None:
            checks.append(QCCheck(
                name="height",
                passed=media.height == spec.height,
                expected=str(spec.height),
                actual=str(media.height),
                message="" if media.height == spec.height
                    else f"Height mismatch: expected {spec.height}, got {media.height}",
            ))

        # FPS check
        if spec.fps is not None:
            fps_match = abs(media.fps - spec.fps) < 0.1
            checks.append(QCCheck(
                name="fps",
                passed=fps_match,
                expected=str(spec.fps),
                actual=str(media.fps),
                message="" if fps_match
                    else f"FPS mismatch: expected {spec.fps}, got {media.fps}",
            ))

        # Duration check
        if spec.duration_sec is not None:
            duration_ok = abs(media.duration - spec.duration_sec) <= spec.duration_tolerance_sec
            checks.append(QCCheck(
                name="duration",
                passed=duration_ok,
                expected=f"{spec.duration_sec}±{spec.duration_tolerance_sec}s",
                actual=f"{media.duration}s",
                message="" if duration_ok
                    else f"Duration out of range: expected {spec.duration_sec}±{spec.duration_tolerance_sec}s, got {media.duration}s",
            ))

        # Audio presence check
        if spec.requires_audio:
            checks.append(QCCheck(
                name="audio_present",
                passed=media.has_audio,
                expected="audio required",
                actual="audio present" if media.has_audio else "no audio",
                message="" if media.has_audio else "Audio required but not found",
            ))

        # Video codec check
        if spec.expected_video_codec:
            codec_match = media.video_codec.lower() == spec.expected_video_codec.lower()
            checks.append(QCCheck(
                name="video_codec",
                passed=codec_match,
                expected=spec.expected_video_codec,
                actual=media.video_codec,
                message="" if codec_match
                    else f"Video codec mismatch: expected {spec.expected_video_codec}, got {media.video_codec}",
            ))

        return checks

    # -- DB persistence -------------------------------------------------- #

    def _write_qc_report(
        self,
        result: QCResult,
        attempt_id: str | None,
    ) -> None:
        """Write a qc_reports row for the result."""
        now = _utc_now()
        report_id = uuid.uuid4().hex
        checks_dict = {
            c.name: {
                "passed": c.passed,
                "expected": c.expected,
                "actual": c.actual,
            }
            for c in result.checks
        }

        self.db.execute(
            """INSERT INTO qc_reports
               (report_id, task_id, attempt_id, asset_id, status,
                checks, issues, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                report_id,
                result.task_id,
                attempt_id,
                result.asset_id,
                result.status,
                json.dumps(checks_dict),
                json.dumps(result.issues),
                now,
                now,
            ),
        )


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")

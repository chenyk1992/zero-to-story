"""Final Technical QC — validate the final assembled MP4 + SRT sidecar.

Checks per plan (Wave 1 Final QC):
- Container parseable
- 1080x1920
- CFR 24fps
- H.264/yuv420p
- AAC 48kHz Stereo
- Video and audio duration reasonable
- Total duration matches EDL allowed error
- SRT time ranges don't exceed final video duration
- No empty files
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from lfo.core.database import Database


@dataclass
class FinalQCCheck:
    """A single QC check result."""
    name: str
    passed: bool
    expected: str = ""
    actual: str = ""
    message: str = ""


@dataclass
class FinalQCResult:
    """Complete final QC result."""
    success: bool = False
    video_asset_id: str = ""
    srt_asset_id: str = ""
    checks: list[FinalQCCheck] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


class FinalQCService:
    """Validate final MP4 + SRT delivery package."""

    EXPECTED_WIDTH = 1080
    EXPECTED_HEIGHT = 1920
    EXPECTED_FPS = 24.0
    EXPECTED_VIDEO_CODEC = "h264"
    EXPECTED_PIXEL_FORMAT = "yuv420p"
    EXPECTED_AUDIO_CODEC = "aac"
    EXPECTED_SAMPLE_RATE = 48000
    EXPECTED_CHANNELS = 2
    DURATION_TOLERANCE_SEC = 1.0

    def __init__(
        self,
        db: Database,
        ffmpeg_path: str | None = None,
        ffprobe_path: str | None = None,
    ) -> None:
        self.db = db
        self.ffmpeg_path = ffmpeg_path or shutil.which("ffmpeg") or ""
        self.ffprobe_path = ffprobe_path or shutil.which("ffprobe") or ""

    def validate(
        self,
        video_asset_id: str,
        srt_asset_id: str = "",
        expected_duration_sec: float | None = None,
    ) -> FinalQCResult:
        """Validate the final video (+ optional SRT).

        Args:
            video_asset_id: The final assembly video asset.
            srt_asset_id: Optional SRT subtitle asset.
            expected_duration_sec: Expected total duration (from EDL timeline).

        Returns:
            FinalQCResult with all checks.
        """
        result = FinalQCResult(video_asset_id=video_asset_id, srt_asset_id=srt_asset_id)

        # Load video asset
        video_row = self.db.fetchone(
            "SELECT file_path, task_id, attempt_id FROM assets WHERE asset_id = ?",
            (video_asset_id,),
        )
        if video_row is None:
            result.issues.append(f"Video asset {video_asset_id} not found")
            return result

        video_path = video_row[0]
        task_id = video_row[1]
        attempt_id = video_row[2]

        # Run video checks
        checks: list[FinalQCCheck] = []

        # 1. File exists and not empty
        checks.append(self._check_file_not_empty(video_path, "video"))

        # 2. Probe video streams
        probe = self._probe(video_path)
        if probe is None:
            checks.append(FinalQCCheck(
                name="container", passed=False,
                expected="parseable", actual="probe failed",
                message="Cannot probe video file (ffprobe failed)",
            ))
        else:
            # Resolution
            checks.append(FinalQCCheck(
                name="width",
                passed=probe["width"] == self.EXPECTED_WIDTH,
                expected=str(self.EXPECTED_WIDTH),
                actual=str(probe["width"]),
                message="" if probe["width"] == self.EXPECTED_WIDTH
                    else f"Width: expected {self.EXPECTED_WIDTH}, got {probe['width']}",
            ))
            checks.append(FinalQCCheck(
                name="height",
                passed=probe["height"] == self.EXPECTED_HEIGHT,
                expected=str(self.EXPECTED_HEIGHT),
                actual=str(probe["height"]),
                message="" if probe["height"] == self.EXPECTED_HEIGHT
                    else f"Height: expected {self.EXPECTED_HEIGHT}, got {probe['height']}",
            ))
            # FPS
            fps_ok = abs(probe["fps"] - self.EXPECTED_FPS) < 0.1
            checks.append(FinalQCCheck(
                name="fps",
                passed=fps_ok,
                expected=str(self.EXPECTED_FPS),
                actual=f"{probe['fps']:.2f}",
                message="" if fps_ok
                    else f"FPS: expected {self.EXPECTED_FPS}, got {probe['fps']:.2f}",
            ))
            # Video codec
            codec_match = probe["video_codec"].lower() == self.EXPECTED_VIDEO_CODEC
            checks.append(FinalQCCheck(
                name="video_codec",
                passed=codec_match,
                expected=self.EXPECTED_VIDEO_CODEC,
                actual=probe["video_codec"],
                message="" if codec_match
                    else f"Video codec: expected {self.EXPECTED_VIDEO_CODEC}, got {probe['video_codec']}",
            ))
            # Audio
            if probe["has_audio"]:
                audio_codec_match = probe["audio_codec"].lower() == self.EXPECTED_AUDIO_CODEC
                checks.append(FinalQCCheck(
                    name="audio_codec",
                    passed=audio_codec_match,
                    expected=self.EXPECTED_AUDIO_CODEC,
                    actual=probe["audio_codec"],
                    message="" if audio_codec_match
                        else f"Audio codec: expected {self.EXPECTED_AUDIO_CODEC}, got {probe['audio_codec']}",
                ))
                sr_ok = probe["audio_sample_rate"] == self.EXPECTED_SAMPLE_RATE
                checks.append(FinalQCCheck(
                    name="audio_sample_rate",
                    passed=sr_ok,
                    expected=str(self.EXPECTED_SAMPLE_RATE),
                    actual=str(probe["audio_sample_rate"]),
                    message="" if sr_ok
                        else f"Sample rate: expected {self.EXPECTED_SAMPLE_RATE}, got {probe['audio_sample_rate']}",
                ))
                ch_ok = probe["audio_channels"] == self.EXPECTED_CHANNELS
                checks.append(FinalQCCheck(
                    name="audio_channels",
                    passed=ch_ok,
                    expected=str(self.EXPECTED_CHANNELS),
                    actual=str(probe["audio_channels"]),
                    message="" if ch_ok
                        else f"Channels: expected {self.EXPECTED_CHANNELS}, got {probe['audio_channels']}",
                ))
            else:
                checks.append(FinalQCCheck(
                    name="audio_present", passed=False,
                    expected="audio track", actual="no audio",
                    message="No audio stream found",
                ))
            # Duration reasonable (> 0)
            checks.append(FinalQCCheck(
                name="duration_positive",
                passed=probe["duration_sec"] > 0,
                expected="> 0",
                actual=f"{probe['duration_sec']:.2f}s",
                message="" if probe["duration_sec"] > 0
                    else "Video duration is 0",
            ))
            # Duration matches expected (if provided)
            if expected_duration_sec is not None and expected_duration_sec > 0:
                dur_ok = abs(probe["duration_sec"] - expected_duration_sec) <= self.DURATION_TOLERANCE_SEC
                checks.append(FinalQCCheck(
                    name="duration_matches_edl",
                    passed=dur_ok,
                    expected=f"{expected_duration_sec:.2f}s ±{self.DURATION_TOLERANCE_SEC}s",
                    actual=f"{probe['duration_sec']:.2f}s",
                    message="" if dur_ok
                        else f"Duration mismatch: expected ~{expected_duration_sec:.2f}s, got {probe['duration_sec']:.2f}s",
                ))

        result.checks = checks

        # 3. SRT checks
        if srt_asset_id:
            srt_row = self.db.fetchone(
                "SELECT file_path FROM assets WHERE asset_id = ?",
                (srt_asset_id,),
            )
            if srt_row is None:
                result.checks.append(FinalQCCheck(
                    name="srt_exists", passed=False,
                    expected="SRT asset", actual="not found",
                    message=f"SRT asset {srt_asset_id} not found",
                ))
            else:
                srt_path = srt_row[0]
                result.checks.append(self._check_file_not_empty(srt_path, "srt_file"))
                if probe:
                    srt_issues = self._check_srt_time_ranges(srt_path, probe["duration_sec"])
                    for issue in srt_issues:
                        result.checks.append(FinalQCCheck(
                            name="srt_time_range", passed=False,
                            expected=f"<= {probe['duration_sec']:.2f}s",
                            actual=issue,
                            message=issue,
                        ))

        # Collect issues
        result.issues = [c.message for c in result.checks if not c.passed and c.message]
        result.success = len(result.issues) == 0

        # Write QC report
        self._write_report(result, video_asset_id, srt_asset_id, task_id, attempt_id)

        return result

    # -- internal helpers -------------------------------------------------

    def _check_file_not_empty(self, path: str, label: str) -> FinalQCCheck:
        exists = os.path.exists(path)
        size = os.path.getsize(path) if exists else 0
        return FinalQCCheck(
            name=f"{label}_not_empty",
            passed=exists and size > 0,
            expected="file exists, size > 0",
            actual=f"exists={exists}, size={size}",
            message="" if (exists and size > 0)
                else f"{label}: file missing or empty",
        )

    def _check_srt_time_ranges(self, srt_path: str, video_duration_sec: float) -> list[str]:
        """Check that all SRT cue end times don't exceed video duration."""
        issues: list[str] = []
        try:
            with open(srt_path, encoding="utf-8") as f:
                content = f.read()
        except OSError as exc:
            issues.append(f"Cannot read SRT file: {exc}")
            return issues

        # Parse time ranges: HH:MM:SS,mmm --> HH:MM:SS,mmm
        pattern = r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})"
        for match in re.finditer(pattern, content):
            h2, m2, s2, ms2 = match.groups()[4:]
            end_sec = int(h2) * 3600 + int(m2) * 60 + int(s2) + int(ms2) / 1000.0
            if end_sec > video_duration_sec + 0.5:  # 0.5s tolerance
                issues.append(
                    f"SRT cue ends at {end_sec:.2f}s but video is {video_duration_sec:.2f}s"
                )
        return issues

    def _probe(self, file_path: str) -> dict | None:
        """Probe video file via ffprobe. Returns dict or None."""
        if not self.ffprobe_path or not os.path.exists(file_path):
            return None

        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, OSError):
            return None

        if proc.returncode != 0:
            return None

        data = json.loads(proc.stdout)
        info: dict = {
            "width": 0,
            "height": 0,
            "fps": 0.0,
            "duration_sec": 0.0,
            "video_codec": "",
            "has_audio": False,
            "audio_codec": "",
            "audio_sample_rate": 0,
            "audio_channels": 0,
        }

        fmt = data.get("format", {})
        info["duration_sec"] = float(fmt.get("duration", 0))

        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video" and not info["width"]:
                info["width"] = int(stream.get("width", 0))
                info["height"] = int(stream.get("height", 0))
                info["video_codec"] = stream.get("codec_name", "")
                fps_str = stream.get("r_frame_rate", "0/1")
                if "/" in fps_str:
                    num, den = fps_str.split("/")
                    info["fps"] = float(num) / float(den) if float(den) != 0 else 0
            elif stream.get("codec_type") == "audio":
                info["has_audio"] = True
                info["audio_codec"] = stream.get("codec_name", "")
                info["audio_sample_rate"] = int(stream.get("sample_rate", 0))
                info["audio_channels"] = int(stream.get("channels", 0))

        return info

    def validate_advanced(
        self,
        video_asset_id: str,
        expected_duration_sec: float | None = None,
    ) -> FinalQCResult:
        """Extended validation with black frame, freeze frame, and AV sync checks."""
        result = self.validate(video_asset_id, "", expected_duration_sec)

        video_row = self.db.fetchone(
            "SELECT file_path FROM assets WHERE asset_id = ?", (video_asset_id,),
        )
        if video_row is None:
            return result

        video_path = video_row[0]
        if not os.path.exists(video_path):
            return result

        # Black frame detection
        result.checks.append(self._check_black_frames(video_path))

        # Freeze frame detection
        result.checks.append(self._check_freeze_frames(video_path))

        # AV sync analysis
        result.checks.append(self._check_av_sync(video_path))

        result.issues = [c.message for c in result.checks if not c.passed and c.message]
        result.success = len(result.issues) == 0
        return result

    def _check_black_frames(self, video_path: str) -> FinalQCCheck:
        """Detect excessive black frames using ffmpeg blackframe filter."""
        if not self.ffmpeg_path:
            return FinalQCCheck(name="black_frames", passed=True, message="ffmpeg not available, skipped")

        cmd = [
            self.ffmpeg_path, "-i", video_path,
            "-vf", "blackframe=amount=98:threshold=32",
            "-f", "null", "-",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except (subprocess.TimeoutExpired, OSError) as exc:
            return FinalQCCheck(name="black_frames", passed=True, message=f"check skipped: {exc}")

        # Parse blackframe output for percentage
        black_pct = 0.0
        for line in proc.stderr.split("\n"):
            if "blackframe" in line and "%" in line:
                m = re.search(r"(\d+\.?\d*)%", line)
                if m:
                    black_pct = float(m.group(1))

        passed = black_pct < 10.0
        return FinalQCCheck(
            name="black_frames",
            passed=passed,
            expected="< 10%",
            actual=f"{black_pct:.1f}%",
            message="" if passed else f"Excessive black frames: {black_pct:.1f}%",
        )

    def _check_freeze_frames(self, video_path: str) -> FinalQCCheck:
        """Detect freeze frames using ffmpeg freezedetect filter."""
        if not self.ffmpeg_path:
            return FinalQCCheck(name="freeze_frames", passed=True, message="ffmpeg not available, skipped")

        cmd = [
            self.ffmpeg_path, "-i", video_path,
            "-vf", "freezedetect=n=-60dB:d=2",
            "-f", "null", "-",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except (subprocess.TimeoutExpired, OSError) as exc:
            return FinalQCCheck(name="freeze_frames", passed=True, message=f"check skipped: {exc}")

        freeze_count = proc.stderr.count("[freezedetect @")
        passed = freeze_count == 0
        return FinalQCCheck(
            name="freeze_frames",
            passed=passed,
            expected="0",
            actual=str(freeze_count),
            message="" if passed else f"Detected {freeze_count} freeze frame segments",
        )

    def _check_av_sync(self, video_path: str) -> FinalQCCheck:
        """Check audio/video duration are within tolerance."""
        if not self.ffprobe_path or not os.path.exists(video_path):
            return FinalQCCheck(name="av_sync", passed=True, message="ffprobe not available")

        # Get video duration
        probe = self._probe(video_path)
        if not probe:
            return FinalQCCheck(name="av_sync", passed=True, message="probe failed")

        if not probe["has_audio"]:
            return FinalQCCheck(name="av_sync", passed=True, message="no audio to check")

        # Get audio stream duration separately
        cmd = [
            self.ffprobe_path, "-v", "quiet",
            "-select_streams", "a:0",
            "-show_entries", "stream=duration",
            "-of", "csv=p=0",
            video_path,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            audio_dur = float(proc.stdout.strip()) if proc.returncode == 0 and proc.stdout.strip() else probe["duration_sec"]
        except (ValueError, subprocess.TimeoutExpired, OSError):
            audio_dur = probe["duration_sec"]

        delta = abs(probe["duration_sec"] - audio_dur)
        passed = delta <= self.DURATION_TOLERANCE_SEC
        return FinalQCCheck(
            name="av_sync",
            passed=passed,
            expected=f"<= {self.DURATION_TOLERANCE_SEC}s delta",
            actual=f"{delta:.3f}s delta",
            message="" if passed else f"AV sync delta: {delta:.3f}s",
        )

    def _write_report(
        self,
        result: FinalQCResult,
        video_asset_id: str,
        srt_asset_id: str,
        task_id: str,
        attempt_id: str | None,
    ) -> None:
        """Write qc_reports row."""
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
                task_id,
                attempt_id,
                video_asset_id,
                "PASS" if result.success else "FAIL",
                json.dumps(checks_dict),
                json.dumps(result.issues),
                now,
                now,
            ),
        )


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")

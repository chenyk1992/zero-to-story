"""Tests for planning.duration."""
from lfo.core.workflow_registry import FrameConstraints, WorkflowManifest
from lfo.planning.duration import compute_aligned_frames
from lfo.storyboard.storyboard import Shot


class TestComputeAlignedFrames:
    def _make_manifest(self, fps=24):
        return WorkflowManifest(
            workflow_id="test",
            version="1.0.0",
            family="h3_fl2va",
            workflow_mode="t2va",
            description="test",
            source_file="test.json",
            workflow_hash="",
            frame_constraints=FrameConstraints(fps=fps),
        )

    def test_basic_5_seconds(self):
        """5s @ 24fps = 120 frames → aligned to 124."""
        manifest = self._make_manifest()
        shot = Shot(desired_duration_ms=5000)
        frames = compute_aligned_frames(shot, manifest)
        assert frames == 124

    def test_with_pre_handle(self):
        """Adding pre_handle_ms increases frame count."""
        manifest = self._make_manifest()
        shot = Shot(desired_duration_ms=4000)
        frames = compute_aligned_frames(shot, manifest, pre_handle_ms=500)
        # 4.5s * 24 = 108 → aligned to 107? No, 108 → 124 (next 17k+5)
        # Actually 108: 108 % 17 = 6, so → 124 (17*7+5=124)
        assert frames == 124

    def test_with_post_handle(self):
        """Adding post_handle_ms increases frame count."""
        manifest = self._make_manifest()
        shot = Shot(desired_duration_ms=4000)
        frames = compute_aligned_frames(shot, manifest, post_handle_ms=1000)
        # 5s * 24 = 120 → 124
        assert frames == 124

    def test_boundary_123(self):
        """123 → 124 (per spec)."""
        manifest = self._make_manifest()
        # Need: ceil(ms * 24/1000) = 123
        # ms = 123 * 1000 / 24 = 5125
        shot = Shot(desired_duration_ms=5125)
        frames = compute_aligned_frames(shot, manifest)
        assert frames == 124

    def test_boundary_124(self):
        """124 → 124 (already aligned)."""
        manifest = self._make_manifest()
        shot = Shot(desired_duration_ms=5167)  # 5167 * 24/1000 = 124.008 → ceil = 125? No
        # Let me compute: need ceil(ms * 24/1000) = 124
        # 124 * 1000 / 24 = 5166.67, so ms = 5167 → ceil(124.008) = 125
        # ms = 5166 → ceil(123.984) = 124
        shot = Shot(desired_duration_ms=5166)
        frames = compute_aligned_frames(shot, manifest)
        assert frames == 124

    def test_boundary_125(self):
        """125 → 141 (per spec)."""
        manifest = self._make_manifest()
        # Need ceil(ms * 24/1000) = 125
        # 125 * 1000 / 24 = 5208.33, ms = 5209 → ceil(125.016) = 126? No
        # ms = 5208 → ceil(124.992) = 125
        shot = Shot(desired_duration_ms=5208)
        frames = compute_aligned_frames(shot, manifest)
        assert frames == 141

    def test_align_frame_count_spec_values(self):
        """Verify the spec values for align_frame_count directly."""
        fc = FrameConstraints()
        assert fc.align_frame_count(123) == 124
        assert fc.align_frame_count(124) == 124
        assert fc.align_frame_count(125) == 141
        assert fc.align_frame_count(191) == 192
        assert fc.align_frame_count(192) == 192
        assert fc.align_frame_count(193) == 209

    def test_short_duration(self):
        """Very short shot still aligns properly."""
        manifest = self._make_manifest()
        shot = Shot(desired_duration_ms=100)
        frames = compute_aligned_frames(shot, manifest)
        # 0.1s * 24 = 2.4 → ceil = 3 → aligned to 5
        assert frames == 5

    def test_zero_duration(self):
        """Zero duration → 0 → aligned to 5."""
        manifest = self._make_manifest()
        shot = Shot(desired_duration_ms=0)
        frames = compute_aligned_frames(shot, manifest)
        assert frames == 5

    def test_different_fps(self):
        """Different FPS produces different frame count."""
        manifest = self._make_manifest(fps=30)
        shot = Shot(desired_duration_ms=5000)
        frames = compute_aligned_frames(shot, manifest)
        # 5s * 30 = 150 → 150 % 17 = 14 → 153 (17*9=153, 153%17=0 ≠ 5)
        # Actually 150: 150 % 17 = 14, need 5, so +3 → 153? No, 153 % 17 = 0
        # align_frame_count increments until n % 17 == 5
        # 150 % 17 = 14, 151 % 17 = 15, 152 % 17 = 16, 153 % 17 = 0, ..., 158 % 17 = 5
        assert frames == 158

    def test_determinism(self):
        """Same inputs → same frame count."""
        manifest = self._make_manifest()
        shot = Shot(desired_duration_ms=5000)
        f1 = compute_aligned_frames(shot, manifest)
        f2 = compute_aligned_frames(shot, manifest)
        assert f1 == f2

"""Tests for comfy.gpu_guard — VRAM gate before submitting to ComfyUI.

The guard exists to prevent OOM-driven retry loops on a single-GPU machine.
It MUST be import-safe in environments without NVIDIA drivers (CI, dev laptops).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestGpuAvailability:
    """When pynvml is missing or the GPU is not present, the guard must NOT raise."""

    def test_get_gpu_status_returns_none_when_pynvml_unavailable(self):
        """If pynvml cannot be imported, get_gpu_status() returns None gracefully."""
        from lfo.comfy.gpu_guard import get_gpu_status

        with patch.dict("sys.modules", {"pynvml": None}):
            # Simulate pynvml not installed at all
            import sys as _sys
            _sys.modules.pop("pynvml", None)

            # First, make the import inside gpu_guard fail by mocking importlib
            with patch("lfo.comfy.gpu_guard._load_pynvml", return_value=None):
                result = get_gpu_status()

        assert result is None

    def test_get_gpu_status_returns_none_when_nvml_init_fails(self):
        """If nvmlInit() raises (e.g. no NVIDIA driver), get_gpu_status() returns None."""
        from lfo.comfy.gpu_guard import get_gpu_status

        fake_pynvml = MagicMock()
        fake_pynvml.nvmlInit.side_effect = Exception("driver not loaded")
        with patch("lfo.comfy.gpu_guard._load_pynvml", return_value=fake_pynvml):
            result = get_gpu_status()

        assert result is None

    def test_get_gpu_status_returns_snapshot_when_gpu_present(self):
        """If GPU is present, return a snapshot dict with memory fields."""
        from lfo.comfy.gpu_guard import get_gpu_status

        fake_pynvml = MagicMock()
        fake_handle = MagicMock()
        fake_pynvml.nvmlInit.return_value = None
        fake_pynvml.nvmlDeviceGetCount.return_value = 1
        fake_pynvml.nvmlDeviceGetHandleByIndex.return_value = fake_handle

        # memInfo struct: (used, total) in bytes
        mem_info = MagicMock()
        mem_info.used = 4 * 1024 * 1024 * 1024   # 4 GB used
        mem_info.total = 16 * 1024 * 1024 * 1024  # 16 GB total
        fake_pynvml.nvmlDeviceGetMemoryInfo.return_value = mem_info

        with patch("lfo.comfy.gpu_guard._load_pynvml", return_value=fake_pynvml):
            result = get_gpu_status()

        assert result is not None
        assert result["used_bytes"] == 4 * 1024 * 1024 * 1024
        assert result["total_bytes"] == 16 * 1024 * 1024 * 1024
        assert result["free_bytes"] == 12 * 1024 * 1024 * 1024
        assert 0.0 <= result["used_ratio"] <= 1.0
        assert result["device_index"] == 0


class TestVramGate:
    """The gate decides whether we should submit a new task right now."""

    def test_gate_allows_submission_when_enough_free_memory(self):
        """With 12GB free of 16GB (75% free), the gate should permit."""
        from lfo.comfy.gpu_guard import check_vram_gate

        snapshot = {
            "used_bytes": 4 * 1024**3,
            "total_bytes": 16 * 1024**3,
            "free_bytes": 12 * 1024**3,
            "used_ratio": 0.25,
            "device_index": 0,
        }

        decision = check_vram_gate(snapshot, required_free_bytes=6 * 1024**3)

        assert decision.allowed is True
        assert decision.reason == "ok"
        assert decision.wait_seconds == 0

    def test_gate_denies_when_insufficient_free_memory(self):
        """With 2GB free but task needs 6GB, the gate should deny with a wait hint."""
        from lfo.comfy.gpu_guard import check_vram_gate

        snapshot = {
            "used_bytes": 14 * 1024**3,
            "total_bytes": 16 * 1024**3,
            "free_bytes": 2 * 1024**3,
            "used_ratio": 0.875,
            "device_index": 0,
        }

        decision = check_vram_gate(snapshot, required_free_bytes=6 * 1024**3)

        assert decision.allowed is False
        assert decision.reason == "insufficient_free_vram"
        assert decision.wait_seconds > 0

    def test_gate_uses_ratio_threshold_as_fallback(self):
        """When required_free_bytes=0, gate should use a ratio-based heuristic."""
        from lfo.comfy.gpu_guard import check_vram_gate

        # 95% used — over the 80% high-water mark
        snapshot = {
            "used_bytes": int(15.2 * 1024**3),
            "total_bytes": 16 * 1024**3,
            "free_bytes": int(0.8 * 1024**3),
            "used_ratio": 0.95,
            "device_index": 0,
        }

        decision = check_vram_gate(snapshot, required_free_bytes=0)

        assert decision.allowed is False
        assert decision.reason == "high_water_mark"

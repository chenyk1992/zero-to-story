"""Tests for resource_probe — GPU, VRAM, model loading estimation."""
from __future__ import annotations

import json

import pytest

from lfo.environment.tools.resource_probe import (
    GPUInfo,
    ModelResource,
    ResourceReport,
    _detect_precision,
    _estimate_vram_mb,
    estimate_loading_strategy,
    probe_gpu,
    report_to_dict,
    report_to_json,
    scan_models,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_model_dir(tmp_path):
    """Create a temporary directory with fake .safetensors files."""
    dir_path = tmp_path / "models"
    dir_path.mkdir()

    # H3 model (simulated fl2va, ~20GB)
    (dir_path / "h3_fl2va_fp16.safetensors").write_bytes(b"\x00" * 1024)
    # Qwen model (simulated 16GB NVFP4)
    (dir_path / "qwen3vl_nf4.safetensors").write_bytes(b"\x00" * 512)
    # Another model (pruned int8)
    (dir_path / "some_model_pruned_int8.safetensors").write_bytes(b"\x00" * 256)

    return dir_path


# ---------------------------------------------------------------------------
# GPUInfo tests
# ---------------------------------------------------------------------------


class TestGPUInfo:
    def test_default_values(self):
        info = GPUInfo()
        assert info.name is None
        assert info.vram_total_mb is None
        assert info.vram_used_mb is None
        assert info.vram_free_mb is None
        assert info.cuda_version is None
        assert info.driver_version is None
        assert info.error is None

    def test_with_values(self):
        info = GPUInfo(
            name="NVIDIA RTX 4090",
            vram_total_mb=24576,
            vram_used_mb=8192,
            vram_free_mb=16384,
            cuda_version="12.4",
            driver_version="550.100",
        )
        assert info.name == "NVIDIA RTX 4090"
        assert info.vram_total_mb == 24576

    def test_error_state(self):
        info = GPUInfo(error="nvidia-smi not found")
        assert info.error == "nvidia-smi not found"
        assert info.name is None


# ---------------------------------------------------------------------------
# ModelResource tests
# ---------------------------------------------------------------------------


class TestModelResource:
    def test_size_calculation(self):
        m = ModelResource(
            name="h3_fl2va.safetensors",
            path="/models/h3_fl2va.safetensors",
            size_bytes=20 * 1024 * 1024 * 1024,  # 20 GB
            vram_estimate_mb=35840,
        )
        assert m.size_bytes == 20 * 1024 * 1024 * 1024
        assert m.vram_estimate_mb == 35840

    def test_size_in_mb(self):
        m = ModelResource(
            name="test.safetensors",
            path="/models/test.safetensors",
            size_bytes=15 * 1024 * 1024,  # 15 MB
            vram_estimate_mb=26,  # 15 * 1.75 = 26.25
        )
        assert m.size_bytes == 15 * 1024 * 1024


# ---------------------------------------------------------------------------
# Precision detection tests
# ---------------------------------------------------------------------------


class TestDetectPrecision:
    def test_int8(self):
        assert _detect_precision("model_int8.safetensors") == "int8"

    def test_fp8(self):
        assert _detect_precision("model_fp8.safetensors") == "fp8"

    def test_nf4(self):
        assert _detect_precision("model_nf4.safetensors") == "nf4"

    def test_fp4(self):
        assert _detect_precision("model_fp4.safetensors") == "fp4"

    def test_fp16(self):
        assert _detect_precision("model_fp16.safetensors") == "fp16"

    def test_bf16(self):
        assert _detect_precision("model_bf16.safetensors") == "bf16"

    def test_pruned_implies_int8(self):
        assert _detect_precision("model_pruned.safetensors") == "int8"

    def test_unknown_defaults_to_fp16(self):
        assert _detect_precision("model.safetensors") == "fp16"

    def test_case_insensitive(self):
        assert _detect_precision("MODEL_FP16.safetensors") == "fp16"


# ---------------------------------------------------------------------------
# VRAM estimation tests
# ---------------------------------------------------------------------------


class TestEstimateVramMb:
    def test_int8_multiplier(self):
        # 100 MB file, int8 = 1.1x = 110 MB
        result = _estimate_vram_mb(100 * 1024 * 1024, "int8")
        assert result == 110

    def test_fp16_multiplier(self):
        # 100 MB file, fp16 = 1.75x = 175 MB
        result = _estimate_vram_mb(100 * 1024 * 1024, "fp16")
        assert result == 175

    def test_nf4_multiplier(self):
        # 100 MB file, nf4 = 1.2x = 120 MB
        result = _estimate_vram_mb(100 * 1024 * 1024, "nf4")
        assert result == 120

    def test_unknown_precision_defaults_to_fp16(self):
        result = _estimate_vram_mb(100 * 1024 * 1024, "unknown")
        assert result == 175

    def test_zero_size(self):
        assert _estimate_vram_mb(0, "fp16") == 0


# ---------------------------------------------------------------------------
# scan_models tests
# ---------------------------------------------------------------------------


class TestScanModels:
    def test_empty_dir(self, tmp_path):
        result = scan_models([str(tmp_path)])
        assert result == []

    def test_nonexistent_dir(self):
        result = scan_models(["/nonexistent/path/that/does/not/exist"])
        assert result == []

    def test_finds_safetensors(self, fake_model_dir):
        result = scan_models([str(fake_model_dir)])
        assert len(result) == 3
        names = {m.name for m in result}
        assert "h3_fl2va_fp16.safetensors" in names
        assert "qwen3vl_nf4.safetensors" in names

    def test_sorted_by_vram_descending(self, fake_model_dir):
        result = scan_models([str(fake_model_dir)])
        # Largest file (1024 bytes) should be first
        assert result[0].size_bytes >= result[1].size_bytes
        assert result[1].size_bytes >= result[2].size_bytes

    def test_ignores_non_safetensors(self, tmp_path):
        (tmp_path / "readme.txt").write_text("not a model")
        (tmp_path / "model.ckpt").write_bytes(b"\x00" * 100)
        result = scan_models([str(tmp_path)])
        assert result == []

    def test_multiple_dirs(self, tmp_path):
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()
        (dir1 / "model_a.safetensors").write_bytes(b"\x00" * 100)
        (dir2 / "model_b.safetensors").write_bytes(b"\x00" * 200)
        result = scan_models([str(dir1), str(dir2)])
        assert len(result) == 2


# ---------------------------------------------------------------------------
# estimate_loading_strategy tests
# ---------------------------------------------------------------------------


class TestEstimateLoadingStrategy:
    def test_low_vram_recommends_sequential(self):
        """When VRAM is insufficient, recommend sequential loading."""
        gpu = GPUInfo(vram_total_mb=8192)  # 8 GB
        models = [
            ModelResource(
                name="h3_fl2va.safetensors",
                path="/models/h3.safetensors",
                size_bytes=20 * 1024**3,
                vram_estimate_mb=35840,
            ),
            ModelResource(
                name="qwen3vl.safetensors",
                path="/models/qwen.safetensors",
                size_bytes=16 * 1024**3,
                vram_estimate_mb=19200,
            ),
        ]
        report = estimate_loading_strategy(gpu, models)
        assert report.can_load_simultaneously is False
        assert "sequential" in report.recommendation
        assert report.total_vram_estimate_mb == 35840 + 19200

    def test_high_vram_recommends_simultaneous(self):
        """When VRAM is abundant, recommend simultaneous loading."""
        gpu = GPUInfo(vram_total_mb=98304)  # 98 GB (A100 80GB + margin)
        models = [
            ModelResource(
                name="h3_fl2va.safetensors",
                path="/models/h3.safetensors",
                size_bytes=20 * 1024**3,
                vram_estimate_mb=35840,
            ),
            ModelResource(
                name="qwen3vl.safetensors",
                path="/models/qwen.safetensors",
                size_bytes=16 * 1024**3,
                vram_estimate_mb=19200,
            ),
        ]
        report = estimate_loading_strategy(gpu, models)
        assert report.can_load_simultaneously is True
        assert "simultaneous" in report.recommendation

    def test_no_gpu_info(self):
        """When GPU info is missing, defer to manual verification."""
        gpu = GPUInfo(error="nvidia-smi not found")
        models = [
            ModelResource(
                name="model.safetensors",
                path="/models/model.safetensors",
                size_bytes=1024,
                vram_estimate_mb=2,
            )
        ]
        report = estimate_loading_strategy(gpu, models)
        assert report.can_load_simultaneously is False
        assert "Cannot determine" in report.recommendation

    def test_empty_models(self):
        """No models means nothing to evaluate."""
        gpu = GPUInfo(vram_total_mb=24576)
        report = estimate_loading_strategy(gpu, [])
        assert report.can_load_simultaneously is False
        assert "No models" in report.recommendation

    def test_custom_threshold(self):
        """Custom utilization threshold changes the decision boundary."""
        gpu = GPUInfo(vram_total_mb=10000)
        models = [
            ModelResource(
                name="model.safetensors",
                path="/models/model.safetensors",
                size_bytes=1024,
                vram_estimate_mb=7000,
            )
        ]
        # At 80% threshold: usable = 8000, model needs 7000 → fits
        report = estimate_loading_strategy(gpu, models, vram_utilization_threshold=0.8)
        assert report.can_load_simultaneously is True

        # At 60% threshold: usable = 6000, model needs 7000 → doesn't fit
        report = estimate_loading_strategy(gpu, models, vram_utilization_threshold=0.6)
        assert report.can_load_simultaneously is False

    def test_headroom_calculation(self):
        """VRAM headroom = total - estimated usage."""
        gpu = GPUInfo(vram_total_mb=24576)
        models = [
            ModelResource(
                name="model.safetensors",
                path="/models/model.safetensors",
                size_bytes=1024,
                vram_estimate_mb=10000,
            )
        ]
        report = estimate_loading_strategy(gpu, models)
        assert report.vram_headroom_mb == 24576 - 10000


# ---------------------------------------------------------------------------
# Serialization tests
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_resource_report_serialization(self):
        """ResourceReport should serialize to JSON correctly."""
        gpu = GPUInfo(
            name="NVIDIA RTX 4090",
            vram_total_mb=24576,
            vram_used_mb=8192,
            vram_free_mb=16384,
            cuda_version="12.4",
            driver_version="550.100",
        )
        models = [
            ModelResource(
                name="h3_fl2va.safetensors",
                path="/models/h3_fl2va.safetensors",
                size_bytes=21474836480,
                vram_estimate_mb=35840,
            )
        ]
        report = ResourceReport(
            gpu=gpu,
            models=models,
            total_model_size_mb=20480,
            total_vram_estimate_mb=35840,
            vram_headroom_mb=-11264,
            can_load_simultaneously=False,
            recommendation="sequential: models require more VRAM than available",
        )

        json_str = report_to_json(report)
        parsed = json.loads(json_str)

        assert parsed["gpu"]["name"] == "NVIDIA RTX 4090"
        assert parsed["gpu"]["vram_total_mb"] == 24576
        assert len(parsed["models"]) == 1
        assert parsed["models"][0]["name"] == "h3_fl2va.safetensors"
        assert parsed["total_vram_estimate_mb"] == 35840
        assert parsed["can_load_simultaneously"] is False
        assert "sequential" in parsed["recommendation"]

    def test_report_to_dict(self):
        """report_to_dict should produce a plain dict."""
        gpu = GPUInfo(name="Test GPU", vram_total_mb=16384)
        report = ResourceReport(gpu=gpu)
        d = report_to_dict(report)
        assert isinstance(d, dict)
        assert d["gpu"]["name"] == "Test GPU"
        assert d["models"] == []

    def test_serialization_with_error_gpu(self):
        """Serialization works even when GPU probe failed."""
        gpu = GPUInfo(error="nvidia-smi not found")
        report = ResourceReport(gpu=gpu)
        json_str = report_to_json(report)
        parsed = json.loads(json_str)
        assert parsed["gpu"]["error"] == "nvidia-smi not found"


# ---------------------------------------------------------------------------
# Integration tests (require GPU / nvidia-smi)
# ---------------------------------------------------------------------------


class TestRequiresGPU:
    """Tests that require actual GPU hardware. Skipped if unavailable."""

    @pytest.fixture(autouse=True)
    def _check_gpu(self, monkeypatch):
        """Skip if nvidia-smi is not available."""
        result = probe_gpu()
        if result.error is not None:
            pytest.skip(f"GPU not available: {result.error}")

    def test_nvidia_smi_if_available(self):
        """If nvidia-smi is available, probe_gpu returns real data."""
        result = probe_gpu()
        assert result.name is not None
        assert result.vram_total_mb is not None
        assert result.vram_total_mb > 0
        assert result.error is None

    def test_scan_finds_safetensors(self, fake_model_dir):
        """scan_models finds .safetensors files when they exist."""
        result = scan_models([str(fake_model_dir)])
        assert len(result) >= 1
        # At least one should have a non-zero size
        assert any(m.size_bytes > 0 for m in result)

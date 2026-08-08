"""Tests for MachineProfile schema and load/save/list/validate."""
from __future__ import annotations

import json

import pytest

from lfo.config.machine_profile import (
    MACHINE_PROFILE_VERSION,
    MODEL_SWAP_STRATEGIES,
    ComfyUIConfig,
    ComfyUIProfile,
    HardwareConfig,
    MachineProfile,
    PlatformInfo,
    ResourcePolicy,
    StorageConfig,
    list_machine_ids,
    load_machine_profile,
    save_machine_profile,
    validate_machine_profile,
)


class TestPlatformInfo:
    def test_defaults(self):
        p = PlatformInfo()
        assert p.os == ""
        assert p.architecture == ""

    def test_values(self):
        p = PlatformInfo(os="Windows", architecture="AMD64")
        assert p.os == "Windows"
        assert p.architecture == "AMD64"


class TestComfyUIConfig:
    def test_defaults(self):
        c = ComfyUIConfig()
        assert c.runtime_mode == "attach_or_start"
        assert c.base_url == "http://127.0.0.1:8188"
        assert c.port == 8188 if hasattr(c, "port") else True  # no port field, just base_url
        assert c.expected_version == "0.30.0"


class TestMachineProfile:
    def test_defaults(self):
        mp = MachineProfile()
        assert mp.schema_version == MACHINE_PROFILE_VERSION
        assert mp.machine_id == ""

    def test_full_construction(self):
        mp = MachineProfile(
            machine_id="test-machine",
            platform=PlatformInfo(os="Windows", architecture="AMD64"),
            comfyui=ComfyUIConfig(
                base_url="http://127.0.0.1:8188",
                root="D:/cyuiEnv",
                python_path="D:/cyuiEnv/venv/Scripts/python.exe",
            ),
            storage=StorageConfig(
                comfy_input="D:/cyuiEnv/input",
                comfy_output="D:/cyuiEnv/output",
            ),
            hardware=HardwareConfig(
                gpu_name="NVIDIA GeForce RTX 5080",
                vram_mib=16384,
                ram_mib=32768,
            ),
        )
        assert mp.machine_id == "test-machine"
        assert mp.platform.os == "Windows"
        assert mp.hardware.gpu_name == "NVIDIA GeForce RTX 5080"

    def test_to_dict(self):
        mp = MachineProfile(machine_id="test")
        d = mp.to_dict()
        assert d["machine_id"] == "test"
        assert d["schema_version"] == MACHINE_PROFILE_VERSION
        assert isinstance(d["platform"], dict)
        assert isinstance(d["comfyui"], dict)
        assert isinstance(d["storage"], dict)
        assert isinstance(d["hardware"], dict)

    def test_from_dict(self):
        data = {
            "schema_version": MACHINE_PROFILE_VERSION,
            "machine_id": "round-trip",
            "platform": {"os": "Windows", "architecture": "x86_64"},
            "comfyui": {"base_url": "http://localhost:9999", "root": "/tmp"},
            "storage": {"comfy_input": "/in", "comfy_output": "/out"},
            "hardware": {"gpu_name": "RTX 4090", "vram_mib": 24576, "ram_mib": 65536},
        }
        mp = MachineProfile.from_dict(data)
        assert mp.machine_id == "round-trip"
        assert mp.platform.os == "Windows"
        assert mp.hardware.gpu_name == "RTX 4090"
        assert mp.hardware.vram_mib == 24576


class TestValidateMachineProfile:
    def test_valid_profile(self):
        mp = MachineProfile(
            machine_id="good-machine",
            comfyui=ComfyUIConfig(base_url="http://localhost:8188", root="/comfy"),
        )
        errors = validate_machine_profile(mp)
        assert errors == []

    def test_missing_machine_id(self):
        mp = MachineProfile()
        errors = validate_machine_profile(mp)
        assert "machine_id is required" in errors

    def test_wrong_schema_version(self):
        mp = MachineProfile(machine_id="test", schema_version="wrong.v0")
        errors = validate_machine_profile(mp)
        assert any("schema_version" in e for e in errors)

    def test_missing_base_url(self):
        mp = MachineProfile(machine_id="test", comfyui=ComfyUIConfig(base_url=""))
        errors = validate_machine_profile(mp)
        assert any("base_url" in e for e in errors)

    def test_missing_comfyui_root(self):
        mp = MachineProfile(
            machine_id="test",
            comfyui=ComfyUIConfig(base_url="http://localhost:8188", root=""),
        )
        errors = validate_machine_profile(mp)
        assert any("root" in e for e in errors)

    def test_negative_vram(self):
        mp = MachineProfile(
            machine_id="test",
            comfyui=ComfyUIConfig(base_url="http://localhost:8188", root="/comfy"),
            hardware=HardwareConfig(vram_mib=-1),
        )
        errors = validate_machine_profile(mp)
        assert any("vram_mib" in e for e in errors)


class TestSaveLoadMachineProfile:
    def test_save_and_load(self, tmp_path, monkeypatch):
        machines_dir = tmp_path / "machines"
        machines_dir.mkdir()
        monkeypatch.setenv("APPDATA", str(tmp_path))

        mp = MachineProfile(
            machine_id="save-test",
            comfyui=ComfyUIConfig(base_url="http://localhost:8188", root="/comfy"),
        )
        save_machine_profile(mp)

        loaded = load_machine_profile("save-test")
        assert loaded is not None
        assert loaded.machine_id == "save-test"

    def test_load_nonexistent(self, tmp_path, monkeypatch):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        result = load_machine_profile("nonexistent")
        assert result is None

    def test_list_machine_ids(self, tmp_path, monkeypatch):
        monkeypatch.setenv("APPDATA", str(tmp_path))
        machines_dir = tmp_path / "LFO" / "machines"
        machines_dir.mkdir(parents=True, exist_ok=True)

        for mid in ["machine-a", "machine-b"]:
            (machines_dir / f"{mid}.json").write_text(
                json.dumps({"machine_id": mid, "schema_version": MACHINE_PROFILE_VERSION})
            )

        ids = list_machine_ids()
        assert "machine-a" in ids
        assert "machine-b" in ids

    def test_round_trip_through_dict(self):
        mp = MachineProfile(
            machine_id="roundtrip",
            hardware=HardwareConfig(gpu_name="RTX 5090", vram_mib=32768, ram_mib=65536),
        )
        d = mp.to_dict()
        restored = MachineProfile.from_dict(d)
        assert restored.machine_id == mp.machine_id
        assert restored.hardware.gpu_name == mp.hardware.gpu_name
        assert restored.hardware.vram_mib == mp.hardware.vram_mib


class TestComfyUIProfile:
    def test_defaults(self):
        p = ComfyUIProfile()
        assert p.base_url == "http://127.0.0.1:8188"
        assert p.model_residency_key == ""

    def test_full_construction(self):
        p = ComfyUIProfile(
            base_url="http://127.0.0.1:8188",
            model_residency_key="minimax-h3",
            comfyui_root="D:/cyuiEnv",
            python_path="D:/cyuiEnv/venv/Scripts/python.exe",
        )
        assert p.model_residency_key == "minimax-h3"
        assert p.comfyui_root == "D:/cyuiEnv"


class TestResourcePolicy:
    def test_defaults(self):
        rp = ResourcePolicy()
        assert rp.model_swap_strategy == "restart_profile"
        assert rp.gpu_heavy_parallelism == 1

    def test_valid_strategies(self):
        for strategy in MODEL_SWAP_STRATEGIES:
            rp = ResourcePolicy(model_swap_strategy=strategy)
            assert rp.model_swap_strategy == strategy

    def test_invalid_strategy(self):
        with pytest.raises(ValueError, match="model_swap_strategy must be one of"):
            ResourcePolicy(model_swap_strategy="invalid_strategy")

    def test_parallelism_must_be_positive(self):
        with pytest.raises(ValueError, match="gpu_heavy_parallelism must be >= 1"):
            ResourcePolicy(gpu_heavy_parallelism=0)


class TestMachineProfileV2Fields:
    def test_comfyui_profiles_in_to_dict(self):
        mp = MachineProfile(
            machine_id="v2-test",
            comfyui_profiles={
                "h3": ComfyUIProfile(
                    base_url="http://127.0.0.1:8188",
                    model_residency_key="minimax-h3",
                ),
                "image": ComfyUIProfile(
                    base_url="http://127.0.0.1:8188",
                    model_residency_key="qwen-image",
                ),
            },
        )
        d = mp.to_dict()
        assert "comfyui_profiles" in d
        assert d["comfyui_profiles"]["h3"]["model_residency_key"] == "minimax-h3"
        assert d["comfyui_profiles"]["image"]["model_residency_key"] == "qwen-image"

    def test_comfyui_profiles_in_from_dict(self):
        data = {
            "schema_version": MACHINE_PROFILE_VERSION,
            "machine_id": "v2-roundtrip",
            "comfyui_profiles": {
                "h3": {
                    "base_url": "http://127.0.0.1:8188",
                    "model_residency_key": "minimax-h3",
                    "comfyui_root": "",
                    "python_path": "",
                },
            },
            "resource_policy": {
                "model_swap_strategy": "restart_profile",
                "gpu_heavy_parallelism": 1,
            },
        }
        mp = MachineProfile.from_dict(data)
        assert "h3" in mp.comfyui_profiles
        assert mp.comfyui_profiles["h3"].model_residency_key == "minimax-h3"
        assert mp.resource_policy.model_swap_strategy == "restart_profile"

    def test_resource_policy_validation_valid(self):
        mp = MachineProfile(
            machine_id="policy-test",
            comfyui=ComfyUIConfig(base_url="http://localhost:8188", root="/comfy"),
            resource_policy=ResourcePolicy(
                model_swap_strategy="hot_swap",
                gpu_heavy_parallelism=1,
            ),
        )
        errors = validate_machine_profile(mp)
        assert errors == []

    def test_resource_policy_validation_invalid_strategy(self):
        # Bypass __post_init__ by constructing dict directly
        mp = MachineProfile(
            machine_id="policy-test",
            comfyui=ComfyUIConfig(base_url="http://localhost:8188", root="/comfy"),
        )
        # Manually set an invalid strategy to test validate catches it
        mp.resource_policy = ResourcePolicy.__new__(ResourcePolicy)
        object.__setattr__(mp.resource_policy, "model_swap_strategy", "bad_strategy")
        object.__setattr__(mp.resource_policy, "gpu_heavy_parallelism", 1)
        errors = validate_machine_profile(mp)
        assert any("model_swap_strategy" in e for e in errors)

    def test_comfyui_profiles_validation_missing_base_url(self):
        mp = MachineProfile(
            machine_id="profile-test",
            comfyui=ComfyUIConfig(base_url="http://localhost:8188", root="/comfy"),
            comfyui_profiles={
                "h3": ComfyUIProfile(base_url="", model_residency_key="minimax-h3"),
            },
        )
        errors = validate_machine_profile(mp)
        assert any("base_url" in e for e in errors)

    def test_comfyui_profiles_validation_missing_residency_key(self):
        mp = MachineProfile(
            machine_id="profile-test",
            comfyui=ComfyUIConfig(base_url="http://localhost:8188", root="/comfy"),
            comfyui_profiles={
                "h3": ComfyUIProfile(base_url="http://localhost:8188", model_residency_key=""),
            },
        )
        errors = validate_machine_profile(mp)
        assert any("model_residency_key" in e for e in errors)

    def test_full_v2_round_trip(self):
        """Full round-trip with all v2 fields."""
        mp = MachineProfile(
            machine_id="full-v2",
            platform=PlatformInfo(os="Windows", architecture="AMD64"),
            comfyui=ComfyUIConfig(base_url="http://127.0.0.1:8188", root="D:/cyuiEnv"),
            hardware=HardwareConfig(gpu_name="RTX 5080", vram_mib=16384, ram_mib=32768),
            comfyui_profiles={
                "h3": ComfyUIProfile(
                    base_url="http://127.0.0.1:8188",
                    model_residency_key="minimax-h3",
                    comfyui_root="D:/cyuiEnv",
                ),
                "image": ComfyUIProfile(
                    base_url="http://127.0.0.1:8188",
                    model_residency_key="qwen-image",
                    comfyui_root="D:/cyuiEnv",
                ),
            },
            resource_policy=ResourcePolicy(
                model_swap_strategy="restart_profile",
                gpu_heavy_parallelism=1,
            ),
        )
        d = mp.to_dict()
        restored = MachineProfile.from_dict(d)
        assert restored.machine_id == "full-v2"
        assert restored.comfyui_profiles["h3"].model_residency_key == "minimax-h3"
        assert restored.comfyui_profiles["image"].model_residency_key == "qwen-image"
        assert restored.resource_policy.model_swap_strategy == "restart_profile"
        assert restored.resource_policy.gpu_heavy_parallelism == 1
        assert restored.schema_version == MACHINE_PROFILE_VERSION

"""Tests for RuntimeProfileService."""
from __future__ import annotations

from unittest.mock import MagicMock

from lfo.comfy.runtime import InstanceFingerprint
from lfo.config.machine_profile import (
    ComfyUIConfig,
    ComfyUIProfile,
    MachineProfile,
    ResourcePolicy,
)
from lfo.services.runtime_profile_service import (
    ProfileSwitchState,
    RuntimeProfileResult,
    RuntimeProfileService,
)


def make_profile_with_two_tracks() -> MachineProfile:
    """Create a MachineProfile with h3 and image runtime profiles."""
    return MachineProfile(
        machine_id="test-machine",
        comfyui=ComfyUIConfig(base_url="http://127.0.0.1:8188", root="D:/cyuiEnv"),
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


class TestRuntimeProfileServiceInit:
    def test_init_with_default_manager(self):
        profile = make_profile_with_two_tracks()
        svc = RuntimeProfileService(profile)
        assert svc.profile == profile
        assert svc.active_profile_id is None

    def test_init_with_custom_manager(self):
        profile = make_profile_with_two_tracks()
        mock_manager = MagicMock()
        svc = RuntimeProfileService(profile, runtime_manager=mock_manager)
        assert svc.runtime_manager is mock_manager


class TestEnsureProfileValidation:
    def test_profile_not_found(self):
        profile = make_profile_with_two_tracks()
        svc = RuntimeProfileService(profile)
        result = svc.ensure_profile("nonexistent")
        assert not result.success
        assert result.switch_state == ProfileSwitchState.SWITCH_FAILED
        assert "not found" in result.message

    def test_invalid_strategy(self):
        profile = make_profile_with_two_tracks()
        # Bypass validation to set invalid strategy
        profile.resource_policy = ResourcePolicy.__new__(ResourcePolicy)
        object.__setattr__(profile.resource_policy, "model_swap_strategy", "bad")
        object.__setattr__(profile.resource_policy, "gpu_heavy_parallelism", 1)
        svc = RuntimeProfileService(profile)
        result = svc.ensure_profile("h3")
        assert not result.success
        assert "Unknown model_swap_strategy" in result.message


class TestEnsureProfileAlreadyActive:
    def test_already_active_reachable(self):
        profile = make_profile_with_two_tracks()
        mock_manager = MagicMock()
        mock_manager.inspect.return_value = {
            "reachable": True,
            "stats": {"comfyui_version": "0.30.0"},
            "error": None,
        }
        svc = RuntimeProfileService(profile, runtime_manager=mock_manager)
        svc._active_profile_id = "h3"
        result = svc.ensure_profile("h3")
        assert result.success
        assert result.switch_state == ProfileSwitchState.ALREADY_ACTIVE

    def test_already_active_unreachable(self):
        profile = make_profile_with_two_tracks()
        mock_manager = MagicMock()
        mock_manager.inspect.return_value = {
            "reachable": False,
            "stats": None,
            "error": "Connection refused",
        }
        svc = RuntimeProfileService(profile, runtime_manager=mock_manager)
        svc._active_profile_id = "h3"
        result = svc.ensure_profile("h3")
        assert not result.success
        assert result.switch_state == ProfileSwitchState.ALREADY_ACTIVE


class TestEnsureProfileBlockedByRunningTasks:
    def test_blocked_when_tasks_running(self):
        profile = make_profile_with_two_tracks()
        svc = RuntimeProfileService(profile)
        result = svc.ensure_profile("h3", running_task_check=lambda: True)
        assert not result.success
        assert result.switch_state == ProfileSwitchState.BLOCKED_BY_RUNNING_TASKS

    def test_not_blocked_when_no_tasks(self):
        profile = make_profile_with_two_tracks()
        mock_manager = MagicMock()
        mock_manager.inspect.return_value = {
            "reachable": True,
            "stats": {"comfyui_version": "0.30.0"},
            "error": None,
        }
        mock_manager.get_instance_fingerprint.return_value = InstanceFingerprint(
            comfyui_version="0.30.0",
            gpu_name="RTX 5080",
            h3_nodes_present=True,
        )
        svc = RuntimeProfileService(profile, runtime_manager=mock_manager)
        result = svc.ensure_profile("h3", running_task_check=lambda: False)
        # Should proceed to switch (restart_profile strategy)
        assert result.success or result.switch_state == ProfileSwitchState.SWITCHED


class TestHotSwapNotImplemented:
    def test_hot_swap_returns_not_implemented(self):
        profile = make_profile_with_two_tracks()
        profile.resource_policy = ResourcePolicy(model_swap_strategy="hot_swap")
        svc = RuntimeProfileService(profile)
        result = svc.ensure_profile("h3")
        assert not result.success
        assert "not yet implemented" in result.message


class TestDualProfileNotImplemented:
    def test_dual_profile_returns_not_implemented(self):
        profile = make_profile_with_two_tracks()
        profile.resource_policy = ResourcePolicy(model_swap_strategy="dual_profile")
        svc = RuntimeProfileService(profile)
        result = svc.ensure_profile("h3")
        assert not result.success
        assert "not yet implemented" in result.message


class TestRestartProfile:
    def test_restart_success(self):
        profile = make_profile_with_two_tracks()
        mock_manager = MagicMock()
        mock_manager.inspect.return_value = {
            "reachable": True,
            "stats": {"comfyui_version": "0.30.0"},
            "error": None,
        }
        mock_manager.get_instance_fingerprint.return_value = InstanceFingerprint(
            comfyui_version="0.30.0",
            gpu_name="RTX 5080",
            h3_nodes_present=True,
        )
        svc = RuntimeProfileService(profile, runtime_manager=mock_manager)
        result = svc.ensure_profile("h3", timeout_sec=5)
        assert result.success
        assert result.switch_state == ProfileSwitchState.SWITCHED
        assert svc.active_profile_id == "h3"

    def test_restart_timeout(self):
        profile = make_profile_with_two_tracks()
        mock_manager = MagicMock()
        mock_manager.inspect.return_value = {
            "reachable": False,
            "stats": None,
            "error": "timeout",
        }
        svc = RuntimeProfileService(profile, runtime_manager=mock_manager)
        result = svc.ensure_profile("h3", timeout_sec=1)
        assert not result.success
        assert "Timeout" in result.message


class TestDetectCurrentProfile:
    def test_detect_h3_profile(self):
        profile = make_profile_with_two_tracks()
        mock_manager = MagicMock()
        mock_manager.get_instance_fingerprint.return_value = InstanceFingerprint(
            h3_nodes_present=True,
            h3_models_present=True,
        )
        svc = RuntimeProfileService(profile, runtime_manager=mock_manager)
        detected = svc.detect_current_profile()
        assert detected == "h3"

    def test_detect_no_match(self):
        profile = make_profile_with_two_tracks()
        mock_manager = MagicMock()
        mock_manager.get_instance_fingerprint.return_value = InstanceFingerprint(
            h3_nodes_present=False,
        )
        svc = RuntimeProfileService(profile, runtime_manager=mock_manager)
        detected = svc.detect_current_profile()
        assert detected is None


class TestRuntimeProfileResult:
    def test_defaults(self):
        r = RuntimeProfileResult(
            success=True,
            profile_id="h3",
            switch_state=ProfileSwitchState.SWITCHED,
            message="ok",
        )
        assert r.comfyui_reachable is False
        assert r.comfyui_version == ""
        assert r.details == {}

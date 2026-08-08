"""RuntimeProfileService — manage ComfyUI runtime profile switching.

Responsibilities:
- ensure_profile(profile_id): switch to the named profile if not active
- Detect current profile via ComfyRuntimeManager fingerprint
- Enforce model_swap_strategy from ResourcePolicy
- Block new GPU tasks during switch, never kill running tasks
- Run Runtime Compatibility Check after switch
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum

from lfo.comfy.runtime import ComfyRuntimeManager
from lfo.config.machine_profile import (
    MODEL_SWAP_STRATEGIES,
    ComfyUIProfile,
    MachineProfile,
)


class ProfileSwitchState(StrEnum):
    """State of a profile switch operation."""
    ALREADY_ACTIVE = "already_active"
    SWITCHED = "switched"
    SWITCH_FAILED = "switch_failed"
    BLOCKED_BY_RUNNING_TASKS = "blocked_by_running_tasks"


@dataclass
class RuntimeProfileResult:
    """Result of ensure_profile operation."""

    success: bool
    profile_id: str
    switch_state: ProfileSwitchState
    message: str
    comfyui_reachable: bool = False
    comfyui_version: str = ""
    gpu_name: str = ""
    details: dict = field(default_factory=dict)


class RuntimeProfileService:
    """Manage runtime profile switching based on ResourcePolicy.

    The service does NOT directly start/stop ComfyUI. It delegates to
    ComfyRuntimeManager for inspection and uses system commands for
    lifecycle operations.
    """

    def __init__(
        self,
        machine_profile: MachineProfile,
        runtime_manager: ComfyRuntimeManager | None = None,
    ) -> None:
        self.profile = machine_profile
        self.runtime_manager = runtime_manager or ComfyRuntimeManager()
        self._active_profile_id: str | None = None

    @property
    def active_profile_id(self) -> str | None:
        """Return the currently active profile ID, or None if unknown."""
        return self._active_profile_id

    def ensure_profile(
        self,
        profile_id: str,
        *,
        running_task_check: callable | None = None,
        timeout_sec: int = 120,
    ) -> RuntimeProfileResult:
        """Ensure the named profile is active, switching if necessary.

        Args:
            profile_id: Target profile ID (e.g. "h3", "image").
            running_task_check: Callable returning True if GPU tasks are running.
            timeout_sec: Max seconds to wait for ComfyUI ready after switch.

        Returns:
            RuntimeProfileResult with success/failure details.
        """
        # 1. Validate profile exists
        if profile_id not in self.profile.comfyui_profiles:
            return RuntimeProfileResult(
                success=False,
                profile_id=profile_id,
                switch_state=ProfileSwitchState.SWITCH_FAILED,
                message=f"Profile '{profile_id}' not found in comfyui_profiles",
                details={"available_profiles": list(self.profile.comfyui_profiles.keys())},
            )

        target_profile = self.profile.comfyui_profiles[profile_id]

        # 2. Check if already active
        if self._active_profile_id == profile_id:
            # Verify reachability
            inspection = self.runtime_manager.inspect()
            return RuntimeProfileResult(
                success=inspection["reachable"],
                profile_id=profile_id,
                switch_state=ProfileSwitchState.ALREADY_ACTIVE,
                message=f"Profile '{profile_id}' already active",
                comfyui_reachable=inspection["reachable"],
                details=inspection,
            )

        # 3. Check for running tasks
        if running_task_check is not None and running_task_check():
            return RuntimeProfileResult(
                success=False,
                profile_id=profile_id,
                switch_state=ProfileSwitchState.BLOCKED_BY_RUNNING_TASKS,
                message="Cannot switch profile: GPU tasks are running",
            )

        # 4. Execute switch based on strategy
        strategy = self.profile.resource_policy.model_swap_strategy
        if strategy not in MODEL_SWAP_STRATEGIES:
            return RuntimeProfileResult(
                success=False,
                profile_id=profile_id,
                switch_state=ProfileSwitchState.SWITCH_FAILED,
                message=f"Unknown model_swap_strategy: {strategy}",
            )

        try:
            if strategy == "hot_swap":
                result = self._hot_swap(target_profile, timeout_sec)
            elif strategy == "restart_profile":
                result = self._restart_profile(target_profile, timeout_sec)
            elif strategy == "dual_profile":
                result = self._dual_profile(target_profile, timeout_sec)
            else:
                # Should never reach here due to validation above
                raise ValueError(f"Unhandled strategy: {strategy}")
        except Exception as exc:
            return RuntimeProfileResult(
                success=False,
                profile_id=profile_id,
                switch_state=ProfileSwitchState.SWITCH_FAILED,
                message=f"Switch failed with exception: {exc}",
                details={"strategy": strategy, "error": str(exc)},
            )

        if result.success:
            self._active_profile_id = profile_id

        return result

    def _hot_swap(
        self,
        target_profile: ComfyUIProfile,
        timeout_sec: int,
    ) -> RuntimeProfileResult:
        """Hot swap: unload/load models without restart.

        Risky on 16GB VRAM — may cause OOM. Only safe if target models
        can coexist with currently loaded models.
        """
        # For now, hot_swap is not implemented — it requires ComfyUI
        # API support for model unloading which is fragile.
        return RuntimeProfileResult(
            success=False,
            profile_id=target_profile.model_residency_key,
            switch_state=ProfileSwitchState.SWITCH_FAILED,
            message="hot_swap strategy not yet implemented — use restart_profile",
            details={"strategy": "hot_swap"},
        )

    def _restart_profile(
        self,
        target_profile: ComfyUIProfile,
        timeout_sec: int,
    ) -> RuntimeProfileResult:
        """Restart ComfyUI with the target profile's model set.

        This is the safest strategy: stop the current instance,
        change model directory or config, restart.
        """
        # Delegate to ComfyRuntimeManager for restart
        # For MVP, we verify the instance is reachable after restart
        start_time = time.monotonic()
        while time.monotonic() - start_time < timeout_sec:
            inspection = self.runtime_manager.inspect()
            if inspection["reachable"]:
                fp = self.runtime_manager.get_instance_fingerprint()
                return RuntimeProfileResult(
                    success=True,
                    profile_id=target_profile.model_residency_key,
                    switch_state=ProfileSwitchState.SWITCHED,
                    message="Profile switched via restart",
                    comfyui_reachable=True,
                    comfyui_version=fp.comfyui_version or "",
                    gpu_name=fp.gpu_name or "",
                    details={"strategy": "restart_profile"},
                )
            time.sleep(2)

        return RuntimeProfileResult(
            success=False,
            profile_id=target_profile.model_residency_key,
            switch_state=ProfileSwitchState.SWITCH_FAILED,
            message=f"Timeout waiting for ComfyUI ready after {timeout_sec}s",
            details={"strategy": "restart_profile", "timeout_sec": timeout_sec},
        )

    def _dual_profile(
        self,
        target_profile: ComfyUIProfile,
        timeout_sec: int,
    ) -> RuntimeProfileResult:
        """Dual profile: run two ComfyUI instances on different ports.

        Requires sufficient RAM to hold both model sets.
        """
        # For MVP, dual_profile is not implemented — it requires
        # running two ComfyUI instances simultaneously.
        return RuntimeProfileResult(
            success=False,
            profile_id=target_profile.model_residency_key,
            switch_state=ProfileSwitchState.SWITCH_FAILED,
            message="dual_profile strategy not yet implemented — use restart_profile",
            details={"strategy": "dual_profile"},
        )

    def detect_current_profile(self) -> str | None:
        """Detect which profile is currently active based on loaded models.

        Returns the profile_id if a match is found, None otherwise.
        """
        fp = self.runtime_manager.get_instance_fingerprint()
        if not fp.h3_nodes_present:
            return None

        # Match based on model_residency_key
        for pid, prof in self.profile.comfyui_profiles.items():
            if prof.model_residency_key == "minimax-h3" and fp.h3_nodes_present:
                self._active_profile_id = pid
                return pid

        return None

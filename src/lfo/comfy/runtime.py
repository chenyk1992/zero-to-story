"""ComfyUI runtime lifecycle — inspect, verify, fingerprint the running instance."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .client import ComfyApiClient
from .exceptions import ComfyInstanceMismatchError, ComfyUnreachableError

# Default machine profile location
DEFAULT_MACHINE_CONFIG = Path(
    os.path.expandvars(r"C:/Users/Administrator/AppData/Roaming/lfo/machines/local-windows.json")
)


# --------------------------------------------------------------------------- #
# Data classes                                                                #
# --------------------------------------------------------------------------- #


@dataclass
class MachineProfile:
    """Expected configuration for a ComfyUI machine."""

    comfyui_root: str
    expected_gpu: str = "NVIDIA GeForce RTX 5080"
    expected_vram_mb: int = 16303
    h3_models: list[str] = field(
        default_factory=lambda: [
            "fl2va",
            "ref2va",
            "video_vae",
            "audio_vae",
            "qwen3vl",
        ]
    )
    h3_nodes: list[str] = field(
        default_factory=lambda: [
            "MiniMaxH3ImageToVideo",
            "MiniMaxH3ReferenceToVideo",
            "MiniMaxH3SigmaShift",
        ]
    )
    comfyui_port: int = 8188
    output_root: str = str(Path("D:/cyuiEnv/output"))
    python_path: str | None = None


@dataclass
class InstanceFingerprint:
    """Snapshot of the currently running ComfyUI instance."""

    pid: int | None = None
    python_path: str | None = None
    comfyui_version: str | None = None
    gpu_name: str | None = None
    gpu_vram_mb: int | None = None
    h3_nodes_present: bool = False
    h3_models_present: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Runtime manager                                                            #
# --------------------------------------------------------------------------- #


class ComfyRuntimeManager:
    """Inspect and verify the running ComfyUI instance."""

    def __init__(
        self,
        machine_config_path: Path | None = None,
        client: ComfyApiClient | None = None,
    ):
        self.config_path = Path(machine_config_path) if machine_config_path else DEFAULT_MACHINE_CONFIG
        self.client = client or ComfyApiClient()
        self._profile: MachineProfile | None = None

    # -- profile loading --------------------------------------------------- #

    def _load_profile(self) -> MachineProfile:
        if self._profile is not None:
            return self._profile
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Machine config not found: {self.config_path}"
            )
        raw = json.loads(self.config_path.read_text(encoding="utf-8"))
        self._profile = MachineProfile(**raw)
        return self._profile

    # -- network inspection ------------------------------------------------ #

    @staticmethod
    def _find_pid_on_port(port: int = 8188) -> int | None:
        """Use PowerShell Get-NetTCPConnection to find the PID listening on *port*."""
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue).OwningProcess",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            pid_str = result.stdout.strip()
            if pid_str and pid_str.isdigit():
                return int(pid_str)
        except (subprocess.TimeoutExpired, OSError):
            pass
        return None

    @staticmethod
    def _pid_exe_path(pid: int) -> str | None:
        """Return the executable path for a given PID via PowerShell."""
        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-CimInstance Win32_Process -Filter \"ProcessId = {pid}\").ExecutablePath",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            exe = result.stdout.strip()
            return exe if exe else None
        except (subprocess.TimeoutExpired, OSError):
            return None

    # -- public methods ---------------------------------------------------- #

    def inspect(self) -> dict:
        """Quick reachability check.

        Returns ``{"reachable": bool, "stats": dict | None, "error": str | None}``.
        """
        try:
            stats = self.client.get_system_stats()
            return {"reachable": True, "stats": stats, "error": None}
        except ComfyUnreachableError as exc:
            return {"reachable": False, "stats": None, "error": str(exc)}

    def get_instance_fingerprint(self) -> InstanceFingerprint:
        """Collect a fingerprint of the live ComfyUI instance."""
        fp = InstanceFingerprint()

        # PID + exe path from port
        pid = self._find_pid_on_port(8188)
        fp.pid = pid
        if pid:
            fp.python_path = self._pid_exe_path(pid)

        # Stats from API
        try:
            stats = self.client.get_system_stats()
            dev = stats.get("devices", [{}])[0] if "devices" in stats else {}
            fp.gpu_name = dev.get("name")
            fp.gpu_vram_mb = dev.get("total_memory")
            fp.comfyui_version = stats.get("comfyui_version")
            fp.extra["python_version"] = stats.get("python_version")
            fp.extra["os"] = stats.get("os")
            fp.extra["vram_free"] = dev.get("vram_free")
            fp.extra["vram_total"] = dev.get("vram_total")
        except ComfyUnreachableError:
            pass

        # H3 nodes present?
        try:
            obj_info = self.client.get_object_info()
            fp.h3_nodes_present = any(
                cls in obj_info
                for cls in (
                    "MiniMaxH3ImageToVideo",
                    "MiniMaxH3ReferenceToVideo",
                    "MiniMaxH3SigmaShift",
                )
            )
        except ComfyUnreachableError:
            pass

        # H3 models present?
        try:
            obj_info = self.client.get_object_info("MiniMaxH3ImageToVideo")
            fp.h3_models_present = bool(obj_info)
        except ComfyUnreachableError:
            pass

        return fp

    def verify_instance(self) -> bool:
        """Verify the running ComfyUI matches the expected machine profile.

        Raises ``ComfyInstanceMismatchError`` on any mismatch.
        Returns ``True`` when everything checks out.
        """
        profile = self._load_profile()

        # 1. Port listening?
        pid = self._find_pid_on_port(profile.comfyui_port)
        if pid is None:
            raise ComfyInstanceMismatchError(
                f"No process listening on port {profile.comfyui_port}"
            )

        # 2. Exe path looks like ComfyUI's Python?
        exe = self._pid_exe_path(pid)
        if exe and profile.python_path:
            if Path(exe).name.lower() != Path(profile.python_path).name.lower():
                raise ComfyInstanceMismatchError(
                    f"PID {pid} exe mismatch: expected {profile.python_path}, got {exe}"
                )

        # 3. GPU check via /system_stats
        try:
            stats = self.client.get_system_stats()
        except ComfyUnreachableError as exc:
            raise ComfyInstanceMismatchError(
                f"Cannot query /system_stats: {exc}"
            ) from exc

        dev = stats.get("devices", [{}])[0] if "devices" in stats else {}
        gpu_name = dev.get("name", "")
        if profile.expected_gpu and profile.expected_gpu.lower() not in gpu_name.lower():
            raise ComfyInstanceMismatchError(
                f"GPU mismatch: expected '{profile.expected_gpu}', got '{gpu_name}'"
            )

        # 4. H3 nodes registered?
        try:
            obj_info = self.client.get_object_info()
        except ComfyUnreachableError as exc:
            raise ComfyInstanceMismatchError(
                f"Cannot query /object_info: {exc}"
            ) from exc

        missing = [n for n in profile.h3_nodes if n not in obj_info]
        if missing:
            raise ComfyInstanceMismatchError(
                f"H3 nodes missing from /object_info: {missing}"
            )

        return True

    def is_h3_capable(self) -> bool:
        """Check that all H3 models exist and H3 nodes are registered."""
        fp = self.get_instance_fingerprint()
        return fp.h3_nodes_present and fp.h3_models_present

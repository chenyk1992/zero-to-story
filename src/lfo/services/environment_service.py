"""Environment service — orchestrate discovery + profile creation."""
from __future__ import annotations

import pathlib
import platform

from lfo.config.machine_profile import (
    ComfyUIConfig,
    HardwareConfig,
    MachineProfile,
    PlatformInfo,
    StorageConfig,
    get_machines_dir,
    load_machine_profile,
    save_machine_profile,
)
from lfo.environment.discovery import (
    DiscoveredEnvironment,
    discover_environment,
)


class EnvironmentService:
    """Orchestrate discovery, profile creation, and checks."""

    def __init__(self, machines_dir: pathlib.Path | None = None) -> None:
        self.machines_dir = machines_dir or get_machines_dir()

    def discover_and_create_profile(
        self,
        machine_id: str,
        save: bool = True,
    ) -> tuple[DiscoveredEnvironment, MachineProfile]:
        """Discover environment and create a MachineProfile."""
        discovery = discover_environment()

        storage = StorageConfig()
        if discovery.comfyui_root is not None:
            storage.comfy_input = str(discovery.comfyui_root / "input")
            storage.comfy_output = str(discovery.comfyui_root / "output")

        profile = MachineProfile(
            machine_id=machine_id,
            platform=PlatformInfo(
                os=platform.system(),
                architecture=platform.machine(),
            ),
            comfyui=ComfyUIConfig(
                base_url=f"http://127.0.0.1:{discovery.comfyui_port or 8188}",
                root=str(discovery.comfyui_root) if discovery.comfyui_root else "",
                python_path=str(discovery.python_path) if discovery.python_path else "",
            ),
            hardware=HardwareConfig(
                gpu_name=discovery.gpu_name,
                vram_mib=discovery.vram_mib,
            ),
            storage=storage,
        )

        if save:
            save_machine_profile(profile)

        return discovery, profile

    def get_or_create_profile(self, machine_id: str) -> MachineProfile:
        """Load existing profile or discover and create new one."""
        existing = load_machine_profile(machine_id)
        if existing is not None:
            return existing
        _, profile = self.discover_and_create_profile(machine_id)
        return profile

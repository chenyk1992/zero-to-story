"""LFO Configuration package — defaults, profiles, resolution."""
from .defaults import DEFAULT_COMFYUI_PORT, DEFAULT_TIMEOUT_SEC, Defaults, get_defaults
from .machine_profile import (
    MACHINE_PROFILE_VERSION,
    ComfyUIConfig,
    HardwareConfig,
    MachineProfile,
    PlatformInfo,
    StorageConfig,
    get_machines_dir,
    list_machine_ids,
    load_machine_profile,
    save_machine_profile,
    validate_machine_profile,
)

__all__ = [
    "DEFAULT_COMFYUI_PORT",
    "DEFAULT_TIMEOUT_SEC",
    "MACHINE_PROFILE_VERSION",
    "ComfyUIConfig",
    "Defaults",
    "HardwareConfig",
    "MachineProfile",
    "PlatformInfo",
    "StorageConfig",
    "get_defaults",
    "get_machines_dir",
    "list_machine_ids",
    "load_machine_profile",
    "save_machine_profile",
    "validate_machine_profile",
]

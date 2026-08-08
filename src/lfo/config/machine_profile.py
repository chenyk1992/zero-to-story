"""Machine Profile schema — per-machine configuration for LFO."""
from __future__ import annotations

import json
import os
import pathlib
from dataclasses import asdict, dataclass, field

MACHINE_PROFILE_VERSION = "lfo.machine.v2"

# Valid model swap strategies — must be measured, not assumed
MODEL_SWAP_STRATEGIES = ("hot_swap", "restart_profile", "dual_profile")


@dataclass
class PlatformInfo:
    os: str = ""
    architecture: str = ""


@dataclass
class ComfyUIConfig:
    runtime_mode: str = "attach_or_start"
    base_url: str = "http://127.0.0.1:8188"
    root: str = ""
    main_py: str = ""
    python_path: str = ""
    cli: str = "comfy"
    expected_version: str = "0.30.0"
    launch_arguments: list = field(default_factory=list)


@dataclass
class ComfyUIProfile:
    """A named runtime profile for a specific workload family.

    Each profile declares its own base_url and model_residency_key so the
    RuntimeProfileService can switch between H3 and Qwen workloads.
    """

    base_url: str = "http://127.0.0.1:8188"
    model_residency_key: str = ""
    comfyui_root: str = ""
    python_path: str = ""


@dataclass
class ResourcePolicy:
    """How this machine handles model swapping and GPU parallelism.

    model_swap_strategy must be measured empirically:
    - hot_swap: unload/load models without restart (risky on 16GB)
    - restart_profile: restart ComfyUI with new model set (safer, slower)
    - dual_profile: run two ComfyUI instances on different ports (needs RAM)
    """

    model_swap_strategy: str = "restart_profile"
    gpu_heavy_parallelism: int = 1

    def __post_init__(self) -> None:
        if self.model_swap_strategy not in MODEL_SWAP_STRATEGIES:
            raise ValueError(
                f"model_swap_strategy must be one of {MODEL_SWAP_STRATEGIES}, "
                f"got '{self.model_swap_strategy}'"
            )
        if self.gpu_heavy_parallelism < 1:
            raise ValueError("gpu_heavy_parallelism must be >= 1")


@dataclass
class StorageConfig:
    comfy_input: str = ""
    comfy_output: str = ""
    lfo_cache: str = ""
    lfo_projects: str = ""


@dataclass
class HardwareConfig:
    gpu_name: str = ""
    vram_mib: int = 0
    ram_mib: int = 0


@dataclass
class MachineProfile:
    """Complete machine-specific configuration."""

    schema_version: str = MACHINE_PROFILE_VERSION
    machine_id: str = ""
    platform: PlatformInfo = field(default_factory=PlatformInfo)
    comfyui: ComfyUIConfig = field(default_factory=ComfyUIConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    comfyui_profiles: dict[str, ComfyUIProfile] = field(default_factory=dict)
    resource_policy: ResourcePolicy = field(default_factory=ResourcePolicy)

    def to_dict(self) -> dict:
        d = asdict(self)
        # Convert nested dataclasses in comfyui_profiles
        d["comfyui_profiles"] = {
            k: asdict(v) for k, v in self.comfyui_profiles.items()
        }
        return d

    @classmethod
    def from_dict(cls, data: dict) -> MachineProfile:
        platform = PlatformInfo(**data.pop("platform", {}))
        comfyui = ComfyUIConfig(**data.pop("comfyui", {}))
        storage = StorageConfig(**data.pop("storage", {}))
        hardware = HardwareConfig(**data.pop("hardware", {}))
        # Parse comfyui_profiles
        raw_profiles = data.pop("comfyui_profiles", {})
        comfyui_profiles = {
            k: ComfyUIProfile(**v) for k, v in raw_profiles.items()
        }
        # Parse resource_policy
        raw_policy = data.pop("resource_policy", {})
        resource_policy = ResourcePolicy(**raw_policy) if raw_policy else ResourcePolicy()
        return cls(
            platform=platform,
            comfyui=comfyui,
            storage=storage,
            hardware=hardware,
            comfyui_profiles=comfyui_profiles,
            resource_policy=resource_policy,
            **data,
        )


def get_machines_dir() -> pathlib.Path:
    """Return %APPDATA%/LFO/machines/ as pathlib.Path."""
    appdata = os.environ.get("APPDATA", "")
    if not appdata:
        # Fallback for systems without APPDATA
        appdata = str(pathlib.Path.home() / "AppData" / "Roaming")
    machines_dir = pathlib.Path(appdata) / "LFO" / "machines"
    machines_dir.mkdir(parents=True, exist_ok=True)
    return machines_dir


def load_machine_profile(machine_id: str) -> MachineProfile | None:
    """Load a machine profile from APPDATA. Returns None if not found."""
    path = get_machines_dir() / f"{machine_id}.json"
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    return MachineProfile.from_dict(raw)


def save_machine_profile(profile: MachineProfile) -> None:
    """Save a machine profile to APPDATA."""
    path = get_machines_dir() / f"{profile.machine_id}.json"
    path.write_text(
        json.dumps(profile.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def list_machine_ids() -> list[str]:
    """List all saved machine IDs."""
    machines_dir = get_machines_dir()
    ids = []
    for f in machines_dir.glob("*.json"):
        ids.append(f.stem)
    return sorted(ids)


def validate_machine_profile(profile: MachineProfile) -> list[str]:
    """Validate a machine profile. Returns list of error strings (empty = valid)."""
    errors = []
    if not profile.machine_id:
        errors.append("machine_id is required")
    if profile.schema_version != MACHINE_PROFILE_VERSION:
        errors.append(
            f"schema_version must be '{MACHINE_PROFILE_VERSION}', "
            f"got '{profile.schema_version}'"
        )
    if not profile.comfyui.base_url:
        errors.append("comfyui.base_url is required")
    if not profile.comfyui.root:
        errors.append("comfyui.root is required")
    if profile.hardware.vram_mib < 0:
        errors.append("hardware.vram_mib cannot be negative")
    if profile.hardware.ram_mib < 0:
        errors.append("hardware.ram_mib cannot be negative")
    # Validate resource_policy
    if profile.resource_policy.model_swap_strategy not in MODEL_SWAP_STRATEGIES:
        errors.append(
            f"resource_policy.model_swap_strategy must be one of "
            f"{MODEL_SWAP_STRATEGIES}, "
            f"got '{profile.resource_policy.model_swap_strategy}'"
        )
    if profile.resource_policy.gpu_heavy_parallelism < 1:
        errors.append("resource_policy.gpu_heavy_parallelism must be >= 1")
    # Validate comfyui_profiles
    for name, p in profile.comfyui_profiles.items():
        if not p.base_url:
            errors.append(f"comfyui_profiles['{name}'].base_url is required")
        if not p.model_residency_key:
            errors.append(f"comfyui_profiles['{name}'].model_residency_key is required")
    return errors

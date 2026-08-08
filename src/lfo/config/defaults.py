"""Built-in configuration defaults for LFO."""
from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_TIMEOUT_SEC = 1200  # 20 minutes for agent timeout
DEFAULT_COMFYUI_PORT = 8188
DEFAULT_COMFYUI_BASE_URL = "http://127.0.0.1:8188"

DEFAULT_MIN_FREE_VRAM_MIB = 2048  # 2GB
DEFAULT_MIN_FREE_RAM_MIB = 4096  # 4GB
DEFAULT_MIN_FREE_DISK_MIB = 5120  # 5GB

SUPPORTED_WORKFLOW_FAMILIES = ["h3_fl2va", "h3_ref2va"]
SUPPORTED_TASK_TYPES = ["video.h3", "visual.generate", "visual.edit", "audio.tts"]
SUPPORTED_ASSET_TYPES = ["image", "video", "audio", "subtitle", "document"]

SMOKE_LEVELS = ["none", "static", "runtime", "light", "full"]


@dataclass
class Defaults:
    """All built-in defaults in one place."""

    timeout_sec: int = DEFAULT_TIMEOUT_SEC
    comfyui_port: int = DEFAULT_COMFYUI_PORT
    comfyui_base_url: str = DEFAULT_COMFYUI_BASE_URL
    min_free_vram_mib: int = DEFAULT_MIN_FREE_VRAM_MIB
    min_free_ram_mib: int = DEFAULT_MIN_FREE_RAM_MIB
    min_free_disk_mib: int = DEFAULT_MIN_FREE_DISK_MIB
    smoke_levels: list = field(default_factory=lambda: list(SMOKE_LEVELS))


def get_defaults() -> Defaults:
    return Defaults()

"""4-layer configuration resolution with JSON Pointer --set support."""
from __future__ import annotations

import copy
import json
import os
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any

from .defaults import get_defaults
from .machine_profile import MachineProfile, load_machine_profile

# --------------------------------------------------------------------------- #
# JSON Pointer
# --------------------------------------------------------------------------- #


def apply_json_pointer(base: dict, pointer: str, value: Any) -> dict:
    """Apply a JSON Pointer path to set a value in a dict.

    Supports ``/`` separated paths with ``~0`` for ``~`` and ``~1`` for ``/``.
    Modifies *base* in-place and returns it.

    Examples:
        apply_json_pointer({}, "/comfyui/port", 8188) -> {"comfyui": {"port": 8188}}
        apply_json_pointer({"a": {"b": 1}}, "/a/b", 2) -> {"a": {"b": 2}}
    """
    if not pointer.startswith("/"):
        raise ValueError(f"JSON Pointer must start with '/': {pointer}")

    parts = pointer[1:].split("/")
    # Unescape ~1 -> / and ~0 -> ~
    parts = [p.replace("~1", "/").replace("~0", "~") for p in parts]

    current = base
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]

    current[parts[-1]] = value
    return base


# --------------------------------------------------------------------------- #
# Layer merging
# --------------------------------------------------------------------------- #


def merge_config_layers(base: dict, override: dict) -> dict:
    """Merge two config dicts.

    Rules:
    - Objects: recursive merge
    - Scalars: override wins
    - Arrays: replace entirely (no concat)
    - null: explicit clear (remove key)
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if value is None:
            # Explicit clear
            result.pop(key, None)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_config_layers(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


# --------------------------------------------------------------------------- #
# Environment variable expansion
# --------------------------------------------------------------------------- #

_ENV_VAR_RE = re.compile(r"\$(\w+|\{[^}]*\})|%(\w+)%")


def expand_env_vars(value: Any) -> Any:
    """Expand environment variables in config values.

    Supports: %VAR%, ${VAR}, $VAR
    Only applies to string values within the resolved config.
    """
    if isinstance(value, str):
        return _expand_string(value)
    elif isinstance(value, dict):
        return {k: expand_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [expand_env_vars(item) for item in value]
    return value


def _expand_string(s: str) -> str:
    """Expand env vars in a single string."""
    # Handle %VAR% pattern
    def replace_pct(match: re.Match[str]) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name) or match.group(0)

    s = re.sub(r"%(\w+)%", replace_pct, s)

    # Handle ${VAR} and $VAR patterns
    def replace_dollar(match: re.Match[str]) -> str:
        var_name = match.group(1)
        if var_name.startswith("{") and var_name.endswith("}"):
            var_name = var_name[1:-1]
        return os.environ.get(var_name) or match.group(0)

    s = re.sub(r"\$(\w+|\{[^}]*\})", replace_dollar, s)
    return s


# --------------------------------------------------------------------------- #
# Schema validation (minimal)
# --------------------------------------------------------------------------- #


def validate_against_schema(config: dict, schema: dict) -> list[str]:
    """Validate config against a JSON Schema. Returns list of errors.

    Minimal implementation: checks required properties and type constraints.
    """
    errors = []
    if not isinstance(config, dict):
        errors.append("Config must be a dict")
        return errors

    required = schema.get("required", [])
    for prop in required:
        if prop not in config:
            errors.append(f"Missing required property: {prop}")

    properties = schema.get("properties", {})
    for key, value in config.items():
        if key in properties:
            prop_schema = properties[key]
            expected_type = prop_schema.get("type")
            if expected_type:
                type_map = {
                    "string": str,
                    "integer": int,
                    "number": (int, float),
                    "boolean": bool,
                    "array": list,
                    "object": dict,
                }
                py_type = type_map.get(expected_type)
                if py_type and not isinstance(value, py_type):
                    errors.append(
                        f"Property '{key}' expected type '{expected_type}', "
                        f"got '{type(value).__name__}'"
                    )

            # Check enum
            if "enum" in prop_schema and value not in prop_schema["enum"]:
                errors.append(
                    f"Property '{key}' value '{value}' not in enum {prop_schema['enum']}"
                )

    return errors


# --------------------------------------------------------------------------- #
# Resolved Config
# --------------------------------------------------------------------------- #


@dataclass
class ResolvedConfig:
    """Final resolved configuration after merging all layers."""

    raw: dict
    machine_id: str = ""
    machine_profile: MachineProfile | None = None
    _defaults: dict = field(default_factory=dict, repr=False)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from resolved config by dotted key path."""
        parts = key.split(".")
        current = self.raw
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current


# --------------------------------------------------------------------------- #
# Main resolver
# --------------------------------------------------------------------------- #


def resolve_config(
    project_path: pathlib.Path | None = None,
    machine_id: str = "",
    cli_overrides: dict | None = None,
) -> ResolvedConfig:
    """Resolve final config from 4 layers + CLI overrides.

    Priority (low to high):
    1. Built-in defaults (config/defaults.py)
    2. User global config (%APPDATA%/LFO/config.json)
    3. Machine profile (%APPDATA%/LFO/machines/<machine_id>.json)
    4. Project config (project/config.json)
    5. CLI --set overrides (JSON Pointer)
    """
    # Layer 1: Built-in defaults
    defaults = get_defaults()
    config = {
        "timeout_sec": defaults.timeout_sec,
        "comfyui": {
            "port": defaults.comfyui_port,
            "base_url": defaults.comfyui_base_url,
        },
        "min_free_vram_mib": defaults.min_free_vram_mib,
        "min_free_ram_mib": defaults.min_free_ram_mib,
        "min_free_disk_mib": defaults.min_free_disk_mib,
        "smoke_levels": list(defaults.smoke_levels),
    }

    # Layer 2: User global config
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        global_config_path = pathlib.Path(appdata) / "LFO" / "config.json"
        if global_config_path.exists():
            global_config = json.loads(global_config_path.read_text(encoding="utf-8"))
            config = merge_config_layers(config, global_config)

    # Layer 3: Machine profile
    profile = None
    if machine_id:
        profile = load_machine_profile(machine_id)
        if profile is not None:
            # Extract relevant config sections from profile
            config = merge_config_layers(config, {
                "comfyui": {
                    "base_url": profile.comfyui.base_url,
                    "port": _extract_port(profile.comfyui.base_url),
                    "root": profile.comfyui.root,
                    "python_path": profile.comfyui.python_path,
                    "expected_version": profile.comfyui.expected_version,
                },
                "storage": {
                    "comfy_input": profile.storage.comfy_input,
                    "comfy_output": profile.storage.comfy_output,
                    "lfo_cache": profile.storage.lfo_cache,
                    "lfo_projects": profile.storage.lfo_projects,
                },
                "hardware": {
                    "gpu_name": profile.hardware.gpu_name,
                    "vram_mib": profile.hardware.vram_mib,
                    "ram_mib": profile.hardware.ram_mib,
                },
            })

    # Layer 4: Project config
    if project_path is not None:
        project_config_path = pathlib.Path(project_path) / "config.json"
        if project_config_path.exists():
            project_config = json.loads(project_config_path.read_text(encoding="utf-8"))
            config = merge_config_layers(config, project_config)

    # Expand env vars on the resolved config
    config = expand_env_vars(config)

    # Layer 5: CLI overrides
    if cli_overrides:
        config = merge_config_layers(config, cli_overrides)

    return ResolvedConfig(
        raw=config,
        machine_id=machine_id,
        machine_profile=profile,
    )


def _extract_port(base_url: str) -> int:
    """Extract port number from a base URL like http://127.0.0.1:8188."""
    match = re.search(r":(\d+)(?:/|$)", base_url)
    if match:
        return int(match.group(1))
    return 8188

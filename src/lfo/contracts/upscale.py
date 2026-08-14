"""Optional post-generation video-upscale configuration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


UPSCALE_EXTENSION_KEY = "upscale"
DEFAULT_SCALE_MULTIPLIER = 2.0
MAX_SEED = 2**64 - 1


@dataclass(frozen=True)
class UpscaleOptionIssue:
    """A validation issue for the supported ``extensions.upscale`` fields."""

    path: str
    message: str
    code: str
    value: Any = None


@dataclass(frozen=True)
class UpscaleOptions:
    """Resolved post-generation upscale settings for one clip."""

    enabled: bool = False
    scale_multiplier: float = DEFAULT_SCALE_MULTIPLIER
    seed: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "scale_multiplier": self.scale_multiplier,
            "seed": self.seed,
        }


def validate_upscale_options(config: object, path: str) -> list[UpscaleOptionIssue]:
    """Validate one ``upscale`` extension object without rejecting other extensions."""
    if not isinstance(config, dict):
        return [
            UpscaleOptionIssue(
                path,
                "expected object",
                "type",
                config,
            )
        ]

    issues: list[UpscaleOptionIssue] = []
    if "enabled" in config and not isinstance(config["enabled"], bool):
        issues.append(
            UpscaleOptionIssue(
                f"{path}.enabled",
                "expected boolean",
                "type",
                config["enabled"],
            )
        )

    if "scale_multiplier" in config:
        multiplier = config["scale_multiplier"]
        if isinstance(multiplier, bool) or not isinstance(multiplier, (int, float)):
            issues.append(
                UpscaleOptionIssue(
                    f"{path}.scale_multiplier",
                    "expected positive number",
                    "type",
                    multiplier,
                )
            )
        elif float(multiplier) <= 0:
            issues.append(
                UpscaleOptionIssue(
                    f"{path}.scale_multiplier",
                    "must be > 0",
                    "minimum",
                    multiplier,
                )
            )

    if "seed" in config:
        seed = config["seed"]
        if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
            issues.append(
                UpscaleOptionIssue(
                    f"{path}.seed",
                    "expected integer or null",
                    "type",
                    seed,
                )
            )
        elif isinstance(seed, int) and not 0 <= seed <= MAX_SEED:
            issues.append(
                UpscaleOptionIssue(
                    f"{path}.seed",
                    f"must be between 0 and {MAX_SEED}",
                    "range",
                    seed,
                )
            )
    return issues


def resolve_upscale_options(
    package_extensions: object,
    clip_extensions: object,
) -> UpscaleOptions:
    """Overlay clip options onto package defaults and return normalized settings."""
    package_config = _extension_config(package_extensions, "package extensions")
    clip_config = _extension_config(clip_extensions, "clip extensions")
    merged = {**package_config, **clip_config}
    issues = validate_upscale_options(merged, "upscale")
    if issues:
        raise ValueError(issues[0].message)
    return UpscaleOptions(
        enabled=bool(merged.get("enabled", False)),
        scale_multiplier=float(merged.get("scale_multiplier", DEFAULT_SCALE_MULTIPLIER)),
        seed=merged.get("seed"),
    )


def _extension_config(extensions: object, source: str) -> dict[str, Any]:
    if not isinstance(extensions, dict) or UPSCALE_EXTENSION_KEY not in extensions:
        return {}
    config = extensions[UPSCALE_EXTENSION_KEY]
    if not isinstance(config, dict):
        raise ValueError(f"{source} upscale configuration must be an object")
    return dict(config)

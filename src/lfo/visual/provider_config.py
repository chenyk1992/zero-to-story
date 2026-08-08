"""Provider config validation and CJ1 hashing (spec §9).

Three provider types:
- manual: human-driven, no required fields
- delegated: delegated to external agent, requires allowed_recipients allowlist
- managed: direct API integration, requires endpoint

Secrets must be referenced (auth_ref / env name), never stored raw.
"""
from __future__ import annotations

from typing import Any

from lfo.visual.errors import VisualProviderError
from lfo.visual.hashing import hash_visual_object

# Allowed provider types
_PROVIDER_TYPES = ("manual", "delegated", "managed")

# Fields that look like raw secrets (heuristic: _key, _secret, _token, _password)
_SECRET_SUFFIXES = ("_key", "_secret", "_token", "_password", "_credential")


def _detect_raw_secret(config: dict[str, Any]) -> str | None:
    """Detect raw secret values in config. Returns offending key or None."""
    for key, value in config.items():
        lower = key.lower()
        if any(lower.endswith(s) for s in _SECRET_SUFFIXES):
            if isinstance(value, str) and not value.startswith(("env:", "ref:", "vault:")):
                return key
    return None


def validate_provider_config(provider_type: str, config: dict[str, Any]) -> dict[str, Any]:
    """Validate provider config for the given type.

    Args:
        provider_type: One of 'manual', 'delegated', 'managed'.
        config: Raw config dict.

    Returns:
        Normalized config with provider_type injected.

    Raises:
        VisualProviderError: On invalid type, missing required fields, or raw secrets.
    """
    if provider_type not in _PROVIDER_TYPES:
        raise VisualProviderError(
            f"Unknown provider_type '{provider_type}'. Must be one of {_PROVIDER_TYPES}"
        )

    # Check for raw secrets
    secret_key = _detect_raw_secret(config)
    if secret_key is not None:
        raise VisualProviderError(
            f"Raw secret in config field '{secret_key}'. "
            "Use auth_ref / env: prefix / ref: / vault: instead."
        )

    if provider_type == "managed":
        if "endpoint" not in config or not config["endpoint"]:
            raise VisualProviderError(
                "Managed provider requires 'endpoint' field"
            )
    elif provider_type == "delegated":
        recipients = config.get("allowed_recipients")
        if not recipients or not isinstance(recipients, list) or len(recipients) == 0:
            raise VisualProviderError(
                "Delegated provider requires non-empty 'allowed_recipients' list"
            )

    # Return normalized config
    result = dict(config)
    result["provider_type"] = provider_type
    return result


def hash_provider_config(provider_type: str, config: dict[str, Any]) -> str:
    """Compute LFO-CJ1 hash of a provider config (spec §10).

    Args:
        provider_type: The provider type.
        config: Raw config dict.

    Returns:
        SHA-256 hex digest of canonical serialization.
    """
    obj: dict[str, Any] = {
        "provider_type": provider_type,
        **config,
    }
    return hash_visual_object(obj)

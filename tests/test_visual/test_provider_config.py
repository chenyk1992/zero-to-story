"""Tests for provider config validation."""
from __future__ import annotations

import pytest

from lfo.visual.errors import VisualProviderError
from lfo.visual.provider_config import validate_provider_config


def test_managed_config_with_endpoint_valid():
    """Managed provider requires endpoint."""
    config = validate_provider_config("managed", {
        "endpoint": "http://localhost:9000/generate",
        "timeout": 120,
    })
    assert config["endpoint"] == "http://localhost:9000/generate"


def test_managed_config_missing_endpoint_raises():
    with pytest.raises(VisualProviderError, match="endpoint"):
        validate_provider_config("managed", {
            "timeout": 120,
        })


def test_delegated_config_with_allowlist_valid():
    """Delegated provider requires allowed_recipients allowlist."""
    config = validate_provider_config("delegated", {
        "allowed_recipients": ["agent_1", "agent_2"],
    })
    assert "agent_1" in config["allowed_recipients"]


def test_delegated_config_empty_allowlist_raises():
    with pytest.raises(VisualProviderError, match="allowed_recipients"):
        validate_provider_config("delegated", {
            "allowed_recipients": [],
        })


def test_delegated_config_missing_allowlist_raises():
    with pytest.raises(VisualProviderError, match="allowed_recipients"):
        validate_provider_config("delegated", {})


def test_manual_config_minimal_valid():
    """Manual provider has no required fields."""
    config = validate_provider_config("manual", {})
    assert config["provider_type"] == "manual"


def test_manual_config_with_auth_ref_valid():
    """Secrets only as refs — auth_ref is allowed."""
    config = validate_provider_config("manual", {
        "auth_ref": "env:MY_API_KEY",
    })
    assert config["auth_ref"] == "env:MY_API_KEY"


def test_unknown_provider_type_raises():
    with pytest.raises(VisualProviderError, match="provider_type"):
        validate_provider_config("super_ai", {})


def test_secret_in_config_raises():
    """Raw secrets in config must be rejected."""
    with pytest.raises(VisualProviderError, match="secret"):
        validate_provider_config("managed", {
            "endpoint": "http://localhost:9000",
            "api_key": "sk-actual-secret-value",
        })


def test_config_hash_stable():
    """Same config → same CJ1 hash (order independent)."""
    from lfo.visual.provider_config import hash_provider_config
    a = hash_provider_config("managed", {"endpoint": "http://x", "timeout": 30})
    b = hash_provider_config("managed", {"timeout": 30, "endpoint": "http://x"})
    assert a == b

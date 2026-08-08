"""Tests for VisualTaskCompiler identity."""
from __future__ import annotations

from lfo.visual.task_compiler import (
    VisualTaskCompilerIdentity,
    get_compiler_identity,
)


def test_compiler_semver_is_1_0_0():
    identity = get_compiler_identity()
    assert identity.semver == "1.0.0"


def test_compiler_name_is_lfo_visual():
    identity = get_compiler_identity()
    assert identity.name == "lfo-visual"


def test_compiler_identity_is_frozen():
    identity = get_compiler_identity()
    try:
        identity.semver = "2.0.0"
        raised = False
    except AttributeError:
        raised = True
    assert raised


def test_compiler_identity_has_source_hash():
    identity = get_compiler_identity()
    # source_hash may be None in dev, but field must exist
    assert hasattr(identity, "source_hash")


def test_compiler_identity_fields():
    identity = get_compiler_identity()
    assert isinstance(identity, VisualTaskCompilerIdentity)
    assert identity.name
    assert identity.semver

"""Canonical hashing for VideoExecutionPackage v1."""
from __future__ import annotations

from lfo.core.canonical import hash_value

from .package import VideoExecutionPackage


def package_content_hash(package: VideoExecutionPackage) -> str:
    """Compute the LFO-CJ1 canonical hash of a Package.

    The hash covers every field that affects output. Because ``to_dict()``
    emits a deterministic shape (omitting empty optionals, defaults included),
    the same Package always yields the same hash.
    """
    return hash_value(package.to_dict())

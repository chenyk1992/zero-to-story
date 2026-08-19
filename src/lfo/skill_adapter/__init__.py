"""Skill adapters — transform creative skill output into VideoExecutionPackage.

Each adapter is a pure function from a skill-specific format to the
canonical VideoExecutionPackage v1 contract. Adapters contain no I/O.
"""
from __future__ import annotations

from . import mg_voiceover, product_promo, virtual_presenter, zero_to_story
from .virtual_presenter import build_assembly_package, build_shot_package

__all__ = [
    "build_assembly_package",
    "build_shot_package",
    "mg_voiceover",
    "product_promo",
    "virtual_presenter",
    "zero_to_story",
]

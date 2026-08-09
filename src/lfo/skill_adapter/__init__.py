"""Skill adapters — transform creative skill output into VideoExecutionPackage.

Each adapter is a pure function from a skill-specific format to the
canonical VideoExecutionPackage v1 contract. Adapters contain no I/O.
"""
from __future__ import annotations

__all__ = ["zero_to_story", "product_promo"]

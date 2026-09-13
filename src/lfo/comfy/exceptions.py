"""Errors raised by the Canvas Comfy submission guard."""

from __future__ import annotations


class LfoComfyError(Exception):
    """A Canvas Comfy submission cannot be admitted or reconciled safely."""

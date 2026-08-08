"""Terminal color support — ANSI codes with auto-detection.

Respects NO_COLOR env var and non-TTY output.
"""
from __future__ import annotations

import os
import sys


def _supports_color() -> bool:
    """Detect if the terminal supports ANSI colors."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return False
    return True


_enabled = _supports_color()


def disable_colors() -> None:
    global _enabled
    _enabled = False


def enable_colors() -> None:
    global _enabled
    _enabled = True


def colorize(text: str, *codes: str) -> str:
    """Wrap text in ANSI codes if colors are enabled."""
    if not _enabled:
        return text
    return f"{''.join(codes)}{text}\033[0m"


def green(text: str) -> str:
    return colorize(text, "\033[32m")


def red(text: str) -> str:
    return colorize(text, "\033[31m")


def yellow(text: str) -> str:
    return colorize(text, "\033[33m")


def blue(text: str) -> str:
    return colorize(text, "\033[34m")


def cyan(text: str) -> str:
    return colorize(text, "\033[36m")


def bold(text: str) -> str:
    return colorize(text, "\033[1m")


def dim(text: str) -> str:
    return colorize(text, "\033[2m")

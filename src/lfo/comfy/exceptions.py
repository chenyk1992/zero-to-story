"""Custom exceptions for LFO ComfyUI integration."""

from __future__ import annotations


class LfoComfyError(Exception):
    """Base exception for all LFO ComfyUI errors."""

    pass


class ComfyCliTimeoutError(LfoComfyError):
    """The official ``comfy`` CLI stopped waiting before a workflow finished."""

    def __init__(self, message: str, *, prompt_id: str | None = None) -> None:
        super().__init__(message)
        self.prompt_id = prompt_id


class ComfyUnreachableError(LfoComfyError):
    """ComfyUI service is not reachable on the configured port."""

    pass


class ComfyInstanceMismatchError(LfoComfyError):
    """Running ComfyUI instance does not match expected machine profile."""

    pass


class WorkflowFormatError(LfoComfyError):
    """Workflow file is not in the expected format."""

    pass


class BindingNotFoundError(LfoComfyError):
    """No node found matching the binding selector criteria."""

    pass


class BindingAmbiguousError(LfoComfyError):
    """Multiple nodes match the binding selector criteria."""

    pass


class OutputNotFoundError(LfoComfyError):
    """Expected output files were not found after generation."""

    pass


class OutputCardinalityError(LfoComfyError):
    """Unexpected number of output files discovered."""

    pass


class OutputUnstableError(LfoComfyError):
    """Output file size is still changing (incomplete write)."""

    pass

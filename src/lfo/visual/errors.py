"""Custom exceptions for the Visual domain layer."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lfo.core.state_machine import TaskStatus
    from lfo.visual.stages import VisualStage


class VisualError(Exception):
    """Base exception for visual production errors."""
    pass


class IllegalStateTransitionError(VisualError):
    """Raised when a (TaskStatus, VisualStage) pair is not a legal combination."""

    def __init__(
        self,
        status: TaskStatus | None = None,
        stage: VisualStage | None = None,
        message: str | None = None,
    ):
        if message is None:
            message = (
                f"Illegal visual state combination: "
                f"status={status}, stage={stage}"
            )
        super().__init__(message)
        self.status = status
        self.stage = stage


class VisualContractError(VisualError):
    """Raised when a visual task contract is invalid."""
    pass


class VisualProviderError(VisualError):
    """Raised when a provider operation fails."""
    pass


class VisualResultError(VisualError):
    """Raised when result import/QC fails."""
    pass

"""Base classes for visual providers (spec §15–17).

Three provider kinds:
- ManualProvider: human-driven exchange, no submit/collect
- DelegatedProvider: delegated agent exchange
- ManagedVisualProvider: direct API with submit/collect/cancel
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from lfo.visual.capabilities import ProviderProbeResult, VisualCapabilities


class VisualProvider(ABC):
    """Base class for all visual providers."""

    @property
    @abstractmethod
    def provider_revision_id(self) -> str:
        """The provider revision ID this instance was created from."""
        ...

    @abstractmethod
    def declared_capabilities(self) -> VisualCapabilities:
        """Return the capabilities declared at registration."""
        ...

    @abstractmethod
    def probe(self) -> ProviderProbeResult:
        """Check availability and return current capabilities."""
        ...


class ExchangeVisualProvider(VisualProvider, ABC):
    """Provider that uses export/import exchange pattern."""

    @abstractmethod
    def export_task(self, task_id: str) -> str:
        """Export a task for external processing.

        Returns the exchange execution ID.
        """
        ...

    @abstractmethod
    def import_result(self, manifest: dict) -> str:
        """Import a result from external processing.

        Returns the asset ID.
        """
        ...


class ManagedVisualProvider(VisualProvider, ABC):
    """Provider that supports direct managed execution."""

    @abstractmethod
    def submit(self, task_package: dict) -> str:
        """Submit a task for managed execution.

        Returns the execution ID.
        """
        ...

    @abstractmethod
    def collect(self, execution_id: str) -> dict:
        """Collect results from a managed execution.

        Returns the result manifest dict.
        """
        ...

    @abstractmethod
    def cancel(self, execution_id: str) -> None:
        """Cancel a running execution."""
        ...

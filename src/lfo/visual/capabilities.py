"""Visual provider capabilities and probe results."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VisualCapabilities:
    """Describes what a visual provider can do.

    Used both for provider registration and for capability-matching
    during routing.
    """
    text_to_image: bool = False
    reference_to_image: bool = False
    multi_reference: bool = False
    image_edit: bool = False
    inpainting: bool = False
    character_multiview: bool = False
    storyboard_frame: bool = False
    transparent_output: bool = False

    def supports(self, operation: str) -> bool:
        """Check whether this capability set supports a given operation."""
        mapping = {
            "text_to_image": self.text_to_image,
            "reference_to_image": self.reference_to_image,
            "multi_reference": self.multi_reference,
            "image_edit": self.image_edit,
            "inpainting": self.inpainting,
            "character_multiview": self.character_multiview,
            "storyboard_frame": self.storyboard_frame,
        }
        return mapping.get(operation, False)


@dataclass(frozen=True)
class ProviderProbeResult:
    """Result of probing a provider's availability and capabilities."""
    available: bool
    checked_at: str
    latency_ms: int | None
    provider_version: str | None
    capabilities: VisualCapabilities
    error_code: str | None
    message: str | None

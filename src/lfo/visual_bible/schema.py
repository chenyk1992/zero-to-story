"""Visual Bible schema definition and validation."""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColorSpec:
    name: str
    hex_code: str
    usage: str  # 'primary' | 'secondary' | 'accent' | 'background'


@dataclass
class StyleReference:
    description: str
    reference_images: list[str] = field(default_factory=list)  # asset_ids


@dataclass
class VisualBible:
    """Complete visual bible for a project."""

    project_id: str
    content_hash: str | None = None
    revision_id: str | None = None

    # Visual specification
    characters: dict[str, Any] = field(default_factory=dict)
    scenes: dict[str, Any] = field(default_factory=dict)
    color_palette: list[ColorSpec] = field(default_factory=list)
    style_references: list[StyleReference] = field(default_factory=list)
    props: dict[str, Any] = field(default_factory=dict)
    cinematography: dict[str, Any] = field(default_factory=dict)

    # Metadata
    version: int = 1
    created_by: str = "user"
    parent_revision_id: str | None = None

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON storage."""
        return {
            "project_id": self.project_id,
            "characters": self.characters,
            "scenes": self.scenes,
            "color_palette": [
                dataclasses.asdict(c) for c in self.color_palette
            ],
            "style_references": [
                dataclasses.asdict(s) for s in self.style_references
            ],
            "props": self.props,
            "cinematography": self.cinematography,
            "version": self.version,
            "created_by": self.created_by,
        }

    @classmethod
    def from_dict(cls, data: dict) -> VisualBible:
        """Deserialize from dictionary."""
        color_palette = [
            ColorSpec(**c) for c in data.get("color_palette", [])
        ]
        style_references = [
            StyleReference(**s) for s in data.get("style_references", [])
        ]
        return cls(
            project_id=data["project_id"],
            characters=data.get("characters", {}),
            scenes=data.get("scenes", {}),
            color_palette=color_palette,
            style_references=style_references,
            props=data.get("props", {}),
            cinematography=data.get("cinematography", {}),
            version=data.get("version", 1),
            created_by=data.get("created_by", "user"),
        )

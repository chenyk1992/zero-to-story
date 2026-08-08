"""Image Request schema — structured instructions for agent image generation.

LFO writes image request files (JSON) to the workspace. Agent tools
(MiniMax Code / Codex) read these files, call their image generation
capabilities, and write the results back.

File layout:
    workspace/<novel>/<chapter>/image_requests/
        batch_character_sheets_001.json        ← request
        batch_character_sheets_001_results.json ← agent response

This module defines the data structures for both request and response.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Image request
# ---------------------------------------------------------------------------


@dataclass
class ImageRequest:
    """A single image generation request.

    Produced by LFO, consumed by an agent tool.
    """
    request_id: str = field(default_factory=lambda: f"imgreq_{uuid.uuid4().hex[:8]}")
    type: str = ""                 # "character_sheet" | "storyboard_preview"
    status: str = "pending"        # "pending" | "in_progress" | "completed" | "failed"
    prompt: str = ""               # fully rendered prompt for the image model
    aspect_ratio: str = "16:9"
    resolution: str = "2K"
    output_path: str = ""          # where the agent should save the image
    # Type-specific metadata
    character_id: str = ""         # for type="character_sheet"
    shot_range: list[str] = field(default_factory=list)  # for type="storyboard_preview"
    # Result fields (filled by agent after generation)
    result_asset_path: str = ""
    result_seed: int = 0
    error: str = ""
    created_at: str = ""           # ISO 8601
    completed_at: str = ""         # ISO 8601

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "type": self.type,
            "status": self.status,
            "prompt": self.prompt,
            "aspect_ratio": self.aspect_ratio,
            "resolution": self.resolution,
            "output_path": self.output_path,
            "character_id": self.character_id,
            "shot_range": self.shot_range,
            "result_asset_path": self.result_asset_path,
            "result_seed": self.result_seed,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ImageRequest:
        return cls(**data)


@dataclass
class ImageRequestBatch:
    """A batch of image requests for one pipeline phase.

    One batch = one JSON file on disk.
    """
    batch_id: str = field(default_factory=lambda: f"batch_{uuid.uuid4().hex[:8]}")
    project_id: str = ""
    phase: str = ""                # "character_sheets" | "storyboard_preview"
    requests: list[ImageRequest] = field(default_factory=list)
    created_at: str = ""           # ISO 8601

    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "project_id": self.project_id,
            "phase": self.phase,
            "requests": [r.to_dict() for r in self.requests],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ImageRequestBatch:
        requests = [ImageRequest.from_dict(r) for r in data.pop("requests", [])]
        return cls(requests=requests, **data)


# ---------------------------------------------------------------------------
# Image result (agent response)
# ---------------------------------------------------------------------------


@dataclass
class ImageResult:
    """Result for a single image request, written by the agent."""
    request_id: str = ""
    status: str = ""               # "completed" | "failed"
    result_asset_path: str = ""
    result_seed: int = 0
    error: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "status": self.status,
            "result_asset_path": self.result_asset_path,
            "result_seed": self.result_seed,
            "error": self.error,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ImageResult:
        return cls(**data)


@dataclass
class ImageResultBatch:
    """Agent response containing results for a batch of requests."""
    batch_id: str = ""
    results: list[ImageResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "results": [r.to_dict() for r in self.results],
        }

    @classmethod
    def from_dict(cls, data: dict) -> ImageResultBatch:
        results = [ImageResult.from_dict(r) for r in data.pop("results", [])]
        return cls(results=results, **data)


# ---------------------------------------------------------------------------
# Serialization helpers (read/write JSON files)
# ---------------------------------------------------------------------------


def write_batch(batch: ImageRequestBatch, path: str) -> None:
    """Write an ImageRequestBatch to a JSON file."""
    import json
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(batch.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def read_batch(path: str) -> ImageRequestBatch:
    """Read an ImageRequestBatch from a JSON file."""
    import json
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Batch file not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    return ImageRequestBatch.from_dict(data)


def write_results(batch: ImageResultBatch, path: str) -> None:
    """Write an ImageResultBatch to a JSON file."""
    import json
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(batch.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def read_results(path: str) -> ImageResultBatch:
    """Read an ImageResultBatch from a JSON file."""
    import json
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Results file not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    return ImageResultBatch.from_dict(data)

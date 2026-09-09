"""Project-scoped runtime locations. Media stays separate from internal state."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CanvasSettings:
    project_root: Path
    data_dir: Path
    media_root: Path
    port: int = 8765
    image_concurrency: int = 2

    @classmethod
    def resolve(
        cls,
        project_root: Path | None = None,
        data_dir: Path | None = None,
        media_root: Path | None = None,
        port: int = 8765,
    ) -> CanvasSettings:
        root = (project_root or Path.cwd()).resolve()
        project_key = hashlib.sha256(str(root).casefold().encode()).hexdigest()[:12]
        if data_dir is None:
            override = os.environ.get("LFO_CANVAS_DATA")
            appdata = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
            base = Path(appdata) if appdata else Path.home() / ".local" / "share"
            data_dir = (
                Path(override) if override else base / "zero-to-story" / "canvas" / project_key
            )
        workspace = Path(os.environ.get("LFO_WORKSPACE", str(root / "workspace")))
        image_concurrency = int(os.environ.get("LFO_IMAGE_CONCURRENCY", "2"))
        if image_concurrency not in {1, 2}:
            raise ValueError("LFO_IMAGE_CONCURRENCY must be 1 or 2")
        return cls(
            root, data_dir.resolve(), (media_root or workspace).resolve(), port, image_concurrency
        )

    @property
    def database(self) -> Path:
        return self.data_dir / "canvas.sqlite3"

    @property
    def frontend(self) -> Path:
        return self.project_root / "web" / "canvas" / "dist"

    @property
    def discovery(self) -> Path:
        return self.data_dir / "server.json"

    def output_dir(self, canvas_id: str, run_id: str) -> Path:
        return self.media_root / "projects" / canvas_id / "outputs" / run_id

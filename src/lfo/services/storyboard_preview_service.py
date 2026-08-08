"""StoryboardPreviewService — build storyboard preview image requests.

Groups panels into 8-per-sheet (2x4 grid) with continuity chaining:
- Sheet 1: Panel 01-08
- Sheet 2: Panel 08-15 (panel 1 = panel 08, bridging from sheet 1)
- Sheet 3: Panel 15-22 (panel 1 = panel 15)
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from lfo.core.database import Database
from lfo.storyboard.prompts.storyboard_preview_v1 import render_storyboard_preview_prompt
from lfo.storyboard.storyboard import Storyboard
from lfo.visual.image_request import (
    ImageRequest,
    ImageRequestBatch,
    ImageResult,
    ImageResultBatch,
    read_results,
    write_batch,
)


logger = logging.getLogger(__name__)


@dataclass
class PreviewResult:
    """Result of collecting a single preview sheet generation."""
    sheet_id: str
    success: bool
    asset_id: str = ""
    file_path: str = ""
    error: str = ""


class StoryboardPreviewService:
    """Build and collect storyboard preview image requests."""

    PANELS_PER_SHEET = 8  # 2x4 grid
    OVERLAP_PANELS = 1

    def __init__(self, db: Database, output_root: str = "") -> None:
        self.db = db
        self.output_root = Path(output_root) if output_root else Path(".")

    def build_requests(
        self,
        storyboard: Storyboard,
        project_id: str,
    ) -> ImageRequestBatch:
        """Build preview sheet requests for all panels."""
        batch = ImageRequestBatch(
            batch_id=f"batch_preview_{uuid.uuid4().hex[:8]}",
            project_id=project_id,
            phase="storyboard_preview",
            created_at=datetime.now(UTC).isoformat(),
        )

        panels = storyboard.panels
        if not panels:
            logger.info("No panels in storyboard, skipping preview")
            return batch

        sheet_ranges: list[tuple[int, int]] = []
        step = self.PANELS_PER_SHEET - self.OVERLAP_PANELS
        start = 0
        while start < len(panels):
            end = min(start + self.PANELS_PER_SHEET, len(panels))
            sheet_ranges.append((start, end))
            if end >= len(panels):
                break
            start = end - self.OVERLAP_PANELS

        total_sheets = len(sheet_ranges)

        for sheet_idx, (start, end) in enumerate(sheet_ranges):
            sheet_number = sheet_idx + 1
            sheet_panels = panels[start:end]
            is_bridge = sheet_idx > 0
            bridge_description = ""

            if is_bridge and start > 0:
                bridge_panel = panels[start]
                beat = (
                    storyboard.beat_by_id(bridge_panel.beat_ids[0])
                    if bridge_panel.beat_ids
                    else None
                )
                framing = beat.framing if beat else "medium"
                desc = beat.description if beat else ""
                bridge_description = f"[{framing}] {desc}"

            prompt = render_storyboard_preview_prompt(
                storyboard=storyboard,
                panels=sheet_panels,
                sheet_number=sheet_number,
                total_sheets=total_sheets,
                is_bridge=is_bridge,
                bridge_description=bridge_description,
            )

            output_path = str(
                self.output_root / storyboard.project.novel_id / storyboard.project.chapter_id / "ref_images" / f"storyboard_preview_sheet{sheet_number:02d}.png"
            )

            req = ImageRequest(
                request_id=f"imgreq_preview_sheet{sheet_number:02d}",
                type="storyboard_preview",
                status="pending",
                prompt=prompt,
                aspect_ratio="16:9",
                resolution="2K",
                output_path=output_path,
                shot_range=[p.panel_id for p in sheet_panels],
                created_at=datetime.now(UTC).isoformat(),
            )
            batch.requests.append(req)

        logger.info(
            "Built %d preview sheet requests for project %s (%d panels)",
            len(batch.requests), project_id, len(panels),
        )
        return batch

    def write_requests(self, batch: ImageRequestBatch, novel_id: str, chapter_id: str) -> Path:
        """Write the batch to disk for agent consumption."""
        path = self.output_root / novel_id / chapter_id / "image_requests" / f"{batch.batch_id}.json"
        write_batch(batch, str(path))
        logger.info("Wrote preview batch to %s", path)
        return path

    def collect_results(
        self,
        batch: ImageRequestBatch,
        results_path: str,
        storyboard: Storyboard,
    ) -> list[PreviewResult]:
        """Collect agent generation results and register assets."""
        try:
            result_batch = read_results(results_path)
        except FileNotFoundError:
            logger.error("Results file not found: %s", results_path)
            return [
                PreviewResult(
                    sheet_id=req.request_id,
                    success=False,
                    error="Results file not found",
                )
                for req in batch.requests
            ]

        result_lookup: dict[str, ImageResult] = {
            r.request_id: r for r in result_batch.results
        }

        collected: list[PreviewResult] = []
        for req in batch.requests:
            result = result_lookup.get(req.request_id)
            if not result:
                collected.append(PreviewResult(
                    sheet_id=req.request_id,
                    success=False,
                    error="No result found for request",
                ))
                continue

            if result.status != "completed":
                collected.append(PreviewResult(
                    sheet_id=req.request_id,
                    success=False,
                    error=result.error or "Image generation failed",
                ))
                continue

            file_path = Path(result.result_asset_path)
            if not file_path.exists():
                collected.append(PreviewResult(
                    sheet_id=req.request_id,
                    success=False,
                    error=f"Image file not found: {file_path}",
                ))
                continue

            asset_id = self._register_image_asset(file_path)

            project_id = batch.project_id
            self._bind_and_approve_panel_refs(asset_id, project_id, req.shot_range)

            collected.append(PreviewResult(
                sheet_id=req.request_id,
                success=True,
                asset_id=asset_id,
                file_path=str(file_path),
            ))
            logger.info(
                "Collected preview sheet %s: asset=%s",
                req.request_id, asset_id,
            )

        return collected

    def _register_image_asset(self, file_path: Path) -> str:
        import hashlib
        import json

        asset_id = uuid.uuid4().hex
        now = datetime.now(UTC).isoformat()

        sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()
        size_bytes = file_path.stat().st_size
        content_hash = sha256

        width, height = None, None
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                width, height = img.size
        except Exception:
            pass

        self.db.execute(
            """INSERT INTO assets
               (asset_id, task_id, attempt_id, asset_type, file_path,
                file_hash, file_size, mime_type, width, height,
                content_hash, metadata, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                asset_id,
                None,
                None,
                "image",
                str(file_path),
                sha256,
                size_bytes,
                "image/png",
                width,
                height,
                content_hash,
                json.dumps({"source": "agent_image_generation", "type": "storyboard_preview"}),
                now,
                now,
            ),
        )
        return asset_id

    def _bind_and_approve_panel_refs(
        self,
        asset_id: str,
        project_id: str,
        panel_ids: list[str],
    ) -> list[str]:
        """Create asset_binding + auto-approve for each panel as composition_ref."""
        import json

        row = self.db.fetchone(
            "SELECT content_hash, file_path FROM assets WHERE asset_id = ?",
            (asset_id,),
        )
        content_hash = row[0] if row else ""

        binding_ids: list[str] = []
        existing = self.db.fetchone(
            "SELECT project_id FROM projects WHERE project_id = ?",
            (project_id,),
        )
        if existing is None:
            self.db.execute(
                "INSERT INTO projects (project_id, name) VALUES (?, ?)",
                (project_id, project_id),
            )

        for panel_id in panel_ids:
            binding_id = uuid.uuid4().hex
            review_id = uuid.uuid4().hex
            now = datetime.now(UTC).isoformat()

            self.db.execute(
                """INSERT OR IGNORE INTO asset_bindings
                   (binding_id, asset_id, project_id, entity_type, entity_id,
                    asset_role, revision, validity, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 1, 'current', ?)""",
                (
                    binding_id,
                    asset_id,
                    project_id,
                    "panel",
                    panel_id,
                    "composition_ref",
                    now,
                ),
            )

            existing_review = self.db.fetchone(
                """SELECT review_id FROM asset_reviews
                   WHERE asset_id = ? AND manual_review_status = 'approved'""",
                (asset_id,),
            )
            if existing_review is None:
                self.db.execute(
                    """INSERT INTO asset_reviews
                       (review_id, asset_id, dependency_hash, technical_status,
                        manual_review_status, review_source, reviewer, created_at)
                       VALUES (?, ?, ?, 'passed', 'approved', 'auto_agent',
                               'storyboard_preview_service', ?)""",
                    (review_id, asset_id, content_hash, now),
                )

            binding_ids.append(binding_id)

        logger.info(
            "Bound preview sheet %s to %d panels as composition_ref",
            asset_id, len(panel_ids),
        )
        return binding_ids

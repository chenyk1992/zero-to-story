"""StoryboardPreviewService — build storyboard preview image requests.

Groups shots into 8-per-sheet (2x4 grid) with continuity chaining:
- Sheet 1: Shot 01-08
- Sheet 2: Shot 08-15 (panel 1 = shot 08, bridging from sheet 1)
- Sheet 3: Shot 15-22 (panel 1 = shot 15)
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
    # Each sheet overlaps the previous by 1 panel for continuity
    OVERLAP_PANELS = 1

    def __init__(self, db: Database, output_root: str = "") -> None:
        self.db = db
        self.output_root = Path(output_root) if output_root else Path(".")

    # -- Build requests -----------------------------------------------------

    def build_requests(
        self,
        storyboard: Storyboard,
        project_id: str,
    ) -> ImageRequestBatch:
        """Build preview sheet requests for all shots.

        Groups shots into sheets of PANELS_PER_SHEET with overlap
        chaining for visual continuity between sheets.

        Args:
            storyboard: The storyboard containing shots.
            project_id: Project identifier for the batch.

        Returns:
            ImageRequestBatch with one request per preview sheet.
        """
        batch = ImageRequestBatch(
            batch_id=f"batch_preview_{uuid.uuid4().hex[:8]}",
            project_id=project_id,
            phase="storyboard_preview",
            created_at=datetime.now(UTC).isoformat(),
        )

        shots = storyboard.shots
        if not shots:
            logger.info("No shots in storyboard, skipping preview")
            return batch

        # Calculate sheet ranges with overlap
        # Sheet 1: shots[0..7]   (8 panels)
        # Sheet 2: shots[7..14]  (8 panels, panel 1 = shot 7 for bridge)
        # Sheet 3: shots[14..21] (8 panels, panel 1 = shot 14 for bridge)
        sheet_ranges: list[tuple[int, int]] = []  # (start_idx, end_idx) inclusive
        step = self.PANELS_PER_SHEET - self.OVERLAP_PANELS
        start = 0
        while start < len(shots):
            end = min(start + self.PANELS_PER_SHEET, len(shots))
            sheet_ranges.append((start, end))
            if end >= len(shots):
                break
            start = end - self.OVERLAP_PANELS

        total_sheets = len(sheet_ranges)

        for sheet_idx, (start, end) in enumerate(sheet_ranges):
            sheet_number = sheet_idx + 1
            sheet_shots = shots[start:end]
            is_bridge = sheet_idx > 0
            bridge_description = ""

            if is_bridge and start > 0:
                # The first shot in this sheet is the bridge from previous sheet
                bridge_shot = shots[start]
                bridge_description = (
                    f"[{bridge_shot.camera.shot_size}/{bridge_shot.camera.angle}] "
                    f"{bridge_shot.description}"
                )

            prompt = render_storyboard_preview_prompt(
                storyboard=storyboard,
                shots=sheet_shots,
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
                shot_range=[s.shot_id for s in sheet_shots],
                created_at=datetime.now(UTC).isoformat(),
            )
            batch.requests.append(req)

        logger.info(
            "Built %d preview sheet requests for project %s (%d shots)",
            len(batch.requests), project_id, len(shots),
        )
        return batch

    def write_requests(self, batch: ImageRequestBatch, novel_id: str, chapter_id: str) -> Path:
        """Write the batch to disk for agent consumption.

        Args:
            batch: The batch to write.
            novel_id: Novel ID for path layout.
            chapter_id: Chapter ID for path layout.

        Returns:
            Path to the written batch file.
        """
        path = self.output_root / novel_id / chapter_id / "image_requests" / f"{batch.batch_id}.json"
        write_batch(batch, str(path))
        logger.info("Wrote preview batch to %s", path)
        return path

    # -- Collect results ----------------------------------------------------

    def collect_results(
        self,
        batch: ImageRequestBatch,
        results_path: str,
        storyboard: Storyboard,
    ) -> list[PreviewResult]:
        """Collect agent generation results and register assets.

        Args:
            batch: The original request batch.
            results_path: Path to the agent's results JSON file.
            storyboard: Storyboard to backfill preview data into.

        Returns:
            List of PreviewResult for each request.
        """
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

        # Build lookup from request_id to result
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

            # Verify file exists
            file_path = Path(result.result_asset_path)
            if not file_path.exists():
                collected.append(PreviewResult(
                    sheet_id=req.request_id,
                    success=False,
                    error=f"Image file not found: {file_path}",
                ))
                continue

            # Register asset in DB
            asset_id = self._register_image_asset(file_path)

            # Auto-bind to all covered shots as composition_ref
            project_id = batch.project_id
            self._bind_and_approve_scene_refs(asset_id, project_id, req.shot_range)

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
        """Register a generated image as an asset in the database.

        Args:
            file_path: Path to the image file.

        Returns:
            The new asset_id.
        """
        import hashlib
        import json

        asset_id = uuid.uuid4().hex
        now = datetime.now(UTC).isoformat()

        sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()
        size_bytes = file_path.stat().st_size

        # content_hash for the asset (used by approval dependency check)
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
                None,  # task_id — preview sheets aren't tied to a task
                None,  # attempt_id
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

    def _bind_and_approve_scene_refs(
        self,
        asset_id: str,
        project_id: str,
        shot_ids: list[str],
    ) -> list[str]:
        """Create asset_binding + auto-approve for each shot as composition_ref.

        Preview sheets show all shots' composition. The full sheet is bound
        to every shot as a composition reference so downstream R2V can pick
        it up via the workflow_selector.

        Args:
            asset_id: Preview sheet asset_id.
            project_id: Project identifier.
            shot_ids: Shot IDs covered by this preview sheet.

        Returns:
            List of created binding_ids.
        """
        import json

        # Get content_hash for review's dependency_hash
        row = self.db.fetchone(
            "SELECT content_hash, file_path FROM assets WHERE asset_id = ?",
            (asset_id,),
        )
        content_hash = row[0] if row else ""
        file_path = row[1] if row else ""

        binding_ids: list[str] = []
        # Ensure project row exists (FK target)
        existing = self.db.fetchone(
            "SELECT project_id FROM projects WHERE project_id = ?",
            (project_id,),
        )
        if existing is None:
            self.db.execute(
                "INSERT INTO projects (project_id, name) VALUES (?, ?)",
                (project_id, project_id),
            )

        for shot_id in shot_ids:
            binding_id = uuid.uuid4().hex
            review_id = uuid.uuid4().hex
            now = datetime.now(UTC).isoformat()

            # Create binding (entity_type=shot, role=composition_ref)
            # Use INSERT OR IGNORE — re-collecting should be idempotent
            self.db.execute(
                """INSERT OR IGNORE INTO asset_bindings
                   (binding_id, asset_id, project_id, entity_type, entity_id,
                    asset_role, revision, validity, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 1, 'current', ?)""",
                (
                    binding_id,
                    asset_id,
                    project_id,
                    "shot",
                    shot_id,
                    "composition_ref",
                    now,
                ),
            )

            # Auto-approve (idempotent)
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
            "Bound preview sheet %s to %d shots as composition_ref",
            asset_id, len(shot_ids),
        )
        return binding_ids

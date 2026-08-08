"""CharacterSheetService — build character reference sheet image requests.

This service produces structured image generation requests for agent tools.
The agent executes the requests and writes results back. This service
then collects the results and registers them as assets.
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from lfo.core.database import Database
from lfo.storyboard.prompts.character_sheet_v1 import render_character_sheet_prompt
from lfo.storyboard.storyboard import Character, Storyboard
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
class CharacterSheetResult:
    """Result of collecting a single character sheet generation."""
    character_id: str
    success: bool
    asset_id: str = ""
    file_path: str = ""
    error: str = ""


class CharacterSheetService:
    """Build and collect character reference sheet image requests."""

    def __init__(self, db: Database, output_root: str = "") -> None:
        self.db = db
        self.output_root = Path(output_root) if output_root else Path(".")

    # -- Build requests -----------------------------------------------------

    def build_requests(
        self,
        storyboard: Storyboard,
        project_id: str,
    ) -> ImageRequestBatch:
        """Build image requests for all characters needing reference sheets.

        Args:
            storyboard: The storyboard containing characters.
            project_id: Project identifier for the batch.

        Returns:
            ImageRequestBatch with one request per character that
            doesn't already have a ref_image_path.
        """
        batch = ImageRequestBatch(
            batch_id=f"batch_cs_{uuid.uuid4().hex[:8]}",
            project_id=project_id,
            phase="character_sheets",
            created_at=datetime.now(UTC).isoformat(),
        )

        for char in storyboard.characters:
            if char.ref_image_path:
                logger.info(
                    "Character %s already has ref image %s, skipping",
                    char.character_id, char.ref_image_path,
                )
                continue

            prompt = render_character_sheet_prompt(char, storyboard)
            output_path = str(
                self.output_root / storyboard.project.novel_id / storyboard.project.chapter_id / "ref_images" / f"char_{char.character_id}_sheet.png"
            )

            req = ImageRequest(
                request_id=f"imgreq_char_{char.character_id}_sheet",
                type="character_sheet",
                status="pending",
                prompt=prompt,
                aspect_ratio="16:9",
                resolution="2K",
                output_path=output_path,
                character_id=char.character_id,
                created_at=datetime.now(UTC).isoformat(),
            )
            batch.requests.append(req)

        logger.info(
            "Built %d character sheet requests for project %s",
            len(batch.requests), project_id,
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
        logger.info("Wrote batch to %s", path)
        return path

    # -- Collect results ----------------------------------------------------

    def collect_results(
        self,
        batch: ImageRequestBatch,
        results_path: str,
        storyboard: Storyboard,
    ) -> list[CharacterSheetResult]:
        """Collect agent generation results and register assets.

        Args:
            batch: The original request batch.
            results_path: Path to the agent's results JSON file.
            storyboard: Storyboard to backfill ref data into.

        Returns:
            List of CharacterSheetResult for each request.
        """
        try:
            result_batch = read_results(results_path)
        except FileNotFoundError:
            logger.error("Results file not found: %s", results_path)
            return [
                CharacterSheetResult(
                    character_id=req.character_id,
                    success=False,
                    error="Results file not found",
                )
                for req in batch.requests
            ]

        # Build lookup from request_id to result
        result_lookup: dict[str, ImageResult] = {
            r.request_id: r for r in result_batch.results
        }

        collected: list[CharacterSheetResult] = []
        for req in batch.requests:
            result = result_lookup.get(req.request_id)
            if not result:
                collected.append(CharacterSheetResult(
                    character_id=req.character_id,
                    success=False,
                    error="No result found for request",
                ))
                continue

            if result.status != "completed":
                collected.append(CharacterSheetResult(
                    character_id=req.character_id,
                    success=False,
                    error=result.error or "Image generation failed",
                ))
                continue

            # Verify file exists
            file_path = Path(result.result_asset_path)
            if not file_path.exists():
                collected.append(CharacterSheetResult(
                    character_id=req.character_id,
                    success=False,
                    error=f"Image file not found: {file_path}",
                ))
                continue

            # Register asset in DB
            asset_id = self._register_image_asset(file_path)

            # Auto-bind + approve as character_ref so R2V workflow can use it
            project_id = batch.project_id
            self._bind_and_approve_character_ref(asset_id, project_id, req.character_id)

            # Backfill into storyboard character
            char = storyboard.character_by_id(req.character_id)
            if char:
                char.ref_asset_id = asset_id
                char.ref_image_path = str(file_path)

            collected.append(CharacterSheetResult(
                character_id=req.character_id,
                success=True,
                asset_id=asset_id,
                file_path=str(file_path),
            ))
            logger.info(
                "Collected character sheet for %s: asset=%s",
                req.character_id, asset_id,
            )

        return collected

    def _register_image_asset(self, file_path: Path) -> str:
        """Register a generated image as an asset in the database.

        Args:
            file_path: Path to the image file.

        Returns:
            The new asset_id.
        """
        asset_id = uuid.uuid4().hex
        now = datetime.now(UTC).isoformat()

        # Compute file hash and size
        import hashlib
        sha256 = hashlib.sha256(file_path.read_bytes()).hexdigest()
        size_bytes = file_path.stat().st_size

        # Try to get image dimensions
        width, height = None, None
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                width, height = img.size
        except Exception:
            pass  # PIL unavailable or unsupported format

        # content_hash for the asset (used by approval dependency check)
        content_hash = sha256

        self.db.execute(
            """INSERT INTO assets
               (asset_id, task_id, attempt_id, asset_type, file_path,
                file_hash, file_size, mime_type, width, height,
                content_hash, metadata, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                asset_id,
                None,  # task_id — character sheets aren't tied to a task
                None,  # attempt_id
                "image",
                str(file_path),
                sha256,
                size_bytes,
                "image/png",
                width,
                height,
                content_hash,
                json.dumps({"source": "agent_image_generation"}),
                now,
                now,
            ),
        )
        return asset_id

    def _bind_and_approve_character_ref(
        self,
        asset_id: str,
        project_id: str,
        character_id: str,
    ) -> str:
        """Create asset_binding + auto-approve for a character ref.

        The character sheet is auto-approved so downstream
        workflow_selector / task_readiness can see the ref as ready
        to use for R2V workflows.

        Args:
            asset_id: The asset_id of the character sheet.
            project_id: Project identifier.
            character_id: Character entity_id.

        Returns:
            The new binding_id.
        """
        binding_id = uuid.uuid4().hex
        review_id = uuid.uuid4().hex
        now = datetime.now(UTC).isoformat()

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

        # Get content_hash for review's dependency_hash
        row = self.db.fetchone(
            "SELECT content_hash FROM assets WHERE asset_id = ?",
            (asset_id,),
        )
        content_hash = row[0] if row else ""

        # Create binding (entity_type=character, role=character_ref)
        # Use INSERT OR IGNORE — re-collecting a batch should be idempotent
        self.db.execute(
            """INSERT OR IGNORE INTO asset_bindings
               (binding_id, asset_id, project_id, entity_type, entity_id,
                asset_role, revision, validity, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, 'current', ?)""",
            (
                binding_id,
                asset_id,
                project_id,
                "character",
                character_id,
                "character_ref",
                now,
            ),
        )

        # Auto-approve (technical_status=passed, manual_review_status=approved)
        # Idempotent: insert only if no approved review exists for this asset+role
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
                           'character_sheet_service', ?)""",
                (review_id, asset_id, content_hash, now),
            )

        logger.info(
            "Created binding %s and auto-approved char ref for %s",
            binding_id, character_id,
        )
        return binding_id

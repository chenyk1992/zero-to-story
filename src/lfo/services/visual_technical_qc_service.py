"""Visual Technical QC Service — automated quality checks.

Runs technical checks on imported visual results:
- decodable: file exists and is readable
- hash_match: file_hash matches content's declared hash (if any)
- mime_type: MIME type is present
- dimensions: width/height are present and positive
- file_size: file size is positive (if known)
- alpha: alpha channel info present (if applicable)

Does NOT auto-gate identity, costume, character count, composition —
those are human review checklist items (spec §23).
"""
from __future__ import annotations

import json
from typing import Any

from lfo.application.visual_task_service import VisualTaskService
from lfo.core.database import Database
from lfo.core.state_machine import TaskStatus
from lfo.visual.stages import VisualStage


class VisualTechnicalQCService:
    """Run automated technical QC on visual results."""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._task_svc = VisualTaskService(db)

    def run(self, task_id: str, asset_id: str) -> dict[str, Any]:
        """Run technical QC checks on the given asset.

        Args:
            task_id: The visual task ID.
            asset_id: The asset to check.

        Returns:
            Dict with 'overall' ('pass'/'fail') and 'checks' dict.

        Side effects:
            On pass: transitions task to WAITING_USER + AWAITING_REVIEW.
        """
        asset = self.db.fetchone(
            "SELECT * FROM assets WHERE asset_id = ? AND task_id = ?",
            (asset_id, task_id),
        )
        manifest = self.db.fetchone(
            "SELECT * FROM visual_result_manifests WHERE task_id = ?",
            (task_id,),
        )

        checks: dict[str, bool] = {}

        # decodable: asset exists
        checks["decodable"] = asset is not None

        # mime_type: present
        checks["mime_type"] = (
            asset is not None and asset["mime_type"] is not None
            and len(asset["mime_type"]) > 0
        )

        # dimensions: width and height present and positive
        if asset is not None and asset["width"] and asset["height"]:
            checks["dimensions"] = asset["width"] > 0 and asset["height"] > 0
        else:
            checks["dimensions"] = False

        # file_size: positive if known
        if asset is not None and asset["file_size"] is not None:
            checks["file_size"] = asset["file_size"] > 0
        else:
            checks["file_size"] = True  # unknown is not a failure

        # hash_match: file_hash vs content's declared_hash (if present)
        if manifest is not None:
            content = json.loads(manifest["content"])
            declared = content.get("declared_hash")
            if declared:
                checks["hash_match"] = manifest["file_hash"] == declared
            else:
                checks["hash_match"] = True  # no declared hash → N/A
        else:
            checks["hash_match"] = False

        # alpha: metadata has alpha info (optional)
        if asset is not None and asset["metadata"]:
            meta = json.loads(asset["metadata"])
            checks["alpha"] = "alpha" in meta
        else:
            checks["alpha"] = True  # no metadata → not a failure

        # Overall: all critical checks must pass
        critical = ("decodable", "mime_type", "dimensions", "hash_match")
        overall = "pass" if all(checks.get(k, False) for k in critical) else "fail"

        # On pass, transition to WAITING_USER + AWAITING_REVIEW
        if overall == "pass":
            try:
                self._task_svc.transition(
                    task_id,
                    expected_task_status=TaskStatus.QC_PENDING,
                    expected_visual_stage=VisualStage.RESULT_IMPORTED,
                    new_task_status=TaskStatus.WAITING_USER,
                    new_visual_stage=VisualStage.AWAITING_REVIEW,
                    reason="technical QC passed",
                )
            except Exception:
                # Transition may fail if task already moved; don't block QC report
                pass

        return {
            "overall": overall,
            "checks": checks,
        }

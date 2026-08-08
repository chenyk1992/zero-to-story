"""Asset binding lifecycle + approval management."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC

from lfo.core.database import Database


@dataclass
class ApprovedAsset:
    """An asset that has passed all gates and is ready for execution."""

    asset_id: str
    binding_id: str
    project_id: str
    entity_type: str
    entity_id: str
    asset_role: str
    file_path: str
    file_hash: str
    content_hash: str
    review_id: str
    technical_status: str
    manual_review_status: str


class AssetNotReadyError(Exception):
    """Raised when an asset is not yet approved or file is missing."""

    def __init__(self, reason: str, asset_id: str = "", entity_id: str = ""):
        self.reason = reason
        self.asset_id = asset_id
        self.entity_id = entity_id
        super().__init__(reason)


@dataclass
class BindingRevision:
    binding_id: str
    asset_id: str
    project_id: str
    entity_type: str
    entity_id: str
    asset_role: str
    revision: int
    validity: str  # 'current' | 'stale' | 'superseded'
    superseded_by: str | None


class AssetBindingService:
    """Unified entry point for asset binding operations.

    All binding revisions are created through this service.
    Direct SQL INSERTs to asset_bindings are forbidden.
    """

    def __init__(self, db: Database):
        self.db = db

    def create_binding(
        self,
        asset_id: str,
        project_id: str,
        entity_type: str,
        entity_id: str,
        asset_role: str,
    ) -> BindingRevision:
        """Create first revision of a binding. Returns BindingRevision."""
        binding_id = uuid.uuid4().hex
        now = _utc_now()

        self.db.execute(
            """INSERT INTO asset_bindings
               (binding_id, asset_id, project_id, entity_type, entity_id,
                asset_role, revision, validity, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, 'current', ?)""",
            (binding_id, asset_id, project_id, entity_type, entity_id,
             asset_role, now),
        )

        return BindingRevision(
            binding_id=binding_id,
            asset_id=asset_id,
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_id,
            asset_role=asset_role,
            revision=1,
            validity='current',
            superseded_by=None,
        )

    def create_revision(
        self,
        asset_id: str,
        project_id: str,
        entity_type: str,
        entity_id: str,
        asset_role: str,
    ) -> BindingRevision:
        """Create a new revision, marking old 'current' as 'superseded'.

        Must be transactional. Order of operations:
        1. UPDATE old current → superseded (superseded_by = NULL first,
           because the new row doesn't exist yet for the FK)
        2. INSERT new current row
        3. UPDATE old row's superseded_by to point to the new row
        """
        with self.db.transaction():
            # Find the current binding
            row = self.db.fetchone(
                """SELECT binding_id, revision FROM asset_bindings
                   WHERE project_id = ? AND entity_type = ?
                     AND entity_id = ? AND asset_role = ?
                     AND validity = 'current'""",
                (project_id, entity_type, entity_id, asset_role),
            )

            new_revision = 1 if row is None else row[1] + 1
            new_binding_id = uuid.uuid4().hex
            now = _utc_now()

            old_binding_id = None
            if row is not None:
                old_binding_id = row[0]
                # Mark old as superseded (superseded_by = NULL for now —
                # FK would fail if we reference the not-yet-inserted new row)
                self.db.execute(
                    """UPDATE asset_bindings
                       SET validity = 'superseded', superseded_by = NULL
                       WHERE binding_id = ?""",
                    (old_binding_id,),
                )

            # Insert new current binding
            self.db.execute(
                """INSERT INTO asset_bindings
                   (binding_id, asset_id, project_id, entity_type, entity_id,
                    asset_role, revision, validity, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'current', ?)""",
                (new_binding_id, asset_id, project_id, entity_type, entity_id,
                 asset_role, new_revision, now),
            )

            # Now that the new row exists, set the superseded_by pointer
            if old_binding_id is not None:
                self.db.execute(
                    """UPDATE asset_bindings
                       SET superseded_by = ?
                       WHERE binding_id = ?""",
                    (new_binding_id, old_binding_id),
                )

        return BindingRevision(
            binding_id=new_binding_id,
            asset_id=asset_id,
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_id,
            asset_role=asset_role,
            revision=new_revision,
            validity='current',
            superseded_by=None,
        )

    def get_current_binding(
        self,
        project_id: str,
        entity_type: str,
        entity_id: str,
        asset_role: str,
    ) -> BindingRevision | None:
        """Get the current valid binding for an entity+role."""
        row = self.db.fetchone(
            """SELECT binding_id, asset_id, project_id, entity_type,
                      entity_id, asset_role, revision, validity,
                      superseded_by
               FROM asset_bindings
               WHERE project_id = ? AND entity_type = ?
                 AND entity_id = ? AND asset_role = ?
                 AND validity = 'current'""",
            (project_id, entity_type, entity_id, asset_role),
        )

        if row is None:
            return None

        return BindingRevision(
            binding_id=row[0],
            asset_id=row[1],
            project_id=row[2],
            entity_type=row[3],
            entity_id=row[4],
            asset_role=row[5],
            revision=row[6],
            validity=row[7],
            superseded_by=row[8],
        )

    def approve_asset(
        self,
        asset_id: str,
        reviewer: str,
        review_source: str = "manual",
    ) -> str:
        """Record an approval review. Returns review_id."""
        review_id = uuid.uuid4().hex
        now = _utc_now()

        # Get the asset's content_hash for traceability
        row = self.db.fetchone(
            "SELECT content_hash FROM assets WHERE asset_id = ?",
            (asset_id,),
        )
        dependency_hash = row[0] if row else ""

        self.db.execute(
            """INSERT INTO asset_reviews
               (review_id, asset_id, dependency_hash, technical_status,
                manual_review_status, review_source, reviewer, created_at)
               VALUES (?, ?, ?, 'passed', 'approved', ?, ?, ?)""",
            (review_id, asset_id, dependency_hash, review_source, reviewer, now),
        )

        return review_id

    def reject_asset(
        self,
        asset_id: str,
        reviewer: str,
        reason: str,
        review_source: str = "manual",
    ) -> str:
        """Record a rejection review. Returns review_id."""
        review_id = uuid.uuid4().hex
        now = _utc_now()

        # Get the asset's content_hash for traceability
        row = self.db.fetchone(
            "SELECT content_hash FROM assets WHERE asset_id = ?",
            (asset_id,),
        )
        dependency_hash = row[0] if row else ""

        self.db.execute(
            """INSERT INTO asset_reviews
               (review_id, asset_id, dependency_hash, technical_status,
                manual_review_status, review_source, reviewer,
                rejection_reason, created_at)
               VALUES (?, ?, ?, 'failed', 'rejected', ?, ?, ?, ?)""",
            (review_id, asset_id, dependency_hash, review_source, reviewer,
             reason, now),
        )

        return review_id

    def get_current_approval(self, asset_id: str) -> dict | None:
        """Get the most recent approval/rejection for an asset.

        Returns None if not reviewed or if file_hash changed since review.
        """
        row = self.db.fetchone(
            """SELECT review_id, asset_id, dependency_hash,
                      technical_status, manual_review_status, review_source,
                      reviewer, rejection_reason, created_at
               FROM asset_reviews
               WHERE asset_id = ?
               ORDER BY created_at DESC
               LIMIT 1""",
            (asset_id,),
        )

        if row is None:
            return None

        # Check if the asset's content_hash has changed since review
        current_hash_row = self.db.fetchone(
            "SELECT content_hash FROM assets WHERE asset_id = ?",
            (asset_id,),
        )
        if current_hash_row is not None and current_hash_row[0] != row[2]:
            return None

        return {
            "review_id": row[0],
            "asset_id": row[1],
            "dependency_hash": row[2],
            "technical_status": row[3],
            "manual_review_status": row[4],
            "review_source": row[5],
            "reviewer": row[6],
            "rejection_reason": row[7],
            "created_at": row[8],
        }

    def is_approved(self, asset_id: str) -> bool:
        """Check if asset currently has a valid approval."""
        approval = self.get_current_approval(asset_id)
        if approval is None:
            return False
        return approval["manual_review_status"] == "approved"

    def get_current_approved_asset(
        self,
        *,
        project_id: str,
        entity_type: str,
        entity_id: str,
        asset_role: str,
    ) -> ApprovedAsset:
        """Get the current approved asset for an entity+role, with full gate checks.

        Only returns an ApprovedAsset when ALL conditions are met:
        - binding.validity = 'current'
        - asset file exists on disk
        - asset.file_hash matches current file content
        - review.technical_status = 'passed'
        - review.manual_review_status = 'approved'
        - review.dependency_hash matches current asset content_hash

        Raises:
            AssetNotReadyError: If any gate check fails, with reason detailing why.
        """
        import os

        # 1. Get current binding
        binding = self.get_current_binding(
            project_id, entity_type, entity_id, asset_role
        )
        if binding is None:
            raise AssetNotReadyError(
                f"No current binding found for {entity_type}:{entity_id} role={asset_role}",
                entity_id=entity_id,
            )

        # 2. Get asset record
        asset_row = self.db.fetchone(
            """SELECT asset_id, file_path, file_hash, content_hash
               FROM assets WHERE asset_id = ?""",
            (binding.asset_id,),
        )
        if asset_row is None:
            raise AssetNotReadyError(
                f"Asset {binding.asset_id} not found in database",
                asset_id=binding.asset_id,
                entity_id=entity_id,
            )

        asset_id = asset_row[0]
        file_path = asset_row[1]
        file_hash = asset_row[2]
        content_hash = asset_row[3]

        # 3. Check file exists
        if not os.path.exists(file_path):
            raise AssetNotReadyError(
                f"Asset file missing: {file_path}",
                asset_id=asset_id,
                entity_id=entity_id,
            )

        # 4. Verify file_hash matches current file content
        if file_hash:
            actual_hash = _compute_file_hash(file_path)
            if actual_hash != file_hash:
                raise AssetNotReadyError(
                    f"Asset file_hash mismatch for {asset_id}: expected {file_hash}, got {actual_hash}",
                    asset_id=asset_id,
                    entity_id=entity_id,
                )

        # 5. Get the latest approval record (bypass content_hash auto-invalidation
        #    so we can give a more specific error message)
        review_row = self.db.fetchone(
            """SELECT review_id, asset_id, dependency_hash,
                      technical_status, manual_review_status, review_source,
                      reviewer, rejection_reason, created_at
               FROM asset_reviews
               WHERE asset_id = ?
               ORDER BY created_at DESC
               LIMIT 1""",
            (asset_id,),
        )
        if review_row is None:
            raise AssetNotReadyError(
                f"No approval record for asset {asset_id}",
                asset_id=asset_id,
                entity_id=entity_id,
            )

        approval = {
            "review_id": review_row[0],
            "asset_id": review_row[1],
            "dependency_hash": review_row[2],
            "technical_status": review_row[3],
            "manual_review_status": review_row[4],
            "review_source": review_row[5],
            "reviewer": review_row[6],
            "rejection_reason": review_row[7],
            "created_at": review_row[8],
        }

        # 6. Verify review.dependency_hash matches current content_hash
        if approval["dependency_hash"] != content_hash:
            raise AssetNotReadyError(
                f"Asset {asset_id} content changed since approval (dependency_hash mismatch)",
                asset_id=asset_id,
                entity_id=entity_id,
            )

        # 7. Verify technical_status = 'passed'
        if approval["technical_status"] != "passed":
            raise AssetNotReadyError(
                f"Asset {asset_id} technical_status is '{approval['technical_status']}', need 'passed'",
                asset_id=asset_id,
                entity_id=entity_id,
            )

        # 8. Verify manual_review_status = 'approved'
        if approval["manual_review_status"] != "approved":
            raise AssetNotReadyError(
                f"Asset {asset_id} manual_review_status is '{approval['manual_review_status']}', need 'approved'",
                asset_id=asset_id,
                entity_id=entity_id,
            )

        return ApprovedAsset(
            asset_id=asset_id,
            binding_id=binding.binding_id,
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_id,
            asset_role=asset_role,
            file_path=file_path,
            file_hash=file_hash,
            content_hash=content_hash,
            review_id=approval["review_id"],
            technical_status=approval["technical_status"],
            manual_review_status=approval["manual_review_status"],
        )


def _compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    import hashlib
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    from datetime import datetime
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")

"""Content-addressed storage for imported assets.

Imported assets are copied into a CAS layout keyed by SHA-256::

    workspace/assets/sha256/<前两位>/<完整 sha256>/<原始安全文件名>

Same blob → same path (de-duplication). Logical asset revisions are versioned
separately in the database; the CAS only stores bytes.
"""
from __future__ import annotations

import hashlib
import pathlib
import shutil
import tempfile
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

from lfo.assets.paths import validate_readable_file

# Hash algorithm for blob addressing.
BLOB_HASH_ALGO = "sha256"


@dataclass(frozen=True)
class BlobRef:
    """Reference to a stored blob."""
    blob_hash: str
    size: int
    path: pathlib.Path


@dataclass(frozen=True)
class ImportedAsset:
    """Result of importing an external asset into the CAS."""
    asset_key: str
    blob_hash: str
    blob_size: int
    blob_path: pathlib.Path
    media_type: str
    original_filename: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ContentAddressedStore:
    """Content-addressed blob store."""

    def __init__(self, root: pathlib.Path) -> None:
        self.root = root.resolve(strict=False)
        self.root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _blob_dir(self, blob_hash: str) -> pathlib.Path:
        """Return the directory for a given hash."""
        prefix = blob_hash[:2]
        return self.root / "sha256" / prefix / blob_hash

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def has_blob(self, blob_hash: str) -> bool:
        """Return True if a blob with this hash exists."""
        return self._blob_dir(blob_hash).is_dir()

    def store_file(
        self,
        source: pathlib.Path,
        original_filename: str | None = None,
    ) -> BlobRef:
        """Copy a file into the CAS.

        Streams the file to avoid loading large files into memory.
        Uses a temporary file + atomic rename for crash safety.

        Args:
            source: Path to the source file (must exist and be readable).
            original_filename: Original filename to preserve. If None,
                uses the source file's name.

        Returns:
            BlobRef with hash, size, and final path.
        """
        validate_readable_file(source)
        if original_filename is None:
            original_filename = source.name

        blob_hash, size = self._stream_hash(source)

        dest_dir = self._blob_dir(blob_hash)
        if dest_dir.exists():
            # Blob already stored; verify the file exists.
            existing = dest_dir / original_filename
            if existing.is_file() and existing.stat().st_size == size:
                return BlobRef(blob_hash=blob_hash, size=size, path=existing)

        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_file = dest_dir / original_filename

        # Stream copy via temp file + atomic rename.
        tmp_path: pathlib.Path | None = None
        with source.open("rb") as src_f:
            tmp_fd, tmp_path_str = tempfile.mkstemp(
                prefix=".tmp_", dir=str(dest_dir)
            )
            try:
                tmp_path = pathlib.Path(tmp_path_str)
                with open(tmp_fd, "wb") as tmp_f:
                    shutil.copyfileobj(src_f, tmp_f, length=1024 * 1024)
                tmp_path.replace(dest_file)
            except BaseException:
                # Clean up temp file on failure.
                if tmp_path is not None:
                    with suppress(OSError, FileNotFoundError):
                        tmp_path.unlink()
                raise

        return BlobRef(blob_hash=blob_hash, size=size, path=dest_file)

    def _stream_hash(self, source: pathlib.Path) -> tuple[str, int]:
        """Compute SHA-256 and size by streaming."""
        h = hashlib.new(BLOB_HASH_ALGO)
        size = 0
        with source.open("rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
                size += len(chunk)
        return h.hexdigest(), size

    def resolve_blob(self, blob_hash: str, filename: str) -> pathlib.Path | None:
        """Resolve a blob hash + filename to a path, if it exists."""
        p = self._blob_dir(blob_hash) / filename
        if p.is_file():
            return p
        return None

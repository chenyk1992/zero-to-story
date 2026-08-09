"""Asset importer — orchestrates path resolution, probing, and CAS storage."""
from __future__ import annotations

import pathlib
from dataclasses import dataclass, field
from typing import Any

from lfo.assets.paths import (
    PathSecurityError,
    resolve_package_uri,
    validate_readable_file,
)
from lfo.assets.probe import MediaProbe, ProbeResult
from lfo.assets.store import BlobRef, ContentAddressedStore


@dataclass
class ImportResult:
    """Result of importing a single asset."""
    asset_key: str
    blob_ref: BlobRef
    probe: ProbeResult
    media_type: str
    original_filename: str
    metadata: dict[str, Any] = field(default_factory=dict)


class AssetImporter:
    """Import external assets into LFO's managed storage."""

    def __init__(
        self,
        cas: ContentAddressedStore,
        probe: MediaProbe | None = None,
    ) -> None:
        self.cas = cas
        self.probe = probe or MediaProbe()

    def import_asset(
        self,
        asset_key: str,
        uri: str,
        package_dir: pathlib.Path,
        declared_media_type: str | None = None,
    ) -> ImportResult:
        """Import a single asset from a Package-relative URI.

        Args:
            asset_key: Logical asset key from the Package.
            uri: Package-relative URI (e.g. ``"assets/hero.png"``).
            package_dir: Absolute path to the Package directory.
            declared_media_type: Optional media type hint from the Package.

        Returns:
            ImportResult with blob reference and probe data.

        Raises:
            PathSecurityError: If the URI is unsafe.
            FileNotFoundError: If the source file does not exist.
            ValueError: If media type cannot be determined or mismatches.
        """
        # 1. Resolve and validate the path.
        resolved = resolve_package_uri(uri, package_dir)
        validate_readable_file(resolved)

        # 2. Probe the file.
        probe_result = self.probe.probe(resolved)

        # 3. Cross-check declared vs probed type.
        if (
            declared_media_type
            and probe_result.media_type != declared_media_type
        ):
            # Allow some flexibility: if probed as "document" but declared
            # as something else, trust the probe. If clearly mismatched, warn.
            if probe_result.media_type not in ("document", declared_media_type):
                raise ValueError(
                    f"Media type mismatch for {asset_key!r}: "
                    f"declared {declared_media_type!r}, "
                    f"probed {probe_result.media_type!r}"
                )

        # 4. Store in CAS.
        blob_ref = self.cas.store_file(resolved, original_filename=resolved.name)

        return ImportResult(
            asset_key=asset_key,
            blob_ref=blob_ref,
            probe=probe_result,
            media_type=probe_result.media_type,
            original_filename=resolved.name,
            metadata=probe_result.to_dict(),
        )

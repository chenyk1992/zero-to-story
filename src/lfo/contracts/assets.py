"""AssetSpec — input media reference inside a VideoExecutionPackage.

An ``AssetSpec`` describes one logical input asset. On import LFO copies the
source into its content-addressed store; after import LFO never reads the
source path again.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Media types recognised by v1.
MEDIA_TYPES = frozenset({"image", "video", "audio", "subtitle", "document"})


@dataclass
class AssetSource:
    """Where to find the asset before import."""

    uri: str
    sha256: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str) -> AssetSource:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
        uri = data.get("uri")
        if not isinstance(uri, str) or not uri:
            raise ValueError(f"{path}.uri: required string")
        sha256 = data.get("sha256")
        if sha256 is not None and not isinstance(sha256, str):
            raise TypeError(f"{path}.sha256: expected string or null")
        return cls(uri=uri, sha256=sha256)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"uri": self.uri}
        if self.sha256 is not None:
            d["sha256"] = self.sha256
        return d


@dataclass
class ProvenanceSpec:
    """Provenance metadata — who created this asset and how.

    ``operation`` is an open string (e.g. ``"image.generate"``, ``"video.capture"``);
    LFO does not enumerate creative methods.
    """

    source_type: str
    producer: str
    operation: str
    producer_version: str | None = None
    source_asset_keys: list[str] = field(default_factory=list)
    prompt_hash: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str) -> ProvenanceSpec:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
        source_type = data.get("source_type")
        if not isinstance(source_type, str):
            raise ValueError(f"{path}.source_type: required string")
        producer = data.get("producer")
        if not isinstance(producer, str):
            raise ValueError(f"{path}.producer: required string")
        operation = data.get("operation")
        if not isinstance(operation, str):
            raise ValueError(f"{path}.operation: required string")
        producer_version = data.get("producer_version")
        if producer_version is not None and not isinstance(producer_version, str):
            raise TypeError(f"{path}.producer_version: expected string or null")
        source_asset_keys = data.get("source_asset_keys", [])
        if not isinstance(source_asset_keys, list):
            raise TypeError(f"{path}.source_asset_keys: expected array")
        for i, k in enumerate(source_asset_keys):
            if not isinstance(k, str):
                raise TypeError(f"{path}.source_asset_keys[{i}]: expected string")
        prompt_hash = data.get("prompt_hash")
        if prompt_hash is not None and not isinstance(prompt_hash, str):
            raise TypeError(f"{path}.prompt_hash: expected string or null")
        return cls(
            source_type=source_type,
            producer=producer,
            operation=operation,
            producer_version=producer_version,
            source_asset_keys=source_asset_keys,
            prompt_hash=prompt_hash,
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "source_type": self.source_type,
            "producer": self.producer,
            "operation": self.operation,
        }
        if self.producer_version is not None:
            d["producer_version"] = self.producer_version
        if self.source_asset_keys:
            d["source_asset_keys"] = list(self.source_asset_keys)
        if self.prompt_hash is not None:
            d["prompt_hash"] = self.prompt_hash
        return d


@dataclass
class ReviewDeclaration:
    """Whether this asset requires explicit review before execution."""

    required: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str) -> ReviewDeclaration:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
        required = data.get("required", True)
        if not isinstance(required, bool):
            raise TypeError(f"{path}.required: expected boolean")
        return cls(required=required)

    def to_dict(self) -> dict[str, Any]:
        return {"required": self.required}


@dataclass
class AssetSpec:
    """One logical input asset in a Package."""

    asset_key: str
    media_type: str
    source: AssetSource
    provenance: ProvenanceSpec
    review: ReviewDeclaration = field(default_factory=ReviewDeclaration)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str) -> AssetSpec:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
        asset_key = data.get("asset_key")
        if not isinstance(asset_key, str) or not asset_key:
            raise ValueError(f"{path}.asset_key: required string")
        media_type = data.get("media_type")
        if media_type not in MEDIA_TYPES:
            raise ValueError(
                f"{path}.media_type: must be one of {sorted(MEDIA_TYPES)}"
            )
        source_data = data.get("source")
        if not isinstance(source_data, dict):
            raise ValueError(f"{path}.source: required object")
        source = AssetSource.from_dict(source_data, f"{path}.source")
        prov_data = data.get("provenance")
        if not isinstance(prov_data, dict):
            raise ValueError(f"{path}.provenance: required object")
        provenance = ProvenanceSpec.from_dict(prov_data, f"{path}.provenance")
        review = ReviewDeclaration.from_dict(
            data.get("review", {}), f"{path}.review"
        )
        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            raise TypeError(f"{path}.metadata: expected object")
        return cls(
            asset_key=asset_key,
            media_type=media_type,
            source=source,
            provenance=provenance,
            review=review,
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "asset_key": self.asset_key,
            "media_type": self.media_type,
            "source": self.source.to_dict(),
            "provenance": self.provenance.to_dict(),
            "review": self.review.to_dict(),
        }
        if self.metadata:
            d["metadata"] = dict(self.metadata)
        return d

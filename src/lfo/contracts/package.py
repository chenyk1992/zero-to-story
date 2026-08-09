"""VideoExecutionPackage — the sole public contract between Skill and LFO."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .assets import AssetSpec
from .clips import ClipSpec
from .errors import ValidationResult
from .timeline import ApprovalDeclaration, OutputPolicy

SCHEMA_ID = "lfo.video-execution.v1"


@dataclass
class ProjectInfo:
    """Project metadata (informational, not used for execution)."""

    title: str
    locale: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any], path: str) -> ProjectInfo:
        if not isinstance(data, dict):
            raise TypeError(f"{path}: expected object, got {type(data).__name__}")
        title = data.get("title")
        if not isinstance(title, str) or not title:
            raise ValueError(f"{path}.title: required string")
        locale = data.get("locale")
        if locale is not None and not isinstance(locale, str):
            raise TypeError(f"{path}.locale: expected string or null")
        return cls(title=title, locale=locale)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"title": self.title}
        if self.locale is not None:
            d["locale"] = self.locale
        return d


@dataclass
class VideoExecutionPackage:
    """The single public boundary between Creative Skills and LFO."""

    package_id: str
    revision: int
    project: ProjectInfo
    assets: list[AssetSpec] = field(default_factory=list)
    clips: list[ClipSpec] = field(default_factory=list)
    output: OutputPolicy = field(default_factory=OutputPolicy)
    approval: ApprovalDeclaration = field(default_factory=ApprovalDeclaration)
    timeline: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VideoExecutionPackage:
        if not isinstance(data, dict):
            raise TypeError(f"$: expected object, got {type(data).__name__}")
        schema = data.get("schema")
        if schema != SCHEMA_ID:
            raise ValueError(
                f"$.schema: expected {SCHEMA_ID!r}, got {schema!r}"
            )
        package_id = data.get("package_id")
        if not isinstance(package_id, str) or not package_id:
            raise ValueError("$.package_id: required string")
        revision = data.get("revision")
        if not isinstance(revision, int) or isinstance(revision, bool):
            raise TypeError("$.revision: required integer")
        if revision < 1:
            raise ValueError("$.revision: must be >= 1")
        project_data = data.get("project")
        if not isinstance(project_data, dict):
            raise ValueError("$.project: required object")
        project = ProjectInfo.from_dict(project_data, "$.project")
        assets_data = data.get("assets", [])
        if not isinstance(assets_data, list):
            raise TypeError("$.assets: expected array")
        assets = [
            AssetSpec.from_dict(a, f"$.assets[{i}]") for i, a in enumerate(assets_data)
        ]
        clips_data = data.get("clips", [])
        if not isinstance(clips_data, list):
            raise TypeError("$.clips: expected array")
        clips = [
            ClipSpec.from_dict(c, f"$.clips[{i}]") for i, c in enumerate(clips_data)
        ]
        output = OutputPolicy.from_dict(data.get("output", {}), "$.output")
        approval = ApprovalDeclaration.from_dict(
            data.get("approval", {}), "$.approval"
        )
        timeline = data.get("timeline", {})
        if not isinstance(timeline, dict):
            raise TypeError("$.timeline: expected object")
        extensions = data.get("extensions", {})
        if not isinstance(extensions, dict):
            raise TypeError("$.extensions: expected object")
        return cls(
            package_id=package_id,
            revision=revision,
            project=project,
            assets=assets,
            clips=clips,
            output=output,
            approval=approval,
            timeline=timeline,
            extensions=extensions,
        )

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "schema": SCHEMA_ID,
            "package_id": self.package_id,
            "revision": self.revision,
            "project": self.project.to_dict(),
            "assets": [a.to_dict() for a in self.assets],
            "clips": [c.to_dict() for c in self.clips],
            "output": self.output.to_dict(),
        }
        approval_dict = self.approval.to_dict()
        if approval_dict:
            d["approval"] = approval_dict
        if self.timeline:
            d["timeline"] = dict(self.timeline)
        if self.extensions:
            d["extensions"] = dict(self.extensions)
        return d


def validate_package(data: Any) -> ValidationResult:
    """Validate a raw Package dict. Returns structured errors."""
    result = ValidationResult()
    if not isinstance(data, dict):
        result.add("$", "expected object", "type")
        return result
    schema = data.get("schema")
    if schema != SCHEMA_ID:
        result.add("$.schema", f"expected {SCHEMA_ID!r}", "schema", schema)
        return result
    # Top-level required fields
    if not isinstance(data.get("package_id"), str):
        result.add("$.package_id", "required string", "required")
    revision = data.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool):
        result.add("$.revision", "required integer >= 1", "type")
    elif revision < 1:
        result.add("$.revision", "must be >= 1", "minimum", revision)
    if not isinstance(data.get("project"), dict):
        result.add("$.project", "required object", "required")
    # Collect per-section errors
    try:
        VideoExecutionPackage.from_dict(data)
    except (TypeError, ValueError) as e:
        result.add("$", str(e), "parse")
    # Cross-field: clip_id uniqueness
    clips = data.get("clips", [])
    if isinstance(clips, list):
        seen_ids: dict[str, int] = {}
        for i, c in enumerate(clips):
            if isinstance(c, dict) and isinstance(c.get("clip_id"), str):
                cid = c["clip_id"]
                if cid in seen_ids:
                    result.add(
                        f"$.clips[{i}].clip_id",
                        f"duplicate clip_id {cid!r} (first at index {seen_ids[cid]})",
                        "unique",
                        cid,
                    )
                else:
                    seen_ids[cid] = i
    # Cross-field: asset_key uniqueness
    assets = data.get("assets", [])
    if isinstance(assets, list):
        seen_keys: dict[str, int] = {}
        for i, a in enumerate(assets):
            if isinstance(a, dict) and isinstance(a.get("asset_key"), str):
                ak = a["asset_key"]
                if ak in seen_keys:
                    result.add(
                        f"$.assets[{i}].asset_key",
                        f"duplicate asset_key {ak!r} (first at index {seen_keys[ak]})",
                        "unique",
                        ak,
                    )
                else:
                    seen_keys[ak] = i
    # Cross-field: reference asset_keys must exist
    if isinstance(assets, list) and isinstance(clips, list):
        asset_keys = {
            a["asset_key"] for a in assets
            if isinstance(a, dict) and isinstance(a.get("asset_key"), str)
        }
        for i, c in enumerate(clips):
            if not isinstance(c, dict):
                continue
            gen = c.get("generation", {})
            if not isinstance(gen, dict):
                continue
            refs = gen.get("references", [])
            if not isinstance(refs, list):
                continue
            for j, r in enumerate(refs):
                if not isinstance(r, dict):
                    continue
                ak = r.get("asset_key")
                if isinstance(ak, str) and ak not in asset_keys:
                    result.add(
                        f"$.clips[{i}].generation.references[{j}].asset_key",
                        f"unknown asset_key {ak!r}",
                        "reference",
                        ak,
                    )
    return result

"""VideoExecutionPackage — the sole public contract between Skill and LFO."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .assets import AssetSpec
from .clips import ClipSpec
from .errors import ValidationResult
from .operations import validate_operation_references
from .timeline import ApprovalDeclaration, OutputPolicy, TimelineSpec
from .upscale import UPSCALE_EXTENSION_KEY, validate_upscale_options

SCHEMA_ID = "lfo.video-execution.v1"


@dataclass
class ProjectInfo:
    """Project identity and display metadata used by the Runtime layout."""

    title: str
    project_id: str
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
        project_id = data.get("project_id")
        if not isinstance(project_id, str) or not project_id:
            raise ValueError(f"{path}.project_id: required string")
        return cls(title=title, project_id=project_id, locale=locale)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"title": self.title}
        if self.locale is not None:
            d["locale"] = self.locale
        d["project_id"] = self.project_id
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
    timeline: TimelineSpec = field(default_factory=TimelineSpec)
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
        asset_media_types = {asset.asset_key: asset.media_type for asset in assets}
        for index, clip in enumerate(clips):
            try:
                validate_operation_references(
                    clip.generation.operation,
                    clip.generation.references,
                    asset_media_types=asset_media_types,
                )
            except (TypeError, ValueError) as exc:
                raise type(exc)(
                    f"$.clips[{index}].generation: {exc}"
                ) from exc
        output = OutputPolicy.from_dict(data.get("output", {}), "$.output")
        approval = ApprovalDeclaration.from_dict(
            data.get("approval", {}), "$.approval"
        )
        timeline_data = data.get("timeline")
        if timeline_data is None:
            timeline = TimelineSpec.for_clips(clips)
        else:
            if not isinstance(timeline_data, dict):
                raise TypeError("$.timeline: expected object")
            timeline = TimelineSpec.from_dict(
                timeline_data,
                "$.timeline",
                clip_durations={clip.clip_id: clip.duration_ms for clip in clips},
            )
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
        timeline = self.timeline
        if not timeline.segments:
            timeline = TimelineSpec.for_clips(self.clips)
        d["timeline"] = timeline.to_dict()
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
    _validate_upscale_extension(result, data.get("extensions", {}), "$.extensions")
    # Cross-field: clip_id uniqueness
    clips = data.get("clips", [])
    if isinstance(clips, list):
        seen_ids: dict[str, int] = {}
        for i, c in enumerate(clips):
            if isinstance(c, dict):
                _validate_upscale_extension(
                    result,
                    c.get("extensions", {}),
                    f"$.clips[{i}].extensions",
                )
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


def _validate_upscale_extension(
    result: ValidationResult,
    extensions: object,
    path: str,
) -> None:
    """Validate the optional LFO-owned video-upscale extension namespace."""
    if not isinstance(extensions, dict) or UPSCALE_EXTENSION_KEY not in extensions:
        return
    for issue in validate_upscale_options(
        extensions[UPSCALE_EXTENSION_KEY],
        f"{path}.{UPSCALE_EXTENSION_KEY}",
    ):
        result.add(issue.path, issue.message, issue.code, issue.value)

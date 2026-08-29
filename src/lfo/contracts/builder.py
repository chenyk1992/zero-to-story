"""Convenient, validated construction of :class:`VideoExecutionPackage`.

Creative Skills should normally use this small builder instead of recreating
the package envelope.  It deliberately accepts the public contract objects;
it does not expose any runtime, database, or backend details.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .assets import AssetSource, AssetSpec, ProvenanceSpec, ReviewDeclaration
from .clips import ClipSpec
from .package import ProjectInfo, VideoExecutionPackage, validate_package
from .timeline import ApprovalDeclaration, OutputPolicy, TimelineSpec


class VideoPackageBuilder:
    """Build one ``lfo.video-execution.v1`` package.

    The API stays intentionally small: add already-described assets and clips,
    set output and creative approval, then call :meth:`build` or :meth:`write`.
    Validation happens before every package is returned or written.
    """

    def __init__(
        self,
        package_id: str,
        title: str,
        *,
        revision: int = 1,
        locale: str | None = None,
        project_id: str,
    ) -> None:
        self._package_id = package_id
        self._revision = revision
        if not project_id:
            raise ValueError("project_id is required for workspace routing")
        self._project = ProjectInfo(title=title, project_id=project_id, locale=locale)
        self._assets: list[AssetSpec] = []
        self._clips: list[ClipSpec] = []
        self._output = OutputPolicy()
        self._approval = ApprovalDeclaration()
        self._timeline = TimelineSpec()
        self._extensions: dict[str, Any] = {}

    def project(
        self,
        title: str,
        *,
        locale: str | None = None,
        project_id: str,
    ) -> VideoPackageBuilder:
        """Replace package-level project metadata."""
        if not project_id:
            raise ValueError("project_id is required for workspace routing")
        self._project = ProjectInfo(title=title, project_id=project_id, locale=locale)
        return self

    def add_asset(
        self,
        asset: AssetSpec | None = None,
        *,
        asset_key: str | None = None,
        media_type: str | None = None,
        uri: str | None = None,
        producer: str | None = None,
        operation: str | None = None,
        source_type: str = "external_skill",
        sha256: str | None = None,
        review_required: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> VideoPackageBuilder:
        """Append an ``AssetSpec`` or construct one from common public fields."""
        if asset is not None and any(
            value is not None for value in (asset_key, media_type, uri, producer, operation)
        ):
            raise ValueError("provide either asset or asset fields, not both")
        if asset is None:
            if not all(isinstance(value, str) and value for value in (
                asset_key, media_type, uri, producer, operation
            )):
                raise ValueError(
                    "asset_key, media_type, uri, producer and operation are required"
                )
            assert isinstance(asset_key, str)
            assert isinstance(media_type, str)
            assert isinstance(uri, str)
            assert isinstance(producer, str)
            assert isinstance(operation, str)
            asset = AssetSpec(
                asset_key=asset_key,
                media_type=media_type,
                source=AssetSource(uri=uri, sha256=sha256),
                provenance=ProvenanceSpec(
                    source_type=source_type,
                    producer=producer,
                    operation=operation,
                ),
                review=ReviewDeclaration(required=review_required),
                metadata=dict(metadata or {}),
            )
        if not isinstance(asset, AssetSpec):
            raise TypeError("asset must be an AssetSpec")
        self._assets.append(asset)
        return self

    def add_clip(
        self,
        clip: ClipSpec | None = None,
        *,
        clip_id: str | None = None,
        sequence: int | None = None,
        duration_ms: int | None = None,
        operation: str | None = None,
        prompt: str | None = None,
        references: list[dict[str, Any]] | None = None,
        requirements: dict[str, Any] | None = None,
        negative_prompt: str | None = None,
        seed: int | None = None,
        audio: dict[str, Any] | None = None,
        subtitles: dict[str, Any] | None = None,
        dependencies: list[str] | None = None,
        source_context: dict[str, Any] | None = None,
        extensions: dict[str, Any] | None = None,
    ) -> VideoPackageBuilder:
        """Append a ``ClipSpec`` or construct one from common public fields."""
        if clip is not None and any(
            value is not None for value in (clip_id, sequence, duration_ms, operation, prompt)
        ):
            raise ValueError("provide either clip or clip fields, not both")
        if clip is None:
            if not (
                isinstance(clip_id, str) and clip_id
                and isinstance(sequence, int) and not isinstance(sequence, bool)
                and isinstance(duration_ms, int) and not isinstance(duration_ms, bool)
                and isinstance(operation, str) and operation
                and isinstance(prompt, str) and prompt
            ):
                raise ValueError(
                    "clip_id, sequence, duration_ms, operation and prompt are required"
                )
            generation: dict[str, Any] = {
                "operation": operation,
                "prompt": prompt,
                "requirements": dict(requirements or {}),
                "references": list(references or []),
            }
            if negative_prompt is not None:
                generation["negative_prompt"] = negative_prompt
            if seed is not None:
                generation["seed"] = seed
            clip = ClipSpec.from_dict(
                {
                    "clip_id": clip_id,
                    "sequence": sequence,
                    "duration_ms": duration_ms,
                    "generation": generation,
                    "audio": dict(audio or {}),
                    "subtitles": dict(subtitles or {}),
                    "dependencies": list(dependencies or []),
                    "source_context": dict(source_context or {}),
                    "extensions": dict(extensions or {}),
                },
                "$.clips[]",
            )
        if not isinstance(clip, ClipSpec):
            raise TypeError("clip must be a ClipSpec")
        self._clips.append(clip)
        return self

    def output(self, output: OutputPolicy | None = None, **values: Any) -> VideoPackageBuilder:
        """Set output policy from an object or public output fields."""
        if output is not None and values:
            raise ValueError("provide either output or output fields, not both")
        if output is not None:
            if not isinstance(output, OutputPolicy):
                raise TypeError("output must be an OutputPolicy")
            self._output = output
        else:
            self._output = OutputPolicy.from_dict(values, "$.output")
        return self

    def approval(
        self,
        approval: ApprovalDeclaration | None = None,
        **values: Any,
    ) -> VideoPackageBuilder:
        """Set the Skill's creative approval declaration."""
        if approval is not None and values:
            raise ValueError("provide either approval or approval fields, not both")
        if approval is not None:
            if not isinstance(approval, ApprovalDeclaration):
                raise TypeError("approval must be an ApprovalDeclaration")
            self._approval = approval
        else:
            self._approval = ApprovalDeclaration.from_dict(values, "$.approval")
        return self

    def timeline(
        self,
        spec: TimelineSpec | None = None,
        **values: Any,
    ) -> VideoPackageBuilder:
        """Set the explicit ordered edit list for the package."""
        if spec is not None and values:
            raise ValueError("provide either a TimelineSpec or timeline fields, not both")
        if spec is not None:
            if not isinstance(spec, TimelineSpec):
                raise TypeError("spec must be a TimelineSpec")
            self._timeline = spec
        else:
            self._timeline = TimelineSpec.from_dict(values, "$.timeline")
        return self

    def extensions(self, **values: Any) -> VideoPackageBuilder:
        """Attach Skill-specific metadata in the contract extension namespace."""
        self._extensions = dict(values)
        return self

    def build(self) -> VideoExecutionPackage:
        """Return a package only after validation succeeds."""
        package = VideoExecutionPackage(
            package_id=self._package_id,
            revision=self._revision,
            project=self._project,
            assets=list(self._assets),
            clips=list(self._clips),
            output=self._output,
            approval=self._approval,
            timeline=self._timeline,
            extensions=dict(self._extensions),
        )
        result = validate_package(package.to_dict())
        if not result.ok:
            messages = "; ".join(
                f"{error.path}: {error.message}" for error in result.errors()
            )
            raise ValueError(f"invalid VideoExecutionPackage: {messages}")
        return package

    def write(self, path: str | Path) -> Path:
        """Validate and write a stable UTF-8 JSON execution package."""
        destination = Path(path)
        package = self.build()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(package.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return destination

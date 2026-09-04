#!/usr/bin/env python3
"""Validate the small sidecar that binds an approved H3 prompt to its plan.

The manifest is deliberately independent from LFO internals.  It is created
by ``h3-prompt-writing`` after the creative blueprint is approved and before a
VideoExecutionPackage is locked.  Its job is to catch accidental prompt/asset
drift cheaply; it does not judge the generated video.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA = "h3.prompt-manifest.v1"
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
KNOWN_OPERATIONS = {
    "video.text_to_video",
    "video.image_to_video",
    "video.first_last_frame",
    "video.reference_to_video",
    "video.virtual_presenter",
    "video.passthrough",
}

JsonObject = dict[str, Any]


@dataclass(frozen=True, slots=True)
class Issue:
    path: str
    message: str

    def as_dict(self) -> JsonObject:
        return {"path": self.path, "message": self.message}

    def format(self) -> str:
        return f"{self.path}: {self.message}"


def _mapping(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _hash_ok(value: object) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def _read_prompt(
    root: Mapping[str, Any],
    *,
    base_dir: Path | None,
    issues: list[Issue],
) -> str | None:
    inline = root.get("prompt")
    prompt_path = root.get("prompt_path")
    if inline is not None and not _text(inline):
        issues.append(Issue("prompt", "must be non-empty text when present"))
    if prompt_path is not None and not _text(prompt_path):
        issues.append(Issue("prompt_path", "must be non-empty text when present"))
    if inline is not None and _text(inline):
        prompt = str(inline)
        if prompt_path is not None and _text(prompt_path):
            if base_dir is None:
                issues.append(Issue("prompt_path", "cannot resolve a relative path without a manifest path"))
            else:
                path = (base_dir / str(prompt_path)).resolve()
                try:
                    path.relative_to(base_dir.resolve())
                except ValueError:
                    issues.append(Issue("prompt_path", "must stay inside the manifest directory"))
                else:
                    try:
                        file_prompt = path.read_text(encoding="utf-8")
                    except OSError as exc:
                        issues.append(Issue("prompt_path", f"cannot read prompt file: {exc}"))
                    else:
                        if file_prompt != prompt:
                            issues.append(Issue("prompt_path", "does not match inline prompt"))
        return prompt
    if prompt_path is None:
        issues.append(Issue("prompt", "provide either inline prompt or prompt_path"))
        return None
    if not _text(prompt_path) or base_dir is None:
        return None
    path = (base_dir / str(prompt_path)).resolve()
    try:
        path.relative_to(base_dir.resolve())
    except ValueError:
        issues.append(Issue("prompt_path", "must stay inside the manifest directory"))
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        issues.append(Issue("prompt_path", f"cannot read prompt file: {exc}"))
        return None


def _window_list(
    value: object,
    *,
    path: str,
    duration_ms: float,
    issues: list[Issue],
    required: bool,
) -> list[Mapping[str, Any]]:
    if value is None and not required:
        return []
    if not isinstance(value, list) or (required and not value):
        issues.append(Issue(path, "must be a non-empty array" if required else "must be an array"))
        return []
    windows: list[Mapping[str, Any]] = []
    ids: set[str] = set()
    previous_end: float | None = None
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        entry = _mapping(item)
        if entry is None:
            issues.append(Issue(item_path, "must be an object"))
            continue
        identifier = entry.get("id")
        if not _text(identifier):
            issues.append(Issue(f"{item_path}.id", "must be non-empty text"))
        elif identifier in ids:
            issues.append(Issue(f"{item_path}.id", "must be unique"))
        else:
            ids.add(str(identifier))
        start, end = entry.get("start_ms"), entry.get("end_ms")
        if not _number(start) or not _number(end) or float(end) <= float(start):
            issues.append(Issue(item_path, "start_ms/end_ms must define a positive window"))
            continue
        if float(start) < 0 or float(end) > duration_ms:
            issues.append(Issue(item_path, "window must stay inside the clip duration"))
        if previous_end is not None:
            if float(start) < previous_end:
                issues.append(Issue(item_path, "windows must not overlap"))
            elif float(start) > previous_end:
                issues.append(Issue(item_path, "window gap is not declared; account for it before locking"))
        previous_end = float(end)
        windows.append(entry)
    if windows and float(windows[0].get("start_ms", -1)) != 0:
        issues.append(Issue(f"{path}[0].start_ms", "the first Setup must start at 0ms"))
    if windows and float(windows[-1].get("end_ms", -1)) != duration_ms:
        issues.append(Issue(f"{path}[-1].end_ms", "the final Setup must end at duration_ms"))
    return windows


def _validate_references(
    root: Mapping[str, Any],
    *,
    operation: str,
    issues: list[Issue],
) -> None:
    value = root.get("references", [])
    if not isinstance(value, list):
        issues.append(Issue("references", "must be an array"))
        return
    labels: set[str] = set()
    slots: set[str] = set()
    media_types: list[str] = []
    for index, item in enumerate(value):
        path = f"references[{index}]"
        reference = _mapping(item)
        if reference is None:
            issues.append(Issue(path, "must be an object"))
            continue
        for field in ("label", "slot", "media_type"):
            if not _text(reference.get(field)):
                issues.append(Issue(f"{path}.{field}", "must be non-empty text"))
        label = reference.get("label")
        slot = reference.get("slot")
        media_type = reference.get("media_type")
        if isinstance(label, str):
            if label in labels:
                issues.append(Issue(f"{path}.label", "must be unique"))
            labels.add(label)
        if isinstance(slot, str):
            if slot in slots:
                issues.append(Issue(f"{path}.slot", "must be unique"))
            slots.add(slot)
        if isinstance(media_type, str):
            media_types.append(media_type)

    if operation == "video.text_to_video" and value:
        issues.append(Issue("references", "text_to_video should not carry reference assets"))
    elif operation == "video.image_to_video":
        if sum(slot == "first_frame" for slot in slots) != 1 or media_types.count("image") < 1:
            issues.append(Issue("references", "image_to_video requires exactly one image bound to first_frame"))
    elif operation == "video.first_last_frame":
        if sum(slot == "first_frame" for slot in slots) != 1 or sum(slot == "last_frame" for slot in slots) != 1:
            issues.append(Issue("references", "first_last_frame requires one first_frame and one last_frame"))
        if media_types.count("image") < 2:
            issues.append(Issue("references", "first_last_frame requires two image references"))
    elif operation == "video.reference_to_video":
        for slot in slots:
            if not re.fullmatch(r"ref_(?:image|video|audio)_\d+", slot):
                issues.append(Issue("references", f"R2V slot {slot!r} must be typed ref_image_N/ref_video_N/ref_audio_N"))


def _validate_dialogue(
    root: Mapping[str, Any],
    *,
    prompt: str,
    duration_ms: float,
    issues: list[Issue],
) -> None:
    value = root.get("dialogue_events", [])
    if not isinstance(value, list):
        issues.append(Issue("dialogue_events", "must be an array"))
        return
    ids: set[str] = set()
    ordered: list[tuple[float, Mapping[str, Any]]] = []
    for index, item in enumerate(value):
        path = f"dialogue_events[{index}]"
        event = _mapping(item)
        if event is None:
            issues.append(Issue(path, "must be an object"))
            continue
        for field in ("event_id", "speaker_id", "text"):
            if not _text(event.get(field)):
                issues.append(Issue(f"{path}.{field}", "must be non-empty text"))
        event_id = event.get("event_id")
        if isinstance(event_id, str):
            if event_id in ids:
                issues.append(Issue(f"{path}.event_id", "must be unique"))
            ids.add(event_id)
        start, end = event.get("start_ms"), event.get("end_ms")
        if not _number(start) or not _number(end) or float(end) <= float(start):
            issues.append(Issue(path, "start_ms/end_ms must define a positive window"))
            continue
        if float(start) < 0 or float(end) > duration_ms:
            issues.append(Issue(path, "speech window must stay inside the clip duration"))
        if _text(event.get("text")) and str(event["text"]) not in prompt:
            issues.append(Issue(f"{path}.text", "exact dialogue text is absent from the H3 prompt"))
        ordered.append((float(start), event))

    ordered.sort(key=lambda item: item[0])
    for previous, current in itertools.pairwise(ordered):
        previous_event, current_event = previous[1], current[1]
        if float(current_event["start_ms"]) < float(previous_event["end_ms"]):
            if not bool(previous_event.get("allow_overlap", False)) and not bool(current_event.get("allow_overlap", False)):
                issues.append(Issue("dialogue_events", "speech events overlap without allow_overlap=true"))
    for field in ("allow_overlap",):
        for index, item in enumerate(value):
            if isinstance(item, Mapping) and field in item and not isinstance(item[field], bool):
                issues.append(Issue(f"dialogue_events[{index}].{field}", "must be boolean"))

    for field in ("overall_soundscape", "non_diegetic_music", "soundscape_text"):
        soundscape = root.get(field)
        if not isinstance(soundscape, str):
            continue
        for index, item in enumerate(value):
            if isinstance(item, Mapping) and _text(item.get("text")) and str(item["text"]) in soundscape:
                issues.append(Issue(field, f"must not repeat dialogue event {item.get('event_id', index)}"))


def validate_prompt_manifest(
    document: object,
    *,
    base_dir: Path | None = None,
) -> list[Issue]:
    """Return all prompt-manifest issues in one pass."""

    issues: list[Issue] = []
    root = _mapping(document)
    if root is None:
        return [Issue("$", "manifest root must be an object")]
    if root.get("schema") != SCHEMA:
        issues.append(Issue("schema", f"must be {SCHEMA!r}"))
    if not _text(root.get("clip_id")):
        issues.append(Issue("clip_id", "must be non-empty text"))
    plan_hash = root.get("plan_hash")
    if not _hash_ok(plan_hash):
        issues.append(Issue("plan_hash", "must be a 64-character SHA-256 hex string"))
    duration = root.get("duration_ms")
    if not _number(duration) or float(duration) <= 0:
        issues.append(Issue("duration_ms", "must be a positive number"))
        duration_ms = 0.0
    else:
        duration_ms = float(duration)
    operation = root.get("operation")
    if not _text(operation):
        issues.append(Issue("operation", "must be non-empty text"))
        operation_text = ""
    else:
        operation_text = str(operation)
        if operation_text not in KNOWN_OPERATIONS:
            issues.append(Issue("operation", f"unknown operation {operation_text!r}"))
    prompt = _read_prompt(root, base_dir=base_dir, issues=issues)
    if prompt is not None:
        prompt_hash = root.get("prompt_hash")
        if not _hash_ok(prompt_hash):
            issues.append(Issue("prompt_hash", "must be a 64-character SHA-256 hex string"))
        elif hashlib.sha256(prompt.encode("utf-8")).hexdigest().lower() != str(prompt_hash).lower():
            issues.append(Issue("prompt_hash", "does not match the supplied prompt"))
    _window_list(
        root.get("setup_windows"),
        path="setup_windows",
        duration_ms=duration_ms,
        issues=issues,
        required=True,
    )
    _validate_dialogue(root, prompt=prompt or "", duration_ms=duration_ms, issues=issues)
    _validate_references(root, operation=operation_text, issues=issues)
    return issues


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an H3 prompt manifest before LFO execution.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)
    try:
        document = _load_json(args.manifest)
        issues = validate_prompt_manifest(document, base_dir=args.manifest.resolve().parent)
    except ValueError as exc:
        issues = [Issue(str(args.manifest), str(exc))]
    if args.json_output:
        print(json.dumps({"ok": not issues, "issues": [issue.as_dict() for issue in issues]}, ensure_ascii=False))
    elif issues:
        print(f"H3 PROMPT PREFLIGHT: FAIL ({len(issues)} issue(s))")
        for issue in issues:
            print(f"- {issue.format()}")
    else:
        print("H3 PROMPT PREFLIGHT: PASS")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())

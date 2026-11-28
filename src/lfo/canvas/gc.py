"""Read-only diagnostics and safe orphan cleanup for Canvas workspace and runtime dirs."""

from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from lfo.canvas.settings import CanvasSettings
from lfo.canvas.store import CanvasStore

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled"})


def _dir_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        if item.is_symlink():
            continue
        try:
            if item.is_file():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def _resolve_ref(raw: Any, project_root: Path) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        candidate = Path(raw.strip()).expanduser()
        if not candidate.is_absolute():
            candidate = project_root / candidate
        return candidate.resolve()
    except OSError:
        return None


def _collect_paths(value: Any, project_root: Path, out: set[Path]) -> None:
    if isinstance(value, Mapping):
        for key in ("path", "output_path", "source_path", "import_path", "import_source_path", "story_source_path", "edit_manifest_path"):
            resolved = _resolve_ref(value.get(key), project_root)
            if resolved is not None:
                out.add(resolved)
        for child in value.values():
            _collect_paths(child, project_root, out)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            _collect_paths(item, project_root, out)


def _dir_has_referenced_file(directory: Path, referenced_paths: set[Path]) -> bool:
    for ref in referenced_paths:
        try:
            if ref == directory or ref.is_relative_to(directory):
                return True
        except ValueError:
            continue
    return False


def _iter_subdirs(parent: Path) -> list[Path]:
    if not parent.is_dir():
        return []
    result: list[Path] = []
    for entry in sorted(parent.iterdir()):
        if entry.is_symlink() or not entry.is_dir():
            continue
        result.append(entry)
    return result


def inspect_and_clean_workspace(
    settings: CanvasSettings,
    *,
    apply: bool = False,
    min_age_seconds: float = 3600.0,
) -> dict[str, Any]:
    """Scan workspace and data_dir for unreferenced orphans; delete only when ``apply=True``."""

    if isinstance(min_age_seconds, bool) or min_age_seconds < 0:
        raise ValueError("min_age_seconds 必须是非负数值")
    now = time.time()
    project_root = settings.project_root.resolve()
    media_root = settings.media_root.resolve()
    data_dir = settings.data_dir.resolve()

    store = CanvasStore(settings.database)
    try:
        canvases = store.list_canvases()
        runs = store.list_runs()
    finally:
        store.close()

    referenced_paths: set[Path] = set()
    for canvas in canvases:
        graph = canvas.get("graph", {})
        _collect_paths(graph, project_root, referenced_paths)
        workspace = graph.get("workspace", {}) if isinstance(graph, Mapping) else {}
        summary_desc = workspace.get("production_summary", {}) if isinstance(workspace, Mapping) else {}
        manifest_raw = summary_desc.get("edit_manifest_path") if isinstance(summary_desc, Mapping) else None
        manifest_path = _resolve_ref(manifest_raw, project_root)
        if manifest_path is not None and manifest_path.is_file():
            referenced_paths.add(manifest_path)
            try:
                manifest_json = json.loads(manifest_path.read_text(encoding="utf-8"))
                _collect_paths(manifest_json, project_root, referenced_paths)
            except (OSError, ValueError, TypeError):
                pass

    active_canvas_ids = {str(canvas["id"]) for canvas in canvases if canvas.get("id")}
    has_running_runs = any(run.get("status") == "running" for run in runs)
    known_run_dirs: set[Path] = set()
    live_input_dirs: set[Path] = set()
    terminal_input_dirs: set[Path] = set()
    failed_cancelled_unreferenced = {"count": 0, "bytes": 0}
    for run in runs:
        out_dir = settings.output_dir(str(run["canvas_id"]), str(run["id"])).resolve()
        known_run_dirs.add(out_dir)
        req_id = run.get("request_id")
        if isinstance(req_id, str) and req_id:
            in_dir = (data_dir / "inputs" / uuid.uuid5(uuid.NAMESPACE_URL, req_id).hex).resolve()
            if run.get("status") in _TERMINAL_STATUSES:
                terminal_input_dirs.add(in_dir)
            else:
                live_input_dirs.add(in_dir)
        if run.get("status") in {"failed", "cancelled"} and out_dir.is_dir():
            if not _dir_has_referenced_file(out_dir, referenced_paths):
                failed_cancelled_unreferenced["count"] += 1
                failed_cancelled_unreferenced["bytes"] += _dir_size(out_dir)
    terminal_input_dirs -= live_input_dirs

    candidates: list[dict[str, Any]] = []
    custom_output_subdirs = {"count": 0, "bytes": 0}
    deleted_canvas_projects = {"count": 0, "final_bytes": 0, "non_final_bytes": 0}
    review_silent_videos = {"count": 0, "bytes": 0}

    projects_root = media_root / "projects"
    for project_dir in _iter_subdirs(projects_root):
        if _UUID_RE.match(project_dir.name) and project_dir.name not in active_canvas_ids:
            deleted_canvas_projects["count"] += 1
            final_dir = project_dir / "final"
            final_bytes = _dir_size(final_dir) if final_dir.is_dir() else 0
            total_proj_bytes = _dir_size(project_dir)
            deleted_canvas_projects["final_bytes"] += final_bytes
            deleted_canvas_projects["non_final_bytes"] += max(0, total_proj_bytes - final_bytes)

        outputs_root = project_dir / "outputs"
        for run_dir in _iter_subdirs(outputs_root):
            for silent_file in (*run_dir.glob("review-*-ready/silent.mp4"), run_dir / "silent.mp4"):
                if silent_file.is_file() and not silent_file.is_symlink():
                    try:
                        review_silent_videos["count"] += 1
                        review_silent_videos["bytes"] += silent_file.stat().st_size
                    except OSError:
                        pass
            resolved = run_dir.resolve()
            if not _UUID_RE.match(run_dir.name):
                if resolved not in known_run_dirs:
                    custom_output_subdirs["count"] += 1
                    custom_output_subdirs["bytes"] += _dir_size(run_dir)
                continue
            if resolved in known_run_dirs or _dir_has_referenced_file(resolved, referenced_paths):
                continue
            try:
                age = now - run_dir.stat().st_mtime
            except OSError:
                continue
            if age < min_age_seconds:
                continue
            candidates.append(
                {
                    "kind": "orphan_run_output_dir",
                    "path": str(run_dir),
                    "size_bytes": _dir_size(run_dir),
                }
            )

    inputs_root = data_dir / "inputs"
    for input_dir in _iter_subdirs(inputs_root):
        resolved = input_dir.resolve()
        if resolved in live_input_dirs or _dir_has_referenced_file(resolved, referenced_paths):
            continue
        try:
            age = now - input_dir.stat().st_mtime
        except OSError:
            continue
        if age < min_age_seconds:
            continue
        kind = (
            "terminal_frozen_input_dir"
            if resolved in terminal_input_dirs
            else "orphan_frozen_input_dir"
        )
        candidates.append(
            {
                "kind": kind,
                "path": str(input_dir),
                "size_bytes": _dir_size(input_dir),
            }
        )

    if not has_running_runs:
        temp_root = data_dir / "temporary"
        for temp_dir in _iter_subdirs(temp_root):
            if not temp_dir.name.startswith("execute-"):
                continue
            try:
                age = now - temp_dir.stat().st_mtime
            except OSError:
                continue
            if age < min_age_seconds:
                continue
            candidates.append(
                {
                    "kind": "stale_temp_execute_dir",
                    "path": str(temp_dir),
                    "size_bytes": _dir_size(temp_dir),
                }
            )

    uploads_unreferenced = {"count": 0, "bytes": 0}
    uploads_root = media_root / "assets" / "uploads"
    if uploads_root.is_dir():
        for entry in sorted(uploads_root.iterdir()):
            if entry.is_symlink() or not entry.is_file():
                continue
            if entry.resolve() not in referenced_paths:
                try:
                    uploads_unreferenced["bytes"] += entry.stat().st_size
                    uploads_unreferenced["count"] += 1
                except OSError:
                    continue

    deleted: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    if apply:
        for item in candidates:
            target = Path(item["path"])
            try:
                shutil.rmtree(target)
                deleted.append(item)
            except OSError as exc:
                errors.append({"path": item["path"], "error": str(exc)})

    return {
        "mode": "apply" if apply else "dry_run",
        "min_age_seconds": min_age_seconds,
        "has_running_runs": has_running_runs,
        "candidate_count": len(candidates),
        "candidate_bytes": sum(item["size_bytes"] for item in candidates),
        "candidates": candidates,
        "deleted_count": len(deleted),
        "freed_bytes": sum(item["size_bytes"] for item in deleted),
        "errors": errors,
        "diagnostics": {
            "unreferenced_uploads": uploads_unreferenced,
            "unreferenced_failed_or_cancelled_runs": failed_cancelled_unreferenced,
            "custom_output_subdirs": custom_output_subdirs,
            "deleted_canvas_projects": deleted_canvas_projects,
            "review_silent_videos": review_silent_videos,
        },
        "protected_note": "已接受(ACCEPT)、被拒派生源(REJECT)、非终态冻结输入(running/unknown/queued/pending_agent)、自定义后期子目录、uploads 与 projects/*/final/ 均受保护，不会被删除。",
    }

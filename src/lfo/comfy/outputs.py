"""Collect the unique video reported by one synchronous comfy-cli execution."""
from __future__ import annotations

import pathlib
import tempfile
from urllib.parse import urlencode

from lfo.comfy.cli import ComfyCliOutput, ComfyCliRunResult
from lfo.comfy.client import ComfyApiClient
from lfo.comfy.exceptions import LfoComfyError
from lfo.services.artifact_layout import atomic_copy_verified

_VIDEO_OUTPUT_EXTENSIONS = frozenset({".mp4", ".mov", ".mkv", ".webm"})


def resolve_cli_video(
    result: ComfyCliRunResult,
    output_root: pathlib.Path | None,
) -> tuple[pathlib.Path | None, ComfyCliOutput]:
    """Resolve exactly one video output, preferring the CLI's absolute path."""
    output_root = output_root.resolve() if output_root is not None else None
    videos = [
        item
        for item in result.outputs
        if pathlib.Path(item.filename).suffix.lower() in _VIDEO_OUTPUT_EXTENSIONS
    ]
    if not videos:
        raise LfoComfyError(
            f"comfy-cli prompt {result.prompt_id} did not report a video output"
        )

    absolute_items = [item for item in videos if item.file_type == "absolute"]
    absolute_paths = {
        pathlib.Path(item.filename).resolve() for item in absolute_items
    }
    if output_root is not None:
        outside_root = [
            path for path in absolute_paths if not path.is_relative_to(output_root)
        ]
        if outside_root:
            raise LfoComfyError(
                "comfy-cli reported an absolute video outside the configured output root"
            )
    if len(absolute_paths) > 1:
        raise LfoComfyError(
            f"comfy-cli prompt {result.prompt_id} reported ambiguous video outputs"
        )

    # ``comfy run`` may report the same file both as an absolute path and
    # as a normal ``/view`` output.  Treat those records as equivalent only
    # when their resolved physical paths are identical; otherwise selecting
    # the absolute record would silently hide a second video.
    downloadable_items = [
        item for item in videos if item.file_type in {"output", "temp"}
    ]
    downloadable_by_path: dict[pathlib.Path, ComfyCliOutput] = {}
    unresolved_downloadables: list[ComfyCliOutput] = []
    for item in downloadable_items:
        declared_path = pathlib.Path(item.subfolder) / pathlib.Path(item.filename)
        if output_root is not None and item.file_type == "output":
            path = (output_root / declared_path).resolve()
            if not path.is_relative_to(output_root):
                raise LfoComfyError(
                    "comfy-cli video output escaped the configured output root"
                )
        elif declared_path.is_absolute():
            path = declared_path.resolve()
        else:
            path = None
        if path is None:
            unresolved_downloadables.append(item)
        else:
            downloadable_by_path.setdefault(path, item)

    if len(downloadable_by_path) > 1 or (
        unresolved_downloadables
        and len(downloadable_by_path) + len(unresolved_downloadables) > 1
    ):
        raise LfoComfyError(
            f"comfy-cli prompt {result.prompt_id} reported ambiguous video outputs"
        )

    selected_downloadable: ComfyCliOutput | None = None
    downloadable_path: pathlib.Path | None = None
    if downloadable_by_path:
        downloadable_path, selected_downloadable = next(
            iter(downloadable_by_path.items())
        )
    elif unresolved_downloadables:
        selected_downloadable = unresolved_downloadables[0]

    absolute_path = next(iter(absolute_paths), None)
    if absolute_path is not None and downloadable_items:
        if downloadable_path is None or downloadable_path != absolute_path:
            raise LfoComfyError(
                f"comfy-cli prompt {result.prompt_id} reported ambiguous video outputs"
            )
    if absolute_paths:
        path = absolute_path
        assert path is not None
        if path.is_file():
            selected = next(
                item
                for item in absolute_items
                if pathlib.Path(item.filename).resolve() == path
            )
            return path, selected

    if selected_downloadable is None:
        raise LfoComfyError(
            f"No usable video output found for comfy-cli prompt {result.prompt_id}"
        )
    if output_root is None:
        return None, selected_downloadable
    if downloadable_path is None:
        return None, selected_downloadable
    return (
        downloadable_path if downloadable_path.is_file() else None,
        selected_downloadable,
    )

def materialize_cli_video(
    result: ComfyCliRunResult,
    managed: pathlib.Path,
    *,
    output_root: pathlib.Path | None,
    client: ComfyApiClient,
    timeout_seconds: float,
    base_url: str,
) -> tuple[str, int, str]:
    """Copy a local result or fetch the CLI's canonical ``/view`` output."""
    local_output, selected = resolve_cli_video(result, output_root)
    if local_output is not None:
        digest, size = atomic_copy_verified(local_output, managed)
        return digest, size, str(local_output)

    with tempfile.TemporaryDirectory(prefix="lfo-comfy-output-") as temp_dir:
        downloaded = client.download_output(
            selected.filename,
            pathlib.Path(temp_dir) / pathlib.Path(selected.filename).name,
            subfolder=selected.subfolder,
            file_type=selected.file_type,
            timeout=timeout_seconds,
        )
        digest, size = atomic_copy_verified(downloaded, managed)
    query = urlencode({
        "filename": selected.filename,
        "subfolder": selected.subfolder,
        "type": selected.file_type,
    })
    source = selected.url or f"{base_url.rstrip('/')}/view?{query}"
    return digest, size, source

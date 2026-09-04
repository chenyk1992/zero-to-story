"""Thin synchronous adapter for the official ``comfy`` CLI."""
from __future__ import annotations

import json
import math
import pathlib
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .exceptions import ComfyCliTimeoutError, LfoComfyError


@dataclass(frozen=True)
class ComfyCliOutput:
    """One file-like output reported by ``comfy run``."""

    filename: str
    subfolder: str = ""
    file_type: str = "output"
    url: str | None = None


@dataclass(frozen=True)
class ComfyCliRunResult:
    """Terminal result of one synchronous workflow execution."""

    prompt_id: str
    outputs: tuple[ComfyCliOutput, ...]


ProcessRunner = Callable[..., subprocess.CompletedProcess[str]]

_PROCESS_EXIT_GRACE_SECONDS = 300.0


class ComfyCliRunner:
    """Run exactly one local ComfyUI workflow and wait for its result."""

    def __init__(
        self,
        binary: str = "comfy",
        *,
        process_runner: ProcessRunner = subprocess.run,
    ) -> None:
        self.binary = binary
        self._process_runner = process_runner

    def run_workflow(
        self,
        workflow: dict[str, Any],
        *,
        base_url: str,
        timeout_seconds: float,
    ) -> ComfyCliRunResult:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not math.isfinite(float(timeout_seconds))
            or timeout_seconds <= 0
        ):
            raise ValueError("comfy-cli timeout_seconds must be a positive finite number")
        cli_timeout_seconds = max(1, int(timeout_seconds))
        process_timeout_seconds = float(timeout_seconds) + _PROCESS_EXIT_GRACE_SECONDS
        host, port = _host_and_port(base_url)
        with tempfile.TemporaryDirectory(prefix="lfo-comfy-") as temp_dir:
            workflow_path = pathlib.Path(temp_dir) / "workflow.json"
            workflow_path.write_text(
                json.dumps(workflow, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            command = [
                self.binary,
                "--skip-prompt",
                "--where",
                "local",
                "run",
                "--workflow",
                str(workflow_path),
                "--wait",
                "--host",
                host,
                "--port",
                str(port),
                "--timeout",
                str(cli_timeout_seconds),
                "--no-notify",
                "--json",
            ]
            try:
                completed = self._process_runner(
                    command,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                    timeout=process_timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise ComfyCliTimeoutError(
                    "comfy-cli exceeded its hard wall-clock limit "
                    f"of {process_timeout_seconds:g} seconds"
                ) from exc
            except FileNotFoundError as exc:
                raise LfoComfyError(
                    "comfy-cli executable was not found; install it and ensure 'comfy' is on PATH"
                ) from exc
            except OSError as exc:
                raise LfoComfyError(f"could not start comfy-cli: {exc}") from exc

        events = _parse_events(completed.stdout)
        envelope = next(
            (event for event in reversed(events) if event.get("type") == "envelope"),
            None,
        )
        if envelope is None:
            detail = completed.stderr.strip() or "missing terminal JSON envelope"
            raise LfoComfyError(f"comfy-cli did not return a terminal result: {detail}")
        data = envelope.get("data")
        if isinstance(data, dict) and _is_timeout_status(data.get("status")):
            raise ComfyCliTimeoutError(
                "comfy-cli workflow timed out",
                prompt_id=_prompt_id_from_envelope(envelope),
            )
        if completed.returncode != 0 or envelope.get("ok") is not True:
            error = envelope.get("error")
            if isinstance(error, dict):
                code = str(error.get("code") or "execution_failed")
                message = str(error.get("message") or "workflow execution failed")
                if _is_timeout_error(code, message):
                    raise ComfyCliTimeoutError(
                        f"comfy-cli {code}: {message}",
                        prompt_id=_prompt_id_from_envelope(envelope),
                    )
                raise LfoComfyError(f"comfy-cli {code}: {message}")
            raise LfoComfyError(
                f"comfy-cli failed with exit code {completed.returncode}"
            )

        validation_warnings = [
            event.get("validation_warnings")
            for event in events
            if event.get("type") == "queued" and event.get("validation_warnings")
        ]
        if validation_warnings:
            raise LfoComfyError(
                "comfy-cli queued a partially valid workflow; output was not accepted"
            )

        if not isinstance(data, dict) or data.get("status") != "completed":
            raise LfoComfyError("comfy-cli returned success without a completed workflow")
        warnings = data.get("warnings")
        if warnings not in (None, []):
            raise LfoComfyError(
                "comfy-cli completed with partial-execution warnings; output was not accepted"
            )
        prompt_id = data.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise LfoComfyError("comfy-cli result did not include prompt_id")

        # Local ``--wait`` envelopes normally contain absolute on-disk paths.
        # Prefer those, then merge richer per-node records for older/alternate
        # CLI output without requiring a machine-specific path in source.
        outputs = _outputs_from_urls(data.get("outputs"))
        seen = {(item.filename, item.subfolder, item.file_type) for item in outputs}
        for item in _outputs_from_events(events, prompt_id=prompt_id):
            key = (item.filename, item.subfolder, item.file_type)
            if key not in seen:
                outputs.append(item)
                seen.add(key)
        if not outputs:
            raise LfoComfyError(f"comfy-cli prompt {prompt_id} completed without file output")
        return ComfyCliRunResult(prompt_id=prompt_id, outputs=tuple(outputs))


def _is_timeout_error(code: str, message: str) -> bool:
    """Recognize an explicit timeout error reported by ``comfy run``."""
    normalized_code = code.strip().lower().replace("-", "_").replace(" ", "_")
    normalized_message = message.strip().lower()
    return "timeout" in normalized_code or "timed_out" in normalized_code or (
        "timed out" in normalized_message
    )


def _is_timeout_status(status: object) -> bool:
    if not isinstance(status, str):
        return False
    normalized = status.strip().lower().replace("-", "_").replace(" ", "_")
    return normalized in {"timeout", "timed_out"}


def _prompt_id_from_envelope(envelope: dict[str, Any]) -> str | None:
    """Extract a prompt id when a timeout envelope includes one."""
    prompt_id = envelope.get("prompt_id")
    if isinstance(prompt_id, str) and prompt_id:
        return prompt_id
    for key in ("data", "result", "error"):
        value = envelope.get(key)
        if isinstance(value, dict):
            prompt_id = value.get("prompt_id")
            if isinstance(prompt_id, str) and prompt_id:
                return prompt_id
    return None


def _parse_events(stdout: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(stdout.splitlines(), 1):
        line = raw_line.lstrip("\ufeff").strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LfoComfyError(
                f"comfy-cli returned invalid JSON on stdout line {line_number}"
            ) from exc
        if not isinstance(value, dict):
            raise LfoComfyError(
                f"comfy-cli returned a non-object event on stdout line {line_number}"
            )
        events.append(value)
    return events


def _outputs_from_events(
    events: list[dict[str, Any]], *, prompt_id: str
) -> list[ComfyCliOutput]:
    """Collect only executed outputs belonging to the completed prompt."""
    outputs: list[ComfyCliOutput] = []
    seen: set[tuple[str, str, str]] = set()
    for event in events:
        # Current comfy-cli event/1 records include prompt_id on executed
        # events.  Treat a missing id as non-matching instead of allowing an
        # unrelated execution's output into this envelope.
        if event.get("type") != "executed" or event.get("prompt_id") != prompt_id:
            continue
        values = event.get("outputs")
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, dict):
                continue
            filename = value.get("filename")
            if not isinstance(filename, str) or not filename:
                continue
            subfolder = str(value.get("subfolder") or "")
            file_type = str(value.get("type") or "output")
            key = (filename, subfolder, file_type)
            if key in seen:
                continue
            seen.add(key)
            url = value.get("url")
            outputs.append(
                ComfyCliOutput(
                    filename=filename,
                    subfolder=subfolder,
                    file_type=file_type,
                    url=url if isinstance(url, str) else None,
                )
            )
    return outputs


def _outputs_from_urls(value: object) -> list[ComfyCliOutput]:
    if not isinstance(value, list):
        return []
    outputs: list[ComfyCliOutput] = []
    for item in value:
        if not isinstance(item, str):
            continue
        parsed = urlsplit(item)
        query = parse_qs(parsed.query)
        filename = query.get("filename", [""])[0]
        if filename:
            outputs.append(
                ComfyCliOutput(
                    filename=filename,
                    subfolder=query.get("subfolder", [""])[0],
                    file_type=query.get("type", ["output"])[0],
                    url=item,
                )
            )
            continue
        local_path = pathlib.Path(item)
        if local_path.is_file():
            outputs.append(
                ComfyCliOutput(filename=str(local_path.resolve()), file_type="absolute")
            )
    return outputs


def _host_and_port(base_url: str) -> tuple[str, int]:
    parsed = urlsplit(base_url if "://" in base_url else f"http://{base_url}")
    # Local comfy run accepts host/port and constructs HTTP URLs itself.
    # Never silently downgrade a configured HTTPS endpoint or discard auth.
    if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
        raise LfoComfyError("local comfy-cli requires an HTTP host/port URL without credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise LfoComfyError("local comfy-cli base_url cannot contain a path, query or fragment")
    try:
        port = parsed.port
    except ValueError as exc:
        raise LfoComfyError("invalid local ComfyUI port") from exc
    return parsed.hostname, port or 8188

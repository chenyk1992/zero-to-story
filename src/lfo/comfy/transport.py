"""Shared local Comfy connection, preflight and official CLI transport."""

from __future__ import annotations

import json
import math
import os
import pathlib
import queue
import shlex
import shutil
import socket
import subprocess
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen

PROCESS_EXIT_GRACE_SECONDS = 300.0
DYNAMIC_MEDIA_INPUTS = {
    "LoadImage": frozenset({"image"}),
    "LoadVideo": frozenset({"file"}),
    "LoadAudio": frozenset({"audio"}),
}
Uploader = Callable[[pathlib.Path], str]
_STREAM_END = object()


class ExecutorError(RuntimeError):
    """A terminal, non-retryable adapter error."""

    stage: str

    def __init__(
        self,
        message: str,
        *,
        provider_task_id: str | None = None,
        status: str = "failed",
    ) -> None:
        super().__init__(message)
        self.provider_task_id = provider_task_id
        if status not in {"failed", "unknown"}:
            raise ValueError(f"unsupported executor error status: {status}")
        self.status = status


@dataclass(frozen=True)
class RuntimeConfig:
    base_url: str = "http://127.0.0.1:8188"
    cli_binary: str = "comfy"
    timeout_seconds: float = 7_200.0
    output_root: pathlib.Path | None = None


@dataclass(frozen=True)
class OutputRef:
    filename: str
    subfolder: str = ""
    file_type: str = "output"
    url: str | None = None


@dataclass(frozen=True)
class CliResult:
    provider_task_id: str
    outputs: tuple[OutputRef, ...]
    events: tuple[dict[str, Any], ...]


def _read_json(path: pathlib.Path, *, explicit: bool = False) -> dict[str, Any] | None:
    if not path.exists():
        if explicit:
            raise ExecutorError(f"Comfy config file does not exist: {path}")
        return None
    if not path.is_file():
        raise ExecutorError(f"Comfy config path is not a file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExecutorError(f"Could not read Comfy config {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ExecutorError(f"Comfy config must be a JSON object: {path}")
    return value


def _safe_config_values(value: dict[str, Any]) -> dict[str, Any]:
    """Keep only provider connection fields; never expose unrelated settings."""
    comfy = value.get("comfyui")
    comfy = comfy if isinstance(comfy, dict) else {}
    storage = value.get("storage")
    storage = storage if isinstance(storage, dict) else {}
    result: dict[str, Any] = {}
    for key in ("base_url", "cli"):
        candidate = comfy.get(key, value.get(key))
        if candidate is not None:
            result[key] = candidate
    timeout = comfy.get(
        "timeout_seconds",
        comfy.get("timeout_sec", value.get("timeout_seconds", value.get("timeout_sec"))),
    )
    if timeout is not None:
        result["timeout_seconds"] = timeout
    output_root = (
        comfy.get("output_root") or storage.get("comfy_output") or value.get("output_root")
    )
    if output_root is not None:
        result["output_root"] = output_root
    return result


def _merge_runtime_values(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in _safe_config_values(source).items():
        target[key] = value


def load_runtime_config(
    *,
    config_path: pathlib.Path | None = None,
    machine_id: str | None = None,
    base_url: str | None = None,
    cli_binary: str | None = None,
    timeout_seconds: float | None = None,
) -> RuntimeConfig:
    """Resolve only safe Comfy connection settings.

    Existing LFO config is read opportunistically but no LFO module is
    imported.  Explicit command-line values have the final say.
    """
    values: dict[str, Any] = {}
    appdata = os.environ.get("APPDATA")
    if appdata:
        global_path = pathlib.Path(appdata) / "LFO" / "config.json"
        global_config = _read_json(global_path)
        if global_config is not None:
            _merge_runtime_values(values, global_config)
        selected_machine = machine_id or os.environ.get("LFO_MACHINE_ID")
        if selected_machine:
            machine_path = pathlib.Path(appdata) / "LFO" / "machines" / f"{selected_machine}.json"
            machine_config = _read_json(machine_path)
            if machine_config is not None:
                _merge_runtime_values(values, machine_config)
    if config_path is not None:
        explicit_config = _read_json(config_path, explicit=True)
        assert explicit_config is not None
        _merge_runtime_values(values, explicit_config)

    env_values = {
        "base_url": os.environ.get("LFO_COMFY_BASE_URL"),
        "cli": os.environ.get("LFO_COMFY_CLI"),
        "timeout_seconds": os.environ.get("LFO_COMFY_TIMEOUT"),
        "output_root": os.environ.get("LFO_COMFY_OUTPUT_ROOT"),
    }
    for key, value in env_values.items():
        if value:
            values[key] = value
    if base_url is not None:
        values["base_url"] = base_url
    if cli_binary is not None:
        values["cli"] = cli_binary
    if timeout_seconds is not None:
        values["timeout_seconds"] = timeout_seconds

    resolved_url = str(values.get("base_url") or "http://127.0.0.1:8188")
    resolved_cli = str(values.get("cli") or "comfy")
    raw_timeout = values.get("timeout_seconds", 7_200.0)
    try:
        resolved_timeout = float(raw_timeout)
    except (TypeError, ValueError) as exc:
        raise ExecutorError("Comfy timeout must be a positive finite number") from exc
    if not math.isfinite(resolved_timeout) or resolved_timeout <= 0:
        raise ExecutorError("Comfy timeout must be a positive finite number")
    output_value = values.get("output_root")
    return RuntimeConfig(
        base_url=resolved_url,
        cli_binary=resolved_cli,
        timeout_seconds=resolved_timeout,
        output_root=pathlib.Path(str(output_value)).expanduser() if output_value else None,
    )


def _parse_base_url(base_url: str) -> tuple[str, int]:
    parsed = urlsplit(base_url if "://" in base_url else f"http://{base_url}")
    if parsed.scheme != "http" or not parsed.hostname or parsed.username or parsed.password:
        raise ExecutorError("local Comfy URL must be an HTTP host without credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ExecutorError("local Comfy URL cannot contain a path, query, or fragment")
    try:
        port = parsed.port or 8188
    except ValueError as exc:
        raise ExecutorError("local Comfy URL has an invalid port") from exc
    return parsed.hostname, port


def _http_uploader(base_url: str, timeout: float) -> Uploader:
    def upload(path: pathlib.Path) -> str:
        boundary = f"----canvas-comfy-{uuid.uuid4().hex}"
        upload_name = f"canvas-{uuid.uuid4().hex}-{path.name}"
        content = path.read_bytes()
        parts = [
            f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{upload_name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode(),
            content,
            f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="type"\r\n\r\ninput\r\n'.encode(),
            f'--{boundary}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\nfalse\r\n--{boundary}--\r\n'.encode(),
        ]
        request = Request(
            base_url.rstrip("/") + "/upload/image",
            data=b"".join(parts),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, HTTPError, URLError, json.JSONDecodeError) as exc:
            raise ExecutorError(f"Could not upload Comfy input {path.name}: {exc}") from exc
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("name"), str)
            or not payload["name"]
        ):
            raise ExecutorError(f"Comfy upload response for {path.name} has no file name")
        if payload.get("type") != "input":
            raise ExecutorError(
                f"Comfy upload response for {path.name} has an unexpected file type"
            )
        subfolder = payload.get("subfolder")
        if subfolder is not None and not isinstance(subfolder, str):
            raise ExecutorError(f"Comfy upload response for {path.name} has an invalid subfolder")
        return (
            f"{subfolder}/{payload['name']}"
            if isinstance(subfolder, str) and subfolder
            else payload["name"]
        )

    return upload


def _fetch_object_info(base_url: str, timeout: float) -> dict[str, Any]:
    request = Request(base_url.rstrip("/") + "/object_info", method="GET")
    try:
        with urlopen(request, timeout=min(timeout, 30.0)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, HTTPError, URLError, json.JSONDecodeError) as exc:
        raise ExecutorError(f"Comfy preflight could not read /object_info: {exc}") from exc
    if not isinstance(payload, dict):
        raise ExecutorError("Comfy /object_info returned a non-object payload")
    return payload


def ensure_local_service(config: RuntimeConfig) -> None:
    from .exceptions import LfoComfyError

    try:
        _ensure_local_service(config)
    except LfoComfyError as exc:
        # Preserve the existing request's receipt; this new request was never submitted.
        raise ExecutorError(str(exc)) from exc


def _ensure_local_service(config: RuntimeConfig) -> None:
    """Start the configured local install once through CLI, then wait for readiness."""
    from .admission import VideoSubmissionGuard, state_directory

    host, port = _parse_base_url(config.base_url)
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise ExecutorError("Automatic launch requires a local HTTP Comfy service")
    with VideoSubmissionGuard(config.base_url):
        try:
            _fetch_object_info(config.base_url, 3)
            (state_directory() / "startup.json").unlink(missing_ok=True)
            return
        except ExecutorError as exc:
            if not _connection_unavailable(exc):
                raise
        if _port_open(host, port):
            raise ExecutorError(
                "Comfy endpoint is already listening but not ready; no duplicate launch"
            )
        folder = state_directory()
        marker = folder / "startup.json"
        log_path = folder / "startup.log"
        if marker.exists():
            raise ExecutorError(
                f"Previous Comfy startup has not reached readiness; inspect {log_path}. No duplicate launch"
            )
        cli = shutil.which(config.cli_binary) or config.cli_binary
        try:
            discovery = subprocess.run(
                [cli, "env"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
                check=False,
            )
            envelope = json.loads(discovery.stdout)
            profile = envelope["data"]
            workspace = pathlib.Path(profile["workspace"]["path"])
        except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError) as exc:
            raise ExecutorError(f"Could not resolve configured Comfy workspace: {exc}") from exc
        if discovery.returncode or not (workspace / "main.py").is_file():
            raise ExecutorError("Configured Comfy workspace is not an existing installation")
        env = os.environ.copy()
        # Canvas's own virtualenv must never become Comfy's model runtime.
        env.pop("VIRTUAL_ENV", None)
        env.pop("CONDA_PREFIX", None)
        env.pop("PYTHONPATH", None)
        configured_env = os.environ.get("LFO_COMFY_VENV")
        candidates = (
            [pathlib.Path(configured_env)]
            if configured_env
            else [workspace / ".venv", workspace / "venv", workspace.parent / "standalone-env"]
        )
        for candidate in candidates:
            executable = candidate / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            if executable.is_file():
                env["VIRTUAL_ENV"] = str(candidate)
                break
        else:
            if configured_env:
                raise ExecutorError("LFO_COMFY_VENV does not contain an existing Python runtime")
        extras = shlex.split(
            profile.get("config", {}).get("default_launch_extras") or "", posix=False
        )
        extras = [part.strip('"') for part in extras]
        # Explicit endpoint comes from the same runtime config used for submission.
        for flag in ("--port", "--listen"):
            if flag in extras:
                i = extras.index(flag)
                del extras[i : i + 2]
        extras.extend(["--listen", host, "--port", str(port), "--disable-auto-launch"])
        command = [cli, "--workspace", str(workspace), "launch", "--", *extras]
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        marker.write_text(
            json.dumps({"base_url": config.base_url, "workspace": str(workspace)}), encoding="utf-8"
        )
        try:
            with log_path.open("wb") as log:
                process = subprocess.Popen(
                    command,
                    cwd=workspace,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
        except OSError as exc:
            marker.unlink(missing_ok=True)
            raise ExecutorError(f"Could not launch Comfy CLI: {exc}") from exc
        marker.write_text(
            json.dumps(
                {"pid": process.pid, "base_url": config.base_url, "workspace": str(workspace)}
            ),
            encoding="utf-8",
        )
        deadline = time.monotonic() + min(config.timeout_seconds, 180)
        while time.monotonic() < deadline:
            try:
                _fetch_object_info(config.base_url, 3)
                marker.unlink(missing_ok=True)
                return
            except ExecutorError as exc:
                if not _connection_unavailable(exc):
                    raise
            if process.poll() is not None:
                marker.unlink(missing_ok=True)
                raise ExecutorError(f"Comfy CLI exited during startup; inspect {log_path}")
            time.sleep(1)
        raise ExecutorError(
            f"Comfy startup timed out; inspect {log_path}. No second launch was attempted"
        )


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=3):
            return True
    except OSError:
        return False


def _connection_unavailable(exc: ExecutorError) -> bool:
    cause = exc.__cause__
    if isinstance(cause, HTTPError):
        return False
    if isinstance(cause, URLError):
        cause = cause.reason
    return isinstance(cause, (ConnectionRefusedError, TimeoutError))


def _input_specs(node_info: object) -> dict[str, Any]:
    if not isinstance(node_info, dict):
        return {}
    inputs = node_info.get("input")
    if not isinstance(inputs, dict):
        return {}
    result: dict[str, Any] = {}
    for section in ("required", "optional"):
        values = inputs.get(section)
        if isinstance(values, dict):
            result.update(values)
    return result


def _choice_values(spec: object) -> list[object] | None:
    if isinstance(spec, dict):
        for key in ("enum", "choices", "options"):
            values = spec.get(key)
            if isinstance(values, list):
                return values
        return None
    if isinstance(spec, (list, tuple)) and spec:
        first = spec[0]
        if isinstance(first, (list, tuple, set)):
            return list(first)
    return None


def preflight_workflow(
    workflow: dict[str, Any],
    config: RuntimeConfig,
    *,
    object_info: dict[str, Any] | None = None,
) -> None:
    """Check node classes and server-advertised enum/model values before submit."""
    if object_info is not None:
        info = object_info
    else:
        try:
            info = _fetch_object_info(config.base_url, min(config.timeout_seconds, 3))
        except ExecutorError as exc:
            if not _connection_unavailable(exc):
                raise
            ensure_local_service(config)
            info = _fetch_object_info(config.base_url, config.timeout_seconds)
    missing: list[str] = []
    invalid: list[str] = []
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            invalid.append(f"node {node_id} is not an object")
            continue
        class_type = node.get("class_type")
        if not isinstance(class_type, str) or not class_type:
            invalid.append(f"node {node_id} has no class_type")
            continue
        node_info = info.get(class_type)
        if not isinstance(node_info, dict):
            missing.append(f"{class_type} (node {node_id})")
            continue
        values = node.get("inputs")
        if not isinstance(values, dict):
            invalid.append(f"node {node_id} has no inputs object")
            continue
        specs = _input_specs(node_info)
        for input_name, value in values.items():
            if isinstance(value, list):
                continue
            if input_name in DYNAMIC_MEDIA_INPUTS.get(class_type, frozenset()):
                # These choices are the server's current file listing.  The
                # adapter uploads confirmed media immediately before this
                # preflight, so they are not model/enum constraints.
                continue
            spec = specs.get(input_name)
            choices = _choice_values(spec)
            if choices is not None and value not in choices:
                invalid.append(f"{class_type}.{input_name}={value!r}")
    if missing:
        raise ExecutorError("Comfy preflight missing node classes: " + ", ".join(missing))
    if invalid:
        raise ExecutorError("Comfy preflight rejected workflow inputs: " + ", ".join(invalid))


def _parse_events(stdout: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for number, line in enumerate(stdout.splitlines(), 1):
        stripped = line.strip().lstrip("\ufeff")
        if not stripped:
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ExecutorError(f"comfy-cli returned invalid JSON on stdout line {number}") from exc
        if not isinstance(event, dict):
            raise ExecutorError(f"comfy-cli returned a non-object event on stdout line {number}")
        events.append(event)
    return events


def _output_ref(value: object) -> OutputRef | None:
    if isinstance(value, str):
        parsed = urlsplit(value)
        if parsed.scheme and parsed.netloc:
            query = parse_qs(parsed.query)
            filename = query.get("filename", [""])[0]
            if filename:
                return OutputRef(
                    filename=filename,
                    subfolder=query.get("subfolder", [""])[0],
                    file_type=query.get("type", ["output"])[0],
                    url=value,
                )
        return OutputRef(
            filename=value, file_type="absolute" if pathlib.Path(value).is_absolute() else "output"
        )
    if not isinstance(value, dict):
        return None
    filename = value.get("filename")
    if not isinstance(filename, str) or not filename:
        return None
    url = value.get("url")
    file_type = str(value.get("type") or "output")
    if pathlib.Path(filename).is_absolute():
        file_type = "absolute"
    return OutputRef(
        filename=filename,
        subfolder=str(value.get("subfolder") or ""),
        file_type=file_type,
        url=url if isinstance(url, str) else None,
    )


def _collect_outputs(events: list[dict[str, Any]], prompt_id: str) -> tuple[OutputRef, ...]:
    values: list[object] = []
    envelope = next((event for event in reversed(events) if event.get("type") == "envelope"), None)
    has_envelope_outputs = False
    if isinstance(envelope, dict):
        data = envelope.get("data")
        if isinstance(data, dict) and isinstance(data.get("outputs"), list):
            values.extend(data["outputs"])
            has_envelope_outputs = bool(data["outputs"])
    if not has_envelope_outputs:
        for event in events:
            if event.get("type") == "executed" and event.get("prompt_id") == prompt_id:
                if isinstance(event.get("outputs"), list):
                    values.extend(event["outputs"])
    result: list[OutputRef] = []
    seen: set[tuple[str, str, str]] = set()
    for value in values:
        reference = _output_ref(value)
        if reference is None:
            continue
        key = (reference.filename, reference.subfolder, reference.file_type)
        if key not in seen:
            result.append(reference)
            seen.add(key)
    return tuple(result)


def _read_process_stream(stream: Any, target: queue.Queue[object]) -> None:
    try:
        for line in stream:
            target.put(line)
    finally:
        target.put(_STREAM_END)


def _progress_event(
    event: dict[str, Any],
    provider_task_id: str | None,
) -> dict[str, Any] | None:
    """Translate official comfy-cli events to the small canvas event contract."""
    event_type = event.get("type")
    if event_type not in {"queued", "progress", "executed"}:
        return None
    event_id = event.get("prompt_id")
    if not isinstance(event_id, str) or not event_id:
        event_id = provider_task_id
    payload: dict[str, Any] = {
        "event": str(event_type),
        "status": "queued" if event_type == "queued" else "running",
        "stage": "generation",
    }
    if event_id:
        payload["provider_task_id"] = event_id
    if event_type == "progress":
        for key in ("value", "max", "node"):
            if key in event:
                payload[key] = event[key]
    return payload


def _emit_progress(
    event: dict[str, Any],
    provider_task_id: str | None,
    emit: Callable[[dict[str, Any]], None] | None,
) -> None:
    if emit is None:
        return
    payload = _progress_event(event, provider_task_id)
    if payload is not None:
        emit(payload)


def run_comfy_cli(
    workflow_path: pathlib.Path,
    config: RuntimeConfig,
    *,
    emit: Callable[[dict[str, Any]], None] | None = None,
    request_id: str | None = None,
) -> CliResult:
    from lfo.comfy.admission import VideoSubmissionGuard
    from lfo.comfy.exceptions import LfoComfyError

    try:
        with VideoSubmissionGuard(config.base_url, request_id=request_id) as guard:
            guard.submitted()

            def progress(event: dict[str, Any]) -> None:
                if event.get("provider_task_id"):
                    guard.submitted(str(event["provider_task_id"]))
                if event.get("remote_finished") is True:
                    guard.finished()
                if emit is not None:
                    emit(event)

            try:
                result = _run_comfy_cli(workflow_path, config, emit=progress)
            except ExecutorError as exc:
                if exc.status == "failed":
                    guard.finished()
                elif exc.provider_task_id:
                    guard.submitted(exc.provider_task_id)
                raise
            guard.finished()
            return result
    except LfoComfyError as exc:
        raise ExecutorError(str(exc)) from exc


def _run_comfy_cli(
    workflow_path: pathlib.Path,
    config: RuntimeConfig,
    *,
    emit: Callable[[dict[str, Any]], None] | None = None,
) -> CliResult:
    """Run the official CLI and forward NDJSON events while it is running."""
    host, port = _parse_base_url(config.base_url)
    command = [
        config.cli_binary,
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
        str(max(1, int(config.timeout_seconds))),
        "--no-notify",
        "--json",
    ]
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
    except FileNotFoundError as exc:
        raise ExecutorError("comfy-cli executable was not found") from exc
    except OSError as exc:
        raise ExecutorError(f"could not start comfy-cli: {exc}") from exc

    assert process.stdout is not None
    assert process.stderr is not None
    stdout_queue: queue.Queue[object] = queue.Queue()
    stderr_queue: queue.Queue[object] = queue.Queue()
    stdout_thread = threading.Thread(
        target=_read_process_stream, args=(process.stdout, stdout_queue), daemon=True
    )
    stderr_thread = threading.Thread(
        target=_read_process_stream, args=(process.stderr, stderr_queue), daemon=True
    )
    stdout_thread.start()
    stderr_thread.start()

    events: list[dict[str, Any]] = []
    stderr_lines: list[str] = []
    stdout_done = False
    deadline = time.monotonic() + config.timeout_seconds + PROCESS_EXIT_GRACE_SECONDS
    provider_task_id: str | None = None
    parse_error: ExecutorError | None = None
    try:
        while not stdout_done or process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.wait()
                raise ExecutorError(
                    "comfy-cli exceeded its wall-clock timeout",
                    provider_task_id=provider_task_id,
                    status="unknown",
                )
            try:
                line = stdout_queue.get(timeout=min(0.2, remaining))
            except queue.Empty:
                continue
            if line is _STREAM_END:
                stdout_done = True
                continue
            if not isinstance(line, str) or not line.strip():
                continue
            try:
                event = json.loads(line.lstrip("\ufeff"))
            except json.JSONDecodeError:
                parse_error = ExecutorError(
                    "comfy-cli returned invalid JSON while execution status was uncertain",
                    provider_task_id=provider_task_id,
                    status="unknown",
                )
                # Keep draining the process so it can be terminated cleanly and
                # so a later queued event can still supply the provider ID.
                continue
            if not isinstance(event, dict):
                parse_error = ExecutorError(
                    "comfy-cli returned a non-object event while execution status was uncertain",
                    provider_task_id=provider_task_id,
                    status="unknown",
                )
                continue
            events.append(event)
            event_id = event.get("prompt_id")
            if isinstance(event_id, str) and event_id:
                provider_task_id = event_id
            _emit_progress(event, provider_task_id, emit)
        try:
            process.wait(timeout=max(0.0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.wait()
            raise ExecutorError(
                "comfy-cli exceeded its wall-clock timeout",
                provider_task_id=provider_task_id,
                status="unknown",
            ) from exc
    finally:
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        while True:
            try:
                line = stderr_queue.get_nowait()
            except queue.Empty:
                break
            if line is not _STREAM_END and isinstance(line, str):
                stderr_lines.append(line)

    if parse_error is not None:
        raise parse_error
    envelope = next((event for event in reversed(events) if event.get("type") == "envelope"), None)
    if envelope is None:
        detail = " ".join(stderr_lines).strip() or "missing terminal JSON envelope"
        raise ExecutorError(
            f"comfy-cli did not return a terminal result: {detail}",
            provider_task_id=provider_task_id,
            status="unknown",
        )
    prompt_id: str | None = (
        envelope.get("prompt_id")
        if isinstance(envelope.get("prompt_id"), str)
        else provider_task_id
    )
    data = envelope.get("data")
    if isinstance(data, dict) and isinstance(data.get("prompt_id"), str):
        prompt_id = data["prompt_id"]
    if isinstance(data, dict) and data.get("status") in {"timeout", "timed_out"}:
        raise ExecutorError(
            "comfy-cli workflow timed out", provider_task_id=prompt_id, status="unknown"
        )
    error = envelope.get("error")
    if envelope.get("ok") is not True:
        message = error.get("message") if isinstance(error, dict) else None
        code = str(error.get("code") or "") if isinstance(error, dict) else ""
        if "timeout" in code.lower() or "timed out" in str(message or "").lower():
            raise ExecutorError(
                str(message or "comfy-cli workflow timed out"),
                provider_task_id=prompt_id,
                status="unknown",
            )
        raise ExecutorError(
            str(message or "comfy-cli reported a provider failure"),
            provider_task_id=prompt_id,
            status="failed",
        )
    if process.returncode != 0:
        raise ExecutorError(
            f"comfy-cli exited with code {process.returncode} after submission",
            provider_task_id=prompt_id,
            status="unknown",
        )
    if not isinstance(data, dict) or data.get("status") != "completed":
        status = (
            "failed"
            if isinstance(data, dict) and data.get("status") in {"failed", "error"}
            else "unknown"
        )
        raise ExecutorError(
            "comfy-cli returned without a completed workflow",
            provider_task_id=prompt_id,
            status=status,
        )
    if not prompt_id:
        raise ExecutorError("comfy-cli result did not include prompt_id", status="unknown")
    if emit is not None:
        emit({"stage": "collection", "remote_finished": True, "provider_task_id": prompt_id})
    outputs = _collect_outputs(events, prompt_id)
    if not outputs:
        raise ExecutorError(
            f"comfy-cli prompt {prompt_id} completed without file output",
            provider_task_id=prompt_id,
            status="failed",
        )
    return CliResult(prompt_id, outputs, tuple(events))


def _download_view(
    base_url: str, reference: OutputRef, target: pathlib.Path, timeout: float
) -> None:
    query = urlencode(
        {
            "filename": reference.filename,
            "subfolder": reference.subfolder,
            "type": reference.file_type,
        }
    )
    request = Request(base_url.rstrip("/") + "/view?" + query, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response, target.open("wb") as stream:
            shutil.copyfileobj(response, stream)
    except (OSError, HTTPError, URLError) as exc:
        raise ExecutorError(f"Could not download Comfy output {reference.filename}: {exc}") from exc

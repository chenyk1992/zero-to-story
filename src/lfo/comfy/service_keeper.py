# ruff: noqa: RUF001
"""Keep an MCP-launched local Comfy service alive across Canvas adapters.

On Windows the MCP stdio client owns a process-tree job. Its launch session
must outlive individual adapters or closing that job also removes ComfyUI.
This host-side service holder never uploads or submits media.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .admission import state_directory
from .transport import (
    ExecutorError,
    RuntimeConfig,
    _connected,
    _endpoint,
    _model_environment,
    _owned_offline_session,
    _running,
    load_runtime_config,
)


def _record(path: Path, config: RuntimeConfig, status: str, **details: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({
        "pid": os.getpid(), "base_url": config.base_url, "status": status,
        "recorded_at": datetime.now(UTC).isoformat(),
        **details,
    }, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def keep_service(
    config: RuntimeConfig, status_path: Path, *,
    wait: Callable[[float], None] = time.sleep,
    info: dict[str, Any] | None = None, reservation: str | None = None,
) -> None:
    """Launch only a proven offline service and retain its owning MCP context.

    There is no automatic relaunch after a lost connection or stopped server.
    Existing independent servers are reused without acquiring their lifetime.
    """
    _record(status_path, config, "checking")
    try:
        if info is None:
            with _connected(config) as probe:
                observed = probe.call("server_info")
                if not isinstance(observed, dict):
                    raise ExecutorError("Comfy 服务状态无效")
                info = observed
                if _running(info, config):
                    _record(status_path, config, "reused")
                    return
        with _owned_offline_session(config, info, reservation=reservation) as owner:
            _record(status_path, config, "ready")
            while True:
                wait(60)
                try:
                    running = _running(owner.call("server_info"), config)
                except Exception as exc:
                    # An observation error is not proof the service stopped.
                    # Keep its owning context; never relaunch or deliberately
                    # remove a potentially active generation in this holder.
                    _record(status_path, config, "unknown", error=str(exc))
                    continue
                if not running:
                    _record(status_path, config, "stopped")
                    return
                _record(status_path, config, "ready")
    except Exception as exc:
        _record(status_path, config, "failed", error=str(exc))
        raise


def start_persistent_service(config: RuntimeConfig, info: dict[str, Any]) -> None:
    """Reserve a single detached Windows launcher and wait for its ready proof."""
    _endpoint(config.base_url)
    _model_environment(info, config)  # Fail before reserving if the install is incomplete.
    folder = state_directory()
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / "startup.json"
    reservation = uuid.uuid4().hex
    status_path = folder / f"service-keeper-{reservation}.json"
    configuration = asdict(config)
    for key in ("project_root", "model_venv"):
        if configuration[key] is not None:
            configuration[key] = str(configuration[key])
    payload = {
        "base_url": config.base_url, "workspace": info["workspace"]["path"],
        "reservation": reservation, "runtime_config": configuration,
        "info": info, "status_path": str(status_path),
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    try:
        with marker.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream)
    except FileExistsError as exc:
        raise ExecutorError("上次 ComfyUI 启动尚未核实；停止重复启动") from exc
    try:
        with (folder / f"service-keeper-{reservation}.log").open("ab") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "lfo.comfy.service_keeper", "--bootstrap", str(marker)],
                cwd=config.project_root, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                creationflags=(subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP),
            )
    except OSError as exc:
        # No child exists, so the matching unsubmitted reservation is safe to release.
        marker.unlink(missing_ok=True)
        raise ExecutorError("无法启动独立 Comfy 服务连接") from exc
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        if status_path.exists():
            value = json.loads(status_path.read_text(encoding="utf-8"))
            if value.get("base_url") != config.base_url:
                raise ExecutorError("常驻 Comfy 地址不匹配", status="unknown")
            if value.get("status") == "ready":
                return
            if value.get("status") in {"failed", "stopped", "unknown"}:
                raise ExecutorError(str(value.get("error") or "常驻 Comfy 启动失败"), status="unknown")
        if process.poll() is not None:
            raise ExecutorError("常驻 Comfy 启动进程退出；保留启动记录待核实", status="unknown")
        time.sleep(0.5)
    # Do not kill the launcher or release its reservation on an uncertain timeout.
    raise ExecutorError("常驻 Comfy 启动超时；保留原启动记录", status="unknown")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap", type=Path)
    args = parser.parse_args()
    if args.bootstrap is None:
        keep_service(load_runtime_config(), state_directory() / "service-keeper.json")
        return
    payload = json.loads(args.bootstrap.read_text(encoding="utf-8"))
    configuration = payload["runtime_config"]
    for key in ("project_root", "model_venv"):
        if configuration.get(key) is not None:
            configuration[key] = Path(configuration[key])
    keep_service(
        RuntimeConfig(**configuration), Path(payload["status_path"]),
        info=payload["info"], reservation=payload["reservation"],
    )


if __name__ == "__main__":
    main()

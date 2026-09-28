from __future__ import annotations

import json
from pathlib import Path

import pytest

from lfo.comfy import transport


class FakeSession:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def call(self, name, args=None, **_kwargs):
        self.calls.append((name, args))
        return self.replies.pop(0)


def info(*, running: bool, workspace: Path | None = None):
    return {
        "server": {"running": running, "url": "http://127.0.0.1:8188" if running else None},
        "workspace": {"path": str(workspace or Path("C:/ComfyUI"))},
        "config": {"default_launch_extras": "--use-sage-attention"},
    }


def test_online_session_reuses_existing_comfy(monkeypatch):
    first = FakeSession([info(running=True)])
    monkeypatch.setattr(transport, "_session", lambda *a, **k: first)
    with transport.ready_session(transport.RuntimeConfig()) as session:
        assert session is first
    assert first.calls == [("server_info", None)]


def test_offline_session_uses_existing_model_venv_and_launches_once(monkeypatch, tmp_path):
    from lfo.comfy import admission

    workspace = tmp_path / "desktop" / "ComfyUI"
    venv = workspace.parent / "standalone-env" / "Scripts"
    venv.mkdir(parents=True)
    (venv / "python.exe").write_bytes(b"python")
    first = FakeSession([info(running=False, workspace=workspace)])
    second = FakeSession([
        info(running=False, workspace=workspace), {"ok": True},
        info(running=True, workspace=workspace),
    ])
    sessions = iter([first, second])
    selected = []

    def session(_config, **kwargs):
        selected.append(kwargs.get("model_venv"))
        return next(sessions)

    monkeypatch.setattr(transport, "_session", session)
    monkeypatch.setattr(admission, "state_directory", lambda: tmp_path / "state")
    with transport.ready_session(transport.RuntimeConfig()) as active:
        assert active is second
    assert selected == [None, venv.parent]
    assert second.calls[1][0] == "launch_comfyui"
    assert "--use-sage-attention" in second.calls[1][1]["extra_args"]
    assert not (tmp_path / "state" / "startup.json").exists()


def test_failed_launch_keeps_marker_and_blocks_second_attempt(monkeypatch, tmp_path):
    from lfo.comfy import admission
    from lfo.comfy.mcp_client import McpCallError

    workspace = tmp_path / "ComfyUI"
    (workspace / ".venv" / "Scripts").mkdir(parents=True)
    (workspace / ".venv" / "Scripts" / "python.exe").write_bytes(b"python")
    first = FakeSession([info(running=False, workspace=workspace)])
    second = FakeSession([info(running=False, workspace=workspace)])

    def fail_launch(name, args=None, **_kwargs):
        if name == "launch_comfyui":
            raise McpCallError("timeout")
        return second.replies.pop(0)

    second.call = fail_launch
    sessions = iter([first, second, FakeSession([info(running=False, workspace=workspace)])])
    monkeypatch.setattr(transport, "_session", lambda *a, **k: next(sessions))
    monkeypatch.setattr(admission, "state_directory", lambda: tmp_path / "state")
    with pytest.raises(transport.ExecutorError, match="timeout"):
        with transport.ready_session(transport.RuntimeConfig()):
            pass
    assert json.loads((tmp_path / "state" / "startup.json").read_text())["base_url"] == "http://127.0.0.1:8188"
    with pytest.raises(transport.ExecutorError, match="重复启动"):
        with transport.ready_session(transport.RuntimeConfig()):
            pass


def test_non_loopback_target_is_rejected():
    with pytest.raises(transport.ExecutorError, match="回环"):
        transport.load_runtime_config(base_url="http://example.org:8188")
    with pytest.raises(transport.ExecutorError, match="端口"):
        transport.load_runtime_config(base_url="http://127.0.0.1:0")


def test_conflicting_local_targets_are_rejected(monkeypatch):
    monkeypatch.setenv("LFO_COMFY_MCP_URL", "http://127.0.0.1:8189")
    with pytest.raises(transport.ExecutorError, match="冲突"):
        transport.load_runtime_config(base_url="http://127.0.0.1:8188")

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
        value = self.replies.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def info(*, running: bool, workspace: Path | None = None):
    return {
        "server": {"running": running, "url": "http://127.0.0.1:8188" if running else None},
        "workspace": {"path": str(workspace or Path("C:/ComfyUI"))},
        "config": {"default_launch_extras": "--use-sage-attention"},
    }


def test_online_session_reuses_existing_comfy(monkeypatch):
    first = FakeSession([{"valid": True}])
    monkeypatch.setattr(transport, "_session", lambda *a, **k: first)
    with transport.ready_session(transport.RuntimeConfig()) as session:
        assert session.call("validate_workflow", {"workflow_path": "frozen.json"}) == {"valid": True}
    assert first.calls == [("validate_workflow", {"workflow_path": "frozen.json"})]


def test_offline_session_uses_existing_model_venv_and_launches_once(monkeypatch, tmp_path):
    from lfo.comfy import admission
    from lfo.comfy.mcp_client import McpCallError
    monkeypatch.setattr(transport, "_start_offline_session", transport._owned_offline_session)

    workspace = tmp_path / "desktop" / "ComfyUI"
    venv = workspace.parent / "standalone-env" / "Scripts"
    venv.mkdir(parents=True)
    (venv / "python.exe").write_bytes(b"python")
    first = FakeSession([McpCallError("offline"), info(running=False, workspace=workspace)])
    second = FakeSession([
        info(running=False, workspace=workspace), {"ok": True},
        info(running=True, workspace=workspace), {"valid": True},
    ])
    sessions = iter([first, second])
    selected = []

    def session(_config, **kwargs):
        selected.append(kwargs.get("model_venv"))
        return next(sessions)

    monkeypatch.setattr(transport, "_session", session)
    monkeypatch.setattr(admission, "state_directory", lambda: tmp_path / "state")
    with transport.ready_session(transport.RuntimeConfig()) as active:
        assert active.call("validate_workflow", {"workflow_path": "frozen.json"}) == {"valid": True}
    assert selected == [None, venv.parent]
    assert second.calls[1][0] == "launch_comfyui"
    assert "--use-sage-attention" in second.calls[1][1]["extra_args"]
    assert not (tmp_path / "state" / "startup.json").exists()


def test_failed_launch_keeps_marker_and_blocks_second_attempt(monkeypatch, tmp_path):
    from lfo.comfy import admission
    from lfo.comfy.mcp_client import McpCallError
    monkeypatch.setattr(transport, "_start_offline_session", transport._owned_offline_session)

    workspace = tmp_path / "ComfyUI"
    (workspace / ".venv" / "Scripts").mkdir(parents=True)
    (workspace / ".venv" / "Scripts" / "python.exe").write_bytes(b"python")
    first = FakeSession([McpCallError("offline"), info(running=False, workspace=workspace)])
    second = FakeSession([info(running=False, workspace=workspace)])

    def fail_launch(name, args=None, **_kwargs):
        if name == "launch_comfyui":
            raise McpCallError("timeout")
        return second.replies.pop(0)

    second.call = fail_launch
    sessions = iter([first, second, FakeSession([McpCallError("offline"), info(running=False, workspace=workspace)])])
    monkeypatch.setattr(transport, "_session", lambda *a, **k: next(sessions))
    monkeypatch.setattr(admission, "state_directory", lambda: tmp_path / "state")
    with pytest.raises(transport.ExecutorError, match="timeout"):
        with transport.ready_session(transport.RuntimeConfig()) as active:
            active.call("validate_workflow", {"workflow_path": "frozen.json"})
    assert json.loads((tmp_path / "state" / "startup.json").read_text())["base_url"] == "http://127.0.0.1:8188"
    with pytest.raises(transport.ExecutorError, match="重复启动"):
        with transport.ready_session(transport.RuntimeConfig()) as active:
            active.call("validate_workflow", {"workflow_path": "frozen.json"})


@pytest.mark.parametrize("name", ["run_workflow", "job", "fetch_outputs"])
def test_lost_submission_or_result_never_starts_or_retries(monkeypatch, name):
    from lfo.comfy.mcp_client import McpCallError
    first = FakeSession([McpCallError("lost reply")])
    monkeypatch.setattr(transport, "_session", lambda *a, **k: first)
    with pytest.raises(transport.ExecutorError, match="lost reply"):
        with transport.ready_session(transport.RuntimeConfig()) as active:
            active.call(name, {})
    assert first.calls == [(name, {})]


def test_online_operation_error_is_reported_without_retry_or_launch(monkeypatch):
    from lfo.comfy.mcp_client import McpCallError
    first = FakeSession([McpCallError("bad file"), info(running=True)])
    monkeypatch.setattr(transport, "_session", lambda *a, **k: first)
    with pytest.raises(transport.ExecutorError, match="bad file"):
        with transport.ready_session(transport.RuntimeConfig()) as active:
            active.call("upload_file", {})
    assert first.calls == [("upload_file", {}), ("server_info", None)]


def test_no_offline_recovery_for_any_operation_after_submission_attempt(monkeypatch):
    from lfo.comfy.mcp_client import McpCallError
    first = FakeSession([{"prompt_id": "original"}, McpCallError("lost")])
    monkeypatch.setattr(transport, "_session", lambda *a, **k: first)
    with pytest.raises(transport.ExecutorError, match="lost"):
        with transport.ready_session(transport.RuntimeConfig()) as active:
            active.call("run_workflow", {})
            active.call("search_models", {})
    assert first.calls == [("run_workflow", {}), ("search_models", {})]


def test_non_loopback_target_is_rejected():
    with pytest.raises(transport.ExecutorError, match="回环"):
        transport.load_runtime_config(base_url="http://example.org:8188")
    with pytest.raises(transport.ExecutorError, match="端口"):
        transport.load_runtime_config(base_url="http://127.0.0.1:0")


def test_conflicting_local_targets_are_rejected(monkeypatch):
    monkeypatch.setenv("LFO_COMFY_MCP_URL", "http://127.0.0.1:8189")
    with pytest.raises(transport.ExecutorError, match="冲突"):
        transport.load_runtime_config(base_url="http://127.0.0.1:8188")

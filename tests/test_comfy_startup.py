from urllib.error import URLError

import pytest

from lfo.comfy import transport


def test_online_preflight_does_not_launch(monkeypatch):
    monkeypatch.setattr(transport, "_fetch_object_info", lambda *a: {})
    launch = []
    monkeypatch.setattr(transport, "ensure_local_service", lambda *a: launch.append(1))
    transport.preflight_workflow({}, transport.RuntimeConfig())
    assert not launch


def test_offline_preflight_launches_once_then_validates(monkeypatch):
    calls = []

    def fetch(*args):
        calls.append("probe")
        if len(calls) == 1:
            raise transport.ExecutorError("offline") from URLError(ConnectionRefusedError())
        return {}

    monkeypatch.setattr(transport, "_fetch_object_info", fetch)
    monkeypatch.setattr(transport, "ensure_local_service", lambda *a: calls.append("launch"))
    transport.preflight_workflow({}, transport.RuntimeConfig())
    assert calls == ["probe", "launch", "probe"]


def test_bad_response_does_not_launch(monkeypatch):
    def fetch(*args):
        raise transport.ExecutorError("invalid json") from ValueError()

    monkeypatch.setattr(transport, "_fetch_object_info", fetch)
    monkeypatch.setattr(
        transport, "ensure_local_service", lambda *a: pytest.fail("must not launch")
    )
    with pytest.raises(transport.ExecutorError):
        transport.preflight_workflow({}, transport.RuntimeConfig())


def test_remote_service_cannot_launch_local():
    with pytest.raises(transport.ExecutorError, match="local"):
        transport.ensure_local_service(transport.RuntimeConfig(base_url="http://example.org:8188"))


@pytest.fixture
def startup(monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace

    folder = tmp_path / "state"
    monkeypatch.setenv("LFO_VIDEO_STATE", str(folder))
    monkeypatch.delenv("LFO_COMFY_VENV", raising=False)
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "wrong-canvas-env"))
    workspace = tmp_path / "install" / "ComfyUI"
    workspace.mkdir(parents=True)
    (workspace / "main.py").touch()
    venv = workspace.parent / "standalone-env"
    python = venv / ("Scripts/python.exe" if transport.os.name == "nt" else "bin/python")
    python.parent.mkdir(parents=True)
    python.touch()
    monkeypatch.setattr(
        transport.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "data": {
                        "workspace": {"path": str(workspace)},
                        "config": {"default_launch_extras": "--use-sage-attention"},
                    }
                }
            ),
        ),
    )
    monkeypatch.setattr(transport, "_port_open", lambda *a: False)
    launches = []
    process = SimpleNamespace(pid=123, poll=lambda: None)
    monkeypatch.setattr(
        transport.subprocess,
        "Popen",
        lambda command, **kwargs: launches.append((command, kwargs)) or process,
    )
    return folder, workspace, venv, launches, process


def offline(*args):
    raise transport.ExecutorError("offline") from URLError(ConnectionRefusedError())


def test_startup_uses_existing_model_runtime_and_clears_receipt(monkeypatch, startup):
    folder, workspace, venv, launches, process = startup
    calls = []

    def probe(*a):
        calls.append(1)
        if len(calls) == 1:
            offline()
        return {}

    monkeypatch.setattr(transport, "_fetch_object_info", probe)
    transport.ensure_local_service(transport.RuntimeConfig())
    assert len(launches) == 1
    command, kwargs = launches[0]
    assert command[1:5] == ["--workspace", str(workspace), "launch", "--"]
    assert "--use-sage-attention" in command
    assert command[command.index("--port") + 1] == "8188"
    assert kwargs["env"]["VIRTUAL_ENV"] == str(venv)
    assert not (folder / "startup.json").exists()


def test_start_timeout_keeps_receipt_and_blocks_duplicate(monkeypatch, startup):
    folder, _, _, launches, _ = startup
    monkeypatch.setattr(transport, "_fetch_object_info", offline)
    with pytest.raises(transport.ExecutorError, match="timed out"):
        transport.ensure_local_service(transport.RuntimeConfig(timeout_seconds=0))
    assert (folder / "startup.json").exists()
    with pytest.raises(transport.ExecutorError, match="Previous Comfy startup"):
        transport.ensure_local_service(transport.RuntimeConfig())
    assert len(launches) == 1


def test_known_startup_exit_is_reported(monkeypatch, startup):
    folder, _, _, launches, process = startup
    process.poll = lambda: 1
    monkeypatch.setattr(transport, "_fetch_object_info", offline)
    with pytest.raises(transport.ExecutorError, match="exited"):
        transport.ensure_local_service(transport.RuntimeConfig())
    assert len(launches) == 1
    assert not (folder / "startup.json").exists()


def test_unknown_generation_receipt_blocks_startup(monkeypatch, startup):

    folder, _, _, launches, _ = startup
    folder.mkdir()
    (folder / "submission.json").write_text("{}")
    monkeypatch.setattr(transport, "_fetch_object_info", offline)
    with pytest.raises(transport.ExecutorError, match="原 Comfy") as caught:
        transport.ensure_local_service(transport.RuntimeConfig())
    assert caught.value.status == "failed"  # This new request has never been submitted.
    assert not launches


def test_existing_listener_is_not_relaunched(monkeypatch, startup):
    _, _, _, launches, _ = startup
    monkeypatch.setattr(transport, "_fetch_object_info", offline)
    monkeypatch.setattr(transport, "_port_open", lambda *a: True)
    with pytest.raises(transport.ExecutorError, match="already listening"):
        transport.ensure_local_service(transport.RuntimeConfig())
    assert not launches

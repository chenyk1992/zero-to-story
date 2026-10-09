from __future__ import annotations

import json
from contextlib import contextmanager

import pytest

from lfo.comfy import service_keeper as keeper
from lfo.comfy.transport import RuntimeConfig


class Session:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def call(self, name):
        self.calls.append(name)
        result = next(self.replies)
        if isinstance(result, Exception):
            raise result
        return {"server": {"running": result, "url": "http://127.0.0.1:8188"}}


def test_owner_remains_open_after_start_until_server_stops(monkeypatch, tmp_path):
    probe, owner = Session([False]), Session([True, False])
    opened = []

    @contextmanager
    def connected(_config):
        yield probe

    @contextmanager
    def launch(_config, _info, **_kwargs):
        opened.append(True)
        try:
            yield owner
        finally:
            opened.pop()

    monkeypatch.setattr(keeper, "_connected", connected)
    monkeypatch.setattr(keeper, "_owned_offline_session", launch)
    status = tmp_path / "keeper.json"

    def wait(_seconds):
        assert opened == [True]
        assert json.loads(status.read_text())["status"] == "ready"

    keeper.keep_service(RuntimeConfig(), status, wait=wait)
    assert not opened
    assert json.loads(status.read_text())["status"] == "stopped"
    assert probe.calls == ["server_info"]
    assert owner.calls == ["server_info", "server_info"]


def test_online_service_not_launched_or_stopped(monkeypatch, tmp_path):
    probe = Session([True])

    @contextmanager
    def connected(_config):
        yield probe

    monkeypatch.setattr(keeper, "_connected", connected)
    monkeypatch.setattr(keeper, "_owned_offline_session", lambda *a: pytest.fail("relaunch"))
    status = tmp_path / "keeper.json"
    keeper.keep_service(RuntimeConfig(), status)
    assert json.loads(status.read_text())["status"] == "reused"


def test_observation_error_keeps_owner_open_without_relaunch(monkeypatch, tmp_path):
    @contextmanager
    def connected(_config):
        yield Session([False])

    launches = []

    @contextmanager
    def launch(_config, _info, **_kwargs):
        launches.append(True)
        yield Session([RuntimeError("lost connection"), False])

    monkeypatch.setattr(keeper, "_connected", connected)
    monkeypatch.setattr(keeper, "_owned_offline_session", launch)
    status = tmp_path / "keeper.json"
    observations = []
    keeper.keep_service(RuntimeConfig(), status, wait=lambda _: observations.append(json.loads(status.read_text())["status"]))
    assert len(launches) == 1
    assert observations == ["ready", "unknown"]
    assert json.loads(status.read_text())["status"] == "stopped"


def test_windows_adapter_uses_detached_holder_then_plain_connection(monkeypatch):
    from lfo.comfy import transport

    events = []

    @contextmanager
    def connected(_config):
        events.append("connection opened")
        try:
            yield Session([True])
        finally:
            events.append("connection closed")

    monkeypatch.setattr(keeper, "start_persistent_service", lambda *a: events.append("holder ready"))
    monkeypatch.setattr(transport, "_connected", connected)
    # This regression covers the installed Windows runtime, not a mocked OS.
    if keeper.os.name != "nt":
        pytest.skip("Windows service lifetime")
    with transport._start_offline_session(RuntimeConfig(), {}):
        events.append("adapter work")
    assert events == ["holder ready", "connection opened", "adapter work", "connection closed"]


def test_pending_start_reservation_blocks_duplicate_spawn(monkeypatch, tmp_path):
    monkeypatch.setattr(keeper, "state_directory", lambda: tmp_path)
    monkeypatch.setattr(keeper, "_model_environment", lambda *a: tmp_path)
    monkeypatch.setattr(keeper.subprocess, "Popen", lambda *a, **k: pytest.fail("duplicate spawn"))
    (tmp_path / "startup.json").write_text("{}")
    with pytest.raises(keeper.ExecutorError, match="重复启动"):
        keeper.start_persistent_service(RuntimeConfig(), {"workspace": {"path": str(tmp_path)}})


def test_detached_launch_and_timeout_keep_original_reservation(monkeypatch, tmp_path):
    from types import SimpleNamespace

    monkeypatch.setattr(keeper, "state_directory", lambda: tmp_path)
    monkeypatch.setattr(keeper, "_model_environment", lambda *a: tmp_path)
    clocks = iter([0, 241])
    monkeypatch.setattr(keeper.time, "monotonic", lambda: next(clocks))
    spawned = []

    def spawn(args, **kwargs):
        spawned.append((args, kwargs))
        return SimpleNamespace(poll=lambda: None)

    monkeypatch.setattr(keeper.subprocess, "Popen", spawn)
    with pytest.raises(keeper.ExecutorError, match="超时"):
        keeper.start_persistent_service(RuntimeConfig(), {"workspace": {"path": str(tmp_path)}})
    assert (tmp_path / "startup.json").exists()
    flags = spawned[0][1]["creationflags"]
    assert flags & keeper.subprocess.DETACHED_PROCESS
    assert flags & keeper.subprocess.CREATE_NEW_PROCESS_GROUP
    assert "--bootstrap" in spawned[0][0]

from __future__ import annotations

from pathlib import Path

import pytest

from lfo.comfy import transport
from lfo.comfy.mcp_client import McpCallError


class FakeSession:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def call(self, name, args=None, **_kwargs):
        self.calls.append((name, args))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class FakeGuard:
    def __init__(self):
        self.receipts = []
        self.ended = False

    def submitted(self, prompt_id=None):
        self.receipts.append(prompt_id)

    def finished(self):
        self.ended = True


def test_upload_uses_unique_copy_and_validates_receipt(tmp_path):
    source = tmp_path / "reference.png"
    source.write_bytes(b"frozen")

    class UploadSession:
        def call(self, name, args, **_kwargs):
            assert name == "upload_file" and args["overwrite"] is False
            staged = Path(args["paths"][0])
            assert staged.name != source.name and staged.read_bytes() == b"frozen"
            return {"uploads": [{"cloud_name": "remote.png", "subfolder": "refs", "type": "input"}]}

    assert transport.upload_input(source, UploadSession()) == "refs/remote.png"
    assert source.read_bytes() == b"frozen"
    failed = FakeSession([{"uploads": [{"cloud_name": "one", "type": "input"}, {"error": "partial"}]}])
    with pytest.raises(transport.ExecutorError, match="回执"):
        transport.upload_input(source, failed)


def test_preflight_rejects_bad_node_choice_or_workflow(tmp_path):
    graph = {"1": {"class_type": "Sampler", "inputs": {"mode": "bad"}}}
    session = FakeSession([{"name": "Sampler", "inputs": [{"name": "mode", "choices": ["good"]}]}])
    with pytest.raises(transport.ExecutorError, match="选项"):
        transport.preflight_workflow(graph, tmp_path / "workflow.json", session, inspect_nodes=True)
    assert [name for name, _ in session.calls] == ["nodes"]
    graph["1"]["inputs"]["mode"] = "good"
    session = FakeSession([{"name": "Sampler", "inputs": [{"name": "mode", "choices": ["good"]}]}, {"valid": False, "errors": ["bad"]}])
    with pytest.raises(transport.ExecutorError, match="未通过"):
        transport.preflight_workflow(graph, tmp_path / "workflow.json", session, inspect_nodes=True)


def test_normal_preflight_validates_once_without_enumerating_node_schemas(tmp_path):
    graph = {str(i): {"class_type": f"Node{i}", "inputs": {}} for i in range(20)}
    session = FakeSession([{"valid": True}])
    transport.preflight_workflow(graph, tmp_path / "workflow.json", session)
    assert [name for name, _ in session.calls] == ["validate_workflow"]


def test_normal_preflight_refusal_cannot_submit_or_leave_an_unknown_receipt(tmp_path):
    session = FakeSession([{"valid": False, "errors": ["model not installed"]}])
    with pytest.raises(transport.ExecutorError, match="未通过") as error:
        transport.preflight_workflow({"1": {"class_type": "Sampler", "inputs": {}}}, tmp_path / "workflow.json", session)
    assert error.value.status == "failed"
    assert [name for name, _ in session.calls] == ["validate_workflow"]


def test_submit_lost_reply_keeps_unknown_receipt(tmp_path):
    guard = FakeGuard()
    session = FakeSession([McpCallError("disconnected")])
    with pytest.raises(transport.ExecutorError) as caught:
        transport.run_workflow(tmp_path / "workflow.json", tmp_path, transport.RuntimeConfig(), session, guard=guard)
    assert caught.value.status == "unknown"
    assert guard.receipts == [None] and not guard.ended
    assert [name for name, _ in session.calls] == ["run_workflow"]


@pytest.mark.parametrize("reply", [{}, {"prompt_id": None}])
def test_submit_without_id_keeps_unknown_receipt(tmp_path, reply):
    guard = FakeGuard()
    with pytest.raises(transport.ExecutorError) as caught:
        transport.run_workflow(tmp_path / "workflow.json", tmp_path, transport.RuntimeConfig(), FakeSession([reply]), guard=guard)
    assert caught.value.status == "unknown" and guard.receipts == [None]


def test_job_disconnect_keeps_known_id_and_does_not_resubmit(tmp_path):
    guard = FakeGuard()
    session = FakeSession([{"prompt_id": "p1"}, McpCallError("disconnected")])
    with pytest.raises(transport.ExecutorError) as caught:
        transport.run_workflow(tmp_path / "workflow.json", tmp_path, transport.RuntimeConfig(), session, guard=guard)
    assert caught.value.status == "unknown" and caught.value.provider_task_id == "p1"
    assert guard.receipts == [None, "p1"] and not guard.ended
    assert [name for name, _ in session.calls] == ["run_workflow", "job"]


def test_wait_timeout_keeps_known_id_and_unknown_receipt(tmp_path, monkeypatch):
    guard = FakeGuard()
    session = FakeSession([{"prompt_id": "p1"}, {"prompt_id": "p1", "status": "running"}])
    clock = iter([0, 0, 2, 2])
    monkeypatch.setattr(transport.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(transport.time, "sleep", lambda _seconds: None)
    with pytest.raises(transport.ExecutorError, match="超时") as caught:
        transport.run_workflow(
            tmp_path / "workflow.json", tmp_path,
            transport.RuntimeConfig(timeout_seconds=1), session, guard=guard,
        )
    assert caught.value.status == "unknown" and caught.value.provider_task_id == "p1"
    assert guard.receipts == [None, "p1"] and not guard.ended


@pytest.mark.parametrize("status", ["error", "cancelled"])
def test_failed_terminal_releases_guard_with_evidence(tmp_path, status):
    guard = FakeGuard()
    session = FakeSession([{"prompt_id": "p1"}, {"prompt_id": "p1", "status": status, "error": "node failed"}])
    with pytest.raises(transport.ExecutorError) as caught:
        transport.run_workflow(tmp_path / "workflow.json", tmp_path, transport.RuntimeConfig(), session, guard=guard)
    assert caught.value.status == "failed" and guard.ended


@pytest.mark.parametrize("status", ["completed", "SUCCESS"])
def test_completed_job_fetches_only_files_in_run(tmp_path, status):
    guard = FakeGuard()
    events = []

    class Completed(FakeSession):
        def call(self, name, args=None, **kwargs):
            if name == "fetch_outputs":
                assert not any(event.get("stage") == "collection" for event in events)
                path = Path(args["out_dir"]) / "speech.flac"
                path.write_bytes(b"audio")
                return {"files": [{"path": str(path)}]}
            return super().call(name, args, **kwargs)

    session = Completed([{"prompt_id": "p1"}, {"prompt_id": "p1", "status": status}])
    result = transport.run_workflow(tmp_path / "workflow.json", tmp_path, transport.RuntimeConfig(), session, guard=guard, emit=events.append)
    assert result.provider_task_id == "p1" and Path(result.outputs[0].filename).read_bytes() == b"audio"
    assert guard.ended
    assert not any(event.get("stage") == "collection" for event in events)


@pytest.mark.parametrize("bad", ["outside", "duplicate"])
def test_fetch_rejects_escaped_or_duplicate_file(tmp_path, bad):
    guard = FakeGuard()

    class BadFetch(FakeSession):
        def call(self, name, args=None, **kwargs):
            if name == "fetch_outputs":
                path = (tmp_path / "outside.flac") if bad == "outside" else (Path(args["out_dir"]) / "a.flac")
                path.write_bytes(b"audio")
                files = [{"path": str(path)}]
                if bad == "duplicate":
                    files.append({"path": str(path)})
                return {"files": files}
            return super().call(name, args, **kwargs)

    session = BadFetch([{"prompt_id": "p1"}, {"prompt_id": "p1", "status": "completed"}])
    with pytest.raises(transport.ExecutorError, match="越界"):
        transport.run_workflow(tmp_path / "workflow.json", tmp_path, transport.RuntimeConfig(), session, guard=guard)
    assert guard.ended


@pytest.mark.parametrize("source_type", ["input", "output", "temp"])
def test_fetch_preserves_source_type_after_download(tmp_path, source_type):
    class Fetch(FakeSession):
        def call(self, name, args=None, **kwargs):
            if name == "fetch_outputs":
                path = Path(args["out_dir"]) / "video.mp4"
                path.write_bytes(b"video")
                return {"files": [{"path": str(path), "node_id": "34",
                                   "url": f"http://127.0.0.1:8188/view?filename=video.mp4&type={source_type}"}]}
            return super().call(name, args, **kwargs)

    session = Fetch([{"prompt_id": "p1"}, {"prompt_id": "p1", "status": "completed"}])
    result = transport.run_workflow(tmp_path / "workflow.json", tmp_path,
                                    transport.RuntimeConfig(), session, guard=FakeGuard())
    assert result.outputs[0].file_type == source_type
    assert result.outputs[0].node_id == "34"


@pytest.mark.parametrize("query", ["type=input&type=output", "type=unrecognized"])
def test_fetch_refuses_ambiguous_or_unknown_source_type(tmp_path, query):
    class Fetch(FakeSession):
        def call(self, name, args=None, **kwargs):
            if name == "fetch_outputs":
                path = Path(args["out_dir"]) / "video.mp4"
                path.write_bytes(b"video")
                return {"files": [{"path": str(path),
                                   "url": f"http://127.0.0.1:8188/view?filename=video.mp4&{query}"}]}
            return super().call(name, args, **kwargs)

    session = Fetch([{"prompt_id": "p1"}, {"prompt_id": "p1", "status": "completed"}])
    with pytest.raises(transport.ExecutorError, match="来源类型"):
        transport.run_workflow(tmp_path / "workflow.json", tmp_path,
                               transport.RuntimeConfig(), session, guard=FakeGuard())


def test_vdn_preflight_rejects_old_schema_instead_of_ignoring_auto_policy(tmp_path):
    graph = {"1": {"class_type": "ApplyVDNH3", "inputs": {
        "branch_weights": "auto", "retain_buffers": "auto",
    }}}
    session = FakeSession([{"name": "ApplyVDNH3", "inputs": [
        {"name": "branch_weights", "choices": ["auto", "stream", "cache_gpu"]},
    ]}])
    with pytest.raises(transport.ExecutorError, match="retain_buffers"):
        transport.preflight_workflow(graph, tmp_path / "workflow.json", session)
    assert [name for name, _ in session.calls] == ["nodes"]


def test_transport_records_observed_wait_and_fetch_without_claiming_sampling_time(tmp_path, monkeypatch):
    clock = iter([10.0, 12.0, 42.0, 47.0])
    monkeypatch.setattr(transport.time, "perf_counter", lambda: next(clock))

    class Completed(FakeSession):
        def call(self, name, args=None, **kwargs):
            if name == "fetch_outputs":
                path = Path(args["out_dir"]) / "video.mp4"
                path.write_bytes(b"video")
                return {"files": [{"path": str(path)}]}
            return super().call(name, args, **kwargs)

    session = Completed([{"prompt_id": "p1"}, {"prompt_id": "p1", "status": "completed"}])
    guard = FakeGuard()
    result = transport.run_workflow(tmp_path / "workflow.json", tmp_path,
                                    transport.RuntimeConfig(), session, guard=guard)
    assert result.timings_seconds == {"submit": 2.0, "provider_wait": 30.0, "fetch": 5.0}
    assert [name for name, _ in session.calls] == ["run_workflow", "job"]
    assert guard.receipts == [None, "p1"] and guard.ended


@pytest.mark.parametrize("key,value,choices", [
    ("branch_weights", "stream", None), ("branch_weights", "cache_gpu", []),
    ("retain_buffers", "on", None), ("retain_buffers", "off", []),
])
def test_vdn_preflight_requires_evidence_for_explicit_memory_policy(tmp_path, key, value, choices):
    graph = {"1": {"class_type": "ApplyVDNH3", "inputs": {key: value}}}
    session = FakeSession([{"name": "ApplyVDNH3", "inputs": [
        {"name": key, "choices": choices},
    ]}, {"valid": True}])
    with pytest.raises(transport.ExecutorError, match=key):
        transport.preflight_workflow(graph, tmp_path / "workflow.json", session)
    assert [name for name, _ in session.calls] == ["nodes"]

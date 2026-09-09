from __future__ import annotations

import io
import json
import subprocess
import sys

import pytest

from lfo.comfy.admission import VideoSubmissionGuard, inspect_submission, reconcile_submission
from lfo.comfy.cli import ComfyCliRunner
from lfo.comfy.exceptions import ComfyCliTimeoutError, LfoComfyError


def test_submission_guard_blocks_a_separate_process():
    script = (
        "from lfo.comfy.admission import VideoSubmissionGuard\n"
        "with VideoSubmissionGuard('http://127.0.0.1:8188'):\n"
        "    print('unexpected admission')\n"
    )
    with VideoSubmissionGuard("http://127.0.0.1:8188"):
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=10)
    assert result.returncode != 0
    assert b"unexpected admission" not in result.stdout
    assert b"LfoComfyError" in result.stderr


def test_hard_timeout_keeps_task_number_from_partial_stdout():
    def time_out(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            args[0], 1, output=b'{"type":"queued","prompt_id":"remote-early"}\n'
        )

    runner = ComfyCliRunner(process_runner=time_out)
    with pytest.raises(ComfyCliTimeoutError) as raised:
        runner.run_workflow({}, base_url="http://127.0.0.1:8188", timeout_seconds=1)
    assert raised.value.prompt_id == "remote-early"
    assert inspect_submission()["provider_task_id"] == "remote-early"


def test_other_entrypoint_cannot_submit_while_guard_is_held():
    calls = []
    runner = ComfyCliRunner(process_runner=lambda *args, **kwargs: calls.append(args))
    with VideoSubmissionGuard("http://127.0.0.1:8188"):
        with pytest.raises(LfoComfyError, match="串行"):
            runner.run_workflow({}, base_url="http://127.0.0.1:8188", timeout_seconds=1)
    assert calls == []


def test_lost_process_receipt_keeps_slot_unknown_until_remote_proof(monkeypatch):
    with VideoSubmissionGuard("http://127.0.0.1:8188", request_id="original") as guard:
        guard.submitted("remote-one")
    assert inspect_submission()["provider_task_id"] == "remote-one"
    with pytest.raises(LfoComfyError, match="核实"):
        with VideoSubmissionGuard("http://127.0.0.1:8188"):
            pytest.fail("unknown must block submission")
    with pytest.raises(ValueError, match="编号不匹配"):
        reconcile_submission("different")
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: io.StringIO(
            json.dumps({"remote-one": {"status": {"completed": True, "status_str": "success"}}})
        ),
    )
    assert reconcile_submission("original")["provider_task_id"] == "remote-one"
    assert inspect_submission() is None


def test_empty_history_is_not_cancellation(monkeypatch):
    with VideoSubmissionGuard("http://127.0.0.1:8188", request_id="original") as guard:
        guard.submitted("remote-one")
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: io.StringIO("{}"))
    with pytest.raises(ValueError, match="尚未证明"):
        reconcile_submission("original")
    assert inspect_submission() is not None


def test_no_remote_id_cannot_be_reconciled_by_guessing():
    with VideoSubmissionGuard("http://127.0.0.1:8188", request_id="original") as guard:
        guard.submitted()
    with pytest.raises(ValueError, match="没有远端编号"):
        reconcile_submission("original")
    assert inspect_submission() is not None


def test_known_finished_submission_allows_next_process():
    with VideoSubmissionGuard("http://127.0.0.1:8188") as guard:
        guard.submitted("remote-one")
        guard.finished()
    with VideoSubmissionGuard("http://127.0.0.1:8188") as next_guard:
        next_guard.submitted("remote-two")
        next_guard.finished()
    assert inspect_submission() is None

from __future__ import annotations

import json
import subprocess
import sys
from contextlib import contextmanager

import pytest

from lfo.comfy.admission import (
    VideoSubmissionGuard,
    inspect_submission,
    reconcile_submission,
    reconcile_submission_operator,
)
from lfo.comfy.exceptions import LfoComfyError


def fake_status(monkeypatch, value):
    from lfo.comfy import transport

    @contextmanager
    def session(_config):
        class Client:
            def call(self, name, args):
                assert name == "job" and args["action"] == "status"
                return value

        yield Client()

    monkeypatch.setattr(transport, "_session", session)
    monkeypatch.setattr(
        transport, "load_runtime_config", lambda **_kwargs: transport.RuntimeConfig()
    )


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


def test_admission_module_command_has_clean_stderr():
    result = subprocess.run(
        [sys.executable, "-m", "lfo.comfy.admission"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "null"
    assert "RuntimeWarning" not in result.stderr


def test_lost_process_receipt_keeps_slot_unknown_until_remote_proof(monkeypatch):
    with VideoSubmissionGuard("http://127.0.0.1:8188", request_id="original") as guard:
        guard.submitted("remote-one")
    assert inspect_submission()["provider_task_id"] == "remote-one"
    with pytest.raises(LfoComfyError, match="核实"):
        with VideoSubmissionGuard("http://127.0.0.1:8188"):
            pytest.fail("unknown must block submission")
    with pytest.raises(ValueError, match="编号不匹配"):
        reconcile_submission("different")
    fake_status(monkeypatch, {"prompt_id": "remote-one", "status": "completed"})
    assert reconcile_submission("original")["provider_task_id"] == "remote-one"
    assert inspect_submission() is None


def test_empty_history_is_not_cancellation(monkeypatch):
    with VideoSubmissionGuard("http://127.0.0.1:8188", request_id="original") as guard:
        guard.submitted("remote-one")
    fake_status(monkeypatch, {})
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


def test_operator_reconciliation_is_audited_and_clears_only_matching_receipt(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("LFO_VIDEO_STATE", str(tmp_path))
    with VideoSubmissionGuard("http://127.0.0.1:8188", request_id="request-a") as guard:
        guard.submitted("remote-a")

    result = reconcile_submission_operator(
        "request-a",
        "remote-a",
        "failed",
        "ComfyUI was restarted; the original job is no longer available.",
    )

    assert result["source"] == "operator_confirmation"
    assert result["remote_status"] == "failed"
    assert inspect_submission() is None
    audit_files = list((tmp_path / "reconciliations").glob("*.json"))
    assert len(audit_files) == 1
    audit = json.loads(audit_files[0].read_text(encoding="utf-8"))
    assert audit["request_id"] == "request-a"
    assert audit["provider_task_id"] == "remote-a"
    assert audit["terminal_status"] == "failed"
    assert audit["reason"] == "ComfyUI was restarted; the original job is no longer available."

    with VideoSubmissionGuard("http://127.0.0.1:8188", request_id="next"):
        pass


@pytest.mark.parametrize(
    ("request_id", "provider_task_id", "terminal_status", "reason"),
    [
        ("other", "remote-a", "failed", "confirmed"),
        ("request-a", "other-remote", "failed", "confirmed"),
        ("request-a", "remote-a", "succeeded", "confirmed"),
        ("request-a", "remote-a", "failed", "  "),
    ],
)
def test_operator_reconciliation_rejects_ambiguous_evidence(
    monkeypatch, tmp_path, request_id, provider_task_id, terminal_status, reason
):
    monkeypatch.setenv("LFO_VIDEO_STATE", str(tmp_path))
    with VideoSubmissionGuard("http://127.0.0.1:8188", request_id="request-a") as guard:
        guard.submitted("remote-a")

    with pytest.raises(ValueError):
        reconcile_submission_operator(request_id, provider_task_id, terminal_status, reason)

    assert inspect_submission()["request_id"] == "request-a"
    assert not list((tmp_path / "reconciliations").glob("*.json"))

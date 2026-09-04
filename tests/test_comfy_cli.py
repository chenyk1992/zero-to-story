from __future__ import annotations

import json
import pathlib
import subprocess

import pytest

from lfo.comfy.cli import ComfyCliRunner
from lfo.comfy.exceptions import ComfyCliTimeoutError, LfoComfyError


def _stream(*events: dict) -> str:
    return "\n".join(json.dumps(event) for event in events) + "\n"


def test_run_workflow_waits_and_parses_structured_output() -> None:
    captured: dict[str, object] = {}

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured["process_timeout"] = kwargs["timeout"]
        workflow_path = pathlib.Path(command[command.index("--workflow") + 1])
        captured["workflow"] = json.loads(workflow_path.read_text(encoding="utf-8"))
        stdout = _stream(
            {"schema": "event/1", "type": "queued", "prompt_id": "prompt-1"},
            {
                "schema": "event/1",
                "type": "executed",
                "prompt_id": "prompt-1",
                "outputs": [
                    {
                        "filename": "clip.mp4",
                        "subfolder": "lfo/run",
                        "type": "output",
                        "url": "http://127.0.0.1:8188/view?filename=clip.mp4",
                    }
                ],
            },
            {
                "schema": "envelope/1",
                "type": "envelope",
                "ok": True,
                "data": {
                    "status": "completed",
                    "prompt_id": "prompt-1",
                    "outputs": [],
                },
                "error": None,
            },
        )
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    result = ComfyCliRunner(process_runner=run).run_workflow(
        {"1": {"class_type": "SaveVideo", "inputs": {}}},
        base_url="http://127.0.0.1:8188",
        timeout_seconds=7_200,
    )

    command = captured["command"]
    assert isinstance(command, list)
    assert command[0] == "comfy"
    assert "--wait" in command
    assert command[command.index("--where") + 1] == "local"
    assert command[command.index("--host") + 1] == "127.0.0.1"
    assert command[command.index("--port") + 1] == "8188"
    assert command[command.index("--timeout") + 1] == "7200"
    assert command[-1] == "--json"
    assert captured["process_timeout"] == 7_500
    assert captured["workflow"] == {"1": {"class_type": "SaveVideo", "inputs": {}}}
    assert result.prompt_id == "prompt-1"
    assert result.outputs[0].filename == "clip.mp4"
    assert result.outputs[0].subfolder == "lfo/run"


def test_run_workflow_merges_only_executed_outputs_for_envelope_prompt() -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        stdout = _stream(
            {
                "schema": "event/1",
                "type": "executed",
                "prompt_id": "prompt-other",
                "outputs": [
                    {"filename": "other.mp4", "subfolder": "", "type": "output"}
                ],
            },
            {
                "schema": "event/1",
                "type": "executed",
                "prompt_id": "prompt-current",
                "outputs": [
                    {
                        "filename": "current.mp4",
                        "subfolder": "video",
                        "type": "output",
                    }
                ],
            },
            {
                "schema": "envelope/1",
                "type": "envelope",
                "ok": True,
                "data": {
                    "status": "completed",
                    "prompt_id": "prompt-current",
                    "outputs": [],
                },
                "error": None,
            },
        )
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    result = ComfyCliRunner(process_runner=run).run_workflow(
        {"1": {"class_type": "SaveVideo", "inputs": {}}},
        base_url="http://127.0.0.1:8188",
        timeout_seconds=120,
    )

    assert [(item.filename, item.subfolder) for item in result.outputs] == [
        ("current.mp4", "video")
    ]


def test_run_workflow_does_not_merge_executed_event_without_prompt_id() -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        stdout = _stream(
            {
                "schema": "event/1",
                "type": "executed",
                "outputs": [
                    {"filename": "orphan.mp4", "subfolder": "", "type": "output"}
                ],
            },
            {
                "schema": "envelope/1",
                "type": "envelope",
                "ok": True,
                "data": {
                    "status": "completed",
                    "prompt_id": "prompt-current",
                    "outputs": [
                        "http://127.0.0.1:8188/view?filename=current.mp4&type=output"
                    ],
                },
                "error": None,
            },
        )
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    result = ComfyCliRunner(process_runner=run).run_workflow(
        {"1": {"class_type": "SaveVideo", "inputs": {}}},
        base_url="http://127.0.0.1:8188",
        timeout_seconds=120,
    )

    assert [item.filename for item in result.outputs] == ["current.mp4"]


def test_run_workflow_can_recover_output_metadata_from_envelope_url() -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        stdout = _stream(
            {
                "schema": "envelope/1",
                "type": "envelope",
                "ok": True,
                "data": {
                    "status": "completed",
                    "prompt_id": "prompt-2",
                    "outputs": [
                        "http://localhost:8188/view?filename=clip.mp4&subfolder=video&type=output"
                    ],
                },
                "error": None,
            }
        )
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    result = ComfyCliRunner(process_runner=run).run_workflow(
        {"1": {"class_type": "SaveVideo", "inputs": {}}},
        base_url="localhost:8188",
        timeout_seconds=120,
    )

    assert result.outputs[0].filename == "clip.mp4"
    assert result.outputs[0].subfolder == "video"


def test_run_workflow_prefers_existing_local_path_from_envelope(tmp_path: pathlib.Path) -> None:
    output = tmp_path / "clip.mp4"
    output.write_bytes(b"video")

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        stdout = _stream(
            {
                "schema": "event/1",
                "type": "executed",
                "prompt_id": "prompt-local",
                "outputs": [
                    {"filename": "clip.mp4", "subfolder": "", "type": "output"}
                ],
            },
            {
                "schema": "envelope/1",
                "type": "envelope",
                "ok": True,
                "data": {
                    "status": "completed",
                    "prompt_id": "prompt-local",
                    "outputs": [str(output)],
                },
                "error": None,
            },
        )
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    result = ComfyCliRunner(process_runner=run).run_workflow(
        {"1": {"class_type": "SaveVideo", "inputs": {}}},
        base_url="http://127.0.0.1:8188",
        timeout_seconds=120,
    )

    assert result.outputs[0].file_type == "absolute"
    assert pathlib.Path(result.outputs[0].filename) == output.resolve()


def test_run_workflow_surfaces_cli_error_envelope() -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        stdout = _stream(
            {
                "schema": "envelope/1",
                "type": "envelope",
                "ok": False,
                "data": None,
                "error": {"code": "prompt_rejected", "message": "bad workflow"},
            }
        )
        return subprocess.CompletedProcess(command, 1, stdout=stdout, stderr="")

    with pytest.raises(LfoComfyError, match="prompt_rejected: bad workflow"):
        ComfyCliRunner(process_runner=run).run_workflow(
            {"1": {"class_type": "SaveVideo", "inputs": {}}},
            base_url="http://127.0.0.1:8188",
            timeout_seconds=120,
        )


def test_run_workflow_surfaces_timeout_error_envelope_as_timeout() -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        stdout = _stream(
            {
                "schema": "envelope/1",
                "type": "envelope",
                "ok": False,
                "error": {"code": "timeout", "message": "workflow timed out"},
                "data": {"prompt_id": "prompt-timeout"},
            }
        )
        return subprocess.CompletedProcess(command, 1, stdout=stdout, stderr="")

    with pytest.raises(
        ComfyCliTimeoutError, match="timeout: workflow timed out"
    ) as raised:
        ComfyCliRunner(process_runner=run).run_workflow(
            {"1": {"class_type": "SaveVideo", "inputs": {}}},
            base_url="http://127.0.0.1:8188",
            timeout_seconds=120,
        )

    assert raised.value.prompt_id == "prompt-timeout"


def test_run_workflow_rejects_partial_execution_warning() -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        stdout = _stream(
            {
                "schema": "envelope/1",
                "type": "envelope",
                "ok": True,
                "data": {
                    "status": "completed",
                    "prompt_id": "prompt-partial",
                    "outputs": [
                        "http://127.0.0.1:8188/view?filename=clip.mp4&type=output"
                    ],
                    "warnings": [{"code": "partial_execution"}],
                },
                "error": None,
            }
        )
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    with pytest.raises(LfoComfyError, match="partial-execution"):
        ComfyCliRunner(process_runner=run).run_workflow(
            {"1": {"class_type": "SaveVideo", "inputs": {}}},
            base_url="http://127.0.0.1:8188",
            timeout_seconds=120,
        )


def test_run_workflow_rejects_queued_validation_warnings() -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        stdout = _stream(
            {
                "schema": "event/1",
                "type": "queued",
                "prompt_id": "prompt-partial",
                "validation_warnings": [{"node_id": "save-2"}],
            },
            {
                "schema": "envelope/1",
                "type": "envelope",
                "ok": True,
                "data": {
                    "status": "completed",
                    "prompt_id": "prompt-partial",
                    "outputs": [
                        "http://127.0.0.1:8188/view?filename=clip.mp4&type=output"
                    ],
                },
                "error": None,
            },
        )
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    with pytest.raises(LfoComfyError, match="partially valid"):
        ComfyCliRunner(process_runner=run).run_workflow(
            {"1": {"class_type": "SaveVideo", "inputs": {}}},
            base_url="http://127.0.0.1:8188",
            timeout_seconds=120,
        )


def test_run_workflow_rejects_missing_terminal_envelope() -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command,
            1,
            stdout=_stream({"schema": "event/1", "type": "queued"}),
            stderr="process stopped",
        )

    with pytest.raises(LfoComfyError, match="terminal result"):
        ComfyCliRunner(process_runner=run).run_workflow(
            {"1": {"class_type": "SaveVideo", "inputs": {}}},
            base_url="http://127.0.0.1:8188",
            timeout_seconds=120,
        )


def test_run_workflow_enforces_hard_process_timeout() -> None:
    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    with pytest.raises(
        ComfyCliTimeoutError, match="hard wall-clock limit of 420 seconds"
    ):
        ComfyCliRunner(process_runner=run).run_workflow(
            {"1": {"class_type": "SaveVideo", "inputs": {}}},
            base_url="http://127.0.0.1:8188",
            timeout_seconds=120,
        )


@pytest.mark.parametrize("timeout_seconds", [0, -1, float("nan"), float("inf"), True])
def test_run_workflow_rejects_invalid_timeout(timeout_seconds: float) -> None:
    with pytest.raises(ValueError, match="positive finite"):
        ComfyCliRunner().run_workflow(
            {"1": {"class_type": "SaveVideo", "inputs": {}}},
            base_url="http://127.0.0.1:8188",
            timeout_seconds=timeout_seconds,
        )


@pytest.mark.parametrize("base_url", [
    "https://localhost:8188", "http://user:secret@localhost:8188",
    "http://localhost:8188/prefix?key=secret",
])
def test_cli_rejects_endpoint_details_it_cannot_forward(base_url):
    with pytest.raises(LfoComfyError) as error:
        ComfyCliRunner().run_workflow({}, base_url=base_url, timeout_seconds=30)
    assert "secret" not in str(error.value)

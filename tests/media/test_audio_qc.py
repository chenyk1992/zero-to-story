"""Tests for the narrow audio acceptance QC."""

from __future__ import annotations

from pathlib import Path

from lfo.media import audio_qc
from lfo.media.audio_qc import (
    AudioAcceptanceContract,
    AudioAcceptanceReadiness,
    AudioQualityQC,
)


def test_transcription_difference_requires_listening_instead_of_automatic_rejection():
    from lfo.media.audio_qc import AudioQCReport, AudioQCRuleResult

    report = AudioQCReport(passed=False, results=[AudioQCRuleResult("speech_event:line-1", False)])
    assert report.requires_review
    assert not report.ready_for_acceptance


def _contract() -> AudioAcceptanceContract:
    return (
        AudioAcceptanceContract.from_dict(
            {
                "schema": "lfo.audio_acceptance.v1",
                "require_audio": True,
                "speech_events": [
                    {
                        "event_id": "D001",
                        "speaker_id": "S1",
                        "text": "你好。",
                        "start_ms": 1000,
                        "end_ms": 1800,
                    }
                ],
            }
        )
        or AudioAcceptanceContract()
    )


def test_audio_stream_and_speech_evidence_pass(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fixture")
    monkeypatch.setattr(audio_qc, "probe", lambda _path: {"has_audio": True})
    report = AudioQualityQC().check(
        path,
        _contract(),
        analysis={
            "status": "PASS",
            "peak_db": -3.0,
            "mean_db": -20.0,
            "speech_events": [
                {
                    "event_id": "D001",
                    "speaker_id": "S1",
                    "text": "你好。",
                    "start_ms": 1010,
                    "end_ms": 1790,
                }
            ],
        },
    )
    assert report.passed
    assert not report.inconclusive


def test_audio_speech_mismatch_fails(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fixture")
    monkeypatch.setattr(audio_qc, "probe", lambda _path: {"has_audio": True})
    report = AudioQualityQC().check(
        path,
        _contract(),
        analysis={
            "status": "PASS",
            "speech_events": [
                {
                    "event_id": "D001",
                    "speaker_id": "S2",
                    "text": "再见。",
                    "start_ms": 2000,
                    "end_ms": 2500,
                }
            ],
        },
    )
    assert not report.passed
    assert any(result.rule == "speech_event:D001" for result in report.failures)


def test_inconclusive_analysis_is_reviewable_not_an_automatic_failure(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fixture")
    monkeypatch.setattr(audio_qc, "probe", lambda _path: {"has_audio": True})
    report = AudioQualityQC().check(
        path,
        _contract(),
        analysis={"status": "INCONCLUSIVE", "peak_db": 0.0, "mean_db": -100.0},
    )
    assert report.passed
    assert report.inconclusive


def test_inconclusive_report_exposes_review_readiness_without_rejection(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fixture")
    monkeypatch.setattr(audio_qc, "probe", lambda _path: {"has_audio": True})
    report = AudioQualityQC().check(
        path,
        _contract(),
        analysis={"status": "INCONCLUSIVE"},
    )

    assert report.passed
    assert report.acceptance_readiness is AudioAcceptanceReadiness.REVIEW_REQUIRED
    assert not report.ready_for_acceptance
    assert report.requires_review


def test_missing_required_audio_fails(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fixture")
    monkeypatch.setattr(audio_qc, "probe", lambda _path: {"has_audio": False})
    report = AudioQualityQC().check(path, _contract())
    assert not report.passed
    assert report.failures[0].rule == "audio_stream"


def test_probe_failure_is_a_structured_qc_failure(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "missing.mp4"
    monkeypatch.setattr(audio_qc, "probe", lambda _path: (_ for _ in ()).throw(ValueError("bad media")))

    report = AudioQualityQC().check(path, _contract())

    assert not report.passed
    assert report.failures[0].rule == "audio_artifact"
    assert "bad media" in report.failures[0].message


def test_explicit_null_signal_threshold_is_disabled(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"video")
    monkeypatch.setattr(audio_qc, "probe", lambda _path: {"has_audio": True})
    contract = AudioAcceptanceContract.from_dict(
        {
            "require_audio": True,
            "max_peak_db": None,
            "min_mean_db": None,
        }
    )
    assert contract is not None
    report = AudioQualityQC().check(
        path,
        contract,
        analysis={"peak_db": 0.0, "mean_db": -100.0},
    )
    assert report.passed


def test_overlap_allowed_by_current_event(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"video")
    monkeypatch.setattr(audio_qc, "probe", lambda _path: {"has_audio": True})
    contract = AudioAcceptanceContract.from_dict(
        {
            "require_audio": True,
            "speech_events": [
                {
                    "event_id": "D001",
                    "speaker_id": "S1",
                    "text": "甲",
                    "start_ms": 0,
                    "end_ms": 500,
                },
                {
                    "event_id": "D002",
                    "speaker_id": "S2",
                    "text": "乙",
                    "start_ms": 400,
                    "end_ms": 800,
                    "allow_overlap": True,
                },
            ],
        }
    )
    assert contract is not None
    report = AudioQualityQC().check(
        path,
        contract,
        analysis={
            "speech_events": [
                {
                    "event_id": "D001",
                    "speaker_id": "S1",
                    "text": "甲",
                    "start_ms": 0,
                    "end_ms": 500,
                },
                {
                    "event_id": "D002",
                    "speaker_id": "S2",
                    "text": "乙",
                    "start_ms": 400,
                    "end_ms": 800,
                },
            ]
        },
    )
    assert not any(result.rule == "speech_overlap" for result in report.failures)


def test_missing_speech_events_are_inconclusive_instead_of_an_automatic_failure(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fixture")
    monkeypatch.setattr(audio_qc, "probe", lambda _path: {"has_audio": True})

    report = AudioQualityQC().check(path, _contract(), analysis={"status": "PASS"})

    assert report.passed
    assert report.inconclusive
    assert report.requires_review


def test_untrusted_audio_values_do_not_coerce_to_truthy_or_infinite_settings(
    monkeypatch, tmp_path: Path
) -> None:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fixture")
    monkeypatch.setattr(audio_qc, "probe", lambda _path: {"has_audio": "false"})
    contract = AudioAcceptanceContract.from_dict(
        {
            "require_audio": False,
            "max_peak_db": float("inf"),
            "speech_events": [
                {
                    "event_id": "D001",
                    "speaker_id": "S1",
                    "text": "甲",
                    "start_ms": 0,
                    "end_ms": 500,
                    "allow_overlap": "false",
                }
            ],
        }
    )

    assert contract is not None
    assert contract.max_peak_db == -0.1
    assert contract.speech_events[0].allow_overlap is False
    report = AudioQualityQC().check(path, contract)
    assert report.passed
    assert report.inconclusive
    assert report.requires_review


def test_nonfinite_or_oversized_analysis_metrics_require_review(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"fixture")
    monkeypatch.setattr(audio_qc, "probe", lambda _path: {"has_audio": True})

    report = AudioQualityQC().check(
        path,
        _contract(),
        analysis={"status": "PASS", "peak_db": float("nan"), "mean_db": 10**1000},
    )

    assert report.passed
    assert report.inconclusive
    assert report.requires_review
    assert {result.rule for result in report.results} >= {"peak_headroom", "speech_energy"}

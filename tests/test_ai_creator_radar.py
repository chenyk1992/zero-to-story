from __future__ import annotations

import copy
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / ".agents/skills/ai-creator-radar/scripts/radar.py"
spec = importlib.util.spec_from_file_location("ai_creator_radar", MODULE_PATH)
assert spec and spec.loader
radar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(radar)
BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def observation(hour: float, views: int | None = 100, *, status: str = "ok") -> dict:
    return {"schema_version": 1, "source_id": "bili-watch", "platform": "bilibili", "method": "file",
            "observed_at": radar.iso(BASE + timedelta(hours=hour)), "status": status,
            "items": [{"id": "BV-test", "kind": "video", "title": "AI task", "url": "https://www.bilibili.com/video/BV-test",
                       "rank": None, "metrics": {"views": views, "likes": None}}] if status == "ok" else []}


def first(snapshots: list[dict], hour: float, **kwargs) -> dict:
    return radar.analyze(snapshots, now=BASE + timedelta(hours=hour), **kwargs)["items"][0]


def test_normalize_keeps_missing_zero_and_heat_distinct() -> None:
    videos = radar.normalize("bilibili-popular", {"code": 0, "data": {"list": [
        {"bvid": "BV-test", "title": "test", "stat": {"view": 0, "like": 0}}
    ]}})
    assert videos[0]["metrics"]["views"] == 0
    assert videos[0]["metrics"]["comments"] is None
    topics = radar.normalize("bilibili-hot", {"code": 0, "list": [
        {"keyword": "ＡＩ 编程", "show_name": "AI 编程", "pos": 1, "heat_score": 123}
    ]})
    assert topics[0]["metrics"] == {"hotness": 123}
    assert topics[0]["id"] == radar.topic_id("ai编程")


def test_single_snapshot_never_claims_growth_or_probability() -> None:
    row = first([observation(0, 100000)], 0)
    assert row["signal"] == "INSUFFICIENT_HISTORY"
    assert row["per_hour"] is None
    assert row["forecast_probability"] is None


def test_unequal_intervals_use_rates_not_raw_deltas() -> None:
    row = first([observation(0, 100), observation(1, 200), observation(3, 500)], 3)
    assert row["signal"] == "ACCELERATING_OBSERVED"
    assert row["previous_per_hour"] == 100
    assert row["per_hour"] == 150
    # A larger raw delta over a longer interval is not necessarily acceleration.
    assert first([observation(0, 100), observation(1, 300), observation(3, 600)], 3)["signal"] == "RISING"


def test_counter_decrease_is_correction_but_heat_can_cool() -> None:
    assert first([observation(0, 200), observation(1, 100)], 1)["signal"] == "COUNTER_CORRECTION"
    data = [observation(0), observation(1)]
    data[0]["items"][0]["metrics"] = {"hotness": 200}
    data[1]["items"][0]["metrics"] = {"hotness": 100}
    assert first(data, 1)["signal"] == "COOLING"


def test_latest_failure_and_disappearance_do_not_reuse_old_success() -> None:
    assert first([observation(0), observation(1, status="blocked")], 1)["signal"] == "SOURCE_UNAVAILABLE"
    other = observation(1)
    other["items"][0]["id"] = "other-video"
    assert first([observation(0), other], 1)["signal"] == "NOT_IN_LATEST_SAMPLE"
    assert first([observation(0)], 8)["signal"] == "STALE"


def test_cached_source_time_and_close_samples_do_not_inflate_evidence() -> None:
    cached = [observation(0), observation(1), observation(2)]
    for row in cached:
        row["source_updated_at"] = radar.iso(BASE)
    assert first(cached, 2)["observations"] == 1
    close = [observation(0), observation(0.1), observation(0.2)]
    assert first(close, 0.2)["signal"] == "INSUFFICIENT_HISTORY"
    rows = [observation(0), observation(1), observation(1.1)]
    assert first(rows, 1.1)["signal"] == "WAIT_FOR_SPACED_SAMPLE"
    assert first([observation(0), observation(20)], 20)["signal"] == "GAP_TOO_LONG"


def test_source_scopes_and_platform_metrics_cannot_be_silently_mixed() -> None:
    changed = observation(1)
    changed["query"] = "different query"
    with pytest.raises(ValueError, match="scope"):
        first([observation(0), changed], 1)
    second = observation(1)
    second.update(source_id="douyin-watch", platform="douyin")
    rows = radar.analyze([observation(0), second], now=BASE + timedelta(hours=1))["items"]
    assert len(rows) == 2
    assert all(row["signal"] == "INSUFFICIENT_HISTORY" for row in rows)


def test_identical_values_without_source_update_do_not_assert_a_real_plateau() -> None:
    row = first([observation(0), observation(1), observation(2)], 2)
    assert row["signal"] == "UNCHANGED_OR_CACHED"
    assert row["freshness_basis"] == "observation_time_only"
    assert row["warnings"] and row["forecast_probability"] is None
    row = first([observation(0, None), observation(1, None)], 1)
    assert row["signal"] == "INSUFFICIENT_HISTORY"


@pytest.mark.parametrize("value", ["1.2万", -1, float("nan"), float("inf"), True])
def test_rejects_inexact_or_invalid_metrics(value) -> None:
    data = observation(0)
    data["items"][0]["metrics"]["views"] = value
    with pytest.raises(ValueError):
        radar.validate_snapshot(data, now=BASE)


def test_rejects_future_naive_dates_duplicate_identity_and_access_tokens() -> None:
    with pytest.raises(ValueError, match="future"):
        radar.validate_snapshot(observation(1), now=BASE)
    data = observation(0)
    data["observed_at"] = "2026-01-01T00:00:00"
    with pytest.raises(ValueError, match="timezone"):
        radar.validate_snapshot(data, now=BASE)
    data = observation(0)
    data["items"].append(copy.deepcopy(data["items"][0]))
    with pytest.raises(ValueError, match="duplicate"):
        radar.validate_snapshot(data, now=BASE)
    data = observation(0)
    data["items"][0]["url"] += "?xsec_token=secret"
    with pytest.raises(ValueError, match="url"):
        radar.validate_snapshot(data, now=BASE)


def test_append_only_snapshots_preserve_original_bytes(tmp_path: Path) -> None:
    original = observation(0)
    before = copy.deepcopy(original)
    one = radar.save_snapshot(tmp_path, original, b'{"code":0}')
    two = radar.save_snapshot(tmp_path, original, b'{"code":0}')
    assert one != two
    assert original == before
    loaded = json.loads(one.read_text(encoding="utf-8"))
    assert (tmp_path / loaded["raw_file"]).read_bytes() == b'{"code":0}'
    assert loaded["raw_sha256"] == radar.hashlib.sha256(b'{"code":0}').hexdigest()


def test_empty_200_is_not_success_and_has_no_retry(monkeypatch) -> None:
    calls = []

    class EmptyResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, _):
            return b""

    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            return EmptyResponse()

    monkeypatch.setattr(radar, "build_opener", lambda *_: Opener())
    result, raw = radar.fetch("douyin-hot")
    assert result["status"] == "empty"
    assert result["items"] == [] and raw == b""
    assert len(calls) == 1


def browser_capture(platform: str = "xiaohongshu") -> dict:
    item_id = "6ad76021000000002701e41c" if platform == "xiaohongshu" else "7697792998502976777"
    prefix = "https://www.xiaohongshu.com/explore/" if platform == "xiaohongshu" else "https://www.douyin.com/video/"
    return {"capture_version": 1, "platform": platform, "query": "AI编程", "sort": "最多点赞",
            "sample_scope": "一周内，有限可见样本", "observed_at": radar.iso(BASE), "status": "ok",
            "source_url": "https://www.xiaohongshu.com/search_result" if platform == "xiaohongshu" else "https://www.douyin.com/search/AI",
            "records": [{"id": item_id, "kind": "note" if platform == "xiaohongshu" else "video",
                         "url": prefix + item_id, "title": "AI task", "author": "example",
                         "likes_display": "1.2万", "published_display": "昨天"}]}


@pytest.mark.parametrize("platform", ["douyin", "xiaohongshu"])
def test_browser_counts_dates_and_deduplication_preserve_evidence_limits(platform) -> None:
    capture = browser_capture(platform)
    capture["records"].append(copy.deepcopy(capture["records"][0]))
    result = radar.normalize_browser_capture(capture, "browser-example")
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["metrics"]["likes"] is None
    assert item["metrics"]["views"] is None
    assert item["published_at"] is None and item["rank"] is None
    capture["records"][0]["likes_display"] = "0"
    assert radar.normalize_browser_capture(capture, "browser-example")["items"][0]["metrics"]["likes"] == 0
    capture["records"][0]["likes_display"] = "1,234"
    assert radar.normalize_browser_capture(capture, "browser-example")["items"][0]["metrics"]["likes"] == 1234


def test_browser_import_rejects_wrong_identity_private_fields_and_failed_reuse() -> None:
    capture = browser_capture()
    capture["records"][0]["url"] += "?xsec_token=secret"
    with pytest.raises(ValueError, match="canonical"):
        radar.normalize_browser_capture(capture, "browser-example")
    capture = browser_capture()
    capture["cookies"] = "not-research-data"
    with pytest.raises(ValueError, match="unknown capture"):
        radar.normalize_browser_capture(capture, "browser-example")
    capture = browser_capture()
    capture["status"] = "blocked"
    with pytest.raises(ValueError, match="cannot reuse"):
        radar.normalize_browser_capture(capture, "browser-example")
    capture["records"] = []
    result = radar.normalize_browser_capture(capture, "browser-example")
    assert result["status"] == "blocked" and result["items"] == []


def test_browser_cli_saves_real_input_bytes_and_has_no_network(tmp_path: Path, monkeypatch) -> None:
    def forbidden_network(*_args, **_kwargs):
        pytest.fail("browser import must not make HTTP requests")

    monkeypatch.setattr(radar, "build_opener", forbidden_network)
    payload = json.dumps(browser_capture(), ensure_ascii=False).encode("utf-8")
    input_path = tmp_path / "capture.json"
    input_path.write_bytes(payload)
    store = tmp_path / "research"
    assert radar.main(["browser-import", "--input", str(input_path), "--source-id", "browser-example", "--store", str(store)]) == 0
    saved = json.loads(next((store / "snapshots").glob("*.json")).read_text(encoding="utf-8"))
    assert (store / saved["raw_file"]).read_bytes() == payload
    assert saved["raw_sha256"] == radar.hashlib.sha256(payload).hexdigest()
    assert radar.analyze([saved], now=BASE)["items"][0]["signal"] == "INSUFFICIENT_HISTORY"

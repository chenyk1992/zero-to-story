"""Bounded free public reads, explicit local snapshots and descriptive trend signals."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import unicodedata
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ENDPOINTS = {
    "bilibili-hot": ("bilibili", "https://s.search.bilibili.com/main/hotword?limit=30"),
    "bilibili-popular": ("bilibili", "https://api.bilibili.com/x/web-interface/popular?pn=1&ps=20"),
    "douyin-hot": (
        "douyin",
        "https://www.douyin.com/aweme/v1/web/hot/search/list/"
        "?device_platform=webapp&aid=6383&channel=channel_pc_web&detail_list=1",
    ),
}
METRICS = {"hotness", "views", "likes", "comments", "shares", "saves", "followers_gained"}
CUMULATIVE = METRICS - {"hotness"}
STATUSES = {"ok", "empty", "blocked", "unavailable", "invalid_response"}
MAX_BYTES = 2 * 1024 * 1024


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be ISO 8601 with timezone")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def number(value: Any) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("metrics must be finite nonnegative numbers or null; rounded display counts stay null")
    return value


def parse_json(body: bytes) -> Any:
    def reject(value: str) -> None:
        raise ValueError(f"invalid JSON numeric literal: {value}")
    return json.loads(body.decode("utf-8-sig"), parse_constant=reject)


def valid_url(value: str) -> bool:
    parsed = urlsplit(value)
    sensitive = {"xsec_token", "access_token", "access-token", "token", "mstoken", "cookie", "signature", "api_key"}
    return (parsed.scheme in {"http", "https"} and bool(parsed.hostname) and not parsed.username
            and not parsed.password and not any(key.casefold() in sensitive for key, _ in parse_qsl(parsed.query)))


def validate_snapshot(data: dict, *, now: datetime | None = None) -> dict:
    now = now or utc_now()
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    allowed = {"schema_version", "source_id", "platform", "method", "observed_at", "source_updated_at",
               "source_url", "query", "sort", "sample_scope", "status", "items", "diagnostic", "raw_sha256", "raw_file"}
    if set(data) - allowed:
        raise ValueError("unknown snapshot fields; do not import credentials or arbitrary provider payloads")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", data.get("source_id", "")):
        raise ValueError("source_id must be a stable lowercase identifier")
    if data.get("platform") not in {"douyin", "bilibili", "xiaohongshu", "other"}:
        raise ValueError("unsupported platform")
    if data.get("method") not in {"public_web", "browser", "file"}:
        raise ValueError("method must describe the actual acquisition")
    observed = timestamp(data.get("observed_at"))
    if observed > now + timedelta(seconds=60):
        raise ValueError("future observations are not evidence")
    if data.get("source_updated_at") is not None and timestamp(data["source_updated_at"]) > observed:
        raise ValueError("source_updated_at cannot be later than observed_at")
    if data.get("source_url") is not None and not valid_url(data["source_url"]):
        raise ValueError("source_url must be http(s) without credentials")
    if data.get("status") not in STATUSES or not isinstance(data.get("items"), list):
        raise ValueError("invalid status/items")
    if data["status"] != "ok" and data["items"]:
        raise ValueError("failed/empty sources must not contain successful items")
    if data["status"] == "ok" and not data["items"]:
        raise ValueError("an empty source must not be marked ok")
    seen = set()
    for item in data["items"]:
        if not isinstance(item, dict) or set(item) - {"id", "kind", "title", "url", "author", "published_at", "rank", "metrics"}:
            raise ValueError("invalid item fields")
        for key in ("id", "title", "url"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ValueError(f"item {key} must be nonempty")
        if item.get("kind") not in {"topic", "video", "note"} or not valid_url(item["url"]):
            raise ValueError("invalid item kind/url")
        identity = (item["kind"], item["id"])
        if identity in seen:
            raise ValueError("duplicate item identity in one snapshot")
        seen.add(identity)
        if item.get("published_at") is not None:
            if timestamp(item["published_at"]) > observed:
                raise ValueError("published_at cannot be later than observation")
        rank = item.get("rank")
        if rank is not None and (type(rank) is not int or rank < 1):
            raise ValueError("rank must be a positive integer or null")
        metrics = item.get("metrics")
        if not isinstance(metrics, dict) or set(metrics) - METRICS:
            raise ValueError("unsupported metrics")
        for value in metrics.values():
            number(value)
    return data


def topic_id(title: str) -> str:
    normalized = "".join(unicodedata.normalize("NFKC", title).casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]


def normalize_browser_capture(capture: dict, source_id: str) -> dict:
    """Normalize visible DOM evidence; retain display strings in the saved raw capture."""
    if not isinstance(capture, dict) or capture.get("capture_version") != 1:
        raise ValueError("capture_version must be 1")
    allowed_capture = {"capture_version", "platform", "query", "sort", "sample_scope", "observed_at",
                       "source_url", "status", "diagnostic", "page_title", "limitations", "records",
                       "scope_metadata_correction"}
    if set(capture) - allowed_capture:
        raise ValueError("unknown capture fields; do not import credentials or hidden state")
    platform = capture.get("platform")
    if platform not in {"douyin", "xiaohongshu"}:
        raise ValueError("browser capture platform must be douyin or xiaohongshu")
    for key in ("query", "sort", "sample_scope", "observed_at", "source_url"):
        if not isinstance(capture.get(key), str) or not capture[key].strip():
            raise ValueError(f"browser capture requires {key}")
    expected_host = "www.douyin.com" if platform == "douyin" else "www.xiaohongshu.com"
    if urlsplit(capture["source_url"]).hostname != expected_host:
        raise ValueError("capture source hostname differs from platform")
    records = capture.get("records")
    if not isinstance(records, list) or len(records) > 40:
        raise ValueError("capture records must be a bounded list (at most 40)")
    if capture.get("status") not in {"ok", "empty", "blocked"}:
        raise ValueError("invalid browser capture status")
    if capture["status"] != "ok" and records:
        raise ValueError("blocked/empty captures cannot reuse successful records")
    items = []
    seen = set()
    for record in records:
        allowed_record = {"id", "kind", "url", "title", "author", "likes_display", "published_display",
                          "duration_display", "identity_source"}
        if not isinstance(record, dict) or set(record) - allowed_record:
            raise ValueError("unknown record fields; only rendered research fields may be imported")
        item_id = record.get("id")
        pattern = r"\d{15,22}" if platform == "douyin" else r"[a-f0-9]{24}"
        if not isinstance(item_id, str) or not re.fullmatch(pattern, item_id):
            raise ValueError("content ID missing from rendered DOM; do not invent one")
        kind = "video" if platform == "douyin" else "note"
        url = ("https://www.douyin.com/video/" if platform == "douyin" else "https://www.xiaohongshu.com/explore/") + item_id
        if record.get("kind") != kind or record.get("url") != url:
            raise ValueError("item kind/canonical URL must match its actual platform ID")
        if item_id in seen:
            continue
        seen.add(item_id)
        display = record.get("likes_display")
        # Preserve 1.2万/9.0w in raw evidence; never invent an exact 12000/90000.
        likes = int(display.replace(",", "")) if isinstance(display, str) and re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)", display.strip()) else None
        items.append({"id": item_id, "kind": kind, "title": record.get("title"), "url": url,
                      "author": record.get("author"), "published_at": None, "rank": None,
                      "metrics": {"likes": likes, "views": None, "comments": None, "saves": None, "shares": None}})
    data = {"schema_version": 1, "source_id": source_id, "platform": platform, "method": "browser",
            "observed_at": capture["observed_at"], "source_updated_at": None,
            "source_url": capture["source_url"], "query": capture["query"], "sort": capture["sort"],
            "sample_scope": capture["sample_scope"], "status": capture["status"], "items": items}
    if capture.get("diagnostic"):
        data["diagnostic"] = capture["diagnostic"]
    return validate_snapshot(data)


def normalize(source: str, payload: dict) -> list[dict]:
    """Provider field names are not interchangeable across heat, views and likes."""
    if not isinstance(payload, dict):
        raise ValueError("provider JSON must be an object")
    if source.startswith("bilibili"):
        if payload.get("code") != 0:
            raise ValueError(f"provider business code {payload.get('code')!r}")
        records = payload.get("list") if source == "bilibili-hot" else (payload.get("data") or {}).get("list")
    else:
        if payload.get("status_code") != 0:
            raise ValueError(f"provider business code {payload.get('status_code')!r}")
        records = (payload.get("data") or {}).get("word_list")
    if not isinstance(records, list):
        raise ValueError("provider item list missing")
    items = []
    for entry in records:
        if source == "bilibili-hot":
            title = entry.get("show_name") or entry["keyword"]
            key = entry["keyword"]
            items.append({"id": topic_id(key), "kind": "topic", "title": title,
                          "url": "https://search.bilibili.com/all?keyword=" + quote(key),
                          "rank": entry.get("pos"), "metrics": {"hotness": number(entry.get("heat_score"))}})
        elif source == "bilibili-popular":
            stats = entry.get("stat") or {}
            published = entry.get("pubdate")
            items.append({"id": entry["bvid"], "kind": "video", "title": entry["title"],
                          "url": "https://www.bilibili.com/video/" + entry["bvid"],
                          "author": (entry.get("owner") or {}).get("name"),
                          "published_at": iso(datetime.fromtimestamp(published, timezone.utc)) if published else None,
                          "rank": None,
                          "metrics": {target: number(stats.get(field)) for field, target in
                                      [("view", "views"), ("like", "likes"), ("reply", "comments"),
                                       ("share", "shares"), ("favorite", "saves")]}})
        elif source == "douyin-hot":
            title = entry["word"]
            items.append({"id": topic_id(title), "kind": "topic", "title": title,
                          "url": "https://www.douyin.com/search/" + quote(title),
                          "rank": entry.get("position"), "metrics": {"hotness": number(entry.get("hot_value"))}})
        else:
            raise ValueError("unknown source")
    return items


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(source: str) -> tuple[dict, bytes]:
    platform, url = ENDPOINTS[source]
    result = {"schema_version": 1, "source_id": source, "platform": platform, "method": "public_web",
              "observed_at": iso(utc_now()), "source_updated_at": None, "source_url": url,
              "sample_scope": "one public list; no login, signatures, pagination or retries",
              "status": "unavailable", "items": []}
    raw = b""
    try:
        req = Request(url, headers={"User-Agent": "zero-to-story-research/1.0", "Accept": "application/json"})
        with build_opener(NoRedirect()).open(req, timeout=15) as response:
            raw = response.read(MAX_BYTES + 1)
        if not raw.strip():
            result.update(status="empty", diagnostic="empty HTTP response; no usable evidence, no retry")
        elif len(raw) > MAX_BYTES:
            result.update(status="invalid_response", diagnostic="response exceeds 2 MiB limit")
        else:
            try:
                payload = parse_json(raw)
                code = payload.get("code", payload.get("status_code")) if isinstance(payload, dict) else None
                if code in {-352, -412, 401, 403, 412, 429}:
                    result.update(status="blocked", diagnostic=f"provider business code {code}; no retry")
                    return result, raw
                items = normalize(source, payload)
                result.update(items=items, status="ok" if items else "empty")
                validate_snapshot(result)
            except (ValueError, KeyError, TypeError, AttributeError, UnicodeError) as error:
                result.update(items=[], status="invalid_response", diagnostic=str(error)[:250])
    except HTTPError as error:
        result.update(status="blocked" if error.code in {401, 403, 412, 429} else "unavailable",
                      diagnostic=f"HTTP {error.code}; no retry or alternate identity")
    except (URLError, TimeoutError, OSError) as error:
        result.update(diagnostic=f"{type(error).__name__}; request failed, no retry")
    result["observed_at"] = iso(utc_now())
    return result, raw


def save_snapshot(store: Path, data: dict, raw: bytes | None = None) -> Path:
    validate_snapshot(data)
    folder = store / "snapshots"
    folder.mkdir(parents=True, exist_ok=True)
    stem = timestamp(data["observed_at"]).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:10]
    data = dict(data)
    if raw is not None:
        raw_folder = store / "raw"
        raw_folder.mkdir(parents=True, exist_ok=True)
        raw_path = raw_folder / (stem + ".body")
        with raw_path.open("xb") as handle:
            handle.write(raw)
        data.update(raw_file="raw/" + raw_path.name, raw_sha256=hashlib.sha256(raw).hexdigest())
    path = folder / (stem + ".json")
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
    return path


def analyze(snapshots: list[dict], *, now: datetime | None = None, window_hours: float = 72,
            max_age_hours: float = 6, min_gap_minutes: float = 30, max_gap_hours: float = 12) -> dict:
    """Descriptive rate changes only. No probability, fitted model or cross-platform sum."""
    now = now or utc_now()
    if any(not math.isfinite(value) or value <= 0 for value in
           (window_hours, max_age_hours, min_gap_minutes, max_gap_hours)):
        raise ValueError("time windows and gaps must be positive finite numbers")
    latest: dict[str, dict] = {}
    scopes: dict[str, tuple] = {}
    histories: dict[tuple, list] = defaultdict(list)
    for snapshot in sorted(snapshots, key=lambda value: timestamp(value["observed_at"])):
        validate_snapshot(snapshot, now=now)
        observed = timestamp(snapshot["observed_at"])
        if observed > now:
            continue
        source = snapshot["source_id"]
        scope = tuple(snapshot.get(key) for key in ("platform", "method", "query", "sort", "sample_scope"))
        if source in scopes and scopes[source] != scope:
            raise ValueError("source_id reused for different platform/query/sort/sample scope")
        scopes[source] = scope
        latest[source] = snapshot
        if snapshot["status"] != "ok" or observed < now - timedelta(hours=window_hours):
            continue
        for item in snapshot["items"]:
            key = (source, snapshot["platform"], item["kind"], item["id"])
            measured = timestamp(snapshot.get("source_updated_at") or snapshot["observed_at"])
            histories[key].append((measured, item))
    results = []
    for (source, platform, kind, item_id), history in histories.items():
        # Keep adequately spaced observations; repeated cached source timestamps are one sample.
        samples = []
        for measured, item in sorted(history, key=lambda row: row[0]):
            if not samples or (measured - samples[-1][0]).total_seconds() >= min_gap_minutes * 60:
                samples.append((measured, item))
        current = latest[source]
        present = {(item["kind"], item["id"]) for item in current["items"]}
        last_time, last_item = history[-1]
        row = {"source_id": source, "platform": platform, "kind": kind, "id": item_id,
               "title": last_item["title"], "url": last_item["url"], "observations": len(samples),
               "last_observed_at": iso(last_time), "signal": "INSUFFICIENT_HISTORY",
               "metric": None, "delta": None, "per_hour": None, "previous_per_hour": None,
               "rank_improvement": None, "forecast_probability": None}
        row["freshness_basis"] = "source_updated_at" if current.get("source_updated_at") else "observation_time_only"
        row["warnings"] = [] if current.get("source_updated_at") else ["upstream update time unknown; collection time does not prove fresh data"]
        latest_time = timestamp(current.get("source_updated_at") or current["observed_at"])
        if current["status"] != "ok":
            row["signal"] = "SOURCE_UNAVAILABLE"
        elif (kind, item_id) not in present:
            row["signal"] = "NOT_IN_LATEST_SAMPLE"
        elif (now - latest_time).total_seconds() > max_age_hours * 3600:
            row["signal"] = "STALE"
        elif len(samples) >= 2:
            # If the newest sample is too close, do not compute a rate from obsolete measurements.
            end_time, end = samples[-1]
            if last_time != end_time:
                row["signal"] = "WAIT_FOR_SPACED_SAMPLE"
            else:
                prev_time, prev = samples[-2]
                hours = (end_time - prev_time).total_seconds() / 3600
                if hours > max_gap_hours:
                    row["signal"] = "GAP_TOO_LONG"
                else:
                    metrics = end["metrics"]
                    for metric in ("views", "hotness", "likes", "saves", "comments", "shares"):
                        value, previous = metrics.get(metric), prev["metrics"].get(metric)
                        if value is not None and previous is not None:
                            delta = value - previous
                            row.update(metric=metric, delta=delta, per_hour=round(delta / hours, 4))
                            if delta < 0 and metric in CUMULATIVE:
                                row.update(signal="COUNTER_CORRECTION", per_hour=None)
                            else:
                                row["signal"] = "RISING" if delta > 0 else "COOLING" if delta < 0 else "FLAT"
                                if len(samples) >= 3:
                                    older_time, older = samples[-3]
                                    old_value = older["metrics"].get(metric)
                                    old_hours = (prev_time - older_time).total_seconds() / 3600
                                    if old_value is not None and old_hours <= max_gap_hours:
                                        old_delta = previous - old_value
                                        if old_delta >= 0 or metric not in CUMULATIVE:
                                            old_rate = old_delta / old_hours
                                            row["previous_per_hour"] = round(old_rate, 4)
                                            if old_rate > 0 and delta / hours > old_rate:
                                                row["signal"] = "ACCELERATING_OBSERVED"
                            break
                    if end.get("rank") is not None and prev.get("rank") is not None:
                        row["rank_improvement"] = prev["rank"] - end["rank"]
                        if row["metric"] is None:
                            row["signal"] = "RANK_UP" if row["rank_improvement"] > 0 else "RANK_DOWN" if row["rank_improvement"] < 0 else "FLAT"
                    if (row["metric"] is not None or end.get("rank") is not None) and end["metrics"] == prev["metrics"] and end.get("rank") == prev.get("rank"):
                        row["signal"] = "UNCHANGED_OR_CACHED"
                        row["warnings"].append("same observed metrics/rank; cannot distinguish a plateau from cached data")
        results.append(row)
    return {"as_of": iso(now), "window_hours": window_hours,
            "interpretation": "observed changes only; not a virality forecast or a cross-platform ranking",
            "sources": [{"source_id": source, "status": value["status"], "observed_at": value["observed_at"],
                         "diagnostic": value.get("diagnostic")} for source, value in sorted(latest.items())],
            "items": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("collect", help="one bounded GET per chosen source; no login/retries")
    collect.add_argument("--source", action="append", choices=sorted(ENDPOINTS))
    collect.add_argument("--store", type=Path, required=True)
    ingest = commands.add_parser("import", help="validate a deliberately normalized browser/file observation")
    ingest.add_argument("--input", type=Path, required=True)
    ingest.add_argument("--store", type=Path, required=True)
    browser = commands.add_parser("browser-import", help="normalize a read-only rendered DOM capture; no cookies or network")
    browser.add_argument("--input", type=Path, required=True)
    browser.add_argument("--source-id", required=True)
    browser.add_argument("--store", type=Path, required=True)
    report = commands.add_parser("analyze", help="offline descriptive changes in local snapshots")
    report.add_argument("--store", type=Path, required=True)
    report.add_argument("--output", type=Path)
    report.add_argument("--keyword", action="append", default=[])
    report.add_argument("--window-hours", type=float, default=72)
    report.add_argument("--max-age-hours", type=float, default=6)
    report.add_argument("--min-gap-minutes", type=float, default=30)
    report.add_argument("--max-gap-hours", type=float, default=12)
    args = parser.parse_args(argv)
    try:
        if args.command == "collect":
            outcomes = []
            for source in dict.fromkeys(args.source or ["bilibili-hot"]):
                data, raw = fetch(source)
                path = save_snapshot(args.store, data, raw)
                outcomes.append({"source_id": source, "status": data["status"], "items": len(data["items"]),
                                 "snapshot": str(path.resolve()), "diagnostic": data.get("diagnostic")})
            print(json.dumps(outcomes, ensure_ascii=False, indent=2))
            return 0 if all(row["status"] == "ok" for row in outcomes) else 2
        if args.command == "browser-import":
            raw = args.input.read_bytes()
            capture = parse_json(raw)
            data = normalize_browser_capture(capture, args.source_id)
            path = save_snapshot(args.store, data, raw)
            print(json.dumps({"source_id": args.source_id, "status": data["status"], "items": len(data["items"]),
                              "snapshot": str(path.resolve())}, ensure_ascii=False))
            return 0 if data["status"] == "ok" else 2
        if args.command == "import":
            data = parse_json(args.input.read_bytes())
            # Imported evidence cannot assert a saved raw payload that this command did not verify.
            if any(key in data for key in ("raw_file", "raw_sha256")):
                raise ValueError("import raw_file/raw_sha256 are reserved for collector output")
            path = save_snapshot(args.store, data)
            print(str(path.resolve()))
            return 0
        options = {key: getattr(args, key) for key in ("window_hours", "max_age_hours", "min_gap_minutes", "max_gap_hours")}
        if any(not math.isfinite(value) or value <= 0 for value in options.values()):
            raise ValueError("time windows and gaps must be positive finite numbers")
        paths = sorted((args.store / "snapshots").glob("*.json"))
        result = analyze([parse_json(path.read_bytes()) for path in paths], **options)
        if args.keyword:
            result["items"] = [item for item in result["items"] if any(word.casefold() in item["title"].casefold() for word in args.keyword)]
        text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(text + "\n")
        else:
            print(text)
        return 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

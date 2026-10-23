#!/usr/bin/env python3
"""Adapters for the free / legal hotspot data sources.

Every adapter returns a flat list of records with the SAME shape, so the
scoring layer never needs to know where a record came from:

    {
      "platform": "douyin" | "bilibili" | "youtube",
      "kind":     "keyword" | "video",
      "rank":     int,              # 1-based position in the source list
      "keyword":  str,              # for kind=keyword: the trending term
      "title":    str,              # for kind=video:   the video title
      "heat":     int | None,       # source-provided heat/rank value
      "url":      str | None,
      "category": str | None,       # B站 tname / YouTube channel
      "stat":     {view,like,coin,favorite,comment},   # best effort
      "published": str | None,      # ISO date when available
      "extra":    {...}             # anything source-specific
    }

Design rules (see SOURCES.md):
  * Only public, read-only endpoints. No login state, no write endpoints.
  * Every adapter implements probe(); collect.py probes first and falls back
    through the degradation chain, recording WHICH source actually answered.
  * Field extraction is tolerant (several possible key names) because upstream
    renames fields; the contract fingerprint in collect.py is what detects a
    real schema change.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _get_json(url: str, headers: dict | None = None, timeout: int = 25) -> Any:
    hdr = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        hdr.update(headers)
    req = urllib.request.Request(url, headers=hdr)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _get_text(url: str, headers: dict | None = None, timeout: int = 30) -> str:
    hdr = {"User-Agent": UA}
    if headers:
        hdr.update(headers)
    req = urllib.request.Request(url, headers=hdr)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _first(item: dict, keys: Iterable[str]) -> Any:
    for k in keys:
        v = item.get(k)
        if v not in (None, "", [], {}):
            return v
    return None


def _schema_keys(items: Iterable[Any]) -> list[str]:
    """Field-name set of a response = UNION of the keys of all its items.

    Using only items[0] is unstable on rotating lists. Measured 2026-10-23:
    B站 `popular` returns 20 items where `attribute_v3` is present on 19 of
    them, so whichever item happened to be first decided whether the field
    was in the fingerprint - the contract then reported CHANGED on every
    other run. A union is stable: it only changes when upstream really adds
    or removes a field for good.
    """
    keys: set[str] = set()
    for it in items:
        if isinstance(it, dict):
            keys.update(it.keys())
    return sorted(keys)


def _as_int(value: Any) -> int | None:
    """Parse an int from a number or a Chinese-formatted magnitude string.

    Sources report heat as 9475000, "947.5w", "9.5万", "1.2M views" ... so the
    magnitude suffix has to be honoured or every heat value is off by 10^4.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        s = value.replace(",", "").strip()
        m = re.search(r"[\d.]+", s)
        if not m:
            return None
        try:
            num = float(m.group(0))
        except ValueError:
            return None
        low = s.lower()
        if "亿" in s:
            num *= 1e8
        elif "万" in s or "w" in low:
            num *= 1e4
        elif "k" in low:
            num *= 1e3
        elif "m" in low:
            num *= 1e6
        return int(num)
    return None


def _iso_date(epoch: Any) -> str | None:
    if not isinstance(epoch, (int, float)) or epoch <= 0:
        return None
    import datetime as _dt
    return _dt.datetime.fromtimestamp(epoch, _dt.timezone.utc).date().isoformat()


# --------------------------------------------------------------------------
# base
# --------------------------------------------------------------------------

class Adapter:
    name = "base"
    platform = "base"

    def probe(self) -> tuple[bool, str]:
        """Return (ok, note). Must not raise."""
        raise NotImplementedError

    def fetch(self) -> list[dict]:
        raise NotImplementedError


# --------------------------------------------------------------------------
# 60s API  (MIT, vikiboss/60s)  -- cross-platform hot lists
# --------------------------------------------------------------------------

SIXTY_BASE = "https://60s-api.viki.moe/v2"

SIXTY_ENDPOINTS = {
    "douyin": ("/douyin", "keyword"),
    "rednote": ("/rednote", "keyword"),
    "quark": ("/quark", "keyword"),
    "ai-news": ("/ai-news", "keyword"),
}


class SixtyAdapter(Adapter):
    name = "sixty"
    platform = "multi"

    def probe(self) -> tuple[bool, str]:
        try:
            j = _get_json(f"{SIXTY_BASE}/douyin", timeout=20)
            ok = j.get("code") == 200 and isinstance(j.get("data"), list)
            n = len(j.get("data") or []) if isinstance(j.get("data"), list) else 0
            return ok, f"douyin {n} 条"
        except urllib.error.HTTPError as exc:
            return False, f"HTTP {exc.code}"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)[:80]

    def fetch(self) -> list[dict]:
        out: list[dict] = []
        self.endpoint_status: dict[str, dict] = {}
        self.endpoint_fingerprints: dict[str, dict] = {}
        for key, (path, _kind) in SIXTY_ENDPOINTS.items():
            j = None
            for attempt in range(3):
                try:
                    j = _get_json(f"{SIXTY_BASE}{path}", timeout=20)
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code == 429 and attempt < 2:
                        # Public instance rate limits; back off and retry.
                        time.sleep(3 * (attempt + 1))
                        continue
                    # Rate limits and upstream outages MUST be visible, not swallowed.
                    self.endpoint_status[key] = {"ok": False, "error": f"HTTP {exc.code}"}
                    break
                except Exception as exc:  # noqa: BLE001
                    self.endpoint_status[key] = {"ok": False, "error": str(exc)[:100]}
                    break
            if j is None:
                continue
            if j.get("code") != 200:
                self.endpoint_status[key] = {"ok": False, "error": f"code={j.get('code')}"}
                continue
            self.endpoint_status[key] = {"ok": True}
            data = j.get("data")
            if isinstance(data, dict):
                data = (
                    data.get("list")
                    or data.get("items")
                    or data.get("news")
                    or data.get("data")
                    or []
                )
            if not isinstance(data, list):
                self.endpoint_status[key] = {"ok": False, "error": "data 不是数组"}
                continue
            self.endpoint_fingerprints[key] = _schema_keys(data)
            for rank, item in enumerate(data, start=1):
                if not isinstance(item, dict):
                    continue
                title = _first(item, ("word", "title", "name", "query", "keyword"))
                if not title:
                    continue
                heat = _as_int(
                    _first(item, ("hot_value", "hotValue", "heat", "hot", "value",
                                  "hot_score", "index", "score"))
                )
                out.append(
                    {
                        "platform": key,
                        "kind": "keyword",
                        "rank": rank,
                        "keyword": str(title),
                        "title": None,
                        "heat": heat,
                        "url": _first(item, ("url", "raw_url", "link", "share_url")),
                        "category": _first(item, ("category", "type", "tname")),
                        "stat": {},
                        "published": None,
                        "extra": {},
                    }
                )
        return out


# --------------------------------------------------------------------------
# Bilibili official public web API  (no auth, no key)
# --------------------------------------------------------------------------

BILI_API = "https://api.bilibili.com/x/web-interface"
BILI_HEADERS = {"Referer": "https://www.bilibili.com/", "Origin": "https://www.bilibili.com"}

# Bilibili's public endpoints answer a burst of requests without a buvid
# cookie and then start replying 412 Precondition Failed. Measured
# 2026-10-23: the first ~15 search requests succeed, the next one is 412 and
# keeps failing for minutes. Fetching a buvid3/buvid4 pair from the public
# fingerprint endpoint and sending it back keeps a daily collection run alive.
_BILI_COOKIE: dict[str, str] = {}


def _bili_cookie_path() -> Path:
    """Where the buvid cookie is kept between runs."""
    try:
        from _common import default_data_root

        root = default_data_root()
    except Exception:  # noqa: BLE001
        root = Path.home() / ".cache" / "hot-collect"
    return root / "cookies" / "bilibili.txt"


def _bili_headers(extra: dict | None = None) -> dict:
    hdr = dict(BILI_HEADERS)
    if extra:
        hdr.update(extra)
    cookie = _BILI_COOKIE.get("cookie")
    if cookie:
        hdr["Cookie"] = cookie
    return hdr


def bili_cookie() -> str:
    """The buvid3/buvid4 cookie, persisted so it stays the SAME visitor.

    Measured 2026-10-23: Bilibili search results are bucketed per visitor.
    The same query three times with one cookie returned the IDENTICAL 20
    results (intersection 20 / union 20), while a brand new cookie returned
    a different slice (intersection 16 / union 24). A fresh cookie on every
    run therefore makes the collected values irreproducible and unusable as
    a time series - so the cookie is written to the data root and reused.
    """
    if _BILI_COOKIE.get("cookie"):
        return _BILI_COOKIE["cookie"]
    path = _bili_cookie_path()
    try:
        if path.exists():
            saved = path.read_text(encoding="utf-8").strip()
            if saved:
                _BILI_COOKIE["cookie"] = saved
                return saved
    except Exception:  # noqa: BLE001
        pass
    try:
        j = _get_json("https://api.bilibili.com/x/frontend/finger/spi")
        data = j.get("data") or {}
        parts = []
        if data.get("b_3"):
            parts.append(f"buvid3={data['b_3']}")
        if data.get("b_4"):
            parts.append(f"buvid4={data['b_4']}")
        if parts:
            cookie = "; ".join(parts)
            _BILI_COOKIE["cookie"] = cookie
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(cookie, encoding="utf-8")
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass
    return _BILI_COOKIE.get("cookie", "")


def _get_json_retry(url: str, headers: dict | None = None, attempts: int = 3) -> Any:
    """_get_json with backoff on 412 / 429 - the two codes Bilibili uses to
    push a client away. A failed attempt must not kill the whole endpoint."""
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return _get_json(url, headers=headers)
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code not in (412, 429):
                raise
            bili_cookie()  # refresh the cookie, then wait out the block
            time.sleep(4.0 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            time.sleep(2.0)
    if last_exc:
        raise last_exc
    return None


class BiliAdapter(Adapter):
    name = "bilibili"
    platform = "bilibili"

    # rid 0 = 全站榜; 额外分区按需追加（分区名取自返回项的 tname，不硬编码）
    EXTRA_RIDS = ["36"]

    def _fetch_list(self, url: str) -> list[dict]:
        j = _get_json(url, headers=BILI_HEADERS)
        if j.get("code") != 0:
            return []
        data = j.get("data") or {}
        items = data.get("list") if isinstance(data, dict) else None
        return items if isinstance(items, list) else []

    def probe(self) -> tuple[bool, str]:
        # Probe both endpoints: one being rate-limited must not lose the other.
        for label, url in (
            ("全站榜", f"{BILI_API}/ranking/v2?rid=0&type=all"),
            ("热门", f"{BILI_API}/popular?ps=5&pn=1"),
        ):
            try:
                items = self._fetch_list(url)
            except urllib.error.HTTPError as exc:
                last = f"HTTP {exc.code}"
                continue
            except Exception as exc:  # noqa: BLE001
                last = str(exc)[:80]
                continue
            if items:
                s = items[0].get("stat") or {}
                return True, f"{label} {len(items)} 条，首条 view={s.get('view')}"
            last = f"{label} 返回空"
        return False, last

    def fetch(self) -> list[dict]:
        out: list[dict] = []
        self.endpoint_status = {"popular": {"ok": True}}
        self.endpoint_fingerprints: dict[str, dict] = {}
        urls = [
            (f"{BILI_API}/popular?ps=20&pn=1", "popular"),
            (f"{BILI_API}/ranking/v2?rid=0&type=all", "ranking_v2"),
        ]
        for rid in self.EXTRA_RIDS:
            urls.append((f"{BILI_API}/ranking/v2?rid={rid}&type=all", f"ranking_v2_rid{rid}"))

        for url, label in urls:
            try:
                items = self._fetch_list(url)
            except urllib.error.HTTPError as exc:
                self.endpoint_status[label] = {"ok": False, "error": f"HTTP {exc.code}"}
                time.sleep(2.0)
                continue
            except Exception as exc:  # noqa: BLE001
                self.endpoint_status[label] = {"ok": False, "error": str(exc)[:100]}
                time.sleep(2.0)
                continue
            if not items:
                self.endpoint_status[label] = {"ok": False, "error": "空列表"}
                time.sleep(2.0)
                continue
            self.endpoint_status[label] = {"ok": True, "items": len(items)}
            self.endpoint_fingerprints[label] = _schema_keys(items)
            time.sleep(1.2)
            for rank, v in enumerate(items, start=1):
                if not isinstance(v, dict):
                    continue
                st = v.get("stat") or {}
                out.append(
                    {
                        "platform": "bilibili",
                        "kind": "video",
                        "rank": rank,
                        "keyword": None,
                        "title": str(v.get("title") or "").strip(),
                        "heat": _as_int(st.get("view")),
                        "url": _first(v, ("short_link_v2", "bvid_url"))
                        or (f"https://www.bilibili.com/video/{v.get('bvid')}"
                            if v.get("bvid") else None),
                        "category": _first(v, ("tname", "tname_v2")),
                        "stat": {
                            "view": _as_int(st.get("view")),
                            "like": _as_int(st.get("like")),
                            "coin": _as_int(st.get("coin")),
                            "favorite": _as_int(st.get("favorite")),
                            "comment": _as_int(st.get("reply")),
                            "danmaku": _as_int(st.get("danmaku")),
                        },
                        "published": _iso_date(v.get("pubdate")),
                        "extra": {
                            "bvid": v.get("bvid"),
                            "owner": (v.get("owner") or {}).get("name"),
                            "list": label,
                            "duration": v.get("duration"),
                        },
                    }
                )
        return out

    def search_supply(self, keyword: str) -> dict | None:
        """How saturated a keyword is, and when the newest work on it appeared.

        `numResults` is capped at 1000 by Bilibili, so the raw count cannot
        distinguish "1000" from "5000" - it is useless as a supply measure.
        What IS useful is the NEWEST related upload: if a topic is heating up
        now but the newest related video is weeks old, nobody is making it yet.

        Hot words arrive as full headlines ("Anthropic 推出 AI 智能体 Claude
        Duet"), and Bilibili's search returns nothing for a long sentence, so
        the query is shortened in steps until something matches.

        Returns {"total", "latest_pubdate", "newest_days_ago", "samples"} or None.
        """
        for query in _search_queries(keyword):
            info = self._search_supply_once(query)
            if info and (info.get("total") or 0) > 0:
                info["query_used"] = query
                return info
        return None

    def _search_supply_once(self, query: str) -> dict | None:
        try:
            j = _get_json_retry(
                f"{BILI_API}/search/type?search_type=video"
                f"&keyword={urllib.parse.quote(query)}",
                headers=_bili_headers(),
            )
        except Exception:  # noqa: BLE001
            return None
        if j.get("code") != 0:
            return None
        data = j.get("data") or {}
        items = data.get("result") or []
        if not isinstance(items, list):
            items = []
        # Sort client-side by publish time: passing order=pubdate to this
        # endpoint returns an empty result.
        dated = [
            it for it in items
            if isinstance(it, dict) and isinstance(it.get("pubdate"), (int, float))
        ]
        dated.sort(key=lambda it: it["pubdate"], reverse=True)
        newest = int(dated[0]["pubdate"]) if dated else None
        samples = []
        import datetime as _dt
        for it in dated[:5]:
            samples.append({
                "title": str(it.get("title") or "")[:60],
                "play": _as_int(it.get("play")),
                "pubdate": _iso_date(it.get("pubdate")),
                "age_days": (_dt.date.today() - _dt.date.fromtimestamp(it["pubdate"])).days,
            })
        newest_days = None
        if newest:
            import datetime as _dt
            newest_days = (_dt.date.today() - _dt.date.fromtimestamp(newest)).days
        total = _as_int(data.get("numResults"))
        return {
            "total": total,
            "latest_pubdate": newest,
            "newest_days_ago": newest_days,
            "samples": samples,
        }

    def search_count(self, keyword: str) -> int | None:
        """How many videos exist for a keyword (the denominator of supply gap).

        Uses the public search endpoint; returns None when it is unavailable.
        """
        try:
            j = _get_json_retry(
                f"{BILI_API}/search/type?search_type=video&keyword={urllib.parse.quote(keyword)}",
                headers=_bili_headers(),
            )
        except Exception:  # noqa: BLE001
            return None
        if j.get("code") != 0:
            return None
        data = j.get("data") or {}
        for key in ("numResults", "numPages", "total"):
            v = _as_int(data.get(key))
            if v is not None:
                return v
        return None


# --------------------------------------------------------------------------
# YouTube  (official RSS + trending SSR; Data API v3 optional with a key)
# --------------------------------------------------------------------------

YT_API = "https://www.googleapis.com/youtube/v3"

# 「近 N 天高播放新视频」窗口：越短越早，越能抓到刚起的话题
RECENT_WINDOW_DAYS = 7

# 「近 N 天高播放新视频」怎么取（全部为 2026-10-23 实测结论，不是推测）：
#
# 官方 `search.list` **没有** `order=viewCount`。传了它 API 照样返回 200，但结果
# 根本不按播放量排（实测与 order=relevance 输出一致）——这是静默失效，最危险。
# 正确做法：先用关键词 + relevance 取候选池，再用 `videos.list` 拿 statistics，
# 本地按 viewCount 降序。
#
# 同一关键词 `AI|LLM|agent|GPT|Claude`、7 天窗口、top20 命中 AI 的条数：
#   order=date       16/20，播放量   6k..284k   ← 只给刚上传的，增速信号没法用
#   order=relevance  18/20，播放量 166k..3.46M  ← 用这个
#   order=rating     19/20，播放量 174k..1.57M  ← 命中高但混进大量 shorts 噪声
#   order=title      16/20，播放量 251k..7.8M   ← 混进非英语电视剧
#   不带 q（全球）     0/20，全是国际新闻/体育     ← 必须带赛道词，否则这一层没用
#
# 赛道词可用环境变量 `YOUTUBE_API_QUERY` 覆盖（逗号或 `|` 分隔均可）。
YT_SEARCH_ORDER = "relevance"
YT_DEFAULT_QUERY = "AI|LLM|agent|GPT|Claude"

# 追踪的频道：AI / 开发 / 效率。channel_id 为 YouTube 官方频道 ID。
YT_TRACKED_CHANNELS = {
    "UCsBjURrPoezykLs9EqgamOA": "Fireship",
}


def _extract_yt_initial_data(html: str) -> Any:
    """Pull the `ytInitialData` JSON object out of a YouTube HTML page."""
    marker = "var ytInitialData = "
    idx = html.find(marker)
    if idx < 0:
        marker = 'window["ytInitialData"] = '
        idx = html.find(marker)
    if idx < 0:
        return None
    start = html.find("{", idx + len(marker))
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(html)):
        ch = html[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _walk_video_renderers(node: Any, out: list[dict]) -> None:
    """Recursively find video renderers in ytInitialData.

    YouTube moved most surfaces to `lockupViewModel` (2025+), so both the old
    videoRenderer and the new lockupViewModel have to be handled.
    """
    if isinstance(node, dict):
        for key in ("videoRenderer", "compactVideoRenderer", "lockupViewModel"):
            if key in node and isinstance(node[key], dict):
                out.append(node[key])
        for v in node.values():
            _walk_video_renderers(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_video_renderers(v, out)


def _search_queries(keyword: str) -> list[str]:
    """Progressively shorter search queries for a hot-word headline.

    A hot word is a whole sentence ("Anthropic 推出 AI 智能体 Claude Duet")
    and Bilibili's search matches nothing on a long sentence. Steps:
      1. the headline as-is
      2. the headline without spaces
      3. the longest latin/alnum token (brand or product name)
      4. that token plus the trailing Chinese noun-ish chunk
    """
    out: list[str] = []
    kw = keyword.strip()
    if kw:
        out.append(kw)
        nospace = re.sub(r"\s+", "", kw)
        if nospace != kw:
            out.append(nospace)
        tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9._+-]*", kw)
        if tokens:
            longest = max(tokens, key=len)
            if longest not in out:
                out.append(longest)
            tail = re.findall(r"[\u4e00-\u9fff]{2,}", kw)
            if tail:
                combo = longest + " " + tail[-1]
                if combo not in out:
                    out.append(combo)
    seen = set()
    return [q for q in out if not (q in seen or seen.add(q))]


def _collect_strings(node: Any, out: list[str]) -> None:
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for v in node.values():
            _collect_strings(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_strings(v, out)


def _lockup_fields(r: dict) -> tuple[str | None, str | None, str | None]:
    """Extract (video_id, title, view_text) from a lockupViewModel."""
    vid = r.get("contentId") or r.get("videoId")
    strings: list[str] = []
    _collect_strings(r, strings)
    view_text = next((s for s in strings if "view" in s.lower()), None)
    title = None
    for s in strings:
        if s is view_text:
            continue
        if len(s) < 6 or s.isdigit():
            continue
        if "ago" in s.lower() or "watch" in s.lower():
            continue
        title = s
        break
    return (vid if isinstance(vid, str) else None, title, view_text)


class YouTubeAdapter(Adapter):
    name = "youtube"
    platform = "youtube"

    @staticmethod
    def _rss_text(cid: str, attempts: int = 4) -> tuple[str | None, str]:
        """Fetch a channel feed, retrying the transient failures.

        The YouTube feed endpoint is genuinely flaky: measured on 2026-10-23,
        the SAME url with the SAME user-agent returned 404, 500 and 200 within
        the same three seconds. Roughly half the calls succeed. A single shot
        therefore fails constantly and used to take the whole YouTube source
        down with it.
        """
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
        last = "unknown"
        for attempt in range(attempts):
            try:
                xml = _get_text(url, timeout=20)
                if "<entry>" in xml:
                    return xml, ""
                last = "空 feed"
            except urllib.error.HTTPError as exc:
                last = f"HTTP {exc.code}"
            except Exception as exc:  # noqa: BLE001
                last = str(exc)[:80]
            if attempt < attempts - 1:
                time.sleep(1.5 * (attempt + 1))
        return None, last

    def probe(self) -> tuple[bool, str]:
        cid = next(iter(YT_TRACKED_CHANNELS), None)
        rss_note = "未配置追踪频道"
        rss_ok = False
        if cid:
            xml, err = self._rss_text(cid)
            if xml:
                n = xml.count("<entry>")
                rss_ok = n > 0
                rss_note = f"RSS {n} 条"
            else:
                rss_note = f"RSS 不可用（{err}）"
        # The RSS feed and the Data API are INDEPENDENT layers. A flaky feed
        # must not take the Data API layer down with it - otherwise one 404
        # silently removes the only layer that carries view counts.
        if rss_ok:
            return True, rss_note
        if os.environ.get("YOUTUBE_API_KEY"):
            return True, f"{rss_note} / Data API 可用"
        return False, rss_note

    def _fetch_rss(self) -> list[dict]:
        out: list[dict] = []
        for cid, cname in YT_TRACKED_CHANNELS.items():
            xml, _err = self._rss_text(cid)
            if not xml:
                continue
            try:
                root = ElementTree.fromstring(xml)
            except ElementTree.ParseError:
                continue
            ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
            for rank, entry in enumerate(root.findall("a:entry", ns), start=1):
                vid = entry.findtext("yt:videoId", default="", namespaces=ns)
                title = entry.findtext("a:title", default="", namespaces=ns)
                published = entry.findtext("a:published", default="", namespaces=ns)
                out.append(
                    {
                        "platform": "youtube",
                        "kind": "video",
                        "rank": rank,
                        "keyword": None,
                        "title": title.strip(),
                        "heat": None,
                        "url": f"https://www.youtube.com/watch?v={vid}" if vid else None,
                        "category": cname,
                        "stat": {},
                        "published": published[:10] if published else None,
                        "extra": {"video_id": vid, "source": "rss"},
                    }
                )
        return out

    def _fetch_trending(self) -> list[dict]:
        out: list[dict] = []
        try:
            html = _get_text("https://www.youtube.com/feed/trending", timeout=35)
        except Exception:  # noqa: BLE001
            return out
        data = _extract_yt_initial_data(html)
        if not data:
            return out
        renderers: list[dict] = []
        _walk_video_renderers(data, renderers)
        seen: set[str] = set()
        rank = 0
        for r in renderers:
            vid = r.get("videoId")
            lock_title = lock_view = None
            if "lockupViewModel" in r:
                lock_vid, lock_title, lock_view = _lockup_fields(r["lockupViewModel"])
                vid = vid or lock_vid
            if not vid or vid in seen:
                continue
            seen.add(vid)
            rank += 1
            title = lock_title or (
                (r.get("title") or {}).get("simpleText")
                or "".join(
                    t.get("text", "") for t in ((r.get("title") or {}).get("runs") or [])
                )
            )
            view_text = lock_view or (
                (r.get("viewCountText") or {}).get("simpleText")
                or "".join(
                    t.get("text", "")
                    for t in ((r.get("viewCountText") or {}).get("runs") or [])
                )
            )
            published = (r.get("publishedTimeText") or {}).get("simpleText")
            owner = (
                (r.get("ownerText") or {}).get("simpleText")
                or "".join(
                    t.get("text", "")
                    for t in ((r.get("ownerText") or {}).get("runs") or [])
                )
            )
            out.append(
                {
                    "platform": "youtube",
                    "kind": "video",
                    "rank": rank,
                    "keyword": None,
                    "title": title.strip(),
                    "heat": _as_int(view_text),
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "category": owner or None,
                    "stat": {"view": _as_int(view_text)},
                    "published": published,
                    "extra": {"video_id": vid, "source": "trending"},
                }
            )
        return out

    def _fetch_data_api(self) -> list[dict]:
        """Recently-popular NEW videos via the official Data API v3.

        This is the official replacement for "trending" (the `feed/trending`
        surface is gone). The official API does NOT expose "recent AND high
        view" in one call, so this does it in two:

          1. `search.list` with a track query + `order=relevance` + a recent
             `publishedAfter` window  -> candidate pool (100 units)
          2. `videos.list?part=statistics` for those ids              -> counts (1 unit)

        and then ranks locally by view count. See YT_SEARCH_ORDER for the
        measured comparison of the four legal `order` values.

        Requires a free API key (YOUTUBE_API_KEY). Without it this layer is
        skipped and the reason is reported, never silently ignored.

        Cost: 101 units per collection (official free quota 10000 units/day).
        """
        key = os.environ.get("YOUTUBE_API_KEY")
        if not key:
            self.endpoint_status["data_api_recent_popular"] = {
                "ok": False,
                "error": "未配置 YOUTUBE_API_KEY（官方免费额度 10000 units/天）",
            }
            return []
        query_text = os.environ.get("YOUTUBE_API_QUERY", YT_DEFAULT_QUERY).strip()
        since = (dt.date.today() - dt.timedelta(days=RECENT_WINDOW_DAYS)).isoformat()
        query = (
            "part=snippet&type=video"
            f"&order={YT_SEARCH_ORDER}"
            f"&q={urllib.parse.quote(query_text)}"
            f"&publishedAfter={since}T00:00:00Z&maxResults=50"
            f"&key={key}"
        )
        try:
            j = _get_json(f"{YT_API}/search?{query}", timeout=25)
        except urllib.error.HTTPError as exc:
            self.endpoint_status["data_api_recent_popular"] = {"ok": False, "error": f"HTTP {exc.code}"}
            return []
        except Exception as exc:  # noqa: BLE001
            self.endpoint_status["data_api_recent_popular"] = {"ok": False, "error": str(exc)[:100]}
            return []
        items = j.get("items") or []
        if not items:
            self.endpoint_status["data_api_recent_popular"] = {"ok": False, "error": "空结果"}
            return []
        self.endpoint_fingerprints["data_api_recent_popular"] = _schema_keys(items)

        # `search.list` 的 items[i].id 是嵌套对象 {"kind": ..., "videoId": ...}，
        # 不是字符串——直接 f-string 会把整个 dict 拼进 URL。
        candidates: list[tuple[str, dict]] = []
        for it in items:
            raw = it.get("id")
            vid = raw.get("videoId") if isinstance(raw, dict) else raw
            if vid:
                candidates.append((vid, it.get("snippet") or {}))
        if not candidates:
            self.endpoint_status["data_api_recent_popular"] = {
                "ok": False,
                "error": "候选里没有可用的 videoId",
            }
            return []

        stats = self._youtube_statistics([v for v, _ in candidates], key)
        # 本地按播放量降序——这才是「高播放」的真正含义。
        ranked = sorted(
            candidates,
            key=lambda pair: (stats.get(pair[0]) or {}).get("view") or 0,
            reverse=True,
        )
        self.endpoint_status["data_api_recent_popular"] = {
            "ok": True,
            "items": len(ranked),
            "query": query_text,
            "order": YT_SEARCH_ORDER,
            "window_days": RECENT_WINDOW_DAYS,
            "units": 101,  # search.list 100 + videos.list 1
            "with_stats": sum(1 for v, _ in candidates if v in stats),
        }
        out: list[dict] = []
        for rank, (vid, snip) in enumerate(ranked, start=1):
            st = stats.get(vid) or {}
            out.append(
                {
                    "platform": "youtube",
                    "kind": "video",
                    "rank": rank,
                    "keyword": None,
                    "title": str(snip.get("title") or "").strip(),
                    "heat": st.get("view"),
                    "url": f"https://www.youtube.com/watch?v={vid}",
                    "category": snip.get("channelTitle"),
                    "stat": st,
                    "published": str(snip.get("publishedAt") or "")[:10] or None,
                    "extra": {
                        "video_id": vid,
                        "source": "data_api_recent_popular",
                        "published_at": snip.get("publishedAt"),
                        "window_days": RECENT_WINDOW_DAYS,
                        "query": query_text,
                    },
                }
            )
        return out

    @staticmethod
    def _youtube_statistics(video_ids: list[str], key: str) -> dict[str, dict]:
        """Fetch view/like/comment counts for up to 50 ids per request.

        `videos.list` costs 1 unit per call regardless of batch size, so 50 ids
        per call is the cheapest way to attach counts to the candidate pool.
        """
        stats: dict[str, dict] = {}
        for i in range(0, len(video_ids), 50):
            chunk = video_ids[i : i + 50]
            url = (
                f"{YT_API}/videos?part=statistics&id={urllib.parse.quote(','.join(chunk))}"
                f"&key={key}"
            )
            try:
                body = _get_json(url, timeout=25)
            except Exception:  # noqa: BLE001
                continue
            for v in body.get("items") or []:
                raw = v.get("statistics") or {}
                stats[v.get("id")] = {
                    "view": _as_int(raw.get("viewCount")),
                    "like": _as_int(raw.get("likeCount")),
                    "comment": _as_int(raw.get("commentCount")),
                }
        return stats

    def fetch(self) -> list[dict]:
        self.endpoint_status: dict[str, dict] = {}
        self.endpoint_fingerprints: dict[str, dict] = {}
        rss = self._fetch_rss()
        self.endpoint_status["rss"] = {"ok": bool(rss), "items": len(rss)}
        self.endpoint_fingerprints["rss"] = _schema_keys(rss)
        api = self._fetch_data_api()
        return api + rss


# --------------------------------------------------------------------------
# Chinese-side product pulse (Bilibili search, real play counts)
# --------------------------------------------------------------------------

CN_PRODUCTS_FILE = (
    Path(__file__).resolve().parent.parent / "references" / "cn_products.txt"
)

_TAG_RE = re.compile(r"</?em[^>]*>")


class CnPulseAdapter(Adapter):
    """Real Chinese-side play counts for a maintained list of AI products.

    Measured 2026-10-23: the scoring candidate pool held 173 YouTube
    candidates and 9 Chinese ones. The Chinese hot-word layers carry no heat
    value and never change rank, so S1 and S3 are structurally 0 for them and
    their total is capped at 3.0, while YouTube candidates floor at 5.0 -
    a domestic model could not be selected no matter how real the demand was.

    This face gives the Chinese side a comparable heat AND a comparable rank:
    for each product we take the play counts Bilibili returns, use the best
    work as that product's Chinese-side ceiling, and rank the products against
    each other. A product whose ceiling jumps climbs the list.

    It is a COLLECTION face only. Records carry platform "cnpulse" and are
    NOT admitted to the scoring pool until the regression set reaches 30
    snapshots (scoring version v4). Until then they only accumulate data.
    """

    name = "cnpulse"
    platform = "cnpulse"
    TOP_N = 8
    SLEEP = 1.5
    RECENT_DAYS = 14

    def _load_products(self) -> list[tuple[str, str]]:
        if not CN_PRODUCTS_FILE.exists():
            return []
        out: list[tuple[str, str]] = []
        for line in CN_PRODUCTS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            label, _, query = line.partition("|")
            label = label.strip()
            query = query.strip() or label
            if label:
                out.append((label, query))
        return out

    def _search(self, query: str) -> list[dict]:
        """Videos for a query, newest-weighted.

        The default (relevance) order is used on purpose. `order=click` ranks
        by all-time play count, so an evergreen tutorial from 2018 that merely
        mentions the product comes first - measured 2026-10-23 it handed
        "Seedance 即梦" a 18.2M heat that could never move again.
        """
        url = (
            f"{BILI_API}/search/type?search_type=video"
            f"&keyword={urllib.parse.quote(query)}"
        )
        try:
            j = _get_json_retry(url, headers=_bili_headers())
        except Exception:  # noqa: BLE001
            return []
        if j.get("code") != 0:
            return []
        items = (j.get("data") or {}).get("result") or []
        return [it for it in items if isinstance(it, dict)]

    def probe(self) -> tuple[bool, str]:
        products = self._load_products()
        if not products:
            return False, f"产品清单缺失或为空: {CN_PRODUCTS_FILE}"
        rows = self._search(products[0][1])
        if not rows:
            return False, "B 站搜索无结果"
        plays = [_as_int(r.get("play")) or 0 for r in rows]
        return True, (
            f"{len(products)} 个产品，首个「{products[0][0]}」窗口内最高播放 {max(plays or [0])}"
        )

    def _window(self, vids: list[dict], today: dt.date) -> tuple[int, bool, int, list[dict]]:
        """heat = the ceiling INSIDE the recent window.

        Returns (heat, stale, recent_count, window_sorted_by_play).

        An all-time maximum would be a constant - measured 2026-10-23, the
        play-count ordering handed "Seedance 即梦" a 18,263,579 heat from a
        2018-09-07 evergreen tutorial, a number that can never move and can
        therefore never carry a growth signal.
        """
        recent = [
            v for v in vids
            if v.get("pubdate")
            and (today - dt.date.fromisoformat(v["pubdate"])).days <= self.RECENT_DAYS
        ]
        window = sorted(recent or vids, key=lambda v: -v["play"])
        if not window:
            return 0, True, len(recent), []
        return window[0]["play"], not recent, len(recent), window

    def fetch(self) -> list[dict]:
        products = self._load_products()
        self.endpoint_status: dict[str, dict] = {}
        self.endpoint_fingerprints: dict[str, dict] = {}
        measured: list[dict] = []
        failed: list[str] = []
        all_keys: list[dict] = []
        today = dt.date.today()

        for label, query in products:
            rows = self._search(query)
            if not rows:
                failed.append(label)
                continue
            all_keys.extend(rows)
            vids = []
            for it in rows:
                play = _as_int(it.get("play"))
                if play is None:
                    continue
                vids.append({
                    "title": _TAG_RE.sub("", str(it.get("title") or ""))[:80],
                    "play": play,
                    "pubdate": _iso_date(it.get("pubdate")),
                    "bvid": it.get("bvid"),
                })
            if not vids:
                failed.append(label)
                continue
            # Keep the API's own (relevance) order for the SUPPLY view: that
            # is the list of what people actually made about this product.
            # Sorting by play count buries the most relevant - and most
            # competitive - videos: measured 2026-10-23, the "8G 显存 15 秒
            # 720p" video sits at position 3 for "MiniMax H3" but drops out of
            # a play-count top-8.
            ordered = list(vids)
            # heat = the Chinese-side ceiling INSIDE the recent window, so it
            # tracks what is happening now. An all-time maximum would be a
            # constant and could never carry a growth signal.
            heat, stale, recent_count, window = self._window(ordered, today)
            lead = window[0] if window else ordered[0]
            measured.append({
                "label": label,
                "query": query,
                "heat": heat,
                "stale": stale,
                "recent_count": recent_count,
                "top3_sum": sum(v["play"] for v in window[:3]),
                "videos": ordered[: self.TOP_N],
                "lead": lead,
            })
            time.sleep(self.SLEEP)

        self.endpoint_status["search"] = {
            "ok": bool(measured),
            "items": len(measured),
            "failed": failed,
        }
        if all_keys:
            self.endpoint_fingerprints["search"] = _schema_keys(all_keys)

        # Rank the products against EACH OTHER so the rank means the same
        # thing in every snapshot: a product climbing this list is climbing.
        measured.sort(key=lambda m: -m["heat"])
        out: list[dict] = []
        for rank, m in enumerate(measured, start=1):
            lead = m["lead"]
            out.append({
                "platform": "cnpulse",
                "kind": "keyword",
                "rank": rank,
                "keyword": m["label"],
                "title": lead["title"],
                "heat": m["heat"],
                "url": (
                    f"https://www.bilibili.com/video/{lead['bvid']}"
                    if lead.get("bvid") else None
                ),
                "category": "国产模型中文侧供给",
                "stat": {},
                "published": lead.get("pubdate"),
                "extra": {
                    "query": m["query"],
                    "stale": m["stale"],
                    "recent_count": m["recent_count"],
                    "recent_window_days": self.RECENT_DAYS,
                    "top3_sum": m["top3_sum"],
                    # relevance order = what people actually made about it
                    "top_videos": [
                        {"title": v["title"], "play": v["play"], "pubdate": v["pubdate"]}
                        for v in m["videos"]
                    ],
                },
            })
        return out


ADAPTERS: dict[str, Adapter] = {
    a.name: a for a in (
        SixtyAdapter(),
        BiliAdapter(),
        YouTubeAdapter(),
        CnPulseAdapter(),
    )
}

# 降级链：每个逻辑能力可以由多个源回答。collect.py 按顺序尝试。
DEGRADATION = {
    "keyword-hot": ["sixty", "sixty"],          # 60s 是抖音/小红书热榜的主源
    "video-rank": ["bilibili", "youtube"],      # 作品级：B站优先，YouTube 兜底
    "video-overseas": ["youtube"],
}

__all__ = [
    "Adapter", "SixtyAdapter", "BiliAdapter", "YouTubeAdapter",
    "ADAPTERS", "DEGRADATION", "urllib",
]

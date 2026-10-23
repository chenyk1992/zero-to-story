#!/usr/bin/env python3
"""Score hotspot candidates from the snapshot library.

    python scout.py score            # 五信号打分，输出排序候选
    python scout.py score --top 15 --supply-search 10
    python scout.py cluster          # 词面重叠预聚类（给 LLM 做语义聚类做铺垫）
    python scout.py card "关键词"      # 输出选题卡骨架（证据已填，角度/钩子留空）

Signals (see references/signals.md):
  S1 增速      新增热度/点赞速率        权重 25   需要至少两次快照
  S2 上榜天数  连续出现在快照里的天数    权重 15   需要历史
  S3 爬升斜率  名次变化率              权重 20   需要两次快照
  S4 跨平台    同一词出现在几个平台    权重 25   D1 即可用
  S5 供给缺口  热度分位 - 作品数分位    权重 15   D1 即可用（需一次搜索）

S4 与 S5 不需要历史，这是冷启动期唯一能用的两条「还没火但会火」判据。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import (EXIT_FAIL, EXIT_OK, resolve_data_root,  # noqa: E402
                     version_line)

# S5 (supply gap) needs a Bilibili search call. That lives in the sibling
# skill; if it is not installed the signal degrades to 0 with a visible note
# rather than crashing.
BILI = None
_BILI_NOTE = ""
for _candidate in (
    Path(__file__).resolve().parent.parent.parent / "hot-collect" / "scripts",
):
    if (_candidate / "adapters.py").exists():
        sys.path.insert(0, str(_candidate))
        try:
            from adapters import BiliAdapter as _BiliAdapter

            BILI = _BiliAdapter
        except Exception as _exc:  # noqa: BLE001
            _BILI_NOTE = f"hot-collect 的 adapters 导入失败: {_exc}"
        break
else:
    _BILI_NOTE = "未找到兄弟 skill hot-collect，S5 供给缺口将不可用"

APP_DIR_NAME = "zero-to-story"
DIR_NAME = "hotspot"

WEIGHTS = {"s1_velocity": 25, "s2_days": 15, "s3_climb": 20, "s4_cross": 25, "s5_gap": 15}

# 判定逻辑版本号。信号公式与权重没有变过；变的是「哪些记录有资格当候选」。
#   v1 只有热榜关键词（kind=keyword）进入候选池
#   v2 追加 YouTube「近 7 天高播放新视频」层的视频标题作为候选
#      （那一层的标题带播放量，可直接当热度参与同一套五信号打分）
# 换候选来源必须能一键回退，才能对着历史快照做回归对比。
SCORING_VERSION = "v3"

# 可用的候选来源
CANDIDATE_SOURCES = ("keywords", "youtube_highview")

# YouTube Data API 端点标识（该层记录的 extra.source）
YT_HIGHVIEW_SOURCE = "data_api_recent_popular"


def default_data_root() -> Path:
    env = os.environ.get("LFO_HOTSPOT_DATA")
    if env:
        return Path(env).expanduser().resolve()
    home = Path.home()
    if os.name == "nt":
        return home / "AppData" / "Local" / APP_DIR_NAME / DIR_NAME
    return home / ".local" / "share" / APP_DIR_NAME / DIR_NAME


def load_snapshots(root: Path, snapshots_dir: Path | None = None) -> list[dict]:
    """Load snapshots, newest last.

    `snapshots_dir` overrides where the month-partitioned snapshot folders
    live. The regression harness uses it to score against a FROZEN copy of
    the library, so that later growth of the live library cannot silently
    change what "the same 30 snapshots" means.
    """
    base = snapshots_dir if snapshots_dir else (root / "snapshots")
    snaps = []
    for month_dir in sorted(base.glob("*")):
        if not month_dir.is_dir():
            continue
        for path in sorted(month_dir.glob("*.json")):
            try:
                snaps.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
    return snaps


def _percentile(values: list[float], v: float) -> float:
    """0..1 percentile rank of v inside values."""
    if not values:
        return 0.0
    below = sum(1 for x in values if x < v)
    equal = sum(1 for x in values if x == v)
    return (below + equal / 2) / len(values)


MERGE_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "for", "on", "and", "or", "is", "are", "was",
    "were", "with", "my", "your", "this", "that", "it", "at", "be", "as", "by",
    "from", "how", "why", "what", "when", "who", "can", "do", "does", "did", "you",
    "we", "i", "not", "new", "best", "top", "full", "make", "made", "get", "got",
    "use", "using", "used", "just", "here", "now", "get", "more", "most", "all",
    "最", "的", "了", "在", "是", "我", "有", "和", "就", "不", "也", "这", "那", "你",
    "他", "她", "们", "个", "一", "上", "中", "大", "小", "多", "少",
}

# 中文共享子串的最短长度。4 个字是一个足够「像专有名词」的短语；
# 3 个字（如「国务院」）太容易撞车，宁可漏合并也不误合并。
CJK_PHRASE_MIN = 4
# 拉丁文必须是「相邻的两个内容词」才算同一个短语
LATIN_PHRASE_MIN = 2


def _latin_tokens(text: str) -> list[str]:
    out = []
    for t in re.split(r"[^\w\u4e00-\u9fff]+", text.lower()):
        t = t.strip()
        if len(t) >= 2 and t not in MERGE_STOPWORDS:
            out.append(t)
    return out


def _latin_phrases(text: str) -> set[tuple[str, str]]:
    toks = _latin_tokens(text)
    return {tuple(toks[i : i + 2]) for i in range(len(toks) - 1)}


def _cjk_phrases(text: str) -> set[str]:
    cjk = "".join(ch for ch in text if "\u4e00" <= ch <= "\u9fff")
    return {cjk[i : i + CJK_PHRASE_MIN] for i in range(len(cjk) - CJK_PHRASE_MIN + 1)}


def _same_story(a: str, b: str, plat_a: str = "", plat_b: str = "") -> bool:
    """Do two headlines describe the SAME EVENT?

    Measured 2026-10-23, three things killed the naive versions:

      1. A similarity threshold cannot decide it: "From Okra Harvest to a Sweet
         Surprise" vs "Groundnut Harvest & Traditional Village" scores 0.562,
         HIGHER than genuine duplicates. They are two different videos.
      2. A shared latin PHRASE cannot decide it either: 15 different YouTube
         videos all say "Claude Duet" -> one product, 15 distinct works, 15
         distinct topic angles. Merging them throws away 14 real candidates.
         That is data loss, not de-duplication.
      3. What IS safe: two Chinese hot-list headlines about the same news,
         written differently. The evidence is a shared CJK phrase of >= 4
         chars ("西藏那曲", "人民日报"), and that also catches the SAME news
         appearing on two different platforms (douyin + quark), which is a
         genuine cross-platform signal.

    So: CJK phrase evidence -> merge. Latin phrase evidence -> never merge
    (same product / same channel is not the same event). Cross-platform
    merging of the same EVENT needs semantics, not words - that is what the
    LLM alias table (v3b) is for.
    """
    if _cjk_phrases(a) & _cjk_phrases(b):
        return True
    return False


def merge_near_duplicates(cands: list[dict]) -> tuple[list[dict], dict]:
    """Merge candidates that are the same story told with different headlines.

    LOSSLESS BY CONSTRUCTION: every member of a merged group is preserved in the
    representative's `merged_from` list (keyword, total, platforms, signals).
    Nothing disappears; duplicates are relocated. `--dedup off` restores the
    pre-v3 output exactly.

    The representative keeps the highest total; the merged signals are the
    per-signal max across members, EXCEPT s4_cross which is recomputed from the
    UNION of platforms (a story's platform spread is a property of the story,
    not of one headline).
    """
    n = len(cands)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    pairs: list[tuple[int, int]] = []
    for i in range(n):
        for j in range(i + 1, n):
            if _same_story(cands[i]["keyword"], cands[j]["keyword"],
                           (cands[i].get("platforms") or [""])[0],
                           (cands[j].get("platforms") or [""])[0]):
                pairs.append((i, j))
                ra, rb = find(i), find(j)
                if ra != rb:
                    parent[ra] = rb

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    out: list[dict] = []
    merged_groups = 0
    absorbed = 0
    for members in groups.values():
        if len(members) == 1:
            out.append(cands[members[0]])
            continue
        merged_groups += 1
        absorbed += len(members) - 1
        mem = [cands[i] for i in members]
        rep = max(mem, key=lambda c: c["total"])
        merged = dict(rep)
        merged["signals"] = {
            k: max(m["signals"].get(k, 0) for m in mem) for k in rep["signals"]
        }
        plats = sorted({p for m in mem for p in m.get("platforms", [])})
        merged["platforms"] = plats
        merged["cross_platform"] = len(plats)
        merged["signals"]["s4_cross"] = round(
            min(1.0, (len(plats) - 1) / 2.0) * 100, 1
        )
        merged["total"] = round(
            sum(max(0.0, min(100.0, merged["signals"][k])) * WEIGHTS[k] / 100
                for k in WEIGHTS), 1
        )
        merged["max_heat"] = max(m.get("max_heat") or 0 for m in mem)
        merged["best_rank"] = min((m.get("best_rank") for m in mem
                                  if m.get("best_rank") is not None), default=None)
        merged["days_on"] = max(m.get("days_on") or 0 for m in mem)
        merged["merged_count"] = len(mem)
        merged["merged_from"] = [
            {
                "keyword": m["keyword"],
                "total": m["total"],
                "platforms": m.get("platforms", []),
                "signals": m["signals"],
            }
            for m in mem
        ]
        # supply info: keep the richest one we measured
        with_supply = [m for m in mem if m.get("supply")]
        if with_supply:
            best_supply = max(with_supply, key=lambda c: c["total"])
            merged["supply"] = best_supply["supply"]
            merged["supply_count"] = best_supply.get("supply_count")
            merged["supply_zero"] = best_supply.get("supply_zero", False)
        out.append(merged)

    out.sort(key=lambda c: -c["total"])
    info = {
        "enabled": True,
        "merged_groups": merged_groups,
        "absorbed": absorbed,
        "candidates_before": n,
        "candidates_after": len(out),
        "rule": "共享相邻内容词组(拉丁) 或 ≥4 字连续中文子串",
    }
    return out, info


def cluster_topics(cands: list[dict], min_members: int = 2, top_members: int = 8) -> list[dict]:
    """Group candidates that talk about the SAME THING - without dropping any.

    This is the read-only half of the near-duplicate work. Merging is unsafe
    (see `_same_story`), but the INFORMATION is valuable: when 11 candidates in
    the top list are all about Claude Duet, that is not noise, it is a signal
    that many creators are moving to that topic right now.

    Every candidate stays in the list; this only reports the clusters.
    """
    n = len(cands)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            a, b = cands[i]["keyword"], cands[j]["keyword"]
            if _latin_phrases(a) & _latin_phrases(b) or _cjk_phrases(a) & _cjk_phrases(b):
                ra, rb = find(i), find(j)
                if ra != rb:
                    parent[ra] = rb

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    out: list[dict] = []
    for members in groups.values():
        if len(members) < min_members:
            continue
        mem = [cands[i] for i in members]
        plats = sorted({p for m in mem for p in m.get("platforms", [])})
        out.append({
            "size": len(mem),
            "platforms": plats,
            "cross_platform": len(plats),
            "best_total": max(m["total"] for m in mem),
            "max_heat": max(m.get("max_heat") or 0 for m in mem),
            "best_keyword": max(mem, key=lambda c: c["total"])["keyword"],
            "members": [m["keyword"] for m in sorted(mem, key=lambda c: -c["total"])[:top_members]],
        })
    out.sort(key=lambda t: (-t["size"], -t["best_total"]))
    return out


def score(root: Path, top: int, supply_search: int,
          include: list[str] | None = None, exclude: list[str] | None = None,
          platforms: list[str] | None = None,
          candidate_sources: list[str] | None = None,
          snapshots_dir: Path | None = None,
          dedup: bool = True) -> dict:
    snaps = load_snapshots(root, snapshots_dir)
    if not snaps:
        raise SystemExit("没有快照，先跑 hot-collect 的 collect.py --collect")

    sources = [s for s in (candidate_sources or CANDIDATE_SOURCES) if s in CANDIDATE_SOURCES]
    use_keywords = "keywords" in sources
    use_youtube_highview = "youtube_highview" in sources

    # keyword -> list of (snapshot_index, rank, heat, platform)
    kw_hist: dict[str, list[tuple[int, int, int, str]]] = defaultdict(list)
    # videoId -> list of (snapshot_index, like, view)
    vid_hist: dict[str, list[tuple[int, int, int]]] = defaultdict(list)

    def keep_record(r: dict) -> bool:
        if platforms and r.get("platform") not in platforms:
            return False
        return True

    for si, snap in enumerate(snaps):
        for r in snap.get("records", []):
            if not keep_record(r):
                continue
            if r.get("kind") == "keyword" and r.get("keyword"):
                if not use_keywords:
                    continue
                kw_hist[r["keyword"]].append(
                    (si, int(r.get("rank") or 999), int(r.get("heat") or 0), r.get("platform") or "")
                )
            elif r.get("kind") == "video":
                vid = (r.get("extra") or {}).get("bvid") or (r.get("extra") or {}).get("video_id")
                # Snapshots taken before the YouTube adapter fix stored the raw
                # search.list id object {"kind":..., "videoId":...} instead of a
                # string. Such a value is unhashable and must not crash scoring;
                # it still carries a usable videoId, so salvage it.
                if isinstance(vid, dict):
                    vid = vid.get("videoId") or vid.get("id")
                if not isinstance(vid, str) or not vid:
                    continue
                st = r.get("stat") or {}
                vid_hist[vid].append(
                    (si, int(st.get("like") or 0), int(st.get("view") or 0))
                )
                # 「近 7 天高播放新视频」层的标题就是话题本身，而且带播放量，
                # 可以直接当热度进同一套五信号打分——这正是这一层存在的意义。
                # 只对这一个端点开放：B 站有 215 条标题，全放会把候选池淹掉。
                if use_youtube_highview and (r.get("extra") or {}).get("source") == YT_HIGHVIEW_SOURCE:
                    title = str(r.get("title") or "").strip()
                    if title:
                        kw_hist[title].append(
                            (si, int(r.get("rank") or 999), int(st.get("view") or 0), r.get("platform") or "")
                        )

    # Track filter: a general hot list is mostly national news, which has
    # nothing to do with an AI account. Filter BEFORE scoring, not after.
    if include:
        inc = [w.lower() for w in include if w]
        kw_hist = {
            k: v for k, v in kw_hist.items()
            if any(w in k.lower() for w in inc)
        }
    if exclude:
        exc = [w.lower() for w in exclude if w]
        kw_hist = {
            k: v for k, v in kw_hist.items()
            if not any(w in k.lower() for w in exc)
        }

    last = len(snaps) - 1
    n_snap = len(snaps)

    # ---- per keyword raw signals -------------------------------------------
    raw: dict[str, dict] = {}
    for kw, hist in kw_hist.items():
        days = {snaps[h[0]].get("collected_at", "")[:10] for h in hist}
        kw_platforms = {h[3] for h in hist if h[3]}

        # S1 velocity: heat delta between the two most recent appearances
        hs = sorted(hist, key=lambda x: x[0])
        vel = 0.0
        if len(hs) >= 2:
            h0, h1 = hs[-2], hs[-1]
            if h0[2] > 0:
                vel = (h1[2] - h0[2]) / h0[2]
        # S3 climb: rank improvement rate (positive = moved up)
        climb = 0.0
        if len(hs) >= 2:
            h0, h1 = hs[-2], hs[-1]
            if h0[1] < 999 and h1[1] < 999:
                climb = (h0[1] - h1[1]) / h0[1]

        raw[kw] = {
            "platforms": sorted(kw_platforms),
            "days_on": len(days),
            "best_rank": min((h[1] for h in hist if h[1] < 999), default=None),
            "max_heat": max((h[2] for h in hist), default=0),
            "last_rank": hs[-1][1],
            "velocity": vel,
            "climb": climb,
            "cross_platform": len(kw_platforms),
            "last_seen": snaps[hs[-1][0]].get("collected_at", "")[:19],
        }

    # ---- video level velocity (for B站 / YouTube works) --------------------
    # Diagnostic only: per-video like/view growth. It is NOT one of the five
    # signals and is not wired into the score - the same growth reaches the
    # score through the video title candidate (heat = view count).
    vid_vel: dict[str, float] = {}
    for vid, hist in vid_hist.items():
        hs = sorted(hist, key=lambda x: x[0])
        if len(hs) >= 2 and hs[-2][1] > 0:
            vid_vel[vid] = (hs[-1][1] - hs[-2][1]) / hs[-2][1]

    # ---- S5 supply gap ----------------------------------------------------
    # Bilibili's numResults is capped at 1000, so the raw count cannot measure
    # supply. What can: the age of the NEWEST related upload. A topic that is
    # heating up now while its newest related video is weeks old means nobody
    # is making it yet - that is the gap.
    heats = [r["max_heat"] for r in raw.values()]
    supply: dict[str, dict] = {}
    if supply_search > 0:
        if BILI is None:
            print(f"[degraded] S5 供给缺口不可用: {_BILI_NOTE}")
        else:
            bili = BILI()
            for i, (kw, r) in enumerate(sorted(raw.items(), key=lambda kv: -kv[1]["max_heat"])):
                if i >= supply_search:
                    break
                info = bili.search_supply(kw)
                if info:
                    supply[kw] = info
    ages = [v["newest_days_ago"] for v in supply.values() if v.get("newest_days_ago") is not None]

    # ---- normalise and score ----------------------------------------------
    for kw, r in raw.items():
        s1 = max(0.0, min(1.0, r["velocity"])) * 100 if r["velocity"] > 0 else 0.0
        s2 = min(1.0, r["days_on"] / 5.0) * 100
        s3 = max(0.0, min(1.0, r["climb"])) * 100 if r["climb"] > 0 else 0.0
        s4 = min(1.0, (r["cross_platform"] - 1) / 2.0) * 100
        s5 = 0.0
        if kw in supply:
            info = supply[kw]
            age = info.get("newest_days_ago")
            if age is None:
                # No related upload at all -> the topic is not in this lane.
                r["supply_zero"] = True
            else:
                heat_p = _percentile(heats, r["max_heat"])
                # Older newest-upload => bigger gap. Normalise over the window.
                age_p = 1.0 - (min(age, 60) / 60.0) if ages else 0.0
                s5 = max(0.0, min(1.0, heat_p - age_p)) * 100
            r["supply"] = info
        r["signals"] = {
            "s1_velocity": round(s1, 1),
            "s2_days": round(s2, 1),
            "s3_climb": round(s3, 1),
            "s4_cross": round(s4, 1),
            "s5_gap": round(s5, 1),
        }
        r["total"] = round(
            sum(max(0.0, min(100.0, r["signals"][k])) * WEIGHTS[k] / 100 for k in WEIGHTS), 1
        )
        r["supply_count"] = (r.get("supply") or {}).get("total")

    ranked = sorted(raw.items(), key=lambda kv: -kv[1]["total"])
    cands = [{"keyword": k, **v} for k, v in ranked]

    # ---- same-event merge (口径 v3) ----------------------------------------
    # Only the provably safe case is merged: two Chinese hot-list headlines
    # about the same news (shared CJK phrase). Same-product-different-video
    # is NOT merged - those are distinct works, merging them loses angles.
    dedup_info = {"enabled": dedup, "merged_groups": 0, "absorbed": 0}
    if dedup:
        cands, dedup_info = merge_near_duplicates(cands)

    # ---- topic clusters (read-only, never drops a candidate) ---------------
    topics = cluster_topics(cands)

    out = {
        "scoring_version": SCORING_VERSION,
        "candidate_sources": sources,
        "snapshots_used": n_snap,
        "last_snapshot_at": snaps[-1].get("collected_at"),
        "filters": {"include": include or [], "exclude": exclude or [], "platforms": platforms or []},
        "dedup": dedup_info,
        "topics": topics[:12],
        "candidates": cands[:top],
    }
    return out


def cluster(root: Path, threshold: float, snapshots_dir: Path | None = None) -> dict:
    """Cheap lexical pre-clustering so the LLM starts from groups, not a flat list."""
    snaps = load_snapshots(root, snapshots_dir)
    if not snaps:
        raise SystemExit("没有快照")
    words: list[str] = []
    seen = set()
    for snap in snaps:
        for r in snap.get("records", []):
            if r.get("kind") == "keyword" and r.get("keyword") and r["keyword"] not in seen:
                seen.add(r["keyword"])
                words.append(r["keyword"])

    def bigrams(s: str) -> set[str]:
        s = "".join(ch for ch in s.lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
        return {s[i : i + 2] for i in range(len(s) - 1)} or {s}

    groups: list[list[str]] = []
    for w in words:
        bw = bigrams(w)
        placed = False
        for g in groups:
            gw = bigrams(g[0])
            inter = len(bw & gw)
            union = len(bw | gw) or 1
            if inter / union >= threshold:
                g.append(w)
                placed = True
                break
        if not placed:
            groups.append([w])
    return {"groups": groups, "group_count": len(groups), "word_count": len(words)}


def card(root: Path, keyword: str) -> str:
    """Build a topic card skeleton with the evidence filled in."""
    # Score everything, but measure THIS keyword's supply - the generic
    # top-N supply search would describe a different topic.
    data = score(root, top=999, supply_search=0)
    cands = data["candidates"]
    hit = next((c for c in cands if c["keyword"] == keyword), None)
    if not hit:
        # Exact match only is unusable for a human: YouTube titles are long
        # English strings nobody types in full. Accept a unique substring.
        needle = keyword.strip().lower()
        partial = [c for c in cands if needle and needle in c["keyword"].lower()]
        if len(partial) == 1:
            hit = partial[0]
        elif len(partial) > 1:
            names = "\n".join(f"  - {c['keyword']}" for c in partial[:8])
            return (f"# 选题卡 · {keyword}\n\n"
                    f"⚠️ 「{keyword}」匹配到 {len(partial)} 个候选，请给更唯一的片段：\n{names}\n")
    if not hit:
        return f"# 选题卡 · {keyword}\n\n⚠️ 该词不在最近快照里，先跑 collect.py --collect。\n"
    keyword = hit["keyword"]
    if BILI is not None:
        info = BILI().search_supply(keyword)
        if info:
            hit["supply"] = info
            hit["supply_count"] = info.get("total")
            hit["supply_zero"] = info.get("newest_days_ago") is None
    sig = hit["signals"]
    lines = [
        f"# 选题卡 · {keyword}",
        "",
        "## 证据（由 topic-scout 计算，不要手改）",
        "",
        "| 信号 | 分 | 含义 |",
        "|---|---:|---|",
        f"| S1 增速 | {sig['s1_velocity']} | 最近两次快照的热度变化率 |",
        f"| S2 上榜天数 | {sig['s2_days']} | 出现在多少天的快照里 |",
        f"| S3 爬升斜率 | {sig['s3_climb']} | 名次变化率 |",
        f"| S4 跨平台 | {sig['s4_cross']} | 出现在 {hit['cross_platform']} 个平台：{', '.join(hit['platforms'])} |",
        f"| S5 供给缺口 | {sig['s5_gap']} | 同题**最新一条**作品距今（越小=越有人在跟）+ 热度分位 |",
        f"| **综合** | **{hit['total']}** | 加权总分 |",
        "",
        f"- 最高热度：{hit['max_heat']}｜最好名次：{hit['best_rank']}｜最近一次出现：{hit['last_seen']}",
        f"- 同题供给：B 站相关作品数 {hit.get('supply_count')}，最新一条距今 {(hit.get('supply') or {}).get('newest_days_ago')} 天",
        *(["", "> ⚠️ **B 站上没有任何同题作品**：该词还不在这个赛道，或者压根没人在做。先确认它值不值得做，别把无关当成机会。"] if hit.get("supply_zero") else []),
        "",
        "## 以下由你（Agent）填写",
        "",
        "### 切入角度（3 个，标注适配账号类型）",
        "1. ",
        "2. ",
        "3. ",
        "",
        "### 内容形式 + 开头 3 秒钩子",
        "- 形式：",
        "- 钩子：",
        "",
        "### 竞争度与难度",
        "- 同题最新一条发布时间：",
        "- 素材是否需要真拍 / 能否用录屏替代：",
        "",
        "### tag 建议 / BGM 方向",
        "- ",
        "",
        "### 借势风险提示",
        "- ",
        "",
        "### 违禁词自检",
        "- ",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["score", "cluster", "card"])
    ap.add_argument("keyword", nargs="?", default="")
    ap.add_argument("--data-root", type=Path, default=None)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--supply-search", type=int, default=10)
    ap.add_argument("--threshold", type=float, default=0.6)
    ap.add_argument("--include", default="", help="赛道过滤：逗号分隔，命中任一即保留")
    ap.add_argument("--exclude", default="", help="排除词：逗号分隔")
    ap.add_argument("--platforms", default="", help="限定平台：逗号分隔，如 douyin,rednote,youtube")
    ap.add_argument(
        "--candidate-sources",
        default=",".join(CANDIDATE_SOURCES),
        help="候选来源：逗号分隔，可选 keywords / youtube_highview（v1 回归用 keywords）",
    )
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--version", action="version", version=version_line())
    ap.add_argument("--dedup", choices=["on", "off"], default="on",
                    help="候选池近重复合并（口径 v3）；off = 回到 v2 行为")
    ap.add_argument(
        "--snapshots",
        type=Path,
        default=None,
        help="读指定快照目录（回归用冻结集），覆盖 <data-root>/snapshots",
    )
    args = ap.parse_args()

    root = args.data_root.expanduser().resolve() if args.data_root else default_data_root()
    snaps_dir = args.snapshots.expanduser().resolve() if args.snapshots else None

    def split(v: str) -> list[str]:
        return [x.strip() for x in v.split(",") if x.strip()]

    if args.command == "score":
        data = score(root, args.top, args.supply_search,
                     split(args.include), split(args.exclude), split(args.platforms),
                     split(args.candidate_sources), snaps_dir,
                     dedup=(args.dedup == "on"))
        text = json.dumps(data, ensure_ascii=False, indent=1)
        print(text)
        if args.out:
            args.out.write_text(text, encoding="utf-8")
            print(f"-> {args.out}")
    elif args.command == "cluster":
        data = cluster(root, args.threshold, snaps_dir)
        print(json.dumps(data, ensure_ascii=False, indent=1))
        if args.out:
            args.out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"-> {args.out}")
    else:
        if not args.keyword:
            raise SystemExit("card 需要给出关键词")
        print(card(root, args.keyword))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

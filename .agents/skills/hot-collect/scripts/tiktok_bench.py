#!/usr/bin/env python3
"""TikTok 视频级对标语料库（hot-collect 的第二个采集面）

TikTok has NO free, compliant, live video-level API (measured 2026-10-23, see
SOURCES.md). What IS available is a free public metadata corpus of 5.6B
public TikTok videos, published as monthly Parquet partitions, licensed
CC BY-NC 4.0.

This does two things:
  sync   fetch the newest monthly partition(s) into the isolated data root
  query  answer "how do TikTok creators talk about X, and does it work?"

It is NOT a hot-spot source and is deliberately NOT part of collect.py's
snapshot loop:
  * the corpus is monthly and lagged (latest measured partition ended
    2026-10-03), so a daily snapshot would repeat identical stale rows and
    produce zero deltas;
  * feeding stale rows into topic-scout would make a 3-week-old topic look
    "hot" in the trend signals.
So it lives here as a SEPARATE face of this skill, with its own freshness
reporting, and never touches snapshots/ or contracts/.

    python tiktok_bench.py sync --months 1
    python tiktok_bench.py stats
    python tiktok_bench.py top --limit 20
    python tiktok_bench.py tags --limit 20
    python tiktok_bench.py search "vibe coding" --limit 10
    python tiktok_bench.py hooks --query "claude code" --limit 15

Data root (first hit wins):
  1. --data-root
  2. env LFO_HOTSPOT_DATA
  3. <user data>/zero-to-story/hotspot
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import (EXIT_FAIL, EXIT_OK, need, resolve_data_root,  # noqa: E402
                     version_line)
from tiktok_filters import classify, split_tags  # noqa: E402

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REPO = "datasocial/tiktok-5.6B-videos"
COLS = ["video_id", "posted_at", "country", "language", "caption", "hashtags",
        "on_screen_text", "views", "likes", "comments", "shares", "saves",
        "downloads", "engagement_rate", "is_ai_generated",
        "not_recommended_for_fyp", "duration_ms", "sound_id"]


def corpus_dir(root: Path) -> Path:
    return root / "corpora" / "tiktok"


# --------------------------------------------------------------------------
# sync
# --------------------------------------------------------------------------

def _http_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def _list_months() -> list[str]:
    """Monthly partition paths, oldest first."""
    url = f"https://huggingface.co/api/datasets/{REPO}/tree/main/data"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        items = json.loads(resp.read().decode("utf-8", "replace"))
    paths = [it.get("path", "") for it in items if it.get("path", "").endswith(".parquet")]
    return sorted(paths)


def _remote_size(path: str) -> int:
    req = urllib.request.Request(
        f"https://huggingface.co/datasets/{REPO}/resolve/main/{path}",
        headers={"User-Agent": UA},
        method="HEAD",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return int(resp.headers.get("Content-Length") or 0)


def _download(path: str, dest: Path) -> bool:
    url = f"https://huggingface.co/datasets/{REPO}/resolve/main/{path}"
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=600) as resp, tmp.open("wb") as fh:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
    tmp.replace(dest)
    return True


def cmd_sync(args) -> int:
    root = resolve_data_root(args.data_root)
    dest_dir = corpus_dir(root)
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"数据根目录: {root}\n语料目录: {dest_dir}\n")
    try:
        months = _list_months()
    except Exception as exc:  # noqa: BLE001
        print(f"[fail] 列分区失败: {exc}")
        return 1
    print(f"远端月度分区 {len(months)} 个，取最近 {args.months} 个")
    for path in months[-args.months :]:
        name = Path(path).name
        dest = dest_dir / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"  [skip] {name} 已存在 ({dest.stat().st_size/1e6:.0f} MB)")
            continue
        try:
            size = _remote_size(path)
            print(f"  [get ] {name}  {size/1e6:.0f} MB")
            _download(path, dest)
            print(f"  [ok  ] {name} -> {dest.stat().st_size/1e6:.0f} MB")
        except Exception as exc:  # noqa: BLE001
            print(f"  [fail] {name}: {str(exc)[:120]}")
    return 0


# --------------------------------------------------------------------------
# query
# --------------------------------------------------------------------------

def _load(root: Path, month: str | None):
    # Optional deps are imported HERE, not at module level: a machine that only
    # runs the daily snapshot must not need pyarrow/pandas, and a machine that
    # lacks them must get an actionable message instead of a traceback.
    pq = need("pyarrow.parquet", "读 TikTok 语料 Parquet")
    pd = need("pandas", "TikTok 语料的表格运算")

    files = sorted(corpus_dir(root).glob("*.parquet"))
    if month:
        files = [f for f in files if f.stem == month]
    if not files:
        raise SystemExit("没有语料文件，先跑：tiktok_bench.py sync")
    f = files[-1]
    tbl = pq.read_table(f, columns=COLS)
    df = tbl.to_pandas()
    # Flatten the list-of-struct columns once. (Arrow's binary_join_element_wise
    # does not support list<string> on pyarrow 26, so this is the portable path.)
    from tiktok_filters import _flatten

    for name in ("hashtags", "on_screen_text"):
        df[name] = df[name].map(_flatten)
    return f, df


def _topic_subset(df):
    """Vectorised coarse prefilter, then the strict classifier on the subset.

    A row-by-row .apply() over 1.7M rows took minutes; the prefilter cuts it
    to a few tens of thousands before the expensive per-row scoring runs.
    """
    from tiktok_filters import PREFILTER, classify

    text = (df["caption"].fillna("").astype(str) + " "
            + df["hashtags"].fillna("").astype(str) + " "
            + df["on_screen_text"].fillna("").astype(str))
    mask = text.str.contains(PREFILTER, regex=True, na=False)
    cand = df[mask]
    if not len(cand):
        return cand
    keep = []
    for pos, row in zip(cand.index.to_numpy(), cand.itertuples(index=False)):
        res = classify(row.caption, row.hashtags, row.on_screen_text,
                       str(getattr(row, "language", "") or ""))
        if res["topic"]:
            keep.append(pos)
    return df.loc[keep]


def _is_topic(row) -> bool:
    return classify(row["caption"], row["hashtags"], row["on_screen_text"],
                    str(row.get("language") or ""))["topic"]


def _cmd_stats(args) -> int:
    root = resolve_data_root(args.data_root)
    f, df = _load(root, args.month)
    print(f"文件: {f.name}  {f.stat().st_size/1e6:.0f} MB")
    print(f"总行数: {len(df):,}")
    print(f"覆盖时间: {df['posted_at'].min()} .. {df['posted_at'].max()}")
    made = int((df["is_ai_generated"] == 1).sum())
    topic = _topic_subset(df)
    print(f"\n轴1 用 AI 生成的视频 (is_ai_generated=1): {made:,}"
          f"  ← 这是「用 AI 做内容」，不是「讲 AI」")
    print(f"轴2 主题是 AI 的视频: {len(topic):,}"
          f"  ← 这才是 AI 内容号要看的")
    if len(topic):
        v = topic["views"]
        print(f"\n主题口径播放量: 中位 {int(v.median()):,}  p90 {int(v.quantile(.9)):,}  "
              f"max {int(v.max()):,}")
        print(f"  >10万: {int((v>100_000).sum()):,}   >100万: {int((v>1_000_000).sum()):,}")
        print(f"语言分布: {dict(topic['language'].value_counts().head(8))}")
    print(f"\n注意: 语料是月度且滞后的，**不能**当热点源用（只做对标）。")
    return 0


def _cmd_top(args) -> int:
    root = resolve_data_root(args.data_root)
    f, df = _load(root, args.month)
    pool = _topic_subset(df) if args.topic_only else df
    if args.query:
        pat = re.compile(args.query, re.I)
        pool = pool[_search_haystack(pool).str.contains(pat, na=False)]
    topic = pool[pool["views"] >= args.min_views].sort_values("views", ascending=False)
    topic = topic.head(args.limit)
    scope = "主题AI" if args.topic_only else "全语料"
    print(f"{f.name} · {scope} · 播放量 TOP {len(topic)}\n")
    for _, r in topic.iterrows():
        cap = str(r["caption"])[:70].replace("\n", " ")
        print(f"  {int(r['views']):>9,} like={int(r['likes']):>7,} er={r['engagement_rate']:.3f} "
              f"| {str(r['posted_at'])[:10]} | {cap}")
    return 0


def _search_haystack(df):
    return (df["caption"].fillna("").astype(str) + " "
            + df["hashtags"].fillna("").astype(str) + " "
            + df["on_screen_text"].fillna("").astype(str))


def _cmd_tags(args) -> int:
    from collections import Counter

    root = resolve_data_root(args.data_root)
    f, df = _load(root, args.month)
    pool = _topic_subset(df) if args.topic_only else df
    if args.query:
        pat = re.compile(args.query, re.I)
        pool = pool[_search_haystack(pool).str.contains(pat, na=False)]
    counter: Counter = Counter()
    for row in pool["hashtags"]:
        for t in split_tags(row):
            counter[t.lower()] += 1
    scope = "主题AI" if args.topic_only else "全语料"
    print(f"{f.name} · {scope} · 话题标签 TOP {args.limit}\n")
    for t, c in counter.most_common(args.limit):
        print(f"  #{t:<26s} {c:>7,}")
    return 0


def _cmd_search(args) -> int:
    """Benchmark lookup: what does TikTok look like for THIS keyword.

    Searches the WHOLE corpus by default, not only AI-topic rows: the caller
    brings a specific topic, and the topic filter is a guess. On-screen text is
    searched as well - measured 2026-10-23, the caption of a 828K-view video
    said nothing about AI while its screen text said "Cuando intentas engañar
    a ChatGPT". Caption-only search would have missed it.
    """
    root = resolve_data_root(args.data_root)
    f, df = _load(root, args.month)
    pool = _topic_subset(df) if args.topic_only else df
    pat = re.compile(args.keyword, re.I)
    hit = pool[_search_haystack(pool).str.contains(pat, na=False)]
    hit = hit[hit["views"] >= args.min_views].sort_values("views", ascending=False)
    hit = hit.head(args.limit)
    scope = "主题AI" if args.topic_only else "全语料"
    print(f"{f.name} · {scope} · 匹配 /{args.keyword}/ → {len(hit)} 条（显示前 {len(hit)}）\n")
    for _, r in hit.iterrows():
        cap = str(r["caption"])[:74].replace("\n", " ")
        ost = str(r.get("on_screen_text") or "")[:56]
        print(f"  {int(r['views']):>9,} like={int(r['likes']):>7,} | {str(r['posted_at'])[:10]} | {cap}")
        if ost:
            print(f"              屏幕文字: {ost}")
    return 0


def _cmd_hooks(args) -> int:
    """Opening lines + on-screen text of the winners - the reusable part."""
    root = resolve_data_root(args.data_root)
    f, df = _load(root, args.month)
    pool = _topic_subset(df) if args.topic_only else df
    if args.query:
        pat = re.compile(args.query, re.I)
        pool = pool[_search_haystack(pool).str.contains(pat, na=False)]
    pool = pool[pool["views"] >= args.min_views].sort_values("views", ascending=False)
    scope = "主题AI" if args.topic_only else "全语料"
    print(f"{f.name} · {scope} · 头部内容怎么写的开头\n")
    shown = 0
    for _, r in pool.iterrows():
        cap = str(r["caption"]).strip().replace("\n", " ")
        ost = str(r.get("on_screen_text") or "")
        if not cap and not ost:
            continue
        shown += 1
        print(f"  [{int(r['views']):>9,}] {cap[:88]}")
        if ost:
            print(f"              屏幕文字: {ost[:80]}")
        if shown >= args.limit:
            break
    return 0


def _cmd_check(args) -> int:
    """Verbatim-overflow gate: does this draft copy text from the corpus?

    The corpus is CC BY-NC 4.0, so copying captions / on-screen text into a
    published video is the one thing that is clearly out of bounds. This gate
    catches it BEFORE publication.

    Method: character-level shingles (default 24 chars) of a normalised text
    (lower-case, punctuation stripped, whitespace collapsed). A shingle that
    exists in the corpus means the draft reproduces corpus text verbatim.

    Scope: the AI-topic rows plus the top rows by views - i.e. the material
    a creator would actually quote from. It is NOT a full-corpus index (1.7M
    rows would need a few hundred MB of shingles); it is a tripwire for the
    realistic failure mode, not a proof of absence.
    """
    import hashlib

    pd = need("pandas", "TikTok 语料的表格运算")
    root = resolve_data_root(args.data_root)
    f, df = _load(root, args.month)

    def norm(text: str) -> str:
        t = re.sub(r"[^\w\u4e00-\u9fff]+", " ", str(text).lower())
        return re.sub(r"\s+", " ", t).strip()

    draft_path = Path(args.draft).expanduser()
    draft = draft_path.read_text(encoding="utf-8")
    dn = norm(draft)

    # ---- stage 1: candidate recall over the WHOLE corpus -------------------
    # The creator may have copied from ANY row `search` returned, not only
    # from the AI-topic subset or the top-viewed rows. So the index must be
    # able to reach the whole corpus - but 1.7M rows of shingles is hundreds
    # of MB. Instead: take the draft's distinctive tokens, find the corpus
    # rows that contain them (vectorised), and only build shingles for those.
    tokens = sorted({t for t in dn.split(" ") if len(t) >= 5}, key=len, reverse=True)
    tokens = tokens[:40]
    if not tokens:
        print("草稿里没有足够长的词，跳过（无法做原文比对）")
        return 0
    pattern = "|".join(re.escape(t) for t in tokens)
    blob = (df["caption"].fillna("").astype(str) + " " +
            df["hashtags"].fillna("").astype(str) + " " +
            df["on_screen_text"].fillna("").astype(str))
    hit_mask = blob.str.contains(pattern, regex=True, na=False)
    cand = df[hit_mask]
    scope = _topic_subset(df)
    top = df.sort_values("views", ascending=False).head(args.scope)
    pool = pd.concat([cand, scope, top]).drop_duplicates(subset=["video_id"])

    # ---- stage 2: exact shingle index over the candidate rows --------------
    n = args.shingle
    index: dict[int, str] = {}
    for _, r in pool.iterrows():
        text = norm(f"{r['caption']} {r['hashtags']} {r['on_screen_text']}")
        for i in range(0, max(0, len(text) - n + 1)):
            h = int(hashlib.blake2b(text[i:i + n].encode("utf-8"), digest_size=8).hexdigest(), 16)
            index.setdefault(h, text[i:i + n])

    hits: list[tuple[int, str]] = []
    seen: set[str] = set()
    for i in range(0, max(0, len(dn) - n + 1)):
        piece = dn[i:i + n]
        if piece in seen:
            continue
        h = int(hashlib.blake2b(piece.encode("utf-8"), digest_size=8).hexdigest(), 16)
        if h in index:
            seen.add(piece)
            hits.append((i, piece))

    print(f"语料全量: {len(df):,} 行；草稿词召回候选: {len(cand):,} 行；"
          f"实际建索引: {len(pool):,} 行 / {len(index):,} 个 {n} 字片段")
    print(f"待检文件: {draft_path}  ({len(draft)} 字符)\n")
    if not hits:
        print(f"✅ PASS：没有发现与语料原文重合的 {n} 字以上片段。")
        return 0
    print(f"❌ FAIL：发现 {len(hits)} 处与语料原文重合（≥{n} 字）。以下内容不要直接发布：\n")
    for pos, piece in hits[:10]:
        print(f"  - 偏移 {pos}: {piece[:120]}")
    if len(hits) > 10:
        print(f"  … 另有 {len(hits)-10} 处")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", type=Path, default=None)
    ap.add_argument("--version", action="version", version=version_line())
    ap.add_argument("--month", default=None, help="只查某个月份分区，如 2026-10")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("sync", help="拉取最新月度分区")
    p.add_argument("--months", type=int, default=1, help="拉最近几个分区")
    p.set_defaults(func=cmd_sync)

    p = sub.add_parser("stats", help="语料体检：规模、覆盖时间、AI 两条轴")
    p.set_defaults(func=_cmd_stats)

    p = sub.add_parser("top", help="播放量 TOP")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--min-views", type=int, default=0)
    p.add_argument("--query", default=None, help="只在这个关键词的命中里排")
    p.add_argument("--topic-only", action="store_true", help="只统计「主题是 AI」的视频")
    p.set_defaults(func=_cmd_top)

    p = sub.add_parser("tags", help="话题标签分布")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--query", default=None, help="只统计这个关键词命中的视频")
    p.add_argument("--topic-only", action="store_true", help="只统计「主题是 AI」的视频")
    p.set_defaults(func=_cmd_tags)

    p = sub.add_parser("search", help="按关键词做对标查询（全语料）")
    p.add_argument("keyword")
    p.add_argument("--limit", type=int, default=15)
    p.add_argument("--min-views", type=int, default=0)
    p.add_argument("--topic-only", action="store_true", help="只搜「主题是 AI」的视频")
    p.set_defaults(func=_cmd_search)

    p = sub.add_parser("hooks", help="头部内容的开头写法与屏幕文字")
    p.add_argument("--limit", type=int, default=15)
    p.add_argument("--min-views", type=int, default=100000)
    p.add_argument("--query", default=None, help="只对这个关键词命中的视频")
    p.add_argument("--topic-only", action="store_true", help="只看「主题是 AI」的视频")
    p.set_defaults(func=_cmd_hooks)

    p = sub.add_parser("check", help="发布物原文泄漏闸：查草稿有没有抄语料原文")
    p.add_argument("draft", help="待检文件路径")
    p.add_argument("--shingle", type=int, default=24, help="片段长度（字符），默认 24")
    p.add_argument("--scope", type=int, default=5000, help="再纳入按播放量排序的前 N 行")
    p.set_defaults(func=_cmd_check)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())


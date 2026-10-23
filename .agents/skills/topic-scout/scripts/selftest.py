#!/usr/bin/env python3
"""topic-scout selftest · 离线自检（不联网、不碰真实语料）。

覆盖三件事：
  1. 打分链路能跑，五个信号都在，候选非空
  2. 打分是**确定的**（跑两次结果一致）——否则回归没有意义
  3. **回归闸门会红**：喂一个被破坏的基线，必须判 FAIL
     这一条是本 selftest 的重点：一个只会说 PASS 的闸门等于没有闸门。

    python selftest.py
    python selftest.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import regress  # noqa: E402
import scout  # noqa: E402


def _rec(platform: str, kind: str, rank: int, **kw) -> dict:
    base = {
        "platform": platform, "kind": kind, "rank": rank, "keyword": None,
        "title": None, "heat": None, "url": None, "category": None,
        "stat": {}, "published": None, "extra": {},
    }
    base.update(kw)
    return base


def build_fixture(root: Path, base: Path | None = None) -> None:
    """Three synthetic snapshots that make the five signals actually fire.

    Written twice: into the live snapshot layout and into the frozen
    regression layout, because the two consumers look in different places.
    """
    base = base or (root / "snapshots")
    def yt(rank, heat, title):
        return _rec("youtube", "video", rank, title=title, heat=heat,
                    category="creator", stat={"view": heat, "like": heat // 20},
                    url=f"https://www.youtube.com/watch?v=v{rank}",
                    extra={"video_id": f"v{rank}", "source": "data_api_recent_popular"})

    snaps = [
        ("0100.json", [
            _rec("douyin", "keyword", 1, keyword="AI 大模型", heat=1000),
            _rec("douyin", "keyword", 2, keyword="西藏那曲发生7级地震", heat=800),
            _rec("quark", "keyword", 1, keyword="西藏那曲市巴青县发生7.0级地震", heat=700),
            _rec("ai-news", "keyword", 1, keyword="Anthropic 推出 AI 智能体 Claude Duet", heat=500),
            yt(1, 100000, "Claude Duet Is Here!"),
            yt(2, 50000, "Did Claude Duet just kill Grok Bot?"),
            yt(3, 40000, "Anthropic Just Dropped Claude Duet (Full Breakdown)"),
        ]),
        ("0200.json", [
            _rec("douyin", "keyword", 1, keyword="AI 大模型", heat=3000),
            _rec("douyin", "keyword", 2, keyword="西藏那曲发生7级地震", heat=800),
            _rec("quark", "keyword", 1, keyword="西藏那曲市巴青县发生7.0级地震", heat=700),
            _rec("ai-news", "keyword", 1, keyword="Anthropic 推出 AI 智能体 Claude Duet", heat=500),
            yt(1, 300000, "Claude Duet Is Here!"),
            yt(2, 50000, "Did Claude Duet just kill Grok Bot?"),
            yt(3, 40000, "Anthropic Just Dropped Claude Duet (Full Breakdown)"),
        ]),
        ("0300.json", [
            _rec("douyin", "keyword", 2, keyword="AI 大模型", heat=3000),
            _rec("douyin", "keyword", 2, keyword="西藏那曲发生7级地震", heat=800),
            _rec("quark", "keyword", 1, keyword="西藏那曲市巴青县发生7.0级地震", heat=700),
            _rec("ai-news", "keyword", 1, keyword="Anthropic 推出 AI 智能体 Claude Duet", heat=500),
            yt(3, 900000, "Claude Duet Is Here!"),
            yt(2, 50000, "Did Claude Duet just kill Grok Bot?"),
            yt(3, 40000, "Anthropic Just Dropped Claude Duet (Full Breakdown)"),
        ]),
    ]
    for name, records in snaps:
        d = base / "2026-10"
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(json.dumps({
            "collected_at": f"2026-10-23T{name[:2]}:00:00+08:00",
            "sources": {}, "contracts": {}, "records": records,
        }, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    with tempfile.TemporaryDirectory(prefix="scout-selftest-") as tmp:
        root = Path(tmp)
        build_fixture(root)
        build_fixture(root, root / "regression" / "snapshots")

        # 1. 打分能跑
        data = scout.score(root, top=20, supply_search=0,
                           snapshots_dir=root / "snapshots")
        cands = data["candidates"]
        check("打分产出候选", len(cands) > 0, f"{len(cands)} 个候选")
        check("快照被读到", data["snapshots_used"] == 3, f"{data['snapshots_used']} 份")

        # 2. 五个信号都在，且没有第六个
        sigs = sorted({k for c in cands for k in c["signals"]})
        expected = ["s1_velocity", "s2_days", "s3_climb", "s4_cross", "s5_gap"]
        check("信号集合恰好是五个", sigs == expected, f"{sigs}")

        # 3. S1 增速在合成数据上真的非零（播放量 10万→30万→90万）
        s1_hits = sum(1 for c in cands if c["signals"]["s1_velocity"] > 0)
        check("S1 增速能算出来", s1_hits > 0, f"{s1_hits} 个候选非零")

        # 4. 确定性
        again = scout.score(root, top=20, supply_search=0,
                            snapshots_dir=root / "snapshots")
        check("两次打分结果一致（确定性）",
              json.dumps(again, sort_keys=True, ensure_ascii=False)
              == json.dumps(data, sort_keys=True, ensure_ascii=False))

        # 5. 回归闸门：先造基线，再对着坏基线跑，必须 FAIL
        reg = root / "regression"
        reg.mkdir(parents=True, exist_ok=True)
        base = regress.summarize(regress.run_profile(root, "v2", 20, []))
        (reg / "baseline-v2.json").write_text(
            json.dumps(base, ensure_ascii=False, indent=1), encoding="utf-8")
        check("基线可生成", len(base["candidates"]) > 0, f"{len(base['candidates'])} 候选")

        good = regress.check(base, regress.summarize(regress.run_profile(root, "v2", 20, [])), regress.PROFILES["v2"])
        check("对着好基线判据全过", all(ok for _, ok, _ in good),
              "; ".join(n for n, ok, _ in good if not ok))

        broken = json.loads(json.dumps(base))
        broken["candidates"] = broken["candidates"][:1]
        for c in broken["candidates"]:
            c["total"] = c["total"] + 99
        bad = regress.check(broken, regress.summarize(regress.run_profile(root, "v2", 20, [])),
                            regress.PROFILES["v2"])
        failed_names = [n for n, ok, _ in bad if not ok]
        check("对着坏基线必须报红", len(failed_names) > 0,
              f"报红判据: {failed_names}")

        # 6. card 能出卡，且子串匹配可用
        card = scout.card(root, "Anthropic Just Dropped")
        check("选题卡能生成", card.startswith("# 选题卡"), card.splitlines()[0][:60])
        check("选题卡含证据段", "## 证据" in card)
        check("选题卡留空角度待填", "切入角度" in card)
        ambiguous = scout.card(root, "Claude Duet")
        check("歧义片段会列出候选而不是瞎选", "匹配到" in ambiguous,
              ambiguous.splitlines()[1][:56] if len(ambiguous.splitlines()) > 1 else "")

        # 7. 同一事件合并：同一条中文新闻的两种写法要合并
        on = scout.score(root, top=9999, supply_search=0, snapshots_dir=root / "snapshots",
                         dedup=True)
        off = scout.score(root, top=9999, supply_search=0, snapshots_dir=root / "snapshots",
                          dedup=False)
        kw_off = {c["keyword"] for c in off["candidates"]}
        # 无损的正确判据：合并后每个候选要么还在顶层，要么出现在某个 merged_from 里
        surviving = set()
        for c in on["candidates"]:
            if c.get("merged_count", 1) > 1:
                surviving.update(m["keyword"] for m in c["merged_from"])
            else:
                surviving.add(c["keyword"])
        check("合并无损：每个候选都还在（顶层或 merged_from）",
              surviving == kw_off,
              f"少了 {sorted(kw_off - surviving)[:3] or '无'}")
        check("同一中文新闻的两种写法被合并",
              len(on["candidates"]) < len(off["candidates"]),
              f"{len(off['candidates'])} -> {len(on['candidates'])}")

        # 8. 同一产品的不同 YouTube 视频【不能】合并（那是不同的作品）
        claude_videos = {k for k in kw_off if "Claude Duet" in k or "Grok Bot" in k}
        kept = {k for k in claude_videos
                if any(k == c["keyword"] or k in [m["keyword"] for m in c.get("merged_from", [])]
                       for c in on["candidates"])}
        check("同产品的不同 YouTube 视频不被合并",
              len(kept) == len(claude_videos),
              f"{len(claude_videos)} 个视频 -> 保留 {len(kept)} 个")

        # 9. 话题簇：同题多视频要报出簇，且不删候选
        topics = on.get("topics") or []
        check("话题簇非空", len(topics) > 0, f"{len(topics)} 个簇")
        check("话题簇能标出跨平台",
              any(t["cross_platform"] > 1 for t in topics),
              str([(t["size"], t["platforms"]) for t in topics[:4]]))

    failed = [r for r in results if not r[1]]
    if args.json:
        print(json.dumps({
            "skill": "topic-scout", "selftest": "ok" if not failed else "failed",
            "cases": [{"name": n, "ok": o, "detail": d} for n, o, d in results],
        }, ensure_ascii=False, indent=1))
    else:
        print("topic-scout selftest")
        for n, o, d in results:
            print(f"  {'✅' if o else '❌'} {n}" + (f": {d}" if d else ""))
        print()
        if failed:
            print(f"❌ {len(failed)}/{len(results)} 个用例失败")
        else:
            print(f"✅ {len(results)}/{len(results)} 个用例通过（离线，不碰网络与真实数据）")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

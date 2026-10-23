#!/usr/bin/env python3
"""hot-collect selftest · 离线自检（不联网、不碰真实语料、不写用户数据）。

为什么要有它：把 skill 搬到另一台机器后，第一件事是「证明它在这台机器上是好的」。
这件事必须能在**没有网络、没有 API key、没有 191MB 语料**的情况下做完，否则验证
本身就成了迁移障碍。

做法：用合成快照喂给真实的聚合/契约逻辑，断言输出。

    python selftest.py          # 人类可读
    python selftest.py --json   # 机器可读
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import collect as collect_mod  # noqa: E402


def _rec(platform: str, kind: str, rank: int, **kw) -> dict:
    base = {
        "platform": platform, "kind": kind, "rank": rank, "keyword": None,
        "title": None, "heat": None, "url": None, "category": None,
        "stat": {}, "published": None, "extra": {},
    }
    base.update(kw)
    return base


def build_fixture(root: Path) -> None:
    """Three synthetic snapshots with values we can assert on exactly."""
    snaps = [
        ("2026-10", "0100.json", [
            _rec("douyin", "keyword", 1, keyword="AI 大模型", heat=1000),
            _rec("douyin", "keyword", 2, keyword="Claude Code", heat=500),
            _rec("bilibili", "video", 1, title="某视频", heat=9000,
                 category="科技", stat={"view": 9000, "like": 300},
                 url="https://www.bilibili.com/video/BV1xx", extra={"bvid": "BV1xx"}),
        ]),
        ("2026-10", "0200.json", [
            _rec("douyin", "keyword", 1, keyword="AI 大模型", heat=2000),
            _rec("douyin", "keyword", 3, keyword="Claude Code", heat=500),
            _rec("bilibili", "video", 1, title="某视频", heat=12000,
                 category="科技", stat={"view": 12000, "like": 400},
                 url="https://www.bilibili.com/video/BV1xx", extra={"bvid": "BV1xx"}),
        ]),
        ("2026-10", "0300.json", [
            _rec("douyin", "keyword", 2, keyword="AI 大模型", heat=3000),
            _rec("youtube", "video", 1, title="Some AI video", heat=500000,
                 category="creator", stat={"view": 500000, "like": 20000},
                 url="https://www.youtube.com/watch?v=abc",
                 extra={"video_id": "abc", "source": "data_api_recent_popular"}),
        ]),
    ]
    for month, name, records in snaps:
        d = root / "snapshots" / month
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(json.dumps({
            "collected_at": f"2026-10-23T{name[:2]}:00:00+08:00",
            "sources": {"fixture": {"ok": True, "note": "selftest", "items": len(records)}},
            "contracts": {},
            "records": records,
        }, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    with tempfile.TemporaryDirectory(prefix="hotspot-selftest-") as tmp:
        root = Path(tmp)

        # 1. 合成快照能建起来
        build_fixture(root)
        snaps = sorted(root.rglob("snapshots/*/*.json"))
        check("合成快照写入", len(snaps) == 3, f"{len(snaps)} 份")

        # 2. 聚合能跑，且数值正确
        out = collect_mod.aggregate(root)
        agg = json.loads((root / "aggregates" / "2026-10.json").read_text(encoding="utf-8"))
        kw = agg["keywords"]
        check("聚合产出关键词", "AI 大模型" in kw and "Claude Code" in kw,
              f"关键词 {sorted(kw)}")
        check("聚合 best_rank 正确",
              kw.get("AI 大模型", {}).get("best_rank") == 1,
              f"best_rank={kw.get('AI 大模型', {}).get('best_rank')}")
        check("聚合 max_heat 正确",
              kw.get("AI 大模型", {}).get("max_heat") == 3000,
              f"max_heat={kw.get('AI 大模型', {}).get('max_heat')}")
        check("聚合只收 kind=keyword",
              "某视频" not in kw and "Some AI video" not in kw,
              f"关键词集 {sorted(kw)}")
        check("聚合 platforms 去重", kw.get("AI 大模型", {}).get("platforms") == ["douyin"],
              f"{kw.get('AI 大模型', {}).get('platforms')}")

        # 3. 记录形状符合文档契约
        snap0 = json.loads(snaps[0].read_text(encoding="utf-8"))
        required = {"platform", "kind", "rank", "keyword", "title", "heat",
                    "url", "category", "stat", "published", "extra"}
        shape_ok = all(required.issubset(set(r)) for r in snap0["records"])
        check("记录字段形状符合契约", shape_ok,
              f"缺字段: {sorted(set().union(*[required - set(r) for r in snap0['records']]))}")

        # 4. 数据根解析不依赖当前工作目录
        import os
        cwd = os.getcwd()
        try:
            os.chdir(tmp)
            from _common import default_data_root
            dr = default_data_root()
            check("数据根解析与 CWD 无关", dr.is_absolute(), str(dr))
        finally:
            os.chdir(cwd)

    failed = [r for r in results if not r[1]]
    if args.json:
        print(json.dumps({
            "skill": "hot-collect", "selftest": "ok" if not failed else "failed",
            "cases": [{"name": n, "ok": o, "detail": d} for n, o, d in results],
        }, ensure_ascii=False, indent=1))
    else:
        print("hot-collect selftest")
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

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

        # 5. cnpulse 采集面（离线，不联网）
        import datetime as dt

        from adapters import CnPulseAdapter, _bili_cookie_path

        ad = CnPulseAdapter()
        products = ad._load_products()
        check("产品清单可解析且非空", len(products) >= 5,
              f"{len(products)} 个产品，例：{products[0] if products else None}")
        check("产品清单格式正确（标签|搜索词）",
              all(lbl and qry for lbl, qry in products),
              f"样例：{products[:2]}")

        # heat 必须取近窗口，不能取历史最高。实测踩过的坑：按全站播放量排序，
        # 「Seedance 即梦」拿到 18,263,579 —— 来自 2018-09-07 的通用教程。
        today = dt.date(2026, 10, 23)
        vids = [
            {"title": "2018 通用教程", "play": 18_263_579, "pubdate": "2018-09-07", "bvid": "a"},
            {"title": "本月的作品", "play": 102_642, "pubdate": "2026-10-15", "bvid": "b"},
            {"title": "上周的作品", "play": 4_392, "pubdate": "2026-10-20", "bvid": "c"},
        ]
        heat, stale, recent_count, _ = ad._window(vids, today)
        check("heat 取近窗口而非历史最高", heat == 102_642,
              f"heat={heat}（历史最高是 18,263,579）")
        check("近期作品计数正确", recent_count == 2, f"recent_count={recent_count}")
        check("窗口内有近期作品时不标记 stale", stale is False, f"stale={stale}")

        old_only = [v for v in vids if v["pubdate"] < "2026-01-01"]
        heat2, stale2, _, _ = ad._window(old_only, today)
        check("窗口内无近期作品时降级并标记 stale", stale2 is True and heat2 == 18_263_579,
              f"heat={heat2} stale={stale2}")

        # cookie 必须落在解析出来的数据根下（不能写死路径）
        from _common import default_data_root as _dr

        cp = _bili_cookie_path()
        check("cookie 路径落在数据根下",
              cp.parent.name == "cookies" and cp.parent.parent == _dr(),
              f"{cp}  vs 数据根 {_dr()}")

        # 6. competitions 采集面（离线，不联网）
        from adapters import CompetitionsAdapter, _devpost_deadline

        # 截止日期解析：Devpost 的日期写法有好几种，解析错了「剩几天」就全错
        cases = {
            "Oct 22 - Nov 16, 2026": "2026-11-16",
            "Oct 21 - 27, 2026": "2026-10-27",
            "Oct 23 - 24, 2026": "2026-10-24",
            "Nov 16, 2026": "2026-11-16",
            "Oct 21, 2026 - Nov 30, 2026": "2026-11-30",
            "": None,
        }
        bad = {k: _devpost_deadline(k) for k, v in cases.items() if _devpost_deadline(k) != v}
        check("赛事截止日期解析正确", not bad, f"错解: {bad}")

        cad = CompetitionsAdapter()
        inc, exc = cad._load_filters()
        check("赛事过滤表可解析且非空", len(inc) >= 1 and len(exc) >= 1,
              f"include {len(inc)} 条 / exclude {len(exc)} 条")

        # 过滤真的生效：AI 的留下，crypto 的踢掉
        ai_hack = {"title": "UGREEN Hackathon 2026 on AI NAS",
                   "description": "Build AI agents on a NAS",
                   "themes": [{"name": "AI"}], "tags": []}
        crypto_hack = {"title": "Dakar Bitcoin Hack by BTrust",
                       "description": "Build crypto apps",
                       "themes": [{"name": "Blockchain"}], "tags": []}
        kept = cad._filter([ai_hack, crypto_hack])
        check("赛事过滤保留 AI、排除 crypto",
              len(kept) == 1 and kept[0]["title"].startswith("UGREEN"),
              f"留下 {[k.get('title') for k in kept]}")

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

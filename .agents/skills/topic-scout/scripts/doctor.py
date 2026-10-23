#!/usr/bin/env python3
"""topic-scout doctor · 判断层是否就绪。

    python doctor.py            # 全查
    python doctor.py --offline  # 不联网
    python doctor.py --json

退出码与 hot-collect 一致：
  0 可用 / 1 判定失败 / 2 环境未就绪
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import (EXIT_ENV, EXIT_FAIL, EXIT_OK, SKILL_VERSION,  # noqa: E402
                     have, resolve_data_root, sibling_skill, version_line)

OK, WARN, BLOCK = "ok", "warn", "block"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", type=Path, default=None)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    checks: list[dict] = []

    def add(name: str, status: str, detail: str, fix: str = "") -> None:
        checks.append({"name": name, "status": status, "detail": detail, "fix": fix})

    py_ok = sys.version_info >= (3, 10)
    add("Python 版本", OK if py_ok else BLOCK, f"{sys.version.split()[0]} (需要 ≥3.10)",
        "" if py_ok else "换用 Python 3.10+")

    add("核心依赖（标准库）", OK, "json / urllib / re / pathlib 齐备")

    root = resolve_data_root(args.data_root)
    writable = True
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".doctor-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception as exc:  # noqa: BLE001
        writable = False
        add("数据根目录", BLOCK, f"{root} 不可写：{exc}",
            "用 --data-root 指定可写目录，或设置 LFO_HOTSPOT_DATA")
    if writable:
        add("数据根目录", OK, str(root))

    # 只数活库 root/snapshots；regression/snapshots 是冻结副本，不算进来
    # （否则会虚报一倍）。
    live_root = root / "snapshots"
    snaps = sorted(live_root.rglob("*.json")) if live_root.exists() else []
    n = len(snaps)
    if n == 0:
        add("快照库", BLOCK, "0 份 → 没有快照就没有候选可打",
            "python ../hot-collect/scripts/collect.py --collect")
    elif n < 2:
        add("快照库", WARN, f"{n} 份 → S1/S3 需要至少两份快照")
    elif n < 30:
        add("快照库", WARN, f"{n} 份（回归门禁要求 30 份）",
            "继续每天 collect，满 30 后 regress.py --freeze")
    else:
        add("快照库", OK, f"{n} 份")

    hot = sibling_skill("hot-collect")
    add("兄弟 skill hot-collect", OK if hot else WARN,
        str(hot) if hot else "没找到 → S5 供给缺口降级为 0（其余信号不受影响）",
        "" if hot else "把 hot-collect/ 放到与 topic-scout/ 同级目录")

    reg = root / "regression"
    man = reg / "manifest.json"
    baselines = sorted(reg.glob("baseline-*.json")) if reg.exists() else []
    if man.exists():
        try:
            m = json.loads(man.read_text(encoding="utf-8"))
            add("冻结回归集", OK, f"{m.get('actual_count')}/{m.get('target_count')} 份",
                "" if m.get("actual_count", 0) >= 30 else "满 30 后重跑 regress.py --freeze")
        except Exception:  # noqa: BLE001
            add("冻结回归集", WARN, f"{man} 读不出来")
    else:
        add("冻结回归集", WARN, "没有冻结 → 跑 regress.py --freeze")
    add("口径基线", OK if baselines else WARN,
        ", ".join(b.name for b in baselines) if baselines else "没有基线 → regress.py --make-baseline")

    if not args.offline:
        try:
            import scout
            data = scout.score(root, top=5, supply_search=0)
            add("打分可运行", OK, f"候选 {len(data['candidates'])} 个，口径 {data['scoring_version']}")
        except Exception as exc:  # noqa: BLE001
            add("打分可运行", BLOCK, f"{str(exc)[:120]}")
    else:
        add("打分可运行", OK, "已跳过（--offline）")

    blocked = [c for c in checks if c["status"] == BLOCK]
    warned = [c for c in checks if c["status"] == WARN]

    if args.json:
        print(json.dumps({
            "skill": "topic-scout", "version": SKILL_VERSION,
            "data_root": str(root), "checks": checks,
            "blocked": len(blocked), "warned": len(warned),
            "exit": EXIT_OK if not blocked else EXIT_ENV,
        }, ensure_ascii=False, indent=1))
    else:
        print(f"{version_line()}  ·  数据根目录 {root}\n")
        icon = {OK: "✅", WARN: "⚠️ ", BLOCK: "❌"}
        for c in checks:
            print(f"  {icon[c['status']]} {c['name']}: {c['detail']}")
            if c["fix"] and c["status"] != OK:
                print(f"        → 修复: {c['fix']}")
        print()
        print(f"阻塞 {len(blocked)} 项，降级 {len(warned)} 项")
        if blocked:
            print("❌ 环境未就绪")
        elif warned:
            print("⚠️  可用，但有降级项")
        else:
            print("✅ 全部就绪")

    if blocked:
        return EXIT_ENV
    if warned and args.strict:
        return EXIT_FAIL
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

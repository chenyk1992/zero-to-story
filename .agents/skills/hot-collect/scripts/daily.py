#!/usr/bin/env python3
"""hot-collect daily · 一条命令跑完整条链路，并给出今日选题建议。

这是「把 skill 变成完整、成熟、稳定的调用链路」的落点：
  1. 采集（hot-collect 本体）→ 落快照 + 更新契约指纹
  2. 打分（兄弟 skill topic-scout）→ 按赛道过滤排序
  3. 汇总建议 → 打印可直接开做的方向 + 证据出处 + 降级说明

topic-scout 没装时**降级为只采集**（不报错），因为链路必须能分步跑。

    python daily.py                          # 完整链路
    python daily.py --include "AI,Claude"    # 自定义赛道
    python daily.py --no-collect             # 跳过采集，只用已有快照打分
    python daily.py --json                   # 机器可读

退出码：0 成功 / 1 判定不合格 / 2 环境未就绪
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import (EXIT_ENV, EXIT_FAIL, EXIT_OK, hydrate_user_env,  # noqa: E402
                     resolve_data_root, sibling_skill, version_line)

DEFAULT_INCLUDE = ("AI,大模型,智能,Agent,编程,代码,GPT,Claude,Gemini,"
                    "机器学习,推理,生成,开源,LLM,机器人,网络安全")


def run_collect(root: Path) -> int:
    import collect as collect_mod

    print("=== 1/3 采集 ===")
    try:
        payload = collect_mod.collect(root)
    except Exception as exc:  # noqa: BLE001
        print(f"  ❌ 采集失败：{str(exc)[:160]}")
        return EXIT_FAIL
    contracts = payload.get("contracts") or {}
    changed = [k for k, v in contracts.items() if v == "CHANGED"]
    degraded = []
    for name, meta in (payload.get("sources") or {}).items():
        for ep, st in (meta.get("endpoints") or {}).items():
            if not st.get("ok"):
                degraded.append(f"{name}/{ep}")
    print(f"  快照 {len(payload.get('records') or [])} 条")
    if changed:
        print(f"  ⚠️  契约变化需人工核对：{', '.join(changed)}")
    if degraded:
        print(f"  ⚠️  降级端点（不影响其余）：{', '.join(degraded)}")
    return EXIT_OK


def run_score(root: Path, include: str, top: int) -> tuple[int, dict | None, str]:
    """Run the sibling topic-scout. Returns (exit_code, data_or_None, note)."""
    scout_dir = sibling_skill("topic-scout")
    if not scout_dir:
        return EXIT_OK, None, "topic-scout 未安装 → 只采集，不打分"
    print("\n=== 2/3 打分（topic-scout）===")
    cmd = [sys.executable, str(scout_dir / "scripts" / "scout.py"), "score",
           "--data-root", str(root), "--top", str(top), "--include", include]
    env = dict(os.environ)
    # 把用户级环境变量带进来（新进程可能没继承）
    for var in ("YOUTUBE_API_KEY", "LFO_HOTSPOT_DATA", "YOUTUBE_API_QUERY"):
        if var not in env:
            if os.name == "nt":
                try:
                    import winreg

                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                        val, _ = winreg.QueryValueEx(k, var)
                        if val:
                            env[var] = val
                except Exception:  # noqa: BLE001
                    pass
            else:
                val = os.popen(f"printenv {var}").read().strip()
                if val:
                    env[var] = val
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env)
    if proc.returncode != 0:
        print(f"  ❌ 打分失败（exit {proc.returncode}）")
        err = (proc.stderr or proc.stdout or "").strip().splitlines()
        if err:
            print("     " + err[-1][:160])
        return proc.returncode, None, "打分失败"
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print("  ❌ 打分输出不是 JSON")
        return EXIT_FAIL, None, "打分输出异常"
    print(f"  候选 {len(data.get('candidates') or [])} 个"
          f"（口径 {data.get('scoring_version')}，快照 {data.get('snapshots_used')} 份）")
    return EXIT_OK, data, "ok"


def report(data: dict | None, limit: int = 8) -> None:
    print("\n=== 3/3 今日选题建议 ===")
    if not data or not data.get("candidates"):
        print("  没有候选（快照不足或赛道过滤后为空）")
        return
    cands = data["candidates"][:limit]
    hdr = f"{'候选':44s} {'总分':>6s}  {'S1':>5s} {'S2':>5s} {'S3':>5s} {'S4':>5s} {'S5':>5s}  平台"
    print(hdr)
    print("-" * len(hdr))
    for c in cands:
        s = c["signals"]
        print(f"{c['keyword'][:42]:44s} {c['total']:6.1f}  "
              f"{s['s1_velocity']:5.1f} {s['s2_days']:5.1f} {s['s3_climb']:5.1f} "
              f"{s['s4_cross']:5.1f} {s['s5_gap']:5.1f}  {','.join(c['platforms'])}")
    print()
    # 哪些信号真的在起作用（避免把空转的权重当成判断依据）
    nz = {k: sum(1 for c in data["candidates"] if c["signals"].get(k, 0) > 0)
          for k in ("s1_velocity", "s2_days", "s3_climb", "s4_cross", "s5_gap")}
    print("信号命中数 S1..S5:", nz, f"（共 {len(data['candidates'])} 个候选）")
    topics = data.get("topics") or []
    if topics:
        print()
        print("=== 话题簇（讲同一话题的候选聚在一起；簇大 = 越多创作者在跟）===")
        for t_ in topics[:8]:
            cross = "  ← 跨平台" if t_["cross_platform"] > 1 else ""
            print(f"  ×{t_['size']:<3d} 平台={','.join(t_['platforms']):<18s} "
                  f"最高分={t_['best_total']:5.1f} 最高播放={t_['max_heat']:>10,}  "
                  f"{t_['best_keyword'][:40]}{cross}")
    dead = [k for k, v in nz.items() if v == 0]
    if dead:
        print(f"⚠️  这些信号本轮为空，不要当成「判断为 0」来读：{', '.join(dead)}")
    print()
    print("下一步：对前 2–3 个候选各跑一张选题卡")
    print("  python ../topic-scout/scripts/scout.py card \"<候选里的关键词片段>\"")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", type=Path, default=None)
    ap.add_argument("--include", default=DEFAULT_INCLUDE, help="赛道过滤，逗号分隔")
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--no-collect", action="store_true", help="跳过采集，只打分")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    hydrate_user_env()   # 让用户级 env 立刻生效，不必重启终端
    root = resolve_data_root(args.data_root)
    print(f"{version_line()}  ·  数据根目录 {root}\n")

    if not args.no_collect:
        rc = run_collect(root)
        if rc != EXIT_OK:
            return rc

    rc, data, note = run_score(root, args.include, args.top)
    if args.json:
        print(json.dumps({"skill": "hot-collect", "data_root": str(root),
                          "note": note, "candidates": (data or {}).get("candidates", [])},
                         ensure_ascii=False, indent=1))
    else:
        report(data, args.top)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

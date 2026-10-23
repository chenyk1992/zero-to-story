#!/usr/bin/env python3
"""hot-collect doctor · 一条命令验完整条链路是否就绪。

为什么需要它：这套链路要能搬到别的机器 / 别的项目上。搬过去最容易坏的不是代码，
是**环境**：缺依赖、缺凭据、数据根目录没权限、语料没同步、兄弟 skill 没装。
doctor 把这些一次性查完，并给出可直接粘贴的修复命令。

    python doctor.py                # 全查（含联网探活）
    python doctor.py --offline      # 不联网
    python doctor.py --json         # 机器可读

退出码（与本 skill 其他脚本统一）
  0  可用        - 主链路能跑（可能有降级项，用 --strict 让降级也非零）
  1  判定失败    - 这次检查没通过 / 结果不合格
  2  环境未就绪  - 跑不起来：缺依赖、缺凭据、数据根不可写
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from _common import (EXIT_ENV, EXIT_FAIL, EXIT_OK, OPTIONAL_DEPS,  # noqa: E402
                     SKILL_VERSION, have, resolve_data_root, sibling_skill,
                     version_line)

OK = "ok"
WARN = "warn"
BLOCK = "block"


def _user_scope_env(name: str) -> str | None:
    """Read a USER-scope environment variable (Windows registry) if present.

    A user-scope var set with setx does NOT reach already-running processes.
    Without this lookup the doctor would report "not configured" for a var
    that is actually configured - the single most common false alarm when
    moving this skill to another machine.
    """
    if os.name != "nt":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            val, _ = winreg.QueryValueEx(k, name)
            return val or None
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", type=Path, default=None)
    ap.add_argument("--offline", action="store_true", help="跳过联网探活")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--strict", action="store_true", help="有降级项也返回非零")
    args = ap.parse_args()

    checks: list[dict] = []

    def add(name: str, status: str, detail: str, fix: str = "") -> None:
        checks.append({"name": name, "status": status, "detail": detail, "fix": fix})

    # --- 运行环境 -----------------------------------------------------------
    py_ok = sys.version_info >= (3, 10)
    add("Python 版本", OK if py_ok else BLOCK,
        f"{sys.version.split()[0]} (需要 ≥3.10)",
        "" if py_ok else "换用 Python 3.10+")

    # --- 依赖 ---------------------------------------------------------------
    core = ["json", "urllib.request", "xml.etree.ElementTree", "sqlite3"]
    missing_core = [m for m in core if not have(m)]
    add("核心依赖（标准库）", OK if not missing_core else BLOCK,
        "齐备" if not missing_core else f"缺 {missing_core}")

    opt_missing = [name for name, (mod, _) in OPTIONAL_DEPS.items() if not have(mod)]
    if opt_missing:
        add("可选依赖（TikTok 对标面）", WARN,
            f"缺 {', '.join(opt_missing)} → 只有 TikTok 对标面不可用，主链路不受影响",
            "python -m pip install " + " ".join(opt_missing))
    else:
        add("可选依赖（TikTok 对标面）", OK, "pyarrow / pandas 齐备")

    # --- 凭据 ---------------------------------------------------------------
    # 注意：用户级环境变量（setx / .zshrc）不会进已经开着的进程。
    # 只看 os.environ 会把「配了但没重启进程」误报成「没配」——这正是迁移时
    # 最常见的坑，所以这里额外读一次用户级作用域。
    key = os.environ.get("YOUTUBE_API_KEY")
    if key:
        add("YOUTUBE_API_KEY", OK, "已设置（当前进程可见）")
    else:
        user_key = _user_scope_env("YOUTUBE_API_KEY")
        if user_key:
            add("YOUTUBE_API_KEY", WARN,
                "用户级已设置，但当前进程没有继承 → **重启终端 / 定时任务进程后生效**；"
                "本次运行会跳过该层（并明确报告）",
                "重开终端；或在本次会话里先执行 "
                "$env:YOUTUBE_API_KEY=[Environment]::GetEnvironmentVariable('YOUTUBE_API_KEY','User')")
        else:
            add("YOUTUBE_API_KEY", WARN,
                "未设置 → YouTube「近 7 天高播放新视频」层会被跳过并明确报告",
                "[Environment]::SetEnvironmentVariable('YOUTUBE_API_KEY','<key>','User')")
    q = os.environ.get("YOUTUBE_API_QUERY")
    add("YOUTUBE_API_QUERY", OK,
        q or "未设置 → 用默认 AI|LLM|agent|GPT|Claude")

    # --- 数据根目录 ---------------------------------------------------------
    root = resolve_data_root(args.data_root)
    writable = True
    detail = str(root)
    fix = ""
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".doctor-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception as exc:  # noqa: BLE001
        writable = False
        detail = f"{root} 不可写：{exc}"
        fix = "用 --data-root 指定可写目录，或设置 LFO_HOTSPOT_DATA"
    add("数据根目录", OK if writable else BLOCK, detail, fix)

    # --- 快照库 -------------------------------------------------------------
    # 只数活库 root/snapshots。**不要**用 root.rglob("snapshots/*/*.json")：
    # 那会把 regression/snapshots 里冻结的副本也数进来，虚报一倍。
    live_root = root / "snapshots"
    snaps = sorted(live_root.rglob("*.json")) if live_root.exists() else []
    n = len(snaps)
    frozen = len(list((root / "regression" / "snapshots").rglob("*.json"))) \
        if (root / "regression" / "snapshots").exists() else 0
    if n == 0:
        add("快照库", WARN, "0 份 → 趋势信号（S1/S3/S2）需要至少两份快照",
            "python collect.py --collect")
    elif n < 30:
        add("快照库", WARN, f"{n} 份（回归门禁要求 30 份）",
            "继续每天 collect.py --collect，到 30 份后跑 regress.py --freeze")
    else:
        add("快照库", OK, f"{n} 份")
    if frozen:
        add("冻结回归集副本", OK, f"{frozen} 份（不计入活库）")

    # --- 契约指纹 -----------------------------------------------------------
    contracts = sorted((root / "contracts").glob("*.json")) if writable else []
    add("端点契约指纹", OK if contracts else WARN,
        f"{len(contracts)} 个端点" if contracts else "还没有 → 先跑一次 collect.py --collect")

    # --- 回归装置 -----------------------------------------------------------
    reg = root / "regression"
    man = reg / "manifest.json"
    baselines = sorted(reg.glob("baseline-*.json")) if reg.exists() else []
    if man.exists():
        try:
            m = json.loads(man.read_text(encoding="utf-8"))
            add("冻结回归集", OK, f"{m.get('actual_count')}/{m.get('target_count')} 份（{man}）",
                "" if m.get("actual_count", 0) >= 30 else "快照满 30 后重跑 regress.py --freeze")
        except Exception:  # noqa: BLE001
            add("冻结回归集", WARN, f"{man} 读不出来")
    else:
        add("冻结回归集", WARN, "没有冻结（回归装置在 topic-scout/scripts/regress.py）")
    add("口径基线", OK if baselines else WARN,
        ", ".join(b.name for b in baselines) if baselines else "没有基线 → regress.py --make-baseline")

    # --- TikTok 语料 --------------------------------------------------------
    corpus = sorted((root / "corpora" / "tiktok").glob("*.parquet")) if writable else []
    add("TikTok 语料", OK if corpus else WARN,
        ", ".join(f"{c.name} ({c.stat().st_size/1e6:.0f}MB)" for c in corpus)
        if corpus else "没有语料（TikTok 对标面不可用，不影响主链路）",
        "" if corpus else "python tiktok_bench.py sync --months 1")

    # --- 兄弟 skill ---------------------------------------------------------
    scout = sibling_skill("topic-scout")
    add("兄弟 skill topic-scout", OK if scout else WARN,
        str(scout) if scout else "没找到 → 选题打分与回归装置不可用",
        "" if scout else "把 topic-scout/ 放到与 hot-collect/ 同级目录")

    # --- 联网探活 -----------------------------------------------------------
    if not args.offline:
        try:
            from adapters import ADAPTERS
            for name, adapter in ADAPTERS.items():
                try:
                    ok, note = adapter.probe()
                except Exception as exc:  # noqa: BLE001
                    ok, note = False, f"probe 异常：{str(exc)[:80]}"
                add(f"源连通性 · {name}", OK if ok else WARN, note)
        except Exception as exc:  # noqa: BLE001
            add("源连通性", WARN, f"无法探活：{str(exc)[:100]}")
    else:
        add("源连通性", OK, "已跳过（--offline）")

    # --- 输出 ---------------------------------------------------------------
    blocked = [c for c in checks if c["status"] == BLOCK]
    warned = [c for c in checks if c["status"] == WARN]

    if args.json:
        print(json.dumps({
            "skill": "hot-collect",
            "version": SKILL_VERSION,
            "data_root": str(root),
            "checks": checks,
            "blocked": len(blocked),
            "warned": len(warned),
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
            print("❌ 环境未就绪，先修上面的阻塞项")
        elif warned:
            print("⚠️  可用，但有降级项（不影响主链路；--strict 可让降级也非零）")
        else:
            print("✅ 全部就绪")

    if blocked:
        return EXIT_ENV
    if warned and args.strict:
        return EXIT_FAIL
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())

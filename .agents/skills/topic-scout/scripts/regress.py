#!/usr/bin/env python3
"""Scoring regression harness for topic-scout.

Why this exists: the project rule is "a change to the scoring logic must bump
the version and pass a regression over 30 historical snapshots". Without a
runnable harness that rule is a wish, not a gate.

What it does
  1. Scores a FROZEN snapshot set under a named "profile" (a口径档案).
  2. Either writes a baseline (--make-baseline) or compares the current run
     against a stored baseline (--compare).
  3. Checks the invariants that must hold for any口径 change, and exits
     non-zero when one is broken.

Profiles
  v1  keywords only                        (before YouTube titles were candidates)
  v2  keywords + youtube_highview          (current shipping口径)
  v3  not implemented yet                  (entity merge for S4 + ai-news heat)

Usage
    python regress.py --make-baseline --profile v2
    python regress.py --compare --profile v1 --baseline baseline-v1.json
    python regress.py --compare --profile v2 --baseline baseline-v2.json

The frozen snapshot set lives at <data-root>/regression/snapshots/ and is
described by <data-root>/regression/manifest.json (file list + sha256).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import scout  # noqa: E402
from _common import resolve_data_root, version_line  # noqa: E402

APP_DIR_NAME = "zero-to-story"
DIR_NAME = "hotspot"

# 口径档案：每个档案 = 一组 score() 参数 + 它对下游的承诺
#
# 关键语义：判据取 **基线那一版** 的承诺（before 的档案），不是新版本的。
# 因为我们要问的问题是「新的口径有没有打破旧口径已经许下的保证」，
# 而不是「新版本自己跟自己比」。
PROFILES = {
    "v1": {
        "candidate_sources": ["keywords"],
        "dedup": False,
        "expect": {
            "signal_names": ["s1_velocity", "s2_days", "s3_climb", "s4_cross", "s5_gap"],
            # v1 是历史口径，没有对外承诺 → 阈值放松，只做「不许悄悄变形」的底线
            "max_rank_shift": 999,
            "max_total_delta": 999.0,
            "min_candidate_ratio": 0.5,
            "max_candidate_ratio": 3.0,
        },
    },
    "v2": {
        "candidate_sources": ["keywords", "youtube_highview"],
        "dedup": False,
        "expect": {
            "signal_names": ["s1_velocity", "s2_days", "s3_climb", "s4_cross", "s5_gap"],
            # v2 是当前在用的口径，它对下游承诺了这些 → 门槛要写死，不能留占位
            "max_rank_shift": 2,        # 同一个 top10 里换位的候选不超过 2 个
            "max_total_delta": 40.0,    # 单候选总分变化不超过 40 分
            "min_candidate_ratio": 0.8,  # 候选数不许塌缩 20%
            "max_candidate_ratio": 1.25, # 也不许暴涨 25%（防口径大改混过检查）
            "min_s1_hits": 1,           # S1 必须在跑（v2 的核心增量）
            "min_s4_hits": 0,           # S4 当前恒 0，不作为承诺；v3 才要求点亮
        },
    },
    "v3": {
        "candidate_sources": ["keywords", "youtube_highview"],
        "dedup": True,
        "expect": {
            "signal_names": ["s1_velocity", "s2_days", "s3_climb", "s4_cross", "s5_gap"],
            # v3 的额外承诺（实体归并 + ai-news 热度落地后启用）：
            #   min_s4_hits = 1        S4 必须真的点亮（当前恒 0）
            #   min_s1_hits 中文侧生效  由具体实现再定
            "max_rank_shift": 2,
            "max_total_delta": 40.0,
            "min_candidate_ratio": 0.8,
            "max_candidate_ratio": 1.25,
            "min_s4_hits": 1,
        },
    },
}


def default_data_root() -> Path:
    return resolve_data_root(None)


def regression_dir(root: Path) -> Path:
    return root / "regression"


def frozen_snapshots(root: Path) -> Path:
    return regression_dir(root) / "snapshots"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_profile(root: Path, profile: str, top: int, include: list[str],
                snapshots_dir: Path | None = None) -> dict:
    """Score the frozen set under one profile."""
    if profile not in PROFILES:
        raise SystemExit(f"未知档案 {profile}，可用：{sorted(PROFILES)}")
    spec = PROFILES[profile]
    data = scout.score(
        root,
        top=top,
        supply_search=0,           # 回归不查 B 站：外部状态会变，回归必须可复现
        include=include or None,
        exclude=None,
        platforms=None,
        candidate_sources=spec["candidate_sources"],
        snapshots_dir=snapshots_dir or frozen_snapshots(root),
        dedup=spec.get("dedup", False),
    )
    data["_profile"] = profile
    return data


def summarize(data: dict) -> dict:
    cands = data["candidates"]
    sig_names = sorted({k for c in cands for k in c["signals"]})
    return {
        "profile": data.get("_profile"),
        "scoring_version": data.get("scoring_version"),
        "snapshots_used": data.get("snapshots_used"),
        "candidate_count": len(cands),
        "signal_names": sig_names,
        "s1_hits": sum(1 for c in cands if c["signals"].get("s1_velocity", 0) > 0),
        "s2_hits": sum(1 for c in cands if c["signals"].get("s2_days", 0) > 0),
        "s3_hits": sum(1 for c in cands if c["signals"].get("s3_climb", 0) > 0),
        "s4_hits": sum(1 for c in cands if c["signals"].get("s4_cross", 0) > 0),
        "s5_hits": sum(1 for c in cands if c["signals"].get("s5_gap", 0) > 0),
        "candidates": [
            {
                "keyword": c["keyword"],
                "total": c["total"],
                "platforms": c["platforms"],
                "days_on": c.get("days_on"),
                "signals": c["signals"],
            }
            for c in cands
        ],
    }


def check(before: dict, after: dict, spec: dict) -> list[tuple[str, bool, str]]:
    exp = spec["expect"]
    checks: list[tuple[str, bool, str]] = []

    # 1. 信号集合不得变（不许偷偷加第六个信号）
    names_ok = set(after["signal_names"]) <= set(exp["signal_names"])
    checks.append((
        "信号集合未扩大",
        names_ok,
        f"after={after['signal_names']} 允许={exp['signal_names']}",
    ))

    # 2. 候选数：既不许塌缩，也不许暴涨（暴涨通常是口径大改混过检查）
    #    计数从候选列表现算，不信任基线里存的元数据字段——否则一个被手改坏的
    #    基线可以靠"candidate_count 还是 30"混过这一条。
    bc, ac = len(before["candidates"]), len(after["candidates"])
    ratio = (ac / bc) if bc else 1.0
    lo, hi = exp["min_candidate_ratio"], exp.get("max_candidate_ratio", 99.0)
    checks.append((
        "候选数在区间内",
        lo <= ratio <= hi,
        f"{bc} -> {ac} (ratio {ratio:.2f}, 允许 {lo}~{hi})",
    ))

    # 3. 排名位移
    b_rank = {c["keyword"]: i for i, c in enumerate(before["candidates"])}
    a_rank = {c["keyword"]: i for i, c in enumerate(after["candidates"])}
    shared = set(b_rank) & set(a_rank)
    shifts = [(k, b_rank[k], a_rank[k]) for k in shared if abs(b_rank[k] - a_rank[k]) > 0]
    big = [s for s in shifts if abs(s[1] - s[2]) > 5]
    checks.append((
        "排名位移在阈值内",
        len(big) <= exp["max_rank_shift"],
        f"共有候选 {len(shared)}, 位移>5 名的 {len(big)} 个 (上限 {exp['max_rank_shift']}): "
        + ", ".join(f"{k[:28]}:{s}->{a}" for k, s, a in big[:5]),
    ))

    # 4. 单候选总分变化
    b_total = {c["keyword"]: c["total"] for c in before["candidates"]}
    a_total = {c["keyword"]: c["total"] for c in after["candidates"]}
    deltas = {k: round(a_total[k] - b_total[k], 2) for k in set(b_total) & set(a_total)}
    worst = sorted(deltas.items(), key=lambda kv: -abs(kv[1]))[:5]
    over = {k: v for k, v in deltas.items() if abs(v) > exp["max_total_delta"]}
    checks.append((
        "单候选总分变化在阈值内",
        not over,
        f"超阈值的 {len(over)} 个: " + ", ".join(f"{k[:24]}={v}" for k, v in worst)
        + f" (阈值 {exp['max_total_delta']})",
    ))

    # 5. 目标信号必须真的被点亮
    if "min_s4_hits" in exp:
        checks.append((
            "S4 跨平台被点亮",
            after["s4_hits"] >= exp["min_s4_hits"],
            f"s4_hits={after['s4_hits']} (下限 {exp['min_s4_hits']})",
        ))
    if "min_s1_hits" in exp:
        checks.append((
            "S1 增速在跑",
            after["s1_hits"] >= exp["min_s1_hits"],
            f"s1_hits={after['s1_hits']} (下限 {exp['min_s1_hits']})",
        ))

    # 6. 快照集必须真的被用到
    checks.append((
        "回归集非空",
        after.get("snapshots_used", 0) > 0,
        f"snapshots_used={after.get('snapshots_used')}",
    ))
    return checks


def report(before: dict, after: dict) -> str:
    lines = []
    lines.append(f"before: {before['profile']}  候选 {before['candidate_count']}  "
                 f"快照 {before['snapshots_used']}  "
                 f"S1..S5 命中 {before['s1_hits']}/{before['s2_hits']}/{before['s3_hits']}/"
                 f"{before['s4_hits']}/{before['s5_hits']}")
    lines.append(f"after : {after['profile']}  候选 {after['candidate_count']}  "
                 f"快照 {after['snapshots_used']}  "
                 f"S1..S5 命中 {after['s1_hits']}/{after['s2_hits']}/{after['s3_hits']}/"
                 f"{after['s4_hits']}/{after['s5_hits']}")
    lines.append("")
    b_rank = {c["keyword"]: i for i, c in enumerate(before["candidates"])}
    a_rank = {c["keyword"]: i for i, c in enumerate(after["candidates"])}
    b_total = {c["keyword"]: c["total"] for c in before["candidates"]}
    lines.append(f"{'候选':40s} {'before':>7s} {'after':>7s} {'Δ':>7s}  {'名次':>10s}")
    lines.append("-" * 80)
    for c in after["candidates"][:15]:
        k = c["keyword"]
        bt = b_total.get(k)
        at = c["total"]
        d = f"{at - bt:+.1f}" if bt is not None else "  new"
        rk = f"{b_rank[k]+1}->{a_rank[k]+1}" if k in b_rank else "new->" + str(a_rank[k] + 1)
        lines.append(f"{k[:38]:40s} {str(bt):>7s} {at:7.1f} {d:>7s}  {rk:>10s}")
    return "\n".join(lines)


def freeze(root: Path, limit: int = 30) -> int:
    """Freeze the current snapshot library into the regression set.

    Copies (not links) the snapshots and writes a manifest with a sha256 per
    file, so the regression set cannot drift when the live library grows.
    """
    live = root / "snapshots"
    if not live.exists():
        raise SystemExit(f"没有快照库：{live}")
    files = sorted(live.rglob("*.json"))
    if len(files) < limit:
        print(f"⚠️ 快照只有 {len(files)} 份，少于目标 {limit} 份 → 仍然冻结，但回归集不满员")
    files = files[-limit:]
    rdir = regression_dir(root)
    fsnap = rdir / "snapshots"
    if fsnap.exists():
        for old in fsnap.rglob("*.json"):
            old.unlink()
    fsnap.mkdir(parents=True, exist_ok=True)
    entries = []
    for f in files:
        rel = f.relative_to(live)
        dest = fsnap / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(f.read_bytes())
        entries.append({
            "path": str(rel).replace("\\", "/"),
            "sha256": sha256(dest),
            "bytes": dest.stat().st_size,
            "collected_at": json.loads(dest.read_text(encoding="utf-8")).get("collected_at"),
        })
    manifest = {
        "frozen_at": __import__("datetime").datetime.now().isoformat(),
        "target_count": limit,
        "actual_count": len(entries),
        "source": "live snapshot library (copied)",
        "files": entries,
    }
    (rdir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"冻结完成: {len(entries)} 份 -> {fsnap}")
    print(f"清单: {rdir / 'manifest.json'}")
    for e in entries:
        print(f"  {e['path']}  {e['bytes']:>8,}B  {e['sha256'][:12]}")
    return 0


def verify_dedup(root: Path, include: list[str]) -> tuple[bool, list[tuple[str, bool, str]]]:
    """Prove the near-duplicate merge LOSSLESS.

    The merge exists to stop one story from occupying several rank slots. The
    obvious risk is the opposite: that merging swallows a genuinely different
    topic. So this checks the strong property, not a proxy:

      every candidate that existed before the merge is still present after it -
      either as itself, or listed inside a merged group's `merged_from`.

    plus: untouched candidates must be byte-identical, and the count identity
    must hold (before == after + absorbed).
    """
    checks: list[tuple[str, bool, str]] = []

    before = scout.score(root, top=9999, supply_search=0, include=include or None,
                         dedup=False)
    after = scout.score(root, top=9999, supply_search=0, include=include or None,
                        dedup=True)
    a = before["candidates"]
    b = after["candidates"]

    a_map = {c["keyword"]: c for c in a}
    surviving: set[str] = set()
    merged_candidates = 0
    for c in b:
        if c.get("merged_count", 1) > 1:
            merged_candidates += 1
            for m in c.get("merged_from", []):
                surviving.add(m["keyword"])
        else:
            surviving.add(c["keyword"])

    missing = set(a_map) - surviving
    checks.append((
        "没有候选被丢掉",
        not missing,
        f"合并前 {len(a)} 个，合并后 {len(b)} 个；"
        f"消失的候选: {sorted(missing)[:5] or '无'}"
        + (f"（共 {len(missing)} 个）" if missing else ""),
    ))

    # 未被合并的候选必须逐字段不变
    changed = []
    for c in b:
        if c.get("merged_count", 1) > 1:
            continue
        src = a_map.get(c["keyword"])
        if not src:
            continue
        for field in ("total", "signals", "platforms", "rank", "max_heat", "days_on"):
            if src.get(field) != c.get(field):
                changed.append((c["keyword"][:34], field, src.get(field), c.get(field)))
    checks.append((
        "未被合并的候选逐字段不变",
        not changed,
        f"变动 {len(changed)} 处: {changed[:3]}" if changed else "0 处变动",
    ))

    # 计数恒等式
    absorbed = after.get("dedup", {}).get("absorbed", 0)
    checks.append((
        "计数恒等式 before == after + absorbed",
        len(a) == len(b) + absorbed,
        f"{len(a)} == {len(b)} + {absorbed}",
    ))

    # 合并组必须完整保留每个成员（含代表本身）
    bad_groups = []
    for c in b:
        if c.get("merged_count", 1) <= 1:
            continue
        members = [m["keyword"] for m in c.get("merged_from", [])]
        if len(members) != c["merged_count"] or c["keyword"] not in members:
            bad_groups.append(c["keyword"][:34])
        if len(set(members)) != len(members):
            bad_groups.append(c["keyword"][:34] + "(重复成员)")
    checks.append((
        "每个合并组完整保留全部成员",
        not bad_groups,
        f"异常组: {bad_groups[:3]}" if bad_groups else "全部完整",
    ))

    # 合并组必须有共同短语（不能只靠相似度阈值）
    no_phrase = []
    for c in b:
        if c.get("merged_count", 1) <= 1:
            continue
        members = [m["keyword"] for m in c.get("merged_from", [])]
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                if not scout._same_story(members[i], members[j]):
                    no_phrase.append((members[i][:24], members[j][:24]))
    checks.append((
        "合并依据是共同短语（不是相似度阈值）",
        not no_phrase,
        f"缺短语证据: {no_phrase[:3]}" if no_phrase else "每对都有共同短语",
    ))

    return not any(not ok for _, ok, _ in checks), checks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-root", type=Path, default=None)
    ap.add_argument("--profile", default="v2")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--include", default="", help="赛道过滤，逗号分隔")
    ap.add_argument("--freeze", action="store_true", help="把当前快照库冻结成回归集")
    ap.add_argument("--make-baseline", action="store_true")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--verify-dedup", action="store_true",
                    help="证明近重复合并不丢数据（用冻结回归集，可随 skill 迁移）")
    ap.add_argument("--baseline", type=Path, default=None)
    ap.add_argument("--version", action="version", version=version_line())
    args = ap.parse_args()

    root = args.data_root.expanduser().resolve() if args.data_root else default_data_root()
    if args.freeze:
        return freeze(root)
    rdir = regression_dir(root)
    fsnap = frozen_snapshots(root)
    if not fsnap.exists():
        raise SystemExit(
            f"没有冻结回归集：{fsnap}\n"
            f"先跑：python regress.py --freeze   （把快照库当前内容冻结成回归集）"
        )
    include = [x.strip() for x in args.include.split(",") if x.strip()]

    if args.verify_dedup:
        include = [x.strip() for x in args.include.split(",") if x.strip()]
        ok, checks = verify_dedup(root, include)
        print("=== 去重无损性检查（冻结回归集）===")
        for name, good, detail in checks:
            print(f"  {'✅' if good else '❌'} {name}: {detail}")
        print()
        print("✅ 通过：合并没有丢任何候选" if ok else "❌ 未通过：合并丢了候选")
        return 0 if ok else 1

    after = summarize(run_profile(root, args.profile, args.top, include))

    if args.make_baseline:
        out = args.baseline or (rdir / f"baseline-{args.profile}.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(after, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"基线已写入: {out}")
        print(report(after, after))
        return 0

    if not args.compare:
        print(report(after, after))
        return 0

    base_path = args.baseline or (rdir / f"baseline-{args.profile}.json")
    if not base_path.exists():
        raise SystemExit(f"没有基线文件：{base_path}")
    before = json.loads(base_path.read_text(encoding="utf-8"))
    # 判据取【基线那一版】的承诺：要问的是「新口径有没有打破旧口径的保证」，
    # 不是「新版本自己跟自己比」。用 after 的档案 = 用新口径给自己发通行证。
    base_profile = before.get("profile") or "v2"
    spec = PROFILES[base_profile]

    print(report(before, after))
    print()
    print("=== 判据（基线口径 " + base_profile + " 的承诺）===")
    checks = check(before, after, spec)

    # 7. 确定性：同一档案跑两次必须完全一致，否则回归不可复现
    again = summarize(run_profile(root, args.profile, args.top, include))
    det_ok = json.dumps(again, sort_keys=True, ensure_ascii=False) == \
        json.dumps(after, sort_keys=True, ensure_ascii=False)
    checks.append((
        "两次运行结果一致（确定性）",
        det_ok,
        "一致" if det_ok else "不一致 → 打分里有非确定性（排序/时间/浮点）",
    ))

    failed = 0
    for name, ok, detail in checks:
        print(f"  {'✅' if ok else '❌'} {name}: {detail}")
        if not ok:
            failed += 1
    print()
    if failed:
        print(f"❌ 回归未通过：{failed}/{len(checks)} 条判据失败 → 不允许合并本次口径变更")
        return 1
    print(f"✅ 回归通过：{len(checks)}/{len(checks)} 条判据满足")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

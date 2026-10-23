#!/usr/bin/env python3
"""Collect hotspot snapshots from the free / legal sources.

    python collect.py --probe                  # 只探活，不写盘
    python collect.py --collect                # 探活 → 拉取 → 落盘快照 → 更新契约指纹
    python collect.py --aggregate              # 从快照重建月度聚合
    python collect.py --collect --data-root D  # 覆盖数据根目录

Data root resolution (first hit wins):
    1. --data-root
    2. env LFO_HOTSPOT_DATA
    3. <user data>/zero-to-story/hotspot      (same parent as canvas/ and video/)

Layout under the data root:
    snapshots/YYYY-MM/HHMM.json   one raw snapshot per run (month partitioned)
    aggregates/YYYY-MM.json        per-keyword monthly rollup (never deleted)
    contracts/<source>.json        response field fingerprint, to detect drift

The data root deliberately lives OUTSIDE the project workspace so these
snapshots can never mix with zero-to-story media or outputs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from _common import hydrate_user_env, version_line
from adapters import ADAPTERS  # noqa: E402

APP_DIR_NAME = "zero-to-story"
DIR_NAME = "hotspot"


def default_data_root() -> Path:
    env = os.environ.get("LFO_HOTSPOT_DATA")
    if env:
        return Path(env).expanduser().resolve()
    home = Path.home()
    if os.name == "nt":
        return home / "AppData" / "Local" / APP_DIR_NAME / DIR_NAME
    return home / ".local" / "share" / APP_DIR_NAME / DIR_NAME


def key_fingerprint(payload: Any) -> dict:
    """Field-name fingerprint of a response, used to detect upstream drift."""
    if isinstance(payload, dict):
        return {
            "type": "object",
            "keys": sorted(payload.keys())[:60],
            "item_keys": key_fingerprint(next(iter(payload.values()), None))
            if payload
            else None,
        }
    if isinstance(payload, list):
        item = next((v for v in payload if isinstance(v, (dict, list))), None)
        return {"type": "array", "length": len(payload), "item": key_fingerprint(item)}
    return {"type": type(payload).__name__}


def load_contract(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def write_contract(path: Path, source: str, fp: dict) -> str:
    """Persist the fingerprint; return a status string for the report."""
    old = load_contract(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"source": source, "fingerprint": fp, "checked_at": dt.datetime.now(dt.timezone.utc).isoformat()},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if old is None:
        return "new"
    if old.get("fingerprint") == fp:
        return "same"
    return "CHANGED"


def collect(root: Path) -> dict:
    now = dt.datetime.now()
    sources: dict[str, dict] = {}
    records: list[dict] = []
    contract_status: dict[str, str] = {}

    for name, adapter in ADAPTERS.items():
        ok, note = adapter.probe()
        sources[name] = {"ok": ok, "note": note}
        if not ok:
            print(f"  [skip] {name}: {note}")
            continue
        try:
            rows = adapter.fetch()
        except Exception as exc:  # noqa: BLE001
            sources[name] = {"ok": False, "note": f"fetch failed: {str(exc)[:120]}"}
            print(f"  [fail] {name}: {str(exc)[:120]}")
            continue
        records.extend(rows)
        sources[name]["items"] = len(rows)
        # Endpoint-level failures inside a source must be visible. A source can
        # answer "ok" while half of its endpoints are rate-limited.
        eps = getattr(adapter, "endpoint_status", None) or {}
        fps = getattr(adapter, "endpoint_fingerprints", None) or {}
        for ep, st in eps.items():
            sources[name].setdefault("endpoints", {})[ep] = st
            if not st.get("ok"):
                print(f"        [degraded] {name}/{ep}: {st.get('error') or '空结果'}")
        # A source counts as ok if ANY endpoint delivered. Independent layers
        # inside one source must not be able to veto each other.
        if eps:
            sources[name]["ok"] = sources[name]["ok"] or any(
                st.get("ok") for st in eps.values()
            )
        # Contract fingerprint per ENDPOINT: different endpoints of one source
        # legitimately have different schemas, so a source-level fingerprint
        # would flip every time an endpoint fails and cry wolf.
        for ep, keys in fps.items():
            ep_status = eps.get(ep) or {}
            if not ep_status.get("ok") or not keys:
                # A failed / empty endpoint must NOT overwrite the stored
                # baseline. Otherwise one transient failure (429, RSS hiccup)
                # replaces the contract with an empty fingerprint, and the next
                # healthy run reports a bogus CHANGED - a false alarm that hides
                # the real ones.
                print(f"        [contract skip] {name}/{ep}: 端点本轮失败，保留原指纹基线")
                continue
            result = write_contract(
                root / "contracts" / f"{name}__{ep}.json", f"{name}/{ep}", {"item_keys": keys}
            )
            contract_status[f"{name}/{ep}"] = result
            if result == "CHANGED":
                print(f"        [contract CHANGED] {name}/{ep}: 上游字段可能改了，需人工核对")
        # The probe note describes the source BEFORE fetching; report what each
        # endpoint actually delivered so a partial fetch is not mislabelled.
        # The probe note is kept only when something actually failed - otherwise
        # it can contradict the outcome ("RSS 不可用" while the retry then
        # fetched 15 items fine).
        parts = [
            f"{ep} {st['items']} 条"
            for ep, st in eps.items()
            if st.get("ok") and "items" in st
        ]
        failed = [
            f"{ep}({st.get('error') or '失败'})"
            for ep, st in eps.items()
            if not st.get("ok")
        ]
        detail = " / ".join(parts) if parts else note
        if failed:
            detail = f"{detail} / 失败: {', '.join(failed)}"
        print(f"  [ok]   {name}: {len(rows)} 条 ({detail})")

    month = now.strftime("%Y-%m")
    snap_dir = root / "snapshots" / month
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_path = snap_dir / f"{now.strftime('%H%M')}.json"
    payload = {
        "collected_at": now.astimezone().isoformat(),
        "sources": sources,
        "contracts": contract_status,
        "records": records,
    }
    snap_path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n快照 -> {snap_path}  ({len(records)} 条记录)")
    return payload


def aggregate(root: Path) -> dict:
    """Rebuild monthly per-keyword rollups from the raw snapshots."""
    agg_dir = root / "aggregates"
    agg_dir.mkdir(parents=True, exist_ok=True)
    months = sorted(p for p in (root / "snapshots").glob("*") if p.is_dir())
    written = []
    for mdir in months:
        month = mdir.name
        stat: dict[str, dict] = defaultdict(
            lambda: {"appear": 0, "best_rank": 999, "max_heat": 0, "platforms": set(), "samples": []}
        )
        for snap in sorted(mdir.glob("*.json")):
            try:
                data = json.loads(snap.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            for r in data.get("records", []):
                if r.get("kind") != "keyword":
                    continue
                k = r.get("keyword")
                if not k:
                    continue
                e = stat[k]
                e["appear"] += 1
                e["best_rank"] = min(e["best_rank"], r.get("rank") or 999)
                e["max_heat"] = max(e["max_heat"], r.get("heat") or 0)
                e["platforms"].add(r.get("platform"))
                if len(e["samples"]) < 3:
                    e["samples"].append({"rank": r.get("rank"), "heat": r.get("heat")})
        out = {
            "month": month,
            "keywords": {
                k: {
                    "appear": v["appear"],
                    "best_rank": None if v["best_rank"] == 999 else v["best_rank"],
                    "max_heat": v["max_heat"],
                    "platforms": sorted(p for p in v["platforms"] if p),
                    "samples": v["samples"],
                }
                for k, v in sorted(stat.items())
            },
        }
        path = agg_dir / f"{month}.json"
        path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        written.append(path.name)
        print(f"  聚合 -> {path.name}  ({len(out['keywords'])} 个词)")
    return {"written": written}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--probe", action="store_true", help="只探活")
    ap.add_argument("--collect", action="store_true", help="采集并落盘")
    ap.add_argument("--aggregate", action="store_true", help="重建月度聚合")
    ap.add_argument("--data-root", type=Path, default=None)
    ap.add_argument("--version", action="version", version=version_line())
    args = ap.parse_args()

    hydrate_user_env()   # 让用户级 env 立刻生效，不必重启终端
    root = args.data_root.expanduser().resolve() if args.data_root else default_data_root()
    root.mkdir(parents=True, exist_ok=True)
    print(f"数据根目录: {root}\n")

    if args.probe:
        print("=== 探活 ===")
        all_ok = True
        for name, adapter in ADAPTERS.items():
            ok, note = adapter.probe()
            all_ok = all_ok and ok
            print(f"  {'✓' if ok else '✗'} {name:<12} {note}")
        print(f"\n可用源 {sum(1 for a in ADAPTERS.values() if a.probe()[0])}/{len(ADAPTERS)}")
        return 0 if all_ok else 1

    if args.aggregate:
        print("=== 月度聚合 ===")
        aggregate(root)
        return 0

    print("=== 采集 ===")
    collect(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

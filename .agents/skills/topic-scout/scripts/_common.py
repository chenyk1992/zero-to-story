"""Shared helpers for the topic-scout skill.

Mirrors hot-collect's `_common.py` on purpose: each skill must keep working
when it is copied to another machine or another project on its own. A
cross-skill import would be a portability bug, not a DRY win.

Exit code contract (same as hot-collect):
  0  ok
  1  failed      - the judgement ran but did not pass (e.g. regression failed)
  2  environment - could not start (missing dependency / unreadable data root)
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

SKILL_NAME = "topic-scout"
SKILL_VERSION = "1.0.0"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_ENV = 2

APP_DIR_NAME = "zero-to-story"
DIR_NAME = "hotspot"

OPTIONAL_DEPS = {
    "pyarrow": ("pyarrow", "读 TikTok 语料（topic-scout 本身不需要）"),
    "pandas": ("pandas", "表格运算（topic-scout 本身不需要）"),
}


def default_data_root() -> Path:
    env = os.environ.get("LFO_HOTSPOT_DATA")
    if env:
        return Path(env).expanduser().resolve()
    home = Path.home()
    if os.name == "nt":
        return home / "AppData" / "Local" / APP_DIR_NAME / DIR_NAME
    return home / ".local" / "share" / APP_DIR_NAME / DIR_NAME


def resolve_data_root(cli_value: Path | None) -> Path:
    return cli_value.expanduser().resolve() if cli_value else default_data_root()


def need(module: str, why: str = "") -> object:
    try:
        return importlib.import_module(module)
    except ImportError:
        hint = why or OPTIONAL_DEPS.get(module, (module, ""))[1]
        print(f"❌ 缺少依赖 {module}（{hint}）", file=sys.stderr)
        print(f"   安装：python -m pip install {module}", file=sys.stderr)
        raise SystemExit(EXIT_ENV)


def have(module: str) -> bool:
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False


def version_line() -> str:
    return f"{SKILL_NAME} {SKILL_VERSION}"


def sibling_skill(name: str) -> Path | None:
    here = Path(__file__).resolve().parent.parent.parent
    cand = here / name
    return cand if (cand / "SKILL.md").exists() else None

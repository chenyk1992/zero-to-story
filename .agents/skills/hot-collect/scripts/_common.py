"""Shared helpers for the hot-collect skill.

Portability rules this module enforces:
  * No absolute paths. The data root is resolved as
      --data-root  >  env LFO_HOTSPOT_DATA  >  <user data>/zero-to-story/hotspot
    and never hard-coded to a drive or a machine.
  * Optional third-party dependencies are imported lazily, so a machine that
    only wants the daily snapshot flow does not need pyarrow/pandas at all,
    and a machine that is missing them gets an actionable message instead of
    a traceback.
  * Exit codes are uniform across every script in this skill, so a caller
    (cron, wrapper, another skill) can branch on them.

Exit code contract
  0  ok                - everything asked for succeeded
  1  failed            - the run happened but the result did not pass
                         (contract drift, regression failed, gate tripped)
  2  environment       - the run could not start: missing dependency,
                         missing credential, unwritable data root
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Iterable

SKILL_NAME = "hot-collect"
SKILL_VERSION = "1.0.0"

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_ENV = 2

APP_DIR_NAME = "zero-to-story"
DIR_NAME = "hotspot"

# Optional dependencies: name -> (import name, what it is needed for)
OPTIONAL_DEPS = {
    "pyarrow": ("pyarrow", "读 TikTok 语料 Parquet（只有 TikTok 对标面需要）"),
    "pandas": ("pandas", "TikTok 语料的表格运算（只有 TikTok 对标面需要）"),
}


def default_data_root() -> Path:
    """Resolve the data root. First hit wins: CLI flag, env var, default."""
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
    """Import an optional dependency, or exit(2) with a fix command.

    Never let a missing optional dependency turn into a traceback: a machine
    that only runs the daily snapshot must not be broken by pyarrow.
    """
    try:
        return importlib.import_module(module)
    except ImportError:
        hint = why or OPTIONAL_DEPS.get(module, (module, ""))[1]
        print(f"❌ 缺少依赖 {module}（{hint}）", file=sys.stderr)
        print(f"   安装：python -m pip install {module}", file=sys.stderr)
        print(f"   或跳过：不用这一层即可（其余功能不受影响）", file=sys.stderr)
        raise SystemExit(EXIT_ENV)


def have(module: str) -> bool:
    try:
        importlib.import_module(module)
        return True
    except ImportError:
        return False


def user_scope_env(name: str) -> str | None:
    """Read a USER-scope environment variable (Windows registry).

    A user-scope var set with setx does NOT reach already-running processes.
    Without this lookup, "配了 key 却说没配置" is the single most common
    false alarm when moving this skill to another machine.
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


def hydrate_user_env(names: Iterable[str] = ()) -> list[str]:
    """Copy USER-scope env vars into this process when they are missing.

    Call it at the start of any entry point so a freshly opened terminal
    (or a scheduled task) behaves the same as the shell where the var was set.
    Returns the names that were hydrated.
    """
    hydrated: list[str] = []
    for name in names or ("YOUTUBE_API_KEY", "LFO_HOTSPOT_DATA", "YOUTUBE_API_QUERY"):
        if os.environ.get(name):
            continue
        val = user_scope_env(name)
        if val:
            os.environ[name] = val
            hydrated.append(name)
    return hydrated


def version_line() -> str:
    return f"{SKILL_NAME} {SKILL_VERSION}"


def sibling_skill(name: str) -> Path | None:
    """Locate a sibling skill by name (../<name>), if it is installed."""
    here = Path(__file__).resolve().parent.parent.parent
    cand = here / name
    return cand if (cand / "SKILL.md").exists() else None

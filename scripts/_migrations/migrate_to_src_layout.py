"""One-off migration: add `lfo.` prefix to internal package imports.

Used to move from flat layout (cli/, core/, services/, ...) to src layout
(src/lfo/cli/, src/lfo/core/, ...). Idempotent — running twice is a no-op.

Run from the project root:
    python scripts/migrate_to_src_layout.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

LFO_PACKAGES = (
    "cli", "core", "services", "visual", "planning", "application",
    "comfy", "config", "environment", "assembly", "rendering",
    "storyboard", "visual_bible",
)

# Match "from <pkg>(.something | import ...)" at the start of a line.
_FROM_RE = re.compile(
    r"^(\s*)from\s+(" + "|".join(LFO_PACKAGES) + r")((?:\s|\.|\b))",
    re.MULTILINE,
)
# Match "import <pkg>(.something | nothing)" at the start of a line.
_IMPORT_RE = re.compile(
    r"^(\s*)import\s+(" + "|".join(LFO_PACKAGES) + r")((?:\s|\.|\b|$))",
    re.MULTILINE,
)

# We only need to rewrite files under tests/, src/, and scripts/. Skip
# virtualenvs, .git, and anything inside an installed package
# (site-packages).
SCAN_DIRS = (Path("src"), Path("tests"), Path("scripts"))
SCAN_EXTRA_FILES = tuple(
    p for p in Path(".").glob("*.py")
    if p.name not in {"setup.py", "conftest.py"}  # conftest handled separately
)


def rewrite_text(text: str) -> tuple[str, int]:
    """Return (new_text, num_replacements)."""
    count = 0

    def _from(m: re.Match) -> str:
        nonlocal count
        count += 1
        indent, pkg, sep = m.group(1), m.group(2), m.group(3)
        return f"{indent}from lfo.{pkg}{sep}"

    def _import(m: re.Match) -> str:
        nonlocal count
        count += 1
        indent, pkg, sep = m.group(1), m.group(2), m.group(3)
        return f"{indent}import lfo.{pkg}{sep}"

    new = _FROM_RE.sub(_from, text)
    new = _IMPORT_RE.sub(_import, new)
    return new, count


def iter_python_files() -> list[Path]:
    files: list[Path] = []
    for d in SCAN_DIRS:
        if d.exists():
            files.extend(d.rglob("*.py"))
    files.extend(SCAN_EXTRA_FILES)
    return files


def main() -> int:
    total_files = 0
    total_replacements = 0
    for path in iter_python_files():
        text = path.read_text(encoding="utf-8")
        new, count = rewrite_text(text)
        if count:
            path.write_text(new, encoding="utf-8")
            total_files += 1
            total_replacements += count
            print(f"  {path}: {count} replacements")
    print(f"\nDone. {total_replacements} replacements in {total_files} files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

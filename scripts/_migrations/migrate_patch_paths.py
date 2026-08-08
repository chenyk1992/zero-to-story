"""One-off: add lfo. prefix to string-based mock paths in tests.

Catches patterns like ``patch("cli.run_cmd.PipelineService")`` that the
import-rewriter script (``migrate_to_src_layout.py``) misses because they
are not import statements — they are string arguments to ``mock.patch``.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

LFO = (
    "cli", "core", "services", "visual", "planning", "application",
    "comfy", "config", "environment", "assembly", "rendering",
    "storyboard", "visual_bible",
)

# Match patch("lfo.cli.xxx...") and patch('lfo.cli.xxx...') and patch(\n  "cli.xxx"
PAT = re.compile(
    r'patch\(\s*(["\'])(?:lfo\.)?(' + '|'.join(LFO) + r')\.',
)


def main() -> int:
    total = 0
    for d in ("tests", "scripts"):
        for p in Path(d).rglob("*.py"):
            text = p.read_text(encoding="utf-8")
            new = PAT.sub(lambda m: f'patch({m.group(1)}lfo.{m.group(2)}.', text)
            if new != text:
                n = sum(1 for _ in PAT.finditer(text))
                p.write_text(new, encoding="utf-8")
                print(f"  {p}: {n} replacements")
                total += n
    print(f"\nDone. {total} replacements.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

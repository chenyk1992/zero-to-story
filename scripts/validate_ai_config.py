"""GPT-6 适配变更说明：校验真实 YAML 与项目指令链接，不模拟模型行为。"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

LINK = re.compile(r"!?\[[^\]\n]*\]\((?:<([^>\n]+)>|([^\s)]+))(?:\s+\"[^\"\n]*\")?\)")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})(.*)$")
ALLOWED_FIELDS = {"name", "description", "license", "allowed-tools", "metadata"}


def prose_lines(text: str) -> list[tuple[int, str]]:
    """Exclude fenced examples, whose sample paths are not live file references."""
    result: list[tuple[int, str]] = []
    marker = ""
    for number, line in enumerate(text.splitlines(), 1):
        fence = FENCE.match(line)
        if fence:
            candidate = fence.group(1)
            if not marker:
                marker = candidate
            elif candidate[0] == marker[0] and len(candidate) >= len(marker) and not fence.group(2).strip():
                marker = ""
            continue
        if not marker:
            result.append((number, line))
    return result


def check_skill(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.DOTALL)
    if not match:
        return [f"{path}: SKILL.md must start with YAML frontmatter"]
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as error:
        return [f"{path}: invalid YAML: {error}"]
    if not isinstance(data, dict):
        return [f"{path}: frontmatter must be a mapping"]
    issues = []
    if set(data) - ALLOWED_FIELDS:
        issues.append(f"{path}: unsupported frontmatter fields: {set(data) - ALLOWED_FIELDS}")
    name = data.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
        issues.append(f"{path}: invalid or missing skill name")
    elif name != path.parent.name:
        issues.append(f"{path}: name must match its directory")
    description = data.get("description")
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        issues.append(f"{path}: description must be a nonempty string of at most 1024 characters")
    return issues


def check_links(path: Path) -> tuple[int, list[str]]:
    """Check inline local Markdown file links; anchors and reference-style links are out of scope."""
    checked = 0
    issues = []
    for number, line in prose_lines(path.read_text(encoding="utf-8")):
        for match in LINK.finditer(line):
            target = match.group(1) or match.group(2)
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            checked += 1
            if not (path.parent / unquote(parsed.path)).exists():
                issues.append(f"{path}:{number}: missing local target: {target}")
    return checked, issues


def validate(root: Path) -> tuple[dict[str, int], list[str]]:
    skills_root = root / ".agents/skills"
    entries = sorted(skills_root.glob("*/SKILL.md"))
    issues = []
    if not entries:
        issues.append(f"{skills_root}: no project skills discovered")
    for path in entries:
        issues.extend(check_skill(path))
    # All skill Markdown supports progressive loading; old eval outputs are data.
    markdown = [root / "AGENTS.md", *sorted((root / "docs").glob("ai-*.md"))]
    for entry in entries:
        markdown.append(entry)
        markdown.extend(sorted((entry.parent / "references").rglob("*.md")))
    links = 0
    for path in markdown:
        if not path.is_file():
            issues.append(f"{path}: required instruction file is missing")
            continue
        count, errors = check_links(path)
        links += count
        issues.extend(errors)
    metadata_files = sorted(skills_root.glob("*/agents/openai.yaml")) + sorted(skills_root.glob("*/meta.yaml"))
    for path in metadata_files:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                issues.append(f"{path}: metadata must be a mapping")
        except yaml.YAMLError as error:
            issues.append(f"{path}: invalid YAML: {error}")
    return {"skills": len(entries), "metadata": len(metadata_files), "markdown": len(markdown), "local_links": links}, issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    counts, issues = validate(args.root.resolve())
    print(", ".join(f"{key}={value}" for key, value in counts.items()))
    for issue in issues:
        print(issue)
    print(f"{'FAIL' if issues else 'PASS'}: {len(issues)} issue(s). Inline file links only; no anchor, remote URL or behavioral validation.")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())

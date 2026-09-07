"""GPT-6 适配变更说明：验证校验器的错误检测及边界，不断言提示词措辞。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/validate_ai_config.py"
SPEC = importlib.util.spec_from_file_location("ai_config_validation", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


@pytest.mark.parametrize("frontmatter", ["- list", "name: [broken", "name: demo\ndescription: 123", "name: other\ndescription: Useful skill"])
def test_rejects_invalid_skill_identity_and_yaml(tmp_path: Path, frontmatter: str) -> None:
    path = tmp_path / "demo/SKILL.md"
    path.parent.mkdir()
    path.write_text(f"---\n{frontmatter}\n---\nBody", encoding="utf-8")
    assert VALIDATOR.check_skill(path)


def test_requires_frontmatter_at_start_and_accepts_multiline_description(tmp_path: Path) -> None:
    path = tmp_path / "demo/SKILL.md"
    path.parent.mkdir()
    text = "---\nname: demo\ndescription: |\n  First line\n  Second line\n---\nBody"
    path.write_text(text, encoding="utf-8")
    assert VALIDATOR.check_skill(path) == []
    path.write_text("Explanation before YAML\n" + text, encoding="utf-8")
    assert VALIDATOR.check_skill(path)


def test_checks_real_relative_links_and_ignores_examples_and_remote_targets(tmp_path: Path) -> None:
    (tmp_path / "target file.md").write_text("Target", encoding="utf-8")
    path = tmp_path / "source.md"
    path.write_text(
        '[ok](<target file.md>) [encoded](target%20file.md#heading)\n'
        '[web](https://example.invalid/missing.md) [anchor](#heading)\n'
        '```markdown\n[sample](not-a-real-file.md)\n```\n'
        '[broken](missing.md)\n', encoding="utf-8",
    )
    count, issues = VALIDATOR.check_links(path)
    assert count == 3
    assert len(issues) == 1
    assert "missing.md" in issues[0]


def test_fails_empty_project_instead_of_reporting_success(tmp_path: Path) -> None:
    counts, issues = VALIDATOR.validate(tmp_path)
    assert counts["skills"] == 0
    assert len(issues) >= 2

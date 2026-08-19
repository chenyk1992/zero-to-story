#!/usr/bin/env python3
"""检查仓库结构、计数、链接、用例编号和元数据是否同步。"""

import html
import json
import re
import subprocess
import sys
import traceback
import types
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "tasks", "assets"}
SKIP_FILES = {"evals/run-manifest.md", "CHANGELOG.md"}

# 每项依次为：文件、捕获计数的 regex、期望值来源、预期命中数。
ANCHORS = (
    ("README.md", r"benchmark-(\d+)%20cases", "total", 1),
    ("README.md", r'alt="Benchmark: (\d+) cases"', "total", 1),
    ("README.md", r"scenario%20samples-(\d+)", "rs", 1),
    ("README.md", r'alt="Scenario samples: (\d+)"', "rs", 1),
    ("README.md", r"^当前评测集共 (\d+) 条：$", "total", 1),
    ("README.md", r"^\| SF \| (\d+) \|", "sf", 1),
    ("README.md", r"^\| SNF \| (\d+) \|", "snf", 1),
    ("README.md", r"^\| 场景样本 \| (\d+) \|", "rs", 1),
    # 冠词随数字读音变（an 84-case / a 95-case），两种都要能匹配
    ("README.md", r"\ban? (\d+)-case benchmark", "total", 1),
    ("evals/run-eval.md", r"^### 对 Should Fix（SF-01 到 SF-(\d+)）：$", "sf", 1),
    ("evals/run-eval.md", r"^### 对 Should NOT Fix（SNF-01 到 SNF-(\d+)）：$", "snf", 1),
    ("evals/run-eval.md", r"^- SF 通过率：X/(\d+)$", "sf", 1),
    ("evals/run-eval.md", r"^- SNF 误杀率：X/(\d+)$", "snf", 1),
    ("evals/run-eval.md", r"^注意：token .*一次跑完 (\d+) 条", "total", 1),
    # 贪婪匹配到最后一个「扩到 N 条。」，扩样本时只改正文不用改这条正则
    ("evals/real-samples.md", r"^> v1\.7\.2 新增.*扩到 (\d+) 条。", "rs", 1),
    ("evals/real-samples.md", r"^\| 数量 \| (\d+) 条，持续扩充 \|", "total", 1),
    ("evals/real-samples.md", r"^\| 数量 \| \d+ 条，持续扩充 \| (\d+) 条，质量优先 \|", "rs", 1),
    ("evals/real-samples.md", r"^> 现在覆盖 .*?(\d+) 条 benchmark。", "total", 1),
    ("evals/real-samples.md", r"^### RS-(20)\b", "rs", 1),
    ("evals/benchmark-blind.md", r"^> 共 (\d+) 条。", "total", 1),
    ("evals/benchmark-map.md", r"^> 共 (\d+) 条 = \d+ SF \+ \d+ SNF。$", "total", 1),
    ("evals/benchmark-map.md", r"^> 共 \d+ 条 = (\d+) SF \+ \d+ SNF。$", "sf", 1),
    ("evals/benchmark-map.md", r"^> 共 \d+ 条 = \d+ SF \+ (\d+) SNF。$", "snf", 1),
    ("automation/eval/README.md", r"^\| `B65-(\d+)` \| B-65 到 B-\1 \|$", "total", 1),
)

CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

LINK_RE = re.compile(r"!?\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^)\s]+)")
HTML_LINK_RE = re.compile(r'(?:href|src)="([^"]+)"')
CASE_ID_RE = re.compile(r"\b(?:SF|SNF|RS)-\d+\b")
FUTURE_ID_RE = re.compile(r"新增从\s+((?:SF|SNF|RS)-\d+)\s+起")


def line_number(text, offset):
    return text.count("\n", 0, offset) + 1


def add_issue(issues, path, line, check_id, message):
    issues.append(f"{path}:{line} [{check_id}] {message}")


def read_text(relative, issues, check_id):
    try:
        return (ROOT / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        add_issue(issues, relative, "-", check_id, f"无法读取：{exc}")
        return None


def check_blind_sync(issues):
    script = ROOT / "automation" / "eval" / "make_blind.py"
    result = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
    if result.returncode:
        for message in output.splitlines() or [f"退出码 {result.returncode}"]:
            add_issue(issues, "automation/eval/make_blind.py", "-", "blind-sync", message)
    elif output:
        print(output)


def check_counts(issues):
    benchmark = read_text("evals/benchmark.md", issues, "counts")
    samples = read_text("evals/real-samples.md", issues, "counts")
    if benchmark is None or samples is None:
        return None, None, None, None, 0

    case_matches = list(re.finditer(r"^### ((SF|SNF)-\d+) \|", benchmark, re.MULTILINE))
    rs_matches = list(re.finditer(r"^#{2,4} (RS-\d+)\b", samples, re.MULTILINE))
    if not case_matches:
        add_issue(issues, "evals/benchmark.md", "-", "counts", "没有解析到 benchmark 用例标题")
    if not rs_matches:
        add_issue(issues, "evals/real-samples.md", "-", "counts", "没有解析到 RS 样本标题")

    sf = sum(match.group(2) == "SF" for match in case_matches)
    snf = len(case_matches) - sf
    expected = {"total": len(case_matches), "sf": sf, "snf": snf, "rs": len(rs_matches)}
    anchor_count = 0
    for relative, pattern, source, expected_hits in ANCHORS:
        text = read_text(relative, issues, "counts")
        if text is None:
            continue
        matches = list(re.finditer(pattern, text, re.MULTILINE))
        if len(matches) != expected_hits:
            line = line_number(text, matches[0].start()) if matches else "-"
            add_issue(
                issues,
                relative,
                line,
                "counts",
                f"锚点失配：{pattern!r} 预期命中 {expected_hits} 次，实际 {len(matches)} 次",
            )
            continue
        anchor_count += len(matches)
        for match in matches:
            actual = int(match.group(1))
            if actual != expected[source]:
                add_issue(
                    issues,
                    relative,
                    line_number(text, match.start()),
                    "counts",
                    f"计数应为 {expected[source]}，实际为 {actual}",
                )
    return case_matches, rs_matches, sf, snf, anchor_count


def markdown_files(issues):
    files = []
    for path in ROOT.rglob("*.md"):
        relative = path.relative_to(ROOT)
        relative_text = relative.as_posix()
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if relative_text in SKIP_FILES or (
            relative.parent.as_posix() == "evals" and relative.name.startswith("results-")
        ):
            continue
        try:
            files.append((relative_text, path.read_text(encoding="utf-8")))
        except (OSError, UnicodeError) as exc:
            add_issue(issues, relative_text, "-", "links", f"无法读取：{exc}")
    return files


def strip_inline_code(line):
    return re.sub(r"(`+)[^`]*?\1", "", line)


def local_target(target):
    target = html.unescape(target.strip())
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    if target.startswith(("http://", "https://", "mailto:", "data:", "#")):
        return None
    return unquote(target.split("#", 1)[0].split("?", 1)[0]) or None


def check_links(files, issues):
    checked = 0
    for relative, text in files:
        source = ROOT / relative
        in_fence = False
        for number, raw_line in enumerate(text.splitlines(), 1):
            if re.match(r"^\s*(```|~~~)", raw_line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            line = strip_inline_code(raw_line)
            targets = [match.group(1) for match in LINK_RE.finditer(line)]
            if relative == "README.md":
                targets += [match.group(1) for match in HTML_LINK_RE.finditer(line)]
            for target in targets:
                path_text = local_target(target)
                if path_text is None:
                    continue
                checked += 1
                destination = source.parent / path_text
                if not destination.exists():
                    add_issue(issues, relative, number, "links", f"相对链接目标不存在：{path_text}")
    return checked


def check_case_ids(files, case_matches, rs_matches, issues):
    if case_matches is None or rs_matches is None:
        return
    valid = {match.group(1) for match in case_matches}
    valid.update(match.group(1) for match in rs_matches)
    for relative, text in files:
        # “新增从 RS-20 起”描述的是下一个可用编号，不是对现有用例的引用。
        future_spans = {match.span(1) for match in FUTURE_ID_RE.finditer(text)}
        for match in CASE_ID_RE.finditer(text):
            if match.span() in future_spans:
                continue
            if match.group(0) not in valid:
                add_issue(
                    issues,
                    relative,
                    line_number(text, match.start()),
                    "case-ids",
                    f"用例编号不存在：{match.group(0)}",
                )


def check_meta(issues):
    skill = read_text("SKILL.md", issues, "meta")
    if skill is not None:
        lines = skill.splitlines()
        if not lines or lines[0] != "---" or "---" not in lines[1:]:
            add_issue(issues, "SKILL.md", 1, "meta", "frontmatter 不存在或未闭合")
        else:
            end = lines[1:].index("---") + 1
            metadata = {}
            for number, line in enumerate(lines[1:end], 2):
                match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
                if match:
                    metadata[match.group(1)] = (match.group(2).strip(), number)
            for key in ("name", "description"):
                value, number = metadata.get(key, ("", 1))
                if not value:
                    add_issue(issues, "SKILL.md", number, "meta", f"frontmatter 的 {key} 不能为空")

    for relative in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"):
        text = read_text(relative, issues, "meta")
        if text is None:
            continue
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            add_issue(issues, relative, exc.lineno, "meta", f"JSON 无法解析：{exc.msg}")


# hard_metrics.py 里的词表是判据的脚本实现，references/structures.md 的正文是同一
# 判据的规则真源。两边各自维护，改一边忘另一边就会静默漂移——v2.3.0 新增的借喻场
# 和名词化空动词都是硬编码在脚本里的枚举，属于高风险项。
# 分级对待：正文明说是完整枚举的（借喻「常见 N 套」、名词化空动词）双向核对；正文
# 按「清单是举例不是边界」写的（连词），只查正文列到的词脚本里有，不反向要求穷举。
def load_hard_metrics(issues):
    """直接编译源码取词表，不走 importlib 的字节码缓存。

    pyc 的失效判定依赖解释器版本与构建配置：timestamp-based 只看「秒级 mtime +
    文件大小」，同秒内的等长修改会被判成没变；hash-based 才看内容。本机 3.14 实测
    改内容即失效，但这是个防漂移的检查，不该把正确性押在 CI 那边的缓存策略上。
    """
    relative = "automation/eval/hard_metrics.py"
    path = ROOT / relative
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        add_issue(issues, relative, "-", "rule-tables", f"无法读取：{exc}")
        return None
    module = types.ModuleType("hard_metrics")
    module.__file__ = str(path)
    try:
        exec(compile(source, str(path), "exec"), module.__dict__)
    except Exception:  # noqa: BLE001 — 加载期任何异常都应报成检查失败
        # 只留最后几行：定位到出错的文件、行号和异常类型，不刷屏
        detail = " | ".join(traceback.format_exc().strip().splitlines()[-3:])
        add_issue(issues, relative, "-", "rule-tables", f"加载失败：{detail}")
        return None
    return module


def rule_section(text, number):
    return re.search(rf"^## {number}\. .*?(?=^## |\Z)", text, re.S | re.M)


def code_span_terms(line):
    terms = []
    for span in re.findall(r"`([^`]+)`", line):
        terms += [term.strip() for term in span.split("/") if term.strip()]
    return terms


def check_rule_tables(issues):
    module = load_hard_metrics(issues)
    text = read_text("references/structures.md", issues, "rule-tables")
    if module is None or text is None:
        return 0

    relative = "references/structures.md"
    checked = 0

    # 第 25 条借喻场：正文「常见 N 套：A、B、……」与 METAPHOR_FIELDS 双向一致，
    # 且声明的数量词要和实际列出的套数对得上（加场时忘改数字也算漂移）。
    section = rule_section(text, 25)
    match = re.search(r"常见([一二三四五六七八九十]+)套：([^。]+)。", section.group()) if section else None
    if match is None:
        add_issue(issues, relative, "-", "rule-tables", "第 25 条找不到「常见 N 套：……」枚举，无法与 METAPHOR_FIELDS 对照")
    else:
        line = line_number(text, section.start() + match.start())
        doc_fields = [item.strip() for item in match.group(2).split("、") if item.strip()]
        code_fields = list(module.METAPHOR_FIELDS)
        if CN_NUM.get(match.group(1)) != len(doc_fields):
            add_issue(issues, relative, line, "rule-tables", f"第 25 条声称「{match.group(1)}套」，实际列了 {len(doc_fields)} 套")
        if set(doc_fields) != set(code_fields):
            add_issue(
                issues,
                relative,
                line,
                "rule-tables",
                f"第 25 条与 hard_metrics.METAPHOR_FIELDS 不一致："
                f"仅正文有 {sorted(set(doc_fields) - set(code_fields)) or '无'}，"
                f"仅脚本有 {sorted(set(code_fields) - set(doc_fields)) or '无'}",
            )
        checked += 1

    # 第 21 条名词化：正文列的空动词与 NOMINALIZATION_PATTERNS 的起手动词双向一致。
    # 范围只到起手动词，不含后面的动名词宾语（`优化 / 分析 / 梳理` 那批）：正文把宾语写在
    # 「检测」节且按举例列，脚本侧是穷举，两边口径本就不同，强行对账只会误报。
    section = rule_section(text, 21)
    match = re.search(r"\*\*模式\*\*：(.+)", section.group()) if section else None
    if match is None:
        add_issue(issues, relative, "-", "rule-tables", "第 21 条找不到「**模式**：」行，无法与 NOMINALIZATION_PATTERNS 对照")
    else:
        line = line_number(text, section.start() + match.start())
        doc_verbs = set(code_span_terms(match.group(1)))
        code_verbs = set()
        for pattern in module.NOMINALIZATION_PATTERNS:
            head = re.match(r"[一-鿿]+", pattern.pattern)
            if not head:
                continue
            verb = head.group()
            # `实现了?` / `完成了?对` 里的「了」是可选量词标记，不属于空动词本身
            if verb.endswith("了") and pattern.pattern[head.end() : head.end() + 1] == "?":
                verb = verb[:-1]
            code_verbs.add(verb)
        if doc_verbs != code_verbs:
            add_issue(
                issues,
                relative,
                line,
                "rule-tables",
                f"第 21 条与 hard_metrics.NOMINALIZATION_PATTERNS 的空动词不一致："
                f"仅正文有 {sorted(doc_verbs - code_verbs) or '无'}，"
                f"仅脚本有 {sorted(code_verbs - doc_verbs) or '无'}",
            )
        checked += 1

    # 第 23 条连词：正文是举例，只单向要求它列到的词脚本里都有。
    section = rule_section(text, 23)
    match = re.search(r"\*\*模式\*\*：(.+)", section.group()) if section else None
    if match is None:
        add_issue(issues, relative, "-", "rule-tables", "第 23 条找不到「**模式**：」行，无法与 CONJUNCTIONS_ZH 对照")
    else:
        missing = [term for term in code_span_terms(match.group(1)) if term not in module.CONJUNCTIONS_ZH]
        if missing:
            add_issue(
                issues,
                relative,
                line_number(text, section.start() + match.start()),
                "rule-tables",
                f"第 23 条正文列的连词不在 hard_metrics.CONJUNCTIONS_ZH 里：{missing}",
            )
        checked += 1

    return checked


def main():
    issues = []
    check_blind_sync(issues)
    case_matches, rs_matches, sf, snf, anchors = check_counts(issues)
    files = markdown_files(issues)
    links = check_links(files, issues)
    check_case_ids(files, case_matches, rs_matches, issues)
    check_meta(issues)
    tables = check_rule_tables(issues)

    if issues:
        print("\n".join(issues))
        print(f"check_repo: FAIL（{len(issues)} 个问题）")
        return 1
    total = sf + snf
    print(f"check_repo: OK（{total} 用例 / {len(rs_matches)} 样本 / {anchors} 锚点 / {links} 链接 / {tables} 词表）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

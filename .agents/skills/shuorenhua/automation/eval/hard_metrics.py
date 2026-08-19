#!/usr/bin/env python3
"""eval harness 零依赖硬判与 residual 统计。

v2.2.0：字数留存率 / 破折号密度 / protected spans 粗核（规格见旧 roadmap §6）。
v2.3.0：新增句长 CV / 连词密度 / 名词化 / 借喻场统计与 benchmark 标定模式。
v2.3.0 合并批次：residual 层新增「」/『』高亮短语候选计数，继续只报数不判死。
合并版 v2.3.0 标定实测（SF 57 / SNF 46）：候选数两组中位数与 p90 均为 0、
max 均为 3；SF-55 是自造高亮，SNF-44 是人物对白，原始计数不可分，
因此不设阈值、不影响退出码。
定位：把 judge 模型能被脚本替掉的判定项拿出来硬判——降成本、提稳定性。
判死 vs 报警：字数留存率与破折号密度按 run-eval.md 既有口径直接判过/不过；
protected spans 粗核只报警不判死，缺失留给 judge 复核（粗核是正则匹配，
不判定语义改写是否保真）。

用法（仓库根目录）：
    python3 automation/eval/hard_metrics.py --run tasks/current/eval-runs/<日期>-<版本>/
        # 扫批次目录：自动配对原文本（evals/benchmark-blind.md）与各模型输出，
        # 逐条计算，输出 <目录>/hard-metrics.md 报告和 <目录>/hard-metrics.json
    python3 automation/eval/hard_metrics.py --pair <原文本文件> <改后文本文件>
        # 单条对照：输出可读结果
    python3 automation/eval/hard_metrics.py --stdin <原文本文件>
        # 原文本从文件读，改后文本从 stdin 读；输出可读结果
    python3 automation/eval/hard_metrics.py --pair A.md B.md --report-json
        # 输出单行 JSON，供 automation/eval/README.md 的管道用法拼接 judge 输入

退出码：--run 模式任一长文用例留存率低于硬下限 0.85 时退出码为 1；
批次不完整（零用例批次 / 缺输出）时退出码为 2（报告不可信）；
缺文件、格式异常等自身错误退出码为 2；其余为 0。
"""

import argparse
import json
import re
import sys
from pathlib import Path

# 长文用例判据口径来自 evals/run-eval.md「Long-form / in-place」：
# 字数留存率目标 >= 0.90，硬下限 0.85
RETENTION_TARGET = 0.90
RETENTION_FLOOR = 0.85

# 场景标签里标了 long 的用例按长文判据处理；这个信号同时写死在
# benchmark-blind.md 的标题行里，不依赖 benchmark.md 的预期字段
LONG_TAG = re.compile(r"\blong\b")


def batch_expected_ids(batch):
    """从批次名解析期望覆盖的用例编号集。

    支持 `B01-16`（盲测区间）与旧口径 `SF43-45-SNF34-35`（v1.9.2 回放，
    多个前缀+区间段）。非区间命名（如 targeted-*）返回 None。
    """
    segments = re.split(r"-", batch)
    groups = []  # [(prefix, lo, hi)]
    i = 0
    while i < len(segments):
        seg = segments[i]
        m = re.fullmatch(r"([A-Za-z]*)(\d+)", seg)
        if not m:
            return None
        prefix = m.group(1).upper()
        num = int(m.group(2))
        if i + 1 < len(segments) and re.fullmatch(r"\d+", segments[i + 1]):
            lo, hi = num, int(segments[i + 1])
            if lo > hi:
                return None
            groups.append((prefix, lo, hi))
            i += 2
        else:
            groups.append((prefix, num, num))
            i += 1
    if not groups:
        return None
    ids = set()
    for prefix, lo, hi in groups:
        if prefix in ("", "B"):
            ids.update(f"B-{n:02d}" for n in range(lo, hi + 1))
        else:
            ids.update(f"{prefix}-{n}" for n in range(lo, hi + 1))
    return ids

# 保护片段粗核：数字（含单位）、版本号、路径、反引号片段、带小数的百分比、
# 中英文时间表达、英文缩略词。只做逐字存在检查，不做语义判定。
TOKEN_PATTERNS = [
    (r"`[^`\n]+`", "反引号片段"),
    # 中文紧贴场景（「耗时20ms」「共20人」）没有 \b 边界：数字侧用 ASCII 负向断言，
    # 中文（CJK）不算 word char，汉字贴数字也能命中；单位表把 CJK 单位也列进来。
    (r"(?<![0-9A-Za-z_])\d+(?:\.\d+)?\s*(?:ms|s|h|天|小时|分钟|秒|%|MB|GB|KB|倍|次|人|台|个|条|篇|年|月|日|版本|万|k)(?![0-9A-Za-z_])", "数字+单位"),
    (r"(?<![0-9A-Za-z_])\d+(?:\.\d+)?(?![0-9A-Za-z_])", "数字"),
    # 版本号：中文紧贴（「版本v1.8.0」）用负向字符断言替代 \b
    (r"(?<![0-9A-Za-z])v?\d+\.\d+\.\d+(?:[-+][\w.]+)?(?![0-9A-Za-z])", "版本号"),
    (r"(?:^|[\s(/])(?:[\w-]+/){1,}[\w./-]+", "路径"),
    (r"\b[A-Za-z_][A-Za-z0-9_]*[a-z][A-Za-z0-9_]*(?:[A-Z][a-z0-9]*){2,}\b", "英文标识符"),
    (r"\b(?:[a-z]+_){1,}[a-z][a-z0-9_]*\b", "英文标识符"),
    (r"\b(?:p95|p99|max_connections|handleBurst|Request|iOS|API|URL|DB|HTTP|CLI|Redis|Dijkstra|GitHub|Linux)\b", "英文缩略词/术语"),
    (r"\d{4}[-年]\d{1,2}(?:[-月]\d{1,2}日?)?", "日期"),
]

def parse_cases(root):
    """从 benchmark 语料解析用例：(编号, 场景, 原文)。

    盲测标题 `### B-xx | 场景` 从 evals/benchmark-blind.md 读；
    旧口径 `### SF-xx | 场景 | 描述` / `### SNF-xx | ...`（v1.9.2 回放）
    从 evals/benchmark.md 读。两个语料都解析并合并，编号体系互不冲突。
    """
    cases = []

    def parse_file(path, head):
        text = path.read_text(encoding="utf-8")
        current = None
        for line in text.splitlines():
            m = head.match(line)
            if m:
                current = {"id": m.group(1), "scene": m.group(2).strip(), "quote": []}
                cases.append(current)
                continue
            if current is not None and (line.startswith(">") or not line.strip()):
                current["quote"].append(line)

    blind = root / "evals" / "benchmark-blind.md"
    if blind.exists():
        parse_file(blind, re.compile(r"^### (B-\d+) \| (.+)$"))
    bench = root / "evals" / "benchmark.md"
    if bench.exists():
        parse_file(bench, re.compile(r"^### (SF-\d+|SNF-\d+) \| ([^|]+)"))
    if not cases:
        print("hard_metrics: evals/benchmark-blind.md 与 evals/benchmark.md 都没有可解析用例", file=sys.stderr)
        sys.exit(2)
    out = []
    for c in cases:
        quote = "\n".join(c["quote"]).strip("\n")
        if not quote:
            print(f"hard_metrics: {c['id']} 在 benchmark-blind.md 中没有解析到引用块", file=sys.stderr)
            sys.exit(2)
        out.append((c["id"], c["scene"], quote))
    return out


def extract_blocks(text):
    """从模型输出里切出每条用例的 处理结果 正文。

    返回 {盲测编号: 正文}。B-xx 标题后的「处理结果：」以下到下一个
    B-xx 标题之间的内容都算正文；B-xx 标题缺失时按序配对前一个编号。
    """
    lines = text.splitlines()
    blocks = {}
    pending_id = None
    in_result = False
    buf = []
    for line in lines:
        # 模型可能给整篇输出加 blockquote 前缀（`> ## B-01`），识别标题时先剥
        line_stripped = line[2:] if line.startswith("> ") else line
        # 兼容两代标题：盲测 B-xx 与旧口径 SF-xx / SNF-xx（v1.9.2 回放）
        m = re.match(r"^## (B-\d+|SF-\d+|SNF-\d+)$", line_stripped)
        if m:
            if pending_id is not None and buf:
                blocks.setdefault(pending_id, []).extend(buf)
            pending_id = m.group(1)
            in_result = False
            buf = []
            continue
        if pending_id is None:
            continue
        if in_result and re.match(r"^## |^### ", line_stripped):
            # 下一个用例标题（或章节标题）：结束当前正文块，行由下一轮循环的
            # 标题分支处理；不能用 break，否则后续用例全部丢失
            continue
        # 处理结果 行也可能带 blockquote 前缀（`> 处理结果：`），剥前缀后再识别
        if re.match(r"^处理结果(?:（[^）]*）)?[:：]", line_stripped):
            in_result = True
            rest = line_stripped.split("：", 1)[1] if "：" in line_stripped else (
                line_stripped.split(":", 1)[1] if ":" in line_stripped else ""
            )
            if rest.strip():
                buf.append(rest)
            continue
        if in_result and re.match(r"^判定链[:：]", line):
            continue
        if in_result:
            buf.append(line)
    if pending_id is not None and buf:
        blocks.setdefault(pending_id, []).extend(buf)
    return {k: "\n".join(v) for k, v in blocks.items()}


def strip_output_notes(text):
    """剥掉模型输出末尾的括号说明段（claude 在正文后附的 `（in-place：…）` 等）。

    特征：独立段落、整段以 `（` 开头 `）` 结尾、不是 `（待确认）` 删除清单。
    人工 wc -m 记录不算这些说明（对照 long-form-retention.txt：claude B-19 320、
    B-44 254 都是剥掉说明段后的正文长度）。
    """
    paras = text.split("\n\n")
    out = []
    for para in paras:
        s = para.strip()
        if s.startswith("（") and s.endswith("）") and not s.startswith("（待确认"):
            continue
        out.append(para)
    return "\n\n".join(out)


def count_chars(text, strip_markdown_prefix=False):
    """长文留存率口径：与既有人工 wc -m 一致，统计所有字符含空白。

    benchmark-blind.md 的原文是 blockquote（每行带 `> ` 前缀）；人工 wc -m
    记录的是去掉前缀后的正文（对照 long-form-retention.txt：B-02 231、B-19
    339、B-44 254、B-68 416）。模型输出侧剥掉 `> ` 前缀、末尾括号说明段
    和首尾空白再数。
    """
    lines = []
    for line in text.splitlines():
        if strip_markdown_prefix and line.startswith("> "):
            lines.append(line[2:])
        elif strip_markdown_prefix and line.startswith(">"):
            lines.append(line[1:])
        else:
            lines.append(line)
    text = "\n".join(lines)
    text = strip_output_notes(text)
    return len(text.strip("\n"))


def retained(tokens, text):
    """粗核：token 逐字出现在 text 里才算保留，大小写敏感、忽略空白差异。"""
    norm = re.sub(r"\s+", "", text)
    hits, missing = [], []
    for pat, label, raw in tokens:
        probe = re.sub(r"\s+", "", raw)
        if probe and probe in norm:
            hits.append((pat, label, raw))
        else:
            missing.append((pat, label, raw))
    return hits, missing


def dash_metrics(blocks_text, original):
    """破折号密度：原文本段数、原/改每段 —— 计数、输出首句是否仍以 —— 起手。

    首句起手 = 正文第一段的第一个句子以 `——` 开头（SF-43 判据之一）。
    只统计含 —— 的段；输出侧首句起手是「该改没改」的残留信号。
    """
    def segs(text):
        return [s for s in re.split(r"\n\s*\n", text) if s.strip()]

    def strip_quote_prefix(text):
        """剥 blockquote 前缀：模型输出与 benchmark-blind 原文都可能带 `> `。"""
        lines = []
        for line in text.splitlines():
            if line.startswith("> "):
                lines.append(line[2:])
            elif line.startswith(">"):
                lines.append(line[1:])
            else:
                lines.append(line)
        return "\n".join(lines)

    orig_segs = segs(strip_quote_prefix(original))
    new_segs = segs(strip_quote_prefix(blocks_text))
    orig_counts = [s.count("——") for s in orig_segs]
    new_counts = [s.count("——") for s in new_segs]

    def first_sentence(text):
        return re.split(r"(?<=[。！？.!?])", text, maxsplit=1)[0]

    orig_first_starts = False
    if orig_segs:
        orig_first_starts = first_sentence(orig_segs[0]).lstrip().startswith("——")

    new_first_starts = False
    if new_segs:
        new_first_starts = first_sentence(new_segs[0]).lstrip().startswith("——")

    return {
        "original_segments": len(orig_segs),
        "output_segments": len(new_segs),
        "original_per_segment": orig_counts,
        "output_per_segment": new_counts,
        "output_total_dashes": sum(new_counts),
        "original_first_sentence_starts_with_dash": orig_first_starts,
        "output_first_sentence_starts_with_dash": new_first_starts,
    }


# ---------------------------------------------------------------------------
# residual 统计层（v2.3.0）
# ---------------------------------------------------------------------------
# 定位：既有三项硬判都在「保真侧」——改写有没有改坏。这一层补「残留侧」：
# 改完读起来还像不像模型写的。判据全部不依赖词表，抓的是「换一套词继续做
# 同一件事」——词表拦不住换字，统计量拦得住。
#
# 全部只报警，不判死，不影响退出码。阈值由 --calibrate 在 evals/benchmark.md
# 的 SF（该改）/ SNF（不该改）两组语料上实测标定，不照抄外部经验值。
#
# v2.3.0 标定实测结论（`--calibrate`，SF 53 / SNF 42）：
#   - 句长变异系数：**标不了**。够 12 句的样本 SF 只有 2 条、SNF 零条。
#     标定它需要「人写长文」对照组，本仓库语料里一篇都没有（real-samples.md
#     的 5 条 long 全是 AI 味样本，没有反例）。缺口留给后续版本。
#   - 连词密度：**全局判据被实测否掉，不设阈值**。SNF 中位 5.26 / 千字高于
#     SF 中位 0.00，且 SNF max 81.08 高于 SF max 80.00——不该改的比该改的
#     密度还高。benchmark 里有一对同密度对照用例钉住这件事：SF-50
#     （public-writing 叙事）80.00 该删一半，SNF-39（docs 迁移说明）81.08
#     一个都不能删。原因是 docs / status 靠显性连词承担条件与因果。照抄
#     外部「每千字 7 个」的阈值会优先误伤不该改的文本，因此本层只输出
#     数值供人看，判定交给 structures.md 第 23 条的场景限定。
#   - 名词化 / 借喻场：区分度好，且 SNF 侧零误报。名词化 SF max 4（SF-48）、
#     SNF max 0；借喻场 SF max 5（SF-52）、SNF max 1（SNF-41 的三套名义命中
#     被字面用法排除表滤成一套，正是该用例要验的）。两项都只报数不判死。
#
# v2.3.0 合并批次标定实测结论（`--calibrate`，SF 57 / SNF 46）：
#   - 「」/『』高亮短语：**原始计数不可设阈值**。两组中位数与 p90 都是 0，
#     max 都是 3。SF-55 的 3 处是抽象概念上的自造高亮，SNF-44 的 3 处是小说
#     人物对白；同一个计数对应相反结论，照抄上游「一篇 3 处以上」会直接误伤。
#     因此脚本只机械统计候选，是否属于自造金句仍由人结合引用、正式术语和
#     文学场景判断，不设阈值、不影响退出码。

# 显性连词：中文小句靠语序和事理相接，连词密度高是英文式衔接的搬运痕迹
CONJUNCTIONS_ZH = (
    "因为", "所以", "但是", "然而", "同时", "此外", "而且", "并且",
    "因此", "不仅", "于是", "另外", "总之", "首先", "其次",
    # 条件连词同属显性衔接，是 if/then/otherwise 的搬运重灾区。
    # 单字「则」不收——「规则 / 准则 / 原则」误伤面太大。
    "如果", "否则",
)

# 动词名词化：`进行 / 实现 / 完成 / 开展 / 起到` 带一个动名词，句子变长信息没变
NOMINALIZATION_PATTERNS = (
    re.compile(r"进行(?:了|一次|一场|着)?[^。，！？\n]{0,10}(?:调整|优化|升级|分析|讨论|沟通|梳理|复盘|迭代|探索|尝试|思考|规划|布局|评估|排查|验证)"),
    re.compile(r"实现了?[^。，！？\n]{0,14}的?[^。，！？\n]{0,6}(?:提升|增长|突破|转变|跃升|落地|改善)"),
    re.compile(r"完成了?对[^。，！？\n]{0,16}的"),
    re.compile(r"起到了?[^。，！？\n]{0,12}的?作用"),
    re.compile(r"具有[^。，！？\n]{0,10}(?:意义|价值)"),
    re.compile(r"开展[^。，！？\n]{0,10}(?:工作|建设|研究|合作)"),
)

# 借喻场：同一段里从多套不相干的比喻系统借词，是用比喻替代说明的信号。
# 单套用得准没问题，多套混用才报警。
METAPHOR_FIELDS = {
    "道路竞赛": ("赛道", "跑道", "岔路", "十字路口", "终点线", "起跑线", "弯道超车"),
    "战争攻防": ("护城河", "壁垒", "厮杀", "血战", "阵地", "弹药", "突围", "打法"),
    "建筑灾害": ("坍塌", "崩塌", "地基", "支柱", "废墟", "基石"),
    "温度": ("降温", "升温", "冷却", "余温", "白热化", "点燃"),
    "仓储": ("仓库", "库存", "抽屉", "货架", "囤积"),
    "海洋航行": ("蓝海", "红海", "浪潮", "潮水", "灯塔", "彼岸", "风口"),
    "机器器官": ("齿轮", "引擎", "发动机", "血管", "骨架", "神经末梢"),
}

# 借喻词的字面用法排除：这些前缀出现时该词是技术术语或本义，不算借喻。
# 误伤防护优先——本仓库的判据默认宁可漏报不可误杀。
METAPHOR_LITERAL_PREFIX = {
    "引擎": ("搜索", "渲染", "游戏", "物理", "推荐", "规则", "模板", "查询", "存储"),
    "发动机": ("汽车", "飞机", "柴油", "航空"),
    "仓库": ("代码", "git", "Git", "远程", "本地", "私有", "镜像"),
    "库存": ("商品", "实际", "系统", "剩余"),
    "阵地": ("前沿",),
    "风口": ("出", "通", "进"),
    "打法": ("战术",),
}


def mask_non_prose(text):
    """屏蔽代码块、行内代码、链接目标、URL 和 HTML 标签，保留字符偏移与换行。

    用等长空格替换而不是删除：偏移不变，后续算行号和窗口距离才准。
    """
    def mask(match):
        return "".join("\n" if ch == "\n" else " " for ch in match.group())

    patterns = (
        re.compile(r"\A---\s*\n.*?\n---\s*(?:\n|\Z)", re.DOTALL),
        re.compile(r"```.*?```", re.DOTALL),
        re.compile(r"`[^`\n]*`"),
        re.compile(r"\]\([^\n)]*\)"),
        re.compile(r"https?://[^\s)>]+"),
        re.compile(r"<[^>\n]+>"),
    )
    out = text
    for pattern in patterns:
        out = pattern.sub(mask, out)
    return out


def strip_blockquote(text):
    """剥 blockquote 前缀（benchmark 语料的引用块与模型输出都可能带 `> `）。

    与 dash_metrics 内的同名局部函数功能一致；那个是既有代码的闭包，这里
    单独提供模块级版本给 residual 层用，不改动原函数。
    """
    lines = []
    for line in text.splitlines():
        if line.startswith("> "):
            lines.append(line[2:])
        elif line.startswith(">"):
            lines.append(line[1:])
        else:
            lines.append(line)
    return "\n".join(lines)


def han_count(text):
    return len(re.findall(r"[一-鿿]", text))


def _non_overlapping(text, terms):
    """长词优先的不重叠匹配，返回 [(位置, 词)]。避免「因此」被「因」重复计数。"""
    matches, occupied = [], []
    for term in sorted(terms, key=len, reverse=True):
        for m in re.finditer(re.escape(term), text):
            start, end = m.span()
            if any(start < oe and end > os for os, oe in occupied):
                continue
            matches.append((start, term))
            occupied.append((start, end))
    return sorted(matches)


def sentence_length_cv(text, min_sentences=12):
    """句长变异系数：人写的长短句差距大，模型的句长彼此接近。

    返回 (cv, 句数)。句数不足时 cv 为 None——短文本上这个量没有意义，
    不做外推。
    """
    lengths = [
        han_count(m.group())
        for m in re.finditer(r"[^。！？!?\n]+[。！？!?]", text)
        if han_count(m.group()) >= 4
    ]
    if len(lengths) < min_sentences:
        return None, len(lengths)
    mean = sum(lengths) / len(lengths)
    if mean == 0:
        return None, len(lengths)
    variance = sum((v - mean) ** 2 for v in lengths) / len(lengths)
    return (variance ** 0.5) / mean, len(lengths)


def conjunction_density(text):
    """显性连词密度（每千字）。返回 (密度, 命中数, 汉字数)。"""
    han = han_count(text)
    if han == 0:
        return None, 0, 0
    hits = _non_overlapping(text, CONJUNCTIONS_ZH)
    return len(hits) * 1000.0 / han, len(hits), han


def nominalization_hits(text):
    """动词名词化命中。返回 [(位置, 命中片段)]。"""
    out = []
    for pattern in NOMINALIZATION_PATTERNS:
        for m in pattern.finditer(text):
            out.append((m.start(), m.group()))
    return sorted(out)


def metaphor_fields_hit(text, window=800):
    """借喻场统计：返回 (最大同窗口场数, 命中明细)。

    命中明细为 [(位置, 场名, 词)]。字面用法（搜索引擎、代码仓库）先排除。
    """
    hits = []
    for field, words in METAPHOR_FIELDS.items():
        for word in words:
            for m in re.finditer(re.escape(word), text):
                prefixes = METAPHOR_LITERAL_PREFIX.get(word, ())
                head = text[max(0, m.start() - 4):m.start()]
                if any(head.endswith(p) for p in prefixes):
                    continue
                hits.append((m.start(), field, word))
    hits.sort()
    best = 0
    for i, (start, _, _) in enumerate(hits):
        fields = {h[1] for h in hits[i:] if h[0] - start <= window}
        best = max(best, len(fields))
    return best, hits


def highlight_quote_hits(text):
    """「」/『』括起的短语候选。返回 [(位置, 内容)]。

    只收同一行 1–30 字符的短内容，排除大段引用；脚本无法可靠区分自造金句、
    正式术语和人物对白，因此这一项只提供 residual 观测，不直接判定。
    """
    hits = []
    for pattern in (r"「([^「」\n]{1,30})」", r"『([^『』\n]{1,30})』"):
        for match in re.finditer(pattern, text):
            hits.append((match.start(), match.group(1)))
    return sorted(hits)


def residual_metrics(text):
    """一段文本的残留统计量。输入应为正文（调用方负责剥 blockquote）。"""
    prose = mask_non_prose(text)
    cv, sentences = sentence_length_cv(prose)
    density, conj_hits, han = conjunction_density(prose)
    noms = nominalization_hits(prose)
    fields, field_hits = metaphor_fields_hit(prose)
    quotes = highlight_quote_hits(prose)
    quote_density = len(quotes) * 1000.0 / han if han else None
    return {
        "han": han,
        "sentences": sentences,
        "sentence_cv": None if cv is None else round(cv, 4),
        "conjunction_per_1k": None if density is None else round(density, 2),
        "conjunction_hits": conj_hits,
        "nominalization": len(noms),
        "nominalization_samples": [s for _, s in noms[:4]],
        "metaphor_fields": fields,
        "metaphor_samples": sorted({w for _, _, w in field_hits})[:6],
        "highlight_quotes": len(quotes),
        "highlight_quote_per_1k": None if quote_density is None else round(quote_density, 2),
        "highlight_quote_samples": [s for _, s in quotes[:6]],
    }


def retention_status(ratio):
    if ratio >= RETENTION_TARGET:
        return "ok"
    if ratio >= RETENTION_FLOOR:
        return "warn"
    return "fail"


def normalize_text(t):
    """归一化：去空白、全角/半角括号差异，用于「声明 no-op 但正文没跟上」比对。"""
    norm = re.sub(r"\s+", "", t)
    norm = norm.replace("（", "(").replace("）", ")").replace("，", ",").replace("。", ".")
    return norm


def is_noop(output_text):
    """no-op 判定：输出以「保留原文」开头，或处理结果不含改写正文。

    no-op 用例不判留存率——模型判定不该改时输出说明即可，字数变短不代表误删；
    留存率口径只约束实际改写（替掉人工对长文改写用例的 wc -m）。
    """
    head = output_text.lstrip().split("\n", 1)[0]
    # --pair/--stdin 模式给的是完整模型输出，先剥「处理结果：」前缀再判断
    m = re.match(r"^处理结果(?:（[^）]*）)?[:：]\s*", head)
    if m:
        head = head[m.end():]
    return (
        head.startswith("保留原文")
        or head.startswith("保持原文")
        or head.startswith("保留原文：")
        or head.startswith("保持原文：")
    )


def analyze_case(cid, scene, original, output_text, raw_output=None):
    """单条用例的硬判结果。

    raw_output：可选，完整输出文件文本，用于在判定链里查「力度=no-op」证据；
    缺省时退化用 output_text 本身。
    """
    # --pair/--stdin 常给完整模型输出（含 `## B-xx` 标题）。先尝试剥出「处理结果」
    # 正文；剥不出（纯正文）就原样用。raw_output 未提供时回填为剥前原文，
    # 保证判定链证据可用。
    if re.search(r"^#{1,3} ", output_text, re.MULTILINE):
        blocks = extract_blocks(output_text)
        target = blocks.get(cid) or next(
            (b for b in blocks.values() if b.strip()), ""
        )
        if target.strip():
            if raw_output is None:
                raw_output = output_text
            output_text = target
    char_orig = count_chars(original, strip_markdown_prefix=True)
    char_out = count_chars(output_text, strip_markdown_prefix=True)
    ratio = char_out / char_orig if char_orig else 1.0

    noop = is_noop(output_text)
    is_long = bool(LONG_TAG.search(scene))
    is_inplace_long = is_long and "in-place" in scene
    # 假 no-op 校验：声明保留原文时，要么判定链有「力度=no-op」的推理证据（judge 会复核），
    # 要么正文≈原文（归一化后长度不比原文短太多且原文字符基本都在）。
    # 两者都没有 → 标 noop_unverified，仍按长文判据计算，不让假 no-op 吞掉硬失败。
    noop_unverified = False
    if noop and is_inplace_long:
        verdict_text = raw_output or output_text
        chain_noop = re.search(r"力度\s*[:=]\s*no-?op", verdict_text) is not None
        norm_out = normalize_text(output_text)
        # benchmark-blind 原文带 `> ` blockquote 前缀，归一化前先剥掉
        stripped_orig = "\n".join(
            l[2:] if l.startswith("> ") else (l[1:] if l.startswith(">") else l)
            for l in original.splitlines()
        )
        norm_orig = normalize_text(stripped_orig)
        # 真 no-op 的输出要么是原文本身（正文连续包含归一化后的原文），
        # 要么有判定链「力度=no-op」佐证。假 no-op 只有一句「保留原文」的说明，
        # 原文不会连续出现 → 标 noop_unverified，仍按实际留存率判。
        body_ok = bool(norm_orig) and norm_orig in norm_out
        noop_ok = chain_noop or body_ok
        if not noop_ok:
            noop_unverified = True
        if noop_ok and body_ok:
            # 正文≈原文：留存率按 100% 记（与手工 wc -m 口径一致，
            # 「处理结果：/保持原文：」等包装字不计入分子）
            char_out = char_orig
            ratio = 1.0
    retention = None
    if is_inplace_long:
        status = "noop" if (noop and not noop_unverified) else retention_status(ratio)
        retention = {
            "original_chars": char_orig,
            "output_chars": char_out,
            "ratio": round(ratio, 4),
            "target": RETENTION_TARGET,
            "floor": RETENTION_FLOOR,
            "status": status,
            "noop_unverified": noop_unverified,
        }

    dm = dash_metrics(output_text, original)
    dashes_dense = (
        max(dm["output_per_segment"], default=0) >= 4
        or dm["output_first_sentence_starts_with_dash"]
    )

    tokens = []
    for pat, label in TOKEN_PATTERNS:
        for m in re.finditer(pat, original, re.MULTILINE):
            raw = m.group(0).strip()
            if raw and re.fullmatch(r"[\s\W_]+", raw):
                continue
            tokens.append((pat, label, raw, m.start(), m.end()))

    # 版本号优先：先剥掉完整版本跨度，避免「v1.8.0」再被裸数字拆成幽灵片段 8/8.0
    version_spans = []
    for pat, label in TOKEN_PATTERNS:
        if label != "版本号":
            continue
        for m in re.finditer(pat, original, re.MULTILINE):
            version_spans.append((m.start(), m.end()))
    if version_spans:
        kept = []
        for pat, label, raw, start, end in tokens:
            if any(s < end and start < e for s, e in version_spans if not (label == "版本号" and s == start and e == end)):
                continue
            kept.append((pat, label, raw, start, end))
        tokens = kept

    # 按位置覆盖去重：一个匹配完全落在更早（更长）匹配区间内时丢弃。
    # 例：`3.8%` 先被「数字+单位」匹配（0,4），`3` / `3.8` 落在其内 → 丢弃。
    # 模式顺序即优先级：数字+单位 > 版本号 > 路径 > 标识符 > 日期 > 数字。
    tokens.sort(key=lambda t: (t[3], -(t[4] - t[3])))
    deduped = []
    covered_until = -1
    for pat, label, raw, start, end in tokens:
        if start < covered_until:
            continue
        deduped.append((pat, label, raw))
        covered_until = max(covered_until, end)
    # no-op 用例也要跑粗核：模型说「保留原文」但实际改了数字/术语时，
    # 缺失报警能抓住假 no-op（留存率不判是因为输出是说明文字不是正文）
    hits, missing = retained(deduped, output_text)

    return {
        "case": cid,
        "scene": scene,
        "is_long": is_long,
        "retention": retention,
        "dashes": {
            "dense": dashes_dense,
            **dm,
        },
        "protected": {
            "total": len(deduped),
            "hit": len(hits),
            "missing": missing,
        },
        "noop": noop,
        "noop_unverified": noop_unverified,
    }


def summarize(result):
    """把单条结果变成 markdown 小节（run-eval.md 口径的判定）。"""
    lines = [f"### {result['case']} | {result['scene']}", ""]
    if result["is_long"] and not result["retention"]:
        # 非 in-place 的长文都走这一支：bounded、no-op 判定用例都在内。
        # 早期措辞一律写成「bounded 长文」，会让 judge 误以为用例被判成了 bounded
        # （v2.3.0 跨模型盲测中 judge 对 SNF-38 提出过这一点），改为按场景标签直述。
        lines.append(
            f"- 字数留存率：不适用（场景标签 `{result['scene'] or '未标注'}` 不含 in-place，"
            "run-eval.md 口径只对 in-place 长文判留存率）"
        )
    if result["retention"]:
        r = result["retention"]
        if r.get("noop_unverified"):
            lines.append(f"- 字数留存率：{r['output_chars']}/{r['original_chars']} = {r['ratio']:.1%}（⚠️ 声明保留原文但正文未跟上原文，按实际改写判：目标 ≥ {r['target']:.0%}，硬下限 {r['floor']:.0%}）→ **{r['status'].upper()}**")
        elif r["status"] == "noop":
            lines.append(f"- 字数留存率：{r['output_chars']}/{r['original_chars']} = {r['ratio']:.1%}（no-op：模型判定保留原文，留存率不判；数字仅供参考复核）")
        else:
            lines.append(f"- 字数留存率：{r['output_chars']}/{r['original_chars']} = {r['ratio']:.1%}（目标 ≥ {r['target']:.0%}，硬下限 {r['floor']:.0%}）→ **{r['status'].upper()}**")
        if r["status"] == "warn":
            lines.append("  - ⚠️ 低于目标，高于硬下限：符合 run-eval.md 的既有口径但需 judge 复核风格列")
        elif r["status"] == "fail":
            lines.append("  - ❌ 低于硬下限：长文误删并句重排风险，按 run-eval.md 记硬约束 ❌")
    d = result["dashes"]
    lines.append(f"- 破折号密度：原 {d['original_per_segment']} / 改 {d['output_per_segment']}；输出首句起手={d['output_first_sentence_starts_with_dash']}；总 {d['output_total_dashes']} 处")
    if d["dense"]:
        lines.append("  - ⚠️ 单段 ≥ 4 处或首句起手：命中 SF-43 破折号过密信号，需 judge 复核标点腔处理")
    p = result["protected"]
    lines.append(f"- protected spans 粗核：{p['hit']}/{p['total']} 保留")
    if p["missing"]:
        lines.append("  - ⚠️ 以下受保护片段在输出中未逐字找到（报警不判死，留给 judge 复核）：")
        for pat, label, raw in p["missing"]:
            lines.append(f"    - [{label}] `{raw}`")
    lines.append("")
    return "\n".join(lines)


def analyze_run(root, run_dir):
    """扫批次目录：配对 benchmark-blind.md 原文与各模型输出，逐条硬判。"""
    run_dir = Path(run_dir)
    cases = parse_cases(root)
    by_id = {cid: (scene, quote) for cid, scene, quote in cases}

    if run_dir.is_dir():
        candidates = sorted(run_dir.rglob("rewrite-*.md"))
    elif run_dir.is_file():
        candidates = [run_dir]
    else:
        print(f"hard_metrics: 路径不存在：{run_dir}", file=sys.stderr)
        sys.exit(2)

    model_reports = {}
    report_paths = []
    file_results = {}
    problems = {}
    for path in candidates:
        m = re.search(r"rewrite-([A-Za-z0-9-]+)\.md$", path.name)
        if not m:
            continue
        batch = m.group(1)
        report_paths.append(path)
        blocks = extract_blocks(path.read_text(encoding="utf-8"))
        expected = batch_expected_ids(batch)
        actual_ids = set(blocks)
        if expected is None:
            # 非区间命名（targeted 补跑等）：以实际出现的标题为准
            target_ids = actual_ids
        else:
            target_ids = expected
        ignored = sorted(actual_ids - target_ids)
        results = []
        for cid in sorted(target_ids):
            scene, quote = by_id.get(cid, ("", ""))
            output_text = blocks.get(cid, "")
            if not output_text:
                results.append({
                    "case": cid, "scene": scene,
                    "is_long": bool(LONG_TAG.search(scene)),
                    "retention": None, "dashes": None, "protected": None,
                    "missing_output": True, "noop": False, "noop_unverified": False,
                })
                continue
            results.append(analyze_case(cid, scene, quote, output_text, path.read_text(encoding="utf-8")))

        retentions = [r["retention"] for r in results if r.get("retention")]
        fails = [r["case"] for r in results if r.get("retention") and r["retention"]["status"] == "fail"]
        warns = [r["case"] for r in results if r.get("retention") and r["retention"]["status"] == "warn"]
        dense = [
            (r["case"], max(r["dashes"]["output_per_segment"], default=0))
            for r in results if r.get("dashes") and r["dashes"]["dense"]
        ]
        missing_spans = [
            (r["case"], len(r["protected"]["missing"]))
            for r in results if r.get("protected") and r["protected"]["missing"]
        ]

        key = path.relative_to(run_dir).as_posix() if run_dir.is_dir() else path.name
        file_results[key] = results
        # 零用例批次 = 解析失败或命名不被识别（如旧口径 SF-xx），报告不完整，记硬错
        if len(results) == 0:
            problems.setdefault(key, []).append("零用例批次（文件名命名未被 Bxx-yy 识别或正文为空）")
        if any(r.get("missing_output") for r in results):
            problems.setdefault(key, []).append(
                f"缺输出：{', '.join(r['case'] for r in results if r.get('missing_output'))}"
            )
        model_reports[key] = {
            "batch": batch,
            "total_cases": len(results),
            "ignored_out_of_range": ignored,
            "missing_output": [r["case"] for r in results if r.get("missing_output")],
            "long_form": {
                "cases": len(retentions),
                "warn": warns,
                "fail": fails,
            },
            "dash_dense": dense,
            "protected_missing": missing_spans,
        }

    if not report_paths:
        print(f"hard_metrics: {run_dir} 下没有找到 rewrite-*.md 文件", file=sys.stderr)
        sys.exit(2)

    lines_out = [
        "# Hard Metrics — 硬判报告",
        "",
        f"> 由 `python3 automation/eval/hard_metrics.py --run {run_dir}` 生成。",
        "> 字数留存率与破折号密度按 `evals/run-eval.md` 既有口径判定；protected spans 粗核只报警不判死，缺失由 judge 复核。",
        "> 本报告是运行产物，不入 commit；需要时归档到 `tasks/` 下。",
        "",
        "## 汇总",
        "",
    ]
    total_fail, total_warn = 0, 0
    for key, rep in model_reports.items():
        lf = rep["long_form"]
        total_fail += len(lf["fail"])
        total_warn += len(lf["warn"])
    lines_out.append(f"- 长文硬下限失败 {total_fail} 条（{', '.join(c for rep in model_reports.values() for c in rep['long_form']['fail']) or '无'}）")
    lines_out.append(f"- 长文目标下警告 {total_warn} 条（{', '.join(c for rep in model_reports.values() for c in rep['long_form']['warn']) or '无'}）")
    lines_out.append("")
    for path in report_paths:
        key = path.relative_to(run_dir).as_posix() if run_dir.is_dir() else path.name
        rep = model_reports[key]
        lines_out += [f"## {key}", ""]
        lines_out.append(f"- 用例总数：{rep['total_cases']}")
        if rep.get("ignored_out_of_range"):
            lines_out.append(f"- ⚠️ 区间外标题（已忽略）：{', '.join(rep['ignored_out_of_range'])}")
        if rep["missing_output"]:
            lines_out.append(f"- ⚠️ 缺输出：{', '.join(rep['missing_output'])}")
        lf = rep["long_form"]
        if lf["cases"]:
            lines_out.append(f"- 长文用例 {lf['cases']} 条：硬下限失败 {len(lf['fail'])}（{', '.join(lf['fail']) or '无'}），目标下警告 {len(lf['warn'])}（{', '.join(lf['warn']) or '无'}）")
        else:
            lines_out.append("- 长文用例：0（本批次无 long 标签用例，留存率不判）")
        if rep["dash_dense"]:
            lines_out.append(f"- ⚠️ 破折号过密 {len(rep['dash_dense'])} 条：{', '.join(f'{cid}（{n} 处）' for cid, n in rep['dash_dense'])}")
        if rep["protected_missing"]:
            lines_out.append(f"- ⚠️ 保护片段缺失报警 {len(rep['protected_missing'])} 条：{', '.join(f'{cid}（{n} 项）' for cid, n in rep['protected_missing'])}")
        lines_out.append("")
        for res in file_results[key]:
            if res.get("missing_output"):
                lines_out.append(f"### {res['case']} | {res['scene']}")
                lines_out.append("")
                lines_out.append("- ⚠️ 缺输出：本用例在输出文件中没有解析到处理结果")
                lines_out.append("")
                continue
            lines_out.append(summarize(res))
        lines_out.append("")

    header = lines_out

    out_path = run_dir if run_dir.is_dir() else run_dir.parent
    md_path = out_path / "hard-metrics.md"
    json_path = out_path / "hard-metrics.json"
    md_path.write_text("\n".join(header).rstrip() + "\n", encoding="utf-8")
    json_path.write_text(
        json.dumps({"reports": model_reports, "cases": file_results}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"hard-metrics: {len(report_paths)} 个批次 → {md_path}, {json_path}")
    for name, probs in problems.items():
        for prob in probs:
            print(f"  ⚠️ {name}: {prob}")
    for name, rep in model_reports.items():
        lf = rep["long_form"]
        print(f"  {name}: {rep['total_cases']} 条, 长文 {lf['cases']} 条, 硬下限失败 {len(lf['fail'])}")
    # 退出码：硬下限失败=1；批次不完整（零用例/缺输出）这类报告不可信=2；其余=0
    if any(problems.values()):
        return 2
    return 1 if any(rep["long_form"]["fail"] for rep in model_reports.values()) else 0


def _percentile(values, q):
    """线性插值分位数。零依赖手写，与文件其余部分保持同一风格。"""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    idx = (len(ordered) - 1) * q
    lo = int(idx)
    hi = min(lo + 1, len(ordered) - 1)
    frac = idx - lo
    return ordered[lo] * (1 - frac) + ordered[hi] * frac


def calibrate(root):
    """在 benchmark 语料上实测 residual 判据分布，供定阈值使用。

    分组：`SF-xx` 是该改的 AI 味样本，`SNF-xx` 是不该改的正常样本，两组
    天然构成对照组。`B-xx` 是 SF/SNF 的盲测副本，计入会重复污染分布，排除。

    输出每组每个指标的样本数与分位数。阈值应落在两组分布的分离处，
    并偏向 SNF 一侧——误伤防护优先，宁可漏报不可误杀。
    """
    cases = parse_cases(root)
    groups = {"SF": [], "SNF": []}
    for cid, scene, quote in cases:
        prefix = cid.split("-")[0]
        if prefix not in groups:
            continue
        groups[prefix].append((cid, scene, strip_blockquote(quote).strip()))

    if not groups["SF"] or not groups["SNF"]:
        print("hard_metrics: benchmark.md 没有解析到 SF/SNF 分组，无法标定", file=sys.stderr)
        return 2

    print("# residual 判据标定（evals/benchmark.md）\n")
    print(f"样本：SF {len(groups['SF'])} 条（该改）/ SNF {len(groups['SNF'])} 条（不该改）")
    print("B-xx 盲测副本已排除，避免同一文本重复计入分布。\n")

    collected = {}
    for name, items in groups.items():
        stats = {"cv": [], "conj": [], "nom": [], "field": [], "quote": []}
        for _, _, body in items:
            m = residual_metrics(body)
            if m["sentence_cv"] is not None:
                stats["cv"].append(m["sentence_cv"])
            if m["conjunction_per_1k"] is not None and m["han"] >= 80:
                stats["conj"].append(m["conjunction_per_1k"])
            stats["nom"].append(m["nominalization"])
            stats["field"].append(m["metaphor_fields"])
            stats["quote"].append(m["highlight_quotes"])
        collected[name] = stats

    labels = {
        "cv": "句长变异系数（句数 ≥ 12 才计）",
        "conj": "连词密度 每千字（汉字 ≥ 80 才计）",
        "nom": "名词化命中数 每条",
        "field": "同窗口借喻场数 每条",
        "quote": "「」/『』高亮短语候选数 每条",
    }
    for key, label in labels.items():
        print(f"## {label}\n")
        print("| 组 | n | p10 | p25 | 中位 | p75 | p90 | max |")
        print("|---|---|---|---|---|---|---|---|")
        for name in ("SF", "SNF"):
            vals = collected[name][key]
            if not vals:
                print(f"| {name} | 0 | - | - | - | - | - | - |")
                continue
            cells = " | ".join(
                "-" if v is None else f"{v:.2f}"
                for v in (
                    _percentile(vals, 0.10),
                    _percentile(vals, 0.25),
                    _percentile(vals, 0.50),
                    _percentile(vals, 0.75),
                    _percentile(vals, 0.90),
                    max(vals),
                )
            )
            print(f"| {name} | {len(vals)} | {cells} |")
        print()

    print("## 逐条命中（名词化 / 借喻场 / 高亮短语非零项）\n")
    for name, items in groups.items():
        for cid, scene, body in items:
            m = residual_metrics(body)
            if m["nominalization"] or m["metaphor_fields"] >= 2 or m["highlight_quotes"]:
                print(
                    f"- {cid}（{scene.strip()}）：名词化 {m['nominalization']}"
                    f"{'（' + '、'.join(m['nominalization_samples']) + '）' if m['nominalization_samples'] else ''}"
                    f"，借喻场 {m['metaphor_fields']}"
                    f"{'（' + '、'.join(m['metaphor_samples']) + '）' if m['metaphor_samples'] else ''}"
                    f"，高亮短语候选 {m['highlight_quotes']}"
                    f"{'（' + '、'.join(m['highlight_quote_samples']) + '）' if m['highlight_quote_samples'] else ''}"
                )
    return 0


def read_text_safe(path):
    """读文件，缺文件时打印错误并退出 2（自身错误口径）。"""
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as e:
        print(f"hard_metrics: 读文件失败 {path}: {e}", file=sys.stderr)
        sys.exit(2)


def single_pair(original_path, output_path, scene=""):
    """单条对照：原文本从文件读，改后文本从文件或 stdin 读。"""
    original = read_text_safe(original_path)
    if output_path == "-":
        output_text = sys.stdin.read()
    else:
        output_text = read_text_safe(output_path)
    cid = f"{Path(original_path).name} / {Path(output_path).name}"
    res = analyze_case(cid, scene, original, output_text)
    print(summarize(res).rstrip())
    return 0


def main():
    ap = argparse.ArgumentParser(description="说人话 eval harness 硬判与 residual 统计（v2.3.0）")
    ap.add_argument("--run", metavar="DIR", help="扫批次目录（含 rewrite-*.md），输出 hard-metrics 报告")
    ap.add_argument("--pair", nargs=2, metavar=("ORIG", "OUT"), help="单条对照：原文本文件 + 改后文本文件（- 表示 stdin）")
    ap.add_argument("--stdin", metavar="ORIG", help="原文本文件，改后文本从 stdin 读")
    ap.add_argument("--report-json", action="store_true", help="--pair 模式输出单行 JSON（供 judge 输入拼接）")
    ap.add_argument("--scene", metavar="SCENE", default="", help="单条模式（--pair/--stdin）的用例场景标签，如 'public-writing / long / in-place'，用于长文留存判据")
    ap.add_argument("--residual", metavar="FILE", help="对单个文本算 residual 统计量（句长 CV / 连词密度 / 名词化 / 借喻场 / 「」高亮短语），只报警不判死；- 表示 stdin")
    ap.add_argument("--calibrate", action="store_true", help="在 evals/benchmark.md 的 SF / SNF 两组语料上实测 residual 判据分布，用于定阈值")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[2]

    if args.calibrate:
        return calibrate(root)

    if args.residual:
        text = sys.stdin.read() if args.residual == "-" else read_text_safe(args.residual)
        res = residual_metrics(strip_blockquote(text))
        if args.report_json:
            print(json.dumps(res, ensure_ascii=False))
        else:
            print(f"汉字数 {res['han']}，可计句数 {res['sentences']}")
            cv = res["sentence_cv"]
            print(f"- 句长变异系数：{'句数不足 12，不判' if cv is None else cv}")
            print(f"- 连词密度：{res['conjunction_per_1k']} /千字（命中 {res['conjunction_hits']} 处）")
            print(f"- 名词化：{res['nominalization']} 处 {res['nominalization_samples']}")
            print(f"- 借喻场：{res['metaphor_fields']} 套 {res['metaphor_samples']}")
            print(f"- 「」/『』高亮短语候选：{res['highlight_quotes']} 处，{res['highlight_quote_per_1k']} /千字 {res['highlight_quote_samples']}")
        return 0

    if args.run:
        sys.exit(analyze_run(root, args.run))

    if args.pair:
        if args.report_json:
            original = read_text_safe(args.pair[0])
            output_text = (
                sys.stdin.read()
                if args.pair[1] == "-"
                else read_text_safe(args.pair[1])
            )
            res = analyze_case("pair", args.scene, original, output_text)
            print(json.dumps(res, ensure_ascii=False))
            return 0
        sys.exit(single_pair(args.pair[0], args.pair[1], args.scene))

    if args.stdin:
        original = read_text_safe(args.stdin)
        res = analyze_case("stdin", args.scene, original, sys.stdin.read())
        if args.report_json:
            print(json.dumps(res, ensure_ascii=False))
        else:
            print(summarize(res).rstrip())
        return 0

    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())

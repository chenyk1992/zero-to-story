"""Pure structural checks for completed H3 prompt drafts.

This module deliberately has no filesystem, Canvas, or provider I/O. The
caller supplies an already-resolved Canvas snapshot and decides how to present
the findings; passing structural checks never accepts generated media.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal


@dataclass(frozen=True)
class Finding:
    """One deterministic prompt issue found by the linter."""

    code: str
    severity: Literal["error", "warning"]
    message: str
    line: int | None = None


@dataclass(frozen=True)
class LintResult:
    """The checks run and facts that need a human or another contract."""

    findings: tuple[Finding, ...]
    checked: tuple[str, ...]
    unverified: tuple[str, ...]


@dataclass(frozen=True)
class _Field:
    name: str
    value: str
    line: int
    value_line: int


_BASIC_FIELDS = (
    "integrated_multimodal_description",
    "overall_soundscape",
    "non_diegetic_music",
)
_REFERENCE_FIELDS = (
    "subject_definitions",
    "summary",
    "retention_analysis",
    "detailed_description",
    "overall_soundscape",
    "non_diegetic_music",
)
_FIELD_PATTERN = re.compile(
    r"^(?P<name>integrated_multimodal_description|subject_definitions|summary|"
    r"retention_analysis|detailed_description|overall_soundscape|non_diegetic_music):"
    r"(?P<rest>.*)$"
)
_DIALOGUE_PATTERN = re.compile(r"<d>(?P<content>.*?)</d>", re.DOTALL)
_DIALOGUE_OPEN = re.compile(r"<d>")
_DIALOGUE_CLOSE = re.compile(r"</d>")
_DIALOGUE_TAG = re.compile(r"</?d>")
_SHOT_PATTERN = re.compile(r"\[Shot (?P<number>[1-9]\d*)\]")
_REFERENCE_PATTERN = re.compile(r"<(Subject|Picture|Video|Audio)\s+(\d+)>")
_REFERENCE_DEFINITION_PATTERN = re.compile(
    r"(?m)^\s*<(Subject|Picture|Video|Audio)\s+([1-9]\d*)>\s+is\b"
)
_SPEAKER_PATTERN = re.compile(r"\((?P<numbers>S[0-9]+(?:\s*,\s*S[0-9]+)*)\)")
_LEGACY_FIELD_PATTERN = re.compile(
    r"(?mi)^\s*(?:visual style|visual_style|scene setting|scene_setting|"
    r"camera(?: and composition)?|camera_and_composition|action(?: and timing)?|"
    r"action_and_timing|dialogue(?: and sound)?|dialogue_and_sound|negative prompt|"
    r"negative_prompt)\s*:"
)
_ASSET_ANCHOR_PATTERN = re.compile(r"@(CHR|SCN|PRP)\b")
_VISIBLE_RETENTION = {
    "fully_preserved",
    "partially_preserved",
    "attribute_transfer",
    "weak_reference",
}
_AUDIO_RETENTION = {"fully_copy", "partially_copy", "reference", "weak_reference"}
_RETENTION_LINE = re.compile(
    r"^\s*<(Subject|Picture|Video|Audio)\s+([1-9]\d*)>(?:\s*\([^)]*\))?\s*:"
    r"\s*([a-z_]+)\s*-\s*(\S.*)\s*$"
)


def lint_snapshot(
    snapshot: Mapping[str, Any],
    *,
    blueprint: Mapping[str, Any] | None = None,
    panel_id: str | None = None,
) -> LintResult:
    """Check a resolved H3 snapshot without modifying it.

    Blueprint comparison is optional. A local prompt can still receive format
    feedback without an episode-wide blueprint, with that gap recorded as
    unverified rather than treated as an input error.
    """

    findings: list[Finding] = []
    unverified: list[str] = []
    model = snapshot.get("model")
    mode = _normalized_mode(snapshot.get("mode"))
    if not isinstance(model, str) or "h3" not in model.lower():
        return LintResult(
            findings=(),
            checked=(),
            unverified=("未检查: 当前快照未标识为 H3 模型。",),
        )
    if mode is None:
        return LintResult(
            findings=(),
            checked=(),
            unverified=("未检查: 当前 H3 模式不在检查器支持范围内。",),
        )

    prompt = snapshot.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return LintResult(
            findings=(Finding("H3-FIELDS", "error", "提示词必须是非空文本。"),),
            checked=("H3-FIELDS",),
            unverified=(),
        )
    prompt = prompt.removeprefix("\ufeff")
    masked_prompt, dialogues = _mask_dialogue_content(prompt)
    findings.extend(_check_dialogue_markup(prompt, dialogues))

    expected_fields = _REFERENCE_FIELDS if mode == "r2v" else _BASIC_FIELDS
    fields, field_findings = _parse_fields(prompt, masked_prompt, expected_fields)
    findings.extend(field_findings)

    inputs = snapshot.get("inputs")
    input_mapping = inputs if isinstance(inputs, Mapping) else {}
    duration_ms = _duration_milliseconds(snapshot.get("parameters"), findings)
    description_name = "detailed_description" if mode == "r2v" else "integrated_multimodal_description"
    description = fields.get(description_name)
    shot_count = _check_shots(description, duration_ms, findings) if description else 0

    _check_alignment(mode, prompt, fields, shot_count, duration_ms, input_mapping, findings)
    _check_references(mode, fields, input_mapping, snapshot.get("parameters"), masked_prompt, findings, unverified)
    retention_labels = _standalone_reference_labels(fields.get("subject_definitions"))
    _check_retention(fields.get("retention_analysis"), retention_labels, findings)
    _check_dialogue_in_sound_fields(fields, findings)
    _check_speakers(description, findings, unverified)
    _check_leaks(masked_prompt, findings)
    _check_plan(
        snapshot,
        mode,
        fields,
        blueprint,
        panel_id,
        duration_ms,
        shot_count,
        findings,
        unverified,
    )

    return LintResult(
        findings=tuple(findings),
        checked=(
            "H3-FIELDS",
            "H3-ALIGN",
            "H3-SHOTS",
            "H3-REF",
            "H3-RETENTION",
            "H3-DIALOGUE",
            "H3-SPEAKER",
            "H3-LEAK",
        ),
        unverified=tuple(dict.fromkeys(unverified)),
    )


def _normalized_mode(value: Any) -> Literal["t2v", "i2v", "fl2v", "r2v"] | None:
    if not isinstance(value, str):
        return None
    aliases: dict[str, Literal["t2v", "i2v", "fl2v", "r2v"]] = {
        "t2v": "t2v",
        "t2va": "t2v",
        "video.text_to_video": "t2v",
        "i2v": "i2v",
        "i2va": "i2v",
        "video.image_to_video": "i2v",
        "fl2v": "fl2v",
        "fl2va": "fl2v",
        "video.first_last_frame": "fl2v",
        "r2v": "r2v",
        "ref2v": "r2v",
        "ref2va": "r2v",
        "video.reference_to_video": "r2v",
    }
    return aliases.get(value.strip().lower())


def _mask_dialogue_content(text: str) -> tuple[str, list[tuple[int, int, str]]]:
    """Hide dialogue bodies from structural parsing while retaining newlines."""

    masked = list(text)
    matches: list[tuple[int, int, str]] = []
    for match in _DIALOGUE_PATTERN.finditer(text):
        matches.append((match.start(), match.end(), match.group("content")))
        for index in range(match.start("content"), match.end("content")):
            if masked[index] not in "\r\n":
                masked[index] = "x"

    open_positions = [match.start() for match in _DIALOGUE_OPEN.finditer(text)]
    close_positions = [match.start() for match in _DIALOGUE_CLOSE.finditer(text)]
    if len(open_positions) > len(close_positions):
        for index in range(open_positions[-1], len(masked)):
            if masked[index] not in "\r\n":
                masked[index] = "x"
    return "".join(masked), matches


def _check_dialogue_markup(text: str, dialogues: Sequence[tuple[int, int, str]]) -> list[Finding]:
    findings: list[Finding] = []
    if not _dialogue_tags_are_well_formed(text):
        findings.append(Finding("H3-DIALOGUE", "error", "<d> 标签必须按顺序成对闭合并且不得嵌套。"))
    for start, _, content in dialogues:
        if not re.match(r"^\[[^\]\r\n]+\]", content):
            findings.append(
                Finding(
                    "H3-DIALOGUE",
                    "error",
                    "每个 <d> 必须以非空语言标签开头, 例如 [Chinese]。",
                    _line_number(text, start),
                )
            )
    return findings


def _dialogue_tags_are_well_formed(text: str) -> bool:
    is_open = False
    for match in _DIALOGUE_TAG.finditer(text):
        if match.group() == "<d>":
            if is_open:
                return False
            is_open = True
        elif not is_open:
            return False
        else:
            is_open = False
    return not is_open


def _parse_fields(
    prompt: str, masked_prompt: str, expected: Sequence[str]
) -> tuple[dict[str, _Field], list[Finding]]:
    raw_lines = prompt.splitlines()
    masked_lines = masked_prompt.splitlines()
    occurrences: list[tuple[str, int]] = []
    for index, line in enumerate(masked_lines):
        match = _FIELD_PATTERN.match(line)
        if match:
            occurrences.append((match.group("name"), index))

    findings: list[Finding] = []
    actual = [name for name, _ in occurrences]
    if actual != list(expected):
        findings.append(
            Finding(
                "H3-FIELDS",
                "error",
                f"字段必须且只能按顺序出现: {' → '.join(expected)}。",
            )
        )

    fields: dict[str, _Field] = {}
    for occurrence_index, (name, line_index) in enumerate(occurrences):
        if name in fields:
            continue
        next_line = (
            occurrences[occurrence_index + 1][1]
            if occurrence_index + 1 < len(occurrences)
            else len(raw_lines)
        )
        line_match = _FIELD_PATTERN.match(raw_lines[line_index])
        assert line_match is not None
        value_lines = [line_match.group("rest").lstrip()]
        value_lines.extend(raw_lines[line_index + 1 : next_line])
        value = "\n".join(value_lines).strip()
        fields[name] = _Field(name, value, line_index + 1, line_index + 1)
        if not value:
            findings.append(Finding("H3-FIELDS", "error", f"字段 {name} 不能为空。", line_index + 1))
    return fields, findings


def _duration_milliseconds(parameters: Any, findings: list[Finding]) -> int | None:
    if not isinstance(parameters, Mapping):
        findings.append(Finding("H3-SHOTS", "error", "快照缺少有效的 duration 参数。"))
        return None
    value = parameters.get("duration")
    if isinstance(value, bool) or value is None:
        findings.append(Finding("H3-SHOTS", "error", "duration 必须是正数。"))
        return None
    try:
        duration = Decimal(str(value))
    except (InvalidOperation, ValueError):
        findings.append(Finding("H3-SHOTS", "error", "duration 必须是正数。"))
        return None
    if not duration.is_finite() or duration <= 0:
        findings.append(Finding("H3-SHOTS", "error", "duration 必须是正数。"))
        return None
    milliseconds = duration * Decimal("1000")
    if milliseconds != milliseconds.to_integral_value():
        findings.append(Finding("H3-SHOTS", "error", "duration 必须精确到毫秒。"))
        return None
    return int(milliseconds)


def _check_shots(field: _Field, duration_ms: int | None, findings: list[Finding]) -> int:
    masked_description, _ = _mask_dialogue_content(field.value)
    matches = list(_SHOT_PATTERN.finditer(masked_description))
    if not matches:
        findings.append(Finding("H3-SHOTS", "error", "主描述段必须从 [Shot 1] 开始。", field.line))
        return 0
    numbers = [int(match.group("number")) for match in matches]
    if numbers != list(range(1, len(numbers) + 1)):
        findings.append(Finding("H3-SHOTS", "error", "Shot 编号必须从 1 连续递增。", field.line))

    first_prefix = field.value[: matches[0].start()]
    if first_prefix.strip():
        findings.append(Finding("H3-SHOTS", "error", "主描述段必须从 [Shot 1] 开始。", field.line))

    previous_cut: int | None = None
    for index, match in enumerate(matches):
        line = field.value_line + masked_description[: match.start()].count("\n")
        end = matches[index + 1].start() if index + 1 < len(matches) else None
        following = masked_description[match.end() : end]
        if index == 0:
            if re.match(r"\s*(?:At|From)\s+\d{2}:\d{2}\.\d{3}\b", following):
                findings.append(Finding("H3-SHOTS", "error", "[Shot 1] 不得包含时间码。", line))
            continue
        timestamp = re.match(r"\s*At\s+(\d{2}):(\d{2})\.(\d{3}),", following)
        if timestamp is None:
            findings.append(
                Finding("H3-SHOTS", "error", f"[Shot {index + 1}] 必须使用 At MM:SS.mmm 时间码。", line)
            )
            continue
        minutes, seconds, milliseconds = (int(group) for group in timestamp.groups())
        if seconds >= 60:
            findings.append(Finding("H3-SHOTS", "error", "时间码的秒数必须小于 60。", line))
            continue
        cut = (minutes * 60 + seconds) * 1000 + milliseconds
        if cut <= 0 or duration_ms is None or cut >= duration_ms:
            findings.append(Finding("H3-SHOTS", "error", "切点必须严格位于视频时长内部。", line))
        if previous_cut is not None and cut <= previous_cut:
            findings.append(Finding("H3-SHOTS", "error", "切点必须严格递增。", line))
        previous_cut = cut
    return len(matches)


def _check_alignment(
    mode: Literal["t2v", "i2v", "fl2v", "r2v"],
    prompt: str,
    fields: Mapping[str, _Field],
    shot_count: int,
    duration_ms: int | None,
    inputs: Mapping[str, Any],
    findings: list[Finding],
) -> None:
    lines = prompt.splitlines()
    first_line = lines[0] if lines else ""
    first_field_line = min((field.line for field in fields.values()), default=1)
    if mode == "i2v":
        expected = (
            "For the target video, at 0.00 seconds into the target video, "
            "<Picture 1> (from [Shot 1]) is fully referenced."
        )
        if first_line != expected or len(lines) < 3 or lines[1] != "" or first_field_line != 3:
            findings.append(Finding("H3-ALIGN", "error", "I2V 首行必须使用当前基础格式的首帧对齐指令。", 1))
        if not inputs.get("first_frame"):
            findings.append(Finding("H3-REF", "error", "I2V 必须有实际 first_frame 输入。"))
    elif mode == "fl2v":
        if duration_ms is None or shot_count == 0:
            return
        seconds = Decimal(duration_ms) / Decimal("1000")
        expected = (
            "How the reference pictures align with the target video — Picture 1 (from Shot 1) "
            "aligns with the 0.00-second mark of the target video; "
            f"Picture 2 (from Shot {shot_count}) aligns with the {seconds:.2f}-second mark of "
            "the target video."
        )
        if first_line != expected or len(lines) < 3 or lines[1] != "" or first_field_line != 3:
            findings.append(Finding("H3-ALIGN", "error", "FL2V 首行必须匹配末镜和实际时长。", 1))
        if not inputs.get("first_frame") or not inputs.get("last_frame"):
            findings.append(Finding("H3-REF", "error", "FL2V 必须有实际 first_frame 和 last_frame 输入。"))
    elif mode in {"t2v", "r2v"} and first_field_line > 1:
        findings.append(Finding("H3-ALIGN", "error", "该模式不得使用基础模式的首帧对齐首行。", 1))


def _check_references(
    mode: Literal["t2v", "i2v", "fl2v", "r2v"],
    fields: Mapping[str, _Field],
    inputs: Mapping[str, Any],
    parameters: Any,
    masked_prompt: str,
    findings: list[Finding],
    unverified: list[str],
) -> None:
    slot_counts = _slot_counts(mode, inputs)
    frame_zero_guide = isinstance(parameters, Mapping) and bool(parameters.get("frame_zero_video_guide"))
    if frame_zero_guide:
        unverified.append(
            "未验证: frame_zero_video_guide 改变视频/音频参考用途, 未对其槽位完整性作结论。"
        )

    subject_definitions = fields.get("subject_definitions")
    defined_subjects: set[int] = set()
    if subject_definitions:
        for match in re.finditer(r"(?m)^\s*<Subject ([1-9]\d*)>\s+is\b", subject_definitions.value):
            number = int(match.group(1))
            if number in defined_subjects:
                findings.append(
                    Finding("H3-REF", "error", f"<Subject {number}> 只能定义一次。", subject_definitions.line)
                )
            defined_subjects.add(number)

    for match in _REFERENCE_PATTERN.finditer(masked_prompt):
        category, raw_number = match.groups()
        number = int(raw_number)
        line = _line_number(masked_prompt, match.start())
        if number < 1:
            findings.append(Finding("H3-REF", "error", f"<{category} {number}> 编号必须从 1 开始。", line))
            continue
        if category == "Subject":
            if subject_definitions and number not in defined_subjects:
                findings.append(Finding("H3-REF", "error", f"<Subject {number}> 缺少定义。", line))
            continue
        if frame_zero_guide and category in {"Video", "Audio"}:
            continue
        if number > slot_counts[category]:
            findings.append(
                Finding("H3-REF", "error", f"<{category} {number}> 没有对应的实际输入槽位。", line)
            )


def _slot_counts(mode: Literal["t2v", "i2v", "fl2v", "r2v"], inputs: Mapping[str, Any]) -> dict[str, int]:
    def count_sequence(key: str) -> int:
        value = inputs.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return len(value)
        return 0

    picture_count = 0
    if mode == "i2v" and inputs.get("first_frame"):
        picture_count = 1
    elif mode == "fl2v":
        picture_count = int(bool(inputs.get("first_frame"))) + int(bool(inputs.get("last_frame")))
    elif mode == "r2v":
        picture_count = count_sequence("reference_images")
    return {
        "Picture": picture_count,
        "Video": count_sequence("reference_videos") if mode == "r2v" else 0,
        "Audio": count_sequence("reference_audios") if mode == "r2v" else 0,
    }


def _standalone_reference_labels(field: _Field | None) -> set[tuple[str, int]]:
    if field is None:
        return set()
    return {
        (match.group(1), int(match.group(2)))
        for match in _REFERENCE_DEFINITION_PATTERN.finditer(field.value)
    }


def _check_retention(
    field: _Field | None,
    required_labels: set[tuple[str, int]],
    findings: list[Finding],
) -> None:
    if field is None:
        for category, number in sorted(required_labels):
            findings.append(
                Finding(
                    "H3-RETENTION",
                    "error",
                    f"retention_analysis 缺少 <{category} {number}> 条目。",
                )
            )
        return
    seen_labels: set[tuple[str, int]] = set()
    for offset, line in enumerate(field.value.splitlines()):
        if not line.strip():
            continue
        if _SPEAKER_PATTERN.search(line):
            findings.append(
                Finding("H3-RETENTION", "error", "retention_analysis 不能包含 S 编号。", field.value_line + offset)
            )
        match = _RETENTION_LINE.match(line)
        if match is None:
            findings.append(
                Finding("H3-RETENTION", "error", "retention_analysis 行必须使用引用标签和固定枚举。", field.value_line + offset)
            )
            continue
        category, raw_number, marker, _ = match.groups()
        label = (category, int(raw_number))
        if label in seen_labels:
            findings.append(
                Finding(
                    "H3-RETENTION",
                    "error",
                    f"retention_analysis 中 <{category} {raw_number}> 只能出现一次。",
                    field.value_line + offset,
                )
            )
        seen_labels.add(label)
        allowed = _AUDIO_RETENTION if category == "Audio" else _VISIBLE_RETENTION
        if marker not in allowed:
            findings.append(
                Finding("H3-RETENTION", "error", f"{category} 不接受 retention 枚举 {marker}。", field.value_line + offset)
            )
    for category, number in sorted(required_labels - seen_labels):
        findings.append(
            Finding(
                "H3-RETENTION",
                "error",
                f"retention_analysis 缺少 <{category} {number}> 条目。",
            )
        )


def _check_dialogue_in_sound_fields(fields: Mapping[str, _Field], findings: list[Finding]) -> None:
    for name in ("overall_soundscape", "non_diegetic_music"):
        field = fields.get(name)
        if field and ("<d>" in field.value or "</d>" in field.value):
            findings.append(Finding("H3-DIALOGUE", "error", f"{name} 不得包含完整对白或歌词。", field.line))


def _check_speakers(field: _Field | None, findings: list[Finding], unverified: list[str]) -> None:
    if field is None:
        return
    masked, dialogues = _mask_dialogue_content(field.value)
    speaker_matches = list(_SPEAKER_PATTERN.finditer(masked))
    if dialogues and not speaker_matches:
        unverified.append("未验证: 对白存在, 但提示词没有可解析的实际发声 S 编号。")
        return
    next_number = 1
    seen: set[int] = set()
    for match in speaker_matches:
        line = field.value_line + masked[: match.start()].count("\n")
        for raw_number in re.findall(r"S([0-9]+)", match.group("numbers")):
            number = int(raw_number)
            if number < 1:
                findings.append(Finding("H3-SPEAKER", "error", "S 编号必须从 S1 开始。", line))
                continue
            if number not in seen:
                if number != next_number:
                    findings.append(
                        Finding("H3-SPEAKER", "error", "新出现的 S 编号必须按实际发声顺序连续。", line)
                    )
                seen.add(number)
                next_number += 1


def _check_leaks(masked_prompt: str, findings: list[Finding]) -> None:
    if "```" in masked_prompt:
        findings.append(Finding("H3-LEAK", "error", "提示词正文不得包含 Markdown 代码围栏。"))
    match = _LEGACY_FIELD_PATTERN.search(masked_prompt)
    if match:
        findings.append(
            Finding("H3-LEAK", "error", "提示词正文混入旧版分段字段。", _line_number(masked_prompt, match.start()))
        )
    match = _ASSET_ANCHOR_PATTERN.search(masked_prompt)
    if match:
        findings.append(Finding("H3-LEAK", "error", "提示词正文不得使用旧资产锚点。", _line_number(masked_prompt, match.start())))


def _check_plan(
    snapshot: Mapping[str, Any],
    mode: Literal["t2v", "i2v", "fl2v", "r2v"],
    fields: Mapping[str, _Field],
    blueprint: Mapping[str, Any] | None,
    panel_id: str | None,
    duration_ms: int | None,
    shot_count: int,
    findings: list[Finding],
    unverified: list[str],
) -> None:
    if blueprint is None and panel_id is None:
        unverified.append("未验证: 未提供蓝图, 未核对上游 Panel、镜头和锁定对白。")
        return
    if blueprint is None or not isinstance(panel_id, str) or not panel_id:
        unverified.append("未验证: 蓝图和 panel_id 必须同时提供才会进行计划比对。")
        return

    if not isinstance(blueprint, Mapping):
        findings.append(Finding("PLAN-MATCH", "error", "蓝图必须是对象。"))
        return
    panels = _strict_mapping_items(blueprint.get("panels"), "panels", findings)
    matched_panels = [panel for panel in panels if panel.get("id") == panel_id]
    if len(matched_panels) != 1:
        findings.append(Finding("PLAN-MATCH", "error", f"蓝图必须恰好包含一个 Panel {panel_id}。"))
        return
    panel = matched_panels[0]
    generation = blueprint.get("generation")
    if not isinstance(generation, Mapping):
        findings.append(Finding("PLAN-MATCH", "error", "蓝图缺少 generation 计划。"))
        return
    plans = _strict_mapping_items(generation.get("panel_plans"), "generation.panel_plans", findings)
    matched_plans = [plan for plan in plans if plan.get("panel_id") == panel_id]
    if len(matched_plans) != 1:
        findings.append(Finding("PLAN-MATCH", "error", f"Panel {panel_id} 必须恰好有一个 generation plan。"))
        return
    expected_operation = {
        "t2v": "video.text_to_video",
        "i2v": "video.image_to_video",
        "fl2v": "video.first_last_frame",
        "r2v": "video.reference_to_video",
    }[mode]
    if matched_plans[0].get("operation") != expected_operation:
        findings.append(Finding("PLAN-MATCH", "error", "Canvas 模式与蓝图 operation 不一致。"))

    plan_duration_ms = _decimal_milliseconds(panel.get("duration_s"))
    if plan_duration_ms is None or duration_ms is None or plan_duration_ms != duration_ms:
        findings.append(Finding("PLAN-MATCH", "error", "Canvas duration 与蓝图 Panel 时长不一致。"))

    shot_ids = _strict_string_items(panel.get("shot_ids"), "panels.shot_ids", findings)
    if not shot_ids or len(shot_ids) != shot_count:
        findings.append(Finding("PLAN-MATCH", "error", "提示词 Shot 数量与蓝图 Panel 不一致。"))
        return
    shots = _strict_mapping_items(generation.get("shots"), "generation.shots", findings)
    # Blueprint orders are global; prompt Shot numbers restart within each Panel.
    orders = [shot.get("order") for shot in shots]
    if any(type(order) is not int for order in orders) or sorted(orders) != list(range(1, len(shots) + 1)):
        findings.append(Finding("PLAN-MATCH", "error", "蓝图 Shot 全局顺序必须从 1 连续编号。"))
        return
    ordered_panel_ids = [
        shot.get("id")
        for shot in sorted(shots, key=lambda shot: shot["order"])
        if shot.get("panel_id") == panel_id
    ]
    if ordered_panel_ids != shot_ids:
        findings.append(Finding("PLAN-MATCH", "error", "蓝图 Shot 归属或顺序与 Panel 不一致。"))
        return
    plan_shots: list[Mapping[str, Any]] = []
    for shot_id in shot_ids:
        matched_shots = [
            shot
            for shot in shots
            if shot.get("id") == shot_id and shot.get("panel_id") == panel_id
        ]
        if len(matched_shots) != 1:
            findings.append(Finding("PLAN-MATCH", "error", "蓝图 Shot 归属或顺序与 Panel 不一致。"))
            return
        plan_shots.append(matched_shots[0])

    description = fields.get("detailed_description") or fields.get("integrated_multimodal_description")
    if shot_count > 1:
        unverified.append("未验证: 蓝图 v2 没有结构化镜头切点, 未比较导演计划的准确秒数。")
    if description and (_DIALOGUE_PATTERN.search(description.value) or _SPEAKER_PATTERN.search(description.value)):
        unverified.append("未验证: 蓝图未提供角色与 (Sx) 的结构化绑定, 未确认说话人身份。")
    if description is not None:
        _check_plan_dialogue(description, shot_ids, plan_shots, blueprint, findings, unverified)


def _mapping_items(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _strict_mapping_items(
    value: Any, field_name: str, findings: list[Finding]
) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        findings.append(Finding("PLAN-MATCH", "error", f"蓝图 {field_name} 必须是数组。"))
        return []
    if not all(isinstance(item, Mapping) for item in value):
        findings.append(Finding("PLAN-MATCH", "error", f"蓝图 {field_name} 的每项必须是对象。"))
        return []
    return list(value)


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [item for item in value if isinstance(item, str)]


def _strict_string_items(value: Any, field_name: str, findings: list[Finding]) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        findings.append(Finding("PLAN-MATCH", "error", f"蓝图 {field_name} 必须是字符串数组。"))
        return []
    if not all(isinstance(item, str) for item in value):
        findings.append(Finding("PLAN-MATCH", "error", f"蓝图 {field_name} 必须只包含字符串。"))
        return []
    return list(value)


def _decimal_milliseconds(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        milliseconds = Decimal(str(value)) * Decimal("1000")
    except (InvalidOperation, ValueError):
        return None
    if not milliseconds.is_finite() or milliseconds <= 0:
        return None
    if milliseconds != milliseconds.to_integral_value():
        return None
    return int(milliseconds)


def _check_plan_dialogue(
    description: _Field,
    shot_ids: Sequence[str],
    plan_shots: Sequence[Mapping[str, Any]],
    blueprint: Mapping[str, Any],
    findings: list[Finding],
    unverified: list[str],
) -> None:
    if "<scenetrans>" in description.value or "<cutoff>" in description.value:
        unverified.append("未验证: 跨镜或 cutoff 对白无法唯一归属, 未猜测拼接结果。")
        return
    dialogue_entries = {
        item.get("id"): item
        for item in _strict_mapping_items(blueprint.get("dialogue"), "dialogue", findings)
        if isinstance(item.get("id"), str)
    }
    expected_by_shot: list[list[str]] = []
    for shot_id, plan_shot in zip(shot_ids, plan_shots, strict=True):
        dialogue_ids = _strict_string_items(
            plan_shot.get("dialogue_ids"),
            f"shot {shot_id}.dialogue_ids",
            findings,
        )
        expected: list[str] = []
        for dialogue_id in dialogue_ids:
            entry = dialogue_entries.get(dialogue_id)
            if not isinstance(entry, Mapping) or entry.get("shot_id") != shot_id:
                findings.append(Finding("PLAN-DIALOGUE", "error", "蓝图对白与 Shot 的归属不一致。", description.line))
                return
            text = entry.get("text")
            if not isinstance(text, str):
                findings.append(Finding("PLAN-DIALOGUE", "error", "蓝图锁定对白必须是文本。", description.line))
                return
            expected.append(text)
        expected_by_shot.append(expected)

    actual_by_shot: list[list[str]] = [[] for _ in shot_ids]
    masked_description, _ = _mask_dialogue_content(description.value)
    shot_matches = list(_SHOT_PATTERN.finditer(masked_description))
    for dialogue in _DIALOGUE_PATTERN.finditer(description.value):
        shot_number = _current_shot_number(shot_matches, dialogue.start())
        if shot_number is None or shot_number > len(actual_by_shot):
            unverified.append("未验证: 对白不在可解析的当前 Shot 内。")
            continue
        content = dialogue.group("content")
        language = re.match(r"^\[[^\]\r\n]+\](?P<text>.*)$", content, re.DOTALL)
        if language is None:
            continue
        actual_by_shot[shot_number - 1].append(language.group("text").removeprefix(" "))

    for index, (expected, actual) in enumerate(zip(expected_by_shot, actual_by_shot, strict=True), start=1):
        if expected != actual:
            findings.append(
                Finding(
                    "PLAN-DIALOGUE",
                    "error",
                    f"[Shot {index}] 的锁定对白与蓝图文本、标点或顺序不一致。",
                    description.line,
                )
            )


def _current_shot_number(matches: Sequence[re.Match[str]], position: int) -> int | None:
    current: int | None = None
    for match in matches:
        if match.start() >= position:
            break
        current = int(match.group("number"))
    return current


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1

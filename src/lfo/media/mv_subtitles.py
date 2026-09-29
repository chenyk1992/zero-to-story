"""Aspect-aware ASS lyric and intentional visual-text serialization."""

from __future__ import annotations

import re
from typing import Any


def _time(milliseconds: int) -> str:
    centiseconds = round(milliseconds / 10)
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    seconds, centis = divmod(remainder, 100)
    return f"{hours}:{minutes:02}:{seconds:02}.{centis:02}"


def _text(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    # ASS treats \N, \n and \h as control sequences. A word joiner prevents
    # interpretation while leaving the original backslash visibly unchanged.
    normalized = re.sub(r"\\(?=[Nnh])", lambda _match: "\\\u2060", normalized)
    return normalized.replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def render_ass(cues: list[dict[str, Any]], *, width: int, height: int) -> str:
    if isinstance(width, bool) or isinstance(height, bool) or not isinstance(width, int) or not isinstance(height, int) or min(width, height) < 64:
        raise ValueError("字幕画幅无效")
    font_size = max(22, round(height * 0.043))
    margin_x = round(width * 0.07)
    margin_y = round(height * 0.07)
    header = (
        "[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\n"
        f"PlayResX: {width}\nPlayResY: {height}\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Lyric,Microsoft YaHei,{font_size},&H00FFFFFF,&H00FFFFFF,&H90000000,&H60000000,0,0,0,0,100,100,0,0,1,2,0,2,{margin_x},{margin_x},{margin_y},1\n"
        f"Style: Visual,Microsoft YaHei,{round(font_size * 1.15)},&H00FFFFFF,&H00FFFFFF,&H90000000,&H60000000,0,0,0,0,100,100,0,0,1,2,0,5,{margin_x},{margin_x},{margin_y},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines = []
    for cue in cues:
        if not isinstance(cue, dict):
            raise ValueError("文字事件必须是对象")
        start, end = cue.get("start_ms"), cue.get("end_ms")
        if isinstance(start, bool) or isinstance(end, bool) or not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
            raise ValueError("文字事件时间无效")
        content = cue.get("text")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("文字事件缺少原文")
        kind = cue.get("kind", "lyric")
        if kind not in {"lyric", "visual"}:
            raise ValueError("文字事件类型无效")
        if kind == "lyric" and cue.get("status") != "verified":
            raise ValueError("歌词时间须先核对")
        effect = cue.get("effect", "none")
        duration = end - start
        if effect == "none":
            tag = ""
        elif effect == "fade":
            fade = min(180, duration // 4)
            tag = r"{\fad(" + f"{fade},{fade}" + ")}"
        elif effect == "scale":
            tag = r"{\fscx90\fscy90\t(0," + str(duration) + r",\fscx100\fscy100)}"
        else:
            raise ValueError("文字动效不受支持")
        lines.append(f"Dialogue: 0,{_time(start)},{_time(end)},{'Lyric' if kind == 'lyric' else 'Visual'},,0,0,0,,{tag}{_text(content)}")
    return header + "\n".join(lines) + ("\n" if lines else "")

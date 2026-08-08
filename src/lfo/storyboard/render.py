"""LFO Storyboard Markdown renderer.

Renders storyboard JSON to human-readable Markdown for review.
Markdown is a read-only view — edits go through structured patches, not MD.
"""
from __future__ import annotations

from .intake import Intake
from .storyboard import Beat, Panel, Storyboard


def render_intake_md(intake: Intake) -> str:
    """Render an Intake to Markdown for review."""
    lines: list[str] = []
    lines.append("# 项目输入 (Intake)")
    lines.append("")
    lines.append(f"**项目 ID**: `{intake.project_id}`")
    lines.append(f"**Schema**: {intake.schema_version}")
    lines.append("")

    # Sources
    lines.append("## 输入源")
    lines.append("")
    for src in intake.sources:
        lines.append(f"### {src.source_id} ({src.type})")
        lines.append("")
        lines.append(src.content)
        lines.append("")

    # Constraints
    c = intake.constraints
    lines.append("## 约束条件")
    lines.append("")
    lines.append("| 参数 | 值 |")
    lines.append("|------|-----|")
    lines.append(f"| 目标时长 | {c.target_duration_ms}ms ({c.target_duration_ms / 1000:.1f}s) |")
    lines.append(f"| 画幅比 | {c.aspect_ratio} |")
    lines.append(f"| 输出分辨率 | {c.delivery_width}x{c.delivery_height} |")
    lines.append(f"| 语言 | {c.language} |")
    if c.visual_style:
        lines.append(f"| 视觉风格 | {c.visual_style} |")
    lines.append(f"| 最大角色数 | {c.max_characters} |")
    lines.append(f"| 最大场景数 | {c.max_scenes} |")
    if c.mood:
        lines.append(f"| 情绪 | {c.mood} |")
    if c.pacing:
        lines.append(f"| 节奏 | {c.pacing} |")
    lines.append("")

    return "\n".join(lines)


def render_storyboard_md(sb: Storyboard) -> str:
    """Render a Storyboard to Markdown for human review."""
    lines: list[str] = []

    # Title
    title = sb.project.title or sb.project.project_id
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"**项目 ID**: `{sb.project.project_id}`")
    lines.append(f"**版本**: {sb.project.revision}")
    if sb.project.content_hash:
        lines.append(f"**内容 Hash**: `{sb.project.content_hash[:16]}...`")
    lines.append(f"**审阅状态**: {_review_status_cn(sb.review.status)}")
    lines.append("")

    # Story
    if sb.story.logline or sb.story.synopsis:
        lines.append("## 故事")
        lines.append("")
        if sb.story.logline:
            lines.append(f"**Logline**: {sb.story.logline}")
            lines.append("")
        if sb.story.synopsis:
            lines.append(sb.story.synopsis)
            lines.append("")
        if sb.story.theme:
            lines.append(f"**主题**: {sb.story.theme}")
            lines.append("")
        if sb.story.emotional_arc:
            lines.append(f"**情感弧线**: {sb.story.emotional_arc}")
            lines.append("")

    # Style
    if sb.style.visual_style:
        lines.append("## 视觉风格")
        lines.append("")
        lines.append(f"- **风格**: {sb.style.visual_style}")
        if sb.style.color_palette:
            lines.append(f"- **色调**: {sb.style.color_palette}")
        if sb.style.lighting:
            lines.append(f"- **光线**: {sb.style.lighting}")
        if sb.style.mood:
            lines.append(f"- **情绪**: {sb.style.mood}")
        lines.append("")

    # Characters
    if sb.characters:
        lines.append("## 角色")
        lines.append("")
        for char in sb.characters:
            lines.append(f"### {char.name or char.character_id}")
            lines.append("")
            if char.description:
                lines.append(f"_{char.description}_")
                lines.append("")
            meta_parts = []
            if char.role:
                meta_parts.append(f"**角色**: {char.role}")
            if char.age:
                meta_parts.append(f"**年龄**: {char.age}")
            if char.gender:
                meta_parts.append(f"**性别**: {char.gender}")
            if char.distinguishing_features:
                meta_parts.append(f"**特征**: {char.distinguishing_features}")
            if meta_parts:
                lines.append(" | ".join(meta_parts))
                lines.append("")

    # Scenes
    if sb.scenes:
        lines.append("## 场景")
        lines.append("")
        for scene in sb.scenes:
            lines.append(f"### {scene.name or scene.scene_id}")
            lines.append("")
            if scene.description:
                lines.append(f"_{scene.description}_")
                lines.append("")
            meta_parts = []
            if scene.environment:
                meta_parts.append(f"**环境**: {scene.environment}")
            if scene.time_of_day:
                meta_parts.append(f"**时间**: {scene.time_of_day}")
            if scene.lighting:
                meta_parts.append(f"**光线**: {scene.lighting}")
            if meta_parts:
                lines.append(" | ".join(meta_parts))
                lines.append("")

    # Beats
    if sb.beats:
        lines.append("## 节拍")
        lines.append("")
        for beat in sb.beats:
            lines.append(_render_beat_md(beat, sb))
            lines.append("")

    # Panels
    lines.append("## 分镜面板")
    lines.append("")
    for panel in sb.panels:
        lines.append(_render_panel_md(panel, sb))
        lines.append("")

    # Continuity Chains
    if sb.continuity_chains:
        lines.append("## 连续性链")
        lines.append("")
        for chain in sb.continuity_chains:
            lines.append(f"- **{chain.chain_id}**: {', '.join(chain.shot_ids)}")
            if chain.shared_elements:
                lines.append(f"  - 共享元素: {', '.join(chain.shared_elements)}")
        lines.append("")

    # Audio Policy
    if sb.audio_policy and sb.audio_policy.mode != "none":
        lines.append("## 音频策略")
        lines.append("")
        a = sb.audio_policy
        lines.append(f"- **模式**: {a.mode}")
        lines.append(f"- **音乐**: {a.music}")
        lines.append(f"- **音效**: {a.sound_effects}")
        lines.append(f"- **对白**: {a.dialogue}")
        lines.append("")

    # Review
    if sb.review.status != "pending" or sb.review.notes:
        lines.append("## 审阅记录")
        lines.append("")
        lines.append(f"- **状态**: {_review_status_cn(sb.review.status)}")
        if sb.review.reviewer:
            lines.append(f"- **审阅人**: {sb.review.reviewer}")
        if sb.review.approved_at:
            lines.append(f"- **审阅时间**: {sb.review.approved_at}")
        if sb.review.notes:
            lines.append(f"- **备注**: {sb.review.notes}")
        lines.append("")

    return "\n".join(lines)


def _render_beat_md(beat: Beat, sb: Storyboard) -> str:
    """Render a single beat to Markdown."""
    lines: list[str] = []
    lines.append(f"### Beat {beat.sequence} (`{beat.beat_id}`)")
    lines.append("")

    if beat.description:
        lines.append(f"_{beat.description}_")
        lines.append("")

    if beat.framing:
        lines.append(f"**景别**: {beat.framing}")
        lines.append("")

    if beat.dialogue:
        lines.append(f"**对白**: {beat.dialogue}")
        lines.append("")

    if beat.sound:
        lines.append(f"**声音**: {beat.sound}")
        lines.append("")

    if beat.characters:
        lines.append("**角色**:")
        for char_app in beat.characters:
            char = sb.character_by_id(char_app.character_id)
            char_name = char.name if char else char_app.character_id
            parts = [char_name]
            if char_app.screen_position:
                parts.append(f"位置: {char_app.screen_position}")
            if char_app.action:
                parts.append(f"动作: {char_app.action}")
            if char_app.expression:
                parts.append(f"表情: {char_app.expression}")
            lines.append(f"- {' | '.join(parts)}")
        lines.append("")

    return "\n".join(lines)


def _render_panel_md(panel: Panel, sb: Storyboard) -> str:
    """Render a single panel to Markdown."""
    idx = sb.display_index_for_panel(panel.panel_id)
    lines: list[str] = []

    lines.append(f"### Panel {idx} (`{panel.panel_id}`)")
    lines.append("")
    lines.append(
        f"**时长**: {panel.desired_duration_ms}ms ({panel.desired_duration_ms / 1000:.1f}s)"
    )
    lines.append(f"**节拍范围**: {panel.beat_range[0]}–{panel.beat_range[1]}")
    if panel.beat_ids:
        lines.append(f"**节拍**: {', '.join(panel.beat_ids)}")
    lines.append("")

    if panel.prompt_text:
        lines.append(f"**提示词**: {panel.prompt_text}")
        lines.append("")

    return "\n".join(lines)


def _review_status_cn(status: str) -> str:
    """Translate review status to Chinese."""
    return {
        "pending": "待审阅",
        "approved": "已批准",
        "rejected": "已拒绝",
    }.get(status, status)

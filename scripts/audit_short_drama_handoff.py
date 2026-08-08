"""Simulate short-drama → handoff → workspace checks (no LFO storyboard.json)."""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lfo.storyboard.intake import Intake  # noqa: E402
from lfo.storyboard.validate import validate_intake  # noqa: E402

DRAMA = ROOT / ".short-drama" / "午夜不接单"
SKILL_REFS = ROOT / ".agents" / "skills" / "short-drama-screenwriter" / "references"


def main() -> int:
    errors: list[str] = []
    warns: list[str] = []

    # 1) State + creative chain
    state = json.loads((DRAMA / ".drama-state.json").read_text(encoding="utf-8"))
    for key in ("currentStep", "genre", "completedEpisodes", "dramaTitle", "totalEpisodes"):
        if key not in state:
            errors.append(f"state missing {key}")
    if state.get("dramaTitle") != "午夜不接单":
        errors.append("dramaTitle mismatch")
    if 1 not in state.get("bridgedEpisodes", []):
        errors.append("bridgedEpisodes missing 1")
    for rel in (
        "creative-plan.md",
        "characters.md",
        "episode-directory.md",
        "episodes/ep001.md",
        "episodes/ep002.md",
        "episodes/ep003.md",
        "episodes/ep004.md",
    ):
        if not (DRAMA / rel).exists():
            errors.append(f"missing {rel}")

    # 2) Handoff package
    for rel in (
        "handoff/project.json",
        "handoff/characters_visual.md",
        "handoff/ep001/storyboard_brief.md",
        "handoff/ep001/intake.json",
        "handoff/ep001/cut_notes.md",
    ):
        if not (DRAMA / rel).exists():
            errors.append(f"missing {rel}")

    proj = json.loads((DRAMA / "handoff" / "project.json").read_text(encoding="utf-8"))
    if proj.get("novel_id") != "午夜不接单" and proj.get("drama_title") != "午夜不接单":
        errors.append("project.json novel/drama title missing")
    hint = proj.get("workspace_copy_hint", "")
    if "午夜不接单" not in hint or "chapter_" not in hint:
        errors.append(f"bad workspace_copy_hint: {hint}")
    if "midnight_no_orders" in json.dumps(proj, ensure_ascii=False):
        errors.append("legacy midnight_no_orders in project.json")
    if "project_id" in proj and "chapter_" not in str(proj.get("project_id", "")):
        # legacy field ok only if chapter-styled; prefer novel_id
        warns.append("project.json still has project_id; prefer novel_id + per-chapter intake project_id")

    # 3–5) Per bridged episode: intake + brief + workspace copy
    bridged = state.get("bridgedEpisodes") or []
    shot_nums: list[int] = []
    last_intake_valid = False
    for ep in bridged:
        ep_s = f"{int(ep):03d}"
        ch_s = f"{int(ep):02d}"
        ep_dir = DRAMA / "handoff" / f"ep{ep_s}"
        intake_path = ep_dir / "intake.json"
        brief_path = ep_dir / "storyboard_brief.md"
        notes_path = ep_dir / "cut_notes.md"
        for p in (intake_path, brief_path, notes_path):
            if not p.exists():
                errors.append(f"bridged ep{ep_s} missing {p.name}")
                continue

        data = json.loads(intake_path.read_text(encoding="utf-8"))
        vr = validate_intake(data)
        last_intake_valid = vr.valid
        if not vr.valid:
            errors.append(f"ep{ep_s} validate_intake failed: {vr.errors}")
        intake = Intake.from_dict(json.loads(intake_path.read_text(encoding="utf-8")))
        expected_pid = f"午夜不接单-chapter_{ch_s}"
        if intake.project_id != expected_pid:
            errors.append(f"ep{ep_s} project_id expected {expected_pid} got {intake.project_id}")
        c = intake.constraints
        if c.aspect_ratio != "9:16":
            errors.append(f"ep{ep_s} aspect {c.aspect_ratio}")
        if c.max_scenes > 2:
            errors.append(f"ep{ep_s} max_scenes {c.max_scenes}")
        if c.max_characters > 3:
            errors.append(f"ep{ep_s} max_chars {c.max_characters}")
        if c.audio_policy not in ("effects_only", "full", "none"):
            errors.append(f"ep{ep_s} bad audio_policy {c.audio_policy}")
        if intake.sources[0].type != "screenplay":
            errors.append(f"ep{ep_s} source type not screenplay")

        brief = brief_path.read_text(encoding="utf-8")
        for section in (
            "## 项目信息",
            "## 故事梗概",
            "## 角色列表",
            "## 场景列表",
            "## 分镜列表",
            "## 视觉规范",
            "Medium Lock",
            "Style Brief",
            "9:16",
        ):
            if section not in brief:
                errors.append(f"ep{ep_s} brief missing: {section}")
        shot_nums = [int(x) for x in re.findall(r"^\|\s*(\d+)\s*\|", brief, re.M)]
        target_shots = int((c.custom or {}).get("shot_count_target") or 22)
        if len(shot_nums) != target_shots:
            errors.append(f"ep{ep_s} expected {target_shots} shots, got {len(shot_nums)}")
        data_rows = [line for line in brief.splitlines() if re.match(r"^\|\s*\d+", line)]
        weak = [
            r
            for r in data_rows
            if not any(
                k in r for k in ("前景", "中景", "远景", "左侧", "右侧", "中央", "左", "右", "居中", "偏")
            )
        ]
        if weak:
            warns.append(f"ep{ep_s}: {len(weak)} shot rows may lack spatial language")
        table_part = brief.split("## 分镜列表")[1].split("## 视觉规范")[0]
        if "🎣" in table_part or "下集预告" in table_part:
            errors.append(f"ep{ep_s} hook/preview leaked into shot table")

        notes = notes_path.read_text(encoding="utf-8")
        ws_hint = f"workspace/午夜不接单/chapter_{ch_s}"
        if ws_hint not in notes:
            errors.append(f"ep{ep_s} cut_notes missing {ws_hint}")
        if "midnight_no_orders" in notes:
            errors.append(f"ep{ep_s} legacy path in cut_notes")

        dest = ROOT / "workspace" / "午夜不接单" / f"chapter_{ch_s}"
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(intake_path, dest / "intake.json")
        shutil.copy2(brief_path, dest / "storyboard_brief.md")
        copied = json.loads((dest / "intake.json").read_text(encoding="utf-8"))
        vr2 = validate_intake(copied)
        if not vr2.valid:
            errors.append(f"ep{ep_s} copied intake invalid: {vr2.errors}")

    # 6) Skill refs
    for name in (
        "handoff-mapping.md",
        "handoff-brief-template.md",
        "handoff-intake-template.json",
    ):
        if not (SKILL_REFS / name).exists():
            errors.append(f"missing ref {name}")
    tmpl = json.loads((SKILL_REFS / "handoff-intake-template.json").read_text(encoding="utf-8"))
    if "chapter_" not in tmpl.get("project_id", ""):
        errors.append(f"template project_id not chapter-styled: {tmpl.get('project_id')}")

    # 7) Skill text drift: project.json description should mention novel_id
    skill = (ROOT / ".agents" / "skills" / "short-drama-screenwriter" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    if "workspace/{project_id}/ep" in skill:
        errors.append("SKILL still documents legacy workspace/{project_id}/ep path")
    if "handoff/project.json` — `project_id`" in skill:
        warns.append("SKILL step1 still says project.json project_id; should say novel_id")

    print("=== short-drama handoff audit ===")
    print(
        f"bridged={bridged} last_shots={len(shot_nums)} "
        f"last_intake_valid={last_intake_valid} "
        f"workspace_root={ROOT / 'workspace' / '午夜不接单'}"
    )
    print(f"ERRORS ({len(errors)})")
    for e in errors:
        print(f"  E: {e}")
    print(f"WARNS ({len(warns)})")
    for w in warns:
        print(f"  W: {w}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

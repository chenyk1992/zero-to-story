"""Unit tests for the pure H3 prompt structural lint."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPT_PATH = (
    Path(__file__).parents[2]
    / ".agents"
    / "skills"
    / "h3-prompt-writing"
    / "scripts"
    / "h3_prompt_lint.py"
)
SPEC = importlib.util.spec_from_file_location("h3_prompt_lint", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

BASE = (
    "integrated_multimodal_description: [Shot 1] A woman waits by a door. "
    "[Shot 2] At 00:03.000, the camera cuts to her hand.\n\n"
    "overall_soundscape: Footsteps fade.\n\n"
    "non_diegetic_music: N/A"
)

I2V_FIRST_LINE = (
    "For the target video, at 0.00 seconds into the target video, "
    "<Picture 1> (from [Shot 1]) is fully referenced."
)
FL2V_FIRST_LINE = (
    "How the reference pictures align with the target video — Picture 1 (from Shot 1) "
    "aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 2) "
    "aligns with the 8.00-second mark of the target video."
)


def make_snapshot(
    prompt: str = BASE,
    mode: str = "t2v",
    duration: int | float = 8,
    *,
    model: str = "h3",
    inputs: dict[str, Any] | None = None,
    **parameters: Any,
) -> dict[str, Any]:
    return {
        "node_id": "video-1",
        "node_type": "video",
        "provider": "comfy",
        "model": model,
        "mode": mode,
        "prompt": prompt,
        "parameters": {"duration": duration, "aspect_ratio": "16:9", **parameters},
        "inputs": inputs
        or {
            "first_frame": None,
            "last_frame": None,
            "reference_images": [],
            "reference_videos": [],
            "reference_audios": [],
        },
    }


def errors(result: Any, code: str) -> list[Any]:
    return [finding for finding in result.findings if finding.code == code and finding.severity == "error"]


def base_with_first_line(first_line: str) -> str:
    return f"{first_line}\n\n{BASE}"


R2V = (
    "subject_definitions:\n"
    "<Subject 1> is the woman in <Picture 1>.\n"
    "<Subject 2> is the man in <Picture 1>.\n\n"
    "summary: [reference generation] <Subject 1> waits beside <Subject 2>.\n\n"
    "retention_analysis:\n"
    "<Subject 1>: fully_preserved - appearance.\n"
    "<Subject 2>: fully_preserved - appearance.\n\n"
    "detailed_description: [Shot 1] <Subject 1> and <Subject 2> sit together.\n\n"
    "overall_soundscape: Quiet room tone.\n\n"
    "non_diegetic_music: N/A"
)


def r2v_inputs(*, include_first_frame: bool = False) -> dict[str, Any]:
    return {
        "first_frame": {"path": "first.png", "kind": "image"} if include_first_frame else None,
        "last_frame": None,
        "reference_images": [{"path": "board.png", "kind": "image"}],
        "reference_videos": [],
        "reference_audios": [],
    }


def test_cut_must_be_inside_actual_duration() -> None:
    result = MODULE.lint_snapshot(make_snapshot(BASE.replace("00:03.000", "00:10.000")))
    assert errors(result, "H3-SHOTS")


def test_cut_at_end_is_invalid() -> None:
    result = MODULE.lint_snapshot(make_snapshot(BASE.replace("00:03.000", "00:08.000")))
    assert errors(result, "H3-SHOTS")


def test_long_single_shot_is_valid() -> None:
    prompt = BASE.replace("[Shot 2] At 00:03.000, the camera cuts to her hand.", "")
    result = MODULE.lint_snapshot(make_snapshot(prompt))
    assert not [finding for finding in result.findings if finding.severity == "error"]


@pytest.mark.parametrize(
    ("mode", "prompt", "inputs"),
    [
        ("t2v", BASE, None),
        (
            "i2v",
            base_with_first_line(I2V_FIRST_LINE),
            {
                "first_frame": {"path": "opening.png", "kind": "image"},
                "last_frame": None,
                "reference_images": [],
                "reference_videos": [],
                "reference_audios": [],
            },
        ),
        (
            "fl2v",
            base_with_first_line(FL2V_FIRST_LINE),
            {
                "first_frame": {"path": "opening.png", "kind": "image"},
                "last_frame": {"path": "ending.png", "kind": "image"},
                "reference_images": [],
                "reference_videos": [],
                "reference_audios": [],
            },
        ),
        ("r2v", R2V, r2v_inputs()),
    ],
)
def test_all_supported_modes_accept_well_formed_prompts(
    mode: str, prompt: str, inputs: dict[str, Any] | None
) -> None:
    result = MODULE.lint_snapshot(make_snapshot(prompt, mode=mode, inputs=inputs))
    assert not [finding for finding in result.findings if finding.severity == "error"]


@pytest.mark.parametrize(
    "prompt",
    [
        BASE.replace("overall_soundscape:", "integrated_multimodal_description:", 1),
        BASE.replace("overall_soundscape:", "non_diegetic_music:", 1),
        BASE.replace("Footsteps fade.", ""),
    ],
)
def test_duplicate_misordered_or_empty_fields_are_errors(prompt: str) -> None:
    assert errors(MODULE.lint_snapshot(make_snapshot(prompt)), "H3-FIELDS")


@pytest.mark.parametrize(
    "prompt",
    [
        BASE.replace("[Shot 1]", "[Shot 2]", 1),
        BASE.replace("[Shot 2]", "[Shot 1]", 1),
        BASE.replace("At 00:03.000, ", ""),
        BASE.replace("00:03.000", "00:00.000"),
        BASE.replace("00:03.000", "00:05.000").replace("[Shot 2]", "[Shot 3] At 00:04.000, [Shot 2]", 1),
        BASE.replace("[Shot 1]", "[Shot 1] At 00:00.000", 1),
    ],
)
def test_invalid_shot_sequence_or_timestamp_is_an_error(prompt: str) -> None:
    assert errors(MODULE.lint_snapshot(make_snapshot(prompt)), "H3-SHOTS")


@pytest.mark.parametrize(
    "first_shot",
    ["At the doorway, she waits.", "From the hallway, she enters."],
)
def test_first_shot_natural_language_at_or_from_is_not_a_timestamp(first_shot: str) -> None:
    prompt = BASE.replace("A woman waits by a door.", first_shot)
    assert not errors(MODULE.lint_snapshot(make_snapshot(prompt)), "H3-SHOTS")


def test_first_shot_from_timecode_is_an_error() -> None:
    prompt = BASE.replace("A woman waits by a door.", "From 00:00.000, she waits by a door.")
    assert errors(MODULE.lint_snapshot(make_snapshot(prompt)), "H3-SHOTS")


@pytest.mark.parametrize("prefix", ["An introductory sentence. ", "<d>[Chinese] 旁白。</d> "])
def test_first_shot_must_start_at_description_beginning(prefix: str) -> None:
    prompt = BASE.replace("[Shot 1] A woman", f"{prefix}[Shot 1] A woman", 1)
    assert errors(MODULE.lint_snapshot(make_snapshot(prompt)), "H3-SHOTS")


def test_i2v_requires_its_exact_alignment_line() -> None:
    prompt = base_with_first_line(I2V_FIRST_LINE.replace("fully referenced", "loosely referenced"))
    assert errors(MODULE.lint_snapshot(make_snapshot(prompt, mode="i2v")), "H3-ALIGN")


def test_fl2v_requires_final_shot_and_duration_in_alignment_line() -> None:
    prompt = base_with_first_line(FL2V_FIRST_LINE.replace("8.00", "7.00"))
    assert errors(MODULE.lint_snapshot(make_snapshot(prompt, mode="fl2v")), "H3-ALIGN")


@pytest.mark.parametrize(
    ("mode", "first_line", "inputs"),
    [
        (
            "i2v",
            I2V_FIRST_LINE,
            {
                "first_frame": {"path": "opening.png", "kind": "image"},
                "last_frame": None,
                "reference_images": [],
                "reference_videos": [],
                "reference_audios": [],
            },
        ),
        (
            "fl2v",
            FL2V_FIRST_LINE,
            {
                "first_frame": {"path": "opening.png", "kind": "image"},
                "last_frame": {"path": "ending.png", "kind": "image"},
                "reference_images": [],
                "reference_videos": [],
                "reference_audios": [],
            },
        ),
    ],
)
def test_alignment_line_must_be_immediately_followed_by_core_fields(
    mode: str, first_line: str, inputs: dict[str, Any]
) -> None:
    prompt = base_with_first_line(first_line).replace(
        "\n\nintegrated_multimodal_description:",
        "\n\nNote: This extra prose is not part of the H3 prompt format.\n\nintegrated_multimodal_description:",
    )
    assert errors(MODULE.lint_snapshot(make_snapshot(prompt, mode=mode, inputs=inputs)), "H3-ALIGN")


def test_r2v_allows_multiple_subjects_for_one_picture_and_an_optional_first_frame() -> None:
    result = MODULE.lint_snapshot(make_snapshot(R2V, mode="r2v", inputs=r2v_inputs(include_first_frame=True)))
    assert not errors(result, "H3-REF")


def test_r2v_rejects_reference_label_without_an_actual_slot() -> None:
    result = MODULE.lint_snapshot(
        make_snapshot(R2V.replace("<Picture 1>", "<Picture 2>", 1), mode="r2v", inputs=r2v_inputs())
    )
    assert errors(result, "H3-REF")


def test_picture_used_only_as_subject_provenance_needs_no_retention_entry() -> None:
    result = MODULE.lint_snapshot(make_snapshot(R2V, mode="r2v", inputs=r2v_inputs()))
    assert not errors(result, "H3-RETENTION")


def test_standalone_reference_definition_requires_retention_entry() -> None:
    prompt = R2V.replace(
        "<Subject 2> is the man in <Picture 1>.\n\nsummary:",
        "<Subject 2> is the man in <Picture 1>.\n"
        "<Picture 2> is the standalone opening frame.\n\nsummary:",
    )
    inputs = r2v_inputs()
    inputs["reference_images"].append({"path": "opening.png", "kind": "image"})
    result = MODULE.lint_snapshot(make_snapshot(prompt, mode="r2v", inputs=inputs))
    assert errors(result, "H3-RETENTION")


def test_duplicate_retention_entry_is_an_error() -> None:
    prompt = R2V.replace(
        "<Subject 2>: fully_preserved - appearance.",
        "<Subject 2>: fully_preserved - appearance.\n"
        "<Subject 1>: fully_preserved - repeated entry.",
    )
    result = MODULE.lint_snapshot(make_snapshot(prompt, mode="r2v", inputs=r2v_inputs()))
    assert errors(result, "H3-RETENTION")


@pytest.mark.parametrize("label", ["Subject", "Picture", "Video", "Audio"])
def test_zero_numbered_reference_label_is_an_error(label: str) -> None:
    prompt = (
        R2V.replace("<Subject 1>", "<Subject 0>", 1)
        if label == "Subject"
        else R2V.replace("Quiet room tone.", f"<{label} 0> supplies a reference.")
    )
    result = MODULE.lint_snapshot(make_snapshot(prompt, mode="r2v", inputs=r2v_inputs()))
    assert errors(result, "H3-REF")


def test_r2v_does_not_treat_many_subjects_as_many_images() -> None:
    definitions = "\n".join(
        f"<Subject {number}> is a person in <Picture 1>." for number in range(1, 11)
    )
    prompt = R2V.replace(
        "<Subject 1> is the woman in <Picture 1>.\n<Subject 2> is the man in <Picture 1>.",
        definitions,
    ).replace("<Subject 1> waits beside <Subject 2>", "<Subject 1> waits beside <Subject 10>")
    result = MODULE.lint_snapshot(make_snapshot(prompt, mode="r2v", inputs=r2v_inputs()))
    assert not errors(result, "H3-REF")


@pytest.mark.parametrize(
    "prompt",
    [
        R2V.replace("fully_preserved", "invented_status", 1),
        R2V.replace("<Subject 1>: fully_preserved", "<Subject 1> (S1): fully_preserved"),
    ],
)
def test_invalid_retention_marker_or_speaker_reference_is_an_error(prompt: str) -> None:
    assert errors(MODULE.lint_snapshot(make_snapshot(prompt, mode="r2v", inputs=r2v_inputs())), "H3-RETENTION")


@pytest.mark.parametrize(
    "prompt",
    [
        BASE.replace("Footsteps fade.", "<d>[Chinese] 不应出现在这里。</d>"),
        BASE.replace("A woman waits by a door.", "A woman says <d>[Chinese] 门开了。"),
        BASE.replace("<d>[Chinese]", "<d>[]")
        if "<d>[Chinese]" in BASE
        else BASE.replace("A woman waits by a door.", "A woman says <d>[] 门开了。</d>"),
    ],
)
def test_unclosed_or_misplaced_dialogue_is_an_error(prompt: str) -> None:
    assert errors(MODULE.lint_snapshot(make_snapshot(prompt)), "H3-DIALOGUE")


@pytest.mark.parametrize(
    "dialogue",
    [
        "</d><d>[Chinese] one</d><d>[Chinese] two",
        "<d>[Chinese] one <d>[Chinese] two</d></d>",
    ],
)
def test_misordered_or_nested_dialogue_tags_are_errors(dialogue: str) -> None:
    prompt = BASE.replace("A woman waits by a door.", f"A woman says {dialogue}")
    assert errors(MODULE.lint_snapshot(make_snapshot(prompt)), "H3-DIALOGUE")


def test_dialogue_content_is_not_scanned_as_prompt_structure() -> None:
    prompt = (
        "integrated_multimodal_description: [Shot 1] A woman (S1) says: "
        "<d>[Chinese] [Shot 2]，integrated_multimodal_description: @CHR 不要改。</d>\n\n"
        "overall_soundscape: Quiet room tone.\n\n"
        "non_diegetic_music: N/A"
    )
    result = MODULE.lint_snapshot(make_snapshot(prompt))
    assert not [finding for finding in result.findings if finding.severity == "error"]


def test_first_actual_speaker_must_be_s1_but_subject_definitions_do_not_assign_speakers() -> None:
    prompt = R2V.replace(
        "<Subject 1> and <Subject 2> sit together.",
        "<Subject 1> (S2) speaks, <d>[Chinese] 门开了。</d>",
    )
    result = MODULE.lint_snapshot(make_snapshot(prompt, mode="r2v", inputs=r2v_inputs()))
    assert errors(result, "H3-SPEAKER")


def test_compound_speaker_ids_are_parsed_in_vocal_order() -> None:
    prompt = BASE.replace(
        "A woman waits by a door.",
        "Two children (S1,S2) shout together, <d>[Chinese] 等等我们！</d> "
        "Their guardian (S3) answers, <d>[Chinese] 快跟上。</d>",
    )
    result = MODULE.lint_snapshot(make_snapshot(prompt))
    assert not errors(result, "H3-SPEAKER")
    assert not any("没有可解析" in item for item in result.unverified)


def test_old_prompt_shell_and_asset_anchors_are_errors_outside_dialogue() -> None:
    prompt = BASE.replace("A woman waits by a door.", "Visual Style: @CHR woman waits by a door.")
    assert errors(MODULE.lint_snapshot(make_snapshot(prompt)), "H3-LEAK")


def test_bom_crlf_chinese_dialogue_and_empty_establishing_shot_are_valid() -> None:
    prompt = (
        "\ufeffintegrated_multimodal_description: [Shot 1] A quiet street shows a sign reading 营业中.\r\n\r\n"
        "overall_soundscape: N/A\r\n\r\n"
        "non_diegetic_music: N/A"
    )
    result = MODULE.lint_snapshot(make_snapshot(prompt))
    assert not [finding for finding in result.findings if finding.severity == "error"]


def test_frame_zero_video_guide_limits_reference_completeness_to_unverified() -> None:
    prompt = R2V.replace("Quiet room tone.", "<Video 1> supplies the motion guide.")
    result = MODULE.lint_snapshot(
        make_snapshot(
            prompt,
            mode="r2v",
            inputs=r2v_inputs(),
            frame_zero_video_guide=True,
        )
    )
    assert not errors(result, "H3-REF")
    assert any("frame_zero_video_guide" in item for item in result.unverified)


def test_unknown_mode_and_non_h3_input_are_left_unverified() -> None:
    result = MODULE.lint_snapshot(make_snapshot(mode="mystery", model="other-model"))
    assert not [finding for finding in result.findings if finding.severity == "error"]
    assert result.unverified


PLAN = {
    "schema": "zero-to-story.creative-blueprint.v2",
    "panels": [{"id": "P001", "duration_s": 8, "shot_ids": ["C001"]}],
    "dialogue": [
        {
            "id": "D001",
            "order": 1,
            "speaker": "林岚",
            "text": "门开了。",
            "shot_id": "C001",
        }
    ],
    "generation": {
        "panel_plans": [{"panel_id": "P001", "operation": "video.text_to_video"}],
        "shots": [{"id": "C001", "order": 1, "panel_id": "P001", "dialogue_ids": ["D001"]}],
    },
}
SPOKEN = (
    "integrated_multimodal_description: [Shot 1] The woman (S1) says: "
    "<d>[Chinese] 门开了。</d>\n\n"
    "overall_soundscape: Wind outside.\n\n"
    "non_diegetic_music: N/A"
)


def lint_plan(prompt: str = SPOKEN, plan: dict[str, Any] | None = None, **snapshot: Any) -> Any:
    return MODULE.lint_snapshot(
        make_snapshot(prompt, **snapshot), blueprint=PLAN if plan is None else plan, panel_id="P001"
    )


def test_locked_dialogue_change_is_an_error() -> None:
    result = lint_plan(SPOKEN.replace("门开了。", "门关了。"))
    assert errors(result, "PLAN-DIALOGUE")


def test_speaker_identity_is_not_falsely_verified() -> None:
    result = lint_plan()
    assert any("说话人" in item for item in result.unverified)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda plan: plan.update(panels=[]),
        lambda plan: plan["panels"].append(dict(plan["panels"][0])),
        lambda plan: plan["generation"]["panel_plans"][0].update(operation="video.image_to_video"),
        lambda plan: plan["panels"][0].update(duration_s=10),
        lambda plan: plan["panels"][0].update(shot_ids=["C001", "C002"]),
    ],
)
def test_missing_duplicate_or_mismatched_panel_plan_is_an_error(mutate: Any) -> None:
    plan = {
        **PLAN,
        "panels": [dict(PLAN["panels"][0])],
        "generation": {
            "panel_plans": [dict(PLAN["generation"]["panel_plans"][0])],
            "shots": [dict(PLAN["generation"]["shots"][0])],
        },
    }
    mutate(plan)
    assert errors(lint_plan(plan=plan), "PLAN-MATCH")


@pytest.mark.parametrize(
    "prompt",
    [
        SPOKEN.replace("门开了。", "门开了"),
        SPOKEN.replace("<d>[Chinese] 门开了。</d>", ""),
        SPOKEN.replace("门开了。", "门开了。<d>[Chinese] 多出一句。</d>"),
    ],
)
def test_missing_extra_or_punctuation_changed_locked_dialogue_is_an_error(prompt: str) -> None:
    assert errors(lint_plan(prompt), "PLAN-DIALOGUE")


def test_repeated_identical_source_lines_remain_distinct_and_legal() -> None:
    plan = {
        **PLAN,
        "dialogue": [
            *PLAN["dialogue"],
            {"id": "D002", "order": 2, "speaker": "林岚", "text": "门开了。", "shot_id": "C001"},
        ],
        "generation": {
            **PLAN["generation"],
            "shots": [{"id": "C001", "order": 1, "panel_id": "P001", "dialogue_ids": ["D001", "D002"]}],
        },
    }
    prompt = SPOKEN.replace("</d>", "</d> <d>[Chinese] 门开了。</d>")
    assert not errors(lint_plan(prompt, plan), "PLAN-DIALOGUE")


def test_cross_shot_and_cutoff_dialogue_is_left_unverified_instead_of_guessed() -> None:
    prompt = SPOKEN.replace(
        "</d>", " <scenetrans>[Shot 2] At 00:04.000, <d>[Chinese] 还没说完。</d>"
    )
    result = lint_plan(prompt)
    assert any("跨镜" in item or "cutoff" in item for item in result.unverified)


def test_no_blueprint_keeps_structural_checks_and_marks_plan_data_unverified() -> None:
    result = MODULE.lint_snapshot(make_snapshot(SPOKEN))
    assert not [finding for finding in result.findings if finding.severity == "error"]
    assert any("蓝图" in item for item in result.unverified)


def test_missing_structured_cut_times_are_left_unverified() -> None:
    plan = {
        **PLAN,
        "panels": [{"id": "P001", "duration_s": 8, "shot_ids": ["C001", "C002"]}],
        "generation": {
            **PLAN["generation"],
            "shots": [
                {"id": "C001", "order": 1, "panel_id": "P001", "dialogue_ids": []},
                {"id": "C002", "order": 2, "panel_id": "P001", "dialogue_ids": []},
            ],
        },
    }
    result = MODULE.lint_snapshot(make_snapshot(BASE), blueprint=plan, panel_id="P001")
    assert any("切点" in item for item in result.unverified)


@pytest.mark.parametrize("shot_ids", [["C002"], ["C002", "C003"]])
def test_later_panel_uses_global_blueprint_shot_order(shot_ids: list[str]) -> None:
    plan = {
        "panels": [{"id": "P002", "duration_s": 8, "shot_ids": shot_ids}],
        "dialogue": [],
        "generation": {
            "panel_plans": [{"panel_id": "P002", "operation": "video.text_to_video"}],
            "shots": [
                {"id": "C001", "order": 1, "panel_id": "P001", "dialogue_ids": []},
                *[
                    {"id": shot_id, "order": index, "panel_id": "P002", "dialogue_ids": []}
                    for index, shot_id in enumerate(shot_ids, start=2)
                ],
            ],
        },
    }
    prompt = BASE if len(shot_ids) == 2 else BASE.replace(
        "[Shot 2] At 00:03.000, the camera cuts to her hand.", ""
    )
    result = MODULE.lint_snapshot(make_snapshot(prompt), blueprint=plan, panel_id="P002")
    assert not errors(result, "PLAN-MATCH")
    if len(shot_ids) == 2:
        plan["panels"][0]["shot_ids"] = list(reversed(shot_ids))
        result = MODULE.lint_snapshot(make_snapshot(prompt), blueprint=plan, panel_id="P002")
        assert errors(result, "PLAN-MATCH")


@pytest.mark.parametrize("order", [0, 2, True, "1", None])
def test_invalid_global_blueprint_shot_order_is_rejected(order: Any) -> None:
    plan = {
        **PLAN,
        "generation": {
            **PLAN["generation"],
            "shots": [{**PLAN["generation"]["shots"][0], "order": order}],
        },
    }
    assert errors(lint_plan(plan=plan), "PLAN-MATCH")


def test_malformed_blueprint_records_are_not_silently_ignored() -> None:
    plan = {
        **PLAN,
        "generation": {
            **PLAN["generation"],
            "shots": [dict(PLAN["generation"]["shots"][0]), "bad"],
        },
    }
    assert errors(lint_plan(plan=plan), "PLAN-MATCH")


def test_blueprint_shot_requires_dialogue_ids_array() -> None:
    shot = dict(PLAN["generation"]["shots"][0])
    shot.pop("dialogue_ids")
    plan = {
        **PLAN,
        "generation": {**PLAN["generation"], "shots": [shot]},
    }
    assert errors(lint_plan(plan=plan), "PLAN-MATCH")

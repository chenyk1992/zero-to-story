"""Tests for purpose → operation → task type derivation."""
from __future__ import annotations

import pytest

from lfo.visual.purpose import derive_operation, derive_task_type


def test_character_reference_generates():
    assert derive_task_type("character_reference") == "visual.generate"


def test_scene_reference_generates():
    assert derive_task_type("scene_reference") == "visual.generate"


def test_prop_reference_generates():
    assert derive_task_type("prop_reference") == "visual.generate"


def test_shot_start_frame_generates():
    assert derive_task_type("shot_start_frame") == "visual.generate"


def test_shot_end_frame_generates():
    assert derive_task_type("shot_end_frame") == "visual.generate"


def test_continuity_edit_edits():
    assert derive_task_type("continuity_edit") == "visual.edit"


def test_unknown_purpose_raises():
    with pytest.raises(ValueError):
        derive_task_type("not_a_real_purpose")


def test_operation_reference_to_image_with_refs():
    op = derive_operation("character_reference", has_references=True)
    assert op == "reference_to_image"


def test_operation_text_to_image_without_refs():
    op = derive_operation("character_reference", has_references=False)
    assert op == "text_to_image"


def test_shot_end_frame_operation():
    assert derive_operation("shot_end_frame", has_references=True) == "reference_to_image"


def test_continuity_edit_operation():
    assert derive_operation("continuity_edit", has_references=True) == "image_edit"

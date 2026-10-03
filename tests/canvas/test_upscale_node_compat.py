from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SOURCE = Path(__file__).resolve().parents[2] / ".agents/skills/comfy-upscale-executor/custom_node/node_compat.py"
_SPEC = importlib.util.spec_from_file_location("seedvr2_node_compat_test", _SOURCE)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
node_output_value = _MODULE.node_output_value
video_frame_count = _MODULE.video_frame_count
video_frame_sequence = _MODULE.video_frame_sequence


class FakeNodeOutput:
    result = ({"samples": "v3"}, "extra")


class FakeImages:
    def __init__(self, shape: tuple[int, ...], frame_ids: list[int] | None = None):
        self.shape = shape
        self.frame_ids = frame_ids or list(range(shape[1] if len(shape) == 5 else shape[0]))

    def squeeze(self, dimension: int):
        assert self.shape[dimension] == 1
        return FakeImages(self.shape[:dimension] + self.shape[dimension + 1:], self.frame_ids)


def test_node_output_compat_reads_modern_comfy_result_property() -> None:
    assert node_output_value(FakeNodeOutput()) == {"samples": "v3"}
    assert node_output_value(FakeNodeOutput(), 1) == "extra"


def test_node_output_compat_reads_legacy_node_tuple() -> None:
    assert node_output_value(({"samples": "legacy"},)) == {"samples": "legacy"}


def test_video_layout_compat_reads_seedvr2_preprocess_bthwc_and_preserves_all_frames() -> None:
    images = FakeImages((1, 5, 2, 3, 3), frame_ids=list(range(5)))

    assert video_frame_count(images, "preprocess") == 5
    frames = video_frame_sequence(images, "decode")
    assert frames.shape == (5, 2, 3, 3)
    assert frames.frame_ids == list(range(5))


def test_video_layout_compat_keeps_existing_frame_major_4d_layout() -> None:
    images = FakeImages((5, 2, 3, 3), frame_ids=list(range(5)))

    assert video_frame_count(images, "decoded") == 5
    assert video_frame_sequence(images, "decoded") is images


def test_video_layout_compat_rejects_multiple_batches_and_unknown_ranks() -> None:
    with pytest.raises(ValueError, match="single video batch"):
        video_frame_count(FakeImages((2, 5, 2, 3, 3)), "decoded")
    with pytest.raises(ValueError, match="T,H,W,C or B,T,H,W,C"):
        video_frame_count(FakeImages((5, 2, 3)), "decoded")

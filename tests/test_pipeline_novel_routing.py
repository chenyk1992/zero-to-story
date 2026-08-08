"""Tests for novel/chapter routing in PipelineService.

The workspace layout is novel-centric (``<workspace>/<novel>/<chapter>/``).
These tests pin down the resolution rules for the (novel_id, chapter_id) pair
so that the on-disk layout is correct even for non-ASCII (Chinese) novel
names or novel names that contain '-'.

Resolution priority (see PipelineService.__init__):
1. Both explicit (novel_id, chapter_id) args → use them.
2. Only one explicit → derive the other from project_id.
3. Neither → split project_id on the first '-'; flat single-segment fallback.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from lfo.core.database import Database
from lfo.services.pipeline_service import PipelineService


@pytest.fixture
def db(tmp_path):
    """A fresh in-memory-ish DB per test."""
    d = Database(tmp_path / "test.db")
    d.init_schema()
    return d


@pytest.fixture
def isolated_workspace(monkeypatch, tmp_path):
    """Redirect LFO_WORKSPACE to a per-test tmp dir so path lookups don't
    touch the real workspace."""
    monkeypatch.setenv("LFO_WORKSPACE", str(tmp_path / "ws"))


def _make_service(db, isolated_workspace, **kwargs) -> PipelineService:
    """Build a PipelineService with disk preflight and Comfy client
    short-circuited — these tests are only about path resolution."""
    with (
        patch("lfo.services.pipeline_service.check_disk_space"),
        patch("lfo.services.pipeline_service.ComfyApiClient"),
    ):
        return PipelineService(db, **kwargs)


# ---------------------------------------------------------------------------
# Chinese (non-ASCII) novel names
# ---------------------------------------------------------------------------


class TestChineseNovelId:
    def test_chinese_novel_id_creates_correct_path(self, db, isolated_workspace, tmp_path):
        """A Chinese novel name like '我今天不上班' must route to
        ``<workspace>/我今天不上班/<chapter>/outputs/`` — no Unicode escaping,
        no fallback to defaults."""
        svc = _make_service(
            db,
            isolated_workspace,
            project_id="我今天不上班-chapter_01",
            novel_id="我今天不上班",
            chapter_id="chapter_01",
        )
        expected = tmp_path / "ws" / "我今天不上班" / "chapter_01" / "outputs"
        assert Path(svc.output_dir) == expected

    def test_chinese_novel_id_no_dash_split(self, db, isolated_workspace, tmp_path):
        """Same scenario but relying on PipelineService to NOT split 'chapter_01'
        out of the project_id, because the explicit args override that."""
        svc = _make_service(
            db,
            isolated_workspace,
            project_id="我今天不上班",
            novel_id="我今天不上班",
            chapter_id="chapter_01",
        )
        expected = tmp_path / "ws" / "我今天不上班" / "chapter_01" / "outputs"
        assert Path(svc.output_dir) == expected

    def test_pure_chinese_novel_with_unicode_in_chapter(self, db, isolated_workspace, tmp_path):
        """Chapter id can also be Chinese."""
        svc = _make_service(
            db,
            isolated_workspace,
            project_id="我今天不上班-第一章",
            novel_id="我今天不上班",
            chapter_id="第一章",
        )
        expected = tmp_path / "ws" / "我今天不上班" / "第一章" / "outputs"
        assert Path(svc.output_dir) == expected


# ---------------------------------------------------------------------------
# Novel IDs containing '-' (the dash-splitting ambiguity)
# ---------------------------------------------------------------------------


class TestNovelIdWithDash:
    def test_dash_in_novel_name_with_explicit_args(self, db, isolated_workspace, tmp_path):
        """A novel name like 'sci-fi-2025' contains '-'. With explicit
        novel_id + chapter_id, the layout is unambiguous."""
        svc = _make_service(
            db,
            isolated_workspace,
            project_id="sci-fi-2025-chapter_01",
            novel_id="sci-fi-2025",
            chapter_id="chapter_01",
        )
        expected = tmp_path / "ws" / "sci-fi-2025" / "chapter_01" / "outputs"
        assert Path(svc.output_dir) == expected

    def test_dash_in_novel_name_legacy_split_is_wrong(self, db, isolated_workspace, tmp_path):
        """Without explicit args, the legacy first-dash split is wrong for
        'sci-fi-2025-chapter_01' — it yields ('sci', 'fi-2025-chapter_01').
        This test documents the legacy footgun so a future reader knows
        the explicit-arg API is the safe path."""
        svc = _make_service(
            db,
            isolated_workspace,
            project_id="sci-fi-2025-chapter_01",
        )
        # Legacy split: novel_id == "sci", chapter_id == "fi-2025-chapter_01"
        # This is a known ambiguity — callers should pass explicit args.
        expected = tmp_path / "ws" / "sci" / "fi-2025-chapter_01" / "outputs"
        assert Path(svc.output_dir) == expected


# ---------------------------------------------------------------------------
# Resolution priority: explicit > project_id-split > flat
# ---------------------------------------------------------------------------


class TestResolutionPriority:
    def test_both_explicit_wins_over_project_id(self, db, isolated_workspace, tmp_path):
        svc = _make_service(
            db,
            isolated_workspace,
            project_id="ignored-on-purpose",
            novel_id="real_novel",
            chapter_id="real_chapter",
        )
        expected = tmp_path / "ws" / "real_novel" / "real_chapter" / "outputs"
        assert Path(svc.output_dir) == expected

    def test_only_novel_explicit_chapter_derives_from_project_id(self, db, isolated_workspace, tmp_path):
        """When only novel_id is given, the chapter_id comes from project_id
        (treating the whole project_id as the chapter key)."""
        svc = _make_service(
            db,
            isolated_workspace,
            project_id="chapter_07",
            novel_id="only_novel",
        )
        expected = tmp_path / "ws" / "only_novel" / "chapter_07" / "outputs"
        assert Path(svc.output_dir) == expected

    def test_only_chapter_explicit_novel_derives_from_project_id(self, db, isolated_workspace, tmp_path):
        svc = _make_service(
            db,
            isolated_workspace,
            project_id="my_novel",
            chapter_id="only_chapter",
        )
        expected = tmp_path / "ws" / "my_novel" / "only_chapter" / "outputs"
        assert Path(svc.output_dir) == expected

    def test_legacy_split_with_dash(self, db, isolated_workspace, tmp_path):
        """No explicit args, project_id has a '-': split on first '-'."""
        svc = _make_service(
            db,
            isolated_workspace,
            project_id="legacy_novel-chapter_03",
        )
        expected = tmp_path / "ws" / "legacy_novel" / "chapter_03" / "outputs"
        assert Path(svc.output_dir) == expected

    def test_legacy_flat_no_dash(self, db, isolated_workspace, tmp_path):
        """No explicit args, project_id has no '-': flat single-segment
        fallback (both novel and chapter == project_id)."""
        svc = _make_service(
            db,
            isolated_workspace,
            project_id="standalone_thing",
        )
        expected = tmp_path / "ws" / "standalone_thing" / "standalone_thing" / "outputs"
        assert Path(svc.output_dir) == expected

    def test_explicit_output_dir_wins_over_workspace(self, db, isolated_workspace, tmp_path):
        """If the caller pins output_dir explicitly, that wins — used by
        tests and by CLI ``--output-dir`` overrides."""
        custom = tmp_path / "explicit"
        svc = _make_service(
            db,
            isolated_workspace,
            output_dir=str(custom),
            project_id="novel-x-chapter-y",
            novel_id="novel-x",
            chapter_id="chapter-y",
        )
        assert Path(svc.output_dir) == custom


# ---------------------------------------------------------------------------
# ProjectInfo schema: novel_id + chapter_id round-trip
# ---------------------------------------------------------------------------


class TestProjectInfoSchema:
    def test_novel_id_and_chapter_id_round_trip(self):
        """The two new fields must survive to_dict / from_dict."""
        from lfo.storyboard.storyboard import ProjectInfo

        original = ProjectInfo(
            project_id="我今天不上班-chapter_01",
            title="末日逃生篇",
            novel_id="我今天不上班",
            chapter_id="chapter_01",
        )
        roundtripped = ProjectInfo.from_dict(original.to_dict())
        assert roundtripped.project_id == "我今天不上班-chapter_01"
        assert roundtripped.novel_id == "我今天不上班"
        assert roundtripped.chapter_id == "chapter_01"
        assert roundtripped.title == "末日逃生篇"

    def test_novel_id_default_empty(self):
        """Old storyboards without novel_id / chapter_id should still load
        with empty strings — no breakage."""
        from lfo.storyboard.storyboard import ProjectInfo

        p = ProjectInfo.from_dict({"project_id": "legacy", "title": "t"})
        assert p.novel_id == ""
        assert p.chapter_id == ""
        assert p.project_id == "legacy"

    def test_storyboard_with_chinese_ids_loads(self):
        """A full Storyboard with Chinese novel_id + chapter_id must
        round-trip cleanly."""
        from lfo.storyboard.storyboard import Beat, Panel, ProjectInfo, Storyboard

        sb = Storyboard(
            project=ProjectInfo(
                project_id="我今天不上班-chapter_01",
                title="末日逃生篇",
                novel_id="我今天不上班",
                chapter_id="chapter_01",
            ),
            beats=[
                Beat(
                    beat_id="beat_001",
                    sequence=1,
                    scene_id="scene_1",
                    description="Beat 1",
                ),
            ],
            panels=[
                Panel(
                    panel_id="panel_001",
                    sequence=1,
                    beat_ids=["beat_001"],
                    desired_duration_ms=5000,
                ),
            ],
        )
        d = sb.to_dict()
        loaded = Storyboard.from_dict(d)
        assert loaded.project.novel_id == "我今天不上班"
        assert loaded.project.chapter_id == "chapter_01"
        assert loaded.project.title == "末日逃生篇"
        assert loaded.panels[0].panel_id == "panel_001"

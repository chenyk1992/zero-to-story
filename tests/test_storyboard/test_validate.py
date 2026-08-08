"""Tests for LFO Storyboard validation."""
from lfo.storyboard.validate import validate_intake, validate_storyboard


class TestValidateIntake:
    def test_valid_brief(self):
        data = {
            "sources": [
                {"source_id": "s1", "type": "creative_brief", "content": "A film."}
            ],
            "constraints": {"target_duration_ms": 30000, "aspect_ratio": "9:16"},
        }
        result = validate_intake(data)
        assert result.valid is True
        assert len(result.errors) == 0

    def test_missing_sources(self):
        data = {"constraints": {}}
        result = validate_intake(data)
        assert result.valid is False
        assert any(e.path == "/sources" for e in result.errors)

    def test_missing_constraints(self):
        data = {
            "sources": [
                {"source_id": "s1", "type": "creative_brief", "content": "Test"}
            ]
        }
        result = validate_intake(data)
        assert result.valid is False
        assert any(e.path == "/constraints" for e in result.errors)

    def test_invalid_source_type(self):
        data = {
            "sources": [
                {"source_id": "s1", "type": "invalid_type", "content": "Test"}
            ],
            "constraints": {},
        }
        result = validate_intake(data)
        assert result.valid is False
        assert any("Invalid source type" in e.message for e in result.errors)

    def test_empty_content(self):
        data = {
            "sources": [
                {"source_id": "s1", "type": "creative_brief", "content": ""}
            ],
            "constraints": {},
        }
        result = validate_intake(data)
        assert result.valid is False

    def test_negative_duration(self):
        data = {
            "sources": [
                {"source_id": "s1", "type": "creative_brief", "content": "Test"}
            ],
            "constraints": {"target_duration_ms": -100},
        }
        result = validate_intake(data)
        assert result.valid is False

    def test_invalid_aspect_ratio(self):
        data = {
            "sources": [
                {"source_id": "s1", "type": "creative_brief", "content": "Test"}
            ],
            "constraints": {"aspect_ratio": "99:99"},
        }
        result = validate_intake(data)
        assert result.valid is False

    def test_warning_too_long_duration(self):
        data = {
            "sources": [
                {"source_id": "s1", "type": "creative_brief", "content": "Test"}
            ],
            "constraints": {"target_duration_ms": 999999},
        }
        result = validate_intake(data)
        # Should be valid but with warning
        assert result.valid is True
        assert len(result.warnings) > 0


class TestValidateStoryboard:
    def test_valid_minimal(self):
        data = {
            "project": {"project_id": "proj_001"},
            "story": {},
            "shots": [
                {
                    "shot_id": "shot_001",
                    "scene_id": "scene_001",
                    "desired_duration_ms": 5000,
                }
            ],
            "scenes": [
                {"scene_id": "scene_001"}
            ],
        }
        result = validate_storyboard(data)
        assert result.valid is True

    def test_missing_project(self):
        data = {"story": {}, "shots": [{"shot_id": "s1", "scene_id": "sc1", "desired_duration_ms": 1000}]}
        result = validate_storyboard(data)
        assert result.valid is False
        assert any(e.path == "/project" for e in result.errors)

    def test_missing_shots(self):
        data = {"project": {"project_id": "p1"}, "story": {}, "shots": []}
        result = validate_storyboard(data)
        assert result.valid is False
        assert any(e.path == "/shots" for e in result.errors)

    def test_shot_missing_scene(self):
        data = {
            "project": {"project_id": "p1"},
            "story": {},
            "shots": [{"shot_id": "s1", "desired_duration_ms": 1000}],
        }
        result = validate_storyboard(data)
        assert result.valid is False
        assert any("scene_id" in e.path for e in result.errors)

    def test_character_not_found(self):
        data = {
            "project": {"project_id": "p1"},
            "story": {},
            "characters": [{"character_id": "char_001", "name": "Mira"}],
            "scenes": [{"scene_id": "scene_001"}],
            "shots": [
                {
                    "shot_id": "s1",
                    "scene_id": "scene_001",
                    "desired_duration_ms": 1000,
                    "characters": [
                        {"character_id": "char_nonexistent"}
                    ],
                }
            ],
        }
        result = validate_storyboard(data)
        assert result.valid is False
        assert any("not found" in e.message for e in result.errors)

    def test_scene_not_found(self):
        data = {
            "project": {"project_id": "p1"},
            "story": {},
            "scenes": [{"scene_id": "scene_001"}],
            "shots": [
                {
                    "shot_id": "s1",
                    "scene_id": "scene_nonexistent",
                    "desired_duration_ms": 1000,
                }
            ],
        }
        result = validate_storyboard(data)
        assert result.valid is False

    def test_continuity_invalid_reference(self):
        data = {
            "project": {"project_id": "p1"},
            "story": {},
            "scenes": [{"scene_id": "scene_001"}],
            "shots": [
                {
                    "shot_id": "s1",
                    "scene_id": "scene_001",
                    "desired_duration_ms": 1000,
                    "continuity": {"previous_shot_id": "shot_nonexistent"},
                }
            ],
        }
        result = validate_storyboard(data)
        assert result.valid is False
        assert any("previous_shot_id" in e.path for e in result.errors)

    def test_invalid_review_status(self):
        data = {
            "project": {"project_id": "p1"},
            "story": {},
            "shots": [{"shot_id": "s1", "scene_id": "sc1", "desired_duration_ms": 1000}],
            "scenes": [{"scene_id": "sc1"}],
            "review": {"status": "invalid_status"},
        }
        result = validate_storyboard(data)
        assert result.valid is False
        assert any("review/status" in e.path for e in result.errors)

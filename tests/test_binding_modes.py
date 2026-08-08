"""Tests for strict vs migration binding modes."""
import pytest

from lfo.comfy.bindings import Binding, BindingResolver
from lfo.comfy.exceptions import BindingAmbiguousError, BindingNotFoundError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workflow_with_titles():
    """Workflow where all nodes have stable _meta.title."""
    return {
        "6": {
            "class_type": "LoadImage",
            "_meta": {"title": "LFO.FirstFrame"},
            "inputs": {"image": ""},
        },
        "8": {
            "class_type": "MiniMaxH3ImageToVideo",
            "_meta": {"title": "LFO.MainGenerator"},
            "inputs": {"prompt": "", "length": 124},
        },
        "14": {
            "class_type": "SaveVideo",
            "_meta": {"title": "LFO.SaveVideo"},
            "inputs": {"filename_prefix": ""},
        },
    }


@pytest.fixture
def workflow_without_titles():
    """Legacy workflow with NO _meta.title on nodes."""
    return {
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": ""},
        },
        "2": {
            "class_type": "MiniMaxH3ImageToVideo",
            "inputs": {"prompt": "", "length": 124},
        },
        "3": {
            "class_type": "SaveVideo",
            "inputs": {"filename_prefix": ""},
        },
    }


@pytest.fixture
def workflow_ambiguous_class_type():
    """Workflow with multiple LoadImage nodes (no titles)."""
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": ""}},
        "2": {"class_type": "LoadImage", "inputs": {"image": ""}},
        "3": {"class_type": "SaveVideo", "inputs": {}},
    }


# ---------------------------------------------------------------------------
# Strict mode tests
# ---------------------------------------------------------------------------

class TestStrictMode:
    def test_resolve_with_title(self, workflow_with_titles):
        resolver = BindingResolver(workflow_with_titles)
        b = Binding(
            binding_id="prompt",
            selector_title="LFO.MainGenerator",
            selector_class_type="MiniMaxH3ImageToVideo",
            input_name="prompt",
        )
        resolved = resolver.resolve_binding(b, mode="strict")
        assert resolved.resolved_node_id == "8"

    def test_empty_title_strict_raises(self, workflow_with_titles):
        """Strict mode: empty selector_title must raise."""
        resolver = BindingResolver(workflow_with_titles)
        b = Binding(
            binding_id="bad_slot",
            selector_title="",
            selector_class_type="MiniMaxH3ImageToVideo",
            input_name="prompt",
        )
        with pytest.raises(BindingNotFoundError, match="empty selector_title"):
            resolver.resolve_binding(b, mode="strict")

    def test_strict_mode_default(self, workflow_with_titles):
        """Default mode is strict — empty title raises."""
        resolver = BindingResolver(workflow_with_titles)
        b = Binding(
            binding_id="bad_slot",
            selector_title="",
            selector_class_type="MiniMaxH3ImageToVideo",
            input_name="prompt",
        )
        with pytest.raises(BindingNotFoundError):
            resolver.resolve_binding(b)  # default mode

    def test_no_match_strict_raises(self, workflow_with_titles):
        resolver = BindingResolver(workflow_with_titles)
        b = Binding(
            binding_id="missing",
            selector_title="LFO.NonExistent",
            selector_class_type="LoadImage",
            input_name="image",
        )
        with pytest.raises(BindingNotFoundError):
            resolver.resolve_binding(b, mode="strict")

    def test_ambiguous_strict_raises(self, workflow_ambiguous_class_type):
        """Two LoadImage with titles — should still be ambiguous if titles match."""
        wf = workflow_ambiguous_class_type
        # Add same title to both
        wf["1"]["_meta"] = {"title": "LFO.Ref"}
        wf["2"]["_meta"] = {"title": "LFO.Ref"}
        resolver = BindingResolver(wf)
        b = Binding(
            binding_id="ref",
            selector_title="LFO.Ref",
            selector_class_type="LoadImage",
            input_name="image",
        )
        with pytest.raises(BindingAmbiguousError):
            resolver.resolve_binding(b, mode="strict")


# ---------------------------------------------------------------------------
# Migration mode tests
# ---------------------------------------------------------------------------

class TestMigrationMode:
    def test_empty_title_fallback_matches_by_class_type(self, workflow_without_titles):
        resolver = BindingResolver(workflow_without_titles)
        b = Binding(
            binding_id="first_frame",
            selector_title="",
            selector_class_type="LoadImage",
            input_name="image",
        )
        warnings: list[str] = []
        resolved = resolver.resolve_binding(b, mode="migration", warnings=warnings)
        assert resolved.resolved_node_id == "1"
        assert len(warnings) == 1
        assert "Migration fallback" in warnings[0]

    def test_migration_fallback_warning_content(self, workflow_without_titles):
        resolver = BindingResolver(workflow_without_titles)
        b = Binding(
            binding_id="prompt",
            selector_title="",
            selector_class_type="MiniMaxH3ImageToVideo",
            input_name="prompt",
        )
        warnings: list[str] = []
        resolved = resolver.resolve_binding(b, mode="migration", warnings=warnings)
        assert len(warnings) == 1
        assert "prompt" in warnings[0]
        assert "MiniMaxH3ImageToVideo" in warnings[0]

    def test_migration_ambiguous_raises(self, workflow_ambiguous_class_type):
        """Migration with empty title + multiple same-class nodes = ambiguous."""
        resolver = BindingResolver(workflow_ambiguous_class_type)
        b = Binding(
            binding_id="image",
            selector_title="",
            selector_class_type="LoadImage",
            input_name="image",
        )
        with pytest.raises(BindingAmbiguousError):
            resolver.resolve_binding(b, mode="migration")

    def test_migration_no_warning_when_title_present(self, workflow_with_titles):
        """Migration mode with a valid title produces NO warning."""
        resolver = BindingResolver(workflow_with_titles)
        b = Binding(
            binding_id="prompt",
            selector_title="LFO.MainGenerator",
            selector_class_type="MiniMaxH3ImageToVideo",
            input_name="prompt",
        )
        warnings: list[str] = []
        resolved = resolver.resolve_binding(b, mode="migration", warnings=warnings)
        assert resolved.resolved_node_id == "8"
        assert len(warnings) == 0


# ---------------------------------------------------------------------------
# resolve_all tests
# ---------------------------------------------------------------------------

class TestResolveAll:
    def test_resolve_all_strict(self, workflow_with_titles):
        resolver = BindingResolver(workflow_with_titles)
        bindings = [
            Binding("prompt", "LFO.MainGenerator", "MiniMaxH3ImageToVideo", "prompt"),
            Binding("first_frame", "LFO.FirstFrame", "LoadImage", "image"),
            Binding("filename_prefix", "LFO.SaveVideo", "SaveVideo", "filename_prefix"),
        ]
        resolved = resolver.resolve_all(bindings, mode="strict")
        assert len(resolved) == 3
        assert all(r.resolved_node_id is not None for r in resolved)

    def test_resolve_all_strict_one_fails(self, workflow_with_titles):
        """If any binding fails, the whole resolve fails."""
        resolver = BindingResolver(workflow_with_titles)
        bindings = [
            Binding("prompt", "LFO.MainGenerator", "MiniMaxH3ImageToVideo", "prompt"),
            Binding("bad", "", "NonExistent", "input"),
        ]
        with pytest.raises(BindingNotFoundError):
            resolver.resolve_all(bindings, mode="strict")


# ---------------------------------------------------------------------------
# apply_values still works
# ---------------------------------------------------------------------------

class TestApplyValues:
    def test_apply_values_injects_correctly(self, workflow_with_titles):
        resolver = BindingResolver(workflow_with_titles)
        b = Binding("prompt", "LFO.MainGenerator", "MiniMaxH3ImageToVideo", "prompt")
        resolver.resolve_binding(b, mode="strict")

        new_wf = resolver.apply_values([(b, "hello world")])
        assert new_wf["8"]["inputs"]["prompt"] == "hello world"
        # Original unchanged
        assert workflow_with_titles["8"]["inputs"]["prompt"] == ""

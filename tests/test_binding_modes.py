"""Tests for strict node binding and JSON scalar injection."""
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
def workflow_ambiguous_class_type():
    """Workflow with multiple nodes of the same class."""
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
        resolved = resolver.resolve_binding(b)
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
            resolver.resolve_binding(b)

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
            resolver.resolve_binding(b)

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
            resolver.resolve_binding(b)


# ---------------------------------------------------------------------------
# apply_values
# ---------------------------------------------------------------------------

class TestApplyValues:
    def test_apply_values_injects_correctly(self, workflow_with_titles):
        resolver = BindingResolver(workflow_with_titles)
        b = Binding("prompt", "LFO.MainGenerator", "MiniMaxH3ImageToVideo", "prompt")
        resolver.resolve_binding(b)

        new_wf = resolver.apply_values([(b, "hello world")])
        assert new_wf["8"]["inputs"]["prompt"] == "hello world"
        # Original unchanged
        assert workflow_with_titles["8"]["inputs"]["prompt"] == ""

    def test_apply_values_accepts_json_scalars(self, workflow_with_titles):
        resolver = BindingResolver(workflow_with_titles)
        prompt = Binding("prompt", "LFO.MainGenerator", "MiniMaxH3ImageToVideo", "prompt")
        length = Binding("length", "LFO.MainGenerator", "MiniMaxH3ImageToVideo", "length")
        enabled = Binding("enabled", "LFO.MainGenerator", "MiniMaxH3ImageToVideo", "enabled")
        for binding in (prompt, length, enabled):
            resolver.resolve_binding(binding)

        new_wf = resolver.apply_values(
            [(prompt, "hello"), (length, 8), (enabled, True)]
        )

        assert new_wf["8"]["inputs"] == {
            "prompt": "hello",
            "length": 8,
            "enabled": True,
        }

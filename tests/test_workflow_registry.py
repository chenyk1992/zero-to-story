"""Tests for LFO Workflow Registry."""
import json
import pathlib

import pytest

from lfo.comfy.workflow import WorkflowLoader
from lfo.core.workflow_registry import (
    KNOWN_WORKFLOWS,
    WorkflowManifest,
    WorkflowRegistry,
    make_capability,
)


@pytest.fixture
def workflow_dir(tmp_path):
    """Copy test workflow fixtures to a temp directory."""
    src = pathlib.Path(__file__).parent / "fixtures" / "workflows"
    dst = tmp_path / "workflows"
    dst.mkdir()
    for f in src.glob("*.json"):
        (dst / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    seedvr2 = pathlib.Path(__file__).parents[1] / "src" / "lfo" / "registry" / "seedvr2_upscale.json"
    (dst / seedvr2.name).write_text(seedvr2.read_text(encoding="utf-8"), encoding="utf-8")
    presenter = pathlib.Path(__file__).parents[1] / "src" / "lfo" / "registry" / "h3_presenter_r2v.json"
    (dst / presenter.name).write_text(presenter.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


@pytest.fixture
def registry(workflow_dir):
    reg = WorkflowRegistry(workflow_dir)
    return reg


class TestKnownWorkflows:
    def test_eight_workflows_defined(self):
        assert len(KNOWN_WORKFLOWS) == 8
        assert "h3_standard_t2v" in KNOWN_WORKFLOWS
        assert "h3_standard_i2v" in KNOWN_WORKFLOWS
        assert "h3_standard_r2v" in KNOWN_WORKFLOWS
        assert "h3_presenter_r2v" in KNOWN_WORKFLOWS
        assert "h3_vertical_t2v" in KNOWN_WORKFLOWS
        assert "h3_vertical_i2v" in KNOWN_WORKFLOWS
        assert "h3_vertical_r2v" in KNOWN_WORKFLOWS
        assert "seedvr2_upscale" in KNOWN_WORKFLOWS

    def test_t2v_manifest_fields(self):
        m = KNOWN_WORKFLOWS["h3_standard_t2v"]
        assert m.workflow_id == "h3_standard_t2v"
        assert m.family == "h3_fl2va"
        assert m.generates_audio is True
        assert len(m.model_dependencies) == 4
        assert len(m.input_slots) >= 3

    def test_i2v_has_first_frame_slot(self):
        m = KNOWN_WORKFLOWS["h3_standard_i2v"]
        slot_ids = [s.binding_id for s in m.input_slots]
        assert "first_frame" in slot_ids

    def test_r2v_has_three_ref_slots(self):
        m = KNOWN_WORKFLOWS["h3_standard_r2v"]
        slot_ids = [s.binding_id for s in m.input_slots]
        assert "ref_image_0" in slot_ids
        assert "ref_image_1" in slot_ids
        assert "ref_image_2" in slot_ids

    def test_r2v_uses_ref2va_model(self):
        m = KNOWN_WORKFLOWS["h3_standard_r2v"]
        unet = next(d for d in m.model_dependencies if d.role == "unet")
        assert "ref2va" in unet.filename

    def test_presenter_manifest_uses_strict_r2v_slots(self):
        manifest = KNOWN_WORKFLOWS["h3_presenter_r2v"]
        assert manifest.family.startswith("h3_")
        assert manifest.workflow_mode == "r2v"
        assert {slot.binding_id for slot in manifest.input_slots} == {
            "prompt", "duration", "filename_prefix",
        }
        assert all(slot.selector_title for slot in manifest.input_slots)

    def test_presenter_graph_is_core_r2v_without_static_reference_loaders(self):
        workflow = WorkflowLoader.load(
            pathlib.Path(__file__).parents[1] / "src" / "lfo" / "registry" / "h3_presenter_r2v.json"
        )
        classes = {node["class_type"] for node in workflow.values()}
        assert "MiniMaxH3ReferenceToVideo" in classes
        assert {"LoadImage", "LoadVideo", "GetVideoComponents", "LoadAudio"}.isdisjoint(classes)
        assert workflow["12"]["inputs"]["steps"] == 20
        assert workflow["17"]["inputs"]["fps"] == 24
        assert workflow["9"]["inputs"]["length"] == ["8", 1]

    def test_frame_constraints(self):
        m = KNOWN_WORKFLOWS["h3_standard_t2v"]
        assert m.frame_constraints.step == 17
        assert m.frame_constraints.default_frames == 124
        assert m.frame_constraints.fps == 24

    def test_seedvr2_upscale_manifest(self):
        manifest = KNOWN_WORKFLOWS["seedvr2_upscale"]
        assert manifest.workflow_mode == "upscale"
        assert {slot.binding_id for slot in manifest.input_slots} == {
            "input_video", "scale_multiplier", "seed", "filename_prefix",
        }
        assert {dependency.filename for dependency in manifest.model_dependencies} == {
            "seedvr2_3b_int8_convrot.safetensors",
            "seedvr2_ema_vae_fp16.safetensors",
        }


class TestRegistration:
    def test_register_all(self, registry):
        results = registry.register_all()
        assert all(v == "ok" for v in results.values())
        assert len(registry.list_workflows()) == 8

    def test_register_single(self, registry):
        report = registry.register("h3_standard_t2v")
        assert report.workflow_id == "h3_standard_t2v"
        assert report.status == "ok"
        assert len(report.unresolved) == 0

    def test_register_computes_hash(self, registry):
        registry.register("h3_standard_t2v")
        m = registry.get_manifest("h3_standard_t2v")
        assert m.workflow_hash != ""
        assert len(m.workflow_hash) == 64  # SHA-256 hex

    def test_register_missing_file(self, registry):
        # Remove the file
        (registry.workflow_dir / "h3_standard_t2v.json").unlink()
        with pytest.raises(FileNotFoundError):
            registry.register("h3_standard_t2v")

    def test_register_unknown_workflow(self, registry):
        with pytest.raises(ValueError, match="Unknown workflow"):
            registry.register("nonexistent_workflow")

    def test_register_unknown_id(self, registry):
        with pytest.raises(ValueError, match="Unknown workflow"):
            registry.register("unknown_workflow")


class TestBindingResolution:
    def test_t2v_bindings_resolve(self, registry):
        report = registry.register("h3_standard_t2v")
        assert report.status == "ok"
        # All input slots should resolve
        binding_ids = [b["binding_id"] for b in report.bindings if "node_id" in b]
        assert "prompt" in binding_ids
        assert "duration" in binding_ids
        assert "filename_prefix" in binding_ids

    def test_i2v_bindings_resolve(self, registry):
        report = registry.register("h3_standard_i2v")
        assert report.status == "ok"
        binding_ids = [b["binding_id"] for b in report.bindings if "node_id" in b]
        assert "first_frame" in binding_ids
        assert "prompt" in binding_ids

    def test_r2v_bindings_resolve(self, registry):
        report = registry.register("h3_standard_r2v")
        assert report.status == "ok"
        binding_ids = [b["binding_id"] for b in report.bindings if "node_id" in b]
        assert "ref_image_0" in binding_ids
        assert "ref_image_1" in binding_ids
        assert "ref_image_2" in binding_ids

    def test_presenter_bindings_resolve(self, registry):
        report = registry.register("h3_presenter_r2v")
        assert report.status == "ok"
        assert [binding["binding_id"] for binding in report.bindings] == [
            "prompt", "duration", "filename_prefix",
        ]

    def test_binding_node_ids_valid(self, registry):
        report = registry.register("h3_standard_t2v")
        for b in report.bindings:
            if "node_id" in b:
                # Node IDs in API format are numeric strings
                assert b["node_id"].isdigit()

    def test_seedvr2_workflow_is_api_format_and_binds(self, registry):
        workflow = WorkflowLoader.load(registry.workflow_dir / "seedvr2_upscale.json")
        assert WorkflowLoader.is_api_format(workflow)
        assert workflow["8"]["inputs"]["chunking_mode"] == "auto"
        assert "chunking_mode.frames_per_chunk" not in workflow["8"]["inputs"]
        assert workflow["11"]["inputs"]["switch"] is False
        assert workflow["15"]["inputs"]["switch"] is False
        report = registry.register("seedvr2_upscale")
        assert report.status == "ok"
        assert not report.unresolved


class TestCapabilities:
    def test_t2v_capability(self):
        m = KNOWN_WORKFLOWS["h3_standard_t2v"]
        cap = make_capability(m)
        assert "t2va" in cap.modes
        assert cap.accepts_prompt is True
        assert cap.accepts_image is False
        assert cap.produces_video is True
        assert cap.produces_audio is True

    def test_i2v_capability(self):
        m = KNOWN_WORKFLOWS["h3_standard_i2v"]
        cap = make_capability(m)
        assert "i2v" in cap.modes
        assert cap.accepts_image is True
        assert cap.accepts_first_frame is True

    def test_r2v_capability(self):
        m = KNOWN_WORKFLOWS["h3_standard_r2v"]
        cap = make_capability(m)
        assert "r2v" in cap.modes
        assert cap.accepts_reference_images is True

    def test_seedvr2_upscale_capability(self):
        cap = make_capability(KNOWN_WORKFLOWS["seedvr2_upscale"])
        assert cap.modes == ["upscale"]
        assert cap.accepts_prompt is False
        assert cap.produces_audio is True


class TestValidation:
    def test_validate_all_pass(self, registry):
        registry.register("h3_standard_t2v")
        result = registry.validate_workflow("h3_standard_t2v")
        assert result["valid"] is True
        assert all(c["status"] == "pass" for c in result["checks"])

    def test_validate_not_registered(self, registry):
        result = registry.validate_workflow("h3_standard_t2v")
        assert result["valid"] is False

    def test_validate_missing_file(self, tmp_path):
        """Validate when file was deleted after registration."""
        # Setup: copy files, register, then delete
        src = pathlib.Path(__file__).parent / "fixtures" / "workflows"
        wf_dir = tmp_path / "workflows"
        wf_dir.mkdir()
        for f in src.glob("*.json"):
            (wf_dir / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")

        reg = WorkflowRegistry(wf_dir)
        reg.register("h3_standard_t2v")

        # Delete the file
        (wf_dir / "h3_standard_t2v.json").unlink()
        result = reg.validate_workflow("h3_standard_t2v")
        assert result["valid"] is False
        file_check = next(c for c in result["checks"] if c["name"] == "file_exists")
        assert file_check["status"] == "fail"

    def test_validate_changed_hash(self, tmp_path):
        """Validate detects workflow file changes."""
        src = pathlib.Path(__file__).parent / "fixtures" / "workflows"
        wf_dir = tmp_path / "workflows"
        wf_dir.mkdir()
        for f in src.glob("*.json"):
            (wf_dir / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")

        reg = WorkflowRegistry(wf_dir)
        reg.register("h3_standard_t2v")

        # Modify the workflow
        wf_path = wf_dir / "h3_standard_t2v.json"
        wf = json.loads(wf_path.read_text(encoding="utf-8"))
        wf["6"]["inputs"]["prompt"] = "MODIFIED PROMPT"
        wf_path.write_text(json.dumps(wf), encoding="utf-8")

        result = reg.validate_workflow("h3_standard_t2v")
        hash_check = next(c for c in result["checks"] if c["name"] == "hash_match")
        assert hash_check["status"] == "warn"

    def test_validate_check_names(self, registry):
        registry.register("h3_standard_t2v")
        result = registry.validate_workflow("h3_standard_t2v")
        check_names = {c["name"] for c in result["checks"]}
        assert "file_exists" in check_names
        assert "hash_match" in check_names
        assert "bindings_resolve" in check_names
        assert "api_format" in check_names


class TestExport:
    def test_export_registry(self, registry, tmp_path):
        registry.register_all()
        out_dir = tmp_path / "registry"
        registry.export_registry(out_dir)

        # Check all expected files exist
        expected_files = [
            "h3_standard_t2v_manifest.json",
            "h3_standard_t2v_capability.json",
            "h3_standard_t2v_binding_report.json",
            "h3_standard_i2v_manifest.json",
            "h3_standard_i2v_capability.json",
            "h3_standard_i2v_binding_report.json",
            "h3_standard_r2v_manifest.json",
            "h3_standard_r2v_capability.json",
            "h3_standard_r2v_binding_report.json",
            "h3_presenter_r2v_manifest.json",
            "h3_presenter_r2v_capability.json",
            "h3_presenter_r2v_binding_report.json",
        ]
        for fname in expected_files:
            fpath = out_dir / fname
            assert fpath.exists(), f"Missing: {fname}"
            # Verify valid JSON
            data = json.loads(fpath.read_text(encoding="utf-8"))
            assert isinstance(data, dict)

    def test_export_manifest_has_hash(self, registry, tmp_path):
        registry.register("h3_standard_t2v")
        out_dir = tmp_path / "registry"
        registry.export_registry(out_dir)

        manifest = json.loads(
            (out_dir / "h3_standard_t2v_manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["workflow_hash"] != ""
        assert len(manifest["workflow_hash"]) == 64


class TestManifestSerialization:
    def test_manifest_round_trip(self):
        m = KNOWN_WORKFLOWS["h3_standard_t2v"]
        data = m.to_dict()
        restored = WorkflowManifest.from_dict(data)
        assert restored.workflow_id == m.workflow_id
        assert restored.family == m.family
        assert restored.frame_constraints.step == m.frame_constraints.step
        assert len(restored.input_slots) == len(m.input_slots)

    def test_capability_to_dict(self):
        m = KNOWN_WORKFLOWS["h3_standard_t2v"]
        cap = make_capability(m)
        d = cap.to_dict()
        assert d["workflow_id"] == "h3_standard_t2v"
        assert "t2va" in d["modes"]

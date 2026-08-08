"""Tests for configuration resolution — layers, JSON Pointer, env vars."""
from __future__ import annotations

from lfo.config.config_resolver import (
    ResolvedConfig,
    apply_json_pointer,
    expand_env_vars,
    merge_config_layers,
    resolve_config,
    validate_against_schema,
)
from lfo.config.defaults import get_defaults


class TestApplyJsonPointer:
    def test_set_top_level(self):
        base = {}
        result = apply_json_pointer(base, "/timeout_sec", 600)
        assert result == {"timeout_sec": 600}

    def test_set_nested(self):
        base = {"comfyui": {"port": 8188}}
        result = apply_json_pointer(base, "/comfyui/port", 9999)
        assert result["comfyui"]["port"] == 9999

    def test_creates_intermediate(self):
        base = {}
        result = apply_json_pointer(base, "/a/b/c", "value")
        assert result == {"a": {"b": {"c": "value"}}}

    def test_overwrite_scalar_with_object(self):
        base = {"key": "old"}
        result = apply_json_pointer(base, "/key/nested", "new")
        assert result == {"key": {"nested": "new"}}


class TestMergeConfigLayers:
    def test_scalar_override(self):
        base = {"timeout": 100}
        override = {"timeout": 200}
        result = merge_config_layers(base, override)
        assert result["timeout"] == 200

    def test_recursive_merge(self):
        base = {"comfyui": {"port": 8188, "base_url": "http://localhost"}}
        override = {"comfyui": {"port": 9999}}
        result = merge_config_layers(base, override)
        assert result["comfyui"]["port"] == 9999
        assert result["comfyui"]["base_url"] == "http://localhost"

    def test_array_replacement(self):
        base = {"items": [1, 2, 3]}
        override = {"items": [4, 5]}
        result = merge_config_layers(base, override)
        assert result["items"] == [4, 5]

    def test_null_clears_key(self):
        base = {"key": "value", "other": "keep"}
        override = {"key": None}
        result = merge_config_layers(base, override)
        assert "key" not in result
        assert result["other"] == "keep"

    def test_original_not_modified(self):
        base = {"nested": {"a": 1}}
        merge_config_layers(base, {"nested": {"b": 2}})
        assert "b" not in base["nested"]


class TestExpandEnvVars:
    def test_percent_var(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "hello")
        assert expand_env_vars("%TEST_VAR%") == "hello"

    def test_dollar_brace(self, monkeypatch):
        monkeypatch.setenv("MY_PATH", "/usr/local")
        assert expand_env_vars("${MY_PATH}/bin") == "/usr/local/bin"

    def test_dollar_simple(self, monkeypatch):
        monkeypatch.setenv("HOME", "/home/user")
        assert expand_env_vars("$HOME/docs") == "/home/user/docs"

    def test_nested_expansion(self, monkeypatch):
        monkeypatch.setenv("A", "alpha")
        result = expand_env_vars({"key": "%A%", "list": ["$A", "static"]})
        assert result["key"] == "alpha"
        assert result["list"] == ["alpha", "static"]

    def test_unexpanded_leaves_alone(self):
        result = expand_env_vars("%NONEXISTENT_VAR%")
        assert result == "%NONEXISTENT_VAR%"


class TestValidateAgainstSchema:
    def test_valid(self):
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}, "count": {"type": "integer"}},
        }
        errors = validate_against_schema({"name": "test", "count": 5}, schema)
        assert errors == []

    def test_missing_required(self):
        schema = {"required": ["name"]}
        errors = validate_against_schema({}, schema)
        assert any("name" in e for e in errors)

    def test_wrong_type(self):
        schema = {"properties": {"count": {"type": "string"}}}
        errors = validate_against_schema({"count": 42}, schema)
        assert any("type" in e.lower() for e in errors)

    def test_enum_violation(self):
        schema = {"properties": {"level": {"enum": ["low", "high"]}}}
        errors = validate_against_schema({"level": "medium"}, schema)
        assert any("enum" in e for e in errors)


class TestResolvedConfig:
    def test_get_nested_key(self):
        rc = ResolvedConfig(raw={"comfyui": {"port": 9999}})
        assert rc.get("comfyui.port") == 9999

    def test_get_missing_key(self):
        rc = ResolvedConfig(raw={})
        assert rc.get("nonexistent") is None

    def test_get_with_default(self):
        rc = ResolvedConfig(raw={})
        assert rc.get("missing", "default") == "default"

    def test_get_nested_missing(self):
        rc = ResolvedConfig(raw={"a": {"b": 1}})
        assert rc.get("a.c.d") is None


class TestResolveConfig:
    def test_defaults_only(self):
        rc = resolve_config()
        assert rc.raw["timeout_sec"] == get_defaults().timeout_sec
        assert rc.raw["comfyui"]["port"] == get_defaults().comfyui_port

    def test_with_cli_overrides(self):
        rc = resolve_config(cli_overrides={"timeout_sec": 300})
        assert rc.raw["timeout_sec"] == 300

    def test_with_machine_id(self, tmp_path, monkeypatch):
        import json

        appdata = tmp_path / "lfo_config"
        appdata.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("APPDATA", str(appdata))

        machines_dir = appdata / "LFO" / "machines"
        machines_dir.mkdir(parents=True, exist_ok=True)
        (machines_dir / "test.json").write_text(
            json.dumps({
                "schema_version": "lfo.machine.v1",
                "machine_id": "test",
                "comfyui": {"base_url": "http://custom:7777", "root": "/test"},
                "hardware": {"gpu_name": "RTX 4090"},
            })
        )

        rc = resolve_config(machine_id="test")
        assert rc.machine_id == "test"
        assert rc.machine_profile is not None
        assert rc.machine_profile.hardware.gpu_name == "RTX 4090"

    def test_project_config(self, tmp_path, monkeypatch):
        import json

        monkeypatch.setenv("APPDATA", str(tmp_path / "empty_appdata"))

        project = tmp_path / "project"
        project.mkdir()
        (project / "config.json").write_text(
            json.dumps({"timeout_sec": 500})
        )

        rc = resolve_config(project_path=project)
        assert rc.raw["timeout_sec"] == 500

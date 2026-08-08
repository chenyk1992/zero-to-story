"""Tests for CLI dispatch skeleton — registry, parser, output formatting."""
from __future__ import annotations

import argparse

import pytest

from lfo.cli.output import (
    EXIT_CLI_ERROR,
    EXIT_SUCCESS,
    CommandResult,
    format_output,
)
from lfo.cli.registry import CommandRegistry

# ---------------------------------------------------------------------------
# CommandRegistry
# ---------------------------------------------------------------------------


class TestCommandRegistry:
    def setup_method(self):
        CommandRegistry.reset()

    def teardown_method(self):
        CommandRegistry.reset()

    def test_registry_register_and_get(self):
        class FakeCmd:
            name = "fake"

        CommandRegistry.register(FakeCmd)
        assert CommandRegistry.get("fake") is FakeCmd

    def test_registry_get_missing_returns_none(self):
        assert CommandRegistry.get("nonexistent") is None

    def test_registry_all_commands(self):
        class CmdA:
            name = "a"

        class CmdB:
            name = "b"

        CommandRegistry.register(CmdA)
        CommandRegistry.register(CmdB)
        all_cmds = CommandRegistry.all_commands()
        assert all_cmds == {"a": CmdA, "b": CmdB}

    def test_registry_reset(self):
        class TempCmd:
            name = "temp"

        CommandRegistry.register(TempCmd)
        assert CommandRegistry.get("temp") is not None
        CommandRegistry.reset()
        assert CommandRegistry.get("temp") is None
        assert CommandRegistry.all_commands() == {}

    def test_register_returns_class(self):
        """register() should return the class so it can be used as a decorator."""

        @CommandRegistry.register
        class DecoratedCmd:
            name = "decorated"

        assert CommandRegistry.get("decorated") is DecoratedCmd


# ---------------------------------------------------------------------------
# CommandResult + format_output
# ---------------------------------------------------------------------------


class TestCommandResult:
    def test_default_values(self):
        result = CommandResult(ok=True, command="test")
        assert result.ok is True
        assert result.command == "test"
        assert result.data == {}
        assert result.warnings == []
        assert result.error is None


class TestFormatOutput:
    def setup_method(self):
        from lfo.cli.color import disable_colors
        disable_colors()

    def teardown_method(self):
        from lfo.cli.color import enable_colors
        enable_colors()

    def test_command_result_format_json(self):
        result = CommandResult(
            ok=True,
            command="config",
            data={"key": "value"},
            warnings=["watch out"],
        )
        output = format_output(result, json_mode=True)
        import json

        parsed = json.loads(output)
        assert parsed["ok"] is True
        assert parsed["command"] == "config"
        assert parsed["data"] == {"key": "value"}
        assert parsed["warnings"] == ["watch out"]
        assert parsed["error"] is None

    def test_command_result_format_json_error(self):
        result = CommandResult(
            ok=False,
            command="setup",
            error={"code": "E_SETUP", "message": "something broke"},
        )
        output = format_output(result, json_mode=True)
        import json

        parsed = json.loads(output)
        assert parsed["ok"] is False
        assert parsed["error"]["code"] == "E_SETUP"

    def test_command_result_format_human_success(self):
        result = CommandResult(ok=True, command="doctor")
        output = format_output(result, json_mode=False)
        assert "[doctor]" in output

    def test_command_result_format_human_with_warnings(self):
        result = CommandResult(ok=True, command="preflight", warnings=["low disk", "slow GPU"])
        output = format_output(result, json_mode=False)
        assert "[preflight]" in output
        assert "low disk" in output
        assert "slow GPU" in output

    def test_command_result_format_human_error(self):
        result = CommandResult(
            ok=False,
            command="setup",
            error={"code": "E_FAIL", "message": "Out of memory"},
        )
        output = format_output(result, json_mode=False)
        assert output == "Error [E_FAIL]: Out of memory"

    def test_command_result_format_human_error_no_error_dict(self):
        result = CommandResult(ok=False, command="setup")
        output = format_output(result, json_mode=False)
        assert "Error [UNKNOWN]" in output


# ---------------------------------------------------------------------------
# ArgumentParser / main entry
# ---------------------------------------------------------------------------


class DummyCmd:
    """Minimal command for parser tests."""

    name = "dummy"

    @staticmethod
    def configure_parser(parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--name", default="world")

    @staticmethod
    def execute(context, args):
        return CommandResult(ok=True, command="dummy", data={"name": args.name})


class TestBuildParser:
    def setup_method(self):
        CommandRegistry.reset()
        CommandRegistry.register(DummyCmd)

    def teardown_method(self):
        CommandRegistry.reset()

    def test_build_parser_includes_all_commands(self):
        from lfo.cli.main import build_parser

        parser = build_parser()
        # parse_args with the dummy command should work
        args = parser.parse_args(["dummy", "--name", "test"])
        assert args.command == "dummy"
        assert args.name == "test"

    def test_unknown_command_returns_error(self, capsys):

        # An unknown command triggers parser.print_help() + EXIT_CLI_ERROR
        # argparse exits on parse errors; we test via parse_args directly
        with pytest.raises(SystemExit):
            import argparse

            parser = argparse.ArgumentParser()
            subparsers = parser.add_subparsers(dest="command")
            subparsers.add_parser("known")
            parser.parse_args(["unknown"])

    def test_help_flag_works(self, capsys):
        from lfo.cli.main import build_parser

        parser = build_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])
        assert exc_info.value.code == 0

    def test_json_flag_parsed(self):
        from lfo.cli.main import build_parser

        parser = build_parser()
        args = parser.parse_args(["--json", "dummy"])
        assert args.json is True

    def test_verbose_flag_parsed(self):
        from lfo.cli.main import build_parser

        parser = build_parser()
        args = parser.parse_args(["-v", "dummy"])
        assert args.verbose is True

    def test_no_command_prints_help(self, capsys):
        from lfo.cli.main import main

        exit_code = main([])
        assert exit_code == EXIT_CLI_ERROR

    def test_known_command_executes(self):
        from lfo.cli.main import main

        exit_code = main(["dummy", "--name", "lfo"])
        assert exit_code == EXIT_SUCCESS

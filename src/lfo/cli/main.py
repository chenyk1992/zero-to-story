"""LFO CLI entry point — argparse dispatch with JSON + table output."""
from __future__ import annotations

import argparse
import sys

import lfo.cli  # noqa: F401 — triggers @CommandRegistry.register decorators
from lfo.cli.context import CLIContext
from lfo.cli.output import EXIT_CLI_ERROR, EXIT_SUCCESS, CommandResult, format_output
from lfo.cli.registry import CommandRegistry


def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level argument parser with all registered subcommands."""
    parser = argparse.ArgumentParser(
        prog="lfo",
        description="LFO — reusable local video generation and media runtime",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--json", action="store_true", help="JSON output for machines")
    parser.add_argument("--db", default=None, help="Database path (default: from config)")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    for name, cmd_class in CommandRegistry.all_commands().items():
        sub = subparsers.add_parser(name, help=f"{name} command")
        cmd_class.configure_parser(sub)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns an exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return EXIT_CLI_ERROR

    cmd_class = CommandRegistry.get(args.command)
    if cmd_class is None:
        parser.print_help()
        return EXIT_CLI_ERROR

    context = CLIContext(
        config=None,
        db=None,
        verbose=args.verbose,
        json_output=args.json,
    )

    try:
        result = cmd_class.execute(context, args)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result = CommandResult(
            ok=False, command=args.command,
            error={"code": "E_COMMAND_INPUT", "message": str(exc)},
        )
    output = format_output(result, json_mode=args.json)
    print(output)

    return EXIT_SUCCESS if getattr(result, "ok", True) else EXIT_CLI_ERROR


if __name__ == "__main__":
    sys.exit(main())

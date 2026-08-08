"""Command registry — maps command names to handler classes.

Command modules (e.g. ``panels_cmd``, ``preview_cmd``) register via
``@CommandRegistry.register``; ``lfo.cli.__init__`` imports them so
decorators run at package load.
"""
from __future__ import annotations


class CommandProtocol:
    """Interface all commands must implement."""

    name: str

    @staticmethod
    def configure_parser(parser): ...

    @staticmethod
    def execute(context, args): ...


class CommandRegistry:
    """Maps command names to their handler classes."""

    _commands: dict[str, type[CommandProtocol]] = {}

    @classmethod
    def register(cls, cmd_class: type[CommandProtocol]) -> type[CommandProtocol]:
        """Register a command class. Can be used as a decorator."""
        cls._commands[cmd_class.name] = cmd_class
        return cmd_class

    @classmethod
    def get(cls, name: str) -> type[CommandProtocol] | None:
        """Look up a command class by name."""
        return cls._commands.get(name)

    @classmethod
    def all_commands(cls) -> dict[str, type[CommandProtocol]]:
        """Return a copy of the registered commands map."""
        return dict(cls._commands)

    @classmethod
    def reset(cls) -> None:
        """Test helper — clear all registered commands."""
        cls._commands.clear()

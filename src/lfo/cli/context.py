"""CLI execution context — shared state for all commands."""
from __future__ import annotations

from dataclasses import dataclass

from lfo.config.config_resolver import ResolvedConfig
from lfo.core.database import Database


@dataclass
class CLIContext:
    """Shared state passed to every CLI command handler."""

    config: ResolvedConfig | None
    db: Database | None
    verbose: bool
    json_output: bool

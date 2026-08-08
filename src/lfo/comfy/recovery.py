"""Crash recovery from DB records."""

from __future__ import annotations

from dataclasses import dataclass

from .client import ComfyApiClient
from .collect import AssetRecord, ComfyOutputCollector
from .exceptions import ComfyUnreachableError

# --------------------------------------------------------------------------- #
# Data classes                                                                #
# --------------------------------------------------------------------------- #


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""

    recovered: bool
    asset_record: AssetRecord | None = None
    method_used: str = ""  # "history", "scan", "history+scan", "none"
    error: str | None = None


# --------------------------------------------------------------------------- #
# Recovery manager                                                           #
# --------------------------------------------------------------------------- #


class RecoveryManager:
    """Recover outputs from interrupted or uncertain submissions."""

    def __init__(
        self,
        client: ComfyApiClient,
        collector: ComfyOutputCollector,
    ):
        self.client = client
        self.collector = collector

    # -- helpers ----------------------------------------------------------- #

    def _query_history(self, prompt_id: str) -> dict | None:
        """Query /history/{prompt_id}. Returns None on any error."""
        try:
            return self.client.get_history(prompt_id)
        except ComfyUnreachableError:
            return None

    def _history_has_output(self, prompt_id: str) -> bool:
        """Check if history contains output data for the prompt."""
        history = self._query_history(prompt_id)
        if not history or prompt_id not in history:
            return False
        entry = history[prompt_id]
        return bool(entry.get("outputs"))

    def _history_completed(self, prompt_id: str) -> bool:
        """Check if history shows the prompt as completed."""
        history = self._query_history(prompt_id)
        if not history or prompt_id not in history:
            return False
        status = history[prompt_id].get("status", {})
        return bool(status.get("completed"))

    # -- public methods ---------------------------------------------------- #

    def recover_attempt(self, db_record: dict) -> RecoveryResult:
        """Recover a known-submitted attempt.

        Strategy:
        1. Query history for prompt_id → confirm completion status.
        2. Scan attempt_dir for outputs (Path C — authoritative).
        3. Validate + register any found files.
        """
        prompt_id = db_record.get("prompt_id", "")

        # Step 1: history check (informational)
        history_ok = False
        if prompt_id:
            history_ok = self._history_completed(prompt_id)

        # Step 2: scan filesystem (authoritative)
        collect_result = self.collector.collect(db_record)

        if collect_result.assets:
            method = "history+scan" if history_ok else "scan"
            return RecoveryResult(
                recovered=True,
                asset_record=collect_result.assets[0],
                method_used=method,
            )

        # No assets found
        if history_ok:
            # History says completed but no files — outputs may have been moved
            return RecoveryResult(
                recovered=False,
                method_used="history",
                error="History shows completed but no output files found in attempt_dir",
            )

        return RecoveryResult(
            recovered=False,
            method_used="none",
            error="No history record and no output files found",
        )

    def recover_uncertain_attempt(self, db_record: dict) -> RecoveryResult:
        """Recover from ``SUBMISSION_UNCERTAIN`` state.

        This handles the case where the prompt may or may not have been
        accepted by ComfyUI (e.g. network interruption between POST and response).

        Strategy:
        1. Try history lookup first.
        2. Fall back to directory scan.
        3. Handle ``COMFY_JOB_NOT_FOUND`` gracefully.
        """
        prompt_id = db_record.get("prompt_id", "")

        # Step 1: history lookup
        if prompt_id:
            history = self._query_history(prompt_id)
            if history and prompt_id in history:
                # Prompt was accepted — try to collect
                collect_result = self.collector.collect(db_record)
                if collect_result.assets:
                    return RecoveryResult(
                        recovered=True,
                        asset_record=collect_result.assets[0],
                        method_used="history_confirmed",
                    )
                # History exists but no files yet — still processing?
                return RecoveryResult(
                    recovered=False,
                    method_used="history",
                    error="Prompt in history but outputs not yet available",
                )

        # Step 2: scan anyway (prompt may have been submitted without us
        # getting the response)
        collect_result = self.collector.collect(db_record)
        if collect_result.assets:
            return RecoveryResult(
                recovered=True,
                asset_record=collect_result.assets[0],
                method_used="scan_only",
            )

        return RecoveryResult(
            recovered=False,
            method_used="none",
            error="Prompt not found in history and no output files on disk",
        )

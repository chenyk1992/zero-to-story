"""Prompt submission + journal recording."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from .client import ComfyApiClient
from .workflow import WorkflowLoader

# --------------------------------------------------------------------------- #
# Protocols                                                                   #
# --------------------------------------------------------------------------- #


class SubmissionJournal(Protocol):
    """Abstract journal for recording prompt submissions.

    Implemented by the persistence layer (SQLite, JSONL, etc.).
    """

    def record_submission(
        self,
        prompt_id: str,
        attempt_id: str,
        filename_prefix: str,
        attempt_dir: str,
    ) -> None:
        """Persist a submission record."""
        ...


# --------------------------------------------------------------------------- #
# Data classes                                                                #
# --------------------------------------------------------------------------- #


@dataclass
class SubmitResult:
    """Result of a successful prompt submission."""

    prompt_id: str
    node_id: str
    node_type: str
    client_id: str
    filename_prefix: str
    attempt_dir: str


# --------------------------------------------------------------------------- #
# Submitter                                                                   #
# --------------------------------------------------------------------------- #


class PromptSubmitter:
    """Prepare and submit a prompt to ComfyUI."""

    def __init__(self, client: ComfyApiClient, journal: SubmissionJournal):
        self.client = client
        self.journal = journal

    def prepare_and_submit(
        self,
        workflow: dict,
        project_id: str,
        task_id: str,
        attempt_id: str,
    ) -> SubmitResult:
        """Submit a workflow with a deterministic output prefix.

        Steps:
        1. Build ``filename_prefix = lfo/<project>/<task>/<attempt>/video``.
        2. Inject into the SaveVideo node.
        3. Verify the target attempt dir is empty (no stale outputs).
        4. POST to ``/prompt``.
        5. Record in the journal.

        Returns a :class:`SubmitResult`.
        """
        filename_prefix = f"lfo/{project_id}/{task_id}/{attempt_id}/video"
        attempt_dir = f"lfo/{attempt_id}"

        # Inject filename_prefix into SaveVideo node(s)
        save_nodes = WorkflowLoader.find_nodes_by_class(workflow, "SaveVideo")
        if not save_nodes:
            raise RuntimeError(
                "No SaveVideo node found in workflow — cannot set filename_prefix"
            )

        for _node_id, node_data in save_nodes:
            if "inputs" not in node_data:
                node_data["inputs"] = {}
            node_data["inputs"]["filename_prefix"] = filename_prefix

        # Submit
        client_id = str(uuid.uuid4())
        result = self.client.submit_prompt(workflow, client_id)
        prompt_id = result.get("prompt_id", "")

        # Journal
        self.journal.record_submission(
            prompt_id=prompt_id,
            attempt_id=attempt_id,
            filename_prefix=filename_prefix,
            attempt_dir=attempt_dir,
        )

        return SubmitResult(
            prompt_id=prompt_id,
            node_id=save_nodes[0][0],
            node_type="SaveVideo",
            client_id=client_id,
            filename_prefix=filename_prefix,
            attempt_dir=attempt_dir,
        )

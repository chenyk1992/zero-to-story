"""ExecutionFacade — lightweight execution orchestrator for READY tasks.

Responsibilities:
- run_ready_task(task_id): load READY task → create Attempt → submit → monitor → collect
- recover_attempt(attempt_id): recover from a failed/uncertain attempt

Internal reuse:
- comfy/client.py (ComfyApiClient)
- comfy/submit.py (PromptSubmitter)
- comfy/monitor.py (polling)
- comfy/collect.py (result collection)
- comfy/recovery.py (attempt recovery)
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from lfo.comfy.client import ComfyApiClient
from lfo.comfy.workflow_loader import (
    apply_filename_prefix,
    apply_float_input,
    apply_image_input,
    apply_text_input,
    blueprint_to_text,
    deep_copy_workflow,
    load_workflow,
)
from lfo.core.database import Database
from lfo.core.state_machine import SubmissionState, TaskStatus


@dataclass
class AttemptResult:
    """Result of an execution attempt."""

    attempt_id: str
    task_id: str
    success: bool
    prompt_id: str = ""
    message: str = ""
    status: str = ""
    details: dict = field(default_factory=dict)


class ExecutionFacade:
    """Orchestrate task execution via ComfyUI."""

    def __init__(
        self,
        db: Database,
        client: ComfyApiClient | None = None,
    ) -> None:
        self.db = db
        self.client = client or ComfyApiClient()

    def run_ready_task(self, task_id: str) -> AttemptResult:
        """Execute a READY task.

        Steps:
        1. Load task and verify it's READY
        2. Load current materialization
        3. Verify environment hash matches
        4. Create Attempt record
        5. Submit to ComfyUI
        6. Record submission in journal
        7. Return result (async monitoring is separate)

        Args:
            task_id: The READY task to execute.

        Returns:
            AttemptResult with submission details.
        """
        # 1. Load task
        task_row = self.db.fetchone(
            """SELECT task_id, project_id, status, params_hash, idempotency_key
               FROM tasks WHERE task_id = ?""",
            (task_id,),
        )
        if task_row is None:
            return AttemptResult(
                attempt_id="",
                task_id=task_id,
                success=False,
                message=f"Task {task_id} not found",
            )

        task_id, project_id, status, params_hash, idempotency_key = (
            task_row[0], task_row[1], task_row[2], task_row[3], task_row[4]
        )

        if status != TaskStatus.READY.value:
            return AttemptResult(
                attempt_id="",
                task_id=task_id,
                success=False,
                message=f"Task {task_id} is in '{status}' state, expected READY",
            )

        # 2. Load materialization
        mat_row = self.db.fetchone(
            """SELECT materialization_id, workflow_id, params, environment_snapshot_id,
                      environment_execution_hash, binding_snapshot, prompt_snapshot
               FROM task_materializations
               WHERE task_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (task_id,),
        )
        if mat_row is None:
            return AttemptResult(
                attempt_id="",
                task_id=task_id,
                success=False,
                message=f"No materialization found for task {task_id}",
            )

        materialization_id, workflow_id, params_json, env_snapshot_id = (
            mat_row[0], mat_row[1], mat_row[2], mat_row[3]
        )
        env_execution_hash = mat_row[4]

        # 3. Verify environment hash
        current_hash = self._get_current_env_hash(env_snapshot_id)
        if current_hash and current_hash != env_execution_hash:
            # Environment changed — mark task as STALE
            self.db.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
                (TaskStatus.STALE.value, _utc_now(), task_id),
            )
            return AttemptResult(
                attempt_id="",
                task_id=task_id,
                success=False,
                message="ENVIRONMENT_CHANGED_AFTER_MATERIALIZATION",
                details={
                    "expected_hash": env_execution_hash,
                    "current_hash": current_hash,
                },
            )

        # 4. Create Attempt
        attempt_id = uuid.uuid4().hex
        now = _utc_now()
        self.db.execute(
            """INSERT INTO attempts
               (attempt_id, task_id, idempotency_key, workflow_id, params,
                content_hash, dependency_hash, params_hash, status,
                environment_snapshot_id, execution_environment_hash,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                attempt_id,
                task_id,
                idempotency_key,
                workflow_id,
                params_json,
                params_hash,  # content_hash = params_hash for now
                env_execution_hash,  # dependency_hash = env hash
                params_hash,
                SubmissionState.PREPARED.value,
                env_snapshot_id,
                env_execution_hash,
                now,
                now,
            ),
        )

        # 5. Update task status to RUNNING
        self.db.execute(
            """UPDATE tasks SET status = ?, latest_attempt_id = ?, updated_at = ?
               WHERE task_id = ?""",
            (TaskStatus.RUNNING.value, attempt_id, now, task_id),
        )

        # 6. Submit to ComfyUI (MVP: just record the attempt, actual submission
        #    is done by the monitor/collect pipeline)
        prompt_id = self._submit_to_comfyui(attempt_id, workflow_id, params_json)

        # 7. Record in submission journal
        journal_id = uuid.uuid4().hex
        self.db.execute(
            """INSERT INTO submission_journal
               (journal_id, attempt_id, task_id, state, from_state,
                provider_job_id, submitted_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                journal_id,
                attempt_id,
                task_id,
                SubmissionState.SUBMITTED.value,
                SubmissionState.PREPARED.value,
                prompt_id,
                now,
                now,
                now,
            ),
        )

        # 8. Update attempt status
        self.db.execute(
            "UPDATE attempts SET status = ?, updated_at = ? WHERE attempt_id = ?",
            (SubmissionState.SUBMITTED.value, now, attempt_id),
        )

        return AttemptResult(
            attempt_id=attempt_id,
            task_id=task_id,
            success=True,
            prompt_id=prompt_id,
            message=f"Task {task_id} submitted to ComfyUI",
            status=SubmissionState.SUBMITTED.value,
            details={
                "workflow_id": workflow_id,
                "materialization_id": materialization_id,
            },
        )

    def recover_attempt(self, attempt_id: str) -> AttemptResult:
        """Recover a failed or uncertain attempt.

        Steps:
        1. Load attempt and its task
        2. Check submission journal for recoverable prompt_id
        3. If recoverable, resume monitoring
        4. If not, create new attempt

        Args:
            attempt_id: The attempt to recover.

        Returns:
            AttemptResult with recovery details.
        """
        # 1. Load attempt
        attempt_row = self.db.fetchone(
            """SELECT attempt_id, task_id, idempotency_key, workflow_id, params,
                      status, params_hash
               FROM attempts WHERE attempt_id = ?""",
            (attempt_id,),
        )
        if attempt_row is None:
            return AttemptResult(
                attempt_id=attempt_id,
                task_id="",
                success=False,
                message=f"Attempt {attempt_id} not found",
            )

        task_id = attempt_row[1]
        current_status = attempt_row[6]

        # 2. Check journal for recoverable prompt_id
        journal_row = self.db.fetchone(
            """SELECT journal_id, provider_job_id, state
               FROM submission_journal
               WHERE attempt_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (attempt_id,),
        )

        if journal_row is not None:
            journal_id, prompt_id, state = journal_row[0], journal_row[1], journal_row[2]
            if state == SubmissionState.SUBMISSION_UNCERTAIN.value and prompt_id:
                # Recover: resume monitoring with existing prompt_id
                return AttemptResult(
                    attempt_id=attempt_id,
                    task_id=task_id,
                    success=True,
                    prompt_id=prompt_id,
                    message=f"Recovered attempt {attempt_id} with prompt_id {prompt_id}",
                    status=SubmissionState.SUBMITTED.value,
                    details={"recovered": True, "journal_id": journal_id},
                )

        # 3. Cannot recover — return failure
        return AttemptResult(
            attempt_id=attempt_id,
            task_id=task_id,
            success=False,
            message=f"Attempt {attempt_id} cannot be recovered (status: {current_status})",
            status=current_status,
        )

    def _get_current_env_hash(self, snapshot_id: str) -> str | None:
        """Get the current environment hash for comparison."""
        row = self.db.fetchone(
            "SELECT execution_environment_hash FROM environment_snapshots WHERE snapshot_id = ?",
            (snapshot_id,),
        )
        if row is not None:
            return row[0]
        return None

    def _submit_to_comfyui(self, attempt_id: str, workflow_id: str, params_json: str) -> str:
        """Submit a prompt to ComfyUI. Returns prompt_id.

        Steps:
        1. Load workflow JSON from registry
        2. Deep copy to avoid mutating the cached original
        3. Resolve reference bindings → upload images to ComfyUI input dir
        4. Apply text/float/image inputs from params
        5. POST to /prompt endpoint
        """
        import logging
        log = logging.getLogger(__name__)

        params: dict = json.loads(params_json) if params_json else {}

        # 1. Load workflow JSON from registry
        try:
            workflow = load_workflow(workflow_id)
        except FileNotFoundError:
            # Workflow JSON not available (test environment, unregistered
            # workflow, etc.) — fall back to stub prompt_id so the journal
            # record is still created. The monitor/collect pipeline will
            # not find a real ComfyUI job for this prompt_id.
            log.warning(
                "Workflow JSON not found for '%s' — using stub prompt_id",
                workflow_id,
            )
            return uuid.uuid4().hex

        # 2. Deep copy so we don't mutate the cached original
        workflow = deep_copy_workflow(workflow)

        # 3. Resolve reference bindings → upload images + set LoadImage inputs
        #    Also handle any LoadImage nodes in the workflow that aren't covered
        #    by reference_bindings — they need a valid image file or ComfyUI
        #    rejects the prompt with "Invalid image file".
        reference_bindings = params.get("reference_bindings", [])
        binding_snapshot = params.get("_binding_snapshot", {})

        # Build a map of slot → uploaded filename for bindings we process
        uploaded_slots: dict[int, str] = {}

        for binding in reference_bindings:
            slot = binding.get("slot", 0)
            asset_id = binding.get("asset_id", "")
            role = binding.get("role", "")

            # Resolve file_path from binding_snapshot or DB
            file_path = None
            if role in binding_snapshot:
                file_path = binding_snapshot[role].get("file_path")
            if not file_path and asset_id:
                # Fallback: look up asset file_path from DB
                row = self.db.fetchone(
                    "SELECT file_path FROM assets WHERE asset_id = ?",
                    (asset_id,),
                )
                if row:
                    file_path = row[0]

            if not file_path:
                log.warning(
                    "No file_path for binding slot=%s role=%s asset=%s — skipping",
                    slot, role, asset_id,
                )
                continue

            from pathlib import Path
            path = Path(file_path)
            if not path.exists():
                log.warning("Image file not found: %s — skipping", file_path)
                continue

            # Upload to ComfyUI
            try:
                upload_result = self.client.upload_image(path)
                uploaded_name = upload_result.get("name", path.name)
                uploaded_slots[slot] = uploaded_name
                log.info("Uploaded %s as '%s'", path.name, uploaded_name)
            except Exception as exc:
                log.error("Failed to upload %s: %s", file_path, exc)
                continue

        # Set LoadImage inputs for all slots (1-3). For slots without a real
        # uploaded image, use a placeholder so ComfyUI validation passes.
        # If placeholder upload fails, reuse the first available image so
        # ComfyUI never sees a LoadImage referencing a non-existent file.
        title_map = {
            1: "LFO.Reference01",
            2: "LFO.Reference02",
            3: "LFO.Reference03",
        }
        covered_titles = set(title_map.values())
        # Collect fallback images: any successfully uploaded image can serve
        # as a fallback for empty slots (better than a 400 from ComfyUI).
        fallback_images = list(uploaded_slots.values())
        for slot in (1, 2, 3):
            title = title_map.get(slot)
            if title is None:
                continue
            if slot in uploaded_slots:
                apply_image_input(workflow, title, uploaded_slots[slot])
            else:
                # Upload a placeholder for this slot
                placeholder_name = self._upload_placeholder_image(
                    attempt_id, slot,
                )
                if placeholder_name:
                    apply_image_input(workflow, title, placeholder_name)
                    fallback_images.append(placeholder_name)
                elif fallback_images:
                    # Placeholder upload failed — reuse first available image
                    apply_image_input(workflow, title, fallback_images[0])
                    log.warning(
                        "Placeholder upload failed for slot %d — using '%s' as fallback",
                        slot, fallback_images[0],
                    )

        # Handle any other LoadImage nodes not covered by the R2V slot loop
        # (e.g., I2V's LFO.FirstFrame).  ComfyUI rejects workflows where
        # LoadImage nodes reference non-existent files, so we upload a
        # placeholder for any uncovered LoadImage node.
        for node_key, node_def in workflow.items():
            if node_def.get("class_type") != "LoadImage":
                continue
            node_title = node_def.get("_meta", {}).get("title", "")
            if node_title in covered_titles:
                continue  # Already handled by the R2V slot loop
            current_image = node_def.get("inputs", {}).get("image", "")
            if not current_image:
                continue
            placeholder_name = self._upload_placeholder_image(
                attempt_id, f"extra_{node_key}",
            )
            if placeholder_name:
                node_def["inputs"]["image"] = placeholder_name
                log.info(
                    "Uploaded placeholder for LoadImage '%s' (node %s) as '%s'",
                    node_title, node_key, placeholder_name,
                )

        # 4. Apply prompt, duration, and filename prefix from params
        prompt_text = params.get("prompt", "")
        if not prompt_text:
            # Compile prompt from blueprint if available
            blueprint = params.get("prompt_blueprint")
            if blueprint:
                prompt_text = blueprint_to_text(blueprint)
                log.info(
                    "Compiled prompt from blueprint %s (%d chars)",
                    getattr(blueprint, "blueprint_id", "?"),
                    len(prompt_text),
                )
        if prompt_text:
            # R2V: prompt is in "LFO.Prompt" (PrimitiveStringMultiline)
            # T2V: prompt is a direct input on "LFO.MainGenerator"
            applied = apply_text_input(workflow, "LFO.Prompt", prompt_text)
            if not applied:
                applied = self._apply_prompt_to_generator(workflow, prompt_text)
            if not applied:
                log.warning("Could not apply prompt to workflow %s", workflow_id)
        else:
            log.warning("No prompt text for workflow %s — using default", workflow_id)

        duration_sec = params.get("duration_sec", 5)
        apply_float_input(workflow, "LFO.Duration", float(duration_sec))

        shot_id = params.get("shot_id", attempt_id[:12])
        apply_filename_prefix(workflow, "LFO.SaveVideo", f"video/{shot_id}")

        # 5. Submit to ComfyUI
        result = self.client.submit_prompt(workflow, client_id=attempt_id)
        prompt_id = result.get("prompt_id", "")
        log.info(
            "Submitted to ComfyUI: workflow=%s prompt_id=%s shot=%s",
            workflow_id, prompt_id, shot_id,
        )

        if not prompt_id:
            # Fallback: still return something for the journal record
            prompt_id = uuid.uuid4().hex
            log.warning("ComfyUI returned no prompt_id — using fallback %s", prompt_id)

        return prompt_id

    def _upload_placeholder_image(self, attempt_id: str, slot: int) -> str:
        """Upload a small placeholder image to ComfyUI for a reference slot.

        Used when a LoadImage node in the workflow doesn't have a real
        reference image (e.g. T2V mode with only 1 character ref, leaving
        slots 2 and 3 empty). ComfyUI rejects prompts where LoadImage nodes
        reference non-existent files.

        Returns the uploaded filename, or empty string on failure.
        """
        import logging
        import tempfile
        from pathlib import Path

        log = logging.getLogger(__name__)

        # Create a 64x64 neutral gray PNG
        placeholder_name = f"placeholder_{attempt_id[:8]}_{slot}.png"
        try:
            from PIL import Image
            img = Image.new("RGB", (64, 64), color=(128, 128, 128))
        except ImportError:
            # PIL not available — create minimal valid PNG manually
            # (1x1 white pixel PNG)
            import struct, zlib
            def _minimal_png():
                signature = b'\x89PNG\r\n\x1a\n'
                # IHDR
                ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
                ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff
                ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
                # IDAT
                raw = zlib.compress(b'\x00\xff\xff\xff')
                idat_crc = zlib.crc32(b'IDAT' + raw) & 0xffffffff
                idat = struct.pack('>I', len(raw)) + b'IDAT' + raw + struct.pack('>I', idat_crc)
                # IEND
                iend_crc = zlib.crc32(b'IEND') & 0xffffffff
                iend = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
                return signature + ihdr + idat + iend
            img = None

        tmp_path = Path(tempfile.gettempdir()) / placeholder_name
        try:
            if img is not None:
                img.save(str(tmp_path), "PNG")
            else:
                tmp_path.write_bytes(_minimal_png())

            result = self.client.upload_image(tmp_path)
            name = result.get("name", placeholder_name)
            log.info("Uploaded placeholder for slot %d as '%s'", slot, name)
            return name
        except Exception as exc:
            log.error("Failed to upload placeholder for slot %d: %s", slot, exc)
            return ""
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    @staticmethod
    def _apply_prompt_to_generator(workflow: dict, prompt_text: str) -> bool:
        """Apply prompt directly to LFO.MainGenerator's `prompt` input.

        Used for T2V workflows where the prompt is a direct string input on
        the MainGenerator node rather than a separate PrimitiveStringMultiline.
        """
        from lfo.comfy.workflow_loader import find_node_by_title

        node_key = find_node_by_title(workflow, "LFO.MainGenerator")
        if node_key is None:
            return False
        node = workflow[node_key]
        inputs = node.get("inputs", {})
        if "prompt" not in inputs:
            return False
        # Only set if it's a simple value (string), not a link (list)
        if isinstance(inputs["prompt"], str):
            inputs["prompt"] = prompt_text
            return True
        return False


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")

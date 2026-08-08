"""PipelineService — execute full storyboard → video pipeline.

Flow per shot:
  promote → execute → collect → QC → normalize → create selection →
  render selection → approve selection → extract end frame from clip

Post-shot assembly:
  create EDL → resolve clips → assemble MP4 → generate SRT → final QC
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from lfo.application.execution_facade import ExecutionFacade
from lfo.assembly.compiler import AssemblyCompiler
from lfo.assembly.service import AssemblyService
from lfo.comfy.client import ComfyApiClient
from lfo.comfy.collect import ComfyOutputCollector
from lfo.comfy.monitor import ComfyMonitor
from lfo.core.database import Database
from lfo.core.disk_guard import DiskSpaceStatus, check_disk_space
from lfo.core.state_machine import TaskStatus
from lfo.services import workspace
from lfo.services.character_sheet_service import CharacterSheetService
from lfo.services.editorial_service import EditorialService
from lfo.services.edl_service import EDLService
from lfo.services.end_frame_extractor import EndFrameExtractor
from lfo.services.final_qc_service import FinalQCService
from lfo.services.media_service import MediaService
from lfo.services.srt_generator import SRTGenerator
from lfo.services.storyboard_graph_service import StoryboardGraphService
from lfo.services.task_readiness_service import TaskReadinessService
from lfo.services.technical_qc_service import QCSpec, TechnicalQCService
from lfo.services.video_collect_service import VideoCollectService
from lfo.storyboard.storyboard import Storyboard
from lfo.visual.image_request import read_batch


@dataclass
class TaskPipelineResult:
    """Result of processing a single task through the pipeline."""

    task_id: str
    shot_id: str
    success: bool = False
    status: str = ""
    asset_id: str = ""
    normalized_asset_id: str = ""
    selected_clip_id: str = ""
    selected_clip_status: str = ""
    error: str = ""
    qc_passed: bool = False
    normalized: bool = False
    end_frame_extracted: bool = False


@dataclass
class AssemblyPipelineResult:
    """Result of the post-shot assembly phase."""

    success: bool = False
    edl_id: str = ""
    output_asset_id: str = ""
    output_file_path: str = ""
    srt_asset_id: str = ""
    srt_file_path: str = ""
    final_qc_passed: bool = False
    error: str = ""


@dataclass
class PipelineResult:
    """Result of executing the full pipeline."""

    project_id: str
    success: bool = False
    task_results: list[TaskPipelineResult] = field(default_factory=list)
    assembly_result: AssemblyPipelineResult = field(default_factory=AssemblyPipelineResult)
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    errors: list[str] = field(default_factory=dict)
    image_phase: dict = field(default_factory=dict)  # Phase 0 image generation status
    paused: bool = False  # True when waiting for user to generate images


class PipelineService:
    """Execute the full storyboard → video pipeline.

    Path resolution priority for the novel/chapter pair:

    1. **Explicit args** — ``novel_id=...`` and ``chapter_id=...`` are used
       directly. This is the safest mode; recommended for any storyboard
       that has a non-ASCII or dash-containing novel name.
    2. **Derive from ``project_id``** — split on the first ``-`` (legacy
       behaviour). Only used when explicit args are missing.
    3. **Flat fallback** — if project_id has no ``-`` and no explicit args,
       both novel and chapter are the same as project_id.

    The on-disk layout is novel-centric (``<workspace>/<novel>/<chapter>/``);
    see ``services.workspace`` for the full path contract.
    """

    def __init__(
        self,
        db: Database,
        comfy_url: str = "http://127.0.0.1:8188",
        output_dir: str = "",
        auto_approve: bool = False,
        comfy_output_root: str = "",
        project_id: str = "default",
        novel_id: str = "",
        chapter_id: str = "",
        skip_images: bool = False,
    ) -> None:
        self.db = db
        self.project_id = project_id
        self.skip_images = skip_images

        # Resolve the (novel_id, chapter_id) pair for path layout.
        # 1. Both explicit → use them. 2. Only one explicit → derive the
        #    other from project_id. 3. Neither → fall back to splitting
        #    project_id on the first '-', with a flat single-segment
        #    fallback.
        if novel_id and chapter_id:
            resolved_novel, resolved_chapter = novel_id, chapter_id
        elif novel_id and not chapter_id:
            resolved_novel = novel_id
            resolved_chapter = project_id if project_id else novel_id
        elif chapter_id and not novel_id:
            resolved_chapter = chapter_id
            resolved_novel = project_id if project_id else chapter_id
        else:
            # Neither explicit — legacy derivation. If the novel name
            # contains '-' (e.g. "sci-fi-2025"), this will mis-split; the
            # caller should pass explicit args in that case.
            if "-" in project_id:
                resolved_novel, resolved_chapter = project_id.split("-", 1)
            else:
                resolved_novel, resolved_chapter = project_id, project_id
        self.novel_id = resolved_novel
        self.chapter_id = resolved_chapter
        # If the caller didn't pin an output_dir, derive it from the workspace.
        # Each project gets its own subdir so novels / storyboards / outputs
        # never bleed into each other. See services.workspace.
        if output_dir:
            self.output_dir = output_dir
        else:
            self.output_dir = str(
                workspace.project_output_dir(resolved_novel, resolved_chapter),
            )
        os.makedirs(self.output_dir, exist_ok=True)
        self.auto_approve = auto_approve

        # Resolve ComfyUI output root: explicit arg > workspace default > legacy env
        if comfy_output_root:
            comfy_root = comfy_output_root
        else:
            comfy_root = str(
                workspace.project_output_dir(resolved_novel, resolved_chapter) / "comfy",
            )
        os.makedirs(comfy_root, exist_ok=True)

        # ComfyUI
        self.client = ComfyApiClient(comfy_url)
        self.monitor = ComfyMonitor(self.client)

        # Services
        self.graph_service = StoryboardGraphService(db)
        self.readiness_service = TaskReadinessService(db)
        self.execution_facade = ExecutionFacade(db, self.client)
        self.collector = ComfyOutputCollector(
            output_root=Path(comfy_root),
            assets_dir=Path(self.output_dir) / "assets",
        )
        self.video_collect = VideoCollectService(
            db, self.collector, self.monitor,
        )
        self.qc_service = TechnicalQCService(db)
        self.media_service = MediaService(
            db, output_dir=str(Path(self.output_dir) / "normalized"),
        )
        self.end_frame_extractor = EndFrameExtractor(
            db, output_dir=str(Path(self.output_dir) / "end_frames"),
        )
        self.editorial_service = EditorialService(db, media_service=self.media_service)
        self.edl_service = EDLService(db)
        self.srt_generator = SRTGenerator(
            db, output_dir=str(Path(self.output_dir) / "srt"),
        )
        self.final_qc_service = FinalQCService(db)
        self.assembly_compiler = AssemblyCompiler(
            db, output_dir=str(Path(self.output_dir) / "assembly"),
        )
        self.assembly_service = AssemblyService(
            db,
            compiler=self.assembly_compiler,
            edl_service=self.edl_service,
        )
        self.character_sheet_service = CharacterSheetService(db, output_root=str(self.output_dir))

        # Disk preflight: warn if the output volume is near-full. Never
        # blocks the run — the user might have cleaned up concurrently —
        # but the warning is loud and visible so it can't be missed.
        self._disk_status = self._preflight_disk()

    # -- public API ------------------------------------------------------- #

    def execute(self, storyboard: Storyboard) -> PipelineResult:
        """Execute the full pipeline for a storyboard.

        Steps:
        0. Phase 0: Character sheet image generation (if needed)
        1. Build task graph from storyboard
        2. For each task (in dependency order):
           a. Promote → Execute → Collect → QC → Normalize
           b. Create selection → Render → Approve → Extract end frame
        3. Assembly: EDL → Resolve → Assemble MP4 → SRT → Final QC
        """
        result = PipelineResult(project_id=storyboard.project.project_id)
        self._storyboard = storyboard

        # Ensure project exists in DB
        self._ensure_project(storyboard.project.project_id, storyboard.project.title)

        # Phase 0: Character sheet image generation
        if not self.skip_images:
            image_phase = self._run_image_phase(storyboard)
            result.image_phase = image_phase
            if image_phase.get("status") == "waiting":
                result.paused = True
                result.errors["image_phase"] = (
                    "Character sheet images required. "
                    "Run 'lfo images build <storyboard.json>' to create requests, "
                    "generate images with your agent, then re-run 'lfo run'."
                )
                return result
            if image_phase.get("status") == "failed":
                result.errors["image_phase"] = image_phase.get("error", "Image generation failed")
                # Continue with pipeline — images are best-effort
                print(f"[Pipeline] Image phase warning: {result.errors['image_phase']}")

        # 1. Build task graph
        print(f"[Pipeline] Building task graph for {storyboard.project.project_id}...")
        graph = self.graph_service.build_graph(storyboard)
        tasks = graph.tasks
        result.total_tasks = len(tasks)
        print(f"[Pipeline] {len(tasks)} tasks created")

        if not tasks:
            result.success = True
            return result

        # 2. Process each task
        for i, planned_task in enumerate(tasks):
            if planned_task.status == "WAITING_ASSETS":
                print(
                    f"\n[Pipeline] Task {i + 1}/{len(tasks)}: "
                    f"{planned_task.task_id} — waiting for assets, skipping"
                )
                result.task_results.append(
                    TaskPipelineResult(
                        task_id=planned_task.task_id,
                        shot_id=(
                            planned_task.target_ids[0]
                            if planned_task.target_ids
                            else ""
                        ),
                        status="WAITING_ASSETS",
                    )
                )
                continue

            print(f"\n[Pipeline] Task {i + 1}/{len(tasks)}: {planned_task.task_id}")
            task_result = self._process_task(planned_task)
            result.task_results.append(task_result)

            if task_result.success:
                result.completed_tasks += 1
            else:
                result.failed_tasks += 1
                result.errors[planned_task.task_id] = task_result.error

        # 3. Assembly pipeline (if all shots succeeded)
        if result.failed_tasks == 0 and result.completed_tasks > 0:
            print("\n[Pipeline] Running assembly pipeline...")
            assembly_result = self._run_assembly_pipeline(storyboard)
            result.assembly_result = assembly_result
            if not assembly_result.success:
                result.errors["assembly"] = assembly_result.error

        # Final status
        result.success = result.failed_tasks == 0 and result.assembly_result.success
        return result

    # -- image phase ---------------------------------------------------- #

    def _run_image_phase(self, storyboard: Storyboard) -> dict:
        """Run Phase 0: character sheet image generation.

        Returns a dict with status and details:
        - {"status": "skipped"} — all characters already have ref images
        - {"status": "collected"} — results file found and collected
        - {"status": "waiting"} — requests written, waiting for user to generate
        """
        # Check if there's an existing batch with results
        batch_dir = (
            Path(self.output_dir) / self.novel_id / self.chapter_id / "image_requests"
        )
        if batch_dir.exists():
            # Look for existing batch files with corresponding results
            batch_files = sorted(
                [f for f in batch_dir.glob("batch_*.json") if not f.name.endswith("_results.json")],
                key=lambda f: f.stat().st_mtime,
            )
            for batch_file in batch_files:
                results_file = batch_file.with_name(f"{batch_file.stem}_results.json")
                if results_file.exists():
                    # Collect from existing results
                    batch = read_batch(str(batch_file))
                    print(f"[Pipeline] Image phase: collecting results from {results_file}")
                    collected = self.character_sheet_service.collect_results(
                        batch, str(results_file), storyboard,
                    )
                    success_count = sum(1 for c in collected if c.success)
                    fail_count = sum(1 for c in collected if not c.success)
                    print(
                        f"[Pipeline] Image phase: collected {success_count}/{len(collected)} "
                        f"({fail_count} failed)",
                    )
                    return {
                        "status": "collected",
                        "requests_count": len(batch.requests),
                        "success_count": success_count,
                        "fail_count": fail_count,
                        "batch_id": batch.batch_id,
                    }

        batch = self.character_sheet_service.build_requests(
            storyboard, storyboard.project.project_id,
        )

        if not batch.requests:
            print("[Pipeline] Image phase: all characters already have ref images, skipping")
            return {"status": "skipped", "requests_count": 0}

        # Write batch to disk
        batch_path = self.character_sheet_service.write_requests(
            batch, self.novel_id, self.chapter_id,
        )
        print(f"[Pipeline] Image phase: {len(batch.requests)} requests written to {batch_path}")

        # Check if results file exists
        results_path = batch_path.with_name(f"{batch.batch_id}_results.json")
        if results_path.exists():
            print(f"[Pipeline] Image phase: collecting results from {results_path}")
            collected = self.character_sheet_service.collect_results(
                batch, str(results_path), storyboard,
            )
            success_count = sum(1 for c in collected if c.success)
            fail_count = sum(1 for c in collected if not c.success)
            print(
                f"[Pipeline] Image phase: collected {success_count}/{len(collected)} "
                f"({fail_count} failed)",
            )
            return {
                "status": "collected",
                "requests_count": len(batch.requests),
                "success_count": success_count,
                "fail_count": fail_count,
                "batch_id": batch.batch_id,
            }

        # Results not available yet — pause pipeline
        print(
            f"[Pipeline] Image phase: waiting for character sheet generation. "
            f"Run your agent to generate images, then re-run 'lfo run'."
        )
        return {
            "status": "waiting",
            "requests_count": len(batch.requests),
            "batch_id": batch.batch_id,
            "batch_path": str(batch_path),
            "results_path": str(results_path),
        }

    # -- prompt compilation --------------------------------------------- #

    def _compile_prompt_for_task(self, planned_task) -> str:
        """Compile the prompt text for a planned task from the storyboard."""
        from lfo.services.panel_generation_service import PanelGenerationService
        from lfo.services.storyboard_graph_service import StoryboardGraphService

        panel_id = planned_task.target_ids[0] if planned_task.target_ids else ""
        if not panel_id or not hasattr(self, "_storyboard"):
            return ""

        panel = self._storyboard.panel_by_id(panel_id)
        if panel is not None and panel.prompt_text:
            return panel.prompt_text

        project_id = self._storyboard.project.project_id
        available_assets = StoryboardGraphService(self.db)._load_available_assets(project_id)

        svc = PanelGenerationService()
        plan = svc.generate_plan(
            self._storyboard,
            project_id,
            available_assets=available_assets,
        )
        for panel_plan in plan.panel_plans:
            if panel_plan.panel_id == panel_id:
                return panel_plan.prompt_text
        return ""

    def _get_panel_duration(self, panel_id: str) -> int:
        """Get desired duration in seconds for a panel from the storyboard."""
        if not panel_id or not hasattr(self, "_storyboard"):
            return 5
        panel = self._storyboard.panel_by_id(panel_id)
        if panel is None:
            return 5
        return max(1, (panel.desired_duration_ms + 500) // 1000)

    def _get_shot_duration(self, shot_id: str) -> int:
        """Legacy alias — target_ids are panel ids in the panel-only model."""
        return self._get_panel_duration(shot_id)

    # -- continuity binding ---------------------------------------------- #

    def _bind_end_frame_to_next_shot(
        self,
        source_shot_id: str,
        end_frame_asset_id: str,
    ) -> None:
        """No-op in panel-only r2v execution.

        End frames must not replace composition_ref or veto r2v; continuity
        is carried via PanelPack, not shot-to-shot start_frame binding.
        """
        return

    # -- per-task processing --------------------------------------------- #

    def _process_task(self, planned_task) -> TaskPipelineResult:
        """Process a single task through the full pipeline."""
        task_result = TaskPipelineResult(
            task_id=planned_task.task_id,
            shot_id=planned_task.target_ids[0] if planned_task.target_ids else "",
        )

        # a. Promote to READY
        print(f"  [1/8] Promoting {planned_task.task_id} to READY...")
        # Build the params dict from the planned task. These become part
        # of params_hash + idempotency_key inside promote_to_ready. For
        # the live E2E the prompt blueprint drives the full render
        # parameter set, so this is a minimal subset: the workflow, the
        # reference bindings, and the desired duration.
        #
        # Also resolve the binding_snapshot so execution_facade can find
        # file_paths for each reference binding when uploading to ComfyUI.
        binding_snapshot: dict = {}
        for req in planned_task.asset_requirements:
            entity_id = getattr(req, "entity_id", None) or getattr(req, "target_id", "")
            role = getattr(req, "asset_role", "")
            # Look up current approved asset for this requirement
            try:
                entity_type = getattr(req, "entity_type", None) or role
                approved = self.readiness_service.asset_service.get_current_approved_asset(
                    project_id=self._storyboard.project.project_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    asset_role=role,
                )
                binding_snapshot[role] = {
                    "asset_id": approved.asset_id,
                    "binding_id": approved.binding_id,
                    "file_path": approved.file_path,
                    "file_hash": approved.file_hash,
                    "content_hash": approved.content_hash,
                }
            except Exception:
                pass  # requirement not yet met — promote_to_ready will block

        # Compile prompt blueprint → text for the LFO.Prompt input
        prompt_text = self._compile_prompt_for_task(planned_task)

        # Get shot duration from storyboard
        shot_id = planned_task.target_ids[0] if planned_task.target_ids else ""
        duration_sec = self._get_shot_duration(shot_id)

        params = {
            "workflow_id": planned_task.workflow_id,
            "aligned_frames": planned_task.aligned_frames,
            "reference_bindings": [
                {
                    "slot": b.slot,
                    "asset_id": b.asset_id,
                    "entity_id": b.entity_id,
                    "role": b.role,
                    "is_symbolic": b.is_symbolic,
                }
                for b in planned_task.reference_bindings
            ],
            "_binding_snapshot": binding_snapshot,
            "prompt": prompt_text,
            "prompt_blueprint_id": planned_task.prompt_blueprint_id,
            "duration_sec": duration_sec,
            "shot_id": shot_id,
        }
        promo_result = self.readiness_service.promote_to_ready(
            planned_task.task_id,
            asset_requirements=list(planned_task.asset_requirements),
            workflow_id=planned_task.workflow_id,
            params=params,
        )
        if not promo_result.success:
            print(f"        Promotion pending: {promo_result.message}")
        else:
            print(f"        Promoted: {promo_result.materialization_id}")

        # b. Execute
        print(f"  [2/8] Executing {planned_task.task_id}...")
        exec_result = self.execution_facade.run_ready_task(planned_task.task_id)
        if not exec_result.success:
            task_result.error = f"Execution failed: {exec_result.message}"
            print(f"        FAILED: {exec_result.message}")
            return task_result
        print(f"        Submitted: prompt_id={exec_result.prompt_id}")

        # c. Collect
        print("  [3/8] Collecting output...")
        collect_result = self.video_collect.collect(exec_result.attempt_id)
        if not collect_result.success:
            task_result.error = f"Collection failed: {'; '.join(collect_result.errors)}"
            print(f"        FAILED: {task_result.error}")
            return task_result
        print(f"        Collected: {len(collect_result.assets)} asset(s)")

        # Get the primary asset
        primary_asset = collect_result.assets[0] if collect_result.assets else None
        if primary_asset is None:
            task_result.error = "No assets collected"
            print("        FAILED: No assets")
            return task_result

        # Find the asset_id in DB
        asset_row = self.db.fetchone(
            "SELECT asset_id FROM assets WHERE attempt_id = ?",
            (exec_result.attempt_id,),
        )
        asset_id = asset_row[0] if asset_row else ""
        task_result.asset_id = asset_id

        # d. QC
        print("  [4/8] Running QC...")
        spec = QCSpec(
            width=864,
            height=480,
            fps=24.0,
            duration_sec=5.0,
            requires_audio=True,
            expected_video_codec="h264",
            duration_tolerance_sec=1.0,
        )
        qc_result = self.qc_service.check_asset(asset_id, spec)
        task_result.qc_passed = qc_result.passed
        print(f"        QC: {qc_result.status}")

        # e. Normalize (registers output as new asset)
        print("  [5/8] Normalizing...")
        try:
            normalized = self.media_service.normalize(asset_id, "vertical_h264_v1")
            task_result.normalized = True
            task_result.normalized_asset_id = normalized.asset_id
            print(f"        Normalized: {normalized.file_path} (asset_id={normalized.asset_id})")
        except Exception as e:
            print(f"        Normalize failed: {e}")
            task_result.error = f"Normalize failed: {e}"
            return task_result

        # f. Create selection → Render
        print("  [6/8] Creating + rendering selected clip...")
        try:
            selection = self.editorial_service.create_selection(
                project_id=self._storyboard.project.project_id,
                shot_id=task_result.shot_id,
                normalized_asset_id=task_result.normalized_asset_id,
            )
            rendered = self.editorial_service.render_selected_clip(selection.selected_clip_id)
            task_result.selected_clip_id = rendered.selected_clip_id
            task_result.selected_clip_status = rendered.status
            print(f"        Selection: {rendered.selected_clip_id} status={rendered.status}")
        except Exception as e:
            print(f"        Selection failed: {e}")
            task_result.error = f"Selection failed: {e}"
            return task_result

        if task_result.selected_clip_status == "technical_failed":
            task_result.error = "Selected clip technical QC failed"
            print("        FAILED: technical QC")
            return task_result

        # g. Approve
        print("  [7/8] Approving selected clip...")
        if self.auto_approve:
            try:
                approved = self.editorial_service.approve_selected_clip(task_result.selected_clip_id)
                task_result.selected_clip_status = approved.status
                print("        Auto-approved")
            except Exception as e:
                print(f"        Approval failed: {e}")
                task_result.error = f"Approval failed: {e}"
                return task_result
        else:
            print("        WAITING_USER (auto_approve=False)")

        # h. Extract end frame from approved clip
        end_frame_asset_id = ""
        if task_result.selected_clip_status == "approved":
            print("  [8/8] Extracting end frame from clip...")
            try:
                frame_result = self.end_frame_extractor.extract_from_clip(
                    task_result.selected_clip_id,
                )
                task_result.end_frame_extracted = frame_result.success
                if frame_result.success:
                    end_frame_asset_id = frame_result.frame_asset_id
                    print(f"        Frame: {frame_result.file_path}")
                else:
                    print(f"        Frame extraction failed: {frame_result.error}")
            except Exception as e:
                print(f"        End frame extraction error: {e}")
        else:
            print(f"  [8/8] Skipping end clip (status={task_result.selected_clip_status})")

        # i. Bind end frame as start_frame for the next shot in continuity chain
        if end_frame_asset_id and task_result.shot_id:
            self._bind_end_frame_to_next_shot(
                source_shot_id=task_result.shot_id,
                end_frame_asset_id=end_frame_asset_id,
            )

        task_result.success = True
        task_result.status = "SUCCEEDED"
        return task_result

    # -- post-shot assembly ---------------------------------------------- #

    def _run_assembly_pipeline(self, storyboard: Storyboard) -> AssemblyPipelineResult:
        """Run the assembly pipeline after all shots are processed."""
        result = AssemblyPipelineResult()

        # 1. Build panel order from storyboard
        panel_ids = [p.panel_id for p in storyboard.panels]
        if not panel_ids:
            result.error = "No panels in storyboard"
            return result

        # 2. Create + approve EDL (shot_ids param holds panel ids)
        print("  [Assembly] Creating EDL...")
        edl = self.edl_service.create_edl(
            project_id=storyboard.project.project_id,
            shot_ids=panel_ids,
            export_profile_id="vertical_h264_v1",
            subtitle_enabled=True,
        )
        self.edl_service.approve_edl(edl.edl_id)
        result.edl_id = edl.edl_id
        print(f"  [Assembly] EDL: {edl.edl_id}")

        # 3. Build assembly snapshot (resolve clips)
        print("  [Assembly] Resolving clips...")
        resolved = self.edl_service.resolve_clips(edl.edl_id)
        snapshot = self.assembly_service._build_snapshot(
            edl.edl_id, storyboard.project.project_id, resolved,
        )
        if not snapshot.clips:
            result.error = "No clips resolved for assembly"
            return result

        # 4. Assemble
        print("  [Assembly] Assembling MP4...")
        assembly_result = self.assembly_service.build_from_edl(edl.edl_id)
        if not assembly_result.success:
            result.error = assembly_result.error
            return result

        result.output_asset_id = assembly_result.output_asset_id
        result.output_file_path = assembly_result.output_file_path
        print(f"  [Assembly] Output: {assembly_result.output_file_path}")

        # 5. Generate SRT
        print("  [Assembly] Generating SRT...")
        srt_result = self.srt_generator.generate(
            edl.edl_id,
            storyboard,
            snapshot,
            language="zh-CN",
        )
        if srt_result.success:
            srt_asset_id = self.srt_generator.register_srt_asset(
                edl.edl_id,
                storyboard.project.project_id,
                srt_result.file_path,
                srt_result.cue_count,
            )
            result.srt_asset_id = srt_asset_id
            result.srt_file_path = srt_result.file_path
            print(f"  [Assembly] SRT: {srt_result.file_path} ({srt_result.cue_count} cues)")
        else:
            print(f"  [Assembly] SRT generation skipped: {srt_result.error}")

        # 6. Final QC
        print("  [Assembly] Running final QC...")
        qc_result = self.final_qc_service.validate(
            video_asset_id=result.output_asset_id,
            srt_asset_id=result.srt_asset_id,
            expected_duration_sec=snapshot.total_duration_sec,
        )
        result.final_qc_passed = qc_result.success
        if not qc_result.success:
            result.error = f"Final QC failed: {'; '.join(qc_result.issues)}"
            print(f"  [Assembly] Final QC FAILED: {qc_result.issues}")
        else:
            print("  [Assembly] Final QC PASSED")

        result.success = True
        return result

    # -- internal helpers -------------------------------------------------

    def _preflight_disk(self) -> DiskSpaceStatus | None:
        """Check free space on the output volume and log a warning if low.

        Returns the status object so callers / tests can introspect.
        Never raises — if the check itself fails we just stay silent.
        """
        logger = logging.getLogger(__name__)
        try:
            status = check_disk_space(self.output_dir)
        except Exception as e:
            logger.debug("disk preflight failed: %s", e)
            return None

        if status.should_warn:
            free_gb = status.free_bytes / (1024**3) if status.free_bytes else 0
            if status.should_block:
                logger.warning(
                    "Disk space CRITICAL on %s: only %.1f GB free. "
                    "Pipeline may run out of disk mid-batch. Free space first.",
                    status.path, free_gb,
                )
            else:
                logger.warning(
                    "Disk space low on %s: %.1f GB free. "
                    "Consider cleaning up before running a multi-shot batch.",
                    status.path, free_gb,
                )
        return status

    def _ensure_project(self, project_id: str, title: str = "") -> None:
        """Insert project row if it doesn't exist."""
        row = self.db.fetchone(
            "SELECT project_id FROM projects WHERE project_id = ?",
            (project_id,),
        )
        if row is None:
            self.db.execute(
                "INSERT INTO projects (project_id, name) VALUES (?, ?)",
                (project_id, title or project_id),
            )


def _utc_now() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%fZ")


# ============================================================================
# Blocked-downstream detection
# ============================================================================
#
# ``promote_task_to_ready`` (core/runtime.py) only allows promotion when every
# dependency is in ``TASK_TERMINAL_STATES``. ``FAILED_RETRYABLE`` is *not*
# terminal — so a downstream of a FAILED_RETRYABLE task is permanently stuck
# in PLANNED even though the upstream is by definition "going to be retried".
#
# To fix this without modifying the conservative contract of
# ``promote_task_to_ready``, the pipeline exposes a discoverer:
# ``find_unblocked_tasks`` returns PLANNED tasks whose entire dependency
# chain is in the OK set (SUCCEEDED / APPROVED / FAILED_RETRYABLE). The
# caller can then decide whether to call ``promote_task_to_ready`` for
# each — typically after a successful retry of the upstream.

_OK_UPSTREAM_STATES = frozenset({
    TaskStatus.SUCCEEDED.value,
    TaskStatus.APPROVED.value,
    TaskStatus.FAILED_RETRYABLE.value,
})

_BLOCKING_UPSTREAM_STATES = frozenset({
    TaskStatus.FAILED_TERMINAL.value,
    TaskStatus.STALE.value,
    TaskStatus.NEEDS_REMATERIALIZATION.value,
    TaskStatus.CANCELLED.value,
    TaskStatus.SUPERSEDED.value,
})


def find_unblocked_tasks(db: Database, project_id: str) -> list[dict]:
    """Return PLANNED tasks in ``project_id`` whose dependencies are all OK.

    A task is "unblocked" iff:
    - its status is PLANNED, AND
    - every dependency is in the OK set (SUCCEEDED / APPROVED /
      FAILED_RETRYABLE). If any dependency is RUNNING / QUEUED /
      WAITING_USER / READY / PLANNED / STALE / FAILED_TERMINAL / etc.,
      the task stays blocked.

    Returns a list of task dicts (with ``task_id`` and ``dependencies``).
    The caller decides what to do with the result.
    """
    rows = db.fetchall(
        """SELECT task_id, dependencies
           FROM tasks
           WHERE project_id = ? AND status = ?""",
        (project_id, TaskStatus.PLANNED.value),
    )
    if not rows:
        return []

    # Pre-fetch dependency statuses in one query to avoid N+1
    dep_ids: set[str] = set()
    parsed: list[tuple[str, list[str]]] = []
    for row in rows:
        deps_raw = row[1] or "[]"
        try:
            deps = json.loads(deps_raw) if isinstance(deps_raw, str) else list(deps_raw)
        except (ValueError, TypeError):
            deps = []
        parsed.append((row[0], deps))
        dep_ids.update(deps)

    if dep_ids:
        placeholders = ",".join("?" for _ in dep_ids)
        dep_rows = db.fetchall(
            f"SELECT task_id, status FROM tasks WHERE task_id IN ({placeholders})",
            tuple(dep_ids),
        )
        dep_status = {tid: status for tid, status in dep_rows}
    else:
        dep_status = {}

    unblocked: list[dict] = []
    for task_id, deps in parsed:
        if not deps:
            # No dependencies — trivially unblocked
            unblocked.append({"task_id": task_id, "dependencies": []})
            continue
        all_ok = all(dep_status.get(d) in _OK_UPSTREAM_STATES for d in deps)
        if all_ok:
            unblocked.append({"task_id": task_id, "dependencies": deps})

    return unblocked


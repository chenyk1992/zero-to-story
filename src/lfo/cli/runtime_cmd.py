"""lfo runtime commands — validate, plan, execute, status, retry, cancel, export.

New v1 runtime CLI for VideoExecutionPackage execution.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from lfo.application.video_runtime import VideoRuntime
from lfo.backends.capabilities import CapabilityManifest
from lfo.backends.registry import BackendRegistry
from lfo.cli.output import CommandResult
from lfo.cli.registry import CommandRegistry

logger = logging.getLogger(__name__)


def _default_registry() -> BackendRegistry:
    """Create a registry with the H3 backend pre-registered."""
    reg = BackendRegistry()
    reg.register(CapabilityManifest(
        backend_id="comfyui.h3",
        revision="1.0.0",
        workflow_hash="wf-h3-r2v-1",
        operations=["video.text_to_video", "video.reference_to_video", "video.image_to_video"],
        accepted_media_types=["image", "video"],
        max_references=9,
        duration_constraints={"min_ms": 500, "max_ms": 60000},
        frame_constraints={"formula": "17k+5"},
        resolution_constraints={"min_width": 256, "max_width": 1920, "min_height": 256, "max_height": 1920},
        fps_constraints=[24.0],
        native_audio_capability="optional",
        seed_capability=True,
        reproducibility_claim="best_effort",
    ))
    return reg


# ===========================================================================
# lfo validate
# ===========================================================================

def cmd_validate(package_path: str = "") -> dict:
    """Validate a VideoExecutionPackage file."""
    if not package_path:
        return {"success": False, "error": "package_path is required"}
    runtime = VideoRuntime(_default_registry())
    result = runtime.validate(package_path)
    return {
        "success": result.valid,
        "valid": result.valid,
        "errors": result.errors,
    }


# ===========================================================================
# lfo plan
# ===========================================================================

def cmd_plan(package_path: str = "") -> dict:
    """Generate an execution plan without running."""
    if not package_path:
        return {"success": False, "error": "package_path is required"}
    runtime = VideoRuntime(_default_registry())
    result = runtime.plan(package_path)
    return {
        "success": result.error is None,
        "plan_id": result.plan_id,
        "clips": result.clip_plans,
        "warnings": result.warnings,
        "error": result.error,
    }


# ===========================================================================
# lfo execute
# ===========================================================================

def cmd_execute(package_path: str = "", approve: bool = False) -> dict:
    """Execute a VideoExecutionPackage."""
    if not package_path:
        return {"success": False, "error": "package_path is required"}
    runtime = VideoRuntime(_default_registry())
    result = runtime.execute(package_path, approval=approve)
    return {
        "success": result.status == "COMPLETED",
        "run_id": result.run_id,
        "status": result.status,
        "clip_count": result.clip_count,
        "error": result.error,
    }


# ===========================================================================
# lfo status
# ===========================================================================

def cmd_runtime_status(run_id: str = "") -> dict:
    """Get status of a v1 runtime run."""
    if not run_id:
        return {"success": False, "error": "run_id is required"}
    runtime = VideoRuntime(_default_registry())
    result = runtime.status(run_id)
    return {
        "success": result.error is None,
        "run_id": result.run_id,
        "status": result.status,
        "tasks": result.tasks,
        "error": result.error,
    }


# ===========================================================================
# lfo retry
# ===========================================================================

def cmd_retry(run_id: str = "", clip_id: str = "") -> dict:
    """Retry a failed run or clip."""
    if not run_id:
        return {"success": False, "error": "run_id is required"}
    runtime = VideoRuntime(_default_registry())
    result = runtime.retry(run_id, scope=clip_id or None)
    return {
        "success": result.status == "COMPLETED",
        "run_id": result.run_id,
        "status": result.status,
        "error": result.error,
    }


# ===========================================================================
# lfo cancel
# ===========================================================================

def cmd_cancel(run_id: str = "") -> dict:
    """Cancel a run."""
    if not run_id:
        return {"success": False, "error": "run_id is required"}
    runtime = VideoRuntime(_default_registry())
    runtime.cancel(run_id)
    return {"success": True, "run_id": run_id, "status": "CANCELLED"}


# ===========================================================================
# lfo export
# ===========================================================================

def cmd_export(run_id: str = "") -> dict:
    """Export a completed run."""
    if not run_id:
        return {"success": False, "error": "run_id is required"}
    runtime = VideoRuntime(_default_registry())
    result = runtime.export(run_id)
    return {
        "success": result.status == "READY",
        "export_id": result.export_id,
        "status": result.status,
        "file_path": result.file_path,
        "error": result.error,
    }

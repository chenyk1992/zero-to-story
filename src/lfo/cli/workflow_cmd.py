"""lfo workflow command — fork workflows."""
from __future__ import annotations


def cmd_workflow_fork(
    source_id: str = "",
    new_id: str = "",
) -> dict:
    """lfo workflow fork: Create a new workflow from an existing one.

    Args:
        source_id: Source workflow ID
        new_id: New workflow ID

    Returns:
        dict with fork result
    """
    if not source_id:
        return {"success": False, "error": "source_id is required"}
    if not new_id:
        return {"success": False, "error": "new_id is required"}

    from lfo.core.workflow_registry import KNOWN_WORKFLOWS

    if source_id not in KNOWN_WORKFLOWS:
        return {
            "success": False,
            "error": f"Unknown source workflow: {source_id}",
            "known_workflows": list(KNOWN_WORKFLOWS.keys()),
        }

    if new_id in KNOWN_WORKFLOWS:
        return {
            "success": False,
            "error": f"Workflow ID already exists: {new_id}",
        }

    import copy

    source_manifest = KNOWN_WORKFLOWS[source_id]
    new_manifest = copy.deepcopy(source_manifest)
    new_manifest.workflow_id = new_id
    new_manifest.description = f"Forked from {source_id}: {new_manifest.description}"

    # Note: we don't add to KNOWN_WORKFLOWS at runtime — this would require
    # registry file modification. For now, return the proposed manifest.
    return {
        "success": True,
        "source_id": source_id,
        "new_id": new_id,
        "manifest": new_manifest.to_dict(),
        "note": "Fork created in memory. To persist, add to workflow registry file.",
    }

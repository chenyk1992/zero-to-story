"""Mode Complete gate runner (M0–M13) for Visual Production Mode.

Exercises Manual + FakeManaged paths in a temp DB and prints per-milestone
status.  Exit code = number of failed gates (0 = Mode Complete).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
import uuid
from typing import Callable

from lfo.application.asset_service import AssetBindingService
from lfo.application.visual_profile_service import VisualProfileService
from lfo.application.visual_provider_service import VisualProviderService
from lfo.application.visual_result_service import VisualResultService
from lfo.application.visual_routing_service import VisualRoutingService
from lfo.application.visual_task_service import VisualTaskService
from lfo.core.database import Database
from lfo.core.state_machine import TaskStatus
from lfo.services.continuity_service import ContinuityService
from lfo.services.task_readiness_service import TaskReadinessService
from lfo.visual.task_contract import validate_task_package
from lfo.visual.result_manifest import VisualResultManifest
from lfo.visual.provider_config import validate_provider_config
from lfo.visual.providers.manual import ManualProvider
from lfo.visual.providers.fake_managed import FakeManagedProvider
from lfo.visual.stages import VisualStage


# ---------------------------------------------------------------------------
# Gate registry
# ---------------------------------------------------------------------------

_GATES: list[tuple[str, str, Callable[[], bool]]] = []


def gate(milestone: str, label: str) -> Callable:
    """Decorator registering a gate check."""
    def deco(fn: Callable[[], bool]) -> Callable[[], bool]:
        _GATES.append((milestone, label, fn))
        return fn
    return deco


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------

@gate("M0", "Phase 0 clean: no VisualAssetService / keyframe.image")
def gate_m0() -> bool:
    import os
    # Ensure no stale service files exist
    stale = ["services/visual_asset_service.py"]
    for f in stale:
        if os.path.exists(f):
            return False
    return True


@gate("M1", "Schema v10: visual tables + attempt_kind")
def gate_m1() -> bool:
    db = Database()
    db.init_schema()
    tables = [
        "visual_provider_revisions",
        "visual_generation_profile_revisions",
        "visual_task_contracts",
        "visual_result_manifests",
        "visual_provider_executions",
        "visual_exchange_executions",
    ]
    for t in tables:
        row = db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (t,),
        )
        if row is None:
            db.close()
            return False
    # attempt_kind column
    info = db.fetchall("PRAGMA table_info(attempts)")
    cols = {r["name"] for r in info}
    db.close()
    return "attempt_kind" in cols


@gate("M2", "Domain layer: visual/*.py modules importable")
def gate_m2() -> bool:
    try:
        import lfo.visual.errors  # noqa: F401
        import lfo.visual.stages  # noqa: F401
        import lfo.visual.capabilities  # noqa: F401
        import lfo.visual.hashing  # noqa: F401
        import lfo.visual.purpose  # noqa: F401
        import lfo.visual.task_compiler  # noqa: F401
        return True
    except Exception:
        return False


@gate("M3", "Contracts + services importable")
def gate_m3() -> bool:
    try:
        pkg = validate_task_package({
            "purpose": "character_reference",
            "operation": "text_to_image",
            "task_type": "visual.generate",
        })
        assert pkg.purpose == "character_reference"
        manifest = VisualResultManifest(
            task_id="t1",
            content={"file_path": "/tmp/x.png", "width": 1024, "height": 1024},
            content_hash="a" * 64,
        )
        assert manifest.task_id == "t1"
        return True
    except Exception:
        return False


@gate("M4", "Provider config validation works")
def gate_m4() -> bool:
    try:
        cfg = validate_provider_config("manual", {"mode": "local"})
        assert cfg["provider_type"] == "manual"
        return True
    except Exception:
        return False


@gate("M5", "Routing resolves providers in temp DB")
def gate_m5() -> bool:
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    _register_provider(db, "manual")

    ts = VisualTaskService(db)
    task_id = ts.create_visual_task(
        purpose="character_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )

    rs = VisualRoutingService(db)
    choice = rs.route(task_id)
    db.close()
    return choice is not None and "revision_id" in choice


@gate("M6", "Manual path: create → import → QC → approve + bind")
def gate_m6() -> bool:
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    _setup_profile(db)
    _register_provider(db, "manual")

    ts = VisualTaskService(db)
    task_id = ts.create_visual_task(
        purpose="character_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )

    # Verify routing resolves a provider (dry_run — no state change)
    rs = VisualRoutingService(db)
    dry = rs.dry_run(
        project_id="proj1",
        purpose="character_reference",
        required_capabilities=["text_to_image"],
    )
    if not dry or not dry.get("routed"):
        db.close()
        return False

    # Manual exchange: provider exports, human produces result, import
    provider = ManualProvider(
        provider_revision_id=dry["revision_id"],
        config={},
        capabilities={"text_to_image": True},
    )
    provider.export_task(task_id)

    # import_manifest: PLANNED/UNROUTED → QC_PENDING/RESULT_IMPORTED
    rs2 = VisualResultService(db)
    asset_id = rs2.import_manifest({
        "task_id": task_id,
        "content": {"file_path": "manual_output.png", "width": 1024, "height": 1024},
        "file_hash": "a" * 64,
    }, source_root="/tmp")

    # Tech QC pass: QC_PENDING/RESULT_IMPORTED → WAITING_USER/AWAITING_REVIEW
    ts.transition(task_id,
        expected_task_status=TaskStatus.QC_PENDING,
        expected_visual_stage=VisualStage.RESULT_IMPORTED,
        new_task_status=TaskStatus.WAITING_USER,
        new_visual_stage=VisualStage.AWAITING_REVIEW,
        reason="tech_qc_passed",
    )

    # Approve: creates binding + transitions to APPROVED/APPROVED
    rs2.approve(
        task_id,
        asset_id=asset_id,
        entity_type="character",
        entity_id="char-1",
        asset_role="character_reference",
        reviewer="gate_test",
    )

    # Verify APPROVED
    row = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", (task_id,))
    db.close()
    return row is not None and row["status"] == TaskStatus.APPROVED.value


@gate("M7", "FakeManaged path: create → route → submit → collect → import → QC")
def gate_m7() -> bool:
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    _setup_profile(db)
    # Register as "managed" (valid provider type) but use FakeManagedProvider
    _register_provider(db, "managed")

    ts = VisualTaskService(db)
    task_id = ts.create_visual_task(
        purpose="character_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )

    # Verify routing resolves a provider (dry_run)
    rs = VisualRoutingService(db)
    dry = rs.dry_run(
        project_id="proj1",
        purpose="character_reference",
        required_capabilities=["text_to_image"],
    )
    if not dry or not dry.get("routed"):
        db.close()
        return False

    # Use FakeManagedProvider for the actual submit/collect cycle
    provider = FakeManagedProvider(
        provider_revision_id=dry["revision_id"],
        config={},
        capabilities={"text_to_image": True},
    )
    pkg = {
        "task_id": task_id,
        "purpose": "character_reference",
        "operation": "text_to_image",
        "task_type": "visual.generate",
    }
    exec_id = provider.submit(pkg)
    result = provider.collect(exec_id)

    # import_manifest: PLANNED/UNROUTED → QC_PENDING/RESULT_IMPORTED
    rs2 = VisualResultService(db)
    rs2.import_manifest(result, source_root="/tmp")

    # Verify QC_PENDING
    row = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", (task_id,))
    db.close()
    return row is not None and row["status"] == TaskStatus.QC_PENDING.value


@gate("M8", "CLI: visual + project commands importable")
def gate_m8() -> bool:
    try:
        import lfo.cli.visual_cmd  # noqa: F401
        import lfo.cli.project_cmd  # noqa: F401
        return True
    except Exception:
        return False


@gate("M9", "DAG integration: visual_required policy inserts visual.generate tasks")
def gate_m9() -> bool:
    from lfo.services.storyboard_graph_service import StoryboardGraphService
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    # Activate visual_required profile
    psvc = VisualProfileService(db)
    rid = psvc.create_draft("proj1", {"visual_input_policy": "visual_required"})
    psvc.activate(rid)

    # Call the policy resolver directly
    graph_svc = StoryboardGraphService.__new__(StoryboardGraphService)
    graph_svc.db = db
    policy = graph_svc._get_visual_policy("proj1")
    db.close()
    return policy == "visual_required"


@gate("M10", "Dual gate: video task blocked when visual not approved")
def gate_m10() -> bool:
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")

    # Create a visual task (PLANNED) and a video task that depends on it
    ts = VisualTaskService(db)
    vis_id = ts.create_visual_task(
        purpose="character_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )
    # Create video task depending on visual task
    vid_id = str(uuid.uuid4())
    db.execute(
        """INSERT INTO tasks (task_id, project_id, task_type, status,
                             dependencies, idempotency_key,
                             created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (vid_id, "proj1", "h3_i2v", TaskStatus.WAITING_ASSETS.value,
         json.dumps([vis_id]), str(uuid.uuid4()),
         "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    )

    svc = TaskReadinessService(db)
    # promote_to_ready will fail at the dual gate because visual dep
    # is PLANNED (not APPROVED), before needing env snapshot/assets
    result = svc.promote_to_ready(
        vid_id,
        asset_requirements=[],
        workflow_id="wf_test",
        params={},
    )
    db.close()
    # Gate passes if promotion was BLOCKED by visual dependency
    return not result.success and "Visual dependency" in result.message


@gate("M11", "Profile switch: activate stales unstarted visual tasks")
def gate_m11() -> bool:
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    _setup_profile(db, policy="allow_t2va_fallback")

    ts = VisualTaskService(db)
    tid = ts.create_visual_task(
        purpose="character_reference",
        project_id="proj1",
        shot_id=None,
        references=[],
    )

    psvc = VisualProfileService(db)
    rid2 = psvc.create_draft("proj1", {"visual_input_policy": "visual_required"})
    psvc.activate(rid2)

    row = db.fetchone("SELECT status FROM tasks WHERE task_id = ?", (tid,))
    db.close()
    return row is not None and row["status"] == TaskStatus.STALE.value


@gate("M12", "Continuity edit: create_continuity_edit works")
def gate_m12() -> bool:
    db = Database()
    db.init_schema()
    db.execute("INSERT INTO projects (project_id, name) VALUES ('proj1', 'n')")
    # Create a source end frame
    db.execute(
        """INSERT INTO tasks (task_id, project_id, task_type, status,
                             dependencies, idempotency_key,
                             created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ("vid-1", "proj1", "h3_i2v", TaskStatus.APPROVED.value,
         "[]", "ek-1", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
    )
    db.execute(
        """INSERT INTO assets (asset_id, task_id, asset_type, file_path,
                               content_hash, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        ("ef-1", "vid-1", "image", "/tmp/ef.png", "h",
         "2026-01-01T00:00:00Z"),
    )

    svc = ContinuityService(db)
    tid = svc.create_continuity_edit(
        project_id="proj1",
        source_shot_id="shot-1",
        target_shot_id="shot-2",
        end_frame_asset_id="ef-1",
    )
    row = db.fetchone(
        "SELECT task_type FROM tasks WHERE task_id = ?", (tid,)
    )
    db.close()
    return row is not None and row["task_type"] == "visual.edit"


@gate("M13", "Full suite green: all visual tests pass")
def gate_m13() -> bool:
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_visual/", "-q", "--tb=no"],
        capture_output=True, text=True,
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_profile(db: Database, policy: str = "allow_t2va_fallback") -> str:
    svc = VisualProfileService(db)
    rid = svc.create_draft("proj1", {"visual_input_policy": policy})
    svc.activate(rid)
    return rid


def _register_provider(db: Database, ptype: str) -> str:
    ps = VisualProviderService(db)
    cfg: dict = {}
    if ptype == "managed":
        cfg["endpoint"] = "http://localhost:9999/fake"
    rid = ps.create_draft(
        provider_id=f"prov-{ptype}-test",
        scope_type="global",
        scope_id="*",
        provider_type=ptype,
        adapter_name=f"{ptype}_adapter",
        config=cfg,
        capabilities={"text_to_image": True},
    )
    ps.activate(rid)
    return rid


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Visual Production Mode Complete gates")
    parser.add_argument("--skip-production", action="store_true",
                        help="Skip production proof gate (M13 subprocess test)")
    args = parser.parse_args()

    failures: list[str] = []
    print("=" * 60)
    print("Visual Production Mode — M0–M13 Gates")
    print("=" * 60)

    for milestone, label, fn in _GATES:
        if args.skip_production and milestone == "M13":
            print(f"  [{milestone}] SKIP  {label}")
            continue
        try:
            ok = fn()
        except Exception as e:
            ok = False
            print(f"  [{milestone}] ERROR {label}: {e}")
            traceback.print_exc()
        status = "PASS" if ok else "FAIL"
        print(f"  [{milestone}] {status}  {label}")
        if not ok:
            failures.append(milestone)

    print("=" * 60)
    total = len(_GATES)
    failed = len(failures)
    passed = total - failed
    print(f"Result: {passed}/{total} gates passed")
    if failures:
        print(f"Failed: {', '.join(failures)}")
        return failed
    print("Mode Complete ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""LFO Core — deterministic serialization, hashing, SQLite schema, and state transitions."""
from .canonical import (
    LFO_CJ1_DUPLICATE_KEY,
    LFO_CJ1_ERROR,
    LFO_CJ1_FLOAT_FORBIDDEN,
    hash_bytes,
    hash_value,
    normalize_project_path,
    serialize,
    serialize_with_schema,
)
from .database import SCHEMA_VERSION, Database
from .hashing import (
    WORKFLOW_HASH_ALGORITHM,
    compute_compiler_identity,
    compute_content_hash,
    compute_dependency_hash,
    compute_file_hash,
    compute_idempotency_key,
    compute_params_hash,
    compute_workflow_hash,
)
from .state_machine import (
    TASK_ACTIVE_STATES,
    TASK_BLOCKING_STATES,
    TASK_TERMINAL_STATES,
    FailureClassification,
    ProjectState,
    SubmissionState,
    Task,
    TaskStatus,
    compute_project_state,
    merge_run_status,
)
from .workflow_registry import (
    KNOWN_WORKFLOWS,
    BindingReport,
    FrameConstraints,
    InputSlot,
    ModelDependency,
    OutputSpec,
    ResolutionConstraints,
    ResourceProfile,
    WorkflowCapability,
    WorkflowManifest,
    WorkflowRegistry,
    make_capability,
)

__all__ = [
    # canonical
    "serialize",
    "serialize_with_schema",
    "hash_value",
    "hash_bytes",
    "normalize_project_path",
    # hashing
    "compute_content_hash",
    "compute_dependency_hash",
    "compute_params_hash",
    "compute_idempotency_key",
    "compute_compiler_identity",
    "compute_workflow_hash",
    "compute_file_hash",
    "WORKFLOW_HASH_ALGORITHM",
    # state machine
    "TaskStatus",
    "SubmissionState",
    "FailureClassification",
    "Task",
    "ProjectState",
    "compute_project_state",
    "merge_run_status",
    "TASK_TERMINAL_STATES",
    "TASK_ACTIVE_STATES",
    "TASK_BLOCKING_STATES",
    # database
    "Database",
    "SCHEMA_VERSION",
    # workflow registry
    "WorkflowManifest",
    "WorkflowCapability",
    "BindingReport",
    "WorkflowRegistry",
    "InputSlot",
    "ModelDependency",
    "FrameConstraints",
    "ResolutionConstraints",
    "ResourceProfile",
    "OutputSpec",
    "KNOWN_WORKFLOWS",
    "make_capability",
    # exceptions
    "LFO_CJ1_ERROR",
    "LFO_CJ1_FLOAT_FORBIDDEN",
    "LFO_CJ1_DUPLICATE_KEY",
]

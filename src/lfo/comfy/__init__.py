"""LFO — Local Film Orchestrator.

ComfyUI integration package for AI film production.
"""

from .bindings import Binding, BindingResolver
from .client import ComfyApiClient
from .collect import AssetRecord, CollectResult, ComfyOutputCollector, MediaInfo
from .doctor import CheckResult, ComfyDoctor, DoctorReport
from .exceptions import (
    BindingAmbiguousError,
    BindingNotFoundError,
    ComfyInstanceMismatchError,
    ComfyUnreachableError,
    LfoComfyError,
    OutputCardinalityError,
    OutputNotFoundError,
    OutputUnstableError,
    WorkflowFormatError,
)
from .monitor import ComfyMonitor
from .recovery import RecoveryManager, RecoveryResult
from .runtime import ComfyRuntimeManager, InstanceFingerprint, MachineProfile
from .submit import PromptSubmitter, SubmitResult
from .workflow import WorkflowLoader

__all__ = [
    # client
    "ComfyApiClient",
    # runtime
    "ComfyRuntimeManager",
    "MachineProfile",
    "InstanceFingerprint",
    # doctor
    "ComfyDoctor",
    "DoctorReport",
    "CheckResult",
    # workflow
    "WorkflowLoader",
    # bindings
    "Binding",
    "BindingResolver",
    # submit
    "PromptSubmitter",
    "SubmitResult",
    # monitor
    "ComfyMonitor",
    # collect
    "ComfyOutputCollector",
    "MediaInfo",
    "AssetRecord",
    "CollectResult",
    # recovery
    "RecoveryManager",
    "RecoveryResult",
    # exceptions
    "LfoComfyError",
    "ComfyUnreachableError",
    "ComfyInstanceMismatchError",
    "WorkflowFormatError",
    "BindingNotFoundError",
    "BindingAmbiguousError",
    "OutputNotFoundError",
    "OutputCardinalityError",
    "OutputUnstableError",
]

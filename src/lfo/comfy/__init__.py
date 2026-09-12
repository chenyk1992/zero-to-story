"""LFO — Local Film Orchestrator.

ComfyUI integration package for AI film production.
"""

from .bindings import Binding, BindingResolver
from .cli import ComfyCliOutput, ComfyCliRunner, ComfyCliRunResult
from .client import ComfyApiClient
from .collect import AssetRecord, CollectResult, ComfyOutputCollector, MediaInfo
from .doctor import CheckResult, ComfyDoctor, DoctorReport
from .exceptions import (
    BindingAmbiguousError,
    BindingNotFoundError,
    ComfyCliTimeoutError,
    ComfyInstanceMismatchError,
    ComfyUnreachableError,
    LfoComfyError,
    OutputCardinalityError,
    OutputNotFoundError,
    OutputUnstableError,
    WorkflowFormatError,
)
from .runtime import ComfyRuntimeManager, InstanceFingerprint, MachineProfile
from .workflow import WorkflowLoader

__all__ = [
    # client
    "ComfyApiClient",
    "ComfyCliRunner",
    "ComfyCliRunResult",
    "ComfyCliOutput",
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
    # collect
    "ComfyOutputCollector",
    "MediaInfo",
    "AssetRecord",
    "CollectResult",
    # exceptions
    "LfoComfyError",
    "ComfyCliTimeoutError",
    "ComfyUnreachableError",
    "ComfyInstanceMismatchError",
    "WorkflowFormatError",
    "BindingNotFoundError",
    "BindingAmbiguousError",
    "OutputNotFoundError",
    "OutputCardinalityError",
    "OutputUnstableError",
]

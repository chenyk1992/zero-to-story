"""Unified Check Framework — CheckResult, CheckContext, CheckRunner."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum


class CheckSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"


class CheckStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class CheckResult:
    """Immutable check result."""

    check_id: str  # stable identifier, e.g. "comfyui.reachable"
    severity: CheckSeverity
    status: CheckStatus
    message: str
    details: dict = field(default_factory=dict)
    remediation: str | None = None


@dataclass
class CheckContext:
    """Context passed to every check."""

    machine_profile: object | None = None
    env_snapshot: dict | None = None
    required_workflow_ids: set[str] = field(default_factory=set)
    required_model_ids: set[str] = field(default_factory=set)
    required_tools: set[str] = field(default_factory=set)
    required_storage_bytes: int = 0


# Type alias for check functions
CheckFn = Callable[[CheckContext], CheckResult]


def check(
    check_id: str,
    severity: CheckSeverity = CheckSeverity.WARNING,
    description: str = "",
):
    """Decorator to register a check function.

    Attaches metadata (_check_id, _severity, _description) to the function.
    """

    def decorator(fn: CheckFn) -> CheckFn:
        fn._check_id = check_id  # type: ignore[attr-defined]
        fn._severity = severity  # type: ignore[attr-defined]
        fn._description = description  # type: ignore[attr-defined]
        return fn

    return decorator


class CheckRunner:
    """Run checks and collect results."""

    def __init__(self) -> None:
        self._checks: list[CheckFn] = []

    def register(self, fn: CheckFn) -> None:
        """Register a check function."""
        self._checks.append(fn)

    def run(self, context: CheckContext) -> list[CheckResult]:
        """Run all registered checks."""
        results: list[CheckResult] = []
        for fn in self._checks:
            try:
                result = fn(context)
                results.append(result)
            except Exception as exc:
                # Convert exception to a failed check result
                check_id = getattr(fn, "_check_id", fn.__name__)
                severity = getattr(fn, "_severity", CheckSeverity.WARNING)
                results.append(
                    CheckResult(
                        check_id=check_id,
                        severity=severity,
                        status=CheckStatus.FAILED,
                        message=f"Check raised exception: {exc}",
                    )
                )
        return results

    def run_subset(
        self, context: CheckContext, check_ids: set[str]
    ) -> list[CheckResult]:
        """Run only specified checks (for Preflight)."""
        results: list[CheckResult] = []
        for fn in self._checks:
            fn_id = getattr(fn, "_check_id", "")
            if fn_id in check_ids:
                try:
                    result = fn(context)
                    results.append(result)
                except Exception as exc:
                    severity = getattr(fn, "_severity", CheckSeverity.WARNING)
                    results.append(
                        CheckResult(
                            check_id=fn_id,
                            severity=severity,
                            status=CheckStatus.FAILED,
                            message=f"Check raised exception: {exc}",
                        )
                    )
        return results

    @property
    def registered_check_ids(self) -> list[str]:
        """List all registered check IDs."""
        return [getattr(fn, "_check_id", fn.__name__) for fn in self._checks]

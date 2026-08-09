"""Validation errors for VideoExecutionPackage."""
from __future__ import annotations

from typing import Any


class ValidationError:
    """Structured validation error with JSON Pointer path."""

    def __init__(self, path: str, message: str, code: str, value: Any = None) -> None:
        self.path = path
        self.message = message
        self.code = code
        self.value = value

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "path": self.path,
            "message": self.message,
            "code": self.code,
        }
        if self.value is not None:
            d["value"] = self.value
        return d

    def __repr__(self) -> str:
        return f"ValidationError({self.path!r}, {self.message!r}, {self.code!r})"


class ValidationResult:
    """Collects validation errors."""

    def __init__(self) -> None:
        self._errors: list[ValidationError] = []

    @property
    def ok(self) -> bool:
        return not self._errors

    def add(self, path: str, message: str, code: str, value: Any = None) -> None:
        self._errors.append(ValidationError(path, message, code, value))

    def extend(self, other: ValidationResult) -> None:
        self._errors.extend(other._errors)

    def errors(self) -> list[ValidationError]:
        return list(self._errors)

    def to_dict(self) -> list[dict[str, Any]]:
        return [e.to_dict() for e in self._errors]

    def __repr__(self) -> str:
        return f"ValidationResult(errors={len(self._errors)})"

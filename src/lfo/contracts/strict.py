"""Small helpers for strict contract-object parsing."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class UnknownFieldError(ValueError):
    """Raised when a contract object contains a field outside its allowlist."""

    def __init__(self, path: str, fields: Iterable[Any]) -> None:
        self.fields = tuple(str(field) for field in fields)
        self.path = f"{path}.{self.fields[0]}" if self.fields else path
        if len(self.fields) == 1:
            message = f"{self.path}: unknown field"
        else:
            message = f"{self.path}: unknown fields {list(self.fields)!r}"
        super().__init__(message)


def ensure_allowed_fields(
    data: dict[str, Any],
    path: str,
    allowed: Iterable[str],
) -> None:
    """Reject keys not present in the object's explicit field allowlist.

    The first unknown key is exposed as ``UnknownFieldError.path`` so callers
    can preserve a useful field path in structured validation errors.  The
    complete unknown-key set remains in the exception text for diagnostics.
    """
    allowed_fields = set(allowed)
    unknown = sorted((key for key in data if key not in allowed_fields), key=str)
    if not unknown:
        return
    raise UnknownFieldError(path, unknown)

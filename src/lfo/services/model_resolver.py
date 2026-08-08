"""Model resolver — logical model_id to physical file resolution."""
from __future__ import annotations

import hashlib
import pathlib
from dataclasses import dataclass

from lfo.config.machine_profile import MachineProfile
from lfo.config.model_registry import get_model_declaration


@dataclass
class ResolvedModel:
    """A model resolved to its physical location."""

    model_id: str
    resolved_path: pathlib.Path | None
    verification_mode: str  # 'quick' | 'strict'
    size_bytes: int = 0
    mtime_ns: int = 0
    sha256: str | None = None
    found: bool = False


class ModelResolver:
    """Resolve logical model IDs to physical files."""

    def __init__(self, machine_profile: MachineProfile) -> None:
        self.profile = machine_profile

    def resolve(self, model_id: str) -> ResolvedModel:
        """Find model file on this machine (quick mode).

        Quick mode checks file existence and size only (no hash).
        """
        decl = get_model_declaration(model_id)
        if decl is None:
            return ResolvedModel(
                model_id=model_id,
                resolved_path=None,
                verification_mode="quick",
                found=False,
            )

        # Search in common model directories
        search_dirs = self._get_model_search_dirs()

        for directory in search_dirs:
            if not directory.exists():
                continue
            for filename in decl.candidate_filenames:
                candidate = directory / filename
                if candidate.exists():
                    stat = candidate.stat()
                    return ResolvedModel(
                        model_id=model_id,
                        resolved_path=candidate,
                        verification_mode="quick",
                        size_bytes=stat.st_size,
                        mtime_ns=stat.st_mtime_ns,
                        found=True,
                    )

        return ResolvedModel(
            model_id=model_id,
            resolved_path=None,
            verification_mode="quick",
            found=False,
        )

    def strict_verify(self, model_id: str) -> ResolvedModel:
        """Full SHA-256 verification (slow, for migration/publish)."""
        resolved = self.resolve(model_id)
        if not resolved.found or resolved.resolved_path is None:
            return resolved

        # Compute SHA-256
        sha256 = self._compute_file_hash(resolved.resolved_path)
        return ResolvedModel(
            model_id=resolved.model_id,
            resolved_path=resolved.resolved_path,
            verification_mode="strict",
            size_bytes=resolved.size_bytes,
            mtime_ns=resolved.mtime_ns,
            sha256=sha256,
            found=True,
        )

    def resolve_many(self, model_ids: set[str]) -> dict[str, ResolvedModel]:
        """Resolve multiple models at once."""
        return {mid: self.resolve(mid) for mid in model_ids}

    def _get_model_search_dirs(self) -> list[pathlib.Path]:
        """Get directories to search for models."""
        dirs = []

        # From machine profile
        comfy_root = self.profile.comfyui.root
        if comfy_root:
            root = pathlib.Path(comfy_root)
            dirs.append(root / "models" / "unet")
            dirs.append(root / "models" / "vae")
            dirs.append(root / "models" / "clip")
            dirs.append(root / "models" / "llm")
            dirs.append(root / "models")  # fallback

        return [d for d in dirs if d is not None]

    @staticmethod
    def _compute_file_hash(path: pathlib.Path) -> str:
        """Compute SHA-256 hash of a file."""
        data = path.read_bytes()
        return hashlib.sha256(data).hexdigest()

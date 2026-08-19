"""ComfyUI HTTP API client."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from .exceptions import ComfyUnreachableError


class ComfyApiClient:
    """HTTP client for the ComfyUI server API."""

    def __init__(self, base_url: str = "http://127.0.0.1:8188"):
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(
        self,
        method: str,
        path: str,
        *,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> requests.Response:
        try:
            resp = self._session.request(
                method, self._url(path), timeout=timeout, **kwargs
            )
            resp.raise_for_status()
            return resp
        except requests.ConnectionError as exc:
            raise ComfyUnreachableError(
                f"Cannot connect to ComfyUI at {self.base_url}: {exc}"
            ) from exc
        except requests.Timeout as exc:
            raise ComfyUnreachableError(
                f"Request to {self.base_url}{path} timed out"
            ) from exc

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def get_system_stats(self) -> dict:
        """Return system statistics (GPU, RAM, Python version, etc.)."""
        resp = self._request("GET", "/system_stats", timeout=10)
        return resp.json()

    def get_features(self) -> dict:
        """Return supported server features."""
        resp = self._request("GET", "/features", timeout=10)
        return resp.json()

    def get_object_info(self, node_class: str | None = None) -> dict:
        """Return node class definitions, optionally filtered to one class."""
        path = "/object_info"
        if node_class:
            path = f"/object_info/{node_class}"
        resp = self._request("GET", path, timeout=15)
        return resp.json()

    def get_queue(self) -> dict:
        """Return current running and pending queue."""
        resp = self._request("GET", "/queue", timeout=10)
        return resp.json()

    def submit_prompt(self, workflow: dict, client_id: str) -> dict:
        """Submit a prompt (workflow) for execution.

        Returns dict with at least ``prompt_id``.
        """
        payload = {"prompt": workflow, "client_id": client_id}
        resp = self._request("POST", "/prompt", json=payload, timeout=30)
        return resp.json()

    def get_history(self, prompt_id: str) -> dict:
        """Return execution history for a given prompt."""
        # H3 can keep ComfyUI's request thread busy while a long sample is
        # running; do not turn a slow history response into a false failure.
        resp = self._request("GET", f"/history/{prompt_id}", timeout=60)
        return resp.json()

    def interrupt(self) -> None:
        """Interrupt the currently executing prompt."""
        self._request("POST", "/interrupt", timeout=10)

    def free_memory(self, *, unload_models: bool = True, free_memory: bool = True) -> None:
        """Ask ComfyUI to release cached models and GPU memory."""
        self._request(
            "POST",
            "/free",
            json={"unload_models": unload_models, "free_memory": free_memory},
            timeout=30,
        )

    def upload_file(self, file_path: Path, subfolder: str = "") -> dict:
        """Upload a file to ComfyUI's input directory.

        ComfyUI's historical ``/upload/image`` endpoint accepts generic input
        files; video loaders use that same endpoint.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError("Input file is unavailable")

        with path.open("rb") as fh:
            files = {"image": (path.name, fh, "application/octet-stream")}
            data = {"subfolder": subfolder} if subfolder else {}
            resp = self._request(
                "POST", "/upload/image", files=files, data=data, timeout=60
            )
        return resp.json()

    def upload_image(self, image_path: Path, subfolder: str = "") -> dict:
        """Upload an image file to the ComfyUI input directory."""
        return self.upload_file(image_path, subfolder)

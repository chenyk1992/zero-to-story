from __future__ import annotations

from comfy_api.latest import ComfyExtension

from .bounded_seedvr2 import CanvasSeedVR2BoundedUpscale


class CanvasSeedVR2BoundedExtension(ComfyExtension):
    async def get_node_list(self):
        return [CanvasSeedVR2BoundedUpscale]


async def comfy_entrypoint() -> CanvasSeedVR2BoundedExtension:
    return CanvasSeedVR2BoundedExtension()

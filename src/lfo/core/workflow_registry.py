"""LFO Workflow Registry — manifest, capability, binding, compatibility.

For each registered workflow the registry maintains:
- manifest.json  — identity, hash, constraints, resource profile
- capability.json — what the workflow can/cannot do
- binding_report.json — resolved node bindings for value injection

Registry file: ``.lfo/registry.json`` (project-level) or ``%APPDATA%/lfo/registry.json`` (global).
"""
from __future__ import annotations

import copy
import json
import pathlib
from dataclasses import asdict, dataclass, field

from .hashing import WORKFLOW_HASH_ALGORITHM, compute_workflow_hash

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ModelDependency:
    """A model file required by the workflow."""
    role: str  # 'unet' | 'clip' | 'vae' | 'audio_vae'
    filename: str
    required: bool = True


@dataclass
class InputSlot:
    """A logical input slot that LFO can bind to."""
    binding_id: str          # stable identifier, e.g. "prompt", "first_frame"
    selector_title: str      # _meta.title of the target node
    selector_class_type: str # class_type of the target node
    input_name: str          # input slot name on the target node
    value_type: str          # 'string' | 'int' | 'float' | 'image' | 'select'
    description: str = ""
    optional: bool = False


@dataclass
class OutputSpec:
    """Expected output specification."""
    asset_type: str          # 'video' | 'image' | 'audio'
    count: int = 1           # expected number of output files
    format: str = "mp4"      # file format


@dataclass
class FrameConstraints:
    """Frame grid constraints (H3-specific)."""
    step: int = 17
    min_frames: int = 5
    max_frames: int = 3600
    default_frames: int = 124  # 5s @ 24fps
    fps: int = 24

    @staticmethod
    def align_frame_count(n: int) -> int:
        """Align a frame count to the H3 grid (n % 17 == 5).

        Examples:
            123 → 124, 124 → 124, 125 → 141,
            191 → 192, 192 → 192, 193 → 209
        """
        while n % 17 != 5:
            n += 1
        return n


@dataclass
class ResolutionConstraints:
    """Resolution constraints."""
    min_width: int = 256
    max_width: int = 4096
    min_height: int = 256
    max_height: int = 4096
    width_multiple: int = 32
    height_multiple: int = 32
    default_width: int = 864
    default_height: int = 480


@dataclass
class ResourceProfile:
    """Measured resource requirements."""
    cold_start_sec: float = 360.0
    hot_start_sec: float = 360.0
    peak_vram_mb: float = 0.0


@dataclass
class WorkflowManifest:
    """Complete workflow manifest."""
    workflow_id: str
    version: str
    family: str              # 'h3_fl2va' | 'h3_ref2va'
    workflow_mode: str       # 't2va' | 'i2v' | 'first_last' | 'r2v'
    description: str
    source_file: str         # original workflow file path
    workflow_hash: str       # LFO-WFJ1 hash of the API-format workflow
    workflow_hash_algorithm: str = WORKFLOW_HASH_ALGORITHM  # "lfo-wfj1-sha256-v1"

    # Constraints
    frame_constraints: FrameConstraints = field(default_factory=FrameConstraints)
    resolution_constraints: ResolutionConstraints = field(default_factory=ResolutionConstraints)

    # Input / output
    input_slots: list[InputSlot] = field(default_factory=list)
    output_spec: OutputSpec = field(default_factory=lambda: OutputSpec(asset_type="video"))

    # Models
    model_dependencies: list[ModelDependency] = field(default_factory=list)

    # Resources
    resource_profile: ResourceProfile = field(default_factory=ResourceProfile)

    # Metadata
    generates_audio: bool = True
    tags: list[str] = field(default_factory=list)

    # Binding & compatibility
    binding_policy: str = "strict_title_and_class"  # 'strict_title_and_class' | 'migration_fallback'
    production_ready: bool = False  # True only when all checks pass with no warnings

    # Validation levels (populated by validate_workflow)
    static_valid: bool = False
    runtime_compatible: bool = False
    smoke_tested: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> WorkflowManifest:
        # Reconstruct nested dataclasses
        frame = FrameConstraints(**data.pop("frame_constraints", {}))
        resolution = ResolutionConstraints(**data.pop("resolution_constraints", {}))
        inputs = [InputSlot(**s) for s in data.pop("input_slots", [])]
        output = OutputSpec(**data.pop("output_spec", {}))
        models = [ModelDependency(**m) for m in data.pop("model_dependencies", [])]
        resource = ResourceProfile(**data.pop("resource_profile", {}))
        return cls(
            frame_constraints=frame,
            resolution_constraints=resolution,
            input_slots=inputs,
            output_spec=output,
            model_dependencies=models,
            resource_profile=resource,
            **data,
        )


@dataclass
class WorkflowCapability:
    """What a workflow can and cannot do."""
    workflow_id: str
    modes: list[str] = field(default_factory=list)  # 't2va' | 'i2v' | 'first_last' | 'r2v'

    # What it accepts
    accepts_prompt: bool = True
    accepts_image: bool = False
    accepts_reference_images: bool = False
    accepts_first_frame: bool = False
    accepts_last_frame: bool = False

    # What it produces
    produces_video: bool = True
    produces_audio: bool = True

    # Limitations
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BindingReport:
    """Result of resolving bindings against a concrete workflow."""
    workflow_id: str
    bindings: list[dict] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)  # migration fallback notices
    status: str = "ok"  # 'ok' | 'partial' | 'failed'
    mode: str = "strict"  # 'strict' | 'migration'

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


# ---------------------------------------------------------------------------
# H3 workflow definitions
# ---------------------------------------------------------------------------

H3_T2V_MANIFEST = WorkflowManifest(
    workflow_id="h3_standard_t2v",
    version="3.0.0",
    family="h3_fl2va",
    workflow_mode="t2va",
    description="H3 Text-to-Video-Audio (v3): expanded pipeline with MiniMaxH3ImageToVideo + auto-duration math.",
    source_file="h3_standard_t2v.json",
    workflow_hash="",  # computed at registration time
    frame_constraints=FrameConstraints(step=17, min_frames=5, max_frames=3600, default_frames=124, fps=24),
    resolution_constraints=ResolutionConstraints(
        min_width=256, max_width=4096, min_height=256, max_height=4096,
        width_multiple=32, height_multiple=32,
        default_width=864, default_height=480,
    ),
    input_slots=[
        InputSlot(
            binding_id="prompt",
            selector_title="LFO.MainGenerator",
            selector_class_type="MiniMaxH3ImageToVideo",
            input_name="prompt",
            value_type="string",
            description="Three-layer H3 prompt (scene/soundscape/music)",
        ),
        InputSlot(
            binding_id="duration",
            selector_title="LFO.Duration",
            selector_class_type="PrimitiveFloat",
            input_name="value",
            value_type="float",
            description="Duration in seconds (auto-converted to frames on 17k+5 grid via ComfyMathExpression)",
        ),
        InputSlot(
            binding_id="filename_prefix",
            selector_title="LFO.SaveVideo",
            selector_class_type="SaveVideo",
            input_name="filename_prefix",
            value_type="string",
            description="Output filename prefix (e.g. 'lfo/proj01/task01/att001/video')",
        ),
    ],
    output_spec=OutputSpec(asset_type="video", count=1, format="mp4"),
    model_dependencies=[
        ModelDependency(role="unet", filename="minimax_h3_fl2va_pruned_int8_convrot.safetensors"),
        ModelDependency(role="clip", filename="qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"),
        ModelDependency(role="vae", filename="minimax_h3_video_vae_fp16.safetensors"),
        ModelDependency(role="audio_vae", filename="minimax_h3_audio_vae_fp32.safetensors"),
    ],
    resource_profile=ResourceProfile(cold_start_sec=360.7, hot_start_sec=360.0, peak_vram_mb=0),
    generates_audio=True,
    tags=["text-to-video", "audio", "fl2va", "auto-duration"],
)

H3_I2V_MANIFEST = WorkflowManifest(
    workflow_id="h3_standard_i2v",
    version="3.0.0",
    family="h3_fl2va",
    workflow_mode="i2v",
    description="H3 Image-to-Video-Audio (v3): expanded pipeline with MiniMaxH3ImageToVideo + first_frame + auto-duration math.",
    source_file="h3_standard_i2v.json",
    workflow_hash="",
    frame_constraints=FrameConstraints(step=17, min_frames=5, max_frames=3600, default_frames=124, fps=24),
    resolution_constraints=ResolutionConstraints(
        min_width=256, max_width=4096, min_height=256, max_height=4096,
        width_multiple=32, height_multiple=32,
        default_width=640, default_height=640,
    ),
    input_slots=[
        InputSlot(
            binding_id="prompt",
            selector_title="LFO.MainGenerator",
            selector_class_type="MiniMaxH3ImageToVideo",
            input_name="prompt",
            value_type="string",
            description="Three-layer H3 prompt (scene/soundscape/music)",
        ),
        InputSlot(
            binding_id="first_frame",
            selector_title="LFO.FirstFrame",
            selector_class_type="LoadImage",
            input_name="image",
            value_type="image",
            description="Input image to animate (first frame of output video)",
        ),
        InputSlot(
            binding_id="duration",
            selector_title="LFO.Duration",
            selector_class_type="PrimitiveFloat",
            input_name="value",
            value_type="float",
            description="Duration in seconds (auto-converted to frames on 17k+5 grid via ComfyMathExpression)",
        ),
        InputSlot(
            binding_id="filename_prefix",
            selector_title="LFO.SaveVideo",
            selector_class_type="SaveVideo",
            input_name="filename_prefix",
            value_type="string",
            description="Output filename prefix",
        ),
    ],
    output_spec=OutputSpec(asset_type="video", count=1, format="mp4"),
    model_dependencies=[
        ModelDependency(role="unet", filename="minimax_h3_fl2va_pruned_int8_convrot.safetensors"),
        ModelDependency(role="clip", filename="qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"),
        ModelDependency(role="vae", filename="minimax_h3_video_vae_fp16.safetensors"),
        ModelDependency(role="audio_vae", filename="minimax_h3_audio_vae_fp32.safetensors"),
    ],
    resource_profile=ResourceProfile(cold_start_sec=360.6, hot_start_sec=360.0, peak_vram_mb=0),
    generates_audio=True,
    tags=["image-to-video", "audio", "fl2va", "auto-duration"],
)

H3_R2V_MANIFEST = WorkflowManifest(
    workflow_id="h3_standard_r2v",
    version="2.0.0",
    family="h3_ref2va",
    workflow_mode="r2v",
    description="H3 Reference-to-Video (v2): adds ComfyMathExpression for auto frame-count calculation on 17k+5 grid.",
    source_file="h3_standard_r2v.json",
    workflow_hash="",
    frame_constraints=FrameConstraints(step=17, min_frames=5, max_frames=3600, default_frames=124, fps=24),
    resolution_constraints=ResolutionConstraints(
        min_width=256, max_width=4096, min_height=256, max_height=4096,
        width_multiple=32, height_multiple=32,
        default_width=864, default_height=480,
    ),
    input_slots=[
        InputSlot(
            binding_id="prompt",
            selector_title="LFO.Prompt",
            selector_class_type="PrimitiveStringMultiline",
            input_name="value",
            value_type="string",
            description="Three-layer H3 prompt with <Picture N> references",
        ),
        InputSlot(
            binding_id="ref_image_0",
            selector_title="LFO.Reference01",
            selector_class_type="LoadImage",
            input_name="image",
            value_type="image",
            description="Reference image 1 (bound to <Picture 1> in prompt)",
        ),
        InputSlot(
            binding_id="ref_image_1",
            selector_title="LFO.Reference02",
            selector_class_type="LoadImage",
            input_name="image",
            value_type="image",
            description="Reference image 2 (bound to <Picture 2> in prompt)",
        ),
        InputSlot(
            binding_id="ref_image_2",
            selector_title="LFO.Reference03",
            selector_class_type="LoadImage",
            input_name="image",
            value_type="image",
            description="Reference image 3 (bound to <Picture 3> in prompt)",
        ),
        InputSlot(
            binding_id="duration",
            selector_title="LFO.Duration",
            selector_class_type="PrimitiveFloat",
            input_name="value",
            value_type="float",
            description="Duration in seconds (auto-converted to frames on 17k+5 grid via ComfyMathExpression)",
        ),
        InputSlot(
            binding_id="filename_prefix",
            selector_title="LFO.SaveVideo",
            selector_class_type="SaveVideo",
            input_name="filename_prefix",
            value_type="string",
            description="Output filename prefix",
        ),
    ],
    output_spec=OutputSpec(asset_type="video", count=1, format="mp4"),
    model_dependencies=[
        ModelDependency(role="unet", filename="minimax_h3_ref2va_pruned_int8_convrot.safetensors"),
        ModelDependency(role="clip", filename="qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"),
        ModelDependency(role="vae", filename="minimax_h3_video_vae_fp16.safetensors"),
        ModelDependency(role="audio_vae", filename="minimax_h3_audio_vae_fp32.safetensors"),
    ],
    resource_profile=ResourceProfile(cold_start_sec=370.6, hot_start_sec=370.0, peak_vram_mb=0),
    generates_audio=True,
    tags=["reference-to-video", "audio", "ref2va", "multi-reference", "auto-duration"],
)

H3_PRESENTER_R2V_MANIFEST = WorkflowManifest(
    workflow_id="h3_presenter_r2v",
    version="3.0.0",
    family="h3_presenter_r2v",
    workflow_mode="r2v",
    description=(
        "H3 virtual-presenter Reference-to-Video-Audio workflow with explicit "
        "materialized image, video and audio reference slots."
    ),
    source_file="h3_presenter_r2v.json",
    workflow_hash="",
    frame_constraints=FrameConstraints(
        step=17, min_frames=5, max_frames=3600, default_frames=124, fps=24
    ),
    resolution_constraints=ResolutionConstraints(
        min_width=256,
        max_width=4096,
        min_height=256,
        max_height=4096,
        width_multiple=32,
        height_multiple=32,
        default_width=864,
        default_height=480,
    ),
    input_slots=[
        InputSlot(
            binding_id="prompt",
            selector_title="LFO.Prompt",
            selector_class_type="PrimitiveStringMultiline",
            input_name="value",
            value_type="string",
            description=(
                "Presenter prompt; materialized ref_image_N, ref_video_N and "
                "ref_audio_N map to Picture, Video and Audio N+1."
            ),
        ),
        InputSlot(
            binding_id="duration",
            selector_title="LFO.Duration",
            selector_class_type="PrimitiveFloat",
            input_name="value",
            value_type="float",
            description="Duration in seconds, converted to the H3 17k+5 frame grid.",
        ),
        InputSlot(
            binding_id="filename_prefix",
            selector_title="LFO.SaveVideo",
            selector_class_type="SaveVideo",
            input_name="filename_prefix",
            value_type="string",
            description="Output filename prefix managed by LFO.",
        ),
    ],
    output_spec=OutputSpec(asset_type="video", count=1, format="mp4"),
    model_dependencies=[
        ModelDependency(role="unet", filename="minimax_h3_ref2va_pruned_int8_convrot.safetensors"),
        ModelDependency(role="clip", filename="qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"),
        ModelDependency(role="vae", filename="minimax_h3_video_vae_fp16.safetensors"),
        ModelDependency(role="audio_vae", filename="minimax_h3_audio_vae_fp32.safetensors"),
    ],
    resource_profile=ResourceProfile(cold_start_sec=370.6, hot_start_sec=370.0, peak_vram_mb=0),
    generates_audio=True,
    tags=["virtual-presenter", "reference-to-video", "audio", "ref2va", "auto-duration"],
)

# Vertical (9:16) workflow manifests for H3

H3_VERTICAL_T2V_MANIFEST = WorkflowManifest(
    workflow_id="h3_vertical_t2v",
    version="1.0.0",
    family="h3_vertical_fl2va",
    workflow_mode="t2va",
    description="H3 Vertical Text-to-Video-Audio (9:16, ~756p): optimized for RTX 5080 16GB with int8 models.",
    source_file="h3_vertical_t2v.json",
    workflow_hash="",
    frame_constraints=FrameConstraints(step=17, min_frames=5, max_frames=3600, default_frames=124, fps=24),
    resolution_constraints=ResolutionConstraints(
        min_width=256, max_width=4096, min_height=256, max_height=4096,
        width_multiple=32, height_multiple=32,
        default_width=448, default_height=800,
    ),
    input_slots=[
        InputSlot(
            binding_id="prompt",
            selector_title="LFO.MainGenerator",
            selector_class_type="MiniMaxH3ImageToVideo",
            input_name="prompt",
            value_type="string",
            description="Three-layer H3 prompt (scene/soundscape/music)",
        ),
        InputSlot(
            binding_id="duration",
            selector_title="LFO.Duration",
            selector_class_type="PrimitiveFloat",
            input_name="value",
            value_type="float",
            description="Duration in seconds",
        ),
        InputSlot(
            binding_id="filename_prefix",
            selector_title="LFO.SaveVideo",
            selector_class_type="SaveVideo",
            input_name="filename_prefix",
            value_type="string",
            description="Output filename prefix",
        ),
    ],
    output_spec=OutputSpec(asset_type="video", count=1, format="mp4"),
    model_dependencies=[
        ModelDependency(role="unet", filename="minimax_h3_fl2va_pruned_int8_convrot.safetensors"),
        ModelDependency(role="clip", filename="qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"),
        ModelDependency(role="vae", filename="minimax_h3_video_vae_fp16.safetensors"),
        ModelDependency(role="audio_vae", filename="minimax_h3_audio_vae_fp32.safetensors"),
    ],
    resource_profile=ResourceProfile(cold_start_sec=360.0, hot_start_sec=360.0, peak_vram_mb=0),
    generates_audio=True,
    tags=["text-to-video", "audio", "fl2va", "vertical", "9:16"],
)

H3_VERTICAL_I2V_MANIFEST = WorkflowManifest(
    workflow_id="h3_vertical_i2v",
    version="1.0.0",
    family="h3_vertical_fl2va",
    workflow_mode="i2v",
    description="H3 Vertical Image-to-Video-Audio (9:16, ~800P): optimized for RTX 5080 16GB.",
    source_file="h3_vertical_i2v.json",
    workflow_hash="",
    frame_constraints=FrameConstraints(step=17, min_frames=5, max_frames=3600, default_frames=124, fps=24),
    resolution_constraints=ResolutionConstraints(
        min_width=256, max_width=4096, min_height=256, max_height=4096,
        width_multiple=32, height_multiple=32,
        default_width=448, default_height=800,
    ),
    input_slots=[
        InputSlot(
            binding_id="prompt",
            selector_title="LFO.MainGenerator",
            selector_class_type="MiniMaxH3ImageToVideo",
            input_name="prompt",
            value_type="string",
            description="Three-layer H3 prompt",
        ),
        InputSlot(
            binding_id="first_frame",
            selector_title="LFO.FirstFrame",
            selector_class_type="LoadImage",
            input_name="image",
            value_type="image",
            description="Input image to animate",
        ),
        InputSlot(
            binding_id="duration",
            selector_title="LFO.Duration",
            selector_class_type="PrimitiveFloat",
            input_name="value",
            value_type="float",
            description="Duration in seconds",
        ),
        InputSlot(
            binding_id="filename_prefix",
            selector_title="LFO.SaveVideo",
            selector_class_type="SaveVideo",
            input_name="filename_prefix",
            value_type="string",
            description="Output filename prefix",
        ),
    ],
    output_spec=OutputSpec(asset_type="video", count=1, format="mp4"),
    model_dependencies=[
        ModelDependency(role="unet", filename="minimax_h3_fl2va_pruned_int8_convrot.safetensors"),
        ModelDependency(role="clip", filename="qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"),
        ModelDependency(role="vae", filename="minimax_h3_video_vae_fp16.safetensors"),
        ModelDependency(role="audio_vae", filename="minimax_h3_audio_vae_fp32.safetensors"),
    ],
    resource_profile=ResourceProfile(cold_start_sec=360.0, hot_start_sec=360.0, peak_vram_mb=0),
    generates_audio=True,
    tags=["image-to-video", "audio", "fl2va", "vertical", "9:16"],
)

H3_VERTICAL_R2V_MANIFEST = WorkflowManifest(
    workflow_id="h3_vertical_r2v",
    version="1.0.0",
    family="h3_vertical_ref2va",
    workflow_mode="r2v",
    description="H3 Vertical Reference-to-Video (9:16, ~800P): optimized for RTX 5080 16GB.",
    source_file="h3_vertical_r2v.json",
    workflow_hash="",
    frame_constraints=FrameConstraints(step=17, min_frames=5, max_frames=3600, default_frames=124, fps=24),
    resolution_constraints=ResolutionConstraints(
        min_width=256, max_width=4096, min_height=256, max_height=4096,
        width_multiple=32, height_multiple=32,
        default_width=448, default_height=800,
    ),
    input_slots=[
        InputSlot(
            binding_id="prompt",
            selector_title="LFO.Prompt",
            selector_class_type="PrimitiveStringMultiline",
            input_name="value",
            value_type="string",
            description="Three-layer H3 prompt with <Picture N> references",
        ),
        InputSlot(
            binding_id="ref_image_0",
            selector_title="LFO.Reference01",
            selector_class_type="LoadImage",
            input_name="image",
            value_type="image",
            description="Reference image 1",
        ),
        InputSlot(
            binding_id="ref_image_1",
            selector_title="LFO.Reference02",
            selector_class_type="LoadImage",
            input_name="image",
            value_type="image",
            description="Reference image 2",
        ),
        InputSlot(
            binding_id="ref_image_2",
            selector_title="LFO.Reference03",
            selector_class_type="LoadImage",
            input_name="image",
            value_type="image",
            description="Reference image 3",
        ),
        InputSlot(
            binding_id="duration",
            selector_title="LFO.Duration",
            selector_class_type="PrimitiveFloat",
            input_name="value",
            value_type="float",
            description="Duration in seconds",
        ),
        InputSlot(
            binding_id="filename_prefix",
            selector_title="LFO.SaveVideo",
            selector_class_type="SaveVideo",
            input_name="filename_prefix",
            value_type="string",
            description="Output filename prefix",
        ),
    ],
    output_spec=OutputSpec(asset_type="video", count=1, format="mp4"),
    model_dependencies=[
        ModelDependency(role="unet", filename="minimax_h3_ref2va_pruned_int8_convrot.safetensors"),
        ModelDependency(role="clip", filename="qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"),
        ModelDependency(role="vae", filename="minimax_h3_video_vae_fp16.safetensors"),
        ModelDependency(role="audio_vae", filename="minimax_h3_audio_vae_fp32.safetensors"),
    ],
    resource_profile=ResourceProfile(cold_start_sec=370.0, hot_start_sec=370.0, peak_vram_mb=0),
    generates_audio=True,
    tags=["reference-to-video", "audio", "ref2va", "vertical", "9:16"],
)

SEEDVR2_UPSCALE_MANIFEST = WorkflowManifest(
    workflow_id="seedvr2_upscale",
    version="1.0.0",
    family="seedvr2",
    workflow_mode="upscale",
    description="SeedVR2 3B INT8 video restoration and 2x upscale with source audio passthrough.",
    source_file="seedvr2_upscale.json",
    workflow_hash="",
    frame_constraints=FrameConstraints(
        step=1,
        min_frames=1,
        max_frames=3600,
        default_frames=1,
        fps=24,
    ),
    resolution_constraints=ResolutionConstraints(
        min_width=1,
        max_width=16384,
        min_height=1,
        max_height=16384,
        width_multiple=1,
        height_multiple=1,
        default_width=864,
        default_height=480,
    ),
    input_slots=[
        InputSlot(
            binding_id="input_video",
            selector_title="LFO.InputVideo",
            selector_class_type="LoadVideo",
            input_name="file",
            value_type="video",
            description="Generated source video uploaded to ComfyUI input storage.",
        ),
        InputSlot(
            binding_id="scale_multiplier",
            selector_title="LFO.ScaleMultiplier",
            selector_class_type="ResizeImageMaskNode",
            input_name="resize_type.multiplier",
            value_type="float",
            description="SeedVR2 output scale relative to the source video.",
        ),
        InputSlot(
            binding_id="seed",
            selector_title="LFO.Seed",
            selector_class_type="KSampler",
            input_name="seed",
            value_type="int",
            description="Optional deterministic SeedVR2 sampling seed.",
            optional=True,
        ),
        InputSlot(
            binding_id="filename_prefix",
            selector_title="LFO.SaveVideo",
            selector_class_type="SaveVideo",
            input_name="filename_prefix",
            value_type="string",
            description="Output filename prefix managed by LFO.",
        ),
    ],
    output_spec=OutputSpec(asset_type="video", count=1, format="mp4"),
    model_dependencies=[
        ModelDependency(role="unet", filename="seedvr2_3b_int8_convrot.safetensors"),
        ModelDependency(role="vae", filename="seedvr2_ema_vae_fp16.safetensors"),
    ],
    generates_audio=True,
    tags=["video-upscale", "video-restoration", "seedvr2", "int8"],
)

# Registry of all known workflow manifests
KNOWN_WORKFLOWS = {
    "h3_standard_t2v": H3_T2V_MANIFEST,
    "h3_standard_i2v": H3_I2V_MANIFEST,
    "h3_standard_r2v": H3_R2V_MANIFEST,
    "h3_presenter_r2v": H3_PRESENTER_R2V_MANIFEST,
    "h3_vertical_t2v": H3_VERTICAL_T2V_MANIFEST,
    "h3_vertical_i2v": H3_VERTICAL_I2V_MANIFEST,
    "h3_vertical_r2v": H3_VERTICAL_R2V_MANIFEST,
    "seedvr2_upscale": SEEDVR2_UPSCALE_MANIFEST,
}


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

def make_capability(manifest: WorkflowManifest) -> WorkflowCapability:
    """Derive capability from manifest family and explicit workflow_mode."""
    mode = manifest.workflow_mode

    if mode == "t2va":
        return WorkflowCapability(
            workflow_id=manifest.workflow_id,
            modes=["t2va"],
            accepts_prompt=True,
            accepts_image=False,
            produces_video=True,
            produces_audio=True,
            limitations=["No image identity control"],
        )
    elif mode == "i2v":
        return WorkflowCapability(
            workflow_id=manifest.workflow_id,
            modes=["i2v", "first_last"],  # Same workflow supports both modes
            accepts_prompt=True,
            accepts_image=True,
            accepts_first_frame=True,
            produces_video=True,
            produces_audio=True,
            limitations=[],
        )
    elif mode == "first_last":
        return WorkflowCapability(
            workflow_id=manifest.workflow_id,
            modes=["i2v", "first_last"],
            accepts_prompt=True,
            accepts_image=True,
            accepts_first_frame=True,
            produces_video=True,
            produces_audio=True,
            limitations=[],
        )
    elif mode == "r2v":
        limitations = (
            [
                "Presenter slots are explicit and type-specific: ref_image_0..8, "
                "ref_video_0..2 and ref_audio_0..2"
            ]
            if manifest.workflow_id == "h3_presenter_r2v"
            else ["Fixed 3 reference slots"]
        )
        return WorkflowCapability(
            workflow_id=manifest.workflow_id,
            modes=["r2v"],
            accepts_prompt=True,
            accepts_image=False,
            accepts_reference_images=True,
            produces_video=True,
            produces_audio=True,
            limitations=limitations,
        )
    elif mode == "upscale":
        return WorkflowCapability(
            workflow_id=manifest.workflow_id,
            modes=["upscale"],
            accepts_prompt=False,
            accepts_image=False,
            produces_video=True,
            produces_audio=manifest.generates_audio,
            limitations=["Requires a source video artifact"],
        )
    return WorkflowCapability(workflow_id=manifest.workflow_id)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class WorkflowRegistry:
    """Load, validate, and query registered workflows."""

    def __init__(self, workflow_dir: str | pathlib.Path):
        self.workflow_dir = pathlib.Path(workflow_dir)
        self._manifests: dict[str, WorkflowManifest] = {}
        self._capabilities: dict[str, WorkflowCapability] = {}
        self._binding_reports: dict[str, BindingReport] = {}

    def register_all(self) -> dict[str, str]:
        """Register all known workflows from the workflow directory.

        Returns {workflow_id: status} where status is 'ok' or error message.
        """
        results = {}
        for wf_id in KNOWN_WORKFLOWS:
            try:
                self.register(wf_id)
                results[wf_id] = "ok"
            except Exception as e:
                results[wf_id] = str(e)
        return results

    def register(self, workflow_id: str) -> BindingReport:
        """Register a single workflow: load, hash, resolve bindings (strict mode).

        Production registration always uses strict mode — no silent fallback.
        Returns the binding report.
        Raises FileNotFoundError if workflow file missing.
        """
        if workflow_id not in KNOWN_WORKFLOWS:
            raise ValueError(f"Unknown workflow: {workflow_id}")

        # Deep copy so we never mutate the global KNOWN_WORKFLOWS template
        manifest = copy.deepcopy(KNOWN_WORKFLOWS[workflow_id])

        # Load workflow from disk
        wf_path = self.workflow_dir / manifest.source_file
        if not wf_path.exists():
            raise FileNotFoundError(f"Workflow file not found: {wf_path}")

        workflow = json.loads(wf_path.read_text(encoding="utf-8"))

        # Compute hash
        manifest.workflow_hash = compute_workflow_hash(workflow)

        # Resolve bindings — always strict for production
        from lfo.comfy.bindings import Binding, BindingResolver

        bindings = [
            Binding(
                binding_id=slot.binding_id,
                selector_title=slot.selector_title,
                selector_class_type=slot.selector_class_type,
                input_name=slot.input_name,
            )
            for slot in manifest.input_slots
        ]

        resolver = BindingResolver(workflow)
        report = BindingReport(workflow_id=workflow_id, mode="strict")

        for b in bindings:
            try:
                resolved = resolver.resolve_binding(b, mode="strict", warnings=report.warnings)
                report.bindings.append({
                    "binding_id": resolved.binding_id,
                    "node_id": resolved.resolved_node_id,
                    "input_name": resolved.input_name,
                    "class_type": resolved.selector_class_type,
                })
            except Exception as e:
                report.unresolved.append(b.binding_id)
                report.bindings.append({
                    "binding_id": b.binding_id,
                    "error": str(e),
                })

        report.status = "ok" if not report.unresolved else ("partial" if report.bindings else "failed")

        # production_ready: only when status=ok AND no warnings
        manifest.binding_policy = "strict_title_and_class"
        manifest.production_ready = (report.status == "ok" and not report.warnings)
        manifest.static_valid = manifest.production_ready

        # Store
        self._manifests[workflow_id] = manifest
        self._capabilities[workflow_id] = make_capability(manifest)
        self._binding_reports[workflow_id] = report

        return report

    def get_manifest(self, workflow_id: str) -> WorkflowManifest | None:
        return self._manifests.get(workflow_id)

    def get_capability(self, workflow_id: str) -> WorkflowCapability | None:
        return self._capabilities.get(workflow_id)

    def get_binding_report(self, workflow_id: str) -> BindingReport | None:
        return self._binding_reports.get(workflow_id)

    def list_workflows(self) -> list[str]:
        return list(self._manifests.keys())

    def validate_workflow(self, workflow_id: str) -> dict:
        """Run static validation (STRUCTURAL check, no live ComfyUI needed).

        Checks:
        - Workflow file exists
        - Workflow hash matches registered manifest
        - All bindings resolve (strict mode)
        - API format

        Returns {valid: bool, level: str, checks: [{name, status, message}]}
        Level is one of: STATIC_VALID, RUNTIME_COMPATIBLE, SMOKE_TESTED
        """
        checks = []

        if workflow_id not in self._manifests:
            return {
                "valid": False,
                "level": "UNREGISTERED",
                "checks": [{"name": "registered", "status": "fail", "message": f"{workflow_id} not registered"}],
            }

        manifest = self._manifests[workflow_id]

        # 1. File exists
        wf_path = self.workflow_dir / manifest.source_file
        file_exists = wf_path.exists()
        checks.append({
            "name": "file_exists",
            "status": "pass" if file_exists else "fail",
            "message": str(wf_path) if file_exists else f"Missing: {wf_path}",
        })

        if not file_exists:
            return {"valid": False, "level": "STATIC_VALID", "checks": checks}

        # 2. Hash match
        workflow = json.loads(wf_path.read_text(encoding="utf-8"))
        current_hash = compute_workflow_hash(workflow)
        hash_ok = current_hash == manifest.workflow_hash
        checks.append({
            "name": "hash_match",
            "status": "pass" if hash_ok else "warn",
            "message": "Hash unchanged" if hash_ok else "Workflow file changed since registration",
        })

        # 3. Bindings resolve (strict mode)
        from lfo.comfy.bindings import Binding, BindingResolver
        bindings = [
            Binding(
                binding_id=slot.binding_id,
                selector_title=slot.selector_title,
                selector_class_type=slot.selector_class_type,
                input_name=slot.input_name,
            )
            for slot in manifest.input_slots
        ]
        resolver = BindingResolver(workflow)
        binding_warnings: list[str] = []
        binding_ok = True
        for b in bindings:
            try:
                resolver.resolve_binding(b, mode="strict", warnings=binding_warnings)
            except Exception:
                binding_ok = False
        checks.append({
            "name": "bindings_resolve",
            "status": "pass" if binding_ok else "fail",
            "message": "All bindings resolve (strict)" if binding_ok else "Some bindings failed",
        })

        # 4. API format
        from lfo.comfy.workflow import WorkflowLoader
        is_api = WorkflowLoader.is_api_format(workflow)
        checks.append({
            "name": "api_format",
            "status": "pass" if is_api else "fail",
            "message": "API format" if is_api else "Not API format",
        })

        all_pass = all(c["status"] == "pass" for c in checks)

        # Update manifest validation state
        manifest.static_valid = all_pass
        if all_pass:
            manifest.production_ready = not binding_warnings

        # Determine level
        level = "STATIC_VALID"
        if manifest.smoke_tested:
            level = "SMOKE_TESTED"
        elif manifest.runtime_compatible:
            level = "RUNTIME_COMPATIBLE"

        return {"valid": all_pass, "level": level, "checks": checks}

    def check_runtime_compatibility(
        self,
        workflow_id: str,
        comfy_client=None,
        model_dir: str | None = None,
    ) -> dict:
        """Check runtime compatibility against live ComfyUI /object_info.

        This verifies that:
        - Each bound node's class_type exists in the current ComfyUI
        - The bound input names exist on the node
        - Input types are compatible (required vs optional)
        - Required model files exist (if model_dir provided)

        Requires a live ComfyUI connection. Returns:
        {compatible: bool, level: str, checks: [...]}
        """
        checks = []

        if workflow_id not in self._manifests:
            return {
                "compatible": False,
                "level": "UNREGISTERED",
                "checks": [{"name": "registered", "status": "fail", "message": f"{workflow_id} not registered"}],
            }

        manifest = self._manifests[workflow_id]

        # Lazy import to avoid hard dependency
        from lfo.comfy.client import ComfyApiClient
        client = comfy_client or ComfyApiClient()

        # Fetch all node info from ComfyUI
        try:
            object_info = client.get_object_info()
        except Exception as e:
            return {
                "compatible": False,
                "level": "STATIC_VALID",
                "checks": [{
                    "name": "comfyui_connection",
                    "status": "fail",
                    "message": f"Cannot reach ComfyUI: {e}",
                }],
            }

        # Check every class used by the static API graph as well as the
        # explicitly bound inputs below.  Presenter reference loader classes
        # are injected dynamically by the backend and are declared by its
        # capability manifest; the core graph still must expose its H3 R2V
        # generator and decode/encode pipeline to /object_info.
        wf_path = self.workflow_dir / manifest.source_file
        try:
            workflow = json.loads(wf_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            return {
                "compatible": False,
                "level": "STATIC_VALID",
                "checks": [{
                    "name": "workflow_graph",
                    "status": "fail",
                    "message": f"Cannot load workflow graph: {exc}",
                }],
            }
        graph_classes: set[str] = {
            class_type
            for node in workflow.values()
            if isinstance(node, dict)
            and isinstance((class_type := node.get("class_type")), str)
        }
        if manifest.workflow_id == "h3_presenter_r2v":
            # These upload/decomposition nodes are injected per declared
            # reference slot, so they are runtime requirements even though
            # the static template deliberately contains no placeholder media.
            graph_classes.update(
                {"LoadImage", "LoadVideo", "GetVideoComponents", "LoadAudio"}
            )
        for class_type in sorted(graph_classes):
            checks.append({
                "name": f"node_class_{class_type}",
                "status": "pass" if class_type in object_info else "fail",
                "message": (
                    f"Node class '{class_type}' exists in ComfyUI"
                    if class_type in object_info
                    else f"Node class '{class_type}' not found in ComfyUI"
                ),
            })

        # Check each input slot's node class and input name
        for slot in manifest.input_slots:
            class_type = slot.selector_class_type

            if class_type not in object_info:
                checks.append({
                    "name": f"node_class_{class_type}",
                    "status": "fail",
                    "message": f"Node class '{class_type}' not found in ComfyUI",
                })
                continue

            node_info = object_info[class_type]
            input_specs = node_info.get("input", {})

            # Check required and optional inputs
            all_inputs = {}
            for category in ("required", "optional"):
                if category in input_specs:
                    all_inputs.update(input_specs[category])

            if slot.input_name not in all_inputs:
                checks.append({
                    "name": f"input_{class_type}.{slot.input_name}",
                    "status": "fail",
                    "message": (
                        f"Input '{slot.input_name}' not found on '{class_type}'. "
                        f"Available: {list(all_inputs.keys())}"
                    ),
                })
            else:
                checks.append({
                    "name": f"input_{class_type}.{slot.input_name}",
                    "status": "pass",
                    "message": f"Input '{slot.input_name}' exists on '{class_type}'",
                })

        # Check model dependencies
        if model_dir:
            import pathlib
            mdir = pathlib.Path(model_dir)
            for dep in manifest.model_dependencies:
                if not dep.required:
                    continue
                model_path = mdir / dep.filename
                exists = model_path.exists()
                checks.append({
                    "name": f"model_{dep.role}",
                    "status": "pass" if exists else "fail",
                    "message": f"Model '{dep.filename}' {'found' if exists else 'MISSING'}",
                })

        all_pass = all(c["status"] == "pass" for c in checks)

        # Update manifest
        manifest.runtime_compatible = all_pass
        if all_pass:
            level = "RUNTIME_COMPATIBLE"
            if manifest.smoke_tested:
                level = "SMOKE_TESTED"
        else:
            level = "STATIC_VALID"

        return {"compatible": all_pass, "level": level, "checks": checks}

    def mark_smoke_tested(self, workflow_id: str) -> None:
        """Mark a workflow as smoke-tested (actually executed on this machine)."""
        if workflow_id in self._manifests:
            self._manifests[workflow_id].smoke_tested = True

    def export_registry(self, output_dir: str | pathlib.Path) -> None:
        """Export all manifests, capabilities, and binding reports to JSON files."""
        out = pathlib.Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        for wf_id, manifest in self._manifests.items():
            (out / f"{wf_id}_manifest.json").write_text(
                json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        for wf_id, cap in self._capabilities.items():
            (out / f"{wf_id}_capability.json").write_text(
                json.dumps(cap.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        for wf_id, report in self._binding_reports.items():
            (out / f"{wf_id}_binding_report.json").write_text(
                json.dumps(report.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

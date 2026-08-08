"""Tests for runtime compatibility checking (mocked /object_info)."""
import json
import pathlib

import pytest

from lfo.core.workflow_registry import (
    WorkflowRegistry,
)

# ---------------------------------------------------------------------------
# Mock ComfyUI /object_info
# ---------------------------------------------------------------------------

MOCK_OBJECT_INFO = {
    # --- Expanded pipeline: loaders ---
    "UNETLoader": {
        "input": {
            "required": {
                "unet_name": ["STRING", {"default": "model.safetensors"}],
            },
        },
        "output": ["MODEL"],
        "output_name": ["MODEL"],
        "name": "UNET Loader",
        "display_name": "UNET Loader",
        "description": "Load a UNET model",
        "category": "loaders",
    },
    "CLIPLoader": {
        "input": {
            "required": {
                "clip_name": ["STRING", {"default": "clip.safetensors"}],
                "type": ["STRING", {"default": "default"}],
            },
        },
        "output": ["CLIP"],
        "output_name": ["CLIP"],
        "name": "CLIP Loader",
        "display_name": "CLIP Loader",
        "description": "Load a CLIP model",
        "category": "loaders",
    },
    "VAELoader": {
        "input": {
            "required": {
                "vae_name": ["STRING", {"default": "vae.safetensors"}],
            },
        },
        "output": ["VAE"],
        "output_name": ["VAE"],
        "name": "VAE Loader",
        "display_name": "VAE Loader",
        "description": "Load a VAE model",
        "category": "loaders",
    },
    # --- Expanded pipeline: conditioning ---
    "MiniMaxH3ImageToVideo": {
        "input": {
            "required": {
                "clip": ["CLIP", {}],
                "vae": ["VAE", {}],
                "prompt": ["STRING", {"multiline": True}],
                "width": ["INT", {"default": 1344, "min": 32, "max": 16384, "step": 32}],
                "height": ["INT", {"default": 768, "min": 32, "max": 16384, "step": 32}],
                "length": ["INT", {"default": 124, "min": 5, "max": 3600, "step": 17}],
            },
            "optional": {
                "first_frame": ["IMAGE"],
                "last_frame": ["IMAGE"],
            },
        },
        "output": ["CONDITIONING", "LATENT"],
        "output_name": ["positive", "LATENT"],
        "name": "MiniMax H3 Image To Video",
        "display_name": "MiniMax H3 Image To Video",
        "description": "H3 T2VA/I2V/First-Last conditioning + latent",
        "category": "minimax_h3",
    },
    "MiniMaxH3ReferenceToVideo": {
        "input": {
            "required": {
                "clip": ["CLIP", {}],
                "vae": ["VAE", {}],
                "audio_vae": ["VAE", {}],
                "prompt": ["STRING", {"multiline": True}],
                "width": ["INT", {"default": 1344, "min": 32, "step": 32}],
                "height": ["INT", {"default": 768, "min": 32, "step": 32}],
                "length": ["INT", {"default": 124, "min": 5, "step": 17}],
                "ref_image_size": ["STRING", {"default": "match"}],
            },
            "optional": {
                "ref_images": ["REF_IMAGES"],
            },
        },
        "output": ["CONDITIONING", "LATENT"],
        "output_name": ["positive", "LATENT"],
        "name": "MiniMax H3 Reference To Video",
        "display_name": "MiniMax H3 Reference To Video",
        "description": "H3 R2V",
        "category": "minimax_h3",
    },
    # --- Expanded pipeline: sampling ---
    "BasicGuider": {
        "input": {
            "required": {
                "model": ["MODEL", {}],
                "conditioning": ["CONDITIONING", {}],
            },
        },
        "output": ["GUIDER"],
        "output_name": ["GUIDER"],
        "name": "Basic Guider",
        "display_name": "Basic Guider",
        "description": "Guide sampling with conditioning",
        "category": "sampling",
    },
    "KSamplerSelect": {
        "input": {
            "required": {
                "sampler_name": ["STRING", {"default": "euler"}],
            },
        },
        "output": ["SAMPLER"],
        "output_name": ["SAMPLER"],
        "name": "KSampler Select",
        "display_name": "KSampler Select",
        "description": "Select a sampler",
        "category": "sampling",
    },
    "BasicScheduler": {
        "input": {
            "required": {
                "model": ["MODEL", {}],
                "scheduler": ["STRING", {"default": "normal"}],
                "steps": ["INT", {"default": 20, "min": 1}],
                "denoise": ["FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0}],
            },
        },
        "output": ["SIGMAS"],
        "output_name": ["SIGMAS"],
        "name": "Basic Scheduler",
        "display_name": "Basic Scheduler",
        "description": "Scheduler for sampling steps",
        "category": "sampling",
    },
    "RandomNoise": {
        "input": {
            "required": {
                "noise_seed": ["INT", {"default": 0, "min": 0, "max": 18446744073709551615}],
            },
        },
        "output": ["NOISE"],
        "output_name": ["NOISE"],
        "name": "Random Noise",
        "display_name": "Random Noise",
        "description": "Generate random noise",
        "category": "sampling",
    },
    "SamplerCustomAdvanced": {
        "input": {
            "required": {
                "noise": ["NOISE", {}],
                "guider": ["GUIDER", {}],
                "sampler": ["SAMPLER", {}],
                "sigmas": ["SIGMAS", {}],
                "latent_image": ["LATENT", {}],
            },
        },
        "output": ["LATENT"],
        "output_name": ["LATENT"],
        "name": "Sampler Custom Advanced",
        "display_name": "Sampler Custom Advanced",
        "description": "Advanced custom sampler",
        "category": "sampling",
    },
    # --- Expanded pipeline: decode + combine ---
    "VAEDecode": {
        "input": {
            "required": {
                "samples": ["LATENT", {}],
                "vae": ["VAE", {}],
            },
        },
        "output": ["IMAGE"],
        "output_name": ["IMAGE"],
        "name": "VAE Decode",
        "display_name": "VAE Decode",
        "description": "Decode latents to images",
        "category": "latent",
    },
    "VAEDecodeAudio": {
        "input": {
            "required": {
                "samples": ["LATENT", {}],
                "vae": ["VAE", {}],
            },
        },
        "output": ["AUDIO"],
        "output_name": ["AUDIO"],
        "name": "VAE Decode Audio",
        "display_name": "VAE Decode Audio",
        "description": "Decode latents to audio",
        "category": "latent",
    },
    "CreateVideo": {
        "input": {
            "required": {
                "fps": ["INT", {"default": 24, "min": 1}],
                "images": ["IMAGE", {}],
            },
            "optional": {
                "audio": ["AUDIO"],
            },
        },
        "output": ["VIDEO"],
        "output_name": ["VIDEO"],
        "name": "Create Video",
        "display_name": "Create Video",
        "description": "Combine images and audio into video",
        "category": "video",
    },
    "SaveVideo": {
        "input": {
            "required": {
                "filename_prefix": ["STRING", {"default": "ComfyUI"}],
                "video": ["VIDEO"],
            },
        },
        "output": [],
        "output_name": [],
        "name": "Save Video",
        "display_name": "Save Video",
        "description": "Save video with audio",
        "category": "video",
    },
    # --- I2V-specific nodes ---
    "LoadImage": {
        "input": {
            "required": {
                "image": ["IMAGE", {"image_upload": True}],
            },
        },
        "output": ["IMAGE"],
        "output_name": ["IMAGE"],
        "name": "Load Image",
        "display_name": "Load Image",
        "description": "Load an image",
        "category": "image",
    },
    "ImageScaleToTotalPixels": {
        "input": {
            "required": {
                "image": ["IMAGE", {}],
                "upscale_method": ["STRING", {"default": "nearest-exact"}],
                "megapixels": ["FLOAT", {"default": 1.0, "min": 0.01}],
            },
        },
        "output": ["IMAGE"],
        "output_name": ["IMAGE"],
        "name": "Image Scale To Total Pixels",
        "display_name": "Image Scale To Total Pixels",
        "description": "Scale image to target megapixels",
        "category": "image",
    },
    "GetImageSize": {
        "input": {
            "required": {
                "image": ["IMAGE", {}],
            },
        },
        "output": ["INT", "INT"],
        "output_name": ["width", "height"],
        "name": "Get Image Size",
        "display_name": "Get Image Size",
        "description": "Get image dimensions",
        "category": "image",
    },
    # --- R2V-specific nodes ---
    "ResolutionSelector": {
        "input": {
            "required": {
                "aspect_ratio": ["STRING", {"default": "16:9"}],
                "megapixels": ["FLOAT", {"default": 1.0}],
                "multiple": ["INT", {"default": 32}],
            },
        },
        "output": ["INT", "INT"],
        "output_name": ["width", "height"],
        "name": "Resolution Selector",
        "display_name": "Resolution Selector",
        "description": "Select resolution by aspect ratio and megapixels",
        "category": "utils",
    },
    "PrimitiveStringMultiline": {
        "input": {
            "required": {
                "value": ["STRING", {"multiline": True}],
            },
        },
        "output": ["STRING"],
        "output_name": ["STRING"],
        "name": "Primitive String Multiline",
        "display_name": "Primitive String Multiline",
        "description": "Multiline string primitive",
        "category": "utils",
    },
    "PrimitiveFloat": {
        "input": {
            "required": {
                "value": ["FLOAT", {"default": 0.0}],
            },
        },
        "output": ["FLOAT"],
        "output_name": ["FLOAT"],
        "name": "Primitive Float",
        "display_name": "Primitive Float",
        "description": "Float primitive",
        "category": "utils",
    },
    "ComfyMathExpression": {
        "input": {
            "required": {
                "expression": ["STRING", {"default": ""}],
            },
        },
        "output": ["FLOAT", "INT", "BOOLEAN"],
        "output_name": ["FLOAT", "INT", "BOOL"],
        "name": "Math Expression",
        "display_name": "Math Expression",
        "description": "Evaluate math expressions",
        "category": "utils",
    },
}


class MockComfyClient:
    """Mock ComfyUI client that returns canned /object_info."""

    def __init__(self, object_info=None, fail_connect=False):
        self._info = object_info or MOCK_OBJECT_INFO
        self._fail_connect = fail_connect

    def get_object_info(self, node_class=None):
        if self._fail_connect:
            raise ConnectionError("ComfyUI not reachable")
        if node_class:
            if node_class in self._info:
                return {node_class: self._info[node_class]}
            return {}
        return self._info


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workflow_dir(tmp_path):
    """Copy test workflow fixtures to a temp directory."""
    src = pathlib.Path(__file__).parent / "fixtures" / "workflows"
    dst = tmp_path / "workflows"
    dst.mkdir()
    for f in src.glob("*.json"):
        (dst / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    return dst


@pytest.fixture
def registry(workflow_dir):
    reg = WorkflowRegistry(workflow_dir)
    return reg


# ---------------------------------------------------------------------------
# Runtime compatibility — happy path
# ---------------------------------------------------------------------------

class TestRuntimeCompatibilityHappy:
    def test_t2v_runtime_compatible(self, registry):
        registry.register("h3_standard_t2v")
        result = registry.check_runtime_compatibility(
            "h3_standard_t2v",
            comfy_client=MockComfyClient(),
        )
        assert result["compatible"] is True
        assert result["level"] == "RUNTIME_COMPATIBLE"

    def test_i2v_runtime_compatible(self, registry):
        registry.register("h3_standard_i2v")
        result = registry.check_runtime_compatibility(
            "h3_standard_i2v",
            comfy_client=MockComfyClient(),
        )
        assert result["compatible"] is True
        assert result["level"] == "RUNTIME_COMPATIBLE"

    def test_r2v_runtime_compatible(self, registry):
        registry.register("h3_standard_r2v")
        result = registry.check_runtime_compatibility(
            "h3_standard_r2v",
            comfy_client=MockComfyClient(),
        )
        assert result["compatible"] is True
        assert result["level"] == "RUNTIME_COMPATIBLE"

    def test_check_names_included(self, registry):
        registry.register("h3_standard_t2v")
        result = registry.check_runtime_compatibility(
            "h3_standard_t2v",
            comfy_client=MockComfyClient(),
        )
        check_names = {c["name"] for c in result["checks"]}
        # Should have input checks for prompt, length, filename_prefix
        assert any("prompt" in n for n in check_names)
        assert any("filename_prefix" in n for n in check_names)


# ---------------------------------------------------------------------------
# Runtime compatibility — failures
# ---------------------------------------------------------------------------

class TestRuntimeCompatibilityFailures:
    def test_missing_node_class(self, registry):
        """When a node class doesn't exist in ComfyUI."""
        registry.register("h3_standard_t2v")
        # Object info without MiniMaxH3ImageToVideo
        partial_info = {"SaveVideo": MOCK_OBJECT_INFO["SaveVideo"]}
        result = registry.check_runtime_compatibility(
            "h3_standard_t2v",
            comfy_client=MockComfyClient(object_info=partial_info),
        )
        assert result["compatible"] is False
        assert any(c["status"] == "fail" for c in result["checks"])

    def test_missing_input_name(self, registry):
        """When a bound input doesn't exist on the node."""
        registry.register("h3_standard_t2v")
        # Remove 'prompt' from MiniMaxH3ImageToVideo required inputs
        bad_info = json.loads(json.dumps(MOCK_OBJECT_INFO))
        del bad_info["MiniMaxH3ImageToVideo"]["input"]["required"]["prompt"]
        result = registry.check_runtime_compatibility(
            "h3_standard_t2v",
            comfy_client=MockComfyClient(object_info=bad_info),
        )
        assert result["compatible"] is False
        prompt_check = next(
            c for c in result["checks"] if "prompt" in c["name"]
        )
        assert prompt_check["status"] == "fail"

    def test_comfyui_unreachable(self, registry):
        registry.register("h3_standard_t2v")
        result = registry.check_runtime_compatibility(
            "h3_standard_t2v",
            comfy_client=MockComfyClient(fail_connect=True),
        )
        assert result["compatible"] is False
        assert result["checks"][0]["name"] == "comfyui_connection"


# ---------------------------------------------------------------------------
# Three-tier validation levels
# ---------------------------------------------------------------------------

class TestValidationLevels:
    def test_static_valid_after_register(self, registry):
        """After static validation, level is STATIC_VALID."""
        registry.register("h3_standard_t2v")
        result = registry.validate_workflow("h3_standard_t2v")
        assert result["valid"] is True
        assert result["level"] == "STATIC_VALID"

    def test_runtime_compatible_after_check(self, registry):
        """After runtime check, level upgrades to RUNTIME_COMPATIBLE."""
        registry.register("h3_standard_t2v")
        registry.check_runtime_compatibility(
            "h3_standard_t2v",
            comfy_client=MockComfyClient(),
        )
        result = registry.validate_workflow("h3_standard_t2v")
        assert result["level"] == "RUNTIME_COMPATIBLE"

    def test_smoke_tested_highest(self, registry):
        """Smoke tested is the highest level."""
        registry.register("h3_standard_t2v")
        registry.check_runtime_compatibility(
            "h3_standard_t2v",
            comfy_client=MockComfyClient(),
        )
        registry.mark_smoke_tested("h3_standard_t2v")
        result = registry.validate_workflow("h3_standard_t2v")
        assert result["level"] == "SMOKE_TESTED"

    def test_manifest_fields_updated(self, registry):
        registry.register("h3_standard_t2v")
        registry.check_runtime_compatibility(
            "h3_standard_t2v",
            comfy_client=MockComfyClient(),
        )
        m = registry.get_manifest("h3_standard_t2v")
        assert m.static_valid is True
        assert m.runtime_compatible is True
        assert m.smoke_tested is False


# ---------------------------------------------------------------------------
# production_ready
# ---------------------------------------------------------------------------

class TestProductionReady:
    def test_production_ready_after_register(self, registry):
        registry.register("h3_standard_t2v")
        m = registry.get_manifest("h3_standard_t2v")
        # Should be production_ready after successful registration
        assert m.production_ready is True
        assert m.binding_policy == "strict_title_and_class"

    def test_not_ready_when_unregistered(self, registry):
        result = registry.validate_workflow("h3_standard_t2v")
        assert result["valid"] is False
        assert result["level"] == "UNREGISTERED"

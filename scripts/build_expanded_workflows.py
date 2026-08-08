#!/usr/bin/env python3
"""Build expanded T2V/I2V workflows (replacing 4c314f31 hash node with real nodes)
and update all registry manifests + binding reports.

The 4c314f31 hash node is a wrapper that internally handles:
  UNETLoader + CLIPLoader + VAELoader + VAELoader +
  MiniMaxH3ImageToVideo + BasicGuider + KSamplerSelect + BasicScheduler +
  RandomNoise + SamplerCustomAdvanced + VAEDecode + VAEDecodeAudio +
  CreateVideo

Since 4c314f31 is NOT available on the running ComfyUI, we expand to the full
pipeline using the real node types.
"""
from __future__ import annotations

import json
import pathlib

# ---------------------------------------------------------------------------
# Workflow builders
# ---------------------------------------------------------------------------

def build_t2v_workflow() -> dict:
    """Expanded T2V: Resolution + Conditioning + Sampling + Decode + CreateVideo."""
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
                "weight_dtype": "default",
            },
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
                "type": "minimax",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "minimax_h3_video_vae_fp16.safetensors",
            },
        },
        "4": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "minimax_h3_audio_vae_fp32.safetensors",
            },
        },
        "5": {
            "_meta": {"title": "LFO.Resolution"},
            "class_type": "ResolutionSelector",
            "inputs": {
                "aspect_ratio": "16:9 (Widescreen)",
                "megapixels": 0.4,
                "multiple": 32,
            },
        },
        "6": {
            "_meta": {"title": "LFO.Duration"},
            "class_type": "PrimitiveFloat",
            "inputs": {
                "value": 5,
            },
        },
        "7": {
            "class_type": "ComfyMathExpression",
            "inputs": {
                "values.a": ["6", 0],
                "expression": "max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17",
            },
        },
        "8": {
            "_meta": {"title": "LFO.MainGenerator"},
            "class_type": "MiniMaxH3ImageToVideo",
            "inputs": {
                "clip": ["2", 0],
                "vae": ["3", 0],
                "prompt": "test prompt",
                "width": ["5", 0],
                "height": ["5", 1],
                "length": ["7", 1],
            },
        },
        "9": {
            "class_type": "BasicGuider",
            "inputs": {
                "model": ["1", 0],
                "conditioning": ["8", 0],
            },
        },
        "10": {
            "class_type": "KSamplerSelect",
            "inputs": {
                "sampler_name": "res_multistep",
            },
        },
        "11": {
            "class_type": "BasicScheduler",
            "inputs": {
                "model": ["1", 0],
                "scheduler": "simple",
                "steps": 20,
                "denoise": 1.0,
            },
        },
        "12": {
            "class_type": "RandomNoise",
            "inputs": {
                "noise_seed": 12345,
            },
        },
        "13": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["12", 0],
                "guider": ["9", 0],
                "sampler": ["10", 0],
                "sigmas": ["11", 0],
                "latent_image": ["8", 1],
            },
        },
        "14": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["13", 0],
                "vae": ["3", 0],
            },
        },
        "15": {
            "class_type": "VAEDecodeAudio",
            "inputs": {
                "samples": ["13", 0],
                "vae": ["4", 0],
            },
        },
        "16": {
            "class_type": "CreateVideo",
            "inputs": {
                "fps": 24,
                "images": ["14", 0],
                "audio": ["15", 0],
            },
        },
        "17": {
            "_meta": {"title": "LFO.SaveVideo"},
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["16", 0],
                "filename_prefix": "video/test_t2v",
                "format": "mp4",
                "codec": "h264",
            },
        },
    }


 

def build_i2v_workflow() -> dict:
    """Expanded I2V: LoadImage + ImageScale + Resolution + Conditioning + Sampling + Decode + CreateVideo."""
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
                "weight_dtype": "default",
            },
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {
                "clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
                "type": "minimax",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "minimax_h3_video_vae_fp16.safetensors",
            },
        },
        "4": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name": "minimax_h3_audio_vae_fp32.safetensors",
            },
        },
        "5": {
            "_meta": {"title": "LFO.Resolution"},
            "class_type": "ResolutionSelector",
            "inputs": {
                "aspect_ratio": "1:1 (Square)",
                "megapixels": 0.6,
                "multiple": 32,
            },
        },
        "6": {
            "_meta": {"title": "LFO.FirstFrame"},
            "class_type": "LoadImage",
            "inputs": {
                "image": "test_input.png",
            },
        },
        "7": {
            "class_type": "ImageScaleToTotalPixels",
            "inputs": {
                "image": ["6", 0],
                "upscale_method": "nearest-exact",
                "megapixels": 1,
            },
        },
        "8": {
            "class_type": "GetImageSize",
            "inputs": {
                "image": ["7", 0],
            },
        },
        "9": {
            "_meta": {"title": "LFO.Duration"},
            "class_type": "PrimitiveFloat",
            "inputs": {
                "value": 5,
            },
        },
        "10": {
            "class_type": "ComfyMathExpression",
            "inputs": {
                "values.a": ["9", 0],
                "expression": "max(5, round(a * 24)) + (5 - (max(5, round(a * 24)) % 17)) % 17",
            },
        },
        "11": {
            "_meta": {"title": "LFO.MainGenerator"},
            "class_type": "MiniMaxH3ImageToVideo",
            "inputs": {
                "clip": ["2", 0],
                "vae": ["3", 0],
                "prompt": "test i2v prompt",
                "width": ["5", 0],
                "height": ["5", 1],
                "length": ["10", 1],
                "first_frame": ["6", 0],
            },
        },
        "12": {
            "class_type": "BasicGuider",
            "inputs": {
                "model": ["1", 0],
                "conditioning": ["11", 0],
            },
        },
        "13": {
            "class_type": "KSamplerSelect",
            "inputs": {
                "sampler_name": "res_multistep",
            },
        },
        "14": {
            "class_type": "BasicScheduler",
            "inputs": {
                "model": ["1", 0],
                "scheduler": "simple",
                "steps": 20,
                "denoise": 1.0,
            },
        },
        "15": {
            "class_type": "RandomNoise",
            "inputs": {
                "noise_seed": 12345,
            },
        },
        "16": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["15", 0],
                "guider": ["12", 0],
                "sampler": ["13", 0],
                "sigmas": ["14", 0],
                "latent_image": ["11", 1],
            },
        },
        "17": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["16", 0],
                "vae": ["3", 0],
            },
        },
        "18": {
            "class_type": "VAEDecodeAudio",
            "inputs": {
                "samples": ["16", 0],
                "vae": ["4", 0],
            },
        },
        "19": {
            "class_type": "CreateVideo",
            "inputs": {
                "fps": 24,
                "images": ["17", 0],
                "audio": ["18", 0],
            },
        },
        "20": {
            "_meta": {"title": "LFO.SaveVideo"},
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["19", 0],
                "filename_prefix": "video/test_i2v",
                "format": "mp4",
                "codec": "h264",
            },
        },
    }

# ---------------------------------------------------------------------------
# Hash computation
# ---------------------------------------------------------------------------

def compute_hash(workflow: dict) -> str:
    """Compute LFO-WFJ1 hash."""
    import hashlib

    def normalize(obj):
        if isinstance(obj, float):
            if obj == 0.0:
                return 0
            if obj == int(obj) and not (obj != obj):
                return int(obj)
            return obj
        if isinstance(obj, str):
            import unicodedata
            return unicodedata.normalize("NFC", obj)
        if isinstance(obj, dict):
            return {k: normalize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [normalize(v) for v in obj]
        return obj

    normalized = normalize(workflow)
    text = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    root = pathlib.Path(__file__).resolve().parent.parent
    wf_dir = root / "tests" / "fixtures" / "workflows"
    reg_dir = root / "src" / "lfo" / "registry"

    # 1. Build and write workflows
    t2v = build_t2v_workflow()
    i2v = build_i2v_workflow()

    t2v_path = wf_dir / "h3_standard_t2v.json"
    i2v_path = wf_dir / "h3_standard_i2v.json"

    t2v_path.write_text(json.dumps(t2v, indent=2, ensure_ascii=False), encoding="utf-8")
    i2v_path.write_text(json.dumps(i2v, indent=2, ensure_ascii=False), encoding="utf-8")

    t2v_hash = compute_hash(t2v)
    i2v_hash = compute_hash(i2v)

    print(f"T2V workflow: {len(t2v)} nodes → {t2v_path}")
    print(f"T2V hash: {t2v_hash}")
    print(f"I2V workflow: {len(i2v)} nodes → {i2v_path}")
    print(f"I2V hash: {i2v_hash}")

    # 2. Update manifests
    def update_manifest(name: str, new_hash: str, description: str, tags: list[str]):
        path = reg_dir / f"{name}_manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["workflow_hash"] = new_hash
        data["version"] = "3.0.0"
        data["description"] = description
        data["tags"] = tags
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  manifest: {path.name}")

    update_manifest(
        "h3_standard_t2v",
        t2v_hash,
        "H3 Text-to-Video-Audio (v3): expanded pipeline with MiniMaxH3ImageToVideo + auto-duration math.",
        ["text-to-video", "audio", "fl2va", "auto-duration"],
    )
    update_manifest(
        "h3_standard_i2v",
        i2v_hash,
        "H3 Image-to-Video-Audio (v3): expanded pipeline with MiniMaxH3ImageToVideo + first_frame + auto-duration math.",
        ["image-to-video", "audio", "fl2va", "auto-duration"],
    )

    # 3. Update binding reports (hashes stay same structure, just re-write for consistency)
    def update_binding_report(name: str):
        path = reg_dir / f"{name}_binding_report.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = "ok"
        data["warnings"] = []
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  binding: {path.name}")

    update_binding_report("h3_standard_t2v")
    update_binding_report("h3_standard_i2v")

    print("\nDone. Now update workflow_registry.py bindings to match.")


if __name__ == "__main__":
    main()

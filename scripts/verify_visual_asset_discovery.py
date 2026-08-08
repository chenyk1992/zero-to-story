"""Wave 1-D: auto visual asset discovery verification.

Low-cost verification (does not block E2E-A):
1. Check Qwen model availability
2. Check available ComfyUI nodes
3. Confirm Workflow API format detection
4. Record runtime compatibility
5. Verify H3/Qwen switch feasibility

Outputs a JSON report to stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lfo.comfy.client import ComfyApiClient
from lfo.comfy.workflow import WorkflowLoader


def check_qwen_model(client: ComfyApiClient) -> dict:
    """Check if Qwen model loader nodes are available."""
    try:
        info = client.get_object_info()
        qwen_nodes = {
            name: data for name, data in info.items()
            if "qwen" in name.lower()
        }
        return {
            "available": len(qwen_nodes) > 0,
            "nodes": list(qwen_nodes.keys())[:20],
            "count": len(qwen_nodes),
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def check_h3_model(client: ComfyApiClient) -> dict:
    """Check if H3/FL2VA model nodes are available."""
    try:
        info = client.get_object_info()
        h3_nodes = {
            name: data for name, data in info.items()
            if any(kw in name.lower() for kw in ["h3", "fl2va", "wan", "video"])
        }
        return {
            "available": len(h3_nodes) > 0,
            "nodes": list(h3_nodes.keys())[:20],
            "count": len(h3_nodes),
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}


def check_nodes(client: ComfyApiClient) -> dict:
    """List all available node class types."""
    try:
        info = client.get_object_info()
        return {
            "total": len(info),
            "sample": list(info.keys())[:30],
            "has_load_image": "LoadImage" in info,
            "has_k_sampler": "KSampler" in info,
            "has_empty_latent": any("EmptyLatent" in k for k in info),
            "has_vae_decode": any("VAEDecode" in k for k in info),
            "has_save_video": any("VHS_VideoCombine" in k or "SaveVideo" in k for k in info),
        }
    except Exception as exc:
        return {"error": str(exc)}


def check_workflow_api_format(registry_dir: Path) -> dict:
    """Verify Workflow API format detection on exported workflows."""
    results = {}
    for wf_file in registry_dir.glob("*.json"):
        try:
            wf = WorkflowLoader.load(wf_file)
            is_api = WorkflowLoader.is_api_format(wf)
            results[wf_file.name] = {
                "is_api_format": is_api,
                "node_count": len(wf),
            }
        except Exception as exc:
            results[wf_file.name] = {"error": str(exc)}
    return results


def check_runtime_compatibility(client: ComfyApiClient) -> dict:
    """Record runtime compatibility info."""
    try:
        stats = client.get_system_stats()
        gpu = stats.get("devices", [{}])[0]
        return {
            "comfyui_reachable": True,
            "system": stats.get("system", {}),
            "gpu_name": gpu.get("name", "unknown"),
            "gpu_type": gpu.get("type", "unknown"),
            "vram_total_mb": gpu.get("vram_total", 0) / 1024 if gpu.get("vram_total") else 0,
            "vram_free_mb": gpu.get("vram_free", 0) / 1024 if gpu.get("vram_free") else 0,
            "python_version": stats.get("system", {}).get("python_version", "unknown"),
        }
    except Exception as exc:
        return {"comfyui_reachable": False, "error": str(exc)}


def main():
    print("=" * 60)
    print("Wave 1-D: Auto Visual Asset Discovery Verification")
    print("=" * 60)

    report = {}

    # Connect to ComfyUI
    client = ComfyApiClient("http://127.0.0.1:8188")

    # 1. Runtime compatibility
    print("\n[1/5] Checking runtime compatibility...")
    report["runtime"] = check_runtime_compatibility(client)
    rt = report["runtime"]
    if rt.get("comfyui_reachable"):
        print(f"  GPU: {rt.get('gpu_name')}")
        print(f"  VRAM free: {rt.get('vram_free_mb', 0):.0f} MB")
    else:
        print(f"  ComfyUI not reachable: {rt.get('error', '?')}")

    # 2. Nodes
    print("\n[2/5] Checking available nodes...")
    report["nodes"] = check_nodes(client)
    nd = report["nodes"]
    print(f"  Total nodes: {nd.get('total', '?')}")
    print(f"  Has LoadImage: {nd.get('has_load_image', False)}")
    print(f"  Has KSampler: {nd.get('has_k_sampler', False)}")
    print(f"  Has SaveVideo: {nd.get('has_save_video', False)}")

    # 3. Qwen model
    print("\n[3/5] Checking Qwen model availability...")
    report["qwen"] = check_qwen_model(client)
    qw = report["qwen"]
    print(f"  Available: {qw.get('available', False)}")
    if qw.get("nodes"):
        print(f"  Nodes: {qw['nodes'][:5]}")

    # 4. H3 model
    print("\n[4/5] Checking H3/FL2VA model availability...")
    report["h3"] = check_h3_model(client)
    h3 = report["h3"]
    print(f"  Available: {h3.get('available', False)}")
    if h3.get("nodes"):
        print(f"  Nodes: {h3['nodes'][:5]}")

    # 5. Workflow API format
    print("\n[5/5] Verifying Workflow API format detection...")
    registry_dir = Path(__file__).resolve().parent.parent / "src" / "lfo" / "registry"
    report["workflow_formats"] = check_workflow_api_format(registry_dir)
    for name, info in report["workflow_formats"].items():
        fmt = "API" if info.get("is_api_format") else "UI/unknown"
        print(f"  {name}: {fmt} ({info.get('node_count', '?')} nodes)")

    # 6. H3/Qwen switch feasibility
    report["switch_feasibility"] = {
        "h3_available": report["h3"].get("available", False),
        "qwen_available": report["qwen"].get("available", False),
        "switch_possible": report["h3"].get("available", False) and report["qwen"].get("available", False),
        "note": "Switch requires model_swap_strategy from ResourcePolicy",
    }

    print(f"\n{'='*60}")
    print("Switch feasibility:")
    print(f"  H3 available: {report['switch_feasibility']['h3_available']}")
    print(f"  Qwen available: {report['switch_feasibility']['qwen_available']}")
    print(f"  Switch possible: {report['switch_feasibility']['switch_possible']}")
    print(f"{'='*60}")

    # Output JSON report
    print("\n--- JSON REPORT ---")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    return report


if __name__ == "__main__":
    main()

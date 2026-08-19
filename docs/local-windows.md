# Local Windows ComfyUI profile

This document contains machine-specific details for the local LFO + ComfyUI
environment. Update it when the local installation, model location, or machine
profile changes; keep those details out of the always-loaded project rules.

## ComfyUI installation

- Local ComfyUI: `D:\ComfyUI\Comfy-Desktop\ComfyUI\ComfyUI`
- ComfyUI Desktop version: 0.30.2 (Electron + bundled Python 3.12)
- `comfy-cli`: 1.13.0, with the default workspace set to the path above
- Service URL: `http://127.0.0.1:8188`
- Target GPU path: RTX 5080 16GB, using the fl2va int8 path
- Models directory: `D:\ComfyUI\Comfy-Desktop\ComfyUI\ComfyUI\models\`

There is no separate `D:\cyuiEnv\models\` model directory for this setup.

## H3 model set

- `minimax_h3_fl2va_pruned_int8_convrot.safetensors`
- `minimax_h3_ref2va_pruned_int8_convrot.safetensors`
- `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`
- `minimax_h3_video_vae_fp16.safetensors`
- `minimax_h3_audio_vae_fp32.safetensors`

## LFO machine profile

The machine profile is stored at:

`%APPDATA%\LFO\machines\local-windows.json`

Re-run setup after changing the ComfyUI path or reinstalling ComfyUI:

```powershell
python -m lfo.cli.main setup --machine-id local-windows
```

Before a live ComfyUI job, run:

```powershell
python -m lfo.cli.main doctor --machine-id local-windows
python -m lfo.cli.main preflight --machine-id local-windows
```

Run live Package E2E only when the task requires provider integration:

```powershell
python scripts/live_e2e_execution_package.py <execution-package.json> --approve
```

---
name: comfy-video-executor
description: Execute a confirmed video canvas snapshot through local ComfyUI/comfy-cli using the bundled H3 workflows. Use for the final provider adapter after the prompt, assets, mode, and parameters have already been decided; do not use it to write prompts, plan stories, or choose a creative model.
---

# Comfy video executor

先遵守[项目共享生产规则](../../../docs/ai-system-prompt.md)。本 Skill 只消费已经冻结的 Canvas 视频快照，完成一个有边界的执行单元；它不创建监控代理、审批层或第二套提交记录。

This project-only Skill is the script adapter invoked by the Canvas service for a confirmed video run. It converts that run's immutable snapshot into a temporary ComfyUI API workflow, submits it once to a local ComfyUI instance, waits for the terminal result, and copies the single video into the run output directory supplied by the service.

The creative boundary is already closed when this Skill is invoked. Preserve the supplied `prompt` byte-for-byte in the generated request. Do not rewrite, improve, translate, add reference labels, select a different model, or fall back to another provider. Do not modify the Canvas database, create a parallel execution record, or invoke this adapter outside the confirmed Canvas run.

Read [capability.json](capability.json) before rendering the video form. It is the capability source for the canvas: the common fields are `duration`, `aspect_ratio`, and `megapixels`; Comfy-specific fields belong under the snapshot's Comfy options. Values embedded in workflow templates are examples only. A missing required field must be reported to the caller instead of being silently filled from a template.

## Confirmed snapshot

The entry script accepts a JSON object with this shape:

```json
{
  "request_id": "the Canvas run.request_id injected by the service",
  "node_id": "video-1",
  "node_type": "video",
  "provider": "comfy",
  "model": "h3",
  "mode": "fl2v",
  "prompt": "The already approved H3 prompt",
  "parameters": {
    "duration": 5,
    "aspect_ratio": "9:16",
    "megapixels": 0.4,
    "sampler_profile": "native",
    "steps": 20,
    "seed": 123
  },
  "inputs": {
    "first_frame": {"path": "C:/media/first.png", "kind": "image"},
    "last_frame": {"path": "C:/media/last.png", "kind": "image"},
    "reference_images": [],
    "reference_videos": [],
    "reference_audios": []
  }
}
```

`parameters.options.comfy` and `parameters.comfy` are also accepted for the provider-specific fields. The adapter does not merge conflicting copies silently. The four modes have explicit input rules:

- `t2v` accepts no media inputs.
- `i2v` requires exactly one `first_frame` image.
- `fl2v` requires exactly one `first_frame` image and one `last_frame` image.
- `r2v` requires at least one typed reference in `reference_images`, `reference_videos`, or `reference_audios`; its fixed reference slots are preserved and are never inferred from prompt text.

The first three parameters are required for H3 execution. `sampler_profile` and `steps` are also required because the canvas must record the chosen Comfy sampling route instead of inheriting the 0.4 MP or 8-step example values embedded in a template. `native` accepts steps of at least 8; `vdn_turbo` accepts exactly 8. `seed`, `fps`, and `reference_image_size` are optional when supported by the selected mode.

## Canvas service invocation

The Canvas service is the production caller. After confirmation freezes a run, the service writes the snapshot, injects that run's `request_id`, and invokes the entrypoint with the run's existing output directory:

```text
python scripts/execute.py --input confirmed-snapshot.json --output-dir <existing-run-output>
```

This command documents the service's internal invocation and may be used only for scoped adapter debugging against an already frozen run. Running it manually does not create authorization, does not register a Canvas result, and must never be used to bypass the Canvas production route.

The script reads existing safe Comfy settings when available: an optional `--config` JSON, the LFO global/machine config under `%APPDATA%/LFO`, and the environment values `LFO_COMFY_BASE_URL`, `LFO_COMFY_CLI`, `LFO_COMFY_TIMEOUT`, `LFO_COMFY_OUTPUT_ROOT`, and `LFO_FFPROBE`. Explicit CLI flags override the corresponding Comfy configuration values; `LFO_FFPROBE` selects the media-probe executable. Only the URL, Comfy executable, timeout, output-root, and media-probe executable are read; credentials and unrelated settings are never printed.

The default endpoint is `http://127.0.0.1:8188`. Before submission, the script reads ComfyUI's `/object_info` endpoint and rejects missing custom nodes or server-advertised model/enum values. Server file-list choices for dynamic `LoadImage`, `LoadVideo`, and `LoadAudio` inputs are intentionally excluded from this model preflight because confirmed media is uploaded immediately before execution. Uploaded media uses a UUID-prefixed filename in ComfyUI's input root with overwrite disabled, and the workflow token is taken from the upload response's `name`, `subfolder`, and `type` values so the official CLI can enumerate the file. The CLI invocation then uses the official `comfy run --wait --json` command. Its stdout is consumed line-by-line while the process is running, so a queued `prompt_id` is emitted as soon as the official CLI reports it. The temporary workflow is deleted when the process exits. Uploaded references use ComfyUI's local HTTP upload endpoint. A successful run emits progress JSON events and ends with exactly one result line:

```json
{"status":"succeeded","outputs":[{"path":"C:/.../video.mp4","kind":"video","name":"video.mp4"}],"provider_task_id":"..."}
```

The copied result is checked with the project's low-level ffprobe media helper. A non-empty MP4 extension alone is insufficient: the file must have a readable video stream, positive dimensions, a codec, and positive duration. Timeout, malformed output, unavailable assets, validation errors, corrupted output, and non-terminal Comfy failures exit non-zero. If the provider has explicitly reported a generation failure, the final event has `status: "failed"`; if submission or remote completion cannot be proven, it has `status: "unknown"` and preserves any early `provider_task_id`. The caller owns retry policy, QC, database recording, and any subsequent provider choice.

Before submission, the adapter uses the Canvas Comfy `lfo.comfy.admission.VideoSubmissionGuard`. Its machine-wide OS lock covers submission and the full synchronous wait through terminal collection, so another local video run cannot enter while the current Comfy run is active. A persistent submission receipt is stored under the configured application data directory (or `LFO_VIDEO_STATE`) for uncertainty reconciliation; it is not a second request database. The Canvas run's injected `request_id` is used for that receipt. If a submission is uncertain, inspect it with `python -m lfo.comfy.admission`; `--reconcile REQUEST_ID` reads only the original Comfy `/history` and never resubmits. Do not bypass or reimplement this guard.

Technical success does not by itself mean content acceptance. For story production or an explicitly required content review, the caller checks the actual file against the agreed criteria and records `ACCEPT`, `REJECT`, or `INCONCLUSIVE` with observable visual and audio evidence. Ordinary canvas components require technical completion only. The script does not perform semantic review. A real tail frame is extracted from the adopted version only after `ACCEPT` when the next shot needs it. Follow the shared production rules for review and handoff.

The `templates/` files are this Skill's bundled H3 API resources. They provide the supported graph shapes that this Canvas adapter fills from the frozen run snapshot.

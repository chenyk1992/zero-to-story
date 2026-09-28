# Comfy adapter 输入与执行协议

仅在维护、诊断 adapter 或需要核对内部字段时读取。生产入口见 [SKILL.md](../SKILL.md)，能力来源见 [capability.json](../capability.json)。

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
- `r2v` requires at least one typed reference in `reference_images`, `reference_videos`, or `reference_audios`; its fixed reference slots are preserved and are never inferred from prompt text. It optionally accepts `first_frame`, encoded through `MiniMaxH3AddGuide` at `frame_idx=0` after reference conditioning. This is a temporal image anchor, separate from ordinary references; it does not renumber their slots. When `parameters.options.comfy.frame_zero_video_guide` is `true`, the first `reference_video` is consumed as a short multi-frame guide at `frame_idx=0`, together with its extracted soundtrack, instead of as a semantic `<Video N>` reference. The guide must contain a valid H3 clip length such as 22 frames; the generated result includes that overlap and the accepted version must be trimmed before concatenation. Voice references remain on the R2V audio-reference route, never on AddGuide's soundtrack input. `last_frame` is not supported in this combined route. VAE resizing/encoding means the decoded first frame is not promised to be pixel-identical to the source; inspect the actual opening and transition.

The first three parameters are required for H3 execution. `sampler_profile` and `steps` are also required because the canvas must record the chosen Comfy sampling route instead of inheriting the 0.4 MP or 8-step example values embedded in a template. `native` accepts steps of at least 8; `vdn_turbo` accepts exactly 8. `seed`, `fps`, and `reference_image_size` are optional when supported by the selected mode.

## Canvas service invocation

The Canvas service is the production caller. After confirmation freezes a run, the service writes the snapshot, injects that run's `request_id`, and invokes the entrypoint with the run's existing output directory:

```text
python scripts/execute.py --input confirmed-snapshot.json --output-dir <existing-run-output>
```

This command documents the service's internal invocation and may be used only for scoped adapter debugging against an already frozen run. Running it manually does not create authorization, does not register a Canvas result, and must never be used to bypass the Canvas production route.

The Canvas service reads project-local `.lfo/comfy-mcp.json`, or the `LFO_COMFY_MCP_URL`, `LFO_COMFY_MCP_COMMAND`, `LFO_COMFY_MCP_COMFY_BIN`, `LFO_COMFY_MCP_TIMEOUT`, and `LFO_COMFY_MCP_MODEL_VENV` environment settings. The project does not read `.codex/config.toml`. `LFO_FFPROBE` selects the media-probe executable. The configured CLI binary is passed to the official MCP server as `COMFY_BIN`; project code never invokes it directly.

The default endpoint is `http://127.0.0.1:8188` and must remain a local loopback target. Before submission, the adapter calls MCP `nodes` and `validate_workflow` and rejects missing nodes or invalid enum values. Dynamic `LoadImage`, `LoadVideo`, and `LoadAudio` file-list choices are excluded from the supplemental check because the frozen media is uploaded immediately before validation. Each MCP `upload_file(overwrite=False)` call uses a UUID-prefixed source copy; the workflow token comes from its `cloud_name`, `subfolder`, and `type` receipt. The guard writes submission intent before one `run_workflow(wait=False)` call, then persists the returned `prompt_id`. The same session polls `job(action="status")` and calls `fetch_outputs` after a proven completed state. A successful run emits progress JSON events and ends with exactly one result line:

```json
{"status":"succeeded","outputs":[{"path":"C:/.../video.mp4","kind":"video","name":"video.mp4"}],"provider_task_id":"..."}
```

The copied result is checked with the project's low-level ffprobe media helper. A non-empty MP4 extension alone is insufficient: the file must have a readable video stream, positive dimensions, a codec, and positive duration. Timeout, malformed output, unavailable assets, validation errors, corrupted output, and non-terminal Comfy failures exit non-zero. If the provider has explicitly reported a generation failure, the final event has `status: "failed"`; if submission or remote completion cannot be proven, it has `status: "unknown"` and preserves any early `provider_task_id`. The caller owns retry policy, QC, database recording, and any subsequent provider choice.

Before submission, the adapter uses the Canvas Comfy `lfo.comfy.admission.VideoSubmissionGuard`. Its machine-wide OS lock covers submission and the wait for a proven terminal state, so another local run cannot enter while this one is active. A persistent submission receipt is stored under the configured application data directory (or `LFO_VIDEO_STATE`) for uncertainty reconciliation; it is not a second request database. The Canvas run's injected `request_id` is used for that receipt. If a submission is uncertain, inspect it with `python -m lfo.comfy.admission`; `--reconcile REQUEST_ID` calls MCP `job` for the original task and never resubmits. Do not bypass or reimplement this guard.

Technical success does not by itself mean content acceptance. For story production or an explicitly required content review, the caller checks the actual file against the agreed criteria and records `ACCEPT`, `REJECT`, or `INCONCLUSIVE` with observable visual and audio evidence. Ordinary canvas components require technical completion only. The script does not perform semantic review. A real tail frame is extracted from the adopted version only after `ACCEPT` when the next shot needs it. Follow the shared production rules for review and handoff.

The `templates/` files are this Skill's bundled H3 API resources. They provide the supported graph shapes that this Canvas adapter fills from the frozen run snapshot.

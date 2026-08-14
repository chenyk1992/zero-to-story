# Video Execution Package v1

`lfo.video-execution.v1` is the only public contract between a creative Skill and LFO.
The Skill decides the story, visual language, panels, prompts, references and timing. LFO
imports approved assets, selects an execution backend, generates clips, performs media
processing and exports a reproducible result.

## Top-level fields

| Field | Required | Meaning |
| --- | --- | --- |
| `schema` | yes | Must be `lfo.video-execution.v1`. |
| `package_id` | yes | Stable project/package identifier. |
| `revision` | yes | Positive integer; increase whenever an execution-affecting field changes. |
| `project` | yes | Routing metadata: required stable `project_id`, display `title`, and optional `locale`. |
| `assets` | no | Files imported into LFO's content-addressed store. |
| `clips` | no | Ordered, independently retryable video-generation units. |
| `output` | no | Final resolution, codecs, subtitles and destination policy. |
| `approval` | no | Upstream approval declaration. |
| `timeline` | no | Package-level editorial metadata. |
| `extensions` | no | Namespaced producer-specific data; generic execution cannot depend on it. |

## Assets

Each asset has a unique `asset_key`, a `media_type`, a package-relative `source.uri`,
provenance and a review policy. Source paths are read only during import; execution uses
the immutable imported blob. Include `source.sha256` when an upstream system already
knows the content hash.

Supported media types are `image`, `video`, `audio`, `subtitle`, and `document`.

## Clips

Each clip contains:

- stable `clip_id`, integer `sequence`, and positive `duration_ms`;
- `generation.operation` and a complete provider-ready `prompt`;
- optional seed, negative prompt and requirements (`width`, `height`, `fps`, aspect ratio,
  native audio);
- explicitly ordered references with required/optional policy, priority, placement and
  unsupported behavior;
- native/external audio policy, subtitle cues, and other clip dependencies.

Known operations are `video.text_to_video`, `video.image_to_video`,
`video.reference_to_video`, and `video.first_last_frame`. Operation strings remain open so
new backends can add capabilities without revising the package schema.

Dependencies must name existing clips and must form an acyclic graph. A required reference
must resolve to an imported asset revision. Optional references may be dropped only when
their binding says `on_unsupported: drop`.

## Approval and revision rules

Execution requires explicit approval. Asset bytes, binding metadata, prompts, timing,
backend selection or output policy changes invalidate the affected snapshot. Do not mutate
an approved package in place: write a new positive revision.

Validate a package before execution:

```text
python -m lfo.cli.main validate path/to/execution-package.json
python -m lfo.cli.main plan path/to/execution-package.json
```

The machine-readable schema is `src/lfo/contracts/schemas/video-execution-v1.schema.json`.

`project.project_id` is the single routing key for generated media and must be one safe
path component. `output.directory` is only a logical publication/version directory name;
it is never an absolute path. New runs use this layout:

```text
workspace/projects/<project_id>/
├── outputs/<run_id>/clips/<clip_id>/   # provider copy, normalized, mixed, subtitles
├── outputs/<run_id>/global/             # timeline and global subtitles
└── final/<output.directory>/            # final video, sidecar and manifest
```

The Runtime does not write the legacy `workspace/runs` or `workspace/exports` directories.
Provider caches (for example ComfyUI's own output directory) are source caches only; the
managed copy under the project tree is the durable artifact recorded by LFO.

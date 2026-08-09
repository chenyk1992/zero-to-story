# Creative Skill adapter guide

A creative Skill should finish its own approval workflow, write one
`VideoExecutionPackage`, then hand execution to LFO. It must not call ComfyUI, choose node
IDs, poll provider jobs, run FFmpeg, or invent LFO database records.

## Adapter sequence

1. Finish story, character, panel and video-prompt approval in the Skill.
2. Freeze generated reference images and other media as local files.
3. Create assets with complete provenance and review declarations.
4. Convert every executable panel/clip to one `ClipSpec`.
5. Express continuity as explicit asset references or clip dependencies.
6. Write the package with `VideoPackageBuilder`.
7. Run `lfo validate`, then `lfo plan`; show errors or backend decisions to the user.
8. Run `lfo execute --approve` only after user approval.

Use the builder instead of assembling nested dictionaries:

```python
from lfo.contracts import VideoPackageBuilder

builder = VideoPackageBuilder(package_id="promo-001", title="Launch film")
builder.add_asset(
    asset_key="hero.sheet",
    media_type="image",
    uri="assets/hero.png",
    producer="my-creative-skill",
    operation="image.generate",
)
builder.add_clip(
    clip_id="clip-001",
    sequence=1,
    duration_ms=5000,
    operation="video.reference_to_video",
    prompt="A complete production-ready video prompt...",
    references=[{
        "reference_id": "hero-primary",
        "asset_key": "hero.sheet",
        "semantic_usage": "subject.identity",
        "binding": {"required": True, "priority": 100},
    }],
)
builder.write("execution-package.json")
```

Adapter tests should cover: schema validation, deterministic output, relative asset paths,
required reference failures, forward dependencies, and a package round trip. Put genre- or
platform-specific choices in the Skill; keep the adapter a small deterministic transform.

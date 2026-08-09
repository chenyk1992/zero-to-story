# Backend manifest development guide

A backend manifest is the complete declaration of an execution implementation. Generic
planning code must not contain provider-specific frame grids, reference limits, model names
or node identifiers.

Declare:

- stable `backend_id`, breaking `revision`, and exact workflow hash;
- supported operations and accepted reference media types;
- reference count, duration, frame, resolution and FPS constraints;
- native-audio and seed behavior plus reproducibility claim;
- required models and custom nodes;
- output media signature and provider-specific extensions.

Registration rejects conflicting hashes for the same backend and revision. Selection must
fail with structured reasons when constraints are not satisfied; it must never silently
resize, discard required references or replace an operation.

For ComfyUI, keep workflow JSON in `src/lfo/registry/`, give every mutable input a stable
`_meta.title`, and bind by title plus class type. Node-number-only binding is not a production
contract. A new workflow revision must pass static registration, live node/model preflight,
and a smoke generation before it is marked production-ready.

Implement provider execution through `TaskHandler`. Return a durable local file path and
content hash on success, a provider job ID for recovery, and distinguish retryable transport
errors from terminal validation/provider errors.

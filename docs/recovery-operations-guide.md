# Recovery and operations guide

LFO records package revisions, immutable run snapshots, tasks, dependencies, attempts,
leases, artifacts and transition history in SQLite. Re-running a command must use the same
database and content-addressed asset store.

## Before execution

Run machine setup after a ComfyUI path change, then run `doctor` and `preflight`. Verify disk
space, bundled workflow hashes, required models/nodes, FFmpeg/ffprobe, input asset hashes and
the user's approval.

## Failure handling

- `FAILED_RETRYABLE`: correct transient connectivity, disk or provider conditions, then use
  `retry`. The previous attempt remains in the journal.
- `FAILED_TERMINAL`: fix the package, asset or backend compatibility issue and create a new
  package revision.
- Expired `RUNNING`: recovery queries the provider job ID. Completed jobs are collected;
  running jobs remain attached; definite provider failures are recorded. An unavailable or
  ambiguous provider returns `UNKNOWN` and must not submit a duplicate.
- QC failure is a failed task, never a successful artifact.

Cancellation prevents new work; it does not erase attempts or assets. Preserve the database,
CAS and provider output directory during incident analysis. Record the run ID, task ID,
attempt ID, provider job ID, package/content hashes and the relevant transition journal.

## Backup and cleanup

Back up the SQLite database together with the CAS. Do not delete CAS blobs solely because a
source file disappeared. Garbage collection is safe only after checking asset revisions,
artifacts, lineage and exports. Final exports are written atomically and include a provenance
manifest so results can be audited independently.

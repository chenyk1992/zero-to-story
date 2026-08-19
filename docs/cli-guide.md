# LFO command-line guide

Install the project once with `python -m pip install -e ".[dev]"`. Runtime state defaults to the
workspace database and survives separate command invocations.

```text
python -m lfo.cli.main validate execution-package.json
python -m lfo.cli.main plan execution-package.json
python -m lfo.cli.main execute execution-package.json --approve
python -m lfo.cli.main status RUN_ID
python -m lfo.cli.main retry RUN_ID
python -m lfo.cli.main cancel RUN_ID
python -m lfo.cli.main review RUN_ID TARGET approved
python -m lfo.cli.main export RUN_ID
```

`validate` checks the contract without generation. `plan` imports or resolves assets and
shows immutable backend decisions. `execute` persists the package, snapshot, DAG, attempts,
artifacts and transitions. `status` and `retry` read the same SQLite database, so they work
after the original process exits.

Every package must declare `project.project_id`. The plan and run responses expose the
resolved output layout. New media is written only under
`workspace/projects/<project_id>/outputs/<run_id>/`; the final export is published under
`workspace/projects/<project_id>/final/<output.directory>/`. The provider's ComfyUI cache is
kept separately and is copied into the managed project path before it is recorded as an
artifact.

Use `--db` when a caller needs an isolated runtime database. Run `setup`, `doctor`, and
`preflight` for the configured `local-windows` machine before a live ComfyUI job. A run ID,
package revision and failing task ID should always accompany an operational support report.

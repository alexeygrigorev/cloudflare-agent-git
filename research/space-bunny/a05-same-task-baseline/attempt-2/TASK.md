# Task (identical for every attempt — do not read other attempts)

Build a validator for this project's coordination task registry.

## Input

`coordination/TASKS.json` in the repository root. It is a single JSON object:

    { "schema_version": 1, "updated_at": "<ISO8601>", "tasks": [ <row>, ... ] }

Each `<row>` is expected to carry exactly these keys:

    id, team_id, owner_tag, status, updated_at,
    evidence_paths, blocked_on, next_action, acceptance, assignment_ack

`id` is a string. `team_id`, `owner_tag`, `status` are strings.
`updated_at` is an ISO8601 timestamp string.
`evidence_paths`, `blocked_on` are arrays of strings.
`next_action`, `acceptance`, `assignment_ack` are strings.

There is also `coordination/TEAM-REGISTRY.json`, which maps team ids to a
`head_tag`. Several agents share one working tree and edit this registry
concurrently, so your validator will be run against realistic data that other
agents are actively changing.

## What to build

A command-line tool (Python 3, standard library only, no network) that reads
`TASKS.json` and reports problems. Requirements:

1. **Schema conformance.** Every row must have exactly the expected key set.
   Report a missing key and an unexpected key as distinct problems, naming the
   task `id` (or the row index when `id` is absent or not a string).
2. **Type conformance.** Each field must have the type described above. A
   string field given a number, a list field given a string, and a missing
   field are three different problems.
3. **Valid status values.** `status` must be one of a fixed allowed set. Values
   outside it are errors. The allowed set is a property of this project, not
   something to invent per row.
4. **File-level consistency.** The top-level `updated_at` must be at least as
   new as every row's `updated_at`. Flag rows that are newer than the file.
5. **Cross-file ownership.** For each row whose `team_id` appears in
   `TEAM-REGISTRY.json`, the row's `owner_tag` must equal that team's
   `head_tag`. Rows whose `team_id` is absent from the registry are not an
   ownership error.
6. **Evidence paths.** Every path in `evidence_paths` should exist on disk.
   Report non-existent paths. Do not require paths to be inside any
   particular directory.

## Behaviour

- Exit `0` when there are no problems; non-zero when there is at least one.
- Every problem must be reported; do not stop at the first.
- Each problem should identify the task and the field so a human can fix it
  without re-reading the whole file.
- Malformed JSON is an error, not a crash with a traceback.

## Deliverable

- The tool, plus a short `README.md` in your attempt directory stating how to
  run it and what it checks.
- Tests that run the tool against synthetic inputs you construct. Your tests
  must not depend on the live `coordination/TASKS.json`, because that file
  changes while you work.

## Constraints

- Python 3 standard library only. No third-party packages, no network access.
- Your attempt directory is yours alone. Do not read, modify, or depend on any
  other attempt directory; they do not exist for you.
- Do not modify `coordination/TASKS.json` or `TEAM-REGISTRY.json`.
- Do not run the tool against the live registry as your acceptance check; the
  live data is in flux. Use synthetic fixtures.

## How this will be judged

An independent test suite written by someone else, from this specification
only, will be run against your tool. It was written before your attempt
finished and you have not seen it. Your tool is judged on whether it detects
the specified problems and reports them accurately — not on style, and not on
matching any particular implementation.

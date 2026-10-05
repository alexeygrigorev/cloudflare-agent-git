# TASKS.json validator

A command-line validator for this project's coordination task registry
(`coordination/TASKS.json`), per `TASK.md`. Python 3 standard library only;
no third-party packages; no network access.

## How to run

```sh
# From the repository root, using the default paths
python3 validate_tasks.py

# With explicit paths
python3 validate_tasks.py path/to/TASKS.json path/to/TEAM-REGISTRY.json

# Equivalent flag form
python3 validate_tasks.py --tasks path/to/TASKS.json --registry path/to/TEAM-REGISTRY.json

# Base directory for resolving RELATIVE evidence paths (default: cwd)
python3 validate_tasks.py --root /path/to/repo
```

Defaults: `coordination/TASKS.json` and `coordination/TEAM-REGISTRY.json`
relative to the current working directory. Absolute evidence paths are
checked as-is; relative ones resolve against `--root` (or the cwd).

## What it checks

1. **Schema conformance** — every task row carries exactly the expected key
   set (`id`, `team_id`, `owner_tag`, `status`, `updated_at`,
   `evidence_paths`, `blocked_on`, `next_action`, `acceptance`,
   `assignment_ack`). Missing keys and unexpected keys are reported as
   distinct problems, one per key. Rows are identified by `id` when it is a
   string, otherwise by row index (`tasks[3]`).
2. **Type conformance** — `id`/`team_id`/`owner_tag`/`status` are strings;
   `updated_at` is an ISO8601 timestamp string; `evidence_paths` and
   `blocked_on` are arrays of strings; `next_action`, `acceptance` and
   `assignment_ack` are strings. A wrong-typed present field and a missing
   field are reported as separate problems; non-string list elements are
   reported per element.
3. **Valid status values** — `status` must be one of the project's fixed
   vocabulary from `coordination/OPERATING-MODEL.md` ("Statuses: queued,
   ready, running, review, blocked, done, cancelled."). Anything else
   (including different casing) is an error.
4. **File-level consistency** — the top-level `updated_at` must be at least
   as new as every row's `updated_at`; rows newer than the file are flagged.
   Naive timestamps are compared as UTC; `Z` suffixes are accepted.
5. **Cross-file ownership** — for each row whose `team_id` appears in
   `TEAM-REGISTRY.json` (its `teams[].id` / `teams[].head_tag`), the row's
   `owner_tag` must equal that team's `head_tag`. Teams absent from the
   registry are not an ownership error. If the registry file does not exist,
   this check is skipped with a note; a registry that exists but contains
   malformed JSON is an error.
6. **Evidence paths** — every string entry in `evidence_paths` must exist on
   disk (file or directory, anywhere on disk).

## Behaviour

- Every problem is reported (one `PROBLEM ...` line per problem, naming the
  task and the field), followed by a count. Nothing stops at the first.
- Exit codes: `0` = no problems; `1` = at least one problem;
  `2` = the input could not be read/parsed at all (missing file, malformed
  JSON, top-level value not an object) — reported as a clean error message,
  never a traceback.
- Problem lines go to stdout, so the tool can be used in pipelines:
  `python3 validate_tasks.py | grep PROBLEM`.

## Tests

`test_validate_tasks.py` (stdlib `unittest`) builds synthetic fixtures in
temporary directories and runs the tool as a subprocess. It never reads the
live `coordination/TASKS.json` or `TEAM-REGISTRY.json`.

```sh
python3 test_validate_tasks.py
```

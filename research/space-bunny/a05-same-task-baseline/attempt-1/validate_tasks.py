#!/usr/bin/env python3
"""Validate coordination/TASKS.json against this project's task-registry rules.

Checks row schema and types, allowed status values, file-level timestamp
consistency, cross-file ownership against TEAM-REGISTRY.json, and evidence
path existence. Python 3 standard library only; no network access.

See README.md in this directory for full usage and the exact rule set.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_KEYS = (
    "id",
    "team_id",
    "owner_tag",
    "status",
    "updated_at",
    "evidence_paths",
    "blocked_on",
    "next_action",
    "acceptance",
    "assignment_ack",
)

STRING_FIELDS = (
    "id",
    "team_id",
    "owner_tag",
    "status",
    "updated_at",
    "next_action",
    "acceptance",
    "assignment_ack",
)

ARRAY_FIELDS = ("evidence_paths", "blocked_on")

# Project vocabulary, fixed in coordination/OPERATING-MODEL.md:
# "Statuses: queued, ready, running, review, blocked, done, cancelled."
DEFAULT_STATUSES = (
    "queued",
    "ready",
    "running",
    "review",
    "blocked",
    "done",
    "cancelled",
)

DEFAULT_TASKS_PATH = Path("coordination/TASKS.json")
DEFAULT_REGISTRY_PATH = Path("coordination/TEAM-REGISTRY.json")

EXIT_OK = 0
EXIT_PROBLEMS = 1
EXIT_INPUT_ERROR = 2


def json_type_name(value):
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "number"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return type(value).__name__


def parse_iso8601(value):
    """Return a datetime for an ISO8601 string, or None if unparseable."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text[-1] in "Zz":
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def as_comparable(dt):
    """Make naive and aware datetimes mutually comparable (naive means UTC)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def row_label(index, row):
    """Identify a row by its id when that is a string, else by row index."""
    base = "tasks[%d]" % index
    row_id = row.get("id") if isinstance(row, dict) else None
    if isinstance(row_id, str):
        return "%s (id=%r)" % (base, row_id)
    return base


def build_registry_map(registry_data):
    """Map team_id -> head_tag from any of the registry layouts in use.

    Accepts the live format ({"teams": [{"id": ..., "head_tag": ...}, ...]}),
    a bare list of such team objects, a dict mapping team id to an object with
    a "head_tag", or a dict mapping team id directly to the head_tag string.
    """
    mapping = {}
    if isinstance(registry_data, dict) and "teams" in registry_data:
        registry_data = registry_data["teams"]
    if isinstance(registry_data, list):
        for entry in registry_data:
            if not isinstance(entry, dict):
                continue
            team_id = entry.get("id")
            head_tag = entry.get("head_tag")
            if isinstance(team_id, str) and isinstance(head_tag, str):
                mapping[team_id] = head_tag
    elif isinstance(registry_data, dict):
        for team_id, entry in registry_data.items():
            if isinstance(entry, str):
                mapping[str(team_id)] = entry
            elif isinstance(entry, dict):
                head_tag = entry.get("head_tag")
                if isinstance(head_tag, str):
                    mapping[str(team_id)] = head_tag
    return mapping


def path_exists(raw_path, base_dirs):
    """True if the path exists as given, or relative to any known base dir.

    Relative evidence paths are checked against the working directory, the
    directory holding TASKS.json, and its parent (the repository root in the
    live layout), plus any extra --base directories.
    """
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate.exists()
    for base in base_dirs:
        if (base / candidate).exists():
            return True
    return False


def validate_tasks_doc(data, registry_map, statuses, base_dirs):
    """Return the list of problem messages for a parsed TASKS.json document."""
    problems = []

    def problem(message):
        problems.append(message)

    if not isinstance(data, dict):
        problem(
            "file: top-level JSON value must be an object, got %s"
            % json_type_name(data)
        )
        return problems

    file_updated_at = None
    if "updated_at" not in data:
        problem("file: missing top-level key 'updated_at'")
    elif not isinstance(data["updated_at"], str):
        problem(
            "file: top-level field 'updated_at' must be a string, got %s (%r)"
            % (json_type_name(data["updated_at"]), data["updated_at"])
        )
    else:
        file_updated_at = parse_iso8601(data["updated_at"])
        if file_updated_at is None:
            problem(
                "file: top-level field 'updated_at' (%r) is not a valid "
                "ISO8601 timestamp" % (data["updated_at"],)
            )

    if "schema_version" in data and data["schema_version"] != 1:
        problem(
            "file: unsupported schema_version %r (expected 1)"
            % (data["schema_version"],)
        )

    tasks = None
    if "tasks" not in data:
        problem("file: missing top-level key 'tasks'")
    elif not isinstance(data["tasks"], list):
        problem(
            "file: top-level key 'tasks' must be an array, got %s"
            % json_type_name(data["tasks"])
        )
    else:
        tasks = data["tasks"]

    if tasks is None:
        return problems

    expected_keys = set(EXPECTED_KEYS)

    for index, row in enumerate(tasks):
        if not isinstance(row, dict):
            problem(
                "tasks[%d]: row must be a JSON object, got %s (%r)"
                % (index, json_type_name(row), row)
            )
            continue

        ident = row_label(index, row)

        present_keys = set(row.keys())
        for key in sorted(expected_keys - present_keys):
            problem("%s: missing key %r" % (ident, key))
        for key in sorted(present_keys - expected_keys):
            problem("%s: unexpected key %r" % (ident, key))

        for field in STRING_FIELDS:
            if field in row and not isinstance(row[field], str):
                problem(
                    "%s: field %r must be a string, got %s (%r)"
                    % (ident, field, json_type_name(row[field]), row[field])
                )

        for field in ARRAY_FIELDS:
            if field not in row:
                continue
            value = row[field]
            if not isinstance(value, list):
                problem(
                    "%s: field %r must be an array of strings, got %s (%r)"
                    % (ident, field, json_type_name(value), value)
                )
                continue
            for element_index, element in enumerate(value):
                if not isinstance(element, str):
                    problem(
                        "%s: field '%s[%d]' must be a string, got %s (%r)"
                        % (
                            ident,
                            field,
                            element_index,
                            json_type_name(element),
                            element,
                        )
                    )

        status = row.get("status")
        if isinstance(status, str) and status not in statuses:
            problem(
                "%s: field 'status' has invalid value %r (allowed: %s)"
                % (ident, status, ", ".join(sorted(statuses)))
            )

        row_updated_at = row.get("updated_at")
        if isinstance(row_updated_at, str):
            parsed = parse_iso8601(row_updated_at)
            if parsed is None:
                problem(
                    "%s: field 'updated_at' (%r) is not a valid ISO8601 "
                    "timestamp" % (ident, row_updated_at)
                )
            elif file_updated_at is not None:
                if as_comparable(parsed) > as_comparable(file_updated_at):
                    problem(
                        "%s: field 'updated_at' (%r) is newer than the "
                        "top-level 'updated_at' (%r)"
                        % (ident, row_updated_at, data["updated_at"])
                    )

        team_id = row.get("team_id")
        owner_tag = row.get("owner_tag")
        if (
            isinstance(team_id, str)
            and isinstance(owner_tag, str)
            and team_id in registry_map
        ):
            head_tag = registry_map[team_id]
            if owner_tag != head_tag:
                problem(
                    "%s: field 'owner_tag' (%r) does not match head_tag "
                    "(%r) for team_id %r from TEAM-REGISTRY.json"
                    % (ident, owner_tag, head_tag, team_id)
                )

        evidence_paths = row.get("evidence_paths")
        if isinstance(evidence_paths, list):
            for element_index, element in enumerate(evidence_paths):
                if isinstance(element, str) and not path_exists(
                    element, base_dirs
                ):
                    problem(
                        "%s: field 'evidence_paths[%d]' path does not "
                        "exist: %s" % (ident, element_index, element)
                    )

    return problems


def load_json(path):
    """Return (data, error_message). error_message is None on success."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle), None
    except json.JSONDecodeError as exc:
        return None, "%s is not valid JSON: %s (line %d column %d)" % (
            path,
            exc.msg,
            exc.lineno,
            exc.colno,
        )
    except UnicodeDecodeError as exc:
        return None, "%s is not valid UTF-8 text: %s" % (path, exc)
    except OSError as exc:
        return None, "cannot read %s: %s" % (path, exc.strerror or exc)


def build_base_dirs(tasks_path, extra_bases):
    bases = []

    def add(candidate):
        candidate = Path(candidate)
        if candidate not in bases:
            bases.append(candidate)

    add(Path.cwd())
    try:
        resolved = tasks_path.resolve()
    except OSError:  # pragma: no cover - resolve rarely fails
        resolved = tasks_path.absolute()
    add(resolved.parent)
    add(resolved.parent.parent)
    for extra in extra_bases:
        add(extra)
    return bases


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="validate_tasks.py",
        description=(
            "Validate coordination/TASKS.json: row schema and types, allowed "
            "statuses, file-level timestamp consistency, ownership against "
            "TEAM-REGISTRY.json, and evidence path existence."
        ),
    )
    parser.add_argument(
        "tasks_pos",
        nargs="?",
        default=None,
        metavar="TASKS_JSON",
        help="path to TASKS.json (default: coordination/TASKS.json; a "
        "directory is treated as the repository root)",
    )
    parser.add_argument(
        "registry_pos",
        nargs="?",
        default=None,
        metavar="TEAM_REGISTRY_JSON",
        help="path to TEAM-REGISTRY.json (default: coordination/"
        "TEAM-REGISTRY.json)",
    )
    parser.add_argument(
        "--tasks",
        dest="tasks_opt",
        default=None,
        help="path to TASKS.json (alternative to the positional argument)",
    )
    parser.add_argument(
        "--registry",
        dest="registry_opt",
        default=None,
        help="path to TEAM-REGISTRY.json (alternative to the positional "
        "argument)",
    )
    parser.add_argument(
        "--base",
        action="append",
        default=[],
        metavar="DIR",
        help="extra directory for resolving relative evidence paths "
        "(repeatable)",
    )
    parser.add_argument(
        "--statuses",
        default=None,
        metavar="CSV",
        help="comma-separated allowed status values (default: the project "
        "vocabulary queued,ready,running,review,blocked,done,cancelled)",
    )
    args = parser.parse_args(argv)

    tasks_arg = args.tasks_opt or args.tasks_pos
    registry_arg = args.registry_opt or args.registry_pos

    tasks_path = Path(tasks_arg) if tasks_arg else DEFAULT_TASKS_PATH
    if tasks_path.is_dir():
        repo_root = tasks_path
        tasks_path = repo_root / "coordination" / "TASKS.json"
        if registry_arg is None:
            registry_path = repo_root / "coordination" / "TEAM-REGISTRY.json"
        else:
            registry_path = Path(registry_arg)
    elif registry_arg is None:
        registry_path = DEFAULT_REGISTRY_PATH
    else:
        registry_path = Path(registry_arg)

    if not tasks_path.exists():
        print(
            "ERROR: tasks file not found: %s" % tasks_path, file=sys.stderr
        )
        return EXIT_INPUT_ERROR
    tasks_data, tasks_error = load_json(tasks_path)
    if tasks_error is not None:
        print("ERROR: %s" % tasks_error, file=sys.stderr)
        return EXIT_INPUT_ERROR

    registry_map = {}
    if registry_path.exists():
        registry_data, registry_error = load_json(registry_path)
        if registry_error is not None:
            print("ERROR: %s" % registry_error, file=sys.stderr)
            return EXIT_INPUT_ERROR
        registry_map = build_registry_map(registry_data)
    else:
        print(
            "note: registry file not found at %s; skipping cross-file "
            "ownership checks" % registry_path,
            file=sys.stderr,
        )

    if args.statuses is not None:
        statuses = tuple(
            piece.strip()
            for piece in args.statuses.split(",")
            if piece.strip()
        )
    else:
        statuses = DEFAULT_STATUSES

    base_dirs = build_base_dirs(tasks_path, args.base)

    problems = validate_tasks_doc(tasks_data, registry_map, statuses, base_dirs)

    for problem in problems:
        print(problem)

    if problems:
        print("%d problem(s) found." % len(problems))
        return EXIT_PROBLEMS

    print("OK: no problems found.")
    return EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # a broken run must not end in a traceback
        print("ERROR: unexpected failure: %s" % exc, file=sys.stderr)
        sys.exit(EXIT_INPUT_ERROR)

#!/usr/bin/env python3
"""Validate the project's coordination task registry (coordination/TASKS.json).

Checks performed (see TASK.md / README.md):
  1. Schema conformance  - every row has exactly the expected key set.
  2. Type conformance    - every field has the expected type.
  3. Valid status values - status is one of the project's allowed statuses.
  4. File-level consistency - no row is newer than the file's updated_at.
  5. Cross-file ownership - owner_tag matches the team's head_tag in
     coordination/TEAM-REGISTRY.json (teams absent from the registry are
     not an ownership error).
  6. Evidence paths      - every evidence_paths entry exists on disk.

Exit codes: 0 = no problems, 1 = problems found, 2 = the input file could
not be read/parsed at all (e.g. malformed JSON).

Python 3 standard library only; no network access.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# The exact key set every task row must carry, with the expected type of
# each field ("string-list" means a JSON array of strings).
EXPECTED_FIELDS = {
    "id": "string",
    "team_id": "string",
    "owner_tag": "string",
    "status": "string",
    "updated_at": "timestamp",
    "evidence_paths": "string-list",
    "blocked_on": "string-list",
    "next_action": "string",
    "acceptance": "string",
    "assignment_ack": "string",
}

# The project's fixed status vocabulary (coordination/OPERATING-MODEL.md:
# "Statuses: queued, ready, running, review, blocked, done, cancelled.").
ALLOWED_STATUSES = frozenset(
    {"queued", "ready", "running", "review", "blocked", "done", "cancelled"}
)

DEFAULT_TASKS_PATH = os.path.join("coordination", "TASKS.json")
DEFAULT_REGISTRY_PATH = os.path.join("coordination", "TEAM-REGISTRY.json")

EXIT_OK = 0
EXIT_PROBLEMS = 1
EXIT_INPUT_ERROR = 2


def parse_iso8601(value):
    """Parse an ISO8601 timestamp string; return an aware datetime or None.

    Naive timestamps are interpreted as UTC so that aware and naive values
    can be compared without raising.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def type_description(value):
    return type(value).__name__


def row_label(index, row):
    """Identify a row by task id when possible, always by row index."""
    if isinstance(row, dict):
        task_id = row.get("id")
        if isinstance(task_id, str):
            return "task '%s' (tasks[%d])" % (task_id, index)
    return "tasks[%d] (id missing or not a string)" % index


class Validator:
    def __init__(self, registry_map, evidence_root):
        self.registry_map = registry_map  # team_id -> head_tag (may be empty)
        self.evidence_root = evidence_root
        self.problems = []

    def report(self, label, message):
        self.problems.append("%s: %s" % (label, message))

    def check_field_type(self, label, field, value):
        """Return True if value has the expected type for field, else report."""
        expected = EXPECTED_FIELDS[field]
        if expected == "string":
            ok = isinstance(value, str)
            detail = "expected a string, got %s" % type_description(value)
        elif expected == "timestamp":
            ok = isinstance(value, str) and parse_iso8601(value) is not None
            if not isinstance(value, str):
                detail = "expected an ISO8601 timestamp string, got %s" % (
                    type_description(value),)
            else:
                detail = "not a valid ISO8601 timestamp: %r" % (value,)
        else:  # string-list
            if not isinstance(value, list):
                ok = False
                detail = "expected an array of strings, got %s" % (
                    type_description(value),)
            else:
                bad = [(i, item) for i, item in enumerate(value)
                       if not isinstance(item, str)]
                ok = not bad
                detail = "; ".join(
                    "%s[%d] must be a string, got %s"
                    % (field, i, type_description(item))
                    for i, item in bad)
        if not ok:
            self.report(label, "field '%s': %s" % (field, detail))
        return ok

    def check_row(self, index, row, file_updated):
        label = row_label(index, row)
        if not isinstance(row, dict):
            self.report(label, "row is not a JSON object (got %s)"
                        % type_description(row))
            return

        keys = set(row.keys())
        expected_keys = set(EXPECTED_FIELDS)

        # 1. Schema conformance: missing and unexpected keys are distinct.
        for field in EXPECTED_FIELDS:
            if field not in keys:
                self.report(label, "field '%s': missing required key" % field)
        for field in sorted(keys - expected_keys):
            self.report(label, "field '%s': unexpected key not allowed" % field)

        # 2. Type conformance for present fields (missing keys were already
        # reported above and cannot be type-checked).
        row_updated = None
        for field, value in row.items():
            if field not in expected_keys:
                continue
            if field == "updated_at":
                if isinstance(value, str) and parse_iso8601(value) is None:
                    self.check_field_type(label, field, value)
                elif not isinstance(value, str):
                    self.check_field_type(label, field, value)
                else:
                    row_updated = parse_iso8601(value)
                continue
            self.check_field_type(label, field, value)

        # 3. Valid status values (only meaningful for a clean string status).
        status = row.get("status")
        if isinstance(status, str) and status not in ALLOWED_STATUSES:
            self.report(
                label,
                "field 'status': invalid status %r (allowed: %s)"
                % (status, ", ".join(sorted(ALLOWED_STATUSES))))

        # 4. File-level consistency: row must not be newer than the file.
        if file_updated is not None and row_updated is not None:
            if row_updated > file_updated:
                self.report(
                    label,
                    "field 'updated_at': row updated_at %s is newer than the "
                    "file updated_at %s"
                    % (row["updated_at"], file_updated.isoformat()))

        # 5. Cross-file ownership (registry-known teams only).
        team_id = row.get("team_id")
        owner_tag = row.get("owner_tag")
        if isinstance(team_id, str) and isinstance(owner_tag, str):
            head_tag = self.registry_map.get(team_id)
            if head_tag is not None and owner_tag != head_tag:
                self.report(
                    label,
                    "field 'owner_tag': owner %r does not match head_tag %r "
                    "of team %r from TEAM-REGISTRY.json"
                    % (owner_tag, head_tag, team_id))

        # 6. Evidence paths must exist on disk (checked only for clean
        # string lists; type problems were already reported).
        evidence = row.get("evidence_paths")
        if isinstance(evidence, list):
            for i, path in enumerate(evidence):
                if not isinstance(path, str):
                    continue
                if not self.path_exists(path):
                    self.report(
                        label,
                        "field 'evidence_paths': path does not exist: %s"
                        % path)

    def path_exists(self, path):
        if os.path.isabs(path):
            return os.path.exists(path)
        return os.path.exists(os.path.join(self.evidence_root, path))

    def validate(self, data):
        """Validate the parsed TASKS.json document."""
        if not isinstance(data, dict):
            self.report(
                "file",
                "top-level JSON value must be an object, got %s"
                % type_description(data))
            return

        if "tasks" not in data:
            self.report("file", "top-level key 'tasks' is missing")
        elif not isinstance(data["tasks"], list):
            self.report(
                "file",
                "top-level key 'tasks' must be an array, got %s"
                % type_description(data["tasks"]))

        file_updated = None
        if "updated_at" not in data:
            self.report(
                "file",
                "top-level key 'updated_at' is missing (required to check "
                "that no row is newer than the file)")
        elif not isinstance(data["updated_at"], str):
            self.report(
                "file",
                "top-level key 'updated_at' must be an ISO8601 string, got %s"
                % type_description(data["updated_at"]))
        elif parse_iso8601(data["updated_at"]) is None:
            self.report(
                "file",
                "top-level key 'updated_at': not a valid ISO8601 timestamp: "
                "%r" % (data["updated_at"],))
        else:
            file_updated = parse_iso8601(data["updated_at"])

        tasks = data.get("tasks")
        if isinstance(tasks, list):
            for index, row in enumerate(tasks):
                self.check_row(index, row, file_updated)


def load_registry_map(path):
    """Load TEAM-REGISTRY.json.

    Returns (registry_map, fatal_problem, note):
      registry_map   dict team_id -> head_tag, possibly empty
      fatal_problem  problem line if the file exists but cannot be used
      note           informational line (missing file) that is not a problem
    """
    if not os.path.exists(path):
        return {}, None, (
            "note: %s not found; skipping cross-file ownership checks" % path)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, UnicodeDecodeError) as exc:
        return {}, "%s: cannot be read: %s" % (path, exc), None
    except json.JSONDecodeError as exc:
        return {}, (
            "%s: malformed JSON: %s (line %d, column %d)"
            % (path, exc.msg, exc.lineno, exc.colno)), None

    registry_map = {}
    teams = data.get("teams") if isinstance(data, dict) else None
    if isinstance(teams, list):
        for team in teams:
            if not isinstance(team, dict):
                continue
            team_id = team.get("id")
            head_tag = team.get("head_tag")
            if isinstance(team_id, str) and isinstance(head_tag, str):
                registry_map[team_id] = head_tag
    return registry_map, None, None


def load_tasks_document(path):
    """Read and parse TASKS.json. Returns (document, error_line)."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        return None, "cannot read %s: %s" % (path, exc)
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, (
            "%s: malformed JSON: %s (line %d, column %d)"
            % (path, exc.msg, exc.lineno, exc.colno))


def build_argument_parser():
    parser = argparse.ArgumentParser(
        description="Validate coordination/TASKS.json against the project's "
                    "schema, status vocabulary, timestamps, team ownership "
                    "(TEAM-REGISTRY.json) and evidence paths.")
    parser.add_argument(
        "tasks_path", nargs="?", default=None,
        help="path to TASKS.json (default: %s)" % DEFAULT_TASKS_PATH)
    parser.add_argument(
        "registry_path", nargs="?", default=None,
        help="path to TEAM-REGISTRY.json (default: %s)" % DEFAULT_REGISTRY_PATH)
    parser.add_argument(
        "--tasks", dest="tasks_option", default=None,
        help="path to TASKS.json (overrides the positional argument)")
    parser.add_argument(
        "--registry", dest="registry_option", default=None,
        help="path to TEAM-REGISTRY.json (overrides the positional argument)")
    parser.add_argument(
        "--root", default=None,
        help="base directory for relative evidence paths "
             "(default: current directory)")
    return parser


def main(argv=None):
    args = build_argument_parser().parse_args(argv)
    tasks_path = args.tasks_option or args.tasks_path or DEFAULT_TASKS_PATH
    registry_path = (args.registry_option or args.registry_path
                     or DEFAULT_REGISTRY_PATH)
    evidence_root = args.root if args.root is not None else os.getcwd()

    document, error_line = load_tasks_document(tasks_path)
    if document is None:
        print("ERROR: %s" % error_line)
        return EXIT_INPUT_ERROR

    registry_map, registry_problem, registry_note = load_registry_map(
        registry_path)

    validator = Validator(registry_map, evidence_root)
    validator.validate(document)

    if registry_problem:
        validator.report("file", registry_problem)
    if registry_note:
        print(registry_note)

    for problem in validator.problems:
        print("PROBLEM %s" % problem)

    if validator.problems:
        print("%d problem(s) found." % len(validator.problems))
        return EXIT_PROBLEMS
    print("No problems found.")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())

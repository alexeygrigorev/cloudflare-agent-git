#!/usr/bin/env python3
"""Tests for validate_tasks.py, run against synthetic fixtures only.

No test reads or depends on the live coordination/TASKS.json or
TEAM-REGISTRY.json; every fixture is written to a fresh temporary directory.

Run directly:            python3 tests/test_validate_tasks.py -v
Or via unittest discover from this directory:
                         python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "validate_tasks.py"

FILE_UPDATED_AT = "2026-10-02T10:00:00+00:00"

ALLOWED_STATUSES = (
    "queued",
    "ready",
    "running",
    "review",
    "blocked",
    "done",
    "cancelled",
)


def valid_row(**overrides):
    row = {
        "id": "task-1",
        "team_id": "team-a",
        "owner_tag": "alice-head",
        "status": "running",
        "updated_at": "2026-10-01T10:00:00+00:00",
        "evidence_paths": ["evidence/a.md"],
        "blocked_on": [],
        "next_action": "do the thing",
        "acceptance": "thing accepted",
        "assignment_ack": "ACK: owned by alice-head",
    }
    row.update(overrides)
    return row


def tasks_doc(rows, updated_at=FILE_UPDATED_AT, **extra):
    doc = {"schema_version": 1, "updated_at": updated_at, "tasks": rows}
    doc.update(extra)
    return doc


def registry_list(*teams):
    """Live TEAM-REGISTRY.json layout: a list of team objects."""
    return [
        {"id": team_id, "head_tag": head_tag} for team_id, head_tag in teams
    ]


class FixtureBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write(self, relative_path, payload):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(payload, str):
            path.write_text(payload, encoding="utf-8")
        else:
            path.write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
        return path

    def touch(self, relative_path):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("evidence\n", encoding="utf-8")
        return path

    def run_tool(self, tasks, registry=None, cwd=None, extra_args=()):
        command = [sys.executable, str(TOOL)]
        if tasks is not None:
            command.append(str(tasks))
        if registry is not None:
            command.append(str(registry))
        command.extend(extra_args)
        return subprocess.run(
            command,
            cwd=str(cwd) if cwd else str(self.root),
            capture_output=True,
            text=True,
            timeout=60,
        )


class CleanFileTests(FixtureBase):
    def test_clean_file_exits_zero(self):
        self.touch("evidence/a.md")
        tasks = self.write("tasks.json", tasks_doc([valid_row()]))
        registry = self.write(
            "registry.json", registry_list(("team-a", "alice-head"))
        )
        result = self.run_tool(tasks, registry)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("no problems", result.stdout)

    def test_empty_tasks_list_exits_zero(self):
        tasks = self.write("tasks.json", tasks_doc([]))
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_documented_status_is_allowed(self):
        self.touch("evidence/a.md")
        rows = [
            valid_row(id="task-%d" % i, status=status)
            for i, status in enumerate(ALLOWED_STATUSES)
        ]
        tasks = self.write("tasks.json", tasks_doc(rows))
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class SchemaConformanceTests(FixtureBase):
    def test_missing_key_reported_with_task_id(self):
        row = valid_row()
        del row["acceptance"]
        tasks = self.write("tasks.json", tasks_doc([row]))
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing key 'acceptance'", result.stdout)
        self.assertIn("task-1", result.stdout)

    def test_unexpected_key_reported_as_distinct_problem(self):
        tasks = self.write(
            "tasks.json", tasks_doc([valid_row(notes="extra field")])
        )
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 1)
        self.assertIn("unexpected key 'notes'", result.stdout)

    def test_missing_and_unexpected_both_reported(self):
        row = valid_row()
        del row["next_action"]
        row["extra"] = 1
        tasks = self.write("tasks.json", tasks_doc([row]))
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing key 'next_action'", result.stdout)
        self.assertIn("unexpected key 'extra'", result.stdout)

    def test_row_without_string_id_is_named_by_index(self):
        row = valid_row()
        del row["id"]
        tasks = self.write("tasks.json", tasks_doc([row]))
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 1)
        self.assertIn("tasks[0]", result.stdout)
        self.assertIn("missing key 'id'", result.stdout)

    def test_non_string_id_named_by_index_and_type_flagged(self):
        tasks = self.write("tasks.json", tasks_doc([valid_row(id=7)]))
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 1)
        self.assertIn("tasks[0]", result.stdout)
        self.assertIn("field 'id' must be a string", result.stdout)

    def test_row_that_is_not_an_object_is_reported_by_index(self):
        tasks = self.write("tasks.json", tasks_doc(["not-a-row"]))
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 1)
        self.assertIn("tasks[0]", result.stdout)
        self.assertIn("must be a JSON object", result.stdout)

    def test_missing_top_level_tasks_key(self):
        doc = {"schema_version": 1, "updated_at": FILE_UPDATED_AT}
        tasks = self.write("tasks.json", doc)
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 1)
        self.assertIn("'tasks'", result.stdout)


class TypeConformanceTests(FixtureBase):
    def test_string_field_given_number(self):
        tasks = self.write(
            "tasks.json", tasks_doc([valid_row(owner_tag=42)])
        )
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 1)
        self.assertIn("field 'owner_tag' must be a string", result.stdout)
        self.assertIn("number", result.stdout)

    def test_list_field_given_string(self):
        tasks = self.write(
            "tasks.json", tasks_doc([valid_row(evidence_paths="evidence.md")])
        )
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 1)
        self.assertIn("field 'evidence_paths' must be an array", result.stdout)

    def test_array_element_not_a_string(self):
        tasks = self.write(
            "tasks.json", tasks_doc([valid_row(evidence_paths=["ok", 3])])
        )
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "field 'evidence_paths[1]' must be a string", result.stdout
        )

    def test_blocked_on_element_not_a_string(self):
        tasks = self.write(
            "tasks.json", tasks_doc([valid_row(blocked_on=[None])])
        )
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "field 'blocked_on[0]' must be a string", result.stdout
        )

    def test_missing_field_is_not_reported_as_type_problem(self):
        row = valid_row()
        del row["acceptance"]
        tasks = self.write("tasks.json", tasks_doc([row]))
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing key 'acceptance'", result.stdout)
        self.assertNotIn("field 'acceptance' must be a string", result.stdout)

    def test_invalid_timestamp_string_reported(self):
        tasks = self.write(
            "tasks.json", tasks_doc([valid_row(updated_at="yesterday")])
        )
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a valid ISO8601 timestamp", result.stdout)


class StatusTests(FixtureBase):
    def test_invalid_status_reported(self):
        tasks = self.write("tasks.json", tasks_doc([valid_row(status="WIP")]))
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 1)
        self.assertIn("field 'status'", result.stdout)
        self.assertIn("'WIP'", result.stdout)
        self.assertIn("allowed", result.stdout)

    def test_status_type_problem_not_double_reported(self):
        tasks = self.write("tasks.json", tasks_doc([valid_row(status=1)]))
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 1)
        self.assertIn("field 'status' must be a string", result.stdout)
        self.assertNotIn("invalid value", result.stdout)


class FileLevelConsistencyTests(FixtureBase):
    def test_row_newer_than_file_is_flagged(self):
        tasks = self.write(
            "tasks.json",
            tasks_doc(
                [valid_row(updated_at="2026-10-03T00:00:00+00:00")],
            ),
        )
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 1)
        self.assertIn("newer than", result.stdout)
        self.assertIn("task-1", result.stdout)

    def test_row_equal_to_file_timestamp_is_not_flagged(self):
        self.touch("evidence/a.md")
        tasks = self.write(
            "tasks.json", tasks_doc([valid_row(updated_at=FILE_UPDATED_AT)])
        )
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_row_older_than_file_is_not_flagged(self):
        self.touch("evidence/a.md")
        tasks = self.write(
            "tasks.json",
            tasks_doc([valid_row(updated_at="2026-09-01T00:00:00+00:00")]),
        )
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_top_level_updated_at_is_flagged(self):
        rows = [valid_row()]
        doc = {"schema_version": 1, "tasks": rows}
        tasks = self.write("tasks.json", doc)
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing top-level key 'updated_at'", result.stdout)


class OwnershipTests(FixtureBase):
    def test_owner_mismatch_with_live_style_registry(self):
        self.touch("evidence/a.md")
        tasks = self.write("tasks.json", tasks_doc([valid_row()]))
        registry = self.write(
            "registry.json", registry_list(("team-a", "bob-head"))
        )
        result = self.run_tool(tasks, registry)
        self.assertEqual(result.returncode, 1)
        self.assertIn("field 'owner_tag'", result.stdout)
        self.assertIn("alice-head", result.stdout)
        self.assertIn("bob-head", result.stdout)
        self.assertIn("team-a", result.stdout)

    def test_matching_owner_passes(self):
        self.touch("evidence/a.md")
        tasks = self.write("tasks.json", tasks_doc([valid_row()]))
        registry = self.write(
            "registry.json", registry_list(("team-a", "alice-head"))
        )
        result = self.run_tool(tasks, registry)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_team_absent_from_registry_is_not_an_ownership_error(self):
        self.touch("evidence/a.md")
        tasks = self.write(
            "tasks.json", tasks_doc([valid_row(team_id="unknown-team")])
        )
        registry = self.write(
            "registry.json", registry_list(("team-a", "alice-head"))
        )
        result = self.run_tool(tasks, registry)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dict_of_objects_registry_layout(self):
        self.touch("evidence/a.md")
        tasks = self.write("tasks.json", tasks_doc([valid_row()]))
        registry = self.write(
            "registry.json",
            {"schema_version": 1, "teams": {"team-a": {"head_tag": "z-head"}}},
        )
        result = self.run_tool(tasks, registry)
        self.assertEqual(result.returncode, 1)
        self.assertIn("z-head", result.stdout)

    def test_missing_registry_file_skips_ownership_check(self):
        self.touch("evidence/a.md")
        tasks = self.write("tasks.json", tasks_doc([valid_row()]))
        result = self.run_tool(tasks, self.root / "does-not-exist.json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ownership", result.stderr)


class EvidencePathTests(FixtureBase):
    def test_missing_evidence_path_reported(self):
        tasks = self.write(
            "tasks.json",
            tasks_doc([valid_row(evidence_paths=["evidence/a.md"])]),
        )
        registry = self.write("registry.json", registry_list())
        result = self.run_tool(tasks, registry)
        self.assertEqual(result.returncode, 1)
        self.assertIn("evidence/a.md", result.stdout)
        self.assertIn("does not exist", result.stdout)

    def test_existing_evidence_path_passes(self):
        self.touch("evidence/a.md")
        tasks = self.write("tasks.json", tasks_doc([valid_row()]))
        registry = self.write("registry.json", registry_list())
        result = self.run_tool(tasks, registry)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_relative_path_resolved_against_repo_root_layout(self):
        # Live layout: TASKS.json sits in <root>/coordination/, evidence
        # paths are relative to <root>.
        self.touch("evidence/a.md")
        tasks = self.write("coordination/tasks.json", tasks_doc([valid_row()]))
        registry = self.write("coordination/registry.json", registry_list())
        result = self.run_tool(tasks, registry, cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_absolute_evidence_path(self):
        existing = self.touch("evidence/a.md")
        tasks = self.write(
            "tasks.json",
            tasks_doc(
                [
                    valid_row(id="good", evidence_paths=[str(existing)]),
                    valid_row(
                        id="bad",
                        evidence_paths=["/nonexistent/nowhere.txt"],
                    ),
                ]
            ),
        )
        registry = self.write("registry.json", registry_list())
        result = self.run_tool(tasks, registry)
        self.assertEqual(result.returncode, 1)
        self.assertIn("/nonexistent/nowhere.txt", result.stdout)
        self.assertNotIn("id='good'", result.stdout)

    def test_outside_directory_paths_are_allowed(self):
        # Requirement: do not require paths to be inside any particular dir.
        with tempfile.TemporaryDirectory() as other_dir:
            outside = Path(other_dir) / "elsewhere.md"
            outside.write_text("x\n", encoding="utf-8")
            tasks = self.write(
                "tasks.json",
                tasks_doc([valid_row(evidence_paths=[str(outside)])]),
            )
            registry = self.write("registry.json", registry_list())
            result = self.run_tool(tasks, registry)
            self.assertEqual(
                result.returncode, 0, result.stdout + result.stderr
            )


class CliBehaviourTests(FixtureBase):
    def test_malformed_json_is_clean_error_not_traceback(self):
        tasks = self.write("tasks.json", "{definitely not json")
        result = self.run_tool(tasks)
        self.assertEqual(result.returncode, 2)
        self.assertIn("not valid JSON", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn("Traceback", result.stdout)

    def test_missing_tasks_file_is_clean_error(self):
        result = self.run_tool(self.root / "absent.json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not found", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_all_problems_reported_not_just_first(self):
        row = valid_row(status="WIP", owner_tag=5)
        del row["acceptance"]
        row["unexpected_key"] = True
        self.write("evidence/missing-later.md", "x")  # exists
        tasks = self.write(
            "tasks.json",
            tasks_doc(
                [
                    row,
                    valid_row(
                        id="task-2",
                        evidence_paths=["evidence/really-missing.md"],
                    ),
                ]
            ),
        )
        registry = self.write(
            "registry.json", registry_list(("team-a", "someone-else"))
        )
        result = self.run_tool(tasks, registry)
        self.assertEqual(result.returncode, 1)
        stdout = result.stdout
        self.assertIn("missing key 'acceptance'", stdout)
        self.assertIn("unexpected key 'unexpected_key'", stdout)
        self.assertIn("must be a string", stdout)
        self.assertIn("'WIP'", stdout)
        self.assertIn("does not match head_tag", stdout)
        self.assertIn("does not exist", stdout)
        problem_lines = [
            line
            for line in stdout.splitlines()
            if line.startswith("tasks[")
        ]
        self.assertGreaterEqual(len(problem_lines), 6)

    def test_default_paths_from_repo_style_root(self):
        self.touch("evidence/a.md")
        self.write("coordination/TASKS.json", tasks_doc([valid_row()]))
        self.write(
            "coordination/TEAM-REGISTRY.json",
            registry_list(("team-a", "alice-head")),
        )
        result = self.run_tool(None, None, cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_directory_argument_treated_as_repo_root(self):
        self.touch("evidence/a.md")
        self.write("coordination/TASKS.json", tasks_doc([valid_row()]))
        self.write(
            "coordination/TEAM-REGISTRY.json",
            registry_list(("team-a", "alice-head")),
        )
        result = self.run_tool(self.root, None, cwd=tempfile.gettempdir())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_long_form_flags(self):
        self.touch("evidence/a.md")
        tasks = self.write("tasks.json", tasks_doc([valid_row()]))
        registry = self.write(
            "registry.json", registry_list(("team-a", "alice-head"))
        )
        result = self.run_tool(
            None,
            None,
            extra_args=["--tasks", str(tasks), "--registry", str(registry)],
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)

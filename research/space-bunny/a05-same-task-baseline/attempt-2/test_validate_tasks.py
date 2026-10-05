#!/usr/bin/env python3
"""Tests for validate_tasks.py, run against synthetic fixtures only.

The live coordination/TASKS.json and TEAM-REGISTRY.json are never read:
every fixture is written into a fresh temporary directory.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "validate_tasks.py")

FILE_UPDATED = "2026-10-03T02:00:00+00:00"
ROW_UPDATED = "2026-10-03T01:00:00+00:00"

ALLOWED_STATUSES = ["queued", "ready", "running", "review", "blocked",
                    "done", "cancelled"]


def valid_row(index=0, **overrides):
    row = {
        "id": "task-%d" % index,
        "team_id": "team-a",
        "owner_tag": "head-a",
        "status": "running",
        "updated_at": ROW_UPDATED,
        "evidence_paths": ["evidence/file-%d.txt" % index],
        "blocked_on": [],
        "next_action": "do the thing",
        "acceptance": "tests pass",
        "assignment_ack": "ACK: owned",
    }
    row.update(overrides)
    return row


def valid_registry():
    return {
        "schema_version": 1,
        "updated_at": FILE_UPDATED,
        "teams": [
            {"id": "team-a", "head_tag": "head-a"},
            {"id": "team-b", "head_tag": "head-b"},
        ],
    }


class Fixture:
    """Builds a disposable coordination fixture in a temp directory."""

    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="task-validator-test-")
        self.tasks_path = os.path.join(self.dir, "coordination", "TASKS.json")
        self.registry_path = os.path.join(self.dir, "coordination",
                                          "TEAM-REGISTRY.json")

    def write_tasks(self, document, raw=None):
        os.makedirs(os.path.dirname(self.tasks_path), exist_ok=True)
        with open(self.tasks_path, "w", encoding="utf-8") as handle:
            if raw is not None:
                handle.write(raw)
            else:
                json.dump(document, handle, indent=2)

    def write_registry(self, document=None):
        os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
        with open(self.registry_path, "w", encoding="utf-8") as handle:
            json.dump(document if document is not None else valid_registry(),
                      handle, indent=2)

    def remove_registry(self):
        if os.path.exists(self.registry_path):
            os.remove(self.registry_path)

    def add_evidence_file(self, relpath, content="evidence\n"):
        path = os.path.join(self.dir, relpath)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return path

    def add_evidence_dir(self, relpath):
        path = os.path.join(self.dir, relpath)
        if os.path.isfile(path):
            os.remove(path)
        os.makedirs(path, exist_ok=True)
        return path

    def standard(self, rows, tasks_document=None, registry=None):
        """Write a tasks document (file updated_at newer than rows) and the
        default registry, and create the evidence files the rows reference."""
        for row in rows:
            for relpath in row.get("evidence_paths", []):
                if not isinstance(relpath, str):
                    continue
                if os.path.isabs(relpath):
                    continue
                if relpath.endswith("/"):
                    self.add_evidence_dir(relpath)
                else:
                    self.add_evidence_file(relpath)
        document = tasks_document if tasks_document is not None else {
            "schema_version": 1,
            "updated_at": FILE_UPDATED,
            "tasks": rows,
        }
        self.write_tasks(document)
        if registry is not False:
            self.write_registry(registry)
        return document

    def run(self, cwd=None, extra_args=None):
        cmd = [sys.executable, TOOL,
               "--tasks", self.tasks_path,
               "--registry", self.registry_path,
               "--root", self.dir]
        if extra_args:
            cmd.extend(extra_args)
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              cwd=cwd or self.dir, timeout=120)
        return proc


class ValidatorTestCase(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        self.addCleanup(self.cleanup_fixture)

    def cleanup_fixture(self):
        import shutil
        shutil.rmtree(self.fixture.dir, ignore_errors=True)

    # -- baseline ---------------------------------------------------------

    def test_clean_fixture_exits_zero(self):
        self.fixture.standard([valid_row(0), valid_row(1)])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("No problems found", proc.stdout)
        self.assertNotIn("PROBLEM", proc.stdout)

    # -- 1. schema conformance -------------------------------------------

    def test_missing_key_reported_and_names_task(self):
        row = valid_row(0)
        del row["acceptance"]
        self.fixture.standard([row])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("task 'task-0'", proc.stdout)
        self.assertIn("acceptance", proc.stdout)
        self.assertIn("missing", proc.stdout)

    def test_unexpected_key_reported_and_names_task(self):
        row = valid_row(0, extra_note="not in schema")
        self.fixture.standard([row])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("task 'task-0'", proc.stdout)
        self.assertIn("extra_note", proc.stdout)
        self.assertIn("unexpected", proc.stdout)

    def test_missing_and_unexpected_are_distinct_problems(self):
        row = valid_row(0, extra_note="surprise")
        del row["acceptance"]
        self.fixture.standard([row])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout.count("PROBLEM"), 2)
        self.assertIn("acceptance", proc.stdout)
        self.assertIn("extra_note", proc.stdout)

    def test_id_not_a_string_identifies_row_by_index(self):
        self.fixture.standard([valid_row(0), valid_row(1, id=99)])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("tasks[1]", proc.stdout)
        self.assertIn("'id'", proc.stdout)  # the type problem on id itself

    def test_id_missing_identifies_row_by_index(self):
        row = valid_row(0)
        del row["id"]
        self.fixture.standard([row])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("tasks[0]", proc.stdout)
        self.assertIn("id", proc.stdout)
        self.assertIn("missing", proc.stdout)

    # -- 2. type conformance ---------------------------------------------

    def test_string_field_given_number(self):
        self.fixture.standard([valid_row(0, owner_tag=42)])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("owner_tag", proc.stdout)
        self.assertIn("string", proc.stdout)
        self.assertIn("int", proc.stdout)

    def test_list_field_given_string(self):
        self.fixture.standard([valid_row(0, blocked_on="team-b")])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("blocked_on", proc.stdout)
        self.assertIn("array", proc.stdout)

    def test_missing_field_is_a_third_distinct_problem(self):
        row = valid_row(0, owner_tag=42, blocked_on="team-b")
        del row["acceptance"]
        self.fixture.standard([row])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        # three different problems: wrong-type string field, wrong-type list
        # field, and a missing field
        self.assertEqual(proc.stdout.count("PROBLEM"), 3)
        self.assertIn("owner_tag", proc.stdout)
        self.assertIn("blocked_on", proc.stdout)
        self.assertIn("acceptance", proc.stdout)

    def test_list_with_non_string_element(self):
        self.fixture.standard([valid_row(0, evidence_paths=["ok.txt", 7])])
        self.fixture.add_evidence_file("ok.txt")
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("evidence_paths[1]", proc.stdout)
        self.assertIn("string", proc.stdout)

    def test_null_value_is_a_type_problem(self):
        self.fixture.standard([valid_row(0, next_action=None)])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("next_action", proc.stdout)

    def test_unparseable_timestamp_string_reported(self):
        self.fixture.standard([valid_row(0, updated_at="yesterday-ish")])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("updated_at", proc.stdout)
        self.assertIn("ISO8601", proc.stdout)

    # -- 3. status values --------------------------------------------------

    def test_invalid_status_reported(self):
        self.fixture.standard([valid_row(0, status="in-progress")])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("status", proc.stdout)
        self.assertIn("in-progress", proc.stdout)

    def test_wrong_case_status_is_invalid(self):
        self.fixture.standard([valid_row(0, status="Running")])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Running", proc.stdout)

    def test_all_allowed_statuses_pass(self):
        rows = [valid_row(i, status=status)
                for i, status in enumerate(ALLOWED_STATUSES)]
        self.fixture.standard(rows)
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 0, proc.stdout)

    # -- 4. file-level consistency ----------------------------------------

    def test_row_newer_than_file_flagged(self):
        self.fixture.standard(
            [valid_row(0, updated_at="2026-10-03T03:00:00+00:00")])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("task 'task-0'", proc.stdout)
        self.assertIn("updated_at", proc.stdout)
        self.assertIn("newer", proc.stdout)

    def test_row_equal_to_file_is_ok(self):
        self.fixture.standard([valid_row(0, updated_at=FILE_UPDATED)])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_row_older_than_file_is_ok(self):
        self.fixture.standard(
            [valid_row(0, updated_at="2020-01-01T00:00:00+00:00")])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_missing_top_level_updated_at_reported(self):
        row = valid_row(0)
        document = {"schema_version": 1, "tasks": [row]}
        self.fixture.standard([row], tasks_document=document)
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("updated_at", proc.stdout)
        self.assertNotIn("PROBLEM task", proc.stdout)  # row itself is clean

    def test_z_suffix_and_naive_timestamps_compare_without_crash(self):
        row = valid_row(0, updated_at="2026-10-03T03:00:00Z")
        document = {"schema_version": 1,
                    "updated_at": "2026-10-03T02:00:00",  # naive
                    "tasks": [row]}
        self.fixture.standard([row], tasks_document=document)
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("newer", proc.stdout)

    # -- 5. cross-file ownership ------------------------------------------

    def test_ownership_mismatch_flagged(self):
        self.fixture.standard([valid_row(0, owner_tag="head-b")])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("owner_tag", proc.stdout)
        self.assertIn("head-a", proc.stdout)  # expected head_tag named
        self.assertIn("head-b", proc.stdout)  # actual owner named

    def test_matching_owner_is_ok(self):
        self.fixture.standard([valid_row(0, owner_tag="head-a")])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_team_absent_from_registry_is_not_an_error(self):
        self.fixture.standard([valid_row(0, team_id="team-unknown")])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertNotIn("owner_tag", proc.stdout)

    def test_missing_registry_file_skips_ownership_check(self):
        self.fixture.standard([valid_row(0)])
        self.fixture.remove_registry()
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_malformed_registry_json_is_an_error(self):
        self.fixture.standard([valid_row(0)])
        with open(self.fixture.registry_path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        proc = self.fixture.run()
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("Traceback", proc.stdout + proc.stderr)
        self.assertIn("malformed JSON", proc.stdout)

    # -- 6. evidence paths -------------------------------------------------

    def test_missing_evidence_path_flagged(self):
        self.fixture.standard([valid_row(0)])
        # standard() auto-creates referenced evidence; delete it so the
        # path is genuinely missing on disk
        os.remove(os.path.join(self.fixture.dir, "evidence", "file-0.txt"))
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("evidence_paths", proc.stdout)
        self.assertIn("evidence/file-0.txt", proc.stdout)
        self.assertIn("does not exist", proc.stdout)

    def test_existing_file_and_directory_evidence_pass(self):
        row = valid_row(0, evidence_paths=["evidence/notes.md",
                                           "evidence/dir/sub"])
        self.fixture.standard([row])
        self.fixture.add_evidence_file("evidence/notes.md")
        self.fixture.add_evidence_dir("evidence/dir/sub")
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_absolute_evidence_path_checked(self):
        existing = self.fixture.add_evidence_file("evidence/abs.txt")
        row = valid_row(0, evidence_paths=[existing, "/nonexistent/nowhere"])
        self.fixture.standard([row])
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        missing_lines = [line for line in proc.stdout.splitlines()
                         if "does not exist" in line]
        self.assertEqual(len(missing_lines), 1)
        self.assertIn("/nonexistent/nowhere", missing_lines[0])
        self.assertNotIn("abs.txt", missing_lines[0])

    # -- behaviour: reporting completeness and exit codes -------------------

    def test_all_problems_reported_not_just_first(self):
        rows = [
            valid_row(0, status="bogus"),
            valid_row(1, owner_tag="head-b"),
            valid_row(2, next_action=123),
        ]
        rows[2]["evidence_paths"] = ["evidence/missing-2.txt"]
        del rows[1]["acceptance"]
        self.fixture.standard(rows)
        # standard() auto-creates referenced evidence; delete row 2's so it
        # is genuinely missing on disk
        os.remove(os.path.join(self.fixture.dir, "evidence", "missing-2.txt"))
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("task 'task-0'", proc.stdout)
        self.assertIn("task 'task-1'", proc.stdout)
        self.assertIn("task 'task-2'", proc.stdout)
        self.assertIn("bogus", proc.stdout)
        self.assertIn("head-a", proc.stdout)
        self.assertIn("acceptance", proc.stdout)
        self.assertIn("evidence/missing-2.txt", proc.stdout)
        # one PROBLEM line per distinct problem: status + owner mismatch +
        # missing acceptance + missing evidence + wrong-type next_action
        self.assertEqual(proc.stdout.count("PROBLEM"), 5)

    def test_malformed_tasks_json_is_error_without_traceback(self):
        self.fixture.write_tasks(None, raw="{oops")
        self.fixture.write_registry()
        proc = self.fixture.run()
        self.assertNotEqual(proc.returncode, 0)
        combined = proc.stdout + proc.stderr
        self.assertNotIn("Traceback", combined)
        self.assertIn("malformed JSON", proc.stdout)

    def test_missing_tasks_file_is_error_without_traceback(self):
        self.fixture.write_registry()
        proc = self.fixture.run()
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("Traceback", proc.stdout + proc.stderr)

    def test_tasks_not_a_list_reported(self):
        self.fixture.standard([], tasks_document={
            "schema_version": 1, "updated_at": FILE_UPDATED, "tasks": {}})
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("tasks", proc.stdout)
        self.assertIn("array", proc.stdout)

    def test_top_level_not_an_object_is_error(self):
        self.fixture.write_tasks(None, raw='["just", "a", "list"]')
        self.fixture.write_registry()
        proc = self.fixture.run()
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("Traceback", proc.stdout + proc.stderr)

    def test_row_not_an_object_reported(self):
        self.fixture.standard([], tasks_document={
            "schema_version": 1, "updated_at": FILE_UPDATED,
            "tasks": ["not-a-row", valid_row(1)]})
        proc = self.fixture.run()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("tasks[0]", proc.stdout)
        self.assertIn("task 'task-1'", proc.stdout)

    def test_row_problem_lines_name_task_and_field(self):
        self.fixture.standard([valid_row(0, status="bogus")])
        proc = self.fixture.run()
        problem_lines = [line for line in proc.stdout.splitlines()
                         if line.startswith("PROBLEM") and "task '" in line]
        self.assertTrue(problem_lines)
        for line in problem_lines:
            self.assertIn("task 'task-0'", line)
            self.assertIn("field '", line)

    # -- CLI invocation styles ---------------------------------------------

    def test_default_paths_from_working_directory(self):
        self.fixture.standard([valid_row(0)])
        proc = subprocess.run(
            [sys.executable, TOOL], capture_output=True, text=True,
            cwd=self.fixture.dir, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_positional_arguments(self):
        self.fixture.standard([valid_row(0, owner_tag="head-b")])
        proc = subprocess.run(
            [sys.executable, TOOL, self.fixture.tasks_path,
             self.fixture.registry_path, "--root", self.fixture.dir],
            capture_output=True, text=True, cwd=self.fixture.dir, timeout=120)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("owner_tag", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)

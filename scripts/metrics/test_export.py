#!/usr/bin/env python3
"""Unit tests for Continuation Runtime resolved tasks metrics collector and CLI (export.py)."""

import datetime
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from scripts.metrics.export import (
    ROOT,
    STORE,
    parse_window_seconds,
    summarize_resolved_tasks,
    summarize_running_agents,
    summarize_commits,
)


class TestResolvedTasksNumeratorExclusion(unittest.TestCase):
    """Test numerator exclusions per METRICS.md: unaccepted, awaiting-review, failed, in-progress."""

    def test_unaccepted_tasks_excluded(self):
        tasks = [
            {"id": "t-no-acc", "status": "done", "updated_at": "2026-10-07T03:00:00Z"},
            {"id": "t-empty-acc", "status": "done", "acceptance": "", "updated_at": "2026-10-07T03:00:00Z"},
            {"id": "t-valid-acc", "status": "done", "acceptance": "Passed QA review", "accepted_at": "2026-10-07T03:00:00Z"},
        ]
        res = summarize_resolved_tasks(tasks=tasks, as_of="2026-10-07T04:00:00Z", window_seconds=7200)
        self.assertEqual(res["resolved_unique_task_ids"], ["t-valid-acc"])
        self.assertEqual(res["resolved_task_count"], 1)

    def test_awaiting_review_tasks_excluded(self):
        tasks = [
            {"id": "t-awaiting-1", "status": "awaiting-review", "acceptance": "Spec met", "updated_at": "2026-10-07T03:00:00Z"},
            {"id": "t-awaiting-2", "status": "completed-awaiting-review", "acceptance": "Spec met", "updated_at": "2026-10-07T03:00:00Z"},
            {"id": "t-review", "status": "review", "acceptance": "Spec met", "updated_at": "2026-10-07T03:00:00Z"},
            {"id": "t-done", "status": "done", "acceptance": "Accepted by peer", "accepted_at": "2026-10-07T03:00:00Z"},
        ]
        res = summarize_resolved_tasks(tasks=tasks, as_of="2026-10-07T04:00:00Z", window_seconds=7200)
        self.assertEqual(res["resolved_unique_task_ids"], ["t-done"])
        self.assertEqual(res["resolved_task_count"], 1)

    def test_in_progress_failed_cancelled_tasks_excluded(self):
        statuses = ["todo", "in_progress", "starting", "running", "failed", "cancelled", "queued", "blocked", "held", "ready"]
        tasks = [{"id": f"t-{st}", "status": st, "acceptance": "Some claim", "updated_at": "2026-10-07T03:00:00Z"} for st in statuses]
        tasks.append({"id": "t-accepted", "status": "accepted", "acceptance": "Full peer signoff", "accepted_at": "2026-10-07T03:00:00Z"})
        res = summarize_resolved_tasks(tasks=tasks, as_of="2026-10-07T04:00:00Z", window_seconds=7200)
        self.assertEqual(res["resolved_unique_task_ids"], ["t-accepted"])
        self.assertEqual(res["resolved_task_count"], 1)

    def test_rejected_verdict_tasks_excluded(self):
        tasks = [
            {"id": "t-rej-1", "status": "done", "acceptance": "Spec met", "acceptance_status": "REJECTED", "accepted_at": "2026-10-07T03:00:00Z"},
            {"id": "t-rej-2", "status": "done", "acceptance": "Spec met", "reviewer_verdict": "FAIL", "accepted_at": "2026-10-07T03:00:00Z"},
            {"id": "t-rej-3", "status": "done", "acceptance": "Spec met", "verdict": "REJECT", "accepted_at": "2026-10-07T03:00:00Z"},
            {"id": "t-ok", "status": "done", "acceptance": "Spec met", "acceptance_status": "ACCEPTED", "accepted_at": "2026-10-07T03:00:00Z"},
        ]
        res = summarize_resolved_tasks(tasks=tasks, as_of="2026-10-07T04:00:00Z", window_seconds=7200)
        self.assertEqual(res["resolved_unique_task_ids"], ["t-ok"])
        self.assertEqual(res["resolved_task_count"], 1)

    def test_duplicate_aliases_counted_once(self):
        tasks = [
            {"id": "t-dup", "status": "done", "acceptance": "Signoff 1", "accepted_at": "2026-10-07T03:00:00Z", "team_id": "team-a", "owner_tag": "owner-1"},
            {"id": "t-dup", "status": "done", "acceptance": "Signoff 2", "accepted_at": "2026-10-07T03:15:00Z", "team_id": "team-a", "owner_tag": "owner-1"},
        ]
        res = summarize_resolved_tasks(tasks=tasks, as_of="2026-10-07T04:00:00Z", window_seconds=7200)
        self.assertEqual(res["resolved_unique_task_ids"], ["t-dup"])
        self.assertEqual(res["resolved_task_count"], 1)
        self.assertEqual(res["by_project"].get("team-a"), 1)
        self.assertEqual(res["by_owner"].get("owner-1"), 1)


class TestResolvedTasksWindowFiltering(unittest.TestCase):
    """Test sliding window filtering (in-window vs older than window) and parsing."""

    def setUp(self):
        self.as_of = "2026-10-07T04:00:00Z"
        self.tasks = [
            {"id": "t-15m", "status": "done", "acceptance": "Accepted", "accepted_at": "2026-10-07T03:45:00Z"},  # 900s age
            {"id": "t-45m", "status": "done", "acceptance": "Accepted", "accepted_at": "2026-10-07T03:15:00Z"},  # 2700s age
            {"id": "t-2d", "status": "done", "acceptance": "Accepted", "accepted_at": "2026-10-05T04:00:00Z"},   # 172800s age
        ]

    def test_window_30m(self):
        res = summarize_resolved_tasks(tasks=self.tasks, as_of=self.as_of, window_seconds=1800)
        self.assertEqual(res["resolved_unique_task_ids"], ["t-15m"])
        self.assertEqual(res["resolved_task_count"], 1)

    def test_window_shorthand_30m(self):
        res = summarize_resolved_tasks(tasks=self.tasks, as_of=self.as_of, window_seconds="30m")
        self.assertEqual(res["resolved_unique_task_ids"], ["t-15m"])
        self.assertEqual(res["window_seconds"], 1800.0)

    def test_window_shorthand_24h(self):
        res = summarize_resolved_tasks(tasks=self.tasks, as_of=self.as_of, window_seconds="24h")
        self.assertEqual(res["resolved_unique_task_ids"], ["t-15m", "t-45m"])
        self.assertEqual(res["resolved_task_count"], 2)
        self.assertEqual(res["window_seconds"], 86400.0)

    def test_window_all_time(self):
        res = summarize_resolved_tasks(tasks=self.tasks, as_of=self.as_of, window_seconds="all")
        self.assertEqual(res["resolved_unique_task_ids"], ["t-15m", "t-2d", "t-45m"])
        self.assertEqual(res["resolved_task_count"], 3)
        self.assertIsNone(res["window_seconds"])

    def test_future_timestamp_excluded(self):
        tasks = [
            {"id": "t-future", "status": "done", "acceptance": "Accepted", "accepted_at": "2026-10-07T05:00:00Z"},  # 1 hour in future
            {"id": "t-now", "status": "done", "acceptance": "Accepted", "accepted_at": "2026-10-07T03:59:00Z"},
        ]
        res = summarize_resolved_tasks(tasks=tasks, as_of=self.as_of, window_seconds=3600)
        self.assertEqual(res["resolved_unique_task_ids"], ["t-now"])
        self.assertEqual(res["resolved_task_count"], 1)

    def test_parse_window_seconds(self):
        ref_dt = datetime.datetime(2026, 10, 7, 4, 0, 0, tzinfo=datetime.timezone.utc)
        self.assertEqual(parse_window_seconds(None, ref_dt), None)
        self.assertEqual(parse_window_seconds("all", ref_dt), None)
        self.assertEqual(parse_window_seconds("all-time", ref_dt), None)
        self.assertEqual(parse_window_seconds(1800, ref_dt), 1800.0)
        self.assertEqual(parse_window_seconds("30m", ref_dt), 1800.0)
        self.assertEqual(parse_window_seconds("24h", ref_dt), 86400.0)
        self.assertEqual(parse_window_seconds("1d", ref_dt), 86400.0)
        self.assertEqual(parse_window_seconds("45s", ref_dt), 45.0)
        self.assertEqual(parse_window_seconds("calendar-day", ref_dt), 4 * 3600.0)


class TestResolvedTasksUnknownTimestamps(unittest.TestCase):
    """Test unknown timestamp preservation (never backfilled to ingestion or now)."""

    def test_unknown_timestamp_preservation_sliding_window(self):
        tasks = [
            {"id": "t-unknown-1", "status": "done", "acceptance": "Valid acceptance"},  # no timestamp at all
            {"id": "t-unknown-2", "status": "done", "acceptance": "Valid acceptance", "accepted_at": "unknown"},  # explicit unknown
            {"id": "t-known", "status": "done", "acceptance": "Valid acceptance", "accepted_at": "2026-10-07T03:50:00Z"},
        ]
        # In a 30m window, unknown timestamps MUST NOT be backfilled to now/as_of:
        res = summarize_resolved_tasks(tasks=tasks, as_of="2026-10-07T04:00:00Z", window_seconds=1800)
        self.assertEqual(res["resolved_unique_task_ids"], ["t-known"])
        self.assertEqual(res["resolved_task_count"], 1)
        self.assertEqual(res["unknown_timestamp_task_ids"], ["t-unknown-1", "t-unknown-2"])
        self.assertEqual(res["unknown_timestamp_count"], 2)

    def test_unknown_timestamp_all_time(self):
        tasks = [
            {"id": "t-unknown", "status": "done", "acceptance": "Valid acceptance", "accepted_at": "unknown"},
        ]
        res = summarize_resolved_tasks(tasks=tasks, as_of="2026-10-07T04:00:00Z", window_seconds=None)
        self.assertIn("t-unknown", res["unknown_timestamp_task_ids"])
        self.assertEqual(res["unknown_timestamp_count"], 1)
        # Freshness and latest_accepted_at stay None when all timestamps are unknown
        self.assertIsNone(res["latest_accepted_at"])
        self.assertIsNone(res["freshness_seconds"])


class TestResolvedTasksReopened(unittest.TestCase):
    """Test reopened task detection and separation without creating duplicate IDs."""

    def test_reopened_detection_via_reopened_flag(self):
        tasks = [
            {"id": "t-reopened-flag", "status": "in_progress", "reopened": True},
        ]
        res = summarize_resolved_tasks(tasks=tasks, as_of="2026-10-07T04:00:00Z", window_seconds=86400)
        self.assertEqual(res["reopened_task_ids"], ["t-reopened-flag"])
        self.assertEqual(res["reopened_count"], 1)
        self.assertEqual(res["resolved_task_count"], 0)

    def test_reopened_detection_via_checkpoint_history(self):
        tasks = [
            {
                "id": "t-reopened-cp",
                "status": "todo",
                "checkpoint_history": [
                    {"status": "done", "outcome": "previously completed", "recorded_at": "2026-10-06T10:00:00Z"}
                ],
            },
        ]
        res = summarize_resolved_tasks(tasks=tasks, as_of="2026-10-07T04:00:00Z", window_seconds=86400)
        self.assertEqual(res["reopened_task_ids"], ["t-reopened-cp"])
        self.assertEqual(res["reopened_count"], 1)
        self.assertEqual(res["resolved_task_count"], 0)

    def test_reopened_does_not_create_duplicate_id_in_window(self):
        tasks = [
            {
                "id": "t-reopened-resolved",
                "status": "done",
                "reopened": True,
                "acceptance": "Re-accepted after regression fix",
                "accepted_at": "2026-10-07T03:30:00Z",
            },
        ]
        res = summarize_resolved_tasks(tasks=tasks, as_of="2026-10-07T04:00:00Z", window_seconds=3600)
        self.assertEqual(res["reopened_task_ids"], ["t-reopened-resolved"])
        self.assertEqual(res["reopened_count"], 1)
        self.assertEqual(res["resolved_unique_task_ids"], ["t-reopened-resolved"])
        self.assertEqual(res["resolved_task_count"], 1)


class TestResolvedTasksEvidenceCoverage(unittest.TestCase):
    """Test on-disk evidence verification and coverage ratio calculation."""

    def test_evidence_coverage_verified_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root_dir = pathlib.Path(tmp)
            ev1 = root_dir / "reports/audit.md"
            ev1.parent.mkdir(parents=True, exist_ok=True)
            ev1.write_text("# Audit report")

            tasks = [
                {
                    "id": "t-verified",
                    "status": "done",
                    "acceptance": "Accepted",
                    "accepted_at": "2026-10-07T03:30:00Z",
                    "evidence_paths": ["reports/audit.md"],
                },
                {
                    "id": "t-missing-file",
                    "status": "done",
                    "acceptance": "Accepted",
                    "accepted_at": "2026-10-07T03:30:00Z",
                    "evidence_paths": ["reports/absent.md"],
                },
                {
                    "id": "t-no-paths",
                    "status": "done",
                    "acceptance": "Accepted",
                    "accepted_at": "2026-10-07T03:30:00Z",
                    "evidence_paths": [],
                },
            ]
            res = summarize_resolved_tasks(tasks=tasks, as_of="2026-10-07T04:00:00Z", window_seconds=3600, root_dir=root_dir)
            cov = res["evidence_coverage"]
            self.assertEqual(cov["verified_count"], 1)
            self.assertEqual(cov["missing_count"], 2)
            self.assertAlmostEqual(cov["coverage_ratio"], 1 / 3, places=4)

    def test_evidence_coverage_zero_tasks(self):
        res = summarize_resolved_tasks(tasks=[], as_of="2026-10-07T04:00:00Z", window_seconds=3600)
        cov = res["evidence_coverage"]
        self.assertEqual(cov["verified_count"], 0)
        self.assertEqual(cov["missing_count"], 0)
        self.assertEqual(cov["coverage_ratio"], 0.0)


class TestResolvedTasksFreshness(unittest.TestCase):
    """Test freshness calculation (seconds since most recent accepted task)."""

    def test_freshness_calculation(self):
        tasks = [
            {"id": "t-older", "status": "done", "acceptance": "OK", "accepted_at": "2026-10-07T03:00:00Z"},
            {"id": "t-newer", "status": "done", "acceptance": "OK", "accepted_at": "2026-10-07T03:30:00Z"},
        ]
        res = summarize_resolved_tasks(tasks=tasks, as_of="2026-10-07T04:00:00Z", window_seconds=7200)
        self.assertEqual(res["latest_accepted_at"], "2026-10-07T03:30:00+00:00")
        self.assertEqual(res["freshness_seconds"], 1800.0)

    def test_freshness_none_when_empty(self):
        res = summarize_resolved_tasks(tasks=[], as_of="2026-10-07T04:00:00Z", window_seconds=7200)
        self.assertIsNone(res["latest_accepted_at"])
        self.assertIsNone(res["freshness_seconds"])


class TestResolvedTasksProjectAndOwner(unittest.TestCase):
    """Test project filtering and breakdown by project and owner."""

    def test_by_project_and_by_owner(self):
        tasks = [
            {"id": "t-1", "status": "done", "acceptance": "OK", "accepted_at": "2026-10-07T03:00:00Z", "project": "proj-a", "owner_tag": "owner-1"},
            {"id": "t-2", "status": "done", "acceptance": "OK", "accepted_at": "2026-10-07T03:10:00Z", "project": "proj-a", "owner_tag": "owner-2"},
            {"id": "t-3", "status": "done", "acceptance": "OK", "accepted_at": "2026-10-07T03:20:00Z", "project": "proj-b", "owner_tag": "owner-1"},
        ]
        res = summarize_resolved_tasks(tasks=tasks, as_of="2026-10-07T04:00:00Z", window_seconds=7200)
        self.assertEqual(res["resolved_task_count"], 3)
        self.assertEqual(res["by_project"], {"proj-a": 2, "proj-b": 1})
        self.assertEqual(res["by_owner"], {"owner-1": 2, "owner-2": 1})

    def test_project_filter(self):
        tasks = [
            {"id": "t-1", "status": "done", "acceptance": "OK", "accepted_at": "2026-10-07T03:00:00Z", "project": "proj-a", "owner_tag": "owner-1"},
            {"id": "t-2", "status": "done", "acceptance": "OK", "accepted_at": "2026-10-07T03:10:00Z", "project": "proj-a", "owner_tag": "owner-2"},
            {"id": "t-3", "status": "done", "acceptance": "OK", "accepted_at": "2026-10-07T03:20:00Z", "project": "proj-b", "owner_tag": "owner-1"},
        ]
        res = summarize_resolved_tasks(tasks=tasks, as_of="2026-10-07T04:00:00Z", window_seconds=7200, project="proj-a")
        self.assertEqual(res["resolved_unique_task_ids"], ["t-1", "t-2"])
        self.assertEqual(res["resolved_task_count"], 2)
        self.assertEqual(res["by_project"], {"proj-a": 2})
        self.assertEqual(res["by_owner"], {"owner-1": 1, "owner-2": 1})


class TestResolvedTasksCli(unittest.TestCase):
    """Test CLI execution with --resolved-tasks, --window, --project, --json."""

    def test_cli_resolved_tasks_json(self):
        cmd = [
            sys.executable,
            str(ROOT / "scripts/metrics/export.py"),
            "--resolved-tasks",
            "--json",
            "--window", "24h",
            "--as-of", "2026-10-07T04:00:00Z",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(proc.stdout)
        self.assertIn("resolved_unique_task_ids", data)
        self.assertIn("resolved_task_count", data)
        self.assertIn("reopened_task_ids", data)
        self.assertIn("reopened_count", data)
        self.assertIn("unknown_timestamp_task_ids", data)
        self.assertIn("unknown_timestamp_count", data)
        self.assertIn("latest_accepted_at", data)
        self.assertIn("freshness_seconds", data)
        self.assertIn("evidence_coverage", data)
        self.assertIn("by_project", data)
        self.assertIn("by_owner", data)
        self.assertEqual(data["window_seconds"], 86400.0)

    def test_cli_resolved_tasks_text_summary(self):
        cmd = [
            sys.executable,
            str(ROOT / "scripts/metrics/export.py"),
            "--resolved-tasks",
            "--window", "30m",
            "--as-of", "2026-10-07T04:00:00Z",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        self.assertIn("Continuation Runtime Resolved Tasks Summary:", proc.stdout)
        self.assertIn("Resolved task count:", proc.stdout)
        self.assertIn("Evidence coverage:", proc.stdout)

    def test_cli_project_filter(self):
        cmd = [
            sys.executable,
            str(ROOT / "scripts/metrics/export.py"),
            "--resolved-tasks",
            "--json",
            "--window", "24h",
            "--project", "quota-launcher",
            "--as-of", "2026-10-07T04:00:00Z",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(proc.stdout)
        self.assertEqual(data["project"], "quota-launcher")
        for proj in data["by_project"]:
            self.assertEqual(proj, "quota-launcher")


class TestResolvedTasksFileLoading(unittest.TestCase):
    """Test loading tasks from custom tasks_path or repo TASKS.json."""

    def test_load_from_custom_tasks_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            tasks_file = pathlib.Path(tmp) / "custom_tasks.json"
            content = {
                "tasks": [
                    {"id": "t-custom", "status": "done", "acceptance": "Verified", "accepted_at": "2026-10-07T03:30:00Z"}
                ]
            }
            tasks_file.write_text(json.dumps(content))
            res = summarize_resolved_tasks(tasks_path=str(tasks_file), as_of="2026-10-07T04:00:00Z", window_seconds=3600)
            self.assertEqual(res["resolved_unique_task_ids"], ["t-custom"])
            self.assertEqual(res["resolved_task_count"], 1)

    def test_load_from_default_repo_tasks(self):
        # Default load uses coordination/TASKS.json
        res = summarize_resolved_tasks(as_of="2026-10-07T04:00:00Z", window_seconds="all")
        self.assertGreater(res["resolved_task_count"], 100)
        self.assertIn("PUBLICATION-SOCIAL-SHARE-DEFAULT-20261006", res["resolved_unique_task_ids"])


class TestRunningAgentsAndCommits(unittest.TestCase):
    """Test running agents and commit metrics collectors and CLI."""

    def test_summarize_running_agents_synthetic(self):
        fake_latest = {
            "aggregate": {"unregistered_live": 2},
            "sessions": [
                {"id": "s1", "tag": "head-1", "role": "head", "team_id": "T1", "engine": "antigravity", "pid_live": True, "reported_state": "working"},
                {"id": "s2", "tag": "worker-1", "role": "executor", "team_id": "T1", "engine": "codex", "pid_live": True, "reported_state": "idle"},
                {"id": "s3", "tag": "worker-2", "role": "executor", "team_id": "T2", "engine": "zcodex", "pid_live": False, "reported_state": "idle"},
                {"id": "s4", "tag": "anon-1", "role": "unknown", "team_id": "unregistered", "engine": "shell", "pid_live": True, "unregistered": True, "reported_state": "working"},
            ]
        }
        res = summarize_running_agents(as_of="2026-10-07T05:00:00Z", latest_data=fake_latest)
        self.assertEqual(res["total_running_agents"], 3)
        self.assertEqual(res["registered_live_count"], 2)
        self.assertEqual(res["unregistered_live_count"], 1)
        self.assertEqual(res["active_working_count"], 2)
        self.assertEqual(res["idle_waiting_count"], 1)
        self.assertEqual(res["by_role"], {"executor": 1, "head": 1, "unknown": 1})
        self.assertEqual(res["by_provider"], {"antigravity": 1, "codex": 1, "shell": 1})
        self.assertEqual(res["by_team"], {"T1": 2, "unregistered": 1})
        self.assertEqual(res["deduplicated_agent_ids"], ["s1", "s2", "s4"])

    def test_summarize_commits_synthetic_repo(self):
        with tempfile.TemporaryDirectory() as td:
            repo_dir = pathlib.Path(td) / "test_repo"
            repo_dir.mkdir()
            subprocess.run(["git", "init"], cwd=str(repo_dir), capture_output=True, check=True)
            subprocess.run(["git", "config", "user.name", "Test Agent"], cwd=str(repo_dir), capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "agent@test.local"], cwd=str(repo_dir), capture_output=True, check=True)
            (repo_dir / "file.txt").write_text("commit 1")
            subprocess.run(["git", "add", "."], cwd=str(repo_dir), capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "first commit"], cwd=str(repo_dir), capture_output=True, check=True)
            (repo_dir / "file.txt").write_text("commit 2")
            subprocess.run(["git", "add", "."], cwd=str(repo_dir), capture_output=True, check=True)
            subprocess.run(["git", "commit", "-m", "second commit"], cwd=str(repo_dir), capture_output=True, check=True)

            res = summarize_commits(window_seconds=86400, repos=[("test_repo", repo_dir)])
            self.assertEqual(res["total_unique_commits"], 2)
            self.assertIn("test_repo", res["per_repo"])
            self.assertEqual(res["per_repo"]["test_repo"]["unique_commit_count"], 2)
            self.assertIsNotNone(res["per_repo"]["test_repo"]["latest_commit_sha"])

    def test_cli_running_agents_and_commits(self):
        script = ROOT / "scripts/metrics/export.py"
        # Test --running-agents --json
        p1 = subprocess.run([sys.executable, str(script), "--running-agents", "--json"], capture_output=True, text=True, check=True)
        d1 = json.loads(p1.stdout)
        self.assertIn("total_running_agents", d1)
        self.assertIn("registered_live_count", d1)

        # Test --commits --json --window 24h
        p2 = subprocess.run([sys.executable, str(script), "--commits", "--window", "24h", "--json"], capture_output=True, text=True, check=True)
        d2 = json.loads(p2.stdout)
        self.assertIn("total_unique_commits", d2)
        self.assertIn("per_repo", d2)


if __name__ == "__main__":
    unittest.main()

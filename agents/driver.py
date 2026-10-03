"""
agents/driver.py - Real-Agent Harness Driver for Agent Branches (L6)

Orchestrates concurrent coding agents running tasks from demo-target/TASKS.md:
1. MemAvailable >= 10 GiB gate check.
2. Task registration via L2 client (POST /tasks).
3. Workspace isolation & fork checkout for each agent.
4. Concurrently launches real coding agents (zcodex, space-bunny, grok, or dry-run reference patches).
5. Runs L3 radar on push events and submits CONTRACT v0.1 checks (POST /checks).
6. Records complete chronological timeline JSON and final evaluation matrix.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import L2 Client and L3 Radar from local workspace
from agent_branches.client import AgentBranchesAPIError, AgentBranchesClient, StaleVectorError
from radar.admission import get_mem_available_mb
from radar.engine import (
    AgentHead,
    PairResult,
    RadarEngine,
    STATUS_CLEAN,
    STATUS_CONFLICT,
    STATUS_NOT_CHECKED,
    STATUS_UNKNOWN,
    export_l1_payload,
)
from agents.prompts import build_agent_prompt


@dataclass
class TaskSpec:
    task_id: str
    title: str
    body: str
    branch: str
    engine: str = "dry-run"
    registered_task_id: Optional[str] = None
    registered_agent_id: Optional[str] = None
    fork_remote: Optional[str] = None
    token: Optional[str] = None
    workspace_dir: Optional[str] = None
    session_id: Optional[str] = None
    head_sha: Optional[str] = None
    test_result: Optional[Dict[str, Any]] = None


@dataclass
class TimelineEvent:
    timestamp: float
    iso_time: str
    event_type: str
    details: Dict[str, Any]


class AgentHarnessDriver:
    """Orchestrates concurrent real-agent execution across Agent Branches."""

    def __init__(
        self,
        server_url: str = "http://127.0.0.1:8787",
        admin_token: Optional[str] = None,
        runner_token: Optional[str] = None,
        demo_target_path: str = "demo-target",
        run_dir: Optional[str] = None,
        min_mem_gate_gb: float = 10.0,
        poll_interval: float = 2.0,
        max_wait_seconds: float = 300.0,
        engine_mode: str = "dry-run",
        skip_worker_alive: bool = False,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.admin_token = admin_token or os.environ.get("ADMIN_TOKEN", "demo-admin-token")
        self.runner_token = runner_token or os.environ.get("RUNNER_TOKEN", "demo-runner-token")
        self.demo_target_path = os.path.abspath(demo_target_path)
        if not os.path.exists(self.demo_target_path):
            candidates = [
                "/home/alexey/git/cloudflare-agent-git/demo-target",
                "/home/alexey/git/agent-branches-live/demo-target",
            ]
            for cand in candidates:
                if os.path.exists(cand):
                    self.demo_target_path = cand
                    break
        try:
            self.repo_root = subprocess.run(
                ["git", "-C", self.demo_target_path, "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        except Exception:
            self.repo_root = os.path.dirname(self.demo_target_path)
        self.min_mem_gate_gb = float(min_mem_gate_gb)
        self.poll_interval = float(poll_interval)
        self.max_wait_seconds = float(max_wait_seconds)
        self.engine_mode = engine_mode
        self.skip_worker_alive = skip_worker_alive

        run_id = f"run-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        self.run_id = run_id
        self.run_dir = os.path.abspath(run_dir or os.path.join(".local", "agents-runs", run_id))
        os.makedirs(self.run_dir, exist_ok=True)

        self.client = AgentBranchesClient(
            server_url=self.server_url,
            timeout=10.0,
            admin_token=self.admin_token,
        )
        self.timeline: List[TimelineEvent] = []
        self.start_time = time.time()
        self._acked_warning_ids: set[str] = set()

    def record_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """Record a structured timeline event."""
        now = time.time()
        evt = TimelineEvent(
            timestamp=now,
            iso_time=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            event_type=event_type,
            details=details,
        )
        self.timeline.append(evt)
        # Flush timeline to disk incrementally
        self.save_timeline()

    def save_timeline(self) -> str:
        """Write current timeline to JSON file."""
        timeline_path = os.path.join(self.run_dir, "timeline.json")
        payload = {
            "run_id": self.run_id,
            "started_at": self.start_time,
            "engine_mode": self.engine_mode,
            "server_url": self.server_url,
            "events_count": len(self.timeline),
            "events": [asdict(e) for e in self.timeline],
        }
        with open(timeline_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return timeline_path

    def check_memory_gate(self) -> float:
        """Enforce Host MemAvailable >= 10 GiB gate."""
        mem_mb = get_mem_available_mb()
        if mem_mb is None:
            raise RuntimeError("Cannot verify memory gate: /proc/meminfo unreadable")
        gate_mb = self.min_mem_gate_gb * 1024.0
        if mem_mb < gate_mb:
            raise RuntimeError(
                f"Memory gate FAIL: MemAvailable {mem_mb:.1f} MB is below required {gate_mb:.1f} MB (>= {self.min_mem_gate_gb} GiB)"
            )
        self.record_event("memory_gate_passed", {"mem_available_mb": mem_mb, "gate_mb": gate_mb})
        return mem_mb

    def verify_worker_alive(self, timeout_seconds: float = 15.0) -> bool:
        """Verify that the L1 Worker is up and responsive before launching agents (worker_alive check)."""
        t0 = time.time()
        while time.time() - t0 < timeout_seconds:
            try:
                status = self.client.get_status()
                if status is not None and isinstance(status, dict):
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def check_provider_quota_gate(self, provider: str, min_percent: float = 10.0) -> Tuple[bool, str, Dict[str, Any]]:
        """Verify provider quota using quse --json before launching real model sessions."""
        try:
            proc = subprocess.run(
                ["quse", "--json"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if proc.returncode != 0:
                return False, f"quse --json failed with exit code {proc.returncode}: {proc.stderr.strip()}", {}
            data = json.loads(proc.stdout)
        except Exception as exc:
            return False, f"quse check execution error: {exc}", {}

        provider_map = {
            "zcodex": "zai",
            "zai": "zai",
            "space-bunny": "go",
            "go": "go",
            "opencode": "go",
            "grok": "grok",
            "codex": "codex",
            "gemini": "gemini",
        }
        key = provider_map.get(provider.lower(), provider.lower())
        if key not in data:
            return False, f"Provider '{provider}' (key '{key}') not found in quse output", data

        info = data[key]
        if info.get("status") != "ok":
            return False, f"Provider '{provider}' status is {info.get('status')} (error: {info.get('error')})", info

        details = info.get("details", {})
        if details.get("limit_reached") is True:
            return False, f"Provider '{provider}' limit_reached is True", info

        # Codex 15% reserve policy check if codex is ever evaluated
        effective_min = 15.0 if key == "codex" else min_percent

        windows = info.get("windows", {})
        valid_windows_checked = 0
        for win_name in ("5h", "7d", "monthly"):
            win = windows.get(win_name)
            if isinstance(win, dict):
                pct = win.get("percent_remaining")
                if pct is not None:
                    valid_windows_checked += 1
                    if float(pct) < effective_min:
                        return False, f"Provider '{provider}' {win_name} quota {pct}% < {effective_min}% threshold", info

        if valid_windows_checked == 0:
            return False, f"Provider '{provider}' has no known valid quota windows reported (fail-closed)", info

        return True, "Quota check passed", info

    def query_remote_head(self, remote_target: str, branch: str, cwd: Optional[str] = None) -> Optional[str]:
        """Query remote repository HEAD SHA using git ls-remote (verifies real remote push, avoiding commits-as-push)."""
        cmd = ["git"]
        if cwd:
            cmd.extend(["-C", cwd])
        cmd.extend(["ls-remote", remote_target, f"refs/heads/{branch}"])
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                lines = proc.stdout.strip().splitlines()
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == f"refs/heads/{branch}":
                        return parts[0]
                if lines:
                    return lines[0].split()[0]
        except Exception:
            pass
        return None

    def parse_tasks(self, tasks_md_path: Optional[str] = None) -> List[TaskSpec]:
        """Parse tasks from TASKS.md into structured TaskSpecs."""
        md_file = tasks_md_path or os.path.join(self.demo_target_path, "TASKS.md")
        if not os.path.exists(md_file):
            raise FileNotFoundError(f"TASKS.md not found at {md_file}")

        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()

        tasks: List[TaskSpec] = []
        sections = re.split(r"^##\s+([A-Za-z0-9_-]+)\s*[—–-]\s*(.+)$", content, flags=re.MULTILINE)
        for i in range(1, len(sections), 3):
            t_id = sections[i].strip()
            t_title = sections[i + 1].strip()
            t_body = sections[i + 2].strip()
            tasks.append(
                TaskSpec(
                    task_id=t_id,
                    title=t_title,
                    body=t_body,
                    branch=f"feat/{t_id.lower()}",
                )
            )

        # Assign engine per task based on engine_mode
        for idx, t in enumerate(tasks):
            if self.engine_mode == "multi-model":
                engines = ["zcodex", "space-bunny", "grok"]
                t.engine = engines[idx % len(engines)]
            else:
                t.engine = self.engine_mode

        self.record_event("tasks_parsed", {"count": len(tasks), "tasks": [t.task_id for t in tasks]})
        return tasks

    def get_base_commit_sha(self) -> str:
        """Get the base commit SHA of demo-target repository."""
        for candidate in [
            os.path.join(self.demo_target_path, "reference-solutions", "BASE"),
            os.path.join(self.demo_target_path, ".harness", "BASE"),
            os.path.join(self.demo_target_path, "BASE"),
        ]:
            if os.path.exists(candidate):
                with open(candidate, "r", encoding="utf-8") as f:
                    sha = f.read().strip()
                    if sha:
                        return sha
        proc = subprocess.run(
            ["git", "-C", self.repo_root, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout.strip()

    def register_tasks(self, tasks: List[TaskSpec], base_sha: str) -> None:
        """Register tasks with the L1 Coordinator via L2 Client."""
        for t in tasks:
            res = self.client.create_task(
                repo=self.demo_target_path,
                base_sha=base_sha,
                intent=f"{t.task_id}: {t.title}",
                branch=t.branch,
                admin_token=self.admin_token,
            )
            t.registered_task_id = res.get("taskId") or res.get("id") or res.get("task_id")
            t.registered_agent_id = res.get("agentId") or res.get("agent_id") or res.get("agent")
            t.fork_remote = (
                res.get("forkRemote")
                or res.get("forkUrl")
                or res.get("fork_url")
                or (res.get("fork") or {}).get("remote")
            )
            tok_obj = res.get("token")
            if isinstance(tok_obj, dict):
                t.token = tok_obj.get("plaintext") or tok_obj.get("token")
            elif isinstance(tok_obj, str):
                t.token = tok_obj
            t.head_sha = base_sha

            self.record_event(
                "task_registered",
                {
                    "task_id": t.task_id,
                    "title": t.title,
                    "assigned_task_id": t.registered_task_id,
                    "assigned_agent_id": t.registered_agent_id,
                    "branch": t.branch,
                    "fork_remote": t.fork_remote,
                    "engine": t.engine,
                },
            )

    def setup_workspaces(self, tasks: List[TaskSpec], base_sha: str) -> None:
        """Create isolated clone/workspace for each agent with genuine remote tracking."""
        workspaces_root = os.path.join(self.run_dir, "workspaces")
        remotes_root = os.path.join(self.run_dir, "remotes")
        os.makedirs(workspaces_root, exist_ok=True)
        os.makedirs(remotes_root, exist_ok=True)

        for t in tasks:
            ws_dir = os.path.join(workspaces_root, t.task_id.lower())
            os.makedirs(ws_dir, exist_ok=True)
            t.workspace_dir = ws_dir

            # Initialize git clone from repo_root checked out at base_sha
            subprocess.run(["git", "clone", "--quiet", self.repo_root, ws_dir], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", ws_dir, "config", "user.name", f"Agent {t.task_id} ({t.engine})"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", ws_dir, "config", "user.email", f"agent-{t.task_id.lower()}@demo.local"],
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "-C", ws_dir, "checkout", "-q", "-b", t.branch, base_sha], check=True, capture_output=True)

            # Ensure genuine remote repository for fork (bare repo if mock/local, or remote HTTP URL)
            is_mock_remote = not t.fork_remote or "cloudflare.local" in t.fork_remote or "example.com" in t.fork_remote
            if is_mock_remote:
                bare_repo = os.path.join(remotes_root, f"fork-{t.task_id.lower()}.git")
                if not os.path.exists(bare_repo):
                    subprocess.run(["git", "init", "--bare", "--quiet", bare_repo], check=True, capture_output=True)
                    subprocess.run(
                        ["git", "-C", self.repo_root, "push", "--quiet", bare_repo, f"{base_sha}:refs/heads/main", f"{base_sha}:refs/heads/{t.branch}"],
                        check=True,
                        capture_output=True,
                    )
                t.fork_remote = bare_repo

            # Point origin to fork_remote
            subprocess.run(["git", "-C", ws_dir, "remote", "set-url", "origin", t.fork_remote], check=True, capture_output=True)

            # Configure bearer auth header for HTTP remotes if token exists
            if t.token:
                subprocess.run(
                    ["git", "-C", ws_dir, "config", "http.extraHeader", f"Authorization: Bearer {t.token}"],
                    check=True,
                    capture_output=True,
                )

            # Create helper wrapper for agent-branches CLI inside agent workspace
            bin_dir = os.path.join(ws_dir, ".bin")
            os.makedirs(bin_dir, exist_ok=True)
            cli_wrapper = os.path.join(bin_dir, "agent-branches")
            harness_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
            with open(cli_wrapper, "w", encoding="utf-8") as f:
                f.write(
                    f"#!/usr/bin/env bash\n"
                    f"export PYTHONPATH=\"{harness_root}:${{PYTHONPATH}}\"\n"
                    f"exec python3 -m agent_branches.cli --server {self.server_url} \"$@\"\n"
                )
            os.chmod(cli_wrapper, 0o755)

            # Also create helper in workspace root so both PATH and ./agent-branches work
            ws_cli = os.path.join(ws_dir, "agent-branches")
            if not os.path.exists(ws_cli):
                try:
                    os.symlink(cli_wrapper, ws_cli)
                except OSError:
                    shutil.copy2(cli_wrapper, ws_cli)

            # Exclude harness helper files from git tracking
            exclude_file = os.path.join(ws_dir, ".git", "info", "exclude")
            with open(exclude_file, "a", encoding="utf-8") as f:
                f.write("\n.bin/\nagent-branches\nAGENT_TASK.md\n")

            # Ensure agent workspace gets ONLY the base code: scrub reference solutions and solutions docs
            for scrub_target in ["reference-solutions", ".harness", "SOLUTIONS.md", "verify-overlap.sh", "verify-overlap.work.sh"]:
                st_path = os.path.join(ws_dir, scrub_target)
                if os.path.isdir(st_path):
                    shutil.rmtree(st_path, ignore_errors=True)
                elif os.path.isfile(st_path):
                    try:
                        os.remove(st_path)
                    except OSError:
                        pass
                # Also scrub inside demo-target subdirectory if present
                st_sub = os.path.join(ws_dir, "demo-target", scrub_target)
                if os.path.isdir(st_sub):
                    shutil.rmtree(st_sub, ignore_errors=True)
                elif os.path.isfile(st_sub):
                    try:
                        os.remove(st_sub)
                    except OSError:
                        pass

            self.record_event(
                "workspace_created",
                {
                    "task_id": t.task_id,
                    "workspace": ws_dir,
                    "branch": t.branch,
                    "base_sha": base_sha,
                },
            )

    def launch_agents(self, tasks: List[TaskSpec]) -> None:
        """Launch coding agents concurrently across task workspaces."""
        for t in tasks:
            ws_dir = t.workspace_dir
            assert ws_dir is not None

            prompt_text = build_agent_prompt(
                task_id=t.task_id,
                title=t.title,
                body=t.body,
                branch=t.branch,
                server_url=self.server_url,
                agent_id=t.registered_agent_id,
            )

            # Write prompt to workspace file for reference
            prompt_file = os.path.join(ws_dir, "AGENT_TASK.md")
            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(prompt_text)

            if t.engine == "dry-run":
                # Apply reference solution patch
                patch_candidates = [
                    os.path.join(self.demo_target_path, ".harness", "reference-solutions", f"{t.task_id.lower()}.patch"),
                    os.path.join(self.demo_target_path, "reference-solutions", f"{t.task_id.lower()}.patch"),
                    os.path.join(self.demo_target_path, ".harness", f"{t.task_id.lower()}.patch"),
                ]
                patch_file = None
                for cand in patch_candidates:
                    if os.path.exists(cand):
                        patch_file = cand
                        break
                if not patch_file:
                    raise FileNotFoundError(f"Reference patch missing for {t.task_id.lower()} across candidates: {patch_candidates}")

                # Apply patch and commit
                apply_proc = subprocess.run(
                    ["git", "-C", ws_dir, "apply", "--index", patch_file],
                    capture_output=True,
                    text=True,
                )
                if apply_proc.returncode != 0:
                    subprocess.run(["git", "-C", ws_dir, "apply", patch_file], check=True, capture_output=True)
                    subprocess.run(["git", "-C", ws_dir, "add", "-u"], check=True, capture_output=True)
                    if os.path.exists(os.path.join(ws_dir, "demo-target")):
                        subprocess.run(["git", "-C", ws_dir, "add", "demo-target/"], check=True, capture_output=True)

                subprocess.run(
                    ["git", "-C", ws_dir, "commit", "-m", f"feat({t.task_id.lower()}): {t.title}"],
                    check=True,
                    capture_output=True,
                )
                rev_proc = subprocess.run(
                    ["git", "-C", ws_dir, "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                head_sha = rev_proc.stdout.strip()
                t.head_sha = head_sha

                # Execute genuine git push to origin remote repository
                push_proc = subprocess.run(
                    ["git", "-C", ws_dir, "push", "origin", f"HEAD:{t.branch}"],
                    capture_output=True,
                    text=True,
                )
                if push_proc.returncode != 0:
                    raise RuntimeError(f"git push origin {t.branch} failed: {push_proc.stderr.strip() or push_proc.stdout.strip()}")

                # Verify remote ref matches head_sha via git ls-remote (verifies remote push, avoiding commits-as-push)
                remote_sha = self.query_remote_head("origin", t.branch, cwd=ws_dir)
                if not remote_sha or remote_sha != head_sha:
                    raise RuntimeError(f"git ls-remote verification failed: remote SHA {remote_sha} != local {head_sha}")

                # Notify coordinator of push via L2 Client
                assert t.registered_task_id is not None
                assert t.registered_agent_id is not None
                self.client.push(
                    task_id=t.registered_task_id,
                    head_sha=head_sha,
                    agent_id=t.registered_agent_id,
                )

                self.record_event(
                    "dry_run_patch_applied",
                    {
                        "task_id": t.task_id,
                        "head_sha": head_sha,
                        "remote_sha": remote_sha,
                        "remote_verified_via_ls_remote": True,
                        "patch": os.path.basename(patch_file),
                        "status": "pushed_and_verified",
                    },
                )
            else:
                # Quota gate check before launching real model sessions
                passed, reason, qinfo = self.check_provider_quota_gate(t.engine)
                if not passed:
                    raise RuntimeError(f"Quota gate rejected launch for {t.engine}: {reason}")
                self.record_event("quota_gate_verified", {"provider": t.engine, "details": qinfo})

                # Real agent launch via aplexer
                session_tag = f"l6-agent-{t.task_id.lower()}-{self.run_id[:8]}"
                cmd: List[str] = []
                if t.engine == "zcodex":
                    cmd = ["zcodex", "exec", "--dangerously-bypass-approvals-and-sandbox", prompt_text]
                elif t.engine == "space-bunny":
                    cmd = ["opencode", "run", "--model", "opencode/space-bunny-free", prompt_text]
                elif t.engine == "grok":
                    cmd = ["grok", prompt_text]
                else:
                    cmd = ["bash", "-c", f"echo 'Running {t.task_id}'; sleep 2"]

                bin_dir = os.path.join(ws_dir, ".bin")
                aplexer_cmd = [
                    "aplexer",
                    "start",
                    "--workspace",
                    ws_dir,
                    "--tag",
                    session_tag,
                    "--fresh",
                    "--memory",
                    "1500M",
                    "--env",
                    f"PATH={bin_dir}:{os.environ.get('PATH', '')}",
                    "--",
                ] + cmd

                proc = subprocess.run(aplexer_cmd, capture_output=True, text=True)
                session_id = proc.stdout.strip() if proc.returncode == 0 else f"failed-{proc.returncode}"
                t.session_id = session_id

                self.record_event(
                    "agent_launched",
                    {
                        "task_id": t.task_id,
                        "engine": t.engine,
                        "session_tag": session_tag,
                        "session_id": session_id,
                        "command": " ".join(cmd[:3]) + " ...",
                    },
                )

    def evaluate_radar(self, tasks: List[TaskSpec], base_sha: str) -> Dict[str, Any]:
        """Run L3 Radar pairwise evaluation across active task heads and submit CONTRACT v0.1 checks."""
        # Ensure repo_root has all task commit objects in its store
        for t in tasks:
            if t.head_sha and t.workspace_dir:
                try:
                    subprocess.run(
                        ["git", "-C", self.repo_root, "fetch", "--quiet", t.workspace_dir, t.head_sha],
                        capture_output=True,
                    )
                except Exception:
                    pass

        radar = RadarEngine(repo_path=self.repo_root, test_command=["node", "--test"])
        active_heads = [
            AgentHead(
                id=t.registered_agent_id or t.task_id,
                sha=t.head_sha or base_sha,
                base_sha=base_sha,
                branch=t.branch,
                intent=t.title,
            )
            for t in tasks
            if t.head_sha
        ]

        if len(active_heads) < 2:
            return {"evaluated": False, "reason": "less_than_two_active_heads"}

        # Run radar matrix
        report = radar.run_matrix(active_heads, base_sha=base_sha)
        results: List[PairResult] = report.pairs

        # Export CONTRACT v0.1 payload
        payload = export_l1_payload(results, engine=radar)

        # Post checks to L1 Coordinator via L2 Client
        post_res = self.client.send_checks(payload, runner_token=self.runner_token)

        # Retrieve coordinator status to observe generated warnings
        coord_status = self.client.get_status()

        self.record_event(
            "radar_evaluated",
            {
                "heads_vector": payload["vector"],
                "pairs_checked": payload["coverage"]["pairs_checked"],
                "results": [
                    {
                        "pair": r.pair,
                        "status": r.status,
                        "kind": r.kind,
                        "is_conflict": r.is_conflict,
                        "error": r.error,
                    }
                    for r in results
                ],
                "coordinator_accepted": post_res.get("accepted"),
                "active_warnings": coord_status.get("warnings", []),
            },
        )

        return {
            "evaluated": True,
            "results": results,
            "payload": payload,
            "coordinator_status": coord_status,
        }

    def evaluate_combined_merge(self, tasks: List[TaskSpec], base_sha: str) -> Dict[str, Any]:
        """Evaluate sequential combined merge of all task heads and run test suite."""
        scratch_dir = tempfile.mkdtemp(prefix="combined_merge_")
        try:
            subprocess.run(["git", "clone", "--quiet", self.repo_root, scratch_dir], check=True)
            subprocess.run(["git", "-C", scratch_dir, "config", "user.name", "Agent Branches Harness"], check=True)
            subprocess.run(["git", "-C", scratch_dir, "config", "user.email", "harness@demo.local"], check=True)
            subprocess.run(["git", "-C", scratch_dir, "checkout", "-q", base_sha], check=True)

            for t in tasks:
                if not t.head_sha or not t.workspace_dir:
                    continue
                subprocess.run(
                    ["git", "-C", scratch_dir, "fetch", "--quiet", t.workspace_dir, t.head_sha],
                    check=True,
                )
                merge_proc = subprocess.run(
                    ["git", "-C", scratch_dir, "merge", "--no-commit", "--no-ff", "FETCH_HEAD"],
                    capture_output=True,
                    text=True,
                )
                if merge_proc.returncode != 0:
                    diff_proc = subprocess.run(
                        ["git", "-C", scratch_dir, "diff", "--name-only", "--diff-filter=U"],
                        capture_output=True,
                        text=True,
                    )
                    conflicts = [f.strip() for f in diff_proc.stdout.splitlines() if f.strip()]
                    res = {
                        "status": "conflict",
                        "kind": "textual",
                        "conflicting_task": t.task_id,
                        "conflicting_files": conflicts,
                        "merge_stderr": merge_proc.stderr.strip() or merge_proc.stdout.strip(),
                    }
                    self.record_event("combined_merge_evaluated", res)
                    return res
                subprocess.run(
                    ["git", "-C", scratch_dir, "commit", "-m", f"merge: {t.task_id}"],
                    check=True,
                    capture_output=True,
                )

            # All heads merged textually; run tests on combined tree
            test_cwd = (
                os.path.join(scratch_dir, "demo-target")
                if os.path.exists(os.path.join(scratch_dir, "demo-target", "package.json"))
                else scratch_dir
            )
            test_proc = subprocess.run(
                ["node", "--test"],
                cwd=test_cwd,
                capture_output=True,
                text=True,
            )
            if test_proc.returncode == 0:
                res = {
                    "status": "clean",
                    "kind": None,
                    "tests_passed": True,
                    "stdout_tail": test_proc.stdout[-500:] if test_proc.stdout else "",
                }
            else:
                res = {
                    "status": "conflict",
                    "kind": "test",
                    "tests_passed": False,
                    "stdout_tail": test_proc.stdout[-500:] if test_proc.stdout else "",
                    "stderr_tail": test_proc.stderr[-500:] if test_proc.stderr else "",
                }
            self.record_event("combined_merge_evaluated", res)
            return res
        except Exception as exc:
            res = {
                "status": "unknown",
                "error": str(exc),
            }
            self.record_event("combined_merge_evaluated", res)
            return res
        finally:
            shutil.rmtree(scratch_dir, ignore_errors=True)

    def monitor_live_agents(self, tasks: List[TaskSpec], base_sha: str) -> None:
        """Monitor running agents, detect pushes, evaluate radar periodically, and record timeline."""
        poll_start = time.time()
        last_check_time = 0.0
        check_interval = max(5.0, self.poll_interval)

        while time.time() - poll_start < self.max_wait_seconds:
            any_head_changed = False
            for t in tasks:
                if not t.workspace_dir:
                    continue
                # Detect genuine remote push via git ls-remote (avoiding commits-as-push)
                remote_sha = self.query_remote_head("origin", t.branch, cwd=t.workspace_dir)
                if remote_sha and remote_sha != t.head_sha:
                    old_sha = t.head_sha
                    t.head_sha = remote_sha
                    any_head_changed = True
                    self.record_event(
                        "agent_push_detected_via_ls_remote",
                        {
                            "task_id": t.task_id,
                            "old_sha": old_sha,
                            "new_sha": remote_sha,
                            "verified_via": "git ls-remote",
                        },
                    )
                    if t.registered_task_id and t.registered_agent_id:
                        try:
                            self.client.push(
                                task_id=t.registered_task_id,
                                head_sha=remote_sha,
                                agent_id=t.registered_agent_id,
                            )
                            self.record_event(
                                "push_registered",
                                {
                                    "task_id": t.task_id,
                                    "head_sha": remote_sha,
                                },
                            )
                        except Exception as exc:
                            self.record_event(
                                "push_registration_error",
                                {
                                    "task_id": t.task_id,
                                    "error": str(exc),
                                },
                            )
                else:
                    # Informational check: check if agent committed locally without running git push yet
                    try:
                        local_rev = subprocess.run(
                            ["git", "-C", t.workspace_dir, "rev-parse", "HEAD"],
                            capture_output=True,
                            text=True,
                            timeout=5,
                        )
                        if local_rev.returncode == 0:
                            local_sha = local_rev.stdout.strip()
                            if local_sha and local_sha != (remote_sha or base_sha):
                                self.record_event(
                                    "unpushed_local_commits_detected",
                                    {
                                        "task_id": t.task_id,
                                        "local_sha": local_sha,
                                        "remote_sha": remote_sha or base_sha,
                                        "note": "Commit is local only; waiting for agent git push before registering push",
                                    },
                                )
                    except Exception:
                        pass

            # Check aplexer session liveness
            all_done = True
            for t in tasks:
                if not t.session_id or t.session_id.startswith("failed"):
                    continue
                try:
                    stat_proc = subprocess.run(
                        ["aplexer", "status", t.session_id, "--json"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if stat_proc.returncode == 0:
                        session_info = json.loads(stat_proc.stdout)
                        worker_alive = bool(session_info.get("worker_alive", False) or session_info.get("alive", False))
                        phase = session_info.get("phase") or session_info.get("state") or ""
                        reported_state = session_info.get("reported_state") or ""
                        if worker_alive and (phase in ("running", "working", "waiting") or reported_state in ("running", "working", "waiting")):
                            all_done = False
                except Exception:
                    pass

            # Check for warning acknowledgements from coordinator
            try:
                coord_status = self.client.get_status()
                for w in coord_status.get("warnings", []):
                    w_id = w.get("warningId")
                    if w.get("acknowledged") and w_id not in self._acked_warning_ids:
                        self._acked_warning_ids.add(w_id)
                        self.record_event(
                            "warning_acknowledged",
                            {
                                "warning_id": w_id,
                                "pair": w.get("pair"),
                                "kind": w.get("kind"),
                            },
                        )
            except Exception:
                pass

            # Run radar if any head changed or check interval elapsed
            now = time.time()
            if any_head_changed or (now - last_check_time >= check_interval):
                last_check_time = now
                try:
                    self.evaluate_radar(tasks, base_sha)
                except Exception as exc:
                    self.record_event("radar_evaluation_error", {"error": str(exc)})

            if all_done:
                self.record_event(
                    "all_agents_completed",
                    {
                        "elapsed_seconds": round(time.time() - poll_start, 2),
                    },
                )
                break

            time.sleep(self.poll_interval)

    def verify_agent_workspaces(self, tasks: List[TaskSpec]) -> Dict[str, Any]:
        """Run node --test in each workspace to verify task-level correctness."""
        results: Dict[str, Any] = {}
        for t in tasks:
            assert t.workspace_dir is not None
            test_cwd = (
                os.path.join(t.workspace_dir, "demo-target")
                if os.path.exists(os.path.join(t.workspace_dir, "demo-target", "package.json"))
                else t.workspace_dir
            )
            test_proc = subprocess.run(
                ["node", "--test"],
                cwd=test_cwd,
                capture_output=True,
                text=True,
            )
            passed = test_proc.returncode == 0
            res = {
                "task_id": t.task_id,
                "passed": passed,
                "exit_code": test_proc.returncode,
                "stdout_tail": test_proc.stdout[-500:] if test_proc.stdout else "",
                "stderr_tail": test_proc.stderr[-500:] if test_proc.stderr else "",
            }
            t.test_result = res
            results[t.task_id] = res

        self.record_event("task_tests_verified", results)
        return results

    def run(self) -> Dict[str, Any]:
        """Execute full harness flow."""
        self.record_event("harness_started", {"run_id": self.run_id, "engine_mode": self.engine_mode})

        # 0. Check worker_alive before starting
        if not self.skip_worker_alive:
            if not self.verify_worker_alive():
                raise RuntimeError(
                    f"worker_alive check failed: Worker at {self.server_url} is not responding (endpoint /status unavailable)"
                )
            self.record_event("worker_alive_verified", {"server_url": self.server_url})

        # 1. Check memory gate
        self.check_memory_gate()

        # 2. Parse tasks
        tasks = self.parse_tasks()
        base_sha = self.get_base_commit_sha()

        # 3. Register tasks
        self.register_tasks(tasks, base_sha)

        # 4. Setup workspaces
        self.setup_workspaces(tasks, base_sha)

        # 5. Launch agents
        self.launch_agents(tasks)

        # If live agents, monitor until completion, push events, or timeout
        if self.engine_mode != "dry-run":
            self.monitor_live_agents(tasks, base_sha)

        # 6. Evaluate radar
        radar_summary = self.evaluate_radar(tasks, base_sha)

        # 7. Evaluate combined merge
        combined_merge_summary = self.evaluate_combined_merge(tasks, base_sha)

        # 8. Verify individual workspace tests
        test_summary = self.verify_agent_workspaces(tasks)

        self.record_event(
            "harness_completed",
            {
                "run_id": self.run_id,
                "duration_seconds": round(time.time() - self.start_time, 2),
                "tasks_count": len(tasks),
            },
        )

        timeline_path = self.save_timeline()

        return {
            "run_id": self.run_id,
            "timeline_path": timeline_path,
            "tasks": [asdict(t) for t in tasks],
            "radar_summary": radar_summary,
            "combined_merge_summary": combined_merge_summary,
            "test_summary": test_summary,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="L6 Real-Agent Harness Driver for Agent Branches")
    parser.add_argument("--server", default="http://127.0.0.1:8787", help="L1 Worker / DO Coordinator URL")
    parser.add_argument("--admin-token", default=None, help="Admin bearer token for POST /tasks")
    parser.add_argument("--runner-token", default=None, help="Runner bearer token for POST /checks")
    parser.add_argument("--demo-target", default="demo-target", help="Path to demo-target repository")
    parser.add_argument("--run-dir", default=None, help="Custom directory to store run artifacts")
    parser.add_argument(
        "--engine-mode",
        choices=["dry-run", "zcodex", "space-bunny", "grok", "multi-model"],
        default="dry-run",
        help="Execution engine for tasks (default: dry-run)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Run with reference solution patches instead of live models")
    parser.add_argument("--skip-worker-alive", action="store_true", help="Skip pre-flight Worker /status health check")
    parser.add_argument("--min-mem-gb", type=float, default=10.0, help="Minimum MemAvailable gate in GiB")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Radar polling interval in seconds")
    parser.add_argument("--max-wait", type=float, default=300.0, help="Maximum execution wait time in seconds")
    parser.add_argument("--json", action="store_true", help="Print output summary as JSON")

    args = parser.parse_args()
    if args.dry_run:
        args.engine_mode = "dry-run"

    driver = AgentHarnessDriver(
        server_url=args.server,
        admin_token=args.admin_token,
        runner_token=args.runner_token,
        demo_target_path=args.demo_target,
        run_dir=args.run_dir,
        min_mem_gate_gb=args.min_mem_gb,
        poll_interval=args.poll_interval,
        max_wait_seconds=args.max_wait,
        engine_mode=args.engine_mode,
        skip_worker_alive=args.skip_worker_alive,
    )

    try:
        results = driver.run()
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            print(f"=== L6 Agent Harness Completed Successfully ===")
            print(f"Run ID:        {results['run_id']}")
            print(f"Timeline JSON: {results['timeline_path']}")
            print(f"Tasks:         {len(results['tasks'])}")
            for t in results["tasks"]:
                test_stat = "PASS" if t.get("test_result", {}).get("passed") else "FAIL"
                print(f"  - {t['task_id']} ({t['engine']}): tests {test_stat}, head: {t['head_sha'][:8] if t['head_sha'] else 'none'}")
    except Exception as exc:
        print(f"ERROR: Harness execution failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

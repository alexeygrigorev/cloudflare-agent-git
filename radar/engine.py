"""L3 Advisory Radar Engine.

Provides in-memory pairwise trial-merges using git merge-tree --write-tree,
detects conflicting edits with zero checkout/disk overhead, and runs budgeted
semantic tests against merged snapshots on clean trial-merges.

Status Enum Contract:
- Strictly one of: 'conflict' | 'clean' | 'unknown' | 'not_checked'
  - 'conflict': Textual merge conflict (kind='textual') or semantic test failure (kind='test').
  - 'clean': Both textual merge is clean AND tests positively executed with > 0 collected tests passing.
  - 'unknown': Missing commit objects, execution timeout, 0 tests collected, or check failure.
  - 'not_checked': Disjoint / non-overlapping files where tests were not run.

Strict Invariants:
- Never safe by default: broad is_safe is removed. Output report is {status, kind, evidence}.
- Process group isolation: preexec_fn=os.setsid with os.killpg(SIGKILL) on timeout.
- Total wall-clock timeout budget.
- Clean sanitized execution environment.
- Safe archive extraction preventing directory traversal and symlink escapes.
- Git merge-tree syntax uses --merge-base=<base>.

Reference:
- research/antigravity/agent-branches/CONTRACT-L2-L3.md
- research/claude/spike-a01-merge-matrix.md
"""

from __future__ import annotations

import argparse
import io
import itertools
import json
import os
import pickle
import re
import resource
import select
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Strict Status Enum Values
STATUS_CONFLICT = "conflict"
STATUS_CLEAN = "clean"
STATUS_UNKNOWN = "unknown"
STATUS_NOT_CHECKED = "not_checked"

VALID_STATUSES = {
    STATUS_CONFLICT,
    STATUS_CLEAN,
    STATUS_UNKNOWN,
    STATUS_NOT_CHECKED,
}


@dataclass
class AgentHead:
    """Represents an active agent commit head vector."""

    id: str
    sha: str
    base_sha: Optional[str] = None
    branch: Optional[str] = None
    intent: Optional[str] = None

    @classmethod
    def from_item(cls, item: Any, default_base: Optional[str] = None) -> AgentHead:
        """Coerce an item into an AgentHead instance."""
        if isinstance(item, AgentHead):
            if not item.base_sha and default_base:
                return cls(
                    id=item.id,
                    sha=item.sha,
                    base_sha=default_base,
                    branch=item.branch,
                    intent=item.intent,
                )
            return item

        if isinstance(item, dict):
            agent_id = str(
                item.get("id")
                or item.get("agent_id")
                or item.get("task_id")
                or f"agent-{uuid.uuid4().hex[:6]}"
            )
            head_sha = str(item.get("sha") or item.get("head_sha") or "").strip()
            base_sha = item.get("base_sha") or default_base
            branch = item.get("branch")
            intent = item.get("intent")
            return cls(
                id=agent_id,
                sha=head_sha,
                base_sha=base_sha,
                branch=branch,
                intent=intent,
            )

        if isinstance(item, (tuple, list)) and len(item) >= 2:
            return cls(id=str(item[0]), sha=str(item[1]).strip(), base_sha=default_base)

        if isinstance(item, str):
            clean_str = item.strip()
            if "=" in clean_str:
                parts = clean_str.split("=", 1)
                return cls(id=parts[0].strip(), sha=parts[1].strip(), base_sha=default_base)
            return cls(id=f"head-{clean_str[:8]}", sha=clean_str, base_sha=default_base)

        raise ValueError(f"Cannot parse AgentHead from: {repr(item)}")


class PairResult(dict):
    """Result of evaluating a pairwise trial-merge between two agent heads.

    Adheres strictly to the status enum: 'conflict' | 'clean' | 'unknown' | 'not_checked'.
    Output report format provides: {status, kind, evidence}.
    """

    def __init__(
        self,
        status: str,  # strictly 'conflict' | 'clean' | 'unknown' | 'not_checked'
        kind: Optional[str] = None,  # 'textual' | 'test' | None
        evidence: Optional[Dict[str, Any]] = None,
        pair: Optional[List[str]] = None,
        heads: Optional[Dict[str, str]] = None,
        warning: Optional[Dict[str, Any]] = None,
        tree_sha: Optional[str] = None,
        overlapping_files: Optional[List[str]] = None,
        error: Optional[str] = None,
    ):
        status_norm = status.lower()
        if status_norm not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}")

        data = {
            "status": status_norm,
            "kind": kind or (warning.get("kind") if warning else None),
            "evidence": evidence or (warning.get("evidence") if warning else {}),
            "pair": list(pair or []),
            "heads": dict(heads or {}),
            "warning": warning,
            "tree_sha": tree_sha,
            "overlapping_files": list(overlapping_files or []),
            "error": error,
        }
        super().__init__(data)

    @property
    def status(self) -> str:
        return self["status"]

    @property
    def kind(self) -> Optional[str]:
        return self["kind"]

    @property
    def evidence(self) -> Dict[str, Any]:
        return self["evidence"]

    @property
    def warning(self) -> Optional[Dict[str, Any]]:
        return self["warning"]

    @property
    def warning_id(self) -> Optional[str]:
        return self["warning"].get("warning_id") if self["warning"] else None

    @property
    def tree_sha(self) -> Optional[str]:
        return self["tree_sha"]

    @property
    def pair(self) -> List[str]:
        return self["pair"]

    @property
    def heads(self) -> Dict[str, str]:
        return self["heads"]

    @property
    def overlapping_files(self) -> List[str]:
        return self["overlapping_files"]

    @property
    def error(self) -> Optional[str]:
        return self["error"]

    @property
    def is_clean(self) -> bool:
        return self["status"] == STATUS_CLEAN

    @property
    def is_conflict(self) -> bool:
        return self["status"] == STATUS_CONFLICT

    @property
    def is_unknown(self) -> bool:
        return self["status"] == STATUS_UNKNOWN

    @property
    def is_not_checked(self) -> bool:
        return self["status"] == STATUS_NOT_CHECKED

    def report(self) -> Dict[str, Any]:
        """Return the minimal standard report {status, kind, evidence}."""
        return {
            "status": self["status"],
            "kind": self["kind"],
            "evidence": self["evidence"],
        }

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            return self.status.lower() == other.lower()
        return super().__eq__(other)

    def __repr__(self) -> str:
        k = self.kind or "none"
        return f"<PairResult pair={self.pair} status='{self.status}' kind='{k}'>"


class MatrixResult(dict):
    """Result of evaluating an active head vector matrix."""

    def __init__(
        self,
        pairs: List[PairResult],
        warnings: List[Dict[str, Any]],
        summary: Dict[str, Any],
        duration_seconds: float,
    ):
        matrix_dict = {f"{p.pair[0]}+{p.pair[1]}": p for p in pairs}
        data = {
            "summary": summary,
            "duration_seconds": duration_seconds,
            "warnings": warnings,
            "matrix": matrix_dict,
            "pairs": pairs,
        }
        super().__init__(data)

    @property
    def warnings(self) -> List[Dict[str, Any]]:
        return self["warnings"]

    @property
    def pairs(self) -> List[PairResult]:
        return self["pairs"]

    @property
    def matrix(self) -> Dict[str, PairResult]:
        return self["matrix"]

    @property
    def summary(self) -> Dict[str, Any]:
        return self["summary"]

    @property
    def duration_seconds(self) -> float:
        return self["duration_seconds"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "duration_seconds": self.duration_seconds,
            "warnings": self.warnings,
            "matrix": {k: dict(v) for k, v in self.matrix.items()},
            "pairs": [dict(p) for p in self.pairs],
        }


def create_warning(
    pair: List[str],
    heads: Dict[str, str],
    kind: str,  # "textual" | "test"
    evidence: Dict[str, Any],
    warning_id: Optional[str] = None,
    created_at_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """Build a standard L3 warning dictionary adhering to CONTRACT-L2-L3."""
    if warning_id is None:
        warning_id = f"01a1warn-{uuid.uuid4().hex[:12]}"
    if created_at_ms is None:
        created_at_ms = int(time.time() * 1000)
    return {
        "warning_id": warning_id,
        "pair": list(pair),
        "heads": dict(heads),
        "kind": kind,
        "evidence": evidence,
        "created_at_ms": created_at_ms,
    }


def parse_collected_test_count(output: str) -> Optional[int]:
    """Parse the number of collected / executed tests from runner output."""
    # unittest format: "Ran X test(s) in Ys"
    m_unit = re.search(r"Ran (\d+) tests?", output)
    if m_unit:
        return int(m_unit.group(1))

    # pytest format: "collected X items"
    m_pytest_coll = re.search(r"collected (\d+) items?", output)
    if m_pytest_coll:
        return int(m_pytest_coll.group(1))

    # pytest format: "X passed"
    m_pytest_pass = re.search(r"(\d+) passed", output)
    if m_pytest_pass:
        return int(m_pytest_pass.group(1))

    # Explicit no tests ran
    if "no tests ran" in output.lower() or "0 tests collected" in output.lower():
        return 0

    return None


def safe_extract_tar(archive_bytes: bytes, target_dir: str) -> None:
    """Safely extract tar archive bytes into target_dir preventing traversal, special files, and symlink escapes (D5)."""
    target_dir_real = os.path.realpath(target_dir)

    with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as tar:
        for member in tar.getmembers():
            norm_name = member.name.replace("\\", "/")

            # Reject absolute paths
            if os.path.isabs(norm_name) or norm_name.startswith("/"):
                raise RuntimeError(f"Absolute path rejected in tar archive: {member.name}")

            # Reject '..' components
            if any(part == ".." for part in norm_name.split("/")):
                raise RuntimeError(f"Directory traversal rejected in tar archive: {member.name}")

            # Reject special device/FIFO files
            if member.isdev() or member.ischr() or member.isblk() or member.isfifo():
                raise RuntimeError(f"Special file rejected in tar archive: {member.name}")

            # Validate destination path is strictly inside target_dir
            dest_path = os.path.realpath(os.path.join(target_dir_real, member.name))
            if os.path.commonpath([target_dir_real, dest_path]) != target_dir_real:
                raise RuntimeError(f"Directory traversal detected in tar archive: {member.name}")

            # Check symlinks / hardlinks for escaping target directory
            if member.issym() or member.islnk():
                link_target = os.path.realpath(
                    os.path.join(os.path.dirname(dest_path), member.linkname)
                )
                if os.path.commonpath([target_dir_real, link_target]) != target_dir_real:
                    raise RuntimeError(
                        f"Symlink escapes target directory: {member.name} -> {member.linkname}"
                    )

        if hasattr(tarfile, "data_filter"):
            tar.extractall(target_dir_real, filter="data")
        else:
            # Safe fallback: extract only regular files and directories with normalized permissions
            for member in tar.getmembers():
                if member.isreg():
                    tar.extract(member, target_dir_real)
                    target_file = os.path.join(target_dir_real, member.name)
                    os.chmod(target_file, 0o644)
                elif member.isdir():
                    tar.extract(member, target_dir_real)
                    target_dir_path = os.path.join(target_dir_real, member.name)
                    os.chmod(target_dir_path, 0o755)


class RadarEngine:
    """L3 Advisory Radar Engine.

    Performs pairwise textual trial-merges and budgeted combined-tree test execution.
    """

    def __init__(
        self,
        repo_path: str = ".",
        test_command: Optional[Union[List[str], str]] = None,
        test_runner: Optional[Callable[[str], Tuple[bool, Any]]] = None,
        test_budget_seconds: float = 15.0,
        max_active_heads: int = 10,
        default_base_sha: Optional[str] = None,
        run_tests_on_disjoint: bool = False,
    ):
        self.repo_path = os.path.abspath(repo_path)
        self.test_command = test_command
        self.test_runner = test_runner
        self.test_budget_seconds = float(test_budget_seconds)
        self.max_active_heads = int(max_active_heads)
        self.default_base_sha = default_base_sha
        self.run_tests_on_disjoint = run_tests_on_disjoint

    def _run_git(
        self,
        args: List[str],
        timeout: Optional[float] = 10.0,
        capture_bytes: bool = False,
    ) -> subprocess.CompletedProcess:
        """Run a git command in repository context with process group kill on timeout."""
        cmd = ["git", "-C", self.repo_path] + args
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=not capture_bytes,
            preexec_fn=os.setsid,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=proc.returncode,
                stdout=stdout,
                stderr=stderr,
            )
        except subprocess.TimeoutExpired as exc:
            try:
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
            proc.kill()
            proc.communicate()
            raise exc

    def verify_commit_exists(self, commit_sha: str) -> bool:
        """Verify that a commit object exists in the repository's object store."""
        if not commit_sha or not isinstance(commit_sha, str):
            return False
        clean_sha = commit_sha.strip()
        if len(clean_sha) < 4:
            return False
        try:
            res = self._run_git(["cat-file", "-e", f"{clean_sha}^{{commit}}"], timeout=2.0)
            return res.returncode == 0
        except (subprocess.SubprocessError, OSError):
            return False

    def get_merge_base(self, head_a: str, head_b: str) -> Optional[str]:
        """Compute the common merge base commit SHA between two heads."""
        try:
            res = self._run_git(["merge-base", head_a, head_b], timeout=5.0)
            if res.returncode == 0:
                base = res.stdout.strip()
                return base if base else None
            return None
        except (subprocess.SubprocessError, OSError):
            return None

    def get_changed_files(self, base_sha: str, head_sha: str) -> List[str]:
        """Get the list of modified/added files between base and head."""
        res = self._run_git(["diff", "--name-only", base_sha, head_sha], timeout=5.0)
        if res.returncode != 0:
            raise RuntimeError(f"git diff failed: {res.stderr.strip()}")
        return [line.strip() for line in res.stdout.splitlines() if line.strip()]

    def get_overlapping_files(
        self,
        head_a: str,
        head_b: str,
        base_sha: Optional[str] = None,
    ) -> List[str]:
        """Compute intersecting files modified by both head A and head B relative to base."""
        base = base_sha
        if not base:
            base = self.get_merge_base(head_a, head_b)
        if not base:
            return []

        files_a = set(self.get_changed_files(base, head_a))
        files_b = set(self.get_changed_files(base, head_b))
        return sorted(list(files_a & files_b))

    def trial_merge(
        self,
        head_a: str,
        head_b: str,
        base_sha: Optional[str] = None,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        """Execute pairwise trial-merge using `git merge-tree --write-tree --merge-base=<base>`.

        Pure in-memory calculation: zero checkout, zero working tree mutation,
        zero disk amplification.
        """
        args = ["merge-tree", "--write-tree", "--name-only"]
        if base_sha:
            args.append(f"--merge-base={base_sha}")
        args.extend([head_a, head_b])

        try:
            res = self._run_git(args, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {
                "status": STATUS_UNKNOWN,
                "error": f"Trial merge execution timed out after {timeout}s",
                "tree_sha": None,
                "conflicting_files": [],
                "messages": [],
            }
        except Exception as exc:
            return {
                "status": STATUS_UNKNOWN,
                "error": f"Trial merge execution failed: {exc}",
                "tree_sha": None,
                "conflicting_files": [],
                "messages": [],
            }

        stdout_str = res.stdout.strip()
        stderr_str = res.stderr.strip()

        # Clean merge: returncode 0
        if res.returncode == 0:
            lines = stdout_str.splitlines()
            tree_sha = lines[0].strip() if lines else None
            if not tree_sha or len(tree_sha) != 40:
                return {
                    "status": STATUS_UNKNOWN,
                    "error": f"Invalid tree SHA returned by merge-tree: {tree_sha}",
                    "tree_sha": None,
                    "conflicting_files": [],
                    "messages": [],
                }
            return {
                "status": STATUS_CLEAN,
                "tree_sha": tree_sha,
                "conflicting_files": [],
                "messages": [],
            }

        # Conflicted merge: returncode 1
        if res.returncode == 1:
            # Check if stderr indicates an error rather than a real merge conflict
            if stderr_str and ("not something we can merge" in stderr_str or "fatal:" in stderr_str):
                return {
                    "status": STATUS_UNKNOWN,
                    "error": f"Git object missing or unmergeable: {stderr_str}",
                    "tree_sha": None,
                    "conflicting_files": [],
                    "messages": [],
                }

            lines = res.stdout.splitlines()
            if not lines:
                return {
                    "status": STATUS_UNKNOWN,
                    "error": f"Empty stdout on merge-tree conflict: {stderr_str}",
                    "tree_sha": None,
                    "conflicting_files": [],
                    "messages": [],
                }

            tree_sha = lines[0].strip()
            conflicting_files: List[str] = []
            messages: List[str] = []
            idx = 1
            # Parse conflicting filenames section (terminated by blank line)
            while idx < len(lines) and lines[idx].strip():
                conflicting_files.append(lines[idx].strip())
                idx += 1

            # Skip blank line and parse informational/conflict messages
            idx += 1
            while idx < len(lines):
                if lines[idx].strip():
                    messages.append(lines[idx].strip())
                idx += 1

            return {
                "status": STATUS_CONFLICT,
                "tree_sha": tree_sha,
                "conflicting_files": conflicting_files,
                "messages": messages,
            }

        # Any other returncode is strictly UNKNOWN (fail-closed)
        return {
            "status": STATUS_UNKNOWN,
            "error": f"git merge-tree returned exit code {res.returncode}: {stderr_str or stdout_str}",
            "tree_sha": None,
            "conflicting_files": [],
            "messages": [],
        }

    def extract_tree_to_directory(
        self,
        tree_sha: str,
        target_dir: str,
        timeout: float = 10.0,
    ) -> None:
        """Extract a git tree object to a target directory via in-memory tar stream safely."""
        res = self._run_git(["archive", tree_sha], timeout=timeout, capture_bytes=True)
        if res.returncode != 0:
            err = (
                res.stderr.decode("utf-8", errors="replace")
                if isinstance(res.stderr, bytes)
                else str(res.stderr)
            )
            raise RuntimeError(f"git archive failed: {err}")

        archive_bytes = res.stdout if isinstance(res.stdout, bytes) else res.stdout.encode("utf-8")
        safe_extract_tar(archive_bytes, target_dir)

    def _run_custom_runner_isolated(
        self,
        runner_fn: Callable[[str], Any],
        snap_dir: str,
        timeout: float,
    ) -> Tuple[Optional[bool], Dict[str, Any]]:
        """Run custom runner in an isolated worker process with strict timeout and process group kill (D4 & C-1316)."""
        pipe_r, pipe_w = os.pipe()
        pid = os.fork()

        if pid == 0:
            os.close(pipe_r)
            os.setsid()
            try:
                res = runner_fn(snap_dir)
                payload = pickle.dumps({"ok": True, "res": res})
            except BaseException as exc:
                payload = pickle.dumps({"ok": False, "error": str(exc)})
            try:
                os.write(pipe_w, payload)
            except Exception:
                pass
            finally:
                os.close(pipe_w)
                os._exit(0)
        else:
            os.close(pipe_w)
            ready, _, _ = select.select([pipe_r], [], [], max(0.01, timeout))
            if not ready:
                try:
                    os.killpg(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
                try:
                    os.kill(pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
                try:
                    os.waitpid(pid, 0)
                except Exception:
                    pass
                os.close(pipe_r)
                return None, {
                    "error": "timeout",
                    "details": f"Custom test runner timed out after {timeout:.2f}s",
                }

            data = b""
            while True:
                try:
                    chunk = os.read(pipe_r, 65536)
                    if not chunk:
                        break
                    data += chunk
                except Exception:
                    break
            os.close(pipe_r)
            try:
                os.waitpid(pid, 0)
            except Exception:
                pass

            if not data:
                return None, {
                    "error": "runner_crash",
                    "details": "Custom runner process exited without returning data",
                }

            try:
                out = pickle.loads(data)
            except Exception as exc:
                return None, {
                    "error": "deserialization_failure",
                    "details": f"Failed to deserialize custom runner result: {exc}",
                }

            if not out.get("ok"):
                return None, {
                    "error": "runner_exception",
                    "details": f"Custom runner raised: {out.get('error')}",
                }

            runner_res = out.get("res")

            # Strict return validation:
            # 1. Bare bool True: strictly treated as missing test count evidence -> STATUS_UNKNOWN
            if runner_res is True:
                return False, {
                    "error": "no_collected_test_evidence",
                    "tests_collected": 0,
                    "details": "Custom runner returned bare True without collected test count evidence",
                }
            # 2. Bare bool False: test failure -> STATUS_CONFLICT kind='test'
            if runner_res is False:
                return False, {
                    "error": "test_failure",
                    "details": "Custom runner returned False",
                }
            # 3. Tuple (passed, evidence_dict):
            if isinstance(runner_res, (tuple, list)) and len(runner_res) == 2:
                passed, ev = runner_res
                ev_dict = ev if isinstance(ev, dict) else {"details": str(ev)}
                if passed is True:
                    tc = ev_dict.get("tests_collected")
                    if isinstance(tc, int) and tc > 0:
                        return True, ev_dict
                    else:
                        return False, {
                            "error": "no_collected_test_evidence",
                            "tests_collected": 0,
                            "details": "Custom runner passed but produced no positive collected test count evidence",
                            "evidence": ev_dict,
                        }
                else:
                    ev_dict.setdefault("error", "test_failure")
                    return False, ev_dict

            return False, {
                "error": "invalid_runner_output",
                "details": f"Custom runner returned unexpected output: {repr(runner_res)}",
            }

    def run_combined_tree_tests(
        self,
        tree_sha: str,
        test_command: Optional[Union[List[str], str]] = None,
        budget_seconds: Optional[float] = None,
    ) -> Tuple[Optional[bool], Dict[str, Any]]:
        """Run budgeted test execution on a clean merge tree snapshot with process isolation.

        Enforces:
        - Process group isolation (os.setsid + os.killpg on timeout).
        - Total wall-clock timeout budget.
        - Sanitized minimal execution environment (D6).
        - Resource limits via setrlimit (RLIMIT_CPU, RLIMIT_AS, RLIMIT_FSIZE).
        - Positive collected tests verification (> 0 tests required for clean).

        Returns (result, evidence):
        - (True, evidence): tests passed with > 0 collected tests
        - (False, evidence): tests failed (or 0 tests collected -> error='no_tests_collected')
        - (None, evidence): UNKNOWN (timeout, missing suite, execution failure)
        """
        budget = budget_seconds if budget_seconds is not None else self.test_budget_seconds
        start_time = time.time()
        snap_dir = tempfile.mkdtemp(prefix="radar_snap_")

        try:
            # Check elapsed wall-clock budget
            elapsed = time.time() - start_time
            if elapsed >= budget:
                return None, {
                    "error": "timeout",
                    "details": f"Total budget exceeded before snapshot extraction: {budget}s",
                }

            extract_timeout = max(0.1, min(5.0, budget - elapsed))
            try:
                self.extract_tree_to_directory(tree_sha, snap_dir, timeout=extract_timeout)
            except subprocess.TimeoutExpired:
                return None, {
                    "error": "timeout",
                    "details": f"Snapshot extraction timed out after {extract_timeout:.2f}s",
                }
            except Exception as exc:
                return None, {
                    "error": "extraction_failure",
                    "details": f"Failed to extract tree {tree_sha}: {exc}",
                }

            # Custom callable test runner if provided (D4 & C-1316: isolated worker process with strict budget)
            if self.test_runner is not None:
                elapsed = time.time() - start_time
                remaining_budget = budget - elapsed
                if remaining_budget <= 0:
                    return None, {
                        "error": "timeout",
                        "details": f"Execution timed out before custom runner: {budget}s",
                    }
                return self._run_custom_runner_isolated(self.test_runner, snap_dir, remaining_budget)

            # Determine test command
            cmd = test_command or self.test_command
            if not cmd:
                # Auto-detect test suite in snapshot
                if os.path.exists(os.path.join(snap_dir, "tests")) or any(
                    f.startswith("test_") and f.endswith(".py") for f in os.listdir(snap_dir)
                ):
                    cmd = [sys.executable, "-m", "unittest", "discover", "-s", "."]
                elif os.path.exists(os.path.join(snap_dir, "package.json")):
                    cmd = ["npm", "test"]
                elif os.path.exists(os.path.join(snap_dir, "Cargo.toml")):
                    cmd = ["cargo", "test"]
                else:
                    # STRICT INVARIANT: If overlapping files exist but no test suite is found,
                    # the outcome is strictly UNKNOWN, never safe!
                    return None, {
                        "error": "missing_test_suite",
                        "details": "No test suite found in tree snapshot to verify overlapping files",
                    }

            # Calculate remaining wall-clock budget
            elapsed = time.time() - start_time
            remaining_budget = budget - elapsed
            if remaining_budget <= 0:
                return None, {
                    "error": "timeout",
                    "details": f"Wall-clock budget exhausted before test execution: {budget}s",
                }

            # Command parsing and sanitization (D6: shell=False ALWAYS, parse string via shlex.split)
            if isinstance(cmd, str):
                cmd_list = shlex.split(cmd)
            else:
                cmd_list = list(cmd)
            cmd_str = " ".join(cmd_list)

            # Minimal clean allowlist env (D6)
            clean_env = {
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "HOME": snap_dir,
                "TMPDIR": snap_dir,
                "LANG": "C.UTF-8",
                "LC_ALL": "C.UTF-8",
                "PYTHONPATH": snap_dir,
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONUNBUFFERED": "1",
            }

            def _preexec_limits():
                os.setsid()
                # CPU time limit: budget + 2s margin
                cpu_sec = max(1, int(remaining_budget + 2))
                try:
                    resource.setrlimit(resource.RLIMIT_CPU, (cpu_sec, cpu_sec + 2))
                except (ValueError, OSError):
                    pass
                # Virtual memory limit: 1024 MB
                vmem = 1024 * 1024 * 1024
                try:
                    resource.setrlimit(resource.RLIMIT_AS, (vmem, vmem))
                except (ValueError, OSError):
                    pass
                # Max file size: 50 MB
                fsize = 50 * 1024 * 1024
                try:
                    resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
                except (ValueError, OSError):
                    pass

            # Execute with process group isolation, resource limits, and shell=False ALWAYS
            proc = subprocess.Popen(
                cmd_list,
                cwd=snap_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=_preexec_limits,
                env=clean_env,
                shell=False,
            )

            try:
                stdout, stderr = proc.communicate(timeout=remaining_budget)
            except subprocess.TimeoutExpired as exc:
                # Terminate entire process group
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    pass
                proc.kill()
                try:
                    proc.communicate(timeout=1.0)
                except Exception:
                    pass

                stdout_text = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                stderr_text = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
                return None, {
                    "error": "timeout",
                    "test_command": cmd_str,
                    "details": f"Test runner process group timed out after {remaining_budget:.2f}s and was terminated",
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                }
            except Exception as exc:
                try:
                    pgid = os.getpgid(proc.pid)
                    os.killpg(pgid, signal.SIGKILL)
                except Exception:
                    pass
                return None, {
                    "error": "execution_failure",
                    "test_command": cmd_str,
                    "details": f"Failed to execute test command: {exc}",
                }

            stdout_snippet = stdout[-2000:] if stdout else ""
            stderr_snippet = stderr[-2000:] if stderr else ""
            collected_count = parse_collected_test_count(f"{stdout_snippet}\n{stderr_snippet}")

            if proc.returncode == 0:
                if collected_count is None or collected_count == 0:
                    return False, {
                        "test_command": cmd_str,
                        "exit_code": 0,
                        "tests_collected": 0,
                        "error": "no_collected_test_evidence",
                        "details": "Test command exited 0 but produced no parseable collected test count evidence",
                        "stdout": stdout_snippet,
                        "stderr": stderr_snippet,
                    }

                return True, {
                    "test_command": cmd_str,
                    "exit_code": 0,
                    "tests_collected": collected_count,
                    "stdout": stdout_snippet,
                    "stderr": stderr_snippet,
                    "details": "All combined-tree tests passed cleanly",
                }
            else:
                if (
                    collected_count == 0
                    or "no tests ran" in stderr_snippet.lower()
                    or "0 tests collected" in stderr_snippet.lower()
                ):
                    return False, {
                        "error": "no_tests_collected",
                        "tests_collected": 0,
                        "test_command": cmd_str,
                        "exit_code": proc.returncode,
                        "stdout": stdout_snippet,
                        "stderr": stderr_snippet,
                        "details": f"Test runner collected 0 tests (exit code {proc.returncode})",
                    }

                return False, {
                    "test_command": cmd_str,
                    "exit_code": proc.returncode,
                    "stdout": stdout_snippet,
                    "stderr": stderr_snippet,
                    "details": f"Combined-tree test runner failed with exit code {proc.returncode}\n{stderr_snippet or stdout_snippet}".strip(),
                }

        finally:
            shutil.rmtree(snap_dir, ignore_errors=True)

    def evaluate_pair(
        self,
        head_a: Union[AgentHead, Dict[str, Any], Tuple[str, str], str],
        head_b: Union[AgentHead, Dict[str, Any], Tuple[str, str], str],
        base_sha: Optional[str] = None,
        test_command: Optional[Union[List[str], str]] = None,
        test_budget_seconds: Optional[float] = None,
        force_test: bool = False,
    ) -> PairResult:
        """Evaluate a pair of agent heads for conflicts and semantic regressions.

        Output status enum must be strictly: 'conflict' | 'clean' | 'unknown' | 'not_checked'.
        - On conflict: returns status='conflict' with kind='textual' or kind='test'.
        - On missing objects, execution timeout, or check failure: strictly returns status='unknown'.
        - On disjoint/no-overlap files without tests: strictly returns status='not_checked' (never 'clean').
        - On clean merge with positive passing tests (> 0 tests): returns status='clean'.
        """
        default_base = base_sha or self.default_base_sha
        try:
            a = AgentHead.from_item(head_a, default_base=default_base)
            b = AgentHead.from_item(head_b, default_base=default_base)
        except Exception as exc:
            return PairResult(
                status=STATUS_UNKNOWN,
                pair=["unknown_a", "unknown_b"],
                heads={},
                error=f"Malformed head vector: {exc}",
                evidence={"error": "malformed_head", "details": str(exc)},
            )

        pair = [a.id, b.id]
        heads = {a.id: a.sha, b.id: b.sha}
        base = base_sha or a.base_sha or b.base_sha or self.default_base_sha

        # Fail-closed check: Validate commits exist in object store
        if not self.verify_commit_exists(a.sha):
            err_msg = f"Missing commit object for {a.id}: {a.sha}"
            return PairResult(
                status=STATUS_UNKNOWN,
                pair=pair,
                heads=heads,
                error=err_msg,
                evidence={"error": "missing_commit_object", "details": err_msg},
            )
        if not self.verify_commit_exists(b.sha):
            err_msg = f"Missing commit object for {b.id}: {b.sha}"
            return PairResult(
                status=STATUS_UNKNOWN,
                pair=pair,
                heads=heads,
                error=err_msg,
                evidence={"error": "missing_commit_object", "details": err_msg},
            )
        if base and not self.verify_commit_exists(base):
            err_msg = f"Missing base commit object: {base}"
            return PairResult(
                status=STATUS_UNKNOWN,
                pair=pair,
                heads=heads,
                error=err_msg,
                evidence={"error": "missing_base_commit", "details": err_msg},
            )

        # Step 1: Textual trial-merge
        tm = self.trial_merge(a.sha, b.sha, base_sha=base)
        if tm["status"] == STATUS_UNKNOWN:
            return PairResult(
                status=STATUS_UNKNOWN,
                pair=pair,
                heads=heads,
                error=tm.get("error", "Trial-merge failed"),
                evidence={"error": "trial_merge_failed", "details": tm.get("error")},
            )

        if tm["status"] == STATUS_CONFLICT:
            conflicting_files = tm["conflicting_files"]
            messages = tm["messages"]
            conflict_type = "content_conflict"
            for msg in messages:
                if "CONFLICT (" in msg:
                    ctype = msg.split("CONFLICT (")[1].split(")")[0].strip()
                    conflict_type = f"{ctype}_conflict"
                    break
            details = "\n".join(messages) if messages else f"Conflict markers in {', '.join(conflicting_files)}"

            evidence = {
                "conflicting_files": conflicting_files,
                "conflict_type": conflict_type,
                "details": details,
            }
            warning = create_warning(
                pair=pair,
                heads=heads,
                kind="textual",
                evidence=evidence,
            )
            return PairResult(
                status=STATUS_CONFLICT,
                kind="textual",
                pair=pair,
                heads=heads,
                warning=warning,
                evidence=evidence,
                tree_sha=tm.get("tree_sha"),
                overlapping_files=conflicting_files,
            )

        # Step 2: Clean textual merge succeeded
        tree_sha = tm["tree_sha"]

        # Step 3: Check overlapping files
        try:
            overlapping_files = self.get_overlapping_files(a.sha, b.sha, base_sha=base)
        except Exception as exc:
            return PairResult(
                status=STATUS_UNKNOWN,
                pair=pair,
                heads=heads,
                tree_sha=tree_sha,
                error=f"Failed to compute file overlap: {exc}",
                evidence={"error": "overlap_computation_failed", "details": str(exc)},
            )

        should_run_tests = bool(overlapping_files or force_test or self.run_tests_on_disjoint)

        # Step 4: Budgeted combined-tree test runner
        if should_run_tests:
            test_res, test_evidence = self.run_combined_tree_tests(
                tree_sha,
                test_command=test_command or self.test_command,
                budget_seconds=test_budget_seconds or self.test_budget_seconds,
            )

            # Check if 0 tests collected or unparseable test evidence occurred:
            if test_evidence.get("error") in (
                "no_tests_collected",
                "no_collected_test_evidence",
                "missing_collected_test_evidence",
            ):
                return PairResult(
                    status=STATUS_UNKNOWN,
                    pair=pair,
                    heads=heads,
                    tree_sha=tree_sha,
                    overlapping_files=overlapping_files,
                    evidence=test_evidence,
                    error=test_evidence.get(
                        "details",
                        test_evidence.get("error", "No positive collected test evidence"),
                    ),
                )

            if test_res is None:
                # Timeout, missing test suite, or check failure -> strictly UNKNOWN
                return PairResult(
                    status=STATUS_UNKNOWN,
                    pair=pair,
                    heads=heads,
                    tree_sha=tree_sha,
                    overlapping_files=overlapping_files,
                    evidence=test_evidence,
                    error=test_evidence.get(
                        "details",
                        test_evidence.get("error", "Test check failure"),
                    ),
                )
            elif test_res is False:
                # Semantic test regression / failure -> status='conflict', kind='test'
                warning = create_warning(
                    pair=pair,
                    heads=heads,
                    kind="test",
                    evidence=test_evidence,
                )
                return PairResult(
                    status=STATUS_CONFLICT,
                    kind="test",
                    pair=pair,
                    heads=heads,
                    warning=warning,
                    tree_sha=tree_sha,
                    overlapping_files=overlapping_files,
                    evidence=test_evidence,
                )
            else:
                # Clean merge and positive tests passed (> 0 tests)
                return PairResult(
                    status=STATUS_CLEAN,
                    kind=None,
                    pair=pair,
                    heads=heads,
                    warning=None,
                    tree_sha=tree_sha,
                    overlapping_files=overlapping_files,
                    evidence=test_evidence,
                )
        else:
            # Disjoint / non-overlapping files where tests were not run:
            # STRICT INVARIANT: Must NOT be 'clean'! Returns 'not_checked'.
            evidence = {
                "reason": "disjoint_no_tests",
                "overlapping_files": [],
                "details": "Non-overlapping files merged cleanly textually; semantic tests not executed",
            }
            return PairResult(
                status=STATUS_NOT_CHECKED,
                kind=None,
                pair=pair,
                heads=heads,
                warning=None,
                tree_sha=tree_sha,
                overlapping_files=[],
                evidence=evidence,
            )

    def check_pair(
        self,
        head_a: Union[AgentHead, Dict[str, Any], Tuple[str, str], str],
        head_b: Union[AgentHead, Dict[str, Any], Tuple[str, str], str],
        base_sha: Optional[str] = None,
        test_command: Optional[Union[List[str], str]] = None,
        test_budget_seconds: Optional[float] = None,
        force_test: bool = False,
    ) -> PairResult:
        """Alias for evaluate_pair."""
        return self.evaluate_pair(
            head_a=head_a,
            head_b=head_b,
            base_sha=base_sha,
            test_command=test_command,
            test_budget_seconds=test_budget_seconds,
            force_test=force_test,
        )

    def run_matrix(
        self,
        heads: Union[List[Any], Dict[str, Any]],
        base_sha: Optional[str] = None,
        test_command: Optional[Union[List[str], str]] = None,
        test_budget_seconds: Optional[float] = None,
        force_test: bool = False,
        max_active_heads: Optional[int] = None,
    ) -> MatrixResult:
        """Matrix computation across active head vectors.

        Deterministic & Bounded: N <= 10 by default.
        Pure in-memory trial-merges without checkouts.
        """
        start_time = time.time()
        bound = max_active_heads or self.max_active_heads

        # Normalize heads
        head_list: List[AgentHead] = []
        if isinstance(heads, dict):
            for k, v in heads.items():
                if isinstance(v, dict):
                    d = dict(v)
                    d.setdefault("id", k)
                    head_list.append(AgentHead.from_item(d, default_base=base_sha))
                else:
                    head_list.append(AgentHead(id=str(k), sha=str(v), base_sha=base_sha))
        elif isinstance(heads, (list, tuple)):
            for item in heads:
                head_list.append(AgentHead.from_item(item, default_base=base_sha))
        else:
            raise ValueError(f"Unsupported heads format: {type(heads)}")

        # Enforce deterministic bound
        if len(head_list) > bound:
            head_list = head_list[:bound]

        pairs_results: List[PairResult] = []
        warnings: List[Dict[str, Any]] = []

        clean_count = 0
        conflict_count = 0
        unknown_count = 0
        not_checked_count = 0

        for a, b in itertools.combinations(head_list, 2):
            res = self.evaluate_pair(
                a,
                b,
                base_sha=base_sha,
                test_command=test_command,
                test_budget_seconds=test_budget_seconds,
                force_test=force_test,
            )
            pairs_results.append(res)
            if res.warning:
                warnings.append(res.warning)

            if res.status == STATUS_CLEAN:
                clean_count += 1
            elif res.status == STATUS_CONFLICT:
                conflict_count += 1
            elif res.status == STATUS_UNKNOWN:
                unknown_count += 1
            elif res.status == STATUS_NOT_CHECKED:
                not_checked_count += 1

        duration = time.time() - start_time
        summary = {
            "active_heads": len(head_list),
            "total_pairs": len(pairs_results),
            "clean_pairs": clean_count,
            "conflict_pairs": conflict_count,
            "unknown_pairs": unknown_count,
            "not_checked_pairs": not_checked_count,
            "warning_count": len(warnings),
            "bounded_limit": bound,
        }

        return MatrixResult(
            pairs=pairs_results,
            warnings=warnings,
            summary=summary,
            duration_seconds=round(duration, 4),
        )


def evaluate_pair(
    head_a: Any,
    head_b: Any,
    base_sha: Optional[str] = None,
    repo_path: str = ".",
    test_command: Optional[Union[List[str], str]] = None,
    test_budget_seconds: float = 15.0,
    force_test: bool = False,
) -> PairResult:
    """Convenience function to evaluate a single pair."""
    engine = RadarEngine(
        repo_path=repo_path,
        test_command=test_command,
        test_budget_seconds=test_budget_seconds,
    )
    return engine.evaluate_pair(
        head_a=head_a,
        head_b=head_b,
        base_sha=base_sha,
        force_test=force_test,
    )


def run_matrix(
    heads: Any,
    base_sha: Optional[str] = None,
    repo_path: str = ".",
    test_command: Optional[Union[List[str], str]] = None,
    test_budget_seconds: float = 15.0,
    max_active_heads: int = 10,
    force_test: bool = False,
) -> MatrixResult:
    """Convenience function to run pairwise matrix evaluation."""
    engine = RadarEngine(
        repo_path=repo_path,
        test_command=test_command,
        test_budget_seconds=test_budget_seconds,
        max_active_heads=max_active_heads,
    )
    return engine.run_matrix(
        heads=heads,
        base_sha=base_sha,
        force_test=force_test,
    )


def main():
    """Command-line interface for L3 Advisory Radar Engine."""
    parser = argparse.ArgumentParser(description="L3 Advisory Radar Engine")
    parser.add_argument("--repo", default=".", help="Path to git repository")
    parser.add_argument("--base", default=None, help="Base commit SHA")
    parser.add_argument("--heads", nargs="+", help="Active head commit SHAs or id=sha pairs")
    parser.add_argument("--pair", nargs=2, help="Two heads to evaluate pairwise")
    parser.add_argument("--test-cmd", default=None, help="Command to run tests on combined tree")
    parser.add_argument("--budget", type=float, default=15.0, help="Test execution budget in seconds")
    parser.add_argument("--force-test", action="store_true", help="Run tests even on disjoint files")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    engine = RadarEngine(
        repo_path=args.repo,
        test_command=args.test_cmd,
        test_budget_seconds=args.budget,
        run_tests_on_disjoint=args.force_test,
    )

    if args.pair:
        res = engine.evaluate_pair(
            args.pair[0],
            args.pair[1],
            base_sha=args.base,
            force_test=args.force_test,
        )
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            rep = res.report()
            print(f"Status: {rep['status']}")
            if rep["kind"]:
                print(f"Kind: {rep['kind']}")
            if res.warning:
                print(f"Warning: {json.dumps(res.warning, indent=2)}")
            elif res.error:
                print(f"Error: {res.error}")
            else:
                print(f"Report: {json.dumps(rep, indent=2)}")
    elif args.heads:
        matrix = engine.run_matrix(
            args.heads,
            base_sha=args.base,
            force_test=args.force_test,
        )
        if args.json:
            print(json.dumps(matrix.to_dict(), indent=2))
        else:
            print(f"Evaluated {matrix.summary['total_pairs']} pairs in {matrix.duration_seconds}s")
            print(f"Summary: {matrix.summary}")
            if matrix.warnings:
                print(f"\nActive Warnings ({len(matrix.warnings)}):")
                for w in matrix.warnings:
                    print(
                        f"  - [{w['kind']}] {w['warning_id']} between {w['pair']}: "
                        f"{w['evidence'].get('details')}"
                    )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

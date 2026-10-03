"""L3 Advisory Radar Engine.

Provides in-memory pairwise trial-merges using git merge-tree --write-tree,
detects conflicting edits with zero checkout/disk overhead, and runs budgeted
semantic tests against merged snapshots on clean trial-merges when overlapping
files exist.

Enforces strict fail-closed output invariants:
- On conflict: emits warning {warning_id, pair: [A, B], heads: {A, B}, kind: "textual" | "test", evidence: {...}}
- On missing objects, execution timeout, or check failure: strictly returns "UNKNOWN", NEVER "safe"!

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
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


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

    Subclasses dict for direct JSON serializability and dictionary access,
    while also exposing property and comparison semantics.
    """

    def __init__(
        self,
        status: str,  # "CLEAN" | "CONFLICT" | "TEST_FAILURE" | "UNKNOWN"
        pair: List[str],
        heads: Dict[str, str],
        warning: Optional[Dict[str, Any]] = None,
        tree_sha: Optional[str] = None,
        overlapping_files: Optional[List[str]] = None,
        error: Optional[str] = None,
        evidence: Optional[Dict[str, Any]] = None,
    ):
        data = {
            "status": status,
            "pair": list(pair),
            "heads": dict(heads),
            "warning": warning,
            "tree_sha": tree_sha,
            "overlapping_files": list(overlapping_files or []),
            "error": error,
            "evidence": evidence or (warning.get("evidence") if warning else None),
            "is_safe": (status == "CLEAN"),
        }
        super().__init__(data)

    @property
    def status(self) -> str:
        return self["status"]

    @property
    def warning(self) -> Optional[Dict[str, Any]]:
        return self["warning"]

    @property
    def warning_id(self) -> Optional[str]:
        return self["warning"].get("warning_id") if self["warning"] else None

    @property
    def kind(self) -> Optional[str]:
        return self["warning"].get("kind") if self["warning"] else None

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
    def evidence(self) -> Optional[Dict[str, Any]]:
        return self["evidence"]

    @property
    def is_safe(self) -> bool:
        # STRICT INVARIANT: Never safe by default. Only verified CLEAN is safe.
        return self["status"] == "CLEAN"

    @property
    def is_unknown(self) -> bool:
        return self["status"] == "UNKNOWN"

    @property
    def is_conflict(self) -> bool:
        return self["status"] == "CONFLICT"

    @property
    def is_test_failure(self) -> bool:
        return self["status"] == "TEST_FAILURE"

    @property
    def is_clean(self) -> bool:
        return self["status"] == "CLEAN"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, str):
            return self.status == other
        return super().__eq__(other)

    def __repr__(self) -> str:
        w_id = self.warning_id or "none"
        return f"<PairResult pair={self.pair} status='{self.status}' warning_id='{w_id}' is_safe={self.is_safe}>"


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
    ):
        self.repo_path = os.path.abspath(repo_path)
        self.test_command = test_command
        self.test_runner = test_runner
        self.test_budget_seconds = float(test_budget_seconds)
        self.max_active_heads = int(max_active_heads)
        self.default_base_sha = default_base_sha

    def _run_git(
        self,
        args: List[str],
        timeout: Optional[float] = 10.0,
        capture_bytes: bool = False,
    ) -> subprocess.CompletedProcess:
        """Run a git command in the repository context."""
        cmd = ["git", "-C", self.repo_path] + args
        return subprocess.run(
            cmd,
            capture_output=True,
            text=not capture_bytes,
            timeout=timeout,
        )

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
        """Execute pairwise trial-merge using `git merge-tree --write-tree`.

        Pure in-memory calculation: zero checkout, zero working tree mutation,
        zero disk amplification.
        """
        args = ["merge-tree", "--write-tree", "--name-only"]
        if base_sha:
            args.extend(["--merge-base", base_sha])
        args.extend([head_a, head_b])

        try:
            res = self._run_git(args, timeout=timeout)
        except subprocess.TimeoutExpired:
            return {
                "status": "UNKNOWN",
                "error": f"Trial merge execution timed out after {timeout}s",
                "tree_sha": None,
                "conflicting_files": [],
                "messages": [],
            }
        except Exception as exc:
            return {
                "status": "UNKNOWN",
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
                    "status": "UNKNOWN",
                    "error": f"Invalid tree SHA returned by merge-tree: {tree_sha}",
                    "tree_sha": None,
                    "conflicting_files": [],
                    "messages": [],
                }
            return {
                "status": "CLEAN",
                "tree_sha": tree_sha,
                "conflicting_files": [],
                "messages": [],
            }

        # Conflicted merge: returncode 1
        if res.returncode == 1:
            # Check if stderr indicates an error rather than a real merge conflict
            if stderr_str and ("not something we can merge" in stderr_str or "fatal:" in stderr_str):
                return {
                    "status": "UNKNOWN",
                    "error": f"Git object missing or unmergeable: {stderr_str}",
                    "tree_sha": None,
                    "conflicting_files": [],
                    "messages": [],
                }

            lines = res.stdout.splitlines()
            if not lines:
                return {
                    "status": "UNKNOWN",
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
                "status": "CONFLICT",
                "tree_sha": tree_sha,
                "conflicting_files": conflicting_files,
                "messages": messages,
            }

        # Any other returncode is strictly UNKNOWN (fail-closed)
        return {
            "status": "UNKNOWN",
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
        """Extract a git tree object to a target directory via in-memory tar stream."""
        res = self._run_git(["archive", tree_sha], timeout=timeout, capture_bytes=True)
        if res.returncode != 0:
            err = res.stderr.decode("utf-8", errors="replace") if isinstance(res.stderr, bytes) else str(res.stderr)
            raise RuntimeError(f"git archive failed: {err}")

        with tarfile.open(fileobj=io.BytesIO(res.stdout)) as tar:
            if hasattr(tarfile, "data_filter"):
                tar.extractall(target_dir, filter="tar")
            else:
                tar.extractall(target_dir)

    def run_combined_tree_tests(
        self,
        tree_sha: str,
        test_command: Optional[Union[List[str], str]] = None,
        budget_seconds: Optional[float] = None,
    ) -> Tuple[Optional[bool], Dict[str, Any]]:
        """Run budgeted test execution on a clean merge tree snapshot.

        Returns (result, evidence):
        - (True, evidence): tests passed
        - (False, evidence): tests failed
        - (None, evidence): UNKNOWN (timeout, missing suite, check failure)
        """
        budget = budget_seconds if budget_seconds is not None else self.test_budget_seconds
        snap_dir = tempfile.mkdtemp(prefix="radar_snap_")

        try:
            # 1. Extract tree snapshot
            try:
                self.extract_tree_to_directory(tree_sha, snap_dir, timeout=min(5.0, budget))
            except subprocess.TimeoutExpired:
                return None, {
                    "error": "TIMEOUT",
                    "details": f"Snapshot extraction timed out after {min(5.0, budget)}s",
                }
            except Exception as exc:
                return None, {
                    "error": "EXTRACTION_FAILURE",
                    "details": f"Failed to extract tree {tree_sha}: {exc}",
                }

            # 2. Custom callable test runner if provided
            if self.test_runner is not None:
                try:
                    runner_res = self.test_runner(snap_dir)
                    if isinstance(runner_res, tuple) and len(runner_res) == 2:
                        passed, ev = runner_res
                        if isinstance(ev, dict):
                            return passed, ev
                        return passed, {"details": str(ev)}
                    elif isinstance(runner_res, bool):
                        return runner_res, {"details": f"Custom runner returned {runner_res}"}
                    else:
                        return None, {
                            "error": "INVALID_RUNNER_OUTPUT",
                            "details": str(runner_res),
                        }
                except TimeoutError:
                    return None, {
                        "error": "TIMEOUT",
                        "details": "Custom test runner timed out",
                    }
                except Exception as exc:
                    return None, {
                        "error": "RUNNER_EXCEPTION",
                        "details": f"Custom runner raised: {exc}",
                    }

            # 3. Determine test command
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
                        "error": "MISSING_TEST_SUITE",
                        "details": "No test suite found in tree snapshot to verify overlapping files",
                    }

            # 4. Execute test command with budget timeout
            cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=snap_dir,
                    capture_output=True,
                    text=True,
                    timeout=budget,
                    shell=isinstance(cmd, str),
                )
            except subprocess.TimeoutExpired as exc:
                stdout_text = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                stderr_text = exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "")
                return None, {
                    "error": "TIMEOUT",
                    "test_command": cmd_str,
                    "details": f"Test runner timed out after {budget}s",
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                }
            except Exception as exc:
                return None, {
                    "error": "EXECUTION_FAILURE",
                    "test_command": cmd_str,
                    "details": f"Failed to execute test command: {exc}",
                }

            stdout_snippet = proc.stdout[-2000:] if proc.stdout else ""
            stderr_snippet = proc.stderr[-2000:] if proc.stderr else ""

            if proc.returncode == 0:
                return True, {
                    "test_command": cmd_str,
                    "exit_code": 0,
                    "stdout": stdout_snippet,
                    "stderr": stderr_snippet,
                    "details": "All combined-tree tests passed cleanly",
                }
            else:
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

        Strict Fail-Closed Invariants:
        - On textual conflict: returns status="CONFLICT" with kind="textual" warning.
        - On test failure: returns status="TEST_FAILURE" with kind="test" warning.
        - On clean merge & no overlap (or tests pass): returns status="CLEAN" with no warning.
        - On missing objects, execution timeout, or check failure: strictly returns "UNKNOWN", NEVER "safe"!
        """
        default_base = base_sha or self.default_base_sha
        try:
            a = AgentHead.from_item(head_a, default_base=default_base)
            b = AgentHead.from_item(head_b, default_base=default_base)
        except Exception as exc:
            return PairResult(
                status="UNKNOWN",
                pair=["unknown_a", "unknown_b"],
                heads={},
                error=f"Malformed head vector: {exc}",
            )

        pair = [a.id, b.id]
        heads = {a.id: a.sha, b.id: b.sha}
        base = base_sha or a.base_sha or b.base_sha or self.default_base_sha

        # Fail-closed check: Validate commits exist in object store
        if not self.verify_commit_exists(a.sha):
            return PairResult(
                status="UNKNOWN",
                pair=pair,
                heads=heads,
                error=f"Missing commit object for {a.id}: {a.sha}",
            )
        if not self.verify_commit_exists(b.sha):
            return PairResult(
                status="UNKNOWN",
                pair=pair,
                heads=heads,
                error=f"Missing commit object for {b.id}: {b.sha}",
            )
        if base and not self.verify_commit_exists(base):
            return PairResult(
                status="UNKNOWN",
                pair=pair,
                heads=heads,
                error=f"Missing base commit object: {base}",
            )

        # Step 1: Textual trial-merge
        tm = self.trial_merge(a.sha, b.sha, base_sha=base)
        if tm["status"] == "UNKNOWN":
            return PairResult(
                status="UNKNOWN",
                pair=pair,
                heads=heads,
                error=tm.get("error", "Trial-merge failed"),
            )

        if tm["status"] == "CONFLICT":
            conflicting_files = tm["conflicting_files"]
            messages = tm["messages"]
            conflict_type = "content_conflict"
            for msg in messages:
                if "CONFLICT (" in msg:
                    ctype = msg.split("CONFLICT (")[1].split(")")[0].strip()
                    conflict_type = f"{ctype}_conflict"
                    break
            details = "\n".join(messages) if messages else f"Conflict markers in {', '.join(conflicting_files)}"

            warning = create_warning(
                pair=pair,
                heads=heads,
                kind="textual",
                evidence={
                    "conflicting_files": conflicting_files,
                    "conflict_type": conflict_type,
                    "details": details,
                },
            )
            return PairResult(
                status="CONFLICT",
                pair=pair,
                heads=heads,
                warning=warning,
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
                status="UNKNOWN",
                pair=pair,
                heads=heads,
                tree_sha=tree_sha,
                error=f"Failed to compute file overlap: {exc}",
            )

        # Step 4: Budgeted combined-tree test runner
        if overlapping_files or force_test:
            test_res, test_evidence = self.run_combined_tree_tests(
                tree_sha,
                test_command=test_command or self.test_command,
                budget_seconds=test_budget_seconds or self.test_budget_seconds,
            )

            if test_res is None:
                # Timeout, missing test suite, or check failure -> strictly UNKNOWN
                return PairResult(
                    status="UNKNOWN",
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
                # Semantic test regression / failure!
                warning = create_warning(
                    pair=pair,
                    heads=heads,
                    kind="test",
                    evidence=test_evidence,
                )
                return PairResult(
                    status="TEST_FAILURE",
                    pair=pair,
                    heads=heads,
                    warning=warning,
                    tree_sha=tree_sha,
                    overlapping_files=overlapping_files,
                    evidence=test_evidence,
                )
            else:
                # Clean merge and tests passed cleanly
                return PairResult(
                    status="CLEAN",
                    pair=pair,
                    heads=heads,
                    warning=None,
                    tree_sha=tree_sha,
                    overlapping_files=overlapping_files,
                    evidence=test_evidence,
                )
        else:
            # Clean non-overlapping commits -> returns no warning
            return PairResult(
                status="CLEAN",
                pair=pair,
                heads=heads,
                warning=None,
                tree_sha=tree_sha,
                overlapping_files=[],
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
        test_failure_count = 0
        unknown_count = 0

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

            if res.status == "CLEAN":
                clean_count += 1
            elif res.status == "CONFLICT":
                conflict_count += 1
            elif res.status == "TEST_FAILURE":
                test_failure_count += 1
            elif res.status == "UNKNOWN":
                unknown_count += 1

        duration = time.time() - start_time
        summary = {
            "active_heads": len(head_list),
            "total_pairs": len(pairs_results),
            "clean_pairs": clean_count,
            "conflict_pairs": conflict_count,
            "test_failure_pairs": test_failure_count,
            "unknown_pairs": unknown_count,
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
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    engine = RadarEngine(
        repo_path=args.repo,
        test_command=args.test_cmd,
        test_budget_seconds=args.budget,
    )

    if args.pair:
        res = engine.evaluate_pair(args.pair[0], args.pair[1], base_sha=args.base)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Status: {res.status}")
            if res.warning:
                print(f"Warning ({res.kind}): {json.dumps(res.warning, indent=2)}")
            elif res.error:
                print(f"Error: {res.error}")
            else:
                print(f"Clean merge tree: {res.tree_sha}")
    elif args.heads:
        matrix = engine.run_matrix(args.heads, base_sha=args.base)
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

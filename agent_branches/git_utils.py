"""Git integration utilities for agent-branches client."""

import subprocess
from typing import List, Optional


def run_git_cmd(args: List[str], cwd: Optional[str] = None) -> Optional[str]:
    """Run a git command safely and return stripped stdout or None on error."""
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            return res.stdout.strip()
        return None
    except Exception:
        return None


def get_current_head_sha(cwd: Optional[str] = None) -> Optional[str]:
    """Return current HEAD commit SHA or None."""
    return run_git_cmd(["rev-parse", "HEAD"], cwd=cwd)


def get_current_branch(cwd: Optional[str] = None) -> Optional[str]:
    """Return current branch name or None."""
    branch = run_git_cmd(["branch", "--show-current"], cwd=cwd)
    if branch:
        return branch
    # If in detached HEAD, might return HEAD
    return run_git_cmd(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)


def get_remote_url(remote: str = "origin", cwd: Optional[str] = None) -> Optional[str]:
    """Return URL of given git remote or None."""
    return run_git_cmd(["remote", "get-url", remote], cwd=cwd)


def get_changed_files(
    base_sha: Optional[str] = None,
    head_sha: Optional[str] = None,
    cwd: Optional[str] = None,
) -> List[str]:
    """Return list of changed file paths between base_sha and head_sha."""
    if not head_sha:
        head_sha = "HEAD"
    if base_sha:
        out = run_git_cmd(["diff", "--name-only", f"{base_sha}...{head_sha}"], cwd=cwd)
        if out is None:
            # Fallback to direct range
            out = run_git_cmd(["diff", "--name-only", base_sha, head_sha], cwd=cwd)
    else:
        out = run_git_cmd(["diff", "--name-only", f"{head_sha}~1", head_sha], cwd=cwd)
        if out is None:
            out = run_git_cmd(["diff", "--name-only", "HEAD"], cwd=cwd)

    if not out:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]

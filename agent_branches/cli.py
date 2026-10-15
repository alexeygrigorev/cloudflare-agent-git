"""Command-line interface for agent-branches."""

import argparse
import json
import math
import os
from pathlib import Path
import shlex
import subprocess
import sys
from typing import List, Optional
from agent_branches.config import config_path, save_settings

from agent_branches.client import (
    AgentBranchesAPIError,
    AgentBranchesClient,
    AgentBranchesConnectionError,
    AgentBranchesError,
    StaleVectorError,
    TokenExpiredError,
    TokenRevokedError,
)

from agent_branches.git_utils import (
    get_changed_files,
    get_current_branch,
    get_current_head_sha,
    get_remote_url,
)


def format_task_created(res: dict) -> str:
    """Format task creation response."""
    task_id = res.get("taskId") or res.get("id") or res.get("task_id") or "unknown"
    agent_id = res.get("agentId") or res.get("agent_id") or res.get("agent") or ""
    fork_url = ""
    fork = res.get("fork")
    if isinstance(fork, dict):
        fork_url = fork.get("remote") or fork.get("name") or ""
    elif isinstance(fork, str):
        fork_url = fork
    if not fork_url:
        fork_url = res.get("fork_url") or res.get("forkUrl") or ""

    branch = res.get("branch") or res.get("ref", "").replace("refs/heads/", "")
    head = res.get("head") or res.get("head_sha") or res.get("base_sha") or "N/A"

    lines = [
        "========================================",
        "  TASK REGISTERED SUCCESSFULLY",
        "========================================",
        f"  Task ID:   {_display(task_id)}",
    ]
    if agent_id:
        lines.append(f"  Agent ID:  {_display(agent_id)}")
    if branch:
        lines.append(f"  Branch:    {_display(branch)}")
    if fork_url:
        lines.append(f"  Fork URL:  {_display(fork_url)}")
    lines.append(f"  Head SHA:  {_display(head)}")
    if res.get("intent"):
        lines.append(f"  Intent:    {_display(res.get('intent'))}")
    lines.append("========================================")
    return "\n".join(lines)


def format_push_result(res: dict) -> str:
    """Format push event response."""
    task_id = res.get("task_id") or res.get("taskId") or ""
    agent_id = res.get("agent_id") or res.get("agentId") or res.get("agent") or ""
    head_sha = res.get("head_sha") or res.get("sha") or "unknown"
    accepted = res.get("accepted", False)
    deduped = res.get("deduped", False)
    checks = res.get("radar_checks", res.get("radarChecks", 0))
    new_warnings = res.get("new_warnings", res.get("newWarnings", []))

    lines = [
        "========================================",
        "  WIP COMMIT PUSH REGISTERED",
        "========================================",
    ]
    if task_id:
        lines.append(f"  Task ID:      {_display(task_id)}")
    if agent_id:
        lines.append(f"  Agent ID:     {_display(agent_id)}")
    lines.extend([
        f"  Head SHA:     {_display(head_sha)}",
        f"  Accepted:     {_display(accepted)}",
        f"  Deduped:      {_display(deduped)}",
        f"  Radar Checks: {_display(checks)}",
    ])

    if new_warnings:
        lines.append(f"\n  WARNING: {len(new_warnings)} conflict warning(s) detected!")
        for w in new_warnings:
            wid = w.get("warning_id") or w.get("id") or "unknown"
            kind = w.get("kind", "textual")
            pair = w.get("pair", [])
            evidence = w.get("evidence", {})
            files = evidence.get("conflicting_files", []) if isinstance(evidence, dict) else []
            lines.append(f"  - [{_display(wid)}] ({_display(kind)}) Pair: {_display(pair)}")
            if files:
                lines.append(f"    Conflicting files: {', '.join(_display(path) for path in files)}")
            if isinstance(evidence, str):
                lines.append("    Details: " + _display(evidence))
            if isinstance(evidence, dict) and evidence.get("details"):
                lines.append(f"    Details: {_display(evidence.get('details'))}")
    else:
        lines.append("  Status:       Push recorded; compatibility requires current check results")

    lines.append("========================================")
    return "\n".join(lines)


def _display(value):
    """Keep peer text on its labelled terminal line without interpreting controls."""
    return "".join(char.encode("unicode_escape").decode("ascii")
                   if ord(char) < 32 or 127 <= ord(char) < 160 or char in "\u2028\u2029\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
                   else char for char in str(value))


def _valid_pair(pair):
    return (isinstance(pair, list) and len(pair) == 2
            and all(isinstance(agent, str) and agent for agent in pair) and pair[0] != pair[1])


def _valid_overlap(overlap):
    return (isinstance(overlap, dict) and _valid_pair(overlap.get("agents"))
            and isinstance(overlap.get("paths"), list) and bool(overlap["paths"])
            and all(isinstance(path, str) and path for path in overlap["paths"]))


def _scoped_records(records, agent_id, field, validator=None):
    if not isinstance(records, list):
        return records
    valid = validator or (lambda record: isinstance(record, dict) and _valid_pair(record.get(field)))
    # Unscopable records might concern this agent: retain their uncertainty.
    return [record for record in records if not valid(record) or agent_id in record[field]]


def _coordination_lines(res):
    lines = []
    pairs = res.get("pairs")
    if not isinstance(pairs, list):
        lines.append("\n  Compatibility Checks: UNKNOWN (no readable pair evidence)")
        pairs = []
    else:
        lines.append(f"\n  Compatibility Checks ({len(pairs)}):")
        if not pairs:
            lines.append("    UNKNOWN: no pair checks reported")
    for pair in pairs:
        if not isinstance(pair, dict) or not _valid_pair(pair.get("pair")):
            lines.append("    UNKNOWN: unreadable pair record")
            continue
        agents = pair["pair"]
        pair_heads = pair.get("heads") if isinstance(pair.get("heads"), dict) else {}
        current_heads = res.get("heads") if isinstance(res.get("heads"), dict) else {}
        current = all(isinstance(pair_heads.get(agent), str) and pair_heads[agent]
                      and pair_heads[agent] == current_heads.get(agent) for agent in agents)
        stale = bool(pair.get("stale")) or not current or bool(pair.get("unprocessedReason"))
        evidence = pair.get("evidence") if isinstance(pair.get("evidence"), dict) else {}
        coverage = pair.get("coverage") if isinstance(pair.get("coverage"), dict) else {}
        tests = coverage.get("passed", coverage.get("tests_collected", evidence.get("tests_collected", 0)))
        tested = ((isinstance(tests, int) and not isinstance(tests, bool) and tests > 0)
                  or (isinstance(tests, float) and math.isfinite(tests) and tests.is_integer() and tests > 0))
        tested = tested and (pair.get("coverage") is None or isinstance(pair.get("coverage"), dict))
        status = pair.get("status")
        if stale:
            label = "UNKNOWN (stale or missing current-head evidence)"
        elif status == "conflict":
            label = "CONFLICT"
        elif status == "clean" and tested:
            metric = "passed" if "passed" in coverage else "collected"
            label = f"CLEAN ({tests} combined test(s) {metric})"
        else:
            label = "UNKNOWN (current combination has not passed combined tests)"
        lines.append(f"    {' + '.join(_display(agent) for agent in agents)}: {label}")
        lines.append("      Checked commits: " + ", ".join(f"{_display(agent)}@{_display(pair_heads.get(agent) or 'unknown')[:8]}" for agent in agents))
        files = evidence.get("files") or evidence.get("conflicting_files")
        if status == "conflict" and not stale:
            if isinstance(files, list):
                lines.append("      Conflicting files: " + ", ".join(_display(path) for path in files))
            if evidence.get("summary"):
                lines.append("      " + _display(evidence["summary"]))
            elif isinstance(pair.get("evidence"), str):
                lines.append("      " + _display(pair["evidence"]))
    overlaps = res.get("plannedOverlaps")
    if not isinstance(overlaps, list):
        lines.append("\n  Planned overlaps: UNKNOWN (server did not report readable plan evidence)")
        return lines
    malformed = sum(not _valid_overlap(overlap) for overlap in overlaps)
    if malformed:
        lines.append(f"\n  Planned overlaps: UNKNOWN ({malformed} unreadable record(s))")
    if not overlaps:
        lines.append("\n  Planned overlaps: None reported (plans may be undeclared)")
    for overlap in overlaps:
        if _valid_overlap(overlap):
            lines.append("\n  Planned overlap (not a proven conflict): " + " + ".join(_display(agent) for agent in overlap["agents"]))
            lines.append("    Planned files: " + ", ".join(_display(path) for path in overlap["paths"]))
            lines.append("    Next: agree file ownership or split the work before editing.")
    return lines


def _warning_lines(res, task_id=None):
    title = "Radar Warnings" if task_id else "Active Warnings"
    warnings = res.get("warnings")
    if not isinstance(warnings, list):
        return [f"\n  {title}: UNKNOWN (no readable warning evidence)"]
    valid = [warning for warning in warnings if isinstance(warning, dict)
             and _valid_pair(warning.get("pair")) and isinstance(warning.get("status"), str)
             and warning["status"] in ("active", "invalidated", "acknowledged", "resolved")]
    unknown = len(warnings) - len(valid)
    lines = [f"\n  {title}: UNKNOWN ({unknown} unreadable record(s))"] if unknown else []
    active = [warning for warning in valid if warning["status"] == "active"]
    if not active:
        if not unknown:
            lines.append(f"\n  {title}: None (compatibility is not inferred from absent warnings)")
        return lines
    lines.append(f"\n  Active {title} ({len(active)}):" if task_id else f"\n  {title} ({len(active)}):")
    for warning in active:
        wid = warning.get("warning_id") or warning.get("id") or "unknown"
        lines.append(f"    * [{_display(wid)}] ({_display(warning.get('kind', 'textual'))}) Pair: "
                     + " + ".join(_display(agent) for agent in warning["pair"]))
        evidence = warning.get("evidence") if isinstance(warning.get("evidence"), dict) else {}
        files = evidence.get("conflicting_files") or evidence.get("files")
        if isinstance(files, list):
            lines.append("      Conflicting files: " + ", ".join(_display(path) for path in files))
        if task_id:
            lines.append("      Next: coordinate a fix, publish the updated change and wait for current checks. "
                         f"Acknowledge with `uv run branches ack --task-id {shlex.quote(_display(task_id))} --warning-id {shlex.quote(_display(wid))} --action rebased_locally`.")
    return lines


def format_status_result(res: dict, task_id: Optional[str] = None) -> str:
    """Render coordinator evidence without treating missing data as a clean result."""
    if not isinstance(res, dict):
        return "UNKNOWN: coordinator status is not a readable object"
    lines = ["========================================"]
    if task_id or "task_id" in res or "taskId" in res:
        tid = res.get("task_id") or res.get("taskId") or task_id
        lines.extend([f"  TASK STATUS: {_display(tid)}", "========================================",
                      f"  Status:    {_display(res.get('status', 'active'))}"])
        agent = res.get("agent_id") or res.get("agentId") or res.get("agent") or ""
        if agent:
            lines.append(f"  Agent ID:  {_display(agent)}")
        branch = res.get("branch") or str(res.get("ref") or "").removeprefix("refs/heads/")
        if branch:
            lines.append(f"  Branch:    {_display(branch)}")
        lines.append(f"  Head SHA:  {_display(res.get('head_sha') or res.get('head') or 'N/A')}")
        if res.get("intent"):
            lines.append(f"  Intent:    {_display(res['intent'])}")
        if res.get("test_provenance"):
            lines.append(f"  Recorded tests: {_display(res['test_provenance'])}")
        lines.extend(_warning_lines(res, tid))
    else:
        lines.extend(["  RADAR / COORDINATOR STATUS", "========================================"])
        canonical = res.get("canonical")
        if isinstance(canonical, dict):
            lines.append(f"  Canonical: {_display(canonical.get('name') or 'canonical')}")
        tasks = res.get("agents", res.get("tasks"))
        if isinstance(tasks, list):
            lines.append(f"  Active Tasks ({len(tasks)}):")
            for task in tasks:
                if not isinstance(task, dict):
                    lines.append("    UNKNOWN: unreadable agent record")
                    continue
                tid = task.get("task_id") or task.get("taskId") or task.get("id") or "unknown"
                agent = task.get("agent_id") or task.get("agentId") or task.get("agent") or ""
                branch = task.get("branch") or str(task.get("ref") or "").removeprefix("refs/heads/") or "main"
                head = _display(task.get("head_sha") or task.get("head") or "")[:8]
                lines.append(f"    - {_display(tid)} (branch: {_display(branch)}, head: {head}, agent: {_display(agent)})")
        else:
            lines.append("  Active Tasks: UNKNOWN (no readable agent evidence)")
        lines.extend(_warning_lines(res))
    lines.extend(_coordination_lines(res))
    lines.append("========================================")
    return "\n".join(lines)


def format_ack_result(res: dict) -> str:
    """Format warning acknowledgement response."""
    wid = res.get("warning_id") or res.get("id") or "unknown"
    tid = res.get("task_id") or res.get("taskId") or "unknown"
    action = res.get("action") or "acknowledged"
    time_str = res.get("acknowledged_at") or "now"

    return "\n".join([
        "========================================",
        "  WARNING ACKNOWLEDGED",
        "========================================",
        f"  Warning ID: {_display(wid)}",
        f"  Task ID:    {_display(tid)}",
        f"  Action:     {_display(action)}",
        f"  Time:       {_display(time_str)}",
        "========================================",
    ])


def format_checks_result(res: dict) -> str:

    """Format checks submission response."""
    accepted = res.get("accepted", 0)
    pairs = res.get("pairs", [])
    created = res.get("createdWarnings", [])

    lines = [
        "========================================",
        "  RADAR CHECKS SUBMITTED (CONTRACT v0.1)",
        "========================================",
        f"  Accepted:  {_display(accepted)} check(s)",
        f"  Pairs:     {len(pairs)}",
        f"  Warnings:  {len(created)} created",
    ]
    if created:
        lines.append("\n  New Warning(s):")
        for w in created:
            wid = w.get("id") or w.get("warning_id") or "unknown"
            status = w.get("status", "active")
            reason = w.get("reason", "unknown")
            lines.append(f"  - [{_display(wid)}] ({_display(status)}) {_display(reason)}")
    lines.append("========================================")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:

    """Construct argument parser for agent-branches CLI."""
    parser = argparse.ArgumentParser(
        prog="agent-branches",
        description="L2 Agent Client CLI for Cloudflare Agent Branches",
    )
    parser.add_argument(
        "--server",
        help="L1 Coordinator server URL (default: $AGENT_BRANCHES_SERVER or http://127.0.0.1:8787)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON response",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # task command
    task_parser = subparsers.add_parser("task", help="Task operations")
    task_sub = task_parser.add_subparsers(dest="task_action", help="Task actions")

    task_create = task_sub.add_parser("create", help="Register a new task")
    task_create.add_argument("--repo", help="Optional repository context (or private configuration)")
    task_create.add_argument("--base-sha", help="Optional base commit override (defaults to coordinator canonical HEAD)")
    task_create.add_argument("--intent", default="", help="High-level task intent description")
    task_create.add_argument("--branch", help="Optional branch context (defaults to coordinator task ref)")
    task_create.add_argument("--agent", help="Agent identifier / name prefix")
    task_create.add_argument("--ttl-seconds", type=int, help="Fork token TTL in seconds")
    task_create.add_argument("--files", help="Comma-separated planned file paths, declared before editing")
    task_create.add_argument(
        "--admin-token",
        help="Admin bearer token for authorized task creation (or $ADMIN_TOKEN)",
    )
    task_create.add_argument("--server", help="Coordinator URL")
    task_create.add_argument("--json", action="store_true", help="Output raw JSON")

    # push command
    push_parser = subparsers.add_parser("push", help="Register a WIP commit push")
    push_parser.add_argument("--task-id", help="Task identifier (used to resolve agent ID if omitted)")
    push_parser.add_argument("--agent-id", help="Explicit agent identifier required by L1 coordinator")
    push_parser.add_argument("--head-sha", help="WIP commit SHA (defaults to git HEAD)")
    push_parser.add_argument("--base-sha", help="Base commit SHA")
    push_parser.add_argument(
        "--files-changed",
        help="Comma-separated list of changed files (auto-detected via git if omitted)",
    )
    push_parser.add_argument(
        "--intent-update",
        help="Updated task intent description",
    )
    push_parser.add_argument(
        "--intent",
        dest="intent_update",
        help="Alias for --intent-update",
    )
    push_parser.add_argument(
        "--test-provenance",
        help="Test execution provenance evidence (e.g. 'vitest: 14 passed')",
    )
    push_parser.add_argument("--server", help="Coordinator URL")
    push_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # status command
    status_parser = subparsers.add_parser("status", help="Query coordinator and radar status")
    status_parser.add_argument(
        "--task-id", help="Task ID to query specific task status and active warnings"
    )
    status_parser.add_argument("--server", help="Coordinator URL")
    status_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # ack command
    ack_parser = subparsers.add_parser("ack", help="Acknowledge an active radar conflict warning")
    ack_parser.add_argument(
        "--task-id", required=True, help="Task identifier acknowledging the warning"
    )
    ack_parser.add_argument(
        "--warning-id", required=True, help="Warning identifier being acknowledged"
    )
    ack_parser.add_argument(
        "--action",
        default="rebased_locally",
        help="Action taken to address warning (e.g. 'rebased_locally', 'manual_merge')",
    )
    ack_parser.add_argument("--server", help="Coordinator URL")
    ack_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    # checks command (CONTRACT v0.1)
    checks_parser = subparsers.add_parser(
        "checks", help="Submit radar check results (CONTRACT v0.1)"
    )
    checks_parser.add_argument(
        "--file",
        help="Path to JSON checks payload file (reads from stdin if omitted)",
    )
    checks_parser.add_argument(
        "--runner-token",
        help="Runner bearer token for check submission (or $RUNNER_TOKEN)",
    )
    checks_parser.add_argument("--server", help="Coordinator URL")
    checks_parser.add_argument("--json", action="store_true", help="Output raw JSON")

    configure = subparsers.add_parser("configure", help="Save private per-project coordinator settings")
    configure.add_argument("--server")
    configure.add_argument("--repo")
    configure.add_argument("--base-sha")
    configure.add_argument("--branch")
    configure.add_argument("--runner-token-file")
    configure.add_argument("--admin-token-file")
    configure.add_argument("--task-id")
    configure.add_argument("--task-token-file")
    configure.add_argument("--test-command", help="Explicit operator-owned combined-test command; executed without a shell")

    plan = subparsers.add_parser("plan", help="Declare planned file paths for an existing task")
    plan.add_argument("--task-id", required=True)
    plan.add_argument("--files", required=True, help="Comma-separated paths; an empty value clears the plan")
    plan.add_argument("--server")
    plan.add_argument("--json", action="store_true")

    publish = subparsers.add_parser("publish", help="Push HEAD to this task's verified own fork, then notify the coordinator")
    publish.add_argument("--task-id", required=True)
    publish.add_argument("--server")
    publish.add_argument("--json", action="store_true")

    watch = subparsers.add_parser("watch", help="Continuously check independently published agent changes on this computer")
    watch.add_argument("--server")
    watch.add_argument("--test-command", help="Explicit python -m unittest/pytest command with structured results (or private configuration)")
    watch.add_argument("--test-timeout", type=float, default=60)
    watch.add_argument("--poll-interval", type=float, default=10)
    watch.add_argument("--duration", type=float, help="Stop after this many seconds")
    watch.add_argument("--once", action="store_true", help="Check the current vector once and exit")

    return parser



def handle_task_create(args: argparse.Namespace, client: AgentBranchesClient, as_json: bool) -> int:
    settings = client.settings if isinstance(getattr(client, "settings", None), dict) else {}
    # The coordinator owns canonical Git context. Cwd may be unrelated Git.
    repo = args.repo or os.environ.get("AGENT_BRANCHES_REPO") or settings.get("repo")
    base_sha = args.base_sha or os.environ.get("AGENT_BRANCHES_BASE_SHA") or settings.get("base_sha")
    branch = args.branch or os.environ.get("AGENT_BRANCHES_BRANCH") or settings.get("branch")
    intent = args.intent or ""
    agent = getattr(args, "agent", None)
    ttl = getattr(args, "ttl_seconds", None)
    admin_token = getattr(args, "admin_token", None) or os.environ.get("ADMIN_TOKEN")

    res = client.create_task(
        repo=repo,
        base_sha=base_sha,
        intent=intent,
        branch=branch,
        agent=agent,
        ttl_seconds=ttl,
        admin_token=admin_token,
    )
    client.remember_task(res)
    if getattr(args, "files", None) is not None:
        res["plan"] = client.plan_task(res["taskId"], [path.strip() for path in args.files.split(",") if path.strip()])
    if as_json:
        print(json.dumps(res, indent=2))
    else:
        print(format_task_created(res))
        if "plan" in res:
            print(format_plan_result(res["plan"]))
    return 0


def handle_push(args: argparse.Namespace, client: AgentBranchesClient, as_json: bool) -> int:
    task_id = getattr(args, "task_id", None)
    agent_id = getattr(args, "agent_id", None)

    if not task_id and not agent_id:
        print("Error: either --task-id or --agent-id must be specified", file=sys.stderr)
        return 2

    head_sha = args.head_sha or get_current_head_sha()
    if not head_sha:
        print("Error: --head-sha is required when not in a valid git repository", file=sys.stderr)
        return 1

    files_changed: Optional[List[str]] = None
    if args.files_changed:
        files_changed = [f.strip() for f in args.files_changed.split(",") if f.strip()]
    elif args.base_sha:
        files_changed = get_changed_files(base_sha=args.base_sha, head_sha=head_sha)

    try:
        res = client.push(
            task_id=task_id,
            agent_id=agent_id,
            head_sha=head_sha,
            base_sha=args.base_sha,
            files_changed=files_changed,
            intent=args.intent_update,
            test_provenance=args.test_provenance,
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(res, indent=2))
    else:
        print(format_push_result(res))
    return 0



def handle_status(args: argparse.Namespace, client: AgentBranchesClient, as_json: bool) -> int:
    if args.task_id:
        res = client.get_task(args.task_id)
        if as_json:
            print(json.dumps(res, indent=2))
        else:
            agent_id = res.get("agentId") or res.get("agent_id")
            if not isinstance(agent_id, str) or not agent_id.strip():
                raise ValueError("Task response lacks a valid agent identity; coordination evidence is UNKNOWN")
            credential = client.task_token(args.task_id)
            if not credential:
                raise ValueError("No credential for selected task; coordination evidence is UNKNOWN")
            snapshot = client.get_status(token=credential)
            if not isinstance(snapshot, dict):
                raise ValueError("Coordinator status is unreadable; coordination evidence is UNKNOWN")
            res = {key: res[key] for key in ("taskId", "task_id", "agentId", "agent_id", "status", "ref", "branch", "intent", "test_provenance") if key in res}
            res["heads"] = snapshot.get("heads") if isinstance(snapshot.get("heads"), dict) else {}
            res["head"] = res["heads"].get(agent_id)
            res["head_sha"] = res["head"]
            res["pairs"] = _scoped_records(snapshot.get("pairs"), agent_id, "pair")
            res["plannedOverlaps"] = _scoped_records(snapshot.get("plannedOverlaps"), agent_id, "agents", _valid_overlap)
            res["warnings"] = _scoped_records(snapshot.get("warnings"), agent_id, "pair")
            print(format_status_result(res, task_id=args.task_id))
    else:
        res = client.get_status()
        if as_json:
            print(json.dumps(res, indent=2))
        else:
            print(format_status_result(res, task_id=None))
    return 0


def handle_ack(args: argparse.Namespace, client: AgentBranchesClient, as_json: bool) -> int:
    res = client.ack_warning(
        warning_id=args.warning_id,
        task_id=args.task_id,
        action=args.action,
    )
    if as_json:
        print(json.dumps(res, indent=2))
    else:
        print(format_ack_result(res))
    return 0


def handle_checks(args: argparse.Namespace, client: AgentBranchesClient, as_json: bool) -> int:
    payload_raw = None
    if getattr(args, "file", None):
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                payload_raw = f.read()
        except OSError as exc:
            print(f"Error reading file '{args.file}': {exc}", file=sys.stderr)
            return 1
    else:
        if sys.stdin.isatty():
            print("Error: specify --file <payload.json> or pipe JSON to stdin", file=sys.stderr)
            return 1
        payload_raw = sys.stdin.read()

    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError as exc:
        print(f"Error parsing JSON payload: {exc}", file=sys.stderr)
        return 1

    runner_token = getattr(args, "runner_token", None) or os.environ.get("RUNNER_TOKEN")

    try:
        res = client.send_checks(payload, runner_token=runner_token)
    except StaleVectorError as exc:
        if as_json:
            print(
                json.dumps(
                    {
                        "error": "stale_vector",
                        "status_code": 409,
                        "message": exc.message,
                        "details": exc.payload,
                    },
                    indent=2,
                ),
                file=sys.stderr,
            )
        else:
            print(f"Conflict Error (409): Stale vector - {exc.message}", file=sys.stderr)
            if exc.payload:
                print(f"Details: {exc.payload}", file=sys.stderr)
        return 1
    except TokenExpiredError as exc:
        print(
            f"Authentication Error ({exc.status_code}): Bearer token expired - "
            f"credentials reported expired by coordinator. Halting (no retry). "
            f"Refresh the token and try again. Details: {exc.message}",
            file=sys.stderr,
        )
        return 1
    except TokenRevokedError as exc:
        print(
            f"Authentication Error ({exc.status_code}): Bearer token revoked - "
            f"failing closed, retrying cannot succeed. "
            f"Issuer a new token. Details: {exc.message}",
            file=sys.stderr,
        )
        return 1
    except (ValueError, AgentBranchesAPIError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if as_json:
        print(json.dumps(res, indent=2))
    else:
        print(format_checks_result(res))
    return 0


def format_plan_result(result):
    paths = result.get("plannedPaths")
    readable = isinstance(paths, list) and all(isinstance(path, str) for path in paths)
    lines = [f"Planned files for {_display(result.get('agentId', result.get('taskId', 'task')))}: "
             + ((", ".join(_display(path) for path in paths) or "none (plan cleared)") if readable else "UNKNOWN")]
    overlaps = result.get("plannedOverlaps")
    unknown = not isinstance(overlaps, list) or any(not _valid_overlap(overlap) for overlap in overlaps)
    if unknown:
        lines.append("Planned overlaps: UNKNOWN (unreadable or missing plan evidence)")
    for overlap in overlaps if isinstance(overlaps, list) else []:
        if _valid_overlap(overlap):
            lines.append("PLANNED OVERLAP: " + " + ".join(_display(agent) for agent in overlap["agents"])
                         + ": " + ", ".join(_display(path) for path in overlap["paths"]))
    if isinstance(overlaps, list) and any(_valid_overlap(overlap) for overlap in overlaps):
        lines.append("Coordinate ownership before editing. This overlap is not a proven merge conflict.")
    elif not unknown:
        lines.append("No reported planned overlaps; other agents may have undeclared plans.")
    return "\n".join(lines)


def handle_configure(args, client):
    changes = {}
    for key in ("repo", "base_sha", "branch"):
        value = getattr(args, key, None) or os.environ.get("AGENT_BRANCHES_" + key.upper())
        if value:
            changes[key] = value
    for role in ("runner", "admin"):
        token_file = getattr(args, role + "_token_file")
        token = Path(token_file).read_text().strip() if token_file else os.environ.get(role.upper() + "_TOKEN")
        if token:
            changes[role + "_token"] = token
    if args.test_command:
        changes["test_command"] = shlex.split(args.test_command)
    client.settings = save_settings(client.server_url, changes=changes)
    if args.task_id or args.task_token_file:
        if not args.task_id or not args.task_token_file:
            raise ValueError("Importing a task requires both --task-id and --task-token-file")
        token = Path(args.task_token_file).read_text().strip()
        task = client.get_task(args.task_id, token=token)
        task["token"] = {"plaintext": token}
        client.remember_task(task)
    print(f"Private project configuration saved to {config_path()}. Credentials are not printed.")
    return 0


def handle_publish(args, client, as_json):
    from agent_branches.checker import validated_remote
    token = client.task_tokens.get(args.task_id) or os.environ.get("TASK_TOKEN")
    if not token:
        raise ValueError("Register or import this task's private credential before publishing")
    task = client.get_task(args.task_id, token=token)
    expected = task.get("forkRemote") or (task.get("fork") or {}).get("remote")
    expected = validated_remote(client.server_url, expected or "")
    actual = get_remote_url()
    if not actual or validated_remote(client.server_url, actual) != expected:
        raise ValueError("Refusing publish: origin is not this task's own registered fork")
    head = get_current_head_sha()
    ref = task.get("ref", "refs/heads/main")
    if not head or not ref.startswith("refs/heads/") or any(character in ref for character in (" ", ":", "..")):
        raise ValueError("Cannot verify the current commit or registered destination ref")
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_COUNT": "2",
           "GIT_CONFIG_KEY_0": "http.extraHeader", "GIT_CONFIG_VALUE_0": f"Authorization: Bearer {token}",
           "GIT_CONFIG_KEY_1": "http.followRedirects", "GIT_CONFIG_VALUE_1": "false"}
    result = subprocess.run(["git", "push", "origin", "HEAD:" + ref], env=env, capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError("Git push to the verified task fork failed; no coordinator notification was sent")
    recorded = client.push(task_id=args.task_id, agent_id=task.get("agentId"), head_sha=head, token=token)
    print(json.dumps(recorded, indent=2) if as_json else format_push_result(recorded))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    server_url = getattr(args, "server", None)
    as_json = bool(getattr(args, "json", False))
    try:
        client = AgentBranchesClient(server_url=server_url)
        if args.command == "task":
            if getattr(args, "task_action", None) == "create":
                return handle_task_create(args, client, as_json)
            else:
                parser.parse_args(["task", "--help"])
                return 1
        elif args.command == "push":
            return handle_push(args, client, as_json)
        elif args.command == "status":
            return handle_status(args, client, as_json)
        elif args.command == "ack":
            return handle_ack(args, client, as_json)
        elif args.command == "checks":
            return handle_checks(args, client, as_json)
        elif args.command == "configure":
            return handle_configure(args, client)
        elif args.command == "plan":
            result = client.plan_task(args.task_id, [path.strip() for path in args.files.split(",") if path.strip()])
            print(json.dumps(result, indent=2) if as_json else format_plan_result(result))
            return 0
        elif args.command == "publish":
            return handle_publish(args, client, as_json)
        elif args.command == "watch":
            from agent_branches.checker import watch
            if not (os.environ.get("RUNNER_TOKEN") or client.settings.get("runner_token")):
                raise ValueError("Configure the authenticated client's runner credential before starting watch")
            command = shlex.split(args.test_command) if args.test_command else client.settings.get("test_command")
            watch(client, command, poll_interval=args.poll_interval, duration=args.duration, once=args.once,
                  test_timeout=args.test_timeout)
            return 0
        else:
            parser.print_help()
            return 1
    except AgentBranchesConnectionError as exc:
        print(f"Connection Error: {exc}", file=sys.stderr)
        return 2
    except StaleVectorError as exc:
        print(f"Conflict Error (409): Stale vector - {exc.message}", file=sys.stderr)
        return 1
    except TokenExpiredError as exc:
        print(
            f"Authentication Error ({exc.status_code}): Bearer token expired - "
            f"credentials reported expired by coordinator. Halting (no retry). "
            f"Refresh the token and try again. Details: {exc.message}",
            file=sys.stderr,
        )
        return 1
    except TokenRevokedError as exc:
        print(
            f"Authentication Error ({exc.status_code}): Bearer token revoked - "
            f"failing closed, retrying cannot succeed. "
            f"Issuer a new token. Details: {exc.message}",
            file=sys.stderr,
        )
        return 1
    except AgentBranchesAPIError as exc:
        print(f"API Error ({exc.status_code}): {exc.message}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1



if __name__ == "__main__":
    sys.exit(main())

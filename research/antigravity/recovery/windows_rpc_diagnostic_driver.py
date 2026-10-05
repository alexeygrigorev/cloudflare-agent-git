#!/usr/bin/env python3
"""
Windows RPC Diagnostic Driver (Codex Principal Directive C2267).

A pure standard-library CLI driver designed to run on Windows (or Linux)
to invoke remote FileBus RPC operations over OpenSSH (`ssh.exe` or `ssh`).

Key Architectural & Security Properties:
1. Zero Secrets on sys.argv:
   - Reads bearer credentials strictly from standard input (`sys.stdin`),
     matching Desktop Root's verified DPAPI PowerShell integration pattern.
   - Tokens never appear in command-line arguments, process tables, or shell history.
2. Hardened OpenSSH Invocations:
   - Enforces `-o BatchMode=yes` and `-o StrictHostKeyChecking=yes`.
   - Inserts `--` delimiter before the remote host to defeat option injection.
   - Escapes remote paths via `shlex.quote` for the remote POSIX login shell.
3. Clean JSON Output:
   - Emits structured, sanitized JSON to stdout.
   - Sanitizes error outputs to ensure zero token leakage on failure.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
from typing import Any
from uuid import uuid4


def sanitize_text(text: str) -> str:
    """Redacts tokens, passwords, and sensitive keys from output strings."""
    if not text:
        return ""
    t = re.sub(
        r'("(?:token|parent_token|password|secret)":\s*")[^"]+(")',
        r'\1[REDACTED]\2',
        text,
    )
    t = re.sub(r'(token=)[^\s&]+', r'\1[REDACTED]', t)
    t = re.sub(r'(bearer\s+)[a-zA-Z0-9_\-\.]+', r'\1[REDACTED]', t, flags=re.IGNORECASE)
    return t


def read_credential_from_stdin() -> tuple[str, str | None]:
    """
    Reads credential token strictly from sys.stdin.
    Supports either:
    1. Raw token string (trimmed).
    2. JSON object containing "token" and optional "identity_id" / "sender_id".
    Returns (token, identity_id_or_none).
    """
    if sys.stdin.isatty():
        raise ValueError(
            "Authentication token must be piped via stdin (matching Desktop Root DPAPI pattern); "
            "interactive TTY input without stdin pipe is prohibited."
        )

    raw_input = sys.stdin.read().strip()
    if not raw_input:
        raise ValueError("Stdin was empty; expected bearer token or credential JSON")

    # Try parsing as JSON credential
    try:
        data = json.loads(raw_input)
        if isinstance(data, dict):
            token = data.get("token")
            if not token:
                raise ValueError("JSON credential on stdin must contain a 'token' field")
            ident_id = data.get("identity_id") or data.get("sender_id")
            return str(token), str(ident_id) if ident_id else None
    except json.JSONDecodeError:
        pass

    # Treat raw input as plain token string
    return raw_input, None


def build_ssh_command(
    ssh_binary: str,
    host: str,
    remote_cli: str,
    store_path: str,
) -> list[str]:
    """Constructs the hardened OpenSSH command line."""
    if host.startswith("-"):
        raise ValueError(f"Host operand must not start with '-': {host}")

    remote_parts = [
        "python3",
        shlex.quote(remote_cli),
        "--store",
        shlex.quote(store_path),
        "rpc",
    ]

    return [
        ssh_binary,
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "--",
        host,
    ] + remote_parts


def run_rpc_operation(
    cmd: list[str],
    rpc_request: dict[str, Any],
    timeout_sec: float = 30.0,
) -> dict[str, Any]:
    """Executes the remote OpenSSH command piping the RPC JSON request over stdin."""
    stdin_payload = json.dumps(rpc_request)

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        stdout, stderr = proc.communicate(input=stdin_payload, timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2.0)
        raise TimeoutError(f"RPC transport timed out after {timeout_sec}s")

    if proc.returncode != 0:
        clean_stderr = sanitize_text(stderr.strip())
        raise RuntimeError(
            f"Remote SSH command failed with exit {proc.returncode}: {clean_stderr or 'no stderr'}"
        )

    raw_stdout = stdout.strip()
    if not raw_stdout:
        raise ValueError("Remote host returned empty output framing")

    try:
        resp_obj = json.loads(raw_stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON response framing from remote host: {exc}")

    if not isinstance(resp_obj, dict):
        raise ValueError(f"Expected JSON object in RPC response, got {type(resp_obj).__name__}")

    return resp_obj


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Windows RPC Diagnostic Driver: executes remote FileBus RPC via OpenSSH stdin streaming."
    )
    parser.add_argument("--host", default="hetzner", help="Remote SSH host destination (default: hetzner)")
    parser.add_argument("--remote-cli", required=True, help="Absolute path to bus_cli.py on remote host")
    parser.add_argument("--store", required=True, help="Absolute path to FileBus store on remote host")
    parser.add_argument("--ssh-binary", default="ssh", help="SSH binary path (default: ssh, or ssh.exe on Windows)")
    parser.add_argument(
        "--action",
        required=True,
        choices=["inbox", "send", "ack", "reply", "enroll"],
        help="RPC operation to perform",
    )
    parser.add_argument("--repo-dir", help="Optional local repo directory to append to sys.path")

    # Action-specific arguments (none of these contain credentials)
    parser.add_argument("--identity-id", help="Identity ID for inbox/ack/send")
    parser.add_argument("--to", dest="recipient_id", help="Recipient ID for send")
    parser.add_argument("--body", help="Message body for send/reply")
    parser.add_argument("--data", help="JSON data payload string for send/reply")
    parser.add_argument("--message-id", help="Message ID for ack/reply")
    parser.add_argument("--idempotency-key", help="Idempotency key for send/reply")
    parser.add_argument("--agent-name", help="Agent name for enroll")
    parser.add_argument("--device-id", help="Device ID for enroll")
    parser.add_argument("--project-id", default="agent-coordination", help="Project ID for enroll")
    parser.add_argument("--task-id", help="Task ID for enroll")
    parser.add_argument("--all", dest="include_read", action="store_true", help="Include read messages in inbox")
    parser.add_argument("--timeout", type=float, default=30.0, help="Command timeout in seconds")

    args = parser.parse_args()

    if args.repo_dir:
        repo_path = Path(args.repo_dir).resolve()
        if str(repo_path) not in sys.path:
            sys.path.insert(0, str(repo_path))

    # Read credential token strictly from stdin (except for unauthenticated enroll)
    token: str | None = None
    stdin_ident_id: str | None = None
    if args.action != "enroll":
        try:
            token, stdin_ident_id = read_credential_from_stdin()
        except Exception as exc:
            err_output = {"ok": False, "error": {"code": "credential_error", "message": str(exc)}}
            print(json.dumps(err_output, indent=2))
            return 1

    ident_id = args.identity_id or stdin_ident_id
    req_id = f"diag-{uuid4()}"
    params: dict[str, Any] = {}

    if args.action == "enroll":
        if not args.agent_name or not args.device_id:
            print(json.dumps({"ok": False, "error": "enroll requires --agent-name and --device-id"}, indent=2))
            return 1
        params = {
            "agent_name": args.agent_name,
            "device_id": args.device_id,
            "project_id": args.project_id,
            "task_id": args.task_id,
        }
    elif args.action == "inbox":
        if not ident_id:
            print(json.dumps({"ok": False, "error": "inbox requires identity ID (via flag or stdin JSON)"}, indent=2))
            return 1
        params = {
            "identity_id": ident_id,
            "token": token,
            "unread_only": not args.include_read,
        }
    elif args.action == "send":
        if not ident_id or not args.recipient_id or not args.body:
            print(json.dumps({"ok": False, "error": "send requires sender ID, --to, and --body"}, indent=2))
            return 1
        params = {
            "sender_id": ident_id,
            "token": token,
            "recipient_id": args.recipient_id,
            "body": args.body,
            "data": json.loads(args.data) if args.data else None,
            "idempotency_key": args.idempotency_key,
        }
    elif args.action == "ack":
        if not ident_id or not args.message_id:
            print(json.dumps({"ok": False, "error": "ack requires identity ID and --message-id"}, indent=2))
            return 1
        params = {
            "identity_id": ident_id,
            "token": token,
            "message_id": args.message_id,
        }
    elif args.action == "reply":
        if not ident_id or not args.message_id or not args.body:
            print(json.dumps({"ok": False, "error": "reply requires sender ID, --message-id, and --body"}, indent=2))
            return 1
        params = {
            "sender_id": ident_id,
            "token": token,
            "message_id": args.message_id,
            "body": args.body,
            "data": json.loads(args.data) if args.data else None,
            "idempotency_key": args.idempotency_key,
        }

    rpc_req = {
        "op": args.action,
        "request_id": req_id,
        "params": params,
    }

    try:
        cmd = build_ssh_command(
            ssh_binary=args.ssh_binary,
            host=args.host,
            remote_cli=args.remote_cli,
            store_path=args.store,
        )
        resp = run_rpc_operation(cmd, rpc_req, timeout_sec=args.timeout)
        print(json.dumps(resp, indent=2, ensure_ascii=False))
        return 0 if resp.get("ok") else 2
    except Exception as exc:
        err_msg = sanitize_text(str(exc))
        out = {
            "ok": False,
            "error": {
                "code": "rpc_driver_failure",
                "message": err_msg,
            },
        }
        print(json.dumps(out, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())

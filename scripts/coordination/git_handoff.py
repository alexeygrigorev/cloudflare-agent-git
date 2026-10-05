#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
import os

APLEXER_BIN = os.path.expanduser("~/.local/bin/a")

def run_cmd(cmd, check=True):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error running command {' '.join(cmd)}:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return result

def get_git_head():
    result = run_cmd(["git", "rev-parse", "HEAD"])
    return result.stdout.strip()

def check_git_clean():
    result = run_cmd(["git", "status", "--porcelain"])
    if result.stdout.strip():
        return False
    return True

def cmd_send(args):
    current_head = args.head
    if not current_head:
        current_head = get_git_head()
    
    data = {
        "task": args.task,
        "acceptance_policy": args.policy,
        "fork": args.fork,
        "base": args.base,
        "current_head": current_head,
    }
    
    cmd = [
        APLEXER_BIN, "message", "send",
        "--to", args.to,
        "--kind", "handoff",
        "--data", json.dumps(data),
        "--queue"
    ]
    if args.idempotency_key:
        cmd.extend(["--idempotency-key", args.idempotency_key])
        
    cmd.append(args.text)
    
    # Send the message
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Failed to send handoff: {res.stderr}", file=sys.stderr)
        sys.exit(1)
    print("Git-bound session handoff sent successfully.")
    if res.stdout.strip():
        print(res.stdout.strip())

def cmd_accept(args):
    # Retrieve message
    res = run_cmd([APLEXER_BIN, "message", "show", args.message_id, "--json"])
    try:
        msg = json.loads(res.stdout)
    except json.JSONDecodeError:
        print("Failed to parse message JSON.", file=sys.stderr)
        sys.exit(1)
        
    if msg.get("kind") != "handoff":
        print(f"Message {args.message_id} is not a handoff (kind: {msg.get('kind')})", file=sys.stderr)
        sys.exit(1)
        
    data = msg.get("data")
    if not data:
        print("Handoff message is missing data payload.", file=sys.stderr)
        sys.exit(1)
        
    expected_head = data.get("current_head")
    task = data.get("task")
    policy = data.get("acceptance_policy")
    
    print(f"Evaluating handoff {args.message_id}...")
    print(f"Task: {task}")
    print(f"Acceptance Policy: {policy}")
    print(f"Expected HEAD: {expected_head}")
    
    # Canonical drift detection
    if not check_git_clean():
        print("Canonical drift detection failed: workspace has uncommitted changes.", file=sys.stderr)
        sys.exit(1)
        
    local_head = get_git_head()
    if local_head != expected_head:
        print(f"Canonical drift detection failed: local head ({local_head}) does not match expected ({expected_head}).", file=sys.stderr)
        print(f"Please checkout or sync to {expected_head} before accepting this handoff.", file=sys.stderr)
        sys.exit(1)
        
    # Acknowledge the message (Receiver Deduplication / Acceptance)
    ack_res = run_cmd([APLEXER_BIN, "message", "ack", args.message_id])
    print("Canonical drift detection passed. Recoverable code ensured.")
    print("Handoff accepted and acknowledged.")
    
def main():
    parser = argparse.ArgumentParser(description="Git-Bound Session Handoff CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    send_parser = subparsers.add_parser("send", help="Send a Git-bound handoff message")
    send_parser.add_argument("--to", required=True, help="Recipient tag or session id")
    send_parser.add_argument("--task", required=True, help="Task ID/Description")
    send_parser.add_argument("--policy", required=True, help="Acceptance policy")
    send_parser.add_argument("--fork", required=True, help="Fork name or URL")
    send_parser.add_argument("--base", required=True, help="Base commit or branch")
    send_parser.add_argument("--head", help="Current head commit (inferred if omitted)")
    send_parser.add_argument("--idempotency-key", help="Key for receiver deduplication")
    send_parser.add_argument("text", help="Message text body")
    
    accept_parser = subparsers.add_parser("accept", help="Accept a handoff and perform drift detection")
    accept_parser.add_argument("message_id", help="Message ID to accept")
    
    args = parser.parse_args()
    if args.command == "send":
        cmd_send(args)
    elif args.command == "accept":
        cmd_accept(args)

if __name__ == "__main__":
    main()

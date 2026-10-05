#!/usr/bin/env python3
"""
Windows RPC Diagnostic Driver (Codex Principal Directives C2267 & C2274).

A hardened standard-library diagnostic driver designed to run on Windows (or Linux)
to invoke remote FileBus RPC operations by reusing the pinned typed client `SshFileBusClient`
from `coordination.ssh_rpc`.

Key Architectural & Security Guarantees:
1. Pinned Typed Client Reuse:
   - Delegates transport, command construction, and validation to `SshFileBusClient`.
   - Inherits strict `request_id` correlation, strict `bool(ok)` verification, and decoupled exception chaining.
   - Eliminates redundant raw subprocess and fragile regex redaction.
2. Zero Secrets and Zero Payloads on sys.argv:
   - Credentials (bearer tokens) and message bodies are NEVER accepted via command-line arguments.
   - Input is read strictly via standard input (`sys.stdin`), matching Desktop Root's verified DPAPI PowerShell integration pattern.
   - Interactive TTY input without stdin redirection fails closed immediately.
3. Built-in Unicode Verification Probe:
   - If no explicit body is provided via stdin JSON for `send` or `reply`, the driver defaults
     to a built-in multi-byte Unicode verification string (umlauts, emojis, Cyrillic, math symbols).
4. Sanitized Output Only (Zero Leakage):
   - Raw tokens and private inbox message bodies are NEVER printed to stdout.
   - Inboxes and message lookups emit structured metadata, message counts, and SHA256 body digests.
5. Removal of `enroll`:
   - Enrolling identities is prohibited in this diagnostic driver; agents are pre-enrolled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

# Standard non-secret Unicode probe payload verifying multi-byte UTF-8 wire integrity
DEFAULT_UNICODE_PROBE_BODY = (
    "RPC-Unicode-Diagnostic: Grüß Gott 🚀 / Привет мир / 2H₂ + O₂ ⇌ 2H₂O / 100% 🎯"
)


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


def sanitize_message_summary(msg: dict[str, Any]) -> dict[str, Any]:
    """
    Sanitizes message dictionary by removing raw message bodies and sensitive fields,
    replacing them with character counts, byte counts, and SHA256 body digest.
    """
    body_str = str(msg.get("body") or "")
    body_bytes = body_str.encode("utf-8")
    return {
        "message_id": msg.get("message_id"),
        "sender_id": msg.get("sender_id"),
        "recipient_id": msg.get("recipient_id"),
        "created_at": msg.get("created_at"),
        "read": bool(msg.get("read")),
        "reply_to": msg.get("reply_to"),
        "idempotency_key": msg.get("idempotency_key"),
        "body_length_chars": len(body_str),
        "body_length_bytes": len(body_bytes),
        "body_sha256": hashlib.sha256(body_bytes).hexdigest(),
        "has_data": bool(msg.get("data")),
    }


def read_input_from_stdin() -> tuple[str, dict[str, Any]]:
    """
    Reads credential token and optional payload strictly from sys.stdin.
    Returns: (token, parsed_metadata_dict).

    Supported input forms:
    1. Plain text token (trimmed string).
    2. JSON object containing:
       - "token" (required)
       - "identity_id" / "sender_id" (optional)
       - "recipient_id" / "to" (optional)
       - "message_id" (optional)
       - "body" (optional; if omitted for send/reply, default Unicode probe is used)
       - "data" (optional dict)
       - "idempotency_key" (optional)
    """
    if sys.stdin.isatty():
        raise ValueError(
            "Authentication token and optional payload must be piped via stdin (matching Desktop Root DPAPI pattern); "
            "interactive TTY input without stdin pipe is prohibited."
        )

    raw_input = sys.stdin.read().strip()
    if not raw_input:
        raise ValueError("Stdin was empty; expected bearer token or credential JSON")

    meta: dict[str, Any] = {}
    try:
        data = json.loads(raw_input)
        if isinstance(data, dict):
            token = data.get("token")
            if not token:
                raise ValueError("JSON credential on stdin must contain a 'token' field")
            meta = data
            return str(token).strip(), meta
    except json.JSONDecodeError:
        pass

    # Treat raw input as plain token string
    return raw_input, meta


def resolve_and_import_client(repo_dir: str | None = None) -> type[Any]:
    """
    Discovers the agent-bus repository directory and imports SshFileBusClient
    from coordination.ssh_rpc.
    """
    candidate_dirs: list[Path] = []
    if repo_dir:
        candidate_dirs.append(Path(repo_dir).resolve())

    cwd = Path.cwd().resolve()
    candidate_dirs.extend([
        cwd,
        cwd / "agent-bus",
        cwd / ".local" / "scratch" / "architect06-bus-integration" / "agent-bus",
        cwd / ".local" / "scratch" / "bus-ssh-rpc-snapshot" / "agent-bus",
        cwd / ".local" / "scratch" / "disposable-recovery-test" / "agent-bus",
    ])

    for d in candidate_dirs:
        if (d / "coordination" / "ssh_rpc.py").is_file():
            if str(d) not in sys.path:
                sys.path.insert(0, str(d))
            break

    try:
        from coordination.ssh_rpc import SshFileBusClient
        return SshFileBusClient
    except ImportError as exc:
        raise ImportError(
            f"Could not import SshFileBusClient from coordination.ssh_rpc. "
            f"Specify agent-bus location via --repo-dir. (Searched: {[str(p) for p in candidate_dirs]}): {exc}"
        ) from None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Windows RPC Diagnostic Driver: executes remote FileBus RPC via typed SshFileBusClient."
    )
    parser.add_argument("--host", default="hetzner", help="Remote SSH host destination (default: hetzner)")
    parser.add_argument(
        "--remote-cli",
        default="coordination/bus_cli.py",
        help="Path to bus_cli.py on remote host (default: coordination/bus_cli.py)",
    )
    parser.add_argument("--store", required=True, help="Absolute path to FileBus store on remote host")
    parser.add_argument("--ssh-binary", default="ssh", help="SSH binary path (default: ssh, or ssh.exe on Windows)")
    parser.add_argument(
        "--action",
        required=True,
        choices=["inbox", "send", "ack", "reply", "get"],
        help="RPC operation to perform (enroll is prohibited)",
    )
    parser.add_argument("--repo-dir", help="Optional local agent-bus repo directory to append to sys.path")

    # Action parameters (no body or credentials on argv)
    parser.add_argument("--identity-id", help="Identity ID for inbox/ack/send (can also be supplied via stdin JSON)")
    parser.add_argument("--to", dest="recipient_id", help="Recipient ID for send (can also be supplied via stdin JSON)")
    parser.add_argument("--message-id", help="Message ID for ack/reply/get (can also be supplied via stdin JSON)")
    parser.add_argument("--idempotency-key", help="Idempotency key for send/reply (can also be supplied via stdin JSON)")
    parser.add_argument("--all", dest="include_read", action="store_true", help="Include read messages in inbox")
    parser.add_argument("--timeout", type=float, default=30.0, help="Command timeout in seconds")

    args = parser.parse_args()

    # Read credential token and metadata strictly from stdin
    try:
        token, meta = read_input_from_stdin()
    except Exception as exc:
        err_output = {
            "ok": False,
            "action": args.action,
            "error": {"code": "credential_error", "message": sanitize_text(str(exc))},
        }
        print(json.dumps(err_output, indent=2))
        return 1

    ident_id = args.identity_id or meta.get("identity_id") or meta.get("sender_id")
    recipient_id = args.recipient_id or meta.get("recipient_id") or meta.get("to")
    message_id = args.message_id or meta.get("message_id")
    idempotency_key = args.idempotency_key or meta.get("idempotency_key")
    data_payload = meta.get("data")

    # Body resolution for send/reply: strictly from stdin JSON, or default Unicode probe
    stdin_body = meta.get("body")
    if stdin_body is not None:
        body_to_use = str(stdin_body)
        is_unicode_probe = False
    else:
        body_to_use = DEFAULT_UNICODE_PROBE_BODY
        is_unicode_probe = True

    try:
        client_cls = resolve_and_import_client(args.repo_dir)
        client = client_cls(
            host=args.host,
            store_path=args.store,
            bus_cli_path=args.remote_cli,
            ssh_binary=args.ssh_binary,
            timeout_sec=args.timeout,
        )

        if args.action == "inbox":
            if not ident_id:
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": {
                                "code": "validation_error",
                                "message": "inbox requires identity ID (via --identity-id or stdin JSON)",
                            },
                        },
                        indent=2,
                    )
                )
                return 1

            raw_messages = client.inbox(
                identity_id=ident_id,
                token=token,
                unread_only=not args.include_read,
            )
            sanitized = [sanitize_message_summary(m) for m in raw_messages]
            out = {
                "ok": True,
                "action": "inbox",
                "identity_id": ident_id,
                "unread_only": not args.include_read,
                "message_count": len(sanitized),
                "messages": sanitized,
            }
            print(json.dumps(out, indent=2, ensure_ascii=False))
            return 0

        elif args.action == "send":
            if not ident_id:
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": {
                                "code": "validation_error",
                                "message": "send requires sender ID (via --identity-id or stdin JSON)",
                            },
                        },
                        indent=2,
                    )
                )
                return 1
            if not recipient_id:
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": {
                                "code": "validation_error",
                                "message": "send requires recipient ID (via --to or stdin JSON)",
                            },
                        },
                        indent=2,
                    )
                )
                return 1

            msg_id = client.send(
                sender_id=ident_id,
                token=token,
                recipient_id=recipient_id,
                body=body_to_use,
                data=data_payload,
                idempotency_key=idempotency_key,
            )
            body_bytes = body_to_use.encode("utf-8")
            out = {
                "ok": True,
                "action": "send",
                "message_id": msg_id,
                "sender_id": ident_id,
                "recipient_id": recipient_id,
                "body_length_chars": len(body_to_use),
                "body_length_bytes": len(body_bytes),
                "body_sha256": hashlib.sha256(body_bytes).hexdigest(),
                "is_default_unicode_probe": is_unicode_probe,
            }
            print(json.dumps(out, indent=2, ensure_ascii=False))
            return 0

        elif args.action == "reply":
            if not ident_id:
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": {
                                "code": "validation_error",
                                "message": "reply requires sender ID (via --identity-id or stdin JSON)",
                            },
                        },
                        indent=2,
                    )
                )
                return 1
            if not message_id:
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": {
                                "code": "validation_error",
                                "message": "reply requires message ID (via --message-id or stdin JSON)",
                            },
                        },
                        indent=2,
                    )
                )
                return 1

            reply_id = client.reply(
                sender_id=ident_id,
                token=token,
                message_id=message_id,
                body=body_to_use,
                data=data_payload,
                idempotency_key=idempotency_key,
            )
            body_bytes = body_to_use.encode("utf-8")
            out = {
                "ok": True,
                "action": "reply",
                "reply_message_id": reply_id,
                "reply_to": message_id,
                "sender_id": ident_id,
                "body_length_chars": len(body_to_use),
                "body_length_bytes": len(body_bytes),
                "body_sha256": hashlib.sha256(body_bytes).hexdigest(),
                "is_default_unicode_probe": is_unicode_probe,
            }
            print(json.dumps(out, indent=2, ensure_ascii=False))
            return 0

        elif args.action == "ack":
            if not ident_id:
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": {
                                "code": "validation_error",
                                "message": "ack requires identity ID (via --identity-id or stdin JSON)",
                            },
                        },
                        indent=2,
                    )
                )
                return 1
            if not message_id:
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": {
                                "code": "validation_error",
                                "message": "ack requires message ID (via --message-id or stdin JSON)",
                            },
                        },
                        indent=2,
                    )
                )
                return 1

            ack_result = client.ack(
                identity_id=ident_id,
                token=token,
                message_id=message_id,
            )
            out = {
                "ok": True,
                "action": "ack",
                "message_id": message_id,
                "identity_id": ident_id,
                "status": "acknowledged",
                "message_summary": sanitize_message_summary(ack_result),
            }
            print(json.dumps(out, indent=2, ensure_ascii=False))
            return 0

        elif args.action == "get":
            if not ident_id:
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": {
                                "code": "validation_error",
                                "message": "get requires identity ID (via --identity-id or stdin JSON)",
                            },
                        },
                        indent=2,
                    )
                )
                return 1
            if not message_id:
                print(
                    json.dumps(
                        {
                            "ok": False,
                            "error": {
                                "code": "validation_error",
                                "message": "get requires message ID (via --message-id or stdin JSON)",
                            },
                        },
                        indent=2,
                    )
                )
                return 1

            msg = client.get(
                identity_id=ident_id,
                token=token,
                message_id=message_id,
            )
            out = {
                "ok": True,
                "action": "get",
                "message": sanitize_message_summary(msg),
            }
            print(json.dumps(out, indent=2, ensure_ascii=False))
            return 0

        else:
            print(
                json.dumps(
                    {
                        "ok": False,
                        "error": {
                            "code": "invalid_action",
                            "message": f"Action '{args.action}' is not supported",
                        },
                    },
                    indent=2,
                )
            )
            return 1

    except Exception as exc:
        err_code = exc.__class__.__name__
        err_msg = sanitize_text(str(exc))
        out = {
            "ok": False,
            "action": getattr(args, "action", "unknown"),
            "error": {
                "code": err_code,
                "message": err_msg,
            },
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Genuinely bound desktop mailbox worker; SSH transports requests, not identities.

Supervised existing startup requirement: This worker must run under an existing process
supervisor/watchdog rather than suppressing or swallowing SIGHUP signals. Lifecycle management
is delegated to the supervising environment.
"""
import json
import os
import pathlib
import subprocess
import time

root = pathlib.Path(__file__).resolve().parent.parent
local = root / '.local'
patched = str(root.parent / 'cloudflare-aplexer-protocol' / 'target' / 'debug' / 'aplexer')

ALLOWED_TOKEN_CHARS = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_')


def call(args, binary='aplexer'):
    return subprocess.run([binary, *args], capture_output=True, text=True, timeout=30, check=True)


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(obj, indent=2))
    temp.replace(path)


def is_atomic_partial(name: str) -> bool:
    return name.startswith('.') or name.endswith('.tmp') or '.tmp.' in name


def validate_request(raw_bytes: bytes) -> tuple:
    try:
        text = raw_bytes.decode('utf-8')
        req = json.loads(text)
    except Exception as exc:
        return False, f"malformed_json:{type(exc).__name__}", None

    if not isinstance(req, dict):
        return False, "not_a_json_object", None

    # Detect receipt-shaped files dropped in outbox
    if "receipts" in req or "receipt" in req:
        return False, "receipt_shaped", None

    # Token validation against allowlist
    if "token" not in req:
        return False, "missing_token", None
    token = req["token"]
    if not isinstance(token, str):
        return False, "invalid_token_type", None
    if not token:
        return False, "empty_token", None
    if any(c not in ALLOWED_TOKEN_CHARS for c in token):
        return False, "invalid_token_characters", None

    # Op validation: send or reply
    op = req.get("op", "send")
    if not isinstance(op, str) or op not in ("send", "reply"):
        return False, "invalid_op", None

    # Required recipients or reply_to
    if op == "send":
        if "recipients" not in req:
            return False, "missing_recipients", None
        recipients = req["recipients"]
        if not isinstance(recipients, list) or len(recipients) == 0:
            return False, "invalid_or_empty_recipients", None
        if not all(isinstance(r, str) and len(r) > 0 for r in recipients):
            return False, "invalid_recipient_item", None
    else:  # op == "reply"
        if "reply_to" not in req:
            return False, "missing_reply_to", None
        reply_to = req["reply_to"]
        if not isinstance(reply_to, str) or len(reply_to) == 0:
            return False, "invalid_reply_to", None

    # Body shape validation
    if "body" not in req:
        return False, "missing_body", None
    body = req["body"]
    if not isinstance(body, str):
        return False, "invalid_body_type", None

    # Idempotency key type check if present
    if "idempotency_key" in req:
        if not isinstance(req["idempotency_key"], str):
            return False, "invalid_idempotency_key_type", None

    return True, "", req


def quarantine_file(local_dir: pathlib.Path, request_file: pathlib.Path, reason: str, raw_bytes: bytes = None) -> pathlib.Path:
    quarantine_dir = local_dir / 'audit' / 'orchestrator-quarantine'
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(quarantine_dir, 0o700)

    target_file = quarantine_dir / request_file.name
    if raw_bytes is not None:
        target_file.write_bytes(raw_bytes)
        try:
            request_file.unlink(missing_ok=True)
        except Exception:
            pass
    else:
        try:
            request_file.replace(target_file)
        except Exception:
            data = request_file.read_bytes()
            target_file.write_bytes(data)
            request_file.unlink(missing_ok=True)
    os.chmod(target_file, 0o600)

    meta_file = quarantine_dir / f"{request_file.name}.meta.json"
    meta_content = json.dumps({"file": request_file.name, "reason": reason}, indent=2)
    meta_file.write_text(meta_content)
    os.chmod(meta_file, 0o600)

    try:
        save(local_dir / 'orchestrator-channel-error.json', {
            'stage': 'quarantine',
            'file': request_file.name,
            'reason': reason
        })
    except Exception:
        pass
    return target_file


def process_inbox(local_dir: pathlib.Path, call_fn=call):
    try:
        save(local_dir / 'orchestrator-inbox.json', json.loads(call_fn(['message', 'inbox', '--json']).stdout))
    except Exception as exc:
        save(local_dir / 'orchestrator-channel-error.json', {'stage': 'inbox', 'error': type(exc).__name__})


def process_outbox(local_dir: pathlib.Path, call_fn=call, patched_bin=patched):
    outbox_dir = local_dir / 'orchestrator-outbox'
    if not outbox_dir.exists():
        return

    sent_dir = local_dir / 'orchestrator-sent'
    sent_dir.mkdir(parents=True, exist_ok=True)

    for request in sorted(outbox_dir.iterdir(), key=lambda p: p.name):
        if not request.is_file():
            continue
        if is_atomic_partial(request.name):
            continue

        try:
            raw_bytes = request.read_bytes()
        except Exception as exc:
            quarantine_file(local_dir, request, f"unreadable:{type(exc).__name__}")
            continue

        is_valid, reason, req = validate_request(raw_bytes)
        if not is_valid:
            quarantine_file(local_dir, request, reason, raw_bytes=raw_bytes)
            continue

        token = req['token']
        receipt = sent_dir / f'{token}.json'
        if receipt.exists():
            continue

        op = req.get('op', 'send')
        targets = req['recipients'] if op == 'send' else [req['reply_to']]
        replies = []
        errors = []

        for target in targets:
            part = sent_dir / f'{token}-{target}.json'
            if part.exists():
                try:
                    replies.append(json.loads(part.read_text()))
                    continue
                except Exception:
                    pass
            args = ['message', 'send', '--to', target, '--json'] if op == 'send' else ['message', 'reply', target, '--json']
            binary = 'aplexer'
            if req.get('idempotency_key'):
                binary = patched_bin
                args += ['--idempotency-key', req['idempotency_key'] + ('-' + target if op == 'send' else '')]
            try:
                res = call_fn(args + [req['body']], binary)
                item = json.loads(res.stdout)
                save(part, item)
                replies.append(item)
            except Exception as exc:
                # One stale recipient must not block all other requests or reviewed ACKs.
                errors.append({'target': target, 'error': type(exc).__name__})

        try:
            if not errors:
                save(receipt, {'token': token, 'receipts': replies})
            else:
                save(sent_dir / f'{token}-errors.json', errors)
        except Exception as exc:
            save(local_dir / 'orchestrator-channel-error.json', {'stage': 'request', 'file': request.name, 'error': type(exc).__name__})


def process_acks(local_dir: pathlib.Path, call_fn=call):
    ackfile = local_dir / 'orchestrator-ack.json'
    if ackfile.exists():
        try:
            ids = json.loads(ackfile.read_text())
            remaining = []
            for ident in ids:
                try:
                    call_fn(['message', 'ack', ident, '--json'])
                except Exception:
                    remaining.append(ident)
            # Avoid consuming an ACK file replaced concurrently by the desktop.
            if json.loads(ackfile.read_text()) == ids:
                if remaining:
                    save(ackfile, remaining)
                else:
                    ackfile.unlink()
        except Exception as exc:
            save(local_dir / 'orchestrator-channel-error.json', {'stage': 'ack', 'error': type(exc).__name__})


def run_loop(root_path: pathlib.Path = root, call_fn=call, patched_bin=patched, once=False):
    local_dir = root_path / '.local'
    identity = json.loads(call_fn(['whoami', '--json']).stdout)
    assert identity['workspace'] == str(root_path) and identity['tag'] == 'desktop-orchestrator', identity
    save(local_dir / 'orchestrator-channel-identity.json', {k: identity[k] for k in ['id', 'tag', 'workspace']})
    while not (local_dir / 'orchestrator-channel.stop').exists():
        process_inbox(local_dir, call_fn=call_fn)
        process_outbox(local_dir, call_fn=call_fn, patched_bin=patched_bin)
        process_acks(local_dir, call_fn=call_fn)
        if once:
            break
        time.sleep(5)


if __name__ == '__main__':
    os.chdir(root)
    run_loop(root, call, patched)

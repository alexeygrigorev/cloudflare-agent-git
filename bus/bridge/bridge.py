#!/usr/bin/env python3
"""aplexer bus bridge — connects one machine's local aplexer workspace to the global bus.

Outbound: JSON files dropped in --outbox-dir are POSTed to the bus, then moved to outbox/sent/.
  File format: {"to": "tag@machine" | {"machine": "x", "tag": "y"}, "kind": "note",
                "body": "...", "reply_to": null}
  The message id is a deterministic hash of filename+content, so a resend after a crash
  dedups on the bus instead of duplicating.
  --mode log alternatively watches `aplexer message log --json` for recipients written
  "tag@machine" (the stock CLI cannot produce those; future/patched senders only).

Inbound: long-polls GET /v1/messages with a persisted cursor and delivers each message to
the LOCAL workspace as `aplexer message send --to <tag> "[from tag@machine] <body>"`.
It NEVER passes --from (no impersonation) and never injects into panes. Delivery is
pluggable: --delivery file:<path> appends one JSON line per message (used by tests/demo).

Delivery-then-persist: cursor and the delivered-id set are saved atomically AFTER each
delivery, so a crash can redeliver one message, which the id dedup then absorbs.

Every message progress step is logged with a typed outcome:
  outcome=queued               accepted for the bus (outbox file or log entry), id assigned
  outcome=transported          bus stored it (2xx; duplicate=true means a resend deduped)
  outcome=received-into-inbox  a polled message provably landed in the local workspace
  outcome=acked                the cursor was persisted server-side via POST /v1/ack
  outcome=UNKNOWN              a local native send timed out — it may or may not have landed.
                               The message is NOT marked delivered, the cursor does NOT move
                               past it, and any retry reuses the SAME bus id (never a new id,
                               which would duplicate the message if the first send landed).
                               After --unknown-dead-letter uncertain attempts it is
                               dead-lettered so one wedged target cannot block the stream.

Stdlib only. Single writer per state file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.request

MAX_DELIVERED_MEMORY = 20_000


def log(msg: str) -> None:
    print(f"[bridge {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def http_json(method: str, url: str, token: str, payload=None, timeout: float = 40.0):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as err:
        body = err.read().decode(errors="replace")
        try:
            return err.code, json.loads(body)
        except ValueError:
            return err.code, {"error": body[:300]}
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        return None, {"error": f"network: {err}"}


def parse_to(value):
    """Return (machine, tag); machine None = broadcast."""
    if isinstance(value, str):
        if "@" not in value:
            raise ValueError(f"bad to {value!r}: expected tag@machine")
        tag, machine = value.rsplit("@", 1)
        if machine in ("", "*", "all"):
            machine = None
        return machine, tag
    if isinstance(value, dict):
        machine = value.get("machine") or None
        tag = value.get("tag")
        if machine is None and not tag:
            raise ValueError("bad to: broadcast needs a tag")
        return machine, tag
    raise ValueError(f"bad to {value!r}")


class Bridge:
    def __init__(self, args):
        self.args = args
        self.workspace = pathlib.Path(args.workspace).resolve()
        self.outbox = pathlib.Path(args.outbox_dir)
        self.sent_dir = self.outbox / "sent"
        self.state_file = pathlib.Path(args.state_file)
        self.state = {"cursor": 0, "delivered": {}, "unknown": {}, "acked_cursor": 0}
        self.delivery_file = None
        if args.delivery.startswith("file:"):
            self.delivery_file = pathlib.Path(args.delivery[5:])
            self.delivery_file.parent.mkdir(parents=True, exist_ok=True)
        self.stopping = False

    # ---- state ----
    def load_state(self):
        if self.state_file.exists():
            data = json.loads(self.state_file.read_text())
            self.state["cursor"] = int(data.get("cursor", 0))
            delivered = data.get("delivered", {})
            if isinstance(delivered, dict):
                items = list(delivered.items())[-MAX_DELIVERED_MEMORY:]
                self.state["delivered"] = dict(items)
            unknown = data.get("unknown", {})
            if isinstance(unknown, dict):
                self.state["unknown"] = unknown
            self.state["acked_cursor"] = int(data.get("acked_cursor", 0))
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def save_state(self):
        tmp = self.state_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=1))
        tmp.replace(self.state_file)

    # ---- outbound ----
    def message_id(self, name: str, request: dict) -> str:
        canonical = json.dumps(
            {
                "to": request.get("to"),
                "kind": request.get("kind", "note"),
                "body": request.get("body"),
                "reply_to": request.get("reply_to"),
            },
            sort_keys=True,
        )
        digest = hashlib.sha256(f"{name}\n{canonical}".encode()).hexdigest()[:40]
        return f"b-{digest}"

    def send_outbox(self) -> None:
        self.outbox.mkdir(parents=True, exist_ok=True)
        self.sent_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(self.outbox.glob("*.json")):
            if self.stopping:
                return
            try:
                request = json.loads(path.read_text())
                machine, tag = parse_to(request["to"])
                body = request["body"]
                if not isinstance(body, str) or not body:
                    raise ValueError("body must be a non-empty string")
            except (ValueError, KeyError, json.JSONDecodeError) as err:
                log(f"outbox: rejecting {path.name}: {err}")
                failed = self.outbox / "failed"
                failed.mkdir(exist_ok=True)
                path.replace(failed / path.name)
                continue
            payload = {
                "id": self.message_id(path.name, request),
                "kind": request.get("kind", "note"),
                "body": body,
                "reply_to": request.get("reply_to"),
                "to": {"machine": machine, "tag": tag},
                "from": {"tag": request.get("tag") or self.args.tag,
                         "session_id": request.get("session_id")},
            }
            log(f"outcome=queued file={path.name} id={payload['id']}")
            status, data = http_json(
                "POST", f"{self.args.bus_url}/v1/messages", self.args.token, payload
            )
            if status in (200, 201):
                receipt = {"bus_id": payload["id"], "seq": data.get("message", {}).get("seq")}
                (self.sent_dir / f"{path.name}.sent.json").write_text(json.dumps(receipt))
                path.replace(self.sent_dir / path.name)
                log(f"outcome=transported file={path.name} id={payload['id']} "
                    f"seq={receipt['seq']} duplicate={bool(data.get('duplicate'))}")
            elif status in (429, None) or status >= 500:
                log(f"outcome=queued file={path.name} retryable (HTTP {status}); "
                    f"stays queued with the SAME id {payload['id']}")
                time.sleep(1)
                return  # retry next cycle, in order
            else:
                log(f"outbox: {path.name} rejected (HTTP {status}: {data.get('error')})")
                failed = self.outbox / "failed"
                failed.mkdir(exist_ok=True)
                path.replace(failed / path.name)

    def watch_log(self) -> None:
        """Secondary mode: forward log entries addressed tag@machine (future senders)."""
        out = subprocess.run(
            ["aplexer", "message", "log", "--json"],
            cwd=self.workspace, capture_output=True, text=True, timeout=60, check=True,
        )
        for entry in json.loads(out.stdout):
            to = entry.get("to", {}).get("tag", "")
            if "@" not in to:
                continue
            if entry["id"] in self.state["delivered"]:
                continue
            machine, tag = parse_to(to)
            payload = {
                "id": f"b-log-{entry['id']}",
                "kind": entry.get("kind", "note"),
                "body": entry.get("body", ""),
                "to": {"machine": machine, "tag": tag},
                "from": {"tag": entry.get("from", {}).get("tag"),
                         "session_id": entry.get("from", {}).get("session_id")},
            }
            log(f"outcome=queued log-entry={entry['id']} id={payload['id']}")
            status, data = http_json(
                "POST", f"{self.args.bus_url}/v1/messages", self.args.token, payload
            )
            if status in (200, 201):
                self.state["delivered"][payload["id"]] = data.get("message", {}).get("seq")
                self.save_state()
                log(f"outcome=transported log-entry={entry['id']} id={payload['id']} "
                    f"seq={data.get('message', {}).get('seq')}")

    # ---- inbound ----
    def deliver(self, message: dict) -> tuple[str, str]:
        """Deliver one polled message into the local workspace.

        Returns (status, detail) with status:
          "ok"      — provably landed (or the hermetic file sink accepted it)
          "unknown" — a native send timed out (or a file append failed mid-write):
                      it may or may not be in the inbox, so the caller must not
                      mark it delivered, must not move the cursor past it, and
                      must never retry it under a new id — only the SAME bus id.
          "error"   — known failure; the caller may dead-letter it.
        """
        origin = f"{message['from'].get('tag') or 'unknown-tag'}@{message['from'].get('machine')}"
        body = f"[from {origin}] {message['body']}"
        tag = message.get("to", {}).get("tag")
        if self.delivery_file is not None:
            line = json.dumps(
                {"bus_id": message["id"], "seq": message["seq"], "tag": tag,
                 "origin": origin, "body": body}
            )
            try:
                with self.delivery_file.open("a") as handle:
                    handle.write(line + "\n")
            except OSError as err:
                return "unknown", f"file append uncertain: {err}"
            return "ok", ""
        if not tag:
            return "error", "broadcast message has no local tag to deliver to"
        # The one and only delivery path: an ordinary local send. Never --from.
        argv = ["aplexer", "message", "send", "--to", tag, body]
        assert "--from" not in argv
        try:
            proc = subprocess.run(
                argv, cwd=self.workspace, capture_output=True, text=True,
                timeout=self.args.send_timeout,
            )
        except subprocess.TimeoutExpired:
            return "unknown", f"native send timed out after {self.args.send_timeout}s"
        if proc.returncode != 0:
            return "error", f"aplexer send failed: {(proc.stderr or proc.stdout).strip()[:200]}"
        return "ok", ""

    def ack_cursor(self) -> None:
        """Persist the cursor server-side (observability / future log trimming)."""
        cursor = self.state["cursor"]
        if cursor <= self.state.get("acked_cursor", 0):
            return
        status, _ = http_json(
            "POST", f"{self.args.bus_url}/v1/ack", self.args.token, {"cursor": cursor}, timeout=10
        )
        if status == 200:
            self.state["acked_cursor"] = cursor
            self.save_state()
            log(f"outcome=acked cursor={cursor}")
        else:
            log(f"ack deferred (HTTP {status}); local cursor {cursor} stays authoritative")

    def poll_once(self) -> bool:
        wait = self.args.long_poll
        url = f"{self.args.bus_url}/v1/messages?after={self.state['cursor']}&wait={wait}"
        status, data = http_json("GET", url, self.args.token, timeout=wait + 15)
        if status == 401:
            log("FATAL: bus rejected the token (401); fix --token/--machine")
            sys.exit(2)
        if status != 200:
            log(f"poll failed (HTTP {status}: {data.get('error', 'network')}); backing off")
            return False
        for message in data.get("messages", []):
            mid = message["id"]
            if mid in self.state["delivered"]:
                continue
            outcome, detail = self.deliver(message)
            if outcome == "ok":
                self.state["delivered"][mid] = message["seq"]
                self.state["cursor"] = max(self.state["cursor"], int(message["seq"]))
                self.save_state()
                log(f"outcome=received-into-inbox id={mid} seq={message['seq']} "
                    f"tag={message.get('to', {}).get('tag')}")
            elif outcome == "unknown":
                # Uncertain send: leave the message undelivered so the next poll
                # redelivers it under the SAME bus id. Never mint a new id here —
                # if the first send actually landed, a new id would double-deliver.
                attempts = self.state["unknown"].get(mid, 0) + 1
                self.state["unknown"][mid] = attempts
                self.save_state()
                log(f"outcome=UNKNOWN id={mid} attempt={attempts} ({detail}); "
                    f"not marked delivered, retry keeps the SAME id")
                if attempts >= self.args.unknown_dead_letter:
                    reason = f"uncertain delivery {attempts}x: {detail}"
                    self.state["delivered"][mid] = f"dead:{reason[:180]}"
                    self.state["unknown"].pop(mid, None)
                    self.state["cursor"] = max(self.state["cursor"], int(message["seq"]))
                    self.save_state()
                    log(f"dead-letter {mid}: {reason}")
                    continue
                return True  # stop the cycle; nothing later may leapfrog an uncertain message
            else:
                self.state["delivered"][mid] = f"dead:{detail[:180]}"
                self.state["cursor"] = max(self.state["cursor"], int(message["seq"]))
                self.save_state()
                log(f"dead-letter {mid}: {detail}")
        # The bus-side cursor is only adopted when every message this cycle resolved.
        self.state["cursor"] = max(self.state["cursor"], int(data.get("cursor", 0)))
        self.save_state()
        self.ack_cursor()
        return True

    def run(self) -> None:
        self.load_state()
        if self.args.mode == "log":
            self.watch_log()
            return
        cycles = 0
        while not self.stopping:
            self.send_outbox()
            self.poll_once()
            cycles += 1
            if self.args.max_cycles and cycles >= self.args.max_cycles:
                log(f"max-cycles {self.args.max_cycles} reached; exiting")
                return
            if not self.args.max_cycles:
                time.sleep(self.args.poll_interval)

    def stop(self, *_):
        self.stopping = True


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bus-url", default=os.environ.get("BUS_URL", "http://127.0.0.1:8787"))
    parser.add_argument("--machine", required=True, help="this machine's id (must match the token)")
    parser.add_argument("--token", default=os.environ.get("BUS_TOKEN"), help="machine bearer token")
    parser.add_argument("--tag", default=os.environ.get("APLEXER_TAG", "bus-bridge"),
                        help="display sender tag put on outbound messages")
    parser.add_argument("--workspace", default=os.getcwd(), help="workspace for aplexer delivery")
    parser.add_argument("--outbox-dir", default=None)
    parser.add_argument("--state-file", default=None)
    parser.add_argument("--delivery", default="aplexer",
                        help="'aplexer' (default) or 'file:<path>' for hermetic runs")
    parser.add_argument("--mode", choices=["outbox", "log"], default="outbox")
    parser.add_argument("--poll-interval", type=float, default=3.0)
    parser.add_argument("--long-poll", type=float, default=25.0)
    parser.add_argument("--send-timeout", type=float, default=60.0,
                        help="seconds before a local native send is declared outcome=UNKNOWN")
    parser.add_argument("--unknown-dead-letter", type=int, default=5,
                        help="uncertain attempts for one message before it is dead-lettered")
    parser.add_argument("--max-cycles", type=int, default=0, help="0 = run until stopped")
    args = parser.parse_args(argv)
    if not args.token:
        parser.error("--token or BUS_TOKEN is required")
    root = pathlib.Path(args.workspace)
    args.outbox_dir = args.outbox_dir or str(root / ".local" / "bus-outbox")
    args.state_file = args.state_file or str(root / ".local" / "bus-bridge" / f"state-{args.machine}.json")
    return args


def main():
    args = parse_args()
    bridge = Bridge(args)
    import signal
    signal.signal(signal.SIGTERM, bridge.stop)
    signal.signal(signal.SIGINT, bridge.stop)
    bridge.run()


if __name__ == "__main__":
    main()

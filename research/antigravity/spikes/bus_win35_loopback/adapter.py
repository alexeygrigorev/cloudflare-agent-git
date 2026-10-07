#!/usr/bin/env python3
"""HTTP Loopback Transport Adapter for Agent Bus (Directive C3087 / bus-win35-nonssh-loopback-spike-01).

Provides a lightweight, loopback-bound HTTP REST interface wrapping the existing single-host
FileBus store in /home/alexey/git/agent-bus without modifying agent-bus sources.
Enables outbound-only GitBash curl clients on Windows 35 to communicate across hosts.

Endpoints:
- POST /v1/register: enrolls an agent with device_id, agent_name, project_id
- POST /v1/send: sends message envelope with idempotency key
- GET /v1/inbox: retrieves unread/all messages for authenticated identity
- POST /v1/ack: marks message read-acknowledged (acked_at)
- POST /v1/accept: marks message semantically accepted (accepted_at)
- POST /v1/complete: marks message action-completed (outcome_at, digest)
- POST /v1/reply: sends correlated reply message
- GET /v1/status: service health and store metadata
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pathlib
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

# Resolve agent-bus library path without modifying agent-bus source tree
AGENT_BUS_ROOT = pathlib.Path("/home/alexey/git/agent-bus")
if str(AGENT_BUS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_BUS_ROOT))

try:
    from coordination.bus import BusError, FileBus
    from coordination.errors import CoordinationError, IdempotencyConflict
except ImportError as err:
    raise RuntimeError(f"Failed to import FileBus from {AGENT_BUS_ROOT}: {err}") from err

logger = logging.getLogger("bus_loopback_adapter")


class BusAdapterHandler(BaseHTTPRequestHandler):
    """HTTP request handler dispatching REST calls to FileBus."""

    server_version = "AgentBusLoopbackAdapter/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        # Suppress noisy default stderr logging during automated testing
        logger.debug("%s - - [%s] %s", self.address_string(), self.log_date_time_string(), format % args)

    @property
    def bus(self) -> FileBus:
        return self.server.bus  # type: ignore[attr-defined]

    def _send_json(self, status_code: int, data: dict[str, Any]) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len <= 0:
            return {}
        if content_len > 10 * 1024 * 1024:  # 10 MB payload limit
            raise ValueError("Payload size exceeds maximum allowed limit (10MB)")
        raw = self.rfile.read(content_len).decode("utf-8")
        return json.loads(raw)

    def _handle_bus_error(self, err: Exception) -> None:
        if isinstance(err, IdempotencyConflict):
            self._send_json(HTTPStatus.CONFLICT, {
                "status": "error",
                "code": "idempotency_conflict",
                "detail": str(err),
            })
            return

        code = getattr(err, "code", "bus_error")
        detail = getattr(err, "detail", str(err))
        status_map = {
            "auth_failed": HTTPStatus.UNAUTHORIZED,
            "not_recipient": HTTPStatus.FORBIDDEN,
            "project_scope": HTTPStatus.FORBIDDEN,
            "cross_project": HTTPStatus.FORBIDDEN,
            "unknown_message": HTTPStatus.NOT_FOUND,
            "unknown_identity": HTTPStatus.NOT_FOUND,
            "unknown_recipient": HTTPStatus.NOT_FOUND,
            "unknown_sender": HTTPStatus.NOT_FOUND,
            "idempotency_conflict": HTTPStatus.CONFLICT,
            "outcome_conflict": HTTPStatus.CONFLICT,
        }
        status_code = status_map.get(code, HTTPStatus.BAD_REQUEST)
        self._send_json(status_code, {"status": "error", "code": code, "detail": detail})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        query = parse_qs(parsed.query)

        if path == "/v1/status":
            self._send_json(HTTPStatus.OK, {
                "status": "ok",
                "store_path": str(self.bus.root),
                "device_scope": "win35-nonssh-loopback",
                "transport": "http-loopback",
            })
            return

        if path == "/v1/inbox":
            identity_id = query.get("identity_id", [None])[0]
            token = query.get("token", [None])[0]
            unread_str = query.get("unread_only", ["true"])[0].lower()
            unread_only = unread_str in ("true", "1", "yes")

            if not identity_id or not token:
                self._send_json(HTTPStatus.BAD_REQUEST, {
                    "status": "error",
                    "code": "missing_credentials",
                    "detail": "identity_id and token query parameters are required"
                })
                return

            try:
                messages = self.bus.inbox(identity_id=identity_id, token=token, unread_only=unread_only)
                def _fmt_msg(m):
                    d = m.to_public()
                    d["id"] = m.message_id
                    return d

                self._send_json(HTTPStatus.OK, {
                    "status": "ok",
                    "identity_id": identity_id,
                    "count": len(messages),
                    "messages": [_fmt_msg(m) for m in messages],
                })
            except (BusError, CoordinationError) as err:
                self._handle_bus_error(err)
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {
                    "status": "error",
                    "code": "internal_error",
                    "detail": str(exc),
                })
            return

        self._send_json(HTTPStatus.NOT_FOUND, {
            "status": "error",
            "code": "not_found",
            "detail": f"Path not found: {self.path}"
        })

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")

        try:
            payload = self._read_json()
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {
                "status": "error",
                "code": "malformed_json",
                "detail": str(exc),
            })
            return

        try:
            if path == "/v1/register":
                agent_name = payload.get("agent_name")
                device_id = payload.get("device_id")
                project_id = payload.get("project_id", "agent-bus")
                if not agent_name or not device_id:
                    self._send_json(HTTPStatus.BAD_REQUEST, {
                        "status": "error",
                        "code": "missing_fields",
                        "detail": "agent_name and device_id are required",
                    })
                    return
                ident, token = self.bus.register(
                    agent_name=agent_name,
                    device_id=device_id,
                    project_id=project_id,
                )
                ident_data = ident.public()
                ident_data["id"] = ident.identity_id
                self._send_json(HTTPStatus.CREATED, {
                    "status": "ok",
                    "identity": ident_data,
                    "token": token,
                })
                return

            if path == "/v1/send":
                sender_id = payload.get("sender_id")
                token = payload.get("token")
                recipient_id = payload.get("recipient_id")
                body = payload.get("body")
                kind = payload.get("kind", "note")
                idempotency_key = payload.get("idempotency_key")
                data = payload.get("data")
                reply_to = payload.get("reply_to")

                if not sender_id or not token or not recipient_id or body is None:
                    self._send_json(HTTPStatus.BAD_REQUEST, {
                        "status": "error",
                        "code": "missing_fields",
                        "detail": "sender_id, token, recipient_id, and body are required",
                    })
                    return

                msg = self.bus.send(
                    sender_id=sender_id,
                    token=token,
                    recipient_id=recipient_id,
                    body=body,
                    kind=kind,
                    idempotency_key=idempotency_key,
                    data=data,
                    reply_to=reply_to,
                )
                msg_data = msg.to_public()
                msg_data["id"] = msg.message_id
                self._send_json(HTTPStatus.OK, {
                    "status": "ok",
                    "message": msg_data,
                })
                return

            if path == "/v1/ack":
                identity_id = payload.get("identity_id")
                token = payload.get("token")
                message_id = payload.get("message_id")
                if not identity_id or not token or not message_id:
                    self._send_json(HTTPStatus.BAD_REQUEST, {
                        "status": "error",
                        "code": "missing_fields",
                        "detail": "identity_id, token, and message_id are required",
                    })
                    return
                msg = self.bus.ack(identity_id=identity_id, token=token, message_id=message_id)
                msg_data = msg.to_public()
                msg_data["id"] = msg.message_id
                self._send_json(HTTPStatus.OK, {
                    "status": "ok",
                    "message": msg_data,
                })
                return

            if path == "/v1/accept":
                identity_id = payload.get("identity_id")
                token = payload.get("token")
                message_id = payload.get("message_id")
                if not identity_id or not token or not message_id:
                    self._send_json(HTTPStatus.BAD_REQUEST, {
                        "status": "error",
                        "code": "missing_fields",
                        "detail": "identity_id, token, and message_id are required",
                    })
                    return
                msg = self.bus.accept(identity_id=identity_id, token=token, message_id=message_id)
                msg_data = msg.to_public()
                msg_data["id"] = msg.message_id
                self._send_json(HTTPStatus.OK, {
                    "status": "ok",
                    "message": msg_data,
                })
                return

            if path == "/v1/complete":
                identity_id = payload.get("identity_id")
                token = payload.get("token")
                message_id = payload.get("message_id")
                status = payload.get("status", "completed")
                artifact = payload.get("artifact")
                digest = payload.get("digest")
                extra = payload.get("extra")

                if not identity_id or not token or not message_id:
                    self._send_json(HTTPStatus.BAD_REQUEST, {
                        "status": "error",
                        "code": "missing_fields",
                        "detail": "identity_id, token, and message_id are required",
                    })
                    return
                msg = self.bus.complete(
                    identity_id=identity_id,
                    token=token,
                    message_id=message_id,
                    status=status,
                    artifact=artifact,
                    digest=digest,
                    extra=extra,
                )
                msg_data = msg.to_public()
                msg_data["id"] = msg.message_id
                self._send_json(HTTPStatus.OK, {
                    "status": "ok",
                    "message": msg_data,
                })
                return

            if path == "/v1/reply":
                sender_id = payload.get("sender_id")
                token = payload.get("token")
                message_id = payload.get("message_id")
                body = payload.get("body")
                data = payload.get("data")
                idempotency_key = payload.get("idempotency_key")

                if not sender_id or not token or not message_id or body is None:
                    self._send_json(HTTPStatus.BAD_REQUEST, {
                        "status": "error",
                        "code": "missing_fields",
                        "detail": "sender_id, token, message_id, and body are required",
                    })
                    return
                msg = self.bus.reply(
                    sender_id=sender_id,
                    token=token,
                    message_id=message_id,
                    body=body,
                    data=data,
                    idempotency_key=idempotency_key,
                )
                msg_data = msg.to_public()
                msg_data["id"] = msg.message_id
                self._send_json(HTTPStatus.OK, {
                    "status": "ok",
                    "message": msg_data,
                })
                return

            self._send_json(HTTPStatus.NOT_FOUND, {
                "status": "error",
                "code": "not_found",
                "detail": f"Path not found: {self.path}"
            })
        except (BusError, CoordinationError) as err:
            self._handle_bus_error(err)
        except Exception as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {
                "status": "error",
                "code": "internal_error",
                "detail": str(exc),
            })


class BusLoopbackServer(HTTPServer):
    """HTTPServer holding a shared FileBus instance."""

    def __init__(self, server_address: tuple[str, int], bus: FileBus):
        super().__init__(server_address, BusAdapterHandler)
        self.bus = bus


def create_server(host: str, port: int, store_dir: pathlib.Path) -> BusLoopbackServer:
    bus = FileBus(store_dir)
    return BusLoopbackServer((host, port), bus)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agent Bus HTTP Loopback Adapter")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8788, help="Port to listen on (default: 8788)")
    parser.add_argument("--store", type=pathlib.Path, required=True, help="Path to FileBus store directory")
    args = parser.parse_args(argv)

    server = create_server(args.host, args.port, args.store)
    logger.info("Starting Agent Bus Loopback Adapter on %s:%d using store %s", args.host, args.port, args.store)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down adapter...")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    sys.exit(main())

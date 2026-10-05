#!/usr/bin/env python3
"""
Stdlib-Only Windows Client & Unicode RPC Diagnostic Test.
Under Codex Principal Directive C2263.

Validates:
1. Pure Windows Client import viability without POSIX `fcntl` module.
2. UTF-8 Unicode payload encoding/decoding and clean JSON framing across non-ASCII scripts
   (Cyrillic, German umlauts, CJK characters, emojis, and mathematical symbols).
3. Stdin JSON streaming RPC mechanics matching Desktop Root's verified DPAPI pattern
   (zero secrets or payload bodies on `sys.argv`).
4. `SshFileBusClient` argument construction and mock invocation on non-POSIX platforms.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

# Ensure target integration repository is in sys.path
REPO_DIR = Path("/home/alexey/git/cloudflare-agent-git/.local/scratch/architect06-bus-integration/agent-bus")
if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))


class TestWindowsClientAndUnicodeRpc(unittest.TestCase):
    """Diagnostic suite verifying Windows client compatibility and Unicode RPC streaming."""

    def setUp(self) -> None:
        # Simulate platform without fcntl (such as native Windows)
        self._orig_fcntl = sys.modules.get("fcntl")
        sys.modules["fcntl"] = None

    def tearDown(self) -> None:
        if self._orig_fcntl is not None:
            sys.modules["fcntl"] = self._orig_fcntl
        else:
            sys.modules.pop("fcntl", None)

    def test_01_client_import_without_fcntl(self) -> None:
        """Confirms that coordination modules and SshFileBusClient import without fcntl."""
        try:
            import coordination.envelope
            import coordination.errors
            import coordination.ssh_rpc
            from coordination.ssh_rpc import SshFileBusClient
        except ModuleNotFoundError as exc:
            self.fail(f"Failed to import SshFileBusClient without fcntl: {exc}")

        self.assertIsNotNone(SshFileBusClient)

    def test_02_unicode_payload_framing(self) -> None:
        """Verifies full fidelity UTF-8 serialization/deserialization for non-ASCII payloads."""
        from coordination.envelope import RpcRequest, RpcResponse, new_request_id

        unicode_samples = {
            "cyrillic": "Тестовое сообщение через RPC: проверка UTF-8 и целостности данных",
            "german": "Grüße aus Berlin: Überprüfung von Umlauten äöüß und Sonderzeichen",
            "japanese": "こんにちは世界！FileBus RPC cross-computer message",
            "emojis": "🚀 Windows Desktop ➔ Hetzner Linux Rendezvous 🌐✨",
            "math": "∀x ∈ Agents: Verified(x) ∧ Latency(x) < 1000ms",
        }

        req_id = new_request_id()
        req = RpcRequest(
            op="send",
            request_id=req_id,
            params={
                "sender_id": "01ace831-6d23-4c05-a6df-1a58099aca67",
                "token": "test-dpapi-decrypted-token-abc123xyz",
                "recipient_id": "91d2a63b-fe47-4b53-bee8-2ada24259439",
                "body": unicode_samples["cyrillic"],
                "data": unicode_samples,
            },
        )

        # 1. Serialize request to JSON and encode to UTF-8 bytes
        req_json = json.dumps(req.to_dict(), ensure_ascii=False)
        req_bytes = req_json.encode("utf-8")

        # 2. Decode from UTF-8 bytes and reconstruct request
        decoded_json = req_bytes.decode("utf-8")
        parsed_dict = json.loads(decoded_json)
        reconstructed_req = RpcRequest.from_dict(parsed_dict)

        self.assertEqual(reconstructed_req.request_id, req_id)
        self.assertEqual(reconstructed_req.op, "send")
        self.assertEqual(reconstructed_req.params["body"], unicode_samples["cyrillic"])
        self.assertEqual(reconstructed_req.params["data"], unicode_samples)

        # 3. Simulate RpcResponse with Unicode return payload
        resp_payload = {
            "message_id": "msg-unicode-4497403a",
            "echo": unicode_samples["emojis"],
            "status": "ACCEPTED_ПРОВЕРЕНО",
        }
        resp = RpcResponse(request_id=req_id, ok=True, result=resp_payload)
        resp_json = json.dumps(resp.to_dict(), ensure_ascii=False)
        resp_bytes = resp_json.encode("utf-8")

        reconstructed_resp = RpcResponse.from_dict(json.loads(resp_bytes.decode("utf-8")))
        self.assertTrue(reconstructed_resp.ok)
        self.assertEqual(reconstructed_resp.result["echo"], unicode_samples["emojis"])
        self.assertEqual(reconstructed_resp.result["status"], "ACCEPTED_ПРОВЕРЕНО")

    def test_03_desktop_root_dpapi_stdin_streaming_pattern(self) -> None:
        """
        Verifies that SshFileBusClient encapsulates sensitive parameters strictly in stdin JSON
        streams matching Desktop Root's verified DPAPI pattern, leaving sys.argv completely clean.
        """
        from coordination.ssh_rpc import SshFileBusClient

        captured_commands: list[list[str]] = []
        captured_stdin: list[str | None] = []

        def mock_runner(cmd: list[str], stdin_data: str | None, timeout: float) -> tuple[int, str, str]:
            captured_commands.append(cmd)
            captured_stdin.append(stdin_data)

            # Parse request from stdin
            assert stdin_data is not None
            req_dict = json.loads(stdin_data)
            req_id = req_dict["request_id"]
            op = req_dict["op"]

            if op == "enroll":
                res = {"identity_id": "01ace831-mock", "token": "secret-dpapi-token-777"}
            elif op == "send":
                res = {"message_id": "msg-unicode-888"}
            elif op == "inbox":
                res = [
                    {
                        "message_id": "msg-unicode-888",
                        "sender_id": "desktop-root",
                        "recipient_id": "hetzner-head",
                        "body": "Привет из Windows!",
                        "data": {"status": "OK"},
                    }
                ]
            else:
                res = {"acked_at": "2026-10-05T02:00:00Z"}

            response_json = json.dumps({"request_id": req_id, "ok": True, "result": res})
            return 0, response_json, ""

        client = SshFileBusClient(
            host="hetzner",
            store_path="/var/bus/rendezvous_store",
            bus_cli_path="coordination/bus_cli.py",
            ssh_binary="ssh.exe",  # Windows OpenSSH client binary
            runner=mock_runner,
        )

        secret_token = "SECRET_DPAPI_USER_BOUND_TOKEN_XYZ_999"
        secret_body = "Sensitivny Unicode Body: 🔑 Пароль / Geheime Nachricht"

        # Execute send operation
        client.send(
            sender_id="01ace831-mock",
            token=secret_token,
            recipient_id="91d2a63b-mock",
            body=secret_body,
            data={"auth": "dpapi_verified"},
        )

        self.assertEqual(len(captured_commands), 1)
        argv = captured_commands[0]
        stdin_stream = captured_stdin[0]

        # 1. Assert command line uses ssh.exe and contains zero secrets
        self.assertEqual(argv[0], "ssh.exe")
        self.assertIn("hetzner", argv)
        for arg in argv:
            self.assertNotIn(secret_token, arg, f"Secret token leaked on argv: {arg}")
            self.assertNotIn("Sensitivny", arg, f"Message body leaked on argv: {arg}")
            self.assertNotIn("Geheime", arg, f"Message body leaked on argv: {arg}")

        # 2. Assert stdin stream carries complete structured payload
        self.assertIsNotNone(stdin_stream)
        payload = json.loads(stdin_stream)
        self.assertEqual(payload["op"], "send")
        self.assertEqual(payload["params"]["token"], secret_token)
        self.assertEqual(payload["params"]["body"], secret_body)

    def test_04_windows_client_argument_construction(self) -> None:
        """
        Verifies argument construction on Windows:
        - '--' precedes host to prevent destination injection.
        - Mandatory -o BatchMode=yes and -o StrictHostKeyChecking=yes are present.
        - Remote paths are escaped for the remote POSIX shell via shlex.quote.
        """
        from coordination.ssh_rpc import SshFileBusClient

        captured_cmd: list[str] = []

        def mock_runner(cmd: list[str], stdin_data: str | None, timeout: float) -> tuple[int, str, str]:
            captured_cmd.extend(cmd)
            req_id = json.loads(stdin_data)["request_id"]
            return 0, json.dumps({"request_id": req_id, "ok": True, "result": []}), ""

        client = SshFileBusClient(
            host="135.181.114.209",
            store_path="/home/alexey/remote store with spaces",
            bus_cli_path="/home/alexey/agent-bus/coordination/bus_cli.py",
            ssh_binary="ssh.exe",
            runner=mock_runner,
        )

        client.inbox(identity_id="test-id", token="test-tok")

        self.assertEqual(captured_cmd[0], "ssh.exe")
        self.assertIn("-o", captured_cmd)
        self.assertIn("BatchMode=yes", captured_cmd)
        self.assertIn("StrictHostKeyChecking=yes", captured_cmd)

        # Host preceded by '--'
        host_idx = captured_cmd.index("135.181.114.209")
        self.assertEqual(captured_cmd[host_idx - 1], "--")

        # Remote command parts passed after host
        remote_parts = captured_cmd[host_idx + 1 :]
        self.assertEqual(remote_parts[0], "python3")
        self.assertIn("--store", remote_parts)

        # Remote store with spaces must be quoted with single quotes for remote POSIX shell
        store_idx = remote_parts.index("--store")
        quoted_store = remote_parts[store_idx + 1]
        self.assertTrue(
            quoted_store.startswith("'") and quoted_store.endswith("'"),
            f"Remote path with spaces was not single-quoted: {quoted_store}",
        )


def main() -> int:
    suite = unittest.TestLoader().loadTestsFromTestCase(TestWindowsClientAndUnicodeRpc)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())

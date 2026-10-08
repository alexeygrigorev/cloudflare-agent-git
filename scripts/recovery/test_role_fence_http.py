import concurrent.futures
import io
import json
from pathlib import Path
import tempfile
import time
import unittest
import ssl
import subprocess
import threading
import urllib.request
import urllib.error
import hashlib
import http.client
import sqlite3
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import coordination.role_failover as dependency
from coordination.bus import FileBus
from coordination.role_failover import RoleAuthority
from role_fence_http import initialize, NativeChannel, NativeChannels, Handler, load_proxy
from role_fence import CoordinatorFence, Owner
from test_role_fence_cli import sha
import test_role_fence_cli as cli_tests


class HTTPAdapterTests(unittest.TestCase):
    def test_fixed_proxy_profile_pin_and_startup_revocation(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            helper = p / "helper.py"
            helper.write_text("class ManagedProxy:\n def __init__(self,directory,expected,targets): self.directory=directory; self.targets=targets; self.revoked=False\n def revoke_pending(self): self.revoked=True\n")
            profile = {"directory": str(p / "managed-proxy"), "helper_path": str(helper),
                "helper_sha256": sha(helper), "expected_native": {"id": "TEST-native", "tag": "TEST-root", "workspace": "TEST"},
                "targets": ["TEST-principal"]}
            path = p / "proxy.private.json"
            def write():
                path.write_text(json.dumps(profile)); path.chmod(0o600)
            write()
            proxy = load_proxy(p / "authority.json", {"proxy_enabled": True})
            self.assertTrue(proxy.revoked)
            self.assertEqual(proxy.targets, ("TEST-principal",))
            for targets in ("caller-target", [], ["TEST", "TEST"]):
                profile["targets"] = targets; write()
                with self.assertRaises(PermissionError): load_proxy(p / "authority.json", {"proxy_enabled": True})
            profile["targets"] = ["TEST-principal"]
            profile["helper_sha256"] = "0" * 64; write()
            with self.assertRaises(PermissionError): load_proxy(p / "authority.json", {"proxy_enabled": True})
            profile["helper_sha256"] = sha(helper)
            profile["directory"] = str(p / "untrusted"); write()
            with self.assertRaises(PermissionError): load_proxy(p / "authority.json", {"proxy_enabled": True})

    def test_one_canonical_init_no_ready_quota_assertion(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            bus = FileBus(p / "bus")
            identity, token = bus.register(agent_name="TEST", device_id="TEST", project_id="TEST")
            config = {"authority_source": str(Path(dependency.__file__).resolve()),
                "authority_sha256": sha(dependency.__file__), "bus_store": str(bus.root),
                "authority_db": str(p / "canonical.db"), "sink_journal": str(p / "sinks.db"),
                "bindings": {"actual-native-fixture": {"project": "TEST", "role": "root",
                    "host": "TEST", "generation": "s1", "bus_identity": identity.identity_id,
                    "ready": True, "quota_ok": True}}}
            with concurrent.futures.ThreadPoolExecutor(2) as pool:
                futures = [pool.submit(initialize, config) for _ in range(2)]
                outcomes = []
                for f in futures:
                    try:
                        outcomes.append(f.result()["status"])
                    except FileExistsError:
                        outcomes.append("already_exists")
            self.assertEqual(sorted(outcomes), ["already_exists", "initialized_held"])
            a = RoleAuthority(config["authority_db"])
            self.assertEqual(a.tick("TEST", "root")["state"], "replacement_required")

    def command(self):
        return {"v": 1, "key": "TEST", "operation": "root-status",
                "owner": {"role": "root", "actor": "native", "generation": "s1", "epoch": 1}, "payload": {}}

    def test_outbound_channel_synchronous_native_ack(self):
        stream = io.BytesIO()
        channel = NativeChannel(stream)
        command = self.command()
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            result = pool.submit(channel.perform, command, 2)
            for _ in range(100):
                if stream.getvalue():
                    break
                time.sleep(0.005)
            received = json.loads(stream.getvalue())
            self.assertEqual(received["owner"], command["owner"])
            channel.receipt({**command, "state": "completed"})
            self.assertEqual(result.result()["state"], "completed")

    def test_wrong_generation_receipt_fails_closed(self):
        stream = io.BytesIO()
        channel = NativeChannel(stream)
        command = self.command()
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            result = pool.submit(channel.perform, command, 2)
            for _ in range(100):
                if stream.getvalue():
                    break
                time.sleep(0.005)
            channel.receipt({**command, "owner": {**command["owner"], "epoch": 2}, "state": "completed"})
            with self.assertRaises(ConnectionError):
                result.result()

    def test_disconnected_channel_never_reports_completion(self):
        stream = io.BytesIO()
        channel = NativeChannel(stream)
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            result = pool.submit(channel.perform, self.command(), 2)
            for _ in range(100):
                if stream.getvalue():
                    break
                time.sleep(0.005)
            channel.close()
            with self.assertRaises(ConnectionError):
                result.result()

    def test_already_sent_callback_paused_until_fence_expires_cannot_mutate(self):
        stream = io.BytesIO()
        channel = NativeChannel(stream)
        command = self.command()
        mutations = []
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            issuing = pool.submit(channel.perform, command, 0.05)
            for _ in range(100):
                if stream.getvalue():
                    break
                time.sleep(0.001)
            delayed = json.loads(stream.getvalue())  # Issued before callback fence expired.
            with self.assertRaises(TimeoutError):
                issuing.result()
            # Native final consumer performs this live RPC guard after its pause.
            if channel.authorize(delayed["key"], delayed["owner"], delayed["operation"], delayed["payload"]):
                mutations.append("native action")
            self.assertEqual(mutations, [])

    def test_real_mtls_route_denies_delayed_callback_after_takeover(self):
        fixture = cli_tests.AdapterTests("test_real_fixed_sink_and_durable_receipt")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        p = fixture.p
        key, cert = p / "tls.key", p / "tls.crt"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
            "-keyout", str(key), "-out", str(cert), "-days", "1", "-subj", "/CN=localhost",
            "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
            "-addext", "extendedKeyUsage=serverAuth,clientAuth"],
            check=True, capture_output=True, timeout=20)
        fingerprint = hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()
        credential = fixture.request["credential"]
        fixture.config["tls_clients"] = {fingerprint: {
            "actor": "native-A", "role": "root", "project": "TEST",
            "bus_identity": credential["identity_id"]}}
        profile = p / "server.json"
        profile.write_text(json.dumps(fixture.config))
        profile.chmod(0o600)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.config_path, server.channels = profile, NativeChannels()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=cert)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        client = ssl.create_default_context(cafile=cert)
        client.load_cert_chain(cert, key)
        base = "https://127.0.0.1:" + str(server.server_address[1])
        def post(path, request):
            req = urllib.request.Request(base + path, data=json.dumps(request).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, context=client, timeout=5) as reply:
                return json.load(reply)
        # The genuine premodel capsule connects before acquiring a lease.
        # Only its mTLS/enrolled read-only inspect handshake may omit epoch.
        handshake = {**fixture.request, "op": "inspect"}
        handshake.pop("epoch")
        def channel_status(request):
            connection = http.client.HTTPSConnection("127.0.0.1", server.server_address[1], context=client, timeout=5)
            response = None
            try:
                connection.request("POST", "/v1/native-channel", json.dumps(request), {"Content-Type": "application/json"})
                response = connection.getresponse()
                if response.status == 101:
                    self.assertEqual(response.version, 11)  # Exact cached native consumer contract.
                return response.status
            finally:
                if response is not None:
                    response.close()
                connection.close()
        def custody_rows():
            with sqlite3.connect(fixture.a.path) as db:
                return [db.execute("SELECT * FROM " + table).fetchall()
                        for table in ("roles", "actions", "activation_receipts")]
        before_handshake = custody_rows()
        self.assertEqual(channel_status(handshake), 101)
        self.assertEqual(custody_rows(), before_handshake)
        for wrong in ({"actor": "native-B"}, {"generation": "forged"}, {"op": "acquire"},
                      {"v": 2}, {"epoch": None}, {"epoch": True}, {"epoch": 0}, {"epoch": "1"}):
            self.assertEqual(channel_status({**handshake, **wrong}), 403)
        for route in ("/v1/role-control", "/v1/sink-proof"):
            with self.assertRaises(urllib.error.HTTPError):
                post(route, handshake)
        self.assertEqual(custody_rows(), before_handshake)
        self.assertFalse(fixture.count.exists())
        with self.assertRaises(urllib.error.HTTPError):
            post("/v1/role-control", {**fixture.request, "argv": ["untrusted"]})
        with self.assertRaises(urllib.error.HTTPError):
            post("/v1/role-control", {**fixture.request, "actor": "native-B"})
        owner = {k: fixture.request[k] for k in ("project", "role", "actor", "generation", "epoch")}
        command = {"v": 1, "key": "delayed", "owner": owner,
                   "operation": "root-ping", "payload": {"target": "TEST"}}
        stream = io.BytesIO()
        channel = NativeChannel(stream)
        server.channels.channels[("native-A", "session-A")] = channel
        proof_request = {**fixture.request, "key": "delayed"}
        with concurrent.futures.ThreadPoolExecutor(1) as pool:
            issuer = pool.submit(channel.perform, command, 0.5)
            for _ in range(100):
                if stream.getvalue():
                    break
                time.sleep(0.001)
            self.assertEqual(post("/v1/sink-proof", proof_request)["status"], "ok")
            # Same pinned host certificate may admit only an internally enrolled
            # actual successor; retirement denies an already-pending old proof.
            from role_fence_enrollment import enroll_successor, successor_key
            successor_actor = "049058cd-d750-40ad-acab-c702e3019cad"
            receipt = {"v": 1, "key": successor_key(Owner("TEST", "root", "native-A", "session-A", 1)), "owner": owner, "operation": "root-native-successor",
                "payload": {}, "state": "completed", "evidence": {"successor": {
                    "actor": successor_actor, "host": "TEST", "generation": "win32:99:123456789",
                    "whoami": {"id": successor_actor, "tag": "win35-root-capsule-TEST2"},
                    "root_tag": "win35-root-capsule-TEST2", "kernel": {"pid": 99, "creation_filetime": 123456789},
                    "predecessor_owner": owner, "owned_model_exit": {"verified_dead": True, "owner": owner}}}}
            enrolled = enroll_successor(profile, fixture.a, Owner("TEST", "root", "native-A", "session-A", 1), receipt)
            with self.assertRaises(urllib.error.HTTPError):
                post("/v1/sink-proof", proof_request)
            with self.assertRaises(urllib.error.HTTPError):
                post("/v1/role-control", fixture.request)
            successor_request = {**fixture.request, "op": "inspect", "actor": successor_actor,
                "generation": enrolled["generation"], "credential": enrolled["credential"]}
            self.assertEqual(post("/v1/role-control", successor_request)["status"], "ok")
            with self.assertRaises(urllib.error.HTTPError):
                post("/v1/role-control", {**successor_request, "generation": "caller-random"})
            # Rollback does not extend the authority's native callback deadline.
            with patch("role_fence_http.time.time", return_value=1):
                with self.assertRaises(TimeoutError):
                    issuer.result()
            CoordinatorFence(fixture.a, lambda *_: True, {}, lambda *_: True).handback(
                None, Owner("TEST", "root", "native-A", "session-A", 1),
                Owner("TEST", "root", "native-B", "session-B", 2), {"checkpoint": "TEST-C", "ack": "TEST-A"})
            with self.assertRaises(urllib.error.HTTPError):
                post("/v1/sink-proof", proof_request)
            self.assertFalse(fixture.count.exists())


if __name__ == "__main__":
    unittest.main()

"""One mTLS authority adapter; shares the existing enrolled Bus, no scheduler.

Source/profile review is required before installation. Init creates one canonical
store exclusively, with all observations held until the native owner provisions
real readiness/admission evidence. The existing healthy Bus listener is untouched.
"""
import argparse
import hashlib
import importlib.util
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import ssl
import sys
import threading
import time

from role_fence_cli import handle, private_json, pinned_file, CANONICAL_CONFIG, ModelCustodyPending


class NativeChannels:
    """Outbound mTLS native callback connections; never an SSH fallback."""
    def __init__(self):
        self.lock = threading.Lock()
        self.channels = {}

    def dispatch(self, owner, message, timeout):
        with self.lock:
            channel = self.channels.get((owner.actor, owner.generation))
        if channel is None:
            raise ConnectionError("native callback disconnected")
        return channel.perform(message, timeout)

    def authorize_sink(self, request):
        with self.lock:
            channel = self.channels.get((request["actor"], request["generation"]))
        owner = {k: request[k] for k in ("project", "role", "actor", "generation", "epoch")}
        return bool(channel and channel.authorize(request["key"], owner,
                    request["operation"], request["payload"]))


class NativeChannel:
    def __init__(self, stream):
        self.stream = stream
        self.write_lock = threading.Lock()
        self.pending = {}
        self.lock = threading.Lock()

    def perform(self, message, timeout):
        event, box = threading.Event(), {}
        key = message["key"]
        with self.lock:
            if key in self.pending:
                raise PermissionError("native callback already pending")
            deadline = time.monotonic() + timeout
            self.pending[key] = (event, box, message, deadline)
        try:
            command = {**message, "deadline": time.time() + timeout}
            with self.write_lock:
                self.stream.write(json.dumps(command).encode() + b"\n")
                self.stream.flush()
            if not event.wait(timeout):
                raise TimeoutError("native callback uncertain; original key held")
            if "error" in box:
                raise ConnectionError("native callback disconnected; key held")
            return box["result"]
        finally:
            with self.lock:
                self.pending.pop(key, None)

    def receipt(self, message):
        with self.lock:
            item = self.pending.get(message.get("key"))
            if item:
                event, box, expected, deadline = item
                if (message.get("v"), message.get("owner"), message.get("operation"), message.get("payload")) != (
                        1, expected["owner"], expected["operation"], expected["payload"]) or message.get("state") not in ("ok", "completed", "uncertain"):
                    box["error"] = True
                else:
                    box["result"] = message
                event.set()

    def authorize(self, key, owner, operation, payload):
        """Final consumer must call this live just before its mutation.

        No cached signed proof. Once callback times out/disconnects, even a
        delayed previously sent command loses its right to mutate.
        """
        with self.lock:
            item = self.pending.get(key)
            if not item:
                return False
            event, box, expected, deadline = item
            return bool(not event.is_set() and time.monotonic() < deadline
                        and (owner, operation, payload) == (
                            expected["owner"], expected["operation"], expected["payload"]))

    def close(self):
        with self.lock:
            for event, box, expected, deadline in self.pending.values():
                box["error"] = True
                event.set()


def initialize(config):
    source = pinned_file(config["authority_source"], config["authority_sha256"])
    sys.path.insert(0, str(source.parents[1]))
    from coordination.role_failover import RoleAuthority
    bus = Path(config["bus_store"])
    if not all((bus / p).is_file() for p in ("identities.json", "tokens.json")):
        raise PermissionError("existing enrolled Bus required")
    database, journal = Path(config["authority_db"]), Path(config["sink_journal"])
    if not database.is_absolute() or not journal.is_absolute() or database.parent != journal.parent:
        raise ValueError("one private canonical runtime directory required")
    if not database.parent.is_dir() or database.parent.is_symlink():
        raise PermissionError("owner-provisioned runtime directory required")
    if database.exists() or journal.exists():
        raise FileExistsError("canonical installation exists; inspect and preserve it")
    # O_EXCL is the competing-install fence. Failure retains evidence, not resets.
    fd = os.open(database, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    authority = RoleAuthority(database)
    roles = {}
    for actor, binding in config["bindings"].items():
        if binding["role"] not in ("root", "principal"):
            raise ValueError("unsupported coordinator role")
        if binding["role"] == "principal" and not binding["project"].startswith("TEST"):
            raise PermissionError("production principal migration is outside root bootstrap")
        roles.setdefault((binding["project"], binding["role"]), []).append(actor)
        authority.observe(actor, binding["host"], binding["generation"],
                          ready=False, draft=True, quota_ok=False)
    for (project, role), candidates in roles.items():
        authority.configure(project, role, candidates)
    fd = os.open(journal, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    return {"status": "initialized_held", "roles": len(roles), "observation": "native evidence required"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # No request/token/raw native logs in public or terminal output.

    def send(self, status, response):
        body = json.dumps(response).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            if self.path not in ("/v1/role-control", "/v1/native-channel", "/v1/sink-proof"):
                raise PermissionError("fixed route required")
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= 65536 or self.headers.get("Transfer-Encoding"):
                raise ValueError("bounded fixed request required")
            self.connection.settimeout(65)
            request = json.loads(self.rfile.read(length))
            if request.get("v") != 1 or type(request.get("epoch")) is not int or request["epoch"] < 1:
                raise ValueError("exact version and fencing epoch required")
            if any(k in request for k in ("argv", "authority_db", "bus_store", "ready", "quota_ok", "config")):
                raise PermissionError("client cannot override server custody or execution route")
            config = private_json(self.server.config_path)
            cert = self.connection.getpeercert(binary_form=True)
            fingerprint = hashlib.sha256(cert).hexdigest()
            scope = config["tls_clients"].get(fingerprint)
            scopes = scope.get("actors", [scope]) if scope else []
            if not any((request.get("actor"), request.get("role"),
                             request.get("project"), request.get("credential", {}).get("identity_id")) == (
                    s["actor"], s["role"], s["project"], s["bus_identity"]) for s in scopes):
                raise PermissionError("certificate/native actor scope mismatch")
            if self.path == "/v1/sink-proof":
                # The issuer's authenticated role transaction is still held.
                # Do not acquire another DB write lock here and deadlock it.
                bus_source = pinned_file(config["bus_source"], config["bus_sha256"])
                sys.path.insert(0, str(bus_source.parents[1]))
                import coordination.bus as bus_module
                if Path(bus_module.__file__).resolve() != bus_source.resolve():
                    raise PermissionError("canonical Bus source required")
                bus = bus_module.FileBus(config["bus_store"])
                credential = request["credential"]
                ident = bus._auth(credential["identity_id"], credential["token"])
                binding = config["bindings"].get(request["actor"])
                if not binding or binding.get("retired") or (ident["device_id"], ident["project_id"], request["generation"], request["role"], request["project"]) != (
                        binding["host"], binding["project"], binding["generation"], binding["role"], binding["project"]):
                    raise PermissionError("canonical native binding required")
                if not self.server.channels.authorize_sink(request):
                    raise PermissionError("callback is no longer live/current")
                self.send(200, {"v": 1, "status": "ok", "key": request["key"],
                    "owner": {k: request[k] for k in ("project", "role", "actor", "generation", "epoch")},
                    "operation": request["operation"], "payload": request["payload"]})
                return
            if self.path == "/v1/native-channel":
                inspect = {**request, "op": "inspect"}
                handle(config, inspect)  # Exact enrolled/native binding, no observation override.
                binding = (request["actor"], request["generation"])
                channel = NativeChannel(self.wfile)
                with self.server.channels.lock:
                    if binding in self.server.channels.channels:
                        raise PermissionError("native channel already bound")
                    self.server.channels.channels[binding] = channel
                try:
                    self.send_response(101)
                    self.send_header("Upgrade", "role-fence-v1")
                    self.send_header("Connection", "Upgrade")
                    self.end_headers()
                    while True:
                        raw = self.rfile.readline(65537)
                        if not raw or len(raw) > 65536:
                            break
                        channel.receipt(json.loads(raw))
                finally:
                    channel.close()
                    with self.server.channels.lock:
                        if self.server.channels.channels.get(binding) is channel:
                            self.server.channels.channels.pop(binding)
                return
            response = handle(config, request, self.server.channels.dispatch, private_delivery=True,
                              proxy=getattr(self.server, "proxy", None))
        except ModelCustodyPending:
            self.send(200, {"v": 1, "status": "pending", "reason": "model_thread_ack_and_first_tool_pending"})
            return
        except Exception:
            self.send(403, {"v": 1, "status": "fenced", "reason": "authority_or_sink_hold"})
            return
        self.send(200, response)


def load_proxy(config_path, config):
    if config.get("proxy_enabled") is not True:
        return None
    profile = private_json(Path(config_path).parent / "proxy.private.json")
    source = pinned_file(profile["helper_path"], profile["helper_sha256"])
    directory = Path(profile["directory"])
    if directory != Path(config_path).parent / "managed-proxy" or directory.is_symlink():
        raise PermissionError("fixed owner-private managed proxy directory required")
    expected = profile["expected_native"]
    if set(expected) != {"id", "tag", "workspace"} or not all(isinstance(v, str) and v for v in expected.values()):
        raise PermissionError("genuine bound native proxy identity required")
    targets = profile["targets"]
    if (not isinstance(targets, list) or not 1 <= len(targets) <= 8
            or any(not isinstance(t, str) or not 1 <= len(t) <= 128 for t in targets)
            or len(set(targets)) != len(targets)):
        raise PermissionError("fixed unique native recipient allowlist required")
    spec = importlib.util.spec_from_file_location("win35_root_proxy", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    proxy = module.ManagedProxy(directory, expected, tuple(targets))
    proxy.revoke_pending()  # Shared native effect mutex BEFORE any role/election request.
    return proxy


def serve(config_path):
    config = private_json(config_path)
    # Missing store must remain a hold; serving never initializes implicitly.
    if not Path(config["authority_db"]).is_file() or not Path(config["sink_journal"]).is_file():
        raise PermissionError("canonical authority has not been initialized")
    proxy = load_proxy(config_path, config)
    from role_fence_cli import build
    from role_fence_enrollment import reconcile_successors
    authority, _ = build(config, proxy=proxy)
    reconcile_successors(config_path, authority)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(config["tls"]["server_cert"], config["tls"]["server_key"])
    context.load_verify_locations(cafile=config["tls"]["ca_cert"])
    context.verify_mode = ssl.CERT_REQUIRED
    server = ThreadingHTTPServer((config["listen_host"], config["listen_port"]), Handler)
    server.config_path = config_path
    server.channels = NativeChannels()
    server.proxy = proxy
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.serve_forever(poll_interval=0.5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--init-only", action="store_true")
    args = parser.parse_args()
    if args.init_only:
        print(json.dumps(initialize(private_json(CANONICAL_CONFIG))))
    else:
        serve(CANONICAL_CONFIG)

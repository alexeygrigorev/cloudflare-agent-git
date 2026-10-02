#!/usr/bin/env python3
"""Local resource-binding hazard/comparator; no coding agents or Cloudflare calls."""
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import multiprocessing
from pathlib import Path
import shutil
import sqlite3
import tempfile
from urllib.request import Request, urlopen


FLOOR = 8 * 1024**3
BUDGET = 8 * 1024**2
REPOSITORY = Path(__file__).resolve().parents[2]


def resource_guard(root):
    if min(shutil.disk_usage(root).free, shutil.disk_usage(REPOSITORY).free) < FLOOR:
        raise RuntimeError("stop: free disk below 8 GiB")
    allocated = sum(p.stat().st_blocks * 512 for p in root.rglob("*") if p.is_file())
    if allocated > BUDGET:
        raise RuntimeError("stop: fixture exceeded 8 MiB scratch cap")
    return allocated


def serve(database, task, resource, ready):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, body):
            data = json.dumps(body).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            with sqlite3.connect(database, timeout=3) as connection:
                connection.execute("INSERT OR REPLACE INTO rows VALUES (?, ?)",
                                   (data["id"], data["value"]))
            self.respond({"task": task, "resource": resource, "stored": data["value"]})

        def do_GET(self):
            with sqlite3.connect(database, timeout=3) as connection:
                row = connection.execute("SELECT value FROM rows WHERE id = ?",
                                         ("same-logical-id",)).fetchone()
            self.respond({"task": task, "resource": resource,
                          "value": row[0] if row else None})

    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        ready.send(server.server_port)
        ready.close()
        server.serve_forever()


def request(port, value=None):
    payload = None if value is None else json.dumps({"id": "same-logical-id", "value": value}).encode()
    with urlopen(Request(f"http://127.0.0.1:{port}/row", data=payload,
                         headers={"Content-Type": "application/json"}), timeout=5) as response:
        return json.load(response)


def arm(root, name, shared=False, tasks=("A", "B")):
    scratch = root / name
    scratch.mkdir()
    context = multiprocessing.get_context("spawn")
    processes, ports, bindings = [], {}, {}
    try:
        for task in tasks:
            resource = "shared" if shared else f"task-{task}"
            database = scratch / f"{resource}.sqlite"
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE IF NOT EXISTS rows (id TEXT PRIMARY KEY, value TEXT)")
            receiver, sender = context.Pipe(duplex=False)
            process = context.Process(target=serve, args=(str(database), task, resource, sender))
            process.start()
            processes.append(process)
            sender.close()
            try:
                if not receiver.poll(5):
                    raise RuntimeError("runtime failed to start within five seconds")
                ports[task] = receiver.recv()
            finally:
                receiver.close()
            bindings[task] = resource
        # Both runtime processes stay live. Request order is deliberate, not random.
        writes = {task: request(ports[task], f"value-{task}") for task in tasks}
        reads = {task: request(ports[task]) for task in tasks}
        expected = {task: f"value-{task}" for task in tasks}
        return {"resource_bindings": bindings, "writes": writes, "reads": reads,
                "matches_task_value": {task: reads[task]["value"] == expected[task] for task in tasks},
                "live_runtime_count": len(processes), "allocated_bytes_after_requests": resource_guard(root)}
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
            process.join(timeout=5)
            if process.is_alive():
                process.kill()
                process.join(timeout=5)


def main():
    with tempfile.TemporaryDirectory(prefix="codex-runtime-") as directory:
        root = Path(directory)
        resource_guard(root)
        result = {"scope": "scripted local HTTP/SQLite, no coding agents, no Workers/Artifacts",
                  "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  "disk_budget_bytes": BUDGET, "minimum_free_bytes": FLOOR,
                  "free_before_bytes": shutil.disk_usage(root).free,
                  "repository_free_before_bytes": shutil.disk_usage(REPOSITORY).free,
                  "fresh_data_checks": {task: arm(root, f"fresh-{task}", tasks=(task,)) for task in ("A", "B")},
                  "shared_binding": arm(root, "shared", shared=True),
                  "explicit_per_task_binding": arm(root, "explicit"),
                  "ordinary_separate_resource_control": arm(root, "control")}
        assert all(result["fresh_data_checks"][task]["matches_task_value"][task] for task in ("A", "B"))
        assert result["shared_binding"]["matches_task_value"] == {"A": False, "B": True}
        assert all(result[key]["matches_task_value"][task] for key in
                   ("explicit_per_task_binding", "ordinary_separate_resource_control") for task in ("A", "B"))
        result["allocated_bytes_before_cleanup"] = resource_guard(root)
        result["free_after_requests_bytes"] = shutil.disk_usage(root).free
        result["repository_free_after_requests_bytes"] = shutil.disk_usage(REPOSITORY).free
    result["scratch_removed"] = not root.exists()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

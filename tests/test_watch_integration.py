"""Real independent Git actors + already-running foreground CLI watcher.

Only temporary loopback Node/Artifacts services are used. This is not a
Cloudflare write test and does not invoke the scripted demo helper.
"""
import concurrent.futures
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest

from agent_branches.client import AgentBranchesClient

ROOT = Path(__file__).resolve().parents[1]


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class IndependentPushWatchTests(unittest.TestCase):
    def test_live_watcher_observes_external_clean_semantic_and_textual_changes(self):
        prototype = ROOT / "prototype"
        compiled = prototype / ".build/node/src/local/main.js"
        self.assertTrue(compiled.is_file(), "Run npm run build:node in prototype first")
        temporary_parent = Path(tempfile.gettempdir()).resolve()
        state = Path(tempfile.mkdtemp(prefix="branches-e2e-", dir=temporary_parent)).resolve()
        children, logs = [], []
        admin, runner, sidecar_token = (secrets.token_hex(24) for _ in range(3))
        sidecar_port, api_port = port(), port()
        while api_port == sidecar_port:
            api_port = port()
        api = f"http://127.0.0.1:{api_port}"
        environment = {**os.environ, "AGENT_BRANCHES_CONFIG": str(state / "private.json"),
                       "AGENT_BRANCHES_SERVER": api, "ADMIN_TOKEN": admin, "RUNNER_TOKEN": runner,
                       "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
        environment.pop("AGENT_BRANCHES_DEMO_RUN_ID", None)
        environment.pop("TASK_TOKEN", None)
        # uv may select another Python version; never combine its DLLs with
        # the parent interpreter's standard library or active environment.
        for key in ("PYTHONHOME", "PYTHONPATH", "UV_INTERNAL__PYTHONHOME", "VIRTUAL_ENV"):
            environment.pop(key, None)
        for key in ("AGENT_BRANCHES_REPO", "AGENT_BRANCHES_BASE_SHA", "AGENT_BRANCHES_BRANCH"):
            environment.pop(key, None)

        def start(command, extra, name, group=False):
            log = open(state / (name + ".log"), "wb")
            logs.append(log)
            child = subprocess.Popen(command, cwd=ROOT, env={**environment, **extra}, stdout=log, stderr=log,
                                     start_new_session=group and os.name != "nt",
                                     creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if group and os.name == "nt" else 0)
            children.append(child)
            return child

        def git(arguments, cwd, token=None):
            env = dict(environment)
            if token:
                env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.extraHeader", GIT_CONFIG_VALUE_0=f"Authorization: Bearer {token}")
            result = subprocess.run(["git", *map(str, arguments)], cwd=cwd, env=env, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, f"git {arguments[0]} failed")
            return result.stdout.decode().strip()

        def cli(arguments, *, raw=False, cwd=ROOT):
            command = ["uv", "run", "--project", str(ROOT), "branches", *arguments, *(["--json"] if raw else [])]
            result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, encoding="utf-8", timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr[-500:])
            if not raw:
                self.assertNotIn(admin, result.stdout + result.stderr)
            return json.loads(result.stdout) if raw else result.stdout

        client = AgentBranchesClient(api)
        # Do not rely on this test process's ambient credentials/configuration.
        client.settings = {"runner_token": runner, "admin_token": admin}

        def wait(predicate, description, timeout=20):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                try:
                    result = predicate()
                    if result:
                        return result
                except Exception:
                    pass
                time.sleep(0.1)
            self.fail("Timed out: " + description)

        def wait_pair(heads, expected, kind=None):
            def ready():
                status = client.get_status(runner_token=runner)
                if any(status["heads"].get(task["agentId"]) != head for task, head in zip(tasks, heads)):
                    return None
                pair = status["pairs"][0]
                return pair if pair["status"] == expected and not pair["stale"] and (kind is None or pair.get("kind") == kind) else None
            return wait(ready, f"fresh {expected} at external actor heads")

        try:
            start(["node", str(prototype / "local-artifacts/sidecar.mjs")],
                  {"SIDECAR_ROOT": str(state / "sidecar"), "SIDECAR_PORT": str(sidecar_port),
                   "SIDECAR_TOKEN": sidecar_token, "SIDECAR_NOTIFY_URL": api + "/events/push"}, "sidecar")
            start(["node", str(compiled)], {"PORT": str(api_port), "HOST": "127.0.0.1", "LOCAL_ARTIFACTS_URL": f"http://127.0.0.1:{sidecar_port}",
                  "LOCAL_ARTIFACTS_TOKEN": sidecar_token, "COORDINATOR_STATE_FILE": str(state / "coordinator.json")}, "coordinator")
            wait(lambda: client.get_status(runner_token=runner), "local coordinator")
            setup = client._request("POST", "/setup", {}, headers={"Authorization": "Bearer " + admin})
            bare = state / "sidecar/repos" / (setup["canonical"]["name"] + ".git")
            baseline = state / "baseline"
            git(["clone", str(bare), str(baseline)], state)
            git(["config", "user.name", "Watcher integration"], baseline)
            git(["config", "user.email", "watch@example.invalid"], baseline)
            (baseline / "rate.py").write_text("LIMIT = 5\n")
            (baseline / "region.py").write_text("REGION = 'US'\n")
            (baseline / "test_configuration.py").write_text(
                "import unittest\nfrom rate import LIMIT\nfrom region import REGION\n"
                "class Configuration(unittest.TestCase):\n"
                "    def test_combination(self):\n"
                "        self.assertGreater(LIMIT, 0)\n"
                "        if REGION == 'EU': self.assertLessEqual(LIMIT, 10)\n")
            git(["add", "rate.py", "region.py", "test_configuration.py"], baseline)
            git(["commit", "-m", "Track actual combined configuration test"], baseline)
            git(["push", "origin", "main"], baseline)
            base = git(["rev-parse", "HEAD"], baseline)
            cli(["configure", "--test-command", shlex.join([sys.executable, "-m", "unittest", "discover", "-v"])])
            fresh, unrelated = state / "fresh", state / "unrelated"
            fresh.mkdir()
            unrelated.mkdir()
            git(["init"], unrelated)
            git(["config", "user.name", "Unrelated user"], unrelated)
            git(["config", "user.email", "unrelated@example.invalid"], unrelated)
            git(["commit", "--allow-empty", "-m", "Unrelated repository"], unrelated)
            git(["remote", "add", "origin", "https://github.com/example/unrelated.git"], unrelated)
            self.assertNotEqual(git(["rev-parse", "HEAD"], unrelated), base)
            tasks = [cli(["task", "create", "--agent", name, "--intent", "Independent actor", "--files", path], raw=True, cwd=folder)
                     for name, path, folder in (("actor-a", "rate.py", fresh), ("actor-b", "region.py", unrelated))]
            for task in tasks:
                self.assertEqual(task["base_sha"], base)
                self.assertEqual(task["ref"], "refs/heads/main")
            private = json.loads((state / "private.json").read_text())["servers"][api]
            self.assertNotIn("base_sha", private)
            self.assertEqual(private["tasks"][tasks[0]["taskId"]]["base_sha"], base)
            actors = []
            for index, task in enumerate(tasks):
                folder = state / f"actor-{index}"
                git(["clone", task["fork"]["remote"], str(folder)], state, task["token"]["plaintext"])
                git(["config", "user.name", "Independent actor"], folder)
                git(["config", "user.email", "actor@example.invalid"], folder)
                actors.append(folder)
            # A real zero-test command must publish UNKNOWN, never CLEAN.
            cli(["watch", "--once", "--test-command", shlex.join([sys.executable, "-c", "print('Ran 1 test in 0.0s\\nOK\\n1 passed')"])])
            self.assertEqual(client.get_status(runner_token=runner)["pairs"][0]["status"], "unknown")
            watcher = start(["uv", "run", "branches", "watch", "--poll-interval", "0.2", "--duration", "90"], {}, "watch", group=True)
            wait(lambda: "is watching coordinator heads" in (state / "watch.log").read_text(encoding="utf-8", errors="replace"), "foreground CLI watcher startup")
            runtime = json.loads((state / "private.watch.lock").read_text())
            watch_scratch = Path(runtime["scratch"])
            self.assertTrue(watch_scratch.name.startswith("branches-watch-"))
            wait_pair([base, base], "clean")

            def publish(index, filename, content):
                folder, task = actors[index], tasks[index]
                (folder / filename).write_text(content)
                git(["add", filename], folder)
                git(["commit", "-m", "Independent external change"], folder)
                # Ordinary Git only: no demo helper, no inline checker, no
                # client notification call; the running watcher reacts later.
                git(["push", "origin", "main"], folder, task["token"]["plaintext"])
                return git(["rev-parse", "HEAD"], folder)

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                a = pool.submit(publish, 0, "rate.py", "LIMIT = 10\n")
                b = pool.submit(publish, 1, "region.py", "REGION = 'EU'\n")
                heads = [a.result(), b.result()]
            pair = wait_pair(heads, "clean")
            self.assertEqual(pair["coverage"]["tests_collected"], 1)
            # The friendly publish command is another independent client, not
            # a call into the watcher or the demo's inline checking pipeline.
            (actors[0] / "rate.py").write_text("LIMIT = 20\n")
            git(["add", "rate.py"], actors[0])
            git(["commit", "-m", "Independent CLI publication"], actors[0])
            publish_command = ["uv", "run", "--project", str(ROOT), "branches", "publish", "--task-id", tasks[0]["taskId"], "--json"]
            refused_remote = "https://github.com/example/unrelated.git"
            git(["remote", "set-url", "origin", refused_remote], actors[0])
            refused = subprocess.run(publish_command, cwd=actors[0], env=environment, capture_output=True, text=True, timeout=20)
            self.assertNotEqual(refused.returncode, 0)
            git(["remote", "set-url", "origin", tasks[0]["fork"]["remote"]], actors[0])
            published = subprocess.run(publish_command, cwd=actors[0], env=environment, capture_output=True, text=True, timeout=30)
            self.assertEqual(published.returncode, 0, published.stderr[-500:])
            self.assertTrue(json.loads(published.stdout)["accepted"])
            heads[0] = git(["rev-parse", "HEAD"], actors[0])
            pair = wait_pair(heads, "conflict", "test")
            self.assertEqual(pair["coverage"]["tests_collected"], 1)
            heads[0] = publish(0, "rate.py", "LIMIT = 10\n")
            wait_pair(heads, "clean")
            cli(["plan", "--task-id", tasks[0]["taskId"], "--files", "shared.txt"])
            planned = cli(["plan", "--task-id", tasks[1]["taskId"], "--files", "shared.txt"])
            self.assertIn("PLANNED OVERLAP", planned)
            self.assertIn("not a proven merge conflict", planned)
            for task in tasks:
                current = cli(["status", "--task-id", task["taskId"]])
                self.assertIn("Planned files: shared.txt", current)
                self.assertIn("CLEAN (1 combined test(s) collected)", current)
                self.assertIn("agree file ownership", current)
                self.assertIn("Radar Warnings: None", current)
                self.assertNotIn("Warnings: UNKNOWN", current)
                self.assertNotIn(task["token"]["plaintext"], current)
            for actor, head in zip(actors, heads):
                self.assertEqual(git(["rev-parse", "HEAD"], actor), head)
                self.assertEqual(git(["status", "--porcelain"], actor), "")
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                a = pool.submit(publish, 0, "shared.txt", "LIMIT=10\n")
                b = pool.submit(publish, 1, "shared.txt", "LIMIT=20\n")
                heads = [a.result(), b.result()]
            pair = wait_pair(heads, "conflict", "textual")
            self.assertIn("shared.txt", pair["evidence"]["files"])
            current = cli(["status", "--task-id", tasks[0]["taskId"]])
            self.assertIn("CONFLICT", current)
            self.assertIn("Conflicting files: shared.txt", current)
            self.assertEqual(git(["rev-parse", "refs/heads/main"], bare), base)
            self.assertIsNone(watcher.poll(), "The same foreground watcher must remain alive throughout external pushes")
            if os.name == "nt":
                watcher.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(watcher.pid, signal.SIGINT)
            watcher.wait(timeout=15)
            wait(lambda: not (state / "private.watch.lock").exists() and not watch_scratch.exists(), "Ctrl+C releases watcher scratch and private runtime lock")
            output = (state / "watch.log").read_text(encoding="utf-8", errors="replace")
            self.assertIn("shared.txt", output)
            self.assertNotIn(admin, output)
            self.assertNotIn(runner, output)
            self.assertFalse((state / "private.watch.lock").exists())
            # Omitted context follows the server's next canonical HEAD; an
            # explicit historical base remains an intentional supported override.
            git(["commit", "--allow-empty", "-m", "Advance canonical after watcher verification"], baseline)
            git(["push", "origin", "main"], baseline)
            advanced = git(["rev-parse", "HEAD"], baseline)
            next_task = cli(["task", "create", "--agent", "next", "--intent", "Current canonical"], raw=True, cwd=fresh)
            self.assertEqual(next_task["base_sha"], advanced)
            old_task = cli(["task", "create", "--agent", "historical", "--base-sha", base], raw=True, cwd=unrelated)
            self.assertEqual(old_task["base_sha"], base)
            invalid = subprocess.run(["uv", "run", "--project", str(ROOT), "branches", "task", "create", "--agent", "invalid",
                                      "--base-sha", "not-a-sha"], cwd=fresh, env=environment, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("base_sha", invalid.stderr)
            self.assertNotIn(admin, invalid.stdout + invalid.stderr)
            readable = cli(["task", "create", "--agent", "readable", "--intent", "Token stays private"], cwd=fresh)
            self.assertIn(advanced, readable)
            private = json.loads((state / "private.json").read_text())["servers"][api]
            self.assertNotIn("base_sha", private)
            self.assertEqual(private["tasks"][old_task["taskId"]]["base_sha"], base)
        finally:
            for child in reversed(children):
                if child.poll() is None:
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True, timeout=10)
                    else:
                        child.terminate()
                    child.wait(timeout=10)
            for log in logs:
                log.close()
            self.assertEqual(state.parent, temporary_parent)
            self.assertTrue(state.name.startswith("branches-e2e-"))
            def writable(function, path, error):
                if not Path(path).resolve().is_relative_to(state):
                    raise RuntimeError("Refusing cleanup outside this integration test")
                os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
                function(path)
            for attempt in range(20):
                try:
                    shutil.rmtree(state, onerror=writable)
                    break
                except PermissionError:
                    if attempt == 19:
                        raise
                    time.sleep(0.1)


if __name__ == "__main__":
    unittest.main()

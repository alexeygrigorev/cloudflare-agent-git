#!/usr/bin/env python3
"""Two real Git forks: check a clean combination, then an add/add conflict.

Choose the local coordinator/Artifacts emulator or a real Cloudflare Worker.
Credentials stay in environment/private temporary files.
"""
import argparse
import concurrent.futures
import io
import json
import os
from pathlib import Path
import re
import secrets
import signal
import shlex
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.parse
import zipfile


class OwnedProcesses:
    """Own only handles/groups created by this run; never discover or kill by name."""
    def __init__(self, state):
        self.state = state
        self.entries = {}
        self.lock = threading.RLock()

    def _record(self):
        target = self.state / "processes.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps({"ownerPid": os.getpid(), "processes": [
            {"pid": process.pid, "command": command, "startedAt": started}
            for process, (_, command, started) in self.entries.items()]}), encoding="utf-8")
        temporary.replace(target)

    def start(self, command, **kwargs):
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen(command, **kwargs)
        job = None
        if os.name == "nt":
            # A private Windows job contains this process and descendants, even
            # when the direct server exits first. Closing it kills only this job.
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateJobObjectW.restype = wintypes.HANDLE
            kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            class BasicLimits(ctypes.Structure):
                _fields_ = [("processTime", ctypes.c_longlong), ("jobTime", ctypes.c_longlong),
                            ("flags", wintypes.DWORD), ("minWorkingSet", ctypes.c_size_t),
                            ("maxWorkingSet", ctypes.c_size_t), ("activeProcesses", wintypes.DWORD),
                            ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                            ("scheduling", wintypes.DWORD)]
            class IoCounters(ctypes.Structure):
                _fields_ = [(field, ctypes.c_ulonglong) for field in (
                    "readOps", "writeOps", "otherOps", "readBytes", "writeBytes", "otherBytes")]
            class ExtendedLimits(ctypes.Structure):
                _fields_ = [("basic", BasicLimits), ("io", IoCounters),
                            ("processMemory", ctypes.c_size_t), ("jobMemory", ctypes.c_size_t),
                            ("peakProcessMemory", ctypes.c_size_t), ("peakJobMemory", ctypes.c_size_t)]
            handle = kernel.CreateJobObjectW(None, None)
            limits = ExtendedLimits()
            limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            configured = handle and kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits))
            if not configured or not kernel.AssignProcessToJobObject(handle, wintypes.HANDLE(int(process._handle))):
                if handle:
                    kernel.CloseHandle(handle)
                process.kill()
                process.wait(timeout=5)
                raise RuntimeError("Cannot contain the demo child process in its own Windows job")
            job = (kernel, handle)
        with self.lock:
            self.entries[process] = (job, str(command[0]), time.time())
            self._record()
        return process

    def stop(self, process):
        with self.lock:
            entry = self.entries.pop(process, None)
        if entry is None:
            return
        job = entry[0]
        if job:
            kernel, handle = job
            kernel.TerminateJobObject(handle, 1)
            kernel.CloseHandle(handle)
        elif os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        elif process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name != "nt":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.wait(timeout=5)
        with self.lock:
            self._record()

    def run(self, command, *, timeout, capture_output=False, **kwargs):
        if capture_output:
            kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process = self.start(command, **kwargs)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
        finally:
            self.stop(process)

    def close(self):
        for process in reversed(list(self.entries)):
            self.stop(process)


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_key(message):
    """Advance on Space or Enter without requiring a whole input line."""
    print(f"{message} [Space: continue]", end=" ", flush=True)
    if os.name == "nt" and sys.stdin.isatty():
        import msvcrt
        read = msvcrt.getwch
        restore = lambda: None
    elif sys.stdin.isatty():
        import termios
        import tty
        fd = sys.stdin.fileno()
        original = termios.tcgetattr(fd)
        tty.setraw(fd)
        read = lambda: sys.stdin.read(1)
        restore = lambda: termios.tcsetattr(fd, termios.TCSADRAIN, original)
    else:
        read = lambda: sys.stdin.read(1)
        restore = lambda: None
    try:
        while True:
            key = read()
            if key in (" ", "\r", "\n"):
                break
            if key in ("", "\x03", "\x04"):
                raise KeyboardInterrupt
    finally:
        restore()
        print(flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("local", "cloudflare"), default="local")
    parser.add_argument("--verbose", action="store_true", help="Show internal fetch commands and full check evidence")
    parser.add_argument("--plans", action="store_true", help="Also demonstrate persisted planned-file overlap before editing (requires updated server)")
    parser.add_argument("--serve", action="store_true", help="Keep local API and UI running until Ctrl+C")
    parser.add_argument("--interactive", action="store_true", help="Show live UI; Space executes each displayed command or concurrent-push block")
    args = parser.parse_args()
    cloud = args.backend == "cloudflare"
    if cloud:
        private_env = Path(__file__).resolve().parent.parent / ".env"
        if private_env.is_file():
            for line in private_env.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key, value = key.strip(), value.strip()
                    if key in ("BASE_URL", "ADMIN_TOKEN", "RUNNER_TOKEN"):
                        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                            value = value[1:-1]
                        os.environ.setdefault(key, value)
    cloud_url = os.environ.get("BASE_URL", "").rstrip("/")
    if cloud:
        parsed = urllib.parse.urlsplit(cloud_url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
            parser.error("Cloudflare requires BASE_URL=https://your-worker-host (no credentials, path, query or fragment)")
        if not all(os.environ.get(key, "").strip() for key in ("ADMIN_TOKEN", "RUNNER_TOKEN")):
            parser.error("Cloudflare requires ADMIN_TOKEN and RUNNER_TOKEN in the environment")
    prototype = Path(__file__).resolve().parent.parent
    coordinator = prototype / ".build/node/src/local/main.js"
    if not cloud and not coordinator.is_file():
        parser.error("Run npm run build:node in prototype first")
    if (not cloud and not shutil.which("node")) or not shutil.which("git"):
        parser.error("git must be on PATH; local mode also requires node")

    temp_parent = Path(tempfile.gettempdir()).resolve()
    state = Path(tempfile.mkdtemp(prefix="ab-pair-example-", dir=temp_parent)).resolve()
    os.chmod(state, 0o700)
    children, logs = [], []
    owned_processes = OwnedProcesses(state)
    run_id = secrets.token_hex(16)
    credentials = {name: secrets.token_hex(24) for name in ("ADMIN_TOKEN", "RUNNER_TOKEN", "SIDECAR_TOKEN")}
    if cloud:
        credentials.update({key: os.environ[key].strip() for key in ("ADMIN_TOKEN", "RUNNER_TOKEN")})
    git_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    # No inherited endpoint/configuration can redirect this demo to the cloud.
    clean_env = {k: v for k, v in os.environ.items() if k not in (
        "BASE_URL", "ADMIN_TOKEN", "RUNNER_TOKEN", "SIDECAR_TOKEN", "HOST", "RADAR_IMPL",
        "PYTHONHOME", "PYTHONPATH", "UV_INTERNAL__PYTHONHOME", "VIRTUAL_ENV")}
    sidecar_port, api_port = free_port(), free_port()
    while api_port == sidecar_port:
        api_port = free_port()
    api = cloud_url if cloud else f"http://127.0.0.1:{api_port}"
    sidecar = f"http://127.0.0.1:{sidecar_port}"
    initial_budget = None
    cloud_setup_attempted = False
    block_number = 0
    internal_block = False
    awaiting_review = False

    def separator(description):
        nonlocal block_number, awaiting_review
        if args.interactive and awaiting_review:
            wait_key("Review the output above. Next: reveal the next command block.")
            awaiting_review = False
        block_number += 1
        print("\n" + "=" * 72 + f"\nBlock {block_number}: {description}\n", flush=True)

    def command_description(command):
        if "branches task create" in command:
            agent = "A" if "agent-a" in command else "B"
            return f"Register Agent {agent}'s task using the Branches CLI"
        if "branches status" in command:
            return "Read coordination status using the Branches CLI"
        if "/cloud/demo-repos" in command:
            return "Remove the demo repositories"
        if "/cloud/budget" in command:
            return "Check the Cloudflare operation allowance"
        if "/tasks" in command:
            agent = "A" if "agent-a" in command else "B"
            return f"Register Agent {agent}'s task and create its fork"
        if "/setup" in command:
            return "Create the shared canonical repository"
        if "/checks" in command:
            return "Record the measured compatibility result"
        if "/status" in command:
            return "Read the current coordination status"
        if command.startswith("source "):
            return "Load the private inspection environment in another terminal"
        if "merge-tree" in command:
            return "Check both agents' current changes"
        if "unittest" in command:
            return "Run the combined configuration test"
        agent = "Agent A" if ("AGENT_A_DIR" in command or "/agent-a" in command) else "Agent B" if ("AGENT_B_DIR" in command or "/agent-b" in command) else "The authenticated client"
        if command.startswith("printf "):
            return f"{agent}: write the proposed change"
        if "git clone " in command:
            return f"{agent}: clone its own fork"
        for verb, action in (("add", "stage the changed file"), ("commit", "commit the change locally"),
                             ("push", "publish to its own repository"), ("fetch", "fetch the agent's current commit"),
                             ("init", "prepare the local repository"), ("archive", "export the combined files"),
                             ("ls-remote", "verify canonical main stayed unchanged")):
            if verb in shlex.split(command):
                return f"{agent}: {action}"
        return "Inspect the demo state"

    def show(command, pause=True, new_block=True, description=None):
        nonlocal awaiting_review
        if internal_block and not args.verbose:
            return
        if new_block:
            separator(description or command_description(command))
        print(f"$ {command}", flush=True)
        if args.interactive and pause:
            wait_key("Explain the command above. Next: execute it.")
            awaiting_review = True

    def inspect_result(message):
        nonlocal awaiting_review
        if args.interactive:
            wait_key(message)
            awaiting_review = False

    def print_output(value):
        if internal_block and not args.verbose:
            return
        text = value.decode(errors="replace") if isinstance(value, bytes) else str(value)
        for secret in credentials.values():
            if secret:
                text = text.replace(secret, "[REDACTED]")
        if text.strip():
            print(text.rstrip(), flush=True)

    def branches_cli(arguments, json_response=False, display=True):
        if display:
            show("uv run branches " + shlex.join(arguments))
        cli_env = {**clean_env, "AGENT_BRANCHES_SERVER": api, "ADMIN_TOKEN": credentials["ADMIN_TOKEN"],
                   "RUNNER_TOKEN": credentials["RUNNER_TOKEN"], "PYTHONIOENCODING": "utf-8",
                   "AGENT_BRANCHES_REPO": canonical_remote, "AGENT_BRANCHES_BASE_SHA": canonical_before,
                   "AGENT_BRANCHES_BRANCH": "main", "AGENT_BRANCHES_DEMO_RUN_ID": run_id,
                   "AGENT_BRANCHES_CONFIG": str(state / "branches-config.json")}
        command = ["uv", "run", "branches", *arguments]
        if json_response:
            command.append("--json")
        result = owned_processes.run(command, cwd=prototype, env=cli_env, capture_output=True, encoding="utf-8", timeout=30)
        if result.returncode:
            print_output(result.stderr)
            raise RuntimeError(f"Branches CLI {arguments[0]} failed (exit {result.returncode})")
        if json_response:
            return json.loads(result.stdout)
        print_output(result.stdout)
        return result.stdout

    def git(parts, cwd, token=None, allowed=(0,), display=True):
        env = dict(git_env)
        if cloud:
            env.update(GIT_CONFIG_COUNT="2", GIT_CONFIG_KEY_0="http.followRedirects", GIT_CONFIG_VALUE_0="false",
                       GIT_CONFIG_KEY_1="http.userAgent", GIT_CONFIG_VALUE_1="AgentBranchesDemo/1.0")
        if token:
            env.update(GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="http.extraHeader",
                       GIT_CONFIG_VALUE_0=f"Authorization: Bearer {token}")
            if cloud:
                env.update(GIT_CONFIG_COUNT="3", GIT_CONFIG_KEY_1="http.followRedirects", GIT_CONFIG_VALUE_1="false",
                           GIT_CONFIG_KEY_2="http.userAgent", GIT_CONFIG_VALUE_2="AgentBranchesDemo/1.0")
        if display:
            alias = {"agent-a": "AGENT_A_DIR", "agent-b": "AGENT_B_DIR", "authenticated-client": "CHECK_DIR"}.get(cwd.name)
            location = f'"${alias}"' if alias else shlex.quote(cwd.as_posix())
            show(f"git -C {location} " + shlex.join(list(map(str, parts))))
        result = owned_processes.run(["git", *map(str, parts)], cwd=cwd, env=env,
                                capture_output=True, timeout=45)
        if result.returncode not in allowed:
            print_output(result.stderr)
            raise RuntimeError(f"git {parts[0]} failed (exit {result.returncode})")
        if parts[0] in ("clone", "commit", "push", "fetch"):
            print_output(result.stdout)
            print_output(result.stderr)
        return result

    def request(path, token, data=None, display=True, method=None):
        nonlocal cloud_setup_attempted
        method = method or ("GET" if data is None else "POST")
        label = next((k for k, v in credentials.items() if v == token), "AGENT_TOKEN")
        if display:
            show(f'curl -s -A AgentBranchesDemo/1.0 -X {method} "$API{path}" -H "Authorization: Bearer ${label}"'
                 + (' -H "Content-Type: application/json" --data '
                    + ('@"$DEMO_DIR/checks.json"' if path == "/checks" else shlex.quote(json.dumps(data)))
                    if data is not None else "")
                 + " | jq")
        req = urllib.request.Request(api + path,
                                     data=json.dumps(data).encode() if data is not None else None,
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                                              "User-Agent": "AgentBranchesDemo/1.0"},
                                     method=method)
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *unused, **kwargs):
                return None
        if cloud and path == "/setup" and method == "POST":
            cloud_setup_attempted = True
        with urllib.request.build_opener(NoRedirect).open(req, timeout=15) as response:
            return json.load(response)

    def remote_url(remote):
        resolved = urllib.parse.urljoin(api + "/", remote)
        if cloud:
            url = urllib.parse.urlsplit(resolved)
            base = urllib.parse.urlsplit(api)
            if (url.scheme != base.scheme or url.netloc != base.netloc or url.username or url.password
                    or url.query or url.fragment
                    or re.fullmatch(r"/git/[A-Za-z0-9][A-Za-z0-9_.-]*\.git", url.path) is None
                    or ".." in url.path):
                raise RuntimeError("Refusing credentials for a remote outside this Worker's Git gateway")
        return resolved

    def start(command, env, name):
        log = open(state / f"{name}.log", "wb")
        logs.append(log)
        process = owned_processes.start(command, cwd=prototype, env=env, stdout=log, stderr=log)
        children.append(process)

    def wait_heads(tasks, heads):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            status = request("/status", credentials["ADMIN_TOKEN"], display=False)
            if all(status["heads"].get(t["agentId"]) == h for t, h in zip(tasks, heads)):
                return status
            time.sleep(0.2)
        raise RuntimeError("Push callbacks did not update current heads")

    def commit_change(task, folder, filename, content, message):
        print(f"{task['agentId']}: {filename} = {content.strip()}", flush=True)
        alias = "AGENT_A_DIR" if folder.name == "agent-a" else "AGENT_B_DIR"
        show(f"printf '%s\\n' {shlex.quote(content.strip())} > \"${alias}/{filename}\"")
        (folder / filename).write_text(content, encoding="utf-8")
        git(["add", filename], folder)
        git(["commit", "-m", message], folder)

    def push(task, folder):
        git(["push", "origin", "main"], folder, token=task["token"]["plaintext"], display=False)
        return git(["rev-parse", "HEAD"], folder, display=False).stdout.decode().strip()

    def push_both(tasks, folders):
        nonlocal awaiting_review
        separator("Publish both agents' commits to their separate forks")
        print("Publish work in progress to each agent's own fork so their changes can be checked before integration.\n"
              "The main ref below belongs to that agent's fork; shared canonical main stays unchanged.", flush=True)
        for task, folder in zip(tasks, folders):
            print(f"Publish {task['agentId']} to its own fork (branch main).", flush=True)
            alias = "AGENT_A_DIR" if folder.name == "agent-a" else "AGENT_B_DIR"
            show(f'git -C "${alias}" push origin main', pause=False, new_block=False)
        print("The helper supplies each fork's scoped credential privately.", flush=True)
        if args.interactive:
            wait_key("Both agents have local commits. Next: execute both pushes concurrently.")
            awaiting_review = True
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(push, task, folder) for task, folder in zip(tasks, folders)]
            heads = [future.result() for future in futures]
        if cloud:
            for task, head in zip(tasks, heads):
                event = request("/events/push", task["token"]["plaintext"], {
                    "agent": task["agentId"], "fork": task["fork"]["name"],
                    "ref": "refs/heads/main", "sha": head}, display=args.verbose)
                if event.get("accepted") is not True:
                    raise RuntimeError("Cloudflare push notification was not accepted")
        return heads

    def report(tasks, heads, conflict, test_count, output):
        vector = {task["agentId"]: head for task, head in zip(tasks, heads)}
        payload = {
            "contract": "0.1", "vector": vector,
            "policy": {"merge": "merge-tree-v1", "tests": {"command": "python -m unittest discover -v", "budget_s": 30}},
            "coverage": {"pairs_checked": 1, "tests_collected": test_count},
            "results": [{"pair": list(vector), "heads": vector,
                         "status": "conflict" if conflict else "clean", "kind": "textual" if conflict else None,
                         "evidence": {"summary": "add/add conflict in shared.txt" if conflict else "Real merge-tree succeeded; combined unittest passed",
                                      "tests_collected": test_count, "test_output_tail": output[-2000:],
                                      "files": ["shared.txt"] if conflict else []}}],
        }
        (state / "checks.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if args.verbose:
            print("The authenticated client submits the measured result for these exact two commit heads.", flush=True)
        accepted = request("/checks", credentials["RUNNER_TOKEN"], payload)
        if args.verbose:
            print(json.dumps({"accepted": accepted["accepted"], "pairs": accepted["pairs"]}, indent=2))
            print("Read the coordinator's current status to confirm it accepted this result without stale evidence.", flush=True)
        status = request("/status", credentials["ADMIN_TOKEN"])
        pair = status["pairs"][0]
        expected = "conflict" if conflict else "clean"
        if pair["status"] != expected or pair["stale"]:
            raise RuntimeError(f"Expected fresh {expected} pair status")
        if bool(pair["activeWarningIds"]) != conflict:
            raise RuntimeError("Expected no active warning when clean and an active warning when conflicting")
        if not conflict and pair.get("coverage", {}).get("tests_collected") != 1:
            raise RuntimeError("Coordinator did not record actual combined test coverage")
        return status

    def check_combination(tasks, heads):
        nonlocal internal_block
        print("The authenticated client automatically checks these pushed heads before the next status read.", flush=True)
        internal_block = True
        try:
            client = state / "authenticated-client"
            if not client.exists():
                client.mkdir()
                git(["init", "--quiet"], client)
            for task in tasks:
                show(f'git -C "$CHECK_DIR" fetch {shlex.quote(task["fork"]["remote"])} main')
                git(["fetch", task["fork"]["remote"], "main"], client,
                    token=task["token"]["plaintext"], display=False)
            merged = git(["merge-tree", "--write-tree", *heads], client, allowed=(0, 1))
            output = merged.stdout.decode()
            conflict = merged.returncode == 1
            tests = 0
            if conflict:
                if "CONFLICT" not in output or "shared.txt" not in output:
                    raise RuntimeError("Expected an actual shared.txt merge conflict")
            else:
                tree = output.splitlines()[0]
                archive = git(["archive", "--format=zip", tree], client).stdout
                combined = state / "combined"
                combined.mkdir(exist_ok=True)
                with zipfile.ZipFile(io.BytesIO(archive)) as files:
                    for item in files.infolist():
                        if not (combined / item.filename).resolve().is_relative_to(combined.resolve()):
                            raise RuntimeError("Archive path escapes combined tree")
                    files.extractall(combined)
                (combined / "test_combined.py").write_text(
                    "import unittest\nfrom rate import LIMIT\nfrom region import REGION\n\n"
                    "class CombinedConfiguration(unittest.TestCase):\n"
                    "    def test_eu_limit(self):\n"
                    "        self.assertEqual((REGION, LIMIT), ('EU', 10))\n", encoding="utf-8")
                show('uv run python -m unittest discover -s "$DEMO_DIR/combined" -v')
                tested = owned_processes.run([sys.executable, "-m", "unittest", "discover", "-v"], cwd=combined,
                                        capture_output=True, text=True, timeout=30)
                output = tested.stdout + tested.stderr
                if tested.returncode or "Ran 1 test" not in output:
                    raise RuntimeError("Combined test did not pass with one collected test")
                tests = 1
            if args.verbose:
                print(output.strip())
            report(tasks, heads, conflict, tests, output)
        finally:
            internal_block = False

    def show_current_result(tasks, expected):
        branches_cli(["status"])
        current = request("/status", credentials["ADMIN_TOKEN"], display=False)
        pair = next((p for p in current["pairs"] if set(p["pair"]) == {t["agentId"] for t in tasks}), None)
        if not pair or pair["status"] != expected or pair["stale"]:
            raise RuntimeError("Status did not contain the expected fresh automatic check result")
        print(f"Result: {expected.upper()} — {tasks[0]['agentId']} + {tasks[1]['agentId']}; current commits checked.", flush=True)
        print("Conflicting file: shared.txt (LIMIT=10 versus LIMIT=20). Warning recorded." if expected == "conflict" else
              "rate.py + region.py combine successfully. One combined test passed; no warnings.", flush=True)
        if args.verbose:
            print(json.dumps(pair, indent=2))

    def declare_plans(tasks, folders, paths, expected_overlap):
        before = [git(["rev-parse", "HEAD"], folder, display=False).stdout for folder in folders]
        for task, planned in zip(tasks, paths):
            print(f"{task['agentId']} declares planned file paths before editing: {', '.join(planned)}", flush=True)
            result = request(f'/tasks/{task["taskId"]}/plan', task["token"]["plaintext"], {"plannedPaths": planned})
            print(json.dumps(result, indent=2))
        current = request("/status", credentials["ADMIN_TOKEN"])
        overlaps = current.get("plannedOverlaps")
        if not isinstance(overlaps, list) or bool(overlaps) != expected_overlap:
            raise RuntimeError("Server did not return the expected persisted planned-file overlap")
        for folder, head in zip(folders, before):
            if git(["rev-parse", "HEAD"], folder, display=False).stdout != head or git(["status", "--porcelain"], folder, display=False).stdout:
                raise RuntimeError("Plans must be checked before any local edits or new commits")
        if expected_overlap:
            if not any(set(overlap["agents"]) == {t["agentId"] for t in tasks} and overlap["paths"] == ["shared.txt"] for overlap in overlaps):
                raise RuntimeError("Expected server-derived shared.txt planned overlap")
            print("EARLY OVERLAP: both agents plan shared.txt. Local files and commits are unchanged.\n"
                  "This is a coordination warning, not a proven Git conflict.", flush=True)
        else:
            print("Plans are disjoint; no planned-file overlap. Local files and commits are unchanged.", flush=True)

    def prepare_baseline():
        nonlocal initial_budget
        if cloud:
            initial_budget = request("/cloud/budget", credentials["ADMIN_TOKEN"])
            if initial_budget.get("capabilities", {}).get("ownedDemoCleanup") is not True:
                raise RuntimeError("Worker lacks run-owned cleanup; refusing cloud writes. Deploy the reviewed backend first.")
            required = ("repoCount", "remainingDayOps", "remainingMonthOps", "dailyCap", "monthlyCap", "maxRepos", "maxTotalBytes", "utcDayOps", "calendarMonthOps")
            if any(type(initial_budget.get(key)) is not int for key in required):
                raise RuntimeError("Cloud budget counters/caps missing or invalid; refusing writes")
            if initial_budget["repoCount"] != 0:
                raise RuntimeError("Cloud demo inventory is not empty; refusing writes and cleanup")
            if min(initial_budget["remainingDayOps"], initial_budget["remainingMonthOps"]) < 90:
                raise RuntimeError("Cloud demo needs at least 90 daily and monthly operations remaining")
            if not (0 < initial_budget["dailyCap"] <= 200 and 0 < initial_budget["monthlyCap"] <= 6000
                    and 3 <= initial_budget["maxRepos"] <= 4 and 0 < initial_budget["maxTotalBytes"] <= 16 * 1024 * 1024):
                raise RuntimeError("Cloud operational limits are outside demo bounds")
            if args.verbose:
                print(json.dumps(initial_budget, indent=2))
                print("Operation limits do not prove the shared account's dollar spending cap.")
        setup = request("/setup", credentials["ADMIN_TOKEN"], {"runId": run_id})
        remote = remote_url(setup["canonical"]["remote"])
        repository = state / "sidecar/repos" / (setup["canonical"]["name"] + ".git")
        if cloud:
            seed = state / "seed"
            seed.mkdir()
            git(["init", "-b", "main"], seed)
            git(["config", "user.name", "Demo baseline"], seed, display=False)
            git(["config", "user.email", "baseline@example.invalid"], seed, display=False)
            (seed / "README.md").write_text("# Shared checkout configuration\n", encoding="utf-8")
            git(["add", "README.md"], seed)
            git(["commit", "-m", "Create shared baseline"], seed)
            git(["push", remote, "main"], seed, token=credentials["ADMIN_TOKEN"], display=False)
            before = git(["rev-parse", "HEAD"], seed, display=False).stdout.decode().strip()
        else:
            before = git(["rev-parse", "refs/heads/main"], repository, display=False).stdout.decode().strip()
        return remote, repository, before

    try:
        separator("Prepare demo")
        print("Prepare the selected backend and a shared starting repository. Agent changes come next.", flush=True)
        if args.interactive:
            wait_key("Next: prepare the demo environment.")
            awaiting_review = True
        internal_block = True
        if not cloud:
            start(["node", str(prototype / "local-artifacts/sidecar.mjs")],
              {**clean_env, "SIDECAR_ROOT": str(state / "sidecar"), "SIDECAR_PORT": str(sidecar_port),
               "SIDECAR_TOKEN": credentials["SIDECAR_TOKEN"], "SIDECAR_NOTIFY_URL": api + "/events/push"}, "sidecar")
            start(["node", str(coordinator)],
              {**clean_env, "PORT": str(api_port), "HOST": "127.0.0.1", "LOCAL_ARTIFACTS_URL": sidecar,
               "LOCAL_ARTIFACTS_TOKEN": credentials["SIDECAR_TOKEN"], "ADMIN_TOKEN": credentials["ADMIN_TOKEN"],
               "RUNNER_TOKEN": credentials["RUNNER_TOKEN"], "COORDINATOR_STATE_FILE": str(state / "coordinator.json")}, "coordinator")
        deadline = time.monotonic() + 20
        while True:
            try:
                ready_status = request("/status", credentials["ADMIN_TOKEN"], display=False)
                break
            except (OSError, ValueError):
                if time.monotonic() >= deadline:
                    raise RuntimeError("Local coordinator failed readiness")
                time.sleep(0.2)
        if args.plans and "plannedOverlaps" not in ready_status:
            raise RuntimeError("This server needs the planned-path API update deployed before --plans can run. No demo repositories were created.")
        print(("Real Cloudflare Worker + Artifacts; checks execute on this computer." if cloud else
               "Local Git + Agent Branches coordinator; no Cloudflare operations.") + f"\nAPI={api}\nWorkspace: {state}", flush=True)
        if args.interactive:
            print("Space reveals the next block; Space again executes it. Review the output before continuing. Enter also works; Ctrl+C cleans up.", flush=True)
        if args.serve or args.interactive:
            ui_port = free_port()
            while ui_port in (sidecar_port, api_port):
                ui_port = free_port()
            start([sys.executable, "-m", "http.server", str(ui_port), "--bind", "127.0.0.1", "--directory", str(prototype / "ui")], clean_env, "ui")
            secret_file = state / "admin-token.txt"
            secret_file.touch(mode=0o600)
            secret_file.write_text(credentials["ADMIN_TOKEN"], encoding="utf-8")
            print(f"Open http://127.0.0.1:{ui_port}/index.html?api={api}\n"
                  f"Copy the admin token from private file {secret_file} into the UI authentication form.\n"
                  "Token is deliberately omitted from terminal output.", flush=True)
        canonical_remote, canonical_repo, canonical_before = prepare_baseline()
        internal_block = False
        print("The shared starting repository is ready. No agent changes have been made.", flush=True)
        tasks, folders = [], []
        for label in ("A", "B"):
            print(f"Agent {label} registers a task. The coordinator creates its own fork and a scoped write token.", flush=True)
            print("The helper captures the CLI's JSON response privately to keep the new token out of terminal output.", flush=True)
            task = branches_cli(["task", "create", "--agent", f"agent-{label.lower()}",
                                 "--intent", "Configure checkout limit" if label == "A" else "Configure checkout region"], json_response=True)
            task["tokenLabel"] = f"AGENT_{label}_TOKEN"
            credentials[task["tokenLabel"]] = task["token"]["plaintext"]
            task["fork"]["remote"] = remote_url(task["fork"]["remote"])
            root_path = str(prototype.parent)
            if root_path not in sys.path:
                sys.path.insert(0, root_path)
            from agent_branches.cli import format_task_created
            print_output(format_task_created(task))
            tasks.append(task)
            folder = state / f"agent-{label.lower()}"
            print("Clone this agent's fork; the helper supplies its scoped credential privately.", flush=True)
            show(f'git clone {shlex.quote(task["fork"]["remote"])} {shlex.quote(folder.as_posix())}')
            git(["clone", task["fork"]["remote"], str(folder)], state, token=task["token"]["plaintext"], display=False)
            git(["config", "user.name", f"Demo agent {label}"], folder, display=False)
            git(["config", "user.email", f"agent-{label.lower()}@example.invalid"], folder, display=False)
            folders.append(folder)

        if args.serve or args.interactive:
            env_file = state / "demo.env"
            env_file.touch(mode=0o600)
            inspection_env = {
                "API": api,
                "AGENT_BRANCHES_SERVER": api,
                "AGENT_BRANCHES_CONFIG": str(state / "branches-config.json"),
                "AGENT_BRANCHES_REPO": canonical_remote,
                "AGENT_BRANCHES_BASE_SHA": canonical_before,
                "AGENT_BRANCHES_BRANCH": "main",
                "BASE_SHA": canonical_before,
                "ADMIN_TOKEN": credentials["ADMIN_TOKEN"],
                "RUNNER_TOKEN": credentials["RUNNER_TOKEN"],
                "AGENT_A_TOKEN": credentials["AGENT_A_TOKEN"],
                "AGENT_B_TOKEN": credentials["AGENT_B_TOKEN"],
                "FORK_A": tasks[0]["fork"]["remote"],
                "FORK_B": tasks[1]["fork"]["remote"],
                "DEMO_DIR": state.as_posix(),
                "AGENT_A_DIR": folders[0].as_posix(),
                "AGENT_B_DIR": folders[1].as_posix(),
                "CHECK_DIR": (state / "authenticated-client").as_posix(),
            }
            env_file.write_text("".join(f"export {key}={shlex.quote(value)}\n"
                                        for key, value in inspection_env.items()), encoding="utf-8")
            print("In a second Git Bash terminal, load the private inspection environment:", flush=True)
            show(f"source {shlex.quote(env_file.as_posix())}", pause=False)
            show('uv run branches status', pause=False)
        inspect_result("Two agent forks are ready. Inspect the live UI or API. Next: make compatible updates.")

        print("\nSTAGE 1: Compatible checkout configuration updates from two agents.", flush=True)
        if args.plans:
            declare_plans(tasks, folders, [["rate.py"], ["region.py"]], False)
        commit_change(tasks[0], folders[0], "rate.py", "LIMIT = 10\n", "Add request limit")
        commit_change(tasks[1], folders[1], "region.py", "REGION = 'EU'\n", "Add region")
        heads = push_both(tasks, folders)
        wait_heads(tasks, heads)
        check_combination(tasks, heads)
        show_current_result(tasks, "clean")
        inspect_result("Combined merge and one test passed; the live pair is clean. Inspect the result. Next: the same agents introduce a conflict.")

        print("\nSTAGE 2: The same agents introduce conflicting values in shared.txt.", flush=True)
        if args.plans:
            declare_plans(tasks, folders, [["shared.txt"], ["shared.txt"]], True)
        commit_change(tasks[0], folders[0], "shared.txt", "LIMIT=10\n", "Choose limit 10")
        commit_change(tasks[1], folders[1], "shared.txt", "LIMIT=20\n", "Choose limit 20")
        heads = push_both(tasks, folders)
        wait_heads(tasks, heads)
        check_combination(tasks, heads)
        show_current_result(tasks, "conflict")
        client = state / "authenticated-client"
        internal_block = True
        if cloud:
            canonical_after = git(["ls-remote", canonical_remote, "refs/heads/main"], client,
                                  token=credentials["ADMIN_TOKEN"], display=False).stdout.decode().split()[0]
        else:
            canonical_after = git(["rev-parse", "refs/heads/main"], canonical_repo, display=False).stdout.decode().strip()
        if canonical_after != canonical_before:
            raise RuntimeError("Canonical main changed during checks")
        internal_block = False
        print(f"Canonical main unchanged: {canonical_after}", flush=True)
        inspect_result("The merge check found a shared.txt conflict; the live pair has a warning. Inspect the result. Next: stop and clean up.")
        if args.serve:
            secret_file = state / "credentials.json"
            secret_file.touch(mode=0o600)
            secret_file.write_text(json.dumps(credentials, indent=2), encoding="utf-8")
            print(f"\nOpen http://127.0.0.1:{ui_port}/index.html?api={api}\n"
                  f"Enter ADMIN_TOKEN from private file {secret_file} in the UI authentication form.\n"
                  "Current UI shows the conflict case. Ctrl+C stops owned servers and removes demo state.", flush=True)
            while True:
                time.sleep(0.5)
    finally:
        internal_block = True
        cleanup_error = None
        if cloud_setup_attempted:
            try:
                deleted = request("/cloud/demo-repos", credentials["ADMIN_TOKEN"], {"runId": run_id}, display=False, method="DELETE")
                final_budget = request("/cloud/budget", credentials["ADMIN_TOKEN"], display=False)
                if deleted.get("complete") is not True or deleted.get("remaining") != []:
                    raise RuntimeError("Owned cleanup incomplete; another task may still depend on the canonical repository")
                delta = final_budget["calendarMonthOps"] - initial_budget["calendarMonthOps"]
                if not 0 <= delta <= 90:
                    raise RuntimeError("Cloud operation delta exceeded the 90-operation demo bound or rolled over")
                if args.verbose:
                    print(json.dumps({"deleted": deleted.get("deleted"), "repoCount": final_budget["repoCount"],
                                      "operationDelta": delta}, indent=2))
            except Exception as error:
                cleanup_error = RuntimeError(f"Cloud cleanup/budget verification failed: {type(error).__name__}. Inspect the Worker before retrying.")
        owned_processes.close()
        for log in logs:
            log.close()
        if state.parent != temp_parent or not state.name.startswith("ab-pair-example-"):
            raise RuntimeError("Refusing cleanup outside owned temporary directory")
        def remove_readonly(function, path, error):
            # Git objects are read-only on Windows. Only retry paths beneath
            # this exact, already-validated temporary demo directory.
            if not Path(path).resolve().is_relative_to(state):
                raise RuntimeError("Cleanup path escaped owned directory")
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
            function(path)
        for attempt in range(20):
            try:
                shutil.rmtree(state, onerror=remove_readonly)
                break
            except FileNotFoundError:
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.1)
        if cleanup_error:
            print("Cleanup: owned processes stopped; temporary files removed. Remote cleanup remains unverified.", flush=True)
            raise cleanup_error
        print("Cleanup: owned processes stopped; demo repositories and temporary files removed.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Demo stopped.")
    except Exception as error:
        print(f"Demo failed: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)

"""Foreground authenticated-client checks for independently published agent commits."""
import io
import itertools
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import urllib.parse
import zipfile
import xml.etree.ElementTree as ET

from agent_branches.client import StaleVectorError, TokenExpiredError, TokenRevokedError
from agent_branches.config import config_path, settings_for


class WindowsJob:
    """Own the command's complete process tree without invoking slow WMI tools."""
    def __init__(self, process):
        import ctypes
        from ctypes import wintypes
        size = ctypes.c_size_t
        class BasicLimits(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_longlong), ("job_time", ctypes.c_longlong),
                        ("flags", wintypes.DWORD), ("minimum", size), ("maximum", size),
                        ("active", wintypes.DWORD), ("affinity", size),
                        ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD)]
        class IoCounters(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]
        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("basic", BasicLimits), ("io", IoCounters), ("process_memory", size),
                        ("job_memory", size), ("peak_process", size), ("peak_job", size)]
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.api.CreateJobObjectW(None, None)
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if not (self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits))
                and self.api.AssignProcessToJobObject(self.handle, wintypes.HANDLE(int(process._handle)))):
            error = ctypes.get_last_error()
            self.api.CloseHandle(self.handle)
            raise ctypes.WinError(error)

    def terminate(self):
        self.api.TerminateJobObject(self.handle, 1)

    def close(self):
        self.api.CloseHandle(self.handle)


def validated_remote(server, remote):
    url = urllib.parse.urljoin(server + "/", remote)
    target, origin = urllib.parse.urlsplit(url), urllib.parse.urlsplit(server)
    local = target.hostname in ("localhost", "127.0.0.1", "::1") and origin.hostname in ("localhost", "127.0.0.1", "::1")
    if (target.username or target.password or target.query or target.fragment
            or re.fullmatch(r"/git/[A-Za-z0-9][A-Za-z0-9_.-]*\.git", target.path) is None
            or ".." in target.path or target.scheme not in ("http", "https")
            or (not local and (target.scheme != "https" or target.netloc != origin.netloc))):
        raise ValueError("Fork URL must be this coordinator's Git gateway (or its loopback local sidecar)")
    return url


def positive_finite(value, name, maximum):
    if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= maximum:
        raise ValueError(f"{name} must be finite and between zero and {maximum}")
    return value


def scratch_bytes(root):
    total = 0
    for path in root.rglob("*"):
        try:
            info = path.stat()
        except FileNotFoundError:
            # Git removes transient lock files while commands are running.
            continue
        if stat.S_ISREG(info.st_mode):
            total += info.st_size
    return total


UNITTEST_HARNESS = r'''
import json, sys, unittest
_report = sys.argv[1]
class RecordingRunner(unittest.TextTestRunner):
    def run(self, suite):
        result = super().run(suite)
        count = result.testsRun
        skipped = len(result.skipped)
        expected = len(result.expectedFailures)
        failures = len(result.failures) + len(result.unexpectedSuccesses)
        errors = len(result.errors)
        with open(_report, "w", encoding="utf-8") as report:
            json.dump({"collected": count, "passed": max(0, count-skipped-expected-failures-errors),
                       "skipped": skipped+expected, "failures": failures, "errors": errors,
                       "successful": result.wasSuccessful()}, report)
        return result
program = unittest.main(module=None, argv=["unittest"]+sys.argv[2:], testRunner=RecordingRunner, exit=False)
sys.exit(0 if program.result.wasSuccessful() else 1)
'''


def harness_invocation(command, report):
    """Only recognized framework entrypoints get an owned structured report."""
    parts = list(command)
    if not parts:
        raise ValueError("No test command configured")
    prefix = []
    if Path(parts[0]).name.lower() in ("uv", "uv.exe") and parts[1:2] == ["run"]:
        prefix, parts = parts[:2], parts[2:]
    if parts and re.fullmatch(r"python(?:\d+(?:\.\d+)*)?(?:\.exe)?", Path(parts[0]).name.lower()):
        interpreter, rest = prefix + parts[:1], parts[1:]
        if rest[:2] == ["-m", "unittest"]:
            return interpreter + ["-c", UNITTEST_HARNESS, str(report)] + rest[2:], "unittest"
        if rest[:2] == ["-m", "pytest"]:
            if any(argument.startswith("--junit") for argument in rest[2:]):
                raise ValueError("The checker owns the pytest report; remove configured --junit flags")
            return prefix + parts + ["--junitxml=" + str(report)], "pytest"
    if parts and Path(parts[0]).name.lower() in ("pytest", "pytest.exe"):
        if any(argument.startswith("--junit") for argument in parts[1:]):
            raise ValueError("The checker owns the pytest report; remove configured --junit flags")
        return prefix + parts + ["--junitxml=" + str(report)], "pytest"
    raise ValueError("Unsupported test command; configure python -m unittest or python -m pytest for structured results")


def structured_results(report, framework):
    if not report.is_file() or report.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Missing or oversized structured test report")
    if framework == "unittest":
        result = json.loads(report.read_text(encoding="utf-8"))
        keys = ("collected", "passed", "skipped", "failures", "errors")
        if not isinstance(result, dict) or any(type(result.get(key)) is not int or result[key] < 0 for key in keys) or type(result.get("successful")) is not bool:
            raise ValueError("Invalid structured unittest report")
        if result["passed"] > result["collected"]:
            raise ValueError("Invalid structured unittest counts")
        return result
    root = ET.parse(report).getroot()
    cases = list(root.iter("testcase"))
    counts = {"collected": len(cases), "passed": 0, "skipped": 0, "failures": 0, "errors": 0}
    for case in cases:
        if case.find("error") is not None:
            counts["errors"] += 1
        elif case.find("failure") is not None:
            counts["failures"] += 1
        elif case.find("skipped") is not None:
            counts["skipped"] += 1
        else:
            counts["passed"] += 1
    counts["successful"] = not counts["errors"] and not counts["failures"]
    return counts


def remove_owned_scratch(root):
    parent = Path(tempfile.gettempdir()).resolve()
    if root.parent != parent or not root.name.startswith("branches-watch-"):
        raise RuntimeError("Refusing cleanup outside this watcher's scratch directory")
    def writable(function, path, error):
        if not Path(path).resolve().is_relative_to(root):
            raise RuntimeError("Scratch cleanup path escaped its root")
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        function(path)
    for attempt in range(20):
        try:
            shutil.rmtree(root, onerror=writable)
            return
        except FileNotFoundError:
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.1)


class Watcher:
    def __init__(self, client, test_command, *, test_timeout=60, git_timeout=30, max_scratch_mb=256, emit=print):
        if not test_command or not all(isinstance(part, str) and part for part in test_command):
            raise ValueError("watch requires an explicitly configured combined-test command")
        positive_finite(test_timeout, "Test timeout", 3600)
        positive_finite(git_timeout, "Git timeout", 300)
        positive_finite(max_scratch_mb, "Scratch MiB", 1024)
        self.client, self.command = client, list(test_command)
        self.test_timeout, self.git_timeout = test_timeout, git_timeout
        self.max_bytes = int(max_scratch_mb * 1024 * 1024)
        self.emit = emit
        self.log_path = config_path().with_suffix(".watch.log")
        self.root = Path(tempfile.mkdtemp(prefix="branches-watch-")).resolve()
        os.chmod(self.root, 0o700)
        self.repo = self.root / "objects"
        self.repo.mkdir()
        self.sequence = 0
        self.last_signature = None
        self.retry_at = 0
        try:
            if self._run(["git", "init", "--bare", "--quiet"], self.repo, self.git_timeout)[0]:
                raise RuntimeError("Cannot initialize the watcher's private Git object store")
        except BaseException:
            remove_owned_scratch(self.root)
            raise

    def close(self):
        remove_owned_scratch(self.root)

    @staticmethod
    def _stop(process, job=None):
        if os.name == "nt":
            if job:
                job.terminate()
            elif process.poll() is None:
                process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.wait(timeout=5)

    def _run(self, command, cwd, timeout, token=None):
        positive_finite(timeout, "Command timeout", 3600)
        self.sequence += 1
        stdout_path, stderr_path = (self.root / f"{self.sequence}.out", self.root / f"{self.sequence}.err")
        env = dict(os.environ)
        if command[0] == "git":
            env.update(GIT_TERMINAL_PROMPT="0", GIT_CONFIG_COUNT="2", GIT_CONFIG_KEY_0="http.followRedirects",
                       GIT_CONFIG_VALUE_0="false", GIT_CONFIG_KEY_1="http.userAgent", GIT_CONFIG_VALUE_1="AgentBranchesWatch/1.0")
            if token:
                env.update(GIT_CONFIG_COUNT="3", GIT_CONFIG_KEY_2="http.extraHeader", GIT_CONFIG_VALUE_2=f"Authorization: Bearer {token}")
        else:
            env = {key: value for key, value in env.items()
                   if not any(word in key.upper() for word in ("TOKEN", "SECRET", "PASSWORD", "AGENT_BRANCHES_CONFIG"))}
        process = None
        job = None
        try:
            with open(stdout_path, "wb") as out, open(stderr_path, "wb") as err:
                process = subprocess.Popen(command, cwd=cwd, env=env, stdout=out, stderr=err,
                                           start_new_session=os.name != "nt",
                                           creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
                if os.name == "nt":
                    try:
                        job = WindowsJob(process)
                    except Exception:
                        process.kill()
                        process.wait(timeout=5)
                        raise RuntimeError("Cannot establish bounded ownership of the command's Windows process tree")
                deadline = time.monotonic() + timeout
                while process.poll() is None:
                    size = scratch_bytes(self.root)
                    if size > self.max_bytes or stdout_path.stat().st_size + stderr_path.stat().st_size > 32 * 1024 * 1024:
                        raise RuntimeError("Watcher scratch/output limit exceeded")
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Configured command exceeded its time budget")
                    time.sleep(0.05)
            if stdout_path.stat().st_size + stderr_path.stat().st_size > 32 * 1024 * 1024:
                raise RuntimeError("Configured command exceeded its output limit")
            return process.returncode, stdout_path.read_bytes(), stderr_path.read_bytes()
        finally:
            try:
                if process:
                    self._stop(process, job)
            finally:
                if job:
                    job.close()
            stdout_path.unlink(missing_ok=True)
            stderr_path.unlink(missing_ok=True)

    def _git(self, arguments, token=None, allowed=(0,)):
        result = self._run(["git", *arguments], self.repo, self.git_timeout, token)
        if result[0] not in allowed:
            raise RuntimeError(f"Git {arguments[0]} failed; no clean result recorded")
        return result

    def _extract_archive(self, archive, work):
        existing = scratch_bytes(self.root)
        remaining = self.max_bytes - existing
        with zipfile.ZipFile(io.BytesIO(archive)) as files:
            entries = files.infolist()
            if len(entries) > 10000 or sum(entry.file_size for entry in entries) > remaining:
                raise ValueError("Expanded archive exceeds the scratch byte/member limit")
            targets = set()
            for entry in entries:
                raw = entry.orig_filename.rstrip("/")
                target = (work / entry.filename).resolve()
                mode = entry.external_attr >> 16
                if (not raw or "\\" in raw or re.match(r"^[A-Za-z]:", raw) or raw.startswith("/")
                        or any(part in ("", ".", "..") for part in raw.split("/"))
                        or not target.is_relative_to(work.resolve()) or target in targets
                        or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))
                        or entry.file_size < 0 or (entry.is_dir() and entry.file_size)):
                    raise ValueError("Unsafe, duplicate or unsupported archive member")
                targets.add(target)
            total = 0
            for entry in entries:
                target = (work / entry.filename).resolve()
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                actual = 0
                with files.open(entry) as source, open(target, "wb") as output:
                    while True:
                        chunk = source.read(64 * 1024)
                        if not chunk:
                            break
                        actual += len(chunk)
                        total += len(chunk)
                        if actual > entry.file_size or total > remaining:
                            raise ValueError("Actual expanded archive bytes exceed the declared/bounded size")
                        output.write(chunk)
                if actual != entry.file_size:
                    raise ValueError("Archive member size does not match extracted bytes")
                mode = entry.external_attr >> 16
                if mode:
                    os.chmod(target, mode & 0o777)

    def _pair(self, pair, records, vector, task_tokens):
        evidence = {"summary": "Check did not complete", "tests_collected": 0}
        result = {"pair": list(pair), "heads": {agent: vector[agent] for agent in pair},
                  "status": "unknown", "kind": None, "evidence": evidence}
        output = b""
        try:
            for agent in pair:
                record = records[agent]
                token = task_tokens.get(record["taskId"])
                if not token:
                    raise ValueError(f"Missing private fork credential for {agent}; import or register this task first")
                remote = validated_remote(self.client.server_url, record["forkRemote"])
                # Fetch the named branch, then ensure the pinned coordinator
                # commit is present. Never relabel fetched newer HEAD as checked.
                self._git(["fetch", "--quiet", remote, record.get("ref", "refs/heads/main")], token)
                self._git(["cat-file", "-e", vector[agent] + "^{commit}"])
            code, merged, _ = self._git(["merge-tree", "--write-tree", *(vector[agent] for agent in pair)], allowed=(0, 1))
            if code == 1:
                paths = sorted(set(re.findall(r"^\d+ [0-9a-f]+ [123]\t(.+)$", merged.decode(errors="replace"), re.MULTILINE)))
                result.update(status="conflict", kind="textual")
                evidence.update(summary="Git found a textual conflict in the current combined changes", files=paths)
                return result
            tree = merged.decode().splitlines()[0]
            _, listing, _ = self._git(["ls-tree", "-r", tree])
            if any(line.startswith(b"160000 ") for line in listing.splitlines()):
                raise ValueError("Submodule checkout is unsupported by this checker")
            _, archive, _ = self._git(["archive", "--format=zip", tree])
            work = Path(tempfile.mkdtemp(prefix="pair-", dir=self.root))
            report = None
            try:
                self._extract_archive(archive, work)
                report = self.root / f"test-report-{self.sequence}.json"
                report.unlink(missing_ok=True)
                invocation, framework = harness_invocation(self.command, report)
                exit_code, stdout, stderr = self._run(invocation, work, self.test_timeout)
                output = (stdout + stderr)[-8192:]
                measured = structured_results(report, framework)
                report.unlink(missing_ok=True)
                count = measured["collected"]
                evidence["tests_collected"] = count
                if measured["errors"]:
                    evidence["summary"] = "The structured combined-test report contains harness/test errors"
                elif exit_code and measured["failures"] > 0:
                    result.update(status="conflict", kind="test")
                    evidence["summary"] = "Configured combined tests failed at these exact commits"
                elif not exit_code and measured["successful"] and measured["passed"] > 0:
                    result["status"] = "clean"
                    evidence["summary"] = "Combined merge and configured tests passed at these exact commits"
                else:
                    evidence["summary"] = "No actually passed, non-skipped test was established by the structured report"
            finally:
                if report:
                    report.unlink(missing_ok=True)
                # All files are contained beneath this watcher's verified root.
                shutil.rmtree(work, ignore_errors=True)
        except (TokenExpiredError, TokenRevokedError):
            raise
        except (ValueError, TimeoutError, RuntimeError) as error:
            evidence["summary"] = "Check inconclusive: " + str(error)[:180]
        except Exception as error:
            evidence["summary"] = f"Check inconclusive: {type(error).__name__}; inspect the local checker configuration"
        finally:
            # Keep bounded diagnostic output private; only the structured
            # summary/counts/files above are ever submitted to the coordinator.
            text = output.decode(errors="replace")
            secrets = list(task_tokens.values()) + [self.client.settings.get(key, "") for key in ("admin_token", "runner_token")]
            secrets += [os.environ.get(key, "") for key in ("ADMIN_TOKEN", "RUNNER_TOKEN", "TASK_TOKEN")]
            for secret in secrets:
                if isinstance(secret, str) and secret:
                    text = text.replace(secret, "[REDACTED]")
            record = {"at": time.time(), "pair": list(pair), "heads": result["heads"], "status": result["status"],
                      "summary": evidence["summary"], "output_tail": text[-8192:]}
            self.log_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self.log_path.exists() and self.log_path.stat().st_size > 256 * 1024:
                self.log_path.write_text("", encoding="utf-8")
            descriptor = os.open(self.log_path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, "a", encoding="utf-8") as log:
                log.write(json.dumps(record) + "\n")
        return result

    def tick(self):
        status = self.client.get_status()
        records = {record["agentId"]: record for record in status.get("agents", [])}
        vector = {agent: head for agent, head in status.get("heads", {}).items()
                  if agent in records and isinstance(head, str) and re.fullmatch(r"[0-9a-f]{40}", head)}
        _, settings = settings_for(self.client.server_url)
        tokens = dict(self.client.task_tokens)
        for task_id, task in settings.get("tasks", {}).items():
            value = task.get("token", {})
            token = value.get("plaintext") if isinstance(value, dict) else value
            if token:
                tokens[task_id] = token
        unprocessed = {push.get("agentId") for push in status.get("unprocessedPushes", [])}
        signature = (tuple(sorted(vector.items())), tuple(sorted(tokens.items())), tuple(self.command), tuple(sorted(str(agent) for agent in unprocessed)))
        if len(vector) < 2 or (signature == self.last_signature and time.monotonic() < self.retry_at):
            return None
        results = []
        for pair in itertools.combinations(sorted(vector), 2):
            if unprocessed.intersection(pair):
                results.append({"pair": list(pair), "heads": {agent: vector[agent] for agent in pair},
                                "status": "unknown", "kind": None,
                                "evidence": {"summary": "An agent has an unprocessed push; current evidence is incomplete", "tests_collected": 0}})
            else:
                results.append(self._pair(pair, records, vector, tokens))
        payload = {"contract": "0.1", "vector": vector,
                   "policy": {"merge": "merge-tree-v1", "tests": {"command": self.command, "budget_s": self.test_timeout}},
                   "coverage": {"pairs_checked": len(results), "tests_collected": sum(result["evidence"]["tests_collected"] for result in results)},
                   "results": results}
        try:
            accepted = self.client.send_checks(payload)
        except StaleVectorError:
            self.last_signature = None
            self.emit("Heads changed during checking; old evidence discarded. Rechecking current heads next poll.")
            return None
        self.last_signature = signature
        self.retry_at = time.monotonic() + (60 if any(result["status"] == "unknown" for result in results) else 365 * 86400)
        for result in results:
            files = result["evidence"].get("files", [])
            detail = f"; files: {', '.join(files)}" if files else f"; collected tests: {result['evidence']['tests_collected']}"
            if result["status"] == "unknown":
                detail += "; " + result["evidence"]["summary"]
            self.emit(f"{' + '.join(result['pair'])}: {result['status'].upper()}{detail}")
        return accepted


def watch(client, command, *, poll_interval=10, duration=None, once=False, test_timeout=60, emit=print):
    positive_finite(poll_interval, "Poll interval", 3600)
    positive_finite(test_timeout, "Test timeout", 3600)
    if duration is not None:
        positive_finite(duration, "Duration", 7 * 86400)
    lock = config_path().with_suffix(".watch.lock")
    lock.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise RuntimeError("A watcher already owns this project configuration; stop it before starting another")
    os.write(descriptor, str(os.getpid()).encode())
    os.close(descriptor)
    checker = None
    previous_break = None
    if os.name == "nt":
        def interrupt(signum, frame):
            raise KeyboardInterrupt
        previous_break = signal.signal(signal.SIGBREAK, interrupt)
    try:
        checker = Watcher(client, command, test_timeout=test_timeout, emit=emit)
        lock.write_text(json.dumps({"pid": os.getpid(), "scratch": str(checker.root)}), encoding="utf-8")
        emit("Authenticated client is watching coordinator heads. Combined checks run on this computer; Ctrl+C stops.")
        deadline = time.monotonic() + duration if duration else None
        while True:
            try:
                checker.tick()
            except (TokenExpiredError, TokenRevokedError):
                raise
            except Exception as error:
                emit(f"Check unavailable ({type(error).__name__}); safety remains unknown. Retrying with backoff.")
                if once:
                    raise
                time.sleep(max(5, poll_interval))
            if once or (deadline and time.monotonic() >= deadline):
                break
            time.sleep(min(poll_interval, max(0, deadline - time.monotonic())) if deadline else poll_interval)
    except KeyboardInterrupt:
        emit("Watcher stopped.")
    finally:
        try:
            if checker:
                checker.close()
        finally:
            lock.unlink(missing_ok=True)
        emit("Watcher scratch and owned child processes cleaned up.")
        if previous_break is not None:
            signal.signal(signal.SIGBREAK, previous_break)

# Agent Branches — L1 scaffold prototype

Shared base for the "Agent Branches" competition entry: several coding agents
change code concurrently; each agent works in its own fork of a canonical
repo; a lightweight coordinator tracks per-agent WIP heads and surfaces
radar conflict warnings fed by a trusted local runner.

**The coordinator never runs git and never runs tests** (codex C-1309
deployment boundary). The explicit contest deployment runs on plain Node + Git
on existing Hetzner servers. Repos are REAL bare git repositories on disk,
served by a small Node sidecar; agents clone/push with ordinary git; the radar
runs in a separate trusted runner process (L3) and submits results over an
authenticated, vector-gated route.

Exact routes, request/response shapes, the radar hook contract, auth and
the sidecar API are specified in **[CONTRACT.md](CONTRACT.md) (version
0.1.4)** — L2/L3/L4 build against that file, not against this README.

## Run

Explicit prerequisites:
- System `node` must be on `PATH` (required for sidecar post-receive hook execution).
- `git`, `npm`, and `python3` installed.
- Repository dependencies installed via `npm install` in `prototype/` (executing npm scripts without prior advertised `npm install` fails with exit code 127 due to absent local binaries rather than a product failure; independent head-owned Pro489 verified byte-identical author walkthrough extraction and exit 0).

### Quickstart: Build and Test Suites

```bash
cd prototype

# 1. Install dependencies
npm install

# 2. Type check TypeScript sources
npm run typecheck      # tsc --noEmit

# 3. Run worker tests inside workerd
npm test               # worker tests inside workerd: exit 0

# 4. Run sidecar tests with a real Git client
npm run test:sidecar   # local Git server: 16 passed

# 5. Run coordinator core tests on plain Node
npm run test:node      # core + router + local adapters: 64 passed

# 6. Compile Node coordinator
npm run build:node     # outputs .build/node/src/local/main.js
```

> **Note on test runner environments:** `npm run test:node` (64 tests) and `npm run test:sidecar` (16 tests) are zero-dependency plain Node test lanes that execute directly without external services. `npm test` executes inside vitest/workerd. Regarding aggregate `npm run test:all`, both historical receipts are preserved: an initial run exited with code 1 under Flash518e613f (unverified race condition hypothesis; root cause unknown), and an independent re-run exited with code 0 under independentPro4e2 across all 194 tests. No stability claim is made.

### Executable Protocol Walkthrough

The following self-contained Python script (standard library only) runs the complete multi-agent coordination protocol end-to-end:
- Derives source paths from the current working directory (`prototype/`), resolving `node` and `git` on `PATH`.
- Starts the sidecar and Node coordinator on dynamic loopback ports with matching cryptographically random tokens and isolated state (permissions 0700/0600) outside the source tree.
- Executes `POST /setup` to initialize the canonical repository.
- Executes `POST /tasks` for Task 1 (`claude`) and Task 2 (`codex`), securely parsing tokens in Python without external tools (`jq`).
- Clones Task 1's fork into an isolated workspace using path-scoped Git configuration (`GIT_CONFIG_*` in subprocess environment; zero token exposure in `argv`, `.gitconfig`, or URL).
- Makes a real code commit in the fork and pushes natively to `main`.
- Verifies native push event propagation via the sidecar post-receive hook and reads back the updated head from the coordinator.
- Evaluates mergeability via `git merge-tree` and submits Contract 0.1 typed checks (`POST /checks`).
- Verifies authenticated reads (`GET /status`, `GET /tasks/:id`) and confirms anonymous requests are rejected (`401 Unauthorized`).
- Cleans up child processes and temporary workspaces.

```python
#!/usr/bin/env python3
"""
Agent Branches: Self-contained protocol walkthrough (Python standard library only).
Zero external dependencies; safe path-scoped credentials; no argv exposure.
"""
import os
import sys
import time
import json
import socket
import shutil
import secrets
import pathlib
import tempfile
import subprocess
import urllib.request
import urllib.error

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def http_request(url, method="GET", headers=None, data=None, timeout=10):
    req_headers = {"User-Agent": "agent-branches-walkthrough"}
    if headers:
        req_headers.update(headers)
    body = None
    if data is not None:
        if isinstance(data, (dict, list)):
            body = json.dumps(data).encode("utf-8")
            req_headers["Content-Type"] = "application/json"
        elif isinstance(data, str):
            body = data.encode("utf-8")
        elif isinstance(data, bytes):
            body = data
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8")
            return resp.status, content
    except urllib.error.HTTPError as e:
        content = e.read().decode("utf-8") if e.fp else ""
        return e.code, content

def wait_for_ready(url, expected_statuses=(200, 401), timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        try:
            status, _ = http_request(url, method="GET", timeout=2)
            if status in expected_statuses:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False

def main():
    cwd = pathlib.Path.cwd().resolve()
    sidecar_script = cwd / "local-artifacts" / "sidecar.mjs"
    coord_main = cwd / ".build" / "node" / "src" / "local" / "main.js"

    if not sidecar_script.exists():
        sys.stderr.write(f"Error: sidecar script not found at {sidecar_script}. Run from prototype directory.\n")
        sys.exit(1)
    if not coord_main.exists():
        sys.stderr.write(f"Error: coordinator build not found at {coord_main}. Run 'npm run build:node' first.\n")
        sys.exit(1)

    node_bin = shutil.which("node")
    git_bin = shutil.which("git")
    if not node_bin or not git_bin:
        sys.stderr.write("Error: node and git must be available on PATH.\n")
        sys.exit(1)

    # State directory setup outside source repository with 0700 permissions
    custom_state = os.environ.get("AB_STATE_PARENT")
    if custom_state:
        base_dir = pathlib.Path(custom_state).resolve()
        base_dir.mkdir(parents=True, exist_ok=True)
        state_dir = pathlib.Path(tempfile.mkdtemp(prefix="run-", dir=str(base_dir)))
    elif (cwd.parent / "state").exists():
        state_dir = pathlib.Path(tempfile.mkdtemp(prefix="run-", dir=str(cwd.parent / "state")))
    else:
        state_dir = pathlib.Path(tempfile.mkdtemp(prefix="ab-proto-"))
    os.chmod(state_dir, 0o700)

    sidecar_root = state_dir / "sidecar"
    sidecar_root.mkdir(parents=True, exist_ok=True)
    os.chmod(sidecar_root, 0o700)
    coord_state_file = state_dir / "coordinator-state.json"
    workspaces_dir = state_dir / "workspaces"
    workspaces_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(workspaces_dir, 0o700)

    sidecar_port = find_free_port()
    coord_port = find_free_port()
    while coord_port == sidecar_port:
        coord_port = find_free_port()

    # Shared secrets (random tokens, zero home defaults)
    sidecar_token = secrets.token_hex(20)
    admin_token = secrets.token_hex(20)
    runner_token = secrets.token_hex(20)

    sidecar_proc = None
    coord_proc = None
    sidecar_log = open(state_dir / "sidecar.log", "w")
    coord_log = open(state_dir / "coordinator.log", "w")

    try:
        # 1. Start sidecar
        sidecar_env = {
            **os.environ,
            "PATH": os.environ.get("PATH", ""),
            "SIDECAR_ROOT": str(sidecar_root),
            "SIDECAR_PORT": str(sidecar_port),
            "SIDECAR_TOKEN": sidecar_token,
            "SIDECAR_NOTIFY_URL": f"http://127.0.0.1:{coord_port}/events/push",
        }
        sidecar_proc = subprocess.Popen(
            [node_bin, str(sidecar_script)],
            env=sidecar_env,
            stdout=sidecar_log,
            stderr=sidecar_log,
            cwd=str(cwd),
        )

        # 2. Start coordinator
        coord_env = {
            **os.environ,
            "PORT": str(coord_port),
            "LOCAL_ARTIFACTS_URL": f"http://127.0.0.1:{sidecar_port}",
            "LOCAL_ARTIFACTS_TOKEN": sidecar_token,
            "ADMIN_TOKEN": admin_token,
            "RUNNER_TOKEN": runner_token,
            "COORDINATOR_STATE_FILE": str(coord_state_file),
        }
        coord_proc = subprocess.Popen(
            [node_bin, str(coord_main)],
            env=coord_env,
            stdout=coord_log,
            stderr=coord_log,
            cwd=str(cwd),
        )

        # Readiness gate (finite timeout)
        if not wait_for_ready(f"http://127.0.0.1:{coord_port}/status", expected_statuses=(401, 200), timeout=15):
            raise RuntimeError("Coordinator did not become ready within timeout")

        print("1. Service initialization: sidecar and coordinator listening on loopback.")

        # 3. Setup canonical repository
        status, resp_text = http_request(
            f"http://127.0.0.1:{coord_port}/setup",
            method="POST",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        if status not in (200, 201):
            raise RuntimeError(f"POST /setup failed with status {status}: {resp_text}")
        setup_data = json.loads(resp_text)
        print(f"2. Canonical repository setup: {setup_data.get('canonical', {}).get('name')}")

        # 4. Create Task 1 (claude) and Task 2 (codex)
        status, resp1_text = http_request(
            f"http://127.0.0.1:{coord_port}/tasks",
            method="POST",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={"agent": "claude", "intent": "fix login loop"},
        )
        if status not in (200, 201):
            raise RuntimeError(f"POST /tasks (claude) failed with status {status}: {resp1_text}")
        task1 = json.loads(resp1_text)
        task1_token = task1["token"]["plaintext"]
        task1_remote = task1["fork"]["remote"]
        task1_agent = task1["agentId"]
        task1_id = task1["taskId"]

        # Store token with 0600 permissions outside source code
        task1_tok_file = workspaces_dir / ".task1.token"
        task1_tok_file.touch(mode=0o600)
        task1_tok_file.write_text(task1_token)

        status, resp2_text = http_request(
            f"http://127.0.0.1:{coord_port}/tasks",
            method="POST",
            headers={"Authorization": f"Bearer {admin_token}"},
            data={"agent": "codex", "intent": "refactor auth routes"},
        )
        if status not in (200, 201):
            raise RuntimeError(f"POST /tasks (codex) failed with status {status}: {resp2_text}")
        task2 = json.loads(resp2_text)
        task2_token = task2["token"]["plaintext"]
        task2_agent = task2["agentId"]
        task2_base_sha = task2.get("base_sha") or task2.get("head")

        task2_tok_file = workspaces_dir / ".task2.token"
        task2_tok_file.touch(mode=0o600)
        task2_tok_file.write_text(task2_token)
        print(f"3. Provisioned forks: {task1_agent} and {task2_agent}")

        # 5. Clone Task 1 fork into isolated workspace with path-scoped authentication
        clone_dir = workspaces_dir / "task1-clone"
        git_env = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Bearer {task1_token}",
        }
        res = subprocess.run([git_bin, "clone", task1_remote, str(clone_dir)], env=git_env, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"git clone failed: {res.stderr}")
        print("4. Cloned fork into isolated workspace.")

        # 6. Make commit and push from clone
        subprocess.run([git_bin, "config", "user.name", "Agent Claude"], cwd=clone_dir, check=True, capture_output=True)
        subprocess.run([git_bin, "config", "user.email", "claude@example.invalid"], cwd=clone_dir, check=True, capture_output=True)

        sample_code_file = clone_dir / "fix.txt"
        sample_code_file.write_text("login loop fix verified\n")
        subprocess.run([git_bin, "add", "fix.txt"], cwd=clone_dir, check=True, capture_output=True)
        subprocess.run([git_bin, "commit", "-m", "fix login loop"], cwd=clone_dir, check=True, capture_output=True)

        res = subprocess.run([git_bin, "push", "origin", "main"], cwd=clone_dir, env=git_env, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"git push failed: {res.stderr}")

        task1_head = subprocess.check_output([git_bin, "rev-parse", "HEAD"], cwd=clone_dir, text=True).strip()
        print(f"5. Pushed commit to fork (head: {task1_head[:8]}).")

        # 7. Native coordinator head readback (wait for post-receive webhook delivery)
        updated = False
        start_poll = time.time()
        while time.time() - start_poll < 10:
            status, s_text = http_request(
                f"http://127.0.0.1:{coord_port}/status",
                method="GET",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            if status == 200:
                head_status_data = json.loads(s_text)
                if head_status_data.get("heads", {}).get(task1_agent) == task1_head:
                    updated = True
                    break
            time.sleep(0.3)

        if not updated:
            raise RuntimeError(f"Coordinator did not reflect updated head {task1_head} within timeout")
        print("6. Native post-receive hook verified: coordinator head vector updated.")

        # 8. Real git merge-tree check and Contract 0.1 typed checks submission
        res = subprocess.run(
            [git_bin, "merge-tree", "--write-tree", task1_head, task2_base_sha],
            cwd=clone_dir,
            capture_output=True,
            text=True,
        )
        if res.returncode == 0:
            check_status = "clean"
            check_kind = None
            evidence = {"summary": "clean trial merge across agent heads"}
        else:
            check_status = "conflict"
            check_kind = "textual"
            evidence = {"summary": "textual conflict detected by git merge-tree"}

        checks_payload = {
            "contract": "0.1",
            "vector": {task1_agent: task1_head, task2_agent: task2_base_sha},
            "policy": {
                "merge": "merge-tree-v1",
                "tests": {"command": "npm test", "budget_s": 60},
            },
            "results": [
                {
                    "pair": [task1_agent, task2_agent],
                    "heads": {task1_agent: task1_head, task2_agent: task2_base_sha},
                    "status": check_status,
                    "kind": check_kind,
                    "evidence": evidence,
                }
            ],
        }

        status, checks_resp = http_request(
            f"http://127.0.0.1:{coord_port}/checks",
            method="POST",
            headers={"Authorization": f"Bearer {runner_token}"},
            data=checks_payload,
        )
        if status != 200:
            raise RuntimeError(f"POST /checks failed with status {status}: {checks_resp}")
        print("7. Contract 0.1 typed checks submitted and accepted by coordinator.")

        # 9. Authenticated reads and anonymous 401 check
        status, _ = http_request(
            f"http://127.0.0.1:{coord_port}/status",
            method="GET",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        if status != 200:
            raise RuntimeError(f"Authenticated GET /status failed: {status}")

        status, _ = http_request(
            f"http://127.0.0.1:{coord_port}/status",
            method="GET",
        )
        if status != 401:
            raise RuntimeError(f"Anonymous GET /status expected 401, got {status}")

        status, _ = http_request(
            f"http://127.0.0.1:{coord_port}/tasks/{task1_id}",
            method="GET",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        if status != 200:
            raise RuntimeError(f"Authenticated GET /tasks/:id failed: {status}")
        print("8. Read access control verified: 200 OK authenticated, 401 Unauthorized anonymous.")
        print("Walkthrough completed successfully.")

    finally:
        # Graceful cleanup of exact child processes and state
        if coord_proc:
            coord_proc.terminate()
            try:
                coord_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                coord_proc.kill()
        if sidecar_proc:
            sidecar_proc.terminate()
            try:
                sidecar_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                sidecar_proc.kill()
        sidecar_log.close()
        coord_log.close()
        shutil.rmtree(state_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
```

## Auth

ALL mutating and sensitive read routes are authenticated (muse-r46 review, CONTRACT 0.1.1, C1462 Task 1):

- `POST /setup` and `POST /tasks` (including the fork write-token minted
  there) require `Authorization: Bearer $ADMIN_TOKEN`.
- `POST /checks` (trusted radar runner results) requires
  `Authorization: Bearer $RUNNER_TOKEN`.
- `POST /events/push`, `/events/artifacts`, `/tasks/:id/tests` and
  `/warnings/:id/ack` accept `ADMIN_TOKEN`, the relevant agent's per-task
  token (the write token from `POST /tasks`; the coordinator stores only its
  SHA-256 digest), or — webhooks only — the sidecar shared bearer
  (`LOCAL_ARTIFACTS_TOKEN`). A valid token for a DIFFERENT agent is
  rejected with `403` (no cross-agent writes: an agent cannot post test
  provenance or acks for another agent).
- `GET /status` requires `ADMIN_TOKEN`, `RUNNER_TOKEN` (the runner fetches
  the heads vector before `POST /checks`), or any valid per-task agent token.
  Anonymous requests fail with `401` (`{"error": "unauthorized", "message": "Missing or invalid bearer token"}`).
- `GET /tasks/:id` is owner-or-admin: accepts `ADMIN_TOKEN` or the task owner's
  per-task token. Anonymous requests return `401`; a valid token for a different
  agent returns `403`.
- Missing or wrong token → `401`; if the env secret is not configured the
  route fails closed with `503`. Tokens are never logged or echoed back
  (SHA-256 digest compare — token length is not timing-observable;
  token-free error bodies).
- Per-agent workspaces must keep tokens in 0600 git-ignored files or environment
  variables (`GIT_CONFIG_*`), never in process `argv`, URLs, or published logs.
- The sidecar post-receive hook (`prototype/local-artifacts/notify-hook.mjs`)
  executes with system `node` on `PATH` to deliver push notifications back
  to the coordinator.

## Routes

| Route | Auth | Meaning |
| --- | --- | --- |
| `POST /setup` | admin | create canonical repo (idempotent) |
| `POST /tasks` | admin | `{agent, intent?, base_sha?, ttlSeconds?}` — fork canonical, mint write token; records base_sha + intent |
| `POST /events/push` | agent token \| admin \| sidecar | `{agent\|fork, ref?, sha}` — WIP head; sha must be a real commit in the fork; dedups per (agent, sha), bounded ring |
| `POST /events/artifacts` | sidecar \| admin | documented `cf.artifacts.repo.pushed` envelope → same handler |
| `POST /checks` | runner | `{contract:"0.1", vector, policy, coverage?, results:[{pair,heads,status,kind?,evidence}]}` — vector must equal current heads (stale → 409); warnings only for `conflict` |
| `GET /status` | admin \| runner \| agent token (anonymous 401) | canonical, agents, head vector, per-pair radar status, warnings, radar log, last runner report |
| `GET /tasks/:id` | task's agent \| admin (anonymous 401; cross-agent 403) | base_sha, intent, head, pushes, warnings + acks, testProvenance |
| `POST /tasks/:id/tests` | task's agent \| admin | `{command, exit, head_sha}` — attach test provenance (evidence gate) |
| `POST /warnings/:id/ack` | acking agent \| admin | `{agent, note?}` — record who acknowledged which warning at which head; cross-agent acks are 403 |

## Architecture

Provider-neutral facade since CONTRACT 0.1.4 (details in
[ARCHITECTURE.md](./ARCHITECTURE.md)): the coordination logic lives in
`src/core/` (pure TypeScript over `src/ports/` interfaces — GitHost,
CoordinationStore, PushEvents, Clock/Ids). A zero-dependency `node:http` runtime
(`src/local/main.ts`) serves the same routes from the same core; `npm run test:node`
runs the core suite with NO workerd. Cloudflare Workers and Durable Objects
adapter source (`src/cloudflare/`) is available as an architectural reference
implementation; the explicit contest deployment uses Node + Git on existing Hetzner
with NO Cloudflare deployment plans or instructions.

```
              ┌───────────────── Plain Node Coordinator (src/local/main.ts) ─────────┐
  agent/      │  POST /tasks (admin)   POST /events/*   POST /checks (runner)         │
  harness  ──►│        │                                       │                      │
              │        └──────────────┬────────────────────────┘                      │
              │                 Local Router                                          │
              └───────────────────────┼───────────────────────────────────────────────┘
                                      ▼
        ┌── CoordinatorCore (src/core/coordinator.ts) ────────────────┐
        │  model (persisted via the CoordinationStore port)           │
        │  agents · heads · tasks · warnings/acks                     │
        │  pair checks · runner reports                               │
        │  Radar hook (src/radar.ts, StubRadar                        │
        │  reports not_checked — never a warning)                     │
        └───────────────┬─────────────────────────────────────────────┘
                        ▼  GitHost port (src/ports/githost.ts)
             ├─ SidecarArtifacts ← local Node sidecar (src/local/githost.ts)
             └─ RealArtifacts   ← optional Cloudflare Artifacts adapter (src/artifacts/)

  trusted radar runner (L3, separate process, NOT the coordinator)
      reads /status → does trial merges/tests locally → POST /checks

  local sidecar (prototype/local-artifacts/, Node built-ins + system git)
      real bare repos on disk · create = git init --bare + plumbing seed
      fork = git clone --bare (+ git update-ref to base_sha)
      smart HTTP via git http-backend · per-repo tokens (read can't push)
      post-receive hook → POST /events/push {fork, ref, sha}
```

- **CoordinatorCore**: creates task forks, records pushes (verifying the sha against
  the real repo), maintains the head vector, invalidates warnings when a pair member
  advances, and records trusted runner results. State persists through the
  `CoordinationStore` port (file or in-memory in local mode; DO storage in Cloudflare mode);
  restart tests exist in both runtimes (`test/node` shared-store reconstruction and
  workerd `evictDurableObject`).
- **Radar**: the in-coordinator hook only logs pairs as `not_checked`. Warnings
  exist only for runner-submitted `conflict` results; `clean` at the same
  heads resolves a warning; `unknown` and `not_checked` (including stale
  checks after heads move) are always visibly distinct from `clean`.

## What is real vs deferred

| Piece | Local / Hetzner (today) | Real (account) |
| --- | --- | --- |
| Repo store | REAL bare git repos on disk via the sidecar | Cloudflare Artifacts repos |
| Git remotes | `http://127.0.0.1:8790/git/<name>.git` (smart HTTP) | `https://<ACCOUNT_ID>.artifacts.cloudflare.net/git/<ns>/<repo>.git` |
| Tokens | sidecar-minted, same documented format `art_v1_<40hex>?expires=<unix>` | binding `createToken(scope, ttl)` — real service issues `art_v2_x_<40hex>?expires=<unix>`; tokens are OPAQUE, no prefix validation |
| Push events | sidecar post-receive hook → POST /events/push, plus exceptional manual/envelope recovery routes | real agents `git push` + `cf.artifacts.repo.pushed` subscription → same handler |
| Commit verification | real (`git cat-file`) | `port.hasCommit` → binding `readCommit(sha)`; real commits carry `hash` + epoch-seconds instants, mapped to port types in `src/artifacts/map.ts` |
| Fork at explicit base | real (`git update-ref` after bare clone) | binding cannot fork at a commit: forks default branch, waits for LIST-status readiness (bounded), records realized base = fork head |
| Trial merges/tests | trusted local runner (L3 lane), never the coordinator | same (deployment boundary) |

Real-service evidence: `artifacts-spike/RESULTS.md` +
`appendix-transcript.md` on `origin/proto/artifacts-spike` (@ c75faa1,
29 ops against the real service, 2026-10-03).

Evidence breakdown:
- **Canonical source restore**: Verified independent GitHub restore at `b4a261b6` main; all five source hashes match accepted source `928a838d`, with git fsck exit 0.
- **Operator merge recheck**: Operator recheck (not a new model run; native model traces separately retained) across author commits A772 (`77202c16`), B421 (`4211e0e8`), and C343 (`343c00b2`) demonstrates clean `git merge-tree` (exit 0) and merged-tree tests (A+B: 7 tests, A+C: 11 tests, B+C: 6 tests; all exit 0). Typed checks returned HTTP 200, stale prior vector returned HTTP 409.
- **AgentBus consistency**: Interface AC60 accepted on main at `f389b716` with consumer three-case acceptance; physical two-host proof (AC59) remains pending.
- **Python CLI integration**: Source-only CLI680 accepted via head-registered terminal independent Pro eleven mock tests; normal guard integration `93e4d096` pushed and read back from GitHub (exit 0) at 15:05 UTC. Explicitly distinguishes mock tests from fresh 3-model execution and physical gates.
- **Live fresh 3-model execution**: Fresh actual runtime feature-free 680 seed / 3 forks at 15:05, dispatcher hardcoded historical IDs held prelaunch; bounded Flash repair `6eb045` live, not new 3-model proof. Existing same-host native owner A772 / operator checks HTTP 200 / stale HTTP 409 are separate earlier receipts.

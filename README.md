# agent-branches SDK

Minimal Python SDK client for the Cloudflare Agent Branches L2 coordinator: a
small CLI (`agent-branches`) plus the importable `agent_branches` package
(`client.py`, `cli.py`, `git_utils.py`). MIT licensed.

## Requirements

- Python 3.10+ (stdlib only; no pip installs, no build step).
- A reachable L1 coordinator server (default `http://127.0.0.1:8787`, or set
  `AGENT_BRANCHES_SERVER`).

## Install / run

Clone this repository; the SDK is the repository root. No installation step.

```bash
chmod +x agent-branches        # executable launcher (mode 100755)
./agent-branches --help
```

`./agent-branches` adds the repo root to `sys.path` and calls
`agent_branches.cli.main`.

## Usage examples

```bash
# Register a new task (repo/base-sha/branch default to the local git state)
./agent-branches task create --intent "Fix flaky admission test" \
    --branch proto/my-feature --json

# Register a WIP commit push with test provenance evidence
./agent-branches push --branch proto/my-feature --commit <sha> \
    --test-provenance "python3 -m unittest: 22 passed"

# Query coordinator and radar status for a task
./agent-branches --json status --task-id <task-id>

# Acknowledge an active radar conflict warning
./agent-branches ack --task-id <task-id> --warning-id <warning-id> \
    --action "rebased onto latest main"

# Submit radar check results (CONTRACT v0.1)
./agent-branches checks --help
```

The same operations are available from Python:

```python
from agent_branches.client import AgentBranchesClient

client = AgentBranchesClient()          # reads AGENT_BRANCHES_SERVER
print(client.status(task_id="..."))
```

## Test contract (declared)

| Command | Meaning | Expected result |
| --- | --- | --- |
| `python3 -m unittest -v tests/test_client.py` | **Full SDK client test suite** | **22/22 PASS (OK)** |
| `./agent-branches --help` | Launcher smoke test | exit code 0 |
| `python3 -m unittest discover -s tests` | Whole-directory discovery (SDK **and** non-SDK harness tests) | **FAILS with 4 known errors** — not the SDK contract |

Honest disclosure: `python3 -m unittest discover -s tests` currently reports
`Ran 26 tests ... FAILED (errors=4)`. The four import errors are
`test_a01_runner`, `test_admission`, `test_radar_engine`, and
`test_run10_ack_parser`, which depend on the unbundled `radar/` engine and the
`research/` harness (`research.antigravity.continuation_trial_runner`, etc.).
These research tests are intentionally left in place and are **not** part of
the SDK client suite; they are not deleted or masked to make discovery look
green.

## Run against a local coordinator

The package ships an offline mock coordinator (`tests/mock_l1_server.py`) for
smoke tests and trying the CLI without any infrastructure:

```bash
# Terminal 1 — coordinator on an ephemeral port, gated by a fresh admin token
ADMIN_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
python3 tests/mock_l1_server.py --port 0 --admin-token "$ADMIN_TOKEN"
# prints: Mock L1 Coordinator Server listening at http://127.0.0.1:<port>

# Terminal 2 — point the SDK at it and create a task
export ADMIN_TOKEN
export AGENT_BRANCHES_SERVER=http://127.0.0.1:<port>   # or pass --server per call
./agent-branches task create --intent "My change" --json
```

`task create` fills `repo`, `base-sha` and `branch` from the local git state.
The response carries a per-task token (`token.plaintext`); the Python client
caches it for later `push()` calls. The CLI is process-per-invocation and
cannot keep that cache, so for a coordinator that enforces bearer auth either
export `ADMIN_TOKEN` (admin bearer) or drive pushes through
`AgentBranchesClient`, which resolves the token automatically:

```python
from agent_branches.client import AgentBranchesClient

c = AgentBranchesClient(server_url="http://127.0.0.1:<port>")
task = c.create_task(repo="...", base_sha="...", intent="...", branch="...",
                     admin_token=os.environ["ADMIN_TOKEN"])
c.push(task_id=task["taskId"], files_changed=["README.md"],
       test_provenance="python3 -m unittest: 22 passed")  # token from cache
```

Note: the mock coordinator simulates the L1 HTTP routes and the admin/runner/
per-task bearer ladders; it does not simulate the deployment sidecar.

### Production-parity local run (compiled Node coordinator + Git sidecar)

For full local development with real bare Git repositories and Smart HTTP
cloning and pushing (instead of the offline mock double), run the compiled Node
coordinator alongside the Git sidecar. The daemons are not part of this SDK
repository; they live in an external integration checkout or a packaged
runtime, located through `INTEGRATION_DIR` (default: the sibling
`agent-branches-integration` clone, i.e. `/home/alexey/git/agent-branches-integration`
on the dev host; packaged runtimes point `INTEGRATION_DIR` at the unpacked
runtime directory).

Write the shared stack environment once to `.env.local` with `umask 077`, so
the file is created mode `0600` (owner read/write only), then source it in
every terminal that drives the stack — exported variables do not cross
terminals, and retyping tokens by hand leaks them to scrollback and shell
history:

```bash
# Once — generate fresh tokens and the shared env file (mode 0600)
umask 077
cat > .env.local <<EOF
INTEGRATION_DIR=${INTEGRATION_DIR:-../agent-branches-integration}
SIDECAR_PORT=8790
SIDECAR_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
ADMIN_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
RUNNER_TOKEN=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
EOF
chmod 600 .env.local   # belt-and-braces; umask 077 already produced 0600
```

```bash
# Terminal 1 — Launch the real Git Smart HTTP sidecar daemon
set -a; . ./.env.local; set +a
export SIDECAR_ROOT=./.sidecar-root
node "$INTEGRATION_DIR/prototype/local-artifacts/sidecar.mjs"

# Terminal 2 — Launch the compiled Node coordinator daemon
# Bounded flags, stated as an observed empirical mitigation (Node 24):
# --disable-wasm-trap-handler removes V8's large WASM trap-handler
# address-space reservation, but on its own it is NOT a fix under a hard
# cap — at `ulimit -v 1500000` the full coordinator still aborts on the
# first served request. The verified working envelope pairs the flag with
# an explicit heap cap and a slightly raised address-space limit
# (`ulimit -v 1530000`; 5/5 heartbeats served, RSS 62–77 MB observed):
set -a; . ./.env.local; set +a
ulimit -v 1530000   # per-process virtual address space, not the shared physical budget
export PORT=8787
export HOST=127.0.0.1
export LOCAL_ARTIFACTS_URL=http://127.0.0.1:$SIDECAR_PORT
export LOCAL_ARTIFACTS_TOKEN=$SIDECAR_TOKEN
export COORDINATOR_STATE_FILE=./coordinator-state.json
node --disable-wasm-trap-handler --max-old-space-size=256 \
    "$INTEGRATION_DIR/prototype/.build/node/src/local/main.js"
```

`.env.local` is scratch-local: keep it out of Git and regenerate it per stack
session instead of reusing stale tokens.

#### Two tokens, two authorization planes

Do not conflate the two credentials this stack uses:

- `$SIDECAR_TOKEN` is the **shared sidecar control bearer**: it authorizes
  sidecar control-plane calls (creating canonical repos via `POST /setup`)
  and is what the coordinator presents as `LOCAL_ARTIFACTS_TOKEN`. It is not
  the credential Git Smart HTTP accepts for push.
- The **minted repo write token** returned in the `POST /setup` response
  (`token` field; per-repo, short-lived) — or a task token minted for the
  same repo — is what Git Smart HTTP push requires. It belongs to the repo or
  task that requested it; keep it out of `.env.local`.

#### Pushing work to a canonical repo: exact seed lease

The sidecar's `createRepo()` initializes every canonical bare repo with a
synthetic seed commit (`chore: seed canonical baseline` on `main`) and returns
its SHA as `seedCommit` next to the remote URL and a minted write token. A
freshly created canonical repo is therefore **not** empty: pushing your
unrelated local history (e.g. a branch based on `b2df985`) is a
non-fast-forward. Do **not** recover with an unconstrained `git push --force`
— that silently clobbers anything any other actor lands on `main`. Push with
an exact lease on the seed commit instead:

```bash
# Create the canonical repo on the control plane; the JSON response carries
# remote (canonical URL), seedCommit (seed SHA) and token (repo write token).
sidecar_bearer="Bearer $SIDECAR_TOKEN"   # scheme + control credential, composed once
setup_resp=$(curl -fsS -X POST "http://127.0.0.1:$SIDECAR_PORT/setup" \
    -H "Authorization: $sidecar_bearer" \
    -H 'Content-Type: application/json' \
    -d '{"name":"my-task-repo"}')
seed_sha=$(printf '%s' "$setup_resp" | python3 -c 'import sys, json; print(json.load(sys.stdin)["seedCommit"])')
repo_url=$(printf '%s' "$setup_resp" | python3 -c 'import sys, json; print(json.load(sys.stdin)["remote"])')
repo_tok=$(printf '%s' "$setup_resp" | python3 -c 'import sys, json; print(json.load(sys.stdin)["token"])')
# jq equivalents: seed_sha=$(printf '%s' "$setup_resp" | jq -r .seedCommit), etc.

# Push with the exact lease on the seed commit, authenticated as the minted
# repo write token $repo_tok (0600 file-backed variant below — never argv
# on multi-user hosts):
git push --force-with-lease=refs/heads/main:"$seed_sha" \
    "$repo_url" HEAD:refs/heads/main
```

This succeeds only while canonical `main` still points at `seed_sha`. If
another actor advanced it, git rejects the push (`stale info`) and the
canonical ref is preserved untouched — the failure is closed, not a clobber.

On rejection, recover through ordinary Git integration — never by
force-replacing arbitrary history: fetch the canonical ref, inspect what
landed (`git log`, `git diff`), then rebase or cherry-pick your local work
on top of the advanced canonical `main` and push the integrated result as a
normal fast-forward, with no force flags at all. Re-leasing against a fresh
SHA is only conceivable when you verifiably own the canonical history (e.g.
a coordinated recovery to a known-good state), and the displaced commits
must be preserved, never discarded.
(Verified with git 2.43: lease-at-seed succeeds against a freshly seeded
canonical repo; the same lease after the ref advanced is rejected and the
advanced commit survives.)

#### Token hygiene: argv exposure on multi-user hosts

Tokens passed on a command line are readable by every local user while the
process runs, via `ps aux` and `/proc/<pid>/cmdline`. This applies to
`curl -H` with a composed bearer header, `git -c http.extraHeader=… push`,
and the
`--token` / `--admin-token` CLI flags. Single-user scratch runs can accept
this; on multi-user hosts prefer mode `0600` files over argv:

```bash
# Git: persist the header in the repo config once (file-backed, not per-command
# argv). Use the minted repo write token here — the control bearer $SIDECAR_TOKEN
# is not accepted by Git Smart HTTP push.
umask 077
repo_bearer="Bearer $repo_tok"   # scheme + minted repo write token
git config --local http.<remote-url>.extraHeader "Authorization: $repo_bearer"
chmod 600 .git/config

# curl: read options from a 0600 config file instead of -H
umask 077
sidecar_bearer="Bearer $SIDECAR_TOKEN"   # scheme + control credential
printf 'header = "Authorization: %s"\n' "$sidecar_bearer" > .curl-scratch
curl -K .curl-scratch https://sidecar.example.invalid/...
```

Residual gap, stated honestly: the single `git config` / `printf` invocation
itself carries the token in argv for its brief runtime. For strict zero-argv
setups, write the config file in an editor instead.

## License

MIT — see [LICENSE](LICENSE).

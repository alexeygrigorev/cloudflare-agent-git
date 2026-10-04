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

## License

MIT — see [LICENSE](LICENSE).

# Receipt: Supervision Source Manifest, Dynamic Reload & Multi-Repo Metrics (C3110 / C3111 / Human Intake)

- **Date:** 2026-10-07T05:43:00Z (07:43 CEST)
- **Session Identity:** `ant-head-gap-recovery-20261007` (`cfdc18a9-0946-4770-8aee-cf50a35bfaa7`)
- **Parent Principal:** `codex-principal` (`93cf28f2-2872-411c-a5da-179e1b83b59f`)
- **Desktop Orchestrator:** `desktop-orchestrator` (`79ffb8c7-3f32-46ee-bd60-423a255ebbae`)
- **Declared Scopes:** `research/antigravity/recovery/**`, `research/antigravity/reviews/**`, `scripts/supervision/**`, `scripts/metrics/**`
- **Associated Tasks:**
  - `t-supervision-idle-wake-and-failover-c3110`
  - `t-continuation-runtime-collector-c3111`
  - `human-tracker-availability-agents-commits-20261007`

---

## 1. Problem & Gap Addressed
1. **Supervision Runtime Source Verification Gap (`source32bc`)**:
   - `scripts/supervision/service.py` previously generated `binary-manifest.json` solely for the CLI binary (`/home/alexey/.local/bin/aplexer`), with zero immutable evidence or tracking of its own loaded Python source or imported modules.
   - Long-running `supervision.service` daemon processes could execute stale in-memory bytecode across code updates.
   - Furthermore, `service.py` checked if the CLI binary changed on disk in its main loop, but did not monitor if its own Python source or `failover_integration.py` changed on disk.
2. **Human Direct Intake (7 October 2026)**:
   - "make sure all my requests are stored in the tracker, this tracker is always available, and we're tacking the process though the tasks, track the number of running agents, and the number of commits we're making".
   - Required truthful, deduplicated telemetry on:
     * Current live running agents (registered vs unregistered, active working vs idle/waiting, provider and role breakdown).
     * Reachable git commit counts and unique commit SHAs across all 5 competition repositories (`cloudflare-agent-git`, `agent-branches`, `agent-dashboard`, `agent-quota-launcher`, `agent-bus`) with hourly Berlin breakdown.

---

## 2. Technical Remediation Executed

### A. Supervision Source Manifest & Dynamic Change Detection (`scripts/supervision/service.py`)
1. **Loaded Source Manifest Generation**:
   - Added startup SHA-256 calculation for `service.py` and `failover_integration.py`.
   - Generates and writes `.local/supervision/source-manifest.json` containing:
     * `service_path`: absolute path to loaded `service.py`.
     * `service_sha256`: SHA-256 digest of loaded file (`f130d8ae5298...`).
     * `failover_path`: absolute path to loaded `failover_integration.py`.
     * `failover_sha256`: SHA-256 digest of loaded file (`a6556d6454d2...`).
     * `loaded_at`: ISO-8601 UTC timestamp.
     * `authority`: `"canonical supervision runtime source proof"`.
2. **Lifecycle Event & Status Provenance**:
   - Updated `service-started` event emission in `.local/supervision/events.jsonl` to publish `service_sha256` and `failover_sha256` alongside `binary_sha256`.
   - Included `source_sha256` in the service status report dictionary.
3. **Fail-Closed On-Disk Source Change Detection**:
   - In the supervisor main evaluation loop:
     * Evaluates `same_source` and `same_failover`.
     * If on-disk source changes, raises `RuntimeError('supervision service source changed on disk: restart service to load reviewed code')`, terminating the process cleanly and prompting the supervisor harness/systemd manager to restart with fresh reviewed code.
4. **Dynamic Module Reload**:
   - In `run_failover_tick` caller, uses `importlib.reload(failover_integration)` to guarantee in-memory module synchronization.

### B. Live Running Agents & Commit Metrics Collector (`scripts/metrics/export.py`)
1. **`summarize_running_agents(store_dir=STORE, as_of=None, latest_data=None)`**:
   - Parses `.local/metrics/latest.json`.
   - Computes:
     * `total_running_agents`: count of active PIDs.
     * `registered_live_count`: count of active registered agents from `TEAM-REGISTRY.json`.
     * `unregistered_live_count`: count of unregistered active processes.
     * `active_working_count`: count of agents reporting state `working`.
     * `idle_waiting_count`: count of agents reporting state `idle` or `waiting`.
     * `by_role`: `{role: count}` breakdown.
     * `by_provider`: `{engine: count}` breakdown.
     * `by_team`: `{team_id: count}` breakdown.
     * `deduplicated_agent_ids`: list of distinct active session/actor IDs.
     * Explicit truthfulness limitations.
2. **`summarize_commits(window_seconds=86400, as_of=None, repos=None)`**:
   - Covers the 5 core competition repositories:
     * `cloudflare-agent-git` (`/home/alexey/git/cloudflare-agent-git`)
     * `agent-branches` (`/home/alexey/git/agent-branches`)
     * `agent-dashboard` (`/home/alexey/git/agent-dashboard`)
     * `agent-quota-launcher` (`/home/alexey/git/agent-quota-launcher`)
     * `agent-bus` (`/home/alexey/git/agent-bus`)
   - Computes unique commit SHAs reachable within the specified window (default 24h).
   - Generates hourly commit distribution in Europe/Berlin (CEST, UTC+2) time per repository.
   - Calculates `total_unique_commits` deduplicated across all repositories.
3. **CLI Options Added**:
   - `--running-agents`: prints structured or JSON running agents summary.
   - `--commits`: prints structured or JSON competition commit metrics.

---

## 3. Verification & Acceptance Evidence

### A. Automated Unit Test Suites
1. **`scripts/metrics/test_export.py`**:
   - 30/30 tests passing in 0.441s (`TestRunningAgentsAndCommits`, `TestResolvedTasksNumeratorExclusion`, `TestResolvedTasksFileLoading`, etc.).
2. **`scripts/supervision/test_service.py`**:
   - 55/55 tests passing (`test_source_manifest_and_change_detection`, `test_delivery_diagnostic_hold_cooldown`, `Safety`, etc.).
3. **`scripts/supervision/test_failover_integration.py`**:
   - 4/4 tests passing in 0.048s.
4. **`research/antigravity/recovery/test_installed_safeidle_matrix.py`**:
   - 6/6 tests passing in 0.313s against `/home/alexey/.local/bin/aplexer`.

### B. Live Runtime Restart & Verification
- `supervision.service` restarted via `systemctl --user restart supervision.service`.
- Spawned into fresh aplexer session `2c303bcb-7163-4caa-8dc2-2a2ec96b42b7` (PID `1697442`).
- Generated valid `.local/supervision/source-manifest.json`:
  * `service_sha256`: `f130d8ae52982e542c71df1e4dd6147a6d9a02277345fdeae6d0ec7a42fa23d0`
  * `failover_sha256`: `a6556d6454d2d87511c0c5290289fd095f3933c836531a59f4f295b1b6c6d81c`
- Verified live command output:
  * `python3 scripts/metrics/export.py --running-agents --json` -> 14 running agents (6 registered live, 8 unregistered live, 3 active working, 7 idle/waiting).
  * `python3 scripts/metrics/export.py --commits --window 24h --json` -> 325 total unique commits across 5 repositories (cloudflare: 201, branches: 87, launcher: 27, bus: 10, dashboard: 0).

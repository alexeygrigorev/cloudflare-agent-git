# Deploy-Readiness Evaluation: Win35 Non-SSH Secure Endpoint Candidate (C3123)

## 1. Executive Summary & Candidate Pin
- **Candidate Commit**: `e1e8e50fc828f4d65060707bce0c0b4c31d6372e`
- **Candidate Branch**: `bus-win35-endpoint-3273594b`
- **Worktree Location**: `/home/alexey/git/agent-bus/.local/wt-win35-endpoint-3273594b`
- **Evaluating Agent**: `ant-head-oom-recovery-c3123-20261007` (`1c0dfcf7-3431-4c7b-bec3-8412c09e1ac1`)
- **Authority Scope**: Bounded deploy-readiness evaluation in isolated runtime paths (`research/antigravity/recovery/**`); zero modification to `agent-bus` canonical source and zero assumption of Bus task acceptance or source leases.

## 2. Artifact Integrity Verification
The immutable candidate artifacts in the isolated worktree were verified:
- `adapter/adapter.py`: SHA256 `74ae6dff512ae09fbad909a72bd521f5598d44754238a63ffeef9ded9848074d`
- `tools/make-certs.sh`: SHA256 `b258a1faed0fab1db76725076361720afe876ea609f820ca7e7a213eceb49556`
- `tests/e2e_win35_endpoint.py`: SHA256 `4ebe24b7fb375af8b1ee73478b97bfd81f437f4217cb121d94f44c6d04dd3640`
- `DEPLOY-NOTES.md`: Confirmed present at `.local/codex/bus-win35-resume-3273594b/DEPLOY-NOTES.md` (2,834 bytes).
- `IMPLEMENTATION-LOG.md`: Confirmed present at `.local/codex/bus-win35-resume-3273594b/IMPLEMENTATION-LOG.md` (9,278 bytes).
- `REV-BUS-ENDPOINT-IMPL-01-20261007.md`: Confirmed present at `.local/codex/bus-win35-resume-3273594b/REV-BUS-ENDPOINT-IMPL-01-20261007.md` (3,523 bytes).

## 3. Code Audit & Security Controls
Audited `adapter/adapter.py` against required security controls:
1. **Mutual TLS Enforcement**:
   - Uses `ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)`.
   - Requires client certificates via `ssl.CERT_REQUIRED`.
   - Rejects unauthenticated connections at the TLS handshake level.
2. **Server-Side Allowlist by Cert Fingerprint**:
   - `_verify_allowlist` maps client certificate SHA256 DER fingerprint to permitted `device_id` and `project_id` scopes.
   - Enforced on all incoming requests before payload processing.
3. **Idempotent Operations & Replay Defense**:
   - `POST /v1/send` evaluates `idempotency_key` and returns HTTP 409 Conflict upon duplicate submission.
4. **Distinct Lifecycle Endpoints**:
   - Read acknowledgment (`POST /v1/ack`) is strictly decoupled from semantic acceptance (`POST /v1/accept`) and task completion (`POST /v1/complete`).
5. **No Parallel Listener or Unauthenticated Exposure**:
   - Server defaults to binding only with valid TLS context; plain HTTP is strictly fenced behind `--insecure-loopback` for offline testing.

## 4. Analysis of Failed Worker and Reviewer Rows
- **Observed State**: Worker task `bus-win35-endpoint-impl-01` and reviewer task `bus-win35-endpoint-impl-review-01b` are marked FAILED in the launcher database.
- **Root Cause Diagnosis**:
  - The worker and reviewer workloads wrote outputs to `.local/codex/bus-win35-resume-3273594b/` but failed to emit the standard required `receipt.json` inside their designated execution working directory (`cwd`).
  - Under the launcher receipt contract, task completion requires an authentic `receipt.json` in `cwd`.
- **Preservation Contract**:
  - These failures are genuine contract misses under standard execution rules.
  - Failures are preserved in historical telemetry; they are NOT labeled as "watcher bugs" without proof, nor are they artificially force-completed.

## 5. Host Runtime Inspection & Collision Prevention
To prevent duplicate brokers or port collisions:
- **Port Inspection**: `ss -tlnp` confirms port `8788` is completely free (no active listener).
- **Storage Inspection**: Directory `/home/alexey/.local/share/agent-bus-win35/store` does not exist.
- **Process Check**: No competing adapter instances or orphaned test processes are running.

## 6. Physical Deployment Boundaries & Prerequisites
- **Review Report != Physical Deployment**:
  - The local review report (`REV-BUS-ENDPOINT-IMPL-01-20261007.md`) confirms implementation quality and loopback test passage, but does NOT constitute physical Win35 deployment.
- **Deployment Prerequisites**:
  1. Real CA, server, and client certificates must be generated into restricted `0700`/`0600` directories (`/home/alexey/.local/share/agent-bus-win35/secrets`).
  2. Device enrollment allowlist must be populated with genuine client certificate SHA256 fingerprints.
  3. Systemd user service `agent-bus-win35-adapter.service` must be provisioned under unprivileged user execution with `MemoryMax=300M`.
  4. Root must conduct a reviewed device bootstrap.
- **SSH Transport Fencing**:
  - Outbound Win35 transport relies entirely on mutual TLS over HTTPS; an SSH alias is explicitly **NOT** a prerequisite for deployment.

## 7. Conclusion & Next Ownership Handoff
- Candidate `e1e8e50` is architecturally and cryptographically ready for controlled physical deployment.
- Ant head maintains strict boundary enforcement: no modification to `agent-bus` source, no assumption of Bus task acceptance, and no uncoordinated deployment actions.
- Full readiness receipt preserved for Bus head (`3273594b`) and codex-principal (`93cf28f2`).

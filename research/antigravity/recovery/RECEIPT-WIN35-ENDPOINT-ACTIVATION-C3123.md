# Win35 Endpoint Live Activation & Verification Receipt (C3123)

## 1. Executive Summary & Service Provenance
- **Service Name**: `agent-bus-win35-adapter.service`
- **Unit Configuration**: `~/.config/systemd/user/agent-bus-win35-adapter.service`
- **Service CGroup**: `/user.slice/user-1000.slice/user@1000.service/app.slice/agent-bus-win35-adapter.service`
- **Limits**: `MemoryMax=300M`, `TasksMax=50` (unprivileged execution)
- **Main PID**: `3743626`
- **Bound Address & Port**: `127.0.0.1:8788` (verified listening via `ss -tlnp`)
- **Base Endpoint URL**: `https://127.0.0.1:8788/v1`
- **Candidate Source**: Immutable commit `e1e8e50fc828f4d65060707bce0c0b4c31d6372e` in worktree `/home/alexey/git/agent-bus/.local/wt-win35-endpoint-3273594b`
- **Store Path**: `/home/alexey/.local/share/agent-bus-win35/store` (mode 0700)
- **Secrets Directory**: `/home/alexey/.local/share/agent-bus-win35/secrets` (mode 0700/0600)
- **Canonical Leases**: Strict preservation of Bus source leases; zero mutations to `agent-bus` canonical main.

## 2. Live Runtime Verification Results (10/10 PASS)
Direct live tests were executed against the active endpoint:
1. **Negative 1 (TLS Handshake - No Client Certificate)**:
   - Expected: Connection failure during mutual TLS handshake.
   - Result: `PASS` (`SSLError [SSL: TLSV13_ALERT_CERTIFICATE_REQUIRED] tlsv13 alert certificate required`).
2. **Negative 2 (Allowlist - Unauthorized Client Certificate)**:
   - Expected: HTTP 403 Forbidden.
   - Result: `PASS` (`HTTP 403: {"status": "error", "detail": "Cert fingerprint not allowed"}`).
3. **Negative 3 (Scope Enforcement - Out-of-Scope Project)**:
   - Expected: HTTP 403 Forbidden.
   - Result: `PASS` (`HTTP 403: {"status": "error", "detail": "Project scope forbidden-project not allowed"}`).
4. **Positive 4 (Client Registration)**:
   - Request: `POST /v1/register` (`win35-device-01`, `win35-agent`, `agent-bus-project`).
   - Result: `PASS` (`HTTP 201 Created`, returned `token: f33ff033-5387-4b7c-9200-ffbbc6b989d6`, `identity_id: c212ede3-276c-4020-a443-876d34211f7a`).
5. **Positive 5 (Send Message)**:
   - Request: `POST /v1/send` with `idempotency_key: win35-key-001`.
   - Result: `PASS` (`HTTP 200 OK`, envelope ID `ae882ca9-0f65-4194-906e-6e765da06dd0`).
6. **Negative 6 (Idempotency Replay Defense)**:
   - Request: `POST /v1/send` replaying `idempotency_key: win35-key-001`.
   - Result: `PASS` (`HTTP 409 Conflict: {"status": "error", "detail": "Replay detected"}`).
7. **Positive 7 (Poll Inbox)**:
   - Request: `GET /v1/inbox?identity_id=...&token=...`.
   - Result: `PASS` (`HTTP 200 OK`, returned 1 message matching envelope `ae882ca9...`).
8. **Positive 8 (Read Acknowledgment)**:
   - Request: `POST /v1/ack`.
   - Result: `PASS` (`HTTP 200 OK`, `acked_at` timestamp recorded).
9. **Positive 9 (Semantic Acceptance)**:
   - Request: `POST /v1/accept`.
   - Result: `PASS` (`HTTP 200 OK`, `accepted_at` timestamp recorded).
10. **Positive 10 (Task Completion)**:
    - Request: `POST /v1/complete` with `status: completed`.
    - Result: `PASS` (`HTTP 200 OK`, `outcome.status: completed` recorded).

## 3. Due Callback 06:50 UTC Delivery Confirmation
- **Callback ID**: `bus327-due-0650`
- **Target Session**: `3273594b-3244-45f6-87af-a6a72af7acb4` (`zcode-bus-win35-recovery-head-20261006-resume`)
- **Delivery Timestamp**: `2026-10-07T06:50:19.179723+00:00`
- **Aplexer Receipt ID**: `01a11520-93de-7f70-8777-0ebff67e2aef`
- **Status**: Delivered cleanly to the Bus head inbox on schedule.

## 4. Recipient Epoch Validation Added
- Added `recipient_epoch` / `created_at_ms` validation in `scripts/supervision/service.py`.
- Rejects callback delivery if the session's generation epoch does not match `recipient_epoch`.
- Verified by unit tests in `scripts/supervision/test_service.py`.
- Pushed in commit `cc1c58a`.

## 5. Head Cgroup Memory Stabilization
- Terminated all completed/idle native subagents (`f43568dc`, `a16a8479`, `5a973203`).
- Current head cgroup memory dropped from 1,555 MB to 1,451 MB. OOM count = 0.
- Zero subagents currently running in head scope; all future executor tasks route into independently bounded systemd transient units.

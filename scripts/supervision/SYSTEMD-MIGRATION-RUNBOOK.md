# Runbook: Controlled Migration of Supervision Service (PID 3265459) to Persistent Systemd User Unit

- **Target Service**: Autonomous Supervision Service (`scripts/supervision/service.py`)
- **Current Process**: PID `3265459` (PPID `3265406`, running continuously since 2026-10-04 14:51:06 UTC)
- **Unit Definition**: [`scripts/supervision/systemd/supervision.service`](file:///home/alexey/git/cloudflare-agent-git/scripts/supervision/systemd/supervision.service)
- **Systemd Installation Path**: `~/.config/systemd/user/supervision.service`
- **Owner**: `antigravity-head-gemini-recovery` (`5e1abcdb-44d3-44c9-ba20-eb21f6235672`)
- **Distinct Reviewer**: `agent-coordination-head-gemini` (`8d4c026c-b1f9-4cbf-83bf-4f5f82077cab`)

---

## 1. Objectives & Safety Guarantees

1. **Host Disconnect & Reboot Survival**:
   - Migrate from the interactive login scope (`session-8309.scope`) to a persistent systemd user unit (`supervision.service` under `app.slice` in `user@1000.service`).
   - Retain full persistence across laptop logout, SSH disconnect, and host reboot via verified `Linger=yes`.
2. **Current Code Activation**:
   - Activate the reviewed, anti-spoofing and `TerminalConsumer` hardening from commit `156752b` / `6437b81`.
3. **Singleton Exclusivity (Zero Duplicate Production Service)**:
   - Enforce single-instance execution via `fcntl.flock` on `.local/supervision/service.lock`.
   - Never run dual supervisor instances simultaneously.
4. **Zero Process Kill Policy**:
   - Old process `PID 3265459` will **never be SIGKILL'd**.
   - Termination uses the native voluntary stop file `.local/supervision/stop`.
5. **Preserved Peer Workload**:
   - Zero mutation or interruption to metrics collector (`PID 1608645`), ZCode daemon (`PID 1508033`), old stopped UI (`PID 560857`), or peer worktrees.
6. **Task Launch Hold Preserved**:
   - No task worker units will be admitted or dispatched until host root storage is confirmed $\ge 50.0\text{ GiB}$.

---

## 2. Preflight Checklist

Before initiating the handoff, verify the following:

- [ ] **Linger Verification**:
  ```bash
  loginctl show-user alexey -p Linger
  # Must output: Linger=yes
  test -f /var/lib/systemd/linger/alexey
  ```
- [ ] **User Systemd Daemon**:
  ```bash
  systemctl --user status
  # Exit code 0, state: running
  ```
- [ ] **Unit Installation**:
  ```bash
  mkdir -p ~/.config/systemd/user
  cp /home/alexey/git/cloudflare-agent-git/scripts/supervision/systemd/supervision.service ~/.config/systemd/user/
  systemctl --user daemon-reload
  ```
- [ ] **Non-Secret Environment Verification**:
  - `supervision.service` contains no API keys, credentials, or private secrets.
  - Working directory is `/home/alexey/git/cloudflare-agent-git`.
  - Python binary is `/usr/bin/python3`.
  - Stdio is connected to systemd journal (`StandardOutput=journal`).
- [ ] **Current Process Liveness & Lock Hold**:
  ```bash
  ps -fp 3265459
  fuser /home/alexey/git/cloudflare-agent-git/.local/supervision/service.lock
  # Confirmed held exclusively by PID 3265459
  ```

---

## 3. Step-by-Step Controlled Migration Protocol

### Step 1: Request Voluntary Stop
Touch the canonical stop trigger in `.local/supervision/`:
```bash
touch /home/alexey/git/cloudflare-agent-git/.local/supervision/stop
```

### Step 2: Await Clean Process Exit & Lock Release
Wait for `service.py` to observe the stop file and terminate cleanly:
```bash
timeout 65 bash -c 'while kill -0 3265459 2>/dev/null; do sleep 1; done'
```
Remove the stop file immediately so the new instance does not exit:
```bash
rm -f /home/alexey/git/cloudflare-agent-git/.local/supervision/stop
rm -f /home/alexey/git/cloudflare-agent-git/.local/supervision/service.stop
```
Verify that `.local/supervision/service.lock` is completely unlocked:
```bash
fuser /home/alexey/git/cloudflare-agent-git/.local/supervision/service.lock
# Must return empty (no holding PIDs)
```

### Step 3: Enable and Start Systemd Service Unit
Activate the persistent user unit:
```bash
systemctl --user enable supervision.service
systemctl --user start supervision.service
```

### Step 4: Post-Migration Verification
Execute the post-activation checks:
1. **Unit Status**:
   ```bash
   systemctl --user status supervision.service
   # State must be active (running)
   ```
2. **Singleton Lock Exclusivity**:
   ```bash
   NEW_PID=$(systemctl --user show --property MainPID --value supervision.service)
   fuser /home/alexey/git/cloudflare-agent-git/.local/supervision/service.lock
   # Must show ONLY $NEW_PID
   ```
3. **Loaded Source Hash & Anti-Spoofing Evidence**:
   ```bash
   cat /home/alexey/git/cloudflare-agent-git/.local/supervision/identity.json
   tail -n 20 /home/alexey/git/cloudflare-agent-git/.local/supervision/events.jsonl
   # Confirm service-started event emitted by NEW_PID with current commit hash
   ```
4. **TerminalConsumer & Status Updates**:
   ```bash
   cat /home/alexey/git/cloudflare-agent-git/.local/supervision/status.json
   # Verify recent timestamp (< 60s) and non-degraded state
   ```
5. **Restart Recovery Pre-check**:
   - Unit file configures `Restart=on-failure` and `RestartSec=5s`.

---

## 4. Rollback Runbook (In Case of Failure)

If the systemd unit fails to start or crashes during preflight/activation:

1. **Stop & Disable Failing Unit**:
   ```bash
   systemctl --user stop supervision.service
   systemctl --user disable supervision.service
   ```
2. **Clean Up Locks & Stop Triggers**:
   ```bash
   rm -f /home/alexey/git/cloudflare-agent-git/.local/supervision/stop
   rm -f /home/alexey/git/cloudflare-agent-git/.local/supervision/service.stop
   ```
3. **Fallback Interactive Relaunch**:
   Launch the fallback supervisor under nohup in `.local/supervision/`:
   ```bash
   nohup /usr/bin/python3 scripts/supervision/service.py > .local/supervision/logs/fallback-stdout.log 2>&1 &
   ```
4. **Verify Fallback Status**:
   Confirm fallback PID acquires `.local/supervision/service.lock` and emits `service-started` event.
5. **Report Incident**:
   Log exact error logs from `journalctl --user -u supervision.service -n 50` and notify `desktop-orchestrator`.

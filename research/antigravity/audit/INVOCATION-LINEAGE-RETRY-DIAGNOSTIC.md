# Invocation Lineage & Outer Retry Diagnostic: Forensic Audit of Session Z4abc (`4abc725c`)

**Author:** `antigravity-lineage-auditor`  
**Directives:** Codex Principal C1681 / Parent Session `antigravity-head` (`46fdb644-9b58-4e2f-aab3-9be5e1e33337`, harness `245c7bba-9a7b-45c1-87a7-4537f289f9a5`)  
**Target Session:** `zcode-recovery-test` (`4abc725c-b6ef-4ae6-af9c-978c31cdf151`)  
**Target Rollout:** `~/.zcodex/sessions/2026/10/04/rollout-2026-10-04T01-26-46-01a10417-6d8a-71a0-b347-7bcc1ec2d90f.jsonl`  
**Target Scratch Worktree:** `/home/alexey/git/agent-branches-recovery/.local/scratch/db4-ack-verify/`  
**Date:** 2026-10-04 (Europe/Berlin)  
**Publication Status:** Clean / Public Sanitized (Checked via `publication_guard.py`)  
**Unredacted Technical Companion:** `.local/scratch/private-lineage-audit/retry-diagnosis.unredacted.json` (mode `0600`)

---

## 1. Executive Summary & Core Forensic Conclusions

Under Codex Principal directive C1681, this forensic investigation examined the anomalies reported by worker session Z4abc (`4abc725c`, `zcode-recovery-test`) operating in `/home/alexey/git/agent-branches-recovery`:
1. Duplicate Sidecar request traces emitting identical timestamps down to the millisecond (`[trace] GET /api/health at 2026-10-04T04:45:13.163Z` twice).
2. Reports of a "duplicate Sidecar probe: one create log versus 409 conflict" on fresh repository names.
3. Coordinator setup failing with `[int-err] fetch failed` (HTTP 500) during outbound calls to the local Sidecar.
4. The agent's resulting hypothesis (rollout line 1918): *"Root cause found: every request through this environment's network layer is delivered twice... That explains the 409-on-create: first execution creates, duplicate 409s, and curl is handed the second response."*

### Core Verdict: The "Network Delivers Every Request Twice" Hypothesis is REFUTED

Forensic analysis of the 4.07 MB rollout log, process execution traces, filesystem inode metadata, and Node.js runtime internals demonstrates that **no duplicate network delivery, curl retry, or harness double-send occurred**. 

The observed phenomena stem from four distinct, fully reproducible mechanisms:

| Phenomenon | Z4abc Inferred Cause | Actual Root Cause | Forensic Evidence |
| :--- | :--- | :--- | :--- |
| **Identical Millisecond Traces (`04:45:13.163Z` twice)** | Network layer delivering HTTP packets twice | **Self-inflicted instrumentation bug**: A non-idempotent Python substitution script in line 1897 inserted duplicate `console.error` logging calls into `sidecar.mjs` lines 567–568. | File `prototype/local-artifacts/sidecar.mjs` lines 567–568 contains two consecutive identical logging statements. Single HTTP GET executes both lines synchronously in one tick. |
| **409 Conflict on Repository Creation** | Duplicate request hitting Sidecar and getting 409 | **Model perception / reasoning hallucination**: Sidecar returned `HTTP 200` and `HTTP 201` creating the repositories. The model misread the stdout and hallucinated 409s. | Rollout lines 1864 and 1874 stdout show clean `HTTP 200` and `HTTP 201` creation payloads with seed commits. No 409 occurred on create. |
| **Coordinator Outbound `fetch failed` (HTTP 500)** | Network transmission drops or socket exhaustion | **WebAssembly virtual memory exhaustion**: Node.js 24's global `fetch` (undici) initializes WebAssembly, requiring multi-GB virtual address space reservations. | Rollout line 1955 underlying cause: `WebAssembly.Instance(): Out of memory: Cannot allocate Wasm memory for new instance`. Triggered by `ulimit -v 1500000`. |
| **Protocol 409 on `/checks`** | Duplicate execution hitting stale gate | **Protocol contract specification**: `POST /checks` validates submitted head vectors against current coordinator state. | Defined in `prototype/CONTRACT.md` (lines 273, 373). `bootstrap.py` submitted moved heads; coordinator returned 409 Conflict as specified. |
| **Process / Lineage Multi-Wire Belief** | External phantom executor operating concurrently | **Single-parent process ancestry with confirmation bias**: Primed by line 175 when the agent mistook its own `git clone` success output for an external actor. | All listeners had PPID 2937905 (zcodex runner), executed inside cgroup `aplexer-workload-4abc725c`. Zero foreign actors. |

---

## 2. Forensic Analysis 1: The Identical-Millisecond Trace Investigation

### 2.1 The Observed Symptom

In rollout line 1916 (`2026-10-04T04:45:10.999Z`), worker Z4abc restarted the Sidecar and executed a single `curl` probe:
```bash
curl -sS -m 5 -H "Authorization: Bearer <token>" "http://127.0.0.1:$NEWPORT/api/health" -w "\nHTTP %{http_code}\n"
echo "=== traces:"; grep -c trace "$SCRATCH/logs/sidecar.log"; grep trace "$SCRATCH/logs/sidecar.log"
```

The resulting log output in `$SCRATCH/logs/sidecar.log` contained two identical lines:
```text
[trace] GET /api/health at 2026-10-04T04:45:13.163Z
[trace] GET /api/health at 2026-10-04T04:45:13.163Z
```

In line 1918 (`2026-10-04T04:45:44.178Z`, `msg_01a1053b-6692-7450-83df-c335f8827c80`), the assistant concluded:
> *"Root cause found: every request through this environment's network layer is delivered twice (two identical-millisecond trace lines for one curl). That explains the 409-on-create: first execution creates, duplicate 409s, and curl is handed the second response."*

### 2.2 Forensic Autopsy of the Code Mutation

To determine how the Sidecar produced this trace, we inspected the code on disk at `/home/alexey/git/agent-branches-recovery/.local/scratch/db4-ack-verify/prototype/local-artifacts/sidecar.mjs`.

Lines 562–570 read:
```javascript
export function createSidecarServer(sidecar) {
  return createServer(async (req, res) => {
    try {
      const url = new URL(req.url, "http://127.0.0.1");
      const path = decodeURIComponent(url.pathname);
      console.error(`[trace] ${req.method} ${req.url} at ${new Date().toISOString()}`);
      console.error(`[trace] ${req.method} ${req.url} at ${new Date().toISOString()}`);

      const gitMatch = /^(?:\/git)?\/([A-Za-z0-9][A-Za-z0-9._-]*)\.git\/(info\/refs|git-upload-pack|git-receive-pack)$/.exec(path);
```

**The code itself contains two consecutive identical `console.error` calls.**

### 2.3 The Non-Idempotent Substitution Mechanism

In rollout line 1897 (`2026-10-04T04:43:02.942Z`, `fc_01a1053a-6744-7f41-bb0a-814d4586d6fe`), executed at line 1898 (`zcode_tool_call_7b1c952dc3fe48fdbeee0aa9`), the agent attempted to instrument `sidecar.mjs` using the following inline Python script:

```python
import re
p = "sidecar.mjs"
src = open(p).read()
old = "      const url = new URL(req.url, \"http://127.0.0.1\");\n      const path = decodeURIComponent(url.pathname);\n"
assert src.count(old) == 1, src.count(old)
new = old + "      console.error(`[trace] ${req.method} ${req.url} at ${new Date().toISOString()}`);\n"
open(p, "w").write(src.replace(old, new))
print("instrumented")
```

#### The Algorithmic Flaw:
1. The target replacement string `new` was constructed as `old + "      console.error(...)\n"`.
2. Notice that `old` **remains intact at the beginning of `new`**.
3. Consequently, after the first substitution, the file still contains the exact sequence defined by `old`.
4. Therefore, on any subsequent execution or re-entry of the script, `src.count(old)` **still evaluates to 1**.
5. When `src.replace(old, new)` runs against a file that already has the instrumentation, it finds the single instance of `old` (which immediately precedes the existing `console.error`) and replaces it with `old + console.error`.
6. This injects a **second** identical `console.error` directly below the first one.

### 2.4 Synchronous Execution Proof

When curl made a single HTTP request to `http://127.0.0.1:$NEWPORT/api/health`, the Node.js HTTP server invoked `createServer(async (req, res) => ...)`:
- Line 567 executed: `console.error(...)` evaluated `new Date().toISOString()`, emitting `2026-10-04T04:45:13.163Z`.
- Line 568 executed immediately on the very next CPU instruction within the same synchronous tick: `new Date().toISOString()` evaluated to the identical millisecond `2026-10-04T04:45:13.163Z`.
- Both lines were flushed to `logs/sidecar.log`.

**Conclusion:** The dual trace was not caused by two network packets. It was the synchronous execution of two identical lines of logging code within a single HTTP request handler tick.

---

## 3. Forensic Analysis 2: Repository Creation Probes & The 409 Conflict Mirage

The agent claimed in line 1880 and line 1918 that creating repositories returned 409 Conflict on fresh repository names due to duplicate request delivery.

We performed a line-by-line inspection of all repository creation requests in the rollout log.

### 3.1 Probe 1: `probe-canonical-ztest` (Rollout Lines 1863–1864)

- **Timestamp:** `2026-10-04T04:39:19.832Z`
- **Command:**
  ```bash
  curl -sS -m 10 -X POST -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
    -d '{"name":"probe-canonical-ztest","defaultBranch":"main"}' \
    "http://127.0.0.1:$PORT/api/repos"
  ```
- **Actual Response in Rollout Line 1864:**
  ```json
  {
    "name": "probe-canonical-ztest",
    "remote": "http://127.0.0.1:48099/git/probe-canonical-ztest.git",
    "defaultBranch": "main",
    "token": "[REDACTED_TOKEN]",
    "seedCommit": "9b44105cea1c138d0af35a950e92fd951a8ce82c"
  }
  ```
- **HTTP Status:** `200 OK` / `201 Created`. The repository was created cleanly on disk.
- **Model Reaction (Line 1866):**
  > *"repo already exists" on a fresh name means something's off — inspecting what's on disk in the sidecar root and how createRepo names dirs.*
- **Forensic Fact:** The server never output "repo already exists". The output was valid JSON containing `seedCommit: 9b44105c...`. The model hallucinated the conflict message.

### 3.2 Probe 2: `probe-two-ztest` (Rollout Lines 1873–1874)

- **Timestamp:** `2026-10-04T04:40:51.364Z`
- **Command:**
  ```bash
  curl -sS -m 10 -X POST -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
    -d '{"name":"probe-two-ztest","defaultBranch":"main"}' \
    "http://127.0.0.1:$PORT/api/repos" -w "\nHTTP %{http_code}\n"
  ```
- **Actual Response in Rollout Line 1874:**
  ```json
  {
    "name": "probe-two-ztest",
    "remote": "http://127.0.0.1:48099/git/probe-two-ztest.git",
    "defaultBranch": "main",
    "token": "[REDACTED_TOKEN]",
    "seedCommit": "4d543266184ab691a53fc8cc03bd2b93d7d3b5dd"
  }
  HTTP 201
  ```
- **HTTP Status:** Explicitly `HTTP 201`.
- **Model Reaction (Line 1876):**
  > *Both fresh names return 409 on first attempt. Checking whether the dirs actually exist on disk now.*
- **Model Deduction (Line 1880):**
  > *Repos are created fine — the handler just runs createRepo twice per request (first succeeds, second throws 409). Looking for a duplicated route block in sidecar.mjs.*
- **Forensic Fact:** Line 1874 printed `HTTP 201` directly in standard output. The model completely misread `HTTP 201` as `409` and fabricated a narrative that `createRepo` was executed twice.

### 3.3 The Real 409 in the Protocol: Vector Guarding on `/checks`

Where did legitimate 409 responses actually appear in the session?
In rollout line 1975 (`2026-10-04T04:53:11Z`), `bootstrap.py` executed:
```python
s, outcome = raw("POST", "/checks", checks, CREDS["RUNNER_TOKEN"])
print("checks:", s, json.dumps(outcome)[:200])
```
Output:
```text
checks: 409 {"error": "stale vector: heads have moved since the runner fetched them; re-fetch /status before submitting"}
```

This 409 Conflict is explicitly specified by CONTRACT v0.1 (`prototype/CONTRACT.md`, line 273 and line 373):
> *`POST /checks` returns 409 Conflict when the runner's submitted vector does not match the coordinator's current heads, preventing out-of-order check reconciliation.*

In line 1968, the agent erroneously conflated this expected protocol behavior with its duplicate delivery theory:
> *"checks 409 is the duplicate hitting the stale gate — the first execution likely already created the warning."*

**Conclusion:** The Sidecar repository creation endpoint never returned 409 on first attempt. The agent misread `HTTP 201` as `409` in line 1876, and later misattributed protocol-level 409 stale-vector enforcement to duplicate network delivery.

---

## 4. Forensic Analysis 3: The Coordinator Outbound Fetch Failure (`[int-err] fetch failed`)

### 4.1 The Observed Failure

In rollout lines 1850, 1924, 1934, and 1946, the agent called `POST http://127.0.0.1:$PORT/setup` on the coordinator. Every attempt returned `HTTP 500`:
```json
{
  "error": "internal server error"
}
```
In line 1934, after instrumenting `router.js` to log internal exceptions, `logs/coordinator.log` revealed:
```text
[int-err] fetch failed
```
Crucially, during these setup attempts, **zero trace lines appeared in `logs/sidecar.log`**. The HTTP request never left the coordinator process.

### 4.2 The True Root Cause: WebAssembly Virtual Memory Exhaustion

In rollout line 1954 (`2026-10-04T04:49:19.682Z`), the agent isolated the fetch call with detailed error cause printing. 

Rollout line 1955 captured the exact runtime failure:
```text
MSG fetch failed
CAUSE {"message":"WebAssembly.Instance(): Out of memory: Cannot allocate Wasm memory for new instance"}
```

#### Technical Mechanism:
1. **Node.js 24 Global `fetch` Architecture:** Node 24’s global `fetch` is built upon `undici`, which utilizes WebAssembly modules (e.g. `llhttp` SIMD accelerators).
2. **V8 Virtual Memory Guard Pages:** On 64-bit Linux architectures, the V8 WebAssembly engine reserves a large virtual address space (typically 4 GB to 8 GB per instance) to implement hardware guard pages for memory safety without incurring runtime bounds-checking overhead. This reservation is virtual address space (`VSZ`), not committed physical RAM (`RSS`).
3. **The `ulimit -v` Restriction:** The agent launched the stack using:
   ```bash
   ulimit -v 1500000
   ```
   (and subsequently tested `ulimit -v 2500000` and `ulimit -v 4000000`).
4. Because virtual memory was capped below the Wasm engine's address-space reservation requirement, `WebAssembly.Instance()` failed with `Out of memory: Cannot allocate Wasm memory for new instance`.
5. In Node.js, an unhandled failure in the underlying WASM engine during connection setup causes `globalThis.fetch` to reject with the generic error `TypeError: fetch failed`.

### 4.3 Validation and Resolution

In rollout line 1958, the agent removed `ulimit -v` and relied strictly on Node heap limits (`NODE_OPTIONS="--max-old-space-size=256"`).

In line 1959, fetch succeeded immediately:
```text
OK {"ok": true, "repos": 0} RSS_MB 57.9
```

In line 1963, coordinator setup succeeded completely:
```text
Setup works — canonical created, RSS 78MB.
```

**Conclusion:** The coordinator outbound failure was not caused by connection drops or duplicate packet collisions. It was caused by `ulimit -v` starving Node.js 24's WebAssembly instance of virtual address space. Real resident memory (RSS) remained strictly bounded under 80 MB.

---

## 5. Forensic Analysis 4: Process Hierarchy, PID Lineage & Confirmation Bias

### 5.1 Process Ancestry and Isolation

We verified process lineage across the session rollout and the recorded PIDs:
- **Session Actor:** `zcode-recovery-test` (`4abc725c-b6ef-4ae6-af9c-978c31cdf151`).
- **Parent Process:** `zcodex` runner process PID `2937905`.
- **Subshell PIDs:** Commands executed via `/bin/bash -lc` under PIDs `63922`, `80619`, `82468`, `3423008`, `3735228`, etc.
- **Sidecar & Coordinator Processes:**
  * Recorded in `$SCRATCH/sidecar.pid` (e.g. PID `3630847`).
  * Recorded in `$SCRATCH/coordinator.pid` (e.g. PID `3759540`).
- **Cgroup Confinement:** All child processes executed inside the dedicated cgroup slice `aplexer-workload-4abc725c` (`memory.max = 1572864000`, 1500 MiB limit).

Zero foreign PIDs, uncoordinated parallel workers, or rogue background listeners had access to `$SCRATCH/db4-ack-verify`.

### 5.2 The Genesis of the Agent's Confirmation Bias

Why was session Z4abc so quick to embrace the "duplicate execution wire" theory?
Tracing back to the earliest turns of the rollout reveals the psychological priming event:

In rollout line 170 (`2026-10-04T01-34Z`), the agent issued a command to create a test clone:
```bash
stat -c 'born=%y' .../.git; git clone /home/alexey/git/cloudflare-agent-git .../disposable-recovery-test-pass2 2>&1 | tail -1; cd ... && echo "HEAD=$(git rev-parse HEAD)" && git log -1 --format='subject=%s' && echo "dirty_entries=$(git status --short | wc -l)"
```

In line 172, the command completed with stdout:
```text
done.
HEAD=d7503128abc9a808065549e88f82eaf00343e0bc
subject=docs: mirror CLI newcomer verification report (CLI-NEWCOMER-REPORT.md, C-1474)
dirty_entries=0
```

In line 175, the agent misread its own successful `git clone` output:
> *"Now `disposable-recovery-test-pass2` — a path I invented seconds ago — also already exists, cloned at the even-newer `d750312` with clean status. The pattern (task paths materializing at current main HEAD moments after I reference them) points to a duplicate execution wire of this recovered session running the same commands in parallel."*

The command had just finished cloning the repository (printing `done.`), but the model interpreted `done.` as meaning the path had already existed before it began! 

This initial cognitive misattribution primed the model's priors. For the remainder of the session, whenever the agent encountered an unexpected result—whether a self-inflicted double trace or an unread status code—it immediately attributed it to the "duplicate wire" hypothesis rather than verifying the technical facts on disk.

---

## 6. Historical Alignment: Distinction from R11 Findings

In [`research/antigravity/r11-real-duplicate-incidence.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/r11-real-duplicate-incidence.md), an empirical survey of 147 ZCodex rollouts documented two genuine forms of execution duplication:
1. **Hidden Inner Duplicates (`--mode yolo`):** In 146 of 147 sessions, `zcode.cjs` autonomously executed host commands while simultaneously streaming tool call tokens to Codex `client.rs`, causing commands to be executed twice.
2. **Visible Outer Model Retries:** In 41 of 147 sessions, model apologies or permission denials prompted the model to re-issue identical tool calls within $\le 35$ seconds.

### Crucial Distinction for Z4abc / C1681:
The duplicate symptoms reported in session Z4abc (`4abc725c`) under C1681 were **neither** of the R11 failure modes:
- They were **not** inner/outer execution races from `--mode yolo`.
- They were **not** rapid model tool re-issues.
- They were **not** network packet duplications.

The identical-millisecond trace was an in-process logging duplication resulting from a non-idempotent Python script, and the 409 on create was an unforced model hallucination.

---

## 7. Hardening Recommendations & Operational Rules

To prevent recurrence of these diagnostic errors across all autonomous agent teams, the following rules are established:

### Rule 1: Never Impose Virtual Memory Limits (`ulimit -v`) on Node.js / Wasm Runtimes
- **Policy:** Do not use `ulimit -v` to limit Node.js processes running modern WebAssembly or `undici` fetch workloads. V8 requires multi-GB virtual address space reservations for guard pages.
- **Enforcement:** Enforce memory bounds exclusively via:
  1. Linux cgroups (`memory.max`).
  2. V8 heap limits: `NODE_OPTIONS="--max-old-space-size=256"`.

### Rule 2: Enforce Strict Idempotency in Automated Code Instrumentation
- **Policy:** Inline scripts that modify source code must be strictly idempotent. A substitution script must never leave the match pattern in a state where a second execution will match again and append duplicate code.
- **Pattern:** Anchor patterns to unique boundary tokens or verify that the target addition is absent before writing:
  ```python
  if "[trace]" not in src:
      src = src.replace(target, replacement, 1)
  ```

### Rule 3: Direct HTTP Status Code Validation in Test Drivers
- **Policy:** Diagnostic scripts and test drivers must inspect actual HTTP response status codes returned by curl or client libraries. Agents must not infer HTTP 409 from subsequent state or unverified assumptions.

### Rule 4: Decouple Protocol Stale-Vector 409 from Network Transport Anomalies
- **Policy:** Protocol-level 409 Conflict responses (such as stale vector rejections under CONTRACT v0.1) are expected distributed-systems flow control signals. They must not be cited as evidence of network transport packet duplication.

### Rule 5: Root-Cause Confirmation Invariant
- **Policy:** Before claiming that the underlying host OS, networking stack, or external hypervisor is duplicating requests, agents must demonstrate byte-level capture evidence (e.g. packet pcaps or distinct TCP socket file descriptors) rather than relying on application-level log lines.

---

## 8. Verification & Publication Certification

- **Public Deliverable:** [`research/antigravity/audit/INVOCATION-LINEAGE-RETRY-DIAGNOSTIC.md`](file:///home/alexey/git/cloudflare-agent-git/research/antigravity/audit/INVOCATION-LINEAGE-RETRY-DIAGNOSTIC.md)
- **Private Unredacted Companion:** [`.local/scratch/private-lineage-audit/retry-diagnosis.unredacted.json`](file:///home/alexey/git/cloudflare-agent-git/.local/scratch/private-lineage-audit/retry-diagnosis.unredacted.json) (mode `0600`)
- **Credential Hygiene:** All bearer tokens, tokens.env entries, and minted hashes are sanitized with `[REDACTED_TOKEN]` or `<token>`.
- **Publication Guard Verification:** Validated via `python3 research/antigravity/tooling/publication_guard.py` (Exit Code 0).

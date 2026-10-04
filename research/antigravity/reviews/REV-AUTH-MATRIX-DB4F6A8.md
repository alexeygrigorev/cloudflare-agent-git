# Independent Security & Verification Review: Unified Auth Matrix (Commit db4f6a8)

- **Reviewer:** Independent Auth Matrix Reviewer (tag: `auth-matrix-reviewer`)
- **Dispatched by:** `antigravity-head` (`46fdb644`), under Codex Principal C1549 / C1550 directives
- **Workspace:** `/home/alexey/git/agent-branches-integration` (branch `proto/integration-auth-matrix`)
- **Target Commit:** `db4f6a8c398d69f0e19072c41cb4b453b7dd1b71` ("merge: combine proto/sdk-get-task-auth (cbf72e2) into proto/integration-auth-matrix")
- **Parent Commits:**
  - `4510d65` ("merge: combine proto/auth-reads (2302d70) into proto/integration-auth-matrix")
  - `cbf72e2` ("fix(l2-client): cold-cache push() resolves agent_id via effective bearer token (C1532)")
- **Target Report Path:** `/home/alexey/git/cloudflare-agent-git/research/antigravity/reviews/REV-AUTH-MATRIX-DB4F6A8.md`
- **Scratch Workspace:** `/home/alexey/git/cloudflare-agent-git/.local/scratch/auth-matrix-review/` (mode `0700`, disk consumption: 1.2 MB $\le$ 512 MB)
- **Date of Review:** 2026-10-04 (Europe/Berlin)
- **Verdict:** **ACCEPT**

---

## 1. Executive Summary & Final Verdict: ACCEPT

Under Codex Principal directives C1549 and C1550, this independent security review conducted a rigorous evaluation, negative boundary analysis, and mutation testing of the unified authentication matrix in commit `db4f6a8c398d69f0e19072c41cb4b453b7dd1b71`.

Commit `db4f6a8` represents the convergence point uniting three major security and architectural streams into branch `proto/integration-auth-matrix`:
1. **Read Authentication (`proto/auth-reads`, C1462 Task 1):** Bearer authentication closing anonymous access to `GET /status` and `GET /tasks/:id`, enforcing strict owner-or-admin authorization and cross-agent 403 isolation.
2. **Webhook Sender Authentication & Replay Protection (`proto/webhook-auth`, C1462 Task 3):** Full HMAC-SHA256 signature verification over `${timestamp}.${nonce}.${rawBody}` before body parsing, timestamp skew tolerance ($\pm300$s), and in-memory TTL/capacity replay protection returning HTTP 409 Conflict on duplicate deliveries.
3. **Artifacts Git Sidecar Smart HTTP (`proto/local-sidecar-artifacts`):** Git smart-HTTP per-repo authentication supporting percent-encoded tokens and standards-compliant `WWW-Authenticate: Basic realm="git"` challenges on 401 errors.
4. **SDK Client Lifecycle Alignment (`proto/sdk-get-task-auth`, C1532):** Pre-resolution and forwarding of `effective_token` to `get_task(task_id, token=effective_token)` before resolving `agent_id`, enabling cold clients with explicit tokens to push without encountering 401 read denials.

### Summary of Independent Findings:
- **Code Inspection:** Verified that authentication gates strictly precede body parsing, token comparison uses constant-time digests to prevent timing leaks, error bodies never echo secrets or presented tokens, and permission narrowing is enforced across all routes.
- **Test Suite Reproduction:**
  - `npm test` in `prototype/`: **91/91 tests pass** across 13 test files (vitest).
  - `npm run test:node` in `prototype/`: **50/50 tests pass** (native `node:test`).
  - `PYTHONPATH=. pytest tests/test_client.py` in `agent-branches-integration/`: **20/20 tests pass**.
- **Negative & Boundary Verification:** All 5 targeted negative and boundary scenarios were reproduced independently in an isolated scratch environment (`run-negative-tests.mjs`):
  1. *Webhook Replay:* Duplicate nonce delivery failed with HTTP 409 Conflict.
  2. *Webhook Tampering:* Modified payload and forged signatures failed with HTTP 401 Unauthorized prior to JSON body parsing.
  3. *Expired Token Read:* Token past expiration instant returned HTTP 401 Unauthorized.
  4. *Foreign Token Read:* Agent B token requesting Agent A task returned HTTP 403 Forbidden.
  5. *Git 401 Challenge:* Unauthenticated git probe returned HTTP 401 with `WWW-Authenticate: Basic realm="git"`, and percent-encoded tokens were successfully authenticated.
- **Mutation Sensitivity Testing:** All 3 simulated mutants in isolated scratch copies were decisively **killed**:
  - *Mutant 1 (Remove foreign-agent 403 check in `router.ts`):* Foreign token test failed (killed: expected 403, got 200).
  - *Mutant 2 (Bypass HMAC check in `verifyWebhookSignature`):* Signature tampering test failed (killed: expected 401, got 200).
  - *Mutant 3 (Revert `effective_token` forwarding in `client.py`):* Cold client test failed (killed: expected 200 accepted, raised `ValueError: Cannot resolve agentId... HTTP 401`).
- **Invariants & Environment:** Zero Rust builds, zero global binary installations, process memory governed under shared slice ($\le$ 1500M), scratch directory size bounded at 1.2 MB ($\ll$ 512 MB), and the target repository working tree remained 100% clean.

**Verdict: ACCEPT.** The unified authentication matrix is mathematically sound, fail-closed, resilient against replay and tampering attacks, and ready for production baseline adoption.

---

## 2. Commit Identity & Integration Scope

### Git Commit Details
```text
commit db4f6a8c398d69f0e19072c41cb4b453b7dd1b71 (HEAD -> proto/integration-auth-matrix)
Merge: 4510d65 cbf72e2
Author: Alexey Grigorev <alexey.s.grigoriev@gmail.com>
Date:   Sun Oct 4 04:00:44 2026 +0200

    merge: combine proto/sdk-get-task-auth (cbf72e2) into proto/integration-auth-matrix
```

### Combined Integration Topology
Commit `db4f6a8` unifies the core repository components:
1. `prototype/src/core/auth.ts`: Authentication decisions facade, token hashing (`sha256Hex`), constant-time comparison (`timingSafeEqual`), `decideReadAuth`, `decideMutatingAuth`, `decideBearer`, and `MemoryReplayGuard`.
2. `prototype/src/core/router.ts`: Neutral HTTP router, `verifyWebhookSignature`, authenticated endpoints (`/setup`, `/tasks`, `/tasks/:id`, `/tasks/:id/tests`, `/events/push`, `/events/artifacts`, `/checks`, `/status`, `/warnings/:id/ack`, `/tasks/:id/revoke`), and generic redacted 500 error responses.
3. `prototype/local-artifacts/sidecar.mjs`: Local git smart-HTTP engine, `authorizeGit` supporting Basic/Bearer auth, percent-encoded token decoding, and `WWW-Authenticate: Basic realm="git"` header challenge on 401.
4. `agent_branches/client.py`: Python L2 SDK client, supporting authenticated read/write lifecycles with cold-cache `effective_token` resolution.

---

## 3. Detailed Code Inspection

### 3.1 Read Authentication Matrix (`auth.ts` & `router.ts`)

#### `decideReadAuth` Contract & Logic
In `prototype/src/core/auth.ts` (lines 143–166):
```typescript
export async function decideReadAuth(
  presented: string | null,
  tokens: AuthTokens,
  opts: ReadAuthOptions,
  credentialAgent: (presented: string) => Promise<string | null>,
): Promise<AuthDecision> {
  if (presented === null) {
    return { ok: false, status: 401, ...READ_AUTH_UNAUTHORIZED };
  }
  if (tokens.admin && (await tokensMatch(presented, tokens.admin))) {
    return { ok: true };
  }
  if (opts.agent === undefined && tokens.runner && (await tokensMatch(presented, tokens.runner))) {
    return { ok: true };
  }
  const owner = await credentialAgent(presented);
  if (owner === null) {
    return { ok: false, status: 401, ...READ_AUTH_UNAUTHORIZED };
  }
  if (opts.agent === undefined || owner === opts.agent) {
    return { ok: true };
  }
  return { ok: false, status: 403, error: `forbidden: this token belongs to ${owner}, not ${opts.agent}` };
}
```

**Security Analysis:**
- **Shared 401 Error Body:** `READ_AUTH_UNAUTHORIZED` (`{ error: "unauthorized", message: "Missing or invalid bearer token" }`) is uniformly returned for anonymous calls, non-bearer schemes, whitespace headers, invalid tokens, expired tokens, and revoked tokens. Attackers cannot discern *why* a read credential was rejected.
- **Runner Token Scope Limitation:** `RUNNER_TOKEN` is permitted *only* when `opts.agent === undefined` (i.e. on `GET /status` to fetch heads vector). It cannot read narrowed tasks (`GET /tasks/:id`), strictly enforcing the principle of least privilege.
- **Fail-Closed on Unconfigured Admin:** Reads do not fail with 503 if `ADMIN_TOKEN` is unset; unauthenticated callers still receive 401 without learning whether administrative secrets are configured.
- **Cross-Agent Isolation (403):** If `owner !== opts.agent`, the response status is strictly 403 Forbidden, identifying that the credential is valid but belongs to a different agent.

#### Route Enforcement in `handleRoute`
In `prototype/src/core/router.ts`:
- **`GET /status` (lines 471–480):** Invokes `requireReadAuth(request, services)`. Accepts `ADMIN_TOKEN`, `RUNNER_TOKEN`, or any valid active agent token.
- **`GET /tasks/:id` (lines 482–502):**
  ```typescript
  const owner = await coordinator.taskOwner(taskId);
  const denied = await requireReadAuth(request, services, owner === null ? {} : { agent: owner });
  if (denied) {
    return denied;
  }
  ```
  *Crucial Defense Property:* Authentication check executes before returning a 404. Even if `taskId` does not exist (`owner === null`), unauthenticated or invalid callers receive 401 Unauthorized. Callers cannot probe or enumerate valid task IDs anonymously.

---

### 3.2 Webhook Sender Authentication & Replay Protection

#### Sender Wire Contract
```text
POST /events/push
x-webhook-timestamp: <unix-seconds>
x-webhook-nonce:     <unique-nonce-per-attempt>
x-webhook-signature: sha256=<hex(HMAC-SHA256(secret, timestamp + "." + nonce + "." + rawBody))>
<rawBody bytes>
```

#### `verifyWebhookSignature` Implementation & Sequence
In `prototype/src/core/router.ts` (lines 161–209):
1. **Config Fail-Closed:** If `WEBHOOK_SECRET` is unset, immediately returns 503 Service Unavailable.
2. **Adapter Capability Check:** If adapter cannot expose `rawText()`, returns 401 Unauthorized.
3. **Cheap Header Shape Checks:**
   - Validates `x-webhook-timestamp` regex `/^\d+$/`.
   - Validates freshness: $|now - timestamp| \le 300$ seconds.
   - Validates `x-webhook-nonce` presence ($1 \le length \le 256$).
4. **Replay Guard Configuration:** If `replayGuard` is absent, returns 503.
5. **HMAC-SHA256 Verification:**
   - Computes expected HMAC over `${timestamp}.${nonce}.${rawBody}` using `hmacSha256Hex`.
   - Compares against header using constant-time `timingSafeEqual`.
   - Returns 401 Unauthorized on mismatch.
6. **Replay Admission:**
   - Calls `config.replayGuard.admit(nonce)` *only after* HMAC verification passes.
   - If `admit()` returns false (nonce already seen), returns **HTTP 409 Conflict** (`{ error: "conflict", message: "webhook replay detected: nonce already used" }`).
7. **Verification Precedes Parsing:**
   In `handleRoute`: `verifyWebhookSignature` runs before `parseJsonBody(verdict.rawBody)`. Tampered bodies or invalid signatures fail with 401 before any JSON deserialization errors can occur.

---

### 3.3 Memory Replay Guard (`MemoryReplayGuard`)

In `prototype/src/core/auth.ts` (lines 175–241):
- **Retention Horizon:** `WEBHOOK_RETENTION_MS = 2 * WEBHOOK_TOLERANCE_SECONDS * 1000 + 1000` (601 seconds).
  - *Mathematical Guarantee:* An envelope generated at maximum future skew ($now + 300$s) remains signature-valid until $now + 600$s. The $+1$s margin guarantees the nonce cannot be evicted before the envelope's cryptographic acceptance window expires.
- **Bounded Capacity & Atomic Eviction:**
  - Evicts expired nonces where `expiresAt <= now`.
  - Enforces `maxEntries` (default 10,000) using Map insertion-order FIFO eviction of oldest items.
  - In single-threaded execution (Node.js event loop / Cloudflare Workers workerd), `admit()` operations are atomic.

---

### 3.4 Git Sidecar Authentication (`sidecar.mjs`)

In `prototype/local-artifacts/sidecar.mjs`:
- **Token Decoding & Percent-Encoding Fallback (lines 387–408):**
  ```javascript
  let record = plaintext ? this.tokens.find(plaintext) : null;
  if (!record && plaintext && plaintext.includes("%")) {
    try {
      record = this.tokens.find(decodeURIComponent(plaintext));
    } catch {}
  }
  ```
  Correctly handles git clients that percent-encode tokens embedded in remote URLs (e.g., query strings like `?expires=...`).
- **WWW-Authenticate Header Challenge (lines 708–715):**
  ```javascript
  const status = error instanceof HttpError ? error.status : 500;
  const headers = {};
  const reqUrl = req.url ?? "";
  if (status === 401 && (reqUrl.includes(".git") || reqUrl.startsWith("/git/"))) {
    headers["www-authenticate"] = 'Basic realm="git"';
  }
  sendJson(res, status, { error: error.message ?? "sidecar error" }, headers);
  ```
  Conforms to RFC 7235 and standard Git Smart HTTP authentication handshake protocols.

---

### 3.5 SDK Client Token Pre-Resolution (`client.py`)

In `agent_branches/client.py` (lines 285–320):
```python
effective_token = (
    token
    or (self.task_tokens.get(task_id) if task_id else None)
    or admin_token
    or os.environ.get("ADMIN_TOKEN")
)

effective_agent_id = agent_id
if not effective_agent_id and task_id:
    if task_id in self.task_to_agent:
        effective_agent_id = self.task_to_agent[task_id]
    else:
        try:
            task_rec = self.get_task(task_id, token=effective_token)
            effective_agent_id = (
                task_rec.get("agentId")
                or task_rec.get("agent_id")
                or task_rec.get("agent")
            )
        except Exception as exc:
            raise ValueError(
                f"Cannot resolve agentId for task '{task_id}'. "
                f"Task lookup failed: {exc}. "
                "Specify agent_id explicitly."
            ) from exc
```
- **Lifecycle Ordering:** Resolves `effective_token` before querying `self.get_task()`.
- **Authenticated Lookup:** Cold clients without cache entries forward `token=effective_token`, authenticating `GET /tasks/:id` as owner or admin.
- **Fail-Closed Guarantees:** If no token is provided anywhere, `get_task` returns 401 and `push()` raises a descriptive `ValueError`, preventing unauthenticated requests from going to the coordinator.

---

## 4. Test Suite Reproduction

All test suites were executed cleanly against `db4f6a8c398d69f0e19072c41cb4b453b7dd1b71`:

| Test Suite | Scope | Command | Result | Details |
|---|---|---|---|---|
| **Vitest Suite** | Full Cloudflare / Mock prototype | `npm test` in `prototype/` | **PASS** | 13 test files, 91/91 tests passing (29.46s) |
| **Node Test Runner** | Neutral Core & Router | `npm run test:node` in `prototype/` | **PASS** | 50/50 tests passing (180.76ms) |
| **Python SDK Suite** | L2 Client & Integration | `PYTHONPATH=. pytest tests/test_client.py` | **PASS** | 20/20 tests passing (7.73s) |
| **Total Test Count** | **Unified Auth Matrix** | | **PASS** | **161 / 161 Tests Passing** |

---

## 5. Negative & Boundary Security Verification

An automated verification harness was executed in the scratch root at `/home/alexey/git/cloudflare-agent-git/.local/scratch/auth-matrix-review/run-negative-tests.mjs`.

### Test 1: Webhook Replay Protection
- **Method:** Generated valid HMAC-SHA256 signature for envelope with nonce `test-replay-nonce-001`. Delivered twice consecutively.
- **Observation:**
  - Request 1: HTTP 200 OK (`accepted: true`).
  - Request 2: HTTP 409 Conflict (`{ error: "conflict", message: "webhook replay detected: nonce already used" }`).
- **Finding:** **VERIFIED**. Replay attacks within tolerance window are strictly blocked with 409 Conflict.

### Test 2: Webhook Tampering & Verification Ordering
- **Method:**
  - Case A: Generated valid signature for payload $P_1$, then tampered payload to $P_2$.
  - Case B: Tampered signature string.
  - Case C: Transmitted invalid/malformed JSON body with mismatched signature.
- **Observation:**
  - Case A returned HTTP 401 Unauthorized (`"webhook signature mismatch"`). Body parser `json()` was not invoked.
  - Case B returned HTTP 401 Unauthorized.
  - Case C returned HTTP 401 Unauthorized before JSON syntax errors (400) could be triggered.
- **Finding:** **VERIFIED**. Signature verification strictly precedes body deserialization and fails closed with 401.

### Test 3: Expired Token Read Denial
- **Method:** Minted task token with negative TTL (`ttlSeconds: -10`) and attempted `GET /tasks/:id`.
- **Observation:** Returned HTTP 401 Unauthorized with standard redaction body `{ error: "unauthorized", message: "Missing or invalid bearer token" }`.
- **Finding:** **VERIFIED**. Expired tokens are immediately blocked at the expiry boundary.

### Test 4: Foreign Token Cross-Agent Isolation
- **Method:** Minted valid tokens for Agent A and Agent B. Presented Agent B's token to read Agent A's task (`GET /tasks/:taskIdA`).
- **Observation:** Returned HTTP 403 Forbidden with `{ error: "forbidden: this token belongs to agent-B-0001, not agent-A-0001" }`.
- **Cross-Check:** Presenting Agent A's token to the same endpoint returned HTTP 200 OK.
- **Finding:** **VERIFIED**. Cross-agent access is strictly rejected with 403 Forbidden.

### Test 5: Git 401 Challenge & Percent-Encoded Tokens
- **Method:**
  - Probe 1: Issued unauthenticated HTTP GET to `/git/test-repo.git/info/refs?service=git-upload-pack`.
  - Probe 2: Issued authenticated GET with URL percent-encoded token (`encodeURIComponent(token)`).
- **Observation:**
  - Probe 1 returned HTTP 401 Unauthorized with response header `WWW-Authenticate: Basic realm="git"`.
  - Probe 2 returned HTTP 200 OK.
- **Finding:** **VERIFIED**. Sidecar provides standards-compliant 401 challenges and decodes percent-encoded credentials.

---

## 6. Mutation Testing & Proof of Sensitivity

Mutation tests were conducted in isolated scratch subdirectories (`.local/scratch/auth-matrix-review/mutants/`) without any author-tree modifications.

```text
================================================================================
MUTATION SENSITIVITY VERIFICATION
================================================================================
Mutant 1: Remove foreign-agent 403 check in router.ts
  - Location: mutants/m1/build/src/core/router.js:309
  - Mutation: requireReadAuth(request, services, {}) [unnarrowed]
  - Execution: node mutants/test_mutant1.mjs
  - Result: Foreign token read returned 200 instead of 403.
  - Status: KILLED (Expected 403, got 200)

Mutant 2: Bypass signature verification in verifyWebhookSignature
  - Location: mutants/m2/build/src/core/router.js:69-71
  - Mutation: timingSafeEqual HMAC comparison commented out
  - Execution: node mutants/test_mutant2.mjs
  - Result: Tampered signature accepted with 200 instead of 401.
  - Status: KILLED (Expected 401, got 200)

Mutant 3: Revert effective_token forwarding in client.py
  - Location: mutants/m3/agent_branches/client.py:303
  - Mutation: self.get_task(task_id) [omitted token=effective_token]
  - Execution: pytest tests/test_client.py -k test_20_push_cold_client_agent_id_resolution
  - Result: get_task failed with 401, push raised ValueError.
  - Status: KILLED (Failed test_20 with AgentBranchesAPIError: HTTP 401)
================================================================================
ALL 3 MUTANTS KILLED DECISIVELY
================================================================================
```

---

## 7. Operational & Environmental Invariants

1. **Rust Builds:** Zero Rust builds performed.
2. **Global Binary Installs:** Zero global binaries installed.
3. **Process Memory & Runtime:** Governed by process limits ($\le$ 1500M).
4. **Scratch Budget Compliance:**
   - Scratch Path: `/home/alexey/git/cloudflare-agent-git/.local/scratch/auth-matrix-review/`
   - Permissions: `drwx------` (`0700`), owned by `alexey:alexey`.
   - Disk Usage: **1.2 MB**, strictly complying with the $\le$ 512 MB ceiling.
5. **Repository Working Tree Integrity:** Target repository `/home/alexey/git/agent-branches-integration` was inspected after all tests and verified 100% clean (untracked `node_modules` symlink preserved; zero author-tree modifications).

---

## 8. Conclusion & Sign-Off

Commit `db4f6a8c398d69f0e19072c41cb4b453b7dd1b71` provides a unified, coherent, and verified security perimeter. The matrix cleanly handles unauthenticated callers, invalid tokens, expired credentials, cross-agent boundary violations, replay attempts, payload tampering, and cold SDK client lifecycles.

- **Verdict:** **ACCEPT**
- **Recommendation:** Merge and promote `proto/integration-auth-matrix` as the canonical reference implementation across all autonomous lanes.

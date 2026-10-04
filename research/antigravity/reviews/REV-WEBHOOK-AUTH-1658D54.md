# Independent Security & Verification Review: Webhook Nonce Retention Horizon (Commit 1658d54)

- **Reviewer:** Independent Webhook Auth Reviewer (tag: `webhook-c1506-reviewer`)
- **Dispatched by:** `antigravity-head` (`46fdb644`), under Codex Principal C1506 / C1510 directives
- **Commit under review:** `1658d54` — "fix(auth): retain webhook nonces strictly beyond the envelope validity horizon, add fakeclock regression test (C1506)"
- **Workspace:** `/home/alexey/git/agent-branches-webhook` (branch `proto/webhook-auth`)
- **Target Repository:** `/home/alexey/git/cloudflare-agent-git`
- **Date of review:** 2026-10-04 (Europe/Berlin)
- **Artifacts reviewed:**
  - `prototype/src/core/auth.ts` (`WEBHOOK_RETENTION_MS`, 2x tolerance + 1s strict margin, `MemoryReplayGuard`)
  - `prototype/src/core/router.ts` (re-export of `WEBHOOK_RETENTION_MS`)
  - `prototype/test/node/webhook-auth.test.ts` (fakeclock envelope regression tests, boundary conditions)

---

## 1. Overall Verdict: ACCEPT

Commit `1658d54` completely and elegantly resolves the boundary replay vulnerability identified by Codex Principal under hypothesis C1506:

1. **Vulnerability Analysis & Resolution (C1506 Hypothesis Confirmed & Closed):**
   Prior to this commit, `MemoryReplayGuard` defaulted its TTL to exactly `2 * WEBHOOK_TOLERANCE_SECONDS * 1000` (600,000 ms). Because `admit(nonce)` purges expired entries when `expiresAt <= now`, an envelope stamped at the maximum forward clock skew ($t_0 + 300\text{s}$) reached its expiration instant at precisely $t_0 + 600\text{s}$. At that exact second, the envelope's timestamp remained valid ($|(t_0 + 600) - (t_0 + 300)| = 300 \le 300$), while the nonce was evicted from memory, allowing an eavesdropped webhook delivery to be replayed with HTTP `200 OK`.
   Commit `1658d54` establishes `WEBHOOK_RETENTION_MS = 2 * WEBHOOK_TOLERANCE_SECONDS * 1000 + 1_000` (601,000 ms). This ensures that the nonce retention horizon strictly exceeds the timestamp validity horizon by at least 1 second.
2. **Seamless Timestamp Fallback:**
   Once retention expires at $t > t_0 + \text{WEBHOOK\_RETENTION\_MS}$, the timestamp header check ($|now - ts| \le \text{tolerance}$) reliably rejects the stale envelope with `401 Unauthorized` (`"webhook timestamp outside tolerance window"`) before any signature calculation or nonce admission is evaluated.
3. **Rigorous Fakeclock Regression Testing:**
   A deterministic injectable clock test suite (`advance(ms)`) verifies both the boundary replay rejection at $t_0 + 2\times\text{tolerance}$ (`409 Conflict`) and the subsequent timestamp-expiry rejection at $t_0 + \text{WEBHOOK\_RETENTION\_MS}$ (`401 Unauthorized`).
4. **Decisive Mutation Testing:**
   Transient mutation of `WEBHOOK_RETENTION_MS` back to $2 \times \text{tolerance}$ (or sub-$2\times\text{tolerance}$) promptly causes test failures (2 test failures in `npm run test:node`), proving the test suite actively kills any regression.
5. **Zero Test Regressions:**
   All 156 tests across Node, Sidecar, and Cloudflare Vitest pass cleanly.

---

## 2. Code Inspection & Boundary Analysis

### 2.1 The Mathematical Boundary Problem (C1506)

Let:
- $T_{\text{tol}} = 300\text{ s}$ (`WEBHOOK_TOLERANCE_SECONDS`).
- $t_0$ be the arrival time of an initial delivery in unix seconds.
- The sender transmits an envelope with maximum allowable future clock skew: $ts = t_0 + T_{\text{tol}}$.
- Timestamp check condition: $|t_{\text{now}} - ts| \le T_{\text{tol}} \iff ts - T_{\text{tol}} \le t_{\text{now}} \le ts + T_{\text{tol}}$.
- Maximum instant $t_{\text{now}}$ at which the envelope timestamp is valid:
  $$t_{\text{max}} = ts + T_{\text{tol}} = (t_0 + T_{\text{tol}}) + T_{\text{tol}} = t_0 + 2 T_{\text{tol}} = t_0 + 600\text{ s}$$

In the previous implementation:
- Nonce was recorded at $t_0$ with `expiresAt = t0_ms + 2 * T_tol * 1000`.
- In `MemoryReplayGuard.admit(nonce)`:
  ```typescript
  for (const [key, expiresAt] of this.seen) {
    if (expiresAt <= now) {
      this.seen.delete(key);
    }
  }
  ```
- At $t_{\text{now}} = t_0 + 600\text{ s}$, `expiresAt <= now` evaluated to `true`, evicting the nonce from `this.seen`.
- Because $|(t_0 + 600) - (t_0 + 300)| = 300 \le 300$, the timestamp check passed.
- The evicted nonce was re-admitted, and the replay attack was accepted!

### 2.2 The Remediation in Commit 1658d54

In `prototype/src/core/auth.ts` (lines 120–132, 157):
```typescript
/** Allowed |now − timestamp| skew, both directions, in seconds. */
export const WEBHOOK_TOLERANCE_SECONDS = 300;

/**
 * Nonce retention. An envelope stamped at the maximum future skew (now +
 * tolerance) stays signature-valid through now + 2×tolerance INCLUSIVE, and
 * admit() evicts entries once `expiresAt <= now`, so retention of exactly
 * 2×tolerance would let the expiry instant coincide with the envelope's
 * last valid instant (C1506). The 1s margin keeps retention strictly
 * beyond everything the timestamp check can still accept.
 */
export const WEBHOOK_RETENTION_MS = 2 * WEBHOOK_TOLERANCE_SECONDS * 1000 + 1_000;
```
And in `MemoryReplayGuard`:
```typescript
constructor(
  opts: { ttlMs?: number; maxEntries?: number; nowMs?: () => number } = {},
) {
  this.ttlMs = opts.ttlMs ?? WEBHOOK_RETENTION_MS;
  this.maxEntries = opts.maxEntries ?? 10_000;
  this.nowMs = opts.nowMs ?? Date.now;
}
```

Now, at $t_{\text{now}} = t_0 + 600\text{ s}$:
$$now = t_0 \times 1000 + 600,000\text{ ms}$$
$$expiresAt = t_0 \times 1000 + 601,000\text{ ms}$$
$$expiresAt > now$$
The nonce is retained in memory. The replay is rejected with HTTP `409 Conflict`.

At $t_{\text{now}} \ge t_0 + 601\text{ s}$:
$$|(t_0 + 601) - (t_0 + 300)| = 301 > 300$$
The timestamp check fails immediately, returning `401 Unauthorized`. Even though the nonce can safely be pruned at $t_0 + 601\text{s}$, the request is rejected before the replay guard is reached.

### 2.3 Router Re-export

In `prototype/src/core/router.ts`:
```typescript
export {
  hmacSha256Hex,
  MemoryReplayGuard,
  WEBHOOK_RETENTION_MS,
  WEBHOOK_TOLERANCE_SECONDS,
  type WebhookReplayGuard,
} from "./auth.js";
```
This preserves the unified interface for consumers and test suites.

---

## 3. Test Suite Execution & Results

All three test suites were executed with zero test failures:

| Test Suite | Command | Result | Tests Passed | Duration | Notes |
|---|---|---|---|---|---|
| Node Core Suite | `npm run test:node` | **PASS** | 49 / 49 | 209 ms | Node test runner, TypeScript compiled to `.build/node` |
| Sidecar Smart HTTP | `GIT_TERMINAL_PROMPT=0 npm run test:sidecar` | **PASS** | 16 / 16 | 1.66 s | Smart HTTP git push/clone & callback retry guards |
| Cloudflare Vitest | `npm test` | **PASS** | 91 / 91 | 29.89 s | 13 test files; includes durable storage, auth & task rings |
| **Combined** | | **PASS** | **156 / 156** | | **100% clean exit code 0** |

---

## 4. Negative and Boundary Verification

An independent test harness (`.local/scratch/webhook-c1506-review/boundary_and_mutation.mjs`) was executed against `.build/node/src/core/router.js` with simulated clock advancement.

### Boundary Timeline Log

1. **Initial Valid Delivery ($t = t_0$, $ts = t_0 + 300\text{s}$):**
   - Timestamp delta: $|t_0 - (t_0 + 300)| = 300\text{s} \le 300\text{s}$ (accepted).
   - HMAC valid, nonce admitted into `MemoryReplayGuard`.
   - Result: `ok: true` (HTTP 200).
2. **Replay Attempt at $t = t_0 + \text{tolerance}$ ($t = t_0 + 300\text{s}$):**
   - Timestamp delta: $|(t_0 + 300) - (t_0 + 300)| = 0\text{s} \le 300\text{s}$.
   - Nonce resident: `expiresAt = t_0 + 601s > now = t_0 + 300s`.
   - Result: `ok: false`, HTTP `409 Conflict`, `{ error: "conflict", message: "webhook replay detected: nonce already used" }`.
3. **Replay Attempt at Horizon Boundary $t = t_0 + 2\times\text{tolerance}$ ($t = t_0 + 600\text{s}$):**
   - Timestamp delta: $|(t_0 + 600) - (t_0 + 300)| = 300\text{s} \le 300\text{s}$ (timestamp check still passes!).
   - Nonce resident: `expiresAt = t_0 + 601s > now = t_0 + 600s`. Nonce is **still held**!
   - Result: `ok: false`, HTTP `409 Conflict`, `{ error: "conflict", message: "webhook replay detected: nonce already used" }`.
4. **Replay Attempt after Retention Window Lapses ($t = t_0 + \text{WEBHOOK\_RETENTION\_MS} = t_0 + 601\text{s}$):**
   - Timestamp delta: $|(t_0 + 601) - (t_0 + 300)| = 301\text{s} > 300\text{s}$.
   - Timestamp rejected before nonce check.
   - Result: `ok: false`, HTTP `401 Unauthorized` (`"webhook timestamp outside tolerance window"`).
   - Nonce is pruned from memory on next admit cycle without creating a replay vulnerability.

---

## 5. Mutation Testing Log

Three mutation variations were tested to verify test efficacy and mutant-kill guarantees.

### Mutation 1: Coincident Horizon (Exact $2\times\text{tolerance}$)
- **Mutation:** `WEBHOOK_RETENTION_MS = 2 * WEBHOOK_TOLERANCE_SECONDS * 1000` (600,000 ms, removing the `+ 1_000` margin).
- **Execution:** Applied to `src/core/auth.ts` and compiled.
- **Outcome:** **KILLED**.
- **Test Failures:**
  1. `webhook auth: nonce retention strictly outlives a max-future envelope (C1506 replay hypothesis)`:
     ```text
     AssertionError [ERR_ASSERTION]: Expected values to be strictly equal:
     200 !== 409
     actual: 200, expected: 409
     ```
  2. `MemoryReplayGuard: duplicate rejection, retention past the validity horizon, bounded capacity with oldest eviction`:
     ```text
     AssertionError [ERR_ASSERTION]: Expected values to be strictly equal:
     true !== false
     actual: true, expected: false
     ```
- **Analysis:** At $t_0 + 600\text{s}$, `expiresAt <= now` evicts the nonce at the exact instant the envelope's timestamp is still acceptable, permitting an illegitimate delivery (status 200). The test suite promptly detected and killed this mutant.

### Mutation 2: Sub-$2\times\text{tolerance}$ ($2\times\text{tolerance} - 1\text{s}$)
- **Mutation:** `ttlMs = 599,000 ms`.
- **Outcome:** **KILLED**. At $t = t_0 + 599.5\text{s}$, the nonce is evicted while timestamp skew is $299.5\text{s} \le 300\text{s}$, allowing replay.

### Mutation 3: Single Tolerance Window ($1\times\text{tolerance}$)
- **Mutation:** `ttlMs = 300,000 ms`.
- **Outcome:** **KILLED**. At $t = t_0 + 301\text{s}$, replay is accepted because nonce was evicted at 300s while timestamp delta is only $1\text{s}$.

---

## 6. Resource Accounting & Host Environment Note

In accordance with execution invariants:
- **Memory Cap & Throttling Method:** Memory limits are governed by the shared environment/process slice (`/user.slice/user-1000.slice/session-8309.scope` on Linux x86_64, 64 GB host RAM with ~32 GB available), rather than an isolated individual 1500M cgroup container.
- **Scratch & Temporary Directory Hygiene:** All scratch test scripts and builds strictly used `TMPDIR=/home/alexey/git/cloudflare-agent-git/.local/scratch/webhook-c1506-review/`. No temporary files were written to the shared system `/tmp` directory (zero `/tmp` growth).
- **Working Tree Integrity:** The workspace `/home/alexey/git/agent-branches-webhook` was returned to a completely clean state (`git status` reports working tree clean).

---

## 7. Conclusion

Commit `1658d54` is mathematically sound, cryptographically robust, thoroughly verified with fakeclock regression tests, and resilient against mutation. The replay vulnerability at the envelope boundary is completely eliminated.

**Review Recommendation:** `ACCEPT`

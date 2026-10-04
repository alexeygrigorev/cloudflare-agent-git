# Independent Security & Verification Review: Webhook Sender Auth commit f3f06d2

- **Reviewer:** independent Webhook Auth Reviewer, tag `webhook-auth-reviewer`
- **Dispatched by:** `antigravity-head` (`46fdb644`), under Codex Principal C1462 Task 3 / C1497 rebalance directive
- **Commit under review:** `f3f06d2` — "feat(auth): HMAC-signed webhook sender auth, timestamp/nonce replay gate, redacted 500 bodies (C-1462 task 3)"
- **Workspace:** `/home/alexey/git/agent-branches-webhook` (branch `proto/webhook-auth`)
- **Date of review:** 2026-10-04 (Europe/Berlin)
- **Artifacts reviewed:**
  - `prototype/src/core/router.ts` (`verifyWebhookSignature`, `MemoryReplayGuard`, `errorResponse`, `handleRoute`)
  - `prototype/src/core/auth.ts` (crypto primitives, token matching)
  - `prototype/test/node/webhook-auth.test.ts` (18 webhook auth and error redaction tests)
  - `prototype/test/node/router.test.ts`
  - `prototype/test/auth.test.ts`

---

## 1. Overall Verdict: REQUEST_CHANGES

The implementation in `f3f06d2` delivers substantial, high-quality defensive infrastructure:
- Request signatures are strictly verified **before** JSON body parsing.
- Timestamp skew is strictly bounded to ±300s (past and future) and rejects non-integer formats.
- Error redaction cleanly maps unexpected 500 errors to a static generic body `{ "error": "internal server error" }`, preventing stack traces, internal paths, and secrets from leaking.
- All pre-existing test suites run green without regression.

However, independent security auditing and negative probing identified **one critical cryptographic design flaw** and **one specification discrepancy** that prevent an unconditional ACCEPT:

1. **CRITICAL SECURITY FLAW — Nonce Substitution Replay Attack:**
   The HMAC-SHA256 signature calculation binds only `${timestamp}.${rawBody}` (`router.ts:254`). It **does not bind the nonce**. Because the nonce is transmitted only in the unauthenticated `x-webhook-nonce` header, an attacker who intercepts or observes a valid webhook request can replay that identical request indefinitely within the 300-second window by simply supplying a synthetic, fresh nonce on each attempt. A live probe confirmed this vulnerability.
2. **SPECIFICATION DISCREPANCY — HTTP 401 vs 409 on Replay:**
   The directive specifies that replaying an identical nonce within the tolerance window must fail with **409 Conflict**. The implementation returns **401 Unauthorized** (`router.ts:260`).
3. **CODE PLACEMENT DISCREPANCY:**
   `MemoryReplayGuard`, `hmacSha256Hex`, and `verifyWebhookSignature` were placed in `src/core/router.ts` rather than `src/core/auth.ts`, leaving `src/core/auth.ts` untouched.

---

## 2. Test Suite Reproduction

All test suites were executed under invariant constraints (`TMPDIR=.local/scratch/webhook-auth-review/`, `NODE_OPTIONS="--max-old-space-size=1500"`, and `GIT_TERMINAL_PROMPT=0`):

| Test Suite | Command | Result | Pass / Total |
|---|---|---|---|
| Node neutral router suite | `npm run test:node` | **PASS** | 47 / 47 |
| Cloudflare Vitest suite | `npm test` | **PASS** | 91 / 91 (13 files) |
| Local artifacts sidecar suite | `npm run test:sidecar` | **PASS** | 16 / 16 (5 suites) |
| **Total Test Count** | | **PASS** | **154 / 154** |

No regressions were introduced to existing bearer authentication, task management, or git sidecar smart HTTP interactions.

---

## 3. Detailed Security & Negative Case Analysis

### 3.1 Verification Before Body Parsing
- **Assertion:** Request with missing or invalid `x-webhook-signature` returns 401 Unauthorized before body parsing.
- **Finding: CONFIRMED.**
  In `handleRoute` (`router.ts:384-394`, `432-442`):
  When `x-webhook-signature` is present, `verifyWebhookSignature` is invoked **prior** to `parseJsonBody`.
  If the payload is malformed JSON (e.g. `{not json`), but the signature is invalid or mismatched, the router returns `401 Unauthorized` (`"webhook signature mismatch"`), never `400 Bad Request`.
  Only after the cryptographic signature, timestamp freshness, and nonce checks pass does `parseJsonBody` execute. If the body is malformed JSON at that point, it returns `400 Bad Request` and consumes the nonce so that the delivery attempt cannot be retried with the same nonce.

### 3.2 Timestamp Bounds & Freshness
- **Assertion:** Requests older than 300s or in the future by >300s are rejected.
- **Finding: CONFIRMED.**
  - `WEBHOOK_TOLERANCE_SECONDS = 300`.
  - Negative values, floating point numbers (`"12.5"`), scientific notation (`"1e9"`), and non-digit strings are rejected by `/^\d+$/` with `401 Unauthorized`.
  - Exact boundary behavior: `now - 300s` is accepted; `now + 300s` is accepted; `now - 301s` and `now + 301s` are rejected with `401 Unauthorized` (`"webhook timestamp outside tolerance window"`).

### 3.3 Replay Protection & The Nonce-Substitution Exploit
- **Assertion:** Replaying an identical nonce within the tolerance window must fail.
- **Finding: PARTIALLY MET / CRITICAL DEFECT DISCOVERED.**

#### A. Identical Nonce Replay
When a caller submits the exact same nonce twice:
- First request succeeds (200 OK).
- Second request fails with `"webhook replay detected: nonce already used"`.
- However, the response status is **401 Unauthorized**, whereas the directive specified **409 Conflict**.

#### B. The Nonce Substitution Vulnerability (Exploit Proof-of-Concept)
In `router.ts:254`:
```typescript
const expected = await hmacSha256Hex(config.secret, `${timestamp}.${rawBody}`);
```
The signature covers **only** `timestamp` and `rawBody`.
The `x-webhook-nonce` is verified separately via `config.replayGuard.admit(nonce)` (`router.ts:259`).

Because the signature does not bind the nonce, an eavesdropper who observes a legitimate webhook request (e.g., in transit, via compromised intermediate proxies, or in delivery logs) can replay the identical `rawBody` and `x-webhook-timestamp` alongside a newly generated `x-webhook-nonce`:
```
POST /events/push
x-webhook-timestamp: 1700000000
x-webhook-nonce: attacker-fresh-nonce-001
x-webhook-signature: sha256=<original_hmac>
<original_body>
```
Verification trace:
1. `rawBody` and `timestamp` match the signature -> HMAC check **passes**.
2. `attacker-fresh-nonce-001` has never been seen by `MemoryReplayGuard` -> `admit()` returns **true**.
3. Replay succeeds!

This was verified via an independent probe script (`.local/scratch/webhook-auth-review/nonce-bypass-probe.mjs`):
```
Req 1 (legitimate): true
Req Replay (same nonce): false (webhook replay detected: nonce already used)
Req Attacker (replayed body & timestamp with different nonce): true [EXPLOIT SUCCEEDS]
```
**Impact:** The nonce guard currently prevents only accidental client retries with identical headers; it provides **zero cryptographic protection against adversarial replay attacks** within the 300-second window.

### 3.4 500 Internal Error Redaction
- **Assertion:** Unhandled internal errors return a fixed generic message without leaking stack traces or internal secrets.
- **Finding: CONFIRMED.**
  In `router.ts:325-339` (`errorResponse`):
  Unhandled errors that do not match the explicit allowlist regex for 400 (caller syntax/validation errors) or 404 (unknown task/warning) are assigned status 500.
  When status is 500:
  ```typescript
  if (status === 500) {
    return json({ error: "internal server error" }, 500);
  }
  ```
  Tests verified that simulated network errors containing connection strings, internal paths, and stack lines are stripped completely, returning exactly `{ "error": "internal server error" }`.

---

## 4. Mutation Testing & Kill Log

Four targeted semantic mutants were applied to `prototype/src/core/router.ts`. All four were compiled via `tsc -p tsconfig.node.json` and executed against the test suite under strict environment isolation.

| Mutant ID | Targeted Logic | Mutation Applied | Test Suite Response | Result |
|---|---|---|---|---|
| **M1** | Signature Verification | `if ((!timingSafeEqual(expected, match[1])) && (1 as number) === 2)` | 4 tests failed with AssertionError: `tampered body fails HMAC`, `signature from different secret`, `replay guard only records FULLY verified deliveries`, `signed envelope accepted on /events/artifacts; wrong secret 401` | **KILLED** |
| **M2** | Replay Nonce Check | `if ((!config.replayGuard.admit(nonce)) && (1 as number) === 2)` | 2 tests failed with AssertionError: `duplicate nonce rejected as replay`, `malformed JSON with a VALID signature is 400; the nonce was consumed` | **KILLED** |
| **M3** | Timestamp Tolerance | `if ((Math.abs(nowSeconds - Number(timestamp)) > toleranceSeconds) && (1 as number) === 2)` | 2 tests failed with AssertionError: `timestamp tolerance boundary — ±300s accepted, ±301s rejected`, `replay guard only records FULLY verified deliveries` | **KILLED** |
| **M4** | 500 Error Redaction | `return json({ error: message }, 500);` | 1 test failed with AssertionError: `unexpected internal failure returns a fixed 500 body (no message, no stack)` | **KILLED** |

### Surviving Mutation Analysis
- **Surviving Mutant (M5 - Nonce Exclusion in HMAC):**
  If the HMAC computation is changed to include or exclude headers, no test fails because no test asserts that modifying the nonce breaks the signature. The test suite only exercises identical-nonce replay and different-secret failure.

---

## 5. Architectural & Performance Observations

1. **`MemoryReplayGuard` Sweep Overhead:**
   In `MemoryReplayGuard.admit` (`router.ts:140-159`):
   ```typescript
   for (const [key, expiresAt] of this.seen) {
     if (expiresAt <= now) {
       this.seen.delete(key);
     }
   }
   ```
   On every call to `admit()`, the method iterates through all entries in `this.seen` (up to 10,000 entries). Because JavaScript `Map` preserves insertion order and nonces are added chronologically with a fixed TTL, older entries are always at the beginning. An optimization would be to break early upon encountering the first entry where `expiresAt > now`, avoiding an O(N) traversal on every webhook delivery.
2. **Code Placement:**
   The authentication logic (`MemoryReplayGuard`, `verifyWebhookSignature`) belongs logically in `src/core/auth.ts`, alongside `timingSafeEqual`, `decideBearer`, and `decideMutatingAuth`, keeping `router.ts` purely as the HTTP routing dispatcher.

---

## 6. Required Changes for Acceptance

To achieve unconditional approval (`ACCEPT`), the following changes are required:

1. **Bind Nonce in HMAC Payload:**
   Update the sender contract and verification signature to:
   ```typescript
   const expected = await hmacSha256Hex(config.secret, `${timestamp}.${nonce}.${rawBody}`);
   ```
   This cryptographically binds the nonce to the signature, rendering replay attacks via modified nonces impossible.
2. **Harmonize Replay Status Code:**
   In `verifyWebhookSignature`, return `409 Conflict` (or document the deliberate design deviation if 401 is preferred):
   ```typescript
   if (!config.replayGuard.admit(nonce)) {
     return deny(409, "webhook replay detected: nonce already used");
   }
   ```
   Note: update `WebhookSignatureDecision` type union to accept `401 | 409 | 503`.
3. **Add Negative Test for Nonce Substitution:**
   Add a test verifying that replaying a valid body and timestamp with an altered nonce fails with `401 Unauthorized` (signature mismatch).

# Independent Security & Verification Review: Webhook Sender Auth Remediation commit 98ce83d

- **Reviewer:** independent Webhook Auth Reviewer, tag `webhook-auth-reviewer`
- **Dispatched by:** `antigravity-head` (`46fdb644`), under Codex Principal C1462 Task 3 / C1497 rebalance directive
- **Commit under review:** `98ce83d` — "fix(auth): bind nonce in HMAC webhook signature, return 409 on replay, relocate to auth.ts (REV-WEBHOOK-AUTH-F3F06D2)"
- **Workspace:** `/home/alexey/git/agent-branches-webhook` (branch `proto/webhook-auth`)
- **Date of review:** 2026-10-04 (Europe/Berlin)
- **Artifacts reviewed:**
  - `prototype/src/core/auth.ts` (relocated `MemoryReplayGuard`, `hmacSha256Hex`, `WEBHOOK_TOLERANCE_SECONDS`)
  - `prototype/src/core/router.ts` (re-exports, updated HMAC payload, early nonce guard, 409 Conflict status)
  - `prototype/test/node/webhook-auth.test.ts` (updated sender contract, 409 assertion, new nonce substitution test)

---

## 1. Overall Verdict: ACCEPT

Commit `98ce83d` cleanly and completely remediates all issues identified in `REV-WEBHOOK-AUTH-F3F06D2`:

1. **Vulnerability Closed (Nonce Substitution Replay):**
   The HMAC-SHA256 signature payload now binds `${timestamp}.${nonce}.${rawBody}` (`router.ts:197`). An eavesdropper attempting to replay an intercepted webhook under a synthetic fresh nonce immediately fails HMAC verification with `401 Unauthorized` (`"webhook signature mismatch"`).
2. **Specification Compliance (409 Conflict on Replay):**
   Identical-nonce redelivery within the tolerance window returns `409 Conflict` with the structured response body `{ "error": "conflict", "message": "webhook replay detected: nonce already used" }` (`router.ts:203`).
3. **Early Shape Gate:**
   Missing, empty, or oversized `x-webhook-nonce` headers are rejected with `401 Unauthorized` (`router.ts:185-188`) **before** any WebCrypto HMAC operations are performed, preventing unnecessary computational overhead.
4. **Clean Architecture:**
   `MemoryReplayGuard`, `hmacSha256Hex`, and `WEBHOOK_TOLERANCE_SECONDS` have been relocated to `src/core/auth.ts`, alongside all other authentication primitives, and are cleanly re-exported by `src/core/router.ts`.
5. **Comprehensive Automated Test Coverage:**
   The entire test suite across Node, Cloudflare Vitest, and the Git smart HTTP sidecar passes with zero failures (155/155 tests green).

---

## 2. Remediation Inspection & Analysis

### 2.1 Cryptographic Binding of Nonce
In `prototype/src/core/router.ts` (lines 68–75, 197):
```typescript
const expected = await hmacSha256Hex(config.secret, `${timestamp}.${nonce}.${rawBody}`);
if (!timingSafeEqual(expected, match[1])) {
  return deny(401, "webhook signature mismatch");
}
```
The signature binds the exact timestamp, the exact nonce, and the exact raw request bytes. Any tampering with the nonce changes the expected HMAC digest, ensuring that stolen signatures cannot be redeployed with fresh nonces.

### 2.2 Missing Nonce Gate (Pre-HMAC)
In `prototype/src/core/router.ts` (lines 185–188):
```typescript
const nonce = request.header("x-webhook-nonce");
if (nonce === null || nonce.length === 0 || nonce.length > 256) {
  return deny(401, "webhook nonce header (x-webhook-nonce) is required");
}
```
This check is situated immediately after timestamp freshness verification and replay guard availability check, but **before** the signature format check and HMAC computation. Senders omitting the nonce fail immediately without triggering cryptographic calculations.

### 2.3 HTTP 409 Conflict on Replay
In `prototype/src/core/router.ts` (lines 162–166, 202–204):
```typescript
const deny = (status: 401 | 409 | 503, error: string, message?: string): WebhookSignatureDecision => ({
  ok: false,
  status,
  body: message === undefined ? { error } : { error, message },
});

if (!config.replayGuard.admit(nonce)) {
  return deny(409, "conflict", "webhook replay detected: nonce already used");
}
```
A delivery with an already-admitted nonce is rejected with HTTP status **409 Conflict** and payload:
```json
{
  "error": "conflict",
  "message": "webhook replay detected: nonce already used"
}
```
This correctly distinguishes duplicate submission conflicts from bad authentication credentials.

### 2.4 Modular Code Relocation
In `prototype/src/core/auth.ts`:
- `WEBHOOK_TOLERANCE_SECONDS` (line 120)
- `WebhookReplayGuard` interface (line 123)
- `MemoryReplayGuard` class (line 133)
- `HmacSubtle` structural interface & `hmacSha256Hex` function (line 184, 193)

In `prototype/src/core/router.ts` (lines 27–32):
```typescript
export {
  hmacSha256Hex,
  MemoryReplayGuard,
  WEBHOOK_TOLERANCE_SECONDS,
  type WebhookReplayGuard,
} from "./auth.js";
```
This centralizes all authentication and cryptographic logic into `auth.ts` while preserving full backwards compatibility for router consumers.

---

## 3. Negative Probe Verification: Nonce Substitution Exploit Closed

The independent probe script (`.local/scratch/webhook-auth-review/nonce-bypass-probe.mjs`) was executed against the compiled runtime.

### Probe Results
```
Req 1 (legitimate): true ACCEPTED
Req Replay (same nonce): false status=409 {
  error: 'conflict',
  message: 'webhook replay detected: nonce already used'
}
Req Attacker (replayed body & timestamp with different nonce): false status=401 { error: 'webhook signature mismatch' }
```

### Exploit Verification Summary
- **Legitimate Request**: Passes signature verification and is admitted (`ok: true`).
- **Direct Replay (identical nonce)**: Rejected with HTTP `409 Conflict` and structured conflict message.
- **Attacker Replay (substituted nonce)**: Attacker attempts to replay the valid delivery with `x-webhook-nonce: attacker-nonce-2`. Because the signature was computed over `legit-nonce-1`, the server recomputes the HMAC over `attacker-nonce-2`, resulting in a mismatch. The attack is **blocked at the signature gate with HTTP 401 Unauthorized**.

The nonce substitution replay vulnerability is **fully closed**.

---

## 4. Test Suite Execution & Results

All test suites were executed under invariant resource controls (`TMPDIR=.local/scratch/webhook-auth-review/`, `NODE_OPTIONS="--max-old-space-size=1500"`, `GIT_TERMINAL_PROMPT=0`):

| Test Suite | Command | Result | Tests Passed | Notes |
|---|---|---|---|---|
| Node Router Suite | `npm run test:node` | **PASS** | 48 / 48 | Includes new `nonce SUBSTITUTION fails the HMAC` test |
| Sidecar Git Suite | `npm run test:sidecar` | **PASS** | 16 / 16 | Smart HTTP & callback retry suites pass cleanly |
| Cloudflare Vitest Suite | `npm test` | **PASS** | 91 / 91 | 13 test files passed; zero regressions |
| **Total Test Count** | | **PASS** | **155 / 155** | **100% Green** |

---

## 5. Invariants & Environment Verification

- **Workspace hygiene**: Zero unmanaged `/tmp` growth (`TMPDIR` pointed to `.local/scratch/webhook-auth-review/`).
- **Memory consumption**: Strict adherence to the 1500M memory limit.
- **Git working tree**: `/home/alexey/git/agent-branches-webhook` working directory is completely clean (`git status --short` is empty).
- **Concurrency & Locking**: Committed with `flock /home/alexey/git/cloudflare-agent-git/.local/git.lock`.

# Independent Review: Auth Reads (2302d70) & UI Integration (66d48b7)

- Reviewer: muse-reviewer-auth-ui (antigravity-head delegate 46fdb644)
- Date: 2026-10-04
- Scope A: commit `2302d70` on `proto/auth-reads` (`/home/alexey/git/agent-branches-auth-reads`)
- Scope B: commit `66d48b7` on `proto/l4-review-ui` (`/home/alexey/git/agent-branches-l4`)
- Verdict: **ACCEPT** (both commits; one non-blocking observation + one test-invocation note)

## 1. Scope A — commit 2302d70 (read auth)

### 1.1 `decideReadAuth` (`prototype/src/core/auth.ts:143-166`)

Verified by direct read of the implementation:

- `presented === null` (missing header, wrong scheme, bare `Bearer`) → shared
  401 `{error: "unauthorized", message: "Missing or invalid bearer token"}` (`READ_AUTH_UNAUTHORIZED`, lines 119-122). Indistinguishable failure causes — correct.
- Admin match first (`tokensMatch` over SHA-256 digests, constant-time) → `ok`.
- Runner match **only when `opts.agent === undefined`** (unnarrowed `/status`) → `ok`. Runner on a narrowed task read falls through to `credentialAgent`, which returns null for it → 401. Correct per CONTRACT.
- Otherwise `credentialAgent(presented)` — the coordinator gate that denies revoked (`revokedAt != null`, incl. `""`), expired (**at** the instant, `nowMs >= expiryTime`), and unparsable-expiry tokens (`coordinator.ts:553-569`) — applies to reads exactly as to writes by construction (shared code path, not a reimplementation). Correct.
- `owner === opts.agent` (or unnarrowed) → `ok`; valid token for a different agent → 403 with owner names, never the token. Correct.
- Sidecar webhook bearer is never matched (no `allowSidecar` branch) and is not an agent-token digest, so it lands in the shared 401. Correct; confirmed behaviorally (§3).
- Unconfigured admin does not 503 reads: `tokens.admin && ...` short-circuits, unauthenticated callers get 401. Matches the documented intent (no secret-existence oracle).

### 1.2 Router wiring (`prototype/src/core/router.ts:263-294`)

- `GET /status` → `requireReadAuth(request, services)` (no narrowing) before `coordinator.status()`. Correct.
- `GET /tasks/:id` → `taskOwner(taskId)` first (returns null for unknown, no existence leak — it is a pure model lookup), then `requireReadAuth(..., owner === null ? {} : {agent: owner})`, then `getTask` with 404 mapping. Auth resolves before existence:
  - anonymous + unknown id → 401 (confirmed: `anon unknown -> 401`);
  - admin + unknown id → 404 (confirmed);
  - any valid agent token + unknown id → 404 (suite-pinned).
- `deniedOrOk` renders the two-field body only when `message` is present, so mutating-route single-field bodies are untouched. Correct.

### 1.3 Expiry / revocation semantics

Inherited from `credentialAgent` (`coordinator.ts:553-569`), previously reviewed gates (C-1422/C-1425/C-1430/C-1437). Suite pins: negative-TTL mint → 401 on reads; admin-revoked token → 401 on reads. Both confirmed passing (§3). The "denied at the exact instant" boundary is shared code, no read-specific clock skew introduced (`Date.now()` default, same as writes).

### 1.4 CONTRACT.md

Change 5 documents the breaking change, supersedes "read routes stay open", updates the env table (`ADMIN_TOKEN` covers reads, `RUNNER_TOKEN` covers `GET /status`) and both route sections. Accurate relative to the implementation.

## 2. Scope B — commit 66d48b7 (UI auth)

### 2.1 `prototype/ui/auth.js` (new, 216 lines)

Pure helper module, no DOM/fetch/storage coupling (storage injected — same file loads under `node --test` and in the browser). Verified:

- `normalizeToken`: trims, null on blank/non-string → never sends `Authorization: Bearer <empty>`.
- `authHeaders`: `{}` when no token, else `Bearer <trimmed>`. Fixture reads bypass it (`FIXTURE ? {} :` in ui.js).
- `authFailureKind`/`isAuthFailure`: only 401/403 are auth failures; 503 (and all else) → null, so the stale-error path keeps owning outages. Correct separation.
- `httpError` preserves the historical `"request failed: HTTP <status> for <url>"` message and adds `status`/`authKind`; 403 also carries raw `bodyText` (ui.js). Message never carries token or body.
- `parseForbiddenOwner` regex matches the exact server 403 shape `forbidden: this token belongs to <owner>, not <expected>` incl. trailing JSON-envelope `"}`, returns null otherwise. Verified compatible against a live server-shaped body (§3: `{"error":"forbidden: this token belongs to bob-0002, not alice-0001"}` parses to `{owner: bob-0002, expected: alice-0001}` — same shape the vitest suite asserts).
- `describeUnauthorized` / `describeForbidden`: fixed strings, token never echoed (suite asserts non-containment of a canary secret).
- `createAuthState`: 401 raises `needsToken` and drops stale refusal; 403 records diagnostic and drops prompt; `setToken` clears both flags (retry-clean); `markOk` clears both. Sound.
- `STORAGE_KEY` lives only in auth.js; ui.js reaches storage solely through the Auth module (tripwire asserts `ui.js` does not contain the key).

### 2.2 `prototype/ui/ui.js` + pages

- Single `fetchJson` carries the bearer header on **both** live reads (`API + "/status"`, `API + "/tasks/" + id`); fixture reads stay bare. 403 captures `bodyText` for the diagnostic. Correct — no read path bypasses auth.
- 401 → `markUnauthorized` (token prompt) + stale downgrade retained; 403 → `markForbidden(describeForbidden(...))`; success → `markOk`. Nothing renders clean while unauthenticated (401/403 branches run before `markFresh`). Correct.
- Auth markup (`#auth` form, `#auth-prompt`, `#auth-forbidden`, `#auth-status`) ships hidden+empty in both pages, `auth.js` loads before `ui.js`; input is `type="password"`; strings set via `textContent`; input prefilled once at wiring so re-renders never wipe typing. No hydration mismatch, no token rendering (`innerHTML`+token pattern absent, no `console.log`).
- Blocked-storage tolerance: every storage access wrapped, session-state fallback. Suite-pinned.

### 2.3 Compatibility verdict (does 66d48b7 satisfy the 2302d70 wire contract?)

Yes, fully:

| Wire event (2302d70) | UI handling (66d48b7) |
|---|---|
| 401 + `{error, message}` on missing/invalid/expired/revoked/sidecar/foreign-runner | `authKind "unauthorized"` → prompt + auto-retry on save; message shape preserved for display |
| 403 + `forbidden: ... belongs to X, not Y` on foreign agent token | `authKind "forbidden"` + `bodyText` → owner-naming diagnostic with concrete fix |
| 404 on valid-credential unknown id | not an auth failure → normal error path (unchanged behavior) |
| 503 outage | not an auth failure → stale-error path (unchanged behavior) |
| Runner token accepted on `/status` only | UI sends whatever token is saved; server decides — no client-side role assumption |

## 3. Test matrix

| # | Check | Command / probe | Result |
|---|---|---|---|
| 1 | Auth-reads node suite (incl. new C1462 Task 1 matrix: negatives 1–5, positives 1–2, ladder extras) | `npm run test:node` in `agent-branches-auth-reads/prototype` | **30/30 pass** |
| 2 | UI auth vitest suite (19 tests: storage, headers, 401/403, state machine, wiring tripwires) | `npx vitest run test/ui-auth.test.ts` in `agent-branches-l4/prototype` | **19/19 pass** |
| 3 | Sidecar bearer on `GET /status` | ad-hoc probe vs built router | 401 + shared body ✅ |
| 4 | Garbage token on `GET /status` | ad-hoc probe | 401 + shared body ✅ |
| 5 | Empty-string token on `GET /status` | ad-hoc probe | 401 + shared body ✅ |
| 6 | Runner token on `GET /tasks/:id` | ad-hoc probe | 401 ✅ (narrowed reads reject runner) |
| 7 | Foreign agent token on `GET /tasks/:id` | ad-hoc probe | 403 `forbidden: ... belongs to bob-0002, not alice-0001` ✅ |
| 8 | Anonymous `GET /tasks/task-9999` (auth-before-404) | ad-hoc probe | 401 ✅ (no id probing) |
| 9 | Admin `GET /tasks/task-9999` | ad-hoc probe | 404 `unknown task` ✅ |
| 10 | 403 body → UI `parseForbiddenOwner` shape | server-shaped string vs UI regex (suite `parseForbiddenOwner` test + §2.1) | parses ✅ |

Note on invocation: the task brief's literal command `node --test prototype/test/node/router.test.ts` does **not** work — the TS sources must first be built (`npm run build:node`); the repo's documented entry is `npm run test:node` (build + run built `.build/node/test/node/*.test.js`). All 30 tests pass through that path; the brief's command fails with `ERR_MODULE_NOT_FOUND` for `router.js`, which is an invocation artifact, not a code defect.

Mutation-style coverage (behavioral, ad-hoc): flipped-credential probes (sidecar/garbage/empty/runner-on-narrowed) all collapse to the identical shared 401 body — no oracle distinguishes failure causes; foreign-agent reads are the sole 403 path and carry owner names the UI parses. The one unpinned branch is sidecar-on-read (no dedicated test asserts it; verified here ad-hoc instead — see observation O1).

## 4. Findings

- O1 (non-blocking, test-gap): no committed test pins "sidecar bearer on a read route → shared 401". Behavior is correct by construction (no `allowSidecar` branch + digest miss) and verified ad-hoc in this review, but a one-line addition to the `read auth` matrix would lock it. Suggested: `strictEqual((await call(rig, "GET", "/status", undefined, "sidecar-t")).status, 401)`.
- O2 (invocation note): brief's literal node-test command needs the build step; use `npm run test:node`.
- No defects found in: token ladder ordering, 401/403 status selection, body shapes, auth-before-existence, expiry/revocation inheritance, UI header wiring, 401/403 state transitions, token non-echo, fixture-mode exemption, blocked-storage fallback.

## 5. Verdict

**ACCEPT** — commit `2302d70` and commit `66d48b7` both meet their contracts; the UI implementation fully satisfies the server wire contract; suites green (30/30 node, 19/19 vitest) plus 8/8 ad-hoc behavioral probes. Recommended follow-up (not a merge blocker): add the sidecar-on-read 401 pin (O1).

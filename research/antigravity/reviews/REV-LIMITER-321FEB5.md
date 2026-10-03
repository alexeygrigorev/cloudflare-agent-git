# REV-LIMITER-321FEB5 — Independent negative security review & mutation test

**C-1441 bounded invalid-bearer rate limiter** (`prototype/src/core/router.ts`)
**Reviewer:** independent Space Bunny reviewer, tag `sb-limiter-reviewer` (not the author, not a self-approval)
**Dispatched by:** antigravity-head `46fdb644`, under Codex Principal C1462 directive:
"2 independent Space Bunny review actual limiter 321feb5/a205 source for residual old-map growth / fail-open and spoof key bounds, not self approval"
**Date:** 2026-10-04 (Europe/Berlin)
**Branch / commits reviewed:** `proto/ab-adoption` @ `321feb5` (limiter), tree at `a2055e3`
**Workspace:** `/home/alexey/git/agent-branches-adopt`

---

## 1. Verdict

**REQUEST_CHANGES** — narrow and cheap to clear.

Two blocking items, both **test-suite** defects, no exploitable defect found in the shipped code:

- **B1 (blocking).** The client-key **trust boundary is covered by zero tests.** Two mutants that repoint the limiter key at the spoofable `X-Forwarded-For` header — a *complete, silent* rate-limit bypass — **survive the entire suite** (36/36 node + 92/92 vitest green). Proven twice, in both adapters, with an independent detector showing the bypass is real.
- **B2 (blocking).** `test/node/core.test.ts:461` claims in a comment to exercise "exactly at the window edge". It does not: the arithmetic lands 15 s **past** the edge, so `>=` vs `>` on the window boundary is unconstrained. The mutant changing `>=` to `>` **survives**. A security-relevant boundary is asserted in prose but not in fact.

**The three hypotheses in the directive are DISPROVEN against the shipped code:**

| Directive hypothesis | Finding |
| --- | --- |
| residual old-map growth / memory leak | **Not present.** Hard cap holds at 200 000 unique keys; retained table ≈ 118 KB. |
| fail-open on failed IP extraction / empty / malformed header | **Fails CLOSED** for unidentified clients (one conservative shared bucket). One separate fail-*open* seam exists: `RouterServices.rateLimiter` is optional and its absence disables the control silently (all shipped adapters inject it). |
| `X-Forwarded-For` spoofing | **Not present.** No adapter reads any client-supplied forwarding header. Verified by probe *and* by mutation. |

Non-blocking hardening items (D1–D7) are in §7. Nothing here requires re-architecting the limiter; B1/B2 are two small tests plus one arithmetic fix.

---

## 2. Method & baseline

- Read the full limiter (`router.ts:67-206`), both adapters (`cloudflare/worker.ts:37`, `local/runtime.ts:51`), the wiring (`local/main.ts:56`), and all limiter tests (`test/node/core.test.ts:449-521`, `test/node/router.test.ts:292-355`, `test/auth.test.ts:299-329`).
- Baseline, before any mutation: `npx vitest run` → **13 files / 92 tests passed** (36.4 s); `npm run test:node` → **36/36 passed**. **128 tests green.**
- **14 semantic mutants** applied (M1–M14), each reverted immediately after its run.
- **Independent probes** written from scratch against the *compiled* build (`probe-core.mjs`, `probe-node-adapter.mjs`) and against the *real* Worker via `SELF.fetch` (temporary `test/zz-sb-review-probe.test.ts`, since removed). Probes live in scratch, never in `prototype/`.

### Invariants honored

| Invariant | Evidence |
| --- | --- |
| Zero `/tmp` allocations | All scratch under `/home/alexey/git/cloudflare-agent-git/.local/scratch/sb-limiter-review/`; every subprocess ran with `TMPDIR` set there. |
| Memory cap 1500M | `NODE_OPTIONS=--max-old-space-size=1500` on all harness subprocesses; probes run with `--max-old-space-size=1500`. |
| No permanent source modification | Harness restores pristine copies of all three touched files after every mutant. Final state: `git status --short` → only untracked `prototype/node_modules`; `git diff HEAD -- prototype/src prototype/test` → **empty**. Suites re-run green after restore (36 + 92). |

*(Unrelated process note, not a code defect: `research/antigravity/adoption/ADOPTION-RUN-REPORT.md:29` records the author's run using `/tmp/ab-adoption-run/`; the repo convention is the assigned `TMPDIR`. My own review used none.)*

---

## 3. Residual old-map growth / memory leak — **DISPROVEN**

`router.ts:99,137-143` keeps one `Map<string, FailureEntry>` with a `delete`+`set` recency refresh and a `while (size > maxEntries)` eviction loop (default 500).

| Probe | Result |
| --- | --- |
| 200 000 unique spoofed client keys | `size === 500` (cap never exceeded) |
| Retained heap after those 200 000 inserts, GC settled | **+118 232 B** total; `external` +40 B |
| 5 000 unique keys (author's own measurement, for cross-check) | 500 entries, ≈178 B/client — consistent with mine |
| Entries after the window expired 10 min ago | 5 retained (no TTL sweep) |

**Verdict: bounded, no leak.** Worst case ≈ 0.12 MB per limiter instance, which matches the author's claim and closes the "unbounded per-IP map" DoS surface.

Measurement caveat worth recording: my first run without `--expose-gc` showed a **10.2 MB** delta, which is uncollected garbage, not retention. Anyone re-measuring must settle GC or they will overstate the footprint by ~80×.

**Real (low-severity) consequences of the design, both inherent to cap-with-eviction:**

- **D1 — no TTL sweep.** Expired-but-retained entries occupy the table until churn evicts them. Harmless at 500 entries, but the table can be *permanently* topped up with 500 stale keys by one flood, so the eviction order is attacker-influenceable.
- **D2 — eviction resets live counters (verified).** Probe A6: 5 failures on `10.9.9.9`, then 600 junk keys, then the 6th failure on `10.9.9.9` returns **`false`** — the hot entry was evicted and the count restarted. An attacker who can source 500 distinct keys can wipe their own (or a co-located victim's) accumulated count at will. Self-rotation makes this mostly redundant for the attacker, so severity is low; it is a real counter-reset primitive, not just a memory bound.

---

## 4. Fail-open vs fail-closed — **fail-closed for unidentified clients, one real fail-open seam**

`router.ts:126` collapses a null key to `UNKNOWN_CLIENT_KEY`; `authedOutcome` (`router.ts:182-206`) only counts `401` and only blocks from the `(maxFailures+1)`-th consecutive one.

| Probe | Result | Reading |
| --- | --- | --- |
| A3 — 6 invalid bearers with `clientKey: null`, then a *different* real client's request | `401,401,401,401,401,429` then victim `429` | unidentified clients **share one bucket** → limiting still applies (**fail-closed**) |
| A7 — `clientKey: ""` vs `null` | `""` bucket armed, `null` bucket did not; `size === 2` | empty string is a **second, separate** bucket (`??` does not catch `""`) |
| A9 — header shapes `undefined`, `""`, `Bearer`, `Bearer `, `Basic abc` | all `401` **and counted**; 6th well-formed attempt → `429` | **no free attempts** via header shape; `bearerFrom` lowercases the prefix and trims (`auth.ts:51-56`) |
| A13 — 8 × `503` (unconfigured secret) | `size` unchanged, next `401` | server-state failures are not charged to the client (correct) |
| **A8 — `services.rateLimiter` omitted** | **50 invalid bearers → `401` × 50, never `429`** | **FAIL-OPEN SEAM** |

**D3 (the one true fail-open path).** `RouterServices.rateLimiter` is optional (`router.ts:64`) and `authedOutcome` returns the denial un-counted when it is absent (`router.ts:188-190`). Today both real adapters inject it (`cloudflare/worker.ts:65`, `local/main.ts:56`), so the shipped system is not fail-open — but a third adapter, a test rig, or a refactor that drops the field silently loses the entire control with **no error, no log, no type error**. This is a *latent* fail-open, and it is the one finding I would call a genuine (if low-likelihood) fail-open rather than a hardening nicety. The author's own report already notes the optional field as a rig-compatibility concession, so this is a known trade-off — it just deserves a loud signal instead of silence.

**D4 (availability hazard, medium).** The conservative shared bucket is fail-closed in the *wrong direction* for availability: in any runtime that cannot identify clients, **six** invalid bearers from one attacker lock out **every other** unidentified client for the rest of the window (probe A3). Mitigating factor, verified in probe A12 / N3: one successful authenticated request clears the bucket, so a legitimately configured victim self-heals immediately. Unmitigated for a victim who has no valid credential to present.

**D5 (per-isolate, documented).** The Worker instance is module-scope (`worker.ts:15`), so the budget is **per isolate**: isolate recycling resets counts and multi-PoP/isolate fan-out multiplies the attacker's budget by the number of isolates it reaches. `ADOPTION-RUN-REPORT.md:23` states this limitation honestly and correctly. I confirm it; I do not count it as a defect at prototype tier.

---

## 5. Spoof key bounds — **no header spoofing; two implicit, untested trust assumptions**

Extraction is exactly two lines, and neither reads a client-settable header:

- `cloudflare/worker.ts:37` → `request.headers.get("cf-connecting-ip")`
- `local/runtime.ts:51` → `request.socket?.remoteAddress ?? null`

Repo-wide search for `x-forwarded|true-client|x-real-ip|connecting-ip|remoteAddress` finds **no** other use. Empirically, against the **real Worker** via `SELF.fetch`:

| Probe | Result | Reading |
| --- | --- | --- |
| P3 — six invalid bearers, six **distinct `X-Forwarded-For`** values | `401×5, 429` | XFF is **not** the key. No spoofable-header bypass. |
| P2 — six invalid bearers, six **distinct `cf-connecting-ip`** values | `401 × 6`, never `429` | **the client-supplied `cf-connecting-ip` header is honored verbatim as the bucket key** |
| P4 — flood `cf-connecting-ip: 203.0.113.77` to `429`, then one request from `203.0.113.88` | `401` | bucket isolation is real (no cross-client leakage) |
| Node probe N1 — six invalid bearers, six distinct XFF, real `node:http` server | `401×5, 429` | XFF ignored; socket peer address is the key |

**D6 (medium, architectural).** The Worker trusts `cf-connecting-ip` **unconditionally**. That is safe *only* because Cloudflare's edge overwrites that header, so the Worker is unreachable except through the edge. P2 shows the code itself enforces nothing: any deployment path that reaches the Worker without edge normalization — `wrangler dev`, a tunnel or reverse proxy that forwards the header, a future non-Cloudflare target, or a future "trust `X-Forwarded-For` when behind a proxy" convenience change — converts the limiter into **no limiter at all**, and (see B1) **the test suite would not notice**. The comment `// the edge always provides the real client IP` (`worker.ts:36`) is an *assumption*, not an invariant, and it is exactly the assumption that is untested.

**D7 (medium, by design).** The key is the exact address string — no prefix aggregation. Verified bypasses, no privileges beyond a normal attacker:

- **IPv6 /64 rotation:** 12 consecutive invalid bearers from 12 addresses in one `2001:db8:1234:5678::/64` → **0 of 12 armed** (probe A4). A single residential IPv6 prefix is an unlimited key supply.
- **IPv4 rotation:** 50 attempts, one source each → **never blocked** (probe A5).

Neither is a *bug* in the shipped code — the control is documented as a per-client-key flood blunter — but "5 failures per address" is a much weaker guarantee than "5 failures per attacker" against exactly the attacker population (botnets, cloud ranges, IPv6) that brute-forces bearers. If a stronger claim is ever made in the CONTRACT or on the public site, this is the gap that makes the claim false.

**D8 (low).** `retry-after` is the static `retryAfterSeconds` (default 60) regardless of the window actually remaining: probe A11 arms the block with 1 000 ms of window left and still advertises `60`. Honest clients are told to wait ~59 s too long. Low impact; trivially fixed by computing from `firstFailureAt`.

**D9 (low, expectation-setting).** The block is evaluated **after** `decideBearer`, so a blocked client still pays full auth cost per request (2 × SHA-256 + constant-time compare). Probe A14: 2 000 blocked requests in 161 ms (~80 µs each) — identical cost to the 401 path. The limiter therefore provides **no CPU relief** against a flood; it only changes the answer from `401` to `429`. That is a legitimate design for an anti-guessing control, but it should not be described as DoS mitigation. (D1 is the actual memory-DoS mitigation, and it works.)

---

## 6. Mutation log — 14 mutants, 11 killed, 3 survived

Baseline for every row: 36/36 node + 92/92 vitest. A mutant is **KILLED** if any suite fails; a **COMPILE_ERROR** kill is reported separately because it proves nothing about test strength.

| ID | Mutation (file) | Verdict | Killed by |
| --- | --- | --- | --- |
| **M1** | `router.ts:198` — 429 gate `&& limiter.size > 1_000_000` (bypass) | **KILLED** | `router.test.ts` *"invalid-bearer flood: 5x401 then 429"* |
| **M2a** | `maxFailures` default `5 → 10` (raise burst limit) | **KILLED** | `core.test.ts` *"5-failure threshold arms the block on the 6th"* |
| **M2b** | `windowMs` default `60_000 → 6_000_000` (kill the window) | **KILLED** | `core.test.ts` *"failures outside the 60s window restart the count"* |
| **M3** | `clientKey ?? UNKNOWN_CLIENT_KEY → "fixed"` (IP extraction bypass) | **KILLED** | `core.test.ts` *"5-failure threshold arms on the 6th"* |
| **M4** | `count: existing.count + 1 → existing.count` (no increment) | **KILLED** | `core.test.ts` *"5-failure threshold arms on the 6th"* |
| **M5** | `while (size > maxEntries * 1e9)` (remove eviction → unbounded growth) | **KILLED** | `core.test.ts` *"the tracked-client table is hard-capped"* |
| **M6** | `recordSuccess` delete → `if (false)` (success never clears) | **KILLED** | `core.test.ts` *"successful authentication clears the failure count"* |
| **M7** | drop `if (decision.status !== 401)` (charge 403/503 too) | **KILLED** | `router.test.ts` *"403/503 outcomes are not counted"* (2 failures) |
| **M8** | `clientKey ?? \`anon-${Math.random()}\`` (**fail-open**: fresh bucket per unidentified request) | **KILLED** | `core.test.ts` *"unidentifiable clients share one conservative bucket"* + router flood test (2 failures) |
| **M9** | `local/runtime.ts:51` — key from `X-Forwarded-For` instead of `socket.remoteAddress` | **SURVIVED** ⚠ | node 36/36 **and** vitest 92/92 pass |
| **M10** | `cloudflare/worker.ts:37` — key from `X-Forwarded-For` instead of `cf-connecting-ip` | **SURVIVED** ⚠ | node 36/36 **and** vitest 92/92 pass |
| **M11** | `router.ts:130` window boundary `>= → >` (off-by-one) | **SURVIVED** ⚠ | node suite green |
| **M12** | drop `this.entries.delete(key)` (LRU → FIFO by first sighting) | **SURVIVED** ⚠ | both suites green |
| **M13** | `maxEntries` default `500 → 1_000_000` | **KILLED** | `core.test.ts` *"the tracked-client table is hard-capped"* |
| **M14** | `retryAfterSeconds` default `60 → 1` | **KILLED** | `router.test.ts` *"invalid-bearer flood"* |

*(An earlier, naive M1 written as `if (false && …)` was killed by `error TS18048`, a TypeScript narrowing error — a trivial kill that proves nothing. It was replaced by the compile-valid M1 above, which is killed by a real assertion. Recorded here because a reviewer who reports "M1 killed" without the distinction would be overstating the suite.)*

### 6.1 The three survivors, each verified as a genuine blind spot

**M9 / M10 — the trust boundary is untested (blocking B1).** Both mutants replace the key with a fully client-controlled header. Both keep every suite green — including `auth.test.ts`'s own C-1441 test and all four `core.test.ts` limiter units. My independent detectors see the bypass immediately:

| Detector | Pristine | With M9 (node adapter) | With M10 (worker adapter) |
| --- | --- | --- | --- |
| Six bad bearers, six distinct XFF | `401×5, 429` (blocked) | **`401 × 6` — never blocked** | **`401 × 6` — never blocked** (probe P3) |
| Six bad bearers, six distinct `cf-connecting-ip` | `401 × 6` (isolated) | — | **`401×5, 429`** (isolation destroyed, P2) |
| Suite verdict | 128 green | **128 green** | **128 green** |

Root cause, verified by reading the suite: **no test ever observes the client key.** `test/node/router.test.ts` injects `clientKey` directly through `neutralRequest()` (`fakes.ts:206,222`), bypassing the adapter entirely, and `test/node/local-runtime.test.ts` — the only test that exercises the real `node:http` path — makes exactly **one** unauthenticated request (line 34) and never floods. On the Worker side, `auth.test.ts` floods without any IP header, so it only ever exercises the shared `unknown` bucket and cannot tell one key-derivation policy from another. Net effect: **a refactor can delete the entire rate limit and the suite stays green**, as long as *some* bucket still fills.

**M11 — a test asserts a boundary it never reaches (blocking B2).** `core.test.ts:461-476` intends to pin the exact window edge ("The 5th failure landed exactly at the window edge: fresh count, never armed"). It does not: the loop body increments `now` **after** each `recordFailure`, so after 5 iterations at 15 s spacing the sixth call lands at **T+75 s**, 15 s *past* the 60 s edge. Instrumenting the compiled build confirms the mutant is unobservable:

```
pristine (>=) : spread returns false,false,false,false,false,false
mutant   (>)  : spread returns false,false,false,false,false,false   ← identical
```

The `tight` sub-case moves 60 001 ms, which both operators treat identically. So the boundary comparison is unconstrained by the entire suite. Impact is a 1 ms window skew (low), but the *comment* asserts a guarantee the code does not verify, which is worse than the skew.

**M12 — the LRU claim is unverified.** `router.ts:133-134` documents "Delete + set refreshes recency: Map iteration order is insertion order, so the OLDEST entry is always first for eviction", and the class docstring claims LRU. Removing the refresh (`FIFO by first sighting`) keeps every test green, because `core.test.ts:495-515` inserts `a,b,c,d,e` — a sequence where first-seen order and last-seen order produce the same victim (`a`). The recency property is real (I confirmed it in the compiled build) but unprotected.

---

## 7. Recommendations

### Blocking (clear these to accept)

- **B1 — pin the trust boundary with a test at each adapter.**
  1. *node:* in `test/node/local-runtime.test.ts` (or a new `test/node/limiter-adapter.test.ts`), start the real `serveCoordinator` server, then assert (a) six invalid bearers with six distinct `X-Forwarded-For` values **do** produce `429` on the sixth, and (b) the same for the Worker-style header. This kills M9. Use a stub `CoordinatorAccess` — the auth epilogue runs before any coordinator call, so no sidecar is needed.
  2. *worker:* in `test/auth.test.ts`, flood with six distinct `cf-connecting-ip` headers and assert `401` on all six (per-IP isolation), **and** flood with six distinct `X-Forwarded-For` headers and assert `429` on the sixth (XFF not trusted). This kills M10. Both are deterministic under `SELF.fetch` — I measured both.
  3. Re-run M9/M10 as a mutation gate; both must flip to KILLED.
- **B2 — make the window-edge test actually land on the edge.** Restructure `core.test.ts:461-476` so the sixth call happens at exactly `firstFailureAt + windowMs` (assert `false` with `>=` in place, and add the complementary `windowMs - 1` case asserting the count continues). Delete or correct the inaccurate comment. Re-run M11; it must flip to KILLED.

### Non-blocking hardening, in priority order

- **H1 (D6) — make the `cf-connecting-ip` trust explicit and enforced.** Either document it as an invariant in `CONTRACT.md` ("the limiter's client key is trustworthy only while every request traverses the Cloudflare edge, which overwrites `cf-connecting-ip`"), or add a cheap defense: ignore the header when a request arrives without edge provenance, and/or support an explicit `TRUSTED_PROXY_COUNT`/allow-list for a future proxied deployment. At minimum, add a code comment that names the assumption *and* points at the test from B1.
- **H2 (D3) — remove the silent fail-open seam.** Make `rateLimiter` required on `RouterServices` and update the minimal test rigs explicitly (the `fakes.ts` rig already injects one), or keep it optional but log a one-time warning when a 401 is served with no limiter attached. A security control should not be able to vanish without a trace.
- **H3 (D7) — aggregate keys.** Normalize IPv6 to a /64 (or /56) and IPv4 to a /24 before bucketing, or add a small global (non-per-IP) failure counter that no key rotation can dodge. If neither is in scope, state the limit honestly wherever the control is described: *5 failures per address per 60 s*, not *5 failures per attacker*.
- **H4 (D4) — de-blast the shared `unknown` bucket.** Give unidentified callers a much higher allowance (they cannot be attributed anyway) or key them on a coarse signal, so six anonymous requests cannot lock out every other anonymous client.
- **H5 (D2/D1) — sweep expired entries.** A periodic or amortized TTL sweep (drop entries whose `firstFailureAt` is older than `windowMs`) reclaims stale slots and reduces attacker influence over eviction order, at the cost of a few lines.
- **H6 (D8) — compute `retry-after` from the entry's actual remaining window** instead of the static 60 s.
- **H7 (M12) — extend the cap test** with a sequence that distinguishes LRU from FIFO (e.g. touch `a` again, then overflow, then assert `a` survives) so the documented recency guarantee is protected.
- **H8 (D9) — describe the control accurately** in `ADOPTION-RUN-REPORT.md` / any public description: it blunts per-key bearer guessing and bounds memory; it is not CPU-DoS relief and not a global counter (D5).

### Explicitly *not* recommended

- Do **not** add `X-Forwarded-For` support "for proxied deployments" without the allow-list from H1 — that is precisely mutants M9/M10, and it is a full bypass.
- Do **not** make the block pre-auth (skip the SHA-256 on blocked keys) unless the intent is to change the threat model: it would leak "this key is currently blocked" to unauthenticated callers and would let a poisoned key lock out a victim before they authenticate. D9 is an expectation-setting item, not a defect.

---

## 8. What the shipped code gets right (verified, not assumed)

- Memory is genuinely bounded — 200 000 hostile keys → 500 entries, ≈118 KB retained. The unbounded-map DoS surface is closed.
- 403 and 503 are correctly **not** charged to the client (M7 killed; probe A13), so a server misconfiguration cannot be weaponized into a client's lockout.
- A valid credential is never blocked and clears the count (M6 killed; probes A12/N3) — the "legitimate clients are never blocked" claim holds, including behind shared NAT.
- No `X-Forwarded-For` / `X-Real-IP` trust anywhere; keys come from the edge-set header or the socket peer only.
- No free attempts from header shape: absent, empty, `Bearer`, `Bearer ` and `Basic` are all `401` **and** counted.
- The 429 body never echoes the presented token (`auth.test.ts:318`).
- The author's own report states the per-isolate limitation and the exact window semantics honestly, including an inconvenient self-observation about the threshold arming one attempt early under duplicated loopback traffic.

## 9. Reproduction

```
# baseline
cd prototype && npx vitest run && npm run test:node      # 92 + 36 green
# probes (scratch, read-only w.r.t. the repo)
node --expose-gc --max-old-space-size=1500 mem.mjs      # 200k-key growth bound
node --max-old-space-size=1500 probe-core.mjs            # A1-A14 semantic probes
node probe-node-adapter.mjs                             # real node:http trust boundary
# mutants
python3 mutate.py                 # all 14, restores pristine after each
python3 mutate.py M9 M10          # the two survivors, for re-verification
```
Harness, probes, per-mutant stdout and `mutation-log.json` are in
`/home/alexey/git/cloudflare-agent-git/.local/scratch/sb-limiter-review/`.
Repository state after this review is identical to `a2055e3` (`git diff HEAD` empty).
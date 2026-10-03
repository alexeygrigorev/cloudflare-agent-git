# Current deployment source review

As of 2026-10-03T18:40:38.632640+00:00. Read-only principal source review, not exploit execution, runtime acceptance or a complete security audit. Existing implementation owners keep their files; source is in progress and findings are prospective until tested.

| Finding | Actual source/condition | Required negative evidence | Owner/handoff |
|---|---|---|---|
| Coordinator auth survives Git token TTL | Facade748cf core/coordinator.ts credentialAgent uses only agentTokenHashes; no expiry/task-end/revoked record | fake-clock expiry and task-ended/revoked credentials denied; documented legacy-state handling | deployprep C1375; core integration Ant |
| Old events can rewind head | recordPush checks hasCommit, not actual ref tip; ring16 excludes earlier replay | 17+ pushes then delayed old event; legitimate force push accepted only when actualref agrees | deployprep/Ant C1384 |
| Backend error disclosure | facade core/router errorResponse sends backend message verbatim | fake secret in backend error absent public error/log | deployprep C1372 |
| Webhook/agent auth conflation | deployprep HMAC on both /events routes; existing agent bearer path cannot sign shared secret | agent bearer still works; webhook disabled/config missing fails closed; actual provider sender protocol verified | deployprep C1386 |
| Counter bypass and growth | any arbitrary bearer hash forms a bucket before auth; counter failure fails open | random bad credentials cannot create unbounded buckets/ops; bounded global admission and unavailable storage503/backoff | deployprep C1386 |
| DO expiry API mismatch | coordinator.rateLimit put option expirationTtl180 absent official DO API | real workerd bounded pruning/expiry, not permissive fake | deployprep C1387 |
| UI older response wins | UIcf682f setInterval no generation/single-flight guard; task refresh swallows status failure | later response delivered first, older response ignored; stale status cannot render clean | UI C1385 |

Official [SQLite-backed DO storage](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/) opened2026-10-03; put/delete Supported options enumerates allowUnconfirmed/noCache, not expirationTtl. Inference: the proposed TTL flag does not establish expiry. No runtime TTL test run here.

Deployment waits for actual pinned fixes and independent cross-family verdict, not this paper checklist. Local build/iteration continues. Authenticated coordinator reads, explicit CORS allowlist, isolated staging namespace, short-lived token management, configured sender authenticity and bounded operation admission remain required by the reviewed PLAN7293cc8§5. No public deploy performed or approved in this review.

Separate active-resource credential verification/revocation from deleting reusable dev repos. Cleanup due2026-10-07 is supervised by Codex after genuine human/Claude handoff; do not delete peer-owned active integration resources as a routine prerequisite.


## 2026-10-03T19:13:12.399970+00:00 — committed deployprep6c5377a and head concurrence

Ant actual reply01a1032b-fc76 explicitly holds public deployment for anonymous reads and limiter storage growth. Principal source review credits removal of unsupported expirationTtl; same-key previous-two-bucket deletion does not globally bound one-off attacker keys. Git credential TTL and coordinator bearer expiry remain distinct. All prior findings above are revision-scoped: UI generation ordering is fixed by9aca826 but status-failure index stale badges remain C1399; no assertion that old DO put-option bug persists in6c5377a. Current runtime negative/cross-family review pending; owner111vitest/16sidecar is not public security acceptance.

# Reference solutions — NOT for demo agents

This directory is for the demo harness/principals only. Demo agents must receive
`TASKS.md` and the base tree, never these patches or notes (they reveal the designed
conflicts). Reference branches: `demo-l5-task-1`, `demo-l5-task-2`, `demo-l5-task-3`
(cut from the commit recorded in `BASE`; patches are `git format-patch` output of each).

## What each solution does

- **t1** — `GET /links` listing + visit counters: adds `visits: 0` to the record built in
  `ShortlinkService.create`, adds `list()` and `recordVisit()`, counts redirects.
- **t2** — object-form create with TTL: changes the signature to
  `create({ slug, url, ttlSeconds })` (breaking), stores `expiresAt`, expires in
  `resolve()`, updates existing tests to the new call shape.
- **t3** — bulk import: `POST /links/bulk` calling `service.create(item.slug, item.url)`
  positionally — i.e. the contract as it exists at the shared base commit.

## Designed overlaps (verified by ../../verify-overlap.sh)

1. **T1 + T2 → textual conflict.** Both rewrite the same record literal line inside
   `create()` (`visits: 0` vs `expiresAt`), so `git merge` stops with
   `CONFLICT (content): Merge conflict in demo-target/src/shortlinks.js`.
2. **T2 + T3 → semantic conflict.** No textual overlap (T3 only inserts a new route and
   a new test file), so the merge is clean — but T3's positional `create(item.slug, item.url)`
  now destructures a string, `slug` is `undefined`, validation throws `slug is required`,
   and the bulk endpoint returns 400 instead of 201. Failing test:
   `POST /links/bulk imports every link and returns slugs in order`
   (`demo-target/test/bulk.test.js`, assertion `400 !== 201`).
   The empty-list and malformed-body bulk tests still pass: they never exercise a real
   `create` call, which is exactly what makes semantic conflicts slip past review.

## Running the verification

From anywhere:

    ../../verify-overlap.sh   # or bash demo-target/verify-overlap.sh at the repo root

Exit 0 iff all three facts hold. Requires `git` and Node >= 18 on PATH.

# A09 incumbent check — do the Feb–Oct 2026 exactly-once guard tools cover destination-atomic Git publication?

Owner: `space-bunny-head`, aplexer session `8620fdc9-0518-4d21-a7e2-fc8bd8e58726`, workspace
`/home/alexey/git/cloudflare-agent-git`. Task assigned by claude-principal in `01a0ffd9-68b9`. Date 2026-10-03.

Inputs read (read-only, peers' files, unmodified):
`research/claude/dup-side-effects-evidence.md` (E-C501..E-C522),
`research/debate/codex-a09-publication-adapter-challenge.md`.

## VERDICT: **GAP** — with one partial overlap that must be stated honestly

None of the seven named tools, and none of the four incumbent mitigations, operates on **Git refs, commits
or repository publication**. Their unit of deduplication is a **tool call, an API action, or a workflow
step** — never a destination ref. The narrow A09 adapter's residual is therefore real but **narrower than
"exactly-once publication"**: it is specifically *carrying operation identity and a request digest inside
the published immutable object*, and reconciling against destination history after a lost reply.

The partial overlap is genuine and is the strongest evidence that the market is adjacent rather than
absent: agent-ledger explicitly documents that its own exactly-once property **depends on the downstream
API supporting idempotency keys** — i.e. these products deliberately stop at the transport boundary and
delegate the final guarantee outward. That is precisely the seam A09 proposes to cross, for one destination
class (Git/Artifacts) instead of arbitrary APIs.

## Method and honesty labels

| Label | Meaning here |
|---|---|
| **SOURCE FACT** | Quoted from a primary artifact I fetched today (2026-10-03), with URL |
| **VENDOR CLAIM** | Asserted by the tool's author; not independently reproduced |
| **UNVERIFIED** | Could not retrieve; recorded as unknown, **not** as absent |
| **REPRODUCED** | I ran it. **Empty set — I ran none of these tools.** |

Per my earlier error in this project: a 404 or an unreachable host is **not** evidence of absence, and
absence of documentation is **not** evidence the capability is absent from code. I state both distinctions
where they bite.

## Per-tool findings

### 1. agent-ledger — SOURCE FACT, repo verified
`https://github.com/rune0-dev/agent-ledger` · Apache-2.0 badge in README (GitHub API reports licence
`NOASSERTION`, a metadata discrepancy, not a licence conflict) · 5 stars · created 2026-01-17, last push
2026-02-08 · Python.

**What it guarantees (SOURCE FACT, verbatim from its README):**
> "**At-most-once commit per idem_key**: Each unique `(workflow_id, tool, args)` tuple is recorded at most
> once, enforced by the store's unique constraint on `idem_key` and atomic upsert semantics"

> "**Exactly-once execution**: Depends on your handler being idempotent or the downstream API supporting
> idempotency keys. If it does, passing down `effect.idem_key` would ensure exactly-once execution."

> "**Deterministic canonicalization**: Args are JSON-serialized with sorted keys; non-deterministic values
> (timestamps, UUIDs) in args will create new records"

**Git/ref coverage: NONE.** Word-boundary counts in the README: `ref` 0, `branch` 0, `push` 0, `merg` 0,
`publish` 0, `repository` 0. The 8 occurrences of "git" are all `git clone` of its own demo repository. Its
key is `(workflow_id, tool, args)` — a tool-call identity, not a ref identity.

**Relevance to A09: high, as prior art and as a warning.** Two of its documented constraints are exactly
the A09 contract's hard cases: the non-determinism caveat (UUIDs in args create new records) is Claude's
already-accepted "runtime-minted-ID defeats deduplication" challenge in the A09 doc, independently
discovered by this tool's author. And the exactly-once-conditional-on-downstream statement is the market
declining to own the final hop.

### 2. ExactOnce — SOURCE FACT (HN primary), product host UNVERIFIED
`https://news.ycombinator.com/item?id=47170564`, by michaelnewman, 2026-02-26. Product URL
`https://exactonce.com` → **HTTP 000 / connection failure from this host on two attempts**, and
`api.exactonce.com` likewise. Recorded as **UNVERIFIED (host unreachable)**, *not* as absent.

**What it claims (SOURCE FACT, verbatim from the Show HN text):**
> "The transition from active → consumed is enforced atomically via a DynamoDB conditional write. Under
> concurrency, one request succeeds; the rest deterministically get a typed 409 already_used. No distributed
> locks, no cross-service transactions."

Use cases listed: magic login links, coupon redemption, webhook deduplication, one-time download links,
ticket scanning, licence activation. Private beta, free.

**Git/ref coverage: NONE.** No Git, ref, commit or publication semantics in the announcement. It is a
generic single-use-action primitive — the destination is an API record, not a version-control ref.

**Relevance to A09: the closest architectural analogue, and still not a substitute.** Its atomic
active→consumed transition is the same shape as A09's "bind operation ID, publish once, reconcile
afterwards". Its use cases are all *consumable tokens*, not *mutable named refs with later legitimate
advances* — which is exactly the A09 falsification row "another legitimate publication advances the head",
a case a consumed-once primitive does not model.

### 3. CellaFlow — SOURCE FACT, site fetched
`https://www.cellaflow.com/` → HTTP 200, 30,673 chars. Org `github.com/cellaflow` exists (created
2026-05-27, 4 public repos: `cellaflow-sdks` 7 stars, `cellaflow-benchmarks`, `cellaflow-docs`). Announced
by `druhinbala` in HN 49695071.

**Note on attribution:** Claude's E-C511 lists Cellaflow among tools, but that HN item is the author
*asking* "how do you make sure recovery of an AI agent doesn't repeat the side effect?" **and linking his
own product in the same comment** — it is a launch dressed as a question. The pain claim and the product
claim are the same person; treat the demand signal as weak.

**What it claims (VENDOR CLAIM, site text verbatim):** "Durable execution middleware for autonomous AI
agents… At-Most-Once Tool Guards"; "0.31ms MARGINAL ENGINE OVERHEAD · ~2ms DURABLE COMMIT"; "Many agents,
one action. The outcome survives the crash."; RocksDB local journaling, "append-only execution ledger in a
single transaction", "fenced idempotency leases admit a single caller".

**Git/ref coverage: NONE.** Site counts: `branch` 0, `publish` 0, "exactly once" 0. The 9 `ref` hits are
words like "refresh"/"prefix" and the 21 `commit` hits are its **own** durable-commit latency and RocksDB
ledger commits ("pinned them at a commit", "commit_latency"), not Git commits. Its own proof is "we took
four open-source agent products, pinned them at a commit, and killed the process mid-run" — again Git as a
*pinned input*, never as the publication destination.

The 0.31ms / 1.93ms p50 figures are **VENDOR CLAIM with no methodology I could verify**.

### 4. SafeAgent — UNVERIFIED artifact, pain claim is first-hand
HN parent `47294291` (the text Claude cited, `47294329`, is a **comment**; Claude labelled the comment id as
the thread — minor citation slip worth correcting). By Lions2026, 2026-03-08. **No repository, package or
site found**: GitHub search `safeagent+exactly-once` = 0, `safeagent+agent+python` = 2 unrelated repos
(`jkorzeniowski/safeagentguard`, `parthamehta123/safeagent`).

**What the author claims (SOURCE FACT as a statement, VENDOR CLAIM as a product):**
> "I built a small Python library called SafeAgent that protects real-world side effects when AI agents
> retry tool calls… agent calls tool ↓ network timeout ↓ agent retries ↓ side effect happens twice"

Stated mechanism: `request_id` + durable execution receipt, replay the original receipt instead of
re-executing. **Git/ref coverage: cannot be assessed — no retrievable artifact.** Not recorded as absent.

### 5. Kybernis — UNVERIFIED product, and the one Git-adjacent hit is a different tool
HN `47270121` is a **comment** (parent `47268331` returned empty via Algolia). By wingrammer, 2026-03-06.
Claim:
> "even when the agent output itself is correct and admissible, distributed systems behavior can still
> produce duplicate mutations once execution starts — retries, worker restarts, async scheduling"

Stated boundary: "ensure that action commits exactly once" **at the execution layer, independent of
pre-execution validation.**

**Git search result:** the only near-match is `Kybernis/kybernis-audit` — 1 star, created 2026-03-16, last
push 2026-03-17, **no licence**, described as "The open-source chaos engineering and risk scanner for AI
Agents". That is plausibly the same vendor, but I did **not** fetch its contents, so I record the
Git/ref coverage as **UNVERIFIED** rather than guessing from the name.

This is nonetheless the **most interesting quote in the set for A09**, because it names the exact boundary:
validation ≠ commit-atomicity. That is the A09 adapter's thesis, stated by an independent builder eight
months before our shortlist.

### 6. Aura Guard — UNVERIFIED artifact (repo renamed/moved)
HN `46958572` by aura-guard, 2026-02-10 → `https://github.com/auraguarddev-debug/aura-guard`. GitHub API
returns **301 Moved Permanently** to repository id 1153818856; I did not resolve the destination, so the
current location is **UNVERIFIED**. No verified repo means no verified README.

Claim (SOURCE FACT as statement): "looping search calls, retrying 429/timeouts forever, and double-firing
side effects (refund twice / duplicate emails)"; mechanism is "deterministic ALLOW/CACHE/BLOCK/ESCALATE
decisions before tools run" — i.e. a **pre-execution** gate, which by Kybernis's own framing is the half
that is *not* commit-atomicity. **Git/ref coverage: UNVERIFIED.**

### 7. Duerelay — UNVERIFIED artifact
HN `47664625` by howtobatman101, 2026-04-06. No title, no URL on the item; GitHub search `Duerelay` = **0
repositories**. Claim: "infrastructure that sits between event sources and your systems to enforce
idempotency, isolate sources and govern AI agent actions via policy before they execute." **Git/ref
coverage: UNVERIFIED.**

## Incumbent mitigations (the four non-guard rows)

| Mitigation | SOURCE FACT | Git/ref publication coverage |
|---|---|---|
| HTTP idempotency keys (Stripe) | Claude fetched `docs.stripe.com/api/idempotent_requests`; pattern is per-API, per-request | **None.** Requires the destination to already support keys — the precondition agent-ledger names |
| Durable execution (Temporal) | Claude fetched `temporal.io/ai`: "Guarantee all executions of all processes run to completion… in spite of failures" | **None**, and the A09 doc already records the boundary: Temporal's activity docs state the *called service* enforces idempotency |
| Agent checkpointing (LangGraph) | Claude fetched LangGraph persistence docs: checkpointers "persist a thread's graph state as checkpoints" | **None.** Resumes agent state; says nothing about a destination side effect |
| Verify-before-retry (codex#27283 comment) | Practitioner proposal: treat side-effecting commands as unknown-outcome after timeout, query target state before reissue | **Closest in spirit, and still not it.** It is a *harness discipline* for shell commands; it does not bind an operation ID into a published object, and it does not make publication atomic |

Git's own primitives — the honest baseline for A09 — are `git update-ref` (verifies expected prior object,
supports transactions) and ordinary push/receive-pack. **Rejecting a stale expected head is what plain Git
already does**; the A09 doc says so itself, and my check confirms no incumbent adds the two things A09
actually proposes: operation identity inside the published object, and destination-history reconciliation
after a lost reply.

## What is genuinely covered, and what is not

**Covered by the market (do not claim as novelty):**
- At-most-once *tool-call* execution via a ledger with a unique key — agent-ledger, CellaFlow, Kybernis.
- A generic atomic single-use action primitive — ExactOnce (DynamoDB conditional write).
- Durable workflow replay — Temporal, LangGraph, CellaFlow, agent-ledger.
- Pre-execution policy gates — Aura Guard, Duerelay.
- The *diagnosis* that validation ≠ commit-atomicity — Kybernis, and agent-ledger's own caveat.

**Not covered by anything I could verify (the residual):**
1. **Operation identity carried inside the published immutable Git object.** Every tool keys on a
   call-site tuple held *outside* the destination. agent-ledger's non-determinism caveat is the same hole
   Claude's accepted A09 challenge names; nobody solves it by binding the ID into the artifact.
2. **Reconciliation against destination history after a lost reply**, for a ref that may since have been
   legitimately advanced. ExactOnce models a consumable token, not an advancing branch.
3. **Preserved legitimate repeats** (distinct operation IDs, identical content) versus duplicate
   suppression. No tool states this distinction; content-hash dedup would get it wrong, and agent-ledger's
   canonicalization note shows the hazard is live.
4. **Any Git/Artifacts destination semantics at all.** Zero ref/branch/commit coverage across all seven.

## Honest limits of this check

- **REPRODUCED set is empty.** I ran none of these tools; every capability statement is documented behaviour.
- **Four of seven artifacts are UNVERIFIED** (SafeAgent, Kybernis' actual tool, Aura Guard after redirect,
  Duerelay) and ExactOnce's product host was unreachable. For those I can characterise the *claim* and its
  mechanism, and nothing more. That is a real limitation, not a formality: if Aura Guard's current repo
  documents ref-level publication, this verdict weakens.
- The Git/ref-coverage finding is **absence of documentation**, which is weaker than demonstrated absence. I
  checked two of the three retrievable READMEs/sites in depth (agent-ledger word-boundary counts,
  CellaFlow site text) and searched the third (ExactOnce) at announcement level only.
- No independent reproduction of any vendor benchmark exists that I could find.
- I did not verify E-C501..E-C522's underlying GitHub issues; that is Claude's lane and `zcy-dup-research`
  currently holds edit scope on that file.

## Recommendation to claude-principal

Keep the A09 adapter but **narrow its novelty claim to what survives this check**, and drop any framing that
implies "exactly-once side effects" as a product category — that market exists and Claude's own evidence
document names seven entrants in it.

The defensible wedge is narrow and I would state it as: *operation identity bound into the published Git
object, plus destination-history reconciliation, for Git/Artifacts publication specifically.* Four
incumbents prove the surrounding demand; none addresses the destination-binding seam; and Kybernis
independently articulated the exact boundary eight months ago.

**I would not fill slot six on this.** The A09 doc's own gate still requires an actual internal
publication task compared against ordinary Git, plus at least two external first-hand reports — and one of
its two named sources (E-C501, codex#27283) is a single report about a duplicate GitHub *comment*, not a
publication. That gate is unmet, and nothing in this incumbent check moves it.

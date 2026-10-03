# Muse round 11: ZCode rev1 shadow runner negative review (9ed2ab2/22a556e)

Reviewer: muse-reviewer (7e6e9bb0), per antigravity-head 01a0ff72. Read-only
probes only (dry-run + /tmp outputs + module import); no repo writes, no
builds, no peer-path edits. ZCode owns its paths; I review.

## 1. Overlap-vs-semantic eligibility — structurally fixed, one naming debt

Rev1 withdraws the same-path test (withdrawn_claims ×3 present in dry-run
output; eligible_warnings=="unknown", rate "undefined", binding False —
reproduced). Current rule: published filename overlap → eligible True;
else unknown (via polls or insufficient-timeline). Verified properties:
no-overlap can never yield zero (no false-zero manufacturing); missing
publish files degrade to unknown, not crash (continue → empty sets).
Residual: overlap is filename intersection, a *necessary* precondition, not
proof of conflict — compatible same-name content also flips True. That errs
toward scrutiny, the safe side for a precondition, and the basis string says
exactly what was observed. RECOMMEND: rename the field semantics from
"eligible" to "eligible_precondition" (or document necessary-vs-sufficient)
so a future True cannot be quoted as a conflict finding. No code defect;
no false eligibility manufactured on the current dataset (unknown stands).

## 2. Typed discovery events — discriminant set exact, validation shallow

TYPED_EVENTS (12) == skeleton SCHEMA keys (12/12, verified item-by-item);
ETYPE_KEYS order (etype→event→kind→type) resolves the known shapes without
false counting (run_failure kinds, fence kinds correctly ignored). Honest
scope_note for pre-schema receipts. GAP: counting is presence-only — a typed
event missing SCHEMA-required fields counts identically to a valid one.
Vacuous on today's receipts (schema absent there) but recommend field-
presence validation + malformed count in scan_typed_events before it ever
scores a typed dataset. Cheap, prevents a future counting-validity hole.

## 3. Timestamp dedup — fragile both directions (PROVEN by import probes)

Key is (event, ts) only; task_token is result metadata, not in the key:
- P3a exact twins → dedup-skipped, 1 line (the only case their suite covers).
- P3b same content, skewed ts → DUPLICATED (2 lines). Clock skew defeats it.
- P3c distinct payloads, same (event, ts) → second SILENTLY DROPPED.
  Coarse-ts collision loses data.
- Default call path is lock-free (lock_path=None); read-then-append races
  under concurrent twins (TOCTOU evident by reading; not raced live).
RECOMMEND: key on (task_token, event, stable-content-hash), ts as tiebreak
only; default the flock path (helper already supports it). For an events
ledger that must survive dupexec twins AND coarse clocks, (event,ts) is the
wrong key in both directions. Not blocking dry-run use; blocking for any
production journal reliance.

## 4. Emit gate — SHA refusal proven, timeline/procedure gaps noted

Reproduced: --emit with empty bundle-dir → exit 2, no file written. ✓
Sanitization refusal (exit 3) present in code. GAPS: (a) no timeline-
completeness refusal exists — emit proceeds with eligible=unknown (honest
labeling; but if the requirement is "disabled on incomplete timeline", add
the gate or record the deliberate exception); (b) the repo-default-dir gate
(Codex acceptance) is help-text only — main() enforces nothing for the
default OUT_DIR. Recommend an explicit acceptance token flag before any
repo-default emit, not just documentation.

## Verdict
Rev1 is a genuine correction (withdrawal explicit, dry-run honest, hygiene
good). No blocking defect for continued dry-run use. Three recommendations
for owner action before production reliance: dedup-key hardening, typed-field
validation, emit-gate enforcement. None is mine to implement (ZCode owns).

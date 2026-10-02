# Claude mutual check: A01 pilot (Grok a7ecdd4) and Codex review

2026-10-02 ~22:55 CEST. Agreed mutual-check trigger (pilot delivered). Inspected research/grok/a01-pilot-results.md, both prompts, and research/debate/codex-a01-pilot-review.md. Not a sign-off.

Agree with Codex's three confounds (unequal instructions, unequal oracle access, seeded reader with no live WIP origin) and with Grok's own D-G23: N=1 smoke, not uptake proof.

New point (C-P1), not covered by either file: **the notice arm "passed" by not doing the task.** The instruction was to make bulk_update write directly into state.values. The notice arm's committed bulk.py is byte-identical to base (action keep_update). The control arm's final repair (direct write + `reader.invalidate(key)`) satisfies the instruction AND the oracle. Scored on task acceptance + oracle, the control arm is the only arm that delivered the requested change. An A01 metric that counts "oracle passes" alone rewards warnings that make agents refuse or stall, which is the opposite of the product's value.

Correction for the next pair (input to Grok/ZCode preregistration, Codex's prepared seed):
1. Two-part acceptance: task acceptance test (the requested behavior exists, e.g. bulk path does not call update / perf or structural check) AND the external composition oracle. Report the 2x2 per arm; "oracle pass + task fail" is a failure, not an uptake success.
2. Identical prompts; the warning arrives asynchronously mid-task through the A01 channel (aplexer message or MCP tool), not as a pre-placed WARNING.md the prompt tells the agent to read.
3. Primary outcome: time from the conflicting edit's existence to "task accepted + oracle pass", and edit size; secondary: whether the warned agent produced the compatible design (direct write + invalidation) on its first commit.
4. Separate git repos per arm (Grok noted concurrent git in one shared repo as a defect).

Implication for A01: the value proposition is "agents reach a compatible design earlier", not "agents avoid risky changes". If warned agents mostly refuse/stall, A01 is a brake, and the merge-queue + repair baseline wins.

## Update after Grok fair pair (D-G25, research/grok/a01-fair-results.md, 8623362)

Observed (Grok's report; Codex live review still open): both completion and live arms produced first product commits that pass the registered task check and compose; zero source repair in any arm; elapsed gaps are commit timestamps only. Live peer bytes were visible before the commits; no advisory notice was used.

Claude reading (not a verdict, pending Codex's independent review): with realistic, non-signposted task pairs, the hazard A01 exists to catch did not occur, consistent with E-X020 (1 interference in 834 mined-pair runs) and the arXiv 0.5% co-activity limiter. A01 cannot show a benefit where there is no hazard; manufacturing hazards by hiding context was already rejected. Proposed consequence for the shortlist: A01 stays conditional but loses "primary" status unless a pre-registered, neutral task family with a naturally recurring composition hazard is found (e.g. the archive's Dependency Domino / producer-consumer contract change) and the live arm beats completion-time testing there. Until then, recommend the principals rank A01 by evidence like any other slot.

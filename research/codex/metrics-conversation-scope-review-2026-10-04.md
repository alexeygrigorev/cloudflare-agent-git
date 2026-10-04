# Principal review of conversation-scoped metrics

Target: `6b02f2c98e3fd9f8bb6953f7d4330acd7c1391ad`. This is source inspection and challenge of the head-owned worker/reviewer outputs, not a principal implementation or independent runtime test.

The patch replaces tag/team-only maximum token selection with exact conversation matching when an ID is available. It preserves team agent declarations in a list. The worker reports eight new tests and 102 repository tests passed; independent reviewer `24e23518-3420-4953-b990-3f146ce42e5f` has produced a draft reporting four killed mutants. Those receipts establish useful output; they do not establish complete attribution across every identity lineage.

| Observed source behavior | Required challenge or limit |
|---|---|
| `authentic_conversation_id` returns registry harness ID before live/disk IDs, without comparing conflicts | Test stale registry ID against newer native binding. A first nonempty string is not verification of current identity. Native helper registration may legitimately differ from its parent's identity; distinguish that case explicitly. |
| Top-level agents are suppressed when their tag appears in any team | Test a distinct top-level conversation sharing a team tag. Tag equality alone does not prove a mirror duplicate. |
| Missing-CID events remain eligible for an unknown session, even alongside bound events of that tag/team | Test mixed legacy/current records and keep fallback unbound. A label does not prove attribution. |
| Event matching checks CID/tag/team, but not mode/provider/model/generation | Test conflicting provider/model and cumulative versus per-call records. Existing `record_usage.py` emits cumulative mode, but broad claims require the input contract to be stated and enforced or explicitly limited. |
| Matching selects latest timestamp; aggregate selects maximum per source/CID | Test resumed generations, multiple aliases of one CID, and overlapping parent/child coverage. Latest selection and maximum aggregation are different reconciliation rules. Distinct legitimate API calls are real usage, not automatically duplicate telemetry. |

C1771 (`01a105a4-09e4-7150-8ac8-e7689b7632d1`), C1773 (`01a105a4-6e76-7e00-b180-e4ccc1b61930`) and C1774 (`01a105a4-fcd9-7722-b0f0-8b1e756fe50f`) ask Antigravity to obtain actual independent negative outcomes and bound its acceptance. No peer agreement or completed additional test is inferred. Derived Gemini emission and service reload remain held. `record_usage.py` remains outside the released repair scope.

The latest runbook `7aa20f1` has a distinct current-pin reviewer `02261a65-4c9c-4064-b641-93e8075d77eb`. Existing genuine ZCode `4abc725c` completed and released its prior task; a new head-owned assignment, ACK and first tool are required before counting resumed work. The proposed useful next task is the exact coordinator-primary bootstrap through SDK task/push behavior, separately owned from source review, with fresh quotas, private endpoints and real resource limits.

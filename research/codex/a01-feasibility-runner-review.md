# A01 feasibility runner review: invalid first pair and model mismatch

Observed 2026-10-03T11:46:35.909975+00:00. Principal read-only review; no harness/model execution by Codex.

## Original pair

Preserved the actual pair-results bytes privately at `.local/codex-a01-review/pair-results-e05bd5d1ffb3133987a9aba36af3a3c5ff6e7e978e9b4df125211fc58c0ba655.json`; SHA256 `e05bd5d1ffb3133987a9aba36af3a3c5ff6e7e978e9b4df125211fc58c0ba655`. Producer native `2bb438b2-1f15-4141-8b53-a924041e7302`, model conversation `ses_efe77212bffeM7ITy9l997hHG2`, has only the actual whoami tool `prt_10189b128001XoKl62dRhco77C` at 1791027163433 and source-read tool at 1791027193849. Its recorded source diff is empty. The two existing units pass on the unchanged starting implementation, so they do not establish ticket completion. Consumer native `052daca1-a723-4373-b1d0-7cf6f46de692` did edit its implementation and reported 14 passing tests. This does not establish a completed producer/consumer interaction.

The frozen composite grader exited 2 with argparse reporting missing `--producer` and `--consumer`. This is a harness invocation error, not a task or product failure. Original JSON says FAIL; retain it and append an INVALID / harness-error interpretation. Claude STOP-CHECK `01a10192-f136-7c40-a3e9-723cf5f8dc22` and Codex C-1285 independently agree on invalidity.

## Revised runner and already-started replacement

Pinned revision `32f9ed297faefbcd74c79ef0531a20ed99694bf2` adds grader arguments and a 20-second settle requiring target modifications. It still falls through after timeout without making target modification/completion a validity gate. `setup_workspace` deletes existing destinations; the copied provider DB is also replaced. The original pair's session rows are absent from the current copied databases. I cannot claim a lossless archive exists or all original artifacts remain recoverable.

Replacement native sessions `0c42428b-3ffb-40d5-a9a9-397c9fbf1614` and `bc1e08e6-fc6f-42bd-ade7-d805076e4548` were actually observed in the same paths. Read-only SQLite assistant-message records show provider `opencode`, model `big-pickle`, in roots `ses_efe6d520bffenFspOBursPGicw` and `ses_efe6d5152ffelhgejLzOdF16wm` (creation 1791027752436/2621). The declared `MODEL_ID` is not passed to either launch command. This contradicts the prospectively approved Muse route in addendum f588508. Actual filtered records saved privately at `.local/codex-a01-review/latest.json`. This replacement cannot be labelled a standardized Muse pair. Original first-pair actual provider is presently unknown from the retained telemetry; do not infer it from its tag or the same runner.

Other source concerns: telemetry selects the oldest directory-matching root without a launch-time bound; delivery return-code zero is treated as model notice; the Go gate incorrectly copies a 15% reserve that applies to real Codex rather than the agreed Go >10%/not-limit-reached gate. Intent/warning payloads and frozen grader must remain unchanged unless a prospective amendment is agreed.

## Corrective ownership and next check

Antigravity owns narrow runner repair and producer stop diagnosis; Muse owns independent oracle/negative review. C-1285 messages `01a10194-0f2d-7ad3-9b67-00daecf63ef4` / `01a10194-0f62-75d2-a9ae-ae01ad439ed5` requested a hold on later arms, fail-closed invalidity, task-specific external producer acceptance that fails BASE, immutable baseline diff handling, preservation and actual model verification. Muse's existing message was safely submitted after twice-observed idle/empty composer; transport receipt is not receiver ACK or execution. C-1286 model mismatch notifications include head `01a10195-2e58-7b72-9690-0e91ec6ae39a` and root `01a10195-2ec5-76c1-8ec9-eff63c400e46`.

Next mutual check: actual head ACK, honest preservation/loss inventory, pinned corrected runner and Muse negative verdict before further arms. No task efficacy score, six-approach agreement or autonomous scheduler acceptance follows from this attempt.

# Publication quality and design fidelity

## Why this gate exists

The user rejected the deployed visual treatment as different from the Claude Design reference. Historical deployment, overflow, SVG-label and source checks did not compare the reference with production. They are functional checks, not visual acceptance. Asking the prototype to match the implementation reversed the intended authority. Those earlier checks remain valid in their narrower scope; their design-fidelity acceptance is withdrawn.

The reference is the user-requested [Claude Design project](https://claude.ai/design/p/9c548064-9f6a-4f12-977d-1e9e2cb67831). A mutable project URL alone does not pin an approved design. Current fidelity status: **FAIL / repair not yet reviewed**. No complete prototype export or same-viewport independent visual review is currently recorded.

## Ownership

The publication coordinator owns the backlog, executor and reviewer assignments, preview acceptance, release decision and rollback. Implementers do not approve their own visual changes. An independent visual reviewer must be a different actual agent, with its native identity and task ACK recorded. A process review does not count as a visual review. Editorial facts/style and functional/privacy/accessibility checks have distinct evidence, even if one independent reviewer performs multiple checks.

Principals monitor queue ownership, first actions, evidence, unresolved blockers and continuation; they escalate missing quality checks through the publication coordinator. The desktop orchestrator is the user–Hetzner interface, periodic pings and requested browser interactions. It is not the routine page reviewer, implementation worker, release approver or acceptance dependency. A shared Relay owner is not a website head by inference.

## Reference packet before repair

The coordinator assigns a capture executor. If the authenticated browser is available only through the desktop interface, request that scoped capture interaction; it conveys artifacts, not root QA approval. Browser users must serialize control.

Store an export/version identifier, capture UTC time, source URL, SHA256 manifest, and desktop/mobile screenshots for homepage, one project landing, checklist, daily report and fieldnotes. Keep private authenticated exports private until sanitized. Record which existing user instruction approves the design direction; do not invent a new approval or infer approval from an agent reply. If the approved version cannot be established, record UNKNOWN and obtain the missing version clarification through the interface. Do not ask for routine release permission.

Pin layout and visual invariants in the packet: image-led figure followed by latest-daily title/story, detailed honest-status panel, navigation order, project markers, typography families/weights/sizes, spacing/grid/breakpoints, illustration palette/texture and diagram conventions. In particular, the deployed marketing headline/CTA split hero must not silently replace the reference article-led hierarchy. Use measured values from the exported reference, not invented pixel specifications. Current facts, labels, cutoff dates, accessible descriptions and safe opt-in behavior must remain truthful. Keep the approved exported reference immutable. Annotate factual differences, or separately pin a controlled content-only derivative with a diff proving hierarchy, layout and style unchanged; never mutate the approved reference to match production.

## Independent comparison and verdict

Use identical content snapshot and viewport dimensions for each reference/candidate pair: desktop 1440×1000 and mobile 390×844, or the exact documented export dimensions when those differ. Capture full-page screenshots and top-of-page crops, at equal browser zoom and device scale. Record browser, font loading, image loading and capture time. Compare homepage, project landing, checklist, daily report and fieldnotes side by side. Do not substitute DOM assertions, successful build, source reading or zero horizontal overflow for visual inspection.

The reviewer writes a verdict keyed to the exact candidate Git SHA, reference manifest SHA and screenshot manifest SHA. For each page list layout/hierarchy, typography, spacing, navigation, imagery/markers and responsive differences. Classify every material deviation:

- Factual/dynamic update: current evidence or corrected dates; preserve design hierarchy and cite source.
- Intentional design departure: rationale and actual previously authorized direction or specific human decision if it changes the intended design.
- Fidelity defect: implementation drift requiring repair.
- Unknown: missing artifact, unavailable font, missing page or uncertain provenance; blocks design acceptance.

PASS requires no unresolved material fidelity defect or unknown. Minor nonblocking differences need explicit reasoning and a named owner. Reviewer return FAIL with exact screenshot references and next corrective action otherwise. Record hashes of the website/template/style/illustration artifacts as well as the whole-repository SHA. A new design-artifact hash invalidates the previous visual verdict; changes confined to factual content may use the scoped regression rules below. An unrelated peer commit may retain the existing visual verdict only with a recorded identical website-artifact manifest and newly checked deployed source SHA. No fabricated receiver ACK, screenshot, PASS or measured fidelity score.

## Release packet

Before release the coordinator records: reference/candidate pins; actual implementer and independent reviewer identities/ACKs; visual verdict; editorial source/cutoff/fact corrections, contributor statistics verification against WORKFLOW rules when worker counts are included, actual Opus model provenance and full stylint; functional internal links/assets/RSS and unpublished-content exclusion; responsive keyboard/focus/labels/contrast checks; privacy/consent/referrer/token/error/duplicate checks when signup changes; prior good release and rollback command. Each check has PASS/FAIL/UNKNOWN, artifact, reviewer and timestamp. A build PASS cannot turn another gate PASS.

The editorial check includes readability for a cold reader, per [Write for readers, not for the team](WORKFLOW.md#write-for-readers-not-for-the-team). Reject a daily report or article that reads like an internal document: it doesn't open by explaining the experiment to a newcomer, shows internal codes (A01, R12, E-A040), hashes, paths or session IDs, uses team role or process words (principals, heads, gates, falsification, cutoff) or engine names as codes, leaves a needed technical term unexplained, uses file names as link text, or announces its own style ("in plain words", "to put it simply"). The reviewer records which paragraphs failed the cold reader test. The editorial check also verifies that any included contributor statistics adhere to [Contributor and agent statistics rules](WORKFLOW.md#contributor-and-agent-statistics-rules-for-daily-reports): distinct actors deduplicated by native identity, interval-bounded tool and output sources, delivered groupings distinguishing implementation/review/coordination, exclusion of PIDs/CPU/role-names as proof of productive work, explicit unknown coverage, no worker counts in titles, and strict privacy sanitization.

Unresolved visual blockers hold **design changes** in preview. Keep the present public site and continue separately verified factual fieldnote updates and daily reports within the existing template. Do not copy stale prototype experiment claims into current content. A factual update touching layout, navigation, CSS, SVG or illustration becomes a design change and requires visual review. An urgent factual correction may publish through editorial review without pretending it repairs fidelity.

The coordinator accepts the complete packet and releases through the existing Pages pipeline; root approval is not required. Verify successful deployment and the same source SHA in the page's `<meta name="build-commit">` tag (also kept in an HTML comment in the footer); the hash is never visible text. A lane-owned verifier checks representative actual desktop/mobile rendered pages against the accepted preview, plus changed functionality. Record deployment ID/URL and any mismatch. Roll back only the scoped website release through a new revert commit or redeploy a known accepted artifact; preserve peer commits and ordinary Git recovery. No reset of shared branches or private data publication.

## Field notes timeline admission rules

Per human steering, only publish field notes to the public timeline feed when there is something concrete and meaningful to share. Boring, generic, or routine status entries must be rewritten to highlight specific findings or omitted from the timeline feed altogether.

### Admission criteria

Every admitted timeline card must satisfy all of the following requirements:
1. **Concrete finding and project consequence**: The entry must document an actual test result, technical failure, architecture decision, or verified product milestone. Routine check-ins, monitoring restarts without product defects, and administrative status updates are excluded from the public feed.
2. **Plain-language specific title**: The title must state what actually happened or what was decided in plain language understandable to a cold reader. Generic titles (e.g. "Orchestrator check-in", "Remote check — ...") are strictly rejected.
3. **Actionable summary without boilerplate**: The summary must describe the specific technical finding and its consequence. Boilerplate summaries ("Read the full note for the details"), bullet-separated raw heading lists (` · `), and unexplained internal jargon (e.g. A01, A10, D1 gates, draft numbers, runner session codes) are strictly prohibited.
4. **Admitted categories**: Every admitted entry must be categorized as `decision`, `failed`, `milestone`, or `result`.
5. **Human-readable source links**: The visible link text must be descriptive (e.g. "Read full field note →") rather than exposing raw repository file paths, while preserving the direct permalink URL.

### Preservation of durable research

Unadmitted routine check-in reports remain permanently preserved in `research/orchestrator/` in the repository and are navigable via their individual HTML archive URLs. Omission from the public timeline feed preserves high signal for readers without deleting or rewriting durable research records.

## Regression and continuation

Template/CSS/navigation/diagram changes require the five-page desktop/mobile comparison. Isolated article factual text changes require editorial review plus affected-page rendering and layout invariants; metadata-only fieldnotes require source/cutoff/link checks. Signup changes require independent privacy/function checks and affected visual checks. After every failed gate the coordinator records owner, next action and bounded checkpoint, and delegates repair while reviewers continue independent useful work. Principals inspect the missing-evidence/review queue, not every page themselves.

## Open acceptance tasks

Registered task IDs: `publication-reference-packet`, `publication-fidelity-repair`, `publication-visual-acceptance`, `publication-release-verification`.

- **Publication Coordinator**: Actual reachable Hetzner session `088a2387-89e4-468b-9ca5-20be7ffec202` (tag `public-journal-site`, antigravity engine) succeeding native harness `/root/public_journal_site` via clean handoff. Historical native context and process reviews preserved. Handoff details recorded at `.local/journal/publication-coordinator/HANDOFF.md`.
- **Capture-Ingestion & Spec Executor**: Assigned to actual distinct worker `journal-capture-spec` (session `5a862579-1a2f-4956-9c9a-014ffa12a45c`, antigravity, headless, 2 GiB memory cap, 256 PIDs). Reference authority `Agent-Git-Lab.dc.html` ingested and pinned (SHA256: `3ff499a59c577de113369204a3d35c6434420ddb774dbdc3326fb0fa7d3ac816`, 86,679 bytes). First artifacts delivered: `.local/journal/capture-spec/REFERENCE-MANIFEST.json`, `INVARIANTS.json`, and `CONTRACT.md`. Desktop root browser screenshot packet pending.
- **Independent Visual Reviewer**: Assigned to actual distinct worker `journal-visual-reviewer` (session `676eb72d-c3d6-4fa9-85a0-3b9d2ff05679`, opencode, headless, 2 GiB memory cap, 256 PIDs). Initial 5-family same-viewport comparison matrix generated at `.local/journal/visual-review/COMPARISON-MATRIX.md`. Audit verdict: **FAIL** on homepage hierarchy inversion (marketing hero defect) and **UNKNOWN** on missing browser screenshots. DOM/overflow passes rejected as visual proof.
- **Fidelity Repair Executor**: Blocked on sealed reference packet and capture contract. Will own `website/build.py` and `site.css` under explicit handoff.
- **Release Verification**: Blocked on independent visual PASS, editorial fact check, privacy verification, and accessibility audit.

`publication-quality-process-review` was independently executed by `/root/public_journal_site/relay_signup_review`; its verdict concerns this process only. Follow coordination/TASKS.json for current assignment evidence.

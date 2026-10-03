# Agent Git Lab public journal

Public site: https://alexeygrigorev.com/cloudflare-agent-git/
Claude Design project: https://claude.ai/design/p/9c548064-9f6a-4f12-977d-1e9e2cb67831

The website is a lightweight standard-library Python build. GitHub Pages Actions publishes on accepted public evidence/source updates. Daily reader stories are separate from historical half-hour technical reports. Five project landings are provisional; the sixth selection slot stays open until evidence and principal approvals exist.

Build: `python3 website/build.py --output docs`. Generated output is a deploy artifact, not a workspace/cache backup. Never add private logs or Telegram archives to the public tree.

Daily writer: `python3 website/write_daily.py --date YYYY-MM-DD` creates one genuinely bound headless Claude Opus writing session under a fresh Claude quota reading. It preserves private model/output logs and leaves metadata unpublished. Review evidence/source cutoff, privacy, full stylint and the shared visual rules. Desktop ImageGen can provide a dated illustration using VISUALS.md; conceptual images cannot serve as benchmark proof.

Validation: `python3 website/publish_daily.py YYYY-MM-DD` verifies successful actual Opus completion, metadata, full stylint, image paths and basic privacy checks. After editorial review add `--publish`; then commit only owned article/metadata/share text/assets under the experiment Git lock and push. The first report's model result uses the separately recorded initial writer response. Failed checks preserve the last published article. Corrections retain the old claim/date and describe the new evidence.

The daily-publication automation runs at 09:30 Europe/Berlin, after the 09:00 standup. Its output is a public article plus share-ready text. No automated social-account posting is configured. The existing monitors coordinate the research independently of this writing executor.

Use WORKFLOW.md for voice and evidence rules, VISUALS.md for a single illustration/diagram system, and DESIGN-ITERATIONS.md for actual Claude Design feedback. Project titles/evidence come from research/shortlist-6.md; project viability is not inferred from a landing page. Date all snapshots and distinguish historical field notes from current evidence.

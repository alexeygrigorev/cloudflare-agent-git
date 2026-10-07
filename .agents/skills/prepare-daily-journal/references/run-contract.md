# Existing automation dispatch contract

From `/home/alexey/git/cloudflare-agent-git`, the existing daily automation chooses the Berlin edition date and issues exactly one command:

```bash
python3 .agents/skills/prepare-daily-journal/scripts/dispatch.py 2026-10-06 prepare
```

For read-only forward validation use `DATE validate`. Admission only is `DATE prepare --check`; this does not launch a model. The dispatcher creates one exact native aplexer tag, <=1500M cgroup, private root-filesystem TMPDIR, a fresh Codex reserve gate before dispatch and again through scripts/launch-codex.sh, 60-minute execution bound and task-local storage watch stopping at 500MiB (512MiB limit). It requests no model override. Observed usage remains actual child response evidence, never quota-derived tokens. Keep aggregate incremental storage within 512MiB across related task outputs, not merely this log directory; reviewers may reuse existing previews and assets. No /tmp files, dependency copies, Rust builds or global installs.

Exact dedup key is `daily-journal:YYYY-MM-DD:prepare` (or `validate`). Private logs/identity/prompt/launch/receipt/progress are `.local/journal/remote-preparation/DATE/MODE/`. Existing launch or receipt means inspect and reuse; do not delete the fence or use `--fresh`. A failed launch without a launch receipt is still checked against exact native tag. No restart, busy injection or protected composer submission. Recovery requires publication-head review of actual terminal result and one explicitly owned replacement task token; preserve original output. No automatic retry loop and no new cron/service/scheduler.

The head verifies real `whoami`, first-action ACK, incremental output within the recorded checkpoint and final semantic acceptance. Captured events alone do not imply success. Unknown/exhausted quota or runtime failure holds Codex prep with a truthful failure; a different provider cannot be called Codex. During a genuine dependency wait, preserve partial output and the next owned action without idle polling.

Minimal automation prompt amendment (desktop confirms installation; remote does not create another automation):

> Dispatch remote Codex with prepare-daily-journal/scripts/dispatch.py for the Berlin edition date; observe its private incremental progress and genuine completion. Remote Codex owns preparation/visual acceptance/reviews/publication checks/deployment recovery with public-journal-site; dedicated genuine Claude Opus writes prose. Reuse existing good daily content/assets. Desktop bridges only a specifically requested unavailable ImageGen/browser capability. No desktop QA approval or principal implementation dependency.

## Missing ImageGen capability

This handoff's remote Codex tool inventory exposes `image_gen__imagegen`, with referenced local image paths; no generation call was made because October5 art is already approved. Inventory availability is verified for this session only; remote output materialization and future session availability remain untested. Never claim an ImageGen execution from a tool listing.

If the current remote session has no authorized callable ImageGen, write a single private request `.local/journal/remote-preparation/DATE/prepare/asset-request.md`, send its exact path/token to desktop-orchestrator and retain the reply/digest. Include all of:

- Edition date, source cutoff, conceptual narrative grounded in that day's evidence, one landscape 3:2 image and output `website/assets/DATE.png` (or retained sibling if already approved).
- Reference `website/assets/agent-git-illustration.png`, actual SHA256, and source VISUALS.md. Prompt: flat editorial print style; cobalt #2455ed, ink #1c2027, warm-white #fcfcf8, one orange #ef7134 annotation; fine grain, geometric agent/page/Git forms, negative space, no text/logos. Replace narrative with current evidence; do not depict unsupported adoption, completed autonomy or savings.
- Acceptance: returned original bytes, native tool provenance/time, dimensions and SHA256; actual remote visual inspection of style, narrative, crop and misleading claims; independent reviewer and privacy check; accessible conceptual caption/alt text. Preserve original approved reference and dated art; no needless regeneration.
- Desktop only invokes its available authorized ImageGen and transfers the resulting artifact. Remote Codex accepts/integrates it and owns the remaining preparation. No broad credentials, paid alternative, global install or silent stock-art fallback. Missing artifact holds the owned visual step; record the dependency and continue independent prep.

## Publishing and recovery

Before `publish_daily --publish`, verify current publisher does not attribute review to desktop or replace original publication timestamps; request bounded owner repair if necessary. Follow QUALITY.md acceptance, explicit-path shared Git lock commits, source push and existing Pages CI. Pin prior good release and verify live build metadata/assets; a source push alone is not deployment success. Scoped revert/redeploy preserves peer work and private archives. An already good published DATE is a read-only run, never an automatic republish.

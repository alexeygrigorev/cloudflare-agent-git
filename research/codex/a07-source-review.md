# A07 draft review: evidence is not yet an executable corpus

Reviewed 2026-10-03T07:54:57.234464+00:00. Codex principal; independent source checks and product-gate review, no implementation or efficacy test.

The actual native worker0e2a04ff, saved Go/Muse session ses_eff49f17fffefDxEW6ZdT1IzGj, produced findings-draft.md. Its20 S3 entries are source groups, policies and essays, not20 distinct labeled executable submissions. They cannot yet supply denominators for the proposed70% rejection/90% valid-pass gate. Closed or unvouched contributions can be technically valid; a disclosure policy change is not a valid AI bugfix control. Repeated curl campaigns are not independent observations. Some S1 evidence is secondary, from AI-banning projects or about dependencies rather than inbound patches. Preserve those as boundaries, not demonstrated AI-accepting buyers.

## Primary-source checks

[Homebrew responsible AI policy](https://docs.brew.sh/Responsible-AI-Usage), fetched2026-10-03, permits AI assistance subject to contributor responsibility, verification before requesting review, disclosure and human replies to maintainers. It supports the permitted persona and verification obligation. It does not quantify unmet demand or establish willingness to adopt A07. The opened [Homebrew PR21510](https://github.com/Homebrew/brew/pull/21510) concerns disclosure/template policy, not an individual accepted AI bugfix; do not count it as a valid patch control. I did not independently establish its merge date in this check.

[Vouch README](https://github.com/mitchellh/vouch), fetched2026-10-03, documents project-specific identity trust, optional automatic closure of unvouched/denounced issues and PRs, default bot/write-collaborator exemptions, and maintainer-managed trust files. This is a concrete incumbent identity gate. Its listed integration provides no demonstrated paired reproducer execution in this check; that is a bounded documentation comparison, not proof that no custom integration could do so. Adoption and effectiveness rates were not independently measured.

[Anti Slop README](https://github.com/peakoss/anti-slop), fetched2026-10-03, advertises34 configurable checks/57 options, contributor exemptions and action thresholds. Its README also retains a31-check description, so pin a version before exact rule-count claims. The advertised dataset/efficacy is project-reported, not independently reproduced here. The repository identifies AGPL-3.0 licensing: compare capabilities, but do not copy its implementation into this MIT competition source. No contribution was closed or tested in this review.

## Next useful head-owned falsifier

Ask the researcher for one actual permitted-project submission pair with stable source/patch/reproducer and explicit maintainer outcome, or state that these artifacts are unavailable. Separately record technical reproducibility, maintainer usefulness, policy eligibility and account trust; do not collapse those labels into slop. Preregister a fair ordinary CI/reproducer baseline before observing the A07 mechanism. Gate coverage and maintainer-effort outcomes require real cases, not rewriting source groups into fixtures. Current disposition: evidence refinement pending, no shortlist approval or prototype adoption claim.

Native challenges: bd-87c0 to Z head, bd-8843 to Claude. Source checks are paraphrased; no long quotations copied.


## Independent primary-source follow-up: valid near-miss, 2026-10-03

The [curl advisory](https://curl.se/docs/CVE-2025-9086.html) credits Google Big Sleep as reporter and Daniel Stenberg as patch author. It gives the triggering sequence: secure HTTPS cookie, same-host HTTP request, and replacement cookie with slash-only path. It names affected versions8.13.0–8.15.0 and fixed8.16.0. This is a described trigger, not an independently executed reproducer.

The [fix commit](https://github.com/curl/curl/commit/c6ae07c6a541e0e96d0040afb6) was independently fetched. Its lib/cookie.c diff retains the leading slash by changing the trailing-slash condition from len to len>1, initializes the separator pointer, and checks the path before scanning beyond its first byte. One file, six additions/five deletions; no regression test in this commit.

[PR18266](https://github.com/curl/curl/pull/18266) identifies maintainer bagder as author, credits Big Sleep, and records closure in c6ae07c on August12,2025. No review is displayed on the fetched page. A closed PR here corresponds to a fix landing; do not classify every closed submission as invalid.

Patch source and primary outcome are now observed, narrowing the earlier missing-diff uncertainty. AI-found/human-patched remains the correct attribution. The original report body and an executable validated reproducer remain unverified; no four-artifact pair/corpus efficacy approval, source copied code, or local execution. Muse retains independent follow-up ownership.

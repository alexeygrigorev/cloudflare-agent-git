# Source: Cloudflare competition announcement (fetched 2026-10-02 via r.jina.ai)

URL: https://blog.cloudflare.com/next-git-platform-on-cloudflare/ (published 2026-10-01T13:00Z)

Key verbatim facts (E-C001..E-C008):
- E-C001 "We aren't looking for GitHub as it exists today with agents added on top. At a minimum, we want to see multiple agents working on changes concurrently."
- E-C002 Submit: "A 5-10 minute video demonstrating what you built, what it enables agents and developers to do, and how it works"; "A link to the source code, which must be provided under a permissive open source license (MIT, Apache, BSD)"; "Instructions for running or trying the project".
- E-C003 "Submissions are open until October 14, 2026." (no time/timezone stated in blog; rules page http://cloudflare.com/git-competition to be verified by claude-zcode-redteam)
- E-C004 Prize: top three teams flown (up to two members) to Cloudflare Connect SF; first place $25,000 Cloudflare credits.
- E-C005 Framing questions: "How do agents know what other agents are working on? What happens when they make conflicting changes? How do you review everything they produce? How do you keep track of not just what changed, but why a change was made?"
- E-C006 Primitives: Artifacts binding can create/fork repos, read files/commits, issue repo-scoped Git tokens (https://developers.cloudflare.com/artifacts/api/workers-binding/); event subscriptions for created/imported/forked/deleted/pushed/cloned/fetched (example event type `cf.artifacts.repo.pushed` delivered via Queue to Worker -> Workflow).
- E-C007 Workers Builds Artifacts integration: push to production branch deploys; other branches create Workers Previews (https://developers.cloudflare.com/workers/ci-cd/builds/git-integration/artifacts-integration/). EU/US jurisdiction per namespace. Per-repo metrics.
- E-C008 "Artifacts is available in open beta to customers on the Workers Paid plan." "We will begin billing for Artifacts usage on October 15, 2026."
- Suggested directions in post: "rethink repositories, branches, pull requests, worktrees, code review, and merge conflicts — or build new ways to preserve agent context, compare multiple changes at the same time, and decide which one should ship."

# Claude Design iterations

Actual signed-in web project: https://claude.ai/design/p/9c548064-9f6a-4f12-977d-1e9e2cb67831

## First design and its internal reviews

2026-10-03: The desktop orchestrator used the user-requested https://claude.ai/design interface, uploaded the approved ImageGen illustration, and requested the homepage, project landings, checklist, daily report, field-note archive and shared visual system. Actual selected model: Opus 5.5. Claude created an interactive prototype and a visual-system page, then iterated diagram label size, overlap and grain through its own reviews.

Claude independently read the public repository and corrected three names supplied incorrectly by the orchestrator in the initial prompt. They were not human naming requests. The site retains the actual five hypothesis names. This correction was acknowledged explicitly in the second web request.

Adopted visual language: white paper, cobalt geometric agent markers, ink-black branching paths and folder/page forms, sparse orange annotation rings, subtle print texture, editorial serif headlines and clear plain prose. Hypothesis identity uses circle(A01), square(A16), triangle(A05), diamond(A06), pentagon(A10); the open sixth slot is not a selected product. Functional diagrams remain labelled conceptual and never imply measured benefit.

## Second round against production

The first site deployed successfully as commit53ec46c: https://alexeygrigorev.com/cloudflare-agent-git/ . The second Claude Design request supplied that real URL and asked for production-specific refinements. Claude fetched the actual page text and read site.css/team-workflow.svg; it explicitly could not inspect production in a browser. Its mobile assessment is calculated from source, not a measured screenshot. Root separately checked the actual public homepage, Opus daily report, project navigation and checklist in a browser, including a390px viewport with no document-wide horizontal overflow.

Actual requested changes from Claude's second response:

1. Minimum12px metadata, banner and byline text; less compressed phone headlines.
2. Diagram labels at least3.5percent of SVG width, with a portrait responsibility diagram on phones.
3. Checklist state/date/source, including failed storage/runtime results and withdrawn A01 primary; words and distinct shapes, not color alone or misleading link-arrow marks.
4. Exact built commit and evidence cutoff on every page; readable field-note dates and source-derived titles.
5. One diagram per project using the same shape-agent/folder/branch/orange-ring parts, explicitly conceptual rather than a measured result.

These changes were sent to the independently owned static-site implementation lane for a concrete follow-up. Root verifies the new deployment and actual mobile assets before claiming completion. Claude's prototype also replaced invented03:05 timestamps/countdowns and its own first-person draft with the actual published Opus article and02:24UTC cutoff. Remaining prototype-only grain rendering is not asserted as a production defect.

The dedicated daily Opus writer follows the Telegram writing assistant Substack voice guide and stylint. Private reference corpus and raw design/writer tool logs are not published. Future reports/illustrations use VISUALS.md and this same design project; social-account posting is not automated.


## Adopted implementation release

All five production recommendations are implemented in the static-site lane: five distinct matching project diagrams, portrait team diagram in About and daily articles, minimum12px metadata, readable phone headlines, dated failed/withdrawn/pending/recorded checklist states, exact CIbuildSHA/time and evidence cutoffs on every page, and source-derived field-note headings with readable dates. Proposed workflows are explicitly unvalidated. SVG labels28px in a600px viewBox render near15px at330px width. Implementation build/local links/RSS/HTML safety/accessibility and semantic checks pass. Root will verify this accepted commit in the actual public browser before final handoff.

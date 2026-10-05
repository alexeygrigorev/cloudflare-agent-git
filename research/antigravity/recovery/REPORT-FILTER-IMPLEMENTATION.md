# REPORT-FILTER-IMPLEMENTATION — Public `/history/` product and hour filters

**Date:** 2026-10-05  
**Scope:** Implementation of the accepted filter contract in `REPORT-HISTORY-FILTERS.md` (reviewer ACCEPT in `research/antigravity/reviews/REV-REPORT-HISTORY-FILTERS.md`).  
**Reviewer:** public-journal-site  
**Working directory:** `/home/alexey/git/cloudflare-agent-git`  
**Not edited:** `launcher/`, `tests/` under agent-quota-launcher, `SPEC.md`, `coordination/TASKS.json`, `build.py`.

---

## Files changed

| Path | Change |
|---|---|
| `website/history.py` | Filter contract helpers, data-* markup, four product chips, Berlin hour selects, inlined payload, source stamp, default KPIs computed from the export |
| `website/assets/history-filter.js` | New. Vanilla progressive-enhancement script (signup.js pattern, no new dependency) |
| `website/assets/site.css` | Filter-bar layout, chip/select styles, mobile wrap, 0px overflow guards; dropped `min-width:600px` on the chart SVG |
| `website/test_history.py` | Extended with filter-contract unit tests (24 tests total) |

---

## What the page does now

JavaScript off still serves the full 24h / four-product snapshot (progressive enhancement). With JS:

1. **Four canonical chips** — Branches, Dashboard, Launcher, Coordination (`agent-branches`, `agent-dashboard`, `quota-launcher`, `agent-coordination`). Independent toggles, default all on. Empty selection is an empty state, not “show all”. `unattributed` is not a chip and is not inlined.
2. **Half-open Berlin hour bounds** — From/To `<select>` options are bucket edges, labeled in Berlin time with UTC subtitles. A bucket is in range iff `start <= bucket_start_utc < end`. Mid-hour query values snap to those edges. Inverted or empty overlap zeroes KPIs and shows an explicit empty message. Unobserved rows inside the range stay. Date range does not hide task cards.
3. **Query-string persistence** — Shareable `?product=agent-branches,quota-launcher&from=2026-10-04T13:00:00Z` (default view is a clean URL). Invalid product ids or timestamps fall back to the full window / all products. `replaceState` keeps the current view copyable.
4. **Inlined telemetry** — `<script type="application/json" id="history-telemetry-data">` holds a sanitized subset (window, four products, per-bucket presence/work/status/tokens). Chart bars and KPIs recompute from that payload with no second network hop. The existing JSON URL remains a fallback link.

Filter applies to ledger columns (Tokens column hides when no selected product has an in-range token cell), chart (re-sum selected products; pack in-range hours), KPIs, and task cards (product filter only).

---

## Privacy

Public HTML, inlined payload, and `history-filter.js` contain no `/home/alexey`, `/Users/`, `/tmp/`, session UUIDs, `unattributed`, or `token=` query keys. Agent-count fields from the on-disk export are omitted from the inline payload. Visible labels are the four product names / chip words, not internal session ids.

---

## Tests and browser checks

`python3 -m unittest website.test_history -v` — **24 passed** (0.05s). Coverage includes half-open inclusion, empty product selection, invalid-param fallback, token KPI only when the attributed bucket is in range, inverted bounds, Berlin option labels, inlined JSON hygiene, chip labels, and CSS overflow guards.

Chromium (system `/usr/bin/chromium-browser`, single-process, 390×844 and 1440×1000) against a local preview of the built page:

| Case | Result |
|---|---|
| Default | KPIs `1,086,844` / `20 / 24` / `12.63 h` / `4 Teams`; 24 rows; 4 cards; empty search; overflow **0px** |
| Dashboard only | Tokens `680,764`; `1 Team`; 3 cards hidden; `?product=agent-dashboard`; overflow **0px** |
| No products | Empty copy “Select at least one product…”; tokens `0`; `?product=`; overflow **0px** |
| Shared URL `product=agent-branches,quota-launcher&from=2026-10-04T13:00:00Z` | `11.30 h`, `18 / 18`, 2 cards, tokens column hidden (attribution buckets out of range) |
| Coordination `[12:00Z, 13:00Z)` | Tokens `406,080`; `1 / 1`; 1 row; 1 card |
| Invalid `?product=nope&from=not-a-date` | Falls back to full window / all products; clean URL |
| Inverted From/To | Empty range copy; KPIs zeroed; 4 cards remain; overflow **0px** |
| Reset | Restores default KPIs and clean URL |

Mobile 390px overflow was **0px** on default, dashboard-only, empty-products, shared-URL, and coordination-slice views. Desktop 1440px overflow was **0px**.

---

## Limits

This is client-side filtering of the frozen public export. It does not add a live collector, server-side filter endpoint, private `/api/tasks` fold-in, or FileBus identities. Source stamp uses `generated_at_utc` plus the window and states that filtering does not refresh the collector.

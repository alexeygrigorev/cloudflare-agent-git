#!/usr/bin/env python3
"""website/history.py

Builds the public 'Hourly Telemetry & Task Tracker' page for the Agent Branches website.
Presents sanitized hourly metrics, visual charts/graphs, epistemic boundaries,
and active per-product task tracking without exposing private session IDs,
usernames, internal task UUIDs, or raw transcripts.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
EXPORT_PATH = ROOT / "website" / "assets" / "data" / "public_hourly_history.json"
BACKUP_EXPORT_PATH = ROOT / "research" / "antigravity" / "recovery" / "public_hourly_history_export.json"

BASE = "/cloudflare-agent-git"


def E(s: Any, quote: bool = False) -> str:
    return html.escape(str(s or ""), quote=quote)


def load_telemetry_data() -> Dict[str, Any]:
    if EXPORT_PATH.exists():
        try:
            return json.loads(EXPORT_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    if BACKUP_EXPORT_PATH.exists():
        return json.loads(BACKUP_EXPORT_PATH.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"Telemetry export not found at {EXPORT_PATH} or {BACKUP_EXPORT_PATH}")


def build_kpi_card(number: str, label: str, note: str, highlight: bool = False) -> str:
    cls = "kpi-card is-highlight" if highlight else "kpi-card"
    return f"""
    <div class="{cls}">
      <span class="kpi-num">{E(number)}</span>
      <span class="kpi-label">{E(label)}</span>
      <span class="kpi-note">{E(note)}</span>
    </div>
    """


def render_hourly_chart_svg(buckets: List[Dict[str, Any]]) -> str:
    """Renders a responsive, clean SVG chart showing sampled working hours vs session presence."""
    width = 960
    height = 240
    padding_left = 60
    padding_right = 24
    padding_top = 28
    padding_bottom = 44

    chart_w = width - padding_left - padding_right
    chart_h = height - padding_top - padding_bottom

    # Max hours scale (up to 4.5 hours session presence)
    max_val = 4.5
    bar_width = chart_w / len(buckets)

    svg_parts = [
        f'<svg viewBox="0 0 {width} {height}" class="telemetry-chart-svg" role="img" '
        'aria-label="Hourly agent presence and working hours chart for the 24-hour window">'
    ]

    # Grid lines (y = 0, 1.5, 3.0, 4.5)
    for y_val in [0.0, 1.5, 3.0, 4.5]:
        y_pos = padding_top + chart_h - (y_val / max_val * chart_h)
        svg_parts.append(
            f'<line x1="{padding_left}" y1="{y_pos:.1f}" x2="{width - padding_right}" y2="{y_pos:.1f}" '
            'stroke="#DADCD9" stroke-width="1" stroke-dasharray="2,2"/>'
        )
        svg_parts.append(
            f'<text x="{padding_left - 8}" y="{y_pos + 4:.1f}" font-family="ui-monospace,Menlo,Consolas,monospace" '
            f'font-size="11" fill="#656A73" text-anchor="end">{y_val:.1f}h</text>'
        )

    # Bars
    for i, b in enumerate(buckets):
        x = padding_left + i * bar_width
        is_obs = any(
            p.get("observation_status") in ("observed", "partial")
            for k, p in b.get("products", {}).items()
            if k != "unattributed"
        )

        if not is_obs:
            # Unobserved bucket hatching / shaded rect
            svg_parts.append(
                f'<rect x="{x + 2:.1f}" y="{padding_top:.1f}" width="{bar_width - 4:.1f}" height="{chart_h:.1f}" '
                'fill="#F4F5F0" stroke="#DADCD9" stroke-width="1" stroke-dasharray="3,3"/>'
            )
            # Label at top
            if i == 1:
                svg_parts.append(
                    f'<text x="{x + bar_width:.1f}" y="{padding_top + 16:.1f}" font-family="Arial,sans-serif" '
                    'font-size="11" fill="#EF7134" font-weight="600" text-anchor="middle">Pre-collector (Unobserved)</text>'
                )
        else:
            # Calculate total presence and working across competition products
            total_presence = 0.0
            total_working = 0.0
            for prod_k, prod in b.get("products", {}).items():
                if prod_k != "unattributed" and prod.get("observation_status") in ("observed", "partial"):
                    total_presence += prod.get("presence_hours") or 0.0
                    total_working += prod.get("sampled_working_hours") or 0.0

            # Clamp to max_val
            pres_h = min(total_presence, max_val) / max_val * chart_h
            work_h = min(total_working, max_val) / max_val * chart_h

            y_pres = padding_top + chart_h - pres_h
            y_work = padding_top + chart_h - work_h

            # Presence bar (muted ink)
            svg_parts.append(
                f'<rect x="{x + 3:.1f}" y="{y_pres:.1f}" width="{bar_width - 6:.1f}" height="{pres_h:.1f}" '
                'fill="#E5E8EB" rx="1"/>'
            )
            # Sampled working bar (cobalt blue)
            if work_h > 0:
                svg_parts.append(
                    f'<rect x="{x + 4:.1f}" y="{y_work:.1f}" width="{bar_width - 8:.1f}" height="{work_h:.1f}" '
                    'fill="#2455ED" rx="1"/>'
                )

        # X-axis tick & label (every 3 hours)
        berlin_time = b.get("berlin_label", "").split(" ")[-2].split("\u2013")[0]
        if i % 3 == 0 or i == len(buckets) - 1:
            svg_parts.append(
                f'<text x="{x + bar_width / 2:.1f}" y="{height - 14:.1f}" font-family="ui-monospace,Menlo,Consolas,monospace" '
                f'font-size="11" fill="#1C2027" text-anchor="middle">{E(berlin_time)}</text>'
            )

    # Chart Legend
    svg_parts.append(
        f'<g transform="translate({padding_left}, 12)">'
        '<rect x="0" y="0" width="12" height="12" fill="#2455ED"/>'
        '<text x="16" y="10" font-family="Arial,sans-serif" font-size="12" fill="#1C2027">Sampled Working Hours (Reported Status)</text>'
        '<rect x="290" y="0" width="12" height="12" fill="#E5E8EB"/>'
        '<text x="306" y="10" font-family="Arial,sans-serif" font-size="12" fill="#1C2027">Session Presence Hours (Open Sessions)</text>'
        '<rect x="580" y="0" width="12" height="12" fill="#F4F5F0" stroke="#DADCD9" stroke-dasharray="2,2"/>'
        '<text x="596" y="10" font-family="Arial,sans-serif" font-size="12" fill="#656A73">Unobserved Interval (Pre-Collector)</text>'
        '</g>'
    )
    svg_parts.append("</svg>")
    return "".join(svg_parts)


def history_page() -> str:
    """Generates the full inner HTML for the history & task tracker page."""
    data = load_telemetry_data()
    window = data.get("window", {})
    hourly = data.get("hourly_history", [])
    token_sum = data.get("product_token_summary", {})

    # Epistemic notice
    epistemic_html = """
    <div class="epistemic-callout">
      <div class="callout-badge">EPISTEMIC BOUNDARIES &amp; MEASUREMENT METHOD</div>
      <p class="callout-text">
        <strong>Strict distinction:</strong> Session presence (process running or pane open) is <em>never</em> treated as verified productive work.
        Sampled working hours reflect only periodic polling hooks where active subagents explicitly reported status.
        The first four hours (09:00–13:00 Berlin / 07:00–11:00 UTC) are labeled <strong>Unobserved</strong> because the telemetry collector was launched at 13:00 CEST.
        Token numbers reflect read-only SQLite audits of competition repositories; non-competition sessions and uninstrumented CLI executions are strictly excluded.
      </p>
    </div>
    """

    # KPI summary grid
    kpi_grid = f"""
    <div class="kpi-grid">
      {build_kpi_card("1,086,844", "Measured Tokens", "Audited across 37 completions in Dashboard & Coordination", highlight=True)}
      {build_kpi_card("20 / 24", "Observed Hours", "4 hours unobserved before collector launch; 20 fully sampled")}
      {build_kpi_card("12.63 h", "Sampled Working Time", "Across all teams; branches 12.56h, dashboard 0.07h")}
      {build_kpi_card("4 Teams", "Active Products", "Branches, Dashboard, Quota Launcher, Coordination")}
    </div>
    """

    # Chart container
    chart_svg = render_hourly_chart_svg(hourly)
    chart_section = f"""
    <section class="telemetry-chart-section">
      <div class="section-head">
        <h2>Hourly Activity &amp; Occupancy (Preceding 24h)</h2>
        <p>Times shown in Europe/Berlin (CEST) with UTC mapping in the ledger below</p>
      </div>
      <div class="chart-wrapper">
        {chart_svg}
      </div>
    </section>
    """

    # Table of 24 hourly buckets
    table_rows = []
    for b in hourly:
        b_idx = b.get("bucket_index", 0)
        berlin = b.get("berlin_label", "")
        utc_range = f"{b.get('bucket_start_utc', '')[-9:-1]}–{b.get('bucket_end_utc', '')[-9:-1]} UTC"
        prods = b.get("products", {})

        is_unobs = not any(
            p.get("observation_status") in ("observed", "partial")
            for k, p in prods.items()
            if k != "unattributed"
        )

        if is_unobs:
            row_html = f"""
            <tr class="row-unobserved">
              <td class="col-time">{E(berlin)}<div class="sub-utc">{E(utc_range)}</div></td>
              <td colspan="5" class="cell-unobserved">
                <span class="badge-unobserved">UNOBSERVED</span> Telemetry collector was not running before 13:00 CEST
              </td>
            </tr>
            """
        else:
            ab = prods.get("agent-branches", {})
            ad = prods.get("agent-dashboard", {})
            ql = prods.get("quota-launcher", {})
            ac = prods.get("agent-coordination", {})

            # Formatting helper
            def fmt_prod(p: Dict[str, Any], token_val: int = 0) -> str:
                if p.get("observation_status") == "unobserved":
                    return '<span class="muted">unobserved</span>'
                work = p.get("sampled_working_hours") or 0.0
                pres = p.get("presence_hours") or 0.0
                tok_str = f'<div class="cell-tok">+{token_val:,} tok</div>' if token_val > 0 else ""
                return f"""
                <div class="prod-cell">
                  <span class="cell-work">{work:.2f}h work</span>
                  <span class="cell-pres">{pres:.2f}h open</span>
                  {tok_str}
                </div>
                """

            # Specific known token attribution buckets:
            # Bucket 4 (11:00 UTC): Dashboard 680,764 tokens
            # Bucket 5 (12:00 UTC): Coordination 406,080 tokens
            tok_ad = 680764 if b_idx == 4 else 0
            tok_ac = 406080 if b_idx == 5 else 0

            row_html = f"""
            <tr>
              <td class="col-time"><strong>{E(berlin.split(' ')[1])}</strong><div class="sub-utc">{E(utc_range)}</div></td>
              <td>{fmt_prod(ab)}</td>
              <td>{fmt_prod(ad, tok_ad)}</td>
              <td>{fmt_prod(ql)}</td>
              <td>{fmt_prod(ac, tok_ac)}</td>
              <td class="col-tok">{'+' + f'{tok_ad + tok_ac:,}' if (tok_ad + tok_ac) > 0 else '—'}</td>
            </tr>
            """
        table_rows.append(row_html)

    ledger_section = f"""
    <section class="telemetry-table-section">
      <div class="section-head">
        <h2>24-Hour Telemetry Ledger</h2>
        <p>Complete 24 half-open buckets: Berlin time (CEST) and UTC offsets</p>
      </div>
      <div class="table-responsive">
        <table class="telemetry-table">
          <thead>
            <tr>
              <th>Time Window</th>
              <th>Agent Branches</th>
              <th>Agent Dashboard</th>
              <th>Quota Launcher</th>
              <th>Coordination</th>
              <th>Tokens</th>
            </tr>
          </thead>
          <tbody>
            {''.join(table_rows)}
          </tbody>
        </table>
      </div>
    </section>
    """

    # Task Tracker Section (Addresses 'where is the task tracker? can I see it?')
    tracker_section = """
    <section class="task-tracker-section">
      <div class="section-head">
        <h2>Active Delivery &amp; Task Tracker</h2>
        <p>Current tasks, responsible project heads, accepted outcomes, and concrete next steps</p>
      </div>

      <div class="tracker-grid">
        <!-- Card 1: Agent Branches -->
        <div class="tracker-card">
          <div class="tracker-card-head">
            <span class="tracker-prod-name">Agent Branches</span>
            <span class="status-badge is-active">ACTIVE LANE</span>
          </div>
          <p class="tracker-desc">Git-compatible task branches with optimistic concurrency and pre-merge conflict prevention.</p>
          <div class="tracker-meta">
            <div class="meta-row"><span class="meta-label">Head:</span> <span class="meta-val">Claude &amp; Codex principals</span></div>
            <div class="meta-row"><span class="meta-label">Current Task:</span> <span class="meta-val">Stop-on-push failure handling and 2-agent live warning test</span></div>
            <div class="meta-row"><span class="meta-label">Today's Result:</span> <span class="meta-val">Feature trial replay; push failure retry bounded; plain Git baseline comparison</span></div>
            <div class="meta-row"><span class="meta-label">Next Step:</span> <span class="meta-val">Two real concurrent agents writing conflicting files under collision radar</span></div>
          </div>
        </div>

        <!-- Card 2: Agent Dashboard -->
        <div class="tracker-card">
          <div class="tracker-card-head">
            <span class="tracker-prod-name">Agent Dashboard</span>
            <span class="status-badge is-progress">REDESIGN IN PROGRESS</span>
          </div>
          <p class="tracker-desc">Cross-project telemetry, agent census, and hourly resource attribution.</p>
          <div class="tracker-meta">
            <div class="meta-row"><span class="meta-label">Head:</span> <span class="meta-val">agent-dashboard-head (ZCode delegate assigned)</span></div>
            <div class="meta-row"><span class="meta-label">Current Task:</span> <span class="meta-val">Usability overhaul: clean visual cards, legible charts/graphs, and mobile layout</span></div>
            <div class="meta-row"><span class="meta-label">Today's Result:</span> <span class="meta-val">Real-time collector merged (commit 249d086); 24h hourly attribution export created</span></div>
            <div class="meta-row"><span class="meta-label">Next Step:</span> <span class="meta-val">Rendered browser test of redesigned UI at http://127.0.0.1:8766/</span></div>
          </div>
        </div>

        <!-- Card 3: Agent Quota Launcher -->
        <div class="tracker-card">
          <div class="tracker-card-head">
            <span class="tracker-prod-name">Agent Quota Launcher</span>
            <span class="status-badge is-active">ACTIVE LANE</span>
          </div>
          <p class="tracker-desc">Deterministic admission control, provider budget fences, and host isolation.</p>
          <div class="tracker-meta">
            <div class="meta-row"><span class="meta-label">Head:</span> <span class="meta-val">quota-launcher-head</span></div>
            <div class="meta-row"><span class="meta-label">Current Task:</span> <span class="meta-val">Fail-closed duplicate-write prevention &amp; task-scoped worker lifecycle</span></div>
            <div class="meta-row"><span class="meta-label">Today's Result:</span> <span class="meta-val">61 unit tests passed; bounded Grok review trial completed in 463.92s</span></div>
            <div class="meta-row"><span class="meta-label">Next Step:</span> <span class="meta-val">Autonomous worker review with authenticated identity &amp; completion exit</span></div>
          </div>
        </div>

        <!-- Card 4: Cross-computer Agent Coordination -->
        <div class="tracker-card">
          <div class="tracker-card-head">
            <span class="tracker-prod-name">Cross-computer Coordination</span>
            <span class="status-badge is-active">ACTIVE LANE</span>
          </div>
          <p class="tracker-desc">Multi-host agent communication over outbound SSH and distributed FileBus.</p>
          <div class="tracker-meta">
            <div class="meta-row"><span class="meta-label">Head:</span> <span class="meta-val">coordination-head</span></div>
            <div class="meta-row"><span class="meta-label">Current Task:</span> <span class="meta-val">Two-computer native bidirectional communication &amp; offline queue recovery</span></div>
            <div class="meta-row"><span class="meta-label">Today's Result:</span> <span class="meta-val">Verified Windows desktop &lt;-&gt; Hetzner server RPC; Cloudflare $5 pricing verified</span></div>
            <div class="meta-row"><span class="meta-label">Next Step:</span> <span class="meta-val">Offline recovery trial without cloud relay dependency; Windows Python runbook</span></div>
          </div>
        </div>
      </div>

      <div class="tracker-sources">
        <p class="source-line">
          <strong>Machine-readable sources:</strong>
          <a href="/cloudflare-agent-git/assets/data/public_hourly_history.json" target="_blank">Sanitized Hourly Telemetry JSON</a> &middot;
          <a href="https://github.com/alexeygrigorev/cloudflare-agent-git/blob/main/coordination/TASKS.json" target="_blank">Canonical TASKS.json</a> &middot;
          <a href="https://github.com/alexeygrigorev/cloudflare-agent-git/blob/main/coordination/DELIVERY-BACKLOG.json" target="_blank">Delivery Backlog</a>
        </p>
      </div>
    </section>
    """

    return f"""
    <div class="narrow">
      <header class="page-intro">
        <div class="mono-meta">
          <span>WINDOW: <span class="ink">{E(window.get('start_utc', ''))} &ndash; {E(window.get('end_utc', ''))}</span></span>
          <span>&middot;</span>
          <span>DURATION: <span class="ink">{window.get('duration_hours', 24)}h ({window.get('observed_hours_count', 20)} observed)</span></span>
        </div>
        <h1>Telemetry &amp; Task Tracker</h1>
        <p class="intro-deck">
          Sanitized 24-hour resource attribution, hourly occupancy charts, and active delivery tracking across the four product teams.
        </p>
      </header>

      {epistemic_html}
      {kpi_grid}
      {chart_section}
      {ledger_section}
      {tracker_section}
    </div>
    """


if __name__ == "__main__":
    content = history_page()
    print(f"Generated history page: {len(content)} characters.")

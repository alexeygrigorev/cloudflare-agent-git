#!/usr/bin/env python3
"""website/history.py

Builds the public 'Hourly Telemetry & Task Tracker' page for the Agent Branches website.
Presents sanitized hourly metrics, visual charts/graphs, epistemic boundaries,
and active per-product task tracking without exposing private session IDs,
usernames, internal task UUIDs, or raw transcripts.

Client-side product chips and half-open Berlin hour bounds follow
research/antigravity/recovery/REPORT-HISTORY-FILTERS.md. JavaScript off keeps
the full 24h / four-product snapshot.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
EXPORT_PATH = ROOT / "website" / "assets" / "data" / "public_hourly_history.json"
BACKUP_EXPORT_PATH = ROOT / "research" / "antigravity" / "recovery" / "public_hourly_history_export.json"

BASE = "/cloudflare-agent-git"
BERLIN = ZoneInfo("Europe/Berlin")
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

CANONICAL_PRODUCTS: Tuple[Dict[str, str], ...] = (
    {"id": "agent-branches", "chip": "Branches", "name": "Agent Branches"},
    {"id": "agent-dashboard", "chip": "Dashboard", "name": "Agent Dashboard"},
    {"id": "quota-launcher", "chip": "Launcher", "name": "Quota Launcher"},
    {"id": "agent-coordination", "chip": "Coordination", "name": "Cross-computer Coordination"},
)
CANONICAL_IDS: Tuple[str, ...] = tuple(p["id"] for p in CANONICAL_PRODUCTS)
CHIP_LABELS = {p["id"]: p["chip"] for p in CANONICAL_PRODUCTS}
PRODUCT_NAMES = {p["id"]: p["name"] for p in CANONICAL_PRODUCTS}

# Verified audit totals land on these half-open buckets of the frozen export.
TOKEN_BUCKET_INDEX = {
    "agent-dashboard": 4,
    "agent-coordination": 5,
}

CHART_WIDTH = 960
CHART_HEIGHT = 240
CHART_PAD_LEFT = 60
CHART_PAD_RIGHT = 24
CHART_PAD_TOP = 28
CHART_PAD_BOTTOM = 44
CHART_MAX_HOURS = 4.5


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


def parse_utc(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp to aware UTC. Naive strings are invalid."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def iso_z(dt: datetime) -> str:
    utc = dt.astimezone(timezone.utc).replace(microsecond=0)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def format_berlin(dt: datetime) -> str:
    local = dt.astimezone(BERLIN)
    tzname = local.tzname() or "CEST"
    return f"{local.day} {_MONTHS[local.month - 1]} {local.strftime('%H:%M')} {tzname}"


def format_utc_short(dt: datetime) -> str:
    utc = dt.astimezone(timezone.utc)
    return f"{utc.day} {_MONTHS[utc.month - 1]} {utc.strftime('%H:%M')} UTC"


def canonical_product_ids() -> Tuple[str, ...]:
    return CANONICAL_IDS


def token_attribution(data: Mapping[str, Any]) -> Dict[str, Tuple[int, int]]:
    """Map product id → (bucket_index, tokens) for measured products only."""
    summary = data.get("product_token_summary") or {}
    out: Dict[str, Tuple[int, int]] = {}
    for pid, idx in TOKEN_BUCKET_INDEX.items():
        tok = int((summary.get(pid) or {}).get("total_tokens") or 0)
        if tok > 0:
            out[pid] = (idx, tok)
    return out


def tokens_for_bucket(data: Mapping[str, Any], product_id: str, bucket_index: int) -> int:
    attr = token_attribution(data)
    pair = attr.get(product_id)
    if pair and pair[0] == bucket_index:
        return pair[1]
    return 0


def public_filter_payload(data: Mapping[str, Any]) -> Dict[str, Any]:
    """Sanitized payload inlined for progressive enhancement. No unattributed, paths, or ids."""
    window = data.get("window") or {}
    hourly = data.get("hourly_history") or []
    attr = token_attribution(data)
    buckets = []
    for b in hourly:
        idx = int(b.get("bucket_index") or 0)
        products = {}
        src = b.get("products") or {}
        for pid in CANONICAL_IDS:
            cell = src.get(pid) or {}
            products[pid] = {
                "observation_status": cell.get("observation_status") or "unobserved",
                "coverage_fraction": cell.get("coverage_fraction"),
                "active_presence_agents": cell.get("active_presence_agents"),
                "active_working_agents": cell.get("active_working_agents"),
                "presence_hours": cell.get("presence_hours"),
                "sampled_working_hours": cell.get("sampled_working_hours"),
                "tokens": tokens_for_bucket(data, pid, idx),
            }
        buckets.append(
            {
                "bucket_index": idx,
                "bucket_start_utc": b.get("bucket_start_utc"),
                "bucket_end_utc": b.get("bucket_end_utc"),
                "berlin_label": b.get("berlin_label"),
                "products": products,
            }
        )
    return {
        "generated_at_utc": data.get("generated_at_utc"),
        "window": {
            "start_utc": window.get("start_utc"),
            "end_utc": window.get("end_utc"),
            "duration_hours": window.get("duration_hours"),
            "observed_hours_count": window.get("observed_hours_count"),
        },
        "products": [
            {"id": p["id"], "chip": p["chip"], "name": p["name"]} for p in CANONICAL_PRODUCTS
        ],
        "token_attribution": [
            {"product": pid, "bucket_index": idx, "tokens": tok}
            for pid, (idx, tok) in attr.items()
        ],
        "hourly": buckets,
    }


def embed_json(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=True, separators=(",", ":"))
    return raw.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def bucket_in_range(bucket: Mapping[str, Any], start: datetime, end: datetime) -> bool:
    """Half-open: start <= bucket_start_utc < end."""
    b_start = parse_utc(str(bucket.get("bucket_start_utc") or ""))
    if b_start is None:
        return False
    return start <= b_start < end


def _window_bounds(data: Mapping[str, Any]) -> Tuple[datetime, datetime]:
    window = data.get("window") or {}
    start = parse_utc(str(window.get("start_utc") or ""))
    end = parse_utc(str(window.get("end_utc") or ""))
    if start is None or end is None:
        raise ValueError("Telemetry window is missing UTC bounds")
    return start, end


def _bucket_starts(data: Mapping[str, Any]) -> List[datetime]:
    out = []
    for b in data.get("hourly_history") or []:
        dt = parse_utc(str(b.get("bucket_start_utc") or ""))
        if dt is not None:
            out.append(dt)
    return out


def _bucket_ends(data: Mapping[str, Any]) -> List[datetime]:
    out = []
    for b in data.get("hourly_history") or []:
        dt = parse_utc(str(b.get("bucket_end_utc") or ""))
        if dt is not None:
            out.append(dt)
    return out


def snap_from(dt: datetime, data: Mapping[str, Any]) -> datetime:
    win_start, win_end = _window_bounds(data)
    if dt <= win_start:
        return win_start
    if dt >= win_end:
        return win_end
    prev = win_start
    for edge in _bucket_starts(data):
        if edge == dt:
            return edge
        if edge < dt:
            prev = edge
        else:
            break
    return prev


def snap_to(dt: datetime, data: Mapping[str, Any]) -> datetime:
    win_start, win_end = _window_bounds(data)
    if dt <= win_start:
        return win_start
    if dt >= win_end:
        return win_end
    for edge in _bucket_ends(data):
        if edge == dt:
            return edge
        if edge > dt:
            return edge
    return win_end


def normalize_product_selection(ids: Optional[Iterable[str]], *, missing: bool) -> Optional[Tuple[str, ...]]:
    """Return canonical ids, empty tuple, or None when the param is invalid.

    missing=True (no product query key) → all products.
    Explicit empty list → empty selection (empty state, not 'show all').
    Unknown ids → None (caller falls back to all products).
    """
    if missing:
        return CANONICAL_IDS
    if ids is None:
        return CANONICAL_IDS
    seq = [str(x).strip() for x in ids if str(x).strip()]
    if not seq:
        return tuple()
    known = set(CANONICAL_IDS)
    if any(x not in known for x in seq):
        return None
    ordered = tuple(pid for pid in CANONICAL_IDS if pid in set(seq))
    return ordered


@dataclass(frozen=True)
class FilterState:
    product_ids: Tuple[str, ...]
    start_utc: str
    end_utc: str


def default_filter_state(data: Mapping[str, Any]) -> FilterState:
    win_start, win_end = _window_bounds(data)
    return FilterState(CANONICAL_IDS, iso_z(win_start), iso_z(win_end))


def parse_filter_params(params: Mapping[str, Optional[str]], data: Mapping[str, Any]) -> FilterState:
    """Parse query-string fields. Invalid product/from/to fall back to the full window / all products."""
    fallback = default_filter_state(data)
    has_product = "product" in params
    raw_product = params.get("product") if has_product else None
    if has_product:
        if raw_product is None or raw_product == "":
            ids: Optional[Tuple[str, ...]] = tuple()
        else:
            ids = normalize_product_selection(raw_product.split(","), missing=False)
            if ids is None:
                ids = fallback.product_ids
    else:
        ids = fallback.product_ids

    start = parse_utc(params.get("from")) if params.get("from") else None
    end = parse_utc(params.get("to")) if params.get("to") else None
    win_start, win_end = _window_bounds(data)
    if start is None and params.get("from"):
        start_s = fallback.start_utc
        end_s = fallback.end_utc
        return FilterState(ids, start_s, end_s)
    if end is None and params.get("to"):
        start_s = fallback.start_utc
        end_s = fallback.end_utc
        return FilterState(ids, start_s, end_s)
    if start is None:
        start = win_start
    else:
        start = snap_from(start, data)
    if end is None:
        end = win_end
    else:
        end = snap_to(end, data)
    return FilterState(ids, iso_z(start), iso_z(end))


def serialize_filter_query(state: FilterState, data: Mapping[str, Any]) -> str:
    """Shareable query string. Default full view is empty (no params)."""
    fallback = default_filter_state(data)
    parts: List[str] = []
    if state.product_ids != fallback.product_ids:
        parts.append("product=" + ",".join(state.product_ids))
    if state.start_utc != fallback.start_utc:
        parts.append("from=" + state.start_utc)
    if state.end_utc != fallback.end_utc:
        parts.append("to=" + state.end_utc)
    return "&".join(parts)


def _product_observed(cell: Mapping[str, Any]) -> bool:
    return cell.get("observation_status") in ("observed", "partial")


def compute_kpis(data: Mapping[str, Any], state: FilterState) -> Dict[str, Any]:
    start = parse_utc(state.start_utc)
    end = parse_utc(state.end_utc)
    hourly = data.get("hourly_history") or []
    if start is None or end is None:
        start, end = _window_bounds(data)

    selected = list(state.product_ids)
    in_range = [b for b in hourly if bucket_in_range(b, start, end)]
    empty_reason = None
    if not selected:
        empty_reason = "products"
    elif start >= end or not in_range:
        empty_reason = "range"

    if empty_reason:
        return {
            "tokens": 0,
            "observed_hours": 0,
            "in_range_count": 0 if empty_reason == "range" else len(in_range),
            "sampled_work": 0.0,
            "product_count": len(selected),
            "show_tokens": False,
            "empty_reason": empty_reason,
            "in_range_buckets": [] if empty_reason == "range" else in_range,
        }

    observed = 0
    work = 0.0
    for b in in_range:
        prods = b.get("products") or {}
        if any(_product_observed(prods.get(pid) or {}) for pid in selected):
            observed += 1
        for pid in selected:
            cell = prods.get(pid) or {}
            if _product_observed(cell):
                work += float(cell.get("sampled_working_hours") or 0.0)

    attr = token_attribution(data)
    tokens = 0
    for pid in selected:
        pair = attr.get(pid)
        if not pair:
            continue
        idx, tok = pair
        if idx < 0 or idx >= len(hourly):
            continue
        if bucket_in_range(hourly[idx], start, end):
            tokens += tok

    show_tokens = tokens > 0
    return {
        "tokens": tokens,
        "observed_hours": observed,
        "in_range_count": len(in_range),
        "sampled_work": work,
        "product_count": len(selected),
        "show_tokens": show_tokens,
        "empty_reason": None,
        "in_range_buckets": in_range,
    }


def format_tokens(n: int) -> str:
    return f"{n:,}"


def format_work(hours: float) -> str:
    return f"{hours:.2f} h"


def format_observed(observed: int, total: int) -> str:
    return f"{observed} / {total}"


def hour_bound_options(data: Mapping[str, Any]) -> Dict[str, List[Dict[str, str]]]:
    """From = bucket starts; To = bucket ends. Labels in Berlin time, UTC as subtitle."""
    from_opts = []
    to_opts = []
    for b in data.get("hourly_history") or []:
        start = parse_utc(str(b.get("bucket_start_utc") or ""))
        end = parse_utc(str(b.get("bucket_end_utc") or ""))
        if start is not None:
            from_opts.append(
                {
                    "value": iso_z(start),
                    "berlin": format_berlin(start),
                    "utc": format_utc_short(start),
                }
            )
        if end is not None:
            to_opts.append(
                {
                    "value": iso_z(end),
                    "berlin": format_berlin(end),
                    "utc": format_utc_short(end),
                }
            )
    return {"from": from_opts, "to": to_opts}


def build_kpi_card(number: str, label: str, note: str, highlight: bool = False, kpi_id: str = "") -> str:
    cls = "kpi-card is-highlight" if highlight else "kpi-card"
    ident = f' id="{E(kpi_id, quote=True)}"' if kpi_id else ""
    return f"""
    <div class="{cls}"{ident} data-kpi="{E(kpi_id, quote=True)}">
      <span class="kpi-num" data-full="{E(number, quote=True)}">{E(number)}</span>
      <span class="kpi-label">{E(label)}</span>
      <span class="kpi-note" data-full="{E(note, quote=True)}">{E(note)}</span>
    </div>
    """


def render_hourly_chart_svg(buckets: List[Dict[str, Any]]) -> str:
    """Renders a responsive, clean SVG chart showing sampled working hours vs session presence."""
    width = CHART_WIDTH
    height = CHART_HEIGHT
    padding_left = CHART_PAD_LEFT
    padding_right = CHART_PAD_RIGHT
    padding_top = CHART_PAD_TOP
    padding_bottom = CHART_PAD_BOTTOM

    chart_w = width - padding_left - padding_right
    chart_h = height - padding_top - padding_bottom

    max_val = CHART_MAX_HOURS
    bar_width = chart_w / max(len(buckets), 1)

    svg_parts = [
        f'<svg viewBox="0 0 {width} {height}" class="telemetry-chart-svg" id="history-chart-svg" role="img" '
        'aria-label="Hourly agent presence and working hours chart for the 24-hour window">'
    ]

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

    svg_parts.append('<g id="history-chart-plot">')
    for i, b in enumerate(buckets):
        x = padding_left + i * bar_width
        start = E(b.get("bucket_start_utc", ""), quote=True)
        end = E(b.get("bucket_end_utc", ""), quote=True)
        is_obs = any(
            p.get("observation_status") in ("observed", "partial")
            for k, p in b.get("products", {}).items()
            if k != "unattributed"
        )

        svg_parts.append(
            f'<g class="chart-bar" data-index="{i}" data-start="{start}" data-end="{end}" '
            f'data-observed="{1 if is_obs else 0}">'
        )
        if not is_obs:
            svg_parts.append(
                f'<rect x="{x + 2:.1f}" y="{padding_top:.1f}" width="{bar_width - 4:.1f}" height="{chart_h:.1f}" '
                'fill="#F4F5F0" stroke="#DADCD9" stroke-width="1" stroke-dasharray="3,3"/>'
            )
            if i == 1:
                svg_parts.append(
                    f'<text x="{x + bar_width:.1f}" y="{padding_top + 16:.1f}" font-family="Arial,sans-serif" '
                    'font-size="11" fill="#EF7134" font-weight="600" text-anchor="middle">Pre-collector (Unobserved)</text>'
                )
        else:
            total_presence = 0.0
            total_working = 0.0
            for prod_k, prod in b.get("products", {}).items():
                if prod_k != "unattributed" and prod.get("observation_status") in ("observed", "partial"):
                    total_presence += prod.get("presence_hours") or 0.0
                    total_working += prod.get("sampled_working_hours") or 0.0

            pres_h = min(total_presence, max_val) / max_val * chart_h
            work_h = min(total_working, max_val) / max_val * chart_h

            y_pres = padding_top + chart_h - pres_h
            y_work = padding_top + chart_h - work_h

            svg_parts.append(
                f'<rect x="{x + 3:.1f}" y="{y_pres:.1f}" width="{bar_width - 6:.1f}" height="{pres_h:.1f}" '
                'fill="#E5E8EB" rx="1"/>'
            )
            if work_h > 0:
                svg_parts.append(
                    f'<rect x="{x + 4:.1f}" y="{y_work:.1f}" width="{bar_width - 8:.1f}" height="{work_h:.1f}" '
                    'fill="#2455ED" rx="1"/>'
                )
        svg_parts.append("</g>")
    svg_parts.append("</g>")

    svg_parts.append('<g id="history-chart-xlabels">')
    for i, b in enumerate(buckets):
        x = padding_left + i * bar_width
        berlin_time = b.get("berlin_label", "").split(" ")[-2].split("\u2013")[0]
        if i % 3 == 0 or i == len(buckets) - 1:
            svg_parts.append(
                f'<text x="{x + bar_width / 2:.1f}" y="{height - 14:.1f}" font-family="ui-monospace,Menlo,Consolas,monospace" '
                f'font-size="11" fill="#1C2027" text-anchor="middle">{E(berlin_time)}</text>'
            )
    svg_parts.append("</g>")

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


def _select_html(select_id: str, name: str, options: Sequence[Mapping[str, str]], selected: str) -> str:
    items = []
    for opt in options:
        value = opt["value"]
        sel = " selected" if value == selected else ""
        label = opt["berlin"]
        utc = E(opt["utc"], quote=True)
        items.append(
            f'<option value="{E(value, quote=True)}" data-utc="{utc}"{sel}>{E(label)}</option>'
        )
    return (
        f'<select id="{E(select_id, quote=True)}" name="{E(name, quote=True)}" '
        f'aria-describedby="{E(select_id, quote=True)}-utc">{"".join(items)}</select>'
    )


def history_page() -> str:
    """Generates the full inner HTML for the history & task tracker page."""
    data = load_telemetry_data()
    window = data.get("window", {})
    hourly = data.get("hourly_history", [])
    token_sum = data.get("product_token_summary", {})
    payload = public_filter_payload(data)
    default_state = default_filter_state(data)
    kpis = compute_kpis(data, default_state)
    bounds = hour_bound_options(data)

    work_by = {}
    for pid in CANONICAL_IDS:
        total = 0.0
        for b in hourly:
            cell = (b.get("products") or {}).get(pid) or {}
            if _product_observed(cell):
                total += float(cell.get("sampled_working_hours") or 0.0)
        work_by[pid] = total
    completions = sum(int((token_sum.get(pid) or {}).get("assistant_messages") or 0) for pid in CANONICAL_IDS)

    token_note = (
        f"Audited across {completions} completions in Dashboard & Coordination"
        if kpis["tokens"]
        else "No attributed tokens in this export"
    )
    observed_note = "4 hours unobserved before collector launch; 20 fully sampled"
    work_note = (
        f"Across all teams; branches {work_by['agent-branches']:.2f}h, "
        f"dashboard {work_by['agent-dashboard']:.2f}h"
    )

    generated = parse_utc(str(data.get("generated_at_utc") or ""))
    win_start = parse_utc(str(window.get("start_utc") or ""))
    win_end = parse_utc(str(window.get("end_utc") or ""))
    generated_label = format_utc_short(generated) if generated else "unknown"
    source_stamp = (
        f"Export generated {generated_label}. Window "
        f"{format_berlin(win_start) if win_start else window.get('start_utc')} "
        f"to {format_berlin(win_end) if win_end else window.get('end_utc')} "
        f"({format_utc_short(win_start) if win_start else ''} to "
        f"{format_utc_short(win_end) if win_end else ''}). "
        "Filtering this page does not refresh the collector."
    )

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

    chip_buttons = []
    for p in CANONICAL_PRODUCTS:
        chip_buttons.append(
            f'<button type="button" class="history-chip" aria-pressed="true" '
            f'aria-label="{E(p["name"], quote=True)}" '
            f'data-product="{E(p["id"], quote=True)}">{E(p["chip"])}</button>'
        )

    from_utc = bounds["from"][0]["utc"] if bounds["from"] else ""
    to_utc = bounds["to"][-1]["utc"] if bounds["to"] else ""
    filter_bar = f"""
    <section class="history-filters" aria-label="History filters">
      <div class="history-chips" role="group" aria-label="Filter by product">
        {''.join(chip_buttons)}
      </div>
      <div class="history-range">
        <div class="history-bound">
          <label for="history-from">From (Berlin)</label>
          {_select_html("history-from", "from", bounds["from"], default_state.start_utc)}
          <span class="history-bound-utc" id="history-from-utc">{E(from_utc)}</span>
        </div>
        <div class="history-bound">
          <label for="history-to">To (Berlin)</label>
          {_select_html("history-to", "to", bounds["to"], default_state.end_utc)}
          <span class="history-bound-utc" id="history-to-utc">{E(to_utc)}</span>
        </div>
        <button type="button" class="history-reset" id="history-reset">Reset</button>
        <button type="button" class="history-reset" id="history-export-json">JSON</button>
        <button type="button" class="history-reset" id="history-export-csv">CSV</button>
        <button type="button" class="history-reset" id="history-export-md">Markdown</button>
      </div>
      <p class="history-source">{E(source_stamp)}</p>
      <noscript><p class="history-noscript">Product and hour filters need JavaScript. This page shows the full 24-hour export without them.</p></noscript>
    </section>
    """

    kpi_grid = f"""
    <div class="kpi-grid" id="history-kpis">
      {build_kpi_card(format_tokens(kpis["tokens"]), "Measured Tokens", token_note, highlight=True, kpi_id="kpi-tokens")}
      {build_kpi_card(format_observed(kpis["observed_hours"], kpis["in_range_count"]), "Observed Hours", observed_note, kpi_id="kpi-observed")}
      {build_kpi_card(format_work(kpis["sampled_work"]), "Sampled Working Time", work_note, kpi_id="kpi-work")}
      {build_kpi_card(f'{kpis["product_count"]} Teams', "Active Products", "Branches, Dashboard, Quota Launcher, Coordination", kpi_id="kpi-products")}
    </div>
    """

    chart_svg = render_hourly_chart_svg(hourly)
    chart_section = f"""
    <section class="telemetry-chart-section" id="history-chart-section">
      <div class="section-head">
        <h2>Hourly Activity &amp; Occupancy (Preceding 24h)</h2>
        <p>Times shown in Europe/Berlin (CEST) with UTC mapping in the ledger below</p>
      </div>
      <div class="chart-wrapper" id="history-chart-wrap">
        {chart_svg}
      </div>
    </section>
    """

    table_rows = []
    for b in hourly:
        b_idx = b.get("bucket_index", 0)
        berlin = b.get("berlin_label", "")
        start_utc = b.get("bucket_start_utc", "")
        end_utc = b.get("bucket_end_utc", "")
        utc_range = f"{str(start_utc)[-9:-1]}–{str(end_utc)[-9:-1]} UTC"
        prods = b.get("products", {})

        is_unobs = not any(
            p.get("observation_status") in ("observed", "partial")
            for k, p in prods.items()
            if k != "unattributed"
        )

        row_attrs = (
            f' class="history-row{" row-unobserved" if is_unobs else ""}" '
            f'data-start="{E(start_utc, quote=True)}" data-end="{E(end_utc, quote=True)}" '
            f'data-index="{b_idx}" data-unobserved="{1 if is_unobs else 0}"'
        )

        if is_unobs:
            row_html = f"""
            <tr{row_attrs}>
              <td class="col-time">{E(berlin)}<div class="sub-utc">{E(utc_range)}</div></td>
              <td colspan="5" class="cell-unobserved">
                <span class="badge-unobserved">UNOBSERVED</span> Telemetry collector was not running before 13:00 CEST
              </td>
            </tr>
            """
        else:
            def fmt_prod(pid: str, p: Dict[str, Any], token_val: int = 0) -> str:
                status = p.get("observation_status") or "unobserved"
                work = p.get("sampled_working_hours") or 0.0
                pres = p.get("presence_hours") or 0.0
                if status == "unobserved":
                    inner = '<span class="muted">unobserved</span>'
                else:
                    tok_str = f'<div class="cell-tok">+{token_val:,} tok</div>' if token_val > 0 else ""
                    inner = f"""
                    <div class="prod-cell">
                      <span class="cell-work">{work:.2f}h work</span>
                      <span class="cell-pres">{pres:.2f}h open</span>
                      {tok_str}
                    </div>
                    """
                return (
                    f'<td class="col-product" data-product="{E(pid, quote=True)}" '
                    f'data-status="{E(status, quote=True)}" data-work="{work:.4f}" '
                    f'data-presence="{pres:.4f}" data-tokens="{token_val}">{inner}</td>'
                )

            cells = []
            row_tokens = 0
            for pid in CANONICAL_IDS:
                tok = tokens_for_bucket(data, pid, b_idx)
                row_tokens += tok
                cells.append(fmt_prod(pid, prods.get(pid, {}), tok))
            tok_cell = "+" + f"{row_tokens:,}" if row_tokens > 0 else "—"
            time_label = berlin.split(" ")[1] if " " in berlin else berlin
            row_html = f"""
            <tr{row_attrs}>
              <td class="col-time"><strong>{E(time_label)}</strong><div class="sub-utc">{E(utc_range)}</div></td>
              {''.join(cells)}
              <td class="col-tok" data-tokens="{row_tokens}">{tok_cell}</td>
            </tr>
            """
        table_rows.append(row_html)

    product_headers = "".join(
        f'<th class="col-product" data-product="{E(p["id"], quote=True)}">{E(p["name"])}</th>'
        for p in CANONICAL_PRODUCTS
    )
    ledger_section = f"""
    <section class="telemetry-table-section" id="history-ledger-section">
      <div class="section-head">
        <h2>24-Hour Telemetry Ledger</h2>
        <p>Complete 24 half-open buckets: Berlin time (CEST) and UTC offsets</p>
      </div>
      <div class="table-responsive">
        <table class="telemetry-table" id="history-ledger">
          <thead>
            <tr>
              <th>Time Window</th>
              {product_headers}
              <th class="col-tok">Tokens</th>
            </tr>
          </thead>
          <tbody>
            {''.join(table_rows)}
          </tbody>
        </table>
      </div>
    </section>
    """

    empty_state = """
    <p class="history-empty" id="history-empty" hidden role="status" aria-live="polite"></p>
    """

    tracker_section = """
    <section class="task-tracker-section">
      <div class="section-head">
        <h2>Active Delivery &amp; Task Tracker</h2>
        <p>Current tasks, responsible project heads, accepted outcomes, and concrete next steps</p>
      </div>

      <div class="tracker-grid">
        <div class="tracker-card" data-product="agent-branches">
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

        <div class="tracker-card" data-product="agent-dashboard">
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

        <div class="tracker-card" data-product="quota-launcher">
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

        <div class="tracker-card" data-product="agent-coordination">
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
    <div class="narrow history-page" id="history-page">
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
      {filter_bar}
      {kpi_grid}
      {empty_state}
      <div id="history-results">
      {chart_section}
      {ledger_section}
      </div>
      {tracker_section}
      <script type="application/json" id="history-telemetry-data">{embed_json(payload)}</script>
      <script src="{BASE}/assets/history-filter.js" defer></script>
    </div>
    """


if __name__ == "__main__":
    content = history_page()
    print(f"Generated history page: {len(content)} characters.")

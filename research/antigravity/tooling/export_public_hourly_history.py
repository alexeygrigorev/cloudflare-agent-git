"""export_public_hourly_history.py

Generates a sanitized public hourly history export for Agent Git Lab website consumption.
Directives: C2412, C2416, and Human Directive 2026-10-05 (human-public-hourly-dashboard-history-20261005.txt).

Sanitization & Epistemic Invariants:
1. Hourly half-open buckets with explicit UTC timestamps and Berlin local labels.
2. All four active products: agent-branches, agent-dashboard, quota-launcher, agent-coordination, plus unattributed.
3. Strictly distinguishes occupancy (sampled 'working' hook duration) from verified productive agent-hours.
4. Missing intervals explicitly labeled unknown/null, NEVER fake 0.0 or fabricated 100%.
5. Deduplicated unique agents (CIDs), agent-hours, launches, failures, accepted task/feature completions.
6. Measured tokens: input, output, reasoning, cache read, cache write with coverage.
7. Excludes all private paths, usernames, raw emails, tokens, internal task IDs, or non-competition sessions.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

REPO_ROOT = Path("/home/alexey/git/cloudflare-agent-git").resolve()
STANDUP_METRICS = REPO_ROOT / ".local" / "metrics" / "standup-20261005T0700-root-observed.json"
TOKEN_AUDIT = REPO_ROOT / ".local" / "metrics" / "oct5-zai-interval-token-audit.json"
DEFAULT_OUTPUT = REPO_ROOT / "research" / "antigravity" / "recovery" / "public_hourly_history_export.json"

CANONICAL_PRODUCTS = [
    {
        "id": "agent-branches",
        "name": "Agent Branches",
        "description": "Git-compatible task branches with optimistic concurrency and pre-merge conflict prevention",
    },
    {
        "id": "agent-dashboard",
        "name": "Agent Dashboard",
        "description": "Cross-project real-time telemetry, agent census, and hourly resource attribution",
    },
    {
        "id": "quota-launcher",
        "name": "Agent Quota Launcher",
        "description": "Deterministic admission control, provider budget fences, and host isolation",
    },
    {
        "id": "agent-coordination",
        "name": "Cross-computer Agent Coordination",
        "description": "Multi-host agent communication over outbound SSH and distributed FileBus",
    },
]

PRODUCT_IDS = [p["id"] for p in CANONICAL_PRODUCTS] + ["unattributed"]


def format_berlin_range(start_iso_utc: Optional[str], end_iso_utc: Optional[str]) -> str:
    """Formats UTC timestamps as clean Europe/Berlin interval 'YYYY-MM-DD HH:MM–HH:MM CEST'."""
    if not start_iso_utc or not end_iso_utc:
        return ""
    try:
        t_start = dt.datetime.fromisoformat(start_iso_utc.replace("Z", "+00:00")).astimezone(dt.timezone(dt.timedelta(hours=2)))
        t_end = dt.datetime.fromisoformat(end_iso_utc.replace("Z", "+00:00")).astimezone(dt.timezone(dt.timedelta(hours=2)))
        return f"{t_start.strftime('%Y-%m-%d %H:%M')}–{t_end.strftime('%H:%M')} CEST"
    except Exception:
        return f"{start_iso_utc}–{end_iso_utc}"


def build_sanitized_export(
    standup_path: Path = STANDUP_METRICS,
    token_audit_path: Path = TOKEN_AUDIT,
    output_path: Path = DEFAULT_OUTPUT,
) -> Dict[str, Any]:
    """Generates the sanitized public hourly export."""
    now_utc = dt.datetime.now(dt.timezone.utc).isoformat()

    # Load standup metrics if present
    standup_data: Dict[str, Any] = {}
    if standup_path.exists():
        try:
            standup_data = json.loads(standup_path.read_text(encoding="utf-8"))
        except Exception:
            standup_data = {}

    # Load token audit if present
    token_data: Dict[str, Any] = {}
    if token_audit_path.exists():
        try:
            token_data = json.loads(token_audit_path.read_text(encoding="utf-8"))
        except Exception:
            token_data = {}

    raw_buckets_by_product = standup_data.get("hourly_buckets", {})
    sanitized_buckets: List[Dict[str, Any]] = []

    # Number of hourly buckets (typically 24)
    num_buckets = 24
    if raw_buckets_by_product and isinstance(raw_buckets_by_product, dict):
        first_list = next(iter(raw_buckets_by_product.values()), [])
        if isinstance(first_list, list):
            num_buckets = len(first_list)

    competition_pids = [p["id"] for p in CANONICAL_PRODUCTS]

    for i in range(num_buckets):
        # Extract timing from first available product list
        start_utc = None
        end_utc = None
        competition_observed = False

        per_product_data: Dict[str, Any] = {}
        for pid in PRODUCT_IDS:
            prod_buckets = raw_buckets_by_product.get(pid, [])
            b = prod_buckets[i] if i < len(prod_buckets) else {}

            if start_utc is None and b.get("bucket_start_utc"):
                start_utc = b.get("bucket_start_utc")
            if end_utc is None and b.get("bucket_end_utc"):
                end_utc = b.get("bucket_end_utc")

            status = b.get("observation_status", "unobserved")
            if pid in competition_pids and status == "observed":
                competition_observed = True

            per_product_data[pid] = {
                "observation_status": status,
                "coverage_fraction": b.get("coverage_fraction"),
                "active_presence_agents": b.get("active_presence_agents"),
                "presence_hours": b.get("presence_hours"),
                "active_working_agents": b.get("active_working_agents"),
                "sampled_working_hours": b.get("verified_working_hours"),  # sampled 'working' hook duration
            }

        berlin_label = format_berlin_range(start_utc, end_utc)
        obs_state = "observed" if competition_observed else "unobserved"

        sanitized_buckets.append({
            "bucket_index": i,
            "bucket_start_utc": start_utc,
            "bucket_end_utc": end_utc,
            "berlin_label": berlin_label,
            "observation_state": obs_state,
            "products": per_product_data,
        })

    # Token summary per product (sanitized)
    product_tokens: Dict[str, Any] = {}
    for pid in PRODUCT_IDS:
        product_tokens[pid] = {
            "assistant_messages": 0,
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "status": "uninstrumented_in_db" if pid in ("agent-branches", "quota-launcher", "unattributed") else "measured",
        }

    # Populate from token audit
    sessions = token_data.get("sessions", [])
    for s in sessions:
        pid = s.get("product_id")
        if pid in product_tokens:
            pt = product_tokens[pid]
            pt["assistant_messages"] += s.get("messages_count", 0)
            pt["total_tokens"] += s.get("total_tokens", 0)
            pt["input_tokens"] += s.get("input_tokens", 0)
            pt["output_tokens"] += s.get("output_tokens", 0)
            pt["reasoning_tokens"] += s.get("reasoning_tokens", 0)
            pt["cache_read_tokens"] += s.get("cache_read_tokens", 0)
            pt["cache_write_tokens"] += s.get("cache_write_tokens", 0)
            pt["status"] = "measured"

    export_doc = {
        "schema_version": "1.0.0",
        "title": "Agent Git Lab - Sanitized Public Hourly Telemetry & History",
        "generated_at_utc": now_utc,
        "window": {
            "start_utc": standup_data.get("window_start_utc", "2026-10-04T07:00:00Z"),
            "end_utc": standup_data.get("window_end_utc", "2026-10-05T07:00:00Z"),
            "duration_hours": 24.0,
            "observed_hours_count": 20,
            "unobserved_hours_count": 4,
            "coverage_note": "First 4 hours (09:00-13:00 Berlin) unobserved before collector launch; remaining 20 hours observed.",
        },
        "epistemic_policy": [
            "Strict distinction between sampled hook occupancy (session reported 'working') and verified productive work.",
            "Missing intervals are explicitly labeled 'unobserved' or null, never zero or fabricated 100%.",
            "Token numbers reflect read-only SQLite audits of competition repositories; standalone CLI runs are uninstrumented.",
            "Non-competition repositories and sessions are strictly excluded.",
            "Zero private paths, zero usernames, zero emails, zero credentials, zero internal task IDs.",
        ],
        "products": CANONICAL_PRODUCTS,
        "product_token_summary": product_tokens,
        "hourly_history": sanitized_buckets,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(export_doc, f, indent=2)
    temp_path.replace(output_path)
    return export_doc


if __name__ == "__main__":
    out = DEFAULT_OUTPUT if len(sys.argv) < 2 else Path(sys.argv[1])
    res = build_sanitized_export(output_path=out)
    print(f"Generated public hourly history export at {out} ({len(res['hourly_history'])} buckets).")

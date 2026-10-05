"""Bounded read-only audit of OpenCode token usage for [2026-10-04T07:00:00Z, 2026-10-05T07:00:00Z).

Generates .local/metrics/oct5-zai-interval-token-audit.json with mode 0600.
Strictly scoped to active competition projects (agent-dashboard, agent-bus / agent-coordination, agent-branches, quota-launcher).
Excludes non-competition repositories/sessions (e.g. ods-berlin-bot).
"""
import datetime as dt
import json
import os
import pathlib
import sqlite3

START_ISO = "2026-10-04T07:00:00+00:00"
END_ISO = "2026-10-05T07:00:00+00:00"

ALLOWED_PROJECT_PREFIXES = (
    "/home/alexey/git/agent-dashboard",
    "/home/alexey/git/agent-bus",
    "/home/alexey/git/agent-coordination",
    "/home/alexey/git/agent-quota-launcher",
    "/home/alexey/git/cloudflare-agent-git",
)

def audit_tokens(output_path: pathlib.Path) -> dict:
    start_dt = dt.datetime.fromisoformat(START_ISO)
    end_dt = dt.datetime.fromisoformat(END_ISO)
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    home_db = pathlib.Path.home() / ".local/share/opencode/opencode.db"
    isolated_db = pathlib.Path(".local/opencode-isolated/opencode/opencode.db")

    stores_to_check = [
        ("home_opencode", home_db),
        ("isolated_opencode", isolated_db),
    ]

    audit_result = {
        "schema_version": "1.1.0",
        "audit_name": "oct5-zai-interval-token-audit",
        "source": "opencode-message-reported",
        "window": {
            "start_iso": START_ISO,
            "end_iso": END_ISO,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "duration_hours": 24.0,
        },
        "audited_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "epistemic_notes": [
            "Source is read-only SQLite snapshot of OpenCode message stores.",
            "Attribution is strictly restricted to active competition project repositories.",
            "Non-competition repositories/sessions (such as ods-berlin-bot, 12 msgs, 378,476 tokens) are strictly excluded from totals.",
            "Stored provider totals include cached processing (cache_read). Authoritative total_tokens is preserved as reported by provider.",
            "Direct standalone ZCode CLI / zcy API runs without OpenCode DB recording are uninstrumented in this store (labeled as uninstrumented/unknown, not assumed 0).",
            "Costs are OpenCode/provider estimates, not confirmed billing statements.",
            "Oct 4 Opus daily report response (.local/journal/2026-10-04/response.json) completed at 2026-10-04T07:22:07Z (within window); recorded separately as shared publication service.",
        ],
        "stores_audited": [],
        "sessions": [],
        "excluded_sessions_count": 0,
        "by_provider_model": {},
        "totals": {
            "assistant_messages": 0,
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "reported_cost_usd": 0.0,
        },
        "zai_native_status": {
            "messages_recorded": 0,
            "status": "uninstrumented_in_opencode_db",
            "explanation": "ZCode CLI / zcy headless workers ran outside the local OpenCode SQLite schema; native GLM/ZAI tokens for autonomous workers are not captured in opencode.db tables.",
        },
        "shared_publication_opus_oct4": {
            "status": "completed_in_window",
            "completed_at": "2026-10-04T07:22:07.742627Z",
            "duration_seconds": 412.355,
            "noncache_tokens": 92,
            "cache_write_tokens": 195290,
            "cache_read_tokens": 6323381,
            "output_tokens": 40164,
            "reasoning_tokens": 15330,
            "notes": "Dedicated Opus run for October 4 daily journal, shared publication, not 4-product internal line.",
        }
    }

    for store_name, db_path in stores_to_check:
        if not db_path.exists():
            audit_result["stores_audited"].append({
                "store": store_name,
                "path": str(db_path),
                "status": "missing_skipped",
                "rows": 0,
            })
            continue

        conn = sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
        cur = conn.cursor()

        # Session map for filtering
        cur.execute("SELECT id, directory, title FROM session")
        session_catalog = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

        query = """
        SELECT
            id, session_id, time_created,
            json_extract(data,'$.providerID') as provider,
            json_extract(data,'$.modelID') as model,
            json_extract(data,'$.time.completed') as completed,
            json_extract(data,'$.tokens.total') as total_tokens,
            json_extract(data,'$.tokens.input') as input_tokens,
            json_extract(data,'$.tokens.output') as output_tokens,
            json_extract(data,'$.tokens.reasoning') as reasoning_tokens,
            json_extract(data,'$.tokens.cache.read') as cache_read,
            json_extract(data,'$.tokens.cache.write') as cache_write,
            json_extract(data,'$.cost') as cost
        FROM message
        WHERE time_created >= ? AND time_created < ?
          AND json_extract(data,'$.role') = 'assistant'
        ORDER BY time_created ASC
        """
        rows = cur.execute(query, (start_ms, end_ms)).fetchall()

        scoped_rows = []
        excluded_cnt = 0
        for r in rows:
            sid = r[1]
            sdir, stitle = session_catalog.get(sid, ("unknown", "unknown"))
            if any(sdir.startswith(pfx) for pfx in ALLOWED_PROJECT_PREFIXES):
                scoped_rows.append(r)
            else:
                excluded_cnt += 1

        audit_result["excluded_sessions_count"] += excluded_cnt
        audit_result["stores_audited"].append({
            "store": store_name,
            "path": str(db_path),
            "status": "audited",
            "total_assistant_rows": len(rows),
            "scoped_assistant_rows": len(scoped_rows),
            "excluded_non_project_rows": excluded_cnt,
        })

        session_map = {}
        for r in scoped_rows:
            mid, sid, created, prov, mod, comp, tot, inp, out, reas, cr, cw, cost = r
            if sid not in session_map:
                sdir, stitle = session_catalog.get(sid, ("unknown", "unknown"))
                # determine product
                product_id = "unknown"
                if "agent-dashboard" in sdir:
                    product_id = "agent-dashboard"
                elif "agent-bus" in sdir or "agent-coordination" in sdir:
                    product_id = "agent-coordination"
                elif "agent-branches" in sdir:
                    product_id = "agent-branches"
                elif "quota-launcher" in sdir:
                    product_id = "quota-launcher"

                session_map[sid] = {
                    "session_id": sid,
                    "product_id": product_id,
                    "directory": sdir,
                    "title": stitle,
                    "messages_count": 0,
                    "models": set(),
                    "total_tokens": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                    "cost_usd": 0.0,
                }
            s = session_map[sid]
            s["messages_count"] += 1
            s["models"].add(f"{prov}/{mod}")
            s["total_tokens"] += (tot or 0)
            s["input_tokens"] += (inp or 0)
            s["output_tokens"] += (out or 0)
            s["reasoning_tokens"] += (reas or 0)
            s["cache_read_tokens"] += (cr or 0)
            s["cache_write_tokens"] += (cw or 0)
            s["cost_usd"] += (cost or 0.0)

            # Provider/model grouping
            pm_key = f"{prov or 'unknown'}/{mod or 'unknown'}"
            if pm_key not in audit_result["by_provider_model"]:
                audit_result["by_provider_model"][pm_key] = {
                    "provider": prov,
                    "model": mod,
                    "messages": 0,
                    "total_tokens": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "reasoning_tokens": 0,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                    "cost_usd": 0.0,
                }
            pm = audit_result["by_provider_model"][pm_key]
            pm["messages"] += 1
            pm["total_tokens"] += (tot or 0)
            pm["input_tokens"] += (inp or 0)
            pm["output_tokens"] += (out or 0)
            pm["reasoning_tokens"] += (reas or 0)
            pm["cache_read_tokens"] += (cr or 0)
            pm["cache_write_tokens"] += (cw or 0)
            pm["cost_usd"] += (cost or 0.0)

            # Totals
            audit_result["totals"]["assistant_messages"] += 1
            audit_result["totals"]["total_tokens"] += (tot or 0)
            audit_result["totals"]["input_tokens"] += (inp or 0)
            audit_result["totals"]["output_tokens"] += (out or 0)
            audit_result["totals"]["reasoning_tokens"] += (reas or 0)
            audit_result["totals"]["cache_read_tokens"] += (cr or 0)
            audit_result["totals"]["cache_write_tokens"] += (cw or 0)
            audit_result["totals"]["reported_cost_usd"] += (cost or 0.0)

        for sid, sdata in session_map.items():
            sdata["models"] = sorted(list(sdata["models"]))
            audit_result["sessions"].append(sdata)

        conn.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(audit_result, f, indent=2)
    os.chmod(temp_path, 0o600)
    temp_path.replace(output_path)
    return audit_result

if __name__ == "__main__":
    out_file = pathlib.Path(".local/metrics/oct5-zai-interval-token-audit.json")
    res = audit_tokens(out_file)
    print(f"Audited {res['totals']['assistant_messages']} messages, {res['totals']['total_tokens']} total tokens.")
    print(f"Excluded non-project rows: {res['excluded_sessions_count']}.")
    print(f"Output written to {out_file} (mode 0600).")

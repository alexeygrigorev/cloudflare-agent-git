#!/usr/bin/env python3
"""Principal metrics entrypoint (run it through scripts/principal-metrics.sh).

Calls the working collectors, never duplicates them:
  - scripts/metrics/collect.py   one-shot fleet observation -> .local/metrics/latest.json
  - gh                           issues and commits per repo
  - _docs/founder-journal/       founder messages today (the "## " headings)
  - shutil                       free disk

A number that cannot be measured is None and prints "unknown: <reason>", never
zero and never an estimate. Targets are the ones in _docs/06-metrics.md.

Exit 0 all on target, 1 something off target, 2 critical data unreadable.
A snapshot goes to .local/metrics/ (git-ignored); the previous one is compared.
"""
import argparse
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import zoneinfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERLIN = zoneinfo.ZoneInfo("Europe/Berlin")
OWNER = "alexeygrigorev"
REPOS = ("cloudflare-agent-git", "agent-branches", "agent-quota-launcher",
         "agent-coordination", "agent-dashboard", "agent-hub")
# Verified owner for the legacy bus repo. The default OWNER above is wrong for
# agent-bus (it 404s under alexeygrigorev); explicit "agent-bus" still resolves,
# but only to this verified fully-qualified path, never a silent zero.
AGENT_BUS_CANONICAL = "PocketShell-io/agent-bus"
HEAD_RE = re.compile(r"(^|-)(head|principal)(-|$)")
IDLE_LIMIT_S = 300
TARGETS = {"active_agents": 50, "ready_reserve": 50, "free_disk_gib": 20,
           "resolved_today": 200, "created_today": 250, "commits_24h": 2000}
KEEP_SNAPSHOTS = 200


def run(cmd, timeout=120):
    """Return (stdout, error). Error is a short reason, never a secret."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=ROOT)
    except Exception as e:  # noqa: BLE001
        return None, f"{cmd[0]} failed: {type(e).__name__}"
    if r.returncode != 0:
        first = (r.stderr.strip().splitlines() or ["exit %d" % r.returncode])[0]
        return None, f"{cmd[0]} failed: {first[:120]}"
    return r.stdout, None


def unk(reason):
    return {"value": None, "unknown": reason}


def val(v, **extra):
    d = {"value": v}
    d.update(extra)
    return d


def canonical_repo_path(repo):
    """Resolve a --repos entry to a fully-qualified "owner/name" path.

    Bare names resolve under OWNER, except the legacy "agent-bus" which
    resolves to the verified AGENT_BUS_CANONICAL owner. Entries already
    containing "/" pass through only when exactly "owner/name". Anything
    else returns None so callers report UNKNOWN, never a silent zero.
    """
    repo = (repo or "").strip()
    if not repo:
        return None
    if "/" in repo:
        owner, _, name = repo.partition("/")
        if owner and name and "/" not in name:
            return f"{owner}/{name}"
        return None
    if repo == "agent-bus":
        return AGENT_BUS_CANONICAL
    return f"{OWNER}/{repo}"


def parse_utc(ts):
    """Parse an ISO-8601 timestamp to aware UTC, or None when invalid.

    Lenient convenience for caller-supplied window bounds (since/now):
    naive values are assumed UTC. Committer rows MUST NOT use this;
    they use parse_strict_utc() below.
    """
    try:
        if not isinstance(ts, str) or not ts:
            return None
        dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


_STRICT_TZ_RE = re.compile(r"[+-]\d{2}:?\d{2}(:\d{2}(\.\d+)?)?$|[+-]\d{4}$")


def parse_strict_utc(ts):
    """Parse a committer timestamp strictly, or None when not fully qualified.

    Requires a full datetime with an explicit timezone: the string must
    contain a 'T' time separator and end with 'Z' (or 'z') or a numeric
    UTC offset. Naive values ('2026-10-14T11:00:00') and date-only values
    ('2026-10-14') return None so callers report UNKNOWN instead of
    silently assuming UTC.
    """
    if not isinstance(ts, str) or not ts:
        return None
    s = ts.strip()
    if "T" not in s and "t" not in s:
        return None
    if not (s.endswith("Z") or s.endswith("z") or _STRICT_TZ_RE.search(s)):
        return None
    try:
        dt = datetime.datetime.fromisoformat(s.replace("Z", "+00:00").replace("z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(datetime.timezone.utc)


def collect_fleet(local_dir):
    out, err = run([sys.executable, os.path.join(ROOT, "scripts/metrics/collect.py")])
    if err:
        return None, err
    try:
        with open(os.path.join(local_dir, "latest.json")) as f:
            return json.load(f), None
    except Exception as e:  # noqa: BLE001
        return None, f"latest.json unreadable: {type(e).__name__}"


def fleet_metrics(snap, err):
    m = {}
    if snap is None:
        why = f"collector unavailable ({err})"
        for k in ("idle_per_head", "active_agents", "ready_reserve"):
            m[k] = unk(why)
        return m
    heads = {}
    for s in snap.get("sessions", []):
        tag = s.get("tag") or ""
        if s.get("pid_live") and (HEAD_RE.search(tag) or s.get("role") in ("head", "principal")):
            heads[tag] = {"reported_state": s.get("reported_state"),
                          "idle_seconds": s.get("observed_idle_seconds")}
    if heads:
        m["idle_per_head"] = val(heads, note="longest sampled idle per live head/principal; daily total needs history, unknown")
    else:
        m["idle_per_head"] = unk("no live head or principal session in the collector snapshot")
    agg = snap.get("aggregate", {})
    live, hook = agg.get("agents_pid_live"), agg.get("fresh_hook_working")
    m["active_agents"] = unk(
        "no verified first-tool or progress evidence per worker; collector says PID live and hook "
        f"working are observations only (observed pid_live={live}, fresh_hook_working={hook})")
    ready = (agg.get("tasks_by_status") or {}).get("ready")
    if ready is None:
        m["ready_reserve"] = unk("collector has no ready task count")
    else:
        m["ready_reserve"] = val(ready, note="owner-maintained task registry status 'ready', not independently verified")
    return m


def founder_messages_today(now):
    path = os.path.join(ROOT, "_docs/founder-journal", now.strftime("%Y-%m-%d") + ".md")
    try:
        with open(path) as f:
            n = sum(1 for line in f if line.startswith("## "))
    except FileNotFoundError:
        return val(0, note="no journal file for today: no founder message recorded")
    except Exception as e:  # noqa: BLE001
        return unk(f"journal unreadable: {type(e).__name__}")
    return val(n, note="'## ' headings in today's journal day file, Berlin day")


def gh_json(args):
    out, err = run(["gh"] + args)
    if err:
        return None, err
    try:
        return json.loads(out), None
    except ValueError:
        return None, "gh returned invalid JSON"


def issue_counts(repo, day):
    full = canonical_repo_path(repo)
    if not full:
        return unk(f"unresolvable repo '{repo}': refusing silent zero")
    data, err = gh_json(["issue", "list", "-R", full, "--state", "all", "--limit", "1000",
                         "--json", "state,createdAt,closedAt"])
    if err:
        return unk(err)

    def on_day(ts):
        if not ts:
            return False
        t = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(BERLIN)
        return t.date().isoformat() == day

    return val({"open": sum(1 for i in data if i["state"] == "OPEN"),
                "created_today": sum(1 for i in data if on_day(i.get("createdAt"))),
                "closed_today": sum(1 for i in data if on_day(i.get("closedAt")))},
               note="issues, Berlin calendar day; closed is not acceptance")


def commits_24h(repo, since_iso, now=None):
    """Count unique main-branch commit SHAs by strict committer-UTC window.

    Canonical query always pins sha=main. The local cutoff keeps only rows
    whose commit.committer.date falls in the genuine preceding-24h interval
    (since, now] in UTC: committer <= since and committer > now are filtered
    as old/future. Author dates never substitute. Any shape error, missing
    sha, missing/invalid committer timestamp, or API error is UNKNOWN; a
    valid empty window is 0. Pagination (--paginate --slurp: list of pages)
    is consumed page by page and SHAs are deduped.

    Strictness notes (F1/F2/F4):
    - Committer rows require a full datetime with an explicit Z/offset
      (parse_strict_utc); naive and date-only rows are UNKNOWN, never
      assumed UTC. The lenient parse_utc() is used only for the
      caller-supplied since/now bounds.
    - Row sha must be a nonempty string; non-string (int/bool/None/
      list/dict), missing, or empty sha is UNKNOWN and never counted or
      added to the dedup set (so unhashable values cannot crash). A
      strict 40-hex sha is deliberately NOT required: existing fixtures
      use short names and real-API truth prefers leniency on sha shape
      while staying strict on time shape.
    - Zero pages: both [] (no pages under --slurp) and [[]] (one empty
      page) are treated as a valid empty window 0; any non-list shape
      or non-list page is UNKNOWN.
    """
    full = canonical_repo_path(repo)
    if not full:
        return unk(f"unresolvable repo '{repo}': refusing silent zero")
    since_dt = parse_utc(since_iso)
    if since_dt is None:
        return unk(f"invalid since timestamp {since_iso!r}")
    now_dt = now if now is not None else datetime.datetime.now(datetime.timezone.utc)
    if now_dt.tzinfo is None:
        now_dt = now_dt.replace(tzinfo=datetime.timezone.utc)
    now_dt = now_dt.astimezone(datetime.timezone.utc)
    data, err = gh_json(["api", "--paginate", "--slurp",
                         f"repos/{full}/commits?sha=main&since={since_iso}&per_page=100"])
    if err:
        return unk(err)
    if not isinstance(data, list):
        return unk("gh commits returned unexpected shape")
    seen = set()
    for page in data:
        if not isinstance(page, list):
            return unk("gh commits returned unexpected page shape")
        for c in page:
            if not isinstance(c, dict):
                return unk("gh commits returned row without sha")
            sha = c.get("sha")
            if not isinstance(sha, str) or not sha:
                return unk("gh commits returned row without sha")
            commit = c.get("commit")
            if not isinstance(commit, dict):
                return unk("gh commits returned row without commit timestamps")
            committer = commit.get("committer")
            ts = committer.get("date") if isinstance(committer, dict) else None
            if not ts:
                return unk("gh commits row missing committer date")
            dt = parse_strict_utc(ts)
            if dt is None:
                return unk(f"gh commits row has invalid committer date {ts!r}")
            if dt <= since_dt or dt > now_dt:
                continue
            seen.add(sha)
    return val(len(seen), note="unique SHAs on main by committer time, strict (since, now] UTC, merges included")


def sum_known(per_repo, key):
    vals = [r["value"][key] if key else r["value"] for r in per_repo.values() if r.get("value") is not None]
    return sum(vals) if vals else None


def build(now, local_dir, repos):
    day = now.astimezone(BERLIN).strftime("%Y-%m-%d")
    since = (now - datetime.timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    snap, err = collect_fleet(local_dir)
    m = fleet_metrics(snap, err)
    m["founder_messages_today"] = founder_messages_today(now.astimezone(BERLIN))
    free = shutil.disk_usage("/").free / 1024 ** 3
    m["free_disk_gib"] = val(round(free, 1))
    m["tasks"] = {r: issue_counts(r, day) for r in repos}
    m["commits_24h"] = {r: commits_24h(r, since, now) for r in repos}
    m["unmeasured"] = {k: unk("no reader yet; see _docs/06-metrics.md") for k in
                       ("founder_reminders_and_rescues", "cloud_cost", "memory_per_worker",
                        "resolved_tasks_accepted", "features_done", "tokens_used")}
    return m


def evaluate(m):
    off, critical = [], []
    if m["idle_per_head"].get("value") is None and "collector unavailable" in m["idle_per_head"]["unknown"]:
        critical.append("collector snapshot")
    ready = m["ready_reserve"].get("value")
    for tag, h in (m["idle_per_head"].get("value") or {}).items():
        idle = h.get("idle_seconds") or 0
        if h.get("reported_state") in ("idle", "waiting") and idle >= IDLE_LIMIT_S and (ready or 0) > 0:
            off.append(f"{tag} idle {idle / 60:.0f} min with ready work")
    if ready is not None and ready < TARGETS["ready_reserve"]:
        off.append(f"ready reserve {ready} < {TARGETS['ready_reserve']}")
    if m["free_disk_gib"]["value"] < TARGETS["free_disk_gib"]:
        off.append("free disk")
    for key, label, target in (("created_today", "tasks created today", "created_today"),
                               ("closed_today", "issues closed today", "resolved_today")):
        total = sum_known(m["tasks"], key)
        if total is None:
            critical.append(label)
        elif total < TARGETS[target]:
            off.append(f"{label} {total} < {TARGETS[target]}")
    c = sum_known(m["commits_24h"], None)
    if c is None:
        critical.append("commits 24h")
    elif c < TARGETS["commits_24h"]:
        off.append(f"commits 24h {c} < {TARGETS['commits_24h']}")
    return off, critical


def previous_snapshot(local_dir):
    files = sorted(glob.glob(os.path.join(local_dir, "principal-metrics-2*.json")))
    if not files:
        return None
    try:
        with open(files[-1]) as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return None


def write_snapshot(local_dir, doc):
    os.makedirs(local_dir, mode=0o700, exist_ok=True)
    name = "principal-metrics-" + doc["at"].replace(":", "").replace("-", "")[:15] + "Z.json"
    path = os.path.join(local_dir, name)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(doc, f, indent=1, sort_keys=True)
    for old in sorted(glob.glob(os.path.join(local_dir, "principal-metrics-2*.json")))[:-KEEP_SNAPSHOTS]:
        os.remove(old)
    return path


def numbers(m):
    """Flat comparable numbers, only measured ones."""
    n = {}
    for key in ("ready_reserve", "free_disk_gib", "founder_messages_today"):
        if m[key].get("value") is not None:
            n[key] = m[key]["value"]
    for group, field in (("tasks", None), ("commits_24h", None)):
        for repo, r in m[group].items():
            v = r.get("value")
            if v is None:
                continue
            if isinstance(v, dict):
                for k, x in v.items():
                    n[f"{group}.{repo}.{k}"] = x
            else:
                n[f"{group}.{repo}"] = v
    return n


def wake_coverage_line():
    """Read-only call of scripts/ping/wake-audit.py; its own line, or unknown with the reason."""
    out, err = run([sys.executable, os.path.join(ROOT, "scripts/ping/wake-audit.py"), "--read-only"])
    if err:  # exit 3 (wake unavailable) also lands here; the audit prints the reason itself
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts/ping/wake-audit.py"), "--read-only"],
                           capture_output=True, text=True, cwd=ROOT)
        return (r.stdout.strip().splitlines() or [f"wake coverage: unknown: {err}"])[0]
    return out.strip().splitlines()[0]


def render(doc, prev):
    m, lines = doc["metrics"], []
    old = numbers(prev["metrics"]) if prev else {}
    new = numbers(m)

    def d(key):
        if key in old and key in new and old[key] != new[key]:
            diff = new[key] - old[key]
            return f" ({'+' if diff > 0 else ''}{diff:g} since {prev['at'][11:16]}Z)"
        return ""

    def show(label, entry, key, target=""):
        v = entry.get("value")
        if v is None:
            lines.append(f"  {label}: unknown: {entry['unknown']}")
        else:
            lines.append(f"  {label}: {v}{d(key)}{target}" + (f"  [{entry['note']}]" if entry.get("note") else ""))

    lines.append(f"Principal metrics at {doc['at']} (previous: {prev['at'] if prev else 'none'})")
    lines.append("Agents:")
    idle = m["idle_per_head"]
    if idle.get("value") is None:
        lines.append(f"  idle time per head: unknown: {idle['unknown']}")
    else:
        lines.append("  idle time per head (longest sampled idle; target 0 with ready work):")
        for tag, h in sorted(idle["value"].items()):
            s = h.get("idle_seconds")
            lines.append(f"    {tag}: {h.get('reported_state') or 'state unknown'}, "
                         f"{'idle %.0f min' % (s / 60) if s else 'no idle stretch observed'}")
    show("active agents", m["active_agents"], "active_agents", " (target 50)")
    show("ready reserve", m["ready_reserve"], "ready_reserve", " (target: enough to keep 50 busy)")
    lines.append("  " + wake_coverage_line())
    lines.append("Founder:")
    show("founder messages today", m["founder_messages_today"], "founder_messages_today")
    lines.append("Tasks per repo (open / created today / closed today):")
    for repo, r in m["tasks"].items():
        v = r.get("value")
        if v is None:
            lines.append(f"  {repo}: unknown: {r['unknown']}")
        else:
            lines.append(f"  {repo}: {v['open']} / {v['created_today']} / {v['closed_today']}"
                         f"{d(f'tasks.{repo}.open')}")
    lines.append("Commits last 24h (target 2000 total):")
    for repo, r in m["commits_24h"].items():
        v = r.get("value")
        lines.append(f"  {repo}: " + (f"{v}{d(f'commits_24h.{repo}')}" if v is not None else f"unknown: {r['unknown']}"))
    lines.append("Host:")
    show("free disk GiB", m["free_disk_gib"], "free_disk_gib", " (target at least 20)")
    lines.append("Unknown (no reader yet): " + ", ".join(m["unmeasured"]))
    lines.append("Off target: " + ("; ".join(doc["off_target"]) if doc["off_target"] else "nothing"))
    if doc["critical_unknown"]:
        lines.append("Critical unknown: " + ", ".join(doc["critical_unknown"]))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true", help="print the snapshot as JSON")
    ap.add_argument("--repos", default=os.environ.get("PRINCIPAL_METRICS_REPOS", ",".join(REPOS)))
    ap.add_argument("--local-dir", default=os.path.join(ROOT, ".local/metrics"))
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args(argv)
    now = datetime.datetime.now(datetime.timezone.utc)
    repos = [r for r in a.repos.split(",") if r]
    metrics = build(now, a.local_dir, repos)
    off, critical = evaluate(metrics)
    doc = {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "metrics": metrics,
           "off_target": off, "critical_unknown": critical}
    prev = previous_snapshot(a.local_dir)
    if not a.no_write:
        write_snapshot(a.local_dir, doc)
    print(json.dumps(doc, indent=1, sort_keys=True) if a.json else render(doc, prev))
    return 2 if critical else (1 if off else 0)


if __name__ == "__main__":
    sys.exit(main())

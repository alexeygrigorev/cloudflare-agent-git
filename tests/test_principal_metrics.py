import importlib.util
import json
import pathlib

path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "principal_metrics.py"
spec = importlib.util.spec_from_file_location("principal_metrics", path)
pm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pm)

SNAP = {"aggregate": {"agents_pid_live": 2, "fresh_hook_working": 1, "tasks_by_status": {"ready": 3}},
        "sessions": [{"tag": "bus-head", "role": "head", "pid_live": True,
                      "reported_state": "idle", "observed_idle_seconds": 900},
                     {"tag": "worker-1", "role": "executor", "pid_live": True}]}

EXPECTED_DEFAULTS = ("cloudflare-agent-git", "agent-branches", "agent-quota-launcher",
                     "agent-coordination", "agent-dashboard", "agent-hub")

NOW = pm.datetime.datetime(2026, 10, 14, 12, 0, 0, tzinfo=pm.datetime.timezone.utc)
SINCE = NOW - pm.datetime.timedelta(hours=24)
SINCE_ISO = SINCE.strftime("%Y-%m-%dT%H:%M:%SZ")


def stub(monkeypatch, snap=SNAP, err=None, issues=None, commits=None):
    monkeypatch.setattr(pm, "collect_fleet", lambda d: (snap, err))
    monkeypatch.setattr(pm, "issue_counts", lambda r, day, *a: issues or pm.val(
        {"open": 5, "created_today": 300, "closed_today": 250}))
    monkeypatch.setattr(pm, "commits_24h", lambda r, s, *a: commits or pm.val(2500))


def row(sha, committer, author=None):
    return {"sha": sha, "commit": {"committer": {"date": committer},
                                   "author": {"date": author or committer}}}


def fake_gh(monkeypatch, data=None, err=None, capture=None):
    def fake(args):
        if capture is not None:
            capture.append(list(args))
        if err:
            return None, err
        return data, None
    monkeypatch.setattr(pm, "gh_json", fake)


def test_unknowns_are_never_zero(monkeypatch, tmp_path):
    stub(monkeypatch)
    m = pm.build(pm.datetime.datetime.now(pm.datetime.timezone.utc), str(tmp_path), ["a"])
    assert m["active_agents"]["value"] is None and m["active_agents"]["unknown"]
    assert all(v["value"] is None for v in m["unmeasured"].values())
    assert list(m["idle_per_head"]["value"]) == ["bus-head"]


def test_off_target_exit_1_and_snapshot_compare(monkeypatch, tmp_path, capsys):
    stub(monkeypatch)
    args = ["--repos", "a", "--local-dir", str(tmp_path)]
    assert pm.main(args) == 1  # idle head with ready work, ready 3 < 50
    stub(monkeypatch, issues=pm.val({"open": 7, "created_today": 300, "closed_today": 250}))
    pm.main(args)
    out = capsys.readouterr().out
    assert "a: 7 / 300 / 250 (+2 since" in out
    assert len(list(tmp_path.glob("principal-metrics-2*.json"))) >= 1


def test_collector_down_is_critical_exit_2(monkeypatch, tmp_path):
    stub(monkeypatch, snap=None, err="boom")
    assert pm.main(["--repos", "a", "--local-dir", str(tmp_path), "--no-write"]) == 2


def test_gh_failure_is_unknown_not_zero(monkeypatch, tmp_path, capsys):
    stub(monkeypatch, issues=pm.unk("gh failed"), commits=pm.unk("gh failed"))
    rc = pm.main(["--repos", "a", "--local-dir", str(tmp_path), "--json", "--no-write"])
    doc = json.loads(capsys.readouterr().out)
    assert rc == 2 and doc["metrics"]["tasks"]["a"]["value"] is None


def test_founder_messages_count_headings(monkeypatch, tmp_path):
    monkeypatch.setattr(pm, "ROOT", str(tmp_path))
    d = tmp_path / "_docs/founder-journal"
    d.mkdir(parents=True)
    now = pm.datetime.datetime(2026, 10, 7, 12, tzinfo=pm.BERLIN)
    (d / "2026-10-07.md").write_text("# t\n\n## 05:58\n\nx\n\n## 06:00\n\ny\n")
    assert pm.founder_messages_today(now)["value"] == 2


def test_default_repos_exact_six_audited():
    assert tuple(pm.REPOS) == EXPECTED_DEFAULTS
    assert "agent-bus" not in pm.REPOS
    assert "agent-hub" in pm.REPOS


def test_commits_canonical_query_pins_main(monkeypatch):
    capture = []
    fake_gh(monkeypatch, data=[[]], capture=capture)
    out = pm.commits_24h("agent-hub", SINCE_ISO, NOW)
    assert out["value"] == 0
    assert capture, "expected one gh call"
    url = capture[0][-1]
    assert "repos/alexeygrigorev/agent-hub/commits" in url
    assert "sha=main" in url
    assert f"since={SINCE_ISO}" in url


def test_commits_filters_old_returned_rows(monkeypatch):
    old = "2026-10-01T12:00:00Z"
    fake_gh(monkeypatch, data=[[row("aaa", old)]])
    out = pm.commits_24h("agent-hub", SINCE_ISO, NOW)
    assert out["value"] == 0


def test_commits_uses_committer_not_author(monkeypatch):
    current = "2026-10-14T11:00:00Z"
    old = "2026-10-01T12:00:00Z"
    # fresh author but stale committer -> out of window, must be filtered
    fake_gh(monkeypatch, data=[[row("aaa", old, author=current)]])
    assert pm.commits_24h("agent-hub", SINCE_ISO, NOW)["value"] == 0
    # stale author but fresh committer -> in window, must count
    fake_gh(monkeypatch, data=[[row("bbb", current, author=old)]])
    assert pm.commits_24h("agent-hub", SINCE_ISO, NOW)["value"] == 1


def test_commits_future_rows_filtered(monkeypatch):
    future = "2026-10-15T12:00:00Z"
    current = "2026-10-14T11:00:00Z"
    fake_gh(monkeypatch, data=[[row("fut", future), row("now", current)]])
    out = pm.commits_24h("agent-hub", SINCE_ISO, NOW)
    assert out["value"] == 1


def test_commits_invalid_committer_time_is_unknown(monkeypatch):
    fake_gh(monkeypatch, data=[[row("aaa", "not-a-time")]])
    out = pm.commits_24h("agent-hub", SINCE_ISO, NOW)
    assert out["value"] is None and out["unknown"]


def test_commits_missing_committer_is_unknown(monkeypatch):
    fake_gh(monkeypatch, data=[[{"sha": "aaa", "commit": {"author": {"date": "2026-10-14T11:00:00Z"}}}]])
    out = pm.commits_24h("agent-hub", SINCE_ISO, NOW)
    assert out["value"] is None and out["unknown"]


def test_commits_api_404_is_unknown_not_zero(monkeypatch):
    fake_gh(monkeypatch, err="gh failed: 404 Not Found")
    out = pm.commits_24h("agent-hub", SINCE_ISO, NOW)
    assert out["value"] is None and "404" in out["unknown"]


def test_commits_valid_empty_is_zero(monkeypatch):
    # F4 choice, pinned: both [[]] (one empty page, the true valid-empty
    # case) and [] (no pages at all under --slurp) are a valid empty
    # window 0. Non-list shapes stay UNKNOWN (see shape test below).
    fake_gh(monkeypatch, data=[[]])
    assert pm.commits_24h("agent-hub", SINCE_ISO, NOW)["value"] == 0
    fake_gh(monkeypatch, data=[])
    assert pm.commits_24h("agent-hub", SINCE_ISO, NOW)["value"] == 0


def test_commits_dedupes_unique_shas(monkeypatch):
    current = "2026-10-14T11:00:00Z"
    fake_gh(monkeypatch, data=[[row("aaa", current), row("aaa", current)],
                               [row("aaa", current), row("bbb", current)]])
    assert pm.commits_24h("agent-hub", SINCE_ISO, NOW)["value"] == 2


def test_commits_naive_committer_time_is_unknown(monkeypatch):
    # F1: naive datetime (no Z/offset) must be UNKNOWN, never assumed UTC.
    fake_gh(monkeypatch, data=[[row("aaa", "2026-10-14T11:00:00")]])
    out = pm.commits_24h("agent-hub", SINCE_ISO, NOW)
    assert out["value"] is None and out["unknown"]


def test_commits_date_only_committer_time_is_unknown(monkeypatch):
    # F1: date-only committer value must be UNKNOWN, never assumed UTC.
    fake_gh(monkeypatch, data=[[row("aaa", "2026-10-14")]])
    out = pm.commits_24h("agent-hub", SINCE_ISO, NOW)
    assert out["value"] is None and out["unknown"]


def test_commits_explicit_offset_committer_time_counts(monkeypatch):
    # F1 positive control: explicit numeric offset is a full datetime.
    fake_gh(monkeypatch, data=[[row("aaa", "2026-10-14T11:00:00+00:00")]])
    assert pm.commits_24h("agent-hub", SINCE_ISO, NOW)["value"] == 1


def test_commits_nonstring_sha_is_unknown(monkeypatch):
    # F2: sha must be a nonempty string; anything else is UNKNOWN, never
    # counted. A strict 40-hex sha is deliberately NOT required so the
    # short-name fixtures stay valid (real-API-truth leniency on sha).
    current = "2026-10-14T11:00:00Z"
    for bad_sha in (5, 0, True, False, None, "", ["x"], {"s": "x"}):
        fake_gh(monkeypatch, data=[[{"sha": bad_sha,
                                     "commit": {"committer": {"date": current}}}]])
        out = pm.commits_24h("agent-hub", SINCE_ISO, NOW)
        assert out["value"] is None and out["unknown"], bad_sha


def test_commits_unhashable_sha_never_crashes(monkeypatch):
    # F2 regression: unhashable sha (list) must yield UNKNOWN, not raise.
    current = "2026-10-14T11:00:00Z"
    fake_gh(monkeypatch, data=[[row(["x"], current)]])
    out = pm.commits_24h("agent-hub", SINCE_ISO, NOW)
    assert out["value"] is None and out["unknown"]


def test_commits_missing_sha_is_unknown(monkeypatch):
    current = "2026-10-14T11:00:00Z"
    fake_gh(monkeypatch, data=[[{"commit": {"committer": {"date": current}}}]])
    out = pm.commits_24h("agent-hub", SINCE_ISO, NOW)
    assert out["value"] is None and out["unknown"]


def test_commits_window_boundaries(monkeypatch):
    # F3: genuine preceding-24h interval is (since, now]: == since
    # excluded, == now included, inside edges counted, outside dropped.
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    since_s = SINCE.strftime(fmt)
    now_s = NOW.strftime(fmt)
    inside_after_since = (SINCE + pm.datetime.timedelta(seconds=1)).strftime(fmt)
    inside_before_now = (NOW - pm.datetime.timedelta(seconds=1)).strftime(fmt)
    after_now = (NOW + pm.datetime.timedelta(seconds=1)).strftime(fmt)
    fake_gh(monkeypatch, data=[[row("edge-since", since_s),
                                row("just-inside", inside_after_since),
                                row("mid", "2026-10-14T11:00:00Z"),
                                row("just-before-now", inside_before_now),
                                row("edge-now", now_s),
                                row("after-now", after_now)]])
    out = pm.commits_24h("agent-hub", SINCE_ISO, NOW)
    assert out["value"] == 4  # all but edge-since (old) and after-now (future)


def test_commits_bad_row_on_later_page_is_unknown(monkeypatch):
    # Malformed rows invalidate the whole repo window, even on page 2+.
    current = "2026-10-14T11:00:00Z"
    fake_gh(monkeypatch, data=[[row("good", current)],
                               [row("bad", "not-a-time")]])
    assert pm.commits_24h("agent-hub", SINCE_ISO, NOW)["value"] is None
    fake_gh(monkeypatch, data=[[row("good", current)],
                               [{"sha": ["x"],
                                 "commit": {"committer": {"date": current}}}]])
    assert pm.commits_24h("agent-hub", SINCE_ISO, NOW)["value"] is None
    fake_gh(monkeypatch, data=[[row("good", current)],
                               [row("naive", "2026-10-14T11:00:00")]])
    assert pm.commits_24h("agent-hub", SINCE_ISO, NOW)["value"] is None


def test_commits_unexpected_shape_is_unknown(monkeypatch):
    fake_gh(monkeypatch, data={"sha": "aaa"})
    assert pm.commits_24h("agent-hub", SINCE_ISO, NOW)["value"] is None
    fake_gh(monkeypatch, data=[{"sha": "aaa"}])
    assert pm.commits_24h("agent-hub", SINCE_ISO, NOW)["value"] is None
    fake_gh(monkeypatch, data=[[{}]])
    assert pm.commits_24h("agent-hub", SINCE_ISO, NOW)["value"] is None


def test_explicit_agent_bus_uses_verified_owner(monkeypatch):
    capture = []
    fake_gh(monkeypatch, data=[[]], capture=capture)
    out = pm.commits_24h("agent-bus", SINCE_ISO, NOW)
    assert out["value"] == 0
    url = capture[0][-1]
    assert "repos/PocketShell-io/agent-bus/commits" in url
    assert "alexeygrigorev/agent-bus" not in url
    assert "sha=main" in url


def test_explicit_fully_qualified_repo_passthrough(monkeypatch):
    capture = []
    fake_gh(monkeypatch, data=[[]], capture=capture)
    out = pm.commits_24h("PocketShell-io/agent-bus", SINCE_ISO, NOW)
    assert out["value"] == 0
    assert "repos/PocketShell-io/agent-bus/commits" in capture[0][-1]


def test_unresolvable_repo_is_unknown_not_zero(monkeypatch):
    fake_gh(monkeypatch, data=[[row("aaa", "2026-10-14T11:00:00Z")]])
    for bad in ("", "a/b/c"):
        out = pm.commits_24h(bad, SINCE_ISO, NOW)
        assert out["value"] is None and out["unknown"]


def test_default_coverage_all_six_repos(monkeypatch):
    seen = []

    def fake(args):
        seen.append(args[-1])
        return [[]], None

    monkeypatch.setattr(pm, "gh_json", fake)
    for repo in EXPECTED_DEFAULTS:
        out = pm.commits_24h(repo, SINCE_ISO, NOW)
        assert out["value"] == 0, repo
    joined = "\n".join(seen)
    for repo in EXPECTED_DEFAULTS:
        assert f"repos/alexeygrigorev/{repo}/commits" in joined
    assert "agent-bus" not in joined


def test_build_passes_strict_window(monkeypatch, tmp_path):
    recorded = {}

    def fake_commits(repo, since_iso, now=None):
        recorded["since"] = since_iso
        recorded["now"] = now
        return pm.val(0)

    monkeypatch.setattr(pm, "collect_fleet", lambda d: (SNAP, None))
    monkeypatch.setattr(pm, "issue_counts", lambda r, day, *a: pm.val(
        {"open": 0, "created_today": 0, "closed_today": 0}))
    monkeypatch.setattr(pm, "commits_24h", fake_commits)
    before = pm.datetime.datetime.now(pm.datetime.timezone.utc)
    pm.build(before, str(tmp_path), ["agent-hub"])
    assert recorded["now"] == before
    expected_since = (before - pm.datetime.timedelta(hours=24)).replace(microsecond=0)
    assert pm.parse_utc(recorded["since"]) == expected_since

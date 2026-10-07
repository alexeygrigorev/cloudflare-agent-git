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


def stub(monkeypatch, snap=SNAP, err=None, issues=None, commits=None):
    monkeypatch.setattr(pm, "collect_fleet", lambda d: (snap, err))
    monkeypatch.setattr(pm, "issue_counts", lambda r, day: issues or pm.val(
        {"open": 5, "created_today": 300, "closed_today": 250}))
    monkeypatch.setattr(pm, "commits_24h", lambda r, s: commits or pm.val(2500))


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

import importlib.machinery
import importlib.util
import pathlib
import time

path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "team-status"
loader = importlib.machinery.SourceFileLoader("team_status", str(path))
spec = importlib.util.spec_from_loader("team_status", loader)
ts = importlib.util.module_from_spec(spec)
loader.exec_module(ts)


def session(tag, state, alive=True):
    now = time.time() * 1000
    return {"tag": tag, "state": "running", "worker_alive": alive, "reported_state": state,
            "reported_state_at_ms": now - 600000, "last_activity_ms": now - 60000}


def test_stopped_and_idle_heads_show_up(monkeypatch, capsys):
    snap = [session("branches-head", "idle"), session("bus-head", "working", alive=False)]
    monkeypatch.setattr(ts, "sessions", lambda: snap)
    monkeypatch.setattr(ts, "count_issues", lambda f: None)
    monkeypatch.setattr(ts, "commits_today", lambda: None)
    assert ts.main() == 1
    out = capsys.readouterr().out
    assert "branches-head: running, idle for 10 min" in out
    assert "bus-head: not running" in out
    assert "dashboard-head: not running" in out
    assert "cloud cost this month: unknown" in out
    assert "Off target:" in out and "bus-head" in out


def test_unreadable_data_exits_2(monkeypatch):
    monkeypatch.setattr(ts, "sessions", lambda: None)
    assert ts.main() == 2

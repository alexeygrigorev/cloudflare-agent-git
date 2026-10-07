import importlib.util
import json
import pathlib

import pytest

_spec = importlib.util.spec_from_file_location(
    "launch_gates", pathlib.Path(__file__).resolve().parents[1] / "scripts" / "launch_gates.py")
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)

GIB = 1024 ** 3


@pytest.mark.parametrize("mem,pids", [
    (None, "100"), ("", "100"), ("2G", "100"), ("1501M", "100"),
    ("1500M", None), ("1500M", "101"), ("1500M", "0"), ("1500M", "x"),
])
def test_limits_refused(mem, pids):
    with pytest.raises(g.LaunchRefused):
        g.check_limits(mem, pids)


def test_limits_accepted():
    g.check_limits("1500M", "100")
    g.check_limits("1G", 50)


def test_disk_floor_counts_promised_growth():
    with pytest.raises(g.LaunchRefused):
        g.check_disk(19 * GIB)
    with pytest.raises(g.LaunchRefused):
        g.check_disk(25 * GIB, promised_bytes=6 * GIB)
    assert g.check_disk(25 * GIB) is True      # launch, but start cleanup
    assert g.check_disk(40 * GIB) is False


def test_reviewer_must_differ():
    with pytest.raises(g.LaunchRefused):
        g.check_review("GPT-5", " gpt-5 ")
    with pytest.raises(g.LaunchRefused):
        g.check_review("gpt-5", None)
    g.check_review("gpt-5", "sonnet-5")


def test_check_launch_end_to_end():
    ok = g.check_launch("1500M", 100, 25 * GIB, implementer_model="a",
                        reviewer_model="b", reviewer_launch=True)
    assert ok == {"launch_allowed": True, "cleanup_agent": True}
    with pytest.raises(g.LaunchRefused):
        g.check_launch("1500M", 100, 40 * GIB, implementer_model="a",
                       reviewer_model="a", reviewer_launch=True)


def test_cli_exit_codes(capsys):
    assert g.main(["--memory", "1500M", "--pids", "100", "--disk-path", "/"]) in (0, 75)
    assert g.main(["--pids", "100"]) == 75
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["launch_allowed"] is False

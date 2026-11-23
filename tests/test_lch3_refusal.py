"""Study D2's walls, on made-up records: a launch that set the constants is never
scored, a scored launch never sets a constant, and the scoring script runs only
on the frozen files. No fetched file is read, and no test here can score.
"""
import os
import subprocess
import sys
from datetime import datetime, timezone

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
D2 = os.path.join(os.path.dirname(HERE), "docs", "studies", "d2")
sys.path.insert(0, D2)
import rule  # noqa: E402
import score  # noqa: E402

T0 = datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
LAUNCHES = [
    {"n": 1, "side": rule.SETS, "tag": "2030-001", "t0": T0, "flight": "made up",
     "records": "fetched", "controls": [-7]},
    {"n": 2, "side": rule.SCORED, "tag": "2030-002", "t0": T0, "flight": "made up",
     "records": "fetched", "controls": [7]},
]


class Loader:
    def __init__(self):
        self.calls = []

    def __call__(self, tag, station, days):
        self.calls.append((tag, station, days))
        return None


def test_lch3_a_launch_that_set_the_constants_is_refused_by_name_when_scored():
    loader = Loader()
    with pytest.raises(rule.Refusal) as e:
        rule.collect(LAUNCHES, ["2030-002", "2030-001"], rule.SCORED, loader)
    assert e.value.name == "SCORED-A-CONSTANT-SETTING-LAUNCH"
    assert e.value.detail == "2030-001"
    # refused before any record was asked for, the scored launch's among them
    assert loader.calls == []


def test_lch3_a_scored_launch_is_refused_by_name_when_it_would_set_constants():
    loader = Loader()
    with pytest.raises(rule.Refusal) as e:
        rule.collect(LAUNCHES, ["2030-001", "2030-002"], rule.SETS, loader)
    assert e.value.name == "CONSTANTS-FROM-A-SCORED-LAUNCH"
    assert e.value.detail == "2030-002"
    assert loader.calls == []


def test_lch3_the_right_side_is_not_refused_and_asks_only_for_its_own_records():
    loader = Loader()
    rule.collect(LAUNCHES, ["2030-002"], rule.SCORED, loader)
    # 4 stations, the launch record and one control record each
    assert len(loader.calls) == 8
    assert set(c[0] for c in loader.calls) == {"2030-002"}
    loader = Loader()
    rule.collect(LAUNCHES, ["2030-001"], rule.SETS, loader)
    assert set(c[0] for c in loader.calls) == {"2030-001"}


def test_lch3_a_launch_the_list_does_not_hold_is_refused():
    with pytest.raises(rule.Refusal) as e:
        rule.collect(LAUNCHES, ["2030-999"], rule.SCORED, Loader())
    assert e.value.name == "UNKNOWN-LAUNCH"


def test_lch3_the_committed_split_is_twelve_and_the_one_looked_at_against_twenty_three():
    launches = rule.read_launches(os.path.join(D2, "launches.tsv"))
    sets = [r["tag"] for r in launches if r["side"] == rule.SETS]
    scored = [r["tag"] for r in launches if r["side"] == rule.SCORED]
    assert len(sets) == 13 and len(scored) == 23
    assert not set(sets) & set(scored)
    # the launch D1b looked at is on the constant-setting side, with no record
    looked = [r for r in launches if r["tag"] == "2021-082"]
    assert len(looked) == 1 and looked[0]["side"] == rule.SETS
    assert looked[0]["records"] == "none"
    # by date: every constant-setting launch is before every scored one
    assert max(r["t0"] for r in launches if r["side"] == rule.SETS) < min(
        r["t0"] for r in launches if r["side"] == rule.SCORED)
    # every launch of the committed list that set constants is refused when scored
    for tag in sets:
        loader = Loader()
        with pytest.raises(rule.Refusal) as e:
            rule.collect(launches, [tag], rule.SCORED, loader)
        assert e.value.name == "SCORED-A-CONSTANT-SETTING-LAUNCH" and e.value.detail == tag
        assert loader.calls == []
    # and every scored one is refused when it would set constants
    for tag in scored:
        with pytest.raises(rule.Refusal) as e:
            rule.collect(launches, [tag], rule.SETS, Loader())
        assert e.value.name == "CONSTANTS-FROM-A-SCORED-LAUNCH" and e.value.detail == tag


def test_lch3_a_list_with_one_launch_on_both_sides_is_refused(tmp_path):
    p = tmp_path / "launches.tsv"
    p.write_text("1\tsets-constants\t2030-001\t2030-01-02T03:04:05\tx\tfetched\t-7\n"
                 "2\tscored\t2030-001\t2030-01-02T03:04:05\tx\tfetched\t+7\n", encoding="utf-8")
    with pytest.raises(rule.Refusal) as e:
        rule.read_launches(str(p))
    assert e.value.name == "LAUNCH-ON-BOTH-SIDES"


def test_lch3_a_file_that_is_not_the_one_fetched_is_refused(tmp_path):
    name = rule.record_name("LOC", "2030-002", None)
    (tmp_path / name).write_bytes(b"not what was fetched")
    loader = rule.make_loader(str(tmp_path), {name: ("200", "0" * 64)})
    with pytest.raises(rule.Refusal) as e:
        loader("2030-002", "LOC", None)
    assert e.value.name == "FILE-NOT-AS-FETCHED"
    # a name answered 404 is no file, and a name with no line is refused
    loader = rule.make_loader(str(tmp_path), {name: ("404", "-")})
    assert loader("2030-002", "LOC", None) is None
    with pytest.raises(rule.Refusal) as e:
        rule.make_loader(str(tmp_path), {})("2030-002", "LOC", None)
    assert e.value.name == "NOT-IN-MANIFEST"


def test_lch3_the_freeze_hash_moves_with_one_byte_of_one_file(tmp_path):
    for name, data in (("a.py", b"rule\n"), ("b.json", b"{}\n")):
        (tmp_path / name).write_bytes(data)
    lines, before = score.freeze_lines(str(tmp_path), ["a.py", "b.json"])
    assert len(lines) == 2 and lines[0].endswith("  a.py")
    (tmp_path / "b.json").write_bytes(b"{ }\n")
    _lines, after = score.freeze_lines(str(tmp_path), ["a.py", "b.json"])
    assert before != after


def run_score(*args):
    return subprocess.run([sys.executable, "-B", os.path.join(D2, "score.py")] + list(args),
                          capture_output=True, text=True)


def test_lch3_the_scoring_script_refuses_files_that_are_not_the_frozen_ones(tmp_path):
    out_path = os.path.join(D2, "scored-output.txt")
    before = open(out_path, "rb").read() if os.path.exists(out_path) else None
    got = run_score(str(tmp_path), "--freeze", "0" * 64)
    assert got.returncode != 0 and "REFUSED NOT-FROZEN" in got.stderr, got.stderr
    after = open(out_path, "rb").read() if os.path.exists(out_path) else None
    assert before == after


def test_lch3_the_scoring_script_refuses_a_second_run_and_a_fetch_that_is_not_whole(tmp_path):
    # With the right freeze hash and an empty data folder it must refuse either
    # way, and open no record: ALREADY-SCORED once the one run's output exists,
    # FETCH-NOT-COMPLETE before it does. It can never score from here.
    out_path = os.path.join(D2, "scored-output.txt")
    before = open(out_path, "rb").read() if os.path.exists(out_path) else None
    _lines, freeze = score.freeze_lines()
    got = run_score(str(tmp_path), "--freeze", freeze)
    assert got.returncode != 0
    want = "REFUSED ALREADY-SCORED" if before is not None else "REFUSED FETCH-NOT-COMPLETE"
    assert want in got.stderr, got.stderr
    after = open(out_path, "rb").read() if os.path.exists(out_path) else None
    assert before == after

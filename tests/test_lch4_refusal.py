"""Study D3's walls, on made-up records: a launch that set the constants is never
scored, a scored launch never sets a constant, and the scoring script runs only on the
frozen files, only on a whole fetch, and only once. No fetched file is read, and no
test here can score: the script is run in a copy of the study, on an empty folder.
"""
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
D3 = os.path.join(os.path.dirname(HERE), "docs", "studies", "d3")
sys.path.insert(0, D3)
import d3rule as rule  # noqa: E402
import d3score as score  # noqa: E402
import d3setconstants as setconstants  # noqa: E402

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


def committed():
    return rule.read_launches(os.path.join(D3, "launches.tsv"))


def test_lch4_a_launch_that_set_the_constants_is_refused_by_name_when_scored():
    loader = Loader()
    with pytest.raises(rule.Refusal) as e:
        rule.collect(LAUNCHES, ["2030-002", "2030-001"], rule.SCORED, loader)
    assert (e.value.name, e.value.detail) == ("SCORED-A-CONSTANT-SETTING-LAUNCH", "2030-001")
    # refused before any record was asked for, the scored launch's among them
    assert loader.calls == []


def test_lch4_a_scored_launch_is_refused_by_name_when_it_would_set_constants():
    loader = Loader()
    with pytest.raises(rule.Refusal) as e:
        rule.collect(LAUNCHES, ["2030-001", "2030-002"], rule.SETS, loader)
    assert (e.value.name, e.value.detail) == ("CONSTANTS-FROM-A-SCORED-LAUNCH", "2030-002")
    assert loader.calls == []


def test_lch4_the_right_side_is_not_refused_and_asks_only_for_its_own_records():
    loader = Loader()
    rule.collect(LAUNCHES, ["2030-002"], rule.SCORED, loader)
    # 4 stations, the launch record and one control record each
    assert len(loader.calls) == 8 and set(c[0] for c in loader.calls) == {"2030-002"}
    loader = Loader()
    rule.collect(LAUNCHES, ["2030-001"], rule.SETS, loader)
    assert set(c[0] for c in loader.calls) == {"2030-001"}


def test_lch4_a_launch_the_list_does_not_hold_is_refused():
    with pytest.raises(rule.Refusal) as e:
        rule.collect(LAUNCHES, ["2030-999"], rule.SCORED, Loader())
    assert e.value.name == "UNKNOWN-LAUNCH"


def test_lch4_every_committed_constant_setting_launch_is_refused_when_scored_and_every_scored_one_when_setting():
    launches = committed()
    sets = [r["tag"] for r in launches if r["side"] == rule.SETS]
    scored = [r["tag"] for r in launches if r["side"] == rule.SCORED]
    assert len(sets) == 13 and len(scored) == 23
    for tag in sets:
        loader = Loader()
        with pytest.raises(rule.Refusal) as e:
            rule.collect(launches, [tag], rule.SCORED, loader)
        assert (e.value.name, e.value.detail) == ("SCORED-A-CONSTANT-SETTING-LAUNCH", tag)
        assert loader.calls == []
    for tag in scored:
        loader = Loader()
        with pytest.raises(rule.Refusal) as e:
            rule.collect(launches, [tag], rule.SETS, loader)
        assert (e.value.name, e.value.detail) == ("CONSTANTS-FROM-A-SCORED-LAUNCH", tag)
        assert loader.calls == []
        # and the constant-setting script's own check, which runs before it asks
        # the manifest anything
        with pytest.raises(rule.Refusal) as e:
            setconstants.refuse_other_side(launches, ["2024-002", tag])
        assert (e.value.name, e.value.detail) == ("CONSTANTS-FROM-A-SCORED-LAUNCH", tag)
    setconstants.refuse_other_side(launches, sets)


def test_lch4_a_list_with_one_launch_on_both_sides_is_refused(tmp_path):
    p = tmp_path / "launches.tsv"
    p.write_text("1\tsets-constants\t2030-001\t2030-01-02T03:04:05\tx\tfetched\t-7\n"
                 "2\tscored\t2030-001\t2030-01-02T03:04:05\tx\tfetched\t+7\n", encoding="utf-8")
    with pytest.raises(rule.Refusal) as e:
        rule.read_launches(str(p))
    assert e.value.name == "LAUNCH-ON-BOTH-SIDES"


def test_lch4_a_file_that_is_not_the_one_fetched_is_refused(tmp_path):
    name = rule.record_name("MPP", "2030-002", None)
    (tmp_path / name).write_bytes(b"not what was fetched")
    loader = rule.make_loader(str(tmp_path), {name: ("200", "0" * 64)})
    with pytest.raises(rule.Refusal) as e:
        loader("2030-002", "MPP", None)
    assert e.value.name == "FILE-NOT-AS-FETCHED"
    # a name answered 404 is no file, and a name with no line is refused
    assert rule.make_loader(str(tmp_path), {name: ("404", "-")})("2030-002", "MPP", None) is None
    with pytest.raises(rule.Refusal) as e:
        rule.make_loader(str(tmp_path), {})("2030-002", "MPP", None)
    assert e.value.name == "NOT-IN-MANIFEST"


def test_lch4_the_freeze_hash_moves_with_one_byte_of_one_file(tmp_path):
    for name, data in (("a.py", b"rule\n"), ("b.json", b"{}\n")):
        (tmp_path / name).write_bytes(data)
    lines, before = score.freeze_lines(str(tmp_path), ["a.py", "b.json"])
    assert len(lines) == 2 and lines[0].endswith("  a.py")
    (tmp_path / "b.json").write_bytes(b"{ }\n")
    assert score.freeze_lines(str(tmp_path), ["a.py", "b.json"])[1] != before
    assert score.FROZEN == ["docs/studies/d3/d3rule.py", "docs/studies/d3/d3score.py",
                            "docs/studies/d3/constants.json", "docs/studies/d3/launches.tsv",
                            "docs/studies/d3/manifest.tsv", "docs/studies/d1/firstlook.py",
                            "docs/studies/d1/mseed.py"]


def copy_of_the_study(tmp_path):
    """(the copy's d3score.py, its output path, an empty data folder, its freeze hash).

    The tests below run the scoring script in a copy of the two study folders it
    reads, against an empty data folder: nothing here can score a real record or
    touch the one run's output in the tree."""
    studies = os.path.dirname(D3)
    root = tmp_path / "tree"
    for d in ("d1", "d3"):
        shutil.copytree(os.path.join(studies, d), str(root / "docs" / "studies" / d),
                        ignore=shutil.ignore_patterns("__pycache__", "fig"))
    script = str(root / "docs" / "studies" / "d3" / "d3score.py")
    output = root / "docs" / "studies" / "d3" / "scored-output.txt"
    data = tmp_path / "no-data"
    data.mkdir()
    got = subprocess.run([sys.executable, "-B", script, "--freeze-hash"], capture_output=True, text=True)
    freeze = got.stdout.strip().split("\n")[-1].split()[-1]
    assert len(freeze) == 64, got.stdout + got.stderr
    return script, output, str(data), freeze


def run_score(script, *args):
    return subprocess.run([sys.executable, "-B", script] + list(args), capture_output=True, text=True)


def test_lch4_the_scoring_script_refuses_files_that_are_not_the_frozen_ones(tmp_path):
    script, output, data, freeze = copy_of_the_study(tmp_path)
    if output.exists():
        output.unlink()
    got = run_score(script, data, "--freeze", "0" * 64)
    assert got.returncode != 0 and "REFUSED NOT-FROZEN" in got.stderr, got.stderr
    # the hash that was right, after one byte of the constants has changed
    constants = output.parent / "constants.json"
    constants.write_bytes(constants.read_bytes() + b" ")
    got = run_score(script, data, "--freeze", freeze)
    assert got.returncode != 0 and "REFUSED NOT-FROZEN" in got.stderr, got.stderr
    assert not output.exists()


def test_lch4_the_scoring_script_refuses_a_fetch_that_is_not_whole(tmp_path):
    # the right hash, no output yet, and a data folder holding none of the files the
    # manifest says came: it must not score part of the set, or any.
    script, output, data, freeze = copy_of_the_study(tmp_path)
    if output.exists():
        output.unlink()
    got = run_score(script, data, "--freeze", freeze)
    assert got.returncode != 0 and "REFUSED FETCH-NOT-COMPLETE" in got.stderr, got.stderr
    assert not output.exists()


def test_lch4_the_scoring_run_writes_the_file_it_then_refuses_on(tmp_path, monkeypatch):
    # D2's limit: the name the run writes under was held by no test, so a run that wrote
    # under one name and looked for another would not refuse a second run. Here main() is
    # run in-process, its output path moved to a temporary folder, with a fetch that is
    # settled and a loader that has no file: the first call must write that very path,
    # and the second must be refused on it.
    out = tmp_path / "scored-output.txt"
    monkeypatch.setattr(score, "OUTPUT", str(out))
    monkeypatch.setattr(score.rule, "not_fetched", lambda *a: [])
    monkeypatch.setattr(score.rule, "make_loader", lambda *a: (lambda tag, station, days: None))
    freeze = score.freeze_lines()[1]
    monkeypatch.setattr(sys, "argv", ["d3score.py", str(tmp_path / "no-data"), "--freeze", freeze])
    assert score.main() == 0
    assert out.read_text(encoding="utf-8").split("\n")[:2] == [
        "Study D3, the scoring run.", "Freeze hash %s." % freeze]
    assert [p.name for p in tmp_path.iterdir()] == ["scored-output.txt"]
    with pytest.raises(SystemExit) as e:
        score.main()
    assert "REFUSED ALREADY-SCORED" in str(e.value)


def test_lch4_the_scoring_script_refuses_a_second_run(tmp_path):
    script, output, data, freeze = copy_of_the_study(tmp_path)
    output.write_bytes(b"the one run's output\n")
    got = run_score(script, data, "--freeze", freeze)
    assert got.returncode != 0 and "REFUSED ALREADY-SCORED" in got.stderr, got.stderr
    assert output.read_bytes() == b"the one run's output\n"

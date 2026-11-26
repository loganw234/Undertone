"""LRN-C: the judge, `hw/lrnc/lrnc.py compare`, on a day run end to end with the stand-in for the card.

WHAT THIS HOLDS, at M = 1,024 (the cases, the expectations, the four runs through host.run_case, the judge):
  - the day as it should go PASSes, exit 0, with the control moved SEEN at the record the model runs predict;
  - THE NAMED CONTROLS, each failing as named:
      1. a card record changed in one word is reported at that record, in each field (index, epoch, flags,
         score), with both values;
      2. an update the host names at another index: moved is SEEN at its predicted record; a "moved" run that
         is flow's own (the update named at flow's index) is NOT SEEN, and the day FAILs;
      3. a host operation made outside its window is refused by name and reported OUTSIDE it, too early
         (UPDATE_UNFINISHED) and too late (SWAP_INDEX); each side of the bracket's check alone;
      4. a learner counter, a status bit, lrn_update_at, lrn_refusal or a cap read back changed by one is
         reported by its name;
  - every condition of the verdict broken alone FAILs it: a run not there, a run with no PASS line, a run short
    of its records, the operations' count, an operation's kind or argument, the moved prediction's own premise.
(The named control 5, a learner that reads truth, is in tests/test_lrn_c_standin.py.)
"""
import json
import os
import shutil

import pytest

from hw.e0c import pieces
from hw.lrnc import lrnc, standin

M = 1024
R = pieces.RECORD_BYTES


@pytest.fixture(scope="module")
def day(tmp_path_factory):
    base = str(tmp_path_factory.mktemp("lrnc_day"))
    cases_dir = lrnc.cases(os.path.join(base, "cases"), M)
    for name in lrnc.CASES:
        lrnc.expect(cases_dir, name)
    runs = os.path.join(base, "runs")
    for run_name, case_name in lrnc.RUNS:
        standin.run(cases_dir, case_name, os.path.join(runs, run_name))
    return base, cases_dir, runs


def copy_runs(day, tmp_path):
    _base, _cases, runs = day
    mine = str(tmp_path / "runs")
    shutil.copytree(runs, mine)
    return mine


def judged(day, runs, capsys):
    capsys.readouterr()
    code = lrnc.compare(day[1], runs)
    out = capsys.readouterr().out
    with open(os.path.join(runs, "card-lrnc.json"), encoding="utf-8") as f:
        return code, out, json.load(f)


def edit_report(runs, run_name, change):
    path = os.path.join(runs, run_name, "report.json")
    with open(path, encoding="utf-8") as f:
        r = json.load(f)
    change(r)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(r, f)


def test_lrn_c_the_day_as_it_should_go_passes_with_the_control_seen(day, tmp_path, capsys):
    code, out, card = judged(day, copy_runs(day, tmp_path), capsys)
    assert code == 0, out
    assert out.strip().split("\n")[-1] == "== LRN-C CARD VERDICT: PASS"
    for name in ("flow", "rich", "moved", "flow-again"):
        assert ("== LRN-C RUN %s: IDENTICAL" % name) in out
    assert "== LRN-C CONTROL moved: SEEN" in out and "different from flow's first at record %d, score" % (2 * M) in out
    assert card["verdict"] == "PASS" and card["failed"] == []
    assert out.count("inside") == 2 + 13 + 2 + 2 and "OUTSIDE" not in out


@pytest.mark.parametrize("field", ["index", "epoch", "flags", "score"])
@pytest.mark.parametrize("record", [3, 2 * M + 5])
def test_lrn_c_control_a_card_record_changed_in_one_word_is_reported_at_that_record_in_that_field(
        day, tmp_path, capsys, field, record):
    runs = copy_runs(day, tmp_path)
    path = os.path.join(runs, "flow", "records.bin")
    data = bytearray(open(path, "rb").read())
    values = list(pieces.RECORD.unpack_from(data, record * R))
    i = pieces.SCORE_FIELDS.index(field)
    model = values[i]
    values[i] = model ^ 1 if field == "flags" else model + 1
    pieces.RECORD.pack_into(data, record * R, *values)
    open(path, "wb").write(bytes(data))
    code, out, card = judged(day, runs, capsys)
    assert code == 1 and "== LRN-C CARD VERDICT: FAIL" in out
    assert card["runs"]["flow"]["first"] == {"record": record, "field": field, "card": values[i], "model": model}
    assert card["runs"]["flow-again"]["identical"], "only the run changed is reported"


def test_lrn_c_control_moved_named_at_flows_own_index_is_not_seen(day, tmp_path, capsys):
    runs = copy_runs(day, tmp_path)
    shutil.rmtree(os.path.join(runs, "moved"))
    shutil.copytree(os.path.join(runs, "flow"), os.path.join(runs, "moved"))
    code, out, _card = judged(day, runs, capsys)
    assert code == 1
    assert "== LRN-C CONTROL moved: NOT SEEN: the card's moved run is not its own model run" in out
    assert "== LRN-C RUN moved: DIFFERENT" in out


def test_lrn_c_control_moved_whose_model_runs_do_not_differ_after_the_commit_is_not_seen(day, tmp_path, capsys):
    """The prediction's own premise: if the model's moved run were flow's, nothing would be predicted."""
    base = str(tmp_path / "copy")
    shutil.copytree(day[0], base)
    cases_dir, runs = os.path.join(base, "cases"), os.path.join(base, "runs")
    shutil.copyfile(os.path.join(cases_dir, "expect", "flow", "records.bin"),
                    os.path.join(cases_dir, "expect", "moved", "records.bin"))
    capsys.readouterr()
    assert lrnc.compare(cases_dir, runs) == 1
    assert "== LRN-C CONTROL moved: NOT SEEN: the model's own moved and flow runs differ at None" in capsys.readouterr().out


def test_lrn_c_control_moved_whose_model_runs_differ_first_before_the_commit_is_not_seen(day, tmp_path, capsys):
    """The prediction's own premise, the other half: the two model runs must differ first at or after the commit,
    in the score. Record 3's score is changed in moved's model records and in the card's moved run alike, so the
    card is its own model run and differs from flow's first where the prediction says, but before the commit."""
    base = str(tmp_path / "copy")
    shutil.copytree(day[0], base)
    cases_dir, runs = os.path.join(base, "cases"), os.path.join(base, "runs")
    for path in (os.path.join(cases_dir, "expect", "moved", "records.bin"), os.path.join(runs, "moved", "records.bin")):
        data = bytearray(open(path, "rb").read())
        values = list(pieces.RECORD.unpack_from(data, 3 * R))
        values[3] += 1
        pieces.RECORD.pack_into(data, 3 * R, *values)
        open(path, "wb").write(bytes(data))
    capsys.readouterr()
    assert lrnc.compare(cases_dir, runs) == 1
    out = capsys.readouterr().out
    assert "== LRN-C CONTROL moved: NOT SEEN: the model's own moved and flow runs differ at {'record': 3" in out
    assert "not first in the score at or after the commit at %d" % (2 * M) in out


def _with_script(day, tmp_path, change, stride=37):
    """The day's runs, with flow made again under a script changed by `change` (the expectation unchanged)."""
    runs = copy_runs(day, tmp_path)
    cases_dir = day[1]
    script = json.load(open(os.path.join(cases_dir, "flow", "script.json"), encoding="utf-8"))
    change(script)
    folder = str(tmp_path / "script")
    os.makedirs(folder)
    path = os.path.join(folder, "script.json")
    json.dump(script, open(path, "w", encoding="utf-8"))
    shutil.copyfile(os.path.join(cases_dir, "flow", "blank.blob"), os.path.join(folder, "blank.blob"))
    shutil.rmtree(os.path.join(runs, "flow"))
    standin.run(cases_dir, "flow", os.path.join(runs, "flow"), stride=stride, script=path)
    return runs


def test_lrn_c_control_a_commit_made_too_early_is_refused_by_name_and_reported_outside_its_window(day, tmp_path, capsys):
    def early(script):
        script[1]["after"] = M + 256 - 60
    code, out, card = judged(day, _with_script(day, tmp_path, early), capsys)
    assert code == 1
    line = [x for x in out.splitlines() if "flow op 1 commit" in x][0]
    assert "UPDATE_UNFINISHED, the model's taken" in line and "OUTSIDE its window [1280, 2048]" in line
    assert "NOT the model's" in line
    assert card["runs"]["flow"]["first"]["record"] == 2 * M and card["runs"]["flow"]["first"]["field"] == "epoch"
    assert "lrn_early 1 where the model has 0" in out


def test_lrn_c_control_an_update_made_too_late_is_refused_by_name_and_reported_outside_its_window(day, tmp_path, capsys):
    code, out, _card = judged(day, _with_script(day, tmp_path, lambda s: None, stride=3000), capsys)
    assert code == 1
    line = [x for x in out.splitlines() if "flow op 0 update" in x][0]
    assert "SWAP_INDEX, the model's taken" in line and "OUTSIDE its window [0, 1024]" in line


@pytest.mark.parametrize("side, k, value", [("next_index_before", 1, 1279), ("next_index_after", 1, 2049),
                                             ("next_index_after", 0, 1025)])
def test_lrn_c_each_side_of_the_brackets_check_alone_fails_an_operation_with_the_models_outcome(
        day, tmp_path, capsys, side, k, value):
    runs = copy_runs(day, tmp_path)
    edit_report(runs, "flow", lambda r: r["learner"]["ops"][k].__setitem__(side, value))
    code, out, _card = judged(day, runs, capsys)
    assert code == 1
    line = [x for x in out.splitlines() if "flow op %d " % k in x][0]
    assert "OUTSIDE its window" in line and "NOT the model's" not in line


REGISTERS = ([("counts", n, d) for n in ("lrn_count0", "lrn_count1", "lrn_skip_start", "lrn_skip_busy",
                                         "lrn_skip_full", "lrn_made", "lrn_unmade", "lrn_early") for d in (1, -1)]
             + [("lrn_status", b, None) for b in ("named", "running", "made", "unmade", "refused", "refused_again")]
             + [("caps", "lrn_cap_count_bits", -1), ("caps", "lrn_cap_update_frames", 1),
                (None, "lrn_update_at", 1), (None, "lrn_refusal", "QUANTISE_INPUT"), (None, "lrn_status_word", 64)])


@pytest.mark.parametrize("group, name, delta", REGISTERS)
def test_lrn_c_control_a_register_read_back_changed_by_one_is_reported_by_name(day, tmp_path, capsys, group, name, delta):
    runs = copy_runs(day, tmp_path)

    def change(r):
        end = r["learner"]["end"]
        if group == "lrn_status":
            end["lrn_status"][name] ^= 1
        elif group:
            end[group][name] += delta
        elif name == "lrn_refusal":
            end[name] = delta
        elif name == "lrn_status_word":
            end[name] |= delta
        else:
            end[name] += delta
    edit_report(runs, "rich", change)
    code, out, _card = judged(day, runs, capsys)
    assert code == 1
    line = [x for x in out.splitlines() if x.strip().startswith("rich registers at the end")][0]
    assert "NOT the model's" in line and (name if name != "lrn_status_word" else "lrn_status's word") in line


def test_lrn_c_each_verdict_condition_broken_alone_fails_the_day(day, tmp_path, capsys):
    cases = {
        "a run not there": lambda runs: shutil.rmtree(os.path.join(runs, "rich")),
        "no PASS line": lambda runs: open(os.path.join(runs, "flow-again.log"), "w").close(),
        "short of its records": lambda runs: edit_report(runs, "flow", lambda r: r["run"].__setitem__("records", 4095)),
        "an operation fewer": lambda runs: edit_report(runs, "flow", lambda r: r["learner"]["ops"].pop()),
        "another kind": lambda runs: edit_report(runs, "flow", lambda r: r["learner"]["ops"][1].__setitem__("op", "update")),
        "another argument": lambda runs: edit_report(runs, "flow", lambda r: r["learner"]["ops"][1].__setitem__("arg", 2049)),
        "another blob": lambda runs: edit_report(runs, "rich", lambda r: r["learner"]["ops"][4].__setitem__("blob", "matched.blob")),
        "a clear that read nothing": lambda runs: edit_report(runs, "rich", lambda r: r["learner"]["ops"][1].__setitem__("read", None)),
        "no registers": lambda runs: edit_report(runs, "flow", lambda r: r["learner"].pop("end")),
    }
    for what, breaks in cases.items():
        runs = str(tmp_path / what.replace(" ", "-"))
        shutil.copytree(day[2], runs)
        breaks(runs)
        capsys.readouterr()
        assert lrnc.compare(day[1], runs) == 1, what
        assert "== LRN-C CARD VERDICT: FAIL" in capsys.readouterr().out, what


def test_lrn_c_compare_exits_0_only_on_pass_from_the_command_line(day, tmp_path, capsys):
    runs = copy_runs(day, tmp_path)
    assert lrnc.main(["compare", day[1], runs]) == 0
    edit_report(runs, "moved", lambda r: r["learner"]["end"]["counts"].__setitem__("lrn_made", 2))
    assert lrnc.main(["compare", day[1], runs]) == 1

"""E0C: the ten timed runs' script (hw/e0c/timed.py) on a short case, the card a stand-in that writes the model's run.

What is held: ten generations run one after another, each loading its own set, each opening and closing its
backend; every part of the sum present and timed, the sum the sum of its parts; each generation's counts and the
SHA-256 of its records the model's own run of that set (`e0c.py expect --timed`), as `timed-judge` reads them. Its
control: two sets' files exchanged in the cases folder, so that generation 3 runs set 4's weights; `timed-judge`
reports generation 3 (and 4) DIFFERENT, by records and counts. And a generation that does not end done stops the ten.

The ten sets are e0c.py's rule: set g's coefficients quantise (g + 1) e0[j] + (9 - g) e0[63 - j]; set 9 is E0's own
matched filter, the same blob as the experiment's (held below). The stand-in's clock counts operations, so the
trace's parts here are in its units, not in ns; the host's parts are perf_counter_ns as on the card.

Short case: the timed stream at 150 injections (19,328 frames), seed 2026112402, so every truth record is written
before the start (the stand-in runs the model once, at krn_start), and the signal-free reads cross often enough
that a wrong offset for them shows in the counts.
"""
import contextlib
import io
import json
import os
import shutil

import pytest

import test_seam_e0 as E0
from spec import constants as C
from model.refusal import Refusal

from hw.e0c import e0c, timed
from hw.e0c.kernel_model import ModelKernel

_made = {}
TRIALS = 150     # 19,328 frames: the signal-free reads cross (on this seed; at 100 trials they do not), so their offset is held


def made(tmp_path_factory):
    if not _made:
        base = tmp_path_factory.mktemp("timed")
        folder = str(base / "cases")
        e0c.cases(folder, n=8, seed_base=E0.GATE_SEED, pieces=2, timed_n=TRIALS)
        expected = e0c.expect_timed(folder)
        _made.update(folder=folder, expected=expected, base=base)
    return _made


def factory_for(tdir, polls_running=2):
    """The stand-in for each generation in turn: handed the set the script will read from its file."""
    case = json.load(open(os.path.join(tdir, "timed.json"), encoding="utf-8"))
    blobs = iter([open(os.path.join(tdir, s["blob"]), "rb").read() for s in case["sets"]])
    made_ = []

    def factory():
        made_.append(ModelKernel(case["profile"], next(blobs), tuple(case["sigma"]), polls_running=polls_running))
        return made_[-1]
    return factory, made_


def run_once(tmp_path_factory):
    """One run of the ten over the stand-in, kept for the tests that change its output in a copy."""
    m = made(tmp_path_factory)
    if "out" not in m:
        tdir = os.path.join(m["folder"], "timed")
        factory, _k = factory_for(tdir)
        out = str(m["base"] / "once")
        with contextlib.redirect_stdout(io.StringIO()):
            assert timed.main(["--cases", tdir, "--out", out, "--polls", "50"], factory=factory) == 0
        m["out"] = out
    return m


def test_e0c_control_timed_judge_fails_on_each_of_its_conditions(tmp_path_factory, tmp_path):
    """timed-judge passes only when every generation ended done, there are as many generations as sets, and each
    generation's records and both counts are the model's. Each is broken alone, in a copy of a passing run's
    timed.json, its records' SHA-256s left the model's, and each must FAIL."""
    m = run_once(tmp_path_factory)
    good = json.load(open(os.path.join(m["out"], "timed.json"), encoding="utf-8"))

    def judged(change):
        t = json.loads(json.dumps(good))
        change(t)
        d = tmp_path / change.__name__
        d.mkdir()
        (d / "timed.json").write_text(json.dumps(t), encoding="utf-8")
        lines = []
        return e0c.timed_judge(m["folder"], str(d), out=lines.append), lines

    def nothing(t):
        pass

    def not_done(t):
        t["generations"][3]["end"] = "deadline"

    def one_fewer(t):
        del t["generations"][-1]

    def one_more(t):
        t["generations"].append(dict(t["generations"][-1]))

    def found_off(t):
        t["generations"][6]["found"] += 1

    def noise_off(t):
        t["generations"][6]["noise_crossings"] += 1

    def records_off(t):
        t["generations"][6]["records_sha256"] = "0" * 64

    assert judged(nothing)[0] == 0
    for change in (not_done, one_fewer, one_more, found_off, noise_off, records_off):
        code, lines = judged(change)
        assert code == 1 and lines[-1] == "== E0C TIMED VERDICT: FAIL", change.__name__


def test_e0c_control_timed_score_refuses_a_record_read_at_another_index():
    case = {"trials": 2, "first_index": 64, "spacing": 128, "offsets": {"at": 63, "noise": -1}}
    recs = [{"index": i, "epoch": 0, "flags": 0, "score": 0} for i in range(3 * 128)]
    assert timed.score(recs, case, 10) == (0, 0)
    recs[64 + 128 + 63] = dict(recs[64 + 128 + 63], index=64 + 128 + 64)
    with pytest.raises(Refusal) as e:
        timed.score(recs, case, 10)
    assert e.value.name == "RECORD_ORDER"


def test_e0c_the_ten_sets_are_the_stated_rule():
    assert e0c.timed_blob(9) == E0.facts(2)["blob"], "set 9 is E0's own matched filter"
    blobs = [e0c.timed_blob(g) for g in range(10)]
    assert len(set(blobs)) == 10


def test_e0c_bit_identity_ten_timed_generations_run_and_score_as_the_model_does(tmp_path_factory, tmp_path, capsys):
    m = made(tmp_path_factory)
    tdir = os.path.join(m["folder"], "timed")
    factory, kernels = factory_for(tdir)
    out = str(tmp_path / "out")
    assert timed.main(["--cases", tdir, "--out", out, "--launched-ns", "0", "--polls", "50"], factory=factory) == 0
    printed = capsys.readouterr().out
    assert printed.rstrip().split("\n")[-1].startswith("PASS e0c.timed: 10 generations")
    t = json.load(open(os.path.join(out, "timed.json"), encoding="utf-8"))
    assert len(t["generations"]) == 10 and len(kernels) == 10 and all(k.closed and k.runs == 1 for k in kernels)
    assert t["collector"] == "disabled" and t["frames"] == 128 * (TRIALS + 1) and t["trials"] == TRIALS
    assert sum(e["noise_crossings"] for e in m["expected"]) > 0 and sum(e["found"] for e in m["expected"]) > 0
    for g, (x, e) in enumerate(zip(t["generations"], m["expected"])):
        assert x["end"] == "done" and x["blob"] == "gen%d.blob" % g and x["collector"] == "disabled"
        assert set(x["parts_ns"]) == set(timed.SUM) and all(v >= 0 for v in x["parts_ns"].values())
        assert x["sum_ns"] == sum(x["parts_ns"][k] for k in timed.SUM)
        assert {"allocate", "fill", "run", "fetch", "status_reads"} <= set(x["trace_ns"])
        assert x["trace_ns"]["status_reads"] == 3, "running twice, then done: the stand-in's own count"
        assert (x["found"], x["noise_crossings"], x["records_sha256"]) == (e["found"], e["noise_crossings"], e["sha256"])
        frames = 128 * (TRIALS + 1)
        assert x["records"] == frames and os.path.getsize(os.path.join(out, "gen%d" % g, "records.bin")) == frames * 21
    assert t["total_ns"] == sum(x["sum_ns"] for x in t["generations"])
    assert len(set(x["records_sha256"] for x in t["generations"])) == 10
    lines = []
    assert e0c.timed_judge(m["folder"], out, out=lines.append) == 0
    assert sum(1 for x in lines if "IDENTICAL" in x and "EQUAL" in x) == 10 and "generations an hour" in lines[-2]
    print("\n".join(lines))


def test_e0c_control_a_generation_that_ran_another_set_is_reported(tmp_path_factory, tmp_path):
    m = made(tmp_path_factory)
    folder = str(tmp_path / "cases")
    shutil.copytree(m["folder"], folder)
    tdir = os.path.join(folder, "timed")
    a, b = os.path.join(tdir, "gen3.blob"), os.path.join(tdir, "gen4.blob")
    os.rename(a, a + ".x")
    os.rename(b, a)
    os.rename(a + ".x", b)
    factory, _k = factory_for(tdir)
    out = str(tmp_path / "out")
    assert timed.main(["--cases", tdir, "--out", out, "--polls", "50"], factory=factory) == 0
    lines = []
    assert e0c.timed_judge(folder, out, out=lines.append) == 1
    named = [x for x in lines if "DIFFERENT" in x]
    print("CONTROL e0c timed, sets 3 and 4 exchanged:\n" + "\n".join(named))
    assert [x.split()[1] for x in named] == ["3", "4"]      # by its records; at 10 trials the counts may agree
    assert lines[-1] == "== E0C TIMED VERDICT: FAIL"


def test_e0c_a_generation_that_does_not_end_done_stops_the_ten(tmp_path_factory, tmp_path, capsys):
    m = made(tmp_path_factory)
    tdir = os.path.join(m["folder"], "timed")
    factory, kernels = factory_for(tdir, polls_running=10 ** 6)       # never says done within the polls
    out = str(tmp_path / "out")
    assert timed.main(["--cases", tdir, "--out", out, "--polls", "5"], factory=factory) == 1
    assert capsys.readouterr().out.rstrip().split("\n")[-1] == "STOPPED e0c.timed: generation 0 ended deadline; 1 of 10 ran"
    t = json.load(open(os.path.join(out, "timed.json"), encoding="utf-8"))
    (x,) = t["generations"]
    assert x["end"] == "deadline" and "sum_ns" not in x and "reset" in x and len(kernels) == 1 and kernels[0].closed
    assert t["spec_sha256"] == C.SPEC_SHA256

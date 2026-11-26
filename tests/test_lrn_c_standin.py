"""LRN-C: the model's run of a placed script, and the stand-in for the card, each held to `model.run.learning`.

WHAT THIS HOLDS:
  - `hw.lrnc.windows.run_script`, the loop `expect` runs (records to a sink, a clear reading the fabric's latch),
    gives `model.run.learning`'s records, outcomes, counts, status and sets on the three cases at M = 1,024, the
    clears aside (they are not the model's operations);
  - the stand-in, driven by host.run_case through the library, lands every operation inside its window and
    gives the canonical run's records and registers, at a stride of 1 frame a poll and of 37;
  - the stand-in's own checks: a truth record not the case's, a stream that reaches a record the library has not
    written, core words that are not the blob's, a shadow that is no blob it was handed: each AssertionError;
  - THE NAMED CONTROL 5: a stand-in whose learner reads a truth record's amplitude, or its pulse id, on a stream
    made for it (records of amplitude 0, and one of `e1`), gives records the model's up to the first commit and
    different after it, and other counts: the judge FAILs it. On the case's own stream, amplitude 1/1 and one
    pulse, neither is seen (docs/host/lrn-c.md, limit 5): the test shows that too.
"""
import json
import os

import pytest

from spec import constants as C
from model import learner as ML
from model import records as MR
from model import run as MRUN
from model import source

from host import library as L, ops
from hw.lrnc import lrnc, standin

M = 1024
F = C.LEARN_UPDATE_FRAMES


def info_of(name, m=M):
    info = lrnc.case(name, m)
    info["blobs"] = {"blank.blob": lrnc.blank_blob(), "matched.blob": lrnc.matched_blob()}
    return info


@pytest.mark.parametrize("name", lrnc.CASES)
def test_lrn_c_the_placed_scripts_run_is_model_run_learnings(name):
    info = info_of(name)
    placed = [op["after"] for op in info["script"]]
    mine = []
    got = lrnc.run_case_model(info, placed, mine.append)
    script = {}
    for op, at in zip(info["script"], placed):
        if op["op"] == "clear":
            continue
        argument = info["blobs"][op["blob"]] if op["op"] == "write_shadow" else op["arg"]
        script.setdefault(at, []).append((op["op"], argument))
    noise = source.Noise(info["profile"], info["seed"], info["sigma"][0], info["sigma"][1], info["frames"])
    records, _truth, outcomes, learner = MRUN.learning(noise, info["schedule"], info["frames"],
                                                       info["blobs"][info["blob"]], script, F, C.LEARN_COUNT_BITS)
    assert mine == [MR.pack("score", r) for r in records]
    assert [o for op, o in zip(info["script"], got["outcomes"]) if op["op"] != "clear"] == [o[3] for o in outcomes]
    assert got["learner"].counters() == learner.counters() and got["learner"].status() == learner.status()
    assert [u["blob"] for u in got["learner"].updates] == [u["blob"] for u in learner.updates]
    assert len(learner.updates) == {"flow": 1, "moved": 1, "rich": 3}[name]


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    base = tmp_path_factory.mktemp("lrnc_standin")
    cases_dir = lrnc.cases(str(base / "cases"), M)
    for name in lrnc.CASES:
        lrnc.expect(cases_dir, name)
    return str(base), cases_dir


def expected(cases_dir, name):
    with open(os.path.join(cases_dir, "expect", name, "expected.json"), encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("stride", [1, 37])
@pytest.mark.parametrize("name", lrnc.CASES)
def test_lrn_c_the_stand_in_lands_each_operation_inside_its_window_and_gives_the_canonical_run(folder, name, stride):
    base, cases_dir = folder
    out = os.path.join(base, "runs-%d" % stride, name)
    code, card = standin.run(cases_dir, name, out, stride=stride)
    assert code == 0
    e = expected(cases_dir, name)
    model_ops = [k for k, op in enumerate(e["script"]) if op["op"] != "clear"]
    assert len(card.landed) == len(model_ops)
    for (n, kind, _arg, name_got), k in zip(card.landed, model_ops):
        lo, hi = e["windows"][k]
        assert (lo is None or n >= lo) and (hi is None or n <= hi), (k, n, lo, hi)
        assert kind == e["script"][k]["op"] and name_got == e["outcomes"][k]
    with open(os.path.join(out, "records.bin"), "rb") as f:
        assert f.read() == open(os.path.join(cases_dir, "expect", name, "records.bin"), "rb").read()
    with open(os.path.join(out, "report.json"), encoding="utf-8") as f:
        end = json.load(f)["learner"]["end"]
    assert end["counts"] == e["end"]["counts"] and end["lrn_status"] == e["end"]["lrn_status"]
    assert end["lrn_update_at"] == 0 and end["lrn_refusal"] is None


def test_lrn_c_the_stand_ins_own_checks_each_raise(folder):
    _base, cases_dir = folder
    info, schedule, blobs = standin.read_case(os.path.join(cases_dir, "flow"))
    # A truth record that is not the case's: the denominator's write offers it.
    card = standin.LearnerCard("s16x1", blobs["blank.blob"], (1477, 1), schedule)
    pairs = L.truth_pairs(dict(schedule[0], amplitude_num=2))
    card.do(ops.WriteMany(tuple(pairs[:-1])))
    with pytest.raises(AssertionError, match="not the case's"):
        card.do(ops.Write(*pairs[-1]))
    # Core words that are not the blob's.
    card = standin.LearnerCard("s16x1", blobs["matched.blob"], (1477, 1), schedule)
    card.do(ops.Write(L.offset("configure"), 3))
    card.do(ops.Write(L.offset("shadow_data"), 1))
    with pytest.raises(AssertionError, match="not the blob's"):
        card.do(ops.Write(L.offset("start"), 0))
    # A shadow that is no blob it was handed.
    card = standin.LearnerCard("s16x1", blobs["blank.blob"], (1477, 1), schedule, shadow_blobs=[blobs["blank.blob"]])
    card.do(ops.Write(L.offset("shadow_begin"), 2))
    card.do(ops.Write(L.offset("shadow_data"), 5))
    with pytest.raises(AssertionError, match="no blob it was handed"):
        card.do(ops.Write(L.offset("shadow_data"), 6))


def test_lrn_c_the_stand_in_latches_as_the_fabric_does_a_held_back_shadow_once_a_write(folder):
    """learn.md section 3: a shadow write held back while an update is unfinished latches UPDATE_UNFINISHED for its
    begin and for each word, so refused and refused_again are both set before the library clears them; a held-back
    commit latches once, and counts lrn_early; the core's refusal reads 0 for either."""
    _base, cases_dir = folder
    info, schedule, blobs = standin.read_case(os.path.join(cases_dir, "flow"))
    card = standin.LearnerCard("s16x1", blobs["blank.blob"], (1477, 1), schedule, shadow_blobs=[blobs["blank.blob"]])
    lib = L.Library()
    from host.drive import run_by_calls
    run_by_calls(lib.load(blobs["blank.blob"]), card)
    run_by_calls(lib.start(info["seed"], json.load(open(os.path.join(cases_dir, "table.json"))), info["frames"],
                           schedule), card)
    run_by_calls(lib.lrn_update(2000), card)
    card.do(ops.WriteMany(tuple(lib._shadow_pairs(L.B.read(blobs["blank.blob"])))))
    bits = C.REGISTER_BITS["lrn_status"]
    status = card.do(ops.Read(L.offset("lrn_status")))
    assert status >> bits["refused"] & 1 and status >> bits["refused_again"] & 1 and status >> bits["named"] & 1
    assert card.latch == ["UPDATE_UNFINISHED"] * 66 and card.do(ops.Read(L.offset("refusal"))) == 0
    card.do(ops.Write(L.offset("lrn_refusal"), 0))
    card.do(ops.WriteMany(tuple(L.words_of("commit_at", 3000))))
    status = card.do(ops.Read(L.offset("lrn_status")))
    assert status >> bits["refused"] & 1 and not status >> bits["refused_again"] & 1
    assert card.learner.counters()["lrn_early"] == 1 and card.do(ops.Read(L.offset("refusal"))) == 0


def test_lrn_c_the_stand_in_refuses_a_stream_that_passes_a_record_the_library_has_not_written(folder):
    """A library that writes no truth while the run goes: the stream reaches the first record past `ahead`."""
    base, cases_dir = folder
    out = os.path.join(base, "late", "flow")
    argv = standin.argv_for(cases_dir, "flow", out) + ["--ahead", "1"]
    kept = L.Library.step

    def no_feeding(self):
        status = yield L.Read(L.offset("krn_status"))
        return status, self.run_state.sent
    L.Library.step = no_feeding
    try:
        code, _card = standin.run(cases_dir, "flow", out, argv=argv)
    finally:
        L.Library.step = kept
    assert code == 1
    with open(os.path.join(out, "report.json"), encoding="utf-8") as f:
        assert "before the library wrote the truth record" in json.load(f)["failed"]


# ------------------------------------------------------------------ the named control 5

class ReadsAmplitude(ML.Learner):
    """A learner that reads a truth record's amplitude: it takes no window of a record of amplitude 0."""

    @staticmethod
    def _read_indexes(truth):
        return ML.Learner._read_indexes([r for r in truth if r["amplitude_num"] != 0])


class ReadsPulse(ML.Learner):
    """A learner that reads a truth record's pulse id: it takes no window of a record that is not `e0`'s."""

    @staticmethod
    def _read_indexes(truth):
        return ML.Learner._read_indexes([r for r in truth if r["pulse_id"] == C.PULSE_IDS["e0"]])


def _made_for_it(base):
    """flow at M = 1,024 with every third record of amplitude 0 and record 5 an `e1`."""
    cases_dir = lrnc.cases(os.path.join(base, "cases"), M)
    path = os.path.join(cases_dir, "flow", "schedule.json")
    schedule = json.load(open(path, encoding="utf-8"))
    for t, r in enumerate(schedule):
        if t % 3 == 2:
            r["amplitude_num"] = 0
    schedule[5]["pulse_id"] = C.PULSE_IDS["e1"]
    json.dump(schedule, open(path, "w", encoding="utf-8"))
    for name in lrnc.CASES:
        lrnc.expect(cases_dir, name)
    return cases_dir


@pytest.mark.parametrize("learner_class", [ReadsAmplitude, ReadsPulse])
def test_lrn_c_control_a_stand_in_whose_learner_reads_amplitude_or_pulse_gives_other_records_after_the_commit(
        tmp_path, learner_class, capsys):
    cases_dir = _made_for_it(str(tmp_path))
    runs = os.path.join(str(tmp_path), "runs")
    for run_name, case_name in lrnc.RUNS:
        standin.run(cases_dir, case_name, os.path.join(runs, run_name),
                    learner_class=learner_class if run_name == "flow" else ML.Learner)
    capsys.readouterr()
    assert lrnc.compare(cases_dir, runs) == 1
    said = capsys.readouterr().out
    head = [line for line in said.splitlines() if line.startswith("== LRN-C RUN flow:")][0]
    assert "DIFFERENT" in head
    got = json.load(open(os.path.join(runs, "card-lrnc.json"), encoding="utf-8"))["runs"]["flow"]["first"]
    assert got["record"] >= 2 * M and got["field"] == "score", got      # the model's up to the commit, at 2M
    assert "flow registers at the end: NOT the model's" in said and "lrn_count1" in said
    assert "== LRN-C CARD VERDICT: FAIL" in said
    # The true learner on the same stream passes it: the case is fine, the learner is what is seen.
    standin.run(cases_dir, "flow", os.path.join(runs, "flow"))
    capsys.readouterr()
    assert lrnc.compare(cases_dir, runs) == 0


class DoesNothing(ML.Learner):
    """D0's learner gate's first fault: a learner that does nothing. It counts and judges as the model's does, and
    its updates finish made, but it writes no set into the shadow, so a commit swaps in the set already there."""

    def _make(self):
        kept = self.core.write_shadow
        self.core.write_shadow = lambda blob: None
        try:
            super()._make()
        finally:
            self.core.write_shadow = kept


def test_lrn_c_a_stand_in_whose_learner_does_nothing_gives_other_records_from_the_commit(folder, tmp_path, capsys):
    base, cases_dir = folder
    runs = str(tmp_path / "runs")
    for run_name, case_name in lrnc.RUNS:
        standin.run(cases_dir, case_name, os.path.join(runs, run_name),
                    learner_class=DoesNothing if run_name == "rich" else ML.Learner)
    capsys.readouterr()
    assert lrnc.compare(cases_dir, runs) == 1
    said = capsys.readouterr().out
    got = json.load(open(os.path.join(runs, "card-lrnc.json"), encoding="utf-8"))["runs"]["rich"]
    assert not got["identical"] and got["first"]["record"] == 4 * M and got["first"]["field"] == "score", got
    assert got["registers"], "its counts and status are the model's: only the records see it"


class RoundsAway(ML.Learner):
    """D0's learner gate's second fault: a learner that rounds half away from zero, not half to even."""

    def _quantise(self, d):
        peak = max(abs(x) for x in d)
        if peak == 0:
            return super()._quantise(d)
        out = []
        for x in d:
            q, r = divmod(abs(x) * C.COEFF_MAX, peak)
            q += 1 if 2 * r >= peak else 0
            out.append(q if x >= 0 else -q)
        return out


def test_lrn_c_ties_counts_where_the_two_roundings_can_differ_and_a_learner_rounding_away_is_seen_only_there(folder):
    """The limit, shown: on a difference of [262142, 1] the coefficient of 1 is exactly 0.5, half to even gives 0
    and half away 1, and `ties` counts it; on the three cases at M = 1,024 no update's set holds a tie, so a learner
    that rounds the other way gives the model's records there (docs/host/lrn-c.md, limit 15)."""
    from model import weights
    assert lrnc.ties([262142, 1]) == 1 and lrnc.ties([262142, 3]) == 1 and lrnc.ties([262142, 4]) == 0
    assert lrnc.ties([0, 0]) == 0
    assert list(weights.quantise([262142, 3])) == [131071, 2] == RoundsAway._quantise(None, [262142, 3])
    assert list(weights.quantise([262142, 1])) == [131071, 0]
    assert RoundsAway._quantise(None, [262142, 1]) == [131071, 1]
    base, cases_dir = folder
    for name in lrnc.CASES:
        assert [u["ties"] for u in expected(cases_dir, name)["updates"]] == [0] * {"flow": 1, "moved": 1, "rich": 3}[name]
        out = os.path.join(base, "rounds-away", name)
        assert standin.run(cases_dir, name, out, learner_class=RoundsAway)[0] == 0
        assert open(os.path.join(out, "records.bin"), "rb").read() == \
            open(os.path.join(cases_dir, "expect", name, "records.bin"), "rb").read()


def test_lrn_c_flow_and_moved_from_the_matched_filter_if_the_fabric_refuses_the_blank_set(tmp_path, capsys):
    """The lead's ruling, question 6: `cases --start matched`. The day then passes as it does from the blank set,
    and the records before the commit are the matched filter's, not 0."""
    capsys.readouterr()
    assert lrnc.short(str(tmp_path), start="matched", m=M) == 0
    assert "== LRN-C CONTROL moved: SEEN" in capsys.readouterr().out
    cases_dir = os.path.join(str(tmp_path), "cases")
    for name in ("flow", "moved"):
        assert json.load(open(os.path.join(cases_dir, name, "case.json"), encoding="utf-8"))["blob"] == "matched.blob"
    data = open(os.path.join(cases_dir, "expect", "flow", "records.bin"), "rb").read()
    from hw.e0c import pieces
    assert any(pieces.RECORD.unpack_from(data, r * 21)[3] for r in range(64, 2 * M))
    with pytest.raises(ValueError):
        lrnc.case("flow", M, start="zero")


@pytest.mark.parametrize("learner_class", [ReadsAmplitude, ReadsPulse])
def test_lrn_c_on_the_cases_own_stream_a_learner_reading_amplitude_or_pulse_is_not_seen(folder, learner_class):
    """The limit, shown: amplitude 1/1 and one pulse throughout, so such a learner is the model's."""
    base, cases_dir = folder
    out = os.path.join(base, "unseen-%s" % learner_class.__name__, "flow")
    assert standin.run(cases_dir, "flow", out, learner_class=learner_class)[0] == 0
    assert open(os.path.join(out, "records.bin"), "rb").read() == \
        open(os.path.join(cases_dir, "expect", "flow", "records.bin"), "rb").read()

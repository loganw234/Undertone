"""E1C: the card's side end to end, on a tiny plan, with a stand-in for the card that writes the model's own run.

The path is the box's: every run of order.txt through `hw/e0c/run_piece.py` -> `host.run_case.main`, unchanged, over
`hw/e1c/standin.py`'s CardModel (E0C's ModelKernel, which also takes the start epoch written and a swap at the
commit_at written), then records.bin -> `hw/e1c/e1c.py compare`, against `expect`'s hashes. The stand-in models no
block: this holds E1C's scripts and the library's reading of a buffer, not a kernel (docs/host/e1c.md).

THE TINY PLAN: stage E1's layout (tests/test_lrn_a_e1.py, `make_plan`) with 16 training trials, 72 calibration
blocks and 32 test trials, seed 2026112699: A = 2,048, B = 6,656, L = 10,752; pieces of 2,304, 2,304, 2,048 and 2,048
frames; the swap runs 4,096 frames, committed at 2,048. Its reference part is stage E1's own `measure` and `part_of`
on the same plan, the continuous stream with the hand-over at A. A part of 104 signal-free scores has one crossing at
a false-alarm probability of 0.01, below the statistics' floor of 100 (stats/recovery.py, MIN_CROSSINGS), so the
floor is set to 1 while a part is made here, for E1's `measure` and for E1C's `compare` alike: a size stand-in,
which the short form's test of `evaluate_card` (tests/test_e1c_judge.py) does not need.

The positive case: every run IDENTICAL; the card's part EQUAL to E1's own part of the same plan, key for key; the
blank swap run's records before A the desktop's blank run; both swaps SEEN; the flip SEEN at its predicted record;
the verdict PASS. The gate `swap`: each swap run is the model's run of its named schedule, the new set from the
named index. Its control, the brief's named control 4: a commit at another index than the named one differs from
the model's run of the named schedule, at that index's record, in the epoch field. The brief's named controls 2 and
3: a card record changed in one word is reported at that record, in each of its four fields and three kinds of
run; and the flipped set's run differs from the learned set's at the record the samples predict. Then: the learned
pieces loaded at epoch 0, the two sets exchanged, a commit after the core has passed the named index, a piece
missing or extra or seeded otherwise, and the verdict's conditions each broken alone, each failing as named.
"""
import json
import os
import shutil

import pytest

from spec import constants as C
from stats import recovery

import test_lrn_a_e1 as E1
from host import run_case
from hw.e0c import pieces as P0
from hw.e1c import e1c, standin
from hw.e1c.errors import E1CRefusal
from hw.e1c.standin import CardModel
from learn.errors import LearnRefusal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = E1.make_plan("e1c-tiny", "short", 16, 72, 32, 2026112699)
KEY, BLOCK = "t", 256
_made = {}


def committed_set():
    return {PLAN["name"]: dict(zip(("sha256", "records"), E1.independent_digest(E1.schedule_for(PLAN))))}


def stand_in(folder, r, out, **kw):
    """One run of order.txt through run_piece's path, the card a CardModel (hw/e1c/standin.py, `run`)."""
    code = standin.run(folder, r, out, **kw)
    assert run_case.Backend is not CardModel and run_case.Backend.__name__ == "Backend", "the backend put back"
    return code


def compared(folder, runs, **kw):
    lines = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(recovery, "MIN_CROSSINGS", 1)
        code, record = e1c.compare(folder, runs, references={KEY: made()["reference"]}, out=lines.append, **kw)
    return code, record, lines


def made():
    if not _made:
        base = os.path.join(_made_base[0], "e1c")
        folder, runs = os.path.join(base, "cases"), os.path.join(base, "runs")
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(recovery, "MIN_CROSSINGS", 1)
            reference = E1.part_of(E1.measure(PLAN, committed=committed_set()))
            order = e1c.cases(folder, plans={KEY: PLAN}, committed=committed_set(), references={KEY: reference},
                              swap_part=KEY)
            summary = e1c.expect_part(folder, KEY, block=BLOCK, out=lambda line: None)
        swaps = dict((w, e1c.expect_swap(folder, w, block=BLOCK)) for w in e1c.SWAPS)
        flip = e1c.expect_flip(folder, block=BLOCK)
        codes = dict((r["name"], stand_in(folder, r, os.path.join(runs, r["name"]))) for r in e1c.read_order(folder))
        _made.update(folder=folder, runs=runs, reference=reference, order=order, summary=summary, swaps=swaps,
                     flip=flip, codes=codes)
    return _made


_made_base = []


@pytest.fixture(scope="module")
def tiny(tmp_path_factory):
    if not _made_base:
        _made_base.append(str(tmp_path_factory.mktemp("e1c-tiny")))
    return made()


def copy_runs(tiny, tmp_path):
    runs = str(tmp_path / "runs")
    shutil.copytree(tiny["runs"], runs)
    return runs


def copy_cases(tiny, tmp_path):
    folder = str(tmp_path / "cases")
    shutil.copytree(tiny["folder"], folder)
    return folder


def by_name(tiny):
    return dict((r["name"], r) for r in e1c.read_order(tiny["folder"]))


# ------------------------------------------------------------------ the positive case

def test_e1c_the_tiny_plan_is_the_stated_layout():
    assert (PLAN["A"], PLAN["B"], PLAN["length"], PLAN["m"]) == (2048, 6656, 10752, 104)
    assert [(x.first, x.frames) for x in e1c.the_cut(PLAN)] == [(2048, 2304), (4352, 2304), (6656, 2048), (8704, 2048)]


def test_e1c_every_run_through_run_case_is_the_models_and_the_cards_part_is_e1s(tiny):
    assert set(tiny["codes"].values()) == {0} and len(tiny["codes"]) == 11
    assert [r[0] for r in tiny["order"]] == ["ct-p%d-learned" % q for q in range(4)] + \
        ["ct-p%d-matched" % q for q in range(4)] + ["swap-blank", "swap-matched", "flip-ct-p0"]
    s = tiny["summary"]
    assert s["mirror_equal"] and s["matched_identical_to_stats"] and e1c.differing(s["model_part"], tiny["reference"]) == []
    code, record, lines = compared(tiny["folder"], tiny["runs"])
    for line in lines:
        print(line)
    assert code == 0 and lines[-1].startswith("== E1 CARD VERDICT: PASS")
    assert sum("IDENTICAL: " in line for line in lines) == 10, "the eight pieces and the two swap runs"
    assert any(line.startswith("the flip control, flip-ct-p0: against the flipped set's own model run IDENTICAL")
               for line in lines)
    assert any("part t: EQUAL to its reference part, key for key" in line and "the card's swap-blank run" in line
               and "its records equal the desktop's blank run" in line for line in lines)
    assert record["parts"] == [tiny["reference"]] and record["verdict"] == "PASS"
    assert "== E1C FLIP CONTROL: SEEN, the flip reaches the records at the record predicted and the card ran the " \
        "flipped set" in lines
    on_disk = json.load(open(os.path.join(tiny["runs"], "card-e1.json"), encoding="utf-8"))
    assert on_disk["parts"] == record["parts"] and on_disk["spec_sha256"] == C.SPEC_SHA256


def test_gate_swap__e1c_each_swap_run_is_the_models_named_schedule_the_new_set_from_the_named_index(tiny):
    """Both swap runs, the blank set's (E1's own flow) and the matched filter's: IDENTICAL to the model's run of the
    named schedule; read from the card's bytes, every record before the named index at epoch 0 and every one from it
    at epoch 1; the blank run's records before it the desktop's blank run of the same frames, every score 0; the
    swap written before the named index by next_index's two reads."""
    order = by_name(tiny)
    for which in e1c.SWAPS:
        r = order["swap-%s" % which]
        assert tiny["codes"][r["name"]] == 0, "the host library loads the set and run_case runs to its PASS line"
        rep, data = e1c.compare_run(tiny["folder"], r, tiny["runs"], keep=True)
        assert rep["identity"]["identical"] and r["swap_at"] == PLAN["A"] == 2048 and rep["end"] == "pass"
        recs = list(P0.RECORD.iter_unpack(data))
        assert [x[1] for x in recs] == [0] * 2048 + [1] * 2048
        assert rep["swap"]["next_index_before"] < rep["swap"]["next_index_after"] < 2048
        if which == "blank":
            assert all(x[3] == 0 for x in recs[:2048]) and any(x[3] != 0 for x in recs[2048:])
            assert e1c.sha(data[:2048 * P0.RECORD_BYTES]) == tiny["summary"]["desktop"]["blank_records_sha256"]
        else:
            assert sum(x[3] != 0 for x in recs[:2048]) > 2000
    # from A + 63 on, the swap runs' records are the learned p0's from its local 63: both the learned set on the same frames
    rep, p0 = e1c.compare_run(tiny["folder"], order["ct-p0-learned"], tiny["runs"], keep=True)
    for which in e1c.SWAPS:
        _rep, data = e1c.compare_run(tiny["folder"], order["swap-%s" % which], tiny["runs"], keep=True)
        mine = [x[1:] for x in P0.RECORD.iter_unpack(data)][2048 + 63:]
        theirs = [x[1:] for x in P0.RECORD.iter_unpack(p0)][63:2048]
        assert mine == theirs


def test_control_swap__e1c_a_commit_at_another_index_differs_from_the_named_schedule(tiny, tmp_path):
    order = by_name(tiny)
    for which in e1c.SWAPS:
        r = order["swap-%s" % which]
        for at, record, card, model in ((2049, 2048, 0, 1), (2047, 2047, 1, 0)):
            out = str(tmp_path / ("%s-%d" % (which, at)))
            assert stand_in(tiny["folder"], r, out, swap_at=at) == 0
            exp = e1c.read_json(os.path.join(tiny["folder"], "expect", r["name"] + ".json"))
            got = P0.compare_blocks(e1c.read_bytes(os.path.join(out, "records.bin")), exp, e1c.remake(tiny["folder"], r))
            print("CONTROL swap %s committed at %d where %d was named: %s" % (which, at, r["swap_at"], json.dumps(got["first"])))
            assert not got["identical"] and got["first"] == {"record": record, "field": "epoch", "card": card, "model": model}


def test_e1c_a_commit_written_after_the_core_passed_the_named_index_is_refused_by_name(tiny, tmp_path, capsys):
    r = by_name(tiny)["swap-blank"]
    out = str(tmp_path / "late")
    code = stand_in(tiny["folder"], r, out, swap_after=3072, stride=512)
    said = capsys.readouterr().out
    assert code == 2 and "REFUSED host.run_case SWAP_INDEX" in said
    assert not os.path.exists(os.path.join(out, "records.bin")) or os.path.getsize(os.path.join(out, "records.bin")) == 0


def test_e1c_order_txt_is_what_the_box_script_reads(tiny):
    """Each line four fields, or seven for a swap, each path a file of the cases folder: box_e1.sh's `one` reads them
    so, and run_piece is handed each as it stands."""
    with open(os.path.join(tiny["folder"], "order.txt"), encoding="utf-8") as f:
        lines = f.read().split("\n")
    assert lines[-1] == "" and all(len(line.split(" ")) in (4, 7) for line in lines[:-1]) and len(lines) == 12
    for r in e1c.read_order(tiny["folder"]):
        assert os.path.isfile(os.path.join(tiny["folder"], r["case"], "piece.json"))
        assert os.path.isfile(os.path.join(tiny["folder"], r["case"], "schedule.json"))
        assert os.path.isfile(os.path.join(tiny["folder"], r["blob"]))
        assert os.path.isfile(os.path.join(tiny["folder"], "expect", r["name"] + ".json"))
        if "swap_blob" in r:
            assert os.path.isfile(os.path.join(tiny["folder"], r["swap_blob"])) and (r["swap_at"], r["swap_after"]) == (2048, 1024)
    assert lines[8] == "swap-blank swap-blank blank.blob 0 partt/learned.blob 2048 1024"


# ------------------------------------------------------------------ the brief's named controls 2 and 3

def _changed(data, record, field, by):
    vals = list(P0.RECORD.unpack_from(data, record * P0.RECORD_BYTES))
    i = P0.SCORE_FIELDS.index(field)
    vals[i] = vals[i] + by
    return data[:record * P0.RECORD_BYTES] + P0.RECORD.pack(*vals) + data[(record + 1) * P0.RECORD_BYTES:]


def test_e1c_control_a_card_record_changed_in_one_word_is_reported_at_that_record(tiny):
    order = by_name(tiny)
    for name, record in (("ct-p2-learned", 127), ("ct-p2-learned", 300), ("ct-p0-matched", 63), ("swap-blank", 2048),
                         ("swap-matched", 100)):
        r = order[name]
        exp = e1c.read_json(os.path.join(tiny["folder"], "expect", name + ".json"))
        data = e1c.read_bytes(os.path.join(tiny["runs"], name, "records.bin"))
        assert P0.compare_blocks(data, exp)["identical"]
        for field, by in (("index", 1), ("epoch", 1), ("flags", 2), ("score", -1)):
            got = P0.compare_blocks(_changed(data, record, field, by), exp, e1c.remake(tiny["folder"], r))
            want = P0.RECORD.unpack_from(data, record * P0.RECORD_BYTES)[P0.SCORE_FIELDS.index(field)]
            assert got["first"] == {"record": record, "field": field, "card": want + by, "model": want}, (name, field)
        print("CONTROL one word changed in %s, record %d: each of index, epoch, flags and score named there" % (name, record))
        for bad, at in ((data[:-P0.RECORD_BYTES], len(data) // P0.RECORD_BYTES - 1),
                        (data + data[-P0.RECORD_BYTES:], len(data) // P0.RECORD_BYTES), (data + b"\0", None)):
            got = P0.compare_blocks(bad, exp, e1c.remake(tiny["folder"], r))
            assert not got["identical"] and (at is None or got["first"]["record"] == at)


def test_e1c_control_one_coefficient_changed_differs_from_the_learned_sets_run_at_the_first_record_it_reaches(tiny):
    f = tiny["flip"]
    order = by_name(tiny)
    learned = e1c.read_json(os.path.join(tiny["folder"], "expect", "ct-p0-learned.json"))
    data = e1c.read_bytes(os.path.join(tiny["runs"], "flip-ct-p0", "records.bin"))
    got = P0.compare_blocks(data, learned, e1c.remake(tiny["folder"], order["ct-p0-learned"]))
    tap = f["flip"]["tap"]
    print("CONTROL the learned set with bit 12 of tap %d flipped (%d to %d): first %s; predicted %s"
          % (tap, f["flip"]["before"], f["flip"]["after"], json.dumps(got["first"]), f["predicted"]))
    assert f["predicted"]["record"] >= 63 - tap and got["first"]["record"] == f["predicted"]["record"]
    assert got["first"]["field"] == "score" and got["first"]["card"] - got["first"]["model"] == f["predicted"]["difference"]
    assert abs(f["predicted"]["difference"]) % 4096 == 0 and f["predicted"]["difference"] != 0
    # the flip is round 3's rule on the learned set: bit 12 of its first tap of the largest magnitude
    coeffs = tiny["reference"]["coefficients"]
    assert tap == max(range(64), key=lambda m: (abs(coeffs[m]), -m)) and f["flip"]["before"] == coeffs[tap]
    assert f["flip"]["after"] == f["flip"]["before"] ^ 4096 or f["flip"]["after"] == (f["flip"]["before"] ^ 4096) - (1 << C.COEFF_BITS)


def test_e1c_control_the_flip_is_seen_only_when_the_card_ran_the_flipped_set(tiny, tmp_path):
    order = by_name(tiny)
    for wrong in ("part%s/learned.blob" % KEY, "matched.blob"):
        runs = copy_runs(tiny, tmp_path / wrong.replace("/", "-"))
        shutil.rmtree(os.path.join(runs, "flip-ct-p0"))
        assert stand_in(tiny["folder"], order["flip-ct-p0"], os.path.join(runs, "flip-ct-p0"), blob=wrong) == 0
        code, _record, lines = compared(tiny["folder"], runs)
        assert code == 1 and "== E1C FLIP CONTROL: NOT AS IT MUST BE" in lines and lines[-1] == "== E1 CARD VERDICT: FAIL"


# ------------------------------------------------------------------ the runs a card could get wrong

def test_e1c_control_the_learned_pieces_loaded_at_epoch_0_are_not_e1s_part(tiny, tmp_path):
    runs = copy_runs(tiny, tmp_path)
    for q in range(4):
        r = by_name(tiny)["ct-p%d-learned" % q]
        shutil.rmtree(os.path.join(runs, r["name"]))
        assert stand_in(tiny["folder"], r, os.path.join(runs, r["name"]), epoch=0) == 0
    code, record, lines = compared(tiny["folder"], runs)
    assert code == 1 and sum(line.startswith("  ct-") and "DIFFERENT:" in line for line in lines) == 4
    differ = e1c.differing(record["parts"][0], tiny["reference"])
    print("CONTROL the learned pieces loaded at epoch 0: the part differs in %s" % differ)
    assert set(differ) == {"held_out_epochs", "threshold_epoch", "first_new_epoch_index"}


def test_e1c_control_the_two_sets_exchanged_for_one_piece_differ_at_its_first_records(tiny, tmp_path):
    runs = copy_runs(tiny, tmp_path)
    r = by_name(tiny)["ct-p1-matched"]
    shutil.rmtree(os.path.join(runs, r["name"]))
    assert stand_in(tiny["folder"], r, os.path.join(runs, r["name"]), blob="part%s/learned.blob" % KEY) == 0
    rep, _data = e1c.compare_run(tiny["folder"], r, runs)
    assert not rep["identity"]["identical"] and rep["identity"]["first"]["field"] == "score"
    assert rep["identity"]["first"]["record"] < 64
    code, record, lines = compared(tiny["folder"], runs)
    # On this plan the part need not move (a threshold of 104 scores at one crossing); the run's identity and the
    # statistics' digest of the baseline's reads see the exchange whether it moves or not.
    assert code == 1 and any("the card's baseline reads NOT equal to the statistics'" in line for line in lines)
    assert sum(line.startswith("  ct-") and "DIFFERENT:" in line for line in lines) == 1


def test_e1c_control_compare_refuses_pieces_that_are_not_the_stated_cut(tiny, tmp_path):
    def missing(folder):
        shutil.rmtree(os.path.join(folder, "partt", "p3"))

    def extra(folder):
        shutil.copytree(os.path.join(folder, "partt", "p3"), os.path.join(folder, "partt", "p4"))

    def seed(folder):
        path = os.path.join(folder, "partt", "p1", "piece.json")
        info = e1c.read_json(path)
        e1c.write_json(path, dict(info, seed=PLAN["seed"]))

    def first(folder):
        path = os.path.join(folder, "partt", "p2", "piece.json")
        info = e1c.read_json(path)
        e1c.write_json(path, dict(info, first=info["first"] + 64))

    for change in (missing, extra, seed, first):
        folder = copy_cases(tiny, tmp_path / change.__name__)
        change(folder)
        with pytest.raises(E1CRefusal) as e:
            compared(folder, tiny["runs"])
        assert e.value.name == "PIECE_SET", change.__name__


# ------------------------------------------------------------------ the verdict's conditions, each alone

def _rewrite_expectation(folder, name, data):
    path = os.path.join(folder, "expect", name + ".json")
    exp = e1c.read_json(path)
    whole, blocks = P0.block_hashes(data, exp["block"])
    e1c.write_json(path, dict(exp, sha256=whole, blocks=blocks))


def test_e1c_control_the_verdict_fails_on_each_of_its_conditions_alone(tiny, tmp_path):
    """Each change breaks one condition and leaves the others as they were; each FAILs, by the line that says why."""
    def identity(folder, runs):         # a matched record no read takes, changed: the run DIFFERENT, the part E1's
        path = os.path.join(runs, "ct-p0-matched", "records.bin")
        e1c.write_bytes(path, _changed(e1c.read_bytes(path), 10, "score", 1))
        return "DIFFERENT"

    def flags(folder, runs):            # a flag in that record, the model's expectation made to match it
        path = os.path.join(runs, "ct-p0-matched", "records.bin")
        data = _changed(e1c.read_bytes(path), 10, "flags", 2)
        e1c.write_bytes(path, data)
        _rewrite_expectation(folder, "ct-p0-matched", data)
        return "flags 2"

    def stats(folder, runs):            # the statistics' baseline reads another digest
        path = os.path.join(folder, "expect", "part%s.json" % KEY)
        s = e1c.read_json(path)
        s["stats"]["matched_reads_sha256"] = "0" * 64
        e1c.write_json(path, s)
        return "NOT equal to the statistics'"

    def reference(folder, runs):        # the reference part one count away
        return "DIFFERS from its reference part in found"

    def blank(folder, runs):            # the desktop's blank run of another hash
        path = os.path.join(folder, "expect", "part%s.json" % KEY)
        s = e1c.read_json(path)
        s["desktop"]["blank_records_sha256"] = "0" * 64
        e1c.write_json(path, s)
        return "its records are NOT the desktop's blank run"

    def swap_index(folder, runs):       # the swap's report says the core had passed the named index
        path = os.path.join(runs, "swap-matched", "report.json")
        rep = e1c.read_json(path)
        rep["swap"]["next_index_after"] = 2048
        e1c.write_json(path, rep)
        return "== E1C SWAP matched: IDENTICAL; the first record of the new epoch at 2048, the named index 2048; " \
            "the swap bracketed by next_index [%d, 2048]; NOT AS IT MUST BE" % rep["swap"]["next_index_before"]

    def swap_epoch(folder, runs):       # the expectation's first new epoch elsewhere
        path = os.path.join(folder, "expect", "swap-blank.json")
        e1c.write_json(path, dict(e1c.read_json(path), first_new_epoch_index=2049))
        return "== E1C SWAP blank: IDENTICAL; the first record of the new epoch at 2048, the named index 2048; the " \
            "swap bracketed by next_index [1280, 1536]; NOT AS IT MUST BE"

    def flip(folder, runs):             # the flip's prediction one record later
        path = os.path.join(folder, "expect", "flip-ct-p0.json")
        exp = e1c.read_json(path)
        exp["predicted"]["record"] += 1
        e1c.write_json(path, exp)
        return "== E1C FLIP CONTROL: NOT AS IT MUST BE"

    def flip_difference(folder, runs):  # the flip's predicted difference not the one the records show
        path = os.path.join(folder, "expect", "flip-ct-p0.json")
        exp = e1c.read_json(path)
        exp["predicted"]["difference"] += 1
        e1c.write_json(path, exp)
        return "== E1C FLIP CONTROL: NOT AS IT MUST BE"

    def flip_same(folder, runs):        # a "flip" that changed nothing: its run and its expectation the learned set's
        shutil.copyfile(os.path.join(runs, "ct-p0-learned", "records.bin"), os.path.join(runs, "flip-ct-p0", "records.bin"))
        path = os.path.join(folder, "expect", "flip-ct-p0.json")
        learned = e1c.read_json(os.path.join(folder, "expect", "ct-p0-learned.json"))
        exp = e1c.read_json(path)
        e1c.write_json(path, dict(exp, sha256=learned["sha256"], blocks=learned["blocks"]))
        return "against the flipped set's own model run IDENTICAL; against the learned set's IDENTICAL"

    def swap_identity(folder, runs):    # one record of the swap run after the commit changed
        path = os.path.join(runs, "swap-matched", "records.bin")
        e1c.write_bytes(path, _changed(e1c.read_bytes(path), 3000, "score", 1))
        return "== E1C SWAP matched: DIFFERENT"

    def swap_flags(folder, runs):       # a flag in the swap run, the expectation made to match it
        path = os.path.join(runs, "swap-blank", "records.bin")
        data = _changed(e1c.read_bytes(path), 3000, "flags", 2)       # after the commit: not the blank stretch's
        e1c.write_bytes(path, data)
        _rewrite_expectation(folder, "swap-blank", data)
        return "== E1C SWAP blank: IDENTICAL; the first record of the new epoch at 2048, the named index 2048; the " \
            "swap bracketed by next_index [1280, 1536]; NOT AS IT MUST BE"

    def missing(folder, runs):          # one run's records not there
        os.remove(os.path.join(runs, "ct-p3-matched", "records.bin"))
        return "part t: NOT MADE"

    for change in (identity, flags, stats, reference, blank, swap_index, swap_epoch, flip, flip_difference, flip_same,
                   swap_identity, swap_flags, missing):
        folder = copy_cases(tiny, tmp_path / change.__name__)
        runs = copy_runs(tiny, tmp_path / change.__name__)
        said = change(folder, runs)
        references = {KEY: dict(tiny["reference"], found=tiny["reference"]["found"] + 1)} if change is reference else None
        lines = []
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(recovery, "MIN_CROSSINGS", 1)
            code, _record = e1c.compare(folder, runs, references=references or {KEY: tiny["reference"]}, out=lines.append)
        assert code == 1 and lines[-1] == "== E1 CARD VERDICT: FAIL", change.__name__
        assert any(said in line for line in lines), (change.__name__, said, lines)
        print("CONTROL the verdict, %s alone: FAIL, by %r" % (change.__name__, next(x for x in lines if said in x)[:110]))


# ------------------------------------------------------------------ the other checks of the desktop's side

def test_e1c_expect_refuses_a_learned_set_that_is_not_the_one_trained_again(tiny, tmp_path):
    folder = copy_cases(tiny, tmp_path)
    blob = os.path.join(folder, "part%s" % KEY, "learned.blob")
    flipped, _where = P0.flipped(e1c.read_bytes(blob))
    e1c.write_bytes(blob, flipped)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(recovery, "MIN_CROSSINGS", 1)
        with pytest.raises(E1CRefusal) as e:
            e1c.expect_part(folder, KEY, block=BLOCK, out=lambda line: None)
    assert e.value.name == "LEARNED_SET"


def test_e1c_a_swap_run_is_e1s_wiring_from_epoch_0_and_must_fit_before_the_test_stretch(tiny, tmp_path):
    r = dict(by_name(tiny)["swap-matched"], epoch=1)
    with pytest.raises(ValueError):
        list(e1c.run_records(tiny["folder"], r))
    long_a = E1.make_plan("e1c-long-a", "short", 64, 72, 32, 2026112698)      # A = 8,192 > B - A = 4,608
    assert 2 * long_a["A"] > long_a["B"]
    with pytest.raises(E1CRefusal) as e:
        e1c.cases(str(tmp_path / "long"), plans={KEY: long_a}, references={}, swap_part=KEY)
    assert e.value.name == "PIECE_CUT" and not os.path.exists(str(tmp_path / "long"))
    with pytest.raises(E1CRefusal) as e:
        e1c.cases(str(tmp_path / "none"), plans={KEY: PLAN})
    assert e.value.name == "LEARNED_SET", "a plan that is not E1's six needs its reference parts"


def test_e1c_cases_refuses_another_injection_set_another_trained_set_and_schedules_that_do_not_join(tiny, tmp_path,
                                                                                                   monkeypatch):
    """The three checks `cases` makes before it writes a case, each taken by itself: rule 1's digest (E1's own
    `check_injection_set`), the trained set against its reference, and the pieces' schedules joined back."""
    wrong = {PLAN["name"]: dict(committed_set()[PLAN["name"]], sha256="0" * 64)}
    with pytest.raises(LearnRefusal) as e:
        e1c.cases(str(tmp_path / "a"), plans={KEY: PLAN}, committed=wrong, references={KEY: tiny["reference"]}, swap_part=KEY)
    assert e.value.name == "INJECTION_SET"
    other = dict(tiny["reference"], coefficients=list(reversed(tiny["reference"]["coefficients"])))
    with pytest.raises(E1CRefusal) as e:
        e1c.cases(str(tmp_path / "b"), plans={KEY: PLAN}, committed=committed_set(), references={KEY: other}, swap_part=KEY)
    assert e.value.name == "LEARNED_SET" and "coefficients" in str(e.value)
    kept = e1c.K.schedule_of
    monkeypatch.setattr(e1c.K, "schedule_of", lambda piece, held: kept(piece, held)[:-1])
    with pytest.raises(E1CRefusal) as e:
        e1c.cases(str(tmp_path / "c"), plans={KEY: PLAN}, committed=committed_set(), references={KEY: tiny["reference"]},
                  swap_part=KEY)
    assert e.value.name == "PIECE_SET"


def test_e1c_compare_holds_a_stated_part_to_e1s_own_plan(tmp_path):
    folder = tmp_path / "cases"
    (folder / "part0").mkdir(parents=True)
    plan = E1.plan(0)
    e1c.write_json(str(folder / "part0" / "part.json"), {"key": 0, "plan": dict(plan, seed=plan["seed"] + 1), "pieces": 4})
    with pytest.raises(E1CRefusal) as e:
        e1c.check_set(str(folder), 0, True)
    assert e.value.name == "PIECE_SET" and "its plan is not stage E1's part 0" in str(e.value)
    e1c.write_json(str(folder / "part0" / "part.json"), {"key": 0, "plan": plan, "pieces": 4})
    with pytest.raises(E1CRefusal) as e:
        e1c.check_set(str(folder), 0, True)
    assert e.value.name == "PIECE_SET" and "pieces []" in str(e.value)

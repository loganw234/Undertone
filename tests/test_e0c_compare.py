"""E0C: the card's side end to end, on a short case, with a stand-in for the card that writes the model's own run.

The path is the box's: `hw/e0c/run_piece.py` -> `host.run_case.main`, unchanged, over `hw/e0c/kernel_model.py`'s
ModelKernel (host.fake's registers, filled at krn_start with the model's records of exactly what the library wrote),
then records.bin -> `hw/e0c/e0c.py`'s comparison, against `expect`'s hashes and counts. The stand-in models no
block: this holds the scripts and the library's reading of a buffer, not a kernel (docs/host/e0c.md).

These claim no gate row. D0's gate `bit identity` is held by the stage `rtl-benches` (tests/gates.toml, kind
"stage"), so no pytest test may claim it; and what is held here is E0C's scripts over a stand-in that models no
block, which is not that gate's claim. The positive case: every piece IDENTICAL, and the card's counts the model's.
The brief's named control: a card record changed in one word is reported at that record, with its field and both values, in each of
the record's four fields; and in both directions, one record missing and one extra, and a part of a record left
over. Round 3's flip control (amplitude 2's piece 0) is seen as on the card day. A set of pieces that is not the
stated cut is refused, PIECE_SET. At the stated scale, the judge passes card parts that are round 1's counts and
fails one count changed. And nothing the box runs imports from tests/ (the lead's ruling, 2026-11-25 12:27).

Short case: amplitude 2 (1/1), seed 2026112402 (the gate's), 24 trials, three pieces of 8, 8 and 8 trials (1,024,
1,024 and 1,152 frames), blocks of 256 records so that the block search is used.
"""
import ast
import json
import os
import shutil
import sys

import pytest

import test_seam_e0 as E0
from spec import constants as C

from hw.e0c import e0c, pieces as P
from hw.e0c import run_piece
from hw.e0c.errors import E0CRefusal
from hw.e0c.kernel_model import ModelKernel

N, PIECES, BLOCK, K = 24, 3, 256, 2
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_made = {}


def run_on_stand_in(folder, case, blob_path, out, kernel_blob=None):
    """One piece through run_piece's path, the card a ModelKernel. Returns run_case's exit code."""
    info = json.load(open(os.path.join(case, "piece.json"), encoding="utf-8"))
    with open(kernel_blob or blob_path, "rb") as f:
        blob = f.read()
    from host import run_case
    argv = ["--xclbin", "stand-in", "--shim", "stand-in", "--blob", blob_path,
            "--table", os.path.join(folder, "e0", "table.json"), "--seed", str(info["seed"]),
            "--frames", str(info["frames"]), "--schedule", os.path.join(case, "schedule.json"), "--out", out,
            "--polls", "100"]
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(run_case, "Backend", lambda *a, **kw: ModelKernel(info["profile"], blob, tuple(info["sigma"])))
        return run_piece.main(argv)


def made(tmp_path_factory):
    if not _made:
        base = tmp_path_factory.mktemp("e0c")
        folder, runs = str(base / "cases"), str(base / "runs")
        e0c.cases(folder, n=N, seed_base=E0.GATE_SEED, pieces=PIECES, timed_n=10)
        summary = e0c.expect_amplitude(folder, K, block=BLOCK)
        flip_case = os.path.join(folder, "flip", "a%dp%d" % e0c.FLIP)
        e0c.expect_piece(flip_case, open(os.path.join(folder, "flip", "case.blob"), "rb").read(), BLOCK)
        codes = []
        for d in e0c.piece_dirs(folder, K):
            codes.append(run_on_stand_in(folder, d, os.path.join(folder, "e0", "case.blob"),
                                         os.path.join(runs, os.path.basename(d))))
        codes.append(run_on_stand_in(folder, flip_case, os.path.join(folder, "flip", "case.blob"),
                                     os.path.join(runs, "flip-a%dp%d" % e0c.FLIP)))
        _made.update(folder=folder, runs=runs, summary=summary, codes=codes)
    return _made


def test_e0c_bit_identity_the_cards_records_through_run_case_are_the_models(tmp_path_factory, capsys):
    m = made(tmp_path_factory)
    assert m["codes"] == [0, 0, 0, 0], "run_case printed its PASS line for every piece and the flip"
    assert "PASS host.run_case" in capsys.readouterr().out
    lines = []
    code, parts, reports = e0c.compare(m["folder"], m["runs"], n=N, seed_base=E0.GATE_SEED, pieces=PIECES,
                                       amplitudes=[K], out=lines.append)
    print("\n".join(lines))
    assert [r["case"] for r in reports] == ["a2p0", "a2p1", "a2p2"]
    assert all(r["identity"]["identical"] for r in reports)
    assert [r["identity"]["records"] for r in reports] == [1024, 1024, 1152]
    assert sum(1 for x in lines if "IDENTICAL" in x) == 3 and not any("DIFFERENT" in x for x in lines)
    # at 24 trials the statistics will not judge an efficiency, by name; that is the short case's only failure
    assert code == 1 and lines[-1] == "== E0 CARD VERDICT: FAIL"
    assert [x.split(":")[1].strip() for x in lines if "REFUSED by the statistics" in x] == ["TOLERANCE_UNDEFINED"]
    (p,) = parts
    s = m["summary"]
    assert (p["found"], p["noise_crossings"], p["real_found"], p["model_only"], p["real_only"], p["flags"]) == \
        (s["found"], s["noise_crossings"], s["real_found"], s["model_only"], s["real_only"], s["flags"])
    assert p["n"] == N and p["scores_identical_to_stats"] and s["scores_identical_to_stats"]
    assert (p["late_not_read"], p["late_read"]) == (PIECES - 1, N - PIECES + 1)
    assert p["stream_sha256"] == s["stream_sha256"]


def _changed(data, record, field, by):
    at = record * P.RECORD_BYTES
    v = list(P.RECORD.unpack_from(data, at))
    i = P.SCORE_FIELDS.index(field)
    v[i] = v[i] ^ 1 if field == "flags" else v[i] + by
    return data[:at] + P.RECORD.pack(*v) + data[at + P.RECORD_BYTES:]


def test_e0c_control_a_card_record_changed_in_one_word_is_reported_at_that_record(tmp_path_factory, tmp_path):
    m = made(tmp_path_factory)
    case = os.path.join(m["folder"], "e0", "a2p1")
    data = open(os.path.join(m["runs"], "a2p1", "records.bin"), "rb").read()
    out = tmp_path / "a2p1"
    out.mkdir()

    def compared(bytes_):
        (out / "records.bin").write_bytes(bytes_)
        return e0c.compare_piece(m["folder"], case, str(out))["identity"]

    assert compared(data)["identical"]
    for field, by in (("index", 1), ("epoch", 1), ("flags", 0), ("score", -1)):
        rep = compared(_changed(data, 300, field, by))
        print("CONTROL e0c one word, %s of record 300: %s" % (field, json.dumps(rep)))
        assert not rep["identical"] and rep["blocks_differ"] == 1
        assert rep["first"]["record"] == 300 and rep["first"]["field"] == field
        before = P.RECORD.unpack_from(data, 300 * P.RECORD_BYTES)[P.SCORE_FIELDS.index(field)]
        assert rep["first"]["model"] == before and rep["first"]["card"] != before
    # a flag the card raised is read from the card's own bytes, into its part's flags, and fails the verdict
    (out / "records.bin").write_bytes(_changed(data, 700, "flags", 0))
    assert e0c.compare_piece(m["folder"], case, str(out))["reads"]["flags"] == 1
    assert P.flags_seen(_changed(data, 5, "flags", 0)) == 1 and P.flags_seen(data) == 0
    # the first of two changes is the one named
    rep = compared(_changed(_changed(data, 900, "score", 5), 301, "score", 5))
    assert rep["first"]["record"] == 301 and rep["blocks_differ"] == 2
    # too few, too many, and a part of a record
    n = len(data) // P.RECORD_BYTES
    rep = compared(data[:-P.RECORD_BYTES])
    assert not rep["identical"] and rep["first"]["record"] == n - 1 and "ends" in rep["first"]["why"]
    rep = compared(data + data[-P.RECORD_BYTES:])
    assert not rep["identical"] and rep["first"]["record"] == n and rep["records"] == n + 1
    rep = compared(data + b"\0")
    assert not rep["identical"] and rep["trailing_bytes"] == 1 and rep["first"]["record"] == n


def test_e0c_the_flip_control_is_seen_and_a_card_that_ignored_the_flip_is_not(tmp_path_factory, tmp_path):
    m = made(tmp_path_factory)
    lines = []
    assert e0c.compare_flip(m["folder"], os.path.join(m["runs"], "flip-a2p0"), out=lines.append) == 0
    assert "SEEN" in lines[-1] and "DIFFERENT, first" in lines[0]
    # the control: a card that ran e0's blob for the flip's case
    flip_case = os.path.join(m["folder"], "flip", "a2p0")
    e0_blob = os.path.join(m["folder"], "e0", "case.blob")
    assert run_on_stand_in(m["folder"], flip_case, e0_blob, str(tmp_path / "ignored")) == 0
    lines = []
    assert e0c.compare_flip(m["folder"], str(tmp_path / "ignored"), out=lines.append) == 1
    assert "NOT AS IT MUST BE" in lines[-1]


def test_e0c_control_the_flip_is_seen_only_when_the_run_is_the_flips_and_the_flip_reaches_a_record(tmp_path_factory,
                                                                                                     tmp_path):
    """compare_flip's two conditions, each broken alone. (1) The run is not the flipped blob's own model run: a
    card that ran a third blob (bit 11 of the same tap flipped) differs from both expectations, and is not seen.
    (2) The flip reaches no record: with the flip's expectation made equal to e0's, a run of e0's blob is the flip's
    own model run and is not seen either."""
    m = made(tmp_path_factory)
    flip_case = os.path.join(m["folder"], "flip", "a2p0")
    third, _where = P.flipped(open(os.path.join(m["folder"], "e0", "case.blob"), "rb").read(), bit=11)
    third_path = tmp_path / "third.blob"
    third_path.write_bytes(third)
    assert run_on_stand_in(m["folder"], flip_case, str(third_path), str(tmp_path / "third")) == 0
    lines = []
    assert e0c.compare_flip(m["folder"], str(tmp_path / "third"), out=lines.append) == 1
    assert "own model run DIFFERENT; against e0's DIFFERENT" in lines[0] and "NOT AS IT MUST BE" in lines[-1]
    folder = str(tmp_path / "cases")
    shutil.copytree(m["folder"], folder)
    shutil.copy(os.path.join(folder, "e0", "a2p0", "expected.json"), os.path.join(folder, "flip", "a2p0", "expected.json"))
    shutil.copy(os.path.join(folder, "e0", "case.blob"), os.path.join(folder, "flip", "case.blob"))
    lines = []
    assert e0c.compare_flip(folder, os.path.join(m["runs"], "a2p0"), out=lines.append) == 1
    assert "own model run IDENTICAL; against e0's IDENTICAL" in lines[0] and "NOT AS IT MUST BE" in lines[-1]


def test_e0c_control_a_card_day_without_its_flip_run_fails(tmp_path_factory, tmp_path, monkeypatch):
    """With E0's own verdict PASS (compare stood in for, returning 0), the card day exits 1 when the flip's run
    folder is missing, and names it; with the flip's run there and seen, 0."""
    m = made(tmp_path_factory)
    monkeypatch.setattr(e0c, "compare", lambda *a, **kw: (0, [], []))
    runs = tmp_path / "runs"
    runs.mkdir()
    lines = []
    assert e0c.card_day(m["folder"], str(runs), out=lines.append) == 1
    assert lines[-1].startswith("== E0C FLIP CONTROL: NOT RUN: no run folder")
    shutil.copytree(os.path.join(m["runs"], "flip-a2p0"), str(runs / "flip-a2p0"))
    lines = []
    assert e0c.card_day(m["folder"], str(runs), out=lines.append) == 0
    assert lines[-1].startswith("== E0C FLIP CONTROL: SEEN")


def test_e0c_control_a_card_day_whose_e0_verdict_fails_fails_with_its_flip_seen(tmp_path_factory, tmp_path, monkeypatch):
    """The other way round from the test above: E0's verdict a FAIL (compare stood in for, returning 1) and the flip
    SEEN, the card day still exits 1. Its exit is 0 only when both pass."""
    m = made(tmp_path_factory)
    monkeypatch.setattr(e0c, "compare", lambda *a, **kw: (1, [], []))
    runs = tmp_path / "runs"
    runs.mkdir()
    shutil.copytree(os.path.join(m["runs"], "flip-a2p0"), str(runs / "flip-a2p0"))
    lines = []
    assert e0c.card_day(m["folder"], str(runs), out=lines.append) == 1
    assert lines[-1].startswith("== E0C FLIP CONTROL: SEEN")


def test_e0c_the_card_days_record_is_what_compare_judged(tmp_path_factory, tmp_path):
    """card_day over a real compare, not a stand-in: card-e0.json holds compare's own parts and the pieces' reports,
    as compare returns them, and the tree's definition hash. At 24 trials E0's verdict is a FAIL (the statistics
    refuse to judge, TOLERANCE_UNDEFINED), the flip is SEEN, and the card day exits 1."""
    m = made(tmp_path_factory)
    runs = str(tmp_path / "runs")
    shutil.copytree(m["runs"], runs)
    lines = []
    assert e0c.card_day(m["folder"], runs, n=N, seed_base=E0.GATE_SEED, pieces=PIECES, amplitudes=[K],
                        out=lines.append) == 1
    assert "== E0 CARD VERDICT: FAIL" in lines and lines[-1].startswith("== E0C FLIP CONTROL: SEEN")
    record = json.load(open(os.path.join(runs, "card-e0.json"), encoding="utf-8"))
    assert set(record) == {"parts", "pieces", "spec_sha256"} and record["spec_sha256"] == C.SPEC_SHA256
    code, parts, reports = e0c.compare(m["folder"], runs, n=N, seed_base=E0.GATE_SEED, pieces=PIECES, amplitudes=[K],
                                       out=lambda line: None)
    assert code == 1
    assert record["parts"] == json.loads(json.dumps(parts)) and record["pieces"] == json.loads(json.dumps(reports))
    assert [p["part"] for p in record["parts"]] == [K] and record["parts"][0]["n"] == N
    assert [r["case"] for r in record["pieces"]] == ["a2p0", "a2p1", "a2p2"]
    assert all(r["identity"]["identical"] and r["reads"]["trials"] == 8 for r in record["pieces"])
    assert e0c.stale(record) is None


def test_e0c_control_compare_refuses_pieces_that_are_not_the_stated_cut(tmp_path_factory, tmp_path):
    """compare itself holds the set of pieces (check_set), not only check_set's own test."""
    m = made(tmp_path_factory)
    for change in ("missing", "seed"):
        folder = str(tmp_path / change)
        shutil.copytree(m["folder"], folder)
        if change == "missing":
            shutil.rmtree(os.path.join(folder, "e0", "a2p1"))
        else:
            path = os.path.join(folder, "e0", "a2p2", "piece.json")
            info = json.load(open(path, encoding="utf-8"))
            e0c.write_json(path, dict(info, seed=info["base_seed"]))
        with pytest.raises(E0CRefusal) as e:
            e0c.compare(folder, m["runs"], n=N, seed_base=E0.GATE_SEED, pieces=PIECES, amplitudes=[K],
                        out=lambda line: None)
        assert e.value.name == "PIECE_SET", change


def test_e0c_pieces_that_are_not_the_stated_cut_are_refused_by_name(tmp_path_factory, tmp_path):
    m = made(tmp_path_factory)
    for change in ("missing", "seed", "extra"):
        folder = str(tmp_path / change)
        shutil.copytree(m["folder"], folder)
        if change == "missing":
            shutil.rmtree(os.path.join(folder, "e0", "a2p1"))
        elif change == "seed":
            path = os.path.join(folder, "e0", "a2p2", "piece.json")
            info = json.load(open(path, encoding="utf-8"))
            info["seed"] = info["base_seed"]
            e0c.write_json(path, info)
        else:
            shutil.copytree(os.path.join(folder, "e0", "a2p2"), os.path.join(folder, "e0", "a2p3"))
        with pytest.raises(E0CRefusal) as e:
            e0c.check_set(folder, K, N, E0.GATE_SEED, PIECES)
        assert e.value.name == "PIECE_SET", change
    assert len(e0c.check_set(m["folder"], K, N, E0.GATE_SEED, PIECES)) == PIECES


def test_e0c_the_cost_of_quantisation_is_counted_from_the_cards_hits_against_the_real_filters(tmp_path_factory,
                                                                                               tmp_path):
    """The short case's card and real filter agree on every trial, so a swap of model_only and real_only, or a
    count of the model's hits in place of the card's, would pass it. Here one trial's real hit is flipped in the
    expectation, each way: the card's part must move by exactly one, in the right fields."""
    m = made(tmp_path_factory)
    base = e0c.compare(m["folder"], m["runs"], n=N, seed_base=E0.GATE_SEED, pieces=PIECES, amplitudes=[K],
                       out=lambda line: None)[1][0]
    folder = str(tmp_path / "cases")
    shutil.copytree(m["folder"], folder)
    path = os.path.join(folder, "e0", "a2p1", "expected.json")
    exp = json.load(open(path, encoding="utf-8"))
    hits = e0c.unbitmap(exp["real"]["hits"], 8)
    hit, miss = hits.index(True), hits.index(False)
    for t, was in ((hit, True), (miss, False)):
        changed = list(hits)
        changed[t] = not was
        e0c.write_json(path, dict(exp, real=dict(exp["real"], hits=e0c._bitmap(changed))))
        p = e0c.compare(folder, m["runs"], n=N, seed_base=E0.GATE_SEED, pieces=PIECES, amplitudes=[K],
                        out=lambda line: None)[1][0]
        if was:     # the real filter now misses a trial the card found
            assert (p["real_found"], p["model_only"], p["real_only"]) == \
                (base["real_found"] - 1, base["model_only"] + 1, base["real_only"])
        else:       # the real filter now finds a trial the card missed
            assert (p["real_found"], p["model_only"], p["real_only"]) == \
                (base["real_found"] + 1, base["model_only"], base["real_only"] + 1)
        assert p["found"] == base["found"]


def test_e0c_a_crossing_is_strictly_above_the_threshold():
    assert P.count([10, 11, None, 9], 10) == (1, 3, 1)
    assert P.count([], 0) == (0, 0, 0)


def test_e0c_run_piece_turns_the_collector_off_before_run_case():
    tree = ast.parse(open(os.path.join(ROOT, "hw", "e0c", "run_piece.py"), encoding="utf-8").read())
    main_block = [n for n in tree.body if isinstance(n, ast.If) and "__main__" in ast.unparse(n.test)]
    assert len(main_block) == 1
    calls = [ast.unparse(n) for n in main_block[0].body]
    assert calls == ["gc.disable()", "sys.exit(main(sys.argv[1:]))"]


def _round1():
    return dict((k, json.load(open(os.path.join(e0c.ROUND1, "part%d.json" % k), encoding="utf-8"))) for k in range(5))


def _card_parts_as_round1():
    return [dict(r, spec_sha256=C.SPEC_SHA256, late_found=0, late_read=r["n"] - 3, late_not_read=3)
            for _k, r in sorted(_round1().items())]


def test_e0c_the_judge_at_the_stated_scale_passes_round_1s_counts():
    lines = []
    assert e0c.judge(_card_parts_as_round1(), [], _round1(), E0.not_as_stated, out=lines.append) == 0
    assert sum(1 for x in lines if "EQUAL to round 1's part" in x) == 5 and lines[-1].startswith("== E0 CARD VERDICT: PASS")
    assert sum(1 for x in lines if "INSIDE; noise" in x) == 5


def test_control_statistics__e0c_the_judge_fails_a_count_that_is_not_round_1s():
    for field, change in (("found", -1), ("noise_crossings", 1), ("stream_sha256", None), ("seed", 1)):
        parts = _card_parts_as_round1()
        if field == "found":
            parts[2]["found"] -= 1
            parts[2]["real_found"] -= 1      # the counts still add up: it is a count that differs
        elif field == "stream_sha256":
            parts[3]["stream_sha256"] = "0" * 64
        else:
            parts[1][field] += change
        lines = []
        assert e0c.judge(parts, [], _round1(), E0.not_as_stated, out=lines.append) == 1, field
        named = [x.split("DIFFERS from round 1 in ")[1].split(", ") for x in lines if "DIFFERS from round 1 in" in x]
        assert len(named) == 1 and field in named[0], (field, named)
        assert lines[-1] == "== E0 CARD VERDICT: FAIL"
    # and the tolerance on its own, with no round 1 record to compare: a count far from D8's, found or noise
    for field, change in (("found", -3000), ("noise_crossings", 1500)):
        parts = _card_parts_as_round1()
        parts[2][field] += change
        if field == "found":
            parts[2]["real_found"] += change
        lines = []
        assert e0c.judge(parts, [], None, None, out=lines.append) == 1, field
        (line,) = [x for x in lines if x.lstrip().startswith("1/1") and "efficiency" in x]
        assert ("OUTSIDE; noise" in line) == (field == "found") and line.endswith("OUTSIDE") == (field != "found")
    s = {"stream_sha256": _round1()[0]["stream_sha256"]}
    s.update((f, _round1()[0][f]) for f in e0c.SUMMARY_FIELDS if f != "stream_sha256")
    assert e0c.summary_against_round1(s, _round1()[0]) == []
    assert e0c.summary_against_round1(dict(s, found=s["found"] + 1), _round1()[0]) == ["found"]


def _identical_reports():
    return [{"case": "a%dp%d" % (k, p), "kind": "e0", "run": None,
             "identity": {"identical": True, "records": 6400000, "expected_records": 6400000, "blocks_differ": 0,
                          "first": None, "trailing_bytes": 0}} for k in range(5) for p in range(4)]


def test_e0c_control_the_judge_fails_on_each_of_its_conditions_alone():
    """Each condition of the card's PASS, broken alone, with round 1's record not given (so that its comparison
    cannot be what fails) and the counts round 1's (inside the tolerance): a flag raised; a score read that is not
    the statistics package's; a piece DIFFERENT; a part not as stated, with round 1's `not_as_stated` asked."""
    def run(change=None, as_stated=None):
        parts, reports = _card_parts_as_round1(), _identical_reports()
        if change:
            change(parts, reports)
        lines = []
        return e0c.judge(parts, reports, None, as_stated, out=lines.append), lines

    def flag(parts, reports):
        parts[2]["flags"] = 2

    def stats(parts, reports):
        parts[2]["scores_identical_to_stats"] = False

    def different(parts, reports):
        reports[9]["identity"] = dict(reports[9]["identity"], identical=False, blocks_differ=1,
                                      first={"record": 4097, "field": "score", "card": 1, "model": 0})

    def threshold(parts, reports):
        parts[2]["threshold"] += 1

    assert run()[0] == 0 and run(as_stated=E0.not_as_stated)[0] == 0
    for change, as_stated in ((flag, None), (stats, None), (different, None), (threshold, E0.not_as_stated)):
        code, lines = run(change, as_stated)
        assert code == 1 and lines[-1] == "== E0 CARD VERDICT: FAIL", change.__name__
    code, lines = run(different)
    assert sum(1 for x in lines if "DIFFERENT" in x) == 1 and sum(1 for x in lines if "IDENTICAL" in x) == 19


def test_e0c_a_card_record_names_its_definition_and_is_stale_by_name_once_it_moves():
    assert e0c.stale({"spec_sha256": C.SPEC_SHA256}) is None
    assert e0c.stale({"spec_sha256": "209d3009cd0ba3db510d2a102a05d45c862ac1ee9008aadc612daf2ab4ee066f"}) == "E0C-CARD-STALE"
    assert e0c.stale({}) == "E0C-CARD-STALE"


# ------------------------------------------------------------------ what the box runs imports nothing from tests/

BOX_SCRIPTS = ("hw/e0c/run_piece.py", "hw/e0c/timed.py")
BOX_PACKAGES = ("host", "model", "spec", "hw")


def imported(source_text):
    names = []
    for node in ast.walk(ast.parse(source_text)):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names += [node.module] + ["%s.%s" % (node.module, a.name) for a in node.names]
    return names


def module_file(name):
    parts = name.split(".")
    for path in (os.path.join(ROOT, *parts) + ".py", os.path.join(ROOT, *parts, "__init__.py")):
        if os.path.isfile(path):
            return path
    return None


def reached(start_files):
    """Every module name the files import, followed through the tree: (tree modules, others)."""
    tree, other, todo, seen = set(), set(), list(start_files), set()
    while todo:
        path = todo.pop()
        if path in seen:
            continue
        seen.add(path)
        for name in imported(open(path, encoding="utf-8").read()):
            top = name.split(".")[0]
            f = module_file(name)
            if f:
                tree.add(name)
                todo.append(f)
                parts = name.split(".")
                for i in range(1, len(parts)):     # the packages an import runs first: their __init__.py
                    init = module_file(".".join(parts[:i]))
                    if init:
                        tree.add(".".join(parts[:i]))
                        todo.append(init)
            elif top in BOX_PACKAGES and os.path.isdir(os.path.join(ROOT, top)):
                continue                  # a package of the tree imported for a name in it: its file is followed above
            else:
                other.add(top)
    return tree, other


def box_findings(start_files):
    tree, other = reached(start_files)
    bad = [n for n in tree if n.split(".")[0] not in BOX_PACKAGES or n.split(".")[0] == "tests"
           or n.startswith("hw.") and not n.startswith("hw.e0c.")]
    bad += [n for n in other if n not in sys.stdlib_module_names]
    bad += [n for n in tree | other if n.startswith("test")]
    return sorted(set(bad))


def test_e0c_nothing_the_box_runs_imports_from_tests_or_needs_more_than_the_standard_library():
    files = [os.path.join(ROOT, f) for f in BOX_SCRIPTS]
    assert box_findings(files) == []
    tree, _other = reached(files)
    assert "host.run_case" in tree and "host.backend_xrt" in tree
    assert not any(n.startswith("hw.e0c.e0c") or n.startswith("hw.e0c.pieces") or "kernel_model" in n for n in tree)
    # the shell script runs those two and Python's -c of json and sys alone
    text = open(os.path.join(ROOT, "hw", "e0c", "box_e0.sh"), encoding="utf-8").read()
    runs = [line.split("python3", 1)[1].split()[0] for line in text.split("\n")
            if "python3" in line and not line.lstrip().startswith("#")]
    assert sorted(set(runs)) == ["-c", "hw/e0c/run_piece.py", "hw/e0c/timed.py"]
    for line in text.split("\n"):
        if "python3 -c" in line:
            assert imported(line.split('"')[1]) == ["json", "sys"]


def test_e0c_the_box_check_sees_an_import_from_tests(tmp_path):
    planted = tmp_path / "planted.py"
    planted.write_text("import json\nimport test_seam_e0\nfrom hw.e0c import e0c\nimport numpy\n", encoding="utf-8")
    found = box_findings([str(planted)])
    assert {"test_seam_e0", "numpy", "stats"} <= set(found), found
    tree, _o = reached([str(planted)])
    assert "hw.e0c.e0c" in tree, "followed into the desktop's own file, whose imports of tests/ and stats/ are reported"
    only = tmp_path / "only.py"
    only.write_text("from hw.e0c import e0c\n", encoding="utf-8")
    assert {"test_seam_e0", "numpy", "stats"} <= set(box_findings([str(only)]))

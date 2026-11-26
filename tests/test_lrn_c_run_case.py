"""LRN-C: host.run_case's learner script, run end to end with the stand-in for the card in place of XRT.

WHAT THIS HOLDS:
  - a run with --learn writes its three files, its report's learner part (the caps, each operation with its
    bracket, outcome and times, the registers at the end), and its one PASS line last, which counts the
    operations and those refused by name;
  - a refused operation is its outcome and the run goes on to every record (rich: 7 of 13 refused by name);
  - an operation whose "after" is not reached within --polls rounds ends the run DEADLINE, exit 3;
  - a malformed script, and --learn with --swap-blob, are refused by argparse before the backend opens (exit 2,
    "error:" on stderr); a blob file that is not there raises Python's own error;
  - a kernel with no learner, and one whose learner is not the case's, end REFUSED LEARN_BOUND, exit 2, with
    nothing written before the refusal;
  - WITHOUT --learn the run's operations are those of round 3's path: open, reset, load, start, finish, records.
"""
import json
import os

import pytest

from spec import constants as C
from model import weights

from host import fake, library as L, ops, run_case
from host.drive import Host

from hw.lrnc import lrnc, standin

M = 1024


@pytest.fixture(scope="module")
def cases_dir(tmp_path_factory):
    return lrnc.cases(str(tmp_path_factory.mktemp("lrnc_run_case") / "cases"), M)


def report_of(out):
    with open(os.path.join(out, "report.json"), encoding="utf-8") as f:
        return json.load(f)


def log_of(out):
    with open(out + ".log", encoding="utf-8") as f:
        return f.read()


def test_lrn_c_a_learner_run_writes_its_files_its_learner_report_and_its_pass_line_last(cases_dir, tmp_path):
    out = str(tmp_path / "flow")
    code, _card = standin.run(cases_dir, "flow", out)
    assert code == 0
    assert sorted(os.listdir(out)) == ["records.bin", "report.json", "trace.json"]
    lines = log_of(out).strip().split("\n")
    assert lines[-1] == ("PASS host.run_case: 4096 records of 4096 frames written to %s; 2 learner operation(s), 0 "
                         "refused by name" % out)
    r = report_of(out)
    assert r["learner"]["caps"] == {"count_bits": 32, "update_frames": 256}
    first, second = r["learner"]["ops"]
    assert set(first) == {"k", "op", "after", "polls", "arg", "next_index_before", "outcome", "detail", "ns",
                          "next_index_after"}
    assert (first["op"], first["arg"], first["after"], first["outcome"]) == ("update", M, 0, None)
    assert (second["op"], second["arg"], second["after"]) == ("commit", 2 * M, M + 256 + 4)
    for op in (first, second):
        assert op["next_index_before"] <= op["next_index_after"] and op["ns"][0] <= op["ns"][1]
    assert second["next_index_before"] >= second["after"] and second["polls"] > 0
    assert r["learner"]["end"]["counts"]["lrn_made"] == 1 and r["run"]["records"] == 4096
    assert os.path.getsize(os.path.join(out, "records.bin")) == 4096 * 21


def test_lrn_c_a_refused_operation_is_its_outcome_and_the_run_goes_on(cases_dir, tmp_path):
    out = str(tmp_path / "rich")
    code, _card = standin.run(cases_dir, "rich", out)
    assert code == 0
    r = report_of(out)
    got = [o["outcome"] for o in r["learner"]["ops"]]
    assert got == [None, None, None, "UPDATE_UNFINISHED", "UPDATE_UNFINISHED", "UPDATE_UNFINISHED", None,
                   "SWAP_PENDING", "SWAP_PENDING", "SWAP_INDEX", "SWAP_INDEX", None, None]
    assert r["learner"]["ops"][1]["read"] == "QUANTISE_INPUT"
    assert "the learner UPDATE_UNFINISHED" in r["learner"]["ops"][3]["detail"]
    assert "the core SWAP_PENDING" in r["learner"]["ops"][8]["detail"]
    assert "the core SWAP_INDEX" in r["learner"]["ops"][9]["detail"]
    assert "the learner SWAP_INDEX" in r["learner"]["ops"][10]["detail"]
    assert r["run"]["records"] == 7 * M
    assert log_of(out).strip().split("\n")[-1].endswith("13 learner operation(s), 7 refused by name")


def test_lrn_c_an_after_not_reached_within_polls_ends_the_run_deadline(cases_dir, tmp_path):
    out = str(tmp_path / "flow")
    argv = standin.argv_for(cases_dir, "flow", out, polls=3)
    code, _card = standin.run(cases_dir, "flow", out, argv=argv)
    assert code == 3
    r = report_of(out)
    assert "operation 1 (commit) waited 3 rounds" in r["deadline"]
    assert [o["k"] for o in r["learner"]["ops"]] == [0]
    assert log_of(out).strip().split("\n")[-1].startswith("DEADLINE host.run_case")


BAD = [
    ({"op": "update", "arg": 5}, "keys"),
    ([{"op": "jump", "after": 0}], "is not a dict whose op"),
    ([{"op": "update", "arg": 5, "after": 0, "extra": 1}], "keys"),
    ([{"op": "update", "arg": "5", "after": 0}], "not an int"),
    ([{"op": "update", "arg": 5, "after": -1}], "after"),
    ([{"op": "update", "arg": 5, "after": 9}, {"op": "commit", "arg": 9, "after": 8}], "after"),
    ([{"op": "update", "arg": 5, "after": 4097}], "after"),
    ([{"op": "update", "arg": 5, "after": True}], "after"),
    ([{"op": "write_shadow", "blob": "../blank.blob", "after": 0}], "not a file's name"),
    ([{"op": "clear", "after": 0, "arg": 1}], "keys"),
    ("not a list", "a JSON list"),
]


@pytest.mark.parametrize("script, said", BAD)
def test_lrn_c_a_malformed_script_is_refused_by_argparse_before_the_backend_opens(cases_dir, tmp_path, capsys,
                                                                                  script, said):
    path = str(tmp_path / "script.json")
    json.dump(script if not isinstance(script, dict) else [script], open(path, "w", encoding="utf-8"))
    opened = []
    kept = run_case.Backend
    run_case.Backend = lambda *a, **kw: opened.append(1)
    try:
        with pytest.raises(SystemExit) as e:
            run_case.main(standin.argv_for(cases_dir, "flow", str(tmp_path / "out"), script=path))
    finally:
        run_case.Backend = kept
    assert e.value.code == 2 and opened == []
    err = capsys.readouterr().err
    assert "error: --learn" in err and said in err


def test_lrn_c_learn_with_swap_blob_is_refused_and_a_missing_blob_raises_pythons_own_error(cases_dir, tmp_path, capsys):
    argv = standin.argv_for(cases_dir, "flow", str(tmp_path / "out")) + ["--swap-blob", os.path.join(
        cases_dir, "flow", "blank.blob"), "--swap-at", "10"]
    with pytest.raises(SystemExit) as e:
        run_case.main(argv)
    assert e.value.code == 2 and "--learn and --swap-blob" in capsys.readouterr().err
    path = str(tmp_path / "s.json")
    json.dump([{"op": "write_shadow", "blob": "missing.blob", "after": 0}], open(path, "w", encoding="utf-8"))
    with pytest.raises(FileNotFoundError):
        run_case.main(standin.argv_for(cases_dir, "flow", str(tmp_path / "out"), script=path))


@pytest.mark.parametrize("caps, extra, said", [
    ({"count_bits": 0, "update_frames": 0}, [], "no learner answers at 0xD00 to 0xDFF"),
    ({"count_bits": 32, "update_frames": 16}, [], "needs update_frames 256; the build's is 16"),
    ({}, ["--count-bits", "31"], "needs count_bits 31; the build's is 32")])
def test_lrn_c_a_kernel_whose_learner_is_not_the_cases_is_refused_learn_bound_with_nothing_written(
        cases_dir, tmp_path, caps, extra, said):
    out = str(tmp_path / "flow")
    info, schedule, blobs = standin.read_case(os.path.join(cases_dir, "flow"))
    card = standin.LearnerCard(info["profile"], blobs[info["blob"]], info["sigma"], schedule,
                               count_bits=caps.get("count_bits", 32), update_frames=caps.get("update_frames", 256))
    kept = run_case.Backend
    run_case.Backend = lambda *a, **kw: card
    try:
        code = run_case.main(standin.argv_for(cases_dir, "flow", out) + extra)
    finally:
        run_case.Backend = kept
    assert code == 2
    r = report_of(out)
    assert r["refused"]["name"] == "LEARN_BOUND" and said in r["refused"]["detail"]
    written = [op for op in card.ops if isinstance(op, ops.EFFECTS)]
    assert written[0] == ops.Write(L.offset("krn_reset"), 1), "the first write is the reset after the refusal"


def test_lrn_c_without_learn_the_run_makes_round_3s_operations():
    """run_case on the scripted kernel against the same calls made by hand: the same operations, in order."""
    import tempfile
    blob = weights.matched_filter("s16x1", C.PULSES["e0"], (1,))
    schedule = [{"index": 70, "pulse_id": 0, "amplitude_num": 3, "amplitude_den": 1}]
    table = list(__import__("model.source", fromlist=["gaussian_table"]).gaussian_table(3, 1))
    with tempfile.TemporaryDirectory() as d:
        paths = {}
        for name, value in (("blob", blob), ("table", table), ("schedule", schedule)):
            paths[name] = os.path.join(d, name)
            if name == "blob":
                open(paths[name], "wb").write(value)
            else:
                json.dump(value, open(paths[name], "w", encoding="utf-8"))
        backend = fake.scripted_kernel("s16x1", polls_running=3)
        backend.memory_group = 0
        backend.close = lambda: None
        kept = run_case.Backend
        run_case.Backend = lambda *a, **kw: backend
        try:
            code = run_case.main(["--xclbin", "x", "--shim", "y", "--blob", paths["blob"], "--table", paths["table"],
                                  "--seed", "7", "--frames", "200", "--schedule", paths["schedule"],
                                  "--out", os.path.join(d, "out")])
        finally:
            run_case.Backend = kept
    assert code == 0
    by_hand = fake.scripted_kernel("s16x1", polls_running=3)
    host = Host(by_hand)
    host.open()
    host.reset()
    host.load(blob, epoch=0)
    host.start(7, table, 200, schedule)
    host.finish(10 ** 7)
    host.records()
    assert [ops.key(op) for op in backend.ops] == [ops.key(op) for op in by_hand.ops]

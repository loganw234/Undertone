"""The full run of stage E1 in software, held: its committed parts are still those parts, and the committed
verdict is what the tree's own judge says of them.

The run was the lead's, on 2026-11-23: six parts, about ten minutes of one core each, on seeds named before
the experiment was written (docs/studies/E1-software.md). The gate cannot make it again. What a reader has
is seven committed files under docs/studies/e1/: the six parts the run wrote, and what the judge printed
for them. If a part is changed afterwards, or the judge is, the page's figures no longer follow from the
tree, and nothing would notice.

So this test holds two things. Each part has the SHA-256 it had when the run ended; the judge's output
has the hash of the committed bytes, which are the run's with each line end made a line feed (the run's
own file was a redirect on Windows, and no committed file may hold a carriage return). And the judge of
the tree as it stands, `judge_parts` of tests/test_lrn_a_e1.py, run on the six committed parts, prints
the committed output, byte for byte, and returns 0: or, once the definition has changed, refuses them
for that reason alone (the second test's docstring).

This file is the lead's and is NOT named test_p0_*: it imports the parcel's script, and the control on the
tests keeps only the foundation's own files in its copies.

What it cannot see:
  - whether a part is what a run on its seed gives: no part is run here. A part with every figure changed
    in step, and both hashes changed with it, passes;
  - whether the run came after the seeds were named: no file carries that; the round's ledger does;
  - whether the judge is right: it holds that the judge has not changed what it says of these parts. The
    judge's own gates are the parcel's, in tests/test_lrn_a_e1.py.
"""
import contextlib
import hashlib
import io
import json
import os

import test_lrn_a_e1 as E1
from spec import constants as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.path.join(ROOT, "docs", "studies", "e1")
PARTS = ["c%d.json" % c for c in range(6)]
OUTPUT = "judge-output.txt"
# `sha256sum` of the committed files, taken by the lead when they were put in the tree. The six parts are
# the SECOND run's, made on the merged tree at 17:44 on 2026-11-23: the first run's, of 17:02, differ from
# them in one field of each part, the definition's hash, and in nothing else (docs/studies/E1-software.md).
SHA256 = {
    "c0.json": "ac9c19b0231b251c6596b94214cca1066e6453394f2c92de32b36ad89f6b6e93",
    "c1.json": "d3607488a7a63d702e15242c17e1757d4b2d265b8492a7a8e891e5a0c3f6abec",
    "c2.json": "c40ed4146d5a623bc4afb7986e2ea29d8dab01c56881c6d851e78558c43b713e",
    "c3.json": "1d3af08959d6b62586ff1ad90a235b41b31e5f0e4be379847d59f9e8e47b6b69",
    "c4.json": "5db21a201fdf667e3535887c60f352d54cac780f55a85f38fa7e6c973f02bc2a",
    "c5.json": "5ca7292674ebff07706d577aee0262b1047b16b02468766dff41445e701cb5e6",
    "judge-output.txt": "6691abfacb69aee9c02abfc2f4a705e0157b024e3acafacf23d58edaf6f80f0e",
}
VERDICT = "== E1 SOFTWARE VERDICT: PASS, the reported model is inside the tolerance of E0's efficiency"


def data(name):
    with open(os.path.join(FOLDER, name), "rb") as f:
        return f.read()


def judged(paths):
    """What the tree's judge prints for these parts, and what it returns."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = E1.judge_parts(list(paths))
    return out.getvalue(), code


def test_e1_full_run_the_seven_files_are_the_ones_the_run_left():
    assert sorted(SHA256) == sorted(PARTS + [OUTPUT]) and len(SHA256) == 7
    for name, want in SHA256.items():
        assert hashlib.sha256(data(name)).hexdigest() == want, "%s is not the file the full run left" % name
    assert sorted(n for n in os.listdir(FOLDER) if not n.startswith(".")) == sorted(SHA256)


def test_e1_full_run_the_trees_judge_says_of_the_committed_parts_what_the_committed_output_says():
    """Each part carries the hash of the definition it was run under, and the judge refuses a part of
    another definition: that is the judge's rule, not this test's. So there are two cases.

    The definition is the one the parts were run under: the judge prints the committed output, byte for
    byte, and returns 0. This is the case on the day the run was committed.

    The definition has changed since: the judge must refuse, and for that reason ALONE. Every line it
    prints is a line of the committed output but eight: the line that says the parts are the stated
    experiment, six lines naming the hash, one a part, and the verdict. Then the page's figures are
    those of an earlier definition, and the run is made again before it is claimed for the new one.
    The first run of 2026-11-23 met this at its merge, half an hour after it was made: it was run on the
    parcel's commit, and the branch it was merged into had a later definition.

    WHAT THIS CASE DOES NOT DO: say so where the gate's reader looks. The note below is printed only when
    pytest is asked for a passing test's output (-rA); the gate's line for the tests is the same in both
    cases."""
    committed = data(OUTPUT).decode("utf-8").rstrip("\n").split("\n")
    assert committed[-1] == VERDICT
    # The reported model is the one named before the run, and its count is the page's.
    assert "THE REPORTED MODEL, named before the run: part 5, 16384 truth records" in committed[-2]
    assert "49492 of 100000" in committed[-2] and "INSIDE" in committed[-2]
    parts = [json.loads(data(name)) for name in PARTS]
    assert [p["seed"] for p in parts] == [2026112500 + c for c in range(6)]
    run_under = set(p["spec_sha256"] for p in parts)
    assert len(run_under) == 1, "the six parts were not run under one definition"
    printed, code = judged(os.path.join(FOLDER, name) for name in PARTS)
    if run_under == {C.SPEC_SHA256}:
        assert code == 0
        assert printed.encode("utf-8") == data(OUTPUT), "the judge no longer prints the committed output for the committed parts"
        return
    lines = printed.rstrip("\n").split("\n")
    new = [line for line in lines if line not in committed]
    gone = [line for line in committed if line not in lines]
    print("NOTE the full run of E1 was made under another definition than this tree's; the judge refuses its parts, "
          "and for that alone")
    assert code != 0 and lines[-1] == "== E1 SOFTWARE VERDICT: FAIL"
    assert len([line for line in new if "spec_sha256 is" in line]) == 6 and len(new) == 8, new
    assert len(gone) == 2 and gone[-1] == VERDICT, gone


def test_e1_full_run_a_part_changed_by_one_count_is_seen_twice(tmp_path):
    """The control. The reported part with one injection fewer found: its hash is another, and the judge of
    the six no longer prints the committed output. And the six in another order are not the stated run."""
    part = json.loads(data("c5.json"))
    assert part["found"] == 49492
    part["found"] -= 1
    changed = json.dumps(part).encode("utf-8")
    assert hashlib.sha256(changed).hexdigest() != SHA256["c5.json"]
    paths = []
    for name in PARTS:
        p = tmp_path / name
        p.write_bytes(changed if name == "c5.json" else data(name))
        paths.append(str(p))
    printed, _code = judged(paths)
    assert printed.encode("utf-8") != data(OUTPUT)
    print("CONTROL the full run of E1, one count changed in the reported part: the judge's last line is %r"
          % printed.rstrip("\n").split("\n")[-1])
    five_only, code = judged(paths[:5])
    assert code != 0 and VERDICT not in five_only, "five parts are not the stated experiment"

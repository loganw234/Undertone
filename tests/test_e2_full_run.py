"""The full run of stage E2 in software, held: its committed part is still that part, and the committed verdict is
what the tree's own judge says of it.

The run was the lead's, on 2026-11-25: one part, about eight minutes of one core, on the seed and the injection set
fixed in parcel E2L's design before the run (docs/studies/E2-software.md). The gate cannot make it again. What a
reader has is two committed files under docs/studies/e2/: the part the run wrote, and what the judge printed for it.
If the part is changed afterwards, or the judge is, the page's figures no longer follow from the tree, and nothing
would notice.

So this test holds two things, as tests/test_e1_full_run.py does for stage E1. The part has the SHA-256 it had
when the run ended; the judge's output has the hash of the committed bytes, which are the run's with each line end
made a line feed (the run's own file was a redirect on Windows). And the judge of the tree as it stands,
`judge_parts` of tests/test_e2l_drift.py, run on the committed part, prints the committed output, byte for byte,
and returns 0: or, once the definition has changed, refuses the part for that reason alone, and then THIS TEST
SKIPS, by name, E2-RECORD-STALE. A skip is named and counted on the gate's verdict line, and fails the gate under
--require-all. The control changes one comment line of the definition and requires that skip.

This file is the lead's and is NOT named test_p0_*: it imports the parcel's script.

What it cannot see:
  - whether the part is what a run on its seed gives: no part is run here. A part with every figure changed in
    step, and both hashes changed with it, passes;
  - whether the run came after the seed and the injection set were fixed: no file carries that; the ledgers do;
  - whether the judge is right: it holds that the judge has not changed what it says of this part. The judge's
    own gates are the parcel's, in tests/test_e2l_drift.py.
"""
import contextlib
import hashlib
import io
import json
import os

import pytest

import test_e2l_drift as E2
from spec import constants as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.path.join(ROOT, "docs", "studies", "e2")
PART = "e2-part.json"
OUTPUT = "judge-output.txt"
# `sha256sum` of the committed files, taken by the lead when they were put in the tree, 2026-11-25: the part as
# the run wrote it on an export of 804c49c, under the definition with e1; the output with its line ends made LF.
# Restated by the lead on 2026-11-25, in round 5: the part is now the second run's, made on a git archive export of
# cbf2e77 from 23:07:32 that day under round 5's definition (85e63d4d...). It differs from the first's in the
# definition's hash alone; the first part's SHA-256 was 76f0871a.... The judge's output is unchanged.
SHA256 = {
    "e2-part.json": "4d62bfa907fbb6b1f80a13412ce9f9ca4a6d1a5c72d4050e26e8c7c69ab9bf67",
    "judge-output.txt": "aadec8909846ce63a1bde5ce6cd9c01c20cfbcca6e5a4dbc6b6e26acfadf9247",
}
VERDICT = "== E2 SOFTWARE VERDICT: PASS, each named model recovers events the frozen model misses"
FAIL = "== E2 SOFTWARE VERDICT: FAIL"
STATED = "  the parts against the experiment as this file states it: "
STALE = "E2-RECORD-STALE"


def data(name):
    with open(os.path.join(FOLDER, name), "rb") as f:
        return f.read()


def judged(paths):
    """What the tree's judge prints for these parts, and what it returns."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = E2.judge_parts(list(paths))
    return out.getvalue(), code


def test_e2_full_run_the_two_files_are_the_ones_the_run_left():
    for name, want in SHA256.items():
        assert hashlib.sha256(data(name)).hexdigest() == want, "%s is not the file the full run left" % name
    assert sorted(n for n in os.listdir(FOLDER) if not n.startswith(".")) == sorted(SHA256)
    for name in SHA256:
        assert bytes([13]) not in data(name), name


def the_committed_record_against(spec_sha256):
    """None when the part was run under `spec_sha256` and the tree's judge prints the committed output for it. The
    skip's reason when it was run under another and the judge refuses it for that alone. Fails on anything else."""
    committed = data(OUTPUT).decode("utf-8").rstrip("\n").split("\n")
    assert committed[-1] == VERDICT
    named = [line for line in committed if line.startswith("  THE REPORTED MODEL, named before the run")]
    assert len(named) == 2 and "adaptive model at g = 8" in named[0] and "reset model at g = 8" in named[1]
    assert "found 48796 of 100000" in named[0] and "found 48054 of 100000" in named[1]
    part = json.loads(data(PART))
    assert part["seed"] == 2026112700 and part["name"] == "full"
    printed, code = judged([os.path.join(FOLDER, PART)])
    if part["spec_sha256"] == spec_sha256:
        assert code == 0
        assert printed.encode("utf-8") == data(OUTPUT), "the judge no longer prints the committed output for the part"
        return None
    lines = printed.rstrip("\n").split("\n")
    new = [line for line in lines if line not in committed]
    gone = [line for line in committed if line not in lines]
    assert code != 0 and lines[-1] == FAIL, lines[-3:]
    # three lines new: the experiment not as stated, the one reason (the hash), and the FAIL; two gone
    assert len(new) == 3 and new[0] == STATED + "NOT AS STATED" and new[2] == FAIL, new
    assert new[1].startswith("    part full: spec_sha256 is '%s" % part["spec_sha256"][:8]), new
    assert gone == [STATED + "as stated", VERDICT], gone
    return ("%s: the full run of E2 was made under the definition %s..., and this tree's is %s...; the judge refuses "
            "its part for that alone, so docs/studies/E2-software.md's figures are an earlier definition's until the "
            "run is made again" % (STALE, part["spec_sha256"][:12], spec_sha256[:12]))


def test_e2_full_run_the_trees_judge_says_of_the_committed_part_what_the_committed_output_says():
    """The definition is the one the part was run under: the judge prints the committed output, byte for byte, and
    returns 0. The definition has changed since: the judge must refuse, for that reason ALONE, and this test then
    skips by name, E2-RECORD-STALE. The control is the test after the next."""
    reason = the_committed_record_against(C.SPEC_SHA256)
    if reason is not None:
        pytest.skip(reason)


def test_e2_full_run_a_part_changed_by_one_count_is_seen(tmp_path):
    """One injection fewer found by the reported adaptive model: the part's hash is another, and the judge no longer
    prints the committed output."""
    raw = data(PART)
    text = raw.decode("utf-8")
    assert text.count('"found": 48796') >= 1
    changed = text.replace('"found": 48796', '"found": 48795', 1).encode("utf-8")
    assert hashlib.sha256(changed).hexdigest() != SHA256[PART]
    p = tmp_path / PART
    p.write_bytes(changed)
    printed, _code = judged([str(p)])
    assert printed.encode("utf-8") != data(OUTPUT)
    print("CONTROL the full run of E2, one count changed: the judge's last line is %r"
          % printed.rstrip("\n").split("\n")[-1])


def test_e2_full_run_a_definition_changed_by_one_comment_line_makes_the_record_stale_by_name(monkeypatch):
    """The control of the skip. One comment line of the definition changed is another definition to the judge.
    Under that hash THE TEST ABOVE, called as it is, must skip, by the name E2-RECORD-STALE, and for the judge's
    refusal on the hash alone."""
    with open(os.path.join(ROOT, "spec", "undertone.toml"), "rb") as f:
        raw = f.read().replace(b"\r\n", b"\n")
    rows = raw.split(b"\n")
    at = next(i for i, row in enumerate(rows) if row.startswith(b"#"))
    rows[at] = rows[at] + b" (a comment changed by this test's control)"
    other = hashlib.sha256(b"\n".join(rows)).hexdigest()
    assert hashlib.sha256(raw).hexdigest() == C.SPEC_SHA256, "the hash is not taken as this control takes it"
    assert other != C.SPEC_SHA256
    monkeypatch.setattr(C, "SPEC_SHA256", other)
    with pytest.raises(pytest.skip.Exception) as skipped:
        test_e2_full_run_the_trees_judge_says_of_the_committed_part_what_the_committed_output_says()
    reason = str(skipped.value)
    assert reason.startswith(STALE + ":") and other[:12] in reason, reason
    print("CONTROL the full run of E2 under a definition with one comment line changed: %s" % reason[:120])

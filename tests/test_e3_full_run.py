"""The full run of stage E3 in software, held: its committed parts are still those parts, and the committed verdict is
what the tree's own judge says of them.

The run was the lead's, on 2026-11-25: four parts, one a station, about nine minutes each of one core, on the
recordings, the injection sets and the seeds fixed in parcel E3S's design and its walls before the run
(docs/studies/E3-software.md). The gate cannot make it again: the recordings are not in the tree. What a reader has is
five committed files under docs/studies/e3/run/: the four parts the run wrote, and what the judge printed for them.
If a part is changed afterwards, or the judge is, the page's figures no longer follow from the tree, and nothing
would notice.

So this test holds two things, as tests/test_e1_full_run.py and tests/test_e2_full_run.py do. Each part has the
SHA-256 it had when the run ended; the judge's output has the hash of the committed bytes, which are the run's with
each line end made a line feed. And the judge of the tree as it stands, `judge_parts` of tests/test_e3s_experiment.py,
run on the committed parts, prints the committed output, byte for byte, and returns 0: or, once the definition has
changed, refuses each part for that reason alone, and then THIS TEST SKIPS, by name, E3-RECORD-STALE. A skip is named
and counted on the gate's verdict line, and fails the gate under --require-all. The control changes one comment line
of the definition and requires that skip.

This file is the lead's and is NOT named test_p0_*: it imports the parcel's script.

What it cannot see:
  - whether a part is what a run on its recordings gives: no part is run here, and the recordings are not in the
    tree. A part with every figure changed in step, and its hash and the output's changed with it, passes;
  - whether the run came after the rule, the blocks and the injection sets were frozen: the walls' commits and the
    ledgers carry that, and E3S's own tests hold the freeze;
  - whether the judge is right: it holds that the judge has not changed what it says of these parts. The judge's own
    gates are the parcel's, in tests/test_e3s_empirical.py and tests/test_e3s_experiment.py.
"""
import contextlib
import hashlib
import io
import json
import os

import pytest

import test_e3s_experiment as E3
from spec import constants as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.path.join(ROOT, "docs", "studies", "e3", "run")
STATIONS = ("MPP", "CDM", "HDH", "SRN")
PARTS = ["e3-%s.json" % s for s in STATIONS]
OUTPUT = "judge-output.txt"
# `sha256sum` of the committed files, taken by the lead when they were put in the tree, 2026-11-25: the parts as the
# run wrote them on an export of fefe77b, under round 5's definition (85e63d4d...); the output with its line ends LF.
SHA256 = {
    "e3-MPP.json": "cc2fce35df1ab19c7590fb2de10c45a7ab9d8281ea1eeaf5e7f0e5929a315915",
    "e3-CDM.json": "45f59a2296a1659b1396c5cc9d25f9bc17c6002fe1650e5a1502cddb962ba291",
    "e3-HDH.json": "bc606cf10ff538eab6741ede59f592356da5aa7738b3de5cffa0d43f6fd969c7",
    "e3-SRN.json": "50da18270de2c2fb9d024ed6e452d5ea5fc68513b5598b914cac46cdaec4445e",
    "judge-output.txt": "98b25ed6a352c9d71b2e20d0f2e148228b47bfca4e0459d3740102b59c0497d2",
}
VERDICT = "== E3 SOFTWARE: the experiment held at every station"
NOT_HELD = "== E3 SOFTWARE: NOT HELD at every station"
READINGS = ("  THE REPORTED READINGS, the model named before the run at every station: "
            "MPP REACHES, CDM REACHES, HDH SHORT, SRN REACHES")
STALE = "E3-RECORD-STALE"


def data(name):
    with open(os.path.join(FOLDER, name), "rb") as f:
        return f.read()


def judged(paths):
    """What the tree's judge prints for these parts, and what it returns."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = E3.judge_parts(list(paths))
    return out.getvalue(), code


def test_e3_full_run_the_five_files_are_the_ones_the_run_left():
    for name, want in SHA256.items():
        assert hashlib.sha256(data(name)).hexdigest() == want, "%s is not the file the full run left" % name
    assert sorted(n for n in os.listdir(FOLDER) if not n.startswith(".")) == sorted(SHA256)
    for name in SHA256:
        assert bytes([13]) not in data(name), name


def the_committed_record_against(spec_sha256):
    """None when the parts were run under `spec_sha256` and the tree's judge prints the committed output for them. The
    skip's reason when they were run under another and the judge refuses each for that alone. Fails on anything else."""
    committed = data(OUTPUT).decode("utf-8").rstrip("\n").split("\n")
    assert committed[-1] == VERDICT and READINGS in committed
    parts = [json.loads(data(p)) for p in PARTS]
    assert [p["station"] for p in parts] == list(STATIONS)
    run_under = set(p["spec_sha256"] for p in parts)
    assert len(run_under) == 1, "the four parts were run under %d definitions" % len(run_under)
    under = run_under.pop()
    printed, code = judged([os.path.join(FOLDER, p) for p in PARTS])
    if under == spec_sha256:
        assert code == 0
        assert printed.encode("utf-8") == data(OUTPUT), "the judge no longer prints the committed output for the parts"
        return None
    lines = printed.rstrip("\n").split("\n")
    new = [line for line in lines if line not in committed]
    gone = [line for line in committed if line not in lines]
    assert code != 0 and lines[-1] == NOT_HELD, lines[-3:]
    headers = [line for line in committed if line.endswith("; held: yes")]
    assert len(headers) == 4
    # each station's header now NOT held, one reason a station (the hash), and the verdict NOT HELD; nothing else
    want_new = sorted([h[:-len("yes")] + "NO" for h in headers] +
                      ["    NOT AS STATED: part %s: spec_sha256 is %r, the experiment's is %r" % (s, under, spec_sha256)
                       for s in STATIONS] + [NOT_HELD])
    assert sorted(new) == want_new, new
    assert sorted(gone) == sorted(headers + [VERDICT]), gone
    return ("%s: the full run of E3 was made under the definition %s..., and this tree's is %s...; the judge refuses "
            "its parts for that alone, so docs/studies/E3-software.md's figures are an earlier definition's until the "
            "run is made again" % (STALE, under[:12], spec_sha256[:12]))


def test_e3_full_run_the_trees_judge_says_of_the_committed_parts_what_the_committed_output_says():
    """The definition is the one the parts were run under: the judge prints the committed output, byte for byte, and
    returns 0. The definition has changed since: the judge must refuse, for that reason ALONE, and this test then
    skips by name, E3-RECORD-STALE. The control is the test after the next."""
    reason = the_committed_record_against(C.SPEC_SHA256)
    if reason is not None:
        pytest.skip(reason)


def test_e3_full_run_a_part_changed_by_one_count_is_seen(tmp_path):
    """One injection fewer found by HDH's learner: the part's hash is another, and the judge no longer prints the
    committed output."""
    raw = data("e3-HDH.json")
    text = raw.decode("utf-8")
    assert text.count('"found": 11485') == 1
    changed = text.replace('"found": 11485', '"found": 11484', 1).encode("utf-8")
    assert hashlib.sha256(changed).hexdigest() != SHA256["e3-HDH.json"]
    paths = []
    for p in PARTS:
        q = tmp_path / p
        q.write_bytes(changed if p == "e3-HDH.json" else data(p))
        paths.append(str(q))
    printed, _code = judged(paths)
    assert printed.encode("utf-8") != data(OUTPUT)
    print("CONTROL the full run of E3, one count changed: the judge's last line is %r"
          % printed.rstrip("\n").split("\n")[-1])


def test_e3_full_run_a_definition_changed_by_one_comment_line_makes_the_record_stale_by_name(monkeypatch):
    """The control of the skip. One comment line of the definition changed is another definition to the judge.
    Under that hash THE TEST ABOVE, called as it is, must skip, by the name E3-RECORD-STALE, and for the judge's
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
        test_e3_full_run_the_trees_judge_says_of_the_committed_parts_what_the_committed_output_says()
    reason = str(skipped.value)
    assert reason.startswith(STALE + ":") and other[:12] in reason, reason
    print("CONTROL the full run of E3 under a definition with one comment line changed: %s" % reason[:120])

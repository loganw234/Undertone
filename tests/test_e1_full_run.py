"""The full run of stage E1 in software, held: its committed parts are still those parts, and the committed
verdict is what the tree's own judge says of them.

The run was the lead's, on 2026-11-23: six parts, about ten minutes of one core each, on seeds named before
the experiment was written (docs/studies/E1-software.md). The gate cannot make it again. Restated by the lead
on 2026-11-25: the committed parts are now a third run's, made on round 3's branch under the definition of
the kernel's block, the same as the second run's in every field but that definition's hash. Restated by the lead
again on 2026-11-25, in round 4: the committed parts are now a FOURTH run's, made on an export of 804c49c under the
definition with the pulse e1, the same as the third run's in every field but that definition's hash. What a reader has
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

import pytest

import test_lrn_a_e1 as E1
from spec import constants as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.path.join(ROOT, "docs", "studies", "e1")
PARTS = ["c%d.json" % c for c in range(6)]
OUTPUT = "judge-output.txt"
# `sha256sum` of the committed files, taken by the lead when they were put in the tree. The six parts are
# the THIRD run's, made on round 3's branch at 534bb13 from 08:16 on 2026-11-25, under the definition that
# added the kernel's block. The second run's, made on the merged tree at 17:44 on 2026-11-23, differ from
# them in one field of each part, the definition's hash, and in nothing else; so do the first run's, of
# 17:02 that day. The judge's output is the same for all three, byte for byte once its line ends are made
# line feeds (docs/studies/E1-software.md).
# Restated by the lead again on 2026-11-25, in round 4: the six parts are now the FOURTH run's, made on a git archive
# export of 804c49c from 14:52:06 that day, under the definition with the pulse e1. They differ from the third run's
# in one field of each part, the definition's hash, and in nothing else; the judge's output is unchanged. The third
# run's hashes were 462add11..., 5af8c98f..., 83429623..., 600bb529..., 4bba664f... and e5f259e4....
# Restated by the lead again on 2026-11-25, in round 5: the six parts are now the FIFTH run's, made on a git archive
# export of cbf2e77 from 23:07:31 that day, under round 5's definition with the learner's block (85e63d4d...). They
# differ from the fourth run's in one field of each part, the definition's hash, and in nothing else; the judge's
# output is unchanged. The fourth run's hashes were 25b71f3b..., 1161c388..., 8042d527..., 99cd8b20..., 3ea394c8...
# and e0b89858....
SHA256 = {
    "c0.json": "d1e0618c5afbeaf9d4ea7b53d3bfd383de2394228fcfd169a1a9154eca37b6c4",
    "c1.json": "f93012331d0c6c04379e5d187d6477ffce300642241e8f42a954b2bbd0dcfe96",
    "c2.json": "874b949ed82f9dd4f3c523ac76113a790688df23b7663a098106e6ba177369a6",
    "c3.json": "32f92c063f5992713e6428e45e7e66f4a45519ca52a295493cb8823882ac3b10",
    "c4.json": "b1a17fd9557659d5964569abef23ed83e81eec89587918dcb71f659b1ce8801c",
    "c5.json": "93b115af7cc6d187de95949e6b24ff7f5ef20b4e05e034a27a4d7a8f676a4e3e",
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


STALE = "E1-RECORD-STALE"


def test_e1_full_run_the_trees_judge_says_of_the_committed_parts_what_the_committed_output_says():
    """Each part carries the hash of the definition it was run under, and the judge refuses a part of
    another definition: that is the judge's rule, not this test's. So there are two cases.

    The definition is the one the parts were run under: the judge prints the committed output, byte for
    byte, and returns 0, and this test passes. This is the case on the day the run was committed.

    The definition has changed since: the judge must refuse, and for that reason ALONE. Every line it
    prints is a line of the committed output but eight: the line that says the parts are the stated
    experiment, six lines naming the hash, one a part, and the verdict. Then the page's figures are
    those of an earlier definition, and the run is made again before it is claimed for the new one.
    The first run of 2026-11-23 met this at its merge, half an hour after it was made: it was run on the
    parcel's commit, and the branch it was merged into had a later definition.

    In that case THIS TEST SKIPS, by name, E1-RECORD-STALE, once it has held that the hash is the judge's
    only reason. Until round 3's P0-3 it passed, and the gate was green without a word on a record of an
    earlier definition. A skip is named and counted on the gate's verdict line, and fails the gate under
    --require-all. The control is the next test: one comment line of the definition changed."""
    reason = the_committed_record_against(C.SPEC_SHA256)
    if reason is not None:
        pytest.skip(reason)


def test_e1_full_run_a_definition_changed_by_one_comment_line_makes_the_record_stale_by_name(monkeypatch):
    """The control of the skip above. The definition's hash is taken over its bytes, so one comment line
    changed is another definition to the judge. Under that hash THE TEST ABOVE, called as it is, must skip,
    by the name E1-RECORD-STALE, and for the judge's refusal on the hash alone. Until VP0R3 (2026-11-24) this
    control called the helper and not the test: a test that went back to passing quietly passed it too."""
    with open(os.path.join(ROOT, "spec", "undertone.toml"), "rb") as f:
        raw = f.read().replace(b"\r\n", b"\n")
    lines = raw.split(b"\n")
    at = next(i for i, line in enumerate(lines) if line.startswith(b"#"))
    lines[at] = lines[at] + b" (a comment changed by this test's control)"
    other = hashlib.sha256(b"\n".join(lines)).hexdigest()
    assert hashlib.sha256(raw).hexdigest() == C.SPEC_SHA256, "the hash is not taken as this control takes it"
    assert other != C.SPEC_SHA256
    monkeypatch.setattr(C, "SPEC_SHA256", other)
    with pytest.raises(pytest.skip.Exception) as skipped:
        test_e1_full_run_the_trees_judge_says_of_the_committed_parts_what_the_committed_output_says()
    reason = str(skipped.value)
    assert reason.startswith(STALE + ":") and other[:12] in reason, reason
    print("CONTROL the full run of E1 under a definition with one comment line changed: %s" % reason[:120])


def the_committed_record_against(spec_sha256):
    """None when the parts were run under `spec_sha256` and the tree's judge prints the committed output for
    them. The skip's reason when they were run under another and the judge refuses them for that alone.
    Fails on anything else."""
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
    if run_under == {spec_sha256}:
        assert code == 0
        assert printed.encode("utf-8") == data(OUTPUT), "the judge no longer prints the committed output for the committed parts"
        return None
    lines = printed.rstrip("\n").split("\n")
    new = [line for line in lines if line not in committed]
    gone = [line for line in committed if line not in lines]
    assert code != 0 and lines[-1] == "== E1 SOFTWARE VERDICT: FAIL"
    assert len([line for line in new if "spec_sha256 is" in line]) == 6 and len(new) == 8, new
    assert len(gone) == 2 and gone[-1] == VERDICT, gone
    return ("%s: the full run of E1 was made under the definition %s..., and this tree's is %s...; the judge refuses "
            "its parts for that alone, so docs/studies/E1-software.md's figures are an earlier definition's until "
            "the run is made again" % (STALE, sorted(run_under)[0][:12], spec_sha256[:12]))


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

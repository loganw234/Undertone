"""Stage E0 on the card, the card day's committed record, held: the committed files are still those the day
left, and the tree's own judges say of them what the committed outputs say.

The card day was the lead's, on 2026-11-25, 14:32 to 14:40 on the box's U50, from a snapshot of r4 at 5661550
(docs/studies/CARD-e0.md). The gate cannot run it again: it needs the card. What a reader has is five committed
files under docs/studies/e0-card/:
  - card-e0.json: what `hw/e0c/e0c.py compare` wrote on the desktop from the card's records of the 20 pieces:
    each amplitude's part, read from the card's own bytes, and each piece's report (bit identity by the block
    hashes against the model's expectation, made before the card ran), with the definition's hash;
  - compare-output.txt: what compare printed, the judge's lines and then the flip control's;
  - timed.json: what `hw/e0c/timed.py` wrote on the box for the ten timed generations, their parts and their
    records' SHA-256s (the records themselves stayed on the box);
  - timed-expected.json: the model's run of the ten timed sets (`e0c.py expect --timed`), made before the card ran;
  - timed-judge-output.txt: what `e0c.py timed-judge` printed for them.
The two outputs were Windows redirects; their committed bytes are the run's with each line end made a line feed.

So this file holds three things, as tests/test_e1_full_run.py does for stage E1:
  - each file has the SHA-256 it had when it was put in the tree;
  - `e0c.judge`, given only the record's parts and pieces and round 1's frozen parts (vectors/e0c/round1/),
    prints the committed output's lines up to and including E0's verdict, byte for byte, and returns 0;
  - `e0c.timed_judge`, given the two timed files, prints the committed timed output, byte for byte, and
    returns 0.
The card's image carries round 3's definition, and the record names that definition's hash. Once the tree's
definition moves past it (round 4 adds the pulse e1), the record is an earlier definition's: the second and
third tests then SKIP, by name, E0C-CARD-STALE (`e0c.stale`), and the gate's verdict line counts the skip. The
last test is the control: one comment line of the definition changed must make them skip by that name.

This file is the lead's and is NOT named test_p0_*.

What it cannot see:
  - whether the record is what the card gave: no card runs here. The record's reports and parts were written
    from the card's records on the desktop; a record with every figure changed in step, and its hash with it,
    passes. The day's ledger and the box's SHA256SUMS are the evidence of the records themselves;
  - the flip control's judgement: it needs the flip's records, which are not committed. Its committed line is
    held as text only;
  - whether the judges are right: it holds that they have not changed what they say of this record. Their own
    gates are E0C's, in tests/test_e0c_*.py;
  - whether the stale record's figures would still hold under a later definition: it does not judge it then.
"""
import hashlib
import json
import os
import shutil

import pytest

import test_seam_e0 as E0
from spec import constants as C

from hw.e0c import e0c

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.path.join(ROOT, "docs", "studies", "e0-card")
# `sha256sum` of the committed files, taken by the lead when they were put in the tree, 2026-11-25.
SHA256 = {
    "card-e0.json": "bfe29da984649cb701e812193565b4f6f770db6c246d9a2500db70b2cc41c3fa",
    "compare-output.txt": "47f882d8b1e7f37b4904a4c3400672ee4626f9824639e31f07087716d9723962",
    "timed.json": "1eefa95fc2cc657db644e5292fa0170bb88580f05d26ea9046a20f136b484ec6",
    "timed-expected.json": "82bb01cb1239984a5cadbd0e5f60b40938c1cbcc683ac6d5086fef2ff3275425",
    "timed-judge-output.txt": "290a20982fc2a1aa63f044735851bb8ff42956d6b1a0add5c595a3692d068bf1",
}
E0_VERDICT = ("== E0 CARD VERDICT: PASS, every record of every piece the model's, every count round 1's where given, "
              "every amplitude inside D8's tolerance")
FLIP = "== E0C FLIP CONTROL: SEEN, the flip reaches the records and the card ran the flipped blob"
TIMED_VERDICT = "== E0C TIMED VERDICT: PASS, every generation's records and counts the model's"
STALE = "E0C-CARD-STALE"


def data(name):
    with open(os.path.join(FOLDER, name), "rb") as f:
        return f.read()


def lines(name):
    return data(name).decode("utf-8").rstrip("\n").split("\n")


def stale_reason(record):
    """None when the record was made under the tree's definition, else the skip's reason, by name."""
    name = e0c.stale(record)
    if name is None:
        return None
    assert name == STALE
    return "%s: the card day's record names the definition %s..., the tree's is %s...; the card's image carries " \
           "round 3's definition, and the record is not judged under another" % (
               STALE, str(record.get("spec_sha256"))[:12], C.SPEC_SHA256[:12])


def test_e0c_card_record_the_five_files_are_the_ones_the_card_day_left():
    for name, want in SHA256.items():
        assert hashlib.sha256(data(name)).hexdigest() == want, "%s is not the file the card day left" % name
    assert sorted(n for n in os.listdir(FOLDER) if not n.startswith(".")) == sorted(SHA256)
    for name in SHA256:
        assert bytes([13]) not in data(name), name


def test_e0c_card_record_the_trees_judge_says_of_the_committed_record_what_the_committed_output_says():
    """The record's 20 pieces, its five parts, and the judge of the tree as it stands, given round 1's frozen
    parts as compare gives them: its lines are the committed output's up to E0's verdict, byte for byte, and it
    returns 0. Then the flip control's line, held as text. Skips by name, E0C-CARD-STALE, once the definition
    has moved past the record's."""
    record = json.loads(data("card-e0.json"))
    reason = stale_reason(record)
    if reason is not None:
        pytest.skip(reason)
    committed = lines("compare-output.txt")
    assert committed[-1] == FLIP and E0_VERDICT in committed
    cut = committed.index(E0_VERDICT) + 1
    assert [r["case"] for r in record["pieces"]] == ["a%dp%d" % (k, p) for k in range(5) for p in range(4)]
    assert all(r["identity"]["identical"] for r in record["pieces"])
    assert [p["part"] for p in record["parts"]] == list(range(5))
    round1 = dict((k, json.loads(open(os.path.join(e0c.ROUND1, "part%d.json" % k), "rb").read().decode("utf-8")))
                  for k in range(len(E0.AMPLITUDES)))
    printed = []
    code = e0c.judge(record["parts"], record["pieces"], round1, E0.not_as_stated, out=printed.append)
    assert printed == committed[:cut], "the tree's judge no longer says of the record what the card day's said"
    assert code == 0
    assert [p["found"] for p in record["parts"]] == [round1[k]["found"] for k in range(5)]


def test_e0c_card_record_the_trees_timed_judge_says_of_the_committed_timed_runs_what_the_committed_output_says(
        tmp_path):
    """The ten timed generations' committed results against the model's committed expectation: the tree's
    timed judge prints the committed output, byte for byte, and returns 0. Skips by name, as the test above."""
    record = json.loads(data("card-e0.json"))
    timed = json.loads(data("timed.json"))
    expected = json.loads(data("timed-expected.json"))
    assert timed["spec_sha256"] == expected["spec_sha256"] == record["spec_sha256"]
    reason = stale_reason(record)
    if reason is not None:
        pytest.skip(reason)
    cases = tmp_path / "cases" / "timed"
    cases.mkdir(parents=True)
    shutil.copyfile(os.path.join(FOLDER, "timed-expected.json"), str(cases / "expected.json"))
    run = tmp_path / "run"
    run.mkdir()
    shutil.copyfile(os.path.join(FOLDER, "timed.json"), str(run / "timed.json"))
    printed = []
    code = e0c.timed_judge(str(tmp_path / "cases"), str(run), out=printed.append)
    assert printed == lines("timed-judge-output.txt")
    assert printed[-1] == TIMED_VERDICT and code == 0
    assert [g["end"] for g in timed["generations"]] == ["done"] * 10
    assert timed["collector"] == "disabled" and all(g["collector"] == "disabled" for g in timed["generations"])


def test_e0c_card_record_a_definition_changed_by_one_comment_line_makes_the_record_stale_by_name(monkeypatch):
    """The control of the two skips above. The definition's hash is taken over its bytes, so one comment line
    changed is another definition. Under that hash the two tests above, called as they are, must each skip by
    the name E0C-CARD-STALE, naming both hashes."""
    with open(os.path.join(ROOT, "spec", "undertone.toml"), "rb") as f:
        raw = f.read().replace(b"\r\n", b"\n")
    rows = raw.split(b"\n")
    at = next(i for i, row in enumerate(rows) if row.startswith(b"#"))
    rows[at] = rows[at] + b" (a comment changed by this test's control)"
    other = hashlib.sha256(b"\n".join(rows)).hexdigest()
    assert hashlib.sha256(raw).hexdigest() == C.SPEC_SHA256, "the hash is not taken as this control takes it"
    assert other != C.SPEC_SHA256
    monkeypatch.setattr(C, "SPEC_SHA256", other)
    for test in (test_e0c_card_record_the_trees_judge_says_of_the_committed_record_what_the_committed_output_says,
                 test_e0c_card_record_the_trees_timed_judge_says_of_the_committed_timed_runs_what_the_committed_output_says):
        with pytest.raises(pytest.skip.Exception) as skipped:
            if test.__code__.co_argcount:
                test(None)
            else:
                test()
        reason = str(skipped.value)
        assert reason.startswith(STALE + ":") and other[:12] in reason, reason
    print("CONTROL the card day's record under a definition with one comment line changed: %s" % reason[:120])

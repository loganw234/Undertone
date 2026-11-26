"""Stage E1 on the card, the card day's committed record, held: the committed files are still those the day left,
the tree's E1 judge says of the card's six parts what it said of the software's, and the record says what the
day's printed output says.

The card day was the lead's, on 2026-11-26, 08:00 to 08:18 on the box's U50, from a snapshot of E1C at dc33d30
(docs/studies/CARD-e1.md). The gate cannot run it again: it needs the card, and its 6.76 GB of records are not
committed. What a reader has is three files under docs/studies/e1-card/:
  - card-e1.json: what `hw/e1c/e1c.py compare` wrote on the desktop from the card's records of the 51 runs: the
    six parts read from the card's own bytes, what each check found (each part's, both swap runs', the flip's),
    the judge's result, the verdict, and the definition's hash;
  - compare-output.txt: what compare printed, a Windows redirect whose committed bytes are the run's with each
    line end made a line feed;
  - records-sha256.txt: the box's SHA256SUMS of the run folder, every records.bin and report.json, made on the
    box after the last run, and the same file on the desktop after the copy back.

So this file holds four things:
  - each file has the SHA-256 it had when it was put in the tree;
  - stage E1's own judge (`judge_parts`, through `e1c.judge_output`), given only the record's six parts, prints
    docs/studies/e1/judge-output.txt byte for byte and returns 0, and each part is E1's committed part key for
    key;
  - the record's checks and the printed output agree, line by line, on what the verdict rests on: every run
    IDENTICAL, both swaps at the named index and bracketed below it, the flip at the predicted record by the
    predicted amount; and the box's sums name exactly the runs the output names;
  - the control: one comment line of the definition changed makes the second skip by name.
The card's image carries round 3's definition, and the record names that definition's hash. Once the tree's
definition moves past it (r5's is another), the record is an earlier definition's: the second test then SKIPS,
by name, E1C-CARD-STALE (`e1c.stale`), and the gate's verdict line counts the skip. The third reads no definition
and no judge of the tree, and runs everywhere.

This file is the lead's and is NOT named test_p0_*.

What it cannot see:
  - whether the record is what the card gave: no card runs here. The record's parts and checks were written from
    the card's records on the desktop; a record with every figure changed in step, and its hash with it,
    passes. The day's ledger, the box's log and the box's sums are the evidence of the records themselves;
  - bit identity itself: it needs the records and the model's expectations, neither committed. The IDENTICAL
    lines and the checks' `identical` are held as what the day wrote, not judged again;
  - whether compare is right: its own gates are E1C's, in tests/test_e1c_*.py;
  - whether the stale record's figures would still hold under a later definition: it does not judge it then.
"""
import hashlib
import json
import os
import re

import pytest

from spec import constants as C

from hw.e1c import e1c

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.path.join(ROOT, "docs", "studies", "e1-card")
# `sha256sum` of the committed files, taken by the lead when they were put in the tree, 2026-11-26.
SHA256 = {
    "card-e1.json": "f5446bc7a66e42080cc63e94abf7acd0b642fbad0c67af2e9ad4ded8124c9145",
    "compare-output.txt": "3a24810534ef13534de0b13f4d752435a89093094411e45762a32dfb5dcb2d16",
    "records-sha256.txt": "67135c9257535d619e4ec27ed7373cddaacf241b6f50978770ecd77fed41ea0b",
}
VERDICT = ("== E1 CARD VERDICT: PASS, every record of every run the model's, every part E1's key for key, E1's "
           "judge's output byte for byte")
JUDGE_LINE = "  E1's own judge on the six card parts: its output EQUAL to docs/studies/e1/judge-output.txt, byte for byte"
FLIP = "== E1C FLIP CONTROL: SEEN, the flip reaches the records at the record predicted and the card ran the flipped set"
SWAP_AT = 2097152
STALE = "E1C-CARD-STALE"


def data(name):
    with open(os.path.join(FOLDER, name), "rb") as f:
        return f.read()


def lines(name):
    return data(name).decode("utf-8").rstrip("\n").split("\n")


def stale_reason(record):
    """None when the record was made under the tree's definition, else the skip's reason, by name."""
    name = e1c.stale(record)
    if name is None:
        return None
    assert name == STALE
    return "%s: the card day's record names the definition %s..., the tree's is %s...; the card's image carries " \
           "round 3's definition, and the record is not judged under another" % (
               STALE, str(record.get("spec_sha256"))[:12], C.SPEC_SHA256[:12])


def test_e1c_card_record_the_three_files_are_the_ones_the_card_day_left():
    for name, want in SHA256.items():
        assert hashlib.sha256(data(name)).hexdigest() == want, "%s is not the file the card day left" % name
    assert sorted(n for n in os.listdir(FOLDER) if not n.startswith(".")) == sorted(SHA256)
    for name in SHA256:
        assert bytes([13]) not in data(name), name


def test_e1c_card_record_e1s_judge_says_of_the_cards_six_parts_what_it_said_of_the_softwares(tmp_path):
    """The record's six parts, read from the card's bytes, handed to stage E1's own judge as compare hands them:
    its output is E1's committed output, byte for byte, and it returns 0; and each part is E1's committed part,
    key for key. Then the printed output's judge lines are those. Skips by name, E1C-CARD-STALE, once the
    definition has moved past the record's."""
    record = json.loads(data("card-e1.json"))
    reason = stale_reason(record)
    if reason is not None:
        pytest.skip(reason)
    parts = sorted(record["parts"], key=lambda p: p["part"])
    assert [p["part"] for p in parts] == list(range(6))
    committed = e1c.committed_parts()
    for p in parts:
        assert e1c.differing(p, committed[p["part"]]) == [], "part %d is not E1's committed part" % p["part"]
    printed, code = e1c.judge_output(parts, str(tmp_path / "judge"))
    assert e1c.against_output(printed, e1c.read_bytes(e1c.E1_OUTPUT)) is None, \
        "E1's judge no longer says of the card's parts what it said of the software's"
    assert code == 0
    out = lines("compare-output.txt")
    at = out.index(JUDGE_LINE)
    assert out[at + 1] == "  " + printed.rstrip("\n").split("\n")[-1]
    assert record["judge"] == {"code": 0, "equal": True, "first_difference": None}


def test_e1c_card_record_the_record_and_the_printed_output_agree_on_what_the_verdict_rests_on():
    """Reads no definition and no judge of the tree. The record's verdict and the output's last line are PASS;
    every run the output names is IDENTICAL with its records' count; each part's check is identical, flags 0, the
    baseline the statistics'; part 5's blank stretch is the card's own; each swap's first new epoch is the named
    index and both next_index reads are below it; the flip is its own model run's and differs from the learned
    set's first at the predicted record, in the score field, by the predicted amount; and the box's sums name
    exactly the output's runs, each records.bin and report.json once."""
    record = json.loads(data("card-e1.json"))
    out = lines("compare-output.txt")
    assert record["verdict"] == "PASS" and out[-1] == VERDICT
    assert FLIP in out and JUDGE_LINE in out
    runs = {}
    for line in out:
        m = re.match(r"^  (\S+)\s+IDENTICAL: (\d+) records, every word the model's;", line)
        if m:
            runs[m.group(1)] = int(m.group(2))
    judged = ["c%d-p%d-%s" % (c, p, s) for c in range(6) for p in range(4) for s in ("learned", "matched")]
    assert sorted(runs) == sorted(judged + ["swap-blank", "swap-matched"])
    assert all(runs[n] == 6400000 for n in judged) and runs["swap-blank"] == runs["swap-matched"] == 2 * SWAP_AT
    assert not [line for line in out if "DIFFERENT" in line and not line.startswith("the flip control")]
    for c in range(6):
        got = record["checks"][str(c)]
        assert got["identical"] and got["flags"] == 0 and got["learned_flags"] == 0
        assert got["matched_identical_to_stats"] and got["read"]
        assert got["blank_prefix_equal"] is (True if c == 5 else None), c
    for which, bracket in (("blank", [1049468, 1050033]), ("matched", [1049776, 1050357])):
        got = record["checks"]["swap-" + which]
        assert got["identity"]["identical"] and got["identity"]["records"] == 2 * SWAP_AT
        assert got["first_new_epoch_index"] == SWAP_AT and got["end"] == "pass"
        assert got["next_index"] == bracket and all(v < SWAP_AT for v in bracket)
        assert ("== E1C SWAP %s: IDENTICAL; the first record of the new epoch at %d, the named index %d; the swap "
                "bracketed by next_index %s; SEEN" % (which, SWAP_AT, SWAP_AT, bracket)) in out
    flip = record["checks"]["flip"]
    first, pred = flip["against_learned"]["first"], flip["predicted"]
    assert flip["identity"]["identical"] and not flip["against_learned"]["identical"]
    assert first["record"] == pred["record"] == 35 and first["field"] == pred["field"] == "score"
    assert first["card"] - first["model"] == pred["difference"] == -7278592
    sums = [line.split("  ", 1)[1] for line in lines("records-sha256.txt")]
    names = sorted(judged + ["swap-blank", "swap-matched", "flip-c5-p0"])
    assert sorted(sums) == sorted(n + "/" + f for n in names for f in ("records.bin", "report.json"))


def test_e1c_card_record_a_definition_changed_by_one_comment_line_makes_the_record_stale_by_name(monkeypatch):
    """The control of the skip above. The definition's hash is taken over its bytes, so one comment line changed
    is another definition. Under that hash the judge's test, called as it is, must skip by the name
    E1C-CARD-STALE, naming both hashes."""
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
        test_e1c_card_record_e1s_judge_says_of_the_cards_six_parts_what_it_said_of_the_softwares(None)
    reason = str(skipped.value)
    assert reason.startswith(STALE + ":") and other[:12] in reason, reason
    print("CONTROL the card day's record under a definition with one comment line changed: %s" % reason[:120])

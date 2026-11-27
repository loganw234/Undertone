"""The learner's card day, its committed record, held: the committed files are still those the day left, the
tree's LRN-C judge says of the record's reports what it said on the day, and the record says what the day's
printed output says.

The card day was the lead's, on 2026-11-27, 08:00:28 to 08:01:35 on the box's U50, with the image of e67967d
(parcel POOLRAM's line: the learner in SLR1, the pool in UltraRAM; DATA_CLK 93 MHz) and the host tree of LRN-C at
39c2061 (docs/studies/CARD-learn.md). The gate cannot run it again: it needs the card, and the runs' 418 MB of
records, and the model's 330 MB of expected records, are not committed. What a reader has is under
docs/studies/learn-card/:
  - compare-output.txt: what `hw/lrnc/lrnc.py compare` printed on the desktop, a Windows redirect whose
    committed bytes are the run's with each line end made a line feed;
  - card-lrnc.json: what compare wrote beside it;
  - records-sha256.txt: the box's SHA256SUMS of the run folder (each run's records.bin, report.json and log),
    made on the box after the last run, and the same file on the desktop after the copy back;
  - runs/<run>/report.json and runs/<run>.log: each run's report and log, the bytes those sums name;
  - expect/<case>/expected.json and order.txt: the model's expectation of each case (its records' SHA-256, its
    script, windows, outcomes and the learner's registers at the end), from `lrnc.py expect` on the desktop;
  - day-e67967d.log: the box's log of the day.

So this file holds four things:
  - each file has the SHA-256 it had when it was put in the tree;
  - the tree's judge, given only the committed reports and expectations, prints each run's lines of the committed
    output, word for word: the operations (`_ops_lines`) and the registers at the end (`_registers_lines`); and
    each run's head line is the one its records' SHA-256 against the model's gives. It skips by name,
    LRN-C-CARD-STALE, once the definition has moved past the record's;
  - the record and the printed output agree on what the verdict rests on, reading no definition and no judge:
    the committed reports and logs are the bytes the box's sums name, each run's records hash is the model's,
    flow again is flow, moved is not, the control is SEEN at moved's commit, and the verdict is PASS;
  - the control: one comment line of the definition changed makes the second skip by name.

This file is the lead's and is NOT named test_p0_*.

What it cannot see:
  - whether the record is what the card gave: no card runs here. A record with every file and its hash changed
    in step passes. The day's ledger, the box's log and the box's sums are the evidence of the records;
  - bit identity itself, block by block: it needs the records, not committed. The records are held only by their
    SHA-256, the box's against the model's;
  - the control's first difference: it needs both models' records. The control line is held as printed, and its
    record against moved's commit;
  - whether the model's expectations are the model's: they are held by their hash, as `lrnc.py expect` wrote
    them (the round's ledger, 2026-11-26 08:49), not made again;
  - whether compare is right: its own gates are LRN-C's, in tests/test_lrn_c_*.py.
"""
import hashlib
import json
import os
import re

import pytest

from spec import constants as C

from hw.lrnc import lrnc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FOLDER = os.path.join(ROOT, "docs", "studies", "learn-card")
# `sha256sum` of the committed files, taken by the lead when they were put in the tree, 2026-11-27.
SHA256 = {
    "compare-output.txt": "1eff93400649ac015028dfaa6537f1231dab1e0138815e2e788643ed058c241c",
    "card-lrnc.json": "09612258cd204c7b116dce51a3e45fb0077438a09da4b3d8357f1e4b821823b7",
    "records-sha256.txt": "37fa7fb9c8711dd3957077bf24428ade33377f6aea5b24f9168a8c71dbf1ccf9",
    "day-e67967d.log": "11fdf0639b5fecc0c747c6c6b9dc5dbe229ffe93d97bacf03b2f2f8c8c2a2f22",
    "order.txt": "0089a003647c591ba1cf277d473f61affc8ac771db4706f35edd807dad64cb44",
    "expect/flow/expected.json": "db411c88b913f54f44e16207a1b57abe478ddbd2774ef3b51af04bb68d5de3da",
    "expect/rich/expected.json": "3ed974b9a18de59dae7ae3bb16c819fc5bff32e503933849d1ce8ea131b972e0",
    "expect/moved/expected.json": "6cf1fa0fec98eb916f39c412026299f212d523c788d668070f399084c4af6904",
    "runs/flow/report.json": "f1795338fc2173e032b98a8c2e6b12ae92ba7b2a4462e232017cb1f6c5e5cbcf",
    "runs/flow.log": "a658e4c1dc92908a863f5f3ae62e3901f710d9c7cfccb9ba6afc6fc07557556e",
    "runs/rich/report.json": "8e43055b2ddc7dd162e36629fc64907a31876a31122310cf32cd2b4b19a3f84b",
    "runs/rich.log": "b0db3cf09401404f0874c44eccb425ab44531e0a038233103802d5ec98aa1b6f",
    "runs/moved/report.json": "56a65541281e4ef8a31bde6a1a650719e2b6ee3452a067834310c4a5d95fc796",
    "runs/moved.log": "2167ec22cb9f2f668f1f7e3bd07fc48eec5c7a73eef266e3d3e41f5ceefd74a8",
    "runs/flow-again/report.json": "94eabdd56c4d95dabea415f0a9cd658b8c21f41ead7b5ae774d3787e7e04282f",
    "runs/flow-again.log": "67906976cf91b326cd4e5cdff3a8eac0d787b85a8993f9221b9231ee6cfefa7c",
}
ORDER = [("flow", "flow"), ("rich", "rich"), ("moved", "moved"), ("flow-again", "flow")]
IMAGE = "0af21036a760ba40e1c9f73135c8a6b6cd5e38f1f6c8a07b0f09f56826f5a31b"   # e67967d's undertone_hw.xclbin
VERDICT = "== LRN-C CARD VERDICT: PASS"
STALE = "LRN-C-CARD-STALE"


def data(name):
    with open(os.path.join(FOLDER, *name.split("/")), "rb") as f:
        return f.read()


def lines(name):
    return data(name).decode("utf-8").rstrip("\n").split("\n")


def loaded(name):
    return json.loads(data(name))


def sums():
    """The box's SHA256SUMS as {path: hash}."""
    out = {}
    for line in lines("records-sha256.txt"):
        digest, path = line.split("  ", 1)
        assert path not in out, "%s twice in the box's sums" % path
        out[path] = digest
    return out


def stale_reason(record):
    """None when the record was made under the tree's definition, else the skip's reason, by name."""
    if record.get("spec_sha256") == C.SPEC_SHA256:
        return None
    return "%s: the card day's record names the definition %s..., the tree's is %s...; the record is not judged " \
           "under another" % (STALE, str(record.get("spec_sha256"))[:12], C.SPEC_SHA256[:12])


def test_lrn_c_card_record_the_files_are_the_ones_the_card_day_left():
    for name, want in SHA256.items():
        assert hashlib.sha256(data(name)).hexdigest() == want, "%s is not the file the card day left" % name
    found = []
    for at, _, files in os.walk(FOLDER):
        found += [os.path.relpath(os.path.join(at, f), FOLDER).replace(os.sep, "/") for f in files
                  if not f.startswith(".")]
    assert sorted(found) == sorted(SHA256)
    for name in SHA256:
        assert bytes([13]) not in data(name), name


def test_lrn_c_card_record_the_trees_judge_says_of_the_committed_reports_what_it_printed_on_the_day():
    """The judge's own checks of each run's operations and of the learner's registers at the end, given the
    committed report and the model's expectation, print the committed output's lines for that run, word for word,
    and pass. Each run's head line is the one its records' hash against the model's, its report's record count
    and its log's PASS line give. Skips by name, LRN-C-CARD-STALE, once the definition has moved past the
    record's."""
    record = loaded("card-lrnc.json")
    reason = stale_reason(record)
    if reason is not None:
        pytest.skip(reason)
    assert [line.split() for line in lines("order.txt")] == [list(p) for p in ORDER]
    box = sums()
    printed = []
    for run, case in ORDER:
        expected = loaded("expect/%s/expected.json" % case)
        assert expected["spec_sha256"] == C.SPEC_SHA256, "%s's expectation is another definition's" % case
        report = loaded("runs/%s/report.json" % run)
        log = data("runs/%s.log" % run).decode("utf-8")
        identical = box[run + "/records.bin"] == expected["sha256"]
        ended = report["run"]["records"] == expected["frames"] and any(
            line.startswith("PASS host.run_case") for line in log.splitlines())
        assert identical and ended, "%s is not the model's run on the card" % run
        printed.append("== LRN-C RUN %s: IDENTICAL, %d records" % (run, expected["records"]))
        op_lines, ops_ok, ops_bad = lrnc._ops_lines(run, expected, report)
        reg_lines, regs_ok, regs_bad = lrnc._registers_lines(run, expected, report)
        assert ops_ok, ops_bad
        assert regs_ok, regs_bad
        printed += ["   " + x for x in op_lines + reg_lines]
    out = lines("compare-output.txt")
    assert out[:len(printed)] == printed, "the judge no longer says of the reports what it printed on the day"
    assert out[len(printed):] == [out[-2], VERDICT] and out[-2].startswith("== LRN-C CONTROL moved: SEEN:")


def test_lrn_c_card_record_the_record_and_the_printed_output_agree_on_what_the_verdict_rests_on():
    """Reads no definition and no judge of the tree. The committed reports and logs are the bytes the box's sums
    name, and the sums name each run's records, report and log once and nothing else. Each run's records hash is
    its case's expectation's, so flow again's is flow's and moved's is not. The judge's JSON says the same of
    every run, with no failure. The day's log names the image and each run IDENTICAL by that hash, the card
    HEALTHY before and after. The control is SEEN, at moved's commit, in the score. The verdict is PASS."""
    box = sums()
    names = [run for run, _ in ORDER]
    assert sorted(box) == sorted([r + "/records.bin" for r in names] + [r + "/report.json" for r in names]
                                 + [r + ".log" for r in names])
    for run in names:
        assert hashlib.sha256(data("runs/%s/report.json" % run)).hexdigest() == box[run + "/report.json"], run
        assert hashlib.sha256(data("runs/%s.log" % run)).hexdigest() == box[run + ".log"], run
    want = {case: loaded("expect/%s/expected.json" % case)["sha256"] for case in ("flow", "rich", "moved")}
    record = loaded("card-lrnc.json")
    assert record["verdict"] == "PASS" and record["failed"] == []
    day = lines("day-e67967d.log")
    for run, case in ORDER:
        assert box[run + "/records.bin"] == want[case], "%s's records are not its case's expectation's" % run
        got = record["runs"][run]
        assert got == {"identical": True, "first": None, "ended": True, "operations": True, "registers": True,
                       "sha256": want[case]}, run
        assert "%s IDENTICAL by its SHA-256 %s" % (run, want[case]) in day, run
    assert box["flow-again/records.bin"] == box["flow/records.bin"] != box["moved/records.bin"]
    assert any(line.startswith(IMAGE + "  ") and line.endswith("/build-e67967d/out/undertone_hw.xclbin")
               for line in day)
    assert [line.strip() for line in day if "Device Status:" in line] == ["Device Status: HEALTHY"] * 2
    out = lines("compare-output.txt")
    assert out[-1] == VERDICT
    commit = [op["arg"] for op in loaded("expect/moved/expected.json")["script"] if op["op"] == "commit"]
    m = re.match(r"^== LRN-C CONTROL moved: SEEN: its own model run's, and different from flow's first at record "
                 r"(\d+), score, (\d+) where flow's is (\d+), as predicted$", out[-2])
    assert m and commit == [int(m.group(1))] and m.group(2) != m.group(3), out[-2]
    assert not [line for line in out if "DIFFERENT" in line or "OUTSIDE" in line or "NOT the model's" in line]


def test_lrn_c_card_record_a_definition_changed_by_one_comment_line_makes_the_record_stale_by_name(monkeypatch):
    """The control of the skip above. The definition's hash is taken over its bytes, so one comment line changed
    is another definition. Under that hash the judge's test, called as it is, must skip by the name
    LRN-C-CARD-STALE, naming both hashes."""
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
        test_lrn_c_card_record_the_trees_judge_says_of_the_committed_reports_what_it_printed_on_the_day()
    reason = str(skipped.value)
    assert reason.startswith(STALE + ":") and other[:12] in reason, reason
    print("CONTROL the card day's record under a definition with one comment line changed: %s" % reason[:120])

"""The launch experiment's freeze, held: the files that were frozen before its one scoring run are still those files,
and the run's committed output is still that output.

Study D2 (docs/studies/D2-launch-experiment.md) scored twenty-three launches once, by a rule and constants
committed and hashed before any scored record was opened. The scoring cannot be made again in place, so what
a reader has is the committed output and the files it names. If one of those files changes afterwards, the
output no longer says what the tree's rule gives, and nothing would notice: a verifier was handed a tree in
which one frozen constant had been changed after the scoring, and the gate passed.

This test is the lead's, added on 2026-11-23 in the commit after the study's merge. It works the freeze hash
itself, from the seven files, in the order and form the parcel wrote down at its freeze, and holds it to the
hash the scoring run printed. It holds the whole of the committed output by its own SHA-256: a second
verifier changed one row of the output's table and the first form of this test, which read two lines, passed.
It imports nothing of the study's code.

What it cannot see:
  - whether the scoring came after the freeze: no file carries the run's time;
  - whether the committed output is what the run printed: it holds that the file has not changed since it
    was committed, by a hash the lead took from the committed file, which a verifier's own rerun of the
    scoring at the freeze commit reproduced byte for byte;
  - the fetched records, which are not in the tree;
  - a file that is NOT frozen and changes what a frozen one does. The frozen scripts put docs/studies/d1/ at
    the front of their import path: a new file there with the name of a module they import would take its
    place, and no frozen file would change. A verifier named this; nothing holds it.
"""
import hashlib
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The seven frozen files, in the order of the parcel's freeze entry (the round's ledger, 2026-11-23 13:41:57).
FROZEN = ("docs/studies/d2/rule.py", "docs/studies/d2/score.py", "docs/studies/d2/constants.json",
          "docs/studies/d2/launches.tsv", "docs/studies/d2/manifest.tsv",
          "docs/studies/d1/firstlook.py", "docs/studies/d1/mseed.py")
OUTPUT = "docs/studies/d2/scored-output.txt"
# Typed here from the lead's ledger entry of 13:44 that day, which recomputed it before the scoring was allowed.
FREEZE_HASH = "dc7f28f172f8e201095a07a1a5b762a74407b4ca5c78d58a5d4b6815051f781f"
# The SHA-256 of the committed output, taken by the lead from the file at the merge. The study's row X15 and
# both verifiers give the same.
OUTPUT_SHA256 = "ce75702876d44b825d54c5be173b417aa8c9a3ca849ca8ac92ee4fe7103cd5ba"


def freeze_hash(contents):
    """The SHA-256 of one line for each file, "<the file's SHA-256>  <its path>", each ended by a line feed."""
    lines = "".join("%s  %s\n" % (hashlib.sha256(data).hexdigest(), name) for name, data in contents)
    return hashlib.sha256(lines.encode("ascii")).hexdigest()


def frozen_files():
    out = []
    for name in FROZEN:
        with open(os.path.join(ROOT, name), "rb") as f:
            out.append((name, f.read()))
    return out


def output_bytes():
    with open(os.path.join(ROOT, OUTPUT), "rb") as f:
        return f.read()


def test_p0_the_launch_experiments_frozen_files_are_still_the_frozen_ones():
    assert freeze_hash(frozen_files()) == FREEZE_HASH, \
        "a file frozen before study D2's scoring run has changed: its committed output no longer follows from the tree"


def test_p0_the_scoring_runs_output_is_the_committed_one_and_names_that_freeze():
    data = output_bytes()
    assert hashlib.sha256(data).hexdigest() == OUTPUT_SHA256, "the scoring run's committed output has changed"
    assert data.decode("utf-8").split("\n")[:2] == ["Study D2, the scoring run.", "Freeze hash %s." % FREEZE_HASH]


def test_p0_one_changed_byte_in_any_frozen_file_or_in_the_output_is_seen():
    """The control: each frozen file in turn with its last byte changed; two files' places exchanged; and
    the output with one digit of its results table changed, which the freeze hash alone would not see."""
    contents = frozen_files()
    for i, (name, data) in enumerate(contents):
        changed = list(contents)
        changed[i] = (name, data[:-1] + bytes([data[-1] ^ 1]))
        assert freeze_hash(changed) != FREEZE_HASH, name
    assert freeze_hash([contents[1], contents[0]] + contents[2:]) != FREEZE_HASH
    data = output_bytes()
    assert data.count(b"20 of 23") >= 1
    assert hashlib.sha256(data.replace(b"20 of 23", b"23 of 23", 1)).hexdigest() != OUTPUT_SHA256

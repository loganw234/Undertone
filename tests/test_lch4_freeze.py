"""Study D3's freeze, held: the files frozen before its one scoring run are still those files.

Study D3 (docs/studies/D3-faint-launches.md) scores twenty-three launches once, by a rule and
constants committed and hashed before any scored record was opened. The scoring cannot be made
again in place, so what a reader has is the committed output and the files it names. If one of
those files changes afterwards, the output no longer says what the tree's rule gives, and nothing
else would notice.

This test is written as the lead's tests/test_p0_study_freeze.py is for study D2, and sits outside
the frozen files. It works the freeze hash itself, from the seven files, in the order and form
docs/studies/d3/d3score.py uses ("<SHA-256>  <path>", one line each, each ended by a line feed),
and holds it to the hash typed below, which was written in the round's ledger
(ledger/LCH-4.md, the freeze entry of 2026-11-24) before the scoring run. It imports nothing of
the study's code.

What it cannot see:
  - whether the scoring came after the freeze: no file carries the run's time;
  - the fetched records, which are not in the tree;
  - a file that is NOT frozen and changes what a frozen one does: the frozen scripts put
    docs/studies/d1/ and docs/studies/d3/ at the front of their import path, so a new file in
    either with the name of a module they import would take its place, and no frozen file would
    change. The study's other scripts (d3launches.py, d3setconstants.py) are not frozen: they
    made launches.tsv and constants.json, which are.
"""
import hashlib
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The seven frozen files, in the order of d3score.py's FROZEN.
FROZEN = ("docs/studies/d3/d3rule.py", "docs/studies/d3/d3score.py", "docs/studies/d3/constants.json",
          "docs/studies/d3/launches.tsv", "docs/studies/d3/manifest.tsv",
          "docs/studies/d1/firstlook.py", "docs/studies/d1/mseed.py")
# Typed from `python docs/studies/d3/d3score.py --freeze-hash` at the freeze, and written in the
# round's ledger before the lead allowed the scoring.
FREEZE_HASH = "645d1e84d9e78a1ad3a987e767b38b885e1fe5e0553d3b31bd212ff33baafe59"


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


def test_lch4_the_faint_launch_studys_frozen_files_are_still_the_frozen_ones():
    assert freeze_hash(frozen_files()) == FREEZE_HASH, \
        "a file frozen before study D3's scoring run has changed: the rule is not the one frozen"


def test_lch4_one_changed_byte_in_any_frozen_file_is_seen():
    """The control: each frozen file in turn with its last byte changed, and two files' places
    exchanged, must each move the hash."""
    contents = frozen_files()
    for i, (name, data) in enumerate(contents):
        changed = list(contents)
        changed[i] = (name, data[:-1] + bytes([data[-1] ^ 1]))
        assert freeze_hash(changed) != FREEZE_HASH, name
    assert freeze_hash([contents[1], contents[0]] + contents[2:]) != FREEZE_HASH

"""Stage E3's freeze, held: the files frozen before the first request for its records are still those files.

Stage E3's noise rule (vectors/e3s/rule.json), the request list made from it, the script that
applies it to the fetched files, and the scripts those import or run were committed and hashed
before any record was asked for (the design in the round's ledger, 2026-11-25 20:57, section 12,
wall 1; the freeze entry in ledger/E3S.md names the hash and the commit). If one of them changes
afterwards, the blocks the full run replays no longer follow from the tree's rule, and nothing else
would notice. This test is written as tests/test_lch4_freeze.py is for study D3: it works the
freeze hash itself, in the same form ("<SHA-256>  <path>", one line a file, each ended by a line
feed), and imports nothing of the frozen code.

What it cannot see:
  - whether the first request came after the freeze: no file carries the fetch's time; the
    manifest's first time and the freeze commit's time, side by side, are what order them;
  - the fetched records, which are not in the tree;
  - a file that is NOT frozen and changes what a frozen one does: e3prep.py puts the tree's root and
    docs/studies/d1/ at the front of its import path, so a new file in either with the name of a
    module it imports would take its place; and model/, stats/ and spec/, which it imports, are
    not frozen here (they are held by their own gates, and a change to them is a change of the
    tree's commit, which the full run's part records).
"""
import hashlib
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FROZEN = ("vectors/e3s/rule.json", "docs/studies/e3/e3requests.py", "docs/studies/e3/requests.tsv",
          "docs/studies/e3/e3prep.py", "docs/studies/d1/mseed.py", "docs/studies/d1/catalogue.py",
          "docs/studies/d1/stations.py", "docs/studies/d2/fetch.py")
# Worked by this file's freeze_hash at the freeze, and written in ledger/E3S.md with the freeze commit
# before the first request for records.
FREEZE_HASH = "ee4c566e8caac274bd2a4c68f6374432fdcc6fdc81ba123121d76592ad39b6cd"


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


def test_e3s_freeze_the_frozen_files_are_still_the_frozen_ones():
    assert freeze_hash(frozen_files()) == FREEZE_HASH, \
        "a file frozen before stage E3's first request has changed: the blocks no longer follow from the tree"


def test_e3s_freeze_one_changed_byte_in_any_frozen_file_or_an_exchange_of_two_is_seen():
    contents = frozen_files()
    want = freeze_hash(contents)
    for i, (name, data) in enumerate(contents):
        changed = list(contents)
        changed[i] = (name, data[:-1] + bytes([data[-1] ^ 1]))
        assert freeze_hash(changed) != want, name
    swapped = list(contents)
    swapped[0], swapped[1] = (contents[0][0], contents[1][1]), (contents[1][0], contents[0][1])
    assert freeze_hash(swapped) != want
    assert len(set(FROZEN)) == len(FROZEN) == 8

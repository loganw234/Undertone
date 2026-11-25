"""E0C: the premise, and round 1's record frozen as the card's counts are compared with it.

The card's counts must equal round 1's exactly only if today's model and definition make round 1's stream. The
premise's rerun (E0C's ledger, 2026-11-25 12:33): round 1's own script, `python tests/test_seam_e0.py --full
--amplitude 2`, unchanged, under round 4's tree, kept as vectors/e0c/premise/part2.json. It equals round 1's part 2
(vectors/e0c/round1/part2.json) in every field but `spec_sha256`, the definition's hash, which is today's.

These are RECORDS, not known answers (vectors/e0c/NOTE.json): round 1's parts READ from the round's folder, byte for
byte, their SHA-256s in the note; the premise's MEASURED by its command. What judges the card is the stated cut and
the model's own expect run, not these files.

ONCE `spec/` MOVES (track B's pulse `e1`, the plan's L13), the premise record is of an earlier definition: this test
then holds that the definition's hash is the only field that differs from round 1's, and SKIPS BY NAME,
E0C-PREMISE-STALE, as tests/test_e1_full_run.py does with E1-RECORD-STALE (CLAUDE.md, trap 18). The verdict line
counts the skip, and `--require-all` fails on it, until the rerun is made again under the new definition.
"""
import hashlib
import json
import os

import pytest

from spec import constants as C

from hw.e0c import e0c

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V = os.path.join(ROOT, "vectors", "e0c")
STALE = "E0C-PREMISE-STALE"


def load(*parts):
    with open(os.path.join(V, *parts), encoding="utf-8") as f:
        return json.load(f)


def held(new, old):
    """The fields of the premise's part that are not round 1's."""
    return sorted(k for k in set(new) | set(old) if new.get(k) != old.get(k))


def test_e0c_premise_round_1s_part_2_made_again_under_todays_tree():
    new, old = load("premise", "part2.json"), load("round1", "part2.json")
    assert held(new, old) == ["spec_sha256"], "every field round 1's but the definition's hash"
    assert old["spec_sha256"] == "209d3009cd0ba3db510d2a102a05d45c862ac1ee9008aadc612daf2ab4ee066f"
    assert (new["found"], new["noise_crossings"], new["stream_sha256"][:8]) == (99743, 2008, "d4ff45db")
    if new["spec_sha256"] != C.SPEC_SHA256:
        pytest.skip("%s: the premise's record names the definition %s..., the tree's is %s...; its only difference "
                    "from round 1's is that hash, held above" % (STALE, new["spec_sha256"][:8], C.SPEC_SHA256[:8]))
    lines = []
    assert e0c.premise(os.path.join(V, "premise", "part2.json"), os.path.join(V, "round1", "part2.json"),
                       out=lines.append) == 0
    assert lines[-1] == "== E0C PREMISE: EQUAL in every field but the definition's hash, which is today's"


def test_e0c_premise_a_field_changed_in_a_copy_is_reported(tmp_path):
    new = load("premise", "part2.json")
    for field, value in (("found", 99742), ("stream_sha256", "0" * 64), ("threshold", 1595666165)):
        path = tmp_path / ("%s.json" % field)
        path.write_text(json.dumps(dict(new, **{field: value})), encoding="utf-8")
        lines = []
        assert e0c.premise(str(path), os.path.join(V, "round1", "part2.json"), out=lines.append) == 1, field
        assert "NOT EQUAL" in lines[-1] and field in lines[-1]


def test_e0c_the_frozen_records_are_the_note_says():
    note = load("NOTE.json")
    assert note["basis"] == "READ" and len(note["files"]) == 6
    for row in note["files"]:
        with open(os.path.join(V, row["file"]), "rb") as f:
            data = f.read()
        assert hashlib.sha256(data).hexdigest() == row["source_sha256"], row["file"]
        assert data.count(bytes([13])) == 0
        assert row["basis"] == ("MEASURED" if row["file"].startswith("premise/") else "READ")
        assert "<repos>" in row["source"] or row["file"].startswith("premise/")
    # round 1's counts, as docs/VALIDATION.md's 2026-11-23 table gives them
    r1 = [load("round1", "part%d.json" % k) for k in range(5)]
    assert [p["found"] for p in r1] == [24442, 55857, 99743, 144075, 175622]
    assert [p["noise_crossings"] for p in r1] == [1929, 1974, 2008, 2041, 1987]
    assert [p["seed"] for p in r1] == [2026112300 + k for k in range(5)]
    assert all(p["real_found"] == p["found"] and p["model_only"] == p["real_only"] == 0 and p["flags"] == 0 for p in r1)

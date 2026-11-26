#!/usr/bin/env python3
"""Stage E3's injection sets and their digests, by arithmetic that imports nothing of model/.

    python docs/studies/e3/e3sets.py               write vectors/e3s/injection_sets.json's stations
                                                   from vectors/e3s/blocks.json
    python docs/studies/e3/e3sets.py --short NUM   write its short form's set, at amplitude NUM / 65536

Comparison rule 1 of D0's section 8: the injection set is fixed and committed, with its
hash, before the run. A station's set follows from its amplitude (blocks.json, worked by
e3prep.py from the calibration stretch) and the layout of vectors/e3s/rule.json:

  training   blocks 0 .. training - 1 of the part's stream, a truth record at
             block * block_frames + training_first + training_trial * i
  held-out   blocks training .. training + held_out - 1, a truth record at
             block * block_frames + held_first + held_trial * i

every record e0 at amplitude_num / amplitude_den. The digest is the form of
model.records.digest("truth", ...) written again here, as tests/test_lrn_a_e1.py's
independent_digest writes it: SHA-256 of b"undertone-records" 0 b"truth" 0, then each
record packed "<QHiI" (index, pulse_id, amplitude_num, amplitude_den).
tests/test_e3s_experiment.py holds both forms equal on every committed set.

It imports json, hashlib, struct and spec.constants (for e0's pulse id), nothing else of
the tree.
"""
import hashlib
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from spec import constants as C  # noqa: E402

RULE = os.path.join(ROOT, "vectors", "e3s", "rule.json")
BLOCKS = os.path.join(ROOT, "vectors", "e3s", "blocks.json")
SETS = os.path.join(ROOT, "vectors", "e3s", "injection_sets.json")
# The short form's layout (tests/test_e3s_experiment.py, SHORT): blocks of 16,384 frames.
SHORT = {"block_frames": 16384, "training": 32, "held_out": 64}


def schedule(num, den, block_frames, training, held_out, layout):
    out = []
    for b in range(training):
        for i in range(block_frames // layout["training_trial"]):
            out.append((b * block_frames + layout["training_first"] + layout["training_trial"] * i, num, den))
    for b in range(training, training + held_out):
        for i in range(block_frames // layout["held_trial"]):
            out.append((b * block_frames + layout["held_first"] + layout["held_trial"] * i, num, den))
    return out


def digest(rows):
    pid = C.PULSE_IDS["e0"]
    h = hashlib.sha256(b"undertone-records" + bytes([0]) + b"truth" + bytes([0]))
    for index, num, den in rows:
        h.update(struct.pack("<QHiI", index, pid, num, den))
    return h.hexdigest(), len(rows)


def entry(num, den, block_frames, training, held_out, layout):
    rows = schedule(num, den, block_frames, training, held_out, layout)
    sha, count = digest(rows)
    return {"sha256": sha, "records": count, "amplitude_num": num, "amplitude_den": den,
            "block_frames": block_frames, "training_blocks": training, "held_out_blocks": held_out,
            "training_records": training * (block_frames // layout["training_trial"]),
            "held_out_injections": held_out * (block_frames // layout["held_trial"]),
            "first_index": rows[0][0], "last_index": rows[-1][0]}


def load(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv):
    with open(RULE, encoding="utf-8") as f:
        rule = json.load(f)
    sets = load(SETS, {"what": "Stage E3's injection sets, one a station and the short form's, each with its digest, "
                               "worked by docs/studies/e3/e3sets.py, which imports nothing of model/.",
                       "how_worked": "schedule and digest as e3sets.py's docstring; held to model.records.digest by "
                                     "tests/test_e3s_experiment.py", "stations": {}, "short": None})
    den = rule["amplitude"]["den"]
    if argv[:1] == ["--short"] and len(argv) == 2:
        sets["short"] = entry(int(argv[1]), den, SHORT["block_frames"], SHORT["training"], SHORT["held_out"],
                              rule["layout"])
    elif not argv:
        blocks = load(BLOCKS, None)
        if blocks is None:
            raise SystemExit("no vectors/e3s/blocks.json: run e3prep.py first")
        for s in blocks["stations"]:
            f = s["figures"]
            if f.get("refused"):
                sets["stations"][s["station"]] = {"refused": f["refused"]}
                continue
            sets["stations"][s["station"]] = entry(f["amplitude_num"], f["amplitude_den"], rule["block_frames"],
                                                   rule["use"]["training"], rule["use"]["held_out"], rule["layout"])
    else:
        raise SystemExit(__doc__)
    with open(SETS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(sets, f, indent=1)
        f.write("\n")
    print("wrote vectors/e3s/injection_sets.json: stations %s; short %s"
          % (sorted(sets["stations"]), "yes" if sets["short"] else "no"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

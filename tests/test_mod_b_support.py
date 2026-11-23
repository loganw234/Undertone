"""What MOD-B's test files share. It holds no gate.

Three kinds of thing:

- readers of the frozen vectors under vectors/mod-b/, whose expected answers were worked by hand;
- the datapath's definition WRITTEN OUT A SECOND TIME (`direct_scores`, `forge`), using nothing of
  `model/detector.py`, `model/weights.py` or `model/scorer.py`. It is the independent code the vectors'
  rule allows; it is deliberately the slow, memoryless form, so it shares no structure with the core's
  delay lines and running sums;
- `run_case` and `compare`, which every gate's check and its control both go through.

This file's own tests hold the second-time definition to the hand-worked vectors, so that the "independent
code" is itself held by something worked by hand.
"""
import hashlib
import json
import os
import random

import pytest

from spec import constants as C
from model import records, weights
from model.detector import Core

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = sorted(C.PROFILES)
SETTLING = 1 << C.FLAGS["settling"]
OVERFLOW = 1 << C.FLAGS["overflow"]


def vector(name):
    with open(os.path.join(ROOT, "vectors", "mod-b", name), encoding="utf-8") as f:
        return json.load(f)


def cases(name, profile):
    return [c for c in vector(name)["cases"] if c["profile"] == profile]


def parts(config):
    """A vector's config as `weights.pack`'s arguments after the profile."""
    filters = [{int(c): tuple(row) for c, row in f.items()} for f in config["filters"]]
    return filters, tuple(config["head"]), config["rectifier"], config["pool"], config["score_shift"]


def blob_of(profile, config, pack=None):
    return (pack or weights.pack)(profile, *parts(config))


def run_case(case, core=Core, pack=None):
    """The records a core gives for a vector's case, doing the case's swaps where it says."""
    c = core(blob_of(case["profile"], case["config"], pack))
    out = []
    for n, frame in enumerate(case["frames"]):
        for swap in case.get("swaps", []):
            if swap["after"] == n:
                if swap["write"] is not None:
                    c.write_shadow(blob_of(case["profile"], dict(case["config"], **swap["write"]), pack))
                c.commit(swap["at"])
        out.append(c.step(tuple(frame)))
    return out


def compare(name, got, expected):
    """Findings, one per record whose canonical bytes differ. Records are equal when their bytes are."""
    findings = []
    if len(got) != len(expected):
        findings.append("%s: %d records, the vector has %d" % (name, len(got), len(expected)))
    for g, e in zip(got, expected):
        if records.pack("score", g) != records.pack("score", e):
            findings.append("%s: record %d is %r, the vector says %r" % (name, e["index"], g, e))
    return findings


def check_vectors(name, profile, core=Core, pack=None):
    """(findings, cases checked) for one vector file under one profile."""
    todo = cases(name, profile)
    findings = []
    for case in todo:
        findings += compare(case["name"], run_case(case, core, pack), case["records"])
    return findings, len(todo)


# ---------------------------------------------------- the definition, a second time

def direct_scores(config, frames):
    """score[i] for every frame, straight from the definition, remembering nothing between outputs."""
    filters, head, rectifier, pool, shift = parts(config)
    taps = len(next(iter(filters[0].values())))

    def x(c, m):
        return frames[m][c] if m >= 0 else 0

    def r(k, i):
        if i < 0:
            return 0
        y = 0
        for c, row in filters[k].items():
            for j in range(taps):
                y += row[j] * x(c, i - (taps - 1) + j)
        return abs(y) if rectifier == 1 else y

    out = []
    for i in range(len(frames)):
        a = 0
        for k in range(len(filters)):
            z = 0
            for m in range(pool):
                z += r(k, i - m)
            a += head[k] * z
        out.append(a // 2 ** shift)          # Python's // is floor division, toward minus infinity
    return out


def forge(profile, filters, head, rectifier, pool, score_shift, *, magic=b"UNDTBLOB", version=1, reserved=0,
          nfilters=None, ntaps=None, masks=None, name=None, extra=b"", rehash=True):
    """A blob's bytes from the layout, written out here and not taken from `weights.pack`.

    The keyword arguments let a test write a header that disagrees with the body, with a correct hash,
    which `weights.pack` would refuse to do.
    """
    taps = len(next(iter(filters[0].values()))) if filters else 0
    name = profile.encode("ascii") if name is None else name
    out = magic + version.to_bytes(2, "little") + bytes([len(name)]) + name
    out += (len(filters) if nfilters is None else nfilters).to_bytes(2, "little")
    out += (taps if ntaps is None else ntaps).to_bytes(2, "little")
    out += bytes([rectifier, score_shift]) + pool.to_bytes(4, "little") + reserved.to_bytes(4, "little")
    for n, f in enumerate(filters):
        mask = sum(1 << c for c in f) if masks is None else masks[n]
        out += mask.to_bytes(2, "little")
    for f in filters:
        for c in sorted(f):
            for v in f[c]:
                out += (v % (1 << 32)).to_bytes(4, "little")      # two's complement, 32 bits
    for v in head:
        out += (v % (1 << 32)).to_bytes(4, "little")
    out += extra
    return out + hashlib.sha256(out).digest() if rehash else out


def varied_frames(profile, n, seed, small=False):
    """n frames for the profile, seeded, with a different value in every channel and no zero sample."""
    p = C.PROFILES[profile]
    rng = random.Random(seed)
    lo, hi = (-9, 9) if small else (p["sample_min"], p["sample_max"])
    out = []
    while len(out) < n:
        frame = tuple(rng.randint(lo, hi) for _ in range(p["channels"]))
        if 0 not in frame and len(set(frame)) == len(frame):
            out.append(frame)
    return out


def a_config(profile, taps=2, pool=1, rectifier=0, score_shift=0):
    """A small valid configuration: one filter on the profile's last channel."""
    last = C.PROFILES[profile]["channels"] - 1
    return {"filters": [{str(last): list(range(1, taps + 1))}], "head": [1], "rectifier": rectifier,
            "pool": pool, "score_shift": score_shift}


# ------------------------------------------------- this file's own tests

@pytest.mark.parametrize("profile", PROFILES)
def test_mod_b_support_the_definition_written_out_equals_the_hand_worked_vectors(profile):
    """The second-time definition is itself held to the hand-worked cases, so it can judge the core elsewhere."""
    todo = cases("datapath.json", profile)
    assert len(todo) >= 4
    for case in todo:
        frames = [tuple(f) for f in case["frames"]]
        assert direct_scores(case["config"], frames) == [r["score"] for r in case["records"]], case["name"]


def test_mod_b_support_the_forged_blob_equals_the_hand_worked_bytes():
    todo = vector("blob.json")["cases"]
    assert {c["profile"] for c in todo} == set(PROFILES)
    for case in todo:
        by_hand = bytes.fromhex("".join(h for _what, h in case["bytes"]))
        assert forge(case["profile"], *parts(case["config"]), rehash=False) == by_hand, case["name"]


def test_mod_b_support_varied_frames_differ_by_channel_and_hold_no_zero():
    for profile in PROFILES:
        for frame in varied_frames(profile, 50, seed=1):
            assert len(frame) == C.PROFILES[profile]["channels"]
            assert 0 not in frame and len(set(frame)) == len(frame)

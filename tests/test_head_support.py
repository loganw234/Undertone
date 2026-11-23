"""What HEAD's test files share. It holds no gate.

Four kinds of thing:

- readers of the frozen vectors under vectors/head/, whose expected answers were worked by hand;
- the head's definition WRITTEN OUT A SECOND TIME (`direct_records`, `forge`), using nothing of
  `model/detector.py` or `model/weights.py`. It is the independent code the vectors' rule allows: the slow,
  memoryless form, with the wrap and the sticky flag written here again. It reads `spec.constants`, which is
  shared by design;
- `setting`: a configuration with no hidden layer, written as the version 2 configuration that is the same head;
- `blob_of`, `run_case` and `check_cases`, the harness, which does import the model.

This file's own tests hold the second-time definition to the hand-worked vectors, MOD-B's and HEAD's, so that
the "independent code" is itself held by something worked by hand.
"""
import hashlib
import json
import os

import pytest

from spec import constants as C
from model import weights
from model.detector import Core

import test_mod_b_support as S

PROFILES = S.PROFILES
SETTLING, OVERFLOW = S.SETTLING, S.OVERFLOW
PASS, ABS = C.RECTIFIERS["pass"], C.RECTIFIERS["abs"]
SCORE_BITS = dict((f[0], f[1]) for f in C.RECORDS["score"])["score"]
SCORE_MIN, SCORE_MAX = -(1 << (SCORE_BITS - 1)), (1 << (SCORE_BITS - 1)) - 1


def vector(name):
    with open(os.path.join(S.ROOT, "vectors", "head", name), encoding="utf-8") as f:
        return json.load(f)


def cases(name, profile):
    return [c for c in vector(name)["cases"] if c["profile"] == profile]


def parts(config):
    """A vector's config as `weights.pack`'s arguments after the profile: (positional, keywords)."""
    filters = [{int(c): tuple(row) for c, row in f.items()} for f in config["filters"]]
    args = (filters, tuple(config["head"]), config["rectifier"], config["pool"], config["score_shift"])
    if "hidden" not in config:
        return args, {}
    return args, {"hidden": tuple(tuple(unit) for unit in config["hidden"]), "hidden_shift": config["hidden_shift"],
                  "between": config["between"]}


def blob_of(profile, config):
    args, keywords = parts(config)
    return weights.pack(profile, *args, **keywords)


def setting(config):
    """A configuration with no hidden layer, as the version 2 configuration that is the same head.

    One unit whose weights are the old head weights, the old score shift as the hidden shift, pass between,
    a head weight of 1 and a score shift of 0.
    """
    assert "hidden" not in config
    return dict(config, hidden=[list(config["head"])], hidden_shift=config["score_shift"], between=PASS, head=[1],
                score_shift=0)


def run_case(case, core=Core, change=None):
    """The records a core gives for a vector's case, doing the case's swaps where it says.

    `change` rewrites every configuration the case uses, the first and each one a swap writes, before it is
    packed: `setting`, or a control's nearly-right version of it.
    """
    change = change or (lambda config: config)
    c = core(blob_of(case["profile"], change(case["config"])))
    out = []
    for n, frame in enumerate(case["frames"]):
        for swap in case.get("swaps", []):
            if swap["after"] == n:
                if swap["write"] is not None:
                    c.write_shadow(blob_of(case["profile"], change(dict(case["config"], **swap["write"]))))
                c.commit(swap["at"])
        out.append(c.step(tuple(frame)))
    return out


def check_cases(todo, core=Core, change=None):
    """(findings, cases checked): each case's records against the ones worked by hand, byte for byte."""
    findings = []
    for case in todo:
        findings += S.compare(case["name"], run_case(case, core, change), case["records"])
    return findings, len(todo)


# ---------------------------------------------------- the definition, a second time

def wrap(v):
    """v modulo 2^SCORE_BITS, as two's complement."""
    return (v - SCORE_MIN) % (1 << SCORE_BITS) + SCORE_MIN


def direct_records(config, frames):
    """The score record for every frame, straight from the definition; nothing is kept between outputs but the flag.

    With "hidden" in the configuration: steps 4a to 4d of model/detector.py's docstring. Without: step 4.
    A hidden value or a score that does not fit SCORE_BITS is reduced, and the flag is set from that output on.
    """
    filters = [{int(c): list(row) for c, row in f.items()} for f in config["filters"]]
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
        return abs(y) if config["rectifier"] == ABS else y

    out, overflowed = [], False
    for i in range(len(frames)):
        z = [sum(r(k, i - m) for m in range(config["pool"])) for k in range(len(filters))]
        if "hidden" in config:
            between = []
            for unit in config["hidden"]:
                assert len(unit) == len(z)
                t = sum(g * zk for g, zk in zip(unit, z)) // 2 ** config["hidden_shift"]     # // is floor division
                if not SCORE_MIN <= t <= SCORE_MAX:
                    overflowed, t = True, wrap(t)
                between.append(abs(t) if config["between"] == ABS else t)
            assert len(config["head"]) == len(between)
            a = sum(o * b for o, b in zip(config["head"], between))
        else:
            a = sum(h * zk for h, zk in zip(config["head"], z))
        v = a // 2 ** config["score_shift"]
        if not SCORE_MIN <= v <= SCORE_MAX:
            overflowed, v = True, wrap(v)
        out.append({"index": i, "epoch": 0, "flags": OVERFLOW if overflowed else 0, "score": v})
    return out


def forge(profile, config, *, magic=b"UNDTBLOB", version=2, nfilters=None, nhidden=None, hidden_shift=None, between=None,
          masks=None, extra=b"", rehash=True):
    """A version 2 blob's bytes from the layout, written out here and not taken from `weights.pack`.

    The keyword arguments let a test write a header that disagrees with the body, with a correct hash,
    which `weights.pack` would refuse to do.
    """
    filters = [{int(c): list(row) for c, row in f.items()} for f in config["filters"]]
    name = profile.encode("ascii")
    out = magic + version.to_bytes(2, "little") + bytes([len(name)]) + name
    out += (len(filters) if nfilters is None else nfilters).to_bytes(2, "little")
    out += len(next(iter(filters[0].values()))).to_bytes(2, "little")
    out += bytes([config["rectifier"], config["score_shift"]]) + config["pool"].to_bytes(4, "little")
    out += (len(config["hidden"]) if nhidden is None else nhidden).to_bytes(2, "little")
    out += bytes([config["hidden_shift"] if hidden_shift is None else hidden_shift,
                  config["between"] if between is None else between])
    for n, f in enumerate(filters):
        out += (sum(1 << c for c in f) if masks is None else masks[n]).to_bytes(2, "little")
    words = [v for f in filters for c in sorted(f) for v in f[c]]
    words += [v for unit in config["hidden"] for v in unit] + list(config["head"])
    for v in words:
        out += (v % (1 << 32)).to_bytes(4, "little")              # two's complement, 32 bits
    out += extra
    return out + hashlib.sha256(out).digest() if rehash else out


def a_config(profile, units=3, hidden_shift=0, between=ABS, pool=1, score_shift=0, rectifier=PASS):
    """A small valid configuration with a hidden layer: two filters, the first on the profile's last channel."""
    last = str(C.PROFILES[profile]["channels"] - 1)
    return {"filters": [{last: [1, 2, -3]}, {"0": [4, -1, 2]}], "hidden": [[3 + 2 * j, -5 + 3 * j] for j in range(units)],
            "hidden_shift": hidden_shift, "between": between, "head": [7 - 4 * j for j in range(units)],
            "rectifier": rectifier, "pool": pool, "score_shift": score_shift}


# ------------------------------------------------- this file's own tests

@pytest.mark.parametrize("profile", PROFILES)
def test_head_support_the_definition_written_out_equals_the_hand_worked_vectors(profile):
    """The second-time definition is itself held to the hand-worked cases, HEAD's and MOD-B's, so it can judge the core."""
    todo = cases("datapath.json", profile)
    assert len(todo) >= 2
    for case in todo + S.cases("datapath.json", profile):
        frames = [tuple(f) for f in case["frames"]]
        assert direct_records(case["config"], frames) == case["records"], case["name"]
    assert {c["config"]["between"] for c in todo} == {PASS, ABS}, "a hand-worked case for each thing that can stand between"


def test_head_support_the_forged_blob_equals_the_hand_worked_bytes():
    todo = vector("blob.json")["cases"]
    assert {c["profile"] for c in todo} == set(PROFILES)
    for case in todo:
        by_hand = bytes.fromhex("".join(h for _what, h in case["bytes"]))
        assert forge(case["profile"], case["config"], rehash=False) == by_hand, case["name"]


def test_head_support_wrap_is_the_value_modulo_the_fields_range():
    assert wrap(SCORE_MAX) == SCORE_MAX and wrap(SCORE_MIN) == SCORE_MIN and wrap(0) == 0
    assert wrap(SCORE_MAX + 1) == SCORE_MIN and wrap(SCORE_MIN - 1) == SCORE_MAX
    assert wrap(2 * SCORE_MIN) == 0 and wrap(3 * (SCORE_MAX + 1) + 5) == SCORE_MIN + 5

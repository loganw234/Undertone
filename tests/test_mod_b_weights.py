"""MOD-B's tests of the blob's bytes, of what the quantising rule guarantees, and that model/ holds no float.

The blob's known answers are vectors/mod-b/blob.json, worked by hand; their SHA-256 is computed here with
hashlib from those hand-worked bytes. The quantiser's hand-worked sets are held by the reference-model gate
(test_mod_b_reference.py); here are the properties that hold for every set.
"""
import ast
import hashlib
import os
import random
from fractions import Fraction

import pytest

from spec import constants as C
from model import weights
from model.refusal import Refusal

import test_mod_b_support as S

PROFILES = S.PROFILES
MODULES = ("detector.py", "weights.py", "scorer.py")


def test_mod_b_pack_gives_the_hand_worked_bytes_and_their_hash():
    todo = S.vector("blob.json")["cases"]
    assert {c["profile"] for c in todo} == set(PROFILES)
    for case in todo:
        by_hand = bytes.fromhex("".join(h for _what, h in case["bytes"]))
        blob = S.blob_of(case["profile"], case["config"])
        assert blob[:-32] == by_hand, case["name"]
        assert blob[-32:] == hashlib.sha256(by_hand).digest(), case["name"]
        assert len(blob) == len(by_hand) + 32


def test_mod_b_unpack_gives_back_the_hand_worked_blobs_parts():
    for case in S.vector("blob.json")["cases"]:
        by_hand = bytes.fromhex("".join(h for _what, h in case["bytes"]))
        got = weights.unpack(by_hand + hashlib.sha256(by_hand).digest())
        filters, head, rectifier, pool, score_shift = S.parts(case["config"])
        assert got == {"profile": case["profile"], "filters": tuple(filters), "head": head, "rectifier": rectifier,
                       "pool": pool, "score_shift": score_shift, "sha256": hashlib.sha256(by_hand).hexdigest()}
        assert sorted(got) == ["filters", "head", "pool", "profile", "rectifier", "score_shift", "sha256"]


@pytest.mark.parametrize("profile", PROFILES)
def test_mod_b_pack_equals_the_layout_written_out_on_seeded_configurations(profile):
    """`forge` in test_mod_b_support.py writes the layout a second time; it is held to the hand-worked bytes there."""
    channels = C.PROFILES[profile]["channels"]
    rng = random.Random(99)
    for _ in range(60):
        taps = rng.randint(1, 9)
        filters, rows_left = [], C.MAX_ROWS
        for _k in range(rng.randint(1, 5)):
            read = rng.sample(range(channels), rng.randint(1, min(channels, rows_left)))
            rows_left -= len(read)
            filters.append({c: tuple(rng.randint(C.COEFF_MIN, C.COEFF_MAX) for _ in range(taps)) for c in read})
        args = (filters, tuple(rng.randint(C.COEFF_MIN, C.COEFF_MAX) for _ in filters), rng.randint(0, 1),
                rng.randint(1, C.MAX_POOL), rng.randint(0, C.MAX_SCORE_SHIFT))
        blob = weights.pack(profile, *args)
        assert blob == S.forge(profile, *args)
        back = weights.unpack(blob)
        assert (list(back["filters"]), back["head"], back["rectifier"], back["pool"], back["score_shift"]) == \
            (filters, args[1], args[2], args[3], args[4])
        assert back["sha256"] == blob[-32:].hex()


def test_mod_b_the_order_a_filters_channels_are_given_in_does_not_change_the_blob():
    profile = [p for p in PROFILES if C.PROFILES[p]["channels"] > 1][0]
    a = weights.pack(profile, [{0: (1, 2), 1: (3, 4)}], (1,), 0, 1, 0)
    b = weights.pack(profile, [{1: (3, 4), 0: (1, 2)}], (1,), 0, 1, 0)
    assert a == b
    assert a != weights.pack(profile, [{0: (3, 4), 1: (1, 2)}], (1,), 0, 1, 0), "rows on other channels are another blob"


def test_mod_b_the_mask_field_holds_every_channel_a_profile_may_have():
    """The lead's ruling of 2026-11-23: the mask and the definition must not disagree about the channel count."""
    assert weights.MASK_BITS == 16
    assert max(p["channels"] for p in C.PROFILES.values()) <= weights.MASK_BITS


def test_mod_b_the_quantisers_output_is_within_the_peak_and_the_peak_is_reached():
    rng = random.Random(5)
    for _ in range(200):
        values = [Fraction(rng.randint(-10 ** 6, 10 ** 6), rng.randint(1, 10 ** 4)) for _ in range(rng.randint(1, 12))]
        if not any(values):
            continue
        q = weights.quantise(values)
        peak = max(abs(v) for v in values)
        assert max(abs(v) for v in q) == C.COEFF_MAX == 2 ** (C.COEFF_BITS - 1) - 1
        for v, got in zip(values, q):
            exact = v * C.COEFF_MAX / peak                      # a Fraction: exact
            assert abs(got - exact) <= Fraction(1, 2), "never further than half a step from the exact value"
            if abs(got - exact) == Fraction(1, 2):
                assert got % 2 == 0, "a tie goes to the even integer"
            assert (got > 0) == (v > 0) or got == 0
        assert weights.quantise([-v for v in values]) == tuple(-g for g in q), "the rule is odd: no bias toward either sign"
        assert weights.quantise([v * 7 for v in values]) == q, "and it does not depend on the set's scale"


def test_mod_b_the_quantiser_takes_ints_and_fractions_alike_and_no_float():
    assert weights.quantise([1, Fraction(1, 2)]) == weights.quantise([2, 1]) == (C.COEFF_MAX, 65536)
    for bad in (0.5, True, "1", None):
        with pytest.raises(Refusal) as e:
            weights.quantise([1, bad])
        assert e.value.name == "QUANTISE_INPUT"


@pytest.mark.parametrize("name", MODULES)
def test_mod_b_no_float_can_arise_in_the_models_arithmetic(name):
    """No true division, no float constant, and none of float, math, round, pow or divmod-by-float in the three modules.

    `/` on two ints makes a float; `round` can; `**` with a negative power can. The modules use `//`, `>>`, `divmod`
    on ints and nothing else that divides.
    """
    with open(os.path.join(S.ROOT, "model", name), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Div, ast.Pow)):
            found.append("operator %s" % type(node).__name__)
        if isinstance(node, ast.Constant) and isinstance(node.value, (float, complex)):
            found.append("constant %r at line %d" % (node.value, node.lineno))
        if isinstance(node, ast.Name) and node.id in ("float", "round", "pow", "complex", "math", "statistics", "decimal"):
            found.append("name %s at line %d" % (node.id, node.lineno))
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + ([node.module] if isinstance(node, ast.ImportFrom) else [])
            for n in names:
                if n.split(".")[0] in ("math", "numpy", "statistics", "decimal", "stats", "random", "cmath"):
                    found.append("import of %s at line %d" % (n, node.lineno))
    assert found == []


def test_mod_b_the_no_float_check_sees_a_planted_division():
    """The check above, on a module with one `/` in place of `//`: it must report it."""
    tree = ast.parse("def half(a):\n    return a / 2\n")
    assert any(isinstance(node, ast.Div) for node in ast.walk(tree))
    tree = ast.parse("def half(a):\n    return a // 2\n")
    assert not any(isinstance(node, ast.Div) for node in ast.walk(tree))


@pytest.mark.parametrize("profile", PROFILES)
def test_mod_b_every_score_the_core_gives_is_an_int_and_never_a_bool_or_a_float(profile):
    from model.detector import Core
    config = S.a_config(profile, taps=3, pool=2, rectifier=1, score_shift=3)
    for record in Core(S.blob_of(profile, config)).run(S.varied_frames(profile, 30, seed=1)):
        assert {k: type(v) for k, v in record.items()} == {"index": int, "epoch": int, "flags": int, "score": int}

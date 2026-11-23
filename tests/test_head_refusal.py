"""The refusal gate, for the head's hidden layer: every new way a blob can be wrong is refused, under its own name.

One table of cases, in the form of MOD-B's (tests/test_mod_b_refusal.py): a case is a name and a call made
through that file's `Model`, and the SAME check, its `finding`, makes the call and reports anything but a
Refusal of exactly that name. The controls hand that check MOD-B's two broken models, one that ACCEPTS the
case and one that refuses it under ANOTHER declared name, for every case here; and the shipped code reading a
definition whose two new maxima are one higher.

Blobs whose header disagrees with their body are written by `test_head_support.forge`, from the layout and
with a correct hash, since the model's own `pack` refuses to write them.
"""
import pytest

from spec import constants as C
from model import weights
from model.detector import Core
from model.refusal import Refusal

import test_mod_b_support as S
import test_mod_b_refusal as R
import test_head_support as H

PROFILES = H.PROFILES
PASS, ABS = H.PASS, H.ABS
NEW_NAMES = {"SHAPE_HIDDEN", "SHAPE_HIDDEN_SHIFT", "SHAPE_BETWEEN"}
# Every name a blob with a hidden layer can be refused under for a reason the hidden layer brings.
HEAD_NAMES = NEW_NAMES | {"BLOB_FORMAT", "BLOB_HASH", "RESERVED_BITS", "WEIGHT_COUNT", "WEIGHT_RANGE", "SWAP_SHAPE"}


def good_config(profile):
    """Two filters and three units: the counts differ, so a weight counted against the wrong one shows."""
    last = C.PROFILES[profile]["channels"] - 1
    return {"filters": [{last: (1, 2)}, {0: (3, -1)}], "head": (2, -3, 1), "rectifier": PASS, "pool": 1, "score_shift": 0,
            "hidden": ((1, 2), (3, 4), (-5, 6)), "hidden_shift": 0, "between": ABS}


def table(profile):
    good = good_config(profile)
    nfilters, units = len(good["filters"]), len(good["hidden"])
    old = {k: good[k] for k in ("filters", "rectifier", "pool", "score_shift")}        # the same shape with no hidden layer
    old["head"] = (4, 5)
    out = []

    def case(name, label, call):
        out.append((name, label, call))

    def packing(refusal, label, **changed):
        args = dict(good, **changed)
        case(refusal, "pack: " + label, lambda m: m.pack(profile, **args))

    def forged(refusal, label, config=None, **keywords):
        blob = H.forge(profile, dict(good, **(config or {})), **keywords)
        case(refusal, "unpack: " + label, lambda m: m.unpack(blob))
        case(refusal, "Core: " + label, lambda m: m.Core(blob))

    # -- how many units
    packing("SHAPE_HIDDEN", "no unit", hidden=(), head=())
    packing("SHAPE_HIDDEN", "one unit past the maximum", hidden=((1, 2),) * (C.MAX_HIDDEN + 1), head=(1,) * (C.MAX_HIDDEN + 1))
    for bad in (7, "units", True):
        packing("SHAPE_HIDDEN", "hidden units that are %r" % (bad,), hidden=bad)
    case("SHAPE_HIDDEN", "pack: a hidden shift and no hidden layer", lambda m: m.pack(profile, **old, hidden_shift=0))
    case("SHAPE_HIDDEN", "pack: a between and no hidden layer", lambda m: m.pack(profile, **old, between=PASS))
    forged("SHAPE_HIDDEN", "one unit past the maximum", {"hidden": ((1, 2),) * (C.MAX_HIDDEN + 1), "head": (1,) * (C.MAX_HIDDEN + 1)})
    forged("SHAPE_HIDDEN", "a header that says 65535 units", nhidden=65535)

    # -- the hidden shift, and what stands between
    for bad in (C.MAX_HIDDEN_SHIFT + 1, -1, True, None, 1.0):
        packing("SHAPE_HIDDEN_SHIFT", "a hidden shift of %r" % (bad,), hidden_shift=bad)
    for bad in (C.MAX_HIDDEN_SHIFT + 1, 255):
        forged("SHAPE_HIDDEN_SHIFT", "a hidden shift of %d" % bad, hidden_shift=bad)
    for bad in (max(C.RECTIFIERS.values()) + 1, -1, True, None):
        packing("SHAPE_BETWEEN", "the undeclared between code %r" % (bad,), between=bad)
    for bad in (max(C.RECTIFIERS.values()) + 1, 255):
        forged("SHAPE_BETWEEN", "the undeclared between code %d" % bad, between=bad)

    # -- the blob: its version, and lengths that disagree with its header
    forged("BLOB_FORMAT", "version 2 with no hidden unit, the weights as they were", nhidden=0)
    forged("BLOB_FORMAT", "version 2 with no hidden unit, no hidden weight and no head weight", {"hidden": (), "head": ()})
    old_layout = S.forge(profile, old["filters"], old["head"], old["rectifier"], old["pool"], old["score_shift"], version=2)
    case("BLOB_FORMAT", "unpack: version 1's layout under the number 2", lambda m: m.unpack(old_layout))
    for version in (3, 0, 258):
        forged("BLOB_FORMAT", "version %d" % version, version=version)
    # version 2's layout under the number 1: the layer's shape lies where version 1 reserves four bytes ...
    forged("RESERVED_BITS", "version 2's layout under the number 1", version=1)
    # ... and with those four bytes zeroed it is a version 1 blob whose length disagrees with its header
    forged("BLOB_FORMAT", "version 2's layout under the number 1, the layer's shape zeroed", version=1, nhidden=0, between=0)
    forged("BLOB_FORMAT", "four bytes too many", extra=bytes(4))
    forged("BLOB_FORMAT", "a header that says one unit more than the body holds", nhidden=units + 1)
    forged("BLOB_FORMAT", "a header that says one unit fewer than the body holds", nhidden=units - 1)
    forged("BLOB_FORMAT", "a head sized for the filters, not for the units", {"head": (1,) * nfilters})
    forged("BLOB_FORMAT", "a unit one weight short", {"hidden": ((1, 2), (3, 4), (5,))})
    whole = H.forge(profile, good)
    for position in range(len(whole)):
        damaged = whole[:position] + bytes([whole[position] ^ 0x10]) + whole[position + 1:]
        case("BLOB_HASH", "unpack: one bit changed in byte %d" % position, lambda m, damaged=damaged: m.unpack(damaged))

    # -- the weights
    packing("WEIGHT_COUNT", "a unit with a weight too many", hidden=((1, 2), (3, 4, 5), (-5, 6)))
    packing("WEIGHT_COUNT", "a unit with a weight too few", hidden=((1, 2), (3,), (-5, 6)))
    packing("WEIGHT_COUNT", "a unit that is not a list", hidden=((1, 2), 3, (-5, 6)))
    packing("WEIGHT_COUNT", "a head weight too many", head=(2, -3, 1, 1))
    packing("WEIGHT_COUNT", "a head sized for the filters, not for the units", head=(1,) * nfilters)
    packing("WEIGHT_COUNT", "no head weight", head=())
    for bad in (C.COEFF_MAX + 1, C.COEFF_MIN - 1):
        packing("WEIGHT_RANGE", "the hidden weight %d" % bad, hidden=((1, 2), (3, bad), (-5, 6)))
        packing("WEIGHT_RANGE", "the head weight %d" % bad, head=(2, -3, bad))
        forged("WEIGHT_RANGE", "the hidden weight %d" % bad, {"hidden": ((1, 2), (bad, 4), (-5, 6))})
        forged("WEIGHT_RANGE", "the head weight %d" % bad, {"head": (bad, -3, 1)})
    for bad in (True, 1.0, None, "1"):
        packing("WEIGHT_RANGE", "the hidden weight %r" % (bad,), hidden=((1, 2), (3, 4), (bad, 6)))
        packing("WEIGHT_RANGE", "the head weight %r" % (bad,), head=(2, bad, 1))

    # -- the swap: the hidden layer's shape is shape
    def shadow(running, written, label):
        case("SWAP_SHAPE", "write_shadow: " + label, lambda m: m.Core(running).write_shadow(written))

    one, other = H.blob_of(profile, good), weights.pack(profile, **old)
    shadow(one, other, "a blob with no hidden layer onto a core that has one")
    shadow(other, one, "a blob with a hidden layer onto a core that has none")
    shadow(other, H.blob_of(profile, H.setting(old)), "a version 1 core's own version 2 setting")
    shadow(one, H.blob_of(profile, dict(good, hidden=good["hidden"][:2], head=good["head"][:2])), "another count of units")
    shadow(one, H.blob_of(profile, dict(good, hidden_shift=1)), "another hidden shift")
    shadow(one, H.blob_of(profile, dict(good, between=PASS)), "another between")
    return out


# ------------------------------------------------------------------ the gate

@pytest.mark.parametrize("profile", PROFILES)
def test_gate_refusal__every_new_way_a_blob_can_be_wrong_is_refused_under_its_own_name(profile):
    cases = table(profile)
    reported = ["%s (%s): %s" % (c[0], c[1], R.finding(c, R.Model)) for c in cases if R.finding(c, R.Model) is not None]
    assert reported == []
    assert {c[0] for c in cases} == HEAD_NAMES, "every name the hidden layer can raise has a case, and no case names another"
    assert NEW_NAMES <= set(C.REFUSALS)
    for name in NEW_NAMES:
        labels = [c[1] for c in cases if c[0] == name]
        assert any(l.startswith("pack: ") for l in labels) and any(l.startswith("unpack: ") for l in labels) \
            and any(l.startswith("Core: ") for l in labels), "%s is reached through pack, unpack and Core" % name
    assert len(cases) > 150


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_refusal__what_is_just_inside_each_new_bound_is_accepted(profile):
    """The other direction: at each maximum and each minimum the model answers, and `pack` writes the layout."""
    p = C.PROFILES[profile]
    good = good_config(profile)
    accepted = 0
    for changed in (dict(hidden=((C.COEFF_MIN, C.COEFF_MAX),), head=(C.COEFF_MAX,)),
                    dict(hidden=((1, 2),) * C.MAX_HIDDEN, head=(C.COEFF_MIN,) * C.MAX_HIDDEN),
                    dict(hidden_shift=C.MAX_HIDDEN_SHIFT), dict(hidden_shift=0),
                    dict(between=PASS), dict(between=ABS), dict(score_shift=C.MAX_SCORE_SHIFT, hidden_shift=C.MAX_HIDDEN_SHIFT)):
        args = dict(good, **changed)
        blob = weights.pack(profile, **args)
        assert blob == H.forge(profile, args), "pack writes the layout"
        back = weights.unpack(blob)
        assert sorted(back) == ["between", "filters", "head", "hidden", "hidden_shift", "pool", "profile", "rectifier",
                                "score_shift", "sha256"]
        assert weights.pack(profile, back["filters"], back["head"], back["rectifier"], back["pool"], back["score_shift"],
                            hidden=back["hidden"], hidden_shift=back["hidden_shift"], between=back["between"]) == blob
        assert (back["hidden"], back["head"]) == (tuple(args["hidden"]), tuple(args["head"]))
        Core(blob).step(tuple(p["sample_min"] if c % 2 else p["sample_max"] for c in range(p["channels"])))
        accepted += 1
    assert accepted == 7


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_refusal__each_version_is_read_as_itself_and_a_blob_without_a_hidden_layer_is_version_1(profile):
    good = good_config(profile)
    with_layer = weights.pack(profile, **good)
    without = weights.pack(profile, good["filters"], (4, 5), good["rectifier"], good["pool"], good["score_shift"])
    assert int.from_bytes(with_layer[8:10], "little") == weights.VERSION_HIDDEN == 2
    assert int.from_bytes(without[8:10], "little") == weights.VERSION == 1
    assert without == S.forge(profile, good["filters"], (4, 5), good["rectifier"], good["pool"], good["score_shift"]), \
        "a call with no hidden layer writes round 1's bytes"
    assert sorted(weights.unpack(without)) == ["filters", "head", "pool", "profile", "rectifier", "score_shift", "sha256"]
    assert weights.shape(weights.unpack(with_layer))[:7] == weights.shape(weights.unpack(without))
    assert weights.shape(weights.unpack(with_layer))[7:] == (3, 0, ABS)
    assert Core(with_layer).hidden == 3 and Core(without).hidden == 0
    # the first four bytes of the two fixed headers' last field: reserved in one, the layer's shape in the other
    at = weights.NAME_AT + len(profile) + weights.FIXED_BYTES - 4
    assert without[at:at + 4] == bytes(4) and with_layer[at:at + 4] == bytes([3, 0, 0, ABS])


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_refusal__the_order_of_the_new_checks_is_the_documented_one(profile):
    """Two things wrong at once: the name is the one the documented order reaches first."""
    good = good_config(profile)
    last = C.PROFILES[profile]["channels"] - 1

    def name_of(call):
        with pytest.raises(Refusal) as e:
            call()
        return e.value.name

    def unpacked(config=None, **keywords):
        return name_of(lambda: weights.unpack(H.forge(profile, dict(good, **(config or {})), **keywords)))

    def packed(**changed):
        return name_of(lambda: weights.pack(profile, **dict(good, **changed)))

    assert unpacked(nhidden=0, nfilters=0) == "BLOB_FORMAT"                     # no unit under version 2, before the filters
    assert unpacked({"pool": 0}, nhidden=C.MAX_HIDDEN + 1) == "SHAPE_POOL"      # the pool before the units
    assert unpacked(nhidden=C.MAX_HIDDEN + 1, hidden_shift=99) == "SHAPE_HIDDEN"
    assert unpacked(hidden_shift=99, between=9) == "SHAPE_HIDDEN_SHIFT"
    assert unpacked(between=9, nfilters=C.MAX_FILTERS) == "SHAPE_BETWEEN"       # before the masks' length
    assert unpacked(between=9, masks=[0, 0]) == "SHAPE_BETWEEN"                 # before a mask
    assert unpacked({"hidden": ((1, 2), (3, 4), (1 << 20, 6))}, extra=bytes(4)) == "BLOB_FORMAT"   # the length before a weight
    damaged = H.forge(profile, good, nhidden=0)
    assert name_of(lambda: weights.unpack(damaged[:-1] + bytes([damaged[-1] ^ 1]))) == "BLOB_HASH"  # the hash before anything

    assert packed(filters=[{last: ()}, {0: ()}], hidden=()) == "SHAPE_TAPS"     # the taps before the units
    assert packed(hidden=(), head=()) == "SHAPE_HIDDEN"                         # the units before any count of weights
    assert packed(hidden=((1, 2), (3,), (-5, 6)), rectifier=9) == "WEIGHT_COUNT"
    assert packed(head=(1,), rectifier=9) == "WEIGHT_COUNT"
    assert packed(pool=0, hidden_shift=99) == "SHAPE_POOL"
    assert packed(hidden_shift=99, between=9) == "SHAPE_HIDDEN_SHIFT"
    assert packed(between=9, head=(1 << 20, 1, 1)) == "SHAPE_BETWEEN"

    core = Core(weights.pack(profile, **good))
    core.commit(5)
    assert name_of(lambda: core.write_shadow(H.blob_of(profile, dict(good, between=PASS)))) == "SWAP_PENDING"
    core = Core(weights.pack(profile, **good))
    assert name_of(lambda: core.write_shadow(H.forge(profile, good, between=9))) == "SHAPE_BETWEEN"   # the blob's own, before its shape


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_refusal__a_refused_shadow_changes_nothing_in_a_core_with_a_hidden_layer(profile):
    config = H.a_config(profile, pool=2, hidden_shift=1)
    frames = S.varied_frames(profile, 10, seed=21)
    plain = list(Core(H.blob_of(profile, config)).run(frames))
    core = Core(H.blob_of(profile, config))
    got = []
    for i, frame in enumerate(frames):
        if i == 4:
            for other in (dict(config, hidden_shift=2), dict(config, between=PASS),
                          dict(config, hidden=config["hidden"][:2], head=config["head"][:2])):
                with pytest.raises(Refusal) as e:
                    core.write_shadow(H.blob_of(profile, other))
                assert e.value.name == "SWAP_SHAPE"
        got.append(core.step(frame))
    assert S.compare("after refused shadows", got, plain) == []
    assert S.compare("and the definition", plain, H.direct_records(config, frames)) == []


# --------------------------------------------------------------- the controls

@pytest.mark.parametrize("profile", PROFILES)
def test_control_refusal__a_model_that_accepts_a_new_case_is_caught_for_every_case(profile):
    cases = table(profile)
    missed = [c[:2] for c in cases if R.finding(c, R.broken_model(c[0], "accepts")) != "accepted, not refused as %s" % c[0]]
    assert missed == []
    for name in sorted(NEW_NAMES):
        one = [c for c in cases if c[0] == name][-1]
        print("CONTROL refusal, accepts, %s: %d cases, each reported; for example %s (%s): %s"
              % (profile, len(cases), one[0], one[1], R.finding(one, R.broken_model(one[0], "accepts"))))


@pytest.mark.parametrize("profile", PROFILES)
def test_control_refusal__a_model_that_refuses_a_new_case_under_the_wrong_name_is_caught_for_every_case(profile):
    cases = table(profile)
    missed = [c[:2] for c in cases if R.finding(c, R.broken_model(c[0], "renames")) != "refused as RECORD_KIND, not %s" % c[0]]
    assert missed == []
    for name in sorted(NEW_NAMES):
        one = [c for c in cases if c[0] == name][-1]
        print("CONTROL refusal, wrong name, %s: %d cases, each reported; for example %s (%s): %s"
              % (profile, len(cases), one[0], one[1], R.finding(one, R.broken_model(one[0], "renames"))))


@pytest.mark.parametrize("profile", PROFILES)
def test_control_refusal__a_model_built_with_a_new_maximum_one_higher_is_caught(profile, monkeypatch):
    """Not a wrapper: the shipped code reading a definition whose hidden-layer maxima are one higher."""
    cases = table(profile)                                   # built against the true maxima, before the patch
    for constant, name in (("MAX_HIDDEN", "SHAPE_HIDDEN"), ("MAX_HIDDEN_SHIFT", "SHAPE_HIDDEN_SHIFT")):
        with monkeypatch.context() as patch:
            patch.setattr(C, constant, getattr(C, constant) + 1)
            reported = [(c[1], R.finding(c, R.Model)) for c in cases if c[0] == name]
        seen = [r for r in reported if r[1] is not None]
        assert seen, "a %s one higher was not seen" % constant
        assert [R.finding(c, R.Model) for c in cases if c[0] == name] == [None] * len(reported), "and the shipped model is whole again"
        print("CONTROL refusal, %s one higher, %s: %d case(s) reported; for example %s: %s" % (constant, profile, len(seen), *seen[0]))

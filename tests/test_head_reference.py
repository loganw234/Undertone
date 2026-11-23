"""The reference-model gate, for the head's hidden layer.

Three things are held here.

1. A core with a hidden layer gives the records worked by hand in vectors/head/datapath.json, and the records
   of the definition written out a second time (`direct_records` in test_head_support.py).
2. PART 1 OF THE PLAN'S TEST: today's head is one setting of the new one. Every hand-worked case of round 1
   (vectors/mod-b/datapath.json and swap.json), rewritten as its version 2 setting and run THROUGH THE HIDDEN
   STAGES, gives round 1's hand-worked records, byte for byte; so it does at the score's boundary, where the
   field wraps. A seeded sweep then runs random version 1 configurations on both routes.
3. One flipped bit of a hidden weight or a head weight reaches a score, where the unit reaches the score.

Each control builds something wrong in ONE place, as a subclass or a changed configuration made here, runs the
SAME check, and asserts that the check names a miss.
"""
import copy
import random

import pytest

from spec import constants as C
from model import weights
from model.detector import Core

import test_mod_b_support as S
import test_mod_b_overflow as O
import test_head_support as H

PROFILES = H.PROFILES
PASS, ABS = H.PASS, H.ABS


def old_cases(profile):
    """Round 1's hand-worked cases for the profile: the datapath's and the swap's. Every one has no hidden layer."""
    return S.cases("datapath.json", profile) + S.cases("swap.json", profile)


# ------------------------------------------------------------------ the gate

@pytest.mark.parametrize("profile", PROFILES)
def test_gate_reference_model__hidden_layer_records_equal_the_hand_worked_vectors(profile):
    todo = H.cases("datapath.json", profile)
    findings, n = H.check_cases(todo)
    assert findings == []
    assert n >= 2, "a profile with no hand-worked case would pass while testing nothing"
    for case in todo:
        assert Core(H.blob_of(profile, case["config"])).hidden == len(case["config"]["hidden"]) >= 2
        assert any(r["score"] < 0 for r in case["records"]) and any(r["score"] != 0 for r in case["records"])


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_reference_model__round_1s_vectors_through_the_hidden_stages_as_their_version_2_setting(profile):
    """Part 1. The expected records are MOD-B's, worked by hand; the route is the hidden one."""
    todo = old_cases(profile)
    findings, n = H.check_cases(todo, change=H.setting)
    assert findings == []
    assert n >= 6, "round 1's datapath cases and its swap cases, for this profile"
    for case in todo:
        assert Core(H.blob_of(profile, case["config"])).hidden == 0, "as round 1 wrote it: no hidden layer, today's two lines"
        through = Core(H.blob_of(profile, H.setting(case["config"])))
        assert (through.hidden, through.hidden_shift, through.between, through.shift) == (1, case["config"]["score_shift"], PASS, 0)
    assert any(case["config"]["score_shift"] > 0 for case in todo), "a case whose shift moves into the hidden stage"
    assert any(r["flags"] & S.SETTLING for case in todo for r in case["records"]), "and one that crosses a swap"


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_reference_model__the_setting_is_exact_at_the_scores_boundary_where_the_field_wraps(profile):
    """Why the hidden value has the score field's width: the setting gives today's wrapped scores and today's flag.

    MOD-B's cheap boundary configuration: the head sum reaches exactly the lowest score the field holds, then
    passes it. The expected records are the closed form, the true value modulo 2^64, not either route's output.
    """
    blob, frame, fits = O.boundary(profile, pool_factor=2)
    old = weights.unpack(blob)
    through = weights.pack(profile, old["filters"], (1,), old["rectifier"], old["pool"], 0,
                           hidden=(old["head"],), hidden_shift=old["score_shift"], between=PASS)
    quiet = tuple(0 if v == C.PROFILES[profile]["sample_min"] else v for v in frame)
    frames = [frame] * (fits + 3) + [quiet] * (2 * fits + 2)
    step = C.COEFF_MIN * O.one_product(profile)                           # what one extreme sample adds to the sum

    def true_score(i):               # samples 0 .. fits+2 are extreme, the rest zero; the pool holds the last 2 * fits
        return step * max(0, min(i, fits + 2) - max(0, i - 2 * fits + 1) + 1)

    expected = [{"index": i, "epoch": 0, "flags": S.OVERFLOW if i >= fits else 0, "score": H.wrap(true_score(i))}
                for i in range(len(frames))]
    assert true_score(fits - 1) == H.SCORE_MIN and true_score(fits) < H.SCORE_MIN, "the boundary is where it is said to be"
    assert sum(1 for i in range(len(frames)) if H.wrap(true_score(i)) != true_score(i)) == fits + 2
    core = Core(through)
    assert core.hidden == 1
    assert S.compare("through the hidden stages", list(core.run(frames)), expected) == []
    assert S.compare("today's two lines", list(Core(blob).run(frames)), expected) == []


def sweep_case(profile, rng, loud):
    """A random configuration with no hidden layer, a stream, and at most one swap to other weights of its shape."""
    p = C.PROFILES[profile]
    channels = p["channels"]
    if loud:                         # every value at an extreme, so that the score can pass its field where the profile allows
        nfilters, taps, pool, shift = rng.randint(1, 4), 6, 5, rng.randint(0, 2)
        reads = [list(range(channels))] * nfilters
    else:
        nfilters, taps, pool, shift = rng.randint(1, 4), rng.randint(1, 6), rng.randint(1, 5), rng.randint(0, C.MAX_SCORE_SHIFT)
        reads = [sorted(rng.sample(range(channels), rng.randint(1, channels))) for _ in range(nfilters)]

    def weight_set():
        if loud:
            sign = rng.choice((C.COEFF_MIN, C.COEFF_MAX))
            return {"filters": [{str(c): [C.COEFF_MIN] * taps for c in read} for read in reads], "head": [sign] * nfilters}
        return {"filters": [{str(c): [rng.randint(C.COEFF_MIN, C.COEFF_MAX) for _ in range(taps)] for c in read} for read in reads],
                "head": [rng.randint(C.COEFF_MIN, C.COEFF_MAX) for _ in reads]}

    config = dict(weight_set(), rectifier=rng.randint(0, 1), pool=pool, score_shift=shift)
    if loud:
        frames = [tuple(p["sample_min"] + c for c in range(channels))] * 16
    else:
        frames = S.varied_frames(profile, 24, seed=rng.random())
    swaps = [{"after": 0, "write": weight_set(), "at": rng.randint(1, len(frames) - 1)}] if rng.randint(0, 1) else []
    return {"name": "sweep", "profile": profile, "config": config, "frames": [list(f) for f in frames], "swaps": swaps}


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_reference_model__seeded_version_1_configurations_give_the_same_records_on_both_routes(profile):
    """Part 1, by a seeded sweep. THIS IS AN AGREEMENT OF TWO ROUTES IN ONE MODEL, NOT AN AUTHORITY.

    Each random configuration with no hidden layer is run twice: as round 1's blob, on today's two lines, and as
    its version 2 setting, through the hidden stages. Every record must be equal, byte for byte. Both routes are
    this model's code, so a fault they share passes here; what says either is RIGHT is the hand-worked vectors
    and the second definition, in the tests beside this one. One run in five is loud: every coefficient and
    sample at an extreme, so that where the profile's width allows, the score passes its field on both routes.
    """
    rng = random.Random(20261123)
    tried = swapped = flagged = settling = 0
    for n in range(100):
        case = sweep_case(profile, rng, loud=n % 5 == 0)
        one = H.run_case(case)
        two = H.run_case(case, change=H.setting)
        assert S.compare("sweep %d" % n, two, one) == [], case["config"]
        assert len(one) == len(case["frames"]) and any(r["score"] != 0 for r in one)
        tried += 1
        swapped += bool(case["swaps"])
        flagged += any(r["flags"] & S.OVERFLOW for r in one)
        settling += any(r["flags"] & S.SETTLING for r in one)
    assert tried == 100 and swapped >= 20 and settling >= 10
    # a loud run's largest sum is one head weight times a full pool of full filters; it passes the field or it cannot
    can_pass = -C.COEFF_MIN * 5 * 6 * C.PROFILES[profile]["channels"] * O.one_product(profile) > H.SCORE_MAX
    assert (flagged > 0) == can_pass, "%d flagged runs" % flagged
    print("SWEEP both routes, %s: %d configurations, %d with a swap, %d with settling records, %d with the overflow flag"
          % (profile, tried, swapped, settling, flagged))


def seeded_hidden_config(profile, rng):
    channels = C.PROFILES[profile]["channels"]
    nfilters, taps, units = rng.randint(1, 4), rng.randint(1, 5), rng.randint(1, C.MAX_HIDDEN)
    filters = []
    for _k in range(nfilters):
        read = rng.sample(range(channels), rng.randint(1, channels))
        filters.append({str(c): [rng.randint(C.COEFF_MIN, C.COEFF_MAX) for _ in range(taps)] for c in read})
    return {"filters": filters, "hidden": [[rng.randint(C.COEFF_MIN, C.COEFF_MAX) for _ in filters] for _ in range(units)],
            "hidden_shift": rng.randint(0, C.MAX_HIDDEN_SHIFT), "between": rng.randint(0, 1),
            "head": [rng.randint(C.COEFF_MIN, C.COEFF_MAX) for _ in range(units)],
            "rectifier": rng.randint(0, 1), "pool": rng.randint(1, 5), "score_shift": rng.randint(0, C.MAX_SCORE_SHIFT)}


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_reference_model__seeded_hidden_shapes_and_streams_equal_the_definition_written_out(profile):
    rng = random.Random(20261124)
    tried, units, between = 0, set(), set()
    for _ in range(60):
        config = seeded_hidden_config(profile, rng)
        frames = S.varied_frames(profile, 20, seed=rng.random())
        got = list(Core(H.blob_of(profile, config)).run(frames))
        assert S.compare("seeded hidden shape %d" % tried, got, H.direct_records(config, frames)) == [], config
        tried += 1
        units.add(len(config["hidden"]))
        between.add(config["between"])
    assert tried == 60 and between == {PASS, ABS} and {1, C.MAX_HIDDEN} <= units


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_reference_model__the_largest_hidden_layer_with_every_weight_different_equals_the_definition(profile):
    """MAX_FILTERS filters into MAX_HIDDEN units: a head that paired any weight with the wrong value would show."""
    channels = C.PROFILES[profile]["channels"]
    nfilters = min(C.MAX_FILTERS, C.MAX_ROWS)
    config = {"filters": [{str(k % channels): [k + 1, -2 * k - 3]} for k in range(nfilters)],
              "hidden": [[1000 * j + 7 * k + 1 if (j + k) % 3 else -(1000 * j + 7 * k + 1) for k in range(nfilters)]
                         for j in range(C.MAX_HIDDEN)],
              "hidden_shift": 3, "between": ABS, "head": [(-1) ** j * (50 * j + 11) for j in range(C.MAX_HIDDEN)],
              "rectifier": PASS, "pool": 2, "score_shift": 2}
    weights_seen = [v for unit in config["hidden"] for v in unit]
    assert len(set(weights_seen)) == len(weights_seen) == C.MAX_FILTERS * C.MAX_HIDDEN and len(set(config["head"])) == C.MAX_HIDDEN
    frames = S.varied_frames(profile, 12, seed=77)
    got = list(Core(H.blob_of(profile, config)).run(frames))
    assert S.compare("the largest hidden layer", got, H.direct_records(config, frames)) == []
    assert all(r["flags"] == 0 for r in got) and len({r["score"] for r in got}) == len(got)


# --------------------------------------------------------------- the controls

def other_first_weight(config):
    """The setting with unit 0's first weight one higher, or one lower where it is already the highest."""
    first = config["head"][0]
    return dict(H.setting(config), hidden=[[first + 1 if first < C.COEFF_MAX else first - 1] + list(config["head"][1:])])


NEARLY = {
    "one hidden weight off by one": other_first_weight,
    "the hidden shift off by one": lambda config: dict(H.setting(config), hidden_shift=config["score_shift"] + 1),
    "a head weight of 2 for 1": lambda config: dict(H.setting(config), head=[2]),
    "a score shift of 1 for 0": lambda config: dict(H.setting(config), score_shift=1),
}


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("fault", sorted(NEARLY))
def test_control_reference_model__a_head_that_is_nearly_the_old_one_misses_a_vector_of_round_1s(profile, fault):
    todo = old_cases(profile)
    findings, n = H.check_cases(todo, change=NEARLY[fault])
    missed = sorted({f.split(":")[0] for f in findings})
    assert len(missed) >= n // 2, "at least half of round 1's cases see it: %r" % missed
    print("CONTROL reference-model, nearly the old head (%s), %s: %d of %d cases miss; the first: %s"
          % (fault, profile, len(missed), n, findings[0]))


class BetweenAlwaysPasses(Core):
    def _between(self, t):
        return self._fit(t, "between")


class BetweenAlwaysFolds(Core):
    def _between(self, t):
        return self._fit(-t if t < 0 else t, "between")


class HiddenShiftTowardZero(Core):
    def _hidden(self, u):
        return self._fit(-((-u) >> self.hidden_shift) if u < 0 else u >> self.hidden_shift, "hidden")


class NoHiddenShift(Core):
    def _hidden(self, u):
        return self._fit(u, "hidden")


class HeadWeightsOnTheWrongUnits(Core):
    def _output(self, values, head):
        return super()._output(values, head[::-1])


class UnitWeightsOnTheWrongFilters(Core):
    def _head(self, pooled, head):
        return super()._head(pooled, head[::-1])


class ScoreShiftTowardZero(Core):
    def _score(self, a):
        return self._fit(-((-a) >> self.shift) if a < 0 else a >> self.shift, "score")


BROKEN = [BetweenAlwaysPasses, BetweenAlwaysFolds, HiddenShiftTowardZero, NoHiddenShift, HeadWeightsOnTheWrongUnits,
          UnitWeightsOnTheWrongFilters, ScoreShiftTowardZero]


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("broken", BROKEN, ids=lambda b: b.__name__)
def test_control_reference_model__a_hidden_layer_wrong_in_one_place_misses_a_hand_worked_vector(profile, broken):
    findings, _n = H.check_cases(H.cases("datapath.json", profile), core=broken)
    assert findings != []
    print("CONTROL reference-model, %s, %s: %s" % (broken.__name__, profile, findings[0]))


# ------------------------------------- not hidden: one flipped weight bit

def flipped(value, bit):
    """The COEFF_BITS two's complement value with one bit changed."""
    raw = (value % (1 << C.COEFF_BITS)) ^ (1 << bit)
    return raw - (1 << C.COEFF_BITS) if raw >> (C.COEFF_BITS - 1) else raw


def flips_that_do_not_reach(profile, config, frames):
    """(the flips that left every record unchanged, how many were tried): every bit of every hidden and head weight."""
    base = list(Core(H.blob_of(profile, config)).run(frames))
    misses, tried = [], 0
    places = [("hidden", j, k) for j, unit in enumerate(config["hidden"]) for k in range(len(unit))]
    places += [("head", j, None) for j in range(len(config["head"]))]
    for where, j, k in places:
        for bit in range(C.COEFF_BITS):
            changed = copy.deepcopy(config)
            if where == "hidden":
                changed["hidden"][j][k] = flipped(config["hidden"][j][k], bit)
            else:
                changed["head"][j] = flipped(config["head"][j], bit)
            tried += 1
            if list(Core(H.blob_of(profile, changed)).run(frames)) == base:
                misses.append((where, j, k, bit))
    return misses, tried


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("between", [PASS, ABS])
@pytest.mark.parametrize("shifts", [(0, 0), (3, 2)])
def test_control_reference_model__one_flipped_bit_of_a_hidden_or_head_weight_changes_a_score(profile, between, shifts):
    """Every bit of every weight of the head, where each unit reaches the score: no head weight is zero."""
    config = H.a_config(profile, units=3, hidden_shift=shifts[0], between=between, pool=2, score_shift=shifts[1])
    assert 0 not in config["head"]
    frames = S.varied_frames(profile, 16, seed=5)
    misses, tried = flips_that_do_not_reach(profile, config, frames)
    assert misses == []
    assert tried == (3 * 2 + 3) * C.COEFF_BITS
    print("CONTROL reference-model, flipped head bits, %s, between %d, shifts %r: %d flips, each changed a score"
          % (profile, between, shifts, tried))


@pytest.mark.parametrize("profile", PROFILES)
def test_head_a_zero_head_weight_does_hide_a_flipped_hidden_bit(profile):
    """Why the control above has no zero head weight: behind one, every flip in that unit's weights is hidden."""
    config = H.a_config(profile, units=3, pool=2)
    config["head"][1] = 0
    misses, tried = flips_that_do_not_reach(profile, config, S.varied_frames(profile, 16, seed=5))
    assert tried == (3 * 2 + 3) * C.COEFF_BITS
    assert sorted({(m[0], m[1]) for m in misses}) == [("hidden", 1)], "every flip in the masked unit hides, and no other"
    assert len(misses) == 2 * C.COEFF_BITS

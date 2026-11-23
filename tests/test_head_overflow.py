"""The overflow gate, for the head's hidden layer: its widths, and the sticky flag where a width is a choice.

A hidden layer adds three stages (model/detector.py, steps 4b to 4d). One of their widths is a choice, the
hidden value's, and it is the score field's; the other two are derived and cannot overflow.

THE EXTREMES ARE DERIVED from `spec.constants`, not retyped: every sample at the profile's sample_min, every
coefficient, every hidden weight and every head weight at COEFF_MIN, MAX_TAPS taps, a pool of MAX_POOL, as many
rows as MAX_ROWS allows, MAX_HIDDEN units.

HOW THEY ARE REACHED, and what that concedes. A core with a hidden layer is NOT run through the 65,662 frames
that fill its delay lines and its pool. The hidden layer remembers nothing, so the state those frames lead to
can be written down: `primed` writes a version 2 core's delay lines, pool windows and pool sums from closed
forms, and from there the core's real `step` runs, end to end, on the extreme frame. That the written state
is the state a full run reaches is checked against the pooled values MOD-B's full run of the shipped core
kept (`test_mod_b_overflow.extreme_run`, one run a profile for the whole suite). A fault that only exists in
how a version 2 core gets from an empty state to the extreme is not seen here (docs/model/head.md, limit HL6).

THE CONTROLS: a hidden shift one bit short, a score shift one bit short, and each of the three new stages one
bit narrower, each stepped end to end from the same written state.
"""
from collections import deque

import pytest

from spec import constants as C
from model import detector, weights
from model.detector import Core

import test_mod_b_support as S
import test_mod_b_overflow as O
import test_head_support as H

PROFILES = H.PROFILES
PASS, ABS = H.PASS, H.ABS
SCORE_BITS, SCORE_MIN, SCORE_MAX = H.SCORE_BITS, H.SCORE_MIN, H.SCORE_MAX


def named_shifts(profile):
    """(the hidden shift, the score shift) that the width argument says bring the extremes exactly inside."""
    width, hidden = detector.widths(profile), detector.hidden_widths(profile)
    return width["head"] - hidden["hidden"], hidden["output"] - width["score"]


def extreme_blob(profile, between, hidden_shift=None, score_shift=None):
    """The largest shape with a hidden layer, every coefficient and every weight at COEFF_MIN."""
    filters = O.extreme_filters(profile, C.MAX_TAPS)
    q, s = named_shifts(profile)
    return weights.pack(profile, filters, (C.COEFF_MIN,) * C.MAX_HIDDEN, PASS, C.MAX_POOL,
                        s if score_shift is None else score_shift,
                        hidden=((C.COEFF_MIN,) * len(filters),) * C.MAX_HIDDEN,
                        hidden_shift=q if hidden_shift is None else hidden_shift, between=between)


def primed(core, profile):
    """Write into a core the state a full run at the extremes reaches: every window full of extremes."""
    p = C.PROFILES[profile]
    row = C.MAX_TAPS * O.one_product(profile)                 # one row of taps, full of the largest product
    rows = [len(f) for f in O.extreme_filters(profile, C.MAX_TAPS)]
    assert len(core._line) == p["channels"] and len(core._window) == len(rows) == len(core._sum)
    for c in range(p["channels"]):
        core._line[c] = deque([p["sample_min"]] * C.MAX_TAPS, maxlen=C.MAX_TAPS)
    for k, n in enumerate(rows):
        core._window[k] = deque([n * row] * C.MAX_POOL, maxlen=C.MAX_POOL)
        core._sum[k] = C.MAX_POOL * n * row
    return core


def stepped(core, profile, steps=3):
    """The records of `steps` real steps on the extreme frame, from the written state, with every stage watched."""
    primed(core, profile)
    O.watch(core)
    p = C.PROFILES[profile]
    return [core.step((p["sample_min"],) * p["channels"]) for _ in range(steps)]


# ------------------------------------------------------------------ the gate

@pytest.mark.parametrize("profile", PROFILES)
def test_gate_overflow__the_hidden_layers_widths_equal_the_hand_worked_widths(profile):
    worked = H.vector("widths.json")["profiles"][profile]
    assert detector.hidden_widths(profile) == worked["bits"]
    assert tuple(detector.hidden_widths(profile)) == detector.HIDDEN_STAGES
    assert detector.widths(profile)["head"] == worked["hidden_sum_bits"], "a hidden unit's sum is the head sum, at its width"
    q, s = named_shifts(profile)
    assert q == worked["hidden_shift_that_rules_overflow_out"] <= C.MAX_HIDDEN_SHIFT
    assert s == worked["score_shift_that_rules_overflow_out"] <= C.MAX_SCORE_SHIFT

    def value(text):                                 # "2^63", "3 * 2^82", "-2^76"
        sign = -1 if text.startswith("-") else 1
        factor, _star, power = text.lstrip("-").rpartition(" * ")
        return sign * (int(factor) if factor else 1) * 2 ** int(power.split("^")[1])

    ranges = detector.hidden_ranges(profile)
    assert detector.ranges(profile)["head"][0] == value(worked["extremes"]["hidden_sum"])
    assert ranges["hidden"][0] == value(worked["extremes"]["hidden"])
    assert ranges["between"] == (value(worked["extremes"]["hidden"]), value(worked["extremes"]["between"]))
    assert ranges["output"] == (-value(worked["extremes"]["output"]), value(worked["extremes"]["output"]))
    for stage, (lo, hi) in ranges.items():
        assert O.needs(lo, hi) == worked["bits"][stage], "%s: the declared width is the fewest bits for its range" % stage


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_overflow__the_hidden_values_width_is_derived_from_the_score_field_and_moves_with_it(profile, monkeypatch):
    """The lead's ruling, point 7: no constant of its own. A definition that changes the score field moves it, on purpose."""
    assert detector.hidden_widths(profile)["hidden"] == SCORE_BITS == detector.widths(profile)["score"]
    assert detector.hidden_ranges(profile)["hidden"] == (SCORE_MIN, SCORE_MAX)
    for other in (SCORE_BITS - 16, SCORE_BITS - 1, SCORE_BITS + 8):
        with monkeypatch.context() as patch:
            records = dict(C.RECORDS)
            records["score"] = tuple((name, other if name == "score" else bits, sign) for name, bits, sign in C.RECORDS["score"])
            patch.setattr(C, "RECORDS", records)
            assert detector.widths(profile)["score"] == other
            moved = detector.hidden_widths(profile)
            assert (moved["hidden"], moved["between"]) == (other, other + 1)
            assert moved["output"] == O.needs(C.MAX_HIDDEN * C.COEFF_MIN * (1 << (other - 1)), C.MAX_HIDDEN * C.COEFF_MIN * -(1 << (other - 1)))
    assert detector.hidden_widths(profile)["hidden"] == SCORE_BITS, "and the definition is whole again"


def test_head_the_bounds_the_design_rests_on():
    """Part 3 of the plan's test, as a count; and the two things the hidden shift's bound must allow."""
    bank = C.MAX_ROWS * C.MAX_TAPS
    assert (C.MAX_FILTERS + 1) * C.MAX_HIDDEN * 10 <= bank, "the whole head is at most a tenth of the bank, in multipliers"
    assert (C.MAX_FILTERS + 1) * (C.MAX_HIDDEN + 1) * 10 > bank, "and one unit more would not be"
    assert C.MAX_HIDDEN_SHIFT >= C.MAX_SCORE_SHIFT, "every score shift of a version 1 blob can be the hidden shift of its setting"
    for profile in PROFILES:
        q, s = named_shifts(profile)
        assert 0 <= q <= C.MAX_HIDDEN_SHIFT and 0 <= s <= C.MAX_SCORE_SHIFT


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("between", [PASS, ABS])
def test_gate_overflow__a_hidden_layer_at_the_true_extremes_fits_every_width_and_raises_no_flag(profile, between):
    core = Core(extreme_blob(profile, between))
    got = stepped(core, profile)
    assert core.hidden == C.MAX_HIDDEN
    assert core.pooled == O.extreme_run(profile)["pooled"], "the written state is the one the full run of the shipped core reached"
    row = C.MAX_TAPS * O.one_product(profile)
    head_low = C.COEFF_MIN * C.MAX_ROWS * C.MAX_POOL * row
    assert head_low == O.extreme_run(profile)["head_sum"] == detector.ranges(profile)["head"][0]
    assert core.reached["head"] == (head_low, head_low), "each unit's sum is the head's extreme"
    assert core.reached["hidden"] == (SCORE_MIN, SCORE_MIN), "the named hidden shift brings it to exactly the last value that fits"
    folded = -SCORE_MIN if between == ABS else SCORE_MIN
    assert core.reached["between"] == (folded, folded)
    total = C.MAX_HIDDEN * C.COEFF_MIN * folded
    assert core.reached["output"] == (total, total)
    q, s = named_shifts(profile)
    assert got == [{"index": i, "epoch": 0, "flags": 0, "score": total >> s} for i in range(3)], "no flag, and the score by closed form"
    width = core.width
    assert O.needs(*core.reached["hidden"]) == width["hidden"] and O.needs(*core.reached["output"]) == width["output"]
    if between == ABS:
        assert O.needs(*core.reached["between"]) == width["between"], "abs of the lowest hidden value needs the 65th bit"
        assert total == detector.hidden_ranges(profile)["output"][0]
    else:
        assert total == detector.hidden_ranges(profile)["output"][1]
    for stage in detector.HIDDEN_STAGES:
        lo, hi = detector.hidden_ranges(profile)[stage]
        assert lo <= core.reached[stage][0] and core.reached[stage][1] <= hi


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_overflow__the_flag_rises_at_the_first_hidden_value_that_does_not_fit_and_stays(profile):
    """A cheap configuration whose first unit's sum passes the hidden width while the score still fits.

    One tap, one filter, a pool of 2 * fits; unit 0's weight is COEFF_MIN and unit 1's is 1; pass between; head
    weights 1 and 1; a score shift of 1. After n extreme samples in the pool, unit 0's sum is n * step and unit
    1's is n * (the largest product). `fits` is the n at which n * step is exactly the lowest value 64 bits hold.
    The expected records are this closed form; the last steps cross a swap, and the flag stays.
    """
    _blob, frame, fits = O.boundary(profile, pool_factor=2)
    last = C.PROFILES[profile]["channels"] - 1
    quiet = tuple(0 if v == C.PROFILES[profile]["sample_min"] else v for v in frame)
    product = O.one_product(profile)
    step = C.COEFF_MIN * product

    def blob(first):
        return weights.pack(profile, [{last: (C.COEFF_MIN,)}], (1, 1), PASS, 2 * fits, 1,
                            hidden=((first,), (1,)), hidden_shift=0, between=PASS)

    core = Core(blob(C.COEFF_MIN))
    frames = [frame] * (fits + 3) + [quiet] * (2 * fits + 2)
    got = [core.step(f) for f in frames]

    def held(i):                     # how many extreme samples the pool holds at output i
        return max(0, min(i, fits + 2) - max(0, i - 2 * fits + 1) + 1)

    for i, record in enumerate(got):
        true = held(i) * step
        expected = (H.wrap(true) + held(i) * product) >> 1
        assert record == {"index": i, "epoch": 0, "flags": S.OVERFLOW if i >= fits else 0, "score": expected}, i
    assert held(fits - 1) * step == SCORE_MIN, "the last hidden value that fits is the lowest the width holds"
    assert held(fits) * step < SCORE_MIN and H.wrap(held(fits) * step) != held(fits) * step
    assert all(SCORE_MIN <= (H.wrap(held(i) * step) + held(i) * product) >> 1 <= SCORE_MAX for i in range(len(got))), \
        "the score itself always fits: the flag here is the hidden value's and nothing else's"
    assert got[-1]["score"] == 0 and got[-1]["flags"] == S.OVERFLOW, "back in range, and the flag has stayed"
    core.write_shadow(blob(1))
    core.commit(core.next_index)
    after = [core.step(quiet) for _ in range(3)]
    assert all(r == {"index": len(frames) + n, "epoch": 1, "flags": S.OVERFLOW | (S.SETTLING if n < 2 * fits - 1 else 0), "score": 0}
               for n, r in enumerate(after)), "sticky across a swap"


# --------------------------------------------------------------- the controls

@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("between", [PASS, ABS])
def test_control_overflow__a_hidden_shift_one_bit_short_raises_the_flag_at_the_true_extremes(profile, between):
    q, _s = named_shifts(profile)
    shipped = stepped(Core(extreme_blob(profile, between)), profile, steps=1)
    short = stepped(Core(extreme_blob(profile, between, hidden_shift=q - 1)), profile, steps=1)
    assert shipped[0]["flags"] == 0
    assert short[0]["flags"] == S.OVERFLOW and short[0]["score"] != shipped[0]["score"]
    print("CONTROL overflow, hidden shift %d for %d, %s, between %d: %r; the shipped shift gives %r"
          % (q - 1, q, profile, between, short[0], shipped[0]))


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("between", [PASS, ABS])
def test_control_overflow__a_score_shift_one_bit_short_after_the_hidden_layer_raises_the_flag(profile, between):
    _q, s = named_shifts(profile)
    shipped = stepped(Core(extreme_blob(profile, between)), profile, steps=1)
    short = stepped(Core(extreme_blob(profile, between, score_shift=s - 1)), profile, steps=1)
    assert shipped[0]["flags"] == 0
    assert short[0]["flags"] == S.OVERFLOW and short[0]["score"] != 2 * shipped[0]["score"]
    print("CONTROL overflow, score shift %d for %d after the hidden layer, %s, between %d: %r; the shipped shift gives %r"
          % (s - 1, s, profile, between, short[0], shipped[0]))


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("stage", detector.HIDDEN_STAGES)
def test_control_overflow__a_hidden_stage_one_bit_narrower_raises_the_flag_at_the_true_extremes(profile, stage):
    """A whole core, stepped end to end from the written state. Abs between, so that every stage reaches its last bit."""
    blob = extreme_blob(profile, ABS)
    shipped = stepped(Core(blob), profile, steps=1)
    narrow_core = O.narrowed(stage)(blob)
    narrow = stepped(narrow_core, profile, steps=1)
    assert narrow_core.width[stage] == detector.hidden_widths(profile)[stage] - 1
    assert shipped[0]["flags"] == 0
    assert narrow[0]["flags"] == S.OVERFLOW and narrow[0]["score"] != shipped[0]["score"]
    print("CONTROL overflow, %s one bit narrower, %s: %r; the shipped core gives %r" % (stage, profile, narrow[0], shipped[0]))


@pytest.mark.parametrize("profile", PROFILES)
def test_head_under_pass_a_narrow_between_stage_would_not_show(profile):
    """Why that control folds: under pass the between stage never holds +2^63, and one bit fewer still fits."""
    blob = extreme_blob(profile, PASS)
    assert stepped(O.narrowed("between")(blob), profile, steps=1) == stepped(Core(blob), profile, steps=1)

"""The overflow gate: no accumulator overflows at the extreme inputs, and the flag rises where a width is a choice.

THE EXTREMES ARE DERIVED HERE from `spec.constants`, not retyped: every sample at the profile's
sample_min, every coefficient and every head weight at COEFF_MIN, MAX_TAPS taps, a pool of MAX_POOL, and
as many rows as MAX_ROWS allows. Both factors negative makes every product the largest positive one.

The shipped core runs those extremes IN FULL, once per profile (`extreme_run`, about ten seconds each,
and the result is kept for the tests that read it). The expected values are closed forms worked from the
constants in this file; none comes from the model.

THE CONTROLS narrow one stage by one bit.
- The filter and the score are narrowed in a whole core, run end to end on a stream that reaches that
  stage's extreme.
- The pool and the head are narrowed in a core that is NOT run end to end: it is handed the stage values
  the full shipped run was seen to reach. A whole narrowed core would need the ten-second run again for
  each. This is a stated limit of the control (docs/model/mod-b.md, limit L7).
"""
import functools

import pytest

from spec import constants as C
from model import detector, weights
from model.detector import Core

import test_mod_b_support as S

PROFILES = S.PROFILES
SCORE_BITS = dict((f[0], f[1]) for f in C.RECORDS["score"])["score"]
SCORE_MIN, SCORE_MAX = -(1 << (SCORE_BITS - 1)), (1 << (SCORE_BITS - 1)) - 1


def needs(lo, hi):
    """The fewest signed bits holding lo..hi. Written here again, not imported from the model."""
    bits = 1
    while -(1 << (bits - 1)) > lo or hi > (1 << (bits - 1)) - 1:
        bits += 1
    return bits


def extreme_filters(profile, taps):
    """As many rows as MAX_ROWS allows, every coefficient COEFF_MIN: whole-profile filters, then one with the rest."""
    channels = C.PROFILES[profile]["channels"]
    whole, rest = divmod(C.MAX_ROWS, channels)
    filters = [{c: (C.COEFF_MIN,) * taps for c in range(channels)}] * whole
    if rest:
        filters.append({c: (C.COEFF_MIN,) * taps for c in range(rest)})
    assert sum(len(f) for f in filters) == C.MAX_ROWS and len(filters) <= C.MAX_FILTERS
    return filters


def watch(core):
    """Make a shipped core record, from now on, the lowest and highest value entering each stage's width.

    It changes nothing the core computes. It is switched on for the last outputs of the full run only, where
    the extremes are reached; that no earlier output overflowed is what the sticky flag already says.
    """
    core.reached, fit, head = {}, core._fit, core._head

    def watched_fit(value, stage):
        lo, hi = core.reached.get(stage, (value, value))
        core.reached[stage] = (min(lo, value), max(hi, value))
        return fit(value, stage)

    def watched_head(pooled, weights_):
        core.pooled, core.head_weights = list(pooled), weights_
        core.head_sum = head(pooled, weights_)
        return core.head_sum

    core._fit, core._head = watched_fit, watched_head


@functools.lru_cache(maxsize=None)
def extreme_run(profile):
    """The shipped core at the true extremes, in full. Returns what the tests read."""
    p = C.PROFILES[profile]
    filters = extreme_filters(profile, C.MAX_TAPS)
    shift = detector.widths(profile)["head"] - SCORE_BITS
    blob = weights.pack(profile, filters, (C.COEFF_MIN,) * len(filters), C.RECTIFIERS["pass"], C.MAX_POOL, shift)
    core = Core(blob)
    frame = (p["sample_min"],) * p["channels"]
    n = C.MAX_TAPS + C.MAX_POOL - 1                 # the first output whose every window is full of extremes is n - 1
    wanted = {0, C.MAX_TAPS - 1, n - 2, n - 1}
    kept, flags = {}, 0
    for i in range(n):
        if i == n - 2:
            watch(core)
        record = core.step(frame)
        flags |= record["flags"]
        if i in wanted:
            kept[i] = record
    return {"kept": kept, "flags": flags, "reached": dict(core.reached), "pooled": core.pooled, "head_sum": core.head_sum,
            "head_weights": core.head_weights, "blob": blob, "shift": shift, "frames": n, "rows": [len(f) for f in filters]}


def one_product(profile):
    return C.PROFILES[profile]["sample_min"] * C.COEFF_MIN           # the largest product, both factors negative


# ------------------------------------------------------------------ the gate

@pytest.mark.parametrize("profile", PROFILES)
def test_gate_overflow__the_declared_widths_equal_the_hand_worked_widths(profile):
    worked = S.vector("widths.json")["profiles"][profile]
    assert detector.widths(profile) == worked["bits"]
    assert detector.widths(profile)["head"] - SCORE_BITS == worked["shift_that_rules_overflow_out"] <= C.MAX_SCORE_SHIFT

    def value(text):                                 # "2^39", "3 * 2^47", "-2^76"
        sign = -1 if text.startswith("-") else 1
        factor, _star, power = text.lstrip("-").rpartition(" * ")
        return sign * (int(factor) if factor else 1) * 2 ** int(power.split("^")[1])

    ranges = detector.ranges(profile)
    assert ranges["filter"][1] == value(worked["extremes"]["filter"])
    assert ranges["pool"][1] == value(worked["extremes"]["pool"])
    assert ranges["head"][0] == value(worked["extremes"]["head"])
    for stage, (lo, hi) in ranges.items():
        assert needs(lo, hi) == worked["bits"][stage], "%s: the declared width is the fewest bits for its range" % stage


def test_gate_overflow__d0_row_d4_holds_for_16_bits_and_the_24_bit_figure_is_larger():
    """D4: 128 products of 2^15 * 2^17 sum to 2^39, which needs 41 signed bits. Stated here in figures on purpose."""
    assert detector.ranges("s16x1")["filter"][1] == 128 * 2 ** 15 * 2 ** 17 == 2 ** 39
    assert detector.widths("s16x1")["filter"] == 41
    assert needs(0, 2 ** 39) == 41 and needs(0, 2 ** 39 - 1) == 40
    assert detector.ranges("s24x3")["filter"][1] == 3 * 128 * 2 ** 23 * 2 ** 17 == 3 * 2 ** 47
    assert detector.widths("s24x3")["filter"] == 50
    assert needs(0, 2 ** 47) == 49, "one row of 128 taps under 24 bits"


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_overflow__the_true_extremes_fit_every_width_and_raise_no_flag(profile):
    p = C.PROFILES[profile]
    run = extreme_run(profile)
    width = detector.widths(profile)
    per_filter = min(p["channels"], C.MAX_ROWS)
    row = C.MAX_TAPS * one_product(profile)                               # one row of taps, full of extremes
    assert run["flags"] == 0, "no stage overflowed and no output was settling, at any of the %d outputs" % run["frames"]

    # each stage reached its extreme, and the declared width is exactly what that extreme needs
    assert run["reached"]["filter"][1] == per_filter * row
    assert run["reached"]["pool"][1] == C.MAX_POOL * per_filter * row
    head_low = C.COEFF_MIN * C.MAX_ROWS * C.MAX_POOL * row
    assert run["reached"]["head"][0] == head_low == run["head_sum"]
    assert run["reached"]["score"][0] == SCORE_MIN
    for stage in ("filter", "rectifier", "pool", "head", "score"):
        assert needs(*run["reached"][stage]) == width[stage], "%s: reached %r" % (stage, run["reached"][stage])
        assert detector.ranges(profile).get(stage, (SCORE_MIN, SCORE_MAX))[0] <= run["reached"][stage][0]
        assert run["reached"][stage][1] <= detector.ranges(profile).get(stage, (SCORE_MIN, SCORE_MAX))[1]

    # the score records, by closed form: taps fill for MAX_TAPS outputs, then the pool fills
    def expected(i):
        total = 0
        for m in range(max(0, i - C.MAX_POOL + 1), i + 1):
            total += min(m + 1, C.MAX_TAPS)                               # products under the taps at output m
        return (C.COEFF_MIN * C.MAX_ROWS * total * one_product(profile)) >> run["shift"]

    last = run["frames"] - 1
    for i in (0, C.MAX_TAPS - 1, last - 1, last):
        assert run["kept"][i] == {"index": i, "epoch": 0, "flags": 0, "score": expected(i)}
    assert run["kept"][last]["score"] == SCORE_MIN, "the lowest score the field holds, reached exactly"
    assert run["kept"][last - 1]["score"] > SCORE_MIN


def boundary(profile, pool_factor=1):
    """A cheap configuration whose head sum reaches exactly the lowest score the field holds, with no shift.

    One tap, one filter on one channel, coefficient and head weight COEFF_MIN, samples at sample_min: after
    P outputs the head sum is COEFF_MIN * P * (the largest product). P is chosen to make that -2^63.
    """
    last = C.PROFILES[profile]["channels"] - 1
    pool, rest = divmod(-SCORE_MIN, -C.COEFF_MIN * one_product(profile))
    assert rest == 0 and pool * pool_factor <= C.MAX_POOL
    blob = weights.pack(profile, [{last: (C.COEFF_MIN,)}], (C.COEFF_MIN,), C.RECTIFIERS["pass"], pool * pool_factor, 0)
    frame = tuple(C.PROFILES[profile]["sample_min"] if c == last else 1 + c for c in range(last + 1))
    return blob, frame, pool


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_overflow__the_flag_rises_at_the_first_score_that_does_not_fit_and_stays(profile):
    blob, frame, fits = boundary(profile, pool_factor=2)
    quiet = tuple(0 if v == C.PROFILES[profile]["sample_min"] else v for v in frame)
    core = Core(blob)
    got = [core.step(frame) for _ in range(fits + 3)] + [core.step(quiet) for _ in range(2 * fits + 2)]
    step = C.COEFF_MIN * one_product(profile)                             # what one extreme sample adds to the head sum

    def true_score(i):               # samples 0 .. fits+2 are extreme, the rest zero; the pool holds the last 2 * fits
        return step * max(0, min(i, fits + 2) - max(0, i - 2 * fits + 1) + 1)

    for i, record in enumerate(got):
        true = true_score(i)
        wrapped = (true - SCORE_MIN) % (1 << SCORE_BITS) + SCORE_MIN      # the true value modulo 2^64, two's complement
        assert record == {"index": i, "epoch": 0, "flags": S.OVERFLOW if i >= fits else 0, "score": wrapped}, i
    assert true_score(fits - 1) == SCORE_MIN, "the last score that fits is the lowest the field holds"
    assert true_score(fits) < SCORE_MIN and got[fits]["score"] != true_score(fits)
    assert got[-1]["score"] == true_score(len(got) - 1) == 0 and got[-1]["flags"] == S.OVERFLOW, \
        "the scores are right again once the sum is back in range, and the flag has stayed"
    outside = [i for i in range(len(got)) if not SCORE_MIN <= true_score(i) <= SCORE_MAX]
    assert outside == list(range(fits, 2 * fits + 2)), "the scores that do not fit: while the pool holds more than `fits` extremes"
    assert all(got[i]["score"] == true_score(i) for i in range(len(got)) if not fits <= i < 2 * fits + 2)


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_overflow__the_shift_that_the_width_argument_names_brings_the_extreme_inside(profile):
    """With no shift the extreme head sum is far outside the score field; with the named shift it is exactly inside."""
    run = extreme_run(profile)
    plain = Core(run["blob"])
    assert plain._score(run["head_sum"]) == SCORE_MIN and not plain.overflow
    config = weights.unpack(run["blob"])
    unshifted = Core(weights.pack(config["profile"], config["filters"], config["head"], config["rectifier"],
                                  config["pool"], run["shift"] - 1))
    unshifted._score(run["head_sum"])
    assert unshifted.overflow


# --------------------------------------------------------------- the controls

def narrowed(stage):
    class Narrow(Core):
        def __init__(self, blob, epoch=0):
            super().__init__(blob, epoch)
            self.width = dict(self.width)
            self.width[stage] -= 1
    Narrow.__name__ = "NarrowAt_" + stage
    return Narrow


@pytest.mark.parametrize("profile", PROFILES)
def test_control_overflow__a_core_one_bit_narrower_at_the_filter_overflows_at_the_true_extremes(profile):
    """A whole core, run end to end: one filter across the profile's channels, MAX_TAPS taps, every value at its extreme."""
    p = C.PROFILES[profile]
    rows = {c: (C.COEFF_MIN,) * C.MAX_TAPS for c in range(min(p["channels"], C.MAX_ROWS))}
    blob = weights.pack(profile, [rows], (1,), C.RECTIFIERS["pass"], 1, 0)
    frames = [(p["sample_min"],) * p["channels"]] * C.MAX_TAPS
    expected = len(rows) * C.MAX_TAPS * one_product(profile)
    shipped = list(Core(blob).run(frames))
    assert shipped[-1] == {"index": C.MAX_TAPS - 1, "epoch": 0, "flags": 0, "score": expected}
    assert all(r["flags"] == 0 for r in shipped)
    narrow = list(narrowed("filter")(blob).run(frames))
    assert narrow[-1]["flags"] == S.OVERFLOW and narrow[-1]["score"] != expected
    print("CONTROL overflow, filter one bit narrower, %s: last record %r; the shipped core gives %r"
          % (profile, narrow[-1], shipped[-1]))


@pytest.mark.parametrize("profile", PROFILES)
def test_control_overflow__a_core_one_bit_narrower_at_the_score_overflows_where_the_shipped_core_just_fits(profile):
    """A whole core, run end to end, on the cheap configuration whose last score is exactly the lowest the field holds."""
    blob, frame, fits = boundary(profile)
    shipped = [Core(blob).step(frame)] if fits == 1 else list(Core(blob).run([frame] * fits))
    assert shipped[-1] == {"index": fits - 1, "epoch": 0, "flags": 0, "score": SCORE_MIN}
    narrow = list(narrowed("score")(blob).run([frame] * fits))
    assert narrow[-1]["flags"] == S.OVERFLOW and narrow[-1]["score"] != SCORE_MIN
    assert [r["flags"] for r in narrow] == [0] * (fits // 2) + [S.OVERFLOW] * (fits - fits // 2),         "one bit fewer is half the range: it overflows from the output where the sum first passes -2^62"
    print("CONTROL overflow, score one bit narrower, %s: last record %r; the shipped core gives %r"
          % (profile, narrow[-1], shipped[-1]))


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("stage", ["filter", "rectifier", "pool", "head", "score"])
def test_control_overflow__a_stage_one_bit_narrower_overflows_on_the_values_the_full_run_reached(profile, stage):
    """The cheaper form: the narrowed core is handed the stage values of the full shipped run, not run end to end."""
    run = extreme_run(profile)
    lo, hi = run["reached"][stage]
    extreme = lo if stage in ("head", "score") else hi
    shipped, narrow = Core(run["blob"]), narrowed(stage)(run["blob"])
    assert shipped._fit(extreme, stage) == extreme and not shipped.overflow
    assert narrow._fit(extreme, stage) != extreme and narrow.overflow
    if stage == "head":
        narrow = narrowed("head")(run["blob"])
        assert narrow._head(run["pooled"], run["head_weights"]) != run["head_sum"] and narrow.overflow
        shipped = Core(run["blob"])
        assert shipped._head(run["pooled"], run["head_weights"]) == run["head_sum"] and not shipped.overflow
    if stage == "score":
        narrow = narrowed("score")(run["blob"])
        assert narrow._score(run["head_sum"]) != SCORE_MIN and narrow.overflow
    print("CONTROL overflow, %s one bit narrower, %s: the value %d (%d bits) does not fit %d bits"
          % (stage, profile, extreme, needs(lo, hi), detector.widths(profile)[stage] - 1))


@pytest.mark.parametrize("profile", PROFILES)
def test_mod_b_inputs_short_of_the_extremes_would_not_show_a_narrow_filter(profile):
    """Why the extremes must be the extremes: with only half the taps at COEFF_MIN a narrowed filter passes."""
    p = C.PROFILES[profile]
    half = (C.COEFF_MIN,) * (C.MAX_TAPS // 2) + (0,) * (C.MAX_TAPS - C.MAX_TAPS // 2)
    rows = {c: half for c in range(min(p["channels"], C.MAX_ROWS))}
    blob = weights.pack(profile, [rows], (1,), C.RECTIFIERS["pass"], 1, 0)
    frames = [(p["sample_min"],) * p["channels"]] * C.MAX_TAPS
    assert list(narrowed("filter")(blob).run(frames)) == list(Core(blob).run(frames))


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_overflow__the_flag_stays_set_across_a_swap(profile):
    """Sticky means sticky: a swap changes the weights and the epoch, and does not clear the flag."""
    blob, frame, fits = boundary(profile, pool_factor=2)
    quiet = tuple(0 if v == C.PROFILES[profile]["sample_min"] else v for v in frame)
    core = Core(blob)
    for _ in range(fits + 1):
        last = core.step(frame)
    assert last["flags"] == S.OVERFLOW
    config = weights.unpack(blob)
    core.write_shadow(weights.pack(profile, [{c: (1,) for c in f} for f in config["filters"]], (1,), config["rectifier"],
                                   config["pool"], config["score_shift"]))
    core.commit(core.next_index)
    after = [core.step(quiet) for _ in range(2 * fits + 2)]
    assert all(r["epoch"] == 1 and r["flags"] & S.OVERFLOW for r in after)
    assert after[-1] == {"index": 3 * fits + 2, "epoch": 1, "flags": S.OVERFLOW, "score": 0}, "settled, in range, still marked"

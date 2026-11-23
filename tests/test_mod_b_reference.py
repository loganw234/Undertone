"""The reference-model gate: the core's score records equal known answers, byte for byte.

The known answers are vectors/mod-b/datapath.json and quantise.json, worked by hand, and the datapath's
definition written out a second time in test_mod_b_support.py, which uses nothing of the model's modules
and is itself held to the hand-worked vectors.

Each control builds a model that is wrong in ONE place, as a subclass or a patched function made here,
runs the SAME check, and asserts that the check names a miss. The last tests are the model's half of the
design's bit-identity control: one flipped coefficient bit must reach a score.
"""
import random
from fractions import Fraction

import pytest

from spec import constants as C
from model import records, weights
from model.detector import Core

import test_mod_b_support as S

PROFILES = S.PROFILES
PULSE = C.PULSES["e0"]


# --------------------------------------------------------------- the checks

def check_quantiser(quantise):
    """Findings for a quantising function against the hand-worked sets."""
    findings = []
    todo = S.vector("quantise.json")["cases"]
    for case in todo:
        values = [Fraction(v[0], v[1]) if isinstance(v, list) else v for v in case["values"]]
        got = list(quantise(values))
        if got != case["expected"]:
            findings.append("%s: %r, the vector says %r" % (case["name"], got, case["expected"]))
    return findings, len(todo)


def independent_e0(gains):
    """The matched rows for e0 under per-channel gains, by integers and round half UP.

    Round half up equals round half to even when no value is an exact tie, and this asserts none is.
    It imports nothing of the model.
    """
    qmax = (1 << (C.COEFF_BITS - 1)) - 1
    values = [g * v for g in gains if g != 0 for v in PULSE]
    m = max(abs(v) for v in values)
    out = []
    for v in values:
        assert (2 * v * qmax) % m != 0 or (2 * v * qmax // m) % 2 == 0, "an exact tie: this method does not apply"
        out.append((2 * v * qmax + m) // (2 * m))
    read = [c for c, g in enumerate(gains) if g != 0]
    return {c: out[n * len(PULSE):(n + 1) * len(PULSE)] for n, c in enumerate(read)}


def gains_for(profile):
    """Per-channel gains that differ in size and sign, so no channel can stand in for another."""
    return (3, -1, 2, 5, -4, 7, 6, -8)[:C.PROFILES[profile]["channels"]]


# ------------------------------------------------------------------ the gate

@pytest.mark.parametrize("profile", PROFILES)
def test_gate_reference_model__records_equal_the_hand_worked_vectors(profile):
    findings, n = S.check_vectors("datapath.json", profile)
    assert findings == []
    assert n >= 4, "a profile with no hand-worked case would pass while testing nothing"


def test_gate_reference_model__the_quantiser_equals_the_hand_worked_sets():
    findings, n = check_quantiser(weights.quantise)
    assert findings == []
    assert n >= 6
    ties = [c for c in S.vector("quantise.json")["cases"] if c["name"] in ("halves", "ties-far-from-zero")]
    assert len(ties) == 2, "the tie cases are what a changed rounding must miss"


def test_gate_reference_model__the_reference_pulses_coefficients_equal_the_frozen_ones():
    frozen = S.vector("quantise.json")["e0"]
    assert len(frozen["expected"]) == len(PULSE) == 64
    assert independent_e0((1,))[0] == frozen["expected"], "the frozen list is what the independent method gives"
    for index, value in frozen["by_hand"].items():
        assert frozen["expected"][int(index)] == value, "the four hand-worked coefficients"
    assert list(weights.quantise(list(PULSE))) == frozen["expected"]


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_reference_model__the_matched_filter_is_the_pulse_in_order_and_peaks_at_first_sample_plus_taps_minus_1(profile):
    gains = gains_for(profile)
    config = weights.unpack(weights.matched_filter(profile, PULSE, gains))
    rows = independent_e0(gains)
    assert [{c: list(row) for c, row in f.items()} for f in config["filters"]] == [rows]
    assert (config["head"], config["rectifier"], config["pool"], config["score_shift"]) == ((1,), 0, 1, 0)

    first, taps = 10, len(PULSE)
    frames = [tuple(0 for _ in gains)] * first + [tuple(g * v for g in gains) for v in PULSE] \
        + [tuple(0 for _ in gains)] * 20
    got = list(Core(weights.matched_filter(profile, PULSE, gains)).run(frames))
    peak = sum(rows[c][k] * gains[c] * PULSE[k] for c in rows for k in range(taps))    # the filter fully on the pulse
    assert got[first + taps - 1]["score"] == peak
    assert max(r["score"] for r in got) == peak
    assert [r["score"] for r in got].index(peak) == first + taps - 1, "the peak is at j + T - 1"
    vector_form = {"filters": [{str(c): row for c, row in rows.items()}], "head": [1], "rectifier": 0, "pool": 1,
                   "score_shift": 0}
    assert [r["score"] for r in got] == S.direct_scores(vector_form, frames)
    assert [r["index"] for r in got] == list(range(len(frames)))


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_reference_model__seeded_shapes_and_streams_equal_the_definition_written_out(profile):
    channels = C.PROFILES[profile]["channels"]
    rng = random.Random(20261123)
    tried = 0
    for _ in range(40):
        nfilters, taps = rng.randint(1, 4), rng.randint(1, 6)
        filters = []
        for _k in range(nfilters):
            read = rng.sample(range(channels), rng.randint(1, channels))
            filters.append({str(c): [rng.randint(C.COEFF_MIN, C.COEFF_MAX) for _ in range(taps)] for c in read})
        config = {"filters": filters, "head": [rng.randint(C.COEFF_MIN, C.COEFF_MAX) for _ in filters],
                  "rectifier": rng.randint(0, 1), "pool": rng.randint(1, 5), "score_shift": rng.randint(0, 9)}
        frames = S.varied_frames(profile, 24, seed=rng.random())
        got = list(Core(S.blob_of(profile, config)).run(frames))
        expected = [{"index": i, "epoch": 0, "flags": 0, "score": s} for i, s in enumerate(S.direct_scores(config, frames))]
        assert S.compare("seeded shape %d" % tried, got, expected) == []
        tried += 1
    assert tried == 40


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("rectifier,pool,shift", [(0, 1, 0), (1, 3, 7), (0, 2, C.MAX_SCORE_SHIFT)])
def test_gate_reference_model__the_largest_shape_with_every_coefficient_different_equals_the_definition(profile, rectifier, pool, shift):
    """MAX_ROWS rows of MAX_TAPS taps, no two coefficients alike in a row: a fault at one tap or one row cannot hide behind equal values."""
    channels = C.PROFILES[profile]["channels"]
    rng = random.Random(1281 + pool)
    filters, rows_left = [], C.MAX_ROWS
    while rows_left:
        read = rng.sample(range(channels), min(rows_left, rng.randint(1, channels)))
        rows_left -= len(read)
        filters.append({str(c): rng.sample(range(C.COEFF_MIN, C.COEFF_MAX + 1), C.MAX_TAPS) for c in read})
    assert sum(len(f) for f in filters) == C.MAX_ROWS and len(filters) <= C.MAX_FILTERS
    config = {"filters": filters, "head": rng.sample(range(C.COEFF_MIN, C.COEFF_MAX + 1), len(filters)),
              "rectifier": rectifier, "pool": pool, "score_shift": shift}
    frames = S.varied_frames(profile, C.MAX_TAPS + 12, seed=pool)
    got = list(Core(S.blob_of(profile, config)).run(frames))
    expected = [{"index": i, "epoch": 0, "flags": 0, "score": s} for i, s in enumerate(S.direct_scores(config, frames))]
    assert S.compare("largest shape", got, expected) == []
    assert len({r["score"] for r in got}) == len(got), "the scores differ from output to output"


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_reference_model__a_pool_of_many_thousands_equals_the_sum_written_out(profile):
    """A pool of 6,000 samples is a legal configuration, and its moving sum is the sum of its window."""
    pool, taps = 6000, 2
    config = S.a_config(profile, taps=taps, pool=pool, rectifier=1)
    last = C.PROFILES[profile]["channels"] - 1
    frames = S.varied_frames(profile, 9000, seed=7)
    got = list(Core(S.blob_of(profile, config)).run(frames))
    r = [abs((frames[i - 1][last] if i else 0) * 1 + frames[i][last] * 2) for i in range(len(frames))]
    before = [0]
    for v in r:
        before.append(before[-1] + v)                                  # before[i] = r[0] + ... + r[i-1]
    expected = [before[i + 1] - before[max(0, i + 1 - pool)] for i in range(len(frames))]
    assert [g["score"] for g in got] == expected
    assert all(g["flags"] == 0 for g in got)


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_reference_model__two_cores_on_one_stream_give_the_same_bytes_and_a_core_keeps_its_place(profile):
    config = S.a_config(profile, taps=3, pool=4, rectifier=1)
    frames = S.varied_frames(profile, 60, seed=3)
    whole = list(Core(S.blob_of(profile, config)).run(frames))
    core = Core(S.blob_of(profile, config))
    in_two = list(core.run(frames[:25])) + list(core.run(frames[25:]))
    assert records.digest("score", whole) == records.digest("score", in_two)
    assert records.digest("score", whole)[1] == 60 and core.next_index == 60


# --------------------------------------------------------------- the controls

def half_away_from_zero(p, d):
    q, rem = divmod(abs(p), d)
    q += 1 if 2 * rem >= d else 0
    return q if p >= 0 else -q


def half_up(p, d):
    return (2 * p + d) // (2 * d)


def toward_zero(p, d):
    return abs(p) // d * (1 if p >= 0 else -1)


@pytest.mark.parametrize("wrong", [half_away_from_zero, half_up, toward_zero, lambda p, d: p // d],
                         ids=["half-away-from-zero", "half-up", "toward-zero", "floor"])
def test_control_reference_model__a_quantiser_with_its_rounding_changed_misses_a_vector(monkeypatch, wrong):
    monkeypatch.setattr(weights, "round_half_even", wrong)
    findings, _n = check_quantiser(weights.quantise)
    assert any(f.startswith("halves:") for f in findings), findings
    print("CONTROL reference-model, quantiser rounding changed:", findings[0])


class ShiftTowardZero(Core):
    def _score(self, a):
        return self._fit(-((-a) >> self.shift) if a < 0 else a >> self.shift, "score")


class ShiftToNearest(Core):
    def _score(self, a):
        return self._fit((a + (1 << self.shift >> 1)) >> self.shift, "score")


class NewestFirst(Core):
    def _filter(self, rows):
        return super()._filter(tuple((c, row[::-1]) for c, row in rows))


class OneSampleLate(Core):
    """The filter sees the stream one sample late: output i is what output i - 1 should have been."""

    def __init__(self, blob, epoch=0):
        super().__init__(blob, epoch)
        self._held = tuple(0 for _ in self._line)

    def step(self, frame):
        late, self._held = self._held, frame
        return super().step(late)


class SwappedChannels(Core):
    """Each row is applied to the next channel round."""

    def _filter(self, rows):
        n = self.profile["channels"]
        return super()._filter(tuple(((c + 1) % n, row) for c, row in rows))


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("broken,case", [(ShiftTowardZero, "abs-pool-head-shift"), (ShiftToNearest, "abs-pool-head-shift"),
                                         (NewestFirst, "pulse-in-order"), (OneSampleLate, "pulse-in-order")],
                         ids=["shift-toward-zero", "shift-to-nearest", "coefficients-newest-first", "one-sample-late"])
def test_control_reference_model__a_core_with_one_thing_changed_misses_a_vector(profile, broken, case):
    findings, _n = S.check_vectors("datapath.json", profile, core=broken)
    assert any(case in f for f in findings), findings
    print("CONTROL reference-model, %s, %s:" % (broken.__name__, profile), [f for f in findings if case in f][0])


def test_control_reference_model__rows_applied_to_the_wrong_channel_miss_a_vector():
    """Only a profile with more than one channel can show this; under one channel the fault does not exist."""
    profile = [p for p in PROFILES if C.PROFILES[p]["channels"] > 1][0]
    findings, _n = S.check_vectors("datapath.json", profile, core=SwappedChannels)
    assert any("a-filter-across-channels" in f for f in findings), findings
    print("CONTROL reference-model, SwappedChannels:", findings[0])


# ------------------------------------- not hidden: one flipped coefficient bit

def flip(value, bit):
    """The coefficient with one bit of its COEFF_BITS-wide two's complement pattern flipped."""
    pattern = (value % (1 << C.COEFF_BITS)) ^ (1 << bit)
    return pattern - (1 << C.COEFF_BITS) if pattern >> (C.COEFF_BITS - 1) else pattern


def flips_that_do_not_reach(profile, config, frames, bits):
    """Every (filter, channel, tap, bit) whose flip leaves every score record's bytes unchanged."""
    baseline = [records.pack("score", r) for r in Core(S.blob_of(profile, config)).run(frames)]
    hidden, tried = [], 0
    for k, f in enumerate(config["filters"]):
        for c in f:
            for j in range(len(f[c])):
                for bit in bits:
                    changed = {"filters": [dict(g) for g in config["filters"]], "head": config["head"],
                               "rectifier": config["rectifier"], "pool": config["pool"], "score_shift": config["score_shift"]}
                    row = list(f[c])
                    row[j] = flip(row[j], bit)
                    changed["filters"][k][c] = row
                    got = [records.pack("score", r) for r in Core(S.blob_of(profile, changed)).run(frames)]
                    tried += 1
                    if got == baseline:
                        hidden.append((k, c, j, bit))
    return hidden, tried


@pytest.mark.parametrize("profile", PROFILES)
def test_control_reference_model__one_flipped_coefficient_bit_changes_a_score_in_the_matched_filter(profile):
    """Matched-filter configuration, a stream with no zero sample: nothing stands between a tap and the score."""
    gains = gains_for(profile)
    rows = independent_e0(gains)
    config = {"filters": [{str(c): row for c, row in rows.items()}], "head": [1], "rectifier": 0, "pool": 1, "score_shift": 0}
    frames = S.varied_frames(profile, len(PULSE), seed=11)
    bits = range(C.COEFF_BITS) if len(gains) == 1 else (0, 9, C.COEFF_BITS - 1)
    hidden, tried = flips_that_do_not_reach(profile, config, frames, bits)
    assert hidden == []
    assert tried == len(gains) * len(PULSE) * len(bits)
    print("CONTROL reference-model, flipped bit, %s: %d single-bit flips, each changed a score record" % (profile, tried))


@pytest.mark.parametrize("profile", PROFILES)
def test_control_reference_model__one_flipped_coefficient_bit_changes_a_score_through_every_stage(profile):
    """The other configuration: the absolute value, a pool and non-zero head weights. A flip still arrives."""
    channels = C.PROFILES[profile]["channels"]
    config = {"filters": [{str(c): [3 + c, -5, 7] for c in range(channels)}, {str(channels - 1): [2, 9, -4]}],
              "head": [5, -3], "rectifier": 1, "pool": 3, "score_shift": 0}
    frames = S.varied_frames(profile, 12, seed=5)
    hidden, tried = flips_that_do_not_reach(profile, config, frames, range(C.COEFF_BITS))
    assert hidden == []
    assert tried == (channels + 1) * 3 * C.COEFF_BITS


@pytest.mark.parametrize("profile", PROFILES)
def test_mod_b_a_zero_head_weight_does_hide_a_flipped_bit(profile):
    """Why the control above chooses its configuration: behind a head weight of zero no flip can be seen."""
    last = str(C.PROFILES[profile]["channels"] - 1)
    config = {"filters": [{last: [1, 2, 3]}, {last: [4, 5, 6]}], "head": [1, 0], "rectifier": 0, "pool": 1, "score_shift": 0}
    frames = S.varied_frames(profile, 8, seed=2)
    hidden, tried = flips_that_do_not_reach(profile, config, frames, range(C.COEFF_BITS))
    assert tried == 2 * 3 * C.COEFF_BITS
    assert sorted({h[0] for h in hidden}) == [1], "every flip in the masked filter hides, none in the other"
    assert len(hidden) == 3 * C.COEFF_BITS


def test_mod_b_the_matched_filter_does_not_read_a_channel_whose_gain_is_zero():
    profile = [p for p in PROFILES if C.PROFILES[p]["channels"] > 2][0]
    channels = C.PROFILES[profile]["channels"]
    gains = tuple(5 if c == 1 else 0 for c in range(channels))
    config = weights.unpack(weights.matched_filter(profile, PULSE, gains))
    assert [sorted(f) for f in config["filters"]] == [[1]]
    assert list(config["filters"][0][1]) == S.vector("quantise.json")["e0"]["expected"], "a gain of 5 scales the set, not its shape"
    negative = weights.unpack(weights.matched_filter(profile, PULSE, tuple(-g for g in gains)))
    assert list(negative["filters"][0][1]) == [-v for v in S.vector("quantise.json")["e0"]["expected"]]


def test_gate_reference_model__a_row_of_zeros_for_a_channel_not_read_changes_no_record():
    """Convention (d): a channel a filter does not read is, arithmetically, a row of zeros."""
    profile = [p for p in PROFILES if C.PROFILES[p]["channels"] > 2][0]
    channels = C.PROFILES[profile]["channels"]
    frames = S.varied_frames(profile, 30, seed=19)
    for rectifier, pool in ((0, 1), (1, 4)):
        one = {"filters": [{"1": [7, -3, 5]}], "head": [9], "rectifier": rectifier, "pool": pool, "score_shift": 2}
        padded = dict(one, filters=[{str(c): [7, -3, 5] if c == 1 else [0, 0, 0] for c in range(channels)}])
        a = list(Core(S.blob_of(profile, one)).run(frames))
        b = list(Core(S.blob_of(profile, padded)).run(frames))
        assert S.compare("zero rows", b, a) == [] and len(a) == 30
        assert S.blob_of(profile, one) != S.blob_of(profile, padded), "two blobs, two shapes, one stream of records"
        assert any(r["score"] for r in a)

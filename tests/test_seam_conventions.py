"""The seam: the conventions of docs/model/conventions.md, held on the parts as they meet.

Every expected answer here is in vectors/seam/conventions.json, worked by hand with its sums,
or is integer arithmetic written out in the test. None comes from the code it judges.

Three parcels built to these conventions without seeing one another's code: the injector
(model/inject.py), the detector core and scorer (model/detector.py, model/weights.py,
model/scorer.py) and the statistics (stats/). This file is where they are first run together.
A seam test may import both model/ and stats/; neither package may import the other, and the
`independence` stage holds that.
"""
import json
import os

import pytest

from spec import constants as C
from model import inject, run, source, stream, weights
from model.detector import Core
from model.scorer import Scorer
from stats import matched as stat_matched
from stats import quantise as stat_quantise

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = sorted(C.PROFILES)
E0 = C.PULSES["e0"]
PASS = C.RECTIFIERS["pass"]

with open(os.path.join(ROOT, "vectors", "seam", "conventions.json"), encoding="utf-8") as _f:
    V = json.load(_f)


def frames_on(profile, channel, values):
    """The values on one channel, zeros on the others."""
    n = C.PROFILES[profile]["channels"]
    return [tuple(v if c == channel else 0 for c in range(n)) for v in values]


def core_scores(blob, frames):
    return [r["score"] for r in Core(blob).run(frames)]


def one_filter(profile, rows):
    """A core that is one filter and nothing else: rectifier passes, pool 1, head 1, shift 0."""
    return weights.pack(profile, [rows], (1,), PASS, 1, 0)


# ------------------------------------------------------------ (b): which way round, and whose index

@pytest.mark.parametrize("profile", PROFILES)
def test_seam_the_worked_answer_comes_out_of_the_core_on_every_channel(profile):
    case = V["one_channel"]
    for channel in range(C.PROFILES[profile]["channels"]):
        blob = one_filter(profile, {channel: tuple(case["coefficients"])})
        scores = core_scores(blob, frames_on(profile, channel, case["stream"]))
        assert scores == case["scores"] == [0, 0, 3, 8, 14, 8, 3]
        assert scores.index(max(scores)) == case["peak_index"] == 2 + 3 - 1


@pytest.mark.parametrize("profile", PROFILES)
def test_seam_the_worked_answer_comes_out_of_the_statistics_too(profile):
    case = V["one_channel"]
    channels = C.PROFILES[profile]["channels"]
    for channel in range(channels):
        rows = [[c if ch == channel else 0 for c in case["coefficients"]] for ch in range(channels)]
        scores = stat_matched.matched_scores(frames_on(profile, channel, case["stream"]), profile, rows)
        assert scores.tolist() == case["scores"]


@pytest.mark.parametrize("profile", PROFILES)
def test_seam_coefficients_the_wrong_way_round_give_the_wrong_answer_and_are_seen(profile):
    """The control for (b). Nothing crashes when a filter is written newest sample first:
    the scores are simply other scores, with the peak a sample late and below the energy."""
    case = V["one_channel"]
    wrong = tuple(reversed(case["coefficients"]))
    scores = core_scores(one_filter(profile, {0: wrong}), frames_on(profile, 0, case["stream"]))
    assert scores == case["wrong_way_round"]["scores"] == [0, 0, 1, 4, 10, 12, 9]
    assert scores != case["scores"]
    assert scores.index(max(scores)) == case["peak_index"] + 1 and max(scores) < max(case["scores"])


# ------------------------------------------------------------ (c): strictly greater

@pytest.mark.parametrize("profile", PROFILES)
def test_seam_a_crossing_is_strictly_greater_than_the_threshold(profile):
    case = V["one_channel"]
    frames = frames_on(profile, 0, case["stream"])
    blob = one_filter(profile, {0: tuple(case["coefficients"])})
    assert len(V["crossing"]["cases"]) == 4
    for want in V["crossing"]["cases"]:
        scorer = Scorer(profile, want["threshold"], 0, 0, 0, 0, 16)
        scorer.run(zip(frames, Core(blob).run(frames)))
        assert scorer.crossings == want["crossings"], want
        assert [e["index"] for e in scorer.events] == want["event_indexes"], want
    equal = [c for c in V["crossing"]["cases"] if c["threshold"] == max(case["scores"])]
    assert equal and equal[0]["crossings"] == 0, "the case that tells > from >= is there"


# ------------------------------------------------------------ (d): the channels a filter reads

def test_seam_a_filter_on_two_channels_is_the_sum_of_its_rows():
    case = V["two_channels"]
    profile = "s24x3"
    assert C.PROFILES[profile]["channels"] == 3
    for a, b in ((0, 1), (1, 2), (2, 0)):
        frames = []
        for i in range(7):
            f = [0, 0, 0]
            f[a], f[b] = case["streams"]["a"][i], case["streams"]["b"][i]
            frames.append(tuple(f))
        blob = one_filter(profile, {a: tuple(case["rows"]["a"]), b: tuple(case["rows"]["b"])})
        assert core_scores(blob, frames) == case["scores"] == [0, 5, 3, 18, 15, 8, 5]
        rows = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        rows[a], rows[b] = case["rows"]["a"], case["rows"]["b"]
        assert stat_matched.matched_scores(frames, profile, rows).tolist() == case["scores"]
        # each row alone, on the same frames, gives its own part, and the parts add up
        alone_a = core_scores(one_filter(profile, {a: tuple(case["rows"]["a"])}), frames)
        alone_b = core_scores(one_filter(profile, {b: tuple(case["rows"]["b"])}), frames)
        assert alone_a == V["one_channel"]["scores"] and alone_b == case["scores_b_alone"]
        assert [x + y for x, y in zip(alone_a, alone_b)] == case["scores"]


def test_seam_a_channel_a_filter_does_not_read_is_a_row_of_zeros():
    case = V["two_channels"]
    profile = "s24x3"
    # channel 2 carries large samples the whole time; the filter reads channels 0 and 1 only
    frames = [(case["streams"]["a"][i], case["streams"]["b"][i], 8388607 if i % 2 else -8388608) for i in range(7)]
    reads_two = one_filter(profile, {0: tuple(case["rows"]["a"]), 1: tuple(case["rows"]["b"])})
    reads_three = one_filter(profile, {0: tuple(case["rows"]["a"]), 1: tuple(case["rows"]["b"]), 2: (0, 0, 0)})
    assert core_scores(reads_two, frames) == core_scores(reads_three, frames) == case["scores"]


# ------------------------------------------------------------ (a): where a truth record says the pulse is

@pytest.mark.parametrize("profile", PROFILES)
def test_seam_a_lone_pulse_changes_its_span_by_exactly_the_pulse_and_nothing_else(profile):
    channels = C.PROFILES[profile]["channels"]
    j, length = 37, 200
    silence = [(0,) * channels] * length
    record = {"index": j, "pulse_id": C.PULSE_IDS["e0"], "amplitude_num": 1, "amplitude_den": 1}
    out, truth = inject.inject(profile, silence, [record], length)
    out = list(out)
    assert truth == (record,) and len(out) == length
    for i, frame in enumerate(out):
        want = E0[i - j] if j <= i < j + len(E0) else 0
        assert frame == (want,) * channels, "frame %d" % i
    changed = [i for i, frame in enumerate(out) if frame != (0,) * channels]
    # e0 has nine zero samples, its first and last among them (conventions.md, (a))
    assert len(E0) == 64 and E0.count(0) == 9 and E0[0] == 0 and E0[63] == 0
    assert len(changed) == 55 and changed[0] == j + 1 and changed[-1] == j + 62


@pytest.mark.parametrize("profile", PROFILES)
def test_seam_the_matched_filter_peaks_at_the_truth_index_plus_taps_less_one(profile):
    """CV5, MEASURED here for the reference pulse: quantised coefficients against the pulse itself
    at amplitude 1 are not exact multiples of one another, so the page does not promise this."""
    channels = C.PROFILES[profile]["channels"]
    j, length = 81, 300
    blob = weights.matched_filter(profile, E0, (1,) * channels)
    record = {"index": j, "pulse_id": C.PULSE_IDS["e0"], "amplitude_num": 1, "amplitude_den": 1}
    records, truth = run.detect([(0,) * channels] * length, [record], length, blob)
    scores = [r["score"] for r in records]
    peak = max(scores)
    assert [i for i, s in enumerate(scores) if s == peak] == [j + len(E0) - 1] == [truth[0]["index"] + 63]
    # the peak is each coefficient against its own sample, on every channel: integer arithmetic, written out
    rows = weights.unpack(blob)["filters"][0]
    assert peak == sum(c * p for row in rows.values() for c, p in zip(row, E0))
    assert all(r["flags"] == 0 and r["epoch"] == 0 for r in records)
    assert [r["index"] for r in records] == list(range(length))


# ------------------------------------------------------------ one pulse, one set of coefficients

@pytest.mark.parametrize("profile", PROFILES)
def test_seam_the_model_and_the_statistics_make_the_same_coefficients_from_one_pulse(profile):
    channels = C.PROFILES[profile]["channels"]
    for gains in ((1,) * channels, tuple(range(1, channels + 1)), tuple(-g for g in range(1, channels + 1))):
        model_rows = weights.unpack(weights.matched_filter(profile, E0, gains))["filters"][0]
        stat_rows = stat_quantise.quantise(stat_matched.template(E0, gains))
        assert [list(model_rows[c]) for c in range(channels)] == stat_rows.tolist(), gains
    # the peak of the set is the largest coefficient the width holds, and nothing reaches COEFF_MIN
    one = weights.unpack(weights.matched_filter(profile, E0, (1,) * channels))["filters"][0][0]
    assert max(abs(v) for v in one) == C.COEFF_MAX == 131071


def test_seam_both_quantisers_send_a_tie_to_the_even_integer():
    """e0 has no tie, so e0 alone cannot tell half-to-even from any other rule. This set can."""
    case = V["tie_set"]
    model = list(weights.unpack(weights.matched_filter("s16x1", case["values"], (1,)))["filters"][0][0])
    stat = stat_quantise.quantise(case["values"]).tolist()
    assert model == stat == case["coefficients"] == [131071, 0, 2, 2, 0, -2]


def test_seam_a_quantiser_with_another_rounding_is_seen_on_the_tie_set_and_not_on_e0():
    """The control: half away from zero, written here. It differs from the vector on the tie set.
    On e0 it agrees with both real quantisers, which is why the tie set exists."""
    from fractions import Fraction

    def away(values):
        peak = max(abs(v) for v in values)
        out = []
        for v in values:
            x = Fraction(v * C.COEFF_MAX, peak)
            whole = abs(x.numerator) // x.denominator
            if 2 * (abs(x) - whole) >= 1:
                whole += 1
            out.append(whole if x >= 0 else -whole)
        return out

    case = V["tie_set"]
    assert away(case["values"]) == case["half_away_from_zero"] != case["coefficients"]
    assert away(list(E0)) == stat_quantise.quantise(list(E0)).tolist()


# ------------------------------------------------------------ the interface: frames, and exact agreement

@pytest.mark.parametrize("profile", PROFILES)
def test_seam_every_frame_the_source_and_the_injector_hand_on_is_a_frame_the_core_takes(profile):
    prof = stream.profile(profile)
    channels = prof["channels"]
    length = 1500
    noise = source.Noise(profile, 20261123, 300, 1, length)
    schedule = [{"index": 100 + 200 * i, "pulse_id": 0, "amplitude_num": 3 - i, "amplitude_den": 2} for i in range(6)]
    blob = weights.matched_filter(profile, E0, (1,) * channels)
    pairs, truth = run.scores(noise, schedule, length, blob)
    seen = 0
    for n, (frame, record) in enumerate(pairs):
        assert type(frame) is tuple and stream.check_frame(prof, frame) is frame
        assert (record["index"], record["epoch"], record["flags"]) == (n, 0, 0)
        seen += 1
    assert seen == length and len(truth) == 6


@pytest.mark.parametrize("profile", PROFILES)
def test_seam_the_cores_scores_equal_the_statistics_scores_exactly_on_one_stream(profile):
    """Two implementations that share no code, the same integer coefficients, the same stream:
    every score equal, as integers. The statistics side says when its floats are exact."""
    channels = C.PROFILES[profile]["channels"]
    length = 4000
    gains = tuple(range(1, channels + 1))
    blob = weights.matched_filter(profile, E0, gains)
    rows = weights.unpack(blob)["filters"][0]
    table = [list(rows[c]) for c in range(channels)]
    assert stat_matched.scores_are_exact(profile, table)
    noise = source.Noise(profile, 20261125, 2000, 1, length)
    schedule = [{"index": 300 + 500 * i, "pulse_id": 0, "amplitude_num": 7, "amplitude_den": 3} for i in range(7)]
    pairs, _truth = run.scores(noise, schedule, length, blob)
    frames, model_scores = [], []
    for frame, record in pairs:
        frames.append(frame)
        model_scores.append(record["score"])
    stat_scores = stat_matched.matched_scores(frames, profile, table)
    assert [int(s) for s in stat_scores.tolist()] == model_scores
    assert all(float(s).is_integer() for s in stat_scores.tolist())
    assert max(abs(s) for s in model_scores) > 10 ** 8, "scores of a real size, not zeros"

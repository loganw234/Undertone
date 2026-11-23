"""STAT: the foreign matched filter over an integer stream, under both profiles.

Expected scores are worked by hand in the small cases, and by a plain Python
integer loop written here in the large ones. Channels never carry the same
data, and coefficient rows never match one another, so a fault in one channel
shows.
"""
import numpy as np
import pytest

from spec import constants as C
from stats import matched, recovery
from stats.errors import StatRefusal

PROFILES = sorted(C.PROFILES)


def by_integer_loop(frames, rows):
    """score[i] = sum over c, k of rows[c][k] * frames[i - (T-1) + k][c], zeros before the start."""
    taps = len(rows[0])
    out = []
    for i in range(len(frames)):
        total = 0
        for c, row in enumerate(rows):
            for k in range(taps):
                j = i - (taps - 1) + k
                if j >= 0:
                    total += row[k] * frames[j][c]
        out.append(total)
    return out


def varied_frames(profile_name, count, seed):
    """Frames whose channels differ from one another and reach both ends of the range."""
    p = C.PROFILES[profile_name]
    rng = np.random.Generator(np.random.PCG64(seed))
    a = rng.integers(p["sample_min"], p["sample_max"] + 1, size=(count, p["channels"]))
    a[0, :] = p["sample_min"]
    a[1, :] = p["sample_max"]
    return [tuple(int(v) for v in row) for row in a]


def varied_rows(profile_name, taps, seed):
    channels = C.PROFILES[profile_name]["channels"]
    rng = np.random.Generator(np.random.PCG64(seed))
    a = rng.integers(C.COEFF_MIN, C.COEFF_MAX + 1, size=(channels, taps))
    return [[int(v) for v in row] for row in a]


def test_stat_the_convention_by_hand_oldest_sample_first():
    # coefficients (10, 1): score[i] = 10 * x[i-1] + 1 * x[i], and x[-1] is zero.
    scores = matched.matched_scores([(1,), (2,), (3,), (4,)], "s16x1", [10, 1])
    assert scores.tolist() == [1.0, 12.0, 23.0, 34.0]
    # The reversed reading, 1 * x[i-1] + 10 * x[i], would give 10, 21, 32, 43.
    assert scores.tolist() != [10.0, 21.0, 32.0, 43.0]


def test_stat_the_worked_answer_of_the_conventions_page():
    """The lead's page of seam conventions, docs/model/conventions.md on the round branch, works one
    case by hand: one channel, coefficients 1, 2, 3, the pulse 1, 2, 3 injected with index 2 into
    seven zeros. Its scores are 0, 0, 3, 8, 14, 8, 3; with a threshold of 14 there is no crossing,
    and with 13 there is one, at index 4."""
    frames = [(0,), (0,), (1,), (2,), (3,), (0,), (0,)]
    scores = matched.matched_scores(frames, "s16x1", [1, 2, 3])
    assert scores.tolist() == [0.0, 0.0, 3.0, 8.0, 14.0, 8.0, 3.0]
    assert scores.tolist() != [0.0, 0.0, 1.0, 4.0, 10.0, 12.0, 9.0], "that is the newest-first reading"
    at_14 = recovery.recovery_count(scores, [2], 14.0, lag=2, taps=3, pulse_len=3)
    at_13 = recovery.recovery_count(scores, [2], 13.0, lag=2, taps=3, pulse_len=3)
    assert (at_14["at_index"], at_13["at_index"]) == (0, 1)
    assert int(np.argmax(scores)) == 4 == 2 + 3 - 1


def test_stat_three_channels_by_hand_one_row_per_channel_summed():
    frames = [(1, 10, 100), (2, 20, 200)]
    rows = [[1, 1], [2, 0], [0, 3]]
    # score[0] = (1*0 + 1*1) + (2*0 + 0*10) + (0*0 + 3*100) = 301
    # score[1] = (1*1 + 1*2) + (2*10 + 0*20) + (0*100 + 3*200) = 623
    assert matched.matched_scores(frames, "s24x3", rows).tolist() == [301.0, 623.0]


@pytest.mark.parametrize("profile_name", PROFILES)
def test_stat_a_pulse_whose_first_sample_is_at_j_peaks_at_j_plus_taps_minus_one(profile_name):
    pulse = C.PULSES["e0"]
    channels = C.PROFILES[profile_name]["channels"]
    gains = (3, -1, 2)[:channels]
    rows = matched.template(pulse, gains)
    j, taps = 200, len(pulse)
    frames = np.zeros((600, channels), dtype=np.int64)
    frames[j:j + taps, :] = rows.T
    scores = matched.matched_scores(frames, profile_name, rows)
    energy = sum(g * g for g in gains) * sum(v * v for v in pulse)
    assert int(np.argmax(scores)) == j + taps - 1
    assert scores[j + taps - 1] == energy
    assert (scores[:j] == 0).all(), "a causal filter cannot answer before the pulse arrives"


@pytest.mark.parametrize("profile_name", PROFILES)
@pytest.mark.parametrize("taps", [1, 5, 64, C.MAX_TAPS])
def test_stat_integer_coefficients_give_the_integer_sum_exactly(profile_name, taps):
    frames = varied_frames(profile_name, 300, seed=11 + taps)
    rows = varied_rows(profile_name, taps, seed=97 + taps)
    assert matched.scores_are_exact(profile_name, rows)
    got = matched.matched_scores(frames, profile_name, rows)
    want = by_integer_loop(frames, rows)
    assert len(got) == len(frames) == 300, "one score per frame"
    assert [int(v) for v in got] == want
    assert all(float(w) == g for w, g in zip(want, got.tolist()))


@pytest.mark.parametrize("profile_name", PROFILES)
def test_stat_the_extreme_inputs_stay_exact(profile_name):
    """Every sample and every coefficient at its largest magnitude, signs aligned: the largest score there is."""
    p = C.PROFILES[profile_name]
    taps = C.MAX_TAPS
    frames = [(p["sample_min"],) * p["channels"]] * (taps + 3)
    rows = [[C.COEFF_MIN] * taps] * p["channels"]
    worst = p["sample_min"] * C.COEFF_MIN * taps * p["channels"]
    assert worst == 2 ** (p["sample_bits"] - 1) * 2 ** 17 * 128 * p["channels"]
    assert worst < 2 ** 53
    assert matched.scores_are_exact(profile_name, rows)
    got = matched.matched_scores(frames, profile_name, rows)
    assert int(got[taps - 1]) == worst and got[taps - 1] == float(worst)
    assert [int(v) for v in got] == by_integer_loop(frames, rows)
    # the other sign, at the positive extremes
    frames = [(p["sample_max"],) * p["channels"]] * (taps + 3)
    rows = [[C.COEFF_MAX] * taps] * p["channels"]
    assert [int(v) for v in matched.matched_scores(frames, profile_name, rows)] == by_integer_loop(frames, rows)


def test_stat_exactness_is_claimed_only_where_it_holds():
    assert not matched.scores_are_exact("s16x1", [0.5, 1.0])
    assert matched.scores_are_exact("s16x1", [1.0, -2.0]), "integer-valued floats are integers"
    # 2^53 / 2^15 = 2^38: a single coefficient of 2^38 reaches the limit, one below it does not.
    assert not matched.scores_are_exact("s16x1", [2 ** 38])
    assert matched.scores_are_exact("s16x1", [2 ** 38 - 1])
    # the same total spread over three channels of the wider profile
    assert not matched.scores_are_exact("s24x3", [[2 ** 29], [2 ** 29], [0]])
    assert matched.scores_are_exact("s24x3", [[2 ** 29], [2 ** 29 - 1], [0]])


@pytest.mark.parametrize("profile_name", PROFILES)
def test_stat_real_coefficients_agree_with_a_plain_loop(profile_name):
    frames = varied_frames(profile_name, 200, seed=5)
    channels = C.PROFILES[profile_name]["channels"]
    rng = np.random.Generator(np.random.PCG64(6))
    rows = rng.standard_normal((channels, 17)).tolist()
    got = matched.matched_scores(frames, profile_name, rows)
    want = by_integer_loop(frames, rows)
    scale = max(abs(w) for w in want)
    assert max(abs(g - w) for g, w in zip(got.tolist(), want)) <= 1e-12 * scale


def test_stat_each_channel_reaches_the_score():
    """Zero one channel's row at a time: the score must change, and by exactly that channel's part."""
    frames = varied_frames("s24x3", 120, seed=21)
    rows = varied_rows("s24x3", 9, seed=22)
    whole = matched.matched_scores(frames, "s24x3", rows)
    for c in range(3):
        without = [row if i != c else [0] * 9 for i, row in enumerate(rows)]
        only = [row if i == c else [0] * 9 for i, row in enumerate(rows)]
        part = matched.matched_scores(frames, "s24x3", only)
        assert np.count_nonzero(part) > 100
        assert (matched.matched_scores(frames, "s24x3", without) == whole - part).all()


def test_stat_an_array_and_a_list_of_tuples_are_the_same_stream():
    frames = varied_frames("s24x3", 80, seed=31)
    rows = varied_rows("s24x3", 7, seed=32)
    as_list = matched.matched_scores(frames, "s24x3", rows)
    for dtype in (np.int32, np.int64):
        assert (matched.matched_scores(np.array(frames, dtype=dtype), "s24x3", rows) == as_list).all()
    assert (matched.matched_scores(iter(frames), "s24x3", rows) == as_list).all()


def test_stat_an_empty_stream_gives_no_scores():
    assert matched.matched_scores([], "s16x1", [1, 2]).tolist() == []


def test_stat_template_lays_the_pulse_on_each_channel_with_its_gain():
    rows = matched.template((1, -2, 3), (3, -1, 2))
    assert rows.tolist() == [[3, -6, 9], [-1, 2, -3], [2, -4, 6]]
    assert rows.dtype.kind == "i"


@pytest.mark.parametrize("bad", ["no-such-profile", "", None, 16, ("s16x1",)])
def test_stat_an_undeclared_profile_is_refused_by_the_definitions_name(bad):
    with pytest.raises(StatRefusal) as e:
        matched.matched_scores([(0,)], bad, [1])
    assert e.value.name == "PROFILE_UNKNOWN"


@pytest.mark.parametrize("profile_name", PROFILES)
def test_stat_one_sample_one_past_either_extreme_in_any_channel_is_refused(profile_name):
    p = C.PROFILES[profile_name]
    rows = [[1, 1]] * p["channels"]
    tried = 0
    for bad in (p["sample_min"] - 1, p["sample_max"] + 1):
        for channel in range(p["channels"]):
            frame = [0] * p["channels"]
            frame[channel] = bad
            for stream in ([(0,) * p["channels"], tuple(frame)], np.array([[0] * p["channels"], frame])):
                with pytest.raises(StatRefusal) as e:
                    matched.matched_scores(stream, profile_name, rows)
                assert e.value.name == "SAMPLE_RANGE"
                tried += 1
    assert tried == 4 * p["channels"]


@pytest.mark.parametrize("stream, name", [
    ([(0, 0)], "CHANNELS"),
    ([()], "CHANNELS"),
    ([[0]], "CHANNELS"),
    ([0], "CHANNELS"),
    (np.zeros((4, 2), dtype=np.int64), "CHANNELS"),
    (np.zeros(4, dtype=np.int64), "CHANNELS"),
    ([(1.0,)], "SAMPLE_RANGE"),
    ([(True,)], "SAMPLE_RANGE"),
    (np.zeros((4, 1), dtype=np.float64), "SAMPLE_RANGE"),
    (np.zeros((4, 1), dtype=bool), "SAMPLE_RANGE"),
])
def test_stat_a_stream_that_is_not_frames_of_integers_is_refused_by_name(stream, name):
    with pytest.raises(StatRefusal) as e:
        matched.matched_scores(stream, "s16x1", [1, 2])
    assert e.value.name == name


@pytest.mark.parametrize("profile_name, coeffs, name", [
    ("s16x1", [1] * (C.MAX_TAPS + 1), "SHAPE_TAPS"),
    ("s16x1", [], "SHAPE_TAPS"),
    ("s16x1", [[1, 2], [3, 4]], "CHANNELS"),
    ("s24x3", [1, 2, 3], "CHANNELS"),
    ("s24x3", [[1, 2], [3, 4]], "CHANNELS"),
    ("s24x3", [[1, 2], [3, 4], [5]], "SHAPE"),
    ("s16x1", [[[1]]], "SHAPE"),
    ("s16x1", [1.0, float("nan")], "NOT_FINITE"),
    ("s16x1", ["a"], "VALUE_TYPE"),
    ("s16x1", [2 ** 53 + 2], "INEXACT_INPUT"),
])
def test_stat_a_coefficient_set_outside_the_shape_is_refused_by_name(profile_name, coeffs, name):
    channels = C.PROFILES[profile_name]["channels"]
    with pytest.raises(StatRefusal) as e:
        matched.matched_scores([(0,) * channels], profile_name, coeffs)
    assert e.value.name == name
    assert C.MAX_TAPS == 128

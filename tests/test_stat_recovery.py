"""STAT: thresholds, signal-free scores, the injection-recovery count, the paired cost.

Every expected answer is worked by hand, in the comment beside it.
"""
import math

import numpy as np
import pytest

from stats import recovery
from stats.errors import StatRefusal


def refused(name, fn, *args, **kwargs):
    with pytest.raises(StatRefusal) as e:
        fn(*args, **kwargs)
    assert e.value.name == name


def test_stat_known_threshold_by_hand():
    # Q^-1(0.5) = 0: the threshold sits at the noise mean.
    assert recovery.threshold_known_sigma(0.5, 2.0, [3, 4]) == 0.0
    # Q^-1(0.01) = 2.3263478740408408 (tables); sigma 2; norm((3, 4)) = 5.
    assert recovery.threshold_known_sigma(0.01, 2.0, [3, 4]) == pytest.approx(23.263478740408408, rel=1e-12)
    # two channels are one longer vector: norm of rows (3, 0), (0, 4) is 5 as well
    assert recovery.threshold_known_sigma(0.01, 2.0, [[3, 0], [0, 4]]) == pytest.approx(23.263478740408408, rel=1e-12)
    refused("SIGMA", recovery.threshold_known_sigma, 0.01, 0.0, [3, 4])
    refused("PROBABILITY_RANGE", recovery.threshold_known_sigma, 1.0, 2.0, [3, 4])


def test_stat_signal_free_indexes_by_hand():
    # 20 scores, 3 taps, a 3-sample pulse whose first sample is at 8.
    # Scores 0 and 1 saw fewer than 3 samples. Score i saw samples i-2..i; the pulse is at 8..10;
    # so scores 8..12 touched it. The grid is 2, 5, 8, 11, 14, 17; 8 and 11 are touched.
    assert recovery.signal_free_indexes(20, 3, [8], 3).tolist() == [2, 5, 14, 17]
    # Each edge of the touched range, put exactly on a grid point (a pulse at j touches j .. j + 4):
    assert recovery.signal_free_indexes(20, 3, [7], 3).tolist() == [2, 5, 14, 17]       # 7..11: 11 is the last touched
    assert recovery.signal_free_indexes(20, 3, [6], 3).tolist() == [2, 5, 11, 14, 17]   # 6..10: 11 is the first free
    assert recovery.signal_free_indexes(20, 3, [9], 3).tolist() == [2, 5, 8, 14, 17]    # 9..13: 8 is the last free before
    assert recovery.signal_free_indexes(20, 3, [11], 3).tolist() == [2, 5, 8, 17]       # 11..15: 11 is the first touched
    # No injection at all: the whole grid.
    assert recovery.signal_free_indexes(20, 3, [], 3).tolist() == [2, 5, 8, 11, 14, 17]
    # A longer stride is allowed; a shorter one is refused, because neighbours share samples.
    assert recovery.signal_free_indexes(20, 3, [8], 3, stride=6).tolist() == [2, 14]
    refused("STRIDE_SHORT", recovery.signal_free_indexes, 20, 3, [8], 3, stride=2)
    # A pulse at the very end touches scores up to the last one and no further.
    assert recovery.signal_free_indexes(20, 3, [17], 3).tolist() == [2, 5, 8, 11, 14]
    # Two pulses, in either order.
    assert recovery.signal_free_indexes(20, 3, [14, 2], 3).tolist() == [8, 11]
    refused("INDEX_RANGE", recovery.signal_free_indexes, 20, 3, [20], 3)
    refused("INDEX_RANGE", recovery.signal_free_indexes, 20, 3, [-1], 3)


def test_stat_signal_free_scores_are_the_scores_at_those_indexes():
    scores = np.arange(20) * 10.0
    assert recovery.signal_free_scores(scores, 3, [8], 3).tolist() == [20.0, 50.0, 140.0, 170.0]


def test_stat_threshold_from_scores_by_hand():
    # The scores are 1..1000 in a shuffled order. pfa 0.1 -> k = 100 may cross.
    # The 101st largest is 900, and exactly 901..1000, one hundred scores, lie strictly above it.
    rng = np.random.Generator(np.random.PCG64(3))
    scores = rng.permutation(np.arange(1, 1001)).astype(float)
    t = recovery.threshold_from_scores(scores, 0.1)
    assert (t["threshold"], t["m"], t["k"], t["above"]) == (900.0, 1000, 100, 100)
    assert t["pfa_effective"] == 101 / 1001
    # pfa 0.2 -> k = 200, the 201st largest is 800.
    assert recovery.threshold_from_scores(scores, 0.2)["threshold"] == 800.0


def test_stat_the_crossing_count_is_the_floor_of_the_floats_exact_value():
    """k = floor(pfa * m) is worked on the exact value of the float it is handed. The float written
    0.29 is a hair BELOW 0.29, so over 10,000 scores k is 2,899, one fewer than the decimal reads;
    0.57 and 0.58 behave the same. 0.25 is exact in binary and gives 2,500. The scores are
    0..9999, so the (k+1)-th largest is 9999 - k."""
    scores = np.arange(10_000, dtype=float)
    for pfa, k in ((0.29, 2899), (0.57, 5699), (0.58, 5799), (0.25, 2500), (0.01, 100)):
        t = recovery.threshold_from_scores(scores, pfa)
        assert (t["k"], t["above"], t["threshold"]) == (k, k, float(9999 - k)), pfa
        # whatever k is, the figure handed on is worked from the k actually used
        assert t["pfa_effective"] == (k + 1) / 10_001
    # never MORE crossings than the float's value allows: k / m is at or below pfa
    assert 2899 / 10_000 <= 0.29 and 5699 / 10_000 <= 0.57


def test_stat_threshold_from_tied_scores_reports_how_few_cross():
    # 1000 scores: 850 zeros and 150 fives. k = 100; the 101st largest is 5; nothing is strictly above.
    scores = np.array([0.0] * 850 + [5.0] * 150)
    t = recovery.threshold_from_scores(scores, 0.1)
    assert (t["threshold"], t["k"], t["above"]) == (5.0, 100, 0)


def test_stat_threshold_needs_a_hundred_crossings():
    scores = np.arange(9999, dtype=float)
    refused("TOO_FEW_NOISE_SCORES", recovery.threshold_from_scores, scores, 0.01)      # k = 99
    assert recovery.threshold_from_scores(np.arange(10000, dtype=float), 0.01)["k"] == 100
    refused("NOT_FINITE", recovery.threshold_from_scores, np.array([1.0, float("nan")] * 600), 0.1)
    refused("PROBABILITY_RANGE", recovery.threshold_from_scores, np.arange(10000, dtype=float), 0.0)


def scores_with(peaks, length=100):
    s = np.zeros(length)
    for index, value in peaks.items():
        s[index] = value
    return s


def test_stat_recovery_at_the_injected_index_by_hand():
    # Truth indexes 10, 40, 70; lag 3; so the scores read are 13, 43, 73. Threshold 5.
    scores = scores_with({13: 9.0, 43: 5.0, 44: 9.0, 73: 5.000001})
    r = recovery.recovery_count(scores, [10, 40, 70], 5.0, lag=3, taps=4, pulse_len=4)
    # 9 > 5: found. 5 > 5 is false: a score EQUAL to the threshold is not a crossing. 5.000001 > 5: found.
    assert (r["n"], r["at_index"]) == (3, 2)
    assert r["hits_at_index"].tolist() == [True, False, True]
    assert r["in_window"] == 2 and r["hits_in_window"].tolist() == [True, False, True]
    assert r["minimum_spacing"] == 4


def test_stat_recovery_within_a_window_by_hand():
    # The same scores with a window of 1: the injection at 40 reads scores 42..44, and 44 holds a 9.
    scores = scores_with({13: 9.0, 43: 5.0, 44: 9.0, 73: 5.000001})
    r = recovery.recovery_count(scores, [10, 40, 70], 5.0, lag=3, taps=4, pulse_len=4, window=1)
    assert (r["at_index"], r["in_window"]) == (2, 3)
    assert r["hits_in_window"].tolist() == [True, True, True]
    assert r["minimum_spacing"] == 6
    # A crossing two samples away is outside a window of 1 and inside a window of 2, on either side.
    for index in (41, 45):
        scores = scores_with({index: 9.0})
        assert recovery.recovery_count(scores, [40], 5.0, lag=3, taps=4, pulse_len=4, window=1)["in_window"] == 0
        assert recovery.recovery_count(scores, [40], 5.0, lag=3, taps=4, pulse_len=4, window=2)["in_window"] == 1


def test_stat_the_order_of_the_truth_indexes_is_kept_in_the_hits():
    scores = scores_with({13: 9.0})
    r = recovery.recovery_count(scores, [70, 10, 40], 5.0, lag=3, taps=4, pulse_len=4)
    assert r["hits_at_index"].tolist() == [False, True, False]


def test_stat_minimum_spacing_by_hand():
    # lag = taps - 1 and a pulse as long as the filter: taps + 2 * window.
    assert recovery.minimum_spacing(64, 64, 63, 0) == 64
    assert recovery.minimum_spacing(64, 64, 63, 10) == 84
    # a pulse longer than the filter reaches further into the next injection's samples
    assert recovery.minimum_spacing(4, 10, 3, 0) == 10
    # a larger lag reads scores further on
    assert recovery.minimum_spacing(4, 4, 9, 2) == 12


def test_stat_injections_closer_than_separate_trials_are_refused():
    scores = np.zeros(400)
    ok = recovery.recovery_count(scores, [10, 74], 5.0, lag=63, taps=64, pulse_len=64)
    assert ok["n"] == 2
    refused("INJECTIONS_OVERLAP", recovery.recovery_count, scores, [10, 73], 5.0, lag=63, taps=64, pulse_len=64)
    refused("INJECTIONS_OVERLAP", recovery.recovery_count, scores, [10, 10], 5.0, lag=63, taps=64, pulse_len=64)
    # with a window of 5 the same schedule needs 74 between them
    refused("INJECTIONS_OVERLAP", recovery.recovery_count, scores, [10, 83], 5.0, lag=63, taps=64, pulse_len=64, window=5)
    assert recovery.recovery_count(scores, [10, 84], 5.0, lag=63, taps=64, pulse_len=64, window=5)["n"] == 2
    # the order given does not hide a close pair
    refused("INJECTIONS_OVERLAP", recovery.recovery_count, scores, [200, 10, 73], 5.0, lag=63, taps=64, pulse_len=64)


def test_stat_a_count_that_cannot_be_made_is_refused_by_name():
    scores = np.zeros(100)
    refused("NO_INJECTIONS", recovery.recovery_count, scores, [], 5.0, lag=3, taps=4, pulse_len=4)
    # the last score is index 99: truth 96 with lag 3 reads it; truth 97 reads past the end
    assert recovery.recovery_count(scores, [96], 5.0, lag=3, taps=4, pulse_len=4)["n"] == 1
    refused("INDEX_RANGE", recovery.recovery_count, scores, [97], 5.0, lag=3, taps=4, pulse_len=4)
    refused("INDEX_RANGE", recovery.recovery_count, scores, [96], 5.0, lag=3, taps=4, pulse_len=4, window=1)
    refused("INDEX_RANGE", recovery.recovery_count, scores, [-1], 5.0, lag=3, taps=4, pulse_len=4)
    # a window that reaches before the stream's first score
    refused("INDEX_RANGE", recovery.recovery_count, scores, [0], 5.0, lag=3, taps=4, pulse_len=4, window=4)
    assert recovery.recovery_count(scores, [0], 5.0, lag=3, taps=4, pulse_len=4, window=3)["n"] == 1
    bad = scores.copy()
    bad[50] = float("nan")
    refused("NOT_FINITE", recovery.recovery_count, bad, [10], 5.0, lag=3, taps=4, pulse_len=4)
    refused("NOT_FINITE", recovery.recovery_count, scores, [10], float("nan"), lag=3, taps=4, pulse_len=4)
    refused("SHAPE", recovery.recovery_count, scores, [10.0], 5.0, lag=3, taps=4, pulse_len=4)
    refused("SHAPE", recovery.recovery_count, scores, [10], 5.0, lag=-1, taps=4, pulse_len=4)
    refused("SHAPE", recovery.recovery_count, scores, [10], 5.0, lag=3, taps=0, pulse_len=4)
    refused("SHAPE", recovery.recovery_count, np.zeros((10, 10)), [1], 5.0, lag=3, taps=4, pulse_len=4)


def test_stat_paired_cost_by_hand():
    a = np.array([True, True, False, False, True])
    b = np.array([True, False, True, False, True])
    # found by a only: 1 (the second). By b only: 1 (the third). They cancel.
    r = recovery.paired_cost(a, b)
    assert (r["n"], r["found_a"], r["found_b"], r["a_only"], r["b_only"]) == (5, 3, 3, 1, 1)
    assert r["cost"] == 0.0
    assert r["se"] == pytest.approx(math.sqrt(2.0) / 5.0, rel=1e-15)
    # a finds three of four, b one of four, and b's one is among a's: a_only 2, b_only 0.
    r = recovery.paired_cost(np.array([True, True, True, False]), np.array([True, False, False, False]))
    assert (r["a_only"], r["b_only"], r["cost"]) == (2, 0, 0.5)
    assert r["se"] == pytest.approx(math.sqrt(2 - 4 / 4) / 4, rel=1e-15)      # 0.25
    # identical detectors: no cost and no spread
    r = recovery.paired_cost(a, a)
    assert (r["cost"], r["se"]) == (0.0, 0.0)
    # the sign: b better than a is a negative cost
    assert recovery.paired_cost(b & a, a | b)["cost"] == -2 / 5


def test_stat_paired_cost_refuses_what_is_not_paired():
    a = np.array([True, False])
    refused("SHAPE", recovery.paired_cost, a, np.array([True]))
    refused("SHAPE", recovery.paired_cost, a, np.array([1, 0]))
    refused("NO_INJECTIONS", recovery.paired_cost, np.array([], dtype=bool), np.array([], dtype=bool))

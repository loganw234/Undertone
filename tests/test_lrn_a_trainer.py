"""The learning rule (learn/trainer.py), held to answers worked by hand and to arithmetic written again here.

Every expected answer is in vectors/lrn-a/rule.json, worked by hand with its sums, or is plain
integer arithmetic written out in the test. None comes from the code it judges.

These tests run under both profiles and give every channel different values: a rule that mixed
two channels' rows would give other numbers.
"""
import json
import os
from fractions import Fraction

import numpy as np
import pytest

from spec import constants as C
from model import inject, source
from learn import trainer
from learn.errors import LearnRefusal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = sorted(C.PROFILES)

with open(os.path.join(ROOT, "vectors", "lrn-a", "rule.json"), encoding="utf-8") as _f:
    V = {case["name"]: case for case in json.load(_f)["cases"]}


def fractions_of(rows):
    return tuple(tuple(Fraction(n, d) for n, d in row) for row in rows)


def refused(name, call, *args):
    with pytest.raises(LearnRefusal) as e:
        call(*args)
    assert e.value.name == name, "refused as %s, expected %s" % (e.value.name, name)


# ------------------------------------------------------------ the hand-worked cases

@pytest.mark.parametrize("name", ["one-channel-two-records", "three-channels-each-different"])
def test_lrn_a_trainer_the_hand_worked_stream_gives_the_hand_worked_sums_and_weights(name):
    case = V[name]
    channels = C.PROFILES[case["profile"]]["channels"]
    frames = np.array(case["frames"], dtype=np.int64)
    assert trainer.labelled_windows(case["truth_indexes"], case["taps"], len(frames)) == [tuple(w) for w in case["windows"]]
    learner = trainer.train(frames, case["truth_indexes"], case["taps"])
    assert learner.counts == case["counts"]
    assert learner.sums[0].tolist() == case["sum_label_0"] and learner.sums[1].tolist() == case["sum_label_1"]
    assert learner.weights() == fractions_of(case["weights"])
    assert len(learner.weights()) == channels and len({row for row in learner.weights()}) == channels, \
        "every channel's row is different, so a mix-up cannot hide"


def test_lrn_a_trainer_unequal_counts_divide_each_sum_by_its_own_count():
    case = V["unequal-counts-and-two-ties"]
    learner = trainer.MeanDifference(1, case["taps"])
    for u in case["updates"]:
        learner.update(np.array(u["window"], dtype=np.int64), u["label"])
    assert learner.counts == case["counts"] == [2, 1]
    assert learner.sums[0].tolist() == case["sum_label_0"] and learner.sums[1].tolist() == case["sum_label_1"]
    assert learner.weights() == fractions_of(case["weights"]) == ((Fraction(2), Fraction(4), Fraction(-2)),)
    # the broken thing, in the test: one count for both sums gives another answer on this case
    wrong = tuple(Fraction(a - b, 2) for a, b in zip((3, 4, -1), (2, 0, 2)))
    assert wrong != learner.weights()[0]


# ------------------------------------------------------------ blank, and what one update is

@pytest.mark.parametrize("profile", PROFILES)
def test_lrn_a_trainer_blank_is_every_weight_zero_until_each_label_has_a_window(profile):
    channels = C.PROFILES[profile]["channels"]
    learner = trainer.MeanDifference(channels, 4)
    blank = tuple(tuple(Fraction(0) for _ in range(4)) for _ in range(channels))
    assert learner.counts == [0, 0] and not learner.sums.any() and learner.weights() == blank == learner.start()
    window = np.arange(4 * channels, dtype=np.int64).reshape(4, channels) + 1
    learner.update(window, 1)
    assert learner.counts == [0, 1] and learner.weights() == blank, "one label alone is still blank"
    learner.update(np.zeros((4, channels), dtype=np.int64), 0)
    assert learner.weights() == tuple(tuple(Fraction(int(window[k][c])) for k in range(4)) for c in range(channels))
    assert learner.weights() != blank


@pytest.mark.parametrize("profile", PROFILES)
def test_lrn_a_trainer_the_weights_do_not_depend_on_the_order_of_the_windows(profile):
    channels = C.PROFILES[profile]["channels"]
    frames = np.array(list(source.Noise(profile, 77, 300, 1, 400)), dtype=np.int64)
    windows = [(frames[s:s + 5], (s // 5) % 2) for s in range(0, 400, 5)]
    forward, backward = trainer.MeanDifference(channels, 5), trainer.MeanDifference(channels, 5)
    for w, y in windows:
        forward.update(w, y)
    for w, y in reversed(windows):
        backward.update(w, y)
    assert forward.weights() == backward.weights() and forward.counts == [40, 40]
    # and against the rule written again, in plain Python integers
    for c in range(channels):
        for k in range(5):
            s1 = sum(int(w[k][c]) for w, y in windows if y == 1)
            s0 = sum(int(w[k][c]) for w, y in windows if y == 0)
            assert forward.weights()[c][k] == Fraction(s1, 40) - Fraction(s0, 40)


# ------------------------------------------------------------ what it converges to, with no noise in the way

@pytest.mark.parametrize("profile", PROFILES)
def test_lrn_a_trainer_on_a_stream_that_is_only_injections_the_weights_are_exactly_what_was_injected(profile):
    """The mean of the signal windows less the mean of the signal-free ones is what the injector
    added, whatever the stream's own level: here a different constant on every channel."""
    channels = C.PROFILES[profile]["channels"]
    taps = len(C.PULSES["e0"])
    level = tuple(5 - 6 * c for c in range(channels))                 # 5, -1, -7: no two channels alike
    length = 128 * 6
    schedule = [{"index": 64 + 128 * i, "pulse_id": C.PULSE_IDS["e0"], "amplitude_num": 3, "amplitude_den": 2}
                for i in range(6)]
    stream, truth = inject.inject(profile, [level] * length, schedule, length)
    frames = np.array(list(stream), dtype=np.int64)
    learner = trainer.train(frames, [r["index"] for r in truth], taps)
    added = inject.scaled_pulse(C.PULSE_IDS["e0"], 3, 2)
    assert learner.counts == [6, 6]
    assert learner.weights() == tuple(tuple(Fraction(v) for v in added) for _ in range(channels))
    assert learner.sums[0].tolist() == [[6 * v for v in level]] * taps, "the signal-free sum holds the level and nothing else"


@pytest.mark.parametrize("profile", PROFILES)
def test_lrn_a_trainer_reads_the_truth_index_and_no_frame_outside_its_windows(profile):
    """Frames outside every labelled window can be anything: the weights do not move."""
    channels = C.PROFILES[profile]["channels"]
    frames = np.array(list(source.Noise(profile, 5, 200, 1, 60)), dtype=np.int64)
    indexes = [10, 40]                                              # windows 6..13 and 36..43 with 4 taps
    first = trainer.train(frames, indexes, 4).weights()
    changed = frames.copy()
    for i in list(range(0, 6)) + list(range(14, 36)) + list(range(44, 60)):
        changed[i] = 1000 + i
    assert trainer.train(changed, indexes, 4).weights() == first
    inside = frames.copy()
    inside[13][channels - 1] += 1                                   # the last frame of a signal window, the last channel
    assert trainer.train(inside, indexes, 4).weights() != first


# ------------------------------------------------------------ refusals, each by its name

def test_lrn_a_trainer_refuses_by_name_and_adds_nothing():
    frames = np.zeros((40, 1), dtype=np.int64)
    ok = trainer.labelled_windows([8, 16, 30], 4, 40)
    assert ok == [(8, 1), (4, 0), (16, 1), (12, 0), (30, 1), (26, 0)]
    # a window that leaves the period, at each end, by one frame
    refused("WINDOW_OUTSIDE_PERIOD", trainer.labelled_windows, [3], 4, 40)        # its signal-free window starts at -1
    assert trainer.labelled_windows([4], 4, 40) == [(4, 1), (0, 0)]
    refused("WINDOW_OUTSIDE_PERIOD", trainer.labelled_windows, [37], 4, 40)       # its signal window ends at frame 40
    assert trainer.labelled_windows([36], 4, 40) == [(36, 1), (32, 0)]
    # a signal-free window the pulse before reaches into: 8 apart is the least, 7 is refused
    refused("WINDOW_NOT_FREE", trainer.labelled_windows, [8, 15], 4, 40)
    assert trainer.labelled_windows([8, 16], 4, 40)[-1] == (12, 0)
    # two pulses in one window, out of order, or not ints
    refused("TRAINER_INPUT", trainer.labelled_windows, [8, 11], 4, 40)
    refused("TRAINER_INPUT", trainer.labelled_windows, [16, 8], 4, 40)
    refused("TRAINER_INPUT", trainer.labelled_windows, [8.0], 4, 40)
    refused("TRAINER_INPUT", trainer.labelled_windows, [True], 4, 40)
    refused("TRAINER_INPUT", trainer.labelled_windows, [8], 0, 40)
    # frames that are not integers, or of another shape, or too large to sum exactly
    learner = trainer.MeanDifference(1, 4)
    refused("TRAINER_INPUT", trainer.train, np.zeros((40, 1)), [8], 4)
    refused("TRAINER_INPUT", trainer.train, [[0]] * 40, [8], 4)
    refused("TRAINER_INPUT", trainer.train, np.zeros((40, 2), dtype=np.int64), [8], 4, learner)
    refused("TRAINER_INPUT", trainer.train, frames, [8], 5, learner)
    big = frames.copy()
    big[9][0] = 1 << 31
    refused("TRAINER_INPUT", trainer.train, big, [8], 4)
    big[9][0] = (1 << 31) - 1
    assert trainer.train(big, [8], 4).counts == [1, 1]
    refused("TRAINER_INPUT", learner.update, np.zeros((4, 1), dtype=np.int64), 2)
    refused("TRAINER_INPUT", learner.update, np.zeros((4, 1), dtype=np.int64), True)
    refused("TRAINER_INPUT", learner.update, np.zeros((3, 1), dtype=np.int64), 1)
    refused("TRAINER_INPUT", trainer.MeanDifference, 0, 4)
    assert learner.counts == [0, 0] and not learner.sums.any(), "a refused call added nothing"
    # a refusal part-way through a list of records adds none of them
    refused("WINDOW_NOT_FREE", trainer.train, frames, [8, 16, 23], 4, learner)
    assert learner.counts == [0, 0]


def test_lrn_a_trainer_refuses_more_windows_than_its_sums_hold():
    learner = trainer.MeanDifference(1, 2)
    learner.counts[1] = trainer.COUNT_LIMIT
    refused("TRAINER_COUNT", learner.update, np.zeros((2, 1), dtype=np.int64), 1)
    learner.counts[1] = trainer.COUNT_LIMIT - 1
    learner.update(np.zeros((2, 1), dtype=np.int64), 1)
    assert learner.counts[1] == trainer.COUNT_LIMIT
    refused("TRAINER_COUNT", trainer.train, np.zeros((8, 1), dtype=np.int64), [4], 2, learner)
    # the bound is the one that keeps a sum exact: the largest sample times the most windows fits 63 bits
    assert (trainer.SAMPLE_LIMIT - 1) * trainer.COUNT_LIMIT < 1 << 63
    assert max(max(abs(p["sample_min"]), p["sample_max"]) for p in C.PROFILES.values()) < trainer.SAMPLE_LIMIT


def test_lrn_a_errors_a_refusal_carries_a_declared_name_and_no_other():
    from learn import errors
    assert len(errors.NAMES) == len(set(errors.NAMES)) == 11
    assert not set(errors.NAMES) & set(C.REFUSALS), "the learner's names are its own; the definition's stay the model's"
    with pytest.raises(ValueError):
        errors.LearnRefusal("NOT_DECLARED")
    assert errors.LearnRefusal("TRAINED_ON", "x").name == "TRAINED_ON"

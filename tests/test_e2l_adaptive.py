"""learn/adaptive.py: the adaptive and the reset models' learners keep the blocks they say, and no others.

Each test states the answer it expects. The known answers of the small cases are worked here by plain
arithmetic on Fractions, without `learn.trainer`: the difference of the mean signal window and the mean
signal-free window, channel by channel. Every case that holds a learner's weights runs under both
profiles' channel counts, and every channel's samples differ from every other's, so a learner that mixed
or dropped a channel is seen. The case of stage E2's own blocks and the refusals run on one channel.
"""
from fractions import Fraction

import numpy as np
import pytest

from spec import constants as C
from learn import adaptive, trainer
from learn.errors import LearnRefusal

PROFILES = sorted(C.PROFILES)
TAPS = 2
SPACING = 4                     # a trial every 4 frames, its pulse at frame 2 of the 4: label 0 is frames 0-1, label 1 frames 2-3


def block(number, channels, trials=2):
    """A training block of `trials` trials: frames (SPACING * trials, channels), every value distinct, and its truth indexes."""
    n = SPACING * trials
    frames = np.array([[1000 * (c + 1) + 37 * number * (c + 2) + (i * i + 3 * c * i) % 23 + ((7 * number + 1) * i * (c + 1)) % 29
                        - 11 for c in range(channels)] for i in range(n)], dtype=np.int64)
    return frames, [2 + SPACING * t for t in range(trials)]


def by_hand(blocks, channels):
    """The difference of the two class means over these blocks' windows, by plain arithmetic: rows of Fractions."""
    sums, counts = {0: [[0] * TAPS for _ in range(channels)], 1: [[0] * TAPS for _ in range(channels)]}, {0: 0, 1: 0}
    for frames, indexes in blocks:
        for j in indexes:
            for label, first in ((1, j), (0, j - TAPS)):
                counts[label] += 1
                for c in range(channels):
                    for k in range(TAPS):
                        sums[label][c][k] += int(frames[first + k][c])
    return tuple(tuple(Fraction(sums[1][c][k], counts[1]) - Fraction(sums[0][c][k], counts[0]) for k in range(TAPS))
                 for c in range(channels))


@pytest.mark.parametrize("profile", PROFILES)
def test_e2l_adaptive_a_window_keeps_exactly_its_most_recent_blocks(profile):
    channels = C.PROFILES[profile]["channels"]
    blocks = [block(b, channels) for b in range(5)]
    w = adaptive.Window(channels, TAPS, 3)
    assert w.held() == () and w.records() == 0
    assert w.weights() == tuple(tuple(Fraction(0) for _ in range(TAPS)) for _ in range(channels)), "blank while nothing is held"
    for b, (frames, indexes) in enumerate(blocks):
        w.add(frames, indexes)
        assert w.held() == tuple(range(max(0, b - 2), b + 1)), b
    assert w.added == 5 and w.records() == 6
    want = by_hand(blocks[2:], channels)
    assert w.weights() == want, "the learner over blocks 2, 3 and 4, and over nothing else"
    assert w.weights() != by_hand(blocks[1:], channels) and w.weights() != by_hand(blocks[3:], channels)
    assert w.learner().counts == [6, 6]
    if channels > 1:
        assert len(set(want)) == channels, "every channel's row differs: a learner that mixed channels would be seen"


@pytest.mark.parametrize("profile", PROFILES)
def test_e2l_adaptive_a_reset_drops_every_block_at_its_period_and_at_no_other_block(profile):
    channels = C.PROFILES[profile]["channels"]
    blocks = [block(b, channels) for b in range(10)]
    r = adaptive.Resetting(channels, TAPS, 4, 2)
    held = []
    for frames, indexes in blocks:
        r.add(frames, indexes)
        held.append(r.held())
    assert held == [(0,), (0, 1), (2,), (2, 3), (2, 3, 4), (2, 3, 4, 5), (6,), (6, 7), (6, 7, 8), (6, 7, 8, 9)]
    assert r.resets == [2, 6]
    assert r.weights() == by_hand(blocks[6:], channels)
    # phase 0: no reset before the first block, one before every fourth after it
    z = adaptive.Resetting(channels, TAPS, 4, 0)
    for frames, indexes in blocks:
        z.add(frames, indexes)
    assert z.resets == [4, 8] and z.held() == (8, 9)


def test_e2l_adaptive_stage_e2s_two_learners_hold_the_blocks_its_design_names():
    """The design's window of 8 blocks and its reset before blocks 4 and 12, over sixteen blocks:
    at each block t from 7 to 15 the adaptive holds t - 7 .. t, the reset model 4 .. t up to 11 and 12 .. t after."""
    w, r = adaptive.Window(1, TAPS, 8), adaptive.Resetting(1, TAPS, 8, 4)
    for t in range(16):
        frames, indexes = block(t, 1, trials=1)
        w.add(frames, indexes)
        r.add(frames, indexes)
        assert w.held() == tuple(range(max(0, t - 7), t + 1))
        assert r.held() == tuple(range(12 if t >= 12 else 4 if t >= 4 else 0, t + 1))
    assert r.resets == [4, 12]


@pytest.mark.parametrize("profile", PROFILES)
def test_e2l_adaptive_a_window_wider_than_its_blocks_is_the_trainer_on_all_of_them(profile):
    channels = C.PROFILES[profile]["channels"]
    blocks = [block(b, channels) for b in range(4)]
    w = adaptive.Window(channels, TAPS, 10)
    whole = trainer.MeanDifference(channels, TAPS)
    for frames, indexes in blocks:
        w.add(frames, indexes)
        trainer.train(frames, indexes, TAPS, whole)
    assert w.weights() == whole.weights() == by_hand(blocks, channels)


@pytest.mark.parametrize("profile", PROFILES)
def test_e2l_adaptive_the_two_ways_of_forgetting_are_told_apart(profile):
    """A window of 2 and a reset every 2 blocks hold the same blocks until the first reset and
    different ones after it: a learner that kept the wrong blocks would give other weights."""
    channels = C.PROFILES[profile]["channels"]
    blocks = [block(b, channels) for b in range(3)]
    w, r = adaptive.Window(channels, TAPS, 2), adaptive.Resetting(channels, TAPS, 2, 0)
    for frames, indexes in blocks[:2]:
        w.add(frames, indexes)
        r.add(frames, indexes)
    assert w.held() == r.held() == (0, 1) and w.weights() == r.weights()
    w.add(*blocks[2])
    r.add(*blocks[2])
    assert w.held() == (1, 2) and r.held() == (2,)
    assert w.weights() == by_hand(blocks[1:], channels) != r.weights() == by_hand(blocks[2:], channels)


def test_e2l_adaptive_refusals_by_name_and_nothing_kept_from_a_refused_block():
    for make in (lambda: adaptive.Window(1, TAPS, 0), lambda: adaptive.Window(1, TAPS, 2.0), lambda: adaptive.Window(0, TAPS, 2),
                 lambda: adaptive.Window(1, 0, 2), lambda: adaptive.Resetting(1, TAPS, 0, 0),
                 lambda: adaptive.Resetting(1, TAPS, 4, 4), lambda: adaptive.Resetting(1, TAPS, 4, -1),
                 lambda: adaptive.Resetting(1, TAPS, True, 0)):
        with pytest.raises(LearnRefusal) as e:
            make()
        assert e.value.name == "TRAINER_INPUT"
    w = adaptive.Window(1, TAPS, 3)
    frames, indexes = block(0, 1)
    w.add(frames, indexes)
    for bad, name in (((frames, [2, 4 * 2]), "WINDOW_OUTSIDE_PERIOD"),          # a pulse whose window leaves the block
                      ((frames, [1]), "WINDOW_OUTSIDE_PERIOD"),                  # a signal-free window before the block
                      ((frames, [2, 3]), "TRAINER_INPUT"),                       # two pulses sharing a window
                      ((frames.astype(np.float64), indexes), "TRAINER_INPUT"),   # samples that are not integers
                      ((frames, [2.0]), "TRAINER_INPUT")):
        with pytest.raises(LearnRefusal) as e:
            w.add(*bad)
        assert e.value.name == name, bad
    assert w.held() == (0,) and w.added == 1, "a refused block is not kept, and takes no number"
    r = adaptive.Resetting(1, TAPS, 2, 1)
    r.add(frames, indexes)
    with pytest.raises(LearnRefusal):
        r.add(frames, [1])
    assert r.held() == (0,) and r.resets == [], "a refused block does not reset the learner either"

"""Learners that keep only some of what they were taught: the adaptive and the reset models of stage E2.

The rule is round 2's, unchanged: the difference of two class means (`learn.trainer`). What is new
here is only WHICH labelled windows it is given. A learner of this file is handed its training in
BLOCKS: a stretch of frames, whole, and the truth indexes inside it, as `learn.trainer.train` takes
them. It keeps some of its blocks, and its weights are those of one fresh `MeanDifference` trained on
the blocks it keeps, block by block, through `learn.trainer.train`. Two ways of keeping:

    Window(channels, taps, keep)              the `keep` most recent blocks. A block added when `keep`
                                              are held pushes out the oldest. Stage E2's adaptive model.
    Resetting(channels, taps, period, phase)  every block since its last reset. Before the block
                                              numbered b (the first block added is 0), when b > 0 and
                                              b % period == phase, every block held is dropped: a
                                              reset at a fixed period. Stage E2's reset model.

A reset drops the learner's blocks and nothing else: what a detector holds is the caller's, and this
file never sees a detector, a blob or the model.

Everything `learn.trainer.train` refuses in a block is refused when the block is added, before it is
kept: a window outside the block (WINDOW_OUTSIDE_PERIOD), a signal-free window another pulse reaches
(WINDOW_NOT_FREE), frames or indexes the trainer does not take (TRAINER_INPUT). A `keep`, `period` or
`phase` that is not a whole number in range is TRAINER_INPUT.

This file imports `collections.deque`, `learn.trainer` and `learn.errors` and nothing else: not the
model, the definition or the statistics. Like the trainer it is not told the pulse.

Limits, each by what it concedes:
  - A block's frames are kept as they were handed in, not copied. A caller that changes the array
    afterwards changes what the learner is trained on, and nothing here knows.
  - A block is the unit of forgetting. A window of the most recent N labelled windows, cut inside a
    block, has no form here.
  - The weights are worked again from the kept blocks at every call: exact, and as slow as training
    on every kept window once.
"""
from collections import deque

from learn.errors import LearnRefusal
from learn.trainer import MeanDifference, train


def _whole(value, what, least):
    if type(value) is not int or value < least:
        raise LearnRefusal("TRAINER_INPUT", "%s is %r, not an int of at least %d" % (what, value, least))
    return value


class Kept:
    """What the two learners share: the blocks held, and the learner over them."""

    def __init__(self, channels, taps, keep=None):
        self.channels = _whole(channels, "channels", 1)
        self.taps = _whole(taps, "taps", 1)
        self.kept = deque(maxlen=keep)      # (block number, frames, truth indexes), oldest first
        self.added = 0                      # how many blocks have been added: the number the next one gets

    def _before(self, number):
        """What happens before the block `number` is kept. Nothing, here."""

    def add(self, frames, truth_indexes):
        """Add one training block: its frames (a numpy integer array, frames by channels) and the truth
        indexes inside it, each counted from the block's first frame. Refused as `train` refuses it."""
        indexes = list(truth_indexes)
        train(frames, indexes, self.taps, MeanDifference(self.channels, self.taps))     # every refusal, before it is kept
        self._before(self.added)
        self.kept.append((self.added, frames, indexes))
        self.added += 1

    def held(self):
        """The numbers of the blocks held, oldest first."""
        return tuple(number for number, _frames, _indexes in self.kept)

    def records(self):
        """How many truth records the blocks held carry: each is two labelled windows."""
        return sum(len(indexes) for _number, _frames, indexes in self.kept)

    def learner(self):
        """A fresh `MeanDifference`, trained on every block held, oldest first."""
        learner = MeanDifference(self.channels, self.taps)
        for _number, frames, indexes in self.kept:
            train(frames, indexes, self.taps, learner)
        return learner

    def weights(self):
        """The weights of the learner over the blocks held: blank when no block is held."""
        return self.learner().weights()


class Window(Kept):
    """The adaptive model's learner: the `keep` most recent blocks."""

    def __init__(self, channels, taps, keep):
        super().__init__(channels, taps, _whole(keep, "keep", 1))


class Resetting(Kept):
    """The reset model's learner: every block since its last reset, a reset before each block b > 0
    with b % period == phase."""

    def __init__(self, channels, taps, period, phase):
        super().__init__(channels, taps)
        self.period = _whole(period, "period", 1)
        self.phase = _whole(phase, "phase", 0)
        if self.phase >= self.period:
            raise LearnRefusal("TRAINER_INPUT", "phase %d is not below the period %d" % (self.phase, self.period))
        self.resets = []                    # the numbers of the blocks before which a reset was made

    def _before(self, number):
        if number > 0 and number % self.period == self.phase:
            self.kept.clear()
            self.resets.append(number)

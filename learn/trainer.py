"""The learning rule: the difference of two class means, in exact integers.

WHAT A LABEL IS. A truth record's `index`, as the injector returned it: the
stream index of an injected pulse's first sample. Nothing else is read: not the
pulse's id, not its amplitude, and never anything the detector produced. No
score record is an argument of anything in this file.

WHAT A LABELLED WINDOW IS. With T taps and a truth index j:

    label 1, a signal window        frames j     .. j + T - 1
    label 0, a signal-free window   frames j - T .. j - 1

One of each for each truth record. `labelled_windows` refuses a window that
leaves the frames it was given, and a signal-free window that another record's
pulse touches.

THE RULE. Two sums of windows and two counts, one for each label:

    one update, for a window x with label y:    S[y] <- S[y] + x     n[y] <- n[y] + 1
    the weights, once both counts are at least 1:   w = S[1] / n[1] - S[0] / n[0]

The sums are integers, because samples are. The weights are exact
`fractions.Fraction`s. There is no float here, so the weights do not depend on
the order the windows are added in, and a small case can be worked by hand to
the last digit. BLANK is both sums and both counts at zero: every weight zero.
There is no step size and no stopping test: the caller says how many windows.

WHAT THE LEARNER IS TOLD beyond its labels: the number of taps, and that a
window starts at the truth index. It is not told the pulse. This file imports
the standard library, numpy and this package's own refusal, and nothing of
`model/`, `stats/` or `spec/`.

Limits, each by what it concedes:
  - It does not whiten. A difference of means does not see the noise's
    covariance, so in coloured noise it converges to the pulse, which is then
    not the best filter, and nothing here would say so.
  - It keeps no history: a window added twice counts twice, and nothing here
    knows.
  - The sums are 64-bit integers. A sample must fit 32 signed bits and a label
    may have at most 2^31 windows; past either the trainer refuses by name.
"""
from fractions import Fraction

import numpy as np

from learn.errors import LearnRefusal

SAMPLE_LIMIT = 1 << 31      # a sample's magnitude is below this
COUNT_LIMIT = 1 << 31       # a label has at most this many windows: 2^31 * 2^31 = 2^62 fits a signed 64-bit sum


def _count(value, what, least):
    if type(value) is not int or value < least:
        raise LearnRefusal("TRAINER_INPUT", "%s is %r, not an int of at least %d" % (what, value, least))
    return value


def frame_array(frames, channels):
    """The frames as an int64 array of shape (frames, channels), or a refusal.

    `frames` is a numpy integer array of that shape. A float or a bool array is
    refused, not rounded; so is a sample that does not fit 32 signed bits.
    """
    if not isinstance(frames, np.ndarray) or frames.dtype.kind not in "iu":
        raise LearnRefusal("TRAINER_INPUT", "frames are a numpy array of integers")
    if frames.ndim != 2 or frames.shape[1] != channels:
        raise LearnRefusal("TRAINER_INPUT", "frames of shape %r; %d channel(s) were stated" % (frames.shape, channels))
    if frames.size and (int(frames.min()) <= -SAMPLE_LIMIT or int(frames.max()) >= SAMPLE_LIMIT):
        raise LearnRefusal("TRAINER_INPUT", "a sample does not fit 32 signed bits")
    return frames.astype(np.int64)


def labelled_windows(truth_indexes, taps, period):
    """Where each labelled window starts: a list of (first frame, label), two for each record.

    `period` is how many frames the learner may read: frames 0 .. period - 1.
    The truth indexes are ints, in ascending order. Refused by name:
      an index that is not an int, or indexes out of order or closer than
      `taps`, so that two pulses would share a window         TRAINER_INPUT
      a window with a frame outside 0 .. period - 1            WINDOW_OUTSIDE_PERIOD
      a signal-free window that the record before reaches into WINDOW_NOT_FREE
    """
    taps = _count(taps, "taps", 1)
    period = _count(period, "period", 0)
    out, before = [], None
    for j in truth_indexes:
        if type(j) is not int:
            raise LearnRefusal("TRAINER_INPUT", "a truth index is an int, not %r" % (j,))
        if before is not None and j - before < taps:
            raise LearnRefusal("TRAINER_INPUT", "truth indexes %d and %d: out of order, or closer than %d taps"
                               % (before, j, taps))
        if j - taps < 0 or j + taps > period:
            raise LearnRefusal("WINDOW_OUTSIDE_PERIOD", "the windows of the record at %d are frames %d..%d; the "
                               "learner was given frames 0..%d" % (j, j - taps, j + taps - 1, period - 1))
        if before is not None and j - taps < before + taps:
            raise LearnRefusal("WINDOW_NOT_FREE", "the signal-free window before %d starts at %d, inside the pulse "
                               "at %d..%d" % (j, j - taps, before, before + taps - 1))
        out.append((j, 1))
        out.append((j - taps, 0))
        before = j
    return out


class MeanDifference:
    """The rule's state: two sums and two counts. See the top of this file."""

    def __init__(self, channels, taps):
        self.channels = _count(channels, "channels", 1)
        self.taps = _count(taps, "taps", 1)
        self.sums = np.zeros((2, self.taps, self.channels), dtype=np.int64)     # [label][tap][channel]
        self.counts = [0, 0]

    def start(self):
        """The starting weights, which are blank: one row of zeros for each channel."""
        return tuple(tuple(Fraction(0) for _ in range(self.taps)) for _ in range(self.channels))

    def update(self, window, label):
        """One update: add a labelled window to its label's sum. `window` is (taps, channels) integers."""
        if type(label) is not int or label not in (0, 1):
            raise LearnRefusal("TRAINER_INPUT", "a label is the int 0 or 1, not %r" % (label,))
        x = frame_array(window, self.channels)
        if x.shape[0] != self.taps:
            raise LearnRefusal("TRAINER_INPUT", "a window of %d frames; the filter has %d taps" % (x.shape[0], self.taps))
        if self.counts[label] >= COUNT_LIMIT:
            raise LearnRefusal("TRAINER_COUNT", "label %d already has %d windows" % (label, self.counts[label]))
        self.sums[label] += x
        self.counts[label] += 1

    def weights(self):
        """The weights: a tuple of one row for each channel, each a tuple of `taps` Fractions.

        Row c, entry k is the weight for channel c at tap k, tap 0 meeting the
        window's first frame: the order `model.weights.pack` takes a row in.
        Until each label has a window, the weights are the starting ones.
        """
        n0, n1 = self.counts
        if n0 == 0 or n1 == 0:
            return self.start()
        s0, s1 = self.sums[0].tolist(), self.sums[1].tolist()
        return tuple(tuple(Fraction(s1[k][c], n1) - Fraction(s0[k][c], n0) for k in range(self.taps))
                     for c in range(self.channels))


def train(frames, truth_indexes, taps, learner=None):
    """Feed a learner every labelled window of a training period, and return it.

    `frames` is the period, a numpy integer array (frames, channels): all the
    learner may read. `truth_indexes` are the truth records' indexes inside
    it. `learner` is a `MeanDifference` (a blank one is made when it is left
    out). Everything `labelled_windows` and `update` refuse is refused here,
    before any window is added.
    """
    if not isinstance(frames, np.ndarray) or frames.ndim != 2:
        raise LearnRefusal("TRAINER_INPUT", "frames are a numpy array of shape (frames, channels)")
    if learner is None:
        learner = MeanDifference(frames.shape[1], taps)
    x = frame_array(frames, learner.channels)
    if taps != learner.taps:
        raise LearnRefusal("TRAINER_INPUT", "%r taps asked of a learner with %d" % (taps, learner.taps))
    starts = labelled_windows(list(truth_indexes), taps, x.shape[0])
    for label in (0, 1):
        if learner.counts[label] + len(starts) // 2 > COUNT_LIMIT:
            raise LearnRefusal("TRAINER_COUNT", "label %d would have more than %d windows" % (label, COUNT_LIMIT))
    for first, label in starts:
        learner.update(x[first:first + taps], label)
    return learner

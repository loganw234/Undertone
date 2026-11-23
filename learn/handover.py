"""The hand-over: a learner's weights to a blob, and the blob into a running detector.

What the detector is handed is judged exactly, so nothing here invents a rule.
The weights are quantised by the definition's rule AS THE MODEL IMPLEMENTS IT
(`model.weights.quantise`: peak to the largest coefficient, half to even), every
row of the one filter together as one set, and packed by `model.weights.pack` in
the matched-filter configuration: one filter reading every channel of the
profile, the rectifier passing, a pool of 1, no shift, a head weight of 1. The
score is then the filter's sum.

Everything the model refuses is refused here under the model's own name, by the
model's own code: an all-zero set has no peak (QUANTISE_INPUT), a float is not
an exact value (QUANTISE_INPUT), a blob of another shape cannot be swapped in
(SWAP_SHAPE), nor one committed in the past (SWAP_INDEX) or while a swap is
pending (SWAP_PENDING). This package's own refusal is for weights that are not
one row of equal length for each channel (CANDIDATE_SHAPE).

From the model this file takes three names and no more: `weights.quantise`,
`weights.pack` and `weights.unpack`. A core is handed in; it is not imported.

Limits, each by what it concedes:
  - The blank blob cannot come from the quantising rule, which refuses a set of
    zeros. It is packed directly. So "blank" is a blob of this file's making,
    and a learner that returns its blank weights cannot be handed over at all.
  - One filter, every channel read. A learner that wanted a filter on some
    channels only, or several filters, has no hand-over here.
"""
from spec import constants as C
from model import weights

from learn.errors import LearnRefusal

PASS = C.RECTIFIERS["pass"]


def _channels(profile):
    """The profile's channel count; an undeclared profile is refused by the model's own pack."""
    if type(profile) is not str or profile not in C.PROFILES:
        weights.pack(profile, [{0: (0,)}], (1,), PASS, 1, 0)      # refuses: PROFILE_UNKNOWN
    return C.PROFILES[profile]["channels"]


def blank_blob(profile, taps):
    """The blob a detector holds before anything is learned: every coefficient zero."""
    channels = _channels(profile)
    if type(taps) is not int or taps < 1:
        raise LearnRefusal("CANDIDATE_SHAPE", "taps is %r, not an int of at least 1" % (taps,))
    return weights.pack(profile, [{c: (0,) * taps for c in range(channels)}], (1,), PASS, 1, 0)


def candidate_blob(profile, rows):
    """The blob for a learner's weights, or a refusal by name.

    `rows` is one row for each channel of the profile, in channel order, each
    of the same number of ints or Fractions, tap 0 first (what
    `learn.trainer.MeanDifference.weights` returns).
    """
    channels = _channels(profile)
    if not isinstance(rows, (list, tuple)) or len(rows) != channels:
        raise LearnRefusal("CANDIDATE_SHAPE", "one row for each of the profile's %d channel(s)" % channels)
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) == 0 or len(row) != len(rows[0]):
            raise LearnRefusal("CANDIDATE_SHAPE", "every row is the same number of weights, at least one")
    taps = len(rows[0])
    whole = weights.quantise([v for row in rows for v in row])
    return weights.pack(profile, [{c: whole[c * taps:(c + 1) * taps] for c in range(channels)}], (1,), PASS, 1, 0)


def coefficients(blob):
    """The integer rows of a blob of this file's shape: a tuple of one tuple for each channel."""
    config = weights.unpack(blob)
    if len(config["filters"]) != 1:
        raise LearnRefusal("CANDIDATE_SHAPE", "a blob of %d filters, not one" % len(config["filters"]))
    rows = config["filters"][0]
    return tuple(rows[c] for c in sorted(rows))


def hand_over(core, blob, at):
    """Write the blob to the core's shadow and commit the swap at output index `at`.

    Every output before `at` then carries the old epoch and uses the old
    weights; every output from `at` on carries the new epoch and uses the new
    ones (`model.weights.Store`). Returns `at`.
    """
    core.write_shadow(blob)
    core.commit(at)
    return at

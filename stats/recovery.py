"""Thresholds and the injection-recovery count.

WHAT COUNTS AS RECOVERED. A truth index j is the stream index of an injected
pulse's FIRST sample. `lag` is how many samples later the detector's score for
that pulse is read: T - 1 for the causal filter of `stats.matched`.

  - recovered AT THE INJECTED INDEX:  scores[j + lag] > threshold
  - recovered WITHIN A WINDOW:        the largest of
                                      scores[j + lag - window .. j + lag + window]
                                      is > threshold

A crossing is STRICTLY greater: a score equal to the threshold is not one.

Only the first has an analytic authority (D8 is a test at a known arrival
time). The window count is a different test with more chances to cross: its
found-rate is higher at the same threshold, D8 does not predict it, and it is
compared between implementations on the same stream, not against the formula.

WHY INJECTIONS MUST BE SPACED. The binomial tolerance of `stats.tolerance`
treats each injection as an independent trial. Two injections whose examined
scores share a noise sample are not independent, and one whose pulse reaches
into another's scores is not the stated pulse. So a schedule closer than
`minimum_spacing` is refused, not counted.

A THRESHOLD FROM NOISE is itself a measurement. `threshold_from_scores` takes m
signal-free scores and returns the (k+1)-th largest, k = floor(pfa * m), so
that k of them cross. The false-alarm probability of that threshold is not pfa:
it varies from one noise sample to the next, with mean (k+1)/(m+1) and standard
deviation near sqrt(pfa (1 - pfa) / m) WHEN THE m SCORES ARE INDEPENDENT, which
is why `signal_free_indexes` takes them at least one filter length apart.
`stats.tolerance` adds that spread to an efficiency's tolerance; leaving it out
makes the tolerance too narrow.

Limits. Independence of the m scores is for WHITE noise only. Tied scores at
the threshold make fewer than k cross (`above` reports how many); the tolerance
assumes there are none. A threshold needs k >= 100 here: below that the
first-order spread the tolerance uses is not good enough.

Nothing here imports from `model/`.
"""
import math
from fractions import Fraction

import numpy as np

from stats.errors import StatRefusal
from stats.theory import _number, _probability, _real_array, _sigma, q_inv

MIN_CROSSINGS = 100


def _count(value, what, least=0):
    if type(value) is not int or value < least:
        raise StatRefusal("SHAPE", "%s is %r, not an int of at least %d" % (what, value, least))
    return value


def _score_array(scores):
    a = np.asarray(scores)
    if a.ndim != 1 or a.dtype.kind not in "iuf":
        raise StatRefusal("SHAPE", "scores must be a flat array of numbers")
    a = a.astype(np.float64, copy=False)
    if not np.isfinite(a).all():
        raise StatRefusal("NOT_FINITE", "a score is a NaN or an infinity")
    return a


def _index_array(truth_indexes):
    a = np.asarray(truth_indexes)
    if a.size == 0:
        return np.zeros(0, dtype=np.int64)
    if a.ndim != 1 or a.dtype.kind not in "iu":
        raise StatRefusal("SHAPE", "truth indexes must be a flat sequence of ints")
    return a.astype(np.int64)


def threshold_known_sigma(pfa, sigma, coeffs):
    """D8's own threshold: Q^-1(pfa) * sigma * norm(coeffs), for white noise of known sigma."""
    h = _real_array(coeffs, "coeffs")
    return q_inv(pfa) * _sigma(sigma) * math.sqrt(float((h * h).sum()))


def signal_free_indexes(n_scores, taps, truth_indexes, pulse_len, stride=None):
    """Score indexes that saw no injected sample, at least one filter length apart.

    Score i used samples i - taps + 1 .. i. It is left out when i < taps - 1
    (it saw fewer than `taps` samples) and when those samples touch any
    injected pulse, j .. j + pulse_len - 1. The rest are taken on the grid
    taps - 1, taps - 1 + stride, ...; `stride` defaults to `taps`, and a
    shorter one is refused, because neighbouring scores share samples.
    """
    n_scores = _count(n_scores, "n_scores")
    taps = _count(taps, "taps", 1)
    pulse_len = _count(pulse_len, "pulse_len", 1)
    stride = taps if stride is None else _count(stride, "stride", 1)
    if stride < taps:
        raise StatRefusal("STRIDE_SHORT", "stride %d is shorter than the filter's %d taps" % (stride, taps))
    truth = _index_array(truth_indexes)
    if truth.size and (truth.min() < 0 or truth.max() >= n_scores):
        raise StatRefusal("INDEX_RANGE", "a truth index outside 0..%d" % (n_scores - 1))
    # Score i is touched by the pulse at j when j <= i <= j + pulse_len + taps - 2.
    steps = np.zeros(n_scores + 1, dtype=np.int64)
    np.add.at(steps, truth, 1)
    np.add.at(steps, np.minimum(truth + pulse_len + taps - 1, n_scores), -1)
    touched = np.cumsum(steps[:n_scores]) > 0
    grid = np.arange(taps - 1, n_scores, stride)
    return grid[~touched[grid]]


def signal_free_scores(scores, taps, truth_indexes, pulse_len, stride=None):
    """The scores at `signal_free_indexes`."""
    s = _score_array(scores)
    return s[signal_free_indexes(len(s), taps, truth_indexes, pulse_len, stride)]


def threshold_from_scores(noise_scores, pfa):
    """A threshold for a target false-alarm probability, from m signal-free scores.

    k = floor(pfa * m), and the floor is taken of the EXACT value of the float
    `pfa`, not of the decimal it was written as. The float written 0.29 is a
    hair below 0.29, so over 10,000 scores k is 2,899, one fewer than the
    decimal reads (0.57 and 0.58 are others). So k / m never exceeds pfa; the
    threshold can be one score higher than a reader of the decimal expects;
    and `pfa_effective` below is worked from the k actually used.

    Returns a dict:
      threshold      the (k+1)-th largest score, k = floor(pfa * m)
      m, k           as above
      above          how many of the m are strictly above it: k, or fewer if tied
      pfa_effective  (k + 1) / (m + 1): the mean false-alarm probability of
                     this threshold over noise samples, for independent
                     continuous scores. Hand THIS to the tolerance, with m.
    """
    s = _score_array(noise_scores)
    pfa = _probability(pfa, "pfa")
    m = len(s)
    k = int(Fraction(pfa) * m)
    if k < MIN_CROSSINGS:
        raise StatRefusal("TOO_FEW_NOISE_SCORES",
                          "%d scores at pfa %r give %d crossing(s); %d are needed" % (m, pfa, k, MIN_CROSSINGS))
    threshold = float(np.sort(s)[m - k - 1])
    return {"threshold": threshold, "m": m, "k": k, "above": int((s > threshold).sum()),
            "pfa_effective": (k + 1) / (m + 1)}


def minimum_spacing(taps, pulse_len, lag, window):
    """The least distance between truth indexes at which injections are separate trials.

    Injection j's examined scores use samples j + lag - window - taps + 1 ..
    j + lag + window; its pulse is at j .. j + pulse_len - 1. Two injections S
    apart are separate when those sample ranges do not meet and neither pulse
    reaches the other's range. For lag = taps - 1 and pulse_len <= taps that is
    taps + 2 * window.
    """
    return max(taps + 2 * window, lag + window + 1, pulse_len + taps + window - lag - 1)


def recovery_count(scores, truth_indexes, threshold, lag, taps, pulse_len, window=0):
    """Count the injections recovered, at the injected index and within a window.

    Returns a dict: n, at_index, in_window (counts), hits_at_index,
    hits_in_window (one bool per injection, in the order given) and
    minimum_spacing. Refused by name: no injections; an injection whose scores
    lie outside the stream; injections closer than `minimum_spacing`.
    """
    s = _score_array(scores)
    threshold = _number(threshold, "threshold")
    lag = _count(lag, "lag")
    window = _count(window, "window")
    taps = _count(taps, "taps", 1)
    pulse_len = _count(pulse_len, "pulse_len", 1)
    truth = _index_array(truth_indexes)
    if truth.size == 0:
        raise StatRefusal("NO_INJECTIONS", "a count over zero injections says nothing")
    centre = truth + lag
    if truth.min() < 0 or (centre - window).min() < 0 or (centre + window).max() >= len(s):
        raise StatRefusal("INDEX_RANGE", "an injection's scores lie outside 0..%d" % (len(s) - 1))
    spacing = minimum_spacing(taps, pulse_len, lag, window)
    if truth.size > 1:
        gaps = np.diff(np.sort(truth))
        if gaps.min() < spacing:
            raise StatRefusal("INJECTIONS_OVERLAP",
                              "two injections %d apart; separate trials need %d" % (int(gaps.min()), spacing))
    at_index = s[centre] > threshold
    best = s[centre].copy()
    for offset in range(1, window + 1):
        np.maximum(best, s[centre - offset], out=best)
        np.maximum(best, s[centre + offset], out=best)
    in_window = best > threshold
    return {"n": int(truth.size), "at_index": int(at_index.sum()), "in_window": int(in_window.sum()),
            "hits_at_index": at_index, "hits_in_window": in_window, "minimum_spacing": spacing}


def paired_cost(hits_a, hits_b):
    """What detector b loses against detector a on the SAME injections.

    Both saw one stream, so most injections are found by both or by neither,
    and those say nothing about the difference. Only the injections found by
    exactly one do:

        cost = (a_only - b_only) / n
        se   = sqrt(a_only + b_only - (a_only - b_only)^2 / n) / n

    That standard error is far below the binomial error of either efficiency
    when the detectors mostly agree. It is the right spread for a difference
    measured this way, and the wrong one for either efficiency alone.
    """
    a, b = np.asarray(hits_a), np.asarray(hits_b)
    if a.dtype.kind != "b" or b.dtype.kind != "b" or a.ndim != 1 or a.shape != b.shape:
        raise StatRefusal("SHAPE", "two flat bool arrays of one length are needed")
    n = int(a.size)
    if n == 0:
        raise StatRefusal("NO_INJECTIONS", "a comparison over zero injections says nothing")
    a_only, b_only = int((a & ~b).sum()), int((~a & b).sum())
    diff = a_only - b_only
    return {"n": n, "found_a": int(a.sum()), "found_b": int(b.sum()), "a_only": a_only, "b_only": b_only,
            "cost": diff / n, "se": math.sqrt(a_only + b_only - diff * diff / n) / n}

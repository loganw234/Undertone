"""The foreign matched filter: floating point, numpy, and no code from `model/`.

THE CONVENTIONS (the lead's, 2026-11-23; they are the model's too):

  - A stream is frames; a frame holds one integer sample per channel; a frame's
    index is its position, from 0.
  - The filter is causal and its coefficients are written OLDEST SAMPLE FIRST:

        score[i] = sum over channels c, taps k of  coeff[c][k] * x[i - (T-1) + k][c]

    with samples before the stream's start taken as zero. A score's index is
    the index of the newest sample it used.
  - So the matched filter's coefficients are the pulse IN ORDER, and a pulse
    whose first sample is at index j is wholly under the filter at score index
    j + T - 1.
  - More than one channel: one coefficient row per channel, summed. A filter
    that reads one channel has zero rows elsewhere. (Provisional on the model's
    side until its detector's design is in; this general form covers it.)

Written as a convolution, y[i] = sum c[k] x[i-k], the same filter has its
coefficients reversed. That form appears here once, inside `matched_scores`,
because numpy's routine is a convolution; nothing outside sees it.

WHEN THE FLOAT IS EXACT. With integer coefficients, every product and every
partial sum is an integer. A float64 holds every integer up to 2^53, so when
sum|coeff| * (largest sample magnitude) is below 2^53 the score is the integer
sum itself, whatever order numpy adds in. `scores_are_exact` says whether that
holds. With real coefficients the score is an ordinary rounded float.

Limits. The first T - 1 scores see fewer than T samples: they are returned,
because the model emits one score per sample, but they are not full-window
scores and `stats.recovery.signal_free_indexes` leaves them out. A stream given
as an iterable of tuples is checked frame by frame in Python and is slow beyond
a few hundred thousand frames; an integer numpy array is the fast path.

Nothing here imports from `model/`.
"""
import numpy as np

from spec import constants as C
from stats.errors import StatRefusal

_EXACT_INT = 2 ** 53


def profile_facts(profile_name):
    """(channels, lowest sample, highest sample) for a declared profile, or a refusal."""
    if type(profile_name) is not str or profile_name not in C.PROFILES:
        raise StatRefusal("PROFILE_UNKNOWN", repr(profile_name))
    p = C.PROFILES[profile_name]
    return p["channels"], p["sample_min"], p["sample_max"]


def frames_to_array(stream, profile_name):
    """The stream as an integer array of shape (frames, channels), every sample checked.

    `stream` is an iterable of frames (each a tuple of ints, one per channel)
    or a numpy integer array of that shape. A float or a bool is not a sample,
    in either form: it is refused, not rounded.
    """
    channels, low, high = profile_facts(profile_name)
    if isinstance(stream, np.ndarray):
        if stream.dtype.kind not in "iu":
            raise StatRefusal("SAMPLE_RANGE", "samples of dtype %s are not integers" % stream.dtype)
        if stream.ndim != 2 or stream.shape[1] != channels:
            raise StatRefusal("CHANNELS", "array of shape %r, profile has %d channel(s)" % (stream.shape, channels))
        if stream.size:
            smallest, largest = int(stream.min()), int(stream.max())
            if smallest < low or largest > high:
                raise StatRefusal("SAMPLE_RANGE", "samples span %d..%d, outside %d..%d" % (smallest, largest, low, high))
        return stream
    frames = []
    for frame in stream:
        if type(frame) is not tuple or len(frame) != channels:
            raise StatRefusal("CHANNELS", "frame %r, profile has %d channel(s)" % (frame, channels))
        for v in frame:
            if type(v) is not int or not low <= v <= high:
                raise StatRefusal("SAMPLE_RANGE", "sample %r outside %d..%d" % (v, low, high))
        frames.append(frame)
    return np.array(frames, dtype=np.int64).reshape(len(frames), channels)


def coeff_array(coeffs, profile_name):
    """The coefficient set as a float64 array (channels, taps), or a refusal.

    One row per channel. A flat set is accepted only for a one-channel profile.
    """
    channels = profile_facts(profile_name)[0]
    try:
        a = np.asarray(coeffs)
    except ValueError:
        raise StatRefusal("SHAPE", "coefficient rows of unequal length")
    if a.dtype.kind not in "iuf":
        raise StatRefusal("VALUE_TYPE", "coefficients of dtype %s" % a.dtype)
    if a.dtype.kind in "iu" and a.size and max(abs(int(a.min())), abs(int(a.max()))) > _EXACT_INT:
        raise StatRefusal("INEXACT_INPUT", "an integer coefficient beyond 2^53")
    if a.ndim == 1 and channels == 1:
        a = a.reshape(1, a.shape[0])
    if a.ndim != 2:
        raise StatRefusal("CHANNELS" if a.ndim == 1 else "SHAPE",
                          "coefficients of shape %r, profile has %d channel(s)" % (a.shape, channels))
    if a.shape[0] != channels:
        raise StatRefusal("CHANNELS", "%d coefficient row(s), profile has %d channel(s)" % (a.shape[0], channels))
    if not 1 <= a.shape[1] <= C.MAX_TAPS:
        raise StatRefusal("SHAPE_TAPS", "%d taps, outside 1..%d" % (a.shape[1], C.MAX_TAPS))
    a = a.astype(np.float64)
    if not np.isfinite(a).all():
        raise StatRefusal("NOT_FINITE", "a coefficient is a NaN or an infinity")
    return a


def template(pulse, gains):
    """The coefficient rows of a pulse laid on several channels: row c is gains[c] * pulse.

    Integers in, integers out, so the same array can be added to a stream.
    """
    return np.outer(np.asarray(gains), np.asarray(pulse))


def scores_are_exact(profile_name, coeffs):
    """True when every score of this set, on any stream of this profile, is an exact integer.

    That needs integer coefficients and sum|coeff| * (largest sample magnitude)
    below 2^53. When it holds, a difference of any size between these scores
    and another implementation's integer scores is an error in one of the two.
    """
    low, high = profile_facts(profile_name)[1:]
    h = coeff_array(coeffs, profile_name)
    if not (h == np.rint(h)).all():
        return False
    total = sum(abs(int(v)) for v in h.ravel().tolist())
    return total * max(abs(low), abs(high)) < _EXACT_INT


def matched_scores(stream, profile_name, coeffs):
    """One score per frame, a float64 array, by the convention at the top of this file."""
    x = frames_to_array(stream, profile_name)
    h = coeff_array(coeffs, profile_name)
    frames = x.shape[0]
    if frames == 0:
        return np.zeros(0, dtype=np.float64)
    out = None
    for c in range(h.shape[0]):
        # numpy's routine is the convolution form, so the row goes in reversed.
        part = np.convolve(x[:, c].astype(np.float64), h[c, ::-1])[:frames]
        out = part if out is None else out + part
    return np.ascontiguousarray(out)

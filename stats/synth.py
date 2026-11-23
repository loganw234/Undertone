"""TEST STREAMS ONLY. This is not the instrument's noise generator or its injector.

The instrument's source and injector are the reference model's, in `model/`,
integer arithmetic and bit-exact. What is here exists so that the statistics
can be exercised without `model/`: numpy's PCG64 generator, a Gaussian in
floating point rounded half-to-even to integers, and integer pulses added at
given indexes. A result obtained on these streams is evidence about the code in
`stats/`. It is not evidence about the instrument's generator, its tails or its
injector.

Nothing saturates: a sample that would leave the profile's range is refused,
not clipped. Every draw is from the seed given, so a stream can be made again.

Limits. A rounded Gaussian of standard deviation sigma has variance near
sigma^2 + 1/12, not sigma^2; at sigma in the hundreds the difference in
standard deviation is below one part in a million, and at sigma near 1 it is
not small. numpy does not promise that a seed gives the same stream in every
numpy version.

Nothing here imports from `model/`.
"""
import numpy as np

from stats.errors import StatRefusal
from stats.matched import profile_facts
from stats.theory import _sigma


def _in_range(a, low, high, what):
    if a.size and (a.min() < low or a.max() > high):
        raise StatRefusal("SAMPLE_RANGE", "%s spans %d..%d, outside %d..%d"
                          % (what, int(a.min()), int(a.max()), low, high))


def noise(profile_name, frames, sigma, seed):
    """Rounded white Gaussian noise: an int32 array (frames, channels), each channel its own draw."""
    channels, low, high = profile_facts(profile_name)
    if type(frames) is not int or frames < 0:
        raise StatRefusal("SHAPE", "frames is %r" % (frames,))
    if type(seed) is not int or seed < 0:
        raise StatRefusal("VALUE_TYPE", "seed is %r, not a non-negative int" % (seed,))
    sigma = _sigma(sigma)
    rng = np.random.Generator(np.random.PCG64(seed))
    out = np.empty((frames, channels), dtype=np.int32)
    step = 1 << 20
    for start in range(0, frames, step):
        block = np.rint(rng.standard_normal((min(step, frames - start), channels)) * sigma)
        _in_range(block, low, high, "the noise")
        out[start:start + len(block)] = block
    return out


def schedule(count, spacing, first=0):
    """`count` truth indexes, `spacing` apart, the first at `first`."""
    for value, what, least in ((count, "count", 1), (spacing, "spacing", 1), (first, "first", 0)):
        if type(value) is not int or value < least:
            raise StatRefusal("SHAPE", "%s is %r" % (what, value))
    return first + spacing * np.arange(count, dtype=np.int64)


def inject(stream, profile_name, pulse_rows, truth_indexes):
    """A new stream with the integer pulse added at each truth index.

    `pulse_rows` is (channels, length) integers: row c is added to channel c,
    its first sample at the truth index. The stream given is not changed.
    """
    channels, low, high = profile_facts(profile_name)
    if not isinstance(stream, np.ndarray) or stream.dtype.kind != "i" or stream.ndim != 2 or stream.shape[1] != channels:
        raise StatRefusal("CHANNELS", "the stream must be a signed integer array (frames, %d)" % channels)
    pulse = np.asarray(pulse_rows)
    if pulse.dtype.kind not in "iu":
        raise StatRefusal("SAMPLE_RANGE", "a pulse of dtype %s is not integers" % pulse.dtype)
    if pulse.ndim == 1 and channels == 1:
        pulse = pulse.reshape(1, -1)
    if pulse.ndim != 2 or pulse.shape[0] != channels or pulse.shape[1] < 1:
        raise StatRefusal("CHANNELS", "a pulse of shape %r, profile has %d channel(s)" % (pulse.shape, channels))
    truth = np.asarray(truth_indexes)
    if truth.ndim != 1 or truth.dtype.kind not in "iu":
        raise StatRefusal("SHAPE", "truth indexes must be a flat sequence of ints")
    if truth.size and (truth.min() < 0 or truth.max() + pulse.shape[1] > stream.shape[0]):
        raise StatRefusal("INDEX_RANGE", "a pulse would run outside the stream")
    if len(np.unique(truth)) != len(truth):
        raise StatRefusal("INJECTIONS_OVERLAP", "two injections at one index")
    out = stream.astype(np.int64)
    for c in range(channels):
        for k in range(pulse.shape[1]):
            # The indexes truth + k are all different, so this adds once at each.
            out[truth + k, c] += int(pulse[c, k])
    _in_range(out, low, high, "the stream with its pulses")
    return out.astype(stream.dtype)

"""The analytic matched-filter result: D0 row D8, and what follows from it.

For a pulse s known in shape and amplitude, in white Gaussian noise of known
standard deviation sigma, tested at a known arrival time:

    Pd = Q(Q^-1(Pfa) - d),    d = norm(s) / sigma

The source's own statement is in docs/sources/D8.md. This file is the formula.

Two things here are NOT from that source and are derived in docs/model/stat.md:
`deflection` for a filter that is not the pulse, and `pd_rectified`.

Limits. Everything here assumes real-valued Gaussian noise, white, of one
standard deviation on every channel, and a test at one known index. None of it
describes a detector sliding over a stream, coloured noise, or any
configuration but the matched filter (D0, the four limits under row D8).

Nothing here imports from `model/`.
"""
import math

import numpy as np

from stats.errors import StatRefusal

_SQRT2 = math.sqrt(2.0)


def _number(x, what):
    """A finite float, or a refusal. A bool is not a number here."""
    if isinstance(x, (bool, np.bool_)) or not isinstance(x, (int, float, np.integer, np.floating)):
        raise StatRefusal("VALUE_TYPE", "%s is %r" % (what, x))
    x = float(x)
    if not math.isfinite(x):
        raise StatRefusal("NOT_FINITE", "%s is %r" % (what, x))
    return x


def _probability(p, what="a probability"):
    p = _number(p, what)
    if not 0.0 < p < 1.0:
        raise StatRefusal("PROBABILITY_RANGE", "%s is %r, not inside (0, 1)" % (what, p))
    return p


def _sigma(sigma):
    sigma = _number(sigma, "sigma")
    if not sigma > 0.0:
        raise StatRefusal("SIGMA", "sigma is %r" % (sigma,))
    return sigma


def q(x):
    """The probability that a standard normal value exceeds x."""
    return 0.5 * math.erfc(_number(x, "x") / _SQRT2)


def _q_inv_upper(p):
    """x >= 0 with q(x) = p, for 0 < p <= 0.5. Bisection: slow and obvious.

    q falls from 0.5 at 0 to exactly 0.0 at 40 (it underflows near 38.5), so
    the answer is bracketed. After about 60 halvings the bracket is two
    neighbouring floats; the rest of the 200 change nothing.
    """
    lo, hi = 0.0, 40.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if q(mid) > p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def q_inv(p):
    """The x with q(x) = p, for 0 < p < 1. Anything else is refused.

    Above one half the answer is minus the answer for 1 - p, and 1 - p is exact
    in floating point there.
    """
    p = _probability(p, "p")
    if p == 0.5:
        return 0.0
    if p > 0.5:
        return -_q_inv_upper(1.0 - p)
    return _q_inv_upper(p)


def _real_array(values, what):
    try:
        a = np.asarray(values)
    except ValueError:
        raise StatRefusal("SHAPE", "%s is ragged" % what)
    if a.dtype.kind not in "iuf":
        raise StatRefusal("VALUE_TYPE", "%s has dtype %s" % (what, a.dtype))
    a = a.astype(np.float64)
    if a.size == 0:
        raise StatRefusal("SHAPE", "%s is empty" % what)
    if not np.isfinite(a).all():
        raise StatRefusal("NOT_FINITE", "%s holds a NaN or an infinity" % what)
    return a


def deflection(coeffs, injected, sigma):
    """How far a filter's output moves when the pulse is there, in units of its noise.

        (h . s) / (sigma * norm(h))

    h is the coefficient set, s the samples actually added to the stream, both
    of one shape (taps, or channels by taps). With h equal to s this is D8's
    d = norm(s) / sigma. It can be negative: a filter that points away from the
    pulse finds it less often than chance.
    """
    h = _real_array(coeffs, "coeffs")
    s = _real_array(injected, "injected")
    if h.shape != s.shape:
        raise StatRefusal("SHAPE", "coeffs %r and injected %r differ in shape" % (h.shape, s.shape))
    sigma = _sigma(sigma)
    norm = math.sqrt(float((h * h).sum()))
    if norm == 0.0:
        raise StatRefusal("ZERO_SET", "every coefficient is zero")
    return float((h * s).sum()) / (sigma * norm)


def pd_matched(pfa, d):
    """D8: the detection probability at false-alarm probability pfa and deflection d."""
    return q(q_inv(pfa) - _number(d, "d"))


def pd_rectified(pfa, d):
    """The same filter with an absolute value after it, at the same false-alarm probability.

    The threshold t has to pass pfa / 2 in each tail, and a pulse is then found
    in either tail: Q(t - d) + Q(t + d), t = Q^-1(pfa / 2). It is below
    `pd_matched` for every d > 0. This is D0 row D11's detector.
    """
    pfa = _probability(pfa, "pfa")
    d = _number(d, "d")
    t = q_inv(pfa / 2.0)
    return q(t - d) + q(t + d)

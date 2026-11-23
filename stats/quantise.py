"""The quantising rule of `spec/undertone.toml`, written a second time, in floating point.

    scale    = "peak_to_max":   every value of the set is multiplied so that the
                                 set's largest magnitude maps to 2^(bits-1) - 1
    rounding = "half_to_even":  to the nearest integer, a tie to the even one

`model/` has its own implementation. The two share the rule and no code.

"The set" is everything passed in one call. For a bank of several filters the
definition does not say whether the set is one filter or the bank; in the
matched-filter configuration there is one filter and the question does not
arise.

THE HALF-WAY CASES. A float cannot be trusted near a tie: (c / m) * qmax is two
rounded operations, and a true value a hair above n + 1/2 can arrive as exactly
n + 1/2 and round the wrong way. So a value that arrives within `GUARD` of a
half-way point is not rounded from the float at all. It is worked again exactly,
as a ratio of integers (`fractions.Fraction` holds a float's exact value), and
rounded half to even there. Outside the guard the float and the true value lie
between the same two half-way points, because they differ by at most 2^-23 (two
relative errors of 2^-53 on a magnitude below 2^29) and the guard is 2^-12; so
ordinary rounding of the float is the exact rule's answer. Either way the
result is the exact rule applied to the numbers passed in.

Limits. The numbers passed in are the truth: a coefficient that was already
rounded when it became a float is quantised as the float it is. `bits` is 2 to
30; the error bound above is for that range. An integer beyond 2^53 is refused,
not rounded into a float.

Nothing here imports from `model/`.
"""
import math
from fractions import Fraction

import numpy as np

from spec import constants as C
from stats.errors import StatRefusal

GUARD = 2.0 ** -12
_HALF = Fraction(1, 2)
_EXACT_INT = 2 ** 53


def _scalar(v):
    """The value as a Python int or float, exactly, or a refusal."""
    if isinstance(v, (bool, np.bool_)):
        raise StatRefusal("VALUE_TYPE", "a bool is not a coefficient: %r" % (v,))
    if isinstance(v, (int, np.integer)):
        v = int(v)
        if abs(v) > _EXACT_INT:
            raise StatRefusal("INEXACT_INPUT", "%d is beyond 2^53: a float cannot hold it" % v)
        return v
    if isinstance(v, (float, np.floating)):
        v = float(v)
        if not math.isfinite(v):
            raise StatRefusal("NOT_FINITE", "a coefficient is %r" % (v,))
        return v
    raise StatRefusal("VALUE_TYPE", "not a number: %r" % (v,))


def _flatten(coeffs):
    """(the values in order as Python numbers, the shape). One or two dimensions."""
    if isinstance(coeffs, np.ndarray):
        if coeffs.ndim not in (1, 2):
            raise StatRefusal("SHAPE", "an array of %d dimensions" % coeffs.ndim)
        return [_scalar(v) for v in coeffs.ravel().tolist()], coeffs.shape
    if not isinstance(coeffs, (list, tuple)):
        raise StatRefusal("SHAPE", "not a sequence: %r" % (coeffs,))
    rows = [r for r in coeffs if isinstance(r, (list, tuple, np.ndarray))]
    if not rows:
        return [_scalar(v) for v in coeffs], (len(coeffs),)
    if len(rows) != len(coeffs):
        raise StatRefusal("SHAPE", "rows and bare values mixed")
    width = len(rows[0])
    values = []
    for r in rows:
        if len(r) != width:
            raise StatRefusal("SHAPE", "rows of %d and %d values" % (width, len(r)))
        for v in (r.tolist() if isinstance(r, np.ndarray) else r):
            if isinstance(v, (list, tuple, np.ndarray)):
                raise StatRefusal("SHAPE", "more than two dimensions")
            values.append(_scalar(v))
    return values, (len(rows), width)


def exact_half_to_even(value):
    """A `Fraction` to the nearest integer, a tie to the even one. Exact."""
    floor = value.numerator // value.denominator
    rest = value - floor
    if rest > _HALF:
        return floor + 1
    if rest < _HALF:
        return floor
    return floor if floor % 2 == 0 else floor + 1


def quantise(coeffs, bits=C.COEFF_BITS):
    """The integer coefficient set for a real one. An int64 array of the same shape.

    `coeffs` is a sequence of numbers, a sequence of equal rows, or a numpy
    array of one or two dimensions. The largest magnitude maps to
    2^(bits-1) - 1 exactly, and its sign is kept.
    """
    if type(bits) is not int or not 2 <= bits <= 30:
        raise StatRefusal("COEFF_BITS_RANGE", "bits is %r, not an int from 2 to 30" % (bits,))
    values, shape = _flatten(coeffs)
    if not values:
        raise StatRefusal("SHAPE", "an empty set")
    peak = max(abs(v) for v in values)
    if peak == 0:
        raise StatRefusal("ZERO_SET", "every coefficient is zero: there is no peak to scale to")
    qmax = 2 ** (bits - 1) - 1
    peak_f = float(peak)
    out = []
    for v in values:
        x = (float(v) / peak_f) * qmax
        if abs((x - math.floor(x)) - 0.5) <= GUARD:
            out.append(exact_half_to_even(Fraction(v) * qmax / Fraction(peak)))
        else:
            out.append(round(x))
    return np.array(out, dtype=np.int64).reshape(shape)

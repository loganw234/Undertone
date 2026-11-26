"""The learner's widths: each value of its arithmetic at its true extreme, under both profiles.

The figures are typed here from the design (the parcel's ledger, section 1, row W1), worked from the
bounds: a sum is at most 2^count_bits - 1 windows at an extreme sample; D = S1 n0 - S0 n1 is at most
n0 n1 (2^b - 1) in magnitude; D * COEFF_MAX and the peak follow. `model.learner.widths` must give them,
and the extremes, reached from a written state (both counts at their most, every sum at an extreme),
must need every bit of each width and fit it.
"""
import pytest

from spec import constants as C
from model import learner as L
from model.detector import bits_for
from model.learner import Learner

import test_lrn_b_support as S

WIDTHS = {
    "s16x1": {"count": 32, "sum": 48, "difference": 81, "scaled": 98, "peak": 80, "coefficient": 18},
    "s24x3": {"count": 32, "sum": 56, "difference": 89, "scaled": 106, "peak": 88, "coefficient": 18},
}


def test_lrn_b_widths_are_the_designs():
    assert C.LEARN_COUNT_BITS == 32
    assert {p: L.widths(p) for p in S.PROFILES} == WIDTHS


def extreme(profile, sign):
    """A learner of 2 taps at its most: both counts 2^32 - 1, label 1's sums at one extreme, label 0's at the other."""
    prof = C.PROFILES[profile]
    n = (1 << C.LEARN_COUNT_BITS) - 1
    hi, lo = (prof["sample_max"], prof["sample_min"]) if sign > 0 else (prof["sample_min"], prof["sample_max"])
    learner = Learner(S.start_blob(profile, 2), [], 0)
    learner.counts = [n, n]
    learner.sums = [[[n * lo] * S.channels(profile) for _ in range(2)], [[n * hi] * S.channels(profile) for _ in range(2)]]
    return learner, n


@pytest.mark.parametrize("profile", S.PROFILES)
@pytest.mark.parametrize("sign", [1, -1])
def test_lrn_b_widths_the_extremes_need_every_bit_and_fit(profile, sign):
    w = WIDTHS[profile]
    learner, n = extreme(profile, sign)
    b = C.PROFILES[profile]["sample_bits"]
    d = learner._difference()
    assert set(d) == {sign * n * n * ((1 << b) - 1)}

    def fits(v, bits):
        return -(1 << (bits - 1)) <= v <= (1 << (bits - 1)) - 1
    smin, smax = C.PROFILES[profile]["sample_min"], C.PROFILES[profile]["sample_max"]
    for value, width in [(n * smin, w["sum"]), (n * smax, w["sum"]), (d[0], w["difference"]),
                         (d[0] * C.COEFF_MAX, w["scaled"])]:
        assert fits(value, width), (value, width)
    for value, width in [(n * smin, w["sum"]), (d[0], w["difference"]), (d[0] * C.COEFF_MAX, w["scaled"])]:
        assert not fits(value, width - 1), "one bit fewer would hold %d" % value
    assert abs(d[0]).bit_length() == w["peak"]
    assert set(learner._quantise(d)) == {sign * C.COEFF_MAX}


@pytest.mark.parametrize("profile", S.PROFILES)
def test_lrn_b_widths_follow_the_count_width(profile):
    b = C.PROFILES[profile]["sample_bits"]
    for count_bits in (1, 2, 17, 32):
        w = L.widths(profile, count_bits)
        # a sum of up to 2^k - 1 windows needs b + k bits, but for k = 1, one window, which is a sample's b
        assert w["count"] == count_bits and w["sum"] == (b + count_bits if count_bits > 1 else b)
        assert w["difference"] == bits_for(-(((1 << count_bits) - 1) ** 2) * ((1 << b) - 1),
                                           (((1 << count_bits) - 1) ** 2) * ((1 << b) - 1))

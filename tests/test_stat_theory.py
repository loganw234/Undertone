"""STAT: the Q function, its inverse, D8's formula and the deflection.

Each expected answer is worked here without the code it judges: Q by a
numerical integral of the Gaussian density, Q's inverse by putting the answer
back through `math.erfc`, the pulse's energy by integer arithmetic on the
definition's samples, and the standard quantiles from the usual tables.
"""
import math

import pytest

from spec import constants as C
from stats import theory
from stats.errors import NAMES, STAT_NAMES, StatRefusal

SQRT2 = math.sqrt(2.0)

# Upper-tail quantiles of the standard normal, as tables print them.
TABLE = {0.5: 0.0, 0.05: 1.6448536269514722, 0.025: 1.959963984540054, 0.01: 2.3263478740408408,
         0.005: 2.5758293035489004, 0.001: 3.090232306167813}


def tail_by_integration(x, upper=12.0, steps=40_000):
    """Simpson's rule on the standard normal density from x to `upper`. No erfc."""
    h = (upper - x) / steps
    total = 0.0
    for i in range(steps + 1):
        t = x + i * h
        weight = 1 if i in (0, steps) else (4 if i % 2 else 2)
        total += weight * math.exp(-0.5 * t * t)
    return total * h / 3.0 / math.sqrt(2.0 * math.pi)


@pytest.mark.parametrize("x", [-2.0, -0.5, 0.0, 0.5763478740408408, 1.0, 2.3263478740408408, 4.0])
def test_stat_q_equals_the_integral_of_the_gaussian_density(x):
    assert theory.q(x) == pytest.approx(tail_by_integration(x), rel=1e-8, abs=1e-13)


def test_stat_q_at_zero_is_one_half_and_the_two_tails_sum_to_one():
    assert theory.q(0.0) == 0.5
    for x in (0.3, 1.0, 2.5, 6.0):
        assert theory.q(x) + theory.q(-x) == pytest.approx(1.0, abs=1e-15)
        assert theory.q(x) < theory.q(x - 0.1), "Q must fall as x rises"


@pytest.mark.parametrize("p, x", sorted(TABLE.items()))
def test_stat_q_inv_gives_the_tabled_quantiles(p, x):
    assert theory.q_inv(p) == pytest.approx(x, abs=1e-12)
    # and the table itself is checked against erfc, so a mistyped entry cannot pass
    assert 0.5 * math.erfc(x / SQRT2) == pytest.approx(p, rel=1e-12)


@pytest.mark.parametrize("p", [1e-300, 1e-100, 1e-20, 1e-9, 1e-6, 1e-3, 0.01, 0.1, 0.3, 0.5])
def test_stat_q_inv_put_back_through_erfc_returns_p_in_both_tails(p):
    x = theory.q_inv(p)
    assert 0.5 * math.erfc(x / SQRT2) == pytest.approx(p, rel=1e-11)
    assert (x > 0.0) == (p < 0.5)
    if 1e-9 <= p < 0.5:
        # the other tail, where 1 - p is still a different float from 1
        low = theory.q_inv(1.0 - p)
        assert low < 0.0
        assert 0.5 * math.erfc(-low / SQRT2) == pytest.approx(p, rel=1e-6)


def test_stat_q_inv_is_antisymmetric_about_one_half():
    for p in (0.6, 0.9, 0.99, 0.999999):
        assert theory.q_inv(p) == -theory.q_inv(1.0 - p)
        assert theory.q_inv(p) < 0.0


@pytest.mark.parametrize("bad, name", [(0.0, "PROBABILITY_RANGE"), (1.0, "PROBABILITY_RANGE"),
                                       (-0.1, "PROBABILITY_RANGE"), (1.5, "PROBABILITY_RANGE"),
                                       (float("nan"), "NOT_FINITE"), (float("inf"), "NOT_FINITE"),
                                       (True, "VALUE_TYPE"), ("0.5", "VALUE_TYPE"), (None, "VALUE_TYPE")])
def test_stat_q_inv_refuses_what_is_not_a_probability_by_name(bad, name):
    with pytest.raises(StatRefusal) as e:
        theory.q_inv(bad)
    assert e.value.name == name


def test_stat_d8_at_zero_deflection_is_the_false_alarm_probability():
    for pfa in (0.3, 0.01, 1e-6):
        assert theory.pd_matched(pfa, 0.0) == pytest.approx(pfa, rel=1e-11)


def test_stat_d8_is_one_half_when_the_deflection_equals_the_threshold():
    for pfa in (0.1, 0.01, 1e-4):
        assert theory.pd_matched(pfa, TABLE.get(pfa, theory.q_inv(pfa))) == pytest.approx(0.5, abs=1e-12)


def test_stat_d8_at_the_operating_point_of_d0_row_d11():
    # Q^-1(0.01) = 2.3263478740408408 from the table; minus d = 1.75 leaves 0.5763478740408408.
    by_hand = 0.5 * math.erfc(0.5763478740408408 / SQRT2)
    assert by_hand == pytest.approx(0.28219, abs=5e-6)
    assert theory.pd_matched(0.01, 1.75) == pytest.approx(by_hand, abs=1e-12)
    # D0 row D11 quotes 0.284 for this point. That is the formula at d = 1.7553, not at 1.75.
    assert abs(theory.pd_matched(0.01, 1.75) - 0.284) > 0.0015
    assert theory.pd_matched(0.01, 1.7553) == pytest.approx(0.284, abs=5e-5)


def test_stat_d8_rises_with_deflection_and_with_false_alarm_probability():
    assert theory.pd_matched(0.01, 1.0) < theory.pd_matched(0.01, 2.0) < theory.pd_matched(0.01, 3.0)
    assert theory.pd_matched(0.001, 2.0) < theory.pd_matched(0.01, 2.0) < theory.pd_matched(0.1, 2.0)


def test_stat_rectified_detector_by_hand_and_always_below_d8():
    # t = Q^-1(0.005) = 2.5758293035489004 from the table.
    t, d = 2.5758293035489004, 1.75
    by_hand = 0.5 * math.erfc((t - d) / SQRT2) + 0.5 * math.erfc((t + d) / SQRT2)
    assert by_hand == pytest.approx(0.20446, abs=5e-6)
    assert theory.pd_rectified(0.01, 1.75) == pytest.approx(by_hand, abs=1e-12)
    assert theory.pd_rectified(0.01, 0.0) == pytest.approx(0.01, rel=1e-11)
    assert theory.pd_rectified(0.01, -1.75) == pytest.approx(by_hand, abs=1e-12), "an absolute value cannot see a sign"
    for d in (0.5, 1.0, 1.75, 2.5, 4.0):
        assert theory.pd_rectified(0.01, d) < theory.pd_matched(0.01, d)


def test_stat_deflection_of_the_matched_filter_is_the_pulse_norm_over_sigma():
    pulse = C.PULSES["e0"]
    energy = sum(v * v for v in pulse)          # integer arithmetic on the definition's samples
    for sigma in (1.0, 2.0, 1477.0):
        assert theory.deflection(pulse, pulse, sigma) == pytest.approx(math.sqrt(energy) / sigma, rel=1e-13)


def test_stat_deflection_by_hand_for_a_filter_that_is_not_the_pulse():
    # h = (3, 4), s = (1, 2): h.s = 11, norm(h) = 5, sigma 2 -> 11 / 10.
    assert theory.deflection([3, 4], [1, 2], 2.0) == pytest.approx(1.1, rel=1e-15)
    assert theory.deflection([3, 4], [4, -3], 2.0) == 0.0, "an orthogonal filter is not moved by the pulse"
    assert theory.deflection([-1, -2], [1, 2], 1.0) == pytest.approx(-math.sqrt(5.0), rel=1e-15)
    # scaling the filter changes nothing; scaling the pulse scales the deflection
    assert theory.deflection([30, 40], [1, 2], 2.0) == pytest.approx(1.1, rel=1e-15)
    assert theory.deflection([3, 4], [2, 4], 2.0) == pytest.approx(2.2, rel=1e-15)
    # two channels are one longer vector: rows (3, 0) and (0, 4) against (1, 5) and (7, 2)
    assert theory.deflection([[3, 0], [0, 4]], [[1, 5], [7, 2]], 1.0) == pytest.approx(11 / 5, rel=1e-15)


def test_stat_a_mismatched_filter_never_beats_the_matched_one():
    pulse = C.PULSES["e0"]
    best = theory.deflection(pulse, pulse, 3.0)
    for wrong in (list(reversed(pulse)), [abs(v) for v in pulse], [1] * len(pulse), pulse[1:] + (0,)):
        assert theory.deflection(wrong, pulse, 3.0) < best


@pytest.mark.parametrize("coeffs, injected, sigma, name", [
    ([1, 2], [1, 2, 3], 1.0, "SHAPE"),
    ([0, 0], [1, 2], 1.0, "ZERO_SET"),
    ([1, 2], [1, 2], 0.0, "SIGMA"),
    ([1, 2], [1, 2], -1.0, "SIGMA"),
    ([1, 2], [1, 2], float("nan"), "NOT_FINITE"),
    ([1, float("inf")], [1, 2], 1.0, "NOT_FINITE"),
    ([], [], 1.0, "SHAPE"),
    (["a", "b"], [1, 2], 1.0, "VALUE_TYPE"),
])
def test_stat_deflection_refuses_by_name(coeffs, injected, sigma, name):
    with pytest.raises(StatRefusal) as e:
        theory.deflection(coeffs, injected, sigma)
    assert e.value.name == name


def test_stat_refusal_names_are_the_definitions_plus_this_packages_own_and_none_twice():
    assert NAMES[:len(C.REFUSALS)] == C.REFUSALS
    assert NAMES[len(C.REFUSALS):] == STAT_NAMES
    assert len(set(NAMES)) == len(NAMES), "a name of this package repeats one of the definition's"
    assert len(STAT_NAMES) == 15
    with pytest.raises(ValueError):
        StatRefusal("NOT_DECLARED_ANYWHERE")
    assert StatRefusal("ZERO_SET", "x").name == "ZERO_SET"

"""STAT: the quantising rule in floating point, held against the exact rule.

The exact rule is written a second time below, in rational arithmetic only,
without importing the code it judges. The small cases are worked by hand in
the comments.
"""
import math
from fractions import Fraction

import numpy as np
import pytest

from spec import constants as C
from stats import quantise as Q
from stats.errors import StatRefusal

HALF = Fraction(1, 2)


def exact_rule(values, bits):
    """peak_to_max and half_to_even, in Fractions. Independent of stats.quantise."""
    qmax = 2 ** (bits - 1) - 1
    peak = max(abs(Fraction(v)) for v in values)
    out = []
    for v in values:
        x = Fraction(v) * qmax / peak
        low = math.floor(x)
        if x - low > HALF or (x - low == HALF and low % 2 == 1):
            low += 1
        out.append(low)
    return out


def float_rule_without_the_guard(values, bits):
    """The same float arithmetic as the shipped code, trusting the float at every value."""
    qmax = 2 ** (bits - 1) - 1
    peak = float(max(abs(v) for v in values))
    return [round((float(v) / peak) * qmax) for v in values]


def test_stat_the_rule_is_the_definitions_rule():
    assert C.QUANTISE_SCALE == "peak_to_max"
    assert C.QUANTISE_ROUNDING == "half_to_even"
    assert (C.COEFF_BITS, C.COEFF_MAX) == (18, 131071)


def test_stat_exact_ties_go_to_the_even_integer_in_both_signs():
    # The peak is 131071, so the scale is exactly 1 and each value is its own image.
    values = [131071.0, 0.5, 1.5, 2.5, 3.5, -0.5, -1.5, -2.5, -3.5]
    assert Q.quantise(values).tolist() == [131071, 0, 2, 2, 4, 0, -2, -2, -4]


def test_stat_ties_that_appear_only_after_scaling():
    # The peak 262142 is twice 131071, so every value is halved: odd values become ties.
    values = [262142, 1, 3, 5, 7, -1, -3, -5, 2, 4]
    assert Q.quantise(values).tolist() == [131071, 0, 2, 2, 4, 0, -2, -2, 1, 2]


def test_stat_one_float_step_either_side_of_a_tie_goes_to_its_own_side():
    up, down = math.nextafter(2.5, math.inf), math.nextafter(2.5, -math.inf)
    assert Q.quantise([131071.0, up, down, -up, -down]).tolist() == [131071, 3, 2, -3, -2]


def test_stat_a_small_set_by_hand_at_four_bits_and_two_dimensions():
    # bits 4: qmax = 7. Peak 8, so x = v * 7 / 8:  0.875 -> 1, 1.75 -> 2, 3.5 -> 4 (tie, even), -7 -> -7.
    out = Q.quantise([[1, 2], [4, -8]], bits=4)
    assert out.tolist() == [[1, 2], [4, -7]]
    assert out.shape == (2, 2) and out.dtype == np.int64
    # bits 3: qmax = 3. x = v * 3 / 8:  0.375 -> 0, 0.75 -> 1, 1.5 -> 2 (tie, even), -3 -> -3.
    assert Q.quantise([1, 2, 4, -8], bits=3).tolist() == [0, 1, 2, -3]
    # bits 3, peak 12, so x = v / 4:  0.5 -> 0 (tie, even), 1.5 -> 2 (tie, even), and the same negated.
    assert Q.quantise([12, 2, 6, -2, -6], bits=3).tolist() == [3, 0, 2, 0, -2]


def test_stat_the_set_is_everything_in_one_call():
    # One peak for both rows: the second row is scaled by the first row's peak.
    assert Q.quantise([[8, 0], [4, 2]], bits=4).tolist() == [[7, 0], [4, 2]]
    # Row by row would give [7, 0] and [7, 4]: a different rule.
    assert Q.quantise([4, 2], bits=4).tolist() == [7, 4]


def test_stat_the_reference_pulse_equals_the_exact_rule_and_keeps_its_peak():
    pulse = C.PULSES["e0"]
    out = Q.quantise(pulse).tolist()
    assert out == exact_rule(pulse, C.COEFF_BITS)
    peak_at = max(range(len(pulse)), key=lambda i: abs(pulse[i]))
    assert pulse[peak_at] == -970 and out[peak_at] == C.COEFF_MIN + 1 == -131071
    assert max(abs(v) for v in out) == C.COEFF_MAX
    assert [i for i, v in enumerate(pulse) if v == 0] == [i for i, v in enumerate(out) if v == 0]
    # No value of this pulse is a tie: 131071 is prime, so a tie needs v * 131071 / 970 to end in
    # one half, which needs v = 485 or -485.
    assert 485 not in pulse and -485 not in pulse


def test_stat_numpy_arrays_and_lists_give_the_same_integers():
    pulse = C.PULSES["e0"]
    expect = exact_rule(pulse, 18)
    assert Q.quantise(list(pulse)).tolist() == expect
    assert Q.quantise(np.array(pulse)).tolist() == expect
    assert Q.quantise(np.array(pulse, dtype=np.float64)).tolist() == expect
    assert Q.quantise(np.array(pulse, dtype=np.float32)).tolist() == expect


# Found by search (scratch, 2026-11-23): with a peak of 3.0 these floats lie within a float step of a
# half-way point, and plain float arithmetic lands on the wrong side of it.
NEAR_TIES = [float.fromhex(h) for h in ("0x1.2000900048002p-15", "0x1.e000f00078004p-15",
                                        "0x1.0800840042002p-13", "0x1.c800e40072003p-13",
                                        "0x1.f800fc007e004p-13", "0x1.14008a0045002p-12")]


def test_stat_near_ties_where_a_bare_float_rounds_wrongly_are_quantised_exactly():
    values = [3.0] + NEAR_TIES
    assert Q.quantise(values).tolist() == exact_rule(values, 18) == [131071, 1, 3, 5, 9, 11, 11]


def test_stat_the_float_rule_without_its_guard_is_wrong_on_those_values():
    """The guard's negative control: the same arithmetic, trusted everywhere, misses the exact rule."""
    values = [3.0] + NEAR_TIES
    bare = float_rule_without_the_guard(values, 18)
    exact = exact_rule(values, 18)
    wrong = [i for i in range(len(values)) if bare[i] != exact[i]]
    assert wrong == [1, 2, 3, 4, 5, 6], "every one of the six must be a value the bare float gets wrong"
    assert all(abs(bare[i] - exact[i]) == 1 for i in wrong)


def test_stat_with_the_guard_switched_off_the_shipped_code_fails_the_same_values(monkeypatch):
    values = [3.0] + NEAR_TIES
    monkeypatch.setattr(Q, "GUARD", -1.0)
    assert Q.quantise(values).tolist() != exact_rule(values, 18)


def test_stat_random_sets_equal_the_exact_rule_at_several_widths():
    rng = np.random.Generator(np.random.PCG64(20261123))
    checked = 0
    for bits in (2, 3, 8, 18, 27, 30):
        for _ in range(40):
            values = (rng.standard_normal(33) * 10.0 ** rng.integers(-6, 7)).tolist()
            assert Q.quantise(values, bits).tolist() == exact_rule(values, bits)
            checked += 1
    assert checked == 240


def test_stat_half_way_grid_equals_the_exact_rule_for_awkward_peaks():
    """Every half-way point up to 300 and its two float neighbours, under peaks that do not divide evenly."""
    qmax = C.COEFF_MAX
    checked = 0
    for peak in (3.0, 7.0, 970.0, 0.1, 123.456):
        values = [peak]
        for n in range(300):
            target = (n + 0.5) * peak / qmax
            values += [target, math.nextafter(target, math.inf), math.nextafter(target, -math.inf), -target]
        assert Q.quantise(values).tolist() == exact_rule(values, 18)
        checked += len(values)
    assert checked == 5 * 1201


@pytest.mark.parametrize("coeffs, bits, name", [
    ([0, 0, 0], 18, "ZERO_SET"),
    ([0.0], 18, "ZERO_SET"),
    ([], 18, "SHAPE"),
    ([1.0, float("nan")], 18, "NOT_FINITE"),
    ([1.0, float("inf")], 18, "NOT_FINITE"),
    ([2 ** 53 + 1, 1], 18, "INEXACT_INPUT"),
    ([1, True], 18, "VALUE_TYPE"),
    ([1, "2"], 18, "VALUE_TYPE"),
    ([[1, 2], [3]], 18, "SHAPE"),
    ([[1, 2], 3], 18, "SHAPE"),
    ([[[1]]], 18, "SHAPE"),
    (5, 18, "SHAPE"),
    ([1, 2], 1, "COEFF_BITS_RANGE"),
    ([1, 2], 31, "COEFF_BITS_RANGE"),
    ([1, 2], 18.0, "COEFF_BITS_RANGE"),
    ([1, 2], True, "COEFF_BITS_RANGE"),
])
def test_stat_quantise_refuses_by_name(coeffs, bits, name):
    with pytest.raises(StatRefusal) as e:
        Q.quantise(coeffs, bits)
    assert e.value.name == name


def test_stat_the_largest_exact_integer_is_accepted_and_one_more_is_not():
    assert Q.quantise([2 ** 53, 2 ** 52], bits=3).tolist() == [3, 2]   # 1.5 is a tie: even
    with pytest.raises(StatRefusal) as e:
        Q.quantise([-(2 ** 53) - 1])
    assert e.value.name == "INEXACT_INPUT"

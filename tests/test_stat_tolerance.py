"""STAT: the tolerance of D0 row D9, and whether it has the right width.

The trap this file is built against: a tolerance so wide that any detector
passes, or one applied to something with more spread than a binomial. So the
tolerance is not only computed here, it is CALIBRATED: thousands of small
experiments with a correct detector, and the fraction falling outside one and
two standard errors must be what a binomial gives. A tolerance for the wrong
number of trials, and one that forgets the threshold was measured, must each be
reported by that same calibration. Those are the controls.

Seeds are fixed, so each test gives the same answer every run. Where a test's
pass depends on a draw, the chance a correct implementation fails it is stated.
"""
import math
from fractions import Fraction

import numpy as np
import pytest

from stats import recovery, theory, tolerance
from stats.errors import StatRefusal

Z01 = 2.3263478740408408      # Q^-1(0.01), from tables; checked against erfc in test_stat_theory.py
PFA = 0.01


def refused(name, fn, *args, **kwargs):
    with pytest.raises(StatRefusal) as e:
        fn(*args, **kwargs)
    assert e.value.name == name


# ----------------------------------------------------------------- the numbers

def test_stat_d9_ten_thousand_injections_give_half_a_point_at_worst():
    # D0 row D9: sqrt(0.25 / 10000) = 0.005.
    assert tolerance.binomial_se(0.5, 10_000) == pytest.approx(0.005, rel=1e-14)
    # and 0.5 is the worst case
    for p in (0.1, 0.2822, 0.4, 0.6, 0.9):
        assert tolerance.binomial_se(p, 10_000) < 0.005
    assert tolerance.binomial_se(0.2, 400) == pytest.approx(0.02, rel=1e-14)      # sqrt(0.16 / 400)


def test_stat_the_gate_decisions_are_four_standard_errors_and_a_floor_of_25():
    assert tolerance.Z_GATE == 4.0
    assert tolerance.MIN_NPQ == 25.0
    assert recovery.MIN_CROSSINGS == 100


@pytest.mark.parametrize("n, se, tol, margin", [(10_000, 0.005, 0.020, 0.040),
                                                (100_000, 0.0015811, 0.0063246, 0.0126491),
                                                (200_000, 0.0011180, 0.0044721, 0.0089443),
                                                (1_000_000, 0.0005, 0.0020, 0.0040)])
def test_stat_the_tolerance_table_at_the_gates_operating_point(n, se, tol, margin):
    # d = Q^-1(pfa): D8 gives exactly one half, so se = sqrt(0.25 / n), tolerance 4 se, catch margin 8 se.
    t = tolerance.tolerance(PFA, Z01, n)
    assert t["expected"] == pytest.approx(0.5, abs=1e-12)
    assert t["se_binomial"] == t["se_total"] == pytest.approx(se, abs=5e-8)
    assert t["se_threshold"] == 0.0
    assert t["tolerance"] == pytest.approx(tol, abs=5e-8)
    assert tolerance.catch_margin(PFA, Z01, n) == pytest.approx(margin, abs=5e-8)
    assert math.sqrt(0.25 / n) == pytest.approx(se, abs=5e-8)


def test_stat_a_count_just_inside_is_inside_and_one_just_outside_is_outside():
    # 10,000 injections at Pd 1/2: the tolerance is 0.020, which is 200 counts.
    for found, inside in ((5000, True), (5199, True), (4801, True), (5201, False), (4799, False),
                          (0, False), (10_000, False)):
        c = tolerance.check_efficiency(found, 10_000, PFA, Z01)
        assert c["inside"] is inside, found
        assert c["measured"] == found / 10_000
        assert c["deviation"] == pytest.approx(found / 10_000 - 0.5, abs=1e-12)
        assert c["z_score"] == pytest.approx((found - 5000) / 50.0, abs=1e-8)     # one se is 50 counts


def test_stat_the_prediction_sets_the_spread_not_the_measurement():
    # At Pd 0.2822 (pfa 0.01, d 1.75): se = sqrt(0.2822 * 0.7178 / 10000) = 0.0045007, whatever was found.
    for found in (2000, 2822, 4000):
        c = tolerance.check_efficiency(found, 10_000, PFA, 1.75)
        assert c["se_total"] == pytest.approx(0.0045007, abs=5e-8)
        assert c["expected"] == pytest.approx(0.28219, abs=5e-6)
    assert math.sqrt(0.28219 * 0.71781 / 10_000) == pytest.approx(0.0045007, abs=5e-8)


def test_stat_roc_slope_is_the_derivative_of_d8_with_respect_to_pfa():
    for pfa, d in ((0.01, 1.75), (0.01, Z01), (0.001, 3.0), (0.1, 0.5)):
        h = 1e-5 * pfa
        numeric = (theory.pd_matched(pfa + h, d) - theory.pd_matched(pfa - h, d)) / (2 * h)
        assert tolerance.roc_slope(pfa, d) == pytest.approx(numeric, rel=1e-5)
    # by hand at the gate's point: exp(d * z - d^2 / 2) with d = z is exp(z^2 / 2)
    assert tolerance.roc_slope(PFA, Z01) == pytest.approx(math.exp(Z01 * Z01 / 2.0), rel=1e-12)
    assert math.exp(Z01 * Z01 / 2.0) == pytest.approx(14.968, abs=5e-4)
    assert tolerance.roc_slope(PFA, 0.0) == 1.0, "with no pulse, Pd is Pfa and the slope is one"


def test_stat_a_measured_threshold_widens_the_tolerance_by_hand():
    # n 2000 at Pd 1/2: binomial variance 0.25 / 2000 = 1.25e-4.
    # m 10,000 noise scores at pfa 0.01: slope^2 * 0.01 * 0.99 / 10000 = 224.0556 * 9.9e-7 = 2.2182e-4,
    # with slope^2 = exp(Z01^2) = 224.0556. (Squaring the ROUNDED slope 14.968 gives 2.2180e-4, which is
    # wrong in its last digit; this comment said so until 2026-11-23 and the test was loose enough to pass.)
    t = tolerance.tolerance(PFA, Z01, 2000, m=10_000)
    assert t["se_binomial"] == pytest.approx(math.sqrt(1.25e-4), rel=1e-12)
    assert t["se_threshold"] == pytest.approx(math.sqrt(math.exp(Z01 * Z01) * 0.01 * 0.99 / 10_000), rel=1e-10)
    assert t["se_threshold"] == pytest.approx(0.014893, abs=5e-7)
    assert math.exp(Z01 * Z01) * 0.01 * 0.99 / 10_000 == pytest.approx(2.2182e-4, abs=5e-9)
    assert t["se_total"] == pytest.approx(math.sqrt(1.25e-4 + 2.2182e-4), abs=2e-7)
    assert t["se_total"] == pytest.approx(0.018623, abs=5e-7)
    assert t["tolerance"] == pytest.approx(4 * 0.018623, abs=2e-6)
    c = tolerance.check_efficiency(1000, 2000, PFA, Z01, m=10_000)
    assert c["se_threshold"] == t["se_threshold"] and c["se_total"] == t["se_total"]
    # the same count is judged more leniently when the threshold was measured, as it must be
    assert not tolerance.check_efficiency(1100, 2000, PFA, Z01)["inside"]              # 0.05 against 0.0447
    assert tolerance.check_efficiency(1100, 2000, PFA, Z01, m=10_000)["inside"]        # 0.05 against 0.0745


def test_stat_what_the_check_can_and_cannot_see():
    n = 10_000
    # a correct detector is rejected at the false-rejection rate, 2 Q(4)
    assert tolerance.rejection_probability(0.5, PFA, Z01, n) == pytest.approx(2 * 0.5 * math.erfc(4 / math.sqrt(2)), rel=1e-9)
    assert 2 * 0.5 * math.erfc(4 / math.sqrt(2)) == pytest.approx(6.334e-5, abs=5e-9)
    # one wrong by exactly the tolerance is rejected about half the time: THE LIMIT
    assert tolerance.rejection_probability(0.48, PFA, Z01, n) == pytest.approx(0.5, abs=1e-9)
    # one wrong by half the tolerance is almost always passed
    assert tolerance.rejection_probability(0.49, PFA, Z01, n) < 0.03
    # one wrong by the catch margin is almost always rejected
    assert tolerance.catch_margin(PFA, Z01, n) == pytest.approx(0.04, abs=1e-9)
    assert tolerance.rejection_probability(0.46, PFA, Z01, n) > 1 - 3.2e-5
    assert tolerance.rejection_probability(0.54, PFA, Z01, n) > 1 - 3.2e-5
    # more injections see a smaller fault: the same 0.01 shortfall at three counts
    seen = [tolerance.rejection_probability(0.49, PFA, Z01, k) for k in (10_000, 100_000, 1_000_000)]
    assert seen[0] < 0.03 and 0.98 < seen[1] < 0.995 and seen[2] > 1 - 1e-12


def test_stat_rejection_probability_uses_the_wrong_detectors_own_spread_by_hand():
    """100 injections, D8 one half: the standard error is 0.05 and the tolerance 0.2, so a count is
    inside from 30 to 70. A detector whose TRUE efficiency is 0.8 has its own spread,
    sqrt(0.8 * 0.2 / 100) = 0.04, not the prediction's 0.05. It is rejected when its count is above 70:
    Q((0.7 - 0.8) / 0.04) = Q(-2.5) = 0.99379, plus Q((0.8 - 0.3) / 0.04) = Q(12.5), which is nothing.
    With the prediction's spread the answer would be Q(-2) = 0.97725. The exact binomial figure,
    summed in integers below, is 0.98875: nearer the first."""
    own = 0.5 * math.erfc(-2.5 / math.sqrt(2))
    other = 0.5 * math.erfc(-2.0 / math.sqrt(2))
    assert own == pytest.approx(0.99379, abs=5e-6) and other == pytest.approx(0.97725, abs=5e-6)
    got = tolerance.rejection_probability(0.8, PFA, Z01, 100)
    assert got == pytest.approx(own, abs=1e-9)
    assert abs(got - other) > 0.016
    exact = float(sum(Fraction(math.comb(100, k)) * Fraction(4, 5) ** k * Fraction(1, 5) ** (100 - k)
                      for k in list(range(0, 30)) + list(range(71, 101))))
    assert exact == pytest.approx(0.98875, abs=5e-6)
    assert abs(got - exact) < abs(other - exact)


def test_stat_the_exact_false_rejection_rate_against_an_independent_exact_sum():
    # n = 1,001 at Pd 1/2. The tolerance is 4 * sqrt(0.25 / 1001), which is 63.28 counts,
    # so a count is inside when |K - 500.5| <= 63.28: K from 438 to 563.
    n = 1_001
    assert 4 * math.sqrt(0.25 / n) * n == pytest.approx(63.28, abs=0.005)
    inside = sum(math.comb(n, k) for k in range(438, 564))
    exact = float(1 - Fraction(inside, 2 ** n))
    assert exact == pytest.approx(6.679e-5, abs=5e-9)
    assert tolerance.false_rejection_probability(PFA, Z01, n) == pytest.approx(exact, rel=1e-8)
    # it is near the normal figure and not equal to it
    # 6.3249e-5 at 200,000; the normal figure is 6.3342e-5. (This line held 6.33e-5 to within 5e-7 until
    # 2026-11-23: a figure wrong in its third digit, behind an allowance wide enough to pass it.)
    assert tolerance.false_rejection_probability(PFA, Z01, 200_000) == pytest.approx(6.3249e-5, abs=5e-9)


@pytest.mark.parametrize("call, name", [
    (lambda: tolerance.check_efficiency(-1, 100, PFA, Z01), "COUNT_RANGE"),
    (lambda: tolerance.check_efficiency(101, 100, PFA, Z01), "COUNT_RANGE"),
    (lambda: tolerance.check_efficiency(50.0, 100, PFA, Z01), "COUNT_RANGE"),
    (lambda: tolerance.check_efficiency(0, 0, PFA, Z01), "COUNT_RANGE"),
    (lambda: tolerance.check_efficiency(True, 100, PFA, Z01), "COUNT_RANGE"),
    (lambda: tolerance.check_efficiency(50, 100, PFA, Z01, z=0.0), "COUNT_RANGE"),
    (lambda: tolerance.check_efficiency(50, 99, PFA, Z01), "TOLERANCE_UNDEFINED"),
    (lambda: tolerance.check_efficiency(9990, 10_000, PFA, 8.0), "TOLERANCE_UNDEFINED"),
    (lambda: tolerance.check_efficiency(3, 10_000, 1e-6, 0.0), "TOLERANCE_UNDEFINED"),
    (lambda: tolerance.check_count(50, 100, 1.0), "TOLERANCE_UNDEFINED"),
    (lambda: tolerance.check_efficiency(500, 1000, PFA, Z01, m=9_999), "TOO_FEW_NOISE_SCORES"),
    (lambda: tolerance.check_efficiency(500, 1000, PFA, Z01, m=0), "COUNT_RANGE"),
    (lambda: tolerance.check_efficiency(500, 1000, 0.0, Z01), "PROBABILITY_RANGE"),
    (lambda: tolerance.check_efficiency(500, 1000, PFA, float("nan")), "NOT_FINITE"),
    (lambda: tolerance.binomial_se(1.5, 100), "PROBABILITY_RANGE"),
])
def test_stat_a_check_that_would_mean_nothing_is_refused_by_name(call, name):
    refused(name, call)


def test_stat_the_floor_is_exactly_25():
    # n p (1 - p) = 25 at n = 100, p = 1/2: allowed. One trial fewer: refused.
    assert tolerance.check_efficiency(50, 100, PFA, Z01)["inside"]
    refused("TOLERANCE_UNDEFINED", tolerance.check_efficiency, 50, 99, PFA, Z01)


# ------------------------------------------------------------- the calibration

REPLICATES_KNOWN = 8000
REPLICATES_MEASURED = 2000
N_SMALL = 2000
M_SMALL = 10_000


def exact_outside_fraction(first_inside, last_inside, n=N_SMALL):
    """P(K outside first..last) for K binomial(n, 1/2): integers only."""
    inside = sum(math.comb(n, k) for k in range(first_inside, last_inside + 1))
    return float(1 - Fraction(inside, 2 ** n))


_EXPERIMENTS = {}


def experiments(measured_threshold, seed):
    """What each small experiment found: a list of (found, pfa to judge at, m or None).

    The draws depend only on the seed, so they are made once and every check, right or broken,
    is judged on the same experiments.
    """
    if (measured_threshold, seed) not in _EXPERIMENTS:
        rng = np.random.Generator(np.random.PCG64(seed))
        out = []
        for _ in range(REPLICATES_MEASURED if measured_threshold else REPLICATES_KNOWN):
            with_pulse = rng.standard_normal(N_SMALL) + Z01
            if measured_threshold:
                t = recovery.threshold_from_scores(rng.standard_normal(M_SMALL), PFA)
                out.append((int((with_pulse > t["threshold"]).sum()), t["pfa_effective"], t["m"]))
            else:
                out.append((int((with_pulse > Z01).sum()), PFA, None))
        _EXPERIMENTS[(measured_threshold, seed)] = out
    return _EXPERIMENTS[(measured_threshold, seed)]


def calibration(check, measured_threshold, seed):
    """Run many small experiments with a CORRECT detector and say whether `check` is calibrated.

    The detector is the matched filter's own output in standard units: noise is N(0, 1), a pulse
    adds d = Q^-1(pfa), so its true efficiency is exactly one half. `check` is called as
    check(found, n, pfa, d, m) and its z_score is what is judged.

    Expected fractions outside 1 and 2 standard errors:
      known threshold     exact, from the binomial(2000, 1/2): se is sqrt(2000) / 2 = 22.36 counts, so
                          inside 1 se is 978..1022 and inside 2 se is 956..1044.
      measured threshold  2 Q(1) and 2 Q(2), the normal figures; the count is then a mixture of
                          binomials and has no simple exact form.
    A count of replicates outside is accepted within 4 of its own standard deviations.
    """
    replicates = REPLICATES_MEASURED if measured_threshold else REPLICATES_KNOWN
    if measured_threshold:
        expected = (2 * 0.5 * math.erfc(1 / math.sqrt(2)), 2 * 0.5 * math.erfc(2 / math.sqrt(2)))
    else:
        expected = (exact_outside_fraction(978, 1022), exact_outside_fraction(956, 1044))
    z_scores = []
    cache = {}
    for key in experiments(measured_threshold, seed):
        if key not in cache:
            cache[key] = check(key[0], N_SMALL, key[1], Z01, key[2])["z_score"]
        z_scores.append(cache[key])
    assert len(z_scores) == replicates
    z_scores = np.abs(np.array(z_scores))
    out = {"replicates": replicates, "calibrated": True}
    for z, p in zip((1, 2), expected):
        count = int((z_scores > z).sum())
        band = 4.0 * math.sqrt(replicates * p * (1 - p))
        out["outside_%d" % z] = count
        out["expected_%d" % z] = replicates * p
        out["band_%d" % z] = band
        if abs(count - replicates * p) > band:
            out["calibrated"] = False
    return out


def show(label, c):
    print("\n%s, %d experiments: outside 1 se %d (expected %.0f +/- %.0f), outside 2 se %d (expected %.0f +/- %.0f): %s"
          % (label, c["replicates"], c["outside_1"], c["expected_1"], c["band_1"], c["outside_2"], c["expected_2"],
             c["band_2"], "CALIBRATED" if c["calibrated"] else "NOT CALIBRATED"))


def test_stat_the_exact_fractions_the_calibration_expects():
    # 31.43% outside one standard error and 4.66% outside two: near the normal 31.73% and 4.55%, and
    # not equal, because a count moves in whole steps. The two figures are exact sums in integers,
    # 1 - sum(comb(2000, k) for k in first..last) / 2^2000, and are held to half their last digit.
    # (This test held 0.3146 to within 0.0005 until 2026-11-23. The figure was wrong: it is 0.314304.)
    assert exact_outside_fraction(978, 1022) == pytest.approx(0.314304, abs=5e-7)
    assert exact_outside_fraction(956, 1044) == pytest.approx(0.046553, abs=5e-7)
    assert math.sqrt(N_SMALL) / 2 == pytest.approx(22.36, abs=0.005)


def test_gate_statistics__the_tolerance_has_the_width_of_a_correct_detectors_spread__known_threshold():
    """8,000 experiments of 2,000 injections. Chance a correct tolerance fails: about 1.3e-4 (two
    counts, each beyond 4 of its standard deviations)."""
    c = calibration(tolerance.check_efficiency, measured_threshold=False, seed=20261123)
    show("the tolerance, known threshold", c)
    assert c["calibrated"], c
    assert abs(c["outside_1"] - c["expected_1"]) <= c["band_1"]
    assert abs(c["outside_2"] - c["expected_2"]) <= c["band_2"]
    assert 2300 < c["expected_1"] < 2700 and 300 < c["expected_2"] < 400, "the test must have events to count"


def test_gate_statistics__the_tolerance_has_the_width_of_a_correct_detectors_spread__measured_threshold():
    """2,000 experiments, each with its own threshold from 10,000 noise scores. The threshold term
    is then the larger part of the spread (0.0149 against 0.0112)."""
    c = calibration(tolerance.check_efficiency, measured_threshold=True, seed=20261124)
    show("the tolerance, measured threshold", c)
    assert c["calibrated"], c
    assert 600 < c["expected_1"] < 670 and 80 < c["expected_2"] < 100


def wrong_trial_count(factor):
    """A tolerance worked for `factor` times the real number of trials: the trap in the brief."""
    def check(found, n, pfa, d, m=None):
        c = tolerance.check_efficiency(found, n, pfa, d, m)
        se = tolerance.tolerance(pfa, d, int(n * factor), m)["se_total"]
        return dict(c, z_score=c["deviation"] / se)
    return check


def test_control_statistics__a_tolerance_for_a_quarter_of_the_trials_is_reported_as_too_wide():
    """Twice too wide: it would pass detectors a correct tolerance rejects."""
    c = calibration(wrong_trial_count(0.25), measured_threshold=False, seed=20261123)
    show("CONTROL a tolerance for a quarter of the trials", c)
    assert not c["calibrated"], c
    assert c["outside_1"] < c["expected_1"] - c["band_1"], "too few experiments fall outside a tolerance that is too wide"
    assert c["outside_2"] < c["expected_2"] - c["band_2"]


def test_control_statistics__a_tolerance_for_four_times_the_trials_is_reported_as_too_narrow():
    """Half as wide: it would fail correct detectors."""
    c = calibration(wrong_trial_count(4), measured_threshold=False, seed=20261123)
    show("CONTROL a tolerance for four times the trials", c)
    assert not c["calibrated"], c
    assert c["outside_1"] > c["expected_1"] + c["band_1"]
    assert c["outside_2"] > c["expected_2"] + c["band_2"]


def test_control_statistics__a_tolerance_that_forgets_the_threshold_was_measured_is_reported():
    """A binomial tolerance on something with more spread than a binomial."""
    def binomial_only(found, n, pfa, d, m=None):
        return tolerance.check_efficiency(found, n, pfa, d, None)
    c = calibration(binomial_only, measured_threshold=True, seed=20261124)
    show("CONTROL a tolerance that forgets the threshold was measured", c)
    assert not c["calibrated"], c
    assert c["outside_1"] > c["expected_1"] + c["band_1"]
    assert c["outside_2"] > c["expected_2"] + c["band_2"]


def test_control_statistics__a_tolerance_wrong_by_a_tenth_in_width_is_still_reported():
    """The calibration's own reach: 10% too wide or too narrow in width is seen. Less than that is
    a stated limit in docs/model/stat.md."""
    def scaled(factor):
        def check(found, n, pfa, d, m=None):
            c = tolerance.check_efficiency(found, n, pfa, d, m)
            return dict(c, z_score=c["z_score"] / factor)
        return check
    for factor in (1.1, 1 / 1.1):
        c = calibration(scaled(factor), measured_threshold=False, seed=20261123)
        show("CONTROL a tolerance %.3f times as wide as it should be" % factor, c)
        assert not c["calibrated"], (factor, c)

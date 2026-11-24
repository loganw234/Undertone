"""The paired cost's standard error when BOTH thresholds are measured: is its width right?

Stage E1 compares a learned filter with the matched filter on the same injections, each at its
own threshold, each threshold measured from the same signal-free positions. The statistics
package's `paired_cost` gives the error for two GIVEN thresholds. `paired_arrays` in
tests/test_lrn_a_e1.py adds a term for the two measured ones, and that term is LRN-A's own
derivation. This file calibrates it the way tests/test_stat_tolerance.py calibrates the
tolerance: many small experiments, and the fraction that falls outside one and two standard
errors must be the normal's.

The experiments are made directly on scores, not on samples: two filters at a cosine rho with one
another give, on white Gaussian noise, a pair of standard normal scores with correlation rho; with
the pulse there, the matched filter's is shifted by d and the other's by d * rho. numpy makes the
pairs. Each experiment has the short form's own sizes: 12,000 signal-free pairs, 4,000 pulses.

Two broken formulas must each be reported, one in each direction: the paired error with no
threshold term at all (too narrow), and with the two thresholds' errors added as if they were
independent (too wide).

WHAT THIS DOES NOT SHOW (stated limits). One correlation, 0.99, one false-alarm probability, one
deflection, one size. A formula right there and wrong at another correlation would pass. The
acceptance bands are four standard deviations of a count over 2,000 experiments, so a width wrong
by less than about a tenth is not reliably seen (stat.md's limit 2, for the same method). The
scores are numpy's Gaussians, not the model's stream; numpy does not promise a seed's stream
across versions.
"""
import math

import numpy as np

from stats import recovery, theory, tolerance

import test_lrn_a_e1 as E1

EXPERIMENTS, M, N = 2000, 12000, 4000
RHO, PFA, SEED = 0.99, 0.01, 20261123
# what a correct width gives over 2,000 experiments, and four standard deviations of each count
OUTSIDE_ONE, OUTSIDE_TWO = 2000 * 0.3173, 2000 * 0.0455
BAND_ONE, BAND_TWO = 4 * math.sqrt(2000 * 0.3173 * 0.6827), 4 * math.sqrt(2000 * 0.0455 * 0.9545)

_made = {}


def experiments():
    """For each experiment: the measured cost less the predicted one, and three candidate errors."""
    if _made:
        return _made
    d = theory.q_inv(PFA)                           # the matched filter at an efficiency of one half
    rng = np.random.default_rng(SEED)
    other = math.sqrt(1.0 - RHO * RHO)
    off, formula, narrow, wide = [], [], [], []
    for _ in range(EXPERIMENTS):
        g = rng.standard_normal((M, 2))
        noise_a, noise_b = g[:, 0], RHO * g[:, 0] + other * g[:, 1]
        t_a, t_b = recovery.threshold_from_scores(noise_a, PFA), recovery.threshold_from_scores(noise_b, PFA)
        g = rng.standard_normal((N, 2))
        hits_a = g[:, 0] + d > t_a["threshold"]
        hits_b = RHO * g[:, 0] + other * g[:, 1] + d * RHO > t_b["threshold"]
        pfa = t_a["pfa_effective"]
        s_a, s_b = tolerance.roc_slope(pfa, d), tolerance.roc_slope(pfa, d * RHO)
        pair = E1.paired_arrays(noise_a, t_a["threshold"], hits_a, noise_b, t_b["threshold"], hits_b, s_a, s_b)
        off.append(pair["cost"] - (theory.pd_matched(pfa, d) - theory.pd_matched(pfa, d * RHO)))
        formula.append(pair["se"])
        narrow.append(pair["se_pairs"])
        wide.append(math.sqrt(pair["se_pairs"] ** 2 + (s_a ** 2 + s_b ** 2) * pfa * (1.0 - pfa) / M))
    _made.update(off=np.array(off), formula=np.array(formula), narrow=np.array(narrow), wide=np.array(wide))
    return _made


def counts(off, se):
    z = off / se
    return int((np.abs(z) > 1.0).sum()), int((np.abs(z) > 2.0).sum()), float(z.mean())


def calibrated(one, two):
    return abs(one - OUTSIDE_ONE) <= BAND_ONE and abs(two - OUTSIDE_TWO) <= BAND_TWO


def test_lrn_a_paired_the_error_with_two_measured_thresholds_has_the_width_it_states():
    e = experiments()
    one, two, mean = counts(e["off"], e["formula"])
    print("paired calibration: %d experiments of %d pulses and %d signal-free pairs at correlation %.2f: %d outside one "
          "standard error (%.0f expected, accepted within %.0f), %d outside two (%.0f, within %.0f); mean z %+.3f; the "
          "threshold term is %.2f of the whole error"
          % (EXPERIMENTS, N, M, RHO, one, OUTSIDE_ONE, BAND_ONE, two, OUTSIDE_TWO, BAND_TWO, mean,
             float(np.mean(np.sqrt(e["formula"] ** 2 - e["narrow"] ** 2) / e["formula"]))))
    assert calibrated(one, two)
    assert abs(mean) < 0.15, "the measured cost is not biased against the predicted one by more than a seventh of an error"
    assert float(np.mean(e["narrow"] / e["formula"])) < 0.6, "the threshold term is most of the error here: the case can tell"


def test_lrn_a_paired_control__the_error_without_its_threshold_term_is_reported_as_too_narrow():
    e = experiments()
    one, two, _mean = counts(e["off"], e["narrow"])
    print("CONTROL paired calibration, no threshold term: %d outside one standard error (%.0f expected), %d outside two (%.0f)"
          % (one, OUTSIDE_ONE, two, OUTSIDE_TWO))
    assert not calibrated(one, two) and one > OUTSIDE_ONE + BAND_ONE and two > OUTSIDE_TWO + BAND_TWO


def test_lrn_a_paired_control__the_two_thresholds_taken_as_independent_is_reported_as_too_wide():
    e = experiments()
    one, two, _mean = counts(e["off"], e["wide"])
    print("CONTROL paired calibration, thresholds as if independent: %d outside one standard error (%.0f expected), %d "
          "outside two (%.0f)" % (one, OUTSIDE_ONE, two, OUTSIDE_TWO))
    assert not calibrated(one, two) and one < OUTSIDE_ONE - BAND_ONE


def test_lrn_a_paired_the_term_by_hand_on_a_small_case():
    """Eight signal-free positions, two models. Worked here in fractions, nothing from the code."""
    free_a = np.array([9.0, 8.0, 1.0, 2.0, 3.0, 0.0, 7.0, 1.5])       # above 6.5: positions 0, 1, 6
    free_b = np.array([9.0, 1.0, 8.0, 2.0, 3.0, 0.0, 7.0, 1.5])       # above 6.5: positions 0, 2, 6
    hits_a = np.array([True, True, False, False, True, False])
    hits_b = np.array([True, False, False, True, True, True])
    pair = E1.paired_arrays(free_a, 6.5, hits_a, free_b, 6.5, hits_b, 2.0, 3.0)
    assert (pair["noise_a_only"], pair["noise_b_only"], pair["noise_both"], pair["m"]) == (1, 1, 2, 8)
    assert (pair["a_only"], pair["b_only"], pair["n"]) == (1, 2, 6) and pair["cost"] == (1 - 2) / 6
    # pairs: sqrt(1 + 2 - (1 - 2)^2 / 6) / 6. thresholds: k_a = k_b = 3, both = 2, m = 8:
    #   (4 * 3 * (5/8) + 9 * 3 * (5/8) - 2 * 2 * 3 * (2 - 9/8)) / 64 = (7.5 + 16.875 - 10.5) / 64 = 13.875 / 64
    assert pair["se_pairs"] == math.sqrt(3 - 1 / 6) / 6
    assert abs(pair["se_thresholds"] - math.sqrt(13.875 / 64)) < 1e-15
    assert abs(pair["se"] - math.sqrt((3 - 1 / 6) / 36 + 13.875 / 64)) < 1e-15
    # with equal slopes and equal counts the term is the slope squared times the positions where exactly one crosses
    equal = E1.paired_arrays(free_a, 6.5, hits_a, free_b, 6.5, hits_b, 2.0, 2.0)
    assert abs(equal["se_thresholds"] ** 2 - 4.0 * (1 + 1) / 64) < 1e-15
    # and two models that cross at the very same positions have no threshold term at all
    same = E1.paired_arrays(free_a, 6.5, hits_a, free_a, 6.5, hits_a, 2.0, 2.0)
    assert same["se_thresholds"] == 0.0 and same["cost"] == 0.0

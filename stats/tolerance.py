"""The tolerance of D0 row D9: how far a measured efficiency may lie from its prediction.

A measured efficiency is found / n over n injections. If the detector's true
efficiency is p and the injections are independent trials, `found` is binomial
and found / n has standard error sqrt(p (1 - p) / n). D9 is that, at its worst
case p = 1/2: sqrt(0.25 / 10000) = 0.005.

THE CHECK.   |found / n - p| <= z * se_total,   p = pd_matched(pfa, d)

    se_total^2 = p (1 - p) / n  +  roc_slope(pfa, d)^2 * pfa (1 - pfa) / m

The first term is the binomial one, with p the PREDICTION, not the measurement.
The second is there only when the threshold was itself measured, from m
independent signal-free scores: the threshold's false-alarm probability then
varies by sqrt(pfa (1 - pfa) / m) from one noise sample to the next, and the
efficiency follows it at `roc_slope` points per point. Leaving it out would
apply a binomial tolerance to something with more spread than a binomial.

z = 4 and the floor n p (1 - p) >= 25 are DECISIONs of the lead's (2026-11-23)
for the gate's own checks. A report gives the deviation in standard errors
(`z_score`) whatever z is.

WHAT THE CHECK CANNOT SEE, and this is the limit that matters most. A detector
whose true efficiency is off by less than the tolerance is usually passed. One
off by exactly the tolerance is rejected about half the time. Only one off by
(z + z) standard errors is rejected almost always: `catch_margin`. At D9's
10,000 injections and p = 1/2 the tolerance is 0.020 and the catch margin
0.040. The number of injections has to be chosen for the fault one means to
see; `rejection_probability` says what a given count can do.

Other limits. The spread is the normal approximation's, refused below
n p (1 - p) = 25 (`false_rejection_probability` gives the exact binomial figure
for a known threshold). The threshold term is first order in 1 / m and assumes
Gaussian scores. Independence of the n trials is the caller's to ensure;
`stats.recovery.recovery_count` refuses a schedule that breaks it.

Nothing here imports from `model/`.
"""
import math

from stats.errors import StatRefusal
from stats.recovery import MIN_CROSSINGS
from stats.theory import _number, _probability, pd_matched, q, q_inv

Z_GATE = 4.0
MIN_NPQ = 25.0


def _trials(n, what="n"):
    if type(n) is not int or n < 1:
        raise StatRefusal("COUNT_RANGE", "%s is %r, not a positive int" % (what, n))
    return n


def _z(z):
    z = _number(z, "z")
    if not z > 0.0:
        raise StatRefusal("COUNT_RANGE", "z is %r, not positive" % (z,))
    return z


def binomial_se(p, n):
    """sqrt(p (1 - p) / n): the standard error of a fraction found in n independent trials."""
    p = _number(p, "p")
    if not 0.0 <= p <= 1.0:
        raise StatRefusal("PROBABILITY_RANGE", "p is %r" % (p,))
    return math.sqrt(p * (1.0 - p) / _trials(n))


def roc_slope(pfa, d):
    """How fast D8's Pd moves with Pfa: dPd/dPfa = exp(d * Q^-1(pfa) - d^2 / 2).

    It is the ratio of the two Gaussian densities at the threshold. At Pfa 0.01
    and Pd 1/2 it is about 15: a hundredth of a point of false-alarm
    probability moves the efficiency by 0.15 points.
    """
    d = _number(d, "d")
    return math.exp(d * q_inv(pfa) - 0.5 * d * d)


def _threshold_variance(pfa, d, m):
    if m is None:
        return 0.0
    m = _trials(m, "m")
    if pfa * m < MIN_CROSSINGS:
        raise StatRefusal("TOO_FEW_NOISE_SCORES", "%d scores at pfa %r: fewer than %d crossings" % (m, pfa, MIN_CROSSINGS))
    return roc_slope(pfa, d) ** 2 * pfa * (1.0 - pfa) / m


def check_count(found, n, p, extra_variance=0.0, z=Z_GATE):
    """Is found / n within z standard errors of p? The general form of the check.

    `extra_variance` is added to the binomial p (1 - p) / n. Returns a dict:
    inside, found, n, measured, expected, deviation, se_binomial, se_total,
    tolerance, z_score, z. Refused: a count outside 0..n; n p (1 - p) below 25.
    """
    n = _trials(n)
    if type(found) is not int or not 0 <= found <= n:
        raise StatRefusal("COUNT_RANGE", "found is %r of %d" % (found, n))
    p = _number(p, "p")
    z = _z(z)
    if not 0.0 < p < 1.0 or n * p * (1.0 - p) < MIN_NPQ:
        raise StatRefusal("TOLERANCE_UNDEFINED",
                          "n p (1 - p) is %.3g, below %g: at an efficiency this near 0 or 1 "
                          "a tolerance says nothing" % (n * p * (1.0 - p), MIN_NPQ))
    var_binomial = p * (1.0 - p) / n
    se_total = math.sqrt(var_binomial + extra_variance)
    measured = found / n
    deviation = measured - p
    return {"inside": abs(deviation) <= z * se_total, "found": found, "n": n, "measured": measured,
            "expected": p, "deviation": deviation, "se_binomial": math.sqrt(var_binomial),
            "se_total": se_total, "tolerance": z * se_total, "z_score": deviation / se_total, "z": z}


def tolerance(pfa, d, n, m=None, z=Z_GATE):
    """The tolerance on a measured efficiency, for D8 at (pfa, d) over n injections.

    `m` is None for a threshold known from sigma. For a threshold measured from
    m independent signal-free scores, pass that m, and pass as `pfa` the
    `pfa_effective` that `stats.recovery.threshold_from_scores` returned.
    Returns a dict: expected, se_binomial, se_threshold, se_total, tolerance.
    """
    pfa = _probability(pfa, "pfa")
    p = pd_matched(pfa, d)
    var_threshold = _threshold_variance(pfa, d, m)
    full = check_count(0, n, p, var_threshold, z)
    return {"expected": p, "se_binomial": full["se_binomial"], "se_threshold": math.sqrt(var_threshold),
            "se_total": full["se_total"], "tolerance": full["tolerance"], "z": full["z"], "n": n, "m": m}


def check_efficiency(found, n, pfa, d, m=None, z=Z_GATE):
    """Does a detector that found `found` of n injections match D8 at (pfa, d)?

    This is the check a detector is handed to. `d` is the deflection the
    detector is CLAIMED to have: norm(s) / sigma for the matched filter. See
    `tolerance` for `m`. The dict is `check_count`'s, plus se_threshold.
    """
    pfa = _probability(pfa, "pfa")
    var_threshold = _threshold_variance(pfa, d, m)
    out = check_count(found, n, pd_matched(pfa, d), var_threshold, z)
    out["se_threshold"] = math.sqrt(var_threshold)
    return out


def rejection_probability(true_p, pfa, d, n, m=None, z=Z_GATE):
    """The chance the check reports `outside` for a detector whose true efficiency is true_p.

    Normal approximation, with the wrong detector's own binomial spread. At
    true_p equal to the prediction it is the false-rejection rate, 2 Q(z).
    """
    true_p = _probability(true_p, "true_p")
    t = tolerance(pfa, d, n, m, z)
    se = math.sqrt(true_p * (1.0 - true_p) / n + t["se_threshold"] ** 2)
    shift = true_p - t["expected"]
    return q((t["tolerance"] - shift) / se) + q((t["tolerance"] + shift) / se)


def catch_margin(pfa, d, n, m=None, z=Z_GATE, power_z=Z_GATE):
    """How wrong a detector's true efficiency must be to be rejected almost always.

    (z + power_z) * se_total: a detector off by this much is rejected with
    probability about 1 - Q(power_z), which is 1 - 3.2e-5 at power_z = 4. It
    uses the prediction's spread for the wrong detector's, which is close when
    the two efficiencies are; `rejection_probability` does not.
    """
    return (_z(z) + _z(power_z)) * tolerance(pfa, d, n, m, z)["se_total"]


def _log_pmf(n, k, p):
    return (math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
            + k * math.log(p) + (n - k) * math.log(1.0 - p))


def false_rejection_probability(pfa, d, n, z=Z_GATE):
    """The exact chance that a CORRECT detector falls outside, for a known threshold.

    The binomial's two tails beyond the tolerance, summed term by term; no
    normal approximation. It is close to 2 Q(z) and not equal to it.
    """
    t = tolerance(pfa, d, n, None, z)
    p = t["expected"]
    total = 0.0
    # Start one count inside each edge and walk out with the check's own
    # comparison, so the edge is where `check_count` puts it.
    k = max(0, math.floor(n * (p + t["tolerance"])) - 1)
    while k <= n and abs(k / n - p) <= t["tolerance"]:
        k += 1
    while k <= n:
        term = math.exp(_log_pmf(n, k, p))
        total += term
        if term < 1e-30:
            break
        k += 1
    k = min(n, math.ceil(n * (p - t["tolerance"])) + 1)
    while k >= 0 and abs(k / n - p) <= t["tolerance"]:
        k -= 1
    while k >= 0:
        term = math.exp(_log_pmf(n, k, p))
        total += term
        if term < 1e-30:
            break
        k -= 1
    return total

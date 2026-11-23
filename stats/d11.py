"""The script for D0 row D11:  python -m stats.d11

D11 says that outside the matched-filter configuration D8 does not apply, and
quotes a simulation: an absolute-value rectifier after the filter, at a
false-alarm probability of 0.01 and d = 1.75, on a 128-sample windowed sine at
sigma = 2 over 400,000 trials. The row is falsified by "a committed script that
reproduces both figures". This is that script.

What it simulates, in real-valued samples as D11's run was (nothing here is
quantised): `TRIALS` windows of noise with the pulse added and `TRIALS` windows
of noise alone. The pulse is a 128-sample sine of 8 cycles under a Hann window,
scaled so that norm(s) / sigma is exactly `D`. Each window is correlated with
the pulse. Four detectors are counted, all at false-alarm probability `PFA`:

    matched,   threshold known from sigma      D8 should hold
    matched,   threshold measured from noise   D8 should hold
    rectified, threshold known from sigma      D8 should NOT hold
    rectified, threshold measured from noise   D8 should NOT hold

and each is handed to `stats.tolerance.check_efficiency` against D8.

It also counts the same two detectors on a pulse of the OPPOSITE sign (the same
noise with the pulse subtracted). That is what a rectifier buys: it finds the
negated pulse as often as the pulse, where the matched filter finds it less
often than noise. And it is the only place the rectifier can be told from a
raised one-sided threshold: at d = 1.75 the rectified detector's lower tail
holds 8 trials in a million, so on the pulse itself the two count alike.

The seed, the trial count and the run time are printed. D11 does not say how
many cycles its sine had or which window; by D8 only d matters, and d is the
same here.

Limits. One operating point, one seed. The noise is numpy's Gaussian, not the
instrument's generator. `stats.theory.pd_rectified` is this package's own
derivation, so "the rectified detector matches 0.2045" checks the simulation
and the derivation against each other, and neither against an outside source.

Nothing here imports from `model/`.
"""
import math
import sys
import time

import numpy as np

from stats.recovery import threshold_from_scores, threshold_known_sigma
from stats.theory import deflection, pd_matched, pd_rectified, q, q_inv
from stats.tolerance import check_count, check_efficiency

SEED = 20261123
TRIALS = 400_000
TAPS = 128
CYCLES = 8
SIGMA = 2.0
D = 1.75
PFA = 0.01


def pulse():
    """The 128-sample windowed sine, scaled so that its norm over SIGMA is D."""
    n = np.arange(TAPS)
    shape = 0.5 * (1.0 - np.cos(2.0 * math.pi * n / TAPS)) * np.sin(2.0 * math.pi * CYCLES * n / TAPS)
    return shape * (D * SIGMA / math.sqrt(float((shape * shape).sum())))


def rectify(scores):
    """The rectifier: an absolute value after the filter. Every rectified count below goes through here."""
    return np.abs(scores)


def run(trials=TRIALS, seed=SEED):
    """Simulate, count and check. Returns a dict; `main` prints it."""
    started = time.perf_counter()
    s = pulse()
    energy = float((s * s).sum())
    d = deflection(s, s, SIGMA)
    rng = np.random.Generator(np.random.PCG64(seed))
    with_pulse = np.empty(trials)
    noise_only = np.empty(trials)
    step = 20_000
    for start in range(0, trials, step):
        count = min(step, trials - start)
        with_pulse[start:start + count] = (rng.standard_normal((count, TAPS)) * SIGMA + s) @ s
        noise_only[start:start + count] = (rng.standard_normal((count, TAPS)) * SIGMA) @ s
    # The same noise with the pulse SUBTRACTED: (noise - s) . s = (noise + s) . s - 2 E.
    with_negated = with_pulse - 2.0 * energy

    known = threshold_known_sigma(PFA, SIGMA, s)
    known_rectified = q_inv(PFA / 2.0) * SIGMA * math.sqrt(energy)
    measured = threshold_from_scores(noise_only, PFA)
    measured_rectified = threshold_from_scores(rectify(noise_only), PFA)

    def against_d8(found, pfa=PFA, m=None):
        return check_efficiency(int(found), trials, pfa, d, m)

    out = {
        "seed": seed, "trials": trials, "taps": TAPS, "sigma": SIGMA, "pfa": PFA, "d": d,
        "d8": pd_matched(PFA, d),
        "rectified_exact": pd_rectified(PFA, d),
        "matched_known": against_d8((with_pulse > known).sum()),
        "matched_measured": against_d8((with_pulse > measured["threshold"]).sum(),
                                       measured["pfa_effective"], measured["m"]),
        "rectified_known": against_d8((rectify(with_pulse) > known_rectified).sum()),
        "rectified_measured": against_d8((rectify(with_pulse) > measured_rectified["threshold"]).sum(),
                                         measured_rectified["pfa_effective"], measured_rectified["m"]),
        "false_alarm_matched_known": float((noise_only > known).mean()),
        "false_alarm_rectified_known": float((rectify(noise_only) > known_rectified).mean()),
        "negated_matched_found": int((with_negated > known).sum()),
        "negated_matched_exact": q(q_inv(PFA) + d),
        "negated_rectified_found": int((rectify(with_negated) > known_rectified).sum()),
    }
    out["rectified_known_against_exact"] = check_count(out["rectified_known"]["found"], trials, out["rectified_exact"])
    out["negated_rectified_against_exact"] = check_count(out["negated_rectified_found"], trials, out["rectified_exact"])
    out["seconds"] = time.perf_counter() - started
    return out


def report(r):
    """The lines `main` prints."""
    lines = [
        "D11: seed %d, %d trials with the pulse and %d without, %d taps, sigma %g"
        % (r["seed"], r["trials"], r["trials"], r["taps"], r["sigma"]),
        "     false-alarm probability %g, d = norm(s) / sigma = %.6f" % (r["pfa"], r["d"]),
        "D8's formula          Q(Q^-1(Pfa) - d)        = %.4f" % r["d8"],
        "rectified, exact      Q(t - d) + Q(t + d)     = %.4f   (t = Q^-1(Pfa / 2))" % r["rectified_exact"],
    ]
    for key, label in (("matched_known", "matched,   threshold known   "),
                       ("matched_measured", "matched,   threshold measured"),
                       ("rectified_known", "rectified, threshold known   "),
                       ("rectified_measured", "rectified, threshold measured")):
        c = r[key]
        lines.append("%s  found %6d  efficiency %.4f  se %.4f  %+6.1f se from D8  %s D8's tolerance"
                     % (label, c["found"], c["measured"], c["se_total"], c["z_score"],
                        "INSIDE" if c["inside"] else "OUTSIDE"))
    c = r["rectified_known_against_exact"]
    lines.append("rectified, threshold known, against its own exact figure: %+.1f se, %s"
                 % (c["z_score"], "INSIDE" if c["inside"] else "OUTSIDE"))
    n = r["negated_rectified_against_exact"]
    lines.append("a pulse of the opposite sign, thresholds known: matched found %d (%.1f expected), "
                 "rectified found %d, efficiency %.4f, %+.1f se from its exact figure"
                 % (r["negated_matched_found"], r["negated_matched_exact"] * r["trials"],
                    r["negated_rectified_found"], n["measured"], n["z_score"]))
    lines.append("measured false-alarm rate at the known thresholds: matched %.5f, rectified %.5f"
                 % (r["false_alarm_matched_known"], r["false_alarm_rectified_known"]))
    lines.append("run time %.2f s" % r["seconds"])
    return lines


def main():
    for line in report(run()):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""What study D1b's 2021 records say about the noise stage E3 meets: the design's section 1.

    python docs/studies/e3/e3noise2021.py <folder of D1b's files>                 the samples as recorded
    python docs/studies/e3/e3noise2021.py <folder of D1b's files> --difference    their first difference

NOT E3's RECORDS. D1b's 50-minute HHZ windows of 2021-09-13 and 2021-09-15 (the first and third
of its three days; the second holds the launch D1b looked at) at CI.CDM, CI.HDH, CI.MPP and
CI.SRN, fetched on 2026-11-23 and held to their SHA-256 in docs/studies/d1/manifest.tsv. It makes
no request. This file is the scratch script that printed the design's figures (the round's
ledger, E3S, 2026-11-25 20:57, section 1), with only its import path and this docstring changed.

Prints, a station and a file at a time: the raw level; the e0 filter's scores' spread, and
(99th percentile - median) / Q^-1(0.01) / norm(e0), the white level that would give that
threshold; the 64-frame mean's spread; an amplitude; and a first-order prediction of the matched
filter's and the learner's deflection and D8's Pd at it, from the file's own covariances:

    the matched filter   e0 . p / sqrt(e0' C e0)
    the learner of N     p . p / sqrt(p' C p + tr(C_D C) / N)

with p the injected integers, C the covariance of 64-frame windows at stride 64, and C_D that of
a record's two windows' difference (frames j .. j + 63 less j - 64 .. j - 1, j every 128 frames).

WHAT IT IS NOT, stated:
  - The amplitude is AN APPROXIMATION of e3prep.py's rule, not the rule: the filter here is e0's
    own samples, not the model's quantised integers (a positive multiple of them, so the same
    up to rounding), and above num = 64 the search steps by num // 64, so the num it prints can
    be up to about 1.6% past the least.
  - The deflections and Pd are Gaussian and first order. The e0 scores here are not Gaussian (at
    CDM 2021-09-13 their spread is 171,726 where their 99th percentile gives about 111,000), so
    these are a forecast and not a measurement of any detector.
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "docs", "studies", "d1"))
import mseed  # noqa: E402
from spec import constants as C  # noqa: E402
from stats import theory  # noqa: E402

E0 = np.array(C.PULSES["e0"], dtype=np.float64)
T = 64


def round_half_even(a):
    return np.rint(a)  # numpy rounds half to even


def samples(path):
    recs = mseed.read(path)
    return np.array([v for r in recs for v in r["samples"]], dtype=np.float64)


def windows(x, starts):
    idx = np.asarray(starts)[:, None] + np.arange(T)[None, :]
    return x[idx]


def main(folder):
    for st in ("CDM", "HDH", "MPP", "SRN"):
        for day in ("2021-09-13", "2021-09-15"):
            path = os.path.join(folder, "CI.%s.HHZ.%s.mseed" % (st, day))
            x = samples(path)
            if DIFFERENCE:
                x = np.diff(x)
            n = len(x)
            # e0 filter scores at stride 64, full windows only
            starts = np.arange(0, n - T + 1, T)
            W = windows(x, starts)
            s = W @ E0
            box = W.mean(axis=1)
            med = np.median(s)
            q99 = np.sort(s)[len(s) - int(0.01 * len(s)) - 1]
            target = q99 - med
            sigma_eq = (q99 - med) / theory.q_inv(0.01) / math.sqrt(float(E0 @ E0))
            # least amplitude in steps of 1/65536 whose injected integers reach the target through e0
            num = 1
            while True:
                p = round_half_even(E0 * num / 65536.0)
                if float(p @ E0) >= target:
                    break
                num += 1 if num < 64 else max(1, num // 64)
            A = num / 65536.0
            p = round_half_even(E0 * A)
            # covariances
            cov = np.cov(W, rowvar=False)
            j = np.arange(T, n - T, 128)
            D = windows(x, j) - windows(x, j - T)
            covD = np.cov(D, rowvar=False)
            d_mf = float(E0 @ p) / math.sqrt(float(E0 @ cov @ E0))
            pp = float(p @ cov @ p)
            out = []
            for N in (1024, 16384, 65536):
                extra = float(np.trace(covD @ cov)) / N
                d_l = float(p @ p) / math.sqrt(pp + extra)
                out.append("N %d d %.3f Pd %.3f" % (N, d_l, theory.pd_matched(0.01, d_l)))
            print("%s %s: %d samples, raw mean %.0f sd %.1f; e0 scores sd %.0f, (q99-med)/2.326/norm = %.2f counts; "
                  "boxcar-64 mean sd %.1f; first difference sd %.2f" % (
                      st, day, n, x.mean(), x.std(), s.std(), sigma_eq, box.std(), np.diff(x).std()))
            print("   amplitude %d/65536 = %.5f, injected pulse peak %d, nonzero taps %d, sum %d; "
                  "matched filter d %.3f Pd %.3f; learner (first order, Gaussian, measured covariances): %s; "
                  "the asymptote p.p/sqrt(p'Cp) %.3f" % (
                      num, A, int(np.abs(p).max()), int((p != 0).sum()), int(p.sum()), d_mf,
                      theory.pd_matched(0.01, d_mf), "; ".join(out), float(p @ p) / math.sqrt(pp)))


DIFFERENCE = "--difference" in sys.argv

if __name__ == "__main__":
    main(sys.argv[1])

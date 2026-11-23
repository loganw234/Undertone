"""Stage E0 in software: does the reference model, as a matched filter, find a known pulse as often as D8 says?

This is the run the plan's row V1 turns on. No learning: the coefficients are the matched filter
for the reference pulse, quantised by the definition's rule. The model's own noise, the model's own
injector, the model's own detector core, all through `model.run`. What judges the count is NOT the
model: it is D8's formula and the tolerance, both from `stats/`, which imports nothing of `model/`.

THE EXPERIMENT, fixed before any run (the round's ledger, 2026-11-23, the lead's SEAM design and
its amendment):

  profile     s16x1
  noise       sigma 1477/1, so that amplitude 1 sits at an efficiency of one half
  pulse       e0, injected every 128 frames starting at frame 64, so no two trials share a sample
  read at     the truth index + 63 (docs/model/conventions.md, row CV5; measured for e0 in
              tests/test_seam_conventions.py)
  threshold   D8's own, for a false-alarm probability of 0.01: Q^-1(0.01) * sigma * norm(coefficients),
              with sigma the square root of the noise law's exact variance (model.source.table_variance)
              and the coefficients the integers the core uses. Known, not measured from the run.
  noise alone the score at truth index - 1 of every trial reads 64 samples no pulse touches: one
              signal-free score a trial, counted against the same threshold
  amplitudes  1/2, 3/4, 1, 5/4, 3/2: efficiencies of about 0.12, 0.28, 0.50, 0.72 and 0.88
  seeds       amplitude number k (from 0) uses seed 2026112300 + k in the full run and 2026112400 + k
              in the gate's short form. One seed for each amplitude, so their noise is independent.
  judged by   stats.tolerance.check_efficiency: within 4 standard errors of D8's figure for the
              deflection of what was actually injected against the coefficients actually used

THE GATE runs a short form of amplitude 1: 4,000 injections. Its tolerance is wide, 0.032, and it
says so. Two controls on the same samples must fall outside it: the coefficients written the wrong
way round, and the score read one sample late.

THE FULL RUN is the lead's to make, not the gate's: 200,000 injections an amplitude, about six
minutes a core each.

    python tests/test_seam_e0.py --full --amplitude 0 --out a0.json      (and 1, 2, 3, 4)
    python tests/test_seam_e0.py --judge a0.json a1.json a2.json a3.json a4.json

Each part also holds the model against the statistics package on its own stream: every score that
is read must equal the float matched filter's with the same integer coefficients, exactly; and the
count with REAL coefficients, never quantised, is given beside the model's, which is the cost of
quantisation measured on the same stream.

WHAT THIS DOES NOT SHOW: anything about learning, real records, coloured noise, another pulse, a
second profile, or a filter longer than its pulse. It is one pulse, one noise level, one profile.
A pass here is evidence about sensitivity, by D8's authority. It is not evidence that any fabric is
correct: that is bit identity, which has another authority and is not in round 1.
"""
import hashlib
import json
import math
import os
import sys
from array import array

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:            # run as a script: the tree is not on the path yet
    sys.path.insert(0, ROOT)

from spec import constants as C  # noqa: E402
from model import inject, run, source, weights  # noqa: E402
from stats import matched as stat_matched  # noqa: E402
from stats import recovery, theory, tolerance  # noqa: E402

PROFILE = "s16x1"
SIGMA = (1477, 1)
PFA = 0.01
SPACING = 128
FIRST = 64
AMPLITUDES = ((1, 2), (3, 4), (1, 1), (5, 4), (3, 2))
FULL_N, FULL_SEED = 200000, 2026112300
GATE_N, GATE_SEED, GATE_AMPLITUDE = 4000, 2026112400, 2
E0 = C.PULSES["e0"]
TAPS = len(E0)
PASS = C.RECTIFIERS["pass"]


def facts(k):
    """Everything about amplitude number k that is known before a sample is drawn."""
    num, den = AMPLITUDES[k]
    blob = weights.matched_filter(PROFILE, E0, (1,))
    coeffs = list(weights.unpack(blob)["filters"][0][0])
    table = source.Noise(PROFILE, 0, SIGMA[0], SIGMA[1], 0).table
    var_num, var_den = source.table_variance(table)
    sigma = math.sqrt(var_num / var_den)
    injected = list(inject.scaled_pulse(C.PULSE_IDS["e0"], num, den))
    d = theory.deflection(coeffs, injected, sigma)
    exact = recovery.threshold_known_sigma(PFA, sigma, coeffs)
    return {"amplitude": [num, den], "blob": blob, "coeffs": coeffs, "sigma": sigma, "injected": injected,
            "d": d, "expected": theory.pd_matched(PFA, d), "threshold_exact": exact,
            # scores are integers: a score is above the real threshold exactly when it is above its floor
            "threshold": math.floor(exact)}


def schedule_for(k, n):
    num, den = AMPLITUDES[k]
    return [{"index": FIRST + SPACING * i, "pulse_id": C.PULSE_IDS["e0"], "amplitude_num": num, "amplitude_den": den}
            for i in range(n)]


def measure(k, n, seed, blob=None, keep=False, progress=None):
    """Run n trials of amplitude number k. Returns the scores that are read, and what else was seen.

    at_index[i]   the score at trial i's truth index + 63
    late[i]       the score one sample after it (for the control)
    noise[i]      the score at trial i's truth index - 1: 64 samples no pulse touches
    samples       the whole stream the detector saw, when `keep` is set
    """
    f = facts(k)
    length = SPACING * (n + 1)
    noise = source.Noise(PROFILE, seed, SIGMA[0], SIGMA[1], length)
    pairs, truth = run.scores(noise, schedule_for(k, n), length, blob or f["blob"])
    at_index, late, quiet = [], [], []
    samples = array("h") if keep else None
    flags = records = 0
    for (frame,), record in pairs:
        if keep:
            samples.append(frame)
        place = record["index"] % SPACING
        if place == SPACING - 1:
            at_index.append(record["score"])
        elif place == 0 and record["index"]:
            late.append(record["score"])
        elif place == FIRST - 1 and len(quiet) < n:
            quiet.append(record["score"])
        flags |= record["flags"]
        records += 1
        if progress and records % progress == 0:
            print("  %d of %d frames" % (records, length), flush=True)
    assert records == length and len(truth) == n
    assert [r["index"] for r in truth[:2]] == [FIRST, FIRST + SPACING]
    return {"n": n, "seed": seed, "length": length, "at_index": at_index[:n], "late": late[:n], "noise": quiet,
            "flags": flags, "samples": samples}


def count(scores, threshold):
    return sum(1 for s in scores if s > threshold)


def judge(found, n, d):
    return tolerance.check_efficiency(found, n, PFA, d)


# ------------------------------------------------------------ the gate's short form

_short = {}


def short():
    if not _short:
        f = facts(GATE_AMPLITUDE)
        got = measure(GATE_AMPLITUDE, GATE_N, GATE_SEED + GATE_AMPLITUDE, keep=True)
        _short.update(facts=f, got=got)
    return _short["facts"], _short["got"]


def test_seam_e0_the_setup_is_the_one_stated():
    f = facts(GATE_AMPLITUDE)
    assert f["amplitude"] == [1, 1] and f["injected"] == list(E0)
    # the coefficients are the pulse scaled so its peak, 970, is the largest the width holds, each rounded
    # to the nearest integer: worked here in exact fractions. e0 has no tie, so "nearest" is the whole rule.
    from fractions import Fraction
    peak = max(abs(p) for p in E0)
    assert peak == 970 and all((Fraction(p * C.COEFF_MAX, peak) % 1) != Fraction(1, 2) for p in E0)
    assert f["coeffs"] == [round(Fraction(p * C.COEFF_MAX, peak)) for p in E0]
    assert f["coeffs"][0] == 0 and f["coeffs"][1] == 135 and max(abs(c) for c in f["coeffs"]) == C.COEFF_MAX
    assert abs(f["sigma"] - 1477.0) < 1e-6, "the law's exact standard deviation is the sigma asked for, to a millionth"
    assert 0.49 < f["expected"] < 0.51, "amplitude 1 sits at one half"
    assert abs(f["d"] - 3436.78 / 1477.0) < 1e-3
    expected = [facts(k)["expected"] for k in range(len(AMPLITUDES))]
    assert expected == sorted(expected) and 0.10 < expected[0] < 0.14 and 0.86 < expected[4] < 0.90
    # trials are separate: the statistics package's own rule for this filter, pulse and lag
    assert SPACING >= recovery.minimum_spacing(TAPS, TAPS, TAPS - 1, 0) == 64
    assert FIRST - 1 >= TAPS - 1, "the first signal-free score has a full window of real samples"
    assert len({FULL_SEED + k for k in range(5)} | {GATE_SEED + k for k in range(5)}) == 10


def test_gate_statistics__seam_the_model_finds_the_pulse_as_often_as_d8_says_short_form():
    f, got = short()
    assert got["flags"] == 0, "no record of the run carries a flag: nothing overflowed, nothing settled"
    assert len(got["at_index"]) == len(got["noise"]) == GATE_N
    found = count(got["at_index"], f["threshold"])
    verdict = judge(found, GATE_N, f["d"])
    print("E0 short form: amplitude 1/1, seed %d: found %d of %d, efficiency %.4f, D8 %.4f, %+.2f se, tolerance %.4f, %s"
          % (got["seed"], found, GATE_N, verdict["measured"], verdict["expected"], verdict["z_score"],
             verdict["tolerance"], "INSIDE" if verdict["inside"] else "OUTSIDE"))
    assert verdict["inside"]
    assert 0.031 < verdict["tolerance"] < 0.032, "four standard errors at 4,000 injections: a wide check, stated"


def test_gate_statistics__seam_noise_alone_crosses_at_the_stated_rate_short_form():
    f, got = short()
    crossings = count(got["noise"], f["threshold"])
    verdict = tolerance.check_count(crossings, GATE_N, PFA)
    print("E0 short form: noise alone: %d of %d cross, rate %.5f, %+.2f se from %.2f"
          % (crossings, GATE_N, verdict["measured"], verdict["z_score"], PFA))
    assert verdict["inside"]


def test_gate_statistics__seam_every_score_read_equals_the_statistics_packages_exactly():
    """The model's integer core against the float matched filter of stats/, same coefficients, same
    samples. The float side says its scores are exact for this set; so any difference is an error."""
    f, got = short()
    assert stat_matched.scores_are_exact(PROFILE, f["coeffs"])
    x = np.frombuffer(got["samples"], dtype=np.int16).reshape(-1, 1)
    assert x.shape[0] == got["length"]
    theirs = stat_matched.matched_scores(x, PROFILE, f["coeffs"])
    at = FIRST + SPACING * np.arange(GATE_N)
    assert [int(v) for v in theirs[at + TAPS - 1].tolist()] == got["at_index"]
    assert [int(v) for v in theirs[at - 1].tolist()] == got["noise"]
    assert [int(v) for v in theirs[at + TAPS].tolist()] == got["late"]


def test_control_statistics__seam_coefficients_the_wrong_way_round_fall_outside():
    """Convention (b)'s mistake, at the seam, on the very samples the gate passed on."""
    f, got = short()
    wrong = weights.pack(PROFILE, [{0: tuple(reversed(f["coeffs"]))}], (1,), PASS, 1, 0)
    frames = [(v,) for v in got["samples"]]
    records, _none = run.detect(frames, [], got["length"], wrong)
    scores = [records[FIRST + SPACING * i + TAPS - 1]["score"] for i in range(GATE_N)]
    found = count(scores, f["threshold"])
    verdict = judge(found, GATE_N, f["d"])
    print("CONTROL E0 short form, coefficients reversed: found %d of %d, %+.1f se, %s"
          % (found, GATE_N, verdict["z_score"], "INSIDE" if verdict["inside"] else "OUTSIDE"))
    assert not verdict["inside"] and verdict["z_score"] < -8.0, "beyond the catch margin, not merely outside"


def test_control_statistics__seam_a_score_read_one_sample_late_falls_outside():
    """Row CV5's mistake: the same scores, read at the truth index + 64."""
    f, got = short()
    found = count(got["late"], f["threshold"])
    verdict = judge(found, GATE_N, f["d"])
    print("CONTROL E0 short form, read one sample late: found %d of %d, %+.1f se, %s"
          % (found, GATE_N, verdict["z_score"], "INSIDE" if verdict["inside"] else "OUTSIDE"))
    assert not verdict["inside"] and verdict["z_score"] < -8.0


def test_control_statistics__seam_a_run_of_nothing_is_refused_not_passed():
    f = facts(GATE_AMPLITUDE)
    with pytest.raises(Exception) as e:
        judge(0, 0, f["d"])
    assert type(e.value).__name__ == "StatRefusal"


# ------------------------------------------------------------ the full run, as a script

def full_part(k, n, seed, out):
    f = facts(k)
    print("E0 full run, part %d: amplitude %d/%d, %d injections, seed %d, sigma %d/%d, profile %s"
          % (k, f["amplitude"][0], f["amplitude"][1], n, seed, SIGMA[0], SIGMA[1], PROFILE), flush=True)
    got = measure(k, n, seed, keep=True, progress=SPACING * 20000)
    x = np.frombuffer(got["samples"], dtype=np.int16).reshape(-1, 1)
    at = FIRST + SPACING * np.arange(n)
    same = stat_matched.matched_scores(x, PROFILE, f["coeffs"])
    identical = ([int(v) for v in same[at + TAPS - 1].tolist()] == got["at_index"]
                 and [int(v) for v in same[at - 1].tolist()] == got["noise"])
    # the cost of quantisation, on the same stream: the pulse itself as the coefficients, never rounded
    real = np.asarray(E0, dtype=np.float64)
    real_scores = stat_matched.matched_scores(x, PROFILE, real)
    real_threshold = recovery.threshold_known_sigma(PFA, f["sigma"], real)
    real_d = theory.deflection(real, f["injected"], f["sigma"])
    real_hits = real_scores[at + TAPS - 1] > real_threshold
    model_hits = np.asarray(got["at_index"]) > f["threshold"]
    part = {"part": k, "amplitude": f["amplitude"], "n": n, "seed": seed, "profile": PROFILE, "sigma": list(SIGMA),
            "pfa": PFA, "spacing": SPACING, "length": got["length"],
            "sigma_exact": f["sigma"], "d": f["d"], "expected": f["expected"], "threshold": f["threshold"],
            "found": int(model_hits.sum()), "noise_crossings": count(got["noise"], f["threshold"]),
            "flags": got["flags"], "scores_identical_to_stats": bool(identical),
            "real_d": real_d, "real_found": int(real_hits.sum()),
            "model_only": int((model_hits & ~real_hits).sum()), "real_only": int((real_hits & ~model_hits).sum()),
            "stream_sha256": hashlib.sha256(x.tobytes()).hexdigest(), "spec_sha256": C.SPEC_SHA256}
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(part, fh, indent=1)
        fh.write("\n")
    print("wrote %s" % out)
    return part


def judge_parts(paths):
    parts = []
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            parts.append(json.load(fh))
    parts.sort(key=lambda p: p["part"])
    ok = True
    print("E0 in software: profile %s, sigma %d/%d, Pfa %.2f, the reference model as a matched filter for e0"
          % (parts[0]["profile"], parts[0]["sigma"][0], parts[0]["sigma"][1], parts[0]["pfa"]))
    print("  %-9s %-11s %-7s %-7s %-16s %-10s %-8s %-9s %s"
          % ("amplitude", "seed", "d", "D8", "found", "efficiency", "se from", "tolerance", "verdict"))
    for p in parts:
        v = tolerance.check_efficiency(p["found"], p["n"], p["pfa"], p["d"])
        ok = ok and v["inside"] and p["flags"] == 0 and p["scores_identical_to_stats"]
        print("  %-9s %-11d %-7.4f %-7.4f %-16s %-10.5f %+-8.2f %-9.5f %s"
              % ("%d/%d" % tuple(p["amplitude"]), p["seed"], p["d"], v["expected"],
                 "%d of %d" % (p["found"], p["n"]), v["measured"], v["z_score"], v["tolerance"],
                 "INSIDE" if v["inside"] else "OUTSIDE"))
    print("  noise alone, at the same threshold:")
    for p in parts:
        v = tolerance.check_count(p["noise_crossings"], p["n"], p["pfa"])
        ok = ok and v["inside"]
        print("  %-9s %d of %d cross, rate %.5f, %+.2f se from %.2f, %s"
              % ("%d/%d" % tuple(p["amplitude"]), p["noise_crossings"], p["n"], v["measured"], v["z_score"], p["pfa"],
                 "INSIDE" if v["inside"] else "OUTSIDE"))
    print("  against the statistics package, on each part's own stream:")
    for p in parts:
        print("  %-9s every score read identical: %s; flags seen: %d; with real coefficients %d found, the model %d;"
              " found by the model only %d, by the real set only %d"
              % ("%d/%d" % tuple(p["amplitude"]), "yes" if p["scores_identical_to_stats"] else "NO", p["flags"],
                 p["real_found"], p["found"], p["model_only"], p["real_only"]))
    print("== E0 SOFTWARE VERDICT: %s" % ("PASS, every amplitude inside D8's tolerance" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv):
    def value(flag, default=None):
        return argv[argv.index(flag) + 1] if flag in argv else default

    if "--judge" in argv:
        return judge_parts(argv[argv.index("--judge") + 1:])
    if "--full" in argv:
        k = int(value("--amplitude"))
        n = int(value("--n", FULL_N))
        full_part(k, n, int(value("--seed", FULL_SEED + k)), value("--out", "e0-part%d.json" % k))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Stage E1 in software: does a learner that starts blank reach the matched filter's efficiency?

The design D0, section 8: "The coefficients start blank. Labels come from the injector. Shows:
whether the learner reaches E0's efficiency, and how many labelled windows it takes. Does not
show: a gain over the classical detector. Matching E0 is the best possible result, by D8."

The learner is `learn/`: not an authority, and not judged bit for bit. What it hands the detector
is judged exactly: a blob the model's own rule quantised, swapped in at a named index, whose
records carry the epoch. What the detector then does is judged by `stats/`: D8 and its tolerance.

THE EXPERIMENT, fixed before any run (the round's ledger, 2026-11-23: LRN-A's design of 14:02 and
the lead's ruling of 14:08, which names the seeds):

  profile     s16x1; noise sigma 1477/1; pulse e0 at amplitude 1/1, where D8 gives one half
  a part      one stream under one seed, in three stretches:
                training      frames 0 .. A-1, A = 128 N: N trials, e0 every 128 frames from frame 64.
                              The detector runs BLANK (every coefficient 0), epoch 0.
                calibration   frames A .. B-1, B = A + 64 m1: no injection at all
                test          frames B .. L-1, L = B + 128 n: n trials, laid out as the training ones
  the learner the difference of two class means (learn/trainer.py) over the N truth records of the
              training stretch: 2 N labelled windows. It has no parameter but N.
  hand-over   when the detector's next output is A: quantised by model.weights.quantise, packed,
              written to the shadow, committed AT A. Records below A carry epoch 0; from A on, epoch 1.
  read at     records at or after A + 63 only, 64 apart, so no two read windows share a frame:
              a signal-free score at A + 63 + 64 g wherever no pulse touches its window (all of the
              calibration stretch, and the score at each test trial's truth index - 1), and each test
              trial's score at its truth index + 63
  threshold   MEASURED, after the weight change, from the m = m1 + n signal-free scores of epoch 1:
              stats.recovery.threshold_from_scores at a false-alarm probability of 0.01
  judged by   stats.tolerance.check_efficiency(found, n, pfa_effective, d, m): 4 standard errors, with
              the statistics' own term for a threshold measured from m scores
                check 2   d = the deflection of what was injected against the integers the learner produced
                check 3   d = the matched filter's deflection: "the learner reaches E0's efficiency"
                          means INSIDE here, and nothing else
  baseline    E0's matched filter on the same held-out frames, at its OWN threshold measured the same
              way: equal false-alarm rate, never equal threshold. Its scores are the statistics' float
              filter's, exact for integer coefficients; the model's core is held to them on the first
              256 test trials.
  full run    six parts: N = 16, 64, 256, 1024, 4096, 16384; m1 = 200,000; n = 100,000;
              part c under seed 2026112500 + c. THE MODEL THAT IS REPORTED IS THE LAST, part 5.
  short form  one part: N = 1024; m1 = 8,000; n = 4,000; seed 2026112600

THE COMPARISON RULES of D0's section 8 are held here, as the gate `comparison-rules`:
  1 the injection set of every part is committed, with its hash, in vectors/lrn-a/injection_sets.json;
    a run on any other set is refused before a frame is drawn
  2 the learner reads frames below A; every figure is read from records at or after A + 63
  3 a threshold belongs to one weight epoch and is refused for records of another; two models are
    compared only when each one's own threshold gives it the same count of the same signal-free scores
  4 a false-alarm rate below ten expected crossings in the scores it was measured on is labelled
  5 the reported model is the named one; a report of any other is refused

THE GATE runs the short form. Its tolerance is wide, 0.063, and it says so.

THE FULL RUN is the lead's to make, not the gate's: six to eight minutes a core for each part, which
is an estimate from the short form's rate (docs/model/lrn-a.md, row L19). No part has been run.

    python tests/test_lrn_a_e1.py --full --count 0 --out c0.json      (and 1, 2, 3, 4, 5)
    python tests/test_lrn_a_e1.py --judge c0.json c1.json c2.json c3.json c4.json c5.json

WHAT THIS DOES NOT SHOW: a gain over the matched filter; anything about coloured noise, drift,
another pulse, the second profile, a hidden layer, or a learner in fabric. A pass is evidence about
sensitivity, by D8's authority, for one pulse, one noise level, one sample format, in software. It
is not evidence that any fabric is correct.
"""
import hashlib
import json
import math
import os
import struct
import sys
from array import array
from fractions import Fraction

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:            # run as a script: the tree is not on the path yet
    sys.path.insert(0, ROOT)

from spec import constants as C  # noqa: E402
from model import inject, records, source, weights  # noqa: E402
from model import run as model_run  # noqa: E402
from model.detector import Core  # noqa: E402
from model.refusal import Refusal  # noqa: E402
from stats import matched as stat_matched  # noqa: E402
from stats import recovery, theory, tolerance  # noqa: E402
from stats.errors import StatRefusal  # noqa: E402
from learn import handover, trainer  # noqa: E402
from learn.errors import LearnRefusal  # noqa: E402

PROFILE = "s16x1"
SIGMA = (1477, 1)
PFA = 0.01
SPACING, FIRST = 128, 64
AMPLITUDE = (1, 1)
E0 = C.PULSES["e0"]
TAPS = len(E0)
STRIDE = TAPS                           # read windows are one filter length apart
COUNTS = (16, 64, 256, 1024, 4096, 16384)
NAMED = len(COUNTS) - 1                 # the model that is reported: the last
FULL_M_CAL, FULL_N, FULL_SEED = 200000, 100000, 2026112500
SHORT_TRAIN, SHORT_M_CAL, SHORT_N, SHORT_SEED = 1024, 8000, 4000, 2026112600
CORE_CHECK = 256                        # test trials on which the model's core is held to the baseline's scores
BLANK_EPOCH, LEARNED_EPOCH = 0, 1
FLOOR_CROSSINGS = 10                    # D0 row D10: fewer expected false alarms than this is an extrapolation


# ------------------------------------------------------------ the experiment's parts

def make_plan(name, part, trained_on, m_cal, n, seed):
    a = SPACING * trained_on
    b = a + STRIDE * m_cal
    return {"name": name, "part": part, "trained_on": trained_on, "labelled_windows": 2 * trained_on,
            "m_cal": m_cal, "n": n, "m": m_cal + n, "seed": seed, "A": a, "B": b, "length": b + SPACING * n}


def plan(part):
    """Everything about a part that is known before a sample is drawn. `part` is "short" or 0..5."""
    if part == "short":
        return make_plan("short", "short", SHORT_TRAIN, SHORT_M_CAL, SHORT_N, SHORT_SEED)
    if type(part) is not int or not 0 <= part < len(COUNTS):
        raise ValueError("there is no part %r: a part is \"short\" or 0..%d" % (part, len(COUNTS) - 1))
    return make_plan("full-%d" % part, part, COUNTS[part], FULL_M_CAL, FULL_N, FULL_SEED + part)


def schedule_for(p):
    """The part's injection set: its truth records, in order."""
    def record(index):
        return {"index": index, "pulse_id": C.PULSE_IDS["e0"], "amplitude_num": AMPLITUDE[0], "amplitude_den": AMPLITUDE[1]}
    return [record(FIRST + SPACING * i) for i in range(p["trained_on"])] + \
           [record(p["B"] + FIRST + SPACING * i) for i in range(p["n"])]


def free_positions(p):
    """The indexes of the held-out signal-free scores: the calibration stretch's, then one a test trial."""
    return np.concatenate([p["A"] + STRIDE - 1 + STRIDE * np.arange(p["m_cal"]),
                           p["B"] + FIRST - 1 + SPACING * np.arange(p["n"])])


def at_positions(p):
    """The index each test trial is read at: its truth index + TAPS - 1."""
    return p["B"] + FIRST + TAPS - 1 + SPACING * np.arange(p["n"])


_facts = {}


def facts():
    """What is known of the baseline and the pulse before any run: E0's own figures."""
    if not _facts:
        blob = weights.matched_filter(PROFILE, E0, (1,))
        coeffs = list(weights.unpack(blob)["filters"][0][0])
        var_num, var_den = source.table_variance(source.Noise(PROFILE, 0, SIGMA[0], SIGMA[1], 0).table)
        sigma = math.sqrt(var_num / var_den)
        injected = list(inject.scaled_pulse(C.PULSE_IDS["e0"], AMPLITUDE[0], AMPLITUDE[1]))
        _facts.update(blob=blob, coeffs=coeffs, sigma=sigma, injected=injected,
                      d=theory.deflection(coeffs, injected, sigma),
                      # scores are integers: a score is above the real threshold exactly when it is above its floor
                      threshold_known=math.floor(recovery.threshold_known_sigma(PFA, sigma, coeffs)))
    return _facts


# ------------------------------------------------------------ rule 1: the injection set

_committed = {}


def committed_sets():
    if not _committed:
        with open(os.path.join(ROOT, "vectors", "lrn-a", "injection_sets.json"), encoding="utf-8") as fh:
            _committed.update(json.load(fh)["sets"])
    return _committed


def independent_digest(schedule):
    """(SHA-256, count) of a list of truth records, by arithmetic that uses nothing of model/."""
    h = hashlib.sha256(b"undertone-records" + bytes([0]) + b"truth" + bytes([0]))
    for r in schedule:
        h.update(struct.pack("<QHiI", r["index"], r["pulse_id"], r["amplitude_num"], r["amplitude_den"]))
    return h.hexdigest(), len(schedule)


def check_injection_set(p, schedule, committed=None):
    """Refuse a schedule that is not the part's committed injection set. Returns its digest."""
    want = (committed_sets() if committed is None else committed).get(p["name"])
    if want is None:
        raise LearnRefusal("INJECTION_SET", "no injection set is committed for the part %r" % (p["name"],))
    got = records.digest("truth", schedule)
    if got != (want["sha256"], want["records"]):
        raise LearnRefusal("INJECTION_SET", "part %s: the schedule is %d records with digest %s; the committed set "
                           "is %d with %s" % (p["name"], got[1], got[0], want["records"], want["sha256"]))
    return got[0]


# ------------------------------------------------------------ the wiring, and one run

def wired(profile, frames, schedule, length, blob, hand=None):
    """The injector feeding one detector core, with a hand-over. Returns (pairs, truth).

    `model.run.scores` builds its core inside itself, so no swap can be made through it. This is
    the same wiring, in the same order, with one thing more: `hand` is None, or (when, make,
    commit_at), and when the core's next output is `when`, `make()` is called and the blob it
    returns is written to the shadow and committed at `commit_at`. A `make` that returns None
    hands nothing over. `make` is called before the frame at `when` is drawn from the stream.
    """
    core = Core(blob)
    injected, truth = inject.inject(profile, frames, schedule, length)
    return _wired_pairs(core, iter(injected), hand), truth


def _wired_pairs(core, injected, hand):
    # The detector's whole view of the world is `injected`. Truth is not in scope here.
    when = hand[0] if hand else None
    while True:
        if core.next_index == when:
            new = hand[1]()
            if new is not None:
                handover.hand_over(core, new, hand[2])
        try:
            frame = next(injected)
        except StopIteration:
            return
        yield frame, core.step(frame)


def measure(p, make_learner=None, schedule=None, commit_at=None, committed=None, progress=None):
    """Run one part through the model: the noise, the injector, one core, the learner, the hand-over.

    Returns what was seen: the records that are read, the samples of both periods, the learned
    blob, and what the hand-over did. `make_learner`, `schedule`, `commit_at` and `committed`
    are for the controls and for tests on a small part; the experiment passes none of them.
    """
    schedule = schedule_for(p) if schedule is None else schedule
    digest = check_injection_set(p, schedule, committed)          # rule 1: before a frame is drawn
    a, length = p["A"], p["length"]
    noise = source.Noise(PROFILE, p["seed"], SIGMA[0], SIGMA[1], length)
    train_samples, held = array("h"), array("h")
    state = {"refusal": None, "blob": None, "learner": None}

    def make():
        # Rule 2: the learner is handed the frames below A and the truth records below A, and nothing else.
        x = np.frombuffer(train_samples, dtype=np.int16).reshape(-1, 1)
        assert x.shape[0] == a and len(held) == 0
        learner = trainer.MeanDifference(1, TAPS) if make_learner is None else make_learner()
        trainer.train(x, [r["index"] for r in truth if r["index"] < a], TAPS, learner)
        state["learner"] = learner
        try:
            state["blob"] = handover.candidate_blob(PROFILE, learner.weights())
        except Refusal as e:                # the model's own refusal of the candidate: nothing is handed over
            state["refusal"] = e.name
        return state["blob"]

    pairs, truth = wired(PROFILE, noise, schedule, length, handover.blank_blob(PROFILE, TAPS),
                         (a, make, a if commit_at is None else commit_at))
    reads, flags, first_new, not_blank, seen = [], 0, None, 0, 0
    for (sample,), record in pairs:
        index = record["index"]
        if index < a:
            train_samples.append(sample)
            if record["score"] != 0:
                not_blank += 1
        else:
            held.append(sample)
            if (index - a) % STRIDE == STRIDE - 1:
                reads.append(record)
        if first_new is None and record["epoch"] != BLANK_EPOCH:
            first_new = index
        flags |= record["flags"]
        seen += 1
        if progress and seen % progress == 0:
            print("  %d of %d frames" % (seen, length), flush=True)
    assert seen == length and len(truth) == len(schedule)
    assert records.digest("truth", truth)[0] == digest, "the injector returned the schedule it was handed"
    return {"plan": p, "reads": reads, "train": np.frombuffer(train_samples, dtype=np.int16),
            "held": np.frombuffer(held, dtype=np.int16), "blob": state["blob"], "refusal": state["refusal"],
            "learner": state["learner"], "flags": flags, "first_new_epoch_index": first_new,
            "scores_not_zero_while_blank": not_blank, "injection_sha256": digest, "truth": truth}


# ------------------------------------------------------------ rules 2 and 3: thresholds and counts

def threshold_record(free_records, a, pfa=PFA):
    """A threshold measured from signal-free score records of ONE weight epoch, and that epoch.

    Rule 3: after every weight change the threshold is set again. The epoch field of the records
    is the witness: records of two epochs are refused, and the record made here names its epoch.
    Rule 2: a record the learner's training reached is refused.
    """
    epochs = sorted({r["epoch"] for r in free_records})
    if len(epochs) != 1:
        raise LearnRefusal("THRESHOLD_MIXED", "signal-free scores of %d weight epochs: %r" % (len(epochs), epochs))
    _held_out_only(free_records, a)
    t = recovery.threshold_from_scores(np.array([r["score"] for r in free_records], dtype=np.int64), pfa)
    t["epoch"] = epochs[0]
    return t


def _held_out_only(score_records, a):
    for r in score_records:
        if r["index"] < a + TAPS - 1:
            raise LearnRefusal("TRAINED_ON", "the record at %d reads frames below %d, which the learner trained on"
                               % (r["index"], a))


def hits(at_records, threshold, a):
    """Which injections are found: one bool for each record, strictly above the threshold.

    Refused: a record of another weight epoch than the threshold's (rule 3), and a record the
    learner's training reached (rule 2).
    """
    _held_out_only(at_records, a)
    for r in at_records:
        if r["epoch"] != threshold["epoch"]:
            raise LearnRefusal("THRESHOLD_STALE", "the record at %d carries epoch %d; the threshold was measured "
                               "under epoch %d" % (r["index"], r["epoch"], threshold["epoch"]))
    return np.array([r["score"] > threshold["threshold"] for r in at_records], dtype=bool)


def entry(name, free_records, at_records, a):
    """A model as the comparison takes it: its signal-free records, its own threshold, its hits."""
    t = threshold_record(free_records, a)
    return {"name": name, "free": free_records, "threshold": t, "hits": hits(at_records, t, a)}


def paired_arrays(free_a, threshold_a, hits_a, free_b, threshold_b, hits_b, slope_a, slope_b):
    """What model b loses against model a on the same injections, with BOTH thresholds measured.

    `stats.recovery.paired_cost` gives the cost and its error for two GIVEN thresholds. Here each
    was measured, from the same m signal-free positions. To first order a measured threshold's
    false-alarm probability is off by minus (its crossings at the true quantile, less the expected)
    over m, and the efficiency follows at the ROC's slope. The two models cross at mostly the same
    positions, so the difference of the two errors has variance

        ( slope_a^2 k_a (1 - k_a/m) + slope_b^2 k_b (1 - k_b/m) - 2 slope_a slope_b (both - k_a k_b / m) ) / m^2

    with k the positions where a model is above its own threshold and `both` where both are. With
    equal slopes and equal k that is slope^2 times the positions where exactly one crosses, over
    m^2. This is LRN-A's derivation, not the statistics package's; tests/test_lrn_a_paired.py
    calibrates it. It is first order in 1 / m and assumes Gaussian scores, as the package's own
    threshold term does.
    """
    cost = recovery.paired_cost(hits_a, hits_b)
    above_a, above_b = np.asarray(free_a) > threshold_a, np.asarray(free_b) > threshold_b
    m = int(above_a.size)
    k_a, k_b, both = int(above_a.sum()), int(above_b.sum()), int((above_a & above_b).sum())
    variance = (slope_a ** 2 * k_a * (1.0 - k_a / m) + slope_b ** 2 * k_b * (1.0 - k_b / m)
                - 2.0 * slope_a * slope_b * (both - k_a * k_b / m)) / (m * m)
    se_thresholds = math.sqrt(max(variance, 0.0))
    return {"n": cost["n"], "a_only": cost["a_only"], "b_only": cost["b_only"], "cost": cost["cost"],
            "se_pairs": cost["se"], "se_thresholds": se_thresholds, "se": math.hypot(cost["se"], se_thresholds),
            "noise_a_only": k_a - both, "noise_b_only": k_b - both, "noise_both": both, "m": m}


def compare_at_equal_rate(a, b, slope_a, slope_b):
    """Compare two models' hits. Refused unless each one's own threshold gives it the same count
    of the same signal-free positions: an equal false-alarm rate, never an equal threshold."""
    counts = []
    for e in (a, b):
        t = e["threshold"]
        above = sum(1 for r in e["free"] if r["score"] > t["threshold"])
        counts.append(above)
        if len(e["free"]) != t["m"] or above != t["k"]:
            raise LearnRefusal("UNEQUAL_FALSE_ALARM_RATE", "%s: %d of its %d signal-free scores are above the "
                               "threshold it is counted at; its own threshold gives %d of %d"
                               % (e["name"], above, len(e["free"]), t["k"], t["m"]))
    if (a["threshold"]["m"], a["threshold"]["k"]) != (b["threshold"]["m"], b["threshold"]["k"]) or \
            [r["index"] for r in a["free"]] != [r["index"] for r in b["free"]]:
        raise LearnRefusal("UNEQUAL_FALSE_ALARM_RATE", "%s and %s were not measured at the same signal-free positions "
                           "with the same count" % (a["name"], b["name"]))
    return paired_arrays(np.array([r["score"] for r in a["free"]], dtype=np.float64), a["threshold"]["threshold"], a["hits"],
                         np.array([r["score"] for r in b["free"]], dtype=np.float64), b["threshold"]["threshold"], b["hits"],
                         slope_a, slope_b)


# ------------------------------------------------------------ rule 4: the floor of row D10

def rate_floor(m):
    """The lowest false-alarm probability m signal-free scores support: ten expected crossings."""
    return FLOOR_CROSSINGS / m


def rate_label(pfa, m):
    return "COUNTED" if pfa * m >= FLOOR_CROSSINGS else "EXTRAPOLATION"


# ------------------------------------------------------------ the statistics' filter on the kept samples

def stat_scores_at_reads(held, coeffs, chunk=1 << 20):
    """The statistics' float filter on the held-out samples, at every read position (63, 127, ...
    from the held-out period's first frame). Exact for integer coefficients. Worked in pieces."""
    x = np.asarray(held)
    out = []
    for start in range(0, len(x), chunk):                       # `chunk` is a multiple of the stride
        low = max(0, start - (TAPS - 1))
        piece = stat_matched.matched_scores(x[low:start + chunk].reshape(-1, 1), PROFILE, coeffs)[start - low:]
        out.append(piece[STRIDE - 1::STRIDE])
    return np.concatenate(out)


def records_from(p, scores, epoch):
    """Score records for a filter whose scores at the read positions are `scores`: what a core
    holding that filter from index A on would have emitted there. Used for the baseline and for
    the controls' filters, whose scores come from the statistics' exact filter."""
    return [{"index": p["A"] + STRIDE - 1 + STRIDE * g, "epoch": epoch, "flags": 0, "score": int(s)}
            for g, s in enumerate(scores.tolist())]


def split(p, reads):
    """(signal-free records, at-index records) of a part's read records, each checked by its index."""
    cal, rest = reads[:p["m_cal"]], reads[p["m_cal"]:]
    free, at = cal + rest[0::2], rest[1::2]
    assert [r["index"] for r in free] == free_positions(p).tolist()
    assert [r["index"] for r in at] == at_positions(p).tolist()
    return free, at


def core_agrees(p, held, blob, scores):
    """Is the model's core, holding `blob`, equal to `scores` on the first CORE_CHECK test trials?"""
    start = p["B"] - p["A"]
    core = Core(blob)
    got = [core.step((int(v),))["score"] for v in held[start:start + CORE_CHECK * SPACING]][STRIDE - 1::STRIDE]
    return len(got) == 2 * CORE_CHECK and got == [int(v) for v in scores[p["m_cal"]:p["m_cal"] + 2 * CORE_CHECK].tolist()]


def peak_offset(blob):
    """Where the filter's largest score is for a lone, noise-free injection, less the truth index."""
    record = {"index": 64, "pulse_id": C.PULSE_IDS["e0"], "amplitude_num": AMPLITUDE[0], "amplitude_den": AMPLITUDE[1]}
    stream, _truth = inject.inject(PROFILE, [(0,)] * 256, [record], 256)
    scores = [r["score"] for r in Core(blob).run(stream)]
    return scores.index(max(scores)) - 64 if any(scores) else None


def evaluate(p, reads, held, blob, extra=None):
    """One part's record: everything the judge reads, from the read records and the kept samples."""
    f = facts()
    a, n, m = p["A"], p["n"], p["m"]
    free, at = split(p, reads)
    learned = entry("learned", free, at, a)
    t = learned["threshold"]
    coeffs = list(handover.coefficients(blob)[0]) if blob is not None else [0] * TAPS
    stat_learned = stat_scores_at_reads(held, coeffs)
    identical = stat_matched.scores_are_exact(PROFILE, coeffs) and \
        [int(v) for v in stat_learned.tolist()] == [r["score"] for r in reads]
    base_scores = stat_scores_at_reads(held, f["coeffs"])
    assert stat_matched.scores_are_exact(PROFILE, f["coeffs"])
    base_free, base_at = split(p, records_from(p, base_scores, BLANK_EPOCH))     # a frozen model: never swapped
    base = entry("matched", base_free, base_at, a)
    d_learned = theory.deflection(coeffs, f["injected"], f["sigma"]) if any(coeffs) else None
    part = {"part": p["part"], "name": p["name"], "trained_on": p["trained_on"], "labelled_windows": p["labelled_windows"],
            "seed": p["seed"], "profile": PROFILE, "sigma": list(SIGMA), "pfa": PFA, "amplitude": list(AMPLITUDE),
            "taps": TAPS, "spacing": SPACING, "A": a, "B": p["B"], "length": p["length"], "n": n, "m": m,
            "k": t["k"], "above": t["above"], "threshold": t["threshold"], "threshold_epoch": t["epoch"],
            "held_out_epochs": sorted({r["epoch"] for r in reads}), "rate_floor": rate_floor(m), "rate_label": rate_label(PFA, m),
            "coefficients": coeffs, "blob_sha256": weights.unpack(blob)["sha256"] if blob is not None else None,
            "d_learned": d_learned, "d_matched": f["d"], "found": int(learned["hits"].sum()),
            "base_threshold": base["threshold"]["threshold"], "base_above": base["threshold"]["above"],
            "base_found": int(base["hits"].sum()),
            "base_found_known_threshold": int((base_scores[p["m_cal"]:][1::2] > f["threshold_known"]).sum()),
            "scores_identical_to_stats": bool(identical),
            "core_equals_baseline_on_first_trials": bool(core_agrees(p, held, f["blob"], base_scores)),
            "peak_offset": peak_offset(blob) if blob is not None else None,
            "reported": p["part"] in ("short", NAMED), "spec_sha256": C.SPEC_SHA256}
    try:
        slope_learned = tolerance.roc_slope(t["pfa_effective"], d_learned if d_learned is not None else 0.0)
        pair = compare_at_equal_rate(base, learned, tolerance.roc_slope(t["pfa_effective"], f["d"]), slope_learned)
        part.update(base_only=pair["a_only"], learned_only=pair["b_only"], noise_base_only=pair["noise_a_only"],
                    noise_learned_only=pair["noise_b_only"], noise_both=pair["noise_both"], comparison_refused=None)
    except LearnRefusal as e:               # ties at a threshold: the two are not at an equal rate, and are not compared
        part.update(base_only=None, learned_only=None, noise_base_only=None, noise_learned_only=None, noise_both=None,
                    comparison_refused=e.name)
    part.update(extra or {})
    return part


def part_of(got):
    """The part record of a run made by `measure`."""
    learner = got["learner"]
    stream = hashlib.sha256(got["train"].tobytes() + got["held"].tobytes()).hexdigest()
    return evaluate(got["plan"], got["reads"], got["held"], got["blob"],
                    {"handover_refusal": got["refusal"], "first_new_epoch_index": got["first_new_epoch_index"],
                     "flags": got["flags"], "scores_not_zero_while_blank": got["scores_not_zero_while_blank"],
                     "learner_counts": list(learner.counts), "injection_sha256": got["injection_sha256"],
                     "stream_sha256": stream})


# ------------------------------------------------------------ the result, and the verdict

def result(part):
    """What a part's numbers say: the four checks of the design's item 8, from the part alone."""
    f = facts()
    n, m, k = part["n"], part["m"], part["k"]
    pfa_effective = (k + 1) / (m + 1)
    out = {"measured": part["found"] / n, "pfa_effective": pfa_effective}
    for name, found, pfa, d, scores in (("own", part["found"], pfa_effective, part["d_learned"], m),
                                        ("e0", part["found"], pfa_effective, f["d"], m),
                                        ("baseline", part["base_found"], pfa_effective, f["d"], m),
                                        ("baseline_known", part["base_found_known_threshold"], PFA, f["d"], None)):
        try:
            out[name] = tolerance.check_efficiency(found, n, pfa, d, scores) if d is not None else None
        except StatRefusal as e:            # an efficiency the statistics will not judge
            out[name] = None
            out[name + "_refused"] = e.name
    out["paired"] = None
    counted = all(type(part.get(c)) is int for c in ("base_only", "learned_only", "noise_base_only", "noise_learned_only", "noise_both"))
    if counted and part["d_learned"] is not None and part["base_only"] + part["learned_only"] <= n:
        a_only, b_only = part["base_only"], part["learned_only"]
        diff = a_only - b_only
        se_pairs = math.sqrt(a_only + b_only - diff * diff / n) / n
        s_a, s_b = tolerance.roc_slope(pfa_effective, f["d"]), tolerance.roc_slope(pfa_effective, part["d_learned"])
        both = part["noise_both"]
        k_a, k_b = both + part["noise_base_only"], both + part["noise_learned_only"]
        variance = (s_a ** 2 * k_a * (1 - k_a / m) + s_b ** 2 * k_b * (1 - k_b / m) - 2 * s_a * s_b * (both - k_a * k_b / m)) / (m * m)
        se = math.hypot(se_pairs, math.sqrt(max(variance, 0.0)))
        predicted = theory.pd_matched(pfa_effective, f["d"]) - theory.pd_matched(pfa_effective, part["d_learned"])
        out["paired"] = {"cost": diff / n, "se_pairs": se_pairs, "se_thresholds": math.sqrt(max(variance, 0.0)), "se": se,
                         "predicted": predicted, "z_score": (diff / n - predicted) / se if se > 0 else 0.0}
    return out


def holds(part, r=None):
    """The verdict's conditions for one part: everything but 'the parts are the stated experiment'."""
    r = result(part) if r is None else r
    ok = part["flags"] == 0 and part["scores_identical_to_stats"] and part["core_equals_baseline_on_first_trials"]
    ok = ok and r["own"] is not None and r["own"]["inside"] and r["baseline"] is not None and r["baseline"]["inside"]
    if part["reported"]:
        ok = ok and r["e0"] is not None and r["e0"]["inside"]
    return bool(ok)


def report(parts, which=NAMED):
    """The reported model's part and result. Rule 5: the model reported is the one named before
    the run, the last; asking for any other is refused."""
    if which != NAMED:
        raise LearnRefusal("NOT_THE_NAMED_MODEL", "part %r was asked for; the model named before the run is part %d, "
                           "trained on %d truth records" % (which, NAMED, COUNTS[NAMED]))
    named = [p for p in parts if p["part"] == NAMED]
    if len(named) != 1:
        raise LearnRefusal("NOT_THE_NAMED_MODEL", "%d parts are part %d" % (len(named), NAMED))
    return named[0], result(named[0])


def not_as_stated(parts, parts_wanted=None):
    """Why these parts are not the experiment this file states: a list of reasons, empty when they are.

    Each part is held to what `plan` and `facts` give for it now, and to itself: its blob's hash and
    its deflection are worked again from the coefficients it carries, its counts must add up, and
    its injection set's digest must be the committed one. The set is held to one part a count, each
    under its own seed, on its own stream.

    What it takes on trust, stated: the counts themselves. Nothing here recomputes a count from a
    stream. A part file edited to counts that are consistent with one another and inside the
    tolerance would be judged as those counts. Running a part again is the check for that.
    """
    f = facts()
    wanted = list(range(len(COUNTS))) if parts_wanted is None else parts_wanted
    reasons = []
    if sorted(str(p["part"]) for p in parts) != sorted(str(w) for w in wanted):
        reasons.append("the parts are %s, not exactly %s" % (sorted(str(p["part"]) for p in parts), wanted))
    for part in parts:
        k = part["part"]
        if k not in wanted:
            continue
        p = plan(k)
        want_k = int(Fraction(PFA) * p["m"])
        for name, want in (("seed", p["seed"]), ("trained_on", p["trained_on"]), ("labelled_windows", p["labelled_windows"]),
                           ("A", p["A"]), ("B", p["B"]), ("length", p["length"]), ("n", p["n"]), ("m", p["m"]),
                           ("k", want_k), ("above", want_k), ("base_above", want_k), ("profile", PROFILE),
                           ("sigma", list(SIGMA)), ("pfa", PFA), ("amplitude", list(AMPLITUDE)), ("taps", TAPS),
                           ("spacing", SPACING), ("spec_sha256", C.SPEC_SHA256), ("handover_refusal", None),
                           ("first_new_epoch_index", p["A"]), ("held_out_epochs", [LEARNED_EPOCH]),
                           ("threshold_epoch", LEARNED_EPOCH), ("scores_not_zero_while_blank", 0),
                           ("learner_counts", [p["trained_on"], p["trained_on"]]), ("comparison_refused", None),
                           ("injection_sha256", committed_sets()[p["name"]]["sha256"]),
                           ("reported", k in ("short", NAMED)), ("rate_label", rate_label(part.get("pfa", PFA), p["m"]))):
            if part.get(name, "missing") != want:
                reasons.append("part %s: %s is %r, the experiment's is %r" % (k, name, part.get(name, "missing"), want))
        if part.get("rate_label") == "COUNTED" and part.get("pfa", PFA) * p["m"] < FLOOR_CROSSINGS:
            reasons.append("part %s: a false-alarm probability of %r is below the floor of %d crossings in %d scores, "
                           "and is called counted" % (k, part.get("pfa"), FLOOR_CROSSINGS, p["m"]))
        coeffs = part.get("coefficients")
        try:
            blob = weights.pack(PROFILE, [{0: tuple(coeffs)}], (1,), C.RECTIFIERS["pass"], 1, 0)
            sha, d = weights.unpack(blob)["sha256"], theory.deflection(coeffs, f["injected"], f["sigma"])
        except (Refusal, StatRefusal, TypeError):
            sha, d = None, None
        if sha is None or len(coeffs) != TAPS or part.get("blob_sha256") != sha:
            reasons.append("part %s: its blob hash is not the hash of the coefficients it carries" % k)
        if d is None or part.get("d_learned") is None or abs(part["d_learned"] - d) > 1e-12:
            reasons.append("part %s: d_learned is %r; its coefficients give %r" % (k, part.get("d_learned"), d))
        if abs(part.get("d_matched", 0.0) - f["d"]) > 1e-12:
            reasons.append("part %s: d_matched is %r, the experiment's is %r" % (k, part.get("d_matched"), f["d"]))
        # found by the learned filter = found by the matched filter, less those only it found, plus those only the learned one found
        counts = [part.get(name) for name in ("found", "base_found", "base_only", "learned_only",
                                              "noise_base_only", "noise_learned_only", "noise_both")]
        if not all(type(c) is int and c >= 0 for c in counts) or counts[0] != counts[1] - counts[2] + counts[3] \
                or counts[4] != counts[5] or counts[4] + counts[6] != want_k:
            reasons.append("part %s: its counts do not add up: found %r, the matched filter %r, by the matched filter "
                           "only %r, by the learned one only %r; signal-free crossings by one only %r and %r, by both %r"
                           % ((k,) + tuple(counts)))
    if len({p.get("stream_sha256") for p in parts}) != len(parts):
        reasons.append("two parts were run on the same stream")
    return reasons


def judge_parts(paths):
    parts = []
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            parts.append(json.load(fh))
    parts.sort(key=lambda p: str(p["part"]))
    reasons = not_as_stated(parts)
    ok = not reasons
    f = facts()
    print("E1 in software: profile %s, sigma %d/%d, Pfa %.2f, amplitude %d/%d; the matched filter's d is %.4f"
          % (PROFILE, SIGMA[0], SIGMA[1], PFA, AMPLITUDE[0], AMPLITUDE[1], f["d"]))
    print("  the curve: the learned filter on held-out injections, at its own measured threshold")
    print("  %-7s %-8s %-11s %-8s %-16s %-10s %-22s %-22s %s"
          % ("records", "windows", "seed", "d", "found", "efficiency", "against its own D8", "against E0's D8", "tolerance"))
    rows = []
    for part in parts:
        r = result(part)
        rows.append((part, r))
        ok = ok and holds(part, r)

        def side(v):
            return "REFUSED by the statistics" if v is None else \
                "%.4f %+.2f se %s" % (v["expected"], v["z_score"], "INSIDE" if v["inside"] else "OUTSIDE")
        print("  %-7d %-8d %-11d %-8s %-16s %-10.5f %-22s %-22s %s"
              % (part["trained_on"], part["labelled_windows"], part["seed"],
                 "none" if part["d_learned"] is None else "%.4f" % part["d_learned"],
                 "%d of %d" % (part["found"], part["n"]), r["measured"], side(r["own"]), side(r["e0"]),
                 "none" if r["e0"] is None else "%.5f" % r["e0"]["tolerance"]))
    print("  the baseline, E0's matched filter, on each part's held-out stream:")
    for part, r in rows:
        def said(v):
            return "REFUSED by the statistics" if v is None else "%+.2f se, %s" % (v["z_score"], "INSIDE" if v["inside"] else "OUTSIDE")
        print("  %-7d measured threshold: %d of %d, %s; D8's own threshold: %d, %s"
              % (part["trained_on"], part["base_found"], part["n"], said(r["baseline"]),
                 part["base_found_known_threshold"], said(r["baseline_known"])))
    print("  the paired cost against the baseline, each at its own threshold (reported; not in the verdict):")
    for part, r in rows:
        pr = r["paired"]
        print("  %-7d %s" % (part["trained_on"], "not compared: %s" % part.get("comparison_refused") if pr is None else
                             "cost %+.5f, se %.5f (pairs %.5f, thresholds %.5f); its coefficients predict %+.5f: %+.2f se"
                             % (pr["cost"], pr["se"], pr["se_pairs"], pr["se_thresholds"], pr["predicted"], pr["z_score"])))
    print("  the instrument, on each part:")
    for part, _r in rows:
        print("  %-7d flags %s; every score read identical to the statistics': %s; the core equal to the baseline on the "
              "first %d trials: %s; peak at truth + %s; signal-free scores %d, floor %.2g, a rate of %.2f is %s"
              % (part["trained_on"], part.get("flags"), "yes" if part["scores_identical_to_stats"] else "NO", CORE_CHECK,
                 "yes" if part["core_equals_baseline_on_first_trials"] else "NO", part.get("peak_offset"), part["m"],
                 part.get("rate_floor", 0.0), part["pfa"], part.get("rate_label")))
    inside = [part["trained_on"] for part, r in rows if r["e0"] is not None and r["e0"]["inside"]]
    outside = [part["trained_on"] for part, r in rows if r["e0"] is None or not r["e0"]["inside"]]
    takes = [c for c in inside if all(c > o for o in outside)]
    print("  one reading of the curve, at this tolerance's resolution: every count from %s truth records on is inside "
          "the tolerance of E0's figure" % (min(takes) if takes else "none of these"))
    print("  the parts against the experiment as this file states it: %s"
          % ("one part a count, each under its own seed and its committed injection set" if not reasons else "NOT AS STATED"))
    for reason in reasons:
        print("    " + reason)
    try:
        named, r = report(parts)
        e0 = r["e0"]
        print("  THE REPORTED MODEL, named before the run: part %d, %d truth records, %d labelled windows: %d of %d, "
              "efficiency %.5f; E0's figure %.5f; %s"
              % (named["part"], named["trained_on"], named["labelled_windows"], named["found"], named["n"], r["measured"],
                 e0["expected"] if e0 else float("nan"),
                 "REFUSED by the statistics" if e0 is None else
                 "%+.2f se, tolerance %.5f, %s" % (e0["z_score"], e0["tolerance"], "INSIDE" if e0["inside"] else "OUTSIDE")))
    except LearnRefusal as e:
        ok = False
        print("  THE REPORTED MODEL: refused, %s" % e)
    print("== E1 SOFTWARE VERDICT: %s" % ("PASS, the reported model is inside the tolerance of E0's efficiency" if ok else "FAIL"))
    return 0 if ok else 1


def full_part(count, out):
    p = plan(count)
    print("E1 full run, part %d: %d truth records (%d labelled windows), %d calibration scores, %d test injections, "
          "seed %d, %d frames" % (count, p["trained_on"], p["labelled_windows"], p["m_cal"], p["n"], p["seed"], p["length"]),
          flush=True)
    part = part_of(measure(p, progress=SPACING * 20000))
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(part, fh, indent=1)
        fh.write("\n")
    print("wrote %s" % out)
    return part


def main(argv):
    def value(flag, default=None):
        return argv[argv.index(flag) + 1] if flag in argv else default

    if "--judge" in argv:
        return judge_parts(argv[argv.index("--judge") + 1:])
    if "--full" in argv:
        count = int(value("--count"))
        full_part(count, value("--out", "e1-part%d.json" % count))
        return 0
    print(__doc__)
    return 2


# ------------------------------------------------------------ the gate's short form

_short = {}


def short():
    if not _short:
        got = measure(plan("short"))
        _short.update(got=got, part=part_of(got))
    return _short["got"], _short["part"]


def control_part(coeffs_blob, epoch=LEARNED_EPOCH, extra=None):
    """The short form's part for another filter: its scores on the kept held-out samples by the
    statistics' exact filter, as records of the epoch a core swapped at A would give them."""
    got, _part = short()
    p = got["plan"]
    coeffs = list(handover.coefficients(coeffs_blob)[0]) if coeffs_blob is not None else [0] * TAPS
    reads = records_from(p, stat_scores_at_reads(got["held"], coeffs), epoch)
    base = {"handover_refusal": None, "first_new_epoch_index": p["A"], "flags": 0, "scores_not_zero_while_blank": 0,
            "learner_counts": [p["trained_on"]] * 2, "injection_sha256": got["injection_sha256"], "stream_sha256": "control"}
    base.update(extra or {})
    return evaluate(p, reads, got["held"], coeffs_blob, base)


def test_lrn_a_e1_the_setup_is_the_one_stated():
    p = plan("short")
    assert (p["trained_on"], p["labelled_windows"], p["A"], p["B"], p["length"], p["n"], p["m"]) == \
        (1024, 2048, 131072, 643072, 1155072, 4000, 12000)
    full = [plan(c) for c in range(len(COUNTS))]
    assert [q["trained_on"] for q in full] == [16, 64, 256, 1024, 4096, 16384] and NAMED == 5 and full[NAMED]["trained_on"] == 16384
    assert [q["length"] for q in full] == [25600000 + 128 * c for c in COUNTS]
    assert sum(q["length"] for q in full) == 156395520
    assert all((q["n"], q["m"], q["seed"]) == (100000, 300000, 2026112500 + q["part"]) for q in full)
    assert int(Fraction(PFA) * 12000) == 120 and int(Fraction(PFA) * 300000) == 3000
    f = facts()
    assert f["injected"] == list(E0) and abs(f["d"] - 3436.78 / 1477.0) < 1e-3
    # the tolerances the docstring states, from the statistics' own function
    short_t = tolerance.tolerance(121 / 12001, f["d"], 4000, 12000)
    full_t = tolerance.tolerance(3001 / 300001, f["d"], 100000, 300000)
    assert 0.0627 < short_t["tolerance"] < 0.0629 and 0.01257 < full_t["tolerance"] < 0.01259
    assert short_t["se_threshold"] > short_t["se_binomial"] and full_t["se_threshold"] > full_t["se_binomial"], \
        "the measured threshold is the larger part of the tolerance, at both sizes"
    # trials are separate, by the statistics package's own rule; read windows are a filter length apart
    assert SPACING >= recovery.minimum_spacing(TAPS, TAPS, TAPS - 1, 0) == 64 and STRIDE == TAPS
    # seventeen seeds with E0's ten, and no two streams share a word of the generator's cycle (mod-a.md, limit 7)
    seeds = [FULL_SEED + c for c in range(6)] + [SHORT_SEED] + [2026112300 + k for k in range(5)] + [2026112400 + k for k in range(5)]
    assert len(set(seeds)) == 17
    inverse = pow(source.GAMMA, -1, 1 << 64)
    apart = min(min((x - y) * inverse % (1 << 64), (y - x) * inverse % (1 << 64)) for x in seeds for y in seeds if x != y)
    assert apart > 1 << 57 and max(q["length"] for q in full) < 1 << 25


def test_gate_comparison_rules__rule_1_every_injection_set_is_the_committed_one_by_two_implementations():
    sets = committed_sets()
    assert sorted(sets) == ["full-0", "full-1", "full-2", "full-3", "full-4", "full-5", "short"]
    for part in ["short"] + list(range(len(COUNTS))):
        p = plan(part)
        schedule = schedule_for(p)
        want = sets[p["name"]]
        assert (want["truth_records_trained_on"], want["calibration_scores"], want["test_trials"]) == (p["trained_on"], p["m_cal"], p["n"])
        assert independent_digest(schedule) == (want["sha256"], want["records"]) == records.digest("truth", schedule)
        assert schedule[-1]["index"] == want["last_index"] == p["length"] - TAPS
        if part in ("short", NAMED):        # the run's own check, on the two sets a run of this file's forms starts from
            assert check_injection_set(p, schedule) == want["sha256"]
    assert struct.pack("<QHiI", 64, 0, 1, 1).hex() == "400000000000000000000100000001000000"
    assert len({s["sha256"] for s in sets.values()}) == 7


def test_control_comparison_rules__rule_1_a_run_on_another_injection_set_is_refused_before_a_frame_is_drawn(monkeypatch):
    p = plan("short")
    good = schedule_for(p)

    def changed(i, **fields):
        return good[:i] + [dict(good[i], **fields)] + good[i + 1:]

    others = {
        "one amplitude changed": changed(2000, amplitude_num=2),
        "one index a sample later": changed(3, index=good[3]["index"] + 1),
        "one index a sample earlier": changed(3, index=good[3]["index"] - 1),
        "one injection dropped": good[:-1],
        "one injection added": good + [dict(good[-1], index=good[-1]["index"] + SPACING)],
        "another part's set": schedule_for(plan(3)),
        "the test trials each 64 frames late": good[:p["trained_on"]] + [dict(r, index=r["index"] + 64) for r in good[p["trained_on"]:]],
        "no injection at all": [],
    }

    class NoFrame:
        def __init__(self, *args):
            raise AssertionError("a frame source was made: the run was not refused before a frame was drawn")

    monkeypatch.setattr(source, "Noise", NoFrame)
    for what, schedule in others.items():
        with pytest.raises(LearnRefusal) as e:
            measure(p, schedule=schedule)
        print("CONTROL rule 1, %s: refused, %s" % (what, str(e.value)[:150]))
        assert e.value.name == "INJECTION_SET", what
    # the check is of the set, not of the count alone: a set of the right count and another digest is refused
    assert len(others["one amplitude changed"]) == len(good)
    # and the same call with the committed set gets as far as making its frame source
    with pytest.raises(AssertionError, match="a frame source was made"):
        measure(p)
    with pytest.raises(LearnRefusal) as e:
        measure(make_plan("unknown", "short", 2, 2, 2, 1))
    assert e.value.name == "INJECTION_SET"


def test_gate_comparison_rules__rule_2_every_figure_is_read_from_the_held_out_stretches():
    got, part = short()
    p = got["plan"]
    a = p["A"]
    assert len(got["train"]) == a and len(got["held"]) == p["length"] - a
    assert got["learner"].counts == [p["trained_on"]] * 2, "the learner read every training record's two windows, and no other"
    assert max(r["index"] for r in got["truth"] if r["index"] < a) + TAPS == a, "the last training pulse ends at frame A - 1"
    indexes = [r["index"] for r in got["reads"]]
    assert min(indexes) == a + TAPS - 1 and len(indexes) == p["m_cal"] + 2 * p["n"]
    assert all(y - x == STRIDE for x, y in zip(indexes, indexes[1:])), "no two read windows share a frame"
    # the signal-free positions are the statistics package's own, for the whole stream, cut at A + 63
    theirs = recovery.signal_free_indexes(p["length"], TAPS, [r["index"] for r in got["truth"]], TAPS)
    assert theirs[theirs >= a + TAPS - 1].tolist() == sorted(free_positions(p).tolist()) and len(free_positions(p)) == p["m"]
    assert at_positions(p).tolist() == [r["index"] + TAPS - 1 for r in got["truth"] if r["index"] >= a]
    assert part["held_out_epochs"] == [LEARNED_EPOCH] and part["threshold_epoch"] == LEARNED_EPOCH


def test_control_comparison_rules__rule_2_a_figure_from_frames_the_learner_trained_on_is_refused():
    got, _part = short()
    p = got["plan"]
    a = p["A"]
    free, at = split(p, got["reads"])
    t = threshold_record(free, a)
    for low in (a + TAPS - 2, a - 1, FIRST + TAPS - 1):               # one frame of training in the window; all of it; a training trial
        reached = dict(at[0], index=low)
        for call in (lambda: hits([reached] + at[1:], t, a), lambda: threshold_record([reached] + free[1:], a)):
            with pytest.raises(LearnRefusal) as e:
                call()
            assert e.value.name == "TRAINED_ON", low
    assert hits([dict(at[0], index=a + TAPS - 1)], t, a).shape == (1,), "the first record wholly of held-out frames is taken"
    # and the other direction: the learner handed a truth record of the held-out stretches refuses it
    with pytest.raises(LearnRefusal) as e:
        trainer.train(got["train"].astype(np.int64).reshape(-1, 1), [FIRST, p["B"] + FIRST], TAPS)
    print("CONTROL rule 2: a held-out truth record handed to the trainer: %s" % str(e.value)[:140])
    assert e.value.name == "WINDOW_OUTSIDE_PERIOD"


def one_tap_blob():
    """The lead's control filter: one tap of 1, the rest 0, as the hand-over quantises it."""
    return handover.candidate_blob(PROFILE, ((1,) + (0,) * (TAPS - 1),))


def test_lrn_a_e1_a_score_equal_to_its_threshold_is_not_found_and_not_a_false_alarm():
    """Convention (c): a crossing is strictly greater. Held here for the two places E1 counts."""
    a = 1000
    free = [{"index": a + 63 + 64 * g, "epoch": 1, "flags": 0, "score": s} for g, s in enumerate([5, 7, 7, 9, 1])]
    t = {"threshold": 7.0, "m": 5, "k": 1, "above": 1, "pfa_effective": 2 / 6, "epoch": 1}
    at = [{"index": a + 9000 + 128 * i, "epoch": 1, "flags": 0, "score": s} for i, s in enumerate([6, 7, 8])]
    assert hits(at, t, a).tolist() == [False, False, True]
    e = {"name": "x", "free": free, "threshold": t, "hits": hits(at, t, a)}
    assert compare_at_equal_rate(e, e, 1.0, 1.0)["noise_both"] == 1, "one score is above 7; the two equal to it are not"
    with pytest.raises(LearnRefusal) as refusal:      # counted at 6.5, three are above: not the rate the threshold states
        compare_at_equal_rate(e, dict(e, threshold=dict(t, threshold=6.5)), 1.0, 1.0)
    assert refusal.value.name == "UNEQUAL_FALSE_ALARM_RATE"


def test_gate_comparison_rules__rule_3_each_model_has_its_own_threshold_and_the_same_false_alarm_rate():
    got, part = short()
    p = got["plan"]
    assert part["k"] == part["above"] == part["base_above"] == 120 and part["m"] == 12000
    assert part["threshold"] != part["base_threshold"], "two models, two thresholds"
    assert part["comparison_refused"] is None
    assert part["noise_base_only"] == part["noise_learned_only"] and part["noise_base_only"] + part["noise_both"] == 120
    assert part["found"] == part["base_found"] - part["base_only"] + part["learned_only"]
    print("E1 short form, rule 3: thresholds %.0f (learned) and %.0f (matched), each with 120 of 12,000 signal-free scores "
          "above; %d of those positions are above for both" % (part["threshold"], part["base_threshold"], part["noise_both"]))
    assert part["rate_label"] == "COUNTED" and part["threshold_epoch"] == LEARNED_EPOCH


def test_control_comparison_rules__rule_3_a_comparison_at_an_equal_threshold_is_refused():
    got, _part = short()
    p = got["plan"]
    a = p["A"]
    f = facts()
    slope = tolerance.roc_slope(121 / 12001, f["d"])

    def model(name, coeffs):
        free, at = split(p, records_from(p, stat_scores_at_reads(got["held"], coeffs), LEARNED_EPOCH))
        return dict(entry(name, free, at, a), at=at)

    # A filter that cannot share a threshold with the matched one: its first half, the rest zeros. Its scores are
    # smaller, so the matched filter's threshold is far too high for it and its own far too low for the matched filter.
    half_coeffs = f["coeffs"][:TAPS // 2] + [0] * (TAPS // 2)
    ratio = math.sqrt(sum(c * c for c in half_coeffs) / sum(c * c for c in f["coeffs"]))
    assert ratio < 0.85, "the two filters' noise levels differ by more than any spacing of scores: %.3f" % ratio
    matched, half = model("matched", f["coeffs"]), model("its first half", half_coeffs)
    learned = dict(entry("learned", *split(p, got["reads"]), a), at=split(p, got["reads"])[1])
    assert compare_at_equal_rate(matched, half, slope, slope)["m"] == 12000, "each at its own threshold, they are compared"
    assert compare_at_equal_rate(matched, learned, slope, slope)["m"] == 12000
    for mine, theirs in ((half, matched), (matched, half), (learned, matched), (matched, learned)):
        shared = dict(mine, threshold=dict(theirs["threshold"]), hits=hits(mine["at"], theirs["threshold"], a))
        above = sum(1 for r in mine["free"] if r["score"] > theirs["threshold"]["threshold"])
        print("CONTROL rule 3: %s counted at the threshold of %s: %d of 12,000 of its signal-free scores are above it, where "
              "an equal rate is 120; it would have found %d of 4,000 there, and %d at its own"
              % (mine["name"], theirs["name"], above, int(shared["hits"].sum()), int(mine["hits"].sum())))
        if above == 120:        # D0: "a threshold that happens to give both models the same rate" is no control; say so
            assert "its first half" not in (mine["name"], theirs["name"])
            print("CONTROL rule 3: that pair's shared threshold happens to give the same rate: it shows nothing, and is not asserted")
            continue
        with pytest.raises(LearnRefusal) as e:
            compare_at_equal_rate(theirs, shared, slope, slope)
        assert e.value.name == "UNEQUAL_FALSE_ALARM_RATE"
        with pytest.raises(LearnRefusal):
            compare_at_equal_rate(shared, theirs, slope, slope)
    # the pair that cannot coincide, in both directions, by a margin of two each way
    assert sum(1 for r in half["free"] if r["score"] > matched["threshold"]["threshold"]) < 60
    assert sum(1 for r in matched["free"] if r["score"] > half["threshold"]["threshold"]) > 240
    # and other signal-free positions, or another count of them, are not an equal rate either
    fewer = dict(matched, free=matched["free"][:-1])
    with pytest.raises(LearnRefusal) as e:
        compare_at_equal_rate(fewer, half, slope, slope)
    assert e.value.name == "UNEQUAL_FALSE_ALARM_RATE"
    moved = dict(half, free=[dict(r, index=r["index"] + STRIDE) for r in half["free"]])
    with pytest.raises(LearnRefusal) as e:
        compare_at_equal_rate(matched, moved, slope, slope)
    assert e.value.name == "UNEQUAL_FALSE_ALARM_RATE"


def test_control_comparison_rules__rule_3_a_threshold_kept_after_the_weights_changed_is_refused():
    got, _part = short()
    p = got["plan"]
    a = p["A"]
    free, at = split(p, got["reads"])
    before = [dict(r, epoch=BLANK_EPOCH, score=0) for r in free]       # what the blank detector's signal-free scores are
    kept = recovery.threshold_from_scores(np.zeros(len(before)), PFA)
    kept["epoch"] = BLANK_EPOCH
    assert threshold_record(before, a)["threshold"] == kept["threshold"] == 0.0
    with pytest.raises(LearnRefusal) as e:
        hits(at, kept, a)
    print("CONTROL rule 3, the blank detector's threshold kept for the learned filter's records: %s" % str(e.value)[:130])
    assert e.value.name == "THRESHOLD_STALE"
    assert int((np.array([r["score"] for r in at]) > kept["threshold"]).sum()) > 0.9 * len(at), \
        "the fault matters: at the stale threshold of 0 nearly every injection would count as found"
    # one record of another epoch among the at-index records is enough, and so is one among the signal-free ones
    with pytest.raises(LearnRefusal) as e:
        hits(at[:-1] + [dict(at[-1], epoch=2)], threshold_record(free, a), a)
    assert e.value.name == "THRESHOLD_STALE"
    for mixed in (free[:-1] + [dict(free[-1], epoch=BLANK_EPOCH)], [dict(free[0], epoch=2)] + free[1:], []):
        with pytest.raises(LearnRefusal) as e:
            threshold_record(mixed, a)
        assert e.value.name == "THRESHOLD_MIXED"


def test_gate_comparison_rules__rule_4_a_rate_below_the_floor_is_labelled_an_extrapolation():
    assert rate_floor(12000) == 10 / 12000 and rate_floor(300000) == 10 / 300000
    assert rate_label(PFA, 12000) == rate_label(PFA, 300000) == "COUNTED"
    assert rate_label(10.01 / 12000, 12000) == "COUNTED" and rate_label(9.99 / 12000, 12000) == "EXTRAPOLATION"
    assert rate_label(1e-4, 12000) == "EXTRAPOLATION" and rate_label(1e-4, 300000) == "COUNTED"
    assert PFA / rate_floor(12000) == pytest.approx(12.0) and PFA / rate_floor(300000) == pytest.approx(300.0)
    _got, part = short()
    assert part["rate_label"] == "COUNTED" and part["rate_floor"] == 10 / 12000 and part["pfa"] == PFA


def test_control_comparison_rules__rule_4_a_rate_below_its_floor_that_is_called_counted_is_not_as_stated():
    parts = stated_parts()
    assert not_as_stated(parts) == []
    parts[5]["pfa"] = 2e-5                  # 6 expected crossings in 300,000 scores
    reasons = not_as_stated(parts)
    print("CONTROL rule 4: %s" % [r for r in reasons if "floor" in r])
    assert any("below the floor" in r for r in reasons)
    parts[5]["rate_label"] = "EXTRAPOLATION"
    assert not any("below the floor" in r for r in not_as_stated(parts)), "labelled, it is no longer called counted"
    assert not_as_stated(parts), "though a part at another rate is still not the stated experiment"


def stated_parts():
    """Six part records that ARE the stated experiment, with made-up counts at D8's own figures.

    Each carries the matched filter's own integers as its 'learned' coefficients, so that its blob
    hash and its deflection are consistent with what it carries."""
    f = facts()
    parts = []
    for c in range(len(COUNTS)):
        p = plan(c)
        k = int(Fraction(PFA) * p["m"])
        found = round(theory.pd_matched((k + 1) / (p["m"] + 1), f["d"]) * p["n"])
        parts.append({"part": c, "name": p["name"], "trained_on": p["trained_on"], "labelled_windows": p["labelled_windows"],
                      "seed": p["seed"], "profile": PROFILE, "sigma": list(SIGMA), "pfa": PFA, "amplitude": list(AMPLITUDE),
                      "taps": TAPS, "spacing": SPACING, "A": p["A"], "B": p["B"], "length": p["length"], "n": p["n"], "m": p["m"],
                      "k": k, "above": k, "threshold": 1.0e9, "threshold_epoch": LEARNED_EPOCH, "held_out_epochs": [LEARNED_EPOCH],
                      "rate_floor": rate_floor(p["m"]), "rate_label": "COUNTED", "coefficients": list(f["coeffs"]),
                      "blob_sha256": weights.unpack(f["blob"])["sha256"], "d_learned": f["d"], "d_matched": f["d"],
                      "found": found, "base_threshold": 1.0e9, "base_above": k, "base_found": found,
                      "base_found_known_threshold": round(theory.pd_matched(PFA, f["d"]) * p["n"]),
                      "scores_identical_to_stats": True, "core_equals_baseline_on_first_trials": True, "peak_offset": TAPS - 1,
                      "reported": c == NAMED, "spec_sha256": C.SPEC_SHA256, "base_only": 0, "learned_only": 0,
                      "noise_base_only": 0, "noise_learned_only": 0, "noise_both": k, "comparison_refused": None,
                      "handover_refusal": None, "first_new_epoch_index": p["A"], "flags": 0, "scores_not_zero_while_blank": 0,
                      "learner_counts": [p["trained_on"]] * 2, "injection_sha256": committed_sets()[p["name"]]["sha256"],
                      "stream_sha256": "%064x" % c})
    return parts


def judged(parts, tmp_path, capsys):
    paths = []
    for part in parts:
        path = tmp_path / ("part%s-%d.json" % (part["part"], len(paths)))
        path.write_text(json.dumps(part), encoding="utf-8")
        paths.append(str(path))
    code = judge_parts(paths)
    return code, capsys.readouterr().out


def test_gate_comparison_rules__rule_5_the_reported_model_is_the_one_named_before_the_run(tmp_path, capsys):
    parts = stated_parts()
    named, r = report(parts)
    assert named["part"] == NAMED == 5 and named["trained_on"] == 16384 and named["reported"] and r["e0"]["inside"]
    assert [p["reported"] for p in parts] == [False] * 5 + [True]
    code, out = judged(parts, tmp_path, capsys)
    assert code == 0 and "== E1 SOFTWARE VERDICT: PASS" in out and "NOT AS STATED" not in out
    assert "THE REPORTED MODEL, named before the run: part 5, 16384 truth records, 32768 labelled windows" in out
    _got, part = short()
    assert part["reported"] is True, "the short form has one model, and it is the one it reports"


def test_control_comparison_rules__rule_5_the_best_of_several_snapshots_is_refused(tmp_path, capsys):
    """An earlier snapshot has the highest efficiency. Reporting it is refused; a part file that
    marks it as the reported model is not as stated; and the judge's verdict is read from the
    named part even so."""
    parts = stated_parts()
    parts[3]["found"] += 900
    parts[3]["learned_only"] += 900                 # the counts still add up: it found 900 the baseline did not
    assert not_as_stated(parts) == []
    best = max(parts, key=lambda p: p["found"] / p["n"])["part"]
    assert best == 3 != NAMED
    with pytest.raises(LearnRefusal) as e:
        report(parts, best)
    with capsys.disabled():                 # this test reads what the judge prints, so its own line goes round the capture
        print("CONTROL rule 5, the best snapshot (part %d, efficiency %.4f against the named part's %.4f) asked for: %s"
              % (best, parts[best]["found"] / parts[best]["n"], parts[NAMED]["found"] / parts[NAMED]["n"], e.value))
    assert e.value.name == "NOT_THE_NAMED_MODEL"
    for other in (0, 4, "short", None):
        with pytest.raises(LearnRefusal):
            report(parts, other)
    assert report(parts)[0]["part"] == NAMED, "asked for nothing, the report is the named model"
    marked = stated_parts()
    marked[3]["found"] += 900
    marked[3]["learned_only"] += 900
    marked[3]["reported"], marked[5]["reported"] = True, False
    reasons = not_as_stated(marked)
    assert any("part 3: reported is True" in r for r in reasons) and any("part 5: reported is False" in r for r in reasons)
    code, out = judged(marked, tmp_path, capsys)
    assert code == 1 and "NOT AS STATED" in out and "== E1 SOFTWARE VERDICT: FAIL" in out
    # two parts that both claim to be the named one, and none that does
    for change in (lambda ps: ps.__setitem__(4, dict(ps[5], stream_sha256="x")), lambda ps: ps.pop(5)):
        ps = stated_parts()
        change(ps)
        with pytest.raises(LearnRefusal) as e:
            report(ps)
        assert e.value.name == "NOT_THE_NAMED_MODEL"


def test_control_comparison_rules__the_judge_fails_parts_that_are_not_the_stated_experiment(tmp_path, capsys):
    """Each of these has counts that sit on D8's figures: a judge that read only the counts would
    print PASS for every one."""
    def seed(ps):
        ps[2]["seed"] = FULL_SEED

    def one_stream(ps):
        ps[3]["stream_sha256"] = ps[2]["stream_sha256"]

    def other_set(ps):
        ps[1]["injection_sha256"] = ps[0]["injection_sha256"]

    def swapped_late(ps):
        ps[4]["first_new_epoch_index"] += 1

    def never_swapped(ps):
        ps[4]["held_out_epochs"] = [BLANK_EPOCH]

    def refused_candidate(ps):
        ps[0]["handover_refusal"] = "QUANTISE_INPUT"

    def ties(ps):
        ps[5]["above"] -= 1

    def baseline_at_another_rate(ps):
        ps[5]["base_above"] += 1

    def other_d(ps):
        ps[5]["d_learned"] += 1e-6

    def other_coefficients(ps):
        ps[5]["coefficients"] = list(reversed(ps[5]["coefficients"]))

    def fewer_injections(ps):
        ps[5]["n"] = 50000

    def fewer_signal_free(ps):
        ps[5]["m"] = 150000

    def missing(ps):
        del ps[0]

    def two_of_one(ps):
        ps[0] = dict(ps[1])

    def counts_do_not_add_up(ps):
        ps[5]["base_only"] = 700

    def crossings_do_not_add_up(ps):
        ps[5]["noise_both"] -= 1

    def trained_on_more(ps):
        ps[5]["learner_counts"] = [16384, 16385]

    def other_definition(ps):
        ps[2]["spec_sha256"] = "0" * 64

    def not_blank_before(ps):
        ps[1]["scores_not_zero_while_blank"] = 3

    changes = (seed, one_stream, other_set, swapped_late, never_swapped, refused_candidate, ties, baseline_at_another_rate,
               other_d, other_coefficients, fewer_injections, fewer_signal_free, missing, two_of_one, counts_do_not_add_up,
               crossings_do_not_add_up, trained_on_more, other_definition, not_blank_before)
    for change in changes:
        ps = stated_parts()
        change(ps)
        assert not_as_stated(ps), change.__name__
        (tmp_path / change.__name__).mkdir()
        code, out = judged(ps, tmp_path / change.__name__, capsys)
        assert code == 1 and "NOT AS STATED" in out and "== E1 SOFTWARE VERDICT: FAIL" in out, change.__name__
    # and each condition of the verdict fails on its own, with the parts otherwise as stated
    def low(ps):
        ps[5]["found"] -= 2000
        ps[5]["base_only"] += 2000

    def low_baseline(ps):
        ps[2]["base_found"] -= 2000
        ps[2]["learned_only"] += 2000

    def flag(ps):
        ps[1]["flags"] = 2

    def not_identical(ps):
        ps[0]["scores_identical_to_stats"] = False

    def core_differs(ps):
        ps[3]["core_equals_baseline_on_first_trials"] = False

    for change in (low, low_baseline, flag, not_identical, core_differs):
        ps = stated_parts()
        change(ps)
        assert not_as_stated(ps) == [], change.__name__
        (tmp_path / change.__name__).mkdir()
        code, out = judged(ps, tmp_path / change.__name__, capsys)
        assert code == 1 and "NOT AS STATED" not in out and "== E1 SOFTWARE VERDICT: FAIL" in out, change.__name__
    # A filter that learned nothing, counted exactly as D8 says for ITS OWN integers: check 2 is INSIDE, check 3 is not.
    def learned_nothing(ps, c):
        ps[c]["coefficients"] = [C.COEFF_MAX] + [0] * (TAPS - 1)
        ps[c]["blob_sha256"] = weights.unpack(one_tap_blob())["sha256"]
        ps[c]["d_learned"] = theory.deflection(ps[c]["coefficients"], facts()["injected"], facts()["sigma"])
        ps[c]["found"] = 1000
        ps[c]["base_only"] = ps[c]["base_found"] - 1000
        assert not_as_stated(ps) == [] and result(ps[c])["own"]["inside"] and not result(ps[c])["e0"]["inside"]

    # At an EARLIER count that is the curve, and not a failure: only the named model must reach E0's efficiency.
    ps = stated_parts()
    learned_nothing(ps, 0)
    (tmp_path / "curve").mkdir()
    code, out = judged(ps, tmp_path / "curve", capsys)
    assert code == 0 and "OUTSIDE" in out and "== E1 SOFTWARE VERDICT: PASS" in out
    # At the NAMED count it is the result, and the verdict is FAIL: check 3 is in the verdict, not only check 2.
    ps = stated_parts()
    learned_nothing(ps, NAMED)
    (tmp_path / "named").mkdir()
    code, out = judged(ps, tmp_path / "named", capsys)
    assert code == 1 and "NOT AS STATED" not in out and "== E1 SOFTWARE VERDICT: FAIL" in out
    assert "against E0's D8" in out and "OUTSIDE" in out


# ------------------------------------------------------------ the short form's result, and its controls

def test_gate_statistics__e1_the_learned_filter_reaches_the_matched_filters_efficiency_short_form():
    got, part = short()
    p = got["plan"]
    assert not_as_stated([part], ["short"]) == []
    assert part["flags"] == 0 and got["scores_not_zero_while_blank"] == 0, "nothing overflowed; blank, every score was 0"
    assert part["handover_refusal"] is None and part["first_new_epoch_index"] == p["A"] == 131072
    assert part["scores_identical_to_stats"] and part["core_equals_baseline_on_first_trials"]
    r = result(part)
    own, e0, base = r["own"], r["e0"], r["baseline"]
    print("E1 short form: seed %d, %d truth records (%d labelled windows), swap at %d; %d held-out injections, %d signal-free scores"
          % (p["seed"], p["trained_on"], p["labelled_windows"], p["A"], p["n"], p["m"]))
    print("E1 short form: the learned filter found %d of %d, efficiency %.4f; its coefficients' deflection %.4f, D8 %.4f, "
          "%+.2f se, %s" % (part["found"], p["n"], r["measured"], part["d_learned"], own["expected"], own["z_score"],
                            "INSIDE" if own["inside"] else "OUTSIDE"))
    print("E1 short form: against E0's efficiency, D8 at d %.4f = %.4f: %+.2f se, tolerance %.4f, %s"
          % (part["d_matched"], e0["expected"], e0["z_score"], e0["tolerance"], "INSIDE" if e0["inside"] else "OUTSIDE"))
    print("E1 short form: the matched filter on the same held-out stream: %d of %d at its measured threshold (%+.2f se, %s), "
          "%d at D8's own" % (part["base_found"], p["n"], base["z_score"], "INSIDE" if base["inside"] else "OUTSIDE",
                              part["base_found_known_threshold"]))
    pr = r["paired"]
    print("E1 short form: paired cost %+.5f, se %.5f (pairs %.5f, thresholds %.5f); the coefficients predict %+.5f, %+.2f se"
          % (pr["cost"], pr["se"], pr["se_pairs"], pr["se_thresholds"], pr["predicted"], pr["z_score"]))
    assert own["inside"], "check 2: the instrument counts the learned filter as D8 says for its own integers"
    assert e0["inside"], "check 3: the learner reaches E0's efficiency, inside this short form's wide tolerance"
    assert base["inside"] and r["baseline_known"]["inside"], "the baseline is E0's, on this stream"
    assert 0.0627 < e0["tolerance"] < 0.0629, "four standard errors at 4,000 injections and 12,000 signal-free scores: wide, and stated"
    assert holds(part, r)


def test_control_statistics__e1_the_two_checks_on_the_instrument_can_each_fail():
    """Two of the verdict's conditions are comparisons made inside `evaluate`. Each is shown to
    report a difference: one score read one unit off, and a core holding another filter."""
    got, part = short()
    p = got["plan"]
    extra = {name: part[name] for name in ("handover_refusal", "first_new_epoch_index", "flags", "scores_not_zero_while_blank",
                                           "learner_counts", "injection_sha256", "stream_sha256")}
    for g, off in ((0, 1), (len(got["reads"]) - 1, -1)):                # the first score read and the last, one unit each way
        reads = [dict(r) for r in got["reads"]]
        reads[g]["score"] += off
        wrong = evaluate(p, reads, got["held"], got["blob"], extra)
        assert part["scores_identical_to_stats"] and not wrong["scores_identical_to_stats"] and not holds(wrong)
    learned_scores = stat_scores_at_reads(got["held"], part["coefficients"])
    assert core_agrees(p, got["held"], got["blob"], learned_scores), "the core holding the learned blob gives the learned filter's scores"
    assert not core_agrees(p, got["held"], facts()["blob"], learned_scores), "and the core holding the matched filter does not"
    assert not core_agrees(p, got["held"], got["blob"], stat_scores_at_reads(got["held"], facts()["coeffs"]))
    assert not holds(dict(part, core_equals_baseline_on_first_trials=False))


def test_gate_statistics__e1_the_learned_filter_peaks_where_its_score_is_read():
    """conventions.md does not promise where a filter that is not an exact multiple of the pulse
    peaks. Measured: for the learned blob, a lone noise-free injection's largest score is at the
    truth index + 63, where E1 reads it."""
    _got, part = short()
    assert part["peak_offset"] == TAPS - 1 == 63
    assert peak_offset(facts()["blob"]) == 63
    reversed_blob = weights.pack(PROFILE, [{0: tuple(reversed(part["coefficients"]))}], (1,), C.RECTIFIERS["pass"], 1, 0)
    assert peak_offset(reversed_blob) != 63, "the measurement can tell: the same integers the wrong way round peak elsewhere"


class ReturnsItsStart(trainer.MeanDifference):
    """A trainer that learns nothing: its weights are its starting ones, whatever it is fed."""

    def weights(self):
        return self.start()


class StartsAtOneTap(ReturnsItsStart):
    """The lead's control: starting weights that are NOT zero, one tap of 1 and the rest 0, returned unchanged."""

    def start(self):
        return ((Fraction(1),) + (Fraction(0),) * (self.taps - 1),) * self.channels


SMALL = make_plan("small", "short", 4, 8, 4, 2026112600)


def small_run(make_learner):
    return measure(SMALL, make_learner=make_learner, committed={"small": dict(zip(("sha256", "records"), independent_digest(schedule_for(SMALL))))})


def test_control_statistics__e1_a_trainer_that_returns_its_starting_weights_falls_outside():
    got, part = short()
    p = got["plan"]
    # 1. Blank starting weights. The model's own rule refuses the candidate, so nothing can be handed over.
    blank = ReturnsItsStart(1, TAPS)
    trainer.train(got["train"].astype(np.int64).reshape(-1, 1), [r["index"] for r in got["truth"] if r["index"] < p["A"]], TAPS, blank)
    assert blank.counts == [1024, 1024] and blank.weights() == blank.start() and not any(blank.weights()[0])
    with pytest.raises(Refusal) as e:
        handover.candidate_blob(PROFILE, blank.weights())
    print("CONTROL do-nothing trainer, blank start: the hand-over is refused by the model: %s" % e.value)
    assert e.value.name == "QUANTISE_INPUT"
    # Through E1's own flow, on a small part: the refusal is recorded, nothing is swapped, the detector stays blank.
    flow = small_run(lambda: ReturnsItsStart(1, TAPS))
    assert flow["refusal"] == "QUANTISE_INPUT" and flow["blob"] is None and flow["first_new_epoch_index"] is None
    assert {r["epoch"] for r in flow["reads"]} == {BLANK_EPOCH} and {r["score"] for r in flow["reads"]} == {0}
    # The detector left blank, on the short form's held-out samples: every score 0, epoch 0.
    left = control_part(None, BLANK_EPOCH, {"handover_refusal": "QUANTISE_INPUT", "first_new_epoch_index": None})
    r = result(left)
    reasons = not_as_stated([left], ["short"])
    print("CONTROL do-nothing trainer, blank start: found %d of %d; against E0's efficiency %.4f: %+.1f se, tolerance %.4f, %s; "
          "threshold %.0f with %d of %d signal-free scores above it; NOT AS STATED for %d reasons, the first: %s"
          % (left["found"], left["n"], r["e0"]["expected"], r["e0"]["z_score"], r["e0"]["tolerance"],
             "INSIDE" if r["e0"]["inside"] else "OUTSIDE", left["threshold"], left["above"], left["m"], len(reasons), reasons[0]))
    assert left["found"] == 0 and not r["e0"]["inside"] and r["e0"]["z_score"] < -8.0, "beyond the catch margin, not merely outside"
    assert left["held_out_epochs"] == [BLANK_EPOCH] and left["comparison_refused"] == "UNEQUAL_FALSE_ALARM_RATE"
    assert any("handover_refusal" in x for x in reasons) and any("held_out_epochs" in x for x in reasons)
    assert not holds(left, r)
    # 2. The lead's: starting weights that are not zero. The model accepts them; the judge must fail them.
    start = StartsAtOneTap(1, TAPS)
    assert start.weights() == ((Fraction(1),) + (Fraction(0),) * 63,) and handover.coefficients(one_tap_blob()) == ((C.COEFF_MAX,) + (0,) * 63,)
    flow = small_run(lambda: StartsAtOneTap(1, TAPS))
    assert flow["refusal"] is None and flow["blob"] == one_tap_blob() and flow["first_new_epoch_index"] == SMALL["A"]
    assert [r["epoch"] for r in flow["reads"]] == [LEARNED_EPOCH] * len(flow["reads"])
    held = [int(v) for v in flow["held"]]
    assert [r["score"] for r in flow["reads"]] == [C.COEFF_MAX * held[i - (TAPS - 1)] for i in range(TAPS - 1, len(held), STRIDE)], \
        "swapped in at A, the core's score is that one tap against the oldest sample of its window"
    one = control_part(one_tap_blob())
    r = result(one)
    print("CONTROL do-nothing trainer, one tap of 1: handed over without refusal, swapped in at A; found %d of %d, efficiency "
          "%.4f; its deflection %.4f; against E0's efficiency %.4f: %+.1f se, tolerance %.4f, %s"
          % (one["found"], one["n"], r["measured"], one["d_learned"], r["e0"]["expected"], r["e0"]["z_score"],
             r["e0"]["tolerance"], "INSIDE" if r["e0"]["inside"] else "OUTSIDE"))
    assert one["scores_identical_to_stats"] and one["k"] == 120
    assert core_agrees(p, got["held"], one_tap_blob(), stat_scores_at_reads(got["held"], one["coefficients"])), \
        "the core, holding the one-tap blob, gives these scores on the first 256 test trials"
    assert not r["e0"]["inside"] and r["e0"]["z_score"] < -8.0
    assert not holds(one, r)
    # A one-tap filter's score is one sample times a constant, so scores TIE: when one ties at the threshold, fewer than
    # k are above it, and the part says so. Apart from that, nothing about the part says it is wrong: only the count does.
    reasons = not_as_stated([one], ["short"])
    print("CONTROL do-nothing trainer, one tap of 1: %d of %d signal-free scores are above its threshold (k is %d); as a "
          "part it is %s" % (one["above"], one["m"], one["k"], "as stated" if not reasons else "NOT AS STATED: %s" % reasons))
    assert (one["above"] == 120 and reasons == []) or \
        (one["above"] < 120 and reasons and all("above is" in x or "comparison_refused" in x or "do not add up" in x for x in reasons))
    # and the real learner, on the same samples by the same road, is inside: the control's road can pass
    again = control_part(got["blob"])
    assert again["found"] == part["found"] and result(again)["e0"]["inside"]


def test_control_statistics__e1_labels_shifted_by_a_pulse_length_do_not_reach_the_efficiency():
    got, part = short()
    p = got["plan"]
    x = got["train"].astype(np.int64).reshape(-1, 1)
    labels = [r["index"] for r in got["truth"] if r["index"] < p["A"]]
    for shift, kept in ((TAPS, labels[:-1]), (-TAPS, labels[1:])):       # the record whose window leaves the period is left out
        with pytest.raises(LearnRefusal):
            trainer.train(x, [j + shift for j in labels], TAPS)
        learner = trainer.train(x, [j + shift for j in kept], TAPS)
        assert learner.counts == [1023, 1023]
        shifted = control_part(handover.candidate_blob(PROFILE, learner.weights()), extra={"learner_counts": [1023, 1023]})
        r = result(shifted)
        print("CONTROL labels shifted by %+d frames: found %d of %d, efficiency %.4f; its deflection %+.4f; against E0's "
              "efficiency %.4f: %+.1f se, %s" % (shift, shifted["found"], shifted["n"], r["measured"], shifted["d_learned"],
                                                r["e0"]["expected"], r["e0"]["z_score"], "INSIDE" if r["e0"]["inside"] else "OUTSIDE"))
        assert not r["e0"]["inside"] and r["e0"]["z_score"] < -8.0, "beyond the catch margin, not merely outside"
        assert shifted["d_learned"] < 0, "in this layout the shift puts the pulse in the windows labelled 0"
        assert not holds(shifted, r)
    assert result(part)["e0"]["inside"]


# ------------------------------------------------------------ the wiring

@pytest.mark.parametrize("profile", sorted(C.PROFILES))
def test_lrn_a_e1_the_wiring_equals_the_models_own_runner_when_nothing_is_swapped(profile):
    channels = C.PROFILES[profile]["channels"]
    blob = handover.candidate_blob(profile, tuple(tuple((c + 2) * (k - 3) + c for k in range(9)) for c in range(channels)))
    schedule = [{"index": 30 + 100 * i, "pulse_id": 0, "amplitude_num": 3 + i, "amplitude_den": 2} for i in range(4)]
    frames = list(source.Noise(profile, 9, 700, 1, 450))
    theirs, truth_theirs = model_run.detect(frames, schedule, 450, blob)
    for hand in (None, (200, lambda: None, 200)):                 # no hand-over, and one whose candidate is refused
        pairs, truth = wired(profile, frames, schedule, 450, blob, hand)
        mine = [record for _frame, record in pairs]
        assert records.digest("score", mine) == records.digest("score", theirs) and truth == truth_theirs
        assert records.digest("score", mine)[1] == 450


@pytest.mark.parametrize("profile", sorted(C.PROFILES))
def test_lrn_a_e1_the_same_samples_under_other_truth_records_give_the_same_score_records(profile):
    channels = C.PROFILES[profile]["channels"]
    old = handover.candidate_blob(profile, tuple(tuple((c + 2) * (k - 3) + c for k in range(9)) for c in range(channels)))
    new = handover.candidate_blob(profile, tuple(tuple((k * k) % 7 - c for k in range(9)) for c in range(channels)))
    schedule = [{"index": 30 + 100 * i, "pulse_id": 0, "amplitude_num": 3 + i, "amplitude_den": 2} for i in range(4)]
    pairs, _truth = wired(profile, source.Noise(profile, 9, 700, 1, 450), schedule, 450, old, (210, lambda: new, 210))
    seen = list(pairs)
    samples = [frame for frame, _record in seen]
    assert [r["epoch"] for _f, r in seen] == [0] * 210 + [1] * 240
    again, none = wired(profile, samples, [], 450, old, (210, lambda: new, 210))
    assert none == () and records.digest("score", [r for _f, r in again]) == records.digest("score", [r for _f, r in seen])


def test_lrn_a_e1_the_candidate_is_made_before_the_frame_at_the_named_index_is_drawn():
    drawn = []

    def frames():
        for i in range(40):
            drawn.append(i)
            yield (i,)

    def make():
        assert drawn == list(range(25)), "frames 0..24 have been drawn, and frame 25 has not"
        return None

    pairs, _truth = wired(PROFILE, frames(), [], 40, handover.blank_blob(PROFILE, 4), (25, make, 25))
    assert len(list(pairs)) == 40 and drawn == list(range(40))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

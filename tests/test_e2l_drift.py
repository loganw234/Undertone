"""Stage E2 in software, induced drift: after the pulse changes shape, how fast and how well do the
adaptive and the reset models recover, against the frozen one, at an equal false-alarm rate?

The design D0, section 8: "Mid-run, the pulse shape or the noise colour changes. Five models see the
same stream: frozen; frozen with only its input scaling updated; adaptive; periodically reset; and the
matched filter for the new condition. Shows: whether adaptation recovers events the frozen model
misses, at an equal false-alarm rate." In white noise its direction is known in advance (the plan's
option B); what is measured is how fast, in labelled windows after the change, and how well.

THE EXPERIMENT, fixed before any run (the round's ledger, 2026-11-25: E2L's design of 12:26 and the
lead's ruling after it; the injection sets hashed at 12:30:57 before any run):

  profile     s16x1; noise sigma 1477/1; amplitude 1/1; 64 taps; a false-alarm probability of 0.01
  the pulses  e0, and e1 = e0's recipe with half its 4-cycle sine and sqrt(3)/2 of an 8-cycle one:
              cos(e0, e1) = 0.499949 from the integers (spec/pulses/e1.toml)
  a part      one stream under one seed:
                training   16 blocks of 128 trials, a trial every 128 frames with its pulse at frame
                           64 of the 128; block t is frames 16384 t .. 16384 (t+1) - 1. The pulse is e0
                           in blocks 0-7 and e1 from block 8: THE CHANGE IS AT FRAME 131,072
                held out   from A = 262,144: m1 calibration reads with no injection, then n test trials
                           of e1, laid out as E1's held-out stretch. Nothing a learner is handed is at
                           or after A.
  the models  1 frozen          weights.matched_filter(profile, e0): never swapped
              2 frozen, input scaling updated: THE FROZEN MODEL AGAIN. A positive gain on the
                                coefficients quantises to the frozen blob, byte for byte; one on the
                                score is undone by a threshold set again at an equal false-alarm rate.
                                Held by a test here
              3 adaptive        learn.adaptive.Window over the 8 most recent blocks (1,024 records);
                                retrained after every block; its candidate swapped into the model's
                                core at the block's end, 16384 (t+1): sixteen swaps in the stream;
                                starts from the frozen blob
              4 reset           learn.adaptive.Resetting: every block since its last reset, a reset
                                (its blocks dropped, no swap) before blocks 4 and 12, a period of 8;
                                starts from the frozen blob
              5 the e1 filter   weights.matched_filter(profile, e1): never swapped
  judged      the snapshots of the adaptive and the reset model after blocks 7 to 15, g = 0 .. 8,
              g = 0 the last before the change and g after g post-change blocks, 256 g labelled
              windows after it; snapshot g carries epoch 8 + g. Each on H, at its own threshold
              measured from H's m signal-free reads under its own weights. The adaptive's g = 8 is the
              core's own records in the stream; every other model and snapshot is a REPLAY of H (D0
              section 4): the statistics' float filter on H's kept samples, exact for integer
              coefficients, held to the model's core on the first 256 test trials
  the checks  for every entry: "own", stats.tolerance.check_efficiency at the deflection of e1
              against its own integers (the instrument); "best", at the e1 filter's deflection. For
              every snapshot the paired gain over the frozen model, and the shortfall from the e1
              filter, on the same injections, by LRN-A's derivation (tests/test_lrn_a_e1.py)
  THE REPORTED MODELS, named before the run: the adaptive model's g = 8, and the reset model's g = 8
  the verdict PASS when the part is the stated experiment; no record carries a flag; the adaptive's
              reads equal the statistics' filter; the core equals it on the first 256 trials for every
              entry; every entry is INSIDE its own D8 figure; the frozen model is OUTSIDE the e1
              filter's; and each named snapshot's gain over the frozen model is more than four of its
              standard errors above zero. INSIDE against the e1 filter's figure is reported, not required
  full run    one part: m1 = 200,000, n = 100,000, seed 2026112700. 25,862,144 frames
  short form  one part: m1 = 8,000, n = 4,000, seed 2026112701. 1,286,144 frames

THE COMPARISON RULES of D0's section 8, held here as the gate `comparison-rules`. Rules 2 to 4 by E1's own
functions (tests/test_lrn_a_e1.py), imported and called unchanged: H is laid out as E1's held-out stretch,
and it is the stream's last, so E1's lower bound A + 63 is the whole of rule 2 for it. Rules 1 and 5 by
this file's own `check_injection_set` and `report`, written as E1's are, for this file's sets and models.
  1 each form's injection set is committed with its hash in vectors/e2l/injection_sets.json; a run on
    any other set is refused before a frame is drawn
  2 the learners are handed frames below A, and at each swap only frames already drawn; every figure
    is read from records at or after A + 63
  3 a threshold belongs to one weight epoch; two models are compared only at each one's own threshold,
    each giving the same count of the same signal-free reads
  4 a false-alarm rate below ten expected crossings is labelled an extrapolation
  5 the reported models are the named ones; a report of any other is refused

THE FULL RUN is the lead's, booked: about 8 to 13 minutes of one core (an ESTIMATE, docs/model/e2l.md).

    python tests/test_e2l_drift.py --full --out e2-part.json
    python tests/test_e2l_drift.py --judge e2-part.json

WHAT THIS DOES NOT SHOW: anything in fabric, on real noise, at another overlap, amplitude, noise level or
profile, or for a drift that goes on changing after the change; it is evidence about sensitivity, by D8's
authority, in software. Its limits are docs/model/e2l.md's.
"""
import hashlib
import json
import math
import os
import sys
from array import array
from fractions import Fraction

import numpy as np
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _path in (ROOT, HERE):              # run as a script: the tree, and E1's script beside this one
    if _path not in sys.path:
        sys.path.insert(0, _path)

from spec import constants as C  # noqa: E402
from model import inject, records, source, weights  # noqa: E402
from model.detector import Core  # noqa: E402
from model.refusal import Refusal  # noqa: E402
from stats import matched as stat_matched  # noqa: E402
from stats import recovery, theory, tolerance  # noqa: E402
from stats.errors import StatRefusal  # noqa: E402
from learn import adaptive, handover, trainer  # noqa: E402
from learn.errors import LearnRefusal  # noqa: E402
import test_lrn_a_e1 as E1  # noqa: E402

PROFILE, SIGMA, PFA = E1.PROFILE, E1.SIGMA, E1.PFA
SPACING, FIRST, TAPS, STRIDE = E1.SPACING, E1.FIRST, E1.TAPS, E1.STRIDE
AMPLITUDE = (1, 1)
BLOCKS, CHANGE_BLOCK = 16, 8
KEEP = 8                                    # the adaptive model's window, in blocks
RESET_PERIOD, RESET_PHASE = 8, 4            # the reset model: a reset before blocks 4 and 12
JUDGED = tuple(range(7, BLOCKS))            # the snapshots judged: after blocks 7 .. 15, g = t - 7
LEARNERS = ("adaptive", "reset")
NAMED = {"adaptive": 8, "reset": 8}         # rule 5: the reported models, named before the run
FULL_M_CAL, FULL_N, FULL_SEED = 200000, 100000, 2026112700
SHORT_M_CAL, SHORT_N, SHORT_SEED = 8000, 4000, 2026112701
BLOCK_TRIALS = 128
CORE_CHECK = E1.CORE_CHECK
GAIN_Z = 4.0                                # the verdict: a named gain more than this many standard errors above zero
NAMES = ("e0", "e1")


# ------------------------------------------------------------ the experiment's parts

def make_plan(name, block_trials, m_cal, n, seed):
    bf = SPACING * block_trials
    a = BLOCKS * bf
    b = a + STRIDE * m_cal
    return {"name": name, "block_trials": block_trials, "block_frames": bf, "change": CHANGE_BLOCK * bf,
            "swaps": [bf * (t + 1) for t in range(BLOCKS)], "A": a, "B": b, "m_cal": m_cal, "n": n, "m": m_cal + n,
            "length": b + SPACING * n, "seed": seed}


def plan(form):
    """Everything about a part that is known before a sample is drawn. `form` is "short" or "full"."""
    if form == "short":
        return make_plan("short", BLOCK_TRIALS, SHORT_M_CAL, SHORT_N, SHORT_SEED)
    if form == "full":
        return make_plan("full", BLOCK_TRIALS, FULL_M_CAL, FULL_N, FULL_SEED)
    raise ValueError("there is no form %r: a form is \"short\" or \"full\"" % (form,))


def resets():
    """The blocks before which the reset model drops its blocks."""
    return [b for b in range(1, BLOCKS) if b % RESET_PERIOD == RESET_PHASE]


def held_blocks(learner, t):
    """The training blocks a learner's snapshot after block t is made from, as the plan states them."""
    if learner == "adaptive":
        return list(range(max(0, t - KEEP + 1), t + 1))
    last = max([0] + [r for r in resets() if r <= t])
    return list(range(last, t + 1))


def record(index, name):
    return {"index": index, "pulse_id": C.PULSE_IDS[name], "amplitude_num": AMPLITUDE[0], "amplitude_den": AMPLITUDE[1]}


def trial_indexes(p):
    """Every trial's truth index, as the plan states it: the training trials, then the test trials."""
    return [FIRST + SPACING * i for i in range(BLOCKS * p["block_trials"])] + \
           [p["B"] + FIRST + SPACING * i for i in range(p["n"])]


def schedule_for(p):
    """The part's injection set: e0 before the change, e1 from it on."""
    return [record(j, "e0" if j < p["change"] else "e1") for j in trial_indexes(p)]


_facts = {}


def facts():
    """What is known of the five models and the two pulses before any run."""
    if not _facts:
        f = E1.facts()
        e1_blob = weights.matched_filter(PROFILE, C.PULSES["e1"], (1,))
        e1_coeffs = list(weights.unpack(e1_blob)["filters"][0][0])
        injected = {name: list(inject.scaled_pulse(C.PULSE_IDS[name], AMPLITUDE[0], AMPLITUDE[1])) for name in NAMES}
        _facts.update(sigma=f["sigma"], frozen_blob=f["blob"], frozen_coeffs=list(f["coeffs"]), e1_blob=e1_blob,
                      e1_coeffs=e1_coeffs, injected=injected,
                      d_frozen=theory.deflection(f["coeffs"], injected["e1"], f["sigma"]),
                      d1=theory.deflection(e1_coeffs, injected["e1"], f["sigma"]),
                      response={name: sum(c * s for c, s in zip(f["coeffs"], injected[name])) for name in NAMES})
    return _facts


# ------------------------------------------------------------ rule 1: the injection set

_committed = {}


def committed_sets():
    if not _committed:
        with open(os.path.join(ROOT, "vectors", "e2l", "injection_sets.json"), encoding="utf-8") as fh:
            _committed.update(json.load(fh)["sets"])
    return _committed


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


def own_digest(p, schedule):
    """A committed set made for a test's own small plan: E1's digest, which imports nothing of the model."""
    sha, count = E1.independent_digest(schedule)
    return {p["name"]: {"sha256": sha, "records": count}}


# ------------------------------------------------------------ one run

def measure(p, schedule=None, committed=None, injector=None, hand=None, keep=KEEP, reset=(RESET_PERIOD, RESET_PHASE),
            keep_records=False, progress=None):
    """Run one part through the model: the noise, the injector, the adaptive model's core with its
    sixteen hand-overs, and both learners. Returns what was seen.

    `schedule`, `committed`, `injector`, `hand`, `keep`, `reset` and `keep_records` are for the
    controls and for tests on a small part; the experiment passes none of them.
    """
    schedule = schedule_for(p) if schedule is None else schedule
    digest = check_injection_set(p, schedule, committed)          # rule 1: before a frame is drawn
    a, bf, length = p["A"], p["block_frames"], p["length"]
    noise = source.Noise(PROFILE, p["seed"], SIGMA[0], SIGMA[1], length)
    noise_kept = array("h")

    def tee():                                                    # the noise as the injector draws it, kept
        for frame in noise:
            noise_kept.append(frame[0])
            yield frame

    injected, truth = (inject.inject if injector is None else injector)(PROFILE, tee(), schedule, length)
    core = Core(facts()["frozen_blob"])                           # the adaptive model starts from the frozen blob
    learners = {"adaptive": adaptive.Window(1, TAPS, keep), "reset": adaptive.Resetting(1, TAPS, *reset)}
    snapshots = {name: [] for name in LEARNERS}
    hand = handover.hand_over if hand is None else hand
    block, train_samples, held = array("h"), array("h"), array("h")
    reads, every, swap_epochs, drawn_at_swaps = [], [], [], []
    flags, first_new, seen, swap = 0, None, 0, 0
    swap_at = set(p["swaps"])
    frames = iter(injected)
    while True:
        i = core.next_index
        if swap < BLOCKS and i == p["swaps"][swap]:
            # Rule 2: the learners are handed block `swap`, whose frames are all drawn, and nothing after it.
            drawn_at_swaps.append(len(noise_kept))
            assert len(block) == bf and len(noise_kept) == i, "the frame at the swap index has not been drawn"
            x = np.array(block, dtype=np.int64).reshape(-1, 1)
            lo = i - bf
            indexes = [r["index"] - lo for r in truth if lo <= r["index"] < i]
            for name in LEARNERS:
                learners[name].add(x, indexes)
                snapshots[name].append({"t": swap, "epoch": swap + 1, "held": list(learners[name].held()),
                                        "records": learners[name].records(),
                                        "blob": handover.candidate_blob(PROFILE, learners[name].weights())})
            hand(core, snapshots["adaptive"][-1]["blob"], i)
            train_samples.extend(block)
            block = array("h")
            swap += 1
        try:
            frame = next(frames)
        except StopIteration:
            break
        out = core.step(frame)
        index = out["index"]
        if index < a:
            block.append(frame[0])
        else:
            held.append(frame[0])
            if (index - a) % STRIDE == STRIDE - 1:
                reads.append(out)
        if index in swap_at:
            swap_epochs.append(out["epoch"])
        if first_new is None and out["epoch"] != 0:
            first_new = index
        if keep_records:
            every.append(out)
        flags |= out["flags"]
        seen += 1
        if progress and seen % progress == 0:
            print("  %d of %d frames" % (seen, length), flush=True)
    assert seen == length and len(truth) == len(schedule) and swap == BLOCKS
    assert records.digest("truth", truth)[0] == digest, "the injector returned the schedule it was handed"
    train = np.frombuffer(train_samples, dtype=np.int16)
    return {"plan": p, "reads": reads, "records": every, "train": train, "held": np.frombuffer(held, dtype=np.int16),
            "noise": np.frombuffer(noise_kept, dtype=np.int16), "truth": truth, "snapshots": snapshots,
            "learners": learners, "flags": flags, "first_new_epoch_index": first_new, "swap_epochs": swap_epochs,
            "drawn_at_swaps": drawn_at_swaps, "injection_sha256": digest}


# ------------------------------------------------------------ the drift, as the frozen model sees it

def drift_counts(p, got):
    """What the frozen filter answers to the samples ADDED at every trial the plan states.

    What was added is the stream less its noise, exactly: the run keeps the noise as the injector drew
    it. The frozen filter's response at a trial's index + 63 is its integers against those samples:
    facts()["response"]["e0"] for an e0 trial, ["e1"] for an e1 one. It reads trained-on frames too:
    it is a check of the stream, not a figure about any model, and no threshold or efficiency comes
    from it.
    """
    f = facts()
    js = np.array(trial_indexes(p), dtype=np.int64)
    windows = js[:, None] + np.arange(TAPS)                       # every trial's 64 frames, and only those
    delta = np.concatenate([got["train"], got["held"]])[windows].astype(np.int64) - got["noise"][windows].astype(np.int64)
    response = delta @ np.array(f["frozen_coeffs"], dtype=np.int64)
    sees = {name: js[response == f["response"][name]] for name in NAMES}
    out = {"frozen_sees_e0": int(sees["e0"].size), "frozen_sees_e1": int(sees["e1"].size),
           "frozen_sees_other": int(js.size - sees["e0"].size - sees["e1"].size),
           "last_e0_index": int(sees["e0"].max()) if sees["e0"].size else None,
           "first_e1_index": int(sees["e1"].min()) if sees["e1"].size else None,
           "e1_before_change": int((sees["e1"] < p["change"]).sum()), "e0_from_change": int((sees["e0"] >= p["change"]).sum())}
    return out


def drift_reasons(p, drift):
    """Why the drift the frozen model sees is not the one the plan names: a list, empty when it is."""
    e0 = CHANGE_BLOCK * p["block_trials"]
    want = {"frozen_sees_e0": e0, "frozen_sees_e1": BLOCKS * p["block_trials"] - e0 + p["n"], "frozen_sees_other": 0,
            "last_e0_index": p["change"] - SPACING + FIRST, "first_e1_index": p["change"] + FIRST,
            "e1_before_change": 0, "e0_from_change": 0}
    return ["the drift: %s is %r, the plan's is %r" % (k, drift.get(k, "missing"), v)
            for k, v in want.items() if drift.get(k, "missing") != v]


def run_reasons(p, part):
    """Why a run's swaps and epochs are not the plan's: a list, empty when they are."""
    want = {"first_new_epoch_index": p["block_frames"], "swap_epochs": list(range(1, BLOCKS + 1)),
            "held_out_epochs": [BLOCKS], "drawn_at_swaps": list(p["swaps"])}
    return ["the run: %s is %r, the plan's is %r" % (k, part.get(k, "missing"), v)
            for k, v in want.items() if part.get(k, "missing") != v]


# ------------------------------------------------------------ the entries on H

def entry_of(p, got, model, g, blob, epoch, reads=None):
    """One model on H: its records (the core's own when `reads` is given, else a replay), its own
    threshold and its hits (E1's functions), and what the judge needs of it."""
    f = facts()
    coeffs = list(handover.coefficients(blob)[0])
    scores = E1.stat_scores_at_reads(got["held"], coeffs)
    recs = E1.records_from(p, scores, epoch) if reads is None else reads
    free, at = E1.split(p, recs)
    e = E1.entry("%s g=%s" % (model, g), free, at, p["A"])
    identical = None if reads is None else bool(stat_matched.scores_are_exact(PROFILE, coeffs) and
                                                [int(v) for v in scores.tolist()] == [r["score"] for r in reads])
    t = e["threshold"]
    return {"model": model, "g": g, "epoch": epoch, "in_stream": reads is not None, "coefficients": coeffs,
            "blob_sha256": weights.unpack(blob)["sha256"], "d_own": theory.deflection(coeffs, f["injected"]["e1"], f["sigma"]),
            "found": int(e["hits"].sum()), "threshold": t["threshold"], "k": t["k"], "above": t["above"], "m": t["m"],
            "threshold_epoch": t["epoch"], "scores_identical_to_stats": identical,
            "core_agrees": bool(E1.core_agrees(p, got["held"], blob, scores)), "_entry": e}


def pair_counts(ref, other):
    """Two entries compared at an equal false-alarm rate (E1's function): the counts the judge needs."""
    s_ref = tolerance.roc_slope((ref["k"] + 1) / (ref["m"] + 1), ref["d_own"])
    s_other = tolerance.roc_slope((other["k"] + 1) / (other["m"] + 1), other["d_own"])
    try:
        pr = E1.compare_at_equal_rate(ref["_entry"], other["_entry"], s_ref, s_other)
    except LearnRefusal as e:
        return {"refused": e.name}
    return {"ref_only": pr["a_only"], "other_only": pr["b_only"], "noise_ref_only": pr["noise_a_only"],
            "noise_other_only": pr["noise_b_only"], "noise_both": pr["noise_both"], "refused": None}


def peak_offset(blob, name):
    """Where the filter's largest score is for a lone, noise-free injection of a pulse, less its truth index."""
    stream, _truth = inject.inject(PROFILE, [(0,)] * 256, [record(64, name)], 256)
    scores = [r["score"] for r in Core(blob).run(stream)]
    return scores.index(max(scores)) - 64


def evaluate(p, got, extra=None):
    """One part's record: everything the judge reads, from the run."""
    f = facts()
    frozen, e1f = entry_of(p, got, "frozen", None, f["frozen_blob"], 0), entry_of(p, got, "e1", None, f["e1_blob"], 0)
    frozen["pairs"], e1f["pairs"] = {}, {"frozen": pair_counts(frozen, e1f)}
    snaps = {model: {s["t"]: s for s in got["snapshots"][model]} for model in LEARNERS}
    judged = {model: [] for model in LEARNERS}
    for t in JUDGED:                # one snapshot of each learner at a time: a full part's records are many
        here = {}
        for model in LEARNERS:
            snap, live = snaps[model][t], model == "adaptive" and t == BLOCKS - 1
            here[model] = entry_of(p, got, model, t - JUDGED[0], snap["blob"], snap["epoch"], got["reads"] if live else None)
            here[model].update(t=t, held_blocks=snap["held"], records=snap["records"])
        for model in LEARNERS:
            other = "reset" if model == "adaptive" else "adaptive"
            here[model]["pairs"] = {"frozen": pair_counts(frozen, here[model]), "e1": pair_counts(e1f, here[model]),
                                    other: pair_counts(here[other], here[model])}
        for model in LEARNERS:
            del here[model]["_entry"]
            judged[model].append(here[model])
    del frozen["_entry"], e1f["_entry"]
    entries = [frozen, e1f] + judged["adaptive"] + judged["reset"]
    stream = hashlib.sha256(got["train"].tobytes() + got["held"].tobytes()).hexdigest()
    part = {"name": p["name"], "seed": p["seed"], "profile": PROFILE, "sigma": list(SIGMA), "pfa": PFA, "amplitude": list(AMPLITUDE),
            "taps": TAPS, "spacing": SPACING, "block_trials": p["block_trials"], "change": p["change"], "A": p["A"], "B": p["B"],
            "length": p["length"], "n": p["n"], "m": p["m"], "keep": KEEP, "reset_period": RESET_PERIOD, "reset_phase": RESET_PHASE,
            "spec_sha256": C.SPEC_SHA256, "injection_sha256": got["injection_sha256"], "stream_sha256": stream,
            "flags": got["flags"], "first_new_epoch_index": got["first_new_epoch_index"], "swap_epochs": got["swap_epochs"],
            "drawn_at_swaps": got["drawn_at_swaps"], "held_out_epochs": sorted({r["epoch"] for r in got["reads"]}),
            "drift": drift_counts(p, got), "d_frozen": f["d_frozen"], "d1": f["d1"], "rate_floor": E1.rate_floor(p["m"]),
            "rate_label": E1.rate_label(PFA, p["m"]), "named": dict(NAMED),
            "peak_offsets": {"frozen on e1": peak_offset(f["frozen_blob"], "e1"), "e1 filter on e1": peak_offset(f["e1_blob"], "e1")},
            "entries": entries}
    part.update(extra or {})
    return part


# ------------------------------------------------------------ the result, and the verdict

def paired(counts, n, m, d_ref, d_other, pfa_effective):
    """(other's found - ref's found) / n on the same injections, and its standard error by LRN-A's
    derivation (two measured thresholds), from a pair's counts. None when the pair was not compared."""
    if counts is None or counts.get("refused") is not None:
        return None
    a_only, b_only = counts["ref_only"], counts["other_only"]
    diff = b_only - a_only
    se_pairs = math.sqrt(max(a_only + b_only - diff * diff / n, 0.0)) / n
    s_a, s_b = tolerance.roc_slope(pfa_effective, d_ref), tolerance.roc_slope(pfa_effective, d_other)
    both = counts["noise_both"]
    k_a, k_b = both + counts["noise_ref_only"], both + counts["noise_other_only"]
    variance = (s_a ** 2 * k_a * (1 - k_a / m) + s_b ** 2 * k_b * (1 - k_b / m) - 2 * s_a * s_b * (both - k_a * k_b / m)) / (m * m)
    se = math.hypot(se_pairs, math.sqrt(max(variance, 0.0)))
    predicted = theory.pd_matched(pfa_effective, d_other) - theory.pd_matched(pfa_effective, d_ref)
    gain = diff / n
    return {"gain": gain, "se": se, "se_pairs": se_pairs, "se_thresholds": math.sqrt(max(variance, 0.0)),
            "predicted": predicted, "z_zero": gain / se if se > 0 else 0.0, "z_predicted": (gain - predicted) / se if se > 0 else 0.0}


def find(part, model, g=None):
    got = [e for e in part["entries"] if e["model"] == model and e["g"] == g]
    return got[0] if len(got) == 1 else None


def result(part):
    """What a part's numbers say, entry by entry, from the part alone."""
    n, m = part["n"], part["m"]
    out = {}
    for e in part["entries"]:
        pe = (e["k"] + 1) / (e["m"] + 1)
        r = {"measured": e["found"] / n, "pfa_effective": pe}
        for check, d in (("own", e["d_own"]), ("best", part["d1"])):
            try:
                r[check] = tolerance.check_efficiency(e["found"], n, pe, d, m)
            except StatRefusal as x:
                r[check], r[check + "_refused"] = None, x.name
        r["gain"] = paired(e["pairs"].get("frozen"), n, m, part["d_frozen"], e["d_own"], pe) if e["model"] != "frozen" else None
        if e["model"] in LEARNERS:
            r["shortfall"] = paired(e["pairs"].get("e1"), n, m, part["d1"], e["d_own"], pe)
            other = "reset" if e["model"] == "adaptive" else "adaptive"
            r["against_" + other] = paired(e["pairs"].get(other), n, m, find(part, other, e["g"])["d_own"], e["d_own"], pe) \
                if find(part, other, e["g"]) else None
        out[(e["model"], e["g"])] = r
    return out


def holds(part, r=None):
    """The verdict's conditions for one part: everything but 'the part is the stated experiment'."""
    r = result(part) if r is None else r
    ok = part["flags"] == 0
    live = [e for e in part["entries"] if e["in_stream"]]
    ok = ok and len(live) == 1 and live[0]["scores_identical_to_stats"] is True
    ok = ok and all(e["core_agrees"] for e in part["entries"])
    ok = ok and all(x["own"] is not None and x["own"]["inside"] for x in r.values())
    frozen = r.get(("frozen", None))
    ok = ok and frozen is not None and frozen["best"] is not None and not frozen["best"]["inside"]
    for model, g in NAMED.items():
        x = r.get((model, g))
        ok = ok and x is not None and x["gain"] is not None and x["gain"]["z_zero"] > GAIN_Z
    return bool(ok)


def report(part, model="adaptive", g=None):
    """A reported model's entry and result. Rule 5: only the models named before the run."""
    g = NAMED.get(model) if g is None else g
    if NAMED.get(model) != g or g is None:
        raise LearnRefusal("NOT_THE_NAMED_MODEL", "%s at g = %r was asked for; the models named before the run are %r"
                           % (model, g, NAMED))
    e = find(part, model, g)
    if e is None:
        raise LearnRefusal("NOT_THE_NAMED_MODEL", "the part has no single entry for %s at g = %d" % (model, g))
    return e, result(part)[(model, g)]


def not_as_stated(parts, parts_wanted=("full",)):
    """Why these parts are not the experiment this file states: a list of reasons, empty when they are.

    Each part is held to what `plan` and `facts` give for it now, and to itself: every entry's blob
    hash and deflection are worked again from the coefficients it carries, every snapshot's blocks
    against the plan's, every pair's counts must add up, its injection set's digest must be the
    committed one, and the drift must be where the plan names it. What it takes on trust: the counts
    themselves, as E1's judge does (docs/model/e2l.md).
    """
    f = facts()
    reasons = []
    if sorted(str(p.get("name")) for p in parts) != sorted(parts_wanted):
        reasons.append("the parts are %s, not exactly %s" % (sorted(str(p.get("name")) for p in parts), sorted(parts_wanted)))
    for part in parts:
        name = part.get("name")
        if name not in parts_wanted:
            continue
        p = plan(name)
        k = int(Fraction(PFA) * p["m"])
        for field, want in (("seed", p["seed"]), ("profile", PROFILE), ("sigma", list(SIGMA)), ("pfa", PFA),
                            ("amplitude", list(AMPLITUDE)), ("taps", TAPS), ("spacing", SPACING), ("block_trials", p["block_trials"]),
                            ("change", p["change"]), ("A", p["A"]), ("B", p["B"]), ("length", p["length"]), ("n", p["n"]),
                            ("m", p["m"]), ("keep", KEEP), ("reset_period", RESET_PERIOD), ("reset_phase", RESET_PHASE),
                            ("spec_sha256", C.SPEC_SHA256), ("injection_sha256", committed_sets()[name]["sha256"]),
                            ("named", NAMED), ("rate_label", E1.rate_label(part.get("pfa", PFA), p["m"]))):
            if part.get(field, "missing") != want:
                reasons.append("part %s: %s is %r, the experiment's is %r" % (name, field, part.get(field, "missing"), want))
        if part.get("rate_label") == "COUNTED" and part.get("pfa", PFA) * p["m"] < E1.FLOOR_CROSSINGS:
            reasons.append("part %s: a false-alarm probability of %r is below the floor of %d crossings in %d scores, and is "
                           "called counted" % (name, part.get("pfa"), E1.FLOOR_CROSSINGS, p["m"]))
        for d, want in (("d_frozen", f["d_frozen"]), ("d1", f["d1"])):
            if abs(part.get(d, 0.0) - want) > 1e-12:
                reasons.append("part %s: %s is %r, the experiment's is %r" % (name, d, part.get(d), want))
        reasons += ["part %s: %s" % (name, x) for x in run_reasons(p, part) + drift_reasons(p, part.get("drift", {}))]
        wanted = [("frozen", None, 0), ("e1", None, 0)] + [(model, t - JUDGED[0], t + 1) for model in LEARNERS for t in JUDGED]
        got = [(e.get("model"), e.get("g"), e.get("epoch")) for e in part.get("entries", [])]
        if got != wanted:
            reasons.append("part %s: its entries are %r, the experiment's are %r" % (name, got, wanted))
            continue
        live = [(e["model"], e["g"]) for e in part["entries"] if e.get("in_stream")]
        if live != [("adaptive", NAMED["adaptive"])]:
            reasons.append("part %s: the entries from the core's own records are %r, not the adaptive's last" % (name, live))
        for e in part["entries"]:
            label = "part %s, %s g=%s" % (name, e["model"], e["g"])
            for field, want in (("k", k), ("above", k), ("m", p["m"]), ("threshold_epoch", e["epoch"])):
                if e.get(field) != want:
                    reasons.append("%s: %s is %r, the experiment's is %r" % (label, field, e.get(field), want))
            coeffs = e.get("coefficients")
            try:
                blob = weights.pack(PROFILE, [{0: tuple(coeffs)}], (1,), C.RECTIFIERS["pass"], 1, 0)
                sha, d = weights.unpack(blob)["sha256"], theory.deflection(coeffs, f["injected"]["e1"], f["sigma"])
            except (Refusal, StatRefusal, TypeError):
                sha, d = None, None
            if sha is None or len(coeffs) != TAPS or e.get("blob_sha256") != sha:
                reasons.append("%s: its blob hash is not the hash of the coefficients it carries" % label)
            if d is None or abs(e.get("d_own", 0.0) - d) > 1e-12:
                reasons.append("%s: d_own is %r; its coefficients give %r" % (label, e.get("d_own"), d))
            if e["model"] == "frozen" and e.get("blob_sha256") != weights.unpack(f["frozen_blob"])["sha256"]:
                reasons.append("%s: it is not the frozen blob" % label)
            if e["model"] == "e1" and e.get("blob_sha256") != weights.unpack(f["e1_blob"])["sha256"]:
                reasons.append("%s: it is not the e1 filter's blob" % label)
            if e["model"] in LEARNERS:
                t = e["g"] + JUDGED[0]
                if e.get("t") != t or e.get("held_blocks") != held_blocks(e["model"], t) or \
                        e.get("records") != p["block_trials"] * len(held_blocks(e["model"], t)):
                    reasons.append("%s: made from blocks %r (%r records); the plan's are %r" % (label, e.get("held_blocks"),
                                   e.get("records"), held_blocks(e["model"], t)))
            for ref, counts in sorted(e.get("pairs", {}).items()):
                other = find(part, ref) if ref in ("frozen", "e1") else find(part, ref, e["g"])
                c = [counts.get(x) for x in ("ref_only", "other_only", "noise_ref_only", "noise_other_only", "noise_both")]
                if counts.get("refused") is not None or other is None or not all(type(v) is int and v >= 0 for v in c) \
                        or e["found"] != other["found"] - c[0] + c[1] or c[2] != c[3] or c[2] + c[4] != k:
                    reasons.append("%s: against %s, its counts are not an equal-rate comparison that adds up: %r" % (label, ref, counts))
        a4, r4 = find(part, "adaptive", 4), find(part, "reset", 4)
        if a4["blob_sha256"] != r4["blob_sha256"]:
            reasons.append("part %s: at g = 4 the two learners hold the same blocks and their blobs differ" % name)
        if part.get("peak_offsets") != {"frozen on e1": TAPS - 1, "e1 filter on e1": TAPS - 1}:
            reasons.append("part %s: peaks %r, not at the truth index + 63" % (name, part.get("peak_offsets")))
    return reasons


def judge_parts(paths, parts_wanted=("full",)):
    parts = []
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            parts.append(json.load(fh))
    reasons = not_as_stated(parts, parts_wanted)
    ok = not reasons
    f = facts()
    print("E2 in software: profile %s, sigma %d/%d, Pfa %.2f, amplitude %d/%d; the frozen filter's d is %.4f on e0 and %.4f "
          "on e1; the e1 filter's %.4f" % (PROFILE, SIGMA[0], SIGMA[1], PFA, AMPLITUDE[0], AMPLITUDE[1],
                                           E1.facts()["d"], f["d_frozen"], f["d1"]))

    def said(v):
        return "REFUSED by the statistics" if v is None else "%.4f %+.2f se %s" % (v["expected"], v["z_score"],
                                                                                    "INSIDE" if v["inside"] else "OUTSIDE")

    def gained(v):
        return "not compared" if v is None else "%+.5f se %.5f (z %+.1f); predicted %+.5f (%+.2f se)" % (
            v["gain"], v["se"], v["z_zero"], v["predicted"], v["z_predicted"])
    for part in parts:
        wanted = [("frozen", None), ("e1", None)] + [(model, g) for model in LEARNERS for g in range(len(JUDGED))]
        if any(find(part, model, g) is None for model, g in wanted):
            ok = False
            print("  part %s: not every model and snapshot has one entry; nothing of it is read" % part.get("name"))
            continue
        r = result(part)
        ok = ok and holds(part, r)
        print("  part %s, seed %d: %d held-out injections of e1, %d signal-free reads, k %d" % (part["name"], part["seed"],
              part["n"], part["m"], find(part, "frozen")["k"]))
        for model, label in (("frozen", "the frozen model"), ("e1", "the e1 filter")):
            e, x = find(part, model), r[(model, None)]
            print("  %-16s found %d of %d (%.5f); against its own D8 %s; against the e1 filter's %s"
                  % (label, e["found"], part["n"], x["measured"], said(x["own"]), said(x["best"])))
        for model in LEARNERS:
            print("  the %s model, g = labelled windows after the change / 256:" % model)
            for g in range(len(JUDGED)):
                e, x = find(part, model, g), r[(model, g)]
                print("    g %d (%4d windows) blocks %s: found %d (%.5f), own %s; best %s; gain over frozen %s"
                      % (g, 256 * g, "%d-%d" % (e["held_blocks"][0], e["held_blocks"][-1]), e["found"], x["measured"],
                         said(x["own"]), said(x["best"]), gained(x["gain"])))
            inside = [g for g in range(len(JUDGED)) if r[(model, g)]["best"] is not None and r[(model, g)]["best"]["inside"]]
            outside = [g for g in range(len(JUDGED)) if g not in inside]
            takes = [g for g in inside if all(g > o for o in outside)]
            print("    one reading, at the tolerance's resolution: every snapshot from %s on is inside the e1 filter's figure"
                  % ("%d labelled windows after the change" % (256 * min(takes)) if takes else "none of these"))
        print("  the adaptive less the reset model at each g: %s" % "; ".join(
            "%d %s" % (g, "n/a" if r[("adaptive", g)]["against_reset"] is None else "%+.4f (se %.4f)" % (
                r[("adaptive", g)]["against_reset"]["gain"], r[("adaptive", g)]["against_reset"]["se"])) for g in range(len(JUDGED))))
        print("  the instrument: flags %s; the adaptive's reads identical to the statistics': %s; the core equal to each "
              "replay on the first %d trials: %s; the drift as the frozen model sees it: %d e0 trials to index %s, %d e1 "
              "from %s; peaks %s; a rate of %.2f in %d reads is %s"
              % (part["flags"], [e["scores_identical_to_stats"] for e in part["entries"] if e["in_stream"]], CORE_CHECK,
                 "yes" if all(e["core_agrees"] for e in part["entries"]) else "NO", part["drift"]["frozen_sees_e0"],
                 part["drift"]["last_e0_index"], part["drift"]["frozen_sees_e1"], part["drift"]["first_e1_index"],
                 part["peak_offsets"], part["pfa"], part["m"], part["rate_label"]))
        for model in LEARNERS:
            try:
                e, x = report(part, model)
                print("  THE REPORTED MODEL, named before the run: the %s model at g = %d (%d labelled windows after the "
                      "change): found %d of %d, %.5f; against the e1 filter's figure %s; gain over the frozen model %s"
                      % (model, e["g"], 256 * e["g"], e["found"], part["n"], x["measured"], said(x["best"]), gained(x["gain"])))
            except LearnRefusal as err:
                ok = False
                print("  THE REPORTED MODEL: refused, %s" % err)
    print("  the parts against the experiment as this file states it: %s" % ("as stated" if not reasons else "NOT AS STATED"))
    for reason in reasons:
        print("    " + reason)
    print("== E2 SOFTWARE VERDICT: %s" % ("PASS, each named model recovers events the frozen model misses" if ok else "FAIL"))
    return 0 if ok else 1


def full_part(out):
    p = plan("full")
    print("E2 full run: %d frames, seed %d, change at %d, held out from %d" % (p["length"], p["seed"], p["change"], p["A"]), flush=True)
    part = evaluate(p, measure(p, progress=SPACING * 20000))
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(part, fh, indent=1)
        fh.write("\n")
    print("wrote %s" % out)
    return part


def main(argv):
    if "--judge" in argv:
        return judge_parts(argv[argv.index("--judge") + 1:])
    if "--full" in argv:
        full_part(argv[argv.index("--out") + 1] if "--out" in argv else "e2-part.json")
        return 0
    print(__doc__)
    return 2


# ------------------------------------------------------------ the gate's short form

_short = {}


def short():
    if not _short:
        got = measure(plan("short"))
        _short.update(got=got, part=evaluate(plan("short"), got))
    return _short["got"], _short["part"]


SMALL = make_plan("small", 2, 4, 4, SHORT_SEED)


def small_run(**kwargs):
    schedule = kwargs.pop("schedule", schedule_for(SMALL))
    return measure(SMALL, schedule=schedule, committed=kwargs.pop("committed", own_digest(SMALL, schedule)), **kwargs)


def moved(schedule, index, name):
    """The schedule with the record at `index` carrying another pulse."""
    return [dict(r, pulse_id=C.PULSE_IDS[name]) if r["index"] == index else r for r in schedule]


def test_e2l_drift_the_setup_is_the_one_stated():
    for form, want in (("short", (774144, 1286144, 12000, 2026112701)), ("full", (13062144, 25862144, 300000, 2026112700))):
        p = plan(form)
        assert (p["B"], p["length"], p["m"], p["seed"]) == want, form
        assert (p["A"], p["change"], p["block_frames"]) == (262144, 131072, 16384) and p["swaps"][-1] == p["A"]
        assert len(schedule_for(p)) == 2048 + p["n"] and schedule_for(p)[-1]["index"] == p["length"] - TAPS
    assert resets() == [4, 12] and int(Fraction(PFA) * 12000) == 120 and int(Fraction(PFA) * 300000) == 3000
    assert [held_blocks("adaptive", t) for t in (7, 11, 15)] == [list(range(0, 8)), list(range(4, 12)), list(range(8, 16))]
    assert [held_blocks("reset", t) for t in (3, 7, 11, 12, 15)] == [[0, 1, 2, 3], [4, 5, 6, 7], list(range(4, 12)), [12],
                                                                     [12, 13, 14, 15]]
    assert (PROFILE, SIGMA, PFA, SPACING, FIRST, TAPS, STRIDE) == ("s16x1", (1477, 1), 0.01, 128, 64, 64, 64), "E1's own"
    # the second pulse, as the design worked it (the round's ledger, 12:26): the sums of its integers
    e0, e1 = list(C.PULSES["e0"]), list(C.PULSES["e1"])
    assert len(e1) == 64 and C.PULSE_IDS == {"e0": 0, "e1": 1}
    ee, e11, e01 = sum(v * v for v in e0), sum(v * v for v in e1), sum(a * b for a, b in zip(e0, e1))
    assert (ee, e11, e01) == (11811446, 11810537, 5904898)
    assert abs(e01 / math.sqrt(ee * e11) - 0.499949) < 1e-6 and max(abs(v) for v in e1) == 1213 == -e1[30]
    assert [i for i, v in enumerate(e1) if v == 0] == [0, 8, 16, 24, 32, 40, 48, 56, 63]
    f = facts()
    assert (f["response"]["e0"], f["response"]["e1"]) == (1596020322, 797899764)
    assert abs(f["d_frozen"] - 1.163271) < 1e-5 and abs(f["d1"] - 2.326775) < 1e-5
    assert abs(theory.pd_matched(PFA, f["d_frozen"]) - 0.1224) < 1e-4 and abs(theory.pd_matched(PFA, f["d1"]) - 0.5002) < 1e-4
    # nineteen seeds with E0's ten and E1's seven, and no two streams share a word of the generator's cycle
    seeds = [2026112500 + c for c in range(6)] + [2026112600] + [2026112300 + k for k in range(5)] + \
            [2026112400 + k for k in range(5)] + [FULL_SEED, SHORT_SEED]
    assert len(set(seeds)) == 19
    inverse = pow(source.GAMMA, -1, 1 << 64)
    apart = min(min((x - y) * inverse % (1 << 64), (y - x) * inverse % (1 << 64)) for x in seeds for y in seeds if x != y)
    assert apart > 1 << 57 and plan("full")["length"] < 1 << 25
    short_t = tolerance.tolerance(121 / 12001, f["d1"], 4000, 12000)
    full_t = tolerance.tolerance(3001 / 300001, f["d1"], 100000, 300000)
    assert 0.0627 < short_t["tolerance"] < 0.0629 and 0.01257 < full_t["tolerance"] < 0.01259


# ------------------------------------------------------------ rule 1

def test_gate_comparison_rules__e2_rule_1_every_injection_set_is_the_committed_one_by_two_implementations():
    sets = committed_sets()
    assert sorted(sets) == ["full", "short"]
    for form in ("short", "full"):
        p = plan(form)
        schedule = schedule_for(p)
        want = sets[form]
        assert (want["A"], want["B"], want["length"], want["change_index"], want["calibration_scores"], want["test_trials"]) == \
            (p["A"], p["B"], p["length"], p["change"], p["m_cal"], p["n"])
        assert E1.independent_digest(schedule) == (want["sha256"], want["records"]) == records.digest("truth", schedule)
        assert (want["e0_records"], want["last_e0_index"], want["first_e1_index"]) == (1024, 131008, 131136)
        assert schedule[-1]["index"] == want["last_index"]
        assert check_injection_set(p, schedule) == want["sha256"]
    assert sets["short"]["sha256"] == "dde5210c7325985a5493a3df3256b718ffaa6243c6fe15dba477cef4bee11c32", "the ledger's, 12:31"
    assert sets["full"]["sha256"] == "beb3d9ceffbed498e38724725b5aa1c28ec19f6b8ac0088fdc5efb40860f680b", "the ledger's, 12:31"


def test_control_comparison_rules__e2_rule_1_another_injection_set_is_refused_before_a_frame_is_drawn(monkeypatch):
    p = plan("short")
    good = schedule_for(p)
    early, late = p["change"] - SPACING + FIRST, p["change"] + FIRST
    others = {
        "the drift one trial early": moved(good, early, "e1"),
        "the drift one trial late": moved(good, late, "e0"),
        "one amplitude changed": [dict(r, amplitude_num=2) if i == 3000 else r for i, r in enumerate(good)],
        "one index a sample later": [dict(r, index=r["index"] + 1) if i == 5 else r for i, r in enumerate(good)],
        "one injection dropped": good[:-1],
        "one injection added": good + [dict(good[-1], index=good[-1]["index"] + SPACING)],
        "the other form's set": schedule_for(plan("full")),
        "no injection at all": [],
    }

    class NoFrame:
        def __init__(self, *args):
            raise AssertionError("a frame source was made: the run was not refused before a frame was drawn")

    monkeypatch.setattr(source, "Noise", NoFrame)
    for what, schedule in others.items():
        with pytest.raises(LearnRefusal) as e:
            measure(p, schedule=schedule)
        print("CONTROL E2 rule 1, %s: refused, %s" % (what, str(e.value)[:140]))
        assert e.value.name == "INJECTION_SET", what
    assert len(others["the drift one trial early"]) == len(good), "the check is of the set, not of its count"
    with pytest.raises(AssertionError, match="a frame source was made"):
        measure(p)
    with pytest.raises(LearnRefusal) as e:
        measure(make_plan("unknown", 2, 4, 4, 1))
    assert e.value.name == "INJECTION_SET"


# ------------------------------------------------------------ rule 2

def test_gate_comparison_rules__e2_rule_2_every_figure_is_read_from_the_held_out_stretch():
    got, part = short()
    p = got["plan"]
    a = p["A"]
    assert len(got["train"]) == a and len(got["held"]) == p["length"] - a and len(got["noise"]) == p["length"]
    assert got["drawn_at_swaps"] == p["swaps"], "at each swap the frames below it, and only those, had been drawn"
    for name in LEARNERS:
        assert [s["t"] for s in got["snapshots"][name]] == list(range(BLOCKS))
        assert all(max(s["held"]) == s["t"] < BLOCKS for s in got["snapshots"][name]), "a snapshot holds no block after its own"
    assert max(r["index"] for r in got["truth"] if r["index"] < a) + TAPS == a, "the last training pulse ends at frame A - 1"
    indexes = [r["index"] for r in got["reads"]]
    assert min(indexes) == a + TAPS - 1 and len(indexes) == p["m_cal"] + 2 * p["n"]
    assert all(y - x == STRIDE for x, y in zip(indexes, indexes[1:])), "no two read windows share a frame"
    theirs = recovery.signal_free_indexes(p["length"], TAPS, [r["index"] for r in got["truth"]], TAPS)
    assert theirs[theirs >= a + TAPS - 1].tolist() == sorted(E1.free_positions(p).tolist()) and len(E1.free_positions(p)) == p["m"]
    assert run_reasons(p, part) == []


def test_control_comparison_rules__e2_rule_2_a_figure_from_frames_a_learner_trained_on_is_refused():
    got, _part = short()
    p = got["plan"]
    a = p["A"]
    free, at = E1.split(p, got["reads"])
    t = E1.threshold_record(free, a)
    for low in (a + TAPS - 2, a - 1, FIRST + TAPS - 1, p["change"] + FIRST + TAPS - 1):
        reached = dict(at[0], index=low)
        for call in (lambda: E1.hits([reached] + at[1:], t, a), lambda: E1.threshold_record([reached] + free[1:], a)):
            with pytest.raises(LearnRefusal) as e:
                call()
            assert e.value.name == "TRAINED_ON", low
    print("CONTROL E2 rule 2: records at %d, %d, %d and %d, each refused TRAINED_ON"
          % (a + TAPS - 2, a - 1, FIRST + TAPS - 1, p["change"] + FIRST + TAPS - 1))
    # the learner handed a block that holds a held-out truth record refuses it, and keeps nothing of it
    w = adaptive.Window(1, TAPS, KEEP)
    with pytest.raises(LearnRefusal) as e:
        w.add(got["train"][-p["block_frames"]:].astype(np.int64).reshape(-1, 1), [FIRST, p["B"] + FIRST - (a - p["block_frames"])])
    print("CONTROL E2 rule 2: a held-out truth record handed to the adaptive learner: %s" % str(e.value)[:120])
    assert e.value.name == "WINDOW_OUTSIDE_PERIOD" and w.held() == ()


# ------------------------------------------------------------ rule 3

def test_gate_comparison_rules__e2_rule_3_each_model_its_own_threshold_at_the_same_false_alarm_rate():
    _got, part = short()
    assert all((e["k"], e["above"], e["m"]) == (120, 120, 12000) for e in part["entries"])
    assert all(e["threshold_epoch"] == e["epoch"] for e in part["entries"])
    assert len({e["threshold"] for e in part["entries"]}) >= 18, "each model its own threshold"
    assert all(c.get("refused") is None for e in part["entries"] for c in e["pairs"].values())
    assert part["rate_label"] == "COUNTED" and part["rate_floor"] == 10 / 12000
    assert E1.rate_label(PFA, 300000) == "COUNTED" and E1.rate_label(9.99 / 12000, 12000) == "EXTRAPOLATION"
    print("E2 short form, rule 3: thresholds frozen %.0f, e1 filter %.0f, the adaptive's g = 8 %.0f, each with 120 of 12,000 above"
          % (find(part, "frozen")["threshold"], find(part, "e1")["threshold"], find(part, "adaptive", 8)["threshold"]))


def test_control_comparison_rules__e2_rule_3_a_comparison_at_an_equal_threshold_is_refused():
    got, _part = short()
    p = got["plan"]
    a = p["A"]
    f = facts()

    def model(name, coeffs, epoch):
        free, at = E1.split(p, E1.records_from(p, E1.stat_scores_at_reads(got["held"], coeffs), epoch))
        return dict(E1.entry(name, free, at, a), at=at)

    slope = tolerance.roc_slope(121 / 12001, f["d1"])
    frozen, e1f = model("frozen", f["frozen_coeffs"], 0), model("the e1 filter", f["e1_coeffs"], 0)
    half = model("the frozen filter's first half", f["frozen_coeffs"][:TAPS // 2] + [0] * (TAPS // 2), 0)
    learned = model("the adaptive's g = 8", list(handover.coefficients(got["snapshots"]["adaptive"][-1]["blob"])[0]), 0)
    shown = 0
    for mine, theirs in ((frozen, e1f), (e1f, frozen), (learned, frozen), (frozen, learned), (half, frozen), (frozen, half)):
        assert E1.compare_at_equal_rate(theirs, mine, slope, slope)["m"] == 12000, "each at its own threshold, compared"
        shared = dict(mine, threshold=dict(theirs["threshold"]), hits=E1.hits(mine["at"], theirs["threshold"], a))
        above = sum(1 for r in mine["free"] if r["score"] > theirs["threshold"]["threshold"])
        print("CONTROL E2 rule 3: %s counted at the threshold of %s: %d of 12,000 of its signal-free scores above it, where an "
              "equal rate is 120; it would have found %d of 4,000 there, and %d at its own"
              % (mine["name"], theirs["name"], above, int(shared["hits"].sum()), int(mine["hits"].sum())))
        if above == 120:
            assert "first half" not in mine["name"] + theirs["name"]
            print("CONTROL E2 rule 3: that pair's shared threshold happens to give the same rate: it shows nothing, and is not asserted")
            continue
        for x, y in ((theirs, shared), (shared, theirs)):
            with pytest.raises(LearnRefusal) as e:
                E1.compare_at_equal_rate(x, y, slope, slope)
            assert e.value.name == "UNEQUAL_FALSE_ALARM_RATE"
        shown += 1
    assert shown >= 2
    assert sum(1 for r in half["free"] if r["score"] > frozen["threshold"]["threshold"]) < 60
    assert sum(1 for r in frozen["free"] if r["score"] > half["threshold"]["threshold"]) > 240
    # a threshold of another epoch: the frozen model's (epoch 0) on the adaptive's own records (epoch 16)
    free, at = E1.split(p, got["reads"])
    with pytest.raises(LearnRefusal) as e:
        E1.hits(at, frozen["threshold"], a)
    assert e.value.name == "THRESHOLD_STALE" and {r["epoch"] for r in at} == {BLOCKS}
    with pytest.raises(LearnRefusal) as e:
        E1.threshold_record(free[:-1] + [dict(free[-1], epoch=BLOCKS - 1)], a)
    assert e.value.name == "THRESHOLD_MIXED"


# ------------------------------------------------------------ rule 5, and the judge

def test_gate_comparison_rules__e2_rule_5_the_reported_models_are_the_named_ones(tmp_path, capsys):
    _got, part = short()
    for model in LEARNERS:
        e, _r = report(part, model)
        assert e["g"] == NAMED[model] == 8 and e["held_blocks"][-1] == BLOCKS - 1
    assert part["named"] == NAMED
    assert not_as_stated([part], ("short",)) == []
    path = tmp_path / "short.json"
    path.write_text(json.dumps(part), encoding="utf-8")
    code = judge_parts([str(path)], ("short",))
    out = capsys.readouterr().out
    assert code == 0 and "== E2 SOFTWARE VERDICT: PASS" in out and "NOT AS STATED" not in out
    assert "THE REPORTED MODEL, named before the run: the adaptive model at g = 8" in out
    assert "THE REPORTED MODEL, named before the run: the reset model at g = 8" in out


def test_control_comparison_rules__e2_rule_5_the_best_of_several_snapshots_is_refused():
    _got, part = short()
    r = result(part)
    for model in LEARNERS:
        best = max(range(len(JUDGED)), key=lambda g: r[(model, g)]["measured"])
        asked = best if best != NAMED[model] else NAMED[model] - 1      # the best snapshot, or the one before the named
        with pytest.raises(LearnRefusal) as e:
            report(part, model, asked)
        print("CONTROL E2 rule 5: the %s model's best snapshot is g = %d (%.4f; the named g = 8, %.4f); g = %d asked for: %s"
              % (model, best, r[(model, best)]["measured"], r[(model, 8)]["measured"], asked, str(e.value)[:80]))
        assert e.value.name == "NOT_THE_NAMED_MODEL"
    for model, g in (("adaptive", 0), ("reset", 5), ("frozen", None), ("e1", None), ("adaptive", "8")):
        with pytest.raises(LearnRefusal) as e:
            report(part, model, g)
        assert e.value.name == "NOT_THE_NAMED_MODEL", (model, g)
    marked = json.loads(json.dumps(part))
    marked["named"] = {"adaptive": 7, "reset": 8}
    assert any("named is" in x for x in not_as_stated([marked], ("short",)))


def test_control_comparison_rules__e2_the_judge_fails_parts_that_are_not_the_stated_experiment(tmp_path, capsys):
    """Each change leaves every model's found count as it was: a judge that read only those would pass each."""
    _got, part = short()

    def entry(ps, model, g=None):
        return find(ps, model, g)

    changes = {
        "another seed": lambda ps: ps.__setitem__("seed", FULL_SEED),
        "another injection set": lambda ps: ps.__setitem__("injection_sha256", committed_sets()["full"]["sha256"]),
        "another definition": lambda ps: ps.__setitem__("spec_sha256", "0" * 64),
        "a swap one index late": lambda ps: ps.__setitem__("first_new_epoch_index", ps["first_new_epoch_index"] + 1),
        "a swap missing": lambda ps: ps.__setitem__("swap_epochs", ps["swap_epochs"][:-1]),
        "never swapped over H": lambda ps: ps.__setitem__("held_out_epochs", [0]),
        "the drift a trial early": lambda ps: ps["drift"].update(e1_before_change=1),
        "a snapshot of other blocks": lambda ps: entry(ps, "reset", 5).update(held_blocks=[11, 12]),
        "a window of 7 blocks": lambda ps: entry(ps, "adaptive", 3).update(held_blocks=list(range(4, 11)), records=896),
        "other coefficients": lambda ps: entry(ps, "adaptive", 8).update(coefficients=list(reversed(entry(ps, "adaptive", 8)["coefficients"]))),
        "another deflection": lambda ps: entry(ps, "reset", 2).update(d_own=entry(ps, "reset", 2)["d_own"] + 1e-6),
        "a tie at a threshold": lambda ps: entry(ps, "adaptive", 1).update(above=119),
        "a threshold of another epoch": lambda ps: entry(ps, "reset", 4).update(threshold_epoch=0),
        "counts that do not add up": lambda ps: entry(ps, "adaptive", 6)["pairs"]["frozen"].update(other_only=1),
        "a comparison refused": lambda ps: entry(ps, "reset", 0)["pairs"]["e1"].update(refused="UNEQUAL_FALSE_ALARM_RATE"),
        "an entry missing": lambda ps: ps["entries"].pop(),
        "the frozen model is another blob": lambda ps: entry(ps, "frozen").update(blob_sha256=entry(ps, "e1")["blob_sha256"],
                                                                                    coefficients=entry(ps, "e1")["coefficients"]),
        "a replay called the core's own": lambda ps: entry(ps, "reset", 8).update(in_stream=True),
        "a rate below the floor called counted": lambda ps: ps.__setitem__("pfa", 5e-4),
        "another named model": lambda ps: ps.__setitem__("named", {"adaptive": 7, "reset": 8}),
    }
    for what, change in changes.items():
        ps = json.loads(json.dumps(part))
        change(ps)
        reasons = not_as_stated([ps], ("short",))
        assert reasons, what
        path = tmp_path / ("%d.json" % len(os.listdir(tmp_path)))
        path.write_text(json.dumps(ps), encoding="utf-8")
        code = judge_parts([str(path)], ("short",))
        out = capsys.readouterr().out
        assert code == 1 and "NOT AS STATED" in out and "== E2 SOFTWARE VERDICT: FAIL" in out, what
    # and each of the verdict's own conditions fails alone, the part otherwise as stated
    def flagged(ps):
        ps["flags"] = 2

    def not_identical(ps):
        entry(ps, "adaptive", 8)["scores_identical_to_stats"] = False

    def core_differs(ps):
        entry(ps, "reset", 3)["core_agrees"] = False

    def frozen_finds_what_the_e1_filter_finds(ps):     # fails the frozen model's own check and the drift's both
        fz = entry(ps, "frozen")
        extra = 2000 - fz["found"]
        fz["found"] += extra
        for e in ps["entries"]:
            if e["model"] != "frozen" and "frozen" in e["pairs"]:
                e["pairs"]["frozen"]["ref_only"] += extra

    def named_adaptive_finds_what_frozen_finds(ps):    # fails its own check and the named gain both
        ad, fz = entry(ps, "adaptive", 8), entry(ps, "frozen")
        drop = ad["found"] - fz["found"]
        ad["found"] = fz["found"]
        ad["pairs"]["frozen"]["other_only"] -= drop
        for ref in ("e1", "reset"):
            ad["pairs"][ref]["ref_only"] += drop
        entry(ps, "reset", 8)["pairs"]["adaptive"]["other_only"] += drop    # the reset's g = 8 is compared with it too

    for change in (flagged, not_identical, core_differs, frozen_finds_what_the_e1_filter_finds,
                   named_adaptive_finds_what_frozen_finds):
        ps = json.loads(json.dumps(part))
        change(ps)
        assert not_as_stated([ps], ("short",)) == [], change.__name__
        assert not holds(ps), change.__name__
    assert holds(part)


def test_control_statistics__e2_the_named_gain_is_in_the_verdict_on_its_own(monkeypatch):
    """The part as it is, and the verdict's one condition on the gain asked for more than any gain
    here has: only that condition changes, and the verdict fails."""
    _got, part = short()
    assert holds(part)
    r = result(part)
    z = min(r[(model, g)]["gain"]["z_zero"] for model, g in NAMED.items())
    monkeypatch.setattr(sys.modules[__name__], "GAIN_Z", z + 0.01)
    print("CONTROL E2 the named gain: the smaller of the two named gains is %.1f standard errors; asked for %.2f, the verdict "
          "fails" % (z, z + 0.01))
    assert not holds(part)


# ------------------------------------------------------------ the short form's result

def test_gate_statistics__e2_the_short_form():
    got, part = short()
    p = got["plan"]
    assert not_as_stated([part], ("short",)) == []
    assert part["flags"] == 0 and part["first_new_epoch_index"] == p["block_frames"] and part["held_out_epochs"] == [BLOCKS]
    r = result(part)

    def said(v):
        return "%.4f %+.2f se %s" % (v["expected"], v["z_score"], "INSIDE" if v["inside"] else "OUTSIDE")
    print("E2 short form: seed %d, change at %d, %d held-out injections of e1, %d signal-free reads"
          % (p["seed"], p["change"], p["n"], p["m"]))
    for model in ("frozen", "e1"):
        e, x = find(part, model), r[(model, None)]
        print("E2 short form: %s found %d of %d (%.4f); own %s; against the e1 filter's figure %s"
              % (model, e["found"], p["n"], x["measured"], said(x["own"]), said(x["best"])))
    for model in LEARNERS:
        for g in range(len(JUDGED)):
            e, x = find(part, model, g), r[(model, g)]
            gn = x["gain"]
            print("E2 short form: %s g %d (%d windows after the change): found %d (%.4f); own %s; best %s; gain over frozen "
                  "%+.4f, se %.4f (pairs %.4f, thresholds %.4f), z %+.1f; its integers predict %+.4f"
                  % (model, g, 256 * g, e["found"], x["measured"], said(x["own"]), said(x["best"]), gn["gain"], gn["se"],
                     gn["se_pairs"], gn["se_thresholds"], gn["z_zero"], gn["predicted"]))
    frozen_found = find(part, "frozen")["found"]
    for model in LEARNERS + ("e1",):
        for g in (range(len(JUDGED)) if model in LEARNERS else (None,)):
            gn = r[(model, g)]["gain"]
            assert gn["gain"] == (find(part, model, g)["found"] - frozen_found) / p["n"], "the gain is the two counts' difference"
            assert abs(gn["z_predicted"]) < 4.0, "each gain within four of its standard errors of what its integers predict"
    assert all(x["own"]["inside"] for x in r.values()), "the instrument counts every model as D8 says for its own integers"
    assert r[("e1", None)]["best"]["inside"] and not r[("frozen", None)]["best"]["inside"], "the drift is there, and seen"
    for model, g in NAMED.items():
        assert r[(model, g)]["gain"]["z_zero"] > GAIN_Z, "the named %s recovers events the frozen model misses" % model
    assert 0.0627 < r[("e1", None)]["best"]["tolerance"] < 0.0629
    assert holds(part, r)
    a4, r4 = find(part, "adaptive", 4), find(part, "reset", 4)
    assert a4["blob_sha256"] == r4["blob_sha256"] and a4["found"] == r4["found"], "at g = 4 the two hold the same blocks"


def test_gate_statistics__e2_the_frozen_and_e1_filters_peak_where_they_are_read():
    f = facts()
    assert peak_offset(f["frozen_blob"], "e1") == peak_offset(f["e1_blob"], "e1") == peak_offset(f["frozen_blob"], "e0") == TAPS - 1
    _got, part = short()
    assert peak_offset(weights.pack(PROFILE, [{0: tuple(find(part, "adaptive", 8)["coefficients"])}], (1,),
                                    C.RECTIFIERS["pass"], 1, 0), "e1") == TAPS - 1


def test_gate_statistics__e2_model_2_frozen_with_its_input_scaling_updated_is_the_frozen_model():
    """A positive gain on the coefficients quantises to the frozen blob byte for byte; a gain on the
    score (a head weight of 3) multiplies every score by 3 and, at its own threshold, finds exactly the
    injections the frozen model finds. A gain of -1 is the control: another blob, another count."""
    f = facts()
    for gain in (2, Fraction(3, 2), 7, 1477, Fraction(1, 3)):
        assert weights.matched_filter(PROFILE, C.PULSES["e0"], (gain,)) == f["frozen_blob"], gain
    got, part = short()
    p = got["plan"]
    a = p["A"]
    scaled = weights.pack(PROFILE, [{0: tuple(f["frozen_coeffs"])}], (3,), C.RECTIFIERS["pass"], 1, 0)
    base = E1.stat_scores_at_reads(got["held"], f["frozen_coeffs"])
    assert E1.core_agrees(p, got["held"], scaled, 3 * base), "the core holding the head weight of 3 scores three times as high"
    frozen = E1.entry("frozen", *E1.split(p, E1.records_from(p, base, 0)), a)
    three = E1.entry("scaled", *E1.split(p, E1.records_from(p, 3 * base, 0)), a)
    assert three["threshold"]["threshold"] == 3 * frozen["threshold"]["threshold"]
    assert three["hits"].tolist() == frozen["hits"].tolist() and int(three["hits"].sum()) == find(part, "frozen")["found"]
    negated = weights.matched_filter(PROFILE, C.PULSES["e0"], (-1,))
    assert negated != f["frozen_blob"]
    neg = E1.entry("negated", *E1.split(p, E1.records_from(p, -base, 0)), a)
    print("CONTROL E2 model 2: a gain of -1 is another blob, and finds %d of %d where the frozen model finds %d"
          % (int(neg["hits"].sum()), p["n"], int(frozen["hits"].sum())))
    assert int(neg["hits"].sum()) < int(frozen["hits"].sum()) / 4


def test_gate_comparison_rules__e2_each_snapshot_is_the_learner_on_its_named_blocks():
    """Each snapshot made again, from the kept training frames, by a MeanDifference on exactly the
    plan's blocks: the same blob. A window of 7 blocks and a reset a block late give other blobs."""
    got, part = short()
    p = got["plan"]
    bf = p["block_frames"]
    x = got["train"].astype(np.int64).reshape(-1, 1)
    local = [FIRST + SPACING * i for i in range(p["block_trials"])]

    def blob_of(blocks):
        learner = trainer.MeanDifference(1, TAPS)
        for b in blocks:
            trainer.train(x[b * bf:(b + 1) * bf], local, TAPS, learner)
        return weights.unpack(handover.candidate_blob(PROFILE, learner.weights()))["sha256"]

    for model in LEARNERS:
        for t in JUDGED:
            assert find(part, model, t - JUDGED[0])["blob_sha256"] == blob_of(held_blocks(model, t)), (model, t)
    wrong = {"a window of 7 blocks at g = 3": (blob_of(range(4, 11)), find(part, "adaptive", 3)),
             "a reset a block late at g = 5": (blob_of(range(4, 13)), find(part, "reset", 5)),
             "a reset a block early at g = 8": (blob_of(range(11, 16)), find(part, "reset", 8))}
    for what, (sha, e) in wrong.items():
        print("CONTROL E2 snapshots, %s: blob %s..., the part's %s..." % (what, sha[:12], e["blob_sha256"][:12]))
        assert sha != e["blob_sha256"], what


# ------------------------------------------------------------ the named controls on a small plan

def test_control_statistics__e2_an_adaptive_model_that_never_swaps_equals_its_starting_model():
    f = facts()
    withheld = small_run(hand=lambda core, blob, at: None, keep_records=True)
    stream = [(int(v),) for v in np.concatenate([withheld["train"], withheld["held"]]).tolist()]
    frozen = list(Core(f["frozen_blob"]).run(stream))
    assert withheld["records"] == frozen and len(frozen) == SMALL["length"], "record for record, every field"
    assert withheld["first_new_epoch_index"] is None and set(withheld["swap_epochs"]) == {0}
    assert run_reasons(SMALL, {"first_new_epoch_index": withheld["first_new_epoch_index"],
                               "swap_epochs": withheld["swap_epochs"], "drawn_at_swaps": withheld["drawn_at_swaps"],
                               "held_out_epochs": sorted({r["epoch"] for r in withheld["reads"]})})
    real = small_run(keep_records=True)
    first = SMALL["swaps"][0]
    assert [r["epoch"] for r in real["records"][:first]] == [0] * first and real["records"][first]["epoch"] == 1
    assert real["records"][:first] == frozen[:first], "before its first swap the adaptive model is its start"
    differ = sum(1 for x, y in zip(real["records"][first:], frozen[first:]) if x["score"] != y["score"])
    print("CONTROL E2 never swaps: on the small plan its %d records equal the frozen model's, every one; the real adaptive's "
          "scores differ from the frozen's at %d of the %d records from its first swap" % (len(frozen), differ, len(frozen) - first))
    assert differ > 0.9 * (len(frozen) - first)
    # on the short form: the adaptive's entries as a model that never swapped would give them, the frozen model's
    got, part = short()
    p = got["plan"]
    never = json.loads(json.dumps(part))
    fz = find(never, "frozen")
    for e in never["entries"]:
        if e["model"] == "adaptive":
            e.update(coefficients=fz["coefficients"], blob_sha256=fz["blob_sha256"], d_own=fz["d_own"], found=fz["found"],
                     threshold=fz["threshold"], epoch=0, threshold_epoch=0)
            e["pairs"]["frozen"] = {"ref_only": 0, "other_only": 0, "noise_ref_only": 0, "noise_other_only": 0,
                                    "noise_both": 120, "refused": None}
    never.update(first_new_epoch_index=None, swap_epochs=[0] * BLOCKS, held_out_epochs=[0])
    reasons = not_as_stated([never], ("short",))
    x = result(never)[("adaptive", 8)]
    print("CONTROL E2 never swaps, on the short form: gain over the frozen model %+.4f (z %+.1f); NOT AS STATED for %d "
          "reasons, the first: %s" % (x["gain"]["gain"], x["gain"]["z_zero"], len(reasons), reasons[0]))
    assert x["gain"]["gain"] == 0.0 and not x["gain"]["z_zero"] > GAIN_Z and not holds(never)
    assert any("first_new_epoch_index" in y for y in reasons) and any("held_out_epochs" in y for y in reasons)


def test_control_comparison_rules__e2_a_drift_at_the_wrong_index_is_seen_by_the_frozen_models_count():
    """The frozen model's FOUND count cannot see one trial: it moves by at most 1 / n. Its count of
    e1 trials, by its response to what was added, sees each of these exactly."""
    good = schedule_for(SMALL)
    right = small_run()
    assert drift_reasons(SMALL, drift_counts(SMALL, right)) == []
    early_at, late_at = SMALL["change"] - SPACING + FIRST, SMALL["change"] + FIRST
    early, late = moved(good, early_at, "e1"), moved(good, late_at, "e0")
    for what, schedule in (("one trial early", early), ("one trial late", late)):
        with pytest.raises(LearnRefusal) as e:
            small_run(schedule=schedule, committed=own_digest(SMALL, good))
        assert e.value.name == "INJECTION_SET", "rule 1 refuses it first, when it is given the committed set"
        d = drift_counts(SMALL, small_run(schedule=schedule))          # handed its own digest: rule 1 does not stop it
        reasons = drift_reasons(SMALL, d)
        print("CONTROL E2 drift %s: the frozen model sees %d e0 and %d e1 trials, the first e1 at %s: %s"
              % (what, d["frozen_sees_e0"], d["frozen_sees_e1"], d["first_e1_index"], reasons))
        assert reasons
    assert drift_counts(SMALL, small_run(schedule=early))["e1_before_change"] == 1
    assert drift_counts(SMALL, small_run(schedule=late))["e0_from_change"] == 1

    def lying(profile, frames, schedule, length):     # adds e1 a trial early, and returns the truth it was handed
        stream, _truth = inject.inject(profile, frames, early, length)
        return stream, inject.schedule(schedule, length)

    told = small_run(injector=lying)
    assert told["injection_sha256"] == own_digest(SMALL, good)["small"]["sha256"], "rule 1 saw the committed set"
    d = drift_counts(SMALL, told)
    print("CONTROL E2 drift, an injector that adds e1 a trial early under e0's truth: the frozen model sees e1 first at %s"
          % d["first_e1_index"])
    assert d["first_e1_index"] == early_at and drift_reasons(SMALL, d)
    _got, part = short()
    assert drift_reasons(plan("short"), part["drift"]) == [] and part["drift"]["frozen_sees_e1"] == 1024 + 4000


def test_control_comparison_rules__e2_a_swap_one_index_late_is_not_as_stated():
    late = small_run(hand=lambda core, blob, at: handover.hand_over(core, blob, at + 1))
    fields = {"first_new_epoch_index": late["first_new_epoch_index"], "swap_epochs": late["swap_epochs"],
              "drawn_at_swaps": late["drawn_at_swaps"], "held_out_epochs": sorted({r["epoch"] for r in late["reads"]})}
    reasons = run_reasons(SMALL, fields)
    print("CONTROL E2 a swap one index late: %s" % reasons)
    assert late["first_new_epoch_index"] == SMALL["swaps"][0] + 1 and reasons
    right = small_run()
    assert run_reasons(SMALL, {"first_new_epoch_index": right["first_new_epoch_index"], "swap_epochs": right["swap_epochs"],
                               "drawn_at_swaps": right["drawn_at_swaps"],
                               "held_out_epochs": sorted({r["epoch"] for r in right["reads"]})}) == []


def test_e2l_drift_a_part_survives_being_written_and_read(tmp_path, capsys):
    _got, part = short()
    back = json.loads(json.dumps(part))
    assert back == part and not_as_stated([back], ("short",)) == [] and holds(back)
    # the script's judge is the full run's: handed the short form's part, it says so and fails
    path = tmp_path / "short.json"
    path.write_text(json.dumps(part), encoding="utf-8")
    assert main(["--judge", str(path)]) == 1
    out = capsys.readouterr().out
    assert "the parts are ['short'], not exactly ['full']" in out and "== E2 SOFTWARE VERDICT: FAIL" in out
    assert main([]) == 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

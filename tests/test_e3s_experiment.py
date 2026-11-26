"""Stage E3 in software: does E1's learner reach the matched filter's efficiency on real seismic noise?

D0, section 8, stage E3: "a recorded stream. Real noise from HBM, with injections. Seismic
archives are the candidate." This is E1 with one thing changed, the noise: recorded HHZ counts
of four SCSN stations, replayed through the model's own source (`model.source.Replay`), with `e0`
injected by the model's injector, E1's learner against E0's matched filter, each at its own
threshold measured from the same held-out signal-free scores. D8 cannot predict the answer:
the noise is neither white nor Gaussian nor of one level. **Neither model whitens, and on
coloured noise the matched filter is not the best detector:** the comparison is of the two
detectors D0's stage E3 names, not of either against an optimum.

THE EXPERIMENT, fixed before any record was fetched (the round's ledger: E3S's design of
2026-11-25 20:57 with its corrections of 21:00, ruled by the lead at 21:02; the noise rule frozen
in vectors/e3s/rule.json at the freeze commit acc12ee):

  a part       one station's stream: its kept blocks of 65,536 frames (docs/studies/e3/e3prep.py),
               each a recording, replayed in order, one at a time
                 training   128 blocks, trials of 128 frames, e0 at frame 64 of each; the
                            detector BLANK, epoch 0
                 held-out   400 blocks, trials of 256 frames, e0 at frame 192 of each
  amplitude    one a station, from 16 calibration blocks before the training ones, by the rule
               of e3prep.py; the injection set committed in vectors/e3s/injection_sets.json
  the learner  the difference of two class means (learn/trainer.py) over the LAST 32 training
               blocks: 16,384 truth records, E1's named count. Made, quantised, packed and
               committed AT A, the first held-out frame, before it is drawn. THE NAMED MODEL.
  read at      A + 63 + 64 g: in each held-out trial three signal-free scores (offsets 63, 127,
               191) and one at the injection (255): n = 102,400, m = 307,200, k = 3,072
  thresholds   each model's own, from the same m signal-free scores, at 0.01 (E1's functions)
  the judge    stats.empirical.compare: the matched filter's efficiency less the learner's on the
               same injections, its standard error by resampling the 400 held-out blocks 1,000
               times with both thresholds measured again; its reading at 4 standard errors:
               REACHES, SHORT or AHEAD
  held         the experiment held at a station only if: the part is the stated one; no flag;
               every score read the statistics' exact filter's; the core equal to the baseline
               on the first 256 held-out trials; each threshold gives k of the same m (equal
               rate); and each threshold carries: from the even held-out blocks to the odd and
               back, within 4 resampled standard errors of its stated rate
  reported     beside the reading, not in it: the curve (the learners of the last 2, 8 and all
               128 training blocks, 1,024, 4,096 and 65,536 records), the density method, the
               carry by halves in time, and the resampling on joins of four blocks

THE COMPARISON RULES of D0's section 8, as the gate `comparison-rules`:
  1 every part's injection set is committed with its digest; a run on another is refused before a frame
  2 the learner reads frames below A only; every figure from records at A + 63 or later (E1's
    `hits` and `threshold_record`); a held-out block that meets a training block is refused
  3 thresholds bound to their epoch, and a comparison only at an equal count of the same scores
    (E1's `compare_at_equal_rate`, and the judge's own recount)
  4 a rate below ten expected crossings is labelled (E1's `rate_label`)
  5 the reported model is the named one at every station; another is refused

THE GATE runs the short form: the model's own white noise, written into block recordings and
replayed by the same code, blocks of 16,384 frames (64 calibration, 32 training, 128 held-out;
the named model all 32 training blocks, 4,096 records; n 8,192, m 24,576, so that half of the
signal-free scores still give a threshold its 100 crossings, for the carry). Its answer is
known: on white noise the learner reaches the matched filter (E1).

THE FULL RUN is the lead's, one process a station, after `docs/studies/e3/e3prep.py` has written
the recordings (the design's estimate, 10 to 15 minutes a part):

    python tests/test_e3s_experiment.py --full --station MPP --data <recordings> --out e3-MPP.json   (CDM, HDH, SRN)
    python tests/test_e3s_experiment.py --judge e3-MPP.json e3-CDM.json e3-HDH.json e3-SRN.json

WHAT THIS DOES NOT SHOW: anything in fabric; that a real faint event is found (the pulse is
counts added to counts); a learner that whitens; another pulse, rate, profile or season. A
reading is evidence about sensitivity, on these records, by the statistics' authority. It is not
evidence that any fabric is correct.
"""
import atexit
import hashlib
import json
import os
import shutil
import sys
import tempfile
from array import array
from fractions import Fraction

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
E3DIR = os.path.join(ROOT, "docs", "studies", "e3")
for p in (ROOT, HERE, E3DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from spec import constants as C  # noqa: E402
from model import records, source, weights  # noqa: E402
from model.detector import Core  # noqa: E402
from model.refusal import Refusal  # noqa: E402
from stats import empirical, matched as stat_matched, recovery, theory, tolerance  # noqa: E402
from learn import handover, trainer  # noqa: E402
from learn.errors import LearnRefusal  # noqa: E402
import test_lrn_a_e1 as E1  # noqa: E402  (E1's own rule functions: the lead's ruling of 21:02, question 6)
import e3prep  # noqa: E402
import e3sets  # noqa: E402

RULE = e3prep.load_rule()
PROFILE = RULE["profile"]
E0 = C.PULSES["e0"]
TAPS = len(E0)
PFA = RULE["pfa"]
Z = RULE["z"]
LAYOUT = RULE["layout"]
READS_PER_TRIAL = LAYOUT["held_trial"] // TAPS          # 4: three signal-free, then the injection's
BLANK_EPOCH, LEARNED_EPOCH = 0, 1
CORE_CHECK = 256
SETS_PATH = os.path.join(ROOT, "vectors", "e3s", "injection_sets.json")
BLOCKS_PATH = os.path.join(ROOT, "vectors", "e3s", "blocks.json")
# The design named 2026112690, to be checked far from E0's and E1's seeds; it is not (1.39e17 words
# from one, under 2^57). 2026112695 is the first from it that is, with its louder stream's 2026112700.
SHORT_NOISE_SEED, SHORT_SIGMA, SHORT_CALIBRATION = 2026112695, (1477, 1), 64
LOUD_SEED = SHORT_NOISE_SEED + 5
FOUR = 4                                                 # the join of blocks the reported resampling uses


# ------------------------------------------------------------------ the parts

def make_plan(name, station, block_frames, training, held_out, named_blocks, curve_blocks, seed, carry_seed, resamples):
    trials = block_frames // LAYOUT["held_trial"]
    return {"name": name, "station": station, "block_frames": block_frames, "training": training,
            "held_out": held_out, "named_blocks": named_blocks, "curve_blocks": list(curve_blocks),
            "A": training * block_frames, "length": (training + held_out) * block_frames,
            "trials_per_block": trials, "reads_per_block": block_frames // TAPS,
            "n": held_out * trials, "m": 3 * held_out * trials,
            "named_records": named_blocks * block_frames // LAYOUT["training_trial"],
            "seed": seed, "carry_seed": carry_seed, "resamples": resamples}


def full_plan(station):
    if station not in RULE["stations"]:
        raise ValueError("there is no station %r: the stations are %s" % (station, RULE["stations"]))
    s = RULE["stations"].index(station)
    u = RULE["use"]
    return make_plan("full-" + station, station, RULE["block_frames"], u["training"], u["held_out"],
                     RULE["named_model"]["training_blocks"], RULE["curve_training_blocks"],
                     RULE["seeds"]["comparison"] + s, RULE["seeds"]["carry"] + s, RULE["resamples"])


SHORT = make_plan("short", "short", e3sets.SHORT["block_frames"], e3sets.SHORT["training"], e3sets.SHORT["held_out"],
                  e3sets.SHORT["training"], (2, 8), 2026112691, 2026112711, RULE["resamples"])


def schedule_for(p, num, den):
    """The part's injection set, its truth records in order (e3sets.py's arithmetic)."""
    rows = e3sets.schedule(num, den, p["block_frames"], p["training"], p["held_out"], LAYOUT)
    return [{"index": i, "pulse_id": C.PULSE_IDS["e0"], "amplitude_num": a, "amplitude_den": d} for i, a, d in rows]


def committed_sets():
    with open(SETS_PATH, encoding="utf-8") as f:
        return json.load(f)


def committed_set(p):
    sets = committed_sets()
    return sets["short"] if p["station"] == "short" else sets["stations"].get(p["station"])


def check_injection_set(p, schedule, committed=None):
    """Rule 1: refuse a schedule that is not the part's committed set. Returns its digest."""
    want = committed_set(p) if committed is None else committed
    if not want or "sha256" not in want:
        raise LearnRefusal("INJECTION_SET", "no injection set is committed for the part %r" % (p["name"],))
    got = records.digest("truth", schedule)
    if got != (want["sha256"], want["records"]):
        raise LearnRefusal("INJECTION_SET", "part %s: the schedule is %d records with digest %s; the committed set is "
                           "%d with %s" % (p["name"], got[1], got[0], want["records"], want["sha256"]))
    return got[0]


def replayed(paths):
    """The part's frames: each block's recording replayed by the model's source, one at a time, in order."""
    for path in paths:
        yield from source.Replay(PROFILE, path)


def measure(p, paths, schedule, committed=None, make_learner=None, commit_at=None, progress=None):
    """Run one part through the model: the replayed blocks, the injector, one core, the learner, the hand-over."""
    digest = check_injection_set(p, schedule, committed)          # rule 1: before a frame is drawn
    a, length = p["A"], p["length"]
    first = (p["training"] - p["named_blocks"]) * p["block_frames"]
    train_samples, held = array("h"), array("h")
    state = {"refusal": None, "blob": None, "learner": None}

    def make():
        # Rule 2: the learner is handed frames below A, and the truth records below A, and nothing else.
        x = np.frombuffer(train_samples, dtype=np.int16).reshape(-1, 1)
        assert x.shape[0] == a and len(held) == 0
        learner = trainer.MeanDifference(1, TAPS) if make_learner is None else make_learner()
        trainer.train(x[first:], [r["index"] - first for r in truth if first <= r["index"] < a], TAPS, learner)
        state["learner"] = learner
        try:
            state["blob"] = handover.candidate_blob(PROFILE, learner.weights())
        except Refusal as e:
            state["refusal"] = e.name
        return state["blob"]

    pairs, truth = E1.wired(PROFILE, replayed(paths), schedule, length, handover.blank_blob(PROFILE, TAPS),
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
            if (index - a) % TAPS == TAPS - 1:
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


# ------------------------------------------------------------------ the records, as the judge takes them

def split(p, reads):
    """(signal-free records, at-injection records), each checked by its index."""
    assert len(reads) == p["held_out"] * p["reads_per_block"]
    free = [r for i, r in enumerate(reads) if i % READS_PER_TRIAL != READS_PER_TRIAL - 1]
    at = [r for i, r in enumerate(reads) if i % READS_PER_TRIAL == READS_PER_TRIAL - 1]
    assert [r["index"] for r in reads] == list(range(p["A"] + TAPS - 1, p["length"], TAPS))
    return free, at


def at_positions(p):
    """Each held-out injection's truth index + TAPS - 1."""
    trials = np.arange(p["trials_per_block"])
    return (p["A"] + np.arange(p["held_out"])[:, None] * p["block_frames"] + LAYOUT["held_first"] + TAPS - 1
            + LAYOUT["held_trial"] * trials[None, :]).ravel()


def by_block(p, values, per_trial):
    return np.asarray(values, dtype=np.float64).reshape(p["held_out"], per_trial * p["trials_per_block"])


def judged_model(p, free_records, at_records, threshold):
    return {"free": by_block(p, [r["score"] for r in free_records], READS_PER_TRIAL - 1),
            "at": by_block(p, [r["score"] for r in at_records], 1),
            "free_index": np.array([r["index"] for r in free_records]).reshape(p["held_out"], -1),
            "threshold": threshold}


def matched_coefficients():
    return e3prep.matched_coefficients()


def matched_blob():
    return weights.matched_filter(PROFILE, E0, (1,))


def core_agrees(p, held, blob, scores):
    """Is the model's core, holding `blob`, equal to `scores` on the first CORE_CHECK held-out trials?"""
    frames = CORE_CHECK * LAYOUT["held_trial"]
    core = Core(blob)
    got = [core.step((int(v),))["score"] for v in held[:frames]][TAPS - 1::TAPS]
    want = [int(v) for v in scores[:CORE_CHECK * READS_PER_TRIAL].tolist()]
    return len(got) == CORE_CHECK * READS_PER_TRIAL and got == want


def learner_of(train, p, blocks, schedule):
    """The learner of the last `blocks` training blocks, from the training frames the part kept."""
    first = (p["training"] - blocks) * p["block_frames"]
    x = np.asarray(train).astype(np.int64).reshape(-1, 1)
    idx = [r["index"] - first for r in schedule if first <= r["index"] < p["A"]]
    return trainer.train(x[first:], idx, TAPS)


def judged_from_scores(p, scores):
    """A filter's scores at the reads (the statistics'), as the judge takes a model, at its own threshold."""
    free, at = split(p, E1.records_from(p, scores, LEARNED_EPOCH))
    return judged_model(p, free, at, E1.entry("other", free, at, p["A"])["threshold"]["threshold"])


def compared(p, base, other_scores, seed=None):
    """The judge on a model and another filter's scores at the reads."""
    return empirical.compare(base, judged_from_scores(p, other_scores), PFA, p["resamples"],
                             p["seed"] if seed is None else seed, Z)


def utc_spans(station):
    """(training, held-out) spans of a station's used blocks, from blocks.json: (start us, end us, payload SHA-256)."""
    with open(BLOCKS_PATH, encoding="utf-8") as f:
        blocks = json.load(f)
    rows = [s for s in blocks["stations"] if s["station"] == station][0]["blocks_used"]
    span = RULE["block_frames"] * e3prep.SAMPLE_US
    out = {"training": [], "held_out": []}
    for r in rows:
        if r["role"] in out:
            start = e3prep.us(e3prep.datetime.strptime(r["start_utc"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=e3prep.timezone.utc))
            out[r["role"]].append((start, start + span, r["payload_sha256"]))
    return out


def disjoint(spans):
    """Rule 2 on the blocks: the count the judge checked, or the name it refused under."""
    try:
        return empirical.check_disjoint(spans["training"], spans["held_out"])
    except empirical.EmpiricalRefusal as e:
        return e.name


def scores_identical(held, coeffs, reads):
    """Is every score the model read the statistics' exact filter's, for these coefficients on these samples?"""
    stat = E1.stat_scores_at_reads(held, coeffs)
    return bool(stat_matched.scores_are_exact(PROFILE, coeffs) and
                [int(v) for v in stat.tolist()] == [r["score"] for r in reads])


def evaluate(p, got, schedule, extra=None, spans=None):
    """One part's record: everything the judge reads. `spans` are the blocks' (training, held-out) spans."""
    a, held = p["A"], got["held"]
    free, at = split(p, got["reads"])
    learned = E1.entry("learned", free, at, a)
    blob = got["blob"]
    coeffs = list(handover.coefficients(blob)[0]) if blob is not None else [0] * TAPS
    identical = scores_identical(held, coeffs, got["reads"])
    mf = matched_coefficients()
    base_scores = E1.stat_scores_at_reads(held, mf)
    base_free, base_at = split(p, E1.records_from(p, base_scores, BLANK_EPOCH))
    base = E1.entry("matched", base_free, base_at, a)
    part = {"name": p["name"], "station": p["station"], "plan": p, "profile": PROFILE, "pfa": PFA, "z": Z,
            "taps": TAPS, "spec_sha256": C.SPEC_SHA256, "n": p["n"], "m": p["m"],
            "k": learned["threshold"]["k"], "above": learned["threshold"]["above"],
            "threshold": learned["threshold"]["threshold"], "threshold_epoch": learned["threshold"]["epoch"],
            "base_threshold": base["threshold"]["threshold"], "base_above": base["threshold"]["above"],
            "held_out_epochs": sorted({r["epoch"] for r in got["reads"]}),
            "rate_floor": E1.rate_floor(p["m"]), "rate_label": E1.rate_label(PFA, p["m"]),
            "coefficients": coeffs, "blob_sha256": weights.unpack(blob)["sha256"] if blob is not None else None,
            "found": int(learned["hits"].sum()), "base_found": int(base["hits"].sum()),
            "scores_identical_to_stats": bool(identical),
            "core_equals_baseline_on_first_trials": bool(core_agrees(p, held, matched_blob(), base_scores)),
            "peak_offset": E1.peak_offset(blob) if blob is not None else None,
            "reported": True, "learner_counts": list(got["learner"].counts) if got["learner"] else None,
            "handover_refusal": got["refusal"], "first_new_epoch_index": got["first_new_epoch_index"],
            "flags": got["flags"], "scores_not_zero_while_blank": got["scores_not_zero_while_blank"],
            "injection_sha256": got["injection_sha256"],
            "stream_sha256": hashlib.sha256(got["train"].tobytes() + got["held"].tobytes()).hexdigest(),
            "blocks_sha256": [hashlib.sha256(np.ascontiguousarray(x).astype("<i2").tobytes()).hexdigest()
                              for x in np.split(np.concatenate([got["train"], got["held"]]),
                                                p["training"] + p["held_out"])]}
    try:
        E1.compare_at_equal_rate(base, learned, 1.0, 1.0)                 # rule 3, by E1's own recount
        part["comparison_refused"] = None
    except LearnRefusal as e:
        part["comparison_refused"] = e.name
    jb = judged_model(p, base_free, base_at, base["threshold"]["threshold"])
    jl = judged_model(p, free, at, learned["threshold"]["threshold"])
    try:
        part["judge"] = strip(empirical.compare(jb, jl, PFA, p["resamples"], p["seed"], Z))
    except empirical.EmpiricalRefusal as e:
        part["judge"] = None
        part["comparison_refused"] = part["comparison_refused"] or e.name
    part["carry"] = {}
    for what, model, s in (("matched", jb, 0), ("learned", jl, 2)):
        part["carry"][what] = {split_: carried(empirical.carry_both_ways(model["free"], PFA, p["resamples"],
                                                                         p["carry_seed"] + s + off, split_, Z))
                               for split_, off in (("alternate", 0), ("halves", 4))}
    part["density"] = {what: empirical.slope_by_ranks(model["free"], model["at"], PFA)
                       for what, model in (("matched", jb), ("learned", jl))}
    if p["held_out"] // FOUR >= empirical.MIN_BLOCKS and part["judge"] is not None:
        join = {key: (model[key].reshape(p["held_out"] // FOUR, -1) if key != "threshold" else model[key])
                for model in (jb,) for key in model}
        joinl = {key: (jl[key].reshape(p["held_out"] // FOUR, -1) if key != "threshold" else jl[key]) for key in jl}
        part["judge_four_block_joins"] = strip(empirical.compare(join, joinl, PFA, p["resamples"], p["seed"], Z))
    else:
        part["judge_four_block_joins"] = None
    part["curve"] = []
    for blocks in p["curve_blocks"]:
        if blocks == p["named_blocks"]:
            continue
        lr = learner_of(got["train"], p, blocks, schedule)
        c2 = list(handover.coefficients(handover.candidate_blob(PROFILE, lr.weights()))[0])
        res = strip(compared(p, jb, E1.stat_scores_at_reads(held, c2)))
        part["curve"].append({"training_blocks": blocks, "records": lr.counts[1], "learner_counts": list(lr.counts),
                              "coefficients": c2, "found": res["other_found"], "efficiency": res["other_efficiency"],
                              "cost": res["cost"], "se": res["se"], "reading": res["reading"]})
    part["blocks_disjoint"] = disjoint(spans) if spans is not None else None
    part.update(extra or {})
    return part


def strip(result):
    return {k: v for k, v in result.items() if not isinstance(v, np.ndarray)}


def carried(c):
    return {"split": c["split"], "carries": bool(c["carries"]), "there": dict(c["there"], carries=bool(c["there"]["carries"])),
            "back": dict(c["back"], carries=bool(c["back"]["carries"]))}


# ------------------------------------------------------------------ the verdict

def holds(part):
    """The experiment's conditions at one station, but 'the part is the stated one' (not_as_stated)."""
    ok = part["flags"] == 0 and part["scores_identical_to_stats"] and part["core_equals_baseline_on_first_trials"]
    ok = ok and part["comparison_refused"] is None and part["judge"] is not None
    ok = ok and all(part["carry"][w]["alternate"]["carries"] for w in ("matched", "learned"))
    return bool(ok)


def reading(part):
    return part["judge"]["reading"] if part.get("judge") else None


def committed_blocks(station):
    """The kept blocks' payload SHA-256s, training then held-out, as e3prep.py wrote them."""
    with open(BLOCKS_PATH, encoding="utf-8") as f:
        blocks = json.load(f)
    for s in blocks["stations"]:
        if s["station"] == station:
            rows = [r for r in s["blocks_used"] if r["role"] in ("training", "held_out")]
            return [r["payload_sha256"] for r in rows]
    return None


def not_as_stated(part, plan_of=None, blocks_of=None, sets_of=None):
    """Why this part is not the experiment this file states: a list of reasons, empty when it is.

    What it takes on trust, stated: the counts and the judge's results. Nothing here recomputes
    a score from a stream; running the part again is the check for that."""
    reasons = []
    station = part.get("station")
    try:
        p = (plan_of or (lambda s: SHORT if s == "short" else full_plan(s)))(station)
    except ValueError as e:
        return [str(e)]
    want_k = int(Fraction(PFA) * p["m"])
    want_set = (sets_of or committed_set)(p)
    for name, want in (("plan", p), ("profile", PROFILE), ("pfa", PFA), ("z", Z), ("taps", TAPS),
                       ("spec_sha256", C.SPEC_SHA256), ("n", p["n"]), ("m", p["m"]), ("k", want_k), ("above", want_k),
                       ("base_above", want_k), ("threshold_epoch", LEARNED_EPOCH), ("held_out_epochs", [LEARNED_EPOCH]),
                       ("rate_label", E1.rate_label(PFA, p["m"])), ("reported", True),
                       ("learner_counts", [p["named_records"]] * 2), ("handover_refusal", None),
                       ("first_new_epoch_index", p["A"]), ("scores_not_zero_while_blank", 0),
                       ("comparison_refused", None), ("blocks_disjoint", p["training"] + p["held_out"]),
                       ("injection_sha256", want_set.get("sha256") if want_set else "none committed")):
        if part.get(name, "missing") != want:
            reasons.append("part %s: %s is %r, the experiment's is %r" % (station, name, part.get(name, "missing"), want))
    if part.get("rate_label") == "COUNTED" and part.get("pfa", PFA) * p["m"] < E1.FLOOR_CROSSINGS:
        reasons.append("part %s: a rate below the floor of %d crossings is called counted" % (station, E1.FLOOR_CROSSINGS))
    if station != "short":
        want_blocks = (blocks_of or committed_blocks)(station)
        if part.get("blocks_sha256") != want_blocks:
            reasons.append("part %s: its blocks are not the committed blocks of vectors/e3s/blocks.json" % station)
    coeffs = part.get("coefficients")
    try:
        sha = weights.unpack(weights.pack(PROFILE, [{0: tuple(coeffs)}], (1,), C.RECTIFIERS["pass"], 1, 0))["sha256"]
    except (Refusal, TypeError):
        sha = None
    if sha is None or part.get("blob_sha256") != sha:
        reasons.append("part %s: its blob hash is not the hash of the coefficients it carries" % station)
    j = part.get("judge") or {}
    for name, want in (("m", p["m"]), ("k", want_k), ("n", p["n"]), ("blocks", p["held_out"]),
                       ("resamples", p["resamples"]), ("seed", p["seed"]), ("z", Z)):
        if j.get(name) != want:
            reasons.append("part %s: the judge's %s is %r, the experiment's is %r" % (station, name, j.get(name), want))
    counts = [j.get(x) for x in ("reference_found", "other_found", "reference_only", "other_only")]
    if not all(type(c) is int and c >= 0 for c in counts) or counts[1] != counts[0] - counts[2] + counts[3] \
            or counts[0] != part.get("base_found") or counts[1] != part.get("found"):
        reasons.append("part %s: its counts do not add up: %r, found %r, the matched filter %r"
                       % (station, counts, part.get("found"), part.get("base_found")))
    if j and abs(j.get("cost", 0.0) - (counts[2] - counts[3]) / p["n"]) > 1e-12:
        reasons.append("part %s: the judge's cost is not its counts'" % station)
    if j and j.get("reading") != judge_reading(j):
        reasons.append("part %s: the reading %r is not what its cost and se give" % (station, j.get("reading")))
    return reasons


def judge_reading(j):
    if abs(j["cost"]) <= j["z"] * j["se"]:
        return "REACHES"
    return "SHORT" if j["cost"] > 0 else "AHEAD"


def report(parts, which=None):
    """Rule 5: the reported model is the named one at every station, and every station is reported."""
    if which is not None:
        raise LearnRefusal("NOT_THE_NAMED_MODEL", "%r was asked for; the model named before the run is the learner of "
                           "the last %d training blocks, at every station" % (which, RULE["named_model"]["training_blocks"]))
    stations = [pt["station"] for pt in parts]
    if sorted(stations) != sorted(RULE["stations"]):
        raise LearnRefusal("NOT_THE_NAMED_MODEL", "the parts are of %s; every station of the rule, %s, is reported"
                           % (sorted(stations), RULE["stations"]))
    return [(pt["station"], reading(pt)) for pt in sorted(parts, key=lambda q: RULE["stations"].index(q["station"]))]


def judge_parts(paths, refused=()):
    parts = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            parts.append(json.load(f))
    print("E3 in software: profile %s, Pfa %.2f, z %.1f; the matched filter of e0 against E1's learner of %d records"
          % (PROFILE, PFA, Z, RULE["named_model"]["records"]))
    ok = True
    rows = []
    for part in sorted(parts, key=lambda q: RULE["stations"].index(q["station"]) if q["station"] in RULE["stations"] else 9):
        reasons = not_as_stated(part)
        held_ = holds(part) and not reasons
        ok = ok and held_
        rows.append((part, reasons, held_))
        j = part.get("judge") or {}
        print("  %s: the matched filter %s, the learner %s; cost %s, se %s, %s; held: %s"
              % (part["station"], "%d of %d" % (j.get("reference_found", -1), part["n"]),
                 "%d of %d" % (j.get("other_found", -1), part["n"]),
                 "%+.5f" % j["cost"] if j else "none", "%.5f" % j["se"] if j else "none",
                 j.get("reading", "no reading"), "yes" if held_ else "NO"))
        for w in ("matched", "learned"):
            for s in ("alternate", "halves"):
                c = part["carry"][w][s]
                print("    carry %-8s %-9s there %.5f of %.5f (%+.2f se), back %.5f (%+.2f se): %s"
                      % (w, s, c["there"]["rate"], c["there"]["stated"], c["there"]["z_score"], c["back"]["rate"],
                         c["back"]["z_score"], "CARRIES" if c["carries"] else "DOES NOT CARRY"))
            d = part["density"][w]
            print("    density %-8s slope %.3f, se %.3f; first-order threshold se %.5f" % (w, d["slope"], d["se"], d["se_threshold"]))
        if part.get("judge_four_block_joins"):
            print("    the resampling on joins of four blocks: se %.5f against %.5f" % (part["judge_four_block_joins"]["se"], j["se"]))
        for c in part["curve"]:
            print("    curve: %d records, found %d, cost %+.5f, se %.5f, %s" % (c["records"], c["found"], c["cost"], c["se"], c["reading"]))
        print("    the instrument: flags %s; scores identical to the statistics': %s; core equal to the baseline: %s; "
              "peak at truth + %s" % (part["flags"], part["scores_identical_to_stats"],
                                      part["core_equals_baseline_on_first_trials"], part["peak_offset"]))
        for r in reasons:
            print("    NOT AS STATED: " + r)
    for station in refused:
        print("  %s: REFUSED NOT_ENOUGH_NOISE, no part" % station)
        ok = False
    try:
        named = report(parts)
        print("  THE REPORTED READINGS, the model named before the run at every station: %s"
              % ", ".join("%s %s" % (s, r) for s, r in named))
    except LearnRefusal as e:
        ok = False
        print("  THE REPORTED READINGS: refused, %s" % e)
    print("== E3 SOFTWARE: %s" % ("the experiment held at every station" if ok else "NOT HELD at every station"))
    return 0 if ok else 1


def full_inputs(station, data):
    """What a station's full part reads: (plan, committed set, the recordings' paths in order, schedule, spans)."""
    p = full_plan(station)
    sets = committed_set(p)
    if not sets or "sha256" not in sets:
        raise SystemExit("REFUSED: no injection set is committed for %s (%r)" % (station, sets))
    with open(BLOCKS_PATH, encoding="utf-8") as f:
        blocks = json.load(f)
    rows = [s for s in blocks["stations"] if s["station"] == station][0]
    paths = [os.path.join(data, r["file"]) for r in rows["blocks_used"] if r["role"] in ("training", "held_out")]
    schedule = schedule_for(p, sets["amplitude_num"], sets["amplitude_den"])
    return p, sets, paths, schedule, utc_spans(station)


def full_part(station, data, out):
    p, sets, paths, schedule, spans = full_inputs(station, data)
    print("E3 full run, %s: %d training and %d held-out blocks, amplitude %d/%d, %d frames"
          % (station, p["training"], p["held_out"], sets["amplitude_num"], sets["amplitude_den"], p["length"]), flush=True)
    got = measure(p, paths, schedule, progress=65536 * 32)
    part = evaluate(p, got, schedule, spans=spans)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(part, f, indent=1)
        f.write("\n")
    print("wrote %s: %s" % (out, reading(part)))
    return part


def main(argv):
    def value(flag):
        return argv[argv.index(flag) + 1] if flag in argv else None

    if "--judge" in argv:
        return judge_parts(argv[argv.index("--judge") + 1:])
    if "--full" in argv:
        full_part(value("--station"), value("--data"), value("--out"))
        return 0
    print(__doc__)
    return 2


# ------------------------------------------------------------------ the gate's short form

_short = {}


def short_stream():
    """The short form's blocks: the model's white noise, the calibration by e3prep's own rule."""
    if "blocks" not in _short:
        p = SHORT
        bf = p["block_frames"]
        count = SHORT_CALIBRATION + p["training"] + p["held_out"]
        noise = source.Noise(PROFILE, SHORT_NOISE_SEED, SHORT_SIGMA[0], SHORT_SIGMA[1], count * bf)
        x = np.fromiter((f[0] for f in noise), dtype=np.int64, count=count * bf)
        entries = [{"day": "short", "block": i, "start": i * bf * e3prep.SAMPLE_US, "status": "kept",
                    "x": x[i * bf:(i + 1) * bf].astype(np.int32)} for i in range(count)]
        rule = dict(RULE, block_frames=bf, use={"calibration": SHORT_CALIBRATION, "training": p["training"],
                                                 "held_out": p["held_out"]})
        used, figures = e3prep.assign(entries, rule)
        folder = tempfile.mkdtemp(prefix="e3s-short-")
        atexit.register(shutil.rmtree, folder, True)
        paths, spans = [], {}
        for role in ("training", "held_out"):
            spans[role] = []
            for i, e in enumerate(used[role]):
                path = os.path.join(folder, "%s-%03d.und" % (role, i))
                with open(path, "wb") as f:
                    f.write(e3prep.recording_bytes(e["x"]))
                paths.append(path)
                spans[role].append((e["start"], e["start"] + bf * e3prep.SAMPLE_US,
                                    hashlib.sha256(e3prep.payload(e["x"])).hexdigest()))
        _short.update(blocks=used, figures=figures, paths=paths, spans=spans, folder=folder)
    return _short


def short():
    """The short form's one run through the model, made once; a failure is kept and raised again, not rerun."""
    if "error" in _short:
        raise _short["error"]
    if "part" not in _short:
        try:
            s = short_stream()
            f = s["figures"]
            schedule = schedule_for(SHORT, f["amplitude_num"], f["amplitude_den"])
            got = measure(SHORT, s["paths"], schedule)
            _short.update(schedule=schedule, got=got, part=evaluate(SHORT, got, schedule, spans=s["spans"]))
        except Exception as e:
            _short["error"] = e
            raise
    return _short["got"], _short["part"]


def short_base():
    got, _part = short()
    scores = E1.stat_scores_at_reads(got["held"], matched_coefficients())
    return judged_from_scores(SHORT, scores), scores


def test_e3s_experiment_the_setup_is_the_one_stated():
    p = full_plan("MPP")
    assert (p["A"], p["length"], p["n"], p["m"], p["named_records"]) == (8388608, 34603008, 102400, 307200, 16384)
    assert int(Fraction(PFA) * p["m"]) == 3072 and p["reads_per_block"] == 1024 and p["trials_per_block"] == 256
    assert [full_plan(s)["seed"] for s in RULE["stations"]] == [2026112610, 2026112611, 2026112612, 2026112613]
    assert [full_plan(s)["carry_seed"] for s in RULE["stations"]] == [2026112630, 2026112631, 2026112632, 2026112633]
    assert p["curve_blocks"] == [2, 8, 128] and p["named_blocks"] == 32 and p["resamples"] == 1000
    assert (SHORT["A"], SHORT["length"], SHORT["n"], SHORT["m"], SHORT["named_records"]) == \
        (524288, 2621440, 8192, 24576, 4096)
    assert int(Fraction(PFA) * SHORT["m"]) == 245 and int(Fraction(PFA) * SHORT["m"] // 2) == 122 >= recovery.MIN_CROSSINGS, \
        "half the short form's signal-free scores still hold the 100 crossings a threshold needs, for the carry"
    with pytest.raises(ValueError):
        full_plan("XYZ")
    # the short form's two streams sit far from E0's and E1's seventeen on the generator's cycle (mod-a.md, limit 7)
    seeds = [2026112500 + c for c in range(6)] + [2026112600] + [2026112300 + c for c in range(5)] + \
        [2026112400 + c for c in range(5)]
    assert len(set(seeds)) == 17
    inverse = pow(source.GAMMA, -1, 1 << 64)

    def apart(s, others):
        return min(min((s - y) * inverse % (1 << 64), (y - s) * inverse % (1 << 64)) for y in others)

    assert apart(SHORT_NOISE_SEED, seeds) > 1 << 57 and apart(LOUD_SEED, seeds + [SHORT_NOISE_SEED]) > 1 << 57
    assert apart(2026112690, seeds) < 1 << 57, "the seed the design named first, which this check turned down"
    assert (SHORT_CALIBRATION + SHORT["training"] + SHORT["held_out"]) * SHORT["block_frames"] < 1 << 25
    # the held-out reads: three signal-free, then the injection's, and the injection's is truth + 63
    assert at_positions(SHORT).tolist()[:2] == [SHORT["A"] + 192 + 63, SHORT["A"] + 448 + 63]
    assert recovery.minimum_spacing(TAPS, TAPS, TAPS - 1, 0) <= LAYOUT["held_trial"] - LAYOUT["held_first"] + 128


# ------------------------------------------------------------------ rule 1

def test_gate_comparison_rules__e3s_rule_1_every_injection_set_is_the_committed_one_by_two_implementations():
    sets = committed_sets()
    s = short_stream()
    f = s["figures"]
    assert (sets["short"]["amplitude_num"], sets["short"]["amplitude_den"]) == (f["amplitude_num"], f["amplitude_den"]), \
        "the short form's amplitude, worked again by the calibration rule, is the committed one"
    schedule = schedule_for(SHORT, f["amplitude_num"], f["amplitude_den"])
    assert E1.independent_digest(schedule) == (sets["short"]["sha256"], sets["short"]["records"]) == records.digest("truth", schedule)
    assert check_injection_set(SHORT, schedule) == sets["short"]["sha256"]
    assert sets["short"]["records"] == SHORT["training"] * 128 + SHORT["n"]
    for station, want in sorted(sets["stations"].items()):
        if "sha256" not in want:
            continue
        sched = schedule_for(full_plan(station), want["amplitude_num"], want["amplitude_den"])
        assert E1.independent_digest(sched) == (want["sha256"], want["records"]) == records.digest("truth", sched)
        assert want["records"] == 128 * 512 + 400 * 256 and sched[-1]["index"] == want["last_index"]


def test_control_comparison_rules__e3s_rule_1_a_run_on_another_injection_set_is_refused_before_a_frame_is_drawn(monkeypatch):
    s = short_stream()
    f = s["figures"]
    good = schedule_for(SHORT, f["amplitude_num"], f["amplitude_den"])

    def changed(i, **fields):
        return good[:i] + [dict(good[i], **fields)] + good[i + 1:]

    others = {"one amplitude changed": changed(5000, amplitude_num=good[5000]["amplitude_num"] + 1),
              "one index a sample later": changed(3, index=good[3]["index"] + 1),
              "one injection dropped": good[:-1],
              "one injection added": good + [dict(good[-1], index=good[-1]["index"] + 256)],
              "another station's set": schedule_for(SHORT, f["amplitude_num"] + 7, f["amplitude_den"]),
              "none at all": []}

    class NoReplay:
        def __init__(self, *args):
            raise AssertionError("a recording was replayed: the run was not refused before a frame was drawn")

    monkeypatch.setattr(source, "Replay", NoReplay)
    for what, schedule in others.items():
        with pytest.raises(LearnRefusal) as e:
            list(measure(SHORT, s["paths"], schedule)["reads"])
        print("CONTROL e3s rule 1, %s: refused, %s" % (what, str(e.value)[:120]))
        assert e.value.name == "INJECTION_SET", what
    with pytest.raises(AssertionError, match="a recording was replayed"):
        measure(SHORT, s["paths"], good)


# ------------------------------------------------------------------ rule 2

def test_gate_comparison_rules__e3s_rule_2_every_figure_is_read_from_the_held_out_stretch():
    got, part = short()
    p = SHORT
    assert len(got["train"]) == p["A"] and len(got["held"]) == p["length"] - p["A"]
    assert got["learner"].counts == [p["named_records"]] * 2
    idx = [r["index"] for r in got["reads"]]
    assert min(idx) == p["A"] + TAPS - 1 and all(y - x == TAPS for x, y in zip(idx, idx[1:]))
    free, at = split(p, got["reads"])
    assert [r["index"] for r in at] == at_positions(p).tolist() == [r["index"] + TAPS - 1 for r in got["truth"] if r["index"] >= p["A"]]
    theirs = recovery.signal_free_indexes(p["length"], TAPS, [r["index"] for r in got["truth"]], TAPS)
    assert theirs[theirs >= p["A"] + TAPS - 1].tolist() == [r["index"] for r in free], "the statistics' own rule"
    s = short_stream()
    assert empirical.check_disjoint(s["spans"]["training"], s["spans"]["held_out"]) == p["training"] + p["held_out"]
    assert part["held_out_epochs"] == [LEARNED_EPOCH] and part["first_new_epoch_index"] == p["A"]


def test_control_comparison_rules__e3s_rule_2_the_learner_given_windows_it_is_judged_on_is_refused():
    got, _part = short()
    p = SHORT
    a = p["A"]
    free, at = split(p, got["reads"])
    t = E1.threshold_record(free, a)
    for low in (a + TAPS - 2, a - 1, LAYOUT["training_first"] + TAPS - 1):      # one training frame; all; a training trial's
        reached = dict(at[0], index=low)
        for call in (lambda: E1.hits([reached] + at[1:], t, a), lambda: E1.threshold_record([reached] + free[1:], a)):
            with pytest.raises(LearnRefusal) as e:
                call()
            assert e.value.name == "TRAINED_ON", low
    assert E1.hits([dict(at[0], index=a + TAPS - 1)], t, a).shape == (1,), "the first record wholly of held-out frames is taken"
    with pytest.raises(LearnRefusal) as e:
        trainer.train(got["train"].astype(np.int64).reshape(-1, 1), [LAYOUT["training_first"], a + LAYOUT["held_first"]], TAPS)
    print("CONTROL e3s rule 2, a held-out truth record handed to the trainer: %s" % str(e.value)[:120])
    assert e.value.name == "WINDOW_OUTSIDE_PERIOD"
    s = short_stream()
    tr, ho = s["spans"]["training"], s["spans"]["held_out"]
    for what, held in (("a held-out block that is a training block in time", ho[:5] + [tr[7]] + ho[6:]),
                       ("one that overlaps a training block by one sample", ho[:5] + [(tr[-1][1] - 10000, ho[5][1], ho[5][2])] + ho[6:]),
                       ("one whose samples are a training block's", ho[:5] + [(ho[5][0], ho[5][1], tr[3][2])] + ho[6:])):
        with pytest.raises(empirical.EmpiricalRefusal) as e:
            empirical.check_disjoint(tr, held)
        print("CONTROL e3s rule 2, %s: %s" % (what, str(e.value)[:110]))
        assert e.value.name == "TRAINED_ON", what


# ------------------------------------------------------------------ rule 3

def test_gate_comparison_rules__e3s_rule_3_each_model_has_its_own_threshold_and_the_same_false_alarm_rate():
    _got, part = short()
    assert part["k"] == part["above"] == part["base_above"] == 245 and part["m"] == 24576
    assert part["threshold"] != part["base_threshold"] and part["comparison_refused"] is None
    j = part["judge"]
    assert (j["m"], j["k"], j["n"]) == (24576, 245, 8192)
    assert j["other_found"] == j["reference_found"] - j["reference_only"] + j["other_only"] == part["found"]
    print("E3 short form, rule 3: thresholds %.0f (learned) and %.0f (matched), each with 245 of 24,576 above; %d shared"
          % (part["threshold"], part["base_threshold"], j["noise_both"]))


def test_control_comparison_rules__e3s_rule_3_a_comparison_at_an_equal_threshold_is_refused():
    got, _part = short()
    p = SHORT
    a = p["A"]
    mf = matched_coefficients()
    half = mf[:TAPS // 2] + [0] * (TAPS // 2)

    def model(name, coeffs):
        free, at = split(p, E1.records_from(p, E1.stat_scores_at_reads(got["held"], coeffs), LEARNED_EPOCH))
        return dict(E1.entry(name, free, at, a), at=at)

    matched_, half_ = model("matched", mf), model("its first half", half)
    for mine, theirs in ((half_, matched_), (matched_, half_)):
        shared = dict(mine, threshold=dict(theirs["threshold"]), hits=E1.hits(mine["at"], theirs["threshold"], a))
        above = sum(1 for r in mine["free"] if r["score"] > theirs["threshold"]["threshold"])
        print("CONTROL e3s rule 3: %s counted at the threshold of %s: %d of 24,576 above it, where an equal rate is 245"
              % (mine["name"], theirs["name"], above))
        assert above != 245
        with pytest.raises(LearnRefusal) as e:
            E1.compare_at_equal_rate(theirs, shared, 1.0, 1.0)
        assert e.value.name == "UNEQUAL_FALSE_ALARM_RATE"
        # the judge's own recount, handed one model's threshold as the other's
        jm = judged_model(p, mine["free"], mine["at"], theirs["threshold"]["threshold"])
        jt = judged_model(p, theirs["free"], theirs["at"], theirs["threshold"]["threshold"])
        with pytest.raises(empirical.EmpiricalRefusal) as e:
            empirical.compare(jt, jm, PFA, 50, 1, Z)
        assert e.value.name == "UNEQUAL_FALSE_ALARM_RATE"
    assert sum(1 for r in half_["free"] if r["score"] > matched_["threshold"]["threshold"]) < 122
    assert sum(1 for r in matched_["free"] if r["score"] > half_["threshold"]["threshold"]) > 490


# ------------------------------------------------------------------ rules 4 and 5

def test_gate_comparison_rules__e3s_rule_4_a_rate_below_the_floor_is_labelled():
    assert E1.rate_label(PFA, 307200) == E1.rate_label(PFA, 24576) == "COUNTED"
    assert PFA / E1.rate_floor(307200) == pytest.approx(307.2)
    _got, part = short()
    assert part["rate_label"] == "COUNTED" and not_as_stated(part) == []


def test_control_comparison_rules__e3s_rule_4_a_rate_below_its_floor_called_counted_is_not_as_stated():
    _got, part = short()
    low = dict(part, pfa=3e-4)                                         # 7.4 expected crossings in 24,576
    assert any("below the floor" in r for r in not_as_stated(low))


def test_gate_comparison_rules__e3s_rule_5_the_reported_model_is_the_named_one_at_every_station():
    _got, part = short()
    parts = [dict(part, station=s) for s in RULE["stations"]]
    assert [s for s, _r in report(parts)] == RULE["stations"]
    assert part["learner_counts"] == [SHORT["named_records"]] * 2 and part["reported"] is True


def test_control_comparison_rules__e3s_rule_5_another_model_or_a_station_left_out_is_refused():
    _got, part = short()
    parts = [dict(part, station=s) for s in RULE["stations"]]
    for other in ("the curve's 65,536", 1024):
        with pytest.raises(LearnRefusal) as e:
            report(parts, other)
        assert e.value.name == "NOT_THE_NAMED_MODEL"
    for ps in (parts[:3], parts + [dict(part, station="MPP")]):
        with pytest.raises(LearnRefusal) as e:
            report(ps)
        assert e.value.name == "NOT_THE_NAMED_MODEL"
    assert any("learner_counts" in r for r in not_as_stated(dict(part, learner_counts=[1024, 1024])))
    assert any("reported" in r for r in not_as_stated(dict(part, reported=False)))


# ------------------------------------------------------------------ the short form's reading

def test_gate_statistics__e3s_the_short_form_reaches_the_matched_filter_on_the_models_white_noise():
    got, part = short()
    assert not_as_stated(part) == [], not_as_stated(part)
    assert holds(part), "the experiment held"
    j = part["judge"]
    print("E3 short form: amplitude %d/%d; the matched filter %d of %d, the learner %d; cost %+.5f, se %.5f (pairs %.5f), "
          "%s; tolerance %.5f" % (short_stream()["figures"]["amplitude_num"], short_stream()["figures"]["amplitude_den"],
                                 j["reference_found"], j["n"], j["other_found"], j["cost"], j["se"], j["se_pairs"],
                                 j["reading"], j["tolerance"]))
    for w in ("matched", "learned"):
        c = part["carry"][w]["alternate"]
        print("E3 short form, carry %s: %.5f and %.5f of %.5f: %s" % (w, c["there"]["rate"], c["back"]["rate"],
                                                                     c["there"]["stated"], c["carries"]))
    for c in part["curve"]:
        print("E3 short form, curve: %d records, cost %+.5f, se %.5f, %s" % (c["records"], c["cost"], c["se"], c["reading"]))
    assert j["reading"] == "REACHES" and part["flags"] == 0 and part["peak_offset"] == TAPS - 1
    assert part["scores_identical_to_stats"] and part["core_equals_baseline_on_first_trials"]
    four = part["judge_four_block_joins"]
    print("E3 short form, the resampling on joins of four blocks: se %.5f against %.5f, %s" % (four["se"], j["se"], four["reading"]))
    assert four["blocks"] == SHORT["held_out"] // FOUR == 32 and four["cost"] == j["cost"]
    # on white noise D8 holds, so the matched filter's count is inside stats.tolerance's figure for it
    sigma = (lambda v: (v[0] / v[1]) ** 0.5)(source.table_variance(source.Noise(PROFILE, 0, 1477, 1, 0).table))
    injected = e3prep.response(matched_coefficients(), short_stream()["figures"]["amplitude_num"], 65536)[1]
    d = theory.deflection(matched_coefficients(), list(injected), sigma)
    check = tolerance.check_efficiency(j["reference_found"], j["n"], (122 + 1) / (12288 + 1), d, 12288)
    print("E3 short form, the matched filter against D8 at its d %.4f: %.4f, %+.2f se" % (d, check["expected"], check["z_score"]))
    assert check["inside"]


def test_e3s_experiment_a_part_survives_being_written_and_read_by_the_judge(tmp_path, capsys):
    _got, part = short()
    back = json.loads(json.dumps(part))
    assert not_as_stated(back) == [] and holds(back) and reading(back) == "REACHES"
    paths = []
    for s in RULE["stations"]:
        path = tmp_path / ("%s.json" % s)
        path.write_text(json.dumps(dict(part, station=s, plan=SHORT)), encoding="utf-8")
        paths.append(str(path))
    code = judge_parts(paths)
    out = capsys.readouterr().out
    assert code == 1 and "NOT AS STATED" in out, "short parts posing as stations are not the stated full parts"


# ------------------------------------------------------------------ the verdict's conditions, each alone

def test_control_statistics__e3s_each_condition_of_the_experiment_held_fails_alone():
    _got, part = short()
    assert holds(part)
    for name, value in (("flags", 2), ("scores_identical_to_stats", False), ("core_equals_baseline_on_first_trials", False),
                        ("comparison_refused", "UNEQUAL_FALSE_ALARM_RATE"), ("judge", None)):
        assert not holds(dict(part, **{name: value})), name
    for w in ("matched", "learned"):
        carry = json.loads(json.dumps(part["carry"]))
        carry[w]["alternate"]["carries"] = False
        assert not holds(dict(part, carry=carry)), w
        carry = json.loads(json.dumps(part["carry"]))
        carry[w]["halves"]["carries"] = False
        assert holds(dict(part, carry=carry)), "the carry by halves is reported, not in the verdict"
    # each field the judge holds a part to, changed alone, is a reason
    for name, value in (("k", 121), ("above", 121), ("base_above", 123), ("n", 4095), ("m", 12287),
                        ("spec_sha256", "0" * 64), ("injection_sha256", "0" * 64), ("first_new_epoch_index", SHORT["A"] + 1),
                        ("held_out_epochs", [BLANK_EPOCH]), ("scores_not_zero_while_blank", 1), ("handover_refusal", "QUANTISE_INPUT"),
                        ("blob_sha256", "0" * 64), ("plan", dict(SHORT, seed=1)), ("found", part["found"] + 1),
                        ("blocks_disjoint", "TRAINED_ON"), ("blocks_disjoint", None)):
        assert not_as_stated(dict(part, **{name: value})), name
    j = part["judge"]
    for name, value in (("seed", 1), ("resamples", 999), ("reference_only", j["reference_only"] + 1),
                        ("cost", j["cost"] + 1e-6), ("reading", "SHORT"), ("blocks", 63)):
        assert not_as_stated(dict(part, judge=dict(j, **{name: value}))), name
    # the learner's count and the judge's, moved together, still do not add up with the pairs
    moved = dict(part, found=part["found"] + 1, judge=dict(j, other_found=j["other_found"] + 1))
    assert any("do not add up" in r for r in not_as_stated(moved))
    # and a reading changes with its cost: the same se, a cost past 4 se either way
    assert judge_reading(dict(j, cost=4.01 * j["se"])) == "SHORT" and judge_reading(dict(j, cost=-4.01 * j["se"])) == "AHEAD"
    assert judge_reading(dict(j, cost=3.99 * j["se"])) == "REACHES"


# ------------------------------------------------------------------ the brief's third and fourth named controls

def test_control_statistics__e3s_the_judge_reads_as_short_a_filter_that_finds_a_stated_fraction_fewer():
    """On the short form's held-out samples: the matched filter with tap 20 negated, which D8 says finds
    0.0778 fewer at Pd one half (about 16% of what the matched filter finds), and the learner of the
    last 64 training records, 0.1325 fewer by E1's first-order figure. Each is shown to find fewer on
    this stream, and each is read SHORT; the matched filter against itself REACHES; the reverse AHEAD."""
    got, part = short()
    p = SHORT
    base, base_scores = short_base()
    flipped = list(matched_coefficients())
    flipped[20] = -flipped[20]
    cos = theory.deflection(flipped, E0, 1.0) / theory.deflection(E0, E0, 1.0)
    predicted = 0.5 - theory.pd_matched(PFA, cos * theory.q_inv(PFA))
    first = (p["training"] - 1) * p["block_frames"] + p["block_frames"] // 2      # the last 64 trials of the last block
    x = got["train"].astype(np.int64).reshape(-1, 1)
    sixty_four = trainer.train(x[first:], [r["index"] - first for r in got["truth"] if first <= r["index"] < p["A"]], TAPS)
    assert sixty_four.counts == [64, 64]
    weak = list(handover.coefficients(handover.candidate_blob(PROFILE, sixty_four.weights()))[0])
    for name, coeffs, least in (("tap 20 negated", flipped, 0.04), ("the learner of 64 records", weak, 0.07)):
        scores = E1.stat_scores_at_reads(got["held"], coeffs)
        res = compared(p, base, scores)
        print("CONTROL e3s worse, %s: the matched filter %d of %d, it %d: %.4f fewer (%.1f%% of the matched filter's), "
              "se %.5f, %s%s" % (name, res["reference_found"], res["n"], res["other_found"], res["cost"],
                                 100 * res["cost"] / res["reference_efficiency"], res["se"], res["reading"],
                                 "; D8 predicts %.4f" % predicted if name.startswith("tap") else ""))
        assert res["cost"] > least, "on this stream it does find fewer"
        assert res["reading"] == "SHORT"
        back = compared(p, judged_from_scores(p, scores), base_scores)
        assert back["reading"] == "AHEAD" and back["cost"] == -res["cost"]
    same = compared(p, base, base_scores)
    assert same["reading"] == "REACHES" and same["cost"] == 0.0
    assert abs(predicted - 0.0778) < 1e-3


def test_control_statistics__e3s_a_threshold_from_one_stretch_gives_or_fails_to_give_its_rate_on_another():
    """The short form's matched filter: a threshold from its first 64 held-out blocks, on the next 32 of the
    same white stream, CARRIES. The same threshold, on 32 blocks of the model's noise at 1.25 times the
    level, does NOT CARRY: D8's tail puts the rate at Q(2.3263 / 1.25) = 0.0314 against 0.0100."""
    base, _scores = short_base()
    p = SHORT
    same = empirical.carry(base["free"][:64], base["free"][64:96], PFA, p["resamples"], p["carry_seed"] + 10, Z)
    bf = p["block_frames"]
    noise = source.Noise(PROFILE, LOUD_SEED, 7385, 4, 32 * bf)                 # sigma 1846.25 = 1.25 x 1477
    loud = np.fromiter((f[0] for f in noise), dtype=np.int64, count=32 * bf)
    scores = stat_matched.matched_scores(loud.reshape(-1, 1), PROFILE, matched_coefficients())
    loud_free = np.concatenate([scores[b * bf:(b + 1) * bf][TAPS - 1::TAPS].reshape(-1, READS_PER_TRIAL)[:, :3].ravel()
                                for b in range(32)]).reshape(32, -1)
    assert loud_free.shape == base["free"][64:96].shape
    louder = empirical.carry(base["free"][:64], loud_free, PFA, p["resamples"], p["carry_seed"] + 11, Z)
    want = theory.q(theory.q_inv(PFA) / 1.25)
    for what, c in (("the same stream", same), ("1.25 times the level", louder)):
        print("CONTROL e3s carry, %s: %.5f of the stated %.5f, se %.5f, %+.2f se: %s"
              % (what, c["rate"], c["stated"], c["se"], c["z_score"], "CARRIES" if c["carries"] else "DOES NOT CARRY"))
    assert same["carries"] and not louder["carries"]
    assert abs(louder["rate"] - want) < 4 * louder["se"] and abs(want - 0.0314) < 5e-4
    # the part's own check, both ways by alternate blocks, carries on the white stream for both models
    _got, part = short()
    assert all(part["carry"][w]["alternate"]["carries"] for w in ("matched", "learned"))


def test_control_statistics__e3s_the_two_checks_on_the_instrument_can_each_fail():
    """Two of the conditions are comparisons made inside `evaluate`: every score read against the
    statistics' exact filter, and the core against the baseline. Each is shown to report a difference."""
    got, part = short()
    p = SHORT
    learned_scores = E1.stat_scores_at_reads(got["held"], part["coefficients"])
    base_scores = E1.stat_scores_at_reads(got["held"], matched_coefficients())
    assert core_agrees(p, got["held"], got["blob"], learned_scores), "the core holding the learned blob gives its scores"
    assert not core_agrees(p, got["held"], matched_blob(), learned_scores), "and the core holding the matched filter does not"
    assert not core_agrees(p, got["held"], got["blob"], base_scores)
    off = learned_scores.copy()
    off[5] += 1
    assert not core_agrees(p, got["held"], got["blob"], off), "one score one unit off"
    assert part["scores_identical_to_stats"] and scores_identical(got["held"], part["coefficients"], got["reads"])
    for g, delta in ((0, 1), (len(got["reads"]) - 1, -1)):            # the first score read and the last, one unit each way
        reads = [dict(r) for r in got["reads"]]
        reads[g]["score"] += delta
        assert not scores_identical(got["held"], part["coefficients"], reads), (g, delta)
    assert not scores_identical(got["held"], matched_coefficients(), got["reads"]), "another filter's scores are not these"
    assert not holds(dict(part, scores_identical_to_stats=False))


# ------------------------------------------------------------------ what the short form's layout does not reach

def test_e3s_experiment_a_stations_part_is_held_to_its_committed_blocks_and_they_are_disjoint():
    _got, part = short()
    posed = dict(part, station="posed")
    kw = dict(plan_of=lambda s: SHORT, sets_of=lambda p: committed_sets()["short"])
    assert not_as_stated(posed, blocks_of=lambda s: list(part["blocks_sha256"]), **kw) == []
    other = list(part["blocks_sha256"][:-1]) + ["0" * 64]
    assert any("committed blocks" in r for r in not_as_stated(posed, blocks_of=lambda s: other, **kw))
    for station in RULE["stations"]:
        assert len(committed_blocks(station)) == 528
        spans = utc_spans(station)
        assert disjoint(spans) == 528, station
        assert [s[2] for s in spans["training"] + spans["held_out"]] == committed_blocks(station)
        assert max(e for _s, e, _d in spans["training"]) <= min(s for s, _e, _d in spans["held_out"]), \
            "every training block ends before the first held-out block begins"
    assert committed_blocks("XYZ") is None
    assert part["blocks_disjoint"] == SHORT["training"] + SHORT["held_out"]
    # and the part records what the check says of the spans it is handed: one held-out block that is a training block's
    got = short()[0]
    s = short_stream()["spans"]
    bad = {"training": s["training"], "held_out": s["held_out"][:3] + [s["training"][5]] + s["held_out"][4:]}
    quick = evaluate(dict(SHORT, resamples=20), got, _short["schedule"], spans=bad)
    assert quick["blocks_disjoint"] == "TRAINED_ON" and not_as_stated(dict(part, blocks_disjoint=quick["blocks_disjoint"]))


def test_e3s_experiment_a_full_parts_inputs_are_the_committed_ones():
    """What `--full` hands `measure` and `evaluate`, short of the records themselves, which are not in the tree."""
    for station in RULE["stations"]:
        p, sets, paths, schedule, spans = full_inputs(station, "DATA")
        assert p == full_plan(station) and sets == committed_sets()["stations"][station]
        assert len(paths) == 528 and paths[0] == os.path.join("DATA", station + "/training-000.und")
        assert paths[127].endswith("training-127.und") and paths[128].endswith("held_out-000.und") and paths[-1].endswith("held_out-399.und")
        assert check_injection_set(p, schedule) == sets["sha256"] and len(schedule) == 128 * 512 + 400 * 256
        assert schedule[0]["index"] == 64 and schedule[-1]["index"] == p["length"] - 256 + 192
        assert disjoint(spans) == 528
    with pytest.raises(ValueError):
        full_inputs("XYZ", "DATA")


def test_e3s_experiment_the_named_model_learns_from_the_last_of_the_training_blocks(tmp_path):
    """The full run's named model is the learner of the last 32 of 128 training blocks; the short form's is all
    of them, so this is held on a part of its own: 4 training blocks of 1,024 frames, the named model the last 2."""
    tiny = make_plan("tiny", "tiny", 1024, 4, 2, 2, (), 1, 2, 10)
    noise = source.Noise(PROFILE, SHORT_NOISE_SEED, 300, 1, tiny["length"])
    x = np.array([f[0] for f in noise], dtype=np.int64)
    paths = []
    for b in range(tiny["training"] + tiny["held_out"]):
        path = tmp_path / ("b%d.und" % b)
        path.write_bytes(e3prep.recording_bytes(x[b * 1024:(b + 1) * 1024]))
        paths.append(str(path))
    schedule = schedule_for(tiny, 65536, 65536)
    committed = dict(zip(("sha256", "records"), E1.independent_digest(schedule)))
    got = measure(tiny, paths, schedule, committed=committed)
    assert got["learner"].counts == [16, 16] == [tiny["named_records"]] * 2
    assert got["learner"].weights() == learner_of(got["train"], tiny, 2, schedule).weights()
    assert got["learner"].weights() != learner_of(got["train"], tiny, 4, schedule).weights()
    assert got["first_new_epoch_index"] == tiny["A"] == 4096

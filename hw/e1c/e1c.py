"""Stage E1 on the card, the desktop's side: the training, the cases, the model's expectations, and the judging of
the card's records.

    python hw/e1c/e1c.py cases   <folder>                 each part's set trained here, held to E1's committed part;
                                                          every piece, the two swap runs, the flip; order.txt
    python hw/e1c/e1c.py expect  <folder> --part c        part c: its training stretch through the blank core, its four
                                                          pieces under both sets, in one process; its part, against E1's
    python hw/e1c/e1c.py expect  <folder> --swap blank    the swap run of E1's own flow (blank, then the learned set at A)
    python hw/e1c/e1c.py expect  <folder> --swap matched  the swap run over the matched filter
    python hw/e1c/e1c.py expect  <folder> --flip          the flip piece
    python hw/e1c/e1c.py compare <folder> <runs folder> [--parts 5 ...]   the card's records judged; exit 0 only on PASS
    python hw/e1c/e1c.py short   <folder>                 the short form through every step, the card the first size's
                                                          stand-in, against LRN-A's own short form (not in the gate)

Run from the repository's root. DESKTOP ONLY: this file imports the model, the statistics package, `learn/` and, for
the experiment as stage E1 states it, `tests/test_lrn_a_e1.py` (its plan, its schedule, its facts, its check of the
injection set, its read rules, `wired`, `evaluate` and `judge_parts`), as hw/e0c/e0c.py imports test_seam_e0 (the
lead's ruling of 2026-11-25 20:56, item 7). Nothing the box runs imports it.

THE CASES (`cases`), under <folder>:
  table.json, blank.blob, matched.blob     the noise table of sigma 1477/1; E1's blank set; E0's matched filter for e0
  part<c>/learned.blob, part<c>/part.json  the set the desktop trained for part c, and the part's plan
  part<c>/p<q>/piece.json, schedule.json   piece q of part c's held-out stretch (hw/e1c/cut.py's stated cut)
  swap-blank/, swap-matched/               the swap runs on the named part's stream from frame 0, 2 A frames: the
                                           blank set, or the matched filter, at epoch 0, the learned set written into
                                           the shadow once A / 2 frames are taken and committed at A (swap.json)
  flip/                                    the named part's learned p0, run with round 3's flip of the learned set
  order.txt                                every run, in the card day's order: the named part first
THE EXPECTATIONS (`expect`), under <folder>/expect/: for each run, <run>.json: the SHA-256 of the model's canonical
records whole and for each block of 65,536, the OR of their flags, and the digest of its reads. For each part,
part<c>.json: the desktop's training fields, the statistics' own reads of the same samples with the same integers
(digests, and the 512 baseline scores of the first 256 test trials), the model's own part made in pieces by E1's
own `evaluate`, and that part against E1's committed one, key for key: the premise at full scale.
THE JUDGING (`compare`): bit identity run by run, by the block hashes; the reads FROM THE CARD'S BYTES; each part's
card part, made from them by `evaluate_card`, against E1's committed part key for key; E1's own `judge_parts` on the
six card parts, whose output must be docs/studies/e1/judge-output.txt byte for byte; the two swap runs; the flip.

Which authority each line rests on: bit identity (the model); the parts and the judge's output (stage E1's committed
record, and `stats/` inside the judge). The counts equal E1's in software exactly when every record is the model's,
so nothing here is new evidence about sensitivity (the plan, the lead's reading of 2026-11-25 20:30).
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
import struct
import sys
from array import array

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (ROOT, os.path.join(ROOT, "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402

from spec import constants as C  # noqa: E402
from model import inject, run, source, weights  # noqa: E402
from model import records as model_records  # noqa: E402
from model.detector import Core  # noqa: E402
from model.refusal import Refusal  # noqa: E402
from stats import matched as stat_matched  # noqa: E402
from stats import theory, tolerance  # noqa: E402
from learn import handover, trainer  # noqa: E402
from learn.errors import LearnRefusal  # noqa: E402

import test_lrn_a_e1 as E1  # noqa: E402  the experiment as stage E1 states it

from hw.e0c import pieces as P0  # noqa: E402
from hw.e0c.e0c import read_json, write_json  # noqa: E402
from hw.e1c import cut as K  # noqa: E402
from hw.e1c.errors import E1CRefusal  # noqa: E402

PROFILE, SIGMA, TAPS, GRID = E1.PROFILE, E1.SIGMA, E1.TAPS, E1.STRIDE
CHANNELS = C.PROFILES[PROFILE]["channels"]
BLOCK = 65536
NAMED = E1.NAMED
SETS = (("learned", E1.LEARNED_EPOCH), ("matched", E1.BLANK_EPOCH))
SWAPS = ("blank", "matched")
E1_FOLDER = os.path.join(ROOT, "docs", "studies", "e1")
E1_OUTPUT = os.path.join(E1_FOLDER, "judge-output.txt")
TRAINING_KEYS = ("coefficients", "blob_sha256", "learner_counts", "handover_refusal")

if CHANNELS != 1:
    raise ImportError("stage E1 is one channel of 16 bits (%s); this file keeps a sample a frame" % PROFILE)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def write_bytes(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def part_dir(folder, key):
    return os.path.join(folder, "part%s" % key)


def run_name(key, q, which):
    return "c%s-p%d-%s" % (key, q, which)


def stated_plans():
    return dict((c, E1.plan(c)) for c in range(len(E1.COUNTS)))


def committed_parts():
    """Stage E1's committed parts, c0.json to c5.json, by part. Read for their coefficients and counts: never for
    `spec_sha256`, so that they hold whichever definition made them (the lead's ruling, 2026-11-25 20:56)."""
    return dict((c, read_json(os.path.join(E1_FOLDER, "c%d.json" % c))) for c in range(len(E1.COUNTS)))


def table():
    return list(source.Noise(PROFILE, 0, SIGMA[0], SIGMA[1], 0).table)


# ------------------------------------------------------------------ the training, on the desktop

def training_stream(p, schedule, blank=None):
    """Frames 0 .. A - 1 of the part's stream as the injector makes them, the truth indexes below A, and, with the
    blank set, what the blank core makes of those frames: E1's own training stretch (tests/test_lrn_a_e1.py,
    `measure`). Returns a dict: samples (array of the frames' samples), labels, and with `blank` not_blank (scores
    not 0), flags (their OR) and records_sha256 (the SHA-256 of the blank core's canonical records)."""
    a = p["A"]
    noise = source.Noise(PROFILE, p["seed"], SIGMA[0], SIGMA[1], p["length"])
    frames, truth = inject.inject(PROFILE, noise, schedule, p["length"])
    samples = array("h")
    out = {"labels": [r["index"] for r in truth if r["index"] < a]}
    if blank is None:
        for _i, (sample,) in zip(range(a), frames):
            samples.append(sample)
    else:
        core, h, not_blank, flags = Core(blank, E1.BLANK_EPOCH), hashlib.sha256(), 0, 0
        for _i, frame in zip(range(a), frames):
            samples.append(frame[0])
            r = core.step(frame)
            h.update(model_records.pack("score", r))
            not_blank += r["score"] != 0
            flags |= r["flags"]
        out.update(not_blank=not_blank, flags=flags, records_sha256=h.hexdigest())
    out["samples"] = samples
    return out


def as_frames(samples):
    return np.frombuffer(samples, dtype=np.int16).reshape(-1, 1) if isinstance(samples, array) else samples


def check_training(p, x, labels):
    """Rule 2 of stage E1 as the host's training meets it: it reads frames 0 to A - 1 and nothing past them, and no
    labelled window reaches A, where the judged stretch begins. Refused, learn's TRAINED_ON."""
    a = p["A"]
    if x.shape[0] != a:
        raise LearnRefusal("TRAINED_ON", "the training is handed %d frames; it reads frames 0 to %d alone, and the "
                           "judged stretch begins at A = %d" % (x.shape[0], a - 1, a))
    reach = [j for j in labels if j + TAPS > a]
    if reach:
        raise LearnRefusal("TRAINED_ON", "the signal window of the truth record at %d reaches frame %d, at or past "
                           "A = %d, where the judged stretch begins" % (reach[0], reach[0] + TAPS - 1, a))


def train(p, x, labels, make_learner=None):
    """E1's learner on the training stretch, as E1's `measure` makes it: (learner, blob or None, refusal name)."""
    x = as_frames(x)
    check_training(p, x, labels)
    learner = trainer.MeanDifference(1, TAPS) if make_learner is None else make_learner()
    trainer.train(x, labels, TAPS, learner)
    try:
        return learner, handover.candidate_blob(PROFILE, learner.weights()), None
    except Refusal as e:             # the model's own refusal of the candidate: nothing could be handed over
        return learner, None, e.name


def learned_info(learner, blob, refusal):
    return {"coefficients": list(handover.coefficients(blob)[0]) if blob is not None else None,
            "blob_sha256": weights.unpack(blob)["sha256"] if blob is not None else None,
            "learner_counts": list(learner.counts), "handover_refusal": refusal}


def check_learned(key, info, reference):
    """The set trained here against the committed part's: equal in coefficients, blob hash, counts and refusal, or
    LEARNED_SET."""
    differ = [k for k in TRAINING_KEYS if reference.get(k, "missing") != info[k]]
    if differ:
        raise E1CRefusal("LEARNED_SET", "part %s: the set trained here is not the set the committed part carries: it "
                         "differs in %s" % (key, ", ".join(differ)))
    return info


# ------------------------------------------------------------------ the cases

def held_of(p, schedule):
    return [r for r in schedule if r["index"] < p["A"]], [r for r in schedule if r["index"] >= p["A"]]


def the_cut(p):
    return K.cut(p["A"], p["length"], K.stated_bounds(p["A"], p["B"], p["m_cal"], p["n"]), p["seed"], CHANNELS)


def run_order(keys, swap_part):
    """The card day's runs, in order: the named part's eight, its two swap runs and the flip, then the others, the
    last part first (stage E1's parts 4, 3, 2, 1, 0)."""
    first = [swap_part] + [k for k in reversed(keys) if k != swap_part]
    order = []
    for key in first:
        for which, epoch in SETS:
            blob = "part%s/learned.blob" % key if which == "learned" else "matched.blob"
            for q in range(4):
                order.append([run_name(key, q, which), "part%s/p%d" % (key, q), blob, epoch])
        if key == swap_part:
            for which in SWAPS:
                order.append(["swap-%s" % which, "swap-%s" % which, "%s.blob" % which, E1.BLANK_EPOCH,
                              "part%s/learned.blob" % key, "at", "after"])
            order.append(["flip-c%s-p0" % key, "flip", "flip/flip.blob", E1.LEARNED_EPOCH])
    return order


def cases(folder, plans=None, committed=None, references=None, swap_part=None):
    """Every case of the card day, under `folder`. `plans` maps a part's key to its plan (stage E1's six by
    default); `committed` is the injection sets' digests (vectors/lrn-a/injection_sets.json by default);
    `references` maps a key to the part its training is held to (E1's committed parts by default). The last two
    are for tests on a small plan; the card day passes neither. Returns the run order."""
    stated = plans is None
    plans = stated_plans() if stated else plans
    if references is None:
        if not stated:
            raise E1CRefusal("LEARNED_SET", "a plan that is not stage E1's stated six needs its reference parts")
        references = committed_parts()
    swap_part = (NAMED if stated else max(plans, key=str)) if swap_part is None else swap_part
    p = plans[swap_part]
    if 2 * p["A"] > p["B"]:
        raise E1CRefusal("PIECE_CUT", "a swap run of 2 A = %d frames passes B = %d, the test stretch's first frame"
                         % (2 * p["A"], p["B"]))
    os.makedirs(folder, exist_ok=True)
    blank, matched = handover.blank_blob(PROFILE, TAPS), E1.facts()["blob"]
    with open(os.path.join(folder, "table.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(table(), f)
    write_bytes(os.path.join(folder, "blank.blob"), blank)
    write_bytes(os.path.join(folder, "matched.blob"), matched)
    learned = {}
    for key, p in plans.items():
        schedule = E1.schedule_for(p)
        digest = E1.check_injection_set(p, schedule, committed)          # rule 1: before a frame is drawn
        tr = training_stream(p, schedule)
        learner, blob, refusal = train(p, tr["samples"], tr["labels"])
        info = check_learned(key, learned_info(learner, blob, refusal), references[key])
        learned[key] = blob
        write_bytes(os.path.join(part_dir(folder, key), "learned.blob"), blob)
        pieces = the_cut(p)
        training, held = held_of(p, schedule)
        scheds = [K.schedule_of(piece, held) for piece in pieces]
        K.check_joined(training, pieces, scheds, schedule)
        write_json(os.path.join(part_dir(folder, key), "part.json"),
                   {"key": key, "plan": p, "injection_sha256": digest, "learned": info, "pieces": len(pieces),
                    "stated": stated, "spec_sha256": C.SPEC_SHA256})
        for piece, sched in zip(pieces, scheds):
            d = os.path.join(part_dir(folder, key), "p%d" % piece.number)
            write_json(os.path.join(d, "piece.json"), dict(piece_info(key, piece, len(sched)), schedule_sha256=sha(
                json.dumps(sched).encode())))
            with open(os.path.join(d, "schedule.json"), "w", encoding="utf-8", newline="\n") as f:
                json.dump(sched, f)
    p = plans[swap_part]
    frames = 2 * p["A"]
    sched =[r for r in E1.schedule_for(p) if r["index"] + K.PULSE_LENGTH[r["pulse_id"]] <= frames]
    for which in SWAPS:
        d = os.path.join(folder, "swap-%s" % which)
        piece = K.Piece("swap-%s" % which, 0, frames, p["seed"])
        write_json(os.path.join(d, "piece.json"), piece_info(swap_part, piece, len(sched)))
        with open(os.path.join(d, "schedule.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(sched, f)
        write_json(os.path.join(d, "swap.json"), {"blob": "%s.blob" % which, "epoch": E1.BLANK_EPOCH,
                                                  "swap_blob": "part%s/learned.blob" % swap_part,
                                                  "swap_at": p["A"], "swap_after": p["A"] // 2})
    flip, where = P0.flipped(learned[swap_part])
    write_bytes(os.path.join(folder, "flip", "flip.blob"), flip)
    p0 = read_json(os.path.join(part_dir(folder, swap_part), "p0", "piece.json"))
    write_json(os.path.join(folder, "flip", "piece.json"),
               dict(p0, piece="flip", flip={"tap": where[0], "bit": 12, "before": where[1], "after": where[2]}))
    with open(os.path.join(folder, "flip", "schedule.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(read_json(os.path.join(part_dir(folder, swap_part), "p0", "schedule.json")), f)
    order = run_order(list(plans), swap_part)
    lines = []
    for row in order:
        if row[0].startswith("swap-"):
            row[5], row[6] = p["A"], p["A"] // 2
        lines.append(" ".join(str(v) for v in row))
    with open(os.path.join(folder, "order.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    write_json(os.path.join(folder, "cases.json"), {"keys": list(plans), "swap_part": swap_part, "stated": stated,
                                                    "spec_sha256": C.SPEC_SHA256})
    return order


def piece_info(key, piece, truth):
    return {"key": key, "piece": piece.number, "first": piece.first, "frames": piece.frames, "seed": piece.seed,
            "truth": truth, "profile": PROFILE, "sigma": list(SIGMA), "spec_sha256": C.SPEC_SHA256}


def read_order(folder):
    """order.txt as a list of runs: dicts of name, case, blob, epoch and, for a swap, swap_blob, swap_at, swap_after."""
    out = []
    with open(os.path.join(folder, "order.txt"), encoding="utf-8") as f:
        for line in f.read().split("\n"):
            if not line:
                continue
            v = line.split(" ")
            r = {"name": v[0], "case": v[1], "blob": v[2], "epoch": int(v[3])}
            if len(v) == 7:
                r.update(swap_blob=v[4], swap_at=int(v[5]), swap_after=int(v[6]))
            out.append(r)
    return out


# ------------------------------------------------------------------ the model's side

def run_records(folder, r):
    """The model's score records of one run of order.txt, in order: a piece through one core at the run's epoch, or
    a swap run through stage E1's own wiring (`wired`, `learn.handover.hand_over`)."""
    d = os.path.join(folder, r["case"])
    info, sched = read_json(os.path.join(d, "piece.json")), read_json(os.path.join(d, "schedule.json"))
    blob = read_bytes(os.path.join(folder, r["blob"]))
    noise = source.Noise(PROFILE, info["seed"], SIGMA[0], SIGMA[1], info["frames"])
    if "swap_blob" in r:
        if r["epoch"] != E1.BLANK_EPOCH:
            raise ValueError("E1's wiring starts a core at epoch 0; a swap run at %d is not E1C's" % r["epoch"])
        new = read_bytes(os.path.join(folder, r["swap_blob"]))
        pairs, _truth = E1.wired(PROFILE, noise, sched, info["frames"], blob, (r["swap_after"], lambda: new, r["swap_at"]))
    else:
        pairs, _truth = run.scores(noise, sched, info["frames"], blob, r["epoch"])
    return pairs


def remake(folder, r):
    """A function (first, count) -> the model's canonical bytes of those records of this run, made again."""
    def make(first, count):
        out = bytearray()
        for j, (_frame, rec) in enumerate(run_records(folder, r)):
            if j >= first + count:
                break
            if j >= first:
                out += model_records.pack("score", rec)
        return bytes(out)
    return make


class Hashed:
    """The SHA-256 of a run's canonical records whole and for each block, and the OR of their flags."""

    def __init__(self, block):
        self.block, self.whole, self.blocks, self.buf, self.flags, self.records = block, hashlib.sha256(), [], bytearray(), 0, 0
        self.size = block * P0.RECORD_BYTES

    def add(self, rec):
        self.buf += model_records.pack("score", rec)
        self.flags |= rec["flags"]
        self.records += 1
        if len(self.buf) == self.size:
            self._flush()

    def _flush(self):
        self.whole.update(self.buf)
        self.blocks.append(sha(bytes(self.buf)))
        self.buf = bytearray()

    def done(self, name, r, extra=None):
        if self.buf:
            self._flush()
        out = {"name": name, "case": r["case"], "blob": r["blob"], "epoch": r["epoch"], "records": self.records,
               "sha256": self.whole.hexdigest(), "block": self.block, "blocks": self.blocks, "flags": self.flags,
               "spec_sha256": C.SPEC_SHA256}
        out.update(extra or {})
        return out


def say(line):
    print(line, flush=True)


def expect_part(folder, key, block=BLOCK, out=say):
    """Part `key`: its training stretch through the blank core, the training made again, and its four pieces under
    both sets, in one process. Writes expect/<run>.json for its eight runs and expect/part<key>.json."""
    info = read_json(os.path.join(part_dir(folder, key), "part.json"))
    p = info["plan"]
    learned = read_bytes(os.path.join(part_dir(folder, key), "learned.blob"))
    blank, matched = read_bytes(os.path.join(folder, "blank.blob")), read_bytes(os.path.join(folder, "matched.blob"))
    schedule = E1.schedule_for(p)
    tr = training_stream(p, schedule, blank)
    learner, blob, refusal = train(p, tr["samples"], tr["labels"])
    if blob != learned:
        raise E1CRefusal("LEARNED_SET", "part %s: the set trained again is not the case's learned.blob" % key)
    order = dict((r["name"], r) for r in read_order(folder))
    held = array("h")
    reads = {"learned": [], "matched": []}
    flags = {"learned": 0, "matched": 0}
    first_new = None
    for q in range(info["pieces"]):
        d = os.path.join(part_dir(folder, key), "p%d" % q)
        pc, sched = read_json(os.path.join(d, "piece.json")), read_json(os.path.join(d, "schedule.json"))
        noise = source.Noise(PROFILE, pc["seed"], SIGMA[0], SIGMA[1], pc["frames"])
        frames, _truth = inject.inject(PROFILE, noise, sched, pc["frames"])
        cores = {"learned": Core(learned, E1.LEARNED_EPOCH), "matched": Core(matched, E1.BLANK_EPOCH)}
        hashed = {"learned": Hashed(block), "matched": Hashed(block)}
        samples = array("h")
        for j, frame in enumerate(frames):
            samples.append(frame[0])
            read = j % GRID == GRID - 1
            for which, core in cores.items():
                rec = core.step(frame)
                hashed[which].add(rec)
                if read:
                    reads[which].append(dict(rec, index=pc["first"] + rec["index"]))
                if which == "learned" and first_new is None and rec["epoch"] != E1.BLANK_EPOCH:
                    first_new = pc["first"] + rec["index"]
        held.extend(samples)
        for which, _epoch in SETS:
            name = run_name(key, q, which)
            mine = [x["score"] for x in reads[which] if pc["first"] <= x["index"] < pc["first"] + pc["frames"]]
            e = hashed[which].done(name, order[name], {"reads_sha256": P0.digest_scores(mine), "samples_sha256":
                                                         sha(samples.tobytes())})
            flags[which] |= e["flags"]
            write_json(os.path.join(folder, "expect", name + ".json"), e)
            out("expect %s: %d records, %s" % (name, e["records"], e["sha256"][:16]))
    x = np.frombuffer(held, dtype=np.int16)
    f = E1.facts()
    coeffs = list(handover.coefficients(learned)[0])
    stat_l = [int(v) for v in E1.stat_scores_at_reads(x, coeffs).tolist()]
    stat_m = [int(v) for v in E1.stat_scores_at_reads(x, f["coeffs"]).tolist()]
    stats = {"learned_reads_sha256": P0.digest_scores(stat_l), "matched_reads_sha256": P0.digest_scores(stat_m),
             "base_first_trials": stat_m[p["m_cal"]:p["m_cal"] + 2 * E1.CORE_CHECK]}
    desktop = {"handover_refusal": refusal, "learner_counts": list(learner.counts),
               "injection_sha256": info["injection_sha256"],
               "stream_sha256": sha(tr["samples"].tobytes() + held.tobytes()),
               "scores_not_zero_while_blank": tr["not_blank"], "training_flags": tr["flags"],
               "blank_records_sha256": tr["records_sha256"]}
    extra = extra_of(desktop, first_new, flags["learned"], tr["not_blank"])
    model_part = E1.evaluate(p, reads["learned"], x, learned, extra)
    mirror = evaluate_card(p, reads["learned"], reads["matched"], learned, stats, extra)
    summary = {"key": key, "model_part": model_part, "stats": stats, "desktop": desktop,
               "mirror_equal": mirror == model_part,
               "matched_identical_to_stats": [x["score"] for x in reads["matched"]] == stat_m,
               "matched_flags": flags["matched"], "spec_sha256": C.SPEC_SHA256}
    if info.get("stated"):
        summary["against_e1"] = differing(model_part, committed_parts()[key])
    write_json(os.path.join(folder, "expect", "part%s.json" % key), summary)
    return summary


def extra_of(desktop, first_new, learned_flags, not_blank):
    """The keys of a part that `evaluate` takes from its caller, as E1's `part_of` gives them."""
    return {"handover_refusal": desktop["handover_refusal"], "first_new_epoch_index": first_new,
            "flags": desktop["training_flags"] | learned_flags, "scores_not_zero_while_blank": not_blank,
            "learner_counts": desktop["learner_counts"], "injection_sha256": desktop["injection_sha256"],
            "stream_sha256": desktop["stream_sha256"]}


def differing(part, reference):
    """The keys in which a part is not the reference part, every key of either."""
    return sorted(k for k in set(part) | set(reference) if part.get(k, "missing") != reference.get(k, "missing"))


def expect_swap(folder, which, block=BLOCK):
    """The model's run of a swap run, by stage E1's own wiring: every record's hash, the records before the commit
    (their hash, how many scores are not 0, their flags), and the first record of the new epoch."""
    r = [x for x in read_order(folder) if x["name"] == "swap-%s" % which][0]
    hashed, prefix, before = Hashed(block), hashlib.sha256(), {"not_blank": 0, "flags": 0}
    first_new = None
    for _frame, rec in run_records(folder, r):
        hashed.add(rec)
        if rec["index"] < r["swap_at"]:
            prefix.update(model_records.pack("score", rec))
            before["not_blank"] += rec["score"] != 0
            before["flags"] |= rec["flags"]
        if first_new is None and rec["epoch"] != r["epoch"]:
            first_new = rec["index"]
    e = hashed.done(r["name"], r, {"swap_at": r["swap_at"], "swap_after": r["swap_after"], "first_new_epoch_index":
                                   first_new, "before_commit_sha256": prefix.hexdigest(), "before_commit": before})
    write_json(os.path.join(folder, "expect", r["name"] + ".json"), e)
    return e


def expect_flip(folder, block=BLOCK):
    """The model's run of the flip piece, and the record the flip must first change against the learned set's
    run of the same piece: the first j at or past 63 - tap whose sample j - (63 - tap) is not 0, in the score
    field, by (after - before) times that sample."""
    r = [x for x in read_order(folder) if x["case"] == "flip"][0]
    info = read_json(os.path.join(folder, "flip", "piece.json"))
    hashed, samples = Hashed(block), array("h")
    for frame, rec in run_records(folder, r):
        hashed.add(rec)
        samples.append(frame[0])
    flip = info["flip"]
    j0 = TAPS - 1 - flip["tap"]
    j = next((i + j0 for i, s in enumerate(samples) if s != 0 and i + j0 < len(samples)), None)
    predicted = None if j is None else {"record": j, "field": "score",
                                        "difference": (flip["after"] - flip["before"]) * samples[j - j0]}
    e = hashed.done(r["name"], r, {"flip": flip, "predicted": predicted, "against": run_name(info["key"], 0, "learned")})
    write_json(os.path.join(folder, "expect", r["name"] + ".json"), e)
    return e


# ------------------------------------------------------------------ the card's side

def evaluate_card(p, reads, base_reads, blob, stats, extra=None):
    """A part in E1's form, as tests/test_lrn_a_e1.py's `evaluate` makes it, with the baseline's records handed in.

    `evaluate` makes the baseline's records from the statistics' float filter on the kept samples, and holds the
    model's core to them on the first 256 test trials. On the card the baseline is the card's own run of the matched
    filter, so its records are an argument here, and the statistics' reads come in `stats`, made beside the model's
    run by `expect_part`: the digest of the statistics' reads with the learned integers, and the 512 baseline
    scores of the first 256 test trials. Every other line is `evaluate`'s, by `evaluate`'s own functions. A test
    holds this equal to `evaluate`, key for key, whenever the baseline's records are the statistics' scores
    (tests/test_e1c_judge.py): a mirror, and its limit (docs/host/e1c.md, limit 9) is what that test cannot vary."""
    f = E1.facts()
    a, n, m = p["A"], p["n"], p["m"]
    free, at = E1.split(p, reads)
    learned = E1.entry("learned", free, at, a)
    t = learned["threshold"]
    coeffs = list(handover.coefficients(blob)[0]) if blob is not None else [0] * TAPS
    identical = stat_matched.scores_are_exact(PROFILE, coeffs) and \
        P0.digest_scores([r["score"] for r in reads]) == stats["learned_reads_sha256"]
    base_free, base_at = E1.split(p, base_reads)
    base = E1.entry("matched", base_free, base_at, a)
    first = [r["score"] for r in base_reads[p["m_cal"]:p["m_cal"] + 2 * E1.CORE_CHECK]]
    d_learned = theory.deflection(coeffs, f["injected"], f["sigma"]) if any(coeffs) else None
    part = {"part": p["part"], "name": p["name"], "trained_on": p["trained_on"], "labelled_windows": p["labelled_windows"],
            "seed": p["seed"], "profile": PROFILE, "sigma": list(SIGMA), "pfa": E1.PFA, "amplitude": list(E1.AMPLITUDE),
            "taps": TAPS, "spacing": E1.SPACING, "A": a, "B": p["B"], "length": p["length"], "n": n, "m": m,
            "k": t["k"], "above": t["above"], "threshold": t["threshold"], "threshold_epoch": t["epoch"],
            "held_out_epochs": sorted({r["epoch"] for r in reads}), "rate_floor": E1.rate_floor(m),
            "rate_label": E1.rate_label(E1.PFA, m), "coefficients": coeffs,
            "blob_sha256": weights.unpack(blob)["sha256"] if blob is not None else None,
            "d_learned": d_learned, "d_matched": f["d"], "found": int(learned["hits"].sum()),
            "base_threshold": base["threshold"]["threshold"], "base_above": base["threshold"]["above"],
            "base_found": int(base["hits"].sum()),
            "base_found_known_threshold": sum(1 for r in base_at if r["score"] > f["threshold_known"]),
            "scores_identical_to_stats": bool(identical),
            "core_equals_baseline_on_first_trials": len(first) == 2 * E1.CORE_CHECK and first == stats["base_first_trials"],
            "peak_offset": E1.peak_offset(blob) if blob is not None else None,
            "reported": p["part"] in ("short", NAMED), "spec_sha256": C.SPEC_SHA256}
    try:
        slope_learned = tolerance.roc_slope(t["pfa_effective"], d_learned if d_learned is not None else 0.0)
        pair = E1.compare_at_equal_rate(base, learned, tolerance.roc_slope(t["pfa_effective"], f["d"]), slope_learned)
        part.update(base_only=pair["a_only"], learned_only=pair["b_only"], noise_base_only=pair["noise_a_only"],
                    noise_learned_only=pair["noise_b_only"], noise_both=pair["noise_both"], comparison_refused=None)
    except LearnRefusal as e:               # ties at a threshold: the two are not at an equal rate, and are not compared
        part.update(base_only=None, learned_only=None, noise_base_only=None, noise_learned_only=None, noise_both=None,
                    comparison_refused=e.name)
    part.update(extra or {})
    return part


def first_epoch_change(data, first, epoch):
    """The stream index of the first record in `data` whose epoch is not `epoch`, or None."""
    for j, (_index, e, _flags, _score) in enumerate(P0.RECORD.iter_unpack(data[:len(data) - len(data) % P0.RECORD_BYTES])):
        if e != epoch:
            return first + j
    return None


def run_end(runs, name):
    """How a run ended, from host.run_case's report.json: "pass", "refused <name>", "failed" or "deadline"; None
    when there is no report."""
    report = os.path.join(runs, name, "report.json")
    if not os.path.exists(report):
        return None
    got = read_json(report)
    return "refused %s" % got["refused"]["name"] if "refused" in got else (
        "failed" if "failed" in got else ("deadline" if "deadline" in got else "pass"))


def compare_run(folder, r, runs, keep=False):
    """One run: the card's records.bin against the model's expectation. A report, and the bytes when `keep`."""
    exp = read_json(os.path.join(folder, "expect", r["name"] + ".json"))
    path = os.path.join(runs, r["name"], "records.bin")
    rep = {"name": r["name"], "identity": None, "run": None, "swap": None, "flags": None, "end": None}
    report = os.path.join(runs, r["name"], "report.json")
    if os.path.exists(report):
        got = read_json(report)
        rep["run"], rep["swap"] = got.get("run"), got.get("swap")
        rep["end"] = run_end(runs, r["name"])
    if not os.path.exists(path):
        return rep, None
    data = read_bytes(path)
    rep["identity"] = P0.compare_blocks(data, exp, remake(folder, r))
    rep["flags"] = P0.flags_seen(data)
    return rep, (data if keep else None)


def identity_line(rep):
    i, r = rep["identity"], rep.get("run") or {}
    fed = ("" if not r else "; truth %s before the start, %s while it ran, least slack %s frames, queue peak %s"
           % (r.get("truth_before_start"), r.get("truth_while_running"), r.get("least_slack"), r.get("queue_peak")))
    if i is None:
        return "  %-18s NOT RUN: no records.bin%s" % (rep["name"], "" if rep["end"] is None else " (%s)" % rep["end"])
    if i["identical"]:
        return "  %-18s IDENTICAL: %d records, every word the model's%s" % (rep["name"], i["records"], fed)
    return "  %-18s DIFFERENT: %d records of %d; %d block(s) differ; first %s" % (
        rep["name"], i["records"], i["expected_records"], i["blocks_differ"], json.dumps(i["first"]))


def check_set(folder, key, stated):
    """Part `key`'s case folders held to its stated cut: its plan stage E1's own when the run is the stated one,
    each piece once, each piece.json the cut's piece. PIECE_SET otherwise. Returns the part's part.json."""
    info = read_json(os.path.join(part_dir(folder, key), "part.json"))
    p = info["plan"]
    if stated and p != E1.plan(key):
        raise E1CRefusal("PIECE_SET", "part %s: its plan is not stage E1's part %s" % (key, key))
    pieces = the_cut(p)
    have = sorted(x for x in os.listdir(part_dir(folder, key)) if x.startswith("p") and
                  os.path.isdir(os.path.join(part_dir(folder, key), x)))
    if have != ["p%d" % x.number for x in pieces] or info["pieces"] != len(pieces):
        raise E1CRefusal("PIECE_SET", "part %s: pieces %s, the cut's are %s" % (key, have, ["p%d" % x.number for x in pieces]))
    for x in pieces:
        got = read_json(os.path.join(part_dir(folder, key), "p%d" % x.number, "piece.json"))
        if (got["first"], got["frames"], got["seed"], got["key"]) != (x.first, x.frames, x.seed, key):
            raise E1CRefusal("PIECE_SET", "part %s piece %d is not the stated cut's piece" % (key, x.number))
    return info


def card_part(folder, key, runs, order, swap_part, out, stated=False):
    """Part `key`'s card part, made from the card's own bytes of its eight runs, and what was found on the way.
    Returns (part or None, a dict of the conditions it met)."""
    info = check_set(folder, key, stated)
    p = info["plan"]
    summary = read_json(os.path.join(folder, "expect", "part%s.json" % key))
    learned = read_bytes(os.path.join(part_dir(folder, key), "learned.blob"))
    got = {"identical": True, "flags": 0, "learned_flags": 0, "matched_identical_to_stats": True, "read": True}
    reads = {"learned": [], "matched": []}
    first_new = None
    for which, epoch in SETS:
        for q in range(info["pieces"]):
            r = order[run_name(key, q, which)]
            rep, data = compare_run(folder, r, runs, keep=True)
            out(identity_line(rep))
            got["identical"] = got["identical"] and bool(rep["identity"] and rep["identity"]["identical"])
            if data is None:
                got["read"] = False
                continue
            got["flags"] |= rep["flags"]
            if which == "learned":
                got["learned_flags"] |= rep["flags"]
            pc = read_json(os.path.join(folder, r["case"], "piece.json"))
            piece = K.Piece(q, pc["first"], pc["frames"], pc["seed"])
            try:
                reads[which] += K.reads(data, piece)
            except E1CRefusal as e:
                got["read"] = False
                out("  %-18s its reads refused: %s" % (r["name"], e))
                continue
            if which == "learned" and first_new is None:
                first_new = first_epoch_change(data, pc["first"], E1.BLANK_EPOCH)
    if not got["read"]:
        return None, got
    desktop = summary["desktop"]
    not_blank, blank_from = desktop["scores_not_zero_while_blank"], "the desktop's model run"
    training_flags = desktop["training_flags"]
    got["blank_prefix_equal"] = None
    if key == swap_part and "swap-blank" in order:
        r = order["swap-blank"]
        path = os.path.join(runs, r["name"], "records.bin")
        whole = r["swap_at"] * P0.RECORD_BYTES
        data = read_bytes(path) if os.path.exists(path) else None
        if data is not None and len(data) >= whole:
            prefix = data[:whole]
            got["blank_prefix_equal"] = sha(prefix) == desktop["blank_records_sha256"]
            recs = list(P0.RECORD.iter_unpack(prefix))
            not_blank = sum(1 for x in recs if x[3] != 0)
            training_flags = 0
            for x in recs:
                training_flags |= x[2]
            blank_from = "the card's swap-blank run, records 0 to %d" % (r["swap_at"] - 1)
        else:
            # The run was refused, or ended short, or left no records: the stretch cannot come from the card, and
            # the line says so rather than naming the desktop's run as if it were the plan (VE1C, its (d)).
            end = run_end(runs, r["name"])
            got["blank_prefix_equal"] = None if data is None else False
            got["blank_short"] = True
            blank_from = ("NOT the card's: the swap-blank run %s; it left %s of the %d records before the commit, so "
                          "the blank stretch could not come from the card; the desktop's model run stands in"
                          % ("ended %s" % end if end else "left no report.json",
                             "none (no records.bin)" if data is None else "%d" % (len(data) // P0.RECORD_BYTES),
                             r["swap_at"]))
    got["blank_from"] = blank_from
    extra = extra_of(dict(desktop, training_flags=training_flags), first_new, got["learned_flags"], not_blank)
    part = evaluate_card(p, reads["learned"], reads["matched"], learned, summary["stats"], extra)
    got["matched_identical_to_stats"] = P0.digest_scores([x["score"] for x in reads["matched"]]) == \
        summary["stats"]["matched_reads_sha256"]
    return part, got


def judge_output(parts, folder):
    """What stage E1's own judge prints for these parts, written as files under `folder`, and what it returns."""
    paths = []
    for part in parts:
        path = os.path.join(folder, "c%s.json" % part["part"])
        write_json(path, part)
        paths.append(path)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = E1.judge_parts(paths)
    return buf.getvalue(), code


def against_output(printed, committed):
    """None when the two outputs are equal byte for byte, else the first line in which they differ."""
    a, b = printed.encode("utf-8"), committed
    if a == b:
        return None
    mine, theirs = printed.split("\n"), b.decode("utf-8").split("\n")
    for i, (x, y) in enumerate(zip(mine, theirs)):
        if x != y:
            return {"line": i + 1, "card": x, "e1": y}
    return {"line": min(len(mine), len(theirs)) + 1, "card": None, "e1": None}


def stale(record):
    """The name a committed card-day record is skipped by once the definition moves, or None: E1C-CARD-STALE when
    its `spec_sha256` is not the tree's. The card's image carries round 3's definition (CARD-e0.md, limit 9)."""
    return None if record.get("spec_sha256") == C.SPEC_SHA256 else "E1C-CARD-STALE"


def compare(folder, runs, keys=None, references=None, committed_output=None, out=print):
    """The card day's records judged. Returns (exit code, the record). `keys` limits it to some parts (the reported
    one alone, for a day cut short); `references` and `committed_output` are for tests on a small plan."""
    meta = read_json(os.path.join(folder, "cases.json"))
    stated, swap_part = meta["stated"], meta["swap_part"]
    order_list = read_order(folder)
    order = dict((r["name"], r) for r in order_list)
    all_keys = [swap_part] + [k for k in reversed(meta["keys"]) if k != swap_part]
    keys = all_keys if keys is None else [k for k in all_keys if k in keys]
    if stated:
        references = committed_parts() if references is None else references
        committed_output = read_bytes(E1_OUTPUT) if committed_output is None else committed_output
    ok = True
    out("E1 on the card: profile %s, sigma %d/%d, Pfa %.2f, e0 at amplitude %d/%d; parts %s"
        % (PROFILE, SIGMA[0], SIGMA[1], E1.PFA, E1.AMPLITUDE[0], E1.AMPLITUDE[1], ", ".join(str(k) for k in keys)))
    out("  bit identity, run by run (the model's authority), and each part from the card's own bytes:")
    parts, record = [], {"parts": [], "runs": [], "checks": {}, "spec_sha256": C.SPEC_SHA256}
    for key in keys:
        part, got = card_part(folder, key, runs, order, swap_part, out, stated)
        record["checks"][str(key)] = got
        ok = ok and got["identical"] and got["flags"] == 0 and got["matched_identical_to_stats"]
        if got.get("blank_prefix_equal") is False:
            ok = False
        if part is None:
            ok = False
            out("  part %s: NOT MADE: not every run's records could be read" % key)
            continue
        parts.append(part)
        ref = (references or {}).get(key)
        differ = differing(part, ref) if ref is not None else None
        ok = ok and differ == []
        whose = "E1's committed part" if stated else "its reference part"
        out("  part %s: %s; the card's baseline reads %s the statistics'; flags %d; the blank stretch from %s%s"
            % (key, "no reference given" if ref is None else
               ("EQUAL to %s, key for key" % whose if not differ else "DIFFERS from %s in %s" % (whose, ", ".join(differ))),
               "equal to" if got["matched_identical_to_stats"] else "NOT equal to", got["flags"], got["blank_from"],
               "" if got["blank_prefix_equal"] is None or got.get("blank_short") else (
                   "; its records equal the desktop's blank run" if got["blank_prefix_equal"] else
                   "; its records are NOT the desktop's blank run")))
    record["parts"] = parts
    # the judge
    if stated and len(parts) == len(E1.COUNTS) and sorted(p["part"] for p in parts) == list(range(len(E1.COUNTS))):
        printed, code = judge_output(sorted(parts, key=lambda q: q["part"]), os.path.join(runs, "judge"))
        diff = against_output(printed, committed_output)
        ok = ok and diff is None and code == 0
        record["judge"] = {"code": code, "equal": diff is None, "first_difference": diff}
        out("  E1's own judge on the six card parts: its output %s" % (
            "EQUAL to docs/studies/e1/judge-output.txt, byte for byte" if diff is None else
            "DIFFERS from docs/studies/e1/judge-output.txt from line %d: %r against %r" % (diff["line"], diff["card"], diff["e1"])))
        out("  " + printed.rstrip("\n").split("\n")[-1])
    elif stated:
        ok = False
        record["judge"] = None
        out("  E1's own judge: NOT RUN: it judges the six parts together, and %d were made" % len(parts))
    else:
        record["judge"] = None
        out("  E1's own judge: not asked (not the stated run)")
    # the swaps and the flip
    if swap_part in keys:
        ok = compare_swaps(folder, runs, order_list, record, out) and ok
        ok = compare_flip(folder, runs, order_list, record, out) and ok
    out("== E1 CARD VERDICT: %s" % (("PASS, every record of every run the model's, every part E1's key for key, E1's "
                                     "judge's output byte for byte" if stated else
                                     "PASS, every record of every run the model's, every part its reference's key for "
                                     "key; the judge not asked (not the stated run)") if ok else "FAIL"))
    record["verdict"] = "PASS" if ok else "FAIL"
    write_json(os.path.join(runs, "card-e1.json"), record)
    return (0 if ok else 1), record


def compare_swaps(folder, runs, order_list, record, out):
    ok = True
    for r in [x for x in order_list if "swap_blob" in x]:
        rep, data = compare_run(folder, r, runs, keep=True)
        out(identity_line(rep))
        exp = read_json(os.path.join(folder, "expect", r["name"] + ".json"))
        first_new = first_epoch_change(data, 0, r["epoch"]) if data is not None else None
        s = rep.get("swap") or {}
        bracket = [s.get("next_index_before"), s.get("next_index_after")]
        good = bool(rep["identity"] and rep["identity"]["identical"]) and first_new == r["swap_at"] == \
            exp["first_new_epoch_index"] and all(type(v) is int and v < r["swap_at"] for v in bracket) and rep["flags"] == 0
        record["checks"][r["name"]] = {"identity": rep["identity"], "first_new_epoch_index": first_new,
                                       "next_index": bracket, "end": rep["end"]}
        out("== E1C SWAP %s: %s; the first record of the new epoch at %s, the named index %d; the swap bracketed by "
            "next_index %s; %s" % (r["name"][5:], "IDENTICAL" if rep["identity"] and rep["identity"]["identical"] else
                                   ("NOT RUN" if rep["identity"] is None else "DIFFERENT"), first_new, r["swap_at"],
                                   bracket, "SEEN" if good else "NOT AS IT MUST BE"))
        ok = ok and good
    return ok


def compare_flip(folder, runs, order_list, record, out):
    r = [x for x in order_list if x["case"] == "flip"][0]
    exp = read_json(os.path.join(folder, "expect", r["name"] + ".json"))
    rep, data = compare_run(folder, r, runs, keep=True)
    against = [x for x in order_list if x["name"] == exp["against"]][0]
    if data is None:
        out("== E1C FLIP CONTROL: NOT RUN: no records of %s" % r["name"])
        record["checks"]["flip"] = None
        return False
    other = P0.compare_blocks(data, read_json(os.path.join(folder, "expect", against["name"] + ".json")),
                              remake(folder, against))
    pred = exp["predicted"]
    first = other["first"] or {}
    at_predicted = pred is not None and first.get("record") == pred["record"] and first.get("field") == "score" and \
        type(first.get("card")) is int and first["card"] - first["model"] == pred["difference"]
    ok = rep["identity"]["identical"] and not other["identical"] and at_predicted
    record["checks"]["flip"] = {"identity": rep["identity"], "against_learned": other, "predicted": pred}
    out("the flip control, %s: against the flipped set's own model run %s; against the learned set's %s, first %s; "
        "predicted record %s" % (r["name"], "IDENTICAL" if rep["identity"]["identical"] else "DIFFERENT",
                                 "IDENTICAL" if other["identical"] else "DIFFERENT", json.dumps(other["first"]),
                                 None if pred is None else pred["record"]))
    out("== E1C FLIP CONTROL: %s" % ("SEEN, the flip reaches the records at the record predicted and the card ran the "
                                     "flipped set" if ok else "NOT AS IT MUST BE"))
    return ok


def short_end_to_end(base, out=say):
    """Stage E1's short form (tests/test_lrn_a_e1.py, `plan("short")`) through every step of the card day, the card
    the first size's stand-in (hw/e1c/standin.py): its cases, its expectations, its eleven runs through run_piece and
    host.run_case, and compare, against LRN-A's own short form part. Its exit code is compare's. About a minute and a
    half on the desktop; not in the gate. The premise in pieces at the short form's size, and the card's side end to
    end at a size where the statistics' floor of 100 crossings is met."""
    from hw.e1c import standin
    _got, part = E1.short()
    p = E1.plan("short")
    folder, runs = os.path.join(base, "cases"), os.path.join(base, "runs")
    cases(folder, plans={"short": p}, references={"short": part}, swap_part="short")
    summary = expect_part(folder, "short", out=lambda line: None)
    for which in SWAPS:
        expect_swap(folder, which)
    expect_flip(folder)
    out("the short form in pieces, the model's own run: evaluate_card equals evaluate: %s; the matched reads equal the "
        "statistics': %s; against LRN-A's short form part: %s" % (
            summary["mirror_equal"], summary["matched_identical_to_stats"],
            "EQUAL, key for key" if not differing(summary["model_part"], part) else
            "DIFFERS in %s" % differing(summary["model_part"], part)))
    with contextlib.redirect_stdout(io.StringIO()):
        codes = [standin.run(folder, r, os.path.join(runs, r["name"])) for r in read_order(folder)]
    out("the stand-in's runs: %d, exit codes %s" % (len(codes), sorted(set(codes))))
    code, _record = compare(folder, runs, references={"short": part}, out=out)
    return code if summary["mirror_equal"] and not differing(summary["model_part"], part) and set(codes) == {0} else 1


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("what", choices=("cases", "expect", "compare", "short"))
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--part", type=int)
    ap.add_argument("--swap", choices=SWAPS)
    ap.add_argument("--flip", action="store_true")
    ap.add_argument("--parts", type=int, nargs="+")
    a = ap.parse_args(argv)
    if a.what == "short":
        return short_end_to_end(a.paths[0])
    if a.what == "cases":
        order = cases(a.paths[0])
        print("cases: %d runs under %s" % (len(order), a.paths[0]))
        return 0
    if a.what == "expect":
        if a.swap:
            e = expect_swap(a.paths[0], a.swap)
            print("expect %s: %d records, %s; the new epoch from %s" % (e["name"], e["records"], e["sha256"][:16],
                                                                       e["first_new_epoch_index"]))
        elif a.flip:
            e = expect_flip(a.paths[0])
            print("expect %s: %d records, %s; predicted %s" % (e["name"], e["records"], e["sha256"][:16], e["predicted"]))
        else:
            s = expect_part(a.paths[0], a.part)
            print("expect part %d: evaluate_card equals evaluate: %s; the model's matched reads equal the statistics': "
                  "%s; against E1's committed part: %s" % (a.part, s["mirror_equal"], s["matched_identical_to_stats"],
                                                         "EQUAL, key for key" if s.get("against_e1") == [] else
                                                         "DIFFERS in %s" % s.get("against_e1")))
        return 0
    code, _record = compare(a.paths[0], a.paths[1], a.parts)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

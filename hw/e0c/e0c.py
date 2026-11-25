"""Stage E0 on the card, the desktop's side: the cases, the model's expectations, and the judging of the card's records.

    python hw/e0c/e0c.py cases   <folder>                 every piece of the five amplitudes, the flip, the timed sets
    python hw/e0c/e0c.py expect  <folder> --amplitude k   the model's run of amplitude k's pieces, in order, one process
    python hw/e0c/e0c.py expect  <folder> --flip          the model's run of the flip's piece (amplitude 2's piece 0)
    python hw/e0c/e0c.py expect  <folder> --timed         the model's run of each of the ten timed sets
    python hw/e0c/e0c.py compare <folder> <runs folder>   the card's records against the model's; the reads, the counts,
                                                          round 1's counts, and the judge
    python hw/e0c/e0c.py timed-judge <folder> <timed out> the ten timed runs' records and counts against the model's
    python hw/e0c/e0c.py premise <part.json> <round 1's part.json>   a rerun of a full part against round 1's
    (--n N --seed-base S --pieces P  on cases, expect and compare: a short form; the stated run has neither)

Run from the repository's root. DESKTOP ONLY: this file imports the model, the statistics package and, for the
experiment as round 1 states it, `tests/test_seam_e0.py` (its facts, its schedule's constants, its `not_as_stated`):
the lead's ruling of 2026-11-25 12:27. Nothing the box runs imports it (tests/test_e0c_compare.py holds that).

THE CASES (`cases`), under <folder>:
  e0/case.blob, e0/table.json            E0's matched filter for e0 (gain 1) and the noise table of sigma 1477/1
  e0/a<k>p<p>/piece.json, schedule.json  amplitude k's piece p: its first frame, frames, trials, seed, threshold
  flip/case.blob, flip/a2p0/...          round 3's flip control: e0's blob with bit 12 of its tap 28 flipped
  timed/gen<g>.blob, timed/timed.json, timed/schedule.json, timed/table.json   the ten sets of the timed runs
THE EXPECTATIONS (`expect`), beside each case: expected.json. The model's records are not kept: their SHA-256 is,
whole and for each block of 65,536 records, so a difference is found by its block and named, record and field, by
making that block again (`pieces.compare_blocks`). Beside them: the model's reads and counts, the OR of its flags,
the SHA-256 of the piece's samples, the statistics package's own reads with the same integer coefficients (their
SHA-256) and the real-coefficient filter's hit for every trial (a bitmap), as round 1's `full_part` measures the
cost of quantisation. `expect --amplitude k` chains its pieces' samples into one SHA-256 and holds the amplitude,
at the stated run, against round 1's part k in vectors/e0c/round1/.
THE JUDGING (`compare`), from the card's records.bin of each piece, in <runs folder>/a<k>p<p>/ (host.run_case's
--out): bit identity, piece by piece; the reads FROM THE CARD'S BYTES and their counts; for each amplitude the
card's part in round 1's form; that part against round 1's, field by field but the definition's hash; and the
judge, `stats.tolerance.check_efficiency` and `check_count`, with round 1's `not_as_stated` at the stated run.

Which authority each line rests on: bit identity (the model); reproduction (round 1's record); sensitivity (D8 and
the tolerance, `stats/`), which adds no fact the model's own run does not (the plan's track A).
"""
import argparse
import hashlib
import json
import math
import os
import sys
from array import array

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (ROOT, os.path.join(ROOT, "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np  # noqa: E402

from spec import constants as C  # noqa: E402
from model import records as model_records  # noqa: E402
from model import run, source, weights  # noqa: E402
from stats import matched as stat_matched  # noqa: E402
from stats import recovery, theory, tolerance  # noqa: E402
from stats.errors import StatRefusal  # noqa: E402

import test_seam_e0 as E0  # noqa: E402  the experiment as round 1 states it

from hw.e0c import pieces as P  # noqa: E402
from hw.e0c.errors import E0CRefusal  # noqa: E402

PIECES = 4
BLOCK = 65536
FLIP = (2, 0)                      # the flip control's piece: amplitude 2 (1/1), piece 0 (the lead's ruling)
TIMED_N, TIMED_SETS, TIMED_K = 10000, 10, 2
ROUND1 = os.path.join(ROOT, "vectors", "e0c", "round1")
OFFSETS = {"at": E0.TAPS - 1, "noise": -1, "late": E0.TAPS}


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1)
        f.write("\n")


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def channels():
    return C.PROFILES[E0.PROFILE]["channels"]


def the_cut(k, n, seed_base, pieces):
    """Amplitude k's stream and its pieces: (length, seed, tuple of Piece)."""
    length = E0.SPACING * (n + 1)
    bounds = P.even_bounds(n + 1, pieces, E0.SPACING)
    return length, seed_base + k, P.cut(length, bounds, n, seed_base + k, channels(), E0.SPACING, E0.FIRST, E0.TAPS)


_made = {}


def table():
    """The noise table of the experiment's sigma, made once."""
    if "table" not in _made:
        _made["table"] = list(source.Noise(E0.PROFILE, 0, E0.SIGMA[0], E0.SIGMA[1], 0).table)
        _made["table_sha256"] = sha(json.dumps(_made["table"]).encode())
    return _made["table"]


def facts(k):
    """`test_seam_e0.facts(k)`, made once a process: round 1's facts of amplitude k."""
    if ("facts", k) not in _made:
        _made[("facts", k)] = E0.facts(k)
    return _made[("facts", k)]


def piece_info(k, piece, n, length, seed, pieces, blob, sched, kind="e0"):
    f = facts(k)
    table()
    return {"kind": kind, "amplitude_number": k, "amplitude": f["amplitude"], "piece": piece.number, "pieces": pieces,
            "first": piece.first, "frames": piece.frames, "first_trial": piece.first_trial, "trials": piece.trials,
            "seed": piece.seed, "base_seed": seed, "n": n, "length": length, "profile": E0.PROFILE,
            "sigma": list(E0.SIGMA), "spacing": E0.SPACING, "first_index": E0.FIRST, "taps": E0.TAPS,
            "pulse": "e0", "gains": [1], "threshold": f["threshold"], "blob_sha256": sha(blob),
            "table_sha256": _made["table_sha256"], "schedule_sha256": sha(json.dumps(sched).encode()),
            "spec_sha256": C.SPEC_SHA256}


def timed_blob(g):
    """Set g of the timed runs: (g + 1) e0[j] + (9 - g) e0[63 - j], quantised by the definition's rule."""
    p = [(g + 1) * a + (TIMED_SETS - 1 - g) * b for a, b in zip(E0.E0, reversed(E0.E0))]
    return weights.matched_filter(E0.PROFILE, p, (1,))


def cases(folder, n=E0.FULL_N, seed_base=E0.FULL_SEED, pieces=PIECES, timed_n=TIMED_N):
    blob = facts(0)["blob"]
    if any(facts(k)["blob"] != blob for k in range(len(E0.AMPLITUDES))):
        raise AssertionError("the five amplitudes' blobs differ")
    tab = table()
    for sub in ("e0", "flip", "timed"):
        os.makedirs(os.path.join(folder, sub), exist_ok=True)
        with open(os.path.join(folder, sub, "table.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(tab, f)
    with open(os.path.join(folder, "e0", "case.blob"), "wb") as f:
        f.write(blob)
    flip, where = P.flipped(blob)
    with open(os.path.join(folder, "flip", "case.blob"), "wb") as f:
        f.write(flip)
    made = []
    for k in range(len(E0.AMPLITUDES)):
        length, seed, cut = the_cut(k, n, seed_base, pieces)
        num, den = E0.AMPLITUDES[k]
        for piece in cut:
            sched = P.schedule_of(piece, E0.SPACING, E0.FIRST, C.PULSE_IDS["e0"], num, den)
            d = os.path.join(folder, "e0", "a%dp%d" % (k, piece.number))
            write_json(os.path.join(d, "piece.json"), piece_info(k, piece, n, length, seed, pieces, blob, sched))
            with open(os.path.join(d, "schedule.json"), "w", encoding="utf-8", newline="\n") as f:
                json.dump(sched, f)
            made.append(d)
            if (k, piece.number) == FLIP:
                fd = os.path.join(folder, "flip", "a%dp%d" % FLIP)
                info = piece_info(k, piece, n, length, seed, pieces, flip, sched, kind="flip")
                info["flip"] = {"tap": where[0], "bit": 12, "before": where[1], "after": where[2]}
                write_json(os.path.join(fd, "piece.json"), info)
                with open(os.path.join(fd, "schedule.json"), "w", encoding="utf-8", newline="\n") as f:
                    json.dump(sched, f)
    # the timed runs: amplitude 1/1's stream, its first timed_n trials, ten sets
    f2 = facts(TIMED_K)
    tp = P.cut(E0.SPACING * (timed_n + 1), [0], timed_n, seed_base + TIMED_K, channels(), E0.SPACING, E0.FIRST,
               E0.TAPS)[0]
    sched = P.schedule_of(tp, E0.SPACING, E0.FIRST, C.PULSE_IDS["e0"], *E0.AMPLITUDES[TIMED_K])
    with open(os.path.join(folder, "timed", "schedule.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(sched, f)
    sets = []
    for g in range(TIMED_SETS):
        b = timed_blob(g)
        name = "gen%d.blob" % g
        with open(os.path.join(folder, "timed", name), "wb") as f:
            f.write(b)
        coeffs = list(weights.unpack(b)["filters"][0][0])
        exact = recovery.threshold_known_sigma(E0.PFA, f2["sigma"], coeffs)
        sets.append({"blob": name, "blob_sha256": sha(b), "threshold": math.floor(exact),
                     "d": theory.deflection(coeffs, f2["injected"], f2["sigma"])})
    write_json(os.path.join(folder, "timed", "timed.json"),
               {"profile": E0.PROFILE, "seed": tp.seed, "frames": tp.frames, "trials": tp.trials,
                "sigma": list(E0.SIGMA), "spacing": E0.SPACING, "first_index": E0.FIRST, "taps": E0.TAPS,
                "amplitude": f2["amplitude"], "offsets": {"at": OFFSETS["at"], "noise": OFFSETS["noise"]},
                "sets": sets, "schedule_sha256": sha(json.dumps(sched).encode()), "spec_sha256": C.SPEC_SHA256})
    return made


# ------------------------------------------------------------------ the model's side

def load_case(d):
    info = read_json(os.path.join(d, "piece.json"))
    sched = read_json(os.path.join(d, "schedule.json"))
    piece = P.Piece(info["piece"], info["first"], info["frames"], info["first_trial"], info["trials"], info["seed"])
    return info, piece, sched


def blob_of(folder, info):
    with open(os.path.join(folder, info["kind"], "case.blob"), "rb") as f:
        return f.read()


def model_pairs(info, sched, blob):
    noise = source.Noise(info["profile"], info["seed"], info["sigma"][0], info["sigma"][1], info["frames"])
    pairs, _truth = run.scores(noise, sched, info["frames"], blob)
    return pairs


def remake(info, sched, blob):
    """A function (first, count) -> the model's canonical bytes of those records of this piece, made again."""
    def make(first, count):
        out = bytearray()
        for j, (_frame, r) in enumerate(model_pairs(info, sched, blob)):
            if j >= first + count:
                break
            if j >= first:
                out += model_records.pack("score", r)
        return bytes(out)
    return make


def _rows(blob, profile):
    """The blob's filter 0 as a (channels, taps) list of rows, zeros for a channel it does not read."""
    config = weights.unpack(blob)
    rows = config["filters"][0]
    taps = len(next(iter(rows.values())))
    return [list(rows.get(c, [0] * taps)) for c in range(C.PROFILES[profile]["channels"])]


def _bitmap(hits):
    bits = bytearray((len(hits) + 7) // 8)
    for t, h in enumerate(hits):
        if h:
            bits[t >> 3] |= 1 << (t & 7)
    return bits.hex()


def unbitmap(text, n):
    bits = bytes.fromhex(text)
    return [bool(bits[t >> 3] >> (t & 7) & 1) for t in range(n)]


def expect_piece(d, blob, block=BLOCK, stream=None):
    """The model's run of the piece in folder d: writes and returns expected.json. `stream`, a hashlib object, is fed
    the piece's samples' canonical bytes, so that the pieces of one amplitude chain into its stream's SHA-256."""
    info, piece, sched = load_case(d)
    prof = C.PROFILES[info["profile"]]
    if prof["sample_bits"] != 16:
        raise E0CRefusal("PROFILE_UNKNOWN", "expect keeps a 16-bit stream's samples; %s is %d bits"
                         % (info["profile"], prof["sample_bits"]))
    want = {}
    for name, off in OFFSETS.items():
        for t in range(piece.trials):
            at = info["spacing"] * t + info["first_index"] + off
            if 0 <= at < piece.frames:
                want.setdefault(at, []).append((name, t))
    got = dict((name, [None] * piece.trials) for name in OFFSETS)
    whole, cur, blocks, in_block, flags = hashlib.sha256(), hashlib.sha256(), [], 0, 0
    samples = array("h")
    for j, (frame, r) in enumerate(model_pairs(info, sched, blob)):
        b = model_records.pack("score", r)
        whole.update(b)
        cur.update(b)
        in_block += 1
        if in_block == block:
            blocks.append(cur.hexdigest())
            cur, in_block = hashlib.sha256(), 0
        samples.extend(frame)
        flags |= r["flags"]
        for name, t in want.get(j, ()):
            got[name][t] = r["score"]
    if in_block:
        blocks.append(cur.hexdigest())
    if sys.byteorder != "little":
        raise AssertionError("the samples' canonical bytes are little-endian; this host is not")
    raw = samples.tobytes()
    if stream is not None:
        stream.update(raw)
    x = np.frombuffer(raw, dtype=np.int16).reshape(-1, prof["channels"])
    rows = _rows(blob, info["profile"])
    theirs = stat_matched.matched_scores(x, info["profile"], rows)
    at = np.asarray([info["spacing"] * t + info["first_index"] + OFFSETS["at"] for t in range(piece.trials)], dtype=int)
    quiet = at - OFFSETS["at"] + OFFSETS["noise"]
    stats_at = [int(v) for v in theirs[at].tolist()] if piece.trials else []
    stats_noise = [int(v) for v in theirs[quiet].tolist()] if piece.trials else []
    pulse = C.PULSES[info["pulse"]]
    real_rows = np.asarray([[g * p for p in pulse] for g in info["gains"]], dtype=np.float64)
    real = stat_matched.matched_scores(x, info["profile"], real_rows)
    real_threshold = recovery.threshold_known_sigma(E0.PFA, facts(info["amplitude_number"])["sigma"], real_rows)
    real_hits = [bool(v) for v in (real[at] > real_threshold).tolist()] if piece.trials else []
    model_hits = [s > info["threshold"] for s in got["at"]]
    found, _m, _n = P.count(got["at"], info["threshold"])
    noise_x, _m, _n = P.count(got["noise"], info["threshold"])
    late_x, _late_made, late_not = P.count(got["late"], info["threshold"])
    out = {"case": os.path.basename(os.path.normpath(d)), "kind": info["kind"], "blob_sha256": sha(blob),
           "records": piece.frames, "sha256": whole.hexdigest(), "block": block, "blocks": blocks, "flags": flags,
           "model": {"found": found, "noise_crossings": noise_x, "late_found": late_x, "late_not_read": late_not,
                     "reads_sha256": P.digest_scores(got["at"], got["noise"])},
           "stats": {"reads_sha256": P.digest_scores(stats_at, stats_noise),
                     "identical": stats_at == got["at"] and stats_noise == got["noise"]},
           "real": {"found": sum(real_hits), "hits": _bitmap(real_hits), "threshold": real_threshold,
                    "model_only": sum(1 for m, r in zip(model_hits, real_hits) if m and not r),
                    "real_only": sum(1 for m, r in zip(model_hits, real_hits) if r and not m)},
           "stream_sha256": sha(raw), "spec_sha256": C.SPEC_SHA256}
    write_json(os.path.join(d, "expected.json"), out)
    return out


def piece_dirs(folder, k, kind="e0"):
    names = sorted((x for x in os.listdir(os.path.join(folder, kind)) if x.startswith("a%dp" % k)),
                   key=lambda x: int(x.split("p")[1]))
    return [os.path.join(folder, kind, x) for x in names]


SUMMARY_FIELDS = ("stream_sha256", "found", "noise_crossings", "flags", "scores_identical_to_stats", "real_found",
                  "model_only", "real_only", "n", "seed", "length")


def summary_against_round1(s, r1):
    """The fields in which the model's run of an amplitude's pieces is not round 1's part: the premise in pieces."""
    return [name for name in SUMMARY_FIELDS if s.get(name) != r1.get(name)]


def expect_amplitude(folder, k, block=BLOCK):
    """Every piece of amplitude k, in order, in this one process; then the amplitude's summary, a<k>.json."""
    stream = hashlib.sha256()
    parts = []
    for d in piece_dirs(folder, k):
        info = read_json(os.path.join(d, "piece.json"))
        parts.append((info, expect_piece(d, blob_of(folder, info), block, stream)))
        print("expect a%dp%d: %d records, %s" % (k, info["piece"], info["frames"], parts[-1][1]["sha256"][:16]),
              flush=True)
    info0 = parts[0][0]
    s = {"amplitude_number": k, "n": info0["n"], "seed": info0["base_seed"], "length": info0["length"],
         "pieces": [e["case"] for _i, e in parts], "stream_sha256": stream.hexdigest(),
         "found": sum(e["model"]["found"] for _i, e in parts),
         "noise_crossings": sum(e["model"]["noise_crossings"] for _i, e in parts),
         "late_found": sum(e["model"]["late_found"] for _i, e in parts),
         "late_not_read": sum(e["model"]["late_not_read"] for _i, e in parts),
         "flags": max(e["flags"] for _i, e in parts),
         "scores_identical_to_stats": all(e["stats"]["identical"] for _i, e in parts),
         "real_found": sum(e["real"]["found"] for _i, e in parts),
         "model_only": sum(e["real"]["model_only"] for _i, e in parts),
         "real_only": sum(e["real"]["real_only"] for _i, e in parts), "spec_sha256": C.SPEC_SHA256}
    stated = info0["n"] == E0.FULL_N and info0["base_seed"] == E0.FULL_SEED + k
    if stated:
        s["against_round1"] = summary_against_round1(s, read_json(os.path.join(ROUND1, "part%d.json" % k)))
    write_json(os.path.join(folder, "e0", "a%d.json" % k), s)
    print("expect a%d: found %d, noise %d, stream %s%s" % (k, s["found"], s["noise_crossings"], s["stream_sha256"][:16],
          "" if not stated else ("; EQUAL to round 1's part %d" % k if not s["against_round1"]
                                 else "; DIFFERS from round 1's part %d in %s" % (k, ", ".join(s["against_round1"])))))
    return s


def expect_timed(folder):
    tdir = os.path.join(folder, "timed")
    t = read_json(os.path.join(tdir, "timed.json"))
    sched = read_json(os.path.join(tdir, "schedule.json"))
    info = {"profile": t["profile"], "seed": t["seed"], "sigma": t["sigma"], "frames": t["frames"]}
    out = []
    for s in t["sets"]:
        with open(os.path.join(tdir, s["blob"]), "rb") as f:
            blob = f.read()
        h, at, noise = hashlib.sha256(), [], []
        for j, (_frame, r) in enumerate(model_pairs(info, sched, blob)):
            h.update(model_records.pack("score", r))
            place = (j - t["first_index"]) % t["spacing"]
            trial = (j - t["first_index"]) // t["spacing"]
            if place == t["offsets"]["at"] and 0 <= trial < t["trials"]:
                at.append(r["score"])
            if (j + 1 - t["first_index"]) % t["spacing"] == 0 and 0 <= (j + 1 - t["first_index"]) // t["spacing"] < t["trials"]:
                noise.append(r["score"])
        out.append({"blob": s["blob"], "sha256": h.hexdigest(), "found": P.count(at, s["threshold"])[0],
                    "noise_crossings": P.count(noise, s["threshold"])[0], "reads": [len(at), len(noise)]})
    write_json(os.path.join(tdir, "expected.json"), {"sets": out, "spec_sha256": C.SPEC_SHA256})
    return out


# ------------------------------------------------------------------ the card's side

def compare_piece(folder, d, run_dir):
    """One piece: the card's records.bin in run_dir against the expectation beside its case. Returns a report."""
    info, piece, sched = load_case(d)
    exp = read_json(os.path.join(d, "expected.json"))
    with open(os.path.join(run_dir, "records.bin"), "rb") as f:
        data = f.read()
    blob = blob_of(folder, info)
    ident = P.compare_blocks(data, exp, remake(info, sched, blob))
    rep = {"case": exp["case"], "kind": info["kind"], "identity": ident, "run": None}
    report = os.path.join(run_dir, "report.json")
    if os.path.exists(report):      # host.run_case's account of the run: how far ahead the host kept the truth records
        rep["run"] = read_json(report).get("run")
    if len(data) != piece.frames * P.RECORD_BYTES:
        rep["reads"] = None
        return rep
    got = P.reads(data, piece, info["spacing"], info["first_index"], list(OFFSETS.values()))
    at, noise, late = got[OFFSETS["at"]], got[OFFSETS["noise"]], got[OFFSETS["late"]]
    hits = [s > info["threshold"] for s in at]
    real = unbitmap(exp["real"]["hits"], piece.trials)
    found, made, not_made = P.count(at, info["threshold"])
    late_x, late_made, late_not = P.count(late, info["threshold"])
    rep["reads"] = {"found": found, "noise_crossings": P.count(noise, info["threshold"])[0], "trials": piece.trials,
                    "not_read": not_made + P.count(noise, info["threshold"])[2],
                    "late_found": late_x, "late_read": late_made, "late_not_read": late_not,
                    "flags": P.flags_seen(data),
                    "identical_to_stats": P.digest_scores(at, noise) == exp["stats"]["reads_sha256"],
                    "real_found": sum(real), "model_only": sum(1 for h, r in zip(hits, real) if h and not r),
                    "real_only": sum(1 for h, r in zip(hits, real) if r and not h),
                    "stream_sha256": exp["stream_sha256"]}
    return rep


def check_set(folder, k, n, seed_base, pieces, kind="e0"):
    """The case folders of amplitude k, held to the stated cut: each piece once, each piece.json the cut's."""
    length, seed, cut = the_cut(k, n, seed_base, pieces)
    dirs = piece_dirs(folder, k, kind)
    have = [read_json(os.path.join(d, "piece.json")) for d in dirs]
    if [h["piece"] for h in have] != [p.number for p in cut]:
        raise E0CRefusal("PIECE_SET", "amplitude %d: pieces %s, the cut's are %s"
                         % (k, [h["piece"] for h in have], [p.number for p in cut]))
    for h, p in zip(have, cut):
        if (h["first"], h["frames"], h["first_trial"], h["trials"], h["seed"], h["amplitude_number"], h["n"]) != \
                (p.first, p.frames, p.first_trial, p.trials, p.seed, k, n):
            raise E0CRefusal("PIECE_SET", "amplitude %d piece %d is not the stated cut's piece" % (k, p.number))
    return dirs


def card_part(k, reports, seed_base, length, summary):
    """Amplitude k's part in round 1's form, from the card's reads of its pieces. Its `stream_sha256` is the
    desktop's, from `expect --amplitude k` (summary, a<k>.json): the stream the pieces were cut from, which the
    card does not return."""
    f = facts(k)
    r = [x["reads"] for x in reports]
    streams = hashlib.sha256("".join(x["stream_sha256"] for x in r).encode()).hexdigest()
    return {"part": k, "amplitude": f["amplitude"], "n": sum(x["trials"] for x in r), "seed": seed_base + k,
            "stream_sha256": summary["stream_sha256"],
            "profile": E0.PROFILE, "sigma": list(E0.SIGMA), "pfa": E0.PFA, "spacing": E0.SPACING, "length": length,
            "sigma_exact": f["sigma"], "d": f["d"], "expected": f["expected"], "threshold": f["threshold"],
            "found": sum(x["found"] for x in r), "noise_crossings": sum(x["noise_crossings"] for x in r),
            "flags": max(x["flags"] for x in r), "scores_identical_to_stats": all(x["identical_to_stats"] for x in r),
            "real_found": sum(x["real_found"] for x in r), "model_only": sum(x["model_only"] for x in r),
            "real_only": sum(x["real_only"] for x in r), "late_found": sum(x["late_found"] for x in r),
            "late_read": sum(x["late_read"] for x in r), "late_not_read": sum(x["late_not_read"] for x in r),
            "pieces_stream_sha256": streams, "spec_sha256": C.SPEC_SHA256}


ROUND1_FIELDS = ("amplitude", "n", "seed", "profile", "sigma", "pfa", "spacing", "length", "sigma_exact", "d",
                 "expected", "threshold", "found", "noise_crossings", "flags", "scores_identical_to_stats",
                 "real_found", "model_only", "real_only", "stream_sha256")


def against_round1(part, r1):
    """The fields in which a card part is not round 1's part, all but the definition's hash. Its stream_sha256 is
    the desktop's (see `card_part`): equal, it says the pieces were cut from round 1's own stream."""
    return [name for name in ROUND1_FIELDS if part.get(name) != r1.get(name)]


def stale(record):
    """The name a committed card-day record is skipped by once the definition moves, or None: E0C-CARD-STALE when
    its `spec_sha256` is not the tree's. The card's image carries round 3's definition (the plan's L14)."""
    return None if record.get("spec_sha256") == C.SPEC_SHA256 else "E0C-CARD-STALE"


def judge(parts, reports, round1=None, as_stated=None, out=print):
    """Every line of the card's verdict, and 0 or 1. `round1` maps k to round 1's part; `as_stated` is round 1's
    `not_as_stated`, applied when the run is the stated one."""
    ok = True
    out("E0 on the card: profile %s, sigma %d/%d, Pfa %.2f, the matched filter for e0, in pieces"
        % (E0.PROFILE, E0.SIGMA[0], E0.SIGMA[1], E0.PFA))
    out("  bit identity, piece by piece (the model's authority):")
    for rep in reports:
        i = rep["identity"]
        r = rep.get("run") or {}
        fed = ("" if not r else "; truth %s before the start, %s while it ran, least slack %s frames, queue peak %s"
               % (r.get("truth_before_start"), r.get("truth_while_running"), r.get("least_slack"), r.get("queue_peak")))
        if i["identical"]:
            out("  %-8s IDENTICAL: %d records, every word the model's%s" % (rep["case"], i["records"], fed))
        else:
            ok = False
            out("  %-8s DIFFERENT: %d records of %d; %d block(s) differ; first %s"
                % (rep["case"], i["records"], i["expected_records"], i["blocks_differ"], json.dumps(i["first"])))
    out("  the reads from the card's records, against round 1's record:")
    for p in parts:
        k = p["part"]
        r1 = (round1 or {}).get(k)
        differ = against_round1(p, r1) if r1 else None
        if differ:
            ok = False
        out("  %-9s found %d, noise %d, flags %d, identical to stats %s, real found %d, card only %d, real only %d; "
            "late %d of %d read (%d not read); %s"
            % ("%d/%d" % tuple(p["amplitude"]), p["found"], p["noise_crossings"], p["flags"],
               "yes" if p["scores_identical_to_stats"] else "NO", p["real_found"], p["model_only"], p["real_only"],
               p["late_found"], p["late_read"], p["late_not_read"],
               "no round 1 record given" if r1 is None else
               ("EQUAL to round 1's part %d" % k if not differ else "DIFFERS from round 1 in %s" % ", ".join(differ))))
        ok = ok and p["flags"] == 0 and p["scores_identical_to_stats"]
    reasons = as_stated(parts) if as_stated else []
    out("  the parts against the experiment as round 1 states it: %s"
        % ("not asked (a short form)" if as_stated is None else ("as stated" if not reasons else "NOT AS STATED")))
    for reason in reasons:
        out("    " + reason)
    ok = ok and not reasons
    out("  the judge (D8 and the tolerance, stats/):")
    for p in parts:
        try:
            v = tolerance.check_efficiency(p["found"], p["n"], p["pfa"], p["d"])
            c = tolerance.check_count(p["noise_crossings"], p["n"], p["pfa"])
        except StatRefusal as e:
            ok = False
            out("  %-9s REFUSED by the statistics: %s" % ("%d/%d" % tuple(p["amplitude"]), e))
            continue
        ok = ok and v["inside"] and c["inside"]
        out("  %-9s %d of %d, efficiency %.5f, D8 %.4f, %+.2f se, tolerance %.5f, %s; noise %d, %+.2f se, %s"
            % ("%d/%d" % tuple(p["amplitude"]), p["found"], p["n"], v["measured"], v["expected"], v["z_score"],
               v["tolerance"], "INSIDE" if v["inside"] else "OUTSIDE", p["noise_crossings"], c["z_score"],
               "INSIDE" if c["inside"] else "OUTSIDE"))
    out("== E0 CARD VERDICT: %s" % ("PASS, every record of every piece the model's, every count round 1's where "
                                    "given, every amplitude inside D8's tolerance" if ok else "FAIL"))
    return 0 if ok else 1


def compare(folder, runs, n=E0.FULL_N, seed_base=E0.FULL_SEED, pieces=PIECES, amplitudes=None, out=print):
    """Every amplitude's pieces in `runs` (host.run_case's --out folders, named as their cases) judged."""
    amplitudes = range(len(E0.AMPLITUDES)) if amplitudes is None else amplitudes
    parts, reports = [], []
    for k in amplitudes:
        dirs = check_set(folder, k, n, seed_base, pieces)
        reps = [compare_piece(folder, d, os.path.join(runs, os.path.basename(d))) for d in dirs]
        reports += reps
        if any(r["reads"] is None for r in reps):
            continue
        summary = read_json(os.path.join(folder, "e0", "a%d.json" % k))
        parts.append(card_part(k, reps, seed_base, E0.SPACING * (n + 1), summary))
    stated = n == E0.FULL_N and seed_base == E0.FULL_SEED
    round1 = dict((k, read_json(os.path.join(ROUND1, "part%d.json" % k))) for k in amplitudes) if stated else None
    code = judge(parts, reports, round1, E0.not_as_stated if stated and len(parts) == len(E0.AMPLITUDES) else None, out)
    return code, parts, reports


def compare_flip(folder, run_dir, out=print):
    """Round 3's control on the card: the flipped blob's run must DIFFER from e0's expectation of its piece and be
    IDENTICAL to the flipped blob's own. Returns 0 when it is both."""
    fd = os.path.join(folder, "flip", "a%dp%d" % FLIP)
    ed = os.path.join(folder, "e0", "a%dp%d" % FLIP)
    flip = compare_piece(folder, fd, run_dir)["identity"]
    e0 = compare_piece(folder, ed, run_dir)["identity"]
    out("the flip control, a%dp%d: against the flipped blob's own model run %s; against e0's %s%s"
        % (FLIP + ("IDENTICAL" if flip["identical"] else "DIFFERENT", "IDENTICAL" if e0["identical"] else "DIFFERENT",
                   "" if e0["identical"] else ", first %s, %d block(s) differ" % (json.dumps(e0["first"]),
                                                                                  e0["blocks_differ"]))))
    ok = flip["identical"] and not e0["identical"]
    out("== E0C FLIP CONTROL: %s" % ("SEEN, the flip reaches the records and the card ran the flipped blob" if ok
                                     else "NOT AS IT MUST BE"))
    return 0 if ok else 1


def timed_judge(folder, out_dir, out=print):
    tdir = os.path.join(folder, "timed")
    exp = read_json(os.path.join(tdir, "expected.json"))["sets"]
    got = read_json(os.path.join(out_dir, "timed.json"))
    ok = len(got["generations"]) == len(exp)
    out("the timed runs: %d generations, %d sets expected" % (len(got["generations"]), len(exp)))
    for g, (x, e) in enumerate(zip(got["generations"], exp)):
        same = x.get("records_sha256") == e["sha256"]
        counts = (x.get("found"), x.get("noise_crossings")) == (e["found"], e["noise_crossings"])
        ok = ok and same and counts and x.get("end") == "done"
        out("  gen %d %-10s %s; found %s, noise %s (the model's %d, %d) %s; sum %.3f ms"
            % (g, x.get("blob"), "IDENTICAL" if same else "DIFFERENT", x.get("found"), x.get("noise_crossings"),
               e["found"], e["noise_crossings"], "EQUAL" if counts else "DIFFER", x.get("sum_ns", 0) / 1e6))
    sums = [x["sum_ns"] for x in got["generations"] if "sum_ns" in x]
    if sums:
        mean = sum(sums) / len(sums)
        less = sum(x["sum_ns"] - x["parts_ns"]["open"] - x["parts_ns"]["close"] for x in got["generations"]) / len(sums)
        out("  mean generation %.3f ms: %.0f generations an hour (COMPUTED from the measured parts, the open included);"
            " %.0f an hour with open and close taken out (COMPUTED, not measured)"
            % (mean / 1e6, 3600e9 / mean, 3600e9 / less if less > 0 else float("nan")))
    out("== E0C TIMED VERDICT: %s" % ("PASS, every generation's records and counts the model's" if ok else "FAIL"))
    return 0 if ok else 1


def premise(new_path, old_path, out=print):
    a, b = read_json(new_path), read_json(old_path)
    keys = sorted(set(a) | set(b))
    differ = [k for k in keys if a.get(k) != b.get(k)]
    for k in keys:
        out("  %-26s %s" % (k, "equal" if k not in differ else "DIFFERS: %r against %r" % (a.get(k), b.get(k))))
    ok = differ == ["spec_sha256"] and a["spec_sha256"] == C.SPEC_SHA256
    out("== E0C PREMISE: %s" % ("EQUAL in every field but the definition's hash, which is today's" if ok else
                                "NOT EQUAL: %s" % ", ".join(differ)))
    return 0 if ok else 1


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("what", choices=("cases", "expect", "compare", "timed-judge", "premise"))
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--amplitude", type=int)
    ap.add_argument("--flip", action="store_true")
    ap.add_argument("--timed", action="store_true")
    ap.add_argument("--n", type=int, default=E0.FULL_N)
    ap.add_argument("--seed-base", type=int, default=E0.FULL_SEED)
    ap.add_argument("--pieces", type=int, default=PIECES)
    ap.add_argument("--timed-n", type=int, default=TIMED_N)
    ap.add_argument("--block", type=int, default=BLOCK)
    a = ap.parse_args(argv)
    if a.what == "cases":
        made = cases(a.paths[0], a.n, a.seed_base, a.pieces, a.timed_n)
        print("cases: %d pieces, the flip, %d timed sets, under %s" % (len(made), TIMED_SETS, a.paths[0]))
        return 0
    if a.what == "expect":
        if a.flip:
            d = os.path.join(a.paths[0], "flip", "a%dp%d" % FLIP)
            e = expect_piece(d, blob_of(a.paths[0], read_json(os.path.join(d, "piece.json"))), a.block)
            print("expect flip: %d records, %s" % (e["records"], e["sha256"][:16]))
        elif a.timed:
            for s in expect_timed(a.paths[0]):
                print("expect timed %s: %s, found %d, noise %d" % (s["blob"], s["sha256"][:16], s["found"],
                                                                  s["noise_crossings"]))
        else:
            expect_amplitude(a.paths[0], a.amplitude, a.block)
        return 0
    if a.what == "compare":
        code, parts, reports = compare(a.paths[0], a.paths[1], a.n, a.seed_base, a.pieces)
        write_json(os.path.join(a.paths[1], "card-e0.json"), {"parts": parts, "pieces": reports,
                                                               "spec_sha256": C.SPEC_SHA256})
        flip_run = os.path.join(a.paths[1], "flip-a%dp%d" % FLIP)
        if os.path.isdir(flip_run):
            code = max(code, compare_flip(a.paths[0], flip_run))
        else:
            print("the flip control: no run folder %s" % flip_run)
        return code
    if a.what == "timed-judge":
        return timed_judge(a.paths[0], a.paths[1])
    return premise(a.paths[0], a.paths[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

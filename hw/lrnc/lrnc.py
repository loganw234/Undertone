"""Learning in the fabric on the card, the host's side: the cases, the model's expectations, and the judge.

    python hw/lrnc/lrnc.py cases <folder> [--m n]          the cases (M = 2^20 by default; the short form 2,048)
    python hw/lrnc/lrnc.py expect <folder> --case <name>    one case's expectation: flow, rich or moved, a process each
    python hw/lrnc/lrnc.py compare <folder> <runs>          the judge, from the card's files; exit 0 only on PASS
    python hw/lrnc/lrnc.py short <folder>                   the whole day at M = 2,048, the card a stand-in

WHAT IS JUDGED, and on what authority: BIT IDENTITY, the model's. Every record the card writes, every outcome of
every host operation, and the learner's counters, status and refusal at the end, each equal to the model's run
of the same stream and script (`model.learner`, run as `model.run.learning` runs it: hw/lrnc/windows.py). It is
NOT evidence about sensitivity.

THE CASES (docs/host/lrn-c.md, section 4). Profile s16x1, 64 taps, sigma 1477/1, e0 at amplitude 1/1, E1's layout
of a trial every 128 frames with its truth record at frame 64 of the 128; F and count_bits the definition's. With
M frames (2^20 on the card) and G = M / 256, the guard:
  flow    4M frames from the blank set; update(M) after 0; commit(2M) after M + F + G
  moved   flow with update(M + 128): the lead's control on the card
  rich    7M frames from the matched filter, one record at 0, none from 64 to 2M, E1's layout from 2M and one record
          more at 2.5M; thirteen operations: two updates each committed, one unmade, and UPDATE_UNFINISHED,
          SWAP_PENDING and SWAP_INDEX provoked
and the card runs them in the order flow, rich, moved, flow again (`order.txt`).

THE EXPECTATION, made by `expect` on the desktop: the model's canonical run (each operation at its `after`), its
records kept, their SHA-256 whole and by blocks of 65,536; each operation's window and margin; the model's runs
with every operation at its lo and at its hi, each required to be the canonical run (EDGES_DIFFER otherwise); the
counts worked by hand against the model's (COUNTS_BY_HAND otherwise); what the registers read at the end.

THE JUDGE, `compare`: for each run, its records against the model's (IDENTICAL, or the first differing record
named with its field and both values); each operation's outcome, and its bracket inside its window; every register
at the end; the run's PASS line. The control, moved, must be IDENTICAL to its own model run and differ from flow's
first at the record the two model runs predict, in the score. flow again is held to flow's own expectation. Then
`== LRN-C CARD VERDICT: PASS`, exit 0, only when all of it holds; else FAIL naming the first line that fails, exit 1.

Desktop only: it imports the model and `learn.handover` for the blank set. Nothing the box runs imports it.
"""
import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from spec import constants as C                       # noqa: E402
from model import source, weights                     # noqa: E402
from learn import handover                            # noqa: E402

from hw.e0c import pieces                             # noqa: E402
from hw.lrnc import windows as W                      # noqa: E402
from hw.lrnc.errors import LrncRefusal                # noqa: E402

PROFILE, TAPS, SIGMA, AMPLITUDE = "s16x1", 64, (1477, 1), (1, 1)
SPACING, FIRST = 128, 64
F, COUNT_BITS = C.LEARN_UPDATE_FRAMES, C.LEARN_COUNT_BITS
M_CARD, M_SHORT = 1 << 20, 2048
SEEDS = {"flow": 2026112601, "rich": 2026112602}
BLOCK = 1 << 16
CASES = ("flow", "rich", "moved")
RUNS = (("flow", "flow"), ("rich", "rich"), ("moved", "moved"), ("flow-again", "flow"))
RECORD_BYTES = pieces.RECORD_BYTES


def guard(m):
    """G = M / 256: the guard after a finish or a pending's end (the lead's ruling, 2026-11-26 03:57)."""
    return m // 256


def blank_blob():
    return handover.blank_blob(PROFILE, TAPS)


def matched_blob():
    return weights.matched_filter(PROFILE, C.PULSES["e0"], (1,))


def _record(j):
    return {"index": j, "pulse_id": C.PULSE_IDS["e0"], "amplitude_num": AMPLITUDE[0], "amplitude_den": AMPLITUDE[1]}


def case(name, m):
    """One case at M = m: {"name", "frames", "seed", "schedule", "script", "blob", ...}. M is a multiple of 256."""
    if type(m) is not int or m < 1024 or m % 256:
        raise ValueError("M is a multiple of 256 of at least 1,024, not %r" % (m,))
    g = guard(m)
    common = {"name": name, "profile": PROFILE, "taps": TAPS, "sigma": list(SIGMA), "epoch": 0, "M": m, "G": g,
              "count_bits": COUNT_BITS, "update_frames": F}
    if name in ("flow", "moved"):
        frames = 4 * m
        u = m if name == "flow" else m + SPACING
        script = [{"op": "update", "arg": u, "after": 0},
                  {"op": "commit", "arg": 2 * m, "after": u + F + g}]
        schedule = [_record(FIRST + SPACING * t) for t in range(frames // SPACING)]
        return dict(common, frames=frames, seed=SEEDS["flow"], blob="blank.blob", schedule=schedule, script=script,
                    intended=[None, None])
    if name == "rich":
        frames = 7 * m
        trials = [2 * m + FIRST + SPACING * t for t in range(5 * m // SPACING)]
        x = 2 * m + m // 2
        schedule = [_record(j) for j in sorted([0, x] + trials)]
        a, b, c, d = m + F + g, 3 * m + F + g, 4 * m + 1 + g, 5 * m + F + g
        script = [
            {"op": "update", "arg": m, "after": 0},                   # taken, made unmade: QUANTISE_INPUT at m + F
            {"op": "clear", "after": a},                              # reads QUANTISE_INPUT
            {"op": "update", "arg": 3 * m, "after": a},               # taken
            {"op": "commit", "arg": 4 * m, "after": a},               # UPDATE_UNFINISHED, lrn_early
            {"op": "write_shadow", "blob": "blank.blob", "after": a},  # UPDATE_UNFINISHED
            {"op": "update", "arg": 3 * m + 4 * SPACING, "after": a},  # UPDATE_UNFINISHED
            {"op": "commit", "arg": 4 * m, "after": b},               # taken
            {"op": "update", "arg": 6 * m, "after": b},               # SWAP_PENDING
            {"op": "write_shadow", "blob": "blank.blob", "after": b},  # SWAP_PENDING, the core's
            {"op": "commit", "arg": 1, "after": c},                   # SWAP_INDEX, the core's
            {"op": "update", "arg": 1, "after": c},                   # SWAP_INDEX, the learner's
            {"op": "update", "arg": 5 * m, "after": c},               # taken
            {"op": "commit", "arg": 6 * m, "after": d},               # taken
        ]
        intended = [None, "QUANTISE_INPUT", None, "UPDATE_UNFINISHED", "UPDATE_UNFINISHED", "UPDATE_UNFINISHED", None,
                    "SWAP_PENDING", "SWAP_PENDING", "SWAP_INDEX", "SWAP_INDEX", None, None]
        return dict(common, frames=frames, seed=SEEDS["rich"], blob="matched.blob", schedule=schedule, script=script,
                    intended=intended)
    raise ValueError("no case %r" % (name,))


def by_hand(name, m):
    """The counts worked by hand from the layout and the window rules (docs/host/lrn-c.md, section 4), not by the
    model: {"updates": [(u, n0, n1)], "end": the eight counts}."""
    k = m // SPACING
    end = dict.fromkeys(W.ML.COUNTS + W.ML.COUNTERS, 0)
    if name == "flow":
        end.update(lrn_count0=4 * k, lrn_count1=4 * k, lrn_made=1)
        return {"updates": [(m, k, k)], "end": end}
    if name == "moved":
        end.update(lrn_count0=4 * k, lrn_count1=4 * k, lrn_made=1)
        return {"updates": [(m + SPACING, k + 1, k + 1)], "end": end}
    if name == "rich":
        end.update(lrn_count0=5 * k - 1, lrn_count1=5 * k + 2, lrn_skip_start=1, lrn_skip_busy=2, lrn_made=2,
                   lrn_unmade=1, lrn_early=1)
        return {"updates": [(m, 0, 1), (3 * m, k - 1, k + 2), (5 * m, 3 * k - 1, 3 * k + 2)], "end": end}
    raise ValueError("no case %r" % (name,))


# --------------------------------------------------------------------- cases

def _json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, indent=1)
        f.write("\n")


def cases(folder, m=M_CARD):
    """Write the cases: table.json, order.txt, and for each case its case.json, schedule.json, script.json and the
    two blobs (the script's write_shadow names a blob beside it)."""
    os.makedirs(folder, exist_ok=True)
    blobs = {"blank.blob": blank_blob(), "matched.blob": matched_blob()}
    table = None
    for name in CASES:
        c = case(name, m)
        d = os.path.join(folder, name)
        os.makedirs(d, exist_ok=True)
        info = dict((k, v) for k, v in c.items() if k not in ("schedule", "script"))
        info["spec_sha256"] = C.SPEC_SHA256
        _json(os.path.join(d, "case.json"), info)
        _json(os.path.join(d, "schedule.json"), c["schedule"])
        _json(os.path.join(d, "script.json"), c["script"])
        for b, data in blobs.items():
            with open(os.path.join(d, b), "wb") as f:
                f.write(data)
        if table is None:
            table = list(source.Noise(PROFILE, c["seed"], SIGMA[0], SIGMA[1], c["frames"]).table)
    _json(os.path.join(folder, "table.json"), table)
    with open(os.path.join(folder, "order.txt"), "w", encoding="utf-8", newline="\n") as f:
        for run_name, case_name in RUNS:
            f.write("%s %s\n" % (run_name, case_name))
    return folder


def load_case(folder, name):
    d = os.path.join(folder, name)
    with open(os.path.join(d, "case.json"), encoding="utf-8") as f:
        info = json.load(f)
    with open(os.path.join(d, "schedule.json"), encoding="utf-8") as f:
        info["schedule"] = json.load(f)
    with open(os.path.join(d, "script.json"), encoding="utf-8") as f:
        info["script"] = json.load(f)
    info["blobs"] = {}
    for b in ("blank.blob", "matched.blob"):
        with open(os.path.join(d, b), "rb") as f:
            info["blobs"][b] = f.read()
    return info


# --------------------------------------------------------------------- expect

class _Sink:
    """A sink for run_script: the records' SHA-256 whole and by blocks, and the bytes to a file if one is given."""

    def __init__(self, path=None):
        self.whole, self.block, self.blocks, self.n = hashlib.sha256(), hashlib.sha256(), [], 0
        self.f = open(path, "wb") if path else None

    def __call__(self, data):
        self.whole.update(data)
        self.block.update(data)
        self.n += 1
        if self.f is not None:
            self.f.write(data)
        if self.n % BLOCK == 0:
            self.blocks.append(self.block.hexdigest())
            self.block = hashlib.sha256()

    def close(self):
        if self.n % BLOCK:
            self.blocks.append(self.block.hexdigest())
        if self.f is not None:
            self.f.close()
        return {"sha256": self.whole.hexdigest(), "records": self.n, "block": BLOCK, "blocks": self.blocks}


def run_case_model(info, placed, sink=None, learner_class=W.ML.Learner):
    """The model's run of a loaded case with its operations at `placed`."""
    return W.run_script(info["profile"], info["seed"], tuple(info["sigma"]), info["frames"], info["schedule"],
                        info["blobs"][info["blob"]], info["script"], placed, info["update_frames"],
                        info["count_bits"], info["epoch"], blobs=info["blobs"], learner_class=learner_class, sink=sink)


def _summary(got, info):
    learner = got["learner"]
    return {"outcomes": got["outcomes"],
            "end": W.end_registers(learner, got["latch"], info["update_frames"], info["count_bits"]),
            "updates": [{"u": u["u"], "counts": list(u["counts"]), "outcome": u["outcome"],
                         "blob_sha256": None if u["blob"] is None else hashlib.sha256(u["blob"]).hexdigest()}
                        for u in learner.updates]}


def expect(folder, name):
    """The expectation of one case, under <folder>/expect/<name>/: records.bin (the model's) and expected.json."""
    info = load_case(folder, name)
    out = os.path.join(folder, "expect", name)
    os.makedirs(out, exist_ok=True)
    canonical = [op["after"] for op in info["script"]]
    sink = _Sink(os.path.join(out, "records.bin"))
    got = run_case_model(info, canonical, sink)
    hashes = sink.close()
    summary = _summary(got, info)
    latched = [k for k, (op, o) in enumerate(zip(info["script"], got["outcomes"]))
               if op["op"] != "clear" and o == "QUANTISE_INPUT"]
    if latched:
        raise LrncRefusal("SCRIPT_LATCH", "%s: operation %d lands on an unmade update's latched QUANTISE_INPUT with no "
                          "clear between: the library would raise it, latched before the call" % (name, latched[0]))
    if got["outcomes"] != info["intended"]:
        raise LrncRefusal("SCRIPT_WINDOW", "%s: the model's outcomes at the canonical placement are %r, not the case's "
                          "intended %r" % (name, got["outcomes"], info["intended"]))
    hand = by_hand(name, info["M"])
    model_counts = [(u["u"], u["counts"][0], u["counts"][1]) for u in summary["updates"]]
    if model_counts != [tuple(x) for x in hand["updates"]] or summary["end"]["counts"] != hand["end"]:
        raise LrncRefusal("COUNTS_BY_HAND", "%s: the model's counts at its updates %r and at the end %r; by hand %r "
                          "and %r" % (name, model_counts, summary["end"]["counts"], hand["updates"], hand["end"]))
    wins = W.rule(info["script"], got["outcomes"], got["learner"].updates, info["frames"], info["update_frames"])
    W.check_canonical(info["script"], wins, info["frames"])
    low, high = W.edge_placements(info["script"], wins, info["frames"])
    edges = {}
    for edge, placed in (("lo", low), ("hi", high)):
        s = _Sink()
        other = run_case_model(info, placed, s)
        h = s.close()
        theirs = _summary(other, info)
        same = h["sha256"] == hashes["sha256"] and theirs == summary
        edges[edge] = {"placed": placed, "sha256": h["sha256"], "same": same}
        if not same:
            raise LrncRefusal("EDGES_DIFFER", "%s: every operation at its %s (%r) gives another run: records %s, "
                              "outcomes %r" % (name, edge, placed, h["sha256"], theirs["outcomes"]))
    expected = dict(hashes, name=name, frames=info["frames"], seed=info["seed"], script=info["script"],
                    windows=[list(w) for w in wins], margins=W.margins(info["script"], wins), edges=edges,
                    hand={"updates": [list(x) for x in hand["updates"]], "end": hand["end"]},
                    spec_sha256=C.SPEC_SHA256, **summary)
    _json(os.path.join(out, "expected.json"), expected)
    return expected


# --------------------------------------------------------------------- compare

def _read(path, mode="rb"):
    with open(path, mode) as f:
        return f.read()


def _ops_lines(name, expected, report):
    """(lines, ok, the first failing line or None): each operation's outcome against the model's, and its bracket
    against its window."""
    ops = (report.get("learner") or {}).get("ops")
    if not isinstance(ops, list) or len(ops) != len(expected["script"]):
        line = "%s: the learner's operations in report.json are %r, not %d" % (
            name, None if ops is None else len(ops), len(expected["script"]))
        return [line], False, line
    lines, ok, bad = [], True, None
    for k, (op, want, (lo, hi), got) in enumerate(zip(expected["script"], expected["outcomes"], expected["windows"], ops)):
        have = got.get("read") if op["op"] == "clear" else got.get("outcome")
        if op["op"] == "clear" and got.get("outcome") is not None:
            have = "the clear itself refused %s" % got.get("outcome")
        before, after = got.get("next_index_before"), got.get("next_index_after")
        inside = (type(before) is int and type(after) is int and (lo is None or before >= lo)
                  and (hi is None or after <= hi))
        same = (have == want and got.get("op") == op["op"] and got.get("arg") == op.get("arg")
                and got.get("blob") == op.get("blob"))
        what = "%s(%s)" % (op["op"], op.get("arg", op.get("blob", "")))
        lines.append("%s op %d %s: %s%s, the model's %s; bracket [%s, %s] %s [%s, %s]%s" % (
            name, k, what, "read " if op["op"] == "clear" else "", have or "taken", want or "taken", before, after,
            "inside" if inside else "OUTSIDE its window", lo, hi,
            "" if hi is None or type(after) is not int else "; margin left %d" % (hi - after)))
        if not same:
            lines[-1] += ": NOT the model's"
        if ok and not (same and inside):
            bad = lines[-1]
        ok = ok and same and inside
    return lines, ok, (None if ok else bad)


def _registers_lines(name, expected, report):
    end = (report.get("learner") or {}).get("end")
    want = expected["end"]
    if not isinstance(end, dict):
        line = "%s: no learner registers at the end in report.json" % name
        return [line], False, line
    wrong = []
    for key in ("lrn_update_at", "lrn_refusal"):
        if end.get(key) != want[key]:
            wrong.append("%s %r where the model has %r" % (key, end.get(key), want[key]))
    for group in ("counts", "caps", "lrn_status"):
        for key, value in want[group].items():
            if (end.get(group) or {}).get(key) != value:
                wrong.append("%s %r where the model has %r" % (key, (end.get(group) or {}).get(key), value))
    declared = sum(1 << b for b in C.REGISTER_BITS["lrn_status"].values())
    word = end.get("lrn_status_word")
    if type(word) is not int or word & ~declared:
        wrong.append("lrn_status's word %r holds a bit the definition does not declare" % (word,))
    n = len(want["counts"]) + len(want["caps"]) + len(want["lrn_status"]) + 3
    if wrong:
        line = "%s registers at the end: NOT the model's: %s" % (name, "; ".join(wrong))
        return [line], False, line
    return ["%s registers at the end: %d of %d the model's" % (name, n, n)], True, None


def compare(folder, runs):
    """The judge. Prints its lines and the verdict; writes <runs>/card-lrnc.json; returns 0 on PASS, else 1."""
    with open(os.path.join(folder, "order.txt"), encoding="utf-8") as f:
        order = [line.split() for line in f if line.strip()]
    found, lines, failed = {}, [], []
    model = {}
    for run_name, case_name in order:
        exp_dir = os.path.join(folder, "expect", case_name)
        with open(os.path.join(exp_dir, "expected.json"), encoding="utf-8") as f:
            expected = json.load(f)
        if case_name not in model:
            model[case_name] = _read(os.path.join(exp_dir, "records.bin"))
        mine = model[case_name]
        run_dir = os.path.join(runs, run_name)
        try:
            data = _read(os.path.join(run_dir, "records.bin"))
            with open(os.path.join(run_dir, "report.json"), encoding="utf-8") as f:
                report = json.load(f)
            log = _read(run_dir.rstrip("/\\") + ".log", "r") if os.path.exists(run_dir.rstrip("/\\") + ".log") else ""
        except (OSError, ValueError) as e:
            lines.append("== LRN-C RUN %s: NOT RUN or its files unreadable (%s)" % (run_name, e))
            failed.append(lines[-1])
            found[run_name] = {"files": str(e)}
            continue
        ident = pieces.compare_blocks(data, expected, remake=lambda first, count, mine=mine:
                                      mine[first * RECORD_BYTES:(first + count) * RECORD_BYTES])
        passed = any(line.startswith("PASS host.run_case") for line in log.splitlines())
        ended = isinstance(report.get("run"), dict) and report["run"].get("records") == expected["frames"] and passed
        op_lines, ops_ok, ops_bad = _ops_lines(run_name, expected, report)
        reg_lines, regs_ok, regs_bad = _registers_lines(run_name, expected, report)
        head = "== LRN-C RUN %s: %s" % (run_name, "IDENTICAL, %d records" % ident["records"] if ident["identical"]
                                        else "DIFFERENT: %r" % (ident["first"],))
        if not ended:
            head += "; the run did not end with every record and its PASS line (%s)" % (
                report.get("refused") or report.get("deadline") or report.get("failed") or "no PASS line")
        lines.append(head)
        lines += ["   " + x for x in op_lines + reg_lines]
        ok = ident["identical"] and ended and ops_ok and regs_ok
        if not ok:
            failed.append(head if not (ident["identical"] and ended) else (ops_bad or regs_bad))
        found[run_name] = {"identical": ident["identical"], "first": ident["first"], "ended": ended,
                           "operations": ops_ok, "registers": regs_ok, "sha256": hashlib.sha256(data).hexdigest()}
    # flow again is judged against flow's own expectation, so that both are IDENTICAL makes them the same bytes.
    # The lead's control on the card: moved.
    lines.append(_control_line(folder, runs, model))
    if not lines[-1].startswith("== LRN-C CONTROL moved: SEEN"):
        failed.append(lines[-1])
    verdict = "PASS" if not failed else "FAIL"
    lines.append("== LRN-C CARD VERDICT: %s%s" % (verdict, "" if not failed else ": %s" % failed[0]))
    for line in lines:
        print(line)
    _json(os.path.join(runs, "card-lrnc.json"), {"verdict": verdict, "runs": found, "failed": failed,
                                                 "spec_sha256": C.SPEC_SHA256})
    return 0 if verdict == "PASS" else 1


def first_difference(a, b):
    """The first record at which two records files differ, its field and both values; or None."""
    n = min(len(a), len(b)) // RECORD_BYTES
    for r in range(n):
        x, y = a[r * RECORD_BYTES:(r + 1) * RECORD_BYTES], b[r * RECORD_BYTES:(r + 1) * RECORD_BYTES]
        if x != y:
            p, q = pieces.RECORD.unpack(x), pieces.RECORD.unpack(y)
            field = next(f for f, u, v in zip(pieces.SCORE_FIELDS, p, q) if u != v)
            i = pieces.SCORE_FIELDS.index(field)
            return {"record": r, "field": field, "a": p[i], "b": q[i]}
    return None if len(a) == len(b) else {"record": n, "field": None, "a": None, "b": None}


def _control_line(folder, runs, model):
    """SEEN only if moved's card run is IDENTICAL to moved's model run and differs from flow's model run first at
    the record the two model runs predict, at or after the commit, in the score, with moved's model value."""
    try:
        with open(os.path.join(folder, "expect", "moved", "expected.json"), encoding="utf-8") as f:
            moved = json.load(f)
        flow_model = model.get("flow") or _read(os.path.join(folder, "expect", "flow", "records.bin"))
        moved_model = model.get("moved") or _read(os.path.join(folder, "expect", "moved", "records.bin"))
        card = _read(os.path.join(runs, "moved", "records.bin"))
    except (OSError, ValueError) as e:
        return "== LRN-C CONTROL moved: NOT SEEN: its files are not there (%s)" % e
    predicted = first_difference(moved_model, flow_model)
    commit = [op["arg"] for op in moved["script"] if op["op"] == "commit"][0]
    if predicted is None or predicted["field"] != "score" or predicted["record"] < commit:
        return ("== LRN-C CONTROL moved: NOT SEEN: the model's own moved and flow runs differ at %r, not first in the "
                "score at or after the commit at %d" % (predicted, commit))
    if card != moved_model:
        return "== LRN-C CONTROL moved: NOT SEEN: the card's moved run is not its own model run (%r)" % (
            first_difference(card, moved_model),)
    got = first_difference(card, flow_model)
    if got != predicted:
        return "== LRN-C CONTROL moved: NOT SEEN: it differs from flow's first at %r, the prediction %r" % (got, predicted)
    return ("== LRN-C CONTROL moved: SEEN: its own model run's, and different from flow's first at record %d, score, "
            "%d where flow's is %d, as predicted" % (predicted["record"], predicted["a"], predicted["b"]))


# --------------------------------------------------------------------- short

def short(folder, stride=37):
    """The whole day at M = 2,048 with the stand-in for the card: cases, expectations, the four runs through
    host.run_case, and the judge. Returns the judge's exit code."""
    from hw.lrnc import standin
    cases_dir = cases(os.path.join(folder, "cases"), M_SHORT)
    for name in CASES:
        expect(cases_dir, name)
    runs = os.path.join(folder, "runs")
    os.makedirs(runs, exist_ok=True)
    for run_name, case_name in RUNS:
        standin.run(cases_dir, case_name, os.path.join(runs, run_name), stride=stride)
    return compare(cases_dir, runs)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="what", required=True)
    p = sub.add_parser("cases")
    p.add_argument("folder")
    p.add_argument("--m", type=int, default=M_CARD)
    p = sub.add_parser("expect")
    p.add_argument("folder")
    p.add_argument("--case", required=True, choices=CASES)
    p = sub.add_parser("compare")
    p.add_argument("folder")
    p.add_argument("runs")
    p = sub.add_parser("short")
    p.add_argument("folder")
    a = ap.parse_args(argv)
    if a.what == "cases":
        cases(a.folder, a.m)
        print("cases written to %s at M = %d" % (a.folder, a.m))
        return 0
    if a.what == "expect":
        e = expect(a.folder, a.case)
        print("expect %s: %d records, SHA-256 %s; outcomes %r; edges lo and hi the same; margins %r"
              % (a.case, e["records"], e["sha256"], e["outcomes"], e["margins"]))
        return 0
    if a.what == "compare":
        return compare(a.folder, a.runs)
    return short(a.folder)


if __name__ == "__main__":
    sys.exit(main())

"""The ten timed runs: ten generations one after another on the card, each part timed. For the card day, the lead's.

    python3 hw/e0c/timed.py --xclbin <image> --shim <libundertone_xrt.so> --cases <cases>/timed --out <folder>
                            [--launched-ns <the shell's date +%s%N just before python3>] [--polls n] [--device 0]
                            [--cu undertone_krnl]

Run with the host tree as the current folder. Standard library, `host/` and `spec/` only (and `model.refusal`,
which the library raises): nothing here imports from tests/ or needs numpy.

A GENERATION, in the lead's reading of the plan: one set of weights put on the card, tested on 10,000 injections,
its records read back and scored by the host, and the next set made ready. Nothing is learned: the ten sets were
made beforehand on the desktop (`hw/e0c/e0c.py cases`, timed/gen<g>.blob), each with its own D8 threshold. Every
generation runs the same stream (timed.json: its seed and frames) and the same truth records (schedule.json).

EACH GENERATION OPENS THE DEVICE AFRESH: the host library allocates a buffer each run and frees its buffers only
when the backend closes (host/library.py `start`; host/backend_xrt.py `close`), and the design adds no way to free
one. So the open, which loads the image through XRT, is a part of every generation, and is timed.

THE PARTS, each `time.perf_counter_ns()` around one call, in ns, in timed.json:
  ready     the set's blob read from disk           open      Backend(...): the shim's device open, the image's load
  identity  the library's `open`                    reset     `reset`
  load      `load` of the set                       start     `start`: the buffer allocated and filled, the table,
  finish    `finish`: polling until done                      the seed, the first truth records, the run's arguments
  records   `records`: the buffer fetched and parsed score     the two reads of every trial against the threshold
  close     the backend's close, the buffer freed
  sum = ready + open + identity + reset + load + start + finish + records + score + close
From the run's trace (the driver's Entry times, the backend's clock: perf_counter_ns under XRT), in "trace_ns":
allocate and fill (inside start), run (from the krn_start write's call to the return of the first krn_status read
that says done), fetch (inside records; the parse is records less fetch), and the count of status reads.
OUTSIDE THE SUM, timed apart: "kept", the records' canonical bytes (host.run_case's records.bin layout) written to
<out>/gen<g>/records.bin and their SHA-256 taken, for the desktop's comparison (`e0c.py timed-judge`); and once,
the process's start (the shell's --launched-ns against time.time_ns() at this file's first line) and its imports.

THE COLLECTOR. Python's cyclic garbage collector is off for the whole process, and each generation's records are
dropped before the next, as hw/e0c/run_piece.py says why: a full collection that outlasts the injector store's
slack would lose a run. The lead's ruling, 2026-11-25 12:27.

AN END THAT IS NOT DONE (a refusal by name, a deadline, a failure of XRT or of anything else) is recorded with its
name, the kernel is reset and its answer read (host.run_case's `_reset_and_read`), the backend is closed, and NO
FURTHER GENERATION RUNS: nothing the host writes stops a running kernel (docs/host/host.md, limit 18). The last
line is "PASS e0c.timed: ..." only when all ten ended done; else "STOPPED e0c.timed: ..." and exit 1.
"""
import time

T_START_NS = time.time_ns()
T_START_PERF = time.perf_counter_ns()

import argparse  # noqa: E402
import gc  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from spec import constants as C  # noqa: E402
from model.refusal import Refusal  # noqa: E402
from host import library as L  # noqa: E402
from host.drive import Host  # noqa: E402
from host.run_case import _reset_and_read  # noqa: E402

T_IMPORTED_PERF = time.perf_counter_ns()

SUM = ("ready", "open", "identity", "reset", "load", "start", "finish", "records", "score", "close")
DONE = 1 << C.REGISTER_BITS["krn_status"]["done"]
PAD = bytes(L.SLOT - L.RECORD_BYTES)


def canonical(recs):
    """The records' canonical bytes, as host.run_case writes records.bin."""
    return b"".join(L.SLOT_FORMAT.pack(*[r[name] for name, _b, _s in L.SCORE], PAD)[:L.RECORD_BYTES] for r in recs)


def score(recs, case, threshold):
    """(found, signal-free crossings): each trial's score at truth + offsets["at"] and at truth + offsets["noise"],
    each record held to the index it is read at (RECORD_ORDER otherwise), a crossing strictly above."""
    found = quiet = 0
    for t in range(case["trials"]):
        truth = case["first_index"] + case["spacing"] * t
        for name in ("at", "noise"):
            i = truth + case["offsets"][name]
            r = recs[i]
            if r["index"] != i:
                raise Refusal("RECORD_ORDER", "the record at place %d carries index %d" % (i, r["index"]))
            if r["score"] > threshold:
                if name == "at":
                    found += 1
                else:
                    quiet += 1
    return found, quiet


def trace_parts(trace):
    """allocate, fill, run, fetch and the status reads, from one generation's trace."""
    out = {}
    start_at, status_at = L.offset("krn_start"), L.offset("krn_status")
    began = None
    polls = 0
    for e in trace:
        kind = type(e.op).__name__
        if kind == "Allocate":
            out["allocate"] = e.after - e.before
        elif kind == "Fill":
            out["fill"] = e.after - e.before
        elif kind == "Fetch":
            out["fetch"] = e.after - e.before
        elif kind == "Write" and e.op.offset == start_at:
            began = e.before
        elif kind == "Read" and e.op.offset == status_at and began is not None and "run" not in out:
            polls += 1
            if isinstance(e.result, int) and e.result & DONE:
                out["run"] = e.after - began
    out["status_reads"] = polls
    return out


def generation(g, tdir, case, s, factory, polls, out_dir, schedule, table):
    t = time.perf_counter_ns
    parts, result, recs = {}, {"generation": g, "blob": s["blob"], "end": None}, None
    a = t()
    with open(os.path.join(tdir, s["blob"]), "rb") as f:
        blob = f.read()
    parts["ready"] = t() - a
    a = t()
    backend = factory()
    parts["open"] = t() - a
    trace = []
    lib = Host(backend, trace=trace)
    try:
        try:
            for name, call in (("identity", lambda: lib.open()), ("reset", lambda: lib.reset()),
                               ("load", lambda: lib.load(blob)),
                               ("start", lambda: lib.start(case["seed"], table, case["frames"], schedule)),
                               ("finish", lambda: result.__setitem__("run", lib.finish(polls))),
                               ("records", None), ("score", None)):
                a = t()
                if name == "records":
                    recs = lib.records()
                elif name == "score":
                    result["found"], result["noise_crossings"] = score(recs, case, s["threshold"])
                else:
                    call()
                parts[name] = t() - a
            result["end"] = "done"
        except Refusal as e:
            result["end"], result["refused"] = "refused", {"name": e.name, "detail": e.detail}
        except TimeoutError as e:
            result["end"], result["deadline"] = "deadline", str(e)
        except Exception as e:          # XRT's own error (OSError) or any other: a failure
            result["end"], result["failed"] = "failed", "%s: %s" % (type(e).__name__, e)
        if result["end"] != "done":
            result["reset"], failure = _reset_and_read(lib)
            if failure is not None:
                result["reset_failed"] = failure
    finally:
        a = t()
        try:
            backend.close()
        except Exception as e:
            result["end"], result["close_failed"] = "failed", "%s: %s" % (type(e).__name__, e)
        parts["close"] = t() - a
    if recs is not None:
        a = t()
        data = canonical(recs)
        d = os.path.join(out_dir, "gen%d" % g)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "records.bin"), "wb") as f:
            f.write(data)
        result["records"] = len(recs)
        result["records_sha256"] = hashlib.sha256(data).hexdigest()
        result["kept_ns"] = t() - a
    del recs
    result["parts_ns"] = parts
    if result["end"] == "done":
        result["sum_ns"] = sum(parts[k] for k in SUM)
    result["trace_ns"] = trace_parts(trace)
    return result


def main(argv=None, factory=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xclbin")
    ap.add_argument("--shim")
    ap.add_argument("--cases", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--launched-ns", type=int)
    ap.add_argument("--polls", type=int, default=2000000)
    ap.add_argument("--device", type=int, default=0)
    ap.add_argument("--cu", default="undertone_krnl")
    a = ap.parse_args(argv)
    if factory is None:
        if not a.xclbin or not a.shim:
            ap.error("--xclbin and --shim are needed on the card")
        from host.backend_xrt import Backend

        def factory():
            return Backend(a.xclbin, device=a.device, cu_name=a.cu, shim_path=a.shim)
    case = json.load(open(os.path.join(a.cases, "timed.json"), encoding="utf-8"))
    schedule = json.load(open(os.path.join(a.cases, "schedule.json"), encoding="utf-8"))
    table = json.load(open(os.path.join(a.cases, "table.json"), encoding="utf-8"))
    os.makedirs(a.out, exist_ok=True)
    was = gc.isenabled()
    gc.disable()
    try:
        gens = []
        for g, s in enumerate(case["sets"]):
            gens.append(generation(g, a.cases, case, s, factory, a.polls, a.out, schedule, table))
            r = gens[-1]
            r["collector"] = "enabled" if gc.isenabled() else "disabled"     # read, not written: as it was
            print("gen %d %s: %s%s" % (g, s["blob"], r["end"], "" if r["end"] != "done" else
                  ", found %d, noise %d, sum %.3f ms" % (r["found"], r["noise_crossings"], r["sum_ns"] / 1e6)),
                  flush=True)
            if r["end"] != "done":
                break
    finally:
        if was:
            gc.enable()
    out = {"launched_ns": a.launched_ns, "started_ns": T_START_NS,
           "python_start_ns": None if a.launched_ns is None else T_START_NS - a.launched_ns,
           "imports_ns": T_IMPORTED_PERF - T_START_PERF,
           "collector": "disabled" if all(r["collector"] == "disabled" for r in gens) else "enabled",
           "frames": case["frames"], "trials": case["trials"], "seed": case["seed"],
           "generations": gens, "total_ns": sum(r.get("sum_ns", 0) for r in gens), "spec_sha256": C.SPEC_SHA256}
    with open(os.path.join(a.out, "timed.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    done = len(gens) == len(case["sets"]) and all(r["end"] == "done" for r in gens)
    if done:
        print("PASS e0c.timed: %d generations, %.3f s summed, written to %s" % (len(gens), out["total_ns"] / 1e9, a.out))
        return 0
    print("STOPPED e0c.timed: generation %d ended %s; %d of %d ran" % (len(gens) - 1, gens[-1]["end"], len(gens),
                                                                       len(case["sets"])))
    return 1


if __name__ == "__main__":
    sys.exit(main())

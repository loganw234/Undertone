"""One run of the kernel through the host library on XRT, from files, to files. For BUILD and CARD.

    python -m host.run_case --xclbin <image> --shim <libundertone_xrt.so> --blob <blob> --table <table.json>
                            --seed <n> --frames <n> --schedule <schedule.json> --out <folder>
                            [--epoch n] [--ahead n] [--polls n] [--swap-blob <blob> --swap-at n --swap-after n]
                            [--memory-group n] [--cu undertone_krnl] [--device 0]

It needs the library and nothing of the model: the inputs are made beside the
model, wherever it runs, and the records are compared with the model's there.
  --blob, --swap-blob   a configuration blob's bytes (model.weights.pack's)
  --table               a JSON list of the noise table's ints (model.source.Noise(...).table)
  --schedule            a JSON list of truth records ({"index", "pulse_id", "amplitude_num", "amplitude_den"})

It writes, into --out:
  records.bin    each score record's canonical bytes (model.records.pack's), one after another, in order
  report.json    the identity read, the run's report, the swap's report if any, and the refusal if one ended it
  trace.json     every operation: call, its place in the call, kind, offset or size, result, ns before and after

and then prints ONE LINE beginning "PASS host.run_case", LAST, only when the
run finished and every file is written. A run with no such line is a lost run,
never a result: under hardware emulation a run can end with exit code 0 and
no output (the lead, 2026-11-24 10:17). A refused run writes its files, prints
"REFUSED host.run_case <name>", and exits 2; a backend's failure exits 1.
"""
import argparse
import json
import os
import sys

from model.refusal import Refusal

from host import library as L
from host.backend_xrt import Backend
from host.drive import Host


def _trace_rows(trace):
    rows = []
    for e in trace:
        kind = type(e.op).__name__
        if kind in ("Read", "Write"):
            what = e.op.offset
        elif kind == "WriteMany":
            what = len(e.op.pairs)
        elif kind in ("Allocate",):
            what = e.op.size
        elif kind in ("Fill", "Fetch"):
            what = [e.op.offset, len(e.op.data) if kind == "Fill" else e.op.size]
        else:
            what = None
        result = e.result if isinstance(e.result, int) else (None if e.result is None else type(e.result).__name__)
        rows.append([e.call, e.ordinal, kind, what, result, e.before, e.after])
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--xclbin", required=True)
    ap.add_argument("--shim", required=True)
    ap.add_argument("--blob", required=True)
    ap.add_argument("--table", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--frames", type=int, required=True)
    ap.add_argument("--schedule", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--epoch", type=int, default=0)
    ap.add_argument("--ahead", type=int, default=None)
    ap.add_argument("--polls", type=int, default=10 ** 7)
    ap.add_argument("--swap-blob")
    ap.add_argument("--swap-at", type=int)
    ap.add_argument("--swap-after", type=int, default=0, help="frames through the core before the shadow is written")
    ap.add_argument("--memory-group", type=int, default=-1)
    ap.add_argument("--cu", default="undertone_krnl")
    ap.add_argument("--device", type=int, default=0)
    a = ap.parse_args(argv)
    with open(a.blob, "rb") as f:
        blob = f.read()
    with open(a.table, encoding="utf-8") as f:
        table = json.load(f)
    with open(a.schedule, encoding="utf-8") as f:
        schedule = json.load(f)
    swap_blob = None
    if a.swap_blob:
        with open(a.swap_blob, "rb") as f:
            swap_blob = f.read()
    os.makedirs(a.out, exist_ok=True)
    trace, report, refused = [], {}, None
    with Backend(a.xclbin, device=a.device, cu_name=a.cu, memory_group=a.memory_group, shim_path=a.shim) as backend:
        lib = Host(backend, trace=trace)
        records = []
        try:
            report["identity"] = dict(lib.open(), spec_hash="%064x" % lib.identity["spec_hash"])
            report["memory_group"] = backend.memory_group
            lib.reset()
            lib.load(blob, epoch=a.epoch)
            lib.start(a.seed, table, a.frames, schedule, ahead=a.ahead)
            if swap_blob is not None:
                for _ in range(a.polls):
                    lib.step()
                    if lib.raw_read(L.offset("next_index")) >= a.swap_after:
                        break
                report["swap"] = lib.swap(swap_blob, a.swap_at)
            report["run"] = lib.finish(a.polls)
        except Refusal as e:
            refused = e
            report["refused"] = {"name": e.name, "detail": e.detail}
        if lib.library.run_state is not None and lib.library.run_state.records is not None:
            try:
                records = lib.records()
            except Refusal as e:
                refused = refused or e
                report["records_refused"] = {"name": e.name, "detail": e.detail}
    with open(os.path.join(a.out, "records.bin"), "wb") as f:
        for r in records:
            f.write(L.SLOT_FORMAT.pack(*[r[name] for name, _b, _s in L.SCORE], b"\0" * (L.SLOT - L.RECORD_BYTES))[:L.RECORD_BYTES])
    with open(os.path.join(a.out, "report.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(dict(report, records=len(records)), f, indent=1, default=str)
    with open(os.path.join(a.out, "trace.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(_trace_rows(trace), f)
    if refused is not None:
        print("REFUSED host.run_case %s: %s" % (refused.name, refused.detail), flush=True)
        return 2
    print("PASS host.run_case: %d records of %d frames written to %s" % (len(records), a.frames, a.out), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

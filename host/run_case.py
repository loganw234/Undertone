"""One run of the kernel through the host library on XRT, from files, to files. For BUILD and CARD.

    python -m host.run_case --xclbin <image> --shim <libundertone_xrt.so> --blob <blob> --table <table.json>
                            --seed <n> --frames <n> --schedule <schedule.json> --out <folder>
                            [--epoch n] [--ahead n] [--polls n]
                            [--swap-blob <blob> --swap-at n --swap-after n [--swap-unbatched]]
                            [--memory-group n] [--cu undertone_krnl] [--device 0]

It needs the library and nothing of the model: the inputs are made beside the
model, wherever it runs, and the records are compared with the model's there.
  --blob, --swap-blob   a configuration blob's bytes (model.weights.pack's)
  --table               a JSON list of the noise table's ints (model.source.Noise(...).table)
  --schedule            a JSON list of truth records ({"index", "pulse_id", "amplitude_num", "amplitude_den"})
  --swap-unbatched      the swap's words written one Write each, so that the trace times each one
                        (recorded in report.json as "swap_batched")
  --swap-after          the swap is written once the core has taken this many frames, or after --polls
                        rounds of waiting for that, whichever is first: the swap is made either way, and
                        report.json's "swap" gives the index the core had reached

Its arguments are checked before the backend opens: --polls below 1 is refused
there, by argparse, with its usage line and exit 2. A failure to open the
backend raises, writing nothing. Once the backend is open it writes, into
--out, however the run ends, and BEFORE the backend frees its buffers and
closes the device:
  records.bin    each score record's canonical bytes (model.records.pack's), one after another, in order
  report.json    the identity read, the run's report, the swap's report if any, and how the run ended
  trace.json     every operation: call, its place in the call, kind, offset or size, result, ns before and after
The files are not written when writing them fails, or when the process is
killed; nothing else stops them.

It then prints ONE LINE beginning "PASS host.run_case", LAST, only when the
run finished and every file is written. A run with no such line is a lost run,
never a result: under hardware emulation a run can end with exit code 0 and
no output (the lead, 2026-11-24 10:17). The other ends, each with its files
written and no PASS line:
  REFUSED host.run_case <name>   a refusal by name, during the run or while reading its records: exit 2
  DEADLINE host.run_case         the kernel did not say done within --polls rounds: exit 3
  FAILED host.run_case           the backend failed (XRT's own error), its close failed, or an error that
                                 is none of these was raised: exit 1
WHICH END WINS: a backend failure wins over a refusal met before it (exit 1,
the refusal kept in report.json); a failure of the close wins over every
other end, the files already written then.

AFTER ANY END BUT PASS it writes krn_reset, and then reads krn_refusal and
krn_status and records in report.json what the kernel answered ("reset"):
taken, or refused KERNEL_BUSY with the kernel still running, that latch then
cleared. NOTHING THE HOST WRITES STOPS A RUNNING KERNEL: the kernel refuses a
reset while its run goes (rtl/krnl/undertone_krnl.sv, its krn_reset row;
docs/rtl/krnl.md section 5), and only the image's reload or the card's own
reset stops it. A kernel still running when the backend frees its buffers
may write into a buffer being freed (docs/host/host.md, limit 18).
"""
import argparse
import json
import os
import sys

from model.refusal import Refusal

from host import library as L
from host.backend_xrt import Backend
from host.drive import Host

EXIT_PASS, EXIT_FAILED, EXIT_REFUSED, EXIT_DEADLINE = 0, 1, 2, 3


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
    ap.add_argument("--swap-unbatched", action="store_true", help="write the swap's words one Write each")
    ap.add_argument("--memory-group", type=int, default=-1)
    ap.add_argument("--cu", default="undertone_krnl")
    ap.add_argument("--device", type=int, default=0)
    a = ap.parse_args(argv)
    if a.polls < 1:
        ap.error("--polls is a count of at least 1, not %d" % a.polls)
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
    trace, report, records = [], {}, []
    end, said = EXIT_PASS, ""
    backend = Backend(a.xclbin, device=a.device, cu_name=a.cu, memory_group=a.memory_group, shim_path=a.shim)
    lib = Host(backend, trace=trace)
    try:
        try:
            report["identity"] = dict(lib.open(), spec_hash="%064x" % lib.identity["spec_hash"])
            report["memory_group"] = backend.memory_group
            lib.reset()
            lib.load(blob, epoch=a.epoch)
            lib.start(a.seed, table, a.frames, schedule, ahead=a.ahead)
            if swap_blob is not None:
                report["swap_batched"] = not a.swap_unbatched
                for _ in range(a.polls):
                    lib.step()
                    if lib.raw_read(L.offset("next_index")) >= a.swap_after:
                        break
                report["swap"] = lib.swap(swap_blob, a.swap_at, batch=not a.swap_unbatched)
            report["run"] = lib.finish(a.polls)
        except Refusal as e:
            end, said = EXIT_REFUSED, "REFUSED host.run_case %s: %s" % (e.name, e.detail)
            report["refused"] = {"name": e.name, "detail": e.detail}
        except TimeoutError as e:
            end, said = EXIT_DEADLINE, "DEADLINE host.run_case: %s" % e
            report["deadline"] = str(e)
        except OSError as e:
            end, said = EXIT_FAILED, "FAILED host.run_case: %s" % e
            report["failed"] = str(e)
        except Exception as e:          # none of a refusal, a deadline or XRT's error: a fault, ended as FAILED
            end, said = EXIT_FAILED, "FAILED host.run_case: %s: %s" % (type(e).__name__, e)
            report["failed"] = "%s: %s" % (type(e).__name__, e)
        if end in (EXIT_PASS, EXIT_REFUSED) and lib.library.run_state is not None \
                and lib.library.run_state.records is not None:
            try:
                records = lib.records()
            except Refusal as e:
                end = EXIT_REFUSED
                said = said or "REFUSED host.run_case %s: %s" % (e.name, e.detail)
                report["records_refused"] = {"name": e.name, "detail": e.detail}
            except OSError as e:
                end, said = EXIT_FAILED, "FAILED host.run_case: %s" % e
                report["failed"] = str(e)
        if end != EXIT_PASS:
            report["reset"] = _reset_and_read(lib)
        _write_files(a.out, records, report, trace)
    finally:
        try:
            backend.close()
        except OSError as e:
            end, said = EXIT_FAILED, "FAILED host.run_case: the backend's close: %s" % e
            report["close_failed"] = str(e)
            _write_files(a.out, records, report, trace)
    if end != EXIT_PASS:
        print(said, flush=True)
        return end
    print("PASS host.run_case: %d records of %d frames written to %s" % (len(records), a.frames, a.out), flush=True)
    return EXIT_PASS


def _reset_and_read(lib):
    """krn_reset written, then krn_refusal and krn_status read: what the kernel answered. A reset refused
    KERNEL_BUSY (the kernel still running: nothing the host writes stops it) is cleared and said so."""
    out = {}
    try:
        lib.raw_write(L.offset("krn_reset"), 1)
        code = lib.raw_read(L.offset("krn_refusal"))
        status = lib.raw_read(L.offset("krn_status"))
        out = {"krn_refusal": L.NAME_OF.get(code, code) if code else None, "krn_status": "0x%X" % status,
               "running": bool(status & L.RUNNING)}
        if code == L.C.REFUSAL_CODES["KERNEL_BUSY"]:
            lib.raw_write(L.offset("krn_refusal"), 0)
            out["answer"] = "refused KERNEL_BUSY: the kernel still runs, and the latch was cleared"
        elif code:
            out["answer"] = "a refusal is latched after the reset: %s" % L.NAME_OF.get(code, code)
        else:
            out["answer"] = "taken" if not status & L.RUNNING else "no refusal, and the kernel still says running"
    except OSError as e:
        out["answer"] = "raised: %s" % e
    return out


def _write_files(folder, records, report, trace):
    with open(os.path.join(folder, "records.bin"), "wb") as f:
        pad = b"\0" * (L.SLOT - L.RECORD_BYTES)
        for r in records:
            f.write(L.SLOT_FORMAT.pack(*[r[name] for name, _b, _s in L.SCORE], pad)[:L.RECORD_BYTES])
    with open(os.path.join(folder, "report.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(dict(report, records=len(records)), f, indent=1, default=str)
    with open(os.path.join(folder, "trace.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(_trace_rows(trace), f)


if __name__ == "__main__":
    sys.exit(main())

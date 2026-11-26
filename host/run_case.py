"""One run of the kernel through the host library on XRT, from files, to files. For BUILD and CARD.

    python -m host.run_case --xclbin <image> --shim <libundertone_xrt.so> --blob <blob> --table <table.json>
                            --seed <n> --frames <n> --schedule <schedule.json> --out <folder>
                            [--epoch n] [--ahead n] [--polls n]
                            [--swap-blob <blob> --swap-at n --swap-after n [--swap-unbatched]]
                            [--memory-group n] [--cu undertone_krnl] [--device 0]
                            [--learn <script.json> [--count-bits n] [--update-frames n]]

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
  --learn               the learner's script (round 5, parcel LRN-C; docs/host/lrn-c.md): a JSON list, in
                        order, of {"op": "update" | "commit" | "write_shadow" | "clear", "after": n, and "arg": an
                        int for update and commit, or "blob": a file beside the script for write_shadow}. Each
                        operation is made once a read of next_index is at least its "after", through the
                        library's lrn_ calls; a refusal of one is its outcome, recorded by name, and the run
                        goes on. Not with --swap-blob. --count-bits and --update-frames are what the case's
                        model run needs, the definition's maxima by default: a build whose learner is not that
                        is refused, LEARN_BOUND, before the reset.

BEFORE THE BACKEND OPENS, nothing is written: argparse refuses a malformed
argument, --polls below 1 among them, with its usage and "error:" on stderr
and exit 2; a missing or unreadable input file raises Python's own error
(FileNotFoundError, say), a traceback and exit 1; a failure to open the
backend raises the same way. EXIT 2 IS BOTH ARGPARSE'S AND REFUSED'S: the code
alone does not tell them apart; the line does (argparse's on stderr, REFUSED's
on stdout).

ONCE THE BACKEND IS OPEN it writes, into --out, however the run ends, and
BEFORE the backend frees its buffers and closes the device:
  records.bin    each score record's canonical bytes (model.records.pack's), one after another, in order
  report.json    the identity read, the run's report, the swap's report if any, and how the run ended
  trace.json     every operation: call, its place in the call, kind, offset or size, result, ns before and after
Every exception (every Exception of Python's) is caught there and ends the run
by its kind. The files are not written when writing them fails, or on Ctrl-C
(KeyboardInterrupt, which is not caught) or a killed process.

It then prints ONE LINE beginning "PASS host.run_case", LAST, only when the
run finished and every file is written. A run with no such line is a lost run,
never a result: under hardware emulation a run can end with exit code 0 and
no output (the lead, 2026-11-24 10:17). The other ends, each with its files
written and no PASS line, its line last on stdout:
  REFUSED host.run_case <name>   a refusal by name, during the run or while reading its records: exit 2
  DEADLINE host.run_case         the kernel did not say done within --polls rounds: exit 3
  FAILED host.run_case           the backend failed (XRT's own error), the reset or its reads raised, the
                                 close raised, or any other exception: exit 1
WHICH END WINS: a failure wins over every end met before it. A refusal or a
deadline followed by a failure (while the records are read, at the reset, or
at the close) ends FAILED, exit 1, the earlier end kept in report.json.

AFTER ANY END BUT PASS it writes krn_reset, then reads krn_refusal and
krn_status, and records in report.json ("reset") what the kernel answered:
  "taken"                                  no refusal latched, the kernel not running
  "refused KERNEL_BUSY: ..."               the kernel runs and refused the reset; that latch is then cleared
                                           by a write of 0
  "not taken: the kernel still runs ..."   another refusal was already latched while it runs, so the reset's
                                           own KERNEL_BUSY is not latched behind it; nothing is cleared
  "a refusal is latched, the kernel not running: ..."   and
  "no refusal, and the kernel still says running"       answers the RTL does not give; nothing is cleared
  "raised: ..."                            the write or a read raised: the run ends FAILED
NOTHING THE HOST WRITES STOPS A RUNNING KERNEL: the kernel refuses a reset
while its run goes (rtl/krnl/undertone_krnl.sv, its krn_reset row;
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
from host.drive import Host, run_by_calls

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
    ap.add_argument("--learn", help="the learner's script, a JSON list of operations (docs/host/lrn-c.md)")
    ap.add_argument("--count-bits", type=int, default=L.C.LEARN_COUNT_BITS)
    ap.add_argument("--update-frames", type=int, default=L.C.LEARN_UPDATE_FRAMES)
    a = ap.parse_args(argv)
    if a.polls < 1:
        ap.error("--polls is a count of at least 1, not %d" % a.polls)
    script = None
    if a.learn:
        if a.swap_blob:
            ap.error("--learn and --swap-blob are not given together: the learner's script makes its own commits")
        try:
            script = read_script(a.learn, a.frames)
        except ValueError as e:
            ap.error("--learn: %s" % e)
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
            if script is not None:
                report["learner"] = {"caps": _call(lib, "lrn_open", a.count_bits, a.update_frames), "ops": []}
            lib.reset()
            lib.load(blob, epoch=a.epoch)
            lib.start(a.seed, table, a.frames, schedule, ahead=a.ahead)
            if script is not None:
                _learn(lib, script, report["learner"]["ops"], a.polls)
            if swap_blob is not None:
                report["swap_batched"] = not a.swap_unbatched
                for _ in range(a.polls):
                    lib.step()
                    if lib.raw_read(L.offset("next_index")) >= a.swap_after:
                        break
                report["swap"] = lib.swap(swap_blob, a.swap_at, batch=not a.swap_unbatched)
            report["run"] = lib.finish(a.polls)
            if script is not None:
                report["learner"]["end"] = _call(lib, "lrn_registers")
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
            except Exception as e:      # XRT's error, or any other: a failure, which wins (exit 1)
                end, said = EXIT_FAILED, "FAILED host.run_case: %s: %s" % (type(e).__name__, e)
                report["failed"] = "%s: %s" % (type(e).__name__, e)
        if end != EXIT_PASS:
            report["reset"], failure = _reset_and_read(lib)
            if failure is not None:     # a failure at the reset wins over the end met before it
                end, said = EXIT_FAILED, "FAILED host.run_case: the reset: %s" % failure
                report["failed"] = "the reset: %s" % failure
        _write_files(a.out, records, report, trace)
    finally:
        try:
            backend.close()
        except Exception as e:          # a failure of the close wins over every other end
            end, said = EXIT_FAILED, "FAILED host.run_case: the backend's close: %s: %s" % (type(e).__name__, e)
            report["close_failed"] = "%s: %s" % (type(e).__name__, e)
            _write_files(a.out, records, report, trace)
    if end != EXIT_PASS:
        print(said, flush=True)
        return end
    if script is not None:
        made = report["learner"]["ops"]
        print("PASS host.run_case: %d records of %d frames written to %s; %d learner operation(s), %d refused by name"
              % (len(records), a.frames, a.out, len(made), sum(1 for o in made if o["outcome"] is not None)), flush=True)
        return EXIT_PASS
    print("PASS host.run_case: %d records of %d frames written to %s" % (len(records), a.frames, a.out), flush=True)
    return EXIT_PASS


# ---------------------------------------------------------------- the learner's script (round 5, parcel LRN-C)

LEARN_OPS = {"update": "lrn_update", "commit": "lrn_commit", "write_shadow": "lrn_write_shadow", "clear": "lrn_clear"}


def read_script(path, frames):
    """The learner's script from its file, its form checked: a list of operations in order, each a dict of
    exactly "op" and "after" and its argument ("arg" an int for update and commit; "blob" a file beside the
    script for write_shadow, whose bytes are read here; nothing for clear), "after" an int 0..frames that never
    falls. A form that is not so is a ValueError, which main() hands argparse; a file that cannot be read raises
    Python's own error. Returns a list of dicts, write_shadow's with its bytes under "bytes"."""
    with open(path, encoding="utf-8") as f:
        script = json.load(f)
    if not isinstance(script, list):
        raise ValueError("a script is a JSON list of operations")
    out, last = [], 0
    for k, op in enumerate(script):
        if not isinstance(op, dict) or op.get("op") not in LEARN_OPS:
            raise ValueError("operation %d is not a dict whose op is one of %s" % (k, ", ".join(sorted(LEARN_OPS))))
        want = {"update": {"op", "after", "arg"}, "commit": {"op", "after", "arg"},
                "write_shadow": {"op", "after", "blob"}, "clear": {"op", "after"}}[op["op"]]
        if set(op) != want:
            raise ValueError("operation %d (%s) has the keys %s, not %s" % (k, op["op"], sorted(op), sorted(want)))
        after = op["after"]
        if type(after) is not int or not last <= after <= frames:
            raise ValueError("operation %d's after is %r: an int from the one before it, %d, to the run's %d frames"
                             % (k, after, last, frames))
        last = after
        item = dict(op)
        if "arg" in op and type(op["arg"]) is not int:
            raise ValueError("operation %d's arg is %r, not an int" % (k, op["arg"]))
        if op["op"] == "write_shadow":
            if not isinstance(op["blob"], str) or os.path.basename(op["blob"]) != op["blob"]:
                raise ValueError("operation %d's blob is %r, not a file's name beside the script" % (k, op["blob"]))
            with open(os.path.join(os.path.dirname(os.path.abspath(path)), op["blob"]), "rb") as f:
                item["bytes"] = f.read()
        out.append(item)
    return out


def _call(lib, name, *args):
    """One of the library's learner calls, driven by calls through the host's backend and trace."""
    return run_by_calls(getattr(lib.library, name)(*args), lib.backend, lib.trace, name)


def _next_index(lib):
    """next_index, its two words read lower first. Below 2^32 its upper word is 0, and no carry can fall between."""
    low = lib.raw_read(L.offset("next_index", 0))
    return low | (lib.raw_read(L.offset("next_index", 1)) << L.WORD_BITS)


def _learn(lib, script, made, polls):
    """Each operation of the script in order: the run stepped (truth fed as it goes) until a read of next_index is at
    least its "after", at most `polls` rounds (TimeoutError past them: the operation is not made); next_index read;
    the call; next_index read again. A refusal of the call is its outcome, and the run goes on. Appends to `made`."""
    for k, op in enumerate(script):
        rounds = 0
        while _next_index(lib) < op["after"]:
            if rounds >= polls:
                raise TimeoutError("the learner's operation %d (%s) waited %d rounds for next index %d; the core is at "
                                   "%d" % (k, op["op"], polls, op["after"], _next_index(lib)))
            lib.step()
            rounds += 1
        entry = {"k": k, "op": op["op"], "after": op["after"], "polls": rounds}
        if "arg" in op:
            entry["arg"] = op["arg"]
        if "blob" in op:
            entry["blob"] = op["blob"]
        entry["next_index_before"] = _next_index(lib)
        first = len(lib.trace)
        argument = () if op["op"] == "clear" else (op["bytes"],) if op["op"] == "write_shadow" else (op["arg"],)
        entry["outcome"], entry["detail"] = None, ""
        try:
            got = _call(lib, LEARN_OPS[op["op"]], *argument)
            if op["op"] == "clear":
                entry["read"] = got
        except Refusal as e:
            entry["outcome"], entry["detail"] = e.name, e.detail
        calls = lib.trace[first:]
        entry["ns"] = [calls[0].before, calls[-1].after] if calls else None
        made.append(entry)
        entry["next_index_after"] = _next_index(lib)


RUNNING_BUSY = "refused KERNEL_BUSY: the kernel still runs; the latch was cleared (a write of 0)"


def _reset_and_read(lib):
    """krn_reset written, then krn_refusal and krn_status read: (what the kernel answered, None), or (the
    answer so far, the failure) when any of those raised. The answer's forms:
      "taken"                                     no refusal latched and the kernel not running
      RUNNING_BUSY                                the kernel runs and refused the reset, KERNEL_BUSY; that latch
                                                  is then cleared by a write of 0
      "not taken: the kernel still runs, and ..." the kernel runs with another refusal already latched (the
                                                  first is kept, so the reset's own KERNEL_BUSY is not latched);
                                                  nothing is cleared
      "a refusal is latched, the kernel not running: ..."   a reset the RTL would have taken clears every
                                                  refusal, so this is not the RTL's answer; nothing is cleared
      "no refusal, and the kernel still says running"       neither the RTL's answer; nothing is cleared
      "raised: ..."                               the write or a read raised: a failure, which the caller ends as
    Nothing the host writes stops a running kernel (docs/host/host.md, limit 18)."""
    out = {}
    try:
        lib.raw_write(L.offset("krn_reset"), 1)
        code = lib.raw_read(L.offset("krn_refusal"))
        status = lib.raw_read(L.offset("krn_status"))
        running = bool(status & L.RUNNING)
        named = L.NAME_OF.get(code, code) if code else None
        out = {"krn_refusal": named, "krn_status": "0x%X" % status, "running": running}
        if code == L.C.REFUSAL_CODES["KERNEL_BUSY"] and running:
            lib.raw_write(L.offset("krn_refusal"), 0)
            out["answer"] = RUNNING_BUSY
        elif code and running:
            out["answer"] = "not taken: the kernel still runs, and %s was already latched" % named
        elif code:
            out["answer"] = "a refusal is latched, the kernel not running: %s" % named
        else:
            out["answer"] = "taken" if not running else "no refusal, and the kernel still says running"
        return out, None
    except Exception as e:
        out["answer"] = "raised: %s: %s" % (type(e).__name__, e)
        return out, "%s: %s" % (type(e).__name__, e)


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

#!/usr/bin/env python3
"""Run the benches of rtl/tb/benches.toml. This runs INSIDE the simulation image.

    python rtl/tb/run_benches.py --root /work --out /out [--jobs N]

The tree is mounted read-only; everything this writes goes under --out or the
container's own /tmp. For each bench and each of its profiles there is one
RUN, named <bench>.<profile>, and one more for each mutant, named
<bench>.<profile>.mutant.<mutant>. A bench's own run runs every test of its
module. A mutant's run runs only the tests the mutant must fail: the others
say nothing about it, and on a large design they are most of the time. A run
leaves, under --out:

    <run>.xml             the results file cocotb writes
    <run>.evidence.jsonl  the lines rtl/tb/harness.py appends
    <run>.log             the simulator's output
    <run>.log.build       the build's output, which tools/check_rtl.py reads line by line

and this script leaves runs.json: for each run it tried, what it was and
whether anything went wrong before a simulator started (a mutant whose edit no
longer applies, a build that failed), or the run passed its limit.

EACH RUN IS A PROCESS OF ITS OWN, and up to --jobs of them run side by side
(round 3's P0-3: the second size of the gate had passed ten minutes with the
runs one after another). Each run has a LIMIT in seconds: the bench's `limit`
in the manifest, or DEFAULT_LIMIT. A run still going at its limit is stopped,
with everything it started, and runs.json says "RUN-TIMEOUT" for it. A run
stopped so leaves no results file; tools/check_rtl.py reports it by that name.

THIS SCRIPT DECIDES NOTHING. It does not read a results file and its exit code
means only that it reached its end. tools/check_rtl.py, outside the image,
works out for itself which runs there should be, and reads each one's files.
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import tomllib
import traceback

DEFAULT_LIMIT = 600     # seconds a run may take; round 2's longest single run took 72 (P0-3's record)
DEFAULT_JOBS = 6        # runs side by side: half this desktop's twelve cores
SCRATCH = "/tmp/runner"


def load_profiles(root):
    scope = {}
    with open(os.path.join(root, "spec", "constants.py"), encoding="utf-8") as f:
        exec(compile(f.read(), "spec/constants.py", "exec"), scope)
    return scope["PROFILES"]


def load_manifest(root):
    with open(os.path.join(root, "rtl", "tb", "benches.toml"), "rb") as f:
        return tomllib.loads(f.read().decode("utf-8"))


def mutated_sources(root, bench, mutant, where):
    """Copy the bench's sources under `where`, with the mutant's edits made. Returns the copies' paths."""
    out = []
    for rel in bench["sources"]:
        with open(os.path.join(root, rel), encoding="utf-8", newline="") as f:
            text = f.read()
        if rel == mutant["file"]:
            for old, new in mutant["edits"]:
                if text.count(old) != 1:
                    raise RuntimeError("MUTANT-DOES-NOT-APPLY: %r occurs %d time(s) in %s, not once"
                                       % (old, text.count(old), rel))
                text = text.replace(old, new)
        dst = os.path.join(where, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        out.append(dst)
    if mutant["file"] not in bench["sources"]:
        raise RuntimeError("MUTANT-DOES-NOT-APPLY: %s is not one of the bench's sources" % mutant["file"])
    return out


def plan(manifest):
    """Every run, in the order tools/check_rtl.py's runs_of gives: [(run, what, bench, profile, mutant or None)]."""
    out = []
    for bench in manifest.get("bench", []):
        for profile in bench["profiles"]:
            run = "%s.%s" % (bench["name"], profile)
            out.append((run, "bench", bench, profile, None))
            for mutant in bench.get("mutant", []):
                out.append(("%s.mutant.%s" % (run, mutant["name"]), "mutant", bench, profile, mutant))
    return out


def one_run(root, out, run, bench, profile, prof, sources, only=None):
    from cocotb_tools.runner import get_runner
    build_dir = os.path.join("/tmp", "build", run)
    test_dir = os.path.join("/tmp", "test", run)
    os.makedirs(test_dir, exist_ok=True)
    parameters = {"SAMPLE_BITS": prof["sample_bits"], "CHANNELS": prof["channels"]}
    log = os.path.join(out, run + ".log")
    runner = get_runner("icarus")
    runner.build(sources=sources, hdl_toplevel=bench["toplevel"], parameters=parameters, build_dir=build_dir,
                 always=True, timescale=("1ns", "1ps"), log_file=log + ".build")
    env = {
        "UNDERTONE_PROFILE": profile,
        "UNDERTONE_EVIDENCE": os.path.join(out, run + ".evidence.jsonl"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    runner.test(test_module=bench["module"], hdl_toplevel=bench["toplevel"], build_dir=build_dir, test_dir=test_dir,
                results_xml=os.path.join(out, run + ".xml"), extra_env=env, seed=20261123, log_file=log,
                testcase=only)


def child(root, out, name):
    """Run the one run called `name`, in this process. Writes its entry for runs.json under SCRATCH."""
    # cocotb's runner hands the simulator this process's own import path, and nothing else:
    # so the tree's root (spec, model) and the benches' folder go on it here.
    for folder in (os.path.join(root, "rtl", "tb"), root):
        if folder not in sys.path:
            sys.path.insert(0, folder)
    found = [p for p in plan(load_manifest(root)) if p[0] == name]
    run, what, bench, profile, mutant = found[0]
    prof = load_profiles(root)[profile]
    entry = {"run": run, "what": what, "error": None}
    try:
        if mutant is None:
            one_run(root, out, run, bench, profile, prof, [os.path.join(root, rel) for rel in bench["sources"]])
        else:
            where = os.path.join("/tmp", "src", run)
            shutil.rmtree(where, ignore_errors=True)
            one_run(root, out, run, bench, profile, prof, mutated_sources(root, bench, mutant, where),
                    only=list(mutant["must_fail"]))
    except BaseException as e:   # a simulator that exits, a build that fails: record it
        entry["error"] = "%s: %s" % (type(e).__name__, e)
        traceback.print_exc()
    with open(os.path.join(SCRATCH, run + ".json"), "w", encoding="utf-8") as f:
        json.dump(entry, f)
    return 0


def stop(proc):
    """Stop a run and everything it started: it leads a process group of its own."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--jobs", type=int, default=DEFAULT_JOBS)
    ap.add_argument("--one", help="run this one run in this process (the parent's way of starting each run)")
    a = ap.parse_args()
    root, out = os.path.abspath(a.root), os.path.abspath(a.out)
    os.makedirs(SCRATCH, exist_ok=True)
    if a.one:
        return child(root, out, a.one)
    runs = plan(load_manifest(root))
    todo = list(runs)
    waiting, going, tried = list(todo), {}, {}
    while waiting or going:
        while waiting and len(going) < max(1, a.jobs):
            run, what, bench, _profile, _mutant = waiting.pop(0)
            text = open(os.path.join(SCRATCH, run + ".txt"), "w", encoding="utf-8")
            proc = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--root", root, "--out", out,
                                     "--one", run], stdout=text, stderr=subprocess.STDOUT, start_new_session=True)
            going[run] = (proc, time.monotonic(), int(bench.get("limit", DEFAULT_LIMIT)), what, text)
        time.sleep(0.2)
        for run in list(going):
            proc, began, limit, what, text = going[run]
            took = time.monotonic() - began
            if proc.poll() is None and took < limit:
                continue
            entry = None
            if proc.poll() is None:
                stop(proc)
                entry = {"run": run, "what": what, "error": "RUN-TIMEOUT: the run was still going at its limit of "
                                                             "%d s and was stopped" % limit}
            text.close()
            del going[run]
            if entry is None:
                try:
                    with open(os.path.join(SCRATCH, run + ".json"), encoding="utf-8") as f:
                        entry = json.load(f)
                except (OSError, ValueError):
                    entry = {"run": run, "what": what, "error": "the run's process ended (exit %s) and left no "
                                                                "account of itself" % proc.returncode}
            tried[run] = entry
            print("ran %s in %.0f s%s" % (run, took, "" if entry["error"] is None else "  (ERROR %s)" % entry["error"]),
                  flush=True)
            if entry["error"] is not None:
                with open(os.path.join(SCRATCH, run + ".txt"), encoding="utf-8", errors="replace") as f:
                    sys.stdout.write(f.read())
    with open(os.path.join(out, "runs.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump([tried[r[0]] for r in todo], f, indent=1)
        f.write("\n")
    print("tried %d run(s), up to %d side by side" % (len(tried), max(1, a.jobs)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

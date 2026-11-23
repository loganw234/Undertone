#!/usr/bin/env python3
"""Run the benches of rtl/tb/benches.toml. This runs INSIDE the simulation image.

    python rtl/tb/run_benches.py --root /work --out /out

The tree is mounted read-only; everything this writes goes under --out or the
container's own /tmp. For each bench and each of its profiles there is one
RUN, named <bench>.<profile>, and one more for each mutant, named
<bench>.<profile>.mutant.<mutant>. A bench's own run runs every test of its
module. A mutant's run runs only the tests the mutant must fail: the others
say nothing about it, and on a large design they are most of the time. A run
leaves, under --out:

    <run>.xml             the results file cocotb writes
    <run>.evidence.jsonl  the lines rtl/tb/harness.py appends
    <run>.log             the build's and the simulator's output

and this script leaves runs.json: for each run it tried, what it was and
whether anything went wrong before a simulator started (a mutant whose edit no
longer applies, a build that failed).

THIS SCRIPT DECIDES NOTHING. It does not read a results file and its exit code
means only that it reached its end. tools/check_rtl.py, outside the image,
works out for itself which runs there should be, and reads each one's files.
"""
import argparse
import json
import os
import shutil
import sys
import tomllib
import traceback

from cocotb_tools.runner import get_runner


def load_profiles(root):
    scope = {}
    with open(os.path.join(root, "spec", "constants.py"), encoding="utf-8") as f:
        exec(compile(f.read(), "spec/constants.py", "exec"), scope)
    return scope["PROFILES"]


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


def one_run(root, out, run, bench, profile, prof, sources, only=None):
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


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    root, out = os.path.abspath(a.root), os.path.abspath(a.out)
    with open(os.path.join(root, "rtl", "tb", "benches.toml"), "rb") as f:
        manifest = tomllib.loads(f.read().decode("utf-8"))
    profiles = load_profiles(root)
    # cocotb's runner hands the simulator this process's own import path, and nothing else:
    # so the tree's root (spec, model) and the benches' folder go on it here.
    for folder in (os.path.join(root, "rtl", "tb"), root):
        if folder not in sys.path:
            sys.path.insert(0, folder)
    tried = []

    def attempt(run, what, fn):
        entry = {"run": run, "what": what, "error": None}
        try:
            fn()
        except BaseException as e:   # a simulator that exits, a build that fails: record it and go on
            entry["error"] = "%s: %s" % (type(e).__name__, e)
            traceback.print_exc()
        tried.append(entry)
        print("ran %s%s" % (run, "" if entry["error"] is None else "  (ERROR %s)" % entry["error"]), flush=True)

    for bench in manifest.get("bench", []):
        for profile in bench["profiles"]:
            prof = profiles[profile]
            run = "%s.%s" % (bench["name"], profile)
            sources = [os.path.join(root, rel) for rel in bench["sources"]]
            attempt(run, "bench", lambda: one_run(root, out, run, bench, profile, prof, sources))
            for mutant in bench.get("mutant", []):
                mrun = "%s.mutant.%s" % (run, mutant["name"])

                def mutated():
                    where = os.path.join("/tmp", "src", mrun)
                    shutil.rmtree(where, ignore_errors=True)
                    one_run(root, out, mrun, bench, profile, prof, mutated_sources(root, bench, mutant, where),
                            only=list(mutant["must_fail"]))
                attempt(mrun, "mutant", mutated)
    with open(os.path.join(out, "runs.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(tried, f, indent=1)
        f.write("\n")
    print("tried %d run(s)" % len(tried))
    return 0


if __name__ == "__main__":
    sys.exit(main())

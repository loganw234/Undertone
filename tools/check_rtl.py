#!/usr/bin/env python3
"""The checks of the gate's second size: `bash verify/run.sh --with rtl`.

They need Docker and the simulation image (tools/sim_image.py). The first
size, `bash verify/run.sh`, needs neither and runs none of these.

    check_rtl.py rtl-image   --root DIR --state DIR   the image this tree describes exists and holds what is pinned
    check_rtl.py rtl-spec    --root DIR --state DIR   a simulator and a compiler read the generated copies as the
                                                      numbers the Python copy holds
    check_rtl.py rtl-benches --root DIR --state DIR   every bench of rtl/tb/benches.toml passes, and every mutant
                                                      of the RTL fails as named
    check_rtl.py control KIND --root DIR --scratch DIR

A check prints "OK <kind>: <counts>" and exits 0, or prints each finding as
"FINDING <kind> <where>: <what>" and exits 1. What it cannot answer is REFUSED
by name with exit 2: no Docker, no image for this tree's docker files, a
manifest it cannot read. verify/run.sh asserts on the OK line.

A VERDICT IS NEVER AN EXIT CODE FROM INSIDE THE IMAGE. A simulator exits 0
with every test failed, and exits 0 having run none. So:

  rtl-benches works out for itself, from the manifest and from the bench
  module's source (the functions under @cocotb.test), which runs and which
  tests there must be. For each run it reads the results file cocotb wrote and
  the evidence lines the harness wrote. A run with no results file is a
  finding, NO-RESULTS. A test the source has and the results do not is a
  finding, NOT-RUN. An identity test must have passed AND left evidence of
  records compared with the two digests equal. A mutant passes the stage only
  when each test it names failed, for the kind of mismatch it names.

WHAT THESE CHECKS CANNOT SEE (stated limits):
  rtl-image    whether the image of that name was built by tools/sim_image.py:
               anyone can tag and label an image. The base image's own
               packages are whatever its archive served at the build; this
               stage prints the versions it finds and compares only the pins:
               Icarus Verilog's package version, and everything pip installed.
               Its control plants no image. It shows that a tree whose docker
               files changed, or lost one, is refused by name; the comparison
               of versions has no control.
  rtl-spec     reads the integers and the definition's hash. It takes the
               names from the two copies with a pattern for each. A line of
               the package that says `localparam`, `parameter` or `define, and
               a line of the header that says #define, is a finding when its
               pattern does not read it. A number declared any other way (an
               enum or a const in the header, a const or a typedef in the
               package, a second name after a comma on a localparam line) is
               NOT looked for: the copies are generated, and the `generated`
               stage holds their text. It does not know whether the RTL or a
               C program USES a constant correctly. What it holds the copies
               against is the Python copy, which the `generated` stage holds
               against the definition.
  rtl-benches  a bench's own content. It counts tests and records and reads
               verdicts; it does not read what a test asserts, so a bench that
               compares the wrong streams, or loads the same wrong weights
               into the RTL and the model, passes. The identity tests are the
               ones the manifest names: a comparison the manifest does not
               name is not required to leave evidence. A mutant shows the
               bench sees that one fault, and its run holds only the tests it
               must fail: what the mutant does to any other test is not
               looked at. A mutant's kind is one of the harness's three, WORD,
               COUNT or UNKNOWN-BITS, or empty. The evidence file is written by
               code running inside the simulator, beside the bench: a bench
               could write its own lines. Tests are found by the decorator
               `@cocotb.test`, written that way; one made some other way
               (a test factory) is not in the list this check requires, and
               shows as UNKNOWN-TEST when the results carry it.
  control      plants the faults listed in plants() and no others. The
               benches' control cuts its copy's manifest down to the
               foundation's own bench, p0-onetap, and plants there: it shows
               that the stage reads a wrong expectation and a run with no
               results as findings, on that bench. It runs no other bench,
               so it says nothing about any other bench's own tests.
               Of the judge's findings the benches' control plants four:
               a failed test, a run with no results, an identity test that
               left no evidence, and a mutant that failed for another reason.
               The rest (a mutant that survived, a test not run, an unknown
               test, a test named twice, evidence whose digests disagree, an
               evidence line that cannot be read) are held by the tests in
               tests/test_p0_rtl_gate.py, in the gate's first size, and by
               no control: a verifier disabled each of them in turn and this
               control still printed its line.
               The rtl-spec control changes EVERY number in each copy, the
               hash among them, and takes one name out of the header: every
               one must be reported, so a check that skipped any name, or any
               kind of name, fails it. Each integer has one added to it; the
               hash has one added to it in the package, and in the header a
               digit is put before its sixty-four: a check that
               saw only some other kind of change (one that compared whether
               a number is odd, say) would pass this control.
               The rtl-image control plants three trees: one whose Dockerfile
               has a comment line added, one whose package list has one
               added, and one that has lost its package list. An added
               comment line changes the file's bytes and nothing an image is
               built from. It plants no image.
               An unreadable evidence line is a finding in a bench's own run
               and in a mutant's.
"""
import argparse
import ast
import json
import os
import re
import shutil
import sys
import tomllib
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sim_image  # noqa: E402
from sim_image import ImageRefusal  # noqa: E402
from check_build import copy_tree, write  # noqa: E402
from check_tree import Refusal  # noqa: E402

MANIFEST = "rtl/tb/benches.toml"
NAME = re.compile(r"[a-z][a-z0-9-]*\Z")
KINDS_OF_MISMATCH = ("WORD", "COUNT", "UNKNOWN-BITS", "")


def constants(root):
    """The tree's own spec/constants.py, read from the tree being checked, not imported from this one."""
    scope = {}
    with open(os.path.join(root, "spec", "constants.py"), encoding="utf-8") as f:
        exec(compile(f.read(), "spec/constants.py", "exec"), scope)
    return scope


# ---------------------------------------------------------------- rtl-image

def check_image(root, state):
    name = sim_image.require(root)
    have, want = sim_image.versions(root), sim_image.pins(root)
    findings = []
    for pkg in sorted(set(have["pip"]) | set(want["pip"])):
        a, b = have["pip"].get(pkg), want["pip"].get(pkg)
        if a != b:
            findings.append(("docker/requirements-sim.txt %s" % pkg,
                             "the image holds %s, the list pins %s" % (a or "nothing", b or "nothing")))
    if have["iverilog"] != want["iverilog"]:
        findings.append(("docker/Dockerfile.sim iverilog", "the image holds %s, the file pins %s"
                         % (have["iverilog"], want["iverilog"])))
    ok = "1 image, %s, built from this tree's docker files; it holds Icarus Verilog %s and %d pip package(s) as " \
         "pinned (cocotb %s), and Python %s and gcc %s from its base" \
         % (name, have["iverilog"], len(have["pip"]), have["pip"].get("cocotb"), have["python"], have["gcc"])
    return findings, 1, ok


# ----------------------------------------------------------------- rtl-spec

def expected_numbers(C):
    """Every integer the two copies should carry, worked from the Python copy by this check's own rules.
    tools/gen_spec.py works the same list from the definition, by its rules; the two share no code."""
    e = {}
    for key, value in C.items():
        if key.isupper() and type(value) is int:
            e[key] = value
    e["PROFILE_COUNT"] = len(C["PROFILES"])
    for name, p in C["PROFILES"].items():
        e["PROFILE_%s_SAMPLE_BITS" % name.upper()] = p["sample_bits"]
        e["PROFILE_%s_CHANNELS" % name.upper()] = p["channels"]
    for name, code in C["RECTIFIERS"].items():
        e["RECTIFIER_%s" % name.upper()] = code
    for name, bit in C["FLAGS"].items():
        e["FLAG_%s_BIT" % name.upper()] = bit
    for rec, fields in C["RECORDS"].items():
        at = 0
        for field, bits, sign in fields:
            stem = "%s_%s" % (rec.upper(), field.upper())
            e[stem + "_LSB"], e[stem + "_BITS"], e[stem + "_SIGNED"] = at, bits, int(sign == "signed")
            at += bits
        e["%s_RECORD_BITS" % rec.upper()] = at
    for name, ident in C["PULSE_IDS"].items():
        e["PULSE_%s_ID" % name.upper()] = ident
        e["PULSE_%s_LENGTH" % name.upper()] = len(C["PULSES"][name])
        for j, sample in enumerate(C["PULSES"][name]):
            e["PULSE_%s_SAMPLE_%d" % (name.upper(), j)] = sample
    e["REFUSAL_NONE"] = 0
    for name, code in C["REFUSAL_CODES"].items():
        e["REFUSAL_%s" % name] = code
    for key, value in C["BUS"].items():
        e["BUS_%s" % key.upper()] = value
    for name, (offset, access, words) in C["REGISTERS"].items():
        stem = "REG_%s" % name.upper()
        e[stem + "_OFFSET"], e[stem + "_WORDS"] = offset, words
        e[stem + "_READABLE"], e[stem + "_WRITABLE"] = int("r" in access), int("w" in access)
    for name, (first, end) in C["BLOCKS"].items():
        e["BLOCK_%s_FIRST" % name.upper()], e["BLOCK_%s_END" % name.upper()] = first, end
    for register, bits in C["REGISTER_BITS"].items():
        for name, bit in bits.items():
            e["REG_%s_%s_BIT" % (register.upper(), name.upper())] = bit
    return e


SV_INT = re.compile(r"\s*localparam\s+int\s+([A-Z][A-Z0-9_]*)\s*=")
SV_HASH = re.compile(r"\s*localparam\s+logic\s+\[255:0\]\s+SPEC_SHA256\s*=")
C_DEFINE = re.compile(r"#define\s+UNDERTONE_([A-Z][A-Z0-9_]*)\s+\S")
C_GUARD = re.compile(r"#define\s+UNDERTONE_H\s*\Z")


def declared(root):
    """The names each copy declares, read by pattern. Returns (sv names, c names, findings)."""
    findings, sv, c = [], [], []
    with open(os.path.join(root, "spec", "undertone_pkg.sv"), encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            m = SV_INT.match(line)
            if m:
                sv.append(m.group(1))
            elif SV_HASH.match(line):
                sv.append("SPEC_SHA256")
            elif "localparam" in line or "parameter" in line.split("//")[0] or "`define" in line.split("//")[0]:
                findings.append(("spec/undertone_pkg.sv line %d" % n, "a declaration this check cannot read: %r" % line.strip()))
    with open(os.path.join(root, "spec", "undertone.h"), encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            m = C_DEFINE.match(line)
            if m:
                c.append(m.group(1))
            elif line.lstrip().startswith("#") and "define" in line and not C_GUARD.match(line.rstrip()):
                findings.append(("spec/undertone.h line %d" % n, "a definition this check cannot read: %r" % line.strip()))
    for label, names in (("spec/undertone_pkg.sv", sv), ("spec/undertone.h", c)):
        for name in sorted(set(n for n in names if names.count(n) > 1)):
            findings.append(("%s %s" % (label, name), "declared more than once"))
    return sv, c, findings


def read_back(root, state, sv, c):
    """Have Icarus Verilog print every name of the package and gcc every name of the header. Returns two dicts."""
    os.makedirs(state, exist_ok=True)
    lines = ["module dump;", "  initial begin"]
    for name in sv:
        fmt = "%h" if name == "SPEC_SHA256" else "%0d"
        lines.append('    $display("%s=%s", undertone_pkg::%s);' % (name, fmt, name))
    lines += ["    $finish;", "  end", "endmodule", ""]
    write(state, "dump.sv", "\n".join(lines))
    lines = ["#include <stdio.h>", '#include "undertone.h"', "int main(void) {"]
    for name in c:
        if name == "SPEC_SHA256":
            lines.append('    printf("%s=%%s\\n", UNDERTONE_%s);' % (name, name))
        else:
            lines.append('    printf("%s=%%lld\\n", (long long)(UNDERTONE_%s));' % (name, name))
    lines += ["    return 0;", "}", ""]
    write(state, "dump.c", "\n".join(lines))
    for old in ("sv.txt", "c.txt"):
        if os.path.exists(os.path.join(state, old)):
            os.remove(os.path.join(state, old))
    script = ("mkdir -p /tmp/s && "
              "iverilog -g2012 -o /tmp/s/dump.vvp /work/spec/undertone_pkg.sv /out/dump.sv > /out/sv.log 2>&1 && "
              "vvp -n /tmp/s/dump.vvp > /out/sv.txt 2>> /out/sv.log ; "
              "gcc -std=c11 -Wall -Wextra -Werror -I/work/spec -o /tmp/s/dump /out/dump.c > /out/c.log 2>&1 && "
              "/tmp/s/dump > /out/c.txt 2>> /out/c.log ; true")
    sim_image.run(root, [(root, "/work", "ro"), (state, "/out", "rw")], ["sh", "-c", script], timeout=300)
    out = []
    for name in ("sv.txt", "c.txt"):
        got, path = {}, os.path.join(state, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        got[k] = v
        out.append(got)
    return out


def check_spec(root, state):
    sim_image.require(root)
    C = constants(root)
    want = dict((k, str(v)) for k, v in expected_numbers(C).items())
    want["SPEC_SHA256"] = C["SPEC_SHA256"]
    sv, c, findings = declared(root)
    got_sv, got_c = read_back(root, state, sv, c)
    for label, names, got, tool in (("spec/undertone_pkg.sv", sv, got_sv, "Icarus Verilog"),
                                    ("spec/undertone.h", c, got_c, "gcc")):
        if not got:
            findings.append((label, "%s read nothing back from it: see the log beside %s" % (tool, state)))
            continue
        for name in sorted(set(want) | set(names)):
            if name not in names:
                findings.append(("%s %s" % (label, name), "the Python copy gives it and this copy does not declare it"))
            elif name not in want:
                findings.append(("%s %s" % (label, name), "this copy declares it and the Python copy gives no such number"))
            elif got.get(name) != want[name]:
                findings.append(("%s %s" % (label, name), "%s reads %s, the Python copy holds %s"
                                 % (tool, got.get(name, "nothing"), want[name])))
    return findings, 2 * len(want), "%d values, the definition's hash among them, each read back by Icarus Verilog from " \
        "the package and by gcc from the header, all equal to spec/constants.py" % len(want)


# -------------------------------------------------------------- rtl-benches

def bench_tests(root, module):
    """The names of the functions under @cocotb.test in a bench module, from its source."""
    path = os.path.join(root, "rtl", "tb", module + ".py")
    if not os.path.isfile(path):
        raise Refusal("MANIFEST-MALFORMED: the bench module rtl/tb/%s.py is not in the tree" % module)
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    names = []
    for node in tree.body:
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            for d in node.decorator_list:
                target = d.func if isinstance(d, ast.Call) else d
                if isinstance(target, ast.Attribute) and target.attr == "test" \
                        and isinstance(target.value, ast.Name) and target.value.id == "cocotb":
                    names.append(node.name)
    return names


def manifest(root):
    """The benches, checked. Anything this cannot read exactly is refused, MANIFEST-MALFORMED."""
    path = os.path.join(root, MANIFEST)
    if not os.path.isfile(path):
        raise Refusal("MANIFEST-MALFORMED: %s is not in the tree" % MANIFEST)
    try:
        with open(path, "rb") as f:
            doc = tomllib.loads(f.read().decode("utf-8"))
    except Exception as e:
        raise Refusal("MANIFEST-MALFORMED: %s: %s" % (type(e).__name__, e))
    profiles = constants(root)["PROFILES"]

    def bad(what):
        raise Refusal("MANIFEST-MALFORMED: %s" % what)

    def strings(x):
        return isinstance(x, list) and all(type(v) is str for v in x)

    benches = doc.get("bench")
    if set(doc) != {"bench"} or not isinstance(benches, list) or not benches:
        raise Refusal("NOTHING-SELECTED: %s names no bench" % MANIFEST)
    seen = set()
    for b in benches:
        if not isinstance(b, dict) or set(b) - {"mutant"} != {"name", "toplevel", "sources", "module", "profiles", "identity"}:
            bad("a bench's keys are %s" % (sorted(b) if isinstance(b, dict) else b))
        if type(b["name"]) is not str or not NAME.match(b["name"]) or b["name"] in seen:
            bad("the bench name %r is used twice or is not lower case letters, digits and hyphens" % (b["name"],))
        seen.add(b["name"])
        if type(b["toplevel"]) is not str or type(b["module"]) is not str:
            bad("%s: toplevel and module are names" % b["name"])
        if not strings(b["sources"]) or not b["sources"]:
            bad("%s: sources is a list of paths" % b["name"])
        for rel in b["sources"]:
            if os.path.isabs(rel) or ".." in rel.split("/") or not os.path.isfile(os.path.join(root, rel)):
                bad("%s: the source %r is not a file of the tree" % (b["name"], rel))
        if not strings(b["profiles"]) or not b["profiles"] or len(set(b["profiles"])) != len(b["profiles"]):
            bad("%s: profiles is a list of profile names, each once" % b["name"])
        for p in b["profiles"]:
            if p not in profiles:
                bad("%s: %r is not a profile of the definition" % (b["name"], p))
        b["tests"] = bench_tests(root, b["module"])
        if not b["tests"] or len(set(b["tests"])) != len(b["tests"]):
            bad("%s: rtl/tb/%s.py has no test under @cocotb.test, or names one twice" % (b["name"], b["module"]))
        if not strings(b["identity"]) or not b["identity"] or set(b["identity"]) - set(b["tests"]):
            bad("%s: identity names no test, or names %s, which the module does not have: a bench that holds nothing "
                "against the model is not a bench" % (b["name"], sorted(set(b["identity"]) - set(b["tests"]))))
        b.setdefault("mutant", [])
        mseen = set()
        if not isinstance(b["mutant"], list):
            bad("%s: mutant is a list of tables" % b["name"])
        for m in b["mutant"]:
            if not isinstance(m, dict) or set(m) != {"name", "file", "edits", "must_fail", "kind"}:
                bad("%s: a mutant's keys are %s" % (b["name"], sorted(m) if isinstance(m, dict) else m))
            if type(m["name"]) is not str or not NAME.match(m["name"]) or m["name"] in mseen:
                bad("%s: the mutant name %r is used twice or is not lower case letters, digits and hyphens" % (b["name"], m["name"]))
            mseen.add(m["name"])
            if m["file"] not in b["sources"]:
                bad("%s: mutant %s edits %r, which is not one of the bench's sources" % (b["name"], m["name"], m["file"]))
            if not isinstance(m["edits"], list) or not m["edits"] or not all(strings(e) and len(e) == 2 for e in m["edits"]):
                bad("%s: mutant %s: edits is a list of [old, new]" % (b["name"], m["name"]))
            if not strings(m["must_fail"]) or not m["must_fail"] or set(m["must_fail"]) - set(b["tests"]):
                bad("%s: mutant %s must fail %s, and the module has no such test"
                    % (b["name"], m["name"], sorted(set(m["must_fail"]) - set(b["tests"])) or "nothing"))
            if m["kind"] not in KINDS_OF_MISMATCH:
                bad("%s: mutant %s: kind is WORD, COUNT, UNKNOWN-BITS or empty" % (b["name"], m["name"]))
    return benches


def runs_of(benches):
    """Every run there must be: [(run name, bench, mutant or None)], in the runner's order."""
    out = []
    for b in benches:
        for p in b["profiles"]:
            out.append(("%s.%s" % (b["name"], p), b, None))
            for m in b["mutant"]:
                out.append(("%s.%s.mutant.%s" % (b["name"], p, m["name"]), b, m))
    return out


def read_results(path):
    """{test name: ("pass" | "fail" | "error" | "skip", message)} from a results file, or None when there is
    no file, it cannot be parsed, or it holds no test case. A name seen twice maps to ("twice", "")."""
    if not os.path.isfile(path):
        return None
    try:
        doc = ET.parse(path).getroot()
    except ET.ParseError:
        return None
    out = {}
    for case in doc.iter("testcase"):
        name = case.get("name")
        verdict, message = "pass", ""
        for tag, word in (("failure", "fail"), ("error", "error"), ("skipped", "skip")):
            el = case.find(tag)
            if el is not None and verdict == "pass":
                verdict, message = word, (el.get("message") or "").split("\n")[0]
        out[name] = ("twice", "") if name in out else (verdict, message)
    return out or None


EVIDENCE_MARK = "BIT-IDENTITY"      # what rtl/tb/harness.py puts in every line it writes


def read_evidence(path):
    """The harness's lines for a run: a list of dicts. A line that is not JSON, not an object, or does not
    carry the harness's mark is kept as {"verdict": "UNREADABLE"}."""
    out = []
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        entry = json.loads(line)
                    except ValueError:
                        entry = None
                    if not isinstance(entry, dict) or entry.get("mark") != EVIDENCE_MARK:
                        entry = {"verdict": "UNREADABLE"}
                    out.append(entry)
    return out


def judge(benches, out):
    """Read every run's files under `out`. Returns (findings, tests passed, records compared, runs, mutants, skips)."""
    findings, passed, records, nruns, nmutants, skips = [], 0, 0, 0, 0, []
    errors = {}
    try:
        with open(os.path.join(out, "runs.json"), encoding="utf-8") as f:
            errors = dict((r["run"], r["error"]) for r in json.load(f) if r.get("error"))
    except (OSError, ValueError, KeyError, TypeError):
        pass                        # the runner's own account is a help for messages, never a verdict
    for run, bench, mutant in runs_of(benches):
        results = read_results(os.path.join(out, run + ".xml"))
        evidence = read_evidence(os.path.join(out, run + ".evidence.jsonl"))
        if results is None:
            findings.append((run, "NO-RESULTS: the run left no results file with a test in it%s"
                             % (" (%s)" % errors[run] if run in errors else "")))
            continue
        if any(e.get("verdict") == "UNREADABLE" for e in evidence):
            findings.append((run, "EVIDENCE-UNREADABLE: a line of the run's evidence file is not what the harness writes"))
        if mutant is not None:
            nmutants += 1
            for test in mutant["must_fail"]:
                verdict, message = results.get(test, ("absent", ""))
                if verdict != "fail":
                    findings.append(("%s %s" % (run, test), "MUTANT-SURVIVED: on the mutated RTL this test's verdict is "
                                     "%r, and it must fail" % verdict))
                elif mutant["kind"] and not any(e.get("test") == test and e.get("verdict") == "MISMATCH"
                                                and e.get("kind") == mutant["kind"] for e in evidence):
                    findings.append(("%s %s" % (run, test), "MUTANT-WRONG-REASON: it failed (%s) with no %s mismatch "
                                     "from the harness" % (message, mutant["kind"])))
            continue
        nruns += 1
        for test in bench["tests"]:
            if test not in results:
                findings.append(("%s %s" % (run, test), "NOT-RUN: the bench has this test and the results file does not"))
        for test, (verdict, message) in sorted(results.items()):
            where = "%s %s" % (run, test)
            if test not in bench["tests"]:
                findings.append((where, "UNKNOWN-TEST: the results carry a test the bench's source does not show"))
            elif verdict == "skip":
                skips.append(where)
            elif verdict != "pass":
                findings.append((where, "%s: %s" % (verdict.upper(), message or "no message")))
            else:
                passed += 1
                if test in bench["identity"]:
                    mine = [e for e in evidence if e.get("test") == test]
                    same = [e for e in mine if e.get("verdict") == "IDENTICAL"]
                    if any(e.get("verdict") != "IDENTICAL" for e in mine):
                        findings.append((where, "EVIDENCE-DISAGREES: the test passed and the harness left a line that "
                                         "is not IDENTICAL"))
                    elif not same:
                        findings.append((where, "NO-EVIDENCE: the test passed and the harness compared nothing for it"))
                    elif any(type(e.get("records")) is not int or e["records"] < 1 or not e.get("model_digest")
                             or e.get("model_digest") != e.get("rtl_digest") for e in same):
                        findings.append((where, "EVIDENCE-DISAGREES: a line has no records, or its two digests differ"))
                    else:
                        records += sum(e["records"] for e in same)
    return findings, passed, records, nruns, nmutants, skips


def check_benches(root, state):
    benches = manifest(root)
    sim_image.require(root)
    out = os.path.join(state, "out")
    shutil.rmtree(out, ignore_errors=True)      # this stage's own folder: nothing of an earlier attempt may be read
    os.makedirs(out)
    r = sim_image.run(root, [(root, "/work", "ro"), (out, "/out", "rw")],
                      ["python", "/work/rtl/tb/run_benches.py", "--root", "/work", "--out", "/out"], timeout=3000)
    with open(os.path.join(state, "runner.log"), "w", encoding="utf-8", newline="\n") as f:
        f.write(r.stdout + "\n---- stderr ----\n" + r.stderr)
    findings, passed, records, nruns, nmutants, skips = judge(benches, out)
    for where in skips:
        print("SKIPPED %s" % where)
    ok = "%d test(s) passed in %d run(s) of %d bench(es); %d record(s) identical to the model's, word for word; " \
         "%d mutant run(s) each failed as named" % (passed, nruns, len(benches), records, nmutants)
    return findings, passed, ok


CHECKS = {"rtl-image": check_image, "rtl-spec": check_spec, "rtl-benches": check_benches}


def run(kind, root, state):
    """Returns (exit code, findings, the refusal's name or None). Shared by the real stage and its control."""
    try:
        findings, count, ok = CHECKS[kind](root, state)
    except ImageRefusal as e:
        print("REFUSED %s: %s" % (kind, e))
        return 2, [], e.name
    except Refusal as e:
        print("REFUSED %s: %s" % (kind, e))
        return 2, [], str(e).split(":")[0]
    for where, what in findings:
        print("FINDING %s %s: %s" % (kind, where, what))
    if findings:
        print("FAIL %s: %d finding(s)" % (kind, len(findings)))
        return 1, findings, None
    if count == 0:
        print("REFUSED %s: NOTHING-SELECTED: zero items checked is not a pass" % kind)
        return 2, [], "NOTHING-SELECTED"
    print("OK %s: %s" % (kind, ok))
    return 0, [], None


# ------------------------------------------------------------- the controls

def edit(copy, name, old, new):
    path = os.path.join(copy, name)
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    if text.count(old) != 1:
        raise Refusal("PLANT-DOES-NOT-APPLY: %r is in %s %d time(s), not once" % (old, name, text.count(old)))
    write(copy, name, text.replace(old, new))


def plants(kind, root, scratch):
    """[(a copy of the tree with faults planted, the set of `where` that must be reported, or ("REFUSED", name))]."""
    if kind == "rtl-image":
        a = copy_tree(root, scratch, "a")
        write(a, "docker/Dockerfile.sim", "# planted: one more line\n", "a")     # a tree whose docker files changed
        b = copy_tree(root, scratch, "b")
        os.remove(os.path.join(b, "docker", "requirements-sim.txt"))             # one that lost a file
        c = copy_tree(root, scratch, "c")
        write(c, "docker/requirements-sim.txt", "# planted: one more line\n", "a")  # and one whose package list changed
        return [(a, ("REFUSED", "IMAGE-MISSING")), (b, ("REFUSED", "IMAGE-INPUT-MISSING")),
                (c, ("REFUSED", "IMAGE-MISSING"))]
    if kind == "rtl-spec":
        a = copy_tree(root, scratch, "a")
        # `generated` would see the text; this check must see the numbers.
        # EVERY number of each copy is changed, by the names the copy itself declares: one is added to it.
        sv, c, unreadable = declared(a)
        if unreadable or sorted(sv) != sorted(c):
            raise Refusal("PLANT-DOES-NOT-APPLY: the two copies do not declare the same readable names")
        want = set()
        for name in sv:
            if name == "SPEC_SHA256":
                edit(a, "spec/undertone_pkg.sv", "SPEC_SHA256 = 256'h", "SPEC_SHA256 = 256'h1 + 256'h")
                edit(a, "spec/undertone.h", "#define UNDERTONE_SPEC_SHA256 \"", "#define UNDERTONE_SPEC_SHA256 \"0")
            else:
                edit(a, "spec/undertone_pkg.sv", "localparam int %s = " % name, "localparam int %s = 1 + " % name)
                edit(a, "spec/undertone.h", "#define UNDERTONE_%s " % name, "#define UNDERTONE_%s 1 + " % name)
            want |= {"spec/undertone_pkg.sv %s" % name, "spec/undertone.h %s" % name}
        # And one name taken out of the header, under another: missing, and one too many.
        edit(a, "spec/undertone.h", "#define UNDERTONE_FLAG_OVERFLOW_BIT ", "#define UNDERTONE_PLANTED_OTHER_NAME ")
        return [(a, want | {"spec/undertone.h PLANTED_OTHER_NAME"})]
    if kind == "rtl-benches":
        a = copy_tree(root, scratch, "a")
        # The plants are written for the foundation's own bench, by name: its module has BASE, one_run and
        # control_frames. If that bench goes, this control says so and fails, and is written again.
        named = [b for b in manifest(root) if b["name"] == "p0-onetap"]
        if not named or len(named[0]["profiles"]) < 2:
            raise Refusal("PLANT-DOES-NOT-APPLY: there is no bench p0-onetap under two profiles")
        bench = named[0]
        # The copy's manifest keeps that bench alone: everything from the second top-level [[bench]] on is cut.
        with open(os.path.join(a, MANIFEST), encoding="utf-8", newline="") as f:
            lines = f.read().split("\n")
        starts = [i for i, line in enumerate(lines) if line.strip() == "[[bench]]"]
        if not starts or manifest(root)[0]["name"] != "p0-onetap":
            raise Refusal("PLANT-DOES-NOT-APPLY: p0-onetap is not the manifest's first bench")
        if len(starts) > 1:
            write(a, MANIFEST, "\n".join(lines[:starts[1]]).rstrip("\n") + "\n")
        first, second = bench["profiles"][0], bench["profiles"][1]
        module = "rtl/tb/%s.py" % bench["module"]
        # Under the second profile the simulator exits, with exit code 0, before any test: no results file.
        edit(a, module, "\nimport cocotb\n",
             "\nimport cocotb\nif os.environ.get(\"UNDERTONE_PROFILE\") == \"%s\":\n    os._exit(0)\n" % second)
        # And one more test, with a wrong expectation: the model it compares with has a head weight one less.
        write(a, module, "\n\n@cocotb.test()\nasync def planted_wrong_expectation(dut):\n"
                         "    harness.start_clock(dut)\n"
                         "    coef, head, rectifier, shift, epoch = BASE\n"
                         "    await one_run(dut, BASE, control_frames(), \"planted_wrong_expectation\", \"head one less\",\n"
                         "                  model_config=(coef, head - 1, rectifier, shift, epoch))\n", "a")
        # An identity test that compares nothing: the manifest now names one that leaves no evidence.
        edit(a, MANIFEST, 'identity = ["bit_identity_random", "bit_identity_extremes"]',
             'identity = ["bit_identity_random", "bit_identity_extremes", "control_nothing_compared"]')
        # And a mutant asked to fail for a reason that is not its own: the design that stops is named WORD.
        edit(a, MANIFEST, 'edits = [["out_valid <= in_valid;", "out_valid <= in_valid && (index < 4);"]]\n'
                          'must_fail = ["bit_identity_random", "bit_identity_extremes"]\nkind = "COUNT"',
             'edits = [["out_valid <= in_valid;", "out_valid <= in_valid && (index < 4);"]]\n'
             'must_fail = ["bit_identity_random", "bit_identity_extremes"]\nkind = "WORD"')
        want = {"%s.%s planted_wrong_expectation" % (bench["name"], first), "%s.%s" % (bench["name"], second),
                "%s.%s control_nothing_compared" % (bench["name"], first),
                "%s.%s.mutant.stops-after-four bit_identity_random" % (bench["name"], first),
                "%s.%s.mutant.stops-after-four bit_identity_extremes" % (bench["name"], first)}
        want |= set("%s.%s.mutant.%s" % (bench["name"], second, m["name"]) for m in bench["mutant"])
        return [(a, want)]
    raise Refusal("no control for %s" % kind)


def control(kind, root, scratch):
    ok, total = True, 0
    try:
        planted = plants(kind, root, scratch)
    except (Refusal, ImageRefusal) as e:
        print("control %s: could not plant: %s" % (kind, e))
        return 0
    for copy, want in planted:
        print("control %s: checking the planted copy %s" % (kind, copy))
        rc, findings, refusal = run(kind, copy, os.path.join(copy, ".state"))
        if isinstance(want, tuple):
            total += 1
            if rc != 2 or refusal != want[1]:
                print("control %s: the copy should have been REFUSED as %s (rc=%d, refused as %s)" % (kind, want[1], rc, refusal))
                ok = False
            continue
        got = set(f[0].replace("\\", "/") for f in findings)
        total += len(want)
        if rc != 1 or got != want:
            print("control %s: NOT detected as planted (rc=%d). missed: %s. reported but not planted: %s"
                  % (kind, rc, sorted(want - got) or "none", sorted(got - want) or "none"))
            ok = False
    if ok:
        print("CONTROL-DETECTED %s all %d planted fault(s), nothing else" % (kind, total))
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("kind", choices=sorted(CHECKS) + ["control"])
    ap.add_argument("what", nargs="?", choices=sorted(CHECKS))
    ap.add_argument("--root", required=True)
    ap.add_argument("--state")
    ap.add_argument("--scratch")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    if a.kind == "control":
        if not a.what or not a.scratch:
            ap.error("control needs a KIND and --scratch DIR")
        return control(a.what, root, os.path.abspath(a.scratch))
    if not a.state:
        ap.error("a check needs --state DIR")
    return run(a.kind, root, os.path.abspath(a.state))[0]


if __name__ == "__main__":
    sys.exit(main())

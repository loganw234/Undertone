#!/usr/bin/env python3
"""The build checks behind verify/run.sh. Standard library, plus pytest for the tests.

    check_build.py generated    --root DIR   the generated copies equal their sources
    check_build.py model-tests  --root DIR   the tests under tests/ pass
    check_build.py independence --root DIR   model/ and stats/ each import with the other blocked
    check_build.py registry     --root DIR   gate rows and gate-claiming tests agree, both ways
    check_build.py control KIND --root DIR --scratch DIR
                                             plant faults of KIND in a copy of the tree and run
                                             the same check on the copy

A check prints "OK <kind>: <counts>" and exits 0, or prints each finding as
"FINDING <kind> <where>: <what>" and exits 1. What it cannot do exactly is
REFUSED by name with exit 2. verify/run.sh asserts on the OK line.

`control` prints "CONTROL-DETECTED <kind> ..." and exits 1 only when every
planted fault was reported and nothing else was. When it runs to its end
without that, it exits 0. If it crashes it exits non-zero with a traceback and
no CONTROL-DETECTED line; the runner needs the line, so it fails that too.

WHAT THESE CHECKS CANNOT SEE (stated limits):
  generated     compares spec/constants.py with what the definition gives, and
                each vectors/<folder>/SHA256SUMS with its folder, subfolders
                included. It does not know whether a vector's expected answer
                is right, nor whether the definition says what the design means.
  model-tests   reads the results file pytest writes, not its exit code alone.
                It runs the tests pytest selects under tests/. A conftest.py
                or a pytest.ini can deselect tests, and this stage would run
                what is left: it prints how many ran, and that number is read
                at each merge. Only the lead adds a conftest.py. A test file
                outside tests/, or not named test_*.py, is not run. A property
                no test asserts is not held by this stage.
  independence  catches an import of the other package made while a module is
                imported. It does not see an import inside a function that no
                import runs, a module loaded by path, a copied file, or an
                ImportError the importing module swallows. Both packages read
                spec/: shared facts by design. Code that both import from some
                third place is shared code this stage does not see.
  registry      matches a gate's row to tests by NAME: test_gate_<gate>__*
                and test_control_<gate>__*. It does not read what a test
                asserts, so a test can carry a gate's name and test nothing.
                For a stage row it checks that the control is a MUST_FAIL
                stage of the runner and the test is not; it does not check
                that the two are about the same thing.
  control       plants the faults listed in plants() and no others. A check
                broken some other way passes its control. Nothing guards
                control() itself: one rewritten to always answer DETECTED
                would pass.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_spec  # noqa: E402
import gen_sums  # noqa: E402
from check_tree import Refusal, committable  # noqa: E402

ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def check_generated(root, state):
    findings = list(gen_spec.check(root))
    sums, nfolders, nfiles = gen_sums.check(root)
    findings += sums
    if nfolders == 0:
        raise Refusal("NOTHING-SELECTED: no folder under vectors/")
    return findings, 1 + nfolders, "1 generated file and %d checksum list(s) over %d vector file(s) match their sources" \
        % (nfolders, nfiles)


def pytest_run(root, args):
    return subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider"] + args,
                          cwd=root, capture_output=True, text=True, env=ENV)


def check_model_tests(root, state):
    out = state or tempfile.mkdtemp(prefix="model-tests-")
    os.makedirs(out, exist_ok=True)
    xml = os.path.join(out, "junit-%d.xml" % os.getpid())
    if os.path.exists(xml):
        os.remove(xml)
    p = pytest_run(root, ["-q", "--junitxml", xml, "tests"])
    print(p.stdout[-2500:].rstrip())
    if p.stderr.strip():
        print(p.stderr[-1500:].rstrip())
    if not os.path.exists(xml):
        raise Refusal("NO-RESULTS-FILE: pytest wrote no results (its exit code was %d)" % p.returncode)
    tests = failures = errors = skipped = 0
    findings = []
    for case in ET.parse(xml).getroot().iter("testcase"):
        tests += 1
        ident = "%s::%s" % (case.get("classname", "?"), case.get("name", "?"))
        if case.find("failure") is not None:
            failures += 1
            findings.append((ident, "failed"))
        elif case.find("error") is not None:
            errors += 1
            findings.append((ident, "errored"))
        elif case.find("skipped") is not None:
            skipped += 1
            print("SKIPPED %s: %s" % (ident, case.find("skipped").get("message", "")))
    if tests == 0:
        raise Refusal("NOTHING-SELECTED: pytest collected no test (its exit code was %d)" % p.returncode)
    if p.returncode != 0 and not findings:
        findings.append(("pytest", "exit code %d with no failure in its results file" % p.returncode))
    return findings, tests, "%d tests ran, 0 failed, 0 errored, %d skipped" % (tests, skipped)


def check_independence(root, state):
    findings, counts = [], {}
    for pkg, other in (("model", "stats"), ("stats", "model")):
        if not os.path.isdir(os.path.join(root, pkg)):
            raise Refusal("NO-PACKAGE: %s/" % pkg)
        p = subprocess.run([sys.executable, os.path.join(HERE, "_import_blocked.py"), pkg, other],
                           cwd=root, capture_output=True, text=True, env=ENV)
        n = re.search(r"^MODULES (\d+)$", p.stdout, re.M)
        if p.returncode != 0 or not n:
            raise Refusal("IMPORT-WALK-FAILED: %s: %s" % (pkg, (p.stderr or p.stdout).strip()[-400:]))
        counts[pkg] = int(n.group(1))
        for kind, module, what in re.findall(r"^(CROSS|IMPORT-ERROR) (\S+): (.*)$", p.stdout, re.M):
            findings.append((module, "imports the blocked package: %s" % what if kind == "CROSS"
                             else "does not import: %s" % what))
    return findings, min(counts.values()), \
        "%d module(s) in model/ and %d in stats/ import with the other blocked" % (counts["model"], counts["stats"])


def d0_gates(root):
    path = os.path.join(root, "docs", "studies", "D0-rough-design.md")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        part = text[text.index("## 9. "):text.index("## 10. ")]
    except ValueError:
        raise Refusal("D0-SECTION-9-NOT-FOUND: %s" % path)
    names = []
    for line in part.split("\n"):
        if line.startswith("| ") and not line.startswith("| gate ") and not line.startswith("|---"):
            names.append(line.split("|")[1].strip())
    if not names:
        raise Refusal("D0-GATES-NOT-FOUND")
    return names


def stage_names(root):
    """(every stage of the runner, the ones that are MUST_FAIL controls)."""
    with open(os.path.join(root, "verify", "run.sh"), encoding="utf-8") as f:
        text = f.read()
    return (set(re.findall(r'^stage ([a-z0-9-]+) "', text, re.M)),
            set(re.findall(r'^MUST_FAIL=1\nstage ([a-z0-9-]+) "', text, re.M)))


def collected(root):
    p = pytest_run(root, ["--collect-only", "-q", "tests"])
    names = set(re.findall(r"^\S+::(\w+)", p.stdout, re.M))
    if not names:
        raise Refusal("NOTHING-COLLECTED: %s" % (p.stdout + p.stderr).strip()[-300:])
    return names


def check_registry(root, state):
    with open(os.path.join(root, "tests", "gates.toml"), "rb") as f:
        doc = tomllib.loads(f.read().decode("utf-8"))
    rows = doc.get("gate", [])
    if not isinstance(rows, list) or not rows:
        raise Refusal("NOTHING-SELECTED: tests/gates.toml has no [[gate]] row")
    known, (stages, controls), tests = d0_gates(root), stage_names(root), collected(root)
    findings, slugs, seen = [], set(), set()
    for key in sorted(set(doc) - {"gate"}):
        findings.append(("tests/gates.toml", "has a table named %r; only [[gate]] is read" % key))
    for row in rows:
        name = row.get("name", "?")
        where = "gate %s" % name
        if name in seen:
            findings.append((where, "has two rows"))
        seen.add(name)
        want = {"name", "d0", "kind"} | ({"test", "control"} if row.get("kind") == "stage" else set())
        if set(row) != want:
            findings.append((where, "has the keys %s, expected %s" % (sorted(row), sorted(want))))
        if row.get("d0") not in known:
            findings.append((where, "names %r, which is not a gate of D0's section 9" % (row.get("d0"),)))
        if row.get("kind") == "stage":
            if row.get("test") not in stages - controls:
                findings.append((where, "its test, %r, is not a stage of verify/run.sh that must pass"
                                 % (row.get("test"),)))
            if row.get("control") not in controls:
                findings.append((where, "its control, %r, is not a MUST_FAIL stage of verify/run.sh"
                                 % (row.get("control"),)))
        elif row.get("kind") == "pytest":
            slug = name.replace("-", "_")
            slugs.add(slug)
            for prefix, what in (("test_gate_", "test"), ("test_control_", "negative control")):
                if not any(t.startswith(prefix + slug + "__") for t in tests):
                    findings.append((where, "no %s claims it: no test named %s%s__*" % (what, prefix, slug)))
        else:
            findings.append((where, "kind is %r, not 'stage' or 'pytest'" % (row.get("kind"),)))
    claiming = 0
    for t in sorted(tests):
        m = re.match(r"test_(?:gate|control)_(.*)$", t)
        if not m:
            continue
        claiming += 1
        if "__" not in m.group(1):
            findings.append((t, "claims a gate but has no '__' after the gate's name"))
        elif m.group(1).split("__", 1)[0] not in slugs:
            findings.append((t, "claims gate %r, which has no pytest row in tests/gates.toml"
                             % m.group(1).split("__", 1)[0]))
    return findings, len(rows), "%d gate row(s), each with its test and its control; %d gate-claiming test(s), each with a row" \
        % (len(rows), claiming)


CHECKS = {"generated": check_generated, "model-tests": check_model_tests,
          "independence": check_independence, "registry": check_registry}


def run(kind, root, state=None):
    """Returns (exit code, findings). Shared by the real stage and its control."""
    try:
        findings, count, ok = CHECKS[kind](root, state)
    except Refusal as e:
        print("REFUSED %s: %s" % (kind, e))
        return 2, []
    for where, what in findings:
        print("FINDING %s %s: %s" % (kind, where, what))
    if findings:
        print("FAIL %s: %d finding(s)" % (kind, len(findings)))
        return 1, findings
    if count == 0:
        print("REFUSED %s: NOTHING-SELECTED: zero items checked is not a pass" % kind)
        return 2, []
    print("OK %s: %s" % (kind, ok))
    return 0, []


def copy_tree(root, scratch, tag):
    os.makedirs(scratch, exist_ok=True)
    dst = tempfile.mkdtemp(prefix="plant-%s-" % tag, dir=scratch)
    for name in committable(root):
        full = os.path.join(dst, name)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        shutil.copyfile(os.path.join(root, name), full)
    return dst


def write(root, name, text, mode="w"):
    full = os.path.join(root, name)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, mode, encoding="utf-8", newline="") as f:
        f.write(text)


def plants(kind, root, scratch):
    """A list of (copy of the tree with faults planted, the set of `where` that must be reported,
    or the string "REFUSED" when the check must refuse the copy)."""
    if kind == "generated":
        a = copy_tree(root, scratch, "a")
        write(a, "spec/constants.py", "PLANTED = 1\n", "a")
        vec = os.path.join(a, "vectors", "p0", "sample_range.json")
        with open(vec, encoding="utf-8") as f:
            text = f.read()
        write(a, "vectors/p0/sample_range.json", text.replace("32767", "32768", 1))
        # A vector in a subfolder, never listed: the first verifier's finding on this check.
        write(a, "vectors/p0/deeper/unlisted.json", "{}\n")
        return [(a, {"spec/constants.py", "vectors/p0/sample_range.json", "vectors/p0/deeper/unlisted.json"})]
    if kind == "model-tests":
        a = copy_tree(root, scratch, "a")
        write(a, "tests/test_planted_fail.py", "def test_planted_must_fail():\n    assert 1 == 2\n")
        b = copy_tree(root, scratch, "b")
        for f in os.listdir(os.path.join(b, "tests")):
            if f.startswith("test_") and f.endswith(".py"):
                os.remove(os.path.join(b, "tests", f))
        # A test file that cannot be imported. It gets a copy of its own: pytest stops at a
        # collection error and runs nothing, so a failing test beside it would never be seen.
        c = copy_tree(root, scratch, "c")
        write(c, "tests/test_planted_broken.py", "import no_such_module_anywhere\n\n\ndef test_never_runs():\n    pass\n")
        return [(a, {"tests.test_planted_fail::test_planted_must_fail"}), (b, "REFUSED"),
                (c, {"::tests.test_planted_broken"})]
    if kind == "independence":
        a = copy_tree(root, scratch, "a")
        write(a, "model/planted_cross.py", "import stats\n")
        write(a, "stats/planted_cross.py", "from model import stream\n")
        # A module in a folder with no __init__.py: the first verifier's finding on this check.
        write(a, "model/no_init_here/planted_deep.py", "import stats\n")
        return [(a, {"model.planted_cross", "stats.planted_cross", "model.no_init_here.planted_deep"})]
    if kind == "registry":
        a = copy_tree(root, scratch, "a")
        write(a, "tests/gates.toml",
              '\n[[gate]]\nname = "noise-tails"\nd0 = "noise tails"\nkind = "pytest"\n'
              '\n[[gate]]\nname = "made-up"\nd0 = "a gate D0 does not have"\nkind = "stage"\n'
              'test = "generated"\ncontrol = "ctl-generated"\n'
              '\n[[gate]]\nname = "control-is-no-control"\nd0 = "replay"\nkind = "stage"\n'
              'test = "generated"\ncontrol = "links"\n', "a")
        write(a, "tests/test_planted_claim.py",
              "def test_gate_no_such_gate__anything():\n    pass\n\n\n"
              "def test_control_no_such_gate__anything():\n    pass\n")
        return [(a, {"gate noise-tails", "gate made-up", "gate control-is-no-control",
                     "test_gate_no_such_gate__anything", "test_control_no_such_gate__anything"})]
    raise SystemExit("no plants for %r" % kind)


def control(kind, root, scratch):
    ok, total = True, 0
    for copy, want in plants(kind, root, scratch):
        print("control %s: checking the planted copy %s" % (kind, copy))
        rc, findings = run(kind, copy, os.path.join(copy, ".state"))
        if want == "REFUSED":
            total += 1
            if rc != 2:
                print("control %s: the copy should have been REFUSED (rc=%d)" % (kind, rc))
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
    return run(a.kind, root, os.path.abspath(a.state) if a.state else None)[0]


if __name__ == "__main__":
    sys.exit(main())

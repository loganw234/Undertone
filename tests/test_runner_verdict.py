"""The gate's own verdict line: what `verify/run.sh` prints for each of its sizes.

This project commits on one line. Since round 2 the runner has two sizes, and the bare line
"== VERDICT: PASS" is to mean that every stage ran. A run of the first size must say that the rtl
stages were not run. Nothing held that until a verifier was handed a runner that printed the bare line
for the first size, and found it by running it.

The gate cannot run itself from inside its own tests: so this test runs A COPY of the runner in which
every stage's command is replaced by one that prints what that stage prints when it passes. Everything
else in the copy is the runner's own text: its options, its counting, its verdict line.

What this cannot see: any stage's own check, and the wording for a failing run. It holds four
invocations and no others. It takes about eight seconds, which is why it is in a file of its own:
the `model-tests` control keeps the files named test_p0_* in its copies and would run it again in each.

This file is the lead's.
"""
import os
import re
import subprocess

from test_p0_rtl_gate import ROOT, the_gates_own_bash


def stand_in_runner(tmp_path):
    """Returns (the folder the copy's verify/ is in, how many stages, how many of them are rtl stages)."""
    with open(os.path.join(ROOT, "verify", "run.sh"), encoding="utf-8") as f:
        lines = f.read().split("\n")
    out, control, names = [], False, []
    for line in lines:
        m = re.match(r'(stage ([a-z0-9-]+) "[^"]*") -- ', line)
        if m:
            names.append(m.group(2))
            if control:
                out.append("%s -- sh -c 'echo \"CONTROL-DETECTED stand-in\"; exit 1'" % m.group(1))
            else:
                out.append('%s -- echo "OK %s: 1 stand-in"' % (m.group(1), m.group(2)))
            control = False
        else:
            control = control or line.strip() == "MUST_FAIL=1"
            out.append(line)
    folder = tmp_path / "tree" / "verify"
    folder.mkdir(parents=True)
    with open(folder / "run.sh", "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out))
    return str(tmp_path / "tree"), len(names), len([n for n in names if n.startswith(("rtl-", "ctl-rtl-"))])


def verdict(tree, state, *args):
    """(exit code, the one verdict line) of one run of the copy, with a state folder of its own."""
    r = subprocess.run([the_gates_own_bash(), "verify/run.sh"] + list(args), cwd=tree, capture_output=True, text=True,
                       env=dict(os.environ, STATEROOT=state.as_posix()), timeout=300)
    lines = [line for line in r.stdout.split("\n") if line.startswith("== VERDICT")]
    assert len(lines) == 1, r.stdout + r.stderr
    return r.returncode, lines[0]


def test_runner_the_bare_verdict_line_is_printed_only_when_every_stage_ran(tmp_path):
    tree, n, n_rtl = stand_in_runner(tmp_path)
    assert (n, n_rtl) == (22, 6), "the stage list changed: the figures in the lines below change with it"
    # The first size: every stage that needs no Docker. Its line says what did not run.
    assert verdict(tree, tmp_path / "first") == (
        0, "== VERDICT: PASS for the first size: the 6 rtl stage(s) of 22 were NOT run (--with rtl runs them)")
    # The second size: every stage. The bare line, and the only invocation that prints it.
    assert verdict(tree, tmp_path / "second", "--with", "rtl") == (0, "== VERDICT: PASS")


def test_runner_a_selection_or_a_skip_is_never_the_bare_line(tmp_path):
    tree, _n, _n_rtl = stand_in_runner(tmp_path)
    assert verdict(tree, tmp_path / "only", "--only", "links") == (
        0, "== VERDICT: PASS for the selected stages only: 21 of 22 stage(s) were NOT run")
    code, line = verdict(tree, tmp_path / "skip", "--with", "rtl", "--only", "rtl-image,rtl-spec", "--skip", "rtl-spec")
    assert code == 0 and line.startswith("== VERDICT: PASS for the selected stages only: 20 of 22 stage(s) were NOT run, "
                                         "with 1 stage(s) and 0 inner check(s) skipped by name above")
    code, line = verdict(tree, tmp_path / "all", "--with", "rtl", "--only", "rtl-image,rtl-spec", "--skip", "rtl-spec",
                         "--require-all")
    assert code == 1 and line == "== VERDICT: FAIL"

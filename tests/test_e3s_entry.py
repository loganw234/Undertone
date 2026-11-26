"""The full run's script, started as its docstring says it is started, runs: it does not load and exit.

tests/test_e3s_experiment.py's docstring gives the full run's two commands, from the tree's root:

    python tests/test_e3s_experiment.py --full --station MPP --data <recordings> --out e3-MPP.json
    python tests/test_e3s_experiment.py --judge e3-MPP.json e3-CDM.json e3-HDH.json e3-SRN.json

Until 2026-11-25 the file defined `main` and had no entry block, so each command loaded the file
and exited 0, with nothing run and nothing written (found by the lead's full run, which then
called the committed `main` through a runner of the lead's). Here the script is started so, with
`sys.executable` and no shell, from the root, on argument sets that are refused and write nothing:
a station that is not the rule's, a judge given no parts, and no arguments. Each must exit with its
own code and say its own refusal; a file without the block exits 0 and says nothing, and fails
every test here.

What this does not see: a full part run to its end (the records are not in the tree; the gate holds
what `--full` reads short of them, `full_inputs`), a judge of real parts, and a block that calls
`main` with arguments other than the command line's.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = "tests/test_e3s_experiment.py"  # as the docstring writes it, from the root


def started(args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, SCRIPT] + args, cwd=ROOT, env=env, capture_output=True, text=True,
                          timeout=600)


def test_e3s_entry_full_on_a_station_not_the_rules_is_refused_and_writes_nothing(tmp_path):
    out = tmp_path / "e3-XYZ.json"
    got = started(["--full", "--station", "XYZ", "--data", str(tmp_path / "recordings"), "--out", str(out)])
    assert got.returncode == 1, (got.returncode, got.stdout, got.stderr)
    assert got.stdout == ""
    assert got.stderr.strip().splitlines()[-1] == \
        "ValueError: there is no station 'XYZ': the stations are ['MPP', 'CDM', 'HDH', 'SRN']", got.stderr
    assert "in full_part" in got.stderr and "in full_inputs" in got.stderr, "refused by the full run's own path"
    assert sorted(os.listdir(tmp_path)) == [], "nothing written"


def test_e3s_entry_judge_with_no_parts_is_refused_and_bare_prints_the_commands(tmp_path):
    got = started(["--judge"])
    lines = got.stdout.splitlines()
    assert got.returncode == 1, (got.returncode, got.stdout, got.stderr)
    assert lines[0] == ("E3 in software: profile s16x1, Pfa 0.01, z 4.0; "
                        "the matched filter of e0 against E1's learner of 16384 records"), got.stdout
    assert lines[1].startswith("  THE REPORTED READINGS: refused, NOT_THE_NAMED_MODEL"), got.stdout
    assert lines[-1] == "== E3 SOFTWARE: NOT HELD at every station" and len(lines) == 3, got.stdout
    bare = started([])
    assert bare.returncode == 2, (bare.returncode, bare.stdout, bare.stderr)
    assert bare.stdout.startswith("Stage E3 in software: does E1's learner reach the matched filter's efficiency")
    assert "python tests/test_e3s_experiment.py --full --station MPP" in bare.stdout
    assert "python tests/test_e3s_experiment.py --judge e3-MPP.json" in bare.stdout

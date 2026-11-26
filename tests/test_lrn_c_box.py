"""LRN-C: what the box runs, and that it imports nothing from tests/, learn/ or hw/lrnc/ and needs no more than the
standard library.

The box runs `hw/lrnc/box_lrnc.sh`, which runs `hw/e0c/run_piece.py` (host.run_case with Python's cyclic collector
off) for every run of order.txt, and Python's -c with json and sys to read a field of a JSON file. Nothing else of
Python. The import check is E0C's own (`box_findings` of tests/test_e0c_compare.py, imported), which follows every
import through the tree. Beside it: every flag the script hands run_piece is one host.run_case's parser declares,
so a misspelt flag is seen here and not on the card day; each run sits under `timeout 900` with its stdin closed;
and nothing stops the script after a run that ends refused.
"""
import ast
import os

import test_e0c_compare as T0

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "hw", "lrnc", "box_lrnc.sh")


def script_text():
    with open(SCRIPT, encoding="utf-8") as f:
        return f.read()


def run_case_flags():
    with open(os.path.join(ROOT, "host", "run_case.py"), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    return set(node.args[0].value for node in ast.walk(tree) if isinstance(node, ast.Call)
               and getattr(node.func, "attr", None) == "add_argument" and node.args
               and isinstance(node.args[0], ast.Constant))


def test_lrn_c_nothing_the_box_runs_imports_from_tests_learn_or_hw_lrnc_or_needs_more_than_the_standard_library():
    files = [os.path.join(ROOT, "hw", "e0c", "run_piece.py")]
    assert T0.box_findings(files) == []
    tree, _other = T0.reached(files)
    assert "host.run_case" in tree and "host.library" in tree and "host.drive" in tree
    assert not any(n.startswith(("learn", "stats", "hw.lrnc", "rtl", "tests")) for n in tree)
    text = script_text()
    runs = [line.split("python3", 1)[1].split()[0] for line in text.split("\n")
            if "python3" in line and not line.lstrip().startswith("#")]
    assert sorted(set(runs)) == ["-c", "hw/e0c/run_piece.py"]
    for line in text.split("\n"):
        if "python3 -c" in line:
            assert T0.imported(line.split('"')[1]) == ["json", "sys"]


def test_lrn_c_every_flag_the_box_script_hands_run_piece_is_one_run_case_takes():
    code = "\n".join(line for line in script_text().split("\n") if not line.lstrip().startswith("#"))
    handed = set(w for w in code.replace('"', " ").split() if w.startswith("--"))
    declared = run_case_flags()
    assert handed == {"--xclbin", "--shim", "--blob", "--table", "--seed", "--frames", "--schedule", "--learn",
                      "--count-bits", "--update-frames", "--epoch", "--out", "--polls"}
    assert handed <= declared, handed - declared


def test_lrn_c_the_box_script_bounds_each_run_and_goes_on_after_a_refused_one():
    """Read, not run: no test may start that shell."""
    code = [line for line in script_text().split("\n") if line.strip() and not line.lstrip().startswith("#")]
    runs = [line for line in code if "python3 hw/e0c/run_piece.py" in line]
    assert len(runs) == 1 and "(cd \"$H\" && timeout 900 python3 hw/e0c/run_piece.py" in runs[0]
    tail = code[code.index(runs[0]) + 3]
    assert tail.strip().endswith('> "$R/$name.log" 2>&1 < /dev/null'), tail
    assert "set -u" in code and not any(line.strip().startswith("set -e") or "errexit" in line for line in code)
    exits = [line.strip() for line in code if "exit" in line.replace("exit $?", "")]
    assert exits == ['mkdir -p "$R"; cd "$R" || exit 1'], exits
    loop = code.index("while read -r name case; do")
    assert code[loop:loop + 3] == ["while read -r name case; do", '    [ -n "$name" ] && one "$name" "$case"',
                                   'done < "$CASES/order.txt"']
    assert any('--learn "$d/script.json"' in line for line in code)

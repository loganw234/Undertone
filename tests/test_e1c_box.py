"""E1C: what the box runs, and that it imports nothing from tests/ or learn/ and needs no more than the standard library.

The box runs `hw/e1c/box_e1.sh`, which runs `hw/e0c/run_piece.py` (host.run_case, unchanged, the collector off) for
every run of order.txt, and Python's -c with json and sys to read a field of a JSON file. Nothing else of Python.
The import check is E0C's own (`box_findings` of tests/test_e0c_compare.py, imported), which follows every import
through the tree. Beside it: every flag the script hands run_piece is one host.run_case's parser declares, so a
misspelt flag is seen here and not on the card day; and the fields of order.txt's lines are the ones the script's
`one` reads, four or seven.
"""
import ast
import os

import test_e0c_compare as T0

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "hw", "e1c", "box_e1.sh")


def script_text():
    with open(SCRIPT, encoding="utf-8") as f:
        return f.read()


def run_case_flags():
    with open(os.path.join(ROOT, "host", "run_case.py"), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    return set(node.args[0].value for node in ast.walk(tree) if isinstance(node, ast.Call)
               and getattr(node.func, "attr", None) == "add_argument" and node.args
               and isinstance(node.args[0], ast.Constant))


def test_e1c_nothing_the_box_runs_imports_from_tests_or_learn_or_needs_more_than_the_standard_library():
    files = [os.path.join(ROOT, "hw", "e0c", "run_piece.py")]
    assert T0.box_findings(files) == []
    tree, _other = T0.reached(files)
    assert "host.run_case" in tree and not any(n.startswith(("learn", "stats", "hw.e1c")) for n in tree)
    text = script_text()
    runs = [line.split("python3", 1)[1].split()[0] for line in text.split("\n")
            if "python3" in line and not line.lstrip().startswith("#")]
    assert sorted(set(runs)) == ["-c", "hw/e0c/run_piece.py"]
    for line in text.split("\n"):
        if "python3 -c" in line:
            assert T0.imported(line.split('"')[1]) == ["json", "sys"]


def test_e1c_every_flag_the_box_script_hands_run_piece_is_one_run_case_takes():
    text = script_text()
    handed = set(w for w in text.replace('"', " ").split() if w.startswith("--"))
    declared = run_case_flags()
    assert handed == {"--xclbin", "--shim", "--blob", "--epoch", "--table", "--seed", "--frames", "--schedule", "--out",
                      "--polls", "--swap-blob", "--swap-at", "--swap-after"}
    assert handed <= declared, handed - declared
    assert "--swap-unbatched" in declared and "--swap-unbatched" not in handed, "the swap is batched, as round 3's"


def test_e1c_the_box_check_sees_a_planted_import():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        planted = os.path.join(d, "planted.py")
        with open(planted, "w", encoding="utf-8") as f:
            f.write("import json\nfrom hw.e1c import e1c\nimport learn\n")
        found = set(T0.box_findings([planted]))
    assert {"test_lrn_a_e1", "numpy"} <= found and any(n.startswith("hw.e1c") or n.startswith("learn") for n in found), found

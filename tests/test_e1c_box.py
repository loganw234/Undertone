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


def test_e1c_the_box_script_bounds_each_run_goes_on_after_a_refused_one_and_ends_as_written():
    """Read, not run: no test may start that shell. Each run of run_piece sits under `timeout 900`; nothing stops the
    script after a run that ends refused or failed (no `set -e`, no exit but the one before any run, nothing after
    the loop's call); and its last lines, the flip's comparison by hash and the end, are as written, the flip's
    comparison saying NOT COMPARED, never SAME, when either hash is missing."""
    text = script_text()
    lines = text.split("\n")
    code = [line for line in lines if line.strip() and not line.lstrip().startswith("#")]
    runs = [line for line in code if "python3 hw/e0c/run_piece.py" in line]
    assert len(runs) == 1 and "timeout 900 python3 hw/e0c/run_piece.py" in runs[0]
    assert "set -u" in code and not any(line.strip().startswith("set -e") or "set -o errexit" in line for line in code)
    exits = [line.strip() for line in code if "exit" in line.replace("exit $?", "").replace("exit %s", "")]
    assert exits == ['mkdir -p "$R"; cd "$R" || exit 1'], exits
    loop = code.index("while read -r line; do")
    assert code[loop:loop + 4] == ["while read -r line; do", '    [ -n "$line" ] || continue', "    one $line",
                                   'done < "$CASES/order.txt"']
    tail = code[code.index('flip=$(grep -E \'^flip-\' "$CASES/order.txt" | cut -d\' \' -f1)'):]
    assert tail[:6] == [
        'flip=$(grep -E \'^flip-\' "$CASES/order.txt" | cut -d\' \' -f1)',
        'against=$(field "$CASES/expect/$flip.json" against 2>/dev/null)',
        'want=$(field "$CASES/expect/$against.json" sha256 2>/dev/null)',
        'got=$(sha256sum "$R/$flip/records.bin" 2>/dev/null | cut -d\' \' -f1)',
        'if [ -z "$got" ] || [ -z "$want" ]; then echo "$flip NOT COMPARED: its records or the expectation of $against '
        'are missing";',
        'elif [ "$got" = "$want" ]; then echo "$flip the SAME as $against\'s: the flip was NOT seen";']
    assert tail[6] == 'else echo "$flip differs from $against\'s, as it must"; fi'
    assert tail[-1] == 'echo "== $(date \'+%H:%M:%S\') end"'
    assert sum("SHA256SUMS" in line for line in tail) == 1 and any("health after" in line for line in tail)


def test_e1c_the_box_check_sees_a_planted_import():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        planted = os.path.join(d, "planted.py")
        with open(planted, "w", encoding="utf-8") as f:
            f.write("import json\nfrom hw.e1c import e1c\nimport learn\n")
        found = set(T0.box_findings([planted]))
    assert {"test_lrn_a_e1", "numpy"} <= found and any(n.startswith("hw.e1c") or n.startswith("learn") for n in found), found

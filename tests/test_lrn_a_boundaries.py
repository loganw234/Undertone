"""Where the learner sits: what `learn/` may import, and what may import it.

The `independence` stage holds `model/` and `stats/` apart and knows nothing of a third package.
This file holds the third:

  1. `model/` and `stats/` each import, every file of them, with `learn` blocked.
  2. `learn/` imports, every file of it, with `stats` blocked: what judges the learner is not in it.
     The trainer and the refusals import with `model` and `spec` blocked too.
  3. Read as source: `learn/` imports only what is listed here; from the model it takes three
     names, `weights.quantise`, `weights.pack` and `weights.unpack`; it reads no private name off
     anything but `self`; it never names the pulse or the parts that make the stream; and it names
     no built-in that opens a file or runs text, and no reader of a file.

So `learn/` does not import the pulse, does not name it, and does not open the file it is kept in,
by any of the ways this test lists. That is a reading of names. It is not a wall, and it does not
show that the learner CANNOT look the pulse up.

The first control plants six faults, one at a time, in a copy, and each must be reported where it
is. The second plants eight ways to the pulse with no import of this project, the round's two
verifiers' among them. The first put a function into the trainer that opens spec/pulses/e0.toml
by path, and this test, as it then stood, passed. The second imported a numpy reader by name and
called it bare, and this test, as it stood after the first, passed again.

WHAT THIS CANNOT SEE (stated limits): what `independence` cannot see either. A module loaded by
path; a file copied in. And, because check 3 reads names against lists:
  - a file read through a function the lists do not name. They hold the built-in `open`, six of
    numpy's readers of text and binary files, and the methods `read`, `readline`, `readlines`,
    `read_text` and `read_bytes`. A name on the reader list is refused in three places: read off
    an object (`np.fromregex`), imported by name under its own name or another (`from numpy
    import load as l`), and written bare; and `from <anything> import *` is refused whole. A
    reader of ANOTHER name, in numpy or in a module the import list lets in, passes, however it
    is reached: numpy has more than six;
  - a name reached without being written, by a road the lists do not name, or through an object
    a caller hands in. `getattr`, `globals`, `vars`, `__builtins__`, `__dict__`, `__globals__`
    and `__getattribute__` are refused by name; that is a list too;
  - the pulse's samples typed in as numbers, or worked out by arithmetic.
And this is a test inside `model-tests`, not a stage of the gate with a planted copy of the tree.
"""
import ast
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

# The method of tools/_import_blocked.py, written again: import modules while some packages are blocked.
# One child Python for a tree, and the three import checks in it one after another. Between two
# checks every module of this project is dropped from sys.modules, so that the next check's
# imports go through the finder again and are not answered from what the last check loaded.
CHILD = """
import importlib, importlib.abc, os, sys
PROJECT = ("model", "stats", "learn", "spec")
blocked, current = [], [""]

class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        for other in blocked:
            if name == other or name.startswith(other + "."):
                raise ImportError("BLOCKED: importing %s ran an import of %s" % (current[0], name))
        return None

def modules_of(package):
    names = set()
    for dirpath, dirnames, files in os.walk(package):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for f in files:
            if f.endswith(".py"):
                parts = os.path.relpath(os.path.join(dirpath, f), ".")[:-3].replace(os.sep, "/").split("/")
                if parts[-1] == "__init__":
                    parts = parts[:-1]
                names.add(".".join(parts))
    return names

def check(label, names, block):
    for name in list(sys.modules):
        if name in PROJECT or name.split(".")[0] in PROJECT:
            del sys.modules[name]
    blocked[:] = block
    for n in sorted(names):
        current[0] = n
        try:
            importlib.import_module(n)
        except ImportError as e:
            print("FOUND %s %s %s" % (label, n, "CROSS" if "BLOCKED" in str(e) else "IMPORT-ERROR"))
        except Exception as e:
            print("FOUND %s %s IMPORT-ERROR" % (label, n))
    print("MODULES %s %d" % (label, len(names)))

sys.meta_path.insert(0, Block())
sys.path.insert(0, ".")
check("imports-learn", modules_of("model") | modules_of("stats"), ["learn"])
check("trainer-imports-the-project", {"learn.errors", "learn.trainer"}, ["model", "spec", "stats"])
check("learn-imports-stats", modules_of("learn"), ["stats"])
"""

# What each file of learn/ may import: the first name of the module, and from it only these.
MAY_IMPORT = {
    "learn/__init__.py": {},
    "learn/errors.py": {},
    "learn/trainer.py": {"fractions": {"Fraction"}, "numpy": None, "learn.errors": {"LearnRefusal"}},
    "learn/handover.py": {"spec": {"constants"}, "model": {"weights"}, "learn.errors": {"LearnRefusal"}},
}
FROM_THE_MODEL = {"quantise", "pack", "unpack"}
NEVER_NAMED = {"PULSES", "PULSE_IDS", "scaled_pulse", "matched_filter", "inject", "source", "detector", "run"}
# The pulse is also a data file, spec/pulses/e0.toml, and reading a file needs no import at all. So
# nothing in learn/ may name a built-in that opens a file or runs text, or one that reaches a name by
# a string; and nothing may call a reader by these names off anything, numpy among them.
NO_BUILTIN = {"open", "exec", "eval", "compile", "__import__", "__builtins__", "globals", "vars", "getattr"}
NO_READER = {"open", "load", "loadtxt", "genfromtxt", "fromfile", "fromregex", "memmap",
             "read", "readline", "readlines", "read_text", "read_bytes",
             "__dict__", "__globals__", "__builtins__", "__getattribute__"}


def blocked_imports(root):
    """The three import checks on a tree, in one child Python started by this interpreter's own path.

    Returns (findings, counts): a set of (check, module, kind), and how many modules each check imported.
    """
    p = subprocess.run([sys.executable, "-c", CHILD], cwd=root, capture_output=True, text=True, env=ENV)
    rows = [line.split() for line in p.stdout.splitlines()]
    counts = {row[1]: int(row[2]) for row in rows if row[:1] == ["MODULES"]}
    assert p.returncode == 0 and len(counts) == 3, (p.stdout + p.stderr)[-600:]
    return {(row[1], row[2], row[3]) for row in rows if row[:1] == ["FOUND"]}, counts


def source_findings(root):
    """What the source of learn/ does that it may not: a set of (file, what)."""
    findings = set()
    folder = os.path.join(root, "learn")
    for dirpath, dirnames, files in os.walk(folder):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for f in sorted(files):
            if not f.endswith(".py"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/")
            with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            if rel not in MAY_IMPORT:
                findings.add((rel, "a file this test has no import list for"))
            allowed = MAY_IMPORT.get(rel, {})
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name not in allowed or allowed[alias.name] is not None:
                            findings.add((rel, "imports %s" % alias.name))
                        if set(alias.name.split(".")) & NEVER_NAMED or (alias.asname or "") in NEVER_NAMED:
                            findings.add((rel, "names %s" % alias.name))
                elif isinstance(node, ast.ImportFrom):
                    module = "." * node.level + (node.module or "")
                    for alias in node.names:
                        if module not in allowed or (allowed[module] is not None and alias.name not in allowed[module]):
                            findings.add((rel, "imports %s from %s" % (alias.name, module)))
                        if alias.name in NEVER_NAMED or (alias.asname or "") in NEVER_NAMED:
                            findings.add((rel, "names %s" % alias.name))
                        # A reader brought in by name is then called bare, or under another name, and no
                        # attribute is ever read: so the import itself is refused, and a star import whole.
                        if alias.name in NO_READER:
                            findings.add((rel, "imports the reader %s from %s" % (alias.name, module)))
                        if alias.name == "*":
                            findings.add((rel, "imports everything from %s" % module))
                    if set(module.split(".")) & NEVER_NAMED:
                        findings.add((rel, "names %s" % module))
                elif isinstance(node, ast.Attribute):
                    owner = node.value.id if isinstance(node.value, ast.Name) else None
                    if owner == "weights" and node.attr not in FROM_THE_MODEL:
                        findings.add((rel, "reads weights.%s" % node.attr))
                    private = node.attr.startswith("_") and not (node.attr.startswith("__") and node.attr.endswith("__"))
                    if private and owner != "self":
                        findings.add((rel, "reads the private name %s" % node.attr))
                    if node.attr in NEVER_NAMED:
                        findings.add((rel, "names %s" % node.attr))
                    if node.attr in NO_READER:
                        findings.add((rel, "names the reader %s" % node.attr))
                elif isinstance(node, ast.Name) and node.id in NEVER_NAMED:
                    findings.add((rel, "names %s" % node.id))
                elif isinstance(node, ast.Name) and node.id in NO_BUILTIN:
                    findings.add((rel, "names the built-in %s" % node.id))
                elif isinstance(node, ast.Name) and node.id in NO_READER:
                    findings.add((rel, "names the reader %s" % node.id))
                elif isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in NEVER_NAMED:
                    findings.add((rel, "names %s" % node.name))
    return findings


def everything(root):
    """Every finding of the three checks on a tree: a set of (check, where, what)."""
    found, counts = blocked_imports(root)
    assert counts["imports-learn"] >= 15 and counts["learn-imports-stats"] >= 4 and counts["trainer-imports-the-project"] == 2, \
        "the walk found too few modules to mean anything: %r" % (counts,)
    return found | {("source", rel, what) for rel, what in source_findings(root)}


def test_lrn_a_boundaries_the_learner_sits_where_the_design_says():
    assert everything(ROOT) == set()
    # the lists this test holds the source to are about files that exist
    assert sorted(MAY_IMPORT) == sorted("learn/" + f for f in os.listdir(os.path.join(ROOT, "learn")) if f.endswith(".py"))


def test_lrn_a_boundaries_no_file_of_the_model_or_the_statistics_names_the_learner():
    """A second way, by reading: no import statement under model/ or stats/ names `learn`."""
    for package in ("model", "stats"):
        seen = 0
        for dirpath, _dirs, files in os.walk(os.path.join(ROOT, package)):
            for f in files:
                if f.endswith(".py"):
                    seen += 1
                    with open(os.path.join(dirpath, f), encoding="utf-8") as fh:
                        tree = ast.parse(fh.read())
                    for node in ast.walk(tree):
                        names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                            [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                        assert not [n for n in names if n == "learn" or n.startswith("learn.")], (package, f)
        assert seen >= 5


def test_lrn_a_boundaries_control__six_planted_faults_are_each_reported_where_they_are(tmp_path):
    def copy():
        dst = tmp_path / ("copy%d" % len(os.listdir(tmp_path)))
        for package in ("model", "stats", "learn", "spec"):
            shutil.copytree(os.path.join(ROOT, package), dst / package, ignore=shutil.ignore_patterns("__pycache__"))
        return dst

    def add(root, name, text, mode):
        with open(os.path.join(root, name), mode, encoding="utf-8", newline="") as f:
            f.write(text)

    plants = (
        ("model/ imports learn", "model/planted.py", "import learn\n", "w",
         {("imports-learn", "model.planted", "CROSS")}),
        ("stats/ imports learn", "stats/planted.py", "from learn import trainer\n", "w",
         {("imports-learn", "stats.planted", "CROSS")}),
        ("learn/ imports stats", "learn/planted.py", "import stats\n", "w",
         {("learn-imports-stats", "learn.planted", "CROSS"), ("source", "learn/planted.py", "imports stats"),
          ("source", "learn/planted.py", "a file this test has no import list for")}),
        ("the trainer imports the model", "learn/trainer.py", "\nfrom model import weights\n", "a",
         {("trainer-imports-the-project", "learn.trainer", "CROSS"),
          ("source", "learn/trainer.py", "imports weights from model")}),
        ("the hand-over reads a private name of the model's", "learn/handover.py",
         "\n\ndef planted(v):\n    return weights._exact(v)\n", "a",
         {("source", "learn/handover.py", "reads weights._exact"), ("source", "learn/handover.py", "reads the private name _exact")}),
        ("the trainer names the pulse", "learn/trainer.py", "\n\ndef planted(C):\n    return C.PULSES\n", "a",
         {("source", "learn/trainer.py", "names PULSES")}),
    )
    assert len(plants) == 6
    assert everything(str(copy())) == set(), "a copy with nothing planted is clean"
    for what, name, text, mode, want in plants:
        root = copy()
        add(str(root), name, text, mode)
        got = everything(str(root))
        print("CONTROL boundaries, %s: reported %s" % (what, sorted(got)))
        assert got == want, what


def test_lrn_a_boundaries_control__the_pulse_reached_with_no_import_of_this_project_is_reported(tmp_path):
    """Eight ways to the pulse that need no import statement naming this project, each planted alone.

    The first is the round's verifier's (VLRNA, 2026-11-23): a function in the trainer that opens the
    pulse's own file by path. With that function planted, this file's tests passed, 3 of 3, as they
    then stood. The last three are its second verifier's kind: a numpy reader imported BY NAME and
    called bare, which the check, as it stood after the first, did not see, because it looked for
    a reader's name only where an attribute is read. The check reads names against lists; the
    docstring at the top says what the lists leave out."""
    T, H = "learn/trainer.py", "learn/handover.py"
    plants = (
        ("the pulse's file opened by path", T,
         "\n\ndef planted():\n    with open(\"spec/pulses/e0.toml\") as f:\n"
         "        return [int(v) for v in f.read().replace(\",\", \" \").split() if v.lstrip(\"-\").isdigit()]\n",
         {(T, "names the built-in open"), (T, "names the reader read")}),
        ("the pulse's file read by numpy", T,
         "\n\ndef planted():\n    return np.fromregex(\"spec/pulses/e0.toml\", \"(-?[0-9]+)\", [(\"v\", np.int64)])\n",
         {(T, "names the reader fromregex")}),
        ("an import run as text", T,
         "\n\ndef planted():\n    scope = {}\n    exec(\"from spec.constants import PULSES as p\", scope)\n    return scope[\"p\"]\n",
         {(T, "names the built-in exec")}),
        ("an import by a computed name", T,
         "\n\ndef planted():\n    return __import__(\"spec.\" + \"constants\").constants.__dict__[\"PUL\" + \"SES\"]\n",
         {(T, "names the built-in __import__"), (T, "names the reader __dict__")}),
        ("the pulse's name put together at run time", H,
         "\n\ndef planted():\n    return getattr(C, \"PUL\" + \"SES\")\n",
         {(H, "names the built-in getattr")}),
        # The second verifier's three: a reader brought in by name is called with no attribute read.
        ("a numpy reader imported by name and called bare", T,
         "\n\nfrom numpy import fromregex\n\n\ndef planted():\n    return fromregex(\"spec/pulses/e0.toml\", \"(-?[0-9]+)\", [(\"v\", \"i8\")])\n",
         {(T, "imports the reader fromregex from numpy"), (T, "names the reader fromregex")}),
        ("a numpy reader imported under another name", T,
         "\n\nfrom numpy import load as l\n\n\ndef planted():\n    return l(\"spec/pulses/e0.toml\")\n",
         {(T, "imports the reader load from numpy")}),
        ("everything imported from numpy and a reader called bare", T,
         "\n\nfrom numpy import *\n\n\ndef planted():\n    return loadtxt(\"spec/pulses/e0.toml\")\n",
         {(T, "imports everything from numpy"), (T, "names the reader loadtxt")}),
    )
    assert len(plants) == 8 and source_findings(ROOT) == set()
    for what, name, text, want in plants:
        root = tmp_path / ("copy%d" % len(os.listdir(tmp_path)))
        shutil.copytree(os.path.join(ROOT, "learn"), root / "learn", ignore=shutil.ignore_patterns("__pycache__"))
        assert source_findings(str(root)) == set(), "the copy is clean before the fault"
        with open(os.path.join(root, name), "a", encoding="utf-8", newline="") as f:
            f.write(text)
        got = source_findings(str(root))
        print("CONTROL boundaries, %s: reported %s" % (what, sorted(got)))
        assert got == want, what
    # and the lists are about names learn/ could otherwise use: each built-in on the list exists
    import builtins
    assert all(hasattr(builtins, name) or name == "__builtins__" for name in NO_BUILTIN)

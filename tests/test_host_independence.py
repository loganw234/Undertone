"""The host library is its own code, and runs on Python 3.10: what it imports, and how it is written.

WHAT THIS HOLDS, by reading each file of host/ as Python's own parser does:
  - From `model/` it imports `model.refusal` and nothing else, and nothing at all
    of `stats/`, `learn/`, `rtl/` or `tools/`: the words it writes are not made
    by the code the comparison runs (the brief's regression "a library that is
    the model's because it is the model").
  - No cocotb, numpy or asyncio anywhere in it; `ctypes` only in the XRT backend.
  - Every file parses under Python 3.10's grammar, and imports only standard
    modules that Python 3.10 has, from a list here. The files of `spec/` and
    `model/` it imports parse under 3.10's grammar too.

WHAT IT CANNOT SEE: a call to a function a standard module gained after 3.10;
an import made at run time (importlib, __import__, a name built from strings);
code copied from the model into the library, which reads as the library's own.

ITS CONTROL. Four planted sources, checked by the same function: one that
imports model.weights, one that imports cocotb, one in 3.11's grammar
(`except*`), and one that imports tomllib (3.11's): each is reported.
"""
import ast
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = os.path.join(ROOT, "host")

# Standard modules Python 3.10 has, that the library may use. A module not here is a finding until it is
# looked up and added: every one of these is in 3.10's library (BELIEVED from Python's documentation).
STANDARD_310 = {"argparse", "collections", "ctypes", "hashlib", "json", "os", "struct", "sys", "time"}
OURS = {"spec", "host"}
ALLOWED_FROM_MODEL = {"model.refusal"}
ONLY_IN = {"ctypes": {"backend_xrt.py"}}
NEVER = {"cocotb", "numpy", "asyncio", "stats", "learn", "rtl", "tools", "tomllib"}


def imported(tree):
    """Every module the source imports, as dotted names."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                out.append("." * node.level + (node.module or ""))
            elif node.module == "model":
                out += ["model." + a.name for a in node.names]
            else:
                out.append(node.module)
    return out


def findings(name, text):
    """What is wrong with one file of host/, as a list of sentences."""
    try:
        tree = ast.parse(text, filename=name, feature_version=(3, 10))
    except SyntaxError as e:
        return ["%s: not Python 3.10's grammar: %s" % (name, e.msg)]
    out = []
    for module in imported(tree):
        top = module.split(".")[0]
        if module.startswith("."):
            out.append("%s: a relative import, %s" % (name, module))
        elif top in NEVER:
            out.append("%s: imports %s" % (name, module))
        elif top == "model":
            if module not in ALLOWED_FROM_MODEL:
                out.append("%s: imports %s, of the model's code" % (name, module))
        elif top in OURS:
            pass
        elif top not in STANDARD_310:
            out.append("%s: imports %s, not on the list of 3.10's standard modules" % (name, module))
        elif top in ONLY_IN and name not in ONLY_IN[top]:
            out.append("%s: imports %s, which only %s may" % (name, module, sorted(ONLY_IN[top])))
    return out


def host_files():
    return sorted(f for f in os.listdir(HOST) if f.endswith(".py"))


def test_host_independence_imports_and_grammar():
    files = host_files()
    assert {"__init__.py", "ops.py", "blob.py", "library.py", "drive.py", "backend_xrt.py", "fake.py"} <= set(files)
    for name in files:
        with open(os.path.join(HOST, name), encoding="utf-8") as f:
            assert findings(name, f.read()) == [], name


def test_host_independence_what_it_imports_of_the_tree_parses_as_310():
    for rel in ("spec/__init__.py", "spec/constants.py", "model/__init__.py", "model/refusal.py"):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            ast.parse(f.read(), filename=rel, feature_version=(3, 10))


def test_host_independence_control_each_plant_is_reported():
    plants = {
        "imports the model's reader": "from model import weights\n",
        "imports the model's reader, dotted": "import model.weights\n",
        "imports cocotb": "import cocotb\n",
        "3.11's grammar": "try:\n    pass\nexcept* ValueError:\n    pass\n",
        "a module 3.10 has not": "import tomllib\n",
        "ctypes outside the backend": "import ctypes\n",
    }
    for what, text in plants.items():
        assert findings("library.py", text), what
    assert findings("library.py", "from model.refusal import Refusal\nimport struct\n") == []

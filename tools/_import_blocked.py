"""Import every module of one package while another package is blocked.

    python tools/_import_blocked.py <package> <blocked package>     (run from the tree's root)

Every .py file under the package's folder is imported, found by walking the
folder itself, so a module in a subfolder with no __init__.py is not missed.

Prints "CROSS <module>: ..." when importing that module ran an import of the
blocked package (the import statement may sit in a module it imports),
"IMPORT-ERROR <module>: ..." for one that failed some other way, and
"MODULES <n>" at the end. tools/check_build.py reads those lines.
"""
import importlib
import importlib.abc
import os
import sys

pkg, other = sys.argv[1], sys.argv[2]
current = [pkg]


class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == other or name.startswith(other + "."):
            raise ImportError("BLOCKED: importing %s ran an import of %s" % (current[0], name))
        return None


def modules(package):
    names = set()
    for dirpath, dirnames, files in os.walk(package):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for f in files:
            if f.endswith(".py"):
                parts = os.path.relpath(os.path.join(dirpath, f), ".")[:-3].replace("\\", "/").split("/")
                if parts[-1] == "__init__":
                    parts = parts[:-1]
                names.add(".".join(parts))
    return sorted(names)


sys.meta_path.insert(0, Block())
sys.path.insert(0, ".")
names = modules(pkg)
for n in names:
    current[0] = n
    try:
        importlib.import_module(n)
    except ImportError as e:
        print("%s %s: %s" % ("CROSS" if "BLOCKED" in str(e) else "IMPORT-ERROR", n, e))
    except Exception as e:  # a module that fails to import at all is a finding too
        print("IMPORT-ERROR %s: %s: %s" % (n, type(e).__name__, e))
print("MODULES %d" % len(names))

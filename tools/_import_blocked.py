"""Import every module of one package while another package is blocked.

    python tools/_import_blocked.py <package> <blocked package>     (run from the tree's root)

Prints "CROSS <module>: ..." for a module that tried to import the blocked
package, "IMPORT-ERROR <module>: ..." for one that failed some other way, and
"MODULES <n>" at the end. tools/check_build.py reads those lines.
"""
import importlib
import importlib.abc
import pkgutil
import sys

pkg, other = sys.argv[1], sys.argv[2]
current = [pkg]


class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name == other or name.startswith(other + "."):
            raise ImportError("BLOCKED: %s imports %s" % (current[0], name))
        return None


sys.meta_path.insert(0, Block())
sys.path.insert(0, ".")
top = importlib.import_module(pkg)
names = [pkg] + sorted(n for _f, n, _p in pkgutil.walk_packages(top.__path__, pkg + "."))
for n in names:
    current[0] = n
    try:
        importlib.import_module(n)
    except ImportError as e:
        print("%s %s: %s" % ("CROSS" if "BLOCKED" in str(e) else "IMPORT-ERROR", n, e))
    except Exception as e:  # a module that fails to import at all is a finding too
        print("IMPORT-ERROR %s: %s: %s" % (n, type(e).__name__, e))
print("MODULES %d" % len(names))

"""Reading committed records, and remembering what was read.

A `Reader` is rooted at a folder: the tree, or a copy of it. Every file it reads
is named by its path relative to that root, written with forward slashes, and
logged with the SHA-256 of its bytes. A figure's source lines are that log, so
they name exactly what the figure read.

One read is not of a file's bytes: `pulses()` reads `spec/constants.py`, takes
the value of its `PULSES` assignment by `ast.literal_eval`, and logs the SHA-256
of that value as canonical JSON (`canonical_json`). The lead's ruling of
2026-11-25 17:44: a change to the definition elsewhere does not make the pulses
figure stale; a change to a pulse does.

Field access goes through `field`, which refuses VIZ-RECORD-FIELD for a field
that is absent, of the wrong type, or not finite. A bool is not a number here.
"""
import ast
import hashlib
import json
import math
import os
import re

from viz.errors import VizRefusal

CONSTANTS = "spec/constants.py"


def canonical_json(value):
    """The text a hash of a value is taken over: sorted keys, no spaces, ASCII."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


class Reader:
    """Reads files under `root`, and logs (what, sha256) for each read, in order."""

    def __init__(self, root):
        self.root = root
        self.log = []

    def _bytes(self, rel):
        path = os.path.join(self.root, *rel.split("/"))
        if not os.path.isfile(path):
            raise VizRefusal("VIZ-RECORD-MISSING", rel)
        with open(path, "rb") as f:
            return f.read()

    def raw(self, rel):
        """The file's bytes, logged."""
        data = self._bytes(rel)
        self.log.append((rel, sha256_hex(data)))
        return data

    def glob(self, folder, pattern):
        """The files in `folder` whose names match `pattern` whole, ordered by its one
        group as an int. Refused VIZ-RECORD-MISSING when there is none."""
        path = os.path.join(self.root, *folder.split("/"))
        names = os.listdir(path) if os.path.isdir(path) else []
        found = []
        for name in names:
            m = re.fullmatch(pattern, name)
            if m:
                found.append((int(m.group(1)), "%s/%s" % (folder, name)))
        if not found:
            raise VizRefusal("VIZ-RECORD-MISSING", "no file in %s matches %s" % (folder, pattern))
        found.sort()
        return [rel for _, rel in found]

    def json(self, rel):
        data = self.raw(rel)
        try:
            return json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise VizRefusal("VIZ-RECORD-FIELD", "%s is not JSON: %s" % (rel, e))

    def text(self, rel):
        data = self.raw(rel)
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError as e:
            raise VizRefusal("VIZ-RECORD-FIELD", "%s is not UTF-8: %s" % (rel, e))

    def pulses(self):
        """`PULSES` from spec/constants.py: {name: tuple of ints}. Logs the value's hash."""
        data = self._bytes(CONSTANTS)
        try:
            tree = ast.parse(data.decode("utf-8"))
        except (UnicodeDecodeError, SyntaxError) as e:
            raise VizRefusal("VIZ-RECORD-FIELD", "%s does not parse: %s" % (CONSTANTS, e))
        found = [node.value for node in tree.body
                 if isinstance(node, ast.Assign) and len(node.targets) == 1
                 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "PULSES"]
        if len(found) != 1:
            raise VizRefusal("VIZ-RECORD-FIELD", "%s assigns PULSES %d times, not once"
                             % (CONSTANTS, len(found)))
        try:
            value = ast.literal_eval(found[0])
        except ValueError as e:
            raise VizRefusal("VIZ-RECORD-FIELD", "PULSES is not a literal: %s" % e)
        if not isinstance(value, dict) or not value:
            raise VizRefusal("VIZ-RECORD-FIELD", "PULSES is not a non-empty dict")
        for name, samples in value.items():
            if not isinstance(name, str) or not isinstance(samples, tuple) or not samples \
                    or not all(type(s) is int for s in samples):
                raise VizRefusal("VIZ-RECORD-FIELD", "PULSES[%r] is not a tuple of ints" % (name,))
        what = "%s, PULSES: sha256 of its value as canonical JSON" % CONSTANTS
        self.log.append((what, sha256_hex(canonical_json(value).encode("ascii"))))
        return value


def _is_number(v):
    return type(v) in (int, float) and (type(v) is int or math.isfinite(v))


KINDS = {
    "int": lambda v: type(v) is int,
    "number": _is_number,
    "str": lambda v: type(v) is str,
    "list": lambda v: type(v) is list,
    "dict": lambda v: type(v) is dict,
}


def field(obj, key, kind, where):
    """obj[key], refused VIZ-RECORD-FIELD unless it is there and of `kind`."""
    if type(obj) is not dict or key not in obj:
        raise VizRefusal("VIZ-RECORD-FIELD", "%s has no field %r" % (where, key))
    v = obj[key]
    if not KINDS[kind](v):
        raise VizRefusal("VIZ-RECORD-FIELD", "%s field %r is %r, not %s" % (where, key, v, kind))
    return v


def fraction_pair(obj, key, where):
    """A field written [numerator, denominator] of ints, the denominator positive."""
    v = field(obj, key, "list", where)
    if len(v) != 2 or not all(type(x) is int for x in v) or v[1] <= 0:
        raise VizRefusal("VIZ-RECORD-FIELD", "%s field %r is %r, not [int, positive int]"
                         % (where, key, v))
    return v[0], v[1]

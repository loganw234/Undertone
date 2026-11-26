"""Figures made from the project's committed records, as generated copies of them.

    python -m viz            write every figure into docs/figures/
    python -m viz --check    write nothing; name each figure that differs from
                             what the records make, exit 1 if any does

`build(root)` makes every figure of the registry (`viz.figures.FIGURES`) from
the records under `root` and returns [(file name, SVG text)]. `stale(root)`
compares that with docs/figures/ under the same root. The tests hold the
committed figures byte for byte to `build` of the tree, so a record changed
without its figure, or a figure edited by hand, fails the gate's first size.

Imports: the standard library, `stats/` for a theory curve, and nothing of
`model/`, `learn/`, `host/` or `rtl/` (held by tests/test_viz_writer.py).
What the figures show and cannot show is docs/figures/README.md.
"""
import os

from viz.errors import VizRefusal
from viz.figures import FIGURES
from viz.records import Reader

OUT = "docs/figures"


def build(root, reader=Reader):
    """[(name, text)] for every figure, in the registry's order, each from a reader of its own."""
    return [(name, fn(reader(root))) for name, fn in FIGURES]


def out_dir(root):
    return os.path.join(root, *OUT.split("/"))


def unknown(root):
    """The .svg files in docs/figures/ the registry does not make, sorted."""
    folder = out_dir(root)
    names = set(n for n, _ in FIGURES)
    if not os.path.isdir(folder):
        return []
    return sorted(n for n in os.listdir(folder) if n.lower().endswith(".svg") and n not in names)


def stale(root, reader=Reader):
    """The figures whose committed bytes differ from what the records make (or are missing)."""
    out = []
    for name, text in build(root, reader):
        path = os.path.join(out_dir(root), name)
        committed = None
        if os.path.isfile(path):
            with open(path, "rb") as f:
                committed = f.read()
        if committed != text.encode("ascii"):
            out.append(name)
    return out


def write(root, reader=Reader):
    """Write every figure; refuse, writing nothing, if docs/figures/ holds an unknown .svg."""
    extra = unknown(root)
    if extra:
        raise VizRefusal("VIZ-UNKNOWN-FIGURE", "%s holds %s, which no figure of the registry makes"
                         % (OUT, ", ".join(extra)))
    figures = build(root, reader)
    os.makedirs(out_dir(root), exist_ok=True)
    for name, text in figures:
        with open(os.path.join(out_dir(root), name), "wb") as f:
            f.write(text.encode("ascii"))
    return [name for name, _ in figures]

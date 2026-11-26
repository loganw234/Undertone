"""python -m viz [--check] [--root DIR]

Writes every figure into DIR/docs/figures/ (DIR is the tree this package sits
in unless given), or with --check writes nothing and names each stale figure.
Prints one line a figure. Exit 0 on success, 1 when --check finds a stale or
unknown figure, 2 on a refusal, which is printed "REFUSED <name>: <detail>".
"""
import argparse
import os
import sys

import viz
from viz.errors import VizRefusal

TREE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m viz", description="figures from the committed records")
    ap.add_argument("--check", action="store_true", help="write nothing; name each stale figure")
    ap.add_argument("--root", default=TREE, help="the tree to read and write (default: this one)")
    args = ap.parse_args(argv)
    try:
        if args.check:
            bad = viz.stale(args.root) + ["%s (not made by the registry)" % n for n in viz.unknown(args.root)]
            for name in bad:
                print("STALE %s/%s: run python -m viz and commit it with its records" % (viz.OUT, name))
            if bad:
                return 1
            print("OK figures: %d figure(s) equal what the records make" % len(viz.FIGURES))
            return 0
        for name in viz.write(args.root):
            print("wrote %s/%s" % (viz.OUT, name))
        return 0
    except VizRefusal as e:
        print("REFUSED %s: %s" % (e.name, e.detail))
        return 2


if __name__ == "__main__":
    sys.exit(main())

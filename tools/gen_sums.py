#!/usr/bin/env python3
"""Write, or check, a SHA256SUMS list in each folder under vectors/.

    python tools/gen_sums.py            write vectors/<folder>/SHA256SUMS
    python tools/gen_sums.py --check    exit 1, naming each file that differs
    --root DIR                          work on another copy of the tree

One list per folder, so two parcels never regenerate one file. A list holds
every file in its folder, subfolders included, but itself: "<sha256>  <path>",
sorted, LF. Line endings are folded before hashing, so a checkout that
rewrote them does not look like a changed vector.

This guards a frozen vector against change. It says nothing about whether the
vector's expected answer is right: that is the rule that a known answer is
worked by hand or by independent code, never by the model it then judges.
"""
import hashlib
import os
import sys

NAME = "SHA256SUMS"


def folders(root):
    base = os.path.join(root, "vectors")
    if not os.path.isdir(base):
        return []
    return sorted(d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d)))


def listing(root, folder):
    base = os.path.join(root, "vectors", folder)
    rows = []
    for dirpath, _dirs, files in os.walk(base):
        for f in files:
            full = os.path.join(dirpath, f)
            rel = os.path.relpath(full, base).replace("\\", "/")
            if rel == NAME:
                continue
            with open(full, "rb") as fh:
                digest = hashlib.sha256(fh.read().replace(b"\r\n", b"\n")).hexdigest()
            rows.append((rel, digest))
    return "".join("%s  %s\n" % (d, r) for r, d in sorted(rows)), len(rows)


def check(root):
    """Returns (findings, folders checked, files checked)."""
    findings, nfiles = [], 0
    names = folders(root)
    for folder in names:
        want, n = listing(root, folder)
        nfiles += n
        path = os.path.join(root, "vectors", folder, NAME)
        rel = "vectors/%s/%s" % (folder, NAME)
        if n == 0:
            findings.append((rel, "the folder holds no vector"))
            continue
        if not os.path.exists(path):
            findings.append((rel, "is missing"))
            continue
        with open(path, "rb") as f:
            have = f.read().decode("utf-8").replace("\r\n", "\n")
        if have != want:
            before = len(findings)
            old = dict(l.split("  ", 1)[::-1] for l in have.split("\n") if "  " in l)
            new = dict(l.split("  ", 1)[::-1] for l in want.split("\n") if "  " in l)
            for name in sorted(set(old) | set(new)):
                if old.get(name) != new.get(name):
                    findings.append(("vectors/%s/%s" % (folder, name),
                                     "does not match its line in %s" % NAME
                                     if name in old and name in new else
                                     "is not in %s" % NAME if name in new else
                                     "is in %s and not in the folder" % NAME))
            if len(findings) == before:
                # Same files, same digests, different text: a repeated line, a comment, a missing newline.
                findings.append((rel, "is not exactly what the generator writes"))
    return findings, len(names), nfiles


def main(argv):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if "--root" in argv:
        root = os.path.abspath(argv[argv.index("--root") + 1])
    if "--check" in argv:
        findings, _nf, _n = check(root)
        for name, what in findings:
            print("FINDING generated %s: %s" % (name, what))
        return 1 if findings else 0
    for folder in folders(root):
        text, n = listing(root, folder)
        with open(os.path.join(root, "vectors", folder, NAME), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("wrote vectors/%s/%s (%d files)" % (folder, NAME, n))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

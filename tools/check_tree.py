#!/usr/bin/env python3
"""The checks behind verify/run.sh. Standard library only.

    check_tree.py links  --root DIR    every relative markdown link resolves
    check_tree.py paths  --root DIR    no personal path in a committable file
    check_tree.py claims --root DIR    every claims-register row has a basis
    check_tree.py eol    --root DIR    no CR byte in a committable text file
    check_tree.py control KIND --scratch DIR
                                       plant faults of KIND in a throwaway
                                       repository and run the same check on it

A check prints one line "OK <kind>: <counts>" and exits 0, or prints each
finding as "FINDING <kind> <file>:<line>: <what>" and exits 1. Anything it
cannot do exactly is REFUSED by name with exit 2; it never falls back to a
looser method. verify/run.sh asserts on the OK line, not on the exit code.

`control` exits 1 only when EVERY planted fault was reported on its own line
and nothing else was, and then prints "CONTROL-DETECTED <kind> ...". Every
other outcome, a refusal included, exits 0, so the runner reports a control
that did not fail.

WHAT THESE CHECKS CANNOT SEE (stated limits):
  links   reads inline links, "](target)", in .md and .markdown files,
          outside code fences and code spans. It does not check anchors,
          reference-style links, external URLs, or links in any other kind
          of file. A target must be a committable file, spelled in the case
          git lists it in, or a folder that holds one. Anything shaped like
          "letters then a colon" is taken for an external URL and skipped,
          so a broken "file.md:12" is not seen. A target on the line after
          its "](" is not read.
  paths   reads text for the spellings listed in PERSONAL. A personal detail
          spelled another way is not seen: "~/", an environment variable, a
          percent-encoded path, another person's home, another private
          network range, a Unix home written with backslashes. A file that
          is not UTF-8 text (UTF-16, say) is read as UTF-8, and a path in it
          is not seen. It reads the working tree, not the history: a path
          one commit adds and a later one removes is not seen here.
          The session scratch folder's own name is deliberately NOT a
          spelling: as a bare word it flagged 3 lines on its first run
          (2026-11-21), all 3 of them the survey naming an accelerator's
          memory of the same name. Zero real hits, so it was removed. A real
          path to that folder still trips windows-home and app-data.
  claims  checks rows of tables whose header has a column named exactly
          "basis", in markdown under docs/, outside code fences. A claim
          made in prose, or in a table with another header, is not checked.
          It checks that a basis is one of the labels, not that it is the
          right one. Only an empty source is refused: "-" or "none" passes.
          A falsifier is refused only when it is exactly one of
          NOT_A_FALSIFIER: "unknown" passes. A table inside a blockquote, or
          written without leading pipes, is not read.
  eol     skips a file that holds a NUL byte, as binary.
  control plants the shapes listed in plants() and no others. A check broken
          for a shape that is not planted passes its control. A change that
          removes a spelling from PERSONAL removes its plant with it.
          By class, nothing is planted: late in a long file, late in a long
          table, past a file's first kilobyte, in a percent-encoded link
          target, or in another encoding. The verifier's four mutants of
          2026-11-21 broke one check in each of the first four places, and
          each control still reported CONTROL-DETECTED.
"""
import argparse
import os
import posixpath
import re
import subprocess
import sys
import tempfile
import urllib.parse

LABELS = ("MEASURED", "READ", "COMPUTED", "ESTIMATE", "BELIEVED", "SURVEY",
          "DECISION")
NOT_A_FALSIFIER = ("", "-", "--", "n/a", "na", "none", "tbd", "?")


def _p(*parts):
    # Patterns and samples are assembled from pieces so this file does not
    # contain the spellings it searches for, and so needs no exemption from
    # its own check.
    return "".join(parts)


# (kind, pattern, a sample line the control plants)
PERSONAL = [
    ("windows-home", re.compile(_p("[A-Za-z]:", r"[\\/]+", "Users", r"[\\/]"), re.I),
     _p("C:", "\\", "Users", "\\", "someone", "\\", "work")),
    ("msys-home", re.compile(_p("/c/", "Users/"), re.I),
     _p("/c/", "Users/", "someone/work")),
    ("unix-home", re.compile(_p("/home/", "logan"), re.I),
     _p("/home/", "logan", "/work")),
    ("mac-home", re.compile(_p("/Users/", "logan"), re.I),
     _p("/Users/", "logan", "/work")),
    ("app-data", re.compile(_p("App", "Data"), re.I),
     _p("the ", "App", "Data", " folder")),
    ("user-at-host", re.compile(_p("logan", "@"), re.I),
     _p("ssh ", "logan", "@", "box")),
    ("lan-address", re.compile(_p("192", r"\.", "168", r"\.")),
     _p("192", ".", "168", ".", "0", ".", "9")),
    ("owner-domain", re.compile(_p("improper", "aperture"), re.I),
     _p("mail at ", "improper", "aperture", " dot com")),
]


class Refusal(Exception):
    pass


def committable(root):
    """Paths git would commit from root: tracked, plus untracked not ignored.

    Refuses unless root is the top of its own repository: `git -C DIR` walks
    up to a parent repository when DIR has none, and would then answer about
    the wrong tree.
    """
    try:
        top = subprocess.run(["git", "-C", root, "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True)
    except OSError as e:
        raise Refusal("NO-GIT: cannot run git: %s" % e)
    if top.returncode != 0:
        raise Refusal("NOT-A-REPOSITORY: %s" % root)
    if not os.path.samefile(top.stdout.strip(), root):
        raise Refusal("NOT-THE-TOPLEVEL: %s is inside the repository at %s"
                      % (root, top.stdout.strip()))
    out = subprocess.run(["git", "-C", root, "-c", "core.quotepath=off", "ls-files",
                          "-co", "--exclude-standard", "-z"], capture_output=True)
    if out.returncode != 0:
        raise Refusal("LS-FILES-FAILED: %s" % out.stderr.decode("utf-8", "replace"))
    names = [n for n in out.stdout.decode("utf-8", "replace").split("\0") if n]
    return sorted(n for n in names if os.path.isfile(os.path.join(root, n)))


def read_bytes(root, name):
    with open(os.path.join(root, name), "rb") as f:
        return f.read()


def read_lines(root, name):
    return read_bytes(root, name).decode("utf-8", "replace").split("\n")


FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def prose_lines(lines, blank_spans=True):
    """([(number, text)], line of an unclosed fence or None).

    Lines inside a code fence are left out and, unless blank_spans is off,
    code spans are blanked. A
    fence opens on three or more backticks or tildes; a backtick fence whose
    line carries another backtick is a code span, not a fence. It closes on
    the same character, at least as long, with nothing after it.
    """
    out, fence, opened = [], None, None
    for i, line in enumerate(lines, 1):
        m = FENCE.match(line.rstrip("\r"))
        if fence is None:
            if m and not (m.group(1)[0] == "`" and "`" in m.group(2)):
                fence, opened = m.group(1), i
                continue
            if blank_spans:
                line = re.sub(r"`[^`]*`", lambda s: " " * len(s.group(0)), line)
            out.append((i, line))
        elif m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) \
                and not m.group(2).strip():
            fence, opened = None, None
    return out, opened


LINK = re.compile(r"\]\(\s*(<[^>\n]*>|[^)\s]+)(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")


def is_markdown(name):
    return name.lower().endswith((".md", ".markdown"))


def check_links(root):
    names = committable(root)
    listed = set(n.replace("\\", "/") for n in names)
    folders = set()
    for n in listed:
        while "/" in n:
            n = n.rsplit("/", 1)[0]
            folders.add(n)
    files = [n for n in names if is_markdown(n)]
    findings, count = [], 0
    for name in files:
        prose, unclosed = prose_lines(read_lines(root, name))
        if unclosed:
            findings.append((name, unclosed, "code fence is never closed; "
                             "everything after it is unread"))
        for i, text in prose:
            for m in LINK.finditer(text):
                target = m.group(1)
                if target.startswith("<") and target.endswith(">"):
                    target = target[1:-1]
                if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                    continue
                count += 1
                path = urllib.parse.unquote(target.split("#", 1)[0])
                here = posixpath.dirname(name.replace("\\", "/"))
                full = posixpath.normpath(posixpath.join(here, path))
                if full.startswith("../") or full == ".." or posixpath.isabs(full):
                    findings.append((name, i, "link points outside the repository: %s" % target))
                elif full != "." and full not in listed and full not in folders:
                    findings.append((name, i, "link target is not a committable file, "
                                     "in this spelling: %s" % target))
    ok = "%d relative links in %d markdown files, 0 broken" % (count, len(files))
    return findings, count, ok


def check_paths(root):
    files = committable(root)
    findings, nlines = [], 0
    for name in files:
        for i, line in enumerate(read_lines(root, name), 1):
            nlines += 1
            for kind, pat, _sample in PERSONAL:
                if pat.search(line):
                    findings.append((name, i, "personal path (%s)" % kind))
    ok = "%d lines in %d committable files, 0 personal paths" % (nlines, len(files))
    return findings, nlines, ok


def check_eol(root):
    files = committable(root)
    findings, count = [], 0
    for name in files:
        data = read_bytes(root, name)
        if b"\0" in data:
            continue
        count += 1
        if b"\r" in data:
            line = data[:data.index(b"\r")].count(b"\n") + 1
            findings.append((name, line, "CR byte (%d in the file); line endings are LF"
                             % data.count(b"\r")))
    ok = "%d committable text files, 0 with a CR byte" % count
    return findings, count, ok


def cells(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def check_claims(root):
    files = [n for n in committable(root)
             if is_markdown(n) and n.replace("\\", "/").startswith("docs/")]
    findings, rows, tables = [], 0, 0
    for name in files:
        header, body = None, 0
        # Code spans are kept here: a source cell is often nothing but one.
        prose, _unclosed = prose_lines(read_lines(root, name), blank_spans=False)
        for i, text in prose:
            if not text.lstrip().startswith("|"):
                header = None
                continue
            c = cells(text)
            if header is None:
                header, body = [h.lower() for h in c], 0
                if "basis" in header:
                    tables += 1
                continue
            body += 1
            dashes = all(re.fullmatch(r":?-+:?", x) for x in c)
            if body == 1 and dashes:
                continue
            if "basis" not in header:
                continue
            rows += 1
            if dashes:
                findings.append((name, i, "a row of dashes inside a register"))
                continue
            if len(c) != len(header):
                findings.append((name, i, "row has %d cells, header has %d"
                                 % (len(c), len(header))))
                continue
            basis = c[header.index("basis")]
            if basis not in LABELS:
                findings.append((name, i, "basis is not exactly one of %s: %r"
                                 % ("/".join(LABELS), basis)))
            for col in header:
                if col.startswith("source") and not c[header.index(col)]:
                    findings.append((name, i, "no source or command given"))
            if "falsified by" in header and \
                    c[header.index("falsified by")].lower() in NOT_A_FALSIFIER:
                findings.append((name, i, "no 'falsified by' given"))
    ok = "%d register rows in %d tables in %d files under docs/, 0 unlabelled" \
        % (rows, tables, len(files))
    return findings, rows, ok


CHECKS = {"links": check_links, "paths": check_paths, "claims": check_claims,
          "eol": check_eol}


def run(kind, root):
    """Returns (exit code, findings). Shared by the real stage and its control."""
    try:
        findings, count, ok = CHECKS[kind](root)
    except Refusal as e:
        print("REFUSED %s: %s" % (kind, e))
        return 2, []
    for name, line, what in findings:
        print("FINDING %s %s:%d: %s" % (kind, name, line, what))
    if findings:
        print("FAIL %s: %d finding(s)" % (kind, len(findings)))
        return 1, findings
    if count == 0:
        print("REFUSED %s: NOTHING-SELECTED: zero items checked is not a pass" % kind)
        return 2, []
    print("OK %s: %s" % (kind, ok))
    return 0, []


CLEAN = ("# clean\n\nA [link](other.md) and a ```span``` at a line's start:\n\n"
         "```inline``` code, then a [second link](other.md 'titled').\n\n"
         "~~~\n```\n[not a link](nowhere.md)\n~~~\n\n"
         "| claim | basis | source or command | falsified by |\n|---|---|---|---|\n"
         "| it holds | MEASURED | `make test` | a rerun |\n")
REG = "| claim | basis | source or command | falsified by |\n|---|---|---|---|\n"
GOOD = "| it holds | MEASURED | `make test` | a rerun |\n"


def plants(kind):
    """{file: text} and the set of (file, line) that must each be reported."""
    files = {"docs/clean.md": CLEAN, "docs/other.md": "# other\n",
             ".gitignore": "ignored.md\n", "ignored.md": "# on disk, not committable\n"}
    want = set()

    def add(name, lines, faulty):
        files[name] = "\n".join(lines) + "\n"
        for n in faulty:
            want.add((name, n))

    if kind == "links":
        add("docs/planted.md", [
            "# planted", "",
            "A [good](clean.md) link.",                       # 3
            "A [plain](no-such-file.md) broken link.",        # 4  fault
            "A [titled](gone.md 'a title') broken link.",     # 5  fault
            "A [spaced](<no such file.md>) broken link.",     # 6  fault
            "A link to an [ignored](../ignored.md) file.",    # 7  fault
            "A link in the wrong [case](CLEAN.md).",          # 8  fault
            "```inline``` then a [broken](after-span.md) one.",  # 9  fault
            "A [nested [text]](nested.md) broken link.",      # 10 fault
        ], [4, 5, 6, 7, 8, 9, 10])
        add("top.md", ["# top", "", "A [broken](docs/missing.md) link at the root."], [3])
        add("docs/fence.md", ["# fence", "", "```", "[hidden](nowhere.md)"], [3])
    elif kind == "paths":
        lines, faulty = ["# planted", ""], []
        for _kind, _pat, sample in PERSONAL:
            lines.append("Seen: " + sample)
            faulty.append(len(lines))
        add("docs/planted.md", lines, faulty)
        add("top.txt", ["a note", "Seen: " + PERSONAL[0][2].lower()], [2])
    elif kind == "claims":
        add("docs/planted.md", ["# planted", "", REG.rstrip("\n").split("\n")[0], "|---|---|---|---|",
            GOOD.rstrip("\n"),                                    # 5
            "| it is fast | probably | a guess | a rerun |",      # 6  fault
            "| it is ready | READY | a file | a rerun |",         # 7  fault
            "| it ran | MEASURED, probably not | x | a rerun |",  # 8  fault
            "| it ran | MEASURED |  | a rerun |",                 # 9  fault
            "| it holds | READ | a file | n/a |",                 # 10 fault
            "| - | - | - | - |",                                  # 11 fault
            GOOD.rstrip("\n"), GOOD.rstrip("\n"),                 # 12, 13
            "| late in the table | perhaps | a file | a rerun |",  # 14 fault
        ], [6, 7, 8, 9, 10, 11, 14])
        add("docs/deep/er/planted.md", ["# deep", "", REG.rstrip("\n").split("\n")[0],
            "|---|---|---|---|", "| nested | surely | a file | a rerun |"], [5])
    elif kind == "eol":
        files["docs/planted.md"] = "# planted\r\n\r\ncarriage returns here\r\n"
        want.add(("docs/planted.md", 1))
        files["top.sh"] = "#!/bin/sh\necho one\necho two\r\n"
        want.add(("top.sh", 3))
    return files, want


def control(kind, scratch):
    os.makedirs(scratch, exist_ok=True)
    root = tempfile.mkdtemp(prefix="plant-", dir=scratch)
    if subprocess.run(["git", "init", "-q", root]).returncode != 0:
        print("control %s: git init failed in %s" % (kind, root))
        return 0
    files, want = plants(kind)
    for name, body in files.items():
        full = os.path.join(root, name)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8", newline="") as f:
            f.write(body)
    print("control %s: planted %d fault(s) in %s" % (kind, len(want), root))
    rc, findings = run(kind, root)
    got = set((f[0].replace("\\", "/"), f[1]) for f in findings)
    missed, stray = sorted(want - got), sorted(got - want)
    if rc == 1 and not missed and not stray:
        print("CONTROL-DETECTED %s all %d planted fault(s), nothing else" % (kind, len(want)))
        return 1
    print("control %s: NOT detected as planted (rc=%d). missed: %s. reported but not planted: %s"
          % (kind, rc, missed or "none", stray or "none"))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("kind", choices=sorted(CHECKS) + ["control"])
    ap.add_argument("what", nargs="?", choices=sorted(CHECKS))
    ap.add_argument("--root")
    ap.add_argument("--scratch")
    a = ap.parse_args()
    if a.kind == "control":
        if not a.what or not a.scratch:
            ap.error("control needs a KIND and --scratch DIR")
        return control(a.what, os.path.abspath(a.scratch))
    if not a.root:
        ap.error("%s needs --root DIR" % a.kind)
    return run(a.kind, os.path.abspath(a.root))[0]


if __name__ == "__main__":
    sys.exit(main())

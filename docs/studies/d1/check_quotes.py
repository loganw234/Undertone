#!/usr/bin/env python3
"""Holds every quotation of studies D1 and D1b against the page it came from.

    python docs/studies/d1/check_quotes.py --saved DIR
    python docs/studies/d1/check_quotes.py --study-only

WHAT IT READS
  quotes.tsv, beside this file: the register row, the saved file, the URL
      and the quotation.
  ../D1-launch-data.md and ../D1b-first-look.md: the two studies. Their
      register rows must not share an id.
  ../../../PROVENANCE.md: the sources and their terms.
  DIR: the folder the pages and responses were saved under on the day they
      were read. They are not committed. Without them, --study-only runs the
      checks that need no page.

WHAT IT CHECKS, and prints a FINDING line for each failure
  1. A quotation has at most 25 words.
  2. It occurs, letter for letter, in the saved file. HTML tags are removed
     and entities decoded first, and all white space is ignored on both
     sides, because removing a tag leaves a space the reader does not see.
     (Not run under --study-only.)
  3. It occurs, letter for letter and with white space ignored, in the
     study's register row of that name.
  4. Every text between straight double quotes in a READ row of the study's
     sources register is a quotation listed in quotes.tsv for that row, and
     the row names that quotation's URL.
  5. Every text between straight double quotes on one line of PROVENANCE.md,
     at the repository's root, is a quotation listed in quotes.tsv; and a
     quotation listed for the row PV is in PROVENANCE.md.

WHAT IT CANNOT SEE
  - Whether a quotation supports the claim beside it. That is a reader's
    check, and the verifier's.
  - Whether the page still says today what the saved copy says.
  - A quotation written between other marks, or in prose outside the
    register.
  - A typographic quotation mark that a page uses in place of a straight
    one is compared as the character it is.
"""
import argparse
import html
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STUDIES = [os.path.join(os.path.dirname(HERE), "D1-launch-data.md"),
           os.path.join(os.path.dirname(HERE), "D1b-first-look.md")]
PROVENANCE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))),
                          "PROVENANCE.md")
MAX_WORDS = 25


# A byte-order mark, a zero-width space and a left-to-right mark: pages carry
# them where a reader sees nothing. Built from their numbers so that this
# file holds no invisible character.
INVISIBLE = "".join(chr(c) for c in (0xFEFF, 0x200B, 0x200E))


def squeeze(text):
    return re.sub("[" + chr(92) + "s" + INVISIBLE + "]+", "", text)


def text_of(path):
    raw = open(path, "rb").read().decode("utf-8", "replace")
    if path.lower().endswith((".html", ".htm")):
        raw = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", raw)
        raw = re.sub(r"(?s)<!--.*?-->", " ", raw)
        raw = re.sub(r"(?s)<[^>]+>", " ", raw)
        raw = html.unescape(raw)
    return raw


def read_quotes():
    rows = []
    with open(os.path.join(HERE, "quotes.tsv"), encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if line.startswith("#") or not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 4:
                raise SystemExit("REFUSED BAD-LINE quotes.tsv:%d: %d fields" % (n, len(parts)))
            rows.append(tuple(parts) + (n,))
    return rows


def register_rows():
    """{row id: (file name and line number, basis, whole line)} for the register
    tables of both studies. A row id used twice is refused: a quotation is
    tied to its row by that id."""
    rows = {}
    for path in STUDIES:
        if not os.path.isfile(path):
            continue
        name, header = os.path.basename(path), None
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                if not line.lstrip().startswith("|"):
                    header = None
                    continue
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if header is None:
                    header = [c.lower() for c in cells]
                    continue
                if "basis" not in header or all(re.fullmatch(r":?-+:?", c) for c in cells):
                    continue
                if len(cells) != len(header):
                    continue
                if cells[0] in rows:
                    raise SystemExit("REFUSED ROW-ID-TWICE: %s in %s and at %s"
                                     % (cells[0], rows[cells[0]][0], name))
                rows[cells[0]] = ("%s:%d" % (name, n), cells[header.index("basis")], line)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--saved", help="folder holding pages/ and availability/")
    ap.add_argument("--study-only", action="store_true")
    a = ap.parse_args()
    if not a.saved and not a.study_only:
        ap.error("give --saved DIR, or --study-only")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    quotes, rows, findings, cache = read_quotes(), register_rows(), [], {}
    with open(PROVENANCE, encoding="utf-8") as f:
        provenance_lines = f.read().split("\n")
    provenance = squeeze("\n".join(provenance_lines))
    every = set(squeeze(q[3]) for q in quotes)
    for n, line in enumerate(provenance_lines, 1):
        for found in re.findall(r'"([^"]+)"', line):
            if squeeze(found) not in every:
                findings.append("PROVENANCE.md:%d: quotes text that quotes.tsv does not "
                                "list: %r" % (n, found))
    by_row = {}
    for rid, name, url, quote, n in quotes:
        by_row.setdefault(rid, []).append((quote, url))
        words = len(quote.split())
        if words > MAX_WORDS:
            findings.append("quotes.tsv:%d: %d words, more than %d" % (n, words, MAX_WORDS))
        if a.saved:
            path = os.path.join(a.saved, *name.split("/"))
            if not os.path.isfile(path):
                findings.append("quotes.tsv:%d: saved file is missing: %s" % (n, name))
            else:
                if path not in cache:
                    cache[path] = squeeze(text_of(path))
                if squeeze(quote) not in cache[path]:
                    findings.append("quotes.tsv:%d: not in %s: %r" % (n, name, quote))
        if rid == "PV":
            if squeeze(quote) not in provenance:
                findings.append("quotes.tsv:%d: PROVENANCE.md does not carry: %r" % (n, quote))
        elif rid not in rows:
            findings.append("quotes.tsv:%d: the study has no register row %s" % (n, rid))
        elif squeeze(quote) not in squeeze(rows[rid][2]):
            findings.append("quotes.tsv:%d: row %s of the study does not carry: %r"
                            % (n, rid, quote))
        elif url not in rows[rid][2]:
            findings.append("quotes.tsv:%d: row %s of the study does not name %s"
                            % (n, rid, url))
    read_rows = 0
    for rid, (n, basis, line) in rows.items():
        if basis != "READ":
            continue
        read_rows += 1
        listed = [squeeze(q) for q, _u in by_row.get(rid, [])]
        for found in re.findall(r'"([^"]+)"', line):
            if squeeze(found) not in listed:
                findings.append("%s: row %s quotes text that quotes.tsv "
                                "does not list: %r" % (n, rid, found))
        if not by_row.get(rid):
            findings.append("%s: READ row %s has no quotation in quotes.tsv" % (n, rid))
    for f in findings:
        print("FINDING quotes %s" % f)
    if findings:
        print("FAIL quotes: %d finding(s)" % len(findings))
        return 1
    if not quotes:
        print("REFUSED quotes: NOTHING-SELECTED")
        return 2
    print("OK quotes: %d quotations for %d READ rows, %s, 0 findings"
          % (len(quotes), read_rows,
             "each held against its saved file" if a.saved else "saved files NOT checked"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

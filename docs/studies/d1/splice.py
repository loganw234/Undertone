#!/usr/bin/env python3
"""Writes the generated tables into studies D1 and D1b, between their markers.

    python docs/studies/d1/splice.py --responses DIR            D1's tables
    python docs/studies/d1/splice.py --data DIR                 D1b's tables
    python docs/studies/d1/splice.py --responses DIR --data DIR --check
                                    change nothing; fail if a table in either
                                    study differs from what the scripts print

With --responses it runs stations.py twice and download_list.py once, and
replaces three blocks of ../D1-launch-data.md:

    <!-- d1:stations:today:begin --> ... <!-- d1:stations:today:end -->
        every site, channel epochs open on the day of the study
    <!-- d1:stations:2021:begin --> ... <!-- d1:stations:2021:end -->
        Vandenberg only, channel epochs open on 2021-09-14
    <!-- d1:download:begin --> ... <!-- d1:download:end -->
        the proposed waveform requests

With --data it runs firstlook.py, secondlook.py, mseed.py and catalogue.py
on the fetched files, reads manifest.tsv beside this file, and replaces five
blocks of ../D1b-first-look.md: d1b:manifest, d1b:records, d1b:catalogue,
d1b:firstlook and d1b:secondlook.

--unhold PREFIX is passed on to stations.py. It was how EarthScope's rows
were to be added; since the owner allowed that service on 2026-11-23 its
answers are marked "used" in queries.tsv and the option has nothing to do.

It makes no request. It reads what those scripts read, and the two studies.
It cannot see whether the prose around a block still agrees with the block.
"""
import argparse
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STUDY = os.path.join(os.path.dirname(HERE), "D1-launch-data.md")
STUDY_B = os.path.join(os.path.dirname(HERE), "D1b-first-look.md")


def run(script, args):
    r = subprocess.run([sys.executable, os.path.join(HERE, script)] + args,
                       capture_output=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr.decode("utf-8", "replace"))
        raise SystemExit("REFUSED SCRIPT-FAILED: %s %s" % (script, " ".join(args)))
    return r.stdout.decode("utf-8").replace("\r\n", "\n")


def put(text, tag, body):
    begin = "<!-- %s:begin -->" % tag
    end = "<!-- %s:end -->" % tag
    if text.count(begin) != 1 or text.count(end) != 1:
        raise SystemExit("REFUSED NO-MARKER: %s" % tag)
    head, rest = text.split(begin)
    _old, tail = rest.split(end)
    return head + begin + "\n\n" + body.strip("\n") + "\n\n" + end + tail


def manifest_table():
    rows, total, files = [], 0, 0
    with open(os.path.join(HERE, "manifest.tsv"), encoding="utf-8") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            name, _url, when, status, size, digest = line.rstrip("\n").split("\t")
            rows.append("| %s | %s | %s | %s | %s |" % (
                name, when, status, size, digest[:16] if digest != "-" else "no file"))
            total += int(size)
            files += 1 if status == "200" else 0
    return ("| file | fetched, UTC | HTTP status | bytes | SHA-256, first 16 hex digits |\n"
            "|---|---|---|---|---|\n" + "\n".join(rows) + "\n\n"
            "%d requests; %d answered with a file; %d bytes in all."
            % (len(rows), files, total))


def apply(path, blocks, check):
    with open(path, encoding="utf-8", newline="") as f:
        old = f.read()
    new = old
    for tag, body in blocks:
        new = put(new, tag, body)
    name = os.path.basename(path)
    if check:
        if new != old:
            print("FAIL splice: %s: a generated table differs from what the scripts print"
                  % name)
            return 1
        print("OK splice: %s: %d blocks equal what the scripts print" % (name, len(blocks)))
        return 0
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    print("OK splice: %s: %d blocks written (%s lines)"
          % (name, len(blocks), ", ".join(str(b.count("\n")) for _t, b in blocks)))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--responses", help="folder of saved station-service answers")
    ap.add_argument("--data", help="folder of fetched files")
    ap.add_argument("--unhold", action="append", default=[])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if not a.responses and not a.data:
        ap.error("give --responses DIR, --data DIR, or both")
    rc = 0
    if a.responses:
        extra = []
        for u in a.unhold:
            extra += ["--unhold", u]
        rc |= apply(STUDY, [
            ("d1:stations:today", run("stations.py", ["--responses", a.responses] + extra)),
            ("d1:stations:2021", run("stations.py", ["--responses", a.responses, "--as-of",
                                                    "2021-09-14", "--site", "VSFB"] + extra)),
            ("d1:download", run("download_list.py", [])),
        ], a.check)
    if a.data:
        files = sorted(glob.glob(os.path.join(a.data, "*.mseed")))
        if not files:
            raise SystemExit("REFUSED NO-RECORDS in %s" % a.data)
        rc |= apply(STUDY_B, [
            ("d1b:manifest", manifest_table()),
            ("d1b:records", run("mseed.py", files)),
            ("d1b:catalogue", run("catalogue.py", [a.data])),
            ("d1b:firstlook", run("firstlook.py", [a.data])),
            ("d1b:secondlook", run("secondlook.py", [a.data])),
        ], a.check)
    return rc


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Writes the generated tables into study D1, between its markers.

    python docs/studies/d1/splice.py --responses DIR            the committed form
    python docs/studies/d1/splice.py --responses DIR --unhold es
                                    the form with EarthScope's rows, for the
                                    day the owner has accepted its terms
    python docs/studies/d1/splice.py --responses DIR --check    change nothing;
                                    fail if the study's tables differ from
                                    what the scripts print

It runs stations.py twice and download_list.py once, and replaces three
blocks of ../D1-launch-data.md:

    <!-- d1:stations:today:begin --> ... <!-- d1:stations:today:end -->
        every site, channel epochs open on the day of the study
    <!-- d1:stations:2021:begin --> ... <!-- d1:stations:2021:end -->
        Vandenberg only, channel epochs open on 2021-09-14
    <!-- d1:download:begin --> ... <!-- d1:download:end -->
        the proposed waveform requests

It makes no request. It reads what stations.py reads, and the study.
It cannot see whether the prose around a block still agrees with the block.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STUDY = os.path.join(os.path.dirname(HERE), "D1-launch-data.md")


def run(script, args):
    r = subprocess.run([sys.executable, os.path.join(HERE, script)] + args,
                       capture_output=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr.decode("utf-8", "replace"))
        raise SystemExit("REFUSED SCRIPT-FAILED: %s %s" % (script, " ".join(args)))
    return r.stdout.decode("utf-8").replace("\r\n", "\n")


def put(text, tag, body):
    begin = "<!-- d1:%s:begin -->" % tag
    end = "<!-- d1:%s:end -->" % tag
    if text.count(begin) != 1 or text.count(end) != 1:
        raise SystemExit("REFUSED NO-MARKER: %s" % tag)
    head, rest = text.split(begin)
    _old, tail = rest.split(end)
    return head + begin + "\n\n" + body.strip("\n") + "\n\n" + end + tail


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--responses", required=True)
    ap.add_argument("--unhold", action="append", default=[])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    extra = []
    for u in a.unhold:
        extra += ["--unhold", u]
    blocks = [
        ("stations:today", run("stations.py", ["--responses", a.responses] + extra)),
        ("stations:2021", run("stations.py", ["--responses", a.responses, "--as-of",
                                              "2021-09-14", "--site", "VSFB"] + extra)),
        ("download", run("download_list.py", [])),
    ]
    with open(STUDY, encoding="utf-8", newline="") as f:
        old = f.read()
    new = old
    for tag, body in blocks:
        new = put(new, tag, body)
    if a.check:
        if new != old:
            print("FAIL splice: the study's generated tables differ from what the scripts print")
            return 1
        print("OK splice: %d blocks equal what the scripts print" % len(blocks))
        return 0
    with open(STUDY, "w", encoding="utf-8", newline="\n") as f:
        f.write(new)
    print("OK splice: %d blocks written (%s lines)"
          % (len(blocks), ", ".join(str(b.count("\n")) for _t, b in blocks)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

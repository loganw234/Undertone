#!/usr/bin/env python3
"""Study D3's figures, each on a labelled line, from the committed files only.

    python docs/studies/d3/d3describe.py

It makes no request and opens no record. It reads launches.tsv, requests.tsv,
manifest.tsv, constants.json and scored-output.txt, and counts the output's
table of every window again, independently of the summary the scoring run
printed above it. The lines marked "chosen after looking" describe the output:
they were not fixed before the run, they are not tests, and they change no
headline.
"""
import json
import math
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import d3launches  # noqa: E402
import d3rule as rule  # noqa: E402
import d3score as score  # noqa: E402


def windows_of_output():
    """[(tag, station, kind, days, S or None, why)] from the output's table of every window."""
    rows, on = [], False
    for line in open(os.path.join(HERE, "scored-output.txt"), encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("| launch | station | window |"):
            on = True
            continue
        if not on or not line.startswith("| 20"):
            continue
        f = [c.strip() for c in line.split("|")[1:-1]]
        rows.append((f[0], f[1][3:], f[2], int(f[3]), None if f[4] == "-" else int(f[4]), f[7]))
    return rows


def binom(n, p):
    return [math.comb(n, x) * p ** x * (1 - p) ** (n - x) for x in range(n + 1)]


def main():
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    launches = rule.read_launches(os.path.join(HERE, "launches.tsv"))
    sets = [r for r in launches if r["side"] == rule.SETS]
    scored = [r for r in launches if r["side"] == rule.SCORED]
    print("D1 launches.tsv: %d on the constant-setting side (one of them, 2021-082, with no record), "
          "%d scored; control times %d and %d" % (
              len(sets), len(scored), sum(len(r["controls"]) for r in sets),
              sum(len(r["controls"]) for r in scored)))
    print("D2 the windows, seconds after T0: %s" % "; ".join(
        "CI.%s %.1f km %d to %d (%d s)" % (s, km, rule.window(s)[0], rule.window(s)[1],
                                       rule.window(s)[1] - rule.window(s)[0]) for s, km in rule.STATIONS))
    print("D3 the record spans, seconds from T0: %s" % "; ".join(
        "CI.%s launch %d to %d, control %d to %d" % ((s,) + d3launches.spans(s)["launch"]
                                                   + d3launches.spans(s)["control"])
        for s, _km in rule.STATIONS))
    req = [l for l in open(os.path.join(HERE, "requests.tsv"), encoding="utf-8") if not l.startswith("#")]
    man = [l.rstrip("\n").split("\t") for l in open(os.path.join(HERE, "manifest.tsv"), encoding="utf-8")
           if not l.startswith("#")]
    status = Counter((m[0].split(".")[1] if m[0].startswith("CI.") else "station service", m[3]) for m in man)
    times = sorted(m[2] for m in man)
    wave = [m for m in man if m[0].endswith(".mseed")]
    print("D4 requests.tsv: %d requests; manifest.tsv: %d lines, first %s, last %s; statuses %s; "
          "%d waveform files, %d bytes" % (
              len(req), len(man), times[0], times[-1],
              ", ".join("%s %s: %d" % (k[0], k[1], v) for k, v in sorted(status.items())),
              sum(1 for m in wave if m[3] == "200"), sum(int(m[4]) for m in wave)))
    for m in (times[0], times[-1]):
        t = datetime.strptime(m, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        print("D5 %s is %s local (UTC - 7 h)" % (m, (t - timedelta(hours=7)).strftime("%H:%M:%S")))
    with open(os.path.join(HERE, "constants.json"), encoding="utf-8") as f:
        c = json.load(f)
    print("D6 constants.json: M %s; set from records %s; from %s" % (
        ", ".join("CI.%s %d" % (s, c["M"][s]) for s, _k in rule.STATIONS),
        ", ".join("CI.%s %s" % (s, c["set_from_records"][s]) for s, _k in rule.STATIONS),
        ", ".join(c["launches"])))
    for s, _k in rule.STATIONS:
        a, b = c["S_launch"][s], c["S_control"][s]
        print("D7 CI.%s constant-setting: %d launch windows, S %d to %d; %d control windows, S %d to %d; "
              "launch windows at or above M %d; control windows at or above M %d" % (
                  s, len(a), min(a), max(a), len(b), min(b), max(b),
                  sum(1 for x in a if x >= c["M"][s]), sum(1 for x in b if x >= c["M"][s])))

    rows = windows_of_output()
    print("D8 the output's table of every window: %d rows" % len(rows))
    allp = {}
    for s, km in rule.STATIONS:
        m = c["M"][s]

        def count(kind):
            v = [r[4] for r in rows if r[1] == s and r[2] == kind and r[4] is not None]
            return len(v), sum(1 for x in v if x >= m), sum(1 for r in rows if r[1] == s and r[2] == kind
                                                            and r[4] is None)
        n_l, a, g_l = count("launch")
        n_c, b, g_c = count("control")
        n_w, a_w, _ = count("wrong")
        n_h, a_h, _ = count("shifted")
        p = rule.p_fisher(a, b, n_l, n_c)
        allp[s] = (a, n_l, b, n_c)
        print("D9 CI.%s, counted again: launch %d of %d, control %d of %d, p %.3g, needed %s; no record %d, %d; "
              "wrong %d of %d, p %.3g; hour early %d of %d, p %.3g" % (
                  s, a, n_l, b, n_c, p, rule.needed(b, n_l, n_c, score.LEVEL), g_l, g_c,
                  a_w, n_w, rule.p_fisher(a_w, b, n_w, n_c), a_h, n_h, rule.p_fisher(a_h, b, n_h, n_c)))
    gone = [r for r in rows if r[4] is None]
    print("D10 windows with no record: %s" % "; ".join(
        "%s CI.%s %s %+d: %s" % (r[0], r[1], r[2], r[3], r[5]) for r in gone))
    tot = [sum(allp[s][i] for s, _k in rule.STATIONS) for i in range(4)]
    print("D11 over the four: %d of %d launch windows hit, %d of %d control windows" % tuple(tot))
    other = [r for r in rows if r[2] in ("control", "wrong", "shifted") and r[4] is not None]
    print("D12 control, wrong and hour-early windows with a record: %d, of which %d hit" % (
        len(other), sum(1 for r in other if r[4] >= c["M"][r[1]])))

    # chosen after looking
    for s, _k in rule.STATIONS:
        m = c["M"][s]
        lw = [(r[0], r[4]) for r in rows if r[1] == s and r[2] == "launch" and r[4] is not None]
        cw = [r[4] for r in rows if r[1] == s and r[2] == "control" and r[4] is not None]
        ww = [r[4] for r in rows if r[1] == s and r[2] in ("wrong", "shifted") and r[4] is not None]
        miss = [t for t, v in lw if v < m]
        print("D13 chosen after looking, CI.%s: launch S %d to %d; the largest control S %d, the largest "
              "wrong or hour-early S %d; the launches that missed: %s" % (
                  s, min(v for _t, v in lw), max(v for _t, v in lw), max(cw), max(ww),
                  ", ".join("%s (S = %d)" % (t, v) for t, v in lw if v < m) or "none"))
        ok = []
        for mm in range(rule.M_FLOOR, rule.window(s)[1] - rule.window(s)[0] + 1):
            a = sum(1 for _t, v in lw if v >= mm)
            b = sum(1 for v in cw if v >= mm)
            a_w = sum(1 for r in rows if r[1] == s and r[2] == "wrong" and r[4] is not None and r[4] >= mm)
            a_h = sum(1 for r in rows if r[1] == s and r[2] == "shifted" and r[4] is not None and r[4] >= mm)
            n_w = sum(1 for r in rows if r[1] == s and r[2] == "wrong" and r[4] is not None)
            n_h = sum(1 for r in rows if r[1] == s and r[2] == "shifted" and r[4] is not None)
            seen = (rule.p_fisher(a, b, len(lw), len(cw)) <= score.LEVEL
                    and rule.p_fisher(a_w, b, n_w, len(cw)) > score.CONTROL_LEVEL
                    and rule.p_fisher(a_h, b, n_h, len(cw)) > score.CONTROL_LEVEL)
            ok.append((mm, seen))
        runs, start = [], None
        for mm, seen in ok + [(None, False)]:
            if seen and start is None:
                start = mm
            if not seen and start is not None:
                runs.append((start, prev))
                start = None
            prev = mm
        print("D14 chosen after looking, CI.%s: the values of M at which the reading would still be SEEN: %s" % (
            s, ", ".join("%d to %d" % r for r in runs) or "none"))
    by_tag = dict((r["tag"], r) for r in launches)
    for s, _k in rule.STATIONS:
        m = c["M"][s]
        months = Counter()
        hits = Counter()
        for r in rows:
            if r[1] == s and r[2] == "launch" and r[4] is not None:
                mo = by_tag[r[0]]["t0"].month
                half = "Nov to Mar" if mo in (11, 12, 1, 2, 3) else "Apr to Oct"
                months[half] += 1
                hits[half] += r[4] >= m
        print("D15 chosen after looking, CI.%s, scored launch windows that hit by season: Nov to Mar %d of %d; "
              "Apr to Oct %d of %d" % (s, hits["Nov to Mar"], months["Nov to Mar"], hits["Apr to Oct"],
                                       months["Apr to Oct"]))

    # what the experiment could show, as the design computed it before any record was fetched
    for n_l, n_c in ((23, 68), (15, 45)):
        rej = [[rule.p_fisher(a, b, n_l, n_c) <= score.LEVEL for b in range(n_c + 1)] for a in range(n_l + 1)]
        for p_l in (0.8, 0.5, 0.4, 0.3, 0.2):
            cells = []
            for p_c in (0.0, 0.05, 0.1, 0.2):
                pa, pb = binom(n_l, p_l), binom(n_c, p_c)
                cells.append("%.3f" % sum(pa[a] * pb[b] for a in range(n_l + 1) for b in range(n_c + 1)
                                          if rej[a][b]))
            print("D16 power, %d launch and %d control windows, a launch window hits with chance %.2f; a control "
                  "window with 0, 0.05, 0.1, 0.2: %s" % (n_l, n_c, p_l, ", ".join(cells)))
    print("D17 the least launch-hit count that rejects at %.4f with 23 and 68 windows, for 0 to 20 control hits: %s"
          % (score.LEVEL, ", ".join(str(rule.needed(b, 23, 68, score.LEVEL)) for b in range(21))))
    # D2's own control times (docs/studies/d2/launches.tsv, read as text) that are an hour off
    # their launch's local time, which this study's condition 5 refuses
    off = []
    for line in open(os.path.join(os.path.dirname(HERE), "d2", "launches.tsv"), encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        if f[5] != "fetched":
            continue
        t0 = datetime.strptime(f[3], rule.ISO).replace(tzinfo=timezone.utc)
        for d in f[6].split(","):
            if d and d3launches.daylight(t0) != d3launches.daylight(t0 + timedelta(days=int(d))):
                off.append("%s %s" % (f[2], d))
    print("D19 D2's control times an hour off their launch's local time: %d: %s" % (len(off), ", ".join(off)))
    t_ok = all(d3launches.daylight(r["t0"]) == d3launches.daylight(r["t0"] + timedelta(days=d))
               for r in launches for d in r["controls"])
    print("D20 this study's control times all on their launch's local clock: %s" % t_ok)
    _lines, freeze = score.freeze_lines()
    second = open(os.path.join(HERE, "scored-output.txt"), encoding="utf-8").read().split("\n")[1]
    print("D18 the freeze hash of the files as they are now: %s; the scoring run's own line: %s" % (freeze, second))
    return 0


if __name__ == "__main__":
    sys.exit(main())

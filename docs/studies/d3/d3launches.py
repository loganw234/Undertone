#!/usr/bin/env python3
"""The launches of study D3, the split, the control times and the requests.

    python docs/studies/d3/d3launches.py CATALOGUE_DIR          write launches.tsv and requests.tsv
    python docs/studies/d3/d3launches.py CATALOGUE_DIR --check  fail if either file would differ

The modules of this study are named d3*.py, not D2's names: a test process
that imports D2's rule.py and this study's would otherwise be handed whichever
"rule" it imported first.

It makes no request and opens no waveform. CATALOGUE_DIR holds gcat-launch.tsv
as study D1b fetched it; the file is refused unless its SHA-256 is the one in
docs/studies/d1/manifest.tsv, typed below.

THE RULES (the design in the round's ledger, 2026-11-24 09:27, approved by the
lead at 09:29, before any record of these stations in 2024 was fetched)

  launches   D2's: every entry with vehicle "Falcon 9", a site among
             Vandenberg's codes, a Launch_Date in 2024, and a time written to
             the second and not marked uncertain. 35.
  split      NEW. Launches numbered 1, 2, ... in time order; launch n sets
             constants when n mod 3 = 1, and is scored otherwise: 12 and 23.
             Tag 2021-082, the launch D1b looked at, is on the constant-setting
             side by name, with no record read here.
  controls   D2's rule but for its condition 2: for each launch, T0 plus a
             whole number of weeks, tried in the order of ORDER, launches in
             time order; the first N_CONTROLS that pass all four conditions:
               1 at least 24 hours from the time of every entry from
                 Vandenberg's site codes, any vehicle (24 h and 60 s from one
                 timed to the minute; the whole day and 24 h either side of one
                 with only a day);
               3 at least two hours from every control time already taken;
               4 between 2023-12-01 and 2025-02-01;
               5 NEW: inside Pacific daylight time exactly when its launch is,
                 so that it is at its launch's time of day on the local clock
                 as on the UTC one (D2's limit 8).
             D2's condition 2 (the same side of a date boundary) has no
             boundary to refer to under this split; a control time belongs to
             its launch, and condition 3 keeps every one distinct.
  requests   one station-metadata request; for each launch and station one
             launch record, T0 - 4300 s to T0 + the window's close + 10 s;
             for each control time and station one control record,
             T0' - 700 s to T0' + the window's close + 10 s. HHZ.

WHAT IT CANNOT SEE
  - A launch, a static firing or a called-off countdown the catalogue does not list.
  - Whether a time in the catalogue is right. It reads the time's written form.
  - Whether any station holds a record for any request.
"""
import hashlib
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.join(os.path.dirname(HERE), "d1"))
import catalogue  # noqa: E402
import d3rule as rule  # noqa: E402

CATALOGUE_SHA256 = "456f6acdb9b5ef78a0629153ccd890fb4d0fcb3153ef9d7b264672da33926a1f"
N_CONTROLS = 3
ORDER = [-7, 7, -14, 14, -21, 21, -28, 28, -35, 35, -42, 42]
CONTROL_FROM = datetime(2023, 12, 1, tzinfo=timezone.utc)
CONTROL_TO = datetime(2025, 2, 1, tzinfo=timezone.utc)
# US Pacific daylight time between CONTROL_FROM and CONTROL_TO: from the second
# Sunday of March 2024, 02:00 PST = 10:00 UTC, to the first Sunday of November
# 2024, 02:00 PDT = 09:00 UTC. No other change falls in that range.
DST_ON = datetime(2024, 3, 10, 10, 0, tzinfo=timezone.utc)
DST_OFF = datetime(2024, 11, 3, 9, 0, tzinfo=timezone.utc)
LOOKED_AT = ("2021-082", datetime(2021, 9, 14, 3, 55, 50, tzinfo=timezone.utc), "Starlink-32 (N30)")
LAUNCH_BEFORE = 4300
CONTROL_BEFORE = 700
AFTER_CLOSE = 10
SCEDC = "https://service.scedc.caltech.edu/fdsnws"
ISO = "%Y-%m-%dT%H:%M:%S"


def side_of(n):
    """The side of the launch numbered n (from 1, in time order)."""
    return rule.SETS if n % 3 == 1 else rule.SCORED


def daylight(t):
    """True when t falls in Pacific daylight time (only for CONTROL_FROM <= t < CONTROL_TO)."""
    return DST_ON <= t < DST_OFF


def spans(station):
    """{"launch": (from, to), "control": (from, to)}: seconds from T0 (or T0')
    that a record of this station is asked for."""
    _lo, hi = rule.window(station)
    return {"launch": (-LAUNCH_BEFORE, hi + AFTER_CLOSE),
            "control": (-CONTROL_BEFORE, hi + AFTER_CLOSE)}


def choose_controls(mine, timed, day_only):
    """[[days], ...] for each launch of mine, by the rule above."""
    def clear(tc):
        for t, precision in timed:
            need = 24 * 3600 + (60 if precision.startswith("the minute") else 0)
            if abs((tc - t).total_seconds()) < need:
                return False
        for day in day_only:
            if day - timedelta(hours=24) < tc < day + timedelta(hours=48):
                return False
        return True

    taken, out = [], []
    for t, _tag, _flight in mine:
        got = []
        for days in ORDER:
            tc = t + timedelta(days=days)
            if not CONTROL_FROM <= tc < CONTROL_TO:
                continue
            if not clear(tc):
                continue
            if daylight(tc) != daylight(t):
                continue
            if any(abs((tc - u).total_seconds()) < 2 * 3600 for u in taken):
                continue
            got.append(days)
            taken.append(tc)
            if len(got) == N_CONTROLS:
                break
        out.append(got)
    return out


def build(cat_dir):
    """(launch rows, request rows), each a list of tuples of strings."""
    path = os.path.join(cat_dir, "gcat-launch.tsv")
    got = hashlib.sha256(open(path, "rb").read()).hexdigest()
    if got != CATALOGUE_SHA256:
        raise SystemExit("REFUSED CATALOGUE: %s has SHA-256 %s" % (path, got))
    _head, _updated, rows = catalogue.load(path)
    timed, day_only, mine = [], [], []
    for r in rows:
        if r["Launch_Site"] not in catalogue.VANDENBERG:
            continue
        d = r["Launch_Date"]
        if d[:4] not in ("2023", "2024", "2025"):
            continue
        t, precision = catalogue.when(d)
        if t is None:
            p = d.replace("?", "").split()
            if len(p) < 3 or p[1] not in catalogue.MONTHS:
                raise SystemExit("REFUSED ENTRY: %s has no day: %r" % (r["Launch_Tag"], d))
            day_only.append(datetime(int(p[0]), catalogue.MONTHS.index(p[1]) + 1, int(p[2]),
                                     tzinfo=timezone.utc))
            continue
        timed.append((t, precision))
        if r["LV_Type"] == "Falcon 9" and d.startswith("2024") and precision == "the second":
            mine.append((t, r["Launch_Tag"], r["Flight"]))
    mine.sort()
    if len(set(tag for _t, tag, _f in mine)) != len(mine):
        raise SystemExit("REFUSED: a launch tag occurs twice")
    controls = choose_controls(mine, timed, day_only)
    launches = [("0", rule.SETS, LOOKED_AT[0], LOOKED_AT[1].strftime(ISO), LOOKED_AT[2], "none", "")]
    for i, ((t, tag, flight), got) in enumerate(zip(mine, controls), 1):
        launches.append((str(i), side_of(i), tag, t.strftime(ISO), flight, "fetched",
                         ",".join("%+d" % g for g in got)))

    def url(sta, t, span):
        return ("%s/dataselect/1/query?net=CI&sta=%s&loc=--&cha=HHZ&start=%s&end=%s&nodata=404"
                % (SCEDC, sta, (t + timedelta(seconds=span[0])).strftime(ISO),
                   (t + timedelta(seconds=span[1])).strftime(ISO)))

    stations = [s for s, _km in rule.STATIONS]
    requests = [("scedc-ci-hhz-2024-epochs.txt",
                 "%s/station/1/query?net=CI&sta=%s&cha=HHZ&level=channel&format=text"
                 "&startbefore=2025-01-01T00:00:00&endafter=2024-01-01T00:00:00"
                 % (SCEDC, ",".join(stations)))]
    for _n, _side, tag, t0, _flight, records, ctl in launches:
        if records != "fetched":
            continue
        t = datetime.strptime(t0, ISO).replace(tzinfo=timezone.utc)
        for sta in stations:
            requests.append((rule.record_name(sta, tag, None), url(sta, t, spans(sta)["launch"])))
        for days in ctl.split(","):
            if not days:
                continue
            tc = t + timedelta(days=int(days))
            for sta in stations:
                requests.append((rule.record_name(sta, tag, int(days)),
                                 url(sta, tc, spans(sta)["control"])))
    return launches, requests


def texts(cat_dir):
    launches, requests = build(cat_dir)
    a = ["# The launches of study D3, written by d3launches.py from GCAT's launch list",
         "# (SHA-256 %s)." % CATALOGUE_SHA256,
         "# Tab-separated: number in time order; side; tag; T0 (UTC); flight; records;",
         "# control times as whole days from T0."]
    a += ["\t".join(row) for row in launches]
    b = ["# The requests of study D3, in the order they are made, written by d3launches.py.",
         "# Tab-separated: the file a response is saved under; the address."]
    b += ["\t".join(row) for row in requests]
    return "\n".join(a) + "\n", "\n".join(b) + "\n"


def main():
    args = sys.argv[1:]
    check = "--check" in args
    args = [a for a in args if a != "--check"]
    if len(args) != 1:
        raise SystemExit(__doc__)
    a, b = texts(args[0])
    ok = True
    for name, text in (("launches.tsv", a), ("requests.tsv", b)):
        path = os.path.join(HERE, name)
        if check:
            have = open(path, encoding="utf-8", newline="").read() if os.path.exists(path) else None
            if have != text:
                print("DIFFERS: %s" % name)
                ok = False
        else:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
    n_l = a.count("\tfetched\t")
    print("%s launches.tsv and requests.tsv: %d launches with records, %d requests"
          % ("OK check:" if check and ok else "FAILED check:" if check else "wrote", n_l,
             len(b.strip().split("\n")) - 2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

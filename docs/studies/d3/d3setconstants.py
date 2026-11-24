#!/usr/bin/env python3
"""Set study D3's one constant a station, M, from the constant-setting launches only.

    python docs/studies/d3/d3setconstants.py DATA_DIR            print, and write constants.json
    python docs/studies/d3/d3setconstants.py DATA_DIR --tags A,B the same from the launches named

It makes no request. It reads launches.tsv, the fetch's manifest, and the
records of the launches on the constant-setting side: their launch records and
their own control records. **A launch of the scored side is refused by name,
CONSTANTS-FROM-A-SCORED-LAUNCH, before any record is opened** (d3rule.collect).

HOW M IS SET, for each station: study D2's rule, unchanged (d2/setconstants.py)
  A = the statistic S of every usable constant-setting launch window,
  B = the same of every usable constant-setting control window.
  J(m) = (the share of A at or above m) - (the share of B at or above m),
  for m from 10 to the window's length in seconds. J* is the largest J;
  m_lo the smallest m with J(m) = J*; m_hi the largest m such that every m
  from m_lo to m_hi has J*. M = sqrt(m_lo * m_hi), rounded to the nearest
  whole number. With fewer than 4 launch windows or fewer than 8 control
  windows, M is 10 and the output says it was not set from records.

WHAT IT CANNOT SEE
  - Whether M suits the scored launches: it is set on twelve others.
  - Anything about a scored launch. It never opens one.
"""
import json
import math
import os
import sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import d3rule as rule  # noqa: E402

MIN_LAUNCH_WINDOWS, MIN_CONTROL_WINDOWS = 4, 8


def choose_m(a, b, length):
    """(M, (J*, m_lo, m_hi)) or (10, None) when there are too few windows."""
    if len(a) < MIN_LAUNCH_WINDOWS or len(b) < MIN_CONTROL_WINDOWS:
        return rule.M_FLOOR, None
    j = {}
    for m in range(rule.M_FLOOR, length + 1):
        j[m] = (Fraction(sum(1 for s in a if s >= m), len(a))
                - Fraction(sum(1 for s in b if s >= m), len(b)))
    best = max(j.values())
    m_lo = min(m for m in j if j[m] == best)
    m_hi = m_lo
    while m_hi + 1 in j and j[m_hi + 1] == best:
        m_hi += 1
    return int(math.floor(math.sqrt(m_lo * m_hi) + 0.5)), (best, m_lo, m_hi)


def refuse_other_side(launches, tags):
    """Refuse, by name, any tag that is not on the constant-setting side."""
    sides = dict((row["tag"], row["side"]) for row in launches)
    for tag in tags:
        if tag not in sides:
            raise rule.Refusal("UNKNOWN-LAUNCH", tag)
        if sides[tag] != rule.SETS:
            raise rule.Refusal("CONSTANTS-FROM-A-SCORED-LAUNCH", tag)


def main():
    args = sys.argv[1:]
    tags = None
    if "--tags" in args:
        i = args.index("--tags")
        tags = args[i + 1].split(",")
        del args[i:i + 2]
    if len(args) != 1:
        raise SystemExit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    data_dir = args[0]
    launches = rule.read_launches(os.path.join(HERE, "launches.tsv"))
    manifest = rule.read_manifest(os.path.join(HERE, "manifest.tsv"))
    if tags is None:
        tags = [row["tag"] for row in launches if row["side"] == rule.SETS]
    try:
        refuse_other_side(launches, tags)
        missing = rule.not_fetched(launches, tags, manifest, data_dir)
        if missing:
            raise rule.Refusal("FETCH-NOT-COMPLETE", "%d records of these launches are not "
                               "settled by the manifest, the first %s" % (len(missing), missing[0]))
        rows = rule.collect(launches, tags, rule.SETS, rule.make_loader(data_dir, manifest))
    except rule.Refusal as e:
        raise SystemExit("REFUSED %s" % e)
    used = [t for t in tags if any(r[0] == t for r in rows)]
    print("Constants of study D3, from %d constant-setting launches: %s."
          % (len(used), ", ".join(used)))
    print()
    print("| station | window, s | launch windows: S, in time order | control windows: S, sorted "
          "| no record | J* | m_lo | m_hi | M |")
    print("|---|---|---|---|---|---|---|---|---|")
    out = {"M": {}, "set_from_records": {}, "launches": used, "S_launch": {}, "S_control": {}}
    for station, _km in rule.STATIONS:
        lo, hi = rule.window(station)
        a = [r[4] for r in rows if r[1] == station and r[2] == "launch" and r[4] is not None]
        b = [r[4] for r in rows if r[1] == station and r[2] == "control" and r[4] is not None]
        gone = sum(1 for r in rows if r[1] == station and r[2] in ("launch", "control")
                   and r[4] is None)
        m, how = choose_m(a, b, hi - lo)
        out["M"][station], out["set_from_records"][station] = m, how is not None
        out["S_launch"][station], out["S_control"][station] = a, b
        print("| CI.%s | %d to %d | %s | %s | %d | %s | %s | %s | %d%s |" % (
            station, lo, hi, ", ".join(str(s) for s in a) or "none",
            ", ".join(str(s) for s in sorted(b)) or "none", gone,
            "-" if how is None else "%d/%d" % (how[0].numerator, how[0].denominator)
            if how[0].denominator != 1 else str(how[0].numerator),
            "-" if how is None else how[1], "-" if how is None else how[2], m,
            "" if how is not None else " (not set from records: too few windows)"))
    print()
    print("Windows with no record, constant-setting side:")
    for r in rows:
        if r[2] in ("launch", "control") and r[4] is None:
            print("- %s CI.%s %s%s: %s" % (r[0], r[1], r[2],
                                         " %+d d" % r[3] if r[2] == "control" else "", r[5]))
    path = os.path.join(HERE, "constants.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")
    print()
    print("wrote constants.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

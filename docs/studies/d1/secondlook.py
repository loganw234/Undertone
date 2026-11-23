#!/usr/bin/env python3
"""Second measures for study D1b, EVERY ONE OF THEM CHOSEN AFTER LOOKING.

    python docs/studies/d1/secondlook.py DATA_DIR

It needs numpy, and firstlook.py and mseed.py beside it. It makes no
request. It reads the same *.mseed files as firstlook.py and uses its band
power, its ratio and its stretches unchanged. What it adds was decided
after the first look's tables and figures had been seen, to describe what
they showed. Nothing here was fixed beforehand, so nothing here is a test:
a number below can describe the one launch looked at and cannot count as
evidence that the description would hold for another.

  A  the first counting stretch that begins inside the SOUND window, per
     station and band, on the launch day; and the slope of that onset
     against distance over the stations where the 2 to 8 Hz band has one
  B  the launch day's median ratio over the sound window against the larger
     of the two control days' medians
  C  the seconds before the sound window opens: the median ratio and the up
     seconds from T0 to the sound window's opening, on all three days
"""
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import firstlook as fl  # noqa: E402


def first_in(ratio, window):
    lo, hi = math.floor(window[0]), math.ceil(window[1])
    for s in fl.stretches(ratio):
        if s[2] >= fl.MIN_UP and lo <= s[0] < hi:
            return s
    return None


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    data = fl.load(sys.argv[1])
    print("**A. The first counting stretch that begins inside the sound window, launch day, "
          "vertical channel.** Chosen after looking. A cell reads: onset in seconds after T0, "
          "the last up second, and km over onset in km/s.")
    print()
    print("| station | km | %s |" % " | ".join(fl.band_name(b) for b in range(len(fl.BANDS))))
    print("|---|---|---|---|---|---|")
    fit = []
    for sta, d in fl.STATIONS:
        got = data.get((sta, "HHZ", "2021-09-14"))
        if not got:
            continue
        cells = []
        for b in range(len(fl.BANDS)):
            s = first_in(got[0][b], fl.windows(d)["sound"])
            cells.append("none" if s is None else "%d; %d; %.3f" % (s[0], s[1], d / s[0]))
            if b == fl.COUNTING_BAND and s is not None:
                fit.append((sta, d, s[0], s[1]))
        print("| CI.%s | %.1f | %s |" % (sta, d, " | ".join(cells)))
    print()
    for label, pts in (("every station with such a stretch", fit),
                       ("the same without CI.CDM, whose stretch a control day also has",
                        [p for p in fit if p[0] != "CDM"])):
        ds, ts = np.array([p[1] for p in pts]), np.array([p[2] for p in pts])
        slope, intercept = np.polyfit(ds, ts, 1)
        resid = ts - (slope * ds + intercept)
        print("- Slope of that onset against distance, 2 to 8 Hz, over %s (%s): %.2f s per km, "
              "which is %.3f km/s; intercept %.0f s; residuals %s s."
              % (label, ", ".join("CI." + p[0] for p in pts), slope, 1 / slope, intercept,
                 ", ".join("%+.0f" % r for r in resid)))
    print()
    print("**B. The launch day's median ratio over the sound window against the larger "
          "control day's, 2 to 8 Hz, vertical channel.** Chosen after looking.")
    print()
    print("| station | km | launch day | larger control day | launch over control |")
    print("|---|---|---|---|---|")
    for sta, d in fl.STATIONS:
        meds = {}
        for day, _label, _shift in fl.DAYS:
            got = data.get((sta, "HHZ", day))
            if got:
                meds[day] = fl.look(got[0][fl.COUNTING_BAND], fl.windows(d)["sound"])["median"]
        if len(meds) != 3:
            continue
        control = max(meds["2021-09-13"], meds["2021-09-15"])
        print("| CI.%s | %.1f | %.2f | %.2f | %.1f |" % (sta, d, meds["2021-09-14"], control,
                                                       meds["2021-09-14"] / control))
    print()
    print("**C. Before the sound window opens: from T0 to the sound window's opening, 2 to 8 "
          "Hz, vertical channel.** Chosen after looking, because CI.MPP showed a stretch "
          "there. A cell reads: the median ratio; the up seconds of the seconds.")
    print()
    print("| station | km | seconds after T0 | the day before | launch day | the day after |")
    print("|---|---|---|---|---|---|")
    for sta, d in fl.STATIONS:
        hi = math.floor(fl.windows(d)["sound"][0])
        cells = []
        for day, _label, _shift in fl.DAYS:
            got = data.get((sta, "HHZ", day))
            if not got:
                cells.append("no record")
                continue
            vals = [got[0][fl.COUNTING_BAND][k] for k in range(0, hi)
                    if k in got[0][fl.COUNTING_BAND]]
            cells.append("%.2f; %d of %d" % (float(np.median(vals)),
                                           sum(1 for v in vals if v > fl.UP_ABOVE), len(vals)))
        if all(c == "no record" for c in cells):
            continue
        print("| CI.%s | %.1f | 0 to %d | %s |" % (sta, d, hi, " | ".join(cells)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Prints the proposed waveform requests of study D1, section 8, as a table.

    python docs/studies/d1/download_list.py

It makes no request and reads nothing. The stations and their distances are
the 2021 ladder of the study (its row M4) and the second station of the
nearest rung, CI.LOC, typed here; the window is the study's row X1. It
cannot see whether a station held data in the window: that is the first
thing LCH-2 checks.
"""
BASE = "https://service.scedc.caltech.edu/fdsnws/dataselect/1/query"

# station, km from SLC-4 on 2021-09-14 (the study's block for that date)
LADDER = [("GATR", 13.5), ("LCP", 32.6), ("SYN", 49.9), ("MPP", 78.5),
          ("CDM", 120.4), ("HDH", 181.4), ("SRN", 275.0)]
SECOND_NEAR = ("LOC", 16.5)
KM = dict(LADDER + [SECOND_NEAR])

LAUNCH_DAY, BEFORE, AFTER = "2021-09-14", "2021-09-13", "2021-09-15"
START, END = "03:40:00", "04:30:00"


def url(sta, cha, day):
    return ("%s?net=CI&sta=%s&loc=--&cha=%s&start=%sT%s&end=%sT%s&nodata=404"
            % (BASE, sta, cha, day, START, day, END))


rows = []
for sta in ("GATR", "LCP", "SYN"):
    rows.append(("A", sta, "HHZ", LAUNCH_DAY))
for sta in ("LOC", "MPP", "CDM", "HDH", "SRN"):
    rows.append(("B", sta, "HHZ", LAUNCH_DAY))
for day in (BEFORE, AFTER):
    for sta in ("GATR", "LOC", "LCP", "SYN", "MPP", "CDM", "HDH", "SRN"):
        rows.append(("C", sta, "HHZ", day))
for sta in ("GATR", "LCP", "SYN"):
    for cha in ("HHE", "HHN"):
        rows.append(("D", sta, cha, LAUNCH_DAY))

print("| request | tier | station | km | channel | window, UTC | the request as it would be made |")
print("|---|---|---|---|---|---|---|")
for i, (tier, sta, cha, day) in enumerate(rows, 1):
    print("| %s%02d | %s | CI.%s | %.1f | %s | %s %s to %s | `%s` |"
          % (tier, i, tier, sta, KM[sta], cha, day, START[:5], END[:5], url(sta, cha, day)))
print()
print("%d requests; each is 50 minutes of one channel at 100 samples a second." % len(rows))

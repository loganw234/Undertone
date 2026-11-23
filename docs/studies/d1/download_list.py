#!/usr/bin/env python3
"""The requests of study D1, section 8: the table for the study, or the list to fetch.

    python docs/studies/d1/download_list.py            the 30 waveform requests,
                                                       as the study's table
    python docs/studies/d1/download_list.py --fetch    every request of section 8,
                                                       one "name TAB url" a line,
                                                       in the order they are made

It makes no request and reads nothing. The stations and their distances are
the 2021 ladder of the study (its row M4) and the second station of the
nearest rung, CI.LOC, typed here; the window is the study's. fetch.sh reads
the --fetch form. It cannot see whether a station held data in the window.
"""
import sys

SCEDC = "https://service.scedc.caltech.edu/fdsnws"
GCAT = "https://planet4589.org/space/gcat/tsv"

# station, km from SLC-4 on 2021-09-14 (the study's block for that date)
LADDER = [("GATR", 13.5), ("LCP", 32.6), ("SYN", 49.9), ("MPP", 78.5),
          ("CDM", 120.4), ("HDH", 181.4), ("SRN", 275.0)]
SECOND_NEAR = ("LOC", 16.5)
KM = dict(LADDER + [SECOND_NEAR])

LAUNCH_DAY, BEFORE, AFTER = "2021-09-14", "2021-09-13", "2021-09-15"
START, END = "03:40:00", "04:30:00"


def url(sta, cha, day):
    return ("%s/dataselect/1/query?net=CI&sta=%s&loc=--&cha=%s&start=%sT%s&end=%sT%s&nodata=404"
            % (SCEDC, sta, cha, day, START, day, END))


def waveform_rows():
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
    return rows


def fetch_list():
    out = []
    # item 1: availability extents; LCP's was already in hand
    for sta in ("GATR", "LOC", "SYN", "MPP", "CDM", "HDH", "SRN"):
        out.append(("avail-CI-%s.txt" % sta,
                    "%s/availability/1/extent?network=CI&station=%s&asset=continuous"
                    % (SCEDC, sta)))
    # items 2 and 3: the launch list, the pad table and the site table
    out.append(("gcat-launch.tsv", GCAT + "/launch/launch.tsv"))
    out.append(("gcat-lp.tsv", GCAT + "/tables/lp.tsv"))
    out.append(("gcat-sites.tsv", GCAT + "/tables/sites.tsv"))
    # items 4 and 5: the waveforms
    for _tier, sta, cha, day in waveform_rows():
        out.append(("CI.%s.%s.%s.mseed" % (sta, cha, day), url(sta, cha, day)))
    # item 6: the earthquake catalogue for the three windows
    for day in (BEFORE, LAUNCH_DAY, AFTER):
        out.append(("scedc-events-%s.txt" % day,
                    "%s/event/1/query?starttime=%sT03:00:00&endtime=%sT05:00:00&format=text"
                    % (SCEDC, day, day)))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    if sys.argv[1:] == ["--fetch"]:
        for name, u in fetch_list():
            print("%s\t%s" % (name, u))
        return 0
    if sys.argv[1:]:
        raise SystemExit(__doc__)
    rows = waveform_rows()
    print("| request | tier | station | km | channel | window, UTC "
          "| the request as it would be made |")
    print("|---|---|---|---|---|---|---|")
    for i, (tier, sta, cha, day) in enumerate(rows, 1):
        print("| %s%02d | %s | CI.%s | %.1f | %s | %s %s to %s | `%s` |"
              % (tier, i, tier, sta, KM[sta], cha, day, START[:5], END[:5], url(sta, cha, day)))
    print()
    print("%d requests; each is 50 minutes of one channel at 100 samples a second." % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())

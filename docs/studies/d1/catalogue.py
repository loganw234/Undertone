#!/usr/bin/env python3
"""What the fetched launch catalogue says, for study D1b. Standard library only.

    python docs/studies/d1/catalogue.py DATA_DIR

It makes no request. It reads three files that fetch.sh put in DATA_DIR,
tab-separated, each with a header line and an "Updated" line:

    gcat-launch.tsv   GCAT's launch list
    gcat-lp.tsv       its table of launch pads
    gcat-sites.tsv    its table of launch sites

and prints, as markdown: the entry for launch 2021-082; every entry within
two days of it; the launches from Vandenberg's site codes within 24 hours of
each day's stand-in launch time; the pad's coordinates and the ladder's
distances from them; the launch codes that occur and how often; the entries
whose code holds Z or a pad abort; every entry that mentions the word scrub;
and the count of Falcon 9 launches from Vandenberg in 2024.

WHAT IT CANNOT SEE
  - A countdown the catalogue does not list. Counting codes shows what the
    file holds, not what happened.
  - Whether a time in the file is right. It reads the time's written form.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stations  # noqa: E402  (for the same distance formula as the study)

TAG = "2021-082"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
VANDENBERG = ("V", "VS", "VSFB", "VSFBS")
# The ladder's stations and coordinates, from the study's block for 2021-09-14.
LADDER = [("GATR", 34.5527, -120.5024, 13.5), ("LOC", 34.6907, -120.4469, 16.5),
          ("LCP", 34.7355, -120.2800, 32.6), ("SYN", 34.6072, -120.0696, 49.9),
          ("MPP", 34.8885, -119.8136, 78.5), ("CDM", 34.3685, -119.3414, 120.4),
          ("HDH", 34.7753, -118.6400, 181.4), ("SRN", 33.8285, -117.7894, 275.0)]


def load(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        head = [h.strip() for h in f.readline().lstrip("#").rstrip("\n").split("\t")]
        updated = f.readline().strip().lstrip("#").strip()
        rows = []
        for line in f:
            cells = [c.strip() for c in line.rstrip("\n").split("\t")]
            if len(cells) != len(head):
                raise SystemExit("REFUSED BAD-ROW in %s: %d cells" % (path, len(cells)))
            rows.append(dict(zip(head, cells)))
    return head, updated, rows


def when(text):
    """(time or None, precision): the time a vague date names, if it names a
    minute or better. '2021 Sep 14 0355:50' is to the second."""
    parts = text.replace("?", "").split()
    if len(parts) < 4 or parts[1] not in MONTHS or not parts[3][:4].isdigit():
        return None, "a day or coarser"
    hm = parts[3]
    sec, precision = 0, "the minute"
    if ":" in hm:
        hm, s = hm.split(":")
        sec, precision = int(float(s)), "the second"
    t = datetime(int(parts[0]), MONTHS.index(parts[1]) + 1, int(parts[2]), int(hm[:2]),
                 int(hm[2:4]), sec, tzinfo=timezone.utc)
    return t, precision + (", marked uncertain" if "?" in text else "")


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    d = sys.argv[1]
    head, updated, rows = load(os.path.join(d, "gcat-launch.tsv"))
    _h, lp_updated, pads = load(os.path.join(d, "gcat-lp.tsv"))
    print("The launch list: %d entries, %d columns, the file's own line: %s."
          % (len(rows), len(head), updated))
    print()
    mine = [r for r in rows if r["Launch_Tag"] == TAG]
    if len(mine) != 1:
        raise SystemExit("REFUSED: %d entries with tag %s" % (len(mine), TAG))
    m = mine[0]
    t0, precision = when(m["Launch_Date"])
    print("**The launch.** Tag %s: Launch_Date `%s`, which is to %s; vehicle %s; flight %s; "
          "site %s, pad %s; LaunchCode %s; time cited to `%s`."
          % (TAG, m["Launch_Date"], precision, m["LV_Type"], m["Flight"], m["Launch_Site"],
             m["Launch_Pad"], m["LaunchCode"], m["LTCite"]))
    print()
    print("**Every entry within two days of it.**")
    print()
    print("| tag | Launch_Date | vehicle | site | pad | code | hours from T0 |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        t, _p = when(r["Launch_Date"])
        if t is None:
            near = r["Launch_Date"][:11] in ("2021 Sep 12", "2021 Sep 13", "2021 Sep 14",
                                             "2021 Sep 15", "2021 Sep 16")
            gap = "time not given"
        else:
            near = abs((t - t0).total_seconds()) <= 48 * 3600
            gap = "%+.1f" % ((t - t0).total_seconds() / 3600)
        if near:
            print("| %s | %s | %s | %s | %s | %s | %s |" % (
                r["Launch_Tag"], r["Launch_Date"], r["LV_Type"], r["Launch_Site"],
                r["Launch_Pad"], r["LaunchCode"], gap))
    print()
    print("**Launches from Vandenberg's site codes (%s) within 24 hours of each day's "
          "stand-in time.**" % ", ".join(VANDENBERG))
    print()
    print("| day | stand-in time, UTC | launches within 24 hours, other than %s |" % TAG)
    print("|---|---|---|")
    for shift, label in ((-1, "the day before"), (0, "launch day"), (1, "the day after")):
        ref = t0 + timedelta(days=shift)
        hits = []
        for r in rows:
            t, _p = when(r["Launch_Date"])
            if r["Launch_Site"] in VANDENBERG and t is not None and r["Launch_Tag"] != TAG \
                    and abs((t - ref).total_seconds()) < 24 * 3600:
                hits.append("%s, %s, %s, %+.1f h" % (r["Launch_Tag"], r["LV_Type"],
                                                    r["Launch_Date"],
                                                    (t - ref).total_seconds() / 3600))
        print("| %s | %s | %s |" % (label, ref.strftime("%Y-%m-%d %H:%M:%S"),
                                   "; ".join(hits) or "none"))
    print()
    pad = [p for p in pads if p["Code"] == m["Launch_Pad"] and p["Site"] in VANDENBERG]
    if len(pad) != 1:
        raise SystemExit("REFUSED: %d pad rows for %s" % (len(pad), m["Launch_Pad"]))
    plat, plon = float(pad[0]["Latitude"]), float(pad[0]["Longitude"])
    print("**The pad.** The pad table (%s) lists %s under site %s at latitude %s, longitude %s, "
          "error %s; name: %s." % (lp_updated, pad[0]["Code"], pad[0]["Site"],
                                   pad[0]["Latitude"], pad[0]["Longitude"], pad[0]["Error"],
                                   pad[0]["Name"]))
    print()
    print("| station | km from the study's point (34.633, -120.613) | km from the pad table's "
          "point | difference |")
    print("|---|---|---|---|")
    for sta, lat, lon, km in LADDER:
        d2 = stations.vincenty_km(plat, plon, lat, lon)
        print("| CI.%s | %.1f | %.1f | %+.1f |" % (sta, km, d2, d2 - km))
    print()
    print("**Launch codes.** First letter, then second letter, with the number of entries.")
    print()
    for pos, label in ((0, "first"), (1, "second")):
        count = {}
        for r in rows:
            c = r["LaunchCode"][pos:pos + 1] or "(none)"
            count[c] = count.get(c, 0) + 1
        print("- %s letter: %s" % (label, ", ".join(
            "%s %d" % kv for kv in sorted(count.items(), key=lambda kv: -kv[1]))))
    print()
    odd = [r for r in rows if "Z" in r["LaunchCode"][:2] or r["LaunchCode"][1:2] == "A"]
    print("**Entries whose code holds Z, or A for a pad abort: %d.**" % len(odd))
    print()
    print("| tag | Launch_Date | vehicle | site | pad | code | notes |")
    print("|---|---|---|---|---|---|---|")
    for r in odd:
        print("| %s | %s | %s | %s | %s | %s | %s |" % (
            r["Launch_Tag"], r["Launch_Date"], r["LV_Type"], r["Launch_Site"],
            r["Launch_Pad"], r["LaunchCode"], r["Notes"]))
    print()
    scrub = [r for r in rows if "scrub" in " ".join(r.values()).lower()]
    print("**Entries that hold the word scrub in any field: %d.**" % len(scrub))
    print()
    for r in scrub:
        where = [k for k, v in r.items() if "scrub" in v.lower()]
        print("- %s, %s, %s: in %s: `%s`" % (r["Launch_Tag"], r["Launch_Date"], r["LV_Type"],
                                            ", ".join(where),
                                            "; ".join(r[k] for k in where)))
    print()
    f9 = [r for r in rows if r["LV_Type"] == "Falcon 9" and r["Launch_Date"].startswith("2024")
          and r["Launch_Site"] in VANDENBERG]
    to_second = sum(1 for r in f9 if when(r["Launch_Date"])[1] == "the second")
    print("**Falcon 9 from Vandenberg in 2024.** %d entries, all from pad(s) %s; %d of them "
          "timed to the second and not marked uncertain."
          % (len(f9), ", ".join(sorted(set(r["Launch_Pad"] for r in f9))), to_second))
    return 0


if __name__ == "__main__":
    sys.exit(main())

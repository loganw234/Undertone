#!/usr/bin/env python3
"""The arithmetic behind study D1's COMPUTED rows. Standard library only.

    python docs/studies/d1/figures.py

It reads nothing, and imports stations.py beside it for one distance. Every input is written in this file beside the row of the
study it comes from. It prints one labelled line per figure; a COMPUTED row
of the study cites the label. It cannot see whether an input is true: each
input is a READ, MEASURED, ESTIMATE or BELIEVED row of the study, named in
the comment beside it.
"""
import math

out = []


def line(label, text):
    out.append("%-4s %s" % (label, text))


# F1: seconds per km at each speed. 343 m/s is row L6; 332, 292 and 250 m/s
# are the three phases of row A5.
line("F1", "seconds per km: " + ", ".join(
    "%d m/s -> %.2f" % (c, 1000.0 / c) for c in (343, 332, 292, 250)))

# F2: the plan's row L6, at 343 m/s.
line("F2", "at 343 m/s: 7 km -> %.1f s, 15 km -> %.1f s, 100 km -> %.1f s = %.2f min"
     % (7000 / 343, 15000 / 343, 100000 / 343, 100000 / 343 / 60))

# F3: the window bounds in s/km. Speeds are stations.py's parameters (rows W1, W2).
line("F3", "window slopes: sound %.2f to %.2f s/km; ground %.2f to %.2f s/km"
     % (1 / 0.345, 1 / 0.240, 1 / 6.5, 1 / 1.5))

# F4: 20:56 local on 2021-09-13 (row L3c), if local time was 7 h behind UTC
# (row W6 as first written, BELIEVED then), is 03:56 UTC on 2021-09-14.
h = 20 + 7
line("F4", "20:56 at UTC-7 on 2021-09-13 -> %02d:56 UTC on 2021-09-%d" % (h % 24, 13 + h // 24))

# F5: one request of the proposed download: 50 minutes at 100 samples/s (row M2).
n = 50 * 60 * 100
line("F5", "samples in 50 min at 100 per second: %d" % n)

# F6: an upper bound on its size: nothing compressed, 32-bit samples (row K3)
# in 512-byte records with a 64-byte header, so 112 samples a record (row E1).
recs = math.ceil(n / 112)
ub = recs * 512
line("F6", "upper bound: ceil(%d / 112) = %d records x 512 bytes = %d bytes = %.2f MB"
     % (n, recs, ub, ub / 1e6))

# F7: a typical size, IF Steim-2 averages 2 bytes a sample (row E2, BELIEVED).
typ = n * 2 * 512 / 448
line("F7", "typical: %d x 2 bytes x 512/448 = %.0f bytes = %.2f MB" % (n, typ, typ / 1e6))

# F8: the tiers of the proposed download (section 8): requests per tier.
tiers = [("A", 3), ("B", 5), ("C", 16), ("D", 6)]
total = 0
for name, k in tiers:
    total += k
    line("F8" + name, "tier %s: %d requests; upper bound %.1f MB, typical %.1f MB; "
         "running total %d requests, upper bound %.1f MB, typical %.1f MB"
         % (name, k, k * ub / 1e6, k * typ / 1e6, total, total * ub / 1e6, total * typ / 1e6))

# F9: the launch catalogue's full list, IF a row averages 300 bytes (row E3,
# ESTIMATE). 76034 rows is row L5f.
line("F9", "76034 rows x 300 bytes = %.1f MB" % (76034 * 300 / 1e6))

# F10: full scale of CI.LCP's HHZ channel at two sample widths. 629865000
# counts per m/s is row M5.
for bits in (16, 24):
    line("F10", "%d-bit full scale / 629865000 counts per m/s = %.3g m/s"
         % (bits, 2 ** (bits - 1) / 629865000))

# F11: the largest window SCEDC's dataselect answers, from row T7.
cap = 400 * 1024 * 1024 // 4
line("F11", "(400 x 1024 x 1024 / 4 - 100) samples = %d; at 100 per second = %.1f days"
     % (cap - 100, (cap - 100) / 100 / 86400))

# F12: the standard error of a hit fraction near one half, for n windows.
line("F12", "sqrt(0.25 / n): " + ", ".join(
    "n=%d -> %.3f" % (k, math.sqrt(0.25 / k)) for k in (10, 46, 100, 400)))

# F13: the smallest false-alarm fraction that ten expected false alarms
# support, for n control windows (the counterpart of D0's row D10).
line("F13", "10 / n: " + ", ".join("n=%d -> %.3f" % (k, 10 / k) for k in (100, 200, 1000)))

# F14: how much of one 256 MiB replay channel (D0 row H8) a year of records
# would fill: 46 launches (row L4, BELIEVED) x 8 stations x F5 samples.
s = 46 * 8 * n
line("F14", "46 x 8 x %d = %d samples; / 134217728 = %.2f of one channel at 16 bits"
     % (n, s, s / 134217728))

# F15: the length of each window of the 2021 ladder's first and last rung.
for d in (13.5, 275.0):
    a, b = d / 0.345 - 5, d / 0.240 + 180 + 5
    line("F15", "sound window at %.1f km: %.0f to %.0f s, %.0f s long" % (d, a, b, b - a))

# F16: what a 24-bit converter spanning 40 volts gives in counts a volt, and
# how the gain of the study's row M9, 419430 counts a volt, sits against it.
line("F16", "2^24 / 40 = %.1f counts a volt; 419430 x 40 / 2^24 = %.6f"
     % (2 ** 24 / 40, 419430 * 40 / 2 ** 24))

# F17: a day-long file of the cloud bucket (row T8) against a 50-minute request.
line("F17", "86400 s / 3000 s = %.1f" % (86400 / 3000))

# ---- study D1b. Inputs are rows of D1b-first-look.md, named beside each. ----

# F18: the wheels pip downloaded into the scratch environment, in MB as pip
# printed them (D1b row R2), and the ones it took from the desktop's pip cache.
got = [0.127, 0.214, 0.011, 2.5, 4.0, 12.6, 14.8, 0.092, 2.4]
cached = [0.234, 0.0083, 0.069, 0.070, 9.3, 0.129, 7.3, 0.126, 0.073, 36.7, 0.876, 0.045,
          0.348, 0.135]
line("F18", "downloaded: %d wheels, %.1f MB; from the cache: %d wheels, %.1f MB"
     % (len(got), sum(got), len(cached), sum(cached)))

# F19: bytes a sample in the fetched waveform files (D1b row Q5e): the
# smallest file, the largest, and all 25 together, each of 300001 samples.
line("F19", "327680 / 300001 = %.2f; 655360 / 300001 = %.2f; 10788864 / (25 x 300001) = %.2f"
     % (327680 / 300001, 655360 / 300001, 10788864 / (25 * 300001)))

# F20: the launch list as fetched (D1b row R1): bytes an entry.
line("F20", "13818818 bytes / 76039 entries = %.0f bytes an entry" % (13818818 / 76039))

# F21: CI.LOC's onset, 45 s at 16.5 km (D1b row Q3b), with the 2 s either
# side that a 4 s frame leaves.
line("F21", "16.5 km / 45 s = %.3f km/s; / 47 s = %.3f; / 43 s = %.3f"
     % (16.5 / 45, 16.5 / 47, 16.5 / 43))

# F22: the catalogue's time, 03:55:50 UTC on 2021-09-14 (D1b row Q6a), seven
# hours earlier: the post's "8:56 pm local time on Monday September 13th".
line("F22", "03:55:50 UTC on 2021-09-14 less 7 h = 20:55:50 on 2021-09-13")

# F23: the press release's two figures (D1 rows A3, A4).
line("F23", "733 / 1001 = %.3f" % (733 / 1001))

# F24: what a volts-to-counts gain of 419430 fits (D1 row M9): bits b over a
# full range of V volts give 2^b / V counts a volt.
line("F24", "419430 counts a volt: " + ", ".join(
    "2^%d / %g V = %.1f" % (b, v, 2 ** b / v) for b, v in ((24, 40), (22, 10), (21, 5), (20, 2.5))))

# F25: sample ranges. A signed 16-bit sample runs from -32768 to 32767.
line("F25", "35420 > 32767 and -36647 < -32768: both need 17 bits (2^16 = %d)" % 2 ** 16)

# F26: when each sound window closes against when the stretch ended (D1b row Q4a).
for sta, d, end in (("LOC", 16.5, 502), ("LCP", 32.6, 511), ("SYN", 49.9, 481), ("MPP", 78.5, 574)):
    close = d / 0.240 + 185
    line("F26", "CI.%s: window closes at %.0f s; the stretch's last up second is %d, %+.0f s"
         % (sta, close, end, end - close))

# F27: the steps between neighbouring stations' onsets (D1b row Q3b): seconds
# over km, for 45, 100, 211 and 224 s at 16.5, 32.6, 49.9 and 78.5 km.
pts = [(16.5, 45), (32.6, 100), (49.9, 211), (78.5, 224)]
line("F27", "; ".join("%d s / %.1f km = %.2f s per km" % (t2 - t1, d2 - d1, (t2 - t1) / (d2 - d1))
                       for (d1, t1), (d2, t2) in zip(pts, pts[1:])))

# F28: the magnitude 0.70 earthquake of 2021-09-15 04:18:15.26 at 34.01217,
# -116.3260 (the day's earthquake listing) against CI.SRN's stretch of that
# day, 1329 s to 1375 s after 03:55:50 (D1b row Q2e). CI.SRN is at 33.8285,
# -117.7894 (D1's block for 2021-09-14). 6.5 km/s is the fastest ground speed
# of D1's row W2. The distance is stations.py's, the same formula as the study's.
import os  # noqa: E402
import sys  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stations  # noqa: E402
origin = (4 * 3600 + 18 * 60 + 15.26) - (3 * 3600 + 55 * 60 + 50)
km = stations.vincenty_km(34.01217, -116.3260, 33.8285, -117.7894)
first = origin + km / 6.5
line("F28", "origin %.0f s after the stand-in time, %.0f s after the stretch's first up "
     "second (1329); %.1f km / 6.5 km/s = %.0f s, so no wave before %.0f s, %.0f s "
     "before the stretch's last up second (1375)"
     % (origin, origin - 1329, km, km / 6.5, first, 1375 - first))

print("\n".join(out))

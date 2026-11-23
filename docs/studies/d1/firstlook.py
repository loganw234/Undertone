#!/usr/bin/env python3
"""The first look of study D1b: one launch, the ladder, two control days.

    python docs/studies/d1/firstlook.py DATA_DIR            the tables, as markdown
    python docs/studies/d1/firstlook.py --self-test

It needs numpy and the reader mseed.py beside it. It makes no request. It
reads the *.mseed files that fetch.sh put in DATA_DIR and applies the
measure that was written into the round's ledger at 08:11 on 2026-11-23,
before any waveform was fetched, and into section 8 of D1-launch-data.md:

  band power   frames of 400 samples (4 s), one starting every 100 samples;
               frame k is centred on T0 + k seconds. Mean removed, Hann
               window, squared magnitude of the discrete Fourier transform
               summed over bins with lower edge <= f < upper edge.
  bands        0.5 to 2, 2 to 8, 8 to 20, 20 to 45 Hz
  noise        per band, the median band power over frames centred from
               660 s to 60 s before T0
  ratio        band power over that noise; a second is "up" above 3
  stretch      begins on an up second, ends when two seconds in a row are
               not up; it counts with at least 10 up seconds
  windows      sound: d/0.345 - 5 to d/0.240 + 185 seconds after T0
               ground: d/6.5 - 5 to d/1.5 + 185 seconds after T0
               d from the study's ladder for 2021-09-14, typed below
  onset        the first second of the first counting stretch that begins
               between the ground window's opening and the sound window's close
  decision     per station, in the 2 to 8 Hz band of the vertical channel:
               SEEN if the launch day has a counting stretch that begins in
               a window and neither control day has one that begins in the
               same window; CANNOT TELL if a control day has one too;
               NOTHING VISIBLE if the launch day has none.

T0 is the launch catalogue's time for launch 2021-082, typed below; on a
control day the same clock time stands in for it.

WHAT IT CANNOT SEE
  - What made a signal. It sees power in a band at a time.
  - How often a control day would show a stretch. There are two control days.
  - Anything outside the 50 minutes fetched for each day.
  - The instrument's response: ratios are of raw counts to raw counts.
"""
import math
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mseed  # noqa: E402

# The catalogue's entry for launch 2021-082 reads "2021 Sep 14 0355:50" (D1b, row Q6a).
T0 = datetime(2021, 9, 14, 3, 55, 50, tzinfo=timezone.utc)
DAYS = [("2021-09-13", "control, the day before", -1),
        ("2021-09-14", "launch day", 0),
        ("2021-09-15", "control, the day after", 1)]
# km from Complex 4, the study's ladder for 2021-09-14 (D1-launch-data.md, row M4),
# and CI.LOC, the second station near the pad. CI.GATR is here because it was
# asked for; the data centre answered 404 for it.
STATIONS = [("GATR", 13.5), ("LOC", 16.5), ("LCP", 32.6), ("SYN", 49.9), ("MPP", 78.5),
            ("CDM", 120.4), ("HDH", 181.4), ("SRN", 275.0)]
BANDS = [(0.5, 2.0), (2.0, 8.0), (8.0, 20.0), (20.0, 45.0)]
COUNTING_BAND = 1          # 2 to 8 Hz
FRAME, HOP, RATE = 400, 100, 100.0
NOISE_FROM, NOISE_TO = -660, -60
UP_ABOVE = 3.0
MIN_UP = 10
C_AIR_FAST, C_AIR_SLOW = 0.345, 0.240
V_GROUND_FAST, V_GROUND_SLOW = 6.5, 1.5
SOURCE_SECONDS, TIME_MARGIN = 180.0, 5.0


def windows(d_km):
    """{"sound": (open, close), "ground": (open, close)} in seconds after T0."""
    return {"sound": (d_km / C_AIR_FAST - TIME_MARGIN,
                      d_km / C_AIR_SLOW + SOURCE_SECONDS + TIME_MARGIN),
            "ground": (d_km / V_GROUND_FAST - TIME_MARGIN,
                       d_km / V_GROUND_SLOW + SOURCE_SECONDS + TIME_MARGIN)}


def seconds_of(window):
    """The whole seconds k with floor(open) <= k < ceiling(close)."""
    return range(math.floor(window[0]), math.ceil(window[1]))


def grid(records):
    """(first sample time, samples on an even grid, NaN where nothing was recorded)."""
    first = records[0]["start"]
    last = records[-1]["start"] + timedelta(seconds=(records[-1]["nsamp"] - 1) / RATE)
    n = int(round((last - first).total_seconds() * RATE)) + 1
    x = np.full(n, np.nan)
    for r in records:
        if r["rate"] != RATE:
            raise SystemExit("REFUSED RATE: %s" % r["rate"])
        at = (r["start"] - first).total_seconds() * RATE
        if abs(at - round(at)) > 0.5:
            raise SystemExit("REFUSED OFF-GRID record at %s" % r["start"])
        i = int(round(at))
        x[i:i + r["nsamp"]] = r["samples"]
    return first, x


def band_power(first, x, t0):
    """{k: [power in each band]} for every frame that lies whole inside x, and
    the number of frames left out for a missing sample."""
    freqs = np.fft.rfftfreq(FRAME, 1.0 / RATE)
    masks = [(freqs >= lo) & (freqs < hi) for lo, hi in BANDS]
    hann = np.hanning(FRAME)
    offset = (t0 - first).total_seconds()
    out, left_out = {}, 0
    k_lo = math.ceil(-offset + FRAME / RATE / 2)
    k_hi = math.floor((len(x) - 1) / RATE - offset - FRAME / RATE / 2)
    for k in range(k_lo, k_hi + 1):
        centre = int(round((offset + k) * RATE))
        frame = x[centre - FRAME // 2:centre + FRAME // 2]
        if len(frame) != FRAME or np.isnan(frame).any():
            left_out += 1
            continue
        spec = np.abs(np.fft.rfft((frame - frame.mean()) * hann)) ** 2
        out[k] = [float(spec[m].sum()) for m in masks]
    return out, left_out


def ratios(power, band):
    """{k: power over the noise median} for one band, and the noise median."""
    quiet = [power[k][band] for k in range(NOISE_FROM, NOISE_TO + 1) if k in power]
    if len(quiet) < (NOISE_TO - NOISE_FROM + 1) // 2:
        raise SystemExit("REFUSED NOISE: only %d frames before T0" % len(quiet))
    noise = float(np.median(quiet))
    return {k: v[band] / noise for k, v in power.items()}, noise


def stretches(ratio):
    """[(first second, last up second, number of up seconds)], every stretch."""
    out, ks = [], sorted(ratio)
    start = last_up = None
    ups = misses = 0
    prev = None
    for k in ks:
        gap = prev is not None and k != prev + 1
        up = ratio[k] > UP_ABOVE
        if start is not None and (gap or (not up and misses >= 1)):
            out.append((start, last_up, ups))
            start = None
        if start is None:
            if up:
                start, last_up, ups, misses = k, k, 1, 0
        elif up:
            last_up, ups, misses = k, ups + 1, 0
        else:
            misses += 1
        prev = k
    if start is not None:
        out.append((start, last_up, ups))
    return out


def look(ratio, window):
    """What is reported for one window: the median ratio, the up seconds, the
    longest counting stretch that begins in it (or None)."""
    ks = [k for k in seconds_of(window) if k in ratio]
    if not ks:
        return None
    vals = [ratio[k] for k in ks]
    begun = [s for s in stretches(ratio)
             if s[2] >= MIN_UP and ks[0] <= s[0] <= ks[-1]]
    longest = max(begun, key=lambda s: s[2]) if begun else None
    return {"median": float(np.median(vals)), "up": sum(1 for v in vals if v > UP_ABOVE),
            "seconds": len(ks), "longest": longest, "first": min(begun)[0] if begun else None}


def onset(ratio, d_km):
    """The first counting stretch that begins between the ground window's opening
    and the sound window's close, or None."""
    w = windows(d_km)
    lo, hi = math.floor(w["ground"][0]), math.ceil(w["sound"][1])
    for s in stretches(ratio):
        if s[2] >= MIN_UP and lo <= s[0] < hi:
            return s
    return None


def load(data_dir):
    """{(station, channel, day): (ratio by band, noise by band, frames left out)}."""
    out = {}
    for sta, _d in STATIONS:
        for cha in ("HHZ", "HHE", "HHN"):
            for day, _label, shift in DAYS:
                path = os.path.join(data_dir, "CI.%s.%s.%s.mseed" % (sta, cha, day))
                if not os.path.isfile(path):
                    continue
                first, x = grid(mseed.read(path))
                power, left = band_power(first, x, T0 + timedelta(days=shift))
                per_band = [ratios(power, b) for b in range(len(BANDS))]
                out[(sta, cha, day)] = ([r for r, _n in per_band], [n for _r, n in per_band],
                                        left)
    return out


def decide(per_day):
    """SEEN, CANNOT TELL or NOTHING VISIBLE from {day: look or None} for one window."""
    launch = per_day.get("2021-09-14")
    if launch is None or launch["longest"] is None:
        return "NOTHING VISIBLE"
    for day, _label, shift in DAYS:
        if shift and per_day.get(day) and per_day[day]["longest"] is not None:
            return "CANNOT TELL"
    return "SEEN"


def cell(found):
    if found is None:
        return "no record"
    s = found["longest"]
    return "%.2f; %d of %d; %s" % (
        found["median"], found["up"], found["seconds"],
        "none" if s is None else "%d up from %d s to %d s" % (s[2], s[0], s[1]))


def band_name(b):
    return "%g to %g Hz" % BANDS[b]


def self_test():
    cases = 0
    # stretches: one miss is tolerated, two in a row end it.
    r = {k: 1.0 for k in range(0, 40)}
    for k in list(range(5, 12)) + list(range(13, 18)) + list(range(25, 28)):
        r[k] = 5.0
    assert stretches(r) == [(5, 17, 12), (25, 27, 3)], stretches(r)
    cases += 1
    # a missing second ends a stretch
    r2 = dict(r)
    del r2[9]
    assert stretches(r2)[0] == (5, 8, 4), stretches(r2)
    cases += 1
    # seconds_of: floor(open) <= k < ceiling(close)
    assert list(seconds_of((1.2, 3.1))) == [1, 2, 3]
    cases += 1
    # band power of a 5 Hz sine lies in the 2 to 8 Hz band and nowhere else
    t = np.arange(0, 1500.0, 1 / RATE)
    first = T0 - timedelta(seconds=700)
    quiet = np.random.default_rng(1).normal(0, 1.0, len(t))
    x = quiet.copy()
    on = (t >= 760) & (t < 800)
    x[on] += 30 * np.sin(2 * np.pi * 5.0 * t[on])
    power, left = band_power(first, x, T0)
    assert left == 0
    rat = [ratios(power, b)[0] for b in range(4)]
    s = [z for z in stretches(rat[1]) if z[2] >= MIN_UP]
    assert len(s) == 1 and abs(s[0][0] - 60) <= 2 and abs(s[0][1] - 99) <= 2, s
    assert not [z for z in stretches(rat[0]) if z[2] >= MIN_UP]
    assert not [z for z in stretches(rat[3]) if z[2] >= MIN_UP]
    cases += 1
    # the control: the same record with no sine gives no counting stretch
    power, _left = band_power(first, quiet, T0)
    assert not [z for z in stretches(ratios(power, 1)[0]) if z[2] >= MIN_UP]
    cases += 1
    # a frame with a missing sample is left out and counted
    y = x.copy()
    y[75000] = np.nan
    power, left = band_power(first, y, T0)
    assert left == 4, left
    cases += 1
    # decide
    hit = {"longest": (1, 20, 15)}
    miss = {"longest": None}
    assert decide({"2021-09-14": hit, "2021-09-13": miss, "2021-09-15": miss}) == "SEEN"
    assert decide({"2021-09-14": hit, "2021-09-13": hit, "2021-09-15": miss}) == "CANNOT TELL"
    assert decide({"2021-09-14": miss, "2021-09-13": hit, "2021-09-15": miss}) == "NOTHING VISIBLE"
    cases += 3
    print("OK self-test: %d cases" % cases)


def main():
    if sys.argv[1:] == ["--self-test"]:
        self_test()
        return 0
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    data = load(sys.argv[1])
    km = dict(STATIONS)
    cb = COUNTING_BAND
    print("T0 is %s UTC. A cell reads: the median ratio over the window; the up seconds "
          "of the window's seconds; the longest counting stretch that begins in it."
          % T0.strftime("%Y-%m-%d %H:%M:%S"))
    print()
    seen = []
    for wname in ("sound", "ground"):
        print("**The %s window, vertical channel, %s.**" % (wname, band_name(cb)))
        print()
        print("| station | km | window, s after T0 | the day before | launch day "
              "| the day after | reading |")
        print("|---|---|---|---|---|---|---|")
        for sta, d in STATIONS:
            w = windows(d)[wname]
            per_day = {}
            for day, _label, _shift in DAYS:
                got = data.get((sta, "HHZ", day))
                per_day[day] = look(got[0][cb], w) if got else None
            if all(v is None for v in per_day.values()):
                verdict = "NO RECORD: the data centre answered 404"
            else:
                verdict = decide(per_day)
            if verdict == "SEEN":
                seen.append((sta, wname))
            print("| CI.%s | %.1f | %d to %d | %s | %s | %s | %s |" % (
                sta, d, math.floor(w[0]), math.ceil(w[1]), cell(per_day["2021-09-13"]),
                cell(per_day["2021-09-14"]), cell(per_day["2021-09-15"]), verdict))
        print()
    print("**Onsets, vertical channel, %s.** The first counting stretch that begins between "
          "the ground window's opening and the sound window's close." % band_name(cb))
    print()
    print("| station | km | day | onset, s after T0 | last up second | up seconds "
          "| km / onset, km/s | in the sound window | in the ground window |")
    print("|---|---|---|---|---|---|---|---|---|")
    points = []
    for sta, d in STATIONS:
        for day, label, _shift in DAYS:
            got = data.get((sta, "HHZ", day))
            if not got:
                continue
            s = onset(got[0][cb], d)
            if s is None:
                print("| CI.%s | %.1f | %s | none | - | - | - | - | - |" % (sta, d, label))
                continue
            w = windows(d)
            in_s = math.floor(w["sound"][0]) <= s[0] < math.ceil(w["sound"][1])
            in_g = math.floor(w["ground"][0]) <= s[0] < math.ceil(w["ground"][1])
            speed = "%.3f" % (d / s[0]) if s[0] > 0 else "not after T0"
            print("| CI.%s | %.1f | %s | %d | %d | %d | %s | %s | %s |" % (
                sta, d, label, s[0], s[1], s[2], speed, "yes" if in_s else "no",
                "yes" if in_g else "no"))
            if day == "2021-09-14":
                points.append((sta, d, s[0]))
    print()
    stations_seen = sorted(set(s for s, _w in seen), key=lambda s: km[s])
    fit = [(d, t) for sta, d, t in points if sta in stations_seen]
    if len(fit) >= 3:
        ds, ts = np.array([p[0] for p in fit]), np.array([p[1] for p in fit])
        slope, intercept = np.polyfit(ds, ts, 1)
        resid = ts - (slope * ds + intercept)
        print("Slope of onset against distance over the %d stations read as SEEN (%s): "
              "%.2f s per km, intercept %.0f s, largest residual %.0f s. Sound is 2.90 to "
              "4.17 s per km, the ground 0.15 to 0.67."
              % (len(fit), ", ".join("CI." + s for s in stations_seen), slope, intercept,
                 float(np.abs(resid).max())))
    else:
        print("Slope of onset against distance: not taken. %d station(s) read as SEEN (%s); "
              "three are needed." % (len(stations_seen),
                                     ", ".join("CI." + s for s in stations_seen) or "none"))
    print()
    print("**Every band, the sound window, vertical channel.** A cell reads as above.")
    print()
    print("| station | km | band | the day before | launch day | the day after |")
    print("|---|---|---|---|---|---|")
    for sta, d in STATIONS:
        for b in range(len(BANDS)):
            cells = []
            for day, _label, _shift in DAYS:
                got = data.get((sta, "HHZ", day))
                cells.append(cell(look(got[0][b], windows(d)["sound"]) if got else None))
            if all(c == "no record" for c in cells):
                continue
            print("| CI.%s | %.1f | %s | %s |" % (sta, d, band_name(b), " | ".join(cells)))
    print()
    print("**The horizontal channels on launch day, the sound window, %s.**" % band_name(cb))
    print()
    print("| station | km | HHZ | HHE | HHN |")
    print("|---|---|---|---|---|")
    for sta, d in STATIONS:
        cells = []
        for cha in ("HHZ", "HHE", "HHN"):
            got = data.get((sta, cha, "2021-09-14"))
            cells.append(cell(look(got[0][cb], windows(d)["sound"]) if got else None))
        if cells[1] == "no record" and cells[2] == "no record":
            continue
        print("| CI.%s | %.1f | %s |" % (sta, d, " | ".join(cells)))
    print()
    print("**The whole 50 minutes, vertical channel, %s.** Every counting stretch, wherever "
          "it begins, and the frames left out for a missing sample." % band_name(cb))
    print()
    print("| station | day | counting stretches: up seconds (from s to s after T0) "
          "| frames left out |")
    print("|---|---|---|---|")
    for sta, d in STATIONS:
        for day, label, _shift in DAYS:
            got = data.get((sta, "HHZ", day))
            if not got:
                continue
            ss = [s for s in stretches(got[0][cb]) if s[2] >= MIN_UP]
            print("| CI.%s | %s | %s | %d |" % (
                sta, label, "; ".join("%d (%d to %d)" % (s[2], s[0], s[1]) for s in ss) or "none",
                got[2]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

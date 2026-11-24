#!/usr/bin/env python3
"""The hit rule of study D3, the faint launches, and the split it is held to. No
request, no file read but launches.tsv, the fetch's manifest and the records a
caller's loader hands it.

It is study D2's rule (docs/studies/d2/rule.py), copied and changed in two
things only: the stations, and the close of the window. D2's collect() reads
D2's own station list, so it could not be imported and pointed elsewhere.

THE RULE, as approved by the lead on 2026-11-24 at 09:29, before any record of
these stations in 2024 was fetched

  stations       CI.MPP 78.5 km, CI.CDM 120.4, CI.HDH 181.4, CI.SRN 275.0: D1's
                 2021 ladder past 50 km (D1, row M4), the stations D1b looked at.
  channel, band  the vertical channel, HHZ, 2 to 8 Hz.
  measure        D1's: d1/firstlook.py's band_power, unchanged. Frames of 400
                 samples, one a second, frame k centred on T + k seconds, mean
                 removed, Hann window, squared magnitude summed over the bins
                 with 2 <= f < 8. The noise is the median of that over the
                 frames centred 660 s to 60 s before T. The ratio is power
                 over noise.
  up             a second is up when its ratio is ABOVE 3. Exactly 3 is not up.
  window         the sound window: it opens d / 0.345 - 5 s after T, as D1's;
                 it closes d / 0.240 + SOURCE_SECONDS + 5 s after T, where D1
                 had 180 for the source's length and this study has 430. Its
                 seconds are the whole k with floor(open) <= k < ceiling(close):
                 222 to 763 at MPP, 343 to 937 at CDM, 520 to 1191 at HDH and
                 792 to 1581 at SRN.
  run            inside the window, a run begins on an up second and ends when
                 two seconds in a row are not up, or at once at a second that
                 has no frame. One not-up second between two up seconds does
                 not end it and is not counted.
  S              the largest number of up seconds in one run inside the window.
  hit            S >= M, the station's constant (constants.json).
  usable         a window is scored when at least 300 of the 601 noise frames
                 exist, their median is above zero, and at least 90% of the
                 window's seconds have a frame. Otherwise it is NO RECORD and
                 is in no count.

WHY 430. D1b's row Q4a: for the 2021 launch, which is on the constant-setting
side by name and is never scored, the stretch ended 502, 511, 481 and 574 s
after T0 at 16.5, 32.6, 49.9 and 78.5 km. The end less d / 0.240 less 5 is
428.2, 370.2, 268.1 and 241.9; the largest, rounded up to a whole ten, is 430.
No record of 2024 set it.

THE THREE TIMES A LAUNCH RECORD IS SCORED AT
  true      T = T0, the catalogue's time.
  wrong     T = T0 - (the window's close + 60 s): the same window, closing 60 s
            before T0, with its own noise before it. It cannot hold the launch.
  shifted   T = T0 - 3600 s: the catalogue moved an hour early.
A control record is scored at its own time T0'.

THE SPLIT
  launches.tsv gives each launch its side. collect() takes the side it is
  allowed to read and refuses a launch of the other side, by name, before the
  loader is called for any launch.

WHAT IT CANNOT SEE
  - What made the power. It counts seconds of power in a band.
  - The instrument's response: a ratio is of raw counts to raw counts.
  - Anything in a second that has no frame.
"""
import math
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "d1"))
import firstlook  # noqa: E402
import mseed  # noqa: E402

# km from Complex 4, D1's 2021 ladder (D1, row M4), as D1b used them.
STATIONS = [("MPP", 78.5), ("CDM", 120.4), ("HDH", 181.4), ("SRN", 275.0)]
SOURCE_SECONDS = 430
UP_ABOVE = firstlook.UP_ABOVE
BAND = firstlook.COUNTING_BAND
NOISE_FROM, NOISE_TO = firstlook.NOISE_FROM, firstlook.NOISE_TO
MIN_NOISE_FRAMES = 300
USABLE_SHARE = 0.9
M_FLOOR = firstlook.MIN_UP
WRONG_GAP = 60
SHIFT = 3600
ISO = "%Y-%m-%dT%H:%M:%S"
SETS, SCORED = "sets-constants", "scored"


class Refusal(Exception):
    def __init__(self, name, detail):
        Exception.__init__(self, "%s: %s" % (name, detail))
        self.name, self.detail = name, detail


def window(station):
    """(lo, hi): the sound window's seconds are lo <= k < hi."""
    km = dict(STATIONS)[station]
    opens = km / firstlook.C_AIR_FAST - firstlook.TIME_MARGIN
    closes = km / firstlook.C_AIR_SLOW + SOURCE_SECONDS + firstlook.TIME_MARGIN
    return math.floor(opens), math.ceil(closes)


def statistic(ratio, lo, hi):
    """S for the seconds lo <= k < hi of {k: ratio}, or None when fewer than
    90% of them have a frame."""
    present = sum(1 for k in range(lo, hi) if k in ratio)
    if present < USABLE_SHARE * (hi - lo):
        return None
    best = run = misses = 0
    for k in range(lo, hi):
        if k not in ratio:
            run = misses = 0
        elif ratio[k] > UP_ABOVE:
            run, misses = run + 1, 0
            best = max(best, run)
        elif run:
            misses += 1
            if misses >= 2:
                run = misses = 0
    return best


def ratio_at(first, x, t, lo, hi):
    """({k: ratio} for lo <= k < hi, None) at reference time t, or (None, why)."""
    rate = firstlook.RATE
    half = firstlook.FRAME / rate / 2
    i0 = max(0, int(math.floor(((t - first).total_seconds() + NOISE_FROM - half - 1) * rate)))
    i1 = min(len(x), int(math.ceil(((t - first).total_seconds() + hi + half + 1) * rate)))
    if i1 - i0 < firstlook.FRAME:
        return None, "the record does not reach this time"
    power, _left = firstlook.band_power(first + timedelta(seconds=i0 / rate), x[i0:i1], t)
    quiet = [power[k][BAND] for k in range(NOISE_FROM, NOISE_TO + 1) if k in power]
    if len(quiet) < MIN_NOISE_FRAMES:
        return None, "%d noise frames of %d" % (len(quiet), NOISE_TO - NOISE_FROM + 1)
    noise = float(np.median(quiet))
    if not noise > 0:
        return None, "the noise is zero"
    return {k: power[k][BAND] / noise for k in range(lo, hi) if k in power}, None


def score_at(record, t, station):
    """(S, None) for one window of one record at reference time t, or (None, why)."""
    if record is None:
        return None, "no file"
    first, x = record
    lo, hi = window(station)
    try:
        ratio, why = ratio_at(first, x, t, lo, hi)
    except Exception as e:
        # a window the measure cannot be taken on is NO RECORD, named with why;
        # it is never given a number
        return None, "NOT-MEASURED: %s: %s" % (type(e).__name__, e)
    if ratio is None:
        return None, why
    s = statistic(ratio, lo, hi)
    if s is None:
        return None, "fewer than 90% of the window's seconds have a frame"
    return s, None


def read_record(path):
    """(first sample time, samples on an even grid with NaN in gaps), or None if
    there is no file. A file the reader refuses raises Refusal."""
    if not os.path.isfile(path):
        return None
    try:
        # in time order: firstlook.grid takes the first record's time as the
        # grid's start and would misplace a record that began before it.
        records = sorted(mseed.read(path), key=lambda r: r["start"])
        return firstlook.grid(records)
    except (Exception, SystemExit) as e:
        # whatever the reader or the grid refuses is NO RECORD, with its reason
        raise Refusal("RECORD-NOT-READ", "%s: %s: %s" % (os.path.basename(path),
                                                        type(e).__name__, e))


def record_name(station, tag, days):
    """The file a record was saved under (d3launches.py's naming). days is None
    for the launch record."""
    kind = "launch" if days is None else "c%+03d" % days
    return "CI.%s.HHZ.%s.%s.mseed" % (station, tag, kind)


def read_manifest(path):
    """{name: (status, sha256)}: the last line of each name in the fetch's manifest."""
    out = {}
    for line in open(path, encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        out[f[0]] = (f[3], f[5])
    return out


def not_fetched(launches, tags, manifest, data_dir):
    """The record names of these launches that the manifest does not settle: no
    line, a line that is neither 200 nor 404, or a 200 whose file is missing.
    It opens no record."""
    by_tag = dict((row["tag"], row) for row in launches)
    out = []
    for tag in tags:
        if by_tag[tag]["records"] != "fetched":
            continue
        for station, _km in STATIONS:
            for days in [None] + by_tag[tag]["controls"]:
                name = record_name(station, tag, days)
                row = manifest.get(name)
                if row is None or row[0] not in ("200", "404") or (
                        row[0] == "200" and not os.path.isfile(os.path.join(data_dir, name))):
                    out.append(name)
    return out


def make_loader(data_dir, manifest):
    """loader(tag, station, days) for collect(): what was fetched is what the
    manifest says. A name answered 404 is no file. A file whose SHA-256 is not
    its manifest line's is refused."""
    import hashlib

    def loader(tag, station, days):
        name = record_name(station, tag, days)
        row = manifest.get(name)
        if row is None:
            raise Refusal("NOT-IN-MANIFEST", name)
        if row[0] != "200":
            return None
        path = os.path.join(data_dir, name)
        if not os.path.isfile(path):
            raise Refusal("FILE-MISSING", name)
        if hashlib.sha256(open(path, "rb").read()).hexdigest() != row[1]:
            raise Refusal("FILE-NOT-AS-FETCHED", name)
        return read_record(path)
    return loader


def read_launches(path):
    """[{"n", "side", "tag", "t0", "flight", "records", "controls": [days]}]."""
    out = []
    for line in open(path, encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        if f[1] not in (SETS, SCORED):
            raise Refusal("BAD-SIDE", "%s: %r" % (f[2], f[1]))
        out.append({"n": int(f[0]), "side": f[1], "tag": f[2],
                    "t0": datetime.strptime(f[3], ISO).replace(tzinfo=timezone.utc),
                    "flight": f[4], "records": f[5],
                    "controls": [int(d) for d in f[6].split(",") if d]})
    tags = [row["tag"] for row in out]
    if len(set(tags)) != len(tags):
        raise Refusal("LAUNCH-ON-BOTH-SIDES", "a tag occurs twice in %s" % path)
    return out


def collect(launches, tags, side, loader):
    """One row for every window of the launches named: (tag, station, kind, days,
    S or None, why). kind is "launch", "control", "wrong" or "shifted".

    side is the side this caller may read. A tag of the other side is refused
    by name BEFORE the loader is called for any launch. loader(tag, station,
    days) returns read_record's value; days is None for the launch record."""
    by_tag = dict((row["tag"], row) for row in launches)
    refused = {SCORED: "SCORED-A-CONSTANT-SETTING-LAUNCH", SETS: "CONSTANTS-FROM-A-SCORED-LAUNCH"}
    for tag in tags:
        if tag not in by_tag:
            raise Refusal("UNKNOWN-LAUNCH", tag)
        if by_tag[tag]["side"] != side:
            raise Refusal(refused[side], tag)
    rows = []
    for tag in tags:
        launch = by_tag[tag]
        if launch["records"] != "fetched":
            continue
        t0 = launch["t0"]
        for station, _km in STATIONS:
            _lo, hi = window(station)
            try:
                rec, why = loader(tag, station, None), None
            except Refusal as e:
                rec, why = None, str(e)
            for kind, t in (("launch", t0), ("wrong", t0 - timedelta(seconds=hi + WRONG_GAP)),
                            ("shifted", t0 - timedelta(seconds=SHIFT))):
                s, w = score_at(rec, t, station)
                rows.append((tag, station, kind, 0, s, why or w))
            for days in launch["controls"]:
                try:
                    rec, why = loader(tag, station, days), None
                except Refusal as e:
                    rec, why = None, str(e)
                s, w = score_at(rec, t0 + timedelta(days=days), station)
                rows.append((tag, station, "control", days, s, why or w))
    return rows


def p_fisher(a, b, n_l, n_c):
    """Fisher's exact test, one-sided: the chance of a or more hits among the
    n_l launch windows when the a + b hits fall at random among n_l + n_c."""
    total, hits = n_l + n_c, a + b
    num = sum(math.comb(hits, x) * math.comb(total - hits, n_l - x)
              for x in range(a, min(hits, n_l) + 1))
    return num / math.comb(total, n_l)


def needed(b, n_l, n_c, level):
    """The smallest launch-hit count that rejects at level, or None."""
    for a in range(0, n_l + 1):
        if p_fisher(a, b, n_l, n_c) <= level:
            return a
    return None

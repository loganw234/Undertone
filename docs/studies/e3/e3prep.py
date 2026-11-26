#!/usr/bin/env python3
"""Stage E3's records, from the fetched files to the recordings the model replays: the frozen rule applied.

    python docs/studies/e3/e3prep.py DATA OUT GCAT_LAUNCH_FILE STATIONS_FILE

  DATA               the folder D2's fetch.py wrote docs/studies/e3/requests.tsv into
  OUT                where the recordings go, one a block, OUT/<station>/<role>-<nnn>.und;
                     outside the repository, never committed
  GCAT_LAUNCH_FILE   GCAT's launch list as study D1b fetched it, held to rule.json's SHA-256
  STATIONS_FILE      study D3's station answer, held to rule.json's SHA-256

It makes no request. It reads every number from vectors/e3s/rule.json and writes
vectors/e3s/blocks.json: for each station, every block of every day with what
became of it, the blocks used in each role with their SHA-256, the losses by
rule, and the calibration's figures and amplitude. The injection sets are worked
from that file by e3sets.py, which imports nothing of the model.

THE RULE (the design in the round's ledger, 2026-11-25 20:57, sections 2, 4 and 5,
ruled by the lead at 21:02; written before any request for records):

  blocks     each day of the rule from 00:00:00 UTC in blocks of block_frames
             frames (655.36 s at 100 samples a second); blocks_per_day of them
             (the day's last part block is not used). A block's frames are the
             samples whose times fall in it, in time order.
  keep       a block is kept only if, in this order, each holds; a block lost is
             counted under the first rule it fails:
               1 continuity  the day's file was answered and read by D1's reader;
                             exactly block_frames samples, from records of the
                             station's channel at 100 samples a second, inside
                             one channel epoch of the station file, each sample
                             10 ms after the one before to within half a sample
               2 flat        its samples are not all equal
               3 events      it meets no interval an event of SCEDC's catalogue
                             excludes (below)
               4 launches    it meets no interval a GCAT launch from a
                             Vandenberg site code excludes (below)
               5 range       a calibration block: every sample in -32768..32767;
                             a training or held-out block: in -32768 + H ..
                             32767 - H, H the largest magnitude of the injected
                             integers
  events     T the origin time, M the listed magnitude, D the great-circle
             distance in km from the station on a sphere of earth_radius_km (an
             event listed at latitude 0 and longitude 0 is taken at D = 0).
             A local or regional event (geographic type l or r) with a magnitude
             that is a number, and D <= radius_km_at_m1 * 2^(M - 1), excludes
             [T - before_s, T + D / speed_km_s + duration_s_at_m1 * 2^(max(M, 1) - 1)].
             Any other row (a teleseism, another geographic type, a magnitude
             that is not a number) excludes [T, T + teleseism_after_s].
  launches   an entry timed to the second excludes [T0 + second[0], T0 + second[1]];
             to the minute, [T0 + minute[0], T0 + minute[1]]; to the day only, the
             whole day and day_after_s after it. "Marked uncertain" changes nothing.
             An entry coarser than a day is not covered by the design's rule: it
             excludes nothing and is named in blocks.json.
  roles      a station's kept blocks in time order: the first `calibration`
             (rule 5 without H), then `training`, then `held_out` (rule 5 with
             H). H is known once the calibration is.
  amplitude  on the calibration blocks, the scores of E0's matched filter (the
             integers of model.weights.matched_filter("s16x1", e0, (1,))) at
             score_first + score_stride * g inside each block; t is
             stats.recovery.threshold_from_scores(scores, pfa)["threshold"] and
             med their median. The amplitude is num / den for the least positive
             integer num at which sum_k c_k * inject.scaled_pulse(e0, num, den)_k
             reaches t - med.
  short      a station that keeps fewer blocks than the three roles need is
             NOT_ENOUGH_NOISE: it is written with its counts and has no
             recordings and no amplitude. No day is added.

TWO OUTCOMES ONLY. A precondition that fails stops the prep with a refusal by
name, before anything is written: a fetched file whose SHA-256 is not its
manifest line's, or a request with no manifest line answered 200 or 404
(FETCH_NOT_SETTLED); a catalogue or station file of another SHA-256
(INPUT_SHA256); an event row whose time cannot be read (EVENT_ROW); an
amplitude past 2^31 - 1 (AMPLITUDE_RANGE); a sample past 32 bits in a block
rules 1 to 4 keep (SAMPLE_WIDTH). A day's file that D1's reader refuses is not
a refusal of the prep: its blocks are lost under rule 1, and the reason is
written in blocks.json.

WHAT IT CANNOT SEE
  - Anything in a kept block that no rule names (the design, section 2).
  - Whether D1's reader decodes a record right where both its first and last
    samples are right (D1's mseed.py, its own limits).
  - A station clock that is wrong: times are the records' own.
"""
import hashlib
import json
import math
import os
import struct
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
D1 = os.path.join(os.path.dirname(HERE), "d1")
for p in (ROOT, D1):
    if p not in sys.path:
        sys.path.insert(0, p)
import catalogue  # noqa: E402  (D1's: the launch list's reader)
import mseed  # noqa: E402  (D1's: the miniSEED reader)
from spec import constants as C  # noqa: E402
from model import inject, source, weights  # noqa: E402
from stats import recovery  # noqa: E402

RULE = os.path.join(ROOT, "vectors", "e3s", "rule.json")
BLOCKS = os.path.join(ROOT, "vectors", "e3s", "blocks.json")
REQUESTS = os.path.join(HERE, "requests.tsv")
MANIFEST = os.path.join(HERE, "manifest.tsv")
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
SAMPLE_US = 10000
LOSSES = ("continuity", "flat", "events", "launches", "range")
ROLES = ("calibration", "training", "held_out")


class PrepRefusal(Exception):
    def __init__(self, name, detail):
        self.name = name
        super().__init__("%s: %s" % (name, detail))


def load_rule(path=RULE):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def us(dt):
    """A datetime as whole microseconds since 1970, exactly."""
    d = dt - EPOCH
    return (d.days * 86400 + d.seconds) * 1000000 + d.microseconds


def day_us(day):
    return us(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc))


def sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ------------------------------------------------------------------ the inputs, held

def settled(data_dir, requests_path=REQUESTS, manifest_path=MANIFEST):
    """{name: "200" or "404"} for every request, or FETCH_NOT_SETTLED."""
    names = []
    for line in open(requests_path, encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        names.append(line.split("\t")[0])
    last = {}
    for line in open(manifest_path, encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        last[f[0]] = (f[3], f[5])
    out = {}
    for name in names:
        row = last.get(name)
        if row is None or row[0] not in ("200", "404"):
            raise PrepRefusal("FETCH_NOT_SETTLED", "%s: manifest says %r" % (name, row))
        if row[0] == "200":
            path = os.path.join(data_dir, name)
            if not os.path.isfile(path) or sha256_file(path) != row[1]:
                raise PrepRefusal("FETCH_NOT_SETTLED", "%s: not on disk with its manifest SHA-256" % name)
        out[name] = row[0]
    return out


def held(path, want):
    got = sha256_file(path)
    if got != want:
        raise PrepRefusal("INPUT_SHA256", "%s has SHA-256 %s, not %s" % (path, got, want))


def station_epochs(path, rule):
    """{station: (lat, lon, [(start_us, end_us), ...])} for the rule's channel, from the station answer."""
    out = {}
    for line in open(path, encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        f = [c.strip() for c in line.rstrip("\n").split("|")]
        net, sta, _loc, cha = f[0], f[1], f[2], f[3]
        if net != rule["network"] or cha != rule["channel"] or sta not in rule["stations"]:
            continue
        lat, lon = float(f[4]), float(f[5])
        a = us(datetime.strptime(f[15], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc))
        b = us(datetime.strptime(f[16], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc))
        prev = out.get(sta, (lat, lon, []))
        out[sta] = (lat, lon, prev[2] + [(a, b)])
    return out


# ------------------------------------------------------------------ the excluded intervals

def parse_events(text):
    """The rows of an event-service text answer: dicts of id, t (us), lat, lon, gt, m (a float or None)."""
    out = []
    for line in text.split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        f = [c.strip() for c in line.split("|")]
        if len(f) < 11:
            raise PrepRefusal("EVENT_ROW", "a row of %d fields: %r" % (len(f), line[:120]))
        try:
            t = datetime.strptime(f[1], "%Y/%m/%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)
        except ValueError:
            raise PrepRefusal("EVENT_ROW", "a time that cannot be read: %r" % line[:120])
        try:
            lat, lon = float(f[2]), float(f[3])
        except ValueError:
            lat, lon = 0.0, 0.0
        try:
            m = float(f[10])
            if not math.isfinite(m):
                m = None
        except ValueError:
            m = None
        out.append({"id": f[0], "t": us(t), "lat": lat, "lon": lon, "gt": f[8], "m": m})
    return out


def distance_km(lat1, lon1, lat2, lon2, radius):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(min(1.0, math.sqrt(a)))


def event_interval(ev, lat, lon, rule):
    """The interval (us, us) an event excludes at a station, or None."""
    e = rule["events"]
    m = ev["m"]
    if ev["gt"] in e["local_regional_types"] and m is not None:
        d = 0.0 if (ev["lat"] == 0.0 and ev["lon"] == 0.0) else \
            distance_km(lat, lon, ev["lat"], ev["lon"], e["earth_radius_km"])
        if d > e["radius_km_at_m1"] * 2.0 ** (m - 1.0):
            return None
        after = d / e["speed_km_s"] + e["duration_s_at_m1"] * 2.0 ** (max(m, 1.0) - 1.0)
        return (ev["t"] - int(round(e["before_s"] * 1e6)), ev["t"] + int(math.ceil(after * 1e6)))
    return (ev["t"], ev["t"] + int(e["teleseism_after_s"] * 1e6))


def launch_intervals(rows, rule, lo_us, hi_us):
    """(intervals, coarse): the intervals GCAT's launches from Vandenberg's site codes exclude,
    those meeting [lo, hi]; and the tags of entries there whose date is coarser than a day, which
    the rule does not cover and which exclude nothing (they are listed in blocks.json)."""
    L = rule["launches"]
    out, coarse = [], []
    for r in rows:
        if r["Launch_Site"] not in L["sites"]:
            continue
        t, precision = catalogue.when(r["Launch_Date"])
        if t is not None:
            span = L["second"] if precision.startswith("the second") else L["minute"]
            a, b = us(t) + span[0] * 1000000, us(t) + span[1] * 1000000
        else:
            p = r["Launch_Date"].replace("?", "").split()
            if len(p) >= 3 and p[0].isdigit() and p[1] in catalogue.MONTHS and p[2].isdigit():
                day = datetime(int(p[0]), catalogue.MONTHS.index(p[1]) + 1, int(p[2]), tzinfo=timezone.utc)
                a, b = us(day), us(day + timedelta(days=1)) + L["day_after_s"] * 1000000
            else:
                if p and p[0].isdigit() and lo_us <= us(datetime(int(p[0]), 12, 31, tzinfo=timezone.utc)) \
                        and us(datetime(int(p[0]), 1, 1, tzinfo=timezone.utc)) <= hi_us:
                    coarse.append(r.get("Launch_Tag", "?"))
                continue
        if a <= hi_us and b >= lo_us:
            out.append((a, b))
    return out, coarse


def meets(start, end, intervals):
    """Does the half-open block [start, end) meet any closed interval [a, b]?"""
    return any(a < end and b >= start for a, b in intervals)


# ------------------------------------------------------------------ the samples and the blocks

def day_samples(records, rule, day0):
    """(t, x): every sample of the station's channel in the day's records, time-ordered,
    t in us since day0 and x as int64. Records of another channel or rate are dropped."""
    keep = [r for r in records if (r["network"], r["station"], r["channel"]) == (rule["network"], rule["sta"], rule["channel"])
            and r["location"] in ("", rule["location"].replace("-", "")) and r["rate"] == float(rule["rate"])]
    keep.sort(key=lambda r: us(r["start"]))
    ts, xs = [], []
    for r in keep:
        n = len(r["samples"][:r["nsamp"]])
        ts.append(us(r["start"]) - day0 + SAMPLE_US * np.arange(n, dtype=np.int64))
        xs.append(np.asarray(r["samples"][:r["nsamp"]], dtype=np.int64))
    if not ts:
        return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64)
    t, x = np.concatenate(ts), np.concatenate(xs)
    order = np.argsort(t, kind="stable")
    return t[order], x[order]


def cut(t, x, rule):
    """For each block of the day: its samples (int64, block_frames of them) or None where rule 1 fails."""
    frames, half = rule["block_frames"], rule["half_sample_us"]
    span = frames * SAMPLE_US
    out = []
    which = np.floor_divide(t, span) if t.size else t
    for b in range(rule["blocks_per_day"]):
        lo, hi = np.searchsorted(which, b, "left"), np.searchsorted(which, b, "right")
        if hi - lo != frames:
            out.append(None)
            continue
        d = np.diff(t[lo:hi])
        if d.size and (d.min() < SAMPLE_US - half or d.max() > SAMPLE_US + half):
            out.append(None)
            continue
        out.append(x[lo:hi].copy())
    return out


def within_epoch(start, end, epochs):
    return any(a <= start and end <= b for a, b in epochs)


def response(c, num, den):
    """(the matched filter's response to the injected integers at num / den, those integers)."""
    d = inject.scaled_pulse(C.PULSE_IDS["e0"], num, den)
    return sum(ck * dk for ck, dk in zip(c, d)), d


def lowest(cal_scores, rule):
    """(num, the injected integers, threshold record, med, target): the amplitude rule of the docstring.

    The least num is found by bisection. That is exact because the response never falls as num
    grows: each coefficient has its pulse sample's sign or is zero (the quantising rule keeps
    signs), and each rounded sample moves with num in its own sign, so every term c_k d_k is
    non-decreasing in num. The sign condition is checked here, and the search refuses if it fails."""
    a = rule["amplitude"]
    thr = recovery.threshold_from_scores(np.asarray(cal_scores, dtype=np.int64), a["pfa"])
    med = float(np.median(np.asarray(cal_scores, dtype=np.int64)))
    target = thr["threshold"] - med
    c = matched_coefficients()
    if any(ck * pk < 0 for ck, pk in zip(c, C.PULSES["e0"])):
        raise PrepRefusal("AMPLITUDE_RANGE", "a coefficient of the other sign to its pulse sample")
    top = (1 << 31) - 1
    hi = 1
    while response(c, hi, a["den"])[0] < target:
        if hi == top:
            raise PrepRefusal("AMPLITUDE_RANGE", "no amplitude up to 2^31 - 1 over %d reaches %r" % (a["den"], target))
        hi = min(top, 2 * hi)
    lo = 0                                     # response(lo) < target, or lo = 0, which no amplitude is
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if response(c, mid, a["den"])[0] >= target:
            hi = mid
        else:
            lo = mid
    return hi, response(c, hi, a["den"])[1], thr, med, target


def matched_coefficients():
    """E0's matched filter, as E1's facts() has it: the integers of the model's own blob."""
    return list(weights.unpack(weights.matched_filter("s16x1", C.PULSES["e0"], (1,)))["filters"][0][0])


def calibration_scores(blocks, rule):
    """The matched filter's scores at score_first + score_stride * g inside each calibration block."""
    a = rule["amplitude"]
    c = np.array(matched_coefficients(), dtype=np.int64)
    taps = len(c)
    out = []
    for x in blocks:
        ends = np.arange(a["score_first"], len(x), a["score_stride"])
        w = x[ends[:, None] - (taps - 1) + np.arange(taps)[None, :]]
        out.append(w @ c)
    return np.concatenate(out)


def payload(x):
    """A block's samples as a recording's payload: two's complement, little-endian, 16 bits."""
    x = np.asarray(x)
    if x.size and (int(x.min()) < -32768 or int(x.max()) > 32767):
        raise PrepRefusal("SAMPLE_WIDTH", "a sample outside 16 bits in a block to be recorded")
    return x.astype("<i2").tobytes()


def recording_bytes(x):
    """The bytes model.source.recording("s16x1", frames) gives for these samples, made in numpy.

    The header's fields in model.source.HEADER's order; tests/test_e3s_noise_rule.py holds the
    result equal to model.source.recording's on blocks of its own, and Replay checks every field
    and the payload's hash again when the full run reads it."""
    body = payload(x)
    values = {"magic": source.MAGIC, "version": source.FORMAT_VERSION, "sample_bits": 16, "channels": 1,
              "reserved": 0, "frames": len(x), "sha256": hashlib.sha256(body).digest()}
    head = b"".join(values[n] if isinstance(values[n], bytes) else values[n].to_bytes(size, "little")
                    for n, size in source.HEADER)
    return head + body


def read_day(path):
    """(records, None) by D1's reader, or ([], the reason) for a file it cannot read."""
    try:
        return mseed.read(path), None
    except (mseed.Refusal, struct.error, UnicodeDecodeError, ValueError, IndexError, OverflowError) as e:
        return [], "%s: %s" % (type(e).__name__, str(e)[:200])


def station_blocks(sta, rule, data_dir, answered, epochs, events, launches, files=None, progress=None):
    """Every block of every day of one station, with its status, in time order.

    Each entry: day, block, start (us), status ("kept" or the rule it failed first), and for a
    kept block its samples (int32). Rules 1 to 4 here; rule 5 needs the roles (assign). `files`,
    a list, gets one row a day: its name, the answer, the records and samples read, and the
    reader's refusal if it refused."""
    lat, lon, spans = epochs.get(sta, (0.0, 0.0, []))
    rule_sta = dict(rule, sta=sta)
    excluded = [iv for iv in (event_interval(e, lat, lon, rule) for e in events) if iv]
    span = rule["block_frames"] * SAMPLE_US
    out = []
    for day in rule["days"]:
        day0 = day_us(day)
        name = "%s.%s.%s.%s.mseed" % (rule["network"], sta, rule["channel"], day)
        blocks = [None] * rule["blocks_per_day"]
        row = {"file": name, "answer": answered.get(name), "records": 0, "samples": 0, "refused": None}
        if answered.get(name) == "200":
            recs, why = read_day(os.path.join(data_dir, name))
            t, x = day_samples(recs, rule_sta, day0)
            row.update(records=len(recs), samples=int(x.size), refused=why)
            del recs
            blocks = cut(t, x, rule)
            del t, x
        if files is not None:
            files.append(row)
        for b, xs in enumerate(blocks):
            start = day0 + b * span
            end = start + span
            entry = {"day": day, "block": b, "start": start}
            if xs is None or not within_epoch(start, end, spans):
                entry["status"] = "continuity"
            elif int(xs.min()) == int(xs.max()):
                entry["status"] = "flat"
            elif meets(start, end, excluded):
                entry["status"] = "events"
            elif meets(start, end, launches):
                entry["status"] = "launches"
            else:
                if int(xs.min()) < -(1 << 31) or int(xs.max()) >= 1 << 31:
                    raise PrepRefusal("SAMPLE_WIDTH", "%s %s block %d: a sample past 32 bits" % (sta, day, b))
                entry["status"] = "kept"
                entry["x"] = xs.astype(np.int32)
            out.append(entry)
        if progress:
            progress("  %s %s: %d of %d blocks past rules 1 to 4" % (sta, day, sum(
                1 for e in out if e["day"] == day and e["status"] == "kept"), rule["blocks_per_day"]))
    return out


def assign(entries, rule):
    """Rule 5 and the roles, in time order. Returns (used, figures); `used` is {role: [entry, ...]}.

    The calibration is the first `calibration` blocks inside the 16-bit range; then the amplitude
    and H; then training and held-out blocks inside the range less H. A station short of blocks
    gets used blocks of the roles it filled and figures with "refused": "NOT_ENOUGH_NOISE"."""
    need = rule["use"]
    used = {r: [] for r in ROLES}
    figures = {"refused": None}
    h = None
    for e in entries:
        if e["status"] != "kept":
            continue
        x = e["x"]
        if len(used["calibration"]) < need["calibration"]:
            lo, hi = -32768, 32767
        else:
            lo, hi = -32768 + h, 32767 - h
        if int(x.min()) < lo or int(x.max()) > hi:
            e["status"] = "range"
            continue
        if len(used["calibration"]) < need["calibration"]:
            e["role"] = "calibration"
            used["calibration"].append(e)
            if len(used["calibration"]) == need["calibration"]:
                scores = calibration_scores([b["x"] for b in used["calibration"]], rule)
                num, d, thr, med, target = lowest(scores, rule)
                h = max(abs(v) for v in d)
                figures.update(scores=int(scores.size), k=thr["k"], threshold=thr["threshold"], median=med,
                               target=target, amplitude_num=num, amplitude_den=rule["amplitude"]["den"],
                               injected=list(d), H=h)
            continue
        for role in ("training", "held_out"):
            if len(used[role]) < need[role]:
                e["role"] = role
                used[role].append(e)
                break
        else:
            e["status"] = "unused"
    if any(len(used[r]) < need[r] for r in ROLES):
        figures["refused"] = "NOT_ENOUGH_NOISE"
    return used, figures


def summary(sta, entries, used, figures, files=()):
    losses = {k: sum(1 for e in entries if e["status"] == k) for k in LOSSES}
    kept = sum(1 for e in entries if e["status"] in ("kept", "unused"))
    out = {"station": sta, "blocks": len(entries), "losses": losses, "kept": kept,
           "used": {r: len(used[r]) for r in ROLES}, "figures": figures, "files": list(files),
           "lost": [[e["day"], e["block"], e["status"]] for e in entries if e["status"] in LOSSES]}
    rows = []
    for role in ROLES:
        for i, e in enumerate(used[role]):
            rows.append({"role": role, "n": i, "day": e["day"], "block": e["block"],
                         "start_utc": (EPOCH + timedelta(microseconds=e["start"])).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                         "file": "%s/%s-%03d.und" % (sta, role, i),
                         "payload_sha256": hashlib.sha256(payload(e["x"])).hexdigest()})
    out["blocks_used"] = rows
    return out


def main(argv):
    if len(argv) != 4:
        raise SystemExit(__doc__)
    data_dir, out_dir, gcat, stations_file = argv
    rule = load_rule()
    held(gcat, rule["launches"]["catalogue_sha256"])
    held(stations_file, rule["stations_file_sha256"])
    answered = settled(data_dir)
    epochs = station_epochs(stations_file, rule)
    events = []
    seen = set()
    for day in rule["days"]:
        name = "scedc-events-%s.txt" % day
        if answered.get(name) == "200":
            with open(os.path.join(data_dir, name), encoding="utf-8", errors="replace") as f:
                for ev in parse_events(f.read()):
                    if ev["id"] not in seen:
                        seen.add(ev["id"])
                        events.append(ev)
    _head, _updated, rows = catalogue.load(gcat)
    lo = day_us(rule["days"][0]) - 86400 * 1000000
    hi = day_us(rule["days"][-1]) + 2 * 86400 * 1000000
    launches, coarse = launch_intervals(rows, rule, lo, hi)
    print("E3 prep: %d events from %d days' answers; %d launch intervals near the days; %d entries coarser "
          "than a day" % (len(events), len(rule["days"]), len(launches), len(coarse)), flush=True)
    result = {"what": "Stage E3's blocks, written by docs/studies/e3/e3prep.py from the fetched files under "
                      "vectors/e3s/rule.json. Each station: every block's fate, the blocks used in each role with "
                      "the SHA-256 of its payload, and the calibration's figures.",
              "rule_sha256": sha256_file(RULE), "events": len(events),
              "launch_intervals_utc": [[(EPOCH + timedelta(microseconds=a)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                        (EPOCH + timedelta(microseconds=b)).strftime("%Y-%m-%dT%H:%M:%SZ")]
                                       for a, b in sorted(launches)],
              "launch_entries_coarser_than_a_day": coarse, "stations": []}
    for sta in rule["stations"]:
        files = []
        entries = station_blocks(sta, rule, data_dir, answered, epochs, events, launches, files=files,
                                 progress=lambda s: print(s, flush=True))
        used, figures = assign(entries, rule)
        s = summary(sta, entries, used, figures, files)
        result["stations"].append(s)
        print("E3 prep %s: %d blocks; kept %d; lost %s; used %s; %s" % (
            sta, s["blocks"], s["kept"], s["losses"], s["used"],
            "REFUSED NOT_ENOUGH_NOISE" if figures["refused"] else "amplitude %d/%d, H %d" % (
                figures["amplitude_num"], figures["amplitude_den"], figures["H"])), flush=True)
        if figures["refused"] is None:
            os.makedirs(os.path.join(out_dir, sta), exist_ok=True)
            for role in ROLES:
                for i, e in enumerate(used[role]):
                    with open(os.path.join(out_dir, sta, "%s-%03d.und" % (role, i)), "wb") as f:
                        f.write(recording_bytes(e["x"]))
        for e in entries:
            e.pop("x", None)
    with open(BLOCKS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, indent=1)
        f.write("\n")
    short = [s["station"] for s in result["stations"] if s["figures"]["refused"]]
    print("E3 prep: wrote vectors/e3s/blocks.json; %s" % ("every station has its blocks" if not short else
                                                           "NOT_ENOUGH_NOISE at %s" % ", ".join(short)))
    return 1 if short else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except PrepRefusal as e:
        print("REFUSED %s" % e)
        sys.exit(2)

"""Stage E3's noise rule and its preparation, held on inputs made here: no record is fetched or read.

The rule is vectors/e3s/rule.json; docs/studies/e3/e3requests.py makes the requests from it and
docs/studies/e3/e3prep.py applies it to the fetched files (the design in the round's ledger,
2026-11-25 20:57, sections 2, 4 and 5, ruled by the lead at 21:02). Each keep rule here is
broken one way at a time on a stream written in this file and must lose exactly the block it
names; each figure of the rule is held to the design's; the recording the prep writes is held
equal to model.source.recording's; and D1's miniSEED reader is run on a file this test writes.

What these tests cannot see: real records. A rule that is right on these inputs and wrong on
SCEDC's answers in a way no input here has (another record length, an encoding D1's reader
refuses, a catalogue row of another shape) passes here; blocks.json says what each day's file
held, and a refused file's reason, so the full run's record shows it.
"""
import hashlib
import json
import math
import os
import struct
import sys
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E3 = os.path.join(ROOT, "docs", "studies", "e3")
for p in (ROOT, E3):
    if p not in sys.path:
        sys.path.insert(0, p)

import e3prep as P  # noqa: E402
import e3requests as Q  # noqa: E402
import mseed  # noqa: E402  (D1's, on the path through e3prep)
from spec import constants as C  # noqa: E402
from model import source  # noqa: E402

RULE = P.load_rule()
DAY = "2024-01-08"
DAY0 = P.day_us(DAY)


def small_rule(**changes):
    """The rule with blocks of 64 frames and 5 a day, so that a day is 320 samples."""
    r = json.loads(json.dumps(RULE))
    r.update(block_frames=64, blocks_per_day=5, sta="MPP")
    r.update(changes)
    return r


def record(start_us, samples, sta="MPP", cha="HHZ", rate=100.0, net="CI", loc=""):
    """A record as D1's reader returns one: the fields day_samples reads."""
    return {"network": net, "station": sta, "location": loc, "channel": cha, "rate": rate,
            "start": P.EPOCH + timedelta(microseconds=start_us), "nsamp": len(samples), "samples": list(samples)}


def ramp(n, first=0):
    return [(first + 7 * i) % 1000 - 500 for i in range(n)]


# ------------------------------------------------------------------ the rule's figures

def test_e3s_noise_rule_the_rule_is_the_designs():
    assert RULE["stations"] == ["MPP", "CDM", "HDH", "SRN"] and RULE["channel"] == "HHZ" and RULE["rate"] == 100
    first = datetime(2024, 1, 8, tzinfo=timezone.utc)
    assert RULE["days"] == [(first + timedelta(days=8 * i)).strftime("%Y-%m-%d") for i in range(8)]
    assert RULE["days"][-1] == "2024-03-04" and first.weekday() == 0
    assert sorted({(first + timedelta(days=8 * i)).weekday() for i in range(8)}) == list(range(7)), "each weekday once"
    assert RULE["block_frames"] == 65536 and RULE["blocks_per_day"] == 131 == 8640000 // 65536
    assert sum(RULE["use"].values()) == 544 == 16 + 128 + 400
    assert RULE["profile"] == "s16x1" and RULE["shift"] == 0
    assert RULE["named_model"] == {"training_blocks": 32, "records": 32 * 65536 // 128}
    assert RULE["curve_training_blocks"] == [2, 8, 128] and RULE["use"]["training"] == 128
    assert (RULE["pfa"], RULE["z"], RULE["resamples"]) == (0.01, 4.0, 1000)
    assert RULE["seeds"]["carry"] == RULE["seeds"]["comparison"] + 20
    ev = RULE["events"]
    assert (ev["radius_km_at_m1"], ev["before_s"], ev["speed_km_s"], ev["duration_s_at_m1"], ev["teleseism_after_s"],
            ev["before_day_s"]) == (50, 30, 3, 120, 10800, 10800)
    assert RULE["launches"]["second"] == [-60, 1800] and RULE["launches"]["minute"] == [-120, 1860]
    lay = RULE["layout"]
    assert (lay["taps"], lay["training_trial"], lay["training_first"], lay["held_trial"], lay["held_first"]) == \
        (len(C.PULSES["e0"]), 128, 64, 256, 192)
    assert RULE["block_frames"] % lay["training_trial"] == 0 and RULE["block_frames"] % lay["held_trial"] == 0


def test_e3s_noise_rule_the_requests_are_the_rules_and_the_committed_list_is_theirs():
    rows = Q.requests(RULE)
    assert len(rows) == 8 * 4 + 8 == 40
    assert rows[0] == ("CI.MPP.HHZ.2024-01-08.mseed",
                       "https://service.scedc.caltech.edu/fdsnws/dataselect/1/query?net=CI&sta=MPP&loc=--&cha=HHZ"
                       "&start=2024-01-08T00:00:00&end=2024-01-09T00:00:00&nodata=404")
    assert [r[0] for r in rows[:4]] == ["CI.%s.HHZ.2024-01-08.mseed" % s for s in RULE["stations"]]
    assert rows[32] == ("scedc-events-2024-01-08.txt",
                        "https://service.scedc.caltech.edu/fdsnws/event/1/query?starttime=2024-01-07T21:00:00"
                        "&endtime=2024-01-09T00:00:00&catalog=SCEDC&etype=any&gtype=any&magtype=all&format=text"
                        "&orderby=time&nodata=404")
    assert len({r[0] for r in rows}) == 40
    with open(os.path.join(E3, "requests.tsv"), encoding="utf-8", newline="") as f:
        assert f.read() == Q.text(RULE)
    # a day at 100 samples a second is inside the service's largest window (its page, read 2026-11-25)
    assert 86400 * 100 + 100 <= 400 * 1024 * 1024 // 4


# ------------------------------------------------------------------ rule 1: continuity

def test_e3s_noise_rule_continuous_samples_cut_into_whole_blocks():
    r = small_rule()
    t, x = P.day_samples([record(0, ramp(200)), record(200 * 10000, ramp(130, 200))], r, 0)
    blocks = P.cut(t, x, r)
    assert [b is not None for b in blocks] == [True, True, True, True, True]
    assert np.concatenate(blocks).tolist() == (ramp(200) + ramp(130, 200))[:320]
    # records handed out of order are put in time order
    t2, x2 = P.day_samples([record(200 * 10000, ramp(130, 200)), record(0, ramp(200))], r, 0)
    assert t2.tolist() == t.tolist() and x2.tolist() == x.tolist()


def test_e3s_noise_rule_a_gap_an_overlap_or_a_tear_loses_only_its_own_block():
    r = small_rule()
    for start_us, what in ((150 * 10000 + 5001, "a gap just past half a sample"),
                           (150 * 10000 - 5001, "an overlap just past half a sample"),
                           (151 * 10000, "a missing sample"),
                           (150 * 10000 - 5000, "half a sample early: the gap is allowed, but 65 samples fall in the block")):
        t, x = P.day_samples([record(0, ramp(150)), record(start_us, ramp(200, 150))], r, 0)
        kept = [b is not None for b in P.cut(t, x, r)]
        assert kept == [True, True, False, True, True], (what, kept)
    t, x = P.day_samples([record(0, ramp(150)), record(150 * 10000 + 5000, ramp(200, 150))], r, 0)
    assert sum(b is not None for b in P.cut(t, x, r)) == 5, "half a sample late is continuous, and 64 fall in each block"
    # half a sample early and, ten samples on, half a sample late: both joins are continuous, 64 in the block
    t, x = P.day_samples([record(0, ramp(150)), record(149 * 10000 + 5000, ramp(10, 150)),
                          record(160 * 10000, ramp(200, 160))], r, 0)
    blocks = P.cut(t, x, r)
    assert sum(b is not None for b in blocks) == 5 and sorted(set(np.diff(t[128:192]).tolist())) == [5000, 10000, 15000]
    # a duplicated record: every sample twice
    t, x = P.day_samples([record(0, ramp(320)), record(128 * 10000, ramp(64, 128))], r, 0)
    assert [b is not None for b in P.cut(t, x, r)] == [True, True, False, True, True]


def test_e3s_noise_rule_records_of_another_channel_station_or_rate_are_not_read():
    r = small_rule()
    good = record(0, ramp(320))
    for bad in (record(0, ramp(320), cha="HHN"), record(0, ramp(320), sta="CDM"), record(0, ramp(320), rate=40.0),
                record(0, ramp(320), net="AZ"), record(0, ramp(320), loc="10")):
        t, x = P.day_samples([bad], r, 0)
        assert t.size == 0 and [b is None for b in P.cut(t, x, r)] == [True] * 5
        t, x = P.day_samples([good, bad], r, 0)
        assert sum(b is not None for b in P.cut(t, x, r)) == 5, "the foreign record is dropped, not counted"


def test_e3s_noise_rule_samples_before_midnight_or_past_the_last_block_are_not_in_any_block():
    r = small_rule()
    t, x = P.day_samples([record(-30 * 10000, ramp(400))], r, 0)
    blocks = P.cut(t, x, r)
    assert all(b is not None for b in blocks) and blocks[0].tolist() == ramp(400)[30:94]


def test_e3s_noise_rule_a_block_outside_every_channel_epoch_is_lost():
    assert P.within_epoch(10, 20, [(0, 20)]) and not P.within_epoch(10, 21, [(0, 20)])
    assert not P.within_epoch(10, 20, []) and P.within_epoch(10, 20, [(30, 40), (5, 25)])


# ------------------------------------------------------------------ rules 3 and 4: events and launches

EVENTS_TEXT = """#EventID  | Time                | Latitude | Longtitude   | Depth/km | Author | Catalog | ET | GT   | MagType | Magnitude | MagAuthor | EventLocationName
1001 | 2024/01/08 01:00:00.5000 | 34.88848 | -119.8136200 |  5.00    | CI     | SCEDC   | eq | l |   l     |  1.00     | CI        | made up
1002 | 2024/01/08 02:00:00.0000 | 0.00000 | 0.0000000 |  0.00    | CI     | SCEDC   | ex | l |   un     |  0.00     | CI        | made up
1003 | 2024/01/08 03:00:00.0000 | -20.00000 | 170.0000000 | 30.00    | US     | SCEDC   | eq | t |   w     |  6.10     | US        | made up
1004 | 2024/01/08 04:00:00.0000 | 35.00000 | -118.0000000 |  5.00    | CI     | SCEDC   | eq | r |   l     |          | CI        | made up


# of events : 4
"""


def test_e3s_noise_rule_the_event_answer_is_read_as_the_service_writes_it():
    ev = P.parse_events(EVENTS_TEXT)
    assert [e["id"] for e in ev] == ["1001", "1002", "1003", "1004"]
    assert ev[0]["t"] == P.us(datetime(2024, 1, 8, 1, 0, 0, 500000, tzinfo=timezone.utc))
    assert (ev[0]["gt"], ev[0]["m"], ev[2]["gt"], ev[2]["m"], ev[3]["m"]) == ("l", 1.0, "t", 6.1, None)
    with pytest.raises(P.PrepRefusal) as e:
        P.parse_events("1 | 2024-01-08 01:00 | 1 | 2 | 3 | x | y | eq | l | l | 1.0 | z | w\n")
    assert e.value.name == "EVENT_ROW"
    with pytest.raises(P.PrepRefusal) as e:
        P.parse_events("1 | 2 | 3\n")
    assert e.value.name == "EVENT_ROW"


def test_e3s_noise_rule_each_event_tier_excludes_what_the_rule_says():
    lat, lon = 34.88848, -119.81362
    S = 1000000

    def ev(m, d_km, gt="l", t=0):
        # an event d_km due north of the station
        return {"id": "x", "t": t, "lat": lat + d_km / (2 * math.pi * 6371 / 360.0), "lon": lon, "gt": gt, "m": m}

    iv = P.event_interval(ev(1.0, 0.0), lat, lon, RULE)
    assert iv == (-30 * S, 120 * S)
    assert abs(P.event_interval(ev(1.0, 49.0), lat, lon, RULE)[1] - (49.0 / 3 + 120) * S) <= 1
    assert P.event_interval(ev(1.0, 51.0), lat, lon, RULE) is None, "M 1 reaches 50 km and no further"
    assert P.event_interval(ev(3.0, 199.0), lat, lon, RULE) is not None and P.event_interval(ev(3.0, 201.0), lat, lon, RULE) is None
    assert P.event_interval(ev(3.0, 0.0), lat, lon, RULE)[1] == 480 * S, "120 s at M 1, doubling a magnitude"
    assert P.event_interval(ev(-0.5, 0.0), lat, lon, RULE)[1] == 120 * S, "below M 1 the duration is M 1's"
    assert P.event_interval(ev(-0.5, 20.0), lat, lon, RULE) is None, "M -0.5 reaches 17.7 km"
    assert P.event_interval(ev(6.1, 9000.0, gt="t"), lat, lon, RULE) == (0, 10800 * S)
    assert P.event_interval(ev(None, 9000.0, gt="l"), lat, lon, RULE) == (0, 10800 * S), "no magnitude: a teleseism"
    assert P.event_interval(ev(1.0, 9000.0, gt="q"), lat, lon, RULE) == (0, 10800 * S), "another type: a teleseism"
    zero = dict(ev(0.0, 0.0), lat=0.0, lon=0.0)
    assert P.event_interval(zero, lat, lon, RULE) == (-30 * S, 120 * S), "listed at 0, 0: taken at D = 0"
    assert abs(P.distance_km(0.0, 0.0, 0.0, 1.0, 6371) - 2 * math.pi * 6371 / 360) < 1e-9


def test_e3s_noise_rule_a_block_meeting_an_interval_is_lost_and_its_neighbours_are_not():
    assert P.meets(100, 200, [(150, 160)]) and P.meets(100, 200, [(50, 100)]) and P.meets(100, 200, [(199, 300)])
    assert not P.meets(100, 200, [(200, 300)]) and not P.meets(100, 200, [(10, 99)]) and not P.meets(100, 200, [])


def test_e3s_noise_rule_each_launch_precision_excludes_what_the_rule_says():
    S = 1000000
    rows = [{"Launch_Site": "V", "Launch_Date": "2024 Jan  8 0300:20", "Launch_Tag": "a"},
            {"Launch_Site": "VSFB", "Launch_Date": "2024 Jan  8 0400", "Launch_Tag": "b"},
            {"Launch_Site": "VS", "Launch_Date": "2024 Jan  9", "Launch_Tag": "c"},
            {"Launch_Site": "VSFBS", "Launch_Date": "2024 Jan", "Launch_Tag": "d"},
            {"Launch_Site": "CC", "Launch_Date": "2024 Jan  8 0500:00", "Launch_Tag": "e"},
            {"Launch_Site": "V", "Launch_Date": "2019 Jan  8 0500:00", "Launch_Tag": "f"}]
    ivs, coarse = P.launch_intervals(rows, RULE, DAY0 - 86400 * S, DAY0 + 3 * 86400 * S)
    t1 = DAY0 + (3 * 3600 + 20) * S
    t2 = DAY0 + 4 * 3600 * S
    d3 = DAY0 + 86400 * S
    assert sorted(ivs) == sorted([(t1 - 60 * S, t1 + 1800 * S), (t2 - 120 * S, t2 + 1860 * S),
                                  (d3, d3 + 86400 * S + 1800 * S)])
    assert coarse == ["d"], "a month only is not covered by the rule: named, excluding nothing"


# ------------------------------------------------------------------ the roles, rule 5 and the amplitude

def white_blocks(count, frames, sigma, seed):
    noise = source.Noise("s16x1", seed, sigma, 1, count * frames)
    x = np.array([f[0] for f in noise], dtype=np.int64)
    return [x[i * frames:(i + 1) * frames] for i in range(count)]


def test_e3s_noise_rule_the_amplitude_is_the_least_that_reaches_the_calibrations_excursion():
    blocks = white_blocks(16, 4096, 200, 2026112693)
    scores = P.calibration_scores(blocks, RULE)
    assert scores.size == 16 * 4096 // 64
    c = np.array(P.matched_coefficients(), dtype=np.int64)
    w = blocks[3][64 * 5:64 * 6]
    assert scores[3 * 64 + 5] == int(w @ c), "the score at 63 + 64 g is the window 64 g .. 64 g + 63"
    rule = json.loads(json.dumps(RULE))
    rule["amplitude"] = dict(RULE["amplitude"], pfa=0.1)               # 1,024 scores: 102 above at 0.1
    num, d, thr, med, target = P.lowest(scores, rule)
    assert thr["k"] == 102 and target == thr["threshold"] - med
    resp = lambda n: P.response(P.matched_coefficients(), n, 65536)[0]  # noqa: E731
    assert resp(num) >= target > resp(num - 1), "the least: one less does not reach it"
    assert all(resp(n) <= resp(n + 1) for n in range(1, 4 * num, max(1, num // 50))), "the response never falls"
    assert list(d) == list(P.response(P.matched_coefficients(), num, 65536)[1])
    # on white noise the rule lands near the amplitude where D8 gives the matched filter's d = Q^-1(pfa)
    assert 0.8 < num / 65536 / (200 * 1.2816 / 3436.78) < 1.25
    # a target the response reaches exactly: "reaches" takes equality, and nothing smaller does
    exact = resp(1000)
    made = np.array([0] * 501 + [exact] * 399 + [10 ** 12] * 100, dtype=np.int64)   # median 0; the 101st largest is exact
    n2, _d, thr2, med2, target2 = P.lowest(made, rule)
    assert (thr2["threshold"], med2, target2) == (float(exact), 0.0, float(exact))
    assert resp(n2) == exact and resp(n2 - 1) < exact and n2 <= 1000


def test_e3s_noise_rule_roles_follow_time_and_the_range_less_H_is_applied_after_the_calibration():
    rule = small_rule(use={"calibration": 2, "training": 2, "held_out": 3})
    rule["amplitude"] = dict(RULE["amplitude"], pfa=0.1)            # 1,024 calibration scores: 102 above
    base = white_blocks(10, 64 * 512, 300, 2026112694)
    entries = [{"day": DAY, "block": i, "start": i, "status": "kept", "x": b.astype(np.int32)} for i, b in enumerate(base)]
    entries[1]["x"] = entries[1]["x"].copy()
    entries[1]["x"][7] = 32767                                       # inside 16 bits: a calibration block may hold it
    entries[4]["x"] = entries[4]["x"].copy()
    entries[4]["x"][9] = 32767                                       # past 32767 - H: a training block may not
    entries.insert(2, {"day": DAY, "block": 99, "start": 99, "status": "events"})
    used, fig = P.assign(entries, rule)
    assert [e["block"] for e in used["calibration"]] == [0, 1]
    assert fig["H"] > 0 and fig["refused"] is None
    assert [e["block"] for e in used["training"]] == [2, 3] and [e["block"] for e in used["held_out"]] == [5, 6, 7]
    assert entries[5]["status"] == "range" and entries[9]["status"] == "unused"
    # one block fewer than the roles need: NOT_ENOUGH_NOISE
    short = [dict(e) for e in entries[:8]]
    for e in short:
        e["status"] = "kept" if e["block"] != 99 else "events"
    _u, f2 = P.assign(short, rule)
    assert f2["refused"] == "NOT_ENOUGH_NOISE"


def test_e3s_noise_rule_station_blocks_loses_each_block_to_the_first_rule_it_fails(tmp_path):
    """End to end on a day written by this test as miniSEED and read by D1's reader."""
    r = small_rule()
    frames = 5 * 64
    x = ramp(frames)
    x[64:128] = [17] * 64                                           # block 1: flat
    path = tmp_path / "CI.MPP.HHZ.2024-01-08.mseed"
    path.write_bytes(steim1_file("MPP", DAY0, x[:150]) + steim1_file("MPP", DAY0 + 150 * 10000, x[150:]))
    S = 1000000
    ev = [{"id": "e", "t": DAY0 + 64 * 2 * 10000 + 100000, "lat": 34.88848, "lon": -119.81362, "gt": "l", "m": 1.0}]
    launches = [(DAY0 + 64 * 3 * 10000 + 100000, DAY0 + 64 * 3 * 10000 + 200000)]
    epochs = {"MPP": (34.88848, -119.81362, [(DAY0 - 86400 * S, DAY0 + 86400 * S)])}
    files = []
    entries = P.station_blocks("MPP", dict(r, days=[DAY]), str(tmp_path), {path.name: "200"}, epochs, ev,
                               launches, files=files)
    # the event at block 2 + 0.1 s excludes 30 s before it to 120 s after: blocks 0 to 4 are 0.64 s each,
    # and the flat block is lost to rule 2, which comes first
    assert [e["status"] for e in entries] == ["events", "flat", "events", "events", "events"]
    entries = P.station_blocks("MPP", dict(r, days=[DAY]), str(tmp_path), {path.name: "200"}, epochs, [],
                               launches, files=files)
    assert [e["status"] for e in entries] == ["kept", "flat", "kept", "launches", "kept"]
    assert entries[0]["x"].tolist() == x[:64] and entries[4]["x"].tolist() == x[256:320]
    assert files[-1] == {"file": path.name, "answer": "200", "records": 4, "samples": frames, "refused": None}
    # outside the station's epoch: rule 1
    entries = P.station_blocks("MPP", dict(r, days=[DAY]), str(tmp_path), {path.name: "200"},
                               {"MPP": (0.0, 0.0, [])}, [], [], files=files)
    assert {e["status"] for e in entries} == {"continuity"}
    # a day answered 404, and a file D1's reader refuses: every block lost under rule 1, the reason written
    entries = P.station_blocks("MPP", dict(r, days=[DAY]), str(tmp_path), {path.name: "404"}, epochs, [], [], files=files)
    assert {e["status"] for e in entries} == {"continuity"} and files[-1]["records"] == 0
    path.write_bytes(path.read_bytes()[:700])
    entries = P.station_blocks("MPP", dict(r, days=[DAY]), str(tmp_path), {path.name: "200"}, epochs, [], [], files=files)
    assert {e["status"] for e in entries} == {"continuity"} and "FILE-ENDS-MID-RECORD" in files[-1]["refused"]


# ------------------------------------------------------------------ what the prep writes, and what it refuses

def test_e3s_noise_rule_the_recording_is_the_models_own_and_replays():
    x = np.array([0, -1, 1, 32767, -32768, 1234, -4321] * 9, dtype=np.int32)
    data = P.recording_bytes(x)
    assert data == source.recording("s16x1", tuple((int(v),) for v in x))
    assert source.parse_recording("s16x1", data) == tuple((int(v),) for v in x)
    assert hashlib.sha256(P.payload(x)).digest() == data[source.HEADER_BYTES - 32:source.HEADER_BYTES]
    with pytest.raises(P.PrepRefusal) as e:
        P.payload(np.array([32768]))
    assert e.value.name == "SAMPLE_WIDTH"


def test_e3s_noise_rule_the_prep_refuses_a_fetch_that_is_not_settled_and_an_input_of_another_hash(tmp_path):
    req = tmp_path / "requests.tsv"
    req.write_text("# x\na.mseed\thttp://x/a\nb.txt\thttp://x/b\n", encoding="utf-8")
    (tmp_path / "a.mseed").write_bytes(b"abc")
    good = hashlib.sha256(b"abc").hexdigest()
    man = tmp_path / "manifest.tsv"
    man.write_text("# h\na.mseed\thttp://x/a\tt\t200\t3\t%s\nb.txt\thttp://x/b\tt\t404\t0\t-\n" % good, encoding="utf-8")
    assert P.settled(str(tmp_path), str(req), str(man)) == {"a.mseed": "200", "b.txt": "404"}
    for text in ("# h\na.mseed\thttp://x/a\tt\t200\t3\t%s\n" % good,                       # b has no line
                 "# h\na.mseed\thttp://x/a\tt\t200\t3\t%s\nb.txt\thttp://x/b\tt\t503\t0\t-\n" % good,
                 "# h\na.mseed\thttp://x/a\tt\t200\t3\t%s\nb.txt\thttp://x/b\tt\t404\t0\t-\n" % ("0" * 64)):
        man.write_text(text, encoding="utf-8")
        with pytest.raises(P.PrepRefusal) as e:
            P.settled(str(tmp_path), str(req), str(man))
        assert e.value.name == "FETCH_NOT_SETTLED"
    with pytest.raises(P.PrepRefusal) as e:
        P.held(str(req), "0" * 64)
    assert e.value.name == "INPUT_SHA256"


def test_e3s_noise_rule_the_station_answer_gives_each_stations_epochs():
    text = ("#Network | Station | Location | Channel | Latitude | Longitude | Elevation | Depth | Azimuth | Dip | "
            "Instrument | Scale | ScaleFreq | ScaleUnits | SampleRate | StartTime | EndTime\n"
            "CI|CDM||HHZ|34.36855|-119.341437|166.8|1|0|-90|x|1|1|m/s|100|2023-08-31T19:00:00|2024-07-30T16:45:04\n"
            "CI|CDM||HHZ|34.36855|-119.341437|166.8|1|0|-90|x|1|1|m/s|100|2024-07-30T16:45:04|3000-01-01T00:00:00\n"
            "CI|XYZ||HHZ|1|2|3|1|0|-90|x|1|1|m/s|100|2023-08-31T19:00:00|3000-01-01T00:00:00\n")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "s.txt")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(text)
        ep = P.station_epochs(f, RULE)
    assert sorted(ep) == ["CDM"] and ep["CDM"][:2] == (34.36855, -119.341437) and len(ep["CDM"][2]) == 2
    assert P.within_epoch(DAY0, DAY0 + 655360000, ep["CDM"][2])


# ------------------------------------------------------------------ a miniSEED writer for the tests

def steim1_file(sta, start_us, samples):
    """Fixed-length 512-byte Steim-1 records of 32-bit differences, as D1's reader reads them."""
    out = b""
    at = 0
    while at < len(samples):
        chunk = samples[at:at + 103]
        out += steim1_record(sta, start_us + at * 10000, chunk)
        at += len(chunk)
    return out


def steim1_record(sta, start_us, xs):
    t = P.EPOCH + timedelta(microseconds=start_us)
    doy = t.timetuple().tm_yday
    head = b"000001D " + sta.ljust(5).encode() + b"  " + b"HHZ" + b"CI"
    head += struct.pack(">HHBBBBH", t.year, doy, t.hour, t.minute, t.second, 0, t.microsecond // 100)
    head += struct.pack(">Hhh", len(xs), 100, 1) + bytes([0, 0, 0, 1]) + struct.pack(">iHH", 0, 64, 48)
    head += struct.pack(">HHBBBB", 1000, 0, 10, 1, 9, 0) + bytes(8)
    assert len(head) == 64
    diffs = [0] + [xs[i] - xs[i - 1] for i in range(1, len(xs))]
    frames = b""
    slots = [(0, w) for w in range(3, 16)] + [(f, w) for f in range(1, 7) for w in range(1, 16)]
    grid = [[0] * 16 for _ in range(7)]
    grid[0][1], grid[0][2] = xs[0] & 0xFFFFFFFF, xs[-1] & 0xFFFFFFFF
    for (f, w), d in zip(slots, diffs):
        grid[f][w] = d & 0xFFFFFFFF
        grid[f][0] |= 3 << (30 - 2 * w)
    for f in range(7):
        frames += struct.pack(">16I", *grid[f])
    return head + frames


def test_e3s_noise_rule_the_test_writer_is_read_back_by_d1s_reader():
    xs = ramp(250)
    data = steim1_file("MPP", DAY0 + 12345600, xs)
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "x.mseed")
        with open(f, "wb") as fh:
            fh.write(data)
        recs = mseed.read(f)
    assert [r["nsamp"] for r in recs] == [103, 103, 44] and [v for r in recs for v in r["samples"]] == xs
    assert P.us(recs[1]["start"]) == DAY0 + 12345600 + 103 * 10000

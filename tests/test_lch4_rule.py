"""Study D3's hit rule, its windows, its control times and its test, on made-up records.
No fetched file is read.

Each test states the answer it expects, worked by hand in its comments. These are no
gate of D0's: they hold the scripts of docs/studies/d3 to the rule the design fixed
(the round's ledger, 2026-11-24 09:27, approved by the lead at 09:29). Every number of
the rule has a test here that fails when the number moves, the two that study D2's
limit 18 names among them: the least number of noise frames, and the window that
score_at hands to the statistic, each held end to end through score_at.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from urllib.parse import parse_qs, urlparse

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
D3 = os.path.join(os.path.dirname(HERE), "docs", "studies", "d3")
sys.path.insert(0, D3)
import d3launches  # noqa: E402
import d3rule as rule  # noqa: E402
import d3score as score  # noqa: E402
import d3setconstants as setconstants  # noqa: E402

UTC = timezone.utc
T0 = datetime(2030, 1, 2, 3, 4, 5, tzinfo=UTC)


def series(up, lo=0, hi=40, missing=(), at=5.0, rest=1.0):
    r = dict((k, rest) for k in range(lo - 20, hi + 20))
    for k in up:
        r[k] = at
    for k in missing:
        del r[k]
    return r


# ---------------------------------------------------------------- the windows

def test_lch4_the_windows_open_as_d1s_and_close_on_a_source_of_430_seconds():
    # open d / 0.345 - 5, close d / 0.240 + 430 + 5; floor and ceiling.
    # 78.5 km: 227.54 - 5 = 222.54 and 327.08 + 435 = 762.08.
    # 120.4: 348.99 - 5 = 343.99 and 501.67 + 435 = 936.67.
    # 181.4: 525.80 - 5 = 520.80 and 755.83 + 435 = 1190.83.
    # 275.0: 797.10 - 5 = 792.10 and 1145.83 + 435 = 1580.83.
    assert rule.STATIONS == [("MPP", 78.5), ("CDM", 120.4), ("HDH", 181.4), ("SRN", 275.0)]
    assert [rule.window(s) for s, _km in rule.STATIONS] == [
        (222, 763), (343, 937), (520, 1191), (792, 1581)]
    assert rule.SOURCE_SECONDS == 430


# ---------------------------------------------------------------- the statistic

def test_lch4_one_not_up_second_inside_a_run_does_not_break_it_and_is_not_counted():
    # up 5..14, not up at 15, up 16..25: one run of 20 up seconds.
    assert rule.statistic(series(list(range(5, 15)) + list(range(16, 26))), 0, 40) == 20
    # one up second fewer: 19.
    assert rule.statistic(series(list(range(5, 15)) + list(range(16, 25))), 0, 40) == 19


def test_lch4_two_not_up_seconds_in_a_row_break_a_run():
    # up 5..14, not up at 15 and 16, up 17..26: two runs of 10.
    assert rule.statistic(series(list(range(5, 15)) + list(range(17, 27))), 0, 40) == 10


def test_lch4_a_ratio_of_exactly_three_is_not_up_and_just_above_is():
    # 20 seconds at 5 but for second 12, at exactly 3: 19 up, one run.
    r = series(range(5, 25))
    r[12] = 3.0
    assert rule.statistic(r, 0, 40) == 19
    r[12] = 3.0000001
    assert rule.statistic(r, 0, 40) == 20
    # two seconds at exactly 3 in a row split it: 7 (5..11) and 11 (14..24).
    r[12] = r[13] = 3.0
    assert rule.statistic(r, 0, 40) == 11
    # and the whole run at 2.999 is nothing
    assert rule.statistic(series(range(5, 25), at=2.999), 0, 40) == 0


def test_lch4_a_second_with_no_frame_ends_a_run_at_once():
    # up 5..14, no frame at 15, up 16..25: two runs of 10; 39 of 40 have a frame.
    assert rule.statistic(series(list(range(5, 15)) + list(range(16, 26)), missing=[15]), 0, 40) == 10


def test_lch4_a_window_with_fewer_than_nine_tenths_of_its_seconds_is_no_record():
    # 35 of 40 seconds is 87.5%: no record. 36 of 40 is 90%: scored.
    assert rule.statistic(series(range(5, 25), missing=[30, 31, 32, 33, 34]), 0, 40) is None
    assert rule.statistic(series(range(5, 25), missing=[30, 31, 32, 33]), 0, 40) == 20
    assert rule.USABLE_SHARE == 0.9


def test_lch4_up_seconds_outside_the_window_do_not_count():
    assert rule.statistic(series(range(-10, 5)), 0, 40) == 5
    assert rule.statistic(series(range(35, 50)), 0, 40) == 5


# ---------------------------------------------------------------- made-up records, end to end

def made_up_record(bursts, seed=1, at=T0, before=4300, after=1600):
    """Unit noise from `at` - before to `at` + after, 100 samples a second, with a
    5 Hz sine of amplitude 30 added over each (from, to) in seconds after `at`."""
    first = at - timedelta(seconds=before)
    t = np.arange(0, float(before + after), 0.01)
    x = np.random.default_rng(seed).normal(0.0, 1.0, len(t))
    for lo, hi in bursts:
        on = (t >= lo + before) & (t < hi + before)
        x[on] += 30 * np.sin(2 * np.pi * 5.0 * t[on])
    return first, x


def test_lch4_a_planted_burst_in_each_stations_window_is_seen_and_the_same_noise_without_it_is_not():
    # a 60 s burst from 100 s after the window opens: frames are 4 s long, so the
    # up seconds run from about open + 99 to about open + 160: 58 to 64.
    for station, _km in rule.STATIONS:
        lo, _hi = rule.window(station)
        s, why = rule.score_at(made_up_record([(lo + 100, lo + 160)], before=700), T0, station)
        assert why is None and 58 <= s <= 64, (station, s, why)
        s, why = rule.score_at(made_up_record([], before=700), T0, station)
        assert (s, why) == (0, None), (station, s, why)


def test_lch4_the_window_handed_to_the_statistic_is_the_stations_own_at_both_edges():
    # D2's limit 18: a window thirty seconds too wide passed every test of D2's.
    # Here a burst straddles each edge and score_at must count only what is inside.
    # A burst from close - 40 to close + 40 is up from about close - 41; inside the
    # window, k < close, that is 40 to 42 seconds. One window 30 s wider gives about
    # 70, one 30 s narrower about 10.
    for station, _km in rule.STATIONS:
        lo, hi = rule.window(station)
        s, _w = rule.score_at(made_up_record([(hi - 40, hi + 40)], before=700, after=1700), T0, station)
        assert 39 <= s <= 43, (station, "close", s)
        # a burst that starts 5 s after the close: the first frame that holds any of
        # it is centred at close + 4 (it spans close + 2 to close + 6): nothing inside.
        s, _w = rule.score_at(made_up_record([(hi + 5, hi + 65)], before=700, after=1700), T0, station)
        assert s == 0, (station, "after the close", s)
        # the same at the open: from open - 40 to open + 40 counts open .. about open + 41.
        s, _w = rule.score_at(made_up_record([(lo - 40, lo + 40)], before=700, after=1700), T0, station)
        assert 39 <= s <= 43, (station, "open", s)
        # a burst that ends 5 s before the open: its last frame is centred at open - 4.
        s, _w = rule.score_at(made_up_record([(lo - 65, lo - 5)], before=700, after=1700), T0, station)
        assert s == 0, (station, "before the open", s)


def test_lch4_three_hundred_noise_frames_are_enough_and_two_hundred_and_ninety_nine_are_not():
    # The noise frames are those centred 660 to 60 s before T: 601 of them. Frame k
    # spans k - 2 to k + 2 s. Blanking the record from its start (T - 700) to K - 1 s
    # removes every noise frame up to K and none after it. K = -360 leaves the 300
    # frames -359 .. -60; K = -359 leaves 299.
    for k_last, expect_scored in ((-360, True), (-359, False)):
        first, x = made_up_record([(300, 360)], before=700)
        x = x.copy()
        x[:(700 + k_last - 1) * 100] = np.nan
        s, why = rule.score_at((first, x), T0, "MPP")
        if expect_scored:
            assert why is None and 58 <= s <= 64, (k_last, s, why)
        else:
            assert s is None and why == "299 noise frames of 601", (k_last, s, why)
    assert rule.MIN_NOISE_FRAMES == 300


def rows_for(bursts, station="MPP", control_bursts=()):
    launches = [
        {"n": 1, "side": rule.SETS, "tag": "2030-001", "t0": T0, "flight": "made up",
         "records": "fetched", "controls": [-7]},
        {"n": 2, "side": rule.SCORED, "tag": "2030-002", "t0": T0, "flight": "made up",
         "records": "fetched", "controls": [7]},
    ]

    def loader(tag, sta, days):
        if sta != station:
            return None
        if days is None:
            return made_up_record(bursts)
        return made_up_record(control_bursts, seed=2, at=T0 + timedelta(days=days), before=700)
    rows = rule.collect(launches, ["2030-002"], rule.SCORED, loader)
    return dict((r[2], r[4]) for r in rows if r[1] == station)


def test_lch4_the_wrong_window_closes_sixty_seconds_before_t0():
    # CI.MPP: window 222 to 763, so the wrong window is T0 - 823 + (222 .. 763):
    # from T0 - 601 to T0 - 60. A burst from -100 to -70 is inside it: about 30 up.
    got = rows_for([(-100, -70)])
    assert 28 <= got["wrong"] <= 34 and got["launch"] == 0 and got["shifted"] == 0, got
    # a burst from -58 to -30 starts after the wrong window's close, -60: the first
    # frame holding any of it is centred at -59, outside. With a gap of 30 s in
    # place of 60 it would count about 28.
    got = rows_for([(-58, -30)])
    assert got["wrong"] == 0, got
    assert rule.WRONG_GAP == 60


def test_lch4_the_shifted_catalogue_is_one_hour_early():
    # an hour early the window is T0 - 3600 + (222 .. 763). A burst there is the
    # shifted window's alone; at 3000 s or 4000 s early nothing would see it.
    got = rows_for([(-3600 + 300, -3600 + 360)])
    assert 58 <= got["shifted"] <= 64 and got["launch"] == 0 and got["wrong"] == 0, got
    assert rule.SHIFT == 3600


def test_lch4_a_burst_in_a_control_record_is_a_control_hit():
    got = rows_for([], control_bursts=[(300, 360)])
    assert 58 <= got["control"] <= 64 and got["launch"] == 0, got


def test_lch4_a_station_with_no_file_is_no_record_and_in_no_count():
    def loader(tag, station, days):
        return None
    launches = [{"n": 2, "side": rule.SCORED, "tag": "2030-002", "t0": T0, "flight": "x",
                 "records": "fetched", "controls": [7]}]
    rows = rule.collect(launches, ["2030-002"], rule.SCORED, loader)
    # 4 stations, each a launch, a wrong, a shifted and one control window
    assert len(rows) == 16 and all(r[4] is None and r[5] == "no file" for r in rows)


# ---------------------------------------------------------------- the test and the readings

CONSTANTS = {"M": {"MPP": 50, "CDM": 50, "HDH": 50, "SRN": 50}}


def counted_rows(launch_hits, wrong_hits, shifted_hits, control_hits, n_launch=23, n_control=68,
                 s_hit=100):
    """Rows at CI.MPP with exactly this many windows of each kind at S = s_hit, the rest at 0."""
    rows = []
    for i in range(n_launch):
        rows.append(("t%d" % i, "MPP", "launch", 0, s_hit if i < launch_hits else 0, None))
        rows.append(("t%d" % i, "MPP", "wrong", 0, s_hit if i < wrong_hits else 0, None))
        rows.append(("t%d" % i, "MPP", "shifted", 0, s_hit if i < shifted_hits else 0, None))
    for i in range(n_control):
        rows.append(("t%d" % (i % n_launch), "MPP", "control", 7, s_hit if i < control_hits else 0, None))
    return rows


def reading(rows):
    out = score.summarise(rows, CONSTANTS, "made up")
    line = [x for x in out if x.startswith("| CI.MPP | 78.5")][0]
    head = [x for x in out if x.startswith("**HEADLINE")][0]
    return line.split("|")[-2].strip(), head


def test_lch4_fishers_exact_test_against_values_worked_by_hand():
    # 5 hits, all among 23 launch windows of 91: C(23,5) / C(91,5) = 33,649 / 46,504,458.
    assert abs(rule.p_fisher(5, 0, 23, 68) - 33649 / 46504458) < 1e-15
    # 4 of 4: C(23,4) / C(91,4) = 8,855 / 2,672,670 = 0.00331.
    assert abs(rule.p_fisher(4, 0, 23, 68) - 8855 / 2672670) < 1e-15
    # 3 of 3: C(23,3) / C(91,3) = 1,771 / 121,485 = 0.0146.
    assert abs(rule.p_fisher(3, 0, 23, 68) - 1771 / 121485) < 1e-15
    assert rule.needed(0, 23, 68, 0.0025) == 5
    assert rule.p_fisher(0, 7, 23, 68) == 1.0
    # two and two, by counting the 6 ways to place 2 hits
    assert abs(rule.p_fisher(2, 0, 2, 2) - 1 / 6) < 1e-15
    assert abs(rule.p_fisher(1, 1, 2, 2) - 5 / 6) < 1e-15


def test_lch4_the_level_is_a_quarter_of_one_in_a_hundred_at_a_station():
    assert (score.FAMILY_LEVEL, score.LEVEL) == (0.01, 0.0025)
    # 4 launch hits of 23, none of 68 controls: p = 0.00331, over 0.0025 (and under
    # a third of 0.01, 0.00333, so a level shared over three would pass it).
    assert reading(counted_rows(4, 0, 0, 0))[0] == "NOT SHOWN"
    # 5: p = 0.00072: seen.
    assert reading(counted_rows(5, 0, 0, 0))[0] == "SEEN MORE OFTEN THAN A CONTROL WINDOW"


def test_lch4_the_two_controls_are_held_at_one_in_a_hundred_undivided():
    assert score.CONTROL_LEVEL == 0.01
    # every launch hits; 4 wrong windows of 23, no control: p = 0.00331, under 0.01
    # (over 0.0025): the line is void.
    assert reading(counted_rows(23, 4, 0, 0))[0].startswith("VOID")
    assert reading(counted_rows(23, 0, 4, 0))[0].startswith("VOID")
    # 3 of 23: p = 0.0146, over 0.01: not void.
    assert reading(counted_rows(23, 3, 3, 0))[0] == "SEEN MORE OFTEN THAN A CONTROL WINDOW"


def test_lch4_fifteen_launch_windows_are_enough_to_write_not_shown_and_fourteen_are_not():
    assert score.ENOUGH == 15
    assert reading(counted_rows(0, 0, 0, 0, n_launch=15, n_control=45))[0] == "NOT SHOWN"
    assert reading(counted_rows(0, 0, 0, 0, n_launch=14, n_control=42))[0] == "CANNOT TELL: TOO FEW RECORDS"


def test_lch4_s_equal_to_m_is_a_hit_and_one_less_is_not():
    # M = 50 at CI.MPP; every launch window at S = 50 is 23 hits of 23; at 49, none.
    r, head = reading(counted_rows(23, 0, 0, 0, s_hit=50))
    assert r == "SEEN MORE OFTEN THAN A CONTROL WINDOW" and "YES" in head and "CI.MPP" in head
    r, head = reading(counted_rows(23, 0, 0, 0, s_hit=49))
    assert r == "NOT SHOWN" and head.startswith("**HEADLINE, made up: NO: NOT SHOWN")


def test_lch4_launches_and_controls_that_hit_alike_are_not_seen():
    # every window of both kinds hits: a = 23, b = 68, p = 1.
    assert reading(counted_rows(23, 0, 0, 68))[0] == "NOT SHOWN"


def test_lch4_a_window_with_no_record_is_in_neither_count():
    # 5 launch hits of 23 reject. Two of the hitting windows NO RECORD: 3 of 21 against
    # 0 of 68 is C(21,3) / C(89,3) = 1,330 / 113,564 = 0.0117, which does not.
    rows, dropped = [], 0
    for row in counted_rows(5, 0, 0, 0):
        if row[2] == "launch" and row[4] == 100 and dropped < 2:
            rows.append(row[:4] + (None, "made up"))
            dropped += 1
        else:
            rows.append(row)
    line = [x for x in score.summarise(rows, CONSTANTS, "made up") if x.startswith("| CI.MPP | 78.5")][0]
    assert "| 3 of 21 |" in line and "| 0 of 68 |" in line and "| 2, 0 |" in line, line
    assert line.split("|")[-2].strip() == "NOT SHOWN"
    assert abs(rule.p_fisher(3, 0, 21, 68) - 1330 / 113564) < 1e-15


def test_lch4_a_station_with_no_usable_window_is_not_run():
    rows = [r for r in counted_rows(5, 0, 0, 0) if r[2] != "control"]
    assert reading(rows)[0] == "NOT RUN: NO RECORD"


# ---------------------------------------------------------------- M

def test_lch4_m_is_the_middle_of_the_range_that_best_parts_launches_from_controls():
    # every launch at or above 120, every control at or below 20: J is 1 for m from
    # 21 to 120. sqrt(21 x 120) = 50.2: M is 50.
    a, b = [200, 180, 150, 120], [0, 0, 5, 12, 20, 3, 0, 0]
    assert setconstants.choose_m(a, b, 541) == (50, (Fraction(1), 21, 120))
    # J by hand: m 10..12: 4/4 - 1/8 = 7/8; m 13..15: 3/4 - 1/8; m 16..30: 2/4 - 1/8;
    # m 31..150: 1/2. The largest is 7/8 on 10..12; sqrt(120) = 10.95: 11.
    a, b = [200, 150, 15, 12], [0, 0, 0, 0, 0, 0, 0, 30]
    assert setconstants.choose_m(a, b, 541) == (11, (Fraction(7, 8), 10, 12))
    # launches and controls alike, all under 10: J is 0 from 10 to the window's
    # length, 541: M = sqrt(10 x 541) = 73.6: 74.
    assert setconstants.choose_m([1, 2, 3, 4], [0] * 8, 541) == (74, (Fraction(0), 10, 541))
    # too few windows: D1's 10, and not set
    assert setconstants.choose_m([200, 180, 150], b, 541) == (10, None)
    assert setconstants.choose_m(a, [0] * 7, 541) == (10, None)
    assert (setconstants.MIN_LAUNCH_WINDOWS, setconstants.MIN_CONTROL_WINDOWS, rule.M_FLOOR) == (4, 8, 10)


# ---------------------------------------------------------------- the split and the control times

def test_lch4_the_split_is_every_third_launch_from_the_first():
    assert [d3launches.side_of(n) for n in range(1, 8)] == [
        rule.SETS, rule.SCORED, rule.SCORED, rule.SETS, rule.SCORED, rule.SCORED, rule.SETS]
    launches = rule.read_launches(os.path.join(D3, "launches.tsv"))
    sets = [r["tag"] for r in launches if r["side"] == rule.SETS]
    scored = [r["tag"] for r in launches if r["side"] == rule.SCORED]
    assert sets == ["2021-082", "2024-002", "2024-020", "2024-036", "2024-050", "2024-088", "2024-118",
                    "2024-138", "2024-155", "2024-175", "2024-209", "2024-225", "2024-247"]
    assert len(scored) == 23 and not set(sets) & set(scored)
    for r in launches:
        if r["n"]:
            assert r["side"] == (rule.SETS if r["n"] % 3 == 1 else rule.SCORED), r
    looked = [r for r in launches if r["tag"] == "2021-082"][0]
    assert looked["side"] == rule.SETS and looked["records"] == "none"


def test_lch4_daylight_saving_is_the_pacific_clocks_of_2024():
    one = timedelta(seconds=1)
    on, off = datetime(2024, 3, 10, 10, 0, tzinfo=UTC), datetime(2024, 11, 3, 9, 0, tzinfo=UTC)
    assert (d3launches.daylight(on - one), d3launches.daylight(on)) == (False, True)
    assert (d3launches.daylight(off - one), d3launches.daylight(off)) == (True, False)


def test_lch4_no_control_time_crosses_a_change_of_daylight_saving():
    # a launch five days before the spring change: +7 and +14 fall after it and are
    # skipped; -7, -14, -21 are taken. Five days after the autumn change: -7, -14,
    # -21 fall before it; +7, +14, +21 are taken. Without the condition both would
    # be -7, +7, -14.
    spring = datetime(2024, 3, 5, 4, 0, tzinfo=UTC)
    autumn = datetime(2024, 11, 8, 4, 0, tzinfo=UTC)
    got = d3launches.choose_controls([(spring, "a", "x"), (autumn, "b", "x")], [], [])
    assert got == [[-7, -14, -21], [7, 14, 21]], got
    # and on the committed list, every control time is on its launch's clock
    for r in rule.read_launches(os.path.join(D3, "launches.tsv")):
        for days in r["controls"]:
            assert d3launches.daylight(r["t0"]) == d3launches.daylight(r["t0"] + timedelta(days=days)), r
    by_tag = dict((r["tag"], r) for r in rule.read_launches(os.path.join(D3, "launches.tsv")))
    assert by_tag["2024-046"]["controls"] == [14, 28, 35]


def test_lch4_a_control_time_is_a_day_clear_of_every_listed_launch_and_two_hours_from_every_other():
    t = datetime(2024, 6, 5, 4, 0, tzinfo=UTC)
    # an entry timed to the second 23 h 59 min 59 s after t - 7 d: -7 is not clear.
    near = (t - timedelta(days=7) + timedelta(hours=24) - timedelta(seconds=1), "the second")
    assert d3launches.choose_controls([(t, "a", "x")], [near], []) == [[7, -14, 14]]
    # exactly 24 h after it: clear.
    at = (t - timedelta(days=7) + timedelta(hours=24), "the second")
    assert d3launches.choose_controls([(t, "a", "x")], [at], []) == [[-7, 7, -14]]
    # an entry timed to the minute needs 24 h and 60 s.
    minute = (t - timedelta(days=7) + timedelta(hours=24, seconds=59), "the minute")
    assert d3launches.choose_controls([(t, "a", "x")], [minute], []) == [[7, -14, 14]]
    # two launches one hour apart: the second's -7, +7 and -14 are each within two
    # hours of a time the first took, so it takes +14, -21, +21.
    got = d3launches.choose_controls([(t, "a", "x"), (t + timedelta(hours=1), "b", "x")], [], [])
    assert got == [[-7, 7, -14], [14, -21, 21]], got
    assert d3launches.N_CONTROLS == 3


def test_lch4_every_request_covers_its_windows_and_their_noise():
    # A launch record must hold the true window and its noise, the wrong window and
    # its noise, and the hour-early window and its noise, each frame whole (2 s either
    # side); a control record its window and noise.
    for station, _km in rule.STATIONS:
        lo, hi = rule.window(station)
        sp = d3launches.spans(station)
        need_from = min(-660 - 2, -(hi + 60) - 660 - 2, -3600 - 660 - 2)
        need_to = max(hi + 2, -(hi + 60) + hi + 2, -3600 + hi + 2)
        assert sp["launch"][0] <= need_from and sp["launch"][1] >= need_to, (station, sp)
        assert sp["control"][0] <= -660 - 2 and sp["control"][1] >= hi + 2, (station, sp)
    # and the committed request list asks exactly those spans
    launches = dict((r["tag"], r) for r in rule.read_launches(os.path.join(D3, "launches.tsv")))
    n = 0
    for line in open(os.path.join(D3, "requests.tsv"), encoding="utf-8"):
        if line.startswith("#") or not line.startswith("CI."):
            continue
        name, url = line.rstrip("\n").split("\t")
        _ci, station, _hhz, tag, kind, _ext = name.split(".")
        q = parse_qs(urlparse(url).query)
        start = datetime.strptime(q["start"][0], rule.ISO).replace(tzinfo=UTC)
        end = datetime.strptime(q["end"][0], rule.ISO).replace(tzinfo=UTC)
        t = launches[tag]["t0"]
        if kind == "launch":
            span = d3launches.spans(station)["launch"]
        else:
            t = t + timedelta(days=int(kind[1:]))
            span = d3launches.spans(station)["control"]
        assert (start - t, end - t) == (timedelta(seconds=span[0]), timedelta(seconds=span[1])), name
        assert q["sta"] == [station] and q["cha"] == ["HHZ"] and q["loc"] == ["--"], name
        n += 1
    # 4 stations x (35 launches + 103 control times)
    assert n == 4 * (35 + 103)


def test_lch4_the_scoring_run_writes_and_refuses_under_one_name():
    # D2's limit: the output's name was held by no test. Here one constant names it.
    assert score.OUTPUT_NAME == "scored-output.txt"
    assert score.OUTPUT == os.path.join(D3, "scored-output.txt")

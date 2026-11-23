"""Study D2's hit rule and its test, on made-up records. No fetched file is read.

Each test states the answer it expects, worked by hand in its comments. These
are no gate of D0's: they hold the scoring script of docs/studies/d2 to the
rule its design fixed.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from fractions import Fraction

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "docs", "studies", "d2"))
import rule  # noqa: E402
import score  # noqa: E402
import setconstants  # noqa: E402

T0 = datetime(2030, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def series(up, lo=0, hi=40, missing=(), at=5.0, rest=1.0):
    r = dict((k, rest) for k in range(lo - 20, hi + 20))
    for k in up:
        r[k] = at
    for k in missing:
        del r[k]
    return r


def test_lch3_the_windows_are_d1s_sound_windows():
    # D1's row W1: open d / 0.345 - 5, close d / 0.240 + 185; floor and ceiling.
    # 13.5 km: 34.13 and 241.25. 16.5: 42.83 and 253.75. 32.6: 89.49 and 320.83.
    # 49.9: 139.64 and 392.92. They are D1b's first table of section 5.
    assert [rule.window(s) for s, _km in rule.STATIONS] == [
        (34, 242), (42, 254), (89, 321), (139, 393)]


def test_lch3_one_not_up_second_inside_a_run_does_not_break_it_and_is_not_counted():
    # up 5..14, not up at 15, up 16..25: one run of 20 up seconds.
    r = series(list(range(5, 15)) + list(range(16, 26)))
    assert rule.statistic(r, 0, 40) == 20
    # the same with one up second fewer: 19. With M = 20 the first is a hit and
    # this is not.
    r = series(list(range(5, 15)) + list(range(16, 25)))
    assert rule.statistic(r, 0, 40) == 19


def test_lch3_two_not_up_seconds_in_a_row_break_a_run():
    # up 5..14, not up at 15 and 16, up 17..26: two runs of 10, so S is 10.
    r = series(list(range(5, 15)) + list(range(17, 27)))
    assert rule.statistic(r, 0, 40) == 10


def test_lch3_a_ratio_of_exactly_three_is_not_up():
    # 20 seconds at 5 but for second 12, at exactly 3: 19 up, one run.
    r = series(range(5, 25))
    r[12] = 3.0
    assert rule.statistic(r, 0, 40) == 19
    # and just above three is up
    r[12] = 3.0000001
    assert rule.statistic(r, 0, 40) == 20
    # two seconds at exactly 3 in a row split it: 7 (5..11) and 11 (14..24)
    r[12] = r[13] = 3.0
    assert rule.statistic(r, 0, 40) == 11


def test_lch3_a_second_with_no_frame_ends_a_run_at_once():
    # up 5..14, no frame at 15, up 16..25: two runs of 10. 39 of 40 seconds
    # have a frame, which is above 90%.
    r = series(list(range(5, 15)) + list(range(16, 26)), missing=[15])
    assert rule.statistic(r, 0, 40) == 10


def test_lch3_a_window_with_too_few_frames_is_no_record():
    # 35 of 40 seconds is 87.5%: no record. 36 of 40 is 90%: scored.
    r = series(range(5, 25), missing=[30, 31, 32, 33, 34])
    assert rule.statistic(r, 0, 40) is None
    r = series(range(5, 25), missing=[30, 31, 32, 33])
    assert rule.statistic(r, 0, 40) == 20


def test_lch3_up_seconds_outside_the_window_do_not_count():
    # up from 10 s before the window to its 5th second: 5 inside.
    r = series(range(-10, 5))
    assert rule.statistic(r, 0, 40) == 5
    # up from the 35th second to 10 s after its close: 5 inside.
    r = series(range(35, 50))
    assert rule.statistic(r, 0, 40) == 5


def made_up_record(bursts, seed=1, at=T0):
    """80 minutes of unit noise from `at` - 4300 s, with a 5 Hz sine of amplitude
    30 added over each (from, to) in seconds after `at`."""
    first = at - timedelta(seconds=4300)
    t = np.arange(0, 4800.0, 0.01)
    x = np.random.default_rng(seed).normal(0.0, 1.0, len(t))
    for lo, hi in bursts:
        on = (t >= lo + 4300) & (t < hi + 4300)
        x[on] += 30 * np.sin(2 * np.pi * 5.0 * t[on])
    return first, x


LAUNCHES = [
    {"n": 1, "side": rule.SETS, "tag": "2030-001", "t0": T0, "flight": "made up",
     "records": "fetched", "controls": [-7]},
    {"n": 2, "side": rule.SCORED, "tag": "2030-002", "t0": T0, "flight": "made up",
     "records": "fetched", "controls": [7]},
]


def rows_for(bursts, control_bursts=()):
    def loader(tag, station, days):
        if station != "LOC":
            return None
        if days is None:
            return made_up_record(bursts)
        # a control record is around its own time, a whole number of days from T0
        return made_up_record(control_bursts, seed=2, at=T0 + timedelta(days=days))
    rows = rule.collect(LAUNCHES, ["2030-002"], rule.SCORED, loader)
    return dict((r[2], r[4]) for r in rows if r[1] == "LOC")


def test_lch3_a_planted_burst_in_the_window_is_a_hit_and_the_same_noise_without_it_is_not():
    # CI.LOC's window is 42 to 254 s. A burst from 100 s to 160 s: frames are
    # 4 s long, so the up seconds run from about 99 to about 160: 58 to 64.
    got = rows_for([(100, 160)])
    assert 58 <= got["launch"] <= 64, got
    assert got["wrong"] == 0 and got["shifted"] == 0 and got["control"] == 0, got
    # the same noise with nothing planted: no second is up anywhere
    got = rows_for([])
    assert got == {"launch": 0, "wrong": 0, "shifted": 0, "control": 0}, got


def test_lch3_a_burst_before_t0_is_seen_by_the_wrong_window_and_not_by_the_true_one():
    # CI.LOC's wrong window is the 212 s that close 60 s before T0: from
    # T0 - 272 s to T0 - 60 s. A burst from -250 s to -190 s lies inside it.
    got = rows_for([(-250, -190)])
    assert 58 <= got["wrong"] <= 64, got
    assert got["launch"] == 0 and got["shifted"] == 0, got


def test_lch3_a_burst_an_hour_early_is_seen_by_the_shifted_catalogue_only():
    # an hour early the window is T0 - 3600 + 42 to T0 - 3600 + 254.
    got = rows_for([(-3600 + 100, -3600 + 160)])
    assert 58 <= got["shifted"] <= 64, got
    assert got["launch"] == 0 and got["wrong"] == 0, got


def test_lch3_a_burst_in_a_control_record_is_a_control_hit():
    got = rows_for([], control_bursts=[(100, 160)])
    assert 58 <= got["control"] <= 64 and got["launch"] == 0, got


def test_lch3_a_station_with_no_file_is_no_record_and_in_no_count():
    def loader(tag, station, days):
        return None
    rows = rule.collect(LAUNCHES, ["2030-002"], rule.SCORED, loader)
    # 4 stations, each with a launch, a wrong, a shifted and one control window
    assert len(rows) == 16
    assert all(r[4] is None and r[5] == "no file" for r in rows)


def test_lch3_a_record_with_a_gap_in_its_noise_is_no_record():
    first, x = made_up_record([(100, 160)])
    # blank the 11 minutes before T0 - 55 s: no noise frame is left
    x[int((4300 - 665) * 100):int((4300 - 55) * 100)] = np.nan
    s, why = rule.score_at((first, x), T0, "LOC")
    assert s is None and "noise frames" in why, (s, why)


def test_lch3_fishers_exact_test_against_values_worked_by_hand():
    # 5 hits, all among 23 launch windows of 92: C(23,5) / C(92,5).
    assert abs(rule.p_fisher(5, 0, 23, 69) - 33649 / 49177128) < 1e-15
    # 4 of 4: C(23,4) / C(92,4) = 8855 / 2794155 = 0.00317, above 0.0025
    assert abs(rule.p_fisher(4, 0, 23, 69) - 8855 / 2794155) < 1e-15
    assert rule.needed(0, 23, 69, 0.0025) == 5
    # no hit among the launches is no evidence: p is 1
    assert rule.p_fisher(0, 7, 23, 69) == 1.0
    # two launch and two control windows, by counting the 6 ways to place 2 hits:
    # both among the launches, 1 way of 6; at least one among them, 5 of 6.
    assert abs(rule.p_fisher(2, 0, 2, 2) - 1 / 6) < 1e-15
    assert abs(rule.p_fisher(1, 1, 2, 2) - 5 / 6) < 1e-15
    # with 5 launch and 15 control windows and 3 control hits nothing rejects:
    # 5 of 5 launches with 3 controls is C(8,5) C(12,0) / C(20,5) = 56 / 15504 = 0.0036
    assert rule.needed(3, 5, 15, 0.0025) is None
    assert abs(rule.p_fisher(5, 3, 5, 15) - 56 / 15504) < 1e-15


def test_lch3_m_is_the_middle_of_the_range_that_best_parts_launches_from_controls():
    # every launch at or above 120, every control at or below 20: J is 1 for m
    # from 21 to 120. sqrt(21 x 120) = 50.2: M is 50.
    a, b = [200, 180, 150, 120], [0, 0, 5, 12, 20, 3, 0, 0]
    assert setconstants.choose_m(a, b, 212) == (50, (Fraction(1), 21, 120))
    # J by hand: m 10..12: 4/4 - 1/8 = 7/8. m 13..15: 3/4 - 1/8. m 16..30:
    # 2/4 - 1/8. m 31..150: 1/2. The largest is 7/8 on 10..12; sqrt(120) = 10.95.
    a, b = [200, 150, 15, 12], [0, 0, 0, 0, 0, 0, 0, 30]
    assert setconstants.choose_m(a, b, 212) == (11, (Fraction(7, 8), 10, 12))
    # too few windows: D1's 10, and "not set"
    assert setconstants.choose_m([200, 180, 150], b, 212) == (10, None)
    assert setconstants.choose_m(a, [0] * 7, 212) == (10, None)


def made_up_rows(launch_s, control_s, wrong_s, shifted_s, n_launch=20, n_control=60):
    rows = []
    for i in range(n_launch):
        rows.append(("t%d" % i, "LOC", "launch", 0, launch_s, None))
        rows.append(("t%d" % i, "LOC", "wrong", 0, wrong_s, None))
        rows.append(("t%d" % i, "LOC", "shifted", 0, shifted_s, None))
    for i in range(n_control):
        rows.append(("t%d" % (i % n_launch), "LOC", "control", 7, control_s, None))
    return rows


def counted_rows(launch_hits, wrong_hits, shifted_hits, control_hits, n_launch=23, n_control=69):
    """Rows at CI.LOC with exactly this many windows of each kind at S = 100,
    the rest at 0."""
    rows = []
    for i in range(n_launch):
        rows.append(("t%d" % i, "LOC", "launch", 0, 100 if i < launch_hits else 0, None))
        rows.append(("t%d" % i, "LOC", "wrong", 0, 100 if i < wrong_hits else 0, None))
        rows.append(("t%d" % i, "LOC", "shifted", 0, 100 if i < shifted_hits else 0, None))
    for i in range(n_control):
        rows.append(("t%d" % (i % n_launch), "LOC", "control", 7,
                     100 if i < control_hits else 0, None))
    return rows


def test_lch3_the_level_is_a_quarter_of_one_in_a_hundred_at_a_station():
    # 23 launch windows, 69 control windows, no control hit. 4 launch hits have
    # p = 8855 / 2794155 = 0.0032: under 0.01, over 0.0025, so NOT shown.
    r, _head = reading(counted_rows(4, 0, 0, 0))
    assert r == "NOT SHOWN"
    # 5 have p = 33649 / 49177128 = 0.00068: shown.
    r, _head = reading(counted_rows(5, 0, 0, 0))
    assert r == "SEEN MORE OFTEN THAN A CONTROL WINDOW"
    # with 3 control hits, 7 are needed (the design's table): 6 is not enough
    r, _head = reading(counted_rows(6, 0, 0, 3))
    assert r == "NOT SHOWN"
    r, _head = reading(counted_rows(7, 0, 0, 3))
    assert r == "SEEN MORE OFTEN THAN A CONTROL WINDOW"


def test_lch3_the_two_controls_are_held_at_one_in_a_hundred_undivided():
    # every launch window hits. 4 wrong windows of 23 hit, no control: p = 0.0032,
    # which rejects at 0.01 though it would not at 0.0025: the line is void.
    r, _head = reading(counted_rows(23, 4, 0, 0))
    assert r.startswith("VOID")
    r, _head = reading(counted_rows(23, 0, 4, 0))
    assert r.startswith("VOID")
    # 3 of 23: C(23,3) / C(92,3) = 1771 / 125580 = 0.0141, over 0.01: not void.
    r, _head = reading(counted_rows(23, 3, 3, 0))
    assert r == "SEEN MORE OFTEN THAN A CONTROL WINDOW"


def test_lch3_fifteen_launch_windows_are_enough_to_write_not_shown_and_fourteen_are_not():
    r, _head = reading(counted_rows(0, 0, 0, 0, n_launch=15, n_control=45))
    assert r == "NOT SHOWN"
    r, _head = reading(counted_rows(0, 0, 0, 0, n_launch=14, n_control=42))
    assert r == "CANNOT TELL: TOO FEW RECORDS"


def test_lch3_a_window_with_no_record_is_in_neither_count():
    # 5 launch hits of 23 reject. Mark two of the hitting windows NO RECORD:
    # 3 of 21 is p = C(21,3) / C(90,3) = 1330 / 117480 = 0.0113, which does not.
    rows = counted_rows(5, 0, 0, 0)
    out = []
    dropped = 0
    for row in rows:
        if row[2] == "launch" and row[4] == 100 and dropped < 2:
            out.append(row[:4] + (None, "made up"))
            dropped += 1
        else:
            out.append(row)
    lines = score.summarise(out, CONSTANTS, "made up")
    loc = [line for line in lines if line.startswith("| CI.LOC | 16.5")][0]
    assert "| 3 of 21 |" in loc and "| 0 of 69 |" in loc and "| 2, 0 |" in loc, loc
    assert loc.split("|")[-2].strip() == "NOT SHOWN"


CONSTANTS = {"M": {"GATR": 50, "LOC": 50, "LCP": 50, "SYN": 50}}


def reading(rows):
    out = score.summarise(rows, CONSTANTS, "made up")
    loc = [line for line in out if line.startswith("| CI.LOC | 16.5")][0]
    head = [line for line in out if line.startswith("**HEADLINE")][0]
    return loc.split("|")[-2].strip(), head


def test_lch3_the_reading_of_a_station_follows_the_design():
    # 20 of 20 launch windows hit, 0 of 60 controls: p is far below 0.0025
    r, head = reading(made_up_rows(100, 0, 0, 0))
    assert r == "SEEN MORE OFTEN THAN A CONTROL WINDOW" and "YES" in head and "CI.LOC" in head
    # the same, and the wrong window hits as often: the station's line is void
    r, head = reading(made_up_rows(100, 0, 100, 0))
    assert r.startswith("VOID") and "YES" not in head and "VOID at CI.LOC" in head
    # the same, and the catalogue an hour early hits as often: void too
    r, head = reading(made_up_rows(100, 0, 0, 100))
    assert r.startswith("VOID") and "YES" not in head
    # nothing hits: not shown, with 20 launch windows
    r, head = reading(made_up_rows(0, 0, 0, 0))
    assert r == "NOT SHOWN" and head.startswith("**HEADLINE, made up: NO: NOT SHOWN")
    # launches and controls hit alike, every one: the test must not reject
    r, head = reading(made_up_rows(100, 100, 0, 0))
    assert r == "NOT SHOWN"
    # nothing hits and there are 5 launch windows: cannot tell
    r, head = reading(made_up_rows(0, 0, 0, 0, n_launch=5, n_control=15))
    assert r == "CANNOT TELL: TOO FEW RECORDS" and "CANNOT TELL" in head
    # S one under M is not a hit; S equal to M is
    r, _head = reading(made_up_rows(49, 0, 0, 0))
    assert r == "NOT SHOWN"
    r, _head = reading(made_up_rows(50, 0, 0, 0))
    assert r == "SEEN MORE OFTEN THAN A CONTROL WINDOW"

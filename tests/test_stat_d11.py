"""STAT: the script for D0 row D11, run at its full stated count.

D11 quotes a simulation nobody committed. `python -m stats.d11` is the committed script: it must
reproduce D8's formula for the matched filter, and show a rectified detector falling below it,
with its seed, its trial count and its run time stated.

The seed is fixed, so the figures below are the same every run. Over seeds, each `inside` here
fails a correct implementation with probability 6.3e-5.
"""
import math

import pytest

from stats import d11, theory

SQRT2 = math.sqrt(2.0)
_RUN = {}


def the_run():
    """The script's own run, made once for this file: 400,000 trials each way."""
    if "r" not in _RUN:
        _RUN["r"] = d11.run()
    return _RUN["r"]


def test_stat_d11_states_its_conditions():
    r = the_run()
    assert (r["seed"], r["trials"], r["taps"], r["sigma"], r["pfa"]) == (20261123, 400_000, 128, 2.0, 0.01)
    assert r["d"] == pytest.approx(1.75, rel=1e-12)
    s = d11.pulse()
    assert len(s) == 128
    assert math.sqrt(float((s * s).sum())) / 2.0 == pytest.approx(1.75, rel=1e-12)
    assert abs(s[0]) < 1e-12, "a Hann window is zero at its first sample"
    assert r["seconds"] > 0.0


def test_stat_d11_the_formulas_at_this_point_by_hand():
    r = the_run()
    # Q^-1(0.01) = 2.3263478740408408 and Q^-1(0.005) = 2.5758293035489004, from tables.
    d8 = 0.5 * math.erfc((2.3263478740408408 - 1.75) / SQRT2)
    rectified = 0.5 * math.erfc((2.5758293035489004 - 1.75) / SQRT2) + 0.5 * math.erfc((2.5758293035489004 + 1.75) / SQRT2)
    assert r["d8"] == pytest.approx(d8, abs=1e-12) and d8 == pytest.approx(0.2822, abs=5e-5)
    assert r["rectified_exact"] == pytest.approx(rectified, abs=1e-12) and rectified == pytest.approx(0.2045, abs=5e-5)
    # D0 row D11 quotes 0.284 and 0.206. Neither is the exact figure at d = 1.75.
    assert abs(d8 - 0.284) > 0.0015 and abs(rectified - 0.206) > 0.0015


def test_gate_statistics__d11_the_matched_filter_reproduces_d8():
    r = the_run()
    for key in ("matched_known", "matched_measured"):
        c = r[key]
        assert c["n"] == 400_000
        assert c["inside"], (key, c)
        assert abs(c["z_score"]) <= 4.0
    # with a known threshold the tolerance is 4 * sqrt(0.2822 * 0.7178 / 400000) = 0.0028
    assert r["matched_known"]["tolerance"] == pytest.approx(0.0028, abs=5e-5)
    # with a measured one it is three times that, because the threshold term dominates
    assert r["matched_measured"]["tolerance"] == pytest.approx(0.0085, abs=5e-5)
    assert r["matched_measured"]["se_threshold"] > 2 * r["matched_measured"]["se_binomial"]


def test_control_statistics__d11_a_rectifier_after_the_filter_falls_below_d8():
    """The detector D11 is about: an absolute value after the same filter, at the same false-alarm
    probability. D8 predicts 0.2822; it must find about 0.2045, far outside the tolerance."""
    r = the_run()
    for key in ("rectified_known", "rectified_measured"):
        c = r[key]
        assert not c["inside"], (key, c)
        assert c["deviation"] < -0.07, "the rectified detector must fall BELOW D8, by about 0.078"
    # and it is where its own exact figure puts it, so it fell for the stated reason
    assert r["rectified_known_against_exact"]["inside"], r["rectified_known_against_exact"]
    assert r["rectified_known"]["measured"] == pytest.approx(0.2045, abs=0.003)


def test_stat_d11_a_pulse_of_the_opposite_sign_is_what_tells_a_rectifier_from_a_raised_threshold():
    """On the pulse itself, at d = 1.75, the rectified detector's lower tail holds 8 trials in a
    million: an absolute value and a one-sided test at the rectifier's threshold count alike. On the
    NEGATED pulse they do not: the rectifier finds it as often as the pulse, 0.2045, and the matched
    filter finds it less often than noise, Q(Q^-1(0.01) + 1.75) = 2.3e-5, about 9 in 400,000."""
    r = the_run()
    lower_tail = 0.5 * math.erfc((2.5758293035489004 + 1.75) / SQRT2)
    assert lower_tail == pytest.approx(7.6e-6, abs=5e-8)
    assert r["negated_matched_exact"] == pytest.approx(0.5 * math.erfc((2.3263478740408408 + 1.75) / SQRT2), rel=1e-9)
    assert r["negated_matched_exact"] * 400_000 == pytest.approx(9.15, abs=0.005)
    assert r["negated_matched_found"] <= 30, "the matched filter found a negated pulse it should not"
    assert r["negated_rectified_against_exact"]["inside"], r["negated_rectified_against_exact"]
    assert r["negated_rectified_found"] > 70_000


def test_control_statistics__d11_a_rectifier_that_is_not_an_absolute_value_is_caught(monkeypatch):
    """The broken thing: a "rectifier" that passes its input through. Two checks of this file must
    report it: noise alone then crosses the rectifier's threshold half as often as claimed, and the
    negated pulse is no longer found."""
    monkeypatch.setattr(d11, "rectify", lambda scores: scores)
    r = d11.run(trials=100_000)
    # sqrt(0.01 * 0.99 / 100000) = 0.000315; 4 of them = 0.00126; the broken rate is near 0.005
    assert abs(r["false_alarm_rectified_known"] - 0.01) > 0.00126
    assert r["false_alarm_rectified_known"] == pytest.approx(0.005, abs=0.001)
    assert not r["negated_rectified_against_exact"]["inside"]
    assert r["negated_rectified_found"] <= 10
    # and what does NOT report it: the count on the pulse itself. A stated limit of the script.
    assert r["rectified_known_against_exact"]["inside"]


def test_stat_d11_the_thresholds_give_the_false_alarm_rate_they_claim():
    r = the_run()
    # 400,000 noise-only trials at pfa 0.01: se = sqrt(0.01 * 0.99 / 400000) = 0.000157; 4 se = 0.00063.
    assert math.sqrt(0.01 * 0.99 / 400_000) == pytest.approx(0.000157, abs=5e-7)
    assert abs(r["false_alarm_matched_known"] - 0.01) <= 0.00063
    assert abs(r["false_alarm_rectified_known"] - 0.01) <= 0.00063


def test_stat_d11_main_prints_seed_trial_count_and_run_time(capsys, monkeypatch):
    monkeypatch.setattr(d11, "run", the_run)       # print the run already made; do not simulate twice
    assert d11.main() == 0
    out = capsys.readouterr().out
    assert "seed 20261123" in out
    assert "400000 trials with the pulse and 400000 without" in out
    assert "run time" in out and " s" in out.splitlines()[-1]
    assert "= 0.2822" in out and "= 0.2045" in out
    assert out.count("INSIDE D8's tolerance") == 2 and out.count("OUTSIDE D8's tolerance") == 2
    assert "a pulse of the opposite sign" in out


def test_stat_d11_a_smaller_run_with_another_seed_agrees():
    """Not the same draw twice: a different seed, a tenth of the trials, the same verdicts."""
    r = d11.run(trials=40_000, seed=7)
    assert r["trials"] == 40_000 and r["seed"] == 7
    assert r["matched_known"]["inside"] and not r["rectified_known"]["inside"]
    assert r["matched_known"]["found"] != the_run()["matched_known"]["found"]

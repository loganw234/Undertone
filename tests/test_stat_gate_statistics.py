"""STAT: the statistics gate. A correct matched filter is inside the tolerance of D8; a wrong one is outside.

THE DATA. `stats.synth` streams: rounded Gaussian noise with the reference pulse added at a fixed
spacing. They exercise the code in `stats/`. They are not the instrument's generator.

  s16x1   the pulse at amplitude 1 on the one channel; 200,000 injections 64 frames apart (back to
          back, the least spacing at which they are separate trials); a second, pulse-free stream
          of 6,400,000 frames for thresholds measured from noise.
  s24x3   the pulse with a DIFFERENT gain on each channel, (3, -1, 2), and each channel its own
          noise; 25,000 injections 128 frames apart, so the same stream has one signal-free score
          in each gap, and the measured threshold comes from the stream itself.

THE OPERATING POINT. False-alarm probability 0.01, and sigma chosen so that the pulse's deflection
d = norm(s) / sigma equals Q^-1(0.01) = 2.3263. D8 then gives exactly one half, where the curve is
steepest and a wrong filter costs the most efficiency.

EQUAL FALSE-ALARM RATE, NEVER EQUAL THRESHOLD. Every coefficient set is given the threshold that
gives THAT set a false-alarm probability of 0.01 (D0, comparison rule 3). A wrong filter is then
wrong only in what it finds.

THE TOLERANCE. 4 standard errors (stats.tolerance). At 200,000 injections: 0.00447. At 25,000:
0.01265. With a measured threshold it is wider, and says so.

THE CHANCE OF A FALSE ALARM IN THESE TESTS. Seeds are fixed, so the answers do not change from run
to run. Over seeds, each `inside` assertion fails for a correct implementation with probability
6.3e-5, and each `outside` assertion passes for the stated fault with the probability its test
gives. A control prints the figures it saw: run pytest with -s to read them.
"""
import math

import numpy as np
import pytest

from spec import constants as C
from stats import matched, quantise, recovery, synth, theory, tolerance

PFA = 0.01
Z01 = 2.3263478740408408            # Q^-1(0.01), from tables
PULSE = C.PULSES["e0"]
TAPS = len(PULSE)
ENERGY = sum(v * v for v in PULSE)  # integer arithmetic on the definition's samples

SETUPS = {
    "s16x1": {"gains": (1,), "injections": 200_000, "spacing": 64, "noise_frames": 6_400_000, "seed": 2026112301},
    "s24x3": {"gains": (3, -1, 2), "injections": 25_000, "spacing": 128, "noise_frames": 0, "seed": 2026112303},
}


class Data:
    """One profile's stream, its truth, and a cache of what each coefficient set found on it."""

    def __init__(self, profile_name):
        s = SETUPS[profile_name]
        self.profile = profile_name
        self.rows = matched.template(PULSE, s["gains"])
        self.sigma = math.sqrt(sum(g * g for g in s["gains"]) * ENERGY) / Z01
        self.truth = synth.schedule(s["injections"], s["spacing"])
        frames = s["injections"] * s["spacing"]
        self.stream = synth.inject(synth.noise(profile_name, frames, self.sigma, s["seed"]),
                                   profile_name, self.rows, self.truth)
        self.noise_only = (synth.noise(profile_name, s["noise_frames"], self.sigma, s["seed"] + 1)
                           if s["noise_frames"] else None)
        self._cache = {}

    def count(self, scores, threshold, window=0):
        return recovery.recovery_count(scores, self.truth, threshold, lag=TAPS - 1, taps=TAPS,
                                       pulse_len=TAPS, window=window)

    def evaluate(self, key, coeffs, measured=False):
        """Filter the stream once with `coeffs` and count what it found at the injected index.

        "known"      at the threshold sigma gives THIS set for PFA
        "measured"   (when asked) at a threshold measured from this set's own signal-free scores,
                     with "threshold" what `threshold_from_scores` returned and "free" those scores
        """
        have = self._cache.get(key)
        if have is None or (measured and "measured" not in have):
            scores = matched.matched_scores(self.stream, self.profile, coeffs)
            have = {"known": self.count(scores, recovery.threshold_known_sigma(PFA, self.sigma, coeffs))}
            if measured:
                if self.noise_only is None:
                    free = recovery.signal_free_scores(scores, TAPS, self.truth, TAPS)
                else:
                    free = recovery.signal_free_scores(
                        matched.matched_scores(self.noise_only, self.profile, coeffs), TAPS, [], TAPS)
                have["free"] = free
                have["threshold"] = recovery.threshold_from_scores(free, PFA)
                have["measured"] = self.count(scores, have["threshold"]["threshold"])
            self._cache[key] = have
        return have


_BUILT = {}


def built(profile_name):
    """Each profile's stream is made once for the whole file."""
    if profile_name not in _BUILT:
        _BUILT[profile_name] = Data(profile_name)
    return _BUILT[profile_name]


@pytest.fixture(params=sorted(SETUPS))
def data(request):
    return built(request.param)


@pytest.fixture
def data16():
    return built("s16x1")


@pytest.fixture
def data24():
    return built("s24x3")


def against_d8(r):
    """The check, with the CLAIM that the detector is the matched filter: d = norm(s) / sigma = Z01."""
    return tolerance.check_efficiency(r["at_index"], r["n"], PFA, Z01)


def against_d8_measured(have):
    t = have["threshold"]
    return tolerance.check_efficiency(have["measured"]["at_index"], have["measured"]["n"], t["pfa_effective"], Z01, t["m"])


def show(label, c, extra=""):
    print("\n%s: found %d of %d, efficiency %.5f, D8 %.5f, deviation %+.5f = %+.1f se, tolerance %.5f, %s%s"
          % (label, c["found"], c["n"], c["measured"], c["expected"], c["deviation"], c["z_score"],
             c["tolerance"], "INSIDE" if c["inside"] else "OUTSIDE", extra))


def correct_set(data, which):
    return data.rows if which == "real" else quantise.quantise(data.rows)


# --------------------------------------------------------------------- the data is what it says

def test_stat_the_setups_are_at_the_stated_operating_point(data):
    s = SETUPS[data.profile]
    assert ENERGY == sum(v * v for v in C.PULSES["e0"]) and TAPS == 64
    assert theory.deflection(data.rows, data.rows, data.sigma) == pytest.approx(Z01, rel=1e-12)
    assert theory.pd_matched(PFA, theory.deflection(data.rows, data.rows, data.sigma)) == pytest.approx(0.5, abs=1e-9)
    assert data.stream.shape == (s["injections"] * s["spacing"], C.PROFILES[data.profile]["channels"])
    assert len(data.truth) == s["injections"] and int(data.truth[1] - data.truth[0]) == s["spacing"]
    assert s["spacing"] >= recovery.minimum_spacing(TAPS, TAPS, TAPS - 1, 0) == 64
    # the tolerance bites: 4 se is about half a point at 200,000 injections and 1.3 points at 25,000
    t = tolerance.tolerance(PFA, Z01, s["injections"])
    assert t["tolerance"] == pytest.approx({200_000: 0.0044721, 25_000: 0.0126491}[s["injections"]], abs=5e-8)


def test_stat_the_test_noise_has_the_stated_spread_and_differs_by_channel(data):
    quiet = data.stream if data.noise_only is None else data.noise_only
    channels = quiet.shape[1]
    for c in range(channels):
        # Where the stream carries pulses they add gain^2 * energy / spacing per frame to the variance.
        added = 0.0 if data.noise_only is not None else SETUPS[data.profile]["gains"][c] ** 2 * ENERGY / 128
        assert float(quiet[:, c].std()) == pytest.approx(math.sqrt(data.sigma ** 2 + added), rel=0.005)
    for a in range(channels):
        for b in range(a + 1, channels):
            assert not np.array_equal(quiet[:, a], quiet[:, b]), "two channels carry one stream"
            # the pulses correlate two channels a little (at most 0.02 here); one stream copied would give 1
            assert abs(float(np.corrcoef(quiet[:20000, a], quiet[:20000, b])[0, 1])) < 0.1


# --------------------------------------------------------------------- the gate: a correct filter

@pytest.mark.parametrize("which", ["real", "quantised"])
def test_gate_statistics__the_matched_filter_is_inside_the_tolerance_of_d8__known_threshold(data, which):
    coeffs = correct_set(data, which)
    if which == "quantised":
        assert matched.scores_are_exact(data.profile, coeffs)
        assert int(np.abs(coeffs).max()) == C.COEFF_MAX
    r = data.evaluate(which, coeffs, measured=True)["known"]
    c = against_d8(r)
    show("%s %s, known threshold" % (data.profile, which), c)
    assert r["n"] == SETUPS[data.profile]["injections"]
    assert c["inside"], c
    assert c["expected"] == pytest.approx(0.5, abs=1e-9)


@pytest.mark.parametrize("which", ["real", "quantised"])
def test_gate_statistics__the_matched_filter_is_inside_the_tolerance_of_d8__measured_threshold(data, which):
    coeffs = correct_set(data, which)
    have = data.evaluate(which, coeffs, measured=True)
    t = have["threshold"]
    c = against_d8_measured(have)
    show("%s %s, measured threshold (m = %d)" % (data.profile, which, t["m"]), c)
    assert t["m"] == {"s16x1": 100_000, "s24x3": 25_000}[data.profile]
    assert t["k"] == t["above"] == t["m"] // 100
    assert c["inside"], c
    # The measured threshold is near the known one: within 5 of ITS standard errors, which in
    # standard units is sqrt(pfa (1 - pfa) / m) / density(Q^-1(pfa)): 0.0118 at m = 100,000.
    known = recovery.threshold_known_sigma(PFA, data.sigma, coeffs)
    density = math.exp(-0.5 * Z01 * Z01) / math.sqrt(2 * math.pi)
    assert abs(t["threshold"] - known) / (known / Z01) <= 5 * math.sqrt(PFA * (1 - PFA) / t["m"]) / density
    # and the tolerance says it is wider than the binomial one alone
    assert c["se_total"] > 2 * c["se_binomial"]


def test_gate_statistics__noise_alone_crosses_the_known_threshold_at_the_stated_rate(data):
    """A threshold that gave the wrong false-alarm rate would move every efficiency in this file."""
    coeffs = correct_set(data, "quantised")
    free = data.evaluate("quantised", coeffs, measured=True)["free"]
    threshold = recovery.threshold_known_sigma(PFA, data.sigma, coeffs)
    crossings = int((free > threshold).sum())
    c = tolerance.check_count(crossings, len(free), PFA)
    print("\n%s noise alone: %d of %d cross, rate %.5f, %+.1f se from %.2f"
          % (data.profile, crossings, len(free), c["measured"], c["z_score"], PFA))
    assert len(free) in (100_000, 25_000)
    assert c["inside"], c


# --------------------------------------------------------------------- the controls: wrong filters

def wrong_filter_report(data, label, wrong, measured=False):
    """Hand a wrong coefficient set to the SAME check, as if it were the matched filter.

    Returns (the check against D8, the check against the wrong set's own prediction or None when
    that prediction is too near zero for a tolerance, the predicted efficiency).
    """
    predicted_d = theory.deflection(wrong, data.rows, data.sigma)
    r = data.evaluate(label, wrong, measured)["known"]
    as_matched = against_d8(r)
    predicted = theory.pd_matched(PFA, predicted_d)
    show("CONTROL %s %s" % (data.profile, label), as_matched,
         "; its own prediction %.5f (cosine %.5f)" % (predicted, predicted_d / Z01))
    own = None
    if r["n"] * predicted * (1 - predicted) >= tolerance.MIN_NPQ:
        own = tolerance.check_efficiency(r["at_index"], r["n"], PFA, predicted_d)
    return as_matched, own, predicted


def tap_51_flipped(data16):
    wrong = data16.rows.copy()
    wrong[0, 51] = -wrong[0, 51]
    return wrong


def test_control_statistics__one_small_tap_with_its_sign_flipped_falls_outside(data16):
    """THE STATED MARGIN. Tap 51 of the pulse is 293; the wrong set has -293 there.

    Its cosine with the pulse is 0.98546, so its predicted efficiency is 0.48651: 0.01349 below D8.
    At 200,000 injections that is 12.1 standard errors, and 8.1 beyond the tolerance's edge. The
    chance of this fault landing inside is Q(8.07), below 1e-15.
    """
    assert PULSE[51] == 293
    as_matched, own, predicted = wrong_filter_report(data16, "tap 51 flipped", tap_51_flipped(data16))
    assert predicted == pytest.approx(0.48651, abs=5e-6)
    assert 1 - 2 * 293 ** 2 / ENERGY == pytest.approx(0.98546, abs=5e-6)       # the cosine, by hand
    assert not as_matched["inside"], "a filter wrong by the stated margin passed the check"
    assert as_matched["deviation"] < -as_matched["tolerance"], "and it must fall BELOW"
    assert own["inside"], "it fell outside, but not where its own prediction puts it: %r" % (own,)
    # the margin as stated: 0.01349 is more than the catch margin of 0.00894
    assert 0.5 - predicted > tolerance.catch_margin(PFA, Z01, as_matched["n"])


def test_control_statistics__a_tolerance_for_the_wrong_trial_count_would_pass_that_fault(data16):
    """The trap in the brief, on the detector itself: the tap-51 fault, judged with a tolerance worked
    for 10,000 injections when 200,000 were run, is INSIDE. The right count puts it outside."""
    right = against_d8(data16.evaluate("tap 51 flipped", tap_51_flipped(data16))["known"])
    too_wide = tolerance.tolerance(PFA, Z01, 10_000)["tolerance"]
    assert too_wide == pytest.approx(0.020, abs=1e-9)
    assert abs(right["deviation"]) <= too_wide, "the too-wide tolerance did not pass the fault: the control shows nothing"
    assert not right["inside"]


def test_control_statistics__time_reversed_coefficients_fall_outside(data16):
    """A convolution written where a correlation was meant. The cosine is -0.924: it finds almost nothing."""
    as_matched, own, predicted = wrong_filter_report(data16, "reversed", data16.rows[:, ::-1].copy())
    assert predicted < 1e-5
    assert not as_matched["inside"]
    assert as_matched["measured"] < 0.001, "a reversed filter found pulses it should not"
    assert own is None, "its own prediction is too near zero for a tolerance, and the check must say so"


@pytest.mark.parametrize("channel, cosine, predicted", [(0, 0.59761, 0.17461), (1, 0.96362, 0.46628), (2, 0.84515, 0.35934)])
def test_control_statistics__a_filter_that_ignores_one_channel_falls_outside(data24, channel, cosine, predicted):
    """A FAULT IN ONE CHANNEL ONLY. The gains are (3, -1, 2), so the channels carry 9, 1 and 4 parts
    of 14 of the pulse's energy, and zeroing one leaves a cosine of sqrt(5/14), sqrt(13/14), sqrt(10/14).
    The least of the three effects, channel 1, is 0.0337 below D8: 10.7 standard errors at 25,000
    injections and 6.7 beyond the tolerance's edge (chance of landing inside: Q(6.66), about 1e-11)."""
    gains = SETUPS["s24x3"]["gains"]
    assert math.sqrt(1 - gains[channel] ** 2 / 14) == pytest.approx(cosine, abs=5e-6)
    wrong = data24.rows.copy()
    wrong[channel, :] = 0
    as_matched, own, got = wrong_filter_report(data24, "channel %d zeroed" % channel, wrong, measured=(channel == 2))
    assert got == pytest.approx(predicted, abs=5e-6)
    assert not as_matched["inside"]
    assert as_matched["deviation"] < -as_matched["tolerance"]
    assert own["inside"], own


def test_control_statistics__a_wrong_filter_falls_outside_with_a_measured_threshold_too(data):
    """With a measured threshold the tolerance is wider, so the fault has to be larger to be seen.

    s16x1: tap 20 (value 706) sign-flipped, cosine 0.9156, predicted 0.4222, 0.0778 below D8,
           against a tolerance of 0.0194 (m = 100,000).
    s24x3: channel 2 zeroed, cosine 0.8452, predicted 0.3593, 0.1407 below D8,
           against a tolerance of 0.0397 (m = 25,000).
    The small fault of the first control, 0.0135, is INSIDE these tolerances: a stated limit.
    """
    wrong = data.rows.copy()
    if data.profile == "s16x1":
        assert PULSE[20] == 706
        wrong[0, 20] = -wrong[0, 20]
        label, shortfall, width = "tap 20 flipped", 0.07783, 0.0194
    else:
        wrong[2, :] = 0
        label, shortfall, width = "channel 2 zeroed", 0.14066, 0.0397
    predicted = theory.pd_matched(PFA, theory.deflection(wrong, data.rows, data.sigma))
    assert 0.5 - predicted == pytest.approx(shortfall, abs=5e-6)
    have = data.evaluate(label, wrong, measured=True)
    c = against_d8_measured(have)
    show("CONTROL %s %s, measured threshold (m = %d)" % (data.profile, label, have["threshold"]["m"]), c)
    assert c["tolerance"] == pytest.approx(width, abs=5e-5)
    assert not c["inside"]
    assert c["deviation"] < -c["tolerance"]
    # the limit, shown: the first control's small fault would be passed at this tolerance
    assert 0.01349 < c["tolerance"]


# --------------------------------------------------------------------- the cost of quantisation

def test_stat_quantising_to_18_bits_costs_nothing_that_can_be_measured(data16):
    """Same stream, same injections, real coefficients against quantised ones, each at its own threshold.

    The 18-bit set's cosine with the pulse is 1 - 1.1e-11, so the two detectors should disagree on
    about 0.3 of 200,000 injections. More than 5 would be an error (chance below 1e-5 if Poisson).
    """
    real = data16.evaluate("real", data16.rows, measured=True)["known"]
    q18 = quantise.quantise(data16.rows)
    cosine = theory.deflection(q18, data16.rows, data16.sigma) / Z01
    assert 0 < 1 - cosine < 2e-11
    cost = recovery.paired_cost(real["hits_at_index"],
                                data16.evaluate("quantised", q18, measured=True)["known"]["hits_at_index"])
    print("\n18-bit cost: a_only %d, b_only %d, cost %+.2e, se %.2e" % (cost["a_only"], cost["b_only"], cost["cost"], cost["se"]))
    assert cost["n"] == 200_000
    assert cost["a_only"] + cost["b_only"] <= 5
    assert abs(cost["cost"]) <= 5 / 200_000


def test_stat_a_coarse_quantiser_has_a_cost_and_the_paired_count_finds_it(data16):
    """Three-bit coefficients: cosine 0.98990, predicted efficiency 0.49063, predicted cost 0.00937.

    The paired standard error is about 0.0005, a third of the 0.0016 an unpaired difference of two
    efficiencies would carry, so the cost stands about 20 of its standard errors clear of zero
    and not 6.
    """
    real = data16.evaluate("real", data16.rows, measured=True)["known"]
    q3 = quantise.quantise(data16.rows, bits=3)
    assert int(np.abs(q3).max()) == 3
    predicted_d = theory.deflection(q3, data16.rows, data16.sigma)
    assert predicted_d / Z01 == pytest.approx(0.98990, abs=5e-6)
    predicted_cost = 0.5 - theory.pd_matched(PFA, predicted_d)
    assert predicted_cost == pytest.approx(0.00937, abs=5e-6)
    coarse = data16.evaluate("three bits", q3)["known"]
    cost = recovery.paired_cost(real["hits_at_index"], coarse["hits_at_index"])
    print("\n3-bit cost: a_only %d, b_only %d, cost %.5f, paired se %.5f, predicted %.5f"
          % (cost["a_only"], cost["b_only"], cost["cost"], cost["se"], predicted_cost))
    assert abs(cost["cost"] - predicted_cost) <= 4 * cost["se"]
    assert cost["cost"] > 10 * cost["se"], "the cost is there and the paired count did not see it"
    unpaired = math.sqrt(2) * tolerance.binomial_se(0.5, cost["n"])
    assert cost["se"] < 0.4 * unpaired
    # and the coarse filter, judged as if it were the matched filter, is outside D8's tolerance
    assert not against_d8(coarse)["inside"]


# --------------------------------------------------------------------- the window is another test

def test_stat_a_window_finds_more_and_false_alarms_more_so_d8_does_not_describe_it(data24):
    """Found within +/-8 samples is a different test from found at the injected index.

    On pulses it can only find more. On noise alone it crosses more often than the false-alarm
    probability the threshold was set for, by up to 17 times (the union of 17 scores). So the
    window count is not compared with D8, here or anywhere.
    """
    coeffs = quantise.quantise(data24.rows)
    threshold = recovery.threshold_known_sigma(PFA, data24.sigma, coeffs)
    r = data24.count(matched.matched_scores(data24.stream, "s24x3", coeffs), threshold, window=8)
    assert r["minimum_spacing"] == 80 <= 128
    assert r["in_window"] > r["at_index"]
    assert (r["hits_in_window"] | ~r["hits_at_index"]).all(), "found at the index but not within the window"
    assert not against_d8({"at_index": r["in_window"], "n": r["n"]})["inside"], \
        "the window count happened to match D8: the test of the limit shows nothing"
    # noise alone: 9,000 places in a pulse-free stream, read as if a pulse had been put at each
    quiet = synth.noise("s24x3", 1_280_000, data24.sigma, 2026112304)
    places = synth.schedule(9_000, 128, first=64)
    q = recovery.recovery_count(matched.matched_scores(quiet, "s24x3", coeffs), places, threshold,
                                lag=TAPS - 1, taps=TAPS, pulse_len=TAPS, window=8)
    at, win = q["at_index"] / q["n"], q["in_window"] / q["n"]
    print("\npulses: found at the index %.4f, within +/-8 %.4f; noise alone, 9000 places: at the index %.4f, within +/-8 %.4f"
          % (r["at_index"] / r["n"], r["in_window"] / r["n"], at, win))
    assert tolerance.check_count(q["at_index"], q["n"], PFA)["inside"]
    assert 2 * PFA < win <= 17 * PFA

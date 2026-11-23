"""MOD-A's tests of model/inject.py: the injection gate, its controls, the refusals, and truth isolation.

The check behind the gate rebuilds what was injected from the truth records and the pulse with
`fractions.Fraction` and Python's own `round` (tests/test_mod_a_reference.py), never with the
model's arithmetic, and compares it with output minus input at every frame of every channel.
Hand-worked samples are in vectors/mod-a/injection.json.
"""
import fractions
import math

import numpy as np
import pytest

from spec import constants as C
from model import inject, records, source
from model.refusal import Refusal

import test_mod_a_reference as ref

PROFILES = sorted(C.PROFILES)
PULSE_NAME = {i: name for name, i in C.PULSE_IDS.items()}       # inverted here, not taken from the model
E0 = C.PULSE_IDS["e0"]
L = len(C.PULSES["e0"])

FRAMES = 4096
SIGMA = {"s16x1": (300, 1), "s24x3": (50000, 1)}
# Six injections, none of amplitude zero, both signs, and 3/2 puts ties on e0's odd samples.
SCHEDULE = [{"index": 5, "pulse_id": E0, "amplitude_num": 3, "amplitude_den": 2},
            {"index": 100, "pulse_id": E0, "amplitude_num": -7, "amplitude_den": 4},
            {"index": 777, "pulse_id": E0, "amplitude_num": 1, "amplitude_den": 1},
            {"index": 1500, "pulse_id": E0, "amplitude_num": 5, "amplitude_den": 3},
            {"index": 2600, "pulse_id": E0, "amplitude_num": -2, "amplitude_den": 1},
            {"index": 4000, "pulse_id": E0, "amplitude_num": 33, "amplitude_den": 10}]


def rec(index, num=1, den=1, pulse_id=E0):
    return {"index": index, "pulse_id": pulse_id, "amplitude_num": num, "amplitude_den": den}


def refused(name, call):
    with pytest.raises(Refusal) as e:
        call()
    assert e.value.name == name, "refused as %s, expected %s" % (e.value.name, name)
    return e.value


_noise = {}


def noise_frames(name):
    """The input stream: seeded noise, a different value in every channel. Drawn once."""
    if name not in _noise:
        _noise[name] = list(source.Noise(name, 31, SIGMA[name][0], SIGMA[name][1], FRAMES))
    return _noise[name]


def silence(name, frames):
    return [(0,) * C.PROFILES[name]["channels"]] * frames


def injection_findings(name, frames_in, frames_out, truth):
    """What the truth says was added, rebuilt with other arithmetic, against output minus input.

    An empty list is a pass. A run with no truth record, or whose truth adds only zeros, is a
    finding: it would pass while testing nothing.
    """
    channels = C.PROFILES[name]["channels"]
    a = np.array(frames_in, dtype=np.int64).reshape(-1, channels)
    b = np.array(frames_out, dtype=np.int64).reshape(-1, channels)
    if len(truth) == 0:
        return ["NOTHING-INJECTED: no truth record"]
    want = np.zeros(len(a), dtype=np.int64)
    for r in truth:
        added = ref.ref_scaled(C.PULSES[PULSE_NAME[r["pulse_id"]]], r["amplitude_num"], r["amplitude_den"])
        if r["index"] + len(added) > len(a):
            return ["a truth record at %d runs past the %d frames" % (r["index"], len(a))]
        want[r["index"]:r["index"] + len(added)] += np.array(added, dtype=np.int64)
    if not want.any():
        return ["NOTHING-INJECTED: every sample the truth says was added is zero"]
    if a.shape != b.shape:
        return ["%d frames went in and %d came out" % (len(a), len(b))]
    wrong = np.argwhere((b - a) != want[:, None])
    if len(wrong):
        f, c = (int(v) for v in wrong[0])
        return ["%d samples are not what the truth says; the first is frame %d channel %d: %d was added, "
                "the truth says %d" % (len(wrong), f, c, int(b[f, c] - a[f, c]), int(want[f]))]
    return []


def run(injector, name, schedule=None, frames_in=None):
    """Run an injector over the noise; returns (input frames, output frames, truth)."""
    frames_in = noise_frames(name) if frames_in is None else frames_in
    stream, truth = injector(name, iter(frames_in), SCHEDULE if schedule is None else schedule, len(frames_in))
    return frames_in, list(stream), truth


# ---------------------------------------------------------------- the gate

@pytest.mark.parametrize("name", PROFILES)
def test_gate_injection__the_stream_differs_from_its_input_by_exactly_what_the_truth_says(name):
    frames_in, frames_out, truth = run(inject.inject, name)
    assert injection_findings(name, frames_in, frames_out, truth) == []
    assert list(truth) == SCHEDULE, "the truth is the schedule, in order"
    assert b"".join(records.pack("truth", r) for r in truth) == b"".join(records.pack("truth", r) for r in SCHEDULE)
    changed = sum(1 for x, y in zip(frames_in, frames_out) if x != y)
    zeros_in_e0 = sum(1 for v in C.PULSES["e0"] if v == 0)
    assert zeros_in_e0 == 9 and changed == len(SCHEDULE) * (L - zeros_in_e0), "every non-zero pulse sample landed"
    # a truth index is the pulse's FIRST sample (docs/model/conventions.md, convention (a)): e0[0] is 0,
    # so the first frame to change is index + 1, by e0[1] times the amplitude
    first = SCHEDULE[2]["index"]
    assert frames_out[first] == frames_in[first]
    assert [y - x for x, y in zip(frames_in[first + 1], frames_out[first + 1])] == [1] * len(frames_in[0])
    assert [y - x for x, y in zip(frames_in[first + 28], frames_out[first + 28])] == [-970] * len(frames_in[0])


def test_gate_injection__added_samples_equal_the_hand_worked_ones():
    v = ref.vector("injection.json")
    for case in v["whole"]:
        assert len(case["added"]) == L
        assert list(inject.scaled_pulse(E0, case["amplitude_num"], case["amplitude_den"])) == case["added"]
        assert ref.ref_scaled(C.PULSES["e0"], case["amplitude_num"], case["amplitude_den"]) == case["added"]
    assert len(v["single"]) >= 20
    for case in v["single"]:
        assert C.PULSES["e0"][case["sample"]] == case["pulse_value"], case
        got = inject.scaled_pulse(E0, case["amplitude_num"], case["amplitude_den"])[case["sample"]]
        assert got == case["added"], case["why"]
    # and through a stream, on silence, in every channel
    for name in PROFILES:
        case = v["whole"][0]
        stream, _truth = inject.inject(name, silence(name, 70), [rec(3, case["amplitude_num"], case["amplitude_den"])], 70)
        out = list(stream)
        channels = C.PROFILES[name]["channels"]
        assert out[3:3 + L] == [(d,) * channels for d in case["added"]]
        assert out[:3] == silence(name, 3) and out[3 + L:] == silence(name, 3)


def test_gate_injection__the_integer_rounding_is_half_to_even_everywhere():
    assert C.INJECT_ROUNDING == "half_to_even"
    # by hand: 1/2 -> 0, 3/2 -> 2, 5/2 -> 2, -1/2 -> 0, -3/2 -> -2, -5/2 -> -2, 7/3 -> 2, -7/3 -> -2, 8/3 -> 3
    hand = {(1, 2): 0, (3, 2): 2, (5, 2): 2, (-1, 2): 0, (-3, 2): -2, (-5, 2): -2, (7, 3): 2, (-7, 3): -2,
            (8, 3): 3, (-8, 3): -3, (0, 5): 0, (6, 3): 2, (-6, 3): -2}
    for (num, den), want in hand.items():
        assert inject._round_half_even(num, den) == want, (num, den)
    # against Python's own round on exact fractions, at the field's extremes and at awkward ratios
    nums = (-2 ** 31, -1000003, -7, -3, -1, 0, 1, 2, 3, 5, 970, 2 ** 31 - 1)
    dens = (1, 2, 3, 4, 7, 970, 1940, 65536, 2 ** 32 - 1)
    checked = 0
    for num in nums:
        for den in dens:
            want = ref.ref_scaled(C.PULSES["e0"], num, den)
            assert list(inject.scaled_pulse(E0, num, den)) == want
            # odd symmetry: the negated amplitude adds the negated samples
            if num != -2 ** 31:
                assert list(inject.scaled_pulse(E0, -num, den)) == [-d for d in want]
            checked += 1
    assert checked == len(nums) * len(dens)


def test_gate_injection__a_check_with_nothing_injected_is_refused_not_passed():
    name = "s16x1"
    frames_in, frames_out, truth = run(inject.inject, name, schedule=[])
    assert frames_out == frames_in
    assert injection_findings(name, frames_in, frames_out, truth)[0].startswith("NOTHING-INJECTED")
    # amplitude zero, and an amplitude so small that every sample rounds to zero: accepted, and nothing is added
    for num, den in ((0, 1), (1, 5000)):
        frames_in, frames_out, truth = run(inject.inject, name, schedule=[rec(50, num, den)])
        assert frames_out == frames_in and list(truth) == [rec(50, num, den)]
        assert injection_findings(name, frames_in, frames_out, truth)[0].startswith("NOTHING-INJECTED")
    assert set(inject.scaled_pulse(E0, 1, 5000)) == {0}


# ---------------------------------------------------------------- the controls: broken injectors

def adds_nothing(name, frames, schedule, length):
    return iter(list(frames)), inject.schedule(schedule, length)


def shifted(by):
    def injector(name, frames, schedule, length):
        moved = [dict(r, index=r["index"] + by) for r in schedule]
        return inject.inject(name, frames, moved, length)[0], inject.schedule(schedule, length)
    return injector


def sign_flipped(name, frames, schedule, length):
    other = [dict(r, amplitude_num=-r["amplitude_num"]) for r in schedule]
    return inject.inject(name, frames, other, length)[0], inject.schedule(schedule, length)


def half_amplitude(name, frames, schedule, length):
    other = [dict(r, amplitude_den=2 * r["amplitude_den"]) for r in schedule]
    return inject.inject(name, frames, other, length)[0], inject.schedule(schedule, length)


def one_channel_only(channel):
    def injector(name, frames, schedule, length):
        frames = list(frames)
        stream, truth = inject.inject(name, iter(frames), schedule, length)
        out = [tuple(y[c] if c == channel else x[c] for c in range(len(x))) for x, y in zip(frames, stream)]
        return iter(out), truth
    return injector


def all_but_one_channel(channel):
    def injector(name, frames, schedule, length):
        frames = list(frames)
        stream, truth = inject.inject(name, iter(frames), schedule, length)
        out = [tuple(x[c] if c == channel else y[c] for c in range(len(x))) for x, y in zip(frames, stream)]
        return iter(out), truth
    return injector


def with_rounding(rounding):
    """An injector whose arithmetic is right but for the rounding of a sample."""
    def injector(name, frames, schedule, length):
        frames = list(frames)
        truth = inject.schedule(schedule, length)
        add = {}
        for r in truth:
            for j, p in enumerate(C.PULSES[PULSE_NAME[r["pulse_id"]]]):
                add[r["index"] + j] = rounding(fractions.Fraction(p * r["amplitude_num"], r["amplitude_den"]))
        return iter([tuple(v + add.get(n, 0) for v in f) for n, f in enumerate(frames)]), truth
    return injector


def caught(injector, name, schedule=None):
    frames_in, frames_out, truth = run(injector, name, schedule)
    findings = injection_findings(name, frames_in, frames_out, truth)
    assert len(findings) == 1 and "are not what the truth says" in findings[0], findings
    return findings[0]


@pytest.mark.parametrize("name", PROFILES)
def test_control_injection__an_injector_that_adds_nothing_is_caught(name):
    finding = caught(adds_nothing, name)
    # every non-zero sample of every pulse is missing, in every channel
    missing = len(SCHEDULE) * (L - 9) * C.PROFILES[name]["channels"]
    assert finding.startswith("%d samples" % missing) and "frame 6 channel 0: 0 was added, the truth says 2" in finding


@pytest.mark.parametrize("name", PROFILES)
def test_control_injection__an_injector_a_sample_late_or_early_is_caught(name):
    late = caught(shifted(1), name)
    assert "frame 6 channel 0: 0 was added, the truth says 2" in late       # e0[1] * 3/2 = 1.5 -> 2 is due at 5 + 1
    early = caught(shifted(-1), name)
    assert "frame 5 channel 0: 2 was added, the truth says 0" in early


@pytest.mark.parametrize("name", PROFILES)
def test_control_injection__an_injector_with_the_sign_flipped_is_caught(name):
    assert "frame 6 channel 0: -2 was added, the truth says 2" in caught(sign_flipped, name)


@pytest.mark.parametrize("name", PROFILES)
def test_control_injection__an_injector_at_half_amplitude_is_caught(name):
    # 3/4 where the truth says 3/2: e0[1] gives 0.75 -> 1, not 2
    assert "frame 6 channel 0: 1 was added, the truth says 2" in caught(half_amplitude, name)


def test_control_injection__a_pulse_in_one_channel_only_or_missing_from_one_is_caught():
    name = "s24x3"
    for channel in range(3):
        finding = caught(one_channel_only(channel), name)
        assert "channel %d" % (0 if channel else 1) in finding, "the first channel left without the pulse"
        assert finding.startswith("%d samples" % (len(SCHEDULE) * (L - 9) * 2))
        finding = caught(all_but_one_channel(channel), name)
        assert "channel %d" % channel in finding and finding.startswith("%d samples" % (len(SCHEDULE) * (L - 9)))


@pytest.mark.parametrize("name", PROFILES)
def test_control_injection__a_truth_record_missing_or_one_too_many_is_caught(name):
    def drops_a_record(name_, frames, schedule, length):
        stream, truth = inject.inject(name_, frames, schedule, length)
        return stream, truth[:2] + truth[3:]

    def invents_a_record(name_, frames, schedule, length):
        stream, truth = inject.inject(name_, frames, schedule, length)
        return stream, truth[:3] + (rec(1000, 1, 1),) + truth[3:]

    assert "frame 778 channel 0: 1 was added, the truth says 0" in caught(drops_a_record, name)
    assert "frame 1001 channel 0: 0 was added, the truth says 1" in caught(invents_a_record, name)


@pytest.mark.parametrize("name", PROFILES)
def test_control_injection__a_changed_rounding_is_caught(name):
    # A tie upward, where the rule says to the even one: 7 * 3/2 = 10.5 is 10, and upward gives 11.
    upward = caught(with_rounding(lambda x: math.floor(x + fractions.Fraction(1, 2))), name)
    assert "frame 7 channel 0: 11 was added, the truth says 10" in upward
    # Toward zero: 1 * 3/2 = 1.5 is 2, and cutting gives 1.
    cut = caught(with_rounding(lambda x: int(x)), name)
    assert "frame 6 channel 0: 1 was added, the truth says 2" in cut
    # And the right rounding, written the same way, passes: the wrapper is not what is being caught.
    frames_in, frames_out, truth = run(with_rounding(round), name)
    assert injection_findings(name, frames_in, frames_out, truth) == []


def test_control_injection__the_same_faults_on_zero_amplitude_would_not_be_seen():
    # Why the gate's schedule has no zero amplitude: every broken injector above agrees with the
    # shipped one there, and the check says so rather than passing.
    name, nothing = "s16x1", [rec(5, 0, 1), rec(100, 0, 3)]
    for injector in (adds_nothing, shifted(1), sign_flipped, half_amplitude):
        frames_in, frames_out, truth = run(injector, name, schedule=nothing)
        assert frames_out == frames_in
        assert injection_findings(name, frames_in, frames_out, truth)[0].startswith("NOTHING-INJECTED")


# ---------------------------------------------------------------- refusals, each with a neighbour that is accepted

def test_mod_a_a_second_pulse_reaches_its_own_samples_and_keeps_its_own_length(monkeypatch):
    # One pulse is declared. A second, three samples long, is declared here for this test only, so
    # that a pulse id is seen to pick its own samples and its own length. Nothing in the tree changes.
    monkeypatch.setitem(C.PULSES, "t3", (5, -3, 2))
    monkeypatch.setitem(C.PULSE_IDS, "t3", 7)
    assert inject.pulse(7) == (5, -3, 2) and inject.pulse(E0) == C.PULSES["e0"]
    assert inject.scaled_pulse(7, -3, 2) == (-8, 4, -3)             # -7.5 -> -8, 4.5 -> 4, -3
    name = "s24x3"
    schedule = [rec(10), rec(74, 2, 1, pulse_id=7), rec(77, 1, 1, pulse_id=7), rec(80, -1, 1)]
    stream, truth = inject.inject(name, silence(name, 150), schedule, 150)
    out = [f[0] for f in stream]
    assert out[74:80] == [10, -6, 4, 5, -3, 2] and out[80 + 28] == 970 and out[10 + 28] == -970
    assert list(truth) == schedule
    # the three-sample pulse ends after three frames: the next may start there, and not one earlier
    refused("INJECT_OVERLAP", lambda: inject.schedule([rec(74, pulse_id=7), rec(76, pulse_id=7)], 150))
    refused("INJECT_PAST_END", lambda: inject.schedule([rec(148, pulse_id=7)], 150))
    assert len(inject.schedule([rec(147, pulse_id=7)], 150)) == 1
    refused("PULSE_UNKNOWN", lambda: inject.pulse(3))


def test_mod_a_an_unknown_pulse_or_a_malformed_record_is_refused_by_name():
    assert sorted(C.PULSE_IDS.values()) == [0] and inject.pulse(0) == C.PULSES["e0"]
    for bad in (True, False, 0.0, None, "e0", -1, 65536):
        refused("PULSE_UNKNOWN", lambda: inject.pulse(bad))
    for bad in (1, 2, 65535):
        refused("PULSE_UNKNOWN", lambda: inject.schedule([rec(0, pulse_id=bad)], 100))
        refused("PULSE_UNKNOWN", lambda: inject.scaled_pulse(bad, 1, 1))
    for bad in (rec(0, den=0), rec(-1), rec(0, num=2 ** 31), rec(0, pulse_id=65536), rec(0, num=1.5),
                {"index": 0, "pulse_id": E0, "amplitude_num": 1}, dict(rec(0), channel=0), None, (0, 0, 1, 1)):
        refused("RECORD_FIELD", lambda: inject.schedule([bad], 100))
        refused("RECORD_FIELD", lambda: inject.inject("s16x1", silence("s16x1", 100), [rec(0), bad], 100))
    refused("RECORD_FIELD", lambda: inject.scaled_pulse(E0, 1, 0))
    refused("PROFILE_UNKNOWN", lambda: inject.inject("no-such", [], [], 0))
    assert inject.schedule([rec(0, 2 ** 31 - 1, 2 ** 32 - 1), rec(64, -2 ** 31, 1)], 128)[1]["amplitude_num"] == -2 ** 31


def test_mod_a_two_injections_that_overlap_or_are_out_of_order_are_refused_by_name():
    assert inject.schedule([rec(10), rec(10 + L)], 500) == (rec(10), rec(10 + L)), "one ends where the next starts"
    for second in (10 + L - 1, 10 + 1, 10, 9, 0):
        refused("INJECT_OVERLAP", lambda: inject.schedule([rec(10), rec(second)], 500))
    refused("INJECT_OVERLAP", lambda: inject.schedule([rec(200), rec(10)], 500))          # out of order, far apart
    refused("INJECT_OVERLAP", lambda: inject.schedule([rec(0), rec(100), rec(300), rec(363)], 500))
    e = refused("INJECT_OVERLAP", lambda: inject.inject("s24x3", silence("s24x3", 500), [rec(10), rec(73)], 500))
    assert "73" in e.detail and "74" in e.detail


def test_mod_a_an_injection_past_the_end_is_refused_by_name_before_any_frame():
    def untouchable():
        raise AssertionError("a frame was read before the schedule was checked")
        yield

    assert len(inject.schedule([rec(100 - L)], 100)) == 1, "a pulse may end on the last frame"
    for index, length in ((100 - L + 1, 100), (100, 100), (5000, 100), (0, L - 1), (0, 0)):
        refused("INJECT_PAST_END", lambda: inject.schedule([rec(index)], length))
        refused("INJECT_PAST_END", lambda: inject.inject("s16x1", untouchable(), [rec(index)], length))
    refused("INJECT_PAST_END", lambda: inject.schedule([rec(2 ** 64 - 1)], 2 ** 64))
    assert len(inject.schedule([rec(2 ** 64 - 1 - L)], 2 ** 64)) == 1
    # and the same for every other fault of a schedule
    refused("INJECT_OVERLAP", lambda: inject.inject("s16x1", untouchable(), [rec(10), rec(11)], 500))
    refused("PULSE_UNKNOWN", lambda: inject.inject("s16x1", untouchable(), [rec(10, pulse_id=9)], 500))
    refused("STREAM_LENGTH", lambda: inject.inject("s16x1", untouchable(), [], -1))
    # the order of the checks on one record: fields, pulse, overlap, past the end.
    # In a stream of 80 frames a second record at 40 both overlaps the first and runs past the end.
    refused("RECORD_FIELD", lambda: inject.schedule([rec(10), rec(40, den=0, pulse_id=9)], 80))
    refused("PULSE_UNKNOWN", lambda: inject.schedule([rec(10), rec(40, pulse_id=9)], 80))
    refused("INJECT_OVERLAP", lambda: inject.schedule([rec(10), rec(40)], 80))
    refused("INJECT_PAST_END", lambda: inject.schedule([rec(10), rec(74)], 80))


def test_mod_a_a_sum_outside_the_range_is_refused_by_name_and_never_clipped():
    v = ref.vector("injection.json")["range"]
    lo, hi = C.PROFILES["s16x1"]["sample_min"], C.PROFILES["s16x1"]["sample_max"]
    assert (min(C.PULSES["e0"]), max(C.PULSES["e0"])) == (v["smallest_sample"], v["largest_sample"]) == (-970, 950)
    fits, leaves = v["fits_16_bits"], v["leaves_16_bits"]
    # 33/1 on silence fits 16 bits
    stream, _ = inject.inject("s16x1", silence("s16x1", 100), [rec(7, fits["amplitude_num"], 1)], 100)
    out = [f[0] for f in stream]
    assert (min(out), max(out)) == (fits["smallest_added"], fits["largest_added"]) == (-32010, 31350)
    # 34/1 does not: the run is refused at the frame of e0's sample 28, and nothing was clipped on the way
    assert leaves["smallest_added"] == -32980 < lo
    # -34 * -970 = 32980, past the top; and at 40/1 it is e0's sample 27, -878 * 40 = -35120, that leaves first
    for num, at in ((34, 28), (-34, 28), (40, 27)):
        stream, _ = inject.inject("s16x1", silence("s16x1", 100), [rec(7, num, 1)], 100)
        got = []
        e = refused("INJECT_RANGE", lambda: got.extend(stream))
        assert len(got) == 7 + at and "frame %d" % (7 + at) in e.detail
        assert all(lo <= f[0] <= hi for f in got)
        assert [f[0] for f in got[7:]] == [p * num for p in C.PULSES["e0"][:at]], "what came before is exact"
    # the same amplitude fits the wider profile
    stream, _ = inject.inject("s24x3", silence("s24x3", 100), [rec(7, 34, 1)], 100)
    assert min(min(f) for f in stream) == -32980


@pytest.mark.parametrize("name", PROFILES)
def test_mod_a_the_range_is_exact_at_both_ends_and_in_each_channel(name):
    p = C.PROFILES[name]
    channels = p["channels"]
    for channel in range(channels):
        for edge, sign in ((p["sample_max"], 1), (p["sample_min"], -1)):
            # e0[1] = 1: amplitude sign/1 adds sign at index + 1. One channel sits one short of the edge.
            near = [0] * channels
            near[channel] = edge - sign
            frames = [(0,) * channels] * 4 + [tuple(near)] + [(0,) * channels] * 70
            stream, _ = inject.inject(name, frames, [rec(3, sign, 1)], len(frames))
            out = list(stream)
            assert out[4][channel] == edge and len(out) == len(frames), "exactly the edge is the right answer"
            # at the edge already, the same injection leaves the range
            near[channel] = edge
            frames[4] = tuple(near)
            stream, _ = inject.inject(name, frames, [rec(3, sign, 1)], len(frames))
            got = []
            refused("INJECT_RANGE", lambda: got.extend(stream))
            assert len(got) == 4


def test_mod_a_a_stream_not_of_its_declared_length_is_refused_by_name():
    name = "s24x3"
    for bad in (-1, True, 1.0, None, "70"):
        refused("STREAM_LENGTH", lambda: inject.inject(name, silence(name, 70), [], bad))
        refused("STREAM_LENGTH", lambda: inject.schedule([], bad))
    stream, _ = inject.inject(name, silence(name, 70), [rec(2)], 70)
    assert len(list(stream)) == 70
    for actual in (69, 0):                                     # short: refused at its end
        stream, _ = inject.inject(name, silence(name, actual), [rec(2)], 70)
        got = []
        e = refused("STREAM_LENGTH", lambda: got.extend(stream))
        assert len(got) == actual and "ended after %d" % actual in e.detail
    stream, _ = inject.inject(name, silence(name, 71), [rec(2)], 70)   # long: refused at frame 70
    got = []
    refused("STREAM_LENGTH", lambda: got.extend(stream))
    assert len(got) == 70
    stream, _ = inject.inject(name, [], [], 0)
    assert list(stream) == []


def test_mod_a_a_bad_input_frame_is_refused_by_the_names_p0_declared():
    name = "s24x3"
    hi = C.PROFILES[name]["sample_max"]
    for bad, why in (((0, 0), "CHANNELS"), ((0, 0, 0, 0), "CHANNELS"), ([0, 0, 0], "CHANNELS"),
                     ((0, hi + 1, 0), "SAMPLE_RANGE"), ((0, 0, True), "SAMPLE_RANGE"), ((0, 1.0, 0), "SAMPLE_RANGE")):
        frames = silence(name, 10) + [bad] + silence(name, 60)
        stream, _ = inject.inject(name, frames, [rec(2)], 71)
        got = []
        refused(why, lambda: got.extend(stream))
        assert len(got) == 10


# ---------------------------------------------------------------- the truth, and truth isolation (MOD-A's side)

def test_mod_a_the_truth_is_a_copy_of_the_schedule_and_nothing_reaches_back():
    name = "s16x1"
    mine = [dict(r) for r in SCHEDULE]
    stream, truth = inject.inject(name, iter(noise_frames(name)), mine, FRAMES)
    assert isinstance(truth, tuple) and list(truth) == SCHEDULE and all(t is not m for t, m in zip(truth, mine))
    # changing the caller's records, or the truth handed back, after the call changes nothing in the stream
    mine[0]["amplitude_num"] = 99
    truth[1]["amplitude_num"] = 99
    out = list(stream)
    assert injection_findings(name, noise_frames(name), out, SCHEDULE) == []
    assert inject.schedule(iter(SCHEDULE), FRAMES) == tuple(SCHEDULE), "any iterable of records"


class Tagged(tuple):
    """A frame that tries to carry something besides its samples."""
    label = "an injection is here"


@pytest.mark.parametrize("name", PROFILES)
def test_mod_a_the_stream_carries_nothing_but_samples(name):
    channels = C.PROFILES[name]["channels"]
    tagged = [Tagged(f) for f in noise_frames(name)]
    stream, _truth = inject.inject(name, iter(tagged), SCHEDULE, FRAMES)
    assert not isinstance(stream, (list, tuple)) and not hasattr(stream, "truth")
    out = list(stream)
    assert len(out) == FRAMES
    for frame in out:
        assert type(frame) is tuple and len(frame) == channels and all(type(v) is int for v in frame)
    assert injection_findings(name, noise_frames(name), out, SCHEDULE) == []


@pytest.mark.parametrize("name", PROFILES)
def test_mod_a_schedules_that_add_the_same_samples_give_the_same_stream_whatever_their_truth_says(name):
    # Four schedules. They add the same samples; their truth records differ in bytes.
    a = [rec(100, 1, 2), rec(300, 1, 1), rec(500, -3, 2)]
    b = [rec(100, 2, 4), rec(300, 1000001, 1000000), rec(500, -6, 4)]
    c = a + [rec(700, 0, 1)]                # one more record, of amplitude zero
    d = a + [rec(900, 1, 5000)]             # one more record, too faint to add anything
    streams, truths = [], []
    for schedule in (a, b, c, d):
        stream, truth = inject.inject(name, iter(noise_frames(name)), schedule, FRAMES)
        streams.append(source.stream_bytes(name, stream))
        truths.append(b"".join(records.pack("truth", r) for r in truth))
    assert streams[0] == streams[1] == streams[2] == streams[3]
    assert len(set(truths)) == 4, "four different truths"
    # and the comparison is not of nothing: the stream is not its input, by exactly schedule a
    assert streams[0] != source.stream_bytes(name, noise_frames(name))
    stream, truth = inject.inject(name, iter(noise_frames(name)), a, FRAMES)
    assert injection_findings(name, noise_frames(name), list(stream), truth) == []
    # a schedule that adds different samples gives a different stream
    stream, _ = inject.inject(name, iter(noise_frames(name)), [rec(100, 1, 2), rec(300, 1, 1), rec(500, -3, 4)], FRAMES)
    assert source.stream_bytes(name, stream) != streams[0]

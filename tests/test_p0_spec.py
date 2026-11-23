"""P0's own tests: the generated constants, the stream interface, the refusal type.

Each test states the answer it expects. Expected ranges come from
vectors/p0/sample_range.json, which was worked by hand, not from the code
under test.
"""
import json
import os

import pytest

from spec import constants as C
from model import stream
from model.refusal import Refusal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def hand_worked():
    with open(os.path.join(ROOT, "vectors", "p0", "sample_range.json"), encoding="utf-8") as f:
        return {c["bits"]: (c["min"], c["max"]) for c in json.load(f)["cases"]}


def test_p0_every_profile_range_equals_the_hand_worked_range():
    worked = hand_worked()
    assert len(C.PROFILES) >= 2, "one profile cannot show that nothing is hard-wired"
    for name, p in C.PROFILES.items():
        assert p["sample_bits"] in worked, "no hand-worked case for %s" % name
        assert (p["sample_min"], p["sample_max"]) == worked[p["sample_bits"]]


def test_p0_profiles_are_two_different_formats():
    formats = {(p["sample_bits"], p["channels"]) for p in C.PROFILES.values()}
    assert len(formats) >= 2


def test_p0_coefficient_range_equals_the_hand_worked_range():
    assert (C.COEFF_MIN, C.COEFF_MAX) == hand_worked()[C.COEFF_BITS]


@pytest.mark.parametrize("name", sorted(C.PROFILES))
def test_p0_frame_at_each_extreme_is_accepted(name):
    p = stream.profile(name)
    for v in (p["sample_min"], p["sample_max"], 0):
        frame = (v,) * p["channels"]
        assert stream.check_frame(p, frame) == frame


@pytest.mark.parametrize("name", sorted(C.PROFILES))
def test_p0_frame_one_past_each_extreme_is_refused_by_name(name):
    p = stream.profile(name)
    for v in (p["sample_min"] - 1, p["sample_max"] + 1):
        with pytest.raises(Refusal) as e:
            stream.check_frame(p, (v,) * p["channels"])
        assert e.value.name == "SAMPLE_RANGE"


@pytest.mark.parametrize("name", sorted(C.PROFILES))
def test_p0_frame_with_the_wrong_channel_count_is_refused_by_name(name):
    p = stream.profile(name)
    for frame in ((0,) * (p["channels"] + 1), (0,) * (p["channels"] - 1), [0] * p["channels"]):
        with pytest.raises(Refusal) as e:
            stream.check_frame(p, frame)
        assert e.value.name == "CHANNELS"


def test_p0_a_bool_or_a_float_sample_is_refused():
    p = stream.profile("e0")
    for bad in (True, 1.0):
        with pytest.raises(Refusal) as e:
            stream.check_frame(p, (bad,))
        assert e.value.name == "SAMPLE_RANGE"


def test_p0_unknown_profile_is_refused_by_name():
    with pytest.raises(Refusal) as e:
        stream.profile("no-such-profile")
    assert e.value.name == "PROFILE_UNKNOWN"


def test_p0_a_refusal_cannot_carry_an_undeclared_name():
    with pytest.raises(ValueError):
        Refusal("NOT_DECLARED_ANYWHERE")
    assert Refusal("SAMPLE_RANGE").name == "SAMPLE_RANGE"


def test_p0_reserved_mask_is_exactly_the_undeclared_flag_bits():
    used = 0
    for bit in C.FLAGS.values():
        used |= 1 << bit
    flags_bits = dict((f[0], f[1]) for f in C.RECORDS["score"])["flags"]
    assert flags_bits == 8
    assert used == 0b11, "two flags are declared: settling and overflow"
    assert C.FLAGS_RESERVED_MASK == 0xFC
    assert C.FLAGS_RESERVED_MASK & used == 0
    assert C.FLAGS_RESERVED_MASK | used == 0xFF


def test_p0_reference_pulse_fits_the_narrowest_profile_and_is_not_silent():
    pulse = C.PULSES["e0"]
    narrowest = min(p["sample_max"] for p in C.PROFILES.values())
    assert len(pulse) == 64
    assert max(abs(v) for v in pulse) <= narrowest
    assert 900 <= max(abs(v) for v in pulse) <= 1000, "the pulse was made with a peak near 1000"
    assert pulse[0] == 0 and pulse[-1] == 0, "a Hann window is zero at both ends"
    assert sum(v * v for v in pulse) > 0

"""P0's own tests: the generated constants, the stream interface, the refusal type.

Each test states the answer it expects. Expected ranges come from
vectors/p0/sample_range.json, worked by hand, and the design's figures from
vectors/p0/d0_values.json, copied by hand from D0; neither comes from the
code under test.
"""
import json
import os

import pytest

from spec import constants as C
from model import stream
from model.refusal import Refusal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def vector(name):
    with open(os.path.join(ROOT, "vectors", "p0", name), encoding="utf-8") as f:
        return json.load(f)


def hand_worked():
    return {c["bits"]: (c["min"], c["max"]) for c in vector("sample_range.json")["cases"]}


def test_p0_every_profile_range_equals_the_hand_worked_range():
    worked = hand_worked()
    assert len(C.PROFILES) >= 2, "one profile cannot show that nothing is hard-wired"
    for name, p in C.PROFILES.items():
        assert p["sample_bits"] in worked, "no hand-worked case for %s" % name
        assert (p["sample_min"], p["sample_max"]) == worked[p["sample_bits"]]


def test_p0_profiles_are_two_different_formats():
    formats = {(p["sample_bits"], p["channels"]) for p in C.PROFILES.values()}
    assert len(formats) >= 2
    assert max(p["channels"] for p in C.PROFILES.values()) >= 2, "no profile has more than one channel"


def test_p0_the_definition_holds_the_designs_figures():
    d0 = vector("d0_values.json")["rows"]
    assert C.COEFF_BITS == d0["D2"]["coeff_bits"] == 18
    assert (C.MAX_FILTERS, C.MAX_TAPS) == (d0["D3"]["filters"], d0["D3"]["taps"]) == (16, 128)
    assert (C.COEFF_MIN, C.COEFF_MAX) == hand_worked()[18]
    as_proposed = [p for p in C.PROFILES.values()
                   if (p["sample_bits"], p["channels"]) == (d0["D1"]["sample_bits"], d0["D1"]["channels"])]
    assert len(as_proposed) == 1, "exactly one profile is D0 row D1 as proposed"


P0_REFUSALS = ("PROFILE_UNKNOWN", "CHANNELS", "SAMPLE_RANGE", "SHAPE_FILTERS", "SHAPE_TAPS",
               "RESERVED_BITS", "BLOB_HASH", "SWAP_PENDING", "RECORD_KIND", "RECORD_FIELD")
# As asked for in each parcel's design, in the round ledger, and typed here from those lists.
MOD_B_REFUSALS = ("SHAPE_CHANNEL", "SHAPE_ROWS", "SHAPE_RECTIFIER", "SHAPE_POOL", "SHAPE_SHIFT",
                  "WEIGHT_COUNT", "WEIGHT_RANGE", "BLOB_FORMAT", "SWAP_SHAPE", "SWAP_INDEX", "SWAP_EPOCH",
                  "SCORER_THRESHOLD", "SCORER_WINDOW", "SCORER_BINS", "RECORD_ORDER", "QUANTISE_INPUT")
MOD_A_REFUSALS = ("SEED_RANGE", "NOISE_SIGMA", "NOISE_RANGE", "STREAM_LENGTH", "PULSE_UNKNOWN",
                  "INJECT_OVERLAP", "INJECT_PAST_END", "INJECT_RANGE", "REPLAY_FORMAT", "REPLAY_PROFILE",
                  "REPLAY_HASH")
# Round 2, parcel HEAD: the head's hidden layer.
HEAD_REFUSALS = ("SHAPE_HIDDEN", "SHAPE_HIDDEN_SHIFT", "SHAPE_BETWEEN")
# Round 2, parcels RTL-B and RTL-A: the fabric's alone. The model raises none of the three.
FABRIC_REFUSALS = ("CORE_STOPPED", "REGISTER_ACCESS", "INJECT_PENDING")


def test_p0_refusal_names_are_exactly_the_models_forty_and_the_fabrics_three():
    assert (len(P0_REFUSALS), len(MOD_B_REFUSALS), len(MOD_A_REFUSALS), len(HEAD_REFUSALS)) == (10, 16, 11, 3)
    assert C.REFUSALS == P0_REFUSALS + MOD_B_REFUSALS + MOD_A_REFUSALS + HEAD_REFUSALS + FABRIC_REFUSALS
    assert len(set(C.REFUSALS)) == 43 and len(FABRIC_REFUSALS) == 3


def test_p0_the_hidden_layers_bounds_are_the_ones_generated_and_keep_the_head_small():
    """Round 2's plan fixed "simple enough" before the hidden layer was designed. Its third part is a
    count: at the maxima the whole head, as multipliers, is at most a tenth of the filter bank. Each
    hidden unit takes one multiplier for each filter and one more on its way out."""
    assert (C.MAX_HIDDEN, C.MAX_HIDDEN_SHIFT) == (12, 31)
    assert (C.MAX_FILTERS + 1) * C.MAX_HIDDEN * 10 <= C.MAX_FILTERS * C.MAX_TAPS       # 2,040 <= 2,048
    assert (C.MAX_FILTERS + 1) * (C.MAX_HIDDEN + 1) * 10 > C.MAX_FILTERS * C.MAX_TAPS  # thirteen would not pass
    # Every old head has its setting of the new one only if the hidden shift reaches as far as the score's.
    assert C.MAX_HIDDEN_SHIFT >= C.MAX_SCORE_SHIFT


def test_p0_the_bounds_the_lead_decided_on_2026_11_23_are_the_ones_generated():
    """These four are not D0's figures. They are the values MOD-B's width argument is worked at;
    a change to one is a change to that argument, so it is pinned here to be made on purpose."""
    assert (C.MAX_ROWS, C.MAX_POOL, C.MAX_SCORE_SHIFT, C.MAX_HIST_BINS) == (16, 65536, 31, 4096)
    assert C.MAX_POOL == 2 ** 16 and C.MAX_SCORE_SHIFT == 2 ** 5 - 1


def test_p0_rectifier_codes_are_the_two_declared_and_fit_a_byte():
    assert C.RECTIFIERS == {"pass": 0, "abs": 1}
    assert len(set(C.RECTIFIERS.values())) == len(C.RECTIFIERS)
    assert all(type(v) is int and 0 <= v <= 255 for v in C.RECTIFIERS.values())


def test_p0_an_injected_sample_is_rounded_by_the_rule_the_coefficients_are():
    assert C.INJECT_ROUNDING == "half_to_even" == C.QUANTISE_ROUNDING


def test_p0_every_pulse_has_one_id_that_fits_the_truth_records_field():
    assert C.PULSE_IDS == {"e0": 0}
    assert set(C.PULSE_IDS) == set(C.PULSES)
    assert len(set(C.PULSE_IDS.values())) == len(C.PULSE_IDS)
    width = dict((f[0], (f[1], f[2])) for f in C.RECORDS["truth"])["pulse_id"]
    assert width == (16, "unsigned")
    assert all(type(v) is int and 0 <= v <= 65535 for v in C.PULSE_IDS.values())


@pytest.mark.parametrize("name", sorted(C.PROFILES))
def test_p0_frame_at_each_extreme_is_accepted(name):
    p = stream.profile(name)
    for v in (p["sample_min"], p["sample_max"], 0):
        frame = (v,) * p["channels"]
        assert stream.check_frame(p, frame) == frame


@pytest.mark.parametrize("name", sorted(C.PROFILES))
def test_p0_one_sample_one_past_either_extreme_in_any_channel_is_refused_by_name(name):
    p = stream.profile(name)
    tried = 0
    for bad in (p["sample_min"] - 1, p["sample_max"] + 1):
        for channel in range(p["channels"]):
            frame = [0] * p["channels"]
            frame[channel] = bad
            with pytest.raises(Refusal) as e:
                stream.check_frame(p, tuple(frame))
            assert e.value.name == "SAMPLE_RANGE"
            tried += 1
    assert tried == 2 * p["channels"]


@pytest.mark.parametrize("name", sorted(C.PROFILES))
def test_p0_frame_with_the_wrong_channel_count_is_refused_by_name(name):
    p = stream.profile(name)
    for frame in ((0,) * (p["channels"] + 1), (0,) * (p["channels"] - 1), [0] * p["channels"]):
        with pytest.raises(Refusal) as e:
            stream.check_frame(p, frame)
        assert e.value.name == "CHANNELS"


class _TaggedFrame(tuple):
    """A tuple that carries something besides its samples."""
    label = "more than samples"


class _TaggedSample(int):
    label = "more than a sample"


@pytest.mark.parametrize("name", sorted(C.PROFILES))
def test_p0_a_frame_is_exactly_a_tuple_and_a_sample_exactly_an_int(name):
    """An object of a subclass can carry more than its samples, so neither is taken: a subclass of
    tuple is not a frame (CHANNELS), and a subclass of int is not a sample (SAMPLE_RANGE).
    Parcel MOD-A found, on 2026-11-23, that the first of these was let through."""
    p = stream.profile(name)
    plain = (0,) * p["channels"]
    assert _TaggedFrame(plain) == plain, "equal as tuples, which is why equality is not the test"
    with pytest.raises(Refusal) as e:
        stream.check_frame(p, _TaggedFrame(plain))
    assert e.value.name == "CHANNELS"
    with pytest.raises(Refusal) as e:
        stream.check_frame(p, (_TaggedSample(0),) * p["channels"])
    assert e.value.name == "SAMPLE_RANGE"
    assert stream.check_frame(p, plain) is plain


def test_p0_a_bool_or_a_float_sample_is_refused():
    p = stream.profile("s16x1")
    for bad in (True, 1.0):
        with pytest.raises(Refusal) as e:
            stream.check_frame(p, (bad,))
        assert e.value.name == "SAMPLE_RANGE"


@pytest.mark.parametrize("bad", ["no-such-profile", "", None, 16, [], {}, ("s16x1",)])
def test_p0_anything_but_a_declared_profile_name_is_refused_by_name(bad):
    with pytest.raises(Refusal) as e:
        stream.profile(bad)
    assert e.value.name == "PROFILE_UNKNOWN"


def test_p0_a_profile_is_a_copy_and_changing_it_changes_nothing_shared():
    p = stream.profile("s16x1")
    p["channels"] = 9
    assert C.PROFILES["s16x1"]["channels"] == 1
    assert stream.profile("s16x1")["channels"] == 1


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
    assert narrowest == 32767
    assert len(pulse) == 64
    assert max(abs(v) for v in pulse) <= narrowest
    assert 900 <= max(abs(v) for v in pulse) <= 1000, "the pulse was made with a peak near 1000"
    assert pulse[0] == 0 and pulse[-1] == 0, "a Hann window is zero at both ends"
    assert sum(v * v for v in pulse) > 0


def test_p0_every_refusal_has_a_code_of_its_own_that_fits_a_byte_and_none_is_zero():
    assert set(C.REFUSAL_CODES) == set(C.REFUSALS) and len(C.REFUSAL_CODES) == 43
    assert len(set(C.REFUSAL_CODES.values())) == 43
    assert all(type(v) is int and 1 <= v <= 255 for v in C.REFUSAL_CODES.values())
    # Typed here from the definition as it was first written, so that a renumbering is made on purpose.
    assert (C.REFUSAL_CODES["PROFILE_UNKNOWN"], C.REFUSAL_CODES["BLOB_HASH"], C.REFUSAL_CODES["SHAPE_BETWEEN"]) == (1, 7, 40)
    # The fabric's three, typed from the lead's ruling of 2026-11-23 on the two RTL designs.
    assert [C.REFUSAL_CODES[n] for n in FABRIC_REFUSALS] == [41, 42, 43]


def test_p0_the_registers_lie_inside_the_frame_in_whole_words_and_do_not_overlap():
    assert C.BUS == {"word_bits": 32, "address_bits": 12, "first_offset": 16,
                     "magic": int.from_bytes(b"UNDT", "big")}
    taken = set()
    for name, (offset, access, words) in C.REGISTERS.items():
        assert offset % 4 == 0 and offset >= C.BUS["first_offset"], name
        assert offset + 4 * words <= 2 ** C.BUS["address_bits"] and access in ("ro", "rw", "wo"), name
        span = set(range(offset, offset + 4 * words))
        assert not span & taken, name
        taken |= span
    # The block P0 wrote down: identity and capabilities, read-only, below the control block's 0x80.
    assert C.REGISTERS["id"] == (0x10, "ro", 1) and C.REGISTERS["spec_hash"] == (0x18, "ro", 8)
    assert C.REGISTERS["cap_sample_bits"][0] == 0x18 + 4 * 8          # the hash's eight words, then this
    below = [(offset, access, words) for offset, access, words in C.REGISTERS.values() if offset < 0x80]
    assert len(below) == 15 and all(access == "ro" and offset + 4 * words <= 0x80 for offset, access, words in below)
    assert 8 * 32 == 256                                                 # the hash is a SHA-256


def test_p0_the_register_map_is_three_blocks_and_every_register_is_inside_one():
    """Round 2: the core's control block from 0x080, and the source's and the injector's from 0xF00.
    The figures are typed here from the two designs and the lead's ruling on them, not read from the definition."""
    assert C.BLOCKS == {"core": (0x010, 0xF00), "source": (0xF00, 0xF80), "inject": (0xF80, 0x1000)}
    counts = dict.fromkeys(C.BLOCKS, 0)
    for name, (offset, _access, words) in C.REGISTERS.items():
        inside = [b for b, (first, end) in C.BLOCKS.items() if first <= offset and offset + 4 * words <= end]
        assert len(inside) == 1, name
        counts[inside[0]] += 1
    assert counts == {"core": 15 + 22, "source": 7, "inject": 8} and len(C.REGISTERS) == 52
    # The control block as parcel RTL-B's design counted it: 22 registers in 39 words, 0x080 to 0x11B.
    control = [(offset, words) for offset, _access, words in C.REGISTERS.values() if 0x080 <= offset < 0xF00]
    assert (len(control), sum(w for _o, w in control), min(o for o, _w in control)) == (22, 39, 0x080)
    assert max(o + 4 * w for o, w in control) == 0x11C
    assert C.REGISTERS["shape_masks"][2] == C.MAX_FILTERS            # one word of channel mask a filter
    assert C.REGISTERS["commit_at"] == (0x0F8, "rw", 2) and C.REGISTERS["next_index"] == (0x10C, "ro", 2)
    # One refusal register a block, each read and written.
    assert [C.REGISTERS[n][1] for n in ("refusal", "src_refusal", "inj_refusal")] == ["rw", "rw", "rw"]
    assert C.REGISTERS["src_seed"] == (0xF00, "wo", 2) and C.REGISTERS["cap_inject_pending"] == (0xFA4, "ro", 1)


def test_p0_the_registers_that_are_read_as_bits_and_the_fabrics_two_bounds():
    assert C.REGISTER_BITS == {
        "status": {"running": 0, "loading": 1, "commit": 2, "settling": 3, "closed": 4, "partial": 5, "whole": 6,
                   "overflow": 7, "refused": 8, "refused_again": 9},
        "src_status": {"running": 0}}
    for register in C.REGISTER_BITS:
        assert C.REGISTERS[register][1] == "ro" and C.REGISTERS[register][2] == 1
    assert (C.MAX_NOISE_TABLE, C.MAX_INJECT_PENDING) == (32767, 1024)
    # Under the narrowest profile the fabric's table bound is the largest sample, so it takes what the model takes.
    assert C.MAX_NOISE_TABLE == min(p["sample_max"] for p in C.PROFILES.values())
    assert C.PULSE_SAMPLE_BITS == min(p["sample_bits"] for p in C.PROFILES.values()) == 16

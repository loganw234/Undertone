"""MOD-A's tests of model/source.py: the words, the noise, recordings, and the replay gate.

Expected answers come from three places, none of them the model: the published known answers
in vectors/mod-a/words.json; hand-worked bytes in vectors/mod-a/recording.json; and the second
implementation in tests/test_mod_a_reference.py, which imports nothing of model/ and wrote
vectors/mod-a/noise.json and table.json. The tail of the noise has its own file,
tests/test_mod_a_tails.py.
"""
import ast
import fractions
import hashlib
import os

import numpy as np
import pytest

from spec import constants as C
from model import inject, records, source
from model.refusal import Refusal

import test_mod_a_reference as ref

ROOT = ref.ROOT
PROFILES = sorted(C.PROFILES)


def refused(name, call):
    with pytest.raises(Refusal) as e:
        call()
    assert e.value.name == name, "refused as %s, expected %s" % (e.value.name, name)


# ---------------------------------------------------------------- the words

def test_mod_a_words_equal_the_published_known_answers():
    v = ref.vector("words.json")
    assert [source.word(v["first_words"]["seed"], i) for i in range(5)] == v["first_words"]["words"]
    bins = [0] * 5
    for i in range(v["counts"]["draws"]):
        bins[(source.word(v["counts"]["seed"], i) * 5) >> 64] += 1
    assert bins == v["counts"]["counts"] == [20027, 19892, 20073, 19978, 20030]


@pytest.mark.parametrize("seed,start", [(0, 0), (1, 0), (20261123, 0), (2 ** 64 - 1, 0), (1234567, 2 ** 40),
                                         (987654321, 2 ** 64 - 1000)])
def test_mod_a_words_equal_the_second_implementation(seed, start):
    want = ref.ref_words(seed, start, 1000).tolist()
    assert [source.word(seed, start + k) for k in range(1000)] == want
    assert len(set(want)) == 1000, "no word twice in a thousand"


def test_mod_a_each_word_comes_from_exactly_one_index():
    # The mix can be undone (the reference undoes it with its own code), and the step is odd,
    # so two indexes never give one word: each 64-bit word occurs once in the 2^64 indexes.
    assert source.GAMMA & 1 == 1
    for seed, i in ((0, 0), (1234567, 77), (2 ** 64 - 1, 2 ** 64 - 1), (20261124, 2 ** 33)):
        assert ref.ref_unmix(source.word(seed, i)) == (seed + source.GAMMA * (i + 1)) % 2 ** 64
    # the last index is a word like any other, and one past it is refused
    assert source.word(5, 2 ** 64 - 1) == int(ref.ref_words(5, 2 ** 64 - 1, 1)[0])


@pytest.mark.parametrize("bad", [-1, 2 ** 64, True, 1.0, "1", None])
def test_mod_a_a_seed_or_an_index_out_of_range_is_refused_by_name(bad):
    refused("SEED_RANGE", lambda: source.word(bad, 0))
    refused("STREAM_LENGTH", lambda: source.word(0, bad))
    refused("SEED_RANGE", lambda: source.Noise("s16x1", bad, 100, 1, 4))
    for good in (0, 2 ** 64 - 1):
        assert 0 <= source.word(good, good) < 2 ** 64
        assert source.Noise("s16x1", good, 100, 1, 4).frames == 4


# ---------------------------------------------------------------- the table and the noise

def test_mod_a_a_table_entry_rounds_to_the_nearest_integer_and_a_tie_goes_up():
    # By hand: 1/2 -> 1, 3/2 -> 2, 5/2 -> 3 (ties, upward); 1/3 -> 0, 2/3 -> 1, 7/4 -> 2, 5/4 -> 1; 0/9 -> 0; 6/3 -> 2.
    # No table the tests build has an exact tie, so this is the only thing that holds the direction.
    hand = {(1, 2): 1, (3, 2): 2, (5, 2): 3, (1, 3): 0, (2, 3): 1, (7, 4): 2, (5, 4): 1, (0, 9): 0, (6, 3): 2}
    for (num, den), want in hand.items():
        assert source._nearest(num, den) == want, (num, den)
    assert source._nearest(2 ** 200 + 1, 2) == 2 ** 199 + 1


def test_mod_a_small_tables_equal_the_frozen_ones():
    tables = ref.vector("table.json")["tables"]
    assert [(t["sigma_num"], t["sigma_den"]) for t in tables] == [(1, 1), (2, 1), (3, 2)]
    for t in tables:
        assert list(source.gaussian_table(t["sigma_num"], t["sigma_den"])) == t["table"]
        assert t["table"][-1] == 2 ** 63 and t["table"].count(2 ** 63) == 1
    # the frozen file is what the reference gives today
    assert ref.table_vector()["tables"] == tables
    assert len(tables[0]["table"]) - 1 == 9 and len(tables[1]["table"]) - 1 == 18, "largest magnitudes 9 and 18"


@pytest.mark.parametrize("sn,sd,within", [(1, 1, 3e-7), (3, 2, 1e-12), (2, 1, 1e-12), (100, 1, 1e-12),
                                           (1000, 1, 1e-12)])
def test_mod_a_the_tables_exact_variance_is_sigma_squared(sn, sd, within):
    num, den = source.table_variance(source.gaussian_table(sn, sd))
    assert type(num) is int and den == 2 ** 63
    sigma2 = fractions.Fraction(sn * sn, sd * sd)
    assert abs(fractions.Fraction(num, den) / sigma2 - 1) < within
    # and it is the variance of the law the reference computes in decimal, to what 63 bits can hold
    weights, total = ref.ref_law(sn, sd)
    law = 2 * sum(m * m * w for m, w in enumerate(weights)) / total
    assert abs(float(fractions.Fraction(num, den)) / float(law) - 1) < 1e-12
    if (sn, sd) == (1, 1):
        # 2.2e-7 below sigma^2 at sigma = 1: the law itself, not the table
        assert 2.0e-7 < float(1 - fractions.Fraction(num, den) / sigma2) < 2.3e-7
    # by hand, a table of three magnitudes: P(0) = 1/2, P(1) = 1/4, P(2) = 1/4 gives 0 + 1/4 + 4/4 = 5/4
    assert source.table_variance((2 ** 62, 2 ** 62 + 2 ** 61, 2 ** 63)) == (5 * 2 ** 61, 2 ** 63)


@pytest.mark.parametrize("name,seed,sn,sd", [("s16x1", 20261123, 1000, 1), ("s16x1", 0, 3, 2), ("s16x1", 7, 1, 1),
                                              ("s24x3", 2 ** 64 - 1, 37, 10), ("s24x3", 99, 100, 1),
                                              ("s24x3", 3, 1, 1)])
def test_mod_a_noise_equals_the_second_implementation(name, seed, sn, sd):
    want = [tuple(f) for f in ref.ref_noise(name, seed, sn, sd, 0, 2048).tolist()]
    noise = source.Noise(name, seed, sn, sd, 2048)
    got = list(noise)
    assert got == want
    assert all(type(f) is tuple and len(f) == C.PROFILES[name]["channels"] and all(type(v) is int for v in f)
               for f in got)
    if C.PROFILES[name]["channels"] > 1:
        assert sum(1 for f in got if len(set(f)) > 1) > 1500, "a frame's channels are different draws"


@pytest.mark.parametrize("name", PROFILES)
def test_mod_a_noise_equals_the_frozen_vector(name):
    run = [r for r in ref.vector("noise.json")["runs"] if r["profile"] == name]
    assert len(run) == 1
    run = run[0]
    assert (run["seed"], (run["sigma_num"], run["sigma_den"])) == (ref.GATE_RUNS[name]["seed"],
                                                                 ref.GATE_RUNS[name]["sigma"])
    noise = source.Noise(name, run["seed"], run["sigma_num"], run["sigma_den"], 4096)
    frames = list(noise)
    assert [list(f) for f in frames[:8]] == run["first_frames"]
    # the digest is of the reference's own packing of the frames, not the model's
    assert hashlib.sha256(ref.ref_bytes(name, frames)).hexdigest() == run["sha256_4096"]
    assert hashlib.sha256(source.stream_bytes(name, frames)).hexdigest() == run["sha256_4096"]


def test_mod_a_the_frozen_noise_vector_is_what_the_reference_gives():
    # Recomputed here for s16x1 only: the s24x3 run's table takes the reference about two seconds.
    frozen = [r for r in ref.vector("noise.json")["runs"] if r["profile"] == "s16x1"][0]
    run = ref.GATE_RUNS["s16x1"]
    frames = ref.ref_noise("s16x1", run["seed"], run["sigma"][0], run["sigma"][1], 0, 4096).tolist()
    assert frames[:8] == frozen["first_frames"]
    assert hashlib.sha256(ref.ref_bytes("s16x1", frames)).hexdigest() == frozen["sha256_4096"]


@pytest.mark.parametrize("name", PROFILES)
def test_mod_a_noise_is_the_same_each_time_and_from_any_frame(name):
    noise = source.Noise(name, 42, 50, 1, 300)
    first = list(noise)
    assert list(noise) == first and len(first) == 300
    assert list(noise.from_frame(123)) == first[123:]
    assert list(noise.from_frame(300)) == []
    # a longer source starts with the shorter one's frames: a frame depends on its number, not on the length
    assert list(source.Noise(name, 42, 50, 1, 400))[:300] == first
    refused("STREAM_LENGTH", lambda: list(noise.from_frame(301)))
    refused("STREAM_LENGTH", lambda: list(noise.from_frame(-1)))


@pytest.mark.parametrize("name", PROFILES)
def test_mod_a_noise_has_the_stated_mean_variance_and_no_correlation(name):
    # 2^16 frames. Each statistic must lie within 4 of its own standard deviations (the round's z).
    n, (sn, sd) = 1 << 16, ref.GATE_RUNS[name]["sigma"]
    sigma = sn / sd
    a = np.array(list(source.Noise(name, 1, sn, sd, n)), dtype=np.float64)
    channels = a.shape[1]
    for c in range(channels):
        x = a[:, c]
        assert abs(x.mean()) <= 4 * sigma / np.sqrt(n), "mean of channel %d" % c
        assert abs((x * x).mean() / sigma ** 2 - 1) <= 4 * np.sqrt(2 / n), "variance of channel %d" % c
        assert abs((x[1:] * x[:-1]).mean() / sigma ** 2) <= 4 / np.sqrt(n), "lag-1 correlation of channel %d" % c
        for d in range(c + 1, channels):
            assert abs((x * a[:, d]).mean() / sigma ** 2) <= 4 / np.sqrt(n), "channels %d and %d" % (c, d)
            # the next frame's other channel too: an index that slid by one channel would show here
            assert abs((x[1:] * a[:-1, d]).mean() / sigma ** 2) <= 4 / np.sqrt(n)
            assert abs((x[:-1] * a[1:, d]).mean() / sigma ** 2) <= 4 / np.sqrt(n)


def test_mod_a_seeds_are_places_on_one_cycle_as_the_doc_says():
    # A stated limit, shown: the seed s + k * GAMMA gives the seed s's words k places on.
    g = source.GAMMA
    for seed in (0, 20261123, 2 ** 64 - 1):
        moved = (seed + 3 * g) % 2 ** 64
        assert [source.word(moved, i) for i in range(50)] == [source.word(seed, i + 3) for i in range(50)]
    a = list(source.Noise("s16x1", 5, 100, 1, 200))
    b = list(source.Noise("s16x1", (5 + 7 * g) % 2 ** 64, 100, 1, 200))
    assert b[:193] == a[7:] and b != a


def test_mod_a_one_seed_at_two_sigmas_is_one_sequence_through_two_tables_as_the_doc_says():
    # A stated limit, shown: the same signs, and the same order of magnitudes, sample by sample.
    small = [f[0] for f in source.Noise("s16x1", 9, 100, 1, 3000)]
    large = [f[0] for f in source.Noise("s16x1", 9, 1000, 1, 3000)]
    assert all((x > 0) == (y > 0) and y != 0 for x, y in zip(small, large) if x != 0)
    ranked = sorted((abs(x), abs(y)) for x, y in zip(small, large))
    assert all(y1 <= y2 for (x1, y1), (x2, y2) in zip(ranked, ranked[1:]) if x1 < x2)
    assert len({x for x, _ in ranked}) > 200, "many magnitudes, so the order is a real constraint"
    # with another seed there is no such tie
    other = [f[0] for f in source.Noise("s16x1", 10, 1000, 1, 3000)]
    assert sum(1 for x, y in zip(small, other) if x * y > 0) < 1700


def test_mod_a_a_sigma_that_is_not_a_ratio_of_ints_at_least_one_is_refused_by_name():
    for sn, sd in ((0, 1), (1, 2), (99, 100), (-5, 1), (5, -1), (5, 0), (1.5, 1), (3, 2.0), (True, 1), ("3", 1),
                   (None, 1)):
        refused("NOISE_SIGMA", lambda: source.gaussian_table(sn, sd))
        refused("NOISE_SIGMA", lambda: source.Noise("s24x3", 0, sn, sd, 1))
    for sn, sd in ((1, 1), (2, 2), (3, 2), (101, 100)):
        assert source.gaussian_table(sn, sd)[-1] == 2 ** 63
    assert source.gaussian_table(2, 2) == source.gaussian_table(1, 1), "the ratio is what matters"


def test_mod_a_a_sigma_whose_tail_does_not_fit_the_profile_is_refused_by_name():
    # The largest magnitude is 32767 at sigma = 3579 and 32776 at 3580 (the reference's table, in floats:
    # the two-sided tail first rounds to nothing there). s16x1 holds 32767.
    assert len(source.Noise("s16x1", 0, 3579, 1, 1).table) - 1 == 32767 == C.PROFILES["s16x1"]["sample_max"]
    refused("NOISE_RANGE", lambda: source.Noise("s16x1", 0, 3580, 1, 1))
    # the edge itself: at sigma = 3579.07 the last magnitude is still 32767, and at 3579.08 it is 32768,
    # one past the range, which must be refused and not let through as a sample the profile cannot hold
    assert len(source.Noise("s16x1", 0, 357907, 100, 1).table) - 1 == 32767
    assert len(source.gaussian_table(357908, 100)) - 1 == 32768
    refused("NOISE_RANGE", lambda: source.Noise("s16x1", 0, 357908, 100, 1))
    refused("NOISE_RANGE", lambda: source.Noise("s16x1", 0, 5000, 1, 1))
    refused("NOISE_RANGE", lambda: source.Noise("s16x1", 0, 10 ** 30, 1, 1))     # refused without being built
    assert len(source.Noise("s24x3", 0, 5000, 1, 1).table) - 1 == 45776
    refused("NOISE_RANGE", lambda: source.Noise("s24x3", 0, 10 ** 30, 1, 1))
    refused("NOISE_RANGE", lambda: source.gaussian_table(100, 1, 915))
    # with no bound given, the bound is the largest sample any declared profile holds: nothing larger is built
    refused("NOISE_RANGE", lambda: source.gaussian_table(10 ** 30, 1))
    assert max(p["sample_max"] for p in C.PROFILES.values()) == 8388607
    refused("NOISE_RANGE", lambda: source.gaussian_table(8388608, 8))        # 8 sigma is one past it
    assert len(source.gaussian_table(100, 1, 916)) - 1 == 916


@pytest.mark.parametrize("sn,sd", [(1, 1), (101, 100), (3, 2), (2, 1), (7, 3), (10, 1), (37, 1), (38, 1), (39, 1),
                                    (100, 1), (1000, 1), (3579, 1)])
def test_mod_a_the_table_always_runs_past_eight_sigma(sn, sd):
    # gaussian_table refuses a sigma above an eighth of the range without building its table.
    # That is only right if every table runs past 8 sigma.
    assert (len(source.gaussian_table(sn, sd)) - 1) * sd > 8 * sn


def test_mod_a_a_frame_count_the_generator_cannot_hold_is_refused_by_name():
    for bad in (-1, 1.0, True, None, "4", 2 ** 64 + 1):
        refused("STREAM_LENGTH", lambda: source.Noise("s16x1", 0, 100, 1, bad))
    assert source.Noise("s16x1", 0, 100, 1, 2 ** 64).frames == 2 ** 64      # every word, once
    assert source.Noise("s16x1", 0, 100, 1, 0).frames == 0 and list(source.Noise("s16x1", 0, 100, 1, 0)) == []
    # three channels use three words a frame
    assert source.Noise("s24x3", 0, 100, 1, 2 ** 64 // 3).frames == 2 ** 64 // 3
    refused("STREAM_LENGTH", lambda: source.Noise("s24x3", 0, 100, 1, 2 ** 64 // 3 + 1))


def test_mod_a_noise_checks_in_its_stated_order():
    refused("PROFILE_UNKNOWN", lambda: source.Noise("no-such", -1, 0, 0, -1))
    refused("SEED_RANGE", lambda: source.Noise("s16x1", -1, 0, 0, -1))
    refused("NOISE_SIGMA", lambda: source.Noise("s16x1", 0, 0, 0, -1))
    refused("STREAM_LENGTH", lambda: source.Noise("s16x1", 0, 5000, 1, -1))
    refused("NOISE_RANGE", lambda: source.Noise("s16x1", 0, 5000, 1, 1))


# ---------------------------------------------------------------- bytes and recordings

def hand_recordings():
    out = []
    for case in ref.vector("recording.json")["cases"]:
        payload = bytes.fromhex(case["payload"])
        data = bytes.fromhex(case["header_before_hash"]) + hashlib.sha256(payload).digest() + payload
        out.append((case["profile"], [tuple(f) for f in case["frames"]], payload, data))
    return out


def test_mod_a_stream_bytes_and_recordings_equal_the_hand_worked_bytes():
    seen = set()
    for name, frames, payload, data in hand_recordings():
        assert source.stream_bytes(name, frames) == payload
        assert source.recording(name, frames) == data
        assert len(data) == 56 + len(payload) == source.HEADER_BYTES + len(payload)
        assert source.parse_recording(name, data) == tuple(frames)
        seen.add(name)
    assert seen == set(C.PROFILES), "a hand-worked recording for every profile"


@pytest.mark.parametrize("name", PROFILES)
def test_mod_a_stream_bytes_equal_the_second_implementation_at_the_extremes(name):
    p = C.PROFILES[name]
    run = ref.GATE_RUNS[name]
    frames = list(source.Noise(name, 9, run["sigma"][0], run["sigma"][1], 500))
    frames += [(p["sample_min"],) * p["channels"], (p["sample_max"],) * p["channels"], (-1,) * p["channels"]]
    assert source.stream_bytes(name, frames) == ref.ref_bytes(name, frames)
    assert source.recording(name, frames) == ref.ref_recording(name, frames)
    assert source.stream_bytes(name, []) == b""
    for bad, why in (((p["sample_max"] + 1,) * p["channels"], "SAMPLE_RANGE"), ((0,) * (p["channels"] + 1), "CHANNELS")):
        refused(why, lambda: source.stream_bytes(name, frames + [bad]))
        refused(why, lambda: source.recording(name, [bad]))


@pytest.mark.parametrize("name", PROFILES)
def test_mod_a_a_recording_written_and_read_back_is_its_stream(name, tmp_path):
    run = ref.GATE_RUNS[name]
    noise = source.Noise(name, 5, run["sigma"][0], run["sigma"][1], 257)
    path = str(tmp_path / "noise.undt")
    assert source.record(name, noise, path) == 257
    with open(path, "rb") as f:
        assert f.read() == ref.ref_recording(name, list(noise))
    replay = source.Replay(name, path)
    assert replay.frames == 257
    assert list(replay) == list(noise) == list(replay), "the same every time it is iterated"
    assert all(type(f) is tuple and all(type(v) is int for v in f) for f in replay)
    empty = str(tmp_path / "empty.undt")
    assert source.record(name, [], empty) == 0
    assert source.Replay(name, empty).frames == 0 and list(source.Replay(name, empty)) == []


def test_mod_a_every_flipped_bit_of_a_recording_is_refused_and_by_the_right_name():
    for name, frames, payload, data in hand_recordings():
        names = {}
        for bit in range(len(data) * 8):
            flipped = bytearray(data)
            flipped[bit // 8] ^= 1 << (bit % 8)
            with pytest.raises(Refusal) as e:
                source.parse_recording(name, bytes(flipped))
            names[bit // 8] = names.get(bit // 8, set()) | {e.value.name}
        # byte by byte, in the header's order: magic 0-7, version 8-9, bits 10-11, channels 12-13,
        # reserved 14-15, frames 16-23, hash 24-55, then the payload
        for byte in range(0, 10):
            assert names[byte] == {"REPLAY_FORMAT"}, byte
        for byte in range(10, 14):
            assert names[byte] == {"REPLAY_PROFILE"}, byte
        for byte in range(14, 16):
            assert names[byte] == {"RESERVED_BITS"}, byte
        for byte in range(16, 24):
            assert names[byte] == {"REPLAY_FORMAT"}, byte
        for byte in range(24, len(data)):
            assert names[byte] == {"REPLAY_HASH"}, byte
        assert len(names) == len(data) and len(data) > 56


def test_mod_a_a_recording_that_is_not_one_is_refused_by_name():
    name, frames, payload, data = hand_recordings()[0]
    other = [n for n in C.PROFILES if n != name][0]
    for bad in (b"", data[:55], data[:56 + len(payload) - 1], data + bytes([0]), b"UNDTSTRX" + data[8:],
                data[:8] + bytes([2, 0]) + data[10:], "text", None, 7, [1, 2]):
        refused("REPLAY_FORMAT", lambda: source.parse_recording(name, bad))
    refused("REPLAY_PROFILE", lambda: source.parse_recording(other, data))
    refused("PROFILE_UNKNOWN", lambda: source.parse_recording("no-such", data))
    assert source.parse_recording(name, bytearray(data)) == tuple(frames)
    # a header that is all there is: zero frames, and it must say so
    assert source.parse_recording(name, source.recording(name, [])) == ()
    # the order: a wrong reserved field is named before a wrong profile, a wrong profile before a wrong length
    both = bytearray(data)
    both[14] ^= 1
    both[10] ^= 1
    refused("RESERVED_BITS", lambda: source.parse_recording(name, bytes(both)))
    both[14] ^= 1
    refused("REPLAY_PROFILE", lambda: source.parse_recording(name, bytes(both) + bytes([0])))
    # and the first bytes and the version come before everything: a wrong version with a wrong reserved field
    first = bytearray(data)
    first[8] ^= 2
    first[14] ^= 1
    refused("REPLAY_FORMAT", lambda: source.parse_recording(name, bytes(first)))
    # a payload of the wrong length is named before its hash, which is wrong too
    refused("REPLAY_FORMAT", lambda: source.parse_recording(name, data[:-1]))


def test_mod_a_a_profile_whose_bits_are_not_whole_bytes_keeps_its_own_range(monkeypatch):
    # Neither declared profile has such a width, but the definition allows one (2 to 32 bits), so a
    # 12-bit, two-channel profile is declared here, for this test only. Nothing in the tree changes.
    monkeypatch.setitem(C.PROFILES, "s12x2", {"sample_bits": 12, "channels": 2, "sample_min": -2048,
                                              "sample_max": 2047})
    frames = [(-2048, 2047), (1, -1), (258, -259)]
    # By hand, two bytes a sample (12 bits rounded up to whole bytes): -2048 = 0xF800 -> 00 f8;
    # 2047 = 0x07FF -> ff 07; 1 -> 01 00; -1 -> ff ff; 258 = 0x0102 -> 02 01; -259 = 0xFEFD -> fd fe.
    assert source.stream_bytes("s12x2", frames).hex() == "00f8ff070100ffff0201fdfe"
    data = source.recording("s12x2", frames)
    assert len(data) == 56 + 12 and source.parse_recording("s12x2", data) == tuple(frames)
    # A recording whose bytes hold a sample 12 bits cannot: 2048 = 00 08. Its header and its hash are right,
    # so the only thing wrong with it is the sample.
    payload = bytes.fromhex("00f8ff07" + "0008" + "ffff")
    bad = data[:16] + (2).to_bytes(8, "little") + hashlib.sha256(payload).digest() + payload
    refused("SAMPLE_RANGE", lambda: source.parse_recording("s12x2", bad))
    # the hash is checked before the samples: the same bytes under a wrong hash are named for the hash
    wrong_hash = bad[:24] + bytes([bad[24] ^ 1]) + bad[25:]
    refused("REPLAY_HASH", lambda: source.parse_recording("s12x2", wrong_hash))
    for sample in (2048, -2049):
        refused("SAMPLE_RANGE", lambda: source.stream_bytes("s12x2", [(0, sample)]))
    # and the noise is held to that range: the table's last magnitude is 2042 at sigma = 223 and 2051 at 224
    assert len(source.Noise("s12x2", 0, 223, 1, 0).table) - 1 == 2042
    refused("NOISE_RANGE", lambda: source.Noise("s12x2", 0, 224, 1, 0))


def test_mod_a_a_recording_refused_hands_out_no_frame(tmp_path):
    name, frames, payload, data = hand_recordings()[0]
    path = str(tmp_path / "bad.undt")
    with open(path, "wb") as f:
        f.write(data[:-1] + bytes([data[-1] ^ 0x80]))
    refused("REPLAY_HASH", lambda: source.Replay(name, path))
    with pytest.raises(OSError):
        source.Replay(name, str(tmp_path / "not-there.undt"))


# ---------------------------------------------------------------- the replay gate

REPLAY_FRAMES = 600
# Small tables, so that building a source twice, or sixty-five times, costs little.
REPLAY_SIGMA = {"s16x1": (300, 1), "s24x3": (700, 1)}
REPLAY_SCHEDULE = [{"index": 3, "pulse_id": 0, "amplitude_num": 3, "amplitude_den": 2},
                   {"index": 200, "pulse_id": 0, "amplitude_num": -7, "amplitude_den": 4},
                   {"index": 536, "pulse_id": 0, "amplitude_num": 5, "amplitude_den": 3}]


def chain(name, seed, noise_class=source.Noise, schedule=None, frames=REPLAY_FRAMES):
    """One run, built from nothing: a source, an injector, and the bytes of what they give."""
    sn, sd = REPLAY_SIGMA[name]
    noise = noise_class(name, seed, sn, sd, frames)
    stream, truth = inject.inject(name, noise, REPLAY_SCHEDULE if schedule is None else schedule, frames)
    return source.stream_bytes(name, stream), b"".join(records.pack("truth", r) for r in truth)


def replay_fault(run_a, run_b):
    """None when two runs are the same bytes, stream and truth; else what differs first."""
    (stream_a, truth_a), (stream_b, truth_b) = run_a, run_b
    if len(stream_a) == 0 and len(stream_b) == 0:
        return "NOTHING-COMPARED: two runs of no frames"
    if stream_a != stream_b:
        if len(stream_a) != len(stream_b):
            return "the streams are %d and %d bytes" % (len(stream_a), len(stream_b))
        return "the streams differ first at byte %d" % next(i for i in range(len(stream_a))
                                                             if stream_a[i] != stream_b[i])
    if truth_a != truth_b:
        return "the truth records differ"
    return None


@pytest.mark.parametrize("name", PROFILES)
def test_gate_replay__two_runs_built_apart_from_one_seed_are_the_same_bytes(name):
    seed = ref.GATE_RUNS[name]["seed"]
    first, second = chain(name, seed), chain(name, seed)
    assert replay_fault(first, second) is None
    assert first[0] is not second[0], "two runs, not one compared with itself"
    width = (C.PROFILES[name]["sample_bits"] // 8) * C.PROFILES[name]["channels"]
    assert len(first[0]) == REPLAY_FRAMES * width and len(first[1]) == 18 * len(REPLAY_SCHEDULE)
    # and the run is what the second implementation says it is: its noise, plus its injected samples
    sn, sd = REPLAY_SIGMA[name]
    want = ref.ref_noise(name, seed, sn, sd, 0, REPLAY_FRAMES)
    for r in REPLAY_SCHEDULE:
        added = ref.ref_scaled(C.PULSES["e0"], r["amplitude_num"], r["amplitude_den"])
        want[r["index"]:r["index"] + len(added), :] += np.array(added, dtype=np.int64)[:, None]
    assert first[0] == ref.ref_bytes(name, want.tolist())


@pytest.mark.parametrize("name", PROFILES)
def test_gate_replay__a_recording_replays_the_same_bytes(name, tmp_path):
    seed = ref.GATE_RUNS[name]["seed"]
    sn, sd = REPLAY_SIGMA[name]
    path = str(tmp_path / "run.undt")
    source.record(name, source.Noise(name, seed, sn, sd, REPLAY_FRAMES), path)

    def replayed():
        stream, truth = inject.inject(name, source.Replay(name, path), REPLAY_SCHEDULE, REPLAY_FRAMES)
        return source.stream_bytes(name, stream), b"".join(records.pack("truth", r) for r in truth)

    assert replay_fault(replayed(), replayed()) is None
    assert replay_fault(replayed(), chain(name, seed)) is None, "a replayed recording is the run it recorded"


@pytest.mark.parametrize("name", PROFILES)
def test_control_replay__each_single_changed_seed_bit_gives_a_different_run(name):
    seed = ref.GATE_RUNS[name]["seed"]
    short = {"schedule": REPLAY_SCHEDULE[:1], "frames": 128}      # 65 runs: short ones, each with an injection
    base = chain(name, seed, **short)
    assert replay_fault(base, chain(name, seed, **short)) is None
    differing = 0
    for bit in range(64):
        fault = replay_fault(base, chain(name, seed ^ (1 << bit), **short))
        assert fault is not None and fault.startswith("the streams differ"), "seed bit %d changed nothing" % bit
        differing += 1
    assert differing == 64


class LeakyNoise(source.Noise):
    """A broken generator: its builds share a counter, so the second build carries on where the first stopped."""
    drawn = 0

    def words(self, first, count):
        start = LeakyNoise.drawn
        LeakyNoise.drawn += count
        return super().words(start + first, count)


@pytest.mark.parametrize("name", PROFILES)
def test_control_replay__a_generator_that_carries_state_between_builds_is_caught(name):
    seed = ref.GATE_RUNS[name]["seed"]
    LeakyNoise.drawn = 0
    first, second = chain(name, seed, LeakyNoise), chain(name, seed, LeakyNoise)
    assert first == chain(name, seed), "its first build is right, so only a second build can show the fault"
    fault = replay_fault(first, second)
    assert fault is not None and fault.startswith("the streams differ")


@pytest.mark.parametrize("name", PROFILES)
def test_control_replay__a_changed_truth_record_or_nothing_to_compare_is_reported(name):
    seed = ref.GATE_RUNS[name]["seed"]
    base = chain(name, seed)
    # the same samples under another truth: 3/2 written as 6/4
    other = [dict(r) for r in REPLAY_SCHEDULE]
    other[0]["amplitude_num"], other[0]["amplitude_den"] = 6, 4
    assert replay_fault(base, chain(name, seed, schedule=other)) == "the truth records differ"
    # one frame fewer (and so without the injection that ends on the last frame)
    shorter = chain(name, seed, schedule=REPLAY_SCHEDULE[:2], frames=REPLAY_FRAMES - 1)
    assert replay_fault(base, shorter).startswith("the streams are")
    empty = chain(name, seed, schedule=[], frames=0)
    assert replay_fault(empty, empty).startswith("NOTHING-COMPARED")


# ---------------------------------------------------------------- no float, no chance

def test_mod_a_the_two_modules_hold_no_float_and_nothing_unseeded():
    for module in ("source.py", "inject.py"):
        with open(os.path.join(ROOT, "model", module), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
            assert not isinstance(node, ast.Div), "%s has a true division" % module
            assert not (isinstance(node, ast.Constant) and isinstance(node.value, (float, complex))), \
                "%s has a float constant" % module
            assert not (isinstance(node, ast.Name) and node.id in ("float", "round", "hash", "id", "set",
                                                                    "frozenset")), "%s uses %s" % (module, node.id)
        assert imported <= {"bisect", "hashlib", "spec", "model"}, "%s imports %s" % (module, sorted(imported))

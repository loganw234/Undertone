"""The injector's bench: rtl/inject/inject.sv against model/inject.py, on every sample of every frame.

It runs once under each profile: the runner sets UNDERTONE_PROFILE and builds
the injector with that profile's SAMPLE_BITS and CHANNELS.

Every comparison drives frames through `harness.exchange`, loads the schedule
through the register port (source_bus.py), and holds what comes out against
what `model.inject.inject` hands out, through `harness.hold`. Each ends with
the refusal register as one more word, so for each of these comparisons of
frames the count of words in the evidence is one more than the frames compared.

WHOSE EXPECTATION. The frames, and the name of a refusal, are the model's,
with four exceptions that are THIS DESIGN'S and are said where they are used:
  - a run begun at index F by inj_frame is held against the model's run from 0
    with every record's index lowered by F. The model has no such run: the
    mapping is this bench's;
  - a record that starts before the frame the injector has reached is
    INJECT_OVERLAP, the fabric's half of that rule;
  - INJECT_PENDING, which the model never raises: it has no bound on a schedule;
  - REGISTER_ACCESS, the lead's ruling: the model has no bus.

The controls on the model side hand the comparison a wrong model and require
a WORD mismatch at the place this file works out: D0's four (an injector that
adds nothing, one a sample late, one with the sign flipped, one at half
amplitude) and a fifth that rounds a tie upward. The controls on the RTL side
are the mutants in benches.toml.

WHAT THIS BENCH DOES NOT SEE: a schedule, an amplitude or an index it does not
run; a record that ends past the stream's end, which is the host library's to
refuse (INJECT_PAST_END) and which this bench never writes; a second pulse.
"""
import fractions
import itertools
import math
import os
import random

import cocotb
from cocotb.triggers import FallingEdge

from spec import constants as C
from model import inject, source
from model.refusal import Refusal

import harness
import source_bus as bus

PROFILE = os.environ["UNDERTONE_PROFILE"]
PROF = C.PROFILES[PROFILE]
CHANNELS = PROF["channels"]
FRAME_BYTES = (CHANNELS * PROF["sample_bits"] + 7) // 8
E0 = C.PULSE_IDS["e0"]
PULSE = C.PULSES["e0"]
L = len(PULSE)
TRUTH = dict((f[0], f[1]) for f in C.RECORDS["truth"])
PULSE_BITS = min(p["sample_bits"] for p in C.PROFILES.values())
LATENCY = 5 + (PULSE_BITS + TRUTH["amplitude_num"] - 1)     # the design's 52
PENDING = C.MAX_INJECT_PENDING
SIGMA = {"s16x1": (1000, 1), "s24x3": (5000, 1)}[PROFILE]
SEED = 2026112330
PREFIX = b"undertone-rtl-a/inject-frames/"
INDEX_MAX = (1 << TRUTH["index"]) - 1


def rec(index, num=1, den=1, pulse_id=E0):
    return {"index": index, "pulse_id": pulse_id, "amplitude_num": num, "amplitude_den": den}


# The six amplitudes of the model's own test (tests/test_mod_a_inject.py, its SCHEDULE), at closer indexes.
SCHEDULE = [rec(5, 3, 2), rec(100, -7, 4), rec(230, 1, 1), rec(400, 5, 3), rec(520, -2, 1), rec(700, 33, 10)]
SCHEDULE_FRAMES = 800
WIDE_RANDOM = 12

_noise = {}


def noise_frames(count, seed=31):
    """The input stream: seeded noise from the model, a different value in every channel."""
    if (count, seed) not in _noise:
        _noise[(count, seed)] = list(source.Noise(PROFILE, seed, SIGMA[0], SIGMA[1], count))
    return _noise[(count, seed)]


def steady(count):
    """A quiet input that still differs by channel: channel c holds 5 * c - 3."""
    return [tuple(5 * c - 3 for c in range(CHANNELS))] * count


def frame_words(frames):
    return [harness.frame_word(PROFILE, f) for f in frames]


def model_outcome(frames, schedule, first=0, declared=None):
    """(the frames the model hands out, the name it refused by or None).

    A run begun at `first` is the model's run from 0 with every record's index lowered by `first`: this
    bench's mapping. `declared` is the stream's length as the model is told it, for a schedule with
    records past the frames driven; the model's frames are then read no further than the frames driven.
    """
    lowered = [dict(r, index=r["index"] - first) for r in schedule]
    out = []
    try:
        stream, _truth = inject.inject(PROFILE, iter(frames), lowered, len(frames) if declared is None else declared)
        for frame in itertools.islice(stream, len(frames)):
            out.append(frame)
    except Refusal as e:
        return out, e.name
    return out, None


def truth_writes(record):
    """One truth record as the writes that offer it: a field a row, the denominator last.

    A numerator is written as its 32 bits, two's complement. One that does not fit them cannot be written
    at all, so it is refused HERE and not cut to fit: the model refuses such a record (RECORD_FIELD), and a
    bench that wrote its low bits would be comparing two different records.
    """
    top = 1 << (TRUTH["amplitude_num"] - 1)
    assert -top <= record["amplitude_num"] < top, "a numerator of %d does not fit its field" % record["amplitude_num"]
    assert 0 <= record["amplitude_den"] <= bus.WORD_MASK and 0 <= record["pulse_id"] <= bus.WORD_MASK
    assert 0 <= record["index"] <= INDEX_MAX
    return (bus.words_of("inj_truth_index", record["index"])
            + [(bus.offset("inj_truth_pulse_id"), record["pulse_id"]),
               (bus.offset("inj_truth_amplitude_num"), record["amplitude_num"] & bus.WORD_MASK),
               (bus.offset("inj_truth_amplitude_den"), record["amplitude_den"])])


async def begin(dut):
    b = bus.Bus(dut, stream_in=True)
    await b.reset()
    return b


async def load(b, schedule):
    pairs = []
    for record in schedule:
        pairs += truth_writes(record)
    if pairs:
        await b.write_many(pairs)


def driver(dut, frames, expect, gap_seed=0, max_gap=2):
    return harness.exchange(dut, frame_words(frames), expect, out_data="out_frame", gap_seed=gap_seed,
                            max_gap=max_gap, max_latency=LATENCY + 16, settle=LATENCY + 16)


async def hold_stream(b, test, label, seen, unknown, model_frames, refused_as):
    """THE COMPARISON: the frames, then the refusal register against the name the model refused by, or none."""
    code = await b.read(bus.offset("inj_refusal"))
    return harness.hold(test, label, seen + [bus.account(FRAME_BYTES, code)],
                        frame_words(model_frames) + [bus.account(FRAME_BYTES, bus.code_of(refused_as))],
                        width_bytes=FRAME_BYTES + 1, prefix=PREFIX, unknown=unknown)


async def run_case(b, test, label, frames, schedule, *, first=0, declared=None, expected=None, gap_seed=0,
                   max_gap=2, fresh=True):
    """Load a schedule, drive the frames, hold what comes out. Returns (the RTL's digest, the latencies seen,
    the name refused by or None, the model's frames)."""
    if fresh:
        await b.reset()
    if first:
        await b.write_value("inj_frame", first)
    await load(b, schedule)
    model_frames, name = model_outcome(frames, schedule, first, declared) if expected is None else expected
    seen, seen_at, sent_at, unknown = await driver(b.dut, frames, len(model_frames), gap_seed, max_gap)
    _count, _model, rtl = await hold_stream(b, test, label, seen, unknown, model_frames, name)
    return rtl, sorted(set(s - t for s, t in zip(seen_at, sent_at))), name, model_frames


# ---------------------------------------------------------------- the stream

@cocotb.test()
async def stream_is_the_models(dut):
    test = "stream_is_the_models"
    b = await begin(dut)
    frames = noise_frames(SCHEDULE_FRAMES)
    # The first record alone, on the stream's first frames: short, so that a broken injector is caught at once.
    _rtl, _lat, name, out = await run_case(b, test, "the first record alone", frames[:100], SCHEDULE[:1], gap_seed=SEED)
    assert name is None and out != frames[:100]
    for label, max_gap in (("with gaps", 2), ("a frame every clock", 0)):
        _rtl, _lat, name, out = await run_case(b, test, label, frames, SCHEDULE, gap_seed=SEED, max_gap=max_gap)
        assert name is None and len(out) == len(frames), (name, len(out))
        changed = sum(1 for a, c in zip(frames, out) if a != c)
        assert changed > len(SCHEDULE) * (L - 20), "the schedule adds too little to hold anything: %d frames" % changed
    # A RECORD WRITTEN WHILE THE STREAM RUNS, ahead of the frame the injector has reached: it is taken, and
    # added exactly. The model is given the whole schedule before frame 0; the RTL its second record after
    # about a hundred frames have gone by, a frame every clock.
    later = [rec(20, 3, 2), rec(300, -5, 4)]
    short = frames[:400]
    model_frames, refused = model_outcome(short, later)
    assert refused is None and model_frames[300:364] != short[300:364]
    await b.reset()
    await load(b, later[:1])
    task = cocotb.start_soon(driver(b.dut, short, len(short), gap_seed=SEED, max_gap=0))
    for _ in range(100):
        await FallingEdge(b.dut.clk)
    await b.write_many(truth_writes(later[1]))
    seen, _seen_at, _sent_at, unknown = await task
    await hold_stream(b, test, "a record written while the stream runs", seen, unknown, model_frames, None)


def differing_ties(schedule):
    """How many samples of a schedule are ties that half-to-even and half-upward round differently."""
    count = 0
    for r in schedule:
        for p in PULSE:
            quotient, remainder = divmod(p * r["amplitude_num"], r["amplitude_den"])
            if 2 * remainder == r["amplitude_den"] and quotient % 2 == 0:
                count += 1
    return count


TIES = [rec(3, 1, 2), rec(100, -3, 2), rec(200, 1, 1940), rec(300, 3, 1940), rec(400, 7, 6)]


@cocotb.test()
async def ties_go_to_the_even(dut):
    test = "ties_go_to_the_even"
    b = await begin(dut)
    assert PULSE[1] == 1 and divmod(PULSE[1] * 1, 2) == (0, 1)      # e0's second sample at 1/2: a tie, the floor even
    assert differing_ties(TIES) > 20, differing_ties(TIES)
    assert differing_ties(TIES[:1]) == 15, differing_ties(TIES[:1])     # e0 at 1/2: fifteen ties whose floor is even
    _rtl, _lat, name, _out = await run_case(b, test, "e0 at 1/2 alone", steady(80), TIES[:1], gap_seed=SEED + 1)
    assert name is None, name
    for label, frames in (("on a quiet stream", steady(480)), ("on noise", noise_frames(480, seed=32))):
        _rtl, _lat, name, _out = await run_case(b, test, label, frames, TIES, gap_seed=SEED + 1)
        assert name is None, name


@cocotb.test()
async def records_that_touch_and_the_ends(dut):
    test = "records_that_touch_and_the_ends"
    b = await begin(dut)
    schedule = [rec(0, 2, 1), rec(L, -3, 1), rec(2 * L, 5, 7), rec(300 - L, 9, 4)]     # the last ends on the last frame
    frames = noise_frames(300, seed=33)
    for label, max_gap in (("a frame every clock", 0), ("with gaps", 2)):
        _rtl, _lat, name, _out = await run_case(b, test, label, frames, schedule, gap_seed=SEED + 2, max_gap=max_gap)
        assert name is None, name


@cocotb.test()
async def a_run_begun_far_out(dut):
    """The index's upper bits. The mapping of a run begun at F is this bench's (the file's docstring)."""
    test = "a_run_begun_far_out"
    b = await begin(dut)
    frames = noise_frames(300, seed=34)
    for first in ((1 << 32) - 100, (1 << 63) - 100, INDEX_MAX - 299):
        schedule = [rec(first + 36, 3, 2), rec(first + 100, -5, 3), rec(first + 200, 7, 4)]
        _rtl, _lat, name, _out = await run_case(b, test, "begun at %d" % first, frames, schedule, first=first,
                                                gap_seed=SEED + 3, max_gap=1)
        assert name is None, name
    # And from 0: a record far out does not fire early, at any of the index's upper bits.
    for bit in (8, 16, 31, 32, 47, 63):
        far = (1 << bit) + 40
        schedule = [rec(10, 3, 2), rec(far, 5, 1)]
        _rtl, _lat, name, _out = await run_case(b, test, "a record at 2^%d + 40" % bit, frames[:110], schedule,
                                                declared=far + L, gap_seed=SEED + 4, max_gap=1)
        assert name is None, name


@cocotb.test()
async def wide_amplitudes(dut):
    """Numerators and denominators across their 32 bits. The model says which are refused, and where."""
    test = "wide_amplitudes"
    b = await begin(dut)
    rng = random.Random(SEED + 5)
    num_top, den_top = 1 << (TRUTH["amplitude_num"] - 1), (1 << TRUTH["amplitude_den"]) - 1
    pairs = [(-num_top, 1), (num_top - 1, den_top), (-num_top, den_top), (1, den_top), (num_top - 1, num_top),
             (-1, 2), (3, den_top - 1), (num_top - 1, 1)]
    for _ in range(WIDE_RANDOM):
        num = rng.getrandbits(rng.randint(1, TRUTH["amplitude_num"] - 1)) * rng.choice((1, -1))
        den = max(1, rng.getrandbits(rng.randint(1, TRUTH["amplitude_den"])))
        pairs.append((num, den))
    frames = noise_frames(80, seed=35)
    taken = refused = 0
    for n, (num, den) in enumerate(pairs):
        _rtl, _lat, name, out = await run_case(b, test, "%d / %d" % (num, den), frames, [rec(8, num, den)],
                                               gap_seed=SEED + n, max_gap=1)
        assert name in (None, "INJECT_RANGE"), name
        if name is None and out != frames:
            taken += 1
        if name is not None:
            refused += 1
    assert taken >= 3 and refused >= 3, (taken, refused)        # both kinds are among the cases, under either profile


@cocotb.test()
async def other_truth_same_samples(dut):
    """Truth isolation at the injector's output: other truth records that add the same samples give the same stream."""
    test = "other_truth_same_samples"
    b = await begin(dut)
    frames = noise_frames(330, seed=36)
    schedules = [[rec(5, 3, 2)],
                 [rec(5, 6, 4)],
                 [rec(5, 3000, 2000), rec(150, 0, 1), rec(250, 1, 5000)],
                 [rec(5, 3 << 20, 1 << 21), rec(100, 1, 5000)]]
    digests, streams = set(), []
    for n, schedule in enumerate(schedules):
        rtl, _lat, name, out = await run_case(b, test, "truth %d" % n, frames, schedule, gap_seed=SEED + 6, max_gap=1)
        assert name is None
        digests.add(rtl)
        streams.append(out)
    assert all(s == streams[0] for s in streams) and streams[0] != frames, "the model's streams are not one stream"
    assert len(digests) == 1, digests


@cocotb.test()
async def latency_is_fifty_two_clocks(dut):
    """The design's number, for a frame with a pulse on it and for one without: truth is not in the timing."""
    assert LATENCY == 52, LATENCY
    b = await begin(dut)
    frames = noise_frames(260, seed=37)
    for max_gap in (0, 2):
        _rtl, latencies, name, _out = await run_case(b, "latency_is_fifty_two_clocks", "gaps to %d" % max_gap, frames,
                                                     [rec(20, 3, 2), rec(84, -1, 3)], gap_seed=SEED + 7, max_gap=max_gap)
        assert name is None and latencies == [52], latencies


# ---------------------------------------------------------------- the refusals

async def refused_at_the_write(b, test, label, schedule, want, frames=None):
    """A schedule the model refuses before any frame: no frame comes out, and the register names it."""
    frames = steady(40) if frames is None else frames
    _rtl, _lat, name, out = await run_case(b, test, label, frames, schedule)
    assert name == want and out == [], (name, len(out))


@cocotb.test()
async def refusal_record_field(dut):
    test = "refusal_record_field"
    b = await begin(dut)
    await refused_at_the_write(b, test, "a denominator of 0", [rec(5, 1, 0)], "RECORD_FIELD")
    await refused_at_the_write(b, test, "a pulse_id word of 2^16", [rec(5, 1, 1, pulse_id=1 << TRUTH["pulse_id"])],
                               "RECORD_FIELD")
    await refused_at_the_write(b, test, "a pulse_id word of every bit set", [rec(5, 1, 1, pulse_id=bus.WORD_MASK)],
                               "RECORD_FIELD")
    await refused_at_the_write(b, test, "an unknown pulse and a denominator of 0: the field first",
                               [rec(5, 1, 0, pulse_id=1)], "RECORD_FIELD")
    await refused_at_the_write(b, test, "a good record, then a denominator of 0", [rec(5, 3, 2), rec(200, 1, 0)],
                               "RECORD_FIELD", frames=steady(300))
    # The other side: the smallest and the largest denominator are taken, the largest under the largest numerator.
    for num, den in ((7, 1), ((1 << (TRUTH["amplitude_num"] - 1)) - 1, (1 << TRUTH["amplitude_den"]) - 1)):
        _rtl, _lat, name, out = await run_case(b, test, "%d over a denominator of %d" % (num, den), steady(100),
                                               [rec(5, num, den)])
        assert name is None and out != steady(100)


@cocotb.test()
async def refusal_pulse_unknown(dut):
    test = "refusal_pulse_unknown"
    b = await begin(dut)
    assert sorted(C.PULSE_IDS.values()) == [E0], "this bench knows one pulse"
    await refused_at_the_write(b, test, "pulse_id 1", [rec(5, 1, 1, pulse_id=E0 + 1)], "PULSE_UNKNOWN")
    await refused_at_the_write(b, test, "the largest pulse_id", [rec(5, 1, 1, pulse_id=(1 << TRUTH["pulse_id"]) - 1)],
                               "PULSE_UNKNOWN")
    await refused_at_the_write(b, test, "an unknown pulse that also overlaps: the pulse first",
                               [rec(100, 1, 1), rec(50, 1, 1, pulse_id=E0 + 1)], "PULSE_UNKNOWN", frames=steady(300))
    _rtl, _lat, name, out = await run_case(b, test, "the declared pulse", steady(100), [rec(5, 4, 1)])
    assert name is None and out != steady(100)


@cocotb.test()
async def refusal_inject_overlap(dut):
    test = "refusal_inject_overlap"
    b = await begin(dut)
    await refused_at_the_write(b, test, "one sample shared", [rec(100, 1, 1), rec(100 + L - 1, 1, 1)], "INJECT_OVERLAP",
                               frames=steady(300))
    await refused_at_the_write(b, test, "out of order", [rec(100, 1, 1), rec(20, 1, 1)], "INJECT_OVERLAP",
                               frames=steady(300))
    await refused_at_the_write(b, test, "the same index twice", [rec(100, 1, 1), rec(100, 2, 1)], "INJECT_OVERLAP",
                               frames=steady(300))
    _rtl, _lat, name, out = await run_case(b, test, "two records that touch", steady(300), [rec(100, 1, 1), rec(100 + L, 2, 1)])
    assert name is None and out != steady(300)
    # The fabric's half: a record before the frame the injector has reached. The expectation is this design's.
    first = 1000
    await run_case(b, test, "a record one frame before the run's first", steady(40), [rec(first - 1, 1, 1)], first=first,
                   expected=([], "INJECT_OVERLAP"))
    _rtl, _lat, name, out = await run_case(b, test, "a record at the run's first frame", steady(100), [rec(first, 3, 1)],
                                           first=first)
    assert name is None and out != steady(100)
    # And while a stream runs: a record whose frame has gone ends the run. The record is behind the frame the
    # injector has reached and NOT behind the record before it, which ended at 84: only the fabric's half of
    # the rule refuses it. No model has this case, so the register is asserted and THE FRAMES COLLECTED ARE
    # COMPARED WITH NOTHING: that a frame taken after the refused write is not offered is not held here.
    await b.reset()
    await load(b, [rec(20, 1, 1)])
    task = cocotb.start_soon(driver(b.dut, steady(300), 0, max_gap=0))
    for _ in range(160):
        await FallingEdge(b.dut.clk)
    assert await b.read(bus.offset("inj_refusal")) == 0
    await b.write_many(truth_writes(rec(100, 1, 1)))        # past the first record's end, behind the frame reached
    await task
    code = await b.read(bus.offset("inj_refusal"))
    assert code == C.REFUSAL_CODES["INJECT_OVERLAP"], code


@cocotb.test()
async def refusal_inject_pending(dut):
    """The expectation is this design's: the model has no bound on a schedule."""
    test = "refusal_inject_pending"
    b = await begin(dut)
    assert await b.read(bus.offset("cap_inject_pending")) == PENDING
    far = 1000000
    full = [rec(8, 3, 2), rec(100, -1, 1)] + [rec(far + L * k, 1, 1) for k in range(PENDING - 2)]
    assert len(full) == PENDING
    # One record more than the store holds.
    await run_case(b, test, "one record more than the store holds", steady(40), full + [rec(far + L * PENDING, 1, 1)],
                   expected=([], "INJECT_PENDING"))
    # The other side: exactly as many as it holds, and the stream is the model's.
    frames = noise_frames(200, seed=38)
    _rtl, _lat, name, out = await run_case(b, test, "as many as the store holds", frames, full, declared=far + L * PENDING)
    assert name is None and out != frames
    assert await b.read(bus.offset("inj_pending")) == PENDING - 2      # two have had their last sample added
    # inj_frame EMPTIES THE STORE: with 1,022 records still held, a new run begins with none, and is the model's.
    first = 5000
    _rtl, _lat, name, out = await run_case(b, test, "a new run begun on a full store", steady(100), [rec(first + 9, 4, 3)],
                                           first=first, fresh=False)
    assert name is None and out != steady(100)
    assert await b.read(bus.offset("inj_pending")) == 0


def widest_amplitude(frames, index, sign):
    """The whole amplitude of the largest magnitude, of this sign, that the model adds to these frames at this
    index without refusing."""
    low, high = 1, PROF["sample_max"] + 1000
    assert model_outcome(frames, [rec(index, sign * low, 1)])[1] is None
    assert model_outcome(frames, [rec(index, sign * high, 1)])[1] == "INJECT_RANGE"
    while high - low > 1:
        mid = (low + high) // 2
        if model_outcome(frames, [rec(index, sign * mid, 1)])[1] is None:
            low = mid
        else:
            high = mid
    return low


@cocotb.test()
async def refusal_inject_range(dut):
    test = "refusal_inject_range"
    b = await begin(dut)
    for label, frames in (("a quiet stream", steady(120)), ("noise", noise_frames(120, seed=39))):
        for sign in (1, -1):
            widest = widest_amplitude(frames, 10, sign)
            _rtl, _lat, name, out = await run_case(b, test, "%s, %d/1: the widest that fits" % (label, sign * widest),
                                                   frames, [rec(10, sign * widest, 1)])
            assert name is None and len(out) == len(frames)
            _rtl, _lat, name, out = await run_case(b, test, "%s, %d/1: one more" % (label, sign * (widest + 1)),
                                                   frames, [rec(10, sign * (widest + 1), 1)])
            assert name == "INJECT_RANGE" and 10 < len(out) < 10 + L, (name, len(out))
    # Far past the range.
    _rtl, _lat, name, out = await run_case(b, test, "far past the range", steady(120), [rec(10, -(1 << 31), 1)])
    assert name == "INJECT_RANGE" and len(out) == 11, (name, len(out))     # e0's first sample is 0, its second is not
    # THE RANGE'S TWO ENDS, EXACTLY. A sum equal to the largest sample, or to the smallest, is taken; one past
    # either is refused, at the frame of the pulse's largest or smallest sample. The last channel carries the
    # value at the edge, the others stay quiet. (Without these four cases a build that refused a sum equal
    # to either end passed every test here: two one-place changes tried in a copy showed it.)
    for end, edge, peak, step in (("the largest sample", PROF["sample_max"], max(PULSE), 1),
                                  ("the smallest sample", PROF["sample_min"], min(PULSE), -1)):
        for past in (0, step):
            frame = tuple(5 * c - 3 for c in range(CHANNELS - 1)) + (edge - peak + past,)
            frames = [frame] * 120
            label = "a sum %s %s" % ("equal to" if past == 0 else "one past", end)
            _rtl, _lat, name, out = await run_case(b, test, label, frames, [rec(10, 1, 1)])
            if past == 0:
                assert name is None and len(out) == len(frames), (label, name, len(out))
                assert edge in [f[-1] for f in out], "the sum never reaches %s" % end
            else:
                assert name == "INJECT_RANGE" and len(out) == 10 + PULSE.index(peak), (label, name, len(out))


@cocotb.test()
async def refusal_register_access(dut):
    """The expected codes here are the lead's ruling, not the model's: the model has no bus."""
    test = "refusal_register_access"
    name = "REGISTER_ACCESS"
    b = await begin(dut)
    hole = bus.offset("cap_inject_pending") + bus.WORD_BYTES
    rows = set()
    for first, _access, count in C.REGISTERS.values():
        rows |= set(first + bus.WORD_BYTES * i for i in range(count))
    assert hole not in rows and hole > bus.offset("inj_frame")

    async def code_is(label, want):
        await hold_stream(b, test, label, [], None, [], want)

    for label, at, word in (("a read-only row", bus.offset("inj_pending"), 0),
                            ("the capability row", bus.offset("cap_inject_pending"), 1),
                            ("an offset that holds no row", hole, 0),
                            ("the block's last word", (1 << C.BUS["address_bits"]) - bus.WORD_BYTES, 0),
                            ("an offset that is not a word's", bus.offset("inj_truth_index") + 1, 0),
                            ("anything but 0 into the refusal register", bus.offset("inj_refusal"), 7)):
        await b.reset()
        await b.write(at, word)
        await code_is(label, name)
    await b.write(bus.offset("inj_refusal"), 0)
    await code_is("a write of 0 clears it", None)

    # Writes that are not its own, and reads: nothing is refused.
    await b.reset()
    await b.write(bus.offset("src_seed"), 5)                # the source's block
    await b.write(C.REGISTERS["id"][0], 5)                  # the core's block
    assert await b.read(hole) == 0
    assert await b.read(bus.offset("inj_truth_amplitude_den")) == 0     # a truth row reads 0: nothing reads truth back
    assert await b.read(bus.offset("src_refusal")) == 0     # not this block's: it answers 0
    await code_is("writes not its own, and reads", None)

    # A refused write during a stream: the run goes on untouched.
    await b.reset()
    schedule = [rec(10, 3, 2), rec(120, -5, 4)]
    frames = noise_frames(220, seed=40)
    model_frames, refused = model_outcome(frames, schedule)
    assert refused is None
    await load(b, schedule)
    task = cocotb.start_soon(driver(b.dut, frames, len(frames), gap_seed=SEED + 8))
    for _ in range(50):
        await FallingEdge(b.dut.clk)
    codes = []
    await b.write(bus.offset("inj_pending"), 0)             # read-only: refused
    codes.append(await b.read(bus.offset("inj_refusal")))
    await b.write(bus.offset("inj_refusal"), 0)             # a write of 0 clears, while the stream runs too
    codes.append(await b.read(bus.offset("inj_refusal")))
    await b.write(bus.offset("inj_refusal"), 3)             # anything but 0: refused, in every state
    seen, _seen_at, _sent_at, unknown = await task
    assert codes == [bus.code_of(name), 0], codes
    await hold_stream(b, test, "refused writes during a stream", seen, unknown, model_frames, name)

    # A record offered after the run has ended, once the register is cleared; and inj_frame begins another run.
    await b.reset()
    await load(b, [rec(5, 1, 0)])                           # RECORD_FIELD: the run is over
    await b.write(bus.offset("inj_refusal"), 0)
    await b.write_many(truth_writes(rec(50, 1, 1)))
    await code_is("a record offered after the run has ended", name)
    seen, _seen_at, _sent_at, unknown = await driver(b.dut, steady(30), 0)
    await hold_stream(b, test, "and no frame is offered", seen, unknown, [], name)
    _rtl, _lat, refused, out = await run_case(b, test, "inj_frame begins another run", steady(150), [rec(2020, 2, 1)],
                                              first=2000, fresh=False)
    assert refused is None and out != steady(150)


# ---------------------------------------------------------------- the controls, on the model side

def tie_upward(frames, schedule):
    """An injector whose arithmetic is right but for a tie, which it rounds upward. Worked with fractions."""
    add = {}
    for r in schedule:
        for j, p in enumerate(PULSE):
            add[r["index"] + j] = math.floor(fractions.Fraction(p * r["amplitude_num"], r["amplitude_den"])
                                             + fractions.Fraction(1, 2))
    return [tuple(v + add.get(n, 0) for v in f) for n, f in enumerate(frames)]


@cocotb.test()
async def control_model_five_wrong_injectors(dut):
    """D0's four and the fifth, on the model side: each wrong model must be reported at the first frame it changes."""
    test = "control_model_five_wrong_injectors"
    b = await begin(dut)
    frames = noise_frames(SCHEDULE_FRAMES)
    await b.reset()
    await load(b, SCHEDULE)
    right, refused = model_outcome(frames, SCHEDULE)
    assert refused is None
    seen, _seen_at, _sent_at, unknown = await driver(b.dut, frames, len(frames), gap_seed=SEED + 9)
    await hold_stream(b, test, "the right model", seen, unknown, right, None)
    wrong_models = (
        ("adds nothing", list(frames), 6),
        ("a sample late", model_outcome(frames, [dict(r, index=r["index"] + 1) for r in SCHEDULE])[0], 6),
        ("the sign flipped", model_outcome(frames, [dict(r, amplitude_num=-r["amplitude_num"]) for r in SCHEDULE])[0], 6),
        ("half the amplitude", model_outcome(frames, [dict(r, amplitude_den=2 * r["amplitude_den"]) for r in SCHEDULE])[0], 6),
        ("a tie upward", tie_upward(frames, SCHEDULE), 7),
    )
    for label, wrong, where in wrong_models:
        assert len(wrong) == len(right)
        differs = [i for i in range(len(right)) if wrong[i] != right[i]]
        # The first record is index 5 at 3/2: e0[1] * 3/2 is 1.5, which is 2, at frame 6; e0[2] * 3/2 is 10.5, a tie, at 7.
        assert differs and differs[0] == where, (label, differs[:3])
        try:
            await hold_stream(b, test, label, seen, unknown, wrong, None)
        except harness.Mismatch as e:
            assert e.kind == "WORD" and e.at == where, str(e)
            continue
        raise AssertionError("the comparison was handed a wrong model (%s) and reported nothing" % label)


@cocotb.test()
async def control_model_refusals(dut):
    """A model that accepts a refused case, and one that names it wrongly, must each be reported."""
    test = "control_model_refusals"
    b = await begin(dut)
    frames = steady(120)
    widest = widest_amplitude(frames, 10, 1)
    schedule = [rec(10, widest + 1, 1)]
    right, refused = model_outcome(frames, schedule)
    assert refused == "INJECT_RANGE" and 0 < len(right) < len(frames)
    await b.reset()
    await load(b, schedule)
    seen, _seen_at, _sent_at, unknown = await driver(b.dut, frames, len(right))
    await hold_stream(b, test, "the right model", seen, unknown, right, refused)
    accepts = right + [frames[len(right)]]                  # a model that hands out the refused frame, unchanged
    for label, wrong, name, where in (("a model that accepts the case", accepts, None, len(right)),
                                      ("a model that names it INJECT_OVERLAP", right, "INJECT_OVERLAP", len(right))):
        try:
            await hold_stream(b, test, label, seen, unknown, wrong, name)
        except harness.Mismatch as e:
            assert e.kind == "WORD" and e.at == where, str(e)
            continue
        raise AssertionError("the comparison was handed a wrong model (%s) and reported nothing" % label)

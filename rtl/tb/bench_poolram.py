"""The pool's read, registered on its own for block memory, held two ways (docs/rtl/poolram.md).

Parcel POOLRAM, round 5. rtl/core/core.sv's pool is read into `pool_q`, a register of its own with
no reset, and the forwarding of the word being written at the same edge is chosen after it, from
two small registers, `fwd_sel` and `fwd_val`. The aim is a memory synthesis can map to UltraRAM;
the claim is that nothing the core computes changes. It runs on the small top, `core_small`, once
under each profile.

THE STREAMS, the same for both tests. Each begins with a reset, then the memory's first 16 words
written through the simulator with known words no frame of the run writes (POISON), then a load:

    1  a pool of 1, back to back                 12 frames   the collision at every frame from 1
    2  a pool of 1, with gaps                    16 frames   collisions and gaps of 1 and 2
    3  a pool of 2, back to back                 12 frames   a read and a write at one edge, two slots
    4  a pool of 2, with gaps                    16 frames
    5  a pool of 3, back to back                 12 frames
    6  a pool of 8, with gaps                    24 frames
    7  a reset in the middle of a pool's fill: a pool of 5, three frames back to back, a reset with
       the memory NOT written again, the same shape loaded, fourteen frames with gaps

Four filters of one tap, coefficients 1 to 4, filter k on channel k mod the profile's channels;
pass; no shift; no hidden layer; every head weight 1: the score is the sum of the four pooled
sums. The samples are a RAMP on every channel, rising every frame by a step that differs by
channel, from a base that differs by stream. So every filter's rectified value rises strictly
from frame to frame, and a pool that drops any word but the right one moves all four pooled sums
the same way: their errors cannot cancel in the score. POISON is larger than any rectified value
here and differs by slot and by filter, so a read of a word no frame wrote is a wrong word, never
a hidden one. The gaps are the harness's own draws for a fixed seed; `gaps_of` replays them, and
each gapped stream asserts the pattern its mutants' failures rest on (the lead's ruling).

TWO TESTS.

  bit_identity_pool_collisions   every record of the seven streams through `harness.compare`,
                                 against the model, with the whole test's records counted
                                 (`core_host.Watch`). An identity test.
  s4_old_at_every_edge           the same frames and gaps through `harness.exchange`, without the
                                 model, and one segment more: a reset with frames in flight. A
                                 coroutine samples, at every falling edge from the first reset on,
                                 `s4_old` and the inputs of the line this parcel replaced, through
                                 the simulator, and works out in Python what that line's register
                                 would hold. Each segment's samples are held word by word against
                                 it with `harness.hold`. Its expected words come from the OLD line,
                                 not from the code it judges. Not an identity test: its words are
                                 not records.

WHAT IT CANNOT SEE, each a stated limit of docs/rtl/poolram.md:
  - THE SECOND TEST READS SEVEN OF THE CORE'S SIGNALS BY NAME (`rst` at the top; `s4_old`, `vld`,
    `pool_wp`, `pool_rp`, `s4_rect` and `pool_mem` in the core), and the stage numbers `ST_S1`,
    `ST_S3` and `ST_S4`. A renaming of any of them fails it when the handle is first looked up, at
    its start or its first sample, not silently.
  - It holds `s4_old` at the clocks its streams reach: pools of 1, 2, 3, 4, 5 and 8 on the small
    top. Beyond them, that `s4_old` is the old register's value at every edge is an argument.
  - Unknown bits are part of the second test's words: a sample is its value, then its mask of
    unknown bits above it. An X where the old register is known is a wrong word, and the same X on
    both sides is equal.
  - Nothing here meets a synthesis tool; Icarus Verilog ignores the memory's attribute.
"""
import os
import random

import cocotb
from cocotb.triggers import FallingEdge, ReadOnly

from spec import constants as C
from model import weights
from model.detector import Core

import harness
import core_host as host

PROFILE = os.environ["UNDERTONE_PROFILE"]
PROF = C.PROFILES[PROFILE]
CHANNELS = PROF["channels"]
PASS = C.RECTIFIERS["pass"]
LATENCY = 11                     # rtl/core/core.sv states it
SETTLE = 3 * LATENCY + 3         # past anything the design could put out late, as bench_core.py
FILTERS = 4                      # the small top's most (core_small: 4)
POISONED = 16                    # the memory's first words written before each stream
WORD_PREFIX = b"undertone-poolram-s4old\x00"     # so a digest of these words is never a digest of records

# label, pool, frames, max_gap, gap seed, the ramp's base (`check_gaps` says what each gapped stream must hold)
STREAMS = (
    ("1: a pool of 1, back to back", 1, 12, 0, 0, 400),
    ("2: a pool of 1, with gaps", 1, 16, 2, 2, 700),
    ("3: a pool of 2, back to back", 2, 12, 0, 0, 1000),
    ("4: a pool of 2, with gaps", 2, 16, 2, 3, 1300),
    ("5: a pool of 3, back to back", 3, 12, 0, 0, 1600),
    ("6: a pool of 8, with gaps", 8, 24, 2, 5, 1900),
)
MIDFILL = ("7: a pool of 5, reset in its fill", 5, 3, 14, 7, 2200, 2500)   # label, pool, before, after, seed, two bases
IN_FLIGHT = ("8: a pool of 4, reset with frames in flight", 4, 6, 10, 2800, 3100)   # label, pool, before, after, two bases


def gaps_of(seed, n, max_gap):
    """The idle clocks `harness.exchange` puts before each of n frames: its own draws, replayed."""
    rng = random.Random(seed)
    return [rng.randint(0, max_gap) for _ in range(n)]


def check_gaps():
    """What each gapped stream must hold, so that no mutant's failure rests on a seed by luck.

    Stream 2, a pool of 1: a frame right after its predecessor (a collision), one after a gap of 1, and
    a frame that did not collide followed by a gap of 2 or more (where a read register loading every
    clock shows). Stream 4, a pool of 2: past the fill, a frame right after its predecessor and one after
    a gap (where a forwarding without its valid shows). Streams 6 and 7: past the fill, both kinds."""
    g = gaps_of(STREAMS[1][4], STREAMS[1][2], STREAMS[1][3])
    assert any(x == 0 for x in g[1:]) and any(x == 1 for x in g[1:]), ("stream 2's gaps", g)
    assert any((i == 0 or g[i] >= 1) and g[i + 1] >= 2 for i in range(len(g) - 1)), ("stream 2's gaps", g)
    for (label, pool, n, max_gap, seed, _base) in (STREAMS[3], STREAMS[5]):
        g = gaps_of(seed, n, max_gap)
        assert any(x == 0 for x in g[pool:]) and any(x >= 1 for x in g[pool:]), (label, g)
    label, pool, _before, after, seed, _b1, _b2 = MIDFILL
    g = gaps_of(seed, after, 2)
    assert any(x == 0 for x in g[pool:]) and any(x >= 1 for x in g[pool:]), (label, g)


def ramp(base, n):
    """n frames, every channel rising every frame by a step of its own."""
    return [tuple(base + (60 + 20 * c) * i for c in range(CHANNELS)) for i in range(n)]


def blob_for(pool):
    filters = [{k % CHANNELS: [k + 1]} for k in range(FILTERS)]
    return weights.pack(PROFILE, filters, [1] * FILTERS, PASS, pool, 0)


def as_int(value):
    return value if isinstance(value, int) else value.to_unsigned()


def poison(w_rect, slot):
    """The word written into memory slot `slot` before a stream: lane k is 2^(W_RECT-3) + slot*256 + k*16 + 1,
    positive, larger than any rectified value of these streams, and different for every slot and lane."""
    return sum(((1 << (w_rect - 3)) + slot * 256 + k * 16 + 1) << (k * w_rect) for k in range(FILTERS))


async def write_poison(dut):
    core = host.inner(dut)
    w_rect = as_int(core.W_RECT.value)
    await FallingEdge(dut.clk)
    for slot in range(POISONED):
        core.pool_mem[slot].value = poison(w_rect, slot)
    await FallingEdge(dut.clk)


async def start(dut, poisoned=True):
    """A reset; the memory's first words written with POISON unless told not to."""
    await harness.reset(dut)
    if poisoned:
        await write_poison(dut)


async def loaded(dut, pool):
    blob = blob_for(pool)
    await host.load(dut, blob, 0)
    return Core(blob, 0)


async def caps_hold(dut):
    caps = await host.capabilities(dut)
    assert caps["cap_filters"] >= FILTERS and caps["cap_rows"] >= FILTERS and caps["cap_taps"] >= 1, caps
    assert caps["cap_pool"] >= max(POISONED, 8), caps
    return caps


# ------------------------------------------------------------------ the records, against the model

@cocotb.test()
async def bit_identity_pool_collisions(dut):
    check_gaps()
    harness.start_clock(dut)
    host.idle(dut)
    host.watch(dut)
    await harness.reset(dut)
    await caps_hold(dut)
    test, total = "bit_identity_pool_collisions", 0
    for label, pool, n, max_gap, seed, base in STREAMS:
        await start(dut)
        core = await loaded(dut, pool)
        total += (await host.compare(dut, core, ramp(base, n), test=test, label=label, gap_seed=seed, max_gap=max_gap,
                                     settle=SETTLE)).count
    label, pool, before, after, seed, base1, base2 = MIDFILL
    await start(dut)
    core = await loaded(dut, pool)
    total += (await host.compare(dut, core, ramp(base1, before), test=test, label=label + ": before the reset",
                                 max_gap=0, settle=SETTLE)).count
    await start(dut, poisoned=False)               # the memory keeps the three words of the run cut short
    core = await loaded(dut, pool)
    total += (await host.compare(dut, core, ramp(base2, after), test=test, label=label + ": after it", gap_seed=seed,
                                 max_gap=2, settle=SETTLE)).count
    assert total == sum(s[2] for s in STREAMS) + before + after, total
    await host.all_seen()


# ------------------------------------------------------------------ s4_old against the line it replaced, at every edge

def encode(value, width):
    """A sampled value as one number: its known bits, and above them the mask of its unknown bits."""
    if isinstance(value, int):
        return value
    if value.is_resolvable:
        return value.to_unsigned()
    text = str(value)
    known = int("".join("1" if ch == "1" else "0" for ch in text), 2)
    unknown = int("".join("0" if ch in "01" else "1" for ch in text), 2)
    return known | (unknown << width)


class OldLine:
    """At every falling edge, after the edge's writes have settled: the design's `s4_old` beside what the
    replaced register would hold, and then that register's next value, worked from the old line

        if (rst) s4_old <= '0;
        else if (vld[ST_S3]) s4_old <= (vld[ST_S4] && (pool_wp == pool_rp)) ? s4_rect : pool_mem[pool_rp];

    out of the same signals the coming rising edge will use. Started at a falling edge right after a
    reset, where that register holds 0."""

    def __init__(self, dut):
        self.dut, self.core = dut, host.inner(dut)
        self.width = len(self.core.s4_old)
        # core.sv's own stage numbers: vld is [ST_H4:ST_S1], so bit k - ST_S1 of its value is vld[k]
        self.s1, self.s3, self.s4 = (as_int(self.core.ST_S1.value), as_int(self.core.ST_S3.value),
                                     as_int(self.core.ST_S4.value))
        self.held = 0                                    # the old register, after the reset just passed
        self.seen, self.want, self.notes = [], [], []
        self.cells, self.on = {}, True
        self.task = cocotb.start_soon(self._run())

    def cell(self, slot):
        if slot not in self.cells:
            self.cells[slot] = self.core.pool_mem[slot]
        return self.cells[slot]

    async def _run(self):
        core, w = self.core, self.width
        while self.on:
            await ReadOnly()
            self.seen.append(encode(core.s4_old.value, w))
            self.want.append(self.held)
            rst = 1 if str(self.dut.rst.value) == "1" else 0
            vld = as_int(core.vld.value)
            v3, v4 = (vld >> (self.s3 - self.s1)) & 1, (vld >> (self.s4 - self.s1)) & 1
            wp, rp = as_int(core.pool_wp.value), as_int(core.pool_rp.value)
            self.notes.append("rst=%d vld[3]=%d vld[4]=%d pool_wp=%d pool_rp=%d" % (rst, v3, v4, wp, rp))
            if rst:
                self.held = 0
            elif v3:
                self.held = encode(core.s4_rect.value, w) if (v4 and wp == rp) else encode(self.cell(rp).value, w)
            await FallingEdge(self.dut.clk)

    def take(self):
        seen, want, notes = self.seen, self.want, self.notes
        self.seen, self.want, self.notes = [], [], []
        return seen, want, notes

    async def stop(self):
        self.on = False
        await FallingEdge(self.dut.clk)
        await self.task


def hold_segment(dut, old, label):
    """Every sample of the segment just ended, against the old register's."""
    seen, want, notes = old.take()
    w = old.width
    for i, (a, b) in enumerate(zip(seen, want)):
        if a != b:
            dut._log.info("%s: the first difference at clock %d of the segment (%s): s4_old 0x%X, the old register 0x%X",
                          label, i, notes[i], a, b)
            break

    def describe(have, expected):
        return "s4_old is 0x%X where the old line's register holds 0x%X (unknown bits, if any, above bit %d)" % (
            have, expected, w)

    harness.hold("s4_old_at_every_edge", label, seen, want, width_bytes=(2 * w + 7) // 8, prefix=WORD_PREFIX,
                 describe=describe)


async def drive(dut, frames, seed, max_gap):
    """The frames into the design, with the gaps `compare` would give them; the records are not compared here."""
    words = [harness.frame_word(PROFILE, f) for f in frames]
    await harness.exchange(dut, words, len(words), gap_seed=seed, max_gap=max_gap, settle=SETTLE)


@cocotb.test()
async def s4_old_at_every_edge(dut):
    check_gaps()
    harness.start_clock(dut)
    host.idle(dut)
    await harness.reset(dut)
    old = OldLine(dut)                                   # from here, every clock
    await caps_hold(dut)
    for label, pool, n, max_gap, seed, base in STREAMS:
        await start(dut)
        await loaded(dut, pool)
        await drive(dut, ramp(base, n), seed, max_gap)
        hold_segment(dut, old, label)
    label, pool, before, after, seed, base1, base2 = MIDFILL
    await start(dut)
    await loaded(dut, pool)
    await drive(dut, ramp(base1, before), 0, 0)
    await start(dut, poisoned=False)
    await loaded(dut, pool)
    await drive(dut, ramp(base2, after), seed, 2)
    hold_segment(dut, old, label)
    # A reset while frames are in the pipeline: six frames back to back, and the reset at the next clock.
    # Three have reached s4 and two s5; no record of them comes out, so this segment is here and not in the
    # identity test.
    label, pool, before, after, base1, base2 = IN_FLIGHT
    await start(dut)
    await loaded(dut, pool)
    for frame in ramp(base1, before):
        await FallingEdge(dut.clk)
        dut.in_valid.value = 1
        dut.in_frame.value = harness.frame_word(PROFILE, frame)
    await start(dut, poisoned=False)                     # rst rises at the next falling edge: frames in flight
    await loaded(dut, pool)
    await drive(dut, ramp(base2, after), 0, 0)
    hold_segment(dut, old, label)
    await old.stop()

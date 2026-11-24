"""The kernel's bench on its small top (rtl/krnl/krnl_small.sv): the queue, the writer, the edge, the run.

krnl_small is rtl/krnl/undertone_krnl.sv with the core at the seam's small
maxima and a queue of EIGHT records. The kernel's own lines are the same at
every maxima; here a stall longer than the queue costs eight records' clocks.
It runs once under each profile (two rows of the manifest, so that each
mutant runs under one).

The kernel is driven only through its AXI4-Lite port (cocotbext-axi's
AxiLiteMaster) and its memory (rtl/tb/krnl_mem.py). Every score word is held
against the model's own run (seam_host.model_records), from memory, slot by
slot, and as the memory took them, beat by beat (rtl/tb/krnl_host.py).

WHAT EACH TEST HOLDS
  identity_small            a stream in stage E0's shape whose slots cross a 4 KB page, under random
                            holds of every channel and late answers, the last answer held 200 clocks,
                            and the address and data held long enough before the page for a burst to
                            meet it: every record the model's, done only after every answer. Then, on
                            that run's words, the comparison handed a model one record late must report
                            a WORD mismatch at record 0 (the evidence is the test control_model_record_late's)
  truth_isolation           two wordings of the truth that add the same samples (3/1 and 6/2) give the
                            same score words
  truth_while_running       a truth record written after the start, ahead of the stream, gives the model's
                            records; one written after the stream passed its index is refused by the
                            injector (INJECT_OVERLAP) and ends the run short (RUN_LENGTH)
  chain_refusal_ends_the_run  a sum out of range: INJECT_RANGE in the injector, RUN_LENGTH in the kernel,
                            and memory holds exactly the records before the refused frame
  queue_overflow_refused    the memory holds its address and data channels longer than the queue: the
                            record cap_record_queue past the last taken is refused, RECORD_QUEUE, and
                            memory holds exactly the records before it
  memory_error_refused      one burst answered SLVERR: MEMORY_WRITE, and krn_records stops before it
  refused_at_the_edge       every refusal of the kernel's edge, by name, with nothing written
  reset_between_runs        krn_reset, then another shape: both runs the model's

WHAT THIS BENCH DOES NOT SEE, each a stated limit of docs/rtl/krnl.md: the queue at the build's depth
of 512 (it is here at 8); a truth schedule longer than the injector's store of 1,024; a stall of the
answers alone, which stalls nothing (up to sixteen bursts may be unanswered).
"""
import os
import random

import cocotb
from cocotb.triggers import RisingEdge

from spec import constants as C
from model import inject, weights
from model.detector import Core
from model.refusal import Refusal

import harness
import seam_host as seam
import krnl_host as k

PROFILE = os.environ["UNDERTONE_PROFILE"]
PROF = C.PROFILES[PROFILE]
E0 = C.PULSE_IDS["e0"]
PULSE = C.PULSES["e0"]
L = len(PULSE)
SEED = 2026112460
SLOT = C.MEMORY_SLOT_BYTES
PAGE = 4096
SIGMA = {"s16x1": (6, 1), "s24x3": (13, 2)}[PROFILE]      # small, for a short table: the writes are the cost
GAINS = {"s16x1": (1,), "s24x3": (3, -2, 1)}[PROFILE]
OTHER = {"s16x1": [[0], [0]], "s24x3": [[0, 2], [1]]}[PROFILE]

# The sizes, set from the kernel's measured rate (docs/rtl/krnl.md, the register). Each run is short: what
# is held here is the kernel's, and a record is the same work in the kernel at the tenth as at the first.
IDENTITY_FRAMES = {"s16x1": 129, "s24x3": 69}[PROFILE]   # odd, and not a multiple of 16
ISOLATION_FRAMES = 67
WHILE_FRAMES = 75
LATE_FRAMES = 40
RANGE_FRAMES = 70
OVERFLOW_FRAMES = 30
ERROR_FRAMES = 20
EDGE_FRAMES = 10
RESET_FRAMES = 21


def rec(index, num=1, den=1, pulse_id=E0):
    return {"index": index, "pulse_id": pulse_id, "amplitude_num": num, "amplitude_den": den}


def e0_blob(gains=GAINS):
    return weights.matched_filter(PROFILE, PULSE, gains)


def case(frames, schedule, blob=None, seed=SEED, epoch=0):
    return seam.Case(PROFILE, seed, SIGMA, frames, schedule, e0_blob() if blob is None else blob, epoch)


async def until_beats(host, mem, n, clocks):
    """Return once the memory has taken n beats; never wait more than `clocks`."""
    waited = 0
    while len(mem.beats) < n:
        assert waited < clocks, "after %d clocks the memory has taken %d beat(s), not %d" % (waited, len(mem.beats), n)
        await RisingEdge(host.dut.ap_clk)
        waited += 1


async def clocks(host, n):
    for _ in range(n):
        await RisingEdge(host.dut.ap_clk)


# ------------------------------------------------------------------ bit identity through the kernel

IDENTITY = {"s16x1": [rec(0, 3, 2), rec(L + 1, -5, 2)], "s24x3": [rec(0, 3, 2)]}[PROFILE]
FIRST = [rec(0, 3, 2)]       # one pulse, from the first frame
PAGE_SLOT = 20               # the slot that begins a 4 KB page


@cocotb.test()
async def identity_small(dut):
    """And, on the words of that run, the comparison handed a model one record late must report a WORD
    mismatch at record 0: the hold of memory is not a hold of anything against itself."""
    test = "identity_small"
    this = case(IDENTITY_FRAMES, IDENTITY)
    base = 0x30000 - PAGE_SLOT * SLOT
    host, mem = await k.begin(dut, base=base, size=this.frames * SLOT, seed=SEED, stall=0.03, stall_len=20,
                              answer_delay=20)
    mem.late_beat, mem.late_clocks = this.frames - 1, 200
    period = seam.period(PROFILE)

    async def before_the_page(host_, mem_):
        # hold the address and the data from slot 17, three slots before the page, for five records, so that
        # the queue holds records on both sides of the page when the bursts resume
        await until_beats(host_, mem_, PAGE_SLOT - 3, period * (PAGE_SLOT + 10) + 4000)
        mem_.hold_aw = mem_.hold_w = True
        await clocks(host_, period * 5)
        mem_.hold_aw = mem_.hold_w = False

    await k.hold_run(test, "E0's shape, slots across a 4 KB page, held and random stalls", host, mem, this, base,
                     during=before_the_page)
    lengths = [b[2] for b in mem.bursts]
    assert max(lengths) > 1, "no burst was longer than one beat: %r" % lengths
    page = [b for b in mem.bursts if (b[1] % PAGE) + b[2] * SLOT == PAGE and b[2] > 1]
    assert page, "no burst of more than one beat ended at the page's edge: %r" % [(hex(b[1]), b[2]) for b in mem.bursts]

    expected, _ = seam.model_records(this)
    late = [dict(expected[0], index=expected[0]["index"] + 1)] + list(expected[:-1])
    try:
        k.hold_memory("control_model_record_late", "against a model one record late", mem, base, late)
    except harness.Mismatch as e:
        assert e.kind == "WORD" and e.at == 0, "the comparison reported %s at %d, not WORD at 0" % (e.kind, e.at)
    else:
        raise AssertionError("the comparison passed a model one record late")


# ------------------------------------------------------------------ truth isolation

# Two wordings of the truth that add the same samples: every field but the index differs, the numerators'
# lowest bits among them.
ISOLATION = (
    ("as first written", [rec(2, 3, 1)]),
    ("the same ratio written otherwise", [rec(2, 6, 2)]),
)


@cocotb.test()
async def truth_isolation(dut):
    test = "truth_isolation"
    streams, truths = [], []
    for _label, schedule in ISOLATION:
        stream, truth = seam.model_stream(case(ISOLATION_FRAMES, schedule, seed=SEED + 2))
        streams.append(stream)
        truths.append(truth)
    assert all(s == streams[0] for s in streams), "the model's streams differ: these are not the same samples"
    assert len(set(repr(t) for t in truths)) == len(ISOLATION), "two of the wordings are the same truth"
    assert [t[-1]["amplitude_num"] % 2 for t in truths] == [1, 0], "the numerators' lowest bits are not 1 and 0"
    assert streams[0] != tuple(case(ISOLATION_FRAMES, [], seed=SEED + 2).noise()), "the truth adds nothing"
    digests, host, mem = [], None, None
    for n, (label, schedule) in enumerate(ISOLATION):
        base = 0x40000 + n * 0x2000
        if host is None:
            host, mem = await k.begin(dut, base=base, size=ISOLATION_FRAMES * SLOT, seed=SEED + n)
        else:
            await k.again(host, mem, base, ISOLATION_FRAMES * SLOT)
        digests.append(await k.hold_run(test, label, host, mem, case(ISOLATION_FRAMES, schedule, seed=SEED + 2), base))
    assert len(set(digests)) == 1, "the kernel's records changed with the truth: %r" % (digests,)


# ------------------------------------------------------------------ truth from the host while the run goes

WHILE = [rec(10, 5, 2)]


@cocotb.test()
async def truth_while_running(dut):
    test = "truth_while_running"
    this = case(WHILE_FRAMES, WHILE, seed=SEED + 3)
    base = 0x50000
    host, mem = await k.begin(dut, base=base, size=this.frames * SLOT, seed=SEED + 3)
    period = seam.period(PROFILE)

    async def feed(host_, mem_):
        # the one record written once the run has begun and before the stream reaches it
        assert not mem_.beats
        await host_.write_many(seam.truth_writes(WHILE[0]))
        assert len(mem_.beats) + 3 < WHILE[0]["index"], "the record at %d came too late" % WHILE[0]["index"]

    await k.hold_run(test, "a record written after the start", host, mem, this, base, truth=[], during=feed)

    # A record written after the stream has passed its index: the injector refuses it and the run ends short.
    late = rec(5, 3, 1)
    short = case(LATE_FRAMES, [], seed=SEED + 4)
    base = 0x60000
    await k.again(host, mem, base, short.frames * SLOT)

    async def too_late(host_, mem_):
        await until_beats(host_, mem_, 20, period * 30 + 4000)
        await host_.write_many(seam.truth_writes(late))

    out = await k.run_case(host, mem, short, base, during=too_late)
    assert out["inject"] == k.code("INJECT_OVERLAP"), k.refusal_names(out)
    assert out["kernel"] == k.code("RUN_LENGTH"), k.refusal_names(out)
    assert out["status"]["done"] == 1
    m = out["records"]
    assert 20 <= m < short.frames, "krn_records reads %d" % m
    expected, _ = seam.model_records(short)
    k.hold_memory(test, "the records before a late record ended the run", mem, base, expected[:m])
    k.check_memory(mem, base, m)


# ------------------------------------------------------------------ a refusal in the chain ends the kernel's run

@cocotb.test()
async def chain_refusal_ends_the_run(dut):
    test = "chain_refusal_ends_the_run"
    big = PROF["sample_max"] // max(abs(p) for p in PULSE) + 2
    this = case(RANGE_FRAMES, [rec(5, big, 1)], seed=SEED + 5)
    # The model's own stream, up to the frame its injector refuses.
    frames = []
    stream, _truth = inject.inject(PROFILE, this.noise(), this.schedule, this.frames)
    try:
        for frame in stream:
            frames.append(frame)
    except Refusal as e:
        assert e.name == "INJECT_RANGE", e.name
    refused_at = len(frames)
    assert 5 <= refused_at < 5 + L, "the model refuses frame %d" % refused_at
    model = Core(this.blob, this.epoch)
    expected = [model.step(frame) for frame in frames]
    base = 0x70000
    host, mem = await k.begin(dut, base=base, size=this.frames * SLOT, seed=SEED + 5)
    out = await k.run_case(host, mem, this, base)
    assert out["inject"] == k.code("INJECT_RANGE") and out["kernel"] == k.code("RUN_LENGTH"), k.refusal_names(out)
    assert out["status"]["done"] == 1
    assert out["records"] == refused_at, "krn_records reads %d; the model refuses frame %d" % (out["records"], refused_at)
    k.hold_memory(test, "the records before INJECT_RANGE", mem, base, expected)
    k.check_memory(mem, base, refused_at)


# ------------------------------------------------------------------ a stall longer than the queue

@cocotb.test()
async def queue_overflow_refused(dut):
    test = "queue_overflow_refused"
    this = case(OVERFLOW_FRAMES, [], seed=SEED + 6)
    base = 0x80000
    host, mem = await k.begin(dut, base=base, size=this.frames * SLOT, seed=SEED + 6)
    depth = (await host.capabilities())["cap_record_queue"]
    period = seam.period(PROFILE)
    held = {}

    async def stall(host_, mem_):
        await until_beats(host_, mem_, 5, period * 20 + 4000)
        mem_.hold_aw = mem_.hold_w = True
        await clocks(host_, 2)                      # a beat already offered may still be taken
        held["taken"] = len(mem_.beats)
        await clocks(host_, period * (depth + 4))
        mem_.hold_aw = mem_.hold_w = False

    out = await k.run_case(host, mem, this, base, during=stall)
    first_refused = held["taken"] + depth
    assert out["kernel"] == k.code("RECORD_QUEUE"), "the kernel's refusal is %s where RECORD_QUEUE is required" % (
        k.refusal_names(out),)
    assert out["records"] == first_refused, "krn_records reads %d; record %d (%d taken and a queue of %d) is the " \
        "first refused" % (out["records"], first_refused, held["taken"], depth)
    assert out["peak"] == depth, "krn_queue_peak reads %d, not the queue's %d" % (out["peak"], depth)
    assert out["status"]["done"] == 1 and out["answered_at_done"]
    expected, _ = seam.model_records(this)
    k.hold_memory(test, "the records before the one the full queue refused", mem, base, expected[:first_refused])
    k.check_memory(mem, base, first_refused)


# ------------------------------------------------------------------ an answer other than OKAY

@cocotb.test()
async def memory_error_refused(dut):
    test = "memory_error_refused"
    this = case(ERROR_FRAMES, [], seed=SEED + 7)
    base = 0x90000
    host, mem = await k.begin(dut, base=base, size=this.frames * SLOT, seed=SEED + 7)
    mem.error_burst = 3
    out = await k.run_case(host, mem, this, base)
    good = sum(b[2] for b in mem.bursts[:3])
    assert out["kernel"] == k.code("MEMORY_WRITE"), "the kernel's refusal is %s" % (k.refusal_names(out),)
    assert out["status"]["done"] == 1
    assert out["records"] == good, "krn_records reads %d; the bursts before the error hold %d" % (out["records"], good)
    assert len(mem.bursts) < this.frames, "every record was still written after the error"
    expected, _ = seam.model_records(this)
    k.hold_memory(test, "the records answered OKAY", mem, base, expected[:good])


# ------------------------------------------------------------------ the kernel's edge

@cocotb.test()
async def refused_at_the_edge(dut):
    base = 0xA0000
    host, mem = await k.begin(dut, base=base, size=EDGE_FRAMES * SLOT, seed=SEED + 8)

    async def refused(expect, detail):
        got = await host.take("krn_refusal")
        assert got == k.code(expect), "%s: refused %s, not %s" % (detail, k.NAME_OF.get(got, got), expect)

    # Nothing loaded: the source has no table, so it does not start.
    await k.arguments(host, base, EDGE_FRAMES * SLOT, EDGE_FRAMES)
    await host.write(k.off("krn_start"), 1)
    await refused("RUN_START", "a start with no table in the source")
    assert await host.take("src_refusal") == k.code("REGISTER_ACCESS")
    state = await host.status()
    assert state == {"running": 0, "done": 0, "refused": 0}, state

    # Each argument wrong in turn, the others right.
    for detail, args, name in (("a length of zero", (base, EDGE_FRAMES * SLOT, 0), "STREAM_LENGTH"),
                               ("a base half a slot off", (base + SLOT // 2, EDGE_FRAMES * SLOT, EDGE_FRAMES), "BUFFER_ALIGN"),
                               ("a size one byte short", (base, EDGE_FRAMES * SLOT - 1, EDGE_FRAMES), "BUFFER_SIZE"),
                               ("slots past 2^64", ((1 << 64) - (EDGE_FRAMES - 1) * SLOT, 1 << 40, EDGE_FRAMES), "BUFFER_SIZE")):
        await k.arguments(host, *args)
        await host.write(k.off("krn_start"), 1)
        await refused(name, detail)
        state = await host.status()
        assert state["running"] == 0 and state["done"] == 0, (detail, state)

    # Writes the kernel takes for itself and refuses.
    for detail, at, value in (("a start of 2", k.off("krn_start"), 2), ("a reset of 0", k.off("krn_reset"), 0),
                              ("a word below the first offset", 0x8, 1), ("src_frames' lower word", k.off("src_frames"), 5),
                              ("src_frames' upper word", k.off("src_frames", 1), 0), ("krn_status", k.off("krn_status"), 1),
                              ("cap_record_queue", k.off("cap_record_queue"), 1),
                              ("an offset in the block that holds no row", k.off("cap_record_queue") + 4, 1),
                              ("an offset that is not a word's", k.off("krn_frames") + 2, 1),
                              ("a refusal register written other than 0", k.off("krn_refusal"), 3)):
        await host.write(at, value)
        await refused("REGISTER_ACCESS", detail)
    assert await host.read(0x8) == 0
    await host.write_bytes(k.off("krn_frames"), bytes([7, 0]))        # two strobes of four
    await refused("REGISTER_ACCESS", "a write of two bytes")
    assert await host.wide("krn_frames") == EDGE_FRAMES
    assert await host.get("src_refusal") == 0, "a write of src_frames reached the source"
    assert not mem.beats, "a refused start wrote to memory"

    # A start with a refusal latched is not taken, and latches nothing more.
    await host.write(k.off("krn_frames") + 2, 1)                     # REGISTER_ACCESS, latched
    await k.arguments(host, base, EDGE_FRAMES * SLOT, EDGE_FRAMES)
    await host.write(k.off("krn_start"), 1)
    state = await host.status()
    assert state == {"running": 0, "done": 0, "refused": 1}, state
    await refused("REGISTER_ACCESS", "the latched refusal")

    # While a run goes: a start, an argument and a reset are each KERNEL_BUSY; the run is still the model's.
    this = case(EDGE_FRAMES, [], seed=SEED + 8)

    async def busy(host_, mem_):
        for detail, at, value in (("a start", k.off("krn_start"), 1), ("an argument", k.off("krn_frames"), 3),
                                  ("a reset", k.off("krn_reset"), 1)):
            await host_.write(at, value)
            got = await host_.take("krn_refusal")
            assert got == k.code("KERNEL_BUSY"), "%s while running: %s" % (detail, k.NAME_OF.get(got, got))

    out = await k.run_case(host, mem, this, base, during=busy)
    expected, _ = seam.model_records(this)
    k.hold_memory("refused_at_the_edge", "a run with three refused writes in it", mem, base, expected)
    k.check_memory(mem, base, this.frames)
    k.check_quiet(out, this.frames)


# ------------------------------------------------------------------ two runs, a reset between

@cocotb.test()
async def reset_between_runs(dut):
    test = "reset_between_runs"
    base = 0xB0000
    first = case(RESET_FRAMES, [], seed=SEED + 9, epoch=4)
    host, mem = await k.begin(dut, base=base, size=RESET_FRAMES * SLOT, seed=SEED + 9)
    await k.hold_run(test, "the first run", host, mem, first, base)
    await host.write(k.off("krn_reset"), 1)
    state = await host.status()
    assert state == {"running": 0, "done": 0, "refused": 0}, state
    assert await host.wide("krn_records") == 0
    caps = await host.capabilities()
    blob = k.core_host.blob_of(PROFILE, OTHER, caps["cap_taps"] - 1, random.Random(SEED + 9), C.RECTIFIERS["abs"], 3, 5,
                               hidden=2, hidden_shift=7, between=C.RECTIFIERS["abs"])
    second = case(RESET_FRAMES, [], blob=blob, seed=SEED + 10, epoch=7)
    base = 0xB4000
    mem.renew(base, RESET_FRAMES * SLOT)
    await k.hold_run(test, "another shape after krn_reset", host, mem, second, base)

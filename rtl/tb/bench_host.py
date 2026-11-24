"""The host library's bench: the library (host/) driving KRNL's kernel in simulation, held against the model.

Bit identity's second part, the host: every score word the library hands its
caller, read from the kernel's buffer through the library, equals the model's
own run of the same configuration. The library is the code under test and the
kernel is KRNL's (rtl/krnl/undertone_krnl.sv at its defaults, the first build).

THE LIBRARY RUNS AS IT WILL ON THE CARD: its procedures through the coroutine
driver (`host.drive.AsyncHost`) over `host_sim.Sim`, whose operations are
AXI4-Lite transactions on the control port and the memory model's store.
Nothing here writes a register itself but through the library, except where a
test plants a fault below the seam (`host_sim.Filtered`) or above it (a
subclass of the library), each named.

THE EXPECTATION IS ALWAYS THE MODEL'S: `model.run.detect` on `model.source.Noise`
and the schedule, or `seam_host.model_records` for a swap, or the model's lazy
run up to its refusal. The library is handed that Noise's own table, the same
schedule and the same blob bytes; one wrong in both alike is not seen (a limit
of docs/host/host.md).

WHAT EACH TEST HOLDS
  identity_e0                      open, reset, load of E0's matched filter, a run with every truth record
                                   written before the start, the records: every word the model's
  identity_fed_and_swapped         a seeded shape with a hidden layer; truth fed while the run goes (two of
                                   five records ahead); a swap to other weights of that shape at an index
                                   inside the run, taken before it
  same_code_both_drivers           the CALL driver (XRT's) replays identity_fed_and_swapped's calls against
                                   the kernel's recorded answers and must make the same operations
  refusal_read_back_by_name        a sum out of range: the injector's INJECT_RANGE raised by the library,
                                   the kernel's RUN_LENGTH in its detail; the records written are the model's
                                   before its refusal; one slot more is RECORD_SLOT
  capabilities_refused_before_any_write   the advertisement read from the kernel, and blobs past it refused by
                                   the bound's name with nothing written
  control_*                        each a fault planted in the library or below the seam, reported by the
                                   comparison at the record and field it predicts

Every wait has a bound in clocks: `finish`'s polls times the backend's pause,
and each AXI4-Lite transaction `host_sim.Sim.bound` clocks.
"""
import os
import random

import cocotb
from cocotb.triggers import ClockCycles

from spec import constants as C
from model import inject, run, weights
from model.detector import Core
from model.refusal import Refusal

import harness
import core_host
import seam_host as seam
import krnl_host
import host_sim

from host import library as L, ops
from host.drive import AsyncHost, Host

PROFILE = os.environ["UNDERTONE_PROFILE"]
PROF = C.PROFILES[PROFILE]
CHANNELS = PROF["channels"]
PULSE = C.PULSES["e0"]
LP = len(PULSE)
E0 = C.PULSE_IDS["e0"]
PERIOD = seam.period(PROFILE)                     # clocks between two frames of the source
SEED = 0x0123456789ABCDEF                         # bits in both words: the wrong-word control needs them
SIGMA = (5, 1)                                    # a table of tens of entries: a short load
GAINS = {"s16x1": (1,), "s24x3": (3, -2, 1)}[PROFILE]
EPOCH = 5
ABS = C.RECTIFIERS["abs"]
PAUSE = 16                                        # clocks between two polls of a run


def rec(index, num=1, den=1):
    return {"index": index, "pulse_id": E0, "amplitude_num": num, "amplitude_den": den}


def e0_blob(gains=GAINS):
    return weights.matched_filter(PROFILE, PULSE, gains)


def case(frames, schedule, blob=None, seed=SEED):
    return seam.Case(PROFILE, seed, SIGMA, frames, schedule, e0_blob() if blob is None else blob, EPOCH)


def polls(frames):
    """Enough polls for a run of `frames`: the frames, the kernel's drain, the chain's latency, and a margin."""
    return (frames * PERIOD + 128 + 200 + 2000) // PAUSE + 50


async def begin(dut, wrap=None):
    """The kernel, its memory and the library over them. `wrap` puts a test's backend around the simulated one."""
    axil, memory = await krnl_host.begin(dut, base=host_sim.BASE, size=4096, margin=host_sim.MARGIN)
    sim = host_sim.Sim(dut, axil, memory, pause=PAUSE)
    backend = sim if wrap is None else wrap(sim)
    return sim, memory, backend


def model_lazy(this, before=()):
    """The model's records up to its own refusal, if it refuses: (records, the refusal's name or None)."""
    core = Core(this.blob, this.epoch)
    injected, _truth = inject.inject(PROFILE, this.noise(), this.schedule, this.frames)
    for method, argument in before:
        getattr(core, method)(argument)
    out = []
    try:
        for frame in injected:
            out.append(core.step(frame))
    except Refusal as e:
        return out, e.name
    return out, None


async def run_case(lib, this, ahead=None, during=None):
    """Through the library: load, start, (during), finish, records. Returns (records, the run's report)."""
    await lib.load(this.blob, epoch=this.epoch)
    await lib.start(this.seed, this.noise().table, this.frames, this.schedule, ahead=ahead)
    if during is not None:
        await during(lib)
    report = await lib.finish(polls(this.frames))
    return await lib.records(), report


def words(records):
    return [harness.record_word(r) for r in records]


def check_buffer(memory, this, got):
    """By assertion: the raw slots are the library's records then zeros; the guard before slot 0 and the
    margin after the last slot hold the pattern; the memory model saw no fault of protocol."""
    base = host_sim.BASE + L.GUARD
    raw = memory.read(base, this.frames * L.SLOT)
    for i, record in enumerate(got):
        slot = raw[i * L.SLOT:(i + 1) * L.SLOT]
        assert slot == harness.record_word(record).to_bytes(L.RECORD_BYTES, "little") + bytes(L.SLOT - L.RECORD_BYTES), i
    assert memory.read(host_sim.BASE, L.GUARD) == bytes([L.PATTERN]) * L.GUARD, "a write landed in the guard"
    assert memory.read(base + this.frames * L.SLOT, 256) == bytes([L.PATTERN]) * 256, "a write landed past the last slot"
    assert memory.faults == [], memory.faults


async def quiet(lib):
    said = await lib.refusals()
    assert said == {"source": None, "injector": None, "core": None, "kernel": None}, said


# ------------------------------------------------------------------ bit identity through the library

@cocotb.test()
async def identity_e0(dut):
    test = "identity_e0"
    sim, memory, backend = await begin(dut)
    lib = AsyncHost(backend)
    identity = await lib.open()
    assert identity["profile"] == PROFILE, identity
    await lib.reset()
    this = case(200, [rec(5, 3, 2), rec(5 + LP, -7, 4), rec(5 + 2 * LP, 5, 3)])
    expected, _truth = run.detect(this.noise(), this.schedule, this.frames, this.blob, this.epoch)
    got, report = await run_case(lib, this)
    seam.hold_records(test, "E0's shape, the truth written before the start", words(got), words(expected), None)
    assert report["records"] == this.frames and report["truth_while_running"] == 0, report
    check_buffer(memory, this, got)
    await quiet(lib)


_kept = {}


@cocotb.test()
async def identity_fed_and_swapped(dut):
    await fed_and_swapped(dut)


async def fed_and_swapped(dut):
    """The body of identity_fed_and_swapped, also run by same_code_both_drivers when it has no kept run."""
    test = "identity_fed_and_swapped"
    sim, memory, backend = await begin(dut)
    trace, calls = [], []
    lib = AsyncHost(backend, trace=trace)

    async def call(name, *args, **kw):
        result = await getattr(lib, name)(*args, **kw)
        calls.append((name, args, kw, result))
        return result

    rng = random.Random(SEED + 1)
    sets = {"s16x1": [[0], [0]], "s24x3": [[0, 2], [1]]}[PROFILE]
    blob = core_host.blob_of(PROFILE, sets, 40, rng, ABS, 3, 5, hidden=2, hidden_shift=7, between=ABS)
    other = core_host.reweighted(rng, blob)
    at = 200
    this = case(360, [rec(5 + 70 * k, k + 2, 3) for k in range(5)], blob=blob, seed=SEED + 1)
    expected, _truth = seam.model_records(this, before=[("write_shadow", other), ("commit", at)])
    await call("open")
    await call("reset")
    await call("load", this.blob, epoch=this.epoch)
    await call("start", this.seed, this.noise().table, this.frames, this.schedule, ahead=2)
    for _ in range(this.frames):                  # the run fed until 60 frames are through the core: a bound
        await call("step")
        if await call("raw_read", L.offset("next_index")) >= 60:
            break
        await ClockCycles(dut.ap_clk, PAUSE)
    else:
        raise AssertionError("after %d rounds the core has not taken 60 frames" % this.frames)
    swapped = await call("swap", other, at)
    assert swapped["next_index_after"] < at, "the commit was taken at next_index %d, not before %d" % (
        swapped["next_index_after"], at)
    report = await call("finish", polls(this.frames))
    got = await call("records")
    seam.hold_records(test, "a hidden layer, truth fed while it runs, a swap at %d" % at, words(got), words(expected),
                      None)
    assert report["truth_before_start"] == 2 and report["truth_while_running"] == 3, report
    assert swapped["next_index_before"] >= 60, swapped
    epochs = sorted({r["epoch"] for r in got})
    assert epochs == [EPOCH, EPOCH + 1] and got[at]["epoch"] == EPOCH + 1 and got[at - 1]["epoch"] == EPOCH
    _kept["fed"] = (calls, list(trace))          # the recorded calls' operations, before the checks' own reads
    check_buffer(memory, this, got)
    await quiet(lib)
    first = [i for i, e in enumerate(trace) if e.call == "swap"][0]
    span = trace[first + swapped["accepting_op"]].after - trace[first + swapped["first_shadow_op"]].before
    dut._log.warning("HOST-SWAP-TIMING first shadow write to the accepting read: %d clocks; next_index %d to %d",
                     span, swapped["next_index_before"], swapped["next_index_after"])


@cocotb.test()
async def same_code_both_drivers(dut):
    """XRT's driver, given this kernel's answers, makes exactly the operations that gave the identity."""
    if "fed" not in _kept:
        await fed_and_swapped(dut)
    calls, trace = _kept["fed"]
    recorded = [(ops.key(e.op), e.result) for e in trace]
    replay = host_sim.Replay(recorded, ops.key)
    host = Host(replay, library=L.Library())
    for name, args, kw, result in calls:
        again = getattr(host, name)(*args, **kw)
        if name == "start":
            assert ops.result_key(again) == ops.result_key(result), name
        else:
            assert again == result, name
    assert replay.at == len(recorded), "the call driver made %d operations, the coroutine driver %d" % (
        replay.at, len(recorded))
    assert len(recorded) > 100


# ------------------------------------------------------------------ refusals through the library

@cocotb.test()
async def refusal_read_back_by_name(dut):
    test = "refusal_read_back_by_name"
    sim, memory, backend = await begin(dut)
    lib = AsyncHost(backend)
    await lib.open()
    await lib.reset()
    big = {"s16x1": 40, "s24x3": 10000}[PROFILE]
    this = case(120, [rec(10, big, 1)])
    expected, name = model_lazy(this)
    assert name == "INJECT_RANGE" and 10 < len(expected) < 10 + LP, (name, len(expected))
    try:
        await run_case(lib, this)
    except Refusal as e:
        assert e.name == "INJECT_RANGE" and "kernel RUN_LENGTH" in e.detail, e
    else:
        raise AssertionError("a run with a sum out of range was not refused")
    got = await lib.records()
    seam.hold_records(test, "the records written before the injector's refusal", words(got), words(expected), None)
    try:
        await lib.records(count=len(expected) + 1)
    except Refusal as e:
        assert e.name == "RECORD_SLOT" and "slot %d" % len(expected) in e.detail, e
    else:
        raise AssertionError("a slot nothing wrote was handed back")
    await quiet(lib)


def past_the_build(caps):
    """(name, a blob one past the build's advertisement): what this profile can say."""
    out = [("SHAPE_FILTERS", weights.pack(PROFILE, [{0: [1, 2]} for _ in range(caps["cap_filters"] + 1)],
                                          [1] * (caps["cap_filters"] + 1), 0, 1, 0))]
    other = [p for p in sorted(C.PROFILES) if p != PROFILE][0]
    out.append(("PROFILE_UNKNOWN", weights.matched_filter(other, PULSE, (1,) * C.PROFILES[other]["channels"])))
    if CHANNELS > 1:
        k = caps["cap_rows"] // CHANNELS + 1
        if k <= caps["cap_filters"]:
            out.append(("SHAPE_ROWS", weights.pack(PROFILE, [dict((c, [1]) for c in range(CHANNELS)) for _ in range(k)],
                                                   [1] * k, 0, 1, 0)))
    return out


@cocotb.test()
async def capabilities_refused_before_any_write(dut):
    sim, memory, backend = await begin(dut, wrap=host_sim.Counting)
    lib = AsyncHost(backend)
    identity = await lib.open()
    caps = identity["caps"]
    assert (caps["cap_filters"], caps["cap_rows"], caps["cap_taps"], caps["cap_hidden"]) == (4, 4, 128, 12), caps
    names = []
    for want, blob in past_the_build(caps):
        try:
            await lib.load(blob)
        except Refusal as e:
            assert e.name == want, (want, e)
        else:
            raise AssertionError("a blob past %s was written" % want)
        assert backend.effects == [], (want, backend.effects[:1])
        names.append(want)
    assert len(names) == (3 if CHANNELS > 1 else 2), names


# ------------------------------------------------------------------ the controls

def first_difference_of(this, other):
    a, _ = run.detect(this.noise(), this.schedule, this.frames, this.blob, this.epoch)
    b, _ = run.detect(other.noise(), other.schedule, other.frames, other.blob, other.epoch)
    return seam.first_difference(a, b), a


async def expect_mismatch(test, label, lib, this, at, field="score"):
    """A run through `lib` whose comparison with the model must fail at record `at`, in `field` alone."""
    got, _report = await run_case(lib, this)
    try:
        seam.hold_records(test, label, words(got), words(run.detect(this.noise(), this.schedule, this.frames,
                                                                    this.blob, this.epoch)[0]), None)
    except harness.Mismatch as e:
        assert e.kind == "WORD" and e.at == at and e.detail.startswith("field(s) %s differ" % field), (e.kind, e.at, e.detail)
    else:
        raise AssertionError("%s: the comparison reported nothing" % label)


class FlipsACoefficientBit(L.Library):
    """The brief's named control: a library that flips bit 0 of the first row's coefficient T - 1 (the one that
    meets the newest sample) as it turns the blob into words."""

    def _words(self, config):
        out = super()._words(config)
        first = config["filters"][0]
        taps = len(first[min(first)])
        out[taps - 1] ^= 1
        return out


@cocotb.test()
async def control_library_coefficient_bit(dut):
    test = "control_library_coefficient_bit"
    config = weights.unpack(e0_blob())
    rows = dict(config["filters"][0])
    c = min(rows)
    rows[c] = rows[c][:-1] + (rows[c][-1] ^ 1,)
    flipped = weights.pack(PROFILE, [rows], list(config["head"]), config["rectifier"], config["pool"],
                           config["score_shift"])
    probe = case(16, [])
    at, _ = first_difference_of(probe, probe.but(blob=flipped))
    assert at is not None and at <= 3, "the flipped tap does not reach an early record: %r" % (at,)
    sim, memory, backend = await begin(dut)
    lib = AsyncHost(backend, library=FlipsACoefficientBit())
    await lib.open()
    await lib.reset()
    await expect_mismatch(test, "a coefficient bit flipped by the library", lib, case(at + 4, []), at)


@cocotb.test()
async def control_library_ignores_capabilities(dut):
    """The brief's named control, on the kernel's own advertisement: a library that writes a blob past it is
    caught by the check of capabilities_refused_before_any_write, and the core refuses it by the same name."""

    class WritesFirst(L.Library):
        def _against(self, config, ident):
            return None
    sim, memory, backend = await begin(dut, wrap=host_sim.Counting)
    lib = AsyncHost(backend, library=WritesFirst())
    identity = await lib.open()
    await lib.reset()
    backend.effects.clear()
    want, blob = past_the_build(identity["caps"])[0]
    try:
        await lib.load(blob)
    except Refusal as e:
        assert e.name == want, e
    else:
        raise AssertionError("the core took a blob past its advertisement")
    assert backend.effects, "the check saw no write"


def dropping(offset):
    """A backend that drops the first write it is handed to `offset`."""
    state = {"done": False}

    def edit(pairs):
        out = []
        for where, word in pairs:
            if where == offset and not state["done"]:
                state["done"] = True
                continue
            out.append((where, word))
        return out
    return lambda sim: host_sim.Filtered(sim, edit), state


@cocotb.test()
async def control_backend_drops_a_write(dut):
    """The lead's control: a backend that drops one register write (the first truth record's numerator, which
    the injector then holds at its reset value, 0) is caught by the comparison, not by any check of its own."""
    test = "control_backend_drops_a_write"
    this = case(1 + LP, [rec(1, 3, 1)])
    at, _ = first_difference_of(this, this.but(schedule=[rec(1, 0, 1)]))
    assert at is not None and at <= 8, "the record reaches no early record: %r" % (at,)
    wrap, state = dropping(L.offset("inj_truth_amplitude_num"))
    sim, memory, backend = await begin(dut, wrap=wrap)
    lib = AsyncHost(backend)
    await lib.open()
    await lib.reset()
    await expect_mismatch(test, "the first numerator dropped below the seam", lib, this, at)
    assert state["done"]


@cocotb.test()
async def control_backend_writes_a_wrong_word(dut):
    """The lead's control: a backend that writes src_seed's lower word at its upper word's offset. The source
    then holds a lower word of 0, its reset, and the upper word written after: the seed's lower bits are lost."""
    test = "control_backend_writes_a_wrong_word"
    low, high = L.offset("src_seed", 0), L.offset("src_seed", 1)
    state = {"done": False}

    def edit(pairs):
        out = []
        for where, word in pairs:
            if where == low and not state["done"]:
                state["done"] = True
                where = high
            out.append((where, word))
        return out
    probe = case(16, [])
    at, _ = first_difference_of(probe, probe.but(seed=SEED >> 32 << 32))
    assert at is not None and at <= 3, at
    sim, memory, backend = await begin(dut, wrap=lambda s: host_sim.Filtered(s, edit))
    lib = AsyncHost(backend)
    await lib.open()
    await lib.reset()
    await expect_mismatch(test, "src_seed's lower word written at its upper word", lib, case(at + 4, []), at)
    assert state["done"]

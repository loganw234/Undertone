"""What the kernel's benches share: a host on the AXI4-Lite port, a run of the kernel, and the holds.

The kernel (rtl/krnl/undertone_krnl.sv) is driven ONLY as a host would drive
it: through its AXI4-Lite slave, by cocotbext-axi's AxiLiteMaster, a third
party's model of that protocol; and through memory, by `krnl_mem.Memory` (or,
in one test, cocotbext-axi's AxiRamWrite). Nothing here reads a signal inside
the top.

A RUN (`run_case`): the core loaded and started through the port; the source
handed the model's own noise table and seed, and the injector the schedule's
truth records (before the start, or some while the run goes); the kernel's
three arguments; `krn_start`; then `krn_status` polled until `done`, every few
clocks from the start write's answer on, with a bound in clocks. The writes
that load a block are the round 2 helpers' own pure functions
(`core_host.shape_pairs`, `stream_pairs`, `seam_host.table_writes`,
`truth_writes`), imported, not changed.

THE HOLDS (`hold_run`), each through `harness.hold`, so each leaves evidence:
  memory       slots 0 to N-1 read back, N being krn_frames: what the kernel was
               asked for, not what was read. Against the model's records
  as written   the beats in the order the memory took them, against the same
               records: a record written twice, or one too many, shows here
               even when memory holds the right bytes
and by assertion: every slot's padding is zero; beat i went to base + i slots;
the slots past N and the margin before the base still hold the pattern; the
memory saw no fault of protocol; krn_records is N; no refusal in the kernel or
any block; and WHEN DONE WAS FIRST READ, EVERY BURST THE MEMORY TOOK HAD BEEN
ANSWERED.

WHAT THIS CANNOT SEE, each a stated limit of docs/rtl/krnl.md:
  - the table, the schedule and the blob loaded are the ones the model is run
    on: one wrong in both alike is not seen;
  - `done` is read by polling, every POLL_GAP clocks: a done that rises and
    falls between two reads is not seen;
  - the records are counted twice in the stage's total: once from memory and
    once as written.
"""
import logging

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotbext.axi import AxiLiteBus, AxiLiteMaster

from spec import constants as C
from model import weights

import harness
import core_host
import seam_host as seam
import source_bus
import krnl_mem

WORD_BITS = C.BUS["word_bits"]
WORD_BYTES = WORD_BITS // 8
WORD_MASK = (1 << WORD_BITS) - 1
SLOT = C.MEMORY_SLOT_BYTES
RECORD_BYTES = harness.RECORD_BYTES
NAME_OF = core_host.NAME_OF
POLL_GAP = 12               # clocks between two reads of krn_status
DRAIN = 128                 # the kernel's clocks after the source's last frame (rtl/krnl/undertone_krnl.sv)


def off(name, word=0):
    return C.REGISTERS[name][0] + word * WORD_BYTES


def code(name):
    return 0 if name is None else C.REFUSAL_CODES[name]


def bit(register, name):
    return C.REGISTER_BITS[register][name]


class Host:
    """The kernel's AXI4-Lite port, as a host would use it, and a clock count kept by the memory model."""

    def __init__(self, dut):
        self.dut = dut
        self.axil = AxiLiteMaster(AxiLiteBus.from_prefix(dut, "s_axi_control"), dut.ap_clk, dut.ap_rst_n,
                                  reset_active_level=False)
        for part in (self.axil.write_if, self.axil.read_if):     # a line a transaction is most of a run's time
            part.log.setLevel(logging.WARNING)

    async def write(self, at, value):
        await self.axil.write(at, (value & WORD_MASK).to_bytes(WORD_BYTES, "little"))

    async def write_bytes(self, at, data):
        await self.axil.write(at, data)

    async def write_many(self, pairs):
        for at, value in pairs:
            await self.write(at, value)

    async def read(self, at):
        return int.from_bytes((await self.axil.read(at, WORD_BYTES)).data, "little")

    async def get(self, name, word=0):
        return await self.read(off(name, word))

    async def wide(self, name):
        value = 0
        for word in range(C.REGISTERS[name][2]):
            value |= (await self.get(name, word)) << (WORD_BITS * word)
        return value

    async def put(self, name, value):
        for word in range(C.REGISTERS[name][2]):
            await self.write(off(name, word), value >> (WORD_BITS * word))

    async def status(self):
        word = await self.get("krn_status")
        return dict((n, (word >> b) & 1) for n, b in C.REGISTER_BITS["krn_status"].items())

    async def refusals(self):
        """The four refusal registers: the kernel's, the core's, the source's, the injector's."""
        return {"kernel": await self.get("krn_refusal"), "core": await self.get("refusal"),
                "source": await self.get("src_refusal"), "inject": await self.get("inj_refusal")}

    async def take(self, name):
        """A refusal register's number, and the register cleared."""
        seen = await self.get(name)
        await self.write(off(name), 0)
        return seen

    async def capabilities(self):
        caps = {}
        for name in C.REGISTERS:
            if name.startswith("cap_"):
                caps[name] = await self.get(name)
        return caps


async def begin(dut, memory=None, **mem):
    """A clock, the kernel held in reset, the memory model, the host; then the reset released.
    `memory` is a function of dut that makes the memory, or None for krnl_mem.Memory with `mem`."""
    Clock(dut.ap_clk, 10, unit="ns").start()
    dut.ap_rst_n.value = 0
    for name in ("bid", "bresp", "bvalid", "awready", "wready", "arready", "rid", "rresp", "rlast", "rvalid", "rdata"):
        getattr(dut, "m_axi_gmem_" + name).value = 0
    host = Host(dut)
    m = memory(dut) if memory is not None else krnl_mem.Memory(dut, **mem)
    for _ in range(6):
        await RisingEdge(dut.ap_clk)
    dut.ap_rst_n.value = 1
    for _ in range(2):
        await RisingEdge(dut.ap_clk)
    return host, m


async def again(host, mem, base, size, **mem_kw):
    """Another run in the same test: krn_reset, and the memory renewed at another base."""
    await host.write(off("krn_reset"), 1)
    mem.renew(base, size, **mem_kw)


# ------------------------------------------------------------------ loading the chain

async def load_core(host, blob, epoch=0):
    """The core's shape, `configure`, the weight words, `start`; then no refusal and the core running."""
    config = weights.unpack(blob)
    words = core_host.words_of(config)
    await host.write_many(core_host.shape_pairs(config) + [(off("configure"), len(words))]
                          + core_host.stream_pairs(words) + [(off("start"), epoch)])
    refused = await host.take("refusal")
    assert refused == 0, "the core refused its load: %s" % NAME_OF.get(refused, refused)
    state = await host.get("status")
    assert (state >> C.REGISTER_BITS["status"]["running"]) & 1, "after its load the core does not run: 0x%X" % state
    return config


async def write_shadow(host, blob):
    words = core_host.words_of(weights.unpack(blob))
    await host.write_many([(off("shadow_begin"), len(words))] + core_host.stream_pairs(words))


async def commit(host, at):
    await host.write_many(core_host.commit_pairs(at))


async def load_chain(host, case, truth=None):
    """The source's table and seed, and the injector's truth records (the schedule's, or `truth`)."""
    pairs = seam.table_writes(case.noise().table)
    for record in (case.schedule if truth is None else truth):
        pairs += seam.truth_writes(record)
    pairs += source_bus.words_of("src_seed", case.seed)
    await host.write_many(pairs)


async def arguments(host, base, size, frames):
    await host.put("krn_buffer", base)
    await host.put("krn_size", size)
    await host.put("krn_frames", frames)


def bound(case, extra=0):
    """Clocks a run may take: every frame of the source, the chain's latency, the drain, and room."""
    return 2 * (seam.period(case.profile) * (case.frames + 2) + 64 + DRAIN) + 2000 + extra


async def wait_done(host, mem, clocks):
    """Poll krn_status until `done`. Returns (the status, the memory's clock when done was first read, and
    whether every burst the memory had taken was answered by then). A bench never waits without a bound."""
    start = mem.clock
    while True:
        state = await host.status()
        if state["done"]:
            answered = len(mem.answers) == len(mem.bursts) and not mem._b
            return state, mem.clock, answered
        assert mem.clock - start < clocks, "after %d clocks the kernel has not said done: %r" % (mem.clock - start, state)
        target = mem.clock + POLL_GAP
        while mem.clock < target:
            await RisingEdge(host.dut.ap_clk)


async def run_case(host, mem, case, base, size=None, truth=None, during=None, extra=0, expect_done=True):
    """Load the chain, set the arguments, start, and wait for done. Returns a dict of what was read."""
    await load_core(host, case.blob, case.epoch)
    await load_chain(host, case, truth)
    await arguments(host, base, case.frames * SLOT if size is None else size, case.frames)
    await host.write(off("krn_start"), 1)
    started = await host.status()
    task = cocotb.start_soon(during(host, mem)) if during is not None else None
    state, done_at, answered = await wait_done(host, mem, bound(case, extra))
    if task is not None:
        await task
    out = {"started": started, "status": state, "done_at": done_at, "answered_at_done": answered,
           "records": await host.wide("krn_records"), "peak": await host.get("krn_queue_peak")}
    out.update(await host.refusals())
    return out


# ------------------------------------------------------------------ the holds

def words(records):
    return [harness.record_word(r) for r in records]


def memory_words(mem, base, n):
    return [int.from_bytes(mem.read(base + i * SLOT, RECORD_BYTES), "little") for i in range(n)]


def hold_memory(test, label, mem, base, expected):
    """THE IDENTITY: slots 0 to N-1 against the model's records."""
    return seam.hold_records(test, label + ": memory", memory_words(mem, base, len(expected)), words(expected), None)


def hold_written(test, label, mem, expected):
    """The beats in the order the memory took them, against the same records."""
    return seam.hold_records(test, label + ": as written", mem.written(), words(expected), None)


def check_memory(mem, base, n):
    """Padding zero, beat i at base + i slots, the pattern untouched outside the n slots, no protocol fault."""
    assert not mem.faults, "the memory model saw faults of protocol: %s" % mem.faults[:5]
    for i in range(n):
        pad = mem.read(base + i * SLOT + RECORD_BYTES, SLOT - RECORD_BYTES)
        assert pad == bytes(SLOT - RECORD_BYTES), "slot %d's padding is %s, not zeros" % (i, pad.hex())
    for i, (_clock, at, _data) in enumerate(mem.beats):
        assert at == base + i * SLOT, "beat %d went to 0x%X where base + %d slots is 0x%X" % (i, at, i, base + i * SLOT)
    before = mem.read(mem.lo, base - mem.lo)
    after = mem.read(base + n * SLOT, mem.hi - (base + n * SLOT))
    pattern = krnl_mem.PATTERN
    assert before == bytes([pattern]) * len(before), "a byte before the buffer's base was written"
    assert after == bytes([pattern]) * len(after), "a byte past the run's %d slots was written" % n


def check_quiet(out, n):
    """A run no one refused: done, n records answered, every refusal register 0, done read only after
    every burst was answered."""
    assert out["answered_at_done"], "done was read at clock %d with a burst the memory had taken not yet answered" \
        % out["done_at"]
    assert out["started"]["running"] == 1, "the start was not taken: %r, %s" % (out["started"], refusal_names(out))
    assert out["status"]["done"] == 1 and out["status"]["running"] == 0, out["status"]
    assert all(out[k] == 0 for k in ("kernel", "core", "source", "inject")), "a refusal: %s" % refusal_names(out)
    assert out["records"] == n, "krn_records reads %d where the run was %d" % (out["records"], n)


def refusal_names(out):
    return dict((k, NAME_OF.get(out[k], out[k])) for k in ("kernel", "core", "source", "inject"))


async def hold_run(test, label, host, mem, case, base, expected=None, **kw):
    """A run no one refuses, held whole. Returns the RTL's digest of the memory's records."""
    if expected is None:
        expected, _truth = seam.model_records(case)
    assert len(expected) == case.frames
    out = await run_case(host, mem, case, base, **kw)
    _n, _model, rtl = hold_memory(test, label, mem, base, expected)
    hold_written(test, label, mem, expected)
    check_memory(mem, base, case.frames)
    check_quiet(out, case.frames)
    return rtl


# ------------------------------------------------------------------ what the two large tops share

E0 = C.PULSE_IDS["e0"]
PULSE = C.PULSES["e0"]
L = len(PULSE)


def rec(index, num=1, den=1, pulse_id=E0):
    return {"index": index, "pulse_id": pulse_id, "amplitude_num": num, "amplitude_den": den}


GAINS = {"s16x1": (1,), "s24x3": (3, -2, 1)}
OTHER_GAINS = {"s16x1": (-1,), "s24x3": (1, 3, -2)}
SIGMA_E0 = {"s16x1": (50, 1), "s24x3": (97, 2)}      # the seam's sigmas: a table of 459 entries under s16x1
SIGMA_SMALL = {"s16x1": (6, 1), "s24x3": (13, 2)}    # a short table: the table's writes are most of a load


def e0_case(profile, frames, seed, sigma, schedule, epoch=3):
    """Stage E0's shape: the reference pulse's matched filter."""
    blob = weights.matched_filter(profile, PULSE, GAINS[profile])
    return seam.Case(profile, seed, sigma, frames, schedule, blob, epoch)


async def identity_e0(dut, test, profile, frames, seed, sigma, schedule, swap_at=None):
    """E0's shape through the kernel: slots across a 4 KB page, random holds of every channel, late answers,
    the last answer held 200 clocks; with `swap_at`, other gains written to the shadow while the run goes
    and committed at that index."""
    this = e0_case(profile, frames, seed, sigma, schedule)
    base = 0x20000 - 7 * SLOT
    host, mem = await begin(dut, base=base, size=this.frames * SLOT, seed=seed, stall=0.05, stall_len=60,
                            answer_delay=20)
    mem.late_beat, mem.late_clocks = this.frames - 1, 200
    expected, during, label = None, None, "E0's shape, random holds"
    if swap_at is not None:
        other = weights.matched_filter(profile, PULSE, OTHER_GAINS[profile])
        unswapped, _ = seam.model_records(this)
        expected, _ = seam.model_records(this, [("write_shadow", other), ("commit", swap_at)])
        assert seam.first_difference(unswapped, expected) == swap_at, "the swap does not show at its index"
        label += ", other gains from index %d" % swap_at

        async def during(host_, mem_):
            await write_shadow(host_, other)
            await commit(host_, swap_at)
            refused = await host_.get("refusal")
            assert refused == 0, "the shadow write or the commit was refused: %s" % NAME_OF.get(refused, refused)
            assert len(mem_.beats) < swap_at - 8, "the commit landed near its own index: %d records out" % len(mem_.beats)

    await hold_run(test, label, host, mem, this, base, expected=expected, during=during)
    return host, mem


# ------------------------------------------------------------------ the capability registers against the core's refusals

SHAPE_SCALARS = core_host.SHAPE_SCALARS


async def try_configure(host, shape):
    """After krn_reset: the shape and `configure` with its own count. Returns the core's refusal, cleared."""
    pairs = [(off(n), shape[n]) for n in SHAPE_SCALARS]
    pairs += [(off("shape_masks", k), mask) for k, mask in enumerate(shape["masks"])]
    pairs.append((off("configure"), core_host.words_in(shape)))
    await host.write(off("krn_reset"), 1)
    await host.write_many(pairs)
    return await host.take("refusal")


async def capabilities_are_accepted(host, profile):
    """For each bound the build advertises: a shape at the advertised value is taken, and one past it is
    refused by that bound's name. Returns the capabilities read."""
    caps = await host.capabilities()
    prof = C.PROFILES[profile]
    assert caps["cap_sample_bits"] == prof["sample_bits"] and caps["cap_channels"] == prof["channels"], caps
    plain = core_host.plain_shape
    cases = [
        ("filters", plain(profile, shape_filters=caps["cap_filters"]),
         plain(profile, shape_filters=caps["cap_filters"] + 1), "SHAPE_FILTERS"),
        ("taps", plain(profile, shape_taps=caps["cap_taps"]), plain(profile, shape_taps=caps["cap_taps"] + 1), "SHAPE_TAPS"),
        ("pool", plain(profile, shape_pool=caps["cap_pool"]), plain(profile, shape_pool=caps["cap_pool"] + 1), "SHAPE_POOL"),
        ("score shift", plain(profile, shape_score_shift=caps["cap_score_shift"]),
         plain(profile, shape_score_shift=caps["cap_score_shift"] + 1), "SHAPE_SHIFT"),
        ("hidden units", plain(profile, shape_hidden=caps["cap_hidden"]),
         plain(profile, shape_hidden=caps["cap_hidden"] + 1), "SHAPE_HIDDEN"),
        ("hidden shift", plain(profile, shape_hidden=1, shape_hidden_shift=caps["cap_hidden_shift"]),
         plain(profile, shape_hidden=1, shape_hidden_shift=caps["cap_hidden_shift"] + 1), "SHAPE_HIDDEN_SHIFT"),
    ]
    if prof["channels"] > 1:            # under one channel a filter is one row (docs/rtl/core.md, limit 12)
        at = core_host.masks_for_rows(prof["channels"], caps["cap_rows"])
        past = core_host.masks_for_rows(prof["channels"], caps["cap_rows"] + 1)
        cases.append(("rows", plain(profile, shape_filters=len(at), masks=at),
                      plain(profile, shape_filters=len(past), masks=past), "SHAPE_ROWS"))
    for code_ in range(8):
        advertised = (caps["cap_rectifiers"] >> code_) & 1
        cases.append(("rectifier %d" % code_, plain(profile, shape_rectifier=code_) if advertised else None,
                      None if advertised else plain(profile, shape_rectifier=code_), "SHAPE_RECTIFIER"))
    for what, inside, past, name in cases:
        if inside is not None:
            got = await try_configure(host, inside)
            assert got == 0, "a shape at the advertised %s was refused %s" % (what, NAME_OF.get(got, got))
        if past is not None:
            got = await try_configure(host, past)
            assert got == code(name), "a shape past the advertised %s was refused %s, not %s" % (
                what, NAME_OF.get(got, got), name)
    await host.write(off("krn_reset"), 1)
    return caps

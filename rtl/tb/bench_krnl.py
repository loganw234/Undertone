"""The kernel's bench on the top that is packaged: rtl/krnl/undertone_krnl.sv at the first build's maxima.

Its parameters' defaults ARE the first build's: 4 filters, 4 rows, 128 taps,
12 hidden units, the definition's other maxima, a queue of 512. The runner
sets SAMPLE_BITS and CHANNELS for each profile; nothing else is changed. The
kernel is driven only through its AXI4-Lite port and its memory
(rtl/tb/krnl_host.py, rtl/tb/krnl_mem.py).

WHAT EACH TEST HOLDS
  identity_e0                stage E0's shape, slots across a 4 KB page, random holds of every channel,
                             late answers, the last held 200 clocks, and other gains written to the
                             shadow while the run goes and committed at a named index: every record the
                             model's, from memory and as written; done only after every answer. Under
                             s16x1, the first build's profile, at the seam's sigma (a table of 459
                             entries) with two pulses that touch; under s24x3 at a small sigma, one pulse
  identity_long_bursts       two long holds of the memory, so that bursts of 16 and of 9 to 15 beats
                             come by construction, one cut at a 4 KB page, under both profiles
  identity_hidden            a seeded shape at the build's taps and rows with all twelve hidden units
  capabilities_are_accepted  each bound the build advertises: a shape at it taken, one past it refused by
                             that bound's name (the capability-bits gate, in simulation)
  identity_on_axi_ram        a run against cocotbext-axi's AxiRamWrite, a third party's write path, under
                             its own pause generators: the records read back are the model's, and done
                             read only after every answer, by a passive look at the bus

WHAT THIS BENCH DOES NOT SEE, each a stated limit of docs/rtl/krnl.md: the queue's overflow at its
depth of 512 (bench_krnl_small holds the overflow at a depth of 8); a stream longer than 129 frames;
a refusal in the chain (bench_krnl_small's).
"""
import logging
import os
import random

import cocotb
from cocotb.triggers import RisingEdge
from cocotbext.axi import AxiRamWrite, AxiWriteBus

from spec import constants as C

import seam_host as seam
import krnl_host as k

PROFILE = os.environ["UNDERTONE_PROFILE"]
SEED = 2026112470
SLOT = C.MEMORY_SLOT_BYTES

# The sizes, set from the kernel's measured rate (docs/rtl/krnl.md, the register).
E0 = {"s16x1": (129, k.SIGMA_E0["s16x1"], [k.rec(0, 3, 2), k.rec(k.L, -7, 4)], 80),
      "s24x3": (70, k.SIGMA_SMALL["s24x3"], [k.rec(0, 3, 2)], 50)}[PROFILE]
HIDDEN_FRAMES = 41
RAM_FRAMES = 40


@cocotb.test()
async def identity_e0(dut):
    frames, sigma, schedule, swap_at = E0
    await k.identity_e0(dut, "identity_e0", PROFILE, frames, SEED, sigma, schedule, swap_at)


LONG_FRAMES = 61
PAGE_AT = 21                # the slot that begins a 4 KB page


@cocotb.test()
async def identity_long_bursts(dut):
    """Bursts of 9 to 16 beats, by construction. The memory holds its address and data channels while
    forty records queue, from the third, and again while twelve do, from the forty-sixth. The kernel's
    queue of 512 holds them all, so on each release the bursts are as long as the rule allows: 16 from
    slot 2, cut to 3 at the page that begins at slot 21, 16 from it, then the rest; and about twelve at
    once after the second hold. A burst of 9 to 15 beats and one of 16 are both required."""
    test = "identity_long_bursts"
    this = k.e0_case(PROFILE, LONG_FRAMES, SEED + 3, k.SIGMA_SMALL[PROFILE], [])
    base = 0x50000 - PAGE_AT * SLOT
    host, mem = await k.begin(dut, base=base, size=this.frames * SLOT, seed=SEED + 3)
    mem.aw_waits_for_w = True
    period = seam.period(PROFILE)

    async def holds(host_, mem_):
        for after, records in ((2, 40), (46, 12)):
            await k.until_beats(host_, mem_, after, period * (after + 50) + 4000)
            mem_.hold_aw = mem_.hold_w = True
            await k.clocks(host_, period * records)
            mem_.hold_aw = mem_.hold_w = False

    await k.hold_run(test, "bursts of 16 and of 9 to 15 beats, one cut at a page", host, mem, this, base,
                     during=holds)
    lengths = [b[2] for b in mem.bursts]
    assert 16 in lengths and any(9 <= n <= 15 for n in lengths), "the bursts' lengths: %r" % lengths
    assert any((b[1] % 4096) + b[2] * SLOT == 4096 and b[2] > 1 for b in mem.bursts), \
        "no burst of more than one beat ended at the page's edge: %r" % [(hex(b[1]), b[2]) for b in mem.bursts]


@cocotb.test()
async def identity_hidden(dut):
    test = "identity_hidden"
    base = 0x40000
    host, mem = await k.begin(dut, base=base, size=HIDDEN_FRAMES * SLOT, seed=SEED + 1, stall=0.05, stall_len=30,
                              answer_delay=10)
    caps = await host.capabilities()
    channels = C.PROFILES[PROFILE]["channels"]
    rng = random.Random(SEED + 1)
    sets = [[0]] * caps["cap_rows"] if channels == 1 else [[0, 1, 2]] + [[1]] * (caps["cap_rows"] - 3)
    assert len(sets) <= caps["cap_filters"] and sum(len(s) for s in sets) == caps["cap_rows"]
    blob = k.core_host.blob_of(PROFILE, sets, caps["cap_taps"], rng, C.RECTIFIERS["abs"], 3, 20,
                               hidden=caps["cap_hidden"], hidden_shift=22, between=C.RECTIFIERS["abs"])
    this = seam.Case(PROFILE, SEED + 1, k.SIGMA_SMALL[PROFILE], HIDDEN_FRAMES, [], blob, 11)
    await k.hold_run(test, "every row at every tap, twelve hidden units", host, mem, this, base)


@cocotb.test()
async def capabilities_are_accepted(dut):
    host, _mem = await k.begin(dut, base=0x1000, size=SLOT)
    caps = await k.capabilities_are_accepted(host, PROFILE)
    assert (caps["cap_filters"], caps["cap_rows"], caps["cap_taps"], caps["cap_hidden"]) == (4, 4, 128, 12), \
        "the packaged top does not advertise the first build's maxima: %r" % caps
    assert caps["cap_record_queue"] == 512, caps


# ------------------------------------------------------------------ the cross-check on a third party's memory

class RamMemory:
    """cocotbext-axi's AxiRamWrite on m_axi_gmem, under its own pause generators, with a clock count and a
    passive look at the bus: each address taken (awvalid and awready at an edge) is a burst, and each answer
    taken (bvalid and bready) an answer, so that the check that done was read only after every answer holds
    here too."""

    def __init__(self, dut, seed):
        self.ram = AxiRamWrite(AxiWriteBus.from_prefix(dut, "m_axi_gmem"), dut.ap_clk, dut.ap_rst_n,
                               reset_active_level=False, size=2 ** 20)
        self.ram.log.setLevel(logging.WARNING)
        rng = random.Random(seed)

        def pauses(p):
            while True:
                yield rng.random() < p

        self.ram.aw_channel.set_pause_generator(pauses(0.3))
        self.ram.w_channel.set_pause_generator(pauses(0.3))
        self.ram.b_channel.set_pause_generator(pauses(0.3))
        self.clock, self.answers, self.bursts, self._b = 0, [], [], []
        self.dut, self.clk = dut, dut.ap_clk
        cocotb.start_soon(self._count())

    def _one(self, name):
        return str(getattr(self.dut, "m_axi_gmem_" + name).value) == "1"

    async def _count(self):
        while True:
            await RisingEdge(self.clk)
            self.clock += 1
            if self._one("awvalid") and self._one("awready"):
                self.bursts.append((self.clock, getattr(self.dut, "m_axi_gmem_awaddr").value.to_unsigned(),
                                    getattr(self.dut, "m_axi_gmem_awlen").value.to_unsigned() + 1))
            if self._one("bvalid") and self._one("bready"):
                self.answers.append(self.clock)

    def read(self, address, length):
        return self.ram.read(address, length)


@cocotb.test()
async def identity_on_axi_ram(dut):
    test = "identity_on_axi_ram"
    this = k.e0_case(PROFILE, RAM_FRAMES, SEED + 2, k.SIGMA_SMALL[PROFILE], [])
    base = 0x30000 - 9 * SLOT
    host, mem = await k.begin(dut, memory=lambda d: RamMemory(d, SEED + 2))
    expected, _ = seam.model_records(this)
    out = await k.run_case(host, mem, this, base)
    k.hold_memory(test, "E0's shape on AxiRamWrite", mem, base, expected)
    k.check_quiet(out, this.frames)
    assert mem.bursts and len(mem.answers) == len(mem.bursts), "bursts %d, answers %d" % (len(mem.bursts), len(mem.answers))

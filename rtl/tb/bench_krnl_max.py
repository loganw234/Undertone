"""The kernel's bench at the definition's maxima (rtl/krnl/krnl_max.sv): rtl/krnl/undertone_krnl.sv with
every maximum of the core the definition's own, and the first build's queue of 512.

WHAT EACH TEST HOLDS
  identity_e0                stage E0's shape at a small sigma, one pulse, slots across a 4 KB page,
                             random holds of every channel and late answers: every record the model's,
                             from memory and as written; done only after every answer
  capabilities_are_accepted  the capability-bits gate at the definition's maxima (krnl_host's)
  the_definitions_maxima     this top advertises the definition's maxima

WHAT THIS BENCH DOES NOT SEE, each a stated limit of docs/rtl/krnl.md: a shape of the definition's
largest size run through the kernel (the core's own bench, bench_core_max, runs it); a stream of more
than 67 frames at these maxima.
"""
import os

import cocotb

from spec import constants as C

import krnl_host as k

PROFILE = os.environ["UNDERTONE_PROFILE"]
SEED = 2026112480
E0_FRAMES = 67              # set from the kernel's measured rate (docs/rtl/krnl.md, the register)


@cocotb.test()
async def identity_e0(dut):
    await k.identity_e0(dut, "identity_e0", PROFILE, E0_FRAMES, SEED, k.SIGMA_SMALL[PROFILE], [k.rec(1, 5, 3)])


@cocotb.test()
async def capabilities_are_accepted(dut):
    """The capability-bits gate (krnl_host.capabilities_are_accepted), and nothing else."""
    host, _mem = await k.begin(dut, base=0x1000, size=C.MEMORY_SLOT_BYTES)
    await k.capabilities_are_accepted(host, PROFILE)


@cocotb.test()
async def the_definitions_maxima(dut):
    """This top advertises the definition's maxima."""
    host, _mem = await k.begin(dut, base=0x1000, size=C.MEMORY_SLOT_BYTES)
    caps = await host.capabilities()
    want = (C.MAX_FILTERS, C.MAX_ROWS, C.MAX_TAPS, C.MAX_HIDDEN, C.MAX_POOL, C.MAX_SCORE_SHIFT, C.MAX_HIDDEN_SHIFT)
    have = tuple(caps[n] for n in ("cap_filters", "cap_rows", "cap_taps", "cap_hidden", "cap_pool", "cap_score_shift",
                                   "cap_hidden_shift"))
    assert have == want, "this top does not advertise the definition's maxima: %r" % (caps,)

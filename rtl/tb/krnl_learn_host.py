"""What the kernel's learner bench needs beyond krnl_host and learn_host: an operation placed in its window,
held to the model's outcome, through the kernel's AXI4-Lite port alone. Parcel KRNL-L, round 5;
docs/rtl/krnl-learn.md.

The kernel (rtl/krnl/undertone_krnl.sv, with rtl/learn/learn.sv and learn_port.sv inside it) is driven ONLY
as a host would drive it: its AXI4-Lite slave and its memory (krnl_host). Nothing here reads a signal inside
the top.

AN OPERATION AND ITS WINDOW. A host cannot put a register write at a chosen clock. So each operation of a
script carries a window of next indexes inside which the model's outcome, its records and its counters are
the same, and the model's script names it at one index inside that window (`Op`). The bench reads the core's
`next_index` through the port until it is at the window's first index, makes the operation's writes, and
reads `next_index` again: the writes landed between the two reads, so the second read at most the window's
last is what makes the comparison sound. An operation outside its window FAILS the test by name; it is
never compared.

AFTER EACH OPERATION: `lrn_refusal` and the core's `refusal` are read and held to what this design latches
for the model's outcome (`learn_host.expected_codes`), `krn_status` is read and its refused bit held to 0
(a learner's refusal is never the kernel's), and both refusal registers are cleared.

WHAT THIS CANNOT SEE, each a stated limit of docs/rtl/krnl-learn.md:
  - an outcome that differs only at a window's edge: the window is where the model's outcome is the same;
  - the clock an operation lands at, inside its window.
"""
from cocotb.triggers import ClockCycles

from spec import constants as C
from model import inject, run as R, weights

import learn_host as lh
import krnl_host as kh

WORD_BITS = C.BUS["word_bits"]
WORD_MASK = (1 << WORD_BITS) - 1
F = C.LEARN_UPDATE_FRAMES
N = C.LEARN_COUNT_BITS
STATUS = C.REGISTER_BITS["lrn_status"]
KRN_STATUS = C.REGISTER_BITS["krn_status"]


class Op:
    """One host operation: the model's index for it, the operation, its argument, and its window."""

    def __init__(self, index, op, argument, first, last):
        assert first <= index <= last, "the model's index %d is outside its own window [%d, %d]" % (index, first, last)
        self.index, self.op, self.argument, self.first, self.last = index, op, argument, first, last


def script_of(ops):
    """The model's script: each operation at its index, in order."""
    out = {}
    for o in ops:
        out.setdefault(o.index, []).append((o.op, o.argument))
    return out


def model(case, ops):
    """`model.run.learning` on the case: (records, truth, outcomes, learner)."""
    return R.learning(case.noise(), case.schedule, case.frames, case.blob, script_of(ops), F, N, case.epoch)


def model_without(case, ops, dropped):
    """The model's learner on the same frames and script, with the truth records at `dropped` taken from what
    the LEARNER is handed (the injector still adds them): what a learner that skipped those records would make."""
    profile = weights.unpack(case.blob)["profile"]
    injected, truth = inject.inject(profile, case.noise(), case.schedule, case.frames)
    indexes = [t["index"] for t in truth if t["index"] not in dropped]
    learner, records, _outcomes = lh.model_run(case.blob, indexes, injected, script_of(ops), F, N, case.epoch)
    return learner, records


async def next_index(host):
    """The core's next index, its two words of one moment (a read of the lower holds the upper)."""
    low = await host.get("next_index", 0)
    high = await host.get("next_index", 1)
    return low | (high << WORD_BITS)


async def until(host, mem, index, period, clocks_most, what):
    """Return the next index read once it is at least `index`; never wait more than `clocks_most` clocks."""
    start = mem.clock
    while True:
        n = await next_index(host)
        if n >= index:
            return n
        assert mem.clock - start < clocks_most, "after %d clocks the core's next index is %d, not %d (%s)" % (
            mem.clock - start, n, index, what)
        await ClockCycles(host.dut.ap_clk, max(period, (index - n) * period // 2))


class Held:
    """Register words that differ from the model's, collected; raised by `close` after the records are held."""

    def __init__(self):
        self.checks = lh.Checks()

    def same(self, what, have, want):
        self.checks.same(what, have, want)

    def close(self):
        self.checks.close()


async def make(host, mem, held, latch, label, o, name, period, clocks_most):
    """One operation in its window, then its two refusal registers held to the model's outcome `name`, the
    kernel's refused bit held to 0, and both refusal registers cleared."""
    before = await until(host, mem, o.first, period, clocks_most, "%s for %s at %d" % (label, o.op, o.index))
    assert before <= o.last, "%s: %s(%s) could not begin inside its window [%d, %d]: the next index is %d" % (
        label, o.op, "a blob" if o.op == "write_shadow" else o.argument, o.first, o.last, before)
    writes = lh.op_writes(o.op, o.argument)
    await host.write_many(writes)
    after = await next_index(host)
    assert after <= o.last, "%s: %s(%s) landed past its window [%d, %d]: the next index read after it is %d" % (
        label, o.op, "a blob" if o.op == "write_shadow" else o.argument, o.first, o.last, after)
    latch.finishes_to(o.index)
    lrn_want, count, core_want = lh.expected_codes(o.op, name, len(writes) - 1)
    latched = latch.latched + ([lh.NAME_OF[lrn_want]] * count if lrn_want else [])
    lrn = await host.get("lrn_refusal")
    core = await host.get("refusal")
    krn = await host.status()
    await host.write_many([(kh.off("lrn_refusal"), 0), (kh.off("refusal"), 0)])
    what = "%s: after %s(%s) in [%d, %d], the model's outcome %s" % (
        label, o.op, "a blob" if o.op == "write_shadow" else o.argument, o.first, o.last, name)
    held.same(what + ": lrn_refusal", lrn, lh.code(latched[0]) if latched else 0)
    held.same(what + ": refusal", core, core_want)
    held.same(what + ": krn_status.refused", krn["refused"], 0)
    latch.latched = []


async def counters(host):
    out = {}
    for name in lh.COUNTERS:
        out[name] = await host.wide(name)
    return out


async def lrn_status(host):
    word = await host.get("lrn_status")
    return dict((name, (word >> bit) & 1) for name, bit in STATUS.items())


async def hold_learner(host, held, learner, latched, label):
    """The eight counts and lrn_status against the model's learner as it stands; `latched` the names
    lrn_refusal has latched since the bench last cleared it."""
    have = await counters(host)
    for name, want in learner.counters().items():
        held.same("%s: %s" % (label, name), have[name], want)
    st = await lrn_status(host)
    for name, want in learner.status().items():
        held.same("%s: lrn_status.%s" % (label, name), st[name], want)
    held.same("%s: lrn_status.refused" % label, st["refused"], int(len(latched) > 0))
    held.same("%s: lrn_status.refused_again" % label, st["refused_again"], int(len(latched) > 1))
    held.same("%s: lrn_refusal" % label, await host.get("lrn_refusal"), lh.code(latched[0]) if latched else 0)


def outcomes_named(outcomes, ops):
    """The model's outcome of each operation, in the order of `ops` (each index's list in order)."""
    by = {}
    for index, op, _argument, name in outcomes:
        by.setdefault(index, []).append((op, name))
    out = []
    for o in ops:
        op, name = by[o.index].pop(0)
        assert op == o.op, "the model's outcome at %d is of %s, not %s" % (o.index, op, o.op)
        out.append(name)
    return out


def collect(held, what, check, *args):
    """Run one of krnl_host's asserting checks, and collect its failure in `held` in place of raising it."""
    try:
        check(*args)
    except AssertionError as e:
        held.checks.wrong.append("%s: %s" % (what, e))


async def learning_run(test, label, host, mem, case, base, ops, period, extra=None, close=True):
    """One run of the kernel with the learner, held whole against `model.run.learning`: every slot of memory
    and every beat as written, the memory's checks, the kernel quiet (krn_records = krn_frames, no refusal of
    the kernel's, the core's, the source's or the injector's, done only after every answer), each operation's
    refusals, and at the end the eight counts and lrn_status. `extra` is a coroutine function called with the
    host during the run, beside the operations, for writes the model does not see; it returns the names it
    latched in lrn_refusal.

    The records are held first and raise at once, through the harness. Everything else is collected, and
    raised by `held.close()`: here, or with `close` False by the caller, after a later run's records are held,
    so that a fault the later run's records show is reported as the harness's mismatch there.
    Returns (the model's learner, its records, the run's out, the collected checks)."""
    records, _truth, outcomes, learner = model(case, ops)
    names = outcomes_named(outcomes, ops)
    held = Held()
    latch = lh.Latch(learner)
    extra_latched = []
    bound = kh.bound(case)

    async def during(host_, mem_):
        for o, name in zip(ops, names):
            await make(host_, mem_, held, latch, label, o, name, period, bound)
        if extra is not None:
            extra_latched.extend(await extra(host_))

    out = await kh.run_case(host, mem, case, base, during=during)
    latch.finishes_to(case.frames)
    kh.hold_memory(test, label, mem, base, records)
    kh.hold_written(test, label, mem, records)
    collect(held, label + ": memory", kh.check_memory, mem, base, case.frames)
    collect(held, label + ": the kernel at done", kh.check_quiet, out, case.frames)
    held.same(label + ": krn_status.refused at done", out["status"]["refused"], 0)
    await hold_learner(host, held, learner, latch.latched + extra_latched, label + ", at the end")
    if close:
        held.close()
    return learner, records, out, held

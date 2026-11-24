"""The host library's simulated backend: the seam's seven operations on KRNL's kernel in the image.

The library (host/) is above the seam and runs unchanged here, through its
coroutine driver (`host.drive.AsyncHost`). This file is the backend: each
operation becomes what a host's would on the card, in simulation:

    Read, Write    one AXI4-Lite transaction on the kernel's control port, through KRNL's `krnl_host.Host`,
                   whose master is cocotbext-axi's AxiLiteMaster; a write's answer must be OKAY
    WriteMany      one transaction after another, in order
    Pause          `pause` clocks
    Allocate       a region of KRNL's memory model (`krnl_mem.Memory.renew`) at BASE, page-aligned and not 0
    Fill           the bytes into the memory model's store, as a sync to the device would put them
    Fetch          the bytes from the memory model's store, as a sync from the device would bring them

`now()` is the memory model's count of clocks.

EVERY WAIT HAS A BOUND IN CLOCKS: a transaction not answered within `bound`
clocks fails the test, saying which (cocotb's with_timeout); the library's own
`finish` bounds its polls.

WHAT IT DOES NOT DO: it holds one region at a time, so a second Allocate
replaces the first (the library allocates once a run); Fill and Fetch touch
the store directly, not through any bus, which is what a synchronised buffer
is to the kernel; it does not model XRT. KRNL's helpers are imported and not
changed.
"""
import cocotb
from cocotb.triggers import ClockCycles, with_timeout

try:
    from cocotb.triggers import SimTimeoutError
except ImportError:                                  # where cocotb 1.x kept it
    from cocotb.result import SimTimeoutError

from host.ops import Read, Write, WriteMany, Pause, Allocate, Fill, Fetch, Buffer

BASE = 0x20000          # the buffer's device address: page-aligned, and not 0 (lead.md 10:17: an ignored base must not pass)
MARGIN = 4096           # the memory model's region round the buffer, holding the pattern


class Sim:
    def __init__(self, dut, host, memory, pause=16, bound=2000, period_ns=10):
        self.dut, self.host, self.memory = dut, host, memory
        self.pause, self.bound, self.period_ns = pause, bound, period_ns
        self.allocated = 0
        self.writes = 0

    def now(self):
        return self.memory.clock

    async def _bounded(self, coroutine, what):
        try:
            return await with_timeout(cocotb.start_soon(coroutine), self.bound * self.period_ns, "ns")
        except SimTimeoutError:
            raise AssertionError("%s was not answered within %d clocks" % (what, self.bound))

    async def _write(self, where, word):
        answer = await self._bounded(self.host.axil.write(where, (word & 0xFFFFFFFF).to_bytes(4, "little")),
                                     "a write of 0x%03X" % where)
        if int(answer.resp) != 0:
            raise OSError("the write of 0x%03X was answered %r, not OKAY" % (where, answer.resp))
        self.writes += 1

    async def do(self, op):
        kind = type(op)
        if kind is Read:
            answer = await self._bounded(self.host.axil.read(op.offset, 4), "a read of 0x%03X" % op.offset)
            if int(answer.resp) != 0:
                raise OSError("the read of 0x%03X was answered %r, not OKAY" % (op.offset, answer.resp))
            return int.from_bytes(answer.data, "little")
        if kind is Write:
            await self._write(op.offset, op.word)
            return None
        if kind is WriteMany:
            for where, word in op.pairs:
                await self._write(where, word)
            return None
        if kind is Pause:
            await ClockCycles(self.dut.ap_clk, self.pause)
            return None
        if kind is Allocate:
            self.memory.renew(BASE, op.size, MARGIN)
            self.allocated += 1
            return Buffer(self.allocated, BASE, op.size)
        if kind is Fill:
            at = op.buffer.address + op.offset - self.memory.lo
            self.memory.mem[at:at + len(op.data)] = op.data
            return None
        if kind is Fetch:
            return self.memory.read(op.buffer.address + op.offset, op.size)
        raise TypeError("not an operation of the seam: %r" % (op,))


class Filtered:
    """A backend wrapped by a test, to plant a fault below the seam: `edit(pairs)` returns the pairs a write
    of them actually makes. Everything else passes through."""

    def __init__(self, inner, edit):
        self.inner, self.edit = inner, edit

    def now(self):
        return self.inner.now()

    async def do(self, op):
        if type(op) is Write:
            pairs = self.edit([(op.offset, op.word)])
            for where, word in pairs:
                await self.inner.do(Write(where, word))
            return None
        if type(op) is WriteMany:
            return await self.inner.do(WriteMany(tuple(self.edit(list(op.pairs)))))
        return await self.inner.do(op)


class Counting:
    """A backend that counts what reaches it that changes something below the seam."""

    def __init__(self, inner):
        self.inner, self.effects = inner, []

    def now(self):
        return self.inner.now()

    async def do(self, op):
        if type(op) in (Write, WriteMany, Allocate, Fill):
            self.effects.append(op)
        return await self.inner.do(op)


class Replay:
    """A CALL backend that answers each operation with what the simulated kernel answered, in order, and fails
    at the first operation that is not the one recorded: what `same_code_both_drivers` drives the call driver
    with."""

    def __init__(self, recorded, key):
        self.recorded, self.key, self.at = list(recorded), key, 0

    def now(self):
        return self.at

    def do(self, op):
        assert self.at < len(self.recorded), "the call driver made an operation more than the kernel run: %r" % (op,)
        want, result = self.recorded[self.at]
        assert self.key(op) == want, "operation %d: the call driver made %r where the coroutine driver made %r" % (
            self.at, self.key(op)[:3], want[:3])
        self.at += 1
        return result

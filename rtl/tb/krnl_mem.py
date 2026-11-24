"""The memory model for the kernel's benches: an AXI4 write slave on m_axi_gmem, written for this parcel.

One coroutine, one look a clock. At each rising edge it reads what the kernel
put on the bus before that edge and what it itself drove, takes each handshake,
and drives its readies and its answer for the next edge. What it does that the
benches need:

  - every beat is logged with its address and its clock, in the order taken,
    so a record written twice, or one too many, is seen even when memory holds
    the right bytes (`beats`);
  - the address, the data and the answer channels can each be held: at random
    from a seed (`stall`, a hold begun with that chance a clock and lasting 1
    to `stall_len` clocks), or until a bench says (`hold_aw`, `hold_w`,
    `hold_b`), which is how a stall longer than the kernel's queue is made;
  - `renew` gives a fresh region and fresh logs for another run in one test;
  - every answer can be delayed (`answer_delay`), and the answer to the burst
    holding a named beat held for longer (`late_beat`, `late_clocks`), which is
    how a done raised before its last answer is caught;
  - one burst can be answered SLVERR (`error_burst`);
  - the buffer and a margin round it start as a pattern (`PATTERN`), so a slot
    never written shows;
  - every burst is checked against what the kernel must do (`faults`): size of
    one slot, INCR, at most 16 beats, no 4 KB page crossed, every strobe set,
    WLAST exactly on the last beat, every beat inside the region.

WHAT IT DOES NOT DO, each a stated limit of docs/rtl/krnl.md: it takes a beat
of data only once the burst's address is taken (AXI allows data first; this
kernel never sends it so, and a kernel that did would stall here and fail by a
bound, not by a named fault); it holds one region of memory; it never reorders
answers; it is this parcel's own reading of AXI4, cross-checked once by
`identity_on_axi_ram` against cocotbext-axi's AxiRamWrite.
"""
import random

import cocotb
from cocotb.triggers import RisingEdge

from spec import constants as C

SLOT = C.MEMORY_SLOT_BYTES
PATTERN = 0xA5
PAGE = 4096
MAX_BEATS = 16


class Memory:
    def __init__(self, dut, base, size, margin=1024, seed=0, stall=0.0, stall_len=1, answer_delay=0, prefix="m_axi_gmem"):
        self.dut, self.p, self.clk = dut, prefix, dut.ap_clk
        self.rng = random.Random(seed)
        self.clock = 0
        self._drive = {"awready": 0, "wready": 0, "bvalid": 0}
        self._held = {"aw": 0, "w": 0, "b": 0}       # clocks left of a random hold on each channel
        self.renew(base, size, margin, stall, stall_len, answer_delay)
        self._sig("awready").value = 0
        self._sig("wready").value = 0
        self._sig("bvalid").value = 0
        self._sig("bresp").value = 0
        self._sig("bid").value = 0
        self.task = cocotb.start_soon(self._run())

    def renew(self, base, size, margin=1024, stall=0.0, stall_len=1, answer_delay=0):
        """A fresh region and fresh logs, for another run in the same test. Call it with nothing in flight."""
        self.lo, self.hi = base - margin, base + size + margin
        assert self.lo >= 0
        self.mem = bytearray([PATTERN]) * (self.hi - self.lo)
        self.stall, self.stall_len, self.answer_delay = stall, stall_len, answer_delay
        self.hold_aw = self.hold_w = self.hold_b = False
        self.late_beat, self.late_clocks = None, 0
        self.error_burst = None
        self.bursts = []        # (clock, address, beats)
        self.beats = []         # (clock, address, the 32 bytes)
        self.answers = []       # clock of each answer taken
        self.faults = []
        self._aw = []           # bursts whose address is taken: [address, beats, beats taken, burst number]
        self._b = []            # answers due: [clock due, resp]

    def _sig(self, name):
        return getattr(self.dut, "%s_%s" % (self.p, name))

    def _one(self, name):
        return str(self._sig(name).value) == "1"

    def read(self, address, length):
        assert self.lo <= address and address + length <= self.hi, "a read outside the model's region"
        return bytes(self.mem[address - self.lo:address - self.lo + length])

    def _stalled(self, channel):
        """A random hold: once begun (with probability `stall` a clock) it lasts 1 to `stall_len` clocks."""
        if self._held[channel] > 0:
            self._held[channel] -= 1
            return True
        if self.stall > 0 and self.rng.random() < self.stall:
            self._held[channel] = self.rng.randint(1, self.stall_len) - 1
            return True
        return False

    async def _run(self):
        while True:
            await RisingEdge(self.clk)
            self.clock += 1
            # ---- the handshakes at this edge ----
            if self._drive["awready"] and self._one("awvalid"):
                addr = self._sig("awaddr").value.to_unsigned()
                beats = self._sig("awlen").value.to_unsigned() + 1
                size = self._sig("awsize").value.to_unsigned()
                burst = self._sig("awburst").value.to_unsigned()
                n = len(self.bursts)
                self.bursts.append((self.clock, addr, beats))
                if (1 << size) != SLOT or burst != 1 or beats > MAX_BEATS:
                    self.faults.append("burst %d: size %d, type %d, %d beats" % (n, size, burst, beats))
                if addr % SLOT or (addr % PAGE) + beats * SLOT > PAGE:
                    self.faults.append("burst %d at 0x%X of %d beats is unaligned or crosses a 4 KB page" % (n, addr, beats))
                self._aw.append([addr, beats, 0, n])
            if self._drive["wready"] and self._one("wvalid"):
                head = self._aw[0]
                at = head[0] + head[2] * SLOT
                data = self._sig("wdata").value.to_unsigned().to_bytes(SLOT, "little")
                strb = self._sig("wstrb").value.to_unsigned()
                last = self._one("wlast")
                if strb != (1 << SLOT) - 1:
                    self.faults.append("beat %d: strobes 0x%X" % (len(self.beats), strb))
                if last != (head[2] == head[1] - 1):
                    self.faults.append("beat %d: WLAST %d on beat %d of %d" % (len(self.beats), last, head[2], head[1]))
                if not (self.lo <= at and at + SLOT <= self.hi):
                    self.faults.append("beat %d at 0x%X is outside the region" % (len(self.beats), at))
                else:
                    self.mem[at - self.lo:at - self.lo + SLOT] = data
                self.beats.append((self.clock, at, data))
                head[2] += 1
                if head[2] == head[1]:
                    self._aw.pop(0)
                    delay = self.answer_delay and self.rng.randint(0, self.answer_delay)
                    if self.late_beat is not None and len(self.beats) - 1 >= self.late_beat \
                            and len(self.beats) - head[1] <= self.late_beat:
                        delay += self.late_clocks
                    self._b.append([self.clock + 1 + delay, 2 if head[3] == self.error_burst else 0])
            if self._drive["bvalid"] and self._one("bready"):
                self.answers.append(self.clock)
                self._b.pop(0)
                self._drive["bvalid"] = 0
            # ---- what to drive for the next edge ----
            self._drive["awready"] = int(not self._stalled("aw") and not self.hold_aw)
            self._drive["wready"] = int(not self._stalled("w") and bool(self._aw) and not self.hold_w)
            due = not self._stalled("b") and bool(self._b) and self._b[0][0] <= self.clock and not self.hold_b
            if self._drive["bvalid"] and self._b:
                due = True                       # an answer offered stays offered until it is taken
            self._drive["bvalid"] = int(due)
            self._sig("awready").value = self._drive["awready"]
            self._sig("wready").value = self._drive["wready"]
            self._sig("bvalid").value = self._drive["bvalid"]
            self._sig("bresp").value = self._b[0][1] if due else 0

    def written(self):
        """The beats' first record-bytes, as words, in the order the memory took them."""
        return [int.from_bytes(d[:RECORD_BYTES], "little") for _c, _a, d in self.beats]


RECORD_BYTES = sum(f[1] for f in C.RECORDS["score"]) // 8

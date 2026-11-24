"""What the source's bench and the injector's bench share: the register port, a reset, and the refusal word.

THE REGISTER PORT is the one every block has (the lead's ruling for both RTL
parcels): reg_valid, reg_we, reg_addr, reg_wdata, and reg_rdata, a register.
`harness.exchange` drives one valid and one word, so it cannot drive this
port; `Bus` does. A write or a read is put on the port at a falling edge and
taken at the rising edge after it. A read's word is looked at half a clock
after the edge that takes the read.

THE REFUSAL WORD. `harness.hold` refuses an empty expectation, and a run the
model refuses before any frame has no frame to hold. So every comparison of
frames in these two benches ends with one more word: the block's refusal
register, read after the stream, under a marker bit above the frame's bits
(`account`). The model's side is the code of the name the model refused by,
or 0. EVERY COUNT OF WORDS THE EVIDENCE CARRIES IS THEREFORE ONE MORE THAN THE
FRAMES COMPARED, for each comparison.

`Bus.edges` counts rising edges from the reset on, so a bench can say how many
clocks lie between the edge that took a write and the edge a word was seen at.

WHAT THIS DOES NOT DO: it does not check that a write was taken. A bench reads
the refusal register for that.
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

from spec import constants as C

WORD_BITS = C.BUS["word_bits"]
WORD_BYTES = WORD_BITS // 8
WORD_MASK = (1 << WORD_BITS) - 1


def offset(name):
    """The byte offset of a register row of the definition."""
    return C.REGISTERS[name][0]


def words_of(name, value):
    """A value as the writes that carry it: [(offset, word), ...], the lowest word at the lowest offset."""
    first, _access, count = C.REGISTERS[name]
    return [(first + WORD_BYTES * i, (value >> (WORD_BITS * i)) & WORD_MASK) for i in range(count)]


def account(frame_bytes, code):
    """The word that ends a comparison of frames: a refusal code under a bit no frame has."""
    return (1 << (8 * frame_bytes)) | code


def code_of(name):
    """The number the fabric reports for a refusal name; 0 for none."""
    return C.REFUSAL_CODES[name] if name else 0


class Bus:
    """One design's register port, and a count of its clock's rising edges."""

    def __init__(self, dut, stream_in):
        self.dut = dut
        self.stream_in = stream_in          # the design has in_valid and in_frame
        self.edges = 0
        Clock(dut.clk, 10, unit="ns").start()
        cocotb.start_soon(self._count())

    async def _count(self):
        while True:
            await RisingEdge(self.dut.clk)
            self.edges += 1

    async def reset(self, clocks=3):
        """Hold rst high for some clocks with nothing offered on any port; release it on a falling edge."""
        dut = self.dut
        await FallingEdge(dut.clk)
        dut.rst.value = 1
        dut.reg_valid.value = 0
        dut.reg_we.value = 0
        dut.reg_addr.value = 0
        dut.reg_wdata.value = 0
        if self.stream_in:
            dut.in_valid.value = 0
            dut.in_frame.value = 0
        for _ in range(clocks):
            await FallingEdge(dut.clk)
        dut.rst.value = 0

    async def write_many(self, pairs):
        """One write a clock: [(offset, word), ...] in order. Returns the edge that takes the last one."""
        dut = self.dut
        taken = None
        for at, word in pairs:
            await FallingEdge(dut.clk)
            dut.reg_valid.value = 1
            dut.reg_we.value = 1
            dut.reg_addr.value = at
            dut.reg_wdata.value = word & WORD_MASK
            taken = self.edges + 1
        await FallingEdge(dut.clk)
        dut.reg_valid.value = 0
        dut.reg_we.value = 0
        return taken

    async def write(self, at, word):
        """One write. Returns the number of the rising edge that takes it."""
        return await self.write_many([(at, word)])

    async def write_value(self, name, value):
        """A whole value into its row, the lowest word first. Returns the edge that takes its last word."""
        return await self.write_many(words_of(name, value))

    async def read(self, at):
        """One read: the word the port's register holds after the edge that takes the read."""
        dut = self.dut
        await FallingEdge(dut.clk)
        dut.reg_valid.value = 1
        dut.reg_we.value = 0
        dut.reg_addr.value = at
        await FallingEdge(dut.clk)
        dut.reg_valid.value = 0
        value = dut.reg_rdata.value
        assert value.is_resolvable, "reg_rdata = %s after a read of 0x%03X" % (value, at)
        return value.to_unsigned()

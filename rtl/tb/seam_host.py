"""What the seam's bench needs beside the two parcels' helpers: a run of the chain, and the model's run of it.

The seam's top (rtl/seam/seam.sv) is three blocks behind one register port and
has no stream input. So a run is: reset; the core loaded and started
(`core_host.load`); the source handed the model's noise table and the injector
the schedule's truth records (`source_bus.Bus`); the seed and the frame count
written, the write of the count's upper word starting the source; and the
score records collected as they come out (`harness.exchange`, given no word to
drive, as the source's own bench collects). `core_host` and `source_bus` are
imported and neither is changed. Both drive the same five signals at falling
edges: this file never uses the two at once.

THE MODEL'S SIDE is `model_records`: model/run.py's three lines, a core, the
injector over the source, and one step for each frame, with the model's own
calls made on the core before the first frame when a swap is asked for.
model/run.py builds its core inside itself, so a swap cannot be made through
it; with nothing asked for, the bench holds `model_records` equal to
`model.run.detect`, record for record.

Two things are written here that the parcels' benches keep inside their bench
modules, which cannot be imported (a bench module has tests in it): the writes
that hand a noise table over, and the writes that offer a truth record. They
say what docs/rtl/source.md says: the table's length, then every entry but the
last; a field a row, the denominator last.

WHAT THIS CANNOT SEE, each a stated limit of docs/rtl/seam.md:
  - The table, the schedule and the blob loaded into the design are the ones
    the model is run on. One wrong in both alike is seen by nothing here.
  - `harness.exchange` listens from the clock after the start write. A record
    put out before it, or after its settle, is seen only by `Chain`'s own
    count of `out_valid` over the whole test, which says how many and not what.
  - The clock a record is seen at is counted from the edge that takes the
    start write. Nothing here knows the clock a frame crossed a joint at.
"""
import cocotb
from cocotb.triggers import FallingEdge, RisingEdge

from spec import constants as C
from model import inject, source, weights
from model.detector import Core

import harness
import core_host as host
import source_bus as bus

TRUTH = dict((f[0], f[1]) for f in C.RECORDS["truth"])
SOURCE_CLOCKS = 5 + C.MAX_NOISE_TABLE.bit_length()                  # a sample: docs/rtl/source.md, row S5
INJECT_CLOCKS = 5 + (C.PULSE_SAMPLE_BITS + TRUTH["amplitude_num"] - 1)     # row S7
CORE_CLOCKS = 11                                                    # docs/rtl/core.md, section 4
CLOCK_PREFIX = b"undertone-seam/clocks\x00"                         # so a digest of clocks is never one of records


class Case:
    """One configuration of the whole chain: what the source, the injector and the core are each given."""

    def __init__(self, profile, seed, sigma, frames, schedule, blob, epoch=0):
        self.profile, self.seed, self.sigma, self.frames = profile, seed, sigma, frames
        self.schedule, self.blob, self.epoch = [dict(r) for r in schedule], blob, epoch

    def noise(self):
        return source.Noise(self.profile, self.seed, self.sigma[0], self.sigma[1], self.frames)

    def but(self, **changed):
        """The same case with some of its parts replaced."""
        parts = dict(profile=self.profile, seed=self.seed, sigma=self.sigma, frames=self.frames,
                     schedule=self.schedule, blob=self.blob, epoch=self.epoch)
        parts.update(changed)
        return Case(**parts)


# ------------------------------------------------------------------ the model's side

def model_stream(case):
    """(the frames the model's injector hands the core, the truth as the injector checked it)."""
    stream, truth = inject.inject(case.profile, case.noise(), case.schedule, case.frames)
    return tuple(stream), truth


def model_records(case, before=()):
    """(the model's score records, the truth): model/run.py's own lines, with `before` done to the core first.

    `before` is a list of (method name, argument): each named method of the model core is called with its
    argument before the first frame is stepped. A shadow write and a commit made there are the model's
    whole account of a swap: `model.weights.Store` gives every output before the committed index the old
    set and every one from it on the new, whenever before that index the two calls were made.
    """
    core = Core(case.blob, case.epoch)
    injected, truth = inject.inject(weights.unpack(case.blob)["profile"], case.noise(), case.schedule, case.frames)
    for method, argument in before:
        getattr(core, method)(argument)
    return tuple(core.step(frame) for frame in injected), truth


def words(records):
    return [harness.record_word(r) for r in records]


def first_difference(a, b):
    """The position of the first record that differs between two runs of the model; None when none does."""
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


# ------------------------------------------------------------------ the writes

def table_writes(table):
    """A model's table as the writes that hand it over: its length, then every entry but the last, in order."""
    entries = table[:-1]
    pairs = [(bus.offset("src_table_length"), len(entries))]
    for entry in entries:
        pairs += bus.words_of("src_table_entry", entry)
    return pairs


def truth_writes(record):
    """One truth record as the writes that offer it: a field a row, the denominator last.

    A field that does not fit its row is refused here, not cut to fit: the model would refuse such a record,
    and a bench that wrote its low bits would be comparing two different records.
    """
    top = 1 << (TRUTH["amplitude_num"] - 1)
    assert -top <= record["amplitude_num"] < top, "a numerator of %d does not fit its field" % record["amplitude_num"]
    assert 0 < record["amplitude_den"] <= bus.WORD_MASK and 0 <= record["pulse_id"] < (1 << TRUTH["pulse_id"])
    assert 0 <= record["index"] < (1 << TRUTH["index"])
    return (bus.words_of("inj_truth_index", record["index"])
            + [(bus.offset("inj_truth_pulse_id"), record["pulse_id"]),
               (bus.offset("inj_truth_amplitude_num"), record["amplitude_num"] & bus.WORD_MASK),
               (bus.offset("inj_truth_amplitude_den"), record["amplitude_den"])])


def period(profile):
    """The clocks between two frames of the source."""
    return SOURCE_CLOCKS * C.PROFILES[profile]["channels"]


def clock_of(profile, k):
    """The clock record k is seen at, counted from the edge that takes the start write: the source's
    1 + period * (k + 1), the injector's 52 and the core's 11, by the two parcels' documents."""
    return 1 + period(profile) * (k + 1) + INJECT_CLOCKS + CORE_CLOCKS


# ------------------------------------------------------------------ the chain

class Chain:
    """The design, its one register port, and a count of its records over a WHOLE test.

    The harness listens only while `exchange` runs. `finish` requires that the design put out, from the
    test's first clock to its last, exactly the records the test's comparisons were handed.
    """

    def __init__(self, dut):
        self.dut = dut
        self.bus = bus.Bus(dut, stream_in=False)        # the clock, and a count of its rising edges
        self.records = 0                                # clocks at which out_valid was high, over the whole test
        self.collected = 0                              # records the runs of this test collected
        self.on = True
        self.task = cocotb.start_soon(self._count())

    async def _count(self):
        while self.on:
            await RisingEdge(self.dut.clk)
            if str(self.dut.out_valid.value) == "1":
                self.records += 1

    async def refusals(self):
        """The three blocks' refusal registers, read through the one bus: (core, source, injector)."""
        return (await self.bus.read(bus.offset("refusal")), await self.bus.read(bus.offset("src_refusal")),
                await self.bus.read(bus.offset("inj_refusal")))

    async def run(self, case, expect=None, during=None, extra_latency=0):
        """Reset, load the three blocks, start the source, and collect the records.

        Returns (the words seen; for each, the clocks from the edge that took the start write to the edge it
        was seen at; None or the first X or Z; the three refusal registers read after the stream).
        `during` is a coroutine function, given this chain, run while the stream goes on.
        """
        b, dut = self.bus, self.dut
        await b.reset()
        await host.load(dut, case.blob, case.epoch)                 # the core: its shape, its weights, its start
        # `load` requires the core's refusal register to read 0, and a core that never heard the bus reads 0
        # too. So the core must also SAY it is running, in a bit that is 0 until a start is taken.
        status = await host.status(dut)
        assert status["running"] == 1, "after its load the core does not say it is running: %r" % (status,)
        pairs = table_writes(case.noise().table)                    # the source: the model's own table
        for record in case.schedule:                                # the injector: the schedule, in stream order
            pairs += truth_writes(record)
        await b.write_many(pairs)
        early = self.records
        started = await b.write_many(bus.words_of("src_seed", case.seed) + bus.words_of("src_frames", case.frames))
        base = b.edges
        count = case.frames if expect is None else expect
        gap = period(case.profile)
        job = harness.exchange(dut, [], count, in_valid="reg_valid", in_data="reg_wdata", out_valid="out_valid",
                               out_data="out_record",
                               max_latency=gap * (case.frames + 2) + INJECT_CLOCKS + CORE_CLOCKS + 16 + extra_latency,
                               settle=gap + INJECT_CLOCKS + CORE_CLOCKS + 8)
        if during is None:
            seen, seen_at, _sent, unknown = await job
        else:
            task = cocotb.start_soon(job)
            await during(self)
            seen, seen_at, _sent, unknown = await task
        assert self.records - early == len(seen), \
            "from the start write on the design put out %d record(s) and the collector saw %d" % (self.records - early, len(seen))
        self.collected += len(seen)
        return seen, [base + at - started for at in seen_at], unknown, await self.refusals()

    async def finish(self, clocks=None):
        """Every record the design put out in this test was collected by a run: none before one, none after."""
        for _ in range(INJECT_CLOCKS + CORE_CLOCKS + 8 if clocks is None else clocks):
            await RisingEdge(self.dut.clk)
        self.on = False
        await self.task
        assert self.records == self.collected, \
            "over the whole test the design put out %d record(s) and the runs collected %d" % (self.records, self.collected)


async def records_out(chain, n, clocks):
    """Return at the falling edge after the design's n-th record of this test has been seen.

    A design that has not put it out after `clocks` clocks fails here: a bench never waits without a bound.
    """
    waited = 0
    while chain.records < n:
        assert waited < clocks, "after %d clocks the design has put out %d record(s) of this test, not %d" % (
            waited, chain.records, n)
        await FallingEdge(chain.dut.clk)
        waited += 1


def hold_records(test, label, seen, expected, unknown, **noted):
    """THE COMPARISON, as `harness.compare` makes it: score records, the model's digest by `model.records.digest`'s rule."""
    return harness.hold(test, label, list(seen), list(expected), width_bytes=harness.RECORD_BYTES,
                        prefix=harness.SCORE_PREFIX, describe=harness.describe_records, unknown=unknown, **noted)


def hold_clocks(test, label, seen, expected):
    """The clock each record was seen at, as words, against the clocks the bench states."""
    return harness.hold(test, label, list(seen), list(expected), width_bytes=8, prefix=CLOCK_PREFIX)

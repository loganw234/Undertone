"""The source's bench: rtl/source/source.sv against model/source.py, on every word and every sample.

It runs once under each profile: the runner sets UNDERTONE_PROFILE and builds
the source with that profile's SAMPLE_BITS and CHANNELS.

What holds the source against the model, each through `harness.hold`:

  words_are_the_models       every word the generator makes, all 64 bits,
                             against model.source.word. A sample is a lossy
                             view of a word, so the generator is held here and
                             not through the table
  frames_are_the_models      frames against model.source.Noise at several
                             sigmas, and the clock each frame is seen at
  every_boundary_is_reached  seeds BUILT so that a chosen word comes out at a
                             chosen place (source_seeds.py): the words on each
                             side of every boundary of three small tables, and
                             of chosen boundaries of a large one, the last
                             among them. Each run asserts through the model
                             that the word and the sample aimed at are there
  the_widest_table_runs      the widest table the build holds, loaded whole
  refusal_noise_range        a table longer than the build holds, and the
                             longest it holds
  refusal_register_access    every write the block does not take, and the
                             writes it must take or leave alone

THE REFUSAL WORD. Every comparison of frames ends with the refusal register as
one more word (source_bus.py says why), so each count of words in the evidence
is one more than the frames compared.

WHOSE EXPECTATION. The frames and words are the model's. In
refusal_noise_range the name is the model's own, raised by
model.source.gaussian_table for a table too long for `largest`. In
refusal_register_access the expected codes are THE LEAD'S RULING, not the
model's: the model has no bus and raises no REGISTER_ACCESS.

The controls on the model side hand the comparison a wrong model and require
a WORD mismatch at the place this file works out: a generator with one bit of
one constant changed, and a table one entry short. The controls on the RTL
side are the mutants in benches.toml.

WHAT THIS BENCH DOES NOT SEE: a seed, a sigma or a length it does not run;
anything about the noise's tails, which is the model's gate; whether a table
the host loads is a Gaussian's, since the bench loads the model's own.
"""
import os
import random

import cocotb
from cocotb.triggers import FallingEdge

from spec import constants as C
from model import source
from model.refusal import Refusal

import harness
import source_bus as bus
import source_seeds as seeds

PROFILE = os.environ["UNDERTONE_PROFILE"]
PROF = C.PROFILES[PROFILE]
CHANNELS = PROF["channels"]
FRAME_BYTES = (CHANNELS * PROF["sample_bits"] + 7) // 8
STEPS = C.MAX_NOISE_TABLE.bit_length()          # the search's comparisons: 15 for 32767 entries
SAMPLE_CLOCKS = 5 + STEPS
PERIOD = SAMPLE_CLOCKS * CHANNELS               # a frame every so many clocks
LARGEST = min(C.MAX_NOISE_TABLE, PROF["sample_max"])
SEED = 2026112320
FRAME_PREFIX = b"undertone-rtl-a/source-frames/"
WORD_PREFIX = b"undertone-rtl-a/source-words/"

# The sizes. Set after the first measured run; see docs/rtl/source.md.
WORD_SEEDS = [0, 1, (1 << 64) - 1, 1 << 31, 1 << 32, 1 << 63, 0x0123456789ABCDEF]
WORD_RANDOM_SEEDS = 5
WORD_FRAMES = 16
NOISE_RUNS = [((1, 1), 48), ((3, 2), 48), ((37, 10), 48), ((100, 1), 48), ((1000, 1), 96)]
SMALL_SIGMAS = [(1, 1), (3, 2), (2, 1)]
LARGE_SIGMA = (1000, 1)
WIDEST_FRAMES = 32


async def begin(dut):
    b = bus.Bus(dut, stream_in=False)
    await b.reset()
    return b


def table_writes(table):
    """A model's table as the writes that hand it over: its length, then every entry but the last, in order."""
    entries = table[:-1]
    pairs = [(bus.offset("src_table_length"), len(entries))]
    for entry in entries:
        pairs += bus.words_of("src_table_entry", entry)
    return pairs


async def load_table(b, table):
    await b.write_many(table_writes(table))


def collector(dut, count, frames, words, settle):
    return harness.exchange(dut, [], count, in_valid="reg_valid", in_data="reg_wdata",
                            out_valid="word_valid" if words else "out_valid",
                            out_data="word" if words else "out_frame",
                            max_latency=PERIOD * (frames + 2) + 16,
                            settle=PERIOD + 8 if settle is None else settle)


async def run(b, seed, frames, *, words=False, expect=None, settle=None, during=None, listen=None):
    """Write the seed and the frame count, whose upper word starts the run, and collect what comes out.

    Returns (the words seen; for each, the clocks from the edge that took the start write to the edge it
    was seen at; None or the first X or Z). `during` is a coroutine function run while the run goes on.
    `listen` is how many frames' worth of clocks to wait when the count asked for is not the count expected.
    """
    started = await b.write_many(bus.words_of("src_seed", seed) + bus.words_of("src_frames", frames))
    base = b.edges
    count = frames * (CHANNELS if words else 1) if expect is None else expect
    job = collector(b.dut, count, frames if listen is None else listen, words, settle)
    if during is None:
        seen, seen_at, _sent, unknown = await job
    else:
        task = cocotb.start_soon(job)
        await during()
        seen, seen_at, _sent, unknown = await task
    return seen, [base + at - started for at in seen_at], unknown


def frame_words(frames):
    return [harness.frame_word(PROFILE, f) for f in frames]


async def hold_frames(b, test, label, seen, unknown, model_frames, refused_as=None, **noted):
    """THE COMPARISON: the frames, then the refusal register against the name the model refused by, or none."""
    code = await b.read(bus.offset("src_refusal"))
    expected = frame_words(model_frames) + [bus.account(FRAME_BYTES, bus.code_of(refused_as))]
    return harness.hold(test, label, seen + [bus.account(FRAME_BYTES, code)], expected,
                        width_bytes=FRAME_BYTES + 1, prefix=FRAME_PREFIX, unknown=unknown, **noted)


async def hold_code(b, test, label, want_name):
    """The refusal register alone, against a name or none."""
    return await hold_frames(b, test, label, [], None, [], refused_as=want_name)


def every_clock(frames):
    """The clock each frame of a run is seen at, counted from the edge that takes the start write."""
    return [1 + PERIOD * (i + 1) for i in range(frames)]


# ---------------------------------------------------------------- the generator, on its words

@cocotb.test()
async def words_are_the_models(dut):
    b = await begin(dut)
    await load_table(b, source.gaussian_table(1, 1))        # the engine searches whatever is loaded
    rng = random.Random(SEED)
    all_seeds = WORD_SEEDS + [rng.getrandbits(64) for _ in range(WORD_RANDOM_SEEDS)]
    total = 0
    for n, seed in enumerate(all_seeds):
        seen, _at, unknown = await run(b, seed, WORD_FRAMES, words=True)
        expected = [source.word(seed, i) for i in range(WORD_FRAMES * CHANNELS)]
        count, _model, _rtl = harness.hold("words_are_the_models", "seed %d" % n, seen, expected,
                                           width_bytes=8, prefix=WORD_PREFIX, unknown=unknown)
        total += count
    assert total == len(all_seeds) * WORD_FRAMES * CHANNELS, total


# ---------------------------------------------------------------- the source, on its frames

@cocotb.test()
async def frames_are_the_models(dut):
    b = await begin(dut)
    rng = random.Random(SEED + 1)
    for (sigma_num, sigma_den), frames in NOISE_RUNS:
        for again in range(2):                              # two seeds through one table
            seed = rng.getrandbits(64)
            noise = source.Noise(PROFILE, seed, sigma_num, sigma_den, frames)
            if again == 0:
                await load_table(b, noise.table)
            seen, at, unknown = await run(b, seed, frames)
            await hold_frames(b, "frames_are_the_models", "sigma %d/%d seed %d" % (sigma_num, sigma_den, again),
                              seen, unknown, list(noise))
            assert at == every_clock(frames), at[:4]


@cocotb.test()
async def a_frame_every_twenty_clocks_a_channel(dut):
    """The design's number: frame n is seen 1 + SAMPLE_CLOCKS * CHANNELS * (n + 1) clocks after the start write is taken,
    out_valid is high for one clock a frame, and the source stops after the last."""
    assert SAMPLE_CLOCKS == 20, SAMPLE_CLOCKS
    b = await begin(dut)
    frames = 24
    noise = source.Noise(PROFILE, 7, 2, 1, frames)
    await load_table(b, noise.table)
    seen, at, unknown = await run(b, 7, frames)
    assert unknown is None and len(seen) == frames, (unknown, len(seen))
    assert at == every_clock(frames), at
    assert at[0] == 1 + 20 * CHANNELS and at[1] - at[0] == 20 * CHANNELS, at[:2]
    status = await b.read(bus.offset("src_status"))
    assert status == 0, status


# ---------------------------------------------------------------- the table, to its last entry

async def reach(b, test, label, sigma, word, want, place):
    """One run in which word number `place` is `word`. The model says that it is, and what it gives."""
    seed = seeds.seed_for(word, place)
    assert source.word(seed, place) == word, "the built seed does not give the word aimed at"
    frames = place // CHANNELS + 1
    model_frames = list(source.Noise(PROFILE, seed, sigma[0], sigma[1], frames))
    assert model_frames[place // CHANNELS][place % CHANNELS] == want, "the model's sample there is not the one aimed at"
    seen, _at, unknown = await run(b, seed, frames, settle=2)
    await hold_frames(b, test, label, seen, unknown, model_frames)


def chosen_magnitudes(table):
    """For a large table: the first three magnitudes, the last three it can yield, and each power of two with the
    magnitude below it, where the search's comparisons all change."""
    last = len(table) - 1
    want = {0, 1, 2}
    k = 1
    while (1 << k) < last:
        want |= {(1 << k) - 1, 1 << k}
        k += 1
    can = [m for m in range(len(table)) if table[m] > (table[m - 1] if m else 0)]
    return want | set(can[-3:])


@cocotb.test()
async def every_boundary_is_reached(dut):
    test = "every_boundary_is_reached"
    b = await begin(dut)
    runs = 0
    for sigma in SMALL_SIGMAS + [LARGE_SIGMA]:
        table = source.gaussian_table(sigma[0], sigma[1])
        await load_table(b, table)
        targets = seeds.boundary_words(table)
        assert max(m for _word, _want, m in targets) == len(table) - 1, "the last magnitude is not among the targets"
        if sigma == LARGE_SIGMA:
            keep = chosen_magnitudes(table)
            targets = [t for t in targets if t[2] in keep]
            assert len(table) - 1 in keep
        for k, (word, want, _m) in enumerate(targets):
            await reach(b, test, "sigma %d/%d word %d" % (sigma[0], sigma[1], k), sigma, word, want, k % (2 * CHANNELS))
            runs += 1
    assert runs > 0


def refusal_name(call):
    try:
        call()
    except Refusal as e:
        return e.name
    return None


def widest_whole_sigma():
    """The largest whole sigma whose table the model builds for this build's `largest`, by the model."""
    low, high = 1, LARGEST                                  # the model takes sigma 1 and refuses sigma `largest`
    while high - low > 1:
        mid = (low + high) // 2
        if refusal_name(lambda: source.gaussian_table(mid, 1, LARGEST)) is None:
            low = mid
        else:
            high = mid
    return low


@cocotb.test()
async def the_widest_table_runs(dut):
    b = await begin(dut)
    sigma = widest_whole_sigma()
    seed = random.Random(SEED + 2).getrandbits(64)
    noise = source.Noise(PROFILE, seed, sigma, 1, WIDEST_FRAMES)
    assert len(noise.table) - 1 <= LARGEST
    await load_table(b, noise.table)
    seen, at, unknown = await run(b, seed, WIDEST_FRAMES)
    await hold_frames(b, "the_widest_table_runs", "sigma %d/1, %d entries" % (sigma, len(noise.table) - 1),
                      seen, unknown, list(noise))
    assert at == every_clock(WIDEST_FRAMES), at[:4]


# ---------------------------------------------------------------- the refusals

@cocotb.test()
async def refusal_noise_range(dut):
    test = "refusal_noise_range"
    b = await begin(dut)
    cap = await b.read(bus.offset("cap_noise_table"))
    assert cap == LARGEST, (cap, LARGEST)
    sigma = widest_whole_sigma()
    name = refusal_name(lambda: source.gaussian_table(sigma + 1, 1, LARGEST))
    assert name == "NOISE_RANGE", name                      # the model's own name for a table past `largest`
    # One entry more than the build holds: refused, and a start then gives no frame.
    await b.write(bus.offset("src_table_length"), LARGEST + 1)
    seen, _at, unknown = await run(b, 5, 3, expect=0)
    await hold_frames(b, test, "one entry more than the build holds", seen, unknown, [], refused_as=name)
    # Far more, to the word's last bit.
    await b.reset()
    await b.write(bus.offset("src_table_length"), bus.WORD_MASK)
    await hold_code(b, test, "a length of every bit set", name)
    # The other side: the longest it holds is taken, as the model takes the widest sigma's table.
    assert refusal_name(lambda: source.gaussian_table(sigma, 1, LARGEST)) is None
    await b.reset()
    await b.write(bus.offset("src_table_length"), LARGEST)
    await hold_code(b, test, "the longest the build holds", None)
    # And a refused length changes nothing: the table before it still runs once the refusal is cleared.
    await b.reset()
    noise = source.Noise(PROFILE, 11, 1, 1, 6)
    await load_table(b, noise.table)
    await b.write(bus.offset("src_table_length"), LARGEST + 1)
    await hold_code(b, test, "a refused length", name)
    await b.write(bus.offset("src_refusal"), 0)
    seen, _at, unknown = await run(b, 11, 6)
    await hold_frames(b, test, "the table before it still runs", seen, unknown, list(noise))


@cocotb.test()
async def refusal_register_access(dut):
    """The expected codes here are the lead's ruling, not the model's: the model has no bus."""
    test = "refusal_register_access"
    name = "REGISTER_ACCESS"
    b = await begin(dut)
    hole = bus.offset("cap_noise_table") + bus.WORD_BYTES
    rows = set()
    for first, _access, count in C.REGISTERS.values():
        rows |= set(first + bus.WORD_BYTES * i for i in range(count))
    assert hole not in rows and bus.offset("src_seed") < hole < bus.offset("inj_frame")

    # Writes the block does not take, each from reset.
    for label, at, word in (("a read-only row", bus.offset("src_status"), 1),
                            ("the capability row", bus.offset("cap_noise_table"), 0),
                            ("an offset that holds no row", hole, 0),
                            ("an offset that is not a word's", bus.offset("src_seed") + 2, 0),
                            ("anything but 0 into the refusal register", bus.offset("src_refusal"), 1)):
        await b.reset()
        await b.write(at, word)
        await hold_code(b, test, label, name)
    await b.write(bus.offset("src_refusal"), 0)
    await hold_code(b, test, "a write of 0 clears it", None)

    # Writes it takes, and writes that are not its own: nothing is refused.
    await b.reset()
    await b.write_value("src_seed", (1 << 64) - 1)
    await b.write(bus.offset("inj_frame"), 5)               # the injector's block
    await b.write(C.REGISTERS["id"][0], 5)                  # the core's block
    assert await b.read(hole) == 0
    assert await b.read(bus.offset("src_seed")) == 0        # a write-only row reads 0
    assert await b.read(bus.offset("inj_refusal")) == 0     # not this block's: it answers 0
    await hold_code(b, test, "writes taken, writes not its own, and reads", None)

    # One entry more than the declared length.
    await b.reset()
    table = source.gaussian_table(1, 1)
    await load_table(b, table)
    await hold_code(b, test, "a table of its declared length", None)
    await b.write_value("src_table_entry", 1 << 62)
    await hold_code(b, test, "one entry more than declared", name)

    # A start with the table short: refused, and no frame.
    await b.reset()
    await b.write_many(table_writes(table)[:-2])            # all but the last entry
    seen, _at, unknown = await run(b, 3, 4, expect=0)
    await hold_frames(b, test, "a start with the table short", seen, unknown, [], refused_as=name)

    # A start with NO table declared since rst is a host that forgot: refused, and no frame.
    await b.reset()
    seen, _at, unknown = await run(b, 3, 4, expect=0)
    await hold_frames(b, test, "a start with no table declared", seen, unknown, [], refused_as=name)
    # The other side: a table DECLARED with no entries is a table. Every count is 0, which is what the
    # model's own lookup gives over a table that holds no entry but its last.
    await b.reset()
    await b.write(bus.offset("src_table_length"), 0)
    zeros = list(NoEntries(PROFILE, 3, 1, 1, 4))
    assert zeros == [(0,) * CHANNELS] * 4, zeros
    seen, at, unknown = await run(b, 3, 4)
    await hold_frames(b, test, "a table declared with no entries", seen, unknown, zeros)
    assert at == every_clock(4), at

    # With a refusal latched a start does nothing; the host clears, then starts.
    await b.reset()
    noise = source.Noise(PROFILE, 21, 1, 1, 5)
    await load_table(b, noise.table)
    await b.write(bus.offset("src_status"), 0)
    seen, _at, unknown = await run(b, 21, 5, expect=0)
    await hold_frames(b, test, "a start with a refusal latched", seen, unknown, [], refused_as=name)
    await b.write(bus.offset("src_refusal"), 0)
    seen, _at, unknown = await run(b, 21, 5)
    await hold_frames(b, test, "cleared, then started", seen, unknown, list(noise))
    # A src_table_length that is taken CLEARS THE REFUSAL too: it begins a new table.
    await b.write(bus.offset("src_status"), 0)
    await hold_code(b, test, "a refusal latched again", name)
    await load_table(b, noise.table)
    await hold_code(b, test, "a taken table length clears it", None)
    seen, _at, unknown = await run(b, 21, 5)
    await hold_frames(b, test, "and the new table runs", seen, unknown, list(noise))

    # A write during a run: refused, and the run goes on untouched. All but one: a write of 0 to the
    # refusal register is taken in every state, and anything but 0 into it is refused in every state.
    await b.reset()
    frames = 6
    noise = source.Noise(PROFILE, 33, 1, 1, frames)
    await load_table(b, noise.table)
    status, codes = [], []

    async def meddle():
        for _ in range(PERIOD + 3):
            await FallingEdge(b.dut.clk)
        status.append(await b.read(bus.offset("src_status")))
        await b.write_value("src_seed", 34)                         # refused
        codes.append(await b.read(bus.offset("src_refusal")))
        await b.write(bus.offset("src_refusal"), 0)                 # taken, during the run
        codes.append(await b.read(bus.offset("src_refusal")))
        await b.write(bus.offset("src_refusal"), 9)                 # refused
        codes.append(await b.read(bus.offset("src_refusal")))
        await b.write(bus.offset("src_refusal"), 0)
        await b.write(bus.offset("src_table_length"), 0)            # refused: the last word of this run's account
        status.append(await b.read(bus.offset("src_status")))

    seen, at, unknown = await run(b, 33, frames, during=meddle)
    assert status == [1 << C_RUNNING_BIT, 1 << C_RUNNING_BIT], status   # every write of `meddle` fell inside the run
    assert codes == [bus.code_of(name), 0, bus.code_of(name)], codes
    await hold_frames(b, test, "writes during a run", seen, unknown, list(noise), refused_as=name)
    assert at == every_clock(frames), at
    assert await b.read(bus.offset("src_status")) == 0


C_RUNNING_BIT = 0       # REG_SRC_STATUS_RUNNING_BIT of the package; the Python copy's name for it is not assumed here


class NoEntries(source.Noise):
    """The model's lookup over a table that holds no entry but its last: every count is 0."""

    def __init__(self, *args):
        super().__init__(*args)
        self.table = self.table[-1:]


# ---------------------------------------------------------------- the controls, on the model side

async def expect_mismatch(hold_it, at):
    """`hold_it` is a comparison against a wrong model. It must raise a WORD mismatch at word `at`."""
    try:
        result = hold_it()
        if hasattr(result, "__await__"):
            await result
    except harness.Mismatch as e:
        assert e.kind == "WORD" and e.at == at, str(e)
        return
    raise AssertionError("the comparison was handed a wrong model and reported nothing")


@cocotb.test()
async def control_model_constant_bit(dut):
    """A model generator with one bit of one constant changed must be reported, at the first word it changes."""
    test = "control_model_constant_bit"
    b = await begin(dut)
    await load_table(b, source.gaussian_table(1, 1))
    seed, frames = 0x0123456789ABCDEF, 16
    count = frames * CHANNELS
    seen, _at, unknown = await run(b, seed, frames, words=True)
    right = seeds.wrong_words(seed, count)
    assert right == [source.word(seed, i) for i in range(count)], "the helper with the model's constants is not the model"
    harness.hold(test, "the right model", seen, right, width_bytes=8, prefix=WORD_PREFIX, unknown=unknown)
    for name in ("gamma", "mix1", "mix2"):
        for bit in (0, 63):
            constants = {"gamma": seeds.GAMMA, "mix1": seeds.MIX1, "mix2": seeds.MIX2}
            constants[name] ^= 1 << bit
            wrong = seeds.wrong_words(seed, count, **constants)
            differs = [i for i in range(count) if wrong[i] != right[i]]
            assert differs, "bit %d of %s changes no word of this run: choose another seed" % (bit, name)
            if name == "gamma":
                assert differs[0] == 0, differs[0]          # the sum for word 0 moves by 2^bit, and the mix is one to one
            label = "bit %d of %s" % (bit, name)
            await expect_mismatch(lambda: harness.hold(test, label, seen, wrong, width_bytes=8, prefix=WORD_PREFIX,
                                                       unknown=unknown), differs[0])


class OneEntryShort(source.Noise):
    """The model with a table one entry short: the entry before the last is gone, so the largest magnitude is."""

    def __init__(self, *args):
        super().__init__(*args)
        self.table = self.table[:-2] + self.table[-1:]


@cocotb.test()
async def control_model_table_one_short(dut):
    """A model whose table is one entry short must be reported, at the frame where the last magnitude is."""
    test = "control_model_table_one_short"
    b = await begin(dut)
    table = source.gaussian_table(1, 1)
    await load_table(b, table)
    word, want, magnitude = seeds.boundary_words(table)[-1]
    assert magnitude == len(table) - 1 and abs(want) == magnitude
    place = 2 * CHANNELS - 1                                # the last channel of the second frame
    seed = seeds.seed_for(word, place)
    assert source.word(seed, place) == word
    frames = 3
    model_frames = list(source.Noise(PROFILE, seed, 1, 1, frames))
    assert model_frames[1][CHANNELS - 1] == want
    short_frames = list(OneEntryShort(PROFILE, seed, 1, 1, frames))
    differs = [i for i in range(frames) if short_frames[i] != model_frames[i]]
    assert differs == [1], differs
    seen, _at, unknown = await run(b, seed, frames)
    await hold_frames(b, test, "the right model", seen, unknown, model_frames)
    await expect_mismatch(lambda: hold_frames(b, test, "a table one entry short", seen, unknown, short_frames), 1)

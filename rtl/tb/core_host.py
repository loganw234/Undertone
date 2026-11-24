"""What the detector core's benches share: the register port driven as a host would drive it.

Loading a configuration is a bench's own work (docs/rtl/README.md): the harness
configures nothing. This file is that work, for rtl/core/core.sv:

  - one read and one write of the register port, by the offsets of
    `spec.constants.REGISTERS`; no offset is typed here;
  - `load`, which does what a host library would: unpacks the blob with the
    model's own `unpack` (the hash, the format, the shape), writes the shape,
    `configure`, the weight words in the blob's order, `start`; and then
    requires that no refusal is latched and that the status says the core runs;
  - `write_shadow` and `commit`, the store's two operations;
  - `plain_shape` and `try_configure`, a shape as the control block's bare
    numbers, for what no blob can say (a shape the model would never pack);
  - `taken`, which waits for the edge that takes the n-th frame, so that a
    write can be landed at a chosen edge of a running stream;
  - `Scripted`, the model core with the model's own calls made before the
    frames they are scripted for, for an operation in the middle of a stream;
  - `Watch`, a count of the design's records over a whole test, because the
    harness listens only inside one call of `compare`;
  - seeded shapes, weights and frames.

WHAT IT CANNOT SEE, each a stated limit of docs/rtl/core.md:
  - `load` takes the weights from the model's `unpack`. A blob the model reads
    wrongly is loaded wrongly into both sides, and no comparison sees it.
  - `Scripted` stands between a bench and the authority. It calls the model's
    own public methods and hands back what `step` returns, untouched; a control
    in bench_core.py hands it a model that commits one output late.
  - A register word compared here goes through `harness.hold`, in tests the
    manifest does not name as identity tests: those words are not records.
"""
import cocotb
from cocotb.triggers import FallingEdge, RisingEdge

from spec import constants as C
from model import weights

import harness

WORD_BITS = C.BUS["word_bits"]
WORD_BYTES = WORD_BITS // 8
WORD_MASK = (1 << WORD_BITS) - 1
REGISTER_PREFIX = b"undertone-registers\x00"       # so a digest of register words is never a digest of records
NAME_OF = dict((code, name) for name, code in C.REFUSAL_CODES.items())
NAME_OF[0] = "none"


def offset(name, word=0):
    """The byte offset of a register's word, from the definition."""
    return C.REGISTERS[name][0] + word * WORD_BYTES


def code(name):
    """The number the fabric reports for a refusal name; 0 for None."""
    return 0 if name is None else C.REFUSAL_CODES[name]


def status_bit(name):
    """The bit a name has in the register `status`, from the definition."""
    return C.REGISTER_BITS["status"][name]


def inner(dut):
    """The core itself: the top, or the instance a wrapper top holds."""
    try:
        return dut.u_core
    except AttributeError:
        return dut


def idle(dut):
    """Nothing offered on the register port. Call it before the first reset: the port's inputs start unknown."""
    dut.reg_valid.value = 0
    dut.reg_we.value = 0
    dut.reg_addr.value = 0
    dut.reg_wdata.value = 0


async def write_many(dut, pairs):
    """Write (offset, value) pairs, one a clock, in order. Each is taken at the rising edge after it is set."""
    for where, value in pairs:
        await FallingEdge(dut.clk)
        dut.reg_valid.value = 1
        dut.reg_we.value = 1
        dut.reg_addr.value = where
        dut.reg_wdata.value = value & WORD_MASK
    await FallingEdge(dut.clk)
    dut.reg_valid.value = 0
    dut.reg_we.value = 0


async def write(dut, name, value, word=0):
    await write_many(dut, [(offset(name, word), value)])


async def read_at(dut, where):
    """One read: the word the port answers with at the edge after the read's."""
    await FallingEdge(dut.clk)
    dut.reg_valid.value = 1
    dut.reg_we.value = 0
    dut.reg_addr.value = where
    await FallingEdge(dut.clk)
    dut.reg_valid.value = 0
    value = dut.reg_rdata.value
    assert value.is_resolvable, "reg_rdata = %s after a read of offset 0x%03X" % (value, where)
    return value.to_unsigned()


async def read(dut, name, word=0):
    return await read_at(dut, offset(name, word))


async def read_wide(dut, name):
    """A register of several words as one number: its lowest bits at the lowest offset."""
    value = 0
    for word in range(C.REGISTERS[name][2]):
        value |= (await read(dut, name, word)) << (word * WORD_BITS)
    return value


async def take_refusal(dut):
    """The latched refusal's number, and the latch cleared."""
    seen = await read(dut, "refusal")
    await write(dut, "refusal", 0)
    return seen


async def status(dut):
    """{name: 0 or 1} for every bit the definition gives `status`."""
    word = await read(dut, "status")
    return dict((name, (word >> bit) & 1) for name, bit in C.REGISTER_BITS["status"].items())


async def capabilities(dut):
    """{register name: value} for every capability register of the read-only block."""
    out = {}
    for name in C.REGISTERS:
        if name.startswith("cap_"):
            out[name] = await read(dut, name)
    return out


# ------------------------------------------------------------------ a configuration, as the host sends it

def words_of(config):
    """The weight words of an unpacked blob, in the blob's order: the rows, the hidden units, the head."""
    out = []
    for rows in config["filters"]:
        for c in sorted(rows):
            out += list(rows[c])
    for unit in config.get("hidden", ()):
        out += list(unit)
    out += list(config["head"])
    return out


def shape_pairs(config):
    """The writes that state an unpacked blob's shape: ten scalars and a mask for each filter."""
    prof = C.PROFILES[config["profile"]]
    filters = config["filters"]
    scalars = (
        ("shape_sample_bits", prof["sample_bits"]),
        ("shape_channels", prof["channels"]),
        ("shape_filters", len(filters)),
        ("shape_taps", len(filters[0][min(filters[0])])),
        ("shape_rectifier", config["rectifier"]),
        ("shape_score_shift", config["score_shift"]),
        ("shape_pool", config["pool"]),
        ("shape_hidden", len(config.get("hidden", ()))),
        ("shape_hidden_shift", config.get("hidden_shift", 0)),
        ("shape_between", config.get("between", 0)),
    )
    pairs = [(offset(name), value) for name, value in scalars]
    for k, rows in enumerate(filters):
        pairs.append((offset("shape_masks", k), sum(1 << c for c in rows)))
    return pairs


def stream_pairs(words):
    return [(offset("shadow_data"), w) for w in words]


async def load(dut, blob, epoch=0):
    """Configure a stopped core from a blob and start it. Call it after a reset. Returns the unpacked blob."""
    config = weights.unpack(blob)            # the host's own checks come first: the hash, the format, the shape
    words = words_of(config)
    await write_many(dut, shape_pairs(config) + [(offset("configure"), len(words))] + stream_pairs(words)
                     + [(offset("start"), epoch)])
    refused = await take_refusal(dut)
    assert refused == 0, "the bench's own load was refused: %s" % NAME_OF.get(refused, refused)
    # "No refusal" is also what a core that never heard the bus would answer: the load is taken only if
    # the core now says it runs.
    state = await status(dut)
    assert state["running"] == 1 and state["loading"] == 0, "after a load the core's status is %s" % state
    return config


async def write_shadow(dut, blob):
    """Send a whole weight set to the shadow: `shadow_begin` with the count, then the words."""
    words = words_of(weights.unpack(blob))
    await write_many(dut, [(offset("shadow_begin"), len(words))] + stream_pairs(words))


def commit_pairs(at):
    """A commit's two writes: the index's lower word, then its upper word, which is the commit."""
    return [(offset("commit_at", 0), at & WORD_MASK), (offset("commit_at", 1), at >> WORD_BITS)]


async def commit(dut, at):
    await write_many(dut, commit_pairs(at))


async def taken(dut, n):
    """Return just after the rising edge that takes the n-th frame offered from now (n counts from 1).

    A write set at the next falling edge lands at the next rising edge: on an unbroken stream that is
    the edge that takes the frame after it.
    """
    seen = 0
    while seen < n:
        await RisingEdge(dut.clk)
        if str(dut.in_valid.value) == "1":
            seen += 1


class Scripted:
    """The model core, with the model's own calls made before the frames they are scripted for.

    `script` maps a count of frames already stepped to a list of (method name, argument): before the
    frame with that count is stepped, each named method of the model core is called with its argument.
    `harness.compare` reads `store` and calls `step`, and nothing else.
    """

    def __init__(self, core, script):
        self.core, self.store, self.script, self.stepped = core, core.store, script, 0

    def step(self, frame):
        for method, argument in self.script.get(self.stepped, ()):
            getattr(self.core, method)(argument)
        self.stepped += 1
        return self.core.step(frame)


class Watch:
    """Counts, over a WHOLE test, the clocks at which out_valid is high.

    The harness listens only inside one call of `compare`: from that call's first frame to its own
    settle. A bench that compares in pieces, and writes registers between them, would never see a
    record the design put out between two calls. This does: `all_seen` requires that the design put
    out exactly as many records as the calls compared, not one more.
    """

    def __init__(self, dut):
        self.dut, self.records, self.compared, self.on = dut, 0, 0, True
        self.task = cocotb.start_soon(self._count())

    async def _count(self):
        while self.on:
            await RisingEdge(self.dut.clk)
            if str(self.dut.out_valid.value) == "1":
                self.records += 1

    async def done(self, clocks=40):
        for _ in range(clocks):                  # past anything still in the pipeline
            await RisingEdge(self.dut.clk)
        self.on = False
        await self.task
        assert self.records == self.compared, \
            "over the whole test the design put out %d record(s) and the comparisons held %d" % (self.records, self.compared)


_watch = None


def watch(dut):
    """Start counting the design's records over the whole test. Call it once the clock runs."""
    global _watch
    _watch = Watch(dut)


async def compare(dut, core, frames, **kw):
    """`harness.compare`, with the records it held added to the whole test's count."""
    result = await harness.compare(dut, core, frames, **kw)
    if _watch is not None:
        _watch.compared += result.count
    return result


async def all_seen():
    """Every record the design put out in this test was inside a comparison: none between two of them."""
    await _watch.done()


def hold_words(test, label, seen, expected):
    """Register words against the words the bench states, through the harness's own comparison."""
    return harness.hold(test, label, list(seen), list(expected), width_bytes=WORD_BYTES, prefix=REGISTER_PREFIX)


# ------------------------------------------------------------------ seeded shapes, weights and frames

def weight(rng):
    return rng.randint(C.COEFF_MIN, C.COEFF_MAX)


def random_sets(rng, channels, caps):
    """For each filter, the channels it reads: inside the build's filters and rows, differing where they can."""
    while True:
        k = rng.randint(1, caps["cap_filters"])
        sets = [sorted(rng.sample(range(channels), rng.randint(1, channels))) for _ in range(k)]
        if sum(len(s) for s in sets) <= caps["cap_rows"]:
            return sets


def blob_of(profile, sets, taps, rng, rectifier, pool, score_shift, hidden=0, hidden_shift=0, between=0):
    """A blob of that shape with every weight drawn over the whole range."""
    filters = [dict((c, [weight(rng) for _ in range(taps)]) for c in s) for s in sets]
    if hidden == 0:
        return weights.pack(profile, filters, [weight(rng) for _ in sets], rectifier, pool, score_shift)
    units = [[weight(rng) for _ in sets] for _ in range(hidden)]
    return weights.pack(profile, filters, [weight(rng) for _ in range(hidden)], rectifier, pool, score_shift,
                        units, hidden_shift, between)


def random_blob(rng, profile, caps, hidden=None, pool=None, taps=None):
    """A seeded shape inside the build's maxima, with weights over their whole range."""
    channels = C.PROFILES[profile]["channels"]
    sets = random_sets(rng, channels, caps)
    taps = taps if taps is not None else rng.choice([1, 2, caps["cap_taps"] - 1, caps["cap_taps"]])
    taps = max(1, taps)
    pool = pool if pool is not None else rng.choice([1, 2, 3, 5, 8])
    hidden = hidden if hidden is not None else rng.choice([0, 1, caps["cap_hidden"]])
    codes = sorted(C.RECTIFIERS.values())
    return blob_of(profile, sets, taps, rng, rng.choice(codes), pool, rng.randint(0, min(12, caps["cap_score_shift"])),
                   hidden, rng.randint(0, min(12, caps["cap_hidden_shift"])) if hidden else 0,
                   rng.choice(codes) if hidden else 0)


def reweighted(rng, blob):
    """Another blob of the same shape: every weight drawn again."""
    config = weights.unpack(blob)
    sets = [sorted(rows) for rows in config["filters"]]
    taps = len(config["filters"][0][min(config["filters"][0])])
    return blob_of(config["profile"], sets, taps, rng, config["rectifier"], config["pool"], config["score_shift"],
                   len(config.get("hidden", ())), config.get("hidden_shift", 0), config.get("between", 0))


def random_frames(rng, profile, n):
    prof = C.PROFILES[profile]
    return [tuple(rng.randint(prof["sample_min"], prof["sample_max"]) for _ in range(prof["channels"])) for _ in range(n)]


# ------------------------------------------------------------------ a shape as bare numbers, for what no blob can say

SHAPE_SCALARS = ("shape_sample_bits", "shape_channels", "shape_filters", "shape_taps", "shape_rectifier",
                 "shape_score_shift", "shape_pool", "shape_hidden", "shape_hidden_shift", "shape_between")


def plain_shape(profile, **over):
    """The smallest shape there is, as the control block's own numbers: one filter of one tap on channel 0,
    pass, a pool of 1, no shift, no hidden layer. `over` replaces any of them; `masks` is the list of masks."""
    prof = C.PROFILES[profile]
    shape = {"shape_sample_bits": prof["sample_bits"], "shape_channels": prof["channels"], "shape_filters": 1,
             "shape_taps": 1, "shape_rectifier": C.RECTIFIERS["pass"], "shape_score_shift": 0, "shape_pool": 1,
             "shape_hidden": 0, "shape_hidden_shift": 0, "shape_between": 0, "masks": None}
    shape.update(over)
    if shape["masks"] is None:
        shape["masks"] = [1] * min(shape["shape_filters"], C.REGISTERS["shape_masks"][2])
    return shape


def rows_of(shape):
    return sum(bin(m).count("1") for m in shape["masks"][:shape["shape_filters"]])


def words_in(shape):
    """How many weight words a set of this shape has: the rows' taps, then the head's."""
    k, h = shape["shape_filters"], shape["shape_hidden"]
    return rows_of(shape) * shape["shape_taps"] + (h * k + h if h else k)


def masks_for_rows(channels, rows):
    """Masks that give exactly that many rows: whole-profile filters, then one with the rest."""
    masks, left = [], rows
    while left > 0:
        n = min(channels, left)
        masks.append((1 << n) - 1)
        left -= n
    return masks


async def try_configure(dut, shape, count=None):
    """After a reset: write the shape and `configure` with the stated count (the shape's own when None).
    Returns the latched refusal's number, 0 when the shape was taken; the latch is cleared."""
    pairs = [(offset(name), shape[name]) for name in SHAPE_SCALARS]
    pairs += [(offset("shape_masks", k), mask) for k, mask in enumerate(shape["masks"])]
    pairs.append((offset("configure"), words_in(shape) if count is None else count))
    await write_many(dut, pairs)
    return await take_refusal(dut)

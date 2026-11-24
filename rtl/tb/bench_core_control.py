"""The detector core's control block: every refusal by its number, and every capability by trial.

It runs once under each profile, on the top the manifest names (the small top:
there no capability is the definition's own, so what a register advertises is
never the constant a test could read instead).

  refuses_<name>              ONE TEST FOR EACH NAME THE FABRIC RAISES, nineteen of them. Each offers
                              the core every case `cases` lists for its name and holds the number the
                              core latches against the package's number for that name, stated here by
                              hand. Two mutants are held against all nineteen: a core that refuses
                              nothing, and a core that names every refusal wrongly. So each test is
                              shown to fail when its refusal is absent, and again when its number is
                              wrong
  refusals_in_order           a shape with two faults is refused under the first name, for the pairs
                              `ORDER` lists; and where the model can be asked the same thing, it
                              gives the name this file states
  outside_its_block           outside 0x010..0xEFF the core does nothing; inside, a read of what is
                              not a readable row answers 0 and refuses nothing
  refused_changes_nothing     THE IDENTITY TEST. A running core is offered operations it must
                              refuse, between stretches of a stream, and every record is still
                              the model's, which was offered none of them
  capabilities_by_trial       each capability register is read, and then the build is ASKED: what
                              is advertised must be taken, and one past it refused under that
                              bound's name
  a_stream_not_finished       docs/rtl/core.md's limit: a stream begun and not finished, or spoiled
                              by one word out of range, blocks a commit until a whole set is in

Register words are held through `harness.hold` (`core_host.hold_words`), so a
mutant can be asked for a WORD mismatch on them. Only `refused_changes_nothing`
is an identity test: the others' words are not records.

WHAT THIS BENCH CANNOT SEE: a case that is not in `cases`. No mutant removes ONE
name's check and leaves the others, so the bench is not shown to tell a missing
check for one name from a missing check for all; and a test that passes only
because another name's check catches its case is not a thing the two mutants
can show. Under a profile of one channel a filter is one row, no shape reaches
SHAPE_ROWS, and `refuses_shape_rows` has no case there: it says so and passes.
A refusal's order against another's is held for `ORDER`'s pairs and no others.
"""
import os
import random

import cocotb
from cocotb.triggers import FallingEdge

from spec import constants as C
from model import weights
from model.detector import Core
from model.refusal import Refusal

import harness
import core_host as host

PROFILE = os.environ["UNDERTONE_PROFILE"]
PROF = C.PROFILES[PROFILE]
CHANNELS = PROF["channels"]
PASS, ABS = C.RECTIFIERS["pass"], C.RECTIFIERS["abs"]
EPOCH_MAX = (1 << dict((f[0], f[1]) for f in C.RECORDS["score"])["epoch"]) - 1
SEED = 2026112330
SETTLE = 36
UNDECLARED = max(C.RECTIFIERS.values()) + 1          # the first rectifier code the definition does not declare
# The names this file has a test for: the nineteen the fabric raises (docs/rtl/core.md, the refusals' table).
FABRIC = ("PROFILE_UNKNOWN", "SHAPE_FILTERS", "SHAPE_TAPS", "SHAPE_RECTIFIER", "SHAPE_SHIFT", "SHAPE_POOL",
          "SHAPE_HIDDEN", "SHAPE_HIDDEN_SHIFT", "SHAPE_BETWEEN", "SHAPE_CHANNEL", "SHAPE_ROWS", "WEIGHT_COUNT",
          "WEIGHT_RANGE", "SWAP_SHAPE", "SWAP_PENDING", "SWAP_INDEX", "SWAP_EPOCH", "CORE_STOPPED", "REGISTER_ACCESS")


async def begin(dut):
    harness.start_clock(dut)
    host.idle(dut)
    host.watch(dut)                                      # every record the design puts out in the test is counted
    await harness.reset(dut)
    return await host.capabilities(dut)


def model_name(call, *args, **kw):
    try:
        call(*args, **kw)
    except Refusal as e:
        return e.name
    return None


async def after(dut, state, blob=None, epoch=0):
    """A reset core brought to a state: 'stopped', 'loading' (the smallest shape taken, no word sent),
    or 'running' (the blob loaded and started)."""
    await harness.reset(dut)
    if state == "loading":
        assert await host.try_configure(dut, host.plain_shape(PROFILE)) == 0
    elif state == "running":
        await host.load(dut, blob, epoch)


# ---- a case is a coroutine that brings a reset core to the refusal and returns the number it latched ----

def shape(stated=None, **over):
    """`configure` of the smallest shape with these numbers in place of its own."""
    async def go(dut, ctx):
        await harness.reset(dut)
        return await host.try_configure(dut, host.plain_shape(PROFILE, **over), stated)
    return go


def writes(state, pairs, epoch=0):
    """These register writes, to a core in that state."""
    async def go(dut, ctx):
        await after(dut, state, ctx["blob"], epoch)
        await host.write_many(dut, pairs)
        return await host.take_refusal(dut)
    return go


def frame(state):
    """One frame offered to a core in that state."""
    async def go(dut, ctx):
        await after(dut, state, ctx["blob"])
        await FallingEdge(dut.clk)
        dut.in_valid.value = 1
        dut.in_frame.value = 0
        await FallingEdge(dut.clk)
        dut.in_valid.value = 0
        return await host.take_refusal(dut)
    return go


def below_the_next_index(frames):
    """A commit that names an output already produced: six frames first, then a commit at index 5."""
    async def go(dut, ctx):
        await after(dut, "running", ctx["blob"])
        await host.compare(dut, Core(ctx["blob"]), frames, test=ctx["test"], label="six frames first", settle=SETTLE)
        await host.commit(dut, len(frames) - 1)
        return await host.take_refusal(dut)
    return go


def cases(name, ctx):
    """[(label, case)] for a refusal name: every way this file knows to be refused under it."""
    caps, count, at = ctx["caps"], ctx["count"], host.offset
    two = host.words_in(host.plain_shape(PROFILE))               # the smallest shape's set: one coefficient, one head weight
    rows_past = host.masks_for_rows(CHANNELS, caps["cap_rows"] + 1)
    empty = at("cap_blob_versions") + host.WORD_BYTES
    assert all(not (r[0] <= empty < r[0] + r[2] * host.WORD_BYTES) for r in C.REGISTERS.values()), "that offset holds a row"
    table = {
        "PROFILE_UNKNOWN": [
            ("the profile's sample bits are another's", shape(shape_sample_bits=PROF["sample_bits"] + 1)),
            ("the profile's channels are another's", shape(shape_channels=CHANNELS + 1))],
        "SHAPE_FILTERS": [
            ("no filter", shape(shape_filters=0)),
            ("one filter past the build's", shape(shape_filters=caps["cap_filters"] + 1))],
        "SHAPE_TAPS": [
            ("no tap", shape(shape_taps=0)),
            ("one tap past the build's", shape(shape_taps=caps["cap_taps"] + 1))],
        "SHAPE_RECTIFIER": [
            ("a rectifier code that is not declared", shape(shape_rectifier=UNDECLARED))],
        "SHAPE_SHIFT": [
            ("a score shift one past the build's", shape(shape_score_shift=caps["cap_score_shift"] + 1))],
        "SHAPE_POOL": [
            ("a pool of none", shape(shape_pool=0)),
            ("a pool one past the build's", shape(shape_pool=caps["cap_pool"] + 1))],
        "SHAPE_HIDDEN": [
            ("one hidden unit past the build's", shape(shape_hidden=caps["cap_hidden"] + 1)),
            ("a hidden shift and no hidden layer", shape(shape_hidden_shift=1)),
            ("a between and no hidden layer", shape(shape_between=ABS))],
        "SHAPE_HIDDEN_SHIFT": [
            ("a hidden shift one past the build's", shape(shape_hidden=1, shape_hidden_shift=caps["cap_hidden_shift"] + 1))],
        "SHAPE_BETWEEN": [
            ("a between code that is not declared", shape(shape_hidden=1, shape_between=UNDECLARED))],
        "SHAPE_CHANNEL": [
            ("a filter that reads no channel", shape(masks=[0])),
            ("a filter that reads a channel the profile has not", shape(masks=[1 | (1 << CHANNELS)]))],
        # reachable only where a filter can have more than one row: mod-b.md's L17
        "SHAPE_ROWS": [
            ("one row past the build's", shape(shape_filters=len(rows_past), masks=rows_past))
        ] if len(rows_past) <= caps["cap_filters"] else [],
        "WEIGHT_COUNT": [
            ("a count one more than the shape's", shape(stated=two + 1)),
            ("a count one fewer than the shape's", shape(stated=two - 1)),
            ("a start before the stream is whole", writes("loading", [(at("start"), 0)])),
            ("a word past the set's end", writes("loading", host.stream_pairs([1] * (two + 1)))),
            ("a stream begun with another count, loading", writes("loading", [(at("shadow_begin"), two + 1)])),
            ("a weight word with no stream begun", writes("running", [(at("shadow_data"), 1)])),
            ("a stream begun with another count, running", writes("running", [(at("shadow_begin"), count + 1)]))],
        "WEIGHT_RANGE": [
            ("a weight one past the highest", writes("loading", [(at("shadow_data"), C.COEFF_MAX + 1)])),
            ("a weight one past the lowest", writes("loading", [(at("shadow_data"), C.COEFF_MIN - 1)])),
            ("a weight out of range, running", writes("running", [(at("shadow_begin"), count), (at("shadow_data"), C.COEFF_MAX + 1)]))],
        "SWAP_SHAPE": [
            ("a shape written to a core that is loading", writes("loading", [(at("shape_taps"), 1)])),
            ("a second configure", writes("loading", [(at("configure"), two)])),
            ("a shape written to a running core", writes("running", [(at("shape_pool"), 1)])),
            ("a mask written to a running core", writes("running", [(at("shape_masks", 1), 1)])),
            ("a configure of a running core", writes("running", [(at("configure"), count)])),
            ("a start of a running core", writes("running", [(at("start"), 0)]))],
        "SWAP_PENDING": [
            ("a second commit", writes("running", host.commit_pairs(5) + host.commit_pairs(9))),
            ("a stream begun between a commit and its index", writes("running", host.commit_pairs(5) + [(at("shadow_begin"), count)]))],
        "SWAP_INDEX": [
            ("a commit below the next index", below_the_next_index(ctx["frames"]))],
        "SWAP_EPOCH": [
            ("a commit at the last epoch", writes("running", host.commit_pairs(3), EPOCH_MAX))],
        "CORE_STOPPED": [
            ("a stream begun on a stopped core", writes("stopped", [(at("shadow_begin"), two)])),
            ("a weight word to a stopped core", writes("stopped", [(at("shadow_data"), 1)])),
            ("a start of a stopped core", writes("stopped", [(at("start"), 0)])),
            ("a commit to a stopped core", writes("stopped", host.commit_pairs(0))),
            ("a commit to a core that is loading", writes("loading", host.commit_pairs(0))),
            ("a frame offered to a stopped core", frame("stopped")),
            ("a frame offered to a core that is loading", frame("loading"))],
        "REGISTER_ACCESS": [
            ("a write to a read-only row of the identity block", writes("stopped", [(at("id"), 1)])),
            ("a write to a capability", writes("stopped", [(at("cap_taps"), 1)])),
            ("a write to the status", writes("stopped", [(at("status"), 0)])),
            ("a write to an offset that holds no row", writes("stopped", [(empty, 0)])),
            ("a write to an offset that is not a multiple of the word", writes("stopped", [(at("shape_taps") + 1, 1)])),
            ("a write to `refusal` that is not zero", writes("stopped", [(at("refusal"), 1)])),
            ("a write to a read-only row of a running core", writes("running", [(at("epoch"), 1)]))],
    }
    assert sorted(table) == sorted(FABRIC), "a case list for each of the fabric's names, and for no other"
    return table[name]


async def refuses(dut, name):
    """Offer the core every case of one name, and hold each latched number against the package's."""
    caps = await begin(dut)
    rng = random.Random(SEED + FABRIC.index(name))
    test = "refuses_" + name.lower()
    blob = host.random_blob(rng, PROFILE, caps, hidden=1, pool=2)
    ctx = {"caps": caps, "blob": blob, "count": len(host.words_of(weights.unpack(blob))), "test": test,
           "frames": host.random_frames(rng, PROFILE, 6)}
    held = 0
    for label, case in cases(name, ctx):
        host.hold_words(test, label, [await case(dut, ctx)], [host.code(name)])
        held += 1
    if name == "SHAPE_ROWS" and CHANNELS == 1:
        assert held == 0, "a filter of one channel is one row: no shape reaches this bound"
    else:
        assert held >= 1, "no case for %s" % name
    await host.all_seen()                                # and no refused operation made the core put out a record


@cocotb.test()
async def refuses_profile_unknown(dut):
    await refuses(dut, "PROFILE_UNKNOWN")


@cocotb.test()
async def refuses_shape_filters(dut):
    await refuses(dut, "SHAPE_FILTERS")


@cocotb.test()
async def refuses_shape_taps(dut):
    await refuses(dut, "SHAPE_TAPS")


@cocotb.test()
async def refuses_shape_rectifier(dut):
    await refuses(dut, "SHAPE_RECTIFIER")


@cocotb.test()
async def refuses_shape_shift(dut):
    await refuses(dut, "SHAPE_SHIFT")


@cocotb.test()
async def refuses_shape_pool(dut):
    await refuses(dut, "SHAPE_POOL")


@cocotb.test()
async def refuses_shape_hidden(dut):
    await refuses(dut, "SHAPE_HIDDEN")


@cocotb.test()
async def refuses_shape_hidden_shift(dut):
    await refuses(dut, "SHAPE_HIDDEN_SHIFT")


@cocotb.test()
async def refuses_shape_between(dut):
    await refuses(dut, "SHAPE_BETWEEN")


@cocotb.test()
async def refuses_shape_channel(dut):
    await refuses(dut, "SHAPE_CHANNEL")


@cocotb.test()
async def refuses_shape_rows(dut):
    await refuses(dut, "SHAPE_ROWS")


@cocotb.test()
async def refuses_weight_count(dut):
    await refuses(dut, "WEIGHT_COUNT")


@cocotb.test()
async def refuses_weight_range(dut):
    await refuses(dut, "WEIGHT_RANGE")


@cocotb.test()
async def refuses_swap_shape(dut):
    await refuses(dut, "SWAP_SHAPE")


@cocotb.test()
async def refuses_swap_pending(dut):
    await refuses(dut, "SWAP_PENDING")


@cocotb.test()
async def refuses_swap_index(dut):
    await refuses(dut, "SWAP_INDEX")


@cocotb.test()
async def refuses_swap_epoch(dut):
    await refuses(dut, "SWAP_EPOCH")


@cocotb.test()
async def refuses_core_stopped(dut):
    await refuses(dut, "CORE_STOPPED")


@cocotb.test()
async def refuses_register_access(dut):
    await refuses(dut, "REGISTER_ACCESS")


# The order of the shape's checks, for these neighbouring pairs: a shape with both faults is refused
# under the first name. It is `unpack`'s order (model/weights.py), with SHAPE_HIDDEN's own case of
# "no hidden layer" where `pack` names it; the host library raises `unpack`'s RESERVED_BITS for those
# bytes of a version 1 blob before the fabric sees anything.
ORDER = (
    ("PROFILE_UNKNOWN", "SHAPE_FILTERS", dict(shape_channels=CHANNELS + 1, shape_filters=0)),
    ("SHAPE_FILTERS", "SHAPE_TAPS", dict(shape_filters=0, shape_taps=0)),
    ("SHAPE_TAPS", "SHAPE_RECTIFIER", dict(shape_taps=0, shape_rectifier=UNDECLARED)),
    ("SHAPE_RECTIFIER", "SHAPE_SHIFT", dict(shape_rectifier=UNDECLARED, shape_score_shift=1 << 20)),
    ("SHAPE_SHIFT", "SHAPE_POOL", dict(shape_score_shift=1 << 20, shape_pool=0)),
    ("SHAPE_POOL", "SHAPE_HIDDEN", dict(shape_pool=0, shape_hidden=1 << 20)),
    ("SHAPE_HIDDEN", "SHAPE_CHANNEL", dict(shape_hidden=1 << 20, masks=[0])),
    ("SHAPE_HIDDEN_SHIFT", "SHAPE_BETWEEN", dict(shape_hidden=1, shape_hidden_shift=1 << 20, shape_between=UNDECLARED)),
    ("SHAPE_BETWEEN", "SHAPE_CHANNEL", dict(shape_hidden=1, shape_between=UNDECLARED, masks=[0])),
    ("SHAPE_CHANNEL", "WEIGHT_COUNT", dict(masks=[0], stated=99)),
)


@cocotb.test()
async def refusals_in_order(dut):
    await begin(dut)
    seen, expected = [], []
    for first, _second, over in ORDER:
        over = dict(over)
        stated = over.pop("stated", None)
        await harness.reset(dut)
        seen.append(await host.try_configure(dut, host.plain_shape(PROFILE, **over), stated))
        expected.append(host.code(first))
    host.hold_words("refusals_in_order", "ten pairs, each refused under its first name", seen, expected)
    # what the model can be asked, it is: the name this file states is the model's own
    row = {0: [1]}
    assert model_name(weights.pack, PROFILE, [row], [1], UNDECLARED, 1, 0) == "SHAPE_RECTIFIER"
    assert model_name(weights.pack, PROFILE, [row], [1], PASS, 1, 0, [[1]], 0, UNDECLARED) == "SHAPE_BETWEEN"
    assert model_name(weights.pack, PROFILE, [row], [1], PASS, 1, 0, None, 1, None) == "SHAPE_HIDDEN"
    assert model_name(weights.pack, PROFILE, [row], [1], PASS, 0, 0) == "SHAPE_POOL"
    assert model_name(weights.pack, PROFILE, [{}], [1], PASS, 1, 0) == "SHAPE_CHANNEL"
    assert model_name(weights.pack, PROFILE, [{CHANNELS: [1]}], [1], PASS, 1, 0) == "SHAPE_CHANNEL"
    assert model_name(weights.pack, PROFILE, [{0: [C.COEFF_MAX + 1]}], [1], PASS, 1, 0) == "WEIGHT_RANGE"
    assert model_name(weights.pack, PROFILE, [row], [C.COEFF_MIN - 1], PASS, 1, 0) == "WEIGHT_RANGE"
    blob = weights.pack(PROFILE, [row], [1], PASS, 1, 0)
    assert model_name(Core(blob, EPOCH_MAX).commit, 3) == "SWAP_EPOCH"
    core = Core(blob)
    core.commit(5)
    assert model_name(core.commit, 9) == "SWAP_PENDING"
    assert model_name(core.write_shadow, blob) == "SWAP_PENDING"
    core = Core(blob)
    for _ in range(6):
        core.step((0,) * CHANNELS)
    assert model_name(core.commit, 5) == "SWAP_INDEX"


@cocotb.test()
async def outside_its_block(dut):
    """Two other blocks live above the core's. Outside its own range the core does nothing: a write is
    ignored and nothing is latched, and a read answers 0. Inside it, a read of an offset that holds no
    row, or of a row that is write-only, answers 0 and refuses nothing."""
    await begin(dut)
    first, end = C.BLOCKS["core"]
    empty = host.offset("cap_blob_versions") + host.WORD_BYTES
    seen = []
    for where in (end, end + host.WORD_BYTES, (1 << C.BUS["address_bits"]) - host.WORD_BYTES, 0, first - host.WORD_BYTES):
        await host.write_many(dut, [(where, 0xFFFFFFFF)])
        seen.append(await host.read(dut, "refusal"))
        seen.append(await host.read_at(dut, where))
    for where in (empty, host.offset("configure"), host.offset("shadow_data"), host.offset("start")):
        seen.append(await host.read_at(dut, where))
        seen.append(await host.read(dut, "refusal"))
    host.hold_words("outside_its_block", "five writes and reads outside the block, four reads of nothing inside it", seen, [0] * 18)
    st = await host.status(dut)
    assert st["running"] == 0 and st["loading"] == 0 and st["refused"] == 0, st


@cocotb.test()
async def refused_changes_nothing(dut):
    caps = await begin(dut)
    rng = random.Random(SEED + 100)
    test = "refused_changes_nothing"
    total = 0
    for n, hidden in enumerate((0, caps["cap_hidden"])):
        blob = host.random_blob(rng, PROFILE, caps, hidden=hidden, pool=3)
        other = host.reweighted(rng, blob)
        count = len(host.words_of(weights.unpack(blob)))
        # a refused shape first: the core is still stopped, and then loads as if nothing had been asked
        await harness.reset(dut)
        assert await host.try_configure(dut, host.plain_shape(PROFILE, shape_taps=0)) == host.code("SHAPE_TAPS")
        st = await host.status(dut)
        assert st["running"] == 0 and st["loading"] == 0, st
        await host.load(dut, blob, 9)
        core = Core(blob, 9)
        frames = host.random_frames(rng, PROFILE, 90)
        total += (await host.compare(dut, core, frames[:30], test=test, label="shape %d: before" % n, gap_seed=n,
                                        settle=SETTLE)).count
        refused = []
        for pairs in ([(host.offset("shape_pool"), 7)], [(host.offset("shape_masks"), 0)], [(host.offset("configure"), count)],
                      [(host.offset("start"), 77)], [(host.offset("shadow_data"), 5)], [(host.offset("shadow_begin"), count + 1)],
                      host.commit_pairs(core.next_index - 1), [(host.offset("status"), 1)], [(host.offset("id"), 1)]):
            await host.write_many(dut, pairs)
            refused.append(await host.take_refusal(dut))
        assert all(refused), refused
        total += (await host.compare(dut, core, frames[30:60], test=test, label="shape %d: after nine refusals" % n,
                                        gap_seed=n + 7, settle=SETTLE)).count
        # the store still works as the model's: a swap to other weights
        await host.write_shadow(dut, other)
        core.write_shadow(other)
        await host.commit(dut, core.next_index + 4)
        core.commit(core.next_index + 4)
        assert await host.take_refusal(dut) == 0
        total += (await host.compare(dut, core, frames[60:], test=test, label="shape %d: a swap after them" % n,
                                        gap_seed=n + 13, settle=SETTLE)).count
    assert total == 2 * 90, total
    await host.all_seen()


def at_and_past(caps):
    """For each bound: (the capability, a shape exactly at what it advertises, one past it, the name)."""
    out = [
        ("cap_filters", host.plain_shape(PROFILE, shape_filters=caps["cap_filters"]),
         host.plain_shape(PROFILE, shape_filters=caps["cap_filters"] + 1), "SHAPE_FILTERS"),
        ("cap_taps", host.plain_shape(PROFILE, shape_taps=caps["cap_taps"]),
         host.plain_shape(PROFILE, shape_taps=caps["cap_taps"] + 1), "SHAPE_TAPS"),
        ("cap_pool", host.plain_shape(PROFILE, shape_pool=caps["cap_pool"]),
         host.plain_shape(PROFILE, shape_pool=caps["cap_pool"] + 1), "SHAPE_POOL"),
        ("cap_score_shift", host.plain_shape(PROFILE, shape_score_shift=caps["cap_score_shift"]),
         host.plain_shape(PROFILE, shape_score_shift=caps["cap_score_shift"] + 1), "SHAPE_SHIFT"),
        ("cap_hidden", host.plain_shape(PROFILE, shape_hidden=caps["cap_hidden"]),
         host.plain_shape(PROFILE, shape_hidden=caps["cap_hidden"] + 1), "SHAPE_HIDDEN"),
        ("cap_hidden_shift", host.plain_shape(PROFILE, shape_hidden=1, shape_hidden_shift=caps["cap_hidden_shift"]),
         host.plain_shape(PROFILE, shape_hidden=1, shape_hidden_shift=caps["cap_hidden_shift"] + 1), "SHAPE_HIDDEN_SHIFT"),
        ("cap_sample_bits", host.plain_shape(PROFILE, shape_sample_bits=caps["cap_sample_bits"]),
         host.plain_shape(PROFILE, shape_sample_bits=caps["cap_sample_bits"] + 1), "PROFILE_UNKNOWN"),
        ("cap_channels", host.plain_shape(PROFILE, shape_channels=caps["cap_channels"]),
         host.plain_shape(PROFILE, shape_channels=caps["cap_channels"] + 1), "PROFILE_UNKNOWN"),
    ]
    at, past = host.masks_for_rows(CHANNELS, caps["cap_rows"]), host.masks_for_rows(CHANNELS, caps["cap_rows"] + 1)
    if len(past) <= caps["cap_filters"]:                 # under one channel a filter is one row: mod-b.md's L17
        out.append(("cap_rows", host.plain_shape(PROFILE, shape_filters=len(at), masks=at),
                    host.plain_shape(PROFILE, shape_filters=len(past), masks=past), "SHAPE_ROWS"))
    return out


@cocotb.test()
async def capabilities_by_trial(dut):
    """What a register advertises is read from the register; what the build takes is found by asking it."""
    caps = await begin(dut)
    test = "capabilities_by_trial"
    for name, at, past, refusal in at_and_past(caps):
        await harness.reset(dut)
        taken = await host.try_configure(dut, at)
        await harness.reset(dut)
        refused = await host.try_configure(dut, past)
        host.hold_words(test, "%s = %d: at it, and one past it" % (name, caps[name]), [taken, refused], [0, host.code(refusal)])
    # the rectifier's codes: each one advertised is taken, for the rectifier and for between; the first not advertised is not
    codes = [c for c in range(host.WORD_BITS) if caps["cap_rectifiers"] >> c & 1]
    first_not = min(c for c in range(host.WORD_BITS) if not caps["cap_rectifiers"] >> c & 1)
    seen, expected = [], []
    for c in codes + [first_not]:
        await harness.reset(dut)
        seen.append(await host.try_configure(dut, host.plain_shape(PROFILE, shape_rectifier=c)))
        expected.append(0 if c in codes else host.code("SHAPE_RECTIFIER"))
        await harness.reset(dut)
        seen.append(await host.try_configure(dut, host.plain_shape(PROFILE, shape_hidden=1, shape_between=c)))
        expected.append(0 if c in codes else host.code("SHAPE_BETWEEN"))
    host.hold_words(test, "cap_rectifiers = %d: each code, as the rectifier and as between" % caps["cap_rectifiers"], seen, expected)
    # the blob's versions: bit 1 is a head with no hidden layer, bit 2 one with a layer
    seen, expected = [], []
    for version, hidden in ((weights.VERSION, 0), (weights.VERSION_HIDDEN, 1)):
        await harness.reset(dut)
        seen.append(await host.try_configure(dut, host.plain_shape(PROFILE, shape_hidden=hidden)))
        expected.append(0)
        assert caps["cap_blob_versions"] >> version & 1, "the build does not advertise blob version %d" % version
    host.hold_words(test, "cap_blob_versions = %d: a head of each version" % caps["cap_blob_versions"], seen, expected)
    # the coefficient's bits: each end of what they hold is taken, and one past each end is not
    top = (1 << (caps["cap_coeff_bits"] - 1)) - 1
    seen, expected = [], []
    for value, name in ((top, None), (-top - 1, None), (top + 1, "WEIGHT_RANGE"), (-top - 2, "WEIGHT_RANGE")):
        await harness.reset(dut)
        assert await host.try_configure(dut, host.plain_shape(PROFILE)) == 0
        await host.write(dut, "shadow_data", value)
        seen.append(await host.take_refusal(dut))
        expected.append(host.code(name))
    host.hold_words(test, "cap_coeff_bits = %d: a weight at each end, and one past each" % caps["cap_coeff_bits"], seen, expected)


@cocotb.test()
async def a_stream_not_finished(dut):
    """The fabric has no third bank. A stream that was begun and not finished, or spoiled by a word out
    of range, has already overwritten part of the shadow: a commit is refused, WEIGHT_COUNT, where the
    model would exchange back to the old set. A whole set written afterwards is committed as the model's."""
    caps = await begin(dut)
    rng = random.Random(SEED + 200)
    test = "a_stream_not_finished"
    blob = host.random_blob(rng, PROFILE, caps, hidden=1, pool=1)
    other = host.reweighted(rng, blob)
    words = host.words_of(weights.unpack(other))
    for label, pairs in (("begun and not finished", [(host.offset("shadow_begin"), len(words))] + host.stream_pairs(words[:-1])),
                         ("spoiled by its first word", [(host.offset("shadow_begin"), len(words)), (host.offset("shadow_data"), C.COEFF_MAX + 1)])):
        await harness.reset(dut)
        await host.load(dut, blob, 2)
        core = Core(blob, 2)
        await host.compare(dut, core, host.random_frames(rng, PROFILE, 10), test=test, label=label + ": before", settle=SETTLE)
        await host.write_many(dut, pairs)
        first = await host.take_refusal(dut)
        await host.commit(dut, core.next_index + 2)
        blocked = await host.take_refusal(dut)
        host.hold_words(test, "a stream " + label + ", then a commit",
                        [first, blocked], [host.code("WEIGHT_RANGE") if "spoiled" in label else 0, host.code("WEIGHT_COUNT")])
        await host.compare(dut, core, host.random_frames(rng, PROFILE, 10), test=test, label=label + ": no swap happened",
                              settle=SETTLE)
        await host.write_shadow(dut, other)
        core.write_shadow(other)
        await host.commit(dut, core.next_index + 2)
        core.commit(core.next_index + 2)
        host.hold_words(test, "the whole set, and its commit, after a stream " + label, [await host.take_refusal(dut)], [0])
        await host.compare(dut, core, host.random_frames(rng, PROFILE, 12), test=test, label=label + ": the swap", settle=SETTLE)
    await host.all_seen()

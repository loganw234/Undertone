"""The detector core held against the reference model on every score word (rtl/core/core.sv).

It runs once under each profile, on the top the manifest names. It reads what
the build can hold from the capability registers, so the same tests run on the
small top and on the definition's maxima.

Fifteen tests. SEVEN ARE THE IDENTITY TESTS the manifest names, each holding the core
against the model through `harness.compare`:

  bit_identity_random          seeded shapes inside the build's maxima, weights and samples over
                               their whole ranges: no hidden layer, one unit, the build's most
  bit_identity_every_tap       two filters whose every coefficient reaches the score unmasked:
                               pass, a pool of 1, head weights of 1, no shift
  bit_identity_swap            a swap to OTHER weights at a named index, with pools of 1 and more
                               and with a hidden layer; then a commit with no write, which
                               exchanges back; then a commit for the very next output
  bit_identity_swap_on_the_edge  the one place where the fabric's order is a choice: a commit
                               whose write lands at the edge that takes frame n-1 and names
                               index n, on an unbroken stream. The swap is at the next clock
  bit_identity_swap_at_zero    a commit at index 0, at five pools of 2 and more: no output is
                               marked as settling
  bit_identity_extremes        the build's own true extremes, in full, by real frames: every
                               sample and weight at its lowest at every maximum; the stream that
                               puts a hidden sum at exactly the lowest value the field holds; the
                               score's own boundary; a flag that must stay when the sums come
                               back into range; and the flag from each hidden unit alone
  bit_identity_counters        the epoch across 2^8, 2^16, 2^31 and to its last value, by the
                               start epoch; the index across 2^16, 2^32 and 2^63 by a state the
                               bench writes into the simulator and into the model alike; and a
                               stream longer than the build's largest pool

FIVE MORE are not identity tests; where they hold a register word it goes through
`harness.hold`:

  latency_is_eleven_clocks     the latency the RTL states
  shadow_closes_and_opens      a shadow write is refused at the last clock a frame of the old
                               set still has weights to read, and taken at the next
  commit_orders                the commits the store must refuse: a second one while one is
                               scheduled, a shadow write between a commit and its index, one
                               while outputs still mix, one below the next index, and one that
                               names the frame taken at its own edge
  commit_at_reads_back         both words of `commit_at`, with an index of 2^32 and more
  swap_epoch_on_the_edge       SWAP_EPOCH for a commit whose write lands at the edge of the swap
                               that reaches the last epoch

THE LAST THREE are the controls on the MODEL side, `control_model_coefficient_bit`,
`control_model_commit_late` and `control_model_head_weights`: each hands `harness.compare`
a model that is wrong in one place and requires a Mismatch at the record this file
predicts. The controls on the RTL side are the mutants in benches.toml.

WHAT THIS BENCH CANNOT SEE is docs/rtl/core.md's list of limits. Two belong
here: a shape the seeded generator never draws is not run; and where the bench
writes state into the simulator, the frames that would lead to that state are
not run.
"""
import os
import random

import cocotb
from cocotb.triggers import FallingEdge, RisingEdge

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
SCORE_BITS = dict((f[0], f[1]) for f in C.RECORDS["score"])["score"]
EPOCH_MAX = (1 << dict((f[0], f[1]) for f in C.RECORDS["score"])["epoch"]) - 1
SEED = 2026112320
LATENCY = 11                     # rtl/core/core.sv states it: eleven registered stages
SETTLE = 3 * LATENCY + 3         # past anything this design could put out late
ONE_PRODUCT = PROF["sample_min"] * C.COEFF_MIN          # the largest product: both factors at their lowest


def needs(lo, hi):
    """The fewest signed bits that hold lo..hi. Written here again, not imported from the model."""
    bits = 1
    while -(1 << (bits - 1)) > lo or hi > (1 << (bits - 1)) - 1:
        bits += 1
    return bits


async def begin(dut):
    """Clock, an idle register port, a reset, and what the build says it can hold. From here on every
    record the design puts out is counted, whether a comparison is listening or not."""
    harness.start_clock(dut)
    host.idle(dut)
    host.watch(dut)
    await harness.reset(dut)
    return await host.capabilities(dut)


async def fresh(dut, blob, epoch=0):
    """A reset core loaded with the blob and started, and the model core built from the same blob."""
    await harness.reset(dut)
    await host.load(dut, blob, epoch)
    return Core(blob, epoch)


async def run(dut, core, frames, test, label, **kw):
    kw.setdefault("settle", SETTLE)
    return await host.compare(dut, core, frames, test=test, label=label, **kw)


async def quiet_refusal(dut):
    """The latched refusal's name, or None, read with nothing in flight; the latch is cleared."""
    seen = await host.take_refusal(dut)
    return None if seen == 0 else host.NAME_OF.get(seen, "code %d" % seen)


def model_refusal(call, *args):
    """The name the model refuses a call under, or None when it takes it."""
    try:
        call(*args)
    except Refusal as e:
        return e.name
    return None


# ------------------------------------------------------------------ every score word

@cocotb.test()
async def bit_identity_random(dut):
    caps = await begin(dut)
    rng = random.Random(SEED)
    total = 0
    for n in range(12):
        blob = host.random_blob(rng, PROFILE, caps, hidden=(0, 1, caps["cap_hidden"])[n % 3])
        core = await fresh(dut, blob, rng.randint(0, 1000))
        result = await run(dut, core, host.random_frames(rng, PROFILE, 120), "bit_identity_random", "shape %d" % n,
                           gap_seed=SEED + n)
        total += result.count
    assert total == 12 * 120, total
    await host.all_seen()


def every_tap(rng, caps):
    """Two filters, pass, a pool of 1, head weights of 1, no shift: the score is the sum of both filters,
    so every coefficient of every row reaches it. No coefficient is zero. Returns (the blob, its rows as
    (filter, channel) in the blob's order, the taps)."""
    sets = [list(range(CHANNELS)), list(range(max(1, CHANNELS - 1)))]
    taps = caps["cap_taps"]
    filters = [dict((c, [host.weight(rng) or 1 for _ in range(taps)]) for c in s) for s in sets]
    rows = [(k, c) for k, s in enumerate(sets) for c in s]
    assert len(rows) <= caps["cap_rows"] and len(sets) <= caps["cap_filters"]
    return filters, rows, taps


def every_tap_blob(filters):
    return weights.pack(PROFILE, filters, [1, 1], PASS, 1, 0)


@cocotb.test()
async def bit_identity_every_tap(dut):
    caps = await begin(dut)
    rng = random.Random(SEED + 100)
    total = 0
    for n in range(3):
        filters, _rows, _taps = every_tap(rng, caps)
        core = await fresh(dut, every_tap_blob(filters), n)
        result = await run(dut, core, host.random_frames(rng, PROFILE, 80), "bit_identity_every_tap", "weights %d" % n,
                           gap_seed=n)
        total += result.count
    assert total == 3 * 80, total
    await host.all_seen()


SWAPS = ((1, 0), (2, 0), (5, 0), (1, 2), (3, 3), (7, 1))       # (pool, hidden units)


@cocotb.test()
async def bit_identity_swap(dut):
    caps = await begin(dut)
    rng = random.Random(SEED + 200)
    total = 0
    for n, (pool, hidden) in enumerate(SWAPS):
        blob = host.random_blob(rng, PROFILE, caps, hidden=min(hidden, caps["cap_hidden"]), pool=pool)
        other = host.reweighted(rng, blob)
        assert other != blob
        core = await fresh(dut, blob, 40 + n)
        frames = host.random_frames(rng, PROFILE, 110)
        label = "pool %d, %d hidden unit(s)" % (pool, hidden)
        total += (await run(dut, core, frames[:20], "bit_identity_swap", label + ": before", gap_seed=n)).count
        # a swap to other weights, six outputs on
        await host.write_shadow(dut, other)
        core.write_shadow(other)
        at = core.next_index + 6
        await host.commit(dut, at)
        core.commit(at)
        assert await quiet_refusal(dut) is None
        total += (await run(dut, core, frames[20:60], "bit_identity_swap", label + ": the swap", gap_seed=n + 50)).count
        # a commit with no write since: it exchanges back, at an index eleven on
        at = core.next_index + 11
        await host.commit(dut, at)
        core.commit(at)
        assert await quiet_refusal(dut) is None
        total += (await run(dut, core, frames[60:90], "bit_identity_swap", label + ": back", gap_seed=n + 90)).count
        # and a commit for the very next output
        at = core.next_index
        await host.commit(dut, at)
        core.commit(at)
        assert await quiet_refusal(dut) is None
        total += (await run(dut, core, frames[90:], "bit_identity_swap", label + ": the next output", gap_seed=n + 130)).count
    assert total == len(SWAPS) * 110, total
    await host.all_seen()                                # no record came out while a register was written between two pieces


@cocotb.test()
async def bit_identity_swap_on_the_edge(dut):
    """A write and a frame at one edge: the write is ordered after the frame. On an unbroken stream the
    commit's upper word lands at the edge that takes frame n-1 and names index n: it is taken, and the
    swap is at the very next clock. The model: `commit(n)` after step n-1 and before step n."""
    caps = await begin(dut)
    rng = random.Random(SEED + 300)
    total = 0
    for case, (n, pool, hidden) in enumerate(((30, 1, 1), (17, 3, 0), (8, 2, caps["cap_hidden"]))):
        blob = host.random_blob(rng, PROFILE, caps, hidden=hidden, pool=pool)
        other = host.reweighted(rng, blob)
        core = await fresh(dut, blob, 7)
        await host.write_shadow(dut, other)
        core.write_shadow(other)
        assert await quiet_refusal(dut) is None

        async def writer():
            await host.taken(dut, n - 2)                 # the edge that took frame n-3 has passed
            await host.write_many(dut, host.commit_pairs(n))   # the lower word with frame n-2, the upper with frame n-1

        task = cocotb.start_soon(writer())
        scripted = host.Scripted(core, {n: [("commit", n)]})
        result = await run(dut, scripted, host.random_frames(rng, PROFILE, 60), "bit_identity_swap_on_the_edge",
                           "case %d: index %d" % (case, n), max_gap=0)
        await task
        assert await quiet_refusal(dut) is None
        total += result.count
    assert total == 3 * 60, total
    await host.all_seen()


def extreme_sets(caps):
    """As many rows as the build allows, in whole-profile filters and then one with the rest."""
    sets, left = [], caps["cap_rows"]
    while left > 0 and len(sets) < caps["cap_filters"]:
        sets.append(list(range(min(CHANNELS, left))))
        left -= len(sets[-1])
    return sets


def all_low(sets, taps):
    return [dict((c, [C.COEFF_MIN] * taps) for c in s) for s in sets]


@cocotb.test()
async def bit_identity_extremes(dut):
    """The build's own true extremes, by real frames. The closed forms are worked here from the build's
    maxima and the definition's constants; the model is asked only whether the stream reaches them."""
    caps = await begin(dut)
    taps, pool = caps["cap_taps"], caps["cap_pool"]
    low = (PROF["sample_min"],) * CHANNELS
    total = 0

    # 1. All maxima, no hidden layer: the rows', the filters', the pool's and the hidden sum's widths fill.
    sets = extreme_sets(caps)
    rows = sum(len(s) for s in sets)
    head_low = C.COEFF_MIN * rows * pool * taps * ONE_PRODUCT          # every head weight at its lowest: negative
    shift = max(0, needs(head_low, 0) - SCORE_BITS)
    assert shift <= caps["cap_score_shift"], "the build's score shift cannot bring its own extreme inside"
    blob = weights.pack(PROFILE, all_low(sets, taps), [C.COEFF_MIN] * len(sets), PASS, pool, shift)
    frames = [low] * (taps + pool - 1 + 3)
    said = list(Core(blob).run(frames))
    assert said[-1]["score"] == head_low >> shift and said[-1]["flags"] == 0, said[-1]
    assert needs(said[-1]["score"], 0) == SCORE_BITS or shift == 0, "the last score uses the field's last bit"
    core = await fresh(dut, blob)
    total += (await run(dut, core, frames, "bit_identity_extremes", "all maxima, no hidden layer", gap_seed=1,
                        max_gap=1)).count

    # 2. The boundary under abs: every unit's hidden sum is exactly the lowest value the field holds, so
    #    between is one past the field's highest, and with every head weight at its lowest the output sum
    #    is at its extreme. One row a filter; the pool is chosen to land on the value.
    units = caps["cap_hidden"]
    k, t = caps["cap_filters"], min(4, taps)
    products, rest = divmod(1 << (SCORE_BITS - 1), -C.COEFF_MIN * ONE_PRODUCT)
    p, rest2 = divmod(products, k * t)
    assert rest == 0 and rest2 == 0 and 1 <= p <= pool, "no pool of this build lands a hidden sum on -2^%d" % (SCORE_BITS - 1)
    one_row = [[c % CHANNELS] for c in range(k)]
    out_low = units * C.COEFF_MIN * (1 << (SCORE_BITS - 1))
    shift = max(0, needs(out_low, 0) - SCORE_BITS)
    assert shift <= caps["cap_score_shift"]
    for label, t_now, flags in (("the boundary: it fits", t, 0), ("one tap more: it does not", t + 1, 1 << C.FLAGS["overflow"])):
        blob = weights.pack(PROFILE, all_low(one_row, t_now), [C.COEFF_MIN] * units, PASS, p, shift,
                            [[C.COEFF_MIN] * k] * units, 0, ABS)
        frames = [low] * (t_now + p - 1 + 3)
        said = list(Core(blob).run(frames))
        assert said[-1]["flags"] == flags, (label, said[-1])
        if not flags:
            assert said[-1]["score"] == out_low >> shift, said[-1]
        core = await fresh(dut, blob)
        total += (await run(dut, core, frames, "bit_identity_extremes", label, gap_seed=2, max_gap=1)).count

    # 3. The score's own width. One unit at -2^63 under pass and a head weight of 1: the score is the
    #    lowest value its field holds, and fits. Two such units: every hidden value still fits and the
    #    output sum, -2^64, does not: the score wraps to 0 and the flag rises at the SCORE's stage.
    lowest = -(1 << (SCORE_BITS - 1))
    for label, n_units, score, flags in (("the score's lowest value", 1, lowest, 0),
                                         ("two units of it: the score does not fit", 2, 0, 1 << C.FLAGS["overflow"])):
        assert n_units <= units
        blob = weights.pack(PROFILE, all_low(one_row, t), [1] * n_units, PASS, p, 0, [[C.COEFF_MIN] * k] * n_units, 0, PASS)
        frames = [low] * (t + p - 1 + 3)
        said = list(Core(blob).run(frames))
        assert said[-1]["score"] == score and said[-1]["flags"] == flags, (label, said[-1])
        core = await fresh(dut, blob)
        total += (await run(dut, core, frames, "bit_identity_extremes", label, gap_seed=3, max_gap=1)).count

    # 4. The flag is sticky. One unit, one tap past the boundary: the hidden value does not fit and the
    #    flag rises. Then frames of zeros until every sum is back in range and the score is 0 again: the
    #    flag stays. (Added after a core whose flag was not sticky passed the three streams above.)
    flag = 1 << C.FLAGS["overflow"]
    quiet = (0,) * CHANNELS
    blob = weights.pack(PROFILE, all_low(one_row, t + 1), [1], PASS, p, 0, [[C.COEFF_MIN] * k], 0, PASS)
    frames = [low] * (t + p + 3) + [quiet] * (t + p + 6)
    said = list(Core(blob).run(frames))
    assert said[0]["flags"] == 0 and said[t + p + 2]["flags"] == flag, (said[0], said[t + p + 2])
    assert said[-1]["flags"] == flag and said[-1]["score"] == 0, said[-1]
    core = await fresh(dut, blob)
    total += (await run(dut, core, frames, "bit_identity_extremes", "the flag stays when the sums come back", gap_seed=4,
                        max_gap=1)).count

    # 5. The flag from EACH unit alone, where the score cannot show it: one stream for every unit of the
    #    build. That unit's weights are at their lowest, one tap past the boundary; every other unit's
    #    weights are zero; every head weight is ZERO. The score is 0 at every output; the flag rises when
    #    that unit's value stops fitting, and stays. (The verifiers' faults: a core whose flag only unit 0
    #    could raise, and then one whose flag every unit but the build's last could raise, each passed
    #    everything that was here before.)
    assert units >= 2
    frames = [low] * (t + p + 3)
    for only in range(units):
        hidden = [[C.COEFF_MIN] * k if j == only else [0] * k for j in range(units)]
        blob = weights.pack(PROFILE, all_low(one_row, t + 1), [0] * units, PASS, p, 0, hidden, 0, PASS)
        said = list(Core(blob).run(frames))
        assert said[0]["flags"] == 0 and said[-1]["flags"] == flag and all(r["score"] == 0 for r in said), (only, said[-1])
        core = await fresh(dut, blob)
        total += (await run(dut, core, frames, "bit_identity_extremes", "the flag from unit %d alone of %d" % (only, units),
                            gap_seed=5 + only, max_gap=1)).count
    assert total == (taps + pool + 2) + 2 * (t + p + 2) + 1 + 2 * (t + p + 2) + (2 * t + 2 * p + 9) + units * (t + p + 3), total
    await host.all_seen()


@cocotb.test()
async def bit_identity_counters(dut):
    caps = await begin(dut)
    rng = random.Random(SEED + 400)
    total = 0
    # the epoch, across each width a short counter would have, by the start epoch
    for start in ((1 << 8) - 1, (1 << 16) - 1, (1 << 31) - 1, EPOCH_MAX - 1):
        blob = host.random_blob(rng, PROFILE, caps, hidden=1, pool=2)
        core = await fresh(dut, blob, start)
        at = core.next_index + 3
        await host.commit(dut, at)
        core.commit(at)
        assert await quiet_refusal(dut) is None
        total += (await run(dut, core, host.random_frames(rng, PROFILE, 12), "bit_identity_counters",
                            "the epoch from %d" % start, gap_seed=start % 97)).count
        if start == EPOCH_MAX - 1:
            # the epoch is now the last its field holds: the next commit is refused, by the model and the core
            name = model_refusal(core.commit, core.next_index + 1)
            await host.commit(dut, core.next_index + 1)
            assert name == "SWAP_EPOCH" and await quiet_refusal(dut) == name
    # the index, across 2^16, 2^32 and 2^63: the state is written, into the simulator and into the model
    for preset in ((1 << 16) - 3, (1 << 32) - 3, (1 << 63) - 3):
        blob = host.random_blob(rng, PROFILE, caps, hidden=0, pool=1)
        core = await fresh(dut, blob, 5)
        await FallingEdge(dut.clk)
        host.inner(dut).next_index.value = preset
        core.store.next_index = preset
        await FallingEdge(dut.clk)
        assert await host.read_wide(dut, "next_index") == preset
        at = preset + 4                                  # a swap past the line too
        await host.commit(dut, at)
        core.commit(at)
        assert await quiet_refusal(dut) is None
        total += (await run(dut, core, host.random_frames(rng, PROFILE, 10), "bit_identity_counters",
                            "the index from %d" % preset, gap_seed=preset % 89)).count
    # the pool's pointer and its counter, past a pool that is the build's most
    blob = host.random_blob(rng, PROFILE, caps, hidden=0, pool=caps["cap_pool"], taps=2)
    core = await fresh(dut, blob)
    total += (await run(dut, core, host.random_frames(rng, PROFILE, caps["cap_pool"] + 40), "bit_identity_counters",
                        "past the largest pool", gap_seed=11, max_gap=1)).count
    assert total == 4 * 12 + 3 * 10 + caps["cap_pool"] + 40, total
    await host.all_seen()


# ------------------------------------------------------------------ the latency

@cocotb.test()
async def latency_is_eleven_clocks(dut):
    """rtl/core/core.sv states it: a frame taken at one rising edge has its record out at the eleventh after."""
    caps = await begin(dut)
    rng = random.Random(SEED + 500)
    blob = host.random_blob(rng, PROFILE, caps, hidden=1, pool=2)
    core = await fresh(dut, blob)
    result = await run(dut, core, host.random_frames(rng, PROFILE, 40), "latency_is_eleven_clocks", "forty frames")
    assert result.latencies == [LATENCY], result.latencies
    await host.all_seen()


# ------------------------------------------------------------------ the store's edges

@cocotb.test()
async def shadow_closes_and_opens(dut):
    """After a swap the bank that was active is still read by the frames taken before it. A shadow write
    is refused, SWAP_PENDING, while one of them still has weights to read, and taken at the first clock
    none has. On an unbroken stream, with the swap's first frame taken at edge t0, the last frame of the
    old set is at stage h1 before edge t0 + 6 and at h2 before t0 + 7: refused at t0 + 6, taken at t0 + 7.
    Then: the refused write changes nothing; written again when open, and committed, every record is
    the model's."""
    caps = await begin(dut)
    rng = random.Random(SEED + 600)
    test = "shadow_closes_and_opens"
    for late, expected in ((6, "SWAP_PENDING"), (7, None)):
        blob = host.random_blob(rng, PROFILE, caps, hidden=1, pool=1)
        second, third = host.reweighted(rng, blob), host.reweighted(rng, blob)
        core = await fresh(dut, blob, 3)
        await host.write_shadow(dut, second)
        core.write_shadow(second)
        at = 20
        await host.commit(dut, at)
        core.commit(at)
        assert await quiet_refusal(dut) is None
        count = len(host.words_of(weights.unpack(third)))

        async def writer():
            await host.taken(dut, at + 1)                # just after t0, the edge that took the swap's first frame
            for _ in range(late - 1):
                await RisingEdge(dut.clk)
            await host.write(dut, "shadow_begin", count)   # lands at t0 + late

        task = cocotb.start_soon(writer())
        await run(dut, core, host.random_frames(rng, PROFILE, 50), test, "the stream, a write %d clocks after the swap" % late,
                  max_gap=0)
        await task
        host.hold_words(test, "a shadow write %d clocks after the swap's first frame" % late,
                        [await host.take_refusal(dut)], [host.code(expected)])
        # written again with nothing in flight, committed, and every record is the model's
        await host.write_shadow(dut, third)
        core.write_shadow(third)
        at = core.next_index + 2
        await host.commit(dut, at)
        core.commit(at)
        host.hold_words(test, "the write again, and its commit", [await host.take_refusal(dut)], [0])
        await run(dut, core, host.random_frames(rng, PROFILE, 30), test, "after the second swap", gap_seed=late)
    await host.all_seen()


@cocotb.test()
async def commit_orders(dut):
    """A commit while one is pending; a commit that names the frame taken at its own edge; a commit while
    outputs still mix. Each is refused under the model's name, and the records are the model's."""
    caps = await begin(dut)
    rng = random.Random(SEED + 700)
    test = "commit_orders"
    blob = host.random_blob(rng, PROFILE, caps, hidden=1, pool=4)
    other = host.reweighted(rng, blob)
    frames = host.random_frames(rng, PROFILE, 90)

    # 1. a second commit while one is scheduled: SWAP_PENDING, and the first stands
    core = await fresh(dut, blob, 1)
    await host.write_shadow(dut, other)
    core.write_shadow(other)
    await host.commit(dut, 12)
    core.commit(12)
    name = model_refusal(core.commit, 15)
    await host.commit(dut, 15)
    host.hold_words(test, "a second commit while one is scheduled", [await host.take_refusal(dut)], [host.code(name)])
    assert name == "SWAP_PENDING"
    # and a shadow write between a commit and its index
    name = model_refusal(core.write_shadow, blob)
    await host.write_shadow(dut, blob)
    host.hold_words(test, "a shadow write between a commit and its index", [await host.take_refusal(dut)], [host.code(name)])
    assert name == "SWAP_PENDING"
    await run(dut, core, frames[:14], test, "the first commit stands", gap_seed=1)
    # 2. outputs 12 to 14 mix (a pool of 4): a commit now is refused; after them it is taken
    name = model_refusal(core.commit, core.next_index + 5)
    await host.commit(dut, core.next_index + 5)
    host.hold_words(test, "a commit while outputs still mix", [await host.take_refusal(dut)], [host.code(name)])
    assert name == "SWAP_PENDING"
    await run(dut, core, frames[14:30], test, "past the mixing", gap_seed=2)
    # 3. a commit below the next index: SWAP_INDEX; at it: taken
    name = model_refusal(core.commit, core.next_index - 1)
    await host.commit(dut, core.next_index - 1)
    host.hold_words(test, "a commit one below the next index", [await host.take_refusal(dut)], [host.code(name)])
    assert name == "SWAP_INDEX"

    # 4. on an unbroken stream, a commit whose upper word lands at the edge that takes frame m and names m:
    #    the write is after the frame, so it is refused, SWAP_INDEX, and no swap happens
    core = await fresh(dut, blob, 1)
    await host.write_shadow(dut, other)
    core.write_shadow(other)
    m = 25

    async def writer():
        await host.taken(dut, m - 1)                     # the edge that took frame m-2 has passed
        await host.write_many(dut, host.commit_pairs(m))   # the upper word lands with frame m

    twin = Core(blob, 1)
    twin.write_shadow(other)
    for frame in frames[:m + 1]:
        twin.step(frame)
    name = model_refusal(twin.commit, m)                 # the model, asked after step m
    task = cocotb.start_soon(writer())
    await run(dut, core, frames[:60], test, "a commit that names the frame taken at its own edge", max_gap=0)
    await task
    host.hold_words(test, "that commit's refusal", [await host.take_refusal(dut)], [host.code(name)])
    assert name == "SWAP_INDEX"
    await host.all_seen()


# ------------------------------------------------------------------ four holes the verifier found, each now held

@cocotb.test()
async def commit_at_reads_back(dut):
    """`commit_at` is two words and reads back the index that is scheduled: its lower word AND its upper
    word, with an index of 2^32 and more scheduled so that the two differ; and zero when none is. The
    expected words of a scheduled commit are what the model's store holds for it. Zero for "none is
    scheduled" is the REGISTER MAP's word, not the model's: the model's store holds None there, which
    this test asserts first, and no number stands for None in the model."""
    caps = await begin(dut)
    rng = random.Random(SEED + 1100)
    test = "commit_at_reads_back"
    blob = host.random_blob(rng, PROFILE, caps, hidden=0, pool=1)
    for at in ((1 << host.WORD_BITS) + 5, (0x300 << host.WORD_BITS) | 0x89ABCDEF):
        core = await fresh(dut, blob)
        assert core.store._at is None
        seen = [await host.read(dut, "commit_at", 0), await host.read(dut, "commit_at", 1)]
        host.hold_words(test, "no commit is scheduled", seen, [0, 0])
        await host.commit(dut, at)
        core.commit(at)
        assert await quiet_refusal(dut) is None
        held = core.store._at                            # the index the model's store holds for the pending swap
        seen = [await host.read(dut, "commit_at", 0), await host.read(dut, "commit_at", 1)]
        host.hold_words(test, "a commit at %d: the lower word, the upper word" % at, seen,
                        [held & host.WORD_MASK, held >> host.WORD_BITS])
        assert seen[0] != seen[1]
    await host.all_seen()


AT_ZERO = ((2, 0), (5, 2), (3, 1), (4, 0), (8, 1))       # (pool, hidden units) for a commit at index 0


@cocotb.test()
async def bit_identity_swap_at_zero(dut):
    """A commit at index 0, with a pool of 2 and more: the swap is before the first output, no value was
    made under the old set, and NO output is marked as settling (model/weights.py, Store.step: the mixed
    outputs exist only when the index is at least 1). Every record carries the new epoch from the first.
    It is driven at the pools of `AT_ZERO` and at no other: a fault that marks settling at index 0 for one
    other pool size is not seen (docs/rtl/core.md, the limit on sampled sizes)."""
    caps = await begin(dut)
    rng = random.Random(SEED + 1200)
    settling = 1 << C.FLAGS["settling"]
    total = 0
    for n, (pool, hidden) in enumerate(AT_ZERO):
        blob = host.random_blob(rng, PROFILE, caps, hidden=min(hidden, caps["cap_hidden"]), pool=pool)
        other = host.reweighted(rng, blob)
        frames = host.random_frames(rng, PROFILE, 30)
        twin = Core(blob, 60 + n)
        twin.write_shadow(other)
        twin.commit(0)
        said = [twin.step(f) for f in frames]
        assert all(r["epoch"] == 61 + n and not r["flags"] & settling for r in said), "the model marks no output"
        core = await fresh(dut, blob, 60 + n)
        await host.write_shadow(dut, other)
        core.write_shadow(other)
        await host.commit(dut, 0)
        core.commit(0)
        assert await quiet_refusal(dut) is None
        total += (await run(dut, core, frames, "bit_identity_swap_at_zero", "pool %d, %d hidden unit(s)" % (pool, hidden),
                            gap_seed=n)).count
    assert total == len(AT_ZERO) * 30, total
    await host.all_seen()


@cocotb.test()
async def swap_epoch_on_the_edge(dut):
    """A write is ordered after a frame at its edge, for SWAP_EPOCH as for SWAP_INDEX. The core starts one
    below the last epoch with a swap scheduled at index 5. On an unbroken stream a second commit's upper
    word lands at the very edge that takes frame 5: the frame's swap comes first, the epoch is then the
    last its field holds, and the commit is refused, SWAP_EPOCH, as the model refuses it after step 5.
    A core that read the epoch before the frame would take it, and wrap the epoch to 0 at its index."""
    caps = await begin(dut)
    rng = random.Random(SEED + 1300)
    test = "swap_epoch_on_the_edge"
    blob = host.random_blob(rng, PROFILE, caps, hidden=1, pool=1)
    other = host.reweighted(rng, blob)
    frames = host.random_frames(rng, PROFILE, 40)
    core = await fresh(dut, blob, EPOCH_MAX - 1)
    await host.write_shadow(dut, other)
    core.write_shadow(other)
    await host.commit(dut, 5)
    core.commit(5)
    assert await quiet_refusal(dut) is None

    async def writer():
        await host.taken(dut, 4)                         # the edge that took frame 3 has passed
        await host.write_many(dut, host.commit_pairs(20))   # the lower word with frame 4, the upper with frame 5

    twin = Core(blob, EPOCH_MAX - 1)
    twin.write_shadow(other)
    twin.commit(5)
    for frame in frames[:6]:
        twin.step(frame)
    name = model_refusal(twin.commit, 20)                # the model, asked after step 5
    assert name == "SWAP_EPOCH"
    task = cocotb.start_soon(writer())
    await run(dut, core, frames, test, "a commit at the edge of the swap that reaches the last epoch", max_gap=0)
    await task
    host.hold_words(test, "that commit's refusal", [await host.take_refusal(dut)], [host.code(name)])
    await host.all_seen()


# ------------------------------------------------------------------ the controls, on the model side

def control_frames(n=24):
    """Three frames of zeros, then one with no zero sample, then more that vary by channel."""
    zero = (0,) * CHANNELS
    fourth = tuple(7 + 2 * c for c in range(CHANNELS))
    more = [tuple((i * 7 + c * 3) % 23 - 11 for c in range(CHANNELS)) for i in range(n - 4)]
    return [zero, zero, zero, fourth] + more


async def expect_mismatch(dut, blob, wrong, frames, test, label, at, field, epoch=0):
    """Load the right blob into the core, hand the harness a model built from the wrong one."""
    await harness.reset(dut)
    await host.load(dut, blob, epoch)
    try:
        await run(dut, wrong, frames, test, label)
    except harness.Mismatch as e:
        assert e.kind == "WORD" and e.at == at and field in e.detail, str(e)
        return
    raise AssertionError("the harness compared a wrong model (%s) and reported nothing" % label)


@cocotb.test()
async def control_model_coefficient_bit(dut):
    """One flipped coefficient bit in the MODEL must be reported, at the first record it changes: the
    newest sample's coefficient of row 0 at record 3, where the first sample that is not zero arrives;
    the coefficient one sample older, of row 1, at record 4."""
    caps = await begin(dut)
    rng = random.Random(SEED + 800)
    filters, rows, taps = every_tap(rng, caps)
    assert taps >= 2 and len(rows) >= 2
    blob = every_tap_blob(filters)
    mask = (1 << C.COEFF_BITS) - 1
    for row, back, bit, at in ((0, 0, 0, 3), (1, 1, C.COEFF_BITS - 1, 4)):
        k, c = rows[row]
        flipped = [dict((ch, list(v)) for ch, v in f.items()) for f in filters]
        raw = (flipped[k][c][taps - 1 - back] & mask) ^ (1 << bit)
        flipped[k][c][taps - 1 - back] = raw - (1 << C.COEFF_BITS) if raw >> (C.COEFF_BITS - 1) else raw
        await expect_mismatch(dut, blob, Core(every_tap_blob(flipped)), control_frames(),
                              "control_model_coefficient_bit", "bit %d of row %d, %d sample(s) back" % (bit, row, back),
                              at, "score")


@cocotb.test()
async def control_model_commit_late(dut):
    """The scripted model, handed a commit one output late, must be reported at the swap's own record."""
    caps = await begin(dut)
    rng = random.Random(SEED + 900)
    blob = host.random_blob(rng, PROFILE, caps, hidden=1, pool=1)
    other = host.reweighted(rng, blob)
    await harness.reset(dut)
    await host.load(dut, blob, 0)
    await host.write_shadow(dut, other)
    await host.commit(dut, 9)
    assert await quiet_refusal(dut) is None
    core = Core(blob, 0)
    core.write_shadow(other)
    late = host.Scripted(core, {4: [("commit", 10)]})
    try:
        await run(dut, late, host.random_frames(rng, PROFILE, 30), "control_model_commit_late", "a commit one output late")
    except harness.Mismatch as e:
        assert e.kind == "WORD" and e.at == 9 and "epoch" in e.detail, str(e)
        return
    raise AssertionError("the harness compared a model that swaps one output late and reported nothing")


@cocotb.test()
async def control_model_head_weights(dut):
    """A model whose hidden weights, or whose head weights, are other than the core's must be reported."""
    caps = await begin(dut)
    rng = random.Random(SEED + 1000)
    filters, rows, taps = every_tap(rng, caps)
    units = [[3, -5], [7, 11]]
    right = weights.pack(PROFILE, filters, [5, -9], PASS, 1, 1, units, 0, PASS)
    for label, wrong_units, wrong_head in (("one hidden weight one more", [[3, -5], [7, 12]], [5, -9]),
                                           ("one head weight one less", units, [5, -10])):
        wrong = weights.pack(PROFILE, filters, wrong_head, PASS, 1, 1, wrong_units, 0, PASS)
        await expect_mismatch(dut, right, Core(wrong), control_frames(), "control_model_head_weights", label, 3, "score")

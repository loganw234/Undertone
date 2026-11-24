"""The detector core built at the definition's maxima (rtl/core/core.sv at its defaults).

It runs once under each profile. This is the top where a capability, a width
and a bound are the definition's own, so this bench holds each against
`spec.constants` and against the model, which the small top's benches cannot.

  identity_block_reads_back     all fifteen registers of the read-only block against the package's
                                Python copy; `spec_hash` as eight words, the lowest first: the
                                convention docs/rtl/README.md's limit 9 says nothing held
  widths_are_the_models         every stage's elaborated width against `detector.widths` and
                                `detector.hidden_widths`
  bounds_are_the_models         one past each of the definition's maxima is refused by the core
                                under the name the model's own `pack` refuses it under
  bit_identity_largest_shape    THE IDENTITY TESTS. The largest shape: every row, every tap, every
                                hidden unit, every weight drawn over its whole range
  bit_identity_boundaries       the two widths that are a choice, at their boundary, by short real
                                runs: a hidden sum of exactly the lowest value the field holds
                                fits; one tap more does not, wraps, and the flag rises and stays
                                across a swap
  latency_is_eleven_clocks      the latency does not follow the build's size

WHAT THIS BENCH DOES NOT DO: the model's run at the true extremes, 65,663 frames with a pool of
65,536 full of extremes. So the pool's and the hidden sum's last bits at the definition's maxima
are held here by the comparison of widths and by nothing else; docs/rtl/core.md says so.
"""
import os
import random

import cocotb

from spec import constants as C
from model import detector, weights
from model.detector import Core
from model.refusal import Refusal

import harness
import core_host as host

PROFILE = os.environ["UNDERTONE_PROFILE"]
PROF = C.PROFILES[PROFILE]
CHANNELS = PROF["channels"]
PASS, ABS = C.RECTIFIERS["pass"], C.RECTIFIERS["abs"]
SCORE_BITS = dict((f[0], f[1]) for f in C.RECORDS["score"])["score"]
SEED = 2026112340
LATENCY = 11
SETTLE = 3 * LATENCY + 3
ONE_PRODUCT = PROF["sample_min"] * C.COEFF_MIN


async def begin(dut):
    harness.start_clock(dut)
    host.idle(dut)
    host.watch(dut)                                      # every record the design puts out in the test is counted
    await harness.reset(dut)
    return await host.capabilities(dut)


async def fresh(dut, blob, epoch=0):
    await harness.reset(dut)
    await host.load(dut, blob, epoch)
    return Core(blob, epoch)


def words(value, count):
    return [(value >> (i * host.WORD_BITS)) & host.WORD_MASK for i in range(count)]


@cocotb.test()
async def identity_block_reads_back(dut):
    harness.start_clock(dut)
    host.idle(dut)
    await harness.reset(dut)
    said = {
        "id": C.BUS["magic"],
        "spec_version": C.SPEC_VERSION,
        "spec_hash": int(C.SPEC_SHA256, 16),
        "cap_sample_bits": PROF["sample_bits"],
        "cap_channels": CHANNELS,
        "cap_coeff_bits": C.COEFF_BITS,
        "cap_filters": C.MAX_FILTERS,
        "cap_taps": C.MAX_TAPS,
        "cap_rows": C.MAX_ROWS,
        "cap_pool": C.MAX_POOL,
        "cap_score_shift": C.MAX_SCORE_SHIFT,
        "cap_hidden": C.MAX_HIDDEN,
        "cap_hidden_shift": C.MAX_HIDDEN_SHIFT,
        "cap_rectifiers": sum(1 << code for code in C.RECTIFIERS.values()),
        "cap_blob_versions": (1 << weights.VERSION) | (1 << weights.VERSION_HIDDEN),
    }
    block = [name for name, row in C.REGISTERS.items() if row[1] == "ro" and row[0] < C.REGISTERS["shape_sample_bits"][0]]
    assert sorted(block) == sorted(said), "this test states a value for every register of the read-only block"
    seen, expected, total = [], [], 0
    for name in block:
        count = C.REGISTERS[name][2]
        for word in range(count):
            seen.append(await host.read(dut, name, word))
        expected += words(said[name], count)
        total += count
    assert total == 22, total                            # fourteen registers of one word, and the hash's eight
    host.hold_words("identity_block_reads_back", "the read-only block, word by word", seen, expected)


def as_int(value):
    return value if isinstance(value, int) else value.to_unsigned()


@cocotb.test()
async def widths_are_the_models(dut):
    harness.start_clock(dut)
    host.idle(dut)
    await harness.reset(dut)
    core, model, hidden = host.inner(dut), detector.widths(PROFILE), detector.hidden_widths(PROFILE)
    stages = (("product", core.W_PROD, model["product"]), ("filter", core.W_FILT, model["filter"]),
              ("rectifier", core.W_RECT, model["rectifier"]), ("pool", core.W_POOL, model["pool"]),
              ("head", core.W_HEAD, model["head"]), ("hidden", core.u_head.W_HID, hidden["hidden"]),
              ("between", core.u_head.W_BTW, hidden["between"]), ("output", core.u_head.W_OUT, hidden["output"]),
              ("score", core.u_head.W_HID, model["score"]))
    seen = [as_int(handle.value) for _name, handle, _want in stages]
    host.hold_words("widths_are_the_models", "the nine widths: " + ", ".join(s[0] for s in stages), seen, [s[2] for s in stages])
    # and the registers themselves are that wide, where one register is one stage's values
    assert len(core.z_flat) == seen[3] * C.MAX_FILTERS, len(core.z_flat)
    assert len(core.s4_rect) == seen[2] * C.MAX_FILTERS, len(core.s4_rect)
    assert len(core.u_head.h2_b) == seen[6] * C.MAX_HIDDEN, len(core.u_head.h2_b)
    assert len(core.u_head.h1_prod) == seen[4] * C.MAX_HIDDEN * C.MAX_FILTERS, len(core.u_head.h1_prod)
    assert len(core.u_head.h3_prod) == seen[7] * C.MAX_HIDDEN, len(core.u_head.h3_prod)


def model_name(call, *args):
    try:
        call(*args)
    except Refusal as e:
        return e.name
    return None


@cocotb.test()
async def bounds_are_the_models(dut):
    """At this top the build's maxima are the definition's, so the model refuses the same shapes."""
    caps = await begin(dut)
    row, test = {0: [1]}, "bounds_are_the_models"
    cases = (
        ("one filter past", host.plain_shape(PROFILE, shape_filters=C.MAX_FILTERS + 1),
         model_name(weights.pack, PROFILE, [row] * (C.MAX_FILTERS + 1), [1] * (C.MAX_FILTERS + 1), PASS, 1, 0)),
        ("one tap past", host.plain_shape(PROFILE, shape_taps=C.MAX_TAPS + 1),
         model_name(weights.pack, PROFILE, [{0: [1] * (C.MAX_TAPS + 1)}], [1], PASS, 1, 0)),
        ("a pool one past", host.plain_shape(PROFILE, shape_pool=C.MAX_POOL + 1),
         model_name(weights.pack, PROFILE, [row], [1], PASS, C.MAX_POOL + 1, 0)),
        ("a score shift one past", host.plain_shape(PROFILE, shape_score_shift=C.MAX_SCORE_SHIFT + 1),
         model_name(weights.pack, PROFILE, [row], [1], PASS, 1, C.MAX_SCORE_SHIFT + 1)),
        ("one hidden unit past", host.plain_shape(PROFILE, shape_hidden=C.MAX_HIDDEN + 1),
         model_name(weights.pack, PROFILE, [row], [1] * (C.MAX_HIDDEN + 1), PASS, 1, 0, [[1]] * (C.MAX_HIDDEN + 1), 0, PASS)),
        ("a hidden shift one past", host.plain_shape(PROFILE, shape_hidden=1, shape_hidden_shift=C.MAX_HIDDEN_SHIFT + 1),
         model_name(weights.pack, PROFILE, [row], [1], PASS, 1, 0, [[1]], C.MAX_HIDDEN_SHIFT + 1, PASS)),
    )
    seen, expected = [], []
    for label, shape, name in cases:
        assert name is not None, "the model takes: " + label
        await harness.reset(dut)
        seen.append(await host.try_configure(dut, shape))
        expected.append(host.code(name))
    host.hold_words(test, "one past each of the definition's maxima, under the model's own names", seen, expected)
    # and exactly at each, the core takes the shape, as the model does
    at = (host.plain_shape(PROFILE, shape_filters=caps["cap_filters"]), host.plain_shape(PROFILE, shape_taps=caps["cap_taps"]),
          host.plain_shape(PROFILE, shape_pool=caps["cap_pool"]), host.plain_shape(PROFILE, shape_score_shift=caps["cap_score_shift"]),
          host.plain_shape(PROFILE, shape_hidden=caps["cap_hidden"]),
          host.plain_shape(PROFILE, shape_hidden=1, shape_hidden_shift=caps["cap_hidden_shift"]))
    seen = []
    for shape in at:
        await harness.reset(dut)
        seen.append(await host.try_configure(dut, shape))
    host.hold_words(test, "exactly at each of the definition's maxima", seen, [0] * len(at))


def extreme_sets(caps):
    sets, left = [], caps["cap_rows"]
    while left > 0 and len(sets) < caps["cap_filters"]:
        sets.append(list(range(min(CHANNELS, left))))
        left -= len(sets[-1])
    return sets


@cocotb.test()
async def bit_identity_largest_shape(dut):
    caps = await begin(dut)
    rng = random.Random(SEED)
    sets = extreme_sets(caps)
    assert sum(len(s) for s in sets) == C.MAX_ROWS
    total = 0
    for n, (hidden, pool) in enumerate(((caps["cap_hidden"], 3), (0, 2))):
        blob = host.blob_of(PROFILE, sets, caps["cap_taps"], rng, ABS if n == 0 else PASS, pool, 9, hidden, 11 if hidden else 0,
                            PASS if hidden else 0)
        other = host.reweighted(rng, blob)
        core = await fresh(dut, blob, 3)
        frames = host.random_frames(rng, PROFILE, 60)
        total += (await host.compare(dut, core, frames[:30], test="bit_identity_largest_shape",
                                        label="%d hidden unit(s): before" % hidden, gap_seed=n, settle=SETTLE)).count
        await host.write_shadow(dut, other)
        core.write_shadow(other)
        await host.commit(dut, core.next_index + 5)
        core.commit(core.next_index + 5)
        assert await host.take_refusal(dut) == 0
        total += (await host.compare(dut, core, frames[30:], test="bit_identity_largest_shape",
                                        label="%d hidden unit(s): a swap" % hidden, gap_seed=n + 5, settle=SETTLE)).count
    assert total == 2 * 60, total
    await host.all_seen()


def landing(caps):
    """(filters of one row, taps, pool) whose extreme products, under one hidden weight at its lowest,
    sum to exactly the lowest value the score field holds."""
    products, rest = divmod(1 << (SCORE_BITS - 1), -C.COEFF_MIN * ONE_PRODUCT)
    assert rest == 0
    k = 1
    while k * 2 <= caps["cap_filters"] and products % (k * 2) == 0:
        k *= 2
    t = 1                                                # taps and pool about equal: the shortest run that lands
    while t * 2 <= caps["cap_taps"] and (products // k) % (t * 2) == 0 and (t * 2) * (t * 2) <= products // k:
        t *= 2
    p = products // (k * t)
    assert k * t * p == products and p <= caps["cap_pool"], (k, t, p, products)
    return k, t, p


@cocotb.test()
async def bit_identity_boundaries(dut):
    caps = await begin(dut)
    rng = random.Random(SEED + 1)
    k, t, p = landing(caps)
    low = (PROF["sample_min"],) * CHANNELS
    quiet = (0,) * CHANNELS
    one_row = [[c % CHANNELS] for c in range(k)]
    lowest = -(1 << (SCORE_BITS - 1))
    flag = 1 << C.FLAGS["overflow"]
    total = 0

    def blob_of(pool, units, head, between):
        filters = [dict((c, [C.COEFF_MIN] * t) for c in s) for s in one_row]
        return weights.pack(PROFILE, filters, head, PASS, pool, 0, [[C.COEFF_MIN] * k] * units, 0, between)

    # the hidden value: exactly the lowest the field holds, under pass and a head weight of 1. It fits.
    blob = blob_of(p, 1, [1], PASS)
    frames = [low] * (t + p - 1 + 2)
    said = list(Core(blob).run(frames))
    assert said[-1] == {"index": len(frames) - 1, "epoch": 0, "flags": 0, "score": lowest}, said[-1]
    core = await fresh(dut, blob)
    total += (await host.compare(dut, core, frames, test="bit_identity_boundaries", label="a hidden sum of exactly the lowest value",
                                    gap_seed=1, max_gap=1, settle=SETTLE)).count
    # a pool twice as long holds more than the field can: the value does not fit, wraps, and the flag
    # rises during the stretch of extremes and stays, across a swap and after the sum is back in range
    if 2 * p <= caps["cap_pool"]:
        blob = blob_of(2 * p, 1, [1], PASS)
        other = weights.pack(PROFILE, [dict((c, [1] * t) for c in s) for s in one_row], [1], PASS, 2 * p, 0, [[1] * k], 0, PASS)
        frames = [low] * (t + p + 2) + [quiet] * (t + 2 * p + 4)
        check = Core(blob)
        check.write_shadow(other)
        check.commit(t + p + 3)
        said = [check.step(f) for f in frames]
        assert said[0]["flags"] == 0 and said[t + p + 1]["flags"] == flag, (said[0], said[t + p + 1])
        assert said[-1]["flags"] == flag and said[-1]["epoch"] == 1 and said[-1]["score"] == 0, said[-1]
        core = await fresh(dut, blob)
        total += (await host.compare(dut, core, frames[:t + p + 2], test="bit_identity_boundaries",
                                        label="one sample past it: the flag rises", gap_seed=2, max_gap=1, settle=SETTLE)).count
        await host.write_shadow(dut, other)
        core.write_shadow(other)
        await host.commit(dut, core.next_index + 1)
        core.commit(core.next_index + 1)
        assert await host.take_refusal(dut) == 0
        total += (await host.compare(dut, core, frames[t + p + 2:], test="bit_identity_boundaries",
                                        label="the flag stays, across a swap", gap_seed=3, max_gap=1, settle=SETTLE)).count
    # the score's own stage: two units at the lowest value under head weights of 1 sum to -2^64
    if caps["cap_hidden"] >= 2:
        blob = blob_of(p, 2, [1, 1], PASS)
        frames = [low] * (t + p - 1 + 2)
        said = list(Core(blob).run(frames))
        assert said[-1]["score"] == 0 and said[-1]["flags"] == flag, said[-1]
        core = await fresh(dut, blob)
        total += (await host.compare(dut, core, frames, test="bit_identity_boundaries", label="the score does not fit",
                                        gap_seed=4, max_gap=1, settle=SETTLE)).count
        # and between's last bit: under abs the lowest value folds to one past the field's highest
        blob = blob_of(p, 2, [C.COEFF_MIN, C.COEFF_MAX], ABS)
        core = await fresh(dut, blob)
        total += (await host.compare(dut, core, frames, test="bit_identity_boundaries", label="between, one past the field's highest",
                                        gap_seed=5, max_gap=1, settle=SETTLE)).count
    assert total > 0
    await host.all_seen()


@cocotb.test()
async def latency_is_eleven_clocks(dut):
    caps = await begin(dut)
    rng = random.Random(SEED + 2)
    blob = host.random_blob(rng, PROFILE, caps, hidden=2, pool=2, taps=3)
    core = await fresh(dut, blob)
    result = await host.compare(dut, core, host.random_frames(rng, PROFILE, 30), test="latency_is_eleven_clocks",
                                   label="thirty frames", settle=SETTLE)
    assert result.latencies == [LATENCY], result.latencies
    await host.all_seen()

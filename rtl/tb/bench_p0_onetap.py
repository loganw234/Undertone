"""The bench that proves the bit-identity harness, on the filter of one tap (rtl/p0/onetap.sv).

It runs once under each profile: the runner sets UNDERTONE_PROFILE and builds
the filter with that profile's SAMPLE_BITS and CHANNELS.

Two tests hold the filter against the model, on every score record:

  bit_identity_random     seeded random configurations and frames
  bit_identity_extremes   thirty-two configurations: the coefficient, the
                          head weight, the rectifier, the shift and the epoch
                          each at both of its ends. Within one configuration
                          the channels' coefficients alternate between the two
                          extremes: it is NOT every combination of coefficient
                          across the channels. Each over every frame whose
                          samples are each an extreme, zero, one or minus one

One states the filter's latency, and the rest are the harness's own negative
controls on the MODEL side: each hands `compare` a model that is wrong in one
place and requires a Mismatch at the record this file predicts. The controls
on the RTL side are the mutants in benches.toml: the runner patches a copy of
the filter and requires these same identity tests to fail.

Why the predicted record is 3: every control stream starts with three frames
of zeros, which score 0 under any coefficient, head, rectifier or shift, and
its fourth frame is chosen so the filter's sum is negative and odd after the
head, so that each single change (a coefficient bit, a head bit, the shift,
the rectifier) changes the fourth score. A changed epoch shows in record 0.
"""
import os
import random

import cocotb

from spec import constants as C
from model import weights
from model.detector import Core

import harness

PROFILE = os.environ["UNDERTONE_PROFILE"]
PROF = C.PROFILES[PROFILE]
CHANNELS = PROF["channels"]
COEFF_MASK = (1 << C.COEFF_BITS) - 1
EPOCH_MAX = (1 << dict((f[0], f[1]) for f in C.RECORDS["score"])["epoch"]) - 1
SEED = 2026112310


def configure(dut, coef, head, rectifier, shift, epoch):
    """Load one configuration into the filter's ports."""
    word = 0
    for c, w in enumerate(coef):
        word |= (w & COEFF_MASK) << (c * C.COEFF_BITS)
    dut.cfg_coef.value = word
    dut.cfg_head.value = head & COEFF_MASK
    dut.cfg_rectifier.value = rectifier
    dut.cfg_shift.value = shift
    dut.cfg_epoch.value = epoch


def model(coef, head, rectifier, shift, epoch):
    """The reference model's core at the same configuration: one filter of one tap reading every channel."""
    blob = weights.pack(PROFILE, [{c: [w] for c, w in enumerate(coef)}], [head], rectifier, 1, shift)
    return Core(blob, epoch)


async def one_run(dut, config, frames, test, label, model_config=None, **kw):
    await harness.reset(dut)
    configure(dut, *config)
    await harness.reset(dut)
    return await harness.compare(dut, model(*(model_config or config)), frames, test=test, label=label, **kw)


@cocotb.test()
async def bit_identity_random(dut):
    harness.start_clock(dut)
    rng = random.Random(SEED)
    total = 0
    for n in range(12):
        config = ([rng.randint(C.COEFF_MIN, C.COEFF_MAX) for _ in range(CHANNELS)],
                  rng.randint(C.COEFF_MIN, C.COEFF_MAX),
                  rng.choice(sorted(C.RECTIFIERS.values())),
                  rng.randint(0, C.MAX_SCORE_SHIFT),
                  rng.randint(0, EPOCH_MAX))
        frames = [tuple(rng.randint(PROF["sample_min"], PROF["sample_max"]) for _ in range(CHANNELS))
                  for _ in range(200)]
        result = await one_run(dut, config, frames, "bit_identity_random", "configuration %d" % n, gap_seed=SEED + n)
        total += result.count
    assert total == 12 * 200, total


@cocotb.test()
async def bit_identity_extremes(dut):
    harness.start_clock(dut)
    values = sorted({PROF["sample_min"], PROF["sample_max"], 0, 1, -1})
    frames = [()]
    for _ in range(CHANNELS):
        frames = [f + (v,) for f in frames for v in values]
    n = 0
    for coef_value in (C.COEFF_MIN, C.COEFF_MAX):
        for head in (C.COEFF_MIN, C.COEFF_MAX):
            for rectifier in sorted(C.RECTIFIERS.values()):
                for shift in (0, C.MAX_SCORE_SHIFT):
                    for epoch in (0, EPOCH_MAX):
                        # The channels' coefficients alternate between the two extremes, so no two
                        # neighbours carry the same one and a fault in one channel cannot hide.
                        coef = [coef_value if c % 2 == 0 else (C.COEFF_MIN + C.COEFF_MAX - coef_value)
                                for c in range(CHANNELS)]
                        expected_model = model(coef, head, rectifier, shift, epoch)
                        await harness.reset(dut)
                        configure(dut, coef, head, rectifier, shift, epoch)
                        await harness.reset(dut)
                        await harness.compare(dut, expected_model, frames, test="bit_identity_extremes",
                                              label="configuration %d" % n, gap_seed=n)
                        n += 1
    assert n == 32, n


@cocotb.test()
async def latency_is_one_clock(dut):
    """rtl/p0/onetap.sv states it: a frame taken at one rising edge is out at the next."""
    harness.start_clock(dut)
    frames = [tuple(c + i for c in range(CHANNELS)) for i in range(40)]
    result = await one_run(dut, ([3] * CHANNELS, 1, C.RECTIFIERS["pass"], 0, 7), frames,
                           "latency_is_one_clock", "forty frames")
    assert result.latencies == [1], result.latencies


# ---- the harness's negative controls, on the model side ----

BASE = ([5, -7, 11][:CHANNELS], 3, C.RECTIFIERS["pass"], 1, 9)


def control_frames():
    """Three frames of zeros, then one whose filter sum under BASE is negative: -45 for one channel
    (5 * -9), -51 for three (5 * -9 + -7 * 4 + 11 * 2). Then twenty more that vary by channel."""
    zero = (0,) * CHANNELS
    fourth = (-9, 4, 2)[:CHANNELS]
    more = [tuple((i * 7 + c * 3) % 23 - 11 for c in range(CHANNELS)) for i in range(20)]
    return [zero, zero, zero, fourth] + more


async def expect_mismatch(dut, test, label, model_config, at, field):
    try:
        await one_run(dut, BASE, control_frames(), test, label, model_config=model_config)
    except harness.Mismatch as e:
        assert e.kind == "WORD" and e.at == at and ("field(s) %s differ" % field) in e.detail, str(e)
        return
    raise AssertionError("the harness compared a wrong model (%s) and reported nothing" % label)


@cocotb.test()
async def control_model_coefficient_bit(dut):
    """One flipped coefficient bit in the MODEL must be reported, at the first record it changes."""
    harness.start_clock(dut)
    coef, head, rectifier, shift, epoch = BASE
    last = CHANNELS - 1
    for bit in (0, C.COEFF_BITS - 1):
        flipped = list(coef)
        raw = (flipped[last] & COEFF_MASK) ^ (1 << bit)
        flipped[last] = raw - (1 << C.COEFF_BITS) if raw >> (C.COEFF_BITS - 1) else raw
        await expect_mismatch(dut, "control_model_coefficient_bit", "bit %d of channel %d" % (bit, last),
                              (flipped, head, rectifier, shift, epoch), 3, "score")


@cocotb.test()
async def control_model_other_fields(dut):
    """A model wrong in its head weight, its shift, its rectifier or its epoch must each be reported."""
    harness.start_clock(dut)
    coef, head, rectifier, shift, epoch = BASE
    await expect_mismatch(dut, "control_model_other_fields", "head weight one less",
                          (coef, head - 1, rectifier, shift, epoch), 3, "score")
    await expect_mismatch(dut, "control_model_other_fields", "shift one more",
                          (coef, head, rectifier, shift + 1, epoch), 3, "score")
    await expect_mismatch(dut, "control_model_other_fields", "rectifier abs",
                          (coef, head, C.RECTIFIERS["abs"], shift, epoch), 3, "score")
    await expect_mismatch(dut, "control_model_other_fields", "epoch one more",
                          (coef, head, rectifier, shift, epoch + 1), 0, "epoch")


@cocotb.test()
async def control_nothing_compared(dut):
    """Zero frames is not a pass: the harness must say so."""
    harness.start_clock(dut)
    await harness.reset(dut)
    configure(dut, *BASE)
    try:
        await harness.compare(dut, model(*BASE), [], test="control_nothing_compared", label="no frames")
    except harness.NothingCompared:
        return
    raise AssertionError("the harness accepted an empty comparison")

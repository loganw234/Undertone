"""The detector core's overflow flag, over all its sources together and in both directions (docs/rtl/flag.md).

It runs on two tops, each under both profiles: `core_small` (three hidden units) and
`core_twelve` (rtl/flag/core_twelve.sv: the same bank with the definition's twelve).
The flag's sources are each hidden unit's value and the score; at one output each
fits, leaves its field upward or leaves it downward. Every case is made by
construction in rtl/tb/flag_cases.py and checked there BEFORE the design runs: by
that file's own evaluator (the case is what its label says) and by the model (its
flag is 0 before the case's first excursion and set from it, and its score is the
evaluator's at every output). Then the harness holds every word of the design's
records against the model's.

SIX IDENTITY TESTS, each through `harness.compare`:

  flag_vclose_both_sources_at_once  round 2's closing verifier's first stream, as kept: a hidden value
                                    and the score out at one output
  flag_vclose_overflow_upward       its second: a hidden value out upward
  flag_every_state                  on three units, every state of the four sources at the first output
                                    where any leaves its field (81 cases); on twelve, the structure of
                                    flag.md section 3 (44 cases). Under s16x1 the tier rule of flag.md
                                    section 6 cuts both (FULL_S16X1 below)
  flag_one_route                    no hidden layer: the source out upward, downward, and nothing out
  flag_stays                        the flag rises, every source comes back into its field, and the flag
                                    stays: from a unit (s24x3) and from the score (both)
  flag_far                          a first excursion past 2^64: the score up and down (both profiles); a
                                    hidden value up and down by a swap (s24x3: under s16x1 these builds'
                                    hidden sum is 65 bits and no hidden value reaches 2^64)

ONE MORE, not an identity test since its words are register words:

  flag_status_reads_the_flag        the status bit `overflow` after a stream with nothing out, after the
                                    score's excursion, and after its return, held by `harness.hold` to the
                                    model's sticky flag

WHAT THIS BENCH CANNOT SEE is docs/rtl/flag.md's list of limits: sizes other than
three and twelve units, twelve units not whole, values the family does not reach,
the hidden shift and between at other settings, the bank, and the rest.
"""
import os

import cocotb

from spec import constants as C
from model import weights
from model.detector import Core

import harness
import core_host as host
import flag_cases as F

PROFILE = os.environ["UNDERTONE_PROFILE"]
PROF = C.PROFILES[PROFILE]
CHANNELS = PROF["channels"]
PASS = C.RECTIFIERS["pass"]
SCORE_BITS = F.FIELD
LATENCY = 11
SETTLE = 3 * LATENCY + 3
ONE_PRODUCT = PROF["sample_min"] * C.COEFF_MIN
FULL_S16X1 = False               # the tier rule of docs/rtl/flag.md section 6: False runs the cut sets under s16x1


async def begin(dut):
    """Clock, an idle register port, a reset, the build's capabilities; every record from here on is counted."""
    harness.start_clock(dut)
    host.idle(dut)
    host.watch(dut)
    await harness.reset(dut)
    return await host.capabilities(dut)


async def fresh(dut, blob, epoch=0):
    await harness.reset(dut)
    await host.load(dut, blob, epoch)
    return Core(blob, epoch)


async def run(dut, core, frames, test, label, **kw):
    kw.setdefault("settle", SETTLE)
    return await host.compare(dut, core, frames, test=test, label=label, **kw)


async def run_case(dut, case, test, seed):
    """The check before the design runs, then the design: reset, load, the swap if any, the stream."""
    case.model_agrees(Core)
    await harness.reset(dut)
    await host.load(dut, case.blob)
    core = case.model(Core)
    if case.swap:
        await host.write_shadow(dut, case.blob_b)
        await host.commit(dut, case.swap[0])
        assert await host.take_refusal(dut) == 0, "the swap of case '%s' was refused" % case.label
    result = await run(dut, core, case.frames, test, case.label, gap_seed=seed, max_gap=0 if len(case.frames) > 100 else 1)
    assert result.count == len(case.frames), (case.label, result.count)
    return core


# ------------------------------------------------------------------ the closing verifier's two streams, as kept

def all_low(sets, taps):
    return [dict((c, [C.COEFF_MIN] * taps) for c in s) for s in sets]


def vclose_shape(caps):
    k, t = caps["cap_filters"], min(4, caps["cap_taps"])
    products, rest = divmod(1 << (SCORE_BITS - 1), -C.COEFF_MIN * ONE_PRODUCT)
    p, rest2 = divmod(products, k * t)
    assert rest == 0 and rest2 == 0 and 1 <= p <= caps["cap_pool"]
    one_row = [[c % CHANNELS] for c in range(k)]
    return k, t, p, one_row


@cocotb.test()
async def flag_vclose_both_sources_at_once(dut):
    """VCLOSE: a hidden value that does not fit AND an output sum that does not fit, first at the same output.
    Unit 0's weights are the lowest, unit 1's half of that; head weights 1 and -2: the output sum is exactly 0
    while unit 0 fits, and exactly 2^64 from the output where unit 0 wraps."""
    caps = await begin(dut)
    k, t, p, one_row = vclose_shape(caps)
    assert caps["cap_hidden"] >= 2
    low = (PROF["sample_min"],) * CHANNELS
    flag = 1 << C.FLAGS["overflow"]
    frames = [low] * (t + p + 3)
    hidden = [[C.COEFF_MIN] * k, [C.COEFF_MIN // 2] * k]
    blob = weights.pack(PROFILE, all_low(one_row, t + 1), [1, -2], PASS, p, 0, hidden, 0, PASS)
    said = list(Core(blob).run(frames))
    assert said[0]["flags"] == 0 and said[-1]["flags"] == flag and all(r["score"] == 0 for r in said), said[-1]
    first = min(i for i, r in enumerate(said) if r["flags"] == flag)
    dut._log.info("VCLOSE both-sources: the model's flag first rises at record %d of %d" % (first, len(said)))
    core = await fresh(dut, blob)
    got = await run(dut, core, frames, "flag_vclose_both_sources_at_once", "hidden and output overflow at one output",
                    gap_seed=21, max_gap=1)
    assert got.count == t + p + 3, got.count
    await host.all_seen()


@cocotb.test()
async def flag_vclose_overflow_upward(dut):
    """VCLOSE: one unit whose hidden sum passes the field's HIGHEST value (hidden weights at their highest on
    products that are all positive), every head weight zero."""
    caps = await begin(dut)
    k, t, p, one_row = vclose_shape(caps)
    low = (PROF["sample_min"],) * CHANNELS
    flag = 1 << C.FLAGS["overflow"]
    frames = [low] * (t + p + 3)
    blob = weights.pack(PROFILE, all_low(one_row, t + 1), [0], PASS, p, 0, [[C.COEFF_MAX] * k], 0, PASS)
    said = list(Core(blob).run(frames))
    assert said[0]["flags"] == 0 and said[-1]["flags"] == flag and all(r["score"] == 0 for r in said), said[-1]
    first = min(i for i, r in enumerate(said) if r["flags"] == flag)
    dut._log.info("VCLOSE upward: the model's flag first rises at record %d of %d" % (first, len(said)))
    core = await fresh(dut, blob)
    got = await run(dut, core, frames, "flag_vclose_overflow_upward", "a hidden sum past the field's highest value",
                    gap_seed=22, max_gap=1)
    assert got.count == t + p + 3, got.count
    await host.all_seen()


# ------------------------------------------------------------------ every state

def state_cases(fam):
    """E1 on three units, E2 on twelve; the cut sets under s16x1 when the tier rule says so."""
    full = PROFILE != "s16x1" or FULL_S16X1
    if fam.H == 3:
        cases = fam.every_state() if full else fam.every_state_cut()
        assert len(cases) == (81 if full else 11), len(cases)
    else:
        assert fam.H == 12, "this bench has a case list for three units and for twelve"
        cases = fam.twelve() if full else fam.twelve_cut()
        assert len(cases) == (44 if full else 4), len(cases)
    return cases, full


@cocotb.test()
async def flag_every_state(dut):
    caps = await begin(dut)
    fam = F.Family(PROFILE, caps)
    cases, full = state_cases(fam)
    dut._log.info("flag_every_state: %d units, %d cases (%s), i* = %d" % (fam.H, len(cases), "whole" if full else "cut", fam.istar))
    total = 0
    for n, case in enumerate(cases):
        await run_case(dut, case, "flag_every_state", n)
        total += len(case.frames)
    assert total == sum(len(c.frames) for c in cases)
    await host.all_seen()


@cocotb.test()
async def flag_one_route(dut):
    caps = await begin(dut)
    fam = F.Family(PROFILE, caps)
    for n, d in enumerate((F.UP, F.DOWN, F.FIT)):
        await run_case(dut, fam.one_route_case(d), "flag_one_route", n)
    await host.all_seen()


def stays_cases(fam):
    cases = [fam.short_score_case(F.UP, 4, 2, quiet=fam.T + 4 + 2, label="the score up at output 2, then back in")]
    if PROFILE == "s24x3":
        cases.insert(0, fam.short_unit_case(F.UP, 8, fam.T + 8 + 2, "unit 0 up at i*, then back in"))
    return cases


@cocotb.test()
async def flag_stays(dut):
    """The flag rises, every source comes back into its field, and the flag stays to the stream's end. Under
    s16x1 only the score's return is run: a unit's needs a pool of about 690 and as many frames of zeros."""
    caps = await begin(dut)
    fam = F.Family(PROFILE, caps)
    for n, case in enumerate(stays_cases(fam)):
        back = case.back_in()
        assert back is not None and back < len(case.frames) - 1, "case '%s' never comes back in" % case.label
        dut._log.info("flag_stays: '%s' is out at %d and back in at %d of %d" % (case.label, case.istar, back, len(case.frames)))
        await run_case(dut, case, "flag_stays", n)
    await host.all_seen()


@cocotb.test()
async def flag_far(dut):
    caps = await begin(dut)
    fam = F.Family(PROFILE, caps)
    cases = [fam.far_score_case(F.UP), fam.far_score_case(F.DOWN)]
    if fam.far_unit_reachable():
        cases += [fam.far_unit_case(F.DOWN), fam.far_unit_case(F.UP)]
    else:
        dut._log.info("flag_far: no hidden value of this build reaches 2^64 under %s; the score's two only" % PROFILE)
    for n, case in enumerate(cases):
        await run_case(dut, case, "flag_far", n)
    await host.all_seen()


@cocotb.test()
async def flag_status_reads_the_flag(dut):
    """The status register's bit `overflow` is the sticky flag: read after a stream with nothing out, after the
    score's excursion, and after the score has come back into its field, and held to the model's flag."""
    caps = await begin(dut)
    fam = F.Family(PROFILE, caps)
    cases = [fam.short_score_case(F.FIT, 4, 2, label="nothing out"), fam.short_score_case(F.UP, 4, 2),
             fam.short_score_case(F.UP, 4, 2, quiet=fam.T + 4 + 2, label="the score up at output 2, then back in")]
    seen, said = [], []
    for n, case in enumerate(cases):
        core = await run_case(dut, case, "flag_status_reads_the_flag", n)
        seen.append((await host.read(dut, "status") >> host.status_bit("overflow")) & 1)
        said.append(int(core.overflow))
    assert said == [0, 1, 1], said
    host.hold_words("flag_status_reads_the_flag", "the status bit overflow after: " + "; ".join(c.label for c in cases),
                    seen, said)
    await host.all_seen()

"""The learner in the seam's chain (rtl/learn/learn_chain.sv), held to `model.run.learning` word for word.

The chain is the source, the injector and the core with the learner beside the core, at the definition's
bounds for the learner: 128 taps at most, count_bits 32, an update time of 256 frames. Its truth is the
injector's: the index of each record the injector takes into its store. Every run is held whole by
`learn_host.Chain.run`: every score record against the model's (`harness.hold`), each host operation's two
refusal registers against the model's outcome, the eight counts and `lrn_status` at the end, and the
injector's refusal 0.

  update_finishes_within_f   at the definition's 128 taps, at the chain's rate: a commit at the last clock
                             of u + F - 1 refused UPDATE_UNFINISHED, at the first of u + F taken. The clock
                             the learner's last write was taken is logged, as evidence of the margin
  truth_isolation            the same samples under three wordings of the truth: 3/1, 6/2, and 3/1 with an
                             added record of amplitude 0. Identical records up to the named commit, and after
                             it each the model's with its own learner's set; the sets of the first and the
                             third differ
  a_record_offered_late      the race: under s24x3 a record offered once the core's next index has reached it
                             and before the injector takes that frame, with an update named there; under s16x1
                             the same offer is refused by the injector, INJECT_OVERLAP
  bit_identity_e1_flow       E1's layout at 64 taps: eight records 128 apart, the update at the training's end,
                             a host shadow write and a commit refused while it runs, the commit at its finish
  full_at_thirty_two_bits    FULL at count_bits 32, from a count written at 2^32 - 2 into both sides
  one_bus_four_blocks        a word of each block, a refusal latched in each and each cleared in turn

WHAT IT CANNOT SEE, each a stated limit of docs/rtl/learn.md: the injector holds e0 alone, so no wording
here changes a pulse id; a coefficient is seen through the noise, not alone (bench_learn.py reads each
alone); the streams are the ones named.
"""
import os

import cocotb
from cocotb.triggers import FallingEdge

from spec import constants as C

import harness
import core_host as host
import learn_host as lh
import seam_host
import source_bus

PROFILE = os.environ["UNDERTONE_PROFILE"]
CH = C.PROFILES[PROFILE]["channels"]
SIGMA = (50, 1) if CH == 1 else (97, 2)
F = C.LEARN_UPDATE_FRAMES


def record(index, num=3, den=1):
    return {"index": index, "pulse_id": 0, "amplitude_num": num, "amplitude_den": den}


def case(taps, schedule, frames, seed=20261125):
    return seam_host.Case(PROFILE, seed, SIGMA, frames, schedule, lh.start_blob(PROFILE, taps))


@cocotb.test()
async def update_finishes_within_f(dut):
    chain = lh.Chain(dut)
    t = C.MAX_TAPS
    u = 520
    c = case(t, [record(128), record(384)], 830)
    script = {10: [("update", u)], u + F - 1: [("commit", 790)], u + F: [("commit", 790)]}
    placement = {(u + F - 1, 0): "last", (u + F, 0): "with"}
    margin = {}

    async def watch_done():
        lrn = dut.u_learn
        while "done" not in margin:
            await FallingEdge(dut.clk)
            made, done = str(lrn.upd_made.value) == "1", str(lrn.upd_done.value) == "1"
            if made and "made" not in margin:
                margin["made"] = (chain.bus.edges, chain.index())
            if made and done:
                margin["done"] = (chain.bus.edges, chain.index())

    cocotb.start_soon(watch_done())
    learner, _records = await chain.run("update_finishes_within_f", "F at 128 taps", c, script, placement=placement)
    assert learner.counters()["lrn_early"] == 1 and learner.counters()["lrn_made"] == 1, learner.counters()
    (e0, i0), (e1, i1) = margin["made"], margin["done"]
    budget = (F - 1) * seam_host.period(PROFILE)
    cocotb.log.info("LEARN-MARGIN %s: made at next index %d, edge %d; done at next index %d, edge %d: %d clocks, "
                    "against %d in F - 1 frames" % (PROFILE, i0, e0, i1, e1, e1 - e0, budget))
    assert e1 - e0 < budget, "the update took %d clocks, past %d" % (e1 - e0, budget)


@cocotb.test()
async def truth_isolation(dut):
    chain = lh.Chain(dut)
    t = 32
    u = 400
    commit = u + F + 4
    base = [64, 128, 192, 256]
    wordings = [("3/1", [record(j, 3, 1) for j in base]),
                ("6/2, the same samples", [record(j, 6, 2) for j in base]),
                ("3/1 and a record of amplitude 0 at 321", [record(j, 3, 1) for j in base] + [record(321, 0, 1)])]
    script = {10: [("update", u)], u + F: [("commit", commit)]}
    runs = []
    for label, schedule in wordings:
        c = case(t, schedule, 700)
        learner, records = await chain.run("truth_isolation", label, c, script)
        runs.append((learner, records))
    # the model says the three add the same samples, and the third's learner has one more record
    a, b, x = runs
    assert a[1] == b[1], "the model gives 3/1 and 6/2 other records"
    assert a[1][:commit] == x[1][:commit], "the model's records differ before the commit"
    sa, sx = a[0].updates[0]["blob"], x[0].updates[0]["blob"]
    assert sa is not None and sx is not None and sa != sx, "the two learners' sets do not differ: nothing is compared"
    assert a[1][commit:] != x[1][commit:], "after the commit the two learners' records do not differ"


@cocotb.test()
async def a_record_offered_late(dut):
    chain = lh.Chain(dut)
    t = 16
    late = record(96)
    if CH == 1:
        # at the chain's rate under s16x1 the injector has taken frame 96 before the core's next index is 96:
        # the offer is behind its frame, and refused
        c = case(t, [record(32), late], 200)
        await chain.start(c, [late])
        await chain.until(96, seam_host.period(PROFILE) * 200, "for the late offer")
        await chain.bus.write_many(seam_host.truth_writes(late))
        refused = await chain.bus.read(source_bus.offset("inj_refusal"))
        assert refused == C.REFUSAL_CODES["INJECT_OVERLAP"], "the injector says %d" % refused
        return
    u = 96
    c = case(t, [record(32), late], u + F + 40)
    script = {10: [("update", u)], u + F: [("commit", u + F + 4)]}
    learner, _ = await chain.run("a_record_offered_late", "a record offered once the core's next index is its own",
                                 c, script, late={96: [late]})
    assert learner.updates[0]["counts"] == (2, 1), learner.updates[0]["counts"]


@cocotb.test()
async def bit_identity_e1_flow(dut):
    chain = lh.Chain(dut)
    t = 64
    records = [record(64 + 128 * k) for k in range(8)]
    u = 64 + 128 * 7 + t + 2
    commit = u + F + 8
    script = {10: [("update", u)], u + 4: [("write_shadow", lh.start_blob(PROFILE, t))], u + 10: [("commit", commit)],
              u + F: [("commit", commit)]}
    learner, _ = await chain.run("bit_identity_e1_flow", "eight records 128 apart at 64 taps",
                                 case(t, records, commit + 40), script)
    assert learner.counters()["lrn_count0"] == 8 and learner.counters()["lrn_count1"] == 8, learner.counters()


@cocotb.test()
async def full_at_thirty_two_bits(dut):
    """FULL at the definition's count_bits, 32, from a state written into both sides: label 0's count at
    2^32 - 2, so that its next window takes it to its most and the two after are FULL. The update after them is
    of a count of 2^32 - 1, so D and the division run near their 32-bit widths."""
    chain = lh.Chain(dut)
    t = 16
    most = (1 << C.LEARN_COUNT_BITS) - 1

    def written(learner):
        learner.counts[0] = most - 1

    async def written_rtl(d):
        d.u_learn.cnt0.value = most - 1

    u = 200
    commit = u + F + 4
    c = case(t, [record(32), record(96), record(160)], commit + 40)
    script = {10: [("update", u)], u + F: [("commit", commit)]}
    learner, _ = await chain.run("full_at_thirty_two_bits", "label 0 at its most of 2^32 - 1", c, script,
                                 before=written, before_rtl=written_rtl)
    got = learner.counters()
    assert got["lrn_count0"] == most and got["lrn_skip_full"] == 2 and learner.updates[0]["counts"][0] == most, got


@cocotb.test()
async def one_bus_four_blocks(dut):
    chain = lh.Chain(dut)
    b = chain.bus
    await b.reset()
    words = [("id", C.BUS["magic"]), ("cap_noise_table", C.MAX_NOISE_TABLE), ("cap_inject_pending", C.MAX_INJECT_PENDING),
             ("lrn_cap_count_bits", C.LEARN_COUNT_BITS), ("lrn_cap_update_frames", C.LEARN_UPDATE_FRAMES)]
    seen = [await b.read(source_bus.offset(name)) for name, _ in words]
    expected = [value for _, value in words]
    # a refusal latched in each block by a write to one of its read-only rows; then each cleared in turn
    ro = [("id", "refusal"), ("cap_noise_table", "src_refusal"), ("cap_inject_pending", "inj_refusal"),
          ("lrn_status", "lrn_refusal")]
    for row, _ in ro:
        await b.write(source_bus.offset(row), 1)
    access = C.REFUSAL_CODES["REGISTER_ACCESS"]
    for k in range(len(ro)):
        for _row, reg in ro:
            seen.append(await b.read(source_bus.offset(reg)))
        expected += [0] * k + [access] * (len(ro) - k)
        await b.write(source_bus.offset(ro[k][1]), 0)
    host.hold_words("one_bus_four_blocks", "five words, then four refusal registers cleared in turn", seen, expected)

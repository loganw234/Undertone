"""The learner in the kernel: rtl/krnl/undertone_krnl.sv itself, the packaged top at its defaults, with
rtl/learn/learn.sv and learn_port.sv inside it. Parcel KRNL-L, round 5; docs/rtl/krnl-learn.md.

The kernel is driven ONLY as a host would drive it, through its AXI4-Lite port and its memory
(rtl/tb/krnl_host.py, krnl_mem.py, krnl_learn_host.py); nothing here reads a signal inside the top. Every
record in memory, every learner register read and every refusal is held against the reference model,
`model.run.learning`.

WHAT EACH TEST HOLDS
  learning_on_the_kernel        at the build's 128 taps. A prelude run left with an update unfinished, a count
                                in each label and a refusal latched in lrn_refusal, held whole; it ends done
                                with krn_status's refused bit 0. Then krn_reset, and the main run against a
                                fresh model learner: four truth records (one of amplitude 0, one of 5/2; START,
                                three BUSY, label 0 at exactly 2T), an update named early, a commit and a whole
                                shadow write held back while it runs, and the commit at its finish. Every slot
                                and beat, each operation's refusals, the eight counts and lrn_status the model's
  learner_rows_through_the_port the 64 words of the learner's block at reset; a refusal latched there and not
                                in krn_refusal; a write the kernel refuses for itself not forwarded; krn_reset
                                clearing the learner; an update with the core stopped
  refusals_through_the_views    an update under each one-field departure from the matched shape (SWAP_SHAPE),
                                with a commit scheduled (SWAP_PENDING), with a stream begun (WEIGHT_COUNT), and
                                under the matched shape alone (taken): each of the core's view ports that the
                                learner reads for these is wired to a register some case tells apart

WHAT THIS BENCH CANNOT SEE, each a stated limit of docs/rtl/krnl-learn.md: an operation's clock inside its
window, and so F to the clock (learn_chain holds it); FULL at 32 bits; the views that make `closed`, and
the commit's index; the pulse id; two updates in one run.
"""
import os

import cocotb

from spec import constants as C
from model import learner as L, run as R, weights
from model.refusal import Refusal

import core_host
import seam_host as seam
import learn_host as lh
import krnl_host as kh
import krnl_learn_host as kl

PROFILE = os.environ["UNDERTONE_PROFILE"]
CH = C.PROFILES[PROFILE]["channels"]
SLOT = C.MEMORY_SLOT_BYTES
WORD_BYTES = C.BUS["word_bits"] // 8
PERIOD = seam.period(PROFILE)
SIGMA = kh.SIGMA_SMALL[PROFILE]
SEED = 20261126
F = C.LEARN_UPDATE_FRAMES
PASS = C.RECTIFIERS["pass"]
ABS = C.RECTIFIERS["abs"]
T = C.MAX_TAPS                       # the packaged top's B_TAPS (its default), read back through cap_taps below

# The prelude: one record, an update named and left unfinished at the run's end.
PRE_FRAMES, PRE_BASE = 300, 0x10000
PRE_RECORDS = [kh.rec(150, 3, 1)]
PRE_OPS = [kl.Op(10, "update", 290, 10, 289)]

# The main run, worked by hand at T = 128 (docs/rtl/krnl-learn.md, section 3):
#   64  3/1  label 0 START; label 1 taken (q - j = 320)
#   384 0/1  label 0 taken (j - p = 320); label 1 taken (q - j = 256)
#   640 3/1  label 0 taken (j - p = 256, exactly 2T); label 1 BUSY (q - j = 80)
#   720 5/2  label 0 BUSY (80 < 256); label 1 BUSY (80 < 128)
FRAMES, BASE = 1080, 0x40000
RECORDS = [kh.rec(64, 3, 1), kh.rec(384, 0, 1), kh.rec(640, 3, 1), kh.rec(720, 5, 2)]
U = 760
FINISH = U + F                       # 1016
EARLY_AT, COMMIT_AT = 1030, 1040
COUNTS = {"lrn_count0": 2, "lrn_count1": 2, "lrn_skip_start": 1, "lrn_skip_busy": 3, "lrn_skip_full": 0,
          "lrn_made": 1, "lrn_unmade": 0, "lrn_early": 1}


def other_set(profile, taps):
    """A set unlike the start set, for the shadow write the learner holds back."""
    return lh.matched_blob(profile, dict((c, [0] * (taps - 1) + [-(c + 3)]) for c in range(CH)))


def main_ops():
    return [kl.Op(10, "update", U, 10, U - 1),
            kl.Op(770, "commit", EARLY_AT, 770, FINISH - 1),
            kl.Op(780, "write_shadow", other_set(PROFILE, T), 780, FINISH - 1),
            kl.Op(1020, "commit", COMMIT_AT, FINISH, COMMIT_AT - 2)]


def mem_kw():
    return dict(stall=0.02, stall_len=20, answer_delay=8)


@cocotb.test()
async def learning_on_the_kernel(dut):
    test = "learning_on_the_kernel"
    start = lh.start_blob(PROFILE, T)
    case = seam.Case(PROFILE, SEED, SIGMA, FRAMES, RECORDS, start, 3)
    ops = main_ops()

    # The model first: the stream is the one worked by hand, and each fault the mutants plant reaches a record.
    records, _truth, outcomes, learner = kl.model(case, ops)
    assert kl.outcomes_named(outcomes, ops) == [None, "UPDATE_UNFINISHED", "UPDATE_UNFINISHED", None], outcomes
    assert learner.counters() == COUNTS, learner.counters()
    made = learner.updates[0]
    assert made["counts"] == (2, 2) and made["blob"] is not None and made["blob"] != start, made["counts"]
    plain, _t, _o, _l = R.learning(case.noise(), case.schedule, case.frames, case.blob,
                                   {1020: [("commit", COMMIT_AT)]}, F, C.LEARN_COUNT_BITS, case.epoch)
    assert seam.first_difference(plain, records) == COMMIT_AT, "the learned set does not show at its commit"
    dropped, _r = kl.model_without(case, ops, {384})
    assert dropped.updates[0]["blob"] != made["blob"], "a learner that skips the amplitude-0 record learns the same"

    host, mem = await kh.begin(dut, base=PRE_BASE, size=PRE_FRAMES * SLOT, seed=SEED, **mem_kw())
    taps = await host.get("cap_taps")
    assert taps == T, "the packaged top advertises %d taps, not the %d this test is worked at" % (taps, T)

    # The prelude, held whole, ends done with a refusal of the learner's latched and the kernel's refused bit 0.
    pre = seam.Case(PROFILE, SEED + 1, SIGMA, PRE_FRAMES, PRE_RECORDS, start, 1)

    async def leave_a_refusal(h):
        await h.write(kh.off("lrn_status"), 1)          # a read-only row: REGISTER_ACCESS, left latched
        return ["REGISTER_ACCESS"]

    pl, _pr, _out, pre_held = await kl.learning_run(test, "the prelude, its update left unfinished", host, mem, pre,
                                                    PRE_BASE, PRE_OPS, PERIOD, extra=leave_a_refusal, close=False)
    assert pl.status()["running"] == 1 and pl.counters()["lrn_count1"] == 1, (pl.status(), pl.counters())

    # krn_reset, and the main run against a learner made new. The prelude's register checks are raised after the
    # main run's records are held, so a fault that reaches the main run's records is reported there.
    await kh.again(host, mem, BASE, FRAMES * SLOT, **mem_kw())
    _l, _r, _o, main_held = await kl.learning_run(test, "four records at 128 taps, the update at %d, the commit at %d"
                                                  % (U, COMMIT_AT), host, mem, case, BASE, ops, PERIOD, close=False)
    main_held.close()
    pre_held.close()


def reset_words(learner, first, end):
    """The words of [first, end) as the model's learner at next index 0 and the definition's build give them."""
    caps = {"lrn_cap_count_bits": C.LEARN_COUNT_BITS, "lrn_cap_update_frames": C.LEARN_UPDATE_FRAMES}
    counters = learner.counters()
    status = learner.status()
    words = {}
    for name, (at, _access, n) in C.REGISTERS.items():
        if not first <= at < end:
            continue
        if name in counters:
            value = counters[name]
        elif name == "lrn_status":
            value = sum(status[b] << bit for b, bit in C.REGISTER_BITS["lrn_status"].items() if b in status)
        elif name in caps:
            value = caps[name]
        elif name in ("lrn_update_at", "lrn_refusal"):
            value = 0
        else:
            raise AssertionError("the learner's block has a row %s this bench does not know" % name)
        for w in range(n):
            words[at + w * WORD_BYTES] = (value >> (32 * w)) & 0xFFFFFFFF
    return [words.get(a, 0) for a in range(first, end, WORD_BYTES)]


@cocotb.test()
async def learner_rows_through_the_port(dut):
    test = "learner_rows_through_the_port"
    host, _mem = await kh.begin(dut, base=0x10000, size=SLOT)
    first, end = C.BLOCKS["learner"]
    model_learner = L.Learner(lh.start_blob(PROFILE, 2), [], F, C.LEARN_COUNT_BITS)
    seen = [await host.read(a) for a in range(first, end, WORD_BYTES)]
    expected = reset_words(model_learner, first, end)

    access, stopped = C.REFUSAL_CODES["REGISTER_ACCESS"], C.REFUSAL_CODES["CORE_STOPPED"]
    refused = 1 << C.REGISTER_BITS["lrn_status"]["refused"]
    krn_refused = 1 << C.REGISTER_BITS["krn_status"]["refused"]

    async def look(*names):
        for name in names:
            seen.append(await host.get(name))

    # a write to a read-only row of the learner's: its latch, and not the kernel's or the core's
    await host.write(kh.off("lrn_status"), 1)
    await look("lrn_refusal", "lrn_status", "krn_refusal", "refusal", "krn_status")
    expected += [access, refused, 0, 0, 0]
    # a write the kernel refuses for itself (two strobes) reaches no block: the kernel's latch alone
    await host.write_bytes(kh.off("lrn_refusal"), bytes(2))
    await look("krn_refusal", "krn_status", "lrn_refusal", "lrn_status")
    expected += [access, krn_refused, access, refused]
    await host.write(kh.off("krn_refusal"), 0)
    # krn_reset clears the learner with the chain
    await host.write(kh.off("krn_reset"), 1)
    await look("lrn_refusal", "lrn_status", "krn_refusal")
    expected += [0, 0, 0]
    # an update with the core stopped
    await host.write_many(lh.op_writes("update", 5))
    await look("lrn_refusal", "lrn_update_at", "krn_refusal")
    expected += [stopped, 0, 0]
    await host.write(kh.off("lrn_refusal"), 0)
    await look("lrn_refusal", "lrn_status")
    expected += [0, 0]
    core_host.hold_words(test, "the learner's block at reset, then its latch beside the kernel's", seen, expected)


def view_cases():
    """(label, blob, what is written before the update, the expected name, whose name it is)."""
    matched = lh.matched_blob(PROFILE, dict((c, [0, c + 2]) for c in range(CH)))
    rows = dict((c, (0, c + 2)) for c in range(CH))
    cases = [
        ("the matched shape at 2 taps", matched, None),
        ("two filters", weights.pack(PROFILE, [{0: (0, 2)}, {min(1, CH - 1): (0, 3)}], (1, 1), PASS, 1, 0), None),
        ("a pool of 2", weights.pack(PROFILE, [rows], (1,), PASS, 2, 0), None),
        ("a score shift of 1", weights.pack(PROFILE, [rows], (1,), PASS, 1, 1), None),
        ("the abs rectifier", weights.pack(PROFILE, [rows], (1,), ABS, 1, 0), None),
        ("one hidden unit", weights.pack(PROFILE, [rows], (1,), PASS, 1, 0, hidden=[(1,)], hidden_shift=0,
                                         between=PASS), None),
        ("the matched shape, a commit scheduled", matched, "commit"),
        ("the matched shape, a stream begun", matched, "begin"),
    ]
    if CH > 1:
        # Under one channel two filters are two rows, so the filters' view and the rows' are told apart only here
        # (docs/rtl/learn.md, limit 11): rows alone, then filters alone.
        cases.append(("one filter reading two of three channels",
                      lh.matched_blob(PROFILE, {0: [0, 2], 1: [0, 3]}), None))
        cases.append(("two filters over three rows",
                      weights.pack(PROFILE, [{0: (0, 2), 1: (0, 3)}, {2: (0, 4)}], (1, 1), PASS, 1, 0), None))
    out = []
    for label, blob, before in cases:
        if before == "begin":
            out.append((label, blob, before, "WEIGHT_COUNT", "the fabric's (docs/rtl/learn.md, section 3)"))
            continue
        m = L.Learner(blob, [], F, C.LEARN_COUNT_BITS)
        if before == "commit":
            m.commit(500)
        try:
            m.update(1000)
            name = None
        except Refusal as e:
            name = e.name
        out.append((label, blob, before, name, "the model's"))
    assert [c[3] for c in out[:6]] == [None] + ["SWAP_SHAPE"] * 5, [c[3] for c in out]
    assert out[6][3] == "SWAP_PENDING" and all(c[3] == "SWAP_SHAPE" for c in out[8:]), [c[3] for c in out]
    return out


@cocotb.test()
async def refusals_through_the_views(dut):
    test = "refusals_through_the_views"
    host, _mem = await kh.begin(dut, base=0x10000, size=SLOT)
    seen, expected = [], []
    for label, blob, before, name, whose in view_cases():
        await host.write(kh.off("krn_reset"), 1)
        await kh.load_core(host, blob)
        if before == "commit":
            await kh.commit(host, 500)
        elif before == "begin":
            await host.write(kh.off("shadow_begin"), len(core_host.words_of(weights.unpack(blob))))
        assert await host.take("refusal") == 0, "%s: the core refused what was written before the update" % label
        await host.write_many(lh.op_writes("update", 1000))
        seen += [await host.get("lrn_refusal"), await host.get("lrn_update_at", 0)]
        expected += [lh.code(name), 1000 if name is None else 0]
        cocotb.log.info("VIEWS %s: %s, %s" % (label, name, whose))
    seen.append(await host.get("krn_refusal"))
    expected.append(0)
    core_host.hold_words(test, "an update under each shape and state, its refusal and its index", seen, expected)

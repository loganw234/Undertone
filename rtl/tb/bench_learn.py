"""The learner beside a small core (rtl/learn/learn_small.sv), held to model/learner.py word for word.

Every test runs under both profiles, and each runs whole streams through `learn_host.small_case`: the
design is reset and loaded, the truth handed over, the frames driven with the script's host operations at
their next indexes, and then every score record is held against the model's (`harness.hold`), each
operation's two refusal registers against the model's outcome, and the eight counts and `lrn_status`
against `counters()` and `status()`. The model is `model.learner.Learner` at this build's bounds: 6 taps
at most, count_bits 3, an update time of 16 frames. Frames come every 20 clocks a channel, the chain's
rate, unless a test says otherwise.

  bit_identity_hand_worked_ties   LRN-B's hand-worked cases with ties (case 1 under s16x1, case 3 under
                                  s24x3), each coefficient alone in a score after the commit
  bit_identity_every_coefficient  a seeded stream at the build's 6 taps: two updates, each set read back
                                  coefficient by coefficient; the core's shadow_count and whole bit after
                                  the learner's writes
  update_finishes_within_f        F from both sides: a commit at the last clock of u + F - 1 refused, at
                                  the first of u + F taken
  skips_at_their_boundaries       START, BUSY (label 0; label 1 from before and from after) and FULL, each
                                  at its boundary, and a label-1 window both BUSY and FULL counted BUSY
  snapshot_at_u                   the windows judged at u in the update and those after it not, with the
                                  update made at u and made a frame late; windows judged during pass B
  a_record_offered_late           a record handed over after the core's next index reached it: judged,
                                  and the update at its index waits for it
  frames_every_clock              windows at a frame a clock, the commit scripted after the learner is done
  refuses_an_update               UPDATE_UNFINISHED, SWAP_INDEX both ways, SWAP_PENDING
  refuses_the_core_rows           a commit, a shadow write and a lone shadow word while unfinished
  refuses_swap_shape              each condition of the matched-filter check alone
  refuses_what_the_model_cannot   CORE_STOPPED, WEIGHT_COUNT and REGISTER_ACCESS: this design's own
  quantise_input                  an update with no window, and one whose every D is zero
  refusal_order                   pairs of an update's faults
  rows_read_back                  lrn_update_at, the caps, lrn_status through an update's life, and the
                                  counters past 2^32 from a written state, their two words of one moment
  extremes_by_real_windows        the sums, D and the peak at their bounds, by 7 windows a label
  widths_are_the_models           the learner's localparams against model.learner.widths
  control_model_half_away         the comparison handed a learner that rounds half away from zero

WHAT IT CANNOT SEE, each a stated limit of docs/rtl/learn.md: the truth port is the bench's, so the
injector's own refusals are not here (bench_learn_chain.py has the injector); the streams and sizes are
the ones named; a register check is an assertion, and a mutant whose fault shows only there names no
kind of mismatch.
"""
import json
import os
import random

import cocotb
from cocotb.triggers import FallingEdge

from spec import constants as C
from model import learner as L, weights
from model.refusal import Refusal

import harness
import core_host as host
import learn_host as lh

PROFILE = os.environ["UNDERTONE_PROFILE"]
PROF = C.PROFILES[PROFILE]
CH = PROF["channels"]
SMIN, SMAX = PROF["sample_min"], PROF["sample_max"]
TAPS = 6            # learn_small's most taps
F = 16              # its update time
NB = 3              # its count_bits
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def case_named(name):
    with open(os.path.join(ROOT, "vectors", "lrn-b", "cases.json"), encoding="utf-8") as f:
        return [c for c in json.load(f)["cases"] if c["name"] == name][0]


def noise(rng, n, scale=None):
    top = SMAX if scale is None else scale
    return [tuple(rng.randint(-top, top) for _ in range(CH)) for _ in range(n)]


def pad(frames, n):
    return list(frames) + lh.zeros(PROFILE, n - len(frames))


def blob_of(taps):
    return lh.start_blob(PROFILE, taps)


def set_of(learner, k=-1):
    """The coefficients of the learner's k-th update, as [channel][tap], or None for an unmade one."""
    u = learner.updates[k]
    if u["blob"] is None:
        return None
    config = weights.unpack(u["blob"])
    return [list(config["filters"][0][c]) for c in range(CH)]


# ------------------------------------------------------------------ the hand-worked cases

@cocotb.test()
async def bit_identity_hand_worked_ties(dut):
    bench = lh.Small(dut, PROFILE)
    case = case_named("s16x1-the-tie" if CH == 1 else "s24x3-ties-on-three-channels")
    taps = case["taps"]
    frames = [tuple(f) for f in case["frames"]]
    u = case["script"][0][2]
    named = case["script"][0][0]
    commit = u + F + 4
    script = {named: [("update", u)], u + F: [("commit", commit)]}
    if CH == 1:
        script[7] = [("write_shadow", blob_of(taps))]           # refused: the update is unfinished
        script[13] = [("commit", u + 4)]                         # refused, and counted in lrn_early
    frames = pad(frames, commit) + lh.impulses(PROFILE, taps)
    # one more record, past the stream's end: it is never judged, and with it known the update is made at u
    # itself, at the edge that judges u's last window (without it, the update waits a frame for the truth at u)
    far = len(frames) + 100
    learner = await lh.small_case(bench, "bit_identity_hand_worked_ties", case["name"], blob_of(taps),
                                  case["truth_indexes"] + [far], frames, script)
    # the model's set is the hand-worked one, ties to the even; half away from zero would be another
    want = [list(c) for c in case["updates"][-1]["coefficients"]]
    assert set_of(learner) == want, "the model's set %r is not the hand-worked %r" % (set_of(learner), want)


# ------------------------------------------------------------------ every coefficient alone

@cocotb.test()
async def bit_identity_every_coefficient(dut):
    bench = lh.Small(dut, PROFILE)
    rng = random.Random(20261125 + CH)
    imp = lh.impulses(PROFILE, TAPS)
    # the first training part, its update at 48 and its commit at 70, after six frames of zeros
    u1 = 48
    c1 = u1 + F + TAPS
    frames = noise(rng, u1 + F) + lh.zeros(PROFILE, TAPS) + imp
    s = len(frames)
    # the second, on more noise; its sums hold the first's windows too (no forgetting)
    records = [6, 18, 30, 42] + [s + 12, s + 24, s + 36, s + 48]
    u2 = s + 54
    c2 = u2 + F + TAPS
    frames = frames + noise(rng, u2 + F - s) + lh.zeros(PROFILE, TAPS) + imp
    script = {10: [("update", u1)], u1 + F: [("commit", c1)], s + 2: [("update", u2)], u2 + F: [("commit", c2)]}

    async def shadow_whole(d):
        # after the learner's writes: the core's stream is whole and counted, so a commit passes WEIGHT_COUNT
        count = await host.read(d, "shadow_count")
        state = await host.status(d)
        assert count == TAPS * CH + 1 and state["whole"] == 1, \
            "after the learner's writes the core's shadow_count is %d and whole %d" % (count, state["whole"])

    learner = await lh.small_case(bench, "bit_identity_every_coefficient", "two updates at 6 taps", blob_of(TAPS),
                                  records, frames, script, probes={u1 + F: shadow_whole})
    assert len(learner.updates) == 2 and set_of(learner, 0) != set_of(learner, 1) and set_of(learner, 0) is not None


# ------------------------------------------------------------------ F from both sides

@cocotb.test()
async def update_finishes_within_f(dut):
    bench = lh.Small(dut, PROFILE)
    rng = random.Random(7 + CH)
    records = [6, 18, 30]
    u = 38
    c = u + F + 6
    frames = pad(noise(rng, 40), c) + lh.impulses(PROFILE, TAPS)
    script = {2: [("update", u)], u + F - 1: [("commit", c)], u + F: [("commit", c)]}
    placement = {(u + F - 1, 0): "last", (u + F, 0): "with"}
    learner = await lh.small_case(bench, "update_finishes_within_f", "F at 6 taps", blob_of(TAPS), records, frames,
                                  script, placement=placement)
    assert learner.counters()["lrn_early"] == 1 and learner.counters()["lrn_made"] == 1


# ------------------------------------------------------------------ the skips

@cocotb.test()
async def skips_at_their_boundaries(dut):
    bench = lh.Small(dut, PROFILE)
    rng = random.Random(3 + CH)
    t = 3
    blob = blob_of(t)
    runs = [
        ("START at T - 1", [2]),
        ("START free at T", [3]),
        ("START before BUSY", [0, 2]),
        ("label 0 BUSY at 2T - 1", [3, 8]),
        ("label 0 free at 2T", [3, 9]),
        ("label 1 BUSY at T - 1, from after and from before", [3, 5]),
        ("label 1 free at T", [3, 6]),
    ]
    for label, records in runs:
        frames = noise(rng, records[-1] + t + 4)
        script = {records[-1] + t + 1: [("update", records[-1] + t + 1)]}
        await lh.small_case(bench, "skips_at_their_boundaries", label, blob, records, frames, script)
    # FULL: eight records 2T apart give eight windows a label, and the eighth is FULL; then a label-1 window
    # both BUSY and FULL, which is counted BUSY
    records = [3 + 6 * i for i in range(8)] + [3 + 6 * 7 + 2]
    u = records[-1] + t + 1
    commit = u + F + 4
    frames = pad(noise(rng, u), commit) + lh.impulses(PROFILE, t)
    learner = await lh.small_case(bench, "skips_at_their_boundaries", "FULL, and BUSY before FULL", blob, records,
                                  frames, {4: [("update", u)], u + F: [("commit", commit)]})
    got = learner.counters()
    both = records[-2]                                # its label 1 is BUSY (the next record 2 on) and FULL (7 taken)
    assert got["lrn_count0"] == 7 and got["lrn_count1"] == 7 and got["lrn_skip_full"] >= 1, got
    assert (both + t, both, 1, "busy") in learner.log, "the stream has no label-1 window both BUSY and FULL"
    # and the last record's label 0 is BUSY (2 after the one before) and FULL (7 taken): counted BUSY
    assert (records[-1], records[-1], 0, "busy") in learner.log, "the stream has no label-0 window both BUSY and FULL"


# ------------------------------------------------------------------ the snapshot

@cocotb.test()
async def snapshot_at_u(dut):
    bench = lh.Small(dut, PROFILE)
    rng = random.Random(11 + CH)
    # T = 1, made at u: label 0 of 4 (frame 3) is judged at 4 and is the update's; label 1 of 4 (frame 4),
    # judged at 5, is not. A record past the stream's end is known, so the update is made at 4 itself
    blob = blob_of(1)
    frames = pad(noise(rng, 8), 4 + F + 3) + lh.impulses(PROFILE, 1)
    script = {1: [("update", 4)], 4 + F: [("commit", 4 + F + 3)]}
    learner = await lh.small_case(bench, "snapshot_at_u", "made at u, T = 1", blob, [2, 4, 500], frames, script)
    assert learner.updates[0]["counts"] == (2, 1), learner.updates[0]["counts"]
    # T = 2, the same at two taps, where a set of one channel is more than its sign: label 0 of 6 (frames 4, 5),
    # judged at 6 = u, is the update's
    blob = blob_of(2)
    frames = pad(noise(rng, 10), 6 + F + 3) + lh.impulses(PROFILE, 2)
    script = {1: [("update", 6)], 6 + F: [("commit", 6 + F + 3)]}
    learner = await lh.small_case(bench, "snapshot_at_u", "made at u, T = 2", blob, [2, 6, 500], frames, script)
    assert learner.updates[0]["counts"] == (2, 1), learner.updates[0]["counts"]
    # T = 2, made a frame late: no record at 8 or later is known when the index is 8, so the update waits for
    # frame 8; the record at 9 is handed over at the edge that takes frame 8, and its label 0 (frames 7, 8),
    # judged there, is not the update's
    frames = pad(noise(rng, 12), 8 + F + 3) + lh.impulses(PROFILE, 2)
    script = {1: [("update", 8)], 8 + F: [("commit", 8 + F + 3)]}
    learner = await lh.small_case(bench, "snapshot_at_u", "made a frame late, T = 2", blob, [2, 9], frames, script,
                                  with_push={9: 9})
    assert learner.updates[0]["counts"] == (1, 1), learner.updates[0]["counts"]
    # T = 6: windows judged while pass B divides go to the live sums, not to the update
    records = [6, 18, 30, 42, 54]
    u = 37
    commit = 70
    frames = pad(noise(rng, 64), commit) + lh.impulses(PROFILE, TAPS)
    script = {2: [("update", u)], u + F: [("commit", commit)]}
    learner = await lh.small_case(bench, "snapshot_at_u", "windows during pass B, T = 6", blob_of(TAPS), records,
                                  frames, script, spacing=20 * CH)
    assert learner.updates[0]["counts"] == (3, 3), learner.updates[0]["counts"]


# ------------------------------------------------------------------ the race

@cocotb.test()
async def a_record_offered_late(dut):
    bench = lh.Small(dut, PROFILE)
    rng = random.Random(13 + CH)
    t = 3
    u = 9
    commit = u + F + 4
    frames = pad(noise(rng, 16), commit) + lh.impulses(PROFILE, t)
    script = {2: [("update", u)], u + F: [("commit", commit)]}
    learner = await lh.small_case(bench, "a_record_offered_late", "the record at u handed over at u", blob_of(t),
                                  [3, 9], frames, script, pushes={9: [9]})
    assert learner.updates[0]["counts"] == (2, 1), learner.updates[0]["counts"]


# ------------------------------------------------------------------ a frame a clock

@cocotb.test()
async def frames_every_clock(dut):
    bench = lh.Small(dut, PROFILE)
    rng = random.Random(17 + CH)
    records = list(range(6, 120, 6))
    u = 100
    commit = u + 600
    frames = pad(noise(rng, 130), commit + 4) + lh.impulses(PROFILE, TAPS)
    script = {3: [("update", u)], commit - 4: [("commit", commit)]}
    await lh.small_case(bench, "frames_every_clock", "a frame every clock", blob_of(TAPS), records, frames, script,
                        spacing=1)


# ------------------------------------------------------------------ the refusals

@cocotb.test()
async def refuses_an_update(dut):
    bench = lh.Small(dut, PROFILE)
    rng = random.Random(19 + CH)
    top = weights.INDEX_MAX
    frames = noise(rng, 90)
    script = {
        2: [("update", 20)],
        5: [("update", 30)],                         # UPDATE_UNFINISHED
        40: [("update", 30)],                        # SWAP_INDEX: below the next index
        41: [("update", top - F + 1)],               # SWAP_INDEX: u + F past the index field's most
        42: [("update", top - F)],                   # taken: u + F is the field's most, and it never finishes here
    }
    await lh.small_case(bench, "refuses_an_update", "unfinished and index", blob_of(TAPS), [6, 18], frames, script)
    script = {2: [("commit", 50)], 3: [("update", 60)],     # SWAP_PENDING
              51: [("update", 60)], 60: [("commit", 70)]}   # after the swap: taken; then a commit refused
    await lh.small_case(bench, "refuses_an_update", "pending", blob_of(TAPS), [6, 18], frames, script)


@cocotb.test()
async def refuses_the_core_rows(dut):
    bench = lh.Small(dut, PROFILE)
    rng = random.Random(23 + CH)
    frames = noise(rng, 60)
    # a shadow write at 9, before the learner writes, and at 24, while its pass B writes the core's stream
    # (made at 21, a frame after u, its pass B runs from about 22 to 27 under either profile)
    script = {2: [("update", 20)], 8: [("commit", 30)], 9: [("write_shadow", blob_of(TAPS))],
              24: [("write_shadow", blob_of(TAPS))], 20 + F: [("commit", 50)]}
    lone = [(lh.offset("shadow_data"), 1)]
    # a lone weight word: held back and refused while the update is unfinished; after the swap at 50 the
    # core's own WEIGHT_COUNT, no stream being begun
    await lh.small_case(bench, "refuses_the_core_rows", "commit, shadow write, a lone word", blob_of(TAPS), [6, 18],
                        frames, script, raws={10: [(lone, "UPDATE_UNFINISHED", 1, None)],
                                              52: [(lone, None, 0, "WEIGHT_COUNT")]})


def shape_blob(**over):
    """A blob of 6 taps that is the matched filter but for what `over` changes. `split` is two filters that
    read every channel between them (under s24x3: rows {0, 1} and {2}), so the count of filters alone differs."""
    channels = over.get("channels", list(range(CH)))
    rows = [dict((c, [1] * TAPS) for c in channels)]
    if over.get("filters") == 2:
        rows.append({0: [2] * TAPS})
    if over.get("split"):
        rows = [{0: [1] * TAPS, 1: [3] * TAPS}, {2: [2] * TAPS}]
    head = tuple([1] * len(rows))
    rect = C.RECTIFIERS["abs"] if over.get("abs") else lh.PASS
    if over.get("hidden"):
        return weights.pack(PROFILE, rows, (1,), rect, over.get("pool", 1), over.get("shift", 0), [list(head)], 0,
                            lh.PASS)
    return weights.pack(PROFILE, rows, head, rect, over.get("pool", 1), over.get("shift", 0))


@cocotb.test()
async def refuses_swap_shape(dut):
    bench = lh.Small(dut, PROFILE)
    rng = random.Random(29 + CH)
    frames = noise(rng, 12)
    cases = [("the rectifier abs", dict(abs=True)), ("a pool of 2", dict(pool=2)), ("a shift of 1", dict(shift=1)),
             ("a hidden unit", dict(hidden=True))]
    if CH > 1:
        # each alone: two filters whose rows are every channel once, and one filter not reading every channel
        cases += [("two filters, every channel once", dict(split=True)),
                  ("a filter not reading every channel", dict(channels=[0, 1]))]
    else:
        # under one channel two filters are also two rows: both conditions hold (docs/rtl/learn.md, a limit)
        cases.append(("two filters", dict(filters=2)))
    for label, over in cases:
        await lh.small_case(bench, "refuses_swap_shape", label, shape_blob(**over), [6], frames,
                            {2: [("update", 8)]})


@cocotb.test()
async def refuses_what_the_model_cannot(dut):
    """The cases this design has and the model cannot: each name is the design's, stated here."""
    bench = lh.Small(dut, PROFILE)
    rng = random.Random(31 + CH)
    await bench.reset()
    # CORE_STOPPED: an update named while the core has not been started
    await host.write_many(dut, lh.op_writes("update", 5))
    lrn, core = await lh.read(dut, "lrn_refusal"), await lh.read(dut, "refusal")
    assert (lrn, core) == (lh.code("CORE_STOPPED"), 0), "an update while stopped: lrn_refusal %d, refusal %d" % (lrn, core)
    frames = noise(rng, 30)
    words = host.words_of(weights.unpack(blob_of(TAPS)))
    begun = [(lh.offset("shadow_begin"), len(words))] + host.stream_pairs(words[:3])
    access = [[(lh.offset("lrn_status"), 1)], [(lh.offset("lrn_count0"), 1)], [(C.BLOCKS["learner"][0] + 0x50, 1)],
              [(lh.offset("lrn_update_at") + 1, 1)], [(lh.offset("lrn_refusal"), 5)],
              [(lh.offset("lrn_cap_update_frames"), 0)]]
    raws = {3: [(begun, None, 0, None)], 4: [(lh.op_writes("update", 20), "WEIGHT_COUNT", 1, None)],
            5: [(w, "REGISTER_ACCESS", 1, None) for w in access]}
    await lh.small_case(bench, "refuses_what_the_model_cannot", "weight count and register access", blob_of(TAPS),
                        [6], frames, {}, raws=raws)


@cocotb.test()
async def quantise_input(dut):
    bench = lh.Small(dut, PROFILE)
    rng = random.Random(37 + CH)
    commit = 4 + F + 2
    frames = pad(noise(rng, 6), commit) + lh.impulses(PROFILE, TAPS)
    script = {1: [("update", 4)], 4 + F: [("commit", commit)]}
    await lh.small_case(bench, "quantise_input", "no window at all", blob_of(TAPS), [], frames, script)
    # windows taken, every D zero: every frame is zero
    frames = lh.zeros(PROFILE, 50)
    script = {1: [("update", 25)], 25 + F: [("update", 25 + F + 1)]}
    learner = await lh.small_case(bench, "quantise_input", "every D zero", blob_of(3), [3, 9], frames, script)
    assert learner.counters()["lrn_unmade"] == 1 and learner.counters()["lrn_count0"] == 2


@cocotb.test()
async def refusal_order(dut):
    bench = lh.Small(dut, PROFILE)
    rng = random.Random(41 + CH)
    frames = noise(rng, 40)
    # UPDATE_UNFINISHED before SWAP_INDEX; SWAP_PENDING before SWAP_INDEX
    script = {2: [("update", 20)], 5: [("update", 1)], 20 + F: [("commit", 39)], 20 + F + 1: [("update", 1)]}
    await lh.small_case(bench, "refusal_order", "unfinished, then pending, before index", blob_of(TAPS), [6], frames,
                        script)
    # SWAP_SHAPE before SWAP_PENDING
    script = {1: [("commit", 30)], 2: [("update", 1)]}
    await lh.small_case(bench, "refusal_order", "shape before pending", shape_blob(pool=2), [6], frames, script)
    # SWAP_INDEX before WEIGHT_COUNT, the design's own order
    words = host.words_of(weights.unpack(blob_of(TAPS)))
    begun = [(lh.offset("shadow_begin"), len(words))] + host.stream_pairs(words[:2])
    raws = {10: [(begun, None, 0, None), (lh.op_writes("update", 3), "SWAP_INDEX", 1, None)]}
    await lh.small_case(bench, "refusal_order", "index before weight count", blob_of(TAPS), [6], frames, {}, raws=raws)

    # UPDATE_UNFINISHED before SWAP_SHAPE. The operations cannot make both hold (an update is named only under
    # the matched shape, which a running core keeps), so an update named and unfinished is written into both
    # sides under another shape, as LRN-B's own test of this order does
    def unfinished(learner):
        learner._update = {"u": 100, "finish": 100 + F, "made": False, "counts": None, "sums": None,
                           "difference": None, "blob": None, "name": None, "outcome": None}

    async def unfinished_rtl(d):
        lrn = d.u_learn
        lrn.upd_u.value, lrn.upd_uf.value = 100, 100 + F
        lrn.upd_taken.value, lrn.upd_made.value, lrn.upd_done.value = 1, 0, 0
        lrn.hold_q.value, lrn.hold_end_q.value = 1, 0

    await lh.small_case(bench, "refusal_order", "unfinished before shape, from a written state", shape_blob(pool=2),
                        [6], frames, {2: [("update", 5)]}, before=unfinished, before_rtl=unfinished_rtl)


# ------------------------------------------------------------------ the rows

@cocotb.test()
async def rows_read_back(dut):
    bench = lh.Small(dut, PROFILE)
    rng = random.Random(43 + CH)
    u = 26
    far = (1 << 33) + 5

    async def named_far(d):
        lo, hi = await lh.read(d, "lrn_update_at", 0), await lh.read(d, "lrn_update_at", 1)
        st = await lh.status(d)
        assert (lo, hi) == (far & lh.WORD_MASK, far >> 32) and st["named"] == 1 and st["running"] == 0, (lo, hi, st)

    async def before_u(d):
        st = await lh.status(d)
        lo = await lh.read(d, "lrn_update_at", 0)
        assert st["named"] == 1 and st["running"] == 0 and lo == u, (st, lo)

    held = {}

    async def lower(d):
        # a lower word read here holds the upper word: a busy skip comes before the upper word is read
        held["lo"] = await lh.read(d, "lrn_skip_busy", 0)

    async def upper(d):
        hi = await lh.read(d, "lrn_skip_busy", 1)
        assert (held["lo"], hi) == (lh.WORD_MASK, 0), "the busy counter's two words: %r, %r" % (held["lo"], hi)

    async def during(d):
        st = await lh.status(d)
        assert st["named"] == 0 and st["running"] == 1, st

    async def after(d):
        st = await lh.status(d)
        lo = await lh.read(d, "lrn_update_at", 0)
        assert st["named"] == 0 and st["running"] == 0 and st["made"] == 1 and lo == 0, (st, lo)
        caps = (await lh.read(d, "lrn_cap_count_bits"), await lh.read(d, "lrn_cap_update_frames"))
        assert caps == (NB, F), caps
        hole = await host.read_at(d, C.BLOCKS["learner"][0] + 0x50)
        assert hole == 0, hole

    def written(learner):
        learner._counters["lrn_skip_busy"] = (1 << 32) - 1

    async def written_rtl(d):
        d.u_learn.c_busy.value = (1 << 32) - 1

    frames = noise(rng, 60)
    # label 0 of 10 is BUSY, at 10, between the two reads; label 0 of 6 and label 1 of 18 are taken before u
    records = [6, 10, 18]
    script = {1: [("update", far)]}
    await lh.small_case(bench, "rows_read_back", "a far update", blob_of(TAPS), [6], frames[:10], script,
                        probes={5: named_far})
    script = {2: [("update", u)]}
    await lh.small_case(bench, "rows_read_back", "an update's life, the counters past 2^32", blob_of(TAPS), records,
                        frames, script, before=written, before_rtl=written_rtl,
                        probes={4: before_u, 8: lower, 11: upper, u + 1: during, u + F + 2: after})


@cocotb.test()
async def reads_while_the_learner_writes(dut):
    """While pass B writes the core's stream, reads come every other clock, alternating between the core's
    `id` and the learner's `lrn_cap_count_bits`: each reads its own word, so no read was lost to a write of
    the learner's (every block's reg_rdata must answer every read for the bus's OR to hold)."""
    bench = lh.Small(dut, PROFILE)
    rng = random.Random(47 + CH)
    u = 26
    words = []

    async def reads(d):
        for k in range(80):
            name = "id" if k % 2 == 0 else "lrn_cap_count_bits"
            words.append((name, await lh.read(d, name)))

    frames = noise(rng, 60)
    await lh.small_case(bench, "reads_while_the_learner_writes", "reads during pass B", blob_of(TAPS), [6, 18],
                        frames, {2: [("update", u)]}, probes={u + 1: reads})
    want = {"id": C.BUS["magic"], "lrn_cap_count_bits": NB}
    wrong = [(k, name, value) for k, (name, value) in enumerate(words) if value != want[name]]
    assert not wrong, "%d read(s) answered another word; the first, read %d of %s: 0x%X" % ((len(wrong),) + wrong[0])


# ------------------------------------------------------------------ the extremes

@cocotb.test()
async def extremes_by_real_windows(dut):
    bench = lh.Small(dut, PROFILE)
    t = 2
    records = [2 + 4 * i for i in range(7)]
    one = []
    for c in range(CH):
        low, high = (SMIN, SMAX) if c % 2 == 0 else (SMAX, SMIN)
        one.append((low, low // 3, high, high // 5))
    frames = []
    for _ in records:
        for k in range(4):
            frames.append(tuple(one[c][k] for c in range(CH)))
    u = records[-1] + t
    commit = u + F + 4
    frames = pad(frames, commit) + lh.impulses(PROFILE, t)
    learner = await lh.small_case(bench, "extremes_by_real_windows", "7 windows a label at the extremes", blob_of(t),
                                  records, frames, {1: [("update", u)], u + F: [("commit", commit)]})
    r = L.ranges(PROFILE, NB)
    d = learner.updates[0]["difference"]
    assert max(abs(v) for v in d) == r["peak"][1] and min(learner.updates[0]["sums"][0][0]) == r["sum"][0], \
        "the stream does not reach the peak's and a sum's bounds"


@cocotb.test()
async def widths_are_the_models(dut):
    harness.start_clock(dut)
    model = L.widths(PROFILE, NB)
    lrn = dut.u_learn
    seen = [as_int(lrn.N.value), as_int(lrn.W_SUM.value), as_int(lrn.W_D.value), as_int(lrn.W_X.value) + 1,
            as_int(lrn.W_MAG.value), C.COEFF_BITS]
    want = [model["count"], model["sum"], model["difference"], model["scaled"], model["peak"], model["coefficient"]]
    host.hold_words("widths_are_the_models", "count, sum, D, D x COEFF_MAX, peak, coefficient", seen, want)


def as_int(value):
    return value if isinstance(value, int) else value.to_unsigned()


# ------------------------------------------------------------------ the controls on the model side

class HalfAway(L.Learner):
    """A learner wrong in one place: a tie goes away from zero."""

    def _quantise(self, d):
        m = max(abs(v) for v in d)
        if m == 0:
            raise Refusal("QUANTISE_INPUT", "all zero")
        out = []
        for v in d:
            n, r = divmod(abs(v) * C.COEFF_MAX, m)
            out.append((n + (1 if 2 * r >= m else 0)) * (1 if v >= 0 else -1))
        return tuple(out)


@cocotb.test()
async def control_model_half_away(dut):
    bench = lh.Small(dut, PROFILE)
    case = case_named("s16x1-the-tie" if CH == 1 else "s24x3-ties-on-three-channels")
    taps = case["taps"]
    u = case["script"][0][2]
    commit = u + F + 4
    frames = pad([tuple(f) for f in case["frames"]], commit) + lh.impulses(PROFILE, taps)
    script = {case["script"][0][0]: [("update", u)], u + F: [("commit", commit)]}
    wrong = lh.model_run(blob_of(taps), case["truth_indexes"], frames, script, F, NB, learner_class=HalfAway)
    right = lh.model_run(blob_of(taps), case["truth_indexes"], frames, script, F, NB)
    first = next(i for i, (a, b) in enumerate(zip(wrong[1], right[1])) if a != b)
    assert first >= commit, "the wrong model differs before the commit, at %d" % first
    try:
        await lh.small_case(bench, "control_model_half_away", "half away from zero", blob_of(taps),
                            case["truth_indexes"], frames, script, model=wrong)
    except harness.Mismatch as e:
        assert e.kind == "WORD" and e.at == first, "the mismatch is %s at %d, not WORD at %d" % (e.kind, e.at, first)
    else:
        raise AssertionError("a learner that rounds half away from zero was not seen")

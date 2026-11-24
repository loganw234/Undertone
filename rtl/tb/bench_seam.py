"""The seam's bench: the source, the injector and the detector core wired together (rtl/seam/seam.sv),
held against the model's own run of the same configuration on every score word.

It runs once under each profile: the runner sets UNDERTONE_PROFILE and builds
the top with that profile's SAMPLE_BITS and CHANNELS.

A RUN (seam_host.Chain.run) loads the three blocks through the top's one
register port, starts the source, and collects every score record the top puts
out, from the first. The expected words are the model's:

  - `model.run.detect` on `model.source.Noise` and the schedule, where it can
    say them: every run with no swap;
  - for a swap, `seam_host.model_records`: model/run.py's own lines with a
    shadow write and a commit made on the core before the first frame. This
    file holds that composition equal to `model.run.detect` when nothing is
    swapped (`composition_is_run_py`, called in `bit_identity_swap`).

WHAT EACH TEST HOLDS
  bit_identity_first_frames   a short stream whose first record is at index 0, in stage E0's shape, compared
                              from record 0
  bit_identity_chain          E0's shape over a schedule of six amplitudes with records that touch and one
                              near the top of the sample's range; then a shape that is not E0's
  truth_isolation             the same samples under other truth records give the same score words
  bit_identity_swap           weights written to the shadow through the bus while the source runs, a commit
                              at a named index, every record before it and from it on the model's
  bit_identity_hand_over      the same with the learner's own blob, pinned in vectors/seam-2/handover.json and
                              held to the trainer by tests/test_seam2_handover.py: learned weights in RTL
  the_chains_clocks          every record is seen at the clock the three blocks' documents add up to
  one_bus_three_blocks        a word of each block read through the one bus, and a refusal of each
  control_model_*             the comparison handed a wrong model: each must report a WORD mismatch at the
                              record this file works out from the model

The controls on the RTL side are the mutants of the top in benches.toml.

THE WORDS A CONTROL HOLDS. A control on the model side, and the test of the
clocks, need the words of a run an identity test has already made. That run
is kept (`kept`) and used again; when it is not there, as in a mutant's run,
which holds only the tests it names, the test makes the run itself.

WHAT THIS BENCH DOES NOT SEE, each a stated limit of docs/rtl/seam.md: a seed,
a sigma, a schedule, a shape or a length it does not run; the frames at the
two joints, which it never reads (it holds the score words they lead to); a
refusal through the chain, since every run here is one no block refuses;
whether the learned weights are any good, which is stage E1's and is not read.
"""
import hashlib
import json
import os
import random

import cocotb

from spec import constants as C
from model import run, weights
from model.detector import Core

import harness
import core_host as host
import seam_host as seam
import source_bus as bus

PROFILE = os.environ["UNDERTONE_PROFILE"]
PROF = C.PROFILES[PROFILE]
CHANNELS = PROF["channels"]
E0 = C.PULSE_IDS["e0"]
PULSE = C.PULSES["e0"]
L = len(PULSE)
SEED = 2026112340
FLAG_SETTLING = 1 << C.FLAGS["settling"]

# A sigma, the filter's gain in each channel, and an amplitude that takes a pulse near the top of the
# sample's range: each differs by profile, and the gains differ by channel.
SIGMA = {"s16x1": (50, 1), "s24x3": (97, 2)}[PROFILE]
GAINS = {"s16x1": (1,), "s24x3": (3, -2, 1)}[PROFILE]
OTHER_GAINS = {"s16x1": (-1,), "s24x3": (1, 3, -2)}[PROFILE]
LARGE = {"s16x1": 33, "s24x3": 8600}[PROFILE]
# The channels each of two filters reads, for a shape that is not E0's: different channels where there are any.
TWO_FILTERS = {"s16x1": [[0], [0]], "s24x3": [[0, 2], [1]]}[PROFILE]
ABS = C.RECTIFIERS["abs"]

# The sizes, set from the chain's measured rate (docs/rtl/seam.md, the register).
FIRST_FRAMES = 96
CHAIN_FRAMES = 420
OTHER_SHAPE_FRAMES = 150
ISOLATION_FRAMES = 140
SWAP_FRAMES = 150


def rec(index, num=1, den=1, pulse_id=E0):
    return {"index": index, "pulse_id": pulse_id, "amplitude_num": num, "amplitude_den": den}


def e0_blob(gains=GAINS):
    """Stage E0's shape: one filter of the reference pulse's 64 taps, a row for each channel."""
    return weights.matched_filter(PROFILE, PULSE, gains)


def case(frames, schedule, blob=None, seed=SEED, epoch=0):
    return seam.Case(PROFILE, seed, SIGMA, frames, schedule, e0_blob() if blob is None else blob, epoch)


# The first record at index 0, so that the chain's very first frames carry a pulse, at a ratio with ties
# (e0's second sample is 1, and 1 * 3/2 is 1.5).
FIRST = [rec(0, 3, 2)]
# Six amplitudes: five ratios of the model's own test and one that takes the pulse near the top of the range.
# The second starts where the first ends and the third where the second ends: records that touch.
SCHEDULE = [rec(5, 3, 2), rec(5 + L, -7, 4), rec(5 + 2 * L, LARGE, 1), rec(210, 5, 3), rec(280, -2, 1), rec(350, 33, 10)]


def first_case():
    return case(FIRST_FRAMES, FIRST)


def quiet(refusals):
    assert refusals == (0, 0, 0), "a block refused during a run no block should refuse: core %s, source %s, injector %s" % tuple(
        host.NAME_OF.get(r, r) for r in refusals)


_kept = {}


async def hold_run(chain, test, label, this, expected=None, during=None, keep=None):
    """Run the chain on a case and hold every record against the model's. Returns the RTL's digest."""
    if expected is None:
        expected, _truth = run.detect(this.noise(), this.schedule, this.frames, this.blob, this.epoch)
    assert len(expected) == this.frames
    seen, clocks, unknown, refusals = await chain.run(this, during=during)
    _count, _model, rtl = seam.hold_records(test, label, seen, seam.words(expected), unknown)
    quiet(refusals)
    if keep is not None:
        _kept[keep] = (seen, clocks)
    return rtl


async def kept(chain, key, this, during=None):
    """(the words, the clock of each) of a run an identity test made and kept; made here when it is not there."""
    if key not in _kept:
        seen, clocks, unknown, refusals = await chain.run(this, during=during)
        assert unknown is None, unknown
        quiet(refusals)
        _kept[key] = (seen, clocks)
    return _kept[key]


# ------------------------------------------------------------------ bit identity, end to end

@cocotb.test()
async def bit_identity_first_frames(dut):
    test = "bit_identity_first_frames"
    chain = seam.Chain(dut)
    this = first_case()
    plain, _ = run.detect(this.noise(), [], this.frames, this.blob)
    with_pulse, _ = run.detect(this.noise(), this.schedule, this.frames, this.blob)
    at = seam.first_difference(plain, with_pulse)
    assert at is not None and at <= 3, "the pulse does not reach the first records: %r" % (at,)
    await hold_run(chain, test, "E0's shape, a record at index 0", this, keep="first")
    await chain.finish()


@cocotb.test()
async def bit_identity_chain(dut):
    test = "bit_identity_chain"
    chain = seam.Chain(dut)
    this = case(CHAIN_FRAMES, SCHEDULE)
    stream, truth = seam.model_stream(this)
    changed = sum(1 for a, b in zip(tuple(this.noise()), stream) if a != b)
    assert len(truth) == len(SCHEDULE) and changed > len(SCHEDULE) * (L - 20), "the schedule adds too little: %d" % changed
    top = max(max(f) for f in stream)
    assert top > PROF["sample_max"] * 3 // 4, "no sample comes near the top of the range: %d" % top
    await hold_run(chain, test, "E0's shape, six amplitudes", this)
    # A shape that is not E0's: both filters and both hidden units the build holds, 63 taps, abs twice, a pool.
    caps = await host.capabilities(dut)
    assert (caps["cap_filters"], caps["cap_hidden"], caps["cap_rows"]) == (2, 2, 3), caps
    blob = host.blob_of(PROFILE, TWO_FILTERS, caps["cap_taps"] - 1, random.Random(SEED + 1), ABS, 3, 5,
                        hidden=2, hidden_shift=7, between=ABS)
    other = case(OTHER_SHAPE_FRAMES, [rec(3, -5, 2), rec(3 + L, 7, 3)], blob=blob, seed=SEED + 1, epoch=7)
    await hold_run(chain, test, "another shape: two filters, a pool of 3, two hidden units", other)
    await chain.finish()


# ------------------------------------------------------------------ truth isolation

# Four wordings of the truth that add the same samples. The first has a denominator of 1 and one record.
ISOLATION = (
    ("as first written", [rec(66, 3, 1)]),
    ("the same ratio written otherwise", [rec(66, 6, 2)]),
    ("a record that adds only zeros put in", [rec(1, 0, 5), rec(66, 3, 1)]),
    ("a record that rounds to zeros, at another index", [rec(2, 1, 100000), rec(66, 3, 1)]),
)


def isolation_case(schedule):
    return case(ISOLATION_FRAMES, schedule, seed=SEED + 2)


@cocotb.test()
async def truth_isolation(dut):
    test = "truth_isolation"
    chain = seam.Chain(dut)
    streams, truths, digests = [], [], []
    for label, schedule in ISOLATION:
        stream, truth = seam.model_stream(isolation_case(schedule))
        streams.append(stream)
        truths.append(truth)
    assert all(s == streams[0] for s in streams), "the model's streams differ: these are not the same samples"
    assert len(set(repr(t) for t in truths)) == len(ISOLATION), "two of the wordings are the same truth"
    assert streams[0] != tuple(isolation_case([]).noise()), "the truth adds nothing"
    for n, (label, schedule) in enumerate(ISOLATION):
        digests.append(await hold_run(chain, test, label, isolation_case(schedule), keep="isolation" if n == 0 else None))
    assert len(set(digests)) == 1, "the chain's records changed with the truth: %r" % (digests,)
    await chain.finish()


# ------------------------------------------------------------------ a swap through the chain

SWAP_AT = 40                # the committed index: inside the first pulse's window
SWAP_AFTER = 12             # the shadow is written once this many records of the run are out
SWAP_SCHEDULE = [rec(6, 5, 2), rec(6 + L, -3, 1)]


def swap_case():
    return case(SWAP_FRAMES, SWAP_SCHEDULE, seed=SEED + 3, epoch=3)


def composition_is_run_py(this):
    """With nothing done to the core first, `seam_host.model_records` is `model.run.detect`, record for record."""
    assert seam.model_records(this) == run.detect(this.noise(), this.schedule, this.frames, this.blob, this.epoch)


def swap_while_running(other, at, after=SWAP_AFTER):
    """For `Chain.run`: while the source runs, wait until `after` records of the run are out, write `other`
    to the shadow, commit at `at`."""

    async def during(chain):
        first = chain.collected                     # the records of this test's earlier runs
        await seam.records_out(chain, first + after, seam.clock_of(PROFILE, after) + 64)
        await host.write_shadow(chain.dut, other)
        await host.commit(chain.dut, at)
        refused = await host.take_refusal(chain.dut)
        assert refused == 0, "the shadow write or the commit was refused: %s" % host.NAME_OF.get(refused, refused)
        assert chain.records - first < at, "the commit landed after its own index: %d record(s) were out" % (chain.records - first)

    return during


@cocotb.test()
async def bit_identity_swap(dut):
    test = "bit_identity_swap"
    chain = seam.Chain(dut)
    this = swap_case()
    composition_is_run_py(this)
    other = e0_blob(OTHER_GAINS)
    unswapped, _ = seam.model_records(this)
    expected, _ = seam.model_records(this, [("write_shadow", other), ("commit", SWAP_AT)])
    # the swap is one that shows: from its index on every record has another epoch, and its own record another score
    assert seam.first_difference(unswapped, expected) == SWAP_AT
    assert all(r["epoch"] == this.epoch for r in expected[:SWAP_AT]) and all(r["epoch"] == this.epoch + 1 for r in expected[SWAP_AT:])
    assert expected[SWAP_AT]["score"] != unswapped[SWAP_AT]["score"]
    await hold_run(chain, test, "E0's shape: other weights from index %d" % SWAP_AT, this, expected=expected,
                   during=swap_while_running(other, SWAP_AT), keep="swap")

    # A shape with a pool, so that the outputs after the swap settle, and with a hidden unit.
    caps = await host.capabilities(dut)
    rng = random.Random(SEED + 4)
    blob = host.blob_of(PROFILE, TWO_FILTERS[::-1], caps["cap_taps"], rng, C.RECTIFIERS["pass"], caps["cap_pool"], 3,
                        hidden=1, hidden_shift=9, between=C.RECTIFIERS["pass"])
    pooled = case(SWAP_FRAMES, SWAP_SCHEDULE, blob=blob, seed=SEED + 4, epoch=9)
    again = host.reweighted(rng, blob)
    assert again != blob
    expected, _ = seam.model_records(pooled, [("write_shadow", again), ("commit", SWAP_AT)])
    settling = [r["index"] for r in expected if r["flags"] & FLAG_SETTLING]
    assert settling == list(range(SWAP_AT, SWAP_AT + caps["cap_pool"] - 1)), settling
    await hold_run(chain, test, "a pool of %d: the outputs that settle" % caps["cap_pool"], pooled, expected=expected,
                   during=swap_while_running(again, SWAP_AT))
    await chain.finish()


# ------------------------------------------------------------------ the learner's hand-over through the chain

VECTOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "vectors", "seam-2", "handover.json")


def hand_over_case():
    """What vectors/seam-2/handover.json pins for this profile: the chain's configuration, the blob the core
    starts with, and the blob the learner handed over. Nothing of `learn/` is imported here: the trainer
    cannot run in the simulation image, and tests/test_seam2_handover.py holds these bytes to it outside."""
    with open(VECTOR, encoding="utf-8") as f:
        pinned = json.load(f)["cases"][PROFILE]
    blob = bytes.fromhex(pinned["blob_hex"])
    assert hashlib.sha256(blob).hexdigest() == pinned["blob_sha256"]
    this = seam.Case(PROFILE, pinned["seed"], tuple(pinned["sigma"]), pinned["frames"], pinned["schedule"],
                     bytes.fromhex(pinned["start_hex"]))
    return this, blob, pinned


@cocotb.test()
async def bit_identity_hand_over(dut):
    """Learned weights go into the RTL: the trainer's blob, written to the shadow through the bus once the
    training period's records are out, committed at the hand-over index, and every record the model's.
    This is not stage E1: no efficiency is read from it and none is claimed."""
    test = "bit_identity_hand_over"
    chain = seam.Chain(dut)
    this, blob, pinned = hand_over_case()
    at, period = pinned["hand_over_at"], pinned["period"]
    expected, _ = seam.model_records(this, [("write_shadow", blob), ("commit", at)])
    unlearned, _ = seam.model_records(this)
    assert seam.first_difference(unlearned, expected) == at and expected[at]["score"] != unlearned[at]["score"]
    # Before the hand-over the core holds one tap, the newest, a weight a channel: every record is its own
    # frame's weighted sum, so the records of the training period hold the frames the trainer was given.
    stream, _ = seam.model_stream(this)
    newest = pinned["start_newest_tap"]
    assert all(expected[i]["score"] == sum(w * x for w, x in zip(newest, stream[i])) for i in range(at))
    assert len(set(r["score"] for r in expected[:period])) > period // 4, "the training period's scores hold too little"
    await hold_run(chain, test, "the learner's blob of %d truth records, handed over at index %d" % (pinned["count"], at),
                   this, expected=expected, during=swap_while_running(blob, at, after=period))
    await chain.finish()


# ------------------------------------------------------------------ the clocks, and the bus

@cocotb.test()
async def the_chains_clocks(dut):
    """Every word right and a clock late is a fault no comparison of words sees. Record k is seen at
    1 + 20 * CHANNELS * (k + 1) + 52 + 11 clocks after the edge that takes the start write."""
    test = "the_chains_clocks"
    chain = seam.Chain(dut)
    this = first_case()
    seen, clocks = await kept(chain, "first", this)
    assert len(seen) == this.frames == len(clocks), (len(seen), len(clocks))
    seam.hold_clocks(test, "the clock of each record", clocks, [seam.clock_of(PROFILE, k) for k in range(this.frames)])
    await chain.finish()


@cocotb.test()
async def one_bus_three_blocks(dut):
    """Each block answers on the one bus with its own word, and a write reaches each."""
    test = "one_bus_three_blocks"
    chain = seam.Chain(dut)
    b = chain.bus
    await b.reset()
    access = C.REFUSAL_CODES["REGISTER_ACCESS"]
    seen = [await b.read(bus.offset("id")), await b.read(bus.offset("cap_noise_table")),
            await b.read(bus.offset("cap_inject_pending")), await b.read(0), await b.read(bus.offset("id"))]
    expected = [C.BUS["magic"], C.MAX_NOISE_TABLE, C.MAX_INJECT_PENDING, 0, C.BUS["magic"]]
    seen += list(await chain.refusals())
    expected += [0, 0, 0]
    # a write to a read-only row of each block: each block refuses it, and each refusal is read through the bus
    for row in ("id", "cap_noise_table", "cap_inject_pending"):
        await b.write(bus.offset(row), 1)
    seen += list(await chain.refusals())
    expected += [access, access, access]
    # each cleared by a write of zero, one at a time: the others stand
    for n, row in enumerate(("refusal", "src_refusal", "inj_refusal")):
        await b.write(bus.offset(row), 0)
        seen += list(await chain.refusals())
        expected += [0] * (n + 1) + [access] * (2 - n)
    host.hold_words(test, "a word of each block, and a refusal of each", seen, expected)
    await chain.finish()


# ------------------------------------------------------------------ the controls on the model side

def expect_mismatch(test, label, seen, wrong, right, at, field):
    """Hand the comparison a wrong model: it must report a WORD mismatch at the first record where the wrong
    model's records leave the right model's, and name the field."""
    assert seam.first_difference(wrong, right) == at, (seam.first_difference(wrong, right), at)
    try:
        seam.hold_records(test, label, seen, seam.words(wrong), None)
    except harness.Mismatch as e:
        assert e.kind == "WORD" and e.at == at and field in e.detail, (e.kind, e.at, e.detail)
        return
    raise AssertionError("the comparison passed a wrong model: %s" % label)


@cocotb.test()
async def control_model_injector_bypassed(dut):
    """A model whose core reads the source's frames: the comparison must stop at the first record the pulse reaches."""
    test = "control_model_injector_bypassed"
    chain = seam.Chain(dut)
    this = first_case()
    seen, _clocks = await kept(chain, "first", this)
    right, _ = run.detect(this.noise(), this.schedule, this.frames, this.blob)
    core = Core(this.blob)
    wrong = tuple(core.step(frame) for frame in this.noise())
    at = seam.first_difference(wrong, right)
    assert at is not None and at <= 3, at
    seam.hold_records(test, "the right model, first", seen, seam.words(right), None)
    expect_mismatch(test, "a model with no injector", seen, wrong, right, at, "score")
    await chain.finish()


@cocotb.test()
async def control_model_swap(dut):
    """A model that never swaps, one that swaps a frame late, one a frame early, and one whose shadow was never
    written: each must be reported at the record where it leaves the right model."""
    test = "control_model_swap"
    chain = seam.Chain(dut)
    this = swap_case()
    other = e0_blob(OTHER_GAINS)
    seen, _clocks = await kept(chain, "swap", this, swap_while_running(other, SWAP_AT))
    right, _ = seam.model_records(this, [("write_shadow", other), ("commit", SWAP_AT)])
    seam.hold_records(test, "the right model, first", seen, seam.words(right), None)
    never, _ = seam.model_records(this)
    late, _ = seam.model_records(this, [("write_shadow", other), ("commit", SWAP_AT + 1)])
    early, _ = seam.model_records(this, [("write_shadow", other), ("commit", SWAP_AT - 1)])
    unwritten, _ = seam.model_records(this, [("commit", SWAP_AT)])
    expect_mismatch(test, "a model that never swaps", seen, never, right, SWAP_AT, "epoch")
    expect_mismatch(test, "a model that swaps a frame late", seen, late, right, SWAP_AT, "epoch")
    expect_mismatch(test, "a model that swaps a frame early", seen, early, right, SWAP_AT - 1, "epoch")
    # The epoch alone would show those three. A swap to the SAME weights has the right epoch and the wrong score.
    assert all(a["epoch"] == b["epoch"] for a, b in zip(unwritten, right))
    expect_mismatch(test, "a model that swaps with the shadow never written", seen, unwritten, right, SWAP_AT, "score")
    await chain.finish()


@cocotb.test()
async def control_model_truth_reaches_the_core(dut):
    """Round 1's control, here: a model whose core is handed one bit of truth. The chain's records are held
    to it, and it must be reported no later than a pulse's length after the truth record's index."""
    test = "control_model_truth_reaches_the_core"
    chain = seam.Chain(dut)
    _label, schedule = ISOLATION[0]
    this = isolation_case(schedule)
    seen, _clocks = await kept(chain, "isolation", this)
    right, truth = run.detect(this.noise(), this.schedule, this.frames, this.blob)
    seam.hold_records(test, "the right model, first", seen, seam.words(right), None)
    starts = set(r["index"] for r in truth)
    core = Core(this.blob)
    stream, _ = seam.model_stream(this)
    wrong = []
    for i, frame in enumerate(stream):
        if i in starts:                                   # one bit of truth: the lowest bit of the first channel
            frame = (frame[0] ^ 1,) + tuple(frame[1:])
        wrong.append(core.step(frame))
    at = seam.first_difference(wrong, right)
    assert at is not None and min(starts) <= at < min(starts) + L, at
    expect_mismatch(test, "a model whose core is handed one bit of truth", seen, tuple(wrong), right, at, "score")
    await chain.finish()

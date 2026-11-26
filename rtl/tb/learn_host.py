"""What the learner's benches share: the model's run, the design's run of the same script, and the checks.

THE MODEL'S SIDE is `model.learner.Learner`, run by `model.run._learning_run`, the loop `model.run.learning`
itself runs (LRN-B's note of 2026-11-25 21:41): a script maps a next index to host operations, each made
before the frame of that index is stepped, or after the last frame. For the chain, `model.run.learning`
whole: the source, the injector, the core and the learner.

THE DESIGN'S SIDE makes the same operations at the same next index, as register writes. Where an
operation's writes land is its `placement`:

    "early"  at its index's slot, before the frame of that index, with no frame taken at their edges;
    "last"   its last write at the edge just before the edge that takes the frame of that index: the last
             clock at which the next index is that index;
    "with"   its last write at the edge that takes the frame BEFORE that index: the first clock at which the
             next index is that index, since a write is ordered after the frame at its edge. A "with"
             operation is the first of its index's list.

After each operation the two refusal registers, the learner's and the core's, are read and cleared, and
each is held to what this design latches for the model's outcome (`expected_codes`): every name the learner
raises, UPDATE_UNFINISHED among them, in `lrn_refusal`; a commit's or a shadow write's own names in the
core's `refusal`. An unmade update's QUANTISE_INPUT, latched at its finish, is counted in.

THE CHECKS COLLECT AND DO NOT RAISE until the end (`Checks`): the score records are held first, through
`harness.hold`, so a fault of the records is reported as the harness's mismatch, and only then is any
register that differed raised, with the first of them named.

WHAT THIS CANNOT SEE, each a stated limit of docs/rtl/learn.md:
  - The script, the truth and the blob given to the design are the ones the model is run on. One wrong in
    both alike is seen by nothing here.
  - The register checks are assertions, not the harness's comparison: a mutant whose fault shows only in a
    register is held by the test's failure and its message, and names no kind of mismatch.
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

from spec import constants as C
from model import inject, learner as L, run as R, weights, source

import harness
import core_host as host
import seam_host
import source_bus

WORD_BITS = C.BUS["word_bits"]
WORD_MASK = (1 << WORD_BITS) - 1
COUNTERS = L.COUNTS + L.COUNTERS                     # the eight count registers, by the definition's names
PASS = C.RECTIFIERS["pass"]
STATUS = C.REGISTER_BITS["lrn_status"]
NAME_OF = dict((c, n) for n, c in C.REFUSAL_CODES.items())


def offset(name, word=0):
    return host.offset(name, word)


def code(name):
    return 0 if name is None else C.REFUSAL_CODES[name]


# ------------------------------------------------------------------ blobs and frames

def matched_blob(profile, rows):
    """The matched-filter configuration: one filter reading every channel, `rows` {channel: coefficients}."""
    return weights.pack(profile, [dict((c, tuple(v)) for c, v in rows.items())], (1,), PASS, 1, 0)


def start_blob(profile, taps):
    """A start set whose newest tap is another weight in each channel, so that every record before a commit
    is its own frame's weighted sum and says something (docs/rtl/seam.md, section 6's reason)."""
    channels = C.PROFILES[profile]["channels"]
    return matched_blob(profile, dict((c, [0] * (taps - 1) + [c + 2]) for c in range(channels)))


def zeros(profile, n):
    return [(0,) * C.PROFILES[profile]["channels"]] * n


def impulses(profile, taps):
    """For each channel an impulse whose value differs by channel, then `taps` frames of zeros: each of the
    `taps` scores after an impulse is one coefficient of that channel times the impulse."""
    channels = C.PROFILES[profile]["channels"]
    out = []
    for c in range(channels):
        out.append(tuple(c + 1 if k == c else 0 for k in range(channels)))
        out += zeros(profile, taps)
    return out


# ------------------------------------------------------------------ the model's side

def model_run(blob, indexes, frames, script, update_frames, count_bits, epoch=0, learner_class=L.Learner,
              before=None):
    """(the learner, its records, its outcomes): the model's own loop over the frames with the script.
    `before` is called with the learner before the first frame, to write a state into it."""
    learner = learner_class(blob, [{"index": j} for j in indexes], update_frames, count_bits, epoch)
    if before is not None:
        before(learner)
    records, outcomes = R._learning_run(learner, list(frames), script)
    return learner, list(records), outcomes


def expected_codes(op, name, words=0):
    """(what lrn_refusal latches, how many times, what the core's refusal latches) for one operation's
    outcome. A shadow write is a shadow_begin and `words` words: while an update is unfinished each is held
    back and refused, and when the core refuses its begin each word after is refused too."""
    if name is None:
        return 0, 0, 0
    if name == "UPDATE_UNFINISHED":
        return code(name), (1 + words if op == "write_shadow" else 1), 0
    if op == "update":
        return code(name), 1, 0
    return 0, 0, code(name)


def op_writes(op, argument):
    """The register writes that make one operation, in order."""
    if op == "update":
        return [(offset("lrn_update_at", 0), argument & WORD_MASK), (offset("lrn_update_at", 1), argument >> WORD_BITS)]
    if op == "commit":
        return host.commit_pairs(argument)
    if op == "write_shadow":
        words = host.words_of(weights.unpack(argument))
        return [(offset("shadow_begin"), len(words))] + host.stream_pairs(words)
    raise ValueError("no operation %r" % (op,))


# ------------------------------------------------------------------ the checks

class Checks:
    """Register words that differ, collected; raised by `close` after the records are held."""

    def __init__(self):
        self.wrong = []

    def same(self, what, have, want):
        if have != want:
            self.wrong.append("%s: the design has %r, the model %r" % (what, have, want))

    def close(self):
        assert not self.wrong, "%d register word(s) differ; the first: %s" % (len(self.wrong), self.wrong[0])


async def read(dut, name, word=0):
    return await host.read(dut, name, word)


async def read_wide(dut, name):
    return await host.read_wide(dut, name)


async def counters(dut):
    out = {}
    for name in COUNTERS:
        out[name] = await read_wide(dut, name)
    return out


async def status(dut):
    word = await read(dut, "lrn_status")
    return dict((name, (word >> bit) & 1) for name, bit in STATUS.items())


async def check_registers(dut, checks, learner, latched, label):
    """The eight counts and lrn_status, against the model's at this next index. `latched` is the list of
    names lrn_refusal has latched since the bench last cleared it."""
    have = await counters(dut)
    for name, want in learner.counters().items():
        checks.same("%s: %s" % (label, name), have[name], want)
    st = await status(dut)
    for name, want in learner.status().items():
        checks.same("%s: lrn_status.%s" % (label, name), st[name], want)
    checks.same("%s: lrn_status.refused" % label, st["refused"], int(len(latched) > 0))
    checks.same("%s: lrn_status.refused_again" % label, st["refused_again"], int(len(latched) > 1))
    first = await read(dut, "lrn_refusal")
    checks.same("%s: lrn_refusal" % label, first, code(latched[0]) if latched else 0)


class Records:
    """Every score record the design puts out over the whole test, sampled at falling edges."""

    def __init__(self, dut):
        self.dut, self.words, self.clocks, self.unknown, self.clock, self.on = dut, [], [], None, 0, True
        self.task = cocotb.start_soon(self._watch())

    async def _watch(self):
        while self.on:
            await RisingEdge(self.dut.clk)
            await FallingEdge(self.dut.clk)
            self.clock += 1
            valid = str(self.dut.out_valid.value)
            if valid not in ("0", "1"):
                self.unknown = self.unknown or (len(self.words), "out_valid = %s" % valid)
                continue
            if valid == "1":
                value = self.dut.out_record.value
                if not value.is_resolvable:
                    self.unknown = self.unknown or (len(self.words), "out_record = %s" % value)
                    self.words.append(0)
                else:
                    self.words.append(value.to_unsigned())
                self.clocks.append(self.clock)

    async def stop(self, clocks=40):
        for _ in range(clocks):
            await FallingEdge(self.dut.clk)
        self.on = False
        await self.task


def hold_records(test, label, seen, records, unknown):
    """THE COMPARISON, as `harness.compare` makes it, of every score record of a test."""
    return harness.hold(test, label, list(seen), [harness.record_word(r) for r in records],
                        width_bytes=harness.RECORD_BYTES, prefix=harness.SCORE_PREFIX,
                        describe=harness.describe_records, unknown=unknown)


class Latch:
    """What lrn_refusal has latched since the bench last cleared it, worked from the model's outcomes."""

    def __init__(self, learner):
        self.latched = []
        self.quantise = sorted(u["finish"] for u in learner.updates if u.get("name") == "QUANTISE_INPUT")
        self.seen = 0

    def finishes_to(self, index):
        while self.seen < len(self.quantise) and self.quantise[self.seen] <= index:
            self.latched.append("QUANTISE_INPUT")
            self.seen += 1


async def check_op(dut, checks, latch, label, index, op, argument, name, words):
    """After one operation: both refusal registers read, held to the model's outcome, and cleared."""
    lrn_want, count, core_want = expected_codes(op, name, words)
    latched = latch.latched + ([NAME_OF[lrn_want]] * count if lrn_want else [])
    lrn = await read(dut, "lrn_refusal")
    core = await read(dut, "refusal")
    await host.write_many(dut, [(offset("lrn_refusal"), 0), (offset("refusal"), 0)])
    what = "%s: after %s(%s) at next index %d, the model's outcome %s" % (label, op, "a blob" if op == "write_shadow"
                                                                       else argument, index, name)
    checks.same(what + ": lrn_refusal", lrn, code(latched[0]) if latched else 0)
    checks.same(what + ": refusal", core, core_want)
    latch.latched = []


def outcomes_by_index(outcomes):
    out = {}
    for index, _op, _arg, name in outcomes:
        out.setdefault(index, []).append(name)
    return out


# ------------------------------------------------------------------ learn_small

class Small:
    """learn_small: its stream, its truth port and its register port, driven at falling edges."""

    def __init__(self, dut, profile):
        self.dut, self.profile = dut, profile
        Clock(dut.clk, 10, unit="ns").start()

    async def reset(self):
        dut = self.dut
        await FallingEdge(dut.clk)
        dut.rst.value = 1
        dut.in_valid.value = 0
        dut.in_frame.value = 0
        dut.truth_valid.value = 0
        dut.truth_index.value = 0
        host.idle(dut)
        for _ in range(3):
            await FallingEdge(dut.clk)
        dut.rst.value = 0

    async def push(self, indexes):
        """Hand the learner truth indexes, one a clock, as the injector does as it takes each record."""
        dut = self.dut
        for j in indexes:
            await FallingEdge(dut.clk)
            dut.truth_valid.value = 1
            dut.truth_index.value = j
        await FallingEdge(dut.clk)
        dut.truth_valid.value = 0

    async def drive(self, frames, script, learner, outcomes, checks, *, spacing=1, placement=None, pushes=None,
                    with_push=None, probes=None, raws=None, label="run"):
        """Every frame, with the script's operations at their next indexes, as the model made them.

        `placement` maps (index, position in that index's list) to "early" (the default), "last" or "with".
        `pushes` maps a next index to truth indexes handed over before that index's operations; `with_push`
        maps a next index to one truth index handed over at the edge that takes the frame before it.
        `probes` maps a next index to a coroutine function, called with the dut there before the operations.
        `raws` maps a next index to writes the model has no operation for, made after the model's ones, each
        (writes, the name lrn_refusal latches or None, how many times, the name the core latches or None),
        which this design states and the model does not. `spacing` is at least the clocks from one frame's
        edge to the next. Returns the Latch.
        """
        dut = self.dut
        placement = placement or {}
        pushes = pushes or {}
        with_push = with_push or {}
        probes = probes or {}
        raws = raws or {}
        names = outcomes_by_index(outcomes)
        latch = Latch(learner)
        n = len(frames)

        async def op_now(index, pos):
            op, argument = script[index][pos]
            writes = op_writes(op, argument)
            await host.write_many(dut, writes)
            await check_op(dut, checks, latch, label, index, op, argument, names[index][pos], len(writes) - 1)

        async def raw_now(index, writes, lrn_name, count, core_name):
            await host.write_many(dut, writes)
            latched = latch.latched + [lrn_name] * (count if lrn_name else 0)
            lrn = await read(dut, "lrn_refusal")
            core = await read(dut, "refusal")
            await host.write_many(dut, [(offset("lrn_refusal"), 0), (offset("refusal"), 0)])
            what = "%s: after the writes %s at next index %d" % (label, [(hex(a), v) for a, v in writes[:3]], index)
            checks.same(what + ": lrn_refusal", lrn, code(latched[0]) if latched else 0)
            checks.same(what + ": refusal", core, code(core_name))
            latch.latched = []

        for index in range(n + 1):
            latch.finishes_to(index)
            if index in pushes:
                await self.push(pushes[index])
            if index in probes:
                await probes[index](dut)
            ops = script.get(index, [])
            last = None
            for pos in range(len(ops)):
                where = placement.get((index, pos), "early")
                if where == "early":
                    await op_now(index, pos)
                elif where == "last":
                    assert last is None and pos == len(ops) - 1, "a 'last' operation is the last of its index"
                    last = pos
                else:
                    assert pos == 0, "a 'with' operation is the first of its index"
            for writes, lrn_name, count, core_name in raws.get(index, []):
                await raw_now(index, writes, lrn_name, count, core_name)
            if index == n:
                if last is not None:
                    await op_now(index, last)
                break
            nxt = (index + 1 in script and placement.get((index + 1, 0)) == "with")
            # the earlier writes of a "last" operation of this index, and of a "with" operation of the next
            pre = []
            if last is not None:
                pre += op_writes(*ops[last])[:-1]
            if nxt:
                pre += op_writes(*script[index + 1][0])[:-1]
            if pre:
                await host.write_many(dut, pre)
            # the slots: idle clocks, the "last" write, then the frame with the "with" write and push
            for _ in range(max(0, spacing - 1 - (1 if last is not None else 0))):
                await FallingEdge(dut.clk)
            if last is not None:
                at, word = op_writes(*ops[last])[-1]
                dut.reg_valid.value, dut.reg_we.value, dut.reg_addr.value, dut.reg_wdata.value = 1, 1, at, word & WORD_MASK
                await FallingEdge(dut.clk)
                dut.reg_valid.value, dut.reg_we.value = 0, 0
            if nxt:
                at, word = op_writes(*script[index + 1][0])[-1]
                dut.reg_valid.value, dut.reg_we.value, dut.reg_addr.value, dut.reg_wdata.value = 1, 1, at, word & WORD_MASK
            if index + 1 in with_push:
                dut.truth_valid.value, dut.truth_index.value = 1, with_push[index + 1]
            dut.in_valid.value = 1
            dut.in_frame.value = harness.frame_word(self.profile, frames[index])
            await FallingEdge(dut.clk)
            dut.in_valid.value = 0
            dut.truth_valid.value = 0
            dut.reg_valid.value, dut.reg_we.value = 0, 0
            if last is not None:
                op, argument = ops[last]
                await check_op(dut, checks, latch, label, index, op, argument, names[index][last],
                               len(op_writes(op, argument)) - 1)
            if nxt:
                op, argument = script[index + 1][0]
                latch.finishes_to(index + 1)
                await check_op(dut, checks, latch, label, index + 1, op, argument, names[index + 1][0],
                               len(op_writes(op, argument)) - 1)
                placement[(index + 1, 0)] = "done"
        return latch


async def small_case(bench, test, label, blob, indexes, frames, script, *, update_frames=16, count_bits=3,
                     spacing=None, placement=None, pushes=None, with_push=None, probes=None, raws=None,
                     learner_class=L.Learner, before=None, before_rtl=None, model=None, load=True):
    """One whole run on learn_small, held to the model: every record, each operation's refusals, and the
    eight counts and lrn_status at the end. Returns the model's learner. The design is reset and loaded here;
    `before_rtl` is a coroutine function called with the dut after the load, to write a state into it."""
    dut, profile = bench.dut, bench.profile
    learner, records, outcomes = model if model is not None else model_run(
        blob, indexes, frames, script, update_frames, count_bits, learner_class=learner_class, before=before)
    await bench.reset()
    if load:
        await host.load(dut, blob)
    if before_rtl is not None:
        await before_rtl(dut)
    later = set(with_push.values()) if with_push else set()
    for v in (pushes or {}).values():
        later |= set(v)
    await bench.push([j for j in indexes if j not in later])
    seen = Records(dut)
    checks = Checks()
    period = spacing if spacing is not None else 20 * C.PROFILES[profile]["channels"]
    latch = await bench.drive(frames, script, learner, outcomes, checks, spacing=period, placement=dict(placement or {}),
                              pushes=pushes, with_push=with_push, probes=probes, raws=raws, label=label)
    await seen.stop()
    latch.finishes_to(len(frames))
    await check_registers(dut, checks, learner, latch.latched, label + ", at the end")
    if records:
        hold_records(test, label, seen.words, records, seen.unknown)
    else:
        checks.same(label + ": records", len(seen.words), 0)
    checks.close()
    return learner


# ------------------------------------------------------------------ learn_chain

class Chain:
    """learn_chain: the source's frames, the injector's truth, the core and the learner behind one bus.

    The source offers a frame every `seam_host.period` clocks, so the core takes one exactly that many clocks
    after the last (docs/rtl/seam.md, row K3). `took[i]` is the rising edge, counted by the bus, after which
    the core's next index is i: a write landing at took[i] + period - 1 is at the last clock at which the
    next index is i, and one landing at took[i] + period is at the edge that takes frame i.
    """

    def __init__(self, dut):
        self.dut = dut
        self.bus = source_bus.Bus(dut, stream_in=False)
        self.took = {}
        cocotb.start_soon(self._watch())

    async def _watch(self):
        last = None
        while True:
            await FallingEdge(self.dut.clk)
            value = self.dut.u_core.next_index.value
            i = value.to_unsigned() if value.is_resolvable else None
            if i != last:
                self.took[i] = self.bus.edges
                last = i

    def index(self):
        return self.dut.u_core.next_index.value.to_unsigned()

    async def until(self, i, clocks, what):
        """Return at the first falling edge at which the core's next index is i; never wait without a bound."""
        waited = 0
        while self.index() < i:
            assert waited < clocks, "after %d clocks the core's next index is %d, not %d (%s)" % (
                waited, self.index(), i, what)
            await FallingEdge(self.dut.clk)
            waited += 1
        assert self.index() == i, "the core's next index is %d, past %d (%s)" % (self.index(), i, what)

    async def land(self, write, edge):
        """Put one write on the port so that the rising edge numbered `edge` takes it."""
        dut, b = self.dut, self.bus
        assert b.edges < edge, "the edge %d has passed (it is %d)" % (edge, b.edges)
        while b.edges < edge - 1:
            await FallingEdge(dut.clk)
        dut.reg_valid.value, dut.reg_we.value, dut.reg_addr.value, dut.reg_wdata.value = 1, 1, write[0], write[1] & WORD_MASK
        await FallingEdge(dut.clk)
        dut.reg_valid.value, dut.reg_we.value = 0, 0

    async def start(self, case, late_records=(), before_rtl=None):
        """Reset; the core loaded; the source's table and the injector's records, but the late ones; the
        source started. Returns the collector of records, started before the start write. `before_rtl` is a
        coroutine function called with the dut after the load, to write a state into it."""
        dut, b = self.dut, self.bus
        await b.reset()
        self.took = {}
        await host.load(dut, case.blob, case.epoch)
        if before_rtl is not None:
            await before_rtl(dut)
        pairs = seam_host.table_writes(case.noise().table)
        for record in case.schedule:
            if record not in late_records:
                pairs += seam_host.truth_writes(record)
        await b.write_many(pairs)
        seen = Records(dut)
        await b.write_many(source_bus.words_of("src_seed", case.seed) + source_bus.words_of("src_frames", case.frames))
        return seen

    async def run(self, test, label, case, script, *, update_frames=C.LEARN_UPDATE_FRAMES,
                  count_bits=C.LEARN_COUNT_BITS, placement=None, late=None, before=None, before_rtl=None):
        """One run of the chain held to `model.run.learning`: every record, each operation's refusals, the
        eight counts and lrn_status at the end, and the injector's refusal 0. `placement` maps (index, 0) to
        "last" for an index's one operation, and (index, 0) to "with" for the next index's; `late` maps a next
        index to truth records offered once the core's next index is that index. `before` writes a state into
        the model's learner before its first frame, and `before_rtl` the same into the design: then the model
        is `model.run.learning`'s own lines, its injector, a learner and its loop, with the state written
        between the learner's making and the loop. Returns the learner."""
        dut, b = self.dut, self.bus
        placement = dict(placement or {})
        late = late or {}
        if before is None:
            records, _truth, outcomes, learner = R.learning(case.noise(), case.schedule, case.frames, case.blob,
                                                            script, update_frames, count_bits, case.epoch)
        else:
            injected, truth = inject.inject(weights.unpack(case.blob)["profile"], case.noise(), case.schedule,
                                            case.frames)
            learner = L.Learner(case.blob, truth, update_frames, count_bits, case.epoch)
            before(learner)
            records, outcomes = R._learning_run(learner, injected, script)
        names = outcomes_by_index(outcomes)
        latch = Latch(learner)
        checks = Checks()
        late_records = [r for rs in late.values() for r in rs]
        seen = await self.start(case, late_records, before_rtl)
        period = seam_host.period(case.profile)
        bound = period * (case.frames + 4) + 400
        withs = set(i for (i, pos), p in placement.items() if p == "with")
        for index in sorted(set(script) | set(late)):
            if index in withs:
                continue                                  # made by the index before it
            await self.until(index, bound, "for the operations at next index %d" % index)
            latch.finishes_to(index)
            for record in late.get(index, []):
                await b.write_many(seam_host.truth_writes(record))
            ops = script.get(index, [])
            landed = []
            for pos, (op, argument) in enumerate(ops):
                writes = op_writes(op, argument)
                if placement.get((index, pos)) == "last":
                    await b.write_many(writes[:-1])
                    landed.append((self.took[index] + period - 1, index, pos, writes))
                else:
                    await b.write_many(writes)
                    await check_op(dut, checks, latch, label, index, op, argument, names[index][pos], len(writes) - 1)
            if index + 1 in withs:
                op, argument = script[index + 1][0]
                writes = op_writes(op, argument)
                await b.write_many(writes[:-1])
                landed.append((self.took[index] + period, index + 1, 0, writes))
            for edge, at, pos, writes in sorted(landed):
                await self.land(writes[-1], edge)
            for edge, at, pos, writes in sorted(landed):
                op, argument = script[at][pos]
                latch.finishes_to(at)
                await check_op(dut, checks, latch, label, at, op, argument, names[at][pos], len(writes) - 1)
        await self.until(case.frames, bound, "for the stream's end")
        await seen.stop(seam_host.INJECT_CLOCKS + seam_host.CORE_CLOCKS + 16)
        latch.finishes_to(case.frames)
        await check_registers(dut, checks, learner, latch.latched, label + ", at the end")
        inj = await b.read(source_bus.offset("inj_refusal"))
        checks.same(label + ": inj_refusal at the end", inj, 0)
        hold_records(test, label, seen.words, records, seen.unknown)
        checks.close()
        return learner, records

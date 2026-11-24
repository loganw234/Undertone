"""The host library's every call, written once, as procedures over the seam's operations.

A procedure is a generator: it yields the operations of `host.ops` and is sent
each one's result. It does no I/O and imports nothing that does, so the same
code drives the simulated kernel (through a coroutine driver) and XRT (through
a call driver): `host.drive` makes both from the list `PROCEDURES`.

THE RULE. A call refuses BEFORE ANY WRITE what it can know from its own inputs
(the blob, the table, the schedule, its numbers) and from the identity and
capability registers. What depends on a block's state it leaves to that block
and READS BACK BY NAME, from the block's refusal register, after each group of
writes; a code read is cleared (a write of 0) and raised. Before a call's first
write it reads the same registers, and one already latched is raised, "latched
before this call", with nothing written. So the library keeps no copy of any
block's state machine. Two exceptions: SWAP_SHAPE for a shadow (the core sees a
shadow's count of words, not its shape), and three things only the host sees,
each raised under the name of what it means: RUN_START (a start that changed
nothing), RUN_LENGTH (a run done with fewer records than asked and nothing
latched) and INJECT_OVERLAP (a run done before the library offered a record).

The library never retries, and never waits without a bound: `finish` polls at
most the number of times it is given, and past it raises Python's TimeoutError
(the lead's ruling, 2026-11-24): a deadline is the caller's, not a refusal of
an input, and the run may still be going.

WHAT IT CANNOT SEE, each a limit of docs/host/host.md: a block that takes a
write and does something else with it (only the comparison with the model sees
that); a refusal of a block it did not write in that call, until a later call
reads it; whether a write landed, other than through a register that says so.
"""
import struct

from spec import constants as C
from model.refusal import Refusal

from host import blob as B
from host.ops import Read, Write, WriteMany, Pause, Allocate, Fill, Fetch

WORD_BITS = C.BUS["word_bits"]
WORD_BYTES = WORD_BITS // 8
WORD_MASK = (1 << WORD_BITS) - 1
SLOT = C.MEMORY_SLOT_BYTES
PATTERN = 0xA5                    # every byte of a buffer before a start: a slot never written keeps it
GUARD = SLOT * 124                # 3,968 bytes before slot 0: non-zero, and slot 4 starts a page of 4,096
NAME_OF = dict((code, name) for name, code in C.REFUSAL_CODES.items())
KRN = C.REGISTER_BITS["krn_status"]
RUNNING, DONE, REFUSED = (1 << KRN["running"]), (1 << KRN["done"]), (1 << KRN["refused"])
# The four refusal registers, in the chain's order: a block's refusal ends a run, and the kernel's follows it.
CHAIN = (("source", "src_refusal"), ("injector", "inj_refusal"), ("core", "refusal"), ("kernel", "krn_refusal"))
CAPS = tuple(sorted((n for n in C.REGISTERS if n.startswith("cap_")), key=lambda n: C.REGISTERS[n][0]))
TRUTH = C.RECORDS["truth"]
SCORE = C.RECORDS["score"]
INDEX_LIMIT = 1 << 64

# The slot's reader, built from the definition's score record: each field little-endian, then the padding.
_CODES = {(64, "unsigned"): "Q", (64, "signed"): "q", (32, "unsigned"): "I", (32, "signed"): "i",
          (16, "unsigned"): "H", (16, "signed"): "h", (8, "unsigned"): "B", (8, "signed"): "b"}
for _name, _bits, _sign in SCORE:
    if (_bits, _sign) not in _CODES:
        raise ImportError("host/library.py reads fields of 8, 16, 32 and 64 bits; the score record's %s is %d %s"
                          % (_name, _bits, _sign))
RECORD_BYTES = sum(bits for _n, bits, _s in SCORE) // 8
if RECORD_BYTES > SLOT:
    raise ImportError("a score record of %d bytes does not fit a slot of %d" % (RECORD_BYTES, SLOT))
SLOT_FORMAT = struct.Struct("<" + "".join(_CODES[(bits, sign)] for _n, bits, sign in SCORE) + "%ds" % (SLOT - RECORD_BYTES))

PROCEDURES = ("open", "reset", "load", "write_shadow", "commit", "swap", "start", "step", "finish", "run",
              "records", "refusals", "raw_read", "raw_write")


def offset(name, word=0):
    return C.REGISTERS[name][0] + word * WORD_BYTES


def words_of(name, value):
    """A value as the writes that carry it into its row: the lowest word at the lowest offset."""
    first, _access, count = C.REGISTERS[name]
    if not 0 <= value < (1 << (WORD_BITS * count)):
        raise ValueError("%r does not fit %s's %d word(s)" % (value, name, count))
    return [(first + WORD_BYTES * i, (value >> (WORD_BITS * i)) & WORD_MASK) for i in range(count)]


def named(code, detail):
    """The refusal a register's code names. A code no name has is an image that does not speak this definition."""
    if code in NAME_OF:
        return Refusal(NAME_OF[code], detail)
    return Refusal("IMAGE_SPEC", "%s: the code %d, which no declared name has" % (detail, code))


def _is_int(v, lo, hi):
    return type(v) is int and lo <= v <= hi


def _refused_and_still(status):
    """krn_status says a refusal is latched and nothing runs: the kernel will do nothing more on its own."""
    return bool(status & REFUSED) and not status & RUNNING


def _field_range(bits, sign):
    return (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if sign == "signed" else (0, (1 << bits) - 1)


def check_record(kind, fields_declared, record):
    """RECORD_FIELD, as the model's `records.check` has it: exactly the declared fields, each an int that fits."""
    if not isinstance(record, dict) or set(record) != {f[0] for f in fields_declared}:
        raise Refusal("RECORD_FIELD", "a %s record has exactly the fields %s" % (kind, ", ".join(f[0] for f in fields_declared)))
    for name, bits, sign in fields_declared:
        lo, hi = _field_range(bits, sign)
        if not _is_int(record[name], lo, hi):
            raise Refusal("RECORD_FIELD", "%s.%s = %r does not fit %d %s bits" % (kind, name, record[name], bits, sign))


def pulse_length(pulse_id):
    names = [n for n in sorted(C.PULSE_IDS) if C.PULSE_IDS[n] == pulse_id]
    if type(pulse_id) is not int or len(names) != 1:
        raise Refusal("PULSE_UNKNOWN", "pulse_id %r names no declared pulse" % (pulse_id,))
    return len(C.PULSES[names[0]])


def check_schedule(schedule, frames):
    """The schedule, checked in `model.inject.schedule`'s order by this library's own code; a list of copies."""
    if not isinstance(schedule, (list, tuple)):
        raise Refusal("RECORD_FIELD", "a schedule is a list of truth records")
    out, free_from = [], 0
    for record in schedule:
        check_record("truth", TRUTH, record)
        if record["amplitude_den"] == 0:
            raise Refusal("RECORD_FIELD", "truth.amplitude_den = 0")
        last = record["index"] + pulse_length(record["pulse_id"])
        if record["index"] < free_from:
            raise Refusal("INJECT_OVERLAP", "the record at %d starts before %d, where the one before it ends"
                          % (record["index"], free_from))
        if last > frames:
            raise Refusal("INJECT_PAST_END", "the record at %d ends at %d, past a run of %d frames" % (record["index"], last, frames))
        out.append(dict(record))
        free_from = last
    return out


def check_table(table, most):
    """NOISE_TABLE: not the form the model's tables have; NOISE_RANGE: longer than the build holds."""
    one = 1 << 63
    if not isinstance(table, (list, tuple)) or not table or any(type(v) is not int for v in table):
        raise Refusal("NOISE_TABLE", "a table is a non-empty list of ints")
    if table[-1] != one or any(not 0 <= v < one for v in table[:-1]) or any(a > b for a, b in zip(table, table[1:])):
        raise Refusal("NOISE_TABLE", "a table's entries rise, each below 2^63 but the last, which is 2^63: "
                      "the library hands over every entry but the last")
    if len(table) - 1 > most:
        raise Refusal("NOISE_RANGE", "a table whose largest magnitude is %d; the build holds %d" % (len(table) - 1, most))


def truth_pairs(record):
    """One truth record as its five writes: the index's two words, the pulse, the numerator as a word, the
    denominator last, whose write offers the record."""
    return (words_of("inj_truth_index", record["index"])
            + [(offset("inj_truth_pulse_id"), record["pulse_id"]),
               (offset("inj_truth_amplitude_num"), record["amplitude_num"] & WORD_MASK),
               (offset("inj_truth_amplitude_den"), record["amplitude_den"])])


def parse_slot(data, n):
    """Slot n of a run as a score record, in the model's own form; RECORD_SLOT or RESERVED_BITS otherwise."""
    *values, pad = SLOT_FORMAT.unpack(data)
    if pad != bytes(len(pad)):
        raise Refusal("RECORD_SLOT", "slot %d's bytes past its record are not zero (%s): nothing wrote a record there"
                      % (n, pad.hex()))
    record = dict((field[0], v) for field, v in zip(SCORE, values))
    if record["flags"] & C.FLAGS_RESERVED_MASK:
        raise Refusal("RESERVED_BITS", "slot %d: flags 0x%02X" % (n, record["flags"]))
    return record


class RunState:
    """What the library knows of the run it started: its buffer, its schedule, and how far it fed it."""

    def __init__(self, buffer, frames, schedule, ahead):
        self.buffer, self.frames, self.schedule, self.ahead = buffer, frames, schedule, ahead
        self.sent = 0                 # truth records written
        self.before = 0               # of those, before the start
        self.least_slack = None       # the least (index - next_index) when a record was written while it ran
        self.records = None           # krn_records, read at the end
        self.peak = None


class Library:
    """The procedures. One object holds what the library knows: the identity it read, the shape it loaded,
    the run it started. The drivers in `host.drive` run its procedures."""

    pattern = PATTERN
    guard = GUARD

    def __init__(self):
        self.identity = None
        self.shape = None
        self.run_state = None

    # -------------------------------------------------------------- pieces every call uses

    def _value(self, name):
        value = 0
        for i in range(C.REGISTERS[name][2]):
            w = yield Read(offset(name, i))
            value |= w << (WORD_BITS * i)
        return value

    def _latched(self, registers, what):
        """Raise a refusal already latched in any of these registers, before anything is written.
        Returns how many reads it made."""
        made = 0
        for block, register in CHAIN:
            if register in registers:
                code = yield Read(offset(register))
                made += 1
                if code:
                    raise named(code, "%s: the %s's refusal was latched before this call, and nothing was written"
                                % (what, block))
        return made

    def _after(self, register, what):
        """Read one block's refusal after a group of writes; a code is cleared and raised."""
        code = yield Read(offset(register))
        if code:
            yield Write(offset(register), 0)
            block = [b for b, r in CHAIN if r == register][0]
            raise named(code, "the %s refused %s" % (block, what))
        return code

    def _ident(self):
        if self.identity is None:
            yield from self.open()
        return self.identity

    def _checked(self, blob):
        """The blob read and held to the definition, then to the build: nothing written."""
        ident = yield from self._ident()
        config = B.read(blob)
        self._against(config, ident)
        return config

    # The two places a control of the tests replaces: what the build is held to, and the words written.
    def _against(self, config, ident):
        B.against(config, ident)

    def _words(self, config):
        return [w & WORD_MASK for w in B.words(config)]

    # -------------------------------------------------------------- the calls

    def open(self):
        """Read the identity block and every capability register; refuse an image of another definition.
        Writes nothing."""
        magic = yield from self._value("id")
        version = yield from self._value("spec_version")
        spec_hash = yield from self._value("spec_hash")
        caps = {}
        for name in CAPS:
            caps[name] = yield from self._value(name)
        wrong = []
        if magic != C.BUS["magic"]:
            wrong.append("id 0x%08X, not 0x%08X" % (magic, C.BUS["magic"]))
        if version != C.SPEC_VERSION:
            wrong.append("spec_version %d, not %d" % (version, C.SPEC_VERSION))
        if spec_hash != int(C.SPEC_SHA256, 16):
            wrong.append("spec_hash %064x, not %s" % (spec_hash, C.SPEC_SHA256))
        if caps["cap_coeff_bits"] != C.COEFF_BITS:
            wrong.append("cap_coeff_bits %d, not %d" % (caps["cap_coeff_bits"], C.COEFF_BITS))
        if wrong:
            raise Refusal("IMAGE_SPEC", "; ".join(wrong))
        found = [name for name, p in sorted(C.PROFILES.items())
                 if (p["sample_bits"], p["channels"]) == (caps["cap_sample_bits"], caps["cap_channels"])]
        if len(found) != 1:
            raise Refusal("PROFILE_UNKNOWN", "the build's samples are %d bits on %d channel(s), which no profile is"
                          % (caps["cap_sample_bits"], caps["cap_channels"]))
        self.identity = {"id": magic, "spec_version": version, "spec_hash": spec_hash, "caps": caps,
                         "profile": found[0]}
        return self.identity

    def reset(self):
        """krn_reset: the three blocks and the run back to their reset state. The library forgets its shape."""
        yield Write(offset("krn_reset"), 1)
        codes = []
        for block, register in CHAIN:
            code = yield Read(offset(register))
            codes.append((block, register, code))
        for block, register, code in codes:
            if code:
                yield Write(offset(register), 0)
                raise named(code, "the %s refused the reset" % block)
        self.shape, self.run_state = None, None

    def load(self, blob, epoch=0):
        """The core configured from a blob and started at an epoch. Returns the shape and the count of words."""
        config = yield from self._checked(blob)
        if not _is_int(epoch, 0, (1 << 32) - 1):
            raise Refusal("SWAP_EPOCH", "a start epoch of %r" % (epoch,))
        words = self._words(config)
        yield from self._latched(("refusal",), "load")
        pairs = [(offset(name), value) for name, value in B.shape_scalars(config)]
        pairs += [(offset("shape_masks", k), m) for k, m in enumerate(B.masks(config))]
        pairs.append((offset("configure"), len(words)))
        yield WriteMany(tuple(pairs))
        yield from self._after("refusal", "the shape")
        yield WriteMany(tuple([(offset("shadow_data"), w) for w in words] + [(offset("start"), epoch)]))
        yield from self._after("refusal", "the weights or the start")
        self.shape = B.shape(config)
        return {"shape": self.shape, "words": len(words)}

    def _shadow_config(self, blob):
        config = yield from self._checked(blob)
        if self.shape is None:
            raise Refusal("SWAP_SHAPE", "no shape was loaded through this library since its last reset")
        if B.shape(config) != self.shape:
            raise Refusal("SWAP_SHAPE", "the blob's shape %r is not the running shape %r" % (B.shape(config), self.shape))
        return config

    def _shadow_pairs(self, config):
        words = self._words(config)
        return [(offset("shadow_begin"), len(words))] + [(offset("shadow_data"), w) for w in words]

    @staticmethod
    def _at(at):
        if not _is_int(at, 0, INDEX_LIMIT - 1):
            raise Refusal("SWAP_INDEX", "a commit at %r" % (at,))
        return words_of("commit_at", at)

    def write_shadow(self, blob):
        """A whole weight set into the shadow."""
        config = yield from self._shadow_config(blob)
        yield from self._latched(("refusal",), "write_shadow")
        yield WriteMany(tuple(self._shadow_pairs(config)))
        yield from self._after("refusal", "the shadow's words")

    def commit(self, at):
        """The swap scheduled at output index `at`: the commit_at's lower word, then its upper, the commit."""
        pairs = self._at(at)
        yield from self._latched(("refusal",), "commit")
        yield WriteMany(tuple(pairs))
        yield from self._after("refusal", "the commit at %d" % at)

    def swap(self, blob, at, batch=True):
        """write_shadow and commit. Between the first shadow write and the read that says the commit was taken
        the library makes exactly the shadow's writes, ONE READ of the core's refusal (after the shadow's last
        word, so that no commit follows a refused shadow) and the commit's writes; nothing else. Returns
        next_index read just before and just after those, and the positions, among this call's operations
        counted from 0, of the first shadow write and the accepting read. `batch=False` writes each word as a
        Write of its own, so that each can be timed."""
        config = yield from self._shadow_config(blob)
        commit = self._at(at)
        pairs = self._shadow_pairs(config)
        n = yield from self._latched(("refusal",), "swap")
        before = 0
        for i in range(C.REGISTERS["next_index"][2]):
            w = yield Read(offset("next_index", i))
            before |= w << (WORD_BITS * i)
            n += 1
        first_shadow = n
        if batch:
            yield WriteMany(tuple(pairs))
            n += 1
        else:
            for where, word in pairs:
                yield Write(where, word)
                n += 1
        code = yield Read(offset("refusal"))
        n += 1
        if code:
            yield Write(offset("refusal"), 0)
            raise named(code, "the core refused the shadow's words")
        if batch:
            yield WriteMany(tuple(commit))
            n += 1
        else:
            for where, word in commit:
                yield Write(where, word)
                n += 1
        accepting = n
        code = yield Read(offset("refusal"))
        n += 1
        if code:
            yield Write(offset("refusal"), 0)
            raise named(code, "the core refused the commit at %d" % at)
        after = 0
        for i in range(C.REGISTERS["next_index"][2]):
            w = yield Read(offset("next_index", i))
            after |= w << (WORD_BITS * i)
        return {"next_index_before": before, "next_index_after": after, "first_shadow_op": first_shadow,
                "accepting_op": accepting, "at": at}

    def start(self, seed, table, frames, schedule, ahead=None):
        """Everything a run needs, written, and the kernel started. Returns the run's buffer."""
        ident = yield from self._ident()
        caps = ident["caps"]
        if not _is_int(seed, 0, INDEX_LIMIT - 1):
            raise Refusal("SEED_RANGE", "seed %r" % (seed,))
        check_table(table, caps["cap_noise_table"])
        if not _is_int(frames, 1, INDEX_LIMIT - 1):
            raise Refusal("STREAM_LENGTH", "a run of %r frames" % (frames,))
        schedule = check_schedule(schedule, frames)
        ahead = caps["cap_inject_pending"] if ahead is None else ahead
        if not _is_int(ahead, 1, caps["cap_inject_pending"]):
            raise Refusal("INJECT_PENDING", "ahead %r; the build's store holds %d" % (ahead, caps["cap_inject_pending"]))
        # A refusal already latched is raised before anything below the seam changes: before the buffer is
        # allocated or filled, and before the last run's state is replaced, whose records stay readable.
        yield from self._latched(tuple(r for _b, r in CHAIN), "start")
        buffer = yield Allocate(self.guard + frames * SLOT)
        yield Fill(buffer, 0, bytes([self.pattern]) * (self.guard + frames * SLOT))
        state = RunState(buffer, frames, schedule, ahead)
        self.run_state = state
        pairs = self._table_pairs(table) + words_of("src_seed", seed)
        yield WriteMany(tuple(pairs))
        yield from self._after("src_refusal", "the table or the seed")
        first = schedule[:ahead]
        if first:
            pairs = []
            for record in first:
                pairs += truth_pairs(record)
            yield WriteMany(tuple(pairs))
            state.sent = state.before = len(first)
            yield from self._after("inj_refusal", "the truth records written before the start")
        yield WriteMany(tuple(words_of("krn_buffer", buffer.address + self.guard) + words_of("krn_size", frames * SLOT)
                              + words_of("krn_frames", frames)))
        yield from self._after("krn_refusal", "the run's arguments")
        yield Write(offset("krn_start"), 1)
        status = yield Read(offset("krn_status"))
        if _refused_and_still(status):
            # Raises the start's refusal by its name, each cleared. The kernel wrote nothing of this run: its
            # krn_records still holds the last run's count (a refused start clears it not), so that count is
            # named in the detail as the last run's, and this run's records are none.
            yield from self._conclude(state, refused_start=True)
            raise Refusal("RUN_START", "observed: after the start write krn_status says refused (0x%X) and the "
                          "run's account says nothing else" % status)
        if not status & (RUNNING | DONE | REFUSED):
            raise Refusal("RUN_START", "after the start write the kernel says none of running, done or refused "
                          "(krn_status 0x%X): the start reached nothing that answered" % status)
        return buffer

    def _table_pairs(self, table):
        """The writes that hand a table over: its length, then every entry but the last, two words each."""
        pairs = [(offset("src_table_length"), len(table) - 1)]
        for entry in table[:-1]:
            pairs += words_of("src_table_entry", entry)
        return pairs

    def step(self):
        """One round of a run: the kernel's status, and as many truth records as bring the store to `ahead`.
        Returns (krn_status, records written so far). A kernel that says refused and is not running will do
        nothing more: the round ends the run there, and raises its refusal by name (`_conclude`)."""
        state = self.run_state
        status = yield Read(offset("krn_status"))
        if _refused_and_still(status):
            yield from self._conclude(state)
            return status, state.sent
        if state.sent < len(state.schedule) and not status & (DONE | REFUSED):
            refused = yield Read(offset("inj_refusal"))
            pending = yield Read(offset("inj_pending"))
            room = max(0, state.ahead - pending)
            batch = state.schedule[state.sent:state.sent + room]
            if batch and not refused:
                at = yield from self._value("next_index")
                slack = batch[0]["index"] - at
                state.least_slack = slack if state.least_slack is None else min(state.least_slack, slack)
                pairs = []
                for record in batch:
                    pairs += truth_pairs(record)
                yield WriteMany(tuple(pairs))
                state.sent += len(batch)
        return status, state.sent

    def finish(self, polls):
        """Step and pause until the kernel says done, or says refused while not running, at most `polls`
        rounds; then read every refusal.

        Returns the run's report; raises the first refusal in the chain's order, with all in its detail; raises
        TimeoutError past `polls`, writing nothing more. A refusal latched while the kernel still runs (its
        queue full, a memory error) ends the wait at done, which the kernel raises once its source has ended."""
        state = self.run_state
        if not _is_int(polls, 1, 1 << 62):
            raise ValueError("polls is a count of at least 1, not %r" % (polls,))
        for _ in range(polls):
            status, _sent = yield from self.step()
            if status & DONE or _refused_and_still(status):
                break
            yield Pause()
        else:
            status = yield Read(offset("krn_status"))
            records = yield from self._value("krn_records")
            raise TimeoutError("after %d polls the kernel has not said done: krn_status 0x%X, krn_records %d, of %d "
                               "frames asked for; the run may still be going" % (polls, status, records, state.frames))
        return (yield from self._conclude(state))

    def _conclude(self, state, refused_start=False):
        """The run's account: every refusal register in the chain's order, krn_records and krn_queue_peak. The
        first refusal latched is raised by its name, every one in its detail, each cleared; else the report.
        After a refused start the kernel wrote nothing of this run, and krn_records is its LAST run's count: the
        run's records are taken as none, and the detail names that count as the last run's."""
        codes = []
        for block, register in CHAIN:
            code = yield Read(offset(register))
            codes.append((block, register, code))
        counted = yield from self._value("krn_records")
        state.records = 0 if refused_start else counted
        state.peak = yield Read(offset("krn_queue_peak"))
        latched = [(b, r, c) for b, r, c in codes if c]
        report = {"frames": state.frames, "records": state.records, "queue_peak": state.peak,
                  "truth_before_start": state.before, "truth_while_running": state.sent - state.before,
                  "least_slack": state.least_slack}
        if latched:
            for _b, register, _c in latched:
                yield Write(offset(register), 0)
            said = "; ".join("%s %s" % (b, NAME_OF.get(c, "code %d" % c)) for b, _r, c in codes if c)
            block, _r, code = latched[0]
            if refused_start:
                raise named(code, "the start was refused: %s; no record of this run was written (krn_records reads "
                            "%d, the last run's count, which a refused start does not clear)" % (said, counted))
            raise named(code, "the run ended refused: %s; %d of %d records written; truth written %d before the "
                        "start and %d while it ran, the least slack %s" % (said, state.records, state.frames,
                                                                            state.before, state.sent - state.before,
                                                                            state.least_slack))
        if state.records != state.frames:
            raise Refusal("RUN_LENGTH", "observed: the kernel says done with %d of %d records and nothing latched"
                          % (state.records, state.frames))
        if state.sent != len(state.schedule):
            raise Refusal("INJECT_OVERLAP", "observed: the run ended with %d of %d truth records offered; the stream "
                          "passed the others before the library wrote them" % (state.sent, len(state.schedule)))
        return report

    def run(self, seed, table, frames, schedule, polls, ahead=None):
        """start, then finish."""
        yield from self.start(seed, table, frames, schedule, ahead)
        return (yield from self.finish(polls))

    def records(self, first=0, count=None):
        """The last run's score records, read from its buffer: `count` slots from `first`, by default every
        record the kernel said it wrote. A slot nothing wrote is refused, RECORD_SLOT."""
        state = self.run_state
        if state is None or state.records is None:
            raise ValueError("no run has finished through this library")
        if count is None and state.records > state.frames:
            raise Refusal("RUN_LENGTH", "the kernel says it wrote %d records of a run of %d: past the buffer's slots, "
                          "and none is read" % (state.records, state.frames))
        count = state.records - first if count is None else count
        if not _is_int(first, 0, INDEX_LIMIT - 1) or not _is_int(count, 0, INDEX_LIMIT - 1) or first + count > state.frames:
            raise ValueError("slots %r to %r of a run of %d" % (first, count, state.frames))
        if count == 0:
            return []
        data = yield Fetch(state.buffer, self.guard + first * SLOT, count * SLOT)
        if len(data) != count * SLOT:
            raise ValueError("the backend handed back %d bytes for %d" % (len(data), count * SLOT))
        return [parse_slot(data[i * SLOT:(i + 1) * SLOT], first + i) for i in range(count)]

    def refusals(self):
        """Each block's refusal register, by name or None. Clears nothing."""
        out = {}
        for block, register in CHAIN:
            code = yield Read(offset(register))
            out[block] = None if code == 0 else NAME_OF.get(code, "code %d" % code)
        return out

    def raw_read(self, where):
        """One read at a byte offset. For tests. Checks nothing."""
        return (yield Read(where))

    def raw_write(self, where, word):
        """One write at a byte offset. For tests, and the card day's raw shape. Checks nothing, reads nothing back."""
        yield Write(where, word)

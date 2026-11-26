"""The first size's stand-in for the card on LRN-C's runs: the kernel's registers over the model's learner, run as the
host writes.

`LearnerCard(profile, blob, sigma, schedule, shadow_blobs, stride, ...)` is `host.fake.Registers` with hooks, as
E0C's ModelKernel is (`hw/e0c/kernel_model.py`, whose helpers it imports). What it does:
  - IT COLLECTS what the host library writes: the noise table, the seed, the core's words and its start epoch,
    and each truth record (the denominator's write offers it), and holds each against what it was handed (the
    blob, the sigma's table, the case's schedule, in order): AssertionError otherwise, its own check and not a
    refusal. It is handed the whole schedule because the model's injector and learner take the whole truth
    before frame 0 (`model.inject.inject`, `model.learner.Learner`).
  - ITS CLOCK: at krn_start it makes `model.inject.inject` over `model.source.Noise` and the learner
    (`learner_class`, `model.learner.Learner` by default) as `model.run.learning` does, and each read of
    krn_status then steps the learner `stride` frames, the loop `model.run._learning_run` runs. next_index reads
    the learner's own. A frame whose truth record the library has not yet written is an AssertionError: the
    stand-in never says a record came late. inj_pending reads the records written and not yet reached.
  - THE LEARNER'S REGISTERS OVER THE MODEL'S LEARNER, at the next index the write lands at. lrn_update_at's upper
    word is `update(u)`; commit_at's upper word `commit(at)`; shadow_begin and its words `write_shadow(blob)`, the
    words held against `shadow_blobs`. A refusal is latched where docs/rtl/learn.md section 3 latches it: an
    update's names and UPDATE_UNFINISHED in lrn_refusal (the core's `refusal` reads 0 for a held-back write, as
    KRNL-L's design has it, the lead's message of 2026-11-26 about 04:05), a commit's or a shadow write's own in
    the core's `refusal`; a held-back shadow write latches once for its begin and once a word; an unmade update
    latches QUANTISE_INPUT at its finish. lrn_status, the counts (a lower word's read holds the upper word),
    lrn_update_at (u while unfinished) and the caps read the learner as the fabric's registers would.
  - At done the run's buffer holds the model's records, one slot a frame, as ModelKernel's does.
So THE STAND-IN'S RECORDS ARE THE MODEL'S RUN WITH EACH OPERATION AT THE INDEX WHERE THE HOST'S WRITE LANDED IN IT,
and the judge compares them with the canonical run: the windows are exercised, not assumed.

IT IS NOT A KERNEL and models no block. What it does not model, each a limit of docs/host/lrn-c.md:
  - no clock but its count of krn_status reads; a write lands at once and in order, nothing posted;
  - no port shared between the host and the learner, so the guard G is never tested here, and the update is
    finished exactly at u + F;
  - the fabric's own first and last refusals of an update, CORE_STOPPED and WEIGHT_COUNT, are not made;
  - truth is never late; XRT's syncs are not modelled (the buffer is a bytearray); the box's Python and its
    collector, and the card's frame rate, vary nothing here;
  - a write the kernel itself refuses (its strobes) never reaches the learner on the card; here no write is refused.

Desktop only: it imports the model.
"""
import contextlib
import io
import json
import os

from spec import constants as C
from model import inject, source
from model import learner as ML
from model.refusal import Refusal

from host import blob as B
from host import fake, library, run_case

from hw.e0c import run_piece
from hw.e0c.kernel_model import WORD_MASK, _at, _signed32

WORD_BITS = C.BUS["word_bits"]
STATUS_BITS = C.REGISTER_BITS["lrn_status"]
KRN = C.REGISTER_BITS["krn_status"]
COUNTS_64 = tuple(n for n in library.LRN_COUNTS if C.REGISTERS[n][2] == 2)
COUNTS_32 = tuple(n for n in library.LRN_COUNTS if C.REGISTERS[n][2] == 1)


class LearnerCard(fake.Registers):
    """See the module. `memory_group` and `close` are what host.run_case asks of a backend besides `do`."""

    def __init__(self, profile, blob, sigma, schedule, shadow_blobs=(), stride=64, count_bits=C.LEARN_COUNT_BITS,
                 update_frames=C.LEARN_UPDATE_FRAMES, learner_class=ML.Learner, **caps):
        words = fake.identity_words(profile, **caps)
        words.update(fake.learner_words(lrn_cap_count_bits=count_bits, lrn_cap_update_frames=update_frames))
        super().__init__(words)
        self.profile, self.blob, self.sigma = profile, blob, tuple(sigma)
        self.schedule = [dict(r) for r in schedule]
        self.shadow_by_words = dict((tuple(w & WORD_MASK for w in B.words(B.read(b))), b) for b in shadow_blobs)
        self.stride, self.count_bits, self.update_frames = stride, count_bits, update_frames
        self.learner_class = learner_class
        self.memory_group = 0
        self.closed = False
        self.runs = 0
        self._clear()
        on_write = {
            _at("src_table_length"): self._table_length,
            _at("src_table_entry", 1): self._table_entry,
            _at("inj_truth_amplitude_den"): self._truth,
            _at("configure"): self._configure,
            _at("shadow_begin"): self._shadow_begin,
            _at("shadow_data"): self._shadow_data,
            _at("start"): self._core_start,
            _at("commit_at", 1): self._commit,
            _at("lrn_update_at", 1): self._update,
            _at("lrn_refusal"): self._lrn_refusal_write,
            _at("krn_start"): self._start,
            _at("krn_reset"): self._reset,
        }
        self.on_write.update(on_write)
        self.on_read.update({
            _at("krn_status"): self._status,
            _at("next_index", 0): lambda b: self._next() & WORD_MASK,
            _at("next_index", 1): lambda b: self._next() >> WORD_BITS,
            _at("inj_pending"): self._pending,
            _at("lrn_status"): self._lrn_status,
            _at("lrn_refusal"): lambda b: C.REFUSAL_CODES[self.latch[0]] if self.latch else 0,
            _at("lrn_update_at", 0): lambda b: self._update_at() & WORD_MASK,
            _at("lrn_update_at", 1): lambda b: self._update_at() >> WORD_BITS,
        })
        for name in COUNTS_32:
            self.on_read[_at(name)] = (lambda name: lambda b: self._count(name) & WORD_MASK)(name)
        for name in COUNTS_64:
            self.on_read[_at(name, 0)] = (lambda name: lambda b: self._count_low(name))(name)
            self.on_read[_at(name, 1)] = (lambda name: lambda b: self.hold.get(name, 0))(name)

    def _clear(self):
        self.table, self.table_length, self.truth, self.core_words = [], None, [], []
        self.phase, self.stream_words, self.stream_count = None, [], 0
        self.learner, self.stream, self.frames, self.out = None, None, 0, bytearray()
        self.latch, self.hold, self.named_u, self.seen, self.due = [], {}, None, 0, 0
        self.epoch, self.done, self.started = 0, False, False
        self.landed = []           # every learner operation: (next index, kind, argument, the name latched or None)

    # ----------------------------------------------------------------- what the library writes
    def _store(self, where, word):
        self.words[where] = word

    def _table_length(self, b, word):
        self.table, self.table_length = [], word

    def _table_entry(self, b, word):
        self._store(_at("src_table_entry", 1), word)
        self.table.append(self.words.get(_at("src_table_entry"), 0) | (word << 32))

    def _truth(self, b, word):
        record = {"index": fake.value(self, "inj_truth_index"),
                  "pulse_id": self.words.get(_at("inj_truth_pulse_id"), 0),
                  "amplitude_num": _signed32(self.words.get(_at("inj_truth_amplitude_num"), 0)),
                  "amplitude_den": word}
        k = len(self.truth)
        if k >= len(self.schedule) or record != self.schedule[k]:
            raise AssertionError("LearnerCard: truth record %d written is %r, not the case's %r"
                                 % (k, record, self.schedule[k] if k < len(self.schedule) else None))
        self.truth.append(record)

    def _configure(self, b, word):
        self._store(_at("configure"), word)
        self.phase, self.core_words = "load", []

    def _shadow_begin(self, b, word):
        self.phase, self.stream_words, self.stream_count = "shadow", [], word
        if word == 0:
            self._shadow_done()

    def _shadow_data(self, b, word):
        if self.phase == "load":
            self.core_words.append(word)
        elif self.phase == "shadow":
            self.stream_words.append(word)
            if len(self.stream_words) == self.stream_count:
                self._shadow_done()
        else:
            raise AssertionError("LearnerCard: a shadow word with no configure or shadow_begin before it")

    def _core_start(self, b, word):
        want = [w & WORD_MASK for w in B.words(B.read(self.blob))]
        if self.core_words != want:
            raise AssertionError("LearnerCard: the core's words written are not the blob's it was handed")
        self.epoch, self.phase = word, None

    def _shadow_done(self):
        self.phase = None
        blob = self.shadow_by_words.get(tuple(self.stream_words))
        if blob is None:
            raise AssertionError("LearnerCard: a shadow of %d words that is no blob it was handed" % len(self.stream_words))
        self._operation("write_shadow", blob, 1 + self.stream_count)

    def _commit(self, b, word):
        self._store(_at("commit_at", 1), word)
        self._operation("commit", fake.value(self, "commit_at"))

    def _update(self, b, word):
        self._store(_at("lrn_update_at", 1), word)
        self._operation("update", fake.value(self, "lrn_update_at"))

    def _operation(self, kind, argument, held=1):
        """One of the host's operations on the model's learner at its next index now; its refusal latched."""
        if self.learner is None:
            raise AssertionError("LearnerCard: a learner operation (%s) before krn_start" % kind)
        n, name = self.learner.next_index, None
        try:
            {"update": self.learner.update, "commit": self.learner.commit,
             "write_shadow": self.learner.write_shadow}[kind](argument)
            if kind == "update":
                self.named_u = argument
        except Refusal as e:
            name = e.name
            if kind == "update" or name == "UPDATE_UNFINISHED":
                self.latch.extend([name] * (held if kind == "write_shadow" else 1))
            elif not self.words.get(_at("refusal"), 0):
                self.words[_at("refusal")] = C.REFUSAL_CODES[name]
        self.landed.append((n, kind, argument if kind != "write_shadow" else "blob", name))
        self._finishes()

    def _lrn_refusal_write(self, b, word):
        if word == 0:
            self.latch = []
        else:
            self.latch.append("REGISTER_ACCESS")

    def _reset(self, b, word):
        self._clear()
        for name in ("src_refusal", "inj_refusal", "refusal", "krn_refusal"):
            self.words[_at(name)] = 0
        self.words.update(fake.value_words("krn_records", 0))

    # ----------------------------------------------------------------- the run
    def _start(self, b, word):
        self.frames, seed = fake.value(self, "krn_frames"), fake.value(self, "src_seed")
        noise = source.Noise(self.profile, seed, self.sigma[0], self.sigma[1], self.frames)
        if self.table_length != len(noise.table) - 1 or self.table != list(noise.table[:-1]):
            raise AssertionError("LearnerCard: the table written is not the sigma's")
        injected, truth = inject.inject(self.profile, noise, self.schedule, self.frames)
        self.learner = self.learner_class(self.blob, truth, self.update_frames, self.count_bits, self.epoch)
        self.stream = iter(injected)
        self.started, self.done, self.out = True, False, bytearray()
        self.runs += 1

    def _next(self):
        return 0 if self.learner is None else self.learner.next_index

    def _finishes(self):
        updates = self.learner.updates
        while self.seen < len(updates) and updates[self.seen]["outcome"] is not None:
            if updates[self.seen]["outcome"] == "unmade":
                self.latch.append("QUANTISE_INPUT")
            self.seen += 1

    def advance(self, count):
        """Step the model's learner `count` frames, or to the run's end; at the end the buffer holds the records."""
        pad = bytes(library.SLOT - library.RECORD_BYTES)
        for _ in range(count):
            n = self.learner.next_index
            if n >= self.frames:
                break
            while self.due < len(self.schedule) and self.schedule[self.due]["index"] <= n:
                self.due += 1
            if len(self.truth) < self.due:
                raise AssertionError("LearnerCard: the stream reached frame %d before the library wrote the truth "
                                     "record at %d" % (n, self.schedule[len(self.truth)]["index"]))
            r = self.learner.step(next(self.stream))
            self.out += library.SLOT_FORMAT.pack(*[r[name] for name, _b, _s in library.SCORE], pad)
            self._finishes()
        if self.learner.next_index >= self.frames and not self.done:
            base = fake.value(self, "krn_buffer")
            handle = [h for h, at in self.addresses.items() if at <= base < at + len(self.memory[h])][0]
            at = base - self.addresses[handle]
            self.memory[handle][at:at + len(self.out)] = self.out
            self.words.update(fake.value_words("krn_records", self.frames))
            self.done = True

    def _status(self, b):
        if not self.started:
            return 0
        if not self.done:
            self.advance(self.stride)
        return (1 << KRN["done"]) if self.done else (1 << KRN["running"])

    def _pending(self, b):
        n = self._next()
        return sum(1 for r in self.truth if r["index"] >= n)

    # ----------------------------------------------------------------- the learner's reads
    def _lrn_status(self, b):
        s = self.learner.status() if self.learner is not None else dict.fromkeys(ML.STATUS_BITS, 0)
        bits = dict(s, refused=int(bool(self.latch)), refused_again=int(len(self.latch) > 1))
        return sum(v << STATUS_BITS[k] for k, v in bits.items())

    def _update_at(self):
        if self.learner is None:
            return 0
        s = self.learner.status()
        return self.named_u if (s["named"] or s["running"]) else 0

    def _count(self, name):
        return 0 if self.learner is None else self.learner.counters()[name]

    def _count_low(self, name):
        v = self._count(name)
        self.hold[name] = v >> WORD_BITS
        return v & WORD_MASK

    def close(self):
        self.closed = True


# --------------------------------------------------------------------- one run of a case through host.run_case

def read_case(case_dir):
    """A case folder's case.json, schedule and blobs: (info, schedule, {name: bytes})."""
    with open(os.path.join(case_dir, "case.json"), encoding="utf-8") as f:
        info = json.load(f)
    with open(os.path.join(case_dir, "schedule.json"), encoding="utf-8") as f:
        schedule = json.load(f)
    blobs = {}
    for name in sorted(os.listdir(case_dir)):
        if name.endswith(".blob"):
            with open(os.path.join(case_dir, name), "rb") as f:
                blobs[name] = f.read()
    return info, schedule, blobs


def argv_for(cases_dir, case, out, polls=1000000, script=None):
    """host.run_case's arguments for one run of a case, as the box gives them (hw/lrnc/box_lrnc.sh)."""
    case_dir = os.path.join(cases_dir, case)
    info, _s, _b = read_case(case_dir)
    return ["--xclbin", "stand-in", "--shim", "stand-in", "--blob", os.path.join(case_dir, info["blob"]),
            "--table", os.path.join(cases_dir, "table.json"), "--seed", str(info["seed"]),
            "--frames", str(info["frames"]), "--schedule", os.path.join(case_dir, "schedule.json"),
            "--learn", script or os.path.join(case_dir, "script.json"), "--count-bits", str(info["count_bits"]),
            "--update-frames", str(info["update_frames"]), "--epoch", str(info["epoch"]), "--out", out,
            "--polls", str(polls)]


def run(cases_dir, case, out, stride=37, learner_class=ML.Learner, polls=1000000, script=None, argv=None, **caps):
    """One run of a case through hw/e0c/run_piece.py and host.run_case, the stand-in in place of XRT's backend.
    Writes `out` (records.bin, report.json, trace.json) and `out`.log, the run's stdout, as the box does.
    Returns (run_case's exit code, the stand-in)."""
    info, schedule, blobs = read_case(os.path.join(cases_dir, case))
    card = LearnerCard(info["profile"], blobs[info["blob"]], info["sigma"], schedule, shadow_blobs=blobs.values(),
                       stride=stride, count_bits=info["count_bits"], update_frames=info["update_frames"],
                       learner_class=learner_class, **caps)
    kept = run_case.Backend
    run_case.Backend = lambda *a, **kw: card
    said = io.StringIO()
    try:
        with contextlib.redirect_stdout(said):
            code = run_piece.main(argv if argv is not None else argv_for(cases_dir, case, out, polls, script))
    finally:
        run_case.Backend = kept
    with open(out.rstrip("/\\") + ".log", "w", encoding="utf-8", newline="\n") as f:
        f.write(said.getvalue())
    return code, card

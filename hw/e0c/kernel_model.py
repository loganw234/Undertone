"""The first size's stand-in for the card: a backend whose kernel writes the model's own run of what it was handed.

`ModelKernel(profile, blob, sigma)` is `host.fake.Registers` with hooks. It collects what the host library writes:
the noise table's entries, the seed's two words, each truth record's five words (the denominator's write offers
it), the shape's scalars and the shadow's words. At the write of krn_start it holds the words written for the core
against the words of the blob it was handed (`host.blob.words`), the table against `model.source.Noise`'s for the
sigma it was handed, and then puts into the run's buffer, at krn_buffer, one slot for each of krn_frames frames:
the score records of `model.run.scores` on `model.source.Noise(profile, seed written, sigma, frames)` with the
truth records written. krn_status then says running for `polls_running` reads, and done after; krn_records is the
frame count. A truth record written after krn_start is refused here (the stand-in runs the model once, at the
start): a test that feeds while the run goes is the library's own suite's, not this one's.

It is NOT a kernel and models no block: it holds what E0C's scripts and the host library do with a buffer the
model filled, and nothing about what the fabric does with the writes. That is bit identity's other parts' (the
benches in simulation, the card day). A blob that is not the one written, or a table that is not the sigma's, is
raised as AssertionError: the stand-in's own check, not a refusal of the contract.

Desktop only: it imports the model.
"""
from spec import constants as C
from model import run, source

from host import blob as B
from host import fake, library

WORD_MASK = (1 << C.BUS["word_bits"]) - 1


def _at(name, word=0):
    return C.REGISTERS[name][0] + 4 * word


def _signed32(w):
    return w - (1 << 32) if w & (1 << 31) else w


class ModelKernel(fake.Registers):
    """See the module. `memory_group` and `close` are what host.run_case asks of a backend besides `do`."""

    def __init__(self, profile, blob, sigma, polls_running=3, **caps):
        super().__init__(fake.identity_words(profile, **caps))
        self.profile, self.blob, self.sigma = profile, blob, sigma
        self.polls_running = polls_running
        self.memory_group = 0
        self.closed = False
        self.runs = 0
        self._clear()
        hooks = {
            _at("src_table_length"): self._table_length,
            _at("src_table_entry", 1): self._table_entry,
            _at("inj_truth_amplitude_den"): self._truth,
            _at("configure"): self._configure,
            _at("shadow_data"): self._shadow,
            _at("krn_start"): self._start,
            _at("krn_reset"): self._reset,
        }
        self.on_write.update(hooks)
        self.on_read[_at("krn_status")] = self._status

    def _clear(self):
        self.table, self.table_length, self.truth, self.core_words = [], None, [], []
        self.left = None
        self.started = False

    # ----------------------------------------------------------------- what the library writes
    def _table_length(self, b, word):
        self.table, self.table_length = [], word

    def _table_entry(self, b, word):
        self.words[_at("src_table_entry", 1)] = word
        self.table.append(self.words.get(_at("src_table_entry"), 0) | (word << 32))

    def _truth(self, b, word):
        if self.started:
            raise AssertionError("ModelKernel: a truth record written after krn_start; the stand-in runs the model once")
        self.truth.append({"index": fake.value(self, "inj_truth_index"),
                           "pulse_id": self.words.get(_at("inj_truth_pulse_id"), 0),
                           "amplitude_num": _signed32(self.words.get(_at("inj_truth_amplitude_num"), 0)),
                           "amplitude_den": word})

    def _configure(self, b, word):
        self.core_words = []

    def _shadow(self, b, word):
        self.core_words.append(word)

    def _reset(self, b, word):
        self._clear()
        for name in ("src_refusal", "inj_refusal", "refusal", "krn_refusal"):
            self.words[_at(name)] = 0
        self.words.update(fake.value_words("krn_records", 0))

    # ----------------------------------------------------------------- the run
    def _start(self, b, word):
        frames, base, seed = fake.value(self, "krn_frames"), fake.value(self, "krn_buffer"), fake.value(self, "src_seed")
        want = [w & WORD_MASK for w in B.words(B.read(self.blob))]
        if self.core_words != want:
            raise AssertionError("ModelKernel: the core's words written are not the blob's it was handed")
        noise = source.Noise(self.profile, seed, self.sigma[0], self.sigma[1], frames)
        if self.table_length != len(noise.table) - 1 or self.table != list(noise.table[:-1]):
            raise AssertionError("ModelKernel: the table written is not the sigma's")
        handle = [h for h, at in self.addresses.items() if at <= base < at + len(self.memory[h])][0]
        at = base - self.addresses[handle]
        pairs, _truth = run.scores(noise, self.truth, frames, self.blob)
        pad = bytes(library.SLOT - library.RECORD_BYTES)
        out = bytearray()
        for _frame, r in pairs:
            out += library.SLOT_FORMAT.pack(*[r[name] for name, _b, _s in library.SCORE], pad)
        self.memory[handle][at:at + len(out)] = out
        self.words.update(fake.value_words("krn_records", frames))
        self.left = self.polls_running
        self.started = True
        self.runs += 1

    def _status(self, b):
        bits = C.REGISTER_BITS["krn_status"]
        if self.left is None:
            return 0
        if self.left > 0:
            self.left -= 1
            return 1 << bits["running"]
        return 1 << bits["done"]

    def close(self):
        self.closed = True

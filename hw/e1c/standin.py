"""The first size's stand-in for the card on E1C's runs: E0C's ModelKernel, and the two things more these runs ask of it.

`CardModel(profile, blob, sigma, swap_blob=None, stride=None)` is `hw.e0c.kernel_model.ModelKernel`, imported, with:
  - THE START EPOCH: the data of the core's `start` write (host.library's `load`) is the epoch the run's records
    carry, as the core's own is. ModelKernel's model run is at epoch 0.
  - A SWAP: the words written after `shadow_begin` once the run is going are the shadow's, held against the
    `swap_blob` it was handed (as ModelKernel holds the load's words against its blob). The write of commit_at's upper
    word is the commit, at the index its two words name. If that index is below the frames the stand-in says the
    core has taken, the commit is refused, SWAP_INDEX, latched in the core's refusal register, as the core latches
    it (docs/rtl/core.md, its refusals); otherwise the run's buffer is made again as the model's run of the same
    stream with the shadow written and the swap committed at that index (`model.weights.Store`).
  - NEXT_INDEX: each read of next_index's lower word says `stride` more frames have been taken, up to the run's
    frames, so that host.run_case's wait for --swap-after ends as it does on the card.
  - TRUTH WHILE THE RUN GOES: a truth record the library writes after krn_start is taken (ModelKernel refuses one),
    and the run's buffer is made again before krn_status next says done. So the library's feeding of a schedule
    longer than the injector's store, 1,024 before the start and the rest while the run goes, is the path here as
    on the card. The stand-in never says a record came late: a host behind the stream is the injector's to refuse.
krn_status says running for `polls_running` reads and done after, as ModelKernel's; `run` gives it enough reads for
every record to be fed.

It is NOT a kernel and models no block. A commit's time is the stand-in's count of next_index reads, not a clock.

Desktop only: it imports the model.
"""
import json
import os

from spec import constants as C
from model import inject, source
from model.detector import Core

from host import blob as B
from host import fake, library, run_case

from hw.e0c import run_piece
from hw.e0c.kernel_model import ModelKernel, WORD_MASK, _at


def model_records(profile, seed, sigma, frames, schedule, blob, epoch, swap=None):
    """The model's score records of one run: its noise, its truth records, one core at `epoch`, and a swap
    (blob, at, after) whose shadow is written once `after` frames are taken and committed at `at`."""
    noise = source.Noise(profile, seed, sigma[0], sigma[1], frames)
    injected, _truth = inject.inject(profile, noise, schedule, frames)
    core = Core(blob, epoch)
    out = []
    for frame in injected:
        if swap is not None and core.next_index == swap[2]:
            core.write_shadow(swap[0])
            core.commit(swap[1])
        out.append(core.step(frame))
    return out


class CardModel(ModelKernel):
    """See the module."""

    def __init__(self, profile, blob, sigma, swap_blob=None, stride=None, polls_running=3, **caps):
        super().__init__(profile, blob, sigma, polls_running, **caps)
        self.swap_blob = swap_blob
        self.stride = stride
        self.on_write[_at("start")] = self._start_epoch
        self.on_write[_at("shadow_begin")] = self._shadow_begin
        self.on_write[_at("commit_at", 1)] = self._commit
        self.on_read[_at("next_index")] = self._next_low
        self.on_read[_at("next_index", 1)] = self._next_high

    def _clear(self):
        super()._clear()
        self.epoch, self.taken, self.swap_words, self.swap, self.frames, self.dirty = 0, 0, None, None, 0, False

    def _truth(self, b, word):
        """A truth record written while the run goes is taken, as the library feeds the card's injector, and the
        buffer is made again before krn_status next says done. (ModelKernel refuses one: it runs the model once.)"""
        started, self.started = self.started, False
        try:
            super()._truth(b, word)
        finally:
            self.started = started
        self.dirty = started

    def _status(self, b):
        if self.dirty and self.left is not None and self.left <= 1:
            self._fill()
            self.dirty = False
        return super()._status(b)

    def _start_epoch(self, b, word):
        self.words[_at("start")] = word
        self.epoch = word

    def _shadow(self, b, word):
        if self.started:
            if self.swap_words is None:
                raise AssertionError("CardModel: a shadow word written while the run goes, with no shadow_begin before it")
            self.swap_words.append(word)
        else:
            self.core_words.append(word)

    def _shadow_begin(self, b, word):
        if not self.started:
            raise AssertionError("CardModel: a shadow_begin before krn_start; the stand-in swaps only while a run goes")
        self.swap_words = []
        self.shadow_taken = self.taken

    def _commit(self, b, word):
        self.words[_at("commit_at", 1)] = word
        at = self.words.get(_at("commit_at"), 0) | (word << 32)
        if at < self.taken:
            self.words[_at("refusal")] = C.REFUSAL_CODES["SWAP_INDEX"]
            return
        want = [w & WORD_MASK for w in B.words(B.read(self.swap_blob))]
        if self.swap_words != want:
            raise AssertionError("CardModel: the shadow's words written are not the swap blob's it was handed")
        self.swap = (self.swap_blob, at, min(self.shadow_taken, at))
        self._fill()

    def _next_low(self, b):
        if self.started and self.stride:
            self.taken = min(self.frames, self.taken + self.stride)
        return self.taken & WORD_MASK

    def _next_high(self, b):
        return self.taken >> 32

    def _start(self, b, word):
        frames, base, seed = fake.value(self, "krn_frames"), fake.value(self, "krn_buffer"), fake.value(self, "src_seed")
        want = [w & WORD_MASK for w in B.words(B.read(self.blob))]
        if self.core_words != want:
            raise AssertionError("CardModel: the core's words written are not the blob's it was handed")
        noise = source.Noise(self.profile, seed, self.sigma[0], self.sigma[1], frames)
        if self.table_length != len(noise.table) - 1 or self.table != list(noise.table[:-1]):
            raise AssertionError("CardModel: the table written is not the sigma's")
        self.handle = [h for h, at in self.addresses.items() if at <= base < at + len(self.memory[h])][0]
        self.base_at, self.seed, self.frames = base - self.addresses[self.handle], seed, frames
        self._fill()
        self.words.update(fake.value_words("krn_records", frames))
        self.left = self.polls_running
        self.started = True
        self.runs += 1

    def _fill(self):
        recs = model_records(self.profile, self.seed, self.sigma, self.frames, self.truth, self.blob, self.epoch, self.swap)
        pad = bytes(library.SLOT - library.RECORD_BYTES)
        out = bytearray()
        for r in recs:
            out += library.SLOT_FORMAT.pack(*[r[name] for name, _b, _s in library.SCORE], pad)
        self.memory[self.handle][self.base_at:self.base_at + len(out)] = out


def run(folder, r, out, swap_at=None, swap_after=None, blob=None, epoch=None, stride=None, polls=100):
    """One run of order.txt (`r`, as `hw.e1c.e1c.read_order` gives it) through the box's path, `hw/e0c/run_piece.py`
    and `host.run_case`, unchanged, the card a CardModel: run_case's exit code. The keyword arguments are what a
    test changes: the commit's index or its wait, the blob the card is handed, its start epoch."""
    with open(os.path.join(folder, r["case"], "piece.json"), encoding="utf-8") as f:
        info = json.load(f)
    blob_path = os.path.join(folder, blob or r["blob"])
    argv = ["--xclbin", "stand-in", "--shim", "stand-in", "--blob", blob_path,
            "--epoch", str(r["epoch"] if epoch is None else epoch), "--table", os.path.join(folder, "table.json"),
            "--seed", str(info["seed"]), "--frames", str(info["frames"]),
            "--schedule", os.path.join(folder, r["case"], "schedule.json"), "--out", out, "--polls", str(polls)]
    swap = None
    if "swap_blob" in r:
        with open(os.path.join(folder, r["swap_blob"]), "rb") as f:
            swap = f.read()
        argv += ["--swap-blob", os.path.join(folder, r["swap_blob"]),
                 "--swap-at", str(r["swap_at"] if swap_at is None else swap_at),
                 "--swap-after", str(r["swap_after"] if swap_after is None else swap_after)]
    with open(blob_path, "rb") as f:
        kernel_blob = f.read()
    with open(os.path.join(folder, r["case"], "schedule.json"), encoding="utf-8") as f:
        truth = len(json.load(f))
    step = stride or max(1, info["frames"] // 16)
    running = truth // C.MAX_INJECT_PENDING + 3          # status reads that say running: enough for every record fed
    kept = run_case.Backend
    run_case.Backend = lambda *a, **kw: CardModel(info["profile"], kernel_blob, tuple(info["sigma"]), swap, stride=step,
                                                  polls_running=running)
    try:
        return run_piece.main(argv)
    finally:
        run_case.Backend = kept

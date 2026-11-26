"""The learner of phase B, in the model: the difference of two class means, run in the stream.

The fabric's learner is written here first, and the RTL is held to this word for word. The rule is
round 2's (`learn/trainer.py`, `docs/model/lrn-a.md`): two sums of labelled windows and two counts, and
the weights the difference of the two means. What is new is WHERE the windows come from and WHEN the
weights change: the windows are taken from the core's delay line as the stream passes, and a weight set
is made only at an index the host names, and swapped in only by a commit the host names.

ONE LEARNER, ONE CORE. `Learner(blob, truth, ...)` makes a `model.detector.Core` from the blob and
wraps it. Every frame goes through `step`, which hands the core the frame unchanged and keeps a copy of
the last T frames, T the running shape's taps: the core's delay line, with zeros before frame 0.

WHAT IS READ OF THE TRUTH: each record's `index`, and nothing else. Not its pulse id, not its
amplitude, and never a score record. The indexes must be ints of the index field, strictly ascending.

THE TWO WINDOWS OF A RECORD at index j, with p the record before it and q the one after it:

    label 0   frames j-T .. j-1   judged when the core's next index is j (when the learner is made, for j = 0)
    label 1   frames j .. j+T-1   judged when the core's next index is j + T

A window judged is taken (added to its label's sum, its count up by one) or skipped, and counted under
the first of these that holds:

    label 0   START  j < T: it would start before frame 0
              BUSY   p exists and j - p < 2T: the span p .. p+T-1 touches it
              FULL   its label's count is at its most, 2^count_bits - 1
    label 1   BUSY   p exists and j - p < T, or q exists and q - j < T
              FULL   as label 0's

A record's span is taken to be j .. j+T-1: the learner is not told a pulse's length, as the trainer is
not. These are the trainer's conditions (`learn.trainer.labelled_windows`, and TRAINER_COUNT at the
fabric's bound): the trainer raises where this skips and counts. A window whose judge point the stream
never reaches is neither judged nor counted.

THE UPDATE. `update(u)` names one. It is MADE at the first moment the core's next index is u and every
window judged there has been judged: from the sums and counts as they stand then,

    D[c][k] = S1[k][c] * n0 - S0[k][c] * n1         for each channel c, each tap k (tap 0 the oldest frame)

quantised as one set by `model.weights.quantise` (peak to COEFF_MAX, half to even) and packed by
`model.weights.pack` in the matched-filter configuration: one filter reading every channel, the
rectifier passing, a pool of 1, no shift, a head weight of 1. Those are the two calls
`learn.handover.candidate_blob` makes; the factor 1 / (n0 n1) between D and the trainer's weights
cancels against the peak. The set is written to the core's shadow. A count at zero makes every D zero
(that label's sum is zero too), and an all-zero set is the quantiser's refusal, QUANTISE_INPUT: the
update then makes no set and the shadow is left as it was.

The update is FINISHED when the next index is u + update_frames, whatever it made, and its outcome is
published then: `lrn_made` or `lrn_unmade` counts it and `status()` says it. A window judged between u
and the finish goes into the sums for the next update: the update at u is of the sums at u.

UNTIL AN UPDATE IS FINISHED, from its naming, these are refused UPDATE_UNFINISHED: a commit (counted,
`lrn_early`), a shadow write, another update. After it the shadow holds the last set written, by the
learner or the host, and a commit takes what it holds. Each host operation is refused in this order:

    update(u)          UPDATE_UNFINISHED, SWAP_SHAPE (the running shape is not the matched-filter
                       configuration of its profile and taps), SWAP_PENDING (a commit is scheduled),
                       SWAP_INDEX (u not an int, below the next index, or u + update_frames past the
                       index field's most)
    commit(at)         UPDATE_UNFINISHED, then the core's own: SWAP_PENDING, SWAP_INDEX, SWAP_EPOCH
    write_shadow(blob) UPDATE_UNFINISHED, then the core's own

Made: LEARN_BOUND (count_bits outside 1..LEARN_COUNT_BITS, update_frames outside
0..LEARN_UPDATE_FRAMES: smaller values are a small build's), after the core's own refusals of the blob;
then RECORD_FIELD and RECORD_ORDER for the truth's indexes.

What is counted, under the definition's register names: `lrn_count0`, `lrn_count1` (windows taken),
`lrn_skip_start`, `lrn_skip_busy`, `lrn_skip_full`, `lrn_made`, `lrn_unmade`, `lrn_early`.

This file imports the standard library, the definition's generated constants and the model's own
modules, and nothing of `learn/`, `stats/` or numpy.

Limits, each by what it concedes (docs/model/lrn-b.md has them all):
  - The trainer's equality is by construction: the same `quantise` and `pack`. A fault in either is
    in both; the hand-worked vector (vectors/lrn-b/) is what judges them.
  - Frames and no clocks: update_frames is a number this is given. Whether a fabric meets it is not
    something this file can say.
  - Isolation by what is passed: this reads `index` alone, and a learner written to read more would
    be caught only by its output.
  - No forgetting: the sums hold every window taken since the learner was made.
  - A caller that calls the core's own `commit` or `write_shadow`, not this file's, is not held to
    UPDATE_UNFINISHED.
"""
from collections import deque

from spec import constants as C
from model import stream, weights
from model.detector import Core, bits_for
from model.refusal import Refusal

PASS = C.RECTIFIERS["pass"]
INDEX_MAX = weights.INDEX_MAX

# The counts and counters, by the names the definition gives their registers.
COUNTS = ("lrn_count0", "lrn_count1")
COUNTERS = ("lrn_skip_start", "lrn_skip_busy", "lrn_skip_full", "lrn_made", "lrn_unmade", "lrn_early")
SKIPPED = {"start": "lrn_skip_start", "busy": "lrn_skip_busy", "full": "lrn_skip_full"}
STATUS_BITS = ("named", "running", "made", "unmade")       # the state bits of lrn_status; the latch's two are the fabric's
for _name in COUNTS + COUNTERS:
    if _name not in C.REGISTERS:
        raise ImportError("model/learner.py counts under the register %s, which the definition does not declare" % _name)
for _name in STATUS_BITS:
    if _name not in C.REGISTER_BITS.get("lrn_status", {}):
        raise ImportError("model/learner.py reports the bit %s of lrn_status, which the definition does not declare" % _name)


def _bound(value, lo, hi, what):
    if type(value) is not int or not lo <= value <= hi:
        raise Refusal("LEARN_BOUND", "%s is %r; the definition allows %d..%d" % (what, value, lo, hi))
    return value


def ranges(profile_name, count_bits=C.LEARN_COUNT_BITS):
    """The extreme values of the learner's arithmetic under a profile: {value: (lowest, highest)}.

    With n = 2^count_bits - 1 windows a label at most and samples in smin..smax: a sum is n windows at
    an extreme; D = S1 n0 - S0 n1 lies in n0 n1 (smin - smax) .. n0 n1 (smax - smin); D * COEFF_MAX
    likewise; the peak is the largest magnitude of D.
    """
    prof = stream.profile(profile_name)
    _bound(count_bits, 1, C.LEARN_COUNT_BITS, "count_bits")
    n = (1 << count_bits) - 1
    smin, smax = prof["sample_min"], prof["sample_max"]
    d = n * n * (smax - smin)
    return {"count": (0, n), "sum": (n * smin, n * smax), "difference": (-d, d),
            "scaled": (-d * C.COEFF_MAX, d * C.COEFF_MAX), "peak": (0, d)}


def widths(profile_name, count_bits=C.LEARN_COUNT_BITS):
    """The width, in bits, of each value the learner's arithmetic holds. The count and the peak are
    unsigned; the rest signed. A coefficient is COEFF_BITS."""
    r = ranges(profile_name, count_bits)
    out = {name: bits_for(lo, hi) for name, (lo, hi) in r.items() if name not in ("count", "peak")}
    out["count"] = count_bits
    out["peak"] = r["peak"][1].bit_length()
    out["coefficient"] = C.COEFF_BITS
    return out


class Learner:
    """One core and the learner beside it. See the top of this file."""

    def __init__(self, blob, truth, update_frames=C.LEARN_UPDATE_FRAMES, count_bits=C.LEARN_COUNT_BITS, epoch=0):
        self.core = Core(blob, epoch)
        self.update_frames = _bound(update_frames, 0, C.LEARN_UPDATE_FRAMES, "update_frames")
        self.count_bits = _bound(count_bits, 1, C.LEARN_COUNT_BITS, "count_bits")
        self.count_max = (1 << count_bits) - 1
        config = self.core.store.config
        self.profile = config["profile"]
        self.channels = self.core.profile["channels"]
        self.taps = self.core.store.shape[2]
        self.indexes = self._read_indexes(truth)
        self._matched = weights.shape(weights.unpack(self._pack([0] * (self.channels * self.taps))))
        self._line = deque([(0,) * self.channels] * self.taps, maxlen=self.taps)
        self.sums = [[[0] * self.channels for _ in range(self.taps)] for _ in (0, 1)]    # [label][tap][channel]
        self.counts = [0, 0]
        self._counters = dict.fromkeys(COUNTERS, 0)
        self.log = []               # every judgement: (next index, record index, label, outcome)
        self.updates = []           # every update made: a dict, see _make
        self._update = None         # the update named and not finished
        self._last = None           # "made" or "unmade": the outcome of the last update finished
        self._due = {}              # next index -> [(record index, the one before, the one after, label)]
        for n, j in enumerate(self.indexes):
            p = self.indexes[n - 1] if n else None
            q = self.indexes[n + 1] if n + 1 < len(self.indexes) else None
            self._due.setdefault(j, []).append((j, p, q, 0))
            self._due.setdefault(j + self.taps, []).append((j, p, q, 1))
        self._at(0)

    # ------------------------------------------------------------ what it is handed

    @staticmethod
    def _read_indexes(truth):
        """The truth's indexes, read off each record's `index` alone."""
        if not isinstance(truth, (list, tuple)):
            raise Refusal("RECORD_FIELD", "the truth is a list or tuple of truth records")
        out = []
        for record in truth:
            if not isinstance(record, dict) or "index" not in record:
                raise Refusal("RECORD_FIELD", "a truth record is a dict with an index")
            j = record["index"]
            if type(j) is not int or not 0 <= j <= INDEX_MAX:
                raise Refusal("RECORD_FIELD", "truth.index = %r does not fit the index field" % (j,))
            if out and j <= out[-1]:
                raise Refusal("RECORD_ORDER", "truth index %d after %d: the indexes rise strictly" % (j, out[-1]))
            out.append(j)
        return tuple(out)

    def _pack(self, values):
        t = self.taps
        return weights.pack(self.profile, [{c: tuple(values[c * t:(c + 1) * t]) for c in range(self.channels)}],
                            (1,), PASS, 1, 0)

    @property
    def next_index(self):
        return self.core.next_index

    # ------------------------------------------------------------ the stream

    def step(self, frame):
        """Hand the core the frame; then judge and update at the core's new next index. Returns its record."""
        record = self.core.step(frame)
        self._line.append(frame)
        self._at(self.core.next_index)
        return record

    def _at(self, n):
        """Everything due when the core's next index is n: the windows judged, then an update made, then finished."""
        for j, p, q, label in self._due.pop(n, ()):
            self._judge(n, j, p, q, label)
        if self._update is not None and not self._update["made"] and self._update["u"] == n:
            self._make()
        if self._update is not None and self._update["made"] and self._update["finish"] == n:
            self._finish()

    # Each condition is a method of its own, so that a test can build a learner wrong in one place.

    def _start(self, j):
        return j < self.taps

    def _busy0(self, j, p):
        return p is not None and j - p < 2 * self.taps

    def _busy1_before(self, j, p):
        return p is not None and j - p < self.taps

    def _busy1_after(self, j, q):
        return q is not None and q - j < self.taps

    def _full(self, label):
        return self.counts[label] >= self.count_max

    def _outcome(self, j, p, q, label):
        if label == 0:
            if self._start(j):
                return "start"
            if self._busy0(j, p):
                return "busy"
        elif self._busy1_before(j, p) or self._busy1_after(j, q):
            return "busy"
        if self._full(label):
            return "full"
        return "taken"

    def _judge(self, n, j, p, q, label):
        outcome = self._outcome(j, p, q, label)
        if outcome == "taken":
            self._take(label, tuple(self._line))
        else:
            self._counters[SKIPPED[outcome]] += 1
        self.log.append((n, j, label, outcome))

    def _take(self, label, window):
        """Add a window, the delay line oldest frame first, to its label's sum."""
        s = self.sums[label]
        for k, frame in enumerate(window):
            for c, v in enumerate(frame):
                s[k][c] += v
        self.counts[label] += 1

    def _difference(self):
        n0, n1 = self.counts
        s0, s1 = self.sums
        return [s1[k][c] * n0 - s0[k][c] * n1 for c in range(self.channels) for k in range(self.taps)]

    def _quantise(self, d):
        return weights.quantise(d)

    def _make(self):
        u = self._update
        d = self._difference()
        u["counts"], u["difference"] = tuple(self.counts), tuple(d)
        u["sums"] = tuple(tuple(tuple(row) for row in s) for s in self.sums)     # [label][tap][channel], at u
        try:
            u["blob"] = self._pack(self._quantise(d))
        except Refusal as e:
            if e.name != "QUANTISE_INPUT":
                raise
            u["blob"], u["name"] = None, e.name           # no set: the shadow is left as it was
        else:
            self.core.write_shadow(u["blob"])
        u["made"] = True
        self.updates.append(u)

    def _finish(self):
        u = self._update
        u["outcome"] = "made" if u["blob"] is not None else "unmade"
        self._counters["lrn_" + u["outcome"]] += 1
        self._last = u["outcome"]
        self._update = None

    # ------------------------------------------------------------ the host's operations

    def _unfinished(self, what):
        if self._update is not None:
            raise Refusal("UPDATE_UNFINISHED", "%s while the update named at %d is not finished: it is at %d, the "
                          "next index is %d" % (what, self._update["u"], self._update["finish"], self.next_index))

    def update(self, at):
        """Name an update at index `at`. See the top of this file for what is refused, and in which order."""
        self._update_unfinished()
        self._update_shape()
        self._update_pending()
        self._update_index(at)
        self._update = {"u": at, "finish": self._finish_index(at), "made": False, "counts": None, "sums": None,
                        "difference": None, "blob": None, "name": None, "outcome": None}
        self._at_now()

    def _update_unfinished(self):
        self._unfinished("an update")

    def _update_shape(self):
        if self.core.store.shape != self._matched:
            raise Refusal("SWAP_SHAPE", "the running shape %r is not the matched-filter configuration %r"
                          % (self.core.store.shape, self._matched))

    def _update_pending(self):
        if self.core.store.pending():
            raise Refusal("SWAP_PENDING", "a commit is scheduled; the shadow is what it will make active")

    def _update_index(self, at):
        if type(at) is not int or not self.next_index <= at or at + self.update_frames > INDEX_MAX:
            raise Refusal("SWAP_INDEX", "an update at %r; the next index is %d and an update finishes %d frames on, "
                          "inside 0..%d" % (at, self.next_index, self.update_frames, INDEX_MAX))

    def _finish_index(self, at):
        return at + self.update_frames

    def _at_now(self):
        """An update named at the next index itself is made at once, and with no update time finished at once."""
        n = self.next_index
        if self._update["u"] == n:
            self._make()
            if self._update["finish"] == n:
                self._finish()

    def commit(self, at):
        """The core's commit, once no update is unfinished."""
        if self._update is not None:
            self._counters["lrn_early"] += 1
            self._unfinished("a commit")
        self.core.commit(at)

    def write_shadow(self, blob):
        """The core's shadow write, once no update is unfinished."""
        self._unfinished("a shadow write")
        self.core.write_shadow(blob)

    # ------------------------------------------------------------ what can be read

    def counters(self):
        """The counts and counters, under the definition's register names."""
        out = dict(zip(COUNTS, self.counts))
        out.update(self._counters)
        return out

    def status(self):
        """The state bits of lrn_status: an update named and its index not reached; made and not finished;
        the last update finished made a set; it made none. The latch's two bits are the fabric's."""
        u = self._update
        return {"named": int(u is not None and not u["made"]), "running": int(u is not None and u["made"]),
                "made": int(self._last == "made"), "unmade": int(self._last == "unmade")}

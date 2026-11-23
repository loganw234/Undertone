"""The scorer: the threshold, the histogram and the event records.

It is fed one (frame, score record) pair at a time, in stream order, and it
reads nothing else. Integers only.

COUNTED RECORDS. A record with the settling flag is left out of everything
below and counted in `excluded`. A record with the overflow flag is counted
like any other; `overflow_at` is the index of the first record that carried
the flag, or None. A run in which it is not None is a marked run.

THRESHOLD. A counted record is above when its score is STRICTLY GREATER than
the threshold. `crossings` is the number of counted records that are above.

EVENTS. An event is captured at every counted record that is above and whose
predecessor was not: not above, or not counted, or there was none. Every such
rising crossing gives an event; capture windows may overlap; none is dropped.
The event record is {index, epoch, score} of that record, `pre` = the number
of frames captured before it (the configured pre, or the index if the stream
began later than that) and `post` = the number captured after it (the
configured post, or fewer if the stream ended first). `events[n]` is the
record and `captures[n]` its frames, pre + 1 + post of them, oldest first.
An event appears when its capture is complete; `close()` ends the stream and
completes the captures still open. Events are in order of their index.

HISTOGRAM. `hist_bins` bins of width 2^hist_shift, the first starting at
`hist_lo`. A counted score lands in bin floor((score - hist_lo) / 2^hist_shift)
when that is one of the bins, in `below` when the score is under `hist_lo`,
and in `above` when it is past the last bin. Nothing is dropped:
below + the bins + above = `counted`.
"""
from collections import deque

from spec import constants as C
from model import records, stream
from model.refusal import Refusal


def _field_range(kind, name):
    for field, bits, sign in C.RECORDS[kind]:
        if field == name:
            return (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if sign == "signed" else (0, (1 << bits) - 1)
    raise KeyError(name)


SCORE_MIN, SCORE_MAX = _field_range("score", "score")
SCORE_BITS = dict((f[0], f[1]) for f in C.RECORDS["score"])["score"]
PRE_MAX = _field_range("event", "pre")[1]
POST_MAX = _field_range("event", "post")[1]
SETTLING = 1 << C.FLAGS["settling"]
OVERFLOW = 1 << C.FLAGS["overflow"]


def _is_int(v, lo, hi):
    return type(v) is int and lo <= v <= hi


class Scorer:
    def __init__(self, profile, threshold, pre, post, hist_lo, hist_shift, hist_bins):
        self.profile = stream.profile(profile)
        if not _is_int(threshold, SCORE_MIN, SCORE_MAX):
            raise Refusal("SCORER_THRESHOLD", "threshold %r is not an int the score field holds" % (threshold,))
        if not _is_int(pre, 0, PRE_MAX) or not _is_int(post, 0, POST_MAX):
            raise Refusal("SCORER_WINDOW", "pre %r, post %r; each is 0..%d" % (pre, post, PRE_MAX))
        if not _is_int(hist_bins, 1, C.MAX_HIST_BINS) or not _is_int(hist_shift, 0, SCORE_BITS - 1) \
                or not _is_int(hist_lo, SCORE_MIN, SCORE_MAX):
            raise Refusal("SCORER_BINS", "hist_lo %r, hist_shift %r, hist_bins %r; bins are 1..%d and the shift 0..%d"
                          % (hist_lo, hist_shift, hist_bins, C.MAX_HIST_BINS, SCORE_BITS - 1))
        self.threshold, self.pre, self.post = threshold, pre, post
        self.hist_lo, self.hist_shift = hist_lo, hist_shift
        self.below, self.bins, self.above = 0, [0] * hist_bins, 0
        self.counted = self.excluded = self.crossings = 0
        self.overflow_at = None
        self.events, self.captures = [], []
        self.next_index = 0
        self.closed = False
        self._was_above = False
        self._recent = deque(maxlen=pre)       # the last `pre` frames
        self._open = []                        # captures still collecting: [record, frames, frames still wanted]

    def histogram(self):
        return {"below": self.below, "bins": tuple(self.bins), "above": self.above}

    def _bin(self, score):
        if score < self.hist_lo:
            self.below += 1
            return
        b = (score - self.hist_lo) >> self.hist_shift
        if b < len(self.bins):
            self.bins[b] += 1
        else:
            self.above += 1

    def _complete(self, capture):
        record, frames, _wanted = capture
        record["post"] = len(frames) - record["pre"] - 1
        self.events.append(records.check("event", record))
        self.captures.append(tuple(frames))

    def feed(self, frame, record):
        """Take the next frame and the score record made from it."""
        if self.closed:
            raise Refusal("RECORD_ORDER", "the stream was closed")
        stream.check_frame(self.profile, frame)
        records.check("score", record)
        if record["index"] != self.next_index:
            raise Refusal("RECORD_ORDER", "record index %d; the next is %d" % (record["index"], self.next_index))
        for capture in self._open:
            capture[1].append(frame)
            capture[2] -= 1
        while self._open and self._open[0][2] == 0:
            self._complete(self._open.pop(0))
        if record["flags"] & OVERFLOW and self.overflow_at is None:
            self.overflow_at = record["index"]
        if record["flags"] & SETTLING:
            self.excluded += 1
            above = False
        else:
            self.counted += 1
            self._bin(record["score"])
            above = record["score"] > self.threshold
            if above:
                self.crossings += 1
                if not self._was_above:
                    capture = [{"index": record["index"], "epoch": record["epoch"], "score": record["score"],
                                "pre": len(self._recent), "post": 0}, list(self._recent) + [frame], self.post]
                    if self.post == 0:
                        self._complete(capture)
                    else:
                        self._open.append(capture)
        self._was_above = above
        self._recent.append(frame)
        self.next_index += 1

    def run(self, pairs):
        """Feed every (frame, record) pair, then close."""
        for frame, record in pairs:
            self.feed(frame, record)
        self.close()

    def close(self):
        """The stream has ended: complete the captures still open, with the frames they have."""
        while self._open:
            self._complete(self._open.pop(0))
        self.closed = True

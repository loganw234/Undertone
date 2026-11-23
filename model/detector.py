"""The detector core: a stream of frames in, one score record per frame out.

Integers only. For output index i, with frame i = (x_0[i], ..., x_{C-1}[i])
and x_c[m] = 0 for m < 0:

  1. filter bank   y_k[i] = sum over the channels c that filter k reads, and
                   over j = 0..T-1, of w[k][c][j] * x_c[i - (T-1) + j].
                   Coefficient 0 meets the oldest sample of the window and
                   coefficient T-1 the newest, x[i]. Exact.
                   (Written as a convolution, y[i] = sum c[j] x[i-j], the same
                   filter has its coefficients reversed. This model uses the
                   form above.)
  2. rectifier     r_k[i] = y_k[i] (pass) or |y_k[i]| (abs). Exact.
  3. pool          z_k[i] = sum over m = 0..P-1 of r_k[i - m], with r_k[m] = 0
                   for m < 0. A moving sum. Exact.
  4. head          a[i] = sum over k of h[k] * z_k[i]. Exact.
  5. score         v[i] = floor(a[i] / 2^s): the one rounding in the datapath,
                   toward minus infinity (an arithmetic shift right).

The record's index is i, the index of the newest sample it used.

The matched-filter configuration is one setting of this, not another path:
one filter, the rectifier passing, P = 1, s = 0 and a head weight of 1 give
score[i] = y_0[i].

A HIDDEN LAYER (a version 2 blob; docs/model/head.md) puts H units between the
pooled values and the score. Step 4 becomes four, and step 5 is unchanged:

  4a. hidden sum    u_j[i] = sum over k of g[j][k] * z_k[i], for each unit j.
                    Step 4's sum under the unit's own weights. Exact.
  4b. hidden value  t_j[i] = floor(u_j[i] / 2^q), q the hidden shift: a second
                    rounding, toward minus infinity like the score's.
  4c. between       b_j[i] = t_j[i] (pass) or |t_j[i]| (abs): the rectifier's
                    two modes, by the blob's `between` code. Exact.
  4d. output sum    a[i] = sum over j of o[j] * b_j[i], o the H head weights.
                    Exact.

Today's head is one setting of that: one unit whose weights are the old head
weights, q = the old score shift, pass between, a head weight of 1 and a score
shift of 0 give the old score and the old flag at every output. A version 1
blob does not take that route here: it takes steps 4 and 5 as they are.

WIDTHS. Every stage value is reduced to the stage's declared width, two's
complement, and a reduction that changes the value raises the sticky overflow
flag. `widths()` derives the declared widths from the definition's maxima; for
the filter, the rectifier, the pool and the head they are wide enough that the
reduction never changes anything. The score is the one width that is a choice:
the record's score field. When v[i] does not fit it, the field holds v[i]
modulo 2^64 as two's complement, and the flag is set in that record and every
later one.

`hidden_widths()` derives the hidden layer's three. The hidden value's width
is the second choice, and it is the score field's width, so that today's head
is exactly the setting above: when floor(u_j / 2^q) does not fit, t_j is that
value modulo 2^64 as two's complement, the same flag is set in that record and
every later one, and what follows is computed from the reduced value. The
other two, between and the output sum, are wide enough that the reduction
never changes anything. The hidden sum is step 4's and has step 4's width.

THE SWAP is the store's (`model.weights.Store`): which outputs use which
weights, and which carry the settling flag, is defined there.
"""
from collections import deque
from operator import mul

from spec import constants as C
from model import records, stream, weights

STAGES = ("filter", "rectifier", "pool", "head", "score")
HIDDEN_STAGES = ("hidden", "between", "output")    # what a hidden layer adds, between "head" and "score"


def bits_for(lo, hi):
    """The fewest signed bits that hold every integer from lo to hi."""
    bits = 1
    while not (-(1 << (bits - 1)) <= lo and hi <= (1 << (bits - 1)) - 1):
        bits += 1
    return bits


def ranges(profile_name):
    """The extreme values each stage can take under the definition's maxima.

    {stage: (lowest, highest)}, for "product" and each of STAGES but "score".
    One row of taps: MAX_TAPS products. One filter: as many rows as the
    profile has channels, and no more than MAX_ROWS. The pool: MAX_POOL
    filter values. The head: MAX_ROWS rows in the whole shape, each head
    weight at an extreme.
    """
    prof = stream.profile(profile_name)
    products = [s * c for s in (prof["sample_min"], prof["sample_max"]) for c in (C.COEFF_MIN, C.COEFF_MAX)]
    p_lo, p_hi = min(products), max(products)
    row_lo, row_hi = C.MAX_TAPS * p_lo, C.MAX_TAPS * p_hi
    per_filter = min(prof["channels"], C.MAX_ROWS)
    f_lo, f_hi = per_filter * row_lo, per_filter * row_hi
    r_lo, r_hi = f_lo, max(f_hi, -f_lo)                      # pass keeps the sign; abs folds it
    z_lo, z_hi = C.MAX_POOL * r_lo, C.MAX_POOL * r_hi
    # The head: sum of h[k] * z_k, and |z_k| is at most (rows of filter k) * MAX_POOL * one row's extreme,
    # so the whole sum is bounded by MAX_ROWS rows at that extreme under a head weight at its extreme.
    one_lo, one_hi = C.MAX_POOL * row_lo, C.MAX_POOL * max(row_hi, -row_lo)
    weighted = [h * z for h in (C.COEFF_MIN, C.COEFF_MAX) for z in (one_lo, one_hi)]
    a_lo, a_hi = C.MAX_ROWS * min(weighted), C.MAX_ROWS * max(weighted)
    return {"product": (p_lo, p_hi), "filter": (f_lo, f_hi), "rectifier": (r_lo, r_hi),
            "pool": (z_lo, z_hi), "head": (a_lo, a_hi)}


def widths(profile_name):
    """The declared width, in signed bits, of each stage under a profile."""
    out = {stage: bits_for(lo, hi) for stage, (lo, hi) in ranges(profile_name).items()}
    out["score"] = dict((f[0], f[1]) for f in C.RECORDS["score"])["score"]
    return out


def hidden_ranges(profile_name):
    """The extreme values each stage of a hidden layer can take: {stage: (lowest, highest)} for HIDDEN_STAGES.

    The hidden value is a choice, and the choice is the record's score field:
    every value that field holds. Between: pass keeps the sign and abs folds
    it, as at the rectifier. The output sum: MAX_HIDDEN units, each head
    weight at an extreme. None of the three depends on the sample format; the
    profile is named all the same, and an undeclared one is refused.
    """
    stream.profile(profile_name)
    bits = dict((f[0], f[1]) for f in C.RECORDS["score"])["score"]
    t_lo, t_hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    b_lo, b_hi = t_lo, max(t_hi, -t_lo)
    weighted = [o * b for o in (C.COEFF_MIN, C.COEFF_MAX) for b in (b_lo, b_hi)]
    return {"hidden": (t_lo, t_hi), "between": (b_lo, b_hi),
            "output": (C.MAX_HIDDEN * min(weighted), C.MAX_HIDDEN * max(weighted))}


def hidden_widths(profile_name):
    """The declared width, in signed bits, of each stage a hidden layer adds."""
    return {stage: bits_for(lo, hi) for stage, (lo, hi) in hidden_ranges(profile_name).items()}


class Core:
    """A detector core built from a configuration blob.

    `step(frame)` takes the next frame and returns its score record;
    `run(frames)` yields one record per frame, in order. A frame that is
    refused (CHANNELS, SAMPLE_RANGE) ends the run there: it advances nothing,
    and the records before it stand.
    """

    def __init__(self, blob, epoch=0):
        self.store = weights.Store(blob, epoch)
        config = self.store.config
        self.profile = stream.profile(config["profile"])
        self.width = dict(widths(config["profile"]), **hidden_widths(config["profile"]))
        self.rectifier = config["rectifier"]
        self.shift = config["score_shift"]
        self.hidden = len(config["hidden"]) if "hidden" in config else 0     # how many hidden units; 0 is no layer
        self.hidden_shift = config.get("hidden_shift")
        self.between = config.get("between")
        taps, pool = self.store.shape[2], config["pool"]
        self._line = [deque([0] * taps, maxlen=taps) for _ in range(self.profile["channels"])]
        self._window = [deque([0] * pool, maxlen=pool) for _ in config["filters"]]
        self._sum = [0] * len(config["filters"])
        self.overflow = False

    @property
    def next_index(self):
        return self.store.next_index

    def write_shadow(self, blob):
        self.store.write_shadow(blob)

    def commit(self, at):
        self.store.commit(at)

    # Each stage is a method of its own so that a test can build a core that is wrong in one place.

    def _fit(self, value, stage):
        """The value in the stage's declared width; the flag rises if that changed it."""
        bits = self.width[stage]
        low = value & ((1 << bits) - 1)
        if low >> (bits - 1):
            low -= 1 << bits
        if low != value:
            self.overflow = True
        return low

    def _filter(self, rows):
        total = 0
        for channel, coefficients in rows:
            total += sum(map(mul, coefficients, self._line[channel]))
        return self._fit(total, "filter")

    def _rectify(self, y):
        return self._fit(-y if self.rectifier == weights.ABS and y < 0 else y, "rectifier")

    def _pool(self, k, r):
        window = self._window[k]
        z = self._fit(self._sum[k] + r - window[0], "pool")   # the moving sum: the newest in, the oldest out
        window.append(r)
        self._sum[k] = z
        return z

    def _head(self, pooled, head):
        return self._fit(sum(map(mul, head, pooled)), "head")

    # The hidden layer's three stages. A hidden unit's sum is `_head` under the unit's weights.

    def _hidden(self, u):
        return self._fit(u >> self.hidden_shift, "hidden")    # the hidden shift: floor, as the score's

    def _between(self, t):
        return self._fit(-t if self.between == weights.ABS and t < 0 else t, "between")

    def _output(self, values, head):
        return self._fit(sum(map(mul, head, values)), "output")

    def _score(self, a):
        return self._fit(a >> self.shift, "score")            # >> on a Python int is floor division by 2^shift

    def step(self, frame):
        stream.check_frame(self.profile, frame)
        index = self.store.next_index
        coefficients, head, epoch, settling = self.store.step()
        for line, sample in zip(self._line, frame):
            line.append(sample)
        pooled = [self._pool(k, self._rectify(self._filter(rows))) for k, rows in enumerate(coefficients)]
        if self.hidden:
            units, out = head
            score = self._score(self._output([self._between(self._hidden(self._head(pooled, unit))) for unit in units], out))
        else:
            score = self._score(self._head(pooled, head))
        flags = (settling << C.FLAGS["settling"]) | (self.overflow << C.FLAGS["overflow"])
        return records.check("score", {"index": index, "epoch": epoch, "flags": flags, "score": score})

    def run(self, frames):
        for frame in frames:
            yield self.step(frame)

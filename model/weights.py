"""Weights: the quantising rule, the configuration blob, and the store with its swap.

Three things live here, and every one of them is integers only.

THE QUANTISING RULE (`quantise`). `spec/undertone.toml` states it: scale the
set so its largest magnitude maps to 2^(COEFF_BITS - 1) - 1, then round half to
even. A set is whatever one call is given. Values are ints or
`fractions.Fraction`; nothing here creates or accepts a float. A caller holding
a float converts it with `Fraction(x)`, which is exact.

THE CONFIGURATION BLOB (`pack`, `unpack`). A model is a shape inside the
definition's maxima, plus the weights, with a hash. On disk, blob version 1,
every integer little-endian:

    magic "UNDTBLOB"   8 bytes
    version            u16, 1
    name length        u8
    profile name       ASCII, that many bytes
    filters K          u16
    taps T             u16
    rectifier          u8, a code of spec.constants.RECTIFIERS
    score_shift        u8
    pool P             u32
    reserved           u32, zero
    K channel masks    u16 each: bit c set means the filter reads channel c
    the rows           filter 0's rows in ascending channel order, then filter
                       1's, ...; a row is T coefficients, i32, OLDEST SAMPLE
                       FIRST (coefficient T-1 meets the newest sample)
    K head weights     i32 each
    SHA-256            of every byte before it, 32 bytes

A filter reads the channels its mask names and holds one row for each. The
shape's cost is its rows, summed over the filters: at most MAX_ROWS.

`unpack` refuses, in this order: BLOB_FORMAT (not bytes, or too short to be a
blob), BLOB_HASH, BLOB_FORMAT (magic, version, a name that runs past the end),
PROFILE_UNKNOWN, RESERVED_BITS, SHAPE_FILTERS, SHAPE_TAPS, SHAPE_RECTIFIER,
SHAPE_SHIFT, SHAPE_POOL, BLOB_FORMAT (the masks run past the end),
SHAPE_CHANNEL, SHAPE_ROWS, BLOB_FORMAT (a length that disagrees with the
header), WEIGHT_RANGE. `pack` refuses, in this order: PROFILE_UNKNOWN,
SHAPE_FILTERS, SHAPE_CHANNEL, SHAPE_ROWS, SHAPE_TAPS, WEIGHT_COUNT,
SHAPE_RECTIFIER, SHAPE_SHIFT, SHAPE_POOL, WEIGHT_RANGE.

THE STORE (`Store`). An active weight set, a shadow, an epoch, and the swap,
defined per output sample: see the class.
"""
import hashlib
from fractions import Fraction

from spec import constants as C
from model.refusal import Refusal
from model import stream

if (C.QUANTISE_SCALE, C.QUANTISE_ROUNDING) != ("peak_to_max", "half_to_even"):
    raise ImportError("model/weights.py implements the rule peak_to_max, half_to_even; the definition now says %s, %s"
                      % (C.QUANTISE_SCALE, C.QUANTISE_ROUNDING))

PASS = C.RECTIFIERS["pass"]
ABS = C.RECTIFIERS["abs"]

MAGIC = b"UNDTBLOB"
VERSION = 1
HASH_BYTES = 32
MASK_BITS = 16
# The fixed fields after the profile name: (name, bytes), in order.
FIXED = (("filters", 2), ("taps", 2), ("rectifier", 1), ("score_shift", 1), ("pool", 4), ("reserved", 4))
FIXED_BYTES = sum(n for _name, n in FIXED)
NAME_AT = len(MAGIC) + 2 + 1           # where the profile name starts
WEIGHT_BYTES = 4                       # a coefficient or a head weight on disk
SMALLEST = NAME_AT + FIXED_BYTES + HASH_BYTES   # no blob is shorter than this


def _field_max(kind, name):
    for field, bits, sign in C.RECORDS[kind]:
        if field == name:
            return (1 << (bits - 1)) - 1 if sign == "signed" else (1 << bits) - 1
    raise KeyError(name)


EPOCH_MAX = _field_max("score", "epoch")
INDEX_MAX = _field_max("score", "index")


# ------------------------------------------------------------------ the rule

def round_half_even(p, d):
    """The integer nearest p/d, for d > 0; a tie goes to the even one."""
    f, rem = divmod(p, d)              # f = floor(p/d), 0 <= rem < d
    twice = 2 * rem
    if twice > d or (twice == d and f % 2 == 1):
        return f + 1
    return f


def _exact(v):
    """(numerator, denominator) of an int or a Fraction; anything else is refused."""
    if type(v) is int:
        return v, 1
    if type(v) is Fraction:
        return v.numerator, v.denominator
    raise Refusal("QUANTISE_INPUT", "%r is not an int or a Fraction" % (v,))


def quantise(values):
    """The set as integer coefficients: peak to COEFF_MAX, half to even.

    With m the largest magnitude in the set, each value v becomes the integer
    nearest v * COEFF_MAX / m, a tie going to the even one. Worked as one exact
    fraction per value. The result lies in -COEFF_MAX..COEFF_MAX: the rule
    never produces COEFF_MIN.
    """
    if not isinstance(values, (list, tuple)) or len(values) == 0:
        raise Refusal("QUANTISE_INPUT", "a set is a non-empty list or tuple")
    exact = [_exact(v) for v in values]
    peak_n, peak_d = 0, 1
    for n, d in exact:                 # the largest |n/d|, compared by cross-multiplying
        if abs(n) * peak_d > peak_n * d:
            peak_n, peak_d = abs(n), d
    if peak_n == 0:
        raise Refusal("QUANTISE_INPUT", "an all-zero set has no peak to scale")
    # v * COEFF_MAX / m  =  (n/d) * COEFF_MAX * (peak_d/peak_n)
    return tuple(round_half_even(n * C.COEFF_MAX * peak_d, d * peak_n) for n, d in exact)


# ------------------------------------------------------------------ the blob

def _is_int(v, lo, hi):
    return type(v) is int and lo <= v <= hi


def _check_scalars(rectifier, score_shift, pool):
    if type(rectifier) is not int or rectifier not in C.RECTIFIERS.values():
        raise Refusal("SHAPE_RECTIFIER", "rectifier code %r; declared: %s" % (rectifier, sorted(C.RECTIFIERS.items())))
    if not _is_int(score_shift, 0, C.MAX_SCORE_SHIFT):
        raise Refusal("SHAPE_SHIFT", "score_shift %r outside 0..%d" % (score_shift, C.MAX_SCORE_SHIFT))
    if not _is_int(pool, 1, C.MAX_POOL):
        raise Refusal("SHAPE_POOL", "pool %r outside 1..%d" % (pool, C.MAX_POOL))


def _check_weights(filters, head):
    for k, rows in enumerate(filters):
        for c in sorted(rows):
            for v in rows[c]:
                if not _is_int(v, C.COEFF_MIN, C.COEFF_MAX):
                    raise Refusal("WEIGHT_RANGE", "filter %d, channel %d: coefficient %r outside %d..%d"
                                  % (k, c, v, C.COEFF_MIN, C.COEFF_MAX))
    for k, v in enumerate(head):
        if not _is_int(v, C.COEFF_MIN, C.COEFF_MAX):
            raise Refusal("WEIGHT_RANGE", "head weight %d: %r outside %d..%d" % (k, v, C.COEFF_MIN, C.COEFF_MAX))


def pack(profile, filters, head, rectifier, pool, score_shift):
    """The blob for a configuration, or a refusal by name.

    `filters` is a list of K dicts; each maps a channel index to that
    channel's row of T coefficients, oldest sample first. `head` is K head
    weights. K, T and the channels each filter reads are taken from them.
    """
    prof = stream.profile(profile)
    if not isinstance(filters, (list, tuple)) or not 1 <= len(filters) <= C.MAX_FILTERS:
        raise Refusal("SHAPE_FILTERS", "a shape has 1..%d filters" % C.MAX_FILTERS)
    rows_total = 0
    for k, rows in enumerate(filters):
        if not isinstance(rows, dict) or len(rows) == 0:
            raise Refusal("SHAPE_CHANNEL", "filter %d reads no channel" % k)
        for c in rows:
            if not _is_int(c, 0, prof["channels"] - 1):
                raise Refusal("SHAPE_CHANNEL", "filter %d reads channel %r; the profile has %d" % (k, c, prof["channels"]))
        rows_total += len(rows)
    if rows_total > C.MAX_ROWS:
        raise Refusal("SHAPE_ROWS", "%d rows; a shape has at most %d" % (rows_total, C.MAX_ROWS))
    first = filters[0][min(filters[0])]
    if not isinstance(first, (list, tuple)) or not 1 <= len(first) <= C.MAX_TAPS:
        raise Refusal("SHAPE_TAPS", "a filter has 1..%d taps" % C.MAX_TAPS)
    taps = len(first)
    for k, rows in enumerate(filters):
        for c in sorted(rows):
            if not isinstance(rows[c], (list, tuple)) or len(rows[c]) != taps:
                raise Refusal("WEIGHT_COUNT", "filter %d, channel %d: a row is %d coefficients" % (k, c, taps))
    if not isinstance(head, (list, tuple)) or len(head) != len(filters):
        raise Refusal("WEIGHT_COUNT", "the head has one weight for each of the %d filters" % len(filters))
    _check_scalars(rectifier, score_shift, pool)
    _check_weights(filters, head)

    name = profile.encode("ascii")
    out = MAGIC + VERSION.to_bytes(2, "little") + len(name).to_bytes(1, "little") + name
    for value, (_field, nbytes) in zip((len(filters), taps, rectifier, score_shift, pool, 0), FIXED):
        out += value.to_bytes(nbytes, "little")
    for rows in filters:
        mask = 0
        for c in rows:
            mask |= 1 << c
        out += mask.to_bytes(MASK_BITS // 8, "little")
    for rows in filters:
        for c in sorted(rows):
            for v in rows[c]:
                out += v.to_bytes(WEIGHT_BYTES, "little", signed=True)
    for v in head:
        out += v.to_bytes(WEIGHT_BYTES, "little", signed=True)
    return out + hashlib.sha256(out).digest()


def unpack(blob):
    """The blob's parts, or a refusal by name.

    Returns a dict with exactly: profile, filters (a tuple of K dicts, channel
    to a tuple of T coefficients), head, rectifier, pool, score_shift, sha256
    (the blob's hash, in hex). The first six are `pack`'s arguments.
    """
    if not isinstance(blob, bytes) or len(blob) < SMALLEST:
        raise Refusal("BLOB_FORMAT", "a blob is bytes, at least %d of them" % SMALLEST)
    body, said = blob[:-HASH_BYTES], blob[-HASH_BYTES:]
    if hashlib.sha256(body).digest() != said:
        raise Refusal("BLOB_HASH", "the last %d bytes are not the SHA-256 of the rest" % HASH_BYTES)
    if body[:len(MAGIC)] != MAGIC or int.from_bytes(body[len(MAGIC):len(MAGIC) + 2], "little") != VERSION:
        raise Refusal("BLOB_FORMAT", "not a version %d blob" % VERSION)
    at = NAME_AT + body[NAME_AT - 1]
    if at + FIXED_BYTES > len(body):
        raise Refusal("BLOB_FORMAT", "the profile name runs past the end")
    try:
        profile = body[NAME_AT:at].decode("ascii")
    except UnicodeDecodeError:
        raise Refusal("PROFILE_UNKNOWN", repr(body[NAME_AT:at]))
    prof = stream.profile(profile)
    fixed = {}
    for field, nbytes in FIXED:
        fixed[field] = int.from_bytes(body[at:at + nbytes], "little")
        at += nbytes
    if fixed["reserved"] != 0:
        raise Refusal("RESERVED_BITS", "blob reserved field = 0x%08X" % fixed["reserved"])
    nfilters, taps = fixed["filters"], fixed["taps"]
    if not 1 <= nfilters <= C.MAX_FILTERS:
        raise Refusal("SHAPE_FILTERS", "%d filters; a shape has 1..%d" % (nfilters, C.MAX_FILTERS))
    if not 1 <= taps <= C.MAX_TAPS:
        raise Refusal("SHAPE_TAPS", "%d taps; a filter has 1..%d" % (taps, C.MAX_TAPS))
    _check_scalars(fixed["rectifier"], fixed["score_shift"], fixed["pool"])
    mask_bytes = MASK_BITS // 8
    if at + nfilters * mask_bytes > len(body):
        raise Refusal("BLOB_FORMAT", "the channel masks run past the end")
    reads, rows_total = [], 0
    for k in range(nfilters):
        mask = int.from_bytes(body[at:at + mask_bytes], "little")
        at += mask_bytes
        if mask == 0 or mask >> prof["channels"]:
            raise Refusal("SHAPE_CHANNEL", "filter %d: channel mask 0x%04X; the profile has %d channel(s)"
                          % (k, mask, prof["channels"]))
        reads.append([c for c in range(prof["channels"]) if mask >> c & 1])
        rows_total += len(reads[-1])
    if rows_total > C.MAX_ROWS:
        raise Refusal("SHAPE_ROWS", "%d rows; a shape has at most %d" % (rows_total, C.MAX_ROWS))
    if at + (rows_total * taps + nfilters) * WEIGHT_BYTES != len(body):
        raise Refusal("BLOB_FORMAT", "the length disagrees with the header")

    def word():
        nonlocal at
        at += WEIGHT_BYTES
        return int.from_bytes(body[at - WEIGHT_BYTES:at], "little", signed=True)

    filters = tuple({c: tuple(word() for _ in range(taps)) for c in channels} for channels in reads)
    head = tuple(word() for _ in range(nfilters))
    _check_weights(filters, head)
    return {"profile": profile, "filters": filters, "head": head, "rectifier": fixed["rectifier"],
            "pool": fixed["pool"], "score_shift": fixed["score_shift"], "sha256": said.hex()}


def shape(config):
    """What a swap may not change: everything in a configuration but the weights."""
    return (config["profile"], len(config["filters"]), len(config["filters"][0][min(config["filters"][0])]),
            tuple(tuple(sorted(rows)) for rows in config["filters"]),
            config["rectifier"], config["pool"], config["score_shift"])


def matched_filter(profile, pulse, gains):
    """The blob of the matched-filter configuration for a pulse.

    One filter; row c is gains[c] * pulse, IN ORDER (oldest sample first), for
    every channel whose gain is not zero; all of the filter's rows are one set
    for the quantising rule. The rectifier passes, the pool is 1, the shift is
    0 and the head weight is the integer 1, so the score is the filter's sum.
    A pulse whose first sample is at stream index j is fully under the filter
    at score index j + len(pulse) - 1.
    """
    prof = stream.profile(profile)
    if not isinstance(gains, (list, tuple)) or len(gains) != prof["channels"]:
        raise Refusal("CHANNELS", "one gain for each of the profile's %d channel(s)" % prof["channels"])
    if not isinstance(pulse, (list, tuple)) or not 1 <= len(pulse) <= C.MAX_TAPS:
        raise Refusal("SHAPE_TAPS", "a pulse of 1..%d samples" % C.MAX_TAPS)
    for v in tuple(gains) + tuple(pulse):
        _exact(v)
    read = [c for c in range(prof["channels"]) if gains[c] != 0]
    whole = quantise([gains[c] * p for c in read for p in pulse])
    rows = {c: whole[n * len(pulse):(n + 1) * len(pulse)] for n, c in enumerate(read)}
    return pack(profile, [rows], (1,), PASS, 1, 0)


# ----------------------------------------------------------------- the store

class Store:
    """The active weight set, the shadow, the epoch, and the swap.

    The swap is defined per output sample. `step()` is called once for each
    output, in order, and says which weights that output uses:

    - `commit(at)` schedules the swap at output index `at`: immediately
      before output `at`, active and shadow exchange and the epoch rises by
      one. Every output before `at` uses the old coefficients and the old
      head; every output from `at` on uses the new ones. No filter sum and no
      head sum mixes two sets.
    - The pool does mix them: with a pool of P, the outputs `at` to
      `at + P - 2` sum rectified values made under the old coefficients with
      values made under the new. `step()` reports those as settling. When
      P = 1, or `at` = 0, there are none.
    - A swap is PENDING from its commit until the last output it mixes has
      been produced. A commit while one is pending is refused, SWAP_PENDING,
      so no output mixes three sets. A shadow write is refused, SWAP_PENDING,
      between a commit and its index.
    - The shadow starts as a copy of the active set, and after a swap it holds
      the set that was active. A commit with no write since exchanges back.
    """

    def __init__(self, blob, epoch=0):
        self.config = unpack(blob)
        if not _is_int(epoch, 0, EPOCH_MAX):
            raise Refusal("SWAP_EPOCH", "start epoch %r outside 0..%d" % (epoch, EPOCH_MAX))
        self.shape = shape(self.config)
        self.pool = self.config["pool"]
        self.active = self._weights(self.config)
        self.shadow = self.active
        self.epoch = epoch
        self.next_index = 0
        self._at = None            # the index of a committed swap that has not happened yet
        self._mixed_until = -1     # the last output the latest swap mixes

    @staticmethod
    def _weights(config):
        return (tuple(tuple((c, rows[c]) for c in sorted(rows)) for rows in config["filters"]), config["head"])

    def pending(self):
        return self._at is not None or self.next_index <= self._mixed_until

    def write_shadow(self, blob):
        """Replace the whole shadow with the blob's weights."""
        if self._at is not None:
            raise Refusal("SWAP_PENDING", "a swap is committed at index %d; the shadow is what it will make active" % self._at)
        config = unpack(blob)
        if shape(config) != self.shape:
            raise Refusal("SWAP_SHAPE", "the blob's shape %r is not the running shape %r" % (shape(config), self.shape))
        self.shadow = self._weights(config)

    def commit(self, at):
        """Schedule the swap at output index `at`."""
        if self.pending():
            raise Refusal("SWAP_PENDING", "a swap is pending" + (
                " at index %d" % self._at if self._at is not None else ": outputs to index %d still mix" % self._mixed_until))
        if not _is_int(at, self.next_index, INDEX_MAX):
            raise Refusal("SWAP_INDEX", "commit at %r; the next output is index %d" % (at, self.next_index))
        if self.epoch + 1 > EPOCH_MAX:
            raise Refusal("SWAP_EPOCH", "the epoch is %d, the last its field holds" % self.epoch)
        self._at = at

    def step(self):
        """For the next output: (coefficient rows, head, epoch, settling)."""
        i = self.next_index
        if self._at == i:
            self.active, self.shadow = self.shadow, self.active
            self.epoch += 1
            self._mixed_until = i + self.pool - 2 if i >= 1 else -1
            self._at = None
        self.next_index = i + 1
        return self.active[0], self.active[1], self.epoch, i <= self._mixed_until

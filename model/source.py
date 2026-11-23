"""The source: a seeded noise generator, and recorded streams.

A source is an iterable of frames (`model.stream`). There are two: `Noise`,
which makes its stream from a seed, and `Replay`, which reads a recording.
Both are repeatable bit for bit, and both are integers from end to end: no
float, no `random`, no hash of an object, no dict order.

THE NOISE. Two steps, each defined by the arithmetic below and by nothing else.

  1. Words. SplitMix64 used as a counter: `word(seed, i)` is a function of
     the seed and the word index alone, so any word can be worked directly.
     Each of its steps is a bijection on 64-bit words, so over the 2^64
     indexes every 64-bit word occurs exactly once.

  2. A word to a sample. The law is the discrete Gaussian on the integers,
     P(X = k) proportional to exp(-k^2 / (2 sigma^2)), sigma = sigma_num /
     sigma_den >= 1. The word's low bit is the sign; its other 63 bits, u,
     are looked up in a table H, where H[m] is 2^63 * P(|X| <= m) rounded to
     the nearest integer; the magnitude is the number of entries H[m] <= u.
     Magnitude 0 takes both signs, so H[0] is P(X = 0) whole. The table ends
     at the first entry equal to 2^63: no sample is ever larger than that
     index, which is about 9.155 sigma.

  Frame n, channel c takes word n * channels + c. Every channel has the same
  sigma.

A RECORDING is a 56-byte header and the samples (`HEADER`, below). Every
field of it is checked before a frame is handed out.

Two outcomes only: the answer, or a `Refusal` by name. What is NOT a refusal:
a path that cannot be opened or written gets Python's own OSError, and
something that cannot be iterated where frames are expected gets Python's own
TypeError.
"""
import bisect
import hashlib

from spec import constants as C
from model import stream
from model.refusal import Refusal

# The word generator. These are SplitMix64's constants.
WORD_BITS = 64
WORD_MASK = (1 << WORD_BITS) - 1
GAMMA = 0x9E3779B97F4A7C15
MIX1 = 0xBF58476D1CE4E5B9
MIX2 = 0x94D049BB133111EB

# The table. A probability is a multiple of 2^-TABLE_BITS. WORK_BITS is the
# fixed point the table is built in; it is far wider than the table so that
# the building's own rounding does not reach an entry.
TABLE_BITS = 63
TABLE_ONE = 1 << TABLE_BITS
WORK_BITS = 192
WORK_ONE = 1 << WORK_BITS

# The recording's header: (field, bytes), in order, every integer little-endian
# and unsigned. The payload follows: frame by frame, channel by channel, each
# sample two's complement, little-endian, in the sample's bits rounded up to
# whole bytes.
MAGIC = b"UNDTSTRM"
FORMAT_VERSION = 1
HEADER = (("magic", 8), ("version", 2), ("sample_bits", 2), ("channels", 2),
          ("reserved", 2), ("frames", 8), ("sha256", 32))
HEADER_BYTES = sum(size for _name, size in HEADER)


def _words(seed, first, count):
    """Words first .. first + count - 1 of the seed's sequence, in order.

    The one place the word arithmetic is written. Word i is a function of the
    seed and of i + 1 alone.
    """
    for i in range(first + 1, first + count + 1):
        z = (seed + GAMMA * i) & WORD_MASK
        z = ((z ^ (z >> 30)) * MIX1) & WORD_MASK
        z = ((z ^ (z >> 27)) * MIX2) & WORD_MASK
        yield z ^ (z >> 31)


def _check_seed(seed):
    if type(seed) is not int or not 0 <= seed <= WORD_MASK:
        raise Refusal("SEED_RANGE", "seed %r is not an int from 0 to 2^%d - 1" % (seed, WORD_BITS))


def word(seed, i):
    """Word number i (from 0) of the seed's sequence: an int from 0 to 2^64 - 1."""
    _check_seed(seed)
    if type(i) is not int or not 0 <= i <= WORD_MASK:
        raise Refusal("STREAM_LENGTH", "word index %r is not an int from 0 to 2^%d - 1" % (i, WORD_BITS))
    for w in _words(seed, i, 1):
        return w


def _exp_neg(num, den):
    """exp(-num / den) in WORK_BITS fixed point, by its Taylor series.

    For 0 <= num / den <= 1/2, which is every sigma >= 1. Each term is the one
    before it times num / (den * n), floored.
    """
    total, term, n = WORK_ONE, WORK_ONE, 0
    while term:
        n += 1
        term = term * num // (den * n)
        total = total - term if n & 1 else total + term
    return total


def _weights(r):
    """w[m] = r^(m^2) in fixed point, for m = 0, 1, 2, ... until it is zero.

    Two multiplications a step: w[m + 1] = w[m] * q[m] and q[m + 1] = q[m] * r^2,
    with q[0] = r, so that q[m] = r^(2m + 1).
    """
    r2 = (r * r) >> WORK_BITS
    w, q = WORK_ONE, r
    while w:
        yield w
        w = (w * q) >> WORK_BITS
        q = (q * r2) >> WORK_BITS


def _nearest(num, den):
    """num / den to the nearest integer, a tie upward. num >= 0, den > 0."""
    return (2 * num + den) // (2 * den)


def _check_sigma(sigma_num, sigma_den):
    for v in (sigma_num, sigma_den):
        if type(v) is not int:
            raise Refusal("NOISE_SIGMA", "sigma %r / %r is not a ratio of two ints" % (sigma_num, sigma_den))
    if sigma_den < 1 or sigma_num < sigma_den:
        raise Refusal("NOISE_SIGMA", "sigma %d / %d is not at least 1 with a denominator of at least 1"
                      % (sigma_num, sigma_den))


def gaussian_table(sigma_num, sigma_den, largest=None):
    """The half table H for sigma = sigma_num / sigma_den, as a tuple of ints.

    H[m] = round(2^63 * P(|X| <= m)) for the discrete Gaussian, a tie upward;
    the last entry is the first that equals 2^63, and its index is the largest
    magnitude a sample can have.

    `largest` is the largest magnitude the caller can hold: a table that needs
    an entry past it is refused as NOISE_RANGE, without being built to its
    end. Left out, it is the largest sample any declared profile holds, so a
    table no profile could use is never built. The last magnitude is above
    8 sigma at every sigma >= 1 (the two-sided tail at 8 sigma is about
    1.2e-15, and the table runs until it is below 2^-64), so a sigma above an
    eighth of `largest` is refused before anything is built.
    """
    _check_sigma(sigma_num, sigma_den)
    if largest is None:
        largest = max(p["sample_max"] for p in C.PROFILES.values())
    if sigma_num * 8 > largest * sigma_den:
        raise Refusal("NOISE_RANGE", "sigma %d / %d: its table runs past 8 sigma, which is past %d"
                      % (sigma_num, sigma_den, largest))
    r = _exp_neg(sigma_den * sigma_den, 2 * sigma_num * sigma_num)
    total = 2 * sum(_weights(r)) - WORK_ONE          # w[0] once, every other weight twice
    table, acc = [], -WORK_ONE
    for m, w in enumerate(_weights(r)):
        if m > largest:
            raise Refusal("NOISE_RANGE", "sigma %d / %d: its table needs a magnitude past %d"
                          % (sigma_num, sigma_den, largest))
        acc += 2 * w                                  # w[0] + 2 * (w[1] + .. + w[m])
        h = _nearest(acc << TABLE_BITS, total)
        table.append(h)
        if h == TABLE_ONE:
            break
    return tuple(table)


def table_variance(table):
    """The variance of the law a table gives, exactly: (numerator, denominator), two ints.

    P(|X| = m) is (H[m] - H[m - 1]) / 2^63 and the mean is exactly zero (the
    sign is one bit of the word), so the variance is the sum of m^2 P(|X| = m).
    It is sigma^2 to within 2.2e-7 at sigma = 1 and far closer above.
    """
    num, below = 0, 0
    for m, h in enumerate(table):
        num += m * m * (h - below)
        below = h
    return num, TABLE_ONE


class Noise:
    """Seeded noise: an iterable of `frames` frames, the same every time it is iterated.

    Refused before any frame, in this order: a profile that is not declared
    (PROFILE_UNKNOWN); a seed that is not an int from 0 to 2^64 - 1
    (SEED_RANGE); a sigma that is not two ints with sigma_num >= sigma_den >= 1
    (NOISE_SIGMA); a frame count that is not an int >= 0, or that needs more
    than the generator's 2^64 words (STREAM_LENGTH); a sigma whose table does
    not fit the profile's sample range (NOISE_RANGE).
    """

    def __init__(self, profile_name, seed, sigma_num, sigma_den, frames):
        self.profile = stream.profile(profile_name)
        _check_seed(seed)
        _check_sigma(sigma_num, sigma_den)
        channels = self.profile["channels"]
        if type(frames) is not int or frames < 0 or frames * channels > WORD_MASK + 1:
            raise Refusal("STREAM_LENGTH", "%r frames of %d channel(s) is not a count the generator's 2^%d words hold"
                          % (frames, channels, WORD_BITS))
        self.seed = seed
        self.sigma = (sigma_num, sigma_den)
        self.frames = frames
        self.table = gaussian_table(sigma_num, sigma_den, self.profile["sample_max"])

    def words(self, first, count):
        """Words first .. first + count - 1 of this source's sequence, in order.

        Frame n, channel c is made from word n * channels + c. Every sample the
        source yields is made from a word that came through here, by the lookup
        in `_samples`: a test that feeds chosen words through a subclass's
        `words` is testing the path every real frame takes.
        """
        return _words(self.seed, first, count)

    def _samples(self, first_word, count):
        """One sample for each word: the word's low bit is the sign; its other
        63 bits are looked up in the table, and the magnitude is how many
        entries are at or below them."""
        lookup, table = bisect.bisect_right, self.table
        for w in self.words(first_word, count):
            m = lookup(table, w >> 1)
            yield -m if w & 1 else m

    def from_frame(self, first):
        """The frames from number `first` to the last, worked directly from the seed."""
        if type(first) is not int or not 0 <= first <= self.frames:
            raise Refusal("STREAM_LENGTH", "frame %r is not one of this source's %d" % (first, self.frames))
        channels = self.profile["channels"]
        samples = self._samples(first * channels, (self.frames - first) * channels)
        # A frame is the next `channels` samples: zip takes one from the same
        # iterator for each channel in turn, and makes a plain tuple of them.
        return zip(*[samples] * channels)

    def __iter__(self):
        return self.from_frame(0)


def _sample_bytes(prof):
    return (prof["sample_bits"] + 7) // 8


def stream_bytes(profile_name, frames):
    """A stream's canonical bytes: the payload of a recording of it.

    Frame by frame, channel by channel, each sample two's complement,
    little-endian. Two streams are equal when these bytes are equal. Every
    frame is checked on the way (CHANNELS, SAMPLE_RANGE).
    """
    prof = stream.profile(profile_name)
    size = _sample_bytes(prof)
    out = bytearray()
    for frame in frames:
        stream.check_frame(prof, frame)
        for v in frame:
            out += v.to_bytes(size, "little", signed=True)
    return bytes(out)


def recording(profile_name, frames):
    """The bytes of a recording of the stream: the header, then `stream_bytes`."""
    prof = stream.profile(profile_name)
    payload = stream_bytes(profile_name, frames)
    count = len(payload) // (_sample_bytes(prof) * prof["channels"])
    values = {"magic": MAGIC, "version": FORMAT_VERSION, "sample_bits": prof["sample_bits"],
              "channels": prof["channels"], "reserved": 0, "frames": count,
              "sha256": hashlib.sha256(payload).digest()}
    out = bytearray()
    for name, size in HEADER:
        v = values[name]
        out += v if isinstance(v, bytes) else v.to_bytes(size, "little")
    return bytes(out) + payload


def parse_recording(profile_name, data):
    """The frames of a recording, as a tuple, or a refusal by name.

    Checked in this order, all of it before any frame is returned:
      fewer bytes than a header, a first field that is not the magic, or a
      version that is not 1                                   REPLAY_FORMAT
      a reserved field that is not zero                       RESERVED_BITS
      sample bits or channels that are not the profile's      REPLAY_PROFILE
      a payload that is not frames * channels * sample bytes  REPLAY_FORMAT
      a payload whose SHA-256 is not the header's             REPLAY_HASH
      a sample outside the profile's range                    SAMPLE_RANGE
    """
    prof = stream.profile(profile_name)
    if not isinstance(data, (bytes, bytearray)):
        raise Refusal("REPLAY_FORMAT", "a recording is bytes, not %s" % type(data).__name__)
    data = bytes(data)
    if len(data) < HEADER_BYTES:
        raise Refusal("REPLAY_FORMAT", "%d bytes is shorter than the %d-byte header" % (len(data), HEADER_BYTES))
    field, at = {}, 0
    for name, size in HEADER:
        raw = data[at:at + size]
        field[name] = raw if name in ("magic", "sha256") else int.from_bytes(raw, "little")
        at += size
    if field["magic"] != MAGIC:
        raise Refusal("REPLAY_FORMAT", "the first %d bytes are not %r" % (len(MAGIC), MAGIC))
    if field["version"] != FORMAT_VERSION:
        raise Refusal("REPLAY_FORMAT", "format version %d, this model reads %d" % (field["version"], FORMAT_VERSION))
    if field["reserved"] != 0:
        raise Refusal("RESERVED_BITS", "recording header reserved = 0x%04X" % field["reserved"])
    if (field["sample_bits"], field["channels"]) != (prof["sample_bits"], prof["channels"]):
        raise Refusal("REPLAY_PROFILE", "the recording is %d bits on %d channel(s), profile %s is %d on %d"
                      % (field["sample_bits"], field["channels"], profile_name,
                         prof["sample_bits"], prof["channels"]))
    size, channels = _sample_bytes(prof), prof["channels"]
    payload = data[HEADER_BYTES:]
    if len(payload) != field["frames"] * channels * size:
        raise Refusal("REPLAY_FORMAT", "the header says %d frames, which is %d payload bytes; there are %d"
                      % (field["frames"], field["frames"] * channels * size, len(payload)))
    if hashlib.sha256(payload).digest() != field["sha256"]:
        raise Refusal("REPLAY_HASH", "the payload's SHA-256 is not the header's")
    frames = []
    for at in range(0, len(payload), channels * size):
        frame = tuple([int.from_bytes(payload[at + c * size:at + (c + 1) * size], "little", signed=True)
                       for c in range(channels)])
        frames.append(stream.check_frame(prof, frame))
    return tuple(frames)


def record(profile_name, frames, path):
    """Write a recording of the stream to `path`. Returns how many frames it holds."""
    data = recording(profile_name, frames)
    prof = stream.profile(profile_name)
    with open(path, "wb") as f:
        f.write(data)
    return (len(data) - HEADER_BYTES) // (_sample_bytes(prof) * prof["channels"])


class Replay:
    """A recorded stream: an iterable of its frames, the same every time.

    The whole file is read and checked when the object is made
    (`parse_recording`), so a recording that is refused hands out no frame.
    """

    def __init__(self, profile_name, path):
        self.profile = stream.profile(profile_name)
        with open(path, "rb") as f:
            data = f.read()
        self._frames = parse_recording(profile_name, data)
        self.frames = len(self._frames)

    def __iter__(self):
        return iter(self._frames)

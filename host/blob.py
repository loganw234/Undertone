"""The library's own reader of a configuration blob, and the words it writes from one.

THIS IS A SECOND READER, ON PURPOSE. The model has one (`model.weights.unpack`)
and the comparison runs the model on the blob. If the library took its words
from that same function, a fault in it would pass both sides. So this file
reads the format again from its description (the docstring of
model/weights.py: blob versions 1 and 2), and imports nothing of `model/` but
the refusal. tests/test_host_blob.py holds the two readers equal on seeded
blobs of both profiles and both versions, and on one malformed blob for each
refusal; a reader made wrong in one place inside that test is reported.

`read(blob)` refuses, in `unpack`'s order and by its names: BLOB_FORMAT (not
bytes, or too short), BLOB_HASH, BLOB_FORMAT (magic, version, a name past the
end), PROFILE_UNKNOWN, RESERVED_BITS (version 1) or BLOB_FORMAT (version 2
with no unit), SHAPE_FILTERS, SHAPE_TAPS, SHAPE_RECTIFIER, SHAPE_SHIFT,
SHAPE_POOL, then for version 2 SHAPE_HIDDEN, SHAPE_HIDDEN_SHIFT,
SHAPE_BETWEEN, then BLOB_FORMAT (masks past the end), SHAPE_CHANNEL,
SHAPE_ROWS, BLOB_FORMAT (a length the header does not give), WEIGHT_RANGE.

`against(config, identity)` refuses what the BUILD cannot take, from its
capability registers, in the core's own order (docs/rtl/core.md, section 7),
with one name the core's chain has not: BLOB_FORMAT when `cap_blob_versions`
lacks the blob's version, placed after PROFILE_UNKNOWN (HOST's decision).

WHAT IT CANNOT SEE: a blob both readers get wrong the same way; the format is
the model's, written twice, and the test holds the two on the blobs it makes.
"""
import hashlib

from spec import constants as C
from model.refusal import Refusal

MAGIC = b"UNDTBLOB"
VERSION_PLAIN, VERSION_HIDDEN = 1, 2
HASH_BYTES = 32
WEIGHT_BYTES = 4
MASK_BYTES = 2
NAME_AT = len(MAGIC) + 2 + 1
# The fixed fields after the name, (name, bytes): version 1, and version 2 where the reserved word holds the layer.
FIXED_PLAIN = (("filters", 2), ("taps", 2), ("rectifier", 1), ("score_shift", 1), ("pool", 4), ("reserved", 4))
FIXED_HIDDEN = FIXED_PLAIN[:-1] + (("hidden", 2), ("hidden_shift", 1), ("between", 1))
FIXED_BYTES = sum(n for _f, n in FIXED_PLAIN)
SMALLEST = NAME_AT + FIXED_BYTES + HASH_BYTES
CODES = set(C.RECTIFIERS.values())


def _u(data, at, n):
    return int.from_bytes(data[at:at + n], "little")


def _within(v, lo, hi):
    return lo <= v <= hi


def read(blob):
    """The blob's configuration, in the form `model.weights.unpack` gives, or a refusal by name.

    Keys: profile, filters (a tuple of dicts, channel to a tuple of coefficients, oldest first), head,
    rectifier, pool, score_shift, sha256; and for version 2 hidden, hidden_shift, between.
    """
    if not isinstance(blob, bytes) or len(blob) < SMALLEST:
        raise Refusal("BLOB_FORMAT", "a blob is bytes, at least %d of them" % SMALLEST)
    body, said = blob[:-HASH_BYTES], blob[-HASH_BYTES:]
    if hashlib.sha256(body).digest() != said:
        raise Refusal("BLOB_HASH", "the last %d bytes are not the SHA-256 of the rest" % HASH_BYTES)
    version = _u(body, len(MAGIC), 2)
    if body[:len(MAGIC)] != MAGIC or version not in (VERSION_PLAIN, VERSION_HIDDEN):
        raise Refusal("BLOB_FORMAT", "not a blob of version %d or %d" % (VERSION_PLAIN, VERSION_HIDDEN))
    at = NAME_AT + body[NAME_AT - 1]
    if at + FIXED_BYTES > len(body):
        raise Refusal("BLOB_FORMAT", "the profile's name runs past the end")
    try:
        profile = body[NAME_AT:at].decode("ascii")
    except UnicodeDecodeError:
        raise Refusal("PROFILE_UNKNOWN", repr(body[NAME_AT:at]))
    if profile not in C.PROFILES:
        raise Refusal("PROFILE_UNKNOWN", repr(profile))
    channels = C.PROFILES[profile]["channels"]
    fixed = {}
    for field, n in (FIXED_PLAIN if version == VERSION_PLAIN else FIXED_HIDDEN):
        fixed[field] = _u(body, at, n)
        at += n
    if version == VERSION_PLAIN:
        if fixed["reserved"] != 0:
            raise Refusal("RESERVED_BITS", "the reserved word is 0x%08X" % fixed["reserved"])
        units = 0
    else:
        units = fixed["hidden"]
        if units == 0:
            raise Refusal("BLOB_FORMAT", "a version %d blob with no hidden unit" % VERSION_HIDDEN)
    k, taps = fixed["filters"], fixed["taps"]
    if not _within(k, 1, C.MAX_FILTERS):
        raise Refusal("SHAPE_FILTERS", "%d filters" % k)
    if not _within(taps, 1, C.MAX_TAPS):
        raise Refusal("SHAPE_TAPS", "%d taps" % taps)
    if fixed["rectifier"] not in CODES:
        raise Refusal("SHAPE_RECTIFIER", "rectifier code %d" % fixed["rectifier"])
    if not _within(fixed["score_shift"], 0, C.MAX_SCORE_SHIFT):
        raise Refusal("SHAPE_SHIFT", "score shift %d" % fixed["score_shift"])
    if not _within(fixed["pool"], 1, C.MAX_POOL):
        raise Refusal("SHAPE_POOL", "pool %d" % fixed["pool"])
    if units:
        if units > C.MAX_HIDDEN:
            raise Refusal("SHAPE_HIDDEN", "%d hidden units" % units)
        if not _within(fixed["hidden_shift"], 0, C.MAX_HIDDEN_SHIFT):
            raise Refusal("SHAPE_HIDDEN_SHIFT", "hidden shift %d" % fixed["hidden_shift"])
        if fixed["between"] not in CODES:
            raise Refusal("SHAPE_BETWEEN", "between code %d" % fixed["between"])
    if at + k * MASK_BYTES > len(body):
        raise Refusal("BLOB_FORMAT", "the channel masks run past the end")
    reads, rows = [], 0
    for f in range(k):
        mask = _u(body, at, MASK_BYTES)
        at += MASK_BYTES
        if mask == 0 or mask >> channels:
            raise Refusal("SHAPE_CHANNEL", "filter %d's mask 0x%04X under %d channel(s)" % (f, mask, channels))
        reads.append([c for c in range(channels) if mask >> c & 1])
        rows += len(reads[-1])
    if rows > C.MAX_ROWS:
        raise Refusal("SHAPE_ROWS", "%d rows" % rows)
    heads = units if units else k
    if at + (rows * taps + units * k + heads) * WEIGHT_BYTES != len(body):
        raise Refusal("BLOB_FORMAT", "the length is not the one the header gives")
    values = [int.from_bytes(body[i:i + WEIGHT_BYTES], "little", signed=True)
              for i in range(at, len(body), WEIGHT_BYTES)]
    for v in values:
        if not _within(v, C.COEFF_MIN, C.COEFF_MAX):
            raise Refusal("WEIGHT_RANGE", "a weight of %d" % v)
    n = 0
    filters = []
    for chans in reads:
        rows_of = {}
        for c in chans:
            rows_of[c] = tuple(values[n:n + taps])
            n += taps
        filters.append(rows_of)
    hidden = []
    for _j in range(units):
        hidden.append(tuple(values[n:n + k]))
        n += k
    head = tuple(values[n:n + heads])
    config = {"profile": profile, "filters": tuple(filters), "head": head, "rectifier": fixed["rectifier"],
              "pool": fixed["pool"], "score_shift": fixed["score_shift"], "sha256": said.hex()}
    if units:
        config.update(hidden=tuple(hidden), hidden_shift=fixed["hidden_shift"], between=fixed["between"])
    return config


def version(config):
    return VERSION_HIDDEN if "hidden" in config else VERSION_PLAIN


def taps(config):
    first = config["filters"][0]
    return len(first[min(first)])


def rows(config):
    return sum(len(f) for f in config["filters"])


def shape(config):
    """Everything a swap may not change: all but the weights."""
    out = (config["profile"], len(config["filters"]), taps(config), tuple(tuple(sorted(f)) for f in config["filters"]),
           config["rectifier"], config["pool"], config["score_shift"])
    if "hidden" in config:
        out += (len(config["hidden"]), config["hidden_shift"], config["between"])
    return out


def words(config):
    """The weight words in the blob's order: each filter's rows by channel, the hidden units, the head."""
    out = []
    for f in config["filters"]:
        for c in sorted(f):
            out.extend(f[c])
    for unit in config.get("hidden", ()):
        out.extend(unit)
    out.extend(config["head"])
    return out


def shape_scalars(config):
    """The core's ten shape registers, by name, in the order the library writes them."""
    prof = C.PROFILES[config["profile"]]
    return (("shape_sample_bits", prof["sample_bits"]), ("shape_channels", prof["channels"]),
            ("shape_filters", len(config["filters"])), ("shape_taps", taps(config)),
            ("shape_rectifier", config["rectifier"]), ("shape_score_shift", config["score_shift"]),
            ("shape_pool", config["pool"]), ("shape_hidden", len(config.get("hidden", ()))),
            ("shape_hidden_shift", config.get("hidden_shift", 0)), ("shape_between", config.get("between", 0)))


def masks(config):
    return [sum(1 << c for c in f) for f in config["filters"]]


def against(config, identity):
    """Refuse, by the bound's name, a configuration the build's capability registers say it cannot take."""
    caps = identity["caps"]
    if config["profile"] != identity["profile"]:
        raise Refusal("PROFILE_UNKNOWN", "the blob is %s and the build is %s" % (config["profile"], identity["profile"]))
    if not caps["cap_blob_versions"] >> version(config) & 1:
        raise Refusal("BLOB_FORMAT", "the build takes no version %d blob (cap_blob_versions 0x%X)"
                      % (version(config), caps["cap_blob_versions"]))
    bounds = (
        ("SHAPE_FILTERS", len(config["filters"]), caps["cap_filters"], "filters"),
        ("SHAPE_TAPS", taps(config), caps["cap_taps"], "taps"),
    )
    for name, have, most, what in bounds:
        if have > most:
            raise Refusal(name, "%d %s; the build holds %d" % (have, what, most))
    if not caps["cap_rectifiers"] >> config["rectifier"] & 1:
        raise Refusal("SHAPE_RECTIFIER", "rectifier code %d; the build's are 0x%X" % (config["rectifier"], caps["cap_rectifiers"]))
    later = (
        ("SHAPE_SHIFT", config["score_shift"], caps["cap_score_shift"], "for the score shift"),
        ("SHAPE_POOL", config["pool"], caps["cap_pool"], "for the pool"),
        ("SHAPE_HIDDEN", len(config.get("hidden", ())), caps["cap_hidden"], "hidden units"),
        ("SHAPE_HIDDEN_SHIFT", config.get("hidden_shift", 0), caps["cap_hidden_shift"], "for the hidden shift"),
    )
    for name, have, most, what in later:
        if have > most:
            raise Refusal(name, "%d %s; the build holds %d" % (have, what, most))
    if "hidden" in config and not caps["cap_rectifiers"] >> config["between"] & 1:
        raise Refusal("SHAPE_BETWEEN", "between code %d; the build's are 0x%X" % (config["between"], caps["cap_rectifiers"]))
    if rows(config) > caps["cap_rows"]:
        raise Refusal("SHAPE_ROWS", "%d rows; the build holds %d" % (rows(config), caps["cap_rows"]))

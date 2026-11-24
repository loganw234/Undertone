"""The library's own blob reader agrees with the model's, and refuses what it refuses, by the same name.

WHAT THIS HOLDS. `host.blob.read`, code of the library's that imports nothing
of the model's reader, gives the configuration `model.weights.unpack` gives on
seeded blobs of both profiles and both versions, and `host.blob.words` the
weight words in the blob's order. On a malformed blob for each refusal
`unpack` names, the library's reader refuses with the same name. Two codes that
agree on these blobs; a format both read wrongly the same way is not seen.

ITS CONTROL. A reader that takes one row newest first, made here, is reported
on every seeded blob whose first row is not its own reverse.
"""
import hashlib
import random

from spec import constants as C
from model import weights
from model.refusal import Refusal

from host import blob as B

SEED = 2026112402


def weight(rng):
    return rng.choice([C.COEFF_MIN, C.COEFF_MAX, 0, -1, 1, rng.randint(C.COEFF_MIN, C.COEFF_MAX)])


def seeded_blob(rng, profile):
    channels = C.PROFILES[profile]["channels"]
    while True:
        k = rng.randint(1, C.MAX_FILTERS)
        sets = [sorted(rng.sample(range(channels), rng.randint(1, channels))) for _ in range(k)]
        if sum(len(s) for s in sets) <= C.MAX_ROWS:
            break
    taps = rng.choice([1, 2, 7, 64, C.MAX_TAPS])
    filters = [dict((c, [weight(rng) for _ in range(taps)]) for c in s) for s in sets]
    rect = rng.choice(sorted(C.RECTIFIERS.values()))
    pool, shift = rng.choice([1, 2, 5, C.MAX_POOL]), rng.randint(0, C.MAX_SCORE_SHIFT)
    hidden = rng.choice([0, 1, 3, C.MAX_HIDDEN])
    if hidden == 0:
        return weights.pack(profile, filters, [weight(rng) for _ in sets], rect, pool, shift)
    units = [[weight(rng) for _ in sets] for _ in range(hidden)]
    return weights.pack(profile, filters, [weight(rng) for _ in range(hidden)], rect, pool, shift, units,
                        rng.randint(0, C.MAX_HIDDEN_SHIFT), rng.choice(sorted(C.RECTIFIERS.values())))


def model_words(config):
    out = []
    for f in config["filters"]:
        for c in sorted(f):
            out += list(f[c])
    for unit in config.get("hidden", ()):
        out += list(unit)
    return out + list(config["head"])


def blobs():
    rng = random.Random(SEED)
    return [seeded_blob(rng, profile) for profile in sorted(C.PROFILES) for _ in range(40)]


def differs(reader, blob):
    """None when the reader agrees with the model's on this blob; else what differs."""
    mine, theirs = reader(blob), weights.unpack(blob)
    if mine != theirs:
        return sorted(k for k in set(mine) | set(theirs) if mine.get(k) != theirs.get(k))
    if B.words(mine) != model_words(theirs):
        return ["words"]
    return None


def test_host_blob_reads_as_the_model_reads():
    seen = set()
    for blob in blobs():
        assert differs(B.read, blob) is None
        config = B.read(blob)
        seen.add((config["profile"], B.version(config)))
    assert seen == {(p, v) for p in C.PROFILES for v in (1, 2)}


def test_host_blob_shape_is_the_models():
    for blob in blobs():
        assert B.shape(B.read(blob)) == weights.shape(weights.unpack(blob))


def test_host_blob_control_a_row_read_newest_first_is_reported():
    def newest_first(blob):
        config = B.read(blob)
        first = config["filters"][0]
        c = min(first)
        flipped = dict(first)
        flipped[c] = tuple(reversed(first[c]))
        return dict(config, filters=(flipped,) + tuple(config["filters"][1:]))
    reported = checked = 0
    for blob in blobs():
        row = weights.unpack(blob)["filters"][0]
        row = row[min(row)]
        if tuple(row) == tuple(reversed(row)):
            continue
        checked += 1
        reported += differs(newest_first, blob) == ["filters"]
    assert checked > 40 and reported == checked


# ------------------------------------------------------------------ malformed blobs, one a refusal

def rehash(body):
    return body + hashlib.sha256(body).digest()


def patched(blob, at, data):
    body = bytearray(blob[:-32])
    body[at:at + len(data)] = data
    return rehash(bytes(body))


def plain_blob(profile="s16x1", taps=3, filters=None):
    filters = filters or [{0: [1, -2, 3][:taps] + [0] * max(0, taps - 3)}]
    return weights.pack(profile, filters, [1] * len(filters), 0, 1, 0)


def hidden_blob():
    return weights.pack("s16x1", [{0: [1, 2]}], [5], 0, 1, 0, [[3]], 2, 1)


NAME = 11                                     # where the profile's name starts
FIXED = NAME + len("s16x1")                   # its fixed fields, for a blob of s16x1
F_FILTERS, F_TAPS, F_RECT, F_SHIFT, F_POOL, F_LAST = FIXED, FIXED + 2, FIXED + 4, FIXED + 5, FIXED + 6, FIXED + 10
MASKS = FIXED + 14


def cases():
    p, h = plain_blob(), hidden_blob()
    wide = weights.pack("s24x3", [{0: [1], 1: [2]} for _ in range(6)], [1] * 6, 0, 1, 0)
    yield "BLOB_FORMAT", bytearray(p)
    yield "BLOB_FORMAT", p[:56]
    yield "BLOB_HASH", p[:-1] + bytes([p[-1] ^ 1])
    yield "BLOB_FORMAT", patched(p, 0, b"X")
    yield "BLOB_FORMAT", patched(p, 8, (3).to_bytes(2, "little"))
    yield "BLOB_FORMAT", patched(p, 10, bytes([200]))
    yield "PROFILE_UNKNOWN", patched(p, NAME, b"\xff")
    yield "PROFILE_UNKNOWN", patched(p, NAME, b"s17x1")
    yield "RESERVED_BITS", patched(p, F_LAST, b"\x01")
    yield "BLOB_FORMAT", patched(h, F_LAST, b"\x00\x00")
    yield "SHAPE_FILTERS", patched(p, F_FILTERS, (0).to_bytes(2, "little"))
    yield "SHAPE_FILTERS", patched(p, F_FILTERS, (C.MAX_FILTERS + 1).to_bytes(2, "little"))
    yield "SHAPE_TAPS", patched(p, F_TAPS, (0).to_bytes(2, "little"))
    yield "SHAPE_TAPS", patched(p, F_TAPS, (C.MAX_TAPS + 1).to_bytes(2, "little"))
    yield "SHAPE_RECTIFIER", patched(p, F_RECT, bytes([9]))
    yield "SHAPE_SHIFT", patched(p, F_SHIFT, bytes([C.MAX_SCORE_SHIFT + 1]))
    yield "SHAPE_POOL", patched(p, F_POOL, (0).to_bytes(4, "little"))
    yield "SHAPE_POOL", patched(p, F_POOL, (C.MAX_POOL + 1).to_bytes(4, "little"))
    yield "SHAPE_HIDDEN", patched(h, F_LAST, (C.MAX_HIDDEN + 1).to_bytes(2, "little"))
    yield "SHAPE_HIDDEN_SHIFT", patched(h, F_LAST + 2, bytes([C.MAX_HIDDEN_SHIFT + 1]))
    yield "SHAPE_BETWEEN", patched(h, F_LAST + 3, bytes([7]))
    yield "BLOB_FORMAT", rehash(p[:MASKS + 1])
    yield "SHAPE_CHANNEL", patched(p, MASKS, (0).to_bytes(2, "little"))
    yield "SHAPE_CHANNEL", patched(p, MASKS, (2).to_bytes(2, "little"))
    yield "SHAPE_ROWS", patched(wide, NAME + 5 + 14, b"".join((7).to_bytes(2, "little") for _ in range(6)))
    yield "BLOB_FORMAT", rehash(p[:-32] + bytes(4))
    yield "WEIGHT_RANGE", patched(p, MASKS + 2, (C.COEFF_MAX + 1).to_bytes(4, "little", signed=True))
    yield "WEIGHT_RANGE", patched(h, len(h) - 32 - 4, (C.COEFF_MIN - 1).to_bytes(4, "little", signed=True))


def refused(reader, blob):
    try:
        reader(blob)
    except Refusal as e:
        return e.name
    return None


def test_host_blob_refuses_by_the_models_names():
    names = []
    for want, blob in cases():
        assert refused(weights.unpack, blob) == want, ("the model's", want)
        assert refused(B.read, blob) == want, ("the library's", want)
        names.append(want)
    assert set(names) == {"BLOB_FORMAT", "BLOB_HASH", "PROFILE_UNKNOWN", "RESERVED_BITS", "SHAPE_FILTERS",
                          "SHAPE_TAPS", "SHAPE_RECTIFIER", "SHAPE_SHIFT", "SHAPE_POOL", "SHAPE_HIDDEN",
                          "SHAPE_HIDDEN_SHIFT", "SHAPE_BETWEEN", "SHAPE_CHANNEL", "SHAPE_ROWS", "WEIGHT_RANGE"}

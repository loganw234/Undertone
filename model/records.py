"""Records, and the one way to turn them into bytes.

A record is a dict with exactly the field names its format declares in
`spec.constants.RECORDS`, each value a Python int that fits the field. The
three kinds are "score" (one per input sample), "truth" (one per injection;
it goes around the detector) and "event".

`pack` gives a record's canonical bytes: its fields in declared order, each
little-endian, two's complement where signed, a whole number of bytes wide.

`digest` hashes a sequence of records of one kind. What is hashed is a prefix
that names the kind, then each record's canonical bytes in order: so two
sequences of different kinds never share a digest by the accident of their
bytes being equal, and an empty sequence of one kind differs from an empty
sequence of another. Bit-identity between two producers of records is the
equality of the digest AND of the count, never of a rounded or thresholded
view of the records.

For a kind and for a record there are two outcomes only: the answer, or a
`Refusal` with a declared name. A kind that is not one of the three is refused
as RECORD_KIND whatever its type, and before anything else is looked at. A
record that does not fit is refused by `check`, by `pack` and by `digest`
alike. What `digest` is handed must be something Python can iterate: a caller
who passes a number gets Python's own TypeError, not a refusal.
"""
import hashlib

from spec import constants as C
from model.refusal import Refusal

DIGEST_PREFIX = b"undertone-records\x00"


def fields(kind):
    """The kind's declared fields, or a refusal by name."""
    if type(kind) is not str or kind not in C.RECORDS:
        raise Refusal("RECORD_KIND", repr(kind))
    return C.RECORDS[kind]


def check(kind, record):
    """Return the record unchanged, or refuse it by name."""
    declared = fields(kind)
    if not isinstance(record, dict) or set(record) != {f[0] for f in declared}:
        raise Refusal("RECORD_FIELD", "%s record needs exactly the fields %s"
                      % (kind, ", ".join(f[0] for f in declared)))
    for name, bits, sign in declared:
        v = record[name]
        lo, hi = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if sign == "signed" else (0, (1 << bits) - 1)
        if type(v) is not int or not lo <= v <= hi:
            raise Refusal("RECORD_FIELD", "%s.%s = %r does not fit %d %s bits" % (kind, name, v, bits, sign))
    if kind == "score" and record["flags"] & C.FLAGS_RESERVED_MASK:
        raise Refusal("RESERVED_BITS", "score.flags = 0x%02X" % record["flags"])
    if kind == "truth" and record["amplitude_den"] == 0:
        raise Refusal("RECORD_FIELD", "truth.amplitude_den = 0: an amplitude is a ratio and its denominator is not zero")
    return record


def pack(kind, record):
    """The record's canonical bytes."""
    check(kind, record)
    out = b""
    for name, bits, sign in fields(kind):
        out += record[name].to_bytes(bits // 8, "little", signed=(sign == "signed"))
    return out


def digest(kind, records):
    """(SHA-256 in hex, how many records) for a sequence of records of one kind.

    The kind is refused first if it is not declared, even for an empty sequence.
    """
    fields(kind)
    h, n = hashlib.sha256(DIGEST_PREFIX + kind.encode("ascii") + b"\x00"), 0
    for r in records:
        h.update(pack(kind, r))
        n += 1
    return h.hexdigest(), n

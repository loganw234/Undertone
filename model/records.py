"""Records, and the one way to turn them into bytes.

A record is a dict with exactly the field names its format declares in
`spec.constants.RECORDS`, each value a Python int that fits the field. The
three kinds are "score" (one per input sample), "truth" (one per injection;
it goes around the detector) and "event".

`pack` gives a record's canonical bytes: its fields in declared order, each
little-endian, two's complement where signed, a whole number of bytes wide.
`digest` hashes a sequence of records. Bit-identity between two producers of
records is the equality of these bytes, never of a rounded or thresholded view
of them.
"""
import hashlib

from spec import constants as C
from model.refusal import Refusal


def check(kind, record):
    """Return the record unchanged, or refuse it by name."""
    if kind not in C.RECORDS:
        raise Refusal("RECORD_KIND", repr(kind))
    fields = C.RECORDS[kind]
    if not isinstance(record, dict) or set(record) != {f[0] for f in fields}:
        raise Refusal("RECORD_FIELD", "%s record needs exactly the fields %s"
                      % (kind, ", ".join(f[0] for f in fields)))
    for name, bits, sign in fields:
        v = record[name]
        lo, hi = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if sign == "signed" else (0, (1 << bits) - 1)
        if type(v) is not int or not lo <= v <= hi:
            raise Refusal("RECORD_FIELD", "%s.%s = %r does not fit %d %s bits" % (kind, name, v, bits, sign))
    if kind == "score" and record["flags"] & C.FLAGS_RESERVED_MASK:
        raise Refusal("RESERVED_BITS", "score.flags = 0x%02X" % record["flags"])
    return record


def pack(kind, record):
    """The record's canonical bytes."""
    check(kind, record)
    out = b""
    for name, bits, sign in C.RECORDS[kind]:
        if bits % 8:
            raise Refusal("RECORD_FIELD", "%s.%s is %d bits, not a whole number of bytes" % (kind, name, bits))
        out += record[name].to_bytes(bits // 8, "little", signed=(sign == "signed"))
    return out


def digest(kind, records):
    """SHA-256, in hex, of the canonical bytes of a sequence of records, and how many there were."""
    h, n = hashlib.sha256(), 0
    for r in records:
        h.update(pack(kind, r))
        n += 1
    return h.hexdigest(), n

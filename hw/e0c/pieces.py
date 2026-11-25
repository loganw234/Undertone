"""Stage E0's stream cut into pieces the card can run one at a time, and the reading of a piece's records.

THE STREAM. Round 1's: trial i has its truth record at index `first_index + spacing x i`, i from 0 to n - 1, and
the stream is spacing x (n + 1) frames, so the last span of `spacing` frames holds no trial (tests/test_seam_e0.py).
Span i is frames spacing x i to spacing x i + spacing - 1, and holds trial i whole: its pulse (CV1) and both of its
reads' windows, the score at truth + taps - 1 and the signal-free score at truth - 1 (CV2), when
first_index >= taps and first_index + taps <= spacing. `cut` refuses a stream for which that is not so.

THE PIECES. A piece is whole spans: it starts at a multiple of `spacing` and ends at one, or at the stream's end.
So every trial and both its reads are in one piece, and in that piece each read sits at a local index of
taps - 1 or more, where the core's delay line holds only the piece's own samples. Each piece is a run of its own:
its seed is the stream's seed advanced to its first frame, (s + GAMMA x channels x first) mod 2^64 (the plan's L17:
the model's word i of seed s is a mix of s + GAMMA x (i + 1)), and its schedule is its trials' truth records with
the piece's first frame taken from each index. Refused by name (hw/e0c/errors.py): a first frame or an end off the
grid, a gap or an overlap (PIECE_CUT); a piece of more frames than one buffer holds in one segment (PIECE_LENGTH).

THE READS. A piece's records file holds one canonical score record (model.records.pack's bytes, the bytes
host.run_case writes to records.bin) for each of its frames, in order. `reads` takes a trial's score at its local
truth index plus an offset from that trial's own piece; a read that falls outside the piece is NOT made, and is
counted (the late read of a piece's last trial is the one that does: its window ends on the next piece's first
frame). Every record read must carry the index it is read at, RECORD_ORDER otherwise; a file whose length is not
the piece's frames' records is refused, RUN_LENGTH.

Standard library, `spec/` and `model.source.GAMMA`. Desktop only: nothing the box runs imports this file.

WHAT IT CANNOT SEE: whether a record it reads is the model's (that is the comparison's, `compare_blocks`); a
read at an index it was not asked for; anything about the samples the card used, which never come back.
"""
import hashlib
import struct
from collections import namedtuple

from spec import constants as C
from model.source import GAMMA

from hw.e0c.errors import E0CRefusal

MASK = (1 << 64) - 1
SLOT = C.MEMORY_SLOT_BYTES
GUARD = SLOT * 124                       # host/library.py's guard before slot 0, as its GUARD
SEGMENT_BYTES = 1 << 28                  # one HBM segment, if the 32 are equal and "8GB" is 8 x 2^30 (the plan's L5)
MOST_FRAMES = (SEGMENT_BYTES - GUARD) // SLOT     # 8,388,484: the plan's L7

_CODES = {(64, "unsigned"): "Q", (64, "signed"): "q", (32, "unsigned"): "I", (32, "signed"): "i",
          (16, "unsigned"): "H", (16, "signed"): "h", (8, "unsigned"): "B", (8, "signed"): "b"}
SCORE_FIELDS = tuple(name for name, _bits, _sign in C.RECORDS["score"])
RECORD = struct.Struct("<" + "".join(_CODES[(bits, sign)] for _n, bits, sign in C.RECORDS["score"]))
RECORD_BYTES = RECORD.size               # 21: index 8, epoch 4, flags 1, score 8
FLAGS_AT = sum(bits for name, bits, _s in C.RECORDS["score"][:SCORE_FIELDS.index("flags")]) // 8
INDEX_AT = 0
SCORE_AT = sum(bits for name, bits, _s in C.RECORDS["score"][:SCORE_FIELDS.index("score")]) // 8

Piece = namedtuple("Piece", "number first frames first_trial trials seed")


def seed_at(seed, first, channels):
    """The seed whose word 0 is word `first x channels` of `seed`: the stream from frame `first` on."""
    return (seed + GAMMA * channels * first) & MASK


def even_bounds(spans, pieces, spacing):
    """First frames of `pieces` pieces of whole spans, each of spans // pieces spans but the last, which takes the
    rest. The stated cut of stage E0: 200,001 spans in four, 50,000 spans each and 50,001 in the last."""
    per = spans // pieces
    return [spacing * per * p for p in range(pieces)]


def cut(length, bounds, n, seed, channels, spacing, first_index, taps, most=MOST_FRAMES):
    """The pieces of a stream of `length` frames with `n` trials, cut at the first frames `bounds`.

    Returns a tuple of Piece. Refused, PIECE_CUT: a stream that is not whole spans, or that does not hold its
    trials and one more span; a trial whose reads' windows leave its span; bounds that do not start at 0, are not
    each a multiple of `spacing`, do not rise, or reach the stream's end. PIECE_LENGTH: a piece past `most`.
    """
    for name, v in (("length", length), ("n", n), ("spacing", spacing), ("first_index", first_index), ("taps", taps)):
        if type(v) is not int or v < 1:
            raise E0CRefusal("PIECE_CUT", "%s is %r, not an int of at least 1" % (name, v))
    if length % spacing or length != spacing * (n + 1):
        raise E0CRefusal("PIECE_CUT", "a stream of %d frames is not %d trials and one more span of %d"
                         % (length, n, spacing))
    if first_index < taps or first_index + taps > spacing:
        raise E0CRefusal("PIECE_CUT", "a trial at %d of a span of %d, with %d taps: its reads' windows leave its span"
                         % (first_index, spacing, taps))
    if not isinstance(bounds, (list, tuple)) or not bounds or any(type(b) is not int for b in bounds):
        raise E0CRefusal("PIECE_CUT", "the bounds are a non-empty list of ints, not %r" % (bounds,))
    if bounds[0] != 0:
        raise E0CRefusal("PIECE_CUT", "the first piece starts at %d, not 0: frames 0 to %d are in no piece"
                         % (bounds[0], bounds[0] - 1))
    ends = list(bounds[1:]) + [length]
    out = []
    for p, (a, b) in enumerate(zip(bounds, ends)):
        if a % spacing:
            raise E0CRefusal("PIECE_CUT", "piece %d starts at frame %d, which is not a multiple of %d" % (p, a, spacing))
        if b <= a:
            raise E0CRefusal("PIECE_CUT", "piece %d starts at %d and the next at %d: an overlap, or an empty piece"
                             % (p, a, b))
        if b > length:
            raise E0CRefusal("PIECE_CUT", "piece %d ends at %d, past the stream's %d frames" % (p, b, length))
        if b - a > most:
            raise E0CRefusal("PIECE_LENGTH", "piece %d holds %d frames; one buffer in one segment holds %d"
                             % (p, b - a, most))
        first_trial = a // spacing
        trials = min(b // spacing, n) - first_trial
        out.append(Piece(p, a, b - a, first_trial, max(trials, 0), seed_at(seed, a, channels)))
    return tuple(out)


def schedule_of(piece, spacing, first_index, pulse_id, amplitude_num, amplitude_den):
    """The piece's truth records: its trials', each index less the piece's first frame."""
    return [{"index": spacing * (piece.first_trial + t) + first_index - piece.first, "pulse_id": pulse_id,
             "amplitude_num": amplitude_num, "amplitude_den": amplitude_den} for t in range(piece.trials)]


def reads(data, piece, spacing, first_index, offsets):
    """Each trial's score at its local truth index plus each offset, read from the piece's records.

    Returns {offset: [score, or None where the read falls outside the piece]}, one entry a trial, in order.
    RUN_LENGTH: a file that is not exactly the piece's records. RECORD_ORDER: a record that does not carry the
    index it is read at.
    """
    if len(data) != piece.frames * RECORD_BYTES:
        raise E0CRefusal("RUN_LENGTH", "piece %d: %d bytes of records, not %d records of %d bytes"
                         % (piece.number, len(data), piece.frames, RECORD_BYTES))
    out = {}
    for offset in offsets:
        got = []
        for t in range(piece.trials):
            at = spacing * t + first_index + offset
            if not 0 <= at < piece.frames:
                got.append(None)
                continue
            index, _epoch, _flags, score = RECORD.unpack_from(data, at * RECORD_BYTES)
            if index != at:
                raise E0CRefusal("RECORD_ORDER", "piece %d: the record at place %d carries index %d"
                                 % (piece.number, at, index))
            got.append(score)
        out[offset] = got
    return out


def count(scores, threshold):
    """(crossings, reads made, reads not made): a crossing is a score strictly above the threshold (CV3)."""
    made = [s for s in scores if s is not None]
    return sum(1 for s in made if s > threshold), len(made), len(scores) - len(made)


def flags_seen(data):
    """The OR of every record's flags byte."""
    seen = 0
    for v in set(data[FLAGS_AT::RECORD_BYTES]):
        seen |= v
    return seen


def digest_scores(*lists):
    """A SHA-256 of score lists, each score a little-endian signed 64-bit word, the lists one after another.
    A read not made is refused here: a digest is of reads made."""
    h = hashlib.sha256()
    for scores in lists:
        if any(s is None for s in scores):
            raise E0CRefusal("PIECE_SET", "a digest asked of reads that were not all made")
        h.update(struct.pack("<%dq" % len(scores), *scores))
    return h.hexdigest()


def block_hashes(data, block):
    """(SHA-256 of the whole, [SHA-256 of each block of `block` records]) of a records file."""
    size = block * RECORD_BYTES
    return (hashlib.sha256(data).hexdigest(),
            [hashlib.sha256(data[i:i + size]).hexdigest() for i in range(0, len(data), size)])


def compare_blocks(data, expected, remake=None):
    """The card's records of one piece against the model's, as `expected` holds them: {"records", "sha256",
    "block", "blocks"}. Returns a report: {"identical", "records", "expected_records", "blocks_differ",
    "first": None or {"record", "field", "card", "model"} or {"record", "why"}}.

    `remake(first, count)` gives the model's canonical bytes of records first .. first + count - 1, made again;
    with it, the first differing record within the first differing block is named, field and values. Without it
    the report names the block only.
    """
    n = len(data) // RECORD_BYTES
    whole, blocks = block_hashes(data[:n * RECORD_BYTES], expected["block"])
    report = {"identical": False, "records": n, "expected_records": expected["records"], "blocks_differ": 0,
              "first": None, "trailing_bytes": len(data) - n * RECORD_BYTES}
    if whole == expected["sha256"] and n == expected["records"] and not report["trailing_bytes"]:
        report["identical"] = True
        return report
    differ = [b for b in range(max(len(blocks), len(expected["blocks"])))
              if b >= len(blocks) or b >= len(expected["blocks"]) or blocks[b] != expected["blocks"][b]]
    report["blocks_differ"] = len(differ)
    if not differ:          # every block equal: the difference is a trailing part of a record
        report["first"] = {"record": n, "why": "%d bytes past the last whole record" % report["trailing_bytes"]}
        return report
    b = differ[0]
    lo = b * expected["block"]
    hi = min((b + 1) * expected["block"], expected["records"])
    if remake is None:
        report["first"] = {"record": lo, "why": "block %d (records %d to %d) differs; no remake was given"
                           % (b, lo, hi - 1)}
        return report
    model = remake(lo, max(hi - lo, 0))
    for r in range(lo, max(hi, min(n, (b + 1) * expected["block"]))):
        if r >= n:
            report["first"] = {"record": r, "why": "the card's file ends at %d records; the model has %d"
                               % (n, expected["records"])}
            return report
        if r >= hi:
            report["first"] = {"record": r, "why": "the card's file has %d records; the model has %d"
                               % (n, expected["records"])}
            return report
        mine = model[(r - lo) * RECORD_BYTES:(r - lo + 1) * RECORD_BYTES]
        card = data[r * RECORD_BYTES:(r + 1) * RECORD_BYTES]
        if mine != card:
            a, m = RECORD.unpack(card), RECORD.unpack(mine)
            field = next(f for f, x, y in zip(SCORE_FIELDS, a, m) if x != y)
            report["first"] = {"record": r, "field": field, "card": a[SCORE_FIELDS.index(field)],
                               "model": m[SCORE_FIELDS.index(field)]}
            return report
    report["first"] = {"record": lo, "why": "block %d differs by its hash and no record in it differs: the "
                       "expectation's block does not hash these bytes" % b}
    return report


def flipped(blob, bit=12):
    """Round 3's flip control, written again here (hw/card/card.py's `flipped`, kept as it ran): bit `bit` of
    filter 0, channel 0's first tap of the largest magnitude, as an 18-bit two's complement word. Returns (blob,
    (tap, before, after)). On e0's matched filter: tap 28, -131071 to -126975 (docs/studies/CARD-first-light.md)."""
    from model import weights
    config = weights.unpack(blob)
    rows = [dict((c, list(row)) for c, row in f.items()) for f in config["filters"]]
    row = rows[0][0]
    tap = max(range(len(row)), key=lambda m: (abs(row[m]), -m))
    v = row[tap]
    w = v ^ (1 << bit)
    if w > C.COEFF_MAX:
        w -= 1 << C.COEFF_BITS
    row[tap] = w
    return weights.pack(config["profile"], rows, list(config["head"]), config["rectifier"], config["pool"],
                        config["score_shift"]), (tap, v, w)

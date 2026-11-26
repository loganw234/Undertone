"""Stage E1's held-out stretch cut into pieces the card can run one at a time, and the reading of a piece's records.

THE STRETCH. A part of stage E1 (tests/test_lrn_a_e1.py, `plan`) is one stream: training, frames 0 to A - 1;
calibration, A to B - 1, with no injection; test, B to L - 1, a trial every 128 frames with its truth at
B + 64 + 128 i. Every figure is read from a record at A + 63 + 64 g: the signal-free scores of the calibration
stretch, and in the test stretch each trial's score at truth - 1 and at truth + 63. A read's window is frames
A + 64 g to A + 64 g + 63 (conventions CV2), one whole block of 64 counted from A, and a test pulse fills one such
block exactly.

THE PIECES. Each piece starts at A + 64 q, so no read's window and no test pulse crosses a bound; in its piece each
read sits at local index 64 q' + 63, where the core's delay line holds the piece's own samples only. The stated cut
is four pieces: the calibration stretch's two halves, then the test stretch's (`stated_bounds`). Each piece is a run
of its own: its seed is the part's seed advanced to its first frame (`hw.e0c.pieces.seed_at`, imported), and its
schedule is its truth records with the piece's first frame taken from each index. Refused by name
(hw/e1c/errors.py): a bound not A + 64 q, a first piece not at A, bounds that do not rise or that reach the
stream's end, a truth record whose pulse a bound splits (PIECE_CUT); a piece of more frames than one buffer holds
in one segment (PIECE_LENGTH); local schedules that do not join back into the part's own (PIECE_SET).

THE READS. A piece's records file holds one canonical score record (model.records.pack's bytes, host.run_case's
records.bin) for each of its frames. `reads` takes the record at every local 64 q + 63, requires it to carry that
index (RECORD_ORDER otherwise) and gives it back at its stream index, first + local; a file that is not exactly the
piece's records is refused, RUN_LENGTH.

Standard library, `spec/` and E0C's `hw/e0c/pieces.py` (which takes `model.source.GAMMA`). Desktop only: nothing the
box runs imports this file.

WHAT IT CANNOT SEE: whether a record it reads is the model's (that is the comparison's, `compare_blocks`); a read at
an index it was not asked for; anything about the samples the card used, which never come back.
"""
from collections import namedtuple

from spec import constants as C

from hw.e0c.pieces import MOST_FRAMES, RECORD, RECORD_BYTES, seed_at
from hw.e1c.errors import E1CRefusal

GRID = 64                                  # stage E1's read stride and its filter's length (tests/test_lrn_a_e1.py, STRIDE)
PULSE_LENGTH = dict((C.PULSE_IDS[name], len(samples)) for name, samples in C.PULSES.items())

Piece = namedtuple("Piece", "number first frames seed")


def stated_bounds(a, b, m_cal, n, spacing=128, grid=GRID):
    """The stated cut's first frames: the calibration stretch's two halves, then the test stretch's."""
    if m_cal % 2 or n % 2:
        raise E1CRefusal("PIECE_CUT", "the stated cut halves %d calibration blocks and %d trials; each must be even"
                         % (m_cal, n))
    return [a, a + grid * (m_cal // 2), b, b + spacing * (n // 2)]


def cut(a, length, bounds, seed, channels, grid=GRID, most=MOST_FRAMES):
    """The pieces of the held-out stretch, frames a to length - 1, cut at the first frames `bounds`. A tuple of Piece."""
    for name, v in (("a", a), ("length", length), ("channels", channels), ("grid", grid)):
        if type(v) is not int or v < (0 if name == "a" else 1):
            raise E1CRefusal("PIECE_CUT", "%s is %r, not a count" % (name, v))
    if length <= a or (length - a) % grid:
        raise E1CRefusal("PIECE_CUT", "a held-out stretch from %d to %d is not whole blocks of %d" % (a, length, grid))
    if not isinstance(bounds, (list, tuple)) or not bounds or any(type(x) is not int for x in bounds):
        raise E1CRefusal("PIECE_CUT", "the bounds are a non-empty list of ints, not %r" % (bounds,))
    if bounds[0] != a:
        raise E1CRefusal("PIECE_CUT", "the first piece starts at %d, not at A = %d" % (bounds[0], a))
    ends = list(bounds[1:]) + [length]
    out = []
    for q, (first, end) in enumerate(zip(bounds, ends)):
        if (first - a) % grid:
            raise E1CRefusal("PIECE_CUT", "piece %d starts at %d, which is not A + %d q (A = %d)" % (q, first, grid, a))
        if end <= first:
            raise E1CRefusal("PIECE_CUT", "piece %d starts at %d and the next at %d: an overlap, or an empty piece"
                             % (q, first, end))
        if end > length:
            raise E1CRefusal("PIECE_CUT", "piece %d ends at %d, past the stream's %d frames" % (q, end, length))
        if end - first > most:
            raise E1CRefusal("PIECE_LENGTH", "piece %d holds %d frames; one buffer in one segment holds %d"
                             % (q, end - first, most))
        out.append(Piece(q, first, end - first, seed_at(seed, first, channels)))
    return tuple(out)


def schedule_of(piece, schedule):
    """The truth records whose pulses lie in the piece, each index less its first frame. A record whose pulse
    starts in the piece and ends past it, or starts before it and ends in it, is refused, PIECE_CUT."""
    out = []
    lo, hi = piece.first, piece.first + piece.frames
    for r in schedule:
        start, end = r["index"], r["index"] + PULSE_LENGTH[r["pulse_id"]]
        if end <= lo or start >= hi:
            continue
        if start < lo or end > hi:
            raise E1CRefusal("PIECE_CUT", "piece %d (frames %d to %d) splits the pulse of the record at %d"
                             % (piece.number, lo, hi - 1, start))
        out.append(dict(r, index=start - lo))
    return out


def join(pieces, schedules):
    """The pieces' local schedules put back at their stream indexes, in order."""
    return [dict(r, index=r["index"] + piece.first) for piece, sched in zip(pieces, schedules) for r in sched]


def check_joined(training, pieces, schedules, schedule):
    """The training stretch's records and the pieces' records, put back, must be the part's own schedule, PIECE_SET."""
    joined = list(training) + join(pieces, schedules)
    if joined != list(schedule):
        raise E1CRefusal("PIECE_SET", "the training records and the pieces' schedules put back are %d records that "
                         "are not the part's %d" % (len(joined), len(schedule)))
    return joined


def read_places(piece, grid=GRID):
    """The local indexes a piece is read at: every grid - 1 + grid q."""
    return range(grid - 1, piece.frames, grid)


def reads(data, piece, grid=GRID):
    """The records at the piece's read places, each at its stream index: dicts of index, epoch, flags and score."""
    if len(data) != piece.frames * RECORD_BYTES:
        raise E1CRefusal("RUN_LENGTH", "piece %d: %d bytes of records, not %d records of %d bytes"
                         % (piece.number, len(data), piece.frames, RECORD_BYTES))
    out = []
    for at in read_places(piece, grid):
        index, epoch, flags, score = RECORD.unpack_from(data, at * RECORD_BYTES)
        if index != at:
            raise E1CRefusal("RECORD_ORDER", "piece %d: the record at place %d carries index %d"
                             % (piece.number, at, index))
        out.append({"index": piece.first + at, "epoch": epoch, "flags": flags, "score": score})
    return out

"""E0C: stage E0's stream in pieces (hw/e0c/pieces.py), held against the model's continuous run.

The gate `replay`: a stream cut into pieces, each run as a run of its own (a fresh core, the seed advanced to the
piece's first frame, the schedule shifted by it), reads every trial exactly as the continuous stream does. Under
both profiles, with a filter that reads two of s24x3's three channels at different gains. Its controls: a piece
seeded without its offset differs at the first record it reads; a schedule shifted by the wrong amount differs at
its first trial's at-index read; a cut off the grid of 128 is refused by name.

Expected answers: the stated cut's figures are the design's (E0C's ledger, 12:24), worked by arithmetic there:
200,001 spans in four, 50,000 a piece and 50,001 in the last; 128 frames a span; a buffer the library's guard of
3,968 bytes and 32 a slot. Each piece's seed is held a second way, by the generator's own identity (words 0 and 1
of the piece's seed are words `first` and `first + 1` of the stream's), so not by retyping the sum. The flip's tap and values are round 3's
(docs/studies/CARD-first-light.md: tap 28, -131071 to -126975).
"""
import pytest

from spec import constants as C
from model import records, run, source, weights

from hw.e0c import pieces as P
from hw.e0c.errors import E0CRefusal

SPACING, FIRST, TAPS = 128, 64, len(C.PULSES["e0"])
E0 = C.PULSES["e0"]
SIGMA = (1477, 1)


def stated(k):
    n = 200000
    length = SPACING * (n + 1)
    return P.cut(length, P.even_bounds(n + 1, 4, SPACING), n, 2026112300 + k, 1, SPACING, FIRST, TAPS)


def test_e0c_the_stated_cut_is_the_designs():
    for k in range(5):
        cut = stated(k)
        assert [p.first for p in cut] == [0, 6400000, 12800000, 19200000]
        assert [p.frames for p in cut] == [6400000, 6400000, 6400000, 6400128]
        assert [(p.first_trial, p.trials) for p in cut] == [(0, 50000), (50000, 50000), (100000, 50000), (150000, 50000)]
        assert sum(p.frames for p in cut) == 25600128 and sum(p.trials for p in cut) == 200000
        assert all(p.frames <= P.MOST_FRAMES == 8388484 for p in cut)
        assert [P.GUARD + P.SLOT * p.frames for p in cut] == [204803968] * 3 + [204808064]
        assert all(P.GUARD + P.SLOT * p.frames <= 1 << 28 for p in cut)
        for p in cut:   # the generator's own identity, words 0 and 1: not the sum retyped
            assert [source.word(p.seed, i) for i in (0, 1)] == [source.word(2026112300 + k, p.first + i) for i in (0, 1)]
    assert [p.seed for p in stated(0)] == [2026112300, 9739868458805808428, 1032992841875952940, 10772861298655649068]
    assert [p.seed - q.seed for p, q in zip(stated(4), stated(0))] == [4, 4, 4, 4]


def _short(profile, gains, n=40, pieces=3, seed=20261125):
    blob = weights.matched_filter(profile, E0, gains)
    length = SPACING * (n + 1)
    channels = C.PROFILES[profile]["channels"]
    cut = P.cut(length, P.even_bounds(n + 1, pieces, SPACING), n, seed, channels, SPACING, FIRST, TAPS)
    whole = [{"index": FIRST + SPACING * i, "pulse_id": C.PULSE_IDS["e0"], "amplitude_num": 1, "amplitude_den": 1}
             for i in range(n)]
    cont, _t = run.detect(source.Noise(profile, seed, SIGMA[0], SIGMA[1], length), whole, length, blob)
    return blob, cut, cont


def _piece_records(profile, blob, piece, sched=None, seed=None):
    sched = P.schedule_of(piece, SPACING, FIRST, C.PULSE_IDS["e0"], 1, 1) if sched is None else sched
    noise = source.Noise(profile, piece.seed if seed is None else seed, SIGMA[0], SIGMA[1], piece.frames)
    recs, _t = run.detect(noise, sched, piece.frames, blob)
    return recs


def _bytes(recs):
    return b"".join(records.pack("score", r) for r in recs)


def _cont_read(cont, piece, t, offset):
    return cont[piece.first + SPACING * t + FIRST + offset]["score"]


PROFILES = (("s16x1", (1,)), ("s24x3", (1, 0, 2)))


@pytest.mark.parametrize("profile,gains", PROFILES)
def test_gate_replay__e0c_pieces_read_every_trial_as_the_continuous_stream_does(profile, gains):
    blob, cut, cont = _short(profile, gains)
    assert len(cut) == 3 and [p.first for p in cut] == [0, 1664, 3328] and cut[-1].frames == 15 * SPACING
    late_not_read = 0
    for piece in cut:
        recs = _piece_records(profile, blob, piece)
        assert len(recs) == piece.frames
        # a piece's start, against the model's continuous run: from record 63 on every record is the continuous
        # one, index less the first frame; record 62 meets only c[0], which is 0; records 0 to 61 may differ
        for j, r in enumerate(recs):
            c = cont[piece.first + j]
            assert r["index"] == j and r["epoch"] == 0 and r["flags"] == 0
            if j >= TAPS - 2:
                assert (r["score"], r["flags"], r["epoch"]) == (c["score"], c["flags"], c["epoch"]), (piece.number, j)
        assert weights.unpack(blob)["filters"][0][0][0] == 0
        early = [j for j in range(TAPS - 2) if recs[j]["score"] != cont[piece.first + j]["score"]]
        if piece.number == 0:
            assert early == [] and recs[0]["score"] == 0
        else:
            assert early, "the delay line starts at zero: some of records 0 to 61 must differ, or this test is blind"
            assert recs[0]["score"] == 0, "record 0 meets only c[63], which is 0"
        got = P.reads(_bytes(recs), piece, SPACING, FIRST, (TAPS - 1, -1, TAPS))
        for offset in (TAPS - 1, -1):
            assert None not in got[offset], "every read of every trial is inside its own piece"
            assert got[offset] == [_cont_read(cont, piece, t, offset) for t in range(piece.trials)]
        late = got[TAPS]
        late_not_read += late.count(None)
        assert [s for s in late if s is not None] == \
            [_cont_read(cont, piece, t, TAPS) for t in range(piece.trials) if late[t] is not None]
    assert late_not_read == len(cut) - 1, "the late read of each piece's last trial but the stream's last falls out"


@pytest.mark.parametrize("profile,gains", PROFILES)
def test_control_replay__e0c_a_piece_seeded_without_its_offset_differs_at_the_first_record_it_reads(profile, gains):
    blob, cut, cont = _short(profile, gains)
    base = cut[0].seed
    for piece in cut[1:]:
        recs = _piece_records(profile, blob, piece, seed=base)
        got = P.reads(_bytes(recs), piece, SPACING, FIRST, (-1, TAPS - 1))
        first = next((t, off) for t in range(piece.trials) for off in (-1, TAPS - 1)
                     if got[off][t] != _cont_read(cont, piece, t, off))
        print("CONTROL e0c %s piece %d seeded %d, not %d: first read that differs, trial %d offset %+d"
              % (profile, piece.number, base, piece.seed, first[0], first[1]))
        assert first == (0, -1), "the first record a piece reads is its first trial's signal-free score, local 63"


@pytest.mark.parametrize("profile,gains", PROFILES)
def test_control_replay__e0c_a_schedule_shifted_a_span_short_differs_at_its_first_at_index_read(profile, gains):
    blob, cut, cont = _short(profile, gains)
    piece = cut[1]
    right = P.schedule_of(piece, SPACING, FIRST, C.PULSE_IDS["e0"], 1, 1)
    wrong = [dict(r, index=r["index"] + SPACING) for r in right[:-1]]
    recs = _piece_records(profile, blob, piece, sched=wrong)
    got = P.reads(_bytes(recs), piece, SPACING, FIRST, (-1, TAPS - 1))
    first = next((t, off) for t in range(piece.trials) for off in (-1, TAPS - 1)
                 if got[off][t] != _cont_read(cont, piece, t, off))
    assert first == (0, TAPS - 1), "trial 0's pulse is missing from its at-index read; its signal-free read is not touched"


def test_control_replay__e0c_a_cut_off_the_grid_is_refused_by_name():
    n = 40
    length = SPACING * (n + 1)

    def refused(bounds, **kw):
        with pytest.raises(E0CRefusal) as e:
            P.cut(kw.pop("length", length), bounds, kw.pop("n", n), 1, 1, SPACING, kw.pop("first_index", FIRST), TAPS,
                  **kw)
        return e.value.name

    for m in (5, 13):
        assert refused([0, SPACING * m + 1]) == "PIECE_CUT"          # one frame late
        assert refused([0, SPACING * m - 1]) == "PIECE_CUT"          # one frame early
    assert refused([0, 64]) == "PIECE_CUT"                           # half a span: a trial's pulse cut in two
    assert refused([SPACING, SPACING * 20]) == "PIECE_CUT"           # frames 0 to 127 in no piece
    assert refused([0, SPACING * 20, SPACING * 20]) == "PIECE_CUT"   # an empty piece
    assert refused([0, SPACING * 20, SPACING * 10]) == "PIECE_CUT"   # an overlap
    assert refused([0, length]) == "PIECE_CUT"                       # a piece that starts at the stream's end
    assert refused([0], length=length + 1) == "PIECE_CUT"            # a stream that is not whole spans
    assert refused([0], first_index=TAPS - 1) == "PIECE_CUT"         # a signal-free read whose window leaves its span
    assert refused([0], first_index=SPACING - TAPS + 1) == "PIECE_CUT"   # an at-index read whose window leaves it
    # one buffer in one segment: 65,535 spans fit, 65,536 do not
    big = 65536
    assert P.cut(SPACING * (big + 1), [0, SPACING * 65535], big, 1, 1, SPACING, FIRST, TAPS)[0].frames == 8388480
    assert refused([0, SPACING * 65536], length=SPACING * (big + 1), n=big) == "PIECE_LENGTH"
    assert refused([0], length=SPACING * 200001, n=200000) == "PIECE_LENGTH"
    # and the stated cut is taken
    assert len(stated(2)) == 4


def test_e0c_a_records_file_that_is_not_its_pieces_is_refused_by_name():
    blob, cut, cont = _short("s16x1", (1,), n=8, pieces=2)
    piece = cut[1]
    data = _bytes(_piece_records("s16x1", blob, piece))
    with pytest.raises(E0CRefusal) as e:
        P.reads(data[:-P.RECORD_BYTES], piece, SPACING, FIRST, (-1,))
    assert e.value.name == "RUN_LENGTH"
    shifted = data[P.RECORD_BYTES:] + data[-P.RECORD_BYTES:]       # one record lost at the front, the last twice
    with pytest.raises(E0CRefusal) as e:
        P.reads(shifted, piece, SPACING, FIRST, (-1,))
    assert e.value.name == "RECORD_ORDER"


def test_e0c_the_record_layout_is_the_models():
    for r in ({"index": 0, "epoch": 0, "flags": 0, "score": 0},
              {"index": (1 << 64) - 1, "epoch": (1 << 32) - 1, "flags": 3, "score": -(1 << 63)},
              {"index": 6400127, "epoch": 7, "flags": 1, "score": 1595666165}):
        assert P.RECORD.pack(*[r[f] for f in P.SCORE_FIELDS]) == records.pack("score", r)
    assert (P.RECORD_BYTES, P.INDEX_AT, P.FLAGS_AT, P.SCORE_AT) == (21, 0, 12, 13)


def test_e0c_the_flip_is_round_3s():
    blob = weights.matched_filter("s16x1", E0, (1,))
    flip, (tap, before, after) = P.flipped(blob)
    assert (tap, before, after) == (28, -131071, -126975)
    a, b = weights.unpack(blob)["filters"][0][0], weights.unpack(flip)["filters"][0][0]
    assert [j for j in range(TAPS) if a[j] != b[j]] == [28]

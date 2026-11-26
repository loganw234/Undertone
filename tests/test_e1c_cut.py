"""E1C: stage E1's held-out stretch in pieces (hw/e1c/cut.py), the stated cut, and every refusal of the cut by name.

Expected answers, worked by arithmetic in E1C's design (the round's ledger, E1C.md, 2026-11-25 20:53, section 2) and
not by the code it judges: a part's held-out stretch is 64 x 200,000 + 128 x 100,000 = 25,600,000 frames; its
four pieces start at A, A + 6,400,000, B and B + 6,400,000 and hold 6,400,000 frames each; a piece is read at every
local 63 + 64 q, 100,000 reads a piece, 400,000 a part. Part 5's first frames are 2,097,152, 8,497,152, 14,897,152
and 21,297,152. Each piece's seed is held a second way, by the generator's own identity (words 0 and 1 of the
piece's seed are words `first` and `first + 1` of the part's), so not by retyping the sum.

These claim no gate row: the gate `replay` is held by tests/test_e1c_replay.py, on the model.
"""
import pytest

from spec import constants as C
from model import source

import test_lrn_a_e1 as E1
from hw.e0c.pieces import MOST_FRAMES, RECORD
from hw.e1c import cut as K
from hw.e1c import e1c
from hw.e1c.errors import E1CRefusal

FIRSTS = {0: 2048, 1: 8192, 2: 32768, 3: 131072, 4: 524288, 5: 2097152}


def test_e1c_the_stated_cut_is_the_designs():
    for c, a in FIRSTS.items():
        p = E1.plan(c)
        assert (p["A"], p["B"], p["length"]) == (a, a + 12800000, a + 25600000)
        pieces = e1c.the_cut(p)
        assert [x.first for x in pieces] == [a, a + 6400000, a + 12800000, a + 19200000]
        assert [x.frames for x in pieces] == [6400000] * 4 and sum(x.frames for x in pieces) == 25600000
        assert [len(K.read_places(x)) for x in pieces] == [100000] * 4
        for x in pieces:
            assert list(source.Noise("s16x1", x.seed, 1477, 1, 0).words(0, 2)) == \
                list(source.Noise("s16x1", p["seed"], 1477, 1, 0).words(x.first, 2)), "the seed is the part's at that frame"
        schedule = E1.schedule_for(p)
        training, held = e1c.held_of(p, schedule)
        scheds = [K.schedule_of(x, held) for x in pieces]
        assert [len(s) for s in scheds] == [0, 0, 50000, 50000] and len(training) == p["trained_on"]
        assert scheds[2][0]["index"] == 64 and scheds[3][-1]["index"] == 64 + 128 * 49999
        assert K.check_joined(training, pieces, scheds, schedule) == schedule
    assert [x.first for x in e1c.the_cut(E1.plan(5))] == [2097152, 8497152, 14897152, 21297152]
    short = e1c.the_cut(E1.plan("short"))
    assert [(x.first, x.frames) for x in short] == [(131072, 256000), (387072, 256000), (643072, 256000), (899072, 256000)]


def test_e1c_every_read_of_every_piece_is_whole_inside_it_at_a_place_past_the_delay_line():
    """The reads of a part, piece by piece, are exactly E1's own read positions, in E1's order: the calibration
    stretch's, then each test trial's signal-free read and its at-index read, each at local 63 or later."""
    for c in (0, 5, "short"):
        p = E1.plan(c)
        got = []
        for x in e1c.the_cut(p):
            places = list(K.read_places(x))
            assert places[0] == 63 and places[-1] == x.frames - 1 and all(b - a == 64 for a, b in zip(places, places[1:]))
            got += [x.first + j for j in places]
        cal = list(E1.free_positions(p)[:p["m_cal"]])
        trials = [v for pair in zip(E1.free_positions(p)[p["m_cal"]:], E1.at_positions(p)) for v in pair]
        assert got == cal + trials and len(got) == p["m_cal"] + 2 * p["n"]


def test_e1c_a_cut_off_the_grid_or_past_a_buffer_is_refused_by_name():
    a, length, seed = 2048, 2048 + 64 * 1000, 7
    good = K.cut(a, length, [a, a + 64 * 400], seed, 1)
    assert [(x.first, x.frames) for x in good] == [(2048, 25600), (27648, 38400)]

    def refused(name, *args, **kw):
        with pytest.raises(E1CRefusal) as e:
            K.cut(*args, **kw)
        assert e.value.name == name, (e.value, args)
        return e.value

    for off in (1, -1, 32, 63):
        refused("PIECE_CUT", a, length, [a, a + 64 * 400 + off], seed, 1)          # a bound off the grid of 64
    refused("PIECE_CUT", a, length, [a + 64, a + 64 * 400], seed, 1)               # the first piece not at A
    refused("PIECE_CUT", a, length, [0, a + 64 * 400], seed, 1)                    # nor before it
    refused("PIECE_CUT", a, length, [a, a + 64 * 400, a + 64 * 400], seed, 1)      # an empty piece
    refused("PIECE_CUT", a, length, [a, a + 64 * 400, a + 64 * 100], seed, 1)      # bounds that do not rise
    refused("PIECE_CUT", a, length, [a, length], seed, 1)                          # a bound at the stream's end
    refused("PIECE_CUT", a, length + 1, [a], seed, 1)                              # a stretch not whole blocks
    refused("PIECE_CUT", a, a, [a], seed, 1)                                       # an empty stretch
    refused("PIECE_CUT", a, length, [], seed, 1)
    refused("PIECE_CUT", a, length, [float(a)], seed, 1)
    # one buffer in one segment holds 8,388,484 frames: 131,070 blocks of 64 are taken, 131,071 refused
    assert MOST_FRAMES == 8388484 and 64 * 131070 <= MOST_FRAMES < 64 * 131071
    big = a + 64 * 131071 * 2
    assert len(K.cut(a, big, [a, a + 64 * 131070, a + 64 * 131070 * 2], seed, 1)) == 3
    e = refused("PIECE_LENGTH", a, big, [a, a + 64 * 131071], seed, 1)
    assert "8388544" in str(e) and "8388484" in str(e)
    with pytest.raises(E1CRefusal) as e:
        K.stated_bounds(a, a + 64 * 7, 7, 4)
    assert e.value.name == "PIECE_CUT"


def test_e1c_a_pulse_a_bound_splits_and_schedules_that_do_not_join_back_are_refused_by_name():
    p = E1.plan("short")
    pieces = e1c.the_cut(p)
    schedule = E1.schedule_for(p)
    training, held = e1c.held_of(p, schedule)
    rec = dict(held[0])
    for start in (pieces[3].first - 1, pieces[3].first - 63, pieces[1].first - 10):    # a pulse over a bound
        with pytest.raises(E1CRefusal) as e:
            K.schedule_of(pieces[3] if start > pieces[2].first else pieces[1], [dict(rec, index=start)])
        assert e.value.name == "PIECE_CUT", start
    assert K.schedule_of(pieces[3], [dict(rec, index=pieces[3].first - 64)]) == []      # one that ends before it
    assert K.schedule_of(pieces[3], [dict(rec, index=pieces[3].first)])[0]["index"] == 0
    scheds = [K.schedule_of(x, held) for x in pieces]
    for wrong in (lambda s: s[2].pop(0), lambda s: s[3].append(dict(s[3][-1], index=s[3][-1]["index"] + 128)),
                  lambda s: s[2].__setitem__(0, dict(s[2][0], index=s[2][0]["index"] + 1))):
        copy = [list(s) for s in scheds]
        wrong(copy)
        with pytest.raises(E1CRefusal) as e:
            K.check_joined(training, pieces, copy, schedule)
        assert e.value.name == "PIECE_SET"
    with pytest.raises(E1CRefusal) as e:
        K.check_joined(training[1:], pieces, scheds, schedule)
    assert e.value.name == "PIECE_SET"


def test_e1c_a_records_file_that_is_not_its_pieces_is_refused_by_name():
    piece = K.Piece(0, 1000, 256, 5)
    data = b"".join(RECORD.pack(j, 1, 0, 3 * j - 7) for j in range(256))
    got = K.reads(data, piece)
    assert [r["index"] for r in got] == [1063, 1127, 1191, 1255] and [r["score"] for r in got] == [182, 374, 566, 758]
    assert {r["epoch"] for r in got} == {1}
    for bad, name in ((data[:-21], "RUN_LENGTH"), (data + data[:21], "RUN_LENGTH"), (data[:-1], "RUN_LENGTH"),
                      (data[21:] + data[:21], "RECORD_ORDER")):
        with pytest.raises(E1CRefusal) as e:
            K.reads(bad, piece)
        assert e.value.name == name
    assert C.RECORDS["score"][0][0] == "index", "the reader takes the record's first field as its index"

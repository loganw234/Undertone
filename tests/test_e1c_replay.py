"""E1C: a held-out stretch in pieces, each run as a run of its own, reads every record stage E1 reads exactly as the
continuous stream does, the swap at A included.

The gate `replay`, on the model, under both profiles, with a learned set whose rows differ from channel to
channel. The continuous stream is stage E1's own wiring (`wired` of tests/test_lrn_a_e1.py): one core holding the
old set, the new one written into its shadow and committed at A. Each piece is a fresh core holding the new set at
epoch 1, its seed the stream's advanced to the piece's first frame, its schedule shifted by it (hw/e1c/cut.py).
Expected: every read at A + 63 + 64 g is the continuous stream's record, index for its stream index, epoch, flags and
score; so is every record of a piece from its local 63 on; and some record of 0 to 62 is not, the delay line holding
zeros there, which is why none of them is read.

Its controls: a piece seeded without its offset differs at the first record it reads, local 63; a test piece
whose schedule is a block late differs first at its first at-index read, local 127, and not at its signal-free read
before it.

The small stream: A = 256 (two training trials), 8 calibration blocks, 6 test trials; the pieces 4 blocks of
calibration, 4 more, 3 trials, 3 trials.
"""
import pytest

from spec import constants as C
from model import inject, source
from model.detector import Core

import test_lrn_a_e1 as E1
from learn import handover
from hw.e1c import cut as K

A, M_CAL, N, SEED, SIGMA = 256, 8, 6, 2026112671, (1477, 1)
B = A + 64 * M_CAL
L = B + 128 * N


def schedule():
    rec = {"pulse_id": C.PULSE_IDS["e0"], "amplitude_num": 1, "amplitude_den": 1}
    return [dict(rec, index=64 + 128 * i) for i in range(A // 128)] + [dict(rec, index=B + 64 + 128 * i) for i in range(N)]


def sets(profile):
    channels = C.PROFILES[profile]["channels"]
    old = handover.candidate_blob(profile, tuple(tuple((c + 2) * (k - 30) + c for k in range(64)) for c in range(channels)))
    new = handover.candidate_blob(profile, tuple(tuple(((k * (c + 3)) % 17) - 8 + c for k in range(64)) for c in range(channels)))
    return old, new


def continuous(profile):
    old, new = sets(profile)
    pairs, _truth = E1.wired(profile, source.Noise(profile, SEED, SIGMA[0], SIGMA[1], L), schedule(), L, old, (A, lambda: new, A))
    return [r for _f, r in pairs]


def pieces(profile):
    return K.cut(A, L, K.stated_bounds(A, B, M_CAL, N), SEED, C.PROFILES[profile]["channels"])


def piece_records(profile, piece, seed=None, shift=0):
    _old, new = sets(profile)
    held = [r for r in schedule() if r["index"] >= A]
    sched = [dict(r, index=r["index"] + shift) for r in K.schedule_of(piece, held) if r["index"] + shift + 64 <= piece.frames]
    noise = source.Noise(profile, piece.seed if seed is None else seed, SIGMA[0], SIGMA[1], piece.frames)
    frames, _truth = inject.inject(profile, noise, sched, piece.frames)
    return list(Core(new, 1).run(frames))


@pytest.mark.parametrize("profile", sorted(C.PROFILES))
def test_gate_replay__e1c_pieces_read_every_held_out_record_as_the_continuous_stream_does(profile):
    whole = continuous(profile)
    assert [r["epoch"] for r in whole] == [0] * A + [1] * (L - A), "the continuous stream swaps at A"
    cut = pieces(profile)
    assert [(x.first, x.frames) for x in cut] == [(256, 256), (512, 256), (768, 384), (1152, 384)]
    reads, some_differ = [], 0
    for x in cut:
        mine = piece_records(profile, x)
        assert len(mine) == x.frames
        for j, r in enumerate(mine):
            theirs = whole[x.first + j]
            same = dict(r, index=r["index"] + x.first) == theirs
            if j >= 63:
                assert same, (profile, x.number, j)
            else:
                some_differ += not same
        reads += [dict(mine[j], index=x.first + j) for j in K.read_places(x)]
    assert reads == [whole[i] for i in range(A + 63, L, 64)] and len(reads) == M_CAL + 2 * N
    assert some_differ > 0, "a piece's first 63 records meet zeros where the continuous stream had samples"
    assert len({r["score"] for r in reads}) == len(reads), "the reads are all different scores: a stream that can show a fault"


@pytest.mark.parametrize("profile", sorted(C.PROFILES))
def test_control_replay__e1c_a_piece_seeded_without_its_offset_differs_at_its_first_read(profile):
    whole = continuous(profile)
    for x in pieces(profile)[1:]:
        mine = piece_records(profile, x, seed=SEED)
        first = next(j for j in range(63, x.frames) if dict(mine[j], index=mine[j]["index"] + x.first) != whole[x.first + j])
        assert first == 63, (profile, x.number, first)
        assert mine[63]["score"] != whole[x.first + 63]["score"]


@pytest.mark.parametrize("profile", sorted(C.PROFILES))
def test_control_replay__e1c_a_schedule_a_block_late_differs_first_at_its_first_at_index_read(profile):
    whole = continuous(profile)
    x = pieces(profile)[2]
    mine = piece_records(profile, x, shift=64)
    places = list(K.read_places(x))
    differ = [j for j in places if dict(mine[j], index=mine[j]["index"] + x.first) != whole[x.first + j]]
    assert differ[0] == 127, (profile, differ[:3])
    assert dict(mine[63], index=mine[63]["index"] + x.first) == whole[x.first + 63], "the signal-free read before it"

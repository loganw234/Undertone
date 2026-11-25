"""E0C: the gate's short form of stage E0, cut into pieces, read and judged as the card's records will be.

The gate `statistics`, its positive case: round 1's short form (tests/test_seam_e0.py: amplitude 1/1, seed
2026112402, 4,000 injections, 512,128 frames) cut into four pieces of 1,000 trials, each run by the model as a
run of its own (seed advanced, schedule shifted). Every read of every trial equals the continuous short form's
exactly, so the count is round 1's short form's (1,999 found, 30 signal-free crossings: docs/VALIDATION.md,
2026-11-23), and it is inside the tolerance.

Its two named controls, as E0's gate has them: on the pieces' own samples, the coefficients the wrong way round,
and the score read one sample late, each fall outside the tolerance beyond the catch margin (z < -8). The late
read of each piece's last trial but the stream's last falls in the next piece's first frame: the reader does not
make a read outside its trial's piece, the control counts those, exactly three (pieces 0 to 2), and is judged on
the other 3,997. It says so.
"""
import test_seam_e0 as E0

from spec import constants as C
from model import run, source, weights
from stats import tolerance

from hw.e0c import pieces as P
from hw.e0c.e0c import OFFSETS

PIECES = 4
_made = {}


def test_e0c_the_reading_offsets_are_round_1s_and_cv5s():
    """hw/e0c/e0c.py's OFFSETS against two things it does not share. Round 1's reading (tests/test_seam_e0.py,
    `measure`): the at-index score is the record at place SPACING - 1 of its span, the signal-free one at place
    FIRST - 1, the late one at place 0 of the next span; a trial's truth record is at place FIRST. And CV5, on the
    model directly: a lone e0 at amplitude 1 in a stream otherwise zero has its largest score at truth + OFFSETS["at"],
    and the signal-free read's score there is 0, no pulse sample under it."""
    assert OFFSETS == {"at": E0.SPACING - 1 - E0.FIRST, "noise": E0.FIRST - 1 - E0.FIRST, "late": E0.SPACING - E0.FIRST}
    truth, length = 200, 400
    frames = [(0,)] * length
    sched = [{"index": truth, "pulse_id": C.PULSE_IDS["e0"], "amplitude_num": 1, "amplitude_den": 1}]
    recs, _t = run.detect(frames, sched, length, weights.matched_filter(E0.PROFILE, E0.E0, (1,)))
    scores = [r["score"] for r in recs]
    assert scores.index(max(scores)) == truth + OFFSETS["at"] and scores.count(max(scores)) == 1
    assert scores[truth + OFFSETS["noise"]] == 0 and all(s == 0 for s in scores[:truth + OFFSETS["noise"] + 1])


def made():
    if not _made:
        f, got = E0.short()
        length = E0.SPACING * (E0.GATE_N + 1)
        seed = E0.GATE_SEED + E0.GATE_AMPLITUDE
        cut = P.cut(length, P.even_bounds(E0.GATE_N + 1, PIECES, E0.SPACING), E0.GATE_N, seed, 1, E0.SPACING,
                    E0.FIRST, E0.TAPS)
        num, den = E0.AMPLITUDES[E0.GATE_AMPLITUDE]
        runs = []
        for piece in cut:
            sched = P.schedule_of(piece, E0.SPACING, E0.FIRST, C.PULSE_IDS["e0"], num, den)
            noise = source.Noise(E0.PROFILE, piece.seed, E0.SIGMA[0], E0.SIGMA[1], piece.frames)
            pairs, _t = run.scores(noise, sched, piece.frames, f["blob"])
            frames, data = [], bytearray()
            for frame, r in pairs:
                frames.append(frame)
                data += P.RECORD.pack(*[r[name] for name in P.SCORE_FIELDS])
            runs.append((piece, frames, bytes(data)))
        _made.update(f=f, got=got, cut=cut, runs=runs)
    return _made


def read_all(runs, offsets):
    out = dict((o, []) for o in offsets)
    for piece, _frames, data in runs:
        got = P.reads(data, piece, E0.SPACING, E0.FIRST, offsets)
        for o in offsets:
            out[o] += got[o]
    return out


def test_gate_statistics__e0c_the_short_form_in_pieces_reads_round_1s_scores_and_is_inside():
    m = made()
    f, got = m["f"], m["got"]
    assert [p.first for p in m["cut"]] == [0, 128000, 256000, 384000] and m["cut"][-1].frames == 128128
    assert [p.trials for p in m["cut"]] == [1000] * 4
    # the shipped offsets (hw/e0c/e0c.py's OFFSETS, which expect and compare share), held against round 1's own
    # reading in tests/test_seam_e0.py's `measure`, which picks records by their place in a span, not by offset
    r = read_all(m["runs"], (OFFSETS["at"], OFFSETS["noise"]))
    at, quiet = r[OFFSETS["at"]], r[OFFSETS["noise"]]
    assert None not in at and None not in quiet
    assert at == got["at_index"] and quiet == got["noise"], "every read in pieces is the continuous stream's"
    found, made_, not_made = P.count(at, f["threshold"])
    crossings = P.count(quiet, f["threshold"])[0]
    v = tolerance.check_efficiency(found, made_, E0.PFA, f["d"])
    print("E0C short form in %d pieces: found %d of %d, %+.2f se, %s; noise %d" % (PIECES, found, made_, v["z_score"],
          "INSIDE" if v["inside"] else "OUTSIDE", crossings))
    assert (found, made_, not_made, crossings) == (1999, 4000, 0, 30)
    assert v["inside"] and tolerance.check_count(crossings, made_, E0.PFA)["inside"]
    assert max(P.flags_seen(data) for _p, _f, data in m["runs"]) == 0


def test_control_statistics__e0c_coefficients_the_wrong_way_round_in_pieces_fall_outside():
    m = made()
    f = m["f"]
    wrong = weights.pack(E0.PROFILE, [{0: tuple(reversed(f["coeffs"]))}], (1,), E0.PASS, 1, 0)
    at = []
    for piece, frames, _data in m["runs"]:
        recs, _t = run.detect(frames, [], piece.frames, wrong)
        data = b"".join(P.RECORD.pack(*[r[name] for name in P.SCORE_FIELDS]) for r in recs)
        at += P.reads(data, piece, E0.SPACING, E0.FIRST, (OFFSETS["at"],))[OFFSETS["at"]]
    found, made_, not_made = P.count(at, f["threshold"])
    v = tolerance.check_efficiency(found, made_, E0.PFA, f["d"])
    print("CONTROL E0C in pieces, coefficients reversed: found %d of %d, %+.1f se, %s"
          % (found, made_, v["z_score"], "INSIDE" if v["inside"] else "OUTSIDE"))
    assert not_made == 0 and not v["inside"] and v["z_score"] < -8.0


def test_control_statistics__e0c_a_score_read_one_sample_late_in_pieces_falls_outside():
    m = made()
    f = m["f"]
    late = read_all(m["runs"], (OFFSETS["late"],))[OFFSETS["late"]]
    found, made_, not_made = P.count(late, f["threshold"])
    v = tolerance.check_efficiency(found, made_, E0.PFA, f["d"])
    print("CONTROL E0C in pieces, read one sample late: found %d of %d, %+.1f se, %s; %d late reads fall past their "
          "piece's end and are not made, the last trial of pieces 0 to %d"
          % (found, made_, v["z_score"], "INSIDE" if v["inside"] else "OUTSIDE", not_made, PIECES - 2))
    assert not_made == PIECES - 1 and made_ == E0.GATE_N - (PIECES - 1)
    missing = [t for t, s in enumerate(late) if s is None]
    assert missing == [p.first_trial + p.trials - 1 for p in m["cut"][:-1]]
    # the reads that are made are the continuous stream's late reads of those trials
    assert [s for s in late if s is not None] == [s for t, s in enumerate(m["got"]["late"]) if t not in missing]
    assert not v["inside"] and v["z_score"] < -8.0

"""The learner of phase B is round 2's rule: its set equals the trainer's hand-over of the same windows.

`learn.handover.candidate_blob` of `learn.trainer.MeanDifference`'s weights, for the windows both
accept, word for word. That is a regression check by construction (the learner calls the same
`quantise` and `pack`); its value is that the learner is the same rule and not a new one. Held three ways:

1. on injector streams where the trainer accepts every record, through `learn.trainer.train` itself:
   its own window rule, its own period, under both profiles and several taps and update indexes;
2. stage E1's own flow (train on the frames below A, hand over and commit at A), reproduced by
   `model.run.learning` with an update time of 0, every score record; and with an update time, the
   same blob committed later;
3. on injector streams with windows skipped (START, BUSY on either label), through `MeanDifference`
   fed exactly the windows the rule written out a second time in test_lrn_b_support takes. That rule
   is held here to `learn.trainer.labelled_windows` where the trainer takes a whole list.

The streams are the model's own noise, which differs channel by channel, with `e0` injected.
"""
import pytest

from model import run, source
from learn import handover, trainer

import test_lrn_b_support as S

SIGMA = (1477, 1)


def schedule(indexes):
    amps = [(5, 2), (3, 1), (-2, 1), (7, 4), (1, 1), (-9, 4)]
    return [S.rec(j, *amps[n % len(amps)]) for n, j in enumerate(indexes)]


def stream(profile, seed, length, indexes):
    """(the injected frames, as the core sees them; the raw noise for `model.run.learning` to inject into)."""
    frames, _truth = S.noise_frames(profile, seed, SIGMA, length, schedule(indexes))
    return frames, source.Noise(profile, seed, SIGMA[0], SIGMA[1], length)


def learned(profile, noise, length, indexes, taps, u, update_frames=0):
    """The learner's set at u, through `model.run.learning` with an update named at 0."""
    blob = S.start_blob(profile, taps)
    _records, truth, outcomes, learner = run.learning(noise, schedule(indexes), length, blob,
                                                       {0: [("update", u)]}, update_frames)
    assert outcomes == [(0, "update", u, None)]
    made = [x for x in learner.updates if x["u"] == u]
    assert len(made) == 1 and made[0]["blob"] is not None
    return made[0]["blob"], learner, truth


# ------------------------------------------------------------ 1. the trainer's own window rule

CASES = [  # (taps, spacing, first, records, the update indexes): every record accepted by the trainer
    (64, 128, 64, 12, (128 * 12, 128 * 7, 128 * 5)),
    (16, 64, 20, 20, (64 * 20 + 20, 64 * 9 + 36, 64 * 3)),
    (40, 96, 41, 14, (96 * 13 + 41 + 40, 96 * 6)),
]


@pytest.mark.parametrize("profile", S.PROFILES)
@pytest.mark.parametrize("taps, spacing, first, count, updates", CASES)
def test_lrn_b_trainer_the_set_is_train_and_candidate_blob_on_the_same_frames(profile, taps, spacing, first, count, updates):
    indexes = [first + spacing * n for n in range(count)]
    length = indexes[-1] + spacing
    seed = 2026112601 + taps
    frames, _noise = stream(profile, seed, length, indexes)
    checked = 0
    for u in updates:
        # the trainer is handed the frames below u and the records whose windows lie wholly below u
        inside = [j for j in indexes if j + taps <= u]
        assert not [j for j in indexes if j <= u < j + taps], "u inside a record's span: the trainer would refuse it"
        want = handover.candidate_blob(profile, trainer.train(S.as_array(frames[:u]), inside, taps).weights())
        got, learner, _ = learned(profile, stream(profile, seed, length, indexes)[1], length, indexes, taps, u)
        assert got == want, (profile, taps, u)
        assert learner.updates[0]["counts"] == (len(inside), len(inside))
        checked += 1
    assert checked == len(updates)


# ------------------------------------------------------------ 2. stage E1's own flow

E1_TAPS, E1_RECORDS, E1_HELD = 64, 16, 640


def e1_like(profile):
    """E1's layout: a trial every 128 frames with its pulse at frame 64; A = 128 N; then a held-out
    stretch with three more trials, which no update at A may see. Returns (A, indexes, the injected
    frames, the raw noise, the length)."""
    a = 128 * E1_RECORDS
    indexes = [128 * n + 64 for n in range(E1_RECORDS)] + [a + 128 * n + 64 for n in range(3)]
    length = a + E1_HELD
    frames, noise = stream(profile, 2026112650, length, indexes)
    return a, indexes, frames, noise, length


def e1_flow(profile, frames, indexes, a, commit_at):
    """E1's flow as tests/test_lrn_a_e1.py has it: the blank detector; when the next output is A, the
    learner trained on the frames and the truth below A, its blob written to the shadow and committed."""
    learner = trainer.train(S.as_array(frames[:a]), [j for j in indexes if j < a], E1_TAPS)
    blob = handover.candidate_blob(profile, learner.weights())
    records = S.frozen(handover.blank_blob(profile, E1_TAPS), frames, writes=[(a, blob)], commits=[(a, commit_at)])
    return records, blob


@pytest.mark.parametrize("profile", S.PROFILES)
def test_lrn_b_trainer_stage_e1s_flow_is_learning_with_no_update_time_every_record(profile):
    a, indexes, frames, noise, length = e1_like(profile)
    want, blob = e1_flow(profile, frames, indexes, a, a)
    assert handover.blank_blob(profile, E1_TAPS) == S.start_blob(profile, E1_TAPS)
    got, _truth, outcomes, learner = run.learning(noise, schedule(indexes), length,
                                                  handover.blank_blob(profile, E1_TAPS),
                                                  {0: [("update", a)], a: [("commit", a)]}, 0)
    assert [o[3] for o in outcomes] == [None, None]
    assert learner.updates[0]["blob"] == blob
    assert S.as_words(got) == S.as_words(want)
    assert got[a - 1]["epoch"] == 0 and got[a]["epoch"] == 1 and len({r["score"] for r in got[a:]}) > 1
    # the held-out trials are taken after A, and change nothing: there is no second update
    assert learner.counts == [E1_RECORDS + 3, E1_RECORDS + 3] and len(learner.updates) == 1


@pytest.mark.parametrize("profile", S.PROFILES)
@pytest.mark.parametrize("update_frames", [1, 64, 256])
def test_lrn_b_trainer_with_an_update_time_the_same_blob_is_committed_that_many_frames_later(profile, update_frames):
    a, indexes, frames, noise, length = e1_like(profile)
    commit = a + update_frames
    assert commit < length
    want, blob = e1_flow(profile, frames, indexes, a, commit)
    script = {0: [("update", a)], commit - 1: [("commit", commit)], commit: [("commit", commit)]}
    got, _truth, outcomes, learner = run.learning(noise, schedule(indexes), length,
                                                  handover.blank_blob(profile, E1_TAPS), script, update_frames)
    assert [o[3] for o in outcomes] == [None, "UPDATE_UNFINISHED", None]
    assert learner.updates[0]["blob"] == blob
    assert S.as_words(got) == S.as_words(want)
    assert got[commit - 1]["epoch"] == 0 and got[commit]["epoch"] == 1


# ------------------------------------------------------------ 3. streams with windows skipped

SKIPPING = [  # (taps, the indexes): records a pulse or more apart, so the injector takes them
    (48, [20, 84, 148, 300, 364, 520, 700]),        # START at 20; BUSY label 0 at 84, 148, 364
    (80, [90, 154, 400, 464, 528, 800, 1000]),      # BUSY label 1 where records are 64 apart; BUSY label 0 too
    (64, [64, 128, 320, 384, 700, 900]),            # exactly T apart: label 1 free, label 0 BUSY; 2T apart free
]


@pytest.mark.parametrize("profile", S.PROFILES)
@pytest.mark.parametrize("taps, indexes", SKIPPING)
def test_lrn_b_trainer_with_windows_skipped_the_set_is_the_trainers_of_the_windows_taken(profile, taps, indexes):
    length = indexes[-1] + taps + 20
    frames, noise = stream(profile, 2026112660 + taps, length, indexes)
    u = length
    blob, learner, _ = learned(profile, noise, length, indexes, taps, u)
    taken = [(first, label) for at, _j, label, o, first in S.judged(indexes, taps) if o == "taken" and at <= u]
    outcomes = {o for _a, _j, _l, o, _f in S.judged(indexes, taps)}
    assert "busy" in outcomes and ("start" in outcomes) == (taps == 48)
    mean = trainer.MeanDifference(S.channels(profile), taps)
    for first, label in taken:
        mean.update(S.as_array(frames[first:first + taps]), label)
    assert blob == handover.candidate_blob(profile, mean.weights())
    assert [(t[0], t[1], t[2], t[3]) for t in S.judged(indexes, taps)] == learner.log
    # the trainer refuses the whole list, by the name the rule maps to
    with pytest.raises(trainer.LearnRefusal) as e:
        trainer.labelled_windows(indexes, taps, length)
    assert e.value.name in ("WINDOW_OUTSIDE_PERIOD", "WINDOW_NOT_FREE", "TRAINER_INPUT")


@pytest.mark.parametrize("taps", [1, 2, 5, 48, 64])
def test_lrn_b_trainer_the_rule_written_again_is_labelled_windows_where_the_trainer_takes_the_list(taps):
    """On lists the trainer takes whole, every window it names is taken by the rule here, and no other."""
    for start, gap, count in ((taps, 2 * taps, 6), (3 * taps, 2 * taps + 1, 5), (taps + 7, 5 * taps, 4)):
        indexes = [start + gap * n for n in range(count)]
        period = indexes[-1] + taps
        want = sorted(trainer.labelled_windows(indexes, taps, period))
        got = sorted((first, label) for at, _j, label, o, first in S.judged(indexes, taps) if o == "taken")
        assert got == want, (taps, start, gap)

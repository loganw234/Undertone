"""D0's gate "truth isolation", restated for a learner in the stream (Logan's word on question 3, round 5).

The restatement: no path from a truth record to any output record except through a set the learner
makes and a commit the host names. In observable form, held here on `model.run.learning`:

  - the same samples under different truth records give identical score records up to the first named
    commit, and identical events and histogram from a scorer fed them;
  - after it, the score records are those of a core with no learner, the learner's set written to its
    shadow and committed at the same indexes.

The core starts from the matched filter for `e0`, with a gain of its own on each channel, so that every
record before the commit carries a score that a leak would move.

How the same samples come with different truth: one stream of samples, already carrying its pulses, is
run again under schedules that add nothing to it and say other things (the real indexes at amplitude
zero; other indexes at amplitude zero, which are labels with no pulse; the second pulse's id at
amplitude zero; no record at all); and the real schedule is run beside the same with every amplitude
written another way (n/d as 2n/2d). Each run names the same update and the same commit.

The controls plant what the restatement forbids: truth reaching a score with no commit (a learner that
hands the core a changed frame at a truth index), a commit the learner makes itself, a commit at an
index no one named (one late, one early), and a learner that reads a truth record's amplitude or pulse
id. Each is reported by the same check at the record where it acts.

What this cannot see, stated: a learner that reads more of the truth than its index and lets it change
no output record, or changes one only for a field none of these schedules varies (they vary whether
there is a record, its index, its amplitude's numerator and denominator, and its pulse id); and anything
about a learner other than `model.learner.Learner` run through `model.run.learning`.
"""
import pytest

from spec import constants as C
from model import inject, records, run, source, weights
from model.learner import Learner
from model.scorer import Scorer

import test_lrn_b_support as S

TAPS = len(C.PULSES["e0"])
LENGTH = 2400
SEED = 20261127
SIGMA = (900, 1)
REAL = [S.rec(200, 3), S.rec(456, 5, 2), S.rec(712, -2), S.rec(968, 7, 4), S.rec(1400, 2)]
U, COMMIT, FRAMES = 1100, 1300, 64
GAINS = {"s16x1": (1,), "s24x3": (2, -1, 3)}


def start(profile):
    return weights.matched_filter(profile, C.PULSES["e0"], GAINS[profile])


def rewritten(schedule):
    """The same records with every amplitude written another way: n/d as 2n/2d."""
    return [dict(r, amplitude_num=2 * r["amplitude_num"], amplitude_den=2 * r["amplitude_den"]) for r in schedule]


def other_truths():
    return [("the real indexes at amplitude zero", [S.rec(r["index"], 0) for r in REAL]),
            ("other indexes at amplitude zero", [S.rec(j, 0) for j in (130, 330, 586, 842, 1500)]),
            ("the real indexes, the second pulse at amplitude zero", [S.rec(r["index"], 0, 1, "e1") for r in REAL]),
            ("no record at all", [])]


def noise_of(profile):
    return source.Noise(profile, SEED, SIGMA[0], SIGMA[1], LENGTH)


def samples(profile):
    injected, _truth = inject.inject(profile, noise_of(profile), REAL, LENGTH)
    return [tuple(f) for f in injected]


def script(commit=True):
    s = {50: [("update", U)]}
    if commit:
        s[U + FRAMES] = [("commit", COMMIT)]
    return s


def learn_run(frames, schedule, profile, commit=True, runner=run.learning):
    return runner(iter(frames), schedule, LENGTH, start(profile), script(commit), FRAMES)


def frozen_expectation(profile, frames, learner, commit=True):
    """A core with no learner: the learner's set, if it made one, written at U and committed at COMMIT."""
    made = [u["blob"] for u in learner.updates if u["u"] == U]
    writes = [(U, made[0])] if made and made[0] is not None else []
    return S.frozen(start(profile), frames, writes, [(U + FRAMES, COMMIT)] if commit else [])


def isolation_findings(profile, runner=run.learning, commit=True):
    """Run the real stream with its truth, then the same samples under each other truth. Findings: empty
    when every run agrees with the restatement and the comparison was not of nothing."""
    real, _truth, outcomes, learner = learn_run(noise_of(profile), REAL, profile, commit, runner)
    if len(real) != LENGTH or [o[3] for o in outcomes] != [None] * len(outcomes):
        return ["NOTHING-COMPARED: the real run gave %d records and outcomes %s" % (len(real), outcomes)]
    frames = samples(profile)
    findings = []
    edge = COMMIT if commit else LENGTH
    want = frozen_expectation(profile, frames, learner, commit)
    first = S.first_difference(S.as_words(real), S.as_words(want))
    if first is not None:
        findings.append("the real run is not the frozen model with its set, first at index %d" % first)
    sets = {learner.updates[0]["blob"]}
    runs = [("the amplitudes written another way", rewritten(REAL), noise_of(profile))] + \
           [(what, sched, frames) for what, sched in other_truths()]
    for what, sched, stream in runs:
        got, _t, outs, other = learn_run(stream, sched, profile, commit, runner)
        if [o[3] for o in outs] != [o[3] for o in outcomes]:
            findings.append("%s: the operations' outcomes differ: %s" % (what, outs))
            continue
        first = S.first_difference(S.as_words(real[:edge]), S.as_words(got[:edge]))
        if first is not None:
            findings.append("%s: the score records differ before the first commit, first at index %d" % (what, first))
        later = S.first_difference(S.as_words(got), S.as_words(frozen_expectation(profile, frames, other, commit)))
        if later is not None:
            findings.append("%s: the records are not the frozen model's with this learner's set, first at index %d"
                            % (what, later))
        sets.add(other.updates[0]["blob"])
    if len(sets) < 3:
        findings.append("NOTHING-COMPARED: the truths gave %d different sets" % len(sets))
    return findings


# ------------------------------------------------------------ the gate, restated

@pytest.mark.parametrize("profile", S.PROFILES)
def test_gate_truth_isolation__the_same_samples_under_other_truth_give_the_same_records_until_the_named_commit(profile):
    assert isolation_findings(profile) == []


@pytest.mark.parametrize("profile", S.PROFILES)
def test_gate_truth_isolation__with_an_update_and_no_commit_every_record_is_the_same_under_every_truth(profile):
    assert isolation_findings(profile, commit=False) == []
    real, _t, _o, learner = learn_run(noise_of(profile), REAL, profile, commit=False)
    assert S.as_words(real) == S.as_words(S.frozen(start(profile), samples(profile)))
    assert learner.updates[0]["blob"] is not None and learner.counters()["lrn_made"] == 1


@pytest.mark.parametrize("profile", S.PROFILES)
def test_gate_truth_isolation__a_scorers_events_and_histogram_are_the_same_under_every_truth(profile):
    """A scorer fed the records before the commit: the same events and histogram under every truth."""
    frames = samples(profile)
    seen = []
    for sched, stream in [(REAL, noise_of(profile))] + [(s, frames) for _w, s in other_truths()]:
        recs, _t, _o, _l = learn_run(stream, sched, profile)
        scorer = Scorer(profile, 10 ** 8, 4, 4, 0, 24, 64)
        for i in range(COMMIT):
            scorer.feed(frames[i], recs[i])
        scorer.close()
        seen.append((records.digest("event", scorer.events), scorer.crossings, tuple(scorer.histogram()["bins"])))
    assert len(set(seen)) == 1 and seen[0][1] > 0


# ------------------------------------------------------------ the controls

class HandsTheCoreAChangedFrame(Learner):
    """Truth reaching a score with no commit: the frame at a truth index has its first sample moved by one."""

    def step(self, frame):
        if self.next_index in self.indexes:
            frame = (frame[0] + 1,) + frame[1:]
        return super().step(frame)


class CommitsItself(Learner):
    """A commit the learner triggers itself, at its update's finish."""

    def _finish(self):
        at = self._update["finish"]
        super()._finish()
        self.core.commit(at)


def commits_at(shift):
    class CommitsElsewhere(Learner):
        """A commit at an index no one named: the one named, moved."""

        def commit(self, at):
            super().commit(at + shift)
    return CommitsElsewhere


def runner_with(make):
    """`model.run.learning` with another learner in it."""
    def runner(frames, schedule, length, blob, script, update_frames):
        injected, truth = inject.inject(weights.unpack(blob)["profile"], frames, schedule, length)
        learner = make(blob, truth, update_frames)
        records_, outcomes = run._learning_run(learner, injected, script)
        return records_, truth, outcomes, learner
    return runner


@pytest.mark.parametrize("profile", S.PROFILES)
def test_gate_truth_isolation__the_runner_the_controls_use_is_clean_with_the_real_learner_in_it(profile):
    assert isolation_findings(profile, runner_with(Learner)) == []


@pytest.mark.parametrize("profile", S.PROFILES)
def test_control_truth_isolation__truth_reaching_a_score_with_no_commit_is_reported(profile):
    findings = isolation_findings(profile, runner_with(HandsTheCoreAChangedFrame), commit=False)
    print("CONTROL truth reaching a score:", findings)
    # The first record whose window meets frame j = 200 under a coefficient of channel 0 that is not zero:
    # record i meets it at tap j - i + T - 1, and e0's last sample, the newest tap's, is 0.
    row = S.rows_of(start(profile))[0]
    j = REAL[0]["index"]
    first = min(i for i in range(j, j + TAPS) if row[j - i + TAPS - 1] != 0)
    assert row[TAPS - 1] == 0 and first == j + 1
    assert "the real run is not the frozen model with its set, first at index %d" % first in findings


@pytest.mark.parametrize("profile", S.PROFILES)
def test_control_truth_isolation__a_commit_the_learner_makes_itself_is_reported(profile):
    findings = isolation_findings(profile, runner_with(CommitsItself), commit=False)
    print("CONTROL a commit the learner makes itself:", findings)
    assert "the real run is not the frozen model with its set, first at index %d" % (U + FRAMES) in findings


@pytest.mark.parametrize("profile", S.PROFILES)
@pytest.mark.parametrize("shift", [1, -1])
def test_control_truth_isolation__a_commit_at_an_index_no_one_named_is_seen_at_that_record(profile, shift):
    findings = isolation_findings(profile, runner_with(commits_at(shift)))
    print("CONTROL a commit at %+d:" % shift, findings)
    assert "the real run is not the frozen model with its set, first at index %d" % min(COMMIT, COMMIT + shift) in findings


def reads_more_than_the_index(field, value):
    class ReadsMore(Learner):
        """Reads a truth record's `field`: a record whose field is `value` is not taken as a label."""

        @staticmethod
        def _read_indexes(truth):
            return Learner._read_indexes([r for r in truth if r[field] != value])
    return ReadsMore


@pytest.mark.parametrize("profile", S.PROFILES)
@pytest.mark.parametrize("field, value", [("amplitude_num", 0), ("pulse_id", C.PULSE_IDS["e1"])])
def test_control_truth_isolation__a_learner_reading_the_amplitude_or_the_pulse_id_gives_another_output(profile, field, value):
    """The same frames and a copy of the truth with one record's `field` changed, and nothing else: the
    learner reads the index alone, so its output is the same; one that reads the field is not."""
    frames = samples(profile)
    copy = [dict(r) for r in REAL]
    copy[2][field] = value
    outs = {}
    for name, make in (("the learner", Learner), ("one reading %s" % field, reads_more_than_the_index(field, value))):
        base, _o, a = S.drive(start(profile), frames, REAL, script(), FRAMES, make=make)
        changed, _o, b = S.drive(start(profile), frames, copy, script(), FRAMES, make=make)
        outs[name] = (S.first_difference(S.as_words(base), S.as_words(changed)), a.counters() == b.counters())
    print("CONTROL reading %s: %s" % (field, outs))
    assert outs["the learner"] == (None, True)
    assert outs["one reading %s" % field] == (COMMIT, False)


@pytest.mark.parametrize("profile", S.PROFILES)
def test_control_truth_isolation__with_a_commit_the_records_differ_from_the_frozen_models(profile):
    """The commit is not of nothing: from the commit's index the records are not those of the start set."""
    real, _t, _o, _l = learn_run(noise_of(profile), REAL, profile)
    first = S.first_difference(S.as_words(real), S.as_words(S.frozen(start(profile), samples(profile))))
    print("CONTROL the frozen model: first difference at index", first)
    assert first == COMMIT

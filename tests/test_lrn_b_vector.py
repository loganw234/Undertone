"""The learner of phase B against the hand-worked vector, vectors/lrn-b/cases.json.

Every case is run through `model.learner.Learner` as `model.run.learning` runs it, with the frames as
given: the judgements, each update's counts, sums, D and set, the outcome of every host operation, the
counters, the status, and every score record are the vector's. Then three of the brief's named
controls, each on the vector: a learner that rounds half away from zero, one that drops the last window
before an update, and one that takes a label-0 window the trainer refuses. Each must give another set,
or another count, where the trainer's own hand-over (`learn.handover.candidate_blob` of a
`learn.trainer.MeanDifference` given the windows the learner took) gives the vector's.

The expected answers are the vector's, worked by hand; nothing here produces one.
"""
import numpy as np
import pytest

from learn import handover, trainer
from model.learner import Learner

import test_lrn_b_support as S

NAMES = [c["name"] for c in S.cases()]


def case_named(name):
    return [c for c in S.cases() if c["name"] == name][0]


def trainers_blob(case, upto=None):
    """The trainer's hand-over over the windows the vector's case takes (at or before `upto`)."""
    taps, frames = case["taps"], case["frames"]
    learner = trainer.MeanDifference(S.channels(case["profile"]), taps)
    count_max = (1 << case["count_bits"]) - 1
    for at, _j, label, o, first in S.judged(case["truth_indexes"], taps, count_max):
        if o == "taken" and (upto is None or at <= upto):
            learner.update(np.array(frames[first:first + taps], dtype=np.int64), label)
    return handover.candidate_blob(case["profile"], learner.weights())


@pytest.mark.parametrize("name", NAMES)
def test_lrn_b_vector_each_case_is_the_learners_word_for_word(name):
    case = case_named(name)
    records, outcomes, learner = S.run_case(case)
    assert [list(t) for t in learner.log] == case["judged"]
    assert [[i, op, a, n] for i, op, a, n in outcomes] == case["outcomes"]
    assert len(learner.updates) == len(case["updates"])
    for got, want in zip(learner.updates, case["updates"]):
        assert (got["u"], got["finish"], list(got["counts"]), got["outcome"]) == \
               (want["u"], want["finish"], want["counts"], want["outcome"])
        assert [list(map(list, s)) for s in got["sums"]] == [want["sum_label_0"], want["sum_label_1"]]
        assert list(got["difference"]) == want["difference"]
        assert max(abs(x) for x in got["difference"]) == want["peak"]
        assert (S.rows_of(got["blob"]) if got["blob"] is not None else None) == want["coefficients"]
        assert got["name"] == want.get("name")
    assert learner.counters() == case["counters"]
    assert learner.status() == case["status"]
    assert S.as_words(records) == case["scores"]


@pytest.mark.parametrize("name", NAMES)
def test_lrn_b_vector_each_set_is_the_trainers_hand_over_of_the_same_windows(name):
    """The regression by construction: the same windows, the trainer's rule and hand-over, the same blob."""
    case = case_named(name)
    _records, _outcomes, learner = S.run_case(case)
    for got in learner.updates:
        if got["blob"] is not None:
            assert got["blob"] == trainers_blob(case, got["u"]), (name, got["u"])


def test_lrn_b_vector_the_case_with_no_truth_is_the_vectors():
    case = case_named("s16x1-the-tie")
    want = case["controls"]["no_truth"]
    records, outcomes, learner = S.run_case(case, indexes=[])
    assert learner.counters() == want["counters"]
    assert [u["outcome"] for u in learner.updates] == [want["update_outcome"]]
    assert [o[3] for o in outcomes] == [None, "UPDATE_UNFINISHED", "UPDATE_UNFINISHED", None]
    assert all(r["score"] == 0 and r["flags"] == 0 for r in records)
    assert [r["epoch"] for r in records] == [0] * 15 + [1] * 3


# ------------------------------------------------------------ the brief's controls, on the vector

class HalfAway(Learner):
    """Rounds half away from zero, in place of half to even."""

    def _quantise(self, d):
        m = max(abs(x) for x in d)
        if m == 0:
            return super()._quantise(d)
        return [S.nearest_away(x * S.C.COEFF_MAX, m) for x in d]


class DropsTheLastWindow(Learner):
    """Makes an update before judging the windows due at its own index: the last window before it is lost."""

    def _at(self, n):
        if self._update is not None and not self._update["made"] and self._update["u"] == n:
            self._make()
        for j, p, q, label in self._due.pop(n, ()):
            self._judge(n, j, p, q, label)
        if self._update is not None and self._update["made"] and self._update["finish"] == n:
            self._finish()


def takes_label_0_of(index):
    class TakesARefusedWindow(Learner):
        """Takes the one label-0 window of the record at `index`, which the trainer refuses."""

        def _start(self, j):
            return j != index and super()._start(j)

        def _busy0(self, j, p):
            return j != index and super()._busy0(j, p)
    return TakesARefusedWindow


@pytest.mark.parametrize("name", ["s16x1-the-tie", "s24x3-ties-on-three-channels"])
def test_lrn_b_vector_control_a_learner_rounding_half_away_from_zero_differs_from_the_trainers_hand_over(name):
    case = case_named(name)
    want = case["controls"]["half_away_from_zero"]["coefficients"]
    _r, _o, broken = S.run_case(case, make=HalfAway)
    got = S.rows_of(broken.updates[-1]["blob"])
    trainers = S.rows_of(trainers_blob(case))
    print("CONTROL half away from zero, %s: the learner's set %s, the trainer's hand-over %s" % (name, got, trainers))
    assert got == want and trainers == case["updates"][-1]["coefficients"] and got != trainers


def test_lrn_b_vector_control_a_learner_dropping_the_last_window_before_an_update_gives_another_set():
    case = case_named("s16x1-the-tie")
    want = case["controls"]["last_window_dropped"]
    _r, _o, broken = S.run_case(case, make=DropsTheLastWindow)
    u = broken.updates[0]
    print("CONTROL last window dropped: counts %s, D %s, set %s; the vector's %s"
          % (list(u["counts"]), list(u["difference"]), S.rows_of(u["blob"]), case["updates"][0]["coefficients"]))
    assert list(u["counts"]) == want["counts"] and list(u["difference"]) == want["difference"]
    assert S.rows_of(u["blob"]) == want["coefficients"] != case["updates"][0]["coefficients"]
    assert u["blob"] != trainers_blob(case)


def test_lrn_b_vector_control_a_learner_taking_a_label_0_window_the_trainer_refuses_gives_another_set_and_count():
    case = case_named("s16x1-the-tie")
    want = case["controls"]["label_0_of_4_taken"]
    with pytest.raises(trainer.LearnRefusal) as e:
        trainer.labelled_windows(case["truth_indexes"], case["taps"], len(case["frames"]))
    assert e.value.name == "WINDOW_NOT_FREE"
    _r, _o, broken = S.run_case(case, make=takes_label_0_of(4))
    u = broken.updates[0]
    print("CONTROL label 0 of 4 taken: counts %s, set %s; the vector's %s"
          % (list(u["counts"]), S.rows_of(u["blob"]), case["updates"][0]["coefficients"]))
    assert list(u["counts"]) == want["counts"] and [list(r) for r in u["sums"][0]] == want["sum_label_0"]
    assert list(u["difference"]) == want["difference"] and S.rows_of(u["blob"]) == want["coefficients"]
    assert broken.counters()["lrn_count0"] == 2 != case["counters"]["lrn_count0"]


def test_lrn_b_vector_control_a_learner_taking_a_window_that_starts_before_frame_0_gives_another_outcome():
    case = case_named("s16x1-start-and-an-unmade-update")
    want = case["controls"]["label_0_of_1_taken"]
    _r, _o, broken = S.run_case(case, make=takes_label_0_of(1))
    first = broken.updates[0]
    print("CONTROL label 0 of 1 taken: the first update %s with set %s, where the vector's is %s"
          % (first["outcome"], S.rows_of(first["blob"]), case["updates"][0]["outcome"]))
    w = want["first_update"]
    assert (list(first["counts"]), list(first["difference"]), first["outcome"]) == (w["counts"], w["difference"], w["outcome"])
    assert S.rows_of(first["blob"]) == w["coefficients"]
    assert broken.counters()["lrn_count0"] == want["lrn_count0"] != case["counters"]["lrn_count0"]


def test_lrn_b_vector_control_a_learner_taking_windows_past_its_count_gives_another_set():
    case = case_named("s24x3-full-at-a-small-count")
    want = case["controls"]["full_windows_taken"]

    class NeverFull(Learner):
        def _full(self, label):
            return False
    _r, _o, broken = S.run_case(case, make=NeverFull)
    u = broken.updates[0]
    assert list(u["counts"]) == want["counts"] and list(u["difference"]) == want["difference"]
    assert u["blob"] != S.run_case(case)[2].updates[0]["blob"]

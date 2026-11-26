"""The learner's counts and refusals, each by its name, and each condition removed alone.

Round 4's verifiers found three times a check the code had that no test held. So for every condition
`model/learner.py` checks there is a test here that a learner with that condition alone removed (a
subclass, or a patched copy made inside the test) fails:

  the windows: START, BUSY on label 0, BUSY on label 1 from the record before, from the record after,
               FULL; at each one's boundary;
  the host's operations: UPDATE_UNFINISHED for an update, a commit and a shadow write, each alone;
               SWAP_SHAPE, SWAP_PENDING and SWAP_INDEX for an update; the order of each pair;
  the learner made: LEARN_BOUND, RECORD_FIELD, RECORD_ORDER, and their order with the blob's own;
  the update: made at u from the sums at u (the snapshot); finished at u + F, not one frame either side;
               its outcome published at the finish, not when it is made; a set that makes no set
               leaving the shadow as it was.

Every expected count is typed here from the design's table, worked by hand on each stream.
"""
import pytest

from spec import constants as C
from model import learner as L
from model import run as run_
from model import weights
from model.learner import Learner
from model.refusal import Refusal

import test_lrn_b_support as S

T = 4
STREAM = [2, 10, 15, 30, 32, 50]        # START at 2; BUSY: label 0 of 15 and of 32, label 1 of 30 and of 32
STREAM_COUNTS = {"lrn_count0": 3, "lrn_count1": 4, "lrn_skip_start": 1, "lrn_skip_busy": 4, "lrn_skip_full": 0,
                 "lrn_made": 0, "lrn_unmade": 0, "lrn_early": 0}


def varied(profile, n):
    """Frames whose channels differ from one another and from frame to frame."""
    return [tuple(((i * 37 + c * 101) % 61) - 30 for c in range(S.channels(profile))) for i in range(n)]


def run(profile, indexes, script=None, make=Learner, length=60, frames_=3, count_bits=C.LEARN_COUNT_BITS):
    frames = varied(profile, length)
    return S.drive(S.start_blob(profile, T), frames, [S.rec(j) for j in indexes], script or {}, frames_,
                   count_bits, make)


def refused(call):
    try:
        call()
        return None
    except Refusal as e:
        return e.name


def fresh(profile, make=Learner, frames_=3, blob=None, steps=0):
    learner = make(blob or S.start_blob(profile, T), [], frames_)
    for f in varied(profile, steps):
        learner.step(f)
    return learner


# ------------------------------------------------------------ the windows, by name

@pytest.mark.parametrize("profile", S.PROFILES)
def test_lrn_b_counts_each_name_counts_the_windows_it_names(profile):
    _r, _o, learner = run(profile, STREAM)
    assert learner.counters() == STREAM_COUNTS
    assert learner.log == [t[:4] for t in S.judged(STREAM, T)]
    assert [o for _n, _j, _l, o in learner.log].count("taken") == 7


class NoStart(Learner):
    def _start(self, j):
        return False


class NoBusy0(Learner):
    def _busy0(self, j, p):
        return False


class NoBusy1Before(Learner):
    def _busy1_before(self, j, p):
        return False


class NoBusy1After(Learner):
    def _busy1_after(self, j, q):
        return False


class NoFull(Learner):
    def _full(self, label):
        return False


@pytest.mark.parametrize("profile", S.PROFILES)
@pytest.mark.parametrize("make, changed", [
    (NoStart, {"lrn_count0": 4, "lrn_skip_start": 0}),
    (NoBusy0, {"lrn_count0": 5, "lrn_skip_busy": 2}),
    (NoBusy1Before, {"lrn_count1": 5, "lrn_skip_busy": 3}),
    (NoBusy1After, {"lrn_count1": 5, "lrn_skip_busy": 3}),
])
def test_lrn_b_counts_control_each_window_condition_removed_alone_changes_the_counts(profile, make, changed):
    _r, _o, broken = run(profile, STREAM, make=make)
    want = dict(STREAM_COUNTS, **changed)
    print("CONTROL %s: %s" % (make.__name__, broken.counters()))
    assert broken.counters() == want != STREAM_COUNTS
    which = {NoBusy1Before: (36, 32), NoBusy1After: (34, 30)}.get(make)
    if which:            # the two label-1 removals differ in which window they take
        assert (which[0], which[1], 1, "taken") in broken.log


@pytest.mark.parametrize("profile", S.PROFILES)
@pytest.mark.parametrize("indexes, judgement, outcome", [
    ([4, 4 + 2 * T], (4 + 2 * T, 4 + 2 * T, 0), "taken"),          # label 0, exactly 2T after: free
    ([4, 4 + 2 * T - 1], (4 + 2 * T - 1, 4 + 2 * T - 1, 0), "busy"),
    ([8, 8 + T], (8 + T, 8, 1), "taken"),                           # label 1, the next exactly T on: free
    ([8, 8 + T - 1], (8 + T, 8, 1), "busy"),
    ([8, 8 + T - 1], (8 + T - 1 + T, 8 + T - 1, 1), "busy"),       # and the next's, from the one before
    ([T], (T, T, 0), "taken"),                                      # START: at T free
    ([T - 1], (T - 1, T - 1, 0), "start"),
])
def test_lrn_b_counts_each_condition_at_its_boundary(profile, indexes, judgement, outcome):
    _r, _o, learner = run(profile, indexes)
    assert judgement + (outcome,) in learner.log


@pytest.mark.parametrize("profile", S.PROFILES)
def test_lrn_b_counts_full_at_a_small_count_and_its_removal(profile):
    indexes = [4, 12, 20, 28, 36]           # 2T apart: every window free; at most 3 a label
    _r, _o, learner = run(profile, indexes, count_bits=2)
    assert learner.counters()["lrn_skip_full"] == 4 and learner.counts == [3, 3]
    assert [t for t in learner.log if t[3] == "full"] == [(28, 28, 0, "full"), (32, 28, 1, "full"),
                                                           (36, 36, 0, "full"), (40, 36, 1, "full")]
    _r, _o, broken = run(profile, indexes, count_bits=2, make=NoFull)
    print("CONTROL NoFull: %s" % broken.counters())
    assert broken.counts == [5, 5] and broken.counters()["lrn_skip_full"] == 0


@pytest.mark.parametrize("profile", S.PROFILES)
def test_lrn_b_counts_full_at_the_definitions_count_from_a_written_state(profile):
    """2^32 - 1 windows a label, reached from a written state: the counts set to 2^32 - 2 before frame 0."""
    most = (1 << C.LEARN_COUNT_BITS) - 1
    learner = Learner(S.start_blob(profile, T), [S.rec(4), S.rec(12)], 3)
    learner.counts = [most - 1, most - 1]
    for f in varied(profile, 20):
        learner.step(f)
    assert [t[3] for t in learner.log] == ["taken", "taken", "full", "full"]
    assert learner.counts == [most, most] and learner.counters()["lrn_skip_full"] == 2


# ------------------------------------------------------------ the order of the window checks, where two or three hold

@pytest.mark.parametrize("profile", S.PROFILES)
def test_lrn_b_counts_a_label_1_window_both_busy_and_full_is_counted_busy(profile):
    """At a count width of 1 (one window a label), records at 8, 20 and 21, T = 2. Label 1 of 20 is BUSY
    (21 is less than T after it) and its label is full; so is label 1 of 21 (20 is less than T before it).
    BUSY is checked first: BUSY 3 (label 0 of 21, label 1 of 20, label 1 of 21) and FULL 1 (label 0 of 20).
    With FULL first for label 1 the same stream gives BUSY 1 and FULL 3."""
    learner = Learner(S.start_blob(profile, 2), [S.rec(j) for j in (8, 20, 21)], 3, 1)
    for f in varied(profile, 30):
        learner.step(f)
    assert learner.log == [(8, 8, 0, "taken"), (10, 8, 1, "taken"), (20, 20, 0, "full"), (21, 21, 0, "busy"),
                           (22, 20, 1, "busy"), (23, 21, 1, "busy")]
    c = learner.counters()
    assert (c["lrn_skip_busy"], c["lrn_skip_full"], c["lrn_count0"], c["lrn_count1"]) == (3, 1, 1, 1)


@pytest.mark.parametrize("profile", S.PROFILES)
@pytest.mark.parametrize("indexes, written, judgement", [
    ([1, 3], False, (3, 3, 0, "start")),       # START and BUSY: 3 < T, and 3 - 1 < 2T
    ([4, 12, 14], False, (14, 14, 0, "busy")), # BUSY and FULL, at a width of 1: 14 - 12 < 2T, and label 0 of 4 is taken
    ([1], True, (1, 1, 0, "start")),           # START and FULL: the counts written at their most after the learner is made
    ([1, 3], True, (3, 3, 0, "start")),        # all three
])
def test_lrn_b_counts_label_0s_order_is_start_then_busy_then_full_where_two_or_three_hold(profile, indexes, written, judgement):
    learner = Learner(S.start_blob(profile, T), [S.rec(j) for j in indexes], 3, 1)
    if written:
        learner.counts = [1, 1]              # 2^1 - 1: each label at its most
    for f in varied(profile, 24):
        learner.step(f)
    assert judgement in learner.log, learner.log


# ------------------------------------------------------------ the host's operations, by name and in order

def other_shapes(profile):
    c = S.channels(profile)
    rows = {k: (1,) * T for k in range(c)}
    out = [("a pool of 2", weights.pack(profile, [rows], (1,), S.PASS, 2, 0)),
           ("abs", weights.pack(profile, [rows], (1,), C.RECTIFIERS["abs"], 1, 0)),
           ("a shift", weights.pack(profile, [rows], (1,), S.PASS, 1, 1)),
           ("two filters", weights.pack(profile, [rows, rows], (1, 1), S.PASS, 1, 0)),
           ("a hidden layer", weights.pack(profile, [rows], (1,), S.PASS, 1, 0, hidden=[(1,)], hidden_shift=0, between=S.PASS))]
    if c > 1:
        out.append(("a filter on one channel of %d" % c, weights.pack(profile, [{0: (1,) * T}], (1,), S.PASS, 1, 0)))
    return out


@pytest.mark.parametrize("profile", S.PROFILES)
def test_lrn_b_counts_an_update_is_refused_by_each_name(profile):
    other = S.blob_of(profile, [[1] * T] * S.channels(profile))
    # UPDATE_UNFINISHED, and before SWAP_INDEX
    a = fresh(profile, steps=2)
    a.update(5)
    assert refused(lambda: a.update(6)) == refused(lambda: a.update(0)) == "UPDATE_UNFINISHED"
    # SWAP_SHAPE, for each shape that is not the matched-filter configuration; and before SWAP_PENDING and SWAP_INDEX
    for what, blob in other_shapes(profile):
        b = fresh(profile, blob=blob, steps=2)
        assert refused(lambda: b.update(5)) == "SWAP_SHAPE", what
        b.commit(4)
        assert refused(lambda: b.update(0)) == "SWAP_SHAPE", what
    # SWAP_PENDING, and before SWAP_INDEX
    c = fresh(profile, steps=2)
    c.write_shadow(other)
    c.commit(6)
    assert refused(lambda: c.update(8)) == refused(lambda: c.update(0)) == "SWAP_PENDING"
    # SWAP_INDEX
    d = fresh(profile, steps=3)
    for at in (2, -1, True, 3.0, "4", L.INDEX_MAX - d.update_frames + 1):
        assert refused(lambda: d.update(at)) == "SWAP_INDEX", at
    assert refused(lambda: d.update(L.INDEX_MAX - d.update_frames)) is None


@pytest.mark.parametrize("profile", S.PROFILES)
def test_lrn_b_counts_an_update_is_refused_unfinished_ahead_of_another_shape_when_both_hold(profile):
    """Both cannot hold by the operations alone: an update is named only under the matched shape, and a
    shape is frozen while the core runs. So the state is written: a learner under another shape, with an
    update written in as named and unfinished. UPDATE_UNFINISHED is named first."""
    for what, blob in other_shapes(profile):
        learner = fresh(profile, blob=blob, steps=2)
        assert refused(lambda: learner.update(5)) == "SWAP_SHAPE", what
        learner._update = {"u": 5, "finish": 8, "made": False, "counts": None, "sums": None,
                           "difference": None, "blob": None, "name": None, "outcome": None}
        assert refused(lambda: learner.update(6)) == "UPDATE_UNFINISHED", what


@pytest.mark.parametrize("profile", S.PROFILES)
def test_lrn_b_counts_an_update_at_a_bool_is_refused_where_its_int_would_be_taken(profile):
    """False is 0 and True is 1 to `isinstance(..., int)`: each named where that int is a taken index."""
    at_zero = fresh(profile, steps=0)
    assert refused(lambda: at_zero.update(False)) == "SWAP_INDEX"
    assert refused(lambda: fresh(profile, steps=0).update(0)) is None
    at_one = fresh(profile, steps=1)
    assert refused(lambda: at_one.update(True)) == "SWAP_INDEX"
    assert refused(lambda: fresh(profile, steps=1).update(1)) is None


@pytest.mark.parametrize("profile", S.PROFILES)
def test_lrn_b_counts_a_truth_index_at_the_fields_most_is_taken_and_one_past_it_refused(profile):
    blob = S.start_blob(profile, T)
    assert Learner(blob, [S.rec(5), S.rec(L.INDEX_MAX)], 3).indexes == (5, L.INDEX_MAX)
    assert L.INDEX_MAX == (1 << 64) - 1
    assert refused(lambda: Learner(blob, [S.rec(5), dict(S.rec(0), index=L.INDEX_MAX + 1)], 3)) == "RECORD_FIELD"


@pytest.mark.parametrize("profile", S.PROFILES)
def test_lrn_b_counts_a_record_at_index_0_is_counted_start_when_the_learner_is_made(profile):
    """Its label-0 window is judged at next index 0, which is reached when the learner is made, before any frame."""
    learner = Learner(S.start_blob(profile, T), [S.rec(0), S.rec(20)], 3)
    assert learner.log == [(0, 0, 0, "start")] and learner.counters()["lrn_skip_start"] == 1
    for f in varied(profile, T):
        learner.step(f)
    assert learner.log == [(0, 0, 0, "start"), (T, 0, 1, "taken")]


@pytest.mark.parametrize("profile", S.PROFILES)
def test_lrn_b_counts_a_commit_and_a_shadow_write_are_refused_while_an_update_is_unfinished_and_counted(profile):
    a = fresh(profile, steps=2)
    a.update(5)
    assert refused(lambda: a.commit(8)) == "UPDATE_UNFINISHED"
    assert refused(lambda: a.commit(0)) == "UPDATE_UNFINISHED"           # before the core's SWAP_INDEX
    assert refused(lambda: a.write_shadow(S.start_blob(profile, T))) == "UPDATE_UNFINISHED"
    assert refused(lambda: a.write_shadow(b"not a blob")) == "UPDATE_UNFINISHED"   # before the blob's own
    assert a.counters()["lrn_early"] == 2
    for f in varied(profile, 6):            # next index 8 = 5 + 3: finished
        a.step(f)
    assert a.next_index == 8 and a.status()["made"] + a.status()["unmade"] == 1
    assert refused(lambda: a.commit(7)) == "SWAP_INDEX"                  # now the core's own names
    assert refused(lambda: a.write_shadow(b"not a blob")) == "BLOB_FORMAT"
    assert refused(lambda: a.commit(9)) is None and a.counters()["lrn_early"] == 2


class NoUnfinishedForAnUpdate(Learner):
    def _update_unfinished(self):
        pass


class NoShapeCheck(Learner):
    def _update_shape(self):
        pass


class NoPendingCheck(Learner):
    def _update_pending(self):
        pass


class NoIndexCheck(Learner):
    def _update_index(self, at):
        pass


class NoUnfinishedForACommit(Learner):
    def commit(self, at):
        self.core.commit(at)


class NoUnfinishedForAShadowWrite(Learner):
    def write_shadow(self, blob):
        self.core.write_shadow(blob)


def scenario(profile, make, name):
    """The one operation each name is for, on a learner of `make`: the name it was refused under, or None."""
    other = S.blob_of(profile, [[1] * T] * S.channels(profile))
    if name == "update unfinished":
        a = fresh(profile, make, steps=2)
        a.update(5)
        return refused(lambda: a.update(6))
    if name == "shape":
        return refused(lambda: fresh(profile, make, blob=other_shapes(profile)[0][1], steps=2).update(5))
    if name == "pending":
        c = fresh(profile, make, steps=2)
        c.write_shadow(other)
        c.commit(6)
        return refused(lambda: c.update(8))
    if name == "index":
        return refused(lambda: fresh(profile, make, steps=3).update(2))
    if name in ("commit unfinished", "shadow unfinished"):
        a = fresh(profile, make, steps=2)
        a.update(5)
        return refused(lambda: a.commit(8) if name == "commit unfinished" else a.write_shadow(other))
    raise AssertionError(name)


@pytest.mark.parametrize("profile", S.PROFILES)
@pytest.mark.parametrize("name, make, want", [
    ("update unfinished", NoUnfinishedForAnUpdate, "UPDATE_UNFINISHED"),
    ("shape", NoShapeCheck, "SWAP_SHAPE"),
    ("pending", NoPendingCheck, "SWAP_PENDING"),
    ("index", NoIndexCheck, "SWAP_INDEX"),
    ("commit unfinished", NoUnfinishedForACommit, "UPDATE_UNFINISHED"),
    ("shadow unfinished", NoUnfinishedForAShadowWrite, "UPDATE_UNFINISHED"),
])
def test_lrn_b_counts_control_each_refusal_removed_alone_is_seen(profile, name, make, want):
    assert scenario(profile, Learner, name) == want
    got = scenario(profile, make, name)
    print("CONTROL %s removed: %r where %s is refused" % (name, got, want))
    assert got != want
    # and each other operation's check is still in place in that learner
    for other_name, _m, other_want in [("update unfinished", None, "UPDATE_UNFINISHED"), ("shape", None, "SWAP_SHAPE"),
                                       ("pending", None, "SWAP_PENDING"), ("index", None, "SWAP_INDEX"),
                                       ("commit unfinished", None, "UPDATE_UNFINISHED"),
                                       ("shadow unfinished", None, "UPDATE_UNFINISHED")]:
        if other_name != name:
            assert scenario(profile, make, other_name) == other_want, (name, other_name)


# ------------------------------------------------------------ the learner made

@pytest.mark.parametrize("profile", S.PROFILES)
def test_lrn_b_counts_the_learner_is_refused_when_made_by_each_name_and_in_order(profile):
    blob = S.start_blob(profile, T)
    for count_bits in (0, C.LEARN_COUNT_BITS + 1, True, "32", 2.0):
        assert refused(lambda: Learner(blob, [], 3, count_bits)) == "LEARN_BOUND", count_bits
    for frames_ in (-1, C.LEARN_UPDATE_FRAMES + 1, 1.0, None):
        assert refused(lambda: Learner(blob, [], frames_)) == "LEARN_BOUND", frames_
    assert refused(lambda: Learner(blob, [], 0, 1)) is None
    assert refused(lambda: Learner(blob, [], C.LEARN_UPDATE_FRAMES, C.LEARN_COUNT_BITS)) is None
    for truth in ("not a list", [5], [{"pulse_id": 0}], [S.rec(True)], [dict(S.rec(0), index=-1)],
                  [dict(S.rec(0), index=L.INDEX_MAX + 1)], [dict(S.rec(0), index=3.0)]):
        assert refused(lambda: Learner(blob, truth, 3)) == "RECORD_FIELD", truth
    for indexes in ([5, 5], [9, 3], [1, 4, 2]):
        assert refused(lambda: Learner(blob, [S.rec(j) for j in indexes], 3)) == "RECORD_ORDER", indexes
    # in order: the blob's own, then the bounds, then the truth
    assert refused(lambda: Learner(b"not a blob", [S.rec(3), S.rec(1)], -1)) == "BLOB_FORMAT"
    assert refused(lambda: Learner(blob, [S.rec(3), S.rec(1)], -1)) == "LEARN_BOUND"
    assert refused(lambda: Learner(blob, [S.rec(3), "x"], 3)) == "RECORD_FIELD"


@pytest.mark.parametrize("profile", S.PROFILES)
def test_lrn_b_counts_control_the_bounds_and_the_truth_checks_each_removed_alone_are_seen(profile, monkeypatch):
    blob = S.start_blob(profile, T)
    with monkeypatch.context() as m:
        m.setattr(L, "_bound", lambda value, lo, hi, what: value)
        got = refused(lambda: Learner(blob, [], 3, C.LEARN_COUNT_BITS + 1))
        print("CONTROL LEARN_BOUND removed:", got)
        assert got != "LEARN_BOUND"

    class NoOrder(Learner):
        @staticmethod
        def _read_indexes(truth):
            return tuple(r["index"] for r in truth)

    class NoField(Learner):
        @staticmethod
        def _read_indexes(truth):
            out = [r["index"] for r in truth]
            if any(b <= a for a, b in zip(out, out[1:])):
                raise Refusal("RECORD_ORDER", "out of order")
            return tuple(out)
    assert refused(lambda: NoOrder(blob, [S.rec(9), S.rec(3)], 3)) is None
    assert refused(lambda: NoField(blob, [dict(S.rec(0), index=-5), S.rec(3)], 3)) is None
    assert refused(lambda: NoField(blob, [S.rec(9), S.rec(3)], 3)) == "RECORD_ORDER"


# ------------------------------------------------------------ the update: when, from what, and what it says

SNAP = [4, 20]       # label 0 of 4 at 4, label 1 of 4 at 8; label 0 of 20 at 20, label 1 of 20 at 24


class RemakesAtTheFinish(Learner):
    """Not the snapshot: makes its set again at the finish, from the sums as they stand then."""

    def _finish(self):
        u = self._update
        if u["blob"] is not None:
            u["blob"] = self._pack(self._quantise(self._difference()))
            self.core.write_shadow(u["blob"])
        super()._finish()


@pytest.mark.parametrize("profile", S.PROFILES)
def test_lrn_b_counts_the_update_at_u_is_of_the_sums_at_u_and_its_removal_is_seen(profile):
    frames = varied(profile, 60)
    script = {0: [("update", 8)], 30: [("commit", 30)]}
    real, _o, learner = S.drive(S.start_blob(profile, T), frames, [S.rec(j) for j in SNAP], script, 22)
    rows = S.worked(frames, SNAP, T, 8)[4]
    assert S.rows_of(learner.updates[0]["blob"]) == rows
    assert learner.updates[0]["counts"] == (1, 1) and learner.counts == [2, 2]
    broken, _o, b = S.drive(S.start_blob(profile, T), frames, [S.rec(j) for j in SNAP], script, 22, make=RemakesAtTheFinish)
    later = S.worked(frames, SNAP, T, 30)[4]
    print("CONTROL remade at the finish: %s, where the snapshot's is %s" % (S.rows_of(b.updates[0]["blob"]), rows))
    assert later != rows and S.rows_of(b.updates[0]["blob"]) == later
    assert S.first_difference(S.as_words(real), S.as_words(broken)) == 30


def finish_moved(by):
    class FinishMoved(Learner):
        def _finish_index(self, at):
            return at + self.update_frames + by
    return FinishMoved


@pytest.mark.parametrize("profile", S.PROFILES)
@pytest.mark.parametrize("frames_", [1, 3, 64])
def test_lrn_b_counts_an_update_is_finished_at_u_plus_its_update_time_and_not_a_frame_either_side(profile, frames_):
    u = 6

    def outcomes(make):
        script = {0: [("update", u)], u + frames_ - 1: [("commit", u + frames_ + 5)], u + frames_: [("commit", u + frames_ + 5)]}
        _r, out, _l = run(profile, [], script, make=make, length=u + frames_ + 10, frames_=frames_)
        return [o[3] for o in out]
    assert outcomes(Learner) == [None, "UPDATE_UNFINISHED", None]
    early, late = outcomes(finish_moved(-1)), outcomes(finish_moved(1))
    print("CONTROL finished a frame early: %s; a frame late: %s" % (early, late))
    assert early == [None, None, "SWAP_PENDING"] and late == [None, "UPDATE_UNFINISHED", "UPDATE_UNFINISHED"]


class PublishesWhenMade(Learner):
    """Counts its outcome when the update is made, not at the finish."""

    def _make(self):
        super()._make()
        self._counters["lrn_made" if self._update["blob"] is not None else "lrn_unmade"] += 1

    def _finish(self):
        name = "lrn_made" if self._update["blob"] is not None else "lrn_unmade"
        super()._finish()
        self._counters[name] -= 1


@pytest.mark.parametrize("profile", S.PROFILES)
@pytest.mark.parametrize("indexes, outcome", [([4], "made"), ([], "unmade")])
def test_lrn_b_counts_the_status_and_the_outcome_over_an_update_and_published_at_the_finish(profile, indexes, outcome):
    u, f = 10, 5

    def history(make):
        learner = make(S.start_blob(profile, T), [S.rec(j) for j in indexes], f)
        learner.update(u)
        seen = []
        for frame in varied(profile, 20):
            seen.append((learner.next_index, learner.status(), learner.counters()["lrn_" + outcome]))
            learner.step(frame)
        return seen, learner
    seen, learner = history(Learner)
    for n, status, counted in seen:
        assert status == {"named": int(n < u), "running": int(u <= n < u + f),
                          "made": int(n >= u + f and outcome == "made"),
                          "unmade": int(n >= u + f and outcome == "unmade")}, n
        assert counted == int(n >= u + f), n
    assert learner.updates[0]["outcome"] == outcome
    broken, _l = history(PublishesWhenMade)
    print("CONTROL published when made: counted at index %d" % min(n for n, _s, c in broken if c))
    assert min(n for n, _s, c in broken if c) == u


@pytest.mark.parametrize("profile", S.PROFILES)
def test_lrn_b_counts_an_update_that_makes_no_set_leaves_the_shadow_and_a_host_write_after_the_finish_wins(profile):
    frames = varied(profile, 40)
    start = S.start_blob(profile, T)
    other = S.blob_of(profile, [[5, -3, 2, 1]] * S.channels(profile))
    # no truth: unmade; the commit swaps in what the shadow held, the start's own set
    recs, out, a = S.drive(start, frames, [], {0: [("update", 5)], 8: [("commit", 8)]}, 3)
    assert a.updates[0]["blob"] is None and a.updates[0]["name"] == "QUANTISE_INPUT"
    assert S.as_words(recs) == S.as_words(S.frozen(start, frames, commits=[(8, 8)]))
    # a set made, then the host's own written over it after the finish: the commit takes the host's
    recs, out, b = S.drive(start, frames, [S.rec(4), S.rec(14)], {0: [("update", 20)], 23: [("write_shadow", other), ("commit", 25)]}, 3)
    assert [o[3] for o in out] == [None, None, None] and b.updates[0]["blob"] is not None
    assert S.as_words(recs) == S.as_words(S.frozen(start, frames, writes=[(23, other)], commits=[(23, 25)]))


# ------------------------------------------------------------ model.run.learning's own checks

def lax_scripts():
    """`model.run._check_script` with one of its conditions removed, each alone."""
    def no_dict(script, length):
        for index, ops in dict(script).items():
            if type(index) is not int or not 0 <= index <= length or not isinstance(ops, (list, tuple)):
                raise Refusal("RECORD_FIELD", "index")
            for op in ops:
                if not isinstance(op, tuple) or len(op) != 2 or op[0] not in run_.OPERATIONS:
                    raise Refusal("RECORD_FIELD", "op")

    def no_range(script, length):
        if not isinstance(script, dict):
            raise Refusal("RECORD_FIELD", "dict")
        for index, ops in script.items():
            for op in ops:
                if not isinstance(op, tuple) or len(op) != 2 or op[0] not in run_.OPERATIONS:
                    raise Refusal("RECORD_FIELD", "op")

    def no_operation(script, length):
        if not isinstance(script, dict):
            raise Refusal("RECORD_FIELD", "dict")
        for index, ops in script.items():
            if type(index) is not int or not 0 <= index <= length or not isinstance(ops, (list, tuple)):
                raise Refusal("RECORD_FIELD", "index")
    return {"a script not a dict": no_dict, "an index past the stream": no_range, "an undeclared operation": no_operation}


BAD_SCRIPTS = {"a script not a dict": [(0, [("update", 5)])],
               "an index past the stream": {13: [("update", 5)]},
               "an undeclared operation": {0: [("swap", 5)]}}


@pytest.mark.parametrize("profile", S.PROFILES)
@pytest.mark.parametrize("what", sorted(BAD_SCRIPTS))
def test_lrn_b_counts_learning_refuses_a_script_not_of_its_form_and_each_check_removed_alone_is_seen(profile, what, monkeypatch):
    frames = varied(profile, 12)
    call = lambda: run_.learning(iter(frames), [], 12, S.start_blob(profile, T), BAD_SCRIPTS[what], 3)  # noqa: E731
    assert refused(call) == "RECORD_FIELD"
    assert refused(lambda: run_.learning(iter(frames), [], 12, S.start_blob(profile, T), {12: [("update", 12)]}, 3)) is None
    monkeypatch.setattr(run_, "_check_script", lax_scripts()[what])
    try:
        got = refused(call)
    except Exception as e:          # what a script that passes no check does next is not a refusal
        got = type(e).__name__
    print("CONTROL %s, its check removed: %r" % (what, got))
    assert got != "RECORD_FIELD"


@pytest.mark.parametrize("profile", S.PROFILES)
def test_lrn_b_counts_learning_records_each_refused_operation_and_runs_on_to_the_end(profile):
    """`model.run.learning` through the injector: three operations refused at one index, each recorded by
    name, the run going on to its length; and its records, outcomes and counters equal the driver's in
    test_lrn_b_support on the same injected frames, so the two loops make the operations alike."""
    length, start = 240, S.start_blob(profile, T)
    schedule = [S.rec(10, 3), S.rec(80, -2), S.rec(150, 5, 2)]
    script = {5: [("update", 100)], 20: [("write_shadow", start), ("commit", 30), ("update", 50)],
              103: [("commit", 110)]}
    frames, truth = S.noise_frames(profile, 2026112670, (700, 1), length, schedule)
    records, truth, outcomes, learner = run_.learning(iter(S.source.Noise(profile, 2026112670, 700, 1, length)),
                                                      schedule, length, start, script, 3)
    assert outcomes == [(5, "update", 100, None), (20, "write_shadow", start, "UPDATE_UNFINISHED"),
                        (20, "commit", 30, "UPDATE_UNFINISHED"), (20, "update", 50, "UPDATE_UNFINISHED"),
                        (103, "commit", 110, None)]
    assert len(records) == length and records[109]["epoch"] == 0 and records[110]["epoch"] == 1
    driven, driven_outcomes, other = S.drive(start, frames, truth, script, 3)
    assert S.as_words(records) == S.as_words(driven)
    assert [o[3] for o in outcomes] == [o[3] for o in driven_outcomes]
    assert learner.counters() == other.counters() and learner.counters()["lrn_early"] == 1


@pytest.mark.parametrize("profile", S.PROFILES)
def test_lrn_b_counts_an_update_named_at_the_next_index_is_made_at_once(profile):
    learner = fresh(profile, frames_=0, steps=0)
    learner2 = Learner(S.start_blob(profile, T), [S.rec(4)], 0)
    for f in varied(profile, 8):
        learner2.step(f)
    learner2.update(8)
    assert learner2.updates[0]["u"] == 8 and learner2.updates[0]["counts"] == (1, 1)
    assert learner2.status() == {"named": 0, "running": 0, "made": 1, "unmade": 0}
    learner.update(0)                     # no window at all: made at once, and unmade at once
    assert learner.status()["unmade"] == 1 and learner.counters()["lrn_unmade"] == 1

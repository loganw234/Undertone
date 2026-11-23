"""The scorer gate: threshold crossings, the histogram and the event records.

Known answers: vectors/mod-b/scorer.json, worked by hand. The scorer is fed score records written in the
vector, so this gate does not lean on the detector core; one further test feeds it the core's own records
and holds what must be true of any stream.

The controls: a threshold off by one in each direction, a compare that is at-or-above, a histogram that
drops its last bin (two ways), and a scorer that counts a settling record. Each is a subclass or a changed
argument made here, run through the SAME check, on the stream that has a score equal to the threshold, a
crossing, and scores in the last bin.
"""
import pytest

from spec import constants as C
from model import records
from model.detector import Core
from model.scorer import Scorer

import test_mod_b_support as S

PROFILES = S.PROFILES


def check_scorer(profile, scorer=Scorer, threshold_error=0):
    """Findings for a scorer class against the hand-worked cases, under one profile."""
    findings = []
    todo = S.vector("scorer.json")["cases"]
    for case in todo:
        frames = [tuple(f) for f in case["frames"][profile]]
        args = dict(case["scorer"])
        args["threshold"] += threshold_error
        s = scorer(profile, **args)
        completed = []
        for frame, record in zip(frames, case["records"]):
            s.feed(frame, record)
            completed.append(len(s.events))            # the events complete before the next record is fed
        s.close()
        want = case["expected"]
        for what, got, expected in (
                ("completed after each record", completed, want["completed_after"]),
                ("completed at close", len(s.events), want["completed_at_close"]),
                ("counted", s.counted, want["counted"]), ("excluded", s.excluded, want["excluded"]),
                ("crossings", s.crossings, want["crossings"]), ("overflow_at", s.overflow_at, want["overflow_at"]),
                ("histogram", s.histogram(), {"below": want["histogram"]["below"], "bins": tuple(want["histogram"]["bins"]),
                                              "above": want["histogram"]["above"]}),
                ("event records", [records.pack("event", e) for e in s.events],
                 [records.pack("event", e["record"]) for e in want["events"]]),
                ("captured frames", s.captures, [tuple(frames[i] for i in e["frames"]) for e in want["events"]])):
            if got != expected:
                findings.append("%s: %s is %r, the vector says %r" % (case["name"], what, got, expected))
    return findings, len(todo)


# ------------------------------------------------------------------ the gate

@pytest.mark.parametrize("profile", PROFILES)
def test_gate_scorer__crossings_events_and_histogram_equal_the_hand_worked_vector(profile):
    findings, n = check_scorer(profile)
    assert findings == []
    assert n == 3
    posts = {case["scorer"]["post"] for case in S.vector("scorer.json")["cases"]}
    assert 0 in posts and len(posts) == 3, "a case with no frame after the crossing, and two with some"


def test_gate_scorer__the_vector_has_what_the_controls_need():
    """A stream with no crossing, or no score in the last bin, would let the controls pass while testing nothing."""
    case = S.vector("scorer.json")["cases"][0]
    threshold, config = case["scorer"]["threshold"], case["scorer"]
    scores = [r["score"] for r in case["records"] if not r["flags"] & S.SETTLING]
    assert threshold in scores and threshold + 1 in scores, "a score equal to the threshold and one a unit above"
    assert case["expected"]["crossings"] >= 1 and len(case["expected"]["events"]) >= 1
    top = config["hist_lo"] + (config["hist_bins"] << config["hist_shift"])
    assert any(top - (1 << config["hist_shift"]) <= s < top for s in scores), "a score in the last bin"
    assert any(s >= top for s in scores) and any(s < config["hist_lo"] for s in scores), "and one each side of the bins"
    assert any(r["flags"] & S.SETTLING for r in case["records"]), "a settling record"
    for profile in PROFILES:
        frames = case["frames"][profile]
        assert len(frames) == len(case["records"])
        assert all(len(set(f)) == len(f) for f in frames), "the channels of a frame differ"


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_scorer__on_the_cores_own_records_every_counted_score_lands_in_exactly_one_place(profile):
    config = S.a_config(profile, taps=3, pool=3, rectifier=0)
    frames = S.varied_frames(profile, 200, seed=17, small=True)
    core = Core(S.blob_of(profile, config))
    core.write_shadow(S.blob_of(profile, dict(config, filters=[{k: [-v for v in row] for k, row in config["filters"][0].items()}])))
    core.commit(50)
    recs = list(core.run(frames))
    threshold = sorted(r["score"] for r in recs)[150]
    s = Scorer(profile, threshold, 5, 7, -64, 3, 16)
    s.run(zip(frames, recs))
    counted = [r for r in recs if not r["flags"] & S.SETTLING]
    assert (s.counted, s.excluded) == (len(counted), 2) == (198, 2)
    h = s.histogram()
    assert h["below"] + sum(h["bins"]) + h["above"] == s.counted
    assert h["below"] == sum(1 for r in counted if r["score"] < -64)
    assert h["above"] == sum(1 for r in counted if r["score"] >= -64 + 16 * 8)
    assert list(h["bins"]) == [sum(1 for r in counted if -64 + 8 * b <= r["score"] < -64 + 8 * (b + 1)) for b in range(16)]
    assert s.crossings == sum(1 for r in counted if r["score"] > threshold) > 10
    rising = [r["index"] for n, r in enumerate(recs)
              if not r["flags"] & S.SETTLING and r["score"] > threshold
              and (n == 0 or recs[n - 1]["flags"] & S.SETTLING or recs[n - 1]["score"] <= threshold)]
    assert [e["index"] for e in s.events] == rising and len(rising) > 5
    for event, frames_kept in zip(s.events, s.captures):
        i = event["index"]
        assert (event["pre"], event["post"]) == (min(5, i), min(7, len(frames) - 1 - i))
        assert frames_kept == tuple(frames[i - event["pre"]:i + event["post"] + 1])
        assert (event["epoch"], event["score"]) == (recs[i]["epoch"], recs[i]["score"])
    assert s.overflow_at is None


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_scorer__the_conventions_pages_worked_answer(profile):
    """docs/model/conventions.md, the lead's: coefficients 1, 2, 3 on the stream 0, 0, 1, 2, 3, 0, 0 give the scores
    0, 0, 3, 8, 14, 8, 3; a threshold of 14 gives no crossing and 13 gives one, at index 4. The figures are typed here
    from that page."""
    last = C.PROFILES[profile]["channels"] - 1
    config = {"filters": [{str(last): [1, 2, 3]}], "head": [1], "rectifier": 0, "pool": 1, "score_shift": 0}
    frames = [tuple(v if c == last else 50 + c for c in range(last + 1)) for v in (0, 0, 1, 2, 3, 0, 0)]
    recs = list(Core(S.blob_of(profile, config)).run(frames))
    assert [r["score"] for r in recs] == [0, 0, 3, 8, 14, 8, 3]
    for threshold, crossings, at in ((14, 0, []), (13, 1, [4])):
        s = Scorer(profile, threshold, 0, 0, 0, 0, 1)
        s.run(zip(frames, recs))
        assert (s.crossings, [e["index"] for e in s.events]) == (crossings, at)


# --------------------------------------------------------------- the controls

def what_differs(findings, case="crossings-events-histogram"):
    """The things a check found different in one case: 'crossings', 'histogram', 'event records', ..."""
    return sorted(f.split(": ")[1].split(" is ")[0] for f in findings if f.startswith(case + ": "))


class AtOrAbove(Scorer):
    def feed(self, frame, record):
        self.threshold -= 1                       # score > threshold - 1 is score >= threshold
        try:
            super().feed(frame, record)
        finally:
            self.threshold += 1


class DropsItsLastBin(Scorer):
    def _bin(self, score):
        if score >= self.hist_lo and (score - self.hist_lo) >> self.hist_shift == len(self.bins) - 1:
            return                                # a score in the last bin is counted nowhere
        super()._bin(score)


class LastBinGoesAbove(Scorer):
    def _bin(self, score):
        if score >= self.hist_lo and (score - self.hist_lo) >> self.hist_shift == len(self.bins) - 1:
            self.above += 1
            return
        super()._bin(score)


class CountsSettling(Scorer):
    def feed(self, frame, record):
        super().feed(frame, dict(record, flags=record["flags"] & ~S.SETTLING))


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("error", [1, -1])
def test_control_scorer__a_threshold_off_by_one_is_caught(profile, error):
    findings, _n = check_scorer(profile, threshold_error=error)
    assert what_differs(findings) == ["captured frames", "completed after each record", "crossings", "event records"], findings
    print("CONTROL scorer, threshold off by %+d, %s:" % (error, profile), [f for f in findings if ": crossings is " in f][0])


@pytest.mark.parametrize("profile", PROFILES)
def test_control_scorer__a_compare_that_is_at_or_above_is_caught(profile):
    findings, _n = check_scorer(profile, scorer=AtOrAbove)
    assert what_differs(findings) == ["captured frames", "completed after each record", "crossings", "event records"], findings
    print("CONTROL scorer, at-or-above, %s:" % profile, [f for f in findings if ": crossings is " in f][0])


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("broken", [DropsItsLastBin, LastBinGoesAbove])
def test_control_scorer__a_histogram_that_drops_its_last_bin_is_caught(profile, broken):
    findings, _n = check_scorer(profile, scorer=broken)
    named = [f for f in findings if ": histogram is " in f]
    assert len(named) == len(findings) == 3, "each case has a score in the last bin, and nothing but the histogram differs"
    assert what_differs(findings) == ["histogram"]
    print("CONTROL scorer, %s, %s:" % (broken.__name__, profile), named[0])


@pytest.mark.parametrize("profile", PROFILES)
def test_control_scorer__a_scorer_that_counts_a_settling_record_is_caught(profile):
    findings, _n = check_scorer(profile, scorer=CountsSettling)
    assert what_differs(findings) == ["captured frames", "completed after each record", "completed at close", "counted",
                                      "crossings", "event records", "excluded", "histogram"],         "the settling record's score is above the threshold: counted, it adds a crossing and hides the event after it"
    print("CONTROL scorer, counts a settling record, %s:" % profile, [f for f in findings if ": counted is " in f][0])


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_scorer__the_flag_is_reported_where_it_first_rose_even_on_a_record_that_is_left_out(profile):
    frames = S.varied_frames(profile, 4, seed=3)
    recs = [{"index": 0, "epoch": 0, "flags": 0, "score": 1},
            {"index": 1, "epoch": 1, "flags": S.SETTLING | S.OVERFLOW, "score": 9},
            {"index": 2, "epoch": 1, "flags": S.OVERFLOW, "score": 9},
            {"index": 3, "epoch": 1, "flags": S.OVERFLOW, "score": 9}]
    s = Scorer(profile, 5, 0, 0, 0, 0, 1)
    assert s.overflow_at is None
    s.run(zip(frames, recs))
    assert s.overflow_at == 1, "index 1 is left out of the counts, and it is still where the run became a marked run"
    assert (s.counted, s.excluded, s.crossings, [e["index"] for e in s.events]) == (3, 1, 2, [2])
    assert s.closed


class DeliversAPostOfZeroLate(Scorer):
    """An event that wants no later frame is held back, and delivered when the next record is fed or at close."""

    _held = None

    def _release(self):
        if self._held:
            self.events.append(self._held[0])
            self.captures.append(self._held[1])
            self._held = None

    def feed(self, frame, record):
        self._release()
        before = len(self.events)
        super().feed(frame, record)
        if self.post == 0 and len(self.events) > before:
            self._held = (self.events.pop(), self.captures.pop())

    def close(self):
        self._release()
        super().close()


@pytest.mark.parametrize("profile", PROFILES)
def test_control_scorer__a_scorer_that_delivers_a_post_of_zero_event_late_is_caught(profile):
    """The event's record and frames are right and it arrives one record late: only the count after each record sees it."""
    findings, _n = check_scorer(profile, scorer=DeliversAPostOfZeroLate)
    assert what_differs(findings, case="a-post-of-zero") == ["completed after each record"], findings
    assert len(findings) == 1, "the two cases with a post above zero are untouched"
    print("CONTROL scorer, a post of zero delivered late, %s:" % profile, findings[0])

"""The truth-isolation gate, across the injector and the detector (D0 section 9).

The claim: what the detector reports depends on the samples it was given and on nothing else.
In particular not on the truth records, which say where a pulse was put and how strong.

How it is held: one stream of samples, already carrying its pulses, is run again under truth
records that differ from the real ones in every way a schedule can while adding the same
samples, or adding none. The score records must come out the same, byte for byte, by
`model.records.digest`. Then the control: a runner made here, which lets ONE BIT of truth reach
the detector's output, must be reported by the same check.

What this gate cannot see, stated:
  - a detector that reads truth and does not let it change a record;
  - a leak keyed on something the other truths here do not vary. They vary whether there is a
    record, its index, and its amplitude's denominator. They cannot vary the pulse id, because
    one pulse is declared, and every one of them adds nothing to the samples; so a detector
    that changed a record only for a second pulse, or only for a non-zero amplitude it had not
    seen in the samples, would pass. The round's closing verifier built two such leaks and both
    passed;
  - anything about a detector other than the shipped core run through `model.run`.
"""
import pytest

from spec import constants as C
from model import inject, records, run, source, stream, weights
from model.detector import Core
from model.refusal import Refusal
from model.scorer import Scorer

PROFILES = sorted(C.PROFILES)
E0 = C.PULSES["e0"]
LENGTH = 3000
SEED = 20261126
SIGMA = (400, 1)


def rec(index, num, den=1):
    return {"index": index, "pulse_id": C.PULSE_IDS["e0"], "amplitude_num": num, "amplitude_den": den}


REAL = [rec(200, 3, 2), rec(700, 1), rec(1300, -2), rec(2100, 5, 4)]


def blob_for(profile):
    return weights.matched_filter(profile, E0, (1,) * C.PROFILES[profile]["channels"])


def the_samples(profile):
    """The stream the detector saw in the real run: noise with the real schedule's pulses added."""
    noise = source.Noise(profile, SEED, SIGMA[0], SIGMA[1], LENGTH)
    injected, _truth = inject.inject(profile, noise, REAL, LENGTH)
    return list(injected)


def other_truths():
    """Schedules that add nothing to a stream and say different things: none at all; the real
    indexes at amplitude zero; the same with another denominator; other indexes at amplitude
    zero; one record too faint to add a sample."""
    faint = rec(2500, 1, 5000)
    assert inject.scaled_pulse(faint["pulse_id"], 1, 5000) == (0,) * len(E0)
    return [("no truth at all", []),
            ("the real indexes, amplitude zero", [rec(r["index"], 0) for r in REAL]),
            ("the real indexes, amplitude zero over three", [rec(r["index"], 0, 3) for r in REAL]),
            ("other indexes, amplitude zero", [rec(i, 0) for i in (64, 500, 1100, 1900, 2600)]),
            ("one record too faint to add anything", [faint])]


OTHERS = 5


def refusal_of(call):
    """(result, None), or (None, a finding) when the call was refused: a refusal is reported, not raised."""
    try:
        return call(), None
    except Refusal as e:
        return None, "refused as %s: %s" % (e.name, e.detail)


def isolation_findings(runner, profile):
    """Run the real stream once with its real truth, then the same samples under each other truth.
    Returns a list of findings; empty means every run's score records had one digest."""
    blob = blob_for(profile)
    noise = source.Noise(profile, SEED, SIGMA[0], SIGMA[1], LENGTH)
    result, refused = refusal_of(lambda: runner(noise, REAL, LENGTH, blob))
    if refused:
        return ["NOTHING-COMPARED: the real run was " + refused]
    first, truth = result
    if not first or len(first) != LENGTH:
        return ["NOTHING-COMPARED: the real run gave %d records" % len(first)]
    want = records.digest("score", first)
    samples = the_samples(profile)
    findings = []
    compared = 0
    for what, schedule in other_truths():
        result, refused = refusal_of(lambda: runner(samples, schedule, LENGTH, blob))
        if refused:
            # a detector that refuses under one truth and not under another has let the truth out
            findings.append("%s: the run was %s, where the real run was not" % (what, refused))
            continue
        got, other = result
        compared += 1
        if records.digest("truth", other) == records.digest("truth", truth):
            findings.append("%s: the truth records did not differ, so nothing was tested" % what)
        if records.digest("score", got) != want:
            where = [i for i, (a, b) in enumerate(zip(first, got)) if a != b]
            findings.append("%s: the score records differ, first at index %s" % (what, where[0] if where else "?"))
    if compared != OTHERS and not findings:
        findings.append("NOTHING-COMPARED: %d of %d other truths were run" % (compared, OTHERS))
    return findings


# ------------------------------------------------------------ the gate

@pytest.mark.parametrize("profile", PROFILES)
def test_gate_truth_isolation__the_same_samples_under_other_truth_give_the_same_score_records(profile):
    assert isolation_findings(run.detect, profile) == []


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_truth_isolation__the_real_run_is_not_a_run_of_nothing(profile):
    """The check above would pass on a detector that reported zeros. This one says it did not:
    the real pulses are in the samples, they move the scores, and the truth says where."""
    blob = blob_for(profile)
    noise = source.Noise(profile, SEED, SIGMA[0], SIGMA[1], LENGTH)
    with_pulses, truth = run.detect(noise, REAL, LENGTH, blob)
    without, none = run.detect(source.Noise(profile, SEED, SIGMA[0], SIGMA[1], LENGTH), [], LENGTH, blob)
    assert list(truth) == REAL and none == ()
    differ = [i for i, (a, b) in enumerate(zip(with_pulses, without)) if a["score"] != b["score"]]
    # The pulse's first and last samples are zero, and so are the filter's first and last coefficients.
    # So a pulse at j puts non-zero samples at j+1 .. j+62, and score i, which reads samples i-63 .. i
    # under coefficients 0 .. 63, is moved for i from j+2 (sample j+1 under coefficient 62) to j+124
    # (sample j+62 under coefficient 1): 123 scores a pulse. Measured, and it is exactly those.
    assert E0[0] == E0[63] == 0 and E0[1] != 0 and E0[62] != 0
    expected = sorted(i for r in REAL for i in range(r["index"] + 2, r["index"] + 125))
    assert differ == expected and len(differ) == 4 * 123
    assert all(r["index"] + 63 in differ for r in REAL), "the score at each truth index + 63 is one of them"
    assert records.digest("score", with_pulses) != records.digest("score", without)


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_truth_isolation__the_events_of_a_scorer_do_not_change_with_the_truth_either(profile):
    blob = blob_for(profile)
    samples = the_samples(profile)
    digests = set()
    for _what, schedule in [("the real truth, replayed as amplitude zero", [rec(r["index"], 0) for r in REAL])] + other_truths():
        pairs, _truth = run.scores(samples, schedule, LENGTH, blob)
        scorer = Scorer(profile, 10 ** 8, 4, 4, 0, 24, 64)
        scorer.run(pairs)
        assert scorer.crossings > 0 and scorer.events
        digests.add((records.digest("event", scorer.events), scorer.crossings, tuple(scorer.histogram()["bins"])))
    assert len(digests) == 1


# ------------------------------------------------------------ the control: a detector wired to read truth

class LeakyCore(Core):
    """A detector that has been handed the truth and lets one bit of it out: the lowest bit of the
    score is set on the frame where a truth record says a pulse begins."""
    starts = frozenset()

    def step(self, frame):
        record = super().step(frame)
        if record["index"] in self.starts:
            record = dict(record, score=record["score"] | 1)
        return record


def leaky_detect(frames, schedule_records, length, blob, epoch=0):
    """`model.run.detect`, with the one change that it tells the core where the truth is."""
    core = LeakyCore(blob, epoch)
    injected, truth = inject.inject(weights.unpack(blob)["profile"], frames, schedule_records, length)
    core.starts = frozenset(r["index"] for r in truth)
    return tuple(core.step(frame) for frame in injected), truth


@pytest.mark.parametrize("profile", PROFILES)
def test_control_truth_isolation__a_runner_that_hands_the_detector_one_bit_of_truth_is_caught(profile):
    findings = isolation_findings(leaky_detect, profile)
    assert findings, "the leak was not seen"
    assert all("the score records differ" in f for f in findings), findings
    # it is a single bit in a handful of records: the real run and the leaky one differ in at most
    # one record for each truth record, and only where the honest score was even
    honest, _ = run.detect(source.Noise(profile, SEED, SIGMA[0], SIGMA[1], LENGTH), REAL, LENGTH, blob_for(profile))
    leaky, _ = leaky_detect(source.Noise(profile, SEED, SIGMA[0], SIGMA[1], LENGTH), REAL, LENGTH, blob_for(profile))
    differ = [i for i, (a, b) in enumerate(zip(honest, leaky)) if a != b]
    assert set(differ) <= {r["index"] for r in REAL}
    assert all(abs(honest[i]["score"] - leaky[i]["score"]) == 1 for i in differ)


class RefusingCore(Core):
    """A detector that has been handed the truth and lets it out another way: it refuses the frame
    where a truth record says a pulse begins."""
    starts = frozenset()

    def step(self, frame):
        if self.next_index in self.starts:
            raise Refusal("SAMPLE_RANGE", "a refusal that depends on the truth")
        return super().step(frame)


def refusing_detect(frames, schedule_records, length, blob, epoch=0):
    core = RefusingCore(blob, epoch)
    injected, truth = inject.inject(weights.unpack(blob)["profile"], frames, schedule_records, length)
    core.starts = frozenset(r["index"] for r in truth if r["amplitude_den"] == 3)
    return tuple(core.step(frame) for frame in injected), truth


@pytest.mark.parametrize("profile", PROFILES)
def test_control_truth_isolation__a_leak_through_a_refusal_is_reported_and_not_raised(profile):
    """The closing verifier's leak: a refusal that happens under one truth and not another. The
    check must report it as a finding; before, the refusal went straight out of the check."""
    findings = isolation_findings(refusing_detect, profile)
    assert len(findings) == 1 and "amplitude zero over three" in findings[0] and "refused as SAMPLE_RANGE" in findings[0]


@pytest.mark.parametrize("profile", PROFILES)
def test_control_truth_isolation__a_check_that_compared_nothing_says_so(profile):
    def runs_nothing(frames, schedule_records, length, blob, epoch=0):
        return (), ()

    assert isolation_findings(runs_nothing, profile)[0].startswith("NOTHING-COMPARED")


# ------------------------------------------------------------ the runner itself

@pytest.mark.parametrize("profile", PROFILES)
def test_seam_the_runner_is_the_parts_run_by_hand_and_nothing_more(profile):
    """`model.run` adds no arithmetic of its own: its records are the core's on the injector's
    stream, its truth is the injector's, its frames are the frames the core was given, and a start
    epoch reaches every record."""
    blob = blob_for(profile)
    by_hand_stream, by_hand_truth = inject.inject(profile, source.Noise(profile, SEED, SIGMA[0], SIGMA[1], LENGTH),
                                                  REAL, LENGTH)
    by_hand_stream = list(by_hand_stream)
    by_hand = tuple(Core(blob, 7).run(by_hand_stream))
    pairs, truth = run.scores(source.Noise(profile, SEED, SIGMA[0], SIGMA[1], LENGTH), REAL, LENGTH, blob, 7)
    pairs = list(pairs)
    assert [frame for frame, _record in pairs] == by_hand_stream
    assert tuple(record for _frame, record in pairs) == by_hand
    assert truth == by_hand_truth and list(truth) == REAL
    assert {record["epoch"] for _frame, record in pairs} == {7}, "the start epoch is carried, not dropped"
    records_only, truth_again = run.detect(source.Noise(profile, SEED, SIGMA[0], SIGMA[1], LENGTH), REAL, LENGTH, blob, 7)
    assert records_only == by_hand and truth_again == truth
    assert {r["epoch"] for r in run.detect(by_hand_stream, [], LENGTH, blob)[0]} == {0}, "and the default is 0"


@pytest.mark.parametrize("profile", PROFILES)
def test_seam_the_runner_refuses_by_the_parts_own_names_the_blob_before_the_schedule(profile):
    blob = blob_for(profile)
    channels = C.PROFILES[profile]["channels"]
    silence = [(0,) * channels] * 100
    broken = blob[:-1] + bytes([blob[-1] ^ 1])
    past_end = [rec(90, 1)]

    def name_of(call):
        with pytest.raises(Refusal) as e:
            call()
        return e.value.name

    assert name_of(lambda: run.scores(silence, [], 100, broken)) == "BLOB_HASH"
    assert name_of(lambda: run.scores(silence, past_end, 100, blob)) == "INJECT_PAST_END"
    assert name_of(lambda: run.scores(silence, past_end, 100, broken)) == "BLOB_HASH", "the blob is checked first"
    assert name_of(lambda: run.scores(silence, [], 100, blob, epoch=-1)) == "SWAP_EPOCH"
    # nothing is read from the stream before those refusals: a stream that cannot be read is never touched
    def unreadable():
        raise AssertionError("a frame was asked for")
        yield
    assert name_of(lambda: run.scores(unreadable(), past_end, 100, blob)) == "INJECT_PAST_END"
    # and a refusal while the pairs run ends them there; the pairs before it stand
    short = silence[:40]
    pairs, _truth = run.scores(short, [], 100, blob)
    got = []
    assert name_of(lambda: got.extend(pairs)) == "STREAM_LENGTH"
    assert len(got) == 40 and got[-1][1]["index"] == 39


# ------------------------------------------------------------ what a frame may be

class Tagged(tuple):
    """A frame that tries to carry something besides its samples."""
    truth = "a pulse begins here"


@pytest.mark.parametrize("profile", PROFILES)
def test_seam_a_frame_that_is_not_exactly_a_tuple_is_refused_everywhere_a_frame_is_taken(profile):
    prof = stream.profile(profile)
    plain = (0,) * prof["channels"]
    tagged = Tagged(plain)
    assert tagged == plain and tagged.truth
    blob = blob_for(profile)
    for what, call in (("the frame check", lambda: stream.check_frame(prof, tagged)),
                       ("the core", lambda: Core(blob).step(tagged)),
                       ("the injector", lambda: next(inject.inject(profile, [tagged], [], 1)[0])),
                       ("the runner", lambda: run.detect([tagged], [], 1, blob)),
                       ("a recording", lambda: source.stream_bytes(profile, [tagged])),
                       ("the scorer", lambda: Scorer(profile, 0, 0, 0, 0, 0, 1).feed(
                           tagged, {"index": 0, "epoch": 0, "flags": 0, "score": 0}))):
        with pytest.raises(Refusal) as e:
            call()
        assert e.value.name == "CHANNELS", what
    assert stream.check_frame(prof, plain) is plain

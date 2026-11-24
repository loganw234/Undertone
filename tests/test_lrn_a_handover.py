"""The hand-over (learn/handover.py): weights to a blob by the model's own rule, and the swap at a named index.

What the detector is handed is judged exactly. The expected integers are in vectors/lrn-a/rule.json,
worked by hand, or come from the definition's rule written again here in exact fractions. The
expected scores around a swap come from the statistics' float filter, which is exact for integer
coefficients and shares no code with the model.

Under both profiles, with every channel's row different.
"""
import json
import os
from fractions import Fraction

import numpy as np
import pytest

from spec import constants as C
from model import source, weights
from model.detector import Core
from model.refusal import Refusal
from stats import matched as stat_matched
from learn import handover, trainer
from learn.errors import LearnRefusal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = sorted(C.PROFILES)
PASS = C.RECTIFIERS["pass"]

with open(os.path.join(ROOT, "vectors", "lrn-a", "rule.json"), encoding="utf-8") as _f:
    V = {case["name"]: case for case in json.load(_f)["cases"]}


def rule_again(rows):
    """The definition's rule in exact fractions: peak to COEFF_MAX, half to even, the whole filter one set."""
    peak = max(abs(Fraction(v)) for row in rows for v in row)
    return tuple(tuple(round(Fraction(v) * C.COEFF_MAX / peak) for v in row) for row in rows)   # round() of a Fraction is half to even


def rows_for(profile, taps, salt):
    """A filter's rows for a profile: small integers, every channel's row different, none all zero.

    Two salts give two shapes, not multiples of one another: with one channel a multiple would
    quantise to the same blob, and a swap between the two would be a swap to the weights already
    active, which is the way D0 says the swap gate could pass while testing nothing."""
    channels = C.PROFILES[profile]["channels"]
    return tuple(tuple((3 * c + 1) * (k + 1) * (-1) ** (k + c) + salt * ((k * k) % 5) - c for k in range(taps))
                 for c in range(channels))


# ------------------------------------------------------------ the weights to a blob

@pytest.mark.parametrize("name", sorted(V))
def test_lrn_a_handover_the_hand_worked_weights_give_the_hand_worked_coefficients(name):
    case = V[name]
    rows = tuple(tuple(Fraction(n, d) for n, d in row) for row in case["weights"])
    blob = handover.candidate_blob(case["profile"], rows)
    want = tuple(tuple(row) for row in case["coefficients"])
    assert handover.coefficients(blob) == want == rule_again(rows)
    config = weights.unpack(blob)
    assert config["profile"] == case["profile"] and len(config["filters"]) == 1
    assert dict(config["filters"][0]) == {c: want[c] for c in range(len(want))}, "channel c holds row c, in order"
    assert (config["head"], config["rectifier"], config["pool"], config["score_shift"]) == ((1,), PASS, 1, 0)


def test_lrn_a_handover_a_tie_goes_to_the_even_integer_both_ways():
    blob = handover.candidate_blob("s16x1", ((Fraction(2), Fraction(4), Fraction(-2)),))
    assert handover.coefficients(blob) == ((65536, 131071, -65536),)
    assert 131071 / 2 == 65535.5, "the case is a tie: 65535 is odd, 65536 even"


@pytest.mark.parametrize("profile", PROFILES)
def test_lrn_a_handover_every_channels_row_is_quantised_as_one_set_and_kept_in_its_place(profile):
    rows = rows_for(profile, 7, 2)
    blob = handover.candidate_blob(profile, rows)
    assert handover.coefficients(blob) == rule_again(rows)
    assert rows_for(profile, 7, 2) != rows_for(profile, 7, 3) and len(set(rows)) == len(rows)
    if len(rows) > 1:
        # one set: a channel quantised alone would have its own peak at COEFF_MAX; here only the largest row does
        peaks = [max(abs(v) for v in row) for row in handover.coefficients(blob)]
        assert peaks.count(C.COEFF_MAX) == 1 and peaks.index(C.COEFF_MAX) == len(rows) - 1
        # and the rows exchanged give another blob
        assert handover.candidate_blob(profile, rows[::-1]) != blob
    # a positive multiple of the weights is the same blob; the negated weights are not
    assert handover.candidate_blob(profile, tuple(tuple(Fraction(v, 7) for v in row) for row in rows)) == blob
    assert handover.candidate_blob(profile, tuple(tuple(-v for v in row) for row in rows)) != blob


@pytest.mark.parametrize("profile", PROFILES)
def test_lrn_a_handover_the_blank_blob_is_every_coefficient_zero_and_scores_zero(profile):
    channels = C.PROFILES[profile]["channels"]
    blob = handover.blank_blob(profile, 5)
    assert handover.coefficients(blob) == ((0,) * 5,) * channels
    config = weights.unpack(blob)
    assert (config["head"], config["rectifier"], config["pool"], config["score_shift"]) == ((1,), PASS, 1, 0)
    records = list(Core(blob).run(source.Noise(profile, 3, 500, 1, 40)))
    assert [r["score"] for r in records] == [0] * 40 and {r["epoch"] for r in records} == {0}
    # a learned blob of the same taps has the blank blob's shape, so it can be swapped in over it
    assert weights.shape(weights.unpack(handover.candidate_blob(profile, rows_for(profile, 5, 1)))) == weights.shape(config)


@pytest.mark.parametrize("profile", PROFILES)
def test_lrn_a_handover_refuses_by_name(profile):
    channels = C.PROFILES[profile]["channels"]
    good = rows_for(profile, 4, 1)
    # the model's own refusals, by the model's own code, under the definition's names
    for bad, name in ((((0,) * 4,) * channels, "QUANTISE_INPUT"),                      # a blank learner's weights
                      (tuple(tuple(float(v) for v in row) for row in good), "QUANTISE_INPUT"),
                      (tuple(tuple(range(1, C.MAX_TAPS + 2)) for _ in good), "SHAPE_TAPS")):
        with pytest.raises(Refusal) as e:
            handover.candidate_blob(profile, bad)
        assert e.value.name == name
    for call in (lambda: handover.candidate_blob("s8x9", good), lambda: handover.blank_blob("s8x9", 4),
                 lambda: handover.candidate_blob(None, good)):
        with pytest.raises(Refusal) as e:
            call()
        assert e.value.name == "PROFILE_UNKNOWN"
    # this package's own
    ragged = (good[:-1] + ((1, 2, 3),),) if channels > 1 else ()         # one row shorter than the others
    for bad in (good + good[:1], good[:-1], ((),) * channels, 7, (5,) * channels) + ragged:
        with pytest.raises(LearnRefusal) as e:
            handover.candidate_blob(profile, bad)
        assert e.value.name == "CANDIDATE_SHAPE", bad
    with pytest.raises(LearnRefusal) as e:
        handover.blank_blob(profile, 0)
    assert e.value.name == "CANDIDATE_SHAPE"
    two = weights.pack(profile, [{0: (1, 2)}, {0: (3, 4)}], (1, 1), PASS, 1, 0)
    with pytest.raises(LearnRefusal) as e:
        handover.coefficients(two)
    assert e.value.name == "CANDIDATE_SHAPE"


# ------------------------------------------------------------ the swap, at a named index

AT, LENGTH, TAPS = 37, 90, 6


def swapped_run(profile, commit_at):
    """Records of a stream on which the blob of filter `new` is handed over, committed at `commit_at`."""
    old = handover.candidate_blob(profile, rows_for(profile, TAPS, 1))
    new = handover.candidate_blob(profile, rows_for(profile, TAPS, 5))
    frames = list(source.Noise(profile, 11, 900, 1, LENGTH))
    core = Core(old)
    records = []
    for frame in frames:
        if core.next_index == min(AT, commit_at):         # the candidate is ready when the next output is the named one
            handover.hand_over(core, new, commit_at)
        records.append(core.step(frame))
    x = np.array(frames, dtype=np.int64)
    by_old = [int(v) for v in stat_matched.matched_scores(x, profile, np.array(handover.coefficients(old))).tolist()]
    by_new = [int(v) for v in stat_matched.matched_scores(x, profile, np.array(handover.coefficients(new))).tolist()]
    return records, by_old, by_new


def first_index_of_the_new_epoch(records):
    new = [r["index"] for r in records if r["epoch"] != 0]
    return new[0] if new else None


@pytest.mark.parametrize("profile", PROFILES)
def test_lrn_a_handover_the_swap_lands_at_the_named_index(profile):
    records, by_old, by_new = swapped_run(profile, AT)
    assert [r["index"] for r in records] == list(range(LENGTH)) and all(r["flags"] == 0 for r in records)
    assert [r["epoch"] for r in records] == [0] * AT + [1] * (LENGTH - AT)
    assert first_index_of_the_new_epoch(records) == AT
    assert [r["score"] for r in records[:AT]] == by_old[:AT], "every output before the index is the old filter's"
    assert [r["score"] for r in records[AT:]] == by_new[AT:], "every output from it on is the new filter's"
    # the fault cannot hide: at the index itself, and one each side, the two filters give different scores
    assert all(by_old[i] != by_new[i] for i in (AT - 1, AT, AT + 1))


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("off", [1, -1])
def test_lrn_a_handover_control__a_blob_swapped_in_one_output_late_or_early_shows_in_the_epoch(profile, off):
    """The named control: the same check on a hand-over that commits one output away from the named index."""
    records, by_old, by_new = swapped_run(profile, AT + off)
    found = first_index_of_the_new_epoch(records)
    print("CONTROL hand-over, %s, committed at %d where %d was named: the first record of epoch 1 is index %d; "
          "record %d carries epoch %d and score %d (the old filter's %d, the new filter's %d)"
          % (profile, AT + off, AT, found, AT + min(off, 0), records[AT + min(off, 0)]["epoch"],
             records[AT + min(off, 0)]["score"], by_old[AT + min(off, 0)], by_new[AT + min(off, 0)]))
    assert found == AT + off != AT, "the check of the test above reports it: the new epoch does not start at the named index"
    assert [r["epoch"] for r in records] != [0] * AT + [1] * (LENGTH - AT)
    if off == 1:        # late: the named index still carries the old epoch and the old filter's score
        assert records[AT]["epoch"] == 0 and records[AT]["score"] == by_old[AT] != by_new[AT]
    else:               # early: the output before the named index already carries the new ones
        assert records[AT - 1]["epoch"] == 1 and records[AT - 1]["score"] == by_new[AT - 1] != by_old[AT - 1]


@pytest.mark.parametrize("profile", PROFILES)
def test_lrn_a_handover_passes_the_models_swap_refusals_through_by_name(profile):
    old = handover.candidate_blob(profile, rows_for(profile, TAPS, 1))
    new = handover.candidate_blob(profile, rows_for(profile, TAPS, 5))
    frames = list(source.Noise(profile, 11, 900, 1, 20))

    def name_of(call):
        with pytest.raises(Refusal) as e:
            call()
        return e.value.name

    core = Core(old)
    for frame in frames[:10]:
        core.step(frame)
    assert name_of(lambda: handover.hand_over(core, new, 9)) == "SWAP_INDEX"           # an output already made
    assert name_of(lambda: handover.hand_over(core, handover.candidate_blob(profile, rows_for(profile, TAPS + 1, 5)), 12)) \
        == "SWAP_SHAPE"
    assert core.step(frames[10])["epoch"] == 0, "a refused hand-over changed nothing"
    assert handover.hand_over(core, new, 14) == 14
    assert name_of(lambda: handover.hand_over(core, new, 16)) == "SWAP_PENDING"
    epochs = [core.step(frame)["epoch"] for frame in frames[11:]]
    assert epochs == [0] * 3 + [1] * 6


def test_lrn_a_handover_a_trainers_weights_go_through_unchanged():
    """The trainer's rows are in the order the hand-over packs: row c is channel c, tap 0 the oldest sample."""
    case = V["three-channels-each-different"]
    learner = trainer.train(np.array(case["frames"], dtype=np.int64), case["truth_indexes"], case["taps"])
    assert handover.coefficients(handover.candidate_blob("s24x3", learner.weights())) == tuple(tuple(r) for r in case["coefficients"])
    # and the blob's scores on that stream are the hand-worked rows against it: channel by channel, oldest first
    frames = [tuple(f) for f in case["frames"]]
    scores = [r["score"] for r in Core(handover.candidate_blob("s24x3", learner.weights())).run(frames)]
    rows = case["coefficients"]
    want = [sum(rows[c][k] * (frames[i - 1 + k][c] if i - 1 + k >= 0 else 0) for c in range(3) for k in range(2))
            for i in range(len(frames))]
    assert scores == want

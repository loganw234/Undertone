"""The blob the seam's bench hands over through the chain is the trainer's own, made again here.

The seam's bench (rtl/tb/bench_seam.py, the test `bit_identity_hand_over`) writes
learned weights to the detector core's shadow through the register port and
commits them at a named index. The trainer, `learn/`, needs numpy, and the
simulation image holds none; the lead ruled that the image stays as it is. So
the blob is made OUTSIDE the image and frozen in `vectors/seam-2/handover.json`,
and the bench reads its bytes and imports nothing of `learn/`.

THIS FILE HOLDS THE FROZEN FILE TO THE TRAINER. For each profile it makes the
model's own frames for the configuration the vector states (`model.source.Noise`
through `model.inject.inject`), trains `learn.trainer.train` on the training
period's frames with the truth indexes the vector states, hands the weights to
`learn.handover.candidate_blob`, and requires the frozen blob to be that blob,
byte for byte. The control: a trainer given labels one frame off, either way,
makes another blob.

WHAT THE VECTOR IS, AND IS NOT. It is an INPUT, pinned: the bytes a learner
produced, so that a simulator can be handed them. It is NOT a known answer
worked by hand, and nothing is judged by it. The expected score words of the
bench are the model's run with these weights, made inside the bench.

The start blob is not the learner's blank one. A blank filter scores every
frame 0, and the records before the hand-over would then say nothing of the
frames the trainer was given. The start blob has one tap that is not zero, the
newest, with another weight in each channel, so every record before the
hand-over is its own frame's weighted sum.

WHAT THIS DOES NOT HOLD, each a limit: that the learned filter is any good (no
efficiency is read and none is claimed: that is stage E1's, and the count here,
sixteen truth records, is the smallest of that stage's); that the bench hands
the design the bytes this file holds (the bench reads the same file, checks
the blob's SHA-256 as the file states it, and gives the design and the model
the same bytes; nothing here runs the bench); a vector changed together with
this test.
"""
import hashlib
import json
import os

import numpy as np
import pytest

from spec import constants as C
from model import inject, source, weights
from learn import handover, trainer

VECTOR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vectors", "seam-2", "handover.json")
PASS = C.RECTIFIERS["pass"]
PROFILES = sorted(C.PROFILES)


def load():
    with open(VECTOR, encoding="utf-8") as f:
        return json.load(f)


def model_frames(profile, case):
    """The frames the model's source and injector make for the vector's configuration."""
    stream, _truth = inject.inject(profile, source.Noise(profile, case["seed"], case["sigma"][0], case["sigma"][1],
                                                         case["frames"]), case["schedule"], case["frames"])
    return list(stream)


def trained_blob(profile, case, shift=0):
    """The trainer's blob: `learn/` on the training period's frames, the truth indexes moved by `shift`."""
    period = np.array(model_frames(profile, case)[:case["period"]], dtype=np.int64)
    learner = trainer.train(period, [j + shift for j in case["train_indexes"]], case["taps"])
    return handover.candidate_blob(profile, learner.weights())


def start_blob(profile, case):
    """One filter of the learner's shape whose only tap that is not zero is the newest, a weight a channel."""
    rows = {c: (0,) * (case["taps"] - 1) + (w,) for c, w in enumerate(case["start_newest_tap"])}
    return weights.pack(profile, [rows], (1,), PASS, 1, 0)


def test_seam2_the_vector_has_a_case_for_each_profile():
    assert sorted(load()["cases"]) == PROFILES


@pytest.mark.parametrize("profile", PROFILES)
def test_seam2_the_frozen_blob_is_the_trainers_on_the_models_frames(profile):
    case = load()["cases"][profile]
    blob = trained_blob(profile, case)
    assert blob.hex() == case["blob_hex"]
    assert hashlib.sha256(blob).hexdigest() == case["blob_sha256"]


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("shift", [1, -1])
def test_seam2_control_a_trainer_given_labels_a_frame_off_makes_another_blob(profile, shift):
    case = load()["cases"][profile]
    assert trained_blob(profile, case, shift).hex() != case["blob_hex"]


@pytest.mark.parametrize("profile", PROFILES)
def test_seam2_the_start_blob_is_one_tap_of_the_learners_shape(profile):
    case = load()["cases"][profile]
    start = start_blob(profile, case)
    assert start.hex() == case["start_hex"]
    assert len(case["start_newest_tap"]) == C.PROFILES[profile]["channels"]
    assert len(set(case["start_newest_tap"])) == len(case["start_newest_tap"]) and 0 not in case["start_newest_tap"]
    assert weights.shape(weights.unpack(start)) == weights.shape(weights.unpack(bytes.fromhex(case["blob_hex"])))
    assert start.hex() != case["blob_hex"]


@pytest.mark.parametrize("profile", PROFILES)
def test_seam2_the_vector_states_what_the_trainer_was_given(profile):
    case = load()["cases"][profile]
    indexes = [r["index"] for r in case["schedule"]]
    assert case["count"] == len(case["train_indexes"]) == 16
    assert indexes[:case["count"]] == case["train_indexes"]
    # every training record's two windows lie inside the period, and the hand-over is after it
    assert min(case["train_indexes"]) - case["taps"] >= 0 and max(case["train_indexes"]) + case["taps"] <= case["period"]
    assert case["period"] <= case["hand_over_at"] < min(indexes[case["count"]:])
    assert max(indexes) + len(C.PULSES["e0"]) <= case["frames"]
    assert case["taps"] == len(C.PULSES["e0"])

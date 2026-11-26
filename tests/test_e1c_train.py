"""E1C: the host trains on the desktop, and a set trained on the stretch it is judged on is refused.

The gate `comparison-rules`, rule 2 of D0's section 8 as the host's training meets it. For stage E1's parts 0 to 3,
the desktop's training (hw/e1c/e1c.py: `training_stream`, then E1's own trainer and hand-over on frames 0 to A - 1
and the truth records below A) must give the set E1's committed part carries: its coefficients, its blob's hash,
its counts and its refusal. Parts 4 and 5, 2,621,440 training frames, are held the same way by `cases` itself, which
refuses LEARNED_SET before it writes a case: a test of them would add about ten seconds to the gate. Expected answers: the committed parts, docs/studies/e1/c0.json to c5.json, read
for those four keys alone and never for `spec_sha256`, so that this holds whichever definition made them (the
lead's ruling, 2026-11-25 20:56).

The brief's named control: a learned set trained on windows from the stretch it is judged on is refused, as E1's
rule 2 refuses it. Three ways, each refused by name, and each layer shown to hold with the one before it taken out:
  - the training handed the whole stream with every truth record: TRAINED_ON (hw/e1c's check); with that check
    taken out, the set it makes is not E1's, LEARNED_SET;
  - the training handed frames 0 to A - 1 and a truth record of the judged stretch: TRAINED_ON; with the check
    taken out, the trainer's own refusal, WINDOW_OUTSIDE_PERIOD (learn/trainer.py), as LRN-A's rule-2 control has it;
  - the training handed the test stretch's own frames and truth records, as if they were the training's: TRAINED_ON;
    with the check taken out, LEARNED_SET.
On the short form's stream (1,155,072 frames), whose honest set is the one LRN-A's short form makes.
"""
import numpy as np
import pytest

from model import inject, source

import test_lrn_a_e1 as E1
from hw.e1c import e1c
from hw.e1c.errors import E1CRefusal
from learn.errors import LearnRefusal


GATE_PARTS = (0, 1, 2, 3)          # 174,080 training frames; parts 4 and 5, 2,621,440 more, are held by `cases`


def test_gate_comparison_rules__e1c_the_desktops_training_is_e1s_for_every_part():
    refs = e1c.committed_parts()
    assert sum(E1.plan(c)["A"] for c in GATE_PARTS) == 174080
    for c in GATE_PARTS:
        p = E1.plan(c)
        tr = e1c.training_stream(p, E1.schedule_for(p))
        assert len(tr["samples"]) == p["A"] and tr["labels"] == [64 + 128 * i for i in range(p["trained_on"])]
        learner, blob, refusal = e1c.train(p, tr["samples"], tr["labels"])
        info = e1c.learned_info(learner, blob, refusal)
        assert e1c.check_learned(c, info, refs[c]) == info
        assert info["learner_counts"] == [p["trained_on"]] * 2 and refusal is None
        assert info["coefficients"] == refs[c]["coefficients"] and info["blob_sha256"] == refs[c]["blob_sha256"]
        print("E1C training, part %d: %d truth records, blob %s..., E1's" % (c, p["trained_on"], info["blob_sha256"][:16]))


_short = {}


def short_stream():
    """The short form's whole stream as the injector makes it, its truth records, and its honest set."""
    if not _short:
        p = E1.plan("short")
        noise = source.Noise(E1.PROFILE, p["seed"], E1.SIGMA[0], E1.SIGMA[1], p["length"])
        frames, truth = inject.inject(E1.PROFILE, noise, E1.schedule_for(p), p["length"])
        x = np.array([f[0] for f in frames], dtype=np.int16).reshape(-1, 1)
        learner, blob, refusal = e1c.train(p, x[:p["A"]], [r["index"] for r in truth if r["index"] < p["A"]])
        _short.update(p=p, x=x, truth=truth, honest=e1c.learned_info(learner, blob, refusal))
    return _short


def test_e1c_the_short_forms_honest_set_is_the_one_lrn_as_short_form_makes():
    s = short_stream()
    _got, part = E1.short()
    assert s["honest"]["coefficients"] == part["coefficients"] and s["honest"]["blob_sha256"] == part["blob_sha256"]
    assert s["honest"]["learner_counts"] == part["learner_counts"] == [1024, 1024]


def test_control_comparison_rules__e1c_a_set_trained_on_the_judged_stretch_is_refused(monkeypatch):
    s = short_stream()
    p, x, truth, honest = s["p"], s["x"], s["truth"], s["honest"]
    a, b = p["A"], p["B"]
    every = [r["index"] for r in truth]
    test = [r["index"] - b for r in truth if r["index"] >= b]
    cheats = {
        "the whole stream with every truth record": (x, every),
        "frames below A and a truth record of the judged stretch": (x[:a], [r["index"] for r in truth if r["index"] < a] + [b + 64]),
        "the test stretch's own frames and truth records": (x[b:], test),
    }
    for what, (frames, labels) in cheats.items():
        with pytest.raises(LearnRefusal) as e:
            e1c.train(p, frames, labels)
        print("CONTROL rule 2, %s: %s" % (what, str(e.value)[:150]))
        assert e.value.name == "TRAINED_ON", what
    # each layer holds with the one before it taken out
    monkeypatch.setattr(e1c, "check_training", lambda *args: None)
    for what in ("the whole stream with every truth record", "the test stretch's own frames and truth records"):
        frames, labels = cheats[what]
        learner, blob, refusal = e1c.train(p, frames, labels)
        info = e1c.learned_info(learner, blob, refusal)
        assert info["coefficients"] != honest["coefficients"]
        with pytest.raises(E1CRefusal) as e:
            e1c.check_learned("short", info, honest)
        print("CONTROL rule 2 with hw/e1c's check taken out, %s: %s" % (what, str(e.value)[:150]))
        assert e.value.name == "LEARNED_SET"
    frames, labels = cheats["frames below A and a truth record of the judged stretch"]
    with pytest.raises(LearnRefusal) as e:
        e1c.train(p, frames, labels)
    print("CONTROL rule 2 with hw/e1c's check taken out, a held-out truth record: %s" % str(e.value)[:150])
    assert e.value.name == "WINDOW_OUTSIDE_PERIOD"
    # and the honest training, through the same road, is E1's
    learner, blob, refusal = e1c.train(p, x[:a], [r["index"] for r in truth if r["index"] < a])
    assert e1c.check_learned("short", e1c.learned_info(learner, blob, refusal), honest)


def test_e1c_the_training_check_refuses_each_thing_it_checks_alone():
    """check_training's two conditions, each alone: one frame too many, one too few, and one label whose signal window
    ends at A rather than at A - 1. A label whose window ends at A - 1 is taken."""
    p = E1.plan(0)
    a = p["A"]
    x = np.zeros((a, 1), dtype=np.int16)
    e1c.check_training(p, x, [a - 64])
    for frames, labels in ((np.zeros((a + 1, 1), dtype=np.int16), [64]), (np.zeros((a - 1, 1), dtype=np.int16), [64]),
                           (x, [64, a - 63])):
        with pytest.raises(LearnRefusal) as e:
            e1c.check_training(p, frames, labels)
        assert e.value.name == "TRAINED_ON"
    info = {"coefficients": [1], "blob_sha256": "x", "learner_counts": [1, 1], "handover_refusal": None}
    for key in e1c.TRAINING_KEYS:
        with pytest.raises(E1CRefusal) as e:
            e1c.check_learned(0, info, dict(info, **{key: "other"}))
        assert e.value.name == "LEARNED_SET" and key in str(e.value)

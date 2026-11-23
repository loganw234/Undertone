"""The swap gate, for the head's hidden layer: every output uses the weights its epoch names.

With a hidden layer the head's weights are the hidden units' weights and the head weights. They exchange with
the coefficients, whole, at the swap's index. The hidden layer remembers nothing, so nothing mixes that did
not mix before: `settling` still marks exactly the outputs whose POOL holds values made under two sets.

The known answers are vectors/head/swap.json, worked by hand, and the definition written a second time
(test_head_support.direct_records), once per weight set. Every swap here is to weights that DIFFER from the
active ones; the last test shows what a swap to the same weights would have hidden.
"""
import random

import pytest

from spec import constants as C
from model.detector import Core

import test_mod_b_support as S
import test_head_support as H

PROFILES = H.PROFILES


def weight_sets(profile, count, seed):
    """`count` configurations of one shape whose every coefficient, hidden weight and head weight differs from set to set."""
    last = str(C.PROFILES[profile]["channels"] - 1)
    rng = random.Random(seed)
    sets = []
    for n in range(count):
        def some(k):
            return [rng.randint(1, 40) * rng.choice((-1, 1)) + 1000 * (n + 1) for _ in range(k)]
        sets.append({"filters": [{last: some(3)}, {"0": some(3)}], "hidden": [some(2), some(2), some(2)], "hidden_shift": 4,
                     "between": H.ABS, "head": some(3), "rectifier": 0, "pool": 1, "score_shift": 2})
    return sets


def check_epochs(profile, core=Core, same_weights=False):
    """Findings: with no pool, each record's score against the weights its epoch names, by the definition written out."""
    at = [5, 9, 17]
    sets = weight_sets(profile, len(at) + 1, seed=4)
    if same_weights:
        sets = [sets[0]] * len(sets)
    frames = S.varied_frames(profile, 24, seed=8)
    by_set = [H.direct_records(s, frames) for s in sets]
    c = core(H.blob_of(profile, sets[0]))
    findings, pending = [], list(zip(at, sets[1:]))
    for i, frame in enumerate(frames):
        if pending and not c.store.pending():
            index, new = pending.pop(0)
            c.write_shadow(H.blob_of(profile, new))
            c.commit(index)
        got = c.step(frame)
        epoch = sum(1 for a in at if a <= i)                 # how many swaps have happened by output i
        findings += S.compare("epochs", [got], [dict(by_set[epoch][i], epoch=epoch)])
    return findings


# ------------------------------------------------------------------ the gate

@pytest.mark.parametrize("profile", PROFILES)
def test_gate_swap__hidden_layer_records_equal_the_hand_worked_swap_vectors(profile):
    todo = H.cases("swap.json", profile)
    findings, n = H.check_cases(todo)
    assert findings == []
    assert n == 1
    for case in todo:
        written = [s["write"] for s in case["swaps"]]
        assert all(w[part] != case["config"][part] for w in written for part in ("filters", "hidden", "head")), \
            "a swap to other coefficients, other hidden weights and other head weights"
        assert len({r["epoch"] for r in case["records"]}) == 2


def test_gate_swap__a_hand_worked_swap_with_a_hidden_layer_crosses_a_pool():
    assert any(r["flags"] & S.SETTLING for p in PROFILES for case in H.cases("swap.json", p) for r in case["records"])


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_swap__with_a_hidden_layer_every_output_uses_the_weights_its_epoch_names(profile):
    assert check_epochs(profile) == []


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("pool", [1, 2, 5])
@pytest.mark.parametrize("at", [0, 1, 7])
def test_gate_swap__with_a_hidden_layer_settling_marks_exactly_the_outputs_the_pool_mixes(profile, pool, at):
    """Outputs at .. at + P - 2 mix, unless the swap is at 0; their scores are still the defined sums.

    The hidden sums and the output sum of every output, mixed or not, are of ONE set: the one active at it.
    """
    last = C.PROFILES[profile]["channels"] - 1
    shape = {"hidden_shift": 1, "between": H.ABS, "rectifier": H.ABS, "pool": pool, "score_shift": 0}
    old = dict(shape, filters=[{str(last): [2, -3]}], hidden=[[3], [-2]], head=[1, 5])
    new = dict(shape, filters=[{str(last): [-7, 5]}], hidden=[[-1], [4]], head=[-6, 2])
    frames = S.varied_frames(profile, 20, seed=at + 31 * pool, small=True)
    core = Core(H.blob_of(profile, old))
    core.write_shadow(H.blob_of(profile, new))
    core.commit(at)
    got = list(core.run(frames))

    def r(i):                                    # the rectified filter value at i, under the set active at i
        w = (new if i >= at else old)["filters"][0][str(last)]
        return abs(w[0] * (frames[i - 1][last] if i else 0) + w[1] * frames[i][last])

    for i, g in enumerate(got):
        active = new if i >= at else old
        mixes = at >= 1 and at <= i <= at + pool - 2
        z = sum(r(m) for m in range(max(0, i - pool + 1), i + 1))
        between = [abs((unit[0] * z) // 2) for unit in active["hidden"]]
        expected = {"index": i, "epoch": 1 if i >= at else 0, "flags": S.SETTLING if mixes else 0,
                    "score": sum(o * b for o, b in zip(active["head"], between))}
        assert S.compare("pool %d at %d" % (pool, at), [g], [expected]) == []
    assert sum(1 for g in got if g["flags"] & S.SETTLING) == (pool - 1 if at >= 1 else 0)


# --------------------------------------------------------------- the controls

def late(which):
    """A core in which one half of the head's weights changes one output after the swap's index."""

    class Late(Core):
        def __init__(self, blob, epoch=0):
            super().__init__(blob, epoch)
            store, honest = self.store, self.store.step

            def step():
                before = store.active
                rows, head, epoch_, settling = honest()
                if store.active is not before:
                    units, out = head
                    old_units, old_out = before[1]
                    head = (units, old_out) if which == "head" else (old_units, out)
                return rows, head, epoch_, settling

            store.step = step

    Late.__name__ = "The%sWeightsOneOutputLate" % which.capitalize()
    return Late


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("which", ["head", "hidden"])
def test_control_swap__half_the_heads_weights_an_output_late_is_caught_by_the_vectors(profile, which):
    todo = H.cases("swap.json", profile)
    findings, _n = H.check_cases(todo, core=late(which))
    at = todo[0]["swaps"][0]["at"]
    named = [f for f in findings if f.startswith("%s: record %d " % (todo[0]["name"], at))]
    assert len(named) == 1 and len(findings) == 1, findings
    print("CONTROL swap, the %s weights an output late, %s:" % (which, profile), named[0])


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("which", ["head", "hidden"])
def test_control_swap__half_the_heads_weights_an_output_late_is_caught_by_the_epoch_check(profile, which):
    findings = check_epochs(profile, core=late(which))
    assert len(findings) == 3, "one wrong output at each of the three swaps"
    assert [f.split("record ")[1].split(" ")[0] for f in findings] == ["5", "9", "17"]
    print("CONTROL swap, epoch check, the %s weights an output late, %s:" % (which, profile), findings[0])


@pytest.mark.parametrize("profile", PROFILES)
def test_head_swapping_to_the_weights_already_active_would_have_hidden_that_fault(profile):
    """Why every swap above is to other weights: the same broken cores pass when the sets are equal."""
    for which in ("head", "hidden"):
        assert check_epochs(profile, core=late(which), same_weights=True) == []
        assert check_epochs(profile, core=late(which), same_weights=False) != []

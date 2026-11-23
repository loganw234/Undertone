"""The swap gate: every output uses the weights its epoch field names.

Known answers: vectors/mod-b/swap.json, worked by hand, and the definition written out a second time
(test_mod_b_support.direct_scores), once per weight set. Every swap here is to weights that DIFFER from
the active ones; the last test shows what a swap to the same weights would have hidden.
"""
import random

import pytest

from spec import constants as C
from model import weights
from model.detector import Core

import test_mod_b_support as S

PROFILES = S.PROFILES


def weight_sets(profile, taps, count, seed):
    """`count` configurations of one shape whose every coefficient differs from set to set."""
    last = str(C.PROFILES[profile]["channels"] - 1)
    rng = random.Random(seed)
    sets = []
    for n in range(count):
        sets.append({"filters": [{last: [rng.randint(1, 50) + 100 * n for _ in range(taps)]}], "head": [n + 1],
                     "rectifier": 0, "pool": 1, "score_shift": 0})
    return sets


def check_epochs(profile, core=Core, same_weights=False):
    """Findings: with no pool, each record's score against the weights its epoch names, by the direct sum."""
    taps, at = 4, [5, 9, 17]
    sets = weight_sets(profile, taps, len(at) + 1, seed=4)
    if same_weights:
        sets = [sets[0]] * len(sets)
    frames = S.varied_frames(profile, 24, seed=8)
    by_set = [S.direct_scores(s, frames) for s in sets]
    c = core(S.blob_of(profile, sets[0]))
    findings, pending = [], list(zip(at, sets[1:]))
    for i, frame in enumerate(frames):
        if pending and not c.store.pending():
            index, new = pending.pop(0)
            c.write_shadow(S.blob_of(profile, new))
            c.commit(index)
        got = c.step(frame)
        epoch = sum(1 for a in at if a <= i)                 # how many swaps have happened by output i
        expected = {"index": i, "epoch": epoch, "flags": 0, "score": by_set[epoch][i]}
        findings += S.compare("epochs", [got], [expected])
    return findings


# ------------------------------------------------------------------ the gate

@pytest.mark.parametrize("profile", PROFILES)
def test_gate_swap__records_equal_the_hand_worked_swap_vectors(profile):
    findings, n = S.check_vectors("swap.json", profile)
    assert findings == []
    assert n == 2
    for case in S.cases("swap.json", profile):
        written = [s["write"] for s in case["swaps"] if s["write"] is not None]
        assert written and all(w["filters"] != case["config"]["filters"] for w in written), "a swap to other weights"
        assert len({r["epoch"] for r in case["records"]}) >= 2
    assert any(r["flags"] & S.SETTLING for case in S.cases("swap.json", profile) for r in case["records"])


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_swap__every_output_uses_the_weights_its_epoch_names(profile):
    assert check_epochs(profile) == []


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("pool", [1, 2, 5])
@pytest.mark.parametrize("at", [0, 1, 7])
def test_gate_swap__settling_marks_exactly_the_outputs_that_mix(profile, pool, at):
    """Outputs at .. at + P - 2 mix, unless the swap is at 0; their scores are still the defined sums."""
    last = C.PROFILES[profile]["channels"] - 1
    old = {"filters": [{str(last): [2, -3]}], "head": [1], "rectifier": 1, "pool": pool, "score_shift": 0}
    new = {"filters": [{str(last): [-7, 5]}], "head": [4], "rectifier": 1, "pool": pool, "score_shift": 0}
    frames = S.varied_frames(profile, 20, seed=at + 31 * pool, small=True)
    core = Core(S.blob_of(profile, old))
    core.write_shadow(S.blob_of(profile, new))
    core.commit(at)
    got = list(core.run(frames))

    def r(i):                                    # the rectified filter value at i, under the set active at i
        w = (new if i >= at else old)["filters"][0][str(last)]
        return abs(w[0] * (frames[i - 1][last] if i else 0) + w[1] * frames[i][last])

    for i, g in enumerate(got):
        mixes = at >= 1 and at <= i <= at + pool - 2
        z = sum(r(m) for m in range(max(0, i - pool + 1), i + 1))
        expected = {"index": i, "epoch": 1 if i >= at else 0, "flags": S.SETTLING if mixes else 0,
                    "score": (4 if i >= at else 1) * z}
        assert S.compare("pool %d at %d" % (pool, at), [g], [expected]) == []
    assert sum(1 for g in got if g["flags"] & S.SETTLING) == (pool - 1 if at >= 1 else 0)


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_swap__the_shadow_holds_the_old_set_after_a_swap_and_the_epoch_counts_swaps(profile):
    sets = weight_sets(profile, 3, 2, seed=6)
    frames = S.varied_frames(profile, 12, seed=9)
    by_set = [S.direct_scores(s, frames) for s in sets]
    core = Core(S.blob_of(profile, sets[0]), epoch=41)
    core.write_shadow(S.blob_of(profile, sets[1]))
    scores, epochs = [], []
    for i, frame in enumerate(frames):
        if i in (3, 6, 9):
            core.commit(i)                       # the second and third commits write nothing: they exchange back
        rec = core.step(frame)
        scores.append(rec["score"])
        epochs.append(rec["epoch"])
    which = [0, 0, 0, 1, 1, 1, 0, 0, 0, 1, 1, 1]
    assert scores == [by_set[w][i] for i, w in enumerate(which)]
    assert epochs == [41, 41, 41, 42, 42, 42, 43, 43, 43, 44, 44, 44]


# --------------------------------------------------------------- the control

class HalfTheTapsLate(Core):
    """At the swap's index the even-numbered taps are new and the odd-numbered are still old; one output later all are new."""

    def __init__(self, blob, epoch=0):
        super().__init__(blob, epoch)
        store, honest = self.store, self.store.step

        def step():
            before = store.active
            rows, head, epoch, settling = honest()
            if store.active is not before:
                rows = tuple(tuple((c, tuple(n if j % 2 == 0 else o for j, (n, o) in enumerate(zip(new, old))))
                                   for (c, new), (_c, old) in zip(new_rows, old_rows))
                             for new_rows, old_rows in zip(rows, before[0]))
            return rows, head, epoch, settling

        store.step = step


@pytest.mark.parametrize("profile", PROFILES)
def test_control_swap__half_the_taps_a_sample_late_is_caught_by_the_vectors(profile):
    findings, _n = S.check_vectors("swap.json", profile, core=HalfTheTapsLate)
    case = [c for c in S.cases("swap.json", profile) if "pool-1" in c["name"]][0]
    at = case["swaps"][0]["at"]
    named = [f for f in findings if f.startswith("%s: record %d " % (case["name"], at))]
    assert len(named) == 1, findings
    assert not any(f.startswith("%s: record %d " % (case["name"], at + 1)) for f in findings), "one sample late, not two"
    print("CONTROL swap, half the taps a sample late, %s:" % profile, named[0])


@pytest.mark.parametrize("profile", PROFILES)
def test_control_swap__half_the_taps_a_sample_late_is_caught_by_the_epoch_check(profile):
    findings = check_epochs(profile, core=HalfTheTapsLate)
    assert len(findings) == 3, "one wrong output at each of the three swaps"
    assert [f.split("record ")[1].split(" ")[0] for f in findings] == ["5", "9", "17"]
    print("CONTROL swap, epoch check, %s:" % profile, findings[0])


@pytest.mark.parametrize("profile", PROFILES)
def test_mod_b_swapping_to_the_weights_already_active_would_have_hidden_that_fault(profile):
    """Why every swap above is to other weights: the same broken core passes when the sets are equal."""
    assert check_epochs(profile, core=HalfTheTapsLate, same_weights=True) == []
    assert check_epochs(profile, core=HalfTheTapsLate, same_weights=False) != []


# ------------------------------------------------- the store as a state machine

@pytest.mark.parametrize("profile", PROFILES)
def test_mod_b_a_swap_is_pending_until_its_last_mixed_output(profile):
    pool = 4
    blob = S.blob_of(profile, S.a_config(profile, pool=pool))
    store = weights.Store(blob)
    assert not store.pending()
    store.commit(3)
    seen = []
    for i in range(10):
        seen.append(store.pending())              # asked before output i is produced
        store.step()
    # waiting before outputs 0..3; outputs 3, 4, 5 mix (3 .. 3 + 4 - 2); free again before output 6
    assert seen == [True, True, True, True, True, True, False, False, False, False]


@pytest.mark.parametrize("profile", PROFILES)
def test_mod_b_the_shadow_may_be_written_while_outputs_still_mix_and_a_commit_may_not(profile):
    """After a swap's index the shadow holds the set that was active, and is free to take the next candidate."""
    pool = 4
    first, second, third = [S.blob_of(profile, dict(S.a_config(profile, pool=pool), head=[h])) for h in (1, 2, 3)]
    frames = S.varied_frames(profile, 12, seed=21, small=True)
    core = Core(first)
    core.write_shadow(second)
    core.commit(2)
    with pytest.raises(weights.Refusal) as e:
        core.write_shadow(third)                              # before the index: the shadow is what will become active
    assert e.value.name == "SWAP_PENDING"
    out = [core.step(f) for f in frames[:3]]                  # outputs 0, 1, 2; outputs 2, 3, 4 mix
    core.write_shadow(third)                                  # allowed: the swap has happened
    with pytest.raises(weights.Refusal) as e:
        core.commit(6)
    assert e.value.name == "SWAP_PENDING"
    out += [core.step(f) for f in frames[3:5]]
    core.commit(6)                                            # output 4 was the last to mix
    out += [core.step(f) for f in frames[5:]]
    assert [r["epoch"] for r in out] == [0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2]
    assert [bool(r["flags"] & S.SETTLING) for r in out] == [False, False, True, True, True, False, True, True, True, False, False, False]
    plain = [r["score"] for r in Core(first).run(frames)]     # head 1; the three sets differ only in the head weight
    assert [r["score"] for r in out] == [s * h for s, h in zip(plain, [1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3])]

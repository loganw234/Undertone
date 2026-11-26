"""LRN-C: each host operation's window of next indexes, held against the model rather than trusted.

WHAT THIS HOLDS:
  - THE ARGUMENT (hw/lrnc/windows.py, docs/host/lrn-c.md section 3): for every operation of the three cases at
    M = 1,024, the model's run with that operation moved to its window's lo, and to its hi, is the canonical run
    (records, outcomes, counts, status, the learner's sets); moved to lo - 1, and to hi + 1, its own outcome is
    another. So each window is the model's, edge for edge. (`expect` holds every lo at once and every hi at once,
    at full scale.)
  - THE TABLES OF THE DOC, at M = 2^20: every window and margin of docs/host/lrn-c.md section 4, cell by cell, is
    what `rule` makes from the outcomes the doc states; and every "after" is the doc's.
  - THE GUARD: every operation whose window's lo is a finish or a pending's end waits for lo + G, G = M / 256.
  - the refusals of the rule: SCRIPT_WINDOW for an outcome no rule covers, a placement outside its window, edge
    placements that cannot keep the order; SCRIPT_LATCH for a case whose operation lands on a latched
    QUANTISE_INPUT; the case's intended outcomes held.
"""
import json
import os

import pytest

from spec import constants as C

from hw.lrnc import lrnc, windows as W
from hw.lrnc.errors import LrncRefusal

M = 1024
F = C.LEARN_UPDATE_FRAMES


def info_of(name, m=M):
    info = lrnc.case(name, m)
    info["blobs"] = {"blank.blob": lrnc.blank_blob(), "matched.blob": lrnc.matched_blob()}
    return info


def run(info, placed):
    sink = lrnc._Sink()
    got = lrnc.run_case_model(info, placed, sink)
    return got, sink.close()["sha256"]


_CANON = {}


def canonical(name):
    if name not in _CANON:
        info = info_of(name)
        got, sha = run(info, [op["after"] for op in info["script"]])
        wins = W.rule(info["script"], got["outcomes"], got["learner"].updates, info["frames"], F)
        _CANON[name] = (info, got, sha, wins, lrnc._summary(got, info))
    return _CANON[name]


def moved(placed, k, to):
    """The placement with operation k at `to`, the others moved only as far as the script's order needs."""
    out = list(placed)
    out[k] = to
    for j in range(k):
        out[j] = min(out[j], to)
    for j in range(k + 1, len(out)):
        out[j] = max(out[j], to)
    return out


CASE_OPS = [(name, k) for name in lrnc.CASES for k in range(len(lrnc.case(name, M)["script"]))]


@pytest.mark.parametrize("name, k", CASE_OPS)
def test_lrn_c_an_operation_at_its_windows_lo_or_hi_gives_the_canonical_run_and_just_outside_another_outcome(name, k):
    info, got, sha, wins, summary = canonical(name)
    lo, hi = wins[k]
    placed = [op["after"] for op in info["script"]]
    tried = 0
    for edge in (lo, hi):
        if edge is None:
            continue
        p = moved(placed, k, edge)
        assert all((a is None or x >= a) and (b is None or x <= b) for x, (a, b) in zip(p, wins)), (edge, p)
        other, other_sha = run(info, p)
        assert other_sha == sha, "operation %d at %d: other records" % (k, edge)
        assert lrnc._summary(other, info) == summary, "operation %d at %d: another run" % (k, edge)
        tried += 1
    for outside in ((lo - 1) if lo is not None and lo >= 1 else None, (hi + 1) if hi is not None else None):
        if outside is None or outside > info["frames"]:
            continue
        other, _sha = run(info, moved(placed, k, outside))
        assert other["outcomes"][k] != got["outcomes"][k], "operation %d at %d, outside [%s, %s]: the same outcome %r" % (
            k, outside, lo, hi, got["outcomes"][k])
        tried += 1
    assert tried >= 2, "operation %d of %s: fewer than two placements could be tried" % (k, name)


def test_lrn_c_the_canonical_outcomes_are_each_cases_intended_ones():
    for name in lrnc.CASES:
        info, got, _sha, _wins, _s = canonical(name)
        assert got["outcomes"] == info["intended"], name


# ------------------------------------------------------------------ the doc's tables, at the card's M

FULL = lrnc.M_CARD


def _full(name):
    c = lrnc.case(name, FULL)
    m = FULL
    if name == "rich":
        updates = [{"u": m, "finish": m + F, "outcome": "unmade"}, {"u": 3 * m, "finish": 3 * m + F, "outcome": "made"},
                   {"u": 5 * m, "finish": 5 * m + F, "outcome": "made"}]
    else:
        u = c["script"][0]["arg"]
        updates = [{"u": u, "finish": u + F, "outcome": "made"}]
    return c, W.rule(c["script"], c["intended"], updates, c["frames"], F)


DOC = {
    "flow": {"after": [0, 1052928], "windows": [(0, 1048576), (1048832, 2097152)], "margins": [1048576, 1044224]},
    "moved": {"after": [0, 1053056], "windows": [(0, 1048704), (1048960, 2097152)], "margins": [1048704, 1044096]},
    "rich": {"after": [0, 1052928, 1052928, 1052928, 1052928, 1052928, 3150080, 3150080, 3150080, 4198401, 4198401,
                       4198401, 5247232],
             "windows": [(0, 1048576), (1048832, None), (1048832, 3145728), (None, 3145983), (None, 3145983),
                         (None, 3145983), (3145984, 4194304), (None, 4194304), (None, 4194304), (4194305, None),
                         (4194305, None), (4194305, 5242880), (5243136, 6291456)],
             "margins": [1048576, None, 2092800, 2093055, 2093055, 2093055, 1044224, 1044224, 1044224, None, None,
                         1044479, 1044224]},
}


@pytest.mark.parametrize("name", lrnc.CASES)
def test_lrn_c_the_docs_windows_afters_and_margins_at_the_cards_m_are_the_rules(name):
    c, wins = _full(name)
    assert [op["after"] for op in c["script"]] == DOC[name]["after"]
    assert wins == DOC[name]["windows"]
    assert W.margins(c["script"], wins) == DOC[name]["margins"]
    W.check_canonical(c["script"], wins, c["frames"])
    W.edge_placements(c["script"], wins, c["frames"])


def test_lrn_c_the_docs_frames_records_and_arguments_at_the_cards_m():
    flow, rich, mv = (lrnc.case(n, FULL) for n in ("flow", "rich", "moved"))
    assert (flow["frames"], rich["frames"], mv["frames"]) == (4194304, 7340032, 4194304)
    assert (len(flow["schedule"]), len(rich["schedule"]), len(mv["schedule"])) == (32768, 40962, 32768)
    assert rich["schedule"][0]["index"] == 0 and 2621440 in [r["index"] for r in rich["schedule"]]
    assert [op.get("arg") for op in rich["script"]] == [1048576, None, 3145728, 4194304, None, 3146240, 4194304,
                                                        6291456, None, 1, 1, 5242880, 6291456]
    assert flow["schedule"][-1]["index"] + 64 == flow["frames"] and rich["schedule"][-1]["index"] + 64 == rich["frames"]
    runs = [case for _run, case in lrnc.RUNS]
    assert runs == ["flow", "rich", "moved", "flow"]
    assert sum(lrnc.case(n, FULL)["frames"] for n in runs) == 19922944
    fed = sum(len(lrnc.case(n, FULL)["schedule"]) for n in runs)
    assert fed == 139266 and fed - 4 * C.MAX_INJECT_PENDING == 135170
    from host import library as L
    assert max(lrnc.case(n, FULL)["frames"] for n in runs) * L.SLOT + L.GUARD == 234884992
    assert 7340032 <= 8388484 and 19922944 * 21 == 418381824
    assert (4194304 * 2 + 7340032) * 21 == 330301440


@pytest.mark.parametrize("name", lrnc.CASES)
def test_lrn_c_every_wait_after_a_finish_or_a_pendings_end_is_lo_plus_the_guard(name):
    for m in (M, FULL):
        c, g = lrnc.case(name, m), lrnc.guard(m)
        wins = _full(name)[1] if m == FULL else canonical(name)[3]
        assert g == m // 256
        for op, (lo, _hi) in zip(c["script"], wins):
            if lo:
                assert op["after"] == lo + g, (name, m, op, lo)


# ------------------------------------------------------------------ the rule's refusals

def test_lrn_c_the_folders_own_names_are_declared_and_an_undeclared_one_is_not_made():
    from hw.lrnc import errors
    assert errors.LRNC_NAMES == ("SCRIPT_WINDOW", "SCRIPT_LATCH", "EDGES_DIFFER", "COUNTS_BY_HAND")
    assert not set(errors.LRNC_NAMES) & set(C.REFUSALS)
    with pytest.raises(ValueError):
        LrncRefusal("SCRIPT_WINDOWS")


def test_lrn_c_an_outcome_no_rule_covers_is_refused_script_window():
    c = lrnc.case("flow", M)
    for outcomes in ([None, "SWAP_EPOCH"], ["SWAP_SHAPE", None], [None, "QUANTISE_INPUT"]):
        with pytest.raises(LrncRefusal) as e:
            W.rule(c["script"], outcomes, [{"u": M, "finish": M + F, "outcome": "made"}], c["frames"], F)
        assert e.value.name == "SCRIPT_WINDOW"


def test_lrn_c_a_placement_outside_its_window_and_an_order_that_cannot_be_kept_are_refused():
    c = lrnc.case("flow", M)
    with pytest.raises(LrncRefusal) as e:
        W.check_canonical(c["script"], [(0, M), (5000, 6000)], c["frames"])
    assert e.value.name == "SCRIPT_WINDOW"
    with pytest.raises(LrncRefusal) as e:
        W.check_canonical(c["script"], [(1, M), (None, None)], c["frames"])
    assert e.value.name == "SCRIPT_WINDOW"
    with pytest.raises(LrncRefusal) as e:
        W.edge_placements(c["script"], [(3000, None), (None, 2000)], c["frames"])
    assert e.value.name == "SCRIPT_WINDOW"
    with pytest.raises(LrncRefusal) as e:
        W.run_script("s16x1", 1, (1477, 1), 10, [], lrnc.blank_blob(), c["script"], [5, 3], F, 32)
    assert e.value.name == "SCRIPT_WINDOW"


def test_lrn_c_a_case_whose_operation_lands_on_the_latch_is_refused_script_latch(tmp_path):
    folder = lrnc.cases(str(tmp_path / "cases"), M)
    import json
    import os
    path = os.path.join(folder, "rich", "script.json")
    script = json.load(open(path, encoding="utf-8"))
    assert script[1]["op"] == "clear"
    del script[1]
    json.dump(script, open(path, "w", encoding="utf-8"))
    case_path = os.path.join(folder, "rich", "case.json")
    info = json.load(open(case_path, encoding="utf-8"))
    del info["intended"][1]
    json.dump(info, open(case_path, "w", encoding="utf-8"))
    with pytest.raises(LrncRefusal) as e:
        lrnc.expect(folder, "rich")
    assert e.value.name == "SCRIPT_LATCH" and "operation 1" in e.value.detail


def test_lrn_c_a_case_whose_model_outcome_is_not_its_intended_one_is_refused(tmp_path):
    import json
    import os
    folder = lrnc.cases(str(tmp_path / "cases"), M)
    case_path = os.path.join(folder, "flow", "case.json")
    info = json.load(open(case_path, encoding="utf-8"))
    info["intended"] = [None, "UPDATE_UNFINISHED"]
    json.dump(info, open(case_path, "w", encoding="utf-8"))
    with pytest.raises(LrncRefusal) as e:
        lrnc.expect(folder, "flow")
    assert e.value.name == "SCRIPT_WINDOW" and "intended" in e.value.detail


def test_lrn_c_the_counts_worked_by_hand_are_the_models_and_one_changed_is_refused(monkeypatch, tmp_path):
    for name in lrnc.CASES:
        _info, got, _sha, _wins, summary = canonical(name)
        hand = lrnc.by_hand(name, M)
        assert [(u["u"], u["counts"][0], u["counts"][1]) for u in summary["updates"]] == hand["updates"], name
        assert summary["end"]["counts"] == hand["end"], name
    folder = lrnc.cases(str(tmp_path / "cases"), M)
    real = lrnc.by_hand

    def off_by_one(name, m):
        out = real(name, m)
        out["end"]["lrn_skip_busy"] += 1
        return out
    monkeypatch.setattr(lrnc, "by_hand", off_by_one)
    with pytest.raises(LrncRefusal) as e:
        lrnc.expect(folder, "rich")
    assert e.value.name == "COUNTS_BY_HAND"


def test_lrn_c_expect_refuses_a_case_whose_edges_differ(monkeypatch, tmp_path):
    """A window rule made one frame too wide at the hi of the first operation: the edge run then lands outside
    the true window, and expect refuses the case, EDGES_DIFFER."""
    folder = lrnc.cases(str(tmp_path / "cases"), M)
    real = W.rule

    def wide(*a, **kw):
        out = real(*a, **kw)
        lo, hi = out[0]
        return [(lo, hi + 1)] + out[1:]
    monkeypatch.setattr(W, "rule", wide)
    with pytest.raises(LrncRefusal) as e:
        lrnc.expect(folder, "flow")
    assert e.value.name == "EDGES_DIFFER" and "every operation at its hi" in e.value.detail

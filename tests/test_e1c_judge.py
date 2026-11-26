"""E1C: the card's parts made as stage E1 makes its own, and E1's own judge on them.

The gate `statistics`, held two ways:
  - at the stated scale, the card's last step: six parts with stage E1's committed counts (docs/studies/e1/c0.json
    to c5.json, which the card's parts must equal key for key), written as compare writes them and judged by E1's
    own `judge_parts`, reprint docs/studies/e1/judge-output.txt byte for byte, and return 0. The parts are read
    for their counts and coefficients and given the tree's own definition hash, as a card part carries it: so this
    holds whichever definition made E1's parts (the lead's ruling, 2026-11-25 20:56);
  - at the short form's size, the card's first step: `evaluate_card`, given the short form's own reads and the
    statistics' baseline records, is `evaluate`'s part key for key. The baseline's records are an argument of
    `evaluate_card`, as the card's matched-filter run gives them; `evaluate` makes them from the statistics' float
    filter. When the two are the same records, the parts must be the same.
The brief's named control: a count changed by one in the card's tally makes the judge's output differ from E1's
committed output, in the lines that print that count and no others; and `evaluate_card` reports a baseline read
changed by one, and a digest that is not the statistics'.
"""
import json

import numpy as np
import pytest

from spec import constants as C

import test_lrn_a_e1 as E1
from hw.e1c import e1c


def card_parts_from_committed():
    """The six committed parts as the card's would be: the same counts and keys, the tree's definition hash."""
    return [dict(part, spec_sha256=C.SPEC_SHA256) for _c, part in sorted(e1c.committed_parts().items())]


def committed():
    return e1c.read_bytes(e1c.E1_OUTPUT)


def test_gate_statistics__e1c_the_committed_counts_through_the_card_judge_reprint_e1s_output(tmp_path):
    printed, code = e1c.judge_output(card_parts_from_committed(), str(tmp_path))
    assert code == 0 and e1c.against_output(printed, committed()) is None
    assert printed.encode("utf-8") == committed()
    assert printed.rstrip("\n").split("\n")[-1] == "== E1 SOFTWARE VERDICT: PASS, the reported model is inside the " \
        "tolerance of E0's efficiency"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["c%d.json" % c for c in range(6)]


def _differing_lines(printed):
    mine, theirs = printed.rstrip("\n").split("\n"), committed().decode("utf-8").rstrip("\n").split("\n")
    assert len(mine) == len(theirs)
    return [(i, a) for i, (a, b) in enumerate(zip(mine, theirs)) if a != b]


def test_control_statistics__e1c_a_count_changed_by_one_in_the_cards_tally_changes_the_judges_output(tmp_path):
    """Each change keeps the part's counts adding up, as a card whose one read crossed would: one injection more
    found by the learned set alone; one more by the baseline alone; one signal-free position crossed by one model
    alone where it was crossed by both. And one count changed with nothing else, which no longer adds up."""
    def found(ps):
        ps[5]["found"] += 1
        ps[5]["learned_only"] += 1

    def base(ps):
        ps[2]["base_found"] += 1
        ps[2]["base_only"] += 1

    def crossing(ps):
        ps[3]["noise_both"] -= 1
        ps[3]["noise_base_only"] += 1
        ps[3]["noise_learned_only"] += 1

    def alone(ps):
        ps[4]["found"] += 1

    expected = {found: ("16384", "16384", "THE"), base: ("256", "256"), crossing: ("1024",), alone: None}
    for change, starts in expected.items():
        ps = card_parts_from_committed()
        change(ps)
        (tmp_path / change.__name__).mkdir()
        printed, code = e1c.judge_output(ps, str(tmp_path / change.__name__))
        diff = e1c.against_output(printed, committed())
        assert diff is not None, change.__name__
        print("CONTROL a count changed by one in the card's tally (%s): the judge's output differs from line %d: %r"
              % (change.__name__, diff["line"], diff["card"][:100]))
        if starts is None:
            assert code == 1 and "NOT AS STATED" in printed
            continue
        lines = _differing_lines(printed)
        assert [line.split()[0] for _i, line in lines] == list(starts[:len(lines)]) and len(lines) == len(starts), lines
        assert code == 0, "the counts add up, and every condition holds: only what is printed differs"


def _short_inputs():
    got, part = E1.short()
    p = got["plan"]
    f = E1.facts()
    held = got["held"]
    stat_l = [int(v) for v in E1.stat_scores_at_reads(held, part["coefficients"]).tolist()]
    stat_m = E1.stat_scores_at_reads(held, f["coeffs"])
    stats = {"learned_reads_sha256": e1c.P0.digest_scores(stat_l),
             "matched_reads_sha256": e1c.P0.digest_scores([int(v) for v in stat_m.tolist()]),
             "base_first_trials": [int(v) for v in stat_m[p["m_cal"]:p["m_cal"] + 2 * E1.CORE_CHECK].tolist()]}
    base_reads = E1.records_from(p, stat_m, E1.BLANK_EPOCH)
    extra = dict((k, part[k]) for k in ("handover_refusal", "first_new_epoch_index", "flags", "scores_not_zero_while_blank",
                                         "learner_counts", "injection_sha256", "stream_sha256"))
    return got, part, p, stats, base_reads, extra


def test_gate_statistics__e1c_evaluate_card_is_evaluate_on_the_short_forms_reads():
    got, part, p, stats, base_reads, extra = _short_inputs()
    mine = e1c.evaluate_card(p, got["reads"], base_reads, got["blob"], stats, extra)
    assert mine == part and sorted(mine) == sorted(part) and len(mine) == len(part)
    assert mine["k"] == 120 and mine["found"] == 1969 and mine["base_found"] == 1935
    assert json.loads(json.dumps(mine)) == part


def test_control_statistics__e1c_evaluate_card_reports_a_baseline_read_changed_and_a_digest_not_the_statistics():
    got, part, p, stats, base_reads, extra = _short_inputs()
    at = p["m_cal"] + 1                                    # the first test trial's at-index read, in the first 256
    base_threshold = part["base_threshold"]
    raised = [dict(r) for r in base_reads]
    was = raised[at]["score"]
    raised[at]["score"] = int(base_threshold) + 1 if was <= base_threshold else int(base_threshold) - 1
    mine = e1c.evaluate_card(p, got["reads"], raised, got["blob"], stats, extra)
    differ = e1c.differing(mine, part)
    print("CONTROL evaluate_card, one baseline read moved across its threshold: the part differs in %s" % differ)
    assert "base_found" in differ and "core_equals_baseline_on_first_trials" in differ
    assert abs(mine["base_found"] - part["base_found"]) == 1 and mine["core_equals_baseline_on_first_trials"] is False
    wrong = dict(stats, learned_reads_sha256="0" * 64)
    assert e1c.differing(e1c.evaluate_card(p, got["reads"], base_reads, got["blob"], wrong, extra), part) == \
        ["scores_identical_to_stats"]
    late = dict(stats, base_first_trials=stats["base_first_trials"][:-1] + [stats["base_first_trials"][-1] + 1])
    assert e1c.differing(e1c.evaluate_card(p, got["reads"], base_reads, got["blob"], late, extra), part) == \
        ["core_equals_baseline_on_first_trials"]


def _stated_compare(tmp_path, keys=None, change=None, judge=None):
    """compare's own path for the stated run, its card parts stood in by the committed ones (with the tree's hash)
    and its swaps and flip by passes: what it prints, and its code. The parts' making from bytes is held elsewhere."""
    folder, runs = tmp_path / "cases", tmp_path / "runs"
    folder.mkdir(parents=True)
    runs.mkdir(parents=True)
    e1c.write_json(str(folder / "cases.json"), {"keys": list(range(6)), "swap_part": 5, "stated": True,
                                                "spec_sha256": C.SPEC_SHA256})
    (folder / "order.txt").write_text("", encoding="utf-8")
    parts = dict((p["part"], p) for p in card_parts_from_committed())
    if change:
        change(parts)
    got = {"identical": True, "flags": 0, "learned_flags": 0, "matched_identical_to_stats": True, "read": True,
           "blank_prefix_equal": None, "blank_from": "the desktop's model run"}
    lines = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(e1c, "card_part", lambda folder_, key, *a, **kw: (parts[key], dict(got)))
        mp.setattr(e1c, "compare_swaps", lambda *a, **kw: True)
        mp.setattr(e1c, "compare_flip", lambda *a, **kw: True)
        if judge is not None:
            mp.setattr(e1c.E1, "judge_parts", judge)
        code, record = e1c.compare(str(folder), str(runs), keys=keys, out=lines.append)
    return code, record, lines


def test_e1c_compare_on_the_stated_run_judges_six_parts_and_fails_a_day_cut_short(tmp_path):
    code, record, lines = _stated_compare(tmp_path / "whole")
    assert code == 0 and lines[-1].startswith("== E1 CARD VERDICT: PASS") and record["judge"]["equal"]
    assert "  E1's own judge on the six card parts: its output EQUAL to docs/studies/e1/judge-output.txt, byte for byte" in lines
    assert sum("EQUAL to E1's committed part, key for key" in line for line in lines) == 6
    assert [p["part"] for p in record["parts"]] == [5, 4, 3, 2, 1, 0], "the reported part first"
    code, record, lines = _stated_compare(tmp_path / "five", keys=[5])
    assert code == 1 and lines[-1] == "== E1 CARD VERDICT: FAIL"
    assert "  E1's own judge: NOT RUN: it judges the six parts together, and 1 were made" in lines

    def found(parts):
        parts[5]["found"] += 1
        parts[5]["learned_only"] += 1
    code, record, lines = _stated_compare(tmp_path / "found", change=found)
    assert code == 1 and record["judge"]["first_difference"]["line"] == 9
    assert any("part 5: DIFFERS from E1's committed part in found, learned_only" in line for line in lines)
    assert any("DIFFERS from docs/studies/e1/judge-output.txt from line 9" in line for line in lines)
    # the judge's output held alone: every part E1's, and a judge that prints one line more
    real = E1.judge_parts

    def louder(paths):
        code_ = real(paths)
        print("  one line more")
        return code_
    code, record, lines = _stated_compare(tmp_path / "louder", judge=louder)
    assert code == 1 and sum("EQUAL to E1's committed part, key for key" in line for line in lines) == 6
    assert record["judge"]["equal"] is False and lines[-1] == "== E1 CARD VERDICT: FAIL"


def test_e1c_a_card_record_names_its_definition_and_is_stale_by_name_once_it_moves():
    assert e1c.stale({"spec_sha256": C.SPEC_SHA256}) is None
    assert e1c.stale({"spec_sha256": "0" * 64}) == "E1C-CARD-STALE"
    assert e1c.stale({}) == "E1C-CARD-STALE"

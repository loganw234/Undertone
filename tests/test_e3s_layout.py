"""Where stage E3's roles fell, held to vectors/e3s/blocks.json; and the experiment's carry seeds, held apart.

The frozen rule fills a station's roles from its kept blocks in time order (vectors/e3s/rule.json,
docs/studies/e3/e3prep.py), so the 544 blocks a station uses are its first five days', not the
eight days' spread the design meant (VE3S, its (b)2; docs/model/e3s.md, the table under "What the
fetch and the prep found" and limit 16). The rule is not changed after the fetch. This file holds
the doc's table of days and roles, cell by cell, and the roles' times, to what the prep wrote.

It also holds a gap the verifier found in the experiment (its (c)): that the matched filter's and the
learner's carry checks run on seeds of their own, by recomputing the short form's carries from the
named seeds and requiring the part's figures. It reads the experiment's short form through
tests/test_e3s_experiment.py and changes nothing of it.

What it cannot see: anything the prep did not write; and the full run's own carries, which only the
lead's run makes.
"""
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

RULE_PATH = os.path.join(ROOT, "vectors", "e3s", "rule.json")
BLOCKS_PATH = os.path.join(ROOT, "vectors", "e3s", "blocks.json")

# The doc's table, typed here from blocks.json as committed at cd39f79: for each day, each station's
# calibration, training, held-out, kept and not used, and lost blocks.
TABLE = {
    "2024-01-08": {"MPP": (16, 98, 0, 0, 17), "CDM": (16, 98, 0, 0, 17), "HDH": (16, 93, 0, 0, 22), "SRN": (16, 94, 0, 0, 21)},
    "2024-01-16": {"MPP": (0, 30, 101, 0, 0), "CDM": (0, 30, 101, 0, 0), "HDH": (0, 35, 95, 0, 1), "SRN": (0, 34, 94, 0, 3)},
    "2024-01-24": {"MPP": (0, 0, 128, 0, 3), "CDM": (0, 0, 128, 0, 3), "HDH": (0, 0, 126, 0, 5), "SRN": (0, 0, 121, 0, 10)},
    "2024-02-01": {"MPP": (0, 0, 131, 0, 0), "CDM": (0, 0, 131, 0, 0), "HDH": (0, 0, 128, 0, 3), "SRN": (0, 0, 131, 0, 0)},
    "2024-02-09": {"MPP": (0, 0, 40, 54, 37), "CDM": (0, 0, 40, 54, 37), "HDH": (0, 0, 51, 42, 38), "SRN": (0, 0, 54, 38, 39)},
    "2024-02-17": {"MPP": (0, 0, 0, 131, 0), "CDM": (0, 0, 0, 131, 0), "HDH": (0, 0, 0, 131, 0), "SRN": (0, 0, 0, 123, 8)},
    "2024-02-25": {"MPP": (0, 0, 0, 125, 6), "CDM": (0, 0, 0, 125, 6), "HDH": (0, 0, 0, 125, 6), "SRN": (0, 0, 0, 122, 9)},
    "2024-03-04": {"MPP": (0, 0, 0, 127, 4), "CDM": (0, 0, 0, 127, 4), "HDH": (0, 0, 0, 127, 4), "SRN": (0, 0, 0, 125, 6)},
}
# Each role's first and last block's start, as the doc states them in words.
TIMES = {
    "MPP": ("2024-01-08T02:43:50.400000Z", "2024-01-16T05:16:45.440000Z", "2024-01-16T05:27:40.800000Z", "2024-02-09T07:16:54.400000Z"),
    "CDM": ("2024-01-08T02:43:50.400000Z", "2024-01-16T05:16:45.440000Z", "2024-01-16T05:27:40.800000Z", "2024-02-09T07:16:54.400000Z"),
    "HDH": ("2024-01-08T03:05:41.120000Z", "2024-01-16T06:11:22.240000Z", "2024-01-16T06:22:17.600000Z", "2024-02-09T09:06:08.000000Z"),
    "SRN": ("2024-01-08T02:54:45.760000Z", "2024-01-16T06:00:26.880000Z", "2024-01-16T06:11:22.240000Z", "2024-02-09T09:38:54.080000Z"),
}
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Monday")


def load():
    with open(BLOCKS_PATH, encoding="utf-8") as f:
        blocks = json.load(f)
    with open(RULE_PATH, encoding="utf-8") as f:
        rule = json.load(f)
    return blocks, rule


def test_e3s_layout_the_roles_fall_on_the_first_five_days_as_the_doc_tabulates():
    from datetime import date
    blocks, rule = load()
    assert list(TABLE) == rule["days"]
    assert [date.fromisoformat(d).strftime("%A") for d in rule["days"]] == list(WEEKDAYS)
    for s in blocks["stations"]:
        sta = s["station"]
        used = Counter((r["day"], r["role"]) for r in s["blocks_used"])
        lost = Counter(d for d, _b, _why in s["lost"])
        for day in rule["days"]:
            c, t, h = used[(day, "calibration")], used[(day, "training")], used[(day, "held_out")]
            unused = rule["blocks_per_day"] - lost[day] - c - t - h
            assert (c, t, h, unused, lost[day]) == TABLE[day][sta], (sta, day)
        assert sum(TABLE[d][sta][4] for d in rule["days"]) == sum(s["losses"].values())
        assert sum(TABLE[d][sta][3] for d in rule["days"]) == s["kept"] - 544
        used_days = sorted({r["day"] for r in s["blocks_used"]})
        assert used_days == rule["days"][:5], "the roles use the first five days and no other"
        assert all(TABLE[d][sta][:3] == (0, 0, 0) for d in rule["days"][5:]), "02-17, 02-25 and 03-04 are not used"
        by = {role: [r["start_utc"] for r in s["blocks_used"] if r["role"] == role] for role in ("calibration", "training", "held_out")}
        assert (by["calibration"][-1], by["training"][-1], by["held_out"][0], by["held_out"][-1]) == TIMES[sta], sta
        assert by["calibration"][0] == "2024-01-08T00:00:00.000000Z"
        # the named model's 32 blocks are the last of training; MPP's and CDM's begin on 01-08, HDH's and SRN's on 01-16
        named = [r["day"] for r in s["blocks_used"] if r["role"] == "training"][-rule["named_model"]["training_blocks"]:]
        assert Counter(named) == ({"2024-01-08": 2, "2024-01-16": 30} if sta in ("MPP", "CDM") else {"2024-01-16": 32}), sta
    unused = sorted(s["kept"] - 544 for s in blocks["stations"])
    assert (unused[0], unused[-1]) == (408, 437)


def test_e3s_layout_the_matched_and_learned_carries_run_on_seeds_of_their_own():
    """The short form's part records four carries a model; each is the one its named seed gives
    (carry_seed, + 2 for the learner, + 4 for the halves), and the matched filter's seed is not the learner's."""
    import test_e3s_experiment as X
    from stats import empirical
    got, part = X.short()
    p = X.SHORT
    base, _scores = X.short_base()
    free, at = X.split(p, got["reads"])
    learned = X.judged_model(p, free, at, part["threshold"])
    for what, model, s in (("matched", base, 0), ("learned", learned, 2)):
        for split_, off in (("alternate", 0), ("halves", 4)):
            want = X.carried(empirical.carry_both_ways(model["free"], X.PFA, p["resamples"], p["carry_seed"] + s + off, split_, X.Z))
            assert part["carry"][what][split_] == want, (what, split_)
    same = X.carried(empirical.carry_both_ways(learned["free"], X.PFA, p["resamples"], p["carry_seed"] + 0, "alternate", X.Z))
    assert part["carry"]["learned"]["alternate"] != same, "the learner's carry is not on the matched filter's seed"

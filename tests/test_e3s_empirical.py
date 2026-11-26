"""Stage E3's judge, `stats/empirical.py`, held on scores made here, where the answer is known.

The judge's error is by resampling whole blocks; the density method is reported beside it. On
Gaussian scores in blocks, where `stats.tolerance` gives the error, each must give it within its
own stated error (the brief's fifth named control). On scores with a shared offset in each block,
which the independent formula cannot see, the resampling must see it and the density method must
not (a control the design added). Each refusal is reached by the case it names, under its name.

What these cannot see: real noise. That the resampling is right where blocks are exchangeable is
shown here; that real blocks are exchangeable is not (docs/model/e3s.md, its limits).
"""
import math
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from stats import empirical as E  # noqa: E402
from stats import theory, tolerance  # noqa: E402
from stats.errors import StatRefusal  # noqa: E402

PFA = 0.01
D = theory.q_inv(PFA)                     # D8 gives one half here
K, FREE, AT = 64, 192, 64                  # the short form's blocks: m 12,288, n 4,096
SEED = 2026112692


def gaussian_blocks(rng, blocks=K, free=FREE, at=AT, d=D, offset_sd=0.0):
    shift = rng.standard_normal((blocks, 1)) * offset_sd
    return rng.standard_normal((blocks, free)) + shift, rng.standard_normal((blocks, at)) + d + shift


def model(free, at, threshold=None):
    m = free.size
    k = E.crossings(m, PFA)
    t = np.partition(free.ravel(), m - k - 1)[m - k - 1] if threshold is None else threshold
    return {"free": free, "at": at, "threshold": float(t), "free_index": np.arange(free.size).reshape(free.shape)}


# ------------------------------------------------------------------ the refusals and the conventions

def test_e3s_empirical_its_refusals_are_its_own_names_and_the_packages():
    assert set(E.EMPIRICAL_NAMES) == {"BLOCKS_SHAPE", "TOO_FEW_BLOCKS", "UNEQUAL_FALSE_ALARM_RATE", "TRAINED_ON"}
    assert isinstance(E.EmpiricalRefusal("TRAINED_ON"), StatRefusal)
    assert E.EmpiricalRefusal("NOT_FINITE").name == "NOT_FINITE"
    with pytest.raises(ValueError):
        E.EmpiricalRefusal("SOMETHING_ELSE")
    rng = np.random.Generator(np.random.PCG64(SEED))
    free, at = gaussian_blocks(rng)
    cases = (("TOO_FEW_BLOCKS", lambda: E.resampled_efficiency(free[:19], at[:19], 0.1, 10, 1)),
             ("BLOCKS_SHAPE", lambda: E.resampled_efficiency(free.ravel(), at, PFA, 10, 1)),
             ("BLOCKS_SHAPE", lambda: E.resampled_efficiency(free, at[:-1], PFA, 10, 1)),
             ("NOT_FINITE", lambda: E.resampled_efficiency(np.where(free > 3, np.nan, free), at, PFA, 10, 1)),
             ("TOO_FEW_NOISE_SCORES", lambda: E.resampled_efficiency(free[:, :100], at, PFA, 10, 1)),
             ("COUNT_RANGE", lambda: E.resampled_efficiency(free, at, PFA, 1, 1)),
             ("BLOCKS_SHAPE", lambda: E.compare(model(free, at), model(free[:, :-1], at), PFA, 10, 1)),
             ("UNEQUAL_FALSE_ALARM_RATE", lambda: E.compare(model(free, at), dict(model(free, at), free_index=model(free, at)["free_index"] + 1), PFA, 10, 1)),
             ("UNEQUAL_FALSE_ALARM_RATE", lambda: E.compare(model(free, at), model(free, at, threshold=0.0), PFA, 10, 1)))
    for name, call in cases:
        with pytest.raises(E.EmpiricalRefusal) as e:
            call()
        assert e.value.name == name, (name, e.value)


def test_e3s_empirical_a_threshold_is_the_packages_and_a_crossing_is_strictly_greater():
    rng = np.random.Generator(np.random.PCG64(SEED + 1))
    free, at = gaussian_blocks(rng)
    r = E.resampled_efficiency(free, at, PFA, 20, 3)
    from stats.recovery import threshold_from_scores
    t = threshold_from_scores(free.ravel(), PFA)
    assert (r["m"], r["k"], r["threshold"]) == (12288, 122, t["threshold"])
    assert r["efficiency"] == float((at > t["threshold"]).mean())
    # a score equal to the threshold is not a hit
    tied = at.copy()
    tied[0, 0] = t["threshold"]
    assert E.resampled_efficiency(free, tied, PFA, 20, 3)["efficiency"] == float((tied > t["threshold"]).mean())
    assert not (tied[0, 0] > t["threshold"])


def test_e3s_empirical_the_resampling_is_seeded_and_the_same_seed_gives_the_same_figure():
    rng = np.random.Generator(np.random.PCG64(SEED + 2))
    free, at = gaussian_blocks(rng)
    a, b = model(free, at), model(free + 0.01, at)
    one, two = E.compare(a, b, PFA, 100, 7), E.compare(a, b, PFA, 100, 7)
    assert one["se"] == two["se"] and one["cost"] == two["cost"]
    assert E.compare(a, b, PFA, 100, 8)["se"] != one["se"]


# ------------------------------------------------------------------ the reading

def test_gate_statistics__e3s_the_judge_reads_equal_detectors_as_reaching():
    rng = np.random.Generator(np.random.PCG64(SEED + 3))
    free, at = gaussian_blocks(rng)
    same = E.compare(model(free, at), model(free, at), PFA, 200, 1)
    assert same["cost"] == 0.0 and same["se"] == 0.0 and same["reading"] == "REACHES"
    # two detectors that differ only by noise of their own: a cost near zero, and REACHES
    jitter = rng.standard_normal(free.shape) * 0.05, rng.standard_normal(at.shape) * 0.05
    near = E.compare(model(free, at), model(free + jitter[0], at + jitter[1]), PFA, 500, 2)
    print("E3S judge: two detectors differing by noise of 0.05: cost %+.5f, se %.5f, %s" % (near["cost"], near["se"], near["reading"]))
    assert near["reading"] == "REACHES" and near["se"] > 0
    assert near["se"] < 0.5 * min(near["se_reference"], near["se_other"]), \
        "the cost's error is the pair's, far below either efficiency's when the two mostly agree"


def test_control_statistics__e3s_the_judge_reads_a_detector_with_less_deflection_as_short_and_the_reverse_as_ahead():
    """A detector whose injections sit 0.3 sigma lower finds about 0.12 fewer at Pd one half (D8 at d - 0.3)."""
    rng = np.random.Generator(np.random.PCG64(SEED + 4))
    free, at = gaussian_blocks(rng)
    other_free, other_at = free + rng.standard_normal(free.shape) * 0.1, at - 0.3 + rng.standard_normal(at.shape) * 0.1
    want = 0.5 - theory.pd_matched(PFA, D - 0.3)
    short = E.compare(model(free, at), model(other_free, other_at), PFA, 500, 3)
    print("CONTROL e3s judge: %.4f fewer predicted, cost %+.5f, se %.5f, %s" % (want, short["cost"], short["se"], short["reading"]))
    assert short["reading"] == "SHORT" and short["cost"] > 0.05
    ahead = E.compare(model(other_free, other_at), model(free, at), PFA, 500, 3)
    assert ahead["reading"] == "AHEAD" and ahead["cost"] == -short["cost"]


# ------------------------------------------------------------------ the brief's fifth control: the method where the term is known

def test_control_statistics__e3s_the_resampling_gives_the_known_error_on_gaussian_scores_within_its_stated_error():
    """On Gaussian scores in blocks, stats.tolerance's se_total is the error of a correct detector's
    efficiency at a measured threshold. Over 100 repetitions at the short form's size, each with
    100 resamples: the resampled error's mean is within 10% of se_total (measured at the design:
    0.990 and 0.992 of it, over 100 and 400 repetitions); its threshold part, the resampled
    variance less the variance with the threshold held, within 15% of se_threshold (0.987, 0.989);
    the part with the threshold held within 10% of the binomial (0.98). One repetition's figure
    spreads by about 15% (its stated error: docs/model/e3s.md)."""
    rng = np.random.Generator(np.random.PCG64(SEED + 5))
    m, n = K * FREE, K * AT
    k = E.crossings(m, PFA)
    want = tolerance.tolerance((k + 1) / (m + 1), D, n, m)
    tot, fix, effs, slopes, slope_ses = [], [], [], [], []
    for r in range(100):
        free, at = gaussian_blocks(rng)
        a = E.resampled_efficiency(free, at, PFA, 100, 1000 + r)
        b = E.resampled_efficiency(free, at, PFA, 100, 1000 + r, fixed_threshold=True)
        tot.append(a["se"])
        fix.append(b["se"])
        effs.append(a["efficiency"])
        s = E.slope_by_ranks(free, at, PFA)
        slopes.append(s["slope"])
        slope_ses.append(s["se"])
    # the density method's own stated error, against its spread over the repetitions (2.13 and 1.90 over 400 at the design)
    density = np.mean(slope_ses) / np.std(slopes, ddof=1)
    print("CONTROL e3s density's error: stated %.3f, spread %.3f (%.3f)" % (np.mean(slope_ses), np.std(slopes, ddof=1), density))
    assert 0.8 < density < 1.5
    tot, fix = np.array(tot), np.array(fix)
    thr = np.sqrt(np.maximum(tot ** 2 - fix ** 2, 0.0))
    ratios = (tot.mean() / want["se_total"], thr.mean() / want["se_threshold"], fix.mean() / want["se_binomial"])
    cv = tot.std(ddof=1) / tot.mean()
    z = (np.array(effs) - want["expected"]) / tot
    print("CONTROL e3s method: resampled se %.5f against %.5f (%.3f); threshold part %.5f against %.5f (%.3f); held %.5f "
          "against %.5f (%.3f); cv %.3f; |z| > 1 in %d of 100" % (tot.mean(), want["se_total"], ratios[0], thr.mean(),
                                                                want["se_threshold"], ratios[1], fix.mean(), want["se_binomial"],
                                                                ratios[2], cv, int((np.abs(z) > 1).sum())))
    assert abs(ratios[0] - 1) <= 0.10 and abs(ratios[1] - 1) <= 0.15 and abs(ratios[2] - 1) <= 0.10
    assert 0.08 < cv < 0.25 and 15 <= int((np.abs(z) > 1).sum()) <= 50


def test_control_statistics__e3s_the_density_method_gives_d8s_slope_on_gaussian_scores_within_its_stated_error():
    rng = np.random.Generator(np.random.PCG64(SEED + 6))
    free, at = gaussian_blocks(rng, blocks=400, free=768, at=256)             # the full run's size
    s = E.slope_by_ranks(free, at, PFA)
    m = free.size
    k = E.crossings(m, PFA)
    want = tolerance.roc_slope((k + 1) / (m + 1), D)
    print("CONTROL e3s density: slope %.3f, se %.3f, count %d, band %d; D8's %.3f: %+.2f se"
          % (s["slope"], s["se"], s["count"], s["width"], want, (s["slope"] - want) / s["se"]))
    assert abs(s["slope"] - want) <= 4 * s["se"] and s["width"] == k // 4 == 768
    first = tolerance.tolerance((k + 1) / (m + 1), D, 102400, m)["se_threshold"]
    assert abs(s["se_threshold"] / first - 1) <= 4 * s["se"] / s["slope"]
    # and it does see a law that is not D8's: injections spread twice as wide flatten the slope
    wide = E.slope_by_ranks(free, (at - D) * 2 + D, PFA)
    assert wide["slope"] < want - 4 * wide["se"]


def test_control_statistics__e3s_a_dependence_the_formula_cannot_see_the_resampling_sees():
    """Scores with a random offset in each block, shared by its signal-free scores and its injections.
    The independent formula and the density method know nothing of it; the resampling must, and must
    agree with the spread over repetitions, which is the truth."""
    rng = np.random.Generator(np.random.PCG64(SEED + 7))
    m, n = K * FREE, K * AT
    k = E.crossings(m, PFA)
    formula = tolerance.tolerance((k + 1) / (m + 1), D, n, m)["se_total"]
    tot, effs, dens = [], [], []
    for r in range(60):
        free, at = gaussian_blocks(rng, offset_sd=1.0)
        a = E.resampled_efficiency(free, at, PFA, 100, 2000 + r)
        tot.append(a["se"])
        effs.append(a["efficiency"])
        s = E.slope_by_ranks(free, at, PFA)
        dens.append(math.sqrt(0.25 / n + s["se_threshold"] ** 2))
    truth = float(np.std(effs, ddof=1))
    print("CONTROL e3s dependence: the spread over 60 repetitions %.5f; resampled %.5f; independent formula %.5f; density %.5f"
          % (truth, np.mean(tot), formula, np.mean(dens)))
    assert np.mean(tot) > 1.5 * formula and np.mean(tot) > 1.5 * np.mean(dens)
    assert abs(np.mean(tot) / truth - 1) < 0.3


# ------------------------------------------------------------------ the carry, and the disjoint check

def test_e3s_empirical_a_threshold_carries_to_blocks_of_the_same_noise_and_not_to_louder_ones():
    rng = np.random.Generator(np.random.PCG64(SEED + 8))
    one = rng.standard_normal((32, 384))
    same, louder = rng.standard_normal((32, 384)), rng.standard_normal((32, 384)) * 1.25
    a = E.carry(one, same, PFA, 300, 1)
    b = E.carry(one, louder, PFA, 300, 2)
    want = theory.q(theory.q_inv(PFA) / 1.25)
    print("E3S carry: same %.5f of %.5f (%+.2f se); louder %.5f (%.4f predicted), %+.2f se" % (
        a["rate"], a["stated"], a["z_score"], b["rate"], want, b["z_score"]))
    assert a["carries"] and not b["carries"] and abs(b["rate"] - want) < 0.006
    both = E.carry_both_ways(np.vstack([one, louder]), PFA, 300, 3, "halves")
    assert not both["carries"] and not both["there"]["carries"] and not both["back"]["carries"]
    alt = E.carry_both_ways(np.vstack([one, same]), PFA, 300, 4, "alternate")
    assert alt["carries"] and alt["there"]["m_from"] == alt["back"]["m_to"] == 32 * 384
    with pytest.raises(E.EmpiricalRefusal):
        E.carry_both_ways(one, PFA, 10, 1, "diagonal")


def test_e3s_empirical_the_disjoint_check_refuses_only_what_meets():
    tr = [(0, 10, "a"), (10, 20, "b")]
    assert E.check_disjoint(tr, [(20, 30, "c"), (40, 50, "d")]) == 4
    for held in ([(19, 29, "c")], [(5, 6, "c")], [(-5, 1, "c")], [(30, 40, "b")]):
        with pytest.raises(E.EmpiricalRefusal) as e:
            E.check_disjoint(tr, held)
        assert e.value.name == "TRAINED_ON"


def test_e3s_empirical_a_resample_of_every_block_once_gives_the_packages_threshold():
    from stats.recovery import threshold_from_scores
    rng = np.random.Generator(np.random.PCG64(SEED + 9))
    for m, pfa in ((12288, 0.01), (307200, 0.01), (2000, 0.1)):
        f = rng.standard_normal(m)
        k = E.crossings(m, pfa)
        t = E._threshold_of_rows(f[None, :], k)[0]
        assert t == threshold_from_scores(f, pfa)["threshold"] and int((f > t).sum()) == k, (m, pfa)


def test_control_statistics__e3s_the_carry_states_its_rate_and_its_error_rightly_where_nothing_changes():
    """From 32 blocks to 32 of the same Gaussian noise, 100 times: the stated rate is (k + 1) / (m + 1)
    exactly; the measured rate's resampled error is within 20% on average of the two-sample binomial
    sqrt(pe (1 - pe) (1 / m_from + 1 / m_to)); and |z| > 2 in at most 12 of the 100 (5 expected). An
    error that resampled one set only would be about 0.71 of the binomial, and fail."""
    rng = np.random.Generator(np.random.PCG64(SEED + 10))
    ses, zs = [], []
    for r in range(100):
        one, two = rng.standard_normal((32, 384)), rng.standard_normal((32, 384))
        c = E.carry(one, two, PFA, 100, 3000 + r)
        assert c["stated"] == (c["k"] + 1) / (c["m_from"] + 1) and c["k"] == 122
        ses.append(c["se"])
        zs.append(c["z_score"])
    pe = (122 + 1) / (12288 + 1)
    want = math.sqrt(pe * (1 - pe) * (2.0 / 12288))
    zs = np.array(zs)
    print("CONTROL e3s carry's error: mean %.5f against %.5f (%.3f); |z| > 2 in %d of 100"
          % (np.mean(ses), want, np.mean(ses) / want, int((np.abs(zs) > 2).sum())))
    assert abs(np.mean(ses) / want - 1) < 0.2 and int((np.abs(zs) > 2).sum()) <= 12

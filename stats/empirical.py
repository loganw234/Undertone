"""Statistics where D8 cannot predict: errors measured from the scores themselves. Stage E3's judge.

On real noise two assumptions behind `stats.tolerance`'s threshold term fail: that the scores
are Gaussian (its slope, `roc_slope`, is D8's) and that the m signal-free scores are independent
(its pfa (1 - pfa) / m). Real noise moves from one stretch to the next, and its scores 64 frames
apart are not independent. So the comparison here takes its error from the scores, by
RESAMPLING WHOLE BLOCKS: a block is a stretch of the stream holding a fixed number of
signal-free scores and of scores at injections, and a resample draws as many blocks as there are,
with replacement, measures each model's threshold again from the resampled signal-free scores, and
counts each model's hits again on the resampled injections. The spread over the resamples is the
error, binomial, threshold, dependence inside a block and the spread between blocks together. It
assumes nothing about the scores' law. It assumes the blocks are exchangeable: dependence that
runs from one block into the next, or a condition many blocks share, it does not see.

Beside it, for comparison and not for a verdict, the DENSITY METHOD: the ROC's slope read from the
ranks of the scores near the threshold, put into the first-order term slope^2 pfa (1 - pfa) / m.
It mends the Gaussian assumption and not the independent one.

WHAT THIS ADDS TO `stats.recovery.paired_cost`, which takes two hit arrays at two GIVEN thresholds
and treats the injections as independent:
  1. the two thresholds' errors, each threshold measured again in every resample;
  2. dependence between scores inside a block, and the spread between blocks;
  3. each threshold's false-alarm rate measured on held-out signal-free scores of other blocks
     (`carry`);
  4. a reading at an equal measured false-alarm rate: REACHES, SHORT or AHEAD at z of its own
     standard errors.

THE CONVENTIONS are the package's: a crossing is strictly greater than the threshold; a
threshold from m signal-free scores is the (k + 1)-th largest, k = floor(pfa * m) of the float's
exact value (`stats.recovery.threshold_from_scores`); the stated rate is (k + 1) / (m + 1).

Refusals are `EmpiricalRefusal`, a `stats.errors.StatRefusal` with four names of this module's
beside the package's own: BLOCKS_SHAPE, TOO_FEW_BLOCKS, UNEQUAL_FALSE_ALARM_RATE, TRAINED_ON.

Nothing here imports from `model/` or `learn/`.
"""
import math
from fractions import Fraction

import numpy as np

from stats.errors import NAMES as _PACKAGE_NAMES
from stats.errors import StatRefusal
from stats.recovery import MIN_CROSSINGS, paired_cost, threshold_from_scores
from stats.theory import _probability
from stats.tolerance import Z_GATE

EMPIRICAL_NAMES = (
    "BLOCKS_SHAPE",              # blocks of unequal counts, or two models on different blocks
    "TOO_FEW_BLOCKS",            # fewer blocks than MIN_BLOCKS to resample
    "UNEQUAL_FALSE_ALARM_RATE",  # a declared threshold that does not give its model k of its own m, or two models at other positions
    "TRAINED_ON",                # a held-out block that meets a training block, in time or in content
)
NAMES = tuple(_PACKAGE_NAMES) + EMPIRICAL_NAMES
MIN_BLOCKS = 20
READINGS = ("REACHES", "SHORT", "AHEAD")


class EmpiricalRefusal(StatRefusal):
    """A named refusal of this module's. `name` is one of `NAMES`."""

    def __init__(self, name, detail=""):
        if name not in NAMES:
            raise ValueError("not a declared refusal name: %r" % (name,))
        self.name = name
        self.detail = detail
        ValueError.__init__(self, "%s: %s" % (name, detail) if detail else name)


def score_blocks(scores, what):
    """A (blocks, per block) float64 array of finite scores, or a refusal."""
    a = np.asarray(scores)
    if a.ndim != 2 or a.dtype.kind not in "iuf" or a.shape[1] < 1:
        raise EmpiricalRefusal("BLOCKS_SHAPE", "%s must be a (blocks, scores) array of numbers, not %r" % (what, a.shape))
    if a.dtype.kind in "iu" and a.size and max(abs(int(a.min())), abs(int(a.max()))) > 2 ** 53:
        raise EmpiricalRefusal("INEXACT_INPUT", "%s holds an integer beyond 2^53" % what)
    a = a.astype(np.float64)
    if not np.isfinite(a).all():
        raise EmpiricalRefusal("NOT_FINITE", "%s holds a NaN or an infinity" % what)
    if a.shape[0] < MIN_BLOCKS:
        raise EmpiricalRefusal("TOO_FEW_BLOCKS", "%s has %d blocks; resampling needs %d" % (what, a.shape[0], MIN_BLOCKS))
    return a


def crossings(m, pfa):
    """k = floor(pfa * m), on the float's exact value, as threshold_from_scores takes it; refused below MIN_CROSSINGS."""
    k = int(Fraction(_probability(pfa, "pfa")) * m)
    if k < MIN_CROSSINGS:
        raise EmpiricalRefusal("TOO_FEW_NOISE_SCORES", "%d scores at pfa %r give %d crossing(s); %d are needed"
                               % (m, pfa, k, MIN_CROSSINGS))
    return k


def _threshold_of_rows(free_rows, k):
    """The (k + 1)-th largest of each row: one threshold for each resample."""
    m = free_rows.shape[1]
    return np.partition(free_rows, m - k - 1, axis=1)[:, m - k - 1]


def _resample_index(blocks, resamples, seed):
    if type(resamples) is not int or resamples < 2:
        raise EmpiricalRefusal("COUNT_RANGE", "resamples is %r, not an int of at least 2" % (resamples,))
    if type(seed) is not int or seed < 0:
        raise EmpiricalRefusal("VALUE_TYPE", "seed is %r, not a non-negative int" % (seed,))
    return np.random.Generator(np.random.PCG64(seed)).integers(0, blocks, size=(resamples, blocks))


def _efficiencies(free, at, k, idx, fixed=None):
    """One efficiency for each resample: each threshold measured again, or held at `fixed`."""
    out = np.empty(idx.shape[0])
    for r in range(idx.shape[0]):
        f = free[idx[r]].ravel()
        t = fixed if fixed is not None else _threshold_of_rows(f[None, :], k)[0]
        out[r] = float((at[idx[r]] > t).mean())
    return out


def resampled_efficiency(free, at, pfa, resamples, seed, fixed_threshold=False):
    """One model's efficiency at its own measured threshold, and its error by resampling whole blocks.

    `free` and `at` are (blocks, per block) arrays of the model's signal-free scores and its scores
    at the injections. With `fixed_threshold` the threshold is held at the whole sample's in every
    resample, so the spread is the injections' alone: the difference of the two variances is the
    threshold's part. Returns a dict: m, k, n, threshold, efficiency, se, efficiencies."""
    free, at = score_blocks(free, "free"), score_blocks(at, "at")
    if free.shape[0] != at.shape[0]:
        raise EmpiricalRefusal("BLOCKS_SHAPE", "%d blocks of signal-free scores and %d of injections" % (free.shape[0], at.shape[0]))
    m = free.size
    k = crossings(m, pfa)
    thr = threshold_from_scores(free.ravel(), pfa)["threshold"]
    idx = _resample_index(free.shape[0], resamples, seed)
    effs = _efficiencies(free, at, k, idx, thr if fixed_threshold else None)
    return {"m": m, "k": k, "n": at.size, "threshold": thr, "efficiency": float((at > thr).mean()),
            "se": float(np.std(effs, ddof=1)), "efficiencies": effs}


def _declared(model, k, what):
    """The model's declared threshold, recounted on its own signal-free scores: k of them above, or a refusal."""
    t = model["threshold"]
    above = int((model["free"] > t).sum())
    if above != k:
        raise EmpiricalRefusal("UNEQUAL_FALSE_ALARM_RATE", "%s: %d of its %d signal-free scores are above the threshold it "
                               "is counted at; an equal rate is %d" % (what, above, model["free"].size, k))
    return t


def compare(reference, other, pfa, resamples, seed, z=Z_GATE):
    """What `other` loses against `reference` on the same injections, each at its own threshold.

    Each model is a dict: "free" and "at", (blocks, per block) arrays of its scores on THE SAME
    blocks and positions; "free_index", the stream index of each signal-free score, which must be
    the two models' same; and "threshold", the threshold it is counted at, which must give it
    exactly k = floor(pfa * m) of its own m signal-free scores. The cost is reference's efficiency
    less other's. Its standard error is by resampling whole blocks, both thresholds measured again
    in every resample. The reading at z standard errors: REACHES (|cost| <= z se), SHORT
    (cost > z se: other finds fewer) or AHEAD (cost < -z se)."""
    models = []
    for what, md in (("reference", reference), ("other", other)):
        models.append({"free": score_blocks(md["free"], what + " free"), "at": score_blocks(md["at"], what + " at"),
                       "threshold": float(md["threshold"]), "free_index": np.asarray(md["free_index"])})
    a, b = models
    if a["free"].shape != b["free"].shape or a["at"].shape != b["at"].shape or a["free"].shape[0] != a["at"].shape[0]:
        raise EmpiricalRefusal("BLOCKS_SHAPE", "the two models are not on the same blocks: %r %r and %r %r"
                               % (a["free"].shape, a["at"].shape, b["free"].shape, b["at"].shape))
    if a["free_index"].shape != a["free"].shape or not np.array_equal(a["free_index"], b["free_index"]):
        raise EmpiricalRefusal("UNEQUAL_FALSE_ALARM_RATE", "the two models' signal-free scores are not at the same positions")
    m = a["free"].size
    k = crossings(m, pfa)
    ta, tb = _declared(a, k, "reference"), _declared(b, k, "other")
    hits_a, hits_b = (a["at"] > ta).ravel(), (b["at"] > tb).ravel()
    pair = paired_cost(hits_a, hits_b)
    idx = _resample_index(a["free"].shape[0], resamples, seed)
    ea, eb = _efficiencies(a["free"], a["at"], k, idx), _efficiencies(b["free"], b["at"], k, idx)
    costs = ea - eb
    se = float(np.std(costs, ddof=1))
    cost = pair["cost"]
    if abs(cost) <= z * se:
        reading = "REACHES"
    else:
        reading = "SHORT" if cost > 0 else "AHEAD"
    both = int(((a["free"] > ta) & (b["free"] > tb)).sum())
    return {"m": m, "k": k, "n": pair["n"], "blocks": a["free"].shape[0], "resamples": resamples, "seed": seed,
            "reference_efficiency": pair["found_a"] / pair["n"], "other_efficiency": pair["found_b"] / pair["n"],
            "reference_found": pair["found_a"], "other_found": pair["found_b"],
            "reference_only": pair["a_only"], "other_only": pair["b_only"], "noise_both": both,
            "cost": cost, "se": se, "se_pairs": pair["se"], "z_score": cost / se if se > 0 else 0.0,
            "z": z, "tolerance": z * se, "catch_margin": 2 * z * se, "reading": reading,
            "se_reference": float(np.std(ea, ddof=1)), "se_other": float(np.std(eb, ddof=1)),
            "reference_threshold": ta, "other_threshold": tb}


def slope_by_ranks(free, at, pfa, width=None):
    """The density method: the ROC's slope at the threshold, read from the scores' ranks.

    With t(j) the (j + 1)-th largest signal-free score, so that j are above it, and w = k // 4
    unless given: the slope is (c / n) / (2 w / (m + 1)), c the injections' scores in
    (t(k + w), t(k - w)]. Its relative variance is (1 - c / n) / c from the count and 1 / (2 w)
    from the band's own width as a probability. The first-order threshold term made from it is
    slope^2 pe (1 - pe) / m, pe = (k + 1) / (m + 1), as stats.tolerance's with D8's slope replaced."""
    f = np.asarray(free, dtype=np.float64).ravel()
    s = np.asarray(at, dtype=np.float64).ravel()
    m, n = f.size, s.size
    k = crossings(m, pfa)
    w = k // 4 if width is None else width
    if type(w) is not int or not 1 <= w < k:
        raise EmpiricalRefusal("COUNT_RANGE", "width %r, not an int from 1 to %d" % (w, k - 1))
    order = np.sort(f)[::-1]
    high, low = order[k - w], order[k + w]
    c = int(((s > low) & (s <= high)).sum())
    if c == 0:
        raise EmpiricalRefusal("COUNT_RANGE", "no injection's score between the two thresholds")
    slope = (c / n) / (2.0 * w / (m + 1))
    rel = math.sqrt((1.0 - c / n) / c + 1.0 / (2 * w))
    pe = (k + 1) / (m + 1)
    term = slope * slope * pe * (1.0 - pe) / m
    return {"slope": slope, "se": slope * rel, "count": c, "width": w, "m": m, "n": n, "k": k,
            "se_threshold": math.sqrt(term)}


def carry(free_from, free_to, pfa, resamples, seed, z=Z_GATE):
    """Does a threshold measured on one set of blocks give its stated rate on another?

    The threshold is the (k + 1)-th largest of `free_from`'s scores; its stated rate (k + 1) / (m + 1);
    its measured rate the fraction of `free_to`'s scores above it. The error is by resampling both
    sets' blocks, each set on its own, the threshold measured again each time. CARRIES when the
    measured rate is within z standard errors of the stated; DOES NOT CARRY otherwise."""
    a, b = score_blocks(free_from, "free_from"), score_blocks(free_to, "free_to")
    m = a.size
    k = crossings(m, pfa)
    stated = (k + 1) / (m + 1)
    thr = _threshold_of_rows(a.ravel()[None, :], k)[0]
    rate = float((b > thr).mean())
    rng = np.random.Generator(np.random.PCG64(seed))
    rates = np.empty(resamples)
    for r in range(resamples):
        fa = a[rng.integers(0, a.shape[0], size=a.shape[0])].ravel()
        fb = b[rng.integers(0, b.shape[0], size=b.shape[0])]
        rates[r] = float((fb > _threshold_of_rows(fa[None, :], k)[0]).mean())
    se = float(np.std(rates, ddof=1))
    zs = (rate - stated) / se if se > 0 else (0.0 if rate == stated else math.inf)
    return {"m_from": m, "k": k, "m_to": b.size, "threshold": float(thr), "stated": stated, "rate": rate,
            "se": se, "z_score": zs, "carries": abs(zs) <= z}


def carry_both_ways(free, pfa, resamples, seed, split="alternate", z=Z_GATE):
    """`carry` from one half of a model's held-out blocks to the other, and back.

    split "alternate": even-numbered blocks and odd-numbered; "halves": the first half in time and
    the second. Returns the two results and whether both carry."""
    f = score_blocks(free, "free")
    if split == "alternate":
        one, two = f[0::2], f[1::2]
    elif split == "halves":
        one, two = f[:f.shape[0] // 2], f[f.shape[0] // 2:]
    else:
        raise EmpiricalRefusal("VALUE_TYPE", "split is %r" % (split,))
    there = carry(one, two, pfa, resamples, seed, z)
    back = carry(two, one, pfa, resamples, seed + 1, z)
    return {"split": split, "there": there, "back": back, "carries": there["carries"] and back["carries"]}


def check_disjoint(training, held_out):
    """Refuse, TRAINED_ON, a held-out block that meets a training block in time or in content.

    Each argument is a list of (start, end, digest) for its blocks: a half-open span [start, end)
    in any one unit, and the SHA-256 of the block's samples. Returns the number of blocks checked."""
    spans = sorted((int(s), int(e)) for s, e, _d in training)
    digests = {d for _s, _e, d in training}
    for s, e, d in held_out:
        if d in digests:
            raise EmpiricalRefusal("TRAINED_ON", "a held-out block's samples are a training block's (%s)" % d)
        for ts, te in spans:
            if int(s) < te and ts < int(e):
                raise EmpiricalRefusal("TRAINED_ON", "the held-out block [%d, %d) meets the training block [%d, %d)"
                                       % (int(s), int(e), ts, te))
    return len(training) + len(held_out)

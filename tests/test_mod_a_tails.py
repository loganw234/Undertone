"""MOD-A's noise-tails gate: how deep the generator's tail follows the Gaussian, and the tests of it.

Three depths, three kinds of test (docs/model/mod-a.md has the argument):

  the table     every entry of the table against the law, recomputed in 50-digit decimal by
                tests/test_mod_a_reference.py. Reaches the table's last entry, about 9.155 sigma.
  the stream    the real iteration, fed the words that sit on each side of every table boundary,
                must yield every magnitude the table holds. Also to the last entry.
  the sample    counts of real draws at and beyond 1, 2, 3, 3.5 and 4 sigma, on each side and in
                each channel, against the law. 2^20 draws reach 4.0 sigma a side. Deeper needs
                more draws than the gate has seconds for: that is the long run, below.

A count must lie within Z = 4 standard deviations, sqrt(n p (1 - p)), of n p; a threshold with
n p (1 - p) below 25 is refused, not tested (the round's rule, the lead's DECISION of 2026-11-23).

THE LONG RUN is the lead's to make, not the gate's:

    python tests/test_mod_a_tails.py --long --draws 1073741824

about 20 minutes on one core for 2^30 draws, to 5.42 sigma a side. It can be made in parts,
because any frame is worked directly from the seed:

    python tests/test_mod_a_tails.py --long --total 1073741824 --start 0         --draws 536870912 --out a.json
    python tests/test_mod_a_tails.py --long --total 1073741824 --start 536870912 --draws 536870912 --out b.json
    python tests/test_mod_a_tails.py --judge a.json b.json

Each part prints, and --judge prints for the sum: every count with its expectation, a verdict
for the generator, and a verdict for the same draws clipped one below the deepest threshold,
which must FAIL.
"""
import json
import math
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.dirname(os.path.abspath(__file__))):   # run as a script: neither is on the path yet
    if _p not in sys.path:
        sys.path.insert(0, _p)

from spec import constants as C  # noqa: E402
from model import source  # noqa: E402

import test_mod_a_reference as ref  # noqa: E402

Z = 4.0                # a count may be this many standard deviations from its expectation
LEAST_VARIANCE = 25.0  # below this n p (1 - p) a threshold is refused
GATE_DRAWS = 1 << 20
SHALLOW = (1.0, 2.0, 3.0, 3.5)
GATE_DEPTH = 4.0       # sigma, a side: 33.2 draws expected beyond it in 2^20
PROFILES = sorted(C.PROFILES)


def threshold(z, sigma_num, sigma_den):
    """The smallest integer k with k >= z * sigma. z is a multiple of 1/2."""
    return -((-int(2 * z) * sigma_num) // (2 * sigma_den))


def count_sides(samples, k):
    """(how many samples are >= k, how many are <= -k), for a 1-D integer array."""
    return int(np.count_nonzero(samples >= k)), int(np.count_nonzero(samples <= -k))


def judge(counts, draws, sigma_num, sigma_den):
    """Findings for a table of counts {k: (upper, lower)} from `draws` samples of one channel.

    An empty list is a pass. A threshold the run is too short for is a finding too.
    """
    if draws == 0 or not counts:
        return ["NOTHING-COUNTED"]
    findings = []
    for k in sorted(counts):
        p = ref.ref_tail(sigma_num, sigma_den, k)
        variance = draws * p * (1 - p)
        if variance < LEAST_VARIANCE:
            findings.append("REFUSED k=%d: n p (1 - p) = %.2f is below %.0f" % (k, variance, LEAST_VARIANCE))
            continue
        for side, got in zip(("upper", "lower"), counts[k]):
            if abs(got - draws * p) > Z * math.sqrt(variance):
                findings.append("k=%d %s: %d counted, %.1f expected, %.1f standard deviations away"
                                % (k, side, got, draws * p, (got - draws * p) / math.sqrt(variance)))
    return findings


def sampled_findings(samples, sigma_num, sigma_den, zs=SHALLOW + (GATE_DEPTH,)):
    """The sampled test, on one channel's draws."""
    counts = {threshold(z, sigma_num, sigma_den): None for z in zs}
    for k in counts:
        counts[k] = count_sides(samples, k)
    return judge(counts, len(samples), sigma_num, sigma_den)


def table_findings(table, sigma_num, sigma_den):
    """Every entry against the law in decimal. An empty list is a pass."""
    ideal = ref.ref_ideal(sigma_num, sigma_den)
    want = ref.ref_table(sigma_num, sigma_den)
    findings = []
    if len(table) != len(want):
        findings.append("the table has %d entries; the law's has %d" % (len(table), len(want)))
    if not table or table[-1] != 1 << 63 or list(table).count(1 << 63) != 1:
        findings.append("the table does not end at its first 2^63")
    if any(b < a for a, b in zip(table, table[1:])):
        findings.append("the table falls somewhere")
    half = ref.decimal.Decimal("0.5000000001")
    worst = max((abs(ref.decimal.Decimal(h) - i), m) for m, (h, i) in enumerate(zip(table, ideal)))
    if worst[0] > half:
        findings.append("entry %d is %.3f units of 2^-63 from the law" % (worst[1], worst[0]))
    return findings


def float_tail_findings(table, sigma_num, sigma_den):
    """For a table too long for decimal in the gate's seconds: every entry's two-sided tail,
    (2^63 - H[m]) / 2^63, against the law summed in floats. It holds each tail to one part in 10^9
    plus 2^-64, which is the full claim only where the tail is below about 10^-10."""
    two_s2 = 2.0 * sigma_num * sigma_num / (sigma_den * sigma_den)
    m = np.arange(0, int(16 * sigma_num / sigma_den) + 2, dtype=np.float64)
    w = np.exp(-(m * m) / two_s2)
    total = w[0] + 2.0 * w[1:].sum()
    beyond = 2.0 * (np.cumsum(w[::-1])[::-1] - w) / total        # P(|X| > m)
    findings = []
    if not table or table[-1] != 1 << 63 or list(table).count(1 << 63) != 1:
        findings.append("the table does not end at its first 2^63")
    got = np.array([((1 << 63) - h) / float(1 << 63) for h in table])
    if len(got) > len(beyond):
        return findings + ["the table has %d entries, past 16 sigma" % len(table)]
    off = np.abs(got - beyond[:len(got)]) - (1e-9 * beyond[:len(got)] + 2.0 ** -64)
    if off.max() > 0:
        findings.append("entry %d: its tail is %.6e, the law's is %.6e" % (int(off.argmax()), got[off.argmax()],
                                                                         beyond[off.argmax()]))
    # the last magnitude is where the law's two-sided tail first rounds to nothing: below 2^-64
    if beyond[len(got) - 1] >= 2.0 ** -64 * 1.001 or (len(got) >= 2 and beyond[len(got) - 2] < 2.0 ** -64 * 0.999):
        findings.append("the table ends at %d, which is not where the law's tail falls below 2^-64" % (len(got) - 1))
    return findings


class FedWords(source.Noise):
    """The shipped source with its words replaced by a given list: everything after the word is the real path."""

    def __init__(self, profile_name, sigma_num, sigma_den, words):
        channels = C.PROFILES[profile_name]["channels"]
        self.fed = list(words) + [0] * (-len(words) % channels)
        super().__init__(profile_name, 0, sigma_num, sigma_den, len(self.fed) // channels)

    def words(self, first, count):
        return iter(self.fed[first:first + count])


def boundary_words(table):
    """For every table boundary, the words on each side of it, with both signs, and what each must give."""
    words, want = [], []
    for m, h in enumerate(table):
        below = table[m - 1] if m else 0
        if h > below:                       # magnitude m is reachable: u from `below` to h - 1
            for u in (below, h - 1):
                for sign in (0, 1):
                    words.append((u << 1) | sign)
                    want.append(-m if sign else m)
    return words, want


def stream_findings(make, table):
    """Feed the boundary words through `make(words)`, a source, and compare what it yields."""
    words, want = boundary_words(table)
    if not words:
        return ["NOTHING-FED"]
    got = [v for frame in make(words) for v in frame][:len(words)]
    wrong = [i for i in range(len(words)) if got[i] != want[i]]
    if wrong:
        i = wrong[0]
        return ["%d of %d boundary words gave the wrong sample; the first: word %d gave %d, the table says %d"
                % (len(wrong), len(words), words[i], got[i], want[i])]
    return []


_runs = {}


def gate_run(name):
    """The run the design named for this profile, drawn once: an int64 array (2^20, channels)."""
    if name not in _runs:
        run = ref.GATE_RUNS[name]
        noise = source.Noise(name, run["seed"], run["sigma"][0], run["sigma"][1], GATE_DRAWS)
        _runs[name] = np.array(list(noise), dtype=np.int64)
    return _runs[name]


# ---------------------------------------------------------------- the gate

@pytest.mark.parametrize("sn,sd", [(1, 1), (3, 2), (2, 1), (37, 10), (100, 1), (1000, 1)])
def test_gate_noise_tails__every_table_entry_is_the_law_rounded(sn, sd):
    table = source.gaussian_table(sn, sd)
    assert table_findings(table, sn, sd) == []
    assert tuple(table) == ref.ref_table(sn, sd)
    # the depth: no magnitude past the last index, which is where the two-sided tail falls below 2^-64
    last = len(table) - 1
    if sn >= 100 * sd:
        assert 9.15 * sn <= last * sd <= 9.16 * sn, "the tails stop at 9.155 sigma"
    assert float_tail_findings(table, sn, sd) == [], "the float check agrees where both are run"


@pytest.mark.parametrize("sn,sd,last", [(100, 1, 916), (1000, 1, 9155), (3579, 1, 32767), (5000, 1, 45776)])
def test_gate_noise_tails__the_long_tables_follow_the_law_in_every_tail(sn, sd, last):
    table = source.gaussian_table(sn, sd)
    assert len(table) - 1 == last
    assert float_tail_findings(table, sn, sd) == []
    assert 9.15 * sn <= last * sd <= 9.16 * sn


@pytest.mark.parametrize("name", PROFILES)
def test_gate_noise_tails__the_stream_yields_every_magnitude_its_table_holds(name):
    for sn, sd in ((1, 1), (2, 1), ref.GATE_RUNS[name]["sigma"]):
        table = source.gaussian_table(sn, sd)
        assert stream_findings(lambda words: FedWords(name, sn, sd, words), table) == []
        words, want = boundary_words(table)
        assert max(want) == len(table) - 1 == -min(want), "the last magnitude is reached, on both sides"
        # Four words a magnitude. Far out, where a magnitude's whole probability is under 2^-64, the
        # rounded table gives some magnitudes one unit of 2^-63 and others none: those cannot occur.
        assert 4 * len(table) >= len(words) >= 3.6 * len(table)
    # the two ends of the word range
    edge = list(FedWords(name, 2, 1, [0, 1, 2 ** 64 - 2, 2 ** 64 - 1]))
    assert [v for f in edge for v in f][:4] == [0, 0, 18, -18]


@pytest.mark.parametrize("name", PROFILES)
def test_gate_noise_tails__sampled_counts_follow_the_law_to_four_sigma_in_every_channel(name):
    sn, sd = ref.GATE_RUNS[name]["sigma"]
    run = gate_run(name)
    assert run.shape == (GATE_DRAWS, C.PROFILES[name]["channels"])
    deepest = threshold(GATE_DEPTH, sn, sd)
    expected = GATE_DRAWS * ref.ref_tail(sn, sd, deepest)
    assert 32 <= expected <= 34, "about 33 draws are expected beyond 4 sigma on a side"
    for c in range(run.shape[1]):
        assert sampled_findings(run[:, c], sn, sd) == [], "channel %d" % c
        upper, lower = count_sides(run[:, c], deepest)
        assert upper > 0 and lower > 0


def test_gate_noise_tails__a_depth_the_run_is_too_short_for_is_refused_not_passed():
    sn, sd = ref.GATE_RUNS["s16x1"]["sigma"]
    run = gate_run("s16x1")[:, 0]
    assert any(f.startswith("REFUSED") for f in sampled_findings(run, sn, sd, zs=(4.5,)))
    assert any(f.startswith("REFUSED") for f in sampled_findings(run[:1 << 16], sn, sd))
    assert sampled_findings(run[:0], sn, sd) == ["NOTHING-COUNTED"]


def test_mod_a_far_out_some_magnitudes_cannot_occur_and_the_doc_says_where():
    # A probability is a multiple of 2^-63. Where a magnitude's whole probability is below that, the
    # rounded cumulative gives some magnitudes one unit and others none. docs/model/mod-a.md states
    # these figures as a limit.
    for sigma, never, first in ((1000, 492, 8559), (5000, 3398, 41816)):
        table = source.gaussian_table(sigma, 1)
        gaps = [m for m in range(1, len(table)) if table[m] == table[m - 1]]
        assert (len(gaps), gaps[0]) == (never, first)
        assert all(table[m] - table[m - 1] in (0, 1) for m in range(first, len(table)))


def test_mod_a_the_discrete_laws_tail_is_below_the_continuous_gaussians_as_the_doc_says():
    # P(X >= k) of the discrete law against Q((k - 1/2) / sigma) of a continuous Gaussian of the same
    # sigma: lower by about z^2 / (24 sigma^2). 21% at 5 sigma for sigma = 2; a part in a million for 1000.
    for sigma, k, low, high in ((2, 10, -0.22, -0.20), (100, 500, -1.2e-4, -1.0e-4), (1000, 5000, -1.2e-6, -1.0e-6)):
        continuous = 0.5 * math.erfc((k - 0.5) / sigma / math.sqrt(2))
        assert low < ref.ref_tail(sigma, 1, k) / continuous - 1 < high, sigma


# ---------------------------------------------------------------- the controls

def saturated(run, limit, channel):
    out = run.copy()
    out[:, channel] = np.clip(out[:, channel], -limit, limit)
    return out


def redrawn(run, limit, channel):
    """A sample past the limit is thrown away and the frame before it used again."""
    out = run.copy()
    past = np.flatnonzero(np.abs(out[:, channel]) > limit)
    for i in past:
        out[i, channel] = out[i - 1, channel]
    return out


@pytest.mark.parametrize("name", PROFILES)
def test_control_noise_tails__samples_clipped_one_below_four_sigma_are_caught_in_each_channel(name):
    sn, sd = ref.GATE_RUNS[name]["sigma"]
    run = gate_run(name)
    limit = threshold(GATE_DEPTH, sn, sd) - 1
    for clip in (saturated, redrawn):
        for c in range(run.shape[1]):
            broken = clip(run, limit, c)
            assert int(np.abs(broken[:, c]).max()) <= limit < int(np.abs(run[:, c]).max())
            for other in range(run.shape[1]):
                findings = sampled_findings(broken[:, other], sn, sd)
                if other == c:
                    deep = [f for f in findings if f.startswith("k=%d " % (limit + 1))]
                    assert len(deep) == 2 and all(" 0 counted" in f for f in deep), findings
                else:
                    assert findings == [], "only the clipped channel fails"


@pytest.mark.parametrize("name", PROFILES)
def test_control_noise_tails__one_side_clipped_is_caught_on_that_side(name):
    sn, sd = ref.GATE_RUNS[name]["sigma"]
    run = gate_run(name)
    limit = threshold(GATE_DEPTH, sn, sd) - 1
    broken = run.copy()
    broken[:, 0] = np.minimum(broken[:, 0], limit)
    findings = sampled_findings(broken[:, 0], sn, sd)
    assert len(findings) == 1 and "upper" in findings[0]


@pytest.mark.parametrize("sn,sd", [(1, 1), (2, 1), (100, 1), (1000, 1)])
def test_control_noise_tails__a_table_cut_short_or_moved_is_caught(sn, sd):
    table = list(source.gaussian_table(sn, sd))
    last = len(table) - 1
    eight = threshold(8.0, sn, sd)
    assert eight < last
    cut_at_eight = table[:eight] + [1 << 63]
    assert any("entries" in f for f in table_findings(cut_at_eight, sn, sd))
    assert any("units of 2^-63 from the law" in f for f in table_findings(cut_at_eight, sn, sd))
    without_last = table[:-2] + [1 << 63]
    assert table_findings(without_last, sn, sd) != [], "one magnitude short"
    assert float_tail_findings(cut_at_eight, sn, sd) != []
    # any one entry two units out is caught, wherever it is
    for m in sorted({0, 1, last // 3, last // 2, last - 2, last - 1}):
        for by in (-2, 2):
            moved = list(table)
            moved[m] += by
            assert table_findings(moved, sn, sd) != [], "entry %d moved by %d" % (m, by)


@pytest.mark.parametrize("name", PROFILES)
def test_control_noise_tails__a_stream_clipped_past_the_sampled_depth_is_caught_at_the_boundaries(name):
    sn, sd = ref.GATE_RUNS[name]["sigma"]
    table = source.gaussian_table(sn, sd)
    limit = threshold(8.0, sn, sd)

    class ClippedDeep(FedWords):
        """Right table, right words, and an iteration that saturates at 8 sigma."""

        def from_frame(self, first):
            for frame in super().from_frame(first):
                yield tuple(max(-limit, min(limit, v)) for v in frame)

    findings = stream_findings(lambda words: ClippedDeep(name, sn, sd, words), table)
    assert len(findings) == 1 and "gave the wrong sample" in findings[0]
    # and the sampled test cannot see it: 8 sigma is far past what 2^20 draws reach. That is why
    # the boundary test exists.
    run = gate_run(name)
    assert int(np.abs(run).max()) < limit
    assert sampled_findings(np.clip(run[:, 0], -limit, limit), sn, sd) == []


def uniform_sum(parts, sigma_num, draws, seed):
    """A generator with thin tails and the right variance: `parts` uniform draws added.

    Each part is uniform on -a..a, a chosen so that parts * a (a + 1) / 3 is sigma^2 as nearly as an
    integer a allows. Its tail ends at parts * a.
    """
    a = int(round((-1 + math.sqrt(1 + 12.0 * sigma_num * sigma_num / parts)) / 2))
    words = ref.ref_words(seed, 0, draws * parts).reshape(draws, parts)
    return (words % np.uint64(2 * a + 1)).astype(np.int64).sum(axis=1) - parts * a, a


def test_control_noise_tails__thin_tails_with_the_right_variance_are_caught():
    sn, sd = ref.GATE_RUNS["s16x1"]["sigma"]
    deepest, three = threshold(GATE_DEPTH, sn, sd), threshold(3.0, sn, sd)
    # four parts: the tail ends at 3.46 sigma, inside the gate's depth, and nothing is counted past 4
    thin, a = uniform_sum(4, sn, GATE_DRAWS, 5)
    assert abs(thin.std() / sn - 1) < 0.01, "the variance is right"
    assert 4 * a < deepest
    findings = sampled_findings(thin, sn, sd)
    assert sum(1 for f in findings if f.startswith("k=%d " % deepest) and " 0 counted" in f) == 2, findings
    # twelve parts, the textbook approximation: its tail runs to 6 sigma, and it is too thin from 3 sigma out
    thin, a = uniform_sum(12, sn, GATE_DRAWS, 5)
    assert abs(thin.std() / sn - 1) < 0.01 and 12 * a > deepest
    findings = sampled_findings(thin, sn, sd)
    low = [f for f in findings if f.startswith("k=%d " % three) and "-" in f.split("expected,")[1]]
    assert len(low) == 2, findings


# ---------------------------------------------------------------- the long run

def long_thresholds(total, sigma_num, sigma_den):
    """Every half sigma from 1 that the total is long enough for, and the deepest k with 32 expected."""
    ks, z = [], 1.0
    while total * ref.ref_tail(sigma_num, sigma_den, threshold(z, sigma_num, sigma_den)) >= 32:
        ks.append(threshold(z, sigma_num, sigma_den))
        z += 0.5
    k = ks[-1]
    while total * ref.ref_tail(sigma_num, sigma_den, k + 1) >= 32:
        k += 1
    return sorted(set(ks + [k]))


def long_part(name, seed, sigma_num, sigma_den, total, start, draws, chunk=1 << 16):
    channels = C.PROFILES[name]["channels"]
    ks = long_thresholds(total, sigma_num, sigma_den)
    counts = [[[0, 0] for _ in ks] for _ in range(channels)]
    noise = source.Noise(name, seed, sigma_num, sigma_den, start + draws)
    frames = noise.from_frame(start)
    done = 0
    while done < draws:
        block = np.array([f for _, f in zip(range(min(chunk, draws - done)), frames)], dtype=np.int64)
        for c in range(channels):
            for j, k in enumerate(ks):
                upper, lower = count_sides(block[:, c], k)
                counts[c][j][0] += upper
                counts[c][j][1] += lower
        done += len(block)
        if done % (chunk * 256) == 0:
            print("  %d of %d frames" % (done, draws), flush=True)
    return {"profile": name, "seed": seed, "sigma_num": sigma_num, "sigma_den": sigma_den, "total": total,
            "start": start, "draws": draws, "thresholds": ks, "counts": counts}


def long_judge(parts):
    first = parts[0]
    key = ("profile", "seed", "sigma_num", "sigma_den", "total", "thresholds")
    assert all(all(p[k] == first[k] for k in key) for p in parts), "the parts are not of one run"
    spans = sorted((p["start"], p["start"] + p["draws"]) for p in parts)
    assert spans[0][0] == 0 and spans[-1][1] == first["total"] and all(a[1] == b[0] for a, b in zip(spans, spans[1:])), \
        "the parts do not cover frames 0 to the total exactly once: %r" % (spans,)
    ks, sn, sd, total = first["thresholds"], first["sigma_num"], first["sigma_den"], first["total"]
    ok = True
    for c in range(len(first["counts"])):
        counts = {k: (sum(p["counts"][c][j][0] for p in parts), sum(p["counts"][c][j][1] for p in parts))
                  for j, k in enumerate(ks)}
        print("channel %d, %d draws, sigma %d/%d" % (c, total, sn, sd))
        for k in ks:
            p = ref.ref_tail(sn, sd, k)
            print("  k=%-8d (%.3f sigma)  expected %14.1f  upper %12d  lower %12d  sd %.1f"
                  % (k, k * sd / sn, total * p, counts[k][0], counts[k][1], math.sqrt(total * p * (1 - p))))
        findings = judge(counts, total, sn, sd)
        for f in findings:
            print("  FINDING %s" % f)
        clipped = {k: (v if k < ks[-1] else (0, 0)) for k, v in counts.items()}
        caught = judge(clipped, total, sn, sd)
        print("  the same draws clipped at %d: %s" % (ks[-1] - 1, "CAUGHT (%d findings)" % len(caught) if caught
                                                      else "NOT CAUGHT"))
        ok = ok and not findings and bool(caught)
    print("== LONG RUN VERDICT: %s, to k = %d (%.3f sigma a side) over %d draws a channel"
          % ("PASS" if ok else "FAIL", ks[-1], ks[-1] * sd / sn, total))
    return ok


def test_mod_a_the_long_run_in_two_parts_judges_as_one_and_its_clip_is_caught(capsys):
    # A small long run, 2^14 draws in two unequal parts: the machinery, not the depth.
    total = 1 << 14
    one = long_part("s24x3", 77, 700, 1, total, 0, total)
    a = long_part("s24x3", 77, 700, 1, total, 0, 5000)
    b = long_part("s24x3", 77, 700, 1, total, 5000, total - 5000)
    for c in range(3):
        for j in range(len(one["thresholds"])):
            assert [a["counts"][c][j][s] + b["counts"][c][j][s] for s in (0, 1)] == one["counts"][c][j]
    assert long_judge([b, a]) is True
    out = capsys.readouterr().out
    assert out.count("CAUGHT (") == 3 and "NOT CAUGHT" not in out and "LONG RUN VERDICT: PASS" in out
    with pytest.raises(AssertionError):
        long_judge([a])                 # half a run is not a run
    # the counts are the ones a direct count of the stream gives
    whole = np.array(list(source.Noise("s24x3", 77, 700, 1, total)), dtype=np.int64)
    for c in range(3):
        for j, k in enumerate(one["thresholds"]):
            assert list(count_sides(whole[:, c], k)) == one["counts"][c][j]
    deepest = one["thresholds"][-1]
    assert total * ref.ref_tail(700, 1, deepest) >= 32 > total * ref.ref_tail(700, 1, deepest + 1)


def figures():
    """Print what docs/model/mod-a.md states as MEASURED: the gate runs' counts, the rate, table build times."""
    import time
    for name in PROFILES:
        sn, sd = ref.GATE_RUNS[name]["sigma"]
        t0 = time.perf_counter()
        run = gate_run(name)
        seconds = time.perf_counter() - t0
        print("%s seed %d sigma %d/%d: %d frames in %.2f s, %.2f microseconds a draw; largest magnitude drawn %d"
              % (name, ref.GATE_RUNS[name]["seed"], sn, sd, len(run), seconds, seconds / run.size * 1e6,
                 int(np.abs(run).max())))
        for c in range(run.shape[1]):
            for z in SHALLOW + (GATE_DEPTH,):
                k = threshold(z, sn, sd)
                p = ref.ref_tail(sn, sd, k)
                sd_ = math.sqrt(len(run) * p * (1 - p))
                upper, lower = count_sides(run[:, c], k)
                print("  channel %d  k=%-6d (%.1f sigma)  expected %9.1f  upper %6d (%+.2f sd)  lower %6d (%+.2f sd)"
                      % (c, k, z, len(run) * p, upper, (upper - len(run) * p) / sd_, lower, (lower - len(run) * p) / sd_))
            print("  channel %d findings: %r" % (c, sampled_findings(run[:, c], sn, sd)))
    for name, sigma in (("s16x1", 1000), ("s16x1", 3579), ("s24x3", 5000), ("s24x3", 100000)):
        t0 = time.perf_counter()
        table = source.Noise(name, 0, sigma, 1, 0).table
        print("table for sigma %d: %d entries, built in %.3f s" % (sigma, len(table), time.perf_counter() - t0))
    return 0


def main(argv):
    def arg(flag, default):
        return argv[argv.index(flag) + 1] if flag in argv else default

    if "--figures" in argv:
        return figures()
    if "--judge" in argv:
        parts = []
        for path in argv[argv.index("--judge") + 1:]:
            with open(path, encoding="utf-8") as f:
                parts.append(json.load(f))
        return 0 if long_judge(parts) else 1
    if "--long" not in argv:
        print(__doc__)
        return 2
    name = arg("--profile", "s16x1")
    seed = int(arg("--seed", ref.GATE_RUNS[name]["seed"]))
    sn, sd = (int(v) for v in arg("--sigma", "%d/%d" % ref.GATE_RUNS[name]["sigma"]).split("/"))
    draws = int(arg("--draws", 1 << 30))
    total = int(arg("--total", draws))
    start = int(arg("--start", 0))
    print("long run: profile %s seed %d sigma %d/%d, frames %d to %d of %d"
          % (name, seed, sn, sd, start, start + draws, total), flush=True)
    part = long_part(name, seed, sn, sd, total, start, draws)
    if "--out" in argv:
        with open(arg("--out", None), "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(part) + "\n")
        print("wrote %s" % arg("--out", None))
    if start == 0 and draws == total:
        return 0 if long_judge([part]) else 1
    print("a part of a run: judge the parts together with --judge")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

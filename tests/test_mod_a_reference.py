"""MOD-A's second implementation: what the source and the injector are judged against.

THIS FILE IMPORTS NOTHING OF `model/`, and a test below holds it to that. It
states again, on purpose, every constant and every rule it needs. It works
with other tools than the model does: numpy's uint64 for the words (the model
uses Python ints and a mask), 50-digit `decimal` for the Gaussian law (the
model uses 192-bit fixed point), numpy's search for the lookup (the model uses
`bisect`), `fractions` and Python's own `round` for an injected sample (the
model uses floor division), `struct` for bytes (the model uses `int.to_bytes`).

The frozen vectors under vectors/mod-a/ that are not worked by hand are
written by this file:

    python tests/test_mod_a_reference.py --write-vectors

and a test in each of the other MOD-A files compares the model with them.
"""
import ast
import decimal
import fractions
import functools
import hashlib
import json
import os
import struct
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:        # run as a script, the tree's root is not on the path yet
    sys.path.insert(0, ROOT)

from spec import constants as C  # noqa: E402

VECTORS = os.path.join(ROOT, "vectors", "mod-a")

# SplitMix64, stated again.
R_GAMMA = 0x9E3779B97F4A7C15
R_MIX1 = 0xBF58476D1CE4E5B9
R_MIX2 = 0x94D049BB133111EB
R_MASK = 0xFFFFFFFFFFFFFFFF

# The two runs the tail test and the frozen noise vector use, named in the design before any run.
GATE_RUNS = {"s16x1": {"seed": 20261123, "sigma": (1000, 1)},
             "s24x3": {"seed": 20261124, "sigma": (5000, 1)}}


def vector(name):
    with open(os.path.join(VECTORS, name), encoding="utf-8") as f:
        return json.load(f)


def ref_words(seed, start, count):
    """Words start .. start + count - 1 of the seed's sequence, as a uint64 array."""
    with np.errstate(over="ignore"):
        index = np.arange(count, dtype=np.uint64) + np.uint64((start + 1) & R_MASK)     # wraps at 2^64
        z = np.uint64(seed) + np.uint64(R_GAMMA) * index
        z = (z ^ (z >> np.uint64(30))) * np.uint64(R_MIX1)
        z = (z ^ (z >> np.uint64(27))) * np.uint64(R_MIX2)
        return z ^ (z >> np.uint64(31))


def _undo_xorshift(z, shift):
    out = z
    for _ in range(64 // shift + 1):
        out = z ^ (out >> shift)
    return out


def ref_unmix(word):
    """The state a word came from: the three steps of the mix, each undone."""
    z = _undo_xorshift(word, 31)
    z = (z * pow(R_MIX2, -1, 1 << 64)) & R_MASK
    z = _undo_xorshift(z, 27)
    z = (z * pow(R_MIX1, -1, 1 << 64)) & R_MASK
    return _undo_xorshift(z, 30)


@functools.lru_cache(maxsize=None)
def ref_law(sigma_num, sigma_den, digits=50):
    """The discrete Gaussian, by `decimal`: (weights w[m] = exp(-m^2 / (2 sigma^2)), their two-sided total).

    Weights below 10^-(digits - 5) are left out; what they sum to is far below 2^-64.
    """
    ctx = decimal.Context(prec=digits)
    two_s2 = ctx.divide(decimal.Decimal(2 * sigma_num * sigma_num), decimal.Decimal(sigma_den * sigma_den))
    floor_ = decimal.Decimal(10) ** -(digits - 5)
    weights, m = [], 0
    while True:
        w = ctx.exp(ctx.divide(decimal.Decimal(-m * m), two_s2))
        if w < floor_:
            break
        weights.append(w)
        m += 1
    total = weights[0]
    for w in weights[1:]:
        total = ctx.add(total, ctx.add(w, w))
    return tuple(weights), total


@functools.lru_cache(maxsize=None)
def ref_ideal(sigma_num, sigma_den, digits=50):
    """2^63 * P(|X| <= m) for every m the law holds, as Decimals: what a table entry should round."""
    ctx = decimal.Context(prec=digits)
    weights, total = ref_law(sigma_num, sigma_den, digits)
    scale = ctx.divide(decimal.Decimal(1 << 63), total)
    out, acc = [], decimal.Decimal(0)
    for m, w in enumerate(weights):
        acc = ctx.add(acc, w if m == 0 else ctx.add(w, w))
        out.append(ctx.multiply(acc, scale))
    return tuple(out)


@functools.lru_cache(maxsize=None)
def ref_table(sigma_num, sigma_den):
    """The table the law gives: each ideal entry rounded to the nearest integer, to its first 2^63."""
    out = []
    for ideal in ref_ideal(sigma_num, sigma_den):
        h = int((ideal + decimal.Decimal("0.5")).to_integral_value(rounding=decimal.ROUND_FLOOR))
        out.append(h)
        if h == 1 << 63:
            break
    return tuple(out)


@functools.lru_cache(maxsize=None)
def _ref_tails(sigma_num, sigma_den):
    two_s2 = 2.0 * sigma_num * sigma_num / (sigma_den * sigma_den)
    m = np.arange(0, int(14 * sigma_num / sigma_den) + 3, dtype=np.float64)
    w = np.exp(-(m * m) / two_s2)
    total = w[0] + 2.0 * w[1:].sum()
    return np.cumsum(w[::-1])[::-1] / total               # summed from the small end


def ref_tail(sigma_num, sigma_den, k):
    """P(X >= k), one side, for k >= 1, in floats: the law summed directly, out to 14 sigma."""
    tails = _ref_tails(sigma_num, sigma_den)
    return float(tails[k]) if k < len(tails) else 0.0


def ref_noise(profile_name, seed, sigma_num, sigma_den, start_frame, count, table=None):
    """Frames start_frame .. start_frame + count - 1 of the noise, as an int64 array (count, channels)."""
    channels = C.PROFILES[profile_name]["channels"]
    if table is None:
        table = ref_table(sigma_num, sigma_den)
    words = ref_words(seed, start_frame * channels, count * channels)
    magnitude = np.searchsorted(np.array(table, dtype=np.uint64), words >> np.uint64(1), side="right").astype(np.int64)
    negative = (words & np.uint64(1)).astype(np.int64)
    return (magnitude * (1 - 2 * negative)).reshape(count, channels)


def ref_scaled(pulse, num, den):
    """What an injection adds: each pulse sample times num / den, by Python's own round (half to even)."""
    return [round(fractions.Fraction(p * num, den)) for p in pulse]


def ref_bytes(profile_name, frames):
    """A stream's bytes by `struct`: each sample the low bytes of a little-endian 32-bit int."""
    size = {16: 2, 24: 3}[C.PROFILES[profile_name]["sample_bits"]]
    return b"".join(struct.pack("<i", int(v))[:size] for frame in frames for v in frame)


def ref_recording(profile_name, frames):
    p = C.PROFILES[profile_name]
    payload = ref_bytes(profile_name, frames)
    return struct.pack("<8sHHHHQ32s", b"UNDTSTRM", 1, p["sample_bits"], p["channels"], 0, len(frames),
                       hashlib.sha256(payload).digest()) + payload


def noise_vector():
    out = {"what": "The noise generator's first frames and a digest of more, for the two runs the design named "
                   "(seed and sigma per profile) before anything was run.",
           "how": "Worked by tests/test_mod_a_reference.py, which imports nothing of model/: numpy uint64 words, "
                  "a table rounded from a 50-digit decimal recomputation of the law, numpy's search. "
                  "sha256_4096 is the SHA-256 of the canonical bytes of frames 0 to 4095: each sample two's "
                  "complement, little-endian, in whole bytes, frame by frame, channel by channel.",
           "runs": []}
    for name in sorted(GATE_RUNS):
        run = GATE_RUNS[name]
        frames = ref_noise(name, run["seed"], run["sigma"][0], run["sigma"][1], 0, 4096).tolist()
        out["runs"].append({"profile": name, "seed": run["seed"], "sigma_num": run["sigma"][0],
                            "sigma_den": run["sigma"][1], "first_frames": frames[:8],
                            "sha256_4096": hashlib.sha256(ref_bytes(name, frames)).hexdigest()})
    return out


def table_vector():
    return {"what": "The half table H for two small sigmas: H[m] = 2^63 * P(|X| <= m) for the discrete Gaussian, "
                    "rounded to the nearest integer, ending at the first entry equal to 2^63 = 9223372036854775808.",
            "how": "Worked by tests/test_mod_a_reference.py, which imports nothing of model/, from exp() in "
                   "50-digit decimal arithmetic.",
            "tables": [{"sigma_num": n, "sigma_den": d, "table": list(ref_table(n, d))}
                       for n, d in ((1, 1), (2, 1), (3, 2))]}


def write_vectors():
    os.makedirs(VECTORS, exist_ok=True)
    for name, doc in (("noise.json", noise_vector()), ("table.json", table_vector())):
        with open(os.path.join(VECTORS, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(doc, indent=1) + "\n")
        print("wrote vectors/mod-a/%s" % name)


# ---- this file's own tests ----

def test_mod_a_reference_imports_nothing_of_the_model():
    with open(os.path.abspath(__file__), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert "spec" in imported, "the walk saw this file's imports"
    assert "model" not in imported and "stats" not in imported
    assert "model" not in {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


def test_mod_a_reference_words_are_the_published_ones():
    v = vector("words.json")
    assert ref_words(1234567, 0, 5).tolist() == v["first_words"]["words"]
    assert v["first_words"]["seed"] == 1234567 and len(v["first_words"]["words"]) == 5
    draws = v["counts"]["draws"]
    assert draws == 100000 and v["counts"]["seed"] == 987654321
    # floor(word * 5 / 2^64), on exact Python ints
    bins = [0] * 5
    for w in ref_words(987654321, 0, draws).tolist():
        bins[(w * 5) >> 64] += 1
    assert bins == v["counts"]["counts"] == [20027, 19892, 20073, 19978, 20030]


def test_mod_a_reference_unmix_undoes_the_mix():
    for seed, i in ((0, 0), (1234567, 4), (R_MASK, 12345), (20261123, 1 << 40)):
        state = (seed + R_GAMMA * (i + 1)) & R_MASK
        assert ref_unmix(int(ref_words(seed, i, 1)[0])) == state


def test_mod_a_reference_rounding_is_half_to_even_on_hand_cases():
    # 1/2 -> 0, 3/2 -> 2, 5/2 -> 2, -1/2 -> 0, -3/2 -> -2, 7/3 -> 2, 8/3 -> 3, -7/3 -> -2
    assert ref_scaled([1, 3, 5, -1, -3], 1, 2) == [0, 2, 2, 0, -2]
    assert ref_scaled([7, 8, -7, -8], 1, 3) == [2, 3, -2, -3]


def test_mod_a_reference_law_sums_to_one_and_has_variance_sigma_squared():
    for n, d in ((1, 1), (3, 2), (2, 1), (100, 1)):
        weights, total = ref_law(n, d)
        var = 2 * sum(decimal.Decimal(m * m) * w for m, w in enumerate(weights)) / total
        sigma2 = fractions.Fraction(n * n, d * d)
        rel = abs(float(var) / float(sigma2) - 1)
        # 2.2e-7 at sigma = 1 (the law is not quite sigma^2 there); nothing a float shows from 1.5 up
        assert rel < (3e-7 if (n, d) == (1, 1) else 1e-12), (n, d, rel)
        assert abs(ref_ideal(n, d)[-1] - (1 << 63)) < decimal.Decimal("1e-20"), "the cumulative ends at one"


if __name__ == "__main__":
    if "--write-vectors" in sys.argv:
        write_vectors()
    else:
        print(__doc__)

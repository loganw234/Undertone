"""What LRN-B's test files share. It holds no gate.

Three kinds of thing:

- the frozen vector, vectors/lrn-b/cases.json, worked by hand, and a reader for it;
- the learner's rule WRITTEN OUT A SECOND TIME (`judged`, `worked`, `nearest_even`, `nearest_away`),
  using nothing of `model/`: which windows a truth list gives and how each is judged, the sums, D,
  the peak and the set. It is the independent code the vectors' rule allows, and this file's own tests
  hold it to the hand-worked cases, so that it is itself held by something worked by hand;
- drivers: `drive`, which steps a `model.learner.Learner` over frames with a script of host operations
  exactly as `model.run.learning` does, without the injector; `frozen`, a core with no learner, the
  same frames and a shadow write and a commit at named indexes; and the streams the other files use.
"""
import json
import os

import numpy as np

from spec import constants as C
from model import inject, records, source, weights
from model.detector import Core
from model.learner import Learner
from model.refusal import Refusal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES = sorted(C.PROFILES)
PASS = C.RECTIFIERS["pass"]
VECTOR = os.path.join(ROOT, "vectors", "lrn-b", "cases.json")


def vector():
    with open(VECTOR, "r", encoding="utf-8") as f:
        return json.load(f)


def cases():
    return vector()["cases"]


def channels(profile):
    return C.PROFILES[profile]["channels"]


def start_blob(profile, taps):
    """The matched-filter configuration with every coefficient 0 and a head weight of 1."""
    return weights.pack(profile, [{c: (0,) * taps for c in range(channels(profile))}], (1,), PASS, 1, 0)


def blob_of(profile, rows):
    """The matched-filter configuration with these integer rows, one for each channel."""
    return weights.pack(profile, [{c: tuple(rows[c]) for c in range(len(rows))}], (1,), PASS, 1, 0)


def rows_of(blob):
    config = weights.unpack(blob)
    rows = config["filters"][0]
    return [list(rows[c]) for c in sorted(rows)]


def rec(index, num=0, den=1, pulse="e0"):
    return {"index": index, "pulse_id": C.PULSE_IDS[pulse], "amplitude_num": num, "amplitude_den": den}


# ------------------------------------------------------------ the rule, a second time

def judged(indexes, taps, count_max=None):
    """Every judgement a truth list gives, in the order the learner logs them: a list of
    (next index, record index, label, outcome), with the window's first frame alongside, sorted by
    next index and then record index. FULL is applied here too, counting the windows taken so far."""
    points = []
    for n, j in enumerate(indexes):
        p = indexes[n - 1] if n else None
        q = indexes[n + 1] if n + 1 < len(indexes) else None
        if j < taps:
            o0 = "start"
        elif p is not None and j - p < 2 * taps:
            o0 = "busy"
        else:
            o0 = "free"
        o1 = "busy" if (p is not None and j - p < taps) or (q is not None and q - j < taps) else "free"
        points.append((j, j, 0, o0, j - taps))
        points.append((j + taps, j, 1, o1, j))
    points.sort(key=lambda t: (t[0], t[1]))
    taken = [0, 0]
    out = []
    for at, j, label, o, first in points:
        if o == "free":
            if count_max is not None and taken[label] >= count_max:
                o = "full"
            else:
                o = "taken"
                taken[label] += 1
        out.append((at, j, label, o, first))
    return out


def nearest_even(p, d):
    q, r = divmod(p, d)
    return q + 1 if 2 * r > d or (2 * r == d and q % 2) else q


def nearest_away(p, d):
    s = -1 if p < 0 else 1
    q, r = divmod(abs(p), d)
    return s * (q + 1 if 2 * r >= d else q)


def worked(frames, indexes, taps, u, count_max=None, rounding=nearest_even):
    """The update at u, from the frames and indexes alone: (counts, sums, D, peak, rows or None)."""
    chans = len(frames[0])
    sums = [[[0] * chans for _ in range(taps)] for _ in (0, 1)]
    counts = [0, 0]
    for at, _j, label, o, first in judged(indexes, taps, count_max):
        if at <= u and o == "taken":
            for k in range(taps):
                for c in range(chans):
                    sums[label][k][c] += frames[first + k][c] if first + k >= 0 else 0
            counts[label] += 1
    d = [sums[1][k][c] * counts[0] - sums[0][k][c] * counts[1] for c in range(chans) for k in range(taps)]
    m = max(abs(x) for x in d)
    if m == 0:
        return counts, sums, d, 0, None
    q = [rounding(x * C.COEFF_MAX, m) for x in d]
    return counts, sums, d, m, [q[c * taps:(c + 1) * taps] for c in range(chans)]


def scores_of(frames, rows, taps):
    """Every score of the matched-filter configuration with these rows, from its own sum."""
    out = []
    for i in range(len(frames)):
        s = 0
        for c, row in enumerate(rows):
            for k in range(taps):
                at = i - (taps - 1) + k
                s += row[k] * (frames[at][c] if at >= 0 else 0)
        out.append(s)
    return out


# ------------------------------------------------------------ drivers

def drive(blob, frames, truth, script, update_frames, count_bits=C.LEARN_COUNT_BITS, make=Learner):
    """`model.run.learning`'s loop with the frames as given and no injector. Returns
    (records, outcomes, learner). An operation's argument "start" is the start blob."""
    learner = make(blob, truth, update_frames, count_bits)
    ops = {"update": lambda a: learner.update(a), "commit": lambda a: learner.commit(a),
           "write_shadow": lambda a: learner.write_shadow(blob if a == "start" else a)}
    out, outcomes = [], []
    for i in range(len(frames) + 1):
        assert learner.next_index == i
        for op, argument in script.get(i, ()):
            try:
                ops[op](argument)
                outcomes.append((i, op, argument, None))
            except Refusal as e:
                outcomes.append((i, op, argument, e.name))
        if i < len(frames):
            out.append(learner.step(tuple(frames[i])))
    return out, outcomes, learner


def script_of(case):
    script = {}
    for i, op, argument in case["script"]:
        script.setdefault(i, []).append((op, argument))
    return script


def run_case(case, make=Learner, indexes=None):
    frames = [tuple(f) for f in case["frames"]]
    truth = [rec(j) for j in (case["truth_indexes"] if indexes is None else indexes)]
    return drive(start_blob(case["profile"], case["taps"]), frames, truth, script_of(case), case["update_frames"],
                 case["count_bits"], make)


def frozen(blob, frames, writes=(), commits=()):
    """A core with no learner: `writes` are (next index, blob), `commits` (next index, at), each made
    when the core's next output is that index. Returns its records."""
    core = Core(blob)
    out = []
    for i in range(len(frames) + 1):
        for at, b in writes:
            if at == i:
                core.write_shadow(b)
        for at, c in commits:
            if at == i:
                core.commit(c)
        if i < len(frames):
            out.append(core.step(tuple(frames[i])))
    return out


def as_words(recs):
    return [[r["index"], r["epoch"], r["flags"], r["score"]] for r in recs]


def first_difference(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def noise_frames(profile, seed, sigma, length, schedule):
    """The model's own noise, a sigma a channel as the source makes it, with the schedule's pulses added."""
    noise = source.Noise(profile, seed, sigma[0], sigma[1], length)
    injected, truth = inject.inject(profile, noise, schedule, length)
    return [tuple(f) for f in injected], truth


def digest(recs):
    return records.digest("score", recs)


def as_array(frames):
    return np.array(frames, dtype=np.int64).reshape(len(frames), -1)


# ------------------------------------------------------------ this file's own tests

def test_lrn_b_support_the_rule_written_again_gives_every_hand_worked_figure():
    """The independent code is held to the hand-worked cases: every judgement, the sums, D, the peak,
    the rows, both roundings where the vector gives them, and the scores after the commit."""
    seen = 0
    for case in cases():
        taps = case["taps"]
        count_max = (1 << case["count_bits"]) - 1
        frames = case["frames"]
        got = [list(t[:4]) for t in judged(case["truth_indexes"], taps, count_max) if t[0] <= len(frames)]
        assert got == case["judged"], case["name"]
        for u in case["updates"]:
            counts, sums, d, m, rows = worked(frames, case["truth_indexes"], taps, u["u"], count_max)
            assert list(counts) == u["counts"] and sums[0] == u["sum_label_0"] and sums[1] == u["sum_label_1"]
            assert d == u["difference"] and m == u["peak"] and rows == u["coefficients"], case["name"]
            seen += 1
        away = case["controls"].get("half_away_from_zero")
        if away:
            last = case["updates"][-1]
            assert worked(frames, case["truth_indexes"], taps, last["u"], count_max, nearest_away)[4] == away["coefficients"]
        rows = case["updates"][-1]["coefficients"]
        commit = [o for o in case["outcomes"] if o[1] == "commit" and o[3] is None][0][2]
        want = scores_of(frames, rows, taps)
        assert [s[3] for s in case["scores"] if s[0] >= commit] == want[commit:], case["name"]
        assert all(s[3] == 0 and s[1] == 0 for s in case["scores"] if s[0] < commit), case["name"]
    assert seen == 5


def test_lrn_b_support_the_learner_imports_the_standard_library_the_definition_and_the_model_alone():
    """model/learner.py: no `learn`, no `stats`, no numpy; and no string of its code names a truth field
    but `index` (its docstrings may). A reading of names, not a wall: see the doc's limit 3."""
    import ast
    import sys
    path = os.path.join(ROOT, "model", "learner.py")
    with open(path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module.split(".")[0])
    assert imported - set(sys.stdlib_module_names) == {"spec", "model"}, imported
    docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                  if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
                  and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
               and id(n) not in docstrings]
    fields = [f[0] for f in C.RECORDS["truth"]]
    assert fields[0] == "index" and "index" in strings
    assert [s for s in strings for name in fields[1:] if name in s] == []


def test_lrn_b_support_the_two_roundings_differ_only_at_ties():
    assert [nearest_even(p, 2) for p in (-3, -1, 1, 3, 5)] == [-2, 0, 0, 2, 2]
    assert [nearest_away(p, 2) for p in (-3, -1, 1, 3, 5)] == [-2, -1, 1, 2, 3]
    assert [nearest_even(p, 3) for p in (-4, -2, 2, 4)] == [nearest_away(p, 3) for p in (-4, -2, 2, 4)] == [-1, -1, 1, 1]

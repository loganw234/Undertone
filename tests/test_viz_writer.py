"""Parcel VIZ: the SVG writer, the readers' refusals, the command, the imports, and the colours.

Each condition the generator checks is removed here alone, and the test expects
the refusal by its declared name (viz/errors.py); a refusal under another name
fails. The answers of the writer's helpers are worked by hand in each test's
docstring or comment. Nothing here imports `model/`.
"""
import ast
import math
import os
import re
import shutil
import subprocess
import sys
from decimal import Decimal

import pytest

import viz
from viz import figures as F
from viz import svg
from viz.__main__ import main
from viz.errors import NAMES, VizRefusal
from viz.records import Reader, field, fraction_pair

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARD = "docs/studies/e0-card/card-e0.json"
SOFT0 = "vectors/e0c/round1/part0.json"
SOFT3 = "vectors/e0c/round1/part3.json"
E1_C3 = "docs/studies/e1/c3.json"
E2_PART = "docs/studies/e2/e2-part.json"
E2_JUDGE = "docs/studies/e2/judge-output.txt"
TIMED = "docs/studies/e0-card/timed.json"


def refused(name, fn, *args, **kw):
    with pytest.raises(VizRefusal) as e:
        fn(*args, **kw)
    assert e.value.name == name, "refused %s, not %s: %s" % (e.value.name, name, e.value.detail)
    return e.value


def patched(json_edits=None, text_edits=None, pulses_edit=None):
    """A Reader that changes what it read of named files, in memory: one fault a test."""
    json_edits, text_edits = json_edits or {}, text_edits or {}

    class Patched(Reader):
        def json(self, rel):
            v = super().json(rel)
            if rel in json_edits:
                json_edits[rel](v)
            return v

        def text(self, rel):
            v = super().text(rel)
            return text_edits[rel](v) if rel in text_edits else v

        def pulses(self):
            v = super().pulses()
            if pulses_edit:
                pulses_edit(v)
            return v
    return Patched(ROOT)


# ---------------------------------------------------------------- the writer's helpers


@pytest.mark.parametrize("lo,hi,most,ticks", [
    (0, 1.5, 6, ["0", "0.5", "1.0", "1.5"]),           # 0.1 gives 15 steps, 0.2 gives 8, 0.5 gives 3
    (0, 0.878, 6, ["0", "0.2", "0.4", "0.6", "0.8", "1.0"]),
    (-1213, 1201, 6, ["-1500", "-1000", "-500", "0", "500", "1000", "1500"]),
    (0, 0, 6, ["-1", "-0.5", "0", "0.5", "1"]),         # one value: widened to -1, 1; 0.2 gives 10 steps
    (0, 8, 6, ["0", "2", "4", "6", "8"]),
    (0, 63, 8, ["0", "10", "20", "30", "40", "50", "60", "70"]),
    (-0.0045, 0.0045, 6, ["-0.006", "-0.004", "-0.002", "0.000", "0.002", "0.004", "0.006"]),
])
def test_viz_nice_ticks_worked_by_hand(lo, hi, most, ticks):
    got = svg.nice_ticks(lo, hi, most)
    assert [Decimal(t) for t in ticks] == got
    assert all(type(t) is Decimal for t in got)


@pytest.mark.parametrize("d,label", [(Decimal("1.0"), "1"), (Decimal("0.50"), "0.5"), (Decimal("0.000"), "0"),
                                     (Decimal("1E+3"), "1000"), (Decimal("-0.0040"), "-0.004")])
def test_viz_tick_label(d, label):
    assert svg.tick_label(d) == label


@pytest.mark.parametrize("v,text", [(-0.001, "0.00"), (-0.004999, "0.00"), (-0.006, "-0.01"), (0.125, "0.12"),
                                    (2.5, "2.50"), (1.005, "1.00"), (330.2251, "330.23")])
def test_viz_fmt_rounds_to_a_hundredth_and_never_writes_minus_zero(v, text):
    """0.125 is exact in binary and rounds half to even; 1.005 is a hair below in binary."""
    assert svg.fmt(v) == text


@pytest.mark.parametrize("ch", [chr(233), chr(13), chr(10), chr(9), chr(0x200B), chr(127), chr(0)])
def test_viz_text_outside_printable_ascii_is_refused(ch):
    refused("VIZ-NOT-ASCII", svg.check_ascii, "a" + ch, "a text")
    refused("VIZ-NOT-ASCII", svg.El("text", {"x": 1.0}, "a" + ch).render)
    refused("VIZ-NOT-ASCII", svg.El("line", {"data-x": "a" + ch}).render)
    refused("VIZ-NOT-ASCII", svg.Figure, "f", "title " + ch, [], 100)


def test_viz_printable_ascii_passes_and_is_escaped():
    s = "".join(chr(c) for c in range(32, 127))
    assert svg.check_ascii(s, "x") == s
    assert svg.El("text", {"b": "&", "a": '"<>'}, "a<b & c>").render() == \
        '<text a="&quot;&lt;&gt;" b="&amp;">a&lt;b &amp; c&gt;</text>'


def test_viz_attributes_are_written_sorted():
    assert svg.El("line", {"y2": 1.0, "x1": 2.0, "data-z": "q", "class": "c"}).render() == \
        '<line class="c" data-z="q" x1="2.00" y2="1.00"/>'


def test_viz_exact_forms():
    assert svg.exact(5) == "5"
    assert svg.exact(svg.Ratio(24442, 200000)) == "24442/200000"   # unreduced: the record's integers
    assert svg.exact(0.1 + 0.2) == "0.30000000000000004"
    for bad in (True, "1", None, Decimal(1)):
        with pytest.raises(TypeError):
            svg.exact(bad)


@pytest.mark.parametrize("num,den", [(1, 0), (1, -2), (1.0, 2), (1, True), (True, 2)])
def test_viz_ratio_refuses_what_is_not_two_ints(num, den):
    refused("VIZ-RECORD-FIELD", svg.Ratio, num, den)


def test_viz_linear_axis_refuses_a_value_outside_it():
    ax = svg.LinearAxis("x", [svg.Ratio(3, 2)])                    # 0 to 1.5
    assert ax.frac(1.5) == 1.0 and ax.frac(0) == 0.0 and ax.frac(svg.Ratio(3, 4)) == 0.5
    for v in (1.5000001, -1e-9, float("nan"), float("inf"), svg.Ratio(7, 4)):
        refused("VIZ-AXIS-RANGE", ax.frac, v)


def test_viz_log_axis_decades_and_refusals():
    ax = svg.Log10Axis("w", [32, 32768])
    assert ax.ticks == [10, 100, 1000, 10000, 100000] and ax.labels[-1] == "100,000"
    assert svg.Log10Axis("w", [10, 1000]).ticks == [10, 100, 1000]    # a top on a decade is kept
    assert svg.Log10Axis("w", [5]).ticks == [1, 10]                   # one decade at least
    assert ax.frac(1000) == 0.5
    for bad in ([0, 10], [-5, 10], [1.5, 10], [True, 10]):
        refused("VIZ-AXIS-RANGE", svg.Log10Axis, "w", bad)
    for v in (9, 100001, 100.0):
        refused("VIZ-AXIS-RANGE", ax.frac, v)


def test_viz_category_axis_refusals():
    refused("VIZ-AXIS-RANGE", svg.CategoryAxis, "g", [])
    ax = svg.CategoryAxis("g", [0, 1, 2, 3])
    assert ax.frac(0) == 0.125 and ax.frac(3) == 0.875
    for v in (-1, 4, True, 1.0):
        refused("VIZ-AXIS-RANGE", ax.frac, v)


def test_viz_refusal_names_are_declared():
    with pytest.raises(ValueError):
        VizRefusal("VIZ-NOT-A-NAME", "x")
    assert len(NAMES) == len(set(NAMES)) == 7


# ---------------------------------------------------------------- the reader


def test_viz_field_refusals():
    rec = {"i": 1, "f": 1.5, "b": True, "nan": float("nan"), "inf": float("inf"), "s": "x", "l": [1, 2]}
    assert field(rec, "i", "int", "r") == 1 and field(rec, "f", "number", "r") == 1.5
    assert field(rec, "i", "number", "r") == 1
    for key, kind in (("missing", "int"), ("b", "int"), ("b", "number"), ("f", "int"), ("nan", "number"),
                      ("inf", "number"), ("s", "number"), ("l", "dict"), ("i", "str")):
        refused("VIZ-RECORD-FIELD", field, rec, key, kind, "r")
    refused("VIZ-RECORD-FIELD", field, [1], "i", "int", "r")
    assert fraction_pair({"a": [3, 2]}, "a", "r") == (3, 2)
    for bad in ([3], [3, 2, 1], [3, 0], [3, -2], [3.0, 2], [True, 2], "3/2"):
        refused("VIZ-RECORD-FIELD", fraction_pair, {"a": bad}, "a", "r")


def test_viz_reader_refusals(tmp_path):
    root = str(tmp_path)
    r = Reader(root)
    refused("VIZ-RECORD-MISSING", r.json, "a.json")
    assert r.log == []                     # a refused read of a missing file logs nothing
    refused("VIZ-RECORD-MISSING", r.glob, "nowhere", r"part(\d+)\.json")
    os.makedirs(os.path.join(root, "d"))
    refused("VIZ-RECORD-MISSING", r.glob, "d", r"part(\d+)\.json")
    for name in ("part10.json", "part2.json", "xpart1.json", "part1.jsonx"):
        open(os.path.join(root, "d", name), "w").write("{}")
    assert r.glob("d", r"part(\d+)\.json") == ["d/part2.json", "d/part10.json"]   # by number, whole names
    open(os.path.join(root, "bad.json"), "wb").write(b"{")
    refused("VIZ-RECORD-FIELD", r.json, "bad.json")
    open(os.path.join(root, "latin.txt"), "wb").write(bytes([0xE9]))
    refused("VIZ-RECORD-FIELD", r.text, "latin.txt")
    refused("VIZ-RECORD-FIELD", r.json, "latin.txt")


@pytest.mark.parametrize("text", [
    "X = 1\n",                                              # no PULSES
    "PULSES = {'e0': (1, 2)}\nPULSES = {'e0': (1, 2)}\n",  # twice
    "PULSES = dict(e0=(1, 2))\n",                           # not a literal
    "PULSES = {'e0': [1, 2]}\n",                            # a list, not a tuple
    "PULSES = {'e0': (1, 2.0)}\n",                          # not all ints
    "PULSES = {'e0': ()}\n",                                # empty
    "PULSES = {}\n",
    "PULSES = ((1, 2),)\n",                                 # not a dict
    "PULSES = {\n",                                         # does not parse
])
def test_viz_pulses_refusals(tmp_path, text):
    os.makedirs(os.path.join(str(tmp_path), "spec"))
    open(os.path.join(str(tmp_path), "spec", "constants.py"), "w").write(text)
    refused("VIZ-RECORD-FIELD", Reader(str(tmp_path)).pulses)


def test_viz_pulses_hash_is_of_the_value_not_the_file(tmp_path):
    os.makedirs(os.path.join(str(tmp_path), "spec"))
    p = os.path.join(str(tmp_path), "spec", "constants.py")
    open(p, "w").write("A = 1\nPULSES = {'e1': (3, 4), 'e0': (1, 2)}\n")
    one = Reader(str(tmp_path))
    assert one.pulses() == {"e0": (1, 2), "e1": (3, 4)}
    open(p, "w").write("# another line of the definition\nA = 2\nPULSES = {'e0': (1, 2), 'e1': (3, 4)}\n")
    two = Reader(str(tmp_path))
    two.pulses()
    assert one.log == two.log
    # sha256 of '{"e0":[1,2],"e1":[3,4]}', worked by hashlib on that literal text
    import hashlib
    assert one.log[0][1] == hashlib.sha256(b'{"e0":[1,2],"e1":[3,4]}').hexdigest()
    open(p, "w").write("PULSES = {'e0': (1, 3), 'e1': (3, 4)}\n")
    three = Reader(str(tmp_path))
    three.pulses()
    assert three.log != one.log


# ---------------------------------------------------------------- each figure's refusals, one fault each


def drop(key):
    return lambda v: v.pop(key)


def setv(key, val):
    def f(v):
        v[key] = val
    return f


def card_part(i, key, val):
    def f(v):
        v["parts"][i][key] = val
    return f


@pytest.mark.parametrize("edits,name", [
    ({SOFT0: drop("found")}, "VIZ-RECORD-FIELD"),
    ({SOFT0: setv("found", True)}, "VIZ-RECORD-FIELD"),
    ({SOFT0: setv("d", float("nan"))}, "VIZ-RECORD-FIELD"),
    ({SOFT0: setv("amplitude", [1])}, "VIZ-RECORD-FIELD"),
    ({SOFT0: setv("amplitude", [1, 0])}, "VIZ-RECORD-FIELD"),
    ({SOFT0: setv("profile", 7)}, "VIZ-RECORD-FIELD"),
    ({CARD: drop("parts")}, "VIZ-RECORD-FIELD"),
    ({CARD: card_part(0, "amplitude", [7, 4])}, "VIZ-RECORD-PAIR"),       # no card part at 1/2
    ({CARD: card_part(1, "amplitude", [1, 2])}, "VIZ-RECORD-PAIR"),       # two card parts at 1/2
    ({CARD: lambda v: v["parts"].append(dict(v["parts"][0], amplitude=[7, 4]))}, "VIZ-RECORD-PAIR"),
    ({CARD: card_part(2, "n", 200001)}, "VIZ-RECORD-PAIR"),
    ({CARD: card_part(2, "d", 2.0)}, "VIZ-RECORD-PAIR"),
    ({CARD: card_part(2, "pfa", 0.02)}, "VIZ-RECORD-PAIR"),
    ({CARD: card_part(2, "sigma", [1478, 1])}, "VIZ-RECORD-PAIR"),
    ({CARD: card_part(2, "expected", 0.5)}, "VIZ-RECORD-PAIR"),
    ({CARD: card_part(2, "profile", "s24x3")}, "VIZ-RECORD-PAIR"),
    # alike in the pair, unlike across amplitudes: one curve needs one sigma, one Pfa, one profile
    ({SOFT3: setv("sigma", [1478, 1]), CARD: card_part(3, "sigma", [1478, 1])}, "VIZ-RECORD-PAIR"),
    ({SOFT3: setv("pfa", 0.02), CARD: card_part(3, "pfa", 0.02)}, "VIZ-RECORD-PAIR"),
    ({SOFT3: setv("profile", "s24x3"), CARD: card_part(3, "profile", "s24x3")}, "VIZ-RECORD-PAIR"),
])
def test_viz_e0_refusals(edits, name):
    refused(name, F.e0_efficiency, patched(json_edits=edits))


def test_viz_e0_refuses_tolerances_of_two_widths(monkeypatch):
    """The legend names one z; tolerances worked at two would make it wrong."""
    real, calls = F.tolerance, []

    def two_widths(pfa, d, n, m=None):
        calls.append(1)
        return real(pfa, d, n, m, z=4.0 if len(calls) == 1 else 3.0)
    monkeypatch.setattr(F, "tolerance", two_widths)
    refused("VIZ-RECORD-PAIR", F.e0_efficiency, Reader(ROOT))


def test_viz_e0_refuses_pulses_without_e0():
    refused("VIZ-RECORD-FIELD", F.e0_efficiency, patched(pulses_edit=lambda v: v.pop("e0")))


@pytest.mark.parametrize("key,val", [("pfa", 0.02), ("d_matched", 2.0), ("n", 99999), ("m", 299999),
                                     ("k", 2999), ("sigma", [1478, 1]), ("profile", "s24x3")])
def test_viz_e1_refuses_parts_that_disagree(key, val):
    refused("VIZ-RECORD-PAIR", F.e1_learning, patched(json_edits={E1_C3: setv(key, val)}))


@pytest.mark.parametrize("edit,name", [
    (drop("k"), "VIZ-RECORD-FIELD"),
    (drop("base_found"), "VIZ-RECORD-FIELD"),
    (setv("d_learned", "2.3"), "VIZ-RECORD-FIELD"),
    (setv("labelled_windows", 0), "VIZ-AXIS-RANGE"),
])
def test_viz_e1_refusals(edit, name):
    refused(name, F.e1_learning, patched(json_edits={E1_C3: edit}))


def entry(model, g=None):
    def find(v):
        return [e for e in v["entries"] if e["model"] == model and (g is None or e["g"] == g)][0]
    return find


@pytest.mark.parametrize("edit,name", [
    (lambda v: v["entries"].append(dict(entry("frozen")(v))), "VIZ-RECORD-FIELD"),     # two frozen
    (lambda v: v["entries"].remove(entry("e1")(v)), "VIZ-RECORD-FIELD"),               # no e1 filter
    (lambda v: entry("adaptive", 3)(v).update(g=None), "VIZ-RECORD-FIELD"),            # g not an int
    (lambda v: entry("adaptive", 3)(v).update(g=4), "VIZ-RECORD-FIELD"),               # g twice
    (lambda v: v.update(entries=[e for e in v["entries"] if e["model"] != "reset"]), "VIZ-RECORD-FIELD"),
    (lambda v: entry("adaptive", 3)(v).update(found=28302), "VIZ-RECORD-PAIR"),        # not the judge's count
    (lambda v: v["entries"].remove(entry("adaptive", 8)(v)), "VIZ-RECORD-PAIR"),       # not the judge's g
    (drop("n"), "VIZ-RECORD-FIELD"),
])
def test_viz_e2_part_refusals(edit, name):
    refused(name, F.e2_recovery, patched(json_edits={E2_PART: edit}))


SNAP3 = "    g 3 ( 768 windows) blocks 3-10: found 28301"


@pytest.mark.parametrize("edit", [
    lambda t: t.replace("predicted +0.16269", "foretold +0.16269"),                 # a snapshot line misshapen
    lambda t: t.replace("predicted +0.16269", "predicted 0.16269"),                 # no sign
    lambda t: t.replace(SNAP3, SNAP3 + " (0.28301), own 0.2851 -0.77 se INSIDE; best 0.5002 -69.06 se OUTSIDE; "
                        "gain over frozen +0.15962 se 0.00219 (z +73.0); predicted +0.16269 (-1.41 se)\n" + SNAP3),
    lambda t: t.replace("  the reset model,", "  the other model,"),                # no reset snapshots
    lambda t: t.replace("the reset model, g = labelled windows after the change / 256:",
                        "the reset model, g = labelled windows after the change / 128:"),   # two steps of g
    lambda t: t.replace("the adaptive model, g = labelled windows after the change / 256:",
                        "the adaptive model, g = windows / 256:"),                  # a header misshapen
    lambda t: t.replace("    one reading, at the tolerance's resolution: every snapshot from 2048",
                        "    another reading: every snapshot from 2048"),          # an unknown line in a section
])
def test_viz_e2_judge_refusals(edit):
    refused("VIZ-PARSE", F.e2_recovery, patched(text_edits={E2_JUDGE: edit}))


def gen(i, f):
    def g(v):
        f(v["generations"][i])
    return g


@pytest.mark.parametrize("edit", [
    gen(3, lambda g: g.update(parts_ns=dict(reversed(list(g["parts_ns"].items()))))),  # another key order
    gen(3, lambda g: g.update(sum_ns=g["sum_ns"] + 1)),                                 # parts do not add up
    gen(3, lambda g: g["parts_ns"].update(open=True)),
    gen(3, lambda g: g.update(generation=4)),                                           # a number twice
    gen(3, lambda g: g.pop("sum_ns")),
    lambda v: v.update(generations=[]),
    lambda v: [g["parts_ns"].update(extra=0) for g in v["generations"]],               # 11 parts, 10 colours
])
def test_viz_timed_refusals(edit):
    refused("VIZ-RECORD-FIELD", F.card_timed, patched(json_edits={TIMED: edit}))


D2 = "docs/studies/d2/scored-output.txt"


def gatr_wrong_unrecorded(t):
    """CI.GATR's wrong windows all without a record, its summary saying 0 of 0: consistent, and empty."""
    t = re.sub(r"(\| CI\.GATR \| wrong \| [^|]* \| [^|]* \| [^|]* \| )(yes|no)( \|)", r"\1-\3", t)
    return t.replace("| CI.GATR | 0 of 7 | 1 | 0 of 7 |", "| CI.GATR | 0 of 0 | 1 | 0 of 7 |")


@pytest.mark.parametrize("edit,name", [
    (lambda t: t.replace("| 2024-091 | CI.LOC | launch | 0 | 207 | 95 | yes |  |",
                         "| 2024-091 | CI.LOC | launch | 0 | 207 | 95 | maybe |  |"), "VIZ-PARSE"),
    (lambda t: t.replace("| 2024-091 | CI.LOC | launch | 0 | 207 | 95 | yes |  |",
                         "| 2024-091 | CI.LOC | launch | 0 | 207 | 95 | yes |"), "VIZ-PARSE"),
    (lambda t: t.replace("| CI.GATR | 0 of 7 | 1 | 0 of 7 | 1 | neither rejects |",
                         "| CI.GATR | none | 1 | 0 of 7 | 1 | neither rejects |"), "VIZ-PARSE"),
    (lambda t: re.sub(r"(?m)^\| CI\.", "| XX.", t), "VIZ-PARSE"),                            # no station rows
    (lambda t: t.replace("| 2024-091 | CI.LOC | launch | 0 | 207 | 95 | yes |",
                         "| 2024-091 | CI.LOC | launch | 0 | 207 | 95 | no |"), "VIZ-RECORD-PAIR"),
    (lambda t: t.replace("| CI.GATR | 0 of 7 | 1 | 0 of 7 |", "| CI.GATR | 0 of 7 | 1 | 1 of 7 |"),
     "VIZ-RECORD-PAIR"),
    (gatr_wrong_unrecorded, "VIZ-RECORD-FIELD"),
])
def test_viz_launch_refusals(edit, name):
    e = refused(name, F.launch_windows, patched(text_edits={D2: edit}))
    if edit is gatr_wrong_unrecorded:
        assert e.detail == "%s: CI.GATR has no wrong window with a record" % D2


@pytest.mark.parametrize("fn,edits,pulses_edit", [
    (F.card_timed, {TIMED: lambda v: v["generations"].reverse()}, None),             # ordered by number
    (F.e2_recovery, {E2_PART: lambda v: v["entries"].reverse()}, None),               # ordered by g
    (F.e0_efficiency, {CARD: lambda v: v["parts"].reverse()}, None),                  # paired by amplitude
    (F.pulses, {}, lambda v: [v.update({k: v.pop(k)}) for k in sorted(v, reverse=True)]),   # by name
])
def test_viz_a_figure_does_not_depend_on_the_records_order(fn, edits, pulses_edit):
    """The same records in another order make the same figure, byte for byte: the order drawn is the
    generator's rule (by number, by g, by amplitude, by name), not the file's."""
    assert fn(patched(json_edits=edits, pulses_edit=pulses_edit)) == fn(Reader(ROOT))


def test_viz_pulses_figure_refuses_more_pulses_than_colours():
    def eleven(v):
        for i in range(9):
            v["x%d" % i] = (0, 1)
    refused("VIZ-RECORD-FIELD", F.pulses, patched(pulses_edit=eleven))
    assert F.pulses(patched(pulses_edit=lambda v: [v.update({"x%d" % i: (0, 1)}) for i in range(8)]))


# ---------------------------------------------------------------- the command


COPIED = ["vectors/e0c/round1", "docs/studies/e0-card", "docs/studies/e1", "docs/studies/e2", "docs/studies/d2",
          "docs/studies/d3", "docs/figures"]


@pytest.fixture
def tree(tmp_path):
    for rel in COPIED:
        shutil.copytree(os.path.join(ROOT, *rel.split("/")), os.path.join(str(tmp_path), *rel.split("/")))
    os.makedirs(os.path.join(str(tmp_path), "spec"))
    shutil.copy2(os.path.join(ROOT, "spec", "constants.py"), os.path.join(str(tmp_path), "spec", "constants.py"))
    return str(tmp_path)


def fig_path(tree, name):
    return os.path.join(tree, "docs", "figures", name)


def test_viz_command_check_and_write(tree, capsys):
    assert main(["--check", "--root", tree]) == 0
    assert capsys.readouterr().out == "OK figures: 6 figure(s) equal what the records make\n"
    open(fig_path(tree, "pulses.svg"), "ab").write(b" ")
    assert main(["--check", "--root", tree]) == 1
    assert capsys.readouterr().out == "STALE docs/figures/pulses.svg: run python -m viz and commit it with its records\n"
    assert main(["--root", tree]) == 0
    assert capsys.readouterr().out.split("\n")[:6] == ["wrote docs/figures/%s" % n for n, _ in F.FIGURES]
    assert main(["--check", "--root", tree]) == 0
    os.remove(fig_path(tree, "pulses.svg"))
    assert main(["--check", "--root", tree]) == 1                  # a missing figure is stale
    capsys.readouterr()
    os.remove(os.path.join(tree, *CARD.split("/")))
    assert main(["--check", "--root", tree]) == 2
    assert capsys.readouterr().out == "REFUSED VIZ-RECORD-MISSING: %s\n" % CARD


def test_viz_an_unknown_figure_is_refused_and_nothing_is_written(tree, capsys):
    open(fig_path(tree, "extra.SVG"), "w").write("<svg/>")
    open(fig_path(tree, "e0-efficiency.svg"), "wb").write(b"")
    assert viz.unknown(tree) == ["extra.SVG"]
    refused("VIZ-UNKNOWN-FIGURE", viz.write, tree)
    assert open(fig_path(tree, "e0-efficiency.svg"), "rb").read() == b""
    assert main(["--root", tree]) == 2
    assert capsys.readouterr().out.startswith("REFUSED VIZ-UNKNOWN-FIGURE: docs/figures holds extra.SVG")
    assert main(["--check", "--root", tree]) == 1
    assert "STALE docs/figures/extra.SVG (not made by the registry)" in capsys.readouterr().out
    open(fig_path(tree, "notes.txt"), "w").write("x")             # only .svg files are the registry's business
    os.remove(fig_path(tree, "extra.SVG"))
    assert viz.unknown(tree) == []


def test_viz_python_dash_m_viz_check_on_the_tree():
    p = subprocess.run([sys.executable, "-m", "viz", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert (p.returncode, p.stdout) == (0, "OK figures: 6 figure(s) equal what the records make\n"), p.stderr


# ---------------------------------------------------------------- the imports

FORBIDDEN = ("model", "learn", "host", "rtl")


def foreign_imports(folder):
    """Each import in folder/*.py whose top name is neither the standard library, stats nor viz."""
    out = []
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".py"):
            continue
        tree = ast.parse(open(os.path.join(folder, name), encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                tops = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                tops = [(node.module or "").split(".")[0]] if node.level == 0 else ["viz"]
            else:
                continue
            for top in tops:
                if top not in sys.stdlib_module_names and top not in ("stats", "viz"):
                    out.append("%s:%d imports %s" % (name, node.lineno, top))
    return out


def test_viz_imports_only_the_standard_library_and_stats():
    assert foreign_imports(os.path.join(ROOT, "viz")) == []


@pytest.mark.parametrize("line", ["import model", "from learn import trainer", "import host.library as h",
                                  "from rtl import x", "import numpy"])
def test_viz_control_an_import_of_another_package_is_caught(tmp_path, line):
    copy = str(tmp_path / "viz")
    shutil.copytree(os.path.join(ROOT, "viz"), copy, ignore=shutil.ignore_patterns("__pycache__"))
    open(os.path.join(copy, "figures.py"), "a").write("\n" + line + "\n")
    found = foreign_imports(copy)
    assert len(found) == 1 and found[0].startswith("figures.py:")


def test_viz_build_imports_nothing_of_model_learn_host_or_rtl():
    code = ("import sys, viz; viz.build(%r); "
            "print(sorted(m for m in sys.modules if m.split('.')[0] in %r))" % (ROOT, FORBIDDEN))
    p = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert (p.returncode, p.stdout) == (0, "[]\n"), p.stderr


# ---------------------------------------------------------------- the colours


def luminance(hex_colour):
    """WCAG 2's relative luminance of an sRGB colour written #rrggbb."""
    def lin(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_viz_contrast_worked_by_hand():
    """White on black is (1 + 0.05) / (0 + 0.05) = 21; a colour on itself is 1."""
    assert contrast("#ffffff", "#000000") == pytest.approx(21.0)
    assert contrast("#2f6fd0", "#2f6fd0") == 1.0


@pytest.mark.parametrize("theme", [svg.LIGHT, svg.DARK])
def test_viz_every_colour_reads_on_both_backgrounds(theme):
    for name, colour in svg.SERIES.items():
        assert contrast(colour, theme["bg"]) >= 3.0, (name, colour, theme["bg"])
    assert contrast(theme["ink"], theme["bg"]) >= 4.5
    assert contrast(theme["muted"], theme["bg"]) >= 4.5
    assert contrast(theme["grid"], theme["bg"]) >= 1.3


def test_viz_figures_use_no_colour_but_the_checked_ones():
    allowed = set(svg.SERIES.values()) | set(svg.LIGHT.values()) | set(svg.DARK.values())
    for name, _ in F.FIGURES:
        text = open(fig_path(ROOT, name), encoding="ascii").read()
        used = set(re.findall(r"#[0-9a-fA-F]{6}\b", text))
        assert used and used <= allowed, (name, used - allowed)
        style = re.search(r"<style>(.*)</style>", text).group(1)
        assert style.startswith("@media (prefers-color-scheme: dark){")
        for v in svg.DARK.values():
            assert v in style
        assert 'class="bg" fill="%s"' % svg.LIGHT["bg"] in text
        assert len(re.findall(r'<text [^>]*class="(ink|muted)"', text)) == len(re.findall(r"<text ", text))

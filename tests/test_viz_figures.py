"""Parcel VIZ: the committed figures are the records' generated copies, and show the records' numbers.

What these hold, and the answer each expects:

1. Every figure `viz.build` makes from the committed records equals the committed
   file under docs/figures/, byte for byte; and that folder holds exactly the
   registry's .svg files.
2. A figure's numbers are the record's. Each figure is read back as XML here, and
   every value it carries (`data-x`, `data-y`, ...) is compared, exactly, with what
   this file reads from the record itself with `json`; every marker's, line's and
   bar's position is compared with this file's own map of those values onto the
   panel's axes, to 0.006 px (the figure rounds to 0.01 px). The theory curves are
   recomputed here from the record's parameters and `stats/`, and the D8 figures of
   E0 and E1 are held to the records and to the judges' printed values.
3. Each figure's source lines name exactly the files it read, with the SHA-256 of
   their bytes worked here; the pulses' line the SHA-256 of PULSES as canonical JSON.
4. The named controls of the brief, each on a copy: a figure edited by hand; a
   record changed by one count; a generator patched to type a count; a CR byte and
   a personal path in a figure, refused by the gate's own `eol` and `paths` stages.

Nothing here imports `model/`. The checks below read the records independently of
`viz`: they share with it only the file names and the SVG's attribute names.
"""
import ast
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from fractions import Fraction

import pytest

import viz
from viz.records import Reader
from stats.theory import pd_matched
from stats.tolerance import tolerance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NS = "{http://www.w3.org/2000/svg}"
PX = 0.006
NAMES = ["e0-efficiency.svg", "e1-learning.svg", "e2-recovery.svg", "card-timed.svg", "pulses.svg"]
CARD = "docs/studies/e0-card/card-e0.json"
E2_PART = "docs/studies/e2/e2-part.json"
E2_JUDGE = "docs/studies/e2/judge-output.txt"
E1_JUDGE = "docs/studies/e1/judge-output.txt"
TIMED = "docs/studies/e0-card/timed.json"


# ---------------------------------------------------------------- reading, independently of viz


def path(root, rel):
    return os.path.join(root, *rel.split("/"))


def load(root, rel):
    with open(path(root, rel), "rb") as f:
        return json.loads(f.read().decode("utf-8"))


def sha(root, rel):
    with open(path(root, rel), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def numbered(root, folder, pattern):
    out = []
    for name in os.listdir(path(root, folder)):
        m = re.fullmatch(pattern, name)
        if m:
            out.append((int(m.group(1)), folder + "/" + name))
    return [rel for _, rel in sorted(out)]


def pulses_of(root):
    tree = ast.parse(open(path(root, "spec/constants.py"), encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == "PULSES":
            return ast.literal_eval(node.value)
    raise AssertionError("no PULSES")


def pulses_line(root):
    canon = json.dumps(pulses_of(root), sort_keys=True, separators=(",", ":"))
    return ("source: spec/constants.py, PULSES: sha256 of its value as canonical JSON  sha256 %s"
            % hashlib.sha256(canon.encode("ascii")).hexdigest())


def file_line(root, rel):
    return "source: %s  sha256 %s" % (rel, sha(root, rel))


def value(s):
    if "/" in s:
        return Fraction(s)
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    return float(s)


class Axes:
    """This file's own map from values to pixels, read from a panel's attributes."""

    def __init__(self, g):
        self.left, self.top = float(g.get("data-left")), float(g.get("data-top"))
        self.width, self.height = float(g.get("data-width")), float(g.get("data-height"))
        self.xs, self.ys = g.get("data-x-scale"), g.get("data-y-scale")
        self.xlo, self.xhi = g.get("data-x-lo"), g.get("data-x-hi")
        self.ylo, self.yhi = g.get("data-y-lo"), g.get("data-y-hi")

    @staticmethod
    def frac(v, scale, lo, hi):
        if scale == "linear":
            lo, hi = Fraction(lo), Fraction(hi)
            return float((Fraction(v) - lo) / (hi - lo)) if not isinstance(v, float) \
                else (v - float(lo)) / float(hi - lo)
        if scale == "log10":
            return (math.log10(v) - math.log10(int(lo))) / (math.log10(int(hi)) - math.log10(int(lo)))
        if scale == "category":
            return (v + 0.5) / int(hi)
        raise AssertionError(scale)

    def px(self, v):
        return self.left + self.frac(v, self.xs, self.xlo, self.xhi) * self.width

    def py(self, v):
        return self.top + self.height - self.frac(v, self.ys, self.ylo, self.yhi) * self.height


class Fig:
    def __init__(self, data):
        self.root = ET.fromstring(data)
        self.panels = {g.get("data-panel"): g for g in self.root.iter(NS + "g") if g.get("class") == "panel"}
        self.sources = [t.text for t in self.root.iter(NS + "text") if (t.text or "").startswith("source: ")]

    def series(self, panel, name):
        return [e for e in self.panels[panel] if e.get("data-series") == name]

    def axes(self, panel):
        return Axes(self.panels[panel])


def centre(e):
    if e.tag == NS + "circle":
        return float(e.get("cx")), float(e.get("cy"))
    return float(e.get("data-cx")), float(e.get("data-cy"))


def check_points(fig, panel, name, expected, out, extra=()):
    """expected: [(data-x text, data-y text)]; positions by this file's map."""
    els = fig.series(panel, name)
    got = [(e.get("data-x"), e.get("data-y")) for e in els]
    if got != expected:
        out.append("%s/%s: values %r, the record's %r" % (panel, name, got, expected))
        return
    ax = fig.axes(panel)
    for e, (x, y) in zip(els, expected):
        cx, cy = centre(e)
        if abs(cx - ax.px(value(x))) > PX or abs(cy - ax.py(value(y))) > PX:
            out.append("%s/%s: the point at %s, %s is drawn at %.2f, %.2f, not %.2f, %.2f"
                       % (panel, name, x, y, cx, cy, ax.px(value(x)), ax.py(value(y))))


def check_polyline(fig, panel, name, values, out):
    els = fig.series(panel, name)
    if len(els) != 1:
        out.append("%s/%s: %d polylines" % (panel, name, len(els)))
        return
    pts = [tuple(float(c) for c in p.split(",")) for p in els[0].get("points").split()]
    if len(pts) != len(values):
        out.append("%s/%s: %d points, %d expected" % (panel, name, len(pts), len(values)))
        return
    ax = fig.axes(panel)
    for (gx, gy), (x, y) in zip(pts, values):
        if abs(gx - ax.px(x)) > PX or abs(gy - ax.py(y)) > PX:
            out.append("%s/%s: (%r, %r) drawn at %.2f, %.2f" % (panel, name, x, y, gx, gy))
            return


def check_hline(fig, panel, name, y, out):
    els = fig.series(panel, name)
    if len(els) != 1 or els[0].get("data-y") != y:
        out.append("%s/%s: %r, the record's %r" % (panel, name, [e.get("data-y") for e in els], y))
        return
    if abs(float(els[0].get("y1")) - fig.axes(panel).py(value(y))) > PX:
        out.append("%s/%s: drawn at %s" % (panel, name, els[0].get("y1")))


def check_sources(fig, lines, out):
    if fig.sources != lines:
        out.append("sources %r, expected %r" % (fig.sources, lines))


# ---------------------------------------------------------------- what each figure must show


def e0_pairs(root):
    soft = [(rel, load(root, rel)) for rel in numbered(root, "vectors/e0c/round1", r"part(\d+)\.json")]
    card = load(root, CARD)["parts"]
    return [(rel, s, [c for c in card if c["amplitude"] == s["amplitude"]][0]) for rel, s in soft]


def e0_findings(data, root):
    fig, out = Fig(data), []
    pairs = e0_pairs(root)
    amp = lambda p: "%d/%d" % tuple(p["amplitude"])  # noqa: E731
    check_points(fig, "main", "software", [(amp(s), "%d/%d" % (s["found"], s["n"])) for _, s, _ in pairs], out)
    check_points(fig, "main", "card", [(amp(c), "%d/%d" % (c["found"], c["n"])) for _, _, c in pairs], out)
    check_points(fig, "residual", "software-offset",
                 [(amp(s), repr(s["found"] / s["n"] - s["expected"])) for _, s, _ in pairs], out)
    check_points(fig, "residual", "card-offset",
                 [(amp(c), repr(c["found"] / c["n"] - c["expected"])) for _, _, c in pairs], out)
    for name, rec in (("software-offset", 1), ("card-offset", 2)):
        got = [e.get("data-expected") for e in fig.series("residual", name)]
        if got != [repr(p[rec]["expected"]) for p in pairs]:
            out.append("residual/%s: D8 figures %r" % (name, got))
    bars = [(e.get("data-x"), e.get("data-lo"), e.get("data-hi")) for e in fig.series("residual", "d8-tolerance")]
    want = []
    for _, s, _ in pairs:
        t = tolerance(s["pfa"], s["d"], s["n"])["tolerance"]
        want.append((amp(s), repr(-t), repr(t)))
    if bars != want:
        out.append("residual/d8-tolerance: %r, expected %r" % (bars, want))
    check_points(fig, "strip", "card-minus-software",
                 [(amp(s), str(c["found"] - s["found"])) for _, s, c in pairs], out)
    e0 = pulses_of(root)["e0"]
    norm = math.sqrt(sum(x * x for x in e0))
    s0 = pairs[0][1]
    sigma = s0["sigma"][0] / s0["sigma"][1]
    top = max(Fraction(*s["amplitude"]) for _, s, _ in pairs)
    curve = [(k / 100, pd_matched(s0["pfa"], (k / 100) * norm / sigma)) for k in range(math.ceil(top * 100) + 1)]
    check_polyline(fig, "main", "d8-curve", curve, out)
    check_sources(fig, [file_line(root, rel) for rel, _, _ in pairs] + [file_line(root, CARD), pulses_line(root)], out)
    return out


def e1_parts(root):
    return [(rel, load(root, rel)) for rel in numbered(root, "docs/studies/e1", r"c(\d+)\.json")]


def e1_findings(data, root):
    fig, out = Fig(data), []
    parts = e1_parts(root)
    p0 = parts[0][1]
    pfa = (p0["k"] + 1) / (p0["m"] + 1)
    check_points(fig, "main", "learned",
                 [(str(p["labelled_windows"]), "%d/%d" % (p["found"], p["n"])) for _, p in parts], out)
    check_points(fig, "main", "matched",
                 [(str(p["labelled_windows"]), "%d/%d" % (p["base_found"], p["n"])) for _, p in parts], out)
    check_points(fig, "main", "own-d8",
                 [(str(p["labelled_windows"]), repr(pd_matched(pfa, p["d_learned"]))) for _, p in parts], out)
    figure = pd_matched(pfa, p0["d_matched"])
    tol = tolerance(pfa, p0["d_matched"], p0["n"], p0["m"])["tolerance"]
    check_hline(fig, "main", "e0-figure", repr(figure), out)
    band = fig.series("main", "e0-tolerance")
    if [(e.get("data-lo"), e.get("data-hi")) for e in band] != [(repr(figure - tol), repr(figure + tol))]:
        out.append("main/e0-tolerance: %r" % [(e.get("data-lo"), e.get("data-hi")) for e in band])
    else:
        ax = fig.axes("main")
        if abs(float(band[0].get("y")) - ax.py(figure + tol)) > PX or \
                abs(float(band[0].get("y")) + float(band[0].get("height")) - ax.py(figure - tol)) > 2 * PX:
            out.append("main/e0-tolerance: drawn at the wrong height")
    check_polyline(fig, "main", "learned-line",
                   [(p["labelled_windows"], Fraction(p["found"], p["n"])) for _, p in parts], out)
    check_sources(fig, [file_line(root, rel) for rel, _ in parts], out)
    return out


SNAP = re.compile(r"    g (\d+) \( *\d+ windows\) blocks \S+: found (\d+) .* predicted ([+-]\d\.\d{5}) \(.*")


def e2_judge(root):
    out, section = {}, None
    for line in open(path(root, E2_JUDGE), encoding="utf-8").read().split("\n"):
        if line.startswith("  the adaptive model,"):
            section = "adaptive"
        elif line.startswith("  the reset model,"):
            section = "reset"
        elif not line.startswith("    "):
            section = None
        m = SNAP.fullmatch(line)
        if m and section:
            out.setdefault(section, []).append((int(m.group(1)), int(m.group(2)), m.group(3)))
    return out


def e2_findings(data, root):
    fig, out = Fig(data), []
    part = load(root, E2_PART)
    n = part["n"]
    by = {}
    for e in part["entries"]:
        by.setdefault(e["model"], []).append(e)
    frozen, best = by["frozen"][0], by["e1"][0]
    check_hline(fig, "main", "frozen", "%d/%d" % (frozen["found"], n), out)
    check_hline(fig, "main", "e1-filter", "%d/%d" % (best["found"], n), out)
    judge = e2_judge(root)
    for model in ("adaptive", "reset"):
        rows = sorted(by[model], key=lambda e: e["g"])
        check_points(fig, "main", model, [(str(e["g"]), "%d/%d" % (e["found"], n)) for e in rows], out)
        preds = sorted(judge[model])
        check_points(fig, "main", model + "-predicted",
                     [(str(g), repr(frozen["found"] / n + float(p))) for g, _, p in preds], out)
        got = [e.get("data-predicted-gain") for e in fig.series("main", model + "-predicted")]
        if got != [p for _, _, p in preds]:
            out.append("main/%s-predicted: gains %r, the judge's %r" % (model, got, [p for _, _, p in preds]))
        check_polyline(fig, "main", model + "-line", [(e["g"], Fraction(e["found"], n)) for e in rows], out)
        check_polyline(fig, "main", model + "-predicted-line",
                       [(g, frozen["found"] / n + float(p)) for g, _, p in preds], out)
    step = re.findall(r"the adaptive model, g = labelled windows after the change / (\d+):",
                      open(path(root, E2_JUDGE), encoding="utf-8").read())
    if [t for t in texts(fig) if "(labelled windows after the change / %s)" % step[0] in t] == []:
        out.append("the x axis does not name the judge's step of g, %s" % step)
    check_sources(fig, [file_line(root, E2_PART), file_line(root, E2_JUDGE)], out)
    return out


def texts(fig):
    return [t.text for t in fig.root.iter(NS + "text")]


def timed_findings(data, root):
    fig, out = Fig(data), []
    gens = sorted(load(root, TIMED)["generations"], key=lambda g: g["generation"])
    bars = [e for e in fig.panels["main"] if e.get("data-ns") is not None]
    want = []
    for slot, g in enumerate(gens):
        below = 0
        for k, v in g["parts_ns"].items():
            want.append((k, str(slot), "%d/1000000" % below, "%d/1000000" % (below + v), str(v),
                         str(g["generation"])))
            below += v
    got = [(e.get("data-series"), e.get("data-x"), e.get("data-y0"), e.get("data-y1"), e.get("data-ns"),
            e.get("data-generation")) for e in bars]
    if got != want:
        out.append("main bars: %d differ from the record's" % sum(1 for a, b in zip(got, want) if a != b)
                   if len(got) == len(want) else "main bars: %d, the record's %d" % (len(got), len(want)))
        return out
    ax = fig.axes("main")
    for e, (_, slot, y0, y1, _, _) in zip(bars, want):
        x, y, w, h = (float(e.get(a)) for a in ("x", "y", "width", "height"))
        if abs(x + w / 2 - ax.px(int(slot))) > PX or abs(y - ax.py(value(y1))) > PX \
                or abs(y + h - ax.py(value(y0))) > 2 * PX:
            out.append("main bar %s %s: drawn at the wrong place" % (slot, e.get("data-series")))
    check_sources(fig, [file_line(root, TIMED)], out)
    return out


def pulses_findings(data, root):
    fig, out = Fig(data), []
    p = pulses_of(root)
    for name in sorted(p):
        check_points(fig, "main", name, [(str(i), str(s)) for i, s in enumerate(p[name])], out)
        check_polyline(fig, "main", name + "-line", list(enumerate(p[name])), out)
    check_sources(fig, [pulses_line(root)], out)
    return out


FINDINGS = {"e0-efficiency.svg": e0_findings, "e1-learning.svg": e1_findings, "e2-recovery.svg": e2_findings,
            "card-timed.svg": timed_findings, "pulses.svg": pulses_findings}


def committed(root, name):
    with open(path(root, "docs/figures/" + name), "rb") as f:
        return f.read()


# ---------------------------------------------------------------- 1. generated copies


def test_viz_registry_is_the_five_figures():
    assert [n for n, _ in viz.figures.FIGURES] == NAMES


def test_viz_folder_holds_the_registry_and_nothing_else():
    held = sorted(n for n in os.listdir(path(ROOT, "docs/figures")) if n.lower().endswith(".svg"))
    assert held == sorted(NAMES)
    assert viz.unknown(ROOT) == []


@pytest.mark.parametrize("name", NAMES)
def test_viz_committed_figure_is_what_the_records_make(name):
    made = dict(viz.build(ROOT))[name].encode("ascii")
    assert committed(ROOT, name) == made, "docs/figures/%s is stale: run python -m viz" % name


def test_viz_stale_names_nothing_on_the_tree():
    assert viz.stale(ROOT) == []


def test_viz_two_builds_are_the_same_bytes():
    assert viz.build(ROOT) == viz.build(ROOT)


@pytest.mark.parametrize("name", NAMES)
def test_viz_figure_is_ascii_lf_with_one_final_newline(name):
    data = committed(ROOT, name)
    assert bytes([13]) not in data
    assert all(32 <= b < 127 or b == 10 for b in data)
    assert data.endswith(b"</svg>\n") and not data.endswith(b"\n\n")
    assert not re.search(rb"-0\.00\b", data)


# ---------------------------------------------------------------- 2 and 3. the records' numbers


@pytest.mark.parametrize("name", NAMES)
def test_viz_figure_shows_the_records_numbers(name):
    assert FINDINGS[name](committed(ROOT, name), ROOT) == []


def test_viz_e0_d8_is_each_parts_own_expected():
    """The lead's ruling: stats.theory.pd_matched(pfa, d) equals each E0 part's `expected`, exactly."""
    rows = [load(ROOT, rel) for rel in numbered(ROOT, "vectors/e0c/round1", r"part(\d+)\.json")]
    rows += load(ROOT, CARD)["parts"]
    assert len(rows) == 10
    for p in rows:
        assert pd_matched(p["pfa"], p["d"]) == p["expected"]


@pytest.mark.parametrize("name,label", [("e0-efficiency.svg", "D8's tolerance about 0, %g se"),
                                        ("e1-learning.svg", "its tolerance, %g se (stats.tolerance)")])
def test_viz_legend_names_the_statistics_own_z(name, label):
    from stats.tolerance import Z_GATE
    assert label % Z_GATE in texts(Fig(committed(ROOT, name)))
    assert "%g" % Z_GATE == "4"


def test_viz_e0_card_counts_equal_softwares():
    """What the lowest panel draws as a row of zeros: the card's count is round 1's at all five amplitudes."""
    pairs = e0_pairs(ROOT)
    assert len(pairs) == 5
    assert [c["found"] - s["found"] for _, s, c in pairs] == [0, 0, 0, 0, 0]


def test_viz_e0_curve_d_and_the_parts_d_differ_in_the_seventh_figure():
    """Limit 5: at amplitude 1/2 the part's d is 1.1634366..., the unrounded pulse's 1.1634321...."""
    from stats.theory import deflection
    p = load(ROOT, "vectors/e0c/round1/part0.json")
    assert Fraction(*p["amplitude"]) == Fraction(1, 2)
    e0 = pulses_of(ROOT)["e0"]
    curve_d = deflection(e0, [0.5 * x for x in e0], p["sigma"][0] / p["sigma"][1])
    a, b = "%.12f" % curve_d, "%.12f" % p["d"]
    assert a[:7] == b[:7] == "1.16343" and a[7] != b[7]


def test_viz_e0_tolerances_are_the_card_judges():
    """The bars are the tolerances the card's judge printed: 0.00293, 0.00402, 0.00447, 0.00402, 0.00293."""
    printed = re.findall(r"tolerance (0\.\d{5}), INSIDE",
                         open(path(ROOT, "docs/studies/e0-card/compare-output.txt"), encoding="utf-8").read())
    mine = ["%.5f" % tolerance(p["pfa"], p["d"], p["n"])["tolerance"] for p in load(ROOT, CARD)["parts"]]
    assert printed == mine == ["0.00293", "0.00402", "0.00447", "0.00402", "0.00293"]


E1_ROW = re.compile(r"  (\d+) +(\d+) +(\d+) +([\d.]+) +(\d+) of (\d+) +([\d.]+) +([\d.]+) [+-][\d.]+ se \w+ "
                    r"([\d.]+) [+-][\d.]+ se \w+ ([\d.]+)")


def test_viz_e1_theory_figures_are_the_judges():
    """At Pfa (k + 1) / (m + 1): own D8 0.1907 0.3840 0.4458 0.4923 0.4976 0.4997, E0's 0.5003, tolerance 0.01258."""
    rows = [m.groups() for m in map(E1_ROW.fullmatch, open(path(ROOT, E1_JUDGE), encoding="utf-8").read().split("\n"))
            if m]
    parts = [p for _, p in e1_parts(ROOT)]
    assert len(rows) == len(parts) == 6
    for row, p in zip(rows, parts):
        pfa = (p["k"] + 1) / (p["m"] + 1)
        assert int(row[1]) == p["labelled_windows"] and int(row[4]) == p["found"]
        assert "%.4f" % pd_matched(pfa, p["d_learned"]) == row[7]
        assert "%.4f" % pd_matched(pfa, p["d_matched"]) == row[8] == "0.5003"
        assert "%.5f" % tolerance(pfa, p["d_matched"], p["n"], p["m"])["tolerance"] == row[9] == "0.01258"
    assert [r[7] for r in rows] == ["0.1907", "0.3840", "0.4458", "0.4923", "0.4976", "0.4997"]


def test_viz_e1_record_pfa_alone_would_not_give_the_judges_figure():
    """Why the figure takes (k + 1) / (m + 1): at the record's pfa, E0's figure is 0.5002, not the judge's 0.5003."""
    p = e1_parts(ROOT)[0][1]
    assert "%.4f" % pd_matched(p["pfa"], p["d_matched"]) == "0.5002"


def test_viz_e2_judge_output_is_this_parts():
    """Each snapshot the judge printed has the part's count, and the gain (found - frozen) / n it printed."""
    part = load(ROOT, E2_PART)
    frozen = [e for e in part["entries"] if e["model"] == "frozen"][0]["found"]
    text = open(path(ROOT, E2_JUDGE), encoding="utf-8").read()
    judge = e2_judge(ROOT)
    assert sorted(judge) == ["adaptive", "reset"] and all(len(v) == 9 for v in judge.values())
    for model, rows in judge.items():
        for g, found, _ in rows:
            entry = [e for e in part["entries"] if e["model"] == model and e["g"] == g]
            assert len(entry) == 1 and entry[0]["found"] == found
            assert ("found %d (" % found) in text
            assert ("gain over frozen %+.5f" % ((found - frozen) / part["n"])) in text


def test_viz_timed_bars_add_to_each_generations_sum():
    for g in load(ROOT, TIMED)["generations"]:
        assert sum(g["parts_ns"].values()) == g["sum_ns"]


# ---------------------------------------------------------------- 4. the named controls, on copies

COPIED = ["vectors/e0c/round1", "docs/studies/e0-card", "docs/studies/e1", "docs/studies/e2", "docs/figures"]


@pytest.fixture
def tree(tmp_path):
    for rel in COPIED:
        shutil.copytree(path(ROOT, rel), path(str(tmp_path), rel))
    os.makedirs(path(str(tmp_path), "spec"))
    shutil.copy2(path(ROOT, "spec/constants.py"), path(str(tmp_path), "spec/constants.py"))
    return str(tmp_path)


def test_viz_copy_is_clean_before_any_plant(tree):
    """The controls' baseline: on an untouched copy nothing is stale and nothing is found."""
    assert viz.stale(tree) == []
    for name in NAMES:
        assert FINDINGS[name](committed(tree, name), tree) == []


def edit_figure(tree, name, old, new):
    p = path(tree, "docs/figures/" + name)
    data = open(p, "rb").read()
    assert data.count(old) >= 1
    open(p, "wb").write(data.replace(old, new, 1))


@pytest.mark.parametrize("old,new", [
    (b'data-y="24442/200000"', b'data-y="24443/200000"'),      # a value the figure carries
    (b'data-series="software" data-x="1/2"', b'data-series="software" data-x="3/4"'),
])
def test_viz_control_a_figure_edited_by_hand_is_stale(tree, old, new):
    edit_figure(tree, "e0-efficiency.svg", old, new)
    assert viz.stale(tree) == ["e0-efficiency.svg"]
    found = e0_findings(committed(tree, "e0-efficiency.svg"), tree)
    print(found)
    assert found and "main/software" in found[0]


def test_viz_control_a_coordinate_edited_by_hand_is_stale(tree):
    data = committed(tree, "e0-efficiency.svg")
    m = re.search(rb'<circle cx="(\d+\.\d\d)"( cy="[\d.]+" data-series="software")', data)
    old = m.group(0)
    edit_figure(tree, "e0-efficiency.svg", old, b'<circle cx="%.2f"' % (float(m.group(1)) + 1) + m.group(2))
    assert viz.stale(tree) == ["e0-efficiency.svg"]
    found = e0_findings(committed(tree, "e0-efficiency.svg"), tree)
    print(found)
    assert found and "drawn at" in found[0]


def change_card_count(tree, old=99743, new=99744):
    p = path(tree, CARD)
    text = open(p, "rb").read()
    assert text.count(b'"found": %d,' % old) == 1
    open(p, "wb").write(text.replace(b'"found": %d,' % old, b'"found": %d,' % new))


def test_viz_control_a_record_changed_by_one_count_makes_another_figure(tree):
    before = dict(viz.build(tree))["e0-efficiency.svg"]
    change_card_count(tree)
    after = dict(viz.build(tree))["e0-efficiency.svg"]
    assert after != before
    assert viz.stale(tree) == ["e0-efficiency.svg"]
    found = e0_findings(committed(tree, "e0-efficiency.svg"), tree)
    print(found)
    assert any("main/card" in f for f in found)
    assert e0_findings(after.encode("ascii"), tree) == []


class TypedCount(Reader):
    """A generator patched to show a typed constant for the card's count at amplitude 1/1."""

    def json(self, rel):
        v = super().json(rel)
        if rel == CARD:
            v["parts"][2]["found"] = 99743
        return v


def test_viz_control_a_generator_typing_a_count_is_caught(tree):
    change_card_count(tree)
    honest = dict(viz.build(tree))["e0-efficiency.svg"]
    typed = dict(viz.build(tree, reader=TypedCount))["e0-efficiency.svg"]
    assert typed != honest
    found = e0_findings(typed.encode("ascii"), tree)
    print(found)
    assert any("main/card" in f and "99743/200000" in f and "99744/200000" in f for f in found)
    assert e0_findings(honest.encode("ascii"), tree) == []
    # and on the unchanged records the typed generator is not told apart: that is why the
    # control changes the record first (README, limit 4)
    assert viz.stale(ROOT, reader=TypedCount) == []


def check_tree(kind, root):
    p = subprocess.run([sys.executable, path(ROOT, "tools/check_tree.py"), kind, "--root", root],
                       capture_output=True, text=True)
    return p.returncode, p.stdout


@pytest.fixture
def repo(tmp_path):
    root = str(tmp_path / "copy")
    os.makedirs(path(root, "docs/figures"))
    subprocess.run(["git", "init", "-q", root], check=True, capture_output=True)
    shutil.copy2(path(ROOT, "docs/figures/e0-efficiency.svg"), path(root, "docs/figures/e0-efficiency.svg"))
    return root


def test_viz_control_eol_and_paths_pass_a_clean_figure(repo):
    for kind in ("eol", "paths"):
        code, out = check_tree(kind, repo)
        print(out)
        assert code == 0 and out.startswith("OK %s: " % kind) and " 1 committable" in out


def test_viz_control_a_cr_byte_in_a_figure_is_refused_by_eol(repo):
    p = path(repo, "docs/figures/e0-efficiency.svg")
    data = open(p, "rb").read()
    open(p, "wb").write(data.replace(b"\n", bytes([13, 10]), 1))
    code, out = check_tree("eol", repo)
    print(out)
    assert code == 1
    assert "FINDING eol docs/figures/e0-efficiency.svg:1: CR byte (1 in the file)" in out


def test_viz_control_a_personal_path_in_a_figure_is_refused_by_paths(repo):
    p = path(repo, "docs/figures/e0-efficiency.svg")
    lines = open(p, "rb").read().decode("ascii").split("\n")
    # assembled from pieces so this file does not hold the spelling it plants
    personal = "C:" + "\\" + "Us" + "ers" + "\\" + "someone" + "\\" + "work"
    lines.insert(len(lines) - 2, '<text x="0" y="0">%s</text>' % personal)
    open(p, "wb").write("\n".join(lines).encode("ascii"))
    code, out = check_tree("paths", repo)
    print(out)
    assert code == 1
    assert "FINDING paths docs/figures/e0-efficiency.svg:%d: personal path (windows-home)" % (len(lines) - 2) in out

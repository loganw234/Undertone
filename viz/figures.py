"""The figures, one function each, and the registry `FIGURES`.

A figure function takes a `viz.records.Reader` rooted at a tree and returns the
SVG text. Every number it draws is read from a committed record through that
reader, or is `stats/`' formula evaluated at parameters read from a record. No
figure types a number that a record holds. What is typed is presentation: the
pixel layout, the colours, the theory curve's sampling step (`CURVE_STEP`), and
the words.

To add a figure: write a function here, add a line to `FIGURES`, run
`python -m viz`, and commit the figure with the record (docs/figures/README.md,
"Adding a figure").
"""
import math
import re
from fractions import Fraction

from stats.theory import deflection, pd_matched
from stats.tolerance import tolerance

from viz.errors import VizRefusal
from viz.records import field, fraction_pair
from viz.svg import (SERIES, Figure, CategoryAxis, LinearAxis, Log10Axis, Panel, Ratio)

CURVE_STEP = Fraction(1, 100)   # the D8 curve is sampled at every hundredth of the amplitude
PLOT_LEFT = 84
PLOT_WIDTH = 440
LEGEND_X = PLOT_LEFT + PLOT_WIDTH + 24
WIDTH = 820

E0_SOFTWARE = "vectors/e0c/round1"
E0_CARD = "docs/studies/e0-card/card-e0.json"
E1_FOLDER = "docs/studies/e1"
E2_PART = "docs/studies/e2/e2-part.json"
E2_JUDGE = "docs/studies/e2/judge-output.txt"
TIMED = "docs/studies/e0-card/timed.json"


def agree(rows, key, what):
    """The one value `key` takes across rows, or VIZ-RECORD-PAIR."""
    values = []
    for where, row in rows:
        v = row[key]
        if v not in values:
            values.append(v)
    if len(values) != 1:
        raise VizRefusal("VIZ-RECORD-PAIR", "%s disagree on %s: %r" % (what, key, values))
    return values[0]


def sigma_text(sigma):
    return "%d/%d" % sigma


# ---------------------------------------------------------------- stage E0


def _e0_part(part, where):
    return {
        "where": where,
        "amplitude": fraction_pair(part, "amplitude", where),
        "n": field(part, "n", "int", where),
        "found": field(part, "found", "int", where),
        "d": field(part, "d", "number", where),
        "pfa": field(part, "pfa", "number", where),
        "sigma": fraction_pair(part, "sigma", where),
        "expected": field(part, "expected", "number", where),
        "profile": field(part, "profile", "str", where),
    }


PAIRED = ("n", "d", "pfa", "sigma", "expected", "profile")


def e0_efficiency(r):
    soft = [_e0_part(r.json(rel), rel) for rel in r.glob(E0_SOFTWARE, r"part(\d+)\.json")]
    card_rec = r.json(E0_CARD)
    card_parts = field(card_rec, "parts", "list", E0_CARD)
    card = [_e0_part(p, "%s parts[%d]" % (E0_CARD, i)) for i, p in enumerate(card_parts)]
    pulses = r.pulses()
    if "e0" not in pulses:
        raise VizRefusal("VIZ-RECORD-FIELD", "PULSES has no e0")
    e0 = pulses["e0"]

    pairs = []
    for s in soft:
        mates = [c for c in card if c["amplitude"] == s["amplitude"]]
        if len(mates) != 1:
            raise VizRefusal("VIZ-RECORD-PAIR", "%s: %d card parts at amplitude %d/%d, not 1"
                             % (s["where"], len(mates), s["amplitude"][0], s["amplitude"][1]))
        c = mates[0]
        for key in PAIRED:
            if c[key] != s[key]:
                raise VizRefusal("VIZ-RECORD-PAIR", "%s and %s differ in %s: %r and %r"
                                 % (s["where"], c["where"], key, s[key], c[key]))
        pairs.append((s, c))
    if len(card) != len(soft):
        raise VizRefusal("VIZ-RECORD-PAIR", "%d card parts and %d software parts" % (len(card), len(soft)))
    rows = [(s["where"], s) for s in soft]
    sigma = agree(rows, "sigma", "the E0 parts")
    pfa = agree(rows, "pfa", "the E0 parts")
    profile = agree(rows, "profile", "the E0 parts")
    sigma_f = sigma[0] / sigma[1]

    amps = [Ratio(*s["amplitude"]) for s, _ in pairs]
    top = max(Fraction(*s["amplitude"]) for s, _ in pairs)
    steps = math.ceil(top / CURVE_STEP)
    curve = []
    for k in range(steps + 1):
        a = k * CURVE_STEP
        d = deflection(e0, [float(a) * x for x in e0], sigma_f)
        curve.append((float(a), pd_matched(pfa, d)))
    judged = [tolerance(s["pfa"], s["d"], s["n"]) for s, _ in pairs]
    tols = [t["tolerance"] for t in judged]
    z = agree([("stats.tolerance", t) for t in judged], "z", "the tolerances")
    soft_off = [float(Ratio(s["found"], s["n"])) - s["expected"] for s, _ in pairs]
    card_off = [float(Ratio(c["found"], c["n"])) - c["expected"] for _, c in pairs]
    diffs = [c["found"] - s["found"] for s, c in pairs]

    yvals = [Ratio(s["found"], s["n"]) for s, _ in pairs] + [Ratio(c["found"], c["n"]) for _, c in pairs]
    yvals += [y for _, y in curve]
    fig = Figure("e0-efficiency", "Stage E0: efficiency against amplitude, software and card",
                 ["The matched filter for e0; profile %s, sigma %s, Pfa %s; each point one part of %s injections"
                  % (profile, sigma_text(sigma), repr(pfa), ", ".join(sorted(set(str(s["n"]) for s, _ in pairs)))),
                  "Authority: stats/ (D8 and its tolerance) for the top two panels; the reference model for the",
                  "lowest, card found less software found at each amplitude (counts, not words)"],
                 WIDTH)
    top_px = fig.top_of_plots()
    xaxis = LinearAxis("amplitude (of the definition's e0)", amps)
    main = fig.add_panel(Panel("main", PLOT_LEFT, top_px, PLOT_WIDTH, 260, xaxis,
                               LinearAxis("efficiency (found / injections)", yvals)))
    resid = fig.add_panel(Panel("residual", PLOT_LEFT, top_px + 260 + 58, PLOT_WIDTH, 130, xaxis,
                                LinearAxis("efficiency - D8", soft_off + card_off + tols + [-t for t in tols])))
    strip = fig.add_panel(Panel("strip", PLOT_LEFT, top_px + 260 + 58 + 130 + 58, PLOT_WIDTH, 70, xaxis,
                                LinearAxis("card - software", diffs)))

    main.line("d8-curve", curve, SERIES["green"])
    for s, c in pairs:
        main.point("software", Ratio(*s["amplitude"]), Ratio(s["found"], s["n"]), SERIES["blue"],
                   shape="circle", filled=True, size=3.5)
        main.point("card", Ratio(*c["amplitude"]), Ratio(c["found"], c["n"]), SERIES["orange"],
                   shape="square", filled=False, size=6.5)
    for (s, c), tol, so, co in zip(pairs, tols, soft_off, card_off):
        a = Ratio(*s["amplitude"])
        resid.errorbar("d8-tolerance", a, -tol, tol, SERIES["green"])
        resid.point("software-offset", a, so, SERIES["blue"], shape="circle", filled=True, size=3.5,
                    extra={"data-expected": repr(s["expected"])})
        resid.point("card-offset", a, co, SERIES["orange"], shape="square", filled=False, size=6.5,
                    extra={"data-expected": repr(c["expected"])})
    for (s, c), dv in zip(pairs, diffs):
        strip.point("card-minus-software", Ratio(*s["amplitude"]), dv, SERIES["orange"], shape="diamond",
                    filled=True, size=4.0)

    fig.legend("line", SERIES["green"], "D8: stats.theory.pd_matched")
    fig.legend("marker", SERIES["blue"], "software, round 1", shape="circle")
    fig.legend("marker", SERIES["orange"], "card, round 4", shape="square", filled=False)
    fig.legend("errorbar", SERIES["green"], "D8's tolerance about 0, %g se" % z)
    fig.legend("marker", SERIES["orange"], "lowest: card less software", shape="diamond")
    fig.source(r.log)
    return fig.render(LEGEND_X, top_px + 8)


# ---------------------------------------------------------------- stage E1


def _e1_part(part, where):
    return {
        "where": where,
        "labelled_windows": field(part, "labelled_windows", "int", where),
        "n": field(part, "n", "int", where),
        "m": field(part, "m", "int", where),
        "k": field(part, "k", "int", where),
        "found": field(part, "found", "int", where),
        "base_found": field(part, "base_found", "int", where),
        "d_learned": field(part, "d_learned", "number", where),
        "d_matched": field(part, "d_matched", "number", where),
        "pfa": field(part, "pfa", "number", where),
        "sigma": fraction_pair(part, "sigma", where),
        "profile": field(part, "profile", "str", where),
    }


def e1_learning(r):
    parts = [_e1_part(r.json(rel), rel) for rel in r.glob(E1_FOLDER, r"c(\d+)\.json")]
    rows = [(p["where"], p) for p in parts]
    pfa = agree(rows, "pfa", "the E1 parts")
    d_matched = agree(rows, "d_matched", "the E1 parts")
    n = agree(rows, "n", "the E1 parts")
    m = agree(rows, "m", "the E1 parts")
    k = agree(rows, "k", "the E1 parts")
    sigma = agree(rows, "sigma", "the E1 parts")
    profile = agree(rows, "profile", "the E1 parts")
    # Each part's threshold was measured from m signal-free scores, k of them above it. Its
    # false-alarm probability is then stats.recovery.threshold_from_scores's pfa_effective,
    # (k + 1) / (m + 1), which is what E1's judge hands D8 and the tolerance; not the target pfa.
    pfa_effective = (k + 1) / (m + 1)
    e0_figure = pd_matched(pfa_effective, d_matched)
    judged = tolerance(pfa_effective, d_matched, n, m)
    tol = judged["tolerance"]
    own = [pd_matched(pfa_effective, p["d_learned"]) for p in parts]

    yvals = [Ratio(p["found"], p["n"]) for p in parts] + [Ratio(p["base_found"], p["n"]) for p in parts]
    yvals += own + [e0_figure - tol, e0_figure + tol]
    fig = Figure("e1-learning", "Stage E1: the learner's efficiency against labelled windows",
                 ["Each point one part, its own seed, scored on %d held-out injections at its own threshold"
                  % n,
                  "measured from m = %d signal-free scores, k = %d; profile %s, sigma %s, target Pfa %s"
                  % (m, k, profile, sigma_text(sigma), repr(pfa)),
                  "D8 and its tolerance at the threshold's Pfa, (k + 1) / (m + 1), with the threshold's own term.",
                  "Authority: stats/. Software only."],
                 WIDTH)
    top_px = fig.top_of_plots()
    xaxis = Log10Axis("labelled windows the learner was given (log scale)",
                      [p["labelled_windows"] for p in parts])
    main = fig.add_panel(Panel("main", PLOT_LEFT, top_px, PLOT_WIDTH, 320, xaxis,
                               LinearAxis("efficiency (found / injections)", yvals)))
    main.hband("e0-tolerance", e0_figure - tol, e0_figure + tol, SERIES["green"])
    main.hline("e0-figure", e0_figure, SERIES["green"], dash="dashed")
    main.line("learned-line", [(p["labelled_windows"], Ratio(p["found"], p["n"])) for p in parts],
              SERIES["blue"], width=1.0)
    for p, o in zip(parts, own):
        main.point("own-d8", p["labelled_windows"], o, SERIES["purple"], shape="diamond", filled=False,
                   size=4.5)
        main.point("matched", p["labelled_windows"], Ratio(p["base_found"], p["n"]), SERIES["grey"],
                   shape="triangle", filled=True, size=3.5)
        main.point("learned", p["labelled_windows"], Ratio(p["found"], p["n"]), SERIES["blue"],
                   shape="circle", filled=True, size=3.5)
    fig.legend("marker", SERIES["blue"], "the learned filter", shape="circle")
    fig.legend("marker", SERIES["purple"], "D8 at that part's own d", shape="diamond", filled=False)
    fig.legend("marker", SERIES["grey"], "the matched filter, same part", shape="triangle")
    fig.legend("line", SERIES["green"], "E0's figure: D8 at the matched d", dash="dashed")
    fig.legend("band", SERIES["green"], "its tolerance, %g se (stats.tolerance)" % judged["z"])
    fig.source(r.log)
    return fig.render(LEGEND_X, top_px + 8)


# ---------------------------------------------------------------- stage E2


def _e2_entry(e, where):
    return {
        "where": where,
        "model": field(e, "model", "str", where),
        "g": e.get("g") if type(e) is dict else None,
        "found": field(e, "found", "int", where),
    }


def parse_e2_predictions(text):
    """({model: {g: (found, gain text, predicted text)}}, windows a step of g) from the judge's output.

    A section opens on a line "  the adaptive model, g = labelled windows after the
    change / <w>:" or the same of "the reset model", and holds lines of four spaces.
    Both headers must be in that shape and name one w, or VIZ-PARSE. Within a
    section, a line "    g ..." must be in the shape read, or VIZ-PARSE; a line
    "    one reading ..." is passed over; any other line of four spaces is refused.
    A line of two spaces ends the section.
    """
    out = {}
    per_g = set()
    section = None
    for number, line in enumerate(text.split("\n"), 1):
        if line.startswith("  the adaptive model,") or line.startswith("  the reset model,"):
            m = HEADER.fullmatch(line)
            if not m:
                raise VizRefusal("VIZ-PARSE", "%s line %d is not a section's header: %r" % (E2_JUDGE, number, line))
            section = m.group(1)
            per_g.add(int(m.group(2)))
        elif section and line.startswith("    "):
            if line.startswith("    one reading"):
                continue
            m = SNAPSHOT.fullmatch(line)
            if not m:
                raise VizRefusal("VIZ-PARSE", "%s line %d is not a snapshot line: %r" % (E2_JUDGE, number, line))
            g = int(m.group(1))
            if g in out.setdefault(section, {}):
                raise VizRefusal("VIZ-PARSE", "%s line %d: g %d twice in the %s model" % (E2_JUDGE, number, g, section))
            out[section][g] = (int(m.group(2)), m.group(3), m.group(4))
        else:
            section = None
    for model in ("adaptive", "reset"):
        if not out.get(model):
            raise VizRefusal("VIZ-PARSE", "%s holds no snapshot line of the %s model" % (E2_JUDGE, model))
    if len(per_g) != 1:
        raise VizRefusal("VIZ-PARSE", "%s names %r labelled windows a step of g, not one figure"
                         % (E2_JUDGE, sorted(per_g)))
    return out, per_g.pop()


HEADER = re.compile(r"  the (adaptive|reset) model, g = labelled windows after the change / (\d+):")
SNAPSHOT = re.compile(
    r"    g (\d+) \( *\d+ windows\) blocks \d+-\d+: found (\d+) \(0\.\d+\), own .*; "
    r"gain over frozen ([+-]\d+\.\d+) se \d+\.\d+ \(z [+-]\d+\.\d+\); "
    r"predicted ([+-]\d+\.\d+) \([+-]\d+\.\d+ se\)")


def e2_recovery(r):
    part = r.json(E2_PART)
    judge = r.text(E2_JUDGE)
    n = field(part, "n", "int", E2_PART)
    pfa = field(part, "pfa", "number", E2_PART)
    profile = field(part, "profile", "str", E2_PART)
    sigma = fraction_pair(part, "sigma", E2_PART)
    raw = field(part, "entries", "list", E2_PART)
    entries = [_e2_entry(e, "%s entries[%d]" % (E2_PART, i)) for i, e in enumerate(raw)]

    def one(model):
        found = [e for e in entries if e["model"] == model]
        if len(found) != 1:
            raise VizRefusal("VIZ-RECORD-FIELD", "%s holds %d entries of model %r, not 1" % (E2_PART, len(found), model))
        return found[0]

    def curve(model):
        found = [e for e in entries if e["model"] == model]
        for e in found:
            if type(e["g"]) is not int:
                raise VizRefusal("VIZ-RECORD-FIELD", "%s field 'g' is %r, not int" % (e["where"], e["g"]))
        gs = [e["g"] for e in found]
        if not found or len(set(gs)) != len(gs):
            raise VizRefusal("VIZ-RECORD-FIELD", "%s: the %s model's g are %r" % (E2_PART, model, gs))
        return sorted(found, key=lambda e: e["g"])

    frozen, best = one("frozen"), one("e1")
    learners = {"adaptive": curve("adaptive"), "reset": curve("reset")}
    predicted, per_g = parse_e2_predictions(judge)
    for model, rows in learners.items():
        if sorted(predicted[model]) != [e["g"] for e in rows]:
            raise VizRefusal("VIZ-RECORD-PAIR", "the judge's %s snapshots are at g %r, the part's at %r"
                             % (model, sorted(predicted[model]), [e["g"] for e in rows]))
        for e in rows:
            if predicted[model][e["g"]][0] != e["found"]:
                raise VizRefusal("VIZ-RECORD-PAIR", "the judge's %s g %d found %d, the part's %d"
                                 % (model, e["g"], predicted[model][e["g"]][0], e["found"]))
    base = Ratio(frozen["found"], n)
    pred = {model: [(e["g"], float(base) + float(predicted[model][e["g"]][2]), predicted[model][e["g"]][2])
                    for e in rows] for model, rows in learners.items()}

    yvals = [base, Ratio(best["found"], n)]
    yvals += [Ratio(e["found"], n) for rows in learners.values() for e in rows]
    yvals += [y for rows in pred.values() for _, y, _ in rows]
    fig = Figure("e2-recovery", "Stage E2: recovery after the drift from e0 to e1",
                 ["Each point a snapshot after g x %d labelled windows of e1, all scored on the same %d" % (per_g, n),
                  "held-out injections of e1, each at its own threshold; profile %s, sigma %s, Pfa %s"
                  % (profile, sigma_text(sigma), repr(pfa)),
                  "Authority: stats/ (D8) for the efficiencies; the dashed predictions are E2L's first-order",
                  "derivation, printed by the judge, which is not stats/'. Software only."],
                 WIDTH)
    top_px = fig.top_of_plots()
    xaxis = LinearAxis("g (labelled windows after the change / %d)" % per_g,
                       [e["g"] for rows in learners.values() for e in rows])
    main = fig.add_panel(Panel("main", PLOT_LEFT, top_px, PLOT_WIDTH, 320, xaxis,
                               LinearAxis("efficiency (found / injections)", yvals)))
    main.hline("e1-filter", Ratio(best["found"], n), SERIES["green"], width=2.0)
    main.hline("frozen", base, SERIES["grey"], width=2.0)
    style = {"adaptive": (SERIES["blue"], "circle"), "reset": (SERIES["orange"], "square")}
    for model, rows in learners.items():
        colour, shape = style[model]
        main.line(model + "-predicted-line", [(g, y) for g, y, _ in pred[model]], colour, dash="dashed",
                  width=1.0)
        main.line(model + "-line", [(e["g"], Ratio(e["found"], n)) for e in rows], colour, width=1.0)
        for g, y, gain in pred[model]:
            main.point(model + "-predicted", g, y, colour, shape=shape, filled=False, size=3.0,
                       extra={"data-predicted-gain": gain, "data-base": "%d/%d" % (base.num, base.den)})
        for e in rows:
            main.point(model, e["g"], Ratio(e["found"], n), colour, shape=shape, filled=True,
                       size=3.5 if shape == "circle" else 3.0)
    fig.legend("marker", SERIES["blue"], "adaptive", shape="circle")
    fig.legend("marker", SERIES["orange"], "reset", shape="square")
    fig.legend("line", SERIES["blue"], "first-order prediction", dash="dashed")
    fig.legend("line", SERIES["green"], "the e1 filter")
    fig.legend("line", SERIES["grey"], "the frozen model (e0's filter)")
    fig.source(r.log)
    return fig.render(LEGEND_X, top_px + 8)


# ---------------------------------------------------------------- the card's timed runs

COLOUR_ORDER = ("blue", "orange", "green", "purple", "red", "teal", "grey", "brown", "pink", "olive")


def card_timed(r):
    rec = r.json(TIMED)
    gens = field(rec, "generations", "list", TIMED)
    frames = field(rec, "frames", "int", TIMED)
    trials = field(rec, "trials", "int", TIMED)
    rows = []
    keys = None
    for i, g in enumerate(gens):
        where = "%s generations[%d]" % (TIMED, i)
        number = field(g, "generation", "int", where)
        parts = field(g, "parts_ns", "dict", where)
        total = field(g, "sum_ns", "int", where)
        these = list(parts)
        if keys is None:
            keys = these
        if these != keys:
            raise VizRefusal("VIZ-RECORD-FIELD", "%s parts_ns has keys %r, not %r" % (where, these, keys))
        values = [field(parts, k, "int", where + " parts_ns") for k in keys]
        if sum(values) != total:
            raise VizRefusal("VIZ-RECORD-FIELD", "%s: its parts sum to %d ns, its sum_ns is %d"
                             % (where, sum(values), total))
        rows.append((number, values, total))
    if not rows:
        raise VizRefusal("VIZ-RECORD-FIELD", "%s holds no generation" % TIMED)
    if len(keys) > len(COLOUR_ORDER):
        raise VizRefusal("VIZ-RECORD-FIELD", "%d parts and %d colours" % (len(keys), len(COLOUR_ORDER)))
    rows.sort(key=lambda row: row[0])
    numbers = [row[0] for row in rows]
    if len(set(numbers)) != len(numbers):
        raise VizRefusal("VIZ-RECORD-FIELD", "%s: generation numbers %r" % (TIMED, numbers))

    fig = Figure("card-timed", "The card's timed generations: where the time goes",
                 ["One bar a generation: the device opened, weights loaded, %d frames run with %d injections,"
                  % (frames, trials),
                  "the records read back and scored, the device closed. Each part as the host timed it.",
                  "Authority: neither. A wall clock of one session of this host code on the U50."],
                 WIDTH)
    top_px = fig.top_of_plots()
    xaxis = CategoryAxis("generation", numbers)
    yaxis = LinearAxis("time (ms)", [Ratio(total, 10 ** 6) for _, _, total in rows])
    main = fig.add_panel(Panel("main", PLOT_LEFT, top_px, PLOT_WIDTH, 320, xaxis, yaxis))
    for slot, (number, values, total) in enumerate(rows):
        below = 0
        for k, v in zip(keys, values):
            main.bar(k, slot, Ratio(below, 10 ** 6), Ratio(below + v, 10 ** 6),
                     SERIES[COLOUR_ORDER[keys.index(k)]],
                     extra={"data-ns": str(v), "data-generation": str(number)})
            below += v
    for k in reversed(keys):
        fig.legend("bar", SERIES[COLOUR_ORDER[keys.index(k)]], k)
    fig.source(r.log)
    return fig.render(LEGEND_X, top_px + 8)


# ---------------------------------------------------------------- the pulses

def pulses(r):
    value = r.pulses()
    names = sorted(value)
    if len(names) > len(COLOUR_ORDER):
        raise VizRefusal("VIZ-RECORD-FIELD", "%d pulses and %d colours" % (len(names), len(COLOUR_ORDER)))
    lengths = sorted(set(len(value[k]) for k in names))
    fig = Figure("pulses", "The definition's pulses",
                 ["%s, %s samples, each oldest sample first (conventions.md, CV2)"
                  % (", ".join(names), " and ".join(str(n) for n in lengths)),
                  "Authority: the definition, spec/undertone.toml, through its generated copy spec/constants.py"],
                 WIDTH)
    top_px = fig.top_of_plots()
    xaxis = LinearAxis("tap (sample offset from the truth index, frames)", [len(value[k]) - 1 for k in names],
                       most=8)
    yaxis = LinearAxis("sample value (integer)", [s for k in names for s in value[k]])
    main = fig.add_panel(Panel("main", PLOT_LEFT, top_px, PLOT_WIDTH, 320, xaxis, yaxis))
    for i, k in enumerate(names):
        colour = SERIES[COLOUR_ORDER[i]]
        main.line(k + "-line", list(enumerate(value[k])), colour, width=1.5)
        for tap, s in enumerate(value[k]):
            main.point(k, tap, s, colour, shape="circle", filled=True, size=2.0)
        fig.legend("marker", colour, k, shape="circle")
    fig.source(r.log)
    return fig.render(LEGEND_X, top_px + 8)


# ---------------------------------------------------------------- the launch studies, D2 and D3

LAUNCH_STUDIES = (("D2", "docs/studies/d2/scored-output.txt"), ("D3", "docs/studies/d3/scored-output.txt"))
KINDS = (("launch", "launch windows"), ("wrong", "wrong windows, closing just before T0"),
         ("shifted", "windows an hour early"), ("control", "control windows, whole weeks away"))
KIND_COLOURS = ("blue", "orange", "purple", "grey")
BAR_WIDTH = 0.18                        # of a station's slot: four bars a slot
BAR_OFFSETS = (-0.3, -0.1, 0.1, 0.3)    # each bar's centre from its slot's centre, in slots
WINDOW_ROW = re.compile(r"\| (\d{4}-\d{3}) \| (CI\.[A-Z0-9]+) \| (launch|wrong|shifted|control) \| [^|]* \| "
                        r"[^|]* \| [^|]* \| (yes|no|-) \| [^|]*\|")
TEST_ROW = re.compile(r"\| (CI\.[A-Z0-9]+) \| (\d+\.\d) \| \d+ \| (\d+) of (\d+) \| (\d+) of (\d+) \| .*\|")
CONTROLS_ROW = re.compile(r"\| (CI\.[A-Z0-9]+) \| (\d+) of (\d+) \| [^|]+ \| (\d+) of (\d+) \| [^|]+ \| [^|]+ \|")


def parse_scored(text, rel):
    """(stations [(name, km text)], {(station, kind): (hits, windows with a record)}) from a study's output.

    The counts are the table "Every window", one row a window: its hit "yes" or "no", or "-" for no
    record, which is not counted. The station rows of the two summary tables are read too, the
    test's (launch and control) and the controls' (wrong and an hour early), and each count there
    must equal the windows' (VIZ-RECORD-PAIR). A row starting "| 20" or "| CI." in neither shape
    is refused, VIZ-PARSE. The stations are drawn in the test table's order.
    """
    stations, summary, counts = [], {}, {}
    for number, line in enumerate(text.split("\n"), 1):
        if line.startswith("| 20"):
            m = WINDOW_ROW.fullmatch(line)
            if not m:
                raise VizRefusal("VIZ-PARSE", "%s line %d is not a window row: %r" % (rel, number, line))
            hits, usable = counts.get((m.group(2), m.group(3)), (0, 0))
            if m.group(4) != "-":
                hits, usable = hits + (m.group(4) == "yes"), usable + 1
            counts[(m.group(2), m.group(3))] = (hits, usable)
        elif line.startswith("| CI."):
            t, c = TEST_ROW.fullmatch(line), CONTROLS_ROW.fullmatch(line)
            if t and not c:
                stations.append((t.group(1), t.group(2)))
                summary[(t.group(1), "launch")] = (int(t.group(3)), int(t.group(4)))
                summary[(t.group(1), "control")] = (int(t.group(5)), int(t.group(6)))
            elif c and not t:
                summary[(c.group(1), "wrong")] = (int(c.group(2)), int(c.group(3)))
                summary[(c.group(1), "shifted")] = (int(c.group(4)), int(c.group(5)))
            else:
                raise VizRefusal("VIZ-PARSE", "%s line %d is not a station row: %r" % (rel, number, line))
    if not stations:
        raise VizRefusal("VIZ-PARSE", "%s holds no station row" % rel)
    for station, _ in stations:
        for kind, _ in KINDS:
            if counts.get((station, kind)) != summary.get((station, kind)):
                raise VizRefusal("VIZ-RECORD-PAIR", "%s: %s's %s windows count %r, its summary %r"
                                 % (rel, station, kind, counts.get((station, kind)), summary.get((station, kind))))
    return stations, counts


def launch_windows(r):
    studies = [(name, rel, parse_scored(r.text(rel), rel)) for name, rel in LAUNCH_STUDIES]
    fig = Figure("launch-windows", "Studies D2 and D3: launch windows against control windows, by station",
                 ["The share of each kind of window with a record in which the study's frozen rule found a hit,",
                  "at each of its stations, nearest the pad first. Each bar carries its hits and its windows.",
                  "Authority: neither. Each study's own rule and Fisher's exact test; no detector was run."],
                 WIDTH)
    top = fig.top_of_plots()
    colours = [SERIES[c] for c in KIND_COLOURS]
    for i, (name, rel, (stations, counts)) in enumerate(studies):
        shares = []
        for station, _ in stations:
            for kind, _ in KINDS:
                hits, usable = counts[(station, kind)]
                if usable == 0:
                    raise VizRefusal("VIZ-RECORD-FIELD", "%s: %s has no %s window with a record"
                                     % (rel, station, kind))
                shares.append(Ratio(hits, usable))
        xaxis = CategoryAxis("%s: station (its distance from the pad)" % name,
                             ["%s (%s km)" % (s, km) for s, km in stations])
        panel = fig.add_panel(Panel(name.lower(), PLOT_LEFT, top + i * (220 + 64), PLOT_WIDTH, 220, xaxis,
                                    LinearAxis("share of windows that hit", shares)))
        for slot, (station, _) in enumerate(stations):
            for (kind, _), colour, offset in zip(KINDS, colours, BAR_OFFSETS):
                hits, usable = counts[(station, kind)]
                panel.bar(kind, slot, 0, Ratio(hits, usable), colour, offset=offset, width=BAR_WIDTH,
                          extra={"data-station": station, "data-hits": str(hits), "data-windows": str(usable)})
    for (kind, label), colour in zip(KINDS, colours):
        fig.legend("bar", colour, label)
    fig.source(r.log)
    return fig.render(LEGEND_X, top + 8)


FIGURES = (
    ("e0-efficiency.svg", e0_efficiency),
    ("e1-learning.svg", e1_learning),
    ("e2-recovery.svg", e2_recovery),
    ("card-timed.svg", card_timed),
    ("pulses.svg", pulses),
    ("launch-windows.svg", launch_windows),
)

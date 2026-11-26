"""A small SVG writer of the generator's own. Standard library only.

WHAT IT DOES. A figure of one or more panels. A panel has two axes: linear,
base-10 logarithmic over positive ints, or categories. Ticks on a linear axis
come from a nice-number rule worked in `decimal.Decimal` (`nice_ticks`). It
draws grid lines, tick labels, axis labels (the y one turned), a title and
subtitle lines; polylines, solid or dashed; markers (circle, square, triangle,
diamond, filled or open); vertical error bars with caps; a horizontal band;
horizontal reference lines; bars; a legend; and the source lines.

WHAT IT WILL NOT DO. Smooth, interpolate or fit; clip (a value outside its axis
is refused, VIZ-AXIS-RANGE); measure text (a width is estimated as
`CHAR_WIDTH` times the font size a character); embed a font (it asks for a
generic sans-serif, so widths differ by viewer); animate; or move a label out of
another's way.

DETERMINISM. Every coordinate is written by `fmt`: Python's "%.2f", which
rounds the exact binary value to the nearest hundredth of a pixel, with "-0.00"
written "0.00". Attributes are written in sorted order, one element a line,
LF line ends and one final newline. Text and attributes must be printable
ASCII, or VIZ-NOT-ASCII. A value drawn from a record carries its exact form on
the element (`exact`): an int as written, a `Ratio` as "num/den" of the
record's own integers, unreduced, a float as Python's `repr`.

LIGHT AND DARK. The background is an opaque rectangle. The theme's colours
(background, ink, muted ink, grid) are written as presentation attributes in
the light set, and a `prefers-color-scheme: dark` rule in the figure's style
overrides them; a viewer that reads no style gets the light set on its own
background. A series colour is the same in both themes and is chosen to keep
at least 3:1 contrast against both backgrounds (WCAG's ratio, held by a test).
"""
import decimal
import math
from decimal import Decimal

from viz.errors import VizRefusal

LIGHT = {"bg": "#ffffff", "ink": "#1f2328", "muted": "#57606a", "grid": "#d0d7de"}
DARK = {"bg": "#0d1117", "ink": "#e6edf3", "muted": "#9198a1", "grid": "#30363d"}

# Series colours: one set for both themes.
SERIES = {
    "blue": "#2f6fd0",
    "orange": "#c8640a",
    "green": "#2e8b3e",
    "purple": "#9b59d0",
    "red": "#d03a3a",
    "teal": "#1a8a8a",
    "grey": "#808080",
    "brown": "#a0703a",
    "pink": "#c8508c",
    "olive": "#7f8a1a",
}

DASHES = {"solid": None, "dashed": "6 4", "dotted": "2 3"}
CHAR_WIDTH = 0.6
FONT = "sans-serif"


class Ratio:
    """A count ratio kept as the record's own two integers, unreduced."""

    __slots__ = ("num", "den")

    def __init__(self, num, den):
        if type(num) is not int or type(den) is not int or den <= 0:
            raise VizRefusal("VIZ-RECORD-FIELD", "a ratio needs ints and a positive denominator: %r/%r"
                             % (num, den))
        self.num = num
        self.den = den

    def __float__(self):
        return self.num / self.den


def exact(v):
    """The exact text of a value drawn: int, Ratio or float."""
    if type(v) is int:
        return str(v)
    if type(v) is Ratio:
        return "%d/%d" % (v.num, v.den)
    if type(v) is float:
        return repr(v)
    raise TypeError("no exact form for %r" % (v,))


def number(v):
    if type(v) is Ratio:
        return float(v)
    if type(v) in (int, float):
        return float(v)
    raise TypeError("not a value: %r" % (v,))


def fmt(v):
    """A coordinate: the nearest hundredth of a pixel, never "-0.00"."""
    s = "%.2f" % v
    return "0.00" if s == "-0.00" else s


def check_ascii(s, what):
    for ch in s:
        if not (" " <= ch <= "~"):
            raise VizRefusal("VIZ-NOT-ASCII", "%s holds %r" % (what, ch))
    return s


def escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def text_width(s, size):
    return CHAR_WIDTH * size * len(s)


# ---------------------------------------------------------------- ticks


def _dec(v):
    if type(v) is Ratio:
        return Decimal(v.num) / Decimal(v.den)
    if type(v) is int:
        return Decimal(v)
    return Decimal(repr(float(v)))


def nice_ticks(lo, hi, most=6):
    """Ticks a step of 1, 2 or 5 times a power of ten apart, covering [lo, hi].

    The step is the smallest such that the ticks cover lo and hi in at most
    `most` intervals. lo == hi is widened by one either side first. Worked in
    Decimal at 50 digits, so 0.1 is 0.1.
    """
    with decimal.localcontext() as ctx:
        ctx.prec = 50
        lo, hi = _dec(lo), _dec(hi)
        if hi < lo:
            lo, hi = hi, lo
        if lo == hi:
            lo, hi = lo - 1, hi + 1
        for exp in range(-20, 21):
            for m in (1, 2, 5):
                step = Decimal(m).scaleb(exp)
                a = (lo / step).to_integral_value(rounding=decimal.ROUND_FLOOR)
                b = (hi / step).to_integral_value(rounding=decimal.ROUND_CEILING)
                if b - a <= most:
                    return [(a + i) * step for i in range(int(b - a) + 1)]
    raise VizRefusal("VIZ-AXIS-RANGE", "no tick step for %s to %s" % (lo, hi))


def tick_label(d):
    """A tick's text: the Decimal written plainly, without trailing zeros."""
    d = d.normalize()
    if d == 0:
        return "0"
    s = format(d, "f")
    return s


# ---------------------------------------------------------------- axes


class LinearAxis:
    scale = "linear"

    def __init__(self, label, values, include_zero=True, most=6):
        vals = [_dec(v) for v in values]
        if include_zero:
            vals.append(Decimal(0))
        self.label = check_ascii(label, "an axis label")
        self.ticks = nice_ticks(min(vals), max(vals), most)
        self.lo, self.hi = self.ticks[0], self.ticks[-1]
        self.labels = [tick_label(t) for t in self.ticks]

    def frac(self, v):
        x = number(v)
        lo, hi = float(self.lo), float(self.hi)
        if not (math.isfinite(x) and lo <= x <= hi):
            raise VizRefusal("VIZ-AXIS-RANGE", "%s is outside %s to %s on %r"
                             % (exact(v), self.lo, self.hi, self.label))
        return (x - lo) / (hi - lo)

    def tick_fracs(self):
        return [self.frac(float(t)) for t in self.ticks]

    def bounds_text(self):
        return str(self.lo), str(self.hi)


def _decade_floor(n):
    return len(str(n)) - 1


class Log10Axis:
    """Positive ints only, from the decade at or below the least to the decade at or above the most."""

    scale = "log10"

    def __init__(self, label, values):
        for v in values:
            if type(v) is not int or v <= 0:
                raise VizRefusal("VIZ-AXIS-RANGE", "a log axis takes positive ints, not %r" % (v,))
        self.label = check_ascii(label, "an axis label")
        lo = _decade_floor(min(values))
        top = max(values)
        hi = _decade_floor(top) if top == 10 ** _decade_floor(top) else _decade_floor(top) + 1
        if hi == lo:
            hi = lo + 1
        self.klo, self.khi = lo, hi
        self.ticks = [10 ** k for k in range(lo, hi + 1)]
        self.labels = [format(t, ",") for t in self.ticks]
        self.lo, self.hi = self.ticks[0], self.ticks[-1]

    def frac(self, v):
        if type(v) is not int or not (self.lo <= v <= self.hi):
            raise VizRefusal("VIZ-AXIS-RANGE", "%r is not a positive int inside %d to %d on %r"
                             % (v, self.lo, self.hi, self.label))
        return (math.log10(v) - self.klo) / (self.khi - self.klo)

    def tick_fracs(self):
        return [self.frac(t) for t in self.ticks]

    def bounds_text(self):
        return str(self.lo), str(self.hi)


class CategoryAxis:
    """n categories, each the centre of its own slot; a value is a category's index."""

    scale = "category"

    def __init__(self, label, categories):
        if not categories:
            raise VizRefusal("VIZ-AXIS-RANGE", "a category axis needs a category")
        self.label = check_ascii(label, "an axis label")
        self.labels = [check_ascii(str(c), "a category") for c in categories]
        self.n = len(categories)
        self.ticks = list(range(self.n))

    def frac(self, i):
        if type(i) is not int or not 0 <= i < self.n:
            raise VizRefusal("VIZ-AXIS-RANGE", "%r is not a category index below %d" % (i, self.n))
        return (i + 0.5) / self.n

    def slot(self):
        return 1.0 / self.n

    def tick_fracs(self):
        return [self.frac(i) for i in self.ticks]

    def bounds_text(self):
        return "0", str(self.n)


# ---------------------------------------------------------------- elements


class El:
    def __init__(self, tag, attrs, text=None):
        self.tag = tag
        self.attrs = attrs
        self.text = text

    def render(self):
        parts = []
        for k in sorted(self.attrs):
            v = self.attrs[k]
            v = fmt(v) if type(v) is float else str(v)
            parts.append('%s="%s"' % (k, escape(check_ascii(v, "attribute %s" % k))))
        head = "<%s %s" % (self.tag, " ".join(parts)) if parts else "<%s" % self.tag
        if self.text is None:
            return head + "/>"
        return "%s>%s</%s>" % (head, escape(check_ascii(self.text, "a text")), self.tag)


def text_el(x, y, s, size=12, cls="ink", anchor="start", weight=None, rotate=False):
    theme = LIGHT[cls]
    a = {"x": float(x), "y": float(y), "font-size": size, "class": cls, "fill": theme,
         "text-anchor": anchor}
    if weight:
        a["font-weight"] = weight
    if rotate:
        a["transform"] = "rotate(-90 %s %s)" % (fmt(x), fmt(y))
    return El("text", a, s)


def marker_els(shape, cx, cy, colour, filled, size, extra):
    """A marker centred on (cx, cy). `size` is its half-width in px."""
    a = dict(extra)
    a["stroke"] = colour
    a["stroke-width"] = "1.5"
    a["fill"] = colour if filled else "none"
    if shape == "circle":
        a.update({"cx": cx, "cy": cy, "r": float(size)})
        return [El("circle", a)]
    if shape == "square":
        a.update({"x": cx - size, "y": cy - size, "width": 2.0 * size, "height": 2.0 * size,
                  "data-cx": cx, "data-cy": cy})
        return [El("rect", a)]
    if shape == "triangle":
        pts = [(cx, cy - size * 1.15), (cx + size, cy + size * 0.85), (cx - size, cy + size * 0.85)]
    elif shape == "diamond":
        pts = [(cx, cy - size * 1.2), (cx + size * 1.2, cy), (cx, cy + size * 1.2), (cx - size * 1.2, cy)]
    else:
        raise ValueError("no marker shape %r" % (shape,))
    a.update({"points": " ".join("%s,%s" % (fmt(x), fmt(y)) for x, y in pts),
              "data-cx": cx, "data-cy": cy})
    return [El("polygon", a)]


class Panel:
    """A plot area at (left, top), width by height, in pixels, with two axes."""

    def __init__(self, name, left, top, width, height, xaxis, yaxis):
        self.name = name
        self.left, self.top, self.width, self.height = float(left), float(top), float(width), float(height)
        self.x, self.y = xaxis, yaxis
        self.els = []

    def px(self, v):
        return self.left + self.x.frac(v) * self.width

    def py(self, v):
        return self.top + self.height - self.y.frac(v) * self.height

    def frame(self):
        out = []
        x0, x1 = self.left, self.left + self.width
        y0, y1 = self.top, self.top + self.height
        for f, label in zip(self.y.tick_fracs(), self.y.labels):
            yy = y1 - f * self.height
            out.append(El("line", {"x1": x0, "y1": yy, "x2": x1, "y2": yy, "class": "grid",
                                   "stroke": LIGHT["grid"], "stroke-width": "1"}))
            out.append(text_el(x0 - 6, yy + 4, label, size=11, anchor="end"))
        for f, label in zip(self.x.tick_fracs(), self.x.labels):
            xx = x0 + f * self.width
            out.append(El("line", {"x1": xx, "y1": y0, "x2": xx, "y2": y1, "class": "grid",
                                   "stroke": LIGHT["grid"], "stroke-width": "1"}))
            out.append(text_el(xx, y1 + 16, label, size=11, anchor="middle"))
        out.append(El("rect", {"x": x0, "y": y0, "width": self.width, "height": self.height,
                               "class": "axis", "stroke": LIGHT["ink"], "fill": "none",
                               "stroke-width": "1"}))
        out.append(text_el((x0 + x1) / 2, y1 + 36, self.x.label, size=12, anchor="middle"))
        out.append(text_el(x0 - 52, (y0 + y1) / 2, self.y.label, size=12, anchor="middle", rotate=True))
        return out

    def group_attrs(self):
        xlo, xhi = self.x.bounds_text()
        ylo, yhi = self.y.bounds_text()
        return {"class": "panel", "data-panel": self.name,
                "data-x-scale": self.x.scale, "data-x-lo": xlo, "data-x-hi": xhi,
                "data-y-scale": self.y.scale, "data-y-lo": ylo, "data-y-hi": yhi,
                "data-left": self.left, "data-top": self.top,
                "data-width": self.width, "data-height": self.height}

    # -- marks. `series` names the element for a reader of the file.

    def line(self, series, values, colour, dash="solid", width=1.5):
        """A polyline through (x, y) values; no exact values carried."""
        pts = " ".join("%s,%s" % (fmt(self.px(x)), fmt(self.py(y))) for x, y in values)
        a = {"data-series": series, "points": pts, "fill": "none", "stroke": colour,
             "stroke-width": str(width)}
        if DASHES[dash]:
            a["stroke-dasharray"] = DASHES[dash]
        self.els.append(El("polyline", a))

    def point(self, series, x, y, colour, shape="circle", filled=True, size=3.5, extra=None):
        a = {"data-series": series, "data-x": exact(x), "data-y": exact(y)}
        a.update(extra or {})
        self.els.extend(marker_els(shape, self.px(x), self.py(y), colour, filled, size, a))

    def hline(self, series, y, colour, dash="solid", width=1.5, extra=None):
        yy = self.py(y)
        a = {"data-series": series, "data-y": exact(y), "x1": self.left, "x2": self.left + self.width,
             "y1": yy, "y2": yy, "stroke": colour, "stroke-width": str(width)}
        if DASHES[dash]:
            a["stroke-dasharray"] = DASHES[dash]
        a.update(extra or {})
        self.els.append(El("line", a))

    def errorbar(self, series, x, lo, hi, colour, cap=5.0):
        xx, ylo, yhi = self.px(x), self.py(lo), self.py(hi)
        a = {"data-series": series, "data-x": exact(x), "data-lo": exact(lo), "data-hi": exact(hi),
             "d": "M%s %sV%sM%s %sH%sM%s %sH%s" % (fmt(xx), fmt(ylo), fmt(yhi),
                                                    fmt(xx - cap), fmt(ylo), fmt(xx + cap),
                                                    fmt(xx - cap), fmt(yhi), fmt(xx + cap)),
             "fill": "none", "stroke": colour, "stroke-width": "1.5"}
        self.els.append(El("path", a))

    def hband(self, series, lo, hi, colour):
        ylo, yhi = self.py(lo), self.py(hi)
        self.els.append(El("rect", {"data-series": series, "data-lo": exact(lo), "data-hi": exact(hi),
                                    "x": self.left, "y": yhi, "width": self.width, "height": ylo - yhi,
                                    "fill": colour, "fill-opacity": "0.18", "stroke": colour,
                                    "stroke-dasharray": DASHES["dotted"], "stroke-width": "1"}))

    def bar(self, series, i, y0, y1, colour, extra=None):
        """A bar in category slot i from y0 to y1, 0.6 of the slot wide."""
        w = self.x.slot() * self.width * 0.6
        xc = self.px(i)
        ya, yb = self.py(y0), self.py(y1)
        a = {"data-series": series, "data-x": exact(i), "data-y0": exact(y0), "data-y1": exact(y1),
             "x": xc - w / 2, "y": yb, "width": w, "height": ya - yb, "fill": colour,
             "stroke": "none"}
        a.update(extra or {})
        self.els.append(El("rect", a))


class Figure:
    """A whole figure: title, subtitle lines, panels, a legend, and source lines."""

    MARGIN = 16

    def __init__(self, name, title, lines, width):
        self.name = name
        self.title = check_ascii(title, "the title")
        self.lines = [check_ascii(s, "a subtitle") for s in lines]
        self.width = float(width)
        self.panels = []
        self.legend_entries = []
        self.sources = []

    def top_of_plots(self):
        return 40.0 + 16.0 * len(self.lines) + 14.0

    def add_panel(self, panel):
        self.panels.append(panel)
        return panel

    def legend(self, kind, colour, label, shape=None, filled=True, dash="solid"):
        self.legend_entries.append((kind, colour, check_ascii(label, "a legend label"), shape, filled, dash))

    def source(self, log):
        self.sources = ["source: %s  sha256 %s" % (what, h) for what, h in log]
        for s in self.sources:
            check_ascii(s, "a source line")

    def _legend_els(self, x, y):
        out = []
        for kind, colour, label, shape, filled, dash in self.legend_entries:
            if kind == "line":
                a = {"x1": x, "y1": y, "x2": x + 24, "y2": y, "stroke": colour, "stroke-width": "2"}
                if DASHES[dash]:
                    a["stroke-dasharray"] = DASHES[dash]
                out.append(El("line", a))
            elif kind == "marker":
                out.extend(marker_els(shape, x + 12, y, colour, filled, 4.0 if shape != "circle" else 3.5, {}))
            elif kind == "band":
                out.append(El("rect", {"x": x, "y": y - 6, "width": 24.0, "height": 12.0, "fill": colour,
                                       "fill-opacity": "0.18", "stroke": colour, "stroke-width": "1",
                                       "stroke-dasharray": DASHES["dotted"]}))
            elif kind == "errorbar":
                out.append(El("path", {"d": "M%s %sV%sM%s %sH%sM%s %sH%s" % (
                    fmt(x + 12), fmt(y - 7), fmt(y + 7), fmt(x + 7), fmt(y - 7), fmt(x + 17),
                    fmt(x + 7), fmt(y + 7), fmt(x + 17)), "fill": "none", "stroke": colour,
                    "stroke-width": "1.5"}))
            elif kind == "bar":
                out.append(El("rect", {"x": x + 4, "y": y - 6, "width": 16.0, "height": 12.0,
                                       "fill": colour, "stroke": "none"}))
            else:
                raise ValueError("no legend kind %r" % (kind,))
            out.append(text_el(x + 32, y + 4, label, size=11))
            y += 18
        return out

    def legend_width(self):
        if not self.legend_entries:
            return 0.0
        return 32 + max(text_width(e[2], 11) for e in self.legend_entries) + self.MARGIN

    def render(self, legend_x, legend_y):
        plots_bottom = max(p.top + p.height for p in self.panels) + 48
        lines_w = [text_width(self.title, 16)] + [text_width(s, 12) for s in self.lines] + \
                  [text_width(s, 10) for s in self.sources]
        width = max(self.width, legend_x + self.legend_width(), max(lines_w) + 2 * self.MARGIN)
        height = plots_bottom + 14.0 * len(self.sources) + 8
        width, height = math.ceil(width), math.ceil(height)
        out = []
        out.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
                   'font-family="%s" role="img" aria-label="%s">' % (width, height, width, height, FONT,
                                                                    escape(self.title)))
        out.append("<title>%s</title>" % escape(self.title))
        dark = ".bg{fill:%s}.ink{fill:%s}.muted{fill:%s}.grid{stroke:%s}.axis{stroke:%s}" % (
            DARK["bg"], DARK["ink"], DARK["muted"], DARK["grid"], DARK["ink"])
        out.append("<style>@media (prefers-color-scheme: dark){%s}</style>" % dark)
        out.append(El("rect", {"x": 0.0, "y": 0.0, "width": float(width), "height": float(height),
                               "class": "bg", "fill": LIGHT["bg"]}).render())
        out.append(text_el(self.MARGIN, 26, self.title, size=16, weight="bold").render())
        y = 46.0
        for s in self.lines:
            out.append(text_el(self.MARGIN, y, s, size=12, cls="muted").render())
            y += 16.0
        for p in self.panels:
            out.append("<g %s>" % " ".join('%s="%s"' % (k, escape(fmt(v) if type(v) is float else str(v)))
                                           for k, v in sorted(p.group_attrs().items())))
            out.extend(e.render() for e in p.frame())
            out.extend(e.render() for e in p.els)
            out.append("</g>")
        out.append('<g class="legend">')
        out.extend(e.render() for e in self._legend_els(legend_x, legend_y))
        out.append("</g>")
        y = plots_bottom
        for s in self.sources:
            out.append(text_el(self.MARGIN, y, s, size=10, cls="muted").render())
            y += 14.0
        out.append("</svg>")
        text = "\n".join(out) + "\n"
        check_ascii(text.replace("\n", ""), "the figure")
        return text

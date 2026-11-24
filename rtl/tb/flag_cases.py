"""The overflow flag's cases, each made by construction, and a second evaluator that checks them.

docs/rtl/flag.md says what this enumerates and why. In short: the flag's sources are
each hidden unit's value and the score; at one output each source fits, leaves its
field upward (past 2^63 - 1) or leaves it downward (below -2^63). A case puts exactly
a chosen set of sources out, in chosen directions, at one output i*, and every source
inside its field at every output before it.

THE FAMILY (docs/rtl/flag.md, section 4). K filters of one row each, filter k on
channel k mod channels; T taps; every coefficient COEFF_MIN; every sample of every
channel at the profile's lowest; rectifier pass; between pass; hidden shift 0. Each
product is then exactly 2^E (E = 32 under s16x1, 40 under s24x3), every filter's
pooled value at output i is 2^E n_i, and unit j's hidden sum is G_j 2^E n_i, where
G_j is the sum of its K hidden weights. With c = 2^(63-E), a unit is out upward
when G n >= c and downward when G n < -c.

THE SECOND EVALUATOR, `Evaluator`, is this file's own arithmetic for that family:
its own delay lines, windows and sums, its own wrap to the field. It imports nothing
of model/detector.py. A bench asserts with it, before the RTL runs, that each case
is what its label says (`Case.check`): every source fits before i*, and at i*
exactly the case's states. `Case.model_agrees` then asks the model, handed in and
not imported here, that its flag is 0 before i* and set from i* exactly when some
source is out, and that its score is this evaluator's at every output.

WHAT IT CANNOT SEE: a fault shared by this evaluator and the model in the family's
own arithmetic (both are integer sums of the same products); and whatever
docs/rtl/flag.md's limits say the family does not reach.
"""
import itertools
from collections import deque

from spec import constants as C
from model import weights

FIT, UP, DOWN = "fit", "up", "down"
PASS = C.RECTIFIERS["pass"]
FIELD = dict((f[0], f[1]) for f in C.RECORDS["score"])["score"]
LOWEST, HIGHEST = -(1 << (FIELD - 1)), (1 << (FIELD - 1)) - 1
FLAG = 1 << C.FLAGS["overflow"]
TAPS = 6                          # the family's taps: the small top's most
BIG = C.COEFF_MAX                 # the largest head weight, for a short stream's score


def wrap(value):
    """The value in the score field's width, two's complement."""
    value &= (1 << FIELD) - 1
    return value - (1 << FIELD) if value >> (FIELD - 1) else value


def state(value):
    if value > HIGHEST:
        return UP
    if value < LOWEST:
        return DOWN
    return FIT


def split(total, k):
    """k weights summing to `total`, as equal as can be, each inside the coefficient's range."""
    base, rest = divmod(total, k)
    out = [base + (1 if j < rest else 0) for j in range(k)]
    assert sum(out) == total and all(C.COEFF_MIN <= w <= C.COEFF_MAX for w in out), (total, out)
    return out


def ceil_div(a, b):
    return -(-a // b)


class Evaluator:
    """The family's datapath, written again: one row a filter, pass, pass. `hidden` None is the one route."""

    def __init__(self, profile, channels_of, coefficients, pool, hidden, head, score_shift, hidden_shift=0):
        self.channels = C.PROFILES[profile]["channels"]
        self.chan, self.coef = channels_of, coefficients
        taps = len(coefficients[0])
        self.lines = [deque([0] * taps, maxlen=taps) for _ in range(self.channels)]
        self.windows = [deque([0] * pool, maxlen=pool) for _ in channels_of]
        self.sums = [0] * len(channels_of)
        self.hidden, self.head = hidden, head
        self.s, self.q = score_shift, hidden_shift
        self.swaps = {}

    def swap_at(self, index, hidden, head):
        self.swaps[index] = (hidden, head)

    def step(self, index, frame):
        """{'units', 'score', 'value', 'raw', 'u'} at this output: states, the score's word, the score before
        its wrap, the hidden sums."""
        if index in self.swaps:
            self.hidden, self.head = self.swaps[index]
        for c in range(self.channels):
            self.lines[c].append(frame[c])
        z = []
        for k, ch in enumerate(self.chan):
            y = sum(w * x for w, x in zip(self.coef[k], self.lines[ch]))   # coefficient j meets the sample T-1-j frames old
            self.sums[k] += y - self.windows[k][0]                          # the window is always full: zeros at first
            self.windows[k].append(y)
            z.append(self.sums[k])
        if self.hidden is None:                                            # the one route: the model's version 1 head
            raw = sum(h * zk for h, zk in zip(self.head, z)) >> self.s
            return {"units": [], "score": state(raw), "value": wrap(raw), "raw": raw, "u": []}
        u = [sum(g * zk for g, zk in zip(unit, z)) for unit in self.hidden]
        shifted = [x >> self.q for x in u]
        a = sum(o * wrap(x) for o, x in zip(self.head, shifted))
        raw = a >> self.s
        return {"units": [state(x) for x in shifted], "score": state(raw), "value": wrap(raw), "raw": raw, "u": u}


class Family:
    """The family for one profile on one build, from its capability registers."""

    def __init__(self, profile, caps):
        prof = C.PROFILES[profile]
        self.profile, self.channels, self.low = profile, prof["channels"], prof["sample_min"]
        self.K, self.H, self.P = caps["cap_filters"], caps["cap_hidden"], caps["cap_pool"]
        self.T = min(TAPS, caps["cap_taps"])
        self.S = caps["cap_score_shift"]
        one = self.low * C.COEFF_MIN
        self.E = one.bit_length() - 1
        assert one == 1 << self.E, "the extreme product is a power of two"
        self.c = 1 << (FIELD - 1 - self.E)
        self.gmax, self.gmin = self.K * C.COEFF_MAX, self.K * C.COEFF_MIN
        n = self.n_seq(self.P, self.P)
        self.istar = next(i for i, x in enumerate(n) if ceil_div(self.c, x) <= self.gmax and self.c // x + 1 <= -self.gmin)
        self.nstar, self.nprev = n[self.istar], n[self.istar - 1]

    def n_seq(self, pool, length):
        """Extreme products in one filter's window at each output of a stream of extreme frames."""
        r, out, total = [], [], 0
        for i in range(length):
            r.append(min(i + 1, self.T))
            total += r[-1] - (r[i - pool] if i >= pool else 0)
            out.append(total)
        return out

    def low_frame(self):
        return (self.low,) * self.channels

    def quiet_frame(self):
        return (0,) * self.channels

    def filters(self):
        return [{k % self.channels: [C.COEFF_MIN] * self.T} for k in range(self.K)]

    def evaluator(self, hidden, head, shift, pool):
        return Evaluator(self.profile, [k % self.channels for k in range(self.K)], [[C.COEFF_MIN] * self.T] * self.K,
                         pool, None if hidden is None else [split(g, self.K) for g in hidden], head, shift)

    def blob(self, hidden, head, shift, pool):
        """hidden: a G for each unit, split over the filters; None for no hidden layer (head is then K weights)."""
        if hidden is None:
            return weights.pack(self.profile, self.filters(), head, PASS, pool, shift)
        return weights.pack(self.profile, self.filters(), head, PASS, pool, shift, [split(g, self.K) for g in hidden], 0, PASS)

    # ---------------------------------------------------------------- the constructions, R1 to R5

    def unit_out(self, direction, n):
        """R1: G that fits at the output before and is out at n, in `direction`."""
        return ceil_div(self.c, n) if direction == UP else -(self.c // n + 1)

    def driver(self, direction, n, o):
        """R4: (G, head weight) for a unit that fits and drives the score out at n alone, under a head weight of o."""
        if direction == UP:
            return ceil_div(self.c, o * n), o
        return self.c // (o * n) + 1, -o

    def all_out_head(self, units, score):
        """R5: head weights and a score shift that put the score out at i* when every unit is out there."""
        g = abs(self.unit_out(DOWN, self.nstar))
        assert all(abs(self.unit_out(d, self.nstar)) == g for d in units), "every |G| is the same"
        p, q = g * self.nprev, 2 * self.c - g * self.nstar
        for shift in range(self.S + 1):
            edge = self.c << shift
            lo, hi = (ceil_div(edge, q), edge // p) if score == UP else (edge // q + 1, (edge - 1) // p)
            if lo <= hi and lo <= len(units) * C.COEFF_MAX:
                parts = [lo // len(units) + (1 if j < lo % len(units) else 0) for j in range(len(units))]
                return [(-1 if (d == UP) == (score == UP) else 1) * m for d, m in zip(units, parts)], shift
        raise AssertionError("no score shift of this build brings the score across at i*")

    def state_case(self, units, score, label=None):
        """A case of E1 or E2: `units` the H units' states and `score` the score's, at i*."""
        G = [0 if d == FIT else self.unit_out(d, self.nstar) for d in units]
        head, shift = [0] * self.H, 0
        fits = [j for j, d in enumerate(units) if d == FIT]
        if score != FIT and fits:
            G[fits[0]], head[fits[0]] = self.driver(score, self.nstar, 2)
        elif score != FIT:
            head, shift = self.all_out_head(units, score)
        frames = [self.low_frame()] * (self.istar + 2)
        return Case(label or describe(units, score), self, G, head, shift, self.P, frames, self.istar, units, score)

    def none_case(self):
        """Nothing out: unit 0 just inside the bottom, unit 1 just inside the top, unit 2 driving the score just
        inside the top, at the stream's last output, i*. The next output would put them out."""
        n = self.nstar
        G, head = [0] * self.H, [0] * self.H
        G[0], G[1] = -(self.c // n), (self.c - 1) // n
        G[2], head[2] = (self.c - 1) // (2 * n), 2
        frames = [self.low_frame()] * (self.istar + 1)
        return Case("none: two units and the score at their edges", self, G, head, 0, self.P, frames, None,
                    [FIT] * self.H, FIT)

    def one_route_case(self, direction):
        """E4: no hidden layer. The source is the head's sum shifted by the score shift (0 here)."""
        n = self.nstar
        if direction == FIT:
            total, frames, at = -(self.c // n), [self.low_frame()] * (self.istar + 1), None
        else:
            total, frames, at = self.unit_out(direction, n), [self.low_frame()] * (self.istar + 2), self.istar
        return Case("no hidden layer: %s" % direction, self, None, split(total, self.K), 0, self.P, frames, at, [], direction)

    def short_score_case(self, direction, pool, at, quiet=0, label=None):
        """The score out at output `at` of a short stream, driven by unit 0 under the largest head weight;
        then `quiet` frames of zeros. FIT: every weight 0 and nothing out."""
        n = self.n_seq(pool, at + 1)
        G, head = [0] * self.H, [0] * self.H
        if direction != FIT:
            G[0], head[0] = self.driver(direction, n[at], BIG)
        frames = [self.low_frame()] * (at + 1) + [self.quiet_frame()] * quiet
        return Case(label or "the score %s at output %d" % (direction, at), self, G, head, 0, pool, frames,
                    at if direction != FIT else None, [FIT] * self.H, direction)

    def short_unit_case(self, direction, pool, quiet, label):
        """Unit 0 out at i* on a pool small enough that frames of zeros empty it; then `quiet` zeros."""
        assert pool > self.istar
        G = [0] * self.H
        G[0] = self.unit_out(direction, self.nstar)
        frames = [self.low_frame()] * (self.istar + 1) + [self.quiet_frame()] * quiet
        return Case(label, self, G, [0] * self.H, 0, pool, frames, self.istar, [direction] + [FIT] * (self.H - 1), FIT)

    def far_score_case(self, direction):
        """E6: the score's first excursion in [2^64, 2^64 + 2^63) in magnitude, at output 1 (n goes 1 to 3)."""
        g = ceil_div(ceil_div(2 * self.c, 3), BIG)
        G, head = [0] * self.H, [0] * self.H
        G[0], head[0] = g, BIG if direction == UP else -BIG
        frames = [self.low_frame()] * 4
        return Case("the score far %s: past 2^64 at its first excursion" % direction, self, G, head, 0, self.P, frames,
                    1, [FIT] * self.H, direction, far=True)

    def far_unit_reachable(self, at=7):
        """Whether unit 0 at its extreme passes 2^64 at index `at`: under s16x1 on these builds it cannot."""
        return -self.gmin * self.n_seq(self.P, at + 1)[at] >= 2 * self.c and self.gmax * self.n_seq(self.P, at + 1)[at] >= 2 * self.c

    def far_unit_case(self, direction, at=7):
        """E6: a hidden value past 2^64 at its first excursion, by a swap at index `at` from all zero weights."""
        assert self.far_unit_reachable(at)
        G = [0] * self.H
        G[0] = self.gmax if direction == UP else self.gmin
        frames = [self.low_frame()] * (at + 3)
        return Case("a hidden value far %s, by a swap at index %d" % (direction, at), self, [0] * self.H, [0] * self.H, 0,
                    self.P, frames, at, [direction] + [FIT] * (self.H - 1), FIT, swap=(at, G, [0] * self.H), far=True)

    # ---------------------------------------------------------------- the enumerations

    def every_state(self):
        """E1 at three units: every state of the four sources, none first, then by how many are out."""
        assert self.H == 3
        states = sorted(itertools.product((UP, DOWN, FIT), repeat=self.H + 1), key=lambda s: sum(x != FIT for x in s))
        return [self.none_case() if all(x == FIT for x in s) else self.state_case(list(s[:-1]), s[-1]) for s in states]

    def every_state_cut(self):
        """E1's cut set (the tier rule): none, the eight singles, all four out in two patterns."""
        keep = [c for c in self.every_state() if sum(x != FIT for x in c.units + [c.score]) <= 1]
        return keep + [self.state_case([UP, DOWN, UP], UP), self.state_case([DOWN, UP, DOWN], DOWN)]

    def twelve(self):
        """E2 at twelve units: the structure of docs/rtl/flag.md, section 3."""
        H = self.H
        alt = [UP if j % 2 == 0 else DOWN for j in range(H)]
        cases = [self.none_case()]
        for j in range(H):
            for d in (UP, DOWN):
                cases.append(self.state_case([d if x == j else FIT for x in range(H)], FIT))
        for j in range(H):
            cases.append(self.state_case([FIT if x == j else alt[x] for x in range(H)], FIT,
                                         "every unit but unit %d out, alternating" % j))
        cases.append(self.state_case([UP] * H, FIT, "all %d units up" % H))
        cases.append(self.state_case([DOWN] * H, FIT, "all %d units down" % H))
        cases.append(self.state_case(alt, FIT, "all %d units out, alternating" % H))
        cases.append(self.state_case([FIT] * H, UP))
        cases.append(self.state_case([FIT] * H, DOWN))
        cases.append(self.state_case(alt, UP, "all %d units out, alternating, and the score up" % H))
        cases.append(self.state_case(alt, DOWN, "all %d units out, alternating, and the score down" % H))
        return cases

    def twelve_cut(self):
        """E2's cut set (the tier rule)."""
        H = self.H
        alt = [UP if j % 2 == 0 else DOWN for j in range(H)]
        return [self.state_case([UP if x == H - 1 else FIT for x in range(H)], FIT),
                self.state_case([DOWN if x == H // 2 else FIT for x in range(H)], FIT),
                self.state_case([FIT if x == 0 else alt[x] for x in range(H)], FIT, "every unit but unit 0 out, alternating"),
                self.state_case(alt, UP, "all %d units out, alternating, and the score up" % H)]


def describe(units, score):
    out = ["unit %d %s" % (j, d) for j, d in enumerate(units) if d != FIT]
    if score != FIT:
        out.append("score %s" % score)
    return ", ".join(out) if out else "none"


class Case:
    """One stream: its blob (and a swap's), its frames, the output i* (None: nothing ever out) and the states there."""

    def __init__(self, label, fam, G, head, shift, pool, frames, istar, units, score, swap=None, far=False):
        self.label, self.fam, self.G, self.head, self.shift, self.pool = label, fam, G, head, shift, pool
        self.frames, self.istar, self.units, self.score, self.swap, self.far = frames, istar, list(units), score, swap, far
        self.blob = fam.blob(G, head, shift, pool)
        self.blob_b = fam.blob(swap[1], swap[2], shift, pool) if swap else None
        self.out = any(x != FIT for x in self.units) or self.score != FIT

    def evaluate(self):
        """This file's evaluator over the whole stream: a list of {'units', 'score', 'value', 'raw', 'u'}."""
        ev = self.fam.evaluator(self.G, self.head, self.shift, self.pool)
        if self.swap:
            at, G, head = self.swap
            ev.swap_at(at, [split(g, self.fam.K) for g in G], head)
        return [ev.step(i, f) for i, f in enumerate(self.frames)]

    def check(self):
        """THE CASE IS WHAT IT SAYS, by this file's arithmetic: nothing out before i*, exactly the states at i*, and
        past 2^64 there when the case says far. Returns the evaluator's per-output list."""
        said = self.evaluate()
        last = len(said) if self.istar is None else self.istar
        for i in range(last):
            assert all(x == FIT for x in said[i]["units"]) and said[i]["score"] == FIT, \
                "case '%s': a source is out at output %d, before i*" % (self.label, i)
        if self.istar is not None:
            at = said[self.istar]
            assert at["units"] == self.units and at["score"] == self.score, \
                "case '%s': at i* = %d the states are %s and %s, not the case's" % (self.label, self.istar, at["units"], at["score"])
            if self.far:
                far = [abs(u) >= 1 << FIELD for u in at["u"]] + [self.score != FIT and abs(at["raw"]) >= 1 << FIELD]
                assert any(far), "case '%s': nothing is past 2^64 at i*" % self.label
        return said

    def model(self, core_class):
        """The model core for this case, with the swap scheduled when there is one."""
        core = core_class(self.blob)
        if self.swap:
            core.write_shadow(self.blob_b)
            core.commit(self.swap[0])
        return core

    def model_agrees(self, core_class):
        """THE MODEL SAYS THE SAME: its flag 0 before i* and set from i* exactly when a source is out; its score is
        the evaluator's at every output. `core_class` is model.detector.Core, handed in. Returns the model's records."""
        said = self.check()
        core = self.model(core_class)
        records = [core.step(f) for f in self.frames]
        for i, (r, e) in enumerate(zip(records, said)):
            flagged = bool(r["flags"] & FLAG)
            want = self.out and self.istar is not None and i >= self.istar
            assert flagged == want, "case '%s': the model's flag at record %d is %s" % (self.label, i, flagged)
            assert r["score"] == e["value"], "case '%s': the model's score at record %d is %d, the evaluator's %d" % (
                self.label, i, r["score"], e["value"])
        return records

    def back_in(self):
        """The first output after i* at which every source fits again, or None."""
        said = self.evaluate()
        for i in range(self.istar + 1, len(said)):
            if all(x == FIT for x in said[i]["units"]) and said[i]["score"] == FIT:
                return i
        return None

"""The generator's refusals: one exception, a declared name, and a detail.

The shape is the model's (`model.refusal.Refusal(name, detail)`), but nothing of
`model/` is imported here: the figures are made from records, not by the model.
These names are the generator's own and are not in the definition.

    VIZ-RECORD-MISSING   a file a figure reads is not there
    VIZ-RECORD-FIELD     a field is absent, of the wrong type, not finite, or not
                         in the shape the figure reads; or a file is not JSON
    VIZ-RECORD-PAIR      two records, or two values, that a figure puts side by side
                         or draws as one disagree on what they must share (an
                         amplitude, a sigma, a Pfa, a d, a count, a tolerance's z)
    VIZ-PARSE            a line of a judge's output is not in the shape read
    VIZ-AXIS-RANGE       a value lies outside its axis, or cannot go on it
                         (a log axis given a value that is not a positive int)
    VIZ-NOT-ASCII        a text or an attribute holds a character outside
                         printable ASCII
    VIZ-UNKNOWN-FIGURE   docs/figures/ holds an .svg the registry does not make
"""

NAMES = (
    "VIZ-RECORD-MISSING",
    "VIZ-RECORD-FIELD",
    "VIZ-RECORD-PAIR",
    "VIZ-PARSE",
    "VIZ-AXIS-RANGE",
    "VIZ-NOT-ASCII",
    "VIZ-UNKNOWN-FIGURE",
)


class VizRefusal(Exception):
    """A refusal by a declared name. Anything else raised is a fault, not a refusal."""

    def __init__(self, name, detail=""):
        if name not in NAMES:
            raise ValueError("undeclared refusal name %r" % (name,))
        self.name = name
        self.detail = detail
        super().__init__("%s: %s" % (name, detail))

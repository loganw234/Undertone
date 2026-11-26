"""The one way LRN-C's scripts say no.

A refusal that means what one of the definition's refusals means carries the definition's name, read from
`spec.constants.REFUSALS` (a records file whose length is not its frames' is RUN_LENGTH). The names below are
this folder's own, the host side's, as `hw/e0c/errors.py` declares E0C's: they are not part of the contract a
bitstream advertises, and none of them is in `spec/`.

Standard library and `spec/` only.
"""
from spec import constants as C

LRNC_NAMES = (
    "SCRIPT_WINDOW",   # an operation whose canonical placement is outside its own window, an outcome no window rule
                       # covers, placements that cannot keep the script's order inside every window, or a model
                       # outcome at the canonical placement that is not the case's intended one
    "SCRIPT_LATCH",    # an operation that lands while an unmade update's QUANTISE_INPUT is latched, with no clear
                       # between: the library would raise it "latched before this call"
    "EDGES_DIFFER",    # the model's run with every operation at its window's lo, or at its hi, is not the canonical run
    "COUNTS_BY_HAND",  # the model's counts are not the layout's counts worked by hand (docs/host/lrn-c.md, section 4)
)

NAMES = tuple(C.REFUSALS) + LRNC_NAMES


class LrncRefusal(ValueError):
    """A named refusal. `name` is one of `NAMES`."""

    def __init__(self, name, detail=""):
        if name not in NAMES:
            raise ValueError("not a declared refusal name: %r" % (name,))
        self.name = name
        self.detail = detail
        super().__init__("%s: %s" % (name, detail) if detail else name)

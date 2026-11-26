"""The one way E1C's scripts say no.

A refusal that means what one of the definition's refusals means carries the
definition's name, read from `spec.constants.REFUSALS` (a record read at a
place that holds another index is RECORD_ORDER; a records file whose length is
not its frames' is RUN_LENGTH). A refusal of the comparison rules of stage E1
is `learn.errors.LearnRefusal`, under learn's own names (TRAINED_ON for a
training handed frames at or past A, the judged stretch's first frame; the
trainer's WINDOW_OUTSIDE_PERIOD; INJECTION_SET). The four names below are this
folder's own, the host side's, as `hw/e0c/errors.py` declares E0C's: they are
not part of the contract a bitstream advertises, and none of them is in
`spec/` (the lead's ruling, 2026-11-25 20:56). The first three mean what
E0C's names of the same spelling mean, on stage E1's grid of 64 frames counted
from A in place of stage E0's spans of 128.

Standard library and `spec/` only, so the box may import it.
"""
from spec import constants as C

E1C_NAMES = (
    "PIECE_CUT",      # a piece's first frame not A + 64 q; a gap, an overlap or an empty piece; a pulse a bound splits
    "PIECE_LENGTH",   # a piece of more frames than one buffer holds in one segment (hw/e0c/pieces.py, MOST_FRAMES)
    "PIECE_SET",      # pieces handed over as one part that are not its stated cut, each piece once; schedules that
                      # do not join back into the part's injection set
    "LEARNED_SET",    # a set the desktop trained that is not the set stage E1's committed part carries
)

NAMES = tuple(C.REFUSALS) + E1C_NAMES


class E1CRefusal(ValueError):
    """A named refusal. `name` is one of `NAMES`."""

    def __init__(self, name, detail=""):
        if name not in NAMES:
            raise ValueError("not a declared refusal name: %r" % (name,))
        self.name = name
        self.detail = detail
        super().__init__("%s: %s" % (name, detail) if detail else name)

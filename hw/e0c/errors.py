"""The one way E0C's scripts say no.

A refusal that means what one of the definition's refusals means carries the
definition's name, read from `spec.constants.REFUSALS` (a record read at a
place that holds another index is RECORD_ORDER; a records file whose length is
not its frames' is RUN_LENGTH). The three names below are this folder's own,
the host side's, as `learn/errors.py` and `stats/errors.py` declare theirs:
they are not part of the contract a bitstream advertises, and none of them is
in `spec/` (the lead's ruling, 2026-11-25 12:27).

Standard library and `spec/` only, so the box may import it.
"""
from spec import constants as C

E0C_NAMES = (
    "PIECE_CUT",      # a piece's first frame, or its end, not on the grid of 128; pieces that leave a gap or overlap
    "PIECE_LENGTH",   # a piece of more frames than one buffer holds in one segment (the plan's L7)
    "PIECE_SET",      # pieces handed over as one amplitude that are not its stated cut, each piece once
)

NAMES = tuple(C.REFUSALS) + E0C_NAMES


class E0CRefusal(ValueError):
    """A named refusal. `name` is one of `NAMES`."""

    def __init__(self, name, detail=""):
        if name not in NAMES:
            raise ValueError("not a declared refusal name: %r" % (name,))
        self.name = name
        self.detail = detail
        super().__init__("%s: %s" % (name, detail) if detail else name)

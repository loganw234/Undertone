"""The one way the statistics say no.

Floating point approximates by nature, so `stats/` cannot promise the model's
"exact or refused". What it does promise: an input it cannot treat honestly is
refused by name, never quietly repaired. A NaN score, a threshold asked of too
few noise scores, two injections that share noise samples: each has a name.

Where a refusal means what one of the definition's refusals means (an unknown
profile, a wrong channel count, a sample outside its range, too many taps) it
carries the definition's name, read from `spec.constants.REFUSALS`, so a stream
the model refuses is refused here under the same name. The other names are this
package's own. They are not part of the contract a bitstream advertises, and
they are declared here and nowhere else.

Nothing here imports from `model/`.
"""
from spec import constants as C

STAT_NAMES = (
    "NOT_FINITE",            # a NaN or an infinity where a number is needed
    "VALUE_TYPE",            # a bool, a string or an object where a number is needed
    "PROBABILITY_RANGE",     # a probability outside the open interval (0, 1)
    "SIGMA",                 # a noise standard deviation that is not a positive finite number
    "SHAPE",                 # an array of the wrong rank, or ragged, or of unequal lengths
    "ZERO_SET",              # a coefficient set with no non-zero value
    "INEXACT_INPUT",         # an integer too large for a float to hold exactly
    "COEFF_BITS_RANGE",      # a coefficient width outside 2..30
    "NO_INJECTIONS",         # a count over zero injections
    "INDEX_RANGE",           # an injection whose scores lie outside the stream
    "INJECTIONS_OVERLAP",    # two injections whose trials share samples
    "STRIDE_SHORT",          # signal-free scores taken closer than the filter is long
    "TOO_FEW_NOISE_SCORES",  # a threshold asked of too few signal-free scores
    "COUNT_RANGE",           # a count that is negative, or more than its trials
    "TOLERANCE_UNDEFINED",   # an efficiency so near 0 or 1 that any detector would pass
)

NAMES = tuple(C.REFUSALS) + STAT_NAMES


class StatRefusal(ValueError):
    """A named refusal. `name` is one of `NAMES`."""

    def __init__(self, name, detail=""):
        if name not in NAMES:
            raise ValueError("not a declared refusal name: %r" % (name,))
        self.name = name
        self.detail = detail
        super().__init__("%s: %s" % (name, detail) if detail else name)

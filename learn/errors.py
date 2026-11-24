"""The one way the learner, and the experiment that judges it, say no.

A refusal raised by one of the model's own functions passes through this package
unchanged, under the definition's name (an all-zero candidate is the model's
QUANTISE_INPUT; a blob of another shape is its SWAP_SHAPE). The names here are
this package's own. They are not part of the contract a bitstream advertises,
so they are declared here and nowhere else, as `stats/errors.py` declares its own.

The first five are raised inside `learn/`. The last six are raised by stage E1's
script, `tests/test_lrn_a_e1.py`, which holds the comparison rules of the design
D0, section 8; they are declared here so that every refusal a learner's result
can meet has one list.
"""

NAMES = (
    "TRAINER_INPUT",             # frames, a window, a label or a truth index that is not what the trainer takes
    "WINDOW_OUTSIDE_PERIOD",     # a labelled window that leaves the frames the trainer was given
    "WINDOW_NOT_FREE",           # a window labelled signal-free that another record's pulse touches
    "TRAINER_COUNT",             # more windows of one label than the sums hold exactly
    "CANDIDATE_SHAPE",           # weights that are not one row of equal length for each channel
    "INJECTION_SET",             # rule 1: a run on an injection set that is not the committed one
    "TRAINED_ON",                # rule 2: a figure asked of a record the learner's training reached
    "THRESHOLD_STALE",           # rule 3: a threshold applied to records of another weight epoch
    "THRESHOLD_MIXED",           # rule 3: a threshold asked of signal-free scores of two epochs
    "UNEQUAL_FALSE_ALARM_RATE",  # rule 3: models compared at thresholds that do not give each the same rate
    "NOT_THE_NAMED_MODEL",       # rule 5: a model reported that is not the one named before the run
)


class LearnRefusal(ValueError):
    """A named refusal. `name` is one of `NAMES`."""

    def __init__(self, name, detail=""):
        if name not in NAMES:
            raise ValueError("not a declared refusal name: %r" % (name,))
        self.name = name
        self.detail = detail
        super().__init__("%s: %s" % (name, detail) if detail else name)

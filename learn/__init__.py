"""The host's learner of phase A, in software: from labelled windows to one filter's coefficients.

    learn.trainer    the rule: the difference of two class means, in exact integers
    learn.handover   the weights to a blob by the model's own quantising rule, and the swap
    learn.errors     the one way this package says no

This package is NOT an authority. The reference model (`model/`) defines what the
detector does with the blob it is handed, bit for bit; the statistics (`stats/`)
judge how well the detector then finds a pulse. How the host arrives at a candidate
is ordinary software (the design D0, section 2), judged by its held-out score.

`model/` and `stats/` never import this package, and it never imports `stats/`:
what judges the learner is not in the learner. `tests/test_lrn_a_boundaries.py`
holds that. docs/model/lrn-a.md says what is done here, and what is conceded.
"""

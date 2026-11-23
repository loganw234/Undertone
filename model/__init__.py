"""The reference model: the authority.

Plain Python, integer arithmetic only, slow and obvious on purpose. The RTL,
the host library and the card are held against this bit for bit, and anything
that cannot be done exactly is refused by name (`model.refusal.Refusal`).

It defines what is deterministic. It does not say how well anything detects:
that is a statistical question with authorities of its own (the design D0,
section 2), and `stats/` holds them. Nothing here imports from `stats/`.

This file is the lead's. A parcel adds modules beside it and does not edit it.
"""

"""The host library: what drives the kernel, in simulation and on the card.

Parcel HOST, round 3. Its document is docs/host/host.md.

THE SHAPE. The library (`host.library`) is written once, as procedures: each
call is a generator that yields the operations of `host.ops` and is sent each
one's result. It does no I/O. Two drivers (`host.drive`) run the procedures:
`Host`, by calls, for a backend whose operations are calls (XRT, through
`host.backend_xrt`), and `AsyncHost`, by coroutines, for one whose operations
are coroutines (the simulated kernel, `rtl/tb/host_sim.py`, which lives beside
the benches because it imports cocotb).

WHAT IT RESTS ON. `spec.constants` for every shared fact, and `model.refusal`
for the one way to say no. Nothing else of `model/`: the blob, the record
slots and the schedule are read by this library's own code, so that a fault
in the model's code is not carried into the words the library writes
(tests/test_host_independence.py holds the imports).

It runs on Python 3.10 and later, with the standard library alone.
"""
import sys

if sys.version_info < (3, 10):
    raise ImportError("the host library needs Python 3.10 or later; this is %d.%d" % sys.version_info[:2])

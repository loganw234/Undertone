"""One piece of stage E0 on the card: `host.run_case`, unchanged, with Python's cyclic garbage collector off.

    python3 hw/e0c/run_piece.py <host.run_case's arguments>      run with the host tree as the current folder

WHY. host.run_case traces every operation of a run in a list. A full collection of the cyclic collector walks
every object it tracks, and on the desktop one took 12.1 ms with 100,000 trace-like entries held and 87.8 ms with
600,000 (MEASURED, E0C's ledger, 2026-11-25 12:24). The injector's store holds 1,024 truth records, 26.2 ms of
the stream at 200 ns a frame (COMPUTED). A piece of 6.4 million frames ends with about 193,000 entries (COMPUTED
from round 3's 2^20 trace); a collection inside it that outlasts the slack would let the stream pass truth records
the host had not yet written, and the run would be refused, INJECT_OVERLAP: a lost run (ESTIMATE; not measured on
the box). With the collector off nothing pauses for it; memory is still freed by reference counts, and nothing
run_case keeps holds a cycle (BELIEVED). The lead's ruling of 2026-11-25 12:27: this wrapper, and run_case as it is.

Everything else is run_case's: its arguments, its files (records.bin, report.json, trace.json), its one PASS line
and its exit codes. Standard library and the host tree only: nothing here imports from tests/.
"""
import gc
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main(argv):
    from host import run_case
    return run_case.main(argv)


if __name__ == "__main__":
    gc.disable()
    sys.exit(main(sys.argv[1:]))

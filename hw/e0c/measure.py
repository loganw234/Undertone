"""The desktop's measurements behind docs/host/e0c.md: what the host library's records cost, what a full collection
of Python's cyclic garbage collector costs with a run's trace held, round 3's 2^20 trace read for its parts, and how
fast `e0c.py expect` runs. Each prints its figures; none is a test, and none runs on the box.

    python hw/e0c/measure.py parse             a slot parsed by host.library.parse_slot: us a record, bytes held
    python hw/e0c/measure.py gc                one gc.collect() with 100,000, 600,000 and 1,200,000 trace entries held
    python hw/e0c/measure.py trace <trace.json> a host.run_case trace: entries, each call's span, the run, fetch, fill
    python hw/e0c/measure.py expect <folder>   cases at 4,000 trials in four pieces, and expect's time a frame

Run from the repository's root. Desktop only (`expect` imports the model and the statistics package).
"""
import gc
import json
import os
import sys
import time
import tracemalloc

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from spec import constants as C  # noqa: E402
from host import library as L  # noqa: E402
from host.drive import Entry  # noqa: E402
from host.ops import Read  # noqa: E402

PAD = bytes(L.SLOT - L.RECORD_BYTES)


def slots(n):
    return b"".join(L.SLOT_FORMAT.pack(i, 0, 0, 1595666164 * (i % 7) - 3 * i, PAD) for i in range(n))


def parse():
    n = 400000
    data = slots(n)
    best = None
    for _ in range(2):
        t0 = time.perf_counter()
        recs = [L.parse_slot(data[i * L.SLOT:(i + 1) * L.SLOT], i) for i in range(n)]
        t1 = time.perf_counter()
        best = (t1 - t0) if best is None else min(best, t1 - t0)
        del recs
    tracemalloc.start()
    recs = [L.parse_slot(data[i * L.SLOT:(i + 1) * L.SLOT], i) for i in range(200000)]
    held, _peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    del recs
    print("parse: %.2f us a record (the faster of two passes over %d), %.0f bytes a record held (200,000, tracemalloc)"
          % (best / n * 1e6, n, held / 200000))


def collect():
    for entries in (100000, 600000, 1200000):
        trace = [Entry("finish", i, Read(16 + 4 * (i % 9)), i, i, i + 1) for i in range(entries)]
        gc.collect()
        t0 = time.perf_counter()
        gc.collect()
        t1 = time.perf_counter()
        print("gc: one full collection with %d trace entries held: %.1f ms" % (entries, (t1 - t0) * 1e3))
        del trace


def trace(path):
    rows = json.load(open(path, encoding="utf-8"))
    calls = []
    for call, ordinal, _kind, _what, _result, before, after in rows:
        if ordinal == 0:
            calls.append([call, before, after, 0])
        calls[-1][2] = after
        calls[-1][3] += 1
    print("trace: %d entries, %.3f ms from the first operation to the last" % (len(rows), (rows[-1][6] - rows[0][5]) / 1e6))
    for call, a, b, n in calls:
        print("  %-10s %8d operations %10.3f ms" % (call, n, (b - a) / 1e6))
    start_at, status_at = C.REGISTERS["krn_start"][0], C.REGISTERS["krn_status"][0]
    done = 1 << C.REGISTER_BITS["krn_status"]["done"]
    t0 = next(r[5] for r in rows if r[2] == "Write" and r[3] == start_at)
    t1 = next(r[6] for r in rows if r[2] == "Read" and r[3] == status_at and r[5] > t0 and isinstance(r[4], int)
              and r[4] & done)
    reads = sum(1 for r in rows if r[2] == "Read" and r[3] == status_at and t0 < r[5] <= t1)
    print("  run: the krn_start write's call to the done read's return %.3f ms, %d status reads" % ((t1 - t0) / 1e6, reads))
    for r in rows:
        if r[2] in ("Allocate", "Fill", "Fetch"):
            print("  %s %s: %.3f ms" % (r[2], r[3], (r[6] - r[5]) / 1e6))


def expect(folder):
    from hw.e0c import e0c
    t0 = time.perf_counter()
    e0c.cases(folder, n=4000, seed_base=e0c.E0.GATE_SEED, pieces=4, timed_n=10)
    t1 = time.perf_counter()
    s = e0c.expect_amplitude(folder, 2)
    t2 = time.perf_counter()
    frames = e0c.E0.SPACING * 4001
    print("expect: %d frames in %.1f s, %.2f us a frame (cases %.1f s); found %d, noise %d"
          % (frames, t2 - t1, (t2 - t1) / frames * 1e6, t1 - t0, s["found"], s["noise_crossings"]))


if __name__ == "__main__":
    what = sys.argv[1]
    {"parse": parse, "gc": collect}.get(what, lambda: None)()
    if what == "trace":
        trace(sys.argv[2])
    elif what == "expect":
        expect(sys.argv[2])

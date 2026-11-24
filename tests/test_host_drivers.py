"""The code above the seam is one code: both drivers run the same procedures to the same operations.

WHAT THIS HOLDS. Every procedure of the library, driven once by calls (`Host`,
XRT's driver) and once by coroutines (`AsyncHost`, the simulated kernel's
driver, here under asyncio), against two copies of one scripted backend, makes
the same operations in the same order with the same values, and returns the
same results. And the two drivers offer exactly the procedures of
`host.library.PROCEDURES`.

WHAT IT DOES NOT HOLD. Anything about a kernel: the backend is `host.fake`,
words in a dict with a scripted run. The same is held on the simulated
kernel's own answers by the bench (rtl/tb/bench_host.py, same_code_both_drivers).
"""
import asyncio

from spec import constants as C
from model import source, weights

from host import fake, library as L, ops
from host.drive import Host, AsyncHost, run_by_calls

PROFILE = "s16x1"
FRAMES = 300


def e0_blob(gains=(1,)):
    return weights.matched_filter(PROFILE, C.PULSES["e0"], gains)


def scripted():
    """The first build's identity, and a kernel run by script (host.fake.scripted_kernel)."""
    return fake.scripted_kernel(PROFILE, polls_running=10)


SCHEDULE = [{"index": 5 + 70 * k, "pulse_id": 0, "amplitude_num": 3 + k, "amplitude_den": 2} for k in range(4)]


def calls(host_like, table):
    """The sequence both drivers are put through: every procedure, in a run's order."""
    yield "open", (), {}
    yield "reset", (), {}
    yield "load", (e0_blob(),), {"epoch": 3}
    yield "swap", (e0_blob((-1,)), 40), {}
    yield "start", (2026112401, table, FRAMES, SCHEDULE), {"ahead": 1}
    yield "step", (), {}
    yield "finish", (20,), {}
    yield "records", (), {}
    yield "write_shadow", (e0_blob(),), {}
    yield "commit", (FRAMES + 10,), {}
    yield "run", (7, table, 20, []), {"polls": 20}
    yield "refusals", (), {}
    yield "raw_read", (L.offset("id"),), {}
    yield "raw_write", (L.offset("refusal"), 0), {}


def drive_sync(table):
    backend = scripted()
    trace = []
    host = Host(backend, trace=trace)
    results = [getattr(host, name)(*args, **kw) for name, args, kw in calls(host, table)]
    return trace, results


def drive_async(table):
    backend = scripted()
    trace = []
    host = AsyncHost(fake.AsyncRegisters(backend), trace=trace)

    async def go():
        return [await getattr(host, name)(*args, **kw) for name, args, kw in calls(host, table)]
    return trace, asyncio.run(go())


def keyed(trace):
    return [(e.call, e.ordinal, ops.key(e.op), ops.result_key(e.result)) for e in trace]


def test_host_drivers_offer_exactly_the_procedures():
    for front in (Host, AsyncHost):
        offered = sorted(n for n in L.PROCEDURES if callable(getattr(front, n, None)))
        assert offered == sorted(L.PROCEDURES), front
    assert len(L.PROCEDURES) == 14


def test_host_drivers_make_the_same_operations():
    table = source.gaussian_table(3, 1)
    sync_trace, sync_results = drive_sync(table)
    async_trace, async_results = drive_async(table)
    assert keyed(sync_trace) == keyed(async_trace)
    assert sync_results == async_results
    # Every procedure made operations, and the run fed truth while it ran: 1 before the start, 3 after.
    assert {e.call for e in sync_trace} == set(L.PROCEDURES)
    report = sync_results[6]
    assert (report["truth_before_start"], report["truth_while_running"], report["records"]) == (1, 3, FRAMES)
    records = sync_results[7]
    assert [r["index"] for r in records] == list(range(FRAMES)) and records[9]["score"] == 13


def test_host_drivers_trace_their_times_in_order():
    trace, _ = drive_sync(source.gaussian_table(3, 1))
    times = [t for e in trace for t in (e.before, e.after)]
    assert times == sorted(times) and len(set(times)) == len(times)


def test_host_drivers_a_driver_that_loses_one_result_is_seen():
    """The comparison above, handed a call driver whose backend answers the first read of inj_pending with a
    full store, reports it: the library then feeds a round later, and the operations part from there."""
    table = source.gaussian_table(3, 1)
    backend = scripted()
    trace = []
    host = Host(backend, trace=trace)
    plain = backend.do
    state = {"lost": False}

    def lossy(op):
        result = plain(op)
        if type(op) is ops.Read and op.offset == L.offset("inj_pending") and not state["lost"]:
            state["lost"] = True
            return 1
        return result
    backend.do = lossy
    for name, args, kw in calls(host, table):
        getattr(host, name)(*args, **kw)
    async_trace, _ = drive_async(table)
    assert state["lost"]
    mine, theirs = keyed(trace), keyed(async_trace)
    first = next(i for i, (a, b) in enumerate(zip(mine, theirs)) if a != b)
    assert mine[first][2] == ("Read", L.offset("inj_pending")) and mine[first][3] == 1, mine[first]


def test_host_drivers_close_the_procedure_on_a_backend_failure():
    backend = fake.Registers(fake.identity_words(PROFILE))

    def broken(op):
        raise OSError("the backend failed")
    backend.do = broken
    procedure = L.Library().open()
    try:
        run_by_calls(procedure, backend)
    except OSError as e:
        assert "failed" in str(e)
    else:
        raise AssertionError("a backend's failure was not raised")
    assert procedure.gi_frame is None

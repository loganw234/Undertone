"""The two drivers: the library's procedures run by calls, or by coroutines.

    Host(backend)        each method runs a procedure to its end: `backend.do(op)` is a call. For XRT.
    AsyncHost(backend)   each method is a coroutine: `await backend.do(op)`. For the simulated kernel.

Both classes are made from ONE list, `host.library.PROCEDURES`, by the two
pairs of functions below, which differ only in `async` and `await`. Every check, every write
and every decision is in the procedures; a driver hands each operation to the
backend and its result back, and does nothing else.

THE TRACE. A driver given a list (`trace=[]`) appends one `Entry` for every
operation: the call it belongs to, its place among that call's operations
(from 0), the operation, its result, and `backend.now()` just before the
backend is handed it and just after it answers. On a host `now()` is
`time.perf_counter_ns()`; in simulation it counts clock edges. The card day
times a swap from it (docs/host/host.md, section 6).

A backend's own failure (an exception from `do`) closes the procedure and goes
to the caller as it is: an XRT failure is Python's OSError, not a refusal.
"""
from collections import namedtuple

from host.library import Library, PROCEDURES

Entry = namedtuple("Entry", "call ordinal op result before after")


def run_by_calls(procedure, backend, trace=None, call=""):
    """Run one procedure to its end, by calls. Returns what the procedure returns."""
    result, ordinal = None, 0
    try:
        op = procedure.send(None)
        while True:
            before = backend.now()
            result = backend.do(op)
            after = backend.now()
            if trace is not None:
                trace.append(Entry(call, ordinal, op, result, before, after))
            ordinal += 1
            op = procedure.send(result)
    except StopIteration as stop:
        return stop.value
    finally:
        procedure.close()


async def run_by_coroutines(procedure, backend, trace=None, call=""):
    """Run one procedure to its end, awaiting each operation. Returns what the procedure returns."""
    result, ordinal = None, 0
    try:
        op = procedure.send(None)
        while True:
            before = backend.now()
            result = await backend.do(op)
            after = backend.now()
            if trace is not None:
                trace.append(Entry(call, ordinal, op, result, before, after))
            ordinal += 1
            op = procedure.send(result)
    except StopIteration as stop:
        return stop.value
    finally:
        procedure.close()


def _by_calls(name):
    def call(self, *args, **kwargs):
        return run_by_calls(getattr(self.library, name)(*args, **kwargs), self.backend, self.trace, name)
    call.__name__ = name
    call.__doc__ = getattr(Library, name).__doc__
    return call


def _by_coroutines(name):
    async def call(self, *args, **kwargs):
        return await run_by_coroutines(getattr(self.library, name)(*args, **kwargs), self.backend, self.trace, name)
    call.__name__ = name
    call.__doc__ = getattr(Library, name).__doc__
    return call


class _Front:
    def __init__(self, backend, library=None, trace=None):
        self.backend = backend
        self.library = Library() if library is None else library
        self.trace = trace

    @property
    def identity(self):
        """What `open` read: the identity block, every capability register, the build's profile."""
        return self.library.identity


class Host(_Front):
    """The library over a backend whose operations are calls (XRT)."""


class AsyncHost(_Front):
    """The library over a backend whose operations are coroutines (the simulated kernel)."""


for _name in PROCEDURES:
    setattr(Host, _name, _by_calls(_name))
    setattr(AsyncHost, _name, _by_coroutines(_name))

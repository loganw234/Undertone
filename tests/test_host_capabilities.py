"""D0's gate "capability bits", on the host's side: a blob past what the build advertises is refused by the
library, by the bound's name, before any write reaches a backend.

WHAT THIS HOLDS. A backend answers the identity block of a build whose
capability registers are smaller than the definition's, one bound at a time.
For each bound a blob one past it is refused by that bound's name by `load`
and by `swap`, and the backend was handed no Write, WriteMany, Allocate or
Fill (`host.ops.EFFECTS`): only the reads of `open`. A blob AT each bound is
loaded, so the check is not one that refuses everything.

WHAT IT DOES NOT HOLD. That a real build's registers say what it takes: that
is the kernel's capability gate (KRNL, `capability-bits`, in the stage
rtl-benches). The backend here is `host.fake`: it models no kernel.

ITS CONTROL. A library that does not hold the blob to the build before it
writes, made here as a subclass, is handed the same blobs: the same check
reports the writes that reached the backend.
"""
from spec import constants as C
from model import weights
from model.refusal import Refusal

from host import fake, library as L, ops
from host.drive import Host

PASS, ABS = C.RECTIFIERS["pass"], C.RECTIFIERS["abs"]


def blob(profile="s16x1", k=1, taps=2, rect=PASS, pool=1, shift=0, hidden=0, hidden_shift=0, between=PASS, chans=None):
    chans = chans or [0]
    filters = [dict((c, [1 + c] * taps) for c in chans) for _ in range(k)]
    if hidden == 0:
        return weights.pack(profile, filters, [1] * k, rect, pool, shift)
    return weights.pack(profile, filters, [1] * hidden, rect, pool, shift, [[1] * k for _ in range(hidden)],
                        hidden_shift, between)


# (the bound's name, the build's registers changed, a blob at the bound, a blob one past it)
CASES = (
    ("PROFILE_UNKNOWN", "s16x1", {}, blob(), blob("s24x3")),
    ("BLOB_FORMAT", "s16x1", {"cap_blob_versions": 1 << 1}, blob(), blob(hidden=1)),
    ("SHAPE_FILTERS", "s16x1", {"cap_filters": 2, "cap_rows": 2}, blob(k=2), blob(k=3)),
    ("SHAPE_TAPS", "s16x1", {"cap_taps": 8}, blob(taps=8), blob(taps=9)),
    ("SHAPE_RECTIFIER", "s16x1", {"cap_rectifiers": 1 << PASS}, blob(rect=PASS), blob(rect=ABS)),
    ("SHAPE_SHIFT", "s16x1", {"cap_score_shift": 10}, blob(shift=10), blob(shift=11)),
    ("SHAPE_POOL", "s16x1", {"cap_pool": 4}, blob(pool=4), blob(pool=5)),
    ("SHAPE_HIDDEN", "s16x1", {"cap_hidden": 2}, blob(hidden=2), blob(hidden=3)),
    ("SHAPE_HIDDEN_SHIFT", "s16x1", {"cap_hidden_shift": 5}, blob(hidden=1, hidden_shift=5), blob(hidden=1, hidden_shift=6)),
    ("SHAPE_BETWEEN", "s16x1", {"cap_rectifiers": 1 << PASS}, blob(hidden=1, between=PASS), blob(hidden=1, between=ABS)),
    ("SHAPE_ROWS", "s24x3", {"cap_rows": 5}, blob("s24x3", k=1, chans=[0, 1, 2]), blob("s24x3", k=2, chans=[0, 1, 2])),
)


class WritesFirst(L.Library):
    """The control: a library that writes a blob without holding it to the build's capability registers."""

    def _against(self, config, ident):
        return None


def attempt(library, profile, caps, call, the_blob):
    """(the refusal's name or None, the operations that changed something below the seam)."""
    backend = fake.Registers(fake.identity_words(profile, **caps))
    host = Host(backend, library=library)
    host.open()
    if call == "swap":
        host.library.shape = L.B.shape(L.B.read(the_blob))          # as if this shape had been loaded
    try:
        if call == "load":
            host.load(the_blob)
        else:
            host.swap(the_blob, 100)
        name = None
    except Refusal as e:
        name = e.name
    return name, [op for op in backend.ops if isinstance(op, ops.EFFECTS)]


def test_gate_host_capabilities__past_each_bound_refused_before_any_write():
    for want, profile, caps, _at, past in CASES:
        for call in ("load", "swap"):
            name, effects = attempt(L.Library(), profile, caps, call, past)
            assert (name, effects) == (want, []), (want, call, name, effects[:2])


def test_gate_host_capabilities__at_each_bound_written():
    for want, profile, caps, at, _past in CASES:
        name, effects = attempt(L.Library(), profile, caps, "load", at)
        assert name is None and effects, (want, name)


def test_gate_host_capabilities__the_cases_cover_every_bound():
    assert len({c[0] for c in CASES}) == len(CASES) == 11
    changed = set()
    for case in CASES:
        changed |= set(case[2])
    assert changed == {"cap_blob_versions", "cap_filters", "cap_rows", "cap_taps", "cap_rectifiers",
                       "cap_score_shift", "cap_pool", "cap_hidden", "cap_hidden_shift"}


def test_control_host_capabilities__a_library_that_writes_first_is_caught():
    for want, profile, caps, _at, past in CASES:
        name, effects = attempt(WritesFirst(), profile, caps, "load", past)
        # Every case's blob is one the definition takes, so the broken library writes each one, and the fake
        # backend refuses nothing: the check above sees the writes.
        assert effects and name is None, (want, name)

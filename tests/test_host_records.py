"""The library reads a slot as the model writes a record, and refuses a slot nothing wrote.

WHAT THIS HOLDS.
  - `host.library.parse_slot`, the library's own reader, takes back every record
    `model.records.pack` writes, followed by zeros to the slot's size, on
    seeded records and every field at both ends.
  - A slot with any byte past the record that is not zero is refused,
    RECORD_SLOT; one whose flags carry a bit the definition does not declare,
    RESERVED_BITS.
  - Through the library and a kernel run by script (`host.fake`): the run's
    slots sit at krn_buffer = the buffer's address + the guard, which is a
    multiple of the slot and not of 4,096; asking for one slot more than the
    kernel wrote meets RECORD_SLOT there, since the library filled the buffer
    with its pattern before the start; and a kernel that ignored its base,
    writing at the buffer's first byte, meets RECORD_SLOT at slot 0.

ITS CONTROL. A library that fills its buffer with zeros in place of its
pattern, made here, hands back the slot nothing wrote as a record, and the
check above reports it.
"""
import random

from spec import constants as C
from model import records, source
from model.refusal import Refusal

from host import fake, library as L
from host.drive import Host

SLOT = C.MEMORY_SLOT_BYTES
FIELDS = C.RECORDS["score"]
FLAGS_AT = sum(bits for name, bits, _s in FIELDS[:[f[0] for f in FIELDS].index("flags")]) // 8


def extremes():
    lows = {"index": 0, "epoch": 0, "flags": 0, "score": -(1 << 63)}
    highs = {"index": (1 << 64) - 1, "epoch": (1 << 32) - 1, "flags": 3, "score": (1 << 63) - 1}
    yield lows
    yield highs
    for name in lows:
        yield dict(lows, **{name: highs[name]})
        yield dict(highs, **{name: lows[name]})


def seeded():
    rng = random.Random(2026112403)
    for _ in range(500):
        yield {"index": rng.getrandbits(64), "epoch": rng.getrandbits(32), "flags": rng.randint(0, 3),
               "score": rng.randint(-(1 << 63), (1 << 63) - 1)}


def slot_of(record):
    data = records.pack("score", record)
    return data + bytes(SLOT - len(data))


def test_host_records_slots_read_as_the_model_packs():
    n = 0
    for record in list(extremes()) + list(seeded()):
        assert L.parse_slot(slot_of(record), 0) == record
        n += 1
    assert n == 510 and L.RECORD_BYTES == len(records.pack("score", {"index": 0, "epoch": 0, "flags": 0, "score": 0}))


def refusal(data):
    try:
        L.parse_slot(data, 7)
    except Refusal as e:
        return e.name
    return None


def test_host_records_a_slot_nothing_wrote_is_refused():
    assert refusal(bytes([L.PATTERN]) * SLOT) == "RECORD_SLOT"
    good = slot_of({"index": 1, "epoch": 2, "flags": 1, "score": -3})
    for at in range(L.RECORD_BYTES, SLOT):
        bad = bytearray(good)
        bad[at] = 1
        assert refusal(bytes(bad)) == "RECORD_SLOT", at
    assert refusal(good) is None


def test_host_records_a_flag_not_declared_is_refused():
    for bit in range(8):
        flags = 1 << bit
        data = bytearray(slot_of({"index": 0, "epoch": 0, "flags": 0, "score": 0}))
        data[FLAGS_AT] = flags
        want = "RESERVED_BITS" if flags & C.FLAGS_RESERVED_MASK else None
        assert refusal(bytes(data)) == want, bit


def a_run(library, frames=40, written=None, ignore_base=False):
    backend = fake.scripted_kernel("s16x1", polls_running=2, written=written, ignore_base=ignore_base)
    host = Host(backend, library=library)
    host.open()
    report = None
    try:
        report = host.run(5, source.gaussian_table(2, 1), frames, [], polls=10)
    except Refusal as e:
        report = e.name
    return backend, host, report


def test_host_records_sit_past_a_guard_at_krn_buffer():
    backend, host, report = a_run(L.Library())
    assert report["records"] == 40
    buffer_address = backend.addresses[0]
    assert fake.value(backend, "krn_buffer") == buffer_address + L.GUARD
    assert L.GUARD % SLOT == 0 and L.GUARD % 4096 != 0 and L.GUARD > 0
    assert fake.value(backend, "krn_size") == 40 * SLOT
    got = host.records()
    assert [r["index"] for r in got] == list(range(40))
    assert bytes(backend.memory[0][:L.GUARD]) == bytes([L.PATTERN]) * L.GUARD


def first_refusal(host, **kw):
    try:
        host.records(**kw)
    except Refusal as e:
        return e.name, e.detail
    return None


def check_unwritten_slot_refused(library):
    """The check: a run that wrote 30 of its 40 slots; the library's count is 30, so ask for slot 30 itself."""
    _backend, host, report = a_run(library, written=30)
    assert report == "RUN_LENGTH"           # observed: done with 30 of 40 and nothing latched
    host.library.run_state.records = 31     # as if the kernel had said 31: slot 30 is one nothing wrote
    return first_refusal(host)


def test_host_records_one_slot_more_than_written_is_refused():
    name, detail = check_unwritten_slot_refused(L.Library())
    assert name == "RECORD_SLOT" and "slot 30" in detail


def test_host_records_a_kernel_that_ignored_its_base_is_refused():
    _backend, host, report = a_run(L.Library(), ignore_base=True)
    assert report["records"] == 40
    name, detail = first_refusal(host)
    assert name == "RECORD_SLOT" and "slot 0" in detail


def test_host_records_control_a_buffer_filled_with_zeros_passes_the_unwritten_slot():
    class ZeroFill(L.Library):
        pattern = 0
    assert check_unwritten_slot_refused(ZeroFill()) is None

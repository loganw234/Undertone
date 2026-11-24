"""The XRT backend's Python: each operation makes the shim's calls in the order that keeps a buffer honest.

WHAT THIS HOLDS, with a fake shim in place of host/xrt_shim.cpp, which keeps a
HOST copy and a DEVICE copy of every buffer, as XRT does:
  - Fetch synchronises from the device and then reads, over the same bytes;
    so a record the device holds is what comes back, and not the host's stale
    copy. Fill writes and then synchronises to the device.
  - Read, Write and WriteMany reach the shim's register calls as given, a batch
    in one call, in order; Allocate hands back the shim's address; the memory
    group asked of `open` is the override, or -1 for "find it in the image";
    and the buffer argument's offset handed to `open` is krn_buffer's.
  - A failure the shim reports is raised as OSError at that call, and the
    ctypes layer turns a non-zero return into one with the shim's message.
  - `close` frees every buffer it allocated, then the device.

ITS CONTROL. A backend whose Fetch reads before it synchronises, made here, hands
back the host's copy, the library's pattern, where the device holds a record:
the check above reports it.

WHAT IT DOES NOT HOLD: anything of XRT. The shim has never been compiled by its
author; whether XRT does what its calls say is the lead's to see under hardware
emulation and on the card (docs/host/host.md, limits).
"""
import ctypes

from spec import constants as C

from host import backend_xrt as X
from host import ops


class FakeShim:
    def __init__(self, fail=None):
        self.calls, self.fail = [], fail or set()
        self.registers, self.host, self.device = {}, {}, {}
        self.freed, self.closed = [], False

    def _log(self, name, *args):
        self.calls.append((name,) + args)
        if name in self.fail:
            raise OSError("XRT shim %s: the fake was told to fail" % name)

    def open(self, xclbin, device, cu_name, buffer_offset, memory_group):
        self._log("open", xclbin, device, cu_name, buffer_offset, memory_group)
        return "handle", (3 if memory_group < 0 else memory_group)

    def close(self, handle):
        self._log("close", handle)
        self.closed = True

    def read(self, handle, where):
        self._log("read", where)
        return self.registers.get(where, 0)

    def write(self, handle, where, word):
        self._log("write", where, word)
        self.registers[where] = word

    def write_many(self, handle, pairs):
        self._log("write_many", tuple(pairs))
        for where, word in pairs:
            self.registers[where] = word

    def alloc(self, handle, size):
        bo = "bo%d" % len(self.host)
        self._log("alloc", size)
        self.host[bo], self.device[bo] = bytearray(size), bytearray(size)
        return bo, 0x4000 * (len(self.host))

    def bo_write(self, handle, bo, at, data):
        self._log("bo_write", bo, at, len(data))
        self.host[bo][at:at + len(data)] = data

    def bo_sync_to(self, handle, bo, at, size):
        self._log("bo_sync_to", bo, at, size)
        self.device[bo][at:at + size] = self.host[bo][at:at + size]

    def bo_sync_from(self, handle, bo, at, size):
        self._log("bo_sync_from", bo, at, size)
        self.host[bo][at:at + size] = self.device[bo][at:at + size]

    def bo_read(self, handle, bo, at, size):
        self._log("bo_read", bo, at, size)
        return bytes(self.host[bo][at:at + size])

    def free(self, handle, bo):
        self._log("free", bo)
        self.freed.append(bo)


def backend(shim=None, **kw):
    shim = shim or FakeShim()
    return X.Backend("image.xclbin", shim=shim, **kw), shim


def fetched_after_the_device_wrote(b, shim):
    """The check: the library's pattern filled, the device then writes a record, and a Fetch must see it."""
    buf = b.do(ops.Allocate(64))
    b.do(ops.Fill(buf, 0, bytes([0xA5]) * 64))
    shim.device[buf.handle][32:64] = bytes(range(32))           # the kernel writes slot 1 on the device
    return b.do(ops.Fetch(buf, 32, 32)) == bytes(range(32))


def test_host_xrt_fetch_and_fill_keep_the_buffer_honest():
    b, shim = backend()
    assert fetched_after_the_device_wrote(b, shim)
    names = [c[0] for c in shim.calls]
    assert names[-2:] == ["bo_sync_from", "bo_read"] and shim.calls[-2][2:] == shim.calls[-1][2:] == (32, 32)
    fill = names.index("bo_write")
    assert names[fill + 1] == "bo_sync_to" and shim.calls[fill][2:] == (0, 64) and shim.calls[fill + 1][2:] == (0, 64)


def test_host_xrt_control_a_backend_that_reads_before_it_syncs_is_seen():
    class ReadsFirst(X.Backend):
        def do(self, op):
            if type(op) is ops.Fetch:
                data = self.shim.bo_read(self.handle, op.buffer.handle, op.offset, op.size)
                self.shim.bo_sync_from(self.handle, op.buffer.handle, op.offset, op.size)
                return data
            return super().do(op)
    shim = FakeShim()
    b = ReadsFirst("image.xclbin", shim=shim)
    assert not fetched_after_the_device_wrote(b, shim)


def test_host_xrt_registers_and_buffers_reach_the_shim_as_given():
    b, shim = backend()
    assert shim.calls[0] == ("open", "image.xclbin", 0, "undertone_krnl", C.REGISTERS["krn_buffer"][0], -1)
    assert b.memory_group == 3
    b.do(ops.Write(0x104, 7))
    b.do(ops.WriteMany(((0x0F0, 1), (0x0F0, 2), (0x0F4, 3))))
    assert b.do(ops.Read(0x0F0)) == 2 and b.do(ops.Read(0x104)) == 7
    assert ("write_many", ((0x0F0, 1), (0x0F0, 2), (0x0F4, 3))) in shim.calls
    buf = b.do(ops.Allocate(100))
    assert (buf.address, buf.size) == (0x4000, 100)
    assert b.do(ops.Pause()) is None
    b2, shim2 = backend(memory_group=5)
    assert shim2.calls[0][-1] == 5 and b2.memory_group == 5


def test_host_xrt_a_shim_failure_is_raised_where_it_happens():
    for name, op in (("read", ops.Read(0x10)), ("write", ops.Write(0x10, 1)), ("write_many", ops.WriteMany(((0x10, 1),))),
                     ("alloc", ops.Allocate(64))):
        b, _shim = backend(FakeShim(fail={name}))
        try:
            b.do(op)
        except OSError as e:
            assert name in str(e)
        else:
            raise AssertionError("%s's failure was not raised" % name)
    b, shim = backend(FakeShim(fail={"bo_sync_from"}))
    buf = b.do(ops.Allocate(32))
    try:
        b.do(ops.Fetch(buf, 0, 32))
    except OSError:
        assert "bo_read" not in [c[0] for c in shim.calls]
    else:
        raise AssertionError("a failed sync was not raised")


def test_host_xrt_close_frees_every_buffer_then_the_device():
    b, shim = backend()
    for _ in range(3):
        b.do(ops.Allocate(32))
    b.close()
    assert shim.freed == ["bo0", "bo1", "bo2"] and shim.closed and shim.calls[-1][0] == "close"


def test_host_xrt_the_ctypes_layer_raises_the_shims_message():
    """CtypesShim._call over a C function of the test's own: a non-zero return is an OSError with the message."""
    class Lib:
        @staticmethod
        def ut_write(handle, where, word, err, size):
            err.value = b"XRT said no"
            return 1

        @staticmethod
        def ut_read(handle, where, out, err, size):
            out._obj.value = 0x554E4454
            return 0
    shim = X.CtypesShim.__new__(X.CtypesShim)
    shim.lib = Lib()
    try:
        shim.write("h", 0x10, 1)
    except OSError as e:
        assert "XRT said no" in str(e) and "ut_write" in str(e)
    else:
        raise AssertionError("a non-zero return was not raised")
    assert shim.read("h", 0x10) == 0x554E4454


def test_host_xrt_no_shim_is_an_oserror(monkeypatch):
    monkeypatch.delenv(X.SHIM_VARIABLE, raising=False)
    try:
        X.Backend("image.xclbin")
    except OSError as e:
        assert X.SHIM_VARIABLE in str(e)
    else:
        raise AssertionError("no shim, and no error")
    assert ctypes.sizeof(ctypes.c_uint32) == 4

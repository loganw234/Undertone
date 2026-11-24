"""The XRT backend: the seam's seven operations on the card, or under XRT's hardware emulation.

XRT 2.14 reaches a user-managed kernel's registers only from C++ (`xrt::ip`;
its Python binding has no `ip`, read by the lead in cft2204 on 2026-11-24). So
this file calls a small C++ shim, host/xrt_shim.cpp, through `ctypes`, which is
the standard library. The shim is compiled by whoever runs this, against the
machine's XRT; its first lines give the command. Nothing here can be compiled
or run on the desktop: there is no XRT there.

What each operation is, in XRT's own calls (the shim makes one call each):

    Read, Write    xrt::ip::read_register, write_register
    WriteMany      write_register in a loop in C++, in order: one Python call for a batch
    Pause          time.sleep(pause_seconds), 0 by default
    Allocate       xrt::bo(device, size, normal, the memory group of the kernel's buffer argument)
    Fill           bo.write, THEN bo.sync(XCL_BO_SYNC_BO_TO_DEVICE) over the same bytes
    Fetch          bo.sync(XCL_BO_SYNC_BO_FROM_DEVICE), THEN bo.read over the same bytes

The two orders of the last two lines are this file's, and are held by
tests/test_host_xrt.py against a fake shim that keeps a host copy and a device
copy of every buffer; its control is a backend that reads before it syncs.

THE MEMORY GROUP is found by the shim from the xclbin: the kernel's argument
whose register offset is `krn_buffer`'s, by OFFSET and never by name (XRT
called the lead's trial argument "buffer_r" where its kernel.xml said
"buffer"). `memory_group` overrides it.

A FAILURE OF XRT is Python's OSError, with the shim's message, raised at the
call that failed and never dropped: it is not a refusal of the contract.

WHAT IT CANNOT SEE: whether a write landed (a PCIe write is posted, and
`write_register` returns before it lands); whatever XRT does inside one call;
whether the memory group found is the one the kernel's master reaches.
"""
import ctypes
import os
import time

from spec import constants as C

from host.ops import Read, Write, WriteMany, Pause, Allocate, Fill, Fetch, Buffer

ERROR_BYTES = 1024
SHIM_VARIABLE = "UNDERTONE_XRT_SHIM"      # where the compiled shim is, when no path is given


class CtypesShim:
    """The shim's C functions, each checked: a non-zero return is an OSError with the shim's own message."""

    def __init__(self, path):
        self.lib = ctypes.CDLL(path)
        u32, u64, vp, cp, sz = ctypes.c_uint32, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t
        tail = [cp, sz]
        sigs = {
            "ut_open": [cp, ctypes.c_uint, cp, u32, ctypes.c_int, ctypes.POINTER(vp), ctypes.POINTER(ctypes.c_int)],
            "ut_read": [vp, u32, ctypes.POINTER(u32)],
            "ut_write": [vp, u32, u32],
            "ut_write_many": [vp, ctypes.POINTER(u32), ctypes.POINTER(u32), sz],
            "ut_alloc": [vp, u64, ctypes.POINTER(vp), ctypes.POINTER(u64)],
            "ut_bo_write": [vp, vp, u64, ctypes.c_char_p, u64],
            "ut_bo_sync_to": [vp, vp, u64, u64],
            "ut_bo_sync_from": [vp, vp, u64, u64],
            "ut_bo_read": [vp, vp, u64, ctypes.c_char_p, u64],
            "ut_free": [vp, vp],
        }
        for name, args in sigs.items():
            fn = getattr(self.lib, name)
            fn.argtypes = args + tail
            fn.restype = ctypes.c_int
        self.lib.ut_close.argtypes = [vp]
        self.lib.ut_close.restype = None

    def _call(self, name, *args):
        err = ctypes.create_string_buffer(ERROR_BYTES)
        rc = getattr(self.lib, name)(*(args + (err, ERROR_BYTES)))
        if rc != 0:
            raise OSError("XRT shim %s: %s" % (name, err.value.decode("utf-8", "replace") or "rc %d" % rc))

    def open(self, xclbin, device, cu_name, buffer_offset, memory_group):
        handle, group = ctypes.c_void_p(), ctypes.c_int()
        self._call("ut_open", xclbin.encode(), device, cu_name.encode(), buffer_offset, memory_group,
                   ctypes.byref(handle), ctypes.byref(group))
        return handle, group.value

    def close(self, handle):
        self.lib.ut_close(handle)

    def read(self, handle, where):
        word = ctypes.c_uint32()
        self._call("ut_read", handle, where, ctypes.byref(word))
        return word.value

    def write(self, handle, where, word):
        self._call("ut_write", handle, where, word)

    def write_many(self, handle, pairs):
        n = len(pairs)
        wheres = (ctypes.c_uint32 * n)(*[p[0] for p in pairs])
        words = (ctypes.c_uint32 * n)(*[p[1] for p in pairs])
        self._call("ut_write_many", handle, wheres, words, n)

    def alloc(self, handle, size):
        bo, address = ctypes.c_void_p(), ctypes.c_uint64()
        self._call("ut_alloc", handle, size, ctypes.byref(bo), ctypes.byref(address))
        return bo, address.value

    def bo_write(self, handle, bo, at, data):
        self._call("ut_bo_write", handle, bo, at, bytes(data), len(data))

    def bo_sync_to(self, handle, bo, at, size):
        self._call("ut_bo_sync_to", handle, bo, at, size)

    def bo_sync_from(self, handle, bo, at, size):
        self._call("ut_bo_sync_from", handle, bo, at, size)

    def bo_read(self, handle, bo, at, size):
        out = ctypes.create_string_buffer(size)
        self._call("ut_bo_read", handle, bo, at, out, size)
        return out.raw

    def free(self, handle, bo):
        self._call("ut_free", handle, bo)


class Backend:
    """The seam's operations on XRT. `shim` is a CtypesShim, or a test's fake with the same methods."""

    def __init__(self, xclbin, device=0, cu_name="undertone_krnl", memory_group=-1, shim=None, shim_path=None,
                 pause_seconds=0.0):
        if shim is None:
            path = shim_path or os.environ.get(SHIM_VARIABLE)
            if not path:
                raise OSError("no XRT shim: give shim_path or set %s to the compiled host/xrt_shim.cpp" % SHIM_VARIABLE)
            shim = CtypesShim(path)
        self.shim = shim
        self.pause_seconds = pause_seconds
        self.handle, self.memory_group = shim.open(xclbin, device, cu_name, C.REGISTERS["krn_buffer"][0], memory_group)
        self.buffers = []

    def now(self):
        return time.perf_counter_ns()

    def do(self, op):
        kind = type(op)
        if kind is Read:
            return self.shim.read(self.handle, op.offset)
        if kind is Write:
            self.shim.write(self.handle, op.offset, op.word)
            return None
        if kind is WriteMany:
            if op.pairs:
                self.shim.write_many(self.handle, op.pairs)
            return None
        if kind is Pause:
            if self.pause_seconds:
                time.sleep(self.pause_seconds)
            return None
        if kind is Allocate:
            bo, address = self.shim.alloc(self.handle, op.size)
            self.buffers.append(bo)
            return Buffer(bo, address, op.size)
        if kind is Fill:
            self.shim.bo_write(self.handle, op.buffer.handle, op.offset, op.data)
            self.shim.bo_sync_to(self.handle, op.buffer.handle, op.offset, len(op.data))
            return None
        if kind is Fetch:
            self.shim.bo_sync_from(self.handle, op.buffer.handle, op.offset, op.size)
            return self.shim.bo_read(self.handle, op.buffer.handle, op.offset, op.size)
        raise TypeError("not an operation of the seam: %r" % (op,))

    def close(self):
        """Free every buffer this backend allocated, then the device. A failure is raised after all are tried."""
        failed = None
        for bo in self.buffers:
            try:
                self.shim.free(self.handle, bo)
            except OSError as e:
                failed = failed or e
        self.buffers = []
        self.shim.close(self.handle)
        if failed is not None:
            raise failed

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

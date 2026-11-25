"""Which bytes does a partial sync from the device bring back, under hw_emu? No kernel runs.
argv: the image, the shim. Run with the host tree as the current folder."""
import os
import sys

sys.path.insert(0, os.getcwd())
from host.backend_xrt import CtypesShim  # noqa: E402
from spec import constants as C  # noqa: E402

xclbin, shim_path = sys.argv[1], sys.argv[2]
GUARD, SIZE = 3968, 131072
TOTAL = GUARD + SIZE
s = CtypesShim(shim_path)
h, group = s.open(xclbin, 0, "undertone_krnl", C.REGISTERS["krn_buffer"][0], -1)
bo, address = s.alloc(h, TOTAL)
print("buffer of %d bytes at device address 0x%X, memory group %s" % (TOTAL, address, group))


def ranges(data):
    out, start = [], 0
    for i in range(1, len(data) + 1):
        if i == len(data) or data[i] != data[start]:
            out.append("[%d, %d) 0x%02X" % (start, i, data[start]))
            start = i
    return "; ".join(out)


s.bo_write(h, bo, 0, bytes([0x11]) * TOTAL)
s.bo_sync_to(h, bo, 0, TOTAL)
s.bo_write(h, bo, 0, bytes([0x22]) * TOTAL)
s.bo_sync_from(h, bo, GUARD, SIZE)
print("after sync_from(at %d, %d bytes), the host's copy: %s" % (GUARD, SIZE, ranges(s.bo_read(h, bo, 0, TOTAL))))
s.bo_write(h, bo, 0, bytes([0x22]) * TOTAL)
s.bo_sync_from(h, bo, 0, TOTAL)
print("after sync_from(at 0, %d bytes), the host's copy: %s" % (TOTAL, ranges(s.bo_read(h, bo, 0, TOTAL))))
s.bo_write(h, bo, 0, bytes([0x33]) * TOTAL)
s.bo_sync_to(h, bo, GUARD, SIZE)
s.bo_write(h, bo, 0, bytes([0x22]) * TOTAL)
s.bo_sync_from(h, bo, 0, TOTAL)
print("after 0x33 sync_to(at %d, %d bytes) and a whole sync_from: %s" % (GUARD, SIZE, ranges(s.bo_read(h, bo, 0, TOTAL))))
s.free(h, bo)
s.close(h)
print("PROBE DONE")

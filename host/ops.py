"""The seam: the seven operations the library asks of a backend, and nothing else.

    Read(offset)                   -> the 32-bit word at that byte offset of the control port
    Write(offset, word)            -> None
    WriteMany(pairs)               -> None; ((offset, word), ...) written one after another, in order
    Pause()                        -> None; the backend waits a little before the library reads again
    Allocate(size)                 -> a Buffer: device memory of `size` bytes, its device address
    Fill(buffer, offset, data)     -> None; the bytes into the buffer, and synchronised to the device
    Fetch(buffer, offset, size)    -> bytes; the buffer synchronised from the device, and then read

A backend makes no decision: it does not retry, check or read back. Everything
that decides is above this seam, in `host.library`.

`Fetch` is ONE operation, the synchronisation and the read together, so that
no code above the seam can read a buffer before it has been synchronised from
the device. `Fill` is the same the other way.

A namedtuple compares as a plain tuple, so `Read(4) == Allocate(4)`. A trace
is therefore compared through `key`, which names each operation's kind.
"""
from collections import namedtuple

Read = namedtuple("Read", "offset")
Write = namedtuple("Write", "offset word")
WriteMany = namedtuple("WriteMany", "pairs")
Pause = namedtuple("Pause", "")
Allocate = namedtuple("Allocate", "size")
Fill = namedtuple("Fill", "buffer offset data")
Fetch = namedtuple("Fetch", "buffer offset size")

# What Allocate hands back. `handle` is the backend's own; the library reads `address` and `size` only.
Buffer = namedtuple("Buffer", "handle address size")

KINDS = (Read, Write, WriteMany, Pause, Allocate, Fill, Fetch)
# The operations that change something below the seam. A refusal "before any write" means none of these.
EFFECTS = (Write, WriteMany, Allocate, Fill)


def key(op):
    """An operation as a plain value that names its kind: what a trace is compared by."""
    parts = []
    for part in op:
        if isinstance(part, Buffer):
            part = ("buffer", part.address, part.size)
        elif isinstance(part, (bytes, bytearray)):
            part = bytes(part)
        elif isinstance(part, (list, tuple)):
            part = tuple(tuple(p) if isinstance(p, (list, tuple)) else p for p in part)
        parts.append(part)
    return (type(op).__name__,) + tuple(parts)


def result_key(result):
    """A result as a plain value: a Buffer by its address and size, bytes as bytes."""
    if isinstance(result, Buffer):
        return ("buffer", result.address, result.size)
    if isinstance(result, bytearray):
        return bytes(result)
    return result

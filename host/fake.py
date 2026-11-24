"""A backend of words in a dict: for the first size's tests, and for a dry run with no kernel at all.

It is NOT a kernel. A read answers what the dict holds at that offset (0 where
nothing is set) or what a hook computes; a write is recorded, and handed to a
hook where one names its offset; a buffer is a bytearray. It models no block,
no refusal and no stream. So a test against it holds the LIBRARY's logic (its
checks, its order, its reading of what it is answered) and nothing about what
a kernel does with the writes: that is the bench's, on the simulated kernel.

`identity_words(profile, **caps)` gives the identity block and the capability
registers of a build, as words by offset, for a definition-true image.
"""
from spec import constants as C

from host import library
from host.ops import Read, Write, WriteMany, Pause, Allocate, Fill, Fetch, Buffer

SLOT = C.MEMORY_SLOT_BYTES
WORD_BITS = C.BUS["word_bits"]
WORD_BYTES = WORD_BITS // 8
WORD_MASK = (1 << WORD_BITS) - 1

# The first build's capabilities (the plan's row "The first build"), as the build's registers would say them.
FIRST_BUILD = {"cap_filters": 4, "cap_taps": 128, "cap_rows": 4, "cap_pool": C.MAX_POOL,
               "cap_score_shift": C.MAX_SCORE_SHIFT, "cap_hidden": C.MAX_HIDDEN, "cap_hidden_shift": C.MAX_HIDDEN_SHIFT,
               "cap_rectifiers": sum(1 << c for c in C.RECTIFIERS.values()), "cap_blob_versions": (1 << 1) | (1 << 2),
               "cap_noise_table": C.MAX_NOISE_TABLE, "cap_inject_pending": C.MAX_INJECT_PENDING, "cap_record_queue": 512}


def value_words(name, value):
    first, _access, count = C.REGISTERS[name]
    return dict((first + WORD_BYTES * i, (value >> (WORD_BITS * i)) & WORD_MASK) for i in range(count))


def identity_words(profile, **caps):
    """The identity block and every capability register of a build of `profile`, as {offset: word}."""
    prof = C.PROFILES[profile]
    values = dict(FIRST_BUILD, cap_sample_bits=prof["sample_bits"], cap_channels=prof["channels"],
                  cap_coeff_bits=C.COEFF_BITS)
    values.update(caps)
    words = {}
    words.update(value_words("id", C.BUS["magic"]))
    words.update(value_words("spec_version", C.SPEC_VERSION))
    words.update(value_words("spec_hash", int(C.SPEC_SHA256, 16)))
    for name, value in values.items():
        words.update(value_words(name, value))
    return words


class Registers:
    """The backend. `ops` is every operation it was handed, in order."""

    def __init__(self, words=None, on_read=None, on_write=None, first_address=0x10000):
        self.words = dict(words or {})
        self.on_read = dict(on_read or {})       # offset -> function(backend) -> word
        self.on_write = dict(on_write or {})     # offset -> function(backend, word)
        self.ops = []
        self.memory = {}                         # handle -> bytearray
        self.addresses = {}                      # handle -> its device address
        self.next_address = first_address
        self.clock = 0

    def now(self):
        self.clock += 1
        return self.clock

    def _write(self, where, word):
        if where in self.on_write:
            self.on_write[where](self, word)
        else:
            self.words[where] = word

    def do(self, op):
        self.ops.append(op)
        kind = type(op)
        if kind is Read:
            if op.offset in self.on_read:
                return self.on_read[op.offset](self)
            return self.words.get(op.offset, 0)
        if kind is Write:
            self._write(op.offset, op.word)
            return None
        if kind is WriteMany:
            for where, word in op.pairs:
                self._write(where, word)
            return None
        if kind is Pause:
            return None
        if kind is Allocate:
            handle = len(self.memory)
            self.memory[handle] = bytearray(op.size)
            self.addresses[handle] = self.next_address
            buffer = Buffer(handle, self.next_address, op.size)
            self.next_address += (op.size + 4095) // 4096 * 4096 + 4096
            return buffer
        if kind is Fill:
            self.memory[op.buffer.handle][op.offset:op.offset + len(op.data)] = op.data
            return None
        if kind is Fetch:
            return bytes(self.memory[op.buffer.handle][op.offset:op.offset + op.size])
        raise TypeError("not an operation of the seam: %r" % (op,))


def value(backend, name):
    """A register's value as the writes left it in the dict, its lowest word first."""
    first, _access, count = C.REGISTERS[name]
    return sum(backend.words.get(first + WORD_BYTES * i, 0) << (WORD_BITS * i) for i in range(count))


def scripted_kernel(profile, polls_running=10, written=None, ignore_base=False, **caps):
    """Registers that run a kernel BY SCRIPT, for the library's logic and nothing else: a write of krn_start
    writes `written` slots (all the run's frames when None) at krn_buffer, each a record of its own index with
    the padding zero, and sets krn_records to that count; then `polls_running` reads of krn_status say running,
    and every later read says done. No refusal is ever latched, and inj_pending always reads 0.
    `ignore_base` writes the slots at the start of the buffer instead: a kernel that ignored krn_buffer."""
    backend = Registers(identity_words(profile, **caps))
    backend.left = None
    status_bits = C.REGISTER_BITS["krn_status"]

    def started(b, word):
        frames, base = value(b, "krn_frames"), value(b, "krn_buffer")
        count = frames if written is None else written
        handle = [h for h, at in b.addresses.items() if at <= base < at + len(b.memory[h])][0]
        at = 0 if ignore_base else base - b.addresses[handle]
        pad =bytes(SLOT - library.RECORD_BYTES)
        for i in range(count):
            b.memory[handle][at + SLOT * i:at + SLOT * (i + 1)] = library.SLOT_FORMAT.pack(i, 0, 0, 7 * i - 50, pad)
        b.words.update(value_words("krn_records", count))
        b.left = polls_running

    def status(b):
        if b.left is None:
            return 0
        if b.left > 0:
            b.left -= 1
            return 1 << status_bits["running"]
        return 1 << status_bits["done"]

    backend.on_write[C.REGISTERS["krn_start"][0]] = started
    backend.on_read[C.REGISTERS["krn_status"][0]] = status
    return backend


class AsyncRegisters:
    """The same backend, its `do` a coroutine: what the coroutine driver is handed."""

    def __init__(self, inner):
        self.inner = inner

    def now(self):
        return self.inner.now()

    async def do(self, op):
        return self.inner.do(op)

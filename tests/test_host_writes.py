"""The library's writes, against operations worked by hand: the one first-size test that holds what it writes.

WHAT THIS HOLDS. For a load of each blob version, a swap and a start, the
library's operations, as `host.fake` records them, are exactly those of
`vectors/host/writes.json`: worked by hand from the blob's format, the register
map and the design, and not by running the library or the model (the vector
says how, with its sums). The blobs are made with `model.weights.pack`: they
are the input, and nothing of the model judges the output.

WHAT IT DOES NOT HOLD. What a kernel does with these writes, and any case but
these four. The bench holds the writes through the kernel against the model.

ITS CONTROL. A library that writes the weights newest first, made here, is
reported at the first operation that differs.
"""
import json
import os

from spec import constants as C
from model import weights

from host import fake, library as L, ops
from host.drive import Host

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "vectors", "host", "writes.json"), encoding="utf-8") as _f:
    VECTOR = json.load(_f)


def where(name, word):
    return C.REGISTERS[name][0] + 4 * word


def expected(listed):
    out = []
    for op in listed:
        kind = op[0]
        if kind == "Read":
            out.append(("Read", where(op[1], op[2])))
        elif kind == "Write":
            out.append(("Write", where(op[1], op[2]), op[3]))
        elif kind == "WriteMany":
            out.append(("WriteMany", tuple((where(n, w), v) for n, w, v in op[1])))
        elif kind == "Allocate":
            out.append(("Allocate", op[1]))
        elif kind == "Fill":
            out.append(("Fill", op[1], bytes([op[3]]) * op[2]))
        else:
            raise AssertionError(kind)
    return out


def made(recorded):
    out = []
    for op in recorded:
        key = ops.key(op)
        if key[0] == "Fill":
            key = ("Fill", key[2], key[3])
        out.append(key)
    return out


def blob_of(spec):
    filters = [dict((int(c), row) for c, row in f.items()) for f in spec["filters"]]
    if "hidden" in spec:
        return weights.pack(spec["profile"], filters, spec["head"], spec["rectifier"], spec["pool"], spec["score_shift"],
                            spec["hidden"], spec["hidden_shift"], spec["between"])
    return weights.pack(spec["profile"], filters, spec["head"], spec["rectifier"], spec["pool"], spec["score_shift"])


def ready(profile, library=None):
    backend = fake.Registers(fake.identity_words(profile))
    backend.words[L.offset("krn_status")] = 1 << C.REGISTER_BITS["krn_status"]["running"]
    host = Host(backend, library=library)
    host.open()
    return host, backend


def calls_made(name, library=None):
    case = VECTOR[name]
    first = VECTOR[case["after"]] if "after" in case else case
    host, backend = ready(first["blob"]["profile"], library)
    if "after" in case:
        host.load(blob_of(first["blob"]), epoch=first["epoch"])
    mark = len(backend.ops)
    if name.startswith("load"):
        host.load(blob_of(case["blob"]), epoch=case["epoch"])
    elif name.startswith("swap"):
        host.swap(blob_of(case["blob"]), case["at"])
    else:
        host.start(case["seed"], case["table"], case["frames"], case["schedule"], ahead=case["ahead"])
    return made(backend.ops[mark:]), expected(case["ops"])


def first_difference(a, b):
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            return i
    return None if len(a) == len(b) else min(len(a), len(b))


def test_host_writes_are_the_vectors():
    for name in ("load_v1", "load_v2", "swap_v1", "start_v1"):
        mine, worked = calls_made(name)
        assert first_difference(mine, worked) is None, (name, first_difference(mine, worked))


def test_host_writes_control_weights_newest_first_is_reported():
    class NewestFirst(L.Library):
        def _words(self, config):
            out = super()._words(config)
            first = config["filters"][0]
            taps = len(first[min(first)])
            out[:taps] = reversed(out[:taps])
            return out
    mine, worked = calls_made("load_v1", NewestFirst())
    assert first_difference(mine, worked) == 3

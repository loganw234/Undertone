"""The bit-identity harness. Every RTL bench of this project compares through it.

The reference model is the authority, so the expected words come from the
model: `compare` steps a `model.detector.Core` over the same frames it drives
into the RTL, and holds every score record the RTL puts out against the
model's, as the record's canonical bytes (`model.records.pack`), in order.
Nothing is rounded, thresholded or sampled: the first word that differs, or a
count that differs, is a `Mismatch`.

THE STREAM CONTRACT a design under test keeps, by port name:

    clk, rst                rst is synchronous and active high
    in_valid, in_frame      a frame is taken at each rising edge where in_valid
                            is high. Channel c is in_frame[c*S +: S], S the
                            profile's sample bits, two's complement
    out_valid, out_record   a score record is out at each rising edge where
                            out_valid is high: the canonical bytes read as one
                            little-endian number, so the first declared field
                            is lowest

`compare` drives with gaps: between frames in_valid falls for a number of
clocks drawn from a seeded generator, so a design that only works on an
unbroken stream is seen. There is no back-pressure in the contract: the design
takes a frame whenever one is offered.

THE PIECES, for a bench whose words are not score records (the source's
samples, say): `exchange` drives words into one pair of ports and collects the
words out of another, and `hold` is the comparison itself, with its evidence.
`compare` is those two with the model's core between them.

WHAT IT REPORTS. `compare` returns an `Identity` (how many records, the digest
of each side by `model.records.digest`'s rule, the latencies seen) or raises
`Mismatch`. Either way, when the environment names a file in
UNDERTONE_EVIDENCE, `hold` appends one JSON line there saying which. The
`rtl-benches` stage reads the results file cocotb writes AND that line: a
bench's verdict is never an exit code.

WHAT IT DOES NOT DO, each a stated limit:
  - It does not configure the design. The bench loads the weights its own way
    and hands `compare` a model core built from the same configuration. A bench
    that loads one thing into the RTL and another into the model is reported as
    a mismatch, which is the point; a bench that loads the same wrong thing
    into both is not seen here.
  - It does not check latency. It reports, for each record, how many clocks
    after its frame was taken the record was seen; a bench that states a
    latency asserts on `Identity.latencies` itself.
  - It does not model back-pressure, a stalled output, or a second clock.
  - It stops listening `settle` clocks after the last word is due, and waits at
    most `max_latency` clocks for it. A word the design would put out later
    than that is not seen, and shows as a COUNT mismatch.
  - A model refusal (a frame the model refuses) propagates as the model's own
    `Refusal`, before anything is driven: nothing is compared.
  - An X or a Z in the output word while its valid is high, or in the valid
    itself, is a Mismatch. One in the word while valid is low is not looked at.
"""
import hashlib
import json
import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge

from spec import constants as C
from model import records, stream

MARK = "BIT-IDENTITY"
RECORD_BITS = sum(f[1] for f in C.RECORDS["score"])
RECORD_BYTES = RECORD_BITS // 8
SCORE_PREFIX = records.DIGEST_PREFIX + b"score" + b"\x00"     # so a digest here is model.records.digest's


class Mismatch(AssertionError):
    """The RTL's words are not the model's. `kind` is WORD, COUNT or UNKNOWN-BITS; `at` is the
    position, counted from 0 in the order the words came out, of the first one that differs."""

    def __init__(self, kind, at, detail):
        super().__init__("%s MISMATCH %s at record %d: %s" % (MARK, kind, at, detail))
        self.kind, self.at, self.detail = kind, at, detail


class NothingCompared(AssertionError):
    """No word was expected. Zero words compared is not a pass."""


class Identity:
    def __init__(self, count, model_digest, dut_digest, latencies):
        self.count, self.model_digest, self.dut_digest, self.latencies = count, model_digest, dut_digest, latencies


def frame_word(profile_name, frame):
    """A frame as the number in_frame carries. The model's own check refuses a bad frame first."""
    prof = stream.profile(profile_name)
    stream.check_frame(prof, frame)
    bits, word = prof["sample_bits"], 0
    for c, sample in enumerate(frame):
        word |= (sample & ((1 << bits) - 1)) << (c * bits)
    return word


def record_word(record):
    """A score record as the number out_record carries: its canonical bytes, little-endian."""
    return int.from_bytes(records.pack("score", record), "little")


def fields_of(word):
    """The fields of a record word, for a message. Never used to decide anything."""
    out, at = {}, 0
    for name, bits, sign in C.RECORDS["score"]:
        v = (word >> at) & ((1 << bits) - 1)
        if sign == "signed" and v >> (bits - 1):
            v -= 1 << bits
        out[name] = v
        at += bits
    return out


def describe_records(have, want):
    a, b = fields_of(have), fields_of(want)
    differing = [n for n in b if a[n] != b[n]]
    return "field(s) %s differ: the RTL has %s, the model %s" % (
        ", ".join(differing), {n: a[n] for n in differing}, {n: b[n] for n in differing})


def describe_words(have, want):
    return "the RTL has 0x%X, the model 0x%X" % (have, want)


def _digest(prefix, words, width_bytes):
    h = hashlib.sha256(prefix)
    for w in words:
        h.update(w.to_bytes(width_bytes, "little"))
    return h.hexdigest()


def _evidence(test, label, **what):
    path = os.environ.get("UNDERTONE_EVIDENCE")
    if path:
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(dict(what, mark=MARK, test=test, label=label), sort_keys=True) + "\n")


def start_clock(dut, period_ns=10):
    Clock(dut.clk, period_ns, unit="ns").start()


async def reset(dut, clocks=3):
    """Hold rst high for some clocks with nothing offered, then release it on a falling edge."""
    await FallingEdge(dut.clk)
    dut.rst.value = 1
    dut.in_valid.value = 0
    dut.in_frame.value = 0
    for _ in range(clocks):
        await FallingEdge(dut.clk)
    dut.rst.value = 0


async def exchange(dut, words_in, expect, *, in_valid="in_valid", in_data="in_frame", out_valid="out_valid",
                   out_data="out_record", gap_seed=0, max_gap=2, max_latency=64, settle=8):
    """Drive `words_in` into one pair of ports, with gaps, and collect the words that come out of another.

    Listens until `expect` words are seen or `max_latency` clocks have passed since the last word went in,
    then `settle` clocks more, so that a word too many is seen. Returns (the words seen, the clock each was
    seen at, the clock each word in was taken at, None or (position, what) for the first X or Z).
    All four port names are arguments; the clock is dut.clk.
    """
    valid_in, data_in = getattr(dut, in_valid), getattr(dut, in_data)
    valid_out, data_out = getattr(dut, out_valid), getattr(dut, out_data)
    seen, seen_at, sent_at, state = [], [], [], {"clock": 0, "listening": True, "unknown": None}

    async def monitor():
        while state["listening"]:
            await RisingEdge(dut.clk)
            state["clock"] += 1
            valid = str(valid_out.value)
            if valid not in ("0", "1"):
                state["unknown"] = state["unknown"] or (len(seen), "%s = %s" % (out_valid, valid))
                continue
            if valid == "1":
                value = data_out.value
                if not value.is_resolvable:
                    state["unknown"] = state["unknown"] or (len(seen), "%s = %s" % (out_data, value))
                    seen.append(0)
                else:
                    seen.append(value.to_unsigned())
                seen_at.append(state["clock"])

    task = cocotb.start_soon(monitor())
    gaps = random.Random(gap_seed)
    for word in words_in:
        for _ in range(gaps.randint(0, max_gap)):
            await FallingEdge(dut.clk)
            valid_in.value = 0
        await FallingEdge(dut.clk)
        valid_in.value = 1
        data_in.value = word
        sent_at.append(state["clock"] + 1)      # the rising edge that takes this word
    await FallingEdge(dut.clk)
    valid_in.value = 0
    waited = 0
    while len(seen) < expect and waited < max_latency:
        await FallingEdge(dut.clk)
        waited += 1
    for _ in range(settle):                     # a word too many would come out here
        await FallingEdge(dut.clk)
    state["listening"] = False
    await task
    return seen, seen_at, sent_at, state["unknown"]


def hold(test, label, seen, expected, *, width_bytes, prefix, describe=describe_words, unknown=None, **noted):
    """THE COMPARISON. `seen` are the RTL's words and `expected` the model's, in order.

    Raises Mismatch at the first word that differs, or when the counts differ, or when `unknown` says an X
    or a Z was seen. Otherwise returns (count, the model's digest, the RTL's digest), each digest a SHA-256
    over `prefix` and then every word as `width_bytes` little-endian bytes. Either way it leaves one line of
    evidence. `noted` goes into the line of an identical comparison as it is given.
    """
    if not expected:
        raise NothingCompared("%s: nothing was expected; zero words compared is not a pass" % MARK)
    try:
        if unknown:
            raise Mismatch("UNKNOWN-BITS", unknown[0], unknown[1])
        for i, (have, want) in enumerate(zip(seen, expected)):
            if have != want:
                raise Mismatch("WORD", i, describe(have, want))
        if len(seen) != len(expected):
            raise Mismatch("COUNT", min(len(seen), len(expected)),
                           "the RTL put out %d record(s), the model %d" % (len(seen), len(expected)))
    except Mismatch as e:
        _evidence(test, label, verdict="MISMATCH", kind=e.kind, at=e.at, detail=e.detail,
                  rtl_records=len(seen), model_records=len(expected))
        raise
    model_digest, rtl_digest = _digest(prefix, expected, width_bytes), _digest(prefix, seen, width_bytes)
    _evidence(test, label, verdict="IDENTICAL", records=len(expected), model_digest=model_digest,
              rtl_digest=rtl_digest, **noted)
    return len(expected), model_digest, rtl_digest


async def compare(dut, core, frames, *, test, label, gap_seed=0, max_gap=2, max_latency=64, settle=8):
    """Drive `frames` into the design and into the model core; hold every record against the model's.

    `core` is a `model.detector.Core` that has produced nothing yet, built from
    the configuration the bench loaded into the design. `test` is the name of
    the cocotb test calling this, and `label` says which run of it: both go
    into the evidence line. Call `reset` first.
    """
    profile_name = core.store.config["profile"]
    frames = list(frames)
    if not frames:
        raise NothingCompared("%s: no frame was given; zero records compared is not a pass" % MARK)
    words_in = [frame_word(profile_name, f) for f in frames]
    expected = [record_word(core.step(f)) for f in frames]      # the model: the authority
    seen, seen_at, sent_at, unknown = await exchange(dut, words_in, len(expected), gap_seed=gap_seed, max_gap=max_gap,
                                                     max_latency=max_latency, settle=settle)
    latencies = sorted(set(s - t for s, t in zip(seen_at, sent_at)))
    count, model_digest, rtl_digest = hold(test, label, seen, expected, width_bytes=RECORD_BYTES, prefix=SCORE_PREFIX,
                                           describe=describe_records, unknown=unknown, latencies=latencies)
    return Identity(count, model_digest, rtl_digest, latencies)

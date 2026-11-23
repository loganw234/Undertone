#!/usr/bin/env python3
"""A small reader for miniSEED 2 files, written for study D1b. Standard library only.

    python docs/studies/d1/mseed.py --self-test
    python docs/studies/d1/mseed.py FILE [FILE ...]      a table of what each file is

WHY NOT A PACKAGE
  The first look needs things a package hides: each record's encoding, its
  length, the widths the samples are stored in. So the headers are read here.
  The samples are decoded here too, and then held against a second reader,
  the package obspy, sample for sample (compare_readers.py). Neither is
  trusted alone.

WHAT IT READS
  Fixed-length data records with a 48-byte header and a blockette 1000,
  big-endian, with samples in Steim-1 (encoding 10) or Steim-2 (encoding 11).
  Anything else is refused by name: another encoding, little-endian words, a
  record without blockette 1000, a record whose last decoded sample is not
  the one its own first frame names.

THE CHECK INSIDE EVERY RECORD
  A Steim record carries its first sample and its last sample in its first
  frame. The decoder adds up differences from the first; if the sum does not
  land on the last, the record is refused. A decoder that drops, doubles or
  misreads one difference is caught by that.

WHAT IT CANNOT SEE
  - Whether the samples are what the ground did. They are what the file holds.
  - An error that leaves both the first and the last sample right, such as
    two wrong differences that cancel.
  - A time that the data logger got wrong.
"""
import struct
import sys
from datetime import datetime, timedelta, timezone

ENCODINGS = {10: "Steim-1", 11: "Steim-2"}


class Refusal(Exception):
    pass


def signed(value, bits):
    """The two's-complement reading of the low `bits` bits of value."""
    value &= (1 << bits) - 1
    return value - (1 << bits) if value >> (bits - 1) else value


def decode_steim(data, nsamp, encoding):
    """(samples, widths): the record's samples and a count of differences by width."""
    if len(data) % 64:
        raise Refusal("DATA-NOT-WHOLE-FRAMES: %d bytes" % len(data))
    diffs, widths = [], {}
    x0 = xn = None
    for f in range(len(data) // 64):
        words = struct.unpack(">16I", data[f * 64:f * 64 + 64])
        ctrl = words[0]
        for i in range(1, 16):
            nib = (ctrl >> (30 - 2 * i)) & 3
            w = words[i]
            if f == 0 and i == 1:
                x0 = signed(w, 32)
                continue
            if f == 0 and i == 2:
                xn = signed(w, 32)
                continue
            if nib == 0:
                continue
            if nib == 1:
                parts = [(w >> s) & 0xFF for s in (24, 16, 8, 0)]
                bits = 8
            elif encoding == 10:
                if nib == 2:
                    parts, bits = [(w >> 16) & 0xFFFF, w & 0xFFFF], 16
                else:
                    parts, bits = [w], 32
            else:
                dnib = (w >> 30) & 3
                if nib == 2:
                    if dnib == 1:
                        parts, bits = [w & 0x3FFFFFFF], 30
                    elif dnib == 2:
                        parts, bits = [(w >> 15) & 0x7FFF, w & 0x7FFF], 15
                    elif dnib == 3:
                        parts, bits = [(w >> s) & 0x3FF for s in (20, 10, 0)], 10
                    else:
                        raise Refusal("STEIM2-BAD-DNIB: nibble 2, dnib 0")
                else:
                    if dnib == 0:
                        parts, bits = [(w >> s) & 0x3F for s in (24, 18, 12, 6, 0)], 6
                    elif dnib == 1:
                        parts, bits = [(w >> s) & 0x1F for s in (25, 20, 15, 10, 5, 0)], 5
                    elif dnib == 2:
                        parts, bits = [(w >> s) & 0xF for s in (24, 20, 16, 12, 8, 4, 0)], 4
                    else:
                        raise Refusal("STEIM2-BAD-DNIB: nibble 3, dnib 3")
            for part in parts:
                diffs.append(signed(part, bits))
            widths[bits] = widths.get(bits, 0) + len(parts)
    if x0 is None or xn is None:
        raise Refusal("NO-FIRST-FRAME")
    if len(diffs) < nsamp:
        raise Refusal("TOO-FEW-DIFFERENCES: %d for %d samples" % (len(diffs), nsamp))
    samples = [x0]
    for d in diffs[1:nsamp]:
        samples.append(samples[-1] + d)
    if nsamp and samples[-1] != xn:
        raise Refusal("LAST-SAMPLE-MISMATCH: decoded %d, the record says %d" % (samples[-1], xn))
    # the widths count includes padding differences after the last sample
    return samples, widths


def parse_record(rec):
    """One record as a dict. Raises Refusal for anything outside what is read."""
    if len(rec) < 64:
        raise Refusal("SHORT-RECORD: %d bytes" % len(rec))
    quality = rec[6:7].decode("ascii", "replace")
    if quality not in "DRQM":
        raise Refusal("NOT-A-DATA-RECORD: quality %r" % quality)
    year, doy, hh, mm, ss, _, frac = struct.unpack(">HHBBBBH", rec[20:30])
    nsamp, factor, mult = struct.unpack(">Hhh", rec[30:36])
    nblk = rec[39]
    tcorr, data_at, blk_at = struct.unpack(">iHH", rec[40:48])
    if factor > 0 and mult > 0:
        rate = float(factor * mult)
    elif factor > 0 and mult < 0:
        rate = factor / -mult
    elif factor < 0 and mult > 0:
        rate = mult / -factor
    elif factor < 0 and mult < 0:
        rate = 1.0 / (factor * mult)
    else:
        raise Refusal("NO-SAMPLE-RATE")
    start = datetime(year, 1, 1, hh, mm, ss, frac * 100, tzinfo=timezone.utc) \
        + timedelta(days=doy - 1)
    enc = order = reclen = None
    micro = 0
    at, seen = blk_at, 0
    while at and seen < nblk:
        kind, nxt = struct.unpack(">HH", rec[at:at + 4])
        if kind == 1000:
            enc, order, power = rec[at + 4], rec[at + 5], rec[at + 6]
            reclen = 1 << power
        elif kind == 1001:
            micro = struct.unpack(">b", rec[at + 5:at + 6])[0]
        at, seen = nxt, seen + 1
    if enc is None:
        raise Refusal("NO-BLOCKETTE-1000")
    if order != 1:
        raise Refusal("NOT-BIG-ENDIAN: word order %d" % order)
    if enc not in ENCODINGS:
        raise Refusal("ENCODING-NOT-READ: %d" % enc)
    start += timedelta(microseconds=micro)
    return {
        "sequence": rec[0:6].decode("ascii", "replace"), "quality": quality,
        "station": rec[8:13].decode("ascii").strip(), "location": rec[13:15].decode("ascii").strip(),
        "channel": rec[15:18].decode("ascii").strip(), "network": rec[18:20].decode("ascii").strip(),
        "start": start, "nsamp": nsamp, "rate": rate, "encoding": enc, "reclen": reclen,
        "data_at": data_at, "time_correction": tcorr, "flags": tuple(rec[36:39]),
    }


def read(path):
    """A list of records, each a dict with its header fields, "samples" and "widths"."""
    raw = open(path, "rb").read()
    out, at = [], 0
    while at < len(raw):
        head = parse_record(raw[at:at + 64])
        reclen = head["reclen"]
        rec = raw[at:at + reclen]
        if len(rec) != reclen:
            raise Refusal("FILE-ENDS-MID-RECORD at byte %d" % at)
        head["samples"], head["widths"] = decode_steim(rec[head["data_at"]:], head["nsamp"],
                                                       head["encoding"])
        out.append(head)
        at += reclen
    if not out:
        raise Refusal("NO-RECORDS")
    return out


def describe(path):
    """A dict of the facts the study's table gives for one file."""
    recs = read(path)
    rate = recs[0]["rate"]
    ids = set((r["network"], r["station"], r["location"], r["channel"]) for r in recs)
    if len(ids) != 1 or any(r["rate"] != rate for r in recs):
        raise Refusal("MORE-THAN-ONE-CHANNEL-OR-RATE")
    gaps = []
    for a, b in zip(recs, recs[1:]):
        want = a["start"] + timedelta(seconds=a["nsamp"] / rate)
        off = (b["start"] - want).total_seconds()
        if abs(off) > 0.5 / rate:
            gaps.append((want, off))
    allx = [x for r in recs for x in r["samples"]]
    lo, hi = min(allx), max(allx)
    widths = {}
    for r in recs:
        for k, v in r["widths"].items():
            widths[k] = widths.get(k, 0) + v
    return {
        "id": ".".join(sorted(ids)[0]), "records": len(recs),
        "reclen": sorted(set(r["reclen"] for r in recs)),
        "encoding": sorted(set(ENCODINGS[r["encoding"]] for r in recs)),
        "rate": rate, "samples": len(allx), "first": recs[0]["start"],
        "last": recs[-1]["start"] + timedelta(seconds=(recs[-1]["nsamp"] - 1) / rate),
        "gaps": gaps, "min": lo, "max": hi,
        "bits": max(lo.bit_length() if lo >= 0 else (-lo - 1).bit_length(),
                    hi.bit_length() if hi >= 0 else (-hi - 1).bit_length()) + 1,
        "widths": widths, "quality": sorted(set(r["quality"] for r in recs)),
        "time_corrections": sorted(set(r["time_correction"] for r in recs)),
    }


def frame_of(diffs, x0, encoding=10):
    """Test helper: one 64-byte Steim-1 first frame holding up to 13 32-bit differences."""
    assert encoding == 10 and len(diffs) <= 13
    xs = [x0]
    for d in diffs[1:]:
        xs.append(xs[-1] + d)
    words = [0, x0 & 0xFFFFFFFF, xs[-1] & 0xFFFFFFFF]
    ctrl = 0
    for i, d in enumerate(diffs):
        words.append(d & 0xFFFFFFFF)
        ctrl |= 3 << (30 - 2 * (3 + i))
    words += [0] * (16 - len(words))
    words[0] = ctrl
    return struct.pack(">16I", *words), xs


def self_test():
    cases = 0
    assert signed(0xFF, 8) == -1 and signed(0x7F, 8) == 127 and signed(0x8000, 16) == -32768
    cases += 3
    # A frame worked by hand: first sample 10, then +5, -7, +100000.
    data, want = frame_of([0, 5, -7, 100000], 10)
    got, widths = decode_steim(data, 4, 10)
    assert got == want == [10, 15, 8, 100008], got
    assert widths == {32: 4}
    cases += 1
    # Four 8-bit differences in one word: control nibble 01 for word 3.
    words = [1 << (30 - 2 * 3), 3, 3 + 1 - 2 + 3, (0 << 24) | (1 << 16) | (0xFE << 8) | 3]
    words += [0] * 12
    got, widths = decode_steim(struct.pack(">16I", *words), 4, 10)
    assert got == [3, 4, 2, 5] and widths == {8: 4}, (got, widths)
    cases += 1
    # Two 16-bit differences: control nibble 10 for word 3.
    words = [2 << (30 - 2 * 3), -5 & 0xFFFFFFFF, (-5 - 300) & 0xFFFFFFFF,
             (0 << 16) | (-300 & 0xFFFF)] + [0] * 12
    got, widths = decode_steim(struct.pack(">16I", *words), 2, 10)
    assert got == [-5, -305] and widths == {16: 2}, (got, widths)
    cases += 1
    # The control: a record whose stated last sample is wrong must be refused.
    data, _want = frame_of([0, 5, -7, 100000], 10)
    bad = data[:8] + struct.pack(">I", 999) + data[12:]
    try:
        decode_steim(bad, 4, 10)
    except Refusal as e:
        assert "LAST-SAMPLE-MISMATCH" in str(e)
    else:
        raise AssertionError("a wrong last sample was not refused")
    cases += 1
    # The control: one flipped bit in a difference must be refused.
    flipped = bytearray(data)
    flipped[4 * 4 + 3] ^= 1
    try:
        decode_steim(bytes(flipped), 4, 10)
    except Refusal:
        pass
    else:
        raise AssertionError("a flipped difference bit was not refused")
    cases += 1
    print("OK self-test: %d cases" % cases)


def main():
    args = sys.argv[1:]
    if args == ["--self-test"]:
        self_test()
        return 0
    if not args:
        raise SystemExit(__doc__)
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    print("| file | channel | records | record bytes | encoding | samples/s | samples | "
          "first sample, UTC | last sample, UTC | gaps | smallest | largest | "
          "bits a sample needs | differences stored in 8, 16, 32 bits |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for path in args:
        d = describe(path)
        name = path.replace("\\", "/").split("/")[-1]
        w = d["widths"]
        print("| %s | %s | %d | %s | %s | %g | %d | %s | %s | %d | %d | %d | %d | %d, %d, %d |" % (
            name, d["id"], d["records"], ", ".join(str(x) for x in d["reclen"]),
            ", ".join(d["encoding"]), d["rate"], d["samples"],
            d["first"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-2],
            d["last"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-2], len(d["gaps"]), d["min"], d["max"],
            d["bits"], w.get(8, 0), w.get(16, 0), w.get(32, 0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

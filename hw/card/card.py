"""The card day's cases, its raw shapes and its comparisons: the lead's, round 3. Run from the repository's root.

    python card.py cases   <folder> [--frames N]           the five cases beside the model (the desktop)
    python card.py compare <case folder> <run out folder>  IDENTICAL or DIFFERENT, the run's report, a swap's timing
    python card.py shapes  --xclbin X --shim S [--device N] [--cu NAME]   raw shapes at and past each capability

THE CASES (s16x1, the build's one profile; stage E0's stream: noise sigma 1477/1, seed 2026112302, the seed of E0's
full run for amplitude 1, the e0 pulse at amplitude 1/1 every 128 frames from frame 64, one fewer injection than
the stream has spans of 128, all written before the start; 2^17 frames unless --frames):
  e0           E0's matched filter, gain 1
  hidden       a seeded shape with the hidden layer at the build's maxima: 4 filters of 128 taps, 12 units, pool 3,
               abs after the filters and after the layer; its two shifts the smallest that keep a probe of the
               first 2,048 frames free of the overflow flag (chosen on the model's run: a DECISION, not a result)
  e0_swap      e0, then a swap to the matched filter written backwards, at index 65,536, after 8,192 frames
  hidden_swap  hidden, then a swap to other weights of that shape, at index 98,304, after 8,192 frames
  e0_flip      the control: e0's blob with one coefficient bit flipped. Its card run must DIFFER from e0's expected
               records and EQUAL the flipped blob's own model run (expected_flip.bin)

Every expectation is the model's: `model.detector.Core` on `model.inject.inject`'s stream, a swap being a shadow
write and a commit made before the first frame (the account `rtl/tb/seam_host.py`'s model_records gives). The
records are compared as bytes, each the definition's little-endian fields in order: `model.records.pack`, and
the library's `SLOT_FORMAT` cut to the record, which are the same layout.

`shapes` writes, for each capability the build advertises, a shape exactly at it and one just past it, raw to
the core's registers after a reset, then `configure`; the first must leave the core's refusal register 0 and the
second hold that bound's name. The pairs are `rtl/tb/bench_core_control.py`'s at_and_past, copied (cocotb is
not on the box). The core's refusal latch is read and cleared after each.
"""
import argparse
import hashlib
import json
import os
import random
import sys

sys.path.insert(0, os.getcwd())
from model import inject, records, source, weights  # noqa: E402
from model.detector import Core  # noqa: E402
from spec import constants as C  # noqa: E402

PROFILE = "s16x1"
SIGMA = (1477, 1)
SEED = 2026112302
SPACING, FIRST = 128, 64
E0 = tuple(C.PULSES["e0"])
OVERFLOW = 1 << C.FLAGS["overflow"]
SETTLING = 1 << C.FLAGS["settling"]
ABS = C.RECTIFIERS["abs"]
SHAPE_SEED, SWAP_SEED = 20261124, 20261125
FLIP_BIT = 12              # flipped in e0's largest coefficient by magnitude (the first such tap), filter 0, channel 0


def schedule(frames):
    n = frames // SPACING - 1
    return [{"index": FIRST + SPACING * i, "pulse_id": C.PULSE_IDS["e0"], "amplitude_num": 1, "amplitude_den": 1}
            for i in range(n)]


def noise(frames):
    return source.Noise(PROFILE, SEED, SIGMA[0], SIGMA[1], frames)


def model_records(blob, frames, sched, before=()):
    core = Core(blob, 0)
    injected, _truth = inject.inject(PROFILE, noise(frames), sched, frames)
    for method, argument in before:
        getattr(core, method)(argument)
    return [core.step(frame) for frame in injected]


def packed(recs):
    return b"".join(records.pack("score", r) for r in recs)


def hidden_parts(rng):
    filters = [{0: [rng.randint(C.COEFF_MIN, C.COEFF_MAX) for _ in range(128)]} for _ in range(4)]
    units = [[rng.randint(C.COEFF_MIN, C.COEFF_MAX) for _ in range(4)] for _ in range(12)]
    head = [rng.randint(C.COEFF_MIN, C.COEFF_MAX) for _ in range(12)]
    return filters, units, head


def hidden_blob(parts, hidden_shift, score_shift):
    filters, units, head = parts
    return weights.pack(PROFILE, filters, head, ABS, 3, score_shift, units, hidden_shift, ABS)


def overflowed(blob, probe, sched):
    return sum(1 for r in model_records(blob, probe, sched) if r["flags"] & OVERFLOW)


def choose_shifts(parts, probe=2048):
    sched = schedule(probe)
    hidden_shift = next(h for h in range(C.MAX_HIDDEN_SHIFT + 1)
                        if overflowed(hidden_blob(parts, h, C.MAX_SCORE_SHIFT), probe, sched) == 0)
    score_shift = next(s for s in range(C.MAX_SCORE_SHIFT + 1)
                       if overflowed(hidden_blob(parts, hidden_shift, s), probe, sched) == 0)
    return hidden_shift, score_shift


def flipped(blob):
    config = weights.unpack(blob)
    rows = [dict((c, list(row)) for c, row in f.items()) for f in config["filters"]]
    k, ch, bit = 0, 0, FLIP_BIT
    tap = max(range(len(rows[k][ch])), key=lambda m: (abs(rows[k][ch][m]), -m))
    v = rows[k][ch][tap]
    w = v ^ (1 << bit)
    if w > C.COEFF_MAX:
        w -= 1 << C.COEFF_BITS
    rows[k][ch][tap] = w
    return weights.pack(PROFILE, rows, list(config["head"]), config["rectifier"], config["pool"],
                        config["score_shift"]), (k, ch, tap, bit, v, w)


def write_case(folder, name, blob, frames, sched, expected, extra):
    d = os.path.join(folder, name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "case.blob"), "wb") as f:
        f.write(blob)
    with open(os.path.join(d, "table.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(list(noise(0).table), f)
    with open(os.path.join(d, "schedule.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(sched, f)
    data = packed(expected)
    with open(os.path.join(d, "expected.bin"), "wb") as f:
        f.write(data)
    flags = [r["flags"] for r in expected]
    info = dict({"case": name, "profile": PROFILE, "frames": frames, "seed": SEED, "sigma": list(SIGMA),
                 "truth_records": len(sched), "records": len(expected),
                 "expected_sha256": hashlib.sha256(data).hexdigest(),
                 "blob_sha256": hashlib.sha256(blob).hexdigest(),
                 "overflow_records": sum(1 for x in flags if x & OVERFLOW),
                 "settling_records": sum(1 for x in flags if x & SETTLING),
                 "distinct_scores": len(set(r["score"] for r in expected)),
                 "spec_sha256": C.SPEC_SHA256}, **extra)
    with open(os.path.join(d, "case.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(info, f, indent=1)
    print("%-12s %d records, %d truth, %d overflow, %d settling, %d distinct scores, expected %s"
          % (name, len(expected), len(sched), info["overflow_records"], info["settling_records"],
             info["distinct_scores"], info["expected_sha256"][:16]), flush=True)
    return d


def cases(folder, frames):
    sched = schedule(frames)
    e0 = weights.matched_filter(PROFILE, E0, (1,))
    base = model_records(e0, frames, sched)
    write_case(folder, "e0", e0, frames, sched, base, {"blob": "matched filter of e0, gain 1"})

    back = weights.matched_filter(PROFILE, tuple(reversed(E0)), (1,))
    at, after = 65536 * frames // (1 << 17), 8192 * frames // (1 << 17)
    swapped = model_records(e0, frames, sched, before=[("write_shadow", back), ("commit", at)])
    d = write_case(folder, "e0_swap", e0, frames, sched, swapped,
                   {"blob": "matched filter of e0, gain 1", "swap_to": "matched filter of e0 written backwards",
                    "swap_at": at, "swap_after": after,
                    "first_difference_from_e0": next((i for i, (x, y) in enumerate(zip(base, swapped)) if x != y), None)})
    with open(os.path.join(d, "swap.blob"), "wb") as f:
        f.write(back)

    flip, where = flipped(e0)
    flip_recs = model_records(flip, frames, sched)
    differ = sum(1 for x, y in zip(base, flip_recs) if x != y)
    assert differ > 0, "the flipped bit reaches no score: choose another"
    d = write_case(folder, "e0_flip", flip, frames, sched, base,
                   {"blob": "e0's matched filter with filter %d channel %d tap %d bit %d flipped: %d -> %d" % where,
                    "expected_is": "e0's records, from the unflipped blob: the card's run must DIFFER",
                    "records_the_flip_changes": differ})
    with open(os.path.join(d, "expected_flip.bin"), "wb") as f:
        f.write(packed(flip_recs))

    rng = random.Random(SHAPE_SEED)
    parts = hidden_parts(rng)
    hidden_shift, score_shift = choose_shifts(parts)
    hid = hidden_blob(parts, hidden_shift, score_shift)
    hid_recs = model_records(hid, frames, sched)
    write_case(folder, "hidden", hid, frames, sched, hid_recs,
               {"blob": "seeded %d: 4 filters x 128 taps, 12 units, pool 3, abs and abs" % SHAPE_SEED,
                "hidden_shift": hidden_shift, "score_shift": score_shift})

    other = hidden_blob(hidden_parts(random.Random(SWAP_SEED)), hidden_shift, score_shift)
    at, after = 98304 * frames // (1 << 17), 8192 * frames // (1 << 17)
    hs = model_records(hid, frames, sched, before=[("write_shadow", other), ("commit", at)])
    d = write_case(folder, "hidden_swap", hid, frames, sched, hs,
                   {"blob": "the hidden case's", "swap_to": "seeded %d, the same shape and shifts" % SWAP_SEED,
                    "swap_at": at, "swap_after": after, "hidden_shift": hidden_shift, "score_shift": score_shift,
                    "first_difference_from_hidden": next((i for i, (x, y) in enumerate(zip(hid_recs, hs)) if x != y), None)})
    with open(os.path.join(d, "swap.blob"), "wb") as f:
        f.write(other)


def compare(folder, out):
    info = json.load(open(os.path.join(folder, "case.json"), encoding="utf-8"))
    report = json.load(open(os.path.join(out, "report.json"), encoding="utf-8"))
    n = len(records.pack("score", {"index": 0, "score": 0, "flags": 0, "epoch": 0}))
    got = open(os.path.join(out, "records.bin"), "rb").read()
    want = open(os.path.join(folder, "expected.bin"), "rb").read()
    info.setdefault("case", os.path.basename(os.path.normpath(folder)))
    info.setdefault("expected_sha256", "(not recorded)")
    print("case %s: report %s" % (info["case"], json.dumps({k: report[k] for k in report if k not in ("identity",)})))
    first = next((i for i in range(0, min(len(got), len(want)), n) if got[i:i + n] != want[i:i + n]), None)
    differing = sum(1 for i in range(0, min(len(got), len(want)), n) if got[i:i + n] != want[i:i + n])
    same = got == want
    if same:
        print("IDENTICAL: %d records, every byte the model's (expected %s)" % (len(want) // n, info["expected_sha256"][:16]))
    else:
        print("DIFFERENT: %d bytes against the model's %d; %d records differ; first at record %s"
              % (len(got), len(want), differing, None if first is None and len(got) == len(want) else
                 (first // n if first is not None else min(len(got), len(want)) // n)))
    flip = os.path.join(folder, "expected_flip.bin")
    if os.path.exists(flip):
        fl = open(flip, "rb").read()
        print("against the flipped blob's own model run: %s" % ("IDENTICAL" if got == fl else "DIFFERENT"))
    if "swap" in report:
        s = report["swap"]
        print("swap: %s" % json.dumps(s))
    return 0 if same else 1


# ------------------------------------------------------------------ raw shapes, on the card or in emulation

SHAPE_SCALARS = ("shape_sample_bits", "shape_channels", "shape_filters", "shape_taps", "shape_rectifier",
                 "shape_score_shift", "shape_pool", "shape_hidden", "shape_hidden_shift", "shape_between")


def plain_shape(**over):
    prof = C.PROFILES[PROFILE]
    shape = {"shape_sample_bits": prof["sample_bits"], "shape_channels": prof["channels"], "shape_filters": 1,
             "shape_taps": 1, "shape_rectifier": C.RECTIFIERS["pass"], "shape_score_shift": 0, "shape_pool": 1,
             "shape_hidden": 0, "shape_hidden_shift": 0, "shape_between": 0, "masks": None}
    shape.update(over)
    if shape["masks"] is None:
        shape["masks"] = [1] * min(shape["shape_filters"], C.REGISTERS["shape_masks"][2])
    return shape


def words_in(shape):
    rows = sum(bin(m).count("1") for m in shape["masks"][:shape["shape_filters"]])
    k, h = shape["shape_filters"], shape["shape_hidden"]
    return rows * shape["shape_taps"] + (h * k + h if h else k)


def masks_for_rows(channels, rows):
    masks, left = [], rows
    while left > 0:
        n = min(channels, left)
        masks.append((1 << n) - 1)
        left -= n
    return masks


def at_and_past(caps):
    out = [
        ("cap_filters", plain_shape(shape_filters=caps["cap_filters"]), plain_shape(shape_filters=caps["cap_filters"] + 1), "SHAPE_FILTERS"),
        ("cap_taps", plain_shape(shape_taps=caps["cap_taps"]), plain_shape(shape_taps=caps["cap_taps"] + 1), "SHAPE_TAPS"),
        ("cap_pool", plain_shape(shape_pool=caps["cap_pool"]), plain_shape(shape_pool=caps["cap_pool"] + 1), "SHAPE_POOL"),
        ("cap_score_shift", plain_shape(shape_score_shift=caps["cap_score_shift"]),
         plain_shape(shape_score_shift=caps["cap_score_shift"] + 1), "SHAPE_SHIFT"),
        ("cap_hidden", plain_shape(shape_hidden=caps["cap_hidden"]), plain_shape(shape_hidden=caps["cap_hidden"] + 1), "SHAPE_HIDDEN"),
        ("cap_hidden_shift", plain_shape(shape_hidden=1, shape_hidden_shift=caps["cap_hidden_shift"]),
         plain_shape(shape_hidden=1, shape_hidden_shift=caps["cap_hidden_shift"] + 1), "SHAPE_HIDDEN_SHIFT"),
        ("cap_sample_bits", plain_shape(shape_sample_bits=caps["cap_sample_bits"]),
         plain_shape(shape_sample_bits=caps["cap_sample_bits"] + 1), "PROFILE_UNKNOWN"),
        ("cap_channels", plain_shape(shape_channels=caps["cap_channels"]),
         plain_shape(shape_channels=caps["cap_channels"] + 1), "PROFILE_UNKNOWN"),
    ]
    channels = C.PROFILES[PROFILE]["channels"]
    at, past = masks_for_rows(channels, caps["cap_rows"]), masks_for_rows(channels, caps["cap_rows"] + 1)
    if len(past) <= caps["cap_filters"]:
        out.append(("cap_rows", plain_shape(shape_filters=len(at), masks=at),
                    plain_shape(shape_filters=len(past), masks=past), "SHAPE_ROWS"))
    return out


def shapes(a):
    from host import library as L
    from host.backend_xrt import Backend
    from host.drive import Host
    bad = 0
    with Backend(a.xclbin, device=a.device, cu_name=a.cu, shim_path=a.shim) as backend:
        lib = Host(backend, trace=[])
        ident = lib.open()
        caps = ident["caps"]
        print("identity: id 0x%08X, spec_version %d, spec_hash %064x" % (ident["id"], ident["spec_version"], ident["spec_hash"]))
        print("caps: %s" % json.dumps(caps, sort_keys=True), flush=True)
        for pair in (a.maxima.split(",") if a.maxima else []):
            name, want = pair.split("=")
            ok = caps.get(name) == int(want)
            bad += not ok
            print("%-4s %-20s the image says %s, the build asked %s" % ("ok" if ok else "BAD", name, caps.get(name), want))
        for cap, at, past, name in at_and_past(caps):
            for which, shape, want in (("at", at, 0), ("past", past, C.REFUSAL_CODES[name])):
                lib.reset()
                for reg in SHAPE_SCALARS:
                    lib.raw_write(L.offset(reg), shape[reg])
                for k, mask in enumerate(shape["masks"]):
                    lib.raw_write(L.offset("shape_masks", k), mask)
                lib.raw_write(L.offset("configure"), words_in(shape))
                got = lib.raw_read(L.offset("refusal"))
                lib.raw_write(L.offset("refusal"), 0)
                ok = got == want
                bad += not ok
                print("%-4s %-16s %-6s refusal %2d %-20s %s" % ("ok" if ok else "BAD", cap, which, got,
                      L.NAME_OF.get(got, "none" if got == 0 else "?"), "" if ok else "wanted %d" % want), flush=True)
        lib.reset()
    print(("PASS card.shapes: the maxima asked are the image's; every shape at a capability taken, every one past it refused by its name" if bad == 0
           else "FAIL card.shapes: %d wrong" % bad), flush=True)
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    what = sys.argv[1]
    if what == "cases":
        ap = argparse.ArgumentParser()
        ap.add_argument("folder")
        ap.add_argument("--frames", type=int, default=1 << 17)
        a = ap.parse_args(sys.argv[2:])
        cases(a.folder, a.frames)
    elif what == "compare":
        sys.exit(compare(sys.argv[2], sys.argv[3]))
    elif what == "shapes":
        ap = argparse.ArgumentParser()
        ap.add_argument("--xclbin", required=True)
        ap.add_argument("--shim", required=True)
        ap.add_argument("--device", type=int, default=0)
        ap.add_argument("--cu", default="undertone_krnl")
        ap.add_argument("--maxima", default="", help="cap=value,... : the build's maxima, each held to the image's register")
        sys.exit(shapes(ap.parse_args(sys.argv[2:])))
    else:
        sys.exit("cases, compare or shapes")

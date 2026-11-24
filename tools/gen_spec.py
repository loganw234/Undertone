#!/usr/bin/env python3
"""Generate the copies of spec/undertone.toml, or check that each is current.

    python tools/gen_spec.py            write the three copies
    python tools/gen_spec.py --check    exit 1, naming each stale copy's first difference
    --root DIR                          work on another copy of the tree

One definition, generated copies. There are three:

    spec/constants.py        the Python constants model/ and stats/ import
    spec/undertone_pkg.sv    a SystemVerilog package, for the RTL
    spec/undertone.h         a C header, for the host library

The second and third carry the same names with the same values, from one list
(`numbers` below): the header's names have the prefix UNDERTONE_. They hold
the integers only. What the Python copy has and they do not: the profiles as
a table (they carry each profile's two numbers), the pulses as lists (they
carry each sample as an integer of its own), and the names of the quantising
and injection rules. A name that two entries of the list would share is
REFUSED.

`--check` compares text: each copy must equal what this generator renders
today. It does not show that a simulator or a compiler reads those lines as
the same numbers; the `rtl-spec` stage of `verify/run.sh --with rtl` does.

The definition is checked before anything is written, and one that does not
make sense is REFUSED by name. What is checked, exactly:

  - the top-level sections are the ones this generator knows (TOP below), no
    more, no fewer;
  - every section's keys are the ones listed in KEYS below, no more, no fewer;
  - a number is an int (never a bool, a float or a string) inside its range;
  - a profile, field, flag, rectifier or pulse name is lower case letters,
    digits and underscores; a refusal name is upper case letters, digits and
    underscores;
  - the records are exactly score, truth and event, each field [name, bits,
    "signed" | "unsigned"] with bits a whole number of bytes from 8 to 64, no
    field named twice, the score record has an unsigned flags field and the
    truth record an unsigned pulse_id field;
  - no flag bit is used twice or lies outside the flags field;
  - a rectifier code is an int from 0 to 255, and no code is used twice;
  - the quantising rule and the injection's rounding are the one rule each
    that this generator knows;
  - no refusal name is listed twice; the refusal codes name exactly the
    refusals, each code is an int from 1 to 255, and no code is used twice;
  - the bus is 32-bit words, the one word this generator knows; a register is
    [offset, "ro" | "rw" | "wo", words] with 1 to 64 words, at a multiple of the
    word's bytes, not below the frame's first offset and not past its address
    bits, and no two registers overlap;
  - a block is [first offset, end], whole words inside the frame with its
    first before its end; no two blocks overlap; and every register lies
    wholly inside one block;
  - a register that has named bits is declared, is one word and can be read;
    a bit is inside the word, and no bit of a register is used twice;
  - a pulse's file is under spec/pulses/, names itself as the definition names
    it, and holds ints that fit the NARROWEST profile;
  - the pulse ids name exactly the pulses, each id fits the truth record's
    pulse_id field, and no id is used twice.

Anything else that goes wrong while reading the definition is refused as
DEFINITION-MALFORMED, with what went wrong: never a traceback.

What is NOT checked: whether a value is the one the design means, whether a
record has the fields the code reads (beyond the two named above), or whether
the bounds make sense together. A definition that says 64 taps where the
design says 128, a truth record with no index, or fewer rows allowed than
filters, is accepted here. The tests hold the first for the figures they pin,
and code that reads a missing field fails its own tests.
"""
import hashlib
import os
import re
import sys
import tomllib

OUT = "spec/constants.py"
OUT_SV = "spec/undertone_pkg.sv"
OUT_C = "spec/undertone.h"
SRC = "spec/undertone.toml"
C_PREFIX = "UNDERTONE_"
KEYS = {
    "meta": {"spec_version"},
    "core": {"coeff_bits", "max_filters", "max_taps", "max_rows", "max_pool", "max_score_shift",
             "max_hidden", "max_hidden_shift"},
    "quantise": {"scale", "rounding"},
    "inject": {"rounding"},
    "scorer": {"max_hist_bins"},
    "records": {"score", "truth", "event"},
    "refusals": {"names"},
    "bus": {"word_bits", "address_bits", "first_offset", "magic"},
    "fabric": {"max_noise_table", "max_inject_pending"},
}
TOP = set(KEYS) | {"profile", "flags", "rectifier", "pulses", "pulse_ids", "refusal_codes", "registers",
                   "blocks", "register_bits"}
ACCESS = ("ro", "rw", "wo")
RANGE = {"spec_version": (1, 10 ** 6), "sample_bits": (2, 32), "channels": (1, 16),
         "coeff_bits": (2, 32), "max_filters": (1, 1024), "max_taps": (1, 65536),
         "max_rows": (1, 1024), "max_pool": (1, 2 ** 24), "max_score_shift": (0, 63),
         "max_hist_bins": (1, 65536), "max_hidden": (1, 1024), "max_hidden_shift": (0, 63),
         "word_bits": (32, 32), "address_bits": (4, 16), "first_offset": (0, 65532), "magic": (1, 2 ** 31 - 1),
         "max_noise_table": (1, 2 ** 20), "max_inject_pending": (1, 65536)}
LOWER = re.compile(r"[a-z][a-z0-9_]*\Z")
UPPER = re.compile(r"[A-Z][A-Z0-9_]*\Z")


class Refused(Exception):
    pass


def number(section, key, value):
    lo, hi = RANGE[key]
    if type(value) is not int or not lo <= value <= hi:
        raise Refused("NUMBER: %s.%s = %r is not an int from %d to %d" % (section, key, value, lo, hi))
    return value


def lower(what, name):
    if type(name) is not str or not LOWER.match(name):
        raise Refused("NAME: %s %r is not lower case letters, digits and underscores" % (what, name))
    return name


def keys(section, have, want):
    if set(have) != set(want):
        raise Refused("KEYS: [%s] has %s, expected %s" % (section, sorted(have), sorted(want)))


def validate(d, root):
    if not isinstance(d, dict) or set(d) != TOP:
        raise Refused("SECTIONS: has %s, expected %s" % (sorted(d), sorted(TOP)))
    for section, want in KEYS.items():
        if not isinstance(d[section], dict):
            raise Refused("SECTIONS: [%s] is not a table" % section)
        keys(section, d[section], want)
    number("meta", "spec_version", d["meta"]["spec_version"])
    if not isinstance(d["profile"], dict) or not d["profile"]:
        raise Refused("PROFILE: there is no profile")
    for name, p in d["profile"].items():
        lower("profile", name)
        if not isinstance(p, dict):
            raise Refused("PROFILE: %s is not a table" % name)
        keys("profile.%s" % name, p, {"sample_bits", "channels"})
        number("profile.%s" % name, "sample_bits", p["sample_bits"])
        number("profile.%s" % name, "channels", p["channels"])
    for key in sorted(KEYS["core"]):
        number("core", key, d["core"][key])
    number("scorer", "max_hist_bins", d["scorer"]["max_hist_bins"])
    if d["quantise"] != {"scale": "peak_to_max", "rounding": "half_to_even"}:
        raise Refused("QUANTISE: this generator knows one rule, peak_to_max with half_to_even")
    if d["inject"] != {"rounding": "half_to_even"}:
        raise Refused("INJECT: this generator knows one rounding for an injected sample, half_to_even")
    if not isinstance(d["rectifier"], dict) or not d["rectifier"]:
        raise Refused("RECTIFIER: there is no mode")
    codes = set()
    for name, code in d["rectifier"].items():
        lower("rectifier", name)
        if type(code) is not int or not 0 <= code <= 255 or code in codes:
            raise Refused("RECTIFIER: %s = %r is used twice or is not an int from 0 to 255" % (name, code))
        codes.add(code)
    for rec, fields in d["records"].items():
        if not isinstance(fields, list) or not fields:
            raise Refused("RECORD: %s has no fields" % rec)
        seen = set()
        for f in fields:
            if not isinstance(f, list) or len(f) != 3:
                raise Refused("RECORD: a field of %s is not [name, bits, sign]" % rec)
            lower("field of %s" % rec, f[0])
            if f[0] in seen:
                raise Refused("RECORD: %s names the field %s twice" % (rec, f[0]))
            seen.add(f[0])
            if type(f[1]) is not int or f[1] not in (8, 16, 24, 32, 40, 48, 56, 64):
                raise Refused("RECORD: %s.%s is %r bits, not a whole number of bytes from 8 to 64" % (rec, f[0], f[1]))
            if f[2] not in ("signed", "unsigned"):
                raise Refused("RECORD: %s.%s is %r, not signed or unsigned" % (rec, f[0], f[2]))
    flag_field = [f for f in d["records"]["score"] if f[0] == "flags"]
    if not flag_field or flag_field[0][2] != "unsigned":
        raise Refused("RECORD: score has no unsigned flags field")
    id_field = [f for f in d["records"]["truth"] if f[0] == "pulse_id"]
    if not id_field or id_field[0][2] != "unsigned":
        raise Refused("RECORD: truth has no unsigned pulse_id field")
    if not isinstance(d["flags"], dict) or not d["flags"]:
        raise Refused("FLAGS: there is no flag")
    used = set()
    for name, bit in d["flags"].items():
        lower("flag", name)
        if type(bit) is not int or not 0 <= bit < flag_field[0][1] or bit in used:
            raise Refused("FLAGS: %s = %r is used twice or lies outside the %d-bit flags field"
                          % (name, bit, flag_field[0][1]))
        used.add(bit)
    names = d["refusals"]["names"]
    if not isinstance(names, list) or not names:
        raise Refused("REFUSALS: there is no name")
    for n in names:
        if type(n) is not str or not UPPER.match(n):
            raise Refused("NAME: refusal %r is not upper case letters, digits and underscores" % (n,))
    if len(set(names)) != len(names):
        raise Refused("REFUSALS: a name is listed twice")
    codes = d["refusal_codes"]
    if not isinstance(codes, dict) or set(codes) != set(names):
        raise Refused("REFUSAL_CODES: the codes do not name exactly the refusals: without a code %s, without a name %s"
                      % (sorted(set(names) - set(codes)) if isinstance(codes, dict) else names,
                         sorted(set(codes) - set(names)) if isinstance(codes, dict) else codes))
    taken = set()
    for n in names:
        if type(codes[n]) is not int or not 1 <= codes[n] <= 255 or codes[n] in taken:
            raise Refused("REFUSAL_CODES: %s = %r is used twice or is not an int from 1 to 255" % (n, codes[n]))
        taken.add(codes[n])
    for key in sorted(KEYS["bus"]):
        number("bus", key, d["bus"][key])
    step, limit = d["bus"]["word_bits"] // 8, 2 ** d["bus"]["address_bits"]
    if d["bus"]["first_offset"] % step or d["bus"]["first_offset"] >= limit:
        raise Refused("BUS: first_offset = %d is not a multiple of %d below %d" % (d["bus"]["first_offset"], step, limit))
    if not isinstance(d["registers"], dict) or not d["registers"]:
        raise Refused("REGISTERS: there is no register")
    spans = []
    for name, r in d["registers"].items():
        lower("register", name)
        if not isinstance(r, list) or len(r) != 3:
            raise Refused("REGISTERS: %s is not [offset, access, words]" % name)
        offset, access, words = r
        if type(offset) is not int or type(words) is not int or not 1 <= words <= 64 or access not in ACCESS:
            raise Refused("REGISTERS: %s = %r is not [an int, one of %s, 1 to 64]" % (name, r, ", ".join(ACCESS)))
        if offset % step or offset < d["bus"]["first_offset"] or offset + step * words > limit:
            raise Refused("REGISTERS: %s at %d for %d word(s) is not at a multiple of %d from %d to below %d"
                          % (name, offset, words, step, d["bus"]["first_offset"], limit))
        spans.append((offset, offset + step * words, name))
    spans.sort()
    for (_a0, a1, an), (b0, _b1, bn) in zip(spans, spans[1:]):
        if b0 < a1:
            raise Refused("REGISTERS: %s and %s overlap" % (an, bn))
    for key in sorted(KEYS["fabric"]):
        number("fabric", key, d["fabric"][key])
    if not isinstance(d["blocks"], dict) or not d["blocks"]:
        raise Refused("BLOCKS: there is no block")
    ranges = []
    for name, r in d["blocks"].items():
        lower("block", name)
        if not isinstance(r, list) or len(r) != 2 or type(r[0]) is not int or type(r[1]) is not int:
            raise Refused("BLOCKS: %s = %r is not [first offset, end], two ints" % (name, r))
        first, end = r
        if first % step or end % step or not d["bus"]["first_offset"] <= first < end <= limit:
            raise Refused("BLOCKS: %s from %d to %d is not whole words from %d to %d with its first before its end"
                          % (name, first, end, d["bus"]["first_offset"], limit))
        ranges.append((first, end, name))
    ranges.sort()
    for (_a0, a1, an), (b0, _b1, bn) in zip(ranges, ranges[1:]):
        if b0 < a1:
            raise Refused("BLOCKS: %s and %s overlap" % (an, bn))
    for r0, r1, rn in spans:
        if not any(first <= r0 and r1 <= end for first, end, _name in ranges):
            raise Refused("BLOCKS: the register %s lies in no block, or across two" % rn)
    if not isinstance(d["register_bits"], dict):
        raise Refused("REGISTER_BITS: is not a table")
    for reg, bits in d["register_bits"].items():
        if reg not in d["registers"] or d["registers"][reg][1] == "wo" or d["registers"][reg][2] != 1:
            raise Refused("REGISTER_BITS: %s is not a register of one word that can be read" % reg)
        if not isinstance(bits, dict) or not bits:
            raise Refused("REGISTER_BITS: %s has no bit" % reg)
        used = set()
        for name, bit in bits.items():
            lower("bit of the register %s" % reg, name)
            if type(bit) is not int or not 0 <= bit < d["bus"]["word_bits"] or bit in used:
                raise Refused("REGISTER_BITS: %s.%s = %r is used twice or lies outside the %d-bit word"
                              % (reg, name, bit, d["bus"]["word_bits"]))
            used.add(bit)
    if not isinstance(d["pulses"], dict) or not d["pulses"]:
        raise Refused("PULSES: there is no pulse")
    narrowest = min(p["sample_bits"] for p in d["profile"].values())
    lo, hi = -2 ** (narrowest - 1), 2 ** (narrowest - 1) - 1
    pulses = {}
    for name, rel in d["pulses"].items():
        lower("pulse", name)
        if type(rel) is not str or not re.match(r"pulses/[a-z0-9_]+\.toml\Z", rel):
            raise Refused("PULSES: %s's path %r is not pulses/<name>.toml" % (name, rel))
        with open(os.path.join(root, "spec", rel), "rb") as f:
            p = tomllib.loads(f.read().decode("utf-8"))
        if set(p) != {"name", "samples"} or p["name"] != name:
            raise Refused("PULSES: %s does not name itself %r, or has other keys" % (rel, name))
        s = p["samples"]
        if not isinstance(s, list) or not s or not all(type(v) is int for v in s):
            raise Refused("PULSES: %s's samples are not a list of ints" % rel)
        if min(s) < lo or max(s) > hi:
            raise Refused("PULSES: %s has a sample outside the narrowest profile, %d bits" % (name, narrowest))
        pulses[name] = list(s)
    ids = d["pulse_ids"]
    if not isinstance(ids, dict) or set(ids) != set(pulses):
        raise Refused("PULSE_IDS: the ids name %s and the pulses are %s"
                      % (sorted(ids) if isinstance(ids, dict) else ids, sorted(pulses)))
    taken = set()
    for name, ident in ids.items():
        if type(ident) is not int or not 0 <= ident < 2 ** id_field[0][1] or ident in taken:
            raise Refused("PULSE_IDS: %s = %r is used twice or does not fit the %d-bit pulse_id field"
                          % (name, ident, id_field[0][1]))
        taken.add(ident)
    return pulses


def load(root):
    try:
        with open(os.path.join(root, SRC), "rb") as f:
            raw = f.read()
        d = tomllib.loads(raw.decode("utf-8"))
        pulses = validate(d, root)
    except Refused:
        raise
    except Exception as e:  # a definition this generator did not foresee is refused, not crashed on
        raise Refused("DEFINITION-MALFORMED: %s: %s" % (type(e).__name__, e))
    return d, pulses, hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def render(d, pulses, digest):
    L = ['"""GENERATED by tools/gen_spec.py from spec/undertone.toml. Do not edit.',
         "",
         "Edit the definition, run the generator, commit both. The `generated` stage",
         'of verify/run.sh fails when this file and the definition disagree.',
         '"""',
         "",
         "SPEC_VERSION = %d" % d["meta"]["spec_version"],
         'SPEC_SHA256 = "%s"' % digest,
         "",
         "PROFILES = {"]
    for name in sorted(d["profile"]):
        p = d["profile"][name]
        b = p["sample_bits"]
        L.append('    "%s": {"sample_bits": %d, "channels": %d, "sample_min": %d, "sample_max": %d},'
                 % (name, b, p["channels"], -2 ** (b - 1), 2 ** (b - 1) - 1))
    c = d["core"]
    L += ["}",
          "",
          "COEFF_BITS = %d" % c["coeff_bits"],
          "COEFF_MIN = %d" % -2 ** (c["coeff_bits"] - 1),
          "COEFF_MAX = %d" % (2 ** (c["coeff_bits"] - 1) - 1),
          "MAX_FILTERS = %d" % c["max_filters"],
          "MAX_TAPS = %d" % c["max_taps"],
          "MAX_ROWS = %d" % c["max_rows"],
          "MAX_POOL = %d" % c["max_pool"],
          "MAX_SCORE_SHIFT = %d" % c["max_score_shift"],
          "MAX_HIDDEN = %d" % c["max_hidden"],
          "MAX_HIDDEN_SHIFT = %d" % c["max_hidden_shift"],
          "MAX_HIST_BINS = %d" % d["scorer"]["max_hist_bins"],
          "MAX_NOISE_TABLE = %d" % d["fabric"]["max_noise_table"],
          "MAX_INJECT_PENDING = %d" % d["fabric"]["max_inject_pending"],
          "",
          "RECTIFIERS = {"]
    for name in sorted(d["rectifier"], key=lambda n: d["rectifier"][n]):
        L.append('    "%s": %d,' % (name, d["rectifier"][name]))
    L += ["}",
          "",
          'QUANTISE_SCALE = "%s"' % d["quantise"]["scale"],
          'QUANTISE_ROUNDING = "%s"' % d["quantise"]["rounding"],
          'INJECT_ROUNDING = "%s"' % d["inject"]["rounding"],
          "",
          "RECORDS = {"]
    for rec in sorted(d["records"]):
        L.append('    "%s": (' % rec)
        for f in d["records"][rec]:
            L.append('        ("%s", %d, "%s"),' % (f[0], f[1], f[2]))
        L.append("    ),")
    L += ["}", "", "FLAGS = {"]
    for name in sorted(d["flags"], key=lambda n: d["flags"][n]):
        L.append('    "%s": %d,' % (name, d["flags"][name]))
    flag_bits = [f[1] for f in d["records"]["score"] if f[0] == "flags"][0]
    used = sum(1 << b for b in d["flags"].values())
    L += ["}",
          "FLAGS_RESERVED_MASK = 0x%02X" % (((1 << flag_bits) - 1) & ~used),
          "",
          "REFUSALS = ("]
    L += ['    "%s",' % n for n in d["refusals"]["names"]]
    L += [")", "", "PULSES = {"]
    for name in sorted(pulses):
        s = pulses[name]
        L.append('    "%s": (' % name)
        for i in range(0, len(s), 8):
            L.append("        " + ", ".join(str(v) for v in s[i:i + 8]) + ",")
        L.append("    ),")
    L += ["}", "PULSE_SAMPLE_BITS = %d" % min(p["sample_bits"] for p in d["profile"].values()), "", "PULSE_IDS = {"]
    for name in sorted(d["pulse_ids"], key=lambda n: d["pulse_ids"][n]):
        L.append('    "%s": %d,' % (name, d["pulse_ids"][name]))
    L += ["}", "", "REFUSAL_CODES = {"]
    L += ['    "%s": %d,' % (n, d["refusal_codes"][n]) for n in d["refusals"]["names"]]
    b = d["bus"]
    L += ["}",
          "",
          'BUS = {"word_bits": %d, "address_bits": %d, "first_offset": %d, "magic": 0x%08X}'
          % (b["word_bits"], b["address_bits"], b["first_offset"], b["magic"]),
          "",
          "BLOCKS = {"]
    for name in sorted(d["blocks"], key=lambda n: d["blocks"][n][0]):
        L.append('    "%s": (0x%03X, 0x%03X),' % (name, d["blocks"][name][0], d["blocks"][name][1]))
    L += ["}", "", "REGISTERS = {"]
    for name in sorted(d["registers"], key=lambda n: d["registers"][n][0]):
        offset, access, words = d["registers"][name]
        L.append('    "%s": (0x%03X, "%s", %d),' % (name, offset, access, words))
    L += ["}", "", "REGISTER_BITS = {"]
    for reg in sorted(d["register_bits"], key=lambda n: d["registers"][n][0]):
        bits = d["register_bits"][reg]
        L.append('    "%s": {%s},' % (reg, ", ".join('"%s": %d' % (n, bits[n]) for n in sorted(bits, key=lambda n: bits[n]))))
    L += ["}", ""]
    return "\n".join(L)


def numbers(d, pulses):
    """The integers the SystemVerilog package and the C header carry: a list of
    (heading, [(NAME, value), ...]). Every value fits 32 signed bits, or the
    definition is refused: both copies declare a plain int.
    """
    c = d["core"]
    groups = [("the definition", [("SPEC_VERSION", d["meta"]["spec_version"])])]
    rows = [("PROFILE_COUNT", len(d["profile"]))]
    for name in sorted(d["profile"]):
        rows += [("PROFILE_%s_SAMPLE_BITS" % name.upper(), d["profile"][name]["sample_bits"]),
                 ("PROFILE_%s_CHANNELS" % name.upper(), d["profile"][name]["channels"])]
    groups.append(("the profiles: a sample format each", rows))
    groups.append(("the core's widths and maxima", [
        ("COEFF_BITS", c["coeff_bits"]),
        ("COEFF_MIN", -2 ** (c["coeff_bits"] - 1)),
        ("COEFF_MAX", 2 ** (c["coeff_bits"] - 1) - 1),
        ("MAX_FILTERS", c["max_filters"]),
        ("MAX_TAPS", c["max_taps"]),
        ("MAX_ROWS", c["max_rows"]),
        ("MAX_POOL", c["max_pool"]),
        ("MAX_SCORE_SHIFT", c["max_score_shift"]),
        ("MAX_HIDDEN", c["max_hidden"]),
        ("MAX_HIDDEN_SHIFT", c["max_hidden_shift"]),
        ("MAX_HIST_BINS", d["scorer"]["max_hist_bins"])]))
    groups.append(("the fabric's own bounds, which the model does not have", [
        ("MAX_NOISE_TABLE", d["fabric"]["max_noise_table"]),
        ("MAX_INJECT_PENDING", d["fabric"]["max_inject_pending"])]))
    groups.append(("the rectifier's codes", [
        ("RECTIFIER_%s" % n.upper(), d["rectifier"][n])
        for n in sorted(d["rectifier"], key=lambda n: d["rectifier"][n])]))
    flag_bits = [f[1] for f in d["records"]["score"] if f[0] == "flags"][0]
    used = sum(1 << b for b in d["flags"].values())
    groups.append(("a score record's flags: the bit each has, and the bits that must be zero",
                   [("FLAG_%s_BIT" % n.upper(), d["flags"][n]) for n in sorted(d["flags"], key=lambda n: d["flags"][n])]
                   + [("FLAGS_RESERVED_MASK", ((1 << flag_bits) - 1) & ~used)]))
    for rec in sorted(d["records"]):
        rows, at = [], 0
        for field, bits, sign in d["records"][rec]:
            stem = "%s_%s" % (rec.upper(), field.upper())
            rows += [(stem + "_LSB", at), (stem + "_BITS", bits), (stem + "_SIGNED", 1 if sign == "signed" else 0)]
            at += bits
        rows.append(("%s_RECORD_BITS" % rec.upper(), at))
        groups.append(("the %s record: each field's lowest bit, its width, and whether it is signed. The canonical "
                       "bytes are little-endian in declared order, so bit 0 is the lowest bit of the first byte" % rec, rows))
    rows = [("PULSE_SAMPLE_BITS", min(p["sample_bits"] for p in d["profile"].values()))]
    for name in sorted(d["pulse_ids"], key=lambda n: d["pulse_ids"][n]):
        rows += [("PULSE_%s_ID" % name.upper(), d["pulse_ids"][name]), ("PULSE_%s_LENGTH" % name.upper(), len(pulses[name]))]
        rows += [("PULSE_%s_SAMPLE_%d" % (name.upper(), j), v) for j, v in enumerate(pulses[name])]
    groups.append(("the reference pulses: the signed bits every sample of a pulse fits (the narrowest profile's), "
                   "and for each pulse the id a truth record carries, its length in samples, and each sample", rows))
    groups.append(("the number the fabric reports for each refusal; 0 is none",
                   [("REFUSAL_NONE", 0)] + [("REFUSAL_%s" % n, d["refusal_codes"][n]) for n in d["refusals"]["names"]]))
    b = d["bus"]
    groups.append(("the register map's frame: one register is one word at a byte offset",
                   [("BUS_WORD_BITS", b["word_bits"]), ("BUS_ADDRESS_BITS", b["address_bits"]),
                    ("BUS_FIRST_OFFSET", b["first_offset"]), ("BUS_MAGIC", b["magic"])]))
    rows = []
    for name in sorted(d["blocks"], key=lambda n: d["blocks"][n][0]):
        rows += [("BLOCK_%s_FIRST" % name.upper(), d["blocks"][name][0]), ("BLOCK_%s_END" % name.upper(), d["blocks"][name][1])]
    groups.append(("the blocks that share the register map: each one's first byte offset, and its end, one past its last byte", rows))
    rows = []
    for name in sorted(d["registers"], key=lambda n: d["registers"][n][0]):
        offset, access, words = d["registers"][name]
        stem = "REG_%s" % name.upper()
        rows += [(stem + "_OFFSET", offset), (stem + "_WORDS", words),
                 (stem + "_READABLE", 1 if access in ("ro", "rw") else 0),
                 (stem + "_WRITABLE", 1 if access in ("rw", "wo") else 0)]
    groups.append(("the registers: each one's byte offset, its words, and whether the host may read and write it", rows))
    rows = []
    for reg in sorted(d["register_bits"], key=lambda n: d["registers"][n][0]):
        bits = d["register_bits"][reg]
        rows += [("REG_%s_%s_BIT" % (reg.upper(), n.upper()), bits[n]) for n in sorted(bits, key=lambda n: bits[n])]
    groups.append(("the bits of the registers that are read as bits; every other bit of such a register reads zero", rows))
    seen = set()
    for _heading, rows in groups:
        for name, value in rows:
            if name in seen:
                raise Refused("NAMES: two entries of the definition both give the generated name %s" % name)
            seen.add(name)
            if not -2 ** 31 <= value <= 2 ** 31 - 1:
                raise Refused("NUMBER: the generated %s = %d does not fit 32 signed bits" % (name, value))
    return groups


def render_sv(d, pulses, digest):
    L = ["// GENERATED by tools/gen_spec.py from spec/undertone.toml. Do not edit.",
         "//",
         "// Edit the definition, run the generator, commit both. The `generated` stage",
         "// of verify/run.sh fails when this file and the definition disagree.",
         "",
         "package undertone_pkg;",
         "",
         "  // the SHA-256 of the definition this package was generated from",
         "  localparam logic [255:0] SPEC_SHA256 = 256'h%s;" % digest]
    for heading, rows in numbers(d, pulses):
        L += ["", "  // %s" % heading]
        L += ["  localparam int %s = %d;" % row for row in rows]
    L += ["", "endpackage", ""]
    return "\n".join(L)


def render_c(d, pulses, digest):
    L = ["/* GENERATED by tools/gen_spec.py from spec/undertone.toml. Do not edit.",
         " *",
         " * Edit the definition, run the generator, commit both. The `generated` stage",
         " * of verify/run.sh fails when this file and the definition disagree.",
         " */",
         "#ifndef UNDERTONE_H",
         "#define UNDERTONE_H",
         "",
         "/* the SHA-256 of the definition this header was generated from */",
         '#define %sSPEC_SHA256 "%s"' % (C_PREFIX, digest)]
    for heading, rows in numbers(d, pulses):
        L += ["", "/* %s */" % heading]
        L += ["#define %s%s %s" % (C_PREFIX, name, "(%d)" % value if value < 0 else "%d" % value) for name, value in rows]
    L += ["", "#endif", ""]
    return "\n".join(L)


OUTPUTS = ((OUT, render), (OUT_SV, render_sv), (OUT_C, render_c))


def check(root):
    """Returns a list of findings, each (file, what). Empty means every copy is current."""
    try:
        loaded = load(root)
        wants = [(out, fn(*loaded)) for out, fn in OUTPUTS]
    except Refused as e:
        return [(SRC, "REFUSED %s" % e)]
    findings = []
    for out, want in wants:
        path = os.path.join(root, out)
        if not os.path.exists(path):
            findings.append((out, "is missing"))
            continue
        with open(path, "rb") as f:
            have = f.read().decode("utf-8").replace("\r\n", "\n")
        if have == want:
            continue
        a, b = have.split("\n"), want.split("\n")
        for i in range(max(len(a), len(b))):
            if i >= len(a) or i >= len(b) or a[i] != b[i]:
                findings.append((out, "differs from the definition at line %d: has %r, the definition gives %r"
                                 % (i + 1, a[i] if i < len(a) else None, b[i] if i < len(b) else None)))
                break
    return findings


def main(argv):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if "--root" in argv:
        root = os.path.abspath(argv[argv.index("--root") + 1])
    if "--check" in argv:
        findings = check(root)
        for name, what in findings:
            print("FINDING generated %s: %s" % (name, what))
        return 1 if findings else 0
    try:
        loaded = load(root)
        texts = [(out, fn(*loaded)) for out, fn in OUTPUTS]
    except Refused as e:
        print("REFUSED %s" % e)
        return 2
    for out, text in texts:      # nothing is written unless every copy rendered
        with open(os.path.join(root, out), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("wrote %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

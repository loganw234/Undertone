#!/usr/bin/env python3
"""Write a built image's manifest from the tools' own reports, and check an image against its manifest.

    python3 hw/manifest.py write --out DIR --target hw|hw_emu --mhz N --commit C --started T --platform P --part P
    python3 hw/manifest.py check --xclbin FILE --manifest FILE
    python3 hw/manifest.py control --xclbin FILE --manifest FILE --scratch DIR

The lead's (round 3, BUILD). `write` runs at the end of hw/build.sh, where the build ran. `check` and `control`
run wherever `xclbinutil` is, the card day's machine above all. Nothing here runs in the gate: there is no
image and no `xclbinutil` on the desktop. Its pure functions (the readers of the tools' text) are held by
tests/test_build_manifest.py on excerpts of real output.

THE MANIFEST is one `key: value` a line. Fields written from the tool's own output, each with where it came
from: the image's SHA-256 and size; the kernel clock the image carries (`xclbinutil --info`, its "Scalable
Clocks", DATA_CLK); for -t hw, the worst slack of the whole design and every clock's row of the routed
timing summary's Intra Clock Table, as printed, and the kernel's row of the per-kernel utilisation report, as
printed. Fields the build script hands in: the commit, the tree's hash, the clock asked for, the target, the
platform, the part, the times.

THE CHECK compares TWO fields with the image itself: its SHA-256, and its kernel clock as `xclbinutil` reads
it from the image. Either differing is REFUSED by name. Its control (the plan's row BUILD): the right image
with its own manifest must be accepted, and a copy of the manifest with its hash changed, and one with its
clock changed, must each be refused by name.

What it cannot see (stated limits): the commit, the tree's hash, the slack and the utilisation are the build
script's word and the reports' text, and nothing here checks them against the image; the image's identity
block carries the definition's hash, which the card day reads, and not the commit. A report's format is
Vitis 2022.2's as read on 2026-11-24; another version's may not be read, and then the field says "unread".
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tree_hash(root):
    """SHA-256 over every file under rtl/, hw/ and spec/: its path, a zero byte, its bytes, a zero byte, sorted."""
    h = hashlib.sha256()
    names = []
    for top in ("rtl", "hw", "spec"):
        for base, _dirs, files in os.walk(os.path.join(root, top)):
            for n in files:
                names.append(os.path.relpath(os.path.join(base, n), root).replace(os.sep, "/"))
    for rel in sorted(names):
        with open(os.path.join(root, rel), "rb") as f:
            h.update(rel.encode() + b"\0" + f.read() + b"\0")
    return h.hexdigest()


# The kernel's clock is the scalable clock named DATA_CLK, of type DATA: on this platform it is
# ulp_ucs_aclk_kernel_00, the clock `--kernel_frequency` sets and v++ lowers when it does not close. The one
# named KERNEL_CLK, of type KERNEL, is ulp_ucs_aclk_kernel_01, at 500 MHz in every image of round 3's (read on
# 2026-11-25 with `xclbinutil --info` on the third link's image and the sweep's two). Until 2026-11-25 this read
# KERNEL_CLK, and the third link's manifest said 500 where its kernel runs at 100.
SCALABLE = re.compile(r"Name:\s+DATA_CLK\s*\n\s*Index:\s+\d+\s*\n\s*Type:\s+DATA\s*\n\s*Frequency:\s+(\d+)\s+MHz")


def kernel_clock_mhz(info):
    """The kernel's clock an image carries, in whole MHz as `xclbinutil --info`'s "Scalable Clocks" prints DATA_CLK.
    None when it is not there, or is there twice."""
    found = SCALABLE.findall(info)
    return int(found[0]) if len(found) == 1 else None


def design_wns(report):
    """The worst slack of the whole design: the first number under "Design Timing Summary". None if absent."""
    on = False
    for line in report.splitlines():
        if "Design Timing Summary" in line:
            on = True
        elif on:
            parts = line.split()
            if parts and re.match(r"^-?\d+\.\d+$", parts[0]):
                return parts[0]
    return None


def intra_clock_rows(report):
    """Every row of the Intra Clock Table whose WNS is a number, as printed, stripped."""
    rows, on = [], False
    for line in report.splitlines():
        if "Intra Clock Table" in line:
            on = True
        elif on and ("Inter Clock Table" in line or "Other Path Groups Table" in line):
            break
        elif on:
            parts = line.split()
            if len(parts) > 2 and re.match(r"^-?\d+\.\d+$", parts[1]):
                rows.append(" ".join(parts))
    return rows


def kernel_util_rows(report, kernel):
    """Every line of a utilisation report that names the kernel, as printed, stripped."""
    return [" ".join(line.split()) for line in report.splitlines() if kernel in line]


def first(paths):
    for p in paths:
        if os.path.isfile(p):
            return p
    return None


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def info_of(xclbin):
    r = subprocess.run(["xclbinutil", "--info", "--input", xclbin], capture_output=True, text=True, timeout=300)
    return r.stdout + r.stderr


def write_manifest(a):
    out = os.path.abspath(a.out)
    xb = os.path.join(out, "undertone_%s.xclbin" % a.target)
    lines = []

    def put(key, value):
        lines.append("%s: %s" % (key, value))

    put("artifact", os.path.basename(xb))
    put("sha256", sha256_file(xb))
    put("bytes", os.path.getsize(xb))
    put("target", a.target)
    put("commit", a.commit)
    put("tree_sha256", tree_hash(os.getcwd()))
    put("platform", a.platform)
    put("part", a.part)
    put("clock_asked_mhz", a.mhz)
    clock = kernel_clock_mhz(info_of(xb))
    put("kernel_clock_mhz", clock if clock is not None else "unread")
    put("started", a.started)
    if a.target == "hw":
        imp = os.path.join(out, "_x_hw", "link", "vivado", "vpl", "prj", "prj.runs", "impl_1")
        rpt = first([os.path.join(imp, n) for n in ("hw_bb_locked_timing_summary_postroute_physopted.rpt",
                                                    "hw_bb_locked_timing_summary_routed.rpt",
                                                    "dr_timing_summary.rpt")])
        put("timing_report", os.path.basename(rpt) if rpt else "unread")
        if rpt:
            text = read(rpt)
            put("design_wns_ns", design_wns(text) or "unread")
            for row in intra_clock_rows(text):
                put("intra_clock", row)
        util = first(sorted(_glob(os.path.join(out, "_x_hw", "reports", "link", "imp"), "kernel_util_routed")))
        put("kernel_util_report", os.path.basename(util) if util else "unread")
        if util:
            for row in kernel_util_rows(read(util), "undertone_krnl"):
                put("kernel_util", row)
    with open(os.path.join(out, "undertone_%s.manifest.txt" % a.target), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


def _glob(folder, part):
    if not os.path.isdir(folder):
        return []
    return [os.path.join(folder, n) for n in os.listdir(folder) if part in n and n.endswith(".rpt")]


def read_manifest(path):
    fields = {}
    for line in read(path).splitlines():
        if ": " in line:
            k, v = line.split(": ", 1)
            fields.setdefault(k, v)
    return fields


def check(xclbin, manifest, info=None):
    """Returns None when the image and its manifest agree on both fields, else the refusal's text."""
    m = read_manifest(manifest)
    if m.get("sha256") != sha256_file(xclbin):
        return "MANIFEST-HASH: the image's SHA-256 is %s; the manifest says %s" % (sha256_file(xclbin), m.get("sha256"))
    clock = kernel_clock_mhz(info if info is not None else info_of(xclbin))
    if clock is None or m.get("kernel_clock_mhz") != str(clock):
        return "MANIFEST-CLOCK: the image carries a kernel clock of %s MHz; the manifest says %s" % (
            clock, m.get("kernel_clock_mhz"))
    return None


def control(xclbin, manifest, scratch):
    """The right manifest accepted; one with its hash changed and one with its clock changed, each refused."""
    os.makedirs(scratch, exist_ok=True)
    info = info_of(xclbin)
    ok = check(xclbin, manifest, info) is None
    print("control: the image with its own manifest: %s" % ("accepted" if ok else "REFUSED, and it must not be"))
    text = read(manifest)
    for name, key, change in (("hash", "sha256", lambda v: ("0" if v[0] != "0" else "1") + v[1:]),
                              ("clock", "kernel_clock_mhz", lambda v: str(int(v) + 1) if v.isdigit() else "1")):
        planted = []
        for line in text.splitlines():
            k, _sep, v = line.partition(": ")
            planted.append("%s: %s" % (k, change(v)) if k == key else line)
        p = os.path.join(scratch, "planted-%s.manifest.txt" % name)
        shutil.copyfile(manifest, p)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(planted) + "\n")
        said = check(xclbin, p, info)
        good = said is not None and said.startswith("MANIFEST-%s:" % name.upper())
        print("control: the manifest with its %s changed: %s" % (name, said or "accepted"))
        ok = ok and good
    print("CONTROL-DETECTED both planted manifests refused by name, and the right one accepted" if ok
          else "CONTROL-FAILED")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="what", required=True)
    w = sub.add_parser("write")
    for k in ("--out", "--target", "--mhz", "--commit", "--started", "--platform", "--part"):
        w.add_argument(k, required=True)
    c = sub.add_parser("check")
    c.add_argument("--xclbin", required=True)
    c.add_argument("--manifest", required=True)
    k = sub.add_parser("control")
    k.add_argument("--xclbin", required=True)
    k.add_argument("--manifest", required=True)
    k.add_argument("--scratch", required=True)
    a = ap.parse_args()
    if a.what == "write":
        return write_manifest(a)
    if a.what == "check":
        said = check(a.xclbin, a.manifest)
        print("OK manifest: the image's SHA-256 and kernel clock are the manifest's" if said is None
              else "REFUSED %s" % said)
        return 0 if said is None else 1
    return control(a.xclbin, a.manifest, a.scratch)


if __name__ == "__main__":
    sys.exit(main())

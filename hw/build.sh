#!/bin/bash
# Undertone's image build: package the kernel, link it, write the manifest from the tool's own reports.
# The lead's (round 3, BUILD). It runs on amd-arc-box for -t hw and in cft2204 for -t hw_emu, from the root of a
# tree exported by commit (git archive), never in a checkout that may move while a link runs.
#
#   bash hw/build.sh hw     <freq in MHz> <out folder>
#   bash hw/build.sh hw_emu <freq in MHz> <out folder>
#
# THE CLOCK IS ASKED FOR EXPLICITLY, in MHz, and has no default: the sibling project's build script defaults to
# 10 MHz, which closes timing trivially and says nothing (the plan's L25).
#
# PROVENANCE: the commit is the file BUILD_COMMIT the export wrote at the tree's root, and hw/manifest.py takes the
# tree's own hash, a SHA-256 over every file of rtl/, hw/ and spec/. A tree with no BUILD_COMMIT is refused.
#
# What it cannot see: whether the exported tree is the commit it names (the export writes both; nothing here
# checks the one against the other); whether the build's reports are complete; anything about the card.
set -euo pipefail

T=${1:?usage: build.sh <hw|hw_emu> <MHz> <out>}
F=${2:?the kernel clock in MHz, asked for explicitly}
OUT=${3:?an out folder}
case "$T" in hw|hw_emu) ;; *) echo "REFUSED: target '$T' is neither hw nor hw_emu" >&2; exit 2;; esac
case "$F" in ''|*[!0-9]*) echo "REFUSED: '$F' is not a whole number of MHz" >&2; exit 2;; esac
[ "$F" -ge 50 ] || { echo "REFUSED: $F MHz is below 50; a clock that closes trivially says nothing" >&2; exit 2; }
[ -f BUILD_COMMIT ] || { echo "REFUSED: no BUILD_COMMIT at the tree's root: export the tree by commit" >&2; exit 2; }

mkdir -p "$OUT"; OUT=$(cd "$OUT" && pwd)
COMMIT=$(cat BUILD_COMMIT)
STARTED=$(date -Iseconds)

for vroot in /data/Xilinx /opt/Xilinx /tools/Xilinx; do
  if [ -f "$vroot/Vitis/2022.2/settings64.sh" ]; then . "$vroot/Vitis/2022.2/settings64.sh" >/dev/null 2>&1; break; fi
done
command -v v++ >/dev/null || { echo "REFUSED: Vitis 2022.2 not found" >&2; exit 2; }
PLATFORM=xilinx_u50_gen3x16_xdma_5_202210_1
export PLATFORM_REPO_PATHS=${PLATFORM_REPO_PATHS:-$HOME/platforms-root/opt/xilinx/platforms}
[ -d "$PLATFORM_REPO_PATHS/$PLATFORM" ] || { echo "REFUSED: platform $PLATFORM not under $PLATFORM_REPO_PATHS" >&2; exit 2; }
PART=xcu50-fsvh2104-2-e

echo "== $(date '+%H:%M:%S') package (KRNL's script)"
vivado -mode batch -nolog -nojournal -source hw/package_kernel.tcl -tclargs "$PART" "$OUT" > "$OUT/package.log" 2>&1 || true
if grep -qE "^ERROR" "$OUT/package.log" || [ ! -f "$OUT/undertone_krnl.xo" ]; then
  echo "REFUSED: PACKAGE-FAILED: Vivado's packaging printed errors or wrote no undertone_krnl.xo:" >&2
  grep -E "^ERROR|^CRITICAL WARNING" "$OUT/package.log" | head -20 >&2
  exit 1
fi
XO="$OUT/undertone_krnl.xo"
grep -E "^HDLPARAM" "$OUT/package.log" || true

echo "== $(date '+%H:%M:%S') link -t $T at $F MHz"
v++ -l -t "$T" --platform "$PLATFORM" --config hw/link.cfg --kernel_frequency "$F" \
    --save-temps --temp_dir "$OUT/_x_$T" -o "$OUT/undertone_$T.xclbin" "$XO" > "$OUT/link_$T.log" 2>&1 || true
if [ ! -f "$OUT/undertone_$T.xclbin" ]; then
  echo "REFUSED: LINK-FAILED: v++ wrote no image:" >&2
  grep -E "^ERROR" "$OUT/link_$T.log" | head -20 >&2
  exit 1
fi
if [ "$T" = hw_emu ]; then emconfigutil --platform "$PLATFORM" --od "$OUT" > "$OUT/emconfig.log" 2>&1; fi

echo "== $(date '+%H:%M:%S') manifest"
python3 hw/manifest.py write --out "$OUT" --target "$T" --mhz "$F" --commit "$COMMIT" \
    --started "$STARTED" --platform "$PLATFORM" --part "$PART"
echo "== $(date '+%H:%M:%S') end"

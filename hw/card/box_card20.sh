# The card day's second part, on the box, the lead's, 2026-11-25: the five cases again at 2^20 frames, so that
# 7,167 of each case's 8,191 truth records are written while the run goes (the plan's CARD row: "or for 2^20 if
# KRNL's design feeds truth records during a run"; docs/rtl/krnl.md, "2^20 samples can be tried").
# Run as: setsid nohup bash box_card20.sh <host tree> <build folder> <cases folder> > <log> 2>&1 < /dev/null &
# As box_card.sh, but: the cases from the third argument; no `xbutil validate` (on this card XRT 2.19 dies in its
# own device-info parser, "Mac address exceed IP4 maximum value", before any test: cft-fp256's docs/CARDDAY.md,
# step 1, and this round's first part at 08:00:24) and the health read by the reports that answer, dynamic-regions,
# electrical and thermal, before and after; the probe and the raw shapes not again (the first part ran them).
# Every output under /data/undertone-r3/card/run20-<time>. Nothing here resets or programs the card by hand.
set -u
H=$1; B=$2; CASES=$3
K=/data/undertone-r3/card
R=$K/run20-$(date '+%H%M%S')
mkdir -p "$R"; cd "$R" || exit 1
IMG=$B/out/undertone_hw.xclbin
MAN=$B/out/undertone_hw.manifest.txt
LIB=$H/libundertone_xrt.so
BDF=0000:02:00.1
. /opt/xilinx/xrt/setup.sh >/dev/null 2>&1
echo "== $(date '+%H:%M:%S') card run at $R; host tree $H; image $IMG; cases $CASES"
sha256sum "$IMG" "$LIB" "$K/card.py" "$K/manifest.py"

health() {  # before | after
    for r in dynamic-regions electrical thermal; do
        xbutil examine -d "$BDF" -r $r > "$1_$r.txt" 2>&1; echo "$1 $r exit $?"
    done
    grep -E "Device Status|Xclbin UUID|undertone_krnl" "$1_dynamic-regions.txt"
    grep -E "^\s+Power\s+:" "$1_electrical.txt"
    grep -E "\|FPGA " "$1_thermal.txt"
}
echo "== $(date '+%H:%M:%S') health before"
health before

echo "== $(date '+%H:%M:%S') the manifest against the image, by the mended reader $K/manifest.py (DATA_CLK)"
(cd "$B" && python3 "$K/manifest.py" check --xclbin "$IMG" --manifest "$MAN") 2>&1 | tail -2

one() {   # name, extra arguments...
    local name=$1; shift
    local case=$CASES/$name frames seed
    frames=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['frames'])" "$case/case.json")
    seed=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['seed'])" "$case/case.json")
    echo "== $(date '+%H:%M:%S') $name: $frames frames, seed $seed $*"
    (cd "$H" && timeout 900 python3 -m host.run_case --xclbin "$IMG" --shim "$LIB" --blob "$case/case.blob" \
        --table "$case/table.json" --seed "$seed" --frames "$frames" --schedule "$case/schedule.json" \
        --out "$R/$name" --polls 2000000 "$@") > "$R/$name.log" 2>&1
    echo "$name run_case exit $?"; tail -3 "$R/$name.log"
    (cd "$H" && python3 "$K/card.py" compare "$case" "$R/$name") 2>&1 | tail -6
}
swap() {  # name: the case's own swap
    local case=$CASES/$1
    one "$1" --swap-blob "$case/swap.blob" \
        --swap-at "$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['swap_at'])" "$case/case.json")" \
        --swap-after "$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['swap_after'])" "$case/case.json")"
}

one e0
one hidden
one e0_flip
swap e0_swap
swap hidden_swap

echo "== $(date '+%H:%M:%S') health after"
health after
echo "processes holding the card's device files:"; (command -v fuser >/dev/null && fuser -v /dev/xfpga/* /dev/dri/renderD* 2>&1 | head -8) || echo "(fuser not found)"
echo "== $(date '+%H:%M:%S') end"

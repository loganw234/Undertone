# The card day, on the box, the lead's: run as ssh <box> 'bash -s -- <host tree> <build folder>' < this file.
# <host tree>: a folder holding the library (host/), model/, spec/ and the shim built there (libundertone_xrt.so);
# <build folder>: the build's folder, holding out/undertone_hw.xclbin and its manifest. The manifest's reader is the
# mended one of 2026-11-25 at /data/undertone-r3/card/manifest.py, not the build folder's own hw/manifest.py.
# The cases are under /data/undertone-r3/card/cases, card.py at /data/undertone-r3/card/card.py; every output under
# /data/undertone-r3/card/run-<time>. Nothing here resets or programs the card by hand: the library's backend loads
# the image through XRT, as the sibling's hosts do.
set -u
H=$1; B=$2
K=/data/undertone-r3/card
R=$K/run-$(date '+%H%M%S')
mkdir -p "$R"; cd "$R" || exit 1
IMG=$B/out/undertone_hw.xclbin
MAN=$B/out/undertone_hw.manifest.txt
LIB=$H/libundertone_xrt.so
BDF=0000:02:00.1
MAXIMA=cap_sample_bits=16,cap_channels=1,cap_coeff_bits=18,cap_filters=4,cap_taps=128,cap_rows=4,cap_pool=65536,cap_score_shift=31,cap_hidden=12,cap_hidden_shift=31,cap_record_queue=512,cap_noise_table=32767,cap_inject_pending=1024
. /opt/xilinx/xrt/setup.sh >/dev/null 2>&1
echo "== $(date '+%H:%M:%S') card run at $R; host tree $H; image $IMG"
sha256sum "$IMG" "$LIB" "$K/card.py"

echo "== $(date '+%H:%M:%S') health before"
xbutil examine > examine_before.txt 2>&1; echo "examine exit $?"; grep -iE "xilinx_u50|$BDF|shell|Device" examine_before.txt | head -6
xbutil examine -d "$BDF" > examine_dev_before.txt 2>&1; echo "examine -d exit $?"; grep -iE "platform|shell|status|temperature|power" examine_dev_before.txt | head -10
timeout 600 xbutil validate -d "$BDF" > validate.txt 2>&1; echo "validate exit $?"; grep -iE "passed|failed|warning|error|validation" validate.txt | head -14

echo "== $(date '+%H:%M:%S') the manifest against the image, by the mended reader $K/manifest.py (DATA_CLK)"
sha256sum "$K/manifest.py"
(cd "$B" && python3 "$K/manifest.py" check --xclbin "$IMG" --manifest "$MAN") 2>&1 | tail -4
mkdir -p "$R/manifest_control"
(cd "$B" && python3 "$K/manifest.py" control --xclbin "$IMG" --manifest "$MAN" --scratch "$R/manifest_control") 2>&1 | tail -5

echo "== $(date '+%H:%M:%S') the card's XRT: which bytes a partial sync moves, no kernel run"
(cd "$H" && timeout 300 python3 "$K/probe_sync.py" "$IMG" "$LIB") > probe_sync.txt 2>&1
echo "probe exit $?"; tail -6 probe_sync.txt

echo "== $(date '+%H:%M:%S') identity, maxima, raw shapes"
(cd "$H" && timeout 600 python3 "$K/card.py" shapes --xclbin "$IMG" --shim "$LIB" --maxima "$MAXIMA") > shapes.log 2>&1
echo "shapes exit $?"; cat shapes.log | tail -30

one() {   # name, extra arguments...
    local name=$1; shift
    local case=$K/cases/$name frames seed
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
    local case=$K/cases/$1
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
xbutil examine -d "$BDF" > examine_dev_after.txt 2>&1; echo "examine -d exit $?"; grep -iE "platform|shell|status|temperature|power" examine_dev_after.txt | head -10
echo "processes holding the card's device files:"; (command -v fuser >/dev/null && fuser -v /dev/xfpga/* /dev/dri/renderD* 2>&1 | head -8) || echo "(fuser not found)"
echo "== $(date '+%H:%M:%S') end"

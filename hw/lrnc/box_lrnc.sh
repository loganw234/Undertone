# Learning in the fabric on the card, on the box, the lead's (round 5, parcel LRN-C; docs/host/lrn-c.md): the runs
# of order.txt, in order. Modelled on hw/e0c/box_e0.sh, which ran round 4's E0 on the card.
# Run detached (CLAUDE.md, trap 19):
#   setsid nohup bash box_lrnc.sh <host tree> <build folder> <cases folder> > <log> 2>&1 < /dev/null &
# <host tree>: a snapshot of the READY commit holding host/, model/, spec/, hw/e0c/, hw/lrnc/ and the shim built
#   there (libundertone_xrt.so); nothing it runs imports learn/, tests/ or numpy.
# <build folder>: the build's folder, holding out/undertone_hw.xclbin, KRNL-L's image, whose definition is the tree's.
# <cases folder>: hw/lrnc/lrnc.py cases' folder; with expect/<case>/expected.json beside it if the lead copied them.
# Each run is one process (hw/e0c/run_piece.py: host.run_case, unchanged by this script, with Python's cyclic
# collector off) with the case's script under --learn. A run that ends refused is logged and the next goes on.
# After each, records.bin's SHA-256 is set beside the expectation's; the judging is the desktop's
# (hw/lrnc/lrnc.py compare). Every output under /data/undertone-r5/lrnc/run-<time>.
set -u
H=$1; B=$2; CASES=$3
K=/data/undertone-r5/lrnc
R=$K/run-$(date '+%H%M%S')
mkdir -p "$R"; cd "$R" || exit 1
IMG=$B/out/undertone_hw.xclbin
LIB=$H/libundertone_xrt.so
BDF=0000:02:00.1
. /opt/xilinx/xrt/setup.sh >/dev/null 2>&1
echo "== $(date '+%H:%M:%S') learning in the fabric on the card at $R; host tree $H; image $IMG; cases $CASES"
sha256sum "$IMG" "$LIB" "$H/hw/e0c/run_piece.py" "$H/host/run_case.py" "$H/host/library.py" "$H/hw/lrnc/box_lrnc.sh"

health() {  # before | after
    for r in dynamic-regions electrical thermal; do
        xbutil examine -d "$BDF" -r $r > "$1_$r.txt" 2>&1; echo "$1 $r exit $?"
    done
    grep -E "Device Status|Xclbin UUID|undertone_krnl" "$1_dynamic-regions.txt"
    grep -E "^\s+Power\s+:" "$1_electrical.txt"
    grep -E "\|FPGA " "$1_thermal.txt"
}
field() {  # file key
    python3 -c "import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])" "$1" "$2"
}
echo "== $(date '+%H:%M:%S') health before"
health before

one() {   # run name, case name
    local name=$1 case=$2 d frames seed blob epoch bits upd want got
    d=$CASES/$case
    frames=$(field "$d/case.json" frames)
    seed=$(field "$d/case.json" seed)
    blob=$(field "$d/case.json" blob)
    epoch=$(field "$d/case.json" epoch)
    bits=$(field "$d/case.json" count_bits)
    upd=$(field "$d/case.json" update_frames)
    echo "== $(date '+%H:%M:%S') $name: case $case, $frames frames, seed $seed, blob $blob"
    (cd "$H" && timeout 900 python3 hw/e0c/run_piece.py --xclbin "$IMG" --shim "$LIB" --blob "$d/$blob" \
        --table "$CASES/table.json" --seed "$seed" --frames "$frames" --schedule "$d/schedule.json" \
        --learn "$d/script.json" --count-bits "$bits" --update-frames "$upd" --epoch "$epoch" \
        --out "$R/$name" --polls 2000000) > "$R/$name.log" 2>&1 < /dev/null
    echo "$name run_piece exit $?"; tail -2 "$R/$name.log"
    got=$(sha256sum "$R/$name/records.bin" 2>/dev/null | cut -d' ' -f1)
    if [ -f "$CASES/expect/$case/expected.json" ]; then
        want=$(field "$CASES/expect/$case/expected.json" sha256)
        if [ "$got" = "$want" ]; then echo "$name IDENTICAL by its SHA-256 $got"; else echo "$name DIFFERENT: $got, the model's $want"; fi
    else
        echo "$name records $got; no expected.json for its case"
    fi
}

while read -r name case; do
    [ -n "$name" ] && one "$name" "$case"
done < "$CASES/order.txt"

echo "== $(date '+%H:%M:%S') health after"
health after
echo "processes holding the card's device files:"; (command -v fuser >/dev/null && fuser -v /dev/xfpga/* /dev/dri/renderD* 2>&1 | head -8) || echo "(fuser not found)"
(cd "$R" && sha256sum */records.bin */report.json *.log > SHA256SUMS 2>/dev/null); echo "SHA256SUMS: $(wc -l < "$R/SHA256SUMS") files"
echo "== $(date '+%H:%M:%S') end"

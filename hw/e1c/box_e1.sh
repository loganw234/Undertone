# Stage E1 on the card, on the box, the lead's (round 5, parcel E1C): every run of order.txt, in its order: the named
# part's eight pieces, its two swap runs and the flip, then the other parts' eight each. Modelled on hw/e0c/box_e0.sh.
# Run detached (CLAUDE.md, trap 19):
#   setsid nohup bash box_e1.sh <host tree> <build folder> <cases folder> > <log> 2>&1 < /dev/null &
# <host tree>: a snapshot of E1C's commit holding host/, model/, spec/, hw/e0c/, hw/e1c/ and the shim built there
#   (libundertone_xrt.so); nothing it runs imports tests/ or learn/ or needs numpy.
# <build folder>: the build's folder, holding out/undertone_hw.xclbin, the image whose definition is the tree's.
# <cases folder>: hw/e1c/e1c.py cases' folder, with the lead's expect run's expect/ folder in it.
# Each run is one process (hw/e0c/run_piece.py: host.run_case, unchanged, with Python's cyclic collector off), so
# each opens the device afresh and its one buffer is freed at its close. A run's line in order.txt is
#   <name> <case> <blob> <epoch> [<swap blob> <swap at> <swap after>]
# each path under the cases folder. After each run, records.bin's SHA-256 is set beside the expectation's and the log
# says IDENTICAL or DIFFERENT; the judging is the desktop's (hw/e1c/e1c.py compare). Every output under
# /data/undertone-r5/e1c/run-<time>. Nothing here resets or programs the card by hand: the library's backend loads
# the image through XRT. A run that ends refused, a blank set's among them, is logged and the next run goes on.
set -u
H=$1; B=$2; CASES=$3
K=/data/undertone-r5/e1c
R=$K/run-$(date '+%H%M%S')
mkdir -p "$R"; cd "$R" || exit 1
IMG=$B/out/undertone_hw.xclbin
LIB=$H/libundertone_xrt.so
BDF=0000:02:00.1
. /opt/xilinx/xrt/setup.sh >/dev/null 2>&1
echo "== $(date '+%H:%M:%S') E1 on the card at $R; host tree $H; image $IMG; cases $CASES"
sha256sum "$IMG" "$LIB" "$H/hw/e0c/run_piece.py" "$H/hw/e1c/box_e1.sh" "$CASES/order.txt"

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

one() {   # name case blob epoch [swap blob, swap at, swap after]
    local name=$1 case=$2 blob=$3 epoch=$4 frames seed want got swap
    frames=$(field "$CASES/$case/piece.json" frames)
    seed=$(field "$CASES/$case/piece.json" seed)
    swap=""
    if [ $# -eq 7 ]; then swap="--swap-blob $CASES/$5 --swap-at $6 --swap-after $7"; fi
    echo "== $(date '+%H:%M:%S') $name: $frames frames, seed $seed, blob $blob, epoch $epoch${swap:+, $swap}"
    # $swap is left unquoted on purpose: it is empty, or six words
    (cd "$H" && timeout 900 python3 hw/e0c/run_piece.py --xclbin "$IMG" --shim "$LIB" --blob "$CASES/$blob" \
        --epoch "$epoch" --table "$CASES/table.json" --seed "$seed" --frames "$frames" \
        --schedule "$CASES/$case/schedule.json" --out "$R/$name" --polls 2000000 $swap) > "$R/$name.log" 2>&1 < /dev/null
    echo "$name run_piece exit $?"; tail -2 "$R/$name.log"
    got=$(sha256sum "$R/$name/records.bin" 2>/dev/null | cut -d' ' -f1)
    if [ -f "$CASES/expect/$name.json" ]; then
        want=$(field "$CASES/expect/$name.json" sha256)
        if [ "$got" = "$want" ]; then echo "$name IDENTICAL by its SHA-256 $got"; else echo "$name DIFFERENT: $got, the model's $want"; fi
    else
        echo "$name records $got; no expectation beside its case"
    fi
}

while read -r line; do
    [ -n "$line" ] || continue
    # shellcheck disable=SC2086
    one $line
done < "$CASES/order.txt"

flip=$(grep -E '^flip-' "$CASES/order.txt" | cut -d' ' -f1)
against=$(field "$CASES/expect/$flip.json" against 2>/dev/null)
want=$(field "$CASES/expect/$against.json" sha256 2>/dev/null)
got=$(sha256sum "$R/$flip/records.bin" 2>/dev/null | cut -d' ' -f1)
if [ "$got" = "$want" ]; then echo "$flip the SAME as $against's: the flip was NOT seen"; else echo "$flip differs from $against's, as it must"; fi

echo "== $(date '+%H:%M:%S') health after"
health after
echo "processes holding the card's device files:"; (command -v fuser >/dev/null && fuser -v /dev/xfpga/* /dev/dri/renderD* 2>&1 | head -8) || echo "(fuser not found)"
(cd "$R" && sha256sum */records.bin */report.json > SHA256SUMS 2>/dev/null); echo "SHA256SUMS: $(wc -l < "$R/SHA256SUMS") files"
echo "== $(date '+%H:%M:%S') end"

# Stage E0 on the card, on the box, the lead's (round 4, track A): every piece of the five amplitudes, the flip
# control, then the ten timed runs. Modelled on hw/card/box_card20.sh, which ran round 3's card day.
# Run detached (CLAUDE.md, trap 19):
#   setsid nohup bash box_e0.sh <host tree> <build folder> <cases folder> > <log> 2>&1 < /dev/null &
# <host tree>: a snapshot of the merge holding host/, model/, spec/, hw/e0c/ and the shim built there
#   (libundertone_xrt.so); nothing it runs imports tests/ or needs numpy.
# <build folder>: the build's folder, holding out/undertone_hw.xclbin, the image whose definition is the tree's.
# <cases folder>: hw/e0c/e0c.py cases' folder, with each expected.json of the lead's expect run beside its case.
# Each piece is one process (hw/e0c/run_piece.py: host.run_case, unchanged, with Python's cyclic collector off),
# so each opens the device afresh and its one buffer is freed at its close. After each, records.bin's SHA-256 is
# set beside the expectation's and the log says IDENTICAL or DIFFERENT; the judging is the desktop's
# (hw/e0c/e0c.py compare). Every output under /data/undertone-r4/e0c/run-<time>. Nothing here resets or programs
# the card by hand: the library's backend loads the image through XRT.
set -u
H=$1; B=$2; CASES=$3
K=/data/undertone-r4/e0c
R=$K/run-$(date '+%H%M%S')
mkdir -p "$R"; cd "$R" || exit 1
IMG=$B/out/undertone_hw.xclbin
LIB=$H/libundertone_xrt.so
BDF=0000:02:00.1
. /opt/xilinx/xrt/setup.sh >/dev/null 2>&1
echo "== $(date '+%H:%M:%S') E0 on the card at $R; host tree $H; image $IMG; cases $CASES"
sha256sum "$IMG" "$LIB" "$H/hw/e0c/run_piece.py" "$H/hw/e0c/timed.py" "$H/hw/e0c/box_e0.sh"

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

one() {   # case folder, blob, out name
    local case=$1 blob=$2 name=$3 frames seed want got
    frames=$(field "$case/piece.json" frames)
    seed=$(field "$case/piece.json" seed)
    echo "== $(date '+%H:%M:%S') $name: $frames frames, seed $seed, blob $blob"
    (cd "$H" && timeout 900 python3 hw/e0c/run_piece.py --xclbin "$IMG" --shim "$LIB" --blob "$blob" \
        --table "$CASES/e0/table.json" --seed "$seed" --frames "$frames" --schedule "$case/schedule.json" \
        --out "$R/$name" --polls 2000000) > "$R/$name.log" 2>&1
    echo "$name run_piece exit $?"; tail -2 "$R/$name.log"
    got=$(sha256sum "$R/$name/records.bin" 2>/dev/null | cut -d' ' -f1)
    if [ -f "$case/expected.json" ]; then
        want=$(field "$case/expected.json" sha256)
        if [ "$got" = "$want" ]; then echo "$name IDENTICAL by its SHA-256 $got"; else echo "$name DIFFERENT: $got, the model's $want"; fi
    else
        echo "$name records $got; no expected.json beside its case"
    fi
}

for case in $(ls -d "$CASES"/e0/a*p* | sort -V); do
    one "$case" "$CASES/e0/case.blob" "$(basename "$case")"
done
one "$CASES/flip/a2p0" "$CASES/flip/case.blob" flip-a2p0
want=$(field "$CASES/e0/a2p0/expected.json" sha256 2>/dev/null)
got=$(sha256sum "$R/flip-a2p0/records.bin" 2>/dev/null | cut -d' ' -f1)
if [ "$got" = "$want" ]; then echo "flip-a2p0 the SAME as e0's a2p0: the flip was NOT seen"; else echo "flip-a2p0 differs from e0's a2p0, as it must"; fi

echo "== $(date '+%H:%M:%S') the ten timed runs"
L0=$(date +%s%N)
(cd "$H" && timeout 900 python3 hw/e0c/timed.py --xclbin "$IMG" --shim "$LIB" --cases "$CASES/timed" \
    --out "$R/timed" --launched-ns "$L0") > "$R/timed.log" 2>&1
echo "timed exit $?"; tail -12 "$R/timed.log"

echo "== $(date '+%H:%M:%S') health after"
health after
echo "processes holding the card's device files:"; (command -v fuser >/dev/null && fuser -v /dev/xfpga/* /dev/dri/renderD* 2>&1 | head -8) || echo "(fuser not found)"
(cd "$R" && sha256sum */records.bin */report.json timed/timed.json > SHA256SUMS 2>/dev/null); echo "SHA256SUMS: $(wc -l < "$R/SHA256SUMS") files"
echo "== $(date '+%H:%M:%S') end"

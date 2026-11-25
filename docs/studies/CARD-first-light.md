# The card day: first light on the U50

Round 3's card day, the lead's, on 2026-11-25, in one booked daytime window. It is the plan's row CARD ([R3-first-light.md](../plans/R3-first-light.md)), run on the third link's image: the kernel of [krnl.md](../rtl/krnl.md) built at 100 MHz from commit `31aaec1`, driven by the host library of [host.md](../host/host.md) through XRT, from `amd-arc-box`, on its Alveo U50. The scripts that ran are under `hw/card/`, each byte for byte the file that ran.

**What rests on what.** Everything here is bit identity: the card's score words against the reference model's own run of the same configuration, stream and swap. It is bit identity's third part, the card, after the RTL in simulation and the library over the simulated kernel. **It is not evidence about sensitivity** (D0, section 2): every case below would pass the same way if the detector could see nothing. Nor is it a throughput figure, or anything about learning: the card ran weights the host gave it.

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure here has a row in the register at the end.

## The result

**Every score word the card put out, in ten runs of five cases, equals the model's, byte for byte. In both runs of the control, a flipped coefficient bit is seen, and the card's records equal the model's run of the flipped blob.**

The cases are `hw/card/card.py`'s, all under the build's one profile, `s16x1`. Each uses stage E0's stream: noise of sigma 1477, seed 2026112302, and the e0 pulse at amplitude 1/1 every 128 frames from frame 64.

- **e0:** E0's matched filter.
- **hidden:** a seeded shape at the build's maxima that uses the hidden layer: 4 filters of 128 taps, 12 units, pool 3.
- **e0_swap** and **hidden_swap:** each of those, with a weight swap written by the host while the run goes, committed at a named index.
- **e0_flip:** the control, e0's blob with bit 12 of filter 0's tap 28 flipped (-131071 to -126975).

| case | 2^17 frames (part one) | 2^20 frames (part two) |
|---|---|---|
| e0 | IDENTICAL, 131,072 records | IDENTICAL, 1,048,576 records |
| hidden | IDENTICAL | IDENTICAL |
| e0_swap | IDENTICAL; swap at 65,536 | IDENTICAL; swap at 524,288 |
| hidden_swap | IDENTICAL; swap at 98,304 | IDENTICAL; swap at 786,432 |
| e0_flip | DIFFERENT from e0's in 130,998 records, the model's own count; IDENTICAL to the flipped blob's model run | DIFFERENT in 1,048,235, the model's count; IDENTICAL to the flipped blob's model run |

Each record file's SHA-256 is its expected file's (rows C6 and C9). The swap is held by the records on either side of its index being equal, as the plan says it is on the card: a swap that landed early or late would change the records between the two indices.

**Truth records written while the run goes (part two).** At 2^20 frames each case has 8,191 truth records. The library wrote 1,024 before the start and 7,167 while the run went. The least slack, a record's index less the core's next index when the host wrote it, was 110,316 frames or more in every case. So the host never came near falling behind, and every injected pulse's score is the model's. In part one all 1,023 records went in before the start, and nothing was fed during the run.

## The host's time to make a swap

From the call of the first shadow write to the return of the read that says the commit was taken, in Python, through `xrt::ip`, with the shadow's words and the commit's each sent as one batch. It is the host's clock, `time.perf_counter_ns`, as each run's `trace.json` records it:

| swap | 2^17 run | 2^20 run |
|---|---|---|
| e0_swap, 66 words | 102,332 ns | 453,233 ns |
| hidden_swap, 573 words | 484,101 ns | 421,869 ns |

**These four say the host made a swap in 0.1 to 0.5 ms, and no more.** The same swap varied more than fourfold between runs, and the larger was once the quicker. What part is Python, the shim, XRT, the driver or PCIe is not separated (host.md, limit 6).

The two reads of `next_index` that bracket each swap put the swap inside 693, 2,519, 2,344 and 2,194 frames. Against their times, the shortest window gives 171 to 206 ns a frame, and the other three give 198 to 202. So about 200 ns, 20 clocks at 100 MHz, as krnl.md's row K8 assumes. These are four windows of under half a millisecond each, not a measured rate.

## What else was read

- **The image is the one loaded.** After each part `xbutil examine -d 0000:02:00.1 -r dynamic-regions` showed Xclbin UUID F6B95DCF-E412-CEF2-7DE7-827DEE594773, the image's, with the compute unit `undertone_krnl:undertone_krnl_1` at 0x1400000. The image's SHA-256 is fce0e2397f16407d..., and the manifest's check passed with its control (the mended reader of 68989eb).
- **The identity block** read by the library: id 0x554E4454 ("UNDT"), version 1, and the definition's SHA-256 0a9242e5..., the tree's. The library refuses any other. Its 13 capabilities each equal the build's.
- **Raw shapes.** For eight capabilities, a shape exactly at it and one just past it were written raw to the core's registers. Each at a capability left refusal 0. Each past one was refused by the fabric under its own name: SHAPE_FILTERS, SHAPE_TAPS, SHAPE_POOL, SHAPE_SHIFT, SHAPE_HIDDEN, SHAPE_HIDDEN_SHIFT, and PROFILE_UNKNOWN for the sample's bits and its channels.
- **A partial sync on the card's XRT 2.19** (`hw/card/probe_sync.py`, written for the emulator and run unchanged, no kernel run) moved [offset, offset + size) and left the rest of the host's copy as it was. Under the emulator's XRT 2.14 it moved [offset, size) and zeroed the rest (host.md, row H22). The backend syncs from byte 0 either way.
- **The card's health.** After each part: Device Status HEALTHY, about 15.0 to 15.2 W, FPGA 35 to 38 C, HBM 30 to 33 C. Nothing held the card's device files after either part, and after part two no process of the lead's remained. The card was left with this image loaded, as XRT leaves the last image. Before part one only "present and ready" was read: see limit 6.

## How it was run

- **Part one**, 08:00:24 to 08:00:35: `hw/card/box_card.sh`, the plan's five cases at 2^17 frames, after the manifest's check and its control, the sync probe, and the raw shapes.
- **Part two**, 08:08:51 to 08:09:14: `hw/card/box_card20.sh`, the same five cases at 2^20 frames. The plan's row runs 2^17 samples, "or for 2^20 if KRNL's design feeds truth records during a run". It does (the library's `ahead`, krnl.md's "2^20 samples can be tried"), and the window had time left: a DECISION of the lead's at 08:06. Its cases were made beside the model on the desktop, `python hw/card/card.py cases <folder> --frames 1048576`, in 2 min 48 s.
- **Both detached on the box**, the one way a run there survives its ssh. Each folder's files were copied back and each file's SHA-256 compared on both machines. The run folders, the logs and the cases are in the round's folder and are not committed. Their figures are copied here, each with the file that gives it.
- **The window**: the card booked sensitive and the box shared, 08:00 to 11:00. Both bookings were released at 08:10, the work done.

## Limits

1. **Bit identity only.** Not sensitivity, not learning, not a rate. The cases are configurations the host wrote, compared with the model's run of the same.
2. **One profile, one seed, one clock.** `s16x1`, seed 2026112302, 100 MHz. The definition's maxima and the second sample format are not on the card (the plan, "Later rounds").
3. **The host never fell behind.** A truth record written late, and what the fabric does with one, was not tried on the card; the fabric's INJECT_OVERLAP and the library's naming of it are held in simulation and in the first size (host.md, limit 9). The record queue never held more than one record (`queue_peak` 1 in every run), so its pressure is not tried either.
4. **A swap a clock late cannot be planted in a built image.** On the card the swap is held by the comparison alone. Its mutants are in simulation (the plan, its note on CARD).
5. **The swap's time is the host's**, four samples, batched, through one stack. It says nothing of the fabric's own time to take a commit.
6. **The health before part one is "present and ready" alone.** On this card XRT 2.19's `xbutil validate` dies in its own device-info parser, "Mac address exceed IP4 maximum value", before any test. `examine -d` without a report name stops after its device table. cft-fp256 met the same on 2026-09-08 (its own CARDDAY record, step 1). Part two reads the reports that answer, before and after.
7. **The compute unit's usage counter reads 0.** That is because the kernel is user-managed and XRT's scheduler never starts it: BELIEVED, not read.
8. **The expected records are the model's own.** The cases' known answers come from `model.detector.Core` on `model.inject.inject`'s stream. That is what bit identity asks: the card against the authority. A fault shared by the model and the RTL would pass here, as it would in simulation.
9. **The scripts are kept as they ran.** `probe_sync.py`'s docstring speaks of the emulator only, and `box_card.sh` runs `xbutil validate`, which fails on this card. Neither is a script for a next card day as it stands.

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| C1 | Part one ran from 08:00:24 to 08:00:35 on 2026-11-25 and part two from 08:08:51 to 08:09:14, each detached on the box, each ending with its script's "end" line | MEASURED | each part's log on the box, `day-080024.log` and `day20-080851.log`, copied back with equal SHA-256; the round's ledger, entries 08:06 and 08:10 | those logs |
| C2 | The scripts under `hw/card/` are the files that ran: box_card.sh e22bff84..., box_card20.sh 86bb0c50..., card.py 3fac7e6a..., probe_sync.py 9239d608... | MEASURED | `sha256sum` on the box before each run and on the committed files | `sha256sum hw/card/*` |
| C3 | The card had the image loaded, UUID F6B95DCF-E412-CEF2-7DE7-827DEE594773, the image's own | MEASURED | `xbutil examine -d 0000:02:00.1 -r dynamic-regions` after part one and before and after part two; `xclbinutil --info` on the image | those reports |
| C4 | The identity block carried id 0x554E4454, version 1 and the definition's SHA-256 0a9242e5..., and 13 capabilities each the build's | MEASURED | each run's `report.json`, its `identity`; `card.py shapes`, "the image says N, the build asked N" for each | those files |
| C5 | Eight capabilities: at each, refusal 0; past each, the refusal by its name, raised by the fabric | MEASURED | `card.py shapes`, "PASS card.shapes", sixteen rows | that output |
| C6 | Part one's five cases of 131,072 frames: four IDENTICAL to the model's records, and e0_flip DIFFERENT from e0's in 130,998 records and IDENTICAL to the flipped blob's model run; each records.bin's SHA-256 its expected file's | MEASURED | `card.py compare`, each case; `sha256sum` of each records.bin and expected file | those files |
| C7 | 130,998 and 1,048,235 are the model's counts of records the flip changes, at 2^17 and 2^20 | COMPUTED | `card.py cases`, its `records_the_flip_changes`, the model's runs of both blobs | that script |
| C8 | Part two's cases have 8,191 truth records each, 1,024 written before the start and 7,167 while the run went, the least slack 110,316 frames or more | MEASURED | each run's `report.json`: truth_before_start, truth_while_running, least_slack | those files |
| C9 | Part two's five cases of 1,048,576 frames: four IDENTICAL, and e0_flip DIFFERENT in 1,048,235 records and IDENTICAL to the flipped blob's model run; each records.bin's SHA-256 its expected file's | MEASURED | `card.py compare`, each case; `sha256sum` of each records.bin and expected file | those files |
| C10 | The host's time from its first shadow write to the accepting read: 102,332 and 453,233 ns for the 66-word swap, 484,101 and 421,869 ns for the 573-word swap | MEASURED | each swap's `trace.json`, the ns before its first shadow op and after its accepting op | those files |
| C11 | Each swap took at most 693, 2,519, 2,344 and 2,194 frames: the spans between the two reads of next_index that bracket it | MEASURED | each swap's `report.json`, next_index_before and next_index_after | those files |
| C12 | About 200 ns a frame, 20 clocks at 100 MHz, in those four windows: 171 to 206 ns in the 693-frame window, 198 to 202 in the other three | COMPUTED | C11's spans over the times between the two reads, from `trace.json`, from the first read's return to the second's call (inner) and from the first's call to the second's return (outer) | the reads' times |
| C13 | On the card's XRT 2.19 a partial sync of the buffer moved [offset, offset + size) in both directions and left the rest | MEASURED | `hw/card/probe_sync.py`'s output in part one | that output |
| C14 | After each part the card was HEALTHY, about 15 W, FPGA 35 to 38 C, nothing holding its device files | MEASURED | the `-r dynamic-regions`, `-r electrical` and `-r thermal` reports; `fuser -v` on its device files | those reports |
| C15 | `xbutil validate` exits 1 on this card, "Mac address exceed IP4 maximum value", before any test | MEASURED | `validate.txt`, part one | that file |
| C16 | The kernel's compute unit's usage counter reads 0 because the kernel is user-managed and XRT's scheduler never starts it | BELIEVED | the counter read 0 after both parts (C3's report); the library starts the kernel by register writes through `xrt::ip` (host.md, section 7) | XRT's documentation of the counter |
| C17 | Running part two at 2^20 frames, inside the same window | DECISION | the lead's, 08:06, by the plan's row CARD and krnl.md's "2^20 samples can be tried" | not applicable |

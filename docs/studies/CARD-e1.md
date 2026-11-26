# Stage E1 on the card

Round 5's first card day, the lead's, on 2026-11-26, 08:00 to 08:18, in a booked daytime window. Stage E1's held-out streams ran on the U50 in pieces, every record compared with the reference model's. The six parts were then read from the card's own bytes and judged by stage E1's own judge. Two more runs swap a trained set in mid-stream at the index the host names, and one flips a coefficient. It ran on round 3's image (the kernel of [krnl.md](../rtl/krnl.md), built at 100 MHz from `31aaec1`, the image of [CARD-first-light.md](CARD-first-light.md) and [CARD-e0.md](CARD-e0.md)), driven by the host library through XRT from `amd-arc-box`. The host side is parcel E1C's, [e1c.md](../host/e1c.md). The box ran a snapshot of E1C at `dc33d30` (`host/`, `model/`, `spec/`, `hw/e0c/`, `hw/e1c/`).

**What rests on what.** Two results with two authorities (D0, section 2):
- **Bit identity rests on the model.** Every record of each of the 51 runs is the model's own run of the same piece, word for word.
- **The counts rest on stage E1's committed record** ([E1-software.md](E1-software.md)), and on `stats/` inside E1's judge. Each part read from the card's bytes must equal E1's committed part key for key, and E1's judge must print its committed output byte for byte.

Because every record is the model's, the card's parts are E1's parts in software, exactly. So the second result is E1's software result, now read from the card's records; it adds nothing to E1 about sensitivity. **Nothing here is learning in the fabric.** The sets were learned on the desktop, in software. The host loaded each one, or wrote it into the shadow and committed the swap, and this image's kernel has no learner.

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure here has a row in the register at the end.

## The result

**`== E1 CARD VERDICT: PASS`. All 51 runs are IDENTICAL to the model's, every word. Each of the six parts read from the card's bytes is EQUAL to E1's committed part, key for key, and E1's own judge on them prints its committed output byte for byte, ending `== E1 SOFTWARE VERDICT: PASS`. Both swaps were seen at the named index, and the flipped coefficient was seen at the record predicted.**

The learned set on each part's held-out injections, at its own measured threshold, and the matched filter on the same stream, read from the card's records (the judge's lines, [e1/judge-output.txt](e1/judge-output.txt)):

| truth records | learned: found of 100,000 | efficiency | against E0's figure | matched filter: found |
|---|---|---|---|---|
| 16 | 18,814 | 0.18814 | -99.24 se, OUTSIDE | 49,614 |
| 64 | 38,385 | 0.38385 | -37.01 se, OUTSIDE | 50,316 |
| 256 | 44,901 | 0.44901 | -16.29 se, OUTSIDE | 50,319 |
| 1,024 | 48,985 | 0.48985 | -3.31 se, INSIDE | 49,895 |
| 4,096 | 50,013 | 0.50013 | -0.04 se, INSIDE | 50,301 |
| 16,384 | 49,492 | 0.49492 | -1.70 se, INSIDE | 49,496 |

**The reported model, named before E1's run, is part 5:** 49,492 of 100,000, efficiency 0.49492, against E0's figure 0.50026, -1.70 se, INSIDE the tolerance of 0.01258. These are E1's own numbers; the card's records give them exactly.

At each part:
- the flags are 0;
- every score read of the learned set is the statistics package's own integer read of the same samples;
- the card's matched-filter reads of the first 256 test trials are the statistics' 512 scores.

The record is [e1-card/card-e1.json](e1-card/card-e1.json). What the judge printed is [e1-card/compare-output.txt](e1-card/compare-output.txt), and the box's sums of every run's records and report are [e1-card/records-sha256.txt](e1-card/records-sha256.txt).

**The two swap runs**, each on part 5's stream from frame 0, 4,194,304 frames. Each loads a set at epoch 0, has the host write the learned set into the shadow once the core has taken 1,048,576 frames, and commits it at 2,097,152:
- **swap-blank**, from E1's blank set (every coefficient 0), E1's own flow: IDENTICAL. The first record of epoch 1 is at 2,097,152, the named index. The two `next_index` reads that bracket the swap are 1,049,468 and 1,050,033, both below it. Its first 2,097,152 records equal the desktop's blank run, so part 5's training-stretch keys are the card's own.
- **swap-matched**, from the matched filter: IDENTICAL, the first record of epoch 1 at 2,097,152, bracketed by 1,049,776 and 1,050,357.

**Three things e1c.md listed as untried on the card are now run** (its limit 7):
- an empty schedule: the 24 runs of the 12 calibration pieces, each IDENTICAL;
- a load at epoch 1: the 24 learned runs, each IDENTICAL;
- the blank set loaded and swapped out: swap-blank, IDENTICAL.

**The flip control**, on part 5's learned piece 0, with bit 12 of tap 28 flipped (-131,071 to -126,975). The card's records are IDENTICAL to the flipped set's own model run, and DIFFERENT from the learned set's. They differ first at record 35, the record predicted, in the score field: 69,605,316 against 76,883,908, a difference of -7,278,592 as predicted. 98 blocks of 98 differ. `== E1C FLIP CONTROL: SEEN`.

**The injector was never short.**
- Each test piece wrote 1,024 truth records before its start and 48,976 while it ran; each swap run 1,024 and 15,360.
- The host stayed at least 129,796 frames ahead of the core in the 48 judged pieces, and at least 129,140 in the swap runs.
- The queue never held more than one record.

## How it was run

- **The expectations first**, on the desktop on 2026-11-25, on E1C's `488dbf8`:
  - `e1c.py cases`, 21:48:36 to 21:49:23;
  - the nine `expect` processes, 21:49:23 to 22:09:25.
  
  They were hashed in the round's ledger before the card ran. They are also the premise at full scale: in pieces, each part's model run is EQUAL to E1's committed part. The code they read is the same at `dc33d30`.
- **On the box**, detached, `hw/e1c/box_e1.sh` from 08:00:06 to 08:18:24:
  - health before;
  - part 5's eight pieces, its two swap runs and the flip, then parts 4 to 0, eight pieces each, one process a run, from 08:00:07 to 08:18:06;
  - health after.
  
  A judged piece took 20 to 24 s whole, 21.4 s on average, and a swap run 14 to 15 s. The box was also running a v++ link of this project's at nice 19 throughout. No figure here is a timing of the card's.
- **Back on the desktop:**
  - The run folder was copied back from 08:19:26 to 08:29:16, all 211 files and 7,871,590,876 bytes, every file's SHA-256 equal on both machines. Its records are 6,761,760,768 bytes.
  - Then `e1c.py compare`, 08:28:06 to 08:28:39, on E1C's `e60f981`, whose `hw/` is `dc33d30`'s.
  - The records stay in the round's folder on the desktop and are not committed. The box's copy was removed after the check, for another project's room on `/data`.
- **Health:**
  - before: HEALTHY, 22.04 W, FPGA 32 C, another image loaded (UUID 16658FE4-F5E9-1E70-F20C-041145575AC8);
  - after: HEALTHY, 15.06 W, FPGA 35 C, HBM 30 C, round 3's image (UUID F6B95DCF-E412-CEF2-7DE7-827DEE594773) with its compute unit at 0x1400000;
  - nothing held the card's device files after.

`tests/test_e1c_card_record.py` holds the committed record:
- each file's SHA-256;
- stage E1's own judge, given only the record's six parts, prints E1's committed output byte for byte and returns 0, and each part is E1's committed part key for key;
- the record and the printed output agree on every condition the verdict rests on, and the box's sums name exactly the runs the output names.

The judge's test skips by name, `E1C-CARD-STALE`, once the definition moves past round 3's, as stage E0's card record does ([CARD-e0.md](CARD-e0.md)).

## Limits

1. **One card, one clock, one profile, one sample format.** The U50, 100 MHz, `s16x1`, `e0` at amplitude 1/1.
2. **Not new evidence about sensitivity.** The counts equal E1's in software because the records equal the model's. The card shows that it reproduces E1's result word for word, not that the learner is better than E1 said.
3. **Not learning in the fabric.** The sets were learned in software on the desktop, from windows the model made, and handed to the card by the host. Nothing was captured from the card, which returns scores only (e1c.md, limit 2).
4. **The expected records are the model's own,** from the same configuration and seeds. A fault shared by the model and the RTL would pass here, as in simulation.
5. **The judged runs hold no swap.** The learned set is loaded at epoch 1. The hand-over at the named index is on the card in part 5's two swap runs alone (e1c.md, limit 3), and parts 0 to 4's blank training stretch is the desktop's model run (limit 4).
6. **The card's stream is not seen:** the card returns scores only, so `stream_sha256` in each part is the desktop's (e1c.md, limit 5).
7. **The collector was off in every run,** as in stage E0's card day. Whether a collection would have outlasted the injector's slack is not measured. The least slack seen was 129,140 frames.
8. **`xbutil validate` was not run;** it dies on this card (CLAUDE.md, trap 21). Health is the three `examine` reports, before and after.
9. **What is not committed:** the records, the traces and the run logs, 7.9 GB, kept on the desktop. The swaps' and the flip's judgement need the records, so the committed test holds the record's checks and the printed lines as written, not judged again.
10. **The record is round 3's definition's.** On a tree whose definition has moved past it, round 5's among them, the record's judge test skips by name.

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| CF1 | The card day ran on the box from 08:00:06 to 08:18:24 on 2026-11-26, detached, ending with its script's "end" line; the 51 runs from 08:00:07 to 08:18:06 | MEASURED | the box's log `e1c-day.log`, copied back; the round's ledger, entries 08:19 and 08:30 | that log |
| CF2 | The box ran a snapshot of E1C at `dc33d30`: the image fce0e239..., the shim 8b0c6911..., run_piece.py 5b029e90..., box_e1.sh 864a56cc..., order.txt 9270e121..., under the definition 0a9242e5... | MEASURED | `sha256sum` in the log's first lines; the prep's import line; `git show dc33d30:<path>` hashed on the desktop | those hashes |
| CF3 | The model's expectations were made on the desktop from 21:48:36 to 22:09:25 on 2026-11-25 and hashed before the card ran; each part's model run in pieces is EQUAL to E1's committed part | MEASURED | `e1c.py cases` and `expect` on `488dbf8`; the ledger's 22:09 entry; its expect-488dbf8.sha256, 6765067b... | a rerun of `expect` |
| CF4 | All 51 runs are IDENTICAL to the model's, every record, by their block hashes | MEASURED | `e1c.py compare`, [e1-card/compare-output.txt](e1-card/compare-output.txt) | the records |
| CF5 | Each of the six parts read from the card's bytes is EQUAL to E1's committed part, key for key; flags 0; every learned read the statistics'; the matched reads of the first 256 test trials the statistics' scores | MEASURED | compare's part lines; [e1-card/card-e1.json](e1-card/card-e1.json), its `checks` | the records |
| CF6 | E1's own judge on the six card parts prints `docs/studies/e1/judge-output.txt` byte for byte and returns 0; its last line is `== E1 SOFTWARE VERDICT: PASS` | MEASURED | compare's judge line; `tests/test_e1c_card_record.py` | that test |
| CF7 | The table's counts, efficiencies and se figures, and the reported model's 49,492 of 100,000, -1.70 se against E0's 0.50026, tolerance 0.01258 | READ | [e1/judge-output.txt](e1/judge-output.txt), printed again from the card's parts (CF6) | CF6 |
| CF8 | Both swap runs are IDENTICAL, 4,194,304 records each; the first record of epoch 1 is at 2,097,152 in each; the `next_index` brackets are 1,049,468 to 1,050,033 and 1,049,776 to 1,050,357 | MEASURED | compare's swap lines; card-e1.json, `checks` | the records and reports |
| CF9 | swap-blank's records 0 to 2,097,151 equal the desktop's blank run | MEASURED | compare's part 5 line, `blank_prefix_equal` | the records |
| CF10 | The flip run is IDENTICAL to the flipped set's model run and differs from the learned set's first at record 35, score, 69,605,316 against 76,883,908, a difference of -7,278,592 as predicted, in 98 blocks of 98 | MEASURED | `compare_flip`, compare's flip lines; card-e1.json, `checks.flip` | the flip's records, kept on the desktop |
| CF11 | Each test piece wrote 1,024 truth records before its start and 48,976 while it ran, each swap run 1,024 and 15,360; the least slack was 129,796 frames in the judged pieces and 129,140 in the swap runs; the queue's peak was 1 | MEASURED | each run's `report.json`, in compare's identity lines | those reports |
| CF12 | A judged piece took 20 to 24 s whole on the box, 21.4 s on average; a swap run 14 to 15 s | MEASURED | the log's start time of each run | that log |
| CF13 | The card read HEALTHY before and after; before, 22.04 W and FPGA 32 C with another image loaded (UUID 16658FE4-F5E9-1E70-F20C-041145575AC8); after, round 3's image F6B95DCF-E412-CEF2-7DE7-827DEE594773 and its compute unit, 15.06 W, FPGA 35 C, HBM 30 C; nothing held the device files | MEASURED | `xbutil examine -r dynamic-regions`, `electrical`, `thermal`, and `fuser`, in the log | those reports |
| CF14 | The run folder copied back is 211 files and 7,871,590,876 bytes, each file's SHA-256 equal on both machines; its records are 6,761,760,768 bytes | MEASURED | `sha256sum -c` on the desktop of the box's SHA256SUMS (102 files), its trace sums (51) and the rest (58); `du -sb`; the ledger, 08:30 | those files |
| CF15 | The box also ran this project's v++ link at nice 19 throughout the card day | MEASURED | the link's log on the box, "Step impl" from 05:46:11; the round's ledger | that log |

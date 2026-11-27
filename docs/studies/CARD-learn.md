# Learning in the fabric on the card

Round 5's second card day, the lead's, on 2026-11-27, 08:00:28 to 08:01:35, in a booked daytime window. LRN-C's four runs went on the U50: the kernel's own learner trained from the windows the card's own injector labels, made its set from the blank set, and the host committed it. Every record each run wrote, the outcome of every host operation on the learner, and the learner's registers at the end were then held to the reference model's run of the same case, by LRN-C's judge (`hw/lrnc/lrnc.py compare`, [lrn-c.md](../host/lrn-c.md)). **`== LRN-C CARD VERDICT: PASS`.**

**What it rests on: bit identity, and its authority is the model** (D0, section 2):
- every score record of the four runs is the model's, by its SHA-256;
- every learner operation's outcome is the model's, and so are the learner's 19 registers at the end of each run.

It is not evidence about sensitivity: no efficiency is measured here. Whether the learner's set finds faint signals is stage E1's question, answered in software ([E1-software.md](E1-software.md)).

**The learner in the fabric learned, on the card.** flow's update ran from the blank set, and its commit at 2,097,152 was taken. moved is flow with its update one trial later, and its records differ from flow's first at that very record, as the model predicts. That is the learner's own set, made in the fabric, reaching the scores at the commit (CL6).

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure here has a row in the register at the end.

## The result

| run | case | frames | learner operations | refused by name | records against the model's | registers at the end |
|---|---|---|---|---|---|---|
| flow | flow | 4,194,304 | 2 | 0 | IDENTICAL | 19 of 19 the model's |
| rich | rich | 7,340,032 | 13 | 7 | IDENTICAL | 19 of 19 the model's |
| moved | moved | 4,194,304 | 2 | 0 | IDENTICAL | 19 of 19 the model's |
| flow again | flow | 4,194,304 | 2 | 0 | IDENTICAL | 19 of 19 the model's |

(CL1 to CL3.) flow again's records are flow's, byte for byte, as its expectation is flow's.

- **Every operation's outcome is the model's.** Each host operation landed inside its window. The least margin the judge printed is 1,042,375 frames, rich's op 8. rich's three operations whose windows have no upper end, ops 1, 9 and 10, print no margin (CL4).
- **rich's provoked outcomes are the model's** (CL5). Seven operations were refused by name: UPDATE_UNFINISHED at ops 3, 4 and 5, SWAP_PENDING at ops 7 and 8, and SWAP_INDEX at ops 9 and 10. Op 1, a `clear()`, read the latched code QUANTISE_INPUT. Each is as [lrn-c.md](../host/lrn-c.md) planned it, to be provoked, and each is the model's.
- **The control, moved:** "SEEN: its own model run's, and different from flow's first at record 2097152, score, 2238591475 where flow's is 2239318260, as predicted". 2,097,152 is the commit's index (CL6).

**The host kept up** (CL7):
- 1,024 truth records before each start, and 135,170 fed while the runs went: 31,744 in each of flow, moved and flow again, and 39,938 in rich;
- the least slack 129,097 frames, in rich; the queue's peak 1 in every run;
- no run refused INJECT_OVERLAP or RUN_LENGTH.

## The image

The card ran the image of e67967d, the line merged into r5 as cc996aa ([krnl.md](../rtl/krnl.md), section 7; [poolram.md](../rtl/poolram.md)):
- KRNL-L's kernel with the learner;
- the lead's floorplan, which places the learner in SLR1 (9bf71d7);
- parcel POOLRAM's pool in UltraRAM (e67967d).

**Its clocks were lowered by v++** (CL8):
- DATA_CLK 93 MHz ("Achieved Freq: 93.9 MHz"), against 100 asked;
- hbm_aclk 382 MHz, against 450.
- At 100 MHz the kernel clock's WNS was -0.649 ns, its worst path a register-write check of the core's.

Logan's word of 2026-11-26 allowed a lowered clock ("Yes, use it"), and his word that evening chose the new image if it was done before the nightly ended ("unless by some chance the new one finishes prior to the nightly run finishing"). It ended at 01:18.

The image is 45,788,071 bytes, SHA-256 0af21036a760ba40e1c9f73135c8a6b6cd5e38f1f6c8a07b0f09f56826f5a31b (CL9). This is its first card day, so **the pool in UltraRAM is held on the card by the same records.**

## How it was run

- **Bookings:** B0439 (u50, sensitive) and B0440 (box, shared), 08:00 to 10:30, with cft-fp256's word; both released at 08:03:28 (CL10). A link of the lead's (5db05d9) was on the box, stopped by `kill -STOP` from 07:44, so it took no CPU.
- **The host tree:** LRN-C at 39c2061, unpacked on the box. Its shim was built against the box's XRT, and the cases' 20 files were checked against the desktop's list. The tree imported under Python 3.12.3 with the definition 85e63d4def6d... (CL11).
- **The script:** `hw/lrnc/box_lrnc.sh`, detached. It ran health before, the four runs in order (each one process of `hw/e0c/run_piece.py`), health after, and the run folder's SHA256SUMS.
- **The copy back:**
  - 418,402,229 bytes without the traces, every file of SHA256SUMS the same on the desktop; then the four traces with their own sums, 472,887,202 bytes in all;
  - the session's 471 MB were then removed from the box.
- **The judge,** on the desktop, in LRN-C's worktree at 39c2061: exit 0, 29 lines, the last its verdict.
- **The card's health:**

  | | Device Status | power | FPGA | HBM | the image loaded |
  |---|---|---|---|---|---|
  | before | HEALTHY | 22.02 W | 32 C | (not read) | 16658FE4..., the one left before |
  | after | HEALTHY | 14.29 W | 35 C | 30 C | 5048622F..., this one, with `undertone_krnl_1` listed |

  After the runs no process held the card's device files (CL12).

**The committed record,** under [learn-card/](learn-card/):
- the judge's printed output with LF line ends, and its JSON;
- the box's SHA256SUMS;
- each run's report.json and log, the bytes those sums name;
- the three cases' expectations and the run order;
- the box's log of the day.

`tests/test_lrn_c_card_record.py` holds four things:
1. each file's hash;
2. the tree's judge, which re-reads the committed reports and expectations and prints each run's lines of the committed output, word for word, with each run's records hash the model's. It skips by name, LRN-C-CARD-STALE, under another definition;
3. that the record and the printed output agree;
4. that skip's control.

## Limits

1. **One card, one image, one sample format.** s16x1 at a lowered clock, 93.9 MHz. Nothing here is shown of s24x3, or of 100 MHz with this image.
2. **The record is held by hashes, not records.** The 418 MB of card records and the model's 330 MB are not committed. The test holds each run's records hash against the model's, and the judge's block-by-block comparison is the day's (CL3).
3. **The control's first difference is held as printed.** It needs both models' records; the test holds its record against moved's commit and its form.
4. **The model's expectations are held by their hash,** as `lrnc.py expect` made them on 2026-11-26, not made again by the gate.
5. **Not a sensitivity result.** The learner's set is two class means' difference; how well it finds faint signals is E1's, in software.
6. **The image's lowered clocks are v++'s choice,** read from the image. That the pool's move and the floorplan together lowered them is BELIEVED (krnl.md, K37 on lead/krnl-l-nohook); the image without the floorplan is still being linked.
7. **Four runs, three cases.** What a case does not provoke is not shown here; lrn-c.md lists each refusal the cases meet, and those met only by a fault.

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| CL1 | The card day ran on the box from 08:00:28 to 08:01:35 on 2026-11-27, detached, ending with its script's "end" line; the runs from 08:00:29 to 08:01:33 | MEASURED | the box's log, `learn-card/day-e67967d.log`, its time lines | the log |
| CL2 | flow, moved and flow again ran 4,194,304 frames each and rich 7,340,032, each with every record, `run_piece exit 0` and `PASS host.run_case`; flow, moved and flow again made 2 learner operations each and rich 13, of which 7 were refused by name | READ | each run's log and report.json in `learn-card/runs/`, and the day's log | those files |
| CL3 | Each run's records.bin has the SHA-256 of its case's expectation (flow and flow again 2dda611f..., rich 635fdd90..., moved b0808f29...), and the judge printed each IDENTICAL, block by block, against the model's records | MEASURED | the box's SHA256SUMS (`learn-card/records-sha256.txt`, the same on the desktop after the copy back) against `learn-card/expect/*/expected.json`; the judge, `python hw/lrnc/lrnc.py compare` at 39c2061, its output `learn-card/compare-output.txt` | those files, and the records on the desktop |
| CL4 | Every operation's outcome is the model's and every bracket inside its window; the least printed margin is 1,042,375 frames (rich op 8); rich's ops 1, 9 and 10 print none | READ | `learn-card/compare-output.txt`; `tests/test_lrn_c_card_record.py` prints its operation lines again from the committed reports | the test |
| CL5 | rich's seven refused by name are ops 3, 4 and 5 (UPDATE_UNFINISHED), 7 and 8 (SWAP_PENDING), 9 and 10 (SWAP_INDEX); op 1's `clear()` read QUANTISE_INPUT; each the model's | READ | `learn-card/compare-output.txt` | the test |
| CL6 | moved's records are its own model run's and differ from flow's model run first at record 2,097,152, the commit's index, in the score, 2,238,591,475 where flow's is 2,239,318,260 | READ | the judge's control line, `learn-card/compare-output.txt`; the commit's index from `learn-card/expect/moved/expected.json` | the records |
| CL7 | Truth records: 1,024 before each start; 31,744 while flow, moved and flow again ran and 39,938 while rich ran, 135,170 in all; the least slack 129,097 frames (rich); the queue's peak 1 in each run | READ | each run's report.json, `run` | those files |
| CL8 | The image's DATA_CLK is 93 MHz, "Achieved Freq: 93.9 MHz" against "Requested Freq: 100 MHz"; v++ chose hbm_aclk 382; at 100 MHz the kernel clock's WNS was -0.649 ns | READ | `xclbinutil --info`, `undertone_hw.xclbin.info`, v++ 60-1230 and the routed timing summary, read on the box (the round's ledger, `lead.md`, 2026-11-27 01:26) | the image |
| CL9 | The image is 45,788,071 bytes, SHA-256 0af21036..., of commit e67967d | READ | its manifest on the box, and `sha256sum` in the day's log | the image |
| CL10 | B0439 and B0440 were booked for 08:00 to 10:30 and released at 08:03:28 | READ | `timesheet.py release`, the round's ledger 2026-11-27 08:04 | the TimeSheet's log |
| CL11 | The box's tree imported under Python 3.12.3 with the definition 85e63d4def6d9b0b; the shim built with exit 0; the cases' files were every one the desktop's | READ | `box_prep_l.sh`'s output, the round's ledger 2026-11-27 08:04 | a prep run again |
| CL12 | Before: HEALTHY, 22.02 W, FPGA 32, image 16658FE4...; after: HEALTHY, 14.29 W, FPGA 35, HBM 30, image 5048622F... with `undertone_krnl_1`; no process holding the card's device files after | READ | `xbutil examine -r dynamic-regions, electrical, thermal`, in the day's log | the log |

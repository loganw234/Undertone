# Stage E0 on the card

Round 4's card day, the lead's, on 2026-11-25, 14:32 to 14:40, in a booked daytime window. *Restated by the lead after the round's closing verifier:* it began at 14:32:03, a minute before its booking's start at 14:33; the card's holder had released it at 14:30:44, and nothing else was booked on it (the round's ledger, 14:33). It is track A of the plan ([R4-card-e0-and-drift.md](../plans/R4-card-e0-and-drift.md)): round 1's stage E0 stream, run on the U50 in pieces, every record compared with the reference model's, and the counts read from the card's own records judged as round 1's were. It ran on round 3's image (the kernel of [krnl.md](../rtl/krnl.md), built at 100 MHz from `31aaec1`, the image of [CARD-first-light.md](CARD-first-light.md)), driven by the host library through XRT from `amd-arc-box`. The host side is parcel E0C's, [e0c.md](../host/e0c.md); the box ran a snapshot of r4 at `5661550` (`host/`, `model/`, `spec/`, `hw/e0c/`).

**What rests on what.** Two results with two authorities (D0, section 2):
- **Bit identity rests on the model.** Every record of every piece is the model's own run of the same piece, word for word.
- **The sensitivity rests on `stats/`.** The counts are read from the card's records, and judged by `stats.tolerance` against D8's figure.

Because every record is the model's, the card's counts are round 1's counts in software, exactly. So the second result is round 1's sensitivity, now read from the card's records; it adds nothing to round 1 about the detector itself. **Nothing here is about learning:** the card ran the weights the host gave it.

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure here has a row in the register at the end.

## The result

**`== E0 CARD VERDICT: PASS`. All 20 pieces are IDENTICAL to the model's, every word. At each of the five amplitudes the card's counts equal round 1's part, field by field, and every amplitude is inside D8's tolerance. The flipped-bit control was seen, and the ten timed generations each equal the model's.**

| amplitude | found of 200,000 | efficiency | D8 | se | noise crossings | se |
|---|---|---|---|---|---|---|
| 1/2 | 24,442 | 0.12221 | 0.1224 | -0.30 | 1,929 | -1.60 |
| 3/4 | 55,857 | 0.27929 | 0.2805 | -1.22 | 1,974 | -0.58 |
| 1/1 | 99,743 | 0.49872 | 0.5002 | -1.33 | 2,008 | +0.18 |
| 5/4 | 144,075 | 0.72037 | 0.7198 | +0.53 | 2,041 | +0.92 |
| 3/2 | 175,622 | 0.87811 | 0.8778 | +0.46 | 1,987 | -0.29 |

Each count is INSIDE its tolerance. At each amplitude:
- the flags are 0;
- every score read is the statistics package's own integer read of the same samples;
- the real-coefficient filter finds the same trials, with card only 0 and real only 0;
- the part is EQUAL to round 1's part.

The record is [e0-card/card-e0.json](e0-card/card-e0.json), and what the judge printed is [e0-card/compare-output.txt](e0-card/compare-output.txt).

**The flip control**, on amplitude 1/1's first piece with round 3's flipped blob: the card's records are IDENTICAL to the flipped blob's own model run, and DIFFERENT from e0's. The first difference is at record 35, score, 198,242,912 against 189,330,016, and 98 blocks of 98 differ. `== E0C FLIP CONTROL: SEEN`.

**The injector was never short.** Each piece wrote 1,024 truth records before its start and 48,976 while it ran, never fewer than 130,133 frames ahead of the core. The queue never held more than one record.

## The timed runs: generations an hour

Ten runs in a row, one a generation. Each is the device opened, a stored set of weights loaded, 1,280,128 frames run with 10,000 injections, its records read back and scored by the host, and the device closed. Each generation's records and counts equal the model's run of its set (`== E0C TIMED VERDICT: PASS`; [e0-card/timed-judge-output.txt](e0-card/timed-judge-output.txt)).

**A generation took 2,828 ms on average, so 1,273 generations an hour with this host code**, the open included. With open and close taken out it would be 1,386 an hour, which is computed and not measured. Where the time goes, as means over the ten:

| part | ms |
|---|---|
| records: read back 1,280,128 records and parse them in Python (the fetch, 53 ms, inside) | 2,232 |
| finish: the card's own run, 1,280,128 frames | 256 |
| open: the device, and round 3's image through XRT | 208 |
| start: allocate, fill and start | 94 |
| close | 23 |
| score: the two reads of 10,000 trials | 13 |

**The host's Python parse is 79% of a generation, and the card's run 9%.** A host that parsed in compiled code, kept the device open and reused its buffer would be bounded nearer the card's 256 ms, about 14,000 an hour. That is an ESTIMATE from these parts, not a run.

## How it was run

- **The expectations first**, on the desktop, from 14:10 to 14:18, by `e0c.py cases` and `expect` on `5661550`. They were fixed and hashed in the round's ledger before the card ran. They are also the premise at full scale: in pieces, each amplitude's model run is EQUAL to round 1's part.
- **On the box**, detached, `hw/e0c/box_e0.sh` from 14:32:03 to 14:39:45:
  - health before;
  - the 20 pieces, one process each, from 14:32:04 to 14:38:39, about 20 s a piece whole;
  - the flip;
  - the ten timed runs, from 14:38:59 to 14:39:38;
  - health after.
- **Back on the desktop**, 2.82 GB of records were copied back, each file's SHA-256 equal on both machines. Then `e0c.py compare` and `timed-judge`, from 14:43:44 to 14:43:58, on r4 at `986cf76`, whose code is `5661550`'s.
- **Health:**
  - before: HEALTHY, 15.98 W, FPGA 36 C, cft-fp256's image loaded;
  - after: HEALTHY, 15.06 W, FPGA 36 C, round 3's image (UUID F6B95DCF-E412-CEF2-7DE7-827DEE594773) and its compute unit at 0x1400000;
  - nothing held the card's device files after.

`tests/test_e0c_card_record.py` holds the committed record:
- each file's SHA-256;
- the tree's judge, given only the record and round 1's frozen parts, reprints the committed output up to E0's verdict, byte for byte;
- the timed judge reprints its output.
It skips by name, `E0C-CARD-STALE`, once the definition moves past round 3's, as stage E1's record test does (CLAUDE.md, trap 18). *Restated by the lead after the round's closing verifier:* the definition moved past round 3's at round 4's merge of `e1`, `60f4391`, fourteen minutes after the record was committed (14:52:48 and 15:06:53). **From that commit on, the two judge tests skip and only the five files' hashes are held.** The judges' reprint was held on round 3's definition, at `0cf211a`'s gate.

## Limits

1. **One card, one clock, one profile, one sample format.** The U50, 100 MHz, `s16x1`, the matched filter for `e0` alone. The fabric's second pulse, the definition's maxima and the second sample format are not on the card.
2. **Not new evidence about sensitivity.** The counts equal round 1's in software because the records equal the model's. The card shows that it reproduces round 1's sensitivity word for word, not that the detector is more sensitive than round 1 said.
3. **The expected records are the model's own,** from the same configuration and seeds. A fault shared by the model and the RTL would pass here, as in simulation.
4. **The stream is in pieces.** Each later piece's first 62 records differ from the continuous stream's, and none of them is read (e0c.md, section 3). The card returns only scores, so the stream's hash in each part is the desktop's (e0c.md, limit 6).
5. **The timed rate is this host code's.** It is one run a generation, opening the device each time, parsing in Python. The rate without open and close, and the bound near the card's own time, are COMPUTED and ESTIMATE, not run.
6. **The collector was off in every piece.** Whether a collection would have outlasted the injector's slack is not measured (e0c.md, limit 5). The least slack seen was 130,133 frames.
7. **`xbutil validate` was not run;** it dies on this card (CLAUDE.md, trap 21). Health is the three `examine` reports, before and after.
8. **What stayed on the box:** each piece's trace and the timed generations' records. The flip's judgement needs its records, so the committed test holds its line as text only.
9. **The record is round 3's definition's.** From round 4's change for the pulse `e1` the tree refuses this image, and the record's test skips by name.

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| CE1 | The card day ran on the box from 14:32:03 to 14:39:45 on 2026-11-25, detached, ending with its script's "end" line | MEASURED | the box's log `e0c-day.log`, copied back; the round's ledger, entries 14:33 and 14:43 | that log |
| CE2 | The box ran a snapshot of r4 at `5661550`: the image fce0e239..., the shim 8b0c6911... (the same bytes as round 3's), run_piece.py 5b029e90..., timed.py 00b6bdd7..., box_e0.sh 09a00f6a..., under the definition 0a9242e5... | MEASURED | `sha256sum` in the log's first lines; `git archive` of `5661550`; the ledger, 14:20 | those hashes |
| CE3 | The model's expectations were made on the desktop from 14:10:13 to 14:18:31 and hashed before the card ran; each amplitude's model run in pieces is EQUAL to round 1's part | MEASURED | `e0c.py expect`, the ledger's 14:19 entry and its expected.sha256 | a rerun of `expect` |
| CE4 | All 20 pieces are IDENTICAL to the model's, every record, by their block hashes | MEASURED | `e0c.py compare`, [e0-card/compare-output.txt](e0-card/compare-output.txt) | the records |
| CE5 | The card's counts are those of the table above, each equal to round 1's part, flags 0, every score read the statistics package's, card only 0 and real only 0 | MEASURED | compare's reads from the card's records; [e0-card/card-e0.json](e0-card/card-e0.json) | the records |
| CE6 | Every amplitude's efficiency and noise count is inside D8's tolerance, at the se figures of the table | COMPUTED | `stats.tolerance` in compare's judge, from CE5's counts | the judge on CE5 |
| CE7 | The flip run is IDENTICAL to the flipped blob's model run and differs from e0's first at record 35, score, 198,242,912 against 189,330,016, in all 98 blocks | MEASURED | `compare_flip`, the last line of compare-output.txt | the flip's records, kept on the desktop |
| CE8 | Each piece wrote 1,024 truth records before its start and 48,976 while it ran; the least slack was 130,133 frames; the queue's peak was 1 | MEASURED | each piece's `report.json`, in compare's identity lines | those reports |
| CE9 | A piece took about 19 to 22 s whole on the box | MEASURED | the log's start time of each piece | that log |
| CE10 | The ten timed generations each equal the model's, records and counts; the mean generation is 2,828.340 ms | MEASURED | `e0c.py timed-judge`, [e0-card/timed-judge-output.txt](e0-card/timed-judge-output.txt); [e0-card/timed.json](e0-card/timed.json) | timed.json |
| CE11 | 1,273 generations an hour with this host code, the open included; 1,386 with open and close taken out | COMPUTED | 3,600 s over CE10's mean, and over the mean less open and close | CE10 |
| CE12 | Of a generation, the records' read and parse is 2,232 ms (79%), the card's run 256 ms (9%), open 208 ms, start 94 ms, close 23 ms, score 13 ms | MEASURED | the means of timed.json's `parts_ns` | timed.json |
| CE13 | A host that parsed in compiled code and kept the device open would make about 14,000 generations an hour, bounded by the card's 256 ms | ESTIMATE | CE12's card share, 3,600 s / 0.256 s | a run of such a host |
| CE14 | The card read HEALTHY before and after; after, round 3's image F6B95DCF-E412-CEF2-7DE7-827DEE594773 and its compute unit; 15.98 W and 15.06 W; FPGA 36 C | MEASURED | `xbutil examine -r dynamic-regions`, `electrical`, `thermal`, in the log | those reports |
| CE15 | The 2,822,461,773 bytes copied back equal the box's, all 43 files of its SHA256SUMS | MEASURED | `sha256sum -c SHA256SUMS` on the desktop; the ledger, 14:43 | those files |
| CE16 | The tree's judge, given the committed record and round 1's frozen parts, reprints the committed output up to E0's verdict byte for byte; the timed judge reprints its output. *Restated by the lead after the round's closing verifier:* so measured on round 3's definition, at `0cf211a`'s gate (run 20261125-144931-986cf76). From `60f4391` the two tests skip by name, E0C-CARD-STALE, and the reprint is not held | MEASURED | `tests/test_e0c_card_record.py` | that test, on round 3's definition |

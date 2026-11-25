# Stage E0 on the card: the host's side

Parcel E0C, round 4, 2026-11-25: track A of [the round's plan](../plans/R4-card-e0-and-drift.md), every part but the card day, which is the lead's. Its design was approved by the lead at 12:27 that day, with eight answers (the round's ledger, not committed). The code is `hw/e0c/`; its tests in the gate's first size are `tests/test_e0c_*.py`; its records are `vectors/e0c/`. Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure here is in the register at the end.

**What it is for.** Round 1's own stage E0 stream (five amplitudes, 200,000 injections each, `tests/test_seam_e0.py --full`) run on the card in pieces, so that the card's counts must equal round 1's exactly; and ten timed runs that say how many trial generations an hour this host code allows.

**What a pass rests on, line by line.** Three authorities, never mixed (D0, section 2):
- *Bit identity*, the model's: every record of every piece the card wrote is the model's own record of that piece.
- *Reproduction*, round 1's record: each amplitude's counts equal round 1's committed part, field by field.
- *Sensitivity*, D8's and `stats/`'s: each amplitude's efficiency inside the tolerance. **It adds no new fact about sensitivity**: if the card equals the model on every word, its counts are the model's on that stream (the plan, track A). Its result is that the card reproduces E0 at scale, or where it does not.

**What has been run.** Everything here in the first size, on the desktop, on the model and on a stand-in for the card (`hw/e0c/kernel_model.py`), at short forms; and the premise at full scale for one amplitude. **Nothing of E0C has run on the box or on the card**, and the expect run's full form is the lead's, after the merge.

## 1. Where things are

| what | where |
|---|---|
| the cut, the seeds, the schedules, the reads, the block hashes, the flip | `hw/e0c/pieces.py` (desktop) |
| the cases, the model's expectations, the comparison, the judge, the premise | `hw/e0c/e0c.py` (desktop) |
| E0C's own refusal names | `hw/e0c/errors.py` |
| one piece on the box: host.run_case, unchanged, the cyclic collector off | `hw/e0c/run_piece.py` (box) |
| the ten timed runs | `hw/e0c/timed.py` (box) |
| the card day's script for the box | `hw/e0c/box_e0.sh` (box) |
| the first size's stand-in for the card | `hw/e0c/kernel_model.py` (desktop) |
| the desktop's measurements behind this page | `hw/e0c/measure.py` (desktop) |
| round 1's five parts, and the premise's part | `vectors/e0c/round1/`, `vectors/e0c/premise/`, their note `vectors/e0c/NOTE.json` |
| the tests | `tests/test_e0c_pieces.py`, `test_e0c_short.py`, `test_e0c_compare.py`, `test_e0c_timed.py`, `test_e0c_premise.py` |

The tests claim the existing gate rows `replay` and `statistics`; E0C adds none. D0's gate `bit identity` is held by the stage `rtl-benches` (its row in `tests/gates.toml` is of kind "stage"), so no pytest test may claim it, and E0C's tests of the card's side claim no gate: they hold E0C's scripts over a stand-in that models no block, which is not that gate's claim. Nothing in `spec/`, `host/` or `hw/card/` changed.

## 2. The pieces

Round 1's stream for amplitude k: trial i has its truth index at 64 + 128 i, i from 0 to 199,999, and the stream is 25,600,128 frames, 200,001 spans of 128; the last span holds no trial. Seed 2026112300 + k, sigma 1477/1, profile `s16x1`. One buffer in one segment holds 8,388,484 frames (the plan's L7), so at most 65,535 whole spans a piece: at least four pieces. E0C takes four, the same for every amplitude (`python hw/e0c/e0c.py cases <folder>`, its `piece.json` files):

| piece | first frame | frames | trials | buffer, guard + 32 a slot | records.bin, 21 a record |
|---|---|---|---|---|---|
| 0 | 0 | 6,400,000 | 0 to 49,999 | 204,803,968 | 134,400,000 |
| 1 | 6,400,000 | 6,400,000 | 50,000 to 99,999 | 204,803,968 | 134,400,000 |
| 2 | 12,800,000 | 6,400,000 | 100,000 to 149,999 | 204,803,968 | 134,400,000 |
| 3 | 19,200,000 | 6,400,128 | 150,000 to 199,999 | 204,808,064 | 134,402,688 |

Each piece's seed is (s + GAMMA x first) mod 2^64, GAMMA the model's `model.source.GAMMA`, one word a frame under `s16x1` (the plan's L17; under `s24x3` it is GAMMA x 3 x first, and the tests run both). For amplitude 0 the four seeds are 2026112300, 9739868458805808428, 1032992841875952940 and 10772861298655649068; for amplitude k each is those plus k. Each piece's schedule is its trials' truth records, each index less the piece's first frame: trial i is at local index 64 + 128 (i - the piece's first trial).

**Why every read of every trial is inside one piece, with its whole window.** Trial i's two reads are the score at 127 + 128 i (truth + 63), whose window is frames 128 i + 64 to 128 i + 127, and the signal-free score at 63 + 128 i (truth - 1), window 128 i to 128 i + 63 (convention CV2: a score's window is its index and the 63 before). Both are in span i, and a piece is whole spans. In its piece each read is at local index 63 + 128 t or later, so the core's delay line holds 64 of the piece's own samples by then. Trial i's pulse touches frames 128 i + 64 to 128 i + 127 only (CV1), and trial i - 1's ends at 128 i - 1. `pieces.cut` refuses a cut for which any of this fails (PIECE_CUT), and a piece past one buffer (PIECE_LENGTH).

**The late read leaves.** The control's read one sample late, at truth + 64, has a window that ends on 128 (i + 1), the next span's first frame. For the last trial of pieces 0 to 2 that is the next piece's frame 0: three trials an amplitude. The last piece's last trial has the empty span after it.

## 3. What the core does at a piece's start

Each piece is a run of its own: `krn_reset`, `load` at epoch 0, `start`, as `host.run_case` does them. In the model that is a fresh `model.detector.Core(blob, 0)`:

- **The delay line** starts at 64 zeros. Record j of a piece, j below 63, sums the coefficients c[0] to c[62 - j] against zeros where the continuous stream had samples. So records 0 to 61 may differ from the continuous stream's. Record 62 meets only c[0], and e0's matched filter has c[0] = 0, so it cannot; record 0 meets only c[63], also 0, so its score is exactly 0. From record 63 on, the window is all the piece's own.
- **The pool** is 1: its window holds only the newest rectified value. Nothing from before the start is carried.
- **Settling** is set only by a swap (`model.weights.Store`), and no piece swaps; overflow is not raised at these widths (round 1's five parts each give `flags` 0, the OR over every record).
- **Index and epoch.** A piece's records are indexed from 0, at epoch 0. So piece record j is the continuous record first + j with its index less `first`, for every j from 62 on.

The test `test_gate_replay__e0c_pieces_read_every_trial_as_the_continuous_stream_does` holds each of these on the model, under both profiles: a short stream in three pieces, each piece run alone, against the continuous run. On the card, round 3's runs each started this way and matched the model from record 0 (the plan's L1). **That the fabric takes a seed above 2^32, and so an offset seed, is BELIEVED until the card day's comparison of every record shows it.**

## 4. The expected records, and the comparison

**The model's records are not kept; their SHA-256 is.** The 20 pieces' records are 2,688,013,440 bytes in their canonical form. `e0c.py expect` keeps, for each piece, the SHA-256 of all its canonical records (`model.records.pack`'s bytes, the bytes `host.run_case` writes to `records.bin`) and one SHA-256 for each block of 65,536 records, 98 blocks a piece. The comparison (`pieces.compare_blocks`) hashes the card's file the same way. Equal is every word equal, but for a SHA-256 collision (limit 2). On a difference it finds the first differing block, makes the model's records of that piece again up to that block's end, and names the first record that differs, its field, and both values; and it counts the differing blocks. A file of too few records, too many, or with part of a record over, is named the same way.

Two things follow from keeping hashes. The expectation is small, about 25 KB a piece, so it is made and fixed before the card runs and goes to the box with the cases. And the box can check each piece's whole hash with `sha256sum` inside the card's window, which `box_e0.sh` does.

**Beside the hashes**, for each piece: the model's counts of the three reads (found, signal-free crossings, late), the OR of every record's flags, the SHA-256 of the piece's injected samples, and the statistics package's own reads of the same samples with the same integer coefficients (`stats.matched.matched_scores`, as a SHA-256 of the at-index and signal-free scores in trial order). Also the real-coefficient filter's hit for every trial, as a bitmap: the pulse itself as the coefficients, never rounded, against `stats.recovery.threshold_known_sigma` of those, as round 1's `full_part` measured the cost of quantisation.

**`expect --amplitude k` runs amplitude k's four pieces in order in one process** and chains their samples into one SHA-256. At the stated run it holds that amplitude against round 1's part k, field by field: the stream's SHA-256, found, noise crossings, flags, scores identical to the statistics, real found, model only, real only, n, seed and length. So the expect run is also the premise at full scale for all five amplitudes, in pieces (section 7). It is 8 to 9 minutes a process on the desktop, 40 to 45 core-minutes for the five, with about 2 more for the flip's piece and about 4 for the ten timed sets (ESTIMATE, from 19 to 21 us a frame measured at the gate's short form's size). It is the lead's, after the merge.

## 5. What runs where, and what crosses

**The box** runs a snapshot of the merge: `host/`, `model/`, `spec/` and `hw/e0c/`, under Python 3.12.3. Its scripts, `run_piece.py`, `timed.py` and `box_e0.sh`, import nothing from `tests/`, and nothing that needs numpy. `test_e0c_nothing_the_box_runs_imports_from_tests_or_needs_more_than_the_standard_library` holds that by following their imports through the tree.

**One process a piece, as round 3's card day did it.** `box_e0.sh` runs each piece as `python3 hw/e0c/run_piece.py <run_case's arguments>`. That file disables Python's cyclic garbage collector and calls `host.run_case.main` unchanged. So each piece opens the device afresh and its one buffer is freed at its close; the library is not changed. `--polls 2000000`, as round 3 used, is about 46 times the 43,470 polling rounds a piece needs at round 3's rate (COMPUTED). `--ahead` is the build's 1,024, and each piece has `timeout 900`.

**Why the collector is off.** `host.run_case` traces every operation of a run in a list, and a full collection walks every object the collector tracks. The injector's store holds 1,024 truth records, which is 26.2 ms of the stream at 200 ns a frame. A piece's trace ends at about 193,000 entries. One full collection inside a piece that outlasts the slack would let the stream pass truth records the host had not yet written, and the run would be refused, INJECT_OVERLAP, by name: a lost run, not a wrong answer. That a collection would fall inside a piece and outlast the slack is an ESTIMATE, and nothing has been measured on the box (limit 5). The lead's ruling: the wrapper, and `host/run_case.py` as it is. The finding is the host library's, and the lead states it at the round's close.

**Desktop to box**, 80,182,554 bytes of cases, measured: each piece's `piece.json` and `schedule.json` (3,741,320 bytes for 50,000 truth records), the shared `case.blob` and `table.json`, the flip's case, and the timed runs' ten blobs, schedule and case file. The lead's `expected.json` files, about 25 KB a piece, go with them.
**Box to desktop**, about 2.8 GB: each piece's `records.bin` (2,688,013,440 bytes for the 20, as the plan's T5 has it, and 134,400,000 more for the flip), `report.json`, its log, and the SHA-256s. `trace.json`, ESTIMATE about 14 MB a piece, stays on the box unless asked for. The timed runs send `timed.json`, which holds each generation's records' SHA-256, and keep the records on the box.

A piece is ESTIMATE 20 to 35 s whole on the box: 1.28 s of the card, parsing 6.4 million records at about 2 us each, writing them, and the open. So the 21 runs, 20 pieces and the flip, take ESTIMATE 7 to 12 minutes. `run_case` holds a piece's records as a list of dicts, 252 bytes a record measured on the desktop, so about 1.6 GB, which the box's 46 GB holds (READ).

## 6. The reading, the count, round 1 and the judge, on the desktop

`python hw/e0c/e0c.py compare <cases> <runs>`, from the card's `records.bin` of each piece:

1. **Bit identity, piece by piece**, by the block hashes: IDENTICAL, or DIFFERENT naming the first record and field. Beside it, from the piece's `report.json`: the truth records written before the start and while it ran, the least slack and the queue's peak.
2. **The reads, from the card's bytes, not the model's.** For trial t of the piece: the record at local 128 t + 127 and the one at 128 t + 63. Each must carry the index it is read at, or the read is refused, RECORD_ORDER, the definition's name. A file whose length is not its frames' records is refused, RUN_LENGTH. The late read is made only where it is inside the piece. Counts are against D8's threshold, 1,595,666,164, and a crossing is a score strictly greater (CV3). Also the OR of every record's flags byte. And the card's at-index and signal-free scores are hashed as `expect` hashed the statistics package's: equal is the card against the foreign implementation, directly.
3. **Each amplitude's pieces must be the stated cut**, each once, each `piece.json` the cut's piece; else PIECE_SET. Then the card's part, in round 1's form. Its `found`, `noise_crossings`, `flags`, `real_found`, `model_only` and `real_only` are the card's: the card's hits against the real filter's bitmap, so "model_only" here means found by the card's integer scores and not by the real filter. Its `stream_sha256` is the desktop's, from `expect` (limit 6). Its facts (n, seed, threshold, d, length) are `tests/test_seam_e0.py`'s, imported, not retyped.
4. **Against round 1**: every field of the card's part against round 1's part k in `vectors/e0c/round1/`, but the definition's hash. EQUAL, or DIFFERS naming the fields.
5. **The judge**: round 1's own `not_as_stated` on the five parts, then `stats.tolerance.check_efficiency(found, n, 0.01, d)` and `check_count(noise_crossings, n, 0.01)` for each amplitude, with real found, card only and real only beside them: the cost of quantisation on the same stream.

The E0 line is `== E0 CARD VERDICT: PASS, ...` only when every piece is IDENTICAL, every part is as stated and equals round 1's, nothing is flagged, every score read is the statistics package's, and every amplitude is inside the tolerance. Otherwise it is `FAIL`, after the lines that say why. Each of those conditions, broken alone, is a FAIL in a test (section 10).

**Then the flip control**, round 3's, on amplitude 2's piece 0: `== E0C FLIP CONTROL: SEEN` only when the flip's run is IDENTICAL to the flipped blob's own model run and DIFFERENT from e0's; otherwise `NOT AS IT MUST BE`. **A missing flip run fails the card day**: with no folder `flip-a2p0`, the line is `== E0C FLIP CONTROL: NOT RUN: ...` and `compare` exits 1 whatever E0's line says. The exit code is 0 only when E0's verdict and the flip's are both passes (`e0c.card_day`). `compare` writes `card-e0.json` with the parts, the pieces' reports and the definition's hash.

**The card day's committed record**, when the lead commits one, names that hash. `e0c.stale(record)` returns `E0C-CARD-STALE` once `spec/` moves past it, so its test can skip by that name, as `tests/test_e1_full_run.py` does (CLAUDE.md, trap 18; the lead's ruling).

## 7. The premise

The exact equality with round 1 needs today's model and definition to make round 1's stream. **At full scale for one amplitude**, round 1's own script was run again, unchanged, under round 4's tree at `59dc834`:

    timeout 580 python tests/test_seam_e0.py --full --amplitude 2 --out part2.json

It ran from 12:27:59 to 12:32:45 on 2026-11-25 and exited 0. Its part has round 1's 23 fields, and every one equals round 1's part 2 but `spec_sha256`. Equal are found 99,743, noise crossings 2,008, threshold 1,595,666,164, d, real found 99,743, model only 0, real only 0, flags 0, and the stream's SHA-256 `d4ff45db...9d91`. Amplitude 2 was chosen because round 1's closing verifier had reproduced it at round 1's code, so it has now been made three times: by round 1's lead, by that verifier, and here under round 4's tree. The part is kept as `vectors/e0c/premise/part2.json`. `test_e0c_premise_round_1s_part_2_made_again_under_todays_tree` holds it equal to round 1's but for that hash, and skips by name, `E0C-PREMISE-STALE`, once `spec/` moves.

**In pieces, for all five amplitudes**, the expect run's comparison with round 1 does the same (section 4), when the lead makes it. At the gate's short form the four pieces' counts are the continuous short form's, 1,999 found and 30 crossings (`test_gate_statistics__e0c_the_short_form_in_pieces_reads_round_1s_scores_and_is_inside`).

Round 1's five parts are frozen byte for byte from `<repos>/AOTPU/Data/runs/2026-11-21-r1-model/reports/e0/`, their SHA-256s in `vectors/e0c/NOTE.json`. They are a record, READ, not a known answer: what judges the card is the stated cut and the model's own expect run.

## 8. The ten timed runs

`hw/e0c/timed.py`, on the box, one process, after E0's pieces: ten generations one after another (the plan's track A, its timed measurement; row T7).

- **The stream.** E0's amplitude-1/1 stream, seed 2026112302, frames 0 to 1,280,127, its first 10,000 trials. The same injection set for every generation.
- **The ten sets**, made on the desktop beforehand; nothing is learned. Set g quantises (g + 1) e0[j] + (9 - g) e0[63 - j] by the definition's rule. Set 9 is E0's own matched filter, and set 0 is mostly e0 reversed. Each has its own D8 threshold and d, computed by `stats/` and written in `timed.json`: d runs from -2.105 for set 0 to 2.327 for set 9. Every set's records differ from every other's, so a set loaded in another's place shows in its records, which `timed-judge` compares. **Its count need not show it:** sets 0 to 3 have a negative d, each finds almost nothing, and their counts are all near zero; sets 8 and 9 are nearly one filter (d 2.324 and 2.327) and may count alike. At the first size's 150 trials, sets 0 to 3 each found 0, and sets 8 and 9 each 78. (E0C's design said the counts were distinct; that was written before d was computed, and is wrong.)
- **Each generation opens the device afresh.** The library frees a run's buffer only when the backend closes, and E0C adds no way to free one. The open, which loads the image through XRT, is timed as a part.
- **The parts**, each `time.perf_counter_ns` around one call: ready (the set read from disk), open, identity, reset, load, start, finish, records, score (the two reads of 10,000 trials against the threshold), close. Their **sum** is the generation's cost. From the run's trace: allocate and fill, inside start; the run, from the krn_start write to the read that says done; fetch, inside records, so the parse is records less fetch; and the count of status reads. Timed apart and outside the sum: keeping the records (their canonical bytes and SHA-256, for the comparison), and once, the process's start and imports.
- **An end that is not done** (a refusal by name, a deadline, a failure) is recorded, the kernel reset and its answer read, the backend closed, and no further generation runs.
- **On the desktop**, `e0c.py timed-judge <cases> <timed out>` holds each generation's SHA-256 and counts against the model's run of that set (`expect --timed`). It prints the parts, and the rate: generations an hour, 3,600 s over the mean sum, COMPUTED from the measured parts, for one run a generation and this host code, the open included. Beside it is the rate with open and close taken out, COMPUTED and not measured: what a library that freed a run's buffer could reach.
- **What it will show** is the card day's. ESTIMATE: parsing 1,280,128 records at about 2 us each is about 2.7 s, so a generation is about 3 to 4 s and the rate 900 to 1,200 an hour; the card's own 0.256 s is a small part (round 3's runs of 2^20 frames took 4 to 5 s whole by its log).

## 9. The card day, as the lead would run it

1. After the merge, on the desktop: `python hw/e0c/e0c.py cases <cases>` (about 8 s, MEASURED), then the expect run: `python hw/e0c/e0c.py expect <cases> --amplitude k` for k from 0 to 4, one process each, then `--flip` and `--timed`. Each `a<k>.json` says EQUAL or DIFFERS against round 1. The expectations' SHA-256s go in the ledger before the card runs.
2. Copy `<cases>` to the box, and the snapshot of `host/`, `model/`, `spec/` and `hw/e0c/` with the shim built there.
3. On the box, detached: `setsid nohup bash hw/e0c/box_e0.sh <host tree> <build folder> <cases> > <log> 2>&1 < /dev/null &`. It reads health before and after. It runs the 20 pieces, printing IDENTICAL or DIFFERENT for each by its hash. It runs the flip on amplitude 2's piece 0, which must differ from e0's hash, then the ten timed runs. It writes a SHA256SUMS of its outputs.
4. Copy back each piece's `records.bin` and `report.json`, the flip's, `timed/timed.json`, the log and SHA256SUMS. Check each file's SHA-256 on both machines.
5. On the desktop: `python hw/e0c/e0c.py compare <cases> <run folder>`, which judges E0 and the flip (`== E0 CARD VERDICT`, `== E0C FLIP CONTROL`) and exits 0 only when both pass, a missing flip run among the failures; and `python hw/e0c/e0c.py timed-judge <cases> <run folder>/timed` (`== E0C TIMED VERDICT`).

## 10. The tests and the controls

`python -m pytest -q -p no:cacheprovider tests/test_e0c_*.py`: 40 tests (37 functions, three of them run under both profiles). Each control below was run, and its output is as printed.

| what | test | it shows |
|---|---|---|
| the stated cut | `test_e0c_the_stated_cut_is_the_designs` | section 2's table and seeds; each seed by the generator's own identity, words 0 and 1 of a piece's seed being words `first` and `first + 1` of the stream's |
| a piece's start, every read (gate `replay`) | `test_gate_replay__e0c_pieces_read_every_trial_as_the_continuous_stream_does` | under both profiles: from record 62 on, every record the continuous one; some of records 0 to 61 differ; record 0 exactly 0; every read equal; exactly two late reads not made in three pieces |
| **named:** a piece seeded without its offset | `test_control_replay__e0c_a_piece_seeded_without_its_offset_differs_at_the_first_record_it_reads` | the first read that differs is the piece's first, its first trial's signal-free score at local 63, under both profiles |
| a schedule shifted a span short | `test_control_replay__e0c_a_schedule_shifted_a_span_short_differs_at_its_first_at_index_read` | the first read that differs is the first trial's at-index read |
| **named:** a cut off the grid | `test_control_replay__e0c_a_cut_off_the_grid_is_refused_by_name` | first frames 128 m + 1 and 128 m - 1 at two m, and 64, refused PIECE_CUT; so are a first piece not at 0, an empty piece, an overlap, a stream not of whole spans, and a read's window leaving its span. 65,535 spans are taken and 65,536 refused, PIECE_LENGTH |
| a records file not its piece's | `test_e0c_a_records_file_that_is_not_its_pieces_is_refused_by_name` | one record short, RUN_LENGTH; shifted by one record, RECORD_ORDER |
| the reading offsets | `test_e0c_the_reading_offsets_are_round_1s_and_cv5s` | `e0c.OFFSETS`, which expect and compare share, against round 1's own reading in `test_seam_e0.measure` (by place in a span) and against CV5 on the model: a lone e0 in a zero stream peaks at truth + 63 alone, and the signal-free read is 0 |
| the short form in pieces (gate `statistics`) | `test_gate_statistics__e0c_the_short_form_in_pieces_reads_round_1s_scores_and_is_inside` | "found 1999 of 4000, -0.06 se, INSIDE; noise 30": every read, made with the shipped `OFFSETS`, is `measure`'s |
| **named:** coefficients reversed | `test_control_statistics__e0c_coefficients_the_wrong_way_round_in_pieces_fall_outside` | "found 0 of 4000, -63.3 se, OUTSIDE" |
| **named:** read one sample late | `test_control_statistics__e0c_a_score_read_one_sample_late_in_pieces_falls_outside` | "found 1696 of 3997, -9.6 se, OUTSIDE; 3 late reads fall past their piece's end and are not made, the last trial of pieces 0 to 2"; the 3,997 made are the continuous stream's late reads of those trials |
| the box's path end to end (no gate row) | `test_e0c_bit_identity_the_cards_records_through_run_case_are_the_models` | three pieces through `run_piece` and `host.run_case` over the stand-in: each IDENTICAL; the card's counts the model's; at 24 trials the statistics refuse to judge, TOLERANCE_UNDEFINED, and that is the only failure |
| **named:** one word changed | `test_e0c_control_a_card_record_changed_in_one_word_is_reported_at_that_record` | in each of index, epoch, flags and score of record 300: reported at record 300, that field, both values; a flag the card raised read into its part; the first of two changes named; one record missing, one extra, one byte over, each named |
| the cost of quantisation | `test_e0c_the_cost_of_quantisation_is_counted_from_the_cards_hits_against_the_real_filters` | one trial's real hit flipped in the expectation, each way: real found, card only and real only move by exactly one, in the right fields |
| a crossing | `test_e0c_a_crossing_is_strictly_above_the_threshold` | a score equal to the threshold does not cross (CV3) |
| the collector off | `test_e0c_run_piece_turns_the_collector_off_before_run_case` | `run_piece.py`'s main block is `gc.disable()` and then `run_case`; `timed.json` records the collector's state as read after each generation |
| the flip | `test_e0c_the_flip_control_is_seen_and_a_card_that_ignored_the_flip_is_not` | seen; a card that ran e0's blob for it is NOT AS IT MUST BE |
| the flip's two conditions, each alone | `test_e0c_control_the_flip_is_seen_only_when_the_run_is_the_flips_and_the_flip_reaches_a_record` | a run of a third blob, DIFFERENT from both expectations, is NOT AS IT MUST BE; with the flip's expectation made e0's, a run IDENTICAL to both is NOT AS IT MUST BE |
| a card day without its flip | `test_e0c_control_a_card_day_without_its_flip_run_fails` | with E0's verdict a pass, no flip run folder exits 1, "== E0C FLIP CONTROL: NOT RUN"; with it, 0 |
| the judge's conditions, each alone | `test_e0c_control_the_judge_fails_on_each_of_its_conditions_alone` | with round 1's record not given and the counts inside: a flag, a score read not the statistics package's, one piece DIFFERENT among twenty, and a part not as stated each FAIL |
| compare holds the set | `test_e0c_control_compare_refuses_pieces_that_are_not_the_stated_cut` | `compare` itself refuses a piece missing, or one with another seed, PIECE_SET |
| the flip's rule | `test_e0c_the_flip_is_round_3s` | tap 28, -131071 to -126975, the only tap changed |
| the set of pieces | `test_e0c_pieces_that_are_not_the_stated_cut_are_refused_by_name` | a piece missing, one with another seed, one extra: each PIECE_SET |
| the judge at the stated scale | `test_e0c_the_judge_at_the_stated_scale_passes_round_1s_counts` and its control `test_control_statistics__e0c_the_judge_fails_a_count_that_is_not_round_1s` | parts with round 1's counts PASS; a count changed (found, noise crossings), the stream's hash, or the seed each FAIL, naming the field; with no round 1 record to compare, a found count 3,000 low is OUTSIDE, and noise crossings 1,500 high are OUTSIDE |
| the box imports | `test_e0c_nothing_the_box_runs_imports_from_tests_or_needs_more_than_the_standard_library`, `test_e0c_the_box_check_sees_an_import_from_tests` | the two box scripts reach `host/`, `model/`, `spec/` and the standard library alone; a planted import of `tests/`, of `e0c.py` or of numpy is reported |
| the timed runs | `test_e0c_bit_identity_ten_timed_generations_run_and_score_as_the_model_does` | ten generations over the stand-in at 150 trials, each part present, each sum its parts', each count and SHA-256 the model's, the collector off in each; the signal-free reads cross there twice in all (row X26), which a wrong offset for them can change, but need not |
| a generation that ran another set | `test_e0c_control_a_generation_that_ran_another_set_is_reported` | sets 3 and 4 exchanged: generations 3 and 4 DIFFERENT |
| timed-judge's conditions, each alone | `test_e0c_control_timed_judge_fails_on_each_of_its_conditions` | in a copy of a passing timed.json: a generation not ended done, one fewer generation, one more, a found count, a noise count, or a records hash changed: each FAIL |
| the timed score's index check | `test_e0c_control_timed_score_refuses_a_record_read_at_another_index` | a record at a read place carrying another index is refused, RECORD_ORDER |
| an end that is not done | `test_e0c_a_generation_that_does_not_end_done_stops_the_ten` | a deadline stops the ten after generation 0, the kernel reset and the backend closed |
| the premise, and the records | `tests/test_e0c_premise.py` | section 7; a field changed in a copy is reported; each frozen file's SHA-256 is its note's |

Also `test_e0c_the_record_layout_is_the_models`, `test_e0c_the_ten_sets_are_the_stated_rule` and `test_e0c_a_card_record_names_its_definition_and_is_stale_by_name_once_it_moves`.

## 11. Limits

1. **Bit identity's own.** A fault the model and the card share passes, as on round 3's card day (its limit 8).
2. **A SHA-256 collision** inside a block would pass a differing block as equal. BELIEVED negligible, and nothing here can rule it out.
3. **The fabric at an offset seed** is seen only on the card day, by the comparison of every record. The first size runs the model alone at offset seeds.
4. **Nothing at scale runs in the first size.** No piece of 6.4 million frames and no XRT. The stand-in (`kernel_model.py`) models no block: it holds what E0C's scripts and the library do with a buffer the model filled, and it runs the model once at krn_start, so a truth record written while a run goes is refused there, not fed. The 205 MB buffer (untried, the plan says), the box's memory and time, and the host keeping up for 6.4 million frames are the card day's.
5. **The collector's pause is measured on the desktop only.** That a full collection inside a long run would outlast the store's slack on the box is an ESTIMATE. Turning the collector off answers it for E0C's runs; `host.run_case` run without the wrapper still has it.
6. **The card's stream is not seen.** A card part's `stream_sha256` is the desktop's, made by the model from the seeds; the card returns only scores.
7. **Three late reads an amplitude are not made**, the last trial of pieces 0 to 2. The late control is judged on the others and says how many.
8. **The premise** is shown by round 1's own script for one amplitude at full scale; for all five, in pieces, only when the expect run is made. Round 1's figures are taken as its part files give them (READ).
9. **The timed runs**: one host, one Python, the device opened for every generation, the collector off. The rate without the open is COMPUTED, not measured. No training between generations is timed, nor a swap inside one run.
10. **D8's own limits, and the tolerance's.** Stated in D0, section 6, and in round 1's judge.
11. **The reads trust their offsets.** A read at an index the reader was not asked for is not seen; only the index each record carries is checked.
12. **The timed script's signal-free read is held on two crossings.** At the first size's 150 trials its count is 2 in all (row X26); a wrong offset for that read that left both crossing would pass there. The pieces' reader, which `compare` uses, is held on 4,000 trials (row X20).
13. **`box_e0.sh` has not run anywhere.** Its syntax was checked on the desktop (`bash -n`), and it calls only the two box scripts and Python's `-c` with `json` and `sys`, which a test holds. What XRT, the box and the card do with it is the card day's.

## 12. Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| X1 | Amplitude k's stream is 25,600,128 frames, 200,001 spans of 128, the last empty | COMPUTED | 128 x (200,000 + 1); `tests/test_seam_e0.py`, `measure`'s length | that file |
| X2 | One buffer in one segment holds at most 65,535 whole spans, 8,388,480 frames, so at least four pieces | COMPUTED | the plan's L7, 8,388,484; 8,388,484 // 128 = 65,535; 200,001 / 65,535 = 3.05 | L7's conditions |
| X3 | The four pieces' first frames, frames, trials, buffers and record bytes are section 2's table | COMPUTED | `python hw/e0c/e0c.py cases <folder>`, each `piece.json` (2026-11-25 12:47); 3,968 + 32 x frames; 21 x frames | `test_e0c_the_stated_cut_is_the_designs` |
| X4 | The pieces' seeds are section 2's, each the generator's word `first` of the stream's seed | COMPUTED | the same `piece.json` files; `test_e0c_the_stated_cut_is_the_designs` holds words 0 and 1 by `model.source.word` | that test |
| X5 | The 20 pieces' records are 2,688,013,440 bytes, 4,096,020,480 as slots | COMPUTED | 5 x 25,600,128 x 21 and x 32 | arithmetic |
| X6 | 98 blocks of 65,536 records a piece | COMPUTED | 6,400,128 / 65,536 = 97.66, and 6,400,000 / 65,536 = 97.66 | arithmetic |
| X7 | The cases folder of the stated run is 80,182,554 bytes, made in 8.3 s; a piece's schedule is 3,741,320 bytes | MEASURED | `e0c.cases(<folder>)`, timed, and the files' sizes, 2026-11-25 12:47 (E0C's scratch, `expect_rate.py`) | a rerun |
| X8 | One full collection of Python's cyclic collector with 100,000, 600,000 and 1,200,000 trace entries held took 12.1, 87.8 and 141.6 ms at 12:21, and 12.8, 94.8 and 281.0 ms at 12:49, on the desktop | MEASURED | at 12:21 E0C's scratch `measure.py` (the ledger, 12:24), the same measurement as the committed one; at 12:49 `python hw/e0c/measure.py gc` | a rerun; the box's own |
| X9 | The injector's store holds 26.2 ms of the stream | COMPUTED | 1,024 x 128 x 200 ns, from `cap_inject_pending` and the plan's L3 | a timed run |
| X10 | Round 3's 2^20 e0 run's trace: 31,658 entries, 31,608 in finish over 209.7 ms from the krn_start write to the done read, 7,122 status reads; its fetch of 33,554,432 bytes 45.2 ms | MEASURED | `python hw/e0c/measure.py trace <repos>/AOTPU/Data/runs/2026-11-24-r3/data/CARD/run20-080851/e0/trace.json` | that file |
| X11 | A piece's trace ends at about 193,000 entries, and needs about 43,470 polling rounds | COMPUTED | 31,608 / 0.2097 s x 1.28 s; 7,122 x 6,400,128 / 1,048,576; from X10 | a piece's own trace |
| X12 | A full collection inside a piece would outlast the store's slack and lose the run, INJECT_OVERLAP | ESTIMATE | X8 to X11; CPython collects fully as its long-lived objects grow by a quarter | a piece run with the collector on |
| X13 | The library parses a slot in 1.70 to 2.10 us on the desktop, and holds 252 bytes a record | MEASURED | `python hw/e0c/measure.py parse`, 12:49 (2.10, 252); the ledger's scratch run, 12:21 (1.70) | a rerun |
| X14 | The box has 36 threads and 46 GB | READ | `<repos>/cft-fp256/CLAUDE.md`, its table of machines | the box |
| X15 | A piece is 20 to 35 s whole on the box, and the 21 runs 7 to 12 minutes | ESTIMATE | X13 at 6.4 million records; round 3's 2^20 cases at 4 to 5 s whole (its log `day20-080851.log`, in the round's folder) | the card day's log |
| X16 | expect runs at 19.07 to 21.15 us a frame on the desktop | MEASURED | `python hw/e0c/measure.py expect <folder>`, 12:49 (21.15); E0C's scratch `expect_rate.py`, 12:47 (19.07): 512,128 frames each | a rerun |
| X17 | The expect run is 8 to 9 minutes a process and 40 to 45 core-minutes for the five, with about 2 for the flip and about 4 for the timed sets | ESTIMATE | X16 x 25,600,128, x 6,400,000 and x 12,801,280 | the lead's run |
| X18 | The premise's rerun equals round 1's part 2 in every field but `spec_sha256` | MEASURED | `timeout 580 python tests/test_seam_e0.py --full --amplitude 2 --out part2.json`, 12:27:59 to 12:32:45, at 59dc834; `python hw/e0c/e0c.py premise vectors/e0c/premise/part2.json vectors/e0c/round1/part2.json` | `test_e0c_premise_round_1s_part_2_made_again_under_todays_tree` |
| X19 | Round 1's counts: 24,442, 55,857, 99,743, 144,075 and 175,622 found; 1,929, 1,974, 2,008, 2,041 and 1,987 noise crossings | READ | `vectors/e0c/round1/part0.json` to `part4.json`, copied from `<repos>/AOTPU/Data/runs/2026-11-21-r1-model/reports/e0/`; `docs/VALIDATION.md`, 2026-11-23 | those files |
| X20 | The short form in four pieces finds 1,999 of 4,000 and 30 crossings, every read the continuous form's | MEASURED | `python -m pytest -q -s tests/test_e0c_short.py` | that test |
| X21 | Its controls: reversed coefficients 0 of 4,000 at -63.3 se; read late 1,696 of 3,997 at -9.6 se, 3 not made | MEASURED | the same command | that test |
| X22 | The timed sets' d runs from -2.105 (set 0) to 2.327 (set 9); sets 0 to 3 are negative, sets 8 and 9 are 2.324 and 2.327 | COMPUTED | `python hw/e0c/e0c.py cases <folder>`, `timed/timed.json` (12:47): `stats.theory.deflection` | that file |
| X26 | At 150 trials, sets 0 to 3 each found 0, set 4 found 3, sets 5 to 9 found 54, 71, 76, 78 and 78; signal-free crossings 1 for sets 3 and 4 and 0 for the rest; each the model's | MEASURED | `python -m pytest -q -s tests/test_e0c_timed.py -k bit_identity_ten`, 2026-11-25 13:09, its `timed-judge` lines | that test |
| X23 | Parsing 1,280,128 records takes about 2.7 s, so a generation 3 to 4 s and 900 to 1,200 an hour | ESTIMATE | X13 x 1,280,128; round 3's whole cases, X15 | the card day's ten timed runs |
| X24 | Four pieces an amplitude; each piece one process; the collector off; no library change | DECISION | E0C's design, ruled by the lead, 2026-11-25 12:27 | not applicable |
| X25 | The flip is bit 12 of tap 28, -131071 to -126975 | READ | `docs/studies/CARD-first-light.md`; held by `test_e0c_the_flip_is_round_3s` | that test |

# Stage E1 on the card: the host's side

Parcel E1C, round 5, 2026-11-25 to 26: the one card day of round 5's plan (`docs/plans/R5-learning-in-fabric-and-real-noise.md`, on the round's branch and not in this parcel's tree) that needs no new image, every part of it but the card day itself, which is the lead's. Its design was approved by the lead at 20:56 on 2026-11-25, with one change to the swap run (the round's ledger, not committed). The code is `hw/e1c/`; its tests in the gate's first size are `tests/test_e1c_*.py`. Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure here is in the register at the end.

**What it is for.** Phase A's two halves together on the card for the first time. The host trains stage E1's learner on the desktop and hands its set over. The card scores E1's held-out streams under the learned set and under the matched filter, every record compared with the model's. E1's own judge then reads the card's records. One run swaps a trained set in mid-stream at the index the host names. This is D0's phase A, "the host reads captured windows and their truth records, trains ..., writes the shadow weights and commits the swap", with one difference: the windows are not captured from the card (limit 2).

**What a pass rests on.** Two authorities, never mixed (D0, section 2):
- **Bit identity** rests on the model. Every record of every run the card wrote is the model's own record of that run.
- **The counts** rest on stage E1's committed record ([E1-software.md](../studies/E1-software.md)), and on `stats/` inside E1's judge. Each part read from the card's bytes must equal E1's committed part, key for key, and E1's judge must print its committed output, byte for byte.

**It adds no new fact about sensitivity.** The counts equal E1's in software exactly when every record is the model's.

**What has been run.** Everything here in the first size, on the desktop: on the model, and through `host.run_case` over a stand-in for the card (`hw/e1c/standin.py`). That was done at a tiny plan, and once at stage E1's short form outside the gate (`python hw/e1c/e1c.py short <folder>`, section 10). The stated run's cases were made once at full scale (section 9). **Nothing of E1C has run on the box or on the card.** The expect run's full form is the lead's, booked, on the READY commit.

## 1. Where things are

| what | where |
|---|---|
| the training, the cases, the model's expectations, the card parts, the judge, the short form end to end | `hw/e1c/e1c.py` (desktop) |
| the cut of the held-out stretch on E1's grid of 64, and the reading of a piece's records | `hw/e1c/cut.py` (desktop) |
| E1C's own refusal names | `hw/e1c/errors.py` |
| the first size's stand-in for the card: E0C's `ModelKernel`, with the start epoch, a swap, and truth fed while a run goes | `hw/e1c/standin.py` (desktop) |
| the card day's script for the box | `hw/e1c/box_e1.sh` (box) |
| one run on the box: `host.run_case`, unchanged, the collector off | `hw/e0c/run_piece.py`, E0C's, unchanged (box) |
| the tests | `tests/test_e1c_cut.py`, `test_e1c_replay.py`, `test_e1c_train.py`, `test_e1c_judge.py`, `test_e1c_card.py`, `test_e1c_box.py` |

**Imported, not copied, and not changed:**
- `tests/test_lrn_a_e1.py`, by `hw/e1c/e1c.py` on the desktop only, as `hw/e0c/e0c.py` imports `test_seam_e0`. It supplies the plan, the schedule, the facts, the injection set's check, the read rules, `wired`, `evaluate`, `split`, `entry`, `compare_at_equal_rate`, `peak_offset` and `judge_parts`;
- `learn.trainer` and `learn.handover`;
- from `hw/e0c/pieces.py`: `seed_at`, the record's layout, `MOST_FRAMES`, `compare_blocks`, `block_hashes`, `flags_seen`, `digest_scores` and `flipped`;
- `hw/e0c/kernel_model.ModelKernel`, subclassed;
- `hw/e0c/run_piece.py`.

**Gate rows: none added, and no shared file changed.** The tests claim four existing rows of `tests/gates.toml`:

| row | its tests here | its controls here |
|---|---|---|
| `replay` | `test_gate_replay__e1c_pieces_read_every_held_out_record_as_the_continuous_stream_does` | `test_control_replay__e1c_a_piece_seeded_without_its_offset_differs_at_its_first_read`, `test_control_replay__e1c_a_schedule_a_block_late_differs_first_at_its_first_at_index_read` |
| `statistics` | `test_gate_statistics__e1c_the_committed_counts_through_the_card_judge_reprint_e1s_output`, `test_gate_statistics__e1c_evaluate_card_is_evaluate_on_the_short_forms_reads` | `test_control_statistics__e1c_a_count_changed_by_one_in_the_cards_tally_changes_the_judges_output`, `test_control_statistics__e1c_evaluate_card_reports_a_baseline_read_changed_and_a_digest_not_the_statistics` |
| `comparison-rules` | `test_gate_comparison_rules__e1c_the_desktops_training_is_e1s_for_every_part` | `test_control_comparison_rules__e1c_a_set_trained_on_the_judged_stretch_is_refused` |
| `swap` | `test_gate_swap__e1c_each_swap_run_is_the_models_named_schedule_the_new_set_from_the_named_index` | `test_control_swap__e1c_a_commit_at_another_index_differs_from_the_named_schedule` |

D0's gate `bit identity` is held by the stage `rtl-benches`, so no pytest test may claim it. E1C's tests of the card's side over the stand-in claim no gate, as E0C's do not.

## 2. Stage E1's six parts

From `tests/test_lrn_a_e1.py`'s `plan` and the committed parts `docs/studies/e1/c0.json` to `c5.json`:

| part | truth records | windows | seed | A | B | L |
|---|---|---|---|---|---|---|
| 0 | 16 | 32 | 2026112500 | 2,048 | 12,802,048 | 25,602,048 |
| 1 | 64 | 128 | 2026112501 | 8,192 | 12,808,192 | 25,608,192 |
| 2 | 256 | 512 | 2026112502 | 32,768 | 12,832,768 | 25,632,768 |
| 3 | 1,024 | 2,048 | 2026112503 | 131,072 | 12,931,072 | 25,731,072 |
| 4 | 4,096 | 8,192 | 2026112504 | 524,288 | 13,324,288 | 26,124,288 |
| 5 | 16,384 | 32,768 | 2026112505 | 2,097,152 | 14,897,152 | 27,697,152 |

Each part is one stream: profile `s16x1`, sigma 1477/1, `e0` at amplitude 1/1.
- **Training,** frames 0 to A - 1: N trials, each truth at 64 + 128 i.
- **Calibration,** A to B - 1: 12,800,000 frames with no injection, 200,000 signal-free reads at A + 63 + 64 g.
- **Test,** B to L - 1: 100,000 trials at B + 64 + 128 i. Each has a signal-free read at truth - 1 and its at-index read at truth + 63.

So the held-out stretch is 25,600,000 frames and 400,000 reads. E1's learned set is committed at A.

## 3. The pieces, and why every read is whole inside one

**Four pieces a part, each 6,400,000 frames.** They start at A, A + 6,400,000, B and B + 6,400,000 (part 5: 2,097,152, 8,497,152, 14,897,152 and 21,297,152).
- Pieces 0 and 1 are the calibration stretch's halves, 100,000 reads each, and hold **no truth record**.
- Pieces 2 and 3 are the test stretch's halves, 50,000 trials each.
- Each piece's seed is `hw.e0c.pieces.seed_at(seed, first, 1)`, and its schedule is its truth records less `first` (`hw/e1c/cut.py`).

**Why.** Every read is at A + 63 + 64 g. Its window is frames A + 64 g to A + 64 g + 63 (conventions, CV2), one whole block of 64 counted from A. Every bound is A + 64 q, so no read's window crosses one.
- In its piece, each read sits at local 64 q' + 63, at least 63, where the delay line holds the piece's own samples only.
- A test pulse at B + 64 + 128 i = A + 64 (m1 + 1 + 2 i) fills exactly one block, so no bound splits a pulse.
- The last training pulse ends at A - 1, before piece 0.
- A piece's records 0 to 62 may differ from the continuous stream's. None is read, and each is still compared with the model's run of that piece, word for word.

**Refused by name** (`hw/e1c/errors.py`):
- PIECE_CUT:
  - a bound not of the form A + 64 q, or a first piece not at A;
  - bounds that do not rise, or that reach the stream's end;
  - a stretch that is not whole blocks;
  - a record whose pulse a bound splits;
  - a swap run of 2 A frames past B.
- PIECE_LENGTH: a piece past 8,388,484 frames, one buffer in one segment.
- PIECE_SET:
  - schedules that do not join back into the part's own;
  - the case folders of a part that are not its stated cut, each piece once;
  - a stated part whose plan is not stage E1's.

These three names mean what E0C's names of the same spelling mean, on E1's grid in place of E0's spans of 128. A read is also refused under two names of the definition's: RECORD_ORDER for a read whose record carries another index than its place, and RUN_LENGTH for a records file that is not its piece's frames.

## 4. Epochs, the training stretch, and the two swap runs

**The 48 judged pieces are loaded,** not swapped into:
- the learned set at epoch 1, the epoch E1's held-out records carry after the hand-over;
- the matched filter at epoch 0, as E1's own baseline records are made (`records_from(..., BLANK_EPOCH)`).

So the card's parts carry E1's epochs, from the card's own bytes. **In these runs the epoch's change at A is the host's load, not a swap** (limit 3).

**The two swap runs,** both on part 5's stream from frame 0, 4,194,304 frames (2 A), seed 2026112505. Its 16,384 training trials are their schedule, and after A comes the calibration stretch's first 32,768 blocks.
- **swap-blank, E1's own flow:** E1's blank set (`learn.handover.blank_blob`, every coefficient 0) loaded at epoch 0. The learned set is written into the shadow once the core has taken 1,048,576 frames, and committed at A = 2,097,152. This is `host.run_case --swap-blob ... --swap-at 2097152 --swap-after 1048576`, through the core's swap as `host/` does it.
- **swap-matched:** the same, over the matched filter at epoch 0 (the lead's ruling, 2026-11-25 20:56).

**What each must be:**
- every record the model's run of the same schedule, by E1's own wiring (`wired`, `learn.handover.hand_over`);
- from the card's bytes, the first record of epoch 1 at the named index;
- `report.json`'s two `next_index` reads, which bracket the swap, both below it.

The model's run before the commit is the blank core's or the matched filter's, and from the commit on the learned set's. **The host library and the model take the blank set:** in the first size it is loaded, run and swapped out with no refusal. Whether the fabric takes it is the card day's (limit 7).

**The training stretch's two keys,** `scores_not_zero_while_blank` and its share of `flags`:
- **Part 5's come from the card's bytes**, records 0 to A - 1 of swap-blank, when that run is there. Those records must also equal the desktop's blank run of the same frames, by their SHA-256.
- **Parts 0 to 4's come from the desktop's model run** of frames 0 to A - 1 through the blank core.

## 5. The flip: one coefficient changed

Part 5's learned piece 0, run with `hw.e0c.pieces.flipped` of the learned set: round 3's and E0C's flip, bit 12 of the first tap of the largest magnitude. For part 5 that is tap 28, -131,071 to -126,975.
- It must be IDENTICAL to the flipped set's own model run, and DIFFERENT from the learned piece's expectation.
- It must differ first at the record the samples predict: the first j at or past 63 - 28 = 35 whose sample j - 35 is not 0, in the score field, by 4,096 times that sample (`expect --flip`).

## 6. The expected records, and the comparison

**Made on the desktop** by `hw/e1c/e1c.py expect`, before the card runs, under `<cases>/expect/`.
- **For each run:** the SHA-256 of the model's canonical records (`model.records.pack`'s bytes, what `host.run_case` writes to `records.bin`), whole and for each block of 65,536, with the OR of their flags and a digest of its reads.
- **For each part:**
  - the desktop's training keys;
  - the statistics' own reads of the same samples with the same integers (`stat_scores_at_reads`, the statistics' float filter, exact for integers): a digest for each set, and the 512 baseline scores of the first 256 test trials;
  - **the model's own part made in pieces by E1's own `evaluate`,** with that part against E1's committed part, key for key. That is the premise at full scale.

**The comparison** is `hw.e0c.pieces.compare_blocks`. It gives IDENTICAL, or the first differing record named with its field and both values, by making that block again through the model. A file of too few records, too many, or with part of a record over is named too.

## 7. The card's parts, and the judge

`python hw/e1c/e1c.py compare <cases> <runs>`, on the desktop, from the card's `records.bin` of each run:
1. **Bit identity**, run by run, by the block hashes.
2. **The reads, from the card's bytes.** Every local 63 + 64 q is read, each required to carry its index and put at its stream index.
3. **Each part's card part,** made by `evaluate_card`: `evaluate`'s own lines, by `evaluate`'s own functions, with the baseline's records handed in from the card's matched-filter runs. `evaluate` makes them from the statistics' float filter on the kept samples, and holds the model's core to them on the first 256 test trials. A test holds `evaluate_card` equal to `evaluate`, key for key, whenever the baseline's records are the statistics' scores (limit 9). Then **the card part against E1's committed part, key for key:** EQUAL, or DIFFERS naming the keys.
4. **E1's own judge** (`judge_parts`) on the six card parts, written as files. Its output must be `docs/studies/e1/judge-output.txt` byte for byte. If it is not, the first differing line is named.
5. **The swaps and the flip,** on lines of their own: `== E1C SWAP blank:`, `== E1C SWAP matched:`, `== E1C FLIP CONTROL:`.
6. **The verdict,** `== E1 CARD VERDICT: PASS`, only when all of these hold:
   - every run is IDENTICAL, and every record's flags are 0;
   - the card's baseline reads are the statistics' at every read;
   - part 5's training stretch from the card is the desktop's blank run;
   - all six parts are EQUAL, and the judge's output is byte-equal;
   - both swaps are SEEN, and the flip is SEEN.

   Exit 0 only then. Each condition broken alone fails in a test (section 11). `compare` writes `card-e1.json`: the card parts, what each check found, and the definition's hash.

**Where each key of a card part comes from:**

| keys | from |
|---|---|
| part, name, trained_on, labelled_windows, seed, profile, sigma, pfa, amplitude, taps, spacing, A, B, length, n, m, reported, rate_floor, rate_label, d_matched, spec_sha256 | the plan and E1's `facts`, imported |
| k, above, threshold, threshold_epoch, held_out_epochs, found | the card's learned records |
| base_threshold, base_above, base_found, base_found_known_threshold | the card's matched records |
| base_only, learned_only, noise_base_only, noise_learned_only, noise_both, comparison_refused | both card models, by `compare_at_equal_rate` |
| scores_identical_to_stats | the card's learned reads against the statistics' digest |
| core_equals_baseline_on_first_trials | the card's matched reads of the first 256 test trials against the statistics' 512 scores: the software check with the card's core in place of the model's |
| first_new_epoch_index | the stream index of the first epoch-1 record of the card's learned pieces: A, by the load at epoch 1 |
| flags | the OR of the card's learned records' flags and the training stretch's (part 5's from the card, the others' from the desktop) |
| scores_not_zero_while_blank | part 5's from the card's swap-blank run; the others' from the desktop's blank run |
| coefficients, blob_sha256, d_learned, peak_offset, learner_counts, handover_refusal | the desktop's training |
| injection_sha256 | E1's `check_injection_set` against `vectors/lrn-a/injection_sets.json` |
| stream_sha256 | the desktop's: the SHA-256 of the training samples and the four pieces' samples chained |

**If the day is cut short,** `compare --parts 5` judges the reported part alone: its eight pieces, both swaps, the flip, and its card part against `c5.json` key for key. The six-part judge then prints NOT RUN, and the verdict is FAIL.

## 8. What runs where, and what crosses

**The box** runs a snapshot of E1C's commit: `host/`, `model/`, `spec/`, `hw/e0c/` and `hw/e1c/`, under Python 3.12.3.
- Each run is `python3 hw/e0c/run_piece.py <run_case's arguments>`: one process a run, the collector off, run_case unchanged, `--polls 2000000`, `timeout 900`, as E0C's day.
- Besides those it runs only `python3 -c` with `json` and `sys`. Nothing of `learn/`, `tests/` or numpy (`test_e1c_box.py`).
- `box_e1.sh` reads its runs in order from `order.txt`: name, case, blob, epoch, and for a swap its blob, index and wait.
- A run that ends refused, a blank set's among them, is logged and the next run goes on.

**The desktop** makes the cases, trains, makes the expectations, and judges.

**Desktop to box:** the cases folder, 47,641,954 bytes for the stated run, and its `expect/` folder, made by the lead's expect run. Its parts:
- 12 test schedules of 50,000 records each, each shared by its piece's learned and matched runs;
- 12 empty calibration schedules, shared likewise;
- the two swap runs' schedules, 16,384 records each;
- the piece.json files, `table.json`, `order.txt`;
- the blank, matched, six learned and flipped blobs.

**Box to desktop:**
- 6,673,680,384 bytes of records, which are 317,794,304 records of 21 bytes;
- each run's report.json and log;
- the day's log and SHA256SUMS.

`trace.json` stays on the box.

## 9. The card day, as the lead would run it

1. On the desktop, on the READY commit: `python hw/e1c/e1c.py cases <cases>`, about 42 s. It trains all six parts and refuses LEARNED_SET unless each is E1's committed set. Then the expect run:
   - `python hw/e1c/e1c.py expect <cases> --part c` for c from 0 to 5, one process each;
   - `expect <cases> --swap blank`, `--swap matched` and `--flip`.

   Each `expect/part<c>.json` says whether the model's part in pieces is EQUAL to E1's, key for key. The expectations' SHA-256s go in the ledger before the card runs.
2. Copy `<cases>` to the box, with the snapshot and the shim built there.
3. On the box, detached: `setsid nohup bash hw/e1c/box_e1.sh <host tree> <build folder> <cases> > <log> 2>&1 < /dev/null &`. Its runs, in order:
   - health before;
   - part 5's eight pieces, its two swap runs and the flip;
   - parts 4, 3, 2, 1 and 0, eight runs each;
   - health after, and SHA256SUMS.
4. Copy back the records, reports and logs, and check each file's SHA-256 on both machines.
5. On the desktop: `python hw/e1c/e1c.py compare <cases> <run folder>`.

**Size and time on the card.** 50 runs:
- 48 judged pieces, 307,200,000 frames, 2.4 times round 4's E0 day;
- the two swap runs, 8,388,608 frames;
- the flip piece, 6,400,000 frames.

So 321,988,608 frames and 6,761,760,768 bytes of records. **About 17 to 21 minutes of the card, an ESTIMATE**, at round 4's 19 to 22 s a piece, with part 5's results in about 4. Then the copy back takes about 6 minutes at round 4's rate, and compare about a minute. **The whole of E1 fits the booked morning.**

## 10. On r5's definition

**A condition of this work:** every test of `tests/test_e1c_*.py` reads stage E1's committed parts for their coefficients and counts and **never for `spec_sha256`**. A card part carries the tree's own hash, as `evaluate` gives it. So the tests hold on E1's parts whichever definition made them: round 3's at E1C's commit, round 4's and round 5's on r5 (the lead's ruling, 2026-11-25 20:56). None of them reads round 3's hash or the card's image, and the stand-in takes the tree's own definition. **None of them calls a skip, so on r5 every one of them runs.** Whether each passes there is the lead's trial merge's to show.

The card day's committed record, which is the lead's, will name round 3's definition. On r5 its judge tests skip by name, **E1C-CARD-STALE**, through `hw/e1c/e1c.py`'s `stale(record)`, as E0C-CARD-STALE does. `test_e1c_judge.py` holds `stale` on a record of another hash.

**How the lead checks before the merge:** a trial merge onto r5's tip in a scratch worktree, which adds files only and so does not conflict; the first size there; and `python -m pytest -q -p no:cacheprovider -rs tests/test_e1c_*.py`.

**The short form, end to end, outside the gate.** `python hw/e1c/e1c.py short <folder>` runs stage E1's short form through every step of the card day, the card the stand-in:
- its cases, its expectations, and its eleven runs through `run_piece` and `host.run_case`;
- the test pieces fed 1,024 truth records before the start and 976 while the run goes, as the card's will be;
- then compare.

It gives `== E1 CARD VERDICT: PASS`: every run IDENTICAL, the card part EQUAL to LRN-A's own short form part key for key, both swaps SEEN at 131,072, and the flip SEEN at record 35 as predicted. That is the premise in pieces at the short form's size, and the card's side end to end at a size where the statistics' floor of 100 crossings is met.

## 11. The tests and the controls

`python -m pytest -q -p no:cacheprovider tests/test_e1c_*.py`. The brief's five named controls, each in the first size, on the model:

| named control | test | it shows |
|---|---|---|
| 1. a learned set trained on windows from the stretch it is judged on is refused, as E1's rule 2 refuses it | `test_control_comparison_rules__e1c_a_set_trained_on_the_judged_stretch_is_refused` | the whole stream, frames below A with a held-out truth record, and the test stretch's own frames: each TRAINED_ON; with hw/e1c's check taken out, the trainer's WINDOW_OUTSIDE_PERIOD, or LEARNED_SET |
| 2. a card record changed in one word is reported, at that record | `test_e1c_control_a_card_record_changed_in_one_word_is_reported_at_that_record` | in each of index, epoch, flags and score, in a learned piece, a matched piece and both swap runs: named at that record, that field, both values; one record short, one extra and a byte over, each named |
| 3. one coefficient changed differs from the learned set's run at the first record it reaches | `test_e1c_control_one_coefficient_changed_differs_from_the_learned_sets_run_at_the_first_record_it_reaches` | the flipped set's run differs first at the record the samples predict, in the score field, by the predicted amount. The card's version is the flip piece, the lead's |
| 4. a commit at another index than the named one differs from the model's run of the named schedule | `test_control_swap__e1c_a_commit_at_another_index_differs_from_the_named_schedule` | committed at A + 1, the first difference is record A, epoch, card 0 and model 1; at A - 1, record A - 1, card 1 and model 0; for both swap runs |
| 5. a count changed by one in the card's tally makes the judge's output differ from E1's committed output | `test_control_statistics__e1c_a_count_changed_by_one_in_the_cards_tally_changes_the_judges_output` | one injection more found by the learned set: three lines differ, part 5's curve, its paired cost and the reported model. One more by the baseline: two lines. One signal-free crossing moved from both models to one each: one line. One count alone: NOT AS STATED |

**Also:**
- the stated cut, its reads and its seeds, and every refusal of the cut by name (`test_e1c_cut.py`);
- the gate `replay` on small streams under both profiles, with its two controls;
- the desktop's training of parts 0 to 3 equal to E1's committed sets. Parts 4 and 5 are held by `cases`, in about 42 s for all six (row K14);
- the short form's honest set equal to LRN-A's;
- `evaluate_card` equal to `evaluate` on the short form's reads, and its control;
- the stated run's compare path, its card parts stood in by the committed ones:
  - six parts PASS;
  - a day cut to part 5 FAIL, NOT RUN;
  - one count changed FAIL at line 9;
  - every part E1's under a judge that prints one line more: FAIL, the judge's condition alone;
- `stale`.

On the tiny plan through the stand-in:
- every run IDENTICAL, and the card part equal to E1's own `measure` and `part_of`;
- the gate `swap`;
- a commit after the core passed the named index refused by name, SWAP_INDEX;
- the learned pieces loaded at epoch 0, which differ in `held_out_epochs`, `threshold_epoch` and `first_new_epoch_index`;
- the two sets exchanged, seen by the run's identity and by the statistics' digest;
- a flip the card did not run;
- pieces that are not the stated cut, PIECE_SET;
- `cases`' three checks, each by itself: another injection set (INJECTION_SET), another trained set (LEARNED_SET), schedules that do not join back (PIECE_SET);
- `order.txt` as the box script reads it;
- `expect`'s LEARNED_SET;
- the swap run's epoch and its fit before B.

**Thirteen changes, each breaking one of the verdict's conditions alone, each FAIL by the line that says why** (`test_e1c_control_the_verdict_fails_on_each_of_its_conditions_alone`):
- a matched record no read takes, changed;
- a flag with its expectation made to match;
- the statistics' baseline digest;
- the reference part;
- the desktop's blank run's hash;
- the swap's next_index bracket;
- the swap's first new epoch;
- the flip's predicted record;
- the flip's predicted difference;
- a flip that changed nothing;
- a swap record changed;
- a swap flag;
- a run's records missing.

**The box** (`test_e1c_box.py`): nothing it runs imports `tests/`, `learn/` or numpy, by E0C's own import check, imported. Every flag the script hands `run_piece` is one `host.run_case` declares.

## 12. Limits

Each is stated by the behaviour it concedes.

1. **Bit identity's own.** A fault the model and the card share passes.
2. **The training windows are the model's, made on the desktop. Nothing is captured from the card,** which returns scores only. D0's phase A "reads captured windows". Here the host reads the windows its own model makes of the same seed, and a card whose noise or injector differed from the model's in the training stretch alone would be seen only in part 5's swap-blank run, by its scores.
3. **The judged runs hold no swap.** The learned set is loaded at epoch 1. The hand-over at A is on the card in part 5's two swap runs alone; parts 0 to 4's hand-over is the model's alone.
4. **Parts 0 to 4's blank training stretch is not run on the card;** its two keys are the desktop's model run.
5. **The card's stream is not seen:** `stream_sha256` is the desktop's.
6. **A SHA-256 collision** in a block, or in a reads digest, passes.
7. **Untried on the card, BELIEVED:**
   - an empty schedule (the 24 runs of the 12 calibration pieces);
   - a load at epoch 1;
   - the blank set loaded and swapped out.

   The kernel's benches run the first two in simulation (`rtl/tb/bench_krnl.py`: an empty schedule, and epoch 11), and the host library and the model take the third. The day's comparison decides each.
8. **The stand-in models no block.** XRT, the box, the 205 MB buffers and the host keeping up with 48,976 truth records while a run goes are the card day's, as E0C's were. The stand-in takes a truth record however late it is written, and never says a record came late.
9. **`evaluate_card` is a mirror of `evaluate`,** held equal to it on the tiny plan (through compare) and the short form (directly). A divergence in a key no case varies would pass. One case of that kind is known: on the tiny plan an exchanged baseline set moves no key of the part, so that case holds the run's identity and the statistics' digest and not the part.
10. **The premise at full scale** is the expect run's, the lead's, before the card day. The gate has the tiny plan, small streams and the short form's reads; the short form end to end is a command, run once (section 10).
11. **The tiny plan's part is made with the statistics' floor of 100 signal-free crossings lowered to 1** inside its tests, since its 104 signal-free scores have one crossing at Pfa 0.01. The floor is the statistics' rule for a threshold; the short form meets it.
12. **Nothing new about sensitivity:** the counts equal E1's exactly when every record is the model's. One card, one clock, one profile (`s16x1`, E1's only one).
13. **The flip is one bit of one tap on one piece.**
14. **The swap's margin** is about 0.21 s at 200 ns a frame. A commit that arrives after A is refused by the core, SWAP_INDEX: a lost run by name.
15. **The flags condition of the verdict is implied by bit identity** wherever the model raises no flag, which is every run here. It is held alone only by a test that makes the expectation match a planted flag.

## 13. Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| K1 | Section 2's table: each part's N, windows, seed, A, B and L | READ | `tests/test_lrn_a_e1.py`, `plan`; `docs/studies/e1/c0.json` to `c5.json`, keys A, B, length, seed | those files |
| K2 | A part's held-out stretch is 25,600,000 frames and 400,000 reads; four pieces of 6,400,000 frames and 100,000 reads; part 5's first frames 2,097,152, 8,497,152, 14,897,152 and 21,297,152 | COMPUTED | 64 x 200,000 + 128 x 100,000; 200,000 + 2 x 100,000; held by `test_e1c_the_stated_cut_is_the_designs` | that test |
| K3 | Every read of every piece is E1's own read position, in E1's order, at local 63 or later | MEASURED | `python -m pytest -q -p no:cacheprovider tests/test_e1c_cut.py`, its second test | that test |
| K4 | 131,070 blocks of 64 fit one buffer of 8,388,484 frames and 131,071 do not | COMPUTED | 64 x 131,070 = 8,388,480; 64 x 131,071 = 8,388,544; held by the cut's refusal test | arithmetic |
| K5 | Part 5's flip is bit 12 of tap 28, -131,071 to -126,975, and its first possible record is local 35 | COMPUTED | `python hw/e1c/e1c.py cases <folder>`, its `flip/piece.json` (2026-11-25 21:19); 63 - 28 | that file |
| K6 | 50 runs, 321,988,608 frames and 6,761,760,768 bytes of records; 616,384 truth records on the card in the judged pieces and one swap run's schedule, 632,768 with both | COMPUTED | 48 x 6,400,000 + 2 x 4,194,304 + 6,400,000; x 21; 12 x 50,000 + 16,384, + 16,384 | arithmetic |
| K7 | 17 to 21 minutes of the card | ESTIMATE | round 4's 19 to 22 s a piece of 6,400,000 frames (CARD-e0.md, CE9, MEASURED there) x 48, the two swap runs and the flip at the same rate a frame, and health | the card day's log |
| K8 | A copy back of about 6 minutes | ESTIMATE | round 4's 2,822,461,773 bytes in 159 s (its ledger, READ) at the same rate for K6's bytes | the card day's copy |
| K9 | An expect run of 12 to 18 minutes, six part processes at once beside two shorter ones | ESTIMATE | K15's 28.29 us a frame over a part's 25,600,000 held-out frames and its training stretch is 12 minutes of one core; contention on 12 logical cores, a guess, the rest | the lead's expect run |
| K10 | The stated run's cases folder is 47,641,954 bytes, made in 42 s, with all six trained sets E1's (no LEARNED_SET) | MEASURED | `python hw/e1c/e1c.py cases <folder>` from 21:18:28 to 21:19:10 on 2026-11-25, and `du -sb` of the folder | a rerun |
| K11 | The short form end to end over the stand-in: PASS; every run IDENTICAL; the card part EQUAL to LRN-A's short form part key for key; both swaps SEEN at 131,072; the flip SEEN at record 35, as predicted; the test pieces fed 1,024 truth records before the start and 976 while the run went | MEASURED | `python hw/e1c/e1c.py short <folder>`, 21:24:05 to 21:26:09 on 2026-11-25 | a rerun |
| K12 | The host library loads E1's blank set at epoch 0, run_case runs the swap-blank run to its PASS line, and the model's records are every score 0 before the commit | MEASURED | `python -m pytest -q -p no:cacheprovider tests/test_e1c_card.py -k gate_swap` | that test |
| K13 | The desktop's training of stage E1's parts 0 to 3 gives each committed part's coefficients, blob hash, counts and refusal | MEASURED | `python -m pytest -q -p no:cacheprovider tests/test_e1c_train.py -k gate` | that test |
| K14 | The desktop's training of all six parts gives each committed part's set | MEASURED | K10's `cases`, which refuses LEARNED_SET otherwise | a rerun of `cases` |
| K15 | The model's run of the short form's pieces under both sets, with its training stretch through the blank core and the statistics' reads, took 29.0 s for 1,024,000 held-out frames, 28.29 us a frame | MEASURED | E1C's scratch script `short_premise.py`, 2026-11-25 21:19:41 to 21:20:24, which calls `cases` and `expect_part` on the short form: **not in the tree**; the short command of K11 makes the same run with more beside it | a rerun |
| K16 | The desktop's cost a frame: source and inject 1.76 us, one core 7.12 us, a record's pack 2.34 us, the blank core 6.01 us | MEASURED | E1C's scratch script `rate.py`, 2026-11-25 21:01, 200,000 frames: **not in the tree** | a rerun |
| K17 | The desktop has 12 logical cores | MEASURED | `nproc`, 2026-11-25 20:51 | the desktop |
| K18 | The kernel's benches run an empty schedule and a start epoch of 11 | READ | `rtl/tb/bench_krnl.py`, lines 73, 107 and 177; `rtl/tb/seam_host.py`, `Case` | those files |
| K19 | The swap's margin is about 0.21 s | COMPUTED | 1,048,576 frames at about 200 ns a frame (CARD-first-light.md's timing paragraph, READ) | the card's run |
| K20 | No new gate row, and no shared file changed | DECISION | the lead's ruling, 2026-11-25 20:56, item 4 | not applicable |
| K21 | The learned set loaded at epoch 1 and the matched filter at 0; the blank swap run beside the matched one; part 5's training keys from the card | DECISION | the lead's ruling, 2026-11-25 20:56, items 1 and 2 | not applicable |

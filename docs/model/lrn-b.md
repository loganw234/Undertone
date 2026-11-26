# The learner of phase B, in the model: `model/learner.py`

Written by parcel LRN-B in round 5, 2026-11-25, from its design as the lead ruled it (the round's ledger, LRN-B's entry of 21:00 and the lead's of 21:04, which are not in the tree). Labels are those of [the design D0](../studies/D0-rough-design.md): MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure on this page is in the register at the end.

## What this is, and what it is not

D0's section 4 names two phases of learning. Phase A, the host trains and the fabric swaps, is round 2's (`learn/`, [lrn-a.md](lrn-a.md)). Phase B is "an update rule in the fabric, applied per labelled window". Logan's word on the round's question 2 reads that as **the learner's state changing at every window and its weights at indexes the host names**, by phase A's own rule, the difference of two class means. This page is that learner **written in the model first**, because the model is the authority: a parcel after this one builds it in RTL and is held to it word for word.

**What a pass here is evidence of:** that the model's learner in the stream is round 2's rule (its set equals the trainer's hand-over of the same windows, word for word), that it does what this page says on the cases worked by hand, and that it keeps the restated truth isolation. **It is not evidence about sensitivity**, which has its own authority. Handed the windows stage E1 trains on, the learner's set is the trainer's own, which is what E1's result in software is about; the tests hold that on a part of 16 records, not on E1's full run. **Nothing here is in the fabric yet.**

## Where it sits

| file | what | imports |
|---|---|---|
| `model/learner.py` | `Learner`: one core and the learner beside it; `ranges` and `widths` | the standard library, `spec.constants` and the model's own modules: nothing of `learn/`, `stats/` or numpy |
| `model/run.py` | `learning`: the injector feeding the core with the learner beside it, and a script of host operations by index | as before, and `model.learner` |
| `vectors/lrn-b/cases.json` | four cases worked by hand | |
| `tests/test_lrn_b_*.py` | the tests below | `learn/` is imported by the tests alone, to hold the equality |

The definition carries what the learner needs (round 5's change, the lead's, from this parcel's design): the section `[learn]` with `count_bits` and `update_frames`; the refusal names UPDATE_UNFINISHED and LEARN_BOUND; the block `learner`, 0xD00 to 0xE00, carved from the end of the core's; its thirteen registers from `lrn_update_at` to `lrn_cap_update_frames`; and the bits of `lrn_status`.

## What the learner reads

The learner is handed the truth records as the injector returns them and reads each record's `index`, and nothing else: not its pulse id, not its amplitude, and never a score record. It checks only that an index is an int of the index field (RECORD_FIELD) and that the indexes rise strictly (RECORD_ORDER).

It sees every frame the core sees: `Learner.step` hands the core the frame unchanged, then keeps its own copy of the last T frames, T the running shape's taps, with zeros before frame 0. That copy is the core's delay line.

## The windows

For a truth record at index j, with p the record before it and q the one after it:

| window | frames | judged when the core's next index is | skipped, the first that holds, as | otherwise |
|---|---|---|---|---|
| label 0 | j - T to j - 1 | j (when the learner is made, for j = 0) | START: j < T. BUSY: p exists and j - p < 2T. FULL: label 0's count is at its most | taken: added to label 0's sum, its count up by one |
| label 1 | j to j + T - 1 | j + T | BUSY: p exists and j - p < T, or q exists and q - j < T. FULL: label 1's count is at its most | taken |

- **A record's span is taken to be j to j + T - 1.** The learner is not told a pulse's length, as the trainer is not: "another record's pulse touches" is another record's span. These are `learn.trainer.labelled_windows`'s conditions (START its WINDOW_OUTSIDE_PERIOD at the start; BUSY on label 0 its WINDOW_NOT_FREE; BUSY on label 1 its TRAINER_INPUT for records closer than T) and FULL is its TRAINER_COUNT at the fabric's bound. The trainer raises where the learner skips and counts.
- **The stream's end.** A window whose judge point the stream never reaches is neither judged nor counted. A judge point at the next index equal to the stream's length, after the last frame, is reached.
- **Two taken windows share no frame and are judged at least T apart** (L1). So a fabric adds at most one window in any T frames.
- Every judgement is in `Learner.log`, as (next index, record index, label, outcome), in the order of the next index and then of the record.

## The update

**Named** by `update(u)`, a host operation. Refused, in this order: UPDATE_UNFINISHED (an update is named and not finished); SWAP_SHAPE (the running shape is not the matched-filter configuration of its profile and taps: one filter reading every channel, the rectifier passing, a pool of 1, no shift, no hidden layer); SWAP_PENDING (a commit is scheduled); SWAP_INDEX (u is not an int, is below the next index, or u + `update_frames` passes the index field's most).

**Made** at the first moment the core's next index is u and every window judged there has been judged: at the call itself when u is the next index, else at the end of the step that takes frame u - 1. From the counts n0, n1 and the sums S0, S1 as they stand then:

    D[c][k] = S1[k][c] * n0 - S0[k][c] * n1        each channel c in order, each tap k, tap 0 the window's oldest frame

then `model.weights.quantise(D)`, peak to COEFF_MAX and half to even over the whole set, and `model.weights.pack` in the matched-filter configuration with a head weight of 1. Those are the two calls `learn.handover.candidate_blob` makes; between D and the trainer's weights S1/n1 - S0/n0 is the factor n0 n1, which the peak cancels (L2). The set is written to the core's shadow by `Core.write_shadow`. **A count at zero makes every D zero**, because that label's sum is zero too, and an all-zero set is the quantiser's refusal, QUANTISE_INPUT: the update then makes no set and the shadow is left as it was.

**Finished** when the next index is u + `update_frames`, whatever it made. Its outcome is published then and not before: `lrn_made` or `lrn_unmade` counts it and `status()` says it. So whether a commit is refused depends on indexes alone, never on the truth.

**The sums at u.** A window judged between u and the finish goes into the sums, and into the next update; the update at u is of the sums at u (the lead's ruling, question 2). How a fabric holds them is its own design.

`update_frames` is the definition's, a requirement on the fabric (the lead's ruling, question 1). The model takes it as a number: 0 is allowed here, and with 0 the learner's flow is stage E1's hand-over in software exactly, made and committed at A.

## The shadow and the commit

- From an update's naming to its finish the shadow is the learner's: a host shadow write is refused, UPDATE_UNFINISHED, as are a commit and another update. A commit so refused is counted, `lrn_early`: the plan's "updates refused for time".
- The check is made **when the operation is named**, whatever index a commit names. A fabric slower than its update time then refuses a commit the model takes, which is seen, where a check on the named index alone would let it swap a shadow it had not finished writing.
- After the finish the shadow holds the last set written, by the learner or the host, and a commit takes what it holds.
- A commit is the core's own after that one check: SWAP_PENDING, SWAP_INDEX, SWAP_EPOCH. A shadow write likewise: SWAP_PENDING, the blob's own names, SWAP_SHAPE.

## Truth isolation, restated

D0's gate "truth isolation" held "no path from the truth record to any output record". The learner reads the truth's indexes, so a truth record reaches the score through the weights. Logan's word on the round's question 3 restated the gate: **no path from a truth record to any output record except through a set the learner makes and a commit the host names.** In observable form, as `tests/test_lrn_b_isolation.py` holds it under both profiles:

- the same samples under different truth records give identical score records up to the first named commit, and the same events and histogram from a scorer fed them;
- after it, the records are those of a core with no learner, the learner's set written to its shadow and committed at the same indexes;
- with an update and no commit, every record of the run is the same under every truth.

The same samples come under different truth by schedules that add nothing to them and say other things: the real indexes at amplitude zero; other indexes at amplitude zero, which are labels with no pulse; the second pulse's id at amplitude zero; no record; and the real schedule with every amplitude written another way, n/d as 2n/2d. The core starts from the matched filter for `e0` with a gain of its own on each channel, so that every record before the commit carries a score a leak would move.

**What depends on truth and is not an output record:** the learner's own counts, counters, status and refusals. They are read by the host, who holds the truth already.

## The widths

At the definition's `count_bits` of 32, from `model.learner.widths` (L3):

| value | how it is bounded | s16x1 | s24x3 |
|---|---|---|---|
| a count | at most 2^32 - 1, unsigned | 32 | 32 |
| a sum | that many windows at an extreme sample | 48 | 56 |
| D | n0 n1 (2^b - 1) at the most, b the sample bits | 81 | 89 |
| D times COEFF_MAX | | 98 | 106 |
| the peak, unsigned | | 80 | 88 |
| a coefficient | COEFF_BITS | 18 | 18 |

Only a count can reach its bound, and a window past it is skipped, FULL. Given that bound no sum, D, product or peak leaves its width. `tests/test_lrn_b_widths.py` reaches every extreme from a written state, both counts at their most and every sum at an extreme, and requires every bit of each width and no more.

## The interface

    Learner(blob, truth, update_frames=LEARN_UPDATE_FRAMES, count_bits=LEARN_COUNT_BITS, epoch=0)
        .update(at)  .commit(at)  .write_shadow(blob)       the host's operations, each taken or refused by name
        .step(frame)                                         the core's record for the frame
        .counters()  .status()  .counts  .sums  .log  .updates  .core

    model.run.learning(frames, schedule_records, length, blob, script, update_frames, count_bits, epoch)
        -> (records, truth, outcomes, learner)

The learner makes its core from the blob, so that it sees every frame the core takes. Made, it refuses, after the blob's own names: LEARN_BOUND (`count_bits` outside 1 to 32, `update_frames` outside 0 to the definition's: a smaller value describes a small build, for its benches); then RECORD_FIELD and RECORD_ORDER for the truth. `learning`'s `script` maps a next index, 0 to the stream's length, to a list of operations, each ("update", u), ("commit", at) or ("write_shadow", blob), made in order before that frame is drawn; each is recorded in `outcomes` as (index, operation, argument, the refusal's name or None), and a refused one leaves the run going, as a refused register write leaves the fabric running. A script that is not of that form is refused, RECORD_FIELD.

*A departure from the design, stated, and accepted by the lead on 2026-11-25:* the design's interface handed the learner a core; it takes the blob and makes its core, so that no core can have taken a frame its learner did not see, a case no declared name would refuse. Nothing else of the interface changed, and nothing of the definition.

## How the fabric will be held to this

For the parcel that builds it in RTL. The expected words are `model.run.learning`'s for the bench's own script, and `model.learner.widths` for its widths:

1. every score record of every run, word for word; after each commit of a learner's set, a stretch that puts each tap of each channel alone into a score, so every coefficient is a score word, since the shadow cannot be read;
2. after each operation's write, the refusal register of that write's block, equal to the model's outcome;
3. at the end of every run, the two counts, the six counters and the state bits of `lrn_status`, equal to `counters()` and `status()`;
4. the update time from both sides, at the build's most taps and channels and the chain's fastest rate: a commit written at the last clock at which the next index is u + F - 1 is refused, and one at the first clock at which it is u + F is taken.

## The hand-worked vector

`vectors/lrn-b/cases.json`, four cases, each driven through `Learner` with the frames as given and truth records of amplitude 0, which the learner reads for their indexes alone. Every figure was worked by hand, with the sums in each case's "worked" lines, and again by code of the parcel's that imports nothing of the tree (L4).

| case | profile | what it holds |
|---|---|---|
| s16x1-the-tie | s16x1 | D = (262142, 1) and a peak of 2 x 131071, so the second coefficient is exactly a half: 0 to even, 1 away from zero; label 0 BUSY four times; a shadow write and a commit refused while the update is unfinished |
| s16x1-start-and-an-unmade-update | s16x1 | START; an update made with a count at zero, which makes no set; another update refused while the first is unfinished; label 0 free at exactly 2T |
| s24x3-ties-on-three-channels | s24x3 | a peak of 4 x 131071 on channel 1, and three coefficients that are ties, one beside the negative peak |
| s24x3-full-at-a-small-count | s24x3 | FULL twice, at a count width of 2; an update named at the next index itself, with an update time of 0, made and finished at once |

## The tests, and the controls with what each printed

Six files, 162 tests, under both profiles wherever a profile is named (L7).

| file | what it holds |
|---|---|
| `test_lrn_b_support.py` | the rule written a second time, held to every figure of the vector; that `model/learner.py` imports the standard library, the definition and the model alone, and that no string of its code names a truth field but `index` |
| `test_lrn_b_vector.py` | each case word for word: judgements, counts, sums, D, the peak, the set, the outcomes, the counters, the status, every score record; each set the trainer's hand-over of the same windows; the case run with no truth; the brief's first three controls |
| `test_lrn_b_trainer.py` | the three equalities with the trainer: through `learn.trainer.train` on streams it takes whole, at three tap counts and several update indexes; stage E1's own flow, every record, at an update time of 0, and the same blob committed 1, 64 and 256 frames later; and on streams with windows skipped, through `MeanDifference` fed the windows the rule takes. And the rule written a second time against `labelled_windows` |
| `test_lrn_b_isolation.py` | the gate truth-isolation, restated (`test_gate_truth_isolation__*`), and its controls (`test_control_truth_isolation__*`) |
| `test_lrn_b_counts.py` | every name: each window condition and its boundary, the order of the window checks where two or three hold, FULL at a small width and at 32 from a written state, a truth index at the field's most and one past it, a bool where an index is asked, a record at index 0 judged when the learner is made, every refusal of every operation and their order, the learner made, `learning`'s script; each condition removed alone; the snapshot; the finish to the frame; the outcome published at the finish; `learning` through the injector recording three refused operations at one index and running on, equal to the support's driver record for record |
| `test_lrn_b_widths.py` | the widths, and the extremes from a written state |

**The controls, each with what the same check printed** (L8). Each is a subclass, a wrapper or a patched copy made inside the test; none is a change to the shipped code.

| control | the broken thing | what the check showed |
|---|---|---|
| the brief's 1: rounding the other way | `_quantise` half away from zero | case 1: the learner's set [[131071, 1]], the trainer's hand-over [[131071, 0]]; case 3: [[1, -500], [131071, 2], [-3, -131071]] against [[0, -500], [131071, 2], [-2, -131070]] |
| 2: the last window before an update dropped | the update made before the windows of its own index are judged | case 1: counts [1, 4], D [229374, 1], set [[131071, 1]] where the vector's is [[131071, 0]] |
| 3: a label-0 window the trainer refuses, taken | label 0 of 4 in case 1 (BUSY); label 0 of 1 in case 2 (START) | case 1: counts [2, 5], set [[131071, -2]]; case 2: the first update made, with set [[131071, -43690]], where the learner's makes no set, and count0 2 |
| 4: a learner reading the amplitude or the pulse id | records whose field has one value are not labels | the learner, under a copy of the truth with one record's amplitude or pulse id changed: no record differs and the counters are equal; the one reading the field: the first record that differs is 1300, the commit's, and the counters differ. Both fields, both profiles |
| 5: a commit at an index no one named | the named commit moved one frame late, one early; a commit the learner makes itself at its finish | the real run's first difference from the frozen model at 1300, 1299 and 1164 respectively |
| 6: the same samples, other truth | an update and no commit; and with a commit | no record differs under any truth; with the commit, the first difference from the frozen model is at 1300, the commit's |
| truth reaching a score with no commit | the frame at a truth index changed by one | the first difference at 201: the frame is 200, and the start set's newest coefficient is `e0`'s last sample, 0 |
| each window condition removed alone | START; BUSY on label 0; BUSY on label 1 from before, from after; FULL | count0 4 and START 0; count0 5 and BUSY 2; count1 5 and BUSY 3, twice, taking different windows; at a width of 2, counts 5 and 5 where they are 3 and 3 |
| each refusal removed alone | UPDATE_UNFINISHED for an update, a commit, a shadow write; SWAP_SHAPE, SWAP_PENDING, SWAP_INDEX for an update; LEARN_BOUND; RECORD_FIELD; RECORD_ORDER | the operation taken, where it is refused under that name; every other check still in place |
| the snapshot removed | the set made again at the finish from the sums then | another set (the s16x1 case: [[-131071, -131071, -131071, -131071]] where the snapshot's is [[97367, -131071, 97367, -131071]]), and the records differ first at the commit's index |
| the finish a frame early, a frame late | the finish at u + F - 1, at u + F + 1 | commits at u + F - 1 and u + F: [taken, SWAP_PENDING] and [UPDATE_UNFINISHED, UPDATE_UNFINISHED], where the learner's are [UPDATE_UNFINISHED, taken], at update times of 1, 3 and 64 |
| the outcome published when made | the count made at u | counted from index 10, u, where the learner counts from 15, u + F |
| `learning`'s script checks, each removed alone | not a dict; an index past the stream; an undeclared operation | an AttributeError, a run that silently never makes the operation, a KeyError: each not the refusal by name |

**One-place faults beyond the controls** (L9). These were made by a script of the parcel's, `mutate.py`, which is in its scratch folder for the round and **not in the tree**: what it shows can be repeated only by making the same changes by hand. Each fault was made alone in a copy of the tree, and these files were run against it. The shapes it tried, thirty faults in its first two passes: seven window conditions each moved off its boundary (START a frame either way, label 0's BUSY at 2T inclusive and at T, label 1's BUSY inclusive from before and from after, FULL a window late), the counts swapped in D, D in tap order, a window newest first, a count not raised, the finish a frame early, the update made a frame late, the windows judged after the update, `lrn_early` not counted and counted on a taken commit, the running bit while named, SWAP_INDEX off by one and a past index taken, the amplitude read, the order not checked, an unmade update published as made, the delay line a frame longer, `learning`'s operations made after their frame, a refused operation raised, each bound one past the definition's, SWAP_PENDING not checked, the shape checked on three of its fields, and the shadow written when no set is made. **The first pass left one standing:** a `learning` that raised a refused shadow write instead of recording it passed every test, because no test refused an operation through `learning` itself, only through the support's driver. The test of `learning` that records three refused operations was added for it, and the fault now fails it.

**Then the round's verifier, VLRNB, found six more shapes that passed every test,** in a copy, each by a one-place change of its own. None was a wrong answer of the code; each was a test missing. Each now has a test of its own in `test_lrn_b_counts.py`, and the same change, made again by the script, fails it:
1. label 1's FULL checked before its BUSY: fails `test_lrn_b_counts_a_label_1_window_both_busy_and_full_is_counted_busy`;
2. label 0's checks in another order (BUSY before START, FULL before BUSY, FULL before START), on windows where two or three hold: each fails `test_lrn_b_counts_label_0s_order_is_start_then_busy_then_full_where_two_or_three_hold`;
3. `update()` naming SWAP_SHAPE ahead of UPDATE_UNFINISHED: fails `test_lrn_b_counts_an_update_is_refused_unfinished_ahead_of_another_shape_when_both_hold`. Both cannot hold by the operations alone, so that test writes the state: an update set in as named, under another shape;
4. a truth index at the field's most refused (`<=` made `<`): fails `test_lrn_b_counts_a_truth_index_at_the_fields_most_is_taken_and_one_past_it_refused`;
5. `update()` taking a bool as the int it is (`isinstance` for `type`): fails `test_lrn_b_counts_an_update_at_a_bool_is_refused_where_its_int_would_be_taken`. The earlier test passed a bool where its int was a past index, refused anyway;
6. the judgement at next index 0, made when the learner is made, left out: fails `test_lrn_b_counts_a_record_at_index_0_is_counted_start_when_the_learner_is_made`.

**What the six have in common:** an order of two checks where both hold, a value at the edge of a type or a field, and the one judgement made outside a step. The script had tried none of the six. Of their kinds it had tried one edge of the index field, an update's u + F at the field's most, and no order of two checks that both hold. A fault of a shape tried neither by it nor by the verifier is not shown to be seen.

## Limits

Each is stated by the behaviour it concedes. A fault inside one of these passes every test here.

1. **The trainer's equality is by construction.** The learner calls `model.weights.quantise` and `model.weights.pack`, the same two functions `learn.handover.candidate_blob` calls: a fault in either is in both, and every equality test passes. The hand-worked vector is what judges them, and only on its four cases.
2. **The model has frames and no clocks.** `update_frames` is a number it is given. Whether a fabric meets it is the fabric's benches' measurement, at the chain's rate. A fabric fed frames faster is not described by it; by the check at the operation's naming it would refuse commits the model takes, which is seen.
3. **Isolation by what is passed, not a wall.** The learner as written reads `index` alone, and a test reads its source for the other field names. A learner written to read more is caught only by its output, and only for a field the isolation tests' schedules vary.
4. **The learner's own registers depend on the truth**, by design. They are not output records, and the restated gate does not cover them.
5. **No forgetting.** The sums hold every window taken since the learner was made. Stage E2's adaptive and reset models have no form here.
6. **One configuration.** The learner's set is the matched-filter configuration (one filter on every channel, pass, a pool of 1, no shift, a head weight of 1). Under any other running shape an update is refused, SWAP_SHAPE.
7. **A pulse is taken to lie within T frames of its index.** A pulse longer than T, which is a filter shorter than the pulse, puts the pulse's tail into a window judged free, and nothing here sees it. `e0` and `e1` are 64 samples (L5).
8. **FULL at the definition's width is held from a written state**, the counts set to 2^32 - 2 in a test, and at a small width by a run. No run takes 2^32 windows.
9. **The counters are unbounded integers in the model** and 64 bits in the definition. Through the injector a run of 2^64 frames judges at most 2^59 windows (L6); a counter past its most is outside both.
10. **The model has the whole truth before frame 0.** A fabric whose host offers a record after the core's next index has reached it, but before the injector takes its frame, could miss its label-0 window where the model takes it.
11. **One index space.** The model's truth index is the core's index.
12. **A caller that calls the core's own `commit` or `write_shadow`** is not held to UPDATE_UNFINISHED, as `model/run.py` already concedes a core fed directly.
13. **The model writes the shadow whole at u**, where a fabric's write may be spread over the update. Nothing outside tells them apart: the shadow cannot be read, and every write and commit is refused until the finish.
14. **What the tests hold at chosen sizes they hold at those sizes.** The learner is run at update times of 0, 1, 3, 5, 22, 64 and 256 frames; at 1, 2, 4, 16, 40, 48, 64 and 80 taps; and at count widths of 1, 2 and 32. A fault that depends on a value between them is not seen.

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| L1 | Two windows the learner takes share no frame, and are judged at least T apart | COMPUTED | every taken window is free of every other record's span: two label 0 windows are 2T or more apart, two label 1 windows T or more, and a label 0 and a label 1 T or more | a stream of the model's on which two taken windows are judged less than T apart |
| L2 | quantise(D) equals quantise(S1/n1 - S0/n0) for integer D | COMPUTED | S1/n1 - S0/n0 = D / (n0 n1), a factor common to every value and to the peak | `tests/test_lrn_b_trainer.py` and `test_lrn_b_vector.py`, the equality tests |
| L3 | The widths table: sums 48 and 56 bits, D 81 and 89, D times COEFF_MAX 98 and 106, the peak 80 and 88, at count_bits 32 | COMPUTED | abs(S) at most n 2^(b-1), abs(D) at most n0 n1 (2^b - 1), with n = 2^32 - 1; `model.learner.widths`, held by `tests/test_lrn_b_widths.py` | that test |
| L4 | The vector's figures were worked by hand, and again, before `model/learner.py` was written, by a script of the parcel's that imports nothing of the tree, `design_check.py`, which is in its scratch folder for the round and **not in the tree**. The tree's own check of them is `test_lrn_b_support.py`, which works every figure a third way from the frames and indexes alone and holds it | READ | the round's ledger, LRN-B's entry of 2026-11-25 21:00, which is not in the tree, for the hand and the script; `python -m pytest -q -p no:cacheprovider tests/test_lrn_b_support.py` for the third way | a figure of the vector that differs from what `test_lrn_b_support.py` works out |
| L5 | `e0` and `e1` are 64 samples each | READ | `spec/pulses/e0.toml`, `spec/pulses/e1.toml` | those files |
| L6 | Through the injector, records are at least 64 frames apart, so a run of 2^64 frames holds at most 2^58 records and judges at most 2^59 windows | COMPUTED | two windows a record; 2^64 / 64 | arithmetic |
| L7 | The six files are 162 tests, and all pass | MEASURED | `python -m pytest -q -p no:cacheprovider tests/test_lrn_b_*.py`, 2026-11-25 22:05: "162 passed" | a rerun |
| L8 | The controls' outputs in the table above, each as printed | MEASURED | `python -m pytest -q -p no:cacheprovider -s tests/test_lrn_b_*.py`, 2026-11-25 21:27, the lines that begin "CONTROL", on the 142 tests of that hour; the twenty tests added since print nothing | a rerun |
| L9 | The faults of the shapes listed above, and no other shape: thirty in the first two passes, twenty-four failing at least one test at the first, one surviving and one not applying as written; with the test added for the survivor and the one rewritten, those two and four more each failing at least one test. Then the verifier's eight changes for its six gaps, against the 162 tests: each fails the test named for it above, and no change survives | MEASURED | `mutate.py`, a script in the parcel's scratch folder for the round, **which is not in the tree**, run 2026-11-25 21:28, 21:34 and 22:08; the verifier's own changes, in its report VLRNB, which is not in the tree either. Each change is a one-place edit a reader can make by hand and run these files against | a fault of a shape neither tried, that passes: each limit above names one |

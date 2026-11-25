# Stage E2 in software, induced drift: `learn/adaptive.py` and `tests/test_e2l_drift.py`

Written by parcel E2L in round 4, 2026-11-25. Labels are those of [the design](../studies/D0-rough-design.md): MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure on this page is in the register at the end, with the command that prints it, the file it is read from, or the rows it is worked from.

## What this is, and what it is not

The design's stage E2: "Mid-run, the pulse shape or the noise colour changes. Five models see the same stream: frozen; frozen with only its input scaling updated; adaptive; periodically reset; and the matched filter for the new condition. *Shows:* whether adaptation recovers events the frozen model misses, at an equal false-alarm rate." Round 4's plan chose a change of pulse shape (its option B), and **in white noise its direction is known in advance**: the frozen filter keeps the overlap of the old pulse with the new, and the learner converges to whatever is injected ([lrn-a.md](lrn-a.md)). So what this stage measures is how fast, in labelled windows after the change, and how well, the adaptive and the reset models recover against the frozen one.

Two things are here.

1. **Two learners that forget** (`learn/adaptive.py`): round 2's rule, the difference of two class means, unchanged, given only some of its training. `Window` keeps the most recent blocks of training; `Resetting` keeps every block since its last reset and resets at a fixed period.
2. **Stage E2 as a script** (`tests/test_e2l_drift.py`), with a short form the gate runs, a full form the lead runs, and a judge. Its functions for rules 2 to 4 are E1's own, imported from `tests/test_lrn_a_e1.py` and called unchanged; rules 1 and 5 are this file's own, written as E1's are.

**What a pass here is evidence of.** Sensitivity, by D8's authority, for one pair of pulses, one overlap, one noise level, one sample format (`s16x1`), in software. **It is not evidence that any fabric is correct**, and nothing of it ran on the card. The short form's tolerance is wide, 0.063, as E1's short form's is.

**Only the short form has been run.** The full run is the lead's. Every figure here about the full run is COMPUTED or an ESTIMATE, and says so.

## Where it sits

| file | what | imports |
|---|---|---|
| `learn/adaptive.py` | `Window` and `Resetting`: which blocks a learner keeps; a fresh `MeanDifference` over them | `collections.deque`, `learn.trainer` (`MeanDifference`, `train`), `learn.errors`; nothing of `model/`, `spec/` or `stats/` |
| `tests/test_e2l_adaptive.py` | the two learners, under both profiles, against answers worked by plain arithmetic | |
| `tests/test_e2l_drift.py` | the experiment, its judge, the short form, the controls; `--full` and `--judge` | the model, the statistics, `learn/`, and E1's script |
| `vectors/e2l/injection_sets.json` | each form's injection set, hashed before any run | written by code that imports nothing of the project |

`learn/adaptive.py` is held by LRN-A's boundary test like every file of `learn/`: its import list is a row of `MAY_IMPORT` in `tests/test_lrn_a_boundaries.py`, the one row this parcel added to that file, by the lead's leave (the round's ledger, the lead's ruling of E2L's design). It does not name the pulse, open a file or run text, by that test's lists.

## The second pulse

`e1` is made by e0's own recipe (`tools/make_pulse.py`: 64 samples, the Hann window 0.5 - 0.5 cos(2 pi i / 63), a peak factor of 1000, rounding half to even), with the sine of 4 cycles replaced by one half of it plus sqrt(3)/2 of a sine of 8 cycles. The 64 integers are the fact, in `spec/pulses/e1.toml`; its `pulse_id` is 1. Its overlap with e0 is a DECISION: this parcel's proposal, ruled by the lead (P5).

| | e0 | e1 |
|---|---|---|
| sum of squares | 11,811,446 | 11,810,537 |
| norm | 3,436.778 | 3,436.646 |
| largest magnitude | 970 | 1,213, at sample 30 |
| zero samples | nine | nine: 0, 8, 16, 24, 32, 40, 48, 56, 63 |
| sum of e0 x e1 | 5,904,898 | |
| cos(e0, e1) | 0.499949 | |

**Why one half.** The frozen model's efficiency at 0.01 falls from 0.5002 to 0.1224: it misses three quarters of what the e1 filter finds, and is still judged by the statistics (n p (1 - p) is about 430 in the short form, against the floor of 25). The 0.378 to be recovered is six short-form tolerances and thirty full-run ones, so the curve has resolution. And the frozen filter's largest response to a lone e1 is at the truth index + 63, where it is read (P2): its loss is not an artefact of where it is read. That is why the second component is at twice e0's frequency and not e0 shifted in phase: a phase-shifted e0 would have the same overlap at lag 0 and, the design reasoned without computing it, a largest response two or three samples later.

## The experiment

Fixed in the docstring of `tests/test_e2l_drift.py`, and in the round's ledger before any run: E2L's design of 12:26, the lead's ruling after it, and the injection sets hashed at 12:30:57. Profile `s16x1`, sigma 1477, amplitude 1/1, 64 taps, a trial every 128 frames with its pulse at frame 64 of the 128 (E1's layout), a false-alarm probability of 0.01.

| stretch of a part's one stream | frames | what is in it |
|---|---|---|
| training block t, t = 0..15 | 16,384 t to 16,384 (t + 1) - 1 | 128 trials; e0 for t below 8, e1 from 8 on. **The change is at frame 131,072** |
| H, calibration | A = 262,144 to B - 1, B = A + 64 m1 | no injection |
| H, test | B to L - 1, L = B + 128 n | n trials of e1 |

| form | m1 | n | m = m1 + n | L | truth records | seed |
|---|---|---|---|---|---|---|
| the short form, in the gate | 8,000 | 4,000 | 12,000 | 1,286,144 | 6,048 | 2026112701 |
| the full run, the lead's | 200,000 | 100,000 | 300,000 | 25,862,144 | 102,048 | 2026112700 |

**The five models.**
1. **frozen**: `weights.matched_filter(profile, e0)`, E0's and E1's blob, never swapped.
2. **frozen, input scaling updated: the frozen model again.** A positive gain on the coefficients is undone by the quantising rule, which scales every set to its peak: the blob for gains 2, 3/2, 7, 1477 and 1/3 is the frozen blob byte for byte. A gain on the score (a head weight of 3) multiplies every score by 3, and a threshold set again at an equal false-alarm rate is multiplied with it: the same injections found, every one. And a change of pulse shape leaves the noise's level as it was, so there is nothing for a scaling to follow. `test_gate_statistics__e2_model_2_...` holds the first two on the short form; its control is a gain of -1, another blob. The third is the noise source's: one sigma for the whole stream.
3. **adaptive**: `learn.adaptive.Window` over the 8 most recent blocks (1,024 truth records, 2,048 labelled windows, E1's short form's count), retrained after every block, its candidate quantised and packed by `learn.handover.candidate_blob` and committed into the model's core at the block's end: sixteen swaps in one stream, the last at A. It starts from the frozen blob.
4. **reset**: `learn.adaptive.Resetting`, every block since its last reset, with a reset before blocks 4 and 12, a period of 8. **A reset drops the learner's blocks and does not swap the detector**; it starts from the frozen blob. Neither choice is ever read in this layout: the next swap after a reset is always a candidate made from the block just added, and the detector holds anything else only on training frames.
5. **the e1 filter**: `weights.matched_filter(profile, e1)`, never swapped: the best a model can do after the change, by D8.

**The snapshots judged**: for each learner the snapshots after blocks 7 to 15, called g = 0 to 8. g = 0 is the last made before the change; g is after g post-change blocks, 256 g labelled windows after the change. Snapshot g carries epoch 8 + g. At g = 4 the two learners hold the same blocks, 4 to 11, and their blobs are equal: a test holds that.

**Where the scores come from.** The adaptive model's g = 8 is the core's own records in the stream; every one read must equal the statistics' exact filter on the kept samples. Every other model and snapshot is judged on H by a **replay** (D0 section 4: "a frozen baseline is a second pass over the same stream with the frozen weights"): the statistics' float filter on H's kept samples, exact for integer coefficients, as records of the snapshot's epoch; and the model's core, holding that blob, held to it on the first 256 test trials, as E1 holds its baseline.

## The comparison rules, as a gate

| rule of the design's section 8 | what holds it | its control, and what it showed (P10) |
|---|---|---|
| 1. the injection set is fixed and committed, with its hash, before the run | `vectors/e2l/injection_sets.json`, two digests, worked by code that imports nothing of the project and written in the round's ledger at 12:31, before any run; a run digests its schedule before a frame source is made | eight other sets, each refused `INJECTION_SET` before a frame source was made: the drift a trial early, a trial late, one amplitude, one index, one dropped, one added, the other form's set, none |
| 2. the stream is split by time | the learners are handed frames below A, and at each swap only the frames already drawn; every figure from records at or after A + 63 | records at A + 62, A - 1, a pre-change trial's index + 63 and a post-change training trial's, each refused `TRAINED_ON` by E1's `hits` and `threshold_record`; a held-out truth record handed to the adaptive learner, refused `WINDOW_OUTSIDE_PERIOD` |
| 3. the threshold is set again after every weight change; models are compared at an equal false-alarm rate | every entry's threshold from H's 12,000 signal-free reads under its own weights, naming its epoch; every comparison recounts | six pairings counted at one shared threshold, each refused `UNEQUAL_FALSE_ALARM_RATE`, with 394, 26, 29, 379, 7 and 583 of 12,000 above where an equal rate is 120; the frozen model's threshold on the adaptive's own records, `THRESHOLD_STALE`; reads of two epochs, `THRESHOLD_MIXED` |
| 4. a rate below D10's floor is labelled | E1's `rate_label`: 0.01 in 12,000 reads is twelve times the floor | a part calling a rate of 5e-4 counted is not as stated |
| 5. the reported model is named before the run | the adaptive's g = 8 and the reset's g = 8; `report` refuses any other | the adaptive's best snapshot, g = 7 (1,964 of 4,000 against the named g = 8's 1,907), refused `NOT_THE_NAMED_MODEL`; a part naming another, not as stated |

The in-stream adaptive model changes weights sixteen times. A threshold is set for every epoch a figure is read from (epoch 16 in the stream, and each replay's); no figure is read from the others, which lie wholly in training.

## What the short form found, beside what was predicted

The prediction is first order and judges nothing: the weights of a learner over N records, a fraction f of them e1, are (1 - f) e0 + f e1 plus noise of variance 2 sigma^2 / N a tap, and their deflection against e1 is <s, e1> / (sigma sqrt(|s|^2 + 128 sigma^2 / N)) with s = (1 - f) e0 + f e1 (P6). The measurement is one run under one seed (P7, P8).

| g | windows after the change | adaptive: predicted | measured, of 4,000 | reset: predicted | measured, of 4,000 |
|---|---|---|---|---|---|
| 0 | 0 | 0.1197 | 504, 0.1260 | 0.1172 | 483, 0.1207 |
| 1 | 256 | 0.1692 | 685, 0.1713 | 0.2017 | 856, 0.2140 |
| 2 | 512 | 0.2310 | 943, 0.2357 | 0.2738 | 1,096, 0.2740 |
| 3 | 768 | 0.2997 | 1,216, 0.3040 | 0.3277 | 1,334, 0.3335 |
| 4 | 1,024 | 0.3663 | 1,446, 0.3615 | 0.3663 | 1,446, 0.3615 |
| 5 | 1,280 | 0.4217 | 1,658, 0.4145 | 0.4252 | 1,667, 0.4168 |
| 6 | 1,536 | 0.4605 | 1,860, 0.4650 | 0.4601 | 1,785, 0.4462 |
| 7 | 1,792 | 0.4823 | 1,964, 0.4910 | 0.4729 | 1,854, 0.4635 |
| 8 | 2,048 | 0.4896 | 1,907, 0.4768 | 0.4795 | 1,907, 0.4768 |

The frozen model found 487 of 4,000 (0.1217; D8 at its deflection on e1, 0.1230, -0.15 se, INSIDE; against the e1 filter's figure, -24.20 se, OUTSIDE). The e1 filter found 2,034 (0.5085; +0.45 se, INSIDE). Every one of the twenty entries is INSIDE its own D8 figure. The named gains over the frozen model: the adaptive's g = 8 +0.3550, standard error 0.0167, 21.2 standard errors; the reset's g = 8 +0.3550, 0.0169, 21.1. Its integers predict +0.3634 and +0.3520.

**Read with its limits.** The curve follows its prediction: the reset model leads while the adaptive still remembers e0 (g = 1 to 3), they meet at g = 4, and the adaptive is ahead at g = 6 and 7. At g = 8 both found 1,907 of 4,000, from different blobs; the reset's prediction there is 0.0101 below the adaptive's, and **at this tolerance the short form cannot tell two learners 0.01 apart**: against the e1 filter's figure both g = 8 snapshots are INSIDE, -1.57 se, with a tolerance of 0.063. From g = 6 on every snapshot of both is INSIDE that tolerance in this one draw. The full run's tolerance is a fifth of it.

## The controls, with what each printed

| control | the broken thing | what the check showed |
|---|---|---|
| an adaptive model that never swaps | a hand-over that does nothing | on a small plan its 4,864 records equal the frozen model's, every field of every one; the real adaptive's scores differ from the frozen's at 4,608 of the 4,608 records from its first swap. On the short form, a part whose adaptive entries are the frozen model's: a gain of exactly 0, z 0, the verdict FAIL, and NOT AS STATED for four reasons, the first that no record carries a new epoch |
| a comparison at an equal threshold | six pairings at a shared threshold | refused, each with a count that is not 120 (rule 3 above) |
| a figure from trained-on frames | records whose windows reach below A | refused (rule 2 above) |
| another injection set | eight sets | refused, each before a frame was drawn (rule 1 above) |
| the drift one trial early, and late | the schedule moved, handed its own digest so that rule 1 does not stop it first | on the small plan the frozen model sees 15 e0 and 21 e1 trials, the first e1 at 1,984 where the plan says 2,112; one trial late, 17 and 19, the first e1 at 2,240. Each NOT AS STATED |
| an injector that adds e1 a trial early under e0's truth | a wrapper that injects the early schedule and returns the committed one's truth | rule 1 passes it; the frozen model sees e1 first at 1,984 |
| a swap one index late | a hand-over that commits at the index + 1 | the first new epoch at 257 where 256 is named, and every swap's record an epoch behind: not as stated |
| model 2 | a gain of -1 | another blob; it finds 0 of 4,000 where the frozen model finds 487 |
| each snapshot is its named blocks | a window of 7 blocks at g = 3; a reset a block late at g = 5; a reset a block early at g = 8 | each another blob than the part's |
| the judge | twenty changes to the short form's part, each leaving every model's found count as it was | each NOT AS STATED and FAIL; and five changes to the verdict's own conditions, each FAIL with the part as stated |
| the named gain | the verdict's threshold on it raised just past the smaller named gain, 21.1 standard errors | the verdict fails, and nothing else about the part changed |

**Why the frozen model's *found* count is not the drift's check.** One trial in 4,000 moves it by at most 1/4,000, far inside any tolerance. What sees the drift is the frozen filter's response to what was added at each trial: the stream less its noise, exactly, since the run keeps the noise as the injector drew it. That is 1,596,020,322 for an e0 trial and 797,899,764 for an e1 one (P2), and the judge requires 1,024 e0 trials ending at index 131,008 and every later trial e1, from 131,136.

Thirteen faults of this parcel's own, each planted in a copy of the tree, each fail at least one of these tests now. One of them, the gain's sign flipped, passed every test as they first stood, because the verdict read its z-score from the counts and nothing held the gain itself; the short-form test now holds every gain to the two counts' difference and to its prediction (P11).

## The full run, which is the lead's

    python tests/test_e2l_drift.py --full --out e2-part.json
    python tests/test_e2l_drift.py --judge e2-part.json

One part, 25,862,144 frames, seed 2026112700, its file and the judge's output to go under `docs/studies/e2/`. An ESTIMATE of 8 to 13 minutes of one core (P9). It keeps H's samples and the whole stream's noise, 2 bytes a frame: about 51 MB and 52 MB. The named figures are those of the short form, at a fifth of its tolerance: at the full run's 0.0126, the first-order curve puts only the adaptive's g = 8 inside the e1 filter's figure, and that only on the average (its expected deviation is -3.3 standard errors, so a correct build is outside about a quarter of the time: [lrn-a.md](lrn-a.md)'s limit 2 again); the reset model is not expected inside at any g.

## Limits

Each is stated by the behaviour it concedes. A fault inside one of these passes the gate.

1. **One noise level, one pulse pair, one overlap, one amplitude, `s16x1`**, white noise, the arrival time known, and the learners told the filter's length and the alignment (lrn-a's limit 13). Under `s24x3`, a scaling with a gain a channel would weight the channels and be another filter; it is not defined or run here.
2. **Every snapshot is judged on one held-out stretch after the last training block, not in the stream's time just after its own swap.** The two estimate the same thing only because the noise is stationary and the pulse constant after the change. A drift that went on changing, or noise that changed, would need a held-out stretch after every swap, each of at least 10,000 signal-free reads for a threshold at 0.01: about 0.8 to 1 million frames a snapshot.
3. **The nine points of a curve share H's noise and injections**: their errors are correlated, and a difference between two snapshots is not two independent figures.
4. **The reset model's phase is one choice**, mid-period. A change just after a reset is its worst case, just before its best; neither is run.
5. **The start and the reset target are never read** (the models, above).
6. **The paired error is uncalibrated here.** LRN-A calibrated its derivation at a correlation of 0.99 between two models; the frozen model and an e1-like snapshot correlate near 0.5. The verdict's named gains are 21 standard errors from zero in the short form, so a miscalibration of tens of percent does not move the verdict; a reported z between two snapshots could be wrong by that much.
7. **The judge takes counts on trust** (lrn-a's limit 6). It holds each part to the plan and to itself, each snapshot's hash and blocks, and the counts adding up; not how each count was made. Only the gate's test makes each snapshot again from the training frames.
8. **Epochs are numbered a detector.** The adaptive's g = 3 and the reset's g = 3 are both epoch 11, and so are the frozen model and the e1 filter, both epoch 0: a threshold of one applied to the other's records is not refused by the epoch, only by the comparison's recount, which a coincidence of counts would pass.
9. **A replayed model is held to the core on 256 test trials of n**; the rest is the statistics' exact filter, as E1's baseline (lrn-a's limit 9).
10. **The drift check is the frozen filter's response at each trial's read index**: samples added somewhere no trial's read reaches, between trials or inside a calibration stretch, are not seen by it.
11. **The verdict's conditions are not each failed alone.** The named gain is (its control above), and so are the flags, the statistics' identity and the core's agreement. A frozen model inside the e1 filter's figure, or a named model with no gain, cannot be made with consistent counts without also failing its own D8 check; the controls that try fail both.
12. **The functions that hold rules 2 and 3 are E1's** and carry E1's limits 17 to 19: they take the hand-over index from their caller, and here the caller is `entry_of`, which passes the plan's A.
13. **`measure` takes a schedule, a set of committed digests, an injector, a hand-over, the window and the reset as arguments**, for the controls and the small plan. The experiment's two forms pass none; the judge holds a part's digest to the committed file, and each snapshot's blocks to the plan's.
14. **The two learners are retrained from their kept blocks at every block**: a learner that kept its sums and subtracted forgotten blocks would be another implementation of the same rule, not tested here.
15. **`learn/adaptive.py` is held by LRN-A's boundary test, whose controls plant their faults in the trainer and the hand-over, not in this file.** Its checks read every file of `learn/` the same way, and this file's row allows `collections.deque`, `learn.trainer`'s two names and `learn.errors`; that a fault planted here would be reported is the same reading of names against lists, not a control run on this file ([lrn-a.md](lrn-a.md)'s limit 12).

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| P1 | sum e0^2 = 11,811,446, sum e1^2 = 11,810,537, sum e0 e1 = 5,904,898, cos(e0, e1) = 0.499949, norm(e1) / norm(e0) = 0.99996; e1's largest magnitude 1,213 at sample 30, zeros at 0, 8, 16, 24, 32, 40, 48, 56 and 63 | COMPUTED | `tests/test_e2l_drift.py`, the setup test, asserts each from `spec.constants`; the lead checked the recipe and the sums by code of its own (the round's ledger, the ruling of E2L's design) | a rerun of the setup test |
| P2 | The frozen filter's noise-free response to a lone e1 is largest at lag 0, 797,899,764, against 1,596,020,322 for e0; the e1 filter peaks at lag 0 for e1; the learned g = 8 peaks there too | COMPUTED | the setup test (the two responses) and `test_gate_statistics__e2_the_frozen_and_e1_filters_peak_where_they_are_read` | a rerun |
| P3 | At sigma 1477 and 0.01: the frozen filter's deflection is 2.326864 on e0 (D8 0.5002) and 1.163271 on e1 (D8 0.1224); the e1 filter's 2.326775 (D8 0.5002); the loss 0.3778 | COMPUTED | the setup test asserts the two deflections on e1 and their D8 figures; the one on e0 is E1's (lrn-a.md, row L1); the loss is their difference | a rerun |
| P4 | The short form's tolerance against the e1 filter's figure is 0.0628 and a full part's 0.0126 | COMPUTED | the setup test, by `stats.tolerance.tolerance` at (121/12001, 4,000, 12,000) and (3001/300001, 100,000, 300,000) | arithmetic |
| P5 | The experiment's choices: e1 and its overlap; the 16 blocks of 128 trials and the change at block 8; the window of 8 blocks; the reset before blocks 4 and 12; the snapshots g = 0 to 8; replay on one held-out stretch; one core in the stream; the reset without a swap; the verdict's conditions; the seeds 2026112700 and 2026112701; the sizes of H | DECISION | E2L's design, the round's ledger 2026-11-25 12:26, approved by the lead after it with seven answers | the lead or the owner deciding otherwise |
| P6 | The first-order curve of the table above, both learners, g = 0 to 8 | COMPUTED | the design's script, `predict.py`, in the round's scratch folder and not in the tree; the formula is written above, and a reader repeats it from the two pulses' integers | the formula worked again |
| P7 | The short form, seed 2026112701: the frozen model 487 of 4,000, the e1 filter 2,034; the eighteen snapshots' counts of the table above; every entry INSIDE its own D8 figure; the named gains +0.3550 (se 0.0167, z 21.2) and +0.3550 (0.0169, 21.1), predicted +0.3634 and +0.3520; the frozen model -24.20 se against the e1 filter's figure | MEASURED | `python -m pytest -q -p no:cacheprovider -s tests/test_e2l_drift.py`, the lines "E2 short form", on the tree with `e1` in its definition (SPEC_SHA256 8444d9d5a25a...), 2026-11-25 12:59 | a rerun, which gives the same counts: the stream is the model's and the rule is exact |
| P8 | What this parcel adds to the gate's first size: its two test files are 29 tests and 30.63 s of the 177.72 s that the run's 1,313 tests took; the first test that needs the short form's one run through the model, 1,286,144 frames, and its evaluation took 24.00 s | MEASURED | `bash verify/run.sh`, 2026-11-25, run id `20261125-130006-108abba`, on a desktop other work shared; the times are each test's `time` in the results file the `model-tests` stage writes under `verify/state/<run id>/model-tests/`, summed by test file | a rerun; the times move with the desktop's load |
| P9 | A full part takes 8 to 13 minutes of one core | ESTIMATE | E1's part, 25.6 to 27.7 million frames with one core in the stream, took 7 to 11 minutes (`docs/studies/E1-software.md`, row E7, READ); this part has the same H, one core, and 20 filter passes and 20 core checks more | the lead's run |
| P10 | The controls' outputs in the tables above | MEASURED | `python -m pytest -q -p no:cacheprovider -s tests/test_e2l_drift.py`, the lines "CONTROL E2", on the tree with `e1` in its definition, 2026-11-25 12:59 | a rerun |
| P11 | Thirteen faults of this parcel's own, each planted in a copy of the tree, each fail at least one test of this parcel's; the gain's sign flipped passed them as they first stood, and is caught since the short-form test holds each gain to its counts | MEASURED | a script in the round's scratch folder, `mutate.py`, 2026-11-25: all thirteen in one run from 13:13 on a copy of the tree as committed, with `e1` in its definition, each failing at least one test; three earlier runs under the scratch harness that put `e1` into the definition in memory before it was merged (the round's ledger, E2L.md, 12:58) found the sign's gap. **It is not in the tree.** Its faults: the window one block short, and one long; the reset a block late, and a block early; the reset dropping nothing; the hand-over an index late; replays at epoch 0; the gain's sign; the adaptive starting from the e1 filter; the verdict without the named gain; the drift check a sample late, and a sample early; each block handed to the learners twice | a fault of another shape that passes: each of the limits above names one |
| P12 | The injection sets' digests: the short form 6,048 records, dde5210c...; the full run 102,048 records, beb3d9ce...; written in the round's ledger at 12:31 before any run | READ | the round's ledger, E2L.md, the entry of 12:31; `vectors/e2l/injection_sets.json`; the rule-1 gate test asserts both against two implementations | a digest that differs |

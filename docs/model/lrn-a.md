# The host's learner of phase A, and stage E1 in software: `learn/`

Written by parcel LRN-A in round 2, 2026-11-23. Labels are those of [the design](../studies/D0-rough-design.md): MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure on this page is in the register at the end, with the command that prints it, the file it is read from, or the rows it is worked from.

## What this is, and what it is not

The design's stage E1: "The coefficients start blank. Labels come from the injector. *Shows:* whether the learner reaches E0's efficiency, and how many labelled windows it takes. *Does not show:* a gain over the classical detector. Matching E0 is the best possible result, by D8."

Three things are here.

1. **A trainer** (`learn/trainer.py`): from labelled windows of the model's own stream to one filter's weights, starting blank.
2. **A hand-over** (`learn/handover.py`): those weights quantised by the definition's rule as the model implements it, packed as a blob, written to a detector's shadow and committed at a named output index.
3. **Stage E1 as a script** (`tests/test_lrn_a_e1.py`), with a short form the gate runs, a full form the lead runs, and a judge. It holds the five comparison rules of the design's section 8 as the gate `comparison-rules`.

**The trainer is not an authority and is not judged bit for bit.** The design's section 2 says so: "How the host arrives at a candidate set is ordinary software, judged by its held-out score and by the same statistics as everything else." What the trainer hands the detector is judged exactly, by the reference model. What the detector then does is judged by `stats/`: D8's formula and its tolerance.

**What a pass here is evidence of.** Sensitivity, by D8's authority, for one pulse (`e0`), one noise level, one sample format (`s16x1`), in software. **It is not evidence that any fabric is correct**: that is bit identity, which has another authority. And the short form in the gate is evidence at a wide tolerance, 0.063, which this page states wherever it gives the short form's result.

**Only the short form has been run.** The full run is the lead's, booked, under seeds named in the round's ledger before any learner ran. Every figure on this page about the full run is COMPUTED or an ESTIMATE, and says so.

## Where it sits

| file | what | imports |
|---|---|---|
| `learn/errors.py` | `LearnRefusal(name, detail)` and its eleven names | nothing |
| `learn/trainer.py` | the rule, and what a labelled window is | the standard library and numpy; nothing of this project |
| `learn/handover.py` | weights to a blob; the blank blob; write the shadow and commit | `spec.constants`, and from the model three names: `weights.quantise`, `weights.pack`, `weights.unpack` |

`learn/` never imports `stats/`: what judges the learner is not in the learner. `model/` and `stats/` never import `learn/`. The gate's `independence` stage knows two packages and not this one, so `tests/test_lrn_a_boundaries.py` holds it: every file of `model/` and `stats/` is imported with `learn` blocked; every file of `learn/` with `stats` blocked, and the trainer with `model` and `spec` blocked too; and the source of `learn/` is read for what it imports and names. It never names the pulse (`PULSES`, `PULSE_IDS`, `scaled_pulse`, `matched_filter`) or the parts that make the stream. **So the learner cannot look the pulse up.** The control plants six faults, one at a time, in a copy, and each is reported in the file it is in (L9).

The learner's refusals are its own, as the statistics' are: they are not part of what a bitstream advertises. A refusal by one of the model's own functions passes through under the definition's name.

## What a label is

A truth record's `index`, as the injector returned it, and nothing else: not the pulse's id, not its amplitude, and never anything the detector produced (the design's row S6). No score record is an argument of anything in `learn/trainer.py`.

With T taps and a truth index j, which is the stream index of the pulse's first sample ([conventions](conventions.md), (a)):

- **a signal window** is frames j to j + T - 1, label 1;
- **a signal-free window** is frames j - T to j - 1, label 0.

One of each for each truth record: N truth records are 2 N labelled windows. A window that leaves the frames the trainer was given is refused, and so is a signal-free window that the record before reaches into.

**What the learner is told beyond its labels:** T, and that a window starts at the truth index. In E1, T is 64, the pulse's length. That is knowledge the learner is given and did not learn.

## The rule

    one update, for a labelled window x with label y:     S[y] <- S[y] + x      n[y] <- n[y] + 1
    the weights, once both counts are at least 1:         w = S[1] / n[1] - S[0] / n[0]

Two sums and two counts. **Blank** is all four at zero, and the weights are then zero. There is no step size and no stopping test: the rule has no parameter but how many windows it is given, and E1 fixes that number before the run.

**Why it reaches the matched filter in white noise.** The mean of the signal windows less the mean of the signal-free ones is exactly what the injector added, whatever the noise's own mean; `tests/test_lrn_a_trainer.py` holds that on a stream with no noise in the way. So the weights are the injected samples plus the difference of two means of N noise windows, each tap with variance 2 sigma^2 / N. D8's best filter is any positive multiple of the injected samples. To first order the cosine between the weights and the pulse is cos^2 = d^2 / (d^2 + 2 T / N), with d the matched filter's deflection, 2.3269 here (L1, L2).

**It departs from one sentence of the design, and not from the design.** The design's section 4, describing phase A, says the host "trains in floating point". This rule does not: its sums are exact integers, because samples are, and its weights are exact fractions handed to `model.weights.quantise`. There is no float between the samples and the model's quantising rule. That was free to take, and it buys two things: the candidate blob is a function of the training windows alone, whatever order they are added in, and a small case can be worked by hand to the last digit (`vectors/lrn-a/rule.json`). It does not depart from the design because the design's section 2 puts the trainer outside the reference model, as "ordinary software", and names what judges it: its held-out score and the statistics. Nothing in the design depends on the host's arithmetic being floating point.

## The hand-over

`candidate_blob(profile, rows)` quantises **every row of the one filter together, as one set** (`model.weights.matched_filter` does the same), and packs the matched-filter configuration: one filter reading every channel, the rectifier passing, a pool of 1, no shift, a head weight of 1. `hand_over(core, blob, at)` writes the shadow and commits at `at`: every output before `at` carries the old epoch and the old weights, every output from `at` on the new (`model.weights.Store`). `tests/test_lrn_a_handover.py` holds the swap between two filters that are both not blank, under both profiles, against the statistics' float filter, which is exact for integers.

**The blank blob cannot come from the quantising rule.** `model.weights.quantise` refuses a set of zeros: it has no peak to scale. So `blank_blob` packs zeros directly, and a learner that returns blank weights cannot be handed over at all. E1's first control turns on this.

## Stage E1

The experiment is fixed in the docstring of `tests/test_lrn_a_e1.py`, and was fixed in the round's ledger before any learner ran. In short, for the profile `s16x1`, noise of sigma 1477, the pulse `e0` at amplitude 1, where D8 gives one half:

| stretch of a part's one stream | frames | what is in it |
|---|---|---|
| training | 0 to A - 1, A = 128 N | N trials, the pulse every 128 frames from frame 64; the detector runs blank, epoch 0 |
| calibration | A to B - 1, B = A + 64 m1 | no injection |
| test | B to L - 1, L = B + 128 n | n trials, laid out as the training ones |

**The split by time (rule 2).** The learner is handed the frames below A and the truth records below A. When the detector's next output is A, the candidate is made, quantised, packed and committed **at A**; the frame at A has not been drawn from the stream at that moment, and a test holds that. Every figure is read from a record at or after A + 63, a score whose whole window is held-out frames, and reads are 64 apart, so no two read windows share a frame.

**The threshold, set again after the weight change (rule 3).** E0's threshold was D8's own, because its coefficients were known. A learner's are not. E1 measures its threshold from the m = m1 + n signal-free scores of the held-out stretches, with `stats.recovery.threshold_from_scores`, at a false-alarm probability of 0.01. A threshold here is a record that names the weight epoch of the scores it was measured from, and counting refuses records of any other epoch. The model's own epoch field is the witness.

**How the threshold's error enters the tolerance.** Through the statistics' own term and no arithmetic of this parcel's: `stats.tolerance.check_efficiency(found, n, pfa_effective, d, m)`, which adds roc_slope^2 pfa (1 - pfa) / m to the binomial variance and takes its expectation at `pfa_effective` = (k + 1) / (m + 1), not at 0.01.

| | n injections | m signal-free scores | k | pfa_effective | binomial se | threshold se | total se | tolerance, 4 se | catch margin, 8 se |
|---|---|---|---|---|---|---|---|---|---|
| the short form | 4,000 | 12,000 | 120 | 0.0100825 | 0.00791 | 0.01355 | 0.01569 | 0.0628 | 0.1255 |
| a part of the full run | 100,000 | 300,000 | 3,000 | 0.0100033 | 0.00158 | 0.00272 | 0.00315 | 0.0126 | 0.0252 |
| E0's part, for comparison: a known threshold | 200,000 | none | | 0.01 | 0.00112 | 0 | 0.00112 | 0.0045 | 0.0089 |

**The measured threshold is the larger part of the tolerance at both sizes, and a part of E1 is 2.8 times as wide as a part of E0 on the same 25,600,000 held-out frames** (L3). That is the price of not knowing the coefficients. For a fixed number of held-out frames the total is least when m is about three times n, which is why a part has 100,000 injections and not E0's 200,000 (L4).

**The floor of row D10 (rule 4).** Ten expected false alarms: for m scores, a false-alarm probability below 10 / m, which is 8.3e-4 for the short form and 3.3e-5 for a full part. E1 states one rate, 0.01: twelve and three hundred times its floor. A rate below the floor is labelled `EXTRAPOLATION`, and a part that calls such a rate counted is not as stated. The m scores are a filter length apart, so D10's caveat about neighbouring scores does not apply to them.

**The result, for the model named before the run (rule 5).** Four things, and the second and third are what "inside" means:

1. the number: found / n at the measured threshold;
2. **against D8 for what the learner produced**: the check above at the deflection of the injected samples against the integers of the learned blob. A badly trained filter passes this: it is judged against its own prediction. It says the instrument counts right;
3. **against E0's efficiency**: the same check at the matched filter's deflection. **"The learner reaches E0's efficiency" means INSIDE here, and nothing else.** A filter that learned nothing is OUTSIDE here and INSIDE at 2;
4. against E0's matched filter on the same held-out frames: the paired cost, below. Reported, and not in the verdict.

The verdict is PASS when the parts are the stated experiment, no record carries a flag, every score read equals the statistics' exactly, every part is INSIDE at 2, the baseline is INSIDE on every part, and the named part is INSIDE at 3. The curve's other counts are not required to be inside at 3: at small counts they are not expected to be.

**The baseline, at an equal false-alarm rate.** E0's matched filter on the same held-out frames, at its **own** threshold measured the same way from the same positions. The comparing function recounts each model's signal-free scores above the threshold it is counted at and refuses unless each count is the same k of the same m. The baseline's scores are the statistics' float filter's, which is exact for integer coefficients; the model's core is held to them on the first 256 test trials of each part, and on every score read for these same integers by E0's own gate, on E0's stream.

## The comparison rules, as a gate

| rule of the design's section 8 | what holds it | its control, and what it showed (L10) |
|---|---|---|
| 1. the injection set is fixed and committed, with its hash, before the run | `vectors/lrn-a/injection_sets.json`: seven digests, worked by code that imports nothing of the model and written in the round's ledger at 14:08:39, before `learn/` existed. A run digests the schedule it is about to use **before a frame is drawn** and refuses on any difference | eight other sets, each refused as `INJECTION_SET` before the frame source was made: one amplitude changed; one index a sample later; one a sample earlier; one injection dropped; one added; another part's set; the test trials 64 frames late; none at all |
| 2. the stream is split by time | the learner is handed frames below A; counting refuses a record below A + 63 | a record with one training frame in its window, one wholly of training frames, and a training trial's own: each refused, `TRAINED_ON`; a held-out truth record handed to the trainer: refused, `WINDOW_OUTSIDE_PERIOD` |
| 3. the threshold is set again after every weight change; models are compared at an equal false-alarm rate | a threshold names its epoch; the comparison recounts | the blank detector's threshold kept for the learned filter's records: refused, `THRESHOLD_STALE`; signal-free scores of two epochs: `THRESHOLD_MIXED`; a comparison at one shared threshold: refused, `UNEQUAL_FALSE_ALARM_RATE`, in four pairings |
| 4. a rate below D10's floor is labelled | `rate_label` | a part at a rate with 6 expected crossings that calls it counted: not as stated |
| 5. the reported model is named before the run | the full run's is part 5, 16,384 truth records; `report` takes no choice | the best of six snapshots asked for: refused, `NOT_THE_NAMED_MODEL`; a part file that marks itself reported: NOT AS STATED |

The design names how this gate could pass while testing nothing: "a threshold that happens to give both models the same rate". So the equal-threshold control uses a pair that cannot coincide, the matched filter and its own first half, whose scores are smaller: counted at the matched filter's threshold, 7 of the half filter's 12,000 signal-free scores are above it where an equal rate is 120, and the other way round 554 are. The learned filter and the matched filter are tried too: 76 and 184. Had either been 120, the test says so and does not count that pair as a control.

## What the short form found, beside what was predicted

Every figure about the learner in this parcel's design was a prediction, made before any learner had run. This is the first measurement, and it is one run under one seed.

| | predicted, before any run (L2) | measured, the short form (L5, L6) |
|---|---|---|
| the cosine of the learned filter with the pulse, N = 1,024 | 0.98865 | 0.99247 |
| 1 - cos^2 | 0.0226 | 0.0150 |
| D8 for the learned integers, at a false-alarm probability of 0.01 | 0.4897 | 0.4932 |
| short of the matched filter by | 0.0105 | 0.0070 |
| the efficiency | | 1,969 of 4,000 = 0.4923 |
| check 2, against D8 for its own integers at `pfa_effective` | | 0.4944: -0.14 se, INSIDE |
| check 3, against E0's efficiency | INSIDE, at a shortfall of two thirds of a standard error | 0.5014: -0.59 se, tolerance 0.0628, INSIDE |
| the matched filter on the same frames, at its measured threshold | | 1,935 of 4,000: -1.13 se, INSIDE |
| the matched filter at D8's own threshold | | 1,977 of 4,000: -0.75 se of a known-threshold tolerance, INSIDE |
| the paired cost of the learned filter | +0.0105 | -0.0085, with a standard error of 0.0071; its integers predict +0.0070; -2.17 se |

**Read with its limits.** The learned filter came out closer to the pulse than the first-order figure: 1 - cos^2 is two thirds of the predicted value. A direct draw of the rule's error says that is 1.8 standard deviations low, and that about 2% of draws are at or below it (L7): this run's training noise was favourable, and the prediction stands as a prediction. **At this tolerance the short form cannot tell a learner at 0.4897 from one at 0.4932, or either from the matched filter.** What it can tell is a learner that learned nothing, or the wrong thing: the controls below. The paired cost has the wrong sign for a learner that is worse than the matched filter, at 2.2 of its standard errors from what its integers predict; the calibration below says how often a correct pair of filters lands that far out, about 3 times in 100, and the paired cost is not in the verdict.

**The peak.** [The conventions](conventions.md) do not promise where a filter peaks when it is not an exact multiple of what was injected. Measured for the learned blob: a lone, noise-free injection's largest score is at the truth index + 63, where E1 reads it. The same integers the wrong way round peak elsewhere, so the measurement can tell (L6).

## The controls, with what each printed

| control | the broken thing | what the same check showed |
|---|---|---|
| a trainer that returns its starting weights, blank | a subclass whose weights are its starting ones | the hand-over is refused by the model: "QUANTISE_INPUT: an all-zero set has no peak to scale". In E1's own flow, on a small part, nothing is swapped and every record stays at epoch 0 and score 0. The detector left blank, on the short form's held-out frames: 0 of 4,000, -32.0 se against E0's efficiency, OUTSIDE; and NOT AS STATED, for nine reasons |
| the same, from weights that are not zero (the lead's) | one tap of 1, the rest 0, returned unchanged | handed over without refusal, and in E1's own flow on a small part swapped in at A, where the core's score is that tap against its window's oldest sample. On the short form's held-out frames: **44 of 4,000, an efficiency of 0.0110**, its deflection 0.0000, -31.3 se against E0's efficiency, OUTSIDE. As a part it is as stated: only the count says it learned nothing |
| labels shifted by a pulse length | the truth indexes plus 64, and minus 64, handed to the real trainer | 0 of 4,000 each way, deflection -2.3093, -32.0 se, OUTSIDE |
| a blob swapped in one output late | a hand-over that commits at 38 where 37 was named | the first record of epoch 1 is index 38; record 37 carries epoch 0 and the old filter's score, under both profiles. Committed one early, record 36 carries epoch 1 and the new filter's score |
| a run on another injection set | eight sets | refused, each before a frame was drawn |
| a comparison at an equal threshold | four pairings | refused, each with a count that is not 120 |
| the best of several snapshots | part 3 asked for where part 5 was named | refused, and NOT AS STATED |

Two things about these that a reader should know. **The two directions of the shifted labels are one broken learner, not two**: in E1's layout a shift of 64 either way puts each pulse in a window labelled 0 and a stretch of noise in a window labelled 1, the same windows both times, so both give the pulse negated. It is the named control and it is caught; it is not two independent tries. And **the controls' filters are scored by the statistics' exact filter on the short form's kept samples**, not by a second run through the model's core: the one-tap filter is run through the core on a small part, and held to the core on the first 256 test trials (limit 9).

## The paired cost's error, with two measured thresholds

`stats.recovery.paired_cost` gives the cost of one detector against another on the same injections and its standard error **for two given thresholds**. In E1 both thresholds are measured, from the same m positions, and that adds a spread the package's figure does not have. **The term below is this parcel's own derivation, not the statistics package's.**

To first order a measured threshold's false-alarm probability is off by minus (its crossings at the true quantile, less the expected) over m, and the efficiency follows at the ROC's slope. Two filters close to one another cross at mostly the same positions, so most of the two errors is shared and cancels in the difference. With k_a and k_b the positions where each model is above its own threshold, `both` where both are, and s_a, s_b the two slopes:

    se_cost^2 = paired_cost's se^2 + ( s_a^2 k_a (1 - k_a/m) + s_b^2 k_b (1 - k_b/m) - 2 s_a s_b (both - k_a k_b / m) ) / m^2

With equal slopes and equal k the added term is the slope squared times the positions where exactly one model crosses, over m^2. In the short form the two models share 107 of their 120 crossings, and the term is 0.0063 where the package's own figure is 0.0033: **left out, the paired error would be less than half what it is** (L8).

`tests/test_lrn_a_paired.py` calibrates it as `tests/test_stat_tolerance.py` calibrates the tolerance: 2,000 experiments on pairs of Gaussian scores at a correlation of 0.99, each of the short form's own sizes. 649 fall outside one standard error where 635 are expected, and 99 outside two where 91 are; the error with no threshold term puts 1,378 and 826 outside, and the error with the two thresholds taken as independent puts 32 and 0 (L8). The term is also worked by hand on eight positions.

## The full run, which is the lead's

Six parts, one for each count: N = 16, 64, 256, 1,024, 4,096 and 16,384 truth records, which is 32 to 32,768 labelled windows. Each has 200,000 calibration scores and 100,000 test trials: n = 100,000, m = 300,000. Part c runs under seed 2026112500 + c; the short form under 2026112600. **The model that is reported is the last, part 5.** The seeds and the reported model are in the round's ledger, in the lead's entry of 14:08 on 2026-11-23, before any learner had run. No two of these seven streams, or E0's ten, share a word of the generator's cycle (L11).

    python tests/test_lrn_a_e1.py --full --count 0 --out c0.json        (and 1, 2, 3, 4, 5)
    python tests/test_lrn_a_e1.py --judge c0.json c1.json c2.json c3.json c4.json c5.json

A part is 25,600,000 + 128 N frames; the six are 156,395,520 (L12). That is an ESTIMATE of 6 to 8 minutes a part on one core (L19); what the short form adds to the gate is measured, 30 s of test time (L13). One part a process; the parts share nothing. Each keeps its held-out samples, 51 MB, and filters them in pieces of 2^20 frames.

**"How many labelled windows it takes"** is the curve those six parts give. What is predicted, and judges nothing:

| N truth records | labelled windows | predicted cosine | D8 at it | short of the matched filter by |
|---|---|---|---|---|
| 16 | 32 | 0.63531 | 0.1982 | 0.3020 |
| 64 | 128 | 0.85455 | 0.3677 | 0.1325 |
| 256 | 512 | 0.95680 | 0.4602 | 0.0400 |
| 1,024 | 2,048 | 0.98865 | 0.4897 | 0.0105 |
| 4,096 | 8,192 | 0.99713 | 0.4975 | 0.0027 |
| 16,384 | 32,768 | 0.99928 | 0.4995 | 0.0007 |

The judge prints one reading of the measured curve and names it as a reading: the first count from which every listed count is inside the tolerance of E0's figure. Its resolution is that tolerance, 0.0126.

## Limits

Each is stated by the behaviour it concedes. A fault inside one of these passes the gate.

1. **The rule does not whiten.** A difference of means does not see the noise's covariance. In coloured noise it would converge to the pulse, which is then not the best filter (the design's third limit on D8), and nothing here would say so: E1's yardstick is D8 for white noise. The rule that does whiten is least squares of the label on the window, at the price of a 64 by 64 matrix to estimate. That is stage E2's to meet.
2. **A learner short of the matched filter by less than the tolerance passes check 3.** At a full part's sizes a learner 0.0126 short is passed about half the time, and only one 0.025 short is caught almost always. In the short form those figures are 0.063 and 0.126. The predicted shortfall of the full run's reported model is 0.0007: **the verdict cannot see it, and a PASS will not mean the learner equals the matched filter. It will mean it is not short of it by the catch margin.**
3. **The paired cost is the sharper figure and it is not in the verdict.** Its threshold term is this parcel's derivation, first order in 1 / m, calibrated at one correlation, one rate and one size (L8). A formula right there and wrong at a full part's sizes, or at the correlation of a filter trained on 16 records, would pass.
4. **The threshold term of the tolerance is the statistics' own, with its own limits** ([stat.md](stat.md), limit 3): first order, Gaussian scores, independent signal-free scores, which here means white noise.
5. **Ties.** A part whose count of signal-free scores above its threshold is not k is not as stated, and is not compared; nothing corrects for a tie. The learned filter's scores are large integers and did not tie in the short form. A filter of one tap ties whenever two samples are equal: the lead's control did not tie under this seed, and its test accepts either outcome.
6. **The judge takes counts on trust.** `not_as_stated` holds a part to the experiment and to itself: its blob's hash and deflection are worked again from the coefficients it carries, its counts must add up, its injection set's digest must be the committed one. It does not recompute a count from a stream. A part file edited to counts that agree with one another and sit inside the tolerance is judged as those counts.
7. **The injection set's digest covers the injections, not the noise.** A run on the committed set under another seed is caught only by the judge, which holds the seed, and by two parts sharing a stream's hash.
8. **`measure` takes a set of committed digests as an argument**, for tests on a small part. The experiment's two forms pass none and use the committed file, and the judge holds a part's digest to the file again; but a caller who passes its own digests has a run that rule 1 did not refuse.
9. **A control's filter is not run through the model's core on the short form's stream.** Its scores there are the statistics' exact filter's. The baseline's are too, in every part: the core is held to them on the first 256 test trials, and for the rest by the argument that integer coefficients make the float exact, which E0's gate holds on E0's stream.
10. **The signal-free positions of a full part are held by arithmetic, not recomputed.** On the short form's stream they equal `stats.recovery.signal_free_indexes` for the whole stream, cut at A + 63. That function builds arrays as long as the stream, so on a full part the same arithmetic is used without that check.
11. **One profile.** E1 is `s16x1`. The trainer and the hand-over are tested under both profiles with every channel different; E1 has not been run under `s24x3`.
12. **The boundaries are a test, not a stage.** `tests/test_lrn_a_boundaries.py` concedes what the `independence` stage concedes: an import by a computed name or through `exec`, a module loaded by path, a copied file. Its reading of the source is of names, so the pulse's samples typed in as numbers would pass it.
13. **The learner is told the filter's length and the alignment.** A learner that had to find the pulse's length, or its position inside a longer window, is a different and harder experiment.
14. **The trainer keeps no history.** A window added twice counts twice. E1 gives it each window once, and a test holds the counts.
15. **One swap a part.** The detector goes from blank to one learned filter. A second hand-over in one stream, and what a threshold measured between two swaps means, are not exercised here.
16. **The short form's INSIDE at check 3 is one draw.** At the predicted shortfall a correct build fails it about 4 times in 10,000 on a fresh seed (L14). The seed was fixed before the run.

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| L1 | The matched filter's deflection in E1 is 2.3269, and D8 gives 0.5002 there at a false-alarm probability of 0.01 | COMPUTED | `python -c "import sys; sys.path[:0]=['.','tests']; import test_lrn_a_e1 as E; from stats import theory; print(E.facts()['d'], theory.pd_matched(0.01, E.facts()['d']))"` | a rerun; `tests/test_seam_e0.py`, which works the same figure |
| L2 | The predicted cosines, D8 figures and shortfalls of the table under "The full run", from cos^2 = d^2 / (d^2 + 2 T / N) with T = 64; and for N = 1,024 a predicted 1 - cos^2 of 0.0226 | COMPUTED | `python -c "import math; from stats import theory as t; d=2.3268642; [print(n, round(math.sqrt(d*d/(d*d+128/n)),5), round(t.pd_matched(0.01, d*math.sqrt(d*d/(d*d+128/n))),4), round(t.pd_matched(0.01,d)-t.pd_matched(0.01, d*math.sqrt(d*d/(d*d+128/n))),4), round(128/n/(d*d+128/n),4)) for n in (16,64,256,1024,4096,16384)]"` | the full run's measured deflections; row L7's direct draw |
| L3 | The tolerance table: the two E1 rows and E0's; a full part's tolerance is 2.8 times E0's part's | COMPUTED | `python -c "from stats import tolerance as t; d=2.3268642; a=t.tolerance(121/12001,d,4000,12000); b=t.tolerance(3001/300001,d,100000,300000); c=t.tolerance(0.01,d,200000); print([(x['se_binomial'],x['se_threshold'],x['se_total'],x['tolerance'],2*x['tolerance']) for x in (a,b,c)], b['tolerance']/c['tolerance'])"`; `tests/test_lrn_a_e1.py`, the setup test, asserts the two tolerances | arithmetic; the statistics' own calibration of its threshold term |
| L4 | For a fixed number of held-out frames, n + m is fixed, and 0.25 / n + 2.218 / m is least at n : m = 0.251 : 0.749 | COMPUTED | `python -c "import math; from stats import tolerance as t; v=t.roc_slope(0.01,2.3268642)**2*0.0099; r=math.sqrt(0.25/v); print(v, r/(1+r), 1/(1+r))"` | arithmetic |
| L5 | The short form, seed 2026112600: the learned filter found 1,969 of 4,000 (0.4923); its integers' deflection is 2.3093, D8 there 0.4944, -0.14 se, INSIDE; against E0's efficiency, 0.5014, -0.59 se, tolerance 0.0628, INSIDE; the matched filter found 1,935 at its measured threshold (-1.13 se, INSIDE) and 1,977 at D8's own; the paired cost is -0.0085 with a standard error of 0.0071 (pairs 0.0033, thresholds 0.0063), its integers predict +0.0070, -2.17 se; the two thresholds are 1,493,607,690 and 1,612,638,907, each with 120 of 12,000 above, 107 of them shared | MEASURED | `python -m pytest -q -p no:cacheprovider -s tests/test_lrn_a_e1.py`, 2026-11-23, the lines "E1 short form" | a rerun, which gives the same counts: the stream is the model's and the rule is exact |
| L6 | The learned filter's cosine with the pulse is 0.99247, so 1 - cos^2 is 0.0150; D8 for its integers at a false-alarm probability of 0.01 is 0.4932, 0.0070 short of the matched filter; -0.75 se for the matched filter at D8's own threshold; the learned blob's peak for a lone noise-free injection is at the truth index + 63 | MEASURED | `python -c "import sys; sys.path[:0]=['.','tests']; import test_lrn_a_e1 as E; from stats import theory as t; g,p=E.short(); c=p['d_learned']/p['d_matched']; print(c, 1-c*c, t.pd_matched(0.01,p['d_learned']), t.pd_matched(0.01,p['d_matched'])-t.pd_matched(0.01,p['d_learned']), E.result(p)['baseline_known']['z_score'], p['peak_offset'])"`, 2026-11-23, about 17 s. The cosine is the ratio of two deflections, and the matched filter's own cosine with the pulse is 1 to eleven places (stat.md, R12) | a rerun |
| L7 | A direct draw of the rule's error, 200,000 times at N = 1,024: 1 - cos^2 has a mean of 0.0223 and a standard deviation of 0.178 of its mean; the short form's 0.0150 is 1.8 standard deviations low, and 2.2% of draws are at or below it. The first-order cosine and the drawn mean differ by at most 0.0012 over the six counts, the most at N = 64 | MEASURED | a script in the parcel's scratch folder for the round, `cos_check.py`, 2026-11-23, numpy seed 20261123. **It is not in the tree**: a reader reproduces it with a loop of their own, adding Gaussians of variance 2 sigma^2 / N to the pulse | such a loop finding otherwise |
| L8 | The paired error's calibration: 649 of 2,000 experiments outside one standard error (635 expected, accepted within 83) and 99 outside two (91, within 37), mean z +0.010; with no threshold term 1,378 and 826; with the thresholds as if independent 32 and 0. In the short form the threshold term is 0.0063 and the package's own figure 0.0033 | MEASURED | `python -m pytest -q -p no:cacheprovider -s tests/test_lrn_a_paired.py`, 2026-11-23, numpy 2.2.6, seed 20261123; and row L5's command for the short form's two terms | a rerun; a calibration at another correlation or size |
| L9 | The boundary control: six planted faults, each reported in the file it is in, and a copy with nothing planted is clean | MEASURED | `python -m pytest -q -p no:cacheprovider -s tests/test_lrn_a_boundaries.py`, 2026-11-23, the lines "CONTROL boundaries" | a rerun |
| L10 | The controls' outputs in the two tables above: eight other injection sets refused before a frame source was made; the equal-threshold counts 7, 554, 76 and 184 where an equal rate is 120; the blank trainer's refusal, 0 of 4,000 at -32.0 se, and nine reasons; the one-tap trainer's 44 of 4,000 (0.0110), deflection 0.0000, -31.3 se, with 120 of 12,000 above its threshold; the shifted labels' 0 of 4,000 each way at deflection -2.3093; the late and the early hand-over at indexes 38 and 36 where 37 was named | MEASURED | `python -m pytest -q -p no:cacheprovider -s tests/test_lrn_a_e1.py tests/test_lrn_a_handover.py`, 2026-11-23, the lines "CONTROL" | a rerun |
| L11 | Seventeen seeds, E1's seven and E0's ten; the closest two streams are more than 2^57 words apart on the generator's cycle, and the longest stream is under 2^25 frames | COMPUTED | `tests/test_lrn_a_e1.py`, the setup test, which asserts it from `model.source.GAMMA`; mod-a.md, limit 7, for why the distance is the seeds' difference times the constant's inverse | a rerun |
| L12 | A full part is 25,600,000 + 128 N frames; the six are 156,395,520; the short form is 1,155,072; a part's held-out samples are 25,600,000 of 2 bytes, 51 MB | COMPUTED | 64 * 200,000 + 128 * 100,000 = 25,600,000; 6 * 25,600,000 + 128 * 21,840 = 156,395,520; 128 * 1,024 + 64 * 8,000 + 128 * 4,000 = 1,155,072; the setup test asserts the first three. The pieces of 2^20 frames are `stat_scores_at_reads`'s `chunk` in `tests/test_lrn_a_e1.py` | arithmetic |
| L13 | What this parcel adds to the gate: in one run of its first size, the parcel's five test files were 63 tests and 29.86 s of the 123.60 s that the run's 855 tests took; `tests/test_lrn_a_e1.py` was 21.98 s of that, and the first test that needs the short form's one run through the model, 1,155,072 frames, took 15.05 s | MEASURED | `bash verify/run.sh`, 2026-11-23, run id `20261123-144116-11711d6`, on a desktop other work shared; the times are the `time` of each test in the results file the `model-tests` stage writes under `verify/state/<run id>/model-tests/`, summed by test file | a rerun; the times move with the desktop's load |
| L19 | A part of the full run takes about 6 to 8 minutes on one core, and the six about 34 to 45 core-minutes | ESTIMATE | 156,395,520 frames (L12) at 13.0 microseconds a frame, which is row L13's 15.05 s over 1,155,072 frames, gives 34 minutes; at 17.3, which is E0's short form the same day under more load (512,128 frames in 8.86 s), 45. A part's filtering of its kept samples is not in either figure. No part has been run | the lead's run |
| L18 | The experiment's choices: the six counts, 200,000 calibration scores and 100,000 test trials a part, the short form's 1,024, 8,000 and 4,000, a false-alarm probability of 0.01, the seeds 2026112500 + c and 2026112600, part 5 as the reported model, the core held to the baseline on 256 trials, the floor of ten crossings, and the verdict's conditions | DECISION | the lead, 2026-11-23, the round's ledger: the entry of 14:08 approving LRN-A's design of 14:02 as designed, and naming the seeds. The floor of ten is the design's row D10; z = 4 is stat.md's row R16 | the lead or the owner deciding otherwise |
| L14 | A correct build fails the short form's check 3 with a probability of about 4e-4 on a fresh seed, at the predicted shortfall of 0.0105 | ESTIMATE | `python -c "from stats.theory import q; print(q(4 - 0.0105/0.01569))"`, which prints 4.3e-4: the lower side alone. It rests on row L2's prediction, which row L6's one draw missed by a third | a count over many seeds |
| L15 | Forty-five one-place faults, each made in a copy of `learn/` or of E1's script, each failed at least one test of this parcel's | MEASURED | a script in the parcel's scratch folder for the round, `mutate.py`, 2026-11-23, in two batches. **It is not in the tree** | a fault of another shape that passes: each of the limits above names one |
| L16 | The rule's sums are exact for a sample that fits 32 signed bits and a label of at most 2^31 windows: 2^31 times 2^31 is 2^62, inside a signed 64-bit integer | COMPUTED | `tests/test_lrn_a_trainer.py`, which asserts the bound and that every declared profile's samples fit it | arithmetic |
| L17 | The vectors' expected answers were worked by hand (`rule.json`) and by code that imports nothing of the model (`injection_sets.json`), the second at 14:08:39 on 2026-11-23, before `learn/` or E1's script existed | READ | the round's ledger, LRN-A's entry of that time; the files' own "how_worked" lines; `tests/test_lrn_a_e1.py` checks the seven digests against `model.records.digest` and against the arithmetic written again | the ledger's entry; a digest that differs |

# Stage E3 in software, on real seismic noise: the experiment, its records and its judge

Written by parcel E3S in round 5, 2026-11-25. Labels are those of [the design](../studies/D0-rough-design.md): MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure on this page is in the register at the end. `<scratch>` is the parcel's scratch folder for the round and `<data>` the folder the fetch wrote into, both outside the repository; nothing in them is committed. `<repos>` is the folder that holds the repositories.

## What this is, and what it is not

D0's stage E3, "a recorded stream ... with injections", which D0 left undesigned. Here it is **stage E1 again with one thing changed, the noise**: recorded HHZ counts of four stations of the Southern California Seismic Network, replayed through the model's own source (`model.source.Replay`), with `e0` injected by the model's injector, E1's learner (the difference of two class means) against E0's matched filter for `e0`, each at its own threshold measured from the same held-out signal-free scores, compared at an equal measured false-alarm rate. **The question is whether the learner reaches the matched filter's efficiency on real noise. D8 cannot predict it:** the noise is neither white nor Gaussian nor of one level.

**Neither model whitens, and on coloured noise the matched filter is not the best detector** (D0, the third limit under row D8; LRN-A's limit 1). The comparison is of the two detectors D0's stage E3 names, not of either against an optimum. A learner that comes out AHEAD has not beaten an optimum; one that comes out SHORT has not failed against one.

**Which authority this rests on.** The statistics package: the new judge, `stats/empirical.py`, beside `stats.recovery` and `stats.tolerance`. The scores are the model's. A reading here is evidence about sensitivity, on these records. **It is not evidence that any fabric is correct.** And the gate runs only the short form, on the model's own white noise: the full run on the records is the lead's.

## Where it sits

| file | what |
|---|---|
| [vectors/e3s/rule.json](../../vectors/e3s/rule.json) | the noise rule, frozen before the first request: stations, days, blocks, keep rules, roles, the amplitude rule, the layout, the named model, the seeds |
| [docs/studies/e3/e3requests.py](../studies/e3/e3requests.py), [requests.tsv](../studies/e3/requests.tsv) | the 40 requests made from the rule |
| [docs/studies/d2/fetch.py](../studies/d2/fetch.py) | study D2's fetch, unchanged, which made them; its record is [manifest.tsv](../studies/e3/manifest.tsv) |
| [docs/studies/e3/e3prep.py](../studies/e3/e3prep.py) | the rule applied: D1's miniSEED reader, the blocks, the keep rules, the roles, the calibration and the recordings |
| [vectors/e3s/blocks.json](../../vectors/e3s/blocks.json) | what the prep made: every block's fate, the blocks used in each role with their SHA-256, each station's calibration |
| [docs/studies/e3/e3sets.py](../studies/e3/e3sets.py), [vectors/e3s/injection_sets.json](../../vectors/e3s/injection_sets.json) | the injection sets and their digests, by code that imports nothing of the model |
| [docs/studies/e3/e3noise2021.py](../studies/e3/e3noise2021.py) | the design's forecast from study D1b's 2021 records (below) |
| [stats/empirical.py](../../stats/empirical.py) | the judge |
| [tests/test_e3s_experiment.py](../../tests/test_e3s_experiment.py) | the experiment, the full run's two commands, the short form, rules 1 to 5 as the gate `comparison-rules`, and the named controls |
| [tests/test_e3s_empirical.py](../../tests/test_e3s_empirical.py) | the judge's own tests and its controls on Gaussian scores |
| [tests/test_e3s_noise_rule.py](../../tests/test_e3s_noise_rule.py), [tests/test_e3s_freeze.py](../../tests/test_e3s_freeze.py) | the rule and the prep on inputs made in the test; the freeze |
| [tests/test_e3s_layout.py](../../tests/test_e3s_layout.py) | where the roles fell, day by day, held to `blocks.json`; the experiment's carry seeds held apart (added after VE3S) |
| [tests/test_e3s_entry.py](../../tests/test_e3s_entry.py) | the full run's script started as its docstring says, with `sys.executable` and no shell, on refused argument sets: it runs and refuses, where it had loaded and exited 0 (added after the lead's full run) |

The tests claim the existing gates `comparison-rules` and `statistics`; no row of `tests/gates.toml` is added. Nothing under `model/`, `learn/`, `spec/` or the rest of `stats/` changed.

## The order it was made in, and the walls

1. **The design** in the round's ledger, 2026-11-25 20:57, with its corrections at 21:00, ruled by the lead at 21:02 (approved, every question as recommended).
2. **Wall 1, the freeze**: the rule, the request list, the prep and the scripts they import or run, committed as `acc12ee` at 21:16:39, their freeze hash `ee4c566e8caac274bd2a4c68f6374432fdcc6fdc81ba123121d76592ad39b6cd` written in the parcel's ledger. [tests/test_e3s_freeze.py](../../tests/test_e3s_freeze.py) holds the eight files to it.
3. **The fetch**, from 04:17:14 to 04:21:13 UTC on 2026-11-26 (21:17 to 21:21 local).
4. **The prep**, once, 21:24:13 to 21:26:52, at the freeze commit.
5. **Wall 2**: the manifest, the blocks and the injection sets committed as `cd39f79` at 21:30:34, before any model ran on a record.
6. **The experiment and its judge**, built and tested on the short form. **Wall 3**: they are committed and verified before the full run, which is the lead's.

## The noise rule

**The stations:** CI.MPP, CI.CDM, CI.HDH and CI.SRN, study D3's four, HHZ at 100 samples a second; their coordinates and channel epochs from D3's station answer, held to its SHA-256 and not asked again. **The days fetched:** eight, 2024-01-08 and every eighth day to 2024-03-04. **The days used: the first five**, because the rule fills the roles in time order (below, and limit 16). *Restated after the verifier's pass (VE3S, its (b)2):* this sentence said the eight days put "each weekday once (Monday twice) and eight weeks of weather and ocean" into the experiment. That was the design's intent and is not what the frozen rule does: the 544 blocks a station uses fall on 2024-01-08, 01-16, 01-24, 02-01 and part of 02-09, Monday to Friday, three and a half weeks, and 02-17, 02-25 and 03-04 were fetched and are not used. **The blocks:** each day from 00:00:00 UTC in 131 blocks of 65,536 frames, 655.36 s.

A block is kept only if, in this order, each holds; a block lost is counted under the first it fails ([e3prep.py](../studies/e3/e3prep.py)'s docstring has every number):

1. **continuity**: exactly 65,536 samples, read by D1's reader, of the station's channel at 100 samples a second, inside one channel epoch, each 10 ms after the one before to within half a sample;
2. **not flat**;
3. **events**: SCEDC's own catalogue, every event type and geographic type. A local or regional event of magnitude M at D km excludes [T - 30 s, T + D / 3 + 120 x 2^(max(M, 1) - 1) s] when D <= 50 x 2^(M - 1) km; a teleseism, a row of another type or one with no magnitude, [T, T + 3 h];
4. **launches**: GCAT's entries from Vandenberg's site codes, any vehicle, [T0 - 60 s, T0 + 1,800 s] for a time to the second (to the minute, -120 s and +1,860 s; to the day, the whole day and 1,800 s after). An entry coarser than a day excludes nothing and is named in `blocks.json`, an addition made before the freeze and accepted by the lead;
5. **range**: a calibration block's samples inside 16 bits; a training or held-out block's inside 16 bits less H, the largest of the injected integers, so the injector can never refuse and no sample is clipped.

A station's kept blocks, in time order, are its 16 calibration blocks, then 128 training, then 400 held-out. A station with fewer than 544 would have been refused by name, NOT_ENOUGH_NOISE, with no day added.

**What it keeps out:** the events SCEDC lists, at those magnitudes and distances; the teleseisms it lists, three hours each; GCAT's Vandenberg launches; gaps, tears and overlaps; flat channels; samples 16 bits cannot hold. **What it cannot keep out** (D0, section 2: a recorded stream's content is unknown): events below the catalogue's completeness or not listed; transients no catalogue names (wind, traffic, people at the vault, a mass recentring, a calibration pulse, a sonic boom, a static firing); teleseisms SCSN did not list; launches from other sites; an event whose effect outlasts its interval. Each stays in, in whichever stretch it falls, and is part of the noise both models are judged on. No rule reads the records' loudness but the range rule, which drops only what 16 bits less H cannot hold (four blocks in all, below): a rule that dropped loud stretches would choose quiet noise for the detectors.

## What the fetch and the prep found

The fetch made 40 requests to `service.scedc.caltech.edu` alone, one after another: every one was answered 200, 393,722,439 bytes in all (R1). The prep read 365 events from the eight days' answers and 7 launch intervals near the days, two of them on fetched days; no GCAT entry near the days is coarser than a day (R2). No file was refused by D1's reader, and no block was lost to continuity or flatness. Of each station's 1,048 blocks (R3):

| station | kept | lost to events | to launches | to range | amplitude, of 65,536 | H, the injection's largest integer |
|---|---|---|---|---|---|---|
| CI.MPP | 981 | 59 | 7 | 1 | 3,569 | 53 |
| CI.CDM | 981 | 60 | 7 | 0 | 3,101 | 46 |
| CI.HDH | 969 | 72 | 7 | 0 | 932 | 14 |
| CI.SRN | 952 | 86 | 7 | 3 | 7,465 | 110 |

Every station filled every role. **Where the roles fell**, a station's blocks of each day by role (R20; c calibration, t training, h held-out, u kept and not used, l lost):

| day, 2024 | weekday | CI.MPP c t h u l | CI.CDM c t h u l | CI.HDH c t h u l | CI.SRN c t h u l |
|---|---|---|---|---|---|
| 01-08 | Monday | 16 98 0 0 17 | 16 98 0 0 17 | 16 93 0 0 22 | 16 94 0 0 21 |
| 01-16 | Tuesday | 0 30 101 0 0 | 0 30 101 0 0 | 0 35 95 0 1 | 0 34 94 0 3 |
| 01-24 | Wednesday | 0 0 128 0 3 | 0 0 128 0 3 | 0 0 126 0 5 | 0 0 121 0 10 |
| 02-01 | Thursday | 0 0 131 0 0 | 0 0 131 0 0 | 0 0 128 0 3 | 0 0 131 0 0 |
| 02-09 | Friday | 0 0 40 54 37 | 0 0 40 54 37 | 0 0 51 42 38 | 0 0 54 38 39 |
| 02-17 | Saturday | 0 0 0 131 0 | 0 0 0 131 0 | 0 0 0 131 0 | 0 0 0 123 8 |
| 02-25 | Sunday | 0 0 0 125 6 | 0 0 0 125 6 | 0 0 0 125 6 | 0 0 0 122 9 |
| 03-04 | Monday | 0 0 0 127 4 | 0 0 0 127 4 | 0 0 0 127 4 | 0 0 0 125 6 |

So, at every station: the calibration is the first three hours of 2024-01-08 UTC (16:00 to about 19:00 on Sunday 2024-01-07 in California); training runs from there to 2024-01-16 at about 05:27 to 06:22 UTC; **the named model's 32 blocks are the last of training**, two of 01-08 and thirty of 01-16 at MPP and CDM, all of 01-16 at HDH and SRN; and the held-out stretch begins in the very next block, with no block between, on 01-16 between 05:27 and 06:22 UTC (the evening of Monday 2024-01-15 in California), and runs to 2024-02-09 between 07:27 and 09:49 UTC, about three and a half weeks. 408 to 437 kept blocks a station, all of 02-09's rest and of the last three days, are not used.

**The amplitudes are the calibration rule's** (below): at each station the matched filter's response to the injected integers first reaches the 99th percentile of its own scores on the 16 calibration blocks above their median, which on Gaussian noise is the amplitude where it finds about half the injections.

## The sample format: HHZ alone in `s16x1`, by a fixed shift of zero bits

- **Why `s16x1`:** E1's profile, so the noise is the only change from E1 (LRN-A's limit 11: E1 has not been run under `s24x3`). Study D1b's 2021 files at these four stations needed 11 to 14 bits.
- **What a shift of zero loses:** nothing of the samples; **range**, so a block with a sample past 16 bits less H is lost to rule 5 (four blocks in all, R3), which leans the noise a little toward what 16 bits hold. HHN and HHE are not used.
- **Any other shift** would cost more: a right shift adds rounding noise and coarsens a pulse whose largest integer is 14 at HDH; a left shift leaves every noise sample a multiple of the shift while injected samples are not, a mark a detector could read.
- **No front end:** a first difference was tried on D1b's 2021 files and trades red noise for blue (below).

## The amplitude rule

On a station's 16 calibration blocks, the scores of E0's matched filter (the integers of `model.weights.matched_filter("s16x1", e0, (1,))`) at 63 + 64 g inside each block, 16,384 of them; t is `stats.recovery.threshold_from_scores` at 0.01 (k = 163) and med their median. **The amplitude is num / 65,536 for the least positive integer num at which the filter's response to `model.inject.scaled_pulse(e0, num, 65536)` reaches t - med.** The least is found by bisection, exact because the response never falls as num grows (each coefficient has its pulse sample's sign, and each rounded sample moves with num in its own sign); [tests/test_e3s_noise_rule.py](../../tests/test_e3s_noise_rule.py) holds the least on white noise and on a target the response meets exactly. The calibration blocks are read for this and for nothing else.

## The experiment's layout

A part is one station. Its stream for the model is its 128 training blocks then its 400 held-out blocks, each a recording replayed in order by `model.source.Replay`, one at a time, through the injector and one core, wired as E1's.

| stretch | blocks | frames | layout | what is read |
|---|---|---|---|---|
| training | 128 | 8,388,608 | trials of 128 frames, `e0` at frame 64; 65,536 truth records; the detector blank, epoch 0 | the learner's labelled windows, frames below A only |
| held-out | 400 | 26,214,400 | trials of 256 frames, `e0` at frame 192; 102,400 injections | records at A + 63 + 64 g: three signal-free a trial (307,200) and one at the injection (102,400) |

- **The named model is the learner of the last 32 training blocks: 16,384 truth records, E1's named count.** It is made, quantised, packed and committed at A = 8,388,608, the first held-out frame, before that frame is drawn.
- **Reported beside it, not in the reading: the curve**, the learners of the last 2, 8 and all 128 training blocks (1,024, 4,096 and 65,536 records), scored by the statistics' exact filter on the same held-out samples.
- **No window crosses a block's edge**, so a join between two blocks hours or a week apart is never inside a window learned from or read.
- **The baseline**, E0's matched filter, is scored by the statistics' exact filter on the same held-out samples; the model's core is held to it on the first 256 held-out trials.
- **The seeds**, named in the design before any run: the resampling's 2026112610 to 2026112613, a station's index in the order MPP, CDM, HDH, SRN; the carry checks' 2026112630 to 2026112633.

## The judge, `stats/empirical.py`

It imports numpy and the statistics package; nothing of `model/` or `learn/`.

**What it adds to `stats.recovery.paired_cost`**, which takes two hit arrays at two given thresholds and treats injections as independent:

1. **the thresholds' errors**: in every resample each model's threshold is measured again from the resampled signal-free scores;
2. **dependence between scores inside a block, and the spread between blocks**;
3. **each threshold's false-alarm rate measured on held-out signal-free scores of other blocks** (`carry`): from the even-numbered held-out blocks to the odd and back. **The even and odd blocks interleave, so each pair shares a day's conditions:** "carries" says the threshold holds between neighbouring blocks of the same days, which is weaker than its name. It does not say the threshold holds from one day to another. The carry by halves in time, first half against second, is the stronger check, and is reported and not in the verdict;
4. **a reading at an equal measured rate**: REACHES when the cost is within 4 of its standard errors of zero, SHORT when the learner finds fewer by more, AHEAD when it finds more.

**The threshold's own error: resampling whole blocks.** On real noise two assumptions of `stats.tolerance`'s term fail: Gaussian scores, through D8's `roc_slope`, and independent signal-free scores, through pfa (1 - pfa) / m. The density of the scores at the threshold mends the first and not the second; resampling whole blocks mends both, up to a block's length, and needs no slope. So the reading's error is the spread of the cost over 1,000 resamples of the 400 held-out blocks, both thresholds measured again in each. **Reported beside it:** the density method (the ROC's slope read from the ranks of the signal-free scores at k - k/4 and k + k/4, and the first-order term it gives), and the resampling on joins of four blocks, which is larger than the plain one when dependence runs past a block.

**Its stated error, measured on Gaussian scores** at the short form's block shape (64 blocks of 192 and 64), where `stats.tolerance` gives the answer (R10): over 100 repetitions the resampled standard error's mean was 1.011 of se_total, its threshold part 1.014 of se_threshold and its part with the threshold held 0.982 of the binomial; one repetition's figure spreads by about 16%; and the resampled errors put 35 of 100 efficiencies outside one standard error, where a Gaussian would put 32 (an earlier run of 400 put 151, 38%: the resampled error runs a few percent narrow at this size). The density slope at the full run's size came out 15.08 against D8's 14.96, 0.27 of its own standard error away. On scores with an offset shared by each block, the resampled error was 0.03216 against a spread of 0.03556 over 60 repetitions, where the independent formula gives 0.01554 and the density method 0.01308 (R11): the formula does not see dependence, and the resampling does.

**Its refusals,** `EmpiricalRefusal`, a subclass of `StatRefusal`: BLOCKS_SHAPE, TOO_FEW_BLOCKS (fewer than 20 blocks), UNEQUAL_FALSE_ALARM_RATE (a declared threshold that does not give its model k of its own m, or two models at other positions), TRAINED_ON (a held-out block that meets a training block in time or content), and the package's own names where they mean the same.

## The reading, and when the experiment held

**The reported figure, for each station: the named model's paired cost against the matched filter**, the matched filter's efficiency less the learner's on the same 102,400 held-out injections, each at its own threshold from the same 307,200 signal-free scores (k = 3,072), **with its standard error by resampling whole blocks and its reading at 4 standard errors: REACHES, SHORT or AHEAD.** All four stations are reported; none is pooled, dropped or chosen. **SHORT is an answer, not a failure of the experiment.**

**The experiment held at a station only if** (each condition, removed alone, changes the verdict in a test):

1. the part is the stated one: station, plan, blocks and their SHA-256 as committed, every held-out block disjoint from every training block in time and in content (`check_disjoint` on `blocks.json`'s spans), injection set as committed, n, m, k, seeds, resamples, the definition's hash, the learner's counts, the hand-over at A, held-out epochs [1], and counts that add up;
2. no record carries a flag;
3. every score read equals the statistics' exact filter's;
4. the core equals the baseline on the first 256 held-out trials;
5. each model's own threshold gives it k of the same m signal-free scores, by E1's recount and the judge's;
6. each model's threshold carries, both ways between the even and odd held-out blocks, within 4 of its resampled standard errors. Those blocks interleave and share each day's conditions, so this holds the threshold between neighbours, not across days (limit 17).

## The comparison rules of D0's section 8

| rule | what holds it | its control |
|---|---|---|
| 1. the injection set fixed and committed, with its hash, before the run | `vectors/e3s/injection_sets.json`, worked by `e3sets.py` without the model, committed at wall 2; the run digests its schedule before a frame is drawn | six other sets, each refused `INJECTION_SET` before any recording is replayed |
| 2. the stream split by time | the learner is handed frames below A; E1's `hits` and `threshold_record` refuse a record below A + 63; the judge's `check_disjoint` refuses a held-out block that meets a training block | records at three depths into training, refused `TRAINED_ON`; a held-out truth record handed to the trainer, `WINDOW_OUTSIDE_PERIOD`; three held-out blocks that meet a training block, `TRAINED_ON` |
| 3. thresholds set again after the weight change; equal false-alarm rate, never equal threshold | E1's epoch-bound thresholds and `compare_at_equal_rate`; the judge's own recount; the carry | the matched filter and its first half at one shared threshold, both ways: `UNEQUAL_FALSE_ALARM_RATE` from E1's code and from the judge's |
| 4. a rate below D10's floor labelled | E1's `rate_label` | a part calling a rate of 7.4 expected crossings counted: not as stated |
| 5. the reported model named before the run | the design: 16,384 records at every station; `report` takes no choice | another model asked for, a station left out, a station twice: `NOT_THE_NAMED_MODEL` |

## The short form, in the gate

**It cannot fetch, and commits no record: its noise is the model's own `Noise`, sigma 1477 as E1's, written into block recordings and replayed by the same code as the full run.** Blocks of 16,384 frames: 64 calibration, 32 training (4,096 records, all of them the named model), 128 held-out (n 8,192, m 24,576, k 245). Every step is the full run's code (the roles and the amplitude by `e3prep.assign`, the injection set and its digest, `Replay`, the learner and the hand-over at A, E1's rule functions, the judge's resampling, carry and density, the curve, the reading) on a stream whose answer is known: on white noise the learner reaches the matched filter (E1). Its part is held to its own blocks as a station's is held to `blocks.json`: each block's samples as replayed, before the injector, against the hashes of the recordings it wrote (since the lead's first full run; until then this check was skipped for the short form).

Two things differ from the design's short form, each found at its first run (the parcel's ledger, 21:34): **the seed**, 2026112695, because the design's 2026112690 is 1.39e17 words from one of E0's and E1's seeds, under the 2^57 E1's setup test asks; and **128 held-out blocks where the design said 64**, because half of 64 blocks' signal-free scores give a threshold 61 crossings, under the 100 `stats.recovery` asks, and the carry was refused.

**What it found** (R12): the amplitude 65,201 / 65,536; the matched filter 4,112 of 8,192, the learner 4,091; cost +0.00256 with a resampled standard error of 0.00441 (the pairs alone 0.00166), **REACHES**, at a tolerance of 0.01764; both thresholds carry; on joins of four blocks the error is 0.00442. The curve: 256 records SHORT (+0.0569), 1,024 REACHES (+0.0165). The matched filter is +0.44 standard errors from D8 at its own deflection, 2.3148.

**What it does not test, and where that is held:** real miniSEED (D1's reader and its self-test; a file of this parcel's own writing, read back); SCEDC's catalogue text (an answer in its format, written in the test); real noise's colour and its blocks' exchangeability, which only the full run meets.

## The named controls, with what each printed (R13)

| control | the broken thing | what the same check showed |
|---|---|---|
| 1. the learner given windows from the stretches it is judged on | records at A + 62, A - 1 and a training trial's; a held-out truth record; held-out blocks that meet a training block | each refused, `TRAINED_ON`, `WINDOW_OUTSIDE_PERIOD`, `TRAINED_ON`; the first record wholly of held-out frames taken |
| 2. a comparison at an equal threshold | the matched filter's first half at the matched filter's threshold, and the reverse | 24 and 1,134 of 24,576 above where an equal rate is 245; refused, `UNEQUAL_FALSE_ALARM_RATE`, by E1's code and by the judge's |
| 3. a model that finds a stated fraction fewer | the matched filter with tap 20 negated (D8: 0.0778 fewer at Pd one half, 16% of what it finds); the learner of 64 records | 0.0646 fewer (12.9%), se 0.00896, SHORT; 0.1329 fewer (26.5%), se 0.01209, SHORT; each reversed AHEAD; the matched filter against itself REACHES |
| 4. a threshold from one stretch on another | the short form's matched filter, its first 64 held-out blocks' threshold on the next 32; and on 32 blocks of the model's noise at 1.25 times the level | 0.01025 of a stated 0.01001, +0.16 se, CARRIES; 0.03304, where D8's tail gives 0.0314, +8.69 se, DOES NOT CARRY |
| 5. the method where the term is known | Gaussian scores in blocks | the figures of R10, each inside its stated error |
| added: a dependence the formula cannot see | Gaussian scores with an offset shared in each block | the figures of R11 |
| added: each condition of the verdict alone | flags, identical scores, the core, the comparison, the judge, each carry; each field `not_as_stated` holds | each changes the verdict |
| added: the carry's own error where nothing changes | 100 pairs of 32 blocks of the same Gaussian noise | the resampled error 0.949 of the two-sample binomial; 7 of 100 outside two standard errors |
| added: the named model is the last training blocks' | a part of its own, 4 training blocks, the named model the last 2 | the learner's weights are the last 2 blocks' and not all 4's |
| added: the instrument's two checks | the core holding another filter, one score one unit off, another filter's scores | each reported: the core unequal, the scores not identical |
| added: one-place faults in the code | 23 in `e3prep.py`, 14 in `stats/empirical.py`, 11 in the experiment's judge, each in a copy of the tree | R18 |

## The one-place faults tried

Each was made in a copy of the tree and the named tests run on it (R18). The scripts that made them are not in the tree; each fault is one change a reader can make by hand.

- **`docs/studies/e3/e3prep.py`, against `tests/test_e3s_noise_rule.py`, 23:** half a sample's lower edge made strict; the sample count checked for too few only; the flat rule removed; the events rule removed; the launches rule removed; the radius a magnitude wider; the duration below M 1 not floored; a teleseism's interval an hour; an event at latitude and longitude 0 not taken at D = 0; the range rule without H; the training and held-out roles reversed; the amplitude's "reaches" made strictly above; a time to the minute given the second's window; `meets` open at its end; the record's rate not checked; the 30 s before an event dropped; a day's launch without its 1,800 s after; the channel-epoch check removed; the calibration scores read a sample late; NOT_ENOUGH_NOISE never refused; the payload's 16-bit width unchecked; `settled` taking any status; `settled` skipping the file's hash.
- **`stats/empirical.py`, against `tests/test_e3s_empirical.py`, 14:** the reading strict at its edge; a declared threshold not recounted; the signal-free positions not compared; the held threshold ignored; the resampled threshold a rank low; the carry's stated rate k / m; the carry resampling one set only; `check_disjoint` closed at its ends; the refusal names unchecked; too few blocks allowed; the cost's error from one model's efficiency; the cost's sign reversed; the density band one-sided; the density's error without its band's.
- **The experiment's judge in `tests/test_e3s_experiment.py`, against that file, 11:** the carry not in the verdict; the blocks not held to `blocks.json`; the named model taken from the first training blocks; the reading at 2 standard errors; a station left out of the report; the counts not added up; the injection set unchecked; signal-free and injection reads swapped in the split; the core check of nothing; the identical-scores check of nothing; `blocks_disjoint` not recorded.

- **Added after the verifier's pass, VE3S's (c), 16 more, each failing a test added for it in `tests/test_e3s_empirical.py` or `tests/test_e3s_layout.py`:** the reading padded by 0.01, and by 0.0001; the tolerance at half; the catch margin at half; `compare`'s z defaulting to 3; `carry`'s to 8; `carry_both_ways`' back leg on its first leg's seed; the density's band over m for m + 1; its pe = k / m; `_declared` loosened to five crossings; `score_blocks`' bound raised past 2^53; `se_pairs`, `z_score` and `noise_both` each zeroed; the cost's error with ddof 0; the learner's carry on the matched filter's seed.
- **Found by the lead's first full run, 2026-11-25, two faults that no test of the parcel's saw.**
  - **The script had no entry block**, so the docstring's `--full` and `--judge` loaded the file and exited 0, with nothing run. The lead ran `main` through a runner of the lead's.
  - **The part's `blocks_sha256` hashed the samples after injection**, which no recording's hash can equal, so every station's part was NOT AS STATED for that reason alone. The short form skipped the check, and the test of the check held a part to its own field.

  Now the script has its entry block, and `tests/test_e3s_entry.py` starts it. The field is each block's samples as replayed, before the injector, hashed by `e3prep.payload`. The short form holds it to its own recordings, and the test of the check holds a posed part to them. The faults tried for these (R18), each in a copy of the tree:
  - the block removed, and a block that does not exit with `main`'s code, each failing `tests/test_e3s_entry.py`;
  - the field hashed after injection, its first or its last block dropped, its samples hashed big-endian, and the short form's check skipped again, each failing the new test in `tests/test_e3s_experiment.py` (all but the last fail the gate's rule 4 test first);
  - the short form's blocks taken from its stored part's own field: this passes alone, since the new test holds the field to the recordings on disk directly, and fails with the field hashed after injection beside it.

A fault of another shape can pass every test; each limit below names the shapes this page knows of.

## The forecast from 2021, and what the experiment was not shaped to do

Before any record of 2024 was fetched, the design measured what study D1b's 2021 records say (`python docs/studies/e3/e3noise2021.py <folder>`, on D1b's folder of the round of 2026-11-21, `Data/runs/2026-11-21-r1-model/data/LCH/` under the lead's checkout, not in the tree). Its eight files and their SHA-256 as `docs/studies/d1/manifest.tsv` holds them, each recomputed on disk on 2026-11-25:

| file | SHA-256 |
|---|---|
| CI.CDM.HHZ.2021-09-13.mseed | 0fa034433f13b855b160e3c5b22f2e5611804f0011425fd1fccab30a2f5ac51b |
| CI.CDM.HHZ.2021-09-15.mseed | e3d9afb1f696562039adf8ff8ae40294f688c9e901f56a84f83676b04b6cf047 |
| CI.HDH.HHZ.2021-09-13.mseed | 25c168f5871fa945d314cfca96a11492a40d305e9ee7c4074af9d1a9a72f2872 |
| CI.HDH.HHZ.2021-09-15.mseed | f1d8b960030d609f85f8c14c4f0a85de483caa6358439865609ac6c1ff500fca |
| CI.MPP.HHZ.2021-09-13.mseed | 7264f7c70a2c799e965a3ba0bd47e9a616f73f84519e115dea22c430b7012abb |
| CI.MPP.HHZ.2021-09-15.mseed | f6eb623e7f6f9722ad7f3c4735c84c999cdda3495d53071fb14779d21da410a4 |
| CI.SRN.HHZ.2021-09-13.mseed | 063cee37558c6c14aea766c34ee8cc7afc9e34c209e2db53d69273094fd58048 |
| CI.SRN.HHZ.2021-09-15.mseed | 9022bcfd91f196be6cf3c92c92336962f86e26a67c1c92842461e0d16cd3dc06 |

**The levels it measured** (R14): the 64-frame mean, which is what the learner's error carries, varies 4.7 to 23 times as much as the white level that would give the matched filter's threshold at CDM, HDH and MPP, and 1.3 times at SRN. `e0` rejects it (its sum is -6). **Its forecast** (R15, an ESTIMATE: first order, Gaussian, from 100 minutes a station of another year): the learner at 16,384 records falls far short at CDM, HDH and MPP (D8's Pd 0.011 to 0.060 where the matched filter's is 0.22 to 0.64) and comes near at SRN (0.444 and 0.541 against 0.505 and 0.607). A first difference before the format moved that up at some stations and down at others, so the design added no front end. **Nothing of the frozen rule, the amplitudes or the judge was set to move that forecast;** the full run is what measures it.

## The full run, which is the lead's

    python tests/test_e3s_experiment.py --full --station MPP --data <recordings> --out e3-MPP.json      (and CDM, HDH, SRN)
    python tests/test_e3s_experiment.py --judge e3-MPP.json e3-CDM.json e3-HDH.json e3-SRN.json

`<recordings>` is the folder the prep wrote, `<scratch>/rec`, 544 recordings a station; `blocks.json` names each, and a part is held to their SHA-256. A part is 34,603,008 frames through the model's core, 1.25 times E1's part 5; ESTIMATE 10 to 15 minutes a part, about 15 minutes for the four at once (R16). The judge prints each station's counts, cost, error, reading, carries, density, curve and instrument, and its last line is `== E3 SOFTWARE:` with whether the experiment held at every station. Its exit code is 0 only when it held at every station, whatever the readings are.

## Limits

Each is stated by the behaviour it concedes. A fault inside one passes the gate.

1. **The noise holds what the rule cannot name** (above). An uncatalogued event in a held-out block stays in both models' scores, and in the learner's training if it falls there.
2. **Dependence longer than a block, or a condition many blocks share, is not in the error.** The resampling treats the 400 held-out blocks as exchangeable. The four-block join is a reading of longer dependence, not a bound. A storm lasting a day would make the error too narrow and nothing in the verdict would say so.
3. **The resampled error runs a few percent narrow** at the short form's size on Gaussian scores (R10: over 400 repetitions its mean was 0.01541 where the efficiencies spread by 0.01632, 5.6% narrower); at 4 standard errors that moves a reading's edge by about a quarter of one. Nothing here measures it at the full run's size.
4. **A learner short by less than about 8 of the judge's standard errors can read REACHES**, as E1's limit 2: the reading is at 4 standard errors, and one short by exactly 4 is read SHORT about half the time.
5. **Neither model whitens, and the matched filter is not the best detector on coloured noise.** REACHES, SHORT or AHEAD is a comparison of these two detectors on this noise and says nothing of an optimum. **A learner may come out AHEAD**: it learns the injected integers, which at amplitudes as small as HDH's (largest integer 14) are not `e0`'s shape exactly, while the matched filter is `e0`'s.
6. **Four stations, five winter days of 2024 used of the eight fetched (2024-01-08 to part of 02-09, Monday to Friday by their UTC dates, none a weekend's), one pulse, one amplitude a station, one false-alarm rate, one profile, one rule.** *Restated after VE3S:* this limit said "eight winter days". The calibration is a station's first 16 kept blocks of 2024-01-08 UTC, a day that begins at 16:00 on Sunday 2024-01-07 in California (the design wrote "the afternoon of 2024-01-08", which was a day late); the matched filter finds about half elsewhere only where the noise is as it was then.
7. **The injection is counts added to counts**, not a ground motion: no instrument response, no propagation, the same pulse at every station.
8. **The training stretch ends where the held-out one begins, with no block between them.** The named model learns from 01-16 (and two blocks of 01-08 at MPP and CDM), and is judged from the next block on, over 01-16 to 02-09. So the reading is of a learner trained just before its test, on the days nearest it; a learner judged weeks after its training is not tried. *Restated after VE3S:* this limit said "The training stretch precedes the held-out one by up to eight weeks", which was the design's intent and not what the rule does.
9. **The judge takes counts on trust**, as E1's limit 6: it holds a part to its plan, its blocks' SHA-256, its set and its own arithmetic, and does not recompute a score from a stream. A part file edited to counts that agree with one another is judged as those counts.
10. **The rule's numbers are held on inputs made in the tests**, not on SCEDC's answers: a record or a catalogue row of a shape no test has would be read as the code reads it. `blocks.json` records each day's records, samples and any refusal of the reader, so the full run's record shows what was read.
11. **SCEDC's bytes are taken as given**; whether a second request returns the same bytes was not tried. The fetched files and the recordings are not in the tree.
12. **The forecast's amplitude is an approximation of the rule** (its script's docstring says how), and its deflections are Gaussian and first order. It drove two choices of the design, the format and the absent front end, and no figure of the experiment.
13. **The short form's answer is known in advance**: white noise. It tests that every step of the full run's code gives E1's answer where that answer is right, and not what real noise does to it.
14. **E1's rule functions are imported from E1's test file.** A change there changes both experiments' rules together, which is intended, and an E1 test that broke them would break E3's too.
15. **The full run's own path is run in the gate only up to its inputs.** `full_inputs` is held (each station's 528 paths in `blocks.json`'s order, its committed set, its disjoint spans), and `measure` and `evaluate` are the short form's code. What only a part of 528 blocks of 65,536 frames meets, its memory and its time among them, is first seen in the lead's run. That the recordings on disk are the blocks named was checked once, read-only, by the parcel's scratch script, and is held again by the part's own `blocks_sha256`. *Restated after the lead's first full run:* that last clause was not so. Until the fix, the field hashed the samples after injection, which no recording's hash can equal. The short form skipped the check, so the gate could not show the fault. Now the field is each replayed block's samples before the injector, and the short form holds it to its own recordings, read back from disk. The full run's own path was not started by its command until the entry block was added (`tests/test_e3s_entry.py` now starts it, on refused arguments only).
16. **The frozen rule departs from the design's stated intent, and the departure stands.** The design said both that a station's kept blocks are used in time order (16, then 128, then 400) and that eight days every eighth day would spread "eight weeks of weather and ocean" and every weekday through the experiment. Both cannot hold: 544 blocks in time order are the first five days' (the table above). The rule as frozen and hashed before the fetch is the first, and it is not changed after the fetch (the lead's ruling of 21:02, restated after VE3S). So **the experiment's noise is five days from 2024-01-08 to 02-09, weekdays by their UTC dates (01-08's first hours are Sunday evening in California), its held-out stretch spanning three and a half weeks of the calendar; 02-17, 02-25 and 03-04 were fetched and are not used;** what weekends, late February or March would do to the reading is not measured. The design missed the conflict and the lead's ruling approved both; the verifier found it.
17. **The carry check is between neighbours.** Its two halves are the even- and odd-numbered held-out blocks, which interleave, so both halves hold every day's conditions. A threshold that holds within each day and not from one day to another carries by this check. The carry by halves in time is reported beside it, not in the verdict.

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| R1 | The fetch: 40 requests to service.scedc.caltech.edu, every one 200, 393,722,439 bytes, 04:17:14 to 04:21:13 UTC on 2026-11-26 | MEASURED | `python docs/studies/d2/fetch.py docs/studies/e3/requests.tsv <data> docs/studies/e3/manifest.tsv <scratch>/requests.log 1440`, run once under `timeout 1500`; its record is [manifest.tsv](../studies/e3/manifest.tsv), which `tests/test_e3s_noise_rule.py` holds to these figures | that test |
| R2 | 365 events in the eight days' answers; 7 launch intervals near the days; no GCAT entry coarser than a day | MEASURED | `python docs/studies/e3/e3prep.py <data> <scratch>/rec <GCAT's launch list> <D3's station answer>`, run once, 2026-11-25 21:24:13 to 21:26:52; [blocks.json](../../vectors/e3s/blocks.json), held by `tests/test_e3s_noise_rule.py` | that test |
| R3 | The prep's table: kept 981, 981, 969, 952; lost to events 59, 60, 72, 86; to launches 7 each; to range 1, 0, 0, 3; none to continuity or flatness; amplitudes 3,569, 3,101, 932, 7,465 of 65,536; H 53, 46, 14, 110 | MEASURED | the same run; `tests/test_e3s_noise_rule.py` holds each cell to `blocks.json` | that test |
| R4 | The layout: training 8,388,608 frames and 65,536 records; held-out 26,214,400 frames, n 102,400, m 307,200, k 3,072; A 8,388,608; a part 34,603,008 frames | COMPUTED | 128 x 65,536; 128 x 512; 400 x 65,536; 400 x 256; 3n; floor(0.01 m); `tests/test_e3s_experiment.py`, its setup test | arithmetic |
| R5 | The short form: n 8,192, m 24,576, k 245; half of m 12,288, k 122; 2,621,440 frames through the core | COMPUTED | the setup test | arithmetic |
| R6 | The design's seed 2026112690 is 139,218,446,187,459,814 words (1.39e17) from one of E0's and E1's seventeen seeds, under 2^57; 2026112695 and 2026112700 are each more than 2^57 from them | COMPUTED | the setup test of `tests/test_e3s_experiment.py`, which asserts the three inequalities; the count is the one its first run printed when it failed on 2026112690 | arithmetic |
| R7 | On white Gaussian noise at the full run's n and m, `stats.tolerance` gives an efficiency an error of 0.00311 (binomial 0.00156, threshold 0.00269) | COMPUTED | `python -c "from stats import tolerance, theory; print(tolerance.tolerance(3073/307201, theory.q_inv(0.01), 102400, 307200))"` | arithmetic |
| R8 | The design's figures, DECISIONs: the stations, days, block length, keep rules and their numbers, the roles, the amplitude rule, the layout, the named model, the curve, z = 4, 1,000 resamples, the seeds | DECISION | the design in the round's ledger, 2026-11-25 20:57 and 21:00, ruled by the lead at 21:02; [rule.json](../../vectors/e3s/rule.json) | the lead or the owner deciding otherwise |
| R9 | The freeze hash `ee4c566e8caac274bd2a4c68f6374432fdcc6fdc81ba123121d76592ad39b6cd` of the eight frozen files, committed at `acc12ee` before the first request | MEASURED | `tests/test_e3s_freeze.py`; the commit's time and the manifest's first time | that test; a changed byte of a frozen file |
| R10 | The method on Gaussian scores in 64 blocks: the resampled error 1.011 of se_total, its threshold part 1.014 of se_threshold, the held part 0.982 of the binomial, one repetition's spread 16%, 35 of 100 outside one standard error; an earlier 400 repetitions gave 0.992, 0.989, 151 of 400, and a mean error of 0.01541 against a spread of 0.01632; the density slope at the full size 15.08 against 14.96, +0.27 se; the density's stated error 2.124 against its spread of 1.909 over the 100 | MEASURED | `python -m pytest -q -p no:cacheprovider -s tests/test_e3s_empirical.py`, 2026-11-25, the lines "CONTROL e3s method", "CONTROL e3s density" and "CONTROL e3s density's error"; the 400 by the parcel's scratch script `method_calibration.py`, which is not in the tree | a rerun |
| R11 | With an offset of sd 1 shared in each block: a spread of 0.03556 over 60 repetitions, the resampled error 0.03216, the independent formula 0.01554, the density method 0.01308 | MEASURED | the same command, the line "CONTROL e3s dependence" | a rerun |
| R12 | The short form's figures: amplitude 65,201; 4,112 and 4,091 of 8,192; cost +0.00256, se 0.00441, pairs 0.00166, REACHES, tolerance 0.01764; four-block joins 0.00442; the curve +0.0569 SHORT at 256 records and +0.0165 REACHES at 1,024; the matched filter +0.44 se from D8 at d 2.3148 | MEASURED | `python -m pytest -q -p no:cacheprovider -s tests/test_e3s_experiment.py`, 2026-11-25, the lines "E3 short form" | a rerun, which gives the same counts: the stream is the model's and the seeds are fixed |
| R13 | The controls' table, every figure | MEASURED | the same command, the lines "CONTROL e3s"; and for the carry's own error `python -m pytest -q -p no:cacheprovider -s tests/test_e3s_empirical.py`, the line "CONTROL e3s carry's error", 2026-11-25 | a rerun |
| R14 | D1b's 2021 files: the 64-frame mean's spread 4.7 to 22.7 times the white level at CDM, HDH and MPP, 1.3 at SRN; e0's sum is -6 | MEASURED | `python docs/studies/e3/e3noise2021.py <D1b's folder>`, 2026-11-25 20:52 in the parcel's scratch and again from the tree at 21:35, the same bytes; the files by the SHA-256 above; e0's sum by `python -c "from spec import constants as C; print(sum(C.PULSES['e0']))"` | a rerun on those files |
| R15 | The forecast: the learner at 16,384 records D8's Pd 0.011 to 0.060 at CDM, HDH and MPP against the matched filter's 0.22 to 0.64, and 0.444 and 0.541 at SRN against 0.505 and 0.607 | ESTIMATE | the same command; first order and Gaussian, from 2021 | the full run |
| R16 | A full part 10 to 15 minutes, the four at once about 15 | ESTIMATE | E1's part 5, 27,697,152 frames in 7 to 11 minutes ([E1-software.md](../studies/E1-software.md), row E7), times 1.25, and Replay's reading | the lead's run |
| R17 | The gate's cost of this parcel's tests | MEASURED | `bash verify/run.sh`, the run named in the parcel's last commit message; the times of `tests/test_e3s_*.py` in its results | a rerun |
| R18 | One-place faults, each made in a copy of the tree and run against the parcel's tests: 23 of 23 in `e3prep.py` failed a test (21 of 23 at the first pass; the two that passed each got a test before the freeze); 14 of 14 in `stats/empirical.py` (10 of 14 at first; four tests added); 11 of 11 in the experiment's judge (7 of 9 at first, two tests added; then two faults more, of which one, `blocks_disjoint` not recorded, passed until a test was added); and after VE3S, 16 of 16 of its gaps; and after the lead's first full run, 2 of 2 faults of the entry block, and 6 of 7 of the blocks' hash, the seventh passing alone and failing beside another | MEASURED | the parcel's scratch scripts `mutate_prep.py`, `mutate_judge.py`, `mutate_gaps.py`, `mutate_entry.py`, `mutate_blocks.py` and `mutate_blocks2.py`, 2026-11-25 21:13 to 22:02, 22:47 to 22:49, 23:11 to 23:12 and 23:25 to 23:35, their outputs in the parcel's scratch folder; **the scripts are not in the tree**: a reader makes each fault by hand from the list under "The one-place faults tried" | a fault of another shape that passes: each limit above names one |
| R20 | Where the roles fell: the table under "What the fetch and the prep found", every cell; the roles' first and last blocks' times; 408 to 437 kept blocks a station not used | MEASURED | `vectors/e3s/blocks.json`, its `blocks_used` and `lost` by day, as the prep wrote them at its one run; `tests/test_e3s_layout.py` holds every cell and time to it | that test |
| R19 | Study D1b's twelve 2021 files at these four stations need 11 to 14 bits, their samples from -1,673 to 5,962 | READ | [D1b](../studies/D1b-first-look.md), the table under Q5c, the column "bits a sample needs" | that table |

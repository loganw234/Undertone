# Stage E2 in software: the full run

The design D0, section 8, stage E2: "Mid-run, the pulse shape or the noise colour changes. Five models see the same stream: frozen; frozen with only its input scaling updated; adaptive; periodically reset; and the matched filter for the new condition. *Shows:* whether adaptation recovers events the frozen model misses, at an equal false-alarm rate." This is that stage, in software only, with round 4's drift: a change of pulse shape, from `e0` to `e1`, whose overlap with `e0` is 0.4999. **No fabric is in it, and nothing here is evidence about fabric.**

The experiment, its comparison rules and its judge are parcel E2L's, in `tests/test_e2l_drift.py` and [e2l.md](../model/e2l.md). They were fixed before any run: the design and the lead's ruling on it, the injection sets hashed and written in the round's ledger, and the two reported models named. The run is the lead's. This page is the record of the run.

## The result

**PASS: each named model recovers events the frozen model misses.** The judge's verdict line: `== E2 SOFTWARE VERDICT: PASS, each named model recovers events the frozen model misses`.

On 100,000 held-out injections of `e1`, each model at its own threshold measured at an equal false-alarm rate of 0.01 from 300,000 signal-free reads:

| model | found | efficiency | against its own D8 figure | against the e1 filter's figure, 0.5002 | gain over the frozen model |
|---|---|---|---|---|---|
| frozen (E0's filter for `e0`) | 12,339 | 0.12339 | 0.1224, +0.56 se, inside | -119.81 se, outside | |
| the e1 filter | 50,447 | 0.50447 | 0.5002, +1.35 se, inside | +1.35 se, inside | |
| **adaptive, g = 8, named** | 48,796 | 0.48796 | 0.4863, +0.51 se, inside | **-3.90 se, inside** | **+0.36457, se 0.00334, z +109.2** |
| **reset, g = 8, named** | 48,054 | 0.48054 | 0.4785, +0.64 se, inside | -6.26 se, outside | **+0.35715, se 0.00336, z +106.3** |

The tolerance against the e1 filter's figure is 0.01258. **Both named models recover what the frozen model misses**, by about 0.36 of the injections each. The adaptive model also reaches the e1 filter's figure within the tolerance; the reset model does not, at 0.020 below it. That was the design's expectation before the run: the adaptive's g = 8 inside on average, expected at -3.3 standard errors, and the reset model not expected inside at any g ([e2l.md](../model/e2l.md), "The full run").

The curve, g = labelled windows after the change / 256, each snapshot on the same held-out stretch:

| g | adaptive: found | its gain | its predicted gain | reset: found | its gain | its predicted gain |
|---|---|---|---|---|---|---|
| 0 | 10,958 | -0.01381 | -0.01256 (-1.31 se) | 10,605 | -0.01734 | -0.01589 (-1.34 se) |
| 1 | 15,302 | +0.02963 | +0.03087 (-1.09 se) | 18,747 | +0.06408 | +0.06562 (-1.02 se) |
| 2 | 20,695 | +0.08356 | +0.08760 (-2.48 se) | 25,617 | +0.13278 | +0.13640 (-1.79 se) |
| 3 | 28,301 | +0.15962 | +0.16269 (-1.41 se) | 31,206 | +0.18867 | +0.19132 (-1.11 se) |
| 4 | 35,111 | +0.22772 | +0.22943 (-0.66 se) | 35,111 | +0.22772 | +0.22943 (-0.66 se) |
| 5 | 41,460 | +0.29121 | +0.29453 (-1.14 se) | 43,137 | +0.30798 | +0.30499 (+0.90 se) |
| 6 | 45,713 | +0.33374 | +0.33523 (-0.48 se) | 47,256 | +0.34917 | +0.34647 (+0.80 se) |
| 7 | 47,748 | +0.35409 | +0.35486 (-0.24 se) | 47,288 | +0.34949 | +0.34957 (-0.02 se) |
| 8 | 48,796 | +0.36457 | +0.36392 (+0.20 se) | 48,054 | +0.35715 | +0.35612 (+0.31 se) |

Every snapshot of both learners is inside the tolerance of its own D8 figure. **Every measured gain is within 2.48 standard errors of the design's first-order prediction**, made from the two pulses' integers before the run. The two learners are equal at g = 4, where they hold the same blocks, as the design requires. The reset model leads at g = 1 to 3 and again at 5 and 6, and the adaptive leads at 7 and 8: so the first-order curve predicts. The short form measured the adaptive ahead at g = 6, where the first-order curve puts the reset model ahead; it was a draw a twenty-fifth of this one's size.

Beside it, from the same run:
- **The instrument:** no flag raised; the adaptive's reads identical to the statistics package's own filter; the core equal to each replay on the first 256 trials.
- **The drift,** as the frozen model sees it: 1,024 `e0` trials to index 131,008, and 101,024 `e1` trials from 131,136.
- **The experiment** as the file states it: one part, its committed injection set, the reported models named before the run.

The judge's whole output is [e2/judge-output.txt](e2/judge-output.txt), and the part it read is beside it.

## How it was run

- **The commands:** `python tests/test_e2l_drift.py --full --out e2-part.json`, then `python tests/test_e2l_drift.py --judge e2-part.json`, from 14:52:06 to 14:59:50 on 2026-11-25: 7 minutes 44 seconds for the part, against the design's ESTIMATE of 8 to 13. The part exited 0, and the judge printed PASS.
- **The tree:** a `git archive` export of parcel E2L's commit `804c49c04ad91ebaaef546938d8e1e0be963418a`, under the definition with `e1`, 8444d9d5.... The lead's branch did not yet hold `e1`. E2L was merged into it at the merge commit, and nothing the run reads differs between the two: `git diff 804c49c` against the merge, on `spec`, `model`, `stats`, `learn`, `tests/test_lrn_a_e1.py` and the two E2L test files, prints nothing.
- **The seed,** 2026112700, and the injection set's digest, beb3d9ce..., were fixed in E2L's design and in the round's ledger before any run. The judge refuses a part on another set.
- **Stage E1's run was made again in the same minutes, on the same export,** under the same definition ([E1-software.md](E1-software.md)).

*Restated by the lead on 2026-11-25, in round 5:* **it was made a second time, and the part under `docs/studies/e2/` is now the second run's.** Round 5's change to the definition, the learner of phase B (`8ba8c01`), made the judge refuse the first part for its hash, and the gate skipped by name, `E2-RECORD-STALE`. The second run was from 23:07:32 to 23:17:58 on 2026-11-25, on a `git archive` export of round 5's branch at `cbf2e77a937f617726aa7ee09abe92d312df19e8`, under the definition 85e63d4d..., beside stage E1's fifth run. The part exited 0, and the judge printed PASS. **The result is the same:** the part equals the first in every field but `spec_sha256`, and the judge's output is the committed one byte for byte, so each figure of "The result" stands, now under round 5's definition.

## What stands behind it

The parcel passed one verifier pass, on Sonnet, before the run. It found two of the lead's three planted faults and no wrong answer of the parcel's. The fault it missed was a weakened assertion in the control for a drift one trial late; the lead showed, in a copy, that the parcel's own unweakened control fails on a detector blind to a late drift. It reproduced `e1` from its recipe, every first-order prediction from the pulse integers, and every short-form count and figure of the parcel's page. That pass was of the short form; the full run came after it.

## Which authority this rests on

The statistics package: D8, and the tolerance for a count out of 100,000 at a threshold measured from 300,000 signal-free scores. The gains are paired comparisons on the same injections, by the derivation LRN-A wrote for stage E1, which is not `stats/`'s and assumes Gaussian scores. The scores are the model's. **It is a sensitivity result. It is not evidence that any fabric is correct.**

## Limits

1. **Software only.** The fabric's injector knows `e0` alone and refuses `e1` by name, `PULSE_UNKNOWN`: a stated subset of the definition ([source.md](../rtl/source.md), limit 7). Stage E2 on the card needs `e1` in the fabric and a new build.
2. **One part, one seed.** The verdict rests on one draw of each named model.
3. **The named gains' error is uncalibrated here** ([e2l.md](../model/e2l.md), limit 6). LRN-A calibrated the paired derivation at a correlation of 0.99 between two models; the frozen model and an `e1`-like snapshot correlate near 0.5. At z above 100 that cannot move the verdict, but a z between two snapshots could be wrong by tens of percent.
4. **The reset model outside the e1 filter's figure is not a failure.** The verdict asks whether a model recovers what the frozen model misses, not whether it reaches the best filter. A reader who takes "PASS" to mean both models reached the e1 filter misreads it.
5. **The drift's direction is known in advance.** In white noise the learners converge to whatever is injected, so this stage measures how fast and how well, not whether adaptation finds an unknown drift, and nothing here is real data.
6. **Every snapshot is judged on one held-out stretch after the last training block** ([e2l.md](../model/e2l.md), limit 2), and **the nine points of a curve share that stretch** (limit 3): their errors are correlated, and a difference between two snapshots is not two independent figures.
7. **The fifth model is the frozen model again.** By E2L's design, an input scaling is undone by the quantising rule or by the threshold set again at an equal false-alarm rate. It is not a separate row here.
8. **What holds this page's figures:** `tests/test_e2_full_run.py`. It holds the two committed files to their SHA-256 and runs the tree's judge on the committed part, requiring the committed output byte for byte. It does not run the part again.
9. **The result is of one definition.** When `spec/undertone.toml` next changes, the judge will refuse the part for its hash, and the test then skips, by name, `E2-RECORD-STALE`, once it has held that the hash is the judge's only reason. A control in the same file changes one comment line of the definition and requires that skip.

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| G1 | The part and the judge's output under `docs/studies/e2/` are the run's: the part byte for byte, the output with each line end made a line feed | MEASURED | `sha256sum` on the committed files, 2026-11-25; `tests/test_e2_full_run.py` holds both | that test |
| G2 | Every figure of "The result" above | READ | [e2/judge-output.txt](e2/judge-output.txt), line for line | that file |
| G3 | The committed output is what the tree's judge prints for the committed part | MEASURED | `tests/test_e2_full_run.py`, in the gate | that test |
| G4 | The part ran from 14:52:06 to 14:59:50 on 2026-11-25, exit 0, on an export of 804c49c, under the definition 8444d9d5..., and the judge printed PASS | MEASURED | the run's log (`e1e2_runs.out`), kept in the round's folder and not committed; the lead's ledger, round 4, its entry of 15:10 | that log |
| G5 | Nothing the run reads differs between 804c49c and the merge commit | MEASURED | `git diff 804c49c -- spec model stats learn tests/test_lrn_a_e1.py tests/test_e2l_drift.py tests/test_e2l_adaptive.py` against the merged tree, which prints nothing | that command |
| G6 | The seed and the injection set's digest were fixed before any run | READ | E2L's ledger, 12:30 and 12:31, and the lead's ruling, in the round's folder and not committed; `vectors/e2l/injection_sets.json` | the ledger's times |
| G7 | Every measured gain is within 2.48 standard errors of the design's first-order prediction | READ | the judge's output, each snapshot's "predicted" figure | that file |
| G8 | The design expected the adaptive's g = 8 inside the e1 filter's figure on average, at -3.3 se, and the reset model not inside at any g | READ | [e2l.md](../model/e2l.md), "The full run", written before the run | that page's history |
| G9 | A full part took 7 minutes 44 seconds of one core, with seven other processes running | MEASURED | G4's log | a rerun |
| G10 | A second run on 2026-11-25, 23:07:32 to 23:17:58, on an export of cbf2e77 under round 5's definition, 85e63d4d...; the part exit 0; the judge PASS. Its part equals the first in every field but `spec_sha256`, and the judge's output is the committed one byte for byte once its line ends are | MEASURED | the run's log (`reruns_r5.out`) and the lead's `compare_reruns.py`, kept in the round's folder and not committed; the lead's ledger, round 5, its entry of 23:19; `tests/test_e2_full_run.py` holds both files | that log; that test |

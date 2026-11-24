# Stage E1 in software: the full run

The design D0, section 8, stage E1: "The coefficients start blank. Labels come from the injector. *Shows:* whether the learner reaches E0's efficiency, and how many labelled windows it takes." This is that stage, in software only: the reference model as the detector, parcel LRN-A's trainer as the learner, the statistics package as the judge. **No fabric is in it, and nothing here is evidence about fabric.**

The experiment, its comparison rules and its judge are parcel LRN-A's, in `tests/test_lrn_a_e1.py` and `docs/model/lrn-a.md`, and were fixed before any run. The run is the lead's. This page is the record of the run.

## The result

**PASS. The reported model is inside the tolerance of E0's efficiency.** The model that is reported was named before any run: the last part, 16,384 truth records. It found 49,492 of 100,000 held-out injections, an efficiency of 0.49492, against the matched filter's figure of 0.50026: 1.70 standard errors below, inside a tolerance of 0.01258.

The curve, each part under its own seed, the learned filter scored at its own measured threshold on 100,000 held-out injections:

| truth records | labelled windows | seed | found | efficiency | against its own prediction | against E0's figure, 0.5003 |
|---|---|---|---|---|---|---|
| 16 | 32 | 2026112500 | 18,814 | 0.18814 | 0.1907, -1.13 se, inside | -99.24 se, outside |
| 64 | 128 | 2026112501 | 38,385 | 0.38385 | 0.3840, -0.06 se, inside | -37.01 se, outside |
| 256 | 512 | 2026112502 | 44,901 | 0.44901 | 0.4458, +1.04 se, inside | -16.29 se, outside |
| 1,024 | 2,048 | 2026112503 | 48,985 | 0.48985 | 0.4923, -0.78 se, inside | -3.31 se, inside |
| 4,096 | 8,192 | 2026112504 | 50,013 | 0.50013 | 0.4976, +0.82 se, inside | -0.04 se, inside |
| 16,384 | 32,768 | 2026112505 | 49,492 | 0.49492 | 0.4997, -1.51 se, inside | -1.70 se, inside |

"Its own prediction" is what the statistics package's formula D8 gives for the integers that part's learner produced: the judge's check 2. "E0's figure" is what D8 gives for the matched filter: the judge's check 3, and the only one the verdict rests on. The tolerance is four standard errors, 0.01258, with the statistics' own term for a threshold measured from scores.

Beside the curve, from the same run:

- **The baseline.** E0's matched filter, on each part's own held-out stream, at its own threshold measured the same way: inside the tolerance in all six parts (-1.31, +0.92, +0.93, -0.42, +0.88, -1.68 standard errors).
- **The paired cost** of the learned filter against the matched filter on the same injections, each at its own threshold: +0.30800, +0.11931, +0.05418, +0.00910, +0.00288 and +0.00004, the last with a standard error of 0.00081. Each is within 1.03 standard errors of what that part's coefficients predict. It is reported and is not in the verdict.
- **The instrument**, in every part: no flag raised; every score read identical to the statistics package's own filter; the model's core equal to the baseline on the first 256 trials; the peak at the truth index plus 63; 300,000 signal-free scores, at which a false-alarm rate of 0.01 is counted and not extrapolated.

The judge's whole output is `docs/studies/e1/judge-output.txt`, and the six parts it read are beside it.

## How it was run: twice, and why

- **The commands:** `python tests/test_lrn_a_e1.py --full --count c --out c<c>.json` for c from 0 to 5, six processes at once; then `python tests/test_lrn_a_e1.py --judge` on the six files, in the same tree.
- **The seeds** are 2026112500 + c. They were named in the lead's ruling on the parcel's design at 14:08 on 2026-11-23, before the parcel wrote the experiment. Each part's injection set is committed with its hash in `vectors/lrn-a/injection_sets.json`, and the judge refuses a part on any other set.
- **The first run:** that day from 17:02:26 to 17:13:05, on parcel LRN-A's commit `6a2431f5d843114eebbee01dcafb2e9bf9e1e997`, in a worktree of its own, clean before and after; each part ended with exit code 0, and the judge there printed PASS. No part had been run before it, by the parcel or by the lead: the parcel's gate runs the short form, one part of 4,000 injections under a seed of its own, 2026112600.
- **Why there is a second.** Each part carries the SHA-256 of the definition it was run under, and the judge refuses a part of another definition. The first run was on the parcel's commit, whose definition had no register map and none of the fabric's names (round 2's RTL parcels); the round's branch gained them at 17:00:38, two minutes before the run began, and the merge at 17:42:37 put the parcel under that definition. This experiment reads none of what was added. On the merged tree the judge said of the first run's parts: NOT AS STATED, six times, for that hash and nothing else, and FAIL. That is the comparison rule doing what it is for.
- **The second run:** from 17:44:09 to 17:53:08, on the merge commit `9c9da6f0c695b619eb996a22b6f252b65fbf793c`, in a worktree of its own, clean before and after; each part exit 0; the judge there printed PASS. **Every part of the second run equals the same part of the first in all fifty of its fields but one, the definition's hash, and the judge's output is the same, byte for byte.** The six parts under `docs/studies/e1/` are the second run's.

So the result was produced twice from the same seeds, and the second production is the one the tree's own judge accepts.

## What stands behind it, and what was not yet behind it when it first ran

The parcel went past three verifier passes. **The first run was made after the first pass and before the second and third; the second run after all three.** The first pass found no wrong answer in the trainer, the hand-over, the scoring or the judge, and reproduced the learning rule, the tolerance and every figure of the parcel's table by code that imports nothing of the parcel's. What the parcel then changed, in two commits, is a document and two test files; `git diff 6a2431f5d843114eebbee01dcafb2e9bf9e1e997 9c9da6f0c695b619eb996a22b6f252b65fbf793c -- learn tests/test_lrn_a_e1.py` prints nothing, and the second and third verifiers each ran that comparison on their own clones.

## Which authority this rests on

The statistics package: D8, and the tolerance it gives for a count out of 100,000 at a threshold measured from 300,000 scores. The scores are the model's. **It is a sensitivity result. It is not evidence that any fabric is correct, and a bit-identity pass of RTL against the model would not be evidence of it either.**

## Limits

1. **Software only.** The detector is the reference model. D0's stage E1 on the card is another round's.
2. **One seed a part.** Each row is one draw, and the verdict rests on one row, the last. The two runs are one experiment made twice on the same seeds: the second adds no draw, and shows only that the run is the same when it is made again.
3. **Where the curve crosses into the tolerance is not placed by this run.** The part at 1,024 records is 3.31 standard errors low of a tolerance of 4: inside, by the judge's rule, and by a margin one draw does not settle. The judge's own line, "every count from 1024 truth records on is inside the tolerance", is a reading of these six rows at this tolerance's resolution and no more.
4. **A learner short of the matched filter by less than the tolerance passes.** 0.0126 at these sizes. The paired cost is the sharper figure and says the reported model is within 0.0017 of the matched filter at two standard errors; it is reported, not judged.
5. **"Reaches E0's efficiency" is all that is shown.** Not a gain over the matched filter, which D8 says cannot be had here: white Gaussian noise of a known level, one known pulse, a known arrival time.
6. **The learner is the simplest one**: the difference of two class means, exact integer arithmetic, no parameter but the count. D0's "trains in floating point" (section 4) is not what was built; the parcel's design says why, and the lead ruled it.
7. **The noise is the model's own**, sigma 1477, one channel, 16-bit samples. Nothing here is real data.
8. **The threshold is measured after the weight change, on signal-free scores of the new epoch only**, and the false-alarm rate is equal between the two models, not the threshold. Those are D0's comparison rules, held by the parcel's gate `comparison-rules`; this page relies on that gate and does not repeat it.
9. **What holds this page's figures**: `tests/test_e1_full_run.py` holds each committed file to its SHA-256 and runs the tree's judge on the six committed parts, requiring the committed output, byte for byte. It does not run a part again: a part is about nine minutes of one core.
10. **The result is of one definition.** When `spec/undertone.toml` next changes, in any line, the judge will refuse these parts as it refused the first run's, and this page's figures will be those of an earlier definition until the run is made again. The test then holds that the hash is the judge's only reason. **It does not say so in the gate's output**, as this line claimed until the round's closing verifier tried it: its note is printed only when pytest is asked for a passing test's output (`-rA`), and the gate's line for the tests is the same in both cases. After a change to the definition the gate is green on a record of an earlier one, and CLAUDE.md's trap 18 is all that says so.

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| E1 | The six parts under `docs/studies/e1/` are the second run's, each with the SHA-256 it had when that run ended. The judge's output there is the run's with each line end made a line feed: the run's own file was a redirect on Windows and held carriage returns, which no committed file may | MEASURED | `sha256sum` on the committed files, 2026-11-23, when they were put in the tree; `tests/test_e1_full_run.py` holds all seven | that test |
| E2 | Every figure of "The result" above | READ | `docs/studies/e1/judge-output.txt`, line for line | that file |
| E3 | The committed output is what the tree's judge prints for the six committed parts | MEASURED | `tests/test_e1_full_run.py`, in the gate | that test |
| E4 | Two runs of six processes on 2026-11-23, each part exit 0, each tree clean: 17:02:26 to 17:13:05 on commit 6a2431f, and 17:44:09 to 17:53:08 on the merge commit 9c9da6f | MEASURED | each run's own log of times and exit codes, kept in the round's folder and not committed; the lead's ledger entries of 17:13 and 17:57 | those logs |
| E8 | Every part of the second run equals the same part of the first in all fifty fields but `spec_sha256`, and the two judge outputs are equal byte for byte once their line ends are | MEASURED | a comparison of the twelve part files field by field, and of the two outputs, by the lead on 2026-11-23; the first run's files are in the round's folder and not committed | a rerun of either on its commit |
| E9 | On the merged tree the judge refuses the first run's parts for the definition's hash and for nothing else: eight lines of its output differ from the committed one | MEASURED | `tests/test_e1_full_run.py` run in a copy of the tree holding the first run's parts: its second case passes | that test, in such a copy |
| E5 | The seeds were named before the experiment was written | READ | the lead's ruling of 14:08 in the round's folder, which is not committed; the parcel's `tests/test_lrn_a_e1.py` states the same six. That the ruling came first rests on the round's ledger | the ledger's times |
| E6 | Nothing of the learner or of the experiment's script differs between the commit the first run was made on and the merge commit the second was made on | MEASURED | `git diff 6a2431f5d843114eebbee01dcafb2e9bf9e1e997 9c9da6f0c695b619eb996a22b6f252b65fbf793c -- learn tests/test_lrn_a_e1.py`, which prints nothing | that command |
| E7 | A part is nine to eleven minutes of one core on the lead's desktop with other work running | MEASURED | E4: six parts at once, 10 minutes 39 seconds end to end the first time and 8 minutes 59 seconds the second. The parcel's estimate was six to eight | a rerun |

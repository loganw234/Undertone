# Stage E3 in software: the full run on real seismic noise

The design D0, section 8, stage E3: "a recorded stream. Real noise from HBM, with injections. Seismic archives are the candidate." This is that stage, in software only. The detector is the reference model, fed by recorded vertical-component counts of four SCSN stations through the model's own replay source, with `e0` injected by the model's injector. E1's learner is compared with E0's matched filter, each at its own threshold measured from the same held-out signal-free scores. The judge is the statistics package's new module, `stats/empirical.py`. **No fabric is in it, and nothing here is evidence about fabric or about the card.**

The experiment, its noise rule, its judge and its walls are parcel E3S's: [e3s.md](../model/e3s.md) and `tests/test_e3s_experiment.py`. They were fixed before any record was fetched. The rule, its requests and its prep were frozen and hashed at wall 1, 35 seconds before the first request for records. The kept blocks and the injection sets were committed at wall 2, before any model ran on a record. The full run is the lead's; this page is its record.

## The result

**The experiment held at every station.** The judge's verdict line: `== E3 SOFTWARE: the experiment held at every station`. Its readings for the model named before the run, the learner of the last 32 training blocks (16,384 truth records): **MPP REACHES, CDM REACHES, HDH SHORT, SRN REACHES.**

On 102,400 held-out injections of `e0` at each station, each model at its own threshold, which gives it exactly 3,072 of the same 307,200 held-out signal-free scores (a false-alarm rate of 0.01):

| station | amplitude, of 65,536 | matched filter found | efficiency | learner found | efficiency | cost (matched less learner) | se, by resampling whole blocks | reading at 4 se |
|---|---|---|---|---|---|---|---|---|
| CI.MPP | 3,569 | 1,334 | 0.01303 | 1,334 | 0.01303 | +0.00000 | 0.00010 | REACHES |
| CI.CDM | 3,101 | 68,000 | 0.66406 | 74,626 | 0.72877 | -0.06471 | 0.05079 | REACHES |
| CI.HDH | 932 | 42,319 | 0.41327 | 11,485 | 0.11216 | +0.30111 | 0.02718 | **SHORT** |
| CI.SRN | 7,465 | 15,742 | 0.15373 | 15,782 | 0.15412 | -0.00039 | 0.00172 | REACHES |

**What each reading says, and what it does not:**
- **HDH: the learner falls far short.** It finds 0.112 of the injections where the matched filter finds 0.413, 11 standard errors short. This is the shape E3S's design forecast from 2021's records of these stations (its section 1, an ESTIMATE, Gaussian and first order). The learner's mean difference carries the long-period noise that `e0` rejects ([lrn-a.md](../model/lrn-a.md), limit 1: the rule does not whiten).
- **SRN: the learner reaches the matched filter**, 0.154 against 0.154, inside 0.25 of a standard error. The 2021 forecast said the same: SRN's noise is loud in `e0`'s own band, so the two filters see the same thing.
- **CDM: the learner finds more than the matched filter,** 0.729 against 0.664, which is 1.27 standard errors and reads REACHES. That standard error is wide, 0.051, because the level moves from block to block. **It is not evidence that the learner is better,** and not that it is as good: at that width the reading cannot tell a learner 0.2 short from one 0.2 ahead. The 2021 forecast said far short. It was not met, and the curve says why the named model's figure is fragile: the learners of 4,096 and 65,536 records find 2,364 and 4,253 of 102,400, where the named one finds 74,626.
- **MPP says nothing about the learner.** Both models find 1,334 of 102,400, 0.013, about the false-alarm rate. The injected pulse is not seen by either, so their difference is 0. The amplitude was set by the frozen rule from the 16 calibration blocks, the first three hours of 2024-01-08 UTC, a Sunday afternoon in California, and it is too small for MPP's held-out noise. **A REACHES here is a reading of two blind detectors.**

**So, on this noise, at these four stations: the learner reached the matched filter at one station where both could see the pulse (SRN), fell far short at one (HDH), and the run cannot say at two (CDM, too wide; MPP, both blind).** The question D0's stage E3 asks, whether the learner reaches E0's efficiency on real noise, has the answer "not in general": at HDH it does not.

## What else the judge printed

- **The threshold's carry**, each model's threshold taken from one set of held-out blocks and counted on another:
  - interleaved blocks (alternate): CARRIES at every station for both models;
  - the two halves of the held-out stretch: DOES NOT CARRY at MPP for both models, at CDM for the matched filter, and at HDH for the learner; it carries at SRN.
  The stretch runs from 2024-01-16 to 2024-02-09, and its level moves across it. The interleaved form shares each day's conditions, so it is the weaker check (e3s.md, limit 17).
- **The curve**, reported and not judged: the learners of 1,024, 4,096 and 65,536 records.
  - At HDH every one is SHORT.
  - At SRN only the smallest is SHORT.
  - At CDM the figures do not rise with the records: 47,370, then 2,364, then 4,253 found, against 74,626 for the named 16,384.
  At MPP and CDM the learners of 1,024 and 4,096 records take only 2024-01-16's blocks, the named one two of 01-08's and thirty of 01-16's, and the largest mostly 01-08's (e3s.md, "Where the roles fell"). So the 4,096-record learner, trained on 01-16 alone, is far below both its neighbours. **The day trained on does not explain the curve, and nothing here does:** what is measured is that the learner's figure on CDM's noise moves by a factor of about 32 with the stretch it was trained on (H12).
- **The threshold's own error, two ways.** The resampled standard error on joins of four blocks against single blocks: CDM 0.088 against 0.051, HDH 0.039 against 0.027, SRN 0.0020 against 0.0017, and MPP 0.00010 for both. So dependence runs past one block at CDM and HDH, and the verdict's error, from single blocks, is the smaller of the two there. HDH's SHORT stands under the larger: 0.30111 is 7.7 of the four-block standard errors.
- **The instrument at every station:** no flag; every score read identical to the statistics' own filter; the model's core equal to the baseline on the first trials; the learned filter's peak at the truth index plus 63.

## How it was run

- **The commands,** from E3S's docstring: `python tests/test_e3s_experiment.py --full --station S --data <recordings> --out e3-S.json` for S each of MPP, CDM, HDH and SRN, four processes at once, then `python tests/test_e3s_experiment.py --judge e3-MPP.json e3-CDM.json e3-HDH.json e3-SRN.json`.
- **From 23:41:30 to 23:50:12 on 2026-11-25:** each station took 8 minutes 34 seconds to 8 minutes 42 seconds. Each exited 0, and the judge exited 0.
- **The tree:** a `git archive` export of round 5's branch at `fefe77bf5ddec605f59e4ca32330c41683b72d9f`, which holds E3S merged with its two fixes, under the definition 85e63d4d....
- **The recordings** were the 544 kept blocks a station that E3S's prep wrote, each held to its SHA-256 in `vectors/e3s/blocks.json`. They are not in the tree.
- **It was the third attempt, and the first two are not the record:**
  1. At 23:07 the command ran nothing. The file had no `if __name__ == "__main__"` block, so it loaded and exited 0 with no part written.
  2. From 23:08 to 23:20 the run was made through a runner of the lead's that called the file's own `main()`. It gave these same counts, readings and figures, but the judge refused every part as NOT AS STATED for one reason: the part's `blocks_sha256` hashed each block after injection, where blocks.json holds the raw recording's hash.
  E3S fixed both (`8c04a35`), and its verifier re-checked the fix. Only the third run's parts are under `docs/studies/e3/run/`.

## Which authority this rests on

**`stats/` alone** (D0, section 2): the resampled paired cost, the measured thresholds and the carry check are the statistics package's, in `stats/empirical.py`, which imports nothing of `model/` or `learn/`. The reference model is the detector here, as in E1, so bit identity is not in question. **This is a result about sensitivity in software on recorded noise.** It is not a result about the fabric, nor about the card, nor about finding a real event: the injections are counts added to counts, with no instrument response.

## Limits

Each of [e3s.md](../model/e3s.md)'s limits holds for this record, among them:
1. **Five days, not eight.** The roles were filled in time order, so each station's blocks come from 2024-01-08 to part of 2024-02-09; 02-17, 02-25 and 03-04 were fetched and not used. The frozen rule stands, as ruled before the fetch (e3s.md, limit 16).
2. **One amplitude a station, set on three hours of one Sunday afternoon.** At MPP it leaves both detectors blind. Another calibration would be another experiment, and would be a change to a frozen rule.
3. **The days are not exchangeable.** Resampling whole blocks treats them as if they were, and the four-block joins show dependence past a block at CDM and HDH. A level shared across many hours is not in the error.
4. **Neither model whitens, and on coloured noise the matched filter is not the best detector.** The comparison is of the two detectors D0's stage E3 names, not of either against an optimum. A detector that whitens might reach the matched filter, or pass it, where this learner does not.
5. **What a recorded stream holds is not known** (D0, section 2): the catalogue rules keep out the events SCEDC lists, not those it does not.
6. **Four stations, five days, one pulse, one false-alarm rate, one profile, one learning rule.** Another of any is another experiment.
7. **The result is of one definition.** When `spec/undertone.toml` next changes, the judge will refuse the parts for their hash, and `tests/test_e3_full_run.py` then skips by name, `E3-RECORD-STALE`.

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| H1 | The four parts and the judge's output under `docs/studies/e3/run/` are the third run's: the parts byte for byte, the output with each line end made a line feed | MEASURED | `sha256sum` on the committed files, 2026-11-25; `tests/test_e3_full_run.py` holds all five | that test |
| H2 | Every count, cost, standard error, reading, carry and curve figure of "The result" and "What else the judge printed" | READ | [e3/run/judge-output.txt](e3/run/judge-output.txt), line for line | that file |
| H3 | The efficiencies of the result's table, each found over 102,400, and each cost their difference | COMPUTED | 1,334 / 102,400 = 0.01303; 68,000 / 102,400 = 0.66406; 74,626 / 102,400 = 0.72877; 42,319 / 102,400 = 0.41327; 11,485 / 102,400 = 0.11216; 15,742 / 102,400 = 0.15373; 15,782 / 102,400 = 0.15412 | arithmetic |
| H4 | HDH's learner is 11 standard errors short and CDM's 1.27 ahead; SRN's cost is inside 0.25 of its standard error | COMPUTED | 0.30111 / 0.02718 = 11.08; 0.06471 / 0.05079 = 1.27; 0.00039 / 0.00172 = 0.23 | arithmetic |
| H5 | The committed output is what the tree's judge prints for the committed parts | MEASURED | `tests/test_e3_full_run.py`, in the gate | that test |
| H6 | The run was from 23:41:30 to 23:50:12 on 2026-11-25, on an export of fefe77b under the definition 85e63d4d..., four processes each exit 0, the judge exit 0 | MEASURED | the run's log (`e3_full3.out`), kept in the round's folder and not committed; the lead's ledger, round 5 | that log |
| H7 | The amplitudes, 3,569, 3,101, 932 and 7,465 over 65,536 | READ | `vectors/e3s/injection_sets.json`, each station's `amplitude_num` and `amplitude_den`; e3s.md, "What the fetch and the prep found" | that file |
| H11 | HDH's cost is 7.7 standard errors by the resampling on joins of four blocks | COMPUTED | 0.30111 / 0.03903 = 7.71, from the judge's output | arithmetic |
| H12 | The 4,096-record learner at CDM finds 2,364 and the named one 74,626, a factor of 31.6 | COMPUTED | 74,626 / 2,364 = 31.57, from the judge's output | arithmetic |
| H8 | The rule was frozen at wall 1, 35 seconds before the first request for records, and the blocks and sets were committed at wall 2, before any model ran on a record | READ | E3S's ledger and its verifier VE3S's first report, in the round's folder and not committed; e3s.md, "The order it was made in, and the walls" | the commits' times against the request log |
| H9 | The 2021 forecast: far short at CDM, HDH and MPP, near at SRN | READ | e3s.md, "The forecast from 2021", an ESTIMATE made before any 2024 record was fetched | that page's history |
| H10 | The second run's counts and readings equal the third's at every station | MEASURED | the lead's comparison of `runs-e3-2` and `runs-e3-3`, by the judge's output line for line apart from the blocks' reasons and the verdict, kept in the round's folder | a rerun |

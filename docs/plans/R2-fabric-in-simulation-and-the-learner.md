# Round 2: the fabric in simulation, and the learner - a draft work order for Logan

Drafted by the lead on 2026-11-23, the day round 1 closed, on Logan's word "Yes draft the plan". **Nothing here is approved, and nothing of round 2 has started.** It ends with seven questions, each answerable in a few words.

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. `<repos>` is the folder that holds this repository and its siblings.

## What binds it

- **The design:** `docs/studies/D0-rough-design.md`, approved by Logan on 2026-11-21, with two rows restated on 2026-11-23.
- **Logan's answers to D0's questions** (2026-11-21, in `docs/ROADMAP.md`): SystemVerilog, cocotb and the Vitis RTL kernel flow; phase A first (the host trains, the fabric swaps), then phase B in the fabric; the lead alone on the box and the card.
- **His words at round 1's close** (2026-11-23, whole in `docs/ROADMAP.md`): "Hidden layer from the start if simple enough, otherwise without for the initial design."; "Proposed is approved", on D0's row D1; Raspberry Shake "Stays held for now."; and, on a package index whose terms exclude a person on a sanctions list, "I don't believe I'm on a sanctions list so should be good there."
- **His words on real data** (2026-11-21): "I prefer to work with real data when able."
- **The standing rules** in `docs/ROADMAP.md`, and the send-back rule: only a regression or a wrong answer sends work back.
- **Round 1's lessons**, in CLAUDE.md's traps and in the sections "The lead's slips" of `docs/VALIDATION.md`. The ones that change how this round is held are under "How the round is held".

## What round 1 leaves

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| N1 | On a clean tree at `879caf0` the gate passes, 16 of 16, with 707 tests, in 85 s | MEASURED | `bash verify/run.sh`, 2026-11-23, run id `20261123-103615-879caf0`; `docs/VALIDATION.md`, the entries of that date | a rerun |
| N2 | The reference model exists in plain integer Python: 1,233 lines in six files of `model/` for the source, the injector, the core, the weight store, the scorer and the runner | MEASURED | `wc -l model/source.py model/inject.py model/detector.py model/weights.py model/scorer.py model/run.py`, 2026-11-23 | a rerun |
| N3 | As a matched filter the model's efficiency is inside the statistics' tolerance of D8's figure at five amplitudes, 200,000 injections each | MEASURED | `python tests/test_seam_e0.py --judge` on the five recorded parts, 2026-11-23; reproduced for one part by the round's closing verifier | a rerun of a part under its stated seed |
| N4 | Every stage width in the model is derived from the definition: the pool needs 57 signed bits under the 16-bit one-channel profile and 66 under the 24-bit three-channel one; the head 77 and 85 | COMPUTED | `python -c "from model import detector; print(detector.widths('s16x1'), detector.widths('s24x3'))"` | the overflow gate, which runs the core at its true extremes |
| N5 | In the matched-filter configuration the model steps about 110,000 frames a second on the desktop | READ | `docs/model/mod-b.md`, row B14, the parcel's measurement; its verifier measured 101,012 | a rerun of that row's command |
| N6 | The filter bank at the definition's maxima is 2,048 multipliers. The head today is 16. A hidden layer of 8 units is 136, 6.6% of the bank; of 16 units, 272, 13.3% | COMPUTED | 16 rows of 128 taps; 16 x H + H for H units on 16 filters | arithmetic |
| N7 | The WSL environment `cft2204` has no RTL simulator installed: `iverilog`, `verilator` and `vvp` are absent from a login shell's path, Python there cannot import `cocotb`, and a search of the filesystem to five levels finds neither simulator | MEASURED | a script run on 2026-11-23 through `wsl -d cft2204 -- bash -l`: `command -v` for each tool, `python3 -c "import cocotb"`, and `find / -maxdepth 5 -name iverilog -o -name verilator` | a rerun; a simulator installed deeper than five levels |
| N8 | The sibling project runs its simulation suite in a Docker image built from `ubuntu:24.04` with Icarus Verilog, Verilator and cocotb | READ | `<repos>/cft-fp256/docker/Dockerfile.sim:1-7` and `:33-37`; `<repos>/cft-fp256/tb/Makefile:3-6` | those files |
| N9 | Docker 29.2.1 answers on the desktop, in Git Bash and in `cft2204`, and its local images include `ubuntu:24.04` | MEASURED | `docker --version` in each, and `docker images`, 2026-11-23 | a rerun |
| N10 | cocotb does not set an exit code for a failed bench; the sibling project reads each bench's results file | READ | `<repos>/cft-fp256/CLAUDE.md:109-118` | cocotb's own makefile |
| N11 | On that project's suites Verilator ran 9.7 times faster than Icarus. It is another design and bounds nothing here | READ | `<repos>/cft-fp256/CLAUDE.md:233-236` | this design's own benches |
| N12 | Under the shell the user region has about 4,920 DSP slices; other sources give 5,936 to 5,948 | SURVEY | D0, row H7, which flags the conflict | the utilisation report of the first build |
| N13 | One DSP slice multiplies 27 bits by 18. A head multiplier is 18 bits by 57 or 66, so about three slices each: about 48 for the head today, 408 for a hidden layer of 8 | ESTIMATE | D0's row D2 for the slice, which is BELIEVED; ceil(66 / 26) = 3 | a synthesis report of the head alone |
| N14 | The launch catalogue lists 46 Falcon 9 launches from Vandenberg in 2024, 35 of them timed to the second | MEASURED | `docs/studies/D1b-first-look.md`, row Q6f, from the fetched catalogue file | a later release of the catalogue |
| N15 | One launch's set of records, seven stations on three days with two stations' horizontals, was 25 files and 10,788,864 bytes, fetched by 30 requests in about a minute | MEASURED | `docs/studies/D1b-first-look.md`, rows Q5e and R1; `docs/studies/d1/manifest.tsv`, the waveform rows, 15:14:01 to 15:15:00 UTC | the manifest |
| N16 | 35 launches fetched the same way are about 378 MB and about 35 minutes of requests, one after another | COMPUTED | 35 x 10,788,864 bytes; 35 x 59 s, from N14 and N15 | whether the nearest station has records in 2024: it had none in 2021 |
| N17 | Round 1's parcels took 37 to 74 minutes for each build, against time boxes of three and four hours; its verifiers' passes took 2 to 22 minutes; the round took three hours and twenty-one minutes | MEASURED | `docs/VALIDATION.md`, the closing entry's table and the entries it sums | those entries |

## What round 2 could be

Three shapes. Each is a real round; they differ in what it would show.

**A. The fabric first.** The source, the injector, the detector core and the weight store in SystemVerilog, each held against the reference model in simulation on every score word. *Shows:* that the model's definition can be built, bit for bit, at the true extremes, under both profiles; it is the first half of D0's bit-identity gate, and it completes the generated-copies gate. *Does not show:* anything on the card, and nothing about learning.

**B. Learning first.** No RTL. The host trainer of phase A in software, and stages E1 and E2 run through the reference model. *Shows:* whether a learner that starts blank reaches the matched filter's efficiency, how many labelled windows that takes, and, in E2, whether adapting recovers events a frozen model misses: the project's own question, on easy mode. *Does not show:* that any of it runs in fabric.

**C. Both, as two tracks that share no file.** A and B's first half, E1, in one round. *Shows:* both of the above but E2. *Costs:* the lead's attention. Round 1 held four parcels and the lead's two pieces in three hours and twenty-one minutes (N17). This would be five parcels and the lead's two.

**Recommended: C.** The two tracks cannot collide: one writes `rtl/` and `tb/`, the other `learn/` and its tests, and both read the model without changing it. What would make C wrong is the head: if the hidden layer is decided late, RTL written for one head is rewritten for another. So the head is decided first, in wave 0, before either track starts.

## The detector's head: what "simple enough" means

Logan's word: "Hidden layer from the start if simple enough, otherwise without for the initial design." The lead proposes a test for "simple enough", **fixed here, before the design is drawn**, so that the answer cannot be bent to fit it. A hidden layer goes in from the start only if all four hold:

1. **Today's head stays an exact special case.** A version 1 blob runs unchanged; every vector of round 1 still passes; the five recorded counts of stage E0 are reproduced to the injection.
2. **One new choice of width, and no more.** The sum into each hidden unit is 77 or 85 bits at the extremes (N4), too wide to carry on. So one shift follows it, into a stated width, with the sticky overflow flag where that width is exceeded, and the overflow gate runs it at the true extremes. A design that needs a second such choice is not simple enough.
3. **The head stays small beside the bank.** Counted as multipliers at the definition's maxima, the whole head is at most a tenth of the filter bank. By N6 that admits 8 hidden units and not 16.
4. **It fits one parcel.** The design, the model's change, its vectors, its tests and its document fit one parcel's time box by the design's own account.

If any fails, the head stays one linear layer, as a stated limit, and the question is asked again after stage E1 has shown whether the learner wants more.

*What this test is not:* a measurement of fabric. N13 is an ESTIMATE and drives nothing here. The fabric's cost is measured when the head is first synthesised, and that report is what would show criterion 3 was the wrong proxy.

## Wave 0, before any other parcel

**P0, the lead's.**

- **The simulators.** A `docker/Dockerfile.sim` of this project's own, with Icarus Verilog, Verilator and cocotb at pinned versions, and a first bench that proves it: a counter in SystemVerilog checked by cocotb. CLAUDE.md's trap 3 said RTL simulation runs in `cft2204`; N7 shows the simulators are not there, and the trap is restated with this draft.
- **A second size for the gate.** `bash verify/run.sh` stays as it is and needs no Docker. A new `--with rtl` adds the stages that run benches in the image. Each such stage reads the results file a bench writes, never the exit code (N10), and each has a control: a bench with a planted wrong expectation must fail it, and a bench that wrote no results must be refused.
- **The generated copies.** `tools/gen_spec.py` gains a SystemVerilog package and a C header from the one definition, each under `--check`, each with one edited constant planted in turn. That completes D0's generated-copies gate.
- **The bit-identity harness.** One cocotb helper that every RTL bench uses: it drives frames from a model stream and compares every score record, word for word, with the model's. The model is the authority, so the expected words come from the model; that is what this gate is. Its control is D0's: one flipped coefficient bit, on each side in turn, must be reported, on a stream where that tap reaches the score.
- **The register map**, in the definition: what the host writes and reads. Design first, because RTL-B, the host library of a later round and the capability bits all read it.

P0 goes past a verifier before wave 1 is dispatched.

**HEAD, a parcel, design first.** The hidden layer's definition in integer arithmetic, held to the four-part test above. Its design is its first report; the lead rules on it; a design that changes D0 goes to Logan. If the test passes, HEAD builds it into the model, with a version 2 blob, vectors worked by hand and the overflow gate at the extremes. If it fails, HEAD's design and the reason are committed as a study and the model is not touched.

## The parcels, as waves

| wave | parcel | what | depends on | time box |
|---|---|---|---|---|
| 0 | **P0**, the lead's | as above | round 1 | 2 h |
| 0 | **HEAD** | as above | round 1 | 2 h |
| 1 | **RTL-B** | The detector core and the weight store in SystemVerilog: filter bank, rectifier, pool, head, score, the swap at a named output index, the flags. Every score word equal to the model's under both profiles, the true extremes among the streams. **Design first:** which refusals live in the fabric and which in the host library; the pipeline's latency, as a number the bench checks; how the parameters follow the generated package | P0, HEAD | 2 h |
| 1 | **RTL-A** | The source and the injector in SystemVerilog: the counter-based generator, the table lookup, the injector's rounding and refusals. Every sample equal to the model's. **Design first:** where the table lives and how wide a sigma the fabric holds; replay from memory is the kernel's and is not in this round | P0 | 2 h |
| 1 | **LRN-A** | Phase A's host trainer, in software: from labelled windows to a coefficient set, quantised by the definition's rule, packed as a blob, swapped in at a named index. Then stage E1 through the reference model. **Design first:** what is learned and from which labels; the split by time; how the threshold is set again after every swap; the comparison-rules gate of D0 section 8 | HEAD's ruling | 2 h |
| 1 | **LCH-3** | The launch-data experiment, with every definition fixed in the ledger before any record is fetched: the 35 launches of N14, a split into launches that set the rule's constants and launches scored once, control windows by D1's rule. **Design first:** the hit rule's open points, and what the count must exceed to say a launch is seen more often than a control window | round 1 | 2 h |
| 2 | **SEAM-2**, the lead's | RTL-A feeding RTL-B in one simulation, against `model/run.py`, on every score word; truth isolation across the two in RTL; the full run of stage E1 | RTL-A, RTL-B, LRN-A | 2 h |

**Named controls, in the briefs.** Each is built, run, seen to fail, and reported with its output.

- **RTL-B:** one flipped coefficient bit in the RTL, and one in the model, must each be reported on a stream where the tap reaches the score. A swap that changes half the taps a clock late must be caught. A core one bit narrower at each stage must raise the flag at the true extremes. A pipeline one stage longer than the stated latency must fail the bench.
- **RTL-A:** a generator with one constant changed, a table one entry short, an injector a sample late and one that rounds a tie upward must each be caught.
- **LRN-A:** a trainer that returns its starting weights must fall outside the tolerance. A run whose injection set differs from the committed hash must be refused. A comparison made at an equal threshold in place of an equal false-alarm rate must be refused. A learner fed labels shifted by a pulse length must not reach the efficiency.
- **LCH-3:** the first control of study D1, the wrong window, must give a count the test does not reject. A catalogue with its times shifted by an hour must not be "seen".
- **HEAD:** a version 1 blob through the new head must reproduce round 1's vectors; a hidden unit with one flipped weight bit must change a score; a shift one bit short must raise the flag at the extremes.
- **SEAM-2:** the same samples under other truth records must give the same RTL score words; a bench wired to read truth must be caught.

## What the round is for

| # | the round is worth running if | basis | source or command | falsified by |
|---|---|---|---|---|
| W1 | the model's definition can be built in RTL and held to it on every score word, at the true extremes, under both profiles, in simulation | BELIEVED | N4: the widths are derived, and the largest is 85 bits; nothing here has synthesised or simulated any of it | a stage of the model that the RTL cannot match without the model changing |
| W2 | a host-trained coefficient set that starts blank reaches the matched filter's efficiency in stage E1, inside the statistics' tolerance | BELIEVED | D8 says the matched filter is the best a learner can reach; N3 is the figure to reach | the full run of E1 falling outside the tolerance at the amplitude where D8 gives one half |
| W3 | "simple enough" can be decided from the four-part test before any RTL exists | DECISION | the test above, proposed here | HEAD's design stop being unable to answer one of the four |
| W4 | by a rule fixed before any record is fetched, launches are seen at the nearest stations more often than control windows are | BELIEVED | one launch, in D1b; N14 says there are 35 to try | LCH-3's test not rejecting |

## How the round is held

As round 1, with what it taught. Each of these is from a slip recorded in `docs/VALIDATION.md` on 2026-11-23.

- **A verifier's clone is sealed by a script that checks itself:** no remote, no reflog, the work before the faults not in the clone. A parcel's commits are squashed into one before faults are planted, so no commit's diff shows a fault.
- **A verifier is not sent to the round's ledger.** The ledger says which clones hold faults. The lead copies the rulings a verifier needs into a file of their own.
- **Before planting, the lead tries its own faults against the parcel's tests.** In round 1 the parcels' tests caught all twenty-six tried, so each planted code fault needed a test changed beside it.
- **A table is confirmed only by a table.** A verifier that reports a table checked gives its own figure for every cell. The one planted fault missed in round 1 was in a table reported as checked after two of its columns.
- **A verifier's box is used.** Three of round 1's verifiers stopped after seven to nine minutes of an hour. A report lists what was not done, item by item, and what was not done is sent back as a second pass.
- **The lead's own work is planted in files the commit already changes.**
- **Time boxes are two hours**, not three or four (N17), and every parcel is design first.
- **Long runs are scripts with a short form in the gate**, booked on the TimeSheet, with their seeds named in the ledger before any run.
- **A round branch, `r2`,** cut from `main`. Merges go on one at a time with the gate after each. The gate registry conflicts at every merge after the first; every row is kept.
- **No card and no box in this round.** Everything is simulation and software on the desktop. The first build is a later round's.

## What this plan does not settle

- **The time boxes.** All are ESTIMATES from N17, and RTL is new ground here.
- **Whether a learner in software says anything about a learner in fabric.** Phase A's trainer runs on the host by design; phase B is not in this round.
- **The table in fabric.** The noise's table at sigma 1000 has 9,156 entries of 63 bits. Where it lives is RTL-A's design.
- **Stage E2.** Not in this round under A or C.
- **The first build, the host library, the kernel and the card day.** Round 3 or later.

## Questions for Logan

Each has a recommendation. A few words answer each.

1. **Which round: A, B or C?**
   - *(Recommended)* **C**, both tracks. A is the fabric alone; B is the learner alone.
2. **The four-part test for "simple enough", as written above?**
   - *(Recommended)* **Yes.** The alternative is to say now: "hidden layer, 8 units" or "no hidden layer", and HEAD builds or skips accordingly.
3. **Which sample format does the RTL take?** Your word on D0's row D1 was "Proposed is approved".
   - *(Recommended)* **Both, as a parameter**: the RTL is written against the generated package, simulated under the 16-bit one-channel format and the 24-bit three-channel one, and the first build's format is chosen when there is a build. The real records are three components, and two files in 25 need 17 bits.
   - *The alternative:* 16-bit, one channel only, and the wider format later.
4. **How are the simulators provided?** `cft2204` has none installed (N7).
   - *(Recommended)* **A Docker image of this project's own**, as cft-fp256 does. It installs nothing into a shared environment, and it downloads Ubuntu packages and cocotb once.
   - *The alternative:* install them into `cft2204`.
5. **The launch experiment, LCH-3: in this round, or the next?**
   - *(Recommended)* **In this round.** It shares no file with the rest and fetches about 378 MB (N16).
6. **No card time and no build on the box in round 2?**
   - *(Recommended)* **Yes, none.**
7. **Commits and the push:** as round 1, local commits on the round branch, and the lead asks again before `main` moves and anything is pushed?
   - *(Recommended)* **Yes.**

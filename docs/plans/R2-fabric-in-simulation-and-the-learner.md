# Round 2: the fabric in simulation, and the learner - the work order (approved by Logan, 2026-11-23)

Drafted by the lead on 2026-11-23, the day round 1 closed, on Logan's word "Yes draft the plan", and approved by him the same day with one change: his word closes this document, and the fifth question he answered otherwise than recommended. This is the third draft. A verifier, VP2, read the first against its sources, re-checked the second, and read the changes of the third, where it found no wrong answer. Its wrong answers are all answered here; four of its smaller points are left as they were, and the record of the three passes in `docs/VALIDATION.md` names them. A few words changed after its last pass, and that record says which. It ends with six questions, each answerable in a few words.

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. `<repos>` is the folder that holds this repository and its siblings.

## What binds it

- **The design:** `docs/studies/D0-rough-design.md`, approved by Logan on 2026-11-21, with two rows restated on 2026-11-23.
- **Logan's word on D0's questions** (2026-11-21, in `docs/ROADMAP.md`) was that all were approved as recommended. The recommendations, in the lead's words: SystemVerilog, cocotb and the Vitis RTL kernel flow; phase A first (the host trains, the fabric swaps), then phase B in the fabric; simulation in the WSL environment; the lead alone on the box and the card.
- **His words at round 1's close** (2026-11-23, whole in `docs/ROADMAP.md`): "Hidden layer from the start if simple enough, otherwise without for the initial design."; "Proposed is approved", on D0's row D1; Raspberry Shake "Stays held for now."; and, on a package index whose terms exclude a person on a sanctions list, "I don't believe I'm on a sanctions list so should be good there."
- **His word on Docker** (2026-11-23, after the first draft): "You may install anything needed to the docker environment, or create a new one for this project if needed".
- **His words on real data** (2026-11-21): "I prefer to work with real data when able."
- **The standing rules** in `docs/ROADMAP.md`, and the send-back rule: only a regression or a wrong answer sends work back.
- **Round 1's lessons**, in CLAUDE.md's traps and in `docs/VALIDATION.md`. The ones that change how this round is held are under "How the round is held".

## What round 1 leaves

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| N1 | On a clean tree at `879caf0` the gate passes, 16 of 16, with 707 tests, in 85 s | MEASURED | `bash verify/run.sh`, 2026-11-23, run id `20261123-103615-879caf0`. The verdict and the count are also in `docs/VALIDATION.md`, the entry after the close; the 85 s is this run's alone | a rerun |
| N2 | The reference model exists in plain integer Python: 1,233 lines in six files of `model/` for the source, the injector, the core, the weight store, the scorer and the runner | MEASURED | `wc -l model/source.py model/inject.py model/detector.py model/weights.py model/scorer.py model/run.py`, 2026-11-23 | a rerun |
| N3 | As a matched filter the model's efficiency is inside the statistics' tolerance of D8's figure at five amplitudes, 200,000 injections each | MEASURED | `python tests/test_seam_e0.py --judge` on the five recorded parts, 2026-11-23; `docs/VALIDATION.md`, the entry for wave 2, has the table. The recorded parts are in the round's folder, which is not in the tree, so this command cannot be rerun from a clone | a rerun of a part under its stated seed |
| N4 | Every stage width in the model is derived from the definition: the pool needs 57 signed bits under the 16-bit one-channel profile and 66 under the 24-bit three-channel one; the head 77 and 85 | COMPUTED | `python -c "from model import detector; print(detector.widths('s16x1'), detector.widths('s24x3'))"` | the overflow gate, which runs the core at its true extremes |
| N5 | In the matched-filter configuration the model steps about 110,000 frames a second under the one-channel profile and about 66,000 under the three-channel one. One run, by the parcel, on a desktop other work shared | READ | `docs/model/mod-b.md`, row B14 | a rerun of that row's command |
| N6 | The filter bank at the definition's maxima is 2,048 multipliers. The head today is 16. A hidden layer of H units on 16 filters is 17 x H: 136 for 8 units, 6.6% of the bank; 204 for 12, 10.0%; 272 for 16, 13.3% | COMPUTED | 16 rows of 128 taps; 16 x H into the hidden units and H out of them | arithmetic |
| N7 | The WSL environment `cft2204` has no RTL simulator installed: `iverilog`, `verilator` and `vvp` are absent from a login shell's path, Python there cannot import `cocotb`, and a search of the filesystem to five levels finds neither simulator | MEASURED | a script run on 2026-11-23 through `wsl -d cft2204 -- bash -l`: `command -v` for each tool, `python3 -c "import cocotb"`, and `find / -maxdepth 5 -name iverilog -o -name verilator` | a rerun; a simulator installed deeper than five levels |
| N8 | The sibling project runs its simulation suite in a Docker image built from `ubuntu:24.04` with Icarus Verilog and Verilator from that system's packages; its header says cocotb is in it too | READ | `<repos>/cft-fp256/docker/Dockerfile.sim:1-7` and `:33-37`; `<repos>/cft-fp256/tb/Makefile:3-6` | those files |
| N9 | Docker 29.2.1 answers on the desktop, in Git Bash and in `cft2204`. Its local images include `ubuntu:24.04`, 78.2 MB, and the sibling project's `cft-sim`, 699 MB | MEASURED | `docker --version` in each, and `docker images`, 2026-11-23 | a rerun |
| N10 | That base image offers Icarus Verilog 12.0, Verilator 5.020 and Python 3.12.3; the newest cocotb on the package index is 2.1.0. That these are offered is all the two commands show; whether they work together is N20 | MEASURED | `docker run --rm ubuntu:24.04 bash -c "apt-get update -qq; apt-cache policy iverilog verilator python3"` and `python -m pip index versions cocotb`, 2026-11-23 | a rerun; the index moving on |
| N11 | cocotb does not set an exit code for a failed bench; the sibling project reads each bench's results file | READ | `<repos>/cft-fp256/CLAUDE.md:109-118` | cocotb's own makefile |
| N12 | On that project's suites Verilator ran 9.7 times faster than Icarus. It is another design and bounds nothing here | READ | `<repos>/cft-fp256/CLAUDE.md:233-236` | this design's own benches |
| N13 | Under the shell the user region has about 4,920 DSP slices; other sources give 5,936 to 5,948 | SURVEY | D0, row H7, which flags the conflict | the utilisation report of the first build |
| N14 | One DSP slice multiplies 27 bits by 18. A head multiplier is 18 bits by 57 or 66, so about three slices each: about 48 for the head today, 408 for a hidden layer of 8 | ESTIMATE | D0's row D2 for the slice, which is BELIEVED; ceil(66 / 26) = 3; N6's 16 and 136 | a synthesis report of the head alone |
| N15 | The launch catalogue lists 46 Falcon 9 launches from Vandenberg in 2024, 35 of them timed to the second | MEASURED | `docs/studies/D1b-first-look.md`, row Q6f, from the fetched catalogue file | a later release of the catalogue |
| N16 | One launch's set of records, seven stations on three days with two stations' horizontals, was 25 files and 10,788,864 bytes, fetched by 30 requests in about a minute | MEASURED | `docs/studies/D1b-first-look.md`, rows Q5e and R1; `docs/studies/d1/manifest.tsv`, the waveform rows, 15:14:01 to 15:15:00 UTC | the manifest |
| N17 | 35 launches fetched the same way are about 378 MB and about 35 minutes of requests, one after another | COMPUTED | 35 x 10,788,864 bytes; 35 x 59 s, from N15 and N16 | a launch whose records are not the 25 files of N16; whether the nearest station has records in 2024, as it had none in 2021 |
| N18 | Round 1's parcels took 37 to 74 minutes for each build, against time boxes of three and four hours; from the foundation onward its verifiers' passes took 2 to 22 minutes; the round took three hours and twenty-one minutes | MEASURED | `docs/VALIDATION.md`, the closing entry's table, the entries it sums and the entry after it | those entries |
| N19 | At sigma 1000 the noise's table has 9,156 entries. Each counts in units of 2^-63: 63 bits hold every entry but the last, which is 2^63 itself | MEASURED | `python -c "from model import source; t = source.gaussian_table(1000, 1); print(len(t), max(v.bit_length() for v in t[:-1]), t[-1] == 2**63)"`, 2026-11-23, which printed 9156 63 True; `docs/model/mod-a.md` speaks of 9,156 entries of 63 bits, in an estimate | a rerun |
| N20 | cocotb's documentation says, on the page of its stable line, which titles itself cocotb 2.1.0.dev3, that it supports Icarus 11.0 and later and Verilator 5.036 and later; and on the page of release 1.9.2, Verilator 5.022 and later. Neither page was read for what an older release needs of Icarus. The base image's Icarus, 12.0, is inside that; its Verilator, 5.020, is older than both | READ | `https://docs.cocotb.org/en/stable/simulator_support.html` and `https://docs.cocotb.org/en/v1.9.2/simulator_support.html`, fetched and read by the lead on 2026-11-23: "cocotb supports Verilator 5.036+", "cocotb supports Icarus 11.0+", "cocotb supports Verilator 5.022 and later"; N10 for the image's versions | P0's first bench, run under each simulator |

## What round 2 could be

Three shapes. Each is a real round; they differ in what it would show.

**A. The fabric first.** The source, the injector, the detector core and the weight store in SystemVerilog, each held against the reference model in simulation on every score word. *Shows:* that the model's definition can be built, bit for bit, at the true extremes, under both profiles. That is the first of the three parts of D0's bit-identity gate (RTL, then host, then card), for the datapath and not the scorer; and it completes the generated-copies gate. *Does not show:* anything on the card, and nothing about learning.

**B. Learning first.** No RTL. The host trainer of phase A in software, and stages E1 and E2 run through the reference model. *Shows:* whether a learner that starts blank reaches the matched filter's efficiency, how many labelled windows that takes, and, in E2, whether adapting recovers events a frozen model misses: the project's own question, on easy mode. *Does not show:* that any of it runs in fabric.

**C. Both, as two tracks.** A, and B's first half, E1, in one round. *Shows:* both of the above but E2. *Costs:* the lead's attention. Round 1 held four parcels and the lead's two pieces in three hours and twenty-one minutes (N18). C is four parcels and the lead's two; with the launch experiment, which is question 4 and stands beside any of the three shapes, it is five.

**Recommended: C.** The two tracks share no file but one: one writes `rtl/` and `tb/`, the other `learn/` and its tests, both read the model without changing it, and each appends its rows to the gate registry, `tests/gates.toml`. In round 1 that file conflicted at two of five merges, and every row was kept. What would make C wrong is the head: if the hidden layer is decided late, RTL written for one head is rewritten for another. So the head is decided first, in wave 0, before either track starts.

## The detector's head: what "simple enough" means

Logan's word: "Hidden layer from the start if simple enough, otherwise without for the initial design." The lead proposes a test for "simple enough", **fixed here, before the design is drawn**, so that the answer cannot be bent to fit it. A hidden layer goes in from the start only if all four hold:

1. **Today's head stays an exact special case.** A version 1 blob runs unchanged; every vector of round 1 still passes; the five recorded counts of stage E0 are reproduced to the injection.
2. **One new choice of width, and at most one new function between the layers.** The sum into each hidden unit is 77 or 85 bits at the extremes (N4), too wide to carry on. So one shift follows it, into a stated width, with the sticky overflow flag where that width is exceeded, and the overflow gate runs it at the true extremes. What stands between the layers is pass or absolute value, which the model's rectifier already has, or a clamp at zero, which it does not: a clamp would be one new rectifier code in the definition, and is the only new function allowed. A design that needs a second choice of width, a table or a multiplier there is not simple enough.
3. **The head stays small beside the bank.** Counted as multipliers at the definition's maxima, the whole head is at most a tenth of the filter bank: 17 x H at most 204.8, so at most 12 hidden units. Eight pass; sixteen do not (N6).
4. **It fits one parcel, shown by doing it.** Parcel HEAD builds it inside its time box and is READY past its verifier. If it is not, its branch is not merged, and the head stays as it is. Nobody's forecast decides this part. What can still bend it, said plainly: the box is two hours, which is an ESTIMATE; so the time counted is the harness's own figure for the parcel's passes, its send-backs among them, READY means its verifier's last pass found no regression and no wrong answer, and if the lead lengthens the box that is a change to this test and goes to Logan.

If any fails, the head stays one linear layer, as a stated limit, and the question is asked again after stage E1 has shown whether the learner wants more.

*What this test is not:* a measurement of fabric. N14 is an ESTIMATE and drives nothing here; the test is a count, two things a gate can check, and one outcome. The fabric's cost is measured when the head is first synthesised, which is not in this round unless question 5 says so.

*What the hidden layer is for in this round:* to exist in the model and in the RTL, held bit for bit. It is not trained in round 2. Stage E1 learns one filter's coefficients in the matched-filter configuration, where D8 applies.

## Wave 0, before any other parcel

**P0, the lead's.**

- **The simulators.** A `docker/Dockerfile.sim` of this project's own, by Logan's word of 2026-11-23, with Icarus Verilog and cocotb at pinned versions, and a first bench that proves they work together. The base image's Verilator is older than any current cocotb supports (N20), so P0 starts on Icarus alone and adds a newer Verilator, built in the image, only if this design's benches are slow enough to need it. The sibling project's image is not used and not changed. D0's fourth answer had simulation in `cft2204`; N7 shows the simulators are not there, and CLAUDE.md's trap 3 is restated with this draft.
- **A second size for the gate.** `bash verify/run.sh` stays as it is and needs no Docker. A new `--with rtl` adds the stages that run benches in the image. Each such stage reads the results file a bench writes, never the exit code (N11), and each has a control: a bench with a planted wrong expectation must fail it, and a bench that wrote no results must be refused.
- **The generated copies.** `tools/gen_spec.py` gains a SystemVerilog package and a C header from the one definition, each under `--check`, each with one edited constant planted in turn. That completes D0's generated-copies gate.
- **The bit-identity harness.** One cocotb helper that every RTL bench uses: it drives frames from a model stream and compares every score record, word for word, with the model's. The model is the authority, so the expected words come from the model; that is what this gate is. P0 proves the harness on a filter of one tap, written in RTL for the purpose, against the model's core configured with one tap: one flipped coefficient bit in the RTL, and one in the model, must each be reported.
- **The register map**, in the definition: what the host writes and reads. Design first, because RTL-B, the host library of a later round and the capability bits all read it.

P0 goes past a verifier before wave 1 is dispatched.

**HEAD, a parcel, design first.** The hidden layer's definition in integer arithmetic, held to the four-part test above. Its design is its first report; the lead rules on it; a design that changes D0 goes to Logan. The design stop can rule on part 3, which is a count, and on whether the design sets out to meet parts 1 and 2. If it does, HEAD builds it into the model, with a version 2 blob, vectors worked by hand and the overflow gate at the extremes. Parts 1 and 2 are then held by gates, after the build, and part 4 is the parcel's own outcome. If the design fails part 3, or cannot meet 1 or 2, it is committed as a study with the reason, and the model is not touched.

## The parcels, as waves

Every time box is an ESTIMATE from N18.

| wave | parcel | what | depends on | time box |
|---|---|---|---|---|
| 0 | **P0**, the lead's | as above | round 1 | 2 h |
| 0 | **HEAD** | as above | round 1 | 2 h |
| 1 | **RTL-B** | The detector core and the weight store in SystemVerilog: filter bank, rectifier, pool, head, score, the swap at a named output index, the flags. Every score word equal to the model's under both profiles, the true extremes among the streams. **Design first:** which refusals live in the fabric and which in the host library; the pipeline's latency, as a number the bench checks; how the parameters follow the generated package. The scorer is not in it | P0, HEAD | 2 h |
| 1 | **RTL-A** | The source and the injector in SystemVerilog: the counter-based generator, the table lookup, the injector's rounding and refusals. Every sample equal to the model's. **Design first:** where the table lives (N19) and how wide a sigma the fabric holds; replay from memory is the kernel's and is not in this round | P0 | 2 h |
| 1 | **LRN-A** | Phase A's host trainer, in software: from labelled windows to one filter's coefficients, quantised by the definition's rule, packed as a blob, swapped in at a named index, in the matched-filter configuration. A short form of stage E1 in the gate. **Design first:** what the labels are; the split by time; how the threshold is set again after every swap; the comparison-rules gate of D0 section 8 | HEAD's ruling | 2 h |
| 1 | **LCH-3**, if question 4 says so | The launch-data experiment, with every definition fixed in the ledger before any record is fetched: the 35 launches of N15, a split into launches that set the rule's constants and launches scored once, control windows by D1's rule. **Design first:** the hit rule's open points, and what the count must exceed to say a launch is seen more often than a control window | round 1 | 2 h |
| 2 | **SEAM-2**, the lead's | RTL-A feeding RTL-B in one simulation, against `model/run.py`, on every score word; truth isolation across the two in RTL; the full run of stage E1, as a script with its seeds named before any run | RTL-A, RTL-B, LRN-A | 2 h |

**Named controls, in the briefs.** Each is built, run, seen to fail, and reported with its output.

- **RTL-B:** one flipped coefficient bit in the RTL, and one in the model, must each be reported on a stream and a configuration where the tap reaches the score. A swap that changes half the taps a clock late must be caught. A core one bit narrower at each stage must raise the flag at the true extremes. A pipeline one stage longer than the stated latency must fail the bench. For each refusal the design puts in the fabric, a build that accepts the case and one that names it wrongly must each be caught.
- **RTL-A:** a generator with one constant changed and a table one entry short must each be caught; and D0's four for the injector, one that adds nothing, one a sample late, one with the sign flipped and one at half amplitude, with a fifth that rounds a tie upward.
- **LRN-A:** a trainer that returns its starting weights must fall outside the tolerance. A run whose injection set differs from the committed hash must be refused. A comparison made at an equal threshold in place of an equal false-alarm rate must be refused. A learner fed labels shifted by a pulse length must not reach the efficiency. A blob swapped in one output late must show in the records' epoch.
- **LCH-3:** the first control of study D1, the wrong window, must give a count the test does not reject. A catalogue with its times shifted by an hour must not be "seen". A launch used to set the rule's constants and then scored must be refused.
- **HEAD:** a version 1 blob through the new head must reproduce round 1's vectors; a hidden unit with one flipped weight bit must change a score, on a configuration where that unit reaches the score; a shift one bit short must raise the flag at the extremes.
- **SEAM-2:** one sample changed between the two RTL blocks must be reported by the comparison of the whole pipeline; the same samples under other truth records must give the same RTL score words; a bench wired to read truth must be caught.

**D0's sixteen gates, and what this round would do to each**, if every parcel is READY. *Would be completed:* generated copies, by P0. *Would be advanced on the RTL side, in simulation, for the datapath:* bit identity (its first part of three), swap, overflow, injection and truth isolation; and refusal, for the refusals RTL-B's design puts in the fabric. *Would be advanced in software:* reference model, by HEAD's vectors if the head changes; comparison rules, by LRN-A. *Built on and not changed:* statistics, whose tolerance judges stage E1; replay and noise tails, which round 1 holds for the model and RTL-A inherits only by matching it sample for sample. *Not touched:* scorer, which no parcel here builds in RTL; capability bits, though P0's register map is what they will read, and provenance: both need a build; and the learner gate, which is the fabric's learner of phase B.

## What the round is for

| # | the round is worth running if | basis | source or command | falsified by |
|---|---|---|---|---|
| W1 | the model's definition can be built in RTL and held to it on every score word, at the true extremes, under both profiles, in simulation | BELIEVED | N4: the widths are derived, and the largest is 85 bits; nothing here has synthesised or simulated any of it | a stage of the model that the RTL cannot match without the model changing |
| W2 | in the matched-filter configuration, a host-trained filter that starts blank reaches the matched filter's efficiency in stage E1, inside the statistics' tolerance | BELIEVED | D8 says the matched filter is the best a learner can reach, and holds in that configuration only; N3 is the figure to reach | the full run of E1 falling outside the tolerance at the amplitude where D8 gives one half |
| W3 | "simple enough" can be decided by the four-part test before the datapath's RTL exists | DECISION | the test above, proposed here: a count, two things a gate checks, and parcel HEAD's own outcome. It measures no fabric | HEAD's design stop being unable to answer part 3, or to say whether its design sets out to meet parts 1 and 2 |
| W4 | by a rule fixed before any record is fetched, launches are seen at the nearest stations more often than control windows are | BELIEVED | one launch, in D1b; N15 says there are 35 to try | LCH-3's test not rejecting |

## How the round is held

As round 1, with what it taught. Each of these is from something `docs/VALIDATION.md` records on 2026-11-23, as a slip of the lead's or as what a pass measured.

- **A verifier's clone is sealed by a script that checks itself:** no remote, no reflog, the work before the faults not in the clone. A parcel's commits are squashed into one before faults are planted, so no commit's diff shows a fault.
- **A verifier is not sent to the round's ledger.** The ledger says which clones hold faults. The lead copies the rulings a verifier needs into a file of their own.
- **Before planting, the lead tries its own faults against the parcel's tests.** In round 1 the parcels' tests caught all twenty-six tried, so each planted code fault needed a test changed beside it.
- **A table is confirmed only by a table.** A verifier that reports a table checked gives its own figure for every cell. The one planted fault missed in round 1 was in a table reported as checked after two of its columns.
- **A verifier's box is used.** One of round 1's verifiers used nine minutes of an hour and left items undone; its second pass covered its own list. A report lists what was not done, item by item, and what was not done is sent back as a second pass.
- **The lead's own work is planted in files the commit already changes.**
- **Time boxes are two hours**, not three or four (N18), and every parcel is design first.
- **Long runs are scripts with a short form in the gate**, booked on the TimeSheet, with their seeds named in the ledger before any run.
- **A round branch, `r2`,** cut from `main`. Merges go on one at a time with the gate after each. The gate registry conflicts whenever two parcels have each added rows, twice in round 1's five merges; every row is kept.
- **Simulation runs in a Docker image on the desktop.** Logan's word of 2026-11-23 allows the image. That it takes the place of `cft2204` for simulation is the lead's reading, from N7.

## What this plan does not settle

- **How long the round takes.** Three waves of two-hour boxes are six hours if every box is used, with the verifiers' passes on top. At round 1's pace, where builds used a third to a half of their boxes (N18), it is four to six hours by the clock. Both are ESTIMATES, and RTL is new ground here.
- **The fabric's cost of anything.** N13 is a SURVEY figure and N14 an ESTIMATE. Nothing is synthesised in this round unless question 5 says so.
- **The scorer in RTL.** No parcel builds it. Bit identity in this round is on score words, before any threshold.
- **Training the hidden layer.** It is built and held bit for bit, and not trained, in this round.
- **Whether a learner in software says anything about a learner in fabric.** Phase A's trainer runs on the host by design; phase B is not in this round.
- **The table in fabric.** Where N19's table lives is RTL-A's design.
- **The image's size.** The sibling project's is 699 MB (N9); this project's is not built.
- **Stage E2**, under A or C. **The first build, the host library, the kernel and the card day:** round 3 or later.

## Questions for Logan

Each has a recommendation and a real alternative. A few words answer each. One question of the first draft, how the simulators are provided, he has answered: a Docker image of this project's own.

1. **Which round: A, B or C?**
   - *(Recommended)* **C**, both tracks: four parcels and the lead's two.
   - *The alternatives:* A, the fabric alone; B, the learner alone.
2. **The four-part test for "simple enough", as written above?**
   - *(Recommended)* **Yes.** It admits up to 12 hidden units, and parcel HEAD's design says how many. In this round the layer is built and held bit for bit; it is not trained.
   - *The alternative:* say now "hidden layer, 8 units" or "no hidden layer", and parcel HEAD builds or is dropped accordingly.
3. **Which sample format does the RTL take?** Your word on D0's row D1 was "Proposed is approved".
   - *(Recommended)* **Both, as a parameter.** The RTL is written against the generated package and every bench runs under the 16-bit one-channel format and the 24-bit three-channel one. That costs each bench twice and leaves the first build's format to the round that builds. The real records are three components, and two files in 25 need 17 bits.
   - *The alternative:* 16-bit, one channel only, and the wider format in a later round.
4. **The launch experiment, LCH-3: in this round, or the next?**
   - *(Recommended)* **In this round**, as a fifth parcel. It touches no file of the other tracks but the gate registry, and fetches about 378 MB (N17).
   - *The alternative:* the next round, and this one stays at four parcels.
5. **The box: nothing on it in round 2?**
   - *(Recommended)* **Nothing.** Everything is simulation and software on the desktop.
   - *The alternative:* after RTL-B is READY, one synthesis of the head alone on the box, by the lead, booked on the TimeSheet. It turns N14 from an estimate into a measurement in this round. It cannot change the head's decision, which is made in wave 0; it would show whether the test's third part was the right proxy. It is a piece this draft has no time box or control for yet.
6. **The push at the close?**
   - *(Recommended)* **The lead asks you again** before `main` moves and anything is pushed, as in round 1.
   - *The alternative:* a standing word now, to push once the closing verifier's pass is clean.

## Logan's word (2026-11-23, verbatim)

> Approved with recommendations except 5 do a synthesis to measure real cost

*The lead's reading.* Round 2 runs as this plan has it, with each question answered as recommended but the fifth:

1. Shape C: both tracks.
2. The four-part test for "simple enough", as written.
3. The RTL takes the sample format as a parameter, and every bench runs under both formats.
4. The launch experiment, LCH-3, is in this round, as a fifth parcel.
5. **Not as recommended.** The alternative: after RTL-B is READY, one synthesis of the head alone on the box, by the lead, booked on the TimeSheet, to measure its real cost.
6. The lead asks him again before `main` moves and anything is pushed.

## Notes after approval

**SYN, the lead's, a piece his fifth answer adds.** The draft said it had no time box or control for it. It has these:

- *When:* in wave 2, after RTL-B is READY and merged. It cannot change the head's decision, which HEAD and the four-part test make in wave 0.
- *What:* one out-of-context synthesis of the head's RTL alone, as RTL-B built it, under each of the two sample formats, on `amd-arc-box`, by the lead and nobody else. It reads the utilisation report: DSP slices, look-up tables, registers. No implementation, no timing closure, no bitstream, nothing on the card.
- *What it settles:* row N14 becomes MEASURED or is shown wrong, and with it D0's row D2, one slice for an 18-bit by 27-bit multiply. It shows whether the test's third part, a count of multipliers, was a fair proxy for cost.
- *Its control:* a module of one multiplier, 18 bits by 16, synthesised the same way first. Its report must show exactly one DSP slice. If it does not, the lead's reading of the report is wrong, and no figure for the head is reported until that is understood.
- *Its time box:* one hour of the lead's, an ESTIMATE; the box's time is booked on the TimeSheet before the run, in the mildest mode that is true, around the sibling project's standing bookings.
- *What it does not show:* whether the head meets timing, what the whole design costs, or anything about the card.

**Wave 0's simulators.** Row N20 stands: the image starts on Icarus Verilog. Logan's word of 2026-11-23 on Docker covers building it.

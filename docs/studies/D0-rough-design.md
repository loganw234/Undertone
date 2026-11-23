# D0: an adaptive detector core on the U50 - rough design (approved by Logan, 2026-11-21)

Drafted by the lead on 2026-11-21 for Logan's review. **Nothing in this document has been built or run.** It proposes; it decides nothing. The decisions are Logan's: section 12 puts them as questions, and he answered all six as recommended on 2026-11-21 (his words close this document). This is the second draft: a verifier (VD0) read the first against its sources on 2026-11-21, re-checked the answers to its findings, and found no wrong answer left; two sentences it then flagged are restated here and have not been back to it. The pass is recorded in [VALIDATION.md](../VALIDATION.md).

## Labels

Every figure and every fact this design leans on sits in a claims register (sections 3, 6 and 7), and each row carries a basis. `verify/run.sh` refuses a row without one.

- **MEASURED**: the lead ran the command given, on the date given.
- **READ**: read from the file and line given. Not re-derived.
- **COMPUTED**: arithmetic from inputs stated in the row.
- **ESTIMATE**: a guess, with what it rests on. It drives no decision until it is measured.
- **BELIEVED**: not checked. Usually textbook knowledge without a committed quote.
- **SURVEY**: taken from the literature survey of 2026-11-21 ([the report](../../reports/Adaptive%20FPGA%20ML%20for%20signal%20detection.md)). Agents wrote that survey and no planted-fault control was run on them, so each SURVEY row is a lead to check, not evidence.
- **DECISION**: a choice, proposed here, that is Logan's to make.

Prose outside the registers is the lead's reasoning. The gate does not check it.

## 1. What binds it

- **Logan's words of 2026-11-21**, kept verbatim in [ROADMAP.md](../ROADMAP.md): weights adaptable at fabric speed; a high-speed, low-latency model, and not traditional LLM inference; the adaptive experiment is whether it can learn to recognise faint signals or missed events; the card is a U50 in a Linux machine and has no network port; ideally the system works on any given input with a properly configured model; an easy first target is preferred. That the model is small is the lead's reading, not his words.
- **The methods**: HonestFramework and ParcelRound. Section 2 is HonestFramework's first mechanism applied here; sections 9 and 10 are the rest.
- **The survey**, as leads only (section 7).

## 2. The central invariant, and the authority

**The invariant.** For any input stream, any weight set and any configuration, every score word the card produces is bit-identical to the one the reference model produces. Anything the fabric cannot do exactly is refused by name. There is no third outcome.

**The authority is a reference model** in plain Python, with integer arithmetic only: slow, obvious, and sharing no code with the things it judges. The RTL in simulation, the host library and the card are each held against it bit for bit. When they disagree, the model is right.

The model defines everything that is deterministic:

- the detector's arithmetic, including every rounding and every width;
- the on-card noise generator's stream for a given seed;
- the injector's schedule and the samples it adds;
- what a weight swap does to each output sample around it;
- the learner's update, bit for bit, including what happens to an update smaller than one least significant bit.

**What the reference model does not cover: detection performance.** How many faint signals are found at a given false-alarm rate is a statistical question, and bit-identity says nothing about it. That question has two other authorities:

1. **The analytic matched-filter result** for a known pulse in white Gaussian noise (row D8; its source was committed on 2026-11-23, and the row is restated in section 6 and at the end of this file). It is outside the project, so the source's own statement is committed with its locator before anything is compared against it.
2. **A second, foreign implementation**: a floating-point matched filter and injection-recovery count written independently of the reference model, run on the same recorded streams.

A bit-identity pass must never be quoted as evidence about sensitivity, nor a sensitivity curve as evidence that the fabric is correct.

**What sits outside all three, and is relied on anyway.** Stated here so that nothing below is read as covering it:

- the tools: that synthesis builds what simulation ran, and that the design closes timing at the clock it claims. Only a build and a card run say so;
- the host trainer of phase A and its quantiser. The reference model defines the weights the fabric holds and what a swap does. How the host arrives at a candidate set is ordinary software, judged by its held-out score and by the same statistics as everything else;
- the Gaussian law the noise generator's tails are tested against, and the threshold set from signal-free noise. Both are statistics, with the sampling error that implies;
- a recorded stream's own truth, in stage E3. Injections into it are known; what else is in it is not.

## 3. What is on hand

`<repos>` is the folder that holds this repository and its siblings.

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| H1 | cft-fp256 builds for the same card with the Vitis RTL kernel flow, against the shell `xilinx_u50_gen3x16_xdma_5_202210_1` | READ | `<repos>/cft-fp256/README.md:13-16` | `platforminfo` on the build machine |
| H2 | The card is in `amd-arc-box`, a separate physical Linux machine | READ | `<repos>/cft-fp256/CLAUDE.md:43-45` | `xbutil examine` on that machine |
| H3 | Vitis 2022.2 is installed on `amd-arc-box` | READ | `<repos>/cft-fp256/CLAUDE.md:50` | `v++ --version` there |
| H4 | Logan's card has no network port; communication goes over the PCIe link | READ | Logan, 2026-11-21, in [ROADMAP.md](../ROADMAP.md) | a look at the card |
| H5 | cft-fp256's card-day record describes an image with "one HBM pseudo-channel per master" | READ | `<repos>/cft-fp256/docs/CARDDAY.md:171` | that project's link configuration under `hw/` |
| H6 | The HBM is 8 GB in 32 pseudo-channels of 256 MB | SURVEY | the report, "Fabric is plentiful" | `platforminfo` on the build machine |
| H7 | Under the shell the user region has about 704K LUTs and 4,920 DSP slices, 2,352 of them in SLR0 and 2,568 in SLR1; other sources give 744,638 LUTs and 5,936 to 5,948 DSPs, the 5,936 from a search summary | SURVEY | the report, "Fabric is plentiful" (the report flags the conflict) | the utilisation report of the first build |
| H8 | If H6's "256 MB" means 2^28 bytes, one channel holds 134,217,728 samples of 16 bits, and 8 GiB holds 4,294,967,296 | COMPUTED | 2^28 / 2 and 2^33 / 2 | whether "256 MB" is 2^28 bytes: read it from `platforminfo` |
| H9 | Neither `iverilog` nor `verilator` is on this desktop's Git Bash PATH; Python 3.12.15 is | MEASURED | `which iverilog verilator; python --version`, 2026-11-21 | a rerun |
| H10 | cft-fp256's RTL suite is cocotb, run under Icarus by default and Verilator while iterating | READ | `<repos>/cft-fp256/CLAUDE.md:109-118` and `:233-236` | that project's `tb/Makefile` |
| H11 | cft-fp256 builds its kernel at 135 MHz. That is a different design and bounds nothing here | READ | `<repos>/cft-fp256/CLAUDE.md:66` | not applicable to this design: only its own first build says what closes |
| H12 | All 32 HBM pseudo-channels attach to SLR0 only | SURVEY | the report, "Fabric is plentiful" | `platforminfo`, and the first build's placement |

## 4. The system

One instrument, built so that the experiment is a replay.

```
 source  ---->  injector  ---->  detector core  ---->  scorer  ---->  records
 (replay from    (adds known      (filter bank,         (threshold,    (to HBM, read
  HBM, or the     pulses, emits    rectifier, pool,      histogram,     back over PCIe)
  on-card noise   a truth record   small dense head)     event capture)
  generator)      the detector          ^
                  never sees)           |
                                   weight store  <----  learner
                                   (active and shadow    (phase A: the host, over PCIe;
                                    copy, atomic swap)    phase B: in the fabric)
```

- **Source.** Either a recorded stream replayed from HBM, loaded over PCIe, or a seeded noise generator on the card. Both are deterministic, so any run can be repeated bit for bit.
- **Injector.** Adds pulses of known shape and amplitude at scheduled sample indexes, and writes a truth record for each. The truth record is the label. It goes around the detector, never through it.
- **Detector core.** A bank of K filters of T taps whose coefficients are data, then a rectifier, a pooling stage and a small dense head, producing one score per input sample. In its **matched-filter configuration** (one filter, the rectifier and the pooling stage set to pass through, the head passing that filter's output as the score) the datapath is the classical matched filter, so the baseline and the learner share one piece of hardware. Any other configuration is a different test, with a different curve (row D11).
- **Scorer.** Compares the score with a threshold register, keeps a histogram of scores, and captures an event record with the samples around it when the threshold is crossed.
- **Weight store.** Every coefficient has an active copy and a shadow copy. New weights are written to the shadow and become active at one sample boundary. This is the one mechanism taken from OpenTPU (row S1).
- **Learner.** Phase A: the host reads captured windows and their truth records, trains in floating point, quantises, checks the candidate on held-out data, writes the shadow weights and commits the swap. Phase B: an update rule in the fabric, applied per labelled window.

**Replay stands in for duplicate hardware.** Because the stream is repeatable bit for bit, a frozen baseline is a second pass over the same stream with the frozen weights, not a second detector on the card.

**"Any given input with a properly configured model."** The core's contract is narrow on purpose: a stream of fixed-point samples in, one score record per sample out. A model is a configuration blob: a shape inside the synthesised maxima, plus the weights, with a hash. A different signal domain is a different blob and a different front-end setting, not a different bitstream. A blob the bitstream cannot run exactly is refused by name.

## 5. The contract

- **Two outcomes only.** A shape past a synthesised maximum, a non-zero reserved bit, a blob whose hash does not match, a swap committed while one is pending: each is refused with its own name. Reserved fields are checked, never ignored.
- **Capability bits are generated** from the same definitions the refusals read, so a bitstream cannot advertise what it would refuse.
- **No silent saturation.** A filter's sum cannot overflow (row D4). Every width after it gets its own argument when the pooling stage and the head are designed. Where a width is a choice, overflow raises a sticky flag in the score record.
- **A swap is defined per output sample.** The reference model says which outputs use the old weights, which the new, and whether any mix the two. Every score record carries the weight epoch, and any mixed output is flagged and left out of the statistics.
- **A learner update that rounds to zero is counted.** A counter records every update lost below one least significant bit, so a learner that has silently stopped learning is visible (row S4).
- **One definition, generated copies.** Shapes, widths, the register map and the record formats live in one file. The SystemVerilog package, the C header and the Python constants are generated from it, with a `--check` that fails on drift.

## 6. The proposed shape

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| D1 | Samples are 16-bit signed, one channel to start | DECISION | proposed here | a first target that needs more channels or more bits |
| D2 | Coefficients are 18-bit signed, one DSP48E2 multiplier per tap | BELIEVED | the DSP48E2 has a 27 by 18 signed multiplier and a 48-bit accumulator; from memory, not from a committed quote | AMD's UG579, and the synthesis report showing one DSP per tap |
| D3 | A first bank of K = 16 filters of T = 128 taps uses 2,048 multipliers | COMPUTED | 16 x 128 | arithmetic |
| D4 | The worst-case sum of one filter fits 41 signed bits | COMPUTED | largest magnitudes 2^15 and 2^17, product 2^32, 128 of them 2^39, plus a sign | an overflow test at the extreme inputs in the reference model |
| D5 | The target is one score per input sample per clock. The clock is unknown until this design's first build closes | ESTIMATE | nothing measured; 135 to 300 MHz is the range used in D6 | the first build's timing report |
| D6 | One 256 MiB channel replays in 0.99 s at 135 MHz and 0.45 s at 300 MHz | COMPUTED | 134,217,728 / 135e6 and / 300e6, from H8 and D5 | the measured clock, and a counted run on the card |
| D7 | The noise generator's tails bound the lowest false-alarm rate that can be claimed from on-card noise | BELIEVED | a generator whose tails are thinner or cut off produces too few large scores | a tail-quantile test of the generator against the Gaussian at the claimed depth |
| D8 | For a pulse s known in shape and amplitude, in white Gaussian noise of known standard deviation sigma, tested at a known arrival time, the matched filter is the optimal detector, and Pd = Q(Q^-1(Pfa) - d) with d = norm(s) / sigma | COMPUTED | restated 2026-11-23. The optimality, and the two Gaussian distributions of the test statistic, are READ in a primary source: Oppenheim and Verghese, MIT 6.011 class notes, chapter 14, section 14.2, read by the lead through text extraction. That chapter does not write the closed form: it is worked from those two distributions, in two lines. Both are in [sources/D8.md](../sources/D8.md), rows P1 to P4 and C1; one secondary page writes the formula whole (rows S1 to S3) | an error in those two lines; a typeset reading of the chapter that differs from the extracted text; stage E0's curve, which round 1's software run found inside the tolerance at five amplitudes (`docs/VALIDATION.md`, 2026-11-23) |
| D9 | With 10,000 injections at one amplitude, the standard error of a measured efficiency is at most 0.5 percentage points | COMPUTED | sqrt(0.25 / 10000) = 0.005 | arithmetic |
| D10 | From one pass over one 256 MiB channel, a per-sample false-alarm probability below about 7.5e-8 has fewer than ten expected false alarms and is an extrapolation. Neighbouring scores of a 128-tap filter are correlated, so ten false alarms are fewer than ten independent events and this floor is optimistic | COMPUTED | 10 / 134,217,728, from H8 | arithmetic; the correlation by a counted run |
| D11 | Outside the matched-filter configuration D8 does not apply: with an absolute-value rectifier after the filter, the detection probability at a false-alarm probability of 0.01 and d = 1.75 is 0.2045, where D8 gives 0.2822 | COMPUTED | restated 2026-11-23. Both figures are exact: `python -c "from stats.theory import *; print(pd_matched(0.01, 1.75), pd_rectified(0.01, 1.75))"`. The committed script `python -m stats.d11` (a 128-sample windowed sine, sigma = 2, 400,000 trials, seed 20261123) finds 0.2827 and 0.2051. This row first quoted 0.284 and 0.206 from a verifier's script that was not in the tree; 0.284 is D8 at d = 1.7553 | the script's figures leaving the tolerance of the exact ones: `tests/test_stat_d11.py` runs it in the gate |

**D8 has four limits of its own.**

- *Arrival time.* The formula is for a test at a known arrival time. A detector sliding over a stream is a different test: its false alarms are counted per unit time and its efficiency is "found within a window of the injection". So stage E0 compares against the formula only at the injected sample index, and reports the sliding found-rate separately, against the foreign implementation.
- *Configuration.* It holds for the matched-filter configuration of section 4 only (row D11).
- *White noise.* For coloured noise the optimal filter whitens first, and d^2 becomes the quadratic form of s in the inverse of the noise covariance. That is believed, textbook and uncommitted, like D8 itself, and stage E2's noise-colour change needs it.
- *Real numbers.* The formula assumes real-valued Gaussian noise and exact coefficients. This design has 16-bit integer samples, 18-bit coefficients and a generator with imperfect tails (D7). The foreign implementation, run on the same integer stream with the same quantised coefficients, is what separates the cost of quantisation from an error in the fabric.

## 7. What the survey says, and how far to trust it

These rows shaped the proposal. None has been checked against its source by the lead.

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| S1 | OpenTPU has had no push since 2017-12-06, its weight DRAM is a simulation stub with no host write path, and each of its multiply-accumulate units holds two weight buffers so a new set can be staged | SURVEY | the report, "OpenTPU's weights-as-data design" | a read-only survey of the OpenTPU repository at a named commit |
| S2 | No published measurement of weight hot-swap latency on an Alveo-class card was found, nor any FPGA work using HBM as a replay store | SURVEY | the report, "Host-trains, FPGA-swaps" and "Fixed-point learning fails silently" | a later search that finds one; an absence is the weakest kind of finding |
| S3 | In one mock data challenge, at one false alarm per month, the best learned searches reached up to 95% of matched-filter sensitive distance in Gaussian noise and 70% in real noise; two CNNs that reached 40 to 95% on Gaussian noise scored zero on real noise | SURVEY | the report, "Parity in Gaussian noise" | the challenge paper itself |
| S4 | In one fixed-point LMS design, updates below one least significant bit truncate to zero, so a filter below that amplitude floor can train to all-zero coefficients with nothing flagging it. The source is a preprint of unknown review status | SURVEY | the report, "Fixed-point learning fails silently" | the preprint; and this project's own reference model |
| S5 | One model trained on ten days of real gravitational-wave noise held a stable detected fraction across the following ten months | SURVEY | the report, "Labels that do not come from the model" | the paper itself |
| S6 | Injecting synthetic signals into live noise is the best-evidenced way to keep a detector trained. On one long, continually changing benchmark, all but one state-of-the-art unsupervised adaptation method eventually fell below the unadapted model, and a periodic reset matched or beat them. Adding a replay buffer and a frozen reference copy is the report's own inference, not a finding it cites | SURVEY | the report, "Labels that do not come from the model" | the cited papers |

What follows from them, as the lead's reasoning: S1 is why OpenTPU is a reference and not a base. S3 and D8 are why the first target has a known optimum. S5, though it is one model, is why drift is induced on purpose in stage E2. S6 is why labels come from the injector and never from the detector's own detections.

## 8. The experiment

Four stages. Each names what its result would and would not show.

- **E0, calibration. No learning.** Coefficients are set to the matched filter for one known pulse in on-card white noise. It runs in the matched-filter configuration. Injection recovery must reproduce the analytic curve of D8 at the injected index, within the binomial error of D9 plus the quantisation cost the foreign implementation measures on the same stream. *Shows:* the instrument and the counting are right. *Does not show:* anything about learning.
- **E1, the learner converges.** The coefficients start blank. Labels come from the injector. *Shows:* whether the learner reaches E0's efficiency, and how many labelled windows it takes. *Does not show:* a gain over the classical detector. Matching E0 is the best possible result, by D8.
- **E2, induced drift.** Mid-run, the pulse shape or the noise colour changes. Five models see the same stream: frozen; frozen with only its input scaling updated; adaptive; periodically reset; and the matched filter for the new condition (the whitened one, if the noise colour changed). *Shows:* whether adaptation recovers events the frozen model misses, at an equal false-alarm rate. This is the "missed events" result, on easy mode.
- **E3, a recorded stream.** Real noise from HBM, with injections. Seismic archives are the candidate. Not designed here.

**The comparison rules, for every stage.** They are the lead's synthesis of practice in the survey; no published protocol for an adapting detector was found.

1. The injection set is fixed and committed, with its hash, before the run.
2. The stream is split by time into periods the learner trains on and periods it never trains on.
3. After every weight change the threshold is set again from signal-free noise. Models are compared at an equal false-alarm rate, never at an equal threshold. Without this, a lower effective threshold looks like better sensitivity.
4. A false-alarm rate below the floor of D10 is labelled as an extrapolation.
5. The model version that is reported is named before the run. Reporting the best of many snapshots is a selection effect.

## 9. Gates, and the negative control each one needs

A gate nobody has watched fail is not a gate. Each of these names the faults its control plants. A control plants a list of shapes and no others, so each list is a stated limit: a gate broken for a shape that is not planted passes its control. Every gate also carries a positive case, a correct build that must pass, and refuses a comparison of zero words.

| gate | what it holds | its negative control | the way it could pass while testing nothing |
|---|---|---|---|
| reference model | the model's score words equal committed known-answer vectors, and agree with the foreign implementation to its stated tolerance | a model with one changed rounding must miss a vector | vectors generated by the model they then judge |
| bit identity | RTL, host and card each equal the reference model on every score word | one flipped coefficient bit, on each side in turn, must be reported, on a stream and a configuration where that tap reaches the score unmasked | comparing detections above threshold instead of raw score words; a rectifier, a pool or a zero head weight hiding the flip |
| truth isolation | no path from the truth record to any output record: score, histogram or event | the same samples with different truth records must give identical outputs, and a core wired to read truth must be caught | a test with no injections; a comparison of scores only |
| injection | the injector adds what the truth record says, where it says | an injector that adds nothing, one a sample late, one with the sign flipped and one at half amplitude must each be caught | zero-amplitude injections |
| swap | every output uses the weights its epoch field names | a swap that changes half the taps a clock late must be caught | swapping in the weights already active |
| refusal | every shape, bit, blob and pending swap outside the contract is refused, with its own name | one build per refusal that accepts the case, and one that refuses it under the wrong name, must each be caught | a suite with no refusal cases; a check of "refused" that ignores the name |
| capability bits | a bitstream advertises exactly what it accepts | a build that advertises a shape it refuses must be caught | reading the advertisement and the refusal from one constant in the test itself |
| generated copies | the SystemVerilog, C and Python constants each equal the one definition | one edited constant in each generated file in turn must fail `--check` | a `--check` that no stage runs, or that covers two of the three |
| overflow | no accumulator overflows at the extreme inputs, and the sticky flag rises where a width is a choice | a core one bit narrower must raise the flag, or be caught | a test whose extreme inputs are not the extremes |
| replay | two runs of the same stream, seed and weights give identical records | a run with one changed seed bit must differ | comparing a run with itself |
| noise tails | the generator's quantiles match the Gaussian to the depth a false-alarm claim needs | a generator with clipped tails must fail at that depth | a test that stops at a depth every generator passes |
| scorer | threshold crossings, the histogram and event records equal the reference model's | a threshold off by one, and a histogram that drops its last bin, must each be caught | a stream with no crossing |
| statistics | the measured efficiency matches D8 within the stated tolerance, in the matched-filter configuration | a coefficient set whose predicted efficiency is outside the tolerance by a stated margin must fall outside | a tolerance so wide that any detector passes |
| learner | the fabric's weights after each update equal the reference model's, and the lost-update counter equals the model's | a learner that does nothing, and one that rounds the other way, must each be caught against a model that does change the weights | a learning rate so small that every update rounds to zero in model and fabric alike (row S4) |
| comparison rules | the rules of section 8: the injection set's hash is committed before the run, and models are compared at an equal false-alarm rate | a run whose injection set differs from the committed hash must be refused, and so must a comparison made at an equal threshold in place of an equal false-alarm rate | a hash recorded after the run; a threshold that happens to give both models the same rate |
| provenance | a bitstream carries its commit, its clock as applied and its timing result | a bitstream from another build must be refused, and the right one accepted | a manifest written by hand; a checker that refuses everything |

## 10. How the work could be split

This is a candidate only. The split is settled in a plan, after this design is approved, and the plan goes past a verifier before it comes to Logan.

**P0, the lead's, before any parcel.** Three things every piece would touch: the one definition file with its generator and `--check`; the score, truth and event record formats; and the reference model's package skeleton with the gate stages that run it.

| candidate parcel | what | builds on |
|---|---|---|
| MOD-A | reference model: the noise generator, replay, the injector and truth records | P0 |
| MOD-B | reference model: the detector core, the scorer and the histogram | P0 |
| STAT | the statistics harness: the committed quote for D8, the foreign floating-point implementation, the injection-recovery count | P0 |
| RTL-A | RTL source and injector, with benches against MOD-A | MOD-A |
| RTL-B | RTL detector core and weight store, with benches against MOD-B | MOD-B |
| HOST | host library: a software backend that replays the reference model's vectors, then the XRT backend | MOD-A, MOD-B |
| KRNL | kernel packaging, the build script and the manifest, following cft-fp256's flow | RTL-A, RTL-B |
| LRN-A | the learner in the reference model, and the host trainer of phase A | MOD-B, STAT |
| LRN-B | the in-fabric learner of phase B | LRN-A, RTL-B |

The card day is the lead's and Logan's. Seam tests belong to the lead: the first is the injector feeding the detector core, which no single parcel above owns.

## 11. Limits of this draft

- Nothing is built. No row about this design is MEASURED: each is COMPUTED, ESTIMATE, BELIEVED or a DECISION.
- The survey behind section 7 was not controlled, and two of its assumptions were already wrong for this setup: a Windows host and a network port. The verifier checked each SURVEY row against the report, not against the papers the report cites.
- The pooling stage, the dense head, the noise generator's method, the learner's update rule, the host trainer and its quantiser are named, not designed. Each is a design-first item for its parcel. Stage E3 is not designed at all.
- How the HBM's 32 channels are presented to a kernel under this shell is not established (H5 is a READ about another design, H6 a SURVEY). The replay length per pass in D6 assumes one channel, and H8 assumes "256 MB" means 2^28 bytes.
- **Placement is open.** By H7 and H12 the HBM attaches to SLR0, which offers 2,352 DSP slices, and the first bank alone wants 2,048 (D3). Either the bank nearly fills SLR0's multipliers or the stream crosses to SLR1. Nothing here says which closes timing.
- D10's floor treats scores as independent. They are not.
- Logan allowed this project the WSL environment, `amd-arc-box` and daytime card windows on 2026-11-21 (question 4). cft-fp256 holds standing bookings on the card, so card time is still booked.
- No source text has been committed for D2 or D8, and section 2 leans on D8 as an authority all the same. Until the quote is committed, stage E0 has only the foreign implementation to stand on.
- D11's figures come from a verifier's script that is not in this tree.
- The gates of section 9 are named, not built. Each control plants a fixed list of faults, and a gate broken some other way passes it.

## 12. Questions for Logan

Each has a recommendation, what it rests on, and what would show it wrong.

1. **The first target.** *Recommended:* a known pulse in on-card white noise (stages E0 to E2), with a recorded seismic stream as E3. *Rests on:* D8 gives a known optimum to measure against, and the injector gives exact labels. *Shown wrong if:* the generator's tails (D7) cannot support a useful false-alarm depth, in which case recorded noise moves forward.
2. **The hardware language and flow.** *Recommended:* SystemVerilog with cocotb benches and the Vitis RTL kernel flow, as cft-fp256 uses on this card (H1, H10). *The alternative:* PyRTL, which OpenTPU is written in. *Rests on:* the flow being proven on this card, and S1. *Shown wrong if:* S1 does not survive a read of the OpenTPU repository, or building on OpenTPU's own code matters to you more than this draft assumes.
3. **Which learner first.** *Recommended:* phase A, the host trains and the fabric swaps, then phase B in the fabric on the same core. *Rests on:* the host can check a candidate before any swap, and S2 says the swap latency is itself unmeasured. *Shown wrong if:* the PCIe round trip is too slow to label the experiment at all, which the first card run measures.
4. **Machines and the card.** May this project simulate in the `cft2204` WSL environment, build on `amd-arc-box`, and book daytime card windows through the TimeSheet, with only the lead touching the box and the card? *Recommended:* yes, on those terms. *Rests on:* cft-fp256's practice. This one is yours alone to grant.
5. **Standing rules.** [ROADMAP.md](../ROADMAP.md) lists the rules proposed to carry over from cft-fp256. *Recommended:* carry them. Strike any that should not bind here.
6. **Committing.** The repository is initialised and nothing is committed. *Recommended:* the lead commits this setup once the verifier's findings are answered, with no remote and no push until you name one.

## Logan's answers (2026-11-21, verbatim)

> I've reviewed it, all are approved with the recommendations and you may create a remote with gh and push AOTPU was intended to stand for 'Adaptable OpenTPU', however I was unaware how outdated it had become by this point. So if you have name suggestions which better align with my typical naming I'd be open to them

All six questions are settled as recommended. The lead's reading of each is in [ROADMAP.md](../ROADMAP.md). The rows marked DECISION in section 6 were not among the questions and stay proposals until a plan fixes them.

## Rows restated after approval, and evidence that arrived (2026-11-23, the lead's)

Logan approved this design on 2026-11-21 as it then stood. Two rows named, in their own last cell, what would move them. Round 1 produced both, and the rows are restated above. What each said before is kept here.

- **Row D8** was BELIEVED, its source "textbook detection theory ...; no quote is committed yet", to be moved by "the committed quote; then stage E0's curve and the foreign implementation". The source is committed in [sources/D8.md](../sources/D8.md). It is not the book this row named, which was not opened: it is a chapter of class notes, read through text extraction, which states the optimality and the two distributions and does not write the formula. So the row is COMPUTED from what was READ, and says so. Stage E0 has been run in software and the foreign implementation exists (`stats/`).
- **Row D11** was BELIEVED, quoting 0.206 and 0.284 from a verifier's script that was not in the tree, to be moved by "a committed script that reproduces both figures". The script is `stats/d11.py`. It does not reproduce those two figures: the exact ones are 0.2045 and 0.2822, and the first quotation's 0.284 belongs to d = 1.7553. The row now gives the exact figures.
- **Section 2's first authority** said row D8 "is BELIEVED until its source is committed". Restated with the row.

Evidence that arrived and changed no row, because the row is a DECISION or the change is Logan's:

- **Row D1**, 16-bit samples on one channel. The first look at real records ([D1b](D1b-first-look.md)) found three components a station and, in two of 25 files, samples that need 17 bits. The definition carries a second profile of 24 bits and three channels, and the model runs under both. Whether D1 changes is put to Logan at the round's close.
- **Row D7**, that the generator's tails bound the lowest false-alarm rate that can be claimed. The generator's tail was counted to 5.42 sigma a side over 2^30 draws and its table checked to its last entry. Parcel MOD-A's finding stands beside the row: the generator's tail is one bound and not the bound, since a score's tail also needs the samples to be independent, which no single-sample test shows.
- **Section 4's "small dense head".** The model's head is one linear layer with no bias. It cannot represent a detector that needs a hidden layer. Accepted by the lead for round 1 as a stated limit, and put to Logan.

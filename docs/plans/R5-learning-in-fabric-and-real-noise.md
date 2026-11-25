# Round 5: learning in the fabric, and real noise - the draft plan

Drafted by the lead on 2026-11-25 on Logan's word after round 4's push: "Begin drafting round 5's plan, the faster host and 200mhz goal can wait till later. Focus on proving things for now rather than speed". This is the first draft. Nothing of round 5 starts before his approval.

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. An ESTIMATE or SURVEY figure drives no decision here until it is measured.

## What binds it

- **The design:** `docs/studies/D0-rough-design.md`, approved by Logan on 2026-11-21. Its section 4 names two phases of learning: phase A, where "the host reads captured windows and their truth records, trains ..., writes the shadow weights and commits the swap", and phase B, "an update rule in the fabric, applied per labelled window". Its section 8 names four stages, E0 to E3. Its section 9 names sixteen gates.
- **His words**, in the ROADMAP's "Logan's words, as given": "I prefer to work with real data when able" (2026-11-21); the goal of weights "adaptable while retaining the speed of FPGA fabric and memory" (2026-11-21); and the word that opens this draft.
- **The lead's reading of "proving things rather than speed":** the round adds claims that rest on an authority, the model for the fabric and `stats/` for sensitivity. It adds no speed, and no new card image unless a proof needs one.

## What rounds 1 to 4 leave

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| L1 | Phase A is built and on the card: the host trains, writes the shadow weights over registers and commits a swap at a named index; on the card a swap lands at its index | READ | `docs/VALIDATION.md`, round 3's card-day entry, row W3 read against what was measured; `docs/studies/CARD-first-light.md`; `spec/undertone.toml`, `shadow_begin`, `shadow_data`, `commit_at` | those files |
| L2 | **No learning is in the fabric.** D0's gate "learner" has no row in the registry; the registry has 15 rows, for 14 of D0's sixteen gates, provenance being the other without one | READ | `docs/ROADMAP.md`, "Where the project stands", the registry's restatement; `tests/gates.toml` | the registry |
| L3 | The learning rule is the difference of two class means in exact integers: two sums of windows and two counts, `w = S[1]/n[1] - S[0]/n[0]` as exact fractions, with no step size and no float | READ | `learn/trainer.py`, `MeanDifference` and its docstring | that file |
| L4 | A label-1 window is frames j to j + T - 1 for a truth index j, and a label-0 window frames j - T to j - 1 | READ | `learn/trainer.py`, its docstring | that file |
| L5 | The model's quantiser is exact integer arithmetic: each value v becomes `round_half_even(v * COEFF_MAX / m)` for the set's largest magnitude m, worked as one fraction a value | READ | `model/weights.py`, `quantise` | that function |
| L6 | So a weight set the learner hands over is a function of integer sums and counts alone: for each tap, D = S1 x n0 - S0 x n1, then `round_half_even(D x COEFF_MAX / max abs D)`. No division is needed until the last step, one a tap | COMPUTED | L3 and L5: S1/n1 - S0/n0 = D / (n1 n0), and the factor 1/(n1 n0) cancels in the ratio to the peak | arithmetic; a vector worked by hand |
| L7 | The core's delay line holds the last T samples; at the score of index i its window is frames i - T + 1 to i | READ | `docs/model/conventions.md`, CV2 | that convention |
| L8 | So both of a truth record's labelled windows pass through the delay line: the label-0 window is its whole content at index j - 1, and the label-1 window at index j + T - 1 | COMPUTED | L4 and L7 | the model |
| L9 | The kernel alone after synthesis in round 3's third link: 329,499 LUTs, 37.80% of the chip's; 729 DSP slices of 5,952 | READ | `docs/ROADMAP.md`, row R7 | that report |
| L10 | Stage E1 in software: the learner reaches the matched filter's efficiency, 0.49492 against 0.50026; stage E2 in software: after a change of pulse shape, the adaptive and reset models each recover about 0.36 of the injections the frozen model misses | READ | `docs/studies/E1-software.md`; `docs/studies/E2-software.md` | those records |
| L11 | Stage E0 on the card: every record of 20 pieces is the model's, and every count round 1's | READ | `docs/studies/CARD-e0.md` | that record |
| L12 | The fabric's injector holds `e0` alone and refuses the definition's `e1` by name, so stage E2 on the card needs an RTL change and a new image | READ | `docs/rtl/source.md`, limit 7 | that file |
| L13 | A link of the kernel for the U50 took 4 h 24 min to 6 h 06 min on the box, three times | READ | CLAUDE.md, trap 19 | the next link |
| L14 | D0's stage E3 is "a recorded stream. Real noise from HBM, with injections. Seismic archives are the candidate. Not designed here" | READ | D0, section 8 | that file |
| L15 | Study D3's records came from SCEDC: HHZ at 100 samples a second at four stations through 2024, the service's terms read before any request; the records are not in the tree | READ | `docs/studies/D3-faint-launches.md`, rows F17 and F18 | that study |
| L16 | Real records hold samples that need 17 bits | READ | `docs/studies/D1b-first-look.md`, row M6 (MEASURED there) | those records |
| L17 | D8, the textbook efficiency, holds for white Gaussian noise of known level; stage E1's paired comparison assumes Gaussian scores | READ | D0, row D8; `docs/studies/E2-software.md`, "Which authority this rests on" (the paired derivation LRN-A wrote for E1 "assumes Gaussian scores") | those files |
| L18 | D0's gate "truth isolation" holds "no path from the truth record to any output record: score, histogram or event" | READ | D0, section 9 | that table |
| L19 | Round 4 ran from its plan's first draft at 10:45 to its push at 16:03 on 2026-11-25, with two parcels and seven verifier passes on Sonnet, which found 17 of 19 planted faults | READ | `git log`; `docs/VALIDATION.md`, round 4's entries | that record |

## What round 5 could be

**A. Learning in the fabric, in simulation: D0's phase B.** The learning rule of L3 built in RTL beside the core. It takes each truth record's two windows from the delay line as they pass (L8), adds them to two sums with two counts, and at an index the host names it makes the weight set of L6, writes it into the shadow and commits it. In simulation, held against the model word for word, as rounds 2 and 3 held the chain. *Shows:* that the rule the project learns by runs in fabric and gives the model's weights, exactly; D0's learner gate gets its row and its control. *Does not show:* anything on the card, or any new fact about sensitivity, since the weights equal the model's and E1's result already holds for them. **Its direction is not known in advance in one respect:** what it costs in fabric, and whether one update finishes between two named indexes.

**B. Stage E3 in software: real noise.** Round 4's B'. Recorded seismic noise through the model's replay source, with injections of `e0`, the learner of E1 against the matched filter, at an equal false-alarm rate measured from signal-free scores. *Shows:* whether the learner reaches the matched filter's efficiency on real noise, which D8 cannot predict (L17). *Does not show:* anything in fabric, or that a real faint event is found. Its costs:
- **a judge**, since D8 does not apply and E1's paired comparison assumes Gaussian scores. A paired test that assumes nothing of the noise, on the two models' hits on the same injections, is in `stats/`'s line of work, written there with its own control;
- **a rule for the noise**, frozen before any record is fetched: which stations, which days, and how stretches holding an earthquake or another event are kept out (D0, section 2's limit that a recorded stream's content is unknown);
- **a sample format**, since real samples need 17 bits (L16): the 24-bit profile, or a fixed scaling into 16 bits, chosen before any record is read.

**C. Stage E2 on the card.** The fabric's injector taught `e1`, a new link, and a card day on which the drift run with its sixteen swaps equals the model's. *Shows:* phase A's adaptation on the card, bit for bit, over a long run with many swaps. *Does not show:* learning in the fabric. Its cost: an RTL change to round 2's verified injector, and a link of 4 h 24 min to 6 h 06 min (L13). **If A comes first, one link can carry both A's learner and C's injector**, and a later card day can run phase B and stage E2 together.

**D. The provenance gate's row.** Its check exists in the build's manifest (round 3), and its row would need a test the gate can run without the box. Small, and proves nothing new about the detector.

**Recommended: A and B, in parallel.** They share no file: A is the model's learner schedule and RTL under `rtl/`, and B is the replay of real noise, `stats/` and a study. A is the project's central claim, weights that adapt in the fabric, held to the model. B is his "real data", where the instrument's answer is not known in advance. C waits for A, so that one link serves both. D is left for a round with a build.

## Track A: learning in the fabric, in simulation

- **The model first.** The model is the authority, so the fabric's learner is first written in the model, as a schedule the model can run in a stream. It takes windows from the delay line at the two indexes of each truth record (L8). It makes the weight set by L6 at a named index, and commits it at a later named index. **It refuses by name an update that cannot finish in time**, and counts what it drops. D0's learner gate names "the lost-update counter". The model's rule must give exactly `learn.trainer.MeanDifference` and `model.weights.quantise`'s set for the same windows: a test holds that, so phase A and phase B are one rule.
- **What the fabric needs that the core has not got:** the truth records (the injector has them); two sums of T words of 64 bits and two counts; a multiply of a sum by a count; a largest magnitude; and one exact division a tap with the model's rounding. The division is done one tap at a time, between two named indexes, about 16 clocks a tap (T2). How many clocks that takes, against the frames between two indexes, is the design's to measure.
- **D0's truth isolation, restated.** The learner reads the truth records, so a truth record reaches the score through the weights. The plan proposes that the gate's claim become: **no path from the truth record to any output record except through a commit the host names**, and that its control plant the path the restatement allows, a commit at an unnamed index, as well as the paths it forbids. Question 3 asks him.
- **The gate "learner", with its control:** the fabric's weights after each update equal the model's, and its counters equal the model's. A learner that does nothing, one that rounds the other way, and one that drops the last window must each be caught, against a model that does change the weights (D0's own list, and its warning, row S4).
- **The cost, measured:** the learner synthesised out of context, as the head was in round 2, for its LUTs, DSP slices and memory against L9's room.
- **The parcels**, each designed first and ruled by the lead before it builds:
  - **LRN-B**, the model's phase-B schedule and its software tests;
  - **RTL-L**, the learner in RTL, its benches against LRN-B's model, its mutants, and the gate's row.
  RTL-L builds on LRN-B's ruled design, as round 2's RTL built on the model.

## Track B: stage E3 in software, real noise

- **The parcel E3S**, designed first, then built:
  - the noise rule, frozen and hashed before any record is fetched (L15's service, or another whose terms are read whole first);
  - the records fetched and logged with each file's source, size and hash, and none committed;
  - the replay through the model's source, at the sample format chosen;
  - the injection set committed with its hash; the learner of E1 and the matched filter for `e0`, each at its own threshold measured from signal-free scores of that noise;
  - the judge.
- **The judge.** A paired comparison of the two models' hits on the same injections, which assumes nothing about the noise, written in `stats/`. It is `stats/`'s own code, with its own control, and imports nothing of `model/` (the independence stage holds that). Beside it, each model's false-alarm rate on held-out signal-free stretches, which on real noise is measured, not assumed.
- **Its named controls:**
  - the learner given windows from the stretches it is judged on must be refused, as E1's rule 2 refuses it;
  - a comparison at an equal threshold must be refused, as E1's rule 3 refuses it;
  - and the judge must report a model that finds a stated fraction fewer injections as worse, on a stream where it is.
- **The full run is the lead's,** booked if it is ten minutes or more.

## The waves

| wave | what | whose | waits for |
|---|---|---|---|
| 0 | the round's branch `r5`, cut from `main` | the lead | approval |
| 1 | LRN-B's design, then its build; E3S's design, then its build | parcels | wave 0 |
| 2 | RTL-L's design, on LRN-B's ruled design; then its build | a parcel | LRN-B's design ruled |
| 3 | the learner's synthesis out of context, on the box; E3S's full run | the lead | RTL-L merged; E3S merged |
| 4 | the round's close: its verifier, the narrow passes, VALIDATION.md, the ROADMAP | the lead | wave 3 |

## What the round is for

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| W1 | In simulation, the fabric's learner gives the model's weight set, word for word, after every update, under both sample formats, and the model's phase-B set equals phase A's for the same windows | BELIEVED | L3, L5, L6: the rule is integer arithmetic, and the RTL has matched the model in every round | RTL-L's benches |
| W2 | D0's learner gate has a row and a control that the gate runs | DECISION | the plan's track A | the registry |
| W3 | On real seismic noise, the learner of E1 is compared with the matched filter at an equal measured false-alarm rate, by a judge that assumes nothing of the noise | DECISION | the plan's track B | E3S's full run |
| W4 | Nothing earlier breaks: both sizes of the gate pass at the round's end, with the two inner checks of the card day's record still skipped by name, E0C-CARD-STALE | BELIEVED | each round so far | the gate |

## Other figures

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| T1 | The learner's state for T = 64 taps under 16-bit samples is two sums of 64 words of 64 bits and two counts, about 8 kbit | COMPUTED | 2 x 64 x 64 = 8,192 bits, from L3 and the trainer's 64-bit sums | RTL-L's design |
| T2 | One update divides once a tap, 64 times. Each quotient is at most COEFF_MAX, 32,767, so a divider that makes one quotient bit a clock needs about 16 clocks a tap, and about 1,000 clocks an update with the peak's search and the shadow's writes | ESTIMATE | 64 taps x (15 quotient bits + 1 for the rounding); the quotient's bound from L5, every value's magnitude at most m; the rest of the update not yet designed | RTL-L's design and its benches |
| T3 | At 20 clocks a frame (`docs/rtl/source.md`'s source rate, round 3's L12) that is about 50 frames, under half of one of E1's trials of 128 frames | COMPUTED | 1,000 / 20; 50 / 128, from T2 | T2 measured |
| T4 | A stretch of real noise as long as E1's full part, 25.6 million frames, is about 71 hours at 100 samples a second | COMPUTED | 25,600,000 / 100 / 3,600, from L15 | arithmetic |
| T5 | The round takes one to two days by the clock | ESTIMATE | L19, with three parcels against round 4's two, and an RTL parcel like round 2's | the round |

## How the round is held

As round 4, with what it taught:
- **Parcels and verifiers by name in every dispatch.** Round 4's were parcels on Opus and verifiers on Sonnet, by his word for that round; question 5 asks again.
- **Each parcel designs first, and the lead rules before it builds.**
- **Every verifier works on a sealed clone with faults the lead planted** in files the tip commit changes, and each fix goes back to the verifier that found it.
- **A comment in a file the build-line list names is not free to add lines** (round 4's slip, VALIDATION.md). RTL-L's mutants and RTL comments follow that.
- **A long run is made on the commit the merge then takes,** or the diff on what it reads is shown empty (round 4's rule).
- **The TimeSheet before every run;** bookings for runs of ten minutes or more; cft-fp256's lead told before heavy desktop runs and any use of the box.

## What this plan does not settle

- **Whether one update finishes between two named indexes** at the rates the stream runs (T2, T3): RTL-L measures it in simulation. If it does not, the design refuses the update by name and counts it, and the gate holds the count.
- **What the learner costs in fabric:** the synthesis in wave 3 measures it. Whether it fits beside the kernel in one image is a later link's question.
- **What real noise does to the learner:** that is what track B is for. A stretch of real noise holds events no one injected (D0, section 2), and the noise rule keeps out what it can name, not what it cannot.
- **Nothing here runs on the card.** Stage E2 on the card, and the learner on the card, wait for a link that carries both (route C).

## Questions for Logan

1. **Which tracks?** *(Recommended)* A and B in parallel: learning in the fabric, in simulation, and stage E3 in software on real noise. Or A alone; or B alone; or C, stage E2 on the card, with its link.
2. **Phase B's rule.** *(Recommended)* The same rule as phase A, the difference of class means, so that the fabric's weights equal the model's and E1's result holds for them unchanged. Or an online rule with a step size, as D0's row S4 imagines, which is a new rule for the model and its own stage E1.
3. **Truth isolation with a learner in the fabric.** *(Recommended)* Restate the gate: no path from a truth record to any output record except through a commit the host names, with a control that plants an unnamed commit. Or keep the gate as written, and keep the learner's truth path outside the detector's gate, held by the learner gate alone.
4. **Real noise.** *(Recommended)* SCEDC's HHZ at 100 samples a second, at stations study D3 used, on days chosen by a rule fixed before any fetch, with the sample format chosen by E3S's design and ruled by the lead. Or another archive or station he names.
5. **Models.** *(Recommended)* Parcels on Opus and verifiers on Sonnet, as round 4. Or verifiers on Opus.
6. **The push at the round's close.** *(Recommended)* As every round: the lead asks him before `main` moves.

# Round 5: learning in the fabric, and real noise - the draft plan

Drafted by the lead on 2026-11-25 on Logan's word after round 4's push: "Begin drafting round 5's plan, the faster host and 200mhz goal can wait till later. Focus on proving things for now rather than speed". This is the second draft, after one verifier pass (VP5, on Sonnet), whose findings are answered below. Nothing of round 5 starts before his approval.

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. An ESTIMATE or SURVEY figure drives no decision here until it is measured.

## What binds it

- **The design:** `docs/studies/D0-rough-design.md`, approved by Logan on 2026-11-21.
  - **Section 4** names two phases of learning. Phase A: "the host reads captured windows and their truth records, trains ..., writes the shadow weights and commits the swap". Phase B: "an update rule in the fabric, applied per labelled window".
  - **Section 8** names four stages, E0 to E3.
  - **Section 9** names sixteen gates.
- **His words**, in the ROADMAP's "Logan's words, as given":
  - "I prefer to work with real data when able" (2026-11-21);
  - the goal of weights "adaptable while retaining the speed of FPGA fabric and memory" (2026-11-21);
  - and the word that opens this draft.
- **The lead's reading of "proving things rather than speed":** the round adds claims that rest on an authority, the model for the fabric and `stats/` for sensitivity. It adds no speed, and no new card image.

## What rounds 1 to 4 leave

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| L1 | Phase A's two halves are built, but have not run together on the card. On the card, a swap of weights the host wrote lands at its named index; the swaps of the card days were sets the host made, not sets a learner trained. A set the learner trained was handed over through the chain in simulation. The host library imports nothing of `learn/` | READ | `docs/VALIDATION.md`, round 3's card-day entry, row W3; `docs/studies/CARD-first-light.md`, its limit 1; `docs/rtl/seam.md`; `docs/host/host.md`; `spec/undertone.toml`, `shadow_begin`, `shadow_data`, `commit_at` | those files |
| L2 | **No learning is in the fabric.** D0's gate "learner" has no row in the registry; the registry has 15 rows, for 14 of D0's sixteen gates, provenance being the other without one | READ | `docs/ROADMAP.md`, "Where the project stands", the registry's restatement; `tests/gates.toml` | the registry |
| L3 | The learning rule is the difference of two class means in exact integers: two sums of windows and two counts, `w = S[1]/n[1] - S[0]/n[0]` as exact fractions, with no step size and no float. With a count at zero the weights are blank | READ | `learn/trainer.py`, `MeanDifference` and its docstring | that file |
| L4 | A label-1 window is frames j to j + T - 1 for a truth index j, and a label-0 window frames j - T to j - 1. The trainer refuses a window that leaves its frames, WINDOW_OUTSIDE_PERIOD, and a label-0 window another record's pulse touches, WINDOW_NOT_FREE | READ | `learn/trainer.py`, its docstring; `learn/errors.py` | that file |
| L5 | The model's quantiser is exact integer arithmetic over the whole set: each value v becomes `round_half_even(v * COEFF_MAX / m)` for the set's largest magnitude m, worked as one fraction a value. It refuses an all-zero set, QUANTISE_INPUT | READ | `model/weights.py`, `quantise` | that function |
| L6 | The learner's hand-over makes one set of every tap of every channel together, in the matched-filter configuration only: one filter reading every channel, the rectifier passing, a pool of 1, a head weight of 1 | READ | `learn/handover.py`, its docstring and `candidate_blob` | that file |
| L7 | So the weight set is a function of integer sums and counts alone: for each tap of each channel, D = S1 x n0 - S0 x n1, then `round_half_even(D x COEFF_MAX / max abs D)` over the whole set. The factor 1/(n1 n0) cancels in the ratio to the peak. D is up to about 96 bits for 64-bit sums and 32-bit counts, and D x COEFF_MAX about 111. The peak needs every D before any division, so D is either stored or made twice | COMPUTED | L3, L5 and L6: S1/n1 - S0/n0 = D / (n1 n0); the widths from the trainer's 64-bit sums and 2^31 windows a label, and COEFF_MAX < 2^15 | arithmetic; a vector worked by hand |
| L8 | The core's delay line holds the last T samples; at the score of index i its window is frames i - T + 1 to i | READ | `docs/model/conventions.md`, CV2 | that convention |
| L9 | So both of a truth record's labelled windows pass through the delay line: the label-0 window is its whole content at index j - 1, and the label-1 window at index j + T - 1. For a record whose label-0 window would start before frame 0, the delay line holds zeros the trainer would refuse | COMPUTED | L4 and L8; CV2's "a sample before the start is zero" | the model |
| L10 | In E1's layout a truth record comes every 128 frames, so with T = 64 the learner's sums change every 64 frames: label 0 at j - 1, label 1 at j + 63, the next label 0 at j + 127 | COMPUTED | L9, and E1's layout of a trial every 128 frames with its pulse at frame 64 of the 128 (`docs/model/e2l.md`, "The experiment") | the model |
| L11 | The core refuses a shadow write while a commit is scheduled or while the shadow is closed, SWAP_PENDING, and has no third bank; the shadow is written today by the host's registers alone | READ | `docs/rtl/core.md`, its refusals table and limits 4 and 5; `spec/undertone.toml`, the register map | that file |
| L12 | The kernel alone after synthesis in round 3's third link: 329,499 LUTs, 37.80% of the chip's; 729 DSP slices of 5,952 | READ | `docs/ROADMAP.md`, row R7 | that report |
| L13 | Stage E1 in software: the learner reaches the matched filter's efficiency, 0.49492 against 0.50026. Stage E2 in software: after a change of pulse shape, the adaptive and reset models each recover about 0.36 of the injections the frozen model misses | READ | `docs/studies/E1-software.md`; `docs/studies/E2-software.md` | those records |
| L14 | Stage E0 on the card: every record of 20 pieces is the model's, and every count round 1's | READ | `docs/studies/CARD-e0.md` | that record |
| L15 | The fabric's injector holds `e0` alone and refuses the definition's `e1` by name, so stage E2 on the card needs an RTL change and a new image | READ | `docs/rtl/source.md`, limit 7 | that file |
| L16 | A link of the kernel for the U50 took 4 h 24 min to 6 h 06 min on the box, three times | READ | CLAUDE.md, trap 19 | the next link |
| L17 | Any change to `spec/undertone.toml` makes the committed records of stage E1, stage E2 and E0C's premise stale, each skipping by name until it is made again; each run is about 7 to 8 minutes | READ | CLAUDE.md, trap 18; `docs/VALIDATION.md`, round 4's card-day entry, the three runs under `e1` | those tests |
| L18 | D0's stage E3 is "a recorded stream. Real noise from HBM, with injections. Seismic archives are the candidate. Not designed here" | READ | D0, section 8 | that file |
| L19 | Study D3's records came from SCEDC: HHZ, one vertical component, at 100 samples a second at four stations through 2024, the service's terms read before any request; the records are not in the tree | READ | `docs/studies/D3-faint-launches.md`, rows F17 and F18 | that study |
| L20 | Launch-day records from SCEDC held samples that need 17 bits, two files of 25 | READ | `docs/studies/D1-launch-data.md`, row M6 (MEASURED there); `docs/studies/D1b-first-look.md`, Q5c | those records |
| L21 | The definition's two profiles are `s16x1`, one channel of 16 bits, and `s24x3`, three channels of 24 bits | READ | `spec/undertone.toml`, the profiles | that file |
| L22 | D8, the textbook efficiency, holds for white Gaussian noise of known level. The paired derivation LRN-A wrote for E1 "assumes Gaussian scores" | READ | D0, row D8; `docs/studies/E2-software.md`, "Which authority this rests on" | those files |
| L23 | `stats/` already holds a paired comparison of two detectors' hits on the same injections, `paired_cost`. Its standard error takes the injections as independent and leaves out the error of a threshold measured from scores, which is the larger part of E1's tolerance | READ | `stats/recovery.py`, `paired_cost`; `docs/model/lrn-a.md`, the tolerance's terms | those files |
| L24 | D0's gate "truth isolation" holds "no path from the truth record to any output record: score, histogram or event"; its control is "the same samples with different truth records must give identical outputs, and a core wired to read truth must be caught" | READ | D0, section 9 | that table |
| L25 | D0's gate "learner" holds "the fabric's weights after each update equal the reference model's, and the lost-update counter equals the model's", where that counter "records every update lost below one least significant bit" | READ | D0, sections 5 and 9, and row S4 behind it | that file |
| L26 | Round 4 ran from its plan's first draft at 10:45 to its push at 16:03 on 2026-11-25, with two parcels and seven verifier passes on Sonnet, which found 17 of 19 planted faults | READ | `git log`; `docs/VALIDATION.md`, round 4's entries | that record |

## What round 5 could be

**A. Learning in the fabric, in simulation: D0's phase B.** The rule of L3 built in RTL beside the core.
- It takes each truth record's two windows from the delay line as they pass (L9), and adds each to a sum, with its count. **That is D0's "applied per labelled window": the sums change at every window.**
- The weights change only at an index the host names. There the learner makes the set of L7, writes it into the shadow, and the host's commit takes it.
- In simulation, held against the model word for word, as rounds 2 and 3 held the chain.

*Shows:* that the rule the project learns by runs in fabric and gives the model's weights exactly, and D0's learner gate gets its row and its control. *Does not show:* anything on the card, or any new fact about sensitivity, since the weights equal the model's and E1's result already holds for them. **What is not known in advance:** what it costs in fabric, and whether an update finishes in the time between windows (T2, T3).

**B. Stage E3 in software: real noise.** Round 4's B'. Recorded seismic noise through the model's replay source, with injections of `e0`, the learner of E1 against the matched filter, at a false-alarm rate measured from signal-free scores. *Shows:* whether the learner reaches the matched filter's efficiency on real noise, which D8 cannot predict (L22). *Does not show:* anything in fabric, or that a real faint event is found. Its costs:
- **A judge.** `paired_cost` exists (L23), but on real noise two of its assumptions must be earned: that the injections are independent, and that a threshold taken from signal-free stretches gives the stated false-alarm rate where the injections are. The judge adds the threshold's own error, and measures each model's false-alarm rate on held-out signal-free stretches, which on real noise is measured, not assumed.
- **A rule for the noise,** frozen and hashed before any record is fetched: which stations, which days, how much, and how stretches holding an earthquake or another event are kept out. D0, section 2, warns that a recorded stream's content is unknown.
- **A sample format** (L20, L21). One of three:
  - HHZ alone scaled into `s16x1` by a fixed shift;
  - three components, HHZ, HHN and HHE, in `s24x3`;
  - a new profile, which changes the definition.
  It is chosen before any record is read.
- **Injection amplitudes.** D8 gives no calibration, so each amplitude is a multiple of the noise's level measured on a calibration stretch, by a rule frozen before any fetch.
- **Size:** one part as long as E1's full part is about 71 hours at 100 samples a second (T4). The design says how many parts, stations and days, and what the judge's tolerance is at that size.

**C. Stage E2 on the card.** The fabric's injector taught `e1`, a new link, and a card day on which the drift run with its sixteen swaps equals the model's. *Shows:* phase A's adaptation on the card, bit for bit, over a long run with many swaps. *Does not show:* learning in the fabric. Its cost: an RTL change to round 2's verified injector, and a link of 4 h 24 min to 6 h 06 min (L16). If A comes first, one link might carry both A's learner and C's injector (BELIEVED: both change the definition, the register map and the kernel, and no such link has been made).

**D. The provenance gate's row.** Its check exists in the build's manifest (round 3). A row would need a test the gate can run without the box. Small, and proves nothing new about the detector.

**Recommended: A and B, in parallel.**
- **They share two things.** Both append rows to `tests/gates.toml`, which is merged by the rule of CLAUDE.md's trap 15. And track A changes the definition (below), which B's runs are made under. Their code does not overlap: A's is the model's learner schedule and RTL under `rtl/`, and B's is a replay of real noise, `stats/` and a study. B's parcel does not change `model/run.py` or the replay without the lead's ruling.
- **A** is the project's central claim, weights that adapt in the fabric, held to the model.
- **B** is his "real data", where the instrument's answer is not known in advance.
- **C** waits for A, so that a link might serve both.
- **D** is left for a round with a build.

## Track A: learning in the fabric, in simulation

- **The model first.** The model is the authority, so the fabric's learner is first written in the model, as a schedule the model runs in a stream:
  - it takes windows from the delay line at the two indexes of each truth record (L9);
  - it makes the set of L7 at a named index;
  - the host commits it at a later named index.
  **The model's set must equal `learn.trainer.MeanDifference` handed over by `learn.handover.candidate_blob` for the same windows.** A test holds that. It is a regression check by construction, since the model's schedule calls the same arithmetic. What is new is the fabric's equality with it.
- **Its refusals, as the trainer's:**
  - a label-0 window that would start before frame 0 is refused or skipped by a rule the design states, as the trainer's WINDOW_OUTSIDE_PERIOD (L9);
  - a label-0 window another pulse touches, as WINDOW_NOT_FREE;
  - an update that is not finished when its commit is named, by a name of its own.
  **Every new name is a change to the definition.**
- **What the fabric needs that the core has not got:**
  - the truth records' indexes, which the injector has (and only the index: the trainer reads no pulse id and no amplitude);
  - the delay line's whole window in one clock, or a copy of it;
  - two sums of 64 words of 64 bits a channel, and two counts;
  - D for each tap, made twice or stored (L7);
  - the peak;
  - an exact division a tap with the model's rounding;
  - **a way into the shadow beside the host's registers** (L11). The core refuses a shadow write while a commit is scheduled. So the design says who writes the shadow when, and what is refused when both would.
- **A change to the definition, and what it costs.** New registers, counters and refusal names change `spec/undertone.toml`. Then the records of E1, E2 and E0C's premise go stale and are made again at the round's end, about 7 to 8 minutes each (L17). **E0C's card-day record stays stale by design.**
- **D0's truth isolation, restated.** The learner reads the truth records' indexes, so a truth record reaches the score through the weights. The plan proposes this restatement: **no path from a truth record to any output record except through a set the learner makes and a commit the host names.** In observable form:
  - the same samples with different truth records give identical outputs up to the first named commit;
  - after it, the outputs equal the model's run with the learner's set.
  The control plants what the restatement forbids:
  - a commit at an index no one named;
  - a commit the learner triggers itself;
  - truth reaching the score, the histogram or an event with no commit;
  - a learner that reads a truth record's pulse id or amplitude.
  Question 3 asks him.
- **D0's learner gate, restated.** The rule has no step size, so no update is "lost below one least significant bit" (L25): D0's counter counts nothing here. The plan proposes the gate hold that the fabric's set after each update equals the model's, and that **the counts of windows taken and refused, and of updates refused for time,** equal the model's. Its controls:
  - a learner that does nothing;
  - one that rounds the other way;
  - one that drops the last window before an update;
  - one that takes a label-0 window the trainer would refuse.
  Each is held against a model that does change the weights. Question 4 asks him.
- **The cost, measured:** the learner synthesised out of context, as the head was in round 2, for its LUTs, DSP slices and memory against L12's room.
- **The parcels,** each designed first and ruled by the lead before it builds:
  - **LRN-B:** the model's phase-B schedule and its refusals, the definition's change, and the software tests;
  - **RTL-L:** the learner in RTL, its way into the shadow, its benches against LRN-B's model, its mutants, and the gate's row.
  RTL-L designs on LRN-B's ruled design, and builds once LRN-B is merged, since its benches run LRN-B's model.

## Track B: stage E3 in software, real noise

- **The parcel E3S,** designed first, then built:
  - the noise rule, frozen and hashed before any record is fetched, from L19's service or another whose terms are read whole first;
  - the sample format, the amplitudes and the size (track B's costs above);
  - the records fetched and logged with each file's source, size and hash, and none committed;
  - the replay through the model's source;
  - the injection set committed with its hash;
  - the learner of E1 and the matched filter for `e0`, each at its own threshold measured from signal-free scores of that noise;
  - the judge, in `stats/`, with its own control, importing nothing of `model/` (the independence stage holds that).
- **Its named controls:**
  - the learner given windows from the stretches it is judged on must be refused, as E1's rule 2 refuses it;
  - a comparison at an equal threshold must be refused, as E1's rule 3 refuses it;
  - the judge must report as worse a model that finds a stated fraction fewer injections, on a stream where it does;
  - and a threshold taken from one stretch must be shown to give, or fail to give, its stated false-alarm rate on another.
- **The full run is the lead's,** booked if it is ten minutes or more, made after track A's definition change so that its record is of the round's last definition.

## The waves

| wave | what | whose | waits for |
|---|---|---|---|
| 0 | the round's branch `r5`, cut from `main` | the lead | approval |
| 1 | LRN-B's design, then its build; E3S's design, then its build | parcels | wave 0 |
| 2 | RTL-L's design, on LRN-B's ruled design; RTL-L's build | a parcel | the design: LRN-B's design ruled; the build: LRN-B merged |
| 3 | the learner's synthesis out of context, on the box; E3S's full run; E1's, E2's and the premise's runs made again under the round's definition | the lead | RTL-L merged; E3S merged; the definition's last change |
| 4 | the round's close: its verifier, the narrow passes, VALIDATION.md, the ROADMAP | the lead | wave 3 |

## What the round is for

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| W1 | In simulation, the fabric's learner gives the model's weight set, word for word, after every update, under both sample formats, with its counts equal to the model's | BELIEVED | L3, L5, L7: the rule is integer arithmetic, and the RTL has matched the model in every round | RTL-L's benches |
| W2 | D0's learner gate has a row and a control that the gate runs, in the restated form question 4 settles | DECISION | the plan's track A | the registry |
| W3 | On real seismic noise, the learner of E1 is compared with the matched filter at a measured false-alarm rate, by a judge whose assumptions are stated and tested on that noise | DECISION | the plan's track B | E3S's full run |
| W4 | Nothing earlier breaks: both sizes of the gate pass at the round's end. The records of E1, E2 and the premise are made again under the round's definition. The two inner checks of the card day's record are still skipped by name, E0C-CARD-STALE | BELIEVED | each round so far; L17 | the gate |

## Other figures

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| T1 | The learner's sums for T = 64 taps under `s16x1` are two of 64 words of 64 bits, about 8 kbit; under `s24x3`, three channels, about 25 kbit; a stored D, or a snapshot of the sums while an update runs, adds as much again | COMPUTED | 2 x 64 x 64 = 8,192 bits, x 3 = 24,576, from L3, L7 and L21 | RTL-L's design |
| T2 | One update divides once a tap of each channel. Each quotient is at most COEFF_MAX, so a divider that makes one quotient bit a clock needs about 16 clocks a tap: about 1,000 clocks for the division under `s16x1` and 3,100 under `s24x3`. The multiplies, the peak's search and the shadow's writes come on top, perhaps as much again | ESTIMATE | 64 x 16 = 1,024 and 192 x 16 = 3,072; the quotient's bound from L5, every value's magnitude at most m; the rest of the update not yet designed | RTL-L's design and its benches |
| T3 | At 20 clocks a frame under `s16x1` and 60 under `s24x3`, an update is then about 50 to 100 frames under either. Against L10's 64 frames between windows, the sums change while an update runs, so the design either snapshots them (T1) or holds windows back, and says which | ESTIMATE | T2, over the source's rate of `docs/rtl/source.md`; L10 | RTL-L's benches |
| T4 | A stretch of real noise as long as E1's full part, 25.6 million frames, is about 71 hours at 100 samples a second | COMPUTED | 25,600,000 / 100 / 3,600, from L19 | arithmetic |
| T5 | The round takes one to two days by the clock | ESTIMATE | L26, with round 4's 5 h 18 min of two parcels and no new RTL; this round has three parcels, one of them RTL as large as round 2's, and a definition change. The basis is weak | the round |

## How the round is held

As round 4, with what it taught:
- **Parcels and verifiers named in every dispatch.** Round 4's were parcels on Opus and verifiers on Sonnet, by his word for that round; question 6 asks again.
- **Each parcel designs first, and the lead rules before it builds.**
- **Every verifier works on a sealed clone with faults the lead planted,** in files the tip commit changes, and each fix goes back to the verifier that found it.
- **A comment in a file the build-line list names is not free to add lines** (round 4's slip, VALIDATION.md). RTL-L's mutants and RTL comments follow that.
- **A long run is made on the commit the merge then takes,** or the diff on what it reads is shown empty (round 4's rule).
- **The TimeSheet before every run,** bookings for runs of ten minutes or more, and cft-fp256's lead told before heavy desktop runs and any use of the box.

## What this plan does not settle

- **Whether an update finishes in the time between windows** (T2, T3). RTL-L measures it in simulation. The design snapshots the sums, holds windows back, or refuses the update by name, and the gate holds the count.
- **What the learner costs in fabric.** The synthesis in wave 3 measures it. Whether it fits beside the kernel in one image is a later link's question.
- **What real noise does to the learner.** That is what track B is for. A stretch of real noise holds events no one injected (D0, section 2), and the noise rule keeps out what it can name, not what it cannot.
- **Nothing here runs on the card.** Stage E2 on the card, and the learner on the card, wait for a link (route C).

## Questions for Logan

1. **Which tracks?** *(Recommended)* A and B in parallel: learning in the fabric, in simulation, and stage E3 in software on real noise. Or A alone; or B alone; or C, stage E2 on the card, with its link.
2. **Phase B's rule.** *(Recommended)* The same rule as phase A, the difference of class means. The fabric adds each labelled window to its sums as it passes, and makes a new set only where the host names it, so the fabric's weights equal the model's and E1's result holds for them unchanged. Or a rule that changes the weights at every window with a step size, which is a new rule for the model, with its own stage E1, and the fixed-point loss D0's row S4 surveys.
3. **Truth isolation with a learner in the fabric.** *(Recommended)* Restate the gate. The same samples with different truth records give identical outputs until the first named commit, and after it the model's outputs with the learned set. Its control plants an unnamed commit, a self-triggered one, truth reaching an output without a commit, and a learner reading more of the truth record than its index. Or keep the gate as written for the detector, and hold the learner's path by the learner gate alone.
4. **The learner gate's counter.** *(Recommended)* Restate it. With no step size nothing is lost below a bit, so the gate counts windows taken and refused, and updates refused for time, each equal to the model's. Or keep D0's counter, which then always reads zero.
5. **Real noise.** *(Recommended)* SCEDC's records at stations study D3 used, on days chosen by a rule fixed before any fetch. Or another archive or station he names.
6. **Models.** *(Recommended)* Parcels on Opus and verifiers on Sonnet, as round 4. Or verifiers on Opus.

The push at the round's close is asked as every round's is: the lead asks him before `main` moves.

# Round 4: sensitivity on the card, and the question in software - the draft plan

Drafted by the lead on 2026-11-25 on Logan's word "Yes, push. Then begin the round 4 draft", given when round 3 was pushed. **This is the first draft. It is not approved: nothing of round 4 starts before Logan approves it.** It goes past a verifier before it comes to him, as rounds 2 and 3 did.

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. An ESTIMATE or SURVEY figure drives no decision here until it is measured.

## What binds it

- **The design:** `docs/studies/D0-rough-design.md`, approved by Logan on 2026-11-21. Its section 8 names four stages, E0 to E3. Round 1 made E0 in software, round 2 E1 in software, and round 3 put the detector on the card with bit identity and no statistics. Its section 4 names two phases: phase A, where the host trains and the fabric swaps, and phase B, where the fabric learns.
- **His words since**, in the ROADMAP's "Logan's words, as given". About 200 MHz is his goal for the kernel's clock "not right now, but in the future" (2026-11-25). The routes toward it are in its "Routes for later", none planned.
- **Round 3's lessons**, in CLAUDE.md's traps 19 to 21 and VALIDATION.md's round-3 entries. The ones that change how this round is held are under "How the round is held".

## What round 3 leaves

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| L1 | Every score word of ten runs on the U50, five cases at 2^17 and at 2^20 frames, equals the model's, and the flipped-bit control was seen in both of its runs | MEASURED | `docs/studies/CARD-first-light.md`, rows C6 and C9 | those rows' files |
| L2 | The card's image runs its kernel at 100 MHz | MEASURED | `docs/rtl/krnl.md`, rows K26 to K28 | the image's info file |
| L3 | On the card, about 200 ns a frame, 20 clocks, in four short windows | COMPUTED | `docs/studies/CARD-first-light.md`, row C12 | a timed run |
| L4 | At 2^20 frames the host wrote 7,167 truth records of each case while it ran, never less than 110,316 frames ahead of the core | MEASURED | `docs/studies/CARD-first-light.md`, row C8 | those runs' reports |
| L5 | The kernel's one master is on HBM[0]; a segment of HBM is 256 MB if the 32 segments are equal and "8GB" is 8 x 2^30 bytes | READ | `hw/link.cfg`'s `sp` line; `docs/studies/P03-platform.md`, row P7, COMPUTED there on two conditions the tool does not give | a build's memory map |
| L6 | A record takes a slot of 32 bytes, and the host's buffer has a guard of 3,968 bytes before the first slot | READ | `docs/rtl/krnl.md`, section 2; `docs/host/host.md`, row H7 | those files |
| L7 | So one run's records fit one segment up to 2^23 - 124 frames, about 8.4 million | COMPUTED | (2^28 - 3,968) / 32 = 8,388,484, from L5 and L6 | L5's conditions |
| L8 | Stage E0's full run in software is 200,000 injections at each of five amplitudes, one every 128 frames, about six minutes of one core each | READ | `tests/test_seam_e0.py`'s docstring | that file |
| L9 | So one amplitude of it is about 25.6 million frames and 819 MB of records, past one segment | COMPUTED | 200,000 x 128 = 25,600,000; x 32 = 819,200,000, from L6 and L8 | arithmetic |
| L10 | Round 1's run of E0 in software was inside the tolerance at all five amplitudes | READ | D0, row D8's last column; `docs/VALIDATION.md`, 2026-11-23 | that record |
| L11 | Stage E1 in software passed: the learner reaches the matched filter's efficiency, 0.49492 against 0.50026 | READ | `docs/studies/E1-software.md` | that page's record |
| L12 | The definition has one pulse, `e0` | READ | `spec/undertone.toml`, `[pulses]` | that file |
| L13 | Any change to `spec/undertone.toml` makes stage E1's committed record stale, and the gate skips by name until the run is made again | READ | CLAUDE.md, trap 18; `tests/test_e1_full_run.py` | that test |
| L14 | The learner is the difference of two class means over labelled windows, exact integer arithmetic | READ | `learn/trainer.py`, `MeanDifference`; `docs/model/lrn-a.md` | those files |
| L15 | The scorer of D0's section 4 has no RTL; the card's records are raw score words | READ | `docs/plans/R3-first-light.md`, "D0's sixteen gates"; `docs/rtl/krnl.md` | those files |
| L16 | The model's core alone steps about 110,000 frames a second in the matched-filter configuration; a run of a stream adds the source and the injector | READ | round 3's plan, row L28, from `docs/model/mod-b.md`, row B14 | that row's command |
| L17 | Round 3 ran from the plan's opening commit at 09:18 on 2026-11-24 to the push at 10:38 on 2026-11-25, with four parcels and twelve verifier passes; its passes found 36 of 36 planted faults | READ | `docs/VALIDATION.md`, round 3's entries; `git log` | that record |

## What round 4 could be

**A. Sensitivity on the card.** Stage E0 on the card, with its statistics: the matched filter's injection recovery at five amplitudes, from the card's own score words, judged by `stats/` against D8. *Shows:* the instrument and the counting on the card are right at scale. *Does not show:* anything about learning. **And since the card equals the model word for word (L1), its counts are the model's own on the same stream. So the stage tests bit identity at a scale round 3 did not reach, and the host's scoring of card records. It adds no new fact about sensitivity.**

**B. The question, in software.** Stage E2 of D0, induced drift, through the reference model: mid-run the pulse changes shape. Five models see the same stream: frozen; frozen with only its input scaling updated; adaptive; periodically reset; and the matched filter for the new pulse. *Shows:* whether adaptation recovers events a frozen model misses, at an equal false-alarm rate, on easy mode. *Does not show:* anything in fabric. It is the experiment the project's question asks, and round 3's plan offered it as its option B.

**C. Toward 200 MHz.** The timing query on the third link's routed design, the register stage in the write checks, the pool out of LUT memory, and links again. *Shows:* where the design closes after each change. *Does not show:* anything about sensitivity. Logan's goal for a later round (the ROADMAP, "Logan's words, as given", 2026-11-25); each link is four and a half to six hours on the box (CLAUDE.md, trap 19).

**D. Real data on the card.** Stage E3: a replay source from HBM in RTL, a recorded stream such as study D3's launches, and the sample format real records need. *Shows:* the detector on real noise. Not designed; the RTL replay source alone is a parcel.

**Recommended: A and B, as two tracks.** A is small, the lead's card day and one parcel, and closes D0's E0 on the card. B is the project's question, wholly in software, where the model is the authority and nothing waits on the box. They share nothing but the definition. C waits for Logan's word on when; D for a design.

## Track A: stage E0 on the card

- **The stream.** One amplitude of E0's full run is about 25.6 million frames (L9), past what one segment holds (L7). Two ways, question 2:
  - *(Recommended)* **runs of 2^22 frames**, 32,767 injections each, six to an amplitude: 196,602 injections an amplitude, against L8's 200,000. Each run has its own seed, named before any run, as round 1 named E0's. No new build and no RTL change. The card's stage is then its own experiment, not a replay of round 1's.
  - *The alternative:* **a new link with the master on four segments**, so that one run holds one amplitude of round 1's own stream, seed for seed. Its counts must then equal round 1's exactly. One link, four and a half to six hours (trap 19), and the host's buffer across segments, untried.
- **Every record of every run is compared with the model's**: the model's run of the same seed, about a minute of one core a run by L8's rate (T3). The comparison is bit identity's, as on round 3's card day, and the count is judged by `stats/` as E0's is in software.
- **The host's side is a parcel, E0C**: the runs, the reading of each run's scores at the truth index + 63 and the signal-free score at the index - 1 (E0's own reading, `tests/test_seam_e0.py`), the judge through `stats.tolerance.check_efficiency`, and a short form in the first size against the model. **The card day is the lead's**, in a booked daytime window, as round 3's.
- **What it cannot show**, and says: a fault the card and the model share. And since L1, the efficiency it measures is the model's on that stream; the stage's own result is that the card reproduces it at scale.

## Track B: stage E2 in software

- **The drift: a change of pulse shape**, question 3. A second pulse, `e1`, joins the definition: a spec change, so stage E1's record is made again at the round's end (L13). From a named index the injector injects `e1` in place of `e0`. *The alternative:* a change of noise colour. It needs coloured noise in the model, and the matched filter for coloured noise whitens first, which D0 holds as BELIEVED and uncommitted (D0, D8's third limit).
- **The five models** of D0's section 8, each a configuration blob and a schedule of swaps, all on one stream:
  - **frozen**: E0's matched filter for `e0`, never changed;
  - **frozen, input scaling updated**: the same filter, its output's scale re-estimated after the change (what "input scaling" is, for this core, is the parcel's to design and the lead's to rule);
  - **adaptive**: the learner of round 2, retrained on the most recent labelled windows at a fixed cadence, swapped in at named indexes;
  - **periodically reset**: adaptive, with its window cleared at a fixed cadence;
  - **the matched filter for `e1`**: the best a model can do after the change, by D8.
- **The comparison rules** of D0's section 8, held by the gate `comparison-rules`: the injection set committed with its hash before the run; after every weight change the threshold set again from signal-free scores of the new epoch; models compared at an equal false-alarm rate; the reported model named before the run.
- **Parcels:** **E2D**, the drift in the model and the definition's second pulse, with the lead's spec change; then **E2L**, the five models, the experiment and its judge, with a short form in the first size. Each designs first, and the lead rules before it builds. **The full run is the lead's**, booked if it is ten minutes or more.
- **What it cannot show:** anything in fabric; real noise; drift of noise colour.

## The waves

| wave | what | whose | waits for |
|---|---|---|---|
| 0 | the round's branch `r4`, cut from `main` | the lead | approval |
| 1 | E0C, design then build; E2D, design, then the definition's `e1` made by the lead from the design he rules (as `655d303` was for KRNL), then E2D's build | parcels, and the lead for the definition | wave 0 |
| 2 | E2L, design then build | a parcel | E2D merged |
| 3 | the card day for stage E0; stage E2's full run; stage E1's run made again | the lead | E0C merged; E2L merged |
| 4 | the round's close: its verifier, the narrow passes, VALIDATION.md, the ROADMAP | the lead | wave 3 |

The round's length by the clock is an ESTIMATE of one to two days (T4), on round 3's two (L17).

## What the round is for

| # | the round is worth running if | basis | source or command | falsified by |
|---|---|---|---|---|
| W1 | on the card, at five amplitudes, every record of every run of stage E0 equals the model's, and each amplitude's count is inside the tolerance of D8 | BELIEVED | L1 at a smaller scale; L10 for the model's counts | the card day's comparison and its judge |
| W2 | in software, after the pulse changes, the adaptive model finds events the frozen one misses, at an equal false-alarm rate | DECISION | measuring it is the point; nothing here says which way it goes | stage E2's full run |
| W3 | nothing round 3 holds breaks: both sizes of the gate pass at the round's end | BELIEVED | each round so far | the gate |

## Other figures

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| T1 | A run of 2^22 frames on the card is about 0.84 s of the kernel at 200 ns a frame | COMPUTED | 4,194,304 x 200e-9, from L3 | a timed run |
| T2 | It holds 32,767 injections, of which 31,743 reach the injector while it runs, about 39,000 a second | COMPUTED | 4,194,304 / 128 - 1 (`hw/card/card.py`'s schedule); 32,767 - 1,024; 5.0e6 / 128 | that schedule |
| T3 | The model makes one run of 2^22 frames in about a minute of one core | ESTIMATE | L8: 25.6 million frames in about six minutes, so 4,194,304 in about 59 s; the comparison adds to it | a timed run |
| T4 | The round takes one to two days by the clock | ESTIMATE | L17, with two tracks of two and one parcels against round 3's four and its build | the round |

## How the round is held

As round 3, with what it taught. Each is from Logan's word or from something `docs/VALIDATION.md` records.

- **Parcels and verifiers on Opus**, named in every dispatch: the parcels by his word of 2026-11-24, the verifiers by his answer to round 3's question 5.
- **The lead's closing documents are written from commands**, and a correction is followed through the whole tree. Round 3's close found eight wrong statements of the lead's over its first two passes, and three things left standing at the third. Two of the eight were corrections whose consequence was not followed.
- **The lead's work on the box and the card goes past a verifier like a parcel's**, with its evidence copied where the verifier can read it: the run folders, and excerpts of any report on the box.
- **A probe's range is read as what it covers**, not as the call's; a report's section is read before its figure (round 3's misreadings: the sync probe's range, and a hold slack read as setup).
- **Every long run on the box is detached** and watched by its log (trap 19). **The TimeSheet before every run.** The card booked sensitive, in daytime.
- **A conditional word is met plainly or asked again.** At round 3's close the lead read "once the verifier returns ready" across to later passes; two verifiers said it stretched the words, and the lead asked.
- **A round branch, `r4`,** cut from `main`; nothing pushed until his word.

## What this plan does not settle

- **Which pulse `e1` is**, and what "input scaling" means for this core: E2D's and E2L's designs, ruled by the lead.
- **The cadence of the adaptive model's retraining, the window it keeps, and the reset's period**: E2L's design, fixed before any run, like E1's seeds.
- **Whether the host keeps up for 2^22 frames.** At 2^20 it never came near falling behind (L4); eight times longer is BELIEVED to be the same, and the card day measures it.
- **Phase B, the scorer in RTL, replay from HBM, the definition's maxima on the card, the second sample format, 200 MHz**: later rounds.

## Questions for Logan

1. **Which round?**
   - *(Recommended)* **A and B**, two tracks: stage E0 on the card, and stage E2 in software.
   - *Alternatives:* A alone; B alone; or C, toward 200 MHz, in place of A.
2. **Stage E0 on the card: how is the stream made?**
   - *(Recommended)* **Runs of 2^22 frames with seeds of their own**, six to an amplitude: no new build.
   - *The alternative:* a new link with the buffer on four segments, so the card replays round 1's E0 stream seed for seed.
3. **Stage E2's drift?**
   - *(Recommended)* **A change of pulse shape**, with a second pulse in the definition.
   - *The alternative:* a change of noise colour, which needs coloured noise in the model and a whitened matched filter.
4. **The timing query toward 200 MHz, in this round as a measurement only?**
   - *(Recommended)* **Not in this round**: the routed design that is kept is the 100 MHz one, so it would give a list to start from, not what 200 MHz needs (the ROADMAP's route 1).
   - *The alternative:* one booked session of Vivado on the box, the lead's, reading every kernel path over 5 ns from the kept design.
5. **The card day: the lead alone, as in round 3?**
   - *(Recommended)* **Yes**, in a booked daytime window, telling you before and after.
6. **The push at the close?**
   - *(Recommended)* **The lead asks you again** before `main` moves and anything is pushed.

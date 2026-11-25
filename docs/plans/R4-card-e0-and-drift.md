# Round 4: stage E0 on the card, and a software stage of the question - the draft plan

Drafted by the lead on 2026-11-25 on Logan's word "Yes, push. Then begin the round 4 draft", given when round 3 was pushed. **This is the third draft, after two verifier passes. It is not approved: nothing of round 4 starts before Logan approves it.** It goes past a verifier before it comes to him, as rounds 2 and 3 did.

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. An ESTIMATE or SURVEY figure drives no decision here until it is measured.

## What binds it

- **The design:** `docs/studies/D0-rough-design.md`, approved by Logan on 2026-11-21. Its section 8 names four stages, E0 to E3. Round 1 made E0 in software, round 2 E1 in software, and round 3 put the detector on the card with bit identity and no statistics. Its section 4 names two phases: phase A, where the host trains and the fabric swaps, and phase B, where the fabric learns.
- **His words**, in the ROADMAP's "Logan's words, as given". On 2026-11-21: "I prefer to work with real data when able." On 2026-11-25, after the lead told him the 200 MHz link had not closed, he asked: "Would we likely be able to go faster if we resolved the issue in RTL? Not right now, but in the future. Ideally Id like to reach ~200mhz just as a goal". *The lead's reading* (the ROADMAP's): about 200 MHz is his goal for a later round, and the routes toward it are in "Routes for later", none planned.
- **Round 3's lessons**, in CLAUDE.md's traps 19 to 21 and VALIDATION.md's round-3 entries. The ones that change how this round is held are under "How the round is held".

## What round 3 leaves

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| L1 | Every score word of ten runs on the U50, five cases at 2^17 and at 2^20 frames, equals the model's, and the flipped-bit control was seen in both of its runs. Every case was at amplitude 1/1 | MEASURED | `docs/studies/CARD-first-light.md`, rows C6 and C9; `hw/card/card.py`'s schedule | those rows' files |
| L2 | The card's image runs its kernel at 100 MHz | MEASURED | `docs/rtl/krnl.md`, rows K26 to K28 | the image's info file |
| L3 | On the card, about 200 ns a frame, 20 clocks, in four short windows | COMPUTED | `docs/studies/CARD-first-light.md`, row C12 | a timed run |
| L4 | At 2^20 frames the host wrote 7,167 truth records of each case while it ran, never less than 110,316 frames ahead of the core | MEASURED | `docs/studies/CARD-first-light.md`, row C8 | those runs' reports |
| L5 | The kernel's one master is on HBM[0]. A segment of HBM is 256 MB if the 32 segments are equal and "8GB" is 8 x 2^30 bytes; in the emulation image HBM[0] to HBM[3] were contiguous, 2^28 bytes each | READ | `hw/link.cfg`'s `sp` line; `docs/studies/P03-platform.md`, row P7 (COMPUTED there on two conditions the tool does not give) and row P15 (MEASURED there in emulation) | a build's memory map |
| L6 | A record takes a slot of 32 bytes, and the host's buffer has a guard of 3,968 bytes before the first slot | READ | `docs/rtl/krnl.md`, section 2; `docs/host/host.md`, row H7 | those files |
| L7 | So one run's records fit one segment up to 2^23 - 124 frames, about 8.4 million, if one buffer can take the whole segment from its base | COMPUTED | (2^28 - 3,968) / 32 = 8,388,484, from L5 and L6 | L5's conditions; a buffer of that size |
| L8 | Stage E0's full run in software is 200,000 injections at each of five amplitudes, one every 128 frames, about six minutes of one core each | READ | `tests/test_seam_e0.py`'s docstring | that file |
| L9 | So one amplitude of it is about 25.6 million frames and 819 MB of slots, past one segment | COMPUTED | 128 x (200,000 + 1) = 25,600,128; x 32 = 819,204,096, from L6 and L8 | arithmetic |
| L10 | Round 1's run of E0 in software was inside the tolerance at all five amplitudes | READ | D0, row D8's last column; `docs/VALIDATION.md`, 2026-11-23 | that record |
| L11 | Stage E1 in software passed: the learner reaches the matched filter's efficiency, 0.49492 against 0.50026 | READ | `docs/studies/E1-software.md` | that page's record |
| L12 | The definition has one pulse, `e0` | READ | `spec/undertone.toml`, `[pulses]` | that file |
| L13 | Any change to `spec/undertone.toml` changes the definition's hash, which makes stage E1's committed record stale (the gate skips by name until the run is made again) | READ | CLAUDE.md, trap 18; `tests/test_e1_full_run.py` | that test |
| L14 | The image's identity block carries the definition's hash, and the host library refuses an image whose hash is not its tree's | READ | `docs/studies/CARD-first-light.md`, "What else was read"; `host/library.py`, its identity check | that code |
| L15 | The learner is the difference of two class means over labelled windows, exact integer arithmetic | READ | `learn/trainer.py`, `MeanDifference`; `docs/model/lrn-a.md` | those files |
| L16 | The scorer of D0's section 4 has no RTL; the card's records are raw score words, and any counting is the host's | READ | `docs/plans/R3-first-light.md`, "D0's sixteen gates"; `docs/rtl/krnl.md` | those files |
| L17 | The model's noise word i of seed s is a mix of s + GAMMA x (i + 1), so under s16x1, one word a frame, the stream from frame k of seed s is the stream from frame 0 of seed s + GAMMA x k, mod 2^64 (under s24x3 the offset is GAMMA x 3k); the fabric's seed register `src_seed` is two words | READ | `model/source.py`, the generator; `spec/undertone.toml`, `src_seed`; VP4's check of the identity in the model, at three offsets | the fabric at an offset seed |
| L18 | The model's core alone steps about 110,000 frames a second in the matched-filter configuration; a run of a stream adds the source and the injector | READ | round 3's plan, row L28, from `docs/model/mod-b.md`, row B14 | that row's command |
| L19 | The injector picks each truth record's pulse by its `pulse_id`, so a change of pulse mid-run is a schedule, once a second pulse is defined | READ | `model/inject.py` | that code |
| L20 | Round 3 ran from its plan's opening commit at 09:18 on 2026-11-24 to its push's commit, 23256a6, at 10:37 on 2026-11-25, with four parcels and twelve verifier passes; its passes found 36 of 36 planted faults | READ | `git log`; `docs/VALIDATION.md`, round 3's entries | that record |

## What round 4 could be

**A. Stage E0 on the card.** The matched filter's injection recovery at five amplitudes, from the card's score words, counted by the host and judged by `stats/` against D8. *Shows:* the card stays bit-identical to the model over about twenty times round 3's frames (T6), at four amplitudes the card has not run (L1), with truth records fed about six times as long a run; and the host's counting of card records is right. *Does not show:* anything about learning. **And it adds no new fact about sensitivity:** if the card equals the model on every word, its counts are the model's on that stream. Its result is that the card reproduces E0 at scale, or where it does not.

**B. Stage E2 in software: induced drift.** Through the reference model, mid-run the pulse changes shape. D0's five models see the same stream. *Shows:* how the adaptive and the reset models recover after the change, against the frozen one, at an equal false-alarm rate, on easy mode. *Does not show:* anything in fabric, or on real noise. **In white noise its direction is known in advance:** if `e1` has `e0`'s norm, the frozen filter, a linear filter, keeps the deflection d x cos(e0, e1), and the learner converges to the pulse injected (L11, L15). So the choice of `e1` sets the size of the effect, and what the stage measures is how fast and how well the adaptive models recover.

**B'. Stage E3 in software: real noise.** Recorded seismic noise through the model's replay source, with injections, as D0's E3 names, the learner against the matched filter at an equal false-alarm rate. *Shows:* how the learner does on real noise, where D8 does not apply (its white-noise limit). *Does not show:* anything in fabric. **Its direction is largely known too:** the difference-of-means learner converges to the injected pulse in any noise (`docs/model/lrn-a.md`), the same unwhitened filter as the matched filter it is set against; what is not known is how it does with finite windows, and the absolute efficiency on that noise. Its costs: no design yet (D0 says "Not designed here"); no judge yet, since D8 does not apply and stage E1's paired comparison assumes Gaussian scores; D0 section 2's limit that a recorded stream's own content is unknown; the records to fetch and log again (study D3's are not in the tree); and a sample format real records need (D1b found values past 16 bits). It is E3 without D0's "from HBM". Logan's words are "I prefer to work with real data when able"; *the lead's reading* is that they point here.

**C. Toward 200 MHz.** The timing query on the kept design, a register stage in the write checks, the pool out of LUT memory, and links again. *Shows:* where the design closes after each change. *Does not show:* anything about sensitivity. His goal for a later round, in the lead's reading; round 3's three timed links, of its five, took 4 h 24 min to 6 h 06 min each on the box (CLAUDE.md, trap 19).

**D. Real data on the card.** Stage E3 on the card: a replay source from HBM in RTL, then B'. Not designed.

**Recommended: A, then B.** A is small and closes D0's E0 on the card. B is D0's next stage in order, where the instrument's answer is known before real noise is tried. B' is the strong alternative for the software track, and the one his words on real data point to, in the lead's reading: question 1 asks him. C waits for his word on when; D for B' and a design.

## Track A: stage E0 on the card

- **The tree.** The card's image carries round 3's definition (L14). **The card day runs from a tree whose `spec/undertone.toml` is round 3's, byte for byte**, or the library refuses the image at open. So E0C is built and merged before any change to the definition, and the card day's host tree is a snapshot taken from that merge. A change to `spec/` for track B lands after the card day. **Its cost:** from then on the round's tree refuses the only card image, so any later work on the card needs a new link (4 h 24 min to 6 h 06 min by round 3's timed three) or a snapshot tree; and the card day's committed record carries round 3's definition's hash, so E0C's test of that record is held as stage E1's is: it names the hash, and skips by name once the definition moves (L13).
- **The stream**, question 2:
  - *(Recommended)* **Round 1's own E0 stream, in pieces.** Each amplitude's 25,600,128 frames (L9) run as four pieces, each within one segment (L7), each starting at a multiple of 128 and seeded with s + GAMMA x start (L17), its schedule shifted by its start. **Then the card's counts must equal round 1's exactly**, amplitude by amplitude, on two premises. *What a piece's start does:* the core's delay line starts at zero, so the first 62 records of each later piece differ from the continuous stream's (VP4-2's run of the model), and nothing flags them: no read falls there, since a trial's two reads use frames 128i to 128i + 127 and a piece starts at a multiple of 128. In the matched-filter configuration the pool holds one sample and carries no state, and settling comes only from a swap. E0C's design shows this, and its test holds it against the model. *That today's model makes round 1's stream:* round 1 ran under an earlier definition, whose hash its parts carry. The gate's short form gives round 1's figures under today's tree (VP4-2), and E0C reruns one full part to show it at scale. That the fabric takes an offset seed is BELIEVED; the card day's comparison of every record shows it.
  - *Runs with seeds of their own*: four runs of 6,400,128 frames an amplitude, exactly 200,000 injections; its own experiment, judged by `stats/`, no exact equality with round 1.
  - **Untried in each of these:** a buffer of about 205 MB in one segment, where round 3's largest was about 34 MB, and the host holding a run's records in memory, which `hw/card/card.py` does whole.
  - *A new link* with the master on four segments, so each amplitude is one run. One link, 4 h 24 min to 6 h 06 min by round 3's three timed links of its five (trap 19), and a buffer across segments, untried; built after any spec change, it would carry the new definition.
- **Every record is compared with the model's**, the model's run of the same piece: 20 runs, four pieces at each of five amplitudes, about a minute and a half of one core each by L8's rate (T3), so about thirty core-minutes, booked. About 2.7 GB of records come back from the box (T5).
- **The parcel E0C**: the pieces and their seeds; the reading of each trial's score at the truth index + 63 and its signal-free score at the index - 1, as `tests/test_seam_e0.py` reads them; the judge, `stats.tolerance.check_efficiency`; and the cost of quantisation beside it, from the statistics package's own filter on the same stream, as round 1's parts carried it. **Its named controls**: the coefficients written the wrong way round, and the score read one sample late, must each fall outside the tolerance, as E0's gate has them (the late read of a piece's last trial falls in the next piece, three trials an amplitude, which the control's design handles); a piece seeded without its offset must differ from the model's continuous stream; and on the card, a flipped coefficient bit must be seen, as on round 3's card day.
- **The card day is the lead's**, in a booked daytime window.
- **And one measured row Logan asked for (2026-11-25): how many trial generations an hour the card allows.** A generation, in the lead's reading, is one set of weights swapped in, tested on a set of injections, its scores read back and scored by the host, and the next set made. On the card day, after E0, the lead times one run with ten swaps at named indexes, the host reading and scoring each stretch between them. Each part's time is taken from the host's clock and the run's trace: the swap, the card's stretch, the read, the scoring and the making of the next set. **The rate an hour is then MEASURED for that host code**, in place of T7's ESTIMATE. It is a measurement of scheduling only: nothing is learned in it, and its weights need be no better than E0's.

## Track B: stage E2 in software

- **The drift: a change of pulse shape**, question 3. A second pulse, `e1`, joins the definition: the lead's change to `spec/`, committed on the gate's second size, after track A's card day (above), and stage E1's record is made again at the round's end (L13). From a named index the injector injects `e1` in place of `e0` (L19). **Which `e1` is chosen sets the effect's size** (option B): the plan proposes fixing its overlap with `e0`, cos(e0, e1), before any run, and question 3 asks him for a value or to leave it to the design. *The alternative:* a change of noise colour, which needs coloured noise in the model and a whitened matched filter that D0 holds as BELIEVED (D8's third limit).
- **The five models** of D0's section 8, each a configuration blob and a schedule of swaps, on one stream:
  - **frozen**: E0's matched filter for `e0`, never changed;
  - **frozen, input scaling updated**: D0 names it and does not define it. For a linear filter in the matched-filter configuration, re-thresholded at an equal false-alarm rate, a scalar gain changes nothing; so this model is BELIEVED to equal the frozen one under a pulse-shape drift. The parcel's design says what it is, and if it is the frozen model again, says so;
  - **adaptive**: round 2's learner, retrained on the most recent labelled windows at a fixed cadence, swapped in at named indexes;
  - **periodically reset**: adaptive, reset at a fixed period. D0 does not define the reset, nor what the adaptive model starts from. The lead proposes that both start from, and reset to, the frozen model, E0's filter for `e0`; whether a reset should instead go to blank is the parcel's design to argue and the lead's to rule. (D0's row S6, a SURVEY, says only that a periodic reset matched or beat adaptation methods on one benchmark);
  - **the matched filter for `e1`**: the best a model can do after the change, by D8.
- **The comparison rules**, all five of D0's section 8, held by the gate `comparison-rules`: the injection set committed with its hash before the run; **the stream split by time into periods a learner trains on and periods it never trains on, and every figure read from the latter**; after every weight change the threshold set again from signal-free scores of the new epoch, and models compared at an equal false-alarm rate; **a false-alarm rate below D10's floor labelled as an extrapolation**; and the reported model named before the run.
- **The authority.** The model makes the scores; **they are judged as stage E1's were**: each model's efficiency at its measured threshold, by `stats/`'s tolerance; and the paired comparison of two models on the same injections, by the derivation LRN-A wrote for E1 (`tests/test_lrn_a_e1.py`), which is not `stats/`'s and assumes Gaussian scores. Nothing here rests on the model's word about detection.
- **The parcel E2L**: the five models, the experiment, its judge and a short form in the first size, designed first and ruled by the lead before it builds, with `e1` fixed in its design. **Its named controls**: an adaptive model that never swaps must equal its own starting model; a comparison made at an equal threshold in place of an equal false-alarm rate, and a figure read from frames a learner trained on, must each be refused, as the gate's control has them. **The full run is the lead's**, booked if it is ten minutes or more.

## The waves

| wave | what | whose | waits for |
|---|---|---|---|
| 0 | the round's branch `r4`, cut from `main` | the lead | approval |
| 1 | E0C, design then build, on round 3's definition; E2L's design | parcels | wave 0 |
| 2a | the card day for stage E0 and the timed run of ten swaps, from a snapshot of E0C's merge | the lead | E0C merged |
| 2b | the definition's `e1`, the lead's, on the second size, from E2L's ruled design | the lead | the card day done; E2L's design ruled |
| 3 | E2L's build | a parcel | `e1` in the definition |
| 4 | stage E2's full run; stage E1's run made again | the lead | E2L merged |
| 5 | the round's close: its verifier, the narrow passes, VALIDATION.md, the ROADMAP | the lead | wave 4 |

Each brief carries a time box by the clock, as the standing rules ask. The round's length is an ESTIMATE of one to two days (T4), on round 3's two (L20).

## What the round is for

| # | the round is worth running if | basis | source or command | falsified by |
|---|---|---|---|---|
| W1 | on the card, every record of every piece of stage E0 equals the model's, at five amplitudes, and each amplitude's count equals round 1's (round 1's stream, in pieces or by a new link) or is inside D8's tolerance (runs with seeds of their own) | BELIEVED | L1 at a smaller scale and one amplitude; L10 for the model's counts | the card day's comparison and its judge |
| W2 | in software, after the pulse changes, the recovery of the adaptive and reset models against the frozen one is measured, at an equal false-alarm rate, in labelled windows after the change | DECISION | measuring it is the point; its direction is known (option B), its size and speed are not | stage E2's full run |
| W3 | nothing round 3 holds breaks: both sizes of the gate pass at the round's end | BELIEVED | each round so far | the gate |

## Other figures

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| T1 | A run of 2^22 frames on the card is about 0.84 s of the kernel at 200 ns a frame | COMPUTED | 4,194,304 x 200e-9, from L3 | a timed run |
| T2 | It holds 32,767 injections, of which 31,743 reach the injector while it runs, about 39,000 a second; six such runs are 196,602 injections | COMPUTED | 4,194,304 / 128 - 1 (`hw/card/card.py`'s schedule); 32,767 - 1,024; 5.0e6 / 128; 6 x 32,767 | that schedule |
| T3 | The model makes a run of a quarter of an amplitude, about 6.4 million frames, in about a minute and a half of one core | ESTIMATE | L8: 25.6 million frames in about six minutes; the comparison adds to it | a timed run |
| T4 | The round takes one to two days by the clock | ESTIMATE | L20, with one parcel a track against round 3's four and its build | the round |
| T5 | The card's records for five amplitudes of E0 are about 2.7 GB at 21 bytes a record, about 4.1 GB as 32-byte slots | COMPUTED | 5 x 25,600,128 x 21 and x 32 | arithmetic |
| T6 | Five amplitudes of E0 are about 128 million frames; round 3's card day ran about 5.9 million, so about twenty-two times as many | COMPUTED | 5 x 25,600,128 = 128,000,640; 5 x (131,072 + 1,048,576) = 5,898,240; the ratio 21.7 | arithmetic |
| T7 | The card allows about 1,000 to 10,000 trial generations an hour by its own time, and about 100 to 1,000 with the host's reading, scoring and training between them, at about 10,000 injections a generation | ESTIMATE | the card's part: 128 x 10,000 frames at 200 ns is 0.26 s (L3), a swap 0.1 to 0.5 ms (`docs/studies/CARD-first-light.md`, row C10); a run of 2^20 frames 0.347 to 0.351 s from the host's first operation to its last, by each part-two case's `trace.json` (round 3's ledger, 2026-11-25 08:10; not in the tree). The host's part is not measured | the card day's timed run of ten swaps |

## How the round is held

As round 3, with what it taught. Each is from Logan's word or from something `docs/VALIDATION.md` records.

- **Parcels on Opus**, named in every dispatch, by his word of 2026-11-24. **Verifiers on Opus**: his answer to round 3's question 5, which the lead reads as standing for round 4 and question 6 asks.
- **The lead's closing documents are written from commands**, and a correction is followed through the whole tree. Round 3's closing passes found four wrong statements of the lead's and one that said more than its evidence at the first, three more at the second, and three things left standing at the third. At least three of them were corrections or restatements whose consequence the lead did not follow.
- **The lead's work on the box and the card goes past a verifier like a parcel's**, with its evidence copied where the verifier can read it: the run folders, and excerpts of any report on the box.
- **A probe's range is read as what it covers**, not as the call's; a report's section is read before its figure (round 3's misreadings: the sync probe's range, and a hold slack read as setup).
- **Every long run on the box is detached** and watched by its log (trap 19). **The TimeSheet before every run.** The card booked sensitive, in daytime.
- **A conditional word is met plainly or asked again.** At round 3's close the lead read "Once the verifier returns ready" across to later passes; two verifiers said it stretched the words, and the lead asked.
- **A round branch, `r4`,** cut from `main`; nothing pushed until his word.

## What this plan does not settle

- **Which pulse `e1` is**, what "input scaling" means for this core, the reset's form, the adaptive model's cadence and window: E2L's design, fixed before any run, like E1's seeds.
- **Whether the pieces of round 1's stream can be read with all the history each score needs**, and how a piece's first frames are flagged: E0C's design. If they cannot, the stream falls back to runs with seeds of their own.
- **Whether the host keeps up for a run of about 6.4 million frames.** At 2^20 it never came near falling behind (L4); six times longer is BELIEVED to be the same, and the card day measures it.
- **Round 3's decisions still open with him** (the ROADMAP, "Open with Logan at round 3's close", item 2): this plan builds on them as they stand.
- **Phase B, the scorer in RTL, replay from HBM, the definition's maxima on the card, the second sample format, 200 MHz**: later rounds. So is his concept of two models on one stream (the ROADMAP's route 3), which is two cores on the card and waits on the pool leaving LUT memory; stage E2's five models in software are its question without the fabric.

## Questions for Logan

1. **Which round?**
   - *(Recommended)* **A, then B**: stage E0 on the card, then stage E2, induced drift, in software.
   - *Alternatives:* A, then B', stage E3 in software on real seismic noise ("I prefer to work with real data when able"), which is not yet designed and has no judge yet; A alone; B or B' alone; or C, toward 200 MHz, in place of A.
2. **Stage E0 on the card: which stream?**
   - *(Recommended)* **Round 1's own stream, in pieces with offset seeds**: no new build, and the card's counts must equal round 1's exactly.
   - *Alternatives:* runs with seeds of their own; or a new link with the buffer on four segments.
3. **Stage E2's drift?** (if B)
   - *(Recommended)* **A change of pulse shape, with the size of the change, `e1`'s overlap with `e0`, fixed before any run.** The overlap sets how much the frozen model loses: say a value, or leave it to E2L's design and the lead's ruling.
   - *The alternative:* a change of noise colour.
4. **The card day: the lead alone, as in round 3?** D0's section 10 says the card day is "the lead's and Logan's".
   - *(Recommended)* **Yes**, in a booked daytime window, telling you before and after.
   - *The alternative:* with you, at a time you name.
5. **The push at the close?**
   - *(Recommended)* **The lead asks you again** before `main` moves and anything is pushed.
   - *The alternative:* a standing word now, to push once the closing verifier's pass is clean.
6. **Verifiers on Opus again?**
   - *(Recommended)* **Yes**, as in round 3, named in every dispatch.
   - *The alternative:* another model you name.

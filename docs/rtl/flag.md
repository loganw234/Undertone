# The overflow flag, over all its sources and both directions

Written by parcel FLAG in round 3, 2026-11-24. Labels are those of [the design](../studies/D0-rough-design.md): MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure on this page is in the register at the end.

The detector core's overflow flag is sticky and rises when a hidden unit's value does not fit its field or the score does not fit its own ([core.md](core.md), section 3; [head.md](../model/head.md), section 1). Round 2's benches held it one stream at a time, and four verifier passes on the core each found one more one-place fault in it that the benches let through, the fourth, the closing verifier, two: the flag as the exclusive-or of its two sources, and a hidden value's fit tested on the low side only ([core.md](core.md), limit 23; [the plan](../plans/R3-first-light.md), row L21). This page is the test that replaces "one more stream for one more point": every state of the flag's sources together, in both directions, made by construction. It changes no line of `rtl/core/`.

**What a pass here is evidence of:** that on these streams the core's records, the flag among them, equal the model's word for word, and that the status register's bit `overflow` reads the model's flag. It advances D0's gate "overflow" in RTL simulation: its clause "the sticky flag rises where a width is a choice". It is held by the stage `rtl-benches`, which is the registry row of the gate "bit identity"; no row of `tests/gates.toml` is added. It is not evidence about sensitivity, which has its own authority.

## 1. Where things are

| what | where |
|---|---|
| the cases, their constructions, and a second evaluator | `rtl/tb/flag_cases.py` |
| the bench | `rtl/tb/bench_flag.py` |
| the core with twelve hidden units, a top of its own | `rtl/flag/core_twelve.sv` |
| its rows and mutants | `rtl/tb/benches.toml`, from the line that names this parcel |

## 2. The flag's sources

Read from the RTL:

- **Each hidden unit** (`rtl/core/core_head.sv`, stage h2). The value u >>> q fits when every bit from the field's top bit up is the same. It is out upward when the top bit of that window is 0 and another is 1, and out downward the other way. The window is 2 bits wide on these builds under `s16x1` and 10 under `s24x3`. The units' bits are ORed.
- **The score** (stage h4): the same test on the output sum shifted by the score shift. The frame's bit is the units' OR, ORed with the score's.
- **With no hidden layer** the one route makes unit 0, under the score shift, the source: the model's "score" on its version 1 route. The h4 test cannot fire there.
- **The record's flag** is the sticky bit ORed with the frame's, and the sticky bit takes that value; only reset clears it (`rtl/core/core.sv`, stage rec). **The status register's bit `overflow`** reads the sticky bit.

The model fits every stage, but at the definition's widths only the hidden values and the score can change a value (`model/detector.py`), so its sources are the RTL's. **At one output each source is in one of three states: it fits, it is out upward (past 2^63 - 1), or it is out downward (below -2^63).**

**"Both directions" is three things here:** a source leaving its field upward and leaving it downward; the flag rising where it must and not rising where it must not (every record before a case's first excursion is compared, and so are none cases whose sources sit at their edges); and the flag rising, then staying when every source is back in its field.

## 3. What is enumerated

| # | test | top, units | the cases | under `s24x3` | under `s16x1` |
|---|---|---|---|---|---|
| E1 | `flag_every_state` | `core_small`, 3 | every state of the four sources at the first output where any leaves its field: three states each, 81 | 81 | 11: none, the eight singles, and all four out twice (units up, down, up with the score up; down, up, down with the score down) |
| E2 | `flag_every_state` | `core_twelve`, 12 | none; each unit alone up and down (24); every unit but one, each left out in turn, the rest alternating up and down (12); all twelve up, down, alternating (3); the score alone up and down (2); all twelve alternating with the score up, and down (2) | 44 | 4: unit 11 alone up, unit 6 alone down, every unit but unit 0, all twelve with the score up |
| E3 | `flag_vclose_both_sources_at_once`, `flag_vclose_overflow_upward` | both | the closing verifier's two streams, as kept | 2 | 2 |
| E4 | `flag_one_route` | both | no hidden layer: out upward, out downward, nothing out | 3 | 3 |
| E5 | `flag_stays` | both | the flag rises, every source comes back into its field, the flag stays: from unit 0 and from the score | 2 | 1, the score's |
| E6 | `flag_far` | both | a first excursion past 2^64: the score up and down by real frames at output 1; a hidden value up and down by a swap at index 7 | 4 | 2, the score's |
| E7 | `flag_status_reads_the_flag` | both | the status bit `overflow` after nothing out, after the score's excursion, and after its return, held by `harness.hold` to the model's sticky flag | 3 | 3 |

E7 is not an identity test: its words are register words. The six others are, and the harness holds every record of them.

**Why three units whole.** E1's cases are every value of the per-output function from the four sources' states to the flag. A core whose flag at an output is any function of those states other than their OR differs from the model at the first excursion of some case: at that case's first excursion, or at the first record of every case if it flags "none". That one sentence covers the parity of the units, the exclusive-or of the two sources, one direction only, one unit only, and every other fault of that shape at once. It holds under `s24x3`; under `s16x1` the cut set ran (section 6).

**Why twelve.** The first build's head has twelve units and four filters ([the plan](../plans/R3-first-light.md), question 2), and on the full top nothing made units 1 to 11 overflow. `core_twelve` is `core_small`'s seven maxima with twelve units, so its streams cost what the small top's do. Twelve is not enumerated whole: 3^13 states. E2 holds each unit's index in each direction, every unit but one, all twelve, and the score with them.

## 4. How each case is made, and checked before the design runs

**The family.** Four filters of one row each, filter k on channel k mod channels; 6 taps; every coefficient at its lowest; every sample of every channel at its lowest; pass rectifier; pass between; hidden shift 0; a pool of 1,024. Each product is then exactly 2^E, with E = 32 under `s16x1` and 40 under `s24x3`. A filter's pooled value at output i is 2^E n_i, n_i being the extreme products in its window, and unit j's hidden sum is G_j 2^E n_i, where G_j is the sum of its four hidden weights: any integer from -2^19 to 4 x 131,071. Let c = 2^(63-E). A unit is out upward when G n >= c and downward when G n < -c.

- **i\*** is the first output at which a unit can leave either way: 685 under `s16x1` (n goes from 4,095 to 4,101) and 5 under `s24x3` (from 15 to 21).
- **A unit out** (R1): up, G = ceil(c / n\*); down, G = -(floor(c / n\*) + 1). It fits at i\* - 1 and is out at i\*.
- **The score out with a unit that fits** (R4): the lowest such unit drives it alone, under a head weight of 2 or -2 and G = ceil(c / 2n\*) or floor(c / 2n\*) + 1; every other head weight is 0.
- **The score out when every unit is out** (R5): an out unit's value wraps to about minus itself, so the score moves by the small steps only, and a score shift scales them. With every |G| equal to g and W the sum of each head weight times the unit's direction, the score is out at i\* and fits before it when |W| lies between c 2^s / (2c - g n\*) and c 2^s / (g n\_prev). The shift used is 10 under `s16x1` and 2 under `s24x3`.
- **None:** unit 0 just inside the bottom, unit 1 just inside the top, unit 2 driving the score just inside the top, at the stream's last output.
- **E5** uses a pool of 8 (a unit) or 4 (the score), then frames of zeros until every window is empty. **E6** puts unit 0's value under the largest head weight so that the score jumps from inside its field to between 2^64 and 2^64 + 2^63 at output 1. Or it swaps, at index 7 where n is 33, from all-zero weights to unit 0's weights all at one extreme, so that the hidden sum is -(2^64 + 2^59) or 2^64 + 524,156 x 2^40.

**The check, for every case, before the design is asked anything** (`Case.model_agrees`). `flag_cases.py` holds a second, restricted evaluator for this family: its own delay lines, windows and sums, and its own wrap to the field. It imports nothing of `model/detector.py`. From it the bench asserts that every source fits at every output before i\*, that at i\* the states are exactly the case's, and that a far case is past 2^64 there. From the model it asserts that the flag is 0 before i\*, that the flag is set from i\* exactly when some source is out, and that the model's score is the evaluator's at every output. A case whose construction is wrong fails there, by its label. Then the design runs, and the harness holds every word.

## 5. The mutants, and their evidence

Each mutant runs under one profile and edits `rtl/core/` in a copy. Every one failed as named on 2026-11-24 (row F5). Each line of evidence below was read against the case, record and field its fault predicts, predicted before it was first run (eleven in the design, two as they were added), and **every one first differed at exactly that case and record, in the overflow bit**. "Flags 0 / 2" is the RTL's / the model's: the overflow bit is 2, the settling bit 1.

| mutant | row | what it plants | the test that fails, and its first mismatch |
|---|---|---|---|
| `sources-are-a-parity` | `flag-s24x3` | the closing verifier's: the flag is the exclusive-or of the units' bit and the score's | `flag_vclose_both_sources_at_once`, record 5, flags 0 / 2; `flag_every_state`, case "unit 0 up, score up", record 5, flags 0 / 2, after 13 identical cases |
| `overflow-only-below` | `flag-s24x3` | the closing verifier's: a hidden value's fit tested on the low side only | `flag_vclose_overflow_upward`, record 5, flags 0 / 2; `flag_every_state`, "unit 0 up", record 5, flags 0 / 2 |
| `overflow-is-a-parity` | `flag-s24x3` | an earlier one: the flag is the parity of the units out | `flag_every_state`, "unit 0 up, unit 1 up", record 5, flags 0 / 2, after 9 identical cases |
| `overflow-not-sticky` | `flag-s16x1` | an earlier one: each record carries its own frame's bit only | `flag_stays`, the score's return, record 9 (the first record with every source back in), flags 0 / 2 |
| `overflow-from-unit-zero-only` | `flag-twelve-s24x3` | an earlier one: only unit 0 raises the flag | `flag_every_state`, "unit 1 up", record 5, flags 0 / 2 |
| `overflow-not-from-the-last-unit` | `flag-twelve-s24x3` | an earlier one: every unit but the build's last raises it, here unit 11 | `flag_every_state`, "unit 11 up", record 5, flags 0 / 2, after 23 identical cases |
| `overflow-only-above` | `flag-s16x1` | the closing verifier's fault's mirror: a hidden value's fit tested on the high side only | `flag_every_state`, "unit 0 down", record 685, flags 0 / 2 |
| `score-fit-only-below` | `flag-s24x3` | the score's fit tested on the low side only | `flag_every_state`, "score up", record 5, flags 0 / 2 |
| `score-fit-only-above` | `flag-s24x3` | the score's fit tested on the high side only | `flag_every_state`, "score down", record 5, flags 0 / 2 |
| `overflow-from-the-first-three-units-only` | `flag-twelve-s24x3` | only units 0 to 2 raise the flag: right on the small top, wrong at twelve | `flag_every_state`, "unit 3 up", record 5, flags 0 / 2 |
| `fit-by-two-bits` | `flag-s24x3` | a hidden value's fit tested by two bits only, the extended value's top bit against the field's sign bit | `flag_far`, the hidden value far down by the swap, record 7, flags 1 / 3 (settling set on both sides) |
| `fit-window-one-bit-short` | `flag-twelve-s16x1` | the hidden fit's window starts one bit high, so a value in [2^63, 2^64) passes as fitting; under `s16x1` the window is then one bit and never fires | `flag_every_state`, "unit 11 up", record 685, flags 0 / 2 |
| `status-overflow-not-sticky` | `flag-twelve-s16x1` | the status bit `overflow` reads the last frame's own bit, not the sticky flag | `flag_status_reads_the_flag`, its third word (after the score's return), 0 where the model's flag is 1 |

The first two are the closing verifier's faults and the next four every earlier mutant of the flag. The other seven are this parcel's neighbours: each direction of each source left out, a fault at a unit index only twelve units have, the two ends of the fit's window, and the status bit.

## 6. The tier under `s16x1`, and what the rows cost

Under `s16x1` a hidden value can leave its field on these builds only after an unbroken fill: its first excursion is at the 686th frame, and such a case is 687 frames long, so a case costs about that. The design's rule, approved by the lead: the whole set under `s16x1` only if every run and mutant together take at most 150 seconds, else the cut sets of section 3. Two runs of the whole set took 114 and 205 seconds in all on a desktop other work shares (rows F2 and F3), the second past the rule. **So the cut sets run under `s16x1`, and the whole sets of E1 and E2 run under `s24x3` only.** With the cut the rows took 87 seconds in all (row F4). Each row's `limit` is about three times its longest run measured.

## 7. Limits

Each is stated by the behaviour it concedes.

1. **Sizes.** Three units are held whole and twelve by structure. No build of 1, 2 or 4 to 11 units is run, so a fault that shows only at a unit count between is not seen.
2. **Twelve units, not every state.** A fault in how the sources combine that shows only for some set of 2 to 10 units out together, other than every unit but one, is not seen at twelve. At three units every set is. *Restated by the lead at the merge, 2026-11-24, from the verifier's pass (VFLAG):* E2 also never drives the score out together with 1 to 11 units out, and drives every unit but one, and all twelve, only in the direction patterns it names. A core that drops the flag when exactly one unit and the score are out passes all 44 of E2's cases at twelve units (VFLAG built it: 307 records identical), and fails at three units, "unit 0 up, score up", record 5. At twelve, such faults are not seen.
3. **Under `s16x1` the cut sets ran** (section 6). E1's other 70 states and E2's other 40 cases ran under `s24x3` only. The RTL's text is one; the fit's window differs, 2 bits against 10. So the claim "every function of the states other than their OR is seen" is made for `s24x3`. Under `s16x1` the eight singles, none and two of the sixteen all-out states are seen.
4. **Values.** At its first excursion a source leaves its field by at most one step of the stream: G x 2^E x 6, at most about 2^53.6 under `s16x1` and 2^61.6 under `s24x3`. E6 is the exception. Nothing is put at exactly 2^63 - 1 or at exactly 2^63, so a fit test that is wrong at one value only is not seen. *Restated by the lead at the merge, from VFLAG:* this said the family "cannot reach" 2^63; for the score it can (at output 0, G = -2^19, a head weight of -2^17 and a score shift of 5 under `s16x1` or 13 under `s24x3` put the score at exactly 2^63 before its wrap, and the model flags it); no case puts it there. For the hidden values at 2^63, and for 2^63 - 1 everywhere, the reason holds. Exactly -2^63 is `bench_core`'s stream 2.
5. **The hidden shift is 0 and between is pass** in every case here. The fit after the shift and abs at the extreme are `bench_core`'s (core.md, limit 21), not this bench's.
6. **The bank is not under test.** Every sample and coefficient is at its lowest, with one row a filter and every channel at the same value. A fault that reaches the head's inputs only by other samples belongs to the bank's benches.
7. **Gaps.** A stream of more than 100 frames is unbroken, but for E3's, which keep the closing verifier's 0 or 1 clocks between frames; a shorter one has 0 or 1.
8. **A hidden value past 2^64.** Under `s16x1` on these builds no hidden value reaches 2^64, since the hidden sum is 65 bits. Under `s24x3` the first excursion without a swap is within one step of the edge. E6's two swap cases, both on unit 0, are the only far hidden values. So a two-bit fit test is seen only by them, and only under `s24x3`: *(restated by the lead at the merge, from VFLAG)* and only on unit 0. A two-bit fit test on any other unit is seen by no case; VFLAG built it and it passed `flag_far` and `flag_every_state`.
9. **Stickiness from a hidden source** is shown under `s24x3` only: under `s16x1` its return needs about 690 more frames. From the score it is shown under both.
10. **The status bit is read at the end of a stream,** with nothing in flight, not at every clock.
11. **The flag across a swap is not driven here.** E6's swap is the case's own first excursion; no case raises the flag and then swaps. A flag cleared by a swap passes this bench, and is `bench_core_max`'s `bit_identity_boundaries`, "the flag stays, across a swap", and not this page's.
12. **A mutant shows the bench sees its fault under one profile,** the one section 5 gives.
13. **Nothing here is evidence about sensitivity.**

What this changes in [core.md](core.md)'s limit 23 is for the lead to restate. On the small top every state of the four sources is driven at the first excursion, by construction, under `s24x3`. At twelve units, on a top of its own, the structure of E2 is driven. The closing verifier's two faults now each have a mutant that fails a named test. The full top's own sentence stands: nothing new runs on `core`.

## 8. Claims register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| F1 | Every case of E1 (81) and E2 (44), under each profile, is what its label says by the second evaluator, and the model's flag and score agree with it at every output; i\* is 685 under `s16x1` and 5 under `s24x3`; the all-out score shifts are 10 and 2 | MEASURED | the bench's own check before each case; outside the simulator, the same checks over every case of both lists on both builds, 2026-11-24 10:18, in the parcel's scratch folder; the bench's log line "flag_every_state: 3 units, 81 cases (whole), i* = 5" | a case whose check fails |
| F2 | The whole sets under both profiles, with eleven mutants, took 114 seconds of run time in all: the four rows 41, 35, 6 and 4, and the mutants 28 | MEASURED | `python tools/check_rtl.py rtl-benches --root . --state <a folder>` on a copy whose manifest held the four rows alone, 2026-11-24 10:21; the lines "ran ... in n s" of that folder's `runner.log`, summed | a rerun |
| F3 | The same with the final thirteen mutants took 205 seconds in all: the `s16x1` rows 65 and 59 | MEASURED | the same command at 10:23; its `runner.log`, summed | a rerun |
| F4 | With the cut sets under `s16x1` the rows took 87 seconds in all: the four rows 16, 12, 8 and 6, and the thirteen mutants 45; the stage passed in 19 seconds of wall time, 28 tests in 4 runs of 4 benches, 19,681 records identical to the model's, 13 mutant runs each failed as named, 17 build logs with no line in them | MEASURED | the same command at 10:24; its `runner.log`, summed, and its OK line | a rerun |
| F5 | Each of the thirteen mutants first differed from the model at the case, record and field of section 5's table | MEASURED | the evidence files of the run of F4, each mutant's MISMATCH lines read with the IDENTICAL lines before them | a rerun whose evidence differs |
| F6 | The 19,681 records are 11,701 under `flag-s16x1`, 673 under `flag-s24x3`, 6,893 under `flag-twelve-s16x1` and 414 under `flag-twelve-s24x3` | MEASURED | the identity tests' IDENTICAL lines of the run of F4, their records summed for each run | a rerun |
| F7 | Side by side with three other runs, the small top under `s16x1` simulated about 1,635 clocks a second, and `core_twelve` about 1,110 | MEASURED | cocotb's own table in the logs of the whole sets' first run, 2026-11-24 10:20 (16,350 and 11,099 ns a second at a clock of 10 ns) | a rerun |
| F8 | A hidden sum of the small top and of `core_twelve` is 65 bits under `s16x1` and 73 under `s24x3`, so the fit's window is 2 bits and 10 | COMPUTED | `rtl/core/core.sv`, W_HEAD: 32 + 18 + clog2(5 x 1,024 x 6) and 40 + 18 + the same; `rtl/core/core_head.sv`, W_HEADX | the RTL's widths changing |
| F9 | At its first excursion without a swap a hidden value leaves its field by less than one step of at most 2^19 x 2^E x 6: about 2^53.6 under `s16x1` and 2^61.6 under `s24x3`, so never past 2^64 | COMPUTED | G at most 2^19 in magnitude; n grows by at most 6 an output in this family | a case of the family whose excursion is larger |
| F10 | The rows' limits are 50, 30, 40 and 30 seconds, about three times the longest run of each measured | DECISION | F3 and F4; the lead's ruling at the word to build | the lead |
| F11 | In the gate's second size on the tree of this parcel's first commit, the stage `rtl-benches` held 200 tests in 18 runs of 17 benches, 83,627 records and 109 mutant runs, which is round 2's 172, 14, 13, 63,946 and 96 with F4's 28, 4, 4, 19,681 and 13 added; this parcel's runs took 81 seconds of it | MEASURED | `bash verify/run.sh --with rtl`, run 20261124-102804-655d303, 2026-11-24 10:28 to 10:37: the stage's OK line, and the lines "ran flag-... in n s" of the stage's `runner.log`, summed; round 2's figures from [the plan](../plans/R3-first-light.md), row L2 | a rerun |

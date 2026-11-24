# The source and the injector in RTL

Parcel RTL-A, round 2. Two modules that make the stream a detector sees, each held against the reference model in simulation: `rtl/source/source.sv` (with `rtl/source/source_mulc.sv`) against `model/source.py`'s `Noise`, and `rtl/inject/inject.sv` against `model/inject.py`. Their benches are `rtl/tb/bench_source.py` and `rtl/tb/bench_inject.py`, with the helpers `rtl/tb/source_bus.py` and `rtl/tb/source_seeds.py`, and their rows and mutants are in `rtl/tb/benches.toml`. How the RTL side works is `docs/rtl/README.md`.

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure here has a row in the register at the end.

**What rests on what.** Everything here is bit identity: the RTL's words against the model's, on the streams the benches run. **Nothing here is evidence about the noise's tails, or about sensitivity.** A source that equals the model sample for sample inherits the model's own gate on its tails and claims no more. Nothing here is synthesised: no cost, no clock, no timing.

## 1. The source

**Words.** The model's word i starts from `seed + GAMMA * (i + 1)` modulo 2^64 (`model/source.py`, lines 74 to 78). The source makes its words in order from word 0, so that number is a 64-bit register that starts at `seed + GAMMA` and gains GAMMA at each word: the first of the generator's three multiplications is an addition. The two mixing multiplications are `source_mulc`: the ten products of 16-bit limbs whose weight is below 2^64, registered at one clock and summed at the next (S1).

**The three constants and the three shifts are typed once in `source.sv` and once in the model. The definition does not hold them**: they are a fact in two places with no generated copy. What holds them is the bench on all 64 bits of every word, and six mutants.

**A word to a sample.** The word's lowest bit is the sign; its other 63 bits, u, are looked up; the magnitude is the number of table entries at or below u. The table is a memory the host loads, at most MAX_NOISE_TABLE entries, 32,767 (S2): every table the model accepts under `s16x1`, and the table of stage E0's sigma among them (S16). The search is 15 comparisons, one a clock, whatever the data (S3).

**The last entry is never handed over.** The model's table ends at its first entry equal to 2^63, and u is at most 2^63 - 1, so that entry is at or below no u and adds nothing to any count (S4). The host hands over the entries before it, and their count, which is the largest magnitude.

**Frames.** Frame n, channel c is made from word n * CHANNELS + c: one engine makes the words in order. One sample is 20 clocks, so **the source offers a frame every 20 clocks under `s16x1` and every 60 under `s24x3`**, `out_valid` high for one clock, and frame n is seen `1 + 20 * CHANNELS * (n + 1)` clocks after the edge that takes the start write (S5). The frame is on `out_valid` and `out_frame`, channel c at `out_frame[c*SAMPLE_BITS +: SAMPLE_BITS]`. There is no back-pressure.

`word_valid` and `word` put each word out as its sample is made. They are ports for the bench, not a switch: the module behaves the same with them unconnected. They exist because a sample is a lossy view of a word (S6).

## 2. The injector

A frame is taken at every rising edge where `in_valid` is high, one a clock if they come so, and is offered **52 clocks later** whether or not a pulse is on it (S7). For a frame inside a record, what is added to every channel is `pulse[j] * amplitude_num / amplitude_den`, a tie to the even integer.

**Every denominator the model takes.** The product's magnitude, at most 2^46, goes through a restoring divider of 47 stages, a new division entering at every clock (S8). Then the model's rounding: one more when twice the remainder exceeds the denominator, or equals it with the quotient odd; then the sign. Rounding the magnitude and restoring the sign is the model's floor-and-bump exactly, by the four cases worked by hand (S9).

**A sum outside the sample's range is refused at that frame**, INJECT_RANGE: that frame is not offered and no later one is. Nothing is clipped and nothing wraps.

**The schedule.** Truth records are written through four rows, one field a row; the write of the denominator offers the record. They are written in stream order into a store of MAX_INJECT_PENDING, 1,024, and a record leaves when its last sample has been added, so a host may write more while a run goes on. Each record is checked as it is offered, by the model's rule in the model's order, and **a refused record ends the run**.

**`inj_frame`** is the index the next frame taken will have; writing it begins a run there. After `rst` the index is 0. The model's injector always begins at 0. **The bench's mapping, which is the bench's and not the model's: a fabric run begun at F with records at index i is held against the model's run from 0 with those records at i - F.**

**The pulse** comes from the generated package's sixty-four integers, `PULSE_E0_SAMPLE_0` to `PULSE_E0_SAMPLE_63`, gathered by a function in `inject.sv`.

## 3. The registers

Two blocks of the definition, `source` and `inject`, each on the register port every block has: `reg_valid`, `reg_we`, `reg_addr`, `reg_wdata`, and `reg_rdata`, a register. Outside its own block a module does nothing: a write is ignored and a read answers 0. **Inside it no write is silent: it is taken, or refused by name.** No register here has a bit that means nothing, and a command is the write of a value's last word.

| row | what a write does |
|---|---|
| `src_seed`, two words | the seed |
| `src_table_length` | begins a new table of that many entries, and clears the refusal |
| `src_table_entry`, two words | the write of the upper word stores the entry at the next place |
| `src_frames`, two words | **the write of the upper word starts the run** |
| `src_refusal` | a write of 0 clears it, in every state, during a run too |
| `inj_frame`, two words | the write of the upper word empties the store and the pipeline, clears the refusal and begins a run |
| `inj_truth_index` (two words), `inj_truth_pulse_id`, `inj_truth_amplitude_num`, `inj_truth_amplitude_den` | a truth record; **the write of the denominator offers it**. Write-only: nothing reads truth back |
| `inj_refusal` | a write of 0 clears it, in every state. Clearing does not begin a run: only `inj_frame` does |

Read-only: `src_status` (one bit: a run is going), `cap_noise_table`, `inj_pending` (how many records the store holds), `cap_inject_pending`. A refusal register reads the **first** refusal since it was cleared.

**Every row of two words is taken whole, and a test holds each.** `src_seed`: `words_are_the_models`, whose seeds have bits set in the upper word. `src_table_entry`: `frames_are_the_models`, whose tables have entries past 32 bits. `src_frames`: `frames_are_the_models`, by its counts of 2^32 + 3 and 2^32, and the mutant `frames-upper-word-dropped`. `inj_truth_index` and `inj_frame`: `a_run_begun_far_out`, whose runs begin and whose records sit past 2^32 and past 2^63.

## 4. The refusals

Seven names are raised in this fabric, counted: NOISE_RANGE, RECORD_FIELD, PULSE_UNKNOWN, INJECT_OVERLAP, INJECT_PENDING, INJECT_RANGE, REGISTER_ACCESS (S10). The last is raised in both modules.

| name | case | what the stream does |
|---|---|---|
| NOISE_RANGE | `src_table_length` above the smaller of MAX_NOISE_TABLE and the profile's largest sample: the model's own condition, a magnitude past `largest` | the write is not taken; a start then does nothing |
| REGISTER_ACCESS, source | a write to a read-only row, to an offset with no row, or to one that is not a word's; anything but 0 into `src_refusal`, in every state; **every other write to the block during a run**, all but the write of 0 that clears the refusal; an entry written when the table has its declared length; a start with fewer entries written than declared; **a start with no table declared since `rst`** | the write is not taken. **A run goes on untouched**: the stream stays the model's for the configuration it began with |
| RECORD_FIELD | a pulse_id word that does not fit its 16 bits, or a denominator of 0 | the run is over: no frame is offered |
| PULSE_UNKNOWN | a pulse_id that names no declared pulse | the same |
| INJECT_OVERLAP | a record that starts before the end of the one before it, **or before the frame the injector has reached** | the same |
| INJECT_PENDING | a record offered when the store holds 1,024 | the same |
| INJECT_RANGE | a sample plus what is added leaves the range, at frame n | frame n is not offered, nor any later one. The frames before it were, as the model hands them out before it refuses |
| REGISTER_ACCESS, injector | a write to a read-only row, to an offset with no row, or to one that is not a word's; anything but 0 into `inj_refusal`, in every state; a record offered after the run has ended | the write is not taken, and a run goes on untouched |

**With a refusal latched in the source a start does nothing**, a latched REGISTER_ACCESS among them: the host clears, then starts.

The second half of INJECT_OVERLAP is the fabric's: the model has the whole schedule before frame 0, and a fabric that takes records during a run can be handed one whose frame has gone. INJECT_PENDING and REGISTER_ACCESS are the fabric's alone: the model has no bound on a schedule and no bus.

**In the host library and not here:** INJECT_PAST_END and the injector's STREAM_LENGTH (the injector does not hold the stream's length); the source's STREAM_LENGTH (more frames than 2^64 words hold); NOISE_SIGMA, SEED_RANGE and PROFILE_UNKNOWN. CHANNELS and SAMPLE_RANGE cannot occur: a frame is its bits.

## 5. Truth isolation

`inject`'s outputs are `out_valid`, `out_frame` and `reg_rdata`, and no other. A truth record reaches `out_frame` only through the adder; `out_valid` only as a refusal that ends the run, and otherwise every frame comes out 52 clocks after it went in, with a pulse or without, so truth is not in the timing; `reg_rdata` as `inj_refusal` and `inj_pending`. The truth rows are write-only. `out_frame` is CHANNELS * SAMPLE_BITS bits of samples and carries nothing else.

For a bench that joins the injector to a detector core: wire the core to `out_valid` and `out_frame` and to nothing else of `inject`. Other truth records that add the same samples, which the bench here holds at the injector's output: the same ratio written otherwise (3/2, 6/4, 3000/2000); a record that adds only zeros put in, taken out or moved.

## 6. The benches, and what each control shows

**The comparison.** `harness.exchange` drives frames and collects words; the register port is driven by `source_bus.py`, since `exchange` drives one valid and one word; `harness.hold` compares and leaves the evidence. **`hold` refuses an empty expectation, and a run the model refuses before any frame has no frame to hold. So every comparison of frames ends with one more word: the block's refusal register, read after the stream, under a marker bit, against the code of the name the model refused by, or 0. For a comparison of frames the count of words the evidence carries is therefore one more than the frames compared. A comparison of the generator's words carries no such word: its count is the words.**

**Whose expectation.** The frames, the words and the names are the model's, but where the bench's own docstrings say otherwise: the mapping of a run begun at F; INJECT_OVERLAP's second half; INJECT_PENDING; REGISTER_ACCESS. Those expectations are this design's and the lead's ruling.

| control | on the RTL side, a mutant | on the model side, a test | how the fault is known to be reached |
|---|---|---|---|
| a generator with one constant changed | six: bit 0 and bit 63 of the increment and of each mixing constant, three under each profile | `control_model_constant_bit` | a changed bit of the increment moves the sum for word 0, and every later step is one to one (S11). For bit 63 of a mixing constant the product changes only when the multiplicand is odd: the test works out the first word that differs and requires the report there |
| a table one entry short | `table-one-entry-short` | `control_model_table_one_short` | **the seed is built, not drawn**: `source_seeds.py` undoes the mix, and the bench asserts through the model that the word and the sample aimed at are there (S12) |
| D0's four for the injector | `adds-nothing`, `one-sample-late`, `sign-flipped`, `half-amplitude` | `control_model_five_wrong_injectors` | the first record is index 5 at 3/2, and e0's second sample times 3/2 is 1.5, which is 2: each first shows at frame 6 (S13) |
| a tie rounded upward | `tie-upward` | the same test | e0's second sample is 1, and at 1/2 that is a tie whose floor is even: the rule gives 0 and upward gives 1 (S14). The bench counts the ties its schedule holds before it compares |

**The refusals have two mutants a module, not two a name** (the lead's ruling, for the stage's length). Each bench has one test for each refusal name, and each of the two mutants must fail every one of those tests: `refuses-nothing`, a build in which no refusal is ever latched and the refused cases named below are taken; and `every-refusal-misnamed`, a build in which the number latched has its lowest bit flipped, which is another declared name's number each time. So each name's test is seen to fail with its refusal absent and again with its number wrong. The stage's judge reports any named test that does not fail, and any that fails without a mismatch of its own. On the model side, `control_model_refusals` in the injector's bench hands the comparison a model that accepts a sum out of range and one that names it INJECT_OVERLAP. **What this concedes: no mutant removes one name's check and leaves the others; and the model-side control is run for one name, INJECT_RANGE.** The injector's rows carry two mutants more that touch a refusal, at the range's two ends; the pass that found them is told below.

**Every mutant runs under one profile** (the same ruling). Each bench has two rows in the manifest, one a profile, so the bench itself runs under both sample formats; a mutant is carried by one of them. **A mutant shows that the bench sees its fault under that one sample format.** None of these faults depends on the format.

| mutant | row, and so its profile | must fail | what it plants |
|---|---|---|---|
| `gamma-bit0` | `source-s16x1` | `words_are_the_models` | bit 0 of the increment |
| `mix1-bit63` | `source-s16x1` | the same | bit 63 of the first mixing constant |
| `mix2-bit0` | `source-s16x1` | the same | bit 0 of the second |
| `table-one-entry-short` | `source-s16x1` | `every_boundary_is_reached` | a search that never counts the table's last entry |
| `refuses-nothing` | `source-s16x1` | `refusal_noise_range`, `refusal_register_access` | a table longer than the build holds is taken, and no refusal is latched |
| `gamma-bit63` | `source-s24x3` | `words_are_the_models` | bit 63 of the increment |
| `mix1-bit0` | `source-s24x3` | the same | bit 0 of the first mixing constant |
| `mix2-bit63` | `source-s24x3` | the same | bit 63 of the second |
| `every-refusal-misnamed` | `source-s24x3` | the two refusal tests | the number latched has its lowest bit flipped |
| `frames-upper-word-dropped` | `source-s24x3` | `frames_are_the_models` | the upper word of `src_frames` is not used: a count of 2^32 + 3 runs three frames |
| `adds-nothing` | `inject-s16x1` | `stream_is_the_models` | the delta is 0 |
| `sign-flipped` | `inject-s16x1` | the same | the delta's sign |
| `tie-upward` | `inject-s16x1` | `ties_go_to_the_even` | the rounding drops "with the quotient odd" |
| `every-refusal-misnamed` | `inject-s16x1` | the six refusal tests | the number latched has its lowest bit flipped |
| `largest-sample-refused` | `inject-s16x1` | `refusal_inject_range` | a sum equal to the largest sample is refused |
| `one-sample-late` | `inject-s24x3` | `stream_is_the_models` | the pulse begins one frame after its index |
| `half-amplitude` | `inject-s24x3` | the same | the denominator is doubled |
| `refuses-nothing` | `inject-s24x3` | the six refusal tests | every record offered is taken, a sum out of range is offered as it wraps, no run ends, no refusal is latched |
| `smallest-sample-refused` | `inject-s24x3` | `refusal_inject_range` | a sum equal to the smallest sample is refused |
| `one-register-more-after-a-pulse` | `inject-s24x3` | `latency_is_fifty_two_clocks`, by its count of clocks: the words are the model's, so it names no kind of mismatch | every frame after the first with a pulse on it takes 53 clocks |

Twenty mutants, twenty mutant runs (S15).

**What the verifier's pass found, and what was done.** A verifier then read this parcel in a clone in which the lead had planted faults. It found no word, sample, refusal or clock count where the RTL and the model differ. It found one thing wrong and two holes, and each is answered here. (1) **Numbers typed into the RTL that the package holds**: the truth index's 64 bits, the bus word's 32 in several forms, the amplitude's 32. Each is now derived from the package, and each module stops every run at time zero, by name, if a row's words no longer fit the field they carry. What stays typed is said in limit 3. (2) **No test held the upper word of `src_frames`**: a source that dropped it passed the whole gate. `frames_are_the_models` now asks for 2^32 + 3 frames and for exactly 2^32, holds the first five and the first two against the model asked for the same count, and reads the source still running; the fault is the mutant `frames-upper-word-dropped`. (3) **Nothing showed that `latency_is_fifty_two_clocks` could fail**: the mutant `one-register-more-after-a-pulse` must fail it now, and that mutant is also what holds "truth is not in the timing".

**Twenty-six more one-place changes, tried once, and what they found.** After both benches passed, the parcel made twenty-six one-place changes of its own RTL, thirteen a module, in a copy of the tree with a manifest of its own, and ran the stage on the copy once. **Twenty-four were caught by the test named for them. Two survived, and they were one fault from two sides: an injector that refuses a sum equal to the largest sample, and one that refuses a sum equal to the smallest.** The RTL was right. No test held the range at either end: `refusal_inject_range` took its bound from the model as the widest whole amplitude that fits and one more, and that never puts a sum exactly on an end. So four cases were added to that test, a sum equal to each end, which is taken, and one past each, which is refused at the frame of the pulse's largest or smallest sample; and the two survivors went into the manifest as the mutants `largest-sample-refused` and `smallest-sample-refused`. Run again on the copy, all twenty-six failed as named (S22). The copy and its manifest are in the round's folder, not in the tree: the list is here.

| the change | the test that caught it |
|---|---|
| source: one clock more in a sample | `a_frame_every_twenty_clocks_a_channel`, `frames_are_the_models`, on their clocks |
| source: the sign inverted | `frames_are_the_models` |
| source: an entry equal to the looked-up number not counted | `every_boundary_is_reached` |
| source: the channels in the other order | `frames_are_the_models` |
| source: one frame too many | `frames_are_the_models` |
| source: one frame too few | `frames_are_the_models` |
| source: the longest table refused | `refusal_noise_range`, `the_widest_table_runs` |
| source: the seed's upper word dropped | `words_are_the_models` |
| source: a table entry's upper word dropped | `frames_are_the_models` |
| source: a start with the table short taken | `refusal_register_access` |
| source: a start with no table declared taken | `refusal_register_access` |
| source: the refusal's clear refused during a run | `refusal_register_access` |
| source: a write during a run not refused | `refusal_register_access` |
| injector: one pipeline stage more | `latency_is_fifty_two_clocks` |
| injector: the index kept to 32 bits | `a_run_begun_far_out` |
| injector: the pulse in one channel only | `stream_is_the_models` |
| injector: a sum equal to the largest sample refused | **none at first**; `refusal_inject_range` once it had the four cases |
| injector: a sum equal to the smallest sample refused | **none at first**; `refusal_inject_range` once it had the four cases |
| injector: two records that touch refused | `refusal_inject_overlap`, `records_that_touch_and_the_ends` |
| injector: the store one record short | `refusal_inject_pending` |
| injector: the rounding cut, never one more | `stream_is_the_models` |
| injector: the index written to `inj_frame` ignored | `a_run_begun_far_out` |
| injector: a record behind the frame reached taken | `refusal_inject_overlap` |
| injector: the pulse_id word's upper bits ignored | `refusal_record_field` |
| injector: a run that comes back when the register is cleared | `refusal_register_access` |
| injector: REGISTER_ACCESS ending the run | `refusal_register_access` |

That pass planted twenty-six faults and no others. A fault of another shape is not shown to be caught by it.

**And three sentences of this document that no test held.** Read against the benches after that pass, three things this page says were held by no test and conceded by no limit: that a record may be written while a run goes on; that a table length that is taken clears the refusal; that `inj_frame` empties the store. Each has a comparison now: a second record written about a hundred frames into a stream that runs a frame a clock, held against the model given both records before frame 0 (`stream_is_the_models`); a refusal latched and then cleared by a taken length, after which the table runs (the source's `refusal_register_access`); a run begun by `inj_frame` with 1,022 records still held, which is the model's and leaves none pending (`refusal_inject_pending`). None needed a change to the RTL.

**What the stage counts, and what it costs.** With these four rows the stage `rtl-benches` passes 60 tests in 6 runs of 5 benches, holds 33,326 words identical to the model's, and sees 34 mutant runs fail as named (S17). Of those, 48 tests, 4 runs, 24,366 words and 20 mutant runs are this parcel's (S18). **The 24,366 are words, not frames**: each comparison of frames ends with the refusal register as one more word, and the words of the generator are counted as words. The four rows and their twenty mutants took 77 seconds of one run of the stage, on a desktop other work was sharing; earlier states of the benches, with fewer cases and sixteen or eighteen mutants, took 112, 87, 96 and 90 seconds of four other runs. The foundation's bench, which the lead measured at 17 seconds alone, took 15 seconds in the first of those five runs and 129, 16, 21 and 18 in the others (S19, S21). In the run of 87 seconds the source's bench simulated 8,651 and 10,050 clocks a second under its two profiles and the injector's 3,743 and 2,984 (S20): the injector's 47 divider stages are evaluated at every clock.

**What these benches advance, and by which gate of D0.** Bit identity, its first part of three, for the stream: the source's words and frames and the injector's frames. Injection, on the RTL side, with D0's four controls and the fifth. Refusal, for the seven names above. Truth isolation, at the injector's output only: across the detector it is the seam's. Replay and noise tails are the model's: nothing here adds to them.

## 7. Limits

Each is stated by the behaviour it concedes.

1. **The source starts at word 0 only.** A run from frame f is the host's: the seed `s + f * channels * GAMMA` gives seed s's words from there (`docs/model/mod-a.md`, row A21). The fabric has no start index.
2. **The table's content is trusted whole, its order included.** The source checks the table's size. A host that loads another table gets another law with nothing here to say so; for entries out of order the stream is no model's at all. A table declared with no entries is content too and is taken: every sample is then 0. What is refused is a start with no table declared since `rst`: that is a host that forgot, not a table.
3. **The generator's constants are in two places** and the definition holds neither (section 1). With them stays the 64 of the generator's word, which is the model's and not the definition's. Two more numbers are typed in the RTL because the package has no name for them: the 8 bits of a refusal's number, which the definition bounds at 255 without generating a width; and the 8 bits of the source's own three counters and of the index into a pulse's samples. Every other width, offset, bound and code in the RTL is the package's. A definition that changed the generator's word or a refusal's byte would not move the RTL with it.
4. **One lookup engine.** A frame every 20 or 60 clocks, not every clock.
5. **Under `s24x3` the fabric holds fewer sigmas than the model**, and refuses the rest as NOISE_RANGE: the same 32,767 entries under both profiles.
6. **INJECT_PAST_END and the injector's STREAM_LENGTH are not here.** A host that writes a record ending past the frames it asks the source for gets a stream whose last pulse is cut by the stream's end, where the model refuses the run, and no fabric refusal says so.
7. **One pulse.** `inject.sv` names e0. A second declared pulse is not reached without an edit; its id is refused as unknown. **And one fault is invisible because of this pulse**: e0's last sample is 0, so an injector whose record leaves the store one sample early adds the same samples, and every test here passes it. The verifier built it. A pulse whose last sample is not zero would show it.
8. **A refusal register keeps the first refusal, so a run that ends after an uncleared REGISTER_ACCESS ends with that number, and the reason for the stop is not in any register.** In the injector REGISTER_ACCESS does not end a run; a refused record or a sum out of range does. If a write was refused and not cleared, and the run then ends, `inj_refusal` still reads REGISTER_ACCESS and nothing reads RECORD_FIELD, PULSE_UNKNOWN, INJECT_OVERLAP, INJECT_PENDING or INJECT_RANGE. The detector core has the same rule and a status bit that says "more than one"; the injector has no such bit. **A host library covers this by reading and clearing the register after each operation.** And once `inj_refusal` is cleared after a run has ended, the run is still over, with nothing but the missing frames to say so, until `inj_frame` begins another.
9. **A frame in the pipeline when a record is refused is not offered.** The model has no such case: it refuses a schedule before frame 0.
10. **No mutant removes one refusal name's check and leaves the others, and every mutant runs under one sample format** (section 6). A build that dropped one name's check only, or a fault that showed under the other format only, is held by the bench's own tests under both formats and by no mutant.
11. **Nothing is synthesised.** The limb products, the one-clock search step, the 47 stages and the store read without a clock are written to be buildable. One simulator, Icarus Verilog.
12. **The benches run the seeds, sigmas, schedules and lengths they name.** A fault that shows only elsewhere passes.
13. **Replay is not here**, nor a top that joins the two modules.
14. **A frame taken on the same clock as the write that begins a run is dropped, and is not counted.** `inj_frame` empties the pipeline, and a frame offered at the edge that takes its upper word goes with it: the next frame taken has the index written. A host begins a run while no frame is being offered.
15. **A record refused while a stream runs is held on the register only.** The case that offers one behind the frame the injector has reached asserts INJECT_OVERLAP in `inj_refusal`; the frames it collects are compared with nothing, since no model has that case. That no frame taken after the refused write is offered was seen by the verifier's own probe and is held by no test here.

## 8. Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| S1 | The low 64 bits of a 64-by-64 product are ten products of 16-bit limbs | COMPUTED | limb i by limb j has weight 2^(16 * (i + j)); those with i + j <= 3 are 4 + 3 + 2 + 1 | arithmetic; `words_are_the_models` |
| S2 | MAX_NOISE_TABLE is 32,767 and MAX_INJECT_PENDING is 1,024 | DECISION | the lead's, 2026-11-23, in the ruling on this parcel's design | the lead changing them |
| S3 | 15 comparisons hold every count to 32,767 | COMPUTED | 2^15 - 1 = 32,767 | arithmetic |
| S4 | The model's last table entry is at or below no looked-up number, and every earlier entry is below 2^63 | COMPUTED | `model/source.py`: line 227, the looked-up number is a word shifted right by one; lines 159 to 169, the table stops at its first entry equal to 2^63 and none exceeds it | a table with an entry above 2^63 |
| S5 | One sample is 20 clocks: two for each mixing multiplication, 15 comparisons, one to put the sample in the frame | COMPUTED | 4 + 15 + 1, from `source.sv`'s list of clocks; `a_frame_every_twenty_clocks_a_channel` asserts it | that test |
| S6 | A change of bit 20 of a word alone changes a sample with a probability below 2^-30 at sigma 1000 | COMPUTED | it moves the looked-up number by 2^19; a table of 9,155 entries has 9,155 boundaries (`docs/model/mod-a.md`, row A5), fewer than 2^14; 2^14 * 2^19 / 2^63 | arithmetic |
| S7 | The injector's latency is 52 clocks | COMPUTED | the registers on the way: 1 + 1 + 1 + 47 + 1 + 1; `latency_is_fifty_two_clocks` asserts that 52 is the only latency seen, and the mutant `one-register-more-after-a-pulse` must fail it | that test; that mutant surviving |
| S8 | The product's magnitude is at most 2^46, so the quotient is 47 bits | COMPUTED | a pulse sample is 16 signed bits and the numerator 32: 2^15 * 2^31 | arithmetic |
| S9 | Rounding the magnitude and restoring the sign equals the model's floor-and-bump for every numerator and every denominator of at least 1 | COMPUTED | `model/inject.py`, lines 41 to 46, against the four cases of a negative product: remainder zero, below half, above half, at the tie | `wide_amplitudes`, `ties_go_to_the_even` |
| S10 | Seven refusal names are raised in this fabric | COMPUTED | counted from section 4's table: six in the injector with REGISTER_ACCESS, two in the source with it, one shared | a recount |
| S11 | A changed bit of the increment changes word 0 | COMPUTED | the sum moves by 2^k, not 0 modulo 2^64; each later step is one to one (`model/source.py`, lines 12 and 13) | the mutant surviving |
| S12 | At sigma 1 the largest magnitude has a probability of 19 units of 2^-63 | COMPUTED | `vectors/mod-a/table.json`: 2^63 less the entry before the last, 9223372036854775808 - 9223372036854775789 | arithmetic |
| S13 | On a schedule whose first record is index 5 at 3/2, the four broken injectors first differ from the model at frame 6, and a tie upward at frame 7 | COMPUTED | `spec/pulses/e0.toml`: the samples 0, 1, 7; 1 * 3/2 = 1.5 and 7 * 3/2 = 10.5; `control_model_five_wrong_injectors` asserts both | that test |
| S14 | e0's second sample is 1, and at 1/2 half-to-even gives 0 where half-upward gives 1 | COMPUTED | `spec/pulses/e0.toml`; `model/inject.py`, lines 43 to 45 | arithmetic |
| S15 | Twenty mutants: five and five in the source's two rows, five and five in the injector's | COMPUTED | counted from section 6's table and from `rtl/tb/benches.toml` | a recount |
| S17 | With this parcel's rows the stage passes 60 tests in 6 runs of 5 benches, 33,326 words identical, 34 mutant runs each failed as named | MEASURED | `python tools/check_rtl.py rtl-benches --root . --state <a folder>`, 2026-11-23: its OK line | that command |
| S18 | 48 of those tests, 4 of the runs, 24,366 of the words and 20 of the mutant runs are this parcel's | COMPUTED | 2 x (9 + 15) tests; 33,326 less the 8,960 of the foundation's bench (`docs/rtl/README.md`, row R3); 34 less its 14 mutant runs (row R5) | arithmetic; those rows |
| S19 | This parcel's rows and twenty mutants took 77 s of one run of the stage, in which the foundation's bench took 15 s; earlier states of the benches took 112 s, 87 s, 96 s and 90 s of four other runs, in which the foundation's bench took 129 s, 16 s, 21 s and 18 s | MEASURED | the same command as S17, five times on 2026-11-23, on a shared desktop: the times of the results files under `<the folder>/out`, from the foundation's last mutant to the injector's last, one-second grain. One reading each, under a load that changed between them. The four earlier runs were of the benches with fewer cases, the first two of sixteen mutants and the next two of eighteen | that command, for the first figure; another load |
| S20 | In the run of 87 s the source's bench simulated 8,651 clocks a second under `s16x1` and 10,050 under `s24x3`, and the injector's 3,743 and 2,984 | MEASURED | that run of S19: the last line of cocotb's summary in `<the folder>/out/<run>.log` gives nanoseconds simulated for each second, 86514.67, 100495.01, 37430.04 and 29843.39, and a clock is 10 ns. One reading, under load, of the tree before the four cases were added | the same command today; another load |
| S22 | Of twenty-six one-place changes of this parcel's RTL, twenty-four failed the test named for them at the first run and two passed it; with four cases added to `refusal_inject_range`, all twenty-six failed as named | MEASURED | `python tools/check_rtl.py rtl-benches --root <the copy> --state <a folder>`, twice on 2026-11-23: the first printed two findings, both MUTANT-SURVIVED, for the two changes at the range's ends; the second printed "26 mutant run(s) each failed as named". The copy and its manifest are in the round's folder, `scratch/RTL-A`, which is not in the tree, so this cannot be rerun from a clone; the two survivors can, as the mutants `largest-sample-refused` and `smallest-sample-refused` of the gate | those two mutants surviving in the gate |
| S21 | The foundation's bench and its mutants take 17 s of the stage alone on the desktop | READ | the lead's message to this parcel, 2026-11-23, of its own run on commit 78c5101 | the lead's run |
| S16 | The table for stage E0's sigma, 1477, has a last index of 13,522, inside the 32,767 the source holds | MEASURED | `python -c "from model import source; t = source.gaussian_table(1477, 1); print(len(t) - 1)"`, 2026-11-23, which printed 13522; the sigma is `tests/test_seam_e0.py`, line 68 | a rerun |

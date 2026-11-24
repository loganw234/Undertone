# The seam: the three RTL blocks wired together

Parcel SEAM-2, round 2, 2026-11-23. The source, the injector and the detector core, each held against the reference model by its own parcel's bench ([source.md](source.md), [core.md](core.md)), wired into one top and held against the model's own run of the same configuration on every score word. The top is `rtl/seam/seam.sv` with `rtl/seam/seam_core.sv`; the bench is `rtl/tb/bench_seam.py` with the helper `rtl/tb/seam_host.py`; the rows and mutants are the last two rows of `rtl/tb/benches.toml`; one frozen input is `vectors/seam-2/handover.json`, held by `tests/test_seam2_handover.py`. How the RTL side works is [README.md](README.md).

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure here has a row in the register at the end.

**What rests on what.** Everything here is bit identity: the top's score words against the model's, on the streams the bench runs. **Nothing here is evidence about sensitivity**, which has its own authority, and nothing here is synthesised. The longest stream is 2,180 frames and every other is 420 or fewer (K1): long enough to hold the chain's wiring and nothing else.

**Which gate, and which part.** D0's gate "bit identity" has three parts: RTL in simulation, the host, the card. This is the first part, for the three blocks **together**: the two parcels held each block alone, each driving its block itself. D0's gate "truth isolation" is advanced on the RTL side, across the detector, which source.md left to the seam. D0's gate "swap" is advanced only in that a swap made through the chain's one bus, while the source runs, is the model's; the swap's own control, half the taps a clock late, is the core's bench's. D0's gate "learner" is not advanced: section 6 says what the hand-over here is and is not. `tests/gates.toml` has no new row: the stage `rtl-benches` already holds "bit identity", and these rows run inside it.

## 1. The top

`seam` takes `SAMPLE_BITS` and `CHANNELS`. Its ports are `clk`, `rst`, the register port's five signals, and `out_valid` and `out_record`. It has no stream input. Every wire of it:

| wire | from | to |
|---|---|---|
| `clk`, `rst` | the top | all three blocks |
| `reg_valid`, `reg_we`, `reg_addr`, `reg_wdata` | the top | all three blocks, each as it comes in |
| `src_valid`, `src_frame` | the source's `out_valid`, `out_frame` | the injector's `in_valid`, `in_frame` |
| `inj_valid`, `inj_frame` | the injector's `out_valid`, `out_frame` | the core's `in_valid`, `in_frame` |
| `out_valid`, `out_record` | the core | the top |
| `reg_rdata` | the three blocks' `reg_rdata`, ORed | the top |

The source's `word_valid` and `word` are left unconnected. There is no register at a joint, and no logic in the top but the OR.

**The core's build.** `seam_core` is `rtl/core/core.sv`, the same lines, at 2 filters, 64 taps, 3 rows, a pool of 4, a score shift of 12, 2 hidden units and a hidden shift of 16. 64 taps and 3 rows hold stage E0's shape under both profiles: one filter of the reference pulse's 64 taps reading every channel is 3 rows under `s24x3`, the bound itself. Two filters and two hidden units let a shape that is not E0's run through the chain. Everything else is small because every clock of the chain evaluates the core (K2).

**What happens at a joint.** The source raises `out_valid` for one clock every 20 clocks a channel and the injector takes its frame at that edge; the injector raises `out_valid` for one clock 52 clocks later and the core takes its frame at that edge; the core's record is out 11 clocks after (K3). Both the source and the injector write their frame register only with their valid, so each holds its frame until its next one. So of the two ways a joint can be a clock off, one changes the words and one does not: **data a clock after its valid** hands the block the frame before, and every record is wrong; **valid a clock after its data** hands it the right frame a clock late, and every word is right. The first is seen by any comparison of words. The second is seen only by a clock, which is why the bench holds the clock of every record of one stream (K4). Three of the words' tests were tried on it at the second joint and one at the first, and pass (K9).

## 2. Truth isolation, and what it rests on in this top

In the model the core is handed frames and nothing else (`model/run.py`). In this top the core is wired to `inj_valid` and `inj_frame` and to nothing else of the injector; the injector's only other output, its `reg_rdata`, goes to the bus.

**What the top cannot give: the register port is one bus.** The writes that carry a truth record reach the core's port as they reach the injector's. That the core does nothing with a write outside its own block is the core's own claim, held by its bench at five offsets (core.md, limit 18). What holds it for this chain is the test `truth_isolation`: four wordings of the truth that the model says add the same samples (the model's four streams are required equal, and its four truths required different), each chain held to the model, and the four chains' digests required equal. The wordings: a record at 3/1; the same at 6/2; a record of amplitude 0/5 put in before it; a record at 1/100000, which rounds every sample to zero, at another index.

Round 1's control was "a runner that hands the detector one bit of truth". Its like here is planted twice. On the RTL side, the mutant `truth-on-the-cores-side`: the top reads the truth records' indexes off the bus as they are written, keeps the exclusive-or of their lowest bits, and puts that bit into the lowest bit of the core's frame. The first two wordings leave that bit 0 and the chain is the model's on them; the third does not (K7). On the model side, `control_model_truth_reaches_the_core`: a model whose core is handed a frame with one bit flipped at a truth record's index.

**A truth record's ratio as written, not its value, reaching the samples** cannot be planted in the top's wiring: the ratio exists only inside the injector. It is the mutant `ratio-as-written`, a patched copy of `rtl/inject/inject.sv` (the manifest lets a mutant edit any of the bench's sources), in which the delta is the pulse times the numerator alone. The first wording has a denominator of 1 and is the model's on that mutant; 6/2 is not (K7).

## 3. The bench

**One port, three blocks.** A run (`seam_host.Chain.run`) is: reset; the core loaded and started by `core_host.load`; the source handed the model's own noise table without its last entry, and the injector the schedule's records, through `source_bus.Bus`; the seed and the frame count written, the write of the count's upper word starting the source. The two helpers are imported and neither is changed. Both drive the same five signals at falling edges and are never used at once. The writes that hand a table over and that offer a truth record are written again in `seam_host.py`, because the parcels keep them inside bench modules, which cannot be imported.

**Collecting, with no stream input.** `harness.exchange` is given no word to drive and listens on `out_valid` and `out_record` from the clock after the start write, as the source's own bench does. Then `harness.hold`, with the score records' prefix: the evidence line is the one `harness.compare` leaves. After every run the three refusal registers are read through the bus and each required 0. They are asserted, not added as words: **the evidence of the five identity tests is score records and nothing else.** And since the harness listens only inside `exchange`, `Chain` counts `out_valid` over each whole test and requires that count to equal the records the runs collected.

**Whose expectation.** The model's, in every comparison of records.

| what | the expected words |
|---|---|
| a run with no swap | `model.run.detect(Noise(profile, seed, sigma, N), schedule, N, blob, epoch)` |
| a run with a swap or a hand-over | `seam_host.model_records`: `model/run.py`'s lines (a core, the injector over the source, one step a frame) with `core.write_shadow(other)` and `core.commit(at)` called before the first frame |

`model/run.py` builds its core inside itself, so a swap cannot be made through it. The composition is held equal to `model.run.detect`, record for record, when nothing is done to the core (`composition_is_run_py`, called in `bit_identity_swap`). In the model the two calls are made before frame 0; in the chain the shadow is written and the commit made while the source runs. `model.weights.Store` gives every output before the committed index the old set and every one from it on the new, whenever before that index the calls are made; the bench requires that the commit was taken (the core's refusal register reads 0) and that fewer records than the index were out when it was.

**The clocks are this document's expectation and not the model's**: the model has frames and no clocks. Record k is expected `1 + 20 * CHANNELS * (k + 1) + 52 + 11` clocks after the edge that takes the start write, the sum of what the two parcels' documents state (K3).

**The tests**, each under both profiles:

| test | what it holds | streams |
|---|---|---|
| `bit_identity_first_frames` | E0's shape, a record at index 0, compared from record 0. The bench first requires, of the model, that the pulse reaches a record no later than the fourth | 96 frames |
| `bit_identity_chain` | E0's shape over six amplitudes, three of whose records touch, with a sample above three quarters of the range's top (the bench requires it of the model's stream); then two filters of 63 taps, reading different channels where the profile has more than one, abs, a pool of 3, two hidden units, abs between | 420 and 150 frames |
| `truth_isolation` | section 2 | four of 140 frames |
| `bit_identity_swap` | E0's shape swapped to other gains at index 40, inside a pulse, the shadow written once twelve records are out; then two filters with a pool of 4 and a hidden unit swapped to other weights, where the bench requires the model to mark exactly outputs 40, 41 and 42 as settling | two of 150 frames |
| `bit_identity_hand_over` | section 6 | 2,180 frames |
| `the_chains_clocks` | the clock of each of the first stream's 96 records | the first stream's |
| `one_bus_three_blocks` | twenty words read through the one bus: a word of each block, one below every block, a refusal latched in each block by a write to one of its read-only rows, and each cleared in turn while the others stand | none |
| `control_model_injector_bypassed`, `control_model_swap`, `control_model_truth_reaches_the_core` | section 4 | none of their own |

The three controls and the clocks' test use the words of a run an identity test has made and kept. When that run is not there, as in a mutant's run, which holds only the tests it names, the test makes the run itself.

The gains differ by channel, (3, -2, 1) under `s24x3`, and the noise differs by channel as the source makes it. The sigma is 50 under `s16x1` and 97/2 under `s24x3`.

**Every wait has a bound in clocks**, and passing it fails the test with a message that says what was waited for. Section 5 says why that sentence is here.

## 4. The controls

**On the model side.** The comparison is handed a wrong model and must report a WORD mismatch at the record this bench works out from the model, naming the field:

| control | the wrong model | where it must be reported |
|---|---|---|
| `control_model_injector_bypassed` | a core stepped over the source's frames | the first record the pulse reaches |
| `control_model_swap` | one that never swaps; one that swaps a frame late; one a frame early; one that commits with the shadow never written | record 40, 40, 39 and 40: the epoch for the first three, the score alone for the fourth |
| `control_model_truth_reaches_the_core` | a core handed one flipped bit at the truth record's index | within a pulse's length of that index |

**On the RTL side: fifteen mutants, each under one profile** (the lead's ruling for the RTL parcels). Fourteen are mutants of the top's wiring; one is a mutant of the injector. The last column is read from each mutant's evidence, not from its verdict (K7).

| mutant | profile | what it plants | must fail | where the evidence puts it |
|---|---|---|---|---|
| `injector-bypassed` | s16x1 | the core reads `src_valid` and `src_frame` | `bit_identity_first_frames` | record 2, the score |
| `joint-one-data-late` | s16x1 | the injector's `in_frame` a clock after its `in_valid` | `bit_identity_first_frames` | record 1: a score of 0 where the model has -7830 |
| `joint-two-valid-late` | s16x1 | the core's `in_valid` a clock after its `in_frame` | `the_chains_clocks` | record 0's clock: 85 where 84 is stated |
| `truth-on-the-cores-side` | s16x1 | section 2 | `truth_isolation` | the first two wordings identical; the third at record 1, the score |
| `ratio-as-written` | s16x1 | section 2; a copy of `inject.sv` | `truth_isolation` | the first wording identical; the second at record 68, the score |
| `swap-does-not-happen` | s16x1 | the commit's upper word never reaches the core | `bit_identity_swap` | record 40: epoch 3 where the model has 4 |
| `source-off-the-bus` | s16x1 | `reg_rdata` without the source's word | `one_bus_three_blocks` | word 1: 0 where the table's bound is |
| `a-high-bit-lost-at-joint-two` | s16x1 | at the core's input the bit below the first channel's sign carries the sign | `bit_identity_chain` | record 153, inside the largest record's window, the score |
| `hand-over-a-frame-late` | s16x1 | the commit's index reaches the core one higher | `bit_identity_hand_over` | record 2,072: epoch 0 where the model has 1 |
| `joint-two-data-late` | s24x3 | the core's `in_frame` a clock after its `in_valid` | `bit_identity_first_frames` | record 1: a score of 0 where the model has -6930 |
| `joint-one-valid-late` | s24x3 | the injector's `in_valid` a clock after its `in_frame` | `the_chains_clocks` | record 0's clock: 125 where 124 is stated |
| `inject-off-the-bus` | s24x3 | `reg_rdata` without the injector's word | `one_bus_three_blocks` | word 2: 0 where the store's bound is |
| `swap-a-frame-late` | s24x3 | the commit's index reaches the core one higher | `bit_identity_swap` | record 40: epoch 3 where the model has 4 |
| `shadow-never-written` | s24x3 | once the core is started the shadow's stream never reaches it; the commit does | `bit_identity_swap` | record 40: the score alone, the epoch right |
| `core-off-the-bus` | s24x3 | `reg_rdata` without the core's word | `one_bus_three_blocks` | word 0: 0 where the magic number is |

`inject-off-the-bus` is the one a seam most needs: with the injector's word off the bus its refusal register reads 0 for ever, and every "no block refused" above would be said of nothing. `a-high-bit-lost-at-joint-two` is there for the stream's amplitudes: three of the shorter tests were tried on it and pass (K9), since none of their streams has a pulse near the top of the range. `shadow-never-written` is there for the swap's weights: the epoch alone shows a swap that did not happen, and only other weights show a swap to the same ones.

**Tried once by hand, on a copy, and not in the manifest** (K8, K9). The first fourteen mutants above, each under the other profile; a register on both the valid and the data at each joint; and a commit whose index reaches the core one lower. All seventeen failed the test named for them, each at the record its fault predicts: the joints' two at record 0's clock, the early swap at record 39 with the new epoch where the model has the old. And four that should pass, since each backs a sentence here that says a test does not see a fault: valid a clock late at the second joint, on three of the words' tests, and at the first, on one; the lost high bit, on three of the shorter tests; truth on the core's side, on two tests whose schedules leave the planted bit at 0. All four passed every test they were handed, nine test runs. And on another copy, three faults of count, since every mutant in the manifest is a fault of words or of clocks: a source that runs one frame past its count, one that stops a frame short, and a top that stops putting records out after its ninetieth. Each was a COUNT mismatch from the harness on the first stream, at records 96, 95 and 90 (K15). Those two passes planted twenty-four faults and no others.

## 5. What the build found

**The chain was the model's as first written.** The top, the helper and the bench passed at their first run, under both profiles (K5). No block and no convention was found wrong.

**A wait with no bound hung the stage, and nothing bounds a test.** The bench waited for the design's twelfth record before writing the shadow. On a mutant whose design put out no record that wait never ended: the simulation ran on, the stage's own limit is 3,000 seconds for every bench together, and stopping the stage's client does not stop its container, which the lead stopped by hand (K10). The wait has a bound now, as every wait in this bench has. **The finding is the foundation's: neither the harness nor the runner puts a bound on a test**, so any bench with one wait that can fail to end holds the gate's second size for fifty minutes. The lead has said a limit a test goes into the runner.

**Icarus Verilog did not build the mutant that was written.** The mutant that hung was `.reg_valid(reg_valid && !(reg_we && reg_addr == REG_COMMIT_AT_OFFSET + 4))`, written inside the core's port connection to drop one write. Built by Icarus Verilog 12.0 it dropped the core's every write: after its load the core's status read 0 in every bit. The same expression with the literal `12'd252` in place of the parameter and the 4 dropped the commit alone; so did the same logic as an `assign` to a wire with the comparison in brackets of its own. And `.reg_wdata((reg_we && reg_addr == REG_COMMIT_AT_OFFSET) ? reg_wdata + 1 : reg_wdata)` added nothing at all: the swap's test passed on it (K11). The cause was not found. **What it concedes for every mutant in the manifest: a mutant written as an expression inside a port connection may not be the design it reads as, and "failed as named" does not show that.** The four mutants here that touch the bus's valid or its data are assigns to a wire with every comparison in brackets of its own, and the early swap of the hand-tried pass, written the same way, moved the swap to record 39: the arithmetic is applied.

**`core_host.load`'s own check passes on a core that never heard the bus.** It requires the core's refusal register to read 0, and a core no write reached reads 0. `seam_host.Chain.run` also requires the status bit `running` after a load. `core_host.py` is not changed.

**The trainer cannot run where a bench runs.** `learn/trainer.py` imports numpy and the simulation image holds none (K12). Section 6 is what was done about it, by the lead's ruling.

**What it costs.** The two rows and their fifteen mutants took 173 seconds of one run of the stage on a copy whose manifest held them alone, on a shared desktop; the hand-over's test was 16 and 45 seconds of that under the two profiles (K6). Inside the gate's second size the whole stage took 350 seconds with these rows, and the gate 10 minutes 4 seconds (K16): the second size with these rows is at the line past which only the lead runs it. In an earlier and faster reading the chain simulated about 3,600 clocks a second under `s16x1` and 3,680 under `s24x3`, which is about 180 and 61 frames a second (K2).

## 6. The learner's hand-over through the chain

**What it is.** The first time learned weights go into RTL. The core starts with a filter of the learner's shape, one filter of 64 taps reading every channel. The chain runs 2,180 frames with sixteen truth records in its first 2,050, the training period. Once the training period's records are out, the bench writes the trainer's blob to the shadow through the bus and commits it at index 2,072, the hand-over; one more truth record follows at 2,112. Every record is held against the model's run of the same blobs with the same `write_shadow` and `commit` (K13).

**What it is not.** It is not stage E1. **No efficiency is read from it and none is claimed.** Sixteen truth records is the smallest of that stage's six counts (K13), and it was chosen because it is the smallest: the trainer's rule gives each record two windows of 64 frames, so sixteen records are a training period of 2,050 frames. Whether these weights find anything is not looked at.

**Where the blob comes from.** The trainer needs numpy and the image has none, and the lead ruled that the image stays as it is. So the blob is made outside the image and frozen: `vectors/seam-2/handover.json` holds, for each profile, the configuration, the truth indexes the trainer was given, the hand-over index, the start blob, and the trained blob with its SHA-256. **That file is an input, pinned. It is not a known answer worked by hand, and nothing is judged by it.** `tests/test_seam2_handover.py`, in the gate's first size, makes the blob again on every run: the model's own frames for that configuration, `learn.trainer.train` on the training period, `learn.handover.candidate_blob`; and requires the frozen bytes to be those, byte for byte. Its control hands the trainer labels one frame off, either way, and requires another blob. Inside the image the bench imports nothing of `learn/`: it reads the bytes.

**Why the start blob is not the learner's blank one.** A blank filter scores every frame 0, and the records before the hand-over would then say nothing about the frames the trainer was given. The start blob's only tap that is not zero is the newest, with another weight in each channel, so every record before the hand-over is its own frame's weighted sum: the bench requires that of the model's records, and requires the training period's 2,050 scores to take more than 512 different values. So the chain's records over the training period hold its frames to the model's, as far as one weighted sum a frame holds them.

## 7. Limits

Each is stated by the behaviour it concedes.

1. **The streams are short.** All but one are 420 frames or fewer and the longest is 2,180. A fault of the chain that shows only after more frames than that is not seen: a counter of the source's or the injector's that wraps, a store that fills. Each block's own bench runs its own counters; nothing runs them through the chain.
2. **No refusal goes through the chain.** Every run here is one no block refuses, and the three refusal registers are required 0 after it. What the chain does when the injector ends a run on a refusal, or the source refuses a start, is each block's own bench's and is not held here. `one_bus_three_blocks` latches one refusal in each block, REGISTER_ACCESS, with nothing running.
3. **The frames at the two joints are never read.** The bench holds the score words they lead to. A fault at a joint that the core's configuration is blind to is not seen. In E0's shape the filter's last coefficient is zero, so a fault in a frame shows a record later than it happened. In the hand-over's training period a frame is held by one weighted sum of its channels: two faults in one frame that cancel in that sum pass.
4. **The table, the schedule and the blob loaded into the design are the ones the model is run on.** One wrong in both alike is seen by nothing here. The table is the model's own, handed over as source.md says; a host that hands over another is source.md's limit 2.
5. **The model's side of a swap is the bench's composition, not `model/run.py`.** It is held to `run.py` only where nothing is swapped. And the model makes its two calls before frame 0 where the chain makes them while the stream runs: what makes those the same is `model.weights.Store`'s rule, read, and the bench's two checks that the commit was taken before its index.
6. **A swap is made at one index in each stream.** A commit that lands at the edge of its own frame is the core's own bench's (`bit_identity_swap_on_the_edge`); the chain does not try it. A second swap in one stream, and a swap back, are not tried through the chain.
7. **The evidence of `swap-a-frame-late` and of `swap-does-not-happen` is the same line**: record 40 with the old epoch. Nothing in the manifest shows the first swaps at 41. What stands for it is the hand-tried early swap, written the same way, which the evidence puts at record 39.
8. **The clocks are held for one stream of 96 frames under each profile, with one schedule.** That the latency does not move with the truth is source.md's claim for the injector alone; here a pulse is on that stream from its first frame.
9. **A mutant shows the bench sees its fault under one sample format.** Fourteen of the fifteen were also tried once under the other, by hand; `hand-over-a-frame-late` was not.
10. **`truth_isolation` shows four wordings.** A path from truth to the core that none of those four moves is not seen: the planted one is moved by exactly one of them, the third.
11. **The core is at this top's maxima, not the definition's.** A fault of the chain that needs a wider core is not seen. The full top's own bench is `bench_core_max`.
12. **One bus, no kernel.** Nothing here is an AXI4-Lite face, and nothing arbitrates two writers: the bench is the only one.
13. **A record put out before a run's start write or after its collector's settle is seen by a count**, which says how many and not what.
14. **The hand-over's blob is held to the trainer outside the image, and the bench is held to the model inside it; nothing holds the two in one run.** A vector changed together with its test passes both. And the hand-over is run for one count, sixteen, one seed and one schedule under each profile.
15. **The cause of what Icarus did with an expression in a port connection is not known** (section 5). The shipped top has no expression in a port connection.
16. **No mutant in the manifest is a fault of count.** Three were tried by hand (section 4); the gate does not hold that this bench sees a record too many or too few.
17. **Nothing is synthesised**, and one simulator, Icarus Verilog 12.0.

## 8. Register

"The stage on a copy" is `python tools/check_rtl.py rtl-benches --root <a copy> --state <a folder>`, where the copy is this tree's `spec`, `model`, `learn`, `rtl`, `tools`, `docker` and `vectors` with a manifest cut down as the row says. The copies and their outputs are in the round's folder, `scratch/SEAM-2`, which is not in the tree: a row that rests on one cannot be rerun from a clone as it stands, and says what in the tree stands for it.

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| K1 | The streams are 96, 420, 150, four of 140, two of 150 and one of 2,180 frames under each profile: 3,706 frames a profile | READ | `rtl/tb/bench_seam.py`, its sizes; `vectors/seam-2/handover.json`, `frames`; 96 + 420 + 150 + 560 + 300 + 2,180 | those files |
| K2 | The chain simulated 35,997.90 ns a second under `s16x1` and 36,807.47 under `s24x3`: about 3,600 and 3,680 clocks a second at 10 ns a clock, and about 180 and 61 frames a second at a frame every 20 and 60 clocks | MEASURED | the stage on a copy whose manifest held the two rows and no mutant, 2026-11-23 18:15: the last line of cocotb's summary in each run's log. One reading, on a shared desktop, of the bench before the hand-over was added | the same line of any run's log; another load |
| K3 | Record k is expected 1 + 20 x CHANNELS x (k + 1) + 52 + 11 clocks after the edge that takes the start write | COMPUTED | source.md, row S5 and section 1; row S7; core.md, section 4 | `the_chains_clocks` failing |
| K4 | Every one of the first stream's 96 records is seen at that clock, under both profiles | MEASURED | the gate's second size: `the_chains_clocks` passing in the runs `seam-s16x1.s16x1` and `seam-s24x3.s24x3` | that test |
| K5 | The top, the helper and the bench passed at their first run: 18 tests in 2 runs, 3,052 records identical to the model's | MEASURED | the stage on that copy of K2, 18:15:10 to 18:15:54: "OK rtl-benches: 18 test(s) passed in 2 run(s) of 2 bench(es); 3052 record(s) identical to the model's, word for word; 0 mutant run(s) each failed as named". The bench then had nine tests and no hand-over | the round's ledger, `SEAM-2.md`, entry 18:18 |
| K6 | With the hand-over and fifteen mutants the two rows are 20 tests in 2 runs, 7,412 records and 15 mutant runs, and took 173 s; the hand-over's test took 16.11 s and 44.56 s of it, and the chain simulated 28,918.64 and 30,619.41 ns a second in that run | MEASURED | the stage on a copy whose manifest held the two rows alone, 2026-11-23 18:34:45 to 18:37:38: "OK rtl-benches: 20 test(s) passed in 2 run(s) of 2 bench(es); 7412 record(s) identical to the model's, word for word; 15 mutant run(s) each failed as named"; the time from the first build log to the runner's last file under `<the folder>/out`; cocotb's summary in each run's log. One reading, on a shared desktop, slower than K2's by about a fifth and a sixth | the gate's second size, whose line for the whole stage holds these and the other rows' |
| K7 | Each of the fifteen mutants failed the test named for it at the record and field section 4's table gives | MEASURED | the first fourteen: the stage on a copy with the two rows and the hand-tried rows, 18:29 to 18:34, each run's evidence file read line by line. The fifteenth: the copy of K6, the same way | the gate's second size: each fails as named there; the place is in each run's evidence file under `verify/state/<run>/` |
| K8 | Seventeen faults tried by hand each failed the test named for them: the first fourteen mutants under the other profile, a register on both valid and data at each joint, and a swap a frame early | MEASURED | that copy of K7's first half: its rows `seamx-s16x1` and `seamx-s24x3`, nine and eight mutants, none among the findings; each one's evidence read. The rows are `scratch/SEAM-2/extra.toml` | the manifest's own mutants, for the fourteen; nothing in the tree, for the three |
| K9 | Four faults that should pass did, on nine test runs: valid late at joint two on three tests and at joint one on one, the lost high bit on three, truth on the core's side on two | MEASURED | the same copy, the row `seamy-s16x1`: the judge's nine findings were exactly "MUTANT-SURVIVED" for those nine, and it printed no other | nothing in the tree: a mutant's run in the gate holds only the tests it must fail |
| K10 | A wait with no bound held the stage from 18:18:34 until the lead stopped the container at 18:23; with a bound the same mutant failed in under a second: "after 388 clocks the design has put out 0 record(s) of this test, not 12" | MEASURED | the stage on two copies, 18:18 and 18:24: the mutant run's log, its last line and its time; the lead's message for the stop. 3,000 is `tools/check_rtl.py`, the limit of its one container call | the round's ledger, `SEAM-2.md`, entry 18:30 |
| K11 | Under Icarus Verilog 12.0 a port connection written as `reg_valid && !(reg_we && reg_addr == REG_COMMIT_AT_OFFSET + 4)` dropped the core's every write; with `12'd252` it dropped the commit alone; as an assign with the comparison bracketed it dropped the commit alone; and a port connection of `(reg_we && reg_addr == REG_COMMIT_AT_OFFSET) ? reg_wdata + 1 : reg_wdata` added nothing | MEASURED | the stage on a copy with one row and seven mutants, 18:26:43 to 18:27:16: the findings for `d7` ("after its load the core does not say it is running", every status bit 0) and `d6` (MUTANT-SURVIVED), and the evidence of `d2` and `d3` (record 40, the old epoch). The seven are `scratch/SEAM-2/diag.toml` | nothing in the tree: the manifest's mutants are written the way that worked |
| K12 | The simulation image's pip list has no numpy, and `learn/trainer.py` imports it | READ | `docker/requirements-sim.txt`, seven packages; `learn/trainer.py`, its imports | those files |
| K13 | The hand-over: 2,180 frames, a training period of 2,050 with sixteen truth records from index 65 every 128, the hand-over at 2,072, one more record at 2,112; the blob is 324 bytes under `s16x1` and 836 under `s24x3`. Sixteen is the first of stage E1's six counts | READ | `vectors/seam-2/handover.json`; the two lengths are half the hex strings'; `tests/test_lrn_a_e1.py`, `COUNTS` | `python -m pytest tests/test_seam2_handover.py`, which makes the blob again |
| K14 | The frozen blob is the trainer's on the model's frames, and labels a frame off give another | MEASURED | `python -m pytest -q tests/test_seam2_handover.py`, 2026-11-23: 11 passed | that command |
| K15 | Three faults of count each gave a COUNT mismatch on the first stream: 97 records where the model has 96, 95 where it has 96, and 90 where it has 96 | MEASURED | the stage on a copy with the row `seam-s16x1` and those three mutants, 18:39:13 to 18:39:51: "3 mutant run(s) each failed as named", and each run's evidence line. The three are `scratch/SEAM-2/count.toml` | nothing in the tree: no mutant of the manifest is a fault of count |
| K16 | With these two rows on the base of 11 benches and 66 mutants, the stage passes 166 tests in 14 runs of 13 benches, holds 57,376 words identical to the model's and sees 88 mutant runs fail as named, in 350 s; the gate's second size took 10 minutes 4 seconds | MEASURED | `bash verify/run.sh --with rtl`, one run alone, 2026-11-23 18:40:29 to 18:50:33 by `date` before and after, on a shared desktop: its line for `rtl-benches`, and one verdict line, "== VERDICT: PASS" | that command; another load |

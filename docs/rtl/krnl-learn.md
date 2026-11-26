# The learner in the kernel

Parcel KRNL-L, round 5, 2026-11-26. Round 5's learner, `rtl/learn/learn.sv` and `rtl/learn/learn_port.sv` ([learn.md](learn.md)), wired into the Vitis kernel `rtl/krnl/undertone_krnl.sv` ([krnl.md](krnl.md)), so that one link puts learning in the fabric on the card. The packaged top is held to the reference model word for word, **in simulation only**, under both sample formats, driven through its AXI4-Lite port and its memory alone. The design was ruled by the lead on 2026-11-26 (the round's ledger, `lead.md`, entry 03:58). How the RTL side works at all is [README.md](README.md).

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure here has a row in the register at the end.

**What rests on what.** Everything here is bit identity: the kernel's score records in memory and the learner's registers read through the port, against `model.run.learning`'s on the streams the bench runs. **Nothing here is evidence about sensitivity**, which has its own authority, `stats/`. Nothing here is synthesised or linked; what the link must show is section 7.

## 1. Where things are

| what | where |
|---|---|
| the core's read-only view ports, and the injector's | `rtl/core/core.sv`, `rtl/inject/inject.sv`: the port lists' ends, and an `assign` block before each `endmodule` |
| the wiring: the learner, the shared port, the read OR | `rtl/krnl/undertone_krnl.sv` |
| the bench, on the packaged top | `rtl/tb/bench_krnl_learn.py`, with `rtl/tb/krnl_learn_host.py` |
| its rows and 12 mutants | `rtl/tb/benches.toml`: `krnl-learn-s16x1` and `krnl-learn-s24x3`, at the end |
| the packaging's sources and their test | `hw/package_kernel.tcl`; `tests/test_krnl_packaging.py` |

## 2. The view ports of core.sv and inject.sv

`learn.sv` needs the core's state and the injector's truth. The simulation tops `learn_small.sv` and `learn_chain.sv` read them by hierarchical name (learn.md, limit 3), and still do. The kernel reads them through ports:

- **`core.sv`, 15 output ports:** `view_running`, `view_next_index`, `view_taps`, `view_filters`, `view_rows`, `view_pool`, `view_score_shift`, `view_rect_abs`, `view_no_hidden`, `view_commit`, `view_commit_at`, `view_partial`, `view_active_sel`, and `view_vld` and `view_tag_sel`, the valid bits and the tags' bank selects of every stage of the pipeline, 1 to 10. The kernel works `closed` from stages 1 to 7 of them, core.sv's `ST_S1` to `ST_CLOSED_LAST`, as the core's own status read works it.
- **`inject.sv`, 2 output ports:** `view_push`, the record taken into the store at this edge (`wr_push`), and `view_index`, its index (`t_index`). Nothing else of a record.

**Each port is an existing signal and nothing more.** Each is driven by one continuous `assign` (one generate loop for the tag selects), and nothing inside either block reads a port. The ports are written with a leading comma after the last port, so no existing line of either file changes: the two files gain 39 and 7 lines and lose none (row KL1). A top that leaves the ports unconnected builds the same design. Every earlier bench of the core, the injector, the seam, the flag, the learner and the kernel passes unchanged in the gate's second size.

Three lines added to `inject.sv`'s port list move the line `rtl/tb/build_lines.toml` names there from 276 to 279. The list moves with it, and so does the one line of `tests/test_p0_rtl_gate.py` that holds the list, each by the lead's word.

## 3. The kernel's wiring

The packaged top's header, its parameter list and its port list, does not change: the rule of plain numbers there (krnl.md, section 7) needs nothing new. In the body:

- **`learn`** is built at the kernel's `B_TAPS` (128 in the packaged top), at `LEARN_COUNT_BITS` (32) and `LEARN_UPDATE_FRAMES` (256) from the package. `krnl_small.sv` and `krnl_max.sv` build theirs at their own `B_TAPS`, 64 and 128.
- **Its frames** are the core's own wires, `inj_valid` and `core_frame`. **Its truth** is the injector's `view_push` and `view_index`: the index of each record the injector takes, and nothing else. **The core's state** comes through the 15 views.
- **Its reset** is the chain's, `chain_rst`: `ap_rst_n` or a write of `krn_reset`. The kernel now resets four blocks.
- **The core's register port is learn_port's.** `learn_port` is handed what the kernel already routes to the core (`core_valid`: every read, and writes inside the core's range). It passes every host access but one held back, and in a clock with no host access to the core it carries the learner's write. While an update is unfinished, the host's commit (`commit_at`'s upper word), `shadow_begin` and `shadow_data` are held back: they reach no block, and the learner latches UPDATE_UNFINISHED (learn.md, section 2.1). A host write to the source, the injector or the learner does not take the core's port.
- **The learner's own port** sees every read, and writes inside its own block or the core's: `bus_valid && (!bus_we || hit_learner || hit_core)`. It needs the core's range to count a commit it held back (`lrn_early`). So **the injector's truth rows never reach the learner's port**, as round 3 keeps them from the core's (the lead's ruling, Q3).
- **The read path's OR** holds the learner's `reg_rdata`: `src_rdata | inj_rdata | core_rdata | learn_rdata`. Each is a register set at the edge that takes the read, and 0 outside its block.

**What answers at 0xD00 to 0xDFF now:** the learner's rows, learn.md section 3. `lrn_update_at`, `lrn_status`, `lrn_refusal`, the two counts, the six 64-bit counters (a read of a lower word holds its upper), `lrn_cap_count_bits` reading 32 and `lrn_cap_update_frames` reading 256; every other offset there reads 0. A write there is forwarded on the bus, as since round 3, and is now the learner's: an update's two words and a clear of `lrn_refusal` are taken, and any other write latches REGISTER_ACCESS in `lrn_refusal`. Until now the kernel sent it to no block (learn.md row L9, restated there).

**The kernel's refusals and the learner's are apart:**
- a write the kernel refuses for itself (strobes not all four, below 0x10, `src_frames`, its own block) is not forwarded, so it never reaches the learner;
- a learner's refusal is latched in `lrn_refusal` alone. It sets no bit of `krn_status`, latches nothing in `krn_refusal` and ends no run: the learner is not in the records' path, and done and RUN_LENGTH are as before;
- a host write held back is answered OKAY, like every operation; its name is in `lrn_refusal`, and the core's refusal reads 0 for it.

## 4. The bench

`bench_krnl_learn.py` runs on `undertone_krnl` itself at its defaults, under each profile. The kernel is driven only as a host drives it: cocotbext-axi's AxiLiteMaster on `s_axi_control`, `krnl_mem.Memory` on `m_axi_gmem`, and no signal inside the top read.

**An operation and its window** (`krnl_learn_host.py`). A host cannot put a write at a chosen clock, so each operation of a script has a window of next indexes inside which the model's outcome, its records and its counters are the same, and the model's script names it at one index in that window. The bench reads the core's `next_index` through the port until it is at the window's first index, makes the operation, and reads `next_index` again. The writes landed between the two reads, so the second read at most the window's last is what makes the comparison sound. An operation outside its window fails the test by name. After each operation `lrn_refusal` and the core's `refusal` are read, held to the model's outcome as `learn_host.expected_codes` gives it, and cleared, and `krn_status`'s refused bit is held to 0.

| test | what it holds |
|---|---|
| `learning_on_the_kernel` | at the build's 128 taps: a prelude run, then `krn_reset`, then the main run (below). Each run held whole: every slot in memory and every beat as written against the model's records, the memory's checks, `krn_records` = `krn_frames`, no refusal of the kernel's, the core's, the source's or the injector's, `krn_status`'s refused bit 0 at done, each operation's refusals, and at the end the eight counts and `lrn_status` against the model's learner |
| `learner_rows_through_the_port` | the 64 words of [0xD00, 0xE00) at reset against the model's learner and the definition's two capabilities; a write to a read-only row latched in `lrn_refusal` and not in `krn_refusal`, `refusal` or `krn_status`; a two-byte write refused by the kernel and reaching no block; `krn_reset` clearing the learner; an update with the core stopped, CORE_STOPPED |
| `refusals_through_the_views` | each after `krn_reset`, the core loaded and running, an update of 1,000 named: under each one-field departure from the matched shape at 2 taps (2 filters, a pool of 2, a score shift of 1, the abs rectifier, one hidden unit; under s24x3 also one filter over two of three channels, and two filters over three rows) SWAP_SHAPE, the model's; with a commit scheduled SWAP_PENDING, the model's; with a stream begun WEIGHT_COUNT, the fabric's own (learn.md, section 3); under the matched shape alone taken, `lrn_update_at` reading 1,000 |

**The prelude** (300 frames, one record at 150, an update named for 290) ends with that update unfinished, a window taken in each label and REGISTER_ACCESS latched in `lrn_refusal`. That run is held whole, and it ends done with `krn_status`'s refused bit 0. Then `krn_reset`, and the main run is held against a learner made new: any count, cursor, update or latch that survived the reset would show in its set, its refusals or its counts. The prelude's register checks are raised only after the main run's records are held, so a fault that reaches the main run's records is reported as the harness's mismatch there.

**The main run**, 1,080 frames, its four truth records worked by hand at T = 128 (row KL3):

| record | amplitude | label 0, frames j − 128 to j − 1 | label 1, frames j to j + 127 |
|---|---|---|---|
| 64 | 3/1 | START | taken |
| 384 | 0/1 | taken | taken |
| 640 | 3/1 | taken, at exactly 2T after 384 | BUSY |
| 720 | 5/2 | BUSY | BUSY |

So two windows a label, one START and three BUSY. The core starts on `learn_host.start_blob` (each channel's newest tap c + 2, the rest 0), so every record before the commit is its frame's own weighted sum. The operations and their windows:

| model's index | operation | window | the model's outcome |
|---|---|---|---|
| 10 | update(760) | 10 to 759 | taken |
| 770 | commit(1030) | 770 to 1015 | UPDATE_UNFINISHED, `lrn_early` 1 |
| 780 | write_shadow(another set) | 780 to 1015 | UPDATE_UNFINISHED, each of its writes |
| 1020 | commit(1040) | 1016 to 1038 | taken: the update finished at 760 + 256 = 1016 |

**Held of the model before the design runs,** so the stream cannot hide what the mutants plant: the four outcomes above; the counts above, and the update's counts (2, 2); the learned set is not the start set; the same run with only the last commit first differs at record 1040; and a learner handed the truth without record 384 learns another set.

## 5. The mutants, and where each one's evidence fell

12 mutants: 11 on `krnl-learn-s16x1` and 1 on `krnl-learn-s24x3`. Each was read against the record or register word its fault predicts, in the run of row KL4. "Word n" of the two short tests is the n-th word they read (from 0): words 0 to 63 are the learner's block, and the rest are listed in the bench in order. Each failure but the last row's is a WORD mismatch from the harness.

| mutant | the fault | where its evidence fell |
|---|---|---|
| `learner-word-not-read` | the learner's `reg_rdata` out of the read OR | rows, word 18 (`lrn_cap_count_bits`): 0 where 32 |
| `truth-not-to-the-learner` | `truth_valid` tied 0 | record 1040: score 12, the start set's, where the model's is 1,729,807 |
| `learner-fed-the-source-frames` | the learner fed the frames the injector takes in (`src_valid`, `src_frame`) | record 1040: score 2,240,100 |
| `learn-port-bypassed` | the core's register port back to round 3's: the host's commit taken while the update is unfinished | record 1030: epoch 4 where the model's is 3 |
| `taps-view-from-rows` | core.sv: `view_taps` from `cfg_rows` | record 1040: score 12 |
| `reads-the-amplitude` | a record of numerator 0 not handed to the learner | record 1040: score 1,736,658 |
| `learner-not-reset-by-krn-reset` | the learner's reset from `ap_rst_n` alone | rows, word 73 (`lrn_refusal` after `krn_reset`): 42, REGISTER_ACCESS, where 0 |
| `learner-built-at-64-taps` | the learner at `B_TAPS` 64 beside a core of 128 | record 1040: epoch 3 where 4, score 12: the update never finishes and the last commit is held back |
| `pool-view-from-filters` | core.sv: `view_pool` from `cfg_filters` | views, word 4 (the pool of 2): 0 where 19, SWAP_SHAPE |
| `learner-refusal-in-krn-status` | the learner's latch ORed into `krn_status`'s refused bit | rows, word 68 (`krn_status`): 4 where 0 |
| `filters-view-one` (s24x3) | core.sv: `view_filters` read as 1 | views, word 18 (two filters over three rows): 0 where 19 |
| `stages-renumbered` | core.sv: `ST_CLOSED_LAST` made `ST_H2`, 8 | no record: the kernel's simulation-only guard stopped the run at time 0, "undertone_krnl: core.sv's stages that read weights at a later edge are not 1 to 7, as v_closed takes them" |

The brief's list is the first six. **No mutant reads the pulse id:** the fabric's injector holds e0 alone, so a learner reading the id reads a constant (learn.md, limit 9). **Round 3's `truth-reaches-the-core`** on `krnl-small-s16x1` still fails at record 1 of the first wording, score 1,890 where the model has 2,160, as krnl.md's table says.

**Tried by hand, on a copy, and not in the manifest** (row KL7). Twenty more faults, nineteen under s16x1 and one under s24x3:

| fault | what it showed |
|---|---|
| the learner blind to the core's range | `lrn_early` 0 where the model has 1, at the end (a register check, no WORD) |
| the learner blind to its own block | rows, word 64 (`lrn_refusal` after a write to `lrn_status`): 0 where 42 |
| the learner deaf to reads | rows, word 18: 0 where 32 |
| learn_port handed every host write, not the core's alone | **passed** (limit 6) |
| `view_partial` tied 0; `view_commit` tied 0 | views, words 14 and 12: 0 where WEIGHT_COUNT and SWAP_PENDING |
| `view_running` tied 1 | rows, word 76: SWAP_SHAPE where CORE_STOPPED |
| `view_rect_abs` tied 0; `view_no_hidden` tied 1; `view_score_shift` tied 0 | views, words 8, 10 and 6: 0 where SWAP_SHAPE |
| `view_next_index` from `commit_at` | record 1040: epoch 3 where 4 |
| `view_index` one more; `view_push` tied 0 | record 1040: score 15,807, and 12 |
| `view_rows` read as 3, under s24x3 | views, word 16 (one filter over two channels): 0 where SWAP_SHAPE |
| `view_rows` read as 1, under s16x1 | **passed**: under one channel the filters' departure is also the rows' (limit 5) |
| the learner's port on every write, unfiltered | **passed** (limit 6) |
| `closed` tied 0; every tag select from stage 1 | **passed** (limit 4) |
| `view_commit_at` from `next_index` | **passed** (limit 4) |
| learn_port's `take` from the source's valid | **passed** (limit 1) |

## 6. Run time

On a copy holding only these two rows, the stage passed 6 tests in 2 runs, 5,520 records identical to the model's, and 12 mutant runs each failed as named. Its 14 runs took 216 s summed, six at a time, in 72 s of wall time. The longest was the s24x3 run, 41 s; each mutant run on `learning_on_the_kernel` took 19 to 24 s, and each on a short test 2 to 3 s (row KL4). An earlier run of the same rows, with 11 mutants, took 155 s summed (row KL4): the desktop's other load moves these times.

The learner is in every kernel build now, so the five earlier rows that build the kernel simulate it too. Without `host-first`, their 30 runs took 137 s summed on a copy, against 120 s in the lead's second size of 00:16. `host-first`'s two runs took 11 and 23 s, against 12 and 24 (row KL6). The loads of the two runs differ, so this is a reading, not a measurement of the learner's cost alone.

## 7. What the link must show, which a simulation cannot

The lead's estimate of the learner alone out of context at 10 ns found WNS +5.747 ns (the round's ledger, `lead.md`, 03:48). Its worst paths ran from the truth store's cursor `t1_reg` into `db_p0`'s DSP inputs, 20 logic levels. It timed no path into or out of the learner. In the link's routed timing of the kernel's clock (DATA_CLK, CLAUDE.md trap 20), look for:

1. those 20-level paths, routed, `u_learn/t1_reg` to `u_learn/db_p0`;
2. **the paths from the core's views into the learner, never timed.** `u_core/next_index_reg`, `commit_at_reg`, the `cfg_*` registers, `vld`, `tg` and `active_sel` into `u_learn`: the 64-bit add and compares of a window's judgement, of an update's make and of its index check, `closed`'s seven compares, and the shape check;
3. **the paths through learn_port into the core's register port.** From `u_learn/hold_q_reg`, `hold_end_q_reg` and the `lw_*` registers, the kernel's `bus_*` registers and the take (`inj_valid`, the core's running bit), through a few LUTs, into `u_core`'s write decode and the weight banks' write enables. The core's register checks were a 26-level path at 200 MHz (krnl.md, row K30) and met at 100 MHz. That the mux adds about two or three levels in front, and now drives that fanout from a LUT, is BELIEVED;
4. **the utilisation**, `u_learn` against SYN-learn.md's s16x1 row (19,070 LUTs, 3,814 of them memory; 26,571 registers; 12 DSP slices; no block RAM), and the kernel's total against its 329,499 LUTs of round 3.

Only s16x1 is linked; s24x3's learner is the larger (SYN-learn.md) and is not the card's.

## 8. Limits

Each is stated by the behaviour it concedes.

1. **F to the clock is not held on the kernel.** An AXI4-Lite write cannot be put at a chosen edge, so the boundary at the clock (a commit refused at the last clock of u + F − 1, taken at the first of u + F) is held on `learn_chain` alone (learn.md, `update_finishes_within_f`). The kernel holds a commit refused while the update is unfinished and one taken in the 23 frames from u + F. learn_port's `take` taken from the source's valid passed every test here (section 5).
2. **Each operation is held inside its window,** where the model's outcome is the same. A fault that changes an outcome only at a window's edge is not seen here.
3. **FULL is not reached on the kernel.** Its count bits are 32, and no state can be written through the port. FULL at 32 bits is held on `learn_chain` from a written state (learn.md, limit 7). No counter here passes 2^32.
4. **`closed` and the commit's index are not seen on the kernel.** `closed` needs a frame of the old bank in stages 1 to 7 at a swap, and the kernel's source gives a frame every 20 clocks under s16x1 and 60 under s24x3, so at the kernel's rate it is never true (row KL8). `view_commit_at` is read only when a frame swaps at the edge an update is named. `closed` tied 0, the tag selects all taken from stage 1, and `view_commit_at` from `next_index` each passed every test here.
5. **A shape view is held only where one departure tells it apart.** Under s16x1 two filters are two rows, so the filters' view and the rows' are told apart under s24x3 alone (learn.md, limit 11). `view_rows` read as 1 passed under s16x1.
6. **Whether the injector's truth rows reach the learner's port is not observable.** The learner decodes its own block and the core's commit row and nothing else, so a kernel that handed it every write passes everything here, as krnl.md's limit 22 says of the core. That they do not reach it rests on the RTL's reading (`learn_valid` in `undertone_krnl.sv`). Likewise learn_port handed every host write, not the core's alone, passes: the core decodes its own range, and the learner's write then waits while a host write to another block holds the core's port.
7. **The pulse id has no mutant:** one pulse (learn.md, limit 9).
8. **A reset in behaviour, not in storage.** `krn_reset` clears every register of the learner: the sums and their copy, the counts, the six counters and their holds, `lrn_update_at`, the update, the latch, the engine. Of the delay buffer and the truth store it clears the pointers and not the contents, since no line of `learn.sv` changes. No stale entry is ever read: a truth entry is read only between the label-1 cursor and the write pointer, and a window reads the delay buffer only over the T frames taken since the reset, the core's next index restarting at 0 with the buffer's pointer. That is BELIEVED by reading, and the prelude holds it on one stream.
9. **The stages `closed` is worked over are retyped.** `view_vld` and `view_tag_sel` are `[10:1]`, every stage of core.sv's pipeline, and the kernel works `closed` over stages 1 to 7, core.sv's `ST_S1` to `ST_CLOSED_LAST`, which are local parameters of the module's body and cannot be named in its port list. A core that renumbered those stages would make the kernel's `closed` differ from the core's own, and no bench would see that difference, since at the kernel's rate `closed` is never true (limit 4). What is seen is the renumbering itself: in simulation the kernel's guard (`ifndef SYNTHESIS`) stops the run by name when `u_core.ST_S1` is not 1 or `u_core.ST_CLOSED_LAST` is not 7 (the mutant `stages-renumbered`). A synthesis carries no such guard. learn.md's limit 4 works `closed` from the same layout.
10. **A mutant runs under one profile.** Eleven run under s16x1 and one under s24x3; the tests run under both.
11. **One update in one run, and no run past 1,080 frames,** on the kernel. Two updates, a second set, and long runs are LRN-C's and the card's.
12. **One simulator,** Icarus Verilog 12.0. Nothing here is synthesised, placed or linked; nothing about sensitivity.

## 9. Register

"The stage on a copy" is `python tools/check_rtl.py rtl-benches --root <a copy> --state <a folder>`, the copy holding this tree's `spec`, `model`, `learn`, `rtl`, `tools`, `docker`, `vectors`, `stats` and `host` with a manifest cut down to the rows named. The copies are in the parcel's scratch folder, not in the tree.

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| KL1 | core.sv gains 39 lines and inject.sv 7, and neither loses one: 15 and 2 view ports | MEASURED | `git diff --numstat` of the two files against r5 at 8811791, 2026-11-26 04:16: `39 0` and `7 0` | that command at this parcel's commit |
| KL2 | The learner in the kernel is built at the kernel's B_TAPS, 128 in the packaged top, LEARN_COUNT_BITS 32 and LEARN_UPDATE_FRAMES 256; krnl_small's B_TAPS is 64 and krnl_max's 128 | READ | `rtl/krnl/undertone_krnl.sv`, the `learn` instance; `spec/constants.py`; `rtl/krnl/krnl_small.sv` and `krnl_max.sv` | those files |
| KL3 | At T = 128 the main run's four records give two windows a label, one START skip and three BUSY | COMPUTED | section 4's table, by learn.md section 2's rules; the bench requires the model's counters to equal them | `learning_on_the_kernel`'s model assertion |
| KL4 | On a copy of these two rows the stage passed 6 tests in 2 runs, 5,520 records identical to the model's, and 12 mutant runs each failed as named, the evidence of each as section 5's first table says; 14 runs, 216 s summed, six at a time, 72 s of wall time; the s24x3 run 41 s, each mutant on `learning_on_the_kernel` 19 to 24 s, each on a short test 2 to 3 s. An earlier run with 11 mutants took 13 runs and 155 s summed | MEASURED | the stage on a copy, 2026-11-26 04:41:05 to 04:42:17: its OK line, the runner's "ran" lines, and each mutant run's log read for its mismatch or its FATAL; the earlier, 04:16:52 to 04:17:45, its "ran" lines | the gate's line for `rtl-benches` and its evidence under `verify/state/<run>/` |
| KL5 | The five earlier rows that build the kernel pass with the learner inside it, every mutant of theirs failing as named, `truth-reaches-the-core` at record 1, score 1,890 where 2,160; and the core's two rows pass with the view ports, every mutant failing as named, RTL-B's two that renumber `ST_CLOSED_LAST` among them | MEASURED | the stage on copies: the five rows 2026-11-26 04:11:21 to 04:12:00 (host-first's two runs left no results there, the copy lacking `host/`) and `host-first` alone, 04:12:16 to 04:12:41, on the views of stages 1 to 7; after the views took every stage, `core-s16x1` and `core-s24x3` with this parcel's rows, 04:36:36 to 04:38:08, 50 mutant runs, and `krnl-first` and both `krnl-small` rows with this parcel's, 04:38:56 to 04:40:36 | the gate's second size |
| KL6 | Without host-first, those rows' 30 runs took 137 s summed on a copy, against 120 s in the lead's second size of 00:16; host-first's took 11 and 23 s, against 12 and 24 | MEASURED | the two copies of KL5: their runner logs' "ran" lines, added; the lead's run 20261126-001647-1107812, its `rtl-benches/runner.log` | another run; another load |
| KL7 | Twenty faults tried by hand showed what section 5's second table says: thirteen failed where it says, and seven passed | MEASURED | the stage on a copy with extra rows holding those faults, on the views of every stage, 2026-11-26 04:42:39 to 04:44:03: nineteen findings MUTANT-SURVIVED, a finding for each test of the seven that passed, and each other mutant run's log read. The same twenty showed the same at 04:14:05 and 04:21:32, on the views of stages 1 to 7 | nothing in the tree: these faults are not in the manifest |
| KL8 | At the kernel's rate `closed` is never true: a frame of the old bank would have to be in stages 1 to 7 at a swap, and frames come 20 clocks apart under s16x1 and 60 under s24x3 | COMPUTED | core.sv: every stage's valid and tag move one stage at every clock, and the frame taken at a swap carries the new bank; `seam_host.period`, source.md row S5 | a stream of the kernel whose `closed` is 1 at some edge |
| KL9 | The learner's estimate alone: WNS +5.747 ns at 10 ns, its worst paths 20 logic levels from `t1_reg` into `db_p0`'s DSP inputs; no path into or out of it timed | READ | the round's ledger, `lead.md`, entry 03:48, the lead's run on the box | the link's routed timing |
| KL10 | In round 3's third link the core's register checks were a 26-level path at 200 MHz and met at 100 MHz; the kernel's synthesis took 329,499 LUTs | READ | krnl.md, rows K29 and K30 | those reports |
| KL11 | learn_port in front of the core's register port adds about two or three logic levels and drives the core's write fanout from a LUT | BELIEVED | this parcel's reading of `learn_port.sv`: a mux of the host's access and the learner's write, and the held-back condition | the link's timing report |
| KL12 | The learner under s16x1 synthesised alone: 19,070 LUTs, 3,814 of them memory, 26,571 registers, 12 DSP slices, no block RAM | READ | `docs/studies/SYN-learn.md` | that page's reports |
| KL13 | The learner's port sees reads, and writes to its own block or the core's | DECISION | the lead's ruling, the round's ledger, `lead.md`, 03:58, Q3 | the RTL, `learn_valid` |

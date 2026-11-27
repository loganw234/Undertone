# The pool's read, registered on its own: the core's pool for UltraRAM

Written by parcel POOLRAM in round 5, 2026-11-26, on Logan's word of that evening to balance the build's resources for the builds to come. Labels are those of [the design](../studies/D0-rough-design.md): MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure on this page is in the register at the end. The core itself is [core.md](core.md); the kernel and its links are [krnl.md](krnl.md).

**What a pass here is evidence of:** that with the pool's read restructured, the core's score records equal the model's on every stream the benches run, and that the value the pool drops, `s4_old`, is what the replaced line's register held, at every clock of this page's streams. It is not evidence that Vivado makes UltraRAM of it, nor that the build meets its clock: the benches meet no synthesis tool. The lead's synthesis of the core alone did make UltraRAM of it, with a timing estimate before placement that meets 100 MHz (section 6); no link of it is made yet. It is not evidence about sensitivity.

## 1. Why

- The kernel's synthesis in round 3 took 329,499 LUTs, 196,089 of them as memory, and no UltraRAM (P15).
- Round 5's image of 9bf71d7 holds 205,206 LUTs as distributed RAM, 76,666 in SLR0 and 128,540 in SLR1, beside 4 of the part's 640 UltraRAM blocks and 239.5 of its 1,344 block RAM tiles (P2). Its SLR1, where the placer put the kernel, used 96.74% of the slices that can be memory (P15).
- The pool's memory is 65,536 words of 164 bits, 10,747,904 bits (P1); in distributed RAM about 192,512 LUTs (P3). So it is most of that memory.
- Both of the links that closed at 100 MHz had their worst path on the kernel's clock from the write pointer, `pool_wp`, to the distributed RAM (P15).

## 2. Where things are

| what | where |
|---|---|
| the core, its pool's read | `rtl/core/core.sv`, `pool_q` and the block `st4_pool` |
| the bench | `rtl/tb/bench_poolram.py` |
| its rows and mutants | `rtl/tb/benches.toml`, the rows `poolram-s16x1` and `poolram-s24x3` at the end; `pool-no-forwarding` in `core-s16x1`, re-expressed in place |
| the text the synthesis was run on, held | `tests/test_poolram_text.py`, in the gate's first size |

## 3. The change

**Why the memory was distributed RAM.** Vivado's own language templates for UltraRAM and for block RAM read the memory into a register of their own, under an enable, with nothing between the memory's word and that register (P7). The old line put a multiplexer there:

    s4_old  <= (vld[ST_S4] && (pool_wp == pool_rp)) ? s4_rect : pool_mem[pool_rp];

so `s4_old` could not be the memory's own register, and the read before it was asynchronous, which only distributed RAM gives. That a registered read address could not stand in for it, because `pool_rp` is reset and has other loads, is BELIEVED. What Vivado itself said is in the kernel's synthesis log on the box, which this page has not read.

**What replaces it.** `core.sv`'s pool read is now three registers and a choice:

    // in s4, at an edge with a frame from s3, after the reset branch
    fwd_sel <= vld[ST_S4] && (pool_wp == pool_rp);     // reset: 1
    fwd_val <= s4_rect;                                // reset: 0
    // its own block, st4_pool
    if (!rst && vld[ST_S3]) pool_q <= pool_mem[pool_rp];
    assign s4_old = fwd_sel ? fwd_val : pool_q;

`pool_q` is the memory's own output register: a latency of one, the old register's load condition as its enable, and no reset. The memory carries `(* ram_style = "ultra" *)`, which Icarus Verilog ignores. The write, `pool_mem[pool_wp] <= s4_rect;` in `s5`, did not move, and no other line of `core.sv` changed: `s4_old` keeps its declaration and becomes a net.

**Why `s4_old` is the old register's value at every edge.** At a rising edge, write c for `vld[ST_S4] && (pool_wp == pool_rp)`, R for `s4_rect` and M for `pool_mem[pool_rp]`, each as before the edge. The old register took 0 under `rst`, c ? R : M when a frame came from `s3`, and held otherwise. At the same edge the new registers give:
- under `rst`: `fwd_sel` 1 and `fwd_val` 0, so `s4_old` is 0;
- with a frame from `s3` and no `rst`: `fwd_sel` c, `fwd_val` R and `pool_q` M, so `s4_old` is c ? R : M;
- otherwise all three hold, and so does `s4_old`.

So after the first reset `s4_old` is the old register's value at every edge, unknown bits included. Nothing else in the design changed, so no other register, and no record, can differ. That is an argument (P8); the bench's second test holds it at every clock of its streams (P10).

- **The collision.** At an edge that reads for frame n with a frame at `s4`, that frame is n-1: `pool_rp` is n mod P and `pool_wp` is (n-1) mod P, since both count frames from one reset under one `cfg_pool`, and `vld` moves one stage a clock. They are equal only at a pool of 1, where the memory still holds frame n-2's word, and `fwd_sel` takes frame n-1's. So what the memory gives at a read and a write of one address cannot reach `s4_old`. The UltraRAM template's header says old data shows there (P7), as the RTL's read gives.
- **After a reset** `s4_old` is 0 until a frame reaches `s4`, as before, and nothing adds it before then. The memory keeps the words of the run before, and the pool's counter keeps them out until P frames have gone by, as before.
- **A change of `cfg_pool`** comes only with a reset: `configure` is taken only while the core is stopped, and reset is the only way there.

**Why no record can show two faults in these lines.** `s5` adds `s4_old` only at the edge after one that loaded it. So a wrong `s4_old` between frames, or before the first frame after a reset, reaches nothing the model defines. A read register that loads at every clock, and an `s4_old` that is not 0 after a reset, pass every record. The bench's second test is what sees them (section 5).

## 4. The memory chosen

UltraRAM, from Vivado 2022.2's own templates, copied by the lead from the box's licensed install for reading only (P7):

| the UltraRAM template | this code |
|---|---|
| `(* ram_style = "ultra" *)` on the memory's declaration | the same, on `pool_mem` |
| one clock for the write and the read | `clk` |
| a write under an enable | `pool_mem[pool_wp] <= s4_rect;`, under a frame at `s4` and no `rst` |
| a read into a register of its own under an enable, a latency of one | `pool_q <= pool_mem[pool_rp];` under `!rst && vld[ST_S3]` |
| no initial value, no reset of the memory or of that register | none |
| old data when the read and write addresses are equal | the RTL's read gives old data, and the forwarding makes the case moot |

**Where it differs from the template.** Each was BELIEVED, at the design, to be inside what Vivado infers. The lead's synthesis of this file made UltraRAM of it (section 6):
1. The template reads and writes in one block under one memory enable. Here the write is in `s5` and the read in `st4_pool`, each with its own enable. Block RAM's two-clock template reads and writes in separate blocks (P7).
2. The template has three pipeline registers after its read register; here there are none, so that no stage's timing moves. The cascade of blocks then has no register in it, and the read is one clock from the first block to `z_flat` (section 6).

**Its shape.** Two accounts of it, and the second is Vivado's:
- **by capacity**, 164 bits are three blocks wide and 65,536 words sixteen deep: 48 blocks (P4, COMPUTED);
- **as Vivado mapped it**, 48 URAM288 in a matrix its UltraRAM table gives as "8x2", under its "Default cascade height of 8" (P18, READ). Its worst path from the memory runs through eight blocks of one cascade (P19, READ).

That the 8x2 is two cascades of eight in each of three slices of the word's width, their outputs chosen in the fabric, is my reading of the table, BELIEVED (P21). It agrees with 48 = 8 x 2 x 3 and with the cascade of eight on the path. If the link shows that Vivado will not make UltraRAM of this code there, or that its read path does not meet 100 MHz, the fallback is the one word `"block"`, on the lead's word only: at least 292 RAMB36 by capacity (P5). Icarus Verilog ignores the attribute, so either word gives the same records.

## 5. The benches

**`bench_poolram.py`**, on `core_small`, a row for each profile. Its streams are the same for both tests, each after a reset, with the memory's first sixteen words written through the simulator with known words that no frame of the run writes, then a load (P16):

| # | stream | frames |
|---|---|---|
| 1 | a pool of 1, back to back: the collision at every frame from 1 | 12 |
| 2 | a pool of 1, with the harness's gaps of 0 to 2 | 16 |
| 3 | a pool of 2, back to back: a read and a write at one edge, at two slots | 12 |
| 4 | a pool of 2, with gaps | 16 |
| 5 | a pool of 3, back to back | 12 |
| 6 | a pool of 8, with gaps | 24 |
| 7 | a pool of 5, three frames back to back, a reset in the middle of its fill with the memory not written again, then fourteen frames with gaps | 3 and 14 |
| 8 | the second test only: a pool of 4, six frames back to back and a reset at the next clock, with three frames past `s4`; then ten frames | 6 and 10 |

**So that a fault cannot hide.** Four filters of one tap, coefficients 1 to 4, filter k on channel k modulo the profile's channels; pass; no shift; no hidden layer; every head weight 1. The score is then the sum of the four pooled sums. The samples are a ramp on every channel, rising by a step that differs by channel, from a base that differs by stream. Every filter's rectified value rises strictly from frame to frame, so a pool that drops any word but the right one moves all four sums the same way, and no error cancels. The words written into the memory first differ by slot and by filter and are larger than any rectified value, so a read of a word no frame wrote is a wrong word, not unknown bits. The gaps are the harness's own draws for a fixed seed: the bench replays them and asserts what each gapped stream holds, so no mutant's failure rests on a seed by luck.

**Two tests.**
- `bit_identity_pool_collisions`, an identity test: every record of streams 1 to 7 against the model, through `harness.compare`, with the whole test's records counted.
- `s4_old_at_every_edge`: the same frames and gaps without the model, and stream 8. At every falling edge from the first reset, a coroutine reads `s4_old` and the replaced line's inputs through the simulator, and works out in Python what that line's register would hold. Each stream's samples are held word by word against it with `harness.hold`. A sample is its value with its mask of unknown bits above it. Its expected words come from the old line, not from the code it judges. It reads seven of the core's signals and three of its stage numbers by name, so a renaming fails it when the handle is first looked up.

**The existing benches** that drive these cases, under both profiles: the collision in `bit_identity_swap_on_the_edge` case 0, `shadow_closes_and_opens` and `swap_epoch_on_the_edge`, back to back, and with gaps in `bit_identity_every_tap`, the pool-1 shapes of `bit_identity_swap` and the index streams of `bit_identity_counters`; pools of 2 and more back to back in `bit_identity_swap_on_the_edge` cases 1 and 2 and `commit_orders`; a change of `cfg_pool` between runs in `bit_identity_random`, `bit_identity_swap` and `bit_identity_swap_at_zero`. None resets in the middle of a pool's fill on purpose. Every bench whose sources hold `core.sv` was run on one copy of the tree before the gate ([core.md](core.md), C23). This bench's two rows and eight new mutants add 20 s of run time to the stage (P12).

**The mutants.** Each under one profile, as the core's are. Each was read against the record or the sample its fault predicts (P11): "stream 1, record 1" counts from 0, and "sample k" is the k-th falling edge of that stream's segment of the second test.

| mutant | profile | the fault | `bit_identity_pool_collisions` | `s4_old_at_every_edge` |
|---|---|---|---|---|
| `pool-no-forwarding`, row `core-s16x1`, re-expressed | s16x1 | the forwarding's flag never set by a frame | (not run) | (not run); `bit_identity_swap_on_the_edge` fails UNKNOWN-BITS at record 1 of case 0, as before: the memory there was never written |
| `forwarding-removed` | s16x1 | the same, on this bench | stream 1, record 1: score -34,359,729,868 where the model's is 4,600, the written word of slot 0 dropped | stream 1, sample 73, after the edge that loads frame 1: slot 0's written word where the register holds frame 0's value |
| `forwarding-one-frame-stale` | s16x1 | the forwarded word the one written a frame before | stream 1, record 1: 8,600 where 4,600, 0 dropped in place of frame 0's 4,000 | stream 1, sample 73: 0 where frame 0's value |
| `forwarding-without-the-pointers` | s16x1 | a frame at `s4` alone forwards | stream 3, record 2: 21,200 where 21,800, frame 1's value dropped in place of frame 0's | stream 3, sample 42, after the edge that loads frame 1: frame 0's value where slot 1's written word |
| `read-every-clock` | s16x1 | the read register's enable dropped | (passes, not named) | stream 2, sample 51, the second clock of a gap of 2 after frame 5: frame 5's value where the register holds frame 4's |
| `forwarding-always` | s24x3 | the forwarding always taken | stream 3, record 2: 21,520 where 22,280 | stream 1, sample 72, after the edge that loads frame 0: 0 where slot 0's written word |
| `read-at-the-write-pointer` | s24x3 | the memory read at `pool_wp` | stream 3, record 2: -35,184,372,057,676 where 22,280, slot 1's written word dropped | stream 3, sample 42: slot 0's written word where slot 1's |
| `forwarding-without-the-valid` | s24x3 | the pointers alone forward | stream 4, record 2: 27,520 where 28,280, after a gap of 2: frame 1's value in place of frame 0's | stream 1, sample 72: 0 where slot 0's written word |
| `not-zero-after-a-reset` | s24x3 | the flag reset to 0 | (passes, not named) | stream 1, sample 0, the first after the first reset: unknown bits where the register holds 0 |

**Six more faults, tried on a copy and not in the manifest** (P17), as a verifier would try them:
- four failed both tests: the choice inverted; the read enabled a stage late, by `vld[ST_S4]`; the pointers compared unequal; and the forwarded word taken from `pool_q`.
- `fwd_val` left out of the reset passed every record, as section 3 says it must, and failed `s4_old_at_every_edge` at its first sample.
- **The read's enable without `!rst` passed both tests.** That is no fault: under `rst` the flag's reset hides whatever `pool_q` loads. Only `tests/test_poolram_text.py` holds the enable as written (limit 9).

Each record figure is the arithmetic of its stream (P9). Stream 1 under s16x1 has one channel from 400 by 60 a frame, and the score at a pool of 1 is 10 times the sample: 4,600 at frame 1. Dropping 0 in place of frame 0's 4,000 gives 8,600. Dropping slot 0's written word gives 8,600 - (4 x 2^33 + 100) = -34,359,729,868.

## 6. What the lead's synthesis showed, and what the link must still show

**The lead's synthesis of this `core.sv`, out of context** (P18 to P20). Vivado 2022.2 on the box, 2026-11-26 21:14 to 21:27. It synthesised the core alone, at the kernel's parameters, with the kernel's `-cascade_dsp tree` and a 10 ns clock. The file it synthesised is this tree's `rtl/core/core.sv`, byte for byte.
1. **The memory became UltraRAM.** 48 URAM288 of the part's 640, no block RAM, and no distributed RAM primitive. The core has 97 LUTs as memory, every one a shift register, where the pool alone took about 192,512 in distributed RAM (P3).
2. **The synthesis log's UltraRAM table:** `pool_mem_reg`, 64 K x 164, read on port A and written on port B. It is 48 blocks in a matrix of shape 8x2, with no register provided for a pipeline and none absorbed.
3. **Two messages about it.** Vivado used its default cascade height of 8 (Synth 8-5780). It warned that the memory, implemented as UltraRAM, has no pipeline registers, and that they are recommended for high performance (Synth 8-6057). Section 4 expected the second; the message I named from memory, Synth 8-7052, was the wrong number.
4. **The timing estimate at 10 ns, before placement:** WNS +3.830 ns over 73,807 endpoints. The worst path from the memory has 5.112 ns of slack: 4.531 ns, 18 levels, from a URAM288 through seven blocks of its cascade and a carry chain of eight, into an input of a hidden product's DSP block. The worst path into `z_flat` has 5.781 ns: 4.146 ns, 17 levels. On that path the first block's cascade output takes 1.397 ns, each of the next six blocks 0.207 ns, and the last block's output 0.193 ns.
5. **The core alone:** 40,018 LUTs, 30,042 registers, 707 DSP slices.

So the template's two differences (section 4) are inside what Vivado infers, and the read path's estimate meets 100 MHz with about half the clock to spare. Routing adds delay that an estimate before placement does not hold.

**What the link must still show:**
1. **That the routed design keeps the 48 blocks and meets 100 MHz:** the read path's slack after routing, with the blocks placed in the SLR beside the core.
2. **What remains of the LUTs as memory:** about 13,000 in the whole routed design, where there were 205,206 (P6, an ESTIMATE). The read's multiplexer of 65,536 words to one, in LUTs, should go too; it is not counted here.
3. **The write side:** `pool_wp` and `s4_rect` now reach 48 blocks, not 24,576 RAM64M8 and RAM64M primitives (P3). The path of the 150 MHz link, the platform's reset to the pool's write enables (krnl.md, K30), should change with them: the write enable still carries `rst`.
4. **That the link's own synthesis of the kernel maps it the same way.** Its run sets only `CASCADE_DSP` (`hw/link.cfg`); a cap such as `-max_uram`, which I remember from Vivado's guide and have not read (BELIEVED), is not set there.

## 7. Limits

Each is stated by the behaviour it concedes.

1. **The benches meet no synthesis tool.** The lead's out-of-context synthesis made UltraRAM of this text, with an estimate that meets 100 MHz before placement (section 6). Whether the link places, routes and meets the clock with it is the link's record. A text that Icarus Verilog simulates rightly and Vivado maps to distributed RAM again passes every bench here. `tests/test_poolram_text.py` holds only that the text is the one the synthesis was run on: the attribute, one write and one read, and a read register with no reset.
2. **The read path through an unpipelined cascade** is timed only by the lead's estimate before placement (section 6). Placed and routed, it is the link's to time.
3. **`s4_old` at every edge is held on the second test's streams**, at pools of 1, 2, 3, 4, 5 and 8 on the small top, under each profile. Beyond them it is section 3's argument. A fault that changes `s4_old` only at a pool or a clock these streams do not reach, and changes no record of any bench, passes. The full top, 65,536 words and pointers of 16 bits, is held only by the records of the benches that build it.
4. **Two faults reach no record:** a read register that loads at every clock, and an `s4_old` not 0 after a reset. Only the second test sees them, by reading the core's signals by name. A renaming fails that test at its first sample. A fault in a signal it does not read is not seen by it.
5. **The memory's first sixteen words are written through the simulator** before each stream, so that a read of a word no frame wrote is a wrong word and not unknown bits. The frames that would have left such words are not run. In stream 7 the words left by the run cut short are the design's own.
6. **The hardware's read holds while its enable is low** (BELIEVED). The template's header gives old data at an address being written (READ), and the forwarding makes that case moot.
7. **Each mutant runs under one profile.**
8. **One simulator**, Icarus Verilog 12.0, which ignores the attribute.
9. **`tests/test_poolram_text.py` reads the text.** Code hidden in a block comment, or a second read written through another name for the memory, is not seen by it. It sees an assignment to `pool_q` of any form that begins with its name: nonblocking, blocking or continuous, whole or by a part select. Until VPOOLRAM's pass it saw only `<=`, and a blocking `pool_q = '0;` in an `always @*` passed it. An assignment inside a concatenation on the left, or from another module by a hierarchical name, is still not seen. It is the only thing that holds the read's enable as `!rst && vld[ST_S3]`: with `vld[ST_S3]` alone the core computes the same at every clock, and both tests pass (P17).
10. **Nothing here is evidence about sensitivity.**

## 8. Register

"The stage on a copy" is `python tools/check_rtl.py rtl-benches --root <a copy> --state <a folder>`, where the copy is this tree's `spec`, `model`, `learn`, `rtl`, `tools`, `docker` and `vectors`, and `host` for a row that needs it, with the manifest cut down to the rows named. The copies are in the parcel's scratch folder, which is not in the tree.

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| P1 | The kernel's pool is 65,536 words of 164 bits, 10,747,904 bits | COMPUTED | `rtl/krnl/undertone_krnl.sv`'s defaults: 4 filters, 128 taps, 4 rows, s16x1, so `W_RECT` = 32 + 8 + 1 = 41 and 4 x 41 = 164; krnl.md, K9 | the build's utilisation report |
| P2 | The routed image of 9bf71d7: 205,206 LUTs as distributed RAM, 76,666 in SLR0 and 128,540 in SLR1; 200,182 RAMD64E; 239.5 block RAM tiles of 1,344; 4 URAM of 640, all in SLR0 | READ | that link's `full_util_routed.rpt`, as copied to the round's folder, `link/9bf71d7-logs/` | that report |
| P3 | In distributed RAM the pool needs about 192,512 LUTs: 23 RAM64M8 and one RAM64M for every 64 words, 188 LUTs, 1,024 times. That Vivado chose that arrangement is BELIEVED; the figure is arithmetic on it | COMPUTED | 164 = 23 x 7 + 3; 23 x 8 + 4 = 188; 65,536 / 64 = 1,024; 188 x 1,024 = 192,512. And 1,024 x 24 = 24,576 groups of 64 words written by `pool_wp` | that link's utilisation by primitive |
| P4 | By capacity, as UltraRAM the pool needs 48 blocks: 3 wide and 16 deep, with a block of 4,096 words of 72 bits (BELIEVED). This is arithmetic, not Vivado's arrangement, which is P18's | COMPUTED | 164 / 72 rounded up is 3; 65,536 / 4,096 = 16; 3 x 16 = 48 | the synthesis's UltraRAM report (P18 agrees on 48) |
| P5 | As block RAM it needs at least 292 RAMB36 | COMPUTED | 10,747,904 / 36,864 = 291.6, rounded up | a synthesis with `"block"` |
| P6 | About 13,000 LUTs as memory should remain in the routed design | ESTIMATE | 205,206 (P2) less 192,512 (P3); round 3's design held about 13,500 outside its kernel, 209,562 against the kernel's 196,089 (K29 and its report) | the next link's report |
| P7 | Vivado 2022.2's language templates: UltraRAM's simple dual port puts `(* ram_style = "ultra" *)` on the memory, writes and reads in one block under one memory enable with a latency of one, reads into a register with no reset, has three pipeline registers after it, initialises nothing, and says old data shows when the two addresses are equal; block RAM's two-clock simple dual port reads and writes in separate blocks | READ | `data/parts/xilinx/templates/vivado/verilog.xml` of the box's install, lines 82216 to 82283 and the block RAM folder at 80431 to 80746, copied by the lead into the parcel's scratch folder (the round's ledger, `lead.md`, 20:58) | those files |
| P8 | After the first reset `s4_old` has the replaced register's value at every edge | BELIEVED | section 3's argument, by cases at an edge | a clock at which the second test, or any later one, finds them apart |
| P9 | The record figures of section 5's table are the arithmetic of their streams | COMPUTED | stream 1 under s16x1: samples 400 + 60i, the score 10 x the sample at a pool of 1, so 4,600 at frame 1, and 4,600 + 4,000 = 8,600; slot 0's written word is 2^33 + 16k + 1 in lane k, four lanes 4 x 2^33 + 100; stream 3 under s16x1: 10 x (1,060 + 1,120) = 21,800 and 10 x (1,000 + 1,120) = 21,200; under s24x3 the lanes are 1, 2, 3 and 4 times channels 0, 1, 2 and 0 | the evidence of P11 |
| P10 | On a copy holding the bench's two rows and `core-s16x1` with only `pool-no-forwarding`, the stage passed: 19 tests in 3 runs of 3 benches, 17,434 records identical to the model's, 9 mutant runs each failed as named, 12 build logs read with no line in them. The second test held 1,022 samples a profile, in eight streams of 128, 116, 97, 119, 97, 133, 196 and 136 | MEASURED | the stage on that copy, 2026-11-26 21:17:42 to 21:17:57, and on a fresh copy after the bench took its stage numbers from the design, 21:36:04 to 21:36:18: the same OK line both times; the evidence lines of `poolram-s16x1.s16x1` and `poolram-s24x3.s24x3` | the gate's second size |
| P11 | Each of the nine mutants failed where section 5's table says, at that record or sample and with those values | MEASURED | both runs of P10: each mutant's evidence file, and the first difference each logged, the same in both | a rerun |
| P12 | The bench's two rows and eight new mutants took 20 s of run time in each run of P10: 1 to 3 s a run in the first, 2 s each in the second, by the runner's own count | MEASURED | the lines "ran ... in N s" of each run's `runner.log`, added | another run; another load |
| P13 | At the kernel's maxima the pooled sum is 57 bits | COMPUTED | `W_POOL` = 32 + clog2(65,536 x 1 x 128 + 1) + 1 = 32 + 24 + 1 | the build |
| P14 | The text test passed, and each of its eleven plants was reported: eight from the first commit, and three since VPOOLRAM's pass, a blocking assignment to `pool_q` in an `always @*`, one to a bit of it, and a continuous assignment | MEASURED | `python -m pytest -q -p no:cacheprovider tests/test_poolram_text.py -s`, 2026-11-26 22:06: "4 passed", a line for each plant; at 21:19, on the first commit's check, the same with eight | that command |
| P15 | Round 3's kernel synthesis: 329,499 LUTs, 196,089 as memory, 0 URAM. Round 5's first fallback, placed: SLR1 at 96.74% of its CLBM slices. The worst path on the kernel's clock of round 3's third link (31aaec1) and of 9bf71d7's image, both closed at 100 MHz: from `pool_wp` to the pool's distributed RAM | READ | krnl.md, K28 and K29; the round's ledger, `lead.md`, entries 16:46 and 20:32 of 2026-11-26, and K35 on the branch `lead/krnl-l-split` | those reports |
| P21 | Vivado's "8x2" is two cascades of eight blocks in depth for each of three slices of the 164 bits, the two cascades' outputs chosen in the fabric | BELIEVED | my reading of P18's table, against 48 = 8 x 2 x 3 and P19's path through eight blocks, `pool_mem_reg_uram_8` to `pool_mem_reg_uram_15`, then LUTs | Vivado's documentation of the table, or the netlist's cascades |
| P16 | The streams of section 5: their pools, frames and gaps; sixteen words written into the memory before each; four filters of one tap with coefficients 1 to 4 | READ | `rtl/tb/bench_poolram.py`, `STREAMS`, `MIDFILL`, `IN_FLIGHT`, `POISONED`, `blob_for` | that file |
| P17 | Of six more faults, four failed both tests; `fwd_val` left out of the reset passed `bit_identity_pool_collisions` and failed `s4_old_at_every_edge` at sample 0 of stream 1; the read's enable without `!rst` passed both | MEASURED | the stage on a copy with the rows `poolramx-s16x1` and `poolramx-s24x3` of the parcel's scratch file `design/verifier.toml`, not in the tree, 2026-11-26 21:27:46 to 21:27:52: "FAIL rtl-benches: 3 finding(s)", the three MUTANT-SURVIVED, and each mutant's evidence | nothing in the tree: these mutants are not in the manifest |
| P18 | The lead's out-of-context synthesis of the core: 48 URAM288 of 640, 0 block RAM tiles, 0 distributed RAM primitives; 40,018 LUTs, 39,921 as logic and 97 as memory, the 97 shift registers; 30,042 registers; 707 DSP slices. Its UltraRAM table: `pool_mem_reg`, 64 K x 164, port A read and port B write, 48 URAM288, matrix shape 8x2, 0 registers provided for pipeline and 0 absorbed. Synth 8-5780, a default cascade height of 8; Synth 8-6057, no pipeline registers | READ | the round's folder, `syn/poolram/syn-poolram.tar`, SHA-256 f7f71d07..., which holds the lead's script `syn_poolram.tcl`, `syn.log` (lines 235, 2608 and 2615 to 2617) and `out/util.rpt`, `out/util_hier.rpt`; read by the lead, and by this parcel at 21:31 | those files |
| P19 | Its timing estimate at 10 ns: WNS +3.830 ns, TNS 0 over 73,807 endpoints, WHS 0.058 ns; from a URAM288, slack 5.112 ns, 4.531 ns, 18 levels (URAM288 7, CARRY8 8), to a DSP block's A input under `u_head`; into `z_flat_reg[55]`, slack 5.781 ns, 4.146 ns, 17 levels (URAM288 7, CARRY8 7), the first block's cascade output 1.397 ns, each of the next six 0.207 ns and the last block's output 0.193 ns | READ | the same tar: `out/timing.rpt`, `out/timing_from_uram.rpt`, `out/timing_to_zflat.rpt` | those files; the link's routed report is the measure |
| P20 | The core it synthesised is this tree's: the tar's `src/core.sv`, `src/core_head.sv` and `src/undertone_pkg.sv` have the SHA-256 of `rtl/core/core.sv`, `rtl/core/core_head.sv` and `spec/undertone_pkg.sv` (830be2f3..., b3460def..., edb24062...) | MEASURED | `sha256sum` of the three files out of the tar and of the tree's, 2026-11-26 21:31 | a change to any of the three |

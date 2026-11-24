# The kernel: the chain behind an AXI4-Lite port, writing every score record to memory

Parcel KRNL, round 3, 2026-11-24. The source, the injector and the detector core of round 2, unchanged, wired as [the seam](seam.md) wires them, inside a Vitis RTL kernel. A host drives the kernel through one AXI4-Lite slave, and the kernel writes every score record to one buffer in memory through one AXI4 master. The top is `rtl/krnl/undertone_krnl.sv`. The benches are `rtl/tb/bench_krnl.py`, `bench_krnl_max.py` and `bench_krnl_small.py`, with the helpers `rtl/tb/krnl_host.py` and `rtl/tb/krnl_mem.py`. The packaging is `hw/kernel.xml`, `hw/package_kernel.tcl` and `hw/link.cfg`, held to the definition by `tests/test_krnl_packaging.py`. How the RTL side works is [README.md](README.md). The design was approved by the lead on 2026-11-24 (the round's ledger, `lead.md`, entry 09:52) and the definition's change for it is the lead's commit 655d303.

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure here that was measured, read or worked out has a row in the register at the end. The kernel's own constants (a burst of at most 16, 16 bursts unanswered, a drain of 128 clocks) and the benches' (a poll every 12 clocks, a last answer held 200 clocks, the streams' lengths) are stated where their source defines them.

**What rests on what.** Everything here is bit identity: the kernel's score words, read back from a memory model, against the model's own run of the same configuration. **Nothing here is evidence about sensitivity**, nothing here is synthesised, and nothing of the packaging has been run by any tool. D0's gates advanced, and how:

- **bit identity**, its first part (RTL in simulation), through the kernel;
- **truth isolation**, in the kernel, in simulation;
- **capability bits**, built here in simulation, with a new row in `tests/gates.toml`: its control is a mutant, not a second build.

## 1. What the kernel is

- **The chain.** The kernel holds the three blocks of round 2 (`rtl/source/`, `rtl/inject/`, `rtl/core/`), unchanged. They are wired source to injector to core, exactly as `rtl/seam/seam.sv` wires them.
  - The core is built at the top's parameters `B_*`.
  - **Their defaults are the first build's maxima**: 4 filters, 4 rows, 128 taps, 12 hidden units, and the definition's other maxima (pool, the two shifts). That is Logan's word on the round's plan, question 2.
  - Every block's reset is the kernel's `ap_rst_n` or a write of `krn_reset`.
- **The register port.** One AXI4-Lite slave, `s_axi_control`, of the definition's 12 address bits and 32-bit words.
  - It takes one operation at a time: a write once both its address and its data are in hand, else a read. It answers OKAY to every operation; a refusal is latched in a register, as every block does.
  - **A write goes only to the block whose range holds its address.** So the injector's truth rows never reach the core's register port at all. The seam's top sent every write to all three blocks (seam.md, section 2).
  - A read goes to all three blocks, and each answers 0 outside its own range.
- **The memory path.** Every score record the core puts out during a run goes into a queue of `RECORD_QUEUE` records (512 by default), and from there to memory through one AXI4 master, `m_axi_gmem`. The master is 256 bits wide and only writes; its read channels are tied off.
- **The control protocol is Vitis's user-managed one.** XRT writes no register of the kernel's. The host writes every row itself, the kernel's start among them, and reads `krn_status` for done. Section 3 says why.

## 2. One record in memory

A score record is 168 bits, 21 bytes: index 8, epoch 4, flags 1, score 8.

- In memory it is a **slot of 32 bytes** (`[memory] slot_bytes` in the definition): its canonical bytes first (`model.records.pack`, the first declared field lowest, each field little-endian), then 11 zero bytes. **The zeros are always written**, so a host that fills a buffer first with a pattern sees a slot never written.
- **Record n is at the buffer's base + 32 n.** The base must be a multiple of 32.
- One record is one beat of the 256-bit master, data byte k going to address + k. That is AXI's rule for byte lanes, BELIEVED from memory of the specification; both memory models here, this parcel's and cocotbext-axi's `AxiRamWrite`, store a beat so.
- A run of 2^17 records is 4 MiB and one of 2^20 is 32 MiB.

## 3. Where the kernel's own registers are, and why the protocol is user-managed

The sibling project's host code records that **XRT's start of an ap_ctrl_hs kernel sends an image of its arguments**, every declared argument rewritten, and a zero for one not set (`<repos>/cft-fp256/host/src/backend_xrt.cpp`, line 281).

In this project's map the core's rows begin at 0x10, where an ap_ctrl_hs kernel's arguments sit:
- an argument at 0x10 would land on the core's read-only identity rows;
- one placed higher would be safe only if XRT writes argument words and nothing between them, which no one here has shown.

So the kernel is user-managed, and **nothing sits below 0x10**: the four words there read 0, and a write there is refused, REGISTER_ACCESS.

The kernel's rows are a block of their own, **`kernel` = [0xE00, 0xF00]**, taken from the end of the core's range. The core had no row there (its last is at 0x11C) and decodes its range from the package, so no line of the core changed.

| row | offset | access | what |
|---|---|---|---|
| `krn_buffer` | 0xE00, 2 words | rw | the buffer's base, bytes |
| `krn_size` | 0xE08, 2 words | rw | the buffer's size, bytes |
| `krn_frames` | 0xE10, 2 words | rw | the run's length in frames, which is the records it must write |
| `krn_start` | 0xE18 | wo | a write of 1 starts a run (section 5) |
| `krn_reset` | 0xE1C | wo | a write of 1 resets the three blocks and the run's state; the arguments are kept |
| `krn_status` | 0xE20 | ro | bit 0 running, bit 1 done, bit 2 refused |
| `krn_refusal` | 0xE24 | rw | the first refusal since cleared; a write of 0 clears it, in every state |
| `krn_records` | 0xE28, 2 words | ro | records written and answered OKAY, in order, from slot 0; a read of the lower word holds the upper |
| `krn_queue_peak` | 0xE30 | ro | the most records the queue held at once in the run |
| `cap_record_queue` | 0xE34 | ro | the build's queue depth |

A few rules on these rows:
- **`done` is not cleared by a read.** It stays until the next start or `krn_reset`, so two readers cannot take it from each other.
- **`src_frames` is the kernel's to write.** `krn_start` writes it from `krn_frames`. A host's write of it through the kernel is refused, REGISTER_ACCESS, and is not forwarded: otherwise a host could start the source with nobody collecting its records.
- **`krn_reset` exists for the card day.** The core's only way back to the stopped state is reset (core.md, limit 7), and the card day runs two shapes.

## 4. When the memory path stalls

Nothing slows the source, so records wait in the kernel's queue.

- **The first build's depth is 512.** That covers a memory that takes nothing for 10,240 clocks (102.4 us at 100 MHz) under 16-bit one-channel samples, and for 30,720 clocks under 24-bit three-channel. How long the card's memory ever refuses a write has not been measured; `krn_queue_peak` is how the card day reads how near a run came.
- **A record that finds the queue full is refused, RECORD_QUEUE.** It is never dropped silently. From then on no record of the run is queued. The records already queued are still written, so memory holds the run's first M records, M being the refused record's index, and `krn_records` reads M.
- **A burst** is as many queued records as no burst has yet taken, at most 16, and never across a 4 KB page. One burst's data goes at a time, after its address; up to 16 bursts may be unanswered.
- With memory keeping up, most bursts are one beat. After a stall they lengthen to drain what waited.
- **An answer other than OKAY is refused, MEMORY_WRITE.** No burst is issued after it, and `krn_records` stops at the records answered OKAY before it.

## 5. The run, and what is refused at the edge

At a write of `krn_start`, in this order:

1. any value but 1: REGISTER_ACCESS;
2. a run going: **KERNEL_BUSY**;
3. then `done` falls;
4. a refusal already latched: the start is not taken and nothing more is latched (the host clears, then starts; the source does the same);
5. `krn_frames` 0: **STREAM_LENGTH**;
6. `krn_buffer` not a multiple of 32: **BUFFER_ALIGN**;
7. `krn_size` under 32 x `krn_frames`, or the slots running past 2^64: **BUFFER_SIZE**.

Then the kernel writes `src_frames` itself (the upper word starts the source) and reads `src_status` back. If the source does not say it runs, **RUN_START**. The source does nothing, silently, on a start while its own refusal is latched (`rtl/source/source.sv`, line 227), and without this check the kernel would wait for frames that never come. The answer to the `krn_start` write comes when all this is decided.

While a run goes:
- a write of an argument, of `krn_start` or of `krn_reset` is **KERNEL_BUSY**;
- writes to the blocks go through: the core's shadow and commit (a swap), the injector's truth records;
- a record arriving with no run going, or past `krn_frames` records, is **RUN_LENGTH**.

**Done rises only with the chain idle**:
- the source has put out `krn_frames` frames;
- 128 clocks have passed since its last one (the chain's last record comes 52 + 11 = 63 clocks after it);
- every queued record is written, or abandoned after MEMORY_WRITE;
- every burst is answered.

Then, with no refusal of the run's own, a count of records answered other than `krn_frames` is **RUN_LENGTH**. That is the chain stopping short: the injector refusing (INJECT_RANGE, INJECT_OVERLAP, ...) or a core never started (CORE_STOPPED). The kernel's register says the run did not complete, and the block's own register says why.

**Truth records during a long run come from the host, while it runs.** The kernel forwards writes to the injector's rows at any time. The injector guards both directions by name, and each refusal ends the run:
- a record written for an index the stream has passed: INJECT_OVERLAP;
- one written into a full store: INJECT_PENDING.

So a host that falls behind gets a refusal by name, then the kernel's RUN_LENGTH. It never gets a wrong record. What the card day can then run is section 8's.

## 6. The benches

The kernel is driven **only** as a host would drive it:
- through its AXI4-Lite port, by cocotbext-axi's `AxiLiteMaster`, a third party's model of that protocol;
- through memory, by `rtl/tb/krnl_mem.py`, a write slave of this parcel's.

The memory model:
- logs every beat with its address;
- holds any channel, at random from a seed or until the bench says;
- delays answers, and holds the one for the run's last beat 200 clocks;
- answers a named burst SLVERR;
- fills the buffer and a margin round it with a pattern;
- checks every burst against what the kernel must do: one slot a beat, INCR, at most 16 beats, no 4 KB page crossed, every strobe set, WLAST on the last beat, every beat inside the region.

One test a profile runs against cocotbext-axi's own `AxiRamWrite` instead, under its pause generators, so a third party's write path reads the same records back.

**What a run holds** (`krnl_host.hold_run`). The model's records are `seam_host.model_records`: `model/run.py`'s own lines, with a shadow write and a commit made on the model's core first when a swap is asked for. Then:
- **memory**, slots 0 to N-1 against those records, where **N is `krn_frames`, what the kernel was asked for, not what was read**;
- **as written**, the beats in the order the memory took them, against the same records;
- and by assertion:
  - every slot's padding is zero;
  - beat i went to base + 32 i;
  - every byte outside the run's slots still holds the pattern;
  - no fault of protocol;
  - `krn_records` = N;
  - no refusal in the kernel or any block;
  - **when done was first read, every burst the memory had taken had been answered**.

Done is polled through the port every 12 clocks from the start write's answer on.

What each fault shows as:

| fault | where it shows |
|---|---|
| a record never written | the pattern at its slot, a WORD mismatch there |
| one written twice | a mismatch as written; in memory too when the second lands in another slot, as the mutant `writes-one-twice` does. A burst written again at its own slot with the same bytes would show as written alone: no such fault is planted |
| the last lost | a mismatch at N-1 and RUN_LENGTH |
| the first lost | a mismatch at 0 |

**The tops.** The runner hands a top two parameters, so:
- `undertone_krnl` itself, at its defaults, is the first build's top: the very file that is packaged;
- `krnl_max.sv` is the same at the definition's maxima;
- `krnl_small.sv` is the same at the seam's small maxima with a queue of 8. A stall longer than its queue costs eight records' clocks, not 512.

The bench rows:

| row | top | tests |
|---|---|---|
| `krnl-first`, both profiles | `undertone_krnl` | `identity_e0` (E0's shape, slots across a 4 KB page, random holds, a swap written while the run goes and committed at a named index; under s16x1 at the seam's sigma, a table of 459 entries, with two pulses that touch), `identity_hidden` (every row at every tap, all twelve hidden units), `capabilities_are_accepted`, `identity_on_axi_ram` |
| `krnl-max`, both profiles | `krnl_max` | `identity_e0`, `capabilities_are_accepted` |
| `krnl-small-s16x1`, `krnl-small-s24x3` | `krnl_small` | `identity_small` (a burst held to meet a page's edge, random holds, the last answer late; then the comparison handed a model one record late must report WORD at 0), `truth_isolation` (3/1 and 6/2 at one index, the same samples, the same digests), `truth_while_running`, `chain_refusal_ends_the_run`, `queue_overflow_refused`, `memory_error_refused`, `refused_at_the_edge`, `reset_between_runs` |

**The capability-bits gate.** `capabilities_are_accepted` reads every capability register through the port. For each bound it configures a shape at the advertised value, with the others small, and requires it taken; then one past it, which must be refused by that bound's name. The bounds are filters, taps, pool, the score shift, hidden units, the hidden shift, and rows under s24x3 only (core.md, limit 12). Each rectifier code from 0 to 7 is taken or refused as `cap_rectifiers` says. Each case begins with `krn_reset`, since a configured core has no way back.

**The mutants**: ten runs, each read by its evidence (K6):

| mutant | row | what it plants | must fail | what its evidence says |
|---|---|---|---|---|
| `drops-one-record` | krnl-small-s16x1 | record 5 counted and not queued | `identity_small` | WORD at record 5: index 6 where the model has 5 |
| `address-steps-wrong` | krnl-small-s16x1 | each burst's next address one slot short | `identity_small` | WORD at record 0: index 18 where the model has 0 |
| `done-before-answer` | krnl-small-s16x1 | the run's end waits for no answer | `identity_small` | memory and as written both identical; "done was read at clock 3774 with a burst the memory had taken not yet answered" |
| `queue-overflows-silently` | krnl-small-s16x1 | a full queue drops the record and latches nothing | `queue_overflow_refused` | every refusal register none, where RECORD_QUEUE is required |
| `error-answer-ignored` | krnl-small-s16x1 | bresp not read | `memory_error_refused` | every refusal register none, where MEMORY_WRITE is required |
| `truth-reaches-the-core` | krnl-small-s16x1 | the lowest bit of the last numerator written to the injector XORed into the core's every frame | `truth_isolation` | WORD at record 1 of the first wording (3/1): score 1890 where the model has 2160 |
| `writes-one-twice` | krnl-small-s24x3 | record 5's beat sent and sent again as the next | `identity_small` | WORD at record 6: index 5 where the model has 6 |
| `advertises-a-deeper-queue` | krnl-small-s24x3 | `cap_record_queue` reads twice the depth | `queue_overflow_refused` | `krn_records` 13 where the advertisement predicts 21 (5 taken and a queue of 16) |
| `advertises-a-longer-filter` | krnl-first, both profiles | a copy of `rtl/core/core.sv` reads `cap_taps` as one more | `capabilities_are_accepted` | "a shape at the advertised taps was refused SHAPE_TAPS", under each profile |

The truth mutant was planned to show as two digests differing. It is caught earlier: its first wording, with an odd numerator, already differs from the model at record 1.

**Tried once by hand, on a copy, and not in the manifest** (K17). Nine more faults of the kernel's, each under s16x1 on the small top. Eight failed the test named for them, each where its fault predicts:

| fault | what it showed |
|---|---|
| the last record not queued | WORD at record 128, the pattern in the slot |
| the first record not queued | WORD at record 0: index 1 where the model has 0 |
| no burst cut at a 4 KB page | the memory model's fault: a burst of 5 beats from 0x2FFC0 crosses the page |
| the base ignored | WORD at record 0, the pattern in the slot |
| padding of ones | "slot 0's padding is ffffffffffffffffffffff, not zeros" |
| a drain of one clock | WORD at record 126, the pattern in the slot |
| strobes not checked | a write of two bytes refused none, not REGISTER_ACCESS |
| the source's start not checked | a start with no table refused none, not RUN_START |

The ninth was planted to show limit 4, and it passed `identity_small`, as that limit says it must: `issued` and `krn_records` counted modulo 256.

## 7. The packaging

`hw/kernel.xml` is adapted from the sibling project's, read there and not copied whole. It declares:
- the kernel `undertone_krnl`, user-managed;
- the slave `s_axi_control` of 0x1000 bytes and 32-bit words;
- the master `m_axi_gmem` of 256 bits;
- one argument, the buffer, on that master at `krn_buffer`'s offset, 0xE00, so that v++ binds the master to memory. XRT never writes it.

`hw/package_kernel.tcl` is adapted from the sibling's. It names its seven sources (the generated package, the three blocks' five files, the kernel's top) rather than globbing, so neither bench top in `rtl/krnl/` is packaged. It packages the top's defaults and prints each parameter it carries as an `HDLPARAM:` line.

`hw/link.cfg` is one compute unit, its master to `HBM[0]`; the clock is the build's to ask.

`tests/test_krnl_packaging.py`, in the gate's first size, holds every number and name in the three files to the definition and the top, and is shown to report eight planted faults. **No tool has read any of the three files**: that is the lead's, in BUILD.

## 8. What the card day can run

- **2^17 samples of stage E0's stream are certain.** Its at most 1,024 truth records all go into the injector before the start (the round's plan, L36).
- **2^20 samples can be tried.** It needs 7,168 more truth records written while the run goes: about 39,000 a second, five register writes each, so 195,313 writes a second, one every 5.1 us, for the run's 0.21 s at 100 MHz.
- How fast XRT's register writes go on this card nobody here has measured. The lead found that XRT 2.14's Python binding cannot reach a user-managed kernel's registers at all, and C++'s `xrt::ip` can (`lead.md`, 10:09).
- **Either way a run ends with every score word the model's, or with INJECT_OVERLAP and RUN_LENGTH by name.**

## 9. Limits

Each is stated by the behaviour it concedes.

1. **One simulator, nothing built.** Only Icarus Verilog 12.0 has read the RTL. No tool has read the packaging. A construct Vivado will not elaborate, an interface the packager does not infer, or a protocol `package_xo` does not take from the XML is not seen here.
2. **User-managed rests on a reading.** Under ap_ctrl_hs XRT sends an argument image (READ, from the sibling's code); that it would write the words between this map's rows is BELIEVED and untested. Neither is held by anything here. The host side of user-managed (`xrt::ip`, the buffer's bank) is HOST's and the lead's.
3. **The overflow is held at a depth of 8, not 512.** A packaged kernel whose queue held fewer than 512 records while its `cap_record_queue` read 512 passes every test here: `capabilities_are_accepted` of `krnl-first` reads 512 from the register, not from the queue. That the register and the queue agree is held on the small top, by `queue_overflow_refused` and its mutant `advertises-a-deeper-queue`.
4. **No run is longer than 129 frames.** `krn_records`, `rec_in`, the source's count and the address are 64 bits. **A kernel whose counters wrapped at 256 passes**, as the foundation's README, limit 5, says of its index: one with `issued` and `krn_records` counted modulo 256 passed `identity_small` (K17). The upper words of `krn_records` and `krn_frames` are never non-zero in a run.
5. **Truth from the host at a long run's rate is not simulated.** No run here holds more than one truth record written while it runs, nor needs more than the injector's store of 1,024, which a run of 65,536 frames would.
6. **The memory model is this parcel's reading of AXI4**, cross-checked by `identity_on_axi_ram` against cocotbext-axi's `AxiRamWrite` once a profile. It takes a burst's data only after its address. AXI allows data first and this kernel never sends it so; a kernel that did would stall here and fail on a bound, not on a named fault. It never reorders answers.
7. **Done is polled every 12 clocks.** Done is sticky, so a done that rose is seen. What is held is that when it was first read every burst was answered, not the clock it rose at.
8. **The drain is 128 clocks**, twice the chain's latency of 63 by the blocks' documents. A chain whose latency grew past 128 would end every run RUN_LENGTH, loudly, on every identity test; it would not pass silently.
9. **A record arriving at the edge that frees a slot of a full queue is refused.** The queue's count is read before that edge's beat leaves.
10. **After MEMORY_WRITE the queued records are abandoned.** `krn_records` counts only the records answered OKAY before the first error. One error test runs: the fourth burst answered SLVERR, with no stall.
11. **Up to 16 bursts may be unanswered**; no test asserts that sixteen ever were.
12. **The edge's refusals, the stall, the error, the chain's refusal, the reset and the truth during a run are held on the small top.** The kernel's lines there are the packaged top's, at other parameters. On the packaged top they are not run.
13. **A burst meeting a page's edge is held on the small top**, where a hold makes a burst of several beats end there. On the other tops the memory model's check holds the page rule on whatever bursts happen.
14. **A record arriving with no run going** (RUN_LENGTH) is not reachable without a fault and is not run. Neither are an answer nobody asked for (MEMORY_WRITE) and a source that stops before its count.
15. **Each record of an identity test is counted twice in the stage's total**: once from memory and once as written.
16. **A mutant shows the bench sees its fault under one profile**, but for the capability mutant, which runs under both. One mutant adds logic of its own, `truth-reaches-the-core` (a register and an XOR on one line). Its evidence is at the record it predicts (K6), which is what holds it.
17. **`advertises-a-longer-filter` edits RTL-B's file**, `rtl/core/core.sv`, as text inside the mutant. It stops applying when that line changes, and the stage then refuses it by name.
18. **The swap through the kernel is at one index**, in `identity_e0`: other gains of E0's shape, at index 80 under s16x1 and 50 under s24x3.
19. **The first build's pool memory is 65,536 entries** (the definition's `max_pool`) of 164 bits under s16x1, 10,747,904 bits, uncounted by the round's plan, which counts DSP slices. What it costs is the build's report's to say.
20. **The streams are short and the sigmas mostly small**, to keep the run time under four minutes (K4). The seam's sigma, a table of 459 entries, is run in one test, `identity_e0` under s16x1.

## 10. Register

"The stage on a copy" is `python tools/check_rtl.py rtl-benches --root <a copy> --state <a folder>`, where the copy is this tree's `spec`, `model`, `learn`, `rtl`, `tools`, `docker` and `vectors` with a manifest of this parcel's four rows alone. The copies are in the round's folder, `scratch/KRNL`, which is not in the tree.

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| K1 | A score record is 168 bits, 21 bytes, in a slot of 32: 11 bytes of zeros after it | READ | `spec/undertone.toml`, `[records]` and `[memory]` | the definition |
| K2 | A queue of 512 covers a memory that takes nothing for 10,240 clocks (102.4 us at 100 MHz) under s16x1 and 30,720 under s24x3 | COMPUTED | 512 x 20 and 512 x 60 clocks a record (the plan, L12); 10,240 x 10 ns | arithmetic |
| K3 | On a copy holding this parcel's four rows, the stage passed: 28 tests in 6 runs of 4 benches, 2,352 records identical to the model's, 10 mutant runs each failed as named, 16 build logs read and the 32 lines in them each on the committed list | MEASURED | the stage on a copy, 2026-11-24 10:38:05 to 10:39:08: its OK line | the gate's second size, whose line for the stage holds these rows' with the others' |
| K4 | The sixteen runs of those rows took 223 s summed, each run's own time by the runner's count, six side by side: 4 + 4 + 9 + 12 + 15 + 21 + 14 + 24 + 13 + 7 + 7 + 7 + 6 + 9 + 34 + 37. The longest was 37 s, `krnl-small-s24x3.s24x3` | MEASURED | the same run of the stage: its `runner.log`, the lines "ran ... in N s" | another run; another load |
| K5 | cocotb's own count of the simulated nanoseconds a wall second, for each run's whole test list, was 7,987 and 11,056 on `krnl-first` (s16x1, s24x3), 9,547 and 10,687 on `krnl-max`, 11,102 and 15,257 on `krnl-small`: about 800 to 1,500 clocks a second at 10 ns, the AXI4-Lite writes that load each run among them | MEASURED | the same run: the TESTS line of cocotb's summary in each run's log | another run; another load |
| K6 | Each of the ten mutant runs failed at the record and field section 6's table gives | MEASURED | the same run: each mutant run's evidence file and log, read line by line | the gate's second size: each fails as named there; its place is in its evidence |
| K7 | The packaging agrees with the definition and the top, and its check reports each of eight planted faults | MEASURED | `python -m pytest -q -p no:cacheprovider tests/test_krnl_packaging.py`, 2026-11-24: 2 passed | that command |
| K8 | A run of 2^20 samples at 100 MHz under s16x1 lasts 0.21 s and needs 7,168 truth records written while it runs, 195,313 register writes a second | COMPUTED | 1,048,576 x 20 / 1e8; the plan, L36 and L37: 8,192 - 1,024; 5.0e6 / 128 x 5 | arithmetic |
| K9 | The first build's pool memory is 10,747,904 bits under s16x1 | COMPUTED | 65,536 entries x 4 filters x 41 bits; 41 is `W_RECT` of `rtl/core/core.sv` line 86 at 16-bit samples, 1 row a filter and 128 taps: 32 + 8 + 1 | the build's utilisation report |
| K10 | XRT's start of an ap_ctrl_hs kernel sends every declared argument's word, a zero for one not set | READ | `<repos>/cft-fp256/host/src/backend_xrt.cpp`, line 281, the sibling project's own record | a host trial of an ap_ctrl_hs kernel whose arguments are set apart |
| K11 | XRT writes the words between two arguments as well | BELIEVED | nothing: no one here has read XRT's source on it or tried it | a hardware emulation trial that reads back a word between two arguments |
| K12 | The source does nothing, and latches nothing, on a start while its own refusal is latched | READ | `rtl/source/source.sv`, line 227 | that file |
| K13 | The chain's last record comes 52 + 11 = 63 clocks after the source's last frame; the kernel's drain is 128 | READ | seam.md, row K3; `rtl/krnl/undertone_krnl.sv`, `DRAIN` | `identity_*` ending in RUN_LENGTH |
| K14 | XRT 2.14's Python binding has no `ip` class and cannot reach a user-managed kernel's registers; C++'s `xrt::ip` can | READ | the round's ledger, `lead.md`, entry 10:09, the lead's trial in `cft2204` | a trial on the box's XRT |
| K15 | The first build's depth of 512 is a DECISION of this parcel's, approved by the lead; no measurement of the card's memory stalls exists here | DECISION | the round's ledger, `KRNL.md` 09:44:33, section 3; `lead.md` 09:52 | the card day's `krn_queue_peak` |
| K16 | With these rows the gate's second size passed: the stage `rtl-benches` 200 tests in 20 runs of 17 benches, 66,298 records identical to the model's, 106 mutant runs each failed as named, 126 build logs read, in 202 s; before these rows it was 172 tests, 63,946 records, 96 mutant runs and 110 build logs, so these rows add 28 tests, 2,352 records, 10 mutant runs and 16 build logs, K3's figures. The verdict named one inner skip, E1-RECORD-STALE | MEASURED | `bash verify/run.sh --with rtl`, run 20261124-104407-655d303, 2026-11-24 10:44:05 to 10:52:15, on this parcel's tree before this row was written: its line for `rtl-benches` and its verdict line; the earlier figures are the round's ledger, `lead.md`, entry 09:56, for 28358e0 | that command |
| K17 | Nine faults tried by hand: eight failed the test named for them where section 6's second table says; the ninth, counters modulo 256, passed `identity_small` | MEASURED | the stage on a copy with the row `krnlx-s16x1` and nine mutants, 2026-11-24 10:52:59 to 10:53:16: "1 finding(s)", that finding "MUTANT-SURVIVED" for the ninth, and each other run's log read; the rows are `scratch/KRNL/extra.toml` | nothing in the tree: these mutants are not in the manifest |
| K18 | A run of 2^17 records is 4 MiB of slots and one of 2^20 is 32 MiB | COMPUTED | 131,072 x 32 = 4,194,304 bytes; 1,048,576 x 32 = 33,554,432 bytes | arithmetic |
| K19 | The model's noise table at the seam's sigma of 50 under s16x1 has 459 entries; at the benches' small sigmas, 56 under s16x1 (6) and 60 under s24x3 (13/2) | MEASURED | `python -c "from model import source; print(len(source.Noise('s16x1', 2026112470, 50, 1, 129).table), len(source.Noise('s16x1', 1, 6, 1, 10).table), len(source.Noise('s24x3', 1, 13, 2, 10).table))"`, 2026-11-24: 459, 56, 60 | that command |

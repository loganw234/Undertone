# The kernel: the chain behind an AXI4-Lite port, writing every score record to memory

Parcel KRNL, round 3, 2026-11-24. The source, the injector and the detector core of round 2, unchanged, wired as [the seam](seam.md) wires them, inside a Vitis RTL kernel. A host drives the kernel through one AXI4-Lite slave, and the kernel writes every score record to one buffer in memory through one AXI4 master. The top is `rtl/krnl/undertone_krnl.sv`. The benches are `rtl/tb/bench_krnl.py`, `bench_krnl_max.py` and `bench_krnl_small.py`, with the helpers `rtl/tb/krnl_host.py` and `rtl/tb/krnl_mem.py`. The packaging is `hw/kernel.xml`, `hw/package_kernel.tcl` and `hw/link.cfg`, held to the definition by `tests/test_krnl_packaging.py`. How the RTL side works is [README.md](README.md). The design was approved by the lead on 2026-11-24 (the round's ledger, `lead.md`, entry 09:52) and the definition's change for it is the lead's commit 655d303.

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure here that was measured, read or worked out has a row in the register at the end. The kernel's own constants (a burst of at most 16, 16 bursts unanswered, a drain of 128 clocks) and the benches' (a poll every 12 clocks, a last answer held 200 clocks, the streams' lengths) are stated where their source defines them.

**What rests on what.** Everything here is bit identity: the kernel's score words, read back from a memory model, against the model's own run of the same configuration. **Nothing here is evidence about sensitivity**, nothing here is synthesised, and nothing of the packaging has been run by any tool. *Restated by the lead on 2026-11-25:* the packaging has since been run by the lead, and the third link for the card synthesised, placed and routed this kernel and closed its clock at 100 MHz (section 7, rows K26 to K30). That is a record of where Vivado closed the design, and nothing has run on the card. *Restated by the lead on 2026-11-25, after the card day:* that image has run on the card. Every score word of ten runs, five cases at 2^17 and at 2^20 frames, equals the model's, and the flipped-bit control was seen in both of its runs ([the card day](../studies/CARD-first-light.md)). That is bit identity's third part, and still nothing about sensitivity. D0's gates advanced, and how:

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

The kernel's rows are a block of their own, **`kernel` = [0xE00, 0xF00]**, taken from the end of the core's range. The core had no row there (its last row, `shadow_words` at 0x118, ends at 0x11C) and decodes its range from the package, so no line of the core changed.

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
- **A burst** is as many queued records as no burst has yet taken, at most 16, and never across a 4 KB page. One burst is out at a time, and up to 16 may be unanswered.
- **A burst's address and its data are offered together.** The data never waits for the address to be taken, and may lead it. That is AXI4's rule as remembered, section A3.3.1 (K22, BELIEVED: the specification was not read): a master must not wait for AWREADY or WREADY before raising AWVALID or WVALID, and a slave may wait for WVALID before raising AWREADY.
- The first version of this kernel raised WVALID only after AWREADY. Against a memory whose AWREADY waits for WVALID it hung on its first burst, a deadlock the card's memory path could meet. The verifier VKRNL found it (K23). The bench `identity_w_before_aw`, and `identity_e0` on the two large tops, now run against such a memory, under both profiles, and the mutant `w-waits-for-the-address` holds that they see it.
- With memory keeping up, most bursts are one beat. After a stall they lengthen to drain what waited.
- **An answer other than OKAY is refused, MEMORY_WRITE.** No burst is issued after it, and `krn_records` stops at the records answered OKAY before it. *Restated by the lead at the merge, 2026-11-24, from the verifier VKRNL-2:* but for one edge. The writer reads the error from a register, so at the clock the error's answer is taken an idle writer with records waiting can still offer one burst (VKRNL-2's sweep of the answer's delay: at a delay of 16 the answer was taken at clock 26502 and a burst first offered at 26503). That burst is written and not counted: `krn_records` stays at the records answered OKAY before the error, and a host that reads `krn_records` slots never reads it.

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
- takes a beat of data only once its burst's address is taken (WREADY waits for the address), and, in a mode the bench sets, takes an address only at an edge where WVALID is high (AWREADY waits for WVALID): the two orders a slave may impose, by A3.3.1 as remembered (K22);
- fills the buffer and a margin round it with a pattern;
- checks every burst against what the kernel must do: one slot a beat, INCR, at most 16 beats, no 4 KB page crossed, every strobe set, WLAST on the last beat, every beat inside the region.

One test a profile runs against cocotbext-axi's own `AxiRamWrite` instead, under its pause generators, so a third party's write path reads the same records back. There a passive look at the bus counts each address and each answer taken, so that the check that done was read only after every answer holds there too. Until commit 955284c it held nothing there, since nothing filled those counts (VKRNL). *Restated by the lead at the merge, from VKRNL-2:* the check can now fail there, but no run makes it: every answer comes well inside the 128-clock drain, so done is never read there with a burst in flight, and the mutant `done-before-answer`, run against `identity_on_axi_ram`, survives. The check that holds done is the memory model's, on the small top.

**Long bursts, by construction.** Until commit 955284c no bench made a burst of more than 8 beats: the small top's queue of 8 capped them, and the large tops never queued more. The verifier VKRNL showed four faults that only longer bursts show, each passing every identity test then. `identity_long_bursts`, on the packaged top under both profiles, now makes them come:
- the memory holds its address and data channels while forty records queue, so the kernel's queue of 512 releases bursts of 16, one cut at a 4 KB page;
- it holds them again while twelve queue, for a burst of 9 to 15.

The test requires a burst of 16, one of 9 to 15, and one of several beats ending at the page's edge. VKRNL's four are mutants on that test (the table below).

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
| `krnl-first`, both profiles | `undertone_krnl` | `identity_e0` (E0's shape, slots across a 4 KB page, random holds, a memory whose AWREADY waits for WVALID, a swap written while the run goes and committed at a named index; under s16x1 at the seam's sigma, a table of 459 entries, with two pulses that touch), `identity_long_bursts`, `identity_hidden` (every row at every tap, all twelve hidden units), `capabilities_are_accepted`, `the_first_builds_maxima`, `identity_on_axi_ram` |
| `krnl-max`, both profiles | `krnl_max` | `identity_e0`, `capabilities_are_accepted`, `the_definitions_maxima` |
| `krnl-small-s16x1`, `krnl-small-s24x3` | `krnl_small` | `identity_small` (a burst held to meet a page's edge, random holds, the last answer late; then the comparison handed a model one record late must report WORD at 0), `identity_w_before_aw` (a memory whose AWREADY waits for WVALID), `truth_isolation` (3/1 and 6/2 at one index, the same samples, the same digests), `truth_while_running`, `chain_refusal_ends_the_run`, `queue_overflow_refused`, `memory_error_refused`, `refused_at_the_edge`, `reset_between_runs` |

**The capability-bits gate.** `capabilities_are_accepted` (in `krnl_host`, run on the packaged top and at the definition's maxima) reads every capability register through the port. Each case begins with `krn_reset`, since a configured core has no way back. For each register the core and the source answer, it configures something at the advertised value with everything else small, and requires it taken; then one past it, which must be refused by that bound's name:
- the profile, `cap_sample_bits` and `cap_channels`: PROFILE_UNKNOWN;
- `cap_filters`, `cap_taps`, `cap_pool`, `cap_score_shift`, `cap_hidden`, `cap_hidden_shift`: each its own name;
- `cap_rows`, under s24x3 only (core.md, limit 12): SHAPE_ROWS;
- `cap_rectifiers`: each code from 0 to 7 taken or refused, SHAPE_RECTIFIER, as its bits say;
- `cap_coeff_bits`: a weight at each end of the range taken, one past either end refused, WEIGHT_RANGE;
- `cap_noise_table`: a table of that many entries declared, one more refused, NOISE_RANGE.

Three registers are read and not tried here:
- `cap_blob_versions`: the fabric sees no blob (core.md, limit 6);
- `cap_inject_pending`: offering 1,024 truth records would be most of a run;
- `cap_record_queue`: tried only on the small top, by `queue_overflow_refused` and its mutant `advertises-a-deeper-queue`.

**No value is compared here with a number of the bench's own.** A register that reads wrong is seen only through what the build then takes or refuses, so the gate's two controls fail through the gate's check alone:
- `advertises-a-longer-filter`: a shape at the advertised taps is refused;
- `takes-one-tap-past-its-advertisement`: a shape past them is taken.

That the packaged top advertises the first build's maxima is a test of its own, `the_first_builds_maxima`; `the_definitions_maxima` is its partner on the large top. Until commit 6e48999 that comparison sat inside the gate's test, and VKRNL showed the control then failed on it alone. Two more faults were tried by hand, each failing the gate where predicted (K24):
- `cap_coeff_bits` one more: "weights at the advertised coefficient's ends were refused WEIGHT_RANGE";
- `cap_noise_table` one more: "a table of the advertised 32768 entries was refused NOISE_RANGE".

**The mutants**: twenty-four runs, each read by its evidence (K6):

| mutant | row | what it plants | must fail | what its evidence says |
|---|---|---|---|---|
| `drops-one-record` | krnl-small-s16x1 | record 5 counted and not queued | `identity_small` | WORD at record 5: index 6 where the model has 5 |
| `address-steps-wrong` | krnl-small-s16x1 | each burst's next address one slot short | `identity_small` | WORD at record 0: index 18 where the model has 0 |
| `done-before-answer` | krnl-small-s16x1 | the run's end waits for no answer | `identity_small` | memory and as written both identical; "done was read at clock 3774 with a burst the memory had taken not yet answered" |
| `queue-overflows-silently` | krnl-small-s16x1 | a full queue drops the record and latches nothing | `queue_overflow_refused` | every refusal register none, where RECORD_QUEUE is required |
| `error-answer-ignored` | krnl-small-s16x1 | bresp not read | `memory_error_refused` | every refusal register none, where MEMORY_WRITE is required |
| `w-waits-for-the-address` | krnl-small-s16x1 | WVALID raised only once the burst's address is taken | `identity_w_before_aw` | "after 3796 clocks the kernel has not said done: {'running': 1, 'done': 0, 'refused': 1}": no beat taken, the queue full, the wait's bound reached |
| `truth-reaches-the-core` | krnl-small-s16x1 | the lowest bit of the last numerator written to the injector XORed into the core's every frame | `truth_isolation` | WORD at record 1 of the first wording (3/1): score 1890 where the model has 2160 |
| `writes-one-twice` | krnl-small-s24x3 | record 5's beat sent and sent again as the next | `identity_small` | WORD at record 6: index 5 where the model has 6 |
| `advertises-a-deeper-queue` | krnl-small-s24x3 | `cap_record_queue` reads twice the depth | `queue_overflow_refused` | `krn_records` 13 where the advertisement predicts 21 (5 taken and a queue of 16) |
| `advertises-a-longer-filter` | krnl-first, both profiles | a copy of `rtl/core/core.sv` reads `cap_taps` as one more | `capabilities_are_accepted` | "a shape at the advertised taps was refused SHAPE_TAPS", under each profile |
| `takes-one-tap-past-its-advertisement` | krnl-first, both profiles | a copy of `rtl/core/core.sv` takes a shape one tap past `cap_taps` | `capabilities_are_accepted` | "a shape past the advertised taps was refused none, not SHAPE_TAPS", under each profile |
| `buffer-taken-while-running` | krnl-small-s16x1 | `krn_buffer`'s lower word taken while a run goes | `refused_at_the_edge` | "krn_buffer word 0 while running: none" |
| `alignment-checked-above-bit-0` | krnl-small-s16x1 | the base's alignment checked on bits 4 to 1 only | `refused_at_the_edge` | "a base 1 byte(s) off: refused RUN_START, not BUFFER_ALIGN" |
| `bursts-after-an-error` | krnl-small-s16x1 | bursts still issued after an answer of SLVERR | `memory_error_refused` | "1 burst(s) offered after the error's answer at clock 1218" |
| `a-slot-skipped-after-a-burst-of-16` | krnl-first, both profiles | the next burst's address one slot on after a burst of 16 | `identity_long_bursts` | WORD at record 19, the pattern in the slot, under each profile: the first burst of 16 was slots 3 to 18 |
| `a-slot-skipped-after-a-burst-over-8` | krnl-first, both profiles | the same after any burst of more than 8 | `identity_long_bursts` | WORD at record 19, the pattern in the slot, under each profile |
| `wlast-early-in-a-burst-of-16` | krnl-first, both profiles | WLAST a beat early in a burst of 16 | `identity_long_bursts` | the memory model's faults "beat 17: WLAST 1 on beat 14 of 16" and "beat 35: ...", under each profile |
| `bursts-of-20` | krnl-first, both profiles | bursts of up to 20 beats | `identity_long_bursts` | the memory model's faults "burst 3: ... 18 beats" and "burst 4: ... 20 beats", under each profile |

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

**The first two links for the card failed in placement** (the lead's, 2026-11-24; the round's ledger, `lead.md`). Vivado could not place a chain of DSP blocks: "The height of the device or SLR DSP column is 110 DSPs". The first, on 955284c, used 730 DSPs and 324,425 LUTs in the kernel's synthesis. The lead read the chain as the core's one-stage sum of a row's 128 products and added `[vivado]` to `hw/link.cfg`, the kernel synthesis run's `CASCADE_DSP` set to `tree`, which builds sums of DSP outputs from fabric adders. That reading was wrong. The second link, on 3fa9b2b, had no PCIN chain left (729 DSPs, 329,695 LUTs) and met the same refusal, a chain beginning at `u_core/s2_prod_reg[128]`; the lead stopped it in placement. Both syntheses had carried the delay line `dl` through 127 DSP blocks' B cascade ports, BCOUT to BCIN (modes `(A*BCIN2)'` and `(A*BCIN'')'` in their DSP reports): one row of taps, one chain. Since the third link `dl` carries the synthesis attribute `keep` (`rtl/core/core.sv`), which holds it in the fabric's registers; Icarus Verilog ignores it, so nothing the benches hold changes. `CASCADE_DSP` stays `tree`. Whether the third link closes, and at what clock, is its record.

**The third link, on 31aaec1, closed at 100 MHz** (the lead's, 2026-11-24; K26 to K28). v++ ran 4 h 24 min and scaled nothing: the image carries DATA_CLK, the kernel's clock, at 100 MHz. The kernel's clock met timing with 0.122 ns to spare. Its worst path is not the sums of limit 2 of [core.md](core.md) but one wire: the pool's write pointer, `pool_wp`, fanned out to the write address of the pool's memory, which synthesis put in distributed RAM. That path is 99% route and has no logic level. The kernel's synthesis took 729 DSP slices and 329,499 LUTs, 196,089 of them as memory, about half of all the part's LUTs that can be memory (K29). The lead BELIEVES limit 19's pool is most of that memory; the report gives the kernel's total, not the pool's.

**Higher clocks did not close** (the lead's overnight sweep, on Logan's word, 2026-11-24 to 25; K30). The same commit linked at 150 MHz ran at 127.4 MHz, and at 200 MHz at 108.2: v++ lowers a clock that does not close. Each link failed on a different worst path: at 150, the platform's reset routed to the pool memory's write enables; at 200, a path of 26 logic levels from the shape's registers to the weight registers, which the lead BELIEVES is the core's checks on register writes. What lies behind each worst path is not known: the reports list the worst paths only. The card day's image is the third link's.

**The first packaging failed** (K20). The lead ran `hw/package_kernel.tcl` with Vivado 2022.2 on commit 29c843b. Vivado's IP packager read every port width and parameter default written with the package's names (`undertone_pkg::BUS_ADDRESS_BITS`, `undertone_pkg::MAX_POOL`) as a parameter named `undertone_pkg`. `ipx::package_project` failed, with 16 errors on eight ports, the address block and three defaults, and no `.xo` was made.

So **the top's parameter list and port list now hold plain numbers only**:
- the port widths 12, 32, 4, 256 and 32;
- the defaults 16, 1, 4, 128, 4, 65536, 31, 12, 31 and 512.

The body still uses the package. Each number is held to the definition twice:
- `tests/test_krnl_packaging.py` parses the top's header. It requires no name of the package there; it requires every port's width and the profile, pool and shift defaults to equal `spec/constants.py`'s, the other maxima to lie inside the definition's, and the queue to be a power of two.
- At elaboration, the top's initial block compares each port's `$bits` with the package's and stops the simulation by name if they part. Two widths changed by hand each stopped it so (K21).

`tests/test_krnl_packaging.py`, in the gate's first size, holds every number and name in the three files and the top's header to the definition, and is shown to report fourteen planted faults. **Whether Vivado now packages the top, and v++ links it, is not known here**: that is the lead's next run, in BUILD. *Restated by the lead on 2026-11-25:* it is known now. Vivado packages the top and v++ links it, as the paragraphs on the links above say.

## 8. What the card day can run

- **2^17 samples of stage E0's stream are certain.** Its at most 1,024 truth records all go into the injector before the start (the round's plan, L36).
- **2^20 samples can be tried.** It needs 7,168 more truth records written while the run goes: about 39,000 a second, five register writes each, so 195,313 writes a second, one every 5.1 us, for the run's 0.21 s at 100 MHz.
- How fast XRT's register writes go on this card nobody here has measured. The lead found that XRT 2.14's Python binding cannot reach a user-managed kernel's registers at all, and C++'s `xrt::ip` can (`lead.md`, 10:09).
- **Either way a run ends with every score word the model's, or with INJECT_OVERLAP and RUN_LENGTH by name.**

## 9. Limits

Each is stated by the behaviour it concedes.

1. **One simulator, nothing built.** Only Icarus Verilog 12.0 has read this RTL. Vivado's packager read the first version once and refused it for the package's names in the top's header (section 7). That cause is held now; whatever else the packager, synthesis or v++ cannot read is not seen here. That covers a construct Vivado will not elaborate, an interface the packager does not infer, or a protocol `package_xo` does not take from the XML. The test of the header holds the forms that failed and nothing else.
2. **User-managed rests on a reading.** Under ap_ctrl_hs XRT sends an argument image (READ, from the sibling's code); that it would write the words between this map's rows is BELIEVED and untested. Neither is held by anything here. The host side of user-managed (`xrt::ip`, the buffer's bank) is HOST's and the lead's.
3. **The overflow is held at a depth of 8, not 512.** A packaged kernel whose queue held fewer than 512 records while its `cap_record_queue` read 512 passes every test here: `capabilities_are_accepted` of `krnl-first` reads 512 from the register, not from the queue. That the register and the queue agree is held on the small top, by `queue_overflow_refused` and its mutant `advertises-a-deeper-queue`.
4. **No run is longer than 129 frames.** `krn_records`, `rec_in`, the source's count and the address are 64 bits. **A kernel whose counters wrapped at 256 passes**, as the foundation's README, limit 5, says of its index: one with `issued` and `krn_records` counted modulo 256 passed `identity_small` (K17). The upper words of `krn_records` and `krn_frames` are never non-zero in a run.
5. **Truth from the host at a long run's rate is not simulated.** No run here holds more than one truth record written while it runs, nor needs more than the injector's store of 1,024, which a run of 65,536 frames would.
6. **The memory model is this parcel's reading of AXI4**, cross-checked by `identity_on_axi_ram` against cocotbext-axi's `AxiRamWrite` once a profile. The rule it holds the kernel to, that a master raises neither valid waiting on a ready, is remembered and not read (K22). It imposes two orders a slave may impose: data only once its address is taken, always; an address only while data is offered, in the tests that ask. It never takes data before its address, so a kernel whose data needed to go first is not exercised. It never reorders answers. A master that broke the rule only for some bursts (those of more than one beat, say) is not planted: the tests in that mode would see it only if such a burst came in them.
7. **Done is polled every 12 clocks.** Done is sticky, so a done that rose is seen. What is held is that when it was first read every burst was answered, not the clock it rose at.
8. **The drain is 128 clocks**, twice the chain's latency of 63 by the blocks' documents. A drain too short ends a run before the chain's last records are out, and the run ends RUN_LENGTH with those slots unwritten. Which tests see a drain only a little short is measured, not argued:
   - a drain of 1 clock fails `identity_small` (K17);
   - drains of 30 to 66 clocks pass `identity_small`, and are caught by `truth_isolation`, `truth_while_running` and `reset_between_runs` (VKRNL, K25). *Restated by the lead at the merge, from VKRNL-2:* drains of 30 and 60 to 62 are caught by those three; drains of 63 to 66 pass all three and `identity_small` too, and are no fault, since 63 is the chain's latency.
   
   So a chain whose latency grew past 128 would be refused loudly by those tests, and not by every identity test.
9. **A record arriving at the edge that frees a slot of a full queue is refused.** The queue's count is read before that edge's beat leaves.
10. **After MEMORY_WRITE the queued records are abandoned.** `krn_records` counts only the records answered OKAY before the first error. One error test runs: the fourth burst answered SLVERR, three records late, while the memory holds its address and data so that records wait unissued. It holds that no burst is offered after the error's answer. A burst offered before the answer is still completed, as AXI requires, and is not counted.
11. **Up to 16 bursts may be unanswered**; no test asserts that sixteen ever were.
12. **The edge's refusals, the stall, the error, the chain's refusal, the reset and the truth during a run are held on the small top.** The kernel's lines there are the packaged top's, at other parameters. On the packaged top they are not run.
13. **A burst meeting a page's edge is held by `identity_small` and `identity_long_bursts`**, where holds make a burst of several beats end there. On the other tests the memory model's check holds the page rule on whatever bursts happen. Bursts of 9 to 16 beats are made by construction in `identity_long_bursts` alone.
14. **A record arriving with no run going** (RUN_LENGTH) is not reachable without a fault and is not run. Neither are an answer nobody asked for (MEMORY_WRITE) and a source that stops before its count.
15. **The stage's total counts most records twice.** A run held whole by `hold_run` counts each record once from memory and once as written. `identity_on_axi_ram`'s and the second run of `truth_while_running` are held from memory alone, and count once.
16. **A mutant shows the bench sees its fault under one profile**, but for the capability mutant, which runs under both. One mutant adds logic of its own, `truth-reaches-the-core` (a register and an XOR on one line). Its evidence is at the record it predicts (K6), which is what holds it.
17. **`advertises-a-longer-filter` edits RTL-B's file**, `rtl/core/core.sv`, as text inside the mutant. It stops applying when that line changes, and the stage then refuses it by name.
18. **The swap through the kernel is at one index**, in `identity_e0`: other gains of E0's shape, at index 80 under s16x1 and 50 under s24x3.
19. **The first build's pool memory is 65,536 entries** (the definition's `max_pool`) of 164 bits under s16x1, 10,747,904 bits, uncounted by the round's plan, which counts DSP slices. What it costs is the build's report's to say. *Restated by the lead on 2026-11-25:* the third link's synthesis put it in distributed RAM, in LUTs: the kernel used 196,089 LUTs as memory and no URAM (K29). That is why two copies of this kernel would not fit, and its write address was that link's worst path (K28). *Restated by the lead after the closing verifier:* "would not fit" is arithmetic, two copies needing 97.3 percent of the part's LUT memory before the platform's own (the ROADMAP's row R8, COMPUTED); no link of two copies was tried.
20. **The streams are short and the sigmas mostly small**, to keep the run time under four minutes (K4). The seam's sigma, a table of 459 entries, is run in one test, `identity_e0` under s16x1.
21. **A host can clear `krn_refusal` while a run goes**, by the rule every block's refusal register has. If it clears a refusal the run latched (RECORD_QUEUE, say), the run's end latches nothing more, since the run is halted. The run then ends with `done` and a refusal of 0, and only `krn_records` against `krn_frames` says it was short. A host reads `krn_records` after every run; nothing here holds that it does (VKRNL, K25).
22. **The routing of writes to one block is not observable by any bench.** Each block decodes its own range and does nothing outside it, so a kernel that sent every write to all three blocks, as the seam's top does, would pass everything here. That the truth rows never reach the core's port rests on the RTL's reading (`hit_core` and its two siblings in `undertone_krnl.sv`), not on a test (VKRNL, K25).
23. **The edge's refusals are tried word by word, and the gate by trial**, as section 6 says. While a run goes, every word of the three arguments, `krn_start` and `krn_reset` are tried. The base is tried 1, 2, 4, 8 and 16 bytes off. Only `cap_blob_versions`, `cap_inject_pending` and, on the large tops, `cap_record_queue` are read without trial. *Restated by the lead at the merge, from VKRNL-2:* and `cap_rows` under `s16x1`, where a filter is one row (section 6 says so). And `identity_w_before_aw`, on the small tops, makes only one-beat bursts; the memory model's mode is held for longer bursts by `identity_e0` and `identity_long_bursts` on the packaged top.

## 10. Register

"The stage on a copy" is `python tools/check_rtl.py rtl-benches --root <a copy> --state <a folder>`, where the copy is this tree's `spec`, `model`, `learn`, `rtl`, `tools`, `docker` and `vectors` with a manifest of this parcel's four rows alone. The copies are in the round's folder, `scratch/KRNL`, which is not in the tree.

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| K1 | A score record is 168 bits, 21 bytes, in a slot of 32: 11 bytes of zeros after it | READ | `spec/undertone.toml`, `[records]` and `[memory]` | the definition |
| K2 | A queue of 512 covers a memory that takes nothing for 10,240 clocks (102.4 us at 100 MHz) under s16x1 and 30,720 under s24x3 | COMPUTED | 512 x 20 and 512 x 60 clocks a record (the plan, L12); 10,240 x 10 ns | arithmetic |
| K3 | On a copy holding this parcel's four rows, the stage passed: 36 tests in 6 runs of 4 benches, 2,728 records identical to the model's, 24 mutant runs each failed as named, 30 build logs read and the 60 lines in them each on the committed list | MEASURED | the stage on a copy, 2026-11-24 11:45:09 to 11:46:01, with every test and mutant of this page: its OK line | the gate's second size, whose line for the stage holds these rows' with the others' |
| K4 | The thirty runs of those rows took 198 s summed, each run's own time by the runner's count, six side by side; the longest was 24 s, `krnl-small-s24x3.s24x3`. An earlier run of sixteen of them, on a busier desktop (10:38), summed to 223 s, its longest 37 s | MEASURED | the same run of the stage: its `runner.log`, the lines "ran ... in N s", added; the earlier, that run's | another run; another load |
| K5 | cocotb's own count of the simulated nanoseconds a wall second, for each run's whole test list, was 16,462 and 15,372 on `krnl-first` (s16x1, s24x3), 10,761 and 10,884 on `krnl-max`, 17,282 and 25,665 on `krnl-small`: about 1,000 to 2,600 clocks a second at 10 ns, the AXI4-Lite writes that load each run among them | MEASURED | the same run: the TESTS line of cocotb's summary in each run's log | another run; another load |
| K6 | Each of the twenty-four mutant runs failed at the record and field section 6's table gives | MEASURED | the same run: each mutant run's log, read for its failure; the ten first mutants' evidence is the same as at 10:38, when the writer waited for AWREADY | the gate's second size: each fails as named there; its place is in its evidence |
| K7 | The packaging and the top's header agree with the definition, and the check reports each of fourteen planted faults | MEASURED | `python -m pytest -q -p no:cacheprovider tests/test_krnl_packaging.py`, 2026-11-24 11:08: 2 passed | that command |
| K8 | A run of 2^20 samples at 100 MHz under s16x1 lasts 0.21 s and needs 7,168 truth records written while it runs, 195,313 register writes a second | COMPUTED | 1,048,576 x 20 / 1e8; the plan, L36 and L37: 8,192 - 1,024; 5.0e6 / 128 x 5 | arithmetic |
| K9 | The first build's pool memory is 10,747,904 bits under s16x1 | COMPUTED | 65,536 entries x 4 filters x 41 bits; 41 is `W_RECT` of `rtl/core/core.sv` line 86 at 16-bit samples, 1 row a filter and 128 taps: 32 + 8 + 1 | the build's utilisation report |
| K10 | XRT's start of an ap_ctrl_hs kernel sends every declared argument's word, a zero for one not set | READ | `<repos>/cft-fp256/host/src/backend_xrt.cpp`, line 281, the sibling project's own record | a host trial of an ap_ctrl_hs kernel whose arguments are set apart |
| K11 | XRT writes the words between two arguments as well | BELIEVED | nothing: no one here has read XRT's source on it or tried it | a hardware emulation trial that reads back a word between two arguments |
| K12 | The source does nothing, and latches nothing, on a start while its own refusal is latched | READ | `rtl/source/source.sv`, line 227 | that file |
| K13 | The chain's last record comes 52 + 11 = 63 clocks after the source's last frame; the kernel's drain is 128 | READ | seam.md, row K3; `rtl/krnl/undertone_krnl.sv`, `DRAIN` | `identity_*` ending in RUN_LENGTH |
| K14 | XRT 2.14's Python binding has no `ip` class and cannot reach a user-managed kernel's registers; C++'s `xrt::ip` can | READ | the round's ledger, `lead.md`, entry 10:09, the lead's trial in `cft2204` | a trial on the box's XRT |
| K15 | The first build's depth of 512 is a DECISION of this parcel's, approved by the lead; no measurement of the card's memory stalls exists here | DECISION | the round's ledger, `KRNL.md` 09:44:33, section 3; `lead.md` 09:52 | the card day's `krn_queue_peak` |
| K16 | With these rows the gate's second size passed: the stage `rtl-benches` 200 tests in 20 runs of 17 benches, 66,298 records identical to the model's, 106 mutant runs each failed as named, 126 build logs read, in 202 s; before these rows it was 172 tests, 63,946 records, 96 mutant runs and 110 build logs, so these rows add 28 tests, 2,352 records, 10 mutant runs and 16 build logs, K3's figures. The verdict named one inner skip, E1-RECORD-STALE | MEASURED | `bash verify/run.sh --with rtl`, run 20261124-104407-655d303, 2026-11-24 10:44:05 to 10:52:15, on this parcel's tree before this row was written: its line for `rtl-benches` and its verdict line; the earlier figures are the round's ledger, `lead.md`, entry 09:56, for 28358e0 | that command |
| K17 | Nine faults tried by hand, on the writer of commit 29c843b, which waited for AWREADY: eight failed the test named for them where section 6's second table says; the ninth, counters modulo 256, passed `identity_small` | MEASURED | the stage on a copy with the row `krnlx-s16x1` and nine mutants, 2026-11-24 10:52:59 to 10:53:16: "1 finding(s)", that finding "MUTANT-SURVIVED" for the ninth, and each other run's log read; the rows are `scratch/KRNL/extra.toml` | nothing in the tree: these mutants are not in the manifest |
| K18 | A run of 2^17 records is 4 MiB of slots and one of 2^20 is 32 MiB | COMPUTED | 131,072 x 32 = 4,194,304 bytes; 1,048,576 x 32 = 33,554,432 bytes | arithmetic |
| K19 | The model's noise table at the seam's sigma of 50 under s16x1 has 459 entries; at the benches' small sigmas, 56 under s16x1 (6) and 60 under s24x3 (13/2) | MEASURED | `python -c "from model import source; print(len(source.Noise('s16x1', 2026112470, 50, 1, 129).table), len(source.Noise('s16x1', 1, 6, 1, 10).table), len(source.Noise('s24x3', 1, 13, 2, 10).table))"`, 2026-11-24: 459, 56, 60 | that command |
| K20 | Vivado 2022.2's IP packager, on the top of commit 29c843b, read `undertone_pkg::NAME` in a port width or a parameter default as an undefined parameter named undertone_pkg: 16 errors (eight ports, the address block reg0 twice, three defaults as user and HDL parameters), `ipx::package_project` failed, no `.xo` | READ | the round's ledger, `lead.md`, entry 11:06, the lead's run in `cft2204`; its whole output is the round's folder's `data/P0-3/krnl_trial1.txt` | the lead's run of the packaging on this commit |
| K21 | With a port's width in the top's header parted from the package's (the slave's read address of 13 bits; the master's data of 512 bits), the simulation stopped at elaboration: "undertone_krnl: a port's width written in the port list is not the definition's" | MEASURED | the stage on a copy with the row `krnly` and those two mutants, 2026-11-24 11:09:23 to 11:09:36: "2 mutant run(s) each failed as named", each run's log a FATAL from `undertone_krnl.sv` with that message; the rows are `scratch/KRNL/extra2.toml` | nothing in the tree: these mutants are not in the manifest |
| K22 | AXI4, section A3.3.1: a master must not wait for AWREADY or WREADY before raising AWVALID or WVALID; a slave may wait for AWVALID or WVALID, or both, before raising AWREADY, and likewise before raising WREADY | BELIEVED | remembered by this parcel, by the verifier VKRNL and by the lead; the specification was not read on 2026-11-24 | AMD's or Arm's AXI4 specification, section A3.3.1 |
| K23 | The writer of commits a0e443b to bf7fa06 raised WVALID only after AWREADY. With `krnl_mem` changed only so that AWREADY waits for WVALID, every test of `krnl-small-s16x1` hung: no beat taken, the queue full, done never raised | READ | the round's ledger, `lead.md`, entry 11:22, VKRNL's measurement on a copy | the mutant `w-waits-for-the-address`, which plants that writer and fails `identity_w_before_aw` at its bound (section 6) |
| K24 | With `cap_coeff_bits` read as one more, `capabilities_are_accepted` failed: "weights at the advertised coefficient's ends were refused WEIGHT_RANGE"; with `cap_noise_table` read as one more: "a table of the advertised 32768 entries was refused NOISE_RANGE"; and with `cap_taps` one more, `the_first_builds_maxima` failed on its own comparison | MEASURED | the stage on a copy with the row `krnlz` and those three mutants, 2026-11-24 11:46:18 to 11:46:28: "3 mutant run(s) each failed as named", each log read; the rows are `scratch/KRNL/extra3.toml` | nothing in the tree: these mutants are not in the manifest |
| K25 | The verifier VKRNL found, on commit 29c843b: no burst of more than 8 beats in any bench; the capability control failing on the bench's literal maxima alone; KERNEL_BUSY tried on one word, BUFFER_ALIGN on one offset, and no burst after MEMORY_WRITE held only as fewer bursts than frames; identity_on_axi_ram's done check unable to fail; drains of 30 to 66 clocks passing identity_small; a host's clear of krn_refusal during a run; the routing of writes unobservable | READ | the lead's message to this parcel of 2026-11-24, VKRNL's report in substance (the round's folder, `reports/VKRNL.md`) | that report |
| K26 | The third link, of commit 31aaec1 at 100 MHz asked, made an image of 45,567,801 bytes, SHA-256 fce0e2397f16407d37fae71bef8f691c9a534eb2e787786aa63942eee5c6c685; v++ reported "Total elapsed time: 4h 23m 50s" | MEASURED | the round's ledger, `lead.md`, entry 18:02 of 2026-11-24: v++'s log and `sha256sum` on the box | the image on the box |
| K27 | The image carries the kernel's clock, DATA_CLK, at 100 MHz, and KERNEL_CLK, another clock of the platform's, at 500 MHz; its info file says of `ulp_ucs_aclk_kernel_00` "Requested Freq: 100 MHz", "Achieved Freq: 100 MHz" | MEASURED | `xclbinutil --info` on the image, on the box, 2026-11-25 06:0x (the round's ledger, `lead.md`, entry 06:07); v++'s `undertone_hw.xclbin.info` | `xclbinutil --info` on the image |
| K28 | Routed, the kernel's clock `clk_kernel_00_unbuffered_net` met with WNS 0.122 ns, TNS 0, over 1,695,906 endpoints, WHS 0.010 ns. Its worst path: `u_core/pool_wp_reg[5]/C` to `u_core/pool_mem_reg_12608_12671_0_6/RAMA/WADR5`, requirement 10.000 ns, data path 9.628 ns, "logic 0.079ns (0.821%) route 9.549ns (99.179%)", 0 logic levels. The design's own worst slack, 0.055 ns, is on a clock of the platform's | MEASURED | the link's `hw_bb_locked_timing_summary_routed.rpt`, read on the box (the round's ledger, `lead.md`, entry 18:02 of 2026-11-24) | that report |
| K29 | The kernel's synthesis: 329,499 LUTs (37.80%), 196,089 of them as memory (48.63% of the part's LUTs that can be memory), 729 DSP slices, 58 block RAM tiles, 0 URAM. The whole routed design: 453,752 LUTs (52.11%), every DSP in SLR0 | MEASURED | the link's utilisation reports, read on the box (the round's ledger, `lead.md`, entry 04:10 of 2026-11-25) | those reports |
| K30 | The same commit linked at 150 MHz ran at 127.4 MHz, WNS -1.177 ns at 6.667, its worst path from the platform's kernel reset (`proc_sys_reset_kernel_slr0`) to `u_core/pool_mem_reg_512_575_0_6`'s write enables, 7.691 ns, 96% route, 4 logic levels; at 200 MHz it ran at 108.2 MHz, WNS -4.242 ns at 5.000, its worst path from `u_core/shp_filters_reg[7]` to `u_core/hid_b_reg[688]`, 9.218 ns, 79% route, 26 logic levels | MEASURED | each link's `undertone_hw.xclbin.info` ("Achieved Freq") and `hw_bb_locked_timing_summary_routed.rpt`, read on the box (the round's ledger, `lead.md`, entries 03:51 and 05:45 of 2026-11-25) | those files |
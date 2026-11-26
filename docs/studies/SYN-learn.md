# What the learner costs: an out-of-context synthesis

Round 5 put phase B's learner into RTL beside the core, in simulation only (`docs/rtl/learn.md`). That page's section 8 counts the learner's storage and arithmetic, and claims no LUT and no clock. The round's plan asked for the cost to be measured: "the learner synthesised out of context, as the head was in round 2, for its LUTs, DSP slices and memory against L12's room" (`docs/plans/R5-learning-in-fabric-and-real-noise.md`, "Track A: learning in the fabric, in simulation"). This page is that measurement, made on the pattern of `docs/studies/SYN-head.md`.

**This page reports a synthesis and nothing more.** The learner was synthesised out of context, for the card's part, with a utilisation report. There was no implementation, no placement and no timing, so nothing here says the learner meets any clock. The learner is in no kernel and no image (learn.md, section 7), and nothing was put on the card.

## The result

**Under s16x1, the profile of the image on the card, the learner is 19,070 look-up tables, 26,571 registers and 12 DSP slices, with no block RAM.** Under s24x3 it is 74,618 look-up tables, 87,896 registers and 12 DSP slices.

| what was synthesised | DSP slices | look-up tables | of them as memory | registers | CARRY8 | F7 muxes | F8 muxes | block RAM tiles |
|---|---|---|---|---|---|---|---|---|
| `learn`, 16-bit one channel | 12 | 19,070 | 3,814 | 26,571 | 391 | 5,192 | 2,498 | 0 |
| `learn`, 24-bit three channels | 12 | 74,618 | 3,942 | 87,896 | 435 | 25,899 | 11,592 | 0 |
| `learn_port`, the learner's register port | 0 | 52 | 0 | 0 | 0 | 0 | 0 | 0 |

None of the three uses URAM. Each `learn` build is at the definition's values in all but the sample format:
- 128 taps;
- counts of 32 bits;
- an update every 256 frames;
- a truth store for 1,024 records and 4 more.

## Against the room

- **The room.** Round 3's third link synthesised the kernel alone at 329,499 look-up tables, 196,089 of them as memory, and 729 DSP slices (`docs/ROADMAP.md`, row R7; `docs/rtl/krnl.md`, row K29). That image's one profile is s16x1 (`docs/studies/CARD-first-light.md`, limit 2).
- **With the learner and its port added, under s16x1:**
  - 348,621 look-up tables: 39.99 hundredths of the chip's 871,680, against the kernel's 37.80 alone;
  - 199,903 of them as memory: 49.58 hundredths of the 403,200 that can be memory, against 48.63;
  - 741 DSP slices of 5,952: 12.45 hundredths, against 12.25.
  
  These sums add two syntheses made separately. They are not a synthesis of the two together (limit 2).
- **The learner alone, against the card:**
  - its DSP slices are 0.20 hundredths of the card's;
  - its look-up tables are 2.19 hundredths under s16x1 and 8.56 under s24x3;
  - its registers are 1.52 and 5.04 hundredths of the card's 1,743,360.
- **There is no sum for s24x3.** That profile is not on the card, and the kernel was never synthesised under it.

## What the counts suggest

These are readings of the totals. The netlist was not read, and the hierarchical report has one level, the module itself.
- **The truth store is not in registers or block RAM.** Section 8 counts 24,576 bits of sums and copy under s16x1 and 86,016 under s24x3. The registers exceed those counts by only 1,995 and 1,880. The truth store's 65,792 bits therefore cannot be in registers, and no block RAM tile was used. Section 8 left open whether the store would be made of LUTs or of block RAM, and the answer here is not block RAM. The lead reads it as held in the 3,814 and 3,942 look-up tables used as memory, with the delay buffer, and the sums and the copy as the registers. That reading is BELIEVED.
- **The growth from s16x1 to s24x3 is mostly multiplexers.** Look-up tables grow 3.9 times, F7 muxes 5.0 times and F8 muxes 4.6 times. The sums grow 3.5 times in bits: 384 sums of 56 bits against 128 of 48. That the growth comes from the multiplexers that pick one sum, or one copied sum, by its index is BELIEVED.
- **The DSP slices are 12 under both profiles.** Section 8 counts two multipliers, of 48 × 32 and of 56 × 32 bits. How the 12 slices divide between them was not read.

## How it was run

- **The machine and the tool:**
  - the Linux box, `amd-arc-box`, booked on the TimeSheet as shared (B0400) inside the box-shared night window of the project that holds standing bookings there, with that project's word;
  - Vivado v2022.2, part `xcu50-fsvh2104-2-e`;
  - `synth_design -mode out_of_context`, with `-generic SAMPLE_BITS=...` and `-generic CHANNELS=...` for `learn` and no parameter for `learn_port`, then `report_utilization` flat and hierarchical;
  - at most 4 threads, at nice 19.
- **When:** 2026-11-26, 00:07:12 to 00:25:41 by the box's clock. The three runs went one after another and each ended with exit code 0. `synth_design` took 7 min 06 s, 9 min 35 s and 29 s of elapsed time.
- **The sources:**
  - `rtl/learn/learn.sv` and `rtl/learn/learn_port.sv` as they stood at parcel RTL-L's commit `8c19f98`;
  - `spec/undertone_pkg.sv` as it stood at `e5e8b08`.
  
  Each file had the same SHA-256 on the box as on the lead's desktop and in the tree this page is committed in (row SL7).
- **What was kept:** the script that drove Vivado and the box's wrapper around it are the lead's, kept in the round's folder and not in the tree. The six reports and four logs were copied there and are not committed. Each copy has the same SHA-256 as its original on the box. The folder made on the box was then removed.

## The tool's warnings

- **48 of Synth 8-7129, the same under both profiles,** for bits 8 to 31 of the port `core_taps`, each bit named twice. The learner reads only the low 8 bits of that 32-bit bus word, since a count of taps up to 128 needs 8 (`TB`, `$clog2(129)`).
- **71 of Synth 8-6014, the same lines under both profiles,** each an "unused sequential element ... removed". Each one names a variable assigned with a blocking `=` inside the clocked block, at the line the warning gives, so none of them makes a register. The lead checked by script that each of the 71 lines assigns that name with `=`.
- **One Netlist 29-101** under each profile (a flat netlist is not ideal for floorplanning), and **one Synth 8-7080** (the criteria for parallel synthesis are not met) under s16x1 and for the port.
- There was no critical warning and no error.

## Limits

1. **No timing.** The divider takes one restoring step a clock, and the sums are added and compared in this RTL's stages as they are. Nothing here says the learner closes at 100 MHz or at any clock. If a build needs more pipeline stages, it has more registers and the same multipliers.
2. **Out of context.** The module was synthesised alone, its inputs free. In the kernel, the tool may share, trim or duplicate logic. The sums with the kernel's figure add two different runs: this script's `synth_design`, and v++'s synthesis inside round 3's link with its own strategy.
3. **One tool, one version, the default strategy.**
4. **Where each array went is BELIEVED.** The netlist was not read, and the report's hierarchy has one level.
5. **The learner's ports are free here.** In the simulation tops the learner reads state of the core and the injector by hierarchical name (learn.md, limit 3). The ports a later round must add to `core.sv` and `inject.sv` for that (learn.md, section 7) are not counted, nor is the read path's OR in the kernel.
6. **The kernel was never synthesised under s24x3,** so the learner's cost under that profile has no kernel to sit beside.

**Whether the learner goes into the kernel, and at which profile, is a later link's question and Logan's decision.** This page measures and decides nothing.

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| SL1 | `learn` under `s16x1` is 12 DSP slices, 19,070 look-up tables (3,814 as memory), 26,571 registers, 391 CARRY8, 5,192 F7 and 2,498 F8 muxes, and no block RAM or URAM; under `s24x3` 12, 74,618 (3,942), 87,896, 435, 25,899, 11,592 and none | MEASURED | Vivado v2022.2, `synth_design -top learn -part xcu50-fsvh2104-2-e -mode out_of_context -generic SAMPLE_BITS=... -generic CHANNELS=...`, then `report_utilization`; 2026-11-26, on the box | the same command on the same files |
| SL2 | `learn_port` is 52 look-up tables and nothing else | MEASURED | the same, `-top learn_port`, no generic | the same |
| SL3 | The card has 871,680 look-up tables, 403,200 that can be memory, 1,743,360 registers and 5,952 DSP slices | READ | the "Available" column of each utilisation report | the part's data sheet |
| SL4 | The kernel alone after synthesis in round 3's third link: 329,499 look-up tables, 196,089 of them as memory, 729 DSP slices, under `s16x1` | READ | `docs/ROADMAP.md`, row R7; `docs/rtl/krnl.md`, row K29; `docs/studies/CARD-first-light.md`, limit 2 | those reports |
| SL5 | 329,499 + 19,070 + 52 = 348,621, which is 39.99 hundredths of 871,680; 196,089 + 3,814 = 199,903, which is 49.58 hundredths of 403,200; 729 + 12 = 741, which is 12.45 hundredths of 5,952; the learner alone is 2.19 and 8.56 hundredths of the look-up tables, 1.52 and 5.04 of the registers, and 0.20 of the DSP slices | COMPUTED | SL1 to SL4 | arithmetic |
| SL6 | The registers exceed section 8's sums and copy (24,576 and 86,016 bits) by 1,995 and 1,880, fewer than the truth store's 65,792 bits | COMPUTED | SL1; `docs/rtl/learn.md`, row L7 | arithmetic |
| SL7 | `rtl/learn/learn.sv`, `rtl/learn/learn_port.sv` and `spec/undertone_pkg.sv` in the tree this page is committed in have the SHA-256 of the files synthesised: 797954c1..., bd3c106c... and edb24062... | MEASURED | `sha256sum` of each in the tree, against the box's own listing at the run's start | that command |
| SL8 | Each of the 71 elements Synth 8-6014 names is assigned with a blocking `=` at the line it gives, and the 71 are the same under both profiles; the 48 lines of Synth 8-7129 name bits 8 to 31 of `core_taps`, the same under both | MEASURED | the two logs, read by a script of the lead's against `rtl/learn/learn.sv`; `diff` of each warning's lines between the two logs | the logs |
| SL9 | The truth store and the delay buffer are the look-up tables used as memory, the sums and the copy are the registers, and the growth from `s16x1` to `s24x3` is the multiplexers that pick one sum by its index | BELIEVED | the totals of SL1 against section 8's counts; no netlist was read | a read of the synthesised netlist |

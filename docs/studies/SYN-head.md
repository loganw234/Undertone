# What the head costs: an out-of-context synthesis

Round 2 gave the detector's head a hidden layer "if simple enough", and the test for simple enough counted multipliers: twelve hidden units make the head 204 multipliers, against a tenth of the filter bank's 2,048, which is 204.8 (`docs/model/head.md`, row HD7). Logan asked for a synthesis, to measure the real cost. This page is that measurement.

**It is a synthesis and nothing more.** Out of context, for the card's part, with a utilisation report. No implementation, no placement, no timing: nothing here says the head meets any clock. Nothing was put on the card.

## The result

**At twelve hidden units the head is 624 DSP slices under 16-bit one-channel samples and 816 under 24-bit three-channel samples.** The card has 5,952.

| what was synthesised | DSP slices | look-up tables | registers | CARRY8 |
|---|---|---|---|---|
| the head, 12 hidden units, 16-bit one channel | 624 | 23,407 | 15,493 | 2,227 |
| the head, 12 hidden units, 24-bit three channels | 816 | 26,330 | 17,221 | 2,503 |
| the same, both weight banks at its ports, 16-bit | 624 | 25,082 | 15,519 | 2,227 |
| the same, both weight banks at its ports, 24-bit | 816 | 28,259 | 17,247 | 2,503 |
| the head, 4 hidden units, 16-bit | 208 | 8,062 | 5,208 | 735 |
| the head, 4 hidden units, 24-bit | 272 | 9,062 | 5,784 | 827 |

The first, second, fifth and sixth rows are the head with its two weight banks given the same wires, so that the choice between them costs nothing; the third and fourth are the module as it is in the tree, where each frame's own select bit picks a bank. The difference is the muxes: about 1,700 and 1,900 look-up tables, and no slice.

And one multiplier alone, registered in and out, a coefficient of 18 bits by:

| the other operand's bits | 16 | 24 | 40 | 44 | 48 | 53 | 57 | 65 | 66 |
|---|---|---|---|---|---|---|---|---|---|
| DSP slices | 1 | 1 | 2 | 2 | 3 | 3 | 3 | 4 | 4 |

16 and 24 are a filter tap under each sample format. 57 and 66 are a hidden weight by a pooled value at the definition's maxima under each format. 65 is a head weight by a hidden value after its magnitude is taken. 40 to 53 are widths the head does not have today.

## What it means for "simple enough"

- **The slices are what the arithmetic said.** A head of twelve units is 192 hidden multipliers and 12 output multipliers. At 3 and 4 slices each: 192 x 3 + 12 x 4 = 624. At 4 and 4: 816. The lead worked those two figures from four single multipliers before any head existed in RTL; the synthesis of the whole head gives the same two, to the slice.
- **In slices the head is three to four tenths of the filter bank, not one.** The bank at the definition's maxima is 2,048 multipliers of 18 by 16 or 18 by 24, one slice each by the table above: 2,048, COMPUTED, since no bank was synthesised. 624 is 30 hundredths of that and 816 is 40. The count of multipliers made it a tenth because it counted a wide multiplier as one.
- **Against the card**: the head is 10.5 hundredths of the DSP slices under 16-bit samples and 13.7 under 24-bit; with the bank, 2,672 and 2,864 of 5,952, which is 45 and 48 hundredths. In look-up tables the head is about 3 hundredths of the card's 871,680.
- **What would bring it to a tenth of the bank in slices**: four hidden units under 16-bit samples, 208 of 2,048. Or a narrower pooled value: a multiplier is 2 slices at 44 bits and 3 at 48, and the pooled value is 57 and 66 bits because the definition lets a pool be 65,536 long over 128 taps. At 44 bits or fewer a head of twelve units would be 192 x 2 + 12 x 4 = 432, COMPUTED. That is a smaller bound in the definition, and a change to the model, which is the authority.

**Which of these is taken, or none, is Logan's.** This page measures; it decides nothing.

## How it was run

- **The machine and the tool:** the Linux box, `amd-arc-box`, booked on the TimeSheet as shared; Vivado v2022.2; part `xcu50-fsvh2104-2-e`; `synth_design -mode out_of_context`; at most 4 threads, under nice. 2026-11-23, 18:04:30 to 18:22:45, eleven runs, each ending with exit code 0.
- **The head** is `rtl/core/core_head.sv`, parcel RTL-B's, with `spec/undertone_pkg.sv`, both as they stood at that parcel's commit `c90cc45c8ba4dbd2bda8d3b1e9e20f152c91fb7e`. Its parameters were left at the definition's maxima but for the sample format and, in the last two rows, the count of hidden units. **That commit was before the parcel's verifier had finished; the parcel's later commits change no line under `rtl/core/`** (register row Y6).
- **The tied form** is a wrapper of the lead's, not in the tree, that hands both banks' ports the same weights and holds the select at 0.
- **One multiplier alone** is a module of the lead's, not in the tree: two input registers, a signed product, an output register.
- The reports are kept in the round's folder with their SHA-256 and are not committed; the six files sent to the box had the same SHA-256 there as on the lead's desktop. The folder made on the box was removed.

## Limits

1. **No timing.** A unit's sum of sixteen products, its shift and its comparison are one stage in this RTL, and a product of 18 by 66 bits is four slices (Y4); that the four are cascaded is the lead's reading of the count, BELIEVED, not read from a netlist. Nothing says that closes at any clock. A build that needs more pipeline stages has more registers and the same multipliers.
2. **Out of context.** The module was synthesised alone, its inputs free. In a whole design the tool may share, trim or duplicate logic, and constants at the ports (a build with fewer units, a fixed shift) would shrink it. The figures are for the head with every weight and every pooled value a free input.
3. **One tool, one version, default strategy.** Another version or another setting may infer the multipliers otherwise.
4. **The filter bank, the pool and the weight store were not synthesised.** The bank's 2,048 is one slice a multiplier by arithmetic. The two banks of weights are 40,536 register bits each by the parcel's count; the pool's memory is in `docs/model/mod-b.md`.
5. **45, 46 and 47 bits were not measured**: where between 44 and 48 a multiplier goes from two slices to three is not placed.
6. **A multiplier alone has two input registers and one output register**, which the tool may take into the slice; the head's multipliers sit in other logic. That the head's total equals the sum of its multipliers taken alone is measured for these two builds and is not a rule.

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| Y1 | The head at twelve hidden units is 624 DSP slices under `s16x1` and 816 under `s24x3`, with the look-up tables, registers and carries of the table | MEASURED | Vivado v2022.2, `synth_design -top syn_head_tied -part xcu50-fsvh2104-2-e -mode out_of_context -generic SAMPLE_BITS=... -generic CHANNELS=...`, then `report_utilization`; 2026-11-23, on the box | the same command on the same files |
| Y2 | With both banks at its ports the head is the same slices and 25,082 and 28,259 look-up tables | MEASURED | the same, `-top core_head` | the same |
| Y3 | With four hidden units: 208 and 272 slices | MEASURED | the same as Y1 with `-generic B_HIDDEN=4` | the same |
| Y4 | One multiplier of 18 bits by 16, 24, 40, 44, 48, 53, 57, 65 and 66 is 1, 1, 2, 2, 3, 3, 3, 4 and 4 slices | MEASURED | the same tool and part on a module of one registered signed multiplier, nine runs, four of them earlier the same day | the same |
| Y5 | The card has 5,952 DSP slices and 871,680 look-up tables | READ | the "Available" column of each utilisation report | the part's data sheet |
| Y6 | No line under `rtl/core/` differs between the commit that was synthesised and the tree this page is committed in | MEASURED | `git diff c90cc45c8ba4dbd2bda8d3b1e9e20f152c91fb7e HEAD -- rtl/core spec/undertone_pkg.sv`, which prints nothing | that command |
| Y7 | 192 x 3 + 12 x 4 = 624 and 192 x 4 + 12 x 4 = 816; 2,048 + 624 = 2,672 and 2,048 + 816 = 2,864; 624 / 2,048 = 0.30 and 816 / 2,048 = 0.40; 624 / 5,952 = 0.105 and 816 / 5,952 = 0.137; 2,672 / 5,952 = 0.45 and 2,864 / 5,952 = 0.48 | COMPUTED | Y1, Y4, and twelve units of sixteen filters from the definition | arithmetic |
| Y8 | The filter bank at the definition's maxima is 2,048 slices | COMPUTED | 16 filters of 128 taps, one multiplier a tap, one slice a multiplier by Y4. No bank was synthesised | a synthesis of the bank |
| Y9 | At a pooled value of 44 bits or fewer a head of twelve units would be 432 slices | COMPUTED | 192 x 2 + 12 x 4, from Y4. No such head was synthesised | a synthesis of it |

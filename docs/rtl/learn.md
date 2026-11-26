# The learner of phase B, in RTL

Parcel RTL-L, round 5, 2026-11-25. D0's phase B learner, the difference of two class means, in SystemVerilog beside the detector core, held to the reference model's `model/learner.py` ([lrn-b.md](../model/lrn-b.md)) word for word, **in simulation only**, under both sample formats. How the RTL side works at all, the harness, the manifest and the gate's second size, is [README.md](README.md).

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure here has a row in the register at the end.

**What rests on what.** Everything here is bit identity: the design's score records and register words against the model's, on the streams the benches run. **Nothing here is evidence about sensitivity**, which has its own authority, `stats/`, and nothing here is synthesised. D0's gate "learner", restated by the round's plan (question 4, approved by Logan): the fabric's set after each update, and the counts of windows taken and refused and of updates refused for time, each equal to the model's. Its row in `tests/gates.toml` is the stage `rtl-benches`, where these benches run.

## 1. Where things are

| what | where |
|---|---|
| the learner, a module whose every output is a register | `rtl/learn/learn.sv` |
| the core's register port shared by the host and the learner: a few gates | `rtl/learn/learn_port.sv` |
| a small core and the learner, frames and truth from the bench | `rtl/learn/learn_small.sv` |
| the seam's chain with the learner at the definition's bounds | `rtl/learn/learn_chain.sv` |
| the benches | `rtl/tb/bench_learn.py`, `rtl/tb/bench_learn_chain.py` |
| what they share: the model's run, the design's run of the same script, the checks | `rtl/tb/learn_host.py` |
| their rows and 66 mutants | `rtl/tb/benches.toml`, from the line that names this parcel |

## 2. What it does

For a truth record at j, with p the record before it and q the one after, and T the core's running taps (LRN-B's design, sections 0 to 4):

- **label 0**, frames j−T..j−1, judged when the core's next index is j; skipped START (j < T), BUSY (j − p < 2T), FULL (its count at its most), in that order;
- **label 1**, frames j..j+T−1, judged when the next index is j + T; skipped BUSY (j − p < T, or q − j < T), FULL;
- **the update**, named by the host's write of `lrn_update_at`'s upper word for an index u: D[c][k] = S1[k][c]·n0 − S0[k][c]·n1 from the sums as they stand at u, quantised over the whole set (peak to COEFF_MAX, half to even), written with a head weight of 1 into the core's shadow;
- **finished** when the next index is u + F, F = `LEARN_UPDATE_FRAMES`, 256, and every one of the learner's writes has been taken. Until then a commit, a shadow write and another update are refused, UPDATE_UNFINISHED; then the host commits through the core's own commit.

### 2.1 Where it sits, and how it reaches the shadow

**The shadow through the core's own register port.** The learner writes `shadow_begin` and then T × C + 1 words of `shadow_data` there, so the core's loader puts each word where a host's would go, and no line of `core.sv` changes. `learn_port` shares the port: it passes every host access but one held back, and in a clock with no host access passed it carries the learner's write. **A passed host access always wins the port, a read above all**, since every block's `reg_rdata` must answer that read for the bus's OR to hold. While an update is unfinished, judged as the frame at that edge leaves the core's next index, the host's write of `commit_at`'s upper word, of `shadow_begin` or of `shadow_data` is held back: it reaches no block, and the learner latches UPDATE_UNFINISHED in **`lrn_refusal`**; a commit also counts `lrn_early`. The core's own register reads 0 for it.

*How this differs from LRN-B's design:* its section 8, item 2 has a refusal read back in "the refusal register of that write's block", which for a commit would be the core's. The core cannot latch a name it does not compute without a change to `core.sv`, so the lead ruled (2026-11-25 22:00) that the learner's name is latched in the learner's register, whatever row the held write was to.

**The core never refuses the learner's writes,** by construction: an update is taken only under the matched shape, so `shadow_begin`'s count is the core's; only reset stops a running core; a commit scheduled refuses the update (SWAP_PENDING) and one written while it runs is held back; the learner offers its first write only when the shadow is open, and during an update no swap can close it again; every coefficient is inside the range.

**The core's and the injector's state, by hierarchical name** (the lead's ruling, V2). The learner needs the core's taps, the six fields of the matched-filter check, whether it runs, its next index, a scheduled commit and its index, a stream of words begun and not whole, and whether the shadow is closed; and the injector's `wr_push` and `t_index`, the index of each record it takes into its store. **No port of either block carries them**, so the two tops read them by name from `u_core` and `u_inject`, and work `closed` from the core's pipeline tags as `core.sv`'s status read does. No line of an earlier parcel's file changes. The kernel's round gives the two blocks ports for them (section 7).

### 2.2 The datapath and its widths

S = SAMPLE_BITS, N = the build's count_bits. Each width is a closed form of `model.learner.ranges`; at N of 2 or more each is the fewest bits for those ranges (row L1), and `widths_are_the_models` reads them back against `model.learner.widths` on `learn_small`.

| value | width | at N = 32, s16x1 / s24x3 |
|---|---|---|
| a count | N, unsigned | 32 |
| a sum | S + N | 48 / 56 |
| D | S + 2N + 1 | 81 / 89 |
| abs D, the peak, a remainder | S + 2N, unsigned | 80 / 88 |
| abs D × COEFF_MAX | S + 2N + 17, unsigned | 97 / 105 |
| a quotient; a coefficient | 17; COEFF_BITS | 17; 18 |

- **The delay buffer** holds the last B frames the core took, B the build's most taps.
- **The sums** are two memories of B words, a word a tap with every channel side by side. A taken window is added a tap a clock, every channel at once, from the clock after its judgement.
- **The copy** (the snapshot) is two memories as large.
- **D** is made from the copy a value a clock, by two multipliers and a subtractor, in the blob's order: channel c, then tap 0 (the window's oldest frame, the blob's coefficient 0) to T − 1.
- **The peak** is kept over pass A; if it is 0 the update makes no set, QUANTISE_INPUT.
- **The division and the rounding.** For each value, a restoring division of abs D × COEFF_MAX by the peak, a quotient bit a clock for 17 clocks, gives Q and the remainder R. **The rounding is made in one place:** Q + 1 when 2R passes the peak, or equals it with Q odd. Then the sign. Half to even is odd-symmetric, so this is `model.weights.round_half_even` on the signed value.
- **Nothing saturates:** abs D is at most the peak, so a coefficient is at most COEFF_MAX.

### 2.3 When, in clocks

- **A label-0 window** is judged at the first edge at which the core runs, its next index as the frame at that edge leaves it is j, and the record is known. A record handed over at an edge is known at that edge, before its frame.
- **A label-1 window** is judged at the edge the next index becomes j + T.
- **The update at u is made** at the first edge at which the next index is u or more, and either a record at u or later is known or frame u has been taken: then no record at u can still come (section 2.5).
- **The snapshot.** A copy pass copies the sums a tap a clock. It starts two clocks after the edge the update is made at when the next index there is u, since that edge's windows are the update's and their adds lead by a clock. It starts one clock after when the next index there is u + 1, since that edge's windows are not the update's, and a read sees the value before the edge that writes it. The counts are taken at that edge the same way.
- **Then pass A** (D and the peak), **`shadow_begin`**, **pass B** (D again, the division, the rounding, a word written each time), **the head weight**.
- **Two adds never overlap at any rate up to a frame a clock.** Taken windows' judge indexes are at least T apart (LRN-B's W6), each is judged at an edge where the next index is its judge index, and the index rises at most one an edge; so two adds start at least T clocks apart, and each takes T.

### 2.4 The update's time

At the definition's 128 taps, measured on `learn_chain` from the edge the update is made at to the edge its last write is taken: **2,699 clocks under s16x1 and 7,819 under s24x3**. The budget in F − 1 frames at the chain's rate is 5,100 and 15,300 (rows L2 and L3). F − 1, because the update may be made a frame after u. So the update finishes inside F = 256 with about half to spare, and `update_finishes_within_f` holds it from both sides: a commit at the last clock at which the next index is u + F − 1 is refused UPDATE_UNFINISHED, one at the first clock at which it is u + F is taken.

### 2.5 The race

The injector takes a record at j only while its own index is at most j, and hands the core each frame 52 clocks after taking it. **Under s24x3 at the chain's rate, for 8 clocks of every frame the core's next index is already j while the injector has not taken frame j** (row L4), so a record at j can arrive after the core's judge point j. The learner judges a late label-0 window at its arrival, and makes an update at u only when the truth at u is final; `a_record_offered_late` drives the case on both tops, and under s16x1 on the chain, where the window is empty, it holds that the injector refuses the offer, INJECT_OVERLAP.

## 3. The registers and the refusals

| row | a write | a read |
|---|---|---|
| `lrn_update_at`, 2 words | the lower word kept; the upper word names `update(u)` | u while an update is unfinished, else 0 |
| `lrn_status` | REGISTER_ACCESS | named (taken, next index below u), running (taken, u or more, not finished), made, unmade (the last finished update's outcome), refused, refused_again |
| `lrn_refusal` | 0 clears it; anything else REGISTER_ACCESS | the first refusal since it was cleared |
| `lrn_count0`, `lrn_count1` | REGISTER_ACCESS | the counts |
| the six 64-bit counters | REGISTER_ACCESS | a read of a lower word holds that counter's upper word for the read of its upper word |
| `lrn_cap_count_bits`, `lrn_cap_update_frames` | REGISTER_ACCESS | the build's N and F |
| any other offset in [0xD00, 0xE00) | REGISTER_ACCESS | 0 |

**An update's faults are named in this order:** CORE_STOPPED, UPDATE_UNFINISHED, SWAP_SHAPE, SWAP_PENDING, SWAP_INDEX, WEIGHT_COUNT. The model's four are in the model's order; the fabric's two, CORE_STOPPED (the core not running) and WEIGHT_COUNT (a host's stream begun and not whole), are first and last, as the core's own chain has them for a commit. An unmade update latches QUANTISE_INPUT at its finish. At one edge the latch takes a clear first, then QUANTISE_INPUT, then the write's refusal.

## 4. The benches

Each bench module has a row for each profile. Every comparison of records goes through `harness.hold`, and every operation's two refusal registers, and the eight counts and `lrn_status` at the end, are held to the model's; the register checks are collected and raised after the records are held, so a fault of the records is reported as the harness's mismatch.

| test | top | what it holds |
|---|---|---|
| `bit_identity_hand_worked_ties` | small | LRN-B's hand-worked cases with ties (case 1 under s16x1, case 3 under s24x3), each coefficient alone in a score after the commit; the model's set is the hand-worked one |
| `bit_identity_every_coefficient` | small | two updates at the build's 6 taps, each set read back coefficient by coefficient; the core's `shadow_count` and `whole` after the learner's writes |
| `update_finishes_within_f` | both | F from both sides, at 6 taps and F 16, and at the definition's 128 taps and F 256 |
| `skips_at_their_boundaries` | small | START at T − 1 and free at T; label 0 BUSY at 2T − 1 and free at 2T; label 1 BUSY at T − 1 from after and from before, and free at T; each label's FULL alone; START before BUSY; two BUSY at one edge; label 0 and label 1 each both BUSY and FULL, counted BUSY |
| `snapshot_at_u` | small | the windows judged at u in the update and the next not, made at u and made a frame late; windows judged while pass B divides |
| `a_record_offered_late` | both | the race (section 2.5) |
| `frames_every_clock` | small | windows at a frame a clock, the commit scripted after the learner is done |
| `refuses_an_update`, `refuses_the_core_rows`, `refuses_swap_shape`, `refuses_what_the_model_cannot`, `quantise_input`, `refusal_order` | small | each refusal of section 3, each case alone where one can be made alone; SWAP_INDEX below the next index, exactly one below it, written at the edge that takes a frame, and past the field's most; no SWAP_PENDING for an update written at the commit's own edge; the order in pairs, UPDATE_UNFINISHED before SWAP_SHAPE from a state written into both sides |
| `rows_read_back`, `reads_while_the_learner_writes` | small | the rows, `lrn_status` at exactly next index u against the model's own there; `lrn_skip_busy`'s two words of one moment; no read lost to a write of the learner's |
| `counters_past_two_to_the_32` | small | all six 64-bit counters carried past 2^32 from a state written into both sides, each to another upper word (1 to 6) |
| `full_at_thirty_two_bits` | chain | FULL at count_bits 32: label 0's count written at 2^32 − 2 into both sides, one window to its most, two FULL, an update of that count |
| `extremes_by_real_windows` | small | the sums, D and the peak at their bounds by 7 windows a label |
| `widths_are_the_models`, `control_model_half_away` | small | the widths; the comparison handed a learner that rounds half away from zero, seen at the record of the tie |
| `truth_isolation` | chain | the same samples under 3/1, 6/2, and 3/1 with an added record of amplitude 0: identical up to the named commit, each the model's with its own learner's set after it, the sets of the first and third different |
| `bit_identity_e1_flow` | chain | E1's layout at 64 taps: eight records 128 apart, a host shadow write and a commit refused while the update runs, the commit at its finish |
| `one_bus_four_blocks` | chain | a word of each block, a refusal latched in each, each cleared in turn |

## 5. The mutants, and where each one's evidence fell

66 mutants: 32 on `learn-s16x1`, 28 on `learn-s24x3`, 5 on `learn-chain-s16x1` and 1 on `learn-chain-s24x3`. Each was read against the record or the register its fault predicts (row L11), in the run of row L5; each named WORD below is held by the stage as a WORD mismatch from the harness, and each other by its test's failure. Eighteen of them came after the verifier VRTLL, in place of one (section 5.1).

| mutant | profile | where its evidence fell |
|---|---|---|
| `does-nothing`, `half-away`, `drops-the-last-window` | s16x1 | case 1's record 32, the impulse on channel 0's tap 1: 2, 1 and 1 where the model has 0, the tie (WORD) |
| `copy-one-early` | s24x3 | "made at u, T = 1", record 23 (WORD) |
| `copy-one-late`, `no-copy` | s16x1, s24x3 | "made a frame late, T = 2", record 27 (WORD) |
| `start-removed`, `busy0-removed`, `busy1-before-removed`, `busy1-after-removed` | both | that label's count register in the boundary's run |
| `full0-removed`, `full1-removed` | s24x3, s16x1 | the FULL run's record 77: another set (WORD) |
| `full-before-busy` | s24x3 | `lrn_skip_busy` 1 where the model has 3 |
| `finished-a-frame-early` | s16x1, and s24x3 at 128 taps | `lrn_refusal` 0 after the commit at u + F − 1, where the model has 54 |
| `finished-a-frame-late` | s24x3 | the commit's record 60: the old epoch (WORD) |
| `make-without-waiting`, `late-record-not-judged` | s16x1, s24x3 | the late record's run, record 29 (WORD) |
| `commit-not-held` | s16x1 | record 30: a swap where none was taken (WORD) |
| `shadow-begin-not-held` | s16x1 | record 50: the old epoch, the core's stream broken in the learner's pass B (WORD) |
| `shadow-data-not-held` | s24x3 | record 50: another set (WORD) |
| `update-not-held` and the thirteen one-condition refusal mutants | both | that case's code in `lrn_refusal`: 0 where the model's name is, or the next name of the chain (`stopped` gave SWAP_SHAPE) |
| `names-every-refusal-wrongly` | s24x3 | every case's code one off: 55 for 54, 18 for 19 |
| `peak-zero` | s24x3 | "no window at all", record 22: a swap the model makes, missing (WORD) |
| `counter-thirty-two-bits`, `upper-word-live` | s16x1, s24x3 | `lrn_skip_busy` 3 where 2^32 + 3; the upper word 1 where the held 0 |
| `sum-narrower`, `peak-narrower`, `difference-narrower`, `dividend-narrower` | both | the extremes' records 48 and 49: another coefficient (WORD) |
| `learner-takes-a-read` | s16x1 | a read of `lrn_cap_count_bits` answering the core's stale word ORed in, 0x554E4457 |
| `taps-reversed`, `channels-swapped` | s16x1, s24x3 | record 70 of the every-coefficient run (WORD) |
| `commit-a-frame-late` | s16x1, chain | E1's flow, record 1290: the old epoch (WORD) |
| `learner-commits-itself` | s16x1, chain | truth isolation, record 437: a new epoch where no commit was named (WORD) |
| `truth-into-the-frame` | s16x1, chain | the third wording's record 0, before any commit (WORD) |
| `reads-the-amplitude` | s16x1, chain | the first wording's record 660, the commit's: another set (WORD) |
| `learner-off-the-bus` | s16x1, chain | word 3, `lrn_cap_count_bits`: 0 where 32 (WORD) |

**Four survived the first pass of the mutants, and each was the bench's stream, not the RTL** (row L12):
- `drops-the-last-window` and `copy-one-late`: with every truth record before u, an update in `learn_small` waited a frame for the truth at u, so the branch of "made at u" was never run. The hand-worked test now holds a record past the stream's end, which makes it run. The second case was at T = 1, where under one channel the set is only a sign; it is now T = 2.
- `shadow-begin-not-held`: the host's shadow write came before the learner's `shadow_begin`, which restarts the stream anyway. A second one is now placed inside the learner's pass B.
- `dividend-narrower`: it narrowed a register whose top bits the division never reads. It now narrows the product itself.

### 5.1 The verifier's gaps, and what holds each now

The verifier VRTLL (round 5) found no wrong answer in the RTL, and eight one-place changes of `learn.sv` that both `learn_small` benches passed. No line of the RTL changed for them: each new test passed on the shipped RTL at its first run. Each gap now has a test that fails on it and a mutant in the manifest, but one that cannot fail (row L15):

| the gap | what holds it now | mutant | where its evidence fell |
|---|---|---|---|
| two BUSY skips at one edge counted as one | `skips_at_their_boundaries`, records 3, 5 and 8 at T = 3: at 8, label 1 of 5 and label 0 of 8, both BUSY | `two-busy-counted-once` | `lrn_skip_busy` 3 where the model has 4 |
| two FULL skips at one edge counted as one | cannot happen (limit 20) | none | none can fall |
| SWAP_INDEX at exactly next index − 1 | `refuses_an_update`, an update of 40 at 41 | `index-one-below-taken` | `lrn_refusal` 0 where the model's is 20 |
| an update written at the edge that takes a frame | `refuses_an_update`, an update of 42 landing at the edge that takes frame 42 | `index-before-the-frame` | the same, after the update of 42 |
| SWAP_PENDING as the frame at the write's edge leaves it | `refuses_an_update`, an update landing at the commit's own edge, which the model takes | `pending-before-the-frame` | `lrn_refusal` 8 where the model's is 0 |
| `lrn_status` at exactly next index u | `rows_read_back`, a read at u against the model's own `status()` there | `status-at-u` | named 1 and running 0 where the model has 0 and 1 |
| every counter's upper word past 2^32 | `counters_past_two_to_the_32` | `start-upper-from-busy`, `busy-upper-from-full`, `full-upper-from-made`, `made-upper-from-unmade`, `unmade-upper-from-early`, `early-upper-from-made` | the counter's two words read at the end: `lrn_early` 4 × 2^32 where the model has 6 × 2^32, and the like |
| every counter's width | `counters_past_two_to_the_32` | `start-thirty-two-bits`, `full-thirty-two-bits`, `made-thirty-two-bits`, `unmade-thirty-two-bits`, `early-thirty-two-bits`, and the earlier `counter-thirty-two-bits` for `lrn_skip_busy` | the counter at the end: 0 where the model has k × 2^32 |

And two more of its notes. **Label 0's FULL and label 1's FULL are each removed alone** (`full0-removed`, `full1-removed`, in place of the pair): the FULL run now has nine records, so each label's eighth window is FULL with no BUSY beside it. **FULL at count_bits 32** is now `full_at_thirty_two_bits` on the chain (limit 7).

## 6. Limits

Each is stated by the behaviour it concedes.

1. **One simulator,** Icarus Verilog 12.0. Only `learn` and `learn_port` alone are synthesised, out of context, for their cost and nothing else: `docs/studies/SYN-learn.md` (the lead's, wave 3). Nothing is implemented, and no clock is claimed.
2. **F is met at the chain's rate.** With frames faster than one every 20 clocks a channel, a commit the model takes at u + F is refused UPDATE_UNFINISHED: seen, not silent. A host that holds the core's port for more than about half the update's budget does the same. The windows are right at any rate up to a frame a clock.
3. **The core's and the injector's state are read by hierarchical name** in the two simulation tops. A synthesis tool may not take them, and a rename in `core.sv` or `inject.sv` stops these builds.
4. **`closed` is worked in the tops from core.sv's tag layout**, retyped from the package. A core that changed its layout would be seen only as a core refusal at the learner's write or as an update that never finishes.
5. **One index space.** An injector begun at another first frame (`inj_frame`) is not mapped: the learner takes its indexes as the core's, wrong without a word. The host library never writes `inj_frame` (row L10).
6. **The truth port's contract is not checked by the learner.** It takes what the injector took: strictly ascending, none behind the core's next index. Its store holds MAX_INJECT_PENDING + 4 indexes, held by derivation (row L6) and not by a run that fills it, and a push into a full store is not refused. `learn_small`'s truth port is the bench's, and keeps the contract by the bench's construction.
7. **FULL is held at count_bits 3 by real windows on `learn_small`, and at count_bits 32 from a written state on `learn_chain`** (`full_at_thirty_two_bits`: label 0's count written at 2^32 − 2 into both sides, one window to its most, then two FULL). 2^32 real windows are not run. **Every one of the six 64-bit counters is carried past 2^32 from a written state** (`counters_past_two_to_the_32`), each to a different upper word, so a counter of 32 bits or an upper word read from another counter's hold is seen; `lrn_skip_busy`'s two words of one moment are also held across a skip between its two reads (`rows_read_back`). A counter past 2^64 is outside both sides. *Restated after the verifier VRTLL (2026-11-25): until then FULL at 32 bits was held by no bench, and only `lrn_skip_busy` was read past 2^32.*
8. **The sums, D and the peak are not read out.** They are seen through the set, each coefficient alone in a score on `learn_small`, and through the counts. On `learn_chain` a wrong coefficient is seen through the noise, not alone.
9. **One pulse in the fabric's injector.** A learner that reads the pulse id reads a constant, and no wording here can show it; reading the amplitude is the mutant `reads-the-amplitude`.
10. **The race is shown under s24x3 in the chain**, where its window is 8 clocks, and under both profiles in `learn_small`. Under s16x1 in the chain it cannot occur at the chain's rate.
11. **Under one channel two filters are two rows,** so the filters' condition and the rows' are never made alone there; the mutants `shape-filters` and `shape-rows` run under s24x3.
12. **UPDATE_UNFINISHED before SWAP_SHAPE cannot be made by operations.** An update is named only under the matched shape, which a running core keeps. It is held from a state written into both sides, as LRN-B's own test does.
13. **A count width of 1 and an update time of 0 are not built** (LRN-B's F6 and F7): at 1 bit the closed-form widths are wider than the fewest, and an update takes clocks. A build refuses either at time zero, by name; the model keeps both.
14. **The refusals' mutants:** each of section 3's conditions has one that removes it alone, but one mutant, `names-every-refusal-wrongly`, stands for every name reported wrongly, as in core.md's limit 11. No mutant reports one name wrongly and leaves the others right.
15. **A mutant shows the bench sees its fault under one profile.**
16. **What this bench holds at sampled sizes it holds at those sizes alone** (core.md limit 23): T at 1, 2, 3, 6, 16, 32, 64 and 128; F at 16 and 256. count_bits at 3 for everything `learn_small` holds, FULL among it; at 32 for what `learn_chain` holds, where FULL is reached only from a written state (limit 7), and for the widths, which `widths_are_the_models` reads at 3 alone.
17. **The model has frames and no clocks.** The clocks of section 2.4 are this design's, held by F from both sides and by the chain bench's log.
18. **Nothing here is evidence about sensitivity.**
19. **Truth isolation in the fabric is held through the model, not by comparing the design's runs with each other.** `truth_isolation` requires the model's records of the wordings 3/1 and 6/2 to be equal, and those of 3/1 and of 3/1 with an added record of amplitude 0 to be equal up to the commit and different after it, and holds the design to the model in each run. So the fabric's records are equal across the wordings only because each equals the model's; no assertion compares two of the design's runs directly.
20. **Two windows cannot both be counted FULL at one next index.** At next index n the windows judged are label 0 of a record at n and label 1 of a record at n − T. For label 1 of n − T to be free of BUSY no record lies in (n − T, n), so the record at n is the next after n − T, and label 0 of n is then BUSY, T < 2T. So `add_full`'s two terms are never true together, and the learner counting them with an OR in place of a sum is identical on every stream: no test can see it, and none does. Two BUSY at one edge do happen, and `skips_at_their_boundaries` holds them (row L14).

## 7. The kernel, a later round's

Wiring the learner into `rtl/krnl/` is not in this parcel. A later round must:
1. give `core.sv` and `inject.sv` read-only ports for what section 2.1 reads by name;
2. instantiate `learn` and `learn_port` in `undertone_krnl.sv`, the core's port through the gate and the learner on the bus unfiltered;
3. OR the learner's `reg_rdata` into the read path;
4. build the core and the learner at one B_TAPS;
5. teach the host library the update, the counters and `lrn_cap_*`, with `host/fake.py` beside it;
6. link.

Until then the kernel sends a write at 0xD00 to 0xDFF to no block, dropped with no refusal, and a read there answers 0 (row L9).

## 8. What it costs, as far as a count can say

Counted at the definition's maxima (B = 128, N = 32); no LUT and no clock is claimed here (row L7). The look-up tables, registers and DSP slices were measured afterwards, by an out-of-context synthesis, in `docs/studies/SYN-learn.md`; no clock is claimed there either.

| what | s16x1 | s24x3 |
|---|---|---|
| the delay buffer, bits | 2,048 | 9,216 |
| the sums, bits | 12,288 | 43,008 |
| the copy, bits | 12,288 | 43,008 |
| the truth store, bits | 65,792 | 65,792 |
| adders for the windows | 1 of 48 bits | 3 of 56 |
| multipliers | 2 of 48 × 32 | 2 of 56 × 32 |
| the divider | one 81-bit restoring step, iterated | one 89-bit step |

The truth store is read at three places at once in this RTL (the two cursors and the record after one); whether a tool makes that of LUTs or of a block RAM with registers before it is the synthesis's to measure. The synthesis made no block RAM under either profile (SYN-learn.md, row SL1).

## 9. Register

"The stage on a copy" is `python tools/check_rtl.py rtl-benches --root <a copy> --state <a folder>`, the copy holding this tree's `spec`, `model`, `learn`, `rtl`, `tools`, `docker` and `vectors` with a manifest of this parcel's four rows alone. The copies are in the round's scratch folder, not in the tree; the gate's second size runs the same rows among the others.

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| L1 | The widths of section 2.2 equal the fewest bits for the model's ranges at count_bits 2, 3 and 32 under both profiles; at count_bits 1 the sum's and D's closed forms are one and two bits wider | COMPUTED | the design's arithmetic, ledger RTL-L.md, 2026-11-25 21:57, row R1; on the small build `widths_are_the_models` reads them back | `widths_are_the_models` failing |
| L2 | At 128 taps the update took 2,699 clocks under s16x1 and 7,819 under s24x3, from the edge it was made at to the edge its last write was taken | MEASURED | the stage on a copy, 2026-11-25 22:27: the LEARN-MARGIN line `update_finishes_within_f` of `bench_learn_chain` logs in each run's log | that line in the gate's run |
| L3 | The budget in F − 1 frames at the chain's rate is 5,100 and 15,300 clocks | COMPUTED | 255 × 20 × 1 and 255 × 20 × 3, seam.md row K3's rate | arithmetic |
| L4 | Under s24x3 at the chain's rate the core's next index is j for 8 clocks before the injector takes frame j; under s16x1 for none | COMPUTED | 60 − 52 and 20 − 52 clocks, from source.md rows S5 and S7 | `a_record_offered_late` under s24x3 |
| L5 | This parcel's four rows pass 50 tests in 4 runs of 4 benches, hold 14,520 records identical to the model's, and see 66 mutant runs fail as named; 462 s of run time and 181 s of the stage alone, six at a time | MEASURED | the stage on a copy, 2026-11-25 23:45:56 to 23:48:57: its OK line, and the runner's "ran" lines. Before the verifier's gaps (22:38:37 to 22:40:46) it was 46 tests, 13,198 records and 49 mutant runs | the gate's line for `rtl-benches`, which gives totals for every bench |
| L6 | In the chain the learner's store holds at most the injector's 1,024 records and 2 more | COMPUTED | records 64 frames apart; a record leaves the injector after its 64th frame and the learner after j + T, T at most 128; the injector 52 clocks ahead of the core | a run that fills it, not made |
| L7 | The storage of section 8: the buffer, the sums, the copy and the truth store | COMPUTED | 128 × C × S; 2 × 128 × C × (S + 32) twice; (1,024 + 4) × 64 | arithmetic |
| L8 | Records through the injector are at least 64 frames apart | READ | `rtl/inject/inject.sv`, `free_from` and INJECT_OVERLAP; e0's length | that file |
| L9 | The kernel sends a write at 0xD00 to 0xDFF to no block, and a read there answers 0 | READ | `rtl/krnl/undertone_krnl.sv`, the three `hit_` wires and the blocks' valids | a bench on the kernel |
| L10 | The host library never writes `inj_frame` | READ | a search of host/ for the name, 2026-11-25 | that search |
| L11 | Each mutant's evidence fell where section 5's table says | MEASURED | the run of L5: each mutant run's results file and evidence file, read one line a test | the gate's evidence under `verify/state/<run>/` |
| L12 | At the first pass of the mutants, four of 49 survived, each for the bench's stream; with the four streams mended, none did | MEASURED | the stage on a copy, 2026-11-25 22:33:45 to 22:36:31, four findings MUTANT-SURVIVED; then the run of L5 | a rerun of the first pass's bench |
| L13 | F = 256 frames is the definition's, and the learner meets it at the chain's rate | DECISION | the lead's ruling, 2026-11-25 22:00, on LRN-B's question 1 | `update_finishes_within_f` failing |
| L14 | No next index judges two windows that are both free of START and BUSY, so two FULL skips never fall at one edge; two BUSY skips do | COMPUTED | limit 20's argument; and a script of the parcel's own that states the window rules anew and imports nothing, over every set of up to five records in 0..19 at T = 1 to 4: no such index. The script is in the round's scratch folder, not the tree | a stream of the model's whose log has two FULL outcomes at one next index |
| L15 | Each of the verifier VRTLL's eight gaps but the two-FULL one fails a test, and each such test passed on the shipped RTL at its first run | MEASURED | the run of L5: the eighteen new mutants of section 5.1 each failed as named, their evidence read one line a test, and the new and changed tests passed on the unchanged RTL | the gate's second size with those mutants |

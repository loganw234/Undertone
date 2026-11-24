# The detector core and its weight store, in RTL

Written by parcel RTL-B in round 2, 2026-11-23. Labels are those of [the design](../studies/D0-rough-design.md): MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure on this page is in the register at the end. How the RTL side works at all, the harness, the manifest and the gate's second size, is [README.md](README.md), beside this page.

This is the reference model's detector core ([mod-b.md](../model/mod-b.md), [head.md](../model/head.md)) in SystemVerilog, **in simulation**, held against the model on every score word. It is the first of the three parts of D0's gate "bit identity": RTL in simulation. The host and the card are later rounds'.

**What a pass here is evidence of:** that the RTL's score records equal the model's on the streams the benches ran. It is not evidence about sensitivity, which has its own authority, and it is not evidence that anything can be built for the card: nothing here has met a synthesis tool.

## 1. Where things are

| what | where |
|---|---|
| the core: the bank, the pool, the store, the control block | `rtl/core/core.sv` |
| the head, a module of its own | `rtl/core/core_head.sv` |
| the core at small maxima, a top for the benches | `rtl/core/core_small.sv` |
| the register port driven as a host would drive it | `rtl/tb/core_host.py` |
| the benches | `rtl/tb/bench_core.py`, `rtl/tb/bench_core_control.py`, `rtl/tb/bench_core_max.py` |
| their rows and mutants | `rtl/tb/benches.toml`, from the line that names this parcel |
| the control block, as numbers | `spec/undertone.toml`, `[registers]` from 0x080, `[register_bits]`, `[blocks]` |

## 2. The shape of a build

`core` takes `SAMPLE_BITS` and `CHANNELS`, and seven build maxima that default to the definition's: `B_FILTERS`, `B_TAPS`, `B_ROWS`, `B_POOL`, `B_SCORE_SHIFT`, `B_HIDDEN`, `B_HIDDEN_SHIFT`. `COEFF_BITS`, the record's layout, every code and every offset come from the generated package. A shape inside the build's maxima is loaded while the core is stopped, and is frozen while it runs.

Two tops are built. `core` at its defaults is the definition's maxima. `core_small` is the same file with 4 filters, 5 rows, 6 taps, a pool of 1,024, 3 hidden units, a score shift of 20 and a hidden shift of 24. It exists because the runner hands a top two parameters and the manifest has no key for more. Its values: every one differs from the definition's, so a capability register is not a constant a test could read instead; rows are more than filters, so the two bounds differ, and no fewer, or a shape with the most filters could not be made; 6 is not a power of two and 1,024 is; a pool of 1,024 lets a hidden sum land on exactly -2^63 under `s16x1`; a score shift of 20 brings this build's largest output sum inside the field.

**The RTL can be built at a smaller maximum without another line changing.** Every width is derived from those parameters, and the capability registers and the refusals read the same parameters.

## 3. The datapath

Eleven registered stages. A frame is taken at a rising edge where `in_valid` is high and the core is running.

| # | stage | what its register holds | `s16x1` / `s24x3` at the definition's maxima |
|---|---|---|---|
| 1 | `s1` | the delay lines, newest sample at position 0; the frame's tag | the sample's bits |
| 2 | `s2` | each coefficient of the frame's own bank times its sample | 34 / 42 |
| 3 | `s3` | the row sums | 41 / 49 |
| 4 | `s4` | the filter sums, rectified; the pool's memory is read here | 41 / 50 |
| 5 | `s5` | the pooled sums | 57 / 66 |
| 6 | `h0` | the pooled sums again: the head's input register | 57 / 66 |
| 7 | `h1` | the hidden products, each at the hidden sum's width | 77 / 85 |
| 8 | `h2` | the hidden values after between, at between's width | 65 / 65 |
| 9 | `h3` | the output products, each at the output sum's width | 85 / 85 |
| 10 | `h4` | the score | 64 / 64 |
| 11 | `rec` | the record; the sticky overflow flag | the record's bits |

- **The widths are closed forms of the model's ranges**, not a search. The largest product is +2^(S + COEFF_BITS - 2), both factors at their lowest, and every other product is smaller in magnitude; so a sum of N products needs that exponent + clog2(N + 1) + 1 bits. The hidden sum's extreme is negative, and needs the exponent + COEFF_BITS + clog2(rows x pool x taps). The hidden value's width is the record's score field; between's is one more; the output sum's is what the build's units at +-2^63 need under a head weight at its lowest. At the definition's maxima they are the model's (`detector.widths`, `detector.hidden_widths`), and a test holds that.
- **Coefficient order.** The model's coefficient j of T meets the sample T - 1 - j frames old. The loader puts it at delay-line position T - 1 - j.
- **The pool** is one accumulator a filter, z + r - oldest, and one memory, the pool's most deep and every filter's rectified value wide, read a stage ahead with the word being written that same clock forwarded (a pool of 1 on consecutive clocks). The memory is never cleared: a counter that stops at P says whether an oldest value exists yet.
- **The two roundings** are at `h2` and `h4`, each an arithmetic shift right of a signed value: toward minus infinity, as the model's.
- **The two widths that are a choice** are the hidden value's and the score's. A value that does not fit keeps the field's bits, the value modulo 2^64, sets the frame's overflow bit, and what follows is computed from the kept bits. Nothing saturates.
- **The flags.** Settling is decided when the frame is taken and travels in its tag. The frame's overflow bit is the OR of every unit's at `h2` and the score's at `h4`; at `rec` the record's flag is the sticky bit OR the frame's, and the sticky bit takes that value. Only reset clears it.
- **One route for both heads.** The fabric builds no second head. A shape with no hidden layer runs as head.md section 2's setting: unit 0 alone, its weights the K head weights, the score shift as its shift, pass between, a head weight of the constant 1 through a mux, and no shift after. The model takes two routes and holds their agreement by a gate (head.md, HL3). **Here HL3 is held once more, by other code:** every identity test whose shape has no hidden layer compares the fabric's one route with the model's version 1 route on every word: `bit_identity_every_tap`, the shapes of `bit_identity_random` and `bit_identity_swap` that have no hidden unit, the first stream of `bit_identity_extremes`, the index's streams of `bit_identity_counters`, and half of `bit_identity_largest_shape`.

## 4. The latency

**Eleven clocks** at every build: a frame taken at one rising edge has its record out at the eleventh after it. `latency_is_eleven_clocks` asserts the latencies seen are exactly [11], on both tops under both profiles. Eleven is a count of this design's registers and not a claim about any clock: a row's taps are summed in one stage, and so are a unit's sum, its shift and its comparison.

## 5. The weight store and the swap

Two banks and one bit, `active_sel`. Before the start a weight word goes into both banks, so the shadow starts as a copy of the active set. A swap is the bit flipping at the frame whose index a commit named, and the epoch rising by one: `Store.step` of `model/weights.py`, line for line, with the model's "outputs still mix" kept as a count.

**The bit travels with the frame, in its tag.** The products at `s2`, the hidden products at `h1` and the output products at `h3` each read the bank the frame at that stage names. So no filter sum, hidden sum or output sum mixes two sets, whatever the pipeline's depth.

**A write and a frame at one edge: the write is ordered after the frame.** Its checks read the state as the frame leaves it. This is the one place where the fabric's order is a choice. A commit whose write lands at the edge that takes frame n-1 and names index n is taken, and the swap is at the very next clock; one that names n-1 is refused, SWAP_INDEX, as `step` then `commit` is in the model. `bit_identity_swap_on_the_edge` and `commit_orders` drive both on an unbroken stream. **A read sees the state before the edge that takes it.**

**The weights arrive as a stream**: `shadow_begin` with the count, then the words in the blob's order through `shadow_data`. A word out of range is not stored and spoils the stream.

## 6. The control block

Its 22 rows are in the definition, `[registers]`, from 0x080 to 0x118, with the ten bits of `status` in `[register_bits]`. The port is the one every block has: `reg_valid`, `reg_we`, `reg_addr`, `reg_wdata`, `reg_rdata`; one operation a clock; `reg_rdata` is a register that answers 0 for what is not a readable row of this block. Outside 0x010 to 0xEFF the core does nothing.

The states are STOPPED (after reset, the only way into it), LOADING (after `configure`) and RUNNING (after `start`). A command's data means something and is checked: `configure` and `shadow_begin` take the count of weight words, `start` the start epoch, `commit_at` the index in two words, the write of the upper word being the commit.

## 7. The refusals

A write that is not taken changes nothing and latches the refusal's number in `refusal`; the first since it was cleared is the one kept, and a later one sets a status bit and is not otherwise recorded. **The fabric raises nineteen names.**

| name | what raises it in the fabric |
|---|---|
| REGISTER_ACCESS | a write to a read-only row, to an offset that holds none, to an offset that is not a multiple of the word; a write to `refusal` that is not zero |
| CORE_STOPPED | a frame offered while the core is STOPPED or LOADING; a commit while it is STOPPED or LOADING; a `shadow_begin`, a weight word or a `start` while it is STOPPED |
| SWAP_SHAPE | a shape register written, or a `configure`, while the core is not STOPPED; a `start` while it is RUNNING |
| PROFILE_UNKNOWN | the sample bits and channels the host states are not this build's |
| SHAPE_FILTERS, SHAPE_TAPS, SHAPE_POOL, SHAPE_SHIFT | K, T, P, s outside what the build holds |
| SHAPE_RECTIFIER | a rectifier code that is not pass or abs |
| SHAPE_HIDDEN | more units than the build holds; or no hidden layer with a hidden shift or a between that is not zero. `unpack` reads those four bytes of a version 1 blob as its reserved field and says RESERVED_BITS: that is the host library's, raised before the fabric sees anything |
| SHAPE_HIDDEN_SHIFT, SHAPE_BETWEEN | with a hidden layer: a shift past the build's; a code that is not declared |
| SHAPE_CHANNEL | a filter's mask is zero, or names a channel the profile has not |
| SHAPE_ROWS | more rows than the build holds |
| SWAP_PENDING | a commit while one is scheduled or outputs still mix; a shadow write while a commit is scheduled, or while the shadow is closed (limit 4) |
| SWAP_INDEX | a commit below the next index |
| SWAP_EPOCH | a commit when the epoch is the last its field holds |
| WEIGHT_COUNT | a stated count that is not the shape's; a word with no stream begun, or past the set's end; a `start` or a commit with a stream not whole |
| WEIGHT_RANGE | a weight word outside the coefficient's range |

That table's rows hold nineteen names. **The order in which one write's faults are named** is one chain in `core.sv`, and it is: REGISTER_ACCESS, CORE_STOPPED, SWAP_SHAPE, PROFILE_UNKNOWN, SHAPE_FILTERS, SHAPE_TAPS, SHAPE_RECTIFIER, SHAPE_SHIFT, SHAPE_POOL, SHAPE_HIDDEN, SHAPE_HIDDEN_SHIFT, SHAPE_BETWEEN, SHAPE_CHANNEL, SHAPE_ROWS, SWAP_PENDING, SWAP_INDEX, SWAP_EPOCH, WEIGHT_COUNT, WEIGHT_RANGE. For a shape that is `unpack`'s order (model/weights.py), with SHAPE_HIDDEN's "no hidden layer" case where `pack` names it; for a commit it is the model's SWAP_PENDING, SWAP_INDEX, SWAP_EPOCH. `refusals_in_order` holds it for ten pairs of a shape's faults.

**Not raised in the fabric.** BLOB_HASH and BLOB_FORMAT are the host's alone: the fabric sees no blob. CHANNELS and SAMPLE_RANGE cannot occur: `in_frame` is exactly the profile's bits and every pattern is a frame. RESERVED_BITS is raised by no fabric block. RECORD_FIELD, RECORD_KIND and QUANTISE_INPUT are the host's; the scorer's four and the source's, injector's and replay file's are other blocks'.

## 8. The capability registers

Each register of the read-only block reads the build's own value. On the full top `identity_block_reads_back` holds all fifteen against `spec.constants`, with `spec_hash` as eight words, the lowest first: **that is what holds README.md's limit 9**, and the mutant `spec-hash-words-reversed` shows it does. On the small top `capabilities_by_trial` reads each register and then asks the build: what is advertised must be taken, and one past it refused under that bound's name. `cap_blob_versions` has bits 1 and 2; the definition holds neither number, so the RTL types them and the test takes them from `model/weights.py`.

## 9. The benches

Each bench module has a row for each profile, so every test runs under both sample formats, and **every mutant runs under one** (the lead's ruling: a mutant's run is a build of its own, and the stage has one budget).

| rows | top | module | tests |
|---|---|---|---|
| `core-s16x1`, `core-s24x3` | `core_small` | `bench_core` | 15: seven identity tests, the latency, the shadow's two edges, the commits the store must refuse, `commit_at` read back, SWAP_EPOCH at a frame's own edge, three controls on the model side |
| `core-control-s16x1`, `core-control-s24x3` | `core_small` | `bench_core_control` | 24: one for each of the nineteen names, the order, outside the block, "a refused operation changes nothing" (the identity test), the capabilities by trial, a stream not finished |
| `core-max-s16x1`, `core-max-s24x3` | `core` | `bench_core_max` | 7: the identity block, the widths, the bounds against the model's own refusals, the largest shape, the two choice widths at their boundary, the true extremes from a written state, the latency |

**The mutants, each with the profile it runs under.**

| mutant | profile | what it plants | the test that must fail |
|---|---|---|---|
| `coefficient-bit-low` | s16x1 | the lowest bit of one coefficient | `bit_identity_every_tap` |
| `coefficient-bit-high` | s24x3 | the top bit of another row's coefficient | `bit_identity_every_tap` |
| `swap-half-taps-late` | s16x1 | half the taps read the bank the frame before named | `bit_identity_swap`, `bit_identity_swap_on_the_edge` |
| `swap-half-taps-early` | s24x3 | half the taps read the bank the frame behind will name | `bit_identity_swap_on_the_edge` |
| `head-weights-late` | s16x1 | the head weights a clock after the hidden weights | `bit_identity_swap` |
| `hidden-weights-late` | s24x3 | the hidden weights a clock after the head weights | `bit_identity_swap` |
| `narrow-row`, `narrow-pool`, `narrow-hidden-value`, `narrow-output` | s16x1 | that stage one bit narrower | `bit_identity_extremes` |
| `narrow-filter`, `narrow-rectifier`, `narrow-hidden-sum`, `narrow-between`, `narrow-score` | s24x3 | that stage one bit narrower | `bit_identity_extremes` |
| `one-stage-longer` | s16x1 | every record through one more register | `latency_is_eleven_clocks` |
| `shadow-not-closed` | s16x1 | the shadow never closed | `shadow_closes_and_opens` |
| `shadow-closed-too-long` | s24x3 | closed one clock more | `shadow_closes_and_opens` |
| `index-sixteen-bits` | s16x1 | an index that wraps at 2^16 | `bit_identity_counters` |
| `index-thirty-two-bits` | s24x3 | an index that wraps at 2^32 | `bit_identity_counters` |
| `cap-taps-one-more`, `cap-rectifiers-a-third` | s16x1 | a capability that advertises what the build refuses | `capabilities_by_trial` |
| `cap-taps-one-fewer` | s24x3 | a capability that advertises less than the build takes | `capabilities_by_trial` |
| `refuses-nothing` | s24x3 | every refused write is taken, and a refused frame is dropped with nothing latched | all nineteen `refuses_*` tests |
| `names-every-refusal-wrongly` | s24x3 | every number the core reports is another | all nineteen `refuses_*` tests |
| `spec-hash-words-reversed` | s24x3 | the hash's eight words the other way round | `identity_block_reads_back` |
| `hidden-shift-logical` | s16x1 | the first rounding as a logical shift | `bit_identity_random` |
| `score-shift-logical` | s24x3 | the second rounding as a logical shift | `bit_identity_random` |
| `rectifier-always-pass` | s16x1 | a rectifier that never folds | `bit_identity_random` |
| `between-always-pass` | s24x3 | a between that never folds | `bit_identity_random` |
| `coefficients-newest-first` | s24x3 | a row loaded the other way round | `bit_identity_every_tap` |
| `pool-no-forwarding` | s16x1 | the pool reads a word the same clock writes; kind UNKNOWN-BITS, since what it reads was never written | `bit_identity_swap_on_the_edge` |
| `settling-one-short` | s16x1 | one output fewer marked as settling | `bit_identity_swap` |
| `settling-one-long` | s24x3 | one output more | `bit_identity_swap` |
| `epoch-sixteen-bits` | s16x1 | an epoch that wraps at 2^16 | `bit_identity_counters` |
| `overflow-not-sticky` | s16x1 | each record carries only its own frame's overflow bit | `bit_identity_extremes` |
| `stops-after-four` | s24x3 | no record after the fourth; kind COUNT | `bit_identity_random` |
| `one-too-many` | s16x1 | a record repeated fourteen idle clocks after it; kind COUNT | `bit_identity_random` |
| `record-at-a-commit` | s24x3 | one clock of `out_valid` at a commit's write, where no comparison listens | `bit_identity_swap`, by the count below |
| `narrow-pool`, on the full top | s16x1 | the pooled sum one bit narrower at the definition's maxima | `bit_identity_written_extremes` |
| `narrow-hidden-sum`, on the full top | s24x3 | the hidden sum one bit narrower at the definition's maxima | `bit_identity_written_extremes` |
| `commit-at-upper-reads-lower` | s16x1 | a read of `commit_at`'s upper word answers its lower word | `commit_at_reads_back` |
| `settling-at-index-zero` | s24x3 | a commit at index 0 marks settling | `bit_identity_swap_at_zero` |
| `overflow-from-unit-zero-only` | s16x1 | only hidden unit 0 can raise the overflow flag | `bit_identity_extremes` |
| `swap-epoch-before-the-frame` | s24x3 | SWAP_EPOCH reads the epoch before a frame taken at the write's own edge | `swap_epoch_on_the_edge` |
| `overflow-not-from-the-last-unit` | s16x1 | every hidden unit but the build's last can raise the overflow flag | `bit_identity_extremes` |
| `overflow-is-a-parity` | s24x3 | the flag is the parity of the units that do not fit: right for one and for three, wrong for two | `bit_identity_extremes` |

**Four holes the verifier found, as it happened.** The parcel's second commit passed its gate with 98 tests and 55 mutant runs. Its verifier (the round's report VRTLB) then showed four one-place faults that no test of the parcel's caught and that fell under no stated limit. One the lead planted in the verifier's clone, a read of `commit_at`'s upper word answering its lower: the parcel's whole gate passed on it, because no test read that word with an index of 2^32 or more scheduled. Three were the verifier's own, each run against four of the six rows (both rows of `bench_core`, and the control block's and the full top's under `s16x1`) with no test failing: a commit at index 0 marking settling (the bench never committed at 0 with a pool of 2 or more); the flag raised only by unit 0 (every overflowing stream overflowed all units, or unit 0); SWAP_EPOCH read before a frame at the write's edge (the order was held for SWAP_INDEX alone). The RTL was right in all four and no line of it changed. Each now has a test whose expected words are the model's, and a mutant that fails it: the four rows of the table before its last two.

**Two neighbours of those holes, from the second verifier.** After the four were closed, two more one-place faults passed all of `bench_core`. *The flag from every unit but the build's last:* the new stream overflowed unit 1 of two configured units, and nothing made the small top's third unit the only source. `bit_identity_extremes` now has one stream for each unit of the build as the only one that overflows, every other unit's weights zero and every head weight zero, and the mutant `overflow-not-from-the-last-unit` fails on the last unit's. *Settling at index 0 for one pool size only* is not closed and cannot be by sampling: it is limit 23.

**And one more, from the third verifier: a flag that is the parity of the overflowing units.** With `ovf = !ovf` in place of `ovf = 1'b1` the bench passed: every stream overflowed one unit or all three of the small top's, and an even count, which cancels, was never driven. `bit_identity_extremes` now has a stream for every unit left out in turn, the others all overflowing at the same output: with three units, each pair. The table's last mutant passes the nine streams before them and fails at the first, at the record where two units stop fitting together.

That is 47 mutants: twenty-three under `s16x1` and twenty-four under `s24x3`. A narrowed filter and a narrowed rectified value are under `s24x3` because only under three channels is a filter wider than a row; the two refusal mutants are there because only there does a shape reach SHAPE_ROWS. The rest are split about evenly. The table's first eighteen rows hold twenty-six mutants, the brief's and the ruling's controls and their opposites; its next thirteen rows are faults the parcel tried against its own bench before reporting; the next two are on the full top; the next four are the first verifier's, the next is the second's and the last is the third's.

**A fault the first bench did not see.** Tried that way, a core whose overflow flag was not sticky passed five of the small top's six identity tests under `s16x1` and four of them under `s24x3`, where `bit_identity_swap` caught it; the sixth, `bit_identity_every_tap`, was not tried. No stream of the small top's extremes came back into range after overflowing. On the full top `bit_identity_boundaries` caught it under both profiles. The fourth stream of `bit_identity_extremes` was added for it, and `overflow-not-sticky` now fails there at the first record after the sums are back in range.

**The true extremes alone cannot show a narrowed pool.** With every weight at its lowest, as the model's overflow test has them, the pooled extreme under `s16x1` is exactly 2^55, the one value that needs the pool's last bit. One bit narrower it wraps to -2^55; the hidden sum of sixteen such under weights of -2^17 is then +2^76, which does not fit the hidden sum's own exact width and wraps back to the right -2^76. The model sees a narrowed pool because it flags the reduction itself; an RTL with no flag there is seen only through the score, and on that stream the score is right. So `bit_identity_written_extremes` has a second stream with one head weight alone, which leaves the pooled value's sign in the score, and the full top's `narrow-pool` fails on it. On the small top the extremes are not powers of two and nothing cancels.

**The harness listens only inside one call of `compare`.** These benches compare a stream in pieces and write registers between them, and a record the design put out between two pieces would be heard by nothing. So every test whose comparisons are meant to pass counts, over the whole test, the clocks at which `out_valid` is high (`core_host.Watch`), and ends by requiring that count to equal the records its comparisons held; the nineteen `refuses_*` tests end the same way, so no refused operation made the core put out a record. The three controls on the model side do not: their comparison is meant to stop at a mismatch. `record-at-a-commit` passes every comparison and fails that count: 678 records put out where 660 were compared. **Each mutant's evidence was read, not its verdict**, on 2026-11-23: each fails at the record or the word its fault predicts (the swap's own frame for "late", the frame before it for "early"; the record where a sum first needs its last bit; latencies of [12]; the first word of the hash). `hidden-weights-late` shows first on a head with no hidden layer: in the one route such a head keeps its weights where a unit's are.

**The refusals' two mutants stand for the brief's two controls for each name.** A mutant's run holds exactly the tests it must fail, and the judge reports any of them that passes (`MUTANT-SURVIVED`). So each of the nineteen tests is shown to fail when its refusal is absent, and again when its number is wrong. Limit 11 says what that concedes.

**The scripted model**, every line of its code, from `rtl/tb/core_host.py` (its docstring is there). It stands between a bench and the authority, so it calls the model's own public methods and hands back what `step` returns, untouched:

    class Scripted:
        def __init__(self, core, script):
            self.core, self.store, self.script, self.stepped = core, core.store, script, 0

        def step(self, frame):
            for method, argument in self.script.get(self.stepped, ()):
                getattr(self.core, method)(argument)
            self.stepped += 1
            return self.core.step(frame)

`control_model_commit_late` hands it a model that commits one output late and requires a Mismatch at the swap's own record.

**The registry row.** `tests/gates.toml` gives D0's gate "bit identity" the stage `rtl-benches` and the control stage `ctl-rtl-benches`. That control is the control on the judge, `tools/check_rtl.py`, and plants nothing in these benches. The controls on these benches are their mutants, and they run inside the stage `rtl-benches` itself.

## 10. Limits

Each is stated by the behaviour it concedes.

1. **One simulator.** Icarus Verilog 12.0 and nothing else. A construct it accepts and a synthesis tool does not is not seen. An `initial $fatal` stops a simulation of a build whose maxima pass the definition's; a synthesis tool is not shown to stop.
2. **No clock is claimed.** Eleven is a count of registers. A row's 128 products are summed in one stage, and a unit's 16 with a shift and a comparison behind them. When a build's timing report asks for more stages the number changes, and the bench's constant with it.
3. **A build smaller than the definition refuses, by the bound's name, a shape the definition allows.** The capability registers say what it holds.
4. **The shadow is closed while a frame taken before a swap still has weights to read from the bank that is now the shadow**: a valid frame at any stage from `s1` to `h1` whose tag names it. A shadow write then is refused, SWAP_PENDING, where the model, which has frames and no clocks, would take it as soon as the index is reached. On an unbroken stream that is six clocks after the swap's first frame; a sparse stream is not held closed for nothing. A host that is refused and writes again gets the model's records, and `shadow_closes_and_opens` holds that at both edges.
5. **The fabric has no third bank.** A stream begun and not finished, or spoiled by a word out of range, has overwritten part of the shadow, and a commit is refused, WEIGHT_COUNT, until a whole set is written. **What is lost against the model:** the model can swap back to the old set with no write at any time; the fabric can only while no stream has been begun since the swap. What keeps the system at the model is the host library unpacking the whole blob before it sends the first word. `a_stream_not_finished` holds both cases.
6. **The fabric checks no hash and sees no blob.** It holds each word to its range and the set to its count and its shape. A host that skips the hash, or damage between the host's check and the register writes, loads a set no blob described, and the fabric runs it exactly: its records are then the model's for the weights it holds, not for the blob the host meant. The shadow cannot be read back.
7. **Reset is the only way to the stopped state**, and a weight position the shape does not use is zero only because reset made it so.
8. **The benches load what the model's `unpack` gives.** A blob the model reads wrongly is loaded wrongly into both sides. `core_host.load` takes a load as taken only when no refusal is latched and the status says the core runs: no refusal alone is also what a core that never heard the bus would answer.
9. **A mutant shows the bench sees its fault under one sample format**, the one section 9's table gives.
10. **No mutant shows the bench sees a pipeline one stage shorter.** The latency test's exact eleven is what would.
11. **The refusals' mutants are two, for all nineteen names.** No mutant removes one name's check and leaves the others, so the bench is not shown to tell a missing check for one name from a missing check for all. And a test that passes only because another name's check catches its case is not a thing these two can show.
12. **Under a profile of one channel a filter is one row.** No shape reaches SHAPE_ROWS there (mod-b.md, L17): `refuses_shape_rows` has no case under `s16x1` and says so, and `cap_rows` is asked of the build under `s24x3` alone.
13. **The model's run at the true extremes is not made on the full top**: 65,663 frames with a pool of 65,536 full of extremes. A thousand such frames cost about eight seconds in Icarus (rows C16 and C17), so the run is about eight minutes a profile for each head: too long for the gate. **The extremes are reached from a written state instead**, as head.md's HL6 does for the model: `bit_identity_written_extremes` writes the state every window reaches into the model and into the design alike, steps four real frames at the extremes from it under each head, and compares every word; the model's records from that state are first held to closed forms. There the pooled sum and the hidden sum are at their last bits, and the hidden value, between and the output sum at theirs. **What that concedes: the path to that state is not run.** A fault that exists only in how the full top fills a pool of 65,536 from empty is not seen there; the small top's own true extremes, run in full by real frames with each of nine stages narrowed by a bit and caught, are what stand for the path. And the state is the bench's to write: one wrong in the model and the design alike would be seen only by those closed forms.
14. **The index crosses 2^16, 2^32 and 2^63 from a state the bench writes** into the simulator and into the model alike, and real frames are stepped from there. The frames that would lead to that state are not run. An index past 2^64 is not reached (mod-b.md, L13); the RTL's would wrap.
15. **A shape the seeded generator does not draw is not run.** The hand-worked vectors of `vectors/` are not replayed through the RTL: the model is held to them by the first size, and the RTL to the model here.
16. **The first refusal is the one kept.** A host that does not read and clear after each operation sees only that one and a bit.
17. **The order of checks is held for ten pairs,** not for every pair.
18. **Outside its block the core is seen to do nothing at five offsets,** not at every one.
19. **A record put out between two pieces of a stream is seen by a count, not by the harness.** The count says that there was one too many in the test, not which one or what it held.
20. **No test writes to the shadow at the swap's own edge.** The verifier closed the shadow against the select before the frame instead of after it: a `shadow_begin` at that edge was then taken, nothing of the parcel's or of its own failed, and no record changed, since the words that follow are still refused. That fault is not seen here.
21. **Every true-extreme stream of these benches uses the pass rectifier.** Abs at the most negative filter sum, at an extreme, is not driven by them. The verifier drove it on the small top (samples lowest, coefficients highest, the build's most pool and units, between abs) and its 1,084 records were the model's; that stream is in the round's report and not in this tree.
22. **No bench reads the widths of the small top, and the row sum's width is read back on neither top.** On the small top the narrowed-stage mutants stand for the widths: each of nine stages, a bit narrower, is caught at the record where it first needs that bit. The verifier worked all forty widths from the model's ranges and found them equal.
23. **What this bench holds at sampled sizes, it holds at those sizes and at no other.** The example the second verifier built: a commit at index 0 must mark no output as settling, and `bit_identity_swap_at_zero` drives it at pools of 2, 3, 4, 5 and 8. A core that marks settling at index 0 for one other pool size alone, 6 say, or 1,024, passes. The same sentence is true of every property held here at chosen sizes: `bit_identity_swap` at pools of 1, 2, 3, 5 and 7; the seeded shapes, whose pools can be 1, 2, 3, 5 or 8, whose taps on the small top can be 1, 2, 5 or 6, and whose shifts can be 0 to 12, which is what the generator can draw and not a count of what its seeds did draw; the epoch across four lines and the index across three; and how many hidden units are made to overflow at once, by construction, on the small top: one, two and all three. What a seeded shape overflows is whatever it draws. A fault that depends on a size or a value between the samples is not seen. No design holds such a fault by accident, and no sampling shows its absence.
24. **Nothing here is evidence about sensitivity.**

## 11. What it costs, as far as a count can say

Counted, at the definition's maxima; no slice, no look-up table and no clock is claimed. A bank is 2,252 weights of 18 bits, 40,536 register bits, and there are two; the multipliers read them through that many two-way mux bits. The head is 192 multipliers of 18 by the pooled value's width and 12 of 18 by 65 (head.md, HD7); the one route adds none. A hidden multiplier's width follows from the pooled value's, which follows from the sample's and the coefficient's bits and the logarithms of the taps, of a filter's rows and of the pool. `core_head` is a module of its own with registered inputs and a registered score, and both banks' head weights at its ports: the choice between them is made inside it, by the frame's bit.

## 12. Claims register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| C1 | At the definition's maxima the nine stage widths are the model's: 34, 41, 41, 57, 77, 64, 65, 85, 64 under `s16x1` and 42, 50, 50, 66, 85, 64, 65, 85, 64 under `s24x3` | MEASURED | `python tools/check_rtl.py rtl-benches --root . --state <a folder>`, 2026-11-23: the test `widths_are_the_models` of `bench_core_max` passing under both profiles; it reads each elaborated localparam and holds it against `detector.widths` and `detector.hidden_widths` | that test failing |
| C2 | A row of 128 taps is 41 and 49 bits | READ | [mod-b.md](../model/mod-b.md), row B4 | that row |
| C3 | The latency is 11 clocks on both tops under both profiles | MEASURED | the same command: `latency_is_eleven_clocks` of `bench_core` and of `bench_core_max` passing; the mutant `one-stage-longer` failing it with latencies of [12] | those tests |
| C4 | The fabric raises nineteen refusal names | COMPUTED | counted from the chain of `wcode` in `rtl/core/core.sv`, nineteen lines, and from section 7's table; `bench_core_control.py` asserts its case table has exactly these nineteen | a recount |
| C5 | The control block is 22 rows from 0x080 to 0x118 | READ | `spec/constants.py`, `REGISTERS`, at the commit this page was written on | that file |
| C6 | On an unbroken stream a shadow write is refused six clocks after the edge that takes a swap's first frame, and taken at seven | MEASURED | the same command: `shadow_closes_and_opens` passing under both profiles; `shadow-not-closed` failing it at six (0 where SWAP_PENDING is expected) and `shadow-closed-too-long` at seven (SWAP_PENDING where 0 is) | those tests |
| C7 | A weight set at the definition's maxima is 2,252 words, and a bank 40,536 bits | COMPUTED | 16 x 128 + 12 x 16 + 12; x 18 | arithmetic |
| C8 | The model's run at the true extremes is 65,663 frames; the small top's own is 1,029 | COMPUTED | `tests/test_mod_b_overflow.py`, `n = C.MAX_TAPS + C.MAX_POOL - 1`; 6 + 1,024 - 1 | arithmetic |
| C9 | One mutant's run cost about 9 seconds of wall time on the small top under `s16x1`, on a desktop that other work was loading | MEASURED | a trial of the bench with twenty mutants through `tools/check_rtl.py rtl-benches` on a copy of the tree, 2026-11-23: twenty results files written between 17:02:45 and 17:05:47 | a rerun |
| C10 | The 47 mutants are section 9's table, twenty-three under `s16x1` and twenty-four under `s24x3` | READ | `rtl/tb/benches.toml` | a recount of that file |
| C11 | Icarus Verilog 12.0 took every construct of the three files as first written | MEASURED | the first trial of `bench_core`, 2026-11-23 17:01: an empty build log and "2 test(s) passed" | another simulator |
| C12 | This parcel's six rows are 92 tests, 23,208 records and 47 mutant runs, and cost 110 seconds of wall time in one trial, on a desktop other work shares | MEASURED | `tools/check_rtl.py rtl-benches` on a copy of the tree whose manifest held the six rows alone, 2026-11-23 19:14, after the three verifiers' holes were closed: "92 test(s) passed in 6 run(s) of 6 bench(es); 23208 record(s) identical to the model's, word for word; 47 mutant run(s) each failed as named", 109.6 s | a rerun |
| C13 | With the foundation's bench the stage's line on this tree is 104 tests in 8 runs of 7 benches, 32,168 records and 61 mutant runs | COMPUTED | C12, and [README.md](README.md)'s rows R3 and R5: 92 + 12, 6 + 2, 6 + 1, 23,208 + 8,960, 47 + 14 | the line `python tools/check_rtl.py rtl-benches --root . --state <a folder>` prints |
| C22 | With `overflow-is-a-parity`, under `s24x3`, nine streams of `bit_identity_extremes` are identical to the model's and the tenth, every unit of three but unit 0, lacks the flag at record 5 where the model has it. Record 5 is where two units first stop fitting there: 4 filters of 5 taps under a pool of 4 hold 4 x 17 = 68 extreme products at output 5 and 4 x 14 = 56 at output 4, and 64 is the most that fits | MEASURED | the trial of C12: that mutant's evidence file, one MISMATCH line and nine IDENTICAL lines; the arithmetic is COMPUTED from the stream's shape | a rerun |
| C21 | With `overflow-not-from-the-last-unit` the stream of unit 2 alone, of 3, lacks the flag at record 821 where the model has it | MEASURED | the trial of C12 at 18:41: that mutant's evidence line | a rerun |
| C19 | Each of the verifier's four faults now fails a test of this bench: the upper word reads 0x5 where the model's index gives 0x1; record 0 has the settling flag where the model has none; record 821 lacks the overflow flag the model has; record 20 has epoch 0 where the model has 4294967295 | MEASURED | the trial of C12: the evidence lines of `commit-at-upper-reads-lower`, `settling-at-index-zero`, `overflow-from-unit-zero-only` and `swap-epoch-before-the-frame` | a rerun |
| C20 | Before those four tests, the parcel's whole gate passed with the first fault in the design, 98 tests and 55 mutant runs; and no test failed on the other three in the four rows the verifier ran them against | READ | the round's report VRTLB, its findings b1 and b4 and its table of survivors, and the lead's ruling after it | that report |
| C14 | With `record-at-a-commit` the design put out 678 records in `bit_identity_swap` and the comparisons held 660 | MEASURED | a trial as C12's, 2026-11-23 17:28: that mutant's log, the assertion's message | a rerun |
| C16 | On the full top, a thousand frames at the largest shape cost 7.8 s of wall time under `s16x1` and 8.4 s under `s24x3` for the constant extreme stream, and 8.2 s and 9.2 s for a random one, each with a load of 0.4 s in it; on a desktop other work shares | MEASURED | a bench of the parcel's scratch folder, NOT in the tree, so not to be rerun from a clone: three tests on the full top through `tools/check_rtl.py rtl-benches` on a copy, 2026-11-23 17:37 and 17:38; the time cocotb prints for each test (0.36, 8.20, 7.77 and 0.41, 9.22, 8.43 s) | a thousand frames at the largest shape, timed again |
| C17 | The model's run at the true extremes, 65,663 frames, would cost about eight minutes under `s16x1` and nine under `s24x3`, for each head | COMPUTED | C16 and C8: (7.77 - 0.36) x 65.663 = 487 s; (8.43 - 0.41) x 65.663 = 527 s | that run, made |
| C18 | At the definition's maxima under `s16x1`, with every head weight at its lowest, a pooled sum one bit narrower gives the model's records at the extreme: the mutant survived the first two streams of `bit_identity_written_extremes` | MEASURED | a trial as C12's, 2026-11-23 17:40: "MUTANT-SURVIVED" for `narrow-pool` on `core-max-s16x1`; with the stream of one head weight added it fails there, +2^59 where the model has -2^59 | that mutant, once the stream is taken out |
| C15 | A core whose overflow flag was not sticky passed the small top's bench as first written | MEASURED | two trials through `tools/check_rtl.py rtl-benches` on scratch copies, 2026-11-23 17:19 and 17:21: "MUTANT-SURVIVED" for `bit_identity_random`, `bit_identity_extremes`, `bit_identity_swap_on_the_edge` and `bit_identity_counters` under both profiles and for `bit_identity_swap` under `s16x1` | the same mutant against the first bench |

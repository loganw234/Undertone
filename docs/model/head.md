# HEAD: the detector head's hidden layer

Written by parcel HEAD in round 2, 2026-11-23. Labels are those of [the design](../studies/D0-rough-design.md): MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure on this page is in the register at the end.

Round 1's head was one linear layer with no bias ([mod-b.md](mod-b.md), section 1, step 4). The owner's word of 2026-11-23 was "Hidden layer from the start if simple enough, otherwise without for the initial design." [The plan of round 2](../plans/R2-fabric-in-simulation-and-the-learner.md) fixed what "simple enough" means before any design was drawn: four parts, all of which must hold. This page is the hidden layer built to that test, in the reference model: `model/detector.py` and `model/weights.py`.

**What it is for in this round:** to exist in the model, so that the RTL is written for one head and not rewritten for another. It is held bit for bit. It is not trained, and nothing here is evidence that it helps detection: that question has other authorities (D0, section 2).

## 1. The arithmetic

Integers only. Everything before the head is as it was: K filters, and for output index i the pooled values z_k[i]. A hidden layer has H units, 1 <= H <= MAX_HIDDEN. Its weights are g[j][k], H rows of K, and o[j], H of them, each a signed integer of COEFF_BITS. A blob carries two shifts, the hidden shift q in 0..MAX_HIDDEN_SHIFT and the score shift s as before, and one code for what stands between the layers.

Round 1's step 4 becomes four. Step 5 does not change.

- **4a. Hidden sum.** u_j[i] = the sum over k of g[j][k] * z_k[i]. Exact. It is round 1's head sum under the unit's own weights: the same code (`Core._head`), the same range and the same declared width.
- **4b. Hidden value.** t_j[i] = floor(u_j[i] / 2^q), an arithmetic shift right, **reduced to the score field's width, two's complement**. This is the layer's one shift and its one width that is a choice. **It is a second rounding in the datapath, toward minus infinity like the score's:** -11 shifted by 1 is -6.
- **4c. Between.** b_j[i] = t_j[i] under code `pass`, the absolute value of t_j[i] under code `abs`. Exact. The codes are the rectifier's, from the definition; there is no third.
- **4d. Output sum.** a[i] = the sum over j of o[j] * b_j[i]. Exact.
- **5. Score.** v[i] = floor(a[i] / 2^s), into the record's score field, as before.

**Widths.** `detector.hidden_ranges(profile)` and `detector.hidden_widths(profile)` derive the three new ones from `spec.constants`; nothing is typed in. `detector.ranges` and `detector.widths` are as round 1 left them.

| stage | extreme inputs | worst value | `s16x1` | `s24x3` | can it overflow |
|---|---|---|---|---|---|
| hidden sum | round 1's head sum, under the unit's weights | -2^76, -2^84 | 77 bits | 85 bits | no |
| hidden value | that, shifted by q | the choice: every value the score field holds | 64 bits | 64 bits | **yes: the flag** |
| between | the lowest hidden value, under abs | +2^63 | 65 bits | 65 bits | no |
| output sum | MAX_HIDDEN units at that, every head weight COEFF_MIN | 12 * 2^80, either sign | 85 bits | 85 bits | no |
| score | the output sum shifted by s | the record's field | 64 bits | 64 bits | yes: the flag, as before |

- **The hidden value's width is the score field's, derived from it, with no constant of its own.** Section 2 says why. A test changes the score field in a patched definition and sees the hidden width move with it.
- **When a hidden value does not fit,** t_j is floor(u_j / 2^q) modulo 2^64 as two's complement, and the sticky `overflow` flag is set in that record and every later one, across swaps: the same flag and the same rule as the score's. The value is still defined bit for bit, and what follows is computed from it exactly.
- **Between needs 65 bits** because the absolute value of -2^63 is +2^63. That is derived, not chosen, as the rectifier's width is.
- **The output sum needs 85 bits under both profiles:** nothing after the hidden value depends on the sample format.
- **What a configuration can do about overflow.** A hidden shift of 13 under `s16x1`, or 21 under `s24x3`, makes overflow of a hidden value impossible; with it, a score shift of 21 makes overflow of the score impossible. Both are inside their bounds.

## 2. Today's head is one setting of it

**The setting.** Round 1's head with weights h and score shift s is the head with: one unit; g[0] = h; hidden shift q = s; `pass` between; o = (1); score shift 0.

**Why every score is the same integer.** u_0 is the same sum of the same products as round 1's head sum. t_0 is that sum shifted by s and reduced to 64 bits: round 1's score field, wrapped the same way when it does not fit, with the flag rising at the same outputs. Pass leaves it. Once 1 * t_0, shifted by 0 and reduced to 64 bits, it is unchanged and raises nothing, because it already fits. The epoch and the settling flag are the store's and are not touched.

**Why 64.** It is the least hidden width for which that holds for every configuration. With a hidden value of W bits, W below 64, a score of 2^(W-1) fits the record under round 1's head and would raise the flag and wrap in the hidden value. A narrower hidden value would make the old head a bypass round the hidden stages: exact only because it is separate.

**Two routes in the model, and what holds them together.** A version 1 blob does not take the setting's route. It takes round 1's two lines, `_score(_head(pooled, head))`, as they were, because MOD-B's overflow tests reach into a version 1 core's `_head`, `_score` and `shift` and must pass unchanged. So "the old head is one setting of the new" is held by a gate, not by construction:

- every hand-worked case of round 1's `vectors/mod-b/datapath.json` and `swap.json`, rewritten as its setting and run through the hidden stages, gives round 1's hand-worked records, byte for byte;
- so it does at the score's boundary, where the field wraps, against the closed form;
- a seeded sweep of random configurations with no hidden layer, some with a swap, gives the same records on both routes. **That sweep is an agreement of two routes in one model, not an authority.**

A fabric may build one route: a version 1 blob loaded as its setting needs no head of its own.

## 3. The blob, version 2

Version 1 is unchanged, byte for byte, and is what `pack` writes whenever there is no hidden layer. Version 2, every integer little-endian:

    magic "UNDTBLOB"   8 bytes
    version            u16, 2
    name length        u8
    profile name       ASCII
    filters K          u16
    taps T             u16
    rectifier          u8      the filter bank's
    score_shift        u8
    pool P             u32
    hidden H           u16     1..MAX_HIDDEN
    hidden_shift       u8      0..MAX_HIDDEN_SHIFT
    between            u8      a code of spec.constants.RECTIFIERS
    K channel masks    u16 each
    the rows           as version 1
    H hidden units     unit 0's K weights in filter order, then unit 1's, ...; i32 each
    H head weights     i32 each: one for each hidden unit
    SHA-256            of every byte before it

The hidden layer's shape lies in the four bytes that version 1 reserves, so the fixed header has one length in both versions. Version 2 has no reserved field: every value of every byte is meant or refused.

- `weights.pack(profile, filters, head, rectifier, pool, score_shift, hidden=None, hidden_shift=None, between=None)`. With `hidden` None it is round 1's call and writes version 1. With `hidden` a list of H units of K weights it writes version 2, and `head` is the H head weights.
- `weights.unpack` of a version 1 blob gives round 1's seven keys; of a version 2 blob, those and `hidden`, `hidden_shift` and `between`.
- `weights.shape` of a configuration with a hidden layer is round 1's tuple with (H, hidden shift, between) after it. `Store.step()` gives four values as before; with a hidden layer the second is the pair (hidden units, head weights).
- `weights.matched_filter` writes version 1, as before.

**Each reader with the other's blob.** Round 1's code refuses any version but 1, BLOB_FORMAT, after the hash. This model reads both. **A head with no hidden layer has one blob, the version 1 one:** version 2 with H = 0 is refused, BLOB_FORMAT.

**Every new way a blob can be wrong.** Three names are new, one for each new field of the shape.

| name | what raises it |
|---|---|
| SHAPE_HIDDEN (new) | `pack`: hidden units that are not a list of 1..MAX_HIDDEN; a hidden shift or a between given with no hidden layer. `unpack`: H past MAX_HIDDEN |
| SHAPE_HIDDEN_SHIFT (new) | `pack` and `unpack`: a hidden shift that is not an int in 0..MAX_HIDDEN_SHIFT |
| SHAPE_BETWEEN (new) | `pack` and `unpack`: a between that is not a declared rectifier code |
| BLOB_FORMAT | `unpack`: version 2 with H = 0; a version that is not 1 or 2; a length that disagrees with the header, which now counts H * K hidden weights and H head weights |
| RESERVED_BITS | `unpack`: version 2's layout under the number 1, where the layer's shape lies in the reserved field |
| WEIGHT_COUNT | `pack`: a unit that is not a list of exactly K weights; a head that is not exactly H weights |
| WEIGHT_RANGE | `pack` and `unpack`: a hidden weight or a head weight that is not an int inside COEFF_MIN..COEFF_MAX |
| SWAP_SHAPE | `write_shadow`: a blob with a hidden layer onto a core without, or the other way; another H, hidden shift or between |

**The order of checks** is part of the definition, and a test holds the neighbouring pairs it lists. `unpack`: as round 1 to PROFILE_UNKNOWN; then RESERVED_BITS (version 1) or BLOB_FORMAT for H = 0 (version 2); SHAPE_FILTERS, SHAPE_TAPS, SHAPE_RECTIFIER, SHAPE_SHIFT, SHAPE_POOL; then, for version 2, SHAPE_HIDDEN, SHAPE_HIDDEN_SHIFT, SHAPE_BETWEEN; then as round 1. `pack`: as round 1 to SHAPE_TAPS; SHAPE_HIDDEN; WEIGHT_COUNT; SHAPE_RECTIFIER, SHAPE_SHIFT, SHAPE_POOL; SHAPE_HIDDEN_SHIFT, SHAPE_BETWEEN; WEIGHT_RANGE.

## 4. The swap

A swap changes weights and not shape. **The hidden units' weights and the head weights are weights:** they exchange with the coefficients, whole, at the swap's index. **H, the hidden shift and what stands between are shape.**

**Nothing mixes that did not mix before.** The hidden layer remembers nothing: no delay line and no running sum. Each output's hidden sums and its output sum are made from that output's pooled values under one weight set. The pool is still the only stage that mixes two sets, `settling` marks the same P - 1 outputs, and with a pool of 1 there are none.

For a fabric: however many pipeline stages its head has, the choice of weight set travels with the sample.

## 5. The gates, and what holds them

No new row in `tests/gates.toml`: the tests claim four gates that exist. The known answers are under `vectors/head/`, worked by hand with the sums in the file: [datapath.json](../../vectors/head/datapath.json), [swap.json](../../vectors/head/swap.json), [blob.json](../../vectors/head/blob.json), [widths.json](../../vectors/head/widths.json). Beside them `direct_records` and `forge` in `tests/test_head_support.py` write the head's definition and the blob's layout a second time, using nothing of the two modules, and are themselves held to the hand-worked vectors. Every test that involves a stream or a shape runs under both profiles.

| gate | what HEAD's tests hold | the faults its controls plant |
|---|---|---|
| reference-model | records with a hidden layer equal the hand-worked vectors and, on 60 seeded shapes a profile and on the largest layer, the second definition; round 1's hand-worked cases as their setting, through the hidden stages, equal round 1's records; the setting at the score's boundary equals the closed form; the seeded sweep of both routes | a head nearly the old one, four ways: one hidden weight off by one, the hidden shift off by one, a head weight of 2 for 1, a score shift of 1 for 0; a between that always passes, and one that always folds; a hidden shift that rounds toward zero, and none at all; head weights on the wrong units; unit weights on the wrong filters; a score shift toward zero; **one flipped bit** of every hidden weight and every head weight |
| overflow | the three widths equal the hand-worked ones; the hidden width follows the score field; at the true extremes the shipped core raises no flag and each new stage reaches its last bit; the flag rises at the first hidden value that does not fit, the value wraps as defined, and the flag stays across a swap | a hidden shift one bit short; a score shift one bit short; each of the three new stages one bit narrower |
| refusal | every case of one table is refused under its own name; what is just inside each new bound is accepted and `pack` writes the layout; each version is read as itself; the order of the new checks; a refused shadow changes nothing | for every case: a model that accepts it, and one that refuses it under another name; the shipped code reading a definition whose MAX_HIDDEN or MAX_HIDDEN_SHIFT is one higher |
| swap | records equal the hand-worked swap vectors; with no pool every score equals the second definition under the weights its epoch names; `settling` marks exactly the outputs the pool mixes | the head weights one output late, and the hidden weights one output late, each caught by the vectors and by the epoch check |

Three tests are there to show that a control's choice of fault matters: a flipped bit behind a zero head weight is not seen; half the head's weights late is not seen when the swap is to the weights already active; a narrowed between stage is not seen under pass.

**How the overflow gate reaches the true extremes.** Not by a run of its own. The hidden layer remembers nothing, so the state a full run reaches can be written down: the test writes a version 2 core's delay lines, pool windows and pool sums from closed forms, and from there the core's real `step` runs end to end on the extreme frame. That the written state is the one a full run reaches is checked against the pooled values MOD-B's full run of the shipped core kept.

## 6. What the head costs a fabric

Counted and sized from the widths above, at the definition's maxima. It is a count of multipliers and their operands, not an estimate of slices.

| | count | operands, `s16x1` | operands, `s24x3` |
|---|---|---|---|
| multipliers into the hidden units | 16 * 12 = 192 | 18 by 57, signed | 18 by 66, signed |
| multipliers out of them | 12 | 18 by 65, signed | 18 by 65, signed |
| all | 204 | | |

And for each of the 12 units: a sum of 16 products into 77 or 85 bits; an arithmetic shift right by 0..31; a reduction to 64 bits that raises the flag; a conditional negation into 65 bits. Then one sum of 12 products into 85 bits, and the score's shift and field, whose input is 85 bits under both profiles.

Round 1's head is 16 multipliers of 18 by 57 or 66. They are hidden unit 0's, if a fabric loads a version 1 blob as its setting.

**Part 3 of the plan's test** is this count: 204 multipliers against a tenth of the bank's 2,048. One unit more would be 221.

## 7. Limits

Each is stated by the behaviour it concedes.

- **HL1. One thing stands between, for the whole layer, and it is pass or abs. There is no clamp.** With abs a unit answers -x as it answers x: a unit that fires when its sum is positive and is silent when it is negative cannot be built. With pass the layer is linear but for its rounding. Units cannot mix the two.
- **HL2. No bias, one shift, dense.** A hidden unit has no bias, as the head has none. The hidden shift is one for the whole layer. Every unit has a weight for every filter; a zero weight is how it ignores one.
- **HL3. The old head as a setting is tested, not proven.** A version 1 blob takes round 1's two lines; its setting takes the hidden stages. Their agreement is held on round 1's hand-worked cases, at the score's boundary, and on the seeded sweep. A blob outside those on which the two routes differ would pass every gate. The sweep compares two routes of one model: a fault both share passes it.
- **HL4. The agreement is of scores, not of blobs or shapes.** A head with no hidden layer and its setting are two blobs with two hashes that give the same records; nothing refuses the second. A core built from one cannot be swapped to the other: SWAP_SHAPE. Two hidden layers that differ only in the order of their units also give the same records.
- **HL5. The flag does not say which stage raised it.** A hidden value and a score raise the same bit. After a hidden value has wrapped, the output sum is made from the wrapped value: the score is defined bit for bit, and is not a score. A run in which the flag rose is a marked run, as in mod-b.md's L2.
- **HL6. A core with a hidden layer is not run through the frames that lead to the extreme.** The overflow gate writes the extreme state and steps from it. A fault that exists only in how a version 2 core fills its delay lines and its pool from empty, at the extremes, is not planted and would not be seen there; the bank's code is the code round 1's full run exercises.
- **HL7. The widths are for the definition's maxima.** The model does not refuse a configuration whose hidden value can overflow: it raises the flag when one does. The output sum's 85 bits are for MAX_HIDDEN = 12.
- **HL8. Every control plants the faults listed in section 5 and no others,** and the second definition is the same author's: `direct_records` and `forge` share no code with the model, but one parcel wrote both. Only the hand-worked vectors are independent of that, and they are small: at most 2 filters, 3 units, a pool of 2 and 5 frames.
- **HL9. A third declared rectifier code would pass silently.** `Core._between` folds under `abs` and passes under anything else, as `Core._rectify` does. The definition declares two codes and the lead's foundation test pins them.
- **HL10. Nothing is trained, and nothing here is evidence about sensitivity.** No rule quantises a hidden weight or a head weight. D0's row D8 holds for the matched-filter configuration only, which has no hidden layer.
- **HL11. The order of the new checks is held for the pairs the test lists,** not for every pair.
- **HL12. The flipped-bit control uses one shape:** two filters, three units, a pool of 2, under both things that can stand between and two pairs of shifts. A flip that hides in another shape is not planted.

## 8. Claims register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| HD1 | The three widths a hidden layer adds are 64 (hidden value), 65 (between) and 85 (output sum) signed bits under both profiles | COMPUTED | `python -c "from model import detector; print(detector.hidden_widths('s16x1'), detector.hidden_widths('s24x3'))"`, and by hand in `vectors/head/widths.json` | `test_gate_overflow__the_hidden_layers_widths_equal_the_hand_worked_widths` failing |
| HD2 | A hidden unit's sum has round 1's head width: 77 bits under `s16x1`, 85 under `s24x3`, with extremes -2^76 and -2^84 | READ | [mod-b.md](mod-b.md), rows B1 and B2, and `vectors/mod-b/widths.json` | the same test, which compares the two |
| HD3 | A hidden shift of 13 (`s16x1`) or 21 (`s24x3`) brings the extreme hidden sum to exactly -2^63, and one less does not fit; a score shift of 21 then brings the extreme output sum inside the field, and 20 does not | COMPUTED | 77 - 64, 85 - 64 and 85 - 64, from HD1 and HD2; 12 * 2^80 / 2^21 = 3 * 2^61 | `test_control_overflow__a_hidden_shift_one_bit_short_raises_the_flag_at_the_true_extremes` and the control beside it for the score shift |
| HD4 | The extreme output sum is 12 * 2^80 in magnitude, which is 3 * 2^82 and needs 85 bits | COMPUTED | 12 units * 2^17 * 2^63; 3 * 2^82 lies between 2^83 and 2^84 | arithmetic; `test_gate_overflow__a_hidden_layer_at_the_true_extremes_fits_every_width_and_raises_no_flag` |
| HD5 | 64 bits is the least hidden width at which the setting of section 2 gives round 1's score and flag for every configuration | COMPUTED | the argument of section 2; below 64 the counter-example is a score of 2^(W-1) | a configuration whose two routes differ: the three tests of section 2 |
| HD6 | At the maxima the head is 204 multipliers, at most a tenth of the bank's 2,048; 13 units would be 221 | COMPUTED | (16 + 1) * 12 and (16 + 1) * 13 against 16 * 128 / 10 = 204.8 | `test_head_the_bounds_the_design_rests_on` |
| HD7 | A fabric's head at the maxima is 192 multipliers of 18 by 57 (`s16x1`) or 18 by 66 (`s24x3`) and 12 of 18 by 65; round 1's head is 16 of the first kind | COMPUTED | MAX_FILTERS * MAX_HIDDEN and MAX_HIDDEN; COEFF_BITS; the pool's width from mod-b.md rows B1 and B2; HD1 | arithmetic; a fabric that builds the head another way |
| HD8 | The maxima this page is worked at: 12 hidden units, a hidden shift of at most 31, 18-bit weights, 16 filters, a score field of 64 bits | READ | `spec/constants.py` at the commit this page was written on: MAX_HIDDEN, MAX_HIDDEN_SHIFT, COEFF_BITS, MAX_FILTERS, RECORDS | the definition changing: every COMPUTED row above is then to be worked again |
| HD9 | HEAD's tests are 124, of which 55 hold a gate and 58 are negative controls | MEASURED | `python -m pytest --collect-only -q -p no:cacheprovider tests/test_head_support.py tests/test_head_reference.py tests/test_head_overflow.py tests/test_head_refusal.py tests/test_head_swap.py`, counted by name, 2026-11-23 | a recount |
| HD10 | The refusal table holds 203 cases under each profile | MEASURED | `python -m pytest -q -s -p no:cacheprovider tests/test_head_refusal.py -k accepts`, 2026-11-23, which prints the count for each profile | a rerun |
| HD11 | Every one of 162 single-bit flips of a hidden or head weight changed at least one record, in each of 8 runs: two profiles, two codes between, two pairs of shifts | MEASURED | `python -m pytest -q -s -p no:cacheprovider tests/test_head_reference.py -k one_flipped_bit`, 2026-11-23 | a rerun; a flip that leaves every record unchanged |
| HD12 | The seeded sweep ran 100 configurations a profile on both routes with every record equal; 52 (`s16x1`) and 49 (`s24x3`) had a swap; none under `s16x1` and 12 under `s24x3` raised the overflow flag | MEASURED | `python -m pytest -q -s -p no:cacheprovider tests/test_head_reference.py -k both_routes`, 2026-11-23 | a rerun |
| HD13 | The hand-worked cases with a hidden layer hold at most 2 filters, 3 units, a pool of 2 and 5 frames | READ | `vectors/head/datapath.json` and `vectors/head/swap.json` | a reading of those files that finds another count |
| HD14 | Round 1's code refuses any version but 1 as BLOB_FORMAT | READ | `model/weights.py` at commit `50ff664`, lines 215 and 216 | that file at that commit |

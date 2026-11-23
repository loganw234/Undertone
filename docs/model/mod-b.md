# MOD-B: the detector core, the weight store and the scorer

Round 1's reference model, the part that turns a stream of frames into score records. Three modules, integers and the standard library only:

- `model/detector.py`: the datapath (filter bank, rectifier, pool, head, score) and its widths.
- `model/weights.py`: the quantising rule, the configuration blob, and the store with its swap.
- `model/scorer.py`: the threshold, the histogram and the event records.

It defines, bit for bit, what the fabric must later do. It says nothing about how well anything detects: that question has other authorities ([D0](../studies/D0-rough-design.md), section 2).

Labels are D0's. Every figure below sits in the claims register at the end. The seam conventions (a) to (d) are the lead's and are stated in `docs/model/conventions.md` on the round branch; where this page restates (b), (c) or (d) it is meant to agree with that page, and that page wins if it does not.

## 1. The datapath

A profile gives the sample width and the channel count C. A shape gives K filters of T taps, for each filter the channels it reads, a rectifier, a pool length P and a score shift s. A weight set gives, for filter k, a row of T coefficients w[k][c] for each channel c the filter reads, and one head weight h[k]. Coefficients and head weights are signed integers of COEFF_BITS.

Frame i is (x_0[i], ..., x_{C-1}[i]), and x_c[m] = 0 for m before the stream's start. For output index i:

1. **Filter bank.** y_k[i] = the sum, over the channels c that filter k reads and over j = 0..T-1, of w[k][c][j] * x_c[i - (T-1) + j]. **Coefficient 0 meets the oldest sample of the window and coefficient T-1 the newest, x[i]** (convention (b)). Exact.
2. **Rectifier.** r_k[i] = y_k[i] in mode `pass`, the absolute value of y_k[i] in mode `abs`. Exact.
3. **Pool.** z_k[i] = r_k[i] + r_k[i-1] + ... + r_k[i-P+1], with r_k[m] = 0 before the stream's start. A moving sum, one output per input. Exact.
4. **Head.** a[i] = the sum over k of h[k] * z_k[i]. Exact.
5. **Score.** v[i] = floor(a[i] / 2^s). **This is the one rounding in the datapath: toward minus infinity**, an arithmetic shift right. -13 shifted by 1 is -7, not -6.

The record is {index: i, epoch, flags, score}. Its index is the index of the newest sample it used.

Written as a convolution, y[i] = sum of c[j] * x[i-j], the same filter has its coefficients reversed. This model uses the form above.

**The matched-filter configuration** is one setting of those five steps, not another path: one filter, `pass`, P = 1, s = 0 and a head weight of the integer 1 give score[i] = y_0[i]. Its coefficients are the pulse **in order**, quantised (section 6). A pulse whose first sample is at stream index j is fully under the filter at score index j + T - 1. `weights.matched_filter(profile, pulse, gains)` builds it.

**More than one channel** (convention (d)). A filter names the channels it reads and holds one row for each; its output is the sum over those channels. A channel it does not read is arithmetically a zero row. The same code runs under both profiles; under `s16x1` every filter reads channel 0.

**Why it is shaped this way.** The pool is a moving sum because it is exact, forgets completely after P samples, and runs at one sample per clock with a delay line. The shift comes last, after every sum, so that there is one rounding and it is in one place. The head has no bias because the threshold does that job.

## 2. Widths

In the shape of D0 row D4: the extreme inputs, the worst value, the bits it needs. S is the largest sample magnitude, reached at sample_min; M = 2^17 is the largest coefficient magnitude, reached at COEFF_MIN. Both factors negative gives the largest product, +S*M.

| stage | extreme inputs | worst value | `s16x1` | `s24x3` | can it overflow |
|---|---|---|---|---|---|
| one product | sample_min * COEFF_MIN | +S*M | 2^32: 34 bits | 2^40: 42 bits | no |
| filter sum | MAX_TAPS taps and every row of one filter at that product | rows * 128 * S*M | 2^39: 41 bits | 3 * 2^47: 50 bits | no |
| rectifier | the same | the same magnitude | 41 bits | 50 bits | no |
| pool sum | MAX_POOL of those in a row | 65,536 times the filter's | 2^55: 57 bits | 3 * 2^63: 66 bits | no |
| head sum | MAX_ROWS rows at that extreme, every head weight COEFF_MIN | -M * 16 * 65,536 * 128 * S*M | -2^76: 77 bits | -2^84: 85 bits | no |
| score | the head sum shifted by s | the record's field | 64 bits | 64 bits | **yes: the flag** |

- **D0 row D4 is confirmed for 16 bits:** 128 products of at most 2^32 reach 2^39, and +2^39 needs 41 signed bits. For 24 bits one row reaches 2^47 and needs 49; a filter across the three channels reaches 3 * 2^47 and needs 50.
- The head's bound counts rows, not filters: the sum over k of h[k] * z_k is at most M times (the rows in the shape) times one row's pooled extreme, and a shape has at most MAX_ROWS rows.
- **The mechanism.** The model reduces five values to their declared widths, two's complement: the filter sum, the rectified value, the pool sum, the head sum and the score. A reduction that changes the value raises the `overflow` flag, which then stays set in every later record of that core, across swaps. For the first four the declared width is the table's, so in the shipped core the reduction never changes anything. A single product is not reduced on its own; its row is the width a multiplier's output needs. `detector.widths(profile)` derives the widths from `spec.constants`; nothing is typed in.
- **The score is the one width that is a choice.** When v[i] does not fit 64 signed bits, the score field holds v[i] modulo 2^64 as two's complement, and the flag is set in that record and every later one. So the value under overflow is still defined bit for bit, and the fabric must match it. Once the true value is back in range the field is the true value again; the flag stays.
- **What a configuration can do about it.** With s = 13 under `s16x1`, or s = 21 under `s24x3`, no legal configuration can overflow the score. With s = 0 the matched-filter configuration cannot (41 or 50 bits).
- The score field stays 64 bits. Nothing narrower is asked for.

## 3. The configuration and its blob

A model is a configuration blob: a shape inside the definition's maxima, plus the weights, with a hash. `weights.pack(profile, filters, head, rectifier, pool, score_shift)` makes one; `filters` is a list of K dicts, each mapping a channel index to that channel's row. `weights.unpack(blob)` gives the parts back. **A core is built from a blob, and the shadow is written with a blob**, so every weight set that reaches the datapath has passed the hash and every check.

On disk, blob version 1, every integer little-endian:

    magic "UNDTBLOB"   8 bytes
    version            u16, 1
    name length        u8
    profile name       ASCII
    filters K          u16
    taps T             u16
    rectifier          u8      a code of spec.constants.RECTIFIERS
    score_shift        u8
    pool P             u32
    reserved           u32     zero
    K channel masks    u16 each: bit c set means the filter reads channel c
    the rows           filter 0's rows in ascending channel order, then filter 1's, ...;
                       a row is T coefficients, i32, oldest sample first
    K head weights     i32 each
    SHA-256            of every byte before it

**What bounds a shape.** K is at most MAX_FILTERS. T is at most MAX_TAPS. The **rows**, summed over the filters, are at most MAX_ROWS; each row is T multipliers, so no legal shape under any profile uses more than D0 row D3's multipliers. P is at most MAX_POOL and s at most MAX_SCORE_SHIFT.

## 4. The swap, per output sample

`weights.Store` holds an active weight set, a shadow, and an epoch that starts at 0, or at a start epoch given at construction.

- `write_shadow(blob)` replaces the whole shadow. The blob must have the running shape: profile, K, T, each filter's channels, rectifier, P and s.
- `commit(at)` schedules the swap **at output index `at`**: immediately before output `at` is computed, active and shadow exchange and the epoch rises by one. An index, and not "now", so that a replay swaps at the same sample. A commit for the next output is `commit(core.next_index)`.
- **Which outputs use which weights.** Every output before `at` uses the old coefficients and the old head and carries the old epoch. Every output from `at` on uses the new coefficients and the new head, on the samples already in the delay lines, and carries the new epoch. No filter sum and no head sum mixes two sets.
- **Which outputs mix.** The pool does. For `at` <= i <= `at` + P - 2, with `at` at least 1, the pooled sum holds rectified values made under the old coefficients and values made under the new. Those P - 1 outputs carry the new epoch **and the `settling` flag**. Their scores are still defined exactly and the fabric must match them. With P = 1, which includes the matched-filter configuration, no output mixes and the flag never rises.
- **Pending.** A swap is pending from its commit until the last output it mixes has been produced. A commit while one is pending is refused, SWAP_PENDING, so no output ever mixes three sets. A shadow write is refused, SWAP_PENDING, between a commit and its index, because the shadow is then what is about to become active; after the index it is allowed.
- After a swap the shadow holds the set that was active. A commit with no write since exchanges back to it.

## 5. The scorer

`Scorer(profile, threshold, pre, post, hist_lo, hist_shift, hist_bins)` is fed one (frame, score record) pair at a time, in stream order, and reads nothing else.

- **Counted records.** A record with `settling` set is left out of every count below and counted in `excluded`. A record with `overflow` set is counted like any other, and `overflow_at` is the index where the flag was first seen, whether or not that record was counted.
- **Threshold** (convention (c)). A counted record is above when its score is **strictly greater** than the threshold. `crossings` is the number of counted records that are above.
- **Events.** An event is captured at every counted record that is above and whose predecessor was not: not above, or not counted, or there was none. Every such rising crossing gives an event; capture windows may overlap; none is dropped.
- **When an event is complete.** An event appears in `events` once the record that supplies its last frame has been fed, or at `close()` if the stream ends first. With a `post` of 0 that record is the crossing's own, so the event is there before the next record is fed. Every event has the same configured `post`, so events complete in the order of their indexes; with a `post` of 0 no window is open when a record arrives.
- **An event record** is {index, epoch, score} of that record, `pre` = the frames captured before it (the configured `pre`, or fewer at the stream's start) and `post` = the frames captured after it (the configured `post`, or fewer at the stream's end). The frames themselves are kept beside the record, in `captures`.
- **Histogram.** `hist_bins` bins of width 2^`hist_shift`, the first starting at `hist_lo`. A counted score under `hist_lo` counts in `below`; one past the last bin counts in `above`. Nothing is dropped: below, the bins and above sum to the counted records.

## 6. The quantising rule

`weights.quantise(values)` is `spec/undertone.toml`'s rule: with m the largest magnitude in the set, each value v becomes the integer nearest v * (2^17 - 1) / m, a tie going to the even integer. It is worked as one exact fraction per value, in integers. Values are ints or `fractions.Fraction`; **nothing in `model/` creates or accepts a float**, and a caller holding one converts it with `Fraction(x)`, which is exact.

- A set is whatever one call is given. `matched_filter` makes one set of all the rows of its one filter.
- The result lies in -(2^17 - 1)..(2^17 - 1). The rule never produces COEFF_MIN.
- The reference pulse `e0` has no exact tie, so it cannot test the rounding. The frozen vectors carry sets that do.

## 7. Refusals

Each is `model.refusal.Refusal(name, detail)`. One row for each name, and beside it exactly what raises it.

| name | what raises it |
|---|---|
| BLOB_FORMAT | `unpack`, and so `Core`, `Store` and `write_shadow`: something that is not `bytes`; too few bytes to hold the fixed fields and a hash; another magic or version; a name length, a count of channel masks or a whole length that disagrees with the bytes that are there |
| BLOB_HASH | `unpack`: the last 32 bytes are not the SHA-256 of the rest. Checked before anything inside is read |
| PROFILE_UNKNOWN | `pack`, `matched_filter` and `Scorer`: a profile name that is not declared. `unpack`: a name in the blob that is not ASCII or not declared |
| RESERVED_BITS | `unpack`: any bit of the blob's reserved field. `Scorer.feed`: any reserved flag bit of the record it is fed |
| SHAPE_FILTERS | `pack`: filters that are not a list, or not 1..MAX_FILTERS of them. `unpack`: K outside 1..MAX_FILTERS |
| SHAPE_TAPS | `pack`: a first row that is not a list of 1..MAX_TAPS coefficients. `unpack`: T outside 1..MAX_TAPS. `matched_filter`: a pulse that is not a list of 1..MAX_TAPS samples |
| SHAPE_RECTIFIER | `pack` and `unpack`: a rectifier that is not one of the declared codes |
| SHAPE_SHIFT | `pack` and `unpack`: a score shift that is not an int in 0..MAX_SCORE_SHIFT |
| SHAPE_POOL | `pack` and `unpack`: a pool that is not an int in 1..MAX_POOL |
| SHAPE_CHANNEL | `pack`: a filter that is not a mapping from channels to rows, that reads no channel, or that names a channel the profile does not have. `unpack`: a channel mask of zero, or with a bit for a channel the profile does not have |
| SHAPE_ROWS | `pack` and `unpack`: more than MAX_ROWS rows in the shape |
| WEIGHT_COUNT | `pack`: a row that is not a list of exactly T coefficients, T being the first row's length; a head that is not a list of exactly K weights. Not raised by `unpack`: in a blob the same fault is a length that disagrees with the header, BLOB_FORMAT |
| WEIGHT_RANGE | `pack` and `unpack`: a coefficient or head weight that is not an int inside COEFF_MIN..COEFF_MAX |
| CHANNELS | `Core.step` and `Scorer.feed`, through `stream.check_frame`: a frame that is not a tuple with one value for each channel. `matched_filter`: gains that are not a list of one gain for each channel |
| SAMPLE_RANGE | `Core.step` and `Scorer.feed`, through `stream.check_frame`: a value in the frame that is not an int inside the profile's range |
| SWAP_SHAPE | `write_shadow`: a blob whose shape is not the running one |
| SWAP_PENDING | `commit`: a swap is pending. `write_shadow`: a swap is committed and its index has not been reached |
| SWAP_INDEX | `commit`: an index that is not an int, that has already been produced, or that the index field cannot hold |
| SWAP_EPOCH | `commit`: the epoch is already the last its field holds. `Core` and `Store`: a start epoch that is not an int the field holds |
| SCORER_THRESHOLD | `Scorer`: a threshold that is not an int the score field holds |
| SCORER_WINDOW | `Scorer`: a `pre` or a `post` that is not an int the event record's field holds |
| SCORER_BINS | `Scorer`: `hist_bins` outside 1..MAX_HIST_BINS, `hist_shift` outside 0..63, or a `hist_lo` that is not an int the score field holds |
| RECORD_ORDER | `Scorer.feed`: a record whose index is not the next one; any record after `close()` |
| RECORD_FIELD | `Scorer.feed`, through `records.check`: a record that is not a dict of exactly a score record's fields, each an int that fits |
| QUANTISE_INPUT | `quantise`: a set that is not a non-empty list or tuple, an all-zero set, a value that is not an int or a Fraction. `matched_filter`: a gain or a pulse sample that is not an int or a Fraction; gains that are all zero |

Where a row says a list, a tuple is taken as well. A refused frame advances nothing, in the core and in the scorer, and the records before it stand. What `stream.check_frame` checks is the lead's to say: today it takes any instance of `tuple`, a subclass included, of the right length whose values are ints in range. This page claims nothing about a frame beyond that.

**The order of checks is part of the definition.** `test_gate_refusal__the_order_of_checks_is_the_documented_one` holds each neighbouring pair of the lists below, with a call that has both things wrong. SHAPE_ROWS's place is held under `s24x3` only, where it can be reached. The order inside `Scorer.feed` is not held by a test: a closed scorer refuses first, then the frame is checked, then the record, then its index.

`pack` checks in this order: PROFILE_UNKNOWN, SHAPE_FILTERS, SHAPE_CHANNEL, SHAPE_ROWS, SHAPE_TAPS, WEIGHT_COUNT, SHAPE_RECTIFIER, SHAPE_SHIFT, SHAPE_POOL, WEIGHT_RANGE. `unpack`: BLOB_FORMAT (type and least length), BLOB_HASH, BLOB_FORMAT (magic, version, the name's length), PROFILE_UNKNOWN, RESERVED_BITS, SHAPE_FILTERS, SHAPE_TAPS, SHAPE_RECTIFIER, SHAPE_SHIFT, SHAPE_POOL, BLOB_FORMAT (channel masks that would run past the end), SHAPE_CHANNEL, SHAPE_ROWS, BLOB_FORMAT (the whole length), WEIGHT_RANGE. `commit`: SWAP_PENDING, SWAP_INDEX, SWAP_EPOCH. `write_shadow`: SWAP_PENDING, the blob's own, SWAP_SHAPE. `Scorer`: PROFILE_UNKNOWN, SCORER_THRESHOLD, SCORER_WINDOW, SCORER_BINS.

## 8. The gates, and what holds them

Five rows of `tests/gates.toml`. Each gate's check is one function that takes the thing under test; the gate's test asserts no finding on the shipped code, and each control hands the same function something broken and asserts the finding. A test that involves a stream or a shape runs under both profiles, and under `s24x3` the channels of a frame differ. The exceptions: what has no profile (the quantising rule; the stated figures of D0 row D4; the blob's hand-worked bytes, which have one case for each profile), and a fault that needs more than one channel to exist (rows on the wrong channel, a row of zeros for a channel not read, a gain of zero), which runs under `s24x3` alone.

**The known answers** are under `vectors/mod-b/`, worked by hand with the sums written in the file, with one exception: the 64 coefficients of `e0` in quantise.json are worked by a function that uses nothing of the model (`independent_e0` in `tests/test_mod_b_reference.py`: round half up by integers, with an assertion that no value is a tie), and four of the 64 by hand. The files: [datapath.json](../../vectors/mod-b/datapath.json), [swap.json](../../vectors/mod-b/swap.json), [quantise.json](../../vectors/mod-b/quantise.json), [blob.json](../../vectors/mod-b/blob.json), [scorer.json](../../vectors/mod-b/scorer.json), [widths.json](../../vectors/mod-b/widths.json). Beside them, two functions in `tests/test_mod_b_support.py` write the datapath's definition (`direct_scores`) and the blob's layout (`forge`) a second time. Those two functions use nothing of the three modules, and each is itself held to the hand-worked vectors. The rest of that file is harness, and it does import the model: `run_case`, `blob_of` and `check_vectors` build and run the core under test.

| gate | what its tests hold | the faults its controls plant |
|---|---|---|
| reference-model | records equal the hand-worked vectors, byte for byte; the quantiser equals the hand-worked sets; the largest shape with every coefficient different, 40 seeded shapes and a pool of 6,000 equal the second definition; in a stream otherwise zero the matched filter for `e0` has its largest score at j + T - 1; a row of zeros for a channel not read changes no record | the quantiser's rounding changed four ways; the shift rounding toward zero, and to nearest; coefficients newest first; the stream one sample late; rows on the wrong channel; **one flipped coefficient bit**, every bit of every tap in the matched-filter configuration under `s16x1` and three bits of every coefficient under `s24x3`, and every bit through `abs`, a pool and a head |
| swap | records equal the hand-worked swap vectors; with no pool, every score equals the direct sum under the weights its epoch names; `settling` marks exactly the outputs that mix | half the taps a sample late, on a swap to different weights, caught by the vectors and by the epoch check |
| refusal | every case of one table is refused under its own name; what is just inside each bound is accepted; a refused call changes nothing; the order of checks | for every case: a model that accepts it, and one that refuses it under another name; the shipped code reading a definition whose maxima are one higher |
| overflow | the declared widths equal the hand-worked ones; the shipped core, run in full at the true extremes, raises no flag and reaches each width's last bit; the flag rises at the first score that does not fit, the field wraps as defined, and the flag stays, across a swap too | a core one bit narrower at the filter and at the score, run end to end; each stage one bit narrower, on the values the full run reached |
| scorer | crossings, events, captured frames, the histogram, and the record after which each event is complete, equal the hand-worked vector; one of its cases has a `post` of 0 | a threshold off by one, each way; an at-or-above compare; a histogram that drops its last bin, two ways; a scorer that counts a settling record; an event with a `post` of 0 delivered one record late |

Three tests are there to show that a control's choice of fault matters: a flipped bit behind a zero head weight is not seen; half the taps a sample late is not seen when the swap is to the weights already active; a narrowed filter is not seen when only half the taps are at the extreme.

## 9. Limits

Each is stated by the behaviour it concedes.

- **L1. One linear head, no bias.** This model cannot represent a detector that needs a hidden layer. A deeper head is a change to the datapath, to the blob's version and to every width after the pool. D0's words are "a small dense head"; this is the smallest one.
- **L2. A run in which overflow rose is a marked run.** The scorer counts its records, and `overflow_at` says where the flag first rose. No efficiency or false-alarm figure from such a run may be reported as valid. The score field of a record that did not fit is the true value modulo 2^64: defined, and not a score.
- **L3. Two rectifier modes, one for the whole bank.** No half-wave and no square. One filter cannot pass while another takes the absolute value.
- **L4. A swap changes coefficients and head weights and nothing else.** The pool length, the shift, the rectifier, the tap count and which channels a filter reads belong to the shape; changing one is a new core, not a swap.
- **L5. The shadow is written whole.** The model has no partly written shadow and says nothing about how long a write takes or how a host delivers one. A commit names its index in advance; a fabric that swaps "when the write lands" is not this model.
- **L6. The settling flag says that an output mixes, not how much.** An output's flag says its pooled sum holds values made under two weight sets. It does not say how many of each, so the first mixed output, which holds one new value, is left out of the statistics exactly as the last one is.
- **L7. The pool and the head are not narrowed in a whole core.** The overflow control narrows the filter and the score in cores run end to end. For the pool and the head it hands a narrowed core the stage values the full shipped run reached. A fault that exists only in how a narrowed pool or head behaves over a whole run, and not on its extreme value, is not planted.
- **L8. Every control plants the faults listed in section 8 and no others.** A gate broken for a shape that is not planted passes its control.
- **L9. The second definition is the same author's.** `direct_scores` and `forge` in `tests/test_mod_b_support.py` share no code with the model, but one person wrote both. Only the hand-worked vectors are independent of that, and they are small: at most 3 taps, 2 filters, a pool of 3, 7 frames. A misreading of the definition that both writings share, and that those small cases do not expose, passes every gate.
- **L10. The quantiser's set is whatever one call is given.** What "the set" is for a bank of several filters is the caller's choice, and no rule here quantises a head weight: the matched-filter configuration's head is the integer 1.
- **L11. Events are unbounded.** Every rising crossing is an event and windows may overlap. A fabric with a bounded number of captures in flight is not this model; there is no hold-off and no count of events lost.
- **L12. The histogram and the captured frames have no record format.** `spec/` declares none. Two producers' histograms are equal when `below`, the bins and `above` are equal; their captures when the frames are.
- **L13. Lengths nothing can reach are not tested.** A stream of 2^64 frames would be refused, RECORD_FIELD, when its index no longer fits; a histogram count is an exact integer here, and how wide a fabric's counter must be is not defined. **And that one refusal would not leave the core as it was:** `Core.step` advances the store and the delay lines before it checks the record it has made, so a record refused there leaves the core one frame on. Every other refusal of `step`, of `commit` and of `write_shadow` changes nothing, and a test holds that; this one cannot be reached, and nothing tests it.
- **L14. The widths are for the definition's maxima, not for a configuration.** The model does not say how much headroom a smaller configuration has, and it does not refuse a configuration whose score can overflow: it raises the flag when one does.
- **L15. The hash guards against damage, not against intent.** Anyone who can write a blob can recompute its SHA-256. Nothing here says the fabric checks it.
- **L16. The blob's fields have their own ceilings.** A channel mask is 16 bits, so a profile of more than 16 channels cannot be packed, and a profile name's length is one byte. `pack` relies on the definition's profiles fitting both; a test holds the first.
- **L17. SHAPE_ROWS cannot be reached under a one-channel profile**, where a filter is one row and SHAPE_FILTERS is reached first. Its cases run under `s24x3` only.
- **L18. The no-float test reads syntax.** In the three modules it sees a true division, a power operator, a float or complex constant, the names `float`, `round`, `pow` and `complex`, and an import of `math`, `cmath`, `decimal`, `statistics`, `random` or `numpy`. A float that arrived through an argument would be refused by the type checks, which are tested; one made by a library call the test does not name would not be seen.
- **L19. Nothing here is evidence about sensitivity.** Bit-exact scores say what the detector computes, not how well it detects.

## 10. Cost

- **In the model:** one multiply-add for each tap of each row, every frame, in plain Python, and constant work per filter for the pool (a running sum over exact integers, with P stored values per filter). A test holds the running sum to the sum written out.
- **In a fabric,** for the RTL round to weigh, and no claim that it fits: one multiplier per tap of every row; a delay line of P values per filter for the pool; K multipliers at the pool's width for the head; a shifter.

## 11. Claims register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| B1 | Under `s16x1` the stage widths are 34 (product), 41 (filter), 41 (rectifier), 57 (pool), 77 (head) and 64 (score) signed bits | COMPUTED | `python -c "from model import detector; print(detector.widths('s16x1'))"`, and by hand in `vectors/mod-b/widths.json` | `test_gate_overflow__the_true_extremes_fit_every_width_and_raise_no_flag` failing; a verifier's own run at the extremes |
| B2 | Under `s24x3` they are 42, 50, 50, 66, 85 and 64 | COMPUTED | the same command with `'s24x3'`, and the same vector | the same test under `s24x3` |
| B3 | D0 row D4 holds: 128 products of 2^15 * 2^17 reach 2^39, which needs 41 signed bits | COMPUTED | 128 * 2^32 = 2^39; 40 signed bits stop at 2^39 - 1 | `test_gate_overflow__d0_row_d4_holds_for_16_bits_and_the_24_bit_figure_is_larger` |
| B4 | Under 24 bits one row of 128 taps reaches 2^47 (49 bits) and a filter across three channels 3 * 2^47 (50 bits) | COMPUTED | 128 * 2^23 * 2^17 = 2^47; 3 * 2^47 lies between 2^48 and 2^49 | the same test |
| B5 | A score shift of 13 (`s16x1`) or 21 (`s24x3`) makes overflow of the score impossible | COMPUTED | 77 - 64 and 85 - 64, from B1 and B2 | `test_gate_overflow__the_shift_that_the_width_argument_names_brings_the_extreme_inside` |
| B6 | No legal shape uses more than 2,048 multipliers in its filter bank | COMPUTED | MAX_ROWS * MAX_TAPS = 16 * 128 | a shape accepted with more rows or taps: the refusal gate's cases for SHAPE_ROWS and SHAPE_TAPS |
| B7 | At the maxima the pool's delay lines hold 42,991,616 bits (`s16x1`) or 52,428,800 bits (`s24x3`) | COMPUTED | 16 * 65,536 * 41 and 16 * 65,536 * 50, from B1 and B2 | arithmetic; a fabric design that stores the pool another way |
| B8 | A pool of 65,536 samples spans 10.9 minutes at 100 samples a second and 27.3 at 40 | COMPUTED | 65,536 / 100 / 60 and 65,536 / 40 / 60; the two rates are examples, not measurements of any station | arithmetic |
| B9 | The full run at the true extremes is 65,663 frames of 2,048 multiply-adds and takes about 10 to 14 seconds a profile on the lead's desktop | MEASURED | `python -m pytest -q -p no:cacheprovider tests/test_mod_b_overflow.py --durations=3`, 2026-11-23: 10.6 s and 9.9 s on one run, 13.5 s and 11.6 s on another | a rerun |
| B10 | The refusal table holds 350 cases under `s16x1` and 355 under `s24x3`, covering 24 and 25 refusal names | MEASURED | `python -c "import sys; sys.path[:0] = ['.', 'tests']; import test_mod_b_refusal as R; print([(p, len(R.table(p)), len({c[0] for c in R.table(p)})) for p in R.PROFILES])"`, 2026-11-23 | a rerun |
| B11 | Every one of 1,152 single-bit coefficient flips (`s16x1`) and 576 (`s24x3`) changed at least one score record in the matched-filter configuration | MEASURED | `python -m pytest -q -s -p no:cacheprovider tests/test_mod_b_reference.py -k flipped_coefficient_bit_changes_a_score_in_the_matched_filter`, 2026-11-23 | a rerun; a flip that leaves every record unchanged |
| B12 | The reference pulse's largest magnitude is 970, and no sample of it quantises on an exact tie | COMPUTED | a tie needs v * 131071 / 970 to end in one half; 131071 is prime, so 485 must divide v, and no sample is 485 or -485 | `test_gate_reference_model__the_reference_pulses_coefficients_equal_the_frozen_ones`, whose independent method asserts there is no tie |
| B13 | The smallest length `unpack` will read past its first check is 57 bytes | COMPUTED | 11 bytes before the name, 14 fixed bytes after it, 32 of hash | `python -c "from model import weights; print(weights.SMALLEST)"` printing another number |
| B14 | In the matched-filter configuration for `e0` the model steps about 110,000 frames a second under `s16x1` and about 66,000 under `s24x3` with three rows | MEASURED | `python -c "import time; from spec import constants as C; from model import weights; from model.detector import Core; core = Core(weights.matched_filter('s16x1', C.PULSES['e0'], (1,))); t = time.perf_counter(); [core.step((1,)) for _ in range(100000)]; print(round(100000 / (time.perf_counter() - t)))"` printed 111535; the same with `'s24x3'`, gains `(3, -1, 2)` and the frame `(1, 2, 3)` printed 66157. 2026-11-23, one run each, on a desktop other work shares | a rerun |
| B15 | MOD-B's tests are 156, of which 72 hold a gate and 55 are negative controls | MEASURED | `python -m pytest --collect-only -q -p no:cacheprovider tests/test_mod_b_*.py`, counted by name, 2026-11-23 | a recount |
| B16 | The maxima this page's figures are worked at: 18-bit coefficients, 16 filters, 16 rows, 128 taps, a pool of 65,536, a score shift of 31; samples of 16 bits on one channel and of 24 bits on three | READ | `spec/constants.py` at the commit this page was written on: COEFF_BITS, MAX_FILTERS, MAX_ROWS, MAX_TAPS, MAX_POOL, MAX_SCORE_SHIFT, PROFILES | the definition changing: every COMPUTED row above is then to be worked again |
| B17 | The hand-worked datapath and swap cases hold at most 3 taps, 2 filters, a pool of 3 and 7 frames; the second definition is compared with the core on 40 seeded shapes a profile, on the largest shape (16 rows of 128 taps, every coefficient different) and on a pool of 6,000 | READ | `vectors/mod-b/datapath.json`, `vectors/mod-b/swap.json` and `tests/test_mod_b_reference.py`, read 2026-11-23 | a reading of those files that finds another count |

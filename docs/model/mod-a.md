# MOD-A: the source and the injector

The part of the reference model that makes a stream and marks it. Two modules, `model/source.py` and `model/inject.py`, both integers and the standard library only. Their tests are `tests/test_mod_a_*.py`; their frozen vectors are under `vectors/mod-a/`.

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure in this page has a row in the register at the end, and the row's number is given where the figure is used.

**What rests on what.** Everything here is about what is deterministic: which samples a seed gives, which samples an injection adds. Nothing here says how well anything detects. The one statistical claim is the noise's law, and section 3 says how far each part of it has been counted and how far it is only constructed.

## 1. What the code does

### The words

`model.source.word(seed, i)` is SplitMix64 used as a counter. For a seed s from 0 to 2^64 - 1 and a word index i from 0:

    z = (s + 0x9E3779B97F4A7C15 * (i + 1)) mod 2^64
    z = ((z xor (z >> 30)) * 0xBF58476D1CE4E5B9) mod 2^64
    z = ((z xor (z >> 27)) * 0x94D049BB133111EB) mod 2^64
    word = z xor (z >> 31)

It has no state but the index, so any word can be worked directly: a test, a bench or one part of a long run starts anywhere. Each step is a bijection on 64-bit words and the counter's step is odd, so over the 2^64 indexes every 64-bit word occurs exactly once (A3). Two answers published for this generator are frozen in `vectors/mod-a/words.json`, and the model gives both (A1, A2).

### From a word to a sample

The law is the **discrete Gaussian on the integers**: P(X = k) proportional to exp(-k^2 / (2 sigma^2)), with sigma = sigma_num / sigma_den, two ints, sigma at least 1.

- The word's low bit is the sign. Its other 63 bits, u, are looked up in a table H.
- H[m] is 2^63 * P(|X| <= m), rounded to the nearest integer. The table ends at the first entry equal to 2^63.
- The magnitude is the number of entries with H[m] <= u. Magnitude 0 takes both signs, so H[0] is P(X = 0) whole.

`model.source.gaussian_table` builds H in 192-bit fixed point: exp(-1 / (2 sigma^2)) by its Taylor series, then two multiplications an entry. The table is what that arithmetic gives; the tests judge it against the law, recomputed another way (section 4).

Why this law, and not a continuous Gaussian rounded to integers: the stated sigma is then the standard deviation of the samples themselves. The variance of the law is sigma^2 to within 2.2e-7 at sigma = 1 and to better than one part in 10^12 at 3/2, 2, 100 and 1000 (A4). `model.source.table_variance(table)` gives the exact variance of a table's law as two ints. A sigma below 1 is refused: the variance statement stops holding there.

### Frames

`model.source.Noise(profile_name, seed, sigma_num, sigma_den, frames)` is an iterable of `frames` frames, the same each time it is iterated; `from_frame(n)` starts at frame n. Frame n, channel c is made from word n * channels + c, so no word is used twice and the 2^64 words bound the length (A22). Every channel has the same sigma.

### The injector

A schedule is a sequence of truth records. One record (index, pulse_id, amplitude_num, amplitude_den) means: the pulse the definition gives that id, scaled by amplitude_num / amplitude_den, is added to **every channel**, its **first** sample at stream index `index`. That is convention (a) of `docs/model/conventions.md`. Sample j of the pulse lands at `index + j`, and what is added there is

    delta[j] = pulse[j] * amplitude_num / amplitude_den, to the nearest integer, a tie to the even one

worked in integers: floor division, then one more when twice the remainder exceeds the denominator, or equals it with the quotient odd. Half to even is the definition's `INJECT_ROUNDING`. It is odd-symmetric: a negated amplitude adds exactly the negated samples.

The output sample is the input sample plus delta[j]. **If that sum is outside the profile's sample range the run is refused at that frame. A sample is never clipped.** The reference pulse e0 has 64 samples, the largest in magnitude -970; on a silent 16-bit stream amplitude 33/1 fits and 34/1 does not (A18).

`model.inject.inject(profile_name, frames, schedule, length)` returns `(stream, truth)`. `length` is the number of frames the stream has. The schedule is checked whole before a frame is read; `truth` is a copy of it, in order. Two injections may not share a sample, and the records must be in order: both are one rule, that a record starts at or after the end of the one before. An injection may end on the last frame and not past it. A stream that is not `length` frames long is refused.

An injection touches no frame outside index to index + L - 1 for a pulse of L samples, and inside that span a frame is unchanged wherever delta is zero. e0 has nine zero samples, so a lone e0 changes 55 frames (A18).

### Recordings

A recording is a 56-byte header (A19) and the samples:

| offset | bytes | field |
|---|---|---|
| 0 | 8 | the ASCII letters `UNDTSTRM` |
| 8 | 2 | format version, 1 |
| 10 | 2 | sample bits |
| 12 | 2 | channels |
| 14 | 2 | reserved, 0 |
| 16 | 8 | frames |
| 24 | 32 | SHA-256 of the payload |
| 56 | frames * channels * B | the payload |

Every integer is little-endian and unsigned but the samples. The payload is frame by frame, channel by channel, each sample two's complement, little-endian, in B bytes, B being the sample's bits rounded up to whole bytes. `stream_bytes` gives a stream's payload, and that is the stream's canonical form: two streams are equal when those bytes are equal. `record` writes a file, `Replay` reads one whole, checks all of it, and only then hands out a frame.

## 2. Refusals

Each is `model.refusal.Refusal` with a name the definition declares. Where one call can fail in more than one way the order is fixed, and the tests hold it: for the noise and for the injector it is the order of the rows below, and for a recording it is the sentence under the table.

| name | when | raised by |
|---|---|---|
| PROFILE_UNKNOWN | the profile is not declared | everything that takes a profile name |
| SEED_RANGE | a seed that is not an int from 0 to 2^64 - 1 | `word`, `Noise` |
| NOISE_SIGMA | sigma is not two ints with sigma_num >= sigma_den >= 1 | `gaussian_table`, `Noise` |
| STREAM_LENGTH | a frame count or word index that is not an int in range; a stream that is not as long as its declared length | `word`, `Noise`, `from_frame`, `schedule`, `inject` |
| NOISE_RANGE | the table at this sigma has a magnitude the profile cannot hold | `gaussian_table`, `Noise` |
| RECORD_FIELD | a truth record that is not one (`model.records.check`) | `schedule`, `inject`, `scaled_pulse` |
| PULSE_UNKNOWN | a pulse_id that names no declared pulse | `pulse`, `schedule`, `inject`, `scaled_pulse` |
| INJECT_OVERLAP | an injection starts before the one before it has ended: overlapping, or out of order | `schedule`, `inject` |
| INJECT_PAST_END | an injection would end past the stream's last frame | `schedule`, `inject` |
| CHANNELS, SAMPLE_RANGE | an input frame of the wrong width or with a sample out of range; a recorded sample out of range | the stream from `inject`; `stream_bytes`, and `recording` and `record`, which are built on it; `parse_recording` and `Replay` |
| INJECT_RANGE | a sample plus what is injected leaves the sample range | the stream from `inject` |
| REPLAY_FORMAT | not a recording: fewer than 56 bytes, wrong first eight, a version that is not 1, or a payload of the wrong length | `parse_recording`, `Replay` |
| RESERVED_BITS | a recording's reserved field is not zero | `parse_recording`, `Replay` |
| REPLAY_PROFILE | a recording whose sample bits or channels are not the named profile's | `parse_recording`, `Replay` |
| REPLAY_HASH | a recording whose payload does not match its SHA-256 | `parse_recording`, `Replay` |

A recording is checked in this order: format (length, first bytes, version), reserved, profile, payload length, hash, samples.

What is not a refusal: a path that cannot be opened is Python's own OSError, and something that cannot be iterated where frames or records are expected is Python's own TypeError.

## 3. How deep the tails hold (D0 row D7)

Three statements, of three different kinds.

1. **The tails stop.** No sample is larger in magnitude than the table's last index. That index is 9 at sigma = 1, 18 at 2, 916 at 100, 9,155 at 1000, 32,767 at 3579 and 45,776 at 5000: 9.155 sigma once sigma is large (A5). It is where the law's two-sided tail falls below 2^-64, and Q(9.1553) is 2^-65 (A6).
2. **Inside that, a word becomes a sample by the law, to within 2^-64.** Every two-sided tail probability the table gives, P(|X| > m), is a multiple of 2^-63 within 2^-64 of the law's, because every entry is the law's value rounded to the nearest integer (A7). The sign is one bit of the word, so each side has exactly half. As a relative error on a one-sided tail probability Q that is 2^-65 / Q: one part in a million at Q = 2.7e-14, which is 7.52 sigma, and 1% at Q = 2.7e-18, which is 8.64 sigma (A8).
3. **That the words in a window are as good as uniform is counted, not constructed,** and only as deep as the longest count. In the gate: 2^20 draws a channel, to 4.0 sigma a side, where 33 draws are expected (A9). In the long run of section 4: 2^30 draws, to 5.42 sigma a side (A11). **The long run has not been made at the time of writing; it is the lead's.**

**So the bound on a false-alarm claim from this noise is:**

- no per-sample probability below 2^-64, about 5.4e-20, can ever be claimed: the tail is not there;
- a counted claim reaches a one-sided per-sample probability of 3.05e-5 with the gate alone, and 2.98e-8 once the long run has been made (A11). D0 row D10's own floor for one pass of one channel is 7.5e-8 (A13);
- between the counted depth and 9.155 sigma a claim rests on statements 1 and 2 and on each word occurring once in a period. That is an argument about the generator's design, not a measurement of a window of its words.

## 4. The tests of the tail

- **The table, every entry.** For sigma = 1, 3/2, 2, 37/10, 100 and 1000 every entry is compared with the law recomputed in 50-digit `decimal` by `tests/test_mod_a_reference.py`, and must be within half a unit of 2^-63. For sigma = 3579 and 5000 the comparison is of every entry's tail in floats, to one part in 10^9 plus 2^-64 (A7).
- **The stream, every magnitude.** The real iteration is fed the words that sit on each side of every table boundary, with both signs, and must yield every magnitude the table holds, to the last. This is what reaches 9.155 sigma on the path a frame actually takes.
- **The sample.** Counts of draws at or beyond 1, 2, 3, 3.5 and 4 sigma, on each side and in each channel, against the law summed in floats. A count must lie within 4 standard deviations, sqrt(n p (1 - p)), of n p, and a threshold with n p (1 - p) below 25 is refused, not tested (A29). The two runs, seed and sigma, were named in the design before any run, and both passed at the first run (A30): profile s16x1, seed 20261123, sigma 1000; profile s24x3, seed 20261124, sigma 5000.

What the gate's two runs counted beyond 4 sigma, where 33.3 and 33.2 are expected on a side: 33 above and 34 below for s16x1; 30 and 34, 36 and 32, 36 and 31 for the three channels of s24x3. Of the forty counts the furthest from its expectation is 2.65 standard deviations (A9).

**The long run** is one command, or the same in parts, because any frame is worked directly from the seed:

    python tests/test_mod_a_tails.py --long --draws 1073741824
    python tests/test_mod_a_tails.py --long --total 1073741824 --start 0 --draws 268435456 --out part0.json
    python tests/test_mod_a_tails.py --judge part0.json part1.json part2.json part3.json

It counts at every half sigma from 1 that the total is long enough for, and at the deepest threshold with 32 expected on a side. It prints every count, a verdict for the generator, and a verdict for the same draws clipped one below the deepest threshold, which must be caught. `--judge` refuses parts that do not cover the run exactly once. At about 1.4 microseconds a draw (A10), 2^30 draws are about 25 minutes on one core (A12).

Depth against length, for a run of n draws a channel: the deepest threshold with 32 expected on a side (A11).

| draws | one-sided probability at the depth | depth |
|---|---|---|
| 2^20 | 3.05e-5 | 4.0 sigma |
| 2^22 | 7.6e-6 | 4.32 sigma |
| 2^24 | 1.9e-6 | 4.62 sigma |
| 2^30 | 2.98e-8 | 5.42 sigma |
| 2^32 | 7.5e-9 | 5.66 sigma |

## 5. The gates, and what each control plants

| gate | held by | controls, each a broken thing built in the test and caught by the same check |
|---|---|---|
| injection | the stream differs from its input by exactly what the truth says, rebuilt with `fractions` and Python's `round`, at every frame of every channel, on noise, under both profiles, for six injections of non-zero amplitude; hand-worked samples in `vectors/mod-a/injection.json` | an injector that adds nothing; a sample late; a sample early; the sign flipped; half the amplitude; the pulse in one channel only, and missing from one; a truth record missing, and one too many; a tie rounded upward; a quotient cut toward zero |
| replay | two runs built apart from one seed (source, injector) give the same stream bytes and truth bytes, equal to what the second implementation gives; a recording replays the run it recorded | each of the 64 single-bit changes of the seed, under both profiles; a generator that carries state from one build to the next; a truth record changed with the samples the same; a run one frame shorter; a comparison of no frames |
| noise-tails | the three tests of section 4 | samples clipped one below 4 sigma, by saturating and by drawing again, in each channel in turn, and on one side only; a table cut at 8 sigma, a table one entry short, and single entries moved by two units; an iteration that clips at 8 sigma with the right table and words; a sum of four uniform draws, and of twelve, with the right variance |

Each check refuses to pass on nothing: no frames, no truth record, expected additions that are all zero, a threshold the run is too short for. Truth isolation is the lead's gate; MOD-A's half is tested here without the gate's name: the frames the injector yields are plain tuples of plain ints even when its input frames are not, and four schedules that add the same samples under four different truths give byte-identical streams.

## 6. Limits

Each is stated by the behaviour it concedes.

**The noise.**

1. **The counted depth is 4.0 sigma a side, in the gate.** A generator whose words go wrong only in windows the tests do not draw, or only in ways that show beyond 4 sigma on the real stream, passes every gate: for instance one that never yields a word whose top thirty bits are all ones. The table and boundary tests would not see it, because they are about the table and the lookup, not about which words arrive. The long run moves this to 5.42 sigma and no further.
2. **The sampled test sees a missing tail, not a slightly thin one.** With 33.2 expected, a count of zero is 5.8 standard deviations out and fails; a tail thinned at 4 sigma by less than about 70% usually passes. At 3 sigma, where 1,415 are expected on a side, a change of 11% is 4 standard deviations (A16).
3. **Independence between samples is tested at one lag only:** the correlation of each channel with itself one frame on, and of each pair of channels in the same frame and one frame either side, on 2^16 frames. A dependence that leaves those and each sample's own law alone, such as a correlation at lag 2 or between squares, passes every gate. A false alarm is a large score, a sum over a filter's taps, and its tail needs that independence; that tail is counted by stage E0, not here.
4. **The words are held on the seeds and index ranges the tests name,** and by the two published answers. A generator that differs at other seeds or indexes passes.
5. **At small sigma the integer law's tail is not the continuous Gaussian's.** P(X >= k) is below Q((k - 1/2) / sigma) of a continuous Gaussian of the same sigma by about z^2 / (24 sigma^2): 21% at 5 sigma for sigma = 2, one part in ten thousand for sigma = 100, one in a million for sigma = 1000 (A14). The tail tests are against the discrete law, which is the generator's stated law.
6. **Far out, the law is right only as a cumulative.** A probability is a multiple of 2^-63. Past about 8.4 to 8.6 sigma a magnitude's whole probability is below that, and the rounded table gives some magnitudes one unit and others none: at sigma = 1000, 492 of the 9,156 magnitudes cannot occur, the first being 8,559 (A15).
7. **A seed is a place on one cycle of 2^64 words.** The seed s + k * 0x9E3779B97F4A7C15 gives the seed s's words k places on. Two arbitrary seeds with streams of L words overlap with probability about 2L / 2^64 (A21).
8. **One seed at two sigmas is one sequence of words through two tables:** the same signs and the same order of magnitudes, sample by sample (A23). Noise at two levels that must be independent needs two seeds.
9. **Every channel has the same sigma.** This source cannot make a stream whose channels differ in noise level.
10. **The table for sigma = 3579 and above is checked in floats, not in decimal** (A7): an error of a few units of 2^-63 near the centre of such a table, where the tail is near one, would pass. The table's arithmetic is the same at every sigma.
11. **The largest tables are slow and large.** A table has about 9.155 sigma entries. It builds in 0.05 s at sigma = 3579, the largest s16x1 holds, and 1.6 s at sigma = 100,000 (A20); near the largest sigma s24x3 holds, about 916,000, it would take about 15 s and several hundred megabytes (A24).
12. **That the table always runs past 8 sigma is tested at twelve sigmas and argued for the rest** (A28). `gaussian_table` uses it to refuse a sigma above an eighth of the range without building its table; called with no range, it takes the largest sample any declared profile holds, so a table no profile could use is never built. If the argument failed somewhere, a sigma that fits would be refused, by name.

**The injector.**

13. **One amplitude on every channel.** This injector cannot make a signal whose strength differs between channels, or one that is on a single channel. A real three-component record of one event will have such a signal. The truth record has no field that could say it.
14. **Two pulses cannot be superposed.** Overlapping injections are refused, so a stream with two events on top of each other cannot be made with one pass.
15. **Amplitude zero is accepted,** and so is an amplitude too small to add anything (1/5000 of e0 adds only zeros). The truth record is then a label on unchanged samples. Whoever counts efficiency must know such records can be there.
16. **A refusal can come part-way.** A sum out of range, a bad input frame, or a stream of the wrong length is found while the stream runs, after earlier frames were handed out and after `inject` returned the truth. A caller that ignores the refusal holds a partial stream and truth records for injections that were not all made. A refused run is no run.
17. **The stream is a Python generator.** The frames it yields carry nothing but samples. The generator object itself holds, inside its own frame, what it is going to add, and a consumer that inspects a generator's internals can read it. Nothing in the language prevents that; the seam tests are where a detector is held to not doing it.
18. **`length` must be declared.** A stream whose length is not known in advance cannot be injected into.
19. **One pulse is declared.** A second pulse's id reaching its own samples and its own length is tested with a pulse declared inside a test, not with a second pulse of the definition.

**Recordings.**

20. **A recording is read into memory whole,** and the format has one version.
21. **No declared profile has a width that is not whole bytes.** The rounding up of a sample's bytes and the range check on a replayed sample are tested with a 12-bit profile declared inside a test.

**What the tests reach.**

22. **Everything is tested at the seeds, sigmas, lengths and schedules the tests name.** A fault that shows only elsewhere passes: at a sigma no test builds, or on a seed no test draws.
23. **No test runs a stream of more than about a million frames.** The noise is checked far into a long source, past frame 2^32 and 2^40 and at a source's last frames, because any frame is worked directly. The injector and a recording are not: a fault that shows only at a frame index a test cannot reach, such as an injector that kept 32 bits of an index, passes every gate.

**The second implementation.**

24. **It was written by the author of the model,** from the same reading of the same design. It uses other tools (numpy's 64-bit integers, `decimal`, `fractions`, `struct`) and imports nothing of `model/`, which a test holds; but a shared misunderstanding of what the law or the rounding should be would pass both. The published answers for the words are the only check that comes from outside the project, and their source is a wiki page, not the generator's author (A1).
25. **The frozen noise vector for s24x3 is not recomputed in the gate.** `vectors/mod-a/noise.json` was written by the second implementation for both profiles; the gate recomputes the s16x1 half and compares the model with both halves.

**Cost** (not a limit of correctness). The shipped iterator draws at about 1.4 microseconds a draw (A10). MOD-A's 141 tests take 13 to 17 s (A25), of which the two sampled runs are about 6 s.

**For the RTL round** (ESTIMATE, A26): a word costs two 64-bit constant multiplies; the lookup is a search of a ROM of 9,156 entries of 63 bits at sigma = 1000, about 577 kbit. The table is data the model produces, so sigma is a load-time parameter. An injected sample needs a product of up to 47 bits divided by a 32-bit denominator.

## 7. Claims register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| A1 | The five words for seed 1234567 and the five counts for seed 987654321 in `vectors/mod-a/words.json` are the ones the Rosetta Code task "Pseudo-random numbers/Splitmix64" states | READ | `https://rosettacode.org/wiki/Pseudo-random_numbers/Splitmix64`, which says it was last edited on 6 November 2026; read by MOD-A on 2026-11-23 through a tool that returns a model's rendering of the page, not its bytes; the lead found the same ten figures in the page's bytes, 397,045 bytes with SHA-256 760ef27bdb0c13eabbf4245323fef7a1bcddf9a90438e87e1c74f729e4c34f14, fetched 2026-11-23 | the page's own text. The page is a wiki anyone may edit, not the generator's author |
| A2 | The model's words give both published answers | MEASURED | `python -m pytest -q tests/test_mod_a_source.py -k published`, 2026-11-23 | a rerun |
| A3 | Over the 2^64 indexes of one seed every 64-bit word occurs exactly once | COMPUTED | each step of the mix is a bijection (an odd multiplier; a shift-and-xor) and the counter's step is odd; `tests/test_mod_a_source.py -k exactly_one_index` undoes the mix with other code | two indexes of one seed that give one word |
| A4 | The law's variance is sigma^2 to within 2.2e-7 at sigma = 1 and to better than 1e-12 at sigma = 3/2, 2, 100 and 1000 | MEASURED | `python -m pytest -q tests/test_mod_a_source.py -k exact_variance`, 2026-11-23 | a rerun |
| A5 | The table's last index is 9 at sigma = 1, 18 at 2, 916 at 100, 9,155 at 1000, 32,767 at 3579 and 45,776 at 5000, and between 9.15 and 9.16 sigma at 100, 1000, 3579 and 5000 | MEASURED | `python -m pytest -q tests/test_mod_a_tails.py tests/test_mod_a_source.py -k "table or tail_does_not_fit"`, 2026-11-23 | a rerun |
| A6 | Q(9.1553) is 2^-65 to four digits | COMPUTED | `0.5 * math.erfc(9.1553 / math.sqrt(2)) / 2.0 ** -65` is 0.99994 | arithmetic |
| A7 | Every table entry is within half a unit of 2^-63 of the law at sigma = 1, 3/2, 2, 37/10, 100 and 1000, by 50-digit decimal; at sigma = 3579 and 5000 every entry's two-sided tail is within one part in 10^9 plus 2^-64, in floats | MEASURED | `python -m pytest -q tests/test_mod_a_tails.py -k "every_table_entry or long_tables"`, 2026-11-23 | a rerun |
| A8 | 2^-65 / Q is 1e-6 at Q = 2.7e-14, which is 7.52 sigma, and 1e-2 at Q = 2.7e-18, which is 8.64 sigma | COMPUTED | `statistics.NormalDist().inv_cdf` of 2^-65 / 1e-6 and of 2^-65 / 1e-2 | arithmetic |
| A9 | The gate's two sampled runs: 33.3 and 33.2 expected on a side beyond 4 sigma; counted 33 and 34 (s16x1), and 30 and 34, 36 and 32, 36 and 31 (s24x3, channels 0 to 2); of forty counts the furthest is 2.65 standard deviations out | MEASURED | `python tests/test_mod_a_tails.py --figures`, 2026-11-23 | a rerun |
| A10 | The shipped iterator draws at about 1.4 microseconds a draw on the lead's desktop: 1.40 for s16x1 and 1.30 for s24x3 over 2^20 frames, one run each | MEASURED | `python tests/test_mod_a_tails.py --figures`, 2026-11-23 | a rerun; another machine |
| A11 | The deepest threshold with 32 expected on a side: one-sided probability 3.05e-5 and 4.0 sigma at 2^20 draws; 7.6e-6 and 4.32 at 2^22; 1.9e-6 and 4.62 at 2^24; 2.98e-8 and 5.42 at 2^30; 7.5e-9 and 5.66 at 2^32 | COMPUTED | 32 / n, and `-statistics.NormalDist().inv_cdf(32 / n)` | arithmetic |
| A12 | The long run of 2^30 draws takes about 25 minutes on one core | ESTIMATE | 2^30 times 1.4e-6 s (A10) is 1,503 s; the counting adds little | the lead's run |
| A13 | D0's floor for one pass of one channel is a per-sample probability of 7.5e-8 | READ | `docs/studies/D0-rough-design.md`, row D10 | that row |
| A14 | The discrete law's P(X >= k) is below a continuous Gaussian's Q((k - 1/2) / sigma) by 21% at k = 10 for sigma = 2, by 1.1e-4 at k = 500 for sigma = 100, and by 1.1e-6 at k = 5000 for sigma = 1000 | MEASURED | `python -m pytest -q tests/test_mod_a_tails.py -k continuous`, 2026-11-23 | a rerun |
| A15 | At sigma = 1000, 492 of the table's 9,156 magnitudes cannot occur, the first being 8,559; at sigma = 5000, 3,398 cannot, the first being 41,816 | MEASURED | `python -m pytest -q tests/test_mod_a_tails.py -k cannot_occur`, 2026-11-23 | a rerun |
| A16 | With 33.2 expected a count of zero is 5.8 standard deviations out; the test fails below a count of 10.2, which is 69% fewer; at 3 sigma 1,415 are expected and 4 standard deviations are 10.6% of that | COMPUTED | 33.2 / sqrt(33.2); 33.2 - 4 sqrt(33.2); 2^20 Q(3) and 4 / sqrt(2^20 Q(3)) | arithmetic |
| A17 | A correct generator with a fresh seed would fail the gate's forty counts with a probability of about 0.25% | ESTIMATE | 40 times 2 Q(4), by the normal approximation; a count of 33 is not normal, so this is rough | the exact binomial sum |
| A18 | e0 has 64 samples, largest 950, smallest -970, nine of them zero, so a lone e0 changes 55 frames; at 33/1 it adds from -32,010 to 31,350, inside 16 bits; at 34/1 it would add -32,980, outside | MEASURED | `python -m pytest -q tests/test_mod_a_inject.py -k "never_clipped or exactly_what"`, 2026-11-23 | a rerun |
| A19 | A recording's header is 56 bytes | COMPUTED | 8 + 2 + 2 + 2 + 2 + 8 + 32; `tests/test_mod_a_source.py -k hand_worked` holds the bytes | arithmetic |
| A20 | A table builds in 0.016 s at sigma = 1000, 0.05 s at 3579 and 1.6 s at 100,000 (915,530 entries), one run each | MEASURED | `python tests/test_mod_a_tails.py --figures`, 2026-11-23 | a rerun |
| A21 | The seed s + k * 0x9E3779B97F4A7C15 gives seed s's words k places on; two arbitrary seeds with streams of L words overlap with probability about 2L / 2^64 | COMPUTED | the word's formula; the first half is shown by `tests/test_mod_a_source.py -k one_cycle` | two such seeds whose words are not shifted copies |
| A22 | A source holds at most 2^64 words: 2^64 frames of one channel, 2^64 / 3 rounded down of three | MEASURED | `python -m pytest -q tests/test_mod_a_source.py -k cannot_hold`, 2026-11-23 | a rerun |
| A23 | One seed at sigma 100 and at sigma 1000 gives the same signs and the same order of magnitudes over 3,000 samples | MEASURED | `python -m pytest -q tests/test_mod_a_source.py -k two_sigmas`, 2026-11-23 | a rerun |
| A24 | Near sigma = 916,000 a table would take about 15 s and several hundred megabytes | ESTIMATE | A20's 1.6 s scaled by 9.16; 8.4 million Python ints of 63 bits | building one |
| A25 | MOD-A's 141 tests take 13 to 17 s on the lead's desktop, which other parcels' runs were sharing | MEASURED | `python -m pytest -q -p no:cacheprovider tests/test_mod_a_inject.py tests/test_mod_a_reference.py tests/test_mod_a_source.py tests/test_mod_a_tails.py`, on 2026-11-23: 139 passed in 17.37 s and in 13.30 s, and with two tests more, 141 passed in 14.23 s | a rerun |
| A26 | In fabric a word costs two 64-bit constant multiplies, the lookup at sigma = 1000 a ROM of about 577 kbit, and an injected sample a product of up to 47 bits divided by 32 | ESTIMATE | 9,156 * 63; 16 bits of pulse times 32 of amplitude; nothing synthesised | the RTL round |
| A27 | The largest whole sigma s16x1 accepts is 3579; 3580 needs a magnitude of 32,776 | MEASURED | `python -m pytest -q tests/test_mod_a_source.py -k tail_does_not_fit`, 2026-11-23 | a rerun |
| A28 | The table's last index is above 8 sigma at sigma = 1, 101/100, 3/2, 2, 7/3, 10, 37, 38, 39, 100, 1000 and 3579; for every other sigma of at least 1 it is argued, not tested: the two-sided tail at 8 sigma is about 1.2e-15, and the table runs until it is below 2^-64 | BELIEVED | `python -m pytest -q tests/test_mod_a_source.py -k past_eight_sigma` for the twelve; the argument for the rest | a sigma of at least 1 whose table ends at or before 8 sigma |
| A29 | A count may be 4 standard deviations from its expectation, and a threshold with n p (1 - p) below 25 is refused | DECISION | the lead's, 2026-11-23, made for STAT's checks and taken here so the round has one rule | the lead changing it |
| A30 | The two sampled runs' seeds and sigmas were written in MOD-A's design before any run, and no seed was changed after a result was seen | READ | the round ledger's MOD-A file, entries of 2026-11-23 08:08 and 08:35; the ledger is kept outside the tree | those entries |

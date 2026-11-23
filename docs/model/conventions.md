# The model's seam conventions

Four conventions decide how the parts of the reference model meet: where an injected pulse is said to be, which way round a filter's coefficients are written, what counts as a crossing, and how a filter reads more than one channel. Each is a DECISION of the lead's, made on 2026-11-23 while the parcels of round 1 were at their design stop, because three parcels (the source and injector, the detector core, the statistics) each needed the same answer and none could see the others.

They bind `model/` and `stats/` alike. A document of a parcel's that says otherwise is wrong, and this one wins.

**What holds them.** Until the seam was merged, nothing did: this page was a statement of intent. Now `tests/test_seam_conventions.py` holds each one, on the parts run together, against answers worked by hand in `vectors/seam/conventions.json`: the core and the statistics package must each give the worked scores below; a filter written the wrong way round must give the other sequence; a score equal to its threshold must not cross; a filter on two channels must be the sum of its rows; an injected pulse must change its span by exactly the pulse. Each convention was broken on purpose in a copy of the code, and a seam test reported each. `tests/test_seam_e0.py` holds (a) and (b) a second way: a count read one sample late, or made with the coefficients reversed, falls outside the tolerance.

What still holds nothing: a convention is held for the cases those tests run, which are small or are the reference pulse. A part that kept every one of them there and broke one elsewhere would pass.

## The conventions

In what follows a stream is a sequence of frames, numbered from 0. Frame i holds one sample for each channel, x_c[i] for channel c. A filter has T taps.

**(a) A truth record's index is the stream index of the pulse's first sample.** An injection of a pulse of length L with index j adds the pulse's k-th sample, scaled, to frame j + k, for k from 0 to L - 1, and touches no frame outside j to j + L - 1. A frame inside that span is unchanged wherever what is added is zero. The reference pulse `e0` has nine zero samples, its first and its last among them, so a lone `e0` at j changes 55 frames, the first j + 1 and the last j + 62. A test that every frame of the span changes would fail on a correct injector.

**(b) A filter is causal, and its coefficients are written oldest sample first.**

    score[i] = sum over k from 0 to T-1 of coeff[k] * x[i - (T-1) + k]

A sample before the stream's start is taken as zero. A score record's index is i, the index of the newest sample the sum used.

So in the matched-filter configuration, where T is the pulse's length, **the coefficients are the pulse in order, not reversed**. Written the other way, as a convolution y[i] = sum of c[k] * x[i - k], the same filter has c reversed. This project writes the first form everywhere.

**(c) A crossing is a score strictly greater than the threshold.** A score equal to the threshold is not a crossing.

**(d) A filter names the channels it reads.** Its output is the sum, over those channels, of that channel's coefficient row against that channel's samples:

    score[i] = sum over c in U of ( sum over k of coeff[c][k] * x_c[i - (T-1) + k] )

where U is the set of channels the filter reads. A channel it does not read is, arithmetically, a row of zeros. A shape's rows, summed over its filters, are bounded by `max_rows` in [the definition](../../spec/undertone.toml), apart from the bound on its filters.

## A worked answer, by hand

One channel. The pulse is 1, 2, 3, so T = 3 and the matched filter's coefficients are 1, 2, 3. The pulse is injected with index j = 2 into a stream of seven zeros:

| i | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|---|
| x[i] | 0 | 0 | 1 | 2 | 3 | 0 | 0 |
| score[i] | 0 | 0 | 3 | 8 | 14 | 8 | 3 |

Each score, written out: score[2] = 3 * x[2] = 3. score[3] = 2 * x[2] + 3 * x[3] = 8. score[4] = 1 * x[2] + 2 * x[3] + 3 * x[4] = 1 + 4 + 9 = 14. score[5] = 1 * x[3] + 2 * x[4] = 8. score[6] = 1 * x[4] = 3.

The largest score is at i = 4 = j + T - 1, and it is the pulse's energy, 1 + 4 + 9. With a threshold of 14 there is no crossing; with 13 there is one, at index 4.

Had the coefficients been written newest first, the scores would be 0, 0, 1, 4, 10, 12, 9: a different sequence with its peak one sample late and below the energy. That is the wrong answer convention (b) exists to rule out, and it is silent: nothing crashes.

## Register

| id | claim | basis | source | falsified by |
|---|---|---|---|---|
| CV1 | A truth record's index is the stream index of the pulse's first sample | DECISION | the lead, 2026-11-23, round 1's ledger; recorded in `docs/VALIDATION.md` at the wave's merge | an injector that changes a frame before its record's index or after index + L - 1, or a seam test that needs another index to pass |
| CV2 | Coefficients are oldest sample first, a sample before the start is zero, and a score's index is its newest sample's | DECISION | the lead, 2026-11-23, the same entry | a model whose scores for the worked answer above are not 0, 0, 3, 8, 14, 8, 3 |
| CV3 | A crossing is strictly greater than the threshold | DECISION | the lead, 2026-11-23, the same entry | a scorer that counts a score equal to its threshold |
| CV4 | A filter's output is the sum over the channels it reads of each channel's row | DECISION | the lead, 2026-11-23, on the detector core's design | a core whose output changes when a row of zeros is added for a channel it did not read |
| CV5 | When a filter's coefficients are a positive multiple of the samples injected, a lone injection at j in a stream otherwise zero gives its largest score at j + T - 1 | COMPUTED | from CV1 and CV2: the sum at i = j + T - 1 pairs each coefficient with its own sample, and by the Cauchy-Schwarz inequality no other alignment gives more; worked for one case above | a noise-free run of the model, with such coefficients, whose largest score is elsewhere |

## What these do not say

- **Where the peak is once anything is rounded.** CV5 needs the coefficients to be an exact positive multiple of what was injected: the pulse at amplitude 1 against the pulse itself is one such case. Quantised coefficients against a pulse injected at a fractional amplitude are two roundings of the same shape, not multiples of one another, and CV5's argument does not cover them. The seam test measures where the peak is for the reference pulse; this page does not promise it.
- **Where the peak is in noise.** CV5 is about a stream that is zero but for the pulse. In noise the largest score near an injection can be at another index. How far from j + T - 1 a crossing may be and still count for that injection is a rule of the scoring, not of this page, and round 1 has not set it.
- **Anything about a filter longer than its pulse.** CV5 takes T as the pulse's length. A filter with more taps than the pulse has samples peaks where its coefficients put it.
- **How an injected sample is rounded, or what a record's flags mean.** The first is `[inject]` in the definition; both are stated where the parts that own them are documented.

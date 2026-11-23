# The statistics: `stats/`

Written by parcel STAT in round 1, 2026-11-23. Labels are those of [the design](../studies/D0-rough-design.md): MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure on this page is in the register at the end, with the command that prints it, the file it is read from, or the rows it is worked from.

## What this is, and what it is not

The reference model in `model/` is the authority for everything deterministic. It says nothing about how well the instrument detects: that is a statistical question, and D0's section 2 gives it two other authorities. Both are here.

1. **The analytic matched-filter result,** D0 row D8, as a formula (`stats/theory.py`), with what was read of its source in [docs/sources/D8.md](../sources/D8.md).
2. **A second, foreign implementation:** a matched filter in floating point, an injection-recovery count, and the tolerance that says whether a measured efficiency matches the formula. It imports nothing from `model/` and shares no code with it. Both read `spec.constants`: shared facts, not shared code.

**What a result from this package is evidence of.** A pass of the `statistics` gate says that the code in `stats/`, run on test streams this package makes itself, counts what D8 predicts and reports a detector that does not. It is not evidence about the reference model, the RTL or the card: none of them is run here. It is not evidence about the instrument's noise generator either, because the test streams come from numpy (limit 9). A bit-identity pass is not evidence about sensitivity, and nothing here is evidence that the fabric is correct.

## The conventions

The lead's seam conventions of 2026-11-23 bind `model/` and `stats/` alike. They are written in `docs/model/conventions.md` on the round branch; that page wins over this one. As this package holds them:

- A truth index is the stream index of an injected pulse's **first** sample.
- A filter is causal, coefficients **oldest sample first**: score[i] = sum over channels c and taps k of coeff[c][k] * x[i - (T-1) + k][c], samples before the stream taken as zero. A score's index is its newest sample's. So the matched filter's coefficients are the pulse in order, and a pulse at j is wholly under the filter at score index j + T - 1.
- A crossing is a score **strictly greater** than the threshold.
- More than one channel: one coefficient row per channel, summed; a channel a filter does not read is a row of zeros.

`tests/test_stat_matched.py` holds the page's own worked answer (coefficients 1, 2, 3; scores 0, 0, 3, 8, 14, 8, 3; one crossing at a threshold of 13 and none at 14), and a three-channel case worked by hand.

## The modules

| module | what it gives |
|---|---|
| `stats/errors.py` | `StatRefusal`, a named refusal. The definition's names where the meaning is the definition's (an unknown profile, a channel count, a sample range, too many taps); fifteen names of this package's own otherwise |
| `stats/theory.py` | `q`, `q_inv`, `pd_matched` (D8), `deflection`, `pd_rectified` |
| `stats/quantise.py` | `quantise`: the definition's `peak_to_max` and `half_to_even`, in floating point with a guard |
| `stats/matched.py` | `frames_to_array`, `template`, `matched_scores`, `scores_are_exact` |
| `stats/recovery.py` | `threshold_known_sigma`, `signal_free_indexes`, `signal_free_scores`, `threshold_from_scores`, `minimum_spacing`, `recovery_count`, `paired_cost` |
| `stats/tolerance.py` | `binomial_se`, `roc_slope`, `tolerance`, `check_efficiency`, `check_count`, `rejection_probability`, `catch_margin`, `false_rejection_probability` |
| `stats/synth.py` | test streams only: `noise`, `schedule`, `inject` |
| `stats/d11.py` | the script for D0 row D11: `python -m stats.d11` |

Each function's docstring gives its arguments, what it returns and what it refuses.

## D8, and two things derived here

`pd_matched(pfa, d)` is Q(Q^-1(pfa) - d). Q is `0.5 * erfc(x / sqrt 2)`. Its inverse is a bisection on Q, slow and obvious; it is tested by putting each answer back through `math.erfc`, and Q itself against a numerical integral of the Gaussian density written in the test.

For the reference pulse `e0` the definition gives 64 samples with energy 11,811,446, so norm 3436.78 and d = 3436.78 / sigma (register R1). The code computes this from `spec.constants`; the figure is typed nowhere in `stats/`.

Two results are **this package's own derivations**, not read from any source:

- **A filter that is not the pulse.** A linear filter h in white Gaussian noise has output h.x, Gaussian with standard deviation sigma norm(h), shifted by h.s when the samples s are added. So its efficiency at false-alarm probability Pfa is Q(Q^-1(Pfa) - (h.s) / (sigma norm(h))): D8 with d replaced by `deflection(h, s, sigma)`, which is d times the cosine of the angle between h and s. This is what predicts the efficiency of a wrong coefficient set in the controls. It follows from the same two facts as D8 (a sum of independent Gaussians is Gaussian; its mean and variance add) and the controls measure it: four wrong filters land inside the tolerance of their own prediction (register R14).
- **An absolute value after the filter.** `pd_rectified(pfa, d)` = Q(t - d) + Q(t + d) with t = Q^-1(pfa / 2): the threshold must pass pfa / 2 in each tail, and a pulse is then found in either.

## The quantising rule, in floating point

`quantise(coeffs, bits=18)` is the definition's rule written a second time: every value of the set is multiplied by (2^(bits-1) - 1) / m, with m the set's largest magnitude, then rounded to the nearest integer, a tie to the even one. `model/` has its own implementation; the seam test of wave 2 compares the two.

**The half-way cases.** In floats the scaled value is (c / m) * qmax, two rounded operations, which leaves it within 2^-23 of the true value for `bits` up to 30. That is enough to be wrong at a tie: with a peak of 3.0, the float `0x1.2000900048002p-15` scales to a hair under 1.5, plain float arithmetic lands on 1.5 and rounds it to 2, and the exact rule says 1. So a value that arrives within 2^-12 of a half-way point is not rounded from the float. It is worked again as an exact ratio of integers and rounded half to even there. Outside the guard the float and the true value lie between the same two half-way points, so ordinary rounding is the exact rule's answer. `tests/test_stat_quantise.py` holds the result against the exact rule written again in rationals, on exact ties, near ties, ties that appear only after scaling, 240 random sets at six widths and 6,005 values on a half-way grid; and it shows the same arithmetic without the guard getting six listed values wrong.

**"The set" is everything in one call.** The definition does not say whether, for a bank of several filters, the set is one filter or the bank. In the matched-filter configuration there is one filter and the readings agree.

## The matched filter, and when it is exact

`matched_scores(stream, profile, coeffs)` returns one score per frame, by the conventions above. It takes a profile by name and runs under both. The stream is an iterable of frames or an integer numpy array; a float or a bool sample is refused, not rounded.

**With integer coefficients the float is exact.** Every product and partial sum is then an integer, and a float64 holds every integer up to 2^53. `scores_are_exact(profile, coeffs)` says whether sum|coeff| * (largest sample magnitude) is below 2^53. At the widest case the definition allows, 24-bit samples, 18-bit coefficients, 128 taps, 3 channels, the largest score is 2^48.58 (R9). So on the same integer stream with the same quantised coefficients, this package's score and the model's score word are the same integer, and a comparison between them has tolerance zero. `tests/test_stat_matched.py` holds the scores against a plain integer loop at 1, 5, 64 and 128 taps and at the extreme inputs, under both profiles.

## Thresholds and the recovery count

A threshold comes one of two ways, and the tolerance has to know which.

- `threshold_known_sigma(pfa, sigma, coeffs)` = Q^-1(pfa) * sigma * norm(coeffs): D8's own threshold, for white noise of known sigma.
- `threshold_from_scores(noise_scores, pfa)`: from m signal-free scores, the (k+1)-th largest, k = floor(pfa * m), so that k of them cross. The floor is of the float's exact value (limit 16). It returns `pfa_effective` = (k + 1) / (m + 1), the mean false-alarm probability of that threshold over noise samples. `signal_free_indexes` picks scores that saw no injected sample, at least one filter length apart, so that in white noise they are independent.

`recovery_count(scores, truth_indexes, threshold, lag, taps, pulse_len, window=0)` counts two things:

- **recovered at the injected index:** scores[j + lag] > threshold, with j the truth index and `lag` = T - 1 for this package's filter;
- **recovered within a window:** the largest of scores[j + lag - window .. j + lag + window] > threshold.

Only the first has an analytic authority: D8 is a test at a known arrival time. The window count is a different test. On the gate's three-channel stream, within +/-8 samples it finds 0.578 of the pulses where the index alone finds 0.498, and on noise alone it crosses at 0.073 of places where the index alone crosses at 0.009 (R15). It is compared between implementations on one stream, never with D8.

Injections closer than `minimum_spacing` (taps + 2 * window, for this filter) are refused: their trials would share noise samples and the binomial tolerance would be false.

## The tolerance

A measured efficiency is found / n. The check is

    abs(found / n - p) <= z * se_total,        p = pd_matched(pfa, d)

    se_total^2 = p (1 - p) / n  +  roc_slope(pfa, d)^2 * pfa (1 - pfa) / m

The first term is D0 row D9's binomial error, with p the **prediction**, not the measurement. The second is present only when the threshold was measured from m independent signal-free scores, and then `pfa` is `pfa_effective`.

**z = 4, and a check is refused when n p (1 - p) is below 25.** Both are DECISIONs of the lead's (2026-11-23) for the gate's own checks. A report gives the deviation in standard errors whatever z is.

**The numbers,** at the gate's operating point, Pfa = 0.01 and d = Q^-1(0.01) = 2.3263, where D8 gives exactly one half and the curve is steepest (R4):

| injections | standard error | tolerance, 4 se | catch margin, 8 se | a correct detector falls outside with probability |
|---|---|---|---|---|
| 10,000 (D9's count) | 0.0050 | 0.0200 | 0.0400 | 6.59e-5 |
| 100,000 | 0.00158 | 0.0063 | 0.0126 | 6.33e-5 |
| 200,000 | 0.00112 | 0.0045 | 0.0089 | 6.32e-5 |
| 1,000,000 | 0.00050 | 0.0020 | 0.0040 | 6.36e-5 |

The last column is exact, summed from the binomial (`false_rejection_probability`); the normal figure is 2 Q(4) = 6.33e-5.

**What the check cannot see. This is the limit that matters most.** A detector whose true efficiency is off by less than the tolerance is usually passed. One off by exactly the tolerance is rejected half the time. Only one off by the **catch margin**, 8 standard errors, is rejected with probability 1 - 3.2e-5. At D9's 10,000 injections a detector 0.01 below D8 is rejected 2.3% of the time; at 100,000, 99.0% of the time (R5). The number of injections has to be chosen for the fault one means to see: `rejection_probability` says what a given count can do.

**A measured threshold costs more than it looks.** At Pfa 0.01 and Pd one half the efficiency moves 14.97 points per point of false-alarm probability (R6), so a threshold measured from m independent noise scores brings a standard error of its own, 1.489 / sqrt(m), which adds to the binomial one in quadrature. The two are equal only when m is 8.9 times the number of injections. At 200,000 injections and m = 100,000 the tolerance is 0.0194, not 0.0045, and the small fault the gate's first control plants (0.0135) is inside it. An experiment that wants a tight comparison with D8 at a measured threshold needs far more signal-free scores than injections, or a threshold known some other way.

**The tolerance's width is itself tested.** `tests/test_stat_tolerance.py` runs 8,000 small experiments with a correct detector and a known threshold, and 2,000 with a threshold measured afresh in each, and requires the fraction falling outside one and two standard errors to match what a binomial gives: the exact binomial figures for the known threshold, the normal ones for the measured threshold. On 2026-11-23 the counts were 2,480 and 352 of 8,000 where 2,514 and 372 are expected, and 652 and 95 of 2,000 where 635 and 91 are expected (R21). The same test must report a tolerance worked for a quarter of the trials, one for four times the trials, one 10% too wide or too narrow, and one that forgets the threshold was measured.

## Handing a detector to the check

A detector here is anything that turns a stream into one score per frame. The check needs three things from whoever runs it: the scores, the threshold that gives **this detector** the stated false-alarm probability, and the deflection the detector is **claimed** to have. For a coefficient set on one of this package's test streams, at the gate's operating point:

```python
from spec import constants as C
from stats import matched, recovery, synth, theory, tolerance

pulse, taps, pfa = C.PULSES["e0"], 64, 0.01
sigma = theory.deflection(pulse, pulse, 1.0) / theory.q_inv(pfa)     # so that D8 gives one half
truth = synth.schedule(200_000, 64)
stream = synth.inject(synth.noise("s16x1", 200_000 * 64, sigma, 1), "s16x1", pulse, truth)

coeffs = list(pulse)                                                 # the detector under test
scores = matched.matched_scores(stream, "s16x1", coeffs)
threshold = recovery.threshold_known_sigma(pfa, sigma, coeffs)       # ITS threshold for pfa
found = recovery.recovery_count(scores, truth, threshold, lag=taps - 1, taps=taps, pulse_len=taps)
claimed_d = theory.deflection(pulse, pulse, sigma)                   # the claim: it is the matched filter
verdict = tolerance.check_efficiency(found["at_index"], found["n"], pfa, claimed_d)
```

With seed 1 as written, `verdict["inside"]` is true at -0.3 standard errors; with `coeffs[51]` negated before the filtering it is false at -12.3 (R26). A detector that is not a linear filter of known coefficients has no threshold from sigma: measure one from its own signal-free scores with `threshold_from_scores`, and pass the `pfa_effective` and the `m` it returns to `check_efficiency`.

## Separating quantisation's cost from an error

D0's fourth limit on D8: the formula assumes exact coefficients and real-valued noise. Three comparisons, each with its own spread, keep the causes apart.

1. **An error.** Same integer stream, same quantised coefficients, the model's score against this package's. By the exactness above they are the same integer; any difference at all is an error in one of the two. Tolerance zero. The function and the bound are here; the comparison is the seam test's, in wave 2.
2. **The cost of quantised coefficients.** Same stream, same injections, this package twice: real coefficients, then `quantise` of them, each at the threshold that gives it the same false-alarm probability. `paired_cost` counts the injections found by exactly one of the two: cost = (a_only - b_only) / n, with standard error sqrt(a_only + b_only - (a_only - b_only)^2 / n) / n. Pairing removes the binomial spread the two runs share. Measured on the gate's 200,000 injections: at 18 bits the two detectors disagree on no injection at all; at 3 bits the cost is 0.0104 with a paired standard error of 0.0005, against a predicted 0.0094 (R12, R13).
3. **What the integer stream itself costs** (rounded samples, the generator's tails): the real-coefficient efficiency on that stream against D8, with the tolerance above. This is the only one of the three that carries binomial spread.

## The gate, and its controls

The gate is `statistics` in `tests/gates.toml`: tests named `test_gate_statistics__*`, controls named `test_control_statistics__*`. All figures are from `python -m pytest -q -p no:cacheprovider -s tests/test_stat_gate_statistics.py` on 2026-11-23, seeds 2026112301 to 2026112304 (R10, R11, R14).

**The data.** Profile `s16x1`: the pulse at amplitude 1, 200,000 injections 64 frames apart, sigma 1477.33 so that d = 2.3263; a second pulse-free stream of 6,400,000 frames for measured thresholds. Profile `s24x3`: the pulse with a different gain on each channel, (3, -1, 2), each channel its own noise, 25,000 injections 128 frames apart, measured thresholds from the same stream's gaps. Every coefficient set gets the threshold that gives **that set** a false-alarm probability of 0.01: equal false-alarm rate, never equal threshold.

**The correct filter is inside** (the gate's positive case):

| profile, coefficients, threshold | found | efficiency | from D8 | tolerance |
|---|---|---|---|---|
| s16x1, real and 18-bit alike, known | 100,067 of 200,000 | 0.50033 | +0.3 se | 0.00447 |
| s24x3, real and 18-bit alike, known | 12,439 of 25,000 | 0.49756 | -0.8 se | 0.01265 |
| s16x1, real and 18-bit alike, measured (m = 100,000) | 99,272 of 200,000 | 0.49636 | -0.8 se | 0.01936 |
| s24x3, real and 18-bit alike, measured (m = 25,000) | 12,647 of 25,000 | 0.50588 | +0.5 se | 0.03969 |

**A wrong filter is outside** (the controls). Each is handed to the same check as if it were the matched filter:

| the fault | cosine with the pulse | predicted | found | from D8 | verdict |
|---|---|---|---|---|---|
| **the stated margin:** tap 51 (value 293) sign-flipped, s16x1 | 0.98546 | 0.48651 | 97,309 of 200,000 = 0.48655 | -12.0 se | outside, and inside its own prediction |
| coefficients time-reversed, s16x1 | -0.92388 | 0.000004 | 1 of 200,000 | -447 se | outside |
| channel 0's row zeroed, s24x3 | 0.59761 | 0.17461 | 4,298 of 25,000 = 0.17192 | -104 se | outside, and inside its own prediction |
| channel 1's row zeroed, s24x3 | 0.96362 | 0.46628 | 11,618 of 25,000 = 0.46472 | -11.2 se | outside, and inside its own prediction |
| channel 2's row zeroed, s24x3 | 0.84515 | 0.35934 | 8,995 of 25,000 = 0.35980 | -44.3 se | outside, and inside its own prediction |
| tap 20 (value 706) sign-flipped, s16x1, measured threshold | 0.91560 | 0.42217 | 83,907 of 200,000 = 0.41953 | -16.7 se | outside |
| channel 2's row zeroed, s24x3, measured threshold | 0.84515 | 0.35934 | 9,336 of 25,000 = 0.37344 | -12.8 se | outside |

The stated margin: the first fault's predicted efficiency is 0.0135 below D8. At 200,000 injections that is 12.1 standard errors, 8.1 beyond the tolerance's edge, and more than the catch margin of 0.0089. The same fault judged with a tolerance worked for 10,000 injections (0.020) is inside: that is the trap of a tolerance for the wrong number of trials, and a control holds it.

## The script for D0 row D11

`python -m stats.d11` simulates what D11 quotes: 400,000 trials with a pulse and 400,000 without, a 128-sample Hann-windowed sine of 8 cycles scaled to d = 1.75 at sigma = 2, false-alarm probability 0.01, seed 20261123, real-valued samples. Its output on 2026-11-23, run time about 1.5 s (R7):

| detector, threshold | found of 400,000 | efficiency | from D8's 0.2822 | verdict |
|---|---|---|---|---|
| matched, known | 113,064 | 0.2827 | +0.7 se | inside |
| matched, measured | 113,400 | 0.2835 | +0.6 se | inside |
| rectified, known | 82,023 | 0.2051 | -108 se | outside |
| rectified, measured | 82,970 | 0.2074 | -35 se | outside |

The rectified detector at a known threshold is 0.9 of a standard error from its own exact figure, 0.2045.

The script also counts both detectors on a pulse of the **opposite sign** (the same noise with the pulse subtracted), at the known thresholds. The matched filter finds 9 of 400,000, where Q(Q^-1(0.01) + 1.75) predicts 9.1. The rectified detector finds 81,658, an efficiency of 0.2041, 0.5 of a standard error below 0.2045. That is what a rectifier buys, and it is the only place the script can tell a rectifier from a raised one-sided threshold: on the pulse itself the rectified detector's lower tail holds 7.6 trials in a million, so the two count alike there. A control replaces the rectifier with one that passes its input through and requires the negated pulse and the noise-only rate to report it; the count on the pulse itself does not report it, and the control says so.

**What this says about D11's row.** D11 quotes "0.206 where D8 gives 0.284" at d = 1.75. At d = 1.75 exactly, D8 gives 0.2822; 0.284 is the formula at d = 1.7553 (R2). The exact figure for the rectified detector is 0.2045 (R3). How D11's run set its thresholds is not recorded. If it measured them from 400,000 noise trials, as this script's second and fourth rows do, one standard error is 0.0021, and its simulated 0.287 is 2.3 standard errors above the exact 0.2822 and its 0.206 is 0.7 above the exact 0.2045. The row's point stands: a rectifier after the filter costs 0.078 of efficiency here, and D8 does not describe it. D0 is the lead's file to restate.

## Limits

Each is stated by the behaviour it concedes. A fault inside one of these passes the gate.

1. **A detector wrong by less than the catch margin can pass.** At n injections with a known threshold the check rejects reliably only a true efficiency 8 sqrt(p (1 - p) / n) from D8, and passes most detectors within 4 of those. At 10,000 injections that is 0.040 and 0.020. With a measured threshold both are wider.
2. **A tolerance wrong by less than 10% in width is not reliably seen.** The calibration test reports a known-threshold tolerance 10% too wide or too narrow, which is about 20% in the trial count. One 5% out is reported about half the time: of 1.05 and 1/1.05, the first is reported and the second is not (R27). With a measured threshold the calibration has 2,000 experiments, not 8,000, and reliably reports only a total width wrong by about 17% or more (R28, arithmetic, not a run); the control it is held to drops the threshold term altogether.
3. **The threshold term is first order.** It assumes Gaussian scores and independent noise scores, and its error shrinks as k grows, k the number of noise scores above the threshold. Below k = 100 a threshold is refused. At k = 100 the z-score of a correct detector is biased by about -0.03, and at k = 200 by about -0.02 (R25).
4. **White, Gaussian noise of one sigma on every channel, and trials that do not overlap.** `deflection`, both thresholds and the independence of signal-free scores all assume it. Coloured noise, a different sigma on each channel, or a pulse that does not arrive whole are outside every formula here. `check_efficiency` cannot tell whether its trials were independent; `recovery_count` refuses a schedule that makes them overlap, and a count made some other way is the caller's to vouch for.
5. **One operating point in the gate.** The gate runs at Pfa 0.01 and Pd 0.5, and D11's script at Pfa 0.01 and Pd 0.28. Nothing here runs at a false-alarm probability below 0.01, at fractional amplitudes, or with a pulse other than `e0` and D11's sine.
6. **The count does not read amplitudes or pulse ids.** A truth list that mixes amplitudes is counted as one population, and a tolerance for a single d is then wrong. The caller splits by amplitude.
7. **The window count has no authority.** It is counted, and nothing here says what it should be.
8. **Ties.** If several signal-free scores equal the threshold, fewer than k cross and the real false-alarm rate is below `pfa_effective`; `above` reports the count, and the tolerance does not correct for it. At the exact edge of a tolerance, floating-point rounding decides `inside`.
9. **The test streams are numpy's, not the instrument's.** `stats/synth.py` is a rounded floating-point Gaussian from PCG64. The model's generator is a different law (a discrete Gaussian, by its parcel's design) and its injector is its own. numpy does not promise that a seed gives the same stream in every version: on a numpy that changes it, each seeded `inside` assertion is a fresh draw that a correct implementation fails with probability 6.3e-5.
10. **Exactness rests on how numpy adds.** The exact-integer argument holds for any order of addition, so it does not depend on numpy's order; it does depend on `numpy.convolve` adding products directly, not through a transform. The tests at the extreme inputs would show a change.
11. **`q_inv` is tested at listed probabilities,** from 1e-300 to one half and their mirror images down to 1 - 1e-9. Between them it is held by being a bisection on a monotone function.
12. **The paired cost's standard error is tested by hand on small cases** and by one measured cost landing within 4 of them. Its width is not calibrated the way the tolerance's is.
13. **The quantiser treats the numbers it is given as the truth.** A coefficient already rounded when it became a float is quantised as that float. `bits` is 2 to 30. **The guard's width is argued, not tested.** Every value found on which plain float arithmetic misses the exact rule has its float exactly on a half-way point, so a guard of zero width, one that fires only there, passes every test here. A search of about 3.5 million near ties at 18, 27 and 30 bits found no value where the float lands off the half-way point on the wrong side (R25). The 2^-12 is the width the error bound justifies; nothing here shows a narrower one failing. So: a test notices the guard's REMOVAL (with it switched off, `tests/test_stat_quantise.py` sees six listed values quantised wrongly), and no test notices its NARROWING, to any width down to zero. Row R8's float is not a case a zero-width guard fails: its float lands exactly on 1.5, where a zero-width guard still fires.
14. **Refusal names.** `stats/` refuses under its own names where the definition has none for the case. Since this parcel's base the definition has gained names of the model's for nearby cases (a quantiser's input, a noise sigma, overlapping injections); `stats/` does not use them, and a seam test that compares refusals by name across the two packages would see different names for those.
15. **The source.** See [docs/sources/D8.md](../sources/D8.md): the primary source was read by the lead through text extraction, and the closed form is computed from it, not read in it.
16. **The crossing count is the floor of the float's exact value.** `threshold_from_scores` takes k = floor(pfa * m) on the exact value of the float `pfa`. A pfa written 0.29 is a float a hair below 0.29, so over 10,000 scores k is 2,899, one fewer than the decimal reads; 0.57 and 0.58 behave the same (R29). The threshold is then one score higher and the false-alarm rate a little lower than asked. `pfa_effective` is worked from the k actually used, so a tolerance given it is right for it; a caller who reads the decimal and expects 2,900 crossings is one out.
17. **`rejection_probability` is a normal approximation with the wrong detector's own spread.** For a detector of true efficiency 0.8 judged against a prediction of one half over 100 injections it gives 0.9938, where the exact binomial figure is 0.9888 and the prediction's spread would give 0.9772 (R30). It is a guide to what a count can see, not a bound.

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| R1 | The reference pulse `e0` has 64 samples, energy 11,811,446 (norm 3436.78) and largest magnitude 970 | COMPUTED | `python -c "from spec import constants as C; p=C.PULSES['e0']; print(len(p), sum(v*v for v in p), sum(v*v for v in p)**0.5, max(map(abs,p)))"` | a rerun |
| R2 | Q^-1(0.01) = 2.32635. D8 at Pfa 0.01 gives 0.2822 at d = 1.75 and 0.2840 at d = 1.7553 | COMPUTED | `python -c "from stats.theory import *; print(q_inv(0.01), pd_matched(0.01,1.75), pd_matched(0.01,1.7553))"` | a table of the normal distribution |
| R3 | An absolute value after the filter gives 0.2045 at Pfa 0.01 and d = 1.75 | COMPUTED | `python -c "from stats.theory import *; print(pd_rectified(0.01,1.75))"`; the formula is this package's derivation | another derivation; row R7's simulation |
| R4 | The tolerance table: standard error, tolerance, catch margin and exact false-rejection probability at 10,000, 100,000, 200,000 and 1,000,000 injections; 2 Q(4) = 6.33e-5 | COMPUTED | `python -c "from stats.theory import *; from stats.tolerance import *; z=q_inv(0.01); [print(n, tolerance(0.01,z,n)['se_total'], tolerance(0.01,z,n)['tolerance'], catch_margin(0.01,z,n), false_rejection_probability(0.01,z,n)) for n in (10000,100000,200000,1000000)]; print(2*q(4))"` | arithmetic: sqrt(0.25 / n), times 4, times 8; an exact binomial sum |
| R5 | A detector 0.01 below D8 at Pd 0.5 is rejected with probability 0.023 at 10,000 injections and 0.990 at 100,000 | COMPUTED | `python -c "from stats.theory import *; from stats.tolerance import *; z=q_inv(0.01); print([rejection_probability(0.49,0.01,z,n) for n in (10000,100000)])"`; normal approximation | a simulation of that detector |
| R6 | At Pfa 0.01 and Pd 0.5, dPd/dPfa = 14.97; a measured threshold brings a standard error of 1.489 / sqrt(m), added in quadrature; that equals the binomial term at m = 8.87 n; at n = 200,000 and m = 100,000 the tolerance is 0.0194 | COMPUTED | `python -c "from stats.theory import *; from stats.tolerance import *; z=q_inv(0.01); s=roc_slope(0.01,z); print(s, s*(0.01*0.99)**0.5, s*s*0.01*0.99/0.25, tolerance(0.01,z,200000,100000)['tolerance'])"` | the calibration test with a measured threshold |
| R7 | D11's script: the four counts, efficiencies and verdicts in its table; the rectified detector 0.9 se from 0.2045; one standard error with a measured threshold 0.0021; on the negated pulse, 9 found by the matched filter (9.1 predicted) and 81,658 by the rectified one, an efficiency of 0.2041, 0.5 se below 0.2045; the lower tail 7.6e-6; run time about 1.5 s (1.38 to 1.61 s over the runs made on this desktop; the round's verifier saw 1.41 s) | MEASURED | `python -m stats.d11`, 2026-11-23, seed 20261123, on the lead's desktop | a rerun; `tests/test_stat_d11.py` |
| R8 | With a peak of 3.0 the float `0x1.2000900048002p-15` is rounded to 2 by plain float arithmetic and to 1 by the exact rule; the float value is within 2^-23 of the true one and the guard is 2^-12 | COMPUTED | `python -m pytest -q -p no:cacheprovider tests/test_stat_quantise.py`; the bound is argued in `stats/quantise.py` | a set on which `quantise` differs from the exact rule |
| R9 | The largest score the definition allows is 2^23 * 2^17 * 128 * 3 = 2^48.58, below 2^53 | COMPUTED | `python -c "import math; print(math.log2(2**23 * 2**17 * 128 * 3))"` | a score that differs from the integer sum: `tests/test_stat_matched.py` |
| R10 | The correct filter's four rows in the gate's table | MEASURED | `python -m pytest -q -p no:cacheprovider -s tests/test_stat_gate_statistics.py`, 2026-11-23 | a rerun |
| R11 | Noise alone crosses the known threshold at 0.01032 of 100,000 scores (s16x1) and 0.00940 of 25,000 (s24x3) | MEASURED | the same command, the lines "noise alone" | a rerun |
| R12 | The 18-bit quantised pulse has a cosine of 1 - 1.09e-11 with the pulse, and on 200,000 injections it and the real coefficients disagree on none | MEASURED | the same command, the line "18-bit cost"; the cosine by `python -c "from spec import constants as C; from stats import quantise, theory; p=C.PULSES['e0']; print(1 - theory.deflection(quantise.quantise(p), p, 1.0) / theory.deflection(p, p, 1.0))"` | a rerun |
| R13 | A 3-bit quantised pulse has cosine 0.98990, predicted cost 0.0094, measured cost 0.0104 with a paired standard error of 0.0005 (5,668 found by the real set only, 3,580 by the 3-bit set only) | MEASURED | the same command, the line "3-bit cost" | a rerun |
| R14 | The seven wrong filters' rows in the controls' table; the four with a known threshold and a prediction away from zero are inside the tolerance of their own prediction | MEASURED | the same command, the lines "CONTROL" | a rerun |
| R15 | On the s24x3 stream, pulses are found at the index at 0.4976 and within +/-8 at 0.5781; on noise alone, at 9,000 places, 0.0094 and 0.0729 | MEASURED | the same command, the last printed line | a rerun |
| R16 | z = 4, and a check is refused below n p (1 - p) = 25 | DECISION | the lead, 2026-11-23, round 1's ledger, the entry approving STAT's design | the lead or the owner deciding otherwise |
| R17 | A threshold needs 100 noise scores above it; the quantiser's guard is 2^-12 and its widths 2 to 30 | DECISION | STAT's design of 2026-11-23, approved by the lead with it | a case that shows either is too loose: limit 3, and row R8 |
| R18 | Sigma for the gate's streams: 1477.33 (s16x1) and 5527.65 (s24x3), each norm of the injected pulse over Q^-1(0.01) | COMPUTED | `python -c "from spec import constants as C; from stats.theory import *; e=sum(v*v for v in C.PULSES['e0']); z=q_inv(0.01); print(e**0.5/z, (14*e)**0.5/z)"` | arithmetic |
| R19 | The exact fractions the calibration expects: 0.3143 outside one standard error and 0.0466 outside two, for 2,000 trials at one half (0.314304 and 0.046553, summed in integers). This row said 0.3146 until 2026-11-23; that was wrong | COMPUTED | `python -m pytest -q -p no:cacheprovider tests/test_stat_tolerance.py -k exact_fractions` | an exact binomial sum |
| R20 | STAT's tests: 223 of them, in 9 to 12 s over several runs on the lead's desktop while two other parcels were running theirs | MEASURED | `python -m pytest -q -p no:cacheprovider tests/test_stat_*.py`, 2026-11-23 | a rerun |
| R21 | The calibration: with a known threshold 2,480 of 8,000 experiments fall outside one standard error (2,514 expected, accepted within 166) and 352 outside two (372, within 75); with a measured threshold 652 of 2,000 (635, within 83) and 95 (91, within 37). The five broken tolerances are each reported: a quarter of the trials 352 and 1; four times the trials 4,819 and 2,480; 1.1 times too wide 2,172 and 188; 1.1 times too narrow 2,842 and 536; forgetting the measured threshold 1,095 and 509 of 2,000 | MEASURED | `python -m pytest -q -p no:cacheprovider -s tests/test_stat_tolerance.py`, 2026-11-23, seeds 20261123 and 20261124 | a rerun |
| R22 | The stated margin: 0.01349 below D8 is 12.1 standard errors at 200,000 injections and 8.1 beyond the tolerance's edge; the chance of that fault landing inside is below 1e-15 | COMPUTED | `python -c "from stats.theory import *; from stats.tolerance import *; z=q_inv(0.01); t=tolerance(0.01,z,200000); s=0.5-pd_matched(0.01,0.9854634*z); print(s, s/t['se_total'], s/t['se_total']-4, q(s/t['se_total']-4))"`; the cosine 0.9854634 is 1 - 2 * 293^2 / 11,811,446 | arithmetic; row R14's first line |
| R23 | What D11's quoted figures are in standard errors: (0.287 - 0.2822) / 0.0021 = 2.3 and (0.206 - 0.2045) / 0.0021 = 0.7; a rectifier costs 0.2822 - 0.2045 = 0.078 at this point | COMPUTED | from rows R2, R3 and R7; the 0.0021 is the matched filter's standard error with a measured threshold, used for the rectified detector too as an approximation | arithmetic; D11's own script, if it is ever found |
| R24 | What the tests hold, as counts: 240 random sets at six widths and 6,005 grid values in the quantiser's tests; scores against an integer loop at 1, 5, 64 and 128 taps; `q_inv` from 1e-300 to one half; 8,000 and 2,000 calibration experiments of 2,000 injections each; the gate's streams of 200,000 injections 64 apart with 6,400,000 pulse-free frames, and 25,000 injections 128 apart with gains (3, -1, 2); fifteen refusal names of this package's own | READ | `tests/test_stat_quantise.py`, `tests/test_stat_matched.py`, `tests/test_stat_theory.py`, `tests/test_stat_tolerance.py`, `tests/test_stat_gate_statistics.py`, `stats/errors.py`, as committed with this page | the files |
| R25 | Two figures a reader CANNOT reproduce from the tree, because the runs behind them are in STAT's scratch folder for the round and nowhere else: a correct detector's z-score with a measured threshold is biased by about -0.03 at k = 100 and -0.02 at k = 200 (20,000 experiments each); and about 3.5 million near ties at 18, 27 and 30 bits held no value where the float lands off a half-way point on the wrong side. Each needs a loop of the reader's own over this package's functions. The round's verifier reran the first by its own code and got -0.039 and -0.026 with a standard error of 0.01; nobody has rerun the second | ESTIMATE | scratch runs of 2026-11-23; no command in the tree reproduces either. The two figures this row used to carry that a reader CAN reproduce are now rows R27 and R28 | a committed run that finds otherwise |
| R26 | The recipe under "Handing a detector to the check", run as written with seed 1: inside at -0.3 standard errors (99,944 of 200,000); with tap 51 negated, outside at -12.3 (97,245 of 200,000) | MEASURED | `python -m pytest -q -p no:cacheprovider -s tests/test_stat_doc.py`, 2026-11-23, which takes the code block out of this page and runs it; the counts are for this desktop's numpy 2.2.6 | a rerun; the test asserts the two verdicts and prints the counts |
| R27 | The calibration's reach, from the tree: a known-threshold tolerance 1.05 times too wide is reported, and one 1.05 times too narrow is not | MEASURED | `python -c "import sys; sys.path.insert(0,'tests'); import test_stat_tolerance as T; from stats import tolerance; f=lambda k: (lambda found,n,pfa,d,m=None: dict(tolerance.check_efficiency(found,n,pfa,d,m), z_score=tolerance.check_efficiency(found,n,pfa,d,m)['z_score']/k)); print([T.calibration(f(k), False, 20261123)['calibrated'] for k in (1.05, 1/1.05)])"`, 2026-11-23, which prints [False, True]; for this desktop's numpy 2.2.6 and that seed | a rerun; another seed can move either answer, which is why it is a limit and not a test |
| R28 | With a measured threshold the calibration accepts a count within 83 of 635 in 2,000 experiments, 0.0416 as a fraction; the fraction outside one standard error moves by 0.484 per unit of relative width; so a width error under 8.6% leaves the expected count inside the band, and about 17% puts it a further band beyond the edge. Arithmetic, not a run | COMPUTED | `python -c "import math; b=4*math.sqrt(2000*0.3173*0.6827)/2000; s=2*math.exp(-0.5)/math.sqrt(2*math.pi); print(b, s, b/s, 2*b/s)"` | a run of the calibration on tolerances scaled by those amounts |
| R29 | A pfa written 0.29, 0.57 or 0.58 gives 2,899, 5,699 or 5,799 crossings over 10,000 scores, one fewer than the decimal reads; 0.25 gives 2,500 | COMPUTED | `python -c "from fractions import Fraction; print([int(Fraction(p) * 10000) for p in (0.29, 0.57, 0.58, 0.25)])"`; `tests/test_stat_recovery.py` holds it against `threshold_from_scores` | a rerun |
| R30 | `rejection_probability(0.8, 0.01, Q^-1(0.01), 100)` is 0.9938 = Q(-2.5); the prediction's spread would give Q(-2) = 0.9772; the exact binomial figure is 0.9888 | COMPUTED | `python -c "from stats.theory import *; from stats.tolerance import *; print(rejection_probability(0.8, 0.01, q_inv(0.01), 100), q(-2.5), q(-2.0))"`; the exact figure is summed in integers in `tests/test_stat_tolerance.py` | a rerun |

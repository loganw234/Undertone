# D1b: a first look at real records - one launch, one ladder, two control days

Written by the parcel LCH on 2026-11-23, phase 2 of [study D1](D1-launch-data.md). **This is a first look. It scores nothing and proves nothing statistical.** It took one launch, the one D1 chose, fetched 50 minutes of record from each station of D1's ladder on the launch day and on the day before and the day after, applied a measure written down before any waveform was fetched, and reports what the numbers were. One launch that someone had already written up cannot say how often a launch is seen, and two control days cannot say how often a quiet day looks like a launch.

Labels are D0's, as in D1. `<data>` is this parcel's data folder in the round's run folder, outside the repository; nothing in it is committed. `<scratch>` is its scratch folder. `<venv>` is the Python of the virtual environment under `<scratch>`.

## The answer in brief

Each sentence points at the rows that carry it.

- **A large signal is in the records, beginning inside the windows predicted beforehand, and it is on neither control day.** At CI.LOC, 16.5 km from the pad, power in the 2 to 8 Hz band rose to a median of 614 times its own pre-launch level across the predicted sound window, and was above 3 times for 454 of the seconds of a stretch that runs from 45 s to 502 s. On the two control days the same window's medians were 1.47 and 0.72, with no such stretch (Q1a). The measure sees power in a band at a time; it cannot say what made it. What points to the pad is its timing across four stations, by a measure chosen after looking and with a misfit that is given beside it (Q3b).
- **The nearest station asked for has no record.** CI.GATR, 13.5 km, answered 404 to all five requests, though its availability listing spans the date (Q1b). So LOC stood in as the nearest, and D1's control 6, which needs both, could not be run.
- **By the rule fixed beforehand it is seen at 16.5, 49.9 and 78.5 km, cannot be told at 32.6 and 120.4 km, and is not visible at 181.4 and 275.0 km** (Q2a). At 32.6 km the rule says cannot tell because a control day has a ten-second stretch in the window; the numbers there are 440 against 1.49 (Q2b). At 120.4 km it says cannot tell for a good reason: the day before shows a stretch beginning at the very same second (Q2c). Not visible is not the same as quiet: at 181.4 km both control days are far busier than the launch day (Q2d), and at 275.0 km the day after has a stretch that the launch day lacks (Q2e). *Restated by the lead on 2026-11-24:* this is one launch of 2021, with D1's close and this study's rule. [Study D3](D3-faint-launches.md), with a later close and D2's rule, found the 23 scored launches of 2024 seen at all four of these farther stations, 14 and 13 of 23 at 181.4 and 275.0 km, mostly from November to March; it says the 2021 launch, flown in September, fits that pattern.
- **By a measure chosen after looking, its onsets rise with distance at about the speed of sound, and the fit is loose.** Taking the first stretch that begins inside each sound window, the onsets at the four near stations are 45, 100, 211 and 224 s: a slope of 3.02 s per km, or 0.331 km/s, with residuals up to 49 s. Station to station the steps are 3.42, 6.42 and 0.45 s per km, and only the first of the three is inside D1's range for sound (Q3b). The slope fixed beforehand came out meaningless, because one station has an earlier, weaker stretch that the definition picked up (Q3a, Q3e).
- **It lasts far longer than D1 assumed**: 270 to 454 seconds, against a source taken to last 180 (Q4a). D1's windows close too early.
- **It stands out most in the 2 to 8 Hz band at three of the four stations, and in 8 to 20 Hz at the fourth** (Q4b). That is where it stands out, not where its power is: each figure is a ratio to that band's own noise at that station.
- **The records are three components at 100 samples a second, stored as Steim-1 in 4096-byte records, with no gap in any of the 25 files fetched** (Q5a, Q5b). Two files hold sample values outside the 16-bit range (Q5c): a 16-bit sample would not hold them.
- **The catalogue times this launch to the second, 03:55:50 UTC, and holds no code for a scrub** (Q6a, Q6b). Its code Z marks seven entries for launches of unknown vehicle (Q6c).
- **One control day is not a clean one.** An interceptor test flew from the same base 10.4 hours before the day-before window (Q6d).

## 1. What was fetched, and with what

Everything fetched is under `<data>`, with its request, the time, the size and the SHA-256 in [manifest.tsv](d1/manifest.tsv), written by [fetch.sh](d1/fetch.sh) one request after another. The list of requests is `python docs/studies/d1/download_list.py --fetch`: D1's section 8, unchanged, in its stated order.

<!-- d1b:manifest:begin -->

| file | fetched, UTC | HTTP status | bytes | SHA-256, first 16 hex digits |
|---|---|---|---|---|
| avail-CI-GATR.txt | 2026-11-23T15:12:50Z | 200 | 6596 | 1ca1771076ebf36d |
| avail-CI-LOC.txt | 2026-11-23T15:12:52Z | 200 | 3003 | 917c5ac2e425bbb4 |
| avail-CI-SYN.txt | 2026-11-23T15:12:54Z | 200 | 3003 | 7ce34b4060594cc5 |
| avail-CI-MPP.txt | 2026-11-23T15:12:55Z | 200 | 3795 | 68d4ae902c630fe8 |
| avail-CI-CDM.txt | 2026-11-23T15:12:57Z | 200 | 6523 | 19244856ff744b9c |
| avail-CI-HDH.txt | 2026-11-23T15:12:59Z | 200 | 3003 | 8a4a2b9f3ec759b2 |
| avail-CI-SRN.txt | 2026-11-23T15:13:00Z | 200 | 4323 | 5e849b88d3ce892e |
| gcat-launch.tsv | 2026-11-23T15:13:02Z | 200 | 13818818 | 456f6acdb9b5ef78 |
| gcat-lp.tsv | 2026-11-23T15:13:05Z | 200 | 367898 | 6434a0b58cb9662b |
| gcat-sites.tsv | 2026-11-23T15:13:07Z | 200 | 125822 | 82588d9aef69112d |
| CI.GATR.HHZ.2021-09-14.mseed | 2026-11-23T15:14:01Z | 404 | 0 | no file |
| CI.LCP.HHZ.2021-09-14.mseed | 2026-11-23T15:14:02Z | 200 | 561152 | 0e20ef570d12a22b |
| CI.SYN.HHZ.2021-09-14.mseed | 2026-11-23T15:14:05Z | 200 | 405504 | 4b12b94670710637 |
| CI.LOC.HHZ.2021-09-14.mseed | 2026-11-23T15:14:07Z | 200 | 454656 | 881b16c671eeb524 |
| CI.MPP.HHZ.2021-09-14.mseed | 2026-11-23T15:14:09Z | 200 | 344064 | 090d12e5bac09025 |
| CI.CDM.HHZ.2021-09-14.mseed | 2026-11-23T15:14:11Z | 200 | 327680 | d67699b0478c1b1f |
| CI.HDH.HHZ.2021-09-14.mseed | 2026-11-23T15:14:13Z | 200 | 327680 | 15c46073d5b38c08 |
| CI.SRN.HHZ.2021-09-14.mseed | 2026-11-23T15:14:16Z | 200 | 643072 | 5b1c8c017e3a550c |
| CI.GATR.HHZ.2021-09-13.mseed | 2026-11-23T15:14:18Z | 404 | 0 | no file |
| CI.LOC.HHZ.2021-09-13.mseed | 2026-11-23T15:14:19Z | 200 | 385024 | 529cbdef7dd5d347 |
| CI.LCP.HHZ.2021-09-13.mseed | 2026-11-23T15:14:21Z | 200 | 380928 | aaa1df8c735034c4 |
| CI.SYN.HHZ.2021-09-13.mseed | 2026-11-23T15:14:24Z | 200 | 356352 | b6117149fd294b07 |
| CI.MPP.HHZ.2021-09-13.mseed | 2026-11-23T15:14:26Z | 200 | 348160 | 7264f7c70a2c799e |
| CI.CDM.HHZ.2021-09-13.mseed | 2026-11-23T15:14:28Z | 200 | 327680 | 0fa034433f13b855 |
| CI.HDH.HHZ.2021-09-13.mseed | 2026-11-23T15:14:30Z | 200 | 327680 | 25c168f5871fa945 |
| CI.SRN.HHZ.2021-09-13.mseed | 2026-11-23T15:14:32Z | 200 | 638976 | 063cee37558c6c14 |
| CI.GATR.HHZ.2021-09-15.mseed | 2026-11-23T15:14:34Z | 404 | 0 | no file |
| CI.LOC.HHZ.2021-09-15.mseed | 2026-11-23T15:14:36Z | 200 | 385024 | 7225bcb7d99d1f05 |
| CI.LCP.HHZ.2021-09-15.mseed | 2026-11-23T15:14:38Z | 200 | 655360 | 62a9938bf0a65540 |
| CI.SYN.HHZ.2021-09-15.mseed | 2026-11-23T15:14:40Z | 200 | 393216 | 537fe562bcf933f8 |
| CI.MPP.HHZ.2021-09-15.mseed | 2026-11-23T15:14:42Z | 200 | 331776 | f6eb623e7f6f9722 |
| CI.CDM.HHZ.2021-09-15.mseed | 2026-11-23T15:14:44Z | 200 | 327680 | e3d9afb1f6965620 |
| CI.HDH.HHZ.2021-09-15.mseed | 2026-11-23T15:14:46Z | 200 | 327680 | f1d8b960030d609f |
| CI.SRN.HHZ.2021-09-15.mseed | 2026-11-23T15:14:48Z | 200 | 643072 | 9022bcfd91f196be |
| CI.GATR.HHE.2021-09-14.mseed | 2026-11-23T15:14:51Z | 404 | 0 | no file |
| CI.GATR.HHN.2021-09-14.mseed | 2026-11-23T15:14:52Z | 404 | 0 | no file |
| CI.LCP.HHE.2021-09-14.mseed | 2026-11-23T15:14:54Z | 200 | 569344 | db4629d50a07c5c8 |
| CI.LCP.HHN.2021-09-14.mseed | 2026-11-23T15:14:56Z | 200 | 569344 | b908ae1a60da7c39 |
| CI.SYN.HHE.2021-09-14.mseed | 2026-11-23T15:14:58Z | 200 | 376832 | f9da910e5709efd6 |
| CI.SYN.HHN.2021-09-14.mseed | 2026-11-23T15:15:00Z | 200 | 380928 | 8186934072475cfa |
| scedc-events-2021-09-13.txt | 2026-11-23T15:15:02Z | 200 | 172 | 318afba41230001e |
| scedc-events-2021-09-14.txt | 2026-11-23T15:15:04Z | 200 | 1540 | 7d3a04fdc9e1b15e |
| scedc-events-2021-09-15.txt | 2026-11-23T15:15:06Z | 200 | 1537 | 0c43f0864e5804d9 |

43 requests; 38 answered with a file; 25134897 bytes in all.

<!-- d1b:manifest:end -->

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| R1 | 43 requests were made for this look, one after another: 7 availability listings, 3 catalogue files, 30 waveform requests of which 25 came as files and 5 were answered 404, and 3 earthquake listings. The 38 files are 25,134,897 bytes. The launch list is 13,818,818 bytes, 182 bytes an entry, not the 22.8 MB D1 estimated | MEASURED | [manifest.tsv](d1/manifest.tsv), written by fetch.sh on 2026-11-23 from 08:12 to 08:15 local; `python docs/studies/d1/figures.py`, line F20 | the manifest; the files' hashes |
| R2 | The tools are in a virtual environment under `<scratch>`: Python 3.12.15 with numpy 2.5.5, matplotlib 3.11.2, obspy 1.5.2 and what they pull in, 23 packages. pip downloaded 9 wheels, 36.7 MB, and took 14, 55.4 MB, from the desktop's own pip cache. Nothing was installed into the desktop's shared Python | MEASURED | `<scratch>/pip-install.log`, its lines Downloading and Using cached; `<venv> -m pip list`; figures.py, line F18 | the log |
| R3 | pip also wrote the 9 wheels it downloaded into the desktop's pip cache, which is outside the scratch folder. That was not intended: the install was run without the option that turns the cache off | MEASURED | `<venv> -m pip cache dir` names the folder; the log's Using cached lines show the same cache being read | the cache's contents |
| R4 | The package index's terms were read before the install. They limit who may use the index: a person who is, or is working on behalf of, one on a named United States sanctions list may not. Whether that limit touches anyone here is not this study's to judge; the lead has put it to the owner. When first written this row said nothing in the terms limits who may download a package. That was wrong: the sentence was on the page and was missed | READ | https://policies.python.org/pypi.org/Terms-of-Service/, read 2026-11-23, its opening paragraph and Account Terms, section 3, Account Requirements: "Please read this Terms of Service agreement carefully before accessing or using PyPI." and "You may not use PyPI if you are or are working on behalf of a Specially Designated National (SDN)" | the page |
| R5 | The samples were read by this study's own reader and again by obspy, and the two agree on every one of 7,500,025 samples in the 25 files, on each file's first sample time and on its rate. A changed sample is reported by the comparison | MEASURED | `<venv> docs/studies/d1/compare_readers.py <data>`, 2026-11-23: its last line reads OK compare: 25 files, 7500025 samples, the two readers agree on every one (obspy 1.5.2) | an error both readers share |

**Why two readers.** The look needs facts a package hides: each record's encoding, its length, the widths its samples are stored in. So [mseed.py](d1/mseed.py) reads the headers itself, and decodes the samples too. Every Steim record carries its own first and last sample, and the reader refuses a record whose decoded last sample is not the one the record names. Then [compare_readers.py](d1/compare_readers.py) holds it against obspy. obspy alone would have been less code; neither alone would have been a check.

## 2. The measure, fixed before any waveform was fetched

The measure is D1's section 8 as committed at `4247b73`, and the decision rule and order of work are in the round's ledger, in this parcel's file, under 2026-11-23 08:11. The first waveform request was made at 08:14. Nothing in it was changed afterwards. [firstlook.py](d1/firstlook.py) is that measure and nothing else; its docstring states it in full, and its self-test (`python docs/studies/d1/firstlook.py --self-test`, 9 cases) plants a 5 Hz burst in noise and finds it, finds nothing in the noise alone, and checks the stretch rule on a case worked by hand.

In short: band power in 4-second frames, one a second, in four bands; a ratio to the median of the ten minutes that end one minute before T0; a second is up above 3; a stretch tolerates one second that is not up and counts with ten that are; and at each station, in the 2 to 8 Hz band of the vertical channel, the launch is **SEEN** if the launch day has a counting stretch that begins inside a predicted window and neither control day has one that begins inside the same window, **CANNOT TELL** if a control day has one too, and **NOTHING VISIBLE** if the launch day has none.

Three things the look had to settle that the measure had left open, each settled the way that changes least:

- *T0.* The catalogue's entry is to the second (Q6a), so T0 is 2021-09-14 03:55:50 UTC and no minute was added to any window.
- *Distances.* The windows use D1's distances, as written beforehand. The catalogue's pad table puts the pad 0.1 to 0.2 km nearer each station (Q6e); that moves no window's edge by a second.
- *A frame with a missing sample.* None occurred: every file is whole (Q5a).

Everything measured beyond this is in section 5 under its own heading, **chosen after looking**, and is said to be so wherever it is used.

## 3. The seven questions

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| Q1a | Question 1. At the nearest station with a record, CI.LOC, 16.5 km, in the 2 to 8 Hz band of the vertical channel, over the sound window (42 to 254 s after T0): the median ratio was 614.02 on the launch day, 1.47 the day before and 0.72 the day after. Up seconds: 209 of 212, against 15 and 1. A counting stretch of 454 up seconds, from 45 s to 502 s, on the launch day; none on either control day. Reading by the rule: SEEN | MEASURED | `python docs/studies/d1/firstlook.py <data>`, the first table of section 5, row CI.LOC | more control days: with two, how often a quiet day shows such a stretch is not known |
| Q1b | The nearest station asked for, CI.GATR, 13.5 km, has no record for any of the three days: all five requests were answered 404. Its availability listing gives its HHZ channel an extent from 2014 to 2026, so an extent hid a gap, as D1 warned it could | MEASURED | the five CI.GATR rows of the manifest in section 1; the HHZ line of `<data>/avail-CI-GATR.txt` | the data centre answering differently |
| Q2a | Question 2. By the rule, in the sound window: SEEN at CI.LOC (16.5 km), CI.SYN (49.9) and CI.MPP (78.5); CANNOT TELL at CI.LCP (32.6) and CI.CDM (120.4); NOTHING VISIBLE at CI.HDH (181.4) and CI.SRN (275.0). So it stops, for this launch, this band and this rule, somewhere past 78.5 km. *Restated by the lead at round 3's close, 2026-11-25:* for this 2021 launch only. In 2024, by study D3's rule, 14 of 23 and 13 of 23 scored launches hit at CI.HDH and CI.SRN. That study used another close and another hit rule ([D3](D3-faint-launches.md), sections 3, 5 and 12) | MEASURED | the same command; the first table of section 5 | another launch; another day's air |
| Q2b | At CI.LCP the rule says CANNOT TELL because the day after has a stretch of 10 up seconds in the window. The numbers beside it: a launch-day median of 440.16 against 0.56 and 1.49; 223 of 232 seconds up against 17 and 36; a launch-day stretch of 412 up seconds. That station is noisy on all three days: it has more than ten counting stretches in each 50 minutes | MEASURED | the same command; the first table and the last table of section 5 | a rule that weighs a stretch's length would read this differently; none was fixed beforehand |
| Q2c | At CI.CDM a counting stretch begins at the same second, 471 s after the stand-in time, on the launch day (62 up seconds) and on the day before (20). Something there recurs at one clock time on two days, and the launch cannot be told from it | MEASURED | the same command; the first and last tables of section 5 | records of more days at that hour |
| Q2d | NOTHING VISIBLE at CI.HDH does not mean a quiet station. In the sound window its launch day has 49 up seconds of 421 and no counting stretch; the day before has 40 and a stretch of 11, the day after 55 and a stretch of 21. From T0 to the sound window's opening the launch day is up 6 of 520 seconds and the control days 172 and 167, each with a stretch of 56 up seconds, beginning 191 s and 218 s after the stand-in time. Over the whole 50 minutes there are 6 counting stretches on the launch day, 9 the day before and 8 the day after. At that station, at this hour, both control days were busier than the launch day. Why was not looked at | MEASURED | `python docs/studies/d1/firstlook.py <data>`, the two window tables and the last table of section 5, rows CI.HDH; `python docs/studies/d1/secondlook.py <data>`, table C, row CI.HDH | records of more days at that hour |
| Q2e | At CI.SRN the day after has a counting stretch of 45 up seconds, from 1329 s to 1375 s after the stand-in time, and the launch day has none. The catalogue lists a magnitude 0.70 earthquake that day at 04:18:15, which is 1345 s after the stand-in time, 136.8 km from the station. The numbers do not allow it to be what began the stretch: the stretch's first up second is 16 s before the earthquake happened. At the fastest ground speed D1 considers, none of its waves reaches the station before 1366 s, so they could fall only in the stretch's last 9 seconds. What began the stretch is not established | COMPUTED | `python docs/studies/d1/figures.py`, line F28, from firstlook.py's sound-window table, row CI.SRN, and the line for event 39809063 in `<data>/scedc-events-2021-09-15.txt` | what would settle it: that station's ratio second by second from 1320 s to 1400 s, and the same minute at stations nearer the epicentre. Neither was looked at |
| Q3a | Question 3, as fixed beforehand. The onsets on the launch day are 45 s at CI.LOC, 100 s at CI.LCP, 211 s at CI.SYN, 26 s at CI.MPP and 471 s at CI.CDM; CI.HDH and CI.SRN have none. The slope over the three stations read as SEEN is -0.16 s per km with a residual of 117 s: neither sound nor ground. It is meaningless, because CI.MPP's first counting stretch, at 26 s, is not its large one, which begins at 224 s | MEASURED | the same command; the onset table of section 5 and the line under it | a definition of onset that survives a station with two stretches |
| Q3b | Question 3, chosen after looking. Taking the first counting stretch that begins inside the sound window: 45, 100, 211 and 224 s at 16.5, 32.6, 49.9 and 78.5 km. Distance over onset is 0.367, 0.326, 0.236 and 0.350 km/s. The slope is 3.02 s per km, 0.331 km/s, with residuals of -16, -9, +49 and -24 s. The fit is loose. Station to station the steps are 3.42, 6.42 and 0.45 s per km (55 s over 16.1 km, 111 s over 17.3 km, 13 s over 28.6 km), and only the first is inside D1's range for sound, 2.90 to 4.17: the four onsets do not lie on one line at the speed of sound. The slope across all four is inside that range and far from the range for the ground, 0.15 to 0.67. With CI.CDM's 471 s at 120.4 km added, a stretch a control day shares, it is 3.89 s per km | MEASURED | `python docs/studies/d1/secondlook.py <data>`, table A of section 5 and the second line under it; `python docs/studies/d1/figures.py`, line F27, for the steps | this measure was chosen after seeing the records; another launch, with the definition fixed first |
| Q3c | Which window: all four of those onsets lie inside the sound window. All four also lie inside the ground window, which on D1's constants is long and overlaps it. The window does not tell the paths apart. A slope would, and the only slope in hand that is not meaningless was chosen after looking and fits loosely (Q3b) | MEASURED | firstlook.py's onset table, columns in the sound window and in the ground window; its two window tables | a ground window drawn from measured ground speeds |
| Q3d | CI.LOC's onset, 45 s, gives 0.367 km/s, faster than the 0.345 that D1 took as the fastest. An onset is known to about 2 s, which makes it 0.351 to 0.384 km/s; and the engines light before first motion, by how long was not read | COMPUTED | `python docs/studies/d1/figures.py`, line F21, from Q3b | the true first arrival, from a shorter frame |
| Q3e | Chosen after looking. CI.MPP alone shows power before its sound window opens: between T0 and 222 s it is up for 132 of 222 seconds on the launch day, with a median ratio of 3.64, against 0 and 4 seconds on the control days. CI.LOC shows none (0 of 42 seconds), and CI.LCP and CI.SYN show no more than on a control day. What it is is not established. A path through the ground from the pad would arrive there about then, but would reach the nearer stations first | MEASURED | secondlook.py, table C of section 5; firstlook.py's last table, row CI.MPP, launch day | the same at another launch; the nearer stations' noise in the same units |
| Q4a | Question 4. In the 2 to 8 Hz band the stretch lasts 454 up seconds at CI.LOC (to 502 s), 412 at CI.LCP (to 511 s), 270 at CI.SYN (to 481 s) and 351 at CI.MPP (to 574 s). Each ends after its sound window has closed, by 248, 190, 88 and 62 s | MEASURED | firstlook.py's first table; figures.py, line F26 | another launch |
| Q4b | The band: 2 to 8 Hz has the largest median ratio at CI.LOC (614 against 70 and 76 in the two higher bands), CI.LCP (440 against 47 and 1.13) and CI.MPP (844 against 5.3 and 160). At CI.SYN 8 to 20 Hz is larger (183 against 88). The 0.5 to 2 Hz band shows no counting stretch at three of the four and one of 10 seconds at CI.LCP. A ratio is to that band's own noise at that station, so this is where the launch stands out, not where its power is | MEASURED | firstlook.py's table Every band, section 5 | spectra in physical units |
| Q4c | The two horizontal channels show the same stretch as the vertical at the two stations where they were fetched: at CI.LCP medians of 379 and 497 beside the vertical's 440, at CI.SYN 38 and 52 beside 88 | MEASURED | firstlook.py's table of the horizontal channels, section 5 | the horizontals at other stations, which were not asked for |
| Q5a | Question 5. Each of the 25 files holds 300,001 samples at 100 a second, from within 4 ms of the second asked for to 50 minutes later, in 4096-byte records, Steim-1, with no gap | MEASURED | `python docs/studies/d1/mseed.py <data>/*.mseed`, the records table of section 4 | the files' hashes in the manifest |
| Q5b | Components: the vertical at seven stations on three days, and both horizontals at CI.LCP and CI.SYN on the launch day. Three components are in the archive as records, as the metadata said | MEASURED | the same table; the manifest | the horizontals at the other five, which were not asked for |
| Q5c | Sample width as stored: each record keeps its first and last sample as 32-bit integers and the rest as differences of 8, 16 or 32 bits. The samples themselves run from -36,647 to 35,420 across the 25 files. Two files, CI.LCP's HHN and HHZ on the launch day, hold values outside a signed 16-bit range and need 17 bits; the other 23 need 11 to 16 | MEASURED | the same table, its columns smallest, largest and bits a sample needs; figures.py, line F25 | a longer record; these are 50 minutes each |
| Q5d | The data centre read a bare time as UTC: a request for 03:40:00 returned a first sample stamped 03:39:59.998 on the day asked for | MEASURED | the same table, column first sample | the files |
| Q5e | The 25 files are 10,788,864 bytes: from 1.09 to 2.18 bytes a sample, 1.44 on average. D1 guessed 2 | COMPUTED | figures.py, line F19, from the manifest's sizes and Q5a | arithmetic |
| Q6a | Question 6. The catalogue's entry for this launch, tag 2021-082, reads 2021 Sep 14 0355:50: to the second and not marked uncertain. A Falcon 9, flight Starlink-32 (N30), site VSFBS, pad SLC4E, code OS, its time cited to Wire. Seven hours earlier is 20:55:50 on 13 September, the post's 8:56 pm | MEASURED | `python docs/studies/d1/catalogue.py <data>`, section 4; figures.py, line F22 | the catalogue's file as fetched, by its hash |
| Q6b | Scrubs: among 76,039 entries the second letter of the launch code is S, U, F, E, Z or A and nothing else. The word scrub occurs in two entries' notes, of 1966 and 1973, each a failure that followed a scrub. The file holds no entry for a countdown that was called off | MEASURED | the same command; the launch codes and the scrub lines of section 4 | a later release of the catalogue |
| Q6c | Code Z: seven entries are coded ZZ, each of vehicle R-UNK, six of them at site UNK. Code A, a pad abort: six entries, one Titan II of 1965 and five Space Shuttle, which fits the column description's words on human spaceflight | MEASURED | the same command; the table of entries whose code holds Z or A, section 4 | a later release |
| Q6d | The day-before control is not clean by D1's own rule. A GBI interceptor flew from site VSFB at 17:30 on 12 September, 10.4 hours before that day's stand-in time; D1's section 7 asks for 24. The day after has no launch from the base within 24 hours but the launch itself, 24 hours before | MEASURED | the same command; the table of launches within 24 hours, section 4 | the catalogue |
| Q6e | The catalogue's pad table puts SLC4E at 34.6320 N, 120.6106 W, to 0.0001 of a degree. Each ladder station is 0.1 to 0.2 km nearer that point than D1's distances say | MEASURED | the same command; the pad's line and table, section 4 | a survey of the pad |
| Q6f | The catalogue lists 46 Falcon 9 launches from Vandenberg in 2024, all from SLC4E. 35 of them are timed to the second and not marked uncertain | MEASURED | the same command; its last line, section 4 | a later release |
| Q6g | The regional earthquake catalogue lists no event from 03:00 to 05:00 UTC on the day before, and seven on each of the other two days, none larger than magnitude 1.39. On the launch day none falls between T0 and 15 minutes after it. Each of those two days has one entry of type ex, with no location, at 03:49:48 and at 04:05:06 (Q6h says what the type is). The launch day's is 362 s before T0, inside the ten minutes the noise is taken from; the day after's is 556 s after the stand-in time. Distant large earthquakes were not checked | MEASURED | `<data>/scedc-events-2021-09-13.txt`, `-14.txt` and `-15.txt`, fetched 2026-11-23 | a catalogue of distant earthquakes, which was not asked |
| Q6h | The type ex is the data centre's code for an explosion: its event service lists Explosion among its event types, and in that page's source the option labelled Explosion carries the value ex. So the two entries of Q6g are catalogued as explosions. Each has latitude 0, longitude 0, depth 0 and magnitude 0 in the listing, with a magnitude type un: the catalogue gives them a time and a type, and no place and no size. Reach: a label on a menu. No page read defines what the network counts as an explosion, or says why an entry has no location; whether either entry is anything the ladder's stations recorded was not looked at | READ | https://service.scedc.caltech.edu/fdsnws/event/1/, the URL Builder's menu Event Types, read 2026-11-23: "Event Types Any Earthquake Quarry blast Nuclear test Sonic blast Shot Long period Explosion Unknown"; the value ex is in the page's source, on the option labelled Explosion, and is not text a reader sees. The entries' fields are in `<data>/scedc-events-2021-09-14.txt` and `-15.txt` | a page of the data centre that defines its event types. Its page About SCEDC Catalogs was read for this on 2026-11-23 and does not |
| Q7 | Question 7. Eleven rows of D1 are restated from this look: L4, W3, W6, M6, M9, E1 to E6. Three of them were wrong as estimates (W3, E1, E3), three moved from BELIEVED to MEASURED (L4, W6, and M6's question for D0), and the rest are sizes now measured | MEASURED | section 7 of this file lists each; D1's own section Changes after the first look | D1's rows as they now stand |

## 4. The records, and the catalogue

<!-- d1b:records:begin -->

| file | channel | records | record bytes | encoding | samples/s | samples | first sample, UTC | last sample, UTC | gaps | smallest | largest | bits a sample needs | differences stored in 8, 16, 32 bits |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CI.CDM.HHZ.2021-09-13.mseed | CI.CDM..HHZ | 80 | 4096 | Steim-1 | 100 | 300001 | 2021-09-13 03:40:00.0031 | 2021-09-13 04:30:00.0031 | 0 | -1186 | 2233 | 13 | 299668, 332, 1 |
| CI.CDM.HHZ.2021-09-14.mseed | CI.CDM..HHZ | 80 | 4096 | Steim-1 | 100 | 300001 | 2021-09-14 03:40:00.0031 | 2021-09-14 04:30:00.0031 | 0 | -717 | 1434 | 12 | 299324, 676, 1 |
| CI.CDM.HHZ.2021-09-15.mseed | CI.CDM..HHZ | 80 | 4096 | Steim-1 | 100 | 300001 | 2021-09-15 03:40:00.0031 | 2021-09-15 04:30:00.0031 | 0 | -674 | 1314 | 12 | 299980, 20, 1 |
| CI.HDH.HHZ.2021-09-13.mseed | CI.HDH..HHZ | 80 | 4096 | Steim-1 | 100 | 300001 | 2021-09-13 03:39:59.9999 | 2021-09-13 04:29:59.9999 | 0 | -823 | 560 | 11 | 299900, 100, 1 |
| CI.HDH.HHZ.2021-09-14.mseed | CI.HDH..HHZ | 80 | 4096 | Steim-1 | 100 | 300001 | 2021-09-14 03:40:00.0000 | 2021-09-14 04:30:00.0000 | 0 | -1062 | 993 | 12 | 299172, 828, 1 |
| CI.HDH.HHZ.2021-09-15.mseed | CI.HDH..HHZ | 80 | 4096 | Steim-1 | 100 | 300001 | 2021-09-15 03:40:00.0000 | 2021-09-15 04:30:00.0000 | 0 | -1068 | 1338 | 12 | 299316, 684, 1 |
| CI.LCP.HHE.2021-09-14.mseed | CI.LCP..HHE | 139 | 4096 | Steim-1 | 100 | 300001 | 2021-09-14 03:39:59.9983 | 2021-09-14 04:29:59.9983 | 0 | -30920 | 32710 | 16 | 78420, 221580, 1 |
| CI.LCP.HHN.2021-09-14.mseed | CI.LCP..HHN | 139 | 4096 | Steim-1 | 100 | 300001 | 2021-09-14 03:39:59.9983 | 2021-09-14 04:29:59.9983 | 0 | -36647 | 33806 | 17 | 76556, 223444, 1 |
| CI.LCP.HHZ.2021-09-13.mseed | CI.LCP..HHZ | 93 | 4096 | Steim-1 | 100 | 300001 | 2021-09-13 03:39:59.9983 | 2021-09-13 04:29:59.9983 | 0 | -20588 | 20403 | 16 | 251244, 48756, 1 |
| CI.LCP.HHZ.2021-09-14.mseed | CI.LCP..HHZ | 137 | 4096 | Steim-1 | 100 | 300001 | 2021-09-14 03:39:59.9983 | 2021-09-14 04:29:59.9983 | 0 | -29207 | 35420 | 17 | 86848, 213150, 3 |
| CI.LCP.HHZ.2021-09-15.mseed | CI.LCP..HHZ | 160 | 4096 | Steim-1 | 100 | 300001 | 2021-09-15 03:39:59.9983 | 2021-09-15 04:29:59.9983 | 0 | -10280 | 12526 | 15 | 0, 300000, 1 |
| CI.LOC.HHZ.2021-09-13.mseed | CI.LOC..HHZ | 94 | 4096 | Steim-1 | 100 | 300001 | 2021-09-13 03:39:59.9983 | 2021-09-13 04:29:59.9983 | 0 | -1639 | 958 | 12 | 248516, 51484, 1 |
| CI.LOC.HHZ.2021-09-14.mseed | CI.LOC..HHZ | 111 | 4096 | Steim-1 | 100 | 300001 | 2021-09-14 03:39:59.9983 | 2021-09-14 04:29:59.9983 | 0 | -23331 | 22089 | 16 | 184156, 115844, 1 |
| CI.LOC.HHZ.2021-09-15.mseed | CI.LOC..HHZ | 94 | 4096 | Steim-1 | 100 | 300001 | 2021-09-15 03:39:59.9983 | 2021-09-15 04:29:59.9983 | 0 | -2606 | 1758 | 13 | 246936, 53064, 1 |
| CI.MPP.HHZ.2021-09-13.mseed | CI.MPP..HHZ | 85 | 4096 | Steim-1 | 100 | 300001 | 2021-09-13 03:39:59.9983 | 2021-09-13 04:29:59.9983 | 0 | 3710 | 5552 | 14 | 283044, 16956, 1 |
| CI.MPP.HHZ.2021-09-14.mseed | CI.MPP..HHZ | 84 | 4096 | Steim-1 | 100 | 300001 | 2021-09-14 03:39:59.9983 | 2021-09-14 04:29:59.9983 | 0 | 2839 | 5962 | 14 | 285488, 14512, 1 |
| CI.MPP.HHZ.2021-09-15.mseed | CI.MPP..HHZ | 81 | 4096 | Steim-1 | 100 | 300001 | 2021-09-15 03:39:59.9983 | 2021-09-15 04:29:59.9983 | 0 | 3317 | 5757 | 14 | 296956, 3044, 1 |
| CI.SRN.HHZ.2021-09-13.mseed | CI.SRN..HHZ | 156 | 4096 | Steim-1 | 100 | 300001 | 2021-09-13 03:39:59.9983 | 2021-09-13 04:29:59.9983 | 0 | -1132 | 2769 | 13 | 13344, 286656, 1 |
| CI.SRN.HHZ.2021-09-14.mseed | CI.SRN..HHZ | 157 | 4096 | Steim-1 | 100 | 300001 | 2021-09-14 03:39:59.9983 | 2021-09-14 04:29:59.9983 | 0 | -1673 | 3247 | 13 | 10952, 289048, 1 |
| CI.SRN.HHZ.2021-09-15.mseed | CI.SRN..HHZ | 157 | 4096 | Steim-1 | 100 | 300001 | 2021-09-15 03:39:59.9983 | 2021-09-15 04:29:59.9983 | 0 | -1402 | 2856 | 13 | 11180, 288820, 1 |
| CI.SYN.HHE.2021-09-14.mseed | CI.SYN..HHE | 92 | 4096 | Steim-1 | 100 | 300001 | 2021-09-14 03:39:59.9983 | 2021-09-14 04:29:59.9983 | 0 | -4950 | 5387 | 14 | 255312, 44688, 1 |
| CI.SYN.HHN.2021-09-14.mseed | CI.SYN..HHN | 93 | 4096 | Steim-1 | 100 | 300001 | 2021-09-14 03:39:59.9983 | 2021-09-14 04:29:59.9983 | 0 | -3304 | 5968 | 14 | 251060, 48940, 1 |
| CI.SYN.HHZ.2021-09-13.mseed | CI.SYN..HHZ | 87 | 4096 | Steim-1 | 100 | 300001 | 2021-09-13 03:39:59.9983 | 2021-09-13 04:29:59.9983 | 0 | -1250 | 3363 | 13 | 275404, 24596, 1 |
| CI.SYN.HHZ.2021-09-14.mseed | CI.SYN..HHZ | 99 | 4096 | Steim-1 | 100 | 300001 | 2021-09-14 03:39:59.9983 | 2021-09-14 04:29:59.9983 | 0 | -8392 | 8642 | 15 | 227056, 72944, 1 |
| CI.SYN.HHZ.2021-09-15.mseed | CI.SYN..HHZ | 96 | 4096 | Steim-1 | 100 | 300001 | 2021-09-15 03:39:59.9983 | 2021-09-15 04:29:59.9983 | 0 | -1272 | 3307 | 13 | 238588, 61412, 1 |

<!-- d1b:records:end -->

What the launch catalogue says, by [catalogue.py](d1/catalogue.py):

<!-- d1b:catalogue:begin -->

The launch list: 76039 entries, 33 columns, the file's own line: Updated 2026 Nov 23 0025:09.

**The launch.** Tag 2021-082: Launch_Date `2021 Sep 14 0355:50`, which is to the second; vehicle Falcon 9; flight Starlink-32 (N30); site VSFBS, pad SLC4E; LaunchCode OS; time cited to `Wire`.

**Every entry within two days of it.**

| tag | Launch_Date | vehicle | site | pad | code | hours from T0 |
|---|---|---|---|---|---|---|
| 2021-S61 | 2021 Sep 12 1730 | GBI | VSFB | - | MS | -34.4 |
| 2021-082 | 2021 Sep 14 0355:50 | Falcon 9 | VSFBS | SLC4E | OS | +0.0 |
| 2021-083 | 2021 Sep 14 1807:19 | Soyuz-2-1B | GIK-5 | LC31 | OS | +14.2 |
| 2021-S62 | 2021 Sep 15 | Hyunmoo-4 | ANHU | - | MS | time not given |
| 2021-M05 | 2021 Sep 15 0334 | Hwasong-11Ga | YDK | - | MS | +23.6 |
| 2021-M06 | 2021 Sep 15 0339 | Hwasong-11Ga | YDK | - | MS | +23.7 |
| 2021-084 | 2021 Sep 16 0002:56 | Falcon 9 | KSC | LC39A | OS | +44.1 |

**Launches from Vandenberg's site codes (V, VS, VSFB, VSFBS) within 24 hours of each day's stand-in time.**

| day | stand-in time, UTC | launches within 24 hours, other than 2021-082 |
|---|---|---|
| the day before | 2021-09-13 03:55:50 | 2021-S61, GBI, 2021 Sep 12 1730, -10.4 h |
| launch day | 2021-09-14 03:55:50 | none |
| the day after | 2021-09-15 03:55:50 | none |

**The pad.** The pad table (Updated 2026 Nov 23 0024:40) lists SLC4E under site VS at latitude 34.6320, longitude -120.6106, error 0.0001; name: Space Launch Complex 4-East, Vandenberg AFB.

| station | km from the study's point (34.633, -120.613) | km from the pad table's point | difference |
|---|---|---|---|
| CI.GATR | 13.5 | 13.3 | -0.2 |
| CI.LOC | 16.5 | 16.4 | -0.1 |
| CI.LCP | 32.6 | 32.4 | -0.2 |
| CI.SYN | 49.9 | 49.7 | -0.2 |
| CI.MPP | 78.5 | 78.3 | -0.2 |
| CI.CDM | 120.4 | 120.2 | -0.2 |
| CI.HDH | 181.4 | 181.2 | -0.2 |
| CI.SRN | 275.0 | 274.8 | -0.2 |

**Launch codes.** First letter, then second letter, with the number of entries.

- first letter: S 49335, M 15585, O 7223, A 2675, Y 455, D 229, H 210, T 175, R 106, N 16, L 12, X 11, Z 7
- second letter: S 62616, U 10652, F 2731, E 27, Z 7, A 6

**Entries whose code holds Z, or A for a pad abort: 13.**

| tag | Launch_Date | vehicle | site | pad | code | notes |
|---|---|---|---|---|---|---|
| 1965-A245 | 1965 Dec 12 1454:06 | Titan II GLV | CC | LC19 | OA | Abort, no launch |
| 1971-000 | 1971 May  5 0743:01 | R-UNK | CC | LC40 | ZZ | - |
| 1977-C01 | 1977 Sep 29 0650:00 | R-UNK | UNK | - | ZZ | - |
| 1982-C01 | 1982 Apr 19 1945:00 | R-UNK | UNK | - | ZZ | - |
| 1984-A47 | 1984 Jun 26 1243:06 | Space Shuttle | KSC | LC39A | OA | Abort, no launch |
| 1985-A26 | 1985 Jul 12 2030:00 | Space Shuttle | KSC | LC39A | OA | Abort, no launch |
| 1986-C01 | 1986 Feb 19 2128:23 | R-UNK | UNK | - | ZZ | - |
| 1993-A20 | 1993 Mar 22 1450:57 | Space Shuttle | KSC | LC39A | OA | - |
| 1993-A21 | 1993 Aug 12 1312:32 | Space Shuttle | KSC | LC39B | OA | Abort, no launch |
| 1994-A08 | 1994 Aug 18 1053:58 | Space Shuttle | KSC | LC39A | OA | Abort, no launch |
| 1998-C01 | 1998 Nov 20 0640 | R-UNK | UNK | - | ZZ | - |
| 2014-000 | 2014 Jan  1 | R-UNK | UNK | - | ZZ | - |
| 2021-C01 | 2021 Apr 29 0523 | R-UNK | UNK | - | ZZ | - |

**Entries that hold the word scrub in any field: 2.**

- 1966-F12, 1966 Dec 14 1100, Soyuz 11A511: in Notes: `Scrub, escape sys fired, explode`
- 1973-E01, 1973 Jun 26 0122, Kosmos 11K65M: in Notes: `Prop leak after scrub`

**Falcon 9 from Vandenberg in 2024.** 46 entries, all from pad(s) SLC4E; 35 of them timed to the second and not marked uncertain.

<!-- d1b:catalogue:end -->

## 5. The numbers

**As fixed beforehand**, by [firstlook.py](d1/firstlook.py):

<!-- d1b:firstlook:begin -->

T0 is 2021-09-14 03:55:50 UTC. A cell reads: the median ratio over the window; the up seconds of the window's seconds; the longest counting stretch that begins in it.

**The sound window, vertical channel, 2 to 8 Hz.**

| station | km | window, s after T0 | the day before | launch day | the day after | reading |
|---|---|---|---|---|---|---|
| CI.GATR | 13.5 | 34 to 242 | no record | no record | no record | NO RECORD: the data centre answered 404 |
| CI.LOC | 16.5 | 42 to 254 | 1.47; 15 of 212; none | 614.02; 209 of 212; 454 up from 45 s to 502 s | 0.72; 1 of 212; none | SEEN |
| CI.LCP | 32.6 | 89 to 321 | 0.56; 17 of 232; none | 440.16; 223 of 232; 412 up from 100 s to 511 s | 1.49; 36 of 232; 10 up from 192 s to 202 s | CANNOT TELL |
| CI.SYN | 49.9 | 139 to 393 | 0.89; 1 of 254; none | 88.08; 182 of 254; 270 up from 211 s to 481 s | 0.80; 4 of 254; none | SEEN |
| CI.MPP | 78.5 | 222 to 513 | 0.79; 0 of 291; none | 843.99; 289 of 291; 351 up from 224 s to 574 s | 1.43; 16 of 291; none | SEEN |
| CI.CDM | 120.4 | 343 to 687 | 1.03; 21 of 344; 20 up from 471 s to 490 s | 1.65; 86 of 344; 62 up from 471 s to 532 s | 1.05; 0 of 344; none | CANNOT TELL |
| CI.HDH | 181.4 | 520 to 941 | 1.41; 40 of 421; 11 up from 615 s to 625 s | 0.95; 49 of 421; none | 1.08; 55 of 421; 21 up from 864 s to 885 s | NOTHING VISIBLE |
| CI.SRN | 275.0 | 792 to 1331 | 0.74; 0 of 539; none | 0.94; 2 of 539; none | 1.13; 56 of 539; 45 up from 1329 s to 1375 s | NOTHING VISIBLE |

**The ground window, vertical channel, 2 to 8 Hz.**

| station | km | window, s after T0 | the day before | launch day | the day after | reading |
|---|---|---|---|---|---|---|
| CI.GATR | 13.5 | -3 to 194 | no record | no record | no record | NO RECORD: the data centre answered 404 |
| CI.LOC | 16.5 | -3 to 196 | 1.17; 6 of 199; none | 523.16; 151 of 199; 454 up from 45 s to 502 s | 0.82; 1 of 199; none | SEEN |
| CI.LCP | 32.6 | 0 to 207 | 0.67; 22 of 207; none | 5.14; 117 of 207; 412 up from 100 s to 511 s | 1.90; 52 of 207; 14 up from 61 s to 74 s | CANNOT TELL |
| CI.SYN | 49.9 | 2 to 219 | 1.19; 10 of 217; none | 1.08; 18 of 217; 270 up from 211 s to 481 s | 0.88; 3 of 217; none | SEEN |
| CI.MPP | 78.5 | 7 to 238 | 0.97; 0 of 231; none | 4.10; 146 of 231; 351 up from 224 s to 574 s | 1.35; 4 of 231; none | SEEN |
| CI.CDM | 120.4 | 13 to 266 | 0.92; 4 of 253; none | 1.16; 0 of 253; none | 1.03; 0 of 253; none | NOTHING VISIBLE |
| CI.HDH | 181.4 | 22 to 306 | 3.28; 150 of 284; 56 up from 191 s to 249 s | 0.51; 1 of 284; none | 2.55; 117 of 284; 56 up from 218 s to 275 s | NOTHING VISIBLE |
| CI.SRN | 275.0 | 37 to 369 | 0.94; 0 of 332; none | 0.97; 0 of 332; none | 0.83; 2 of 332; none | NOTHING VISIBLE |

**Onsets, vertical channel, 2 to 8 Hz.** The first counting stretch that begins between the ground window's opening and the sound window's close.

| station | km | day | onset, s after T0 | last up second | up seconds | km / onset, km/s | in the sound window | in the ground window |
|---|---|---|---|---|---|---|---|---|
| CI.LOC | 16.5 | control, the day before | none | - | - | - | - | - |
| CI.LOC | 16.5 | launch day | 45 | 502 | 454 | 0.367 | yes | yes |
| CI.LOC | 16.5 | control, the day after | none | - | - | - | - | - |
| CI.LCP | 32.6 | control, the day before | none | - | - | - | - | - |
| CI.LCP | 32.6 | launch day | 100 | 511 | 412 | 0.326 | yes | yes |
| CI.LCP | 32.6 | control, the day after | 61 | 74 | 14 | 0.534 | no | yes |
| CI.SYN | 49.9 | control, the day before | none | - | - | - | - | - |
| CI.SYN | 49.9 | launch day | 211 | 481 | 270 | 0.236 | yes | yes |
| CI.SYN | 49.9 | control, the day after | none | - | - | - | - | - |
| CI.MPP | 78.5 | control, the day before | none | - | - | - | - | - |
| CI.MPP | 78.5 | launch day | 26 | 75 | 47 | 3.019 | no | yes |
| CI.MPP | 78.5 | control, the day after | none | - | - | - | - | - |
| CI.CDM | 120.4 | control, the day before | 471 | 490 | 20 | 0.256 | yes | no |
| CI.CDM | 120.4 | launch day | 471 | 532 | 62 | 0.256 | yes | no |
| CI.CDM | 120.4 | control, the day after | none | - | - | - | - | - |
| CI.HDH | 181.4 | control, the day before | 175 | 186 | 12 | 1.037 | no | yes |
| CI.HDH | 181.4 | launch day | none | - | - | - | - | - |
| CI.HDH | 181.4 | control, the day after | 181 | 198 | 17 | 1.002 | no | yes |
| CI.SRN | 275.0 | control, the day before | none | - | - | - | - | - |
| CI.SRN | 275.0 | launch day | none | - | - | - | - | - |
| CI.SRN | 275.0 | control, the day after | 1265 | 1276 | 10 | 0.217 | yes | no |

Slope of onset against distance over the 3 stations read as SEEN (CI.LOC, CI.SYN, CI.MPP): -0.16 s per km, intercept 102 s, largest residual 117 s. Sound is 2.90 to 4.17 s per km, the ground 0.15 to 0.67.

**Every band, the sound window, vertical channel.** A cell reads as above.

| station | km | band | the day before | launch day | the day after |
|---|---|---|---|---|---|
| CI.LOC | 16.5 | 0.5 to 2 Hz | 0.86; 13 of 212; none | 1.91; 49 of 212; none | 0.88; 9 of 212; none |
| CI.LOC | 16.5 | 2 to 8 Hz | 1.47; 15 of 212; none | 614.02; 209 of 212; 454 up from 45 s to 502 s | 0.72; 1 of 212; none |
| CI.LOC | 16.5 | 8 to 20 Hz | 2.29; 91 of 212; 29 up from 229 s to 260 s | 70.39; 207 of 212; 270 up from 47 s to 317 s | 0.43; 21 of 212; none |
| CI.LOC | 16.5 | 20 to 45 Hz | 1.97; 67 of 212; 21 up from 57 s to 77 s | 76.11; 206 of 212; 269 up from 48 s to 316 s | 0.64; 22 of 212; 11 up from 176 s to 187 s |
| CI.LCP | 32.6 | 0.5 to 2 Hz | 0.95; 15 of 232; none | 1.26; 36 of 232; 10 up from 182 s to 192 s | 1.34; 38 of 232; none |
| CI.LCP | 32.6 | 2 to 8 Hz | 0.56; 17 of 232; none | 440.16; 223 of 232; 412 up from 100 s to 511 s | 1.49; 36 of 232; 10 up from 192 s to 202 s |
| CI.LCP | 32.6 | 8 to 20 Hz | 0.88; 17 of 232; none | 46.85; 182 of 232; 244 up from 141 s to 385 s | 1.17; 2 of 232; none |
| CI.LCP | 32.6 | 20 to 45 Hz | 0.82; 22 of 232; none | 1.13; 29 of 232; 29 up from 249 s to 277 s | 1.02; 0 of 232; none |
| CI.SYN | 49.9 | 0.5 to 2 Hz | 0.91; 34 of 254; none | 1.18; 24 of 254; none | 1.09; 38 of 254; none |
| CI.SYN | 49.9 | 2 to 8 Hz | 0.89; 1 of 254; none | 88.08; 182 of 254; 270 up from 211 s to 481 s | 0.80; 4 of 254; none |
| CI.SYN | 49.9 | 8 to 20 Hz | 0.72; 115 of 254; none | 182.94; 218 of 254; 307 up from 176 s to 482 s | 1.17; 8 of 254; none |
| CI.SYN | 49.9 | 20 to 45 Hz | 2.76; 126 of 254; none | 35.20; 232 of 254; 235 up from 157 s to 395 s | 1.02; 0 of 254; none |
| CI.MPP | 78.5 | 0.5 to 2 Hz | 1.18; 40 of 291; none | 0.85; 18 of 291; none | 1.17; 38 of 291; 13 up from 249 s to 262 s |
| CI.MPP | 78.5 | 2 to 8 Hz | 0.79; 0 of 291; none | 843.99; 289 of 291; 351 up from 224 s to 574 s | 1.43; 16 of 291; none |
| CI.MPP | 78.5 | 8 to 20 Hz | 0.95; 0 of 291; none | 5.34; 218 of 291; 202 up from 338 s to 540 s | 1.03; 0 of 291; none |
| CI.MPP | 78.5 | 20 to 45 Hz | 0.75; 1 of 291; none | 159.76; 273 of 291; 325 up from 240 s to 564 s | 4.72; 204 of 291; 194 up from 298 s to 492 s |
| CI.CDM | 120.4 | 0.5 to 2 Hz | 1.08; 23 of 344; none | 0.93; 22 of 344; none | 0.75; 23 of 344; 10 up from 396 s to 406 s |
| CI.CDM | 120.4 | 2 to 8 Hz | 1.03; 21 of 344; 20 up from 471 s to 490 s | 1.65; 86 of 344; 62 up from 471 s to 532 s | 1.05; 0 of 344; none |
| CI.CDM | 120.4 | 8 to 20 Hz | 0.89; 27 of 344; 22 up from 469 s to 490 s | 1.14; 52 of 344; 50 up from 475 s to 524 s | 1.28; 12 of 344; none |
| CI.CDM | 120.4 | 20 to 45 Hz | 1.17; 16 of 344; 12 up from 469 s to 480 s | 0.78; 58 of 344; 52 up from 475 s to 526 s | 0.91; 0 of 344; none |
| CI.HDH | 181.4 | 0.5 to 2 Hz | 0.92; 48 of 421; none | 1.29; 78 of 421; 12 up from 886 s to 897 s | 1.70; 106 of 421; 19 up from 674 s to 695 s |
| CI.HDH | 181.4 | 2 to 8 Hz | 1.41; 40 of 421; 11 up from 615 s to 625 s | 0.95; 49 of 421; none | 1.08; 55 of 421; 21 up from 864 s to 885 s |
| CI.HDH | 181.4 | 8 to 20 Hz | 1.45; 114 of 421; 68 up from 576 s to 644 s | 1.87; 149 of 421; 81 up from 744 s to 825 s | 0.81; 104 of 421; 106 up from 836 s to 942 s |
| CI.HDH | 181.4 | 20 to 45 Hz | 1.29; 44 of 421; 11 up from 706 s to 716 s | 0.78; 34 of 421; 14 up from 802 s to 816 s | 0.49; 5 of 421; none |
| CI.SRN | 275.0 | 0.5 to 2 Hz | 0.99; 41 of 539; none | 0.92; 18 of 539; none | 0.94; 20 of 539; none |
| CI.SRN | 275.0 | 2 to 8 Hz | 0.74; 0 of 539; none | 0.94; 2 of 539; none | 1.13; 56 of 539; 45 up from 1329 s to 1375 s |
| CI.SRN | 275.0 | 8 to 20 Hz | 0.97; 0 of 539; none | 1.01; 0 of 539; none | 1.15; 0 of 539; none |
| CI.SRN | 275.0 | 20 to 45 Hz | 1.04; 19 of 539; none | 1.13; 21 of 539; 12 up from 1292 s to 1303 s | 0.97; 8 of 539; none |

**The horizontal channels on launch day, the sound window, 2 to 8 Hz.**

| station | km | HHZ | HHE | HHN |
|---|---|---|---|---|
| CI.LCP | 32.6 | 440.16; 223 of 232; 412 up from 100 s to 511 s | 379.43; 220 of 232; 408 up from 102 s to 510 s | 497.10; 205 of 232; 377 up from 134 s to 511 s |
| CI.SYN | 49.9 | 88.08; 182 of 254; 270 up from 211 s to 481 s | 38.34; 192 of 254; 274 up from 205 s to 479 s | 51.96; 190 of 254; 270 up from 212 s to 481 s |

**The whole 50 minutes, vertical channel, 2 to 8 Hz.** Every counting stretch, wherever it begins, and the frames left out for a missing sample.

| station | day | counting stretches: up seconds (from s to s after T0) | frames left out |
|---|---|---|---|
| CI.LOC | control, the day before | none | 0 |
| CI.LOC | launch day | 454 (45 to 502); 13 (603 to 615); 14 (619 to 632); 10 (853 to 863); 20 (875 to 895) | 0 |
| CI.LOC | control, the day after | 70 (442 to 511) | 0 |
| CI.LCP | control, the day before | 43 (-281 to -238); 17 (-222 to -206); 47 (-203 to -156); 15 (-7 to 7); 39 (406 to 445); 13 (535 to 547); 11 (640 to 650); 14 (705 to 718); 10 (724 to 733); 18 (977 to 996); 12 (1192 to 1203); 18 (1235 to 1253); 11 (1299 to 1310); 22 (1542 to 1563); 20 (1566 to 1585); 30 (1855 to 1884) | 0 |
| CI.LCP | launch day | 43 (-948 to -906); 10 (-903 to -894); 44 (-890 to -844); 48 (-841 to -793); 33 (-786 to -754); 30 (-750 to -716); 31 (-625 to -594); 412 (100 to 511); 47 (518 to 567); 15 (591 to 606); 26 (612 to 638); 15 (642 to 656); 36 (743 to 778); 14 (864 to 877); 27 (1021 to 1047); 82 (1271 to 1354); 24 (1357 to 1381); 30 (1487 to 1517); 25 (1574 to 1598); 11 (1660 to 1672); 119 (1686 to 1808); 25 (1989 to 2013); 15 (2033 to 2047) | 0 |
| CI.LCP | control, the day after | 13 (-947 to -935); 35 (-932 to -895); 100 (-750 to -649); 14 (61 to 74); 10 (192 to 202); 49 (776 to 825); 47 (839 to 886); 11 (890 to 900); 20 (1031 to 1051); 47 (1061 to 1107); 15 (1305 to 1320); 17 (1324 to 1340); 65 (1345 to 1410); 17 (1413 to 1430); 63 (1942 to 2005); 13 (2013 to 2025); 10 (2028 to 2037) | 0 |
| CI.SYN | control, the day before | 18 (879 to 898); 17 (1100 to 1116); 10 (1261 to 1271); 11 (1965 to 1976) | 0 |
| CI.SYN | launch day | 270 (211 to 481); 10 (880 to 889); 20 (918 to 937); 10 (1347 to 1358) | 0 |
| CI.SYN | control, the day after | 11 (-670 to -659) | 0 |
| CI.MPP | control, the day before | none | 0 |
| CI.MPP | launch day | 47 (26 to 75); 15 (88 to 103); 52 (167 to 221); 351 (224 to 574); 12 (656 to 668); 12 (672 to 683) | 0 |
| CI.MPP | control, the day after | none | 0 |
| CI.CDM | control, the day before | 20 (471 to 490); 16 (1840 to 1856) | 0 |
| CI.CDM | launch day | 62 (471 to 532); 13 (587 to 601); 12 (1839 to 1850) | 0 |
| CI.CDM | control, the day after | 12 (1484 to 1495) | 0 |
| CI.HDH | control, the day before | 10 (-892 to -882); 10 (-360 to -351); 69 (-1 to 69); 12 (175 to 186); 56 (191 to 249); 13 (252 to 265); 11 (615 to 625); 24 (1130 to 1154); 23 (1352 to 1376) | 0 |
| CI.HDH | launch day | 32 (-525 to -491); 12 (-488 to -476); 21 (1153 to 1174); 13 (1182 to 1194); 44 (1352 to 1396); 25 (2014 to 2038) | 0 |
| CI.HDH | control, the day after | 11 (-358 to -347); 14 (-333 to -320); 17 (181 to 198); 56 (218 to 275); 13 (378 to 391); 24 (400 to 423); 21 (864 to 885); 47 (1280 to 1327) | 0 |
| CI.SRN | control, the day before | none | 0 |
| CI.SRN | launch day | 10 (1586 to 1598) | 0 |
| CI.SRN | control, the day after | 10 (1265 to 1276); 13 (1280 to 1292); 30 (1296 to 1326); 45 (1329 to 1375); 13 (1383 to 1398) | 0 |

<!-- d1b:firstlook:end -->

**Chosen after looking**, by [secondlook.py](d1/secondlook.py). These describe what the tables above showed. They were not fixed first and are not tests.

<!-- d1b:secondlook:begin -->

**A. The first counting stretch that begins inside the sound window, launch day, vertical channel.** Chosen after looking. A cell reads: onset in seconds after T0, the last up second, and km over onset in km/s.

| station | km | 0.5 to 2 Hz | 2 to 8 Hz | 8 to 20 Hz | 20 to 45 Hz |
|---|---|---|---|---|---|
| CI.LOC | 16.5 | none | 45; 502; 0.367 | 47; 317; 0.351 | 48; 316; 0.344 |
| CI.LCP | 32.6 | 182; 192; 0.179 | 100; 511; 0.326 | 141; 385; 0.231 | 249; 277; 0.131 |
| CI.SYN | 49.9 | none | 211; 481; 0.236 | 176; 482; 0.284 | 157; 395; 0.318 |
| CI.MPP | 78.5 | none | 224; 574; 0.350 | 320; 334; 0.245 | 240; 564; 0.327 |
| CI.CDM | 120.4 | none | 471; 532; 0.256 | 475; 524; 0.253 | 475; 526; 0.253 |
| CI.HDH | 181.4 | 593; 604; 0.306 | none | 652; 663; 0.278 | 802; 816; 0.226 |
| CI.SRN | 275.0 | none | none | none | 1292; 1303; 0.213 |

- Slope of that onset against distance, 2 to 8 Hz, over every station with such a stretch (CI.LOC, CI.LCP, CI.SYN, CI.MPP, CI.CDM): 3.89 s per km, which is 0.257 km/s; intercept -22 s; residuals +2, -5, +38, -60, +24 s.
- Slope of that onset against distance, 2 to 8 Hz, over the same without CI.CDM, whose stretch a control day also has (CI.LOC, CI.LCP, CI.SYN, CI.MPP): 3.02 s per km, which is 0.331 km/s; intercept 11 s; residuals -16, -9, +49, -24 s.

**B. The launch day's median ratio over the sound window against the larger control day's, 2 to 8 Hz, vertical channel.** Chosen after looking.

| station | km | launch day | larger control day | launch over control |
|---|---|---|---|---|
| CI.LOC | 16.5 | 614.02 | 1.47 | 417.0 |
| CI.LCP | 32.6 | 440.16 | 1.49 | 295.2 |
| CI.SYN | 49.9 | 88.08 | 0.89 | 98.8 |
| CI.MPP | 78.5 | 843.99 | 1.43 | 591.8 |
| CI.CDM | 120.4 | 1.65 | 1.05 | 1.6 |
| CI.HDH | 181.4 | 0.95 | 1.41 | 0.7 |
| CI.SRN | 275.0 | 0.94 | 1.13 | 0.8 |

**C. Before the sound window opens: from T0 to the sound window's opening, 2 to 8 Hz, vertical channel.** Chosen after looking, because CI.MPP showed a stretch there. A cell reads: the median ratio; the up seconds of the seconds.

| station | km | seconds after T0 | the day before | launch day | the day after |
|---|---|---|---|---|---|
| CI.LOC | 16.5 | 0 to 42 | 0.92; 1 of 42 | 1.07; 0 of 42 | 1.05; 0 of 42 |
| CI.LCP | 32.6 | 0 to 89 | 0.59; 8 of 89 | 1.46; 8 of 89 | 1.61; 25 of 89 |
| CI.SYN | 49.9 | 0 to 139 | 1.31; 10 of 139 | 1.10; 11 of 139 | 1.20; 3 of 139 |
| CI.MPP | 78.5 | 0 to 222 | 0.96; 0 of 222 | 3.64; 132 of 222 | 1.35; 4 of 222 |
| CI.CDM | 120.4 | 0 to 343 | 0.91; 4 of 343 | 1.14; 0 of 343 | 1.04; 0 of 343 |
| CI.HDH | 181.4 | 0 to 520 | 1.54; 172 of 520 | 0.54; 6 of 520 | 2.09; 167 of 520 |
| CI.SRN | 275.0 | 0 to 792 | 0.99; 0 of 792 | 0.98; 2 of 792 | 0.83; 2 of 792 |

<!-- d1b:secondlook:end -->

## 6. The figures

Two, each drawn by [figs.py](d1/figs.py) from the fetched files (`<venv> docs/studies/d1/figs.py <data> docs/studies/d1/fig`). A figure is something to look at; every claim above rests on a number.

- [d1b-ladder.png](d1/fig/d1b-ladder.png): for each of the seven stations with a record, the ratio in the 2 to 8 Hz band against seconds after T0, on the three days, with the two predicted windows shaded. The curves are firstlook.py's numbers (rows Q1a to Q3a).
- [d1b-spectrograms.png](d1/fig/d1b-spectrograms.png): for CI.LOC and CI.MPP, power by frequency and time on the launch day and on the day before, each frequency over its own pre-launch median (row Q4b).

## 7. What this changes in D1

Each row named here is restated in D1, and D1's section Changes after the first look lists the same.

| D1 row | it said | the look found | now |
|---|---|---|---|
| L4 | 46 Falcon 9 launches from Vandenberg in 2024, BELIEVED from a search summary | the catalogue lists 46 (Q6f) | MEASURED |
| W6 | the launch was at about 03:56 UTC, BELIEVED from a local time and a remembered offset | the catalogue gives 03:55:50 UTC (Q6a) | MEASURED |
| W3 | the source radiates for 180 s, an ESTIMATE | the signal lasts 270 to 454 s and outlasts every window (Q4a) | the estimate is marked as too short; the windows' close is not yet re-drawn |
| M6 | digitisers are 24 bits or wider, BELIEVED | two records hold samples that need 17 bits (Q5c). The converter's width is still not read | split: samples wider than 16 bits is MEASURED; the converter's width stays BELIEVED |
| M9 | wording that read as nine stations | eight | wording |
| E1 | 512-byte records of 112 samples, BELIEVED | 4096-byte records, Steim-1 (Q5a) | wrong; restated as MEASURED |
| E2 | 2 bytes a sample, BELIEVED | 1.09 to 2.18, mean 1.44 (Q5e) | MEASURED |
| E3 | 300 bytes an entry of the launch list, an ESTIMATE | 182 (R1) | wrong; restated as MEASURED |
| E4, E5 | a request is 0.69 MB typically; 30 requests about 20.6 MB | a file is 0.33 to 0.66 MB; the 25 that came are 10.8 MB | MEASURED |
| E6 | the launch list is about 22.8 MB | 13.8 MB | MEASURED |

**Not restated, and worth the lead's eye.**

- D1's rows T3 and T4 disagree on whether the 100-sample channels are archived continuously. For seven of these eight stations, for these three hours, they are (Q5a). For the eighth nothing came (Q1b).
- D1's row W1 takes 0.345 km/s as the fastest sound. One onset reads faster, within what a 4-second frame can tell (Q3d). The row is left as it is.
- D1's control 3 warns that a model can learn the hour. CI.CDM is a case: the same second on two days (Q2c).
- The plan's row V2, that launch signals can be seen in public seismic records at a predictable lag at more than one distance, is BELIEVED there. For this one launch a signal is there at three distances by the rule and four by the numbers (Q2a, Q2b). On the lag the look is weaker than that: the slope fixed beforehand is meaningless (Q3a), and the one that is inside the range for sound was chosen after looking and fits loosely (Q3b). One launch does not make it a rate.

## 8. D1's controls: which this look ran, and which it could not

| control | on this download |
|---|---|
| 1, arrival time | The slope fixed beforehand was taken and is meaningless (Q3a). The slope chosen after looking is inside the range for sound, with a misfit that is given beside it (Q3b); because it was chosen after, it is a description and not a test. The wrong-window comparison was not run |
| 2, a signal in every record | **Not run.** With one launch window and two control windows at a station its test, Fisher's exact at 0.01, cannot reject whatever the records hold. It is reported as not run, not as passed |
| 3, the hour | Not run as designed; one case of what it is for turned up (Q2c) |
| 6, strength | **Not run.** It needs CI.GATR and CI.LOC together, and CI.GATR has no record (Q1b) |
| 7, other things in the window | The earthquake listing and the launch list were read for all three windows (Q6d, Q6g). Distant earthquakes were not |
| 9, selection | Every station asked for is reported, with or without a signal, and the launch is a selected one, as D1 said |
| 4, 5, 8, 10 to 14 | Not run: each needs more than one launch, or a detector |

## 9. Limits, and what was not done

- **One launch, and a selected one.** The network had written it up. That it shows here says a signal can be there, not how often.
- **Two control days, one of them not clean** (Q6d). No statement here is a rate.
- **The rule fixed beforehand is crude.** A ten-second stretch on a control day outweighs a seven-minute one on the launch day (Q2b). It was applied as written. D1's section 7 sets thresholds from control windows instead; this look did not.
- **Ratios, not amplitudes.** Every number is power over that station's own noise in raw counts. How strength falls with distance in physical units was not measured: it needs each sensor's response, which D1's row M9 has only in part.
- **The onset is the 2 to 8 Hz band's.** At CI.SYN the higher bands begin earlier (table A of section 5).
- **What the early power at CI.MPP is** (Q3e) is not established.
- **Why CI.GATR has no record** was not asked.
- **Distant earthquakes** were not checked: the national catalogue's terms page would not open, so it was not queried.
- **No detector was run.** Nothing here touches D0's reference model.

**What a wider look would be**, for the lead and the owner to decide; none of it was done:

1. CI.GATR's other channels (40 samples a second, and its accelerometer) for the same hours, and NC.PTQ, 6.7 km from the pad in 2021, from the Berkeley data centre.
2. More control days for these seven stations at this hour, chosen by D1's rule, to turn two into a count.
3. A second launch, chosen by rule from the catalogue's 46 of 2024 (Q6f), with every definition fixed first, the onset's among them.
4. The stations with an infrasound channel beside the seismometer: one near Vandenberg, five in Florida (D1's rows M3 and M10).

## Changes after the verifier's third pass, 2026-11-23

The verifier confirmed the headline by a measure of its own and found the tables as committed. It also found three sentences that said more than the numbers, and five smaller things.

| finding | what was wrong | what was done |
|---|---|---|
| 1. The band | the summary said it is mostly in the 2 to 8 Hz band; the figures are ratios to each band's own noise | the summary now says what row Q4b says |
| 2. Row R4 | it said nothing in the package index's terms limits who may download; the terms bar a person on a named sanctions list | restated to the page, with the sentence quoted and placed. The install had already been made on the wrong reading; that is said in the row and went to the lead |
| 3. The slope chosen after looking | section 7's sentence on the plan's row V2 leaned on it without saying so | every place that gives 3.02 s per km, or leans on it, now says it was chosen after looking: the summary twice, Q3b, Q3c, section 7, section 8, and D1's confirmation list. The summary's first line no longer says the signal comes when sound would: it says inside the windows predicted beforehand, which at the nearest station overlap. D1's opening no longer cites Q3b for whether a launch is seen |
| 4. 454 seconds | it is 454 up seconds in a stretch from 45 s to 502 s | the summary says so |
| 5. Fits sound | residuals reach 49 s, and one station-to-station step is 0.45 s per km | the misfit and the three steps are beside the slope wherever it appears |
| 6. Type ex | not read | row Q6h is new: the code is the data centre's for an explosion, by the menu of its own service page. One further page was read for a definition and does not hold one |
| 7. The earthquake inside CI.SRN's day-after stretch | not linked | row Q2e is new: the stretch begins 16 s before the earthquake, so it did not begin it; what did is not established, and the row says what would settle it |
| 8. CI.HDH | not visible could be read as quiet | row Q2d is new, and the summary says so: both control days were busier than the launch day there |

## The lead's eight smaller findings on part A, answered

| finding | answer |
|---|---|
| 1. A frame with a missing sample: does its second count as not up? | D1's section 7 now says: such a second is neither; it ends a stretch at once, and it is left out of a window's count of seconds. firstlook.py does this, and its self-test has the case. None occurred here |
| 2. T0 known only to the minute | D1's section 7 now says T0 is the catalogue's time and must be to the second and unmarked; a launch timed more coarsely is left out of a scored experiment. Here it is 03:55:50 UTC (Q6a). Of 2024's 46 from this pad, 35 qualify (Q6f) |
| 3. The false-alarm fraction thresholds are set to | D1's section 7 now proposes 0.05 a control window, with what that costs in control windows (its row H1) |
| 4. Control 2 can never reject on one launch | Said in section 8 above, and reported as not run |
| 5. Control 6 has no number | D1's control 6 now has one, and says how many launches it needs. It could not be run here |
| 6. A gain of 419,430 fits 24 bits over 40 V, and also 22 over 10 V, 21 over 5 V, 20 over 2.5 V | Conceded and stated in D1's rows M6 and M9. The records settle D0's question and not the converter's width: samples needing 17 bits are in two files (Q5c) |
| 7. Row M9 read as nine stations | Reworded: eight |
| 8. PROVENANCE.md's count of availability requests | Brought up to date, with every other count |

## Changes after the experiment, 2026-11-23

The lead's, from [study D2](D2-launch-experiment.md). Nothing above is edited.

- **This look was one launch, and said so.** There are now 23 scored launches at the three nearest stations that have records throughout 2024: 66 of their 69 launch windows hit, and none of 204 control windows. All three are within 50 km of the pad, where D2's own first limit applies: the launch is loud there, not faint.
- **Row Q1b, CI.GATR's missing record in 2021**: it was missing through most of 2024 as well. D2 has a record of it for no window asked before 2024-11-14.

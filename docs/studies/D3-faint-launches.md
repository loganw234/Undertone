# D3: the faint launches - are launches seen at stations 78 to 275 km from the pad more often than control windows?

Written by the parcel LCH-4 on 2026-11-24, for round 3 ([the plan](../plans/R3-first-light.md), row LCH-4 and row W4). It is the experiment [study D2](D2-launch-experiment.md)'s section 14, item 1, names, on [D1](D1-launch-data.md)'s ladder and [D1b](D1b-first-look.md)'s farther stations.

**The headline. By a rule frozen before any scored record was opened, the scored launches were seen more often than control windows at each of the four stations 78.5 to 275 km from the pad: at CI.MPP (78.5 km) 23 of 23 launch windows hit against 4 of 68 control windows; at CI.CDM (120.4 km) 20 of 23 against 2 of 67; at CI.HDH (181.4 km) 14 of 23 against 5 of 68; and at CI.SRN (275.0 km) 13 of 23 against 7 of 68.** Fisher's exact test, one-sided, at 0.01 shared over the four stations, 0.0025 at each: the four p values run from 1.84e-05 to 8.32e-18 (rows F10, F11). Neither control on the same records rejected at any station, at 0.01 undivided; the nearest, CI.SRN's wrong window, hit 7 of 23 times for p = 0.0282 (row F12). **What it does not show.** A hit is seconds of power in one band of one channel; that a launch made it rests on the control windows and the two controls, not on anything the rule knows about rockets. The launches are Falcon 9 launches of 2024 from one pad, D2's 35, of which 23 are scored. "Faint" here means far: at CI.MPP a launch window's longest run of up seconds was 126 to 339 of its 541 seconds, and nothing here measures strength in physical units. At CI.HDH and CI.SRN 14 and 13 of the 23 launches hit, and, by a description made after looking, at CI.HDH 12 of the 12 scored launches of November to March hit and 2 of the 11 of April to October (row F14); a "yes" there is a rate over the year, not a promise for any one launch. **Nothing here is evidence about the detector, the model or the fabric:** no detector was run, and this touches none of [D0](D0-rough-design.md)'s gates. It is about whether this data source can label events far from the pad at all. **What the experiment's choices knew.** The stations, the rule, the windows and the split were fixed with D1b's 2021 records and D2's committed near-station output in hand, and no record of these stations in 2024; one constant a station was then set from twelve launches of 2024 that are not scored. **Data:** waveforms and station metadata from the Southern California Earthquake Data Center, SCEDC (2013), doi:10.7909/C3WD3xH1, of the Southern California Seismic Network, doi:10.7914/SN/CI; launch times from GCAT (J. McDowell, planet4589.org/space/gcat), under CC-BY. The acknowledgement is in full at the end.

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. `<data>` is this parcel's data folder in the round's run folder, outside the repository; nothing in it is committed. `<scratch>` is its scratch folder there. `<catalogue>` is the folder that holds the launch list D1b fetched on 2026-11-23. `<ledger>` is the round's ledger, `Data/runs/2026-11-24-r3/ledger`, which is not committed. Times of day are local, seven hours behind UTC. Every figure is in the register at the end.

## 1. The question, and the three walls

**By a rule fixed before any record of them is fetched, are launches seen at the stations 78 to 275 km from the pad more often than control windows are?** That is the plan's row W4, BELIEVED there. The danger is a rule tuned on the launches it then scores, and one D2 did not have: D2's rule and its scored output for the near stations are in the tree. Three walls stand against it (row F1):

| wall | what | when, 2026-11-24 |
|---|---|---|
| 1. The split before any fetch | the stations, the launches, the split, the windows, the control times, the hit rule, the test and its level, written in the round's ledger and approved by the lead | written 09:27, approved 09:29; the first data request was at 09:32:48 |
| 2. The rule frozen before a scored record is opened | [d3rule.py](d3/d3rule.py), [d3score.py](d3/d3score.py), [constants.json](d3/constants.json), [launches.tsv](d3/launches.tsv), [manifest.tsv](d3/manifest.tsv) and D1's [firstlook.py](d1/firstlook.py) and [mseed.py](d1/mseed.py), committed at 09:44:51 as `db4bef1`; the SHA-256 of their seven hashes, the freeze hash, written in the ledger and recomputed by the lead | allowed 09:48 |
| 3. Scored once | one run of d3score.py, 09:49:43 to 09:51:01; its output, [scored-output.txt](d3/scored-output.txt), is kept as written and committed at 09:51:47 as `4a3f3b9`, and the script refuses to run while that file exists | once |

The freeze hash is `645d1e84d9e78a1ad3a987e767b38b885e1fe5e0553d3b31bd212ff33baafe59`. `python docs/studies/d3/d3score.py --freeze-hash` prints the seven lines it is the hash of; it is the hash the scoring run printed on its own second line, and [tests/test_lch4_freeze.py](../../tests/test_lch4_freeze.py) holds the seven files to it and the output to its own SHA-256 (row F2).

**Every constant, and where it comes from** (the brief asked this of each):

| constant | value | where it comes from |
|---|---|---|
| band | 2 to 8 Hz of HHZ | D1, section 8, fixed before any record; D2's; unchanged |
| frame, hop, taper | 400 samples, 100, Hann | D1; unchanged |
| noise | the median over frames centred 660 to 60 s before T | D1; unchanged |
| up | a ratio above 3; exactly 3 is not | D1; unchanged |
| a run's tolerance | one not-up second | D1, section 7, step 2; D2's; unchanged |
| the statistic | S, the up seconds of the longest run inside the window | D2's, chosen with the 2021 records in hand and before any 2024 record; unchanged |
| M, one a station | 23, 33, 58, 28 | set here by D2's rule from this study's twelve constant-setting launches at these stations |
| M's floor; least windows to set it | 10; 4 launch and 8 control | D1's minimum; D2's; unchanged |
| least noise frames; usable share | 300 of 601; 90% | D2's; unchanged |
| the window's open | d / 0.345 - 5 s | D1, row W1; unchanged |
| the window's close | d / 0.240 + 430 + 5 s | redrawn here, by a rule from D1b's row Q4a (section 3) |
| distances | 78.5, 120.4, 181.4, 275.0 km | D1, row M4; unchanged |
| wrong window's gap; the shift | 60 s; 3600 s | D2's; unchanged |
| control times | three a launch, whole weeks, 24 h clear, 2 h apart, 2023-12-01 to 2025-02-01 | D2's; unchanged |
| control times on the local clock | new | closes D2's limit 8 (section 4) |
| the split | launch n sets constants when n mod 3 = 1 | new (section 2) |
| the level; the controls' level; enough to say NOT SHOWN | 0.01 over four, 0.0025 each; 0.01 undivided; 15 | D2's; unchanged |

Nothing in that table was chosen from D2's near-station numbers.

## 2. The launches and the split

**The launches are D2's 35** (row F3): from GCAT's launch list as D1b fetched it, checked by its SHA-256, every entry with vehicle Falcon 9, a Vandenberg site code, a date in 2024 UTC, and a time written to the second and not marked uncertain. [d3launches.py](d3/d3launches.py) makes the list and refuses any other file. The catalogue was not asked again.

**The split is new: numbered 1 to 35 in time order, launch n sets constants when n mod 3 = 1, and is scored otherwise.** That is 12 and 23, the counts D2 had, so D2's arithmetic of what the test could show carries. D2 split by date, January to April setting and May to December scored. The reason not to: sound that reaches stations this far travels in ducts of the upper air whose winds turn round with the season (BELIEVED, from memory; no source was read), and the four stations lie east of the pad. A constant set in one season and scored in another would cost power for a reason that is not the launches'. Interleaving puts every season on both sides, and CI.CDM's change of channel epoch on 2024-07-30 too (section 7). The rule reads launch numbers and nothing else. Tag 2021-082, the launch D1b looked at at these very stations, is on the constant-setting side by name and has no record read here. [launches.tsv](d3/launches.tsv) lists all 36 with their side, their time and their control times.

## 3. The stations and the windows

**CI.MPP, CI.CDM, CI.HDH and CI.SRN**, the four farther rungs of D1's 2021 ladder, at D1's distances, 78.5, 120.4, 181.4 and 275.0 km: the stations D1b looked at for one launch of 2021, and found seen at 78.5 km, cannot tell at 120.4 km and nothing visible at 181.4 and 275.0 km (D1b, row Q2a). The vertical channel, HHZ, 100 samples a second. Fixed in the design, with no substitute for a station that has no record; every one has.

**The window is D1's sound window with its close redrawn.** It opens d / 0.345 - 5 s after the catalogue's time T0, as D1's row W1; it closes d / 0.240 + 430 + 5 s after it, where D1 took the source to radiate for 180 s (its row W3, an ESTIMATE that D1 and D1b both mark as too short). Its seconds are the whole k with floor(open) <= k < ceiling(close):

| station | km | D1's window, s | the window here, s | length |
|---|---|---|---|---|
| CI.MPP | 78.5 | 222 to 513 | 222 to 763 | 541 s |
| CI.CDM | 120.4 | 343 to 687 | 343 to 937 | 594 s |
| CI.HDH | 181.4 | 520 to 941 | 520 to 1191 | 671 s |
| CI.SRN | 275.0 | 792 to 1331 | 792 to 1581 | 789 s |

**The 430 is set by a rule from one record that is not scored** (row F4): D1b's row Q4a, the 2021 launch's stretch at the four stations where it was measured, ending 502, 511, 481 and 574 s after T0 at 16.5, 32.6, 49.9 and 78.5 km. Each end less d / 0.240 less 5 is 428.2, 370.2, 268.1 and 241.9; the largest, rounded up to a whole ten, is 430. So the close is the latest a sound at D1's slowest speed could arrive from a source that radiates as long as the 2021 launch's did. No record of 2024 set it. What it concedes is limit 5. The ground window is not scored.

The **wrong window** closes 60 s before T0, with the same length and its own noise before it; the **hour-early window** is the true window with T0 moved 3600 s earlier. Both are D2's.

## 4. The control windows

D2's rule (D2, section 4), with two changes. For each launch, three control windows at the same station with the same edges, each hung on T0 plus a whole number of weeks, tried in the order -7, +7, -14, +14, up to 42 days, launches in time order, and the first three taken that are:

1. at least 24 hours from the time of every entry the catalogue lists from Vandenberg's site codes, any vehicle, either side of the split (24 hours and 60 s from an entry timed to the minute; the whole day and 24 hours either side of one with only a day);
2. at least two hours from every control time already taken;
3. between 2023-12-01 and 2025-02-01;
4. **new: inside Pacific daylight time exactly when its launch is**, which is from 2024-03-10 10:00 UTC to 2024-11-03 09:00 UTC in that range. So every control window is at its launch's time of day on the local clock as well as on UTC: D2's limit 8 is closed for this study. Under D2's rule 7 of D2's control times were an hour off their launch's local time (row F5).

D2's condition that a control time sit on its launch's side of a date boundary has no boundary to refer to under this split: a control time belongs to its launch and its side, and condition 2 keeps every one distinct. That gives **103 control times, 35 on the constant-setting side and 68 on the scored side**; 2024-225 and 2024-204 have two each (row F3). A control window cannot hold a launch the catalogue lists; it can hold anything else, and so can a launch window, and nothing was dropped by eye.

## 5. The hit rule, and its one constant

It is D2's, unchanged but for the stations and the close, and is the docstring of [d3rule.py](d3/d3rule.py), which is D2's [rule.py](d2/rule.py) copied with those two changes: D2's `collect` reads D2's own station list, so it could not be imported and pointed elsewhere. In short: D1's band power (`firstlook.band_power`, imported and unchanged), a second is **up** when its ratio to the noise is above 3; inside the window a **run** begins on an up second and ends at two not-up seconds in a row, or at once at a second with no frame; **S** is the largest number of up seconds in one run inside the window; a window is a **hit** when S >= M; it is **usable** when at least 300 of its 601 noise frames exist, their median is above zero, and 90% of its seconds have a frame, and otherwise it is NO RECORD and in neither count. D2's section 5 says how this departs from D1's section 7 and what that concedes; the same holds here.

**M**, for each station, by [d3setconstants.py](d3/d3setconstants.py), D2's rule unchanged: with A the values of S over the constant-setting launch windows and B over their own control windows, J(m) is the share of A at or above m less the share of B at or above m, for m from 10 to the window's length; M is the square root of the product of the two ends of the first range where J is largest, rounded. It ran once, at 09:42:30, on the twelve constant-setting launches and their 35 control windows, none of them NO RECORD (row F8):

| station | M | constant-setting launch windows: S | the largest S of a constant-setting control window | the range where J is largest | J there |
|---|---|---|---|---|---|
| CI.MPP | 23 | 29 to 317 | 63 | 19 to 29 | 33/35 |
| CI.CDM | 33 | 36 to 197 | 29 | 30 to 36 | 1 |
| CI.HDH | 58 | 8 to 313 | 57 | 58 to 59 | 3/4 |
| CI.SRN | 28 | 0 to 205 | 175 | 26 to 30 | 3/10 |

That is not a result: those launches chose the numbers. It was the first look at any record of 2024 at these stations, and it was a look at the constant-setting side only: the script goes through `d3rule.collect`, which refuses a scored launch by name before it asks for any record.

## 6. The test, and what it could have shown

**At each station on its own**: a hits among the n_L usable scored launch windows against b hits among the n_C usable scored control windows, by Fisher's exact test, one-sided: p is the chance of a or more hits among the launch windows if the a + b hits fell at random among all n_L + n_C windows. **The level was fixed in the design at 0.01 for the four stations together, 0.0025 at each.** The readings were fixed too, as D2's: *seen more often than a control window* where a station rejects and neither of its two controls does at 0.01; *VOID* where it rejects and a control rejects too; *NOT SHOWN* where it does not reject on 15 or more launch windows; *CANNOT TELL* on fewer.

**What the count had to exceed**, fixed in the design: with 23 launch and 68 control windows, the least number of launch hits that rejects is 5, 6, 7, 7, 8, 9, 9, 10, 10, 11, 11 for 0 to 10 control hits (row F13). For no control hit, C(23,5) / C(91,5) = 33,649 / 46,504,458 = 0.00072 rejects, and C(23,4) / C(91,4) = 8,855 / 2,672,670 = 0.0033 does not.

**It could have come out either way.** The chance that one station's test rejects, computed in the design before any record was fetched, from two binomials (row F13):

| a launch window hits with chance | a control window hits with chance 0 | 0.05 | 0.1 | 0.2 |
|---|---|---|---|---|
| 0.8 | 1.000 | 1.000 | 1.000 | 0.991 |
| 0.5 | 0.999 | 0.951 | 0.809 | 0.370 |
| 0.4 | 0.981 | 0.788 | 0.512 | 0.124 |
| 0.3 | 0.864 | 0.464 | 0.196 | 0.021 |
| 0.2 | 0.499 | 0.135 | 0.032 | 0.001 |

The design said, before any fetch, that a launch seen one time in five with one control window in twenty hitting would be found 13% of the time, and that at the two farthest stations, where D1b saw nothing in 2021, NOT SHOWN was the likely reading.

## 7. The download

**One service, the Caltech data centre (SCEDC).** Its service front page, its citation page and its waveform service's page were read whole on 2026-11-24 at 09:30, before any data request (row F17). They ask for a citation, ask users to consider the cloud bucket first and to keep to three sessions at once, say that excessive downloads get an address blacklisted and that polling for real-time data is not allowed, and give a request's largest length. Nothing on them limits who may use the data, and none says that use accepts terms. Not read: the privacy notice the footers link.

**What was asked** ([requests.tsv](d3/requests.tsv), written by d3launches.py before the first request): one station-metadata request for the four stations' HHZ in 2024; for each of the 35 launches and 4 stations a launch record from T0 - 4300 s to T0 + the window's close + 10 s, which holds the true window, the wrong window and the hour-early window, each with its noise; and for each of the 103 control times and 4 stations a control record from T0' - 700 s to the same end. The fetch is D2's [fetch.py](d2/fetch.py), run unchanged: one request after another, one session, the Windows curl, no personal detail, resuming by hash.

**What came** (row F7; [manifest.tsv](d3/manifest.tsv) has every request with its time, status, bytes and SHA-256): 553 requests, from 09:32:48 to 09:42:07, every one answered 200. The 552 waveform files are 221,343,744 bytes; the design had estimated about 214 MB. A second run of the fetch found every file on disk with its manifest line's hash and made no request. The bucket holds day-long files where these are windows of 24.6 to 98.2 minutes, which is D1's reason for the web service and is unchanged.

**The station service's answer** (row F18): HHZ at 100 samples a second at all four through 2024. CI.MPP, CI.HDH and CI.SRN have one channel epoch each over the year; CI.CDM has two, split at 2024-07-30 16:45:04 UTC, the same sensor with its scale given as 314,798,810 and then 314,800,731 counts per m/s.

## 8. The result

The scoring run, as printed ([scored-output.txt](d3/scored-output.txt), which also has every one of its 548 windows with its S):

| station | km | M | launch windows that hit | control windows that hit | p | launch hits needed to reject | no record: launch, control | reading |
|---|---|---|---|---|---|---|---|---|
| CI.MPP | 78.5 | 23 | 23 of 23 | 4 of 68 | 8.32e-18 | 8 | 0, 0 | SEEN MORE OFTEN THAN A CONTROL WINDOW |
| CI.CDM | 120.4 | 33 | 20 of 23 | 2 of 67 | 7.38e-15 | 7 | 0, 1 | SEEN MORE OFTEN THAN A CONTROL WINDOW |
| CI.HDH | 181.4 | 58 | 14 of 23 | 5 of 68 | 4.92e-07 | 9 | 0, 0 | SEEN MORE OFTEN THAN A CONTROL WINDOW |
| CI.SRN | 275.0 | 28 | 13 of 23 | 7 of 68 | 1.84e-05 | 10 | 0, 0 | SEEN MORE OFTEN THAN A CONTROL WINDOW |

**HEADLINE, the scored launches: YES: seen more often than a control window at CI.MPP, CI.CDM, CI.HDH, CI.SRN.**

Each p is far under 0.0025, so no reading here turns on how the 0.01 was shared. Over the four, 70 of 92 launch windows hit and 18 of 271 control windows (row F11). The one window with no record is CI.CDM's control window of launch 2024-251 at +14 days: "0 noise frames of 601", so its record holds no frame in the ten minutes before its time. Why was not looked at.

**Chosen after looking.** These describe the output. They were not fixed first, they are not tests, and they change no headline (row F14).

- **The launch is still loud at CI.MPP**: a launch window's S was 126 to 339 of 541 seconds, where the largest S of a control window was 85. Any M from 10 to 309 would have read it as seen.
- **CI.CDM missed three launches**, 2024-091 (S = 32), 2024-129 (S = 20) and 2024-149 (S = 7); its largest launch S was 594, the whole window. Any M from 10 to 189 would have read it as seen.
- **CI.HDH missed nine launches**, all nine in April to October: 12 of the 12 scored launches of November to March hit and 2 of the 11 of April to October. Any M from 14 to 190, and 12, would have read it as seen.
- **CI.SRN missed ten launches**: 8 of 12 hit in November to March and 5 of 11 in April to October. Its control windows are busy, 7 of 68 hitting with S up to 133, and a wrong or hour-early window reached 222. Only M from 10 to 58 would have read it as seen; its M was 28.
- **Two launches missed at three stations**, 2024-091 and 2024-149, each hitting at CI.MPP. They are also the two scored launches whose time of day is between 11:00 and 12:00 Pacific time (18:39 and 18:56 UTC, in daylight time). D2's CI.SYN missed 2024-149 too (D2, section 8). Why was not looked at.
- The constant-setting side had shown the same seasonal pattern at CI.HDH and CI.SRN before the scoring (the table of section 5, in launch order); that was said in the round's ledger before the run, and it chose nothing.

## 9. The controls

Four were named in the brief. Each was built, run and seen to do what it must.

**1. The wrong window, on the real records.** For each scored launch and station, the window of the same length that closes 60 s before T0, scored by the whole frozen rule with its own noise before it, in the same one run. Its hits against the same control windows, by the same test, at 0.01 undivided, which is harder on the control than 0.0025. It must not reject, and it did not:

| station | wrong windows that hit | p | windows an hour early that hit | p | reading |
|---|---|---|---|---|---|
| CI.MPP | 4 of 23 | 0.108 | 4 of 23 | 0.108 | neither rejects |
| CI.CDM | 0 of 23 | 1 | 1 of 23 | 0.592 | neither rejects |
| CI.HDH | 2 of 23 | 0.569 | 2 of 23 | 0.569 | neither rejects |
| CI.SRN | 7 of 23 | 0.0282 | 2 of 23 | 0.72 | neither rejects |

**2. The catalogue shifted by an hour**, in the same table: every scored launch's time moved 3600 s earlier. It is not seen at any station.

So of the 455 control, wrong and hour-early windows with a record, 40 hit; of the 92 launch windows, 70 did (rows F11, F12). CI.SRN's line is the nearest to void: 7 of 23 wrong windows against 7 of 68 controls, where 0.01 would have voided it and 0.0282 did not.

**That these two controls can fail** is held in the gate on made-up records ([tests/test_lch4_rule.py](../../tests/test_lch4_rule.py)): a burst planted in the wrong window, 100 to 70 s before T0, is counted by it and by neither other window, and one 58 to 30 s before T0, past the wrong window's close, is not counted by it; a burst an hour early by the shifted window only; and four wrong or shifted hits of 23 make a station's line VOID while three do not.

**3. A launch used to set the constants, then scored: refused by name.** `d3rule.collect` refuses it with `SCORED-A-CONSTANT-SETTING-LAUNCH` and the tag before any record is asked for; the test hands it a loader that records every call and finds none. The same test refuses each of the thirteen constant-setting tags of the committed list, 2021-082 among them; and the mirror, `CONSTANTS-FROM-A-SCORED-LAUNCH`, for each of the 23 scored tags, both in `collect` and in the constant-setting script's own check ([tests/test_lch4_refusal.py](../../tests/test_lch4_refusal.py)).

**4. The scoring script on made-up records**, in the gate: unit noise with a 5 Hz burst of 60 s planted in each station's window gives S between 58 and 64, and the same noise without it gives 0. On a ratio series written by hand: one not-up second inside a run is not a break, two are; a ratio of exactly 3 is not up and one just above is; a second with no frame ends a run at once; up seconds outside the window do not count; 36 of 40 seconds is usable and 35 is not. **Each number of the rule is held by a test that fails when it moves**, the two D2's limit 18 names among them: **the least number of noise frames**, by a record blanked so that 300 noise frames remain, which is scored, and 299, which is NO RECORD with that count as its reason; and **the window score_at hands to the statistic**, end to end, at each station's own edges: a burst straddling the close counts 39 to 43 seconds, and one starting 5 s after it none, and the same at the open. The windows, the 430, the wrong gap, the shift, the levels 0.0025 and 0.01, the fifteen, S = M a hit and M - 1 not, J's floor and its least window counts, the split, the daylight-saving condition, the 24 hours, the 60 s, the two hours, the three a launch, a noise of zero, and each request's span against the windows and their noise each have a test. The scoring script refuses files that do not hash to the freeze hash, a fetch the manifest does not settle, and a second run.

**Each test was broken on purpose** (row F16): 58 one-place changes to d3rule.py, d3score.py, d3setconstants.py and d3launches.py, each in a copy outside the tree, run against the rule and refusal tests (not the freeze test, which any change to a frozen file fails trivially). The first pass, of 52, caught 51; a second, of 6 more, caught 5. **Two passed every test**: the scoring run writing its output under another name than the one it refuses a second run on, which is D2's own 26th; and a noise of zero let through to a division, which still made the window NO RECORD but under another reason. Each then got a test, after the scoring and outside the frozen files: the scoring script's `main` run in-process with its output moved to a temporary folder must write that very file and then refuse a second run on it; and a record of zeros must be NO RECORD as "the noise is zero". Against the tests as committed, both are caught, and the other 56 were caught by tests that are still there unchanged. In the real tree a second scoring run, at 09:51, printed `REFUSED ALREADY-SCORED`, exited 1, and left the output's SHA-256 as it was.

## 10. Limits, each by what it concedes

1. **Far, and not always faint.** At CI.MPP the launch is loud (section 8). Strength was not measured in physical units; "faint" in this study means far from the pad, and seen at 14 and 13 of 23 scored launches at the two farthest stations, not weak by any measured amount.
2. **One vehicle, one pad, one year, and 35 of 46.** The 11 launches timed only to the minute are left out by the rule. No other site.
3. **A hit is power in a band.** What made it is not established by a hit. A static firing or a called-off countdown the catalogue does not list, an earthquake, wind or traffic can be in any window. The earthquake catalogue was not read (D1's control 7 was not run).
4. **Not shown to be sound.** The window is a sound window, but arrival time against distance was not measured and the ground window was not scored. At these distances the two windows are apart on D1's speeds (D1, section 5), and a hit inside the sound window is consistent with sound; it is not shown to be.
5. **The close was redrawn after D1b's far-station tables had been seen.** The rule that set 430 reads only D1b's four nearer stations (section 3). But under the new close, CI.HDH's 2021 launch day has a run of 21 up seconds wholly inside the window (1153 to 1174 s) and one of 13 partly inside (1182 to 1194 s), which D1's close, at 940 s, left out; CI.SRN's one launch-day run of 2021 (1586 to 1598 s) is outside both. **And a longer window gives a control window more room** for a run of noise: the windows here are 541 to 789 s, against 291 to 539 s on D1's close, so M was set against controls that had more chance to hit. Whether D1's close would have given another reading was not tried, and would be a second analysis chosen after looking.
6. **A rate over the year, and the season.** The test pools the year. By a description made after looking, at CI.HDH the scored launches of April to October hit 2 times in 11 (section 8). The season reason for the split is BELIEVED, from memory, and is not tested here; an experiment that fixed the season split first would be a new one (section 13).
7. **The constants are the twelve setting launches'.** They are interleaved through the year, so no season is unseen by them; that they carry to the other 23 is what the test shows, for 2024 only. CI.CDM's channel epoch changed on 2024-07-30 with the same sensor and a scale that moved by less than one part in 100,000 (section 7); a ratio to the record's own noise cancels a change of gain and not a change of the sensor's band.
8. **The catalogue's times are taken in their written form.** No time was held against a second source (D1's control 11 was not run).
9. **Four tests on the same launches are not independent.** The shared level does not need them to be; the four p values are not four separate confirmations.
10. **A window with no record is in neither count.** Here there is one, a control window at CI.CDM, whose record has no frame in the ten minutes before its time.
11. **CI.SRN is the noisiest station and its line the weakest.** 7 of 68 control windows hit, and its wrong windows came to p = 0.0282 against the 0.01 that would have voided its line. The control did its job; the margin is not wide.
12. **The scoring run cannot be made again in place**, by design, and the fetched files are not in the repository. What is committed lets a reader check the arithmetic from every window's S, and ask the data centre for the same bytes: the manifest has each request and its hash. Whether the data centre would return the same bytes was not tried.
13. **The reader is D2's and D1's**, unchanged: records are put in time order before D1's grid is built, and a record the reader refuses would be NO RECORD, named with its reason; none was. D2's limit 13 holds here as there: no made-up file tests the reader's ordering.
14. **The gate holds the code, not the result.** The tests run on made-up records. The result is one run on files outside the tree.
15. **That the scoring came after the freeze is not in any file of the tree.** What orders them: the freeze commit's time, 09:44:51; the lead's ledger entry of 09:48, which recomputed the freeze hash in this parcel's worktree and allowed the scoring; the output's commit at 09:51:47; and this parcel's ledger, which gives the run as 09:49:43 to 09:51:01. The round's ledger is not committed. **The scored launches' records were on disk before the freeze**, fetched in the same run as the setting launches', which the brief allows; that none was read before the freeze rests on this parcel's word and on its code: the fetch hashes and decodes nothing, and the constant-setting script and the rehearsal before the freeze go through `collect`, which refuses a scored launch by name.
16. **The same 35 launches as D2, whose near-station result was known.** The launch list is D2's rule; no launch was added or dropped for any reason a record could give.
17. **The scripts are D2's, copied and changed** in the stations, the close, the split and the control times, and renamed (`d3rule.py` and so on) so that a test process that imports D2's `rule` cannot be handed it in place of this study's. A fault D2's code shares would be shared; one the copying made is what the tests and the 58 mutants are for.
18. **Chosen after looking is marked**, in section 8, and is description only.

## 11. D1's controls: which this ran

| D1's control | here |
|---|---|
| 1, arrival time | the wrong window that closes before T0: run, section 9. Onset against distance: not run |
| 2, a signal in every record | run, at each station on its own, at 0.0025 in place of D1's 0.01 |
| 3, the hour | control windows at the same UTC time, weekday and local time of day, 24 hours clear of every listed launch: run. The model shown only the minutes before T0: not run; there is no model |
| 7, other things in the window | the launch list was read for every control time. The earthquake catalogue was not |
| 8, splitting | by launch number, every third; a launch on both sides is refused by name. The record-by-record comparison: not run |
| 9, selection | launches, stations and requests named by rule before the fetch; every station reported |
| 10, window length | every control window has its launch window's length. False alarms per hour: not given |
| 12, the instrument | the epochs read and reported (section 7); ratios only (limit 7) |
| 13, not every launch is the same | one vehicle and one pad; flights with a returning stage are not told apart |
| 4, 5, 6, 11, 14 | not run |

## 12. What this changes in D1, D1b, D2 and the plan

For the lead to restate; this parcel edits none of them.

- **The plan's row W4** is no longer only BELIEVED: for the 23 scored launches of 2024, at the four stations 78.5 to 275 km from the pad, by this rule, it is MEASURED, and the answer is yes at each.
- **D2's limit 1**, "Loud, not faint", and its section 14, item 1: this is that experiment.
- **D1b's row Q2a**, for one 2021 launch nothing visible at 181.4 and 275.0 km: in 2024, by this rule, 14 of 23 and 13 of 23 scored launches hit there. D1b used D1's close and a rule that needs a stretch beginning in the window; this study used another close and another hit (sections 3 and 5).
- **D1's row W3**, the source's 180 s: this study took 430 s, by a rule from D1b's row Q4a.
- **D2's limit 8**, control times on the UTC clock: closed for this study's control times by condition 4 of section 4. D2's own control times are as they were; 7 of them are an hour off (row F5).
- **D2's limit 18**, two numbers no test held: both are held for this study's code.
- **[PROVENANCE.md](../../PROVENANCE.md)** is the lead's: this parcel made 3 page requests and 553 service requests to SCEDC on 2026-11-24, and none to any other host.

## 13. What a wider experiment would be

None of this was done.

1. **The season, fixed first**: the same stations with the split and the test made by season, November to March against April to October, with the hypothesis written before any record is opened. Section 8's description says where to look; it cannot be the test.
2. **The 2026 ladder's stations at these distances**, CI.BCH, CI.LAT and CI.SUN (D1, section 3), and stations at other bearings from the pad.
3. **Onset against distance**, with the definition of an onset fixed first, to say sound or ground.
4. **D1's close**, as a second analysis reported as chosen after looking, to see whether the redrawn close changed any reading.
5. **The 11 launches timed to the minute**, with a window a minute wider; **another year**; **windows marked by the earthquake catalogue**, dropped alike from both counts.
6. **The two launches missed at three stations**, 2024-091 and 2024-149: what differed on those days.

## Acknowledgement

Waveform data and station metadata are from the Southern California Earthquake Data Center, cited as it asks: SCEDC (2013): Southern California Earthquake Center. Caltech.Dataset. doi:10.7909/C3WD3xH1. The stations are the Southern California Seismic Network's: California Institute of Technology (Caltech) (1926): Southern California Seismic Network. International Federation of Digital Seismograph Networks. Other/Seismic Network. doi:10.7914/SN/CI. Launch times are from GCAT (J. McDowell, planet4589.org/space/gcat), under CC-BY, as [PROVENANCE.md](../../PROVENANCE.md) records.

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| F1 | The design was in the round's ledger at 09:27 and the lead approved it at 09:29; the three terms pages were requested at 09:30:05 to 09:30:08 and the first data request was at 09:32:48; the freeze was committed at 09:44:51 as `db4bef1`; the lead allowed the scoring in an entry of 09:48; the one scoring run was 09:49:43 to 09:51:01, and its output was committed at 09:51:47 as `4a3f3b9`; all on 2026-11-24 | MEASURED | `<ledger>`, this parcel's file and the lead's, the entries of those times; `git log -1 --format=%ci db4bef1` and the same for `4a3f3b9`; `python docs/studies/d3/d3describe.py`, lines D4 and D5, for the first and last data request; `<scratch>/requests.log` for the page requests | the ledger's entries; the commits' own times; the manifest |
| F2 | The freeze hash is `645d1e84...afe59`; the seven files in the tree hash to it, the scoring run printed it, and the committed output's SHA-256 is `e2b3d132...845f3e` | MEASURED | `python docs/studies/d3/d3score.py --freeze-hash`; `python docs/studies/d3/d3describe.py`, line D18; `python -m pytest -q -p no:cacheprovider tests/test_lch4_freeze.py` | a changed byte in any of the seven files or in the output |
| F3 | 35 launches have records and 553 requests were listed; 13 tags are on the constant-setting side, one of them 2021-082 with no record, and 23 are scored; there are 35 and 68 control times, 103 in all | MEASURED | `python docs/studies/d3/d3launches.py <catalogue> --check`, which printed "OK check: launches.tsv and requests.tsv: 35 launches with records, 553 requests"; `python docs/studies/d3/d3describe.py`, lines D1 and D4 | the catalogue file, by its hash |
| F4 | The windows of section 3's table, and the 430: 428.2, 370.2, 268.1 and 241.9 from D1b's ends of 502, 511, 481 and 574 s | COMPUTED | `python docs/studies/d3/d3describe.py`, line D2; by hand, 502 - 16.5 / 0.240 - 5 = 428.2, 511 - 32.6 / 0.240 - 5 = 370.2, 481 - 49.9 / 0.240 - 5 = 268.1, 574 - 78.5 / 0.240 - 5 = 241.9; D1b, row Q4a, for the ends | arithmetic; D1b's row |
| F5 | Every control time of this study is on its launch's local clock; 7 of D2's control times are an hour off their launch's local time | COMPUTED | `python docs/studies/d3/d3describe.py`, lines D19 and D20 | the two lists of launches |
| F6 | The record spans: launch records from T0 - 4300 s to T0 + 773, 947, 1201 and 1591 s, control records from T0' - 700 s to the same, at CI.MPP, CI.CDM, CI.HDH and CI.SRN | COMPUTED | `python docs/studies/d3/d3describe.py`, line D3 | the request list |
| F7 | 553 requests from 09:32:48 to 09:42:07 local, every one answered 200; 552 waveform files of 221,343,744 bytes, 138 at each station; a second run of the fetch made no request | MEASURED | `python docs/studies/d3/d3describe.py`, lines D4 and D5, from [manifest.tsv](d3/manifest.tsv); `python docs/studies/d2/fetch.py docs/studies/d3/requests.tsv <data> docs/studies/d3/manifest.tsv <scratch>/requests.log 60`, run at 09:42, which printed "553 requests in the list, 0 to make" | the manifest; the files' hashes |
| F8 | The constants: 23, 33, 58 and 28, set from records at each station, from the twelve launches 2024-002 to 2024-247 of the constant-setting side, and the table of section 5 | MEASURED | `python docs/studies/d3/d3setconstants.py <data>`, run once, 09:42:30 to 09:43:05, its output kept as `<scratch>/setconstants-out1.txt`; `python docs/studies/d3/d3describe.py`, lines D6 and D7, from [constants.json](d3/constants.json) | a rerun on the same files |
| F9 | The design's estimate of the download was about 214 MB | ESTIMATE | the design in `<ledger>`, this parcel's file, 09:27, section 8: each station's largest bytes a second in D1b's 2021 files times the spans | F7, which measured 221 MB |
| F10 | The first table of section 8 and the headline under it, as the scoring run printed them | MEASURED | `python docs/studies/d3/d3score.py <data> --freeze 645d1e84d9e78a1ad3a987e767b38b885e1fe5e0553d3b31bd212ff33baafe59`, run once on 2026-11-24; its output is [scored-output.txt](d3/scored-output.txt) | the same rule on the same files in a copy of the tree without that output; the manifest's hashes hold the files |
| F11 | From the table of every window in that output: the four stations' counts and p as in section 8; over the four, 70 of 92 launch windows and 18 of 271 control windows hit; the one window with no record is CI.CDM's control 2024-251 +14, for "0 noise frames of 601" | COMPUTED | `python docs/studies/d3/d3describe.py`, lines D8 to D11, which count the output's 548 rows again and take p again | a row of the output that disagrees with its table |
| F12 | The table of section 9; of 455 control, wrong and hour-early windows with a record, 40 hit | COMPUTED | `python docs/studies/d3/d3describe.py`, lines D9 and D12; 455 is 271 and 92 and 92 | the output's rows |
| F13 | The table of section 6, and the least launch-hit counts that reject at 0.0025 with 23 and 68 windows | COMPUTED | `python docs/studies/d3/d3describe.py`, lines D16 and D17; by hand for no control hit, 33,649 / 46,504,458 and 8,855 / 2,672,670 | arithmetic; a simulation |
| F14 | Chosen after looking: the S of launch and control windows at each station, the launches that missed, the values of M that would still read seen, and the hits by season; 2024-091 and 2024-149 at 18:39 and 18:56 UTC, 11:39 and 11:56 in Pacific daylight time | COMPUTED | `python docs/studies/d3/d3describe.py`, lines D13, D14 and D15; the two times from [launches.tsv](d3/launches.tsv), less seven hours | the output's rows; these were not fixed before the run |
| F15 | This parcel's tests: 45, all passing; the gate's verdict at the last commit is in the commit's message | MEASURED | `python -m pytest -q -p no:cacheprovider tests/test_lch4_rule.py tests/test_lch4_refusal.py tests/test_lch4_freeze.py`; `bash verify/run.sh` | a rerun |
| F16 | 58 one-place changes to the four scripts, each in a copy: 51 of the first 52 and 5 of the next 6 failed a test; the two that failed none, the output's name and a zero noise, each fail a test added after; a second scoring run in the real tree was refused, `REFUSED ALREADY-SCORED`, with exit 1, and the output's SHA-256 was the same after | MEASURED | `python <scratch>/mutate.py <worktree> <scratch>/mutant-copy`, 2026-11-24, 09:51 to 09:59, its output `<scratch>/mutate-out.txt` ("51 of 52 caught"); the same with the names of the six new ones, 10:01, `<scratch>/mutate-out2.txt` ("6 of 7 caught", the seventh a renaming of one of the 52); the same with the two that passed, 10:02, `<scratch>/mutate-out3.txt` ("2 of 2 caught"); the script is not in the tree. The second run: the command of row F10, again, at 09:51 | a change it did not try |
| F17 | The three SCEDC pages were read whole before any data request, and nothing on them limits who may use the data or says that use accepts terms | READ | https://service.scedc.caltech.edu/, https://scedc.caltech.edu/about/citation.html and https://service.scedc.caltech.edu/fdsnws/dataselect/1/, fetched 2026-11-24 at 09:30 into `<scratch>/pages` and read as text from first line to last; their requests are logged in `<scratch>/requests.log` | the pages |
| F18 | The station service lists HHZ at 100 samples a second for the four through 2024: CI.MPP from 2021-05-11; CI.HDH from 2016-08-11 to 2025-06-24; CI.SRN from 2023-02-08; CI.CDM from 2023-08-31 to 2024-07-30 16:45:04 and from then on, its scale 314,798,810 and then 314,800,731 | MEASURED | the answer saved as `<data>/scedc-ci-hhz-2024-epochs.txt`, columns Scale, SampleRate, StartTime and EndTime; its request is the first row of [manifest.tsv](d3/manifest.tsv) | making the request again |
| F19 | D1b's 2021 runs at CI.HDH, 21 up seconds from 1153 to 1174 s and 13 from 1182 to 1194 s, and at CI.SRN, 10 from 1586 to 1598 s, on the launch day | READ | D1b, section 5, the table of the whole 50 minutes, rows CI.HDH and CI.SRN, launch day | that row |
| F20 | The four stations, the redrawn close and its rule, the split, the control-time rule and its daylight-saving condition, three controls, D2's hit rule and the rule that sets M, the level 0.01 over four, the controls' 0.01, the fifteen | DECISION | the design in `<ledger>`, this parcel's file, 2026-11-24 09:27, approved by the lead at 09:29, before any record of these stations in 2024 was fetched | the lead's ruling of that time |
| F21 | Sound reaching stations this far travels in ducts of the upper air whose winds turn with the season, which is the split's reason | BELIEVED | from memory; no source was read | a source on seasonal infrasound propagation; the season-first experiment of section 13 |

# D2: the launch-data experiment - are launches seen more often than control windows?

Written by the parcel LCH-3 on 2026-11-23, for round 2 ([the plan](../plans/R2-fabric-in-simulation-and-the-learner.md), row LCH-3 and row W4). It follows [study D1](D1-launch-data.md) and [its first look, D1b](D1b-first-look.md).

**The headline. By a rule frozen before any scored record was opened, the scored launches were seen more often than control windows at each of the four stations nearest the pad: at CI.LOC (16.5 km) 23 of 23 launch windows hit against 0 of 68 control windows; at CI.LCP (32.6 km) 23 of 23 against 0 of 68; at CI.SYN (49.9 km) 20 of 23 against 0 of 68; and at CI.GATR (13.5 km) 7 of 7 against 0 of 21, on the seven scored launches it has a record for.** Fisher's exact test, one-sided, at 0.01 shared over the four stations, 0.0025 at each: the four p values run from 8.45e-07 to 4.74e-22 (rows X6, X7). The two controls on the same records did not reject: no window placed to close before the launch hit, and one window of 76 placed an hour early did (row X8). **What it does not show.** A hit is seconds of power in one band of one channel; that a launch made it rests on the control windows and the two controls, not on anything the rule knows about rockets. The launches are Falcon 9 launches of 2024 from one pad, the 35 of 46 that the catalogue times to the second, at stations within 50 km. At those stations the launch is not faint: a launch window's count of up seconds fills most of its window (row X10, a description made after looking). So this says the source can label a loud event near the pad; it says nothing yet of a faint one farther out, which is what the project wants a label for. **Nothing here is evidence about the detector, the model or the fabric:** no detector was run, and this touches none of [D0](D0-rough-design.md)'s gates. It is about whether this data source can label an event at all. **What the experiment's choices knew.** The stations, the hit rule and the split were chosen with the 2021 launch's records in hand (D1b) and no record of 2024. One constant a station was then set from the first twelve launches of 2024, and those twelve are not scored.

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. `<data>` is this parcel's data folder in the round's run folder, outside the repository; nothing in it is committed. `<scratch>` is its scratch folder there. `<catalogue>` is the folder that holds the launch list D1b fetched. Times of day are local, seven hours behind UTC. Every figure is in the register at the end.

## 1. The question, and the three walls

**By a rule fixed before any record of them is fetched, are launches seen at the nearest stations more often than control windows are?** That is the plan's row W4, BELIEVED there. The danger is a rule tuned on the launches it then scores. Three walls stand against it, and this is when each was built (row X1):

| wall | what | when, 2026-11-23 |
|---|---|---|
| 1. The split before any fetch | the launches, the split, the stations, the windows, the control times, the hit rule, the test and its level, written in the round's ledger and approved by the lead | written 13:18, corrected 13:20, approved 13:22; the first data request was at 13:25:03 |
| 2. The rule frozen before a scored record is opened | [rule.py](d2/rule.py), [score.py](d2/score.py), [constants.json](d2/constants.json), [launches.tsv](d2/launches.tsv), [manifest.tsv](d2/manifest.tsv) and D1's [firstlook.py](d1/firstlook.py) and [mseed.py](d1/mseed.py), committed at 13:41:35 as `1f321ec`; the SHA-256 of their seven hashes, the freeze hash, written in the ledger and recomputed by the lead | accepted 13:44 |
| 3. Scored once | one run of score.py, 13:44:20 to 13:45:27; its output, [scored-output.txt](d2/scored-output.txt), is kept as printed, and the script refuses to run while that file exists | once |

Before the freeze the scored launches' files were bytes, lengths and hashes: [fetch.py](d2/fetch.py) decodes nothing. The two scripts that read a record, [setconstants.py](d2/setconstants.py) and score.py, both go through `rule.collect`, which is handed the one side it may read and refuses a launch of the other side by name before it asks for any record.

The freeze hash is `dc7f28f172f8e201095a07a1a5b762a74407b4ca5c78d58a5d4b6815051f781f`. `python docs/studies/d2/score.py --freeze-hash` prints the seven lines it is the hash of; it is the hash the scoring run printed on its own second line (row X2).

## 2. The launches and the split

**The rule.** From GCAT's launch list as D1b fetched it (its SHA-256 is in [d1/manifest.tsv](d1/manifest.tsv) and in [launches.py](d2/launches.py), which refuses any other file): every entry with vehicle Falcon 9, a site among Vandenberg's codes, a date in 2024 UTC, and a time written to the second and not marked uncertain. That is 35 of the 46 the catalogue lists (D1b, row Q6f); the other 11 are timed to the minute. The catalogue was not asked again.

**The split, by date.** In time order the first 12 set constants and the last 23 are scored: 2024-01-03 to 2024-04-07, and 2024-05-10 to 2024-12-29. The rule reads the catalogue's dates and nothing else. It cannot favour an answer; it can cost power, since a constant set in January to April is applied to the rest of the year. The launch D1b looked at, tag 2021-082, is on the constant-setting side by name and has no record read here. [launches.tsv](d2/launches.tsv) lists all 36 with their side, their time and their control times (row X3).

## 3. The stations and the windows

**CI.GATR, CI.LOC, CI.LCP and CI.SYN**, the four nearest of the eight stations D1b asked for, at D1's distances: 13.5, 16.5, 32.6 and 49.9 km. The vertical channel, HHZ, 100 samples a second. Fixed in the design, with no substitute for a station that has no record.

**The window** is D1's sound window, row W1 of D1, unchanged: it opens d / 0.345 - 5 s after the catalogue's time T0 and closes d / 0.240 + 185 s after it; its seconds are the whole k with floor(open) <= k < ceiling(close). That is 34 to 242 s at GATR, 42 to 254 at LOC, 89 to 321 at LCP and 139 to 393 at SYN. D1b found the 180 s inside that close too short for its one launch; the window was not re-drawn, since that would have been one more number taken from a record. The ground window is not scored.

## 4. The control windows

For each launch window, three control windows at the same station with the same edges, each hung on **T0 plus a whole number of weeks**: the same UTC time of day and the same weekday (D1's control 3). The candidates are tried in the order -7, +7, -14, +14, up to 42 days, launches in time order, and the first three are taken that are:

1. at least 24 hours from the time of every entry the catalogue lists from Vandenberg's site codes, any vehicle, any pad, on either side of the split, the 11 coarsely timed launches among them (24 hours and 60 s from an entry timed to the minute; the whole day and 24 hours either side of an entry with only a day);
2. on the same side of the split's boundary as their launch, so that no control window serves both sides;
3. at least two hours from every control time already taken;
4. between 2023-12-01 and 2025-02-01.

That gives 104 control times: 36 on the constant-setting side and 68 on the scored side; one scored launch, 2024-091, has two (row X3). So a control window cannot hold a launch the catalogue lists, a constant-setting launch's day among them. It can hold a firing the catalogue does not list, an earthquake, or anything else; so can a launch window, and nothing was dropped by eye.

## 5. The hit rule

It is the docstring of [rule.py](d2/rule.py), and every step is arithmetic on the samples, the catalogue's time, D1's distance and one integer:

1. **The measure** is D1's, the code of `firstlook.band_power`, imported and unchanged: frames of 400 samples, one a second, frame k centred on T + k seconds, mean removed, Hann window, squared magnitude summed over the bins with 2 <= f < 8 Hz. The noise is the median of that over the frames centred 660 s to 60 s before T. The ratio is power over noise.
2. A second is **up** when its ratio is above 3. Exactly 3 is not up. This is D1's value and was not tuned.
3. Inside the window a **run** begins on an up second and ends when two seconds in a row are not up, or at once at a second that has no frame. One not-up second between two up seconds does not end it and is not counted.
4. **S** is the largest number of up seconds in one run inside the window.
5. A window is a **hit** when S >= M, the station's constant.
6. A window is **usable** when its file came, at least 300 of the 601 noise frames exist, and at least 90% of its seconds have a frame. Otherwise it is NO RECORD and is in neither count.

**This departs from D1's section 7.** There, step 4, a hit is a counting stretch that *begins* inside the window. Here a hit counts up seconds *inside* the window, wherever the run began. The change was chosen knowing the 2021 launch's records and before any 2024 record was fetched: D1b's onsets sat 3 s inside the window's opening at CI.LOC and 2 s inside it at CI.MPP, so by D1's step a launch a few seconds quicker would be no hit while the station shook for minutes. **What it concedes:** a long disturbance that began before the window counts too. That falls on control windows as on launch windows, and the wrong-window control of section 9 is there to see it. D1's proposal to set a threshold from control windows at a false-alarm fraction of 0.05 was not used either: it needs 200 control windows a station (D1, row H1).

**The one constant set from records, M**, for each station, by [setconstants.py](d2/setconstants.py), from the constant-setting launches' windows and their own control windows: with A the values of S over the launch windows and B over the control windows, J(m) is the share of A at or above m less the share of B at or above m, for m from 10 to the window's length; M is the square root of the product of the two ends of the first range of m where J is largest, rounded: the middle, on a ratio scale, of the range that best parts launches from controls. With fewer than 4 launch windows or fewer than 8 control windows M is D1's 10 and is said to be not set from records.

| station | M | set from records | constant-setting launch windows: S | the largest S of a constant-setting control window | the range where J is largest |
|---|---|---|---|---|---|
| CI.GATR | 10 | no: no record for any of the twelve | none | none | - |
| CI.LOC | 95 | yes | 12 windows, 196 to 212 | 45, of 36 windows | 46 to 196 |
| CI.LCP | 96 | yes | 12 windows, 160 to 229 | 57, of 36 windows | 58 to 160 |
| CI.SYN | 130 | yes | 10 windows, 155 to 195 | 108, of 33 windows | 109 to 155 |

At each of the three, every constant-setting launch window lies above every constant-setting control window (row X5). That is not a result: those launches chose the number.

## 6. The test, and what it could have shown

**At each station on its own** (D1's control 2): a hits among the n_L usable scored launch windows against b hits among the n_C usable scored control windows, by Fisher's exact test, one-sided: p is the chance of a or more hits among the launch windows if the a + b hits fell at random among all n_L + n_C windows. **The level was fixed in the design at 0.01 for the four stations together, 0.0025 at each**, whether or not a station had a record. With 23 launch and 69 control windows the smallest a that rejects is 5 when no control window hits, 6 with one, 7 with two or three (row X11). For no control hit the arithmetic is C(23,5) / C(92,5) = 33,649 / 49,177,128 = 0.00068, which rejects, where four of four gives 8,855 / 2,794,155 = 0.0032, which does not.

**The readings were fixed too:** *seen more often than a control window* where a station rejects and neither of its two controls on real records does; *VOID* where it rejects and a control rejects too; *NOT SHOWN* where it does not reject on 15 or more launch windows; *CANNOT TELL* where it does not reject on fewer.

**It could have come out either way.** The chance that one station's test rejects, computed in the design before any record was fetched, from two binomials (row X12):

| launch, control windows | a launch window hits with chance | a control window hits with chance 0 | 0.05 | 0.125 | 0.25 |
|---|---|---|---|---|---|
| 23, 69 | 0.80 | 1.000 | 1.000 | 1.000 | 0.968 |
| 23, 69 | 0.50 | 0.999 | 0.949 | 0.702 | 0.207 |
| 23, 69 | 0.20 | 0.499 | 0.132 | 0.014 | 0.000 |
| 15, 45 | 0.50 | 0.941 | 0.757 | 0.412 | 0.089 |
| 10, 30 | 0.50 | 0.828 | 0.517 | 0.214 | 0.046 |

A launch seen one time in five, with one control window in twenty hitting, would have been found 13% of the time: the experiment could have failed to reject a real and weak effect. With no effect at all a station's test rejects at most 0.0013 of the time at these sizes.

## 7. The download

**One service, the Caltech data centre (SCEDC).** Its service front page, its citation page and its waveform service's page were read whole on 2026-11-23 at 13:22, before any data request. They say what D1's rows T1, T2 and T7 quote from them: a citation is asked for, users are asked to consider the cloud bucket first and to keep to three sessions at once, and a request has a largest length. They also say excessive downloads get an address blacklisted, without a number, and that polling for real-time data is not allowed. Nothing on them limits who may use the data, and none says that use accepts terms. Not read: the university's privacy notice and its copyright-claims page, which the footers link.

**What was asked** (the list is [requests.tsv](d2/requests.tsv), written by launches.py before the first request): one station-metadata request; for each of the 35 launches and 4 stations a launch record, T0 - 4300 s to T0 + 500 s, which holds the true window, the wrong window and the window an hour early, each with its own ten minutes of noise; and for each of the 104 control times and 4 stations a control record, T0' - 700 s to T0' + 500 s.

**What came** (row X4; [manifest.tsv](d2/manifest.tsv) has every request with its time, status, bytes and SHA-256): 557 requests, one after another, in one session, from 13:25:03 to 13:33:35. 446 were answered 200 and 111 were answered 404. The 445 waveform files are 132,153,344 bytes. A second run of fetch.py found every file on disk with its manifest line's hash and made no request. The data centre asks that users consider its cloud bucket first; these are 20-minute and 80-minute windows where the bucket holds day-long files, which is D1's reason for the web service and is unchanged.

**All 111 of the 404s are CI.GATR's.** CI.LOC, CI.LCP and CI.SYN answered all 139 of their requests. Section 10 is GATR's.

## 8. The result

The scoring run, as printed ([scored-output.txt](d2/scored-output.txt), which also has every one of its 548 windows with its S):

| station | km | M | launch windows that hit | control windows that hit | p | launch hits needed to reject | no record: launch, control | reading |
|---|---|---|---|---|---|---|---|---|
| CI.GATR | 13.5 | 10 | 7 of 7 | 0 of 21 | 8.45e-07 | 4 | 16, 47 | SEEN MORE OFTEN THAN A CONTROL WINDOW |
| CI.LOC | 16.5 | 95 | 23 of 23 | 0 of 68 | 4.74e-22 | 5 | 0, 0 | SEEN MORE OFTEN THAN A CONTROL WINDOW |
| CI.LCP | 32.6 | 96 | 23 of 23 | 0 of 68 | 4.74e-22 | 5 | 0, 0 | SEEN MORE OFTEN THAN A CONTROL WINDOW |
| CI.SYN | 49.9 | 130 | 20 of 23 | 0 of 68 | 2.71e-17 | 5 | 0, 0 | SEEN MORE OFTEN THAN A CONTROL WINDOW |

**HEADLINE, the scored launches: YES: seen more often than a control window at CI.GATR, CI.LOC, CI.LCP, CI.SYN.**

Each p is far under 0.0025, so no reading here turns on how the 0.01 was shared. Every window with no record is CI.GATR's, and each is so because no file came (row X9).

**Chosen after looking.** These describe the output. They were not fixed first, they are not tests, and they change no headline (row X10).

- **The launch is loud at these stations.** A launch window's S was 176 to 208 of 208 seconds at CI.GATR, 166 to 212 of 212 at CI.LOC and 135 to 232 of 232 at CI.LCP. The largest S of any control window was 6, 65 and 75.
- **CI.SYN missed three launches**: 2024-149 (S = 14), 2024-171 (S = 14) and 2024-175 (S = 90), where its other twenty were 139 to 251 of 254 and its largest control window was 71. The same three launches hit at CI.LOC and CI.LCP. Why CI.SYN missed them was not looked at.
- **How much the answer rests on M.** At CI.GATR any M from 7 to 176 would part every launch window from every control, wrong and hour-early window; at CI.LOC any from 114 to 166; at CI.LCP any from 92 to 135. At CI.SYN none would: its smallest launch S is 14 and its largest other S is 71.

## 9. The controls

Four were named in the brief. Each was built, run and seen to do what it must.

**1. The wrong window, on the real records.** For each scored launch and station, the window of the same length that closes 60 s before T0, scored by the whole frozen rule with its own noise before it, in the same one run. Its hits against the same control windows, by the same test, at 0.01 undivided, which is harder on the control than 0.0025. It must not reject:

| station | wrong windows that hit | p | windows an hour early that hit | p | reading |
|---|---|---|---|---|---|
| CI.GATR | 0 of 7 | 1 | 0 of 7 | 1 | neither rejects |
| CI.LOC | 0 of 23 | 1 | 1 of 23 | 0.253 | neither rejects |
| CI.LCP | 0 of 23 | 1 | 0 of 23 | 1 | neither rejects |
| CI.SYN | 0 of 23 | 1 | 0 of 23 | 1 | neither rejects |

No wrong window hit, of 76. So the rule did not answer to something that was already there a minute before the launch. D1's other wrong window, placed as if the station were at twice its distance, was not used: a signal that lasts as long as D1b's can reach into it.

**2. The catalogue shifted by an hour**, in the same table: every scored launch's time moved 3600 s earlier. One window of 76 hit: CI.LOC, an hour before launch 2024-171, with S = 113 against M = 95. One of 23 against none of 68 has p = 0.253. It is not "seen" at any station. What made that one hit was not looked at.

So of the 377 control, wrong and hour-early windows with a record, one hit; of the 76 launch windows with a record, 73 did (rows X7, X8).

**That these two controls can fail** is held in the gate on made-up records: a burst planted before T0 is counted by the wrong window and not by the true one, a burst planted an hour early by the shifted window only, and four wrong or shifted hits of 23 make a station's line VOID.

**3. A launch used to set the constants, then scored: refused by name.** `rule.collect` refuses it with `SCORED-A-CONSTANT-SETTING-LAUNCH` and the tag before any record is asked for; the test hands it a loader that records every call and finds none. The same test refuses each of the thirteen constant-setting tags of the committed list, 2021-082 among them. The mirror is held too: a scored launch offered to the constant-setting side is refused with `CONSTANTS-FROM-A-SCORED-LAUNCH`. On the real list, before the freeze, `python docs/studies/d2/setconstants.py <data> --tags 2024-002,2024-088` printed `REFUSED CONSTANTS-FROM-A-SCORED-LAUNCH: 2024-088` and exited 1 (row X13).

**4. The scoring script on made-up records**, in the gate ([tests/test_lch3_rule.py](../../tests/test_lch3_rule.py), [tests/test_lch3_refusal.py](../../tests/test_lch3_refusal.py); row X14): unit noise with a 5 Hz burst of 60 s planted in CI.LOC's window gives S between 58 and 64, and the same noise without it gives 0. On a ratio series written by hand: twenty up seconds with one not-up second inside are one run of 20; nineteen with one are 19; two not-up seconds in a row split a run; a ratio of exactly 3 is not up; a second with no frame ends a run at once; up seconds outside the window do not count. The level, the controls' level, the fifteen, and S equal to M being a hit each have a test. score.py refuses files that do not hash to the freeze hash, a fetch the manifest does not settle, and a second run.

**Each test was broken on purpose.** 25 one-place changes to rule.py, setconstants.py and score.py, each in a copy outside the tree: every one failed a test. A 26th was tried knowing no test holds it, and none does: the name of the file the scoring run writes. If the run wrote under one name and looked for another, a second run would not be refused. What holds that instead is the real tree: at 13:54 a second run with the right hash printed `REFUSED ALREADY-SCORED`, exited 1, and left the output's hash as it was (row X15).

## 10. CI.GATR

The station nearest the pad answered 404 to 111 of its 139 requests. It has a launch record for the last seven scored launches, 2024-213 to 2024-251, and for none of the first sixteen and none of the twelve constant-setting launches. The latest window it refused starts on 2024-11-14 and the earliest it answered starts on 2024-11-16 (row X16). The station service lists an HHZ channel for it through all of 2024, with a new epoch from 2024-04-30 (row X17): as D1b found for 2021, an epoch is not a record.

By the design, fixed before the fetch and not changed after it: GATR was scored on the launch windows it has, at D1's M of 10, because no constant-setting record could set one. **So its line rests on a constant no 2024 record chose**, on seven launches of six weeks of one season, and on 21 control windows. It rejected: 7 of 7 against 0 of 21, p = 1 / C(28,7) = 8.45e-07, the smallest p those numbers allow.

**What a station that can hardly reject does to a level shared over four.** The 0.01 was divided by four before anyone knew GATR had so little. A station with no record spends its quarter on a test that is never run, and the other three are then held at 0.0025 where 0.0033, a third of 0.01, would have kept the three together at 0.01. That costs power, not validity: at 23 launch and 68 control windows, with no control hit, 5 launch hits are needed at 0.0025 and 4 at 0.0033; with two control hits, 7 and 6 (row X11). With its seven windows GATR could still reject, from 4 launch hits when no control window hits. Here every p is so small that the share made no difference.

## 11. Limits, each by what it concedes

1. **Loud, not faint.** The four stations are within 50 km. Nothing here says a launch is seen where D1b found it marginal, 120 km and beyond, and that is where a label for a faint event would have to come from.
2. **One vehicle, one pad, one year, and 35 of 46.** The 11 launches timed only to the minute are left out by the rule, and whether they differ from the 35 in anything but their time's form was not looked at. No other site.
3. **A hit is power in a band.** What made it is not established by a hit. A static firing or a called-off countdown the catalogue does not list, an earthquake, wind or traffic can be in any window. The earthquake catalogue was not read (D1's control 7 was not run).
4. **Not shown to be sound.** The window is D1's sound window, but arrival time against distance was not measured, the ground window was not scored, and near the pad the two windows overlap. That the energy came through the air is not established here.
5. **CI.GATR's constant was not set from records**, and its line rests on seven launches (section 10).
6. **The constants are January to April's.** That they carried to May to December at three stations is what the test shows. It is not shown for another year or after a change of instrument. CI.GATR's channel epoch changed on 2024-04-30; a ratio to the record's own noise cancels a change of gain and not a change of the sensor's band.
7. **The hit rule departs from D1's** (section 5), and concedes a disturbance that began before the window.
8. **Control times match the UTC clock**, not the local one: across a change of daylight saving a control window is an hour off the launch's local time. Which pairs that touches was not worked out.
9. **The catalogue's times are taken in their written form.** Many end in :00. No time was held against a second source (D1's control 11 was not run).
10. **Four tests on the same launches are not independent.** The shared level does not need them to be; the four p values are not four separate confirmations.
11. **A window with no record is in neither count.** Here every such window is one whose file never came, all at CI.GATR. Had a gap been more likely during a launch than on a control day, leaving it out could bias a count; with no gap at the other three stations there is nothing here to bias.
12. **The scoring run cannot be made again in place**, by design, and the fetched files are not in the repository. What is committed lets a reader check the arithmetic from every window's S, and ask the data centre for the same bytes: the manifest has each request and its hash. Whether the data centre would return the same bytes was not tried.
13. **The reader.** Records are put in time order before D1's grid is built; no made-up file tests that line. A record the reader refuses would be NO RECORD, named with its reason; none was.
14. **The gate holds the code, not the result.** The 31 tests run on made-up records. The result is one run on files outside the tree. And one line of the scoring script no test holds: the name of the file it writes (section 9).
15. **Chosen after looking is marked**, in section 8, and is description only.

## 12. D1's controls: which this ran

| D1's control | here |
|---|---|
| 1, arrival time | the wrong window that closes before T0: run, section 9. Onset against distance: not run |
| 2, a signal in every record | run, at each station on its own, at 0.0025 in place of D1's 0.01 |
| 3, the hour | control windows at the same UTC time and weekday, 24 hours clear of every listed launch: run. The model shown only the minutes before T0: not run; there is no model |
| 7, other things in the window | the launch list was read for every control time. The earthquake catalogue was not |
| 8, splitting | by launch and by date; a launch on both sides is refused by name. The record-by-record comparison: not run |
| 9, selection | launches, stations and requests named by rule before the fetch; every station reported |
| 10, window length | every control window has its launch window's length. False alarms per hour: not given |
| 12, the instrument | not run; ratios only (limit 6) |
| 13, not every launch is the same | one vehicle and one pad; flights with a returning stage are not told apart |
| 4, 5, 6, 11, 14 | not run |

## 13. What this changes in D1, D1b and the plan

For the lead to restate; this parcel edits none of them.

- **The plan's row W4** is no longer only BELIEVED: for the 23 scored launches of 2024, at four stations within 50 km, by this rule, it is MEASURED, and the answer is yes.
- **D1's section 9**, "whether a public record shows a launch, as a rate", and D1b's first paragraph, one launch: at three stations there are now 23 scored launches, 66 of whose 69 windows hit.
- **D1's section 7, step 4**: this experiment used another hit, and says why (section 5).
- **D1b's row Q1b** and D1's ladder: CI.GATR has no record for any window asked before 2024-11-14 and has them from 2024-11-16.
- **The plan's row N17** foresaw 378 MB and 35 minutes; this list was 132 MB in eight and a half minutes, with fewer stations and more control windows.
- **[PROVENANCE.md](../../PROVENANCE.md)** is the lead's: this parcel made 3 page requests and 557 service requests to SCEDC on 2026-11-23 and none to any other host.

## 14. What a wider experiment would be

None of this was done.

1. **The faint rungs**: the same 35 launches at D1b's farther stations, 78 to 275 km, with the rule and a new split fixed first. That is the experiment the project's question needs.
2. **Onset against distance**, with the definition of an onset fixed first, to say sound or ground.
3. **The 11 launches timed to the minute**, with a window a minute wider.
4. **Windows marked by the earthquake catalogue**, dropped alike from launch and control counts, to see whether a count moves.
5. **Another year**, to see whether a constant set in 2024 holds.
6. **CI.SYN's three misses**: what differed on those days.

## Acknowledgement

Waveform data and station metadata are from the Southern California Earthquake Data Center, cited as it asks: SCEDC (2013): Southern California Earthquake Center. Caltech.Dataset. doi:10.7909/C3WD3xH1. The stations are the Southern California Seismic Network's: California Institute of Technology (Caltech) (1926): Southern California Seismic Network. International Federation of Digital Seismograph Networks. Other/Seismic Network. doi:10.7914/SN/CI. Launch times are from GCAT (J. McDowell), under CC-BY, as [PROVENANCE.md](../../PROVENANCE.md) records.

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| X1 | The design was in the round's ledger at 13:18 and corrected at 13:20, the lead approved it at 13:22, the first data request was at 13:25:03, the freeze was committed at 13:41:35 as `1f321ec`, the lead accepted it at 13:44, and the one scoring run was 13:44:20 to 13:45:27, all on 2026-11-23 | MEASURED | the round's ledger, this parcel's file and the lead's, the entries of those times; `git log -1 --format=%ci 1f321ec`; `python docs/studies/d2/describe.py`, line D1, for the first request, which the manifest gives in UTC | the ledger's entries; the commit's own time; the manifest |
| X2 | The freeze hash is `dc7f28f1...781f`; the files in the tree hash to it, and it is the hash the scoring run printed | MEASURED | `python docs/studies/d2/score.py --freeze-hash`; `python docs/studies/d2/describe.py`, line D21 | a changed byte in any of the seven files |
| X3 | 35 launches have records and 557 requests were listed; 13 tags are on the constant-setting side, one of them 2021-082 with no record, and 23 are scored; there are 36 and 68 control times | MEASURED | `python docs/studies/d2/launches.py <catalogue> --check`; `python docs/studies/d2/describe.py`, line D20 | the catalogue file, by its hash |
| X4 | 557 requests from 13:25:03 to 13:33:35 local; 446 answered 200, 111 answered 404, none otherwise; 445 waveform files of 132,153,344 bytes; CI.GATR answered 200 to 28 of 139 and 404 to 111, and the other three stations 200 to all 139; a second run of the fetch made no request | MEASURED | `python docs/studies/d2/describe.py`, lines D1 to D3, from [manifest.tsv](d2/manifest.tsv); `python docs/studies/d2/fetch.py docs/studies/d2/requests.tsv <data> docs/studies/d2/manifest.tsv <scratch>/requests.log`, run at 13:34:48, which printed "557 requests in the list, 0 to make" | the manifest; the files' hashes |
| X5 | The constants: 10 at CI.GATR, not set from records; 95 at CI.LOC, 96 at CI.LCP, 130 at CI.SYN, from the twelve launches 2024-002 to 2024-065; and the table of section 5 | MEASURED | `python docs/studies/d2/setconstants.py <data>`, run three times before the freeze with the same output each time; `python docs/studies/d2/describe.py`, lines D7 and D8, from [constants.json](d2/constants.json); the ranges 46 to 196, 58 to 160 and 109 to 155 are in the first command's table | a rerun on the same files |
| X6 | The first table of section 8 and the headline under it, as the scoring run printed them | MEASURED | `python docs/studies/d2/score.py <data> --freeze dc7f28f172f8e201095a07a1a5b762a74407b4ca5c78d58a5d4b6815051f781f`, run once on 2026-11-23; its output is [scored-output.txt](d2/scored-output.txt) | the same rule on the same files in a copy of the tree without that output; the manifest's hashes hold the files |
| X7 | From the table of every window in that output: at CI.GATR 7 of 7 launch windows hit and 0 of 21 control windows; CI.LOC 23 of 23 and 0 of 68; CI.LCP 23 of 23 and 0 of 68; CI.SYN 20 of 23 and 0 of 68; with p of 8.45e-07, 4.74e-22, 4.74e-22 and 2.71e-17. Over the four, 73 of 76 launch windows hit | COMPUTED | `python docs/studies/d2/describe.py`, lines D10, which count the output's 548 rows again and take p again; 7 + 23 + 23 + 20 and 7 + 23 + 23 + 23 | a row of the output that disagrees with its table |
| X8 | The table of section 9; no wrong window hit, of 76; one window an hour early hit, of 76, at CI.LOC before launch 2024-171 with S = 113; of 377 control, wrong and hour-early windows with a record, one hit | COMPUTED | `python docs/studies/d2/describe.py`, lines D11, D16 and D17; 152 is 76 and 76 | the output's rows |
| X9 | Every window with no record in the scoring run is CI.GATR's, 16 launch windows and 47 control windows, each because no file came | COMPUTED | `python docs/studies/d2/describe.py`, lines D10 and D12 | the output's rows |
| X10 | Chosen after looking: the S of launch windows and the largest S of control windows at each station, CI.SYN's three misses, and the ranges of M of section 8 | COMPUTED | `python docs/studies/d2/describe.py`, lines D13, D14 and D15 | the output's rows; these were not fixed before the run |
| X11 | With 23 and 69 windows the smallest launch-hit count that rejects at 0.0025 is 5, 6, 7, 7 for 0 to 3 control hits; with 23 and 68, at 0.0025 and at 0.01 / 3: 5 and 4 for no control hit, 7 and 6 for two; with 7 and 21, 4 for no control hit | COMPUTED | `python docs/studies/d2/describe.py`, lines D24, D19 and D18; by hand for no control hit, 33,649 / 49,177,128 and 8,855 / 2,794,155 | arithmetic |
| X12 | The table of section 6; 13% for a launch seen one time in five with one control window in twenty hitting; with no effect a station's test rejects at most 0.0013 of the time at the three sizes, for chances from 0.05 to 0.5 | COMPUTED | `python docs/studies/d2/describe.py`, lines D22 and D23 | arithmetic; a simulation |
| X13 | The constant-setting script refused a scored launch on the real list, with the line quoted in section 9 | MEASURED | `python docs/studies/d2/setconstants.py <data> --tags 2024-002,2024-088`, 2026-11-23 | a rerun |
| X14 | This parcel's tests: 31, all passing; the gate's verdict at the last commit is in the commit's message | MEASURED | `python -m pytest -q -p no:cacheprovider tests/test_lch3_rule.py tests/test_lch3_refusal.py`; `bash verify/run.sh` | a rerun |
| X15 | 26 one-place changes to the three scripts, each in a copy: 25 failed a test, and the 26th, the name of the output file, failed none. A second scoring run in the real tree was refused, `REFUSED ALREADY-SCORED`, with exit 1, and the output's SHA-256 was `ce757028...3cd5ba` before and after | MEASURED | `python <scratch>/mutate.py <worktree> <scratch>/mutant-copy`, 2026-11-23, 13:51; its output is `<scratch>/mutate-out2.txt`, last line "25 of 26 caught". The script is not in the tree. The second run: the command of row X6, again, at 13:54 | a change it did not try |
| X16 | The latest CI.GATR window answered 404 starts 2024-11-14T04:11:20 and the earliest answered 200 starts 2024-11-16T06:02:20; its launch records that came are 2024-213, 2024-217, 2024-225, 2024-231, 2024-239, 2024-247 and 2024-251 | MEASURED | `python docs/studies/d2/describe.py`, lines D4 and D5 | the manifest |
| X17 | The station service lists CI.GATR's HHZ from 2017-06-29 to 2024-04-30 and from 2024-04-30 on; CI.LCP's from 2021-09-09, CI.LOC's from 2020-08-04, and CI.SYN's from 2014-09-30 to 2025-07-02 | MEASURED | the answer saved as `<data>/scedc-ci-hhz-2024-epochs.txt`, columns StartTime and EndTime; its request is the first row of [manifest.tsv](d2/manifest.tsv) | making the request again |
| X18 | The three SCEDC pages were read whole before any data request, and nothing on them limits who may use the data | READ | https://service.scedc.caltech.edu/, https://scedc.caltech.edu/about/citation.html and https://service.scedc.caltech.edu/fdsnws/dataselect/1/, fetched 2026-11-23 at 13:22 local into `<scratch>/pages` and read as text from first line to last; their requests are the first three lines of `<scratch>/requests.log` | the pages |
| X19 | D1b's onsets were 3 s and 2 s inside the window's opening at CI.LOC and CI.MPP; the catalogue lists 46 Falcon 9 launches from Vandenberg in 2024, 35 timed to the second | READ | D1b, section 5, the first table, rows CI.LOC (window 42 to 254, up from 45 s) and CI.MPP (222 to 513, up from 224 s); D1b, row Q6f | those rows |
| X20 | The four stations, D1's window, the control-time rule, three controls, the hit rule and its departure from D1, the rule that sets M and its floor of 10, the 90%, the level 0.01 over four, the controls' 0.01, the fifteen, and the split at twelve | DECISION | the design in the round's ledger, 2026-11-23 13:18 and 13:20, approved by the lead at 13:22, before any record of 2024 was fetched | the lead's ruling of that time |

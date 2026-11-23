# Round 1: the reference model, and the launch-data study - the work order (approved by Logan, 2026-11-23)

Drafted by the lead on 2026-11-21 and approved by Logan on 2026-11-23, when the round started. His word closes this document; question 6, the licence, he settled differently from the recommendation. This is the third draft. A verifier (VP1) read the first against its sources and the method and re-checked the second; it found every earlier wrong answer fixed, one new wrong answer and seven smaller gaps. Those eight are answered here and have not been back to it.

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. `<repos>` is the folder that holds this repository and its siblings.

## What binds it

- **The design:** `docs/studies/D0-rough-design.md`, approved by Logan on 2026-11-21.
- **Logan's answers to D0's six questions** (2026-11-21, in `docs/ROADMAP.md`): a known pulse in on-card white noise first, with a recorded seismic stream as stage E3; SystemVerilog, cocotb and the Vitis RTL kernel flow; phase A first (the host trains, the fabric swaps), then phase B in the fabric; the WSL environment, the box and daytime card windows allowed, the lead alone on the box and the card; cft-fp256's standing rules carried over; the setup committed.
- **Logan's words on real data** (2026-11-21, whole in `docs/ROADMAP.md`): "utilizing earthquake sensor data but correlating it with SpaceX (or any publicly available) launch times", with a station's position relative to the site giving "different 'levels' of signal to noise with known timestamps", and "I prefer to work with real data when able."
- **The standing rules** in `docs/ROADMAP.md`.
- **The send-back rule:** only a regression or a wrong answer sends work back. Everything else merges as a recorded known limit, and a sentence that claims more than is true is restated at the merge.
- **The lead's lessons,** each in every brief where it applies:
  1. A fact the lead puts in a brief is MEASURED or READ, and says which. In D0's round the lead wrote, unchecked, that an agent cannot message the lead while it runs. Row P4 shows it can.
  2. A figure quoted from a report is quoted with its definition and its conditions, from the report itself.
  3. "Recorded in X" is not written before X holds the record.
  4. Long scripts go in files. CR bytes are counted with Python, never with grep.
  5. A filed report says exactly what the lead changed in it.
  6. A MEASURED row names a command for every part of what it says. The first draft's row P2 cited a command that cannot print a commit id.
  7. A sentence about a whole list is checked against every item. The first draft said each question had three parts; three did not.

## What the round is for

Round 1 builds the authority: the reference model, the statistics that judge sensitivity, and the gates that hold both. It also measures whether Logan's launch-data idea can carry an experiment. The model work runs on the desktop's Python alone; the study also reads public web pages, if question 4 allows.

Each value statement names the measurement that would falsify it.

| # | the round is worth running if | basis | source or command | falsified by |
|---|---|---|---|---|
| V1 | the reference model, in its matched-filter configuration, reproduces D8's curve at the injected index within the tolerance of D9 plus the measured cost of quantisation | BELIEVED | D0 rows D8, D9 and D11 | the software run of stage E0 in wave 2 falling outside that tolerance |
| V2 | launch signals can be seen in public seismic records, at a predictable lag, at more than one distance | BELIEVED | no row below supports it: L1 is a research deployment, L2 an explosion, and L3 gives no distance. It is the thing LCH measures | LCH-2's own look at real records around a handful of launches |
| V3 | two reference-model parcels can build to one stream interface without meeting in one file, the gate registry apart | ESTIMATE | the file table below | a merge conflict between MOD-A and MOD-B outside `spec/` and the gate registry, or SEAM's interface test failing |

**D0's sixteen gates, and which this round builds.** Eleven, some on the model's side only: reference model, truth isolation, injection, swap, refusal, generated copies (the Python copy), overflow, replay, noise tails, scorer, statistics. Five wait for what they need: bit identity (RTL, a host library and the card), capability bits (a bitstream), learner (the learner rounds), comparison rules (the first experiment), provenance (the first build).

**Not in this round:** any RTL, the host library, the kernel build, the card, either learner. Round 2 is planned when this one closes. Row S1 of D0 (OpenTPU's state) stays a SURVEY row; nothing here depends on it.

## What is on hand

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| P1 | On the desktop's `python` 3.12.15: pytest 9.1.1 and numpy 2.2.6 are installed; scipy, obspy and hypothesis are not | MEASURED | an import of each, printing `__version__`, 2026-11-21; VP1 reran it | a rerun |
| P2 | The tree's HEAD and `origin/main` are the same commit, `d13281f`, and one file differs from it: `docs/ROADMAP.md`, with Logan's words of 2026-11-21 added | MEASURED | `git rev-parse --short HEAD`, `git ls-remote origin refs/heads/main` and `git status -sb`, 2026-11-21 | a rerun |
| P3 | The lead's Agent tool can start an agent in a git worktree of its own, on a named model. It has no setting for the branch that worktree is cut from | READ | the tool's own description, read by the lead and, of the same tool, by VP1; not exercised in this project | the first dispatch |
| P4 | A background agent can send the lead a message while it runs. It is queued for the lead's next turn | MEASURED | VP1's test message, sent at its start and logged in `ledger/lead.md` at 08:02 on 2026-11-21 | a later test message failing to arrive. The lead-to-running-agent direction is not shown |
| P5 | D0's section 9 names 16 gates | MEASURED | a count of that table's rows, 2026-11-21; VP1 recounted | a recount |
| L1 | A Falcon 9 launch at Vandenberg was recorded by nine three-component seismometers that researchers placed about 7 km from the pad; one more at about 15 km captured no discernible body-wave arrivals. The same source says earlier work found a Falcon 9's airwaves detectable beyond 10 km. Nothing in it says the recordings are public | BELIEVED | a search summary of arXiv 2502.01982, in [R1-search-2026-11-21.md](R1-search-2026-11-21.md); the paper was not opened | the paper; LCH's own records |
| L2 | In one study of a pad explosion, the seismic record was mainly air-coupled waves of 5 to 23 Hz | BELIEVED | a search summary of Thompson et al. 2017, same file | the paper |
| L3 | Southern California's seismic network detected a 2021 launch from Vandenberg, and its operators say the signal lacks distinct seismic phases | BELIEVED | a search summary of a Caltech network page, same file | the page; LCH's own records |
| L4 | The Falcon 9 flew 46 times from Vandenberg in 2024 | BELIEVED | a search summary of a news page, same file | a count from a launch catalogue |
| L5 | GCAT publishes launch lists as TSV under CC-BY, split into orbital launches, failures, suborbital flights and pad explosions, with a file of references for each launch time. Whether its times are to the second is not confirmed, and nothing says it lists scrubbed countdowns | BELIEVED | a search summary of planet4589.org pages, same file | the catalogue's own column descriptions |
| L6 | At 343 m/s sound takes 2.9 s per km: about 20 s to 7 km, 44 s to 15 km and 4.9 minutes to 100 km | COMPUTED | 1000 / 343, 7000 / 343, 15000 / 343 and 100000 / 343 / 60 | measured lags; wind and temperature move the real figure |
| L7 | A temporary network near Kennedy Space Center recorded several launches, and every one showed a Doppler shift in its seismic and infrasound spectrograms, lower frequencies arriving later | BELIEVED | a search summary of McNutt et al., AGU 2017, same file | the abstract; LCH's own spectrograms |

**What the searches did not find,** by their own summaries: any study of sonic booms recorded by seismometers, and anything on which public stations detect a Vandenberg launch or how far away.

## The launch-data idea, and where it sits

**What it gives that synthetic data cannot.** Labels from a public record that neither the model nor the project produced. A signal whose shape is not of our making, which answers the survey's warning about fitting to simulated shapes. A ladder of strength that geography sets.

**What it does not give for free.** Each of these is a way the experiment could pass while showing nothing, so each becomes a control that LCH must design:

1. **A launch time is not an arrival time.** If the energy travels as sound, a station's signal lags the launch by tens of seconds nearby and by minutes far off (L6), by an amount the weather changes. That it travels as sound is the lead's inference from L2, an explosion; L1's body waves at 7 km say some of it goes through the ground. The label is a window, and its width is something to measure.
2. **A launch is not a signal in every record.** At a far station the truth is "a launch happened", not "its signal is in this trace". Finding it there more often than in matched windows without a launch is the result.
3. **Launch times are not random.** A model can learn the hour, the season or the base's own activity. The control is windows at the same clock time on days without a launch. A scrubbed countdown would be a better one, a published time with nothing behind it, but no source here lists scrubs (L5); LCH looks for one.
4. **There is no known optimum.** Nothing like D8 says how well a detector should do, so this data cannot calibrate the instrument.
5. **It is not a pulse.** A launch lasts minutes (BELIEVED; no row here gives a duration), from a moving source, and at another site its spectrum slid in both seismic and infrasound records (L7, which is about Kennedy Space Center). D0's matched-filter configuration, one short known shape, does not fit it. The datapath's other configuration may: the filter bank as band filters, the rectifier, a long pooling stage, the head. What counts as a hit inside a window, and how false alarms are counted per window, are not defined anywhere yet.
6. **Distance is not the only thing that sets strength.** Station noise, instrument, ground, direction against the rocket's track, and wind all vary with the station. Without a noise measure per station the ladder is confounded.
7. **Other things happen in the window.** Earthquakes, other launches and the base's own activity. Control windows must exclude what a catalogue can name.
8. **One launch is seen at many stations.** Records are split into training and testing by launch and by time, never record by record, or the test set has already been seen.
9. **The sources are mostly the cases that worked.** Rows L1 to L7 are reports of signals found, though L1 also reports one sensor that caught no body waves. A station that recorded nothing is rarely written up.

**Where it sits.** D0's stage E3 is real noise replayed from HBM, with injections, so its labels still come from the injector. Launch-labelled records are a different thing: real events, with no injection. This plan proposes them as a new stage, E4, beside E3. Nothing in D0 changes unless Logan says so (question 1).

D0's first comparison rule fixes and hashes the injection set before a run. E4 has no injections, so its counterpart is the launch list, the stations and the window definitions, fixed and hashed before any record is scored. LCH writes that rule.

**What it would change early.** D0's row D1 proposes 16-bit samples on one channel. Seismic records have three components, and are wider than 16 bits (BELIEVED; LCH reads it from real station metadata). Question 2 asks that D1 stay unfixed in round 1.

## P0, the lead's, before any parcel

Every file each piece would touch:

| file or folder | P0 | MOD-A | MOD-B | STAT | LCH |
|---|---|---|---|---|---|
| `spec/`: the one definition, the reference pulses, the quantising rule | owns | reads | reads | reads | - |
| `model/__init__.py` and the package skeleton | owns | no edit | no edit | - | - |
| `model/` source, injector, truth modules | - | owns | - | - | - |
| `model/` detector, weights, scorer modules | - | - | owns | - | - |
| `stats/` | - | - | - | owns | - |
| `tests/test_<parcel>_*.py` | one test of its own | its own files | its own files | its own files | - |
| `vectors/<parcel>/`, frozen known answers, each folder with its own checksum list | the checksum generator | its own folder | its own folder | - | - |
| the gate registry, `tests/gates.toml` | creates it, with its own rows | adds its rows | adds its rows | adds its rows | - |
| `verify/run.sh`, `tools/`, `Makefile`, `.gitignore`, `.gitattributes` | owns | - | - | - | - |
| `docs/model/<parcel>.md` | - | its own file | its own file | its own file | - |
| `docs/studies/D1-launch-data.md`, `PROVENANCE.md` at the root | - | - | - | - | owns |
| README, CLAUDE.md, ROADMAP, VALIDATION | the lead's | no | no | no | no |

`spec/`, `tests/`, `vectors/`, `docs/model/` and the gate registry each appear in three or more columns. P0 makes the first four shared by construction, a file per parcel or a folder per parcel, so no two parcels edit one file. The registry is the one file several parcels add rows to. Two parcels adding rows will conflict in git, a row each, and V3 excepts it.

P0 delivers:

- **`spec/`**: one definition file (widths, channel count, shape maxima, the score, truth and event record formats, the stream interface between source and detector), the reference pulses as data, and the rule that turns a real coefficient into an integer one. A generator writes the Python constants, with `--check`. Round 2 adds the SystemVerilog and C outputs.
- **The package skeleton**, including `model/__init__.py`, which no parcel edits.
- **The gate registry**, `tests/gates.toml`: a row names a gate, its test and its negative control. P0 creates it with the rows for what P0 itself builds, and each parcel adds the rows for its own gates in the same commit as their tests, so the stage passes at every commit. By the round's close it holds the eleven gates this round builds. A stage walks it and fails by name in both directions: a row no test claims, and a test claiming a row that is not there. Proven with a dummy row.
- **New gate stages**, each with a negative control:
  - `generated`: the generated constants, and each folder's checksum list under `vectors/`, equal what their sources give; one edited constant, and one edited vector, must each fail.
  - `model-tests`: the test run, passing on its count line and not its exit code; a planted failing test must fail it, and a run that collected nothing is refused. P0 ships one test of its own so this holds from the start.
  - `independence`: `model/` runs with `stats/` blocked from import, and `stats/` with `model/` blocked; a planted cross-import must fail. **Its limit:** it sees an import. It does not see a copied file or a module loaded by path. Both sides read `spec/` by design: shared facts, not shared code.
  - `registry`: as above.
- **A rule for known answers:** a frozen vector's expected output is worked by hand on a small case, or produced by STAT's independent code, never by the model it then judges.

P0 lands on the round branch, not on `main`, and goes past a verifier there before any parcel that reads it is dispatched. It preserves behaviour: the gate passes before and after it. Size L, 4 h (ESTIMATE).

## The parcels, as waves

| wave | parcel | what (D0 section) | depends on | size, time box |
|---|---|---|---|---|
| 1 | **MOD-A** | The source and the injector in the reference model (sections 2, 4): a seeded integer noise generator, replay of a recorded stream, the injector, and truth records that go around the detector. **Design first:** the generator and its Gaussian method, how deep its tails hold (row D7), and how deep the tail test can go inside a stated run time. | P0 | L, 4 h |
| 1 | **MOD-B** | The whole detector core, the weight store and the scorer (sections 4, 5): the filter bank, the rectifier, the pooling stage and the dense head, with the matched-filter configuration as one setting; the swap defined per output sample with its epoch field; the threshold, histogram and event records; refusal, by name, of a shape or blob outside the contract, a non-zero reserved field, and a swap committed while one is pending. **Design first:** the swap's semantics, the arithmetic and width of every stage, and a pooling length long enough for a signal that lasts minutes (caution 5). | P0 | L, 4 h |
| 1 | **STAT** | The statistics (section 2): the source's own statement of D8 committed with its locator and date, which needs a public page to be read (question 4); a floating-point matched filter and injection-recovery count that imports nothing from `model/`, using the pulses and the quantising rule from `spec/`; the binomial tolerance of D9. numpy and the standard library only (row P1). | P0 | M, 3 h |
| 1 | **LCH** | The launch-data study, phase 1. **It fetches no data file.** If question 4 allows, it reads the pages behind rows L1 to L7 and commits what each says, as short attributed quotes with locator and date; lists the public seismic stations near each launch site with their distances and whether an infrasound channel sits beside them; reads the launch catalogue's fields and terms; designs the nine controls above and the hit criterion; and proposes the smallest download that would show a ladder, file by file with sizes, with the tools it needs. Then it stops. Output: `docs/studies/D1-launch-data.md` and `PROVENANCE.md`. | nothing | M, 3 h |
| 2 | **SEAM**, the lead's | The first seam tests: the injector feeding the detector core; truth isolation across the two; one pulse definition giving the same coefficients in `model/` and `stats/`; and the software run of stage E0 that decides V1. | MOD-A, MOD-B, STAT | M, 3 h |
| 2 | **LCH-2** | Phase 2, only if Logan approves LCH's list: fetch it, and measure whether the signal is there at a predictable lag, how its strength falls with distance, and what the controls show. No fetched file is committed. | LCH, Logan's word | M, 3 h |

**Named controls, in the briefs.** Each is built, run, seen to fail, and reported with its output.

- **MOD-A:** an injector that adds nothing, one a sample late, one with the sign flipped and one at half amplitude must each be caught. Two separate runs from one seed must give identical records, and a run with one seed bit changed must differ. A generator with clipped tails must fail the tail test, at the depth MOD-A's design states once the lead has approved that design.
- **MOD-B:** one flipped coefficient bit must change a score, on a stream and a configuration where that tap reaches the score unmasked. A swap to different weights that changes half the taps a sample late must be caught. A threshold off by one, and a histogram that drops its last bin, must each be caught. A core one bit narrower must overflow at the true extreme inputs, which the test derives from `spec/`. A model with one rounding changed must miss a frozen vector. A model that accepts a shape past its maximum, and one that refuses it under the wrong name, must each be caught.
- **STAT:** a detector with a coefficient set wrong by a stated margin must fall outside the tolerance. A planted import of `model/` must fail `independence`.
- **SEAM:** the same samples with different truth records must give identical output records, and a detector wired to read truth must be caught.
- **LCH:** its verifier's list carries planted claim-and-source pairs, some false, in the study's own format. That tests the verifier. The experiment's nine controls are LCH's design to write and LCH-2's to run.

**The lead's:** P0; the seam tests; every merge and the gate after it; the round branch; CLAUDE.md and ROADMAP; the docs sweep; any run of ten minutes or more; the close, with a verifier on it; the cost of the round.

**At best about three working days** (ESTIMATE; it rests on no measurement of this project's pace beyond D0's single document): P0 and its verifier, then wave 1, then wave 2 and the close. Send-backs stretch it.

## How the round is held

- **The plan's own check.** A verifier's pass, the lead's answers, and that verifier's re-check of them, before Logan is asked.
- **A round branch.** `r1` is cut from `main` first. P0 lands on `r1` and is verified there. Merges go onto `r1` one at a time with the gate after each, and an integration verifier makes each merge again from its parents. `main` moves to `r1`'s tip at the close, after the full gate and a verifier's pass on that tip.
- **Design first.** A parcel's design is its first report. The lead approves it or answers it, in the ledger, before the parcel builds. A design that would change D0 goes to Logan.
- **Worktrees.** By P3 the tool takes no branch. Where it cuts a worktree from is not in its description; the lead believes it is the lead's checkout, and keeps that checkout on `r1` at each dispatch. The check that follows catches a wrong base either way. Every brief names its base commit as "at or after", has the parcel check it, and has it run `git merge --ff-only` to the commit the dispatch message names, stopping if that refuses.
- **Parcels that build to one interface in parallel are trial-merged** in a throwaway tree before the first one merges: MOD-A with MOD-B.
- **The ledger** is `Data/runs/2026-11-21-r1-model/ledger/`. `Data/` is ignored by git, so no worktree contains it, and every brief gives its absolute path. One file per author, append only, times from `date`, rules in a README there. Agents read it at three moments: before starting, before designing anything that touches a shared file, and before reporting. The lead reads every author's file before each merge and at the wave boundary.
- **Escalation.** A question for the lead is written in the sender's own file, then sent to the lead by message (row P4). Each agent sends a test message when it starts, and the lead logs how each one arrived.
- **Every verifier's subject carries planted faults**, new for each pass, with the key in no file until its report is back.
- **Every brief carries:** a scope ceiling and a time box by the clock; "no helper agents"; the files it owns and the ones it may not touch, with the owner of each; the small edits outside its files that are expected (its rows in the gate registry); its base commit and the check above; the environment facts of rows P1 and P3; its named controls; what READY means; the regression it is most likely to cause; the stop line and what to measure before stopping; a scratch folder of its own; LF; long jobs in the foreground through the tool that reports their end, and a question to the lead before any run of ten minutes or more; delete only what you created; stop only your own processes, by process id; never type a commit id from memory; never the box, the card or WSL, which round 1 does not need; the seven lessons above. Its report says what it changed, shows the gate's and the controls' actual output, discloses any boundary it crossed, says "anything this brief got wrong", ends with what it did not do, and comes after its own background work is stopped.
- **Long runs.** The tail test and stage E0's software run may pass ten minutes in plain Python: VP1 timed one generator draw at about 0.26 s per million on this desktop (its own estimate). Their depth is set by a run-time budget in MOD-A's and SEAM's designs, and any run of ten minutes or more is the lead's, booked on the TimeSheet.
- **A public repository.** Parcels commit short, attributed quotations only, and no third-party data file. `PROVENANCE.md` names each source and its terms.
- **Downloads:** none without Logan's approval of each file. LCH proposes; it does not fetch.

## What this plan does not settle

- Round 2 and everything after it.
- Whether the launch signal is usable. Rows L1 to L7 are search summaries of pages nobody here has opened.
- The time boxes. All are estimates.
- Which launch sites. That Vandenberg has many public stations nearby is BELIEVED; L3 says only that the regional network detected one launch. Florida and Texas are for LCH to look at as well.
- Whether a seismometer's record or an infrasound sensor's is the better stream for this. LCH reports what each site has.

## Questions for Logan

Each has a recommendation, what it rests on, and what would show it wrong.

1. **Where real data sits.**
   - *Recommended:* stage E0 stays synthetic, as the instrument's calibration. Launch-labelled records become a new stage, E4, beside D0's E3, with LCH starting in wave 1. Whether stages E1 and E2 also run on real data is decided when LCH-2 reports.
   - *Rests on:* D8 is the only known optimum, so only synthetic data can show the instrument itself is right; and no one here has yet seen a launch in a seismic record.
   - *The alternative:* real data for every stage after E0, decided now. Stages E1 and E2 then wait for LCH-2.
   - *Shown wrong if:* LCH finds too few launches near enough to any public station, or LCH-2 finds no signal at a predictable lag.
2. **D0's row D1, the sample format.**
   - *Recommended:* it stays unfixed through round 1. P0 carries sample width and channel count as parameters of the one definition.
   - *Rests on:* a seismic stream needs three components and more than 16 bits (BELIEVED), and a parameter costs the reference model nothing.
   - *Shown wrong if:* you want the format fixed now, or LCH finds the public records are narrower than believed.
3. **Models.**
   - *Recommended:* the lead's own model for the authors of MOD-A, MOD-B, STAT and LCH, with Sonnet verifiers on them and on the lead's P0.
   - *Rests on:* these four define the authority everything later is held against. Your rule of 2026-10-12 for cft-fp256 put challenging work on the default model with Sonnet verifiers (READ, from that project's lead notes, which are not in its repository).
   - *The alternative:* Sonnet authors with Haiku verifiers, as cft-fp256's M4 round ran (READ, `<repos>/cft-fp256/Data/runs/2026-11-23-m3-round/plan.md`, its first question).
   - *Shown wrong if:* a verifier misses a planted fault, in which case the verifier's model changes first.
4. **Reading the web, and downloads.**
   - *Recommended:* LCH and STAT may read named public web pages. LCH may also query public station-metadata services, keeping the responses in the round's folder and committing none. No waveform, launch catalogue or package is fetched until you approve LCH's list; a seismic reader such as obspy, absent by row P1, is on that list.
   - *Rests on:* your rule that each download is approved, and on a page having to be opened before a BELIEVED row can become READ.
   - *Shown wrong if:* you count a page read or a metadata query as a download. Then LCH lists those first too, and STAT's D8 stays BELIEVED until you approve its source.
5. **Committing and pushing during the round.**
   - *Recommended:* a standing word for this round: the lead commits to `r1` as work is verified, moves `main` at the close, and pushes then, after the gate and a verifier's pass on the tip. Nothing else in round 1 reaches outside this machine.
   - *Rests on:* the gate and the verifier being the check, as in your other projects (READ, their lead notes).
   - *The alternative:* the lead asks before each push.
   - *Shown wrong if:* you want to see what goes public before it does.
6. **A licence for the public repository.**
   - *Recommended:* Apache-2.0, as cft-fp256 uses (READ, `<repos>/cft-fp256/README.md:442`).
   - *Rests on:* that project being the nearest in kind, hardware with its tooling.
   - *The alternative:* MIT, as HonestFramework and ParcelRound use; or none for now.
   - *Shown wrong if:* you would rather settle it once something is built.
7. **The start.**
   - *Recommended:* on your word, P0 first, with LCH dispatched beside it since it needs nothing from P0.
   - *Rests on:* nothing waits on this round, and LCH's answer shapes question 1.
   - *The alternative:* LCH alone first, and the model work once it reports.
   - *Shown wrong if:* you want the real-data question answered before any model is built.

## Logan's word (2026-11-23, verbatim)

> Go ahead and begin your work, you may create bookings using TimeSheet if you need any resources. Regarding the license, would MIT be a better fit? Apache was chosen for cft-fp256 since part of that project is a contract and Apache suits that better, but here may be different. I prefer the easiest option for others to reutilize the work if they desire to.

*The lead's reading:* the lead had asked whether he approved the plan with its seven recommendations, and this is his answer. The round starts. Questions 1 to 5 and 7 stand as recommended. The lead may book on the TimeSheet. On question 6 he asked whether MIT fits better and gave his test: the easiest option for others to reuse the work. By that test the answer is MIT, and the lead added an MIT licence on the round branch; the recommendation of Apache-2.0 is withdrawn. The standing word of question 5 is read from "go ahead", not from words about pushing, so the lead confirms with him before the push at the round's close.

## Notes after approval

Appended as the round runs. Nothing above is edited.

- **2026-11-23, row P3 is false here.** At the first dispatch the tool refused: "Cannot create agent worktree: not in a git repository". The lead makes each worktree by hand under `Data/worktrees/`, on a branch `parcel/<name>`, and an agent's shell starts in the lead's checkout. Every brief names its worktree's absolute path. The base-commit check in "How the round is held" stands.
- **2026-11-23, P0 also creates `stats/__init__.py`.** The file table gives `stats/` to STAT. The `independence` stage needs both packages to exist, so the skeleton holds both `__init__.py` files and STAT adds modules beside its own.
- **2026-11-23, the definition carries two profiles.** Question 2 left the sample format unfixed, so `spec/undertone.toml` names two formats, 16 bits on one channel and 24 bits on three, and code takes one by name. The second is a guess at a seismic record until LCH reports.

## What the round found, against its value statements (2026-11-23, the lead's)

Each row of "What the round is for" named the measurement that would falsify it. Each was made. The detail, with what was not done, is in [VALIDATION.md](../VALIDATION.md) under 2026-11-23.

- **V1 held.** The reference model, as a matched filter for the reference pulse, was run through its own noise, injector and core at five amplitudes, 200,000 injections each. Its efficiency was within the statistics package's tolerance of D8's figure at every one (the largest deviation 1.33 standard errors), noise alone crossed at the stated rate, and the cost of quantisation measured on the same streams was no injection in a million. One pulse, one noise level, one profile.
- **V2 is supported for one launch and not settled.** One launch that had already been written up is seen, by the rule fixed before the data was fetched, at three stations, 16.5, 49.9 and 78.5 km from the pad, on the launch day and on neither of two control days. At a fourth, 32.6 km, the launch-day figure is as large, and the rule reads "cannot tell" because one control day has a ten-second stretch in the window. (An earlier wording of this note said "plain at four stations ... by a measure fixed before the data was fetched"; the round's closing verifier found that it claimed the fourth for the rule.) The lag's measure was chosen after looking. One launch cannot say how often a launch is seen.
- **V3 held, for three parcels and not two.** MOD-A, MOD-B and STAT built to one interface without seeing one another's code. The first of their three merges was clean; the second and third each conflicted in one file, the gate registry, where each parcel appended its rows. At the seam, the integer core and the floating-point matched filter gave every score equal on one stream under both profiles.

Where the plan was wrong, beside its earlier notes: the gate does not run in seconds once the model's tests are in it, it takes about 75; the time boxes were far too long, as every parcel finished in well under half its box (the model parcels in 57 to 74 minutes of three or four hours); and LCH-2 ran inside round 1, under Logan's word of 2026-11-23 on downloads, where the plan had it waiting for his approval of each file.

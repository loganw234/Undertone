# Roadmap

The lead's file. It holds Logan's decisions as he gave them, the plan of record, and how rounds are held. A parcel does not edit it.

## Where the project stands (2026-11-23)

- **Design:** [D0, the rough design](studies/D0-rough-design.md), approved by Logan on 2026-11-21 with all six of its questions answered as recommended.
- **Plan of record:** [round 2, the fabric in simulation and the learner](plans/R2-fabric-in-simulation-and-the-learner.md), approved by Logan on 2026-11-23 with one change, and running on the local branch `r2`. Before it: [round 1, the reference model and the launch-data study](plans/R1-reference-model.md), approved by Logan on 2026-11-23. Its work was done and verified on the branch `r1`, and `main` was moved to `r1`'s tip and pushed on Logan's word of 2026-11-23.
- **Licence:** MIT, by Logan's test of 2026-11-23: the easiest option for others to reuse the work.
- **Built, in software only:** the reference model (`model/`), the statistics that judge sensitivity (`stats/`), and round 1's eleven gates of D0, none of which needs hardware. As a matched filter the model reproduces the textbook curve at five amplitudes. **Nothing of the system is built on a card**: there is RTL in simulation (below), no host library, and nothing placed, timed or on the card. Of D0's sixteen gates, thirteen have a row in the registry (`tests/gates.toml`): round 1's eleven; the comparison rules, held since round 2's learner on stage E1 in software; and bit identity, of whose three parts the first is held, RTL in simulation. Three have no row: capability bits and provenance, which are about a bitstream, and the learner, which is about weights updated in the fabric.
- **Round 2, so far, on the local branch `r2` and not pushed:** the foundation for RTL. A simulation image of this project's own; a second size of the gate, `bash verify/run.sh --with rtl`; the definition generated as a SystemVerilog package and a C header beside the Python constants; a harness that holds RTL against the model on every score record; and a filter of one tap, written to prove that harness, which is not part of the detector. The register map is whole in the definition: three blocks, fifty-two registers, and three refusal names that are the fabric's alone. How it works is [rtl/README.md](rtl/README.md).
- **The first RTL, in simulation only (2026-11-23, on `r2`, not pushed):** a noise source and an injector ([rtl/source.md](rtl/source.md)), the detector core with its weight store and the head's hidden layer ([rtl/core.md](rtl/core.md)), and the three wired together ([rtl/seam.md](rtl/seam.md)). Each is held against the reference model word for word under both sample formats, each went past verifiers of its own (the core's last commit, and a mutant of the seam's that the lead re-pointed at its merge, past the round's closing verifier only), and none needed the model changed. Through the chain: every score word is the model's own run; the same samples under other truth records give the same scores; a weight swap lands at its named index; and weights the learner trained are written into the RTL and take effect at the index named. **It is bit identity in a simulator. Nothing is placed, timed or on the card, there is no host library, and no efficiency was read from any of it.**
- **Stage E1 in software (2026-11-23, on `r2`, not pushed):** a learner that starts blank ([model/lrn-a.md](model/lrn-a.md)) reaches the matched filter's efficiency. The model named before any run, 16,384 truth records: 49,492 of 100,000 held-out injections, 0.4949 against 0.5003, inside the tolerance; the curve over six counts is in [studies/E1-software.md](studies/E1-software.md). **It is a sensitivity result in software, with one seed a count, and says nothing about fabric.**
- **The head has a hidden layer, in the model** (2026-11-23): up to twelve units, as a second version of the configuration blob; a blob without one is unchanged. It passed the four-part test the plan fixed for "simple enough" and two verifiers. It is not trained. **What it costs in fabric is measured in part, and is more than the test's count suggested**: one multiplier of each of the head's shapes takes 3 or 4 DSP slices where the test counted 1, which makes a head of twelve units about 624 or 816 slices by arithmetic, against 48 or 64 for round 1's head and 5,952 on the card. **The head was then synthesised, out of context, as Logan asked: 624 and 816 slices, as the arithmetic said**, which is three to four tenths of the filter bank's slices where the count of multipliers made it one tenth, and about a tenth to a seventh of the card's ([studies/SYN-head.md](studies/SYN-head.md)). It is a thing for Logan to weigh.
- **The launch experiment, [study D2](studies/D2-launch-experiment.md) (2026-11-23):** by a rule frozen before any scored record was opened, 23 Falcon 9 launches of 2024 were seen at the three nearest stations with full records in 66 of 69 launch windows, against none of 204 control windows; a fourth station has records for seven and hit at all seven. A verifier's own scorer agrees on every one of 548 windows. **Within 50 km the launch is loud, not faint**: this shows the source can label a loud event near the pad, and says nothing yet of a faint one farther out, which is what the project wants a label for.
- **Looked at, once:** one rocket launch in public seismic records. By the rule fixed before the data was fetched it is seen at three stations, 16.5, 49.9 and 78.5 km from the pad, and not at 181 or 275 km. At a fourth, 32.6 km, the launch-day figure is as large as at the others, and the rule reads "cannot tell" because one control day has a ten-second stretch in the window. One launch and two control days; not a rate. [D1b](studies/D1b-first-look.md).
- **Committed and pushed:** the setup, under Logan's word of 2026-11-21, up to `d13281f`; and round 1, under his word of 2026-11-23 at its close ("1. Push"). The remote is the public repository `loganw234/Undertone` on GitHub.

### Open with Logan at round 2's close (2026-11-23)

Round 2 is on the local branch `r2`. **Nothing of it is pushed and `main` has not moved: by his word on the plan, the lead asks him first.** What the round leaves for him:

1. **Whether `main` moves to `r2` and is pushed.**
2. **What the head costs**, now measured: 624 DSP slices under 16-bit samples and 816 under 24-bit, at twelve hidden units, of the card's 5,952. The test for "simple enough" passed on a count of multipliers, which put the head at a tenth of the filter bank; in slices it is three to four tenths. The ways down, each measured or worked in [studies/SYN-head.md](studies/SYN-head.md): fewer hidden units (four is 208 and 272); a smaller bound on the pool or the taps, which narrows the head's multipliers and changes the model's definition; or the head as it is.
3. **The lead's decisions in the round, each his to overturn**: three refusal names that the fabric raises and the model never does, and two bounds the fabric has and the model does not (a noise table of 32,767 entries, 1,024 pending truth records); the core's refusal of a shadow weight write while frames of the old weight set are still in its pipeline, ruled a stated limit and not a finding against the model; the learner's trainer in exact integer arithmetic, where D0 says the host "trains in floating point"; two refusal mutants a module in the RTL benches, in place of two a refusal name; the seam made a parcel where the plan gave it to the lead, and built on the two RTL parcels before either was verified; the seam's document corrected by the lead at the merge and not sent back; the verifier passes on the detector core ended after the third, with one last stream left to the round's closing verifier; and, at the close, **what that verifier then found left as a stated limit and not closed with tests**: two more faults in the core's overflow flag that every bench passes, the RTL right in both (limit 23 of [rtl/core.md](rtl/core.md)).
4. **Which sample format the first build takes.** Still open from round 1: the RTL takes it as a parameter and every bench runs under both.
5. **Raspberry Shake's licence.** Held, by his word.
6. **For the next round's plan**: the launches seen so far are loud, not faint, within 50 km; the gate's second size is past ten minutes and its runner runs one bench at a time; nothing bounds a single test in simulation; four verifier passes on the detector core each found one more fault in its overflow flag that the bench let through, the last of them two, which asks for a test of the flag over all its sources and both directions at once and not another point test (the closing verifier's two streams are kept in the round's folder); the gate is green, without a word, on a long run's record of an earlier definition; the simulator's warnings are read by no one; there is no host library and nothing on the card.

### Open with Logan (2026-11-23, after his answers at the round's close)

His answers are below, verbatim, under "Logan's words, as given". What they leave open:

1. **What round 2 is: answered.** He approved the plan on 2026-11-23 with one change (his words are below). He asked for it that day ("Yes draft the plan"). The draft is [plans/R2-fabric-in-simulation-and-the-learner.md](plans/R2-fabric-in-simulation-and-the-learner.md); it recommends two tracks, the fabric in simulation and the learner in software, and ends with six questions for him. A seventh, how the RTL simulators are provided, he answered while the draft was being checked: a Docker image of this project's own. Nothing of round 2 has started.
2. **Whether a hidden layer is "simple enough".** His word: "Hidden layer from the start if simple enough, otherwise without for the initial design." The draft proposes a four-part test for it, fixed before the design is drawn, and asks him whether that test is the one he means (its question 2). **Answered by the test, 2026-11-23:** he approved the four-part test with the plan; all four parts held, and the hidden layer is in the model. What is open with him now is its cost in fabric, measured in part that day: see "Where the project stands".
3. **Which sample format the RTL takes.** His word on D0's row D1 was "Proposed is approved", which the lead reads as 16-bit samples on one channel, to start. The draft asks it as its question 3, and recommends RTL that takes the format as a parameter.
4. **Raspberry Shake's licence.** Held, by his word.

Settled by those answers: the push of round 1; the package index's terms.

## Logan's words, as given

Kept verbatim, with their dates. The lead's reading follows each, marked as the lead's.

**2026-11-21, the opening message:**

> I'd like to start researching into various approaches utilizing FPGA for ML, OpenTPU is the current system our work will likely be based on or build off of, however Im more interested in allowing the weights to be adaptable while retaining the speed of FPGA fabric and memory (We have a U50 to utilize), since memory is limited to 8gb and traditional LLM inference isnt particularly interesting I'd like to try a high speed low latency model of some sort, perhaps realtime signals analysis? The adaptive portion of the experiment would be seeing if the model could learn to recognize faint signals or otherwise 'missed events'
>
> Go ahead with some research on the topic to see current works

*The lead's reading:* the goal is adaptable weights at fabric speed on the U50; signal analysis is a suggestion, not a requirement; OpenTPU is a likely starting point, not a fixed one.

**2026-11-21, after the survey:**

> *A few small notes/corrections:
> The card is running on a different machine running linux, proven working along with the needed tooling versions to build for it (see cft-fp256 project)
> My card also lacks the network port, so communication has to go over the PCIE link.
>
> Would a different subject work better for this system? Ideally it would be designed to work on any given input with a properly configured model to start. But a 'easy' target might be better for a start

*The lead's reading:* PCIe is the only data path, so the source is replay from HBM or generation on the card. Two design goals: an input-agnostic core, and an easy first target.

**2026-11-21, on method:**

> Before we begin, look at 'HonestFramework' and 'ParcelRound', they are how I prefer to work with AI on projects, for a project reference cft-fp256 utilizes both. Once you finish reading on both methods set up the project in their fashion and draft the rough design

*The lead's reading:* both methods bind this project from its first file. The lead read HonestFramework at `65447fd` and ParcelRound at `origin/main` `f42242e` (its local checkout is behind; see [CLAUDE.md](../CLAUDE.md)).

**2026-11-21, on the design D0:**

> I've reviewed it, all are approved with the recommendations and you may create a remote with gh and push AOTPU was intended to stand for 'Adaptable OpenTPU', however I was unaware how outdated it had become by this point. So if you have name suggestions which better align with my typical naming I'd be open to them

*The lead's reading:* each of D0's six questions is answered with its recommended option:

1. the first target is a known pulse in on-card white noise, with a recorded seismic stream as stage E3;
2. SystemVerilog with cocotb benches and the Vitis RTL kernel flow;
3. phase A first (the host trains, the fabric swaps), then phase B in the fabric;
4. this project may simulate in `cft2204`, build on `amd-arc-box` and book daytime card windows through the TimeSheet, with only the lead touching the box and the card;
5. the standing rules below carry over;
6. the lead commits the setup.

Beyond the six: the lead may create a remote with `gh` and push. The name was meant as "Adaptable OpenTPU", and he is open to another.

**2026-11-21, on the name and the remote** (by the question dialog, verbatim):

- Which name should the project take on GitHub and in its documents? "Undertone"
- Should the new GitHub repository be private or public? "Public"

*The lead's reading:* the project is Undertone from this date. The lead had recommended another name and a private repository; he chose otherwise on both. The local folder keeps its old name until he renames it.

**2026-11-21, asking for the plan, and on real data:**

> Sure, draft the plan. One concept I had regarding 'training' is utilizing earthquake sensor data but correlating it with SpaceX (or any publicly available) launch times, we can utilize the sensor stations position in relation to the SpaceX site to have different 'levels' of signal to noise with known timestamps. It would also help prevent our fake data from being 'too fitted' for the purpose. I prefer to work with real data when able.

*The lead's reading:* draft the plan for the first round. A proposal for the real-data stage: seismic records labelled by public launch times, with a station's distance from the launch site as the ladder of signal strength. A standing preference: real data where it can be had. The plan takes this up as a study parcel and as a question back to him; it changes nothing in D0 until he answers.

**2026-11-23, starting round 1, and on the licence:**

> Go ahead and begin your work, you may create bookings using TimeSheet if you need any resources. Regarding the license, would MIT be a better fit? Apache was chosen for cft-fp256 since part of that project is a contract and Apache suits that better, but here may be different. I prefer the easiest option for others to reutilize the work if they desire to.

*The lead's reading:* the round starts, with the plan's questions 1 to 5 and 7 as recommended; bookings on the TimeSheet are allowed; the licence is MIT. The lead's fuller reading closes the plan of record. Because the word to push is read from "go ahead", the lead asks again before the push at the round's close.

**2026-11-23, on data services, downloads and two services' terms.** The lead had told him that a study agent queried two station-metadata services before reading that using them accepts their terms, that rows from both were being held out of committed files, and that the study proposed a download for his approval.

> If a public data service exists to query it may to determine if it would be useful here. Downloads are also permitted. Allow EarthScope and I'll look into Raspberry Shake

*The lead's reading:*

1. An agent of this project may query a public data service to find out whether it would be useful.
2. Downloads are permitted. The lead reads this as covering what this project's work needs, the launch-data study's proposed download first: not as leave to fetch anything unrelated to it. It replaces, for this project, the rule carried from cft-fp256 that each file be approved.
3. EarthScope's service may be used, and rows from it committed, with the acknowledgement its terms ask for.
4. Raspberry Shake stays held until he has looked: no request to it, and no row from it in a committed file.

**2026-11-23, at the close of round 1.** The lead had put six things to him: the push; the detector's head, which is one linear layer with no bias where D0 says "a small dense head"; D0's row D1, 16-bit samples on one channel, beside real records of three components of which two files in 25 need 17 bits; a package index whose terms exclude a person on a sanctions list; Raspberry Shake; and what round 2 is. He answered the first five, by number:

> 1. Push
> 2. Hidden layer from the start if simple enough, otherwise without for the initial design.
> 3. Proposed is approved
> 4. I don't believe I'm on a sanctions list so should be good there.
> 5. Stays held for now.

*The lead's reading:*

1. `main` moves to `r1`'s tip and is pushed. This is his word for round 1's push, not a standing word for later ones.
2. The detector's head gets a hidden layer if that is simple enough, and stays one linear layer for the initial design if it is not. He did not say who judges "simple enough". The lead takes it as a question for round 2's plan to answer with a measurement, at a design stop, before any RTL is written: what a hidden layer costs in the model (the datapath, the blob's version, every width after the pool) and in the fabric (multipliers and bits), set beside what one layer costs. Until that is answered the model is as it is.
3. Row D1 of D0 is approved as proposed: 16-bit signed samples on one channel, to start. That is the lead's reading of four words, and there is another: that the wider, three-channel format the lead had described beside it is what he approves. The model runs under both formats and nothing built is tied to either, so the two readings part only when the first RTL target is chosen. The lead asks him then.
4. The package index may be used. Its terms exclude a person on a sanctions list, and he does not believe he is on one. Installs still go into a virtual environment, with the shared cache off.
5. Raspberry Shake stays held: no request to it, and no row from it in a committed file.

The sixth, what round 2 is, he did not answer then. Asked next whether the lead should draft the plan, he said, the same day:

> Yes draft the plan

*The lead's reading:* draft it, for his approval, as with round 1. It is not leave to start round 2, to commit beyond the draft's own branch, or to push.

**2026-11-23, on Docker.** The lead had told him that the WSL environment has no RTL simulator installed, that the sibling project runs its benches in a Docker image, and that the draft asked whether this project should have an image of its own.

> You may install anything needed to the docker environment, or create a new one for this project if needed

*The lead's reading:* a Docker image of this project's own may be created, and what the work needs installed in it. The lead takes the new image and leaves the sibling project's as it is. It answers that one question of the draft. It is not approval of round 2, and no image is built before the round is approved; the lead ran one throwaway container of the base image already on the desktop, to read which versions it offers.

**2026-11-23, approving round 2's plan.** The lead had put the draft's six questions to him, each with a recommendation: which round; the four-part test for "simple enough"; the sample format for the RTL; whether the launch experiment is in this round; whether anything runs on the box; and the push at the close.

> Approved with recommendations except 5 do a synthesis to measure real cost

*The lead's reading:* round 2 starts. Questions 1, 2, 3, 4 and 6 are answered as recommended: both tracks; the test as written; RTL that takes the sample format as a parameter; the launch experiment in this round; and the lead asks again before `main` moves and anything is pushed. Question 5 he answered with its alternative: after the detector core's RTL is READY, the lead makes one synthesis of the head alone on the box, booked on the TimeSheet, to measure what it costs. The plan's notes after approval say what that piece is, its control and its limits. His word is not leave to push.

## Standing rules

**Carried over by Logan's word of 2026-11-21** (question 5 of D0). These are rules he set for cft-fp256, read that day from that project's lead notes, which are not in its repository.

- Delete only what you created in this run.
- Stop only processes you started yourself, by process id, never by a name pattern. Other sessions run on this desktop.
- Agents never touch `amd-arc-box` or the card. The lead runs that work.
- Agents test what they can quickly, hand long runs back to the lead, and ask before any run longer than ten minutes.
- No personal path in a committed line. Here this is a gate: the `paths` stage of `verify/run.sh`.
- This file and CLAUDE.md are the lead's.
- No real keys. No git or system configuration changes by agents.
- **Downloads are permitted, by Logan's word of 2026-11-23** (above), where cft-fp256's rule asked approval for each file. The lead's practice under it: each fetched file is logged with its source, its size and its hash; no fetched file is committed; a service's terms are read before its first request; and a service whose terms limit who may use its data waits for Logan.
- Every brief carries a scope ceiling, a time box by the clock, and "no helper agents".
- Long jobs run through the tool that reports their end, never as a detached background process.
- Each agent gets a scratch folder of its own and writes nothing outside it and its deliverables. Line endings are LF.
- Never type a commit id from memory.
- Only a regression or a wrong answer sends work back. Everything else merges as a recorded known limit, and a sentence that claims more than is true is restated at the merge.
- Runs of ten minutes or more on shared hardware are booked through the TimeSheet, with the mode stated.

## How a round is held

- A round's folder is `Data/runs/<date>-<name>/`, with `plan.md`, `briefs/`, `ledger/` and `reports/`. `Data/` is ignored by git and kept on disk, as in cft-fp256.
- The ledger is one file per author, append only, with each heading's time taken from `date`. An agent's final message is its report, and the lead files it under `reports/`.
- The lead's own work goes past a verifier like a parcel's. A verifier reports and fixes nothing, and "found nothing" is an acceptable answer.
- Durable findings are folded into [VALIDATION.md](VALIDATION.md) when the round closes.

## Rounds

| round | what | state |
|---|---|---|
| `2026-11-23-r2` | round 2: the fabric in simulation, the learner, the head, the launch experiment | run on 2026-11-23, on the local branch `r2`: six parcels merged (HEAD, LCH-3, LRN-A, RTL-A, RTL-B, SEAM-2) and the lead's foundation, each past verifiers on sealed clones with planted faults, **but for the detector core's last commit, a mutant of the seam's that the lead re-pointed, and the lead's closing documents, which only the round's closing verifier read**: it found wrong statements in the documents, corrected since, and two more faults the core's bench lets through, left as a stated limit; a narrow pass on those corrections found five more slips in them, corrected in the round's last commit, which no verifier has read; stage E1's full run in software and the head's synthesis, both the lead's. **Not pushed: the lead asks Logan before `main` moves.** The record is in [VALIDATION.md](VALIDATION.md) |
| `2026-11-23-r2-plan` | the draft plan for round 2, and a verifier's three passes over its three drafts | drafted 2026-11-23 on the local branch `r2-plan`; approved by Logan on 2026-11-23 with one change; not pushed. The record is in [VALIDATION.md](VALIDATION.md) |
| `2026-11-21-r1-model` | round 1: the reference model, the statistics, and the launch-data study | run on 2026-11-23, on `r1`: five merges of four parcels (LCH twice, MOD-A, MOD-B, STAT), each past a verifier of its own before it merged, and the lead's two pieces, the foundation and the seam, each past a verifier too; pushed on Logan's word of 2026-11-23. The record is in [VALIDATION.md](VALIDATION.md) |
| `2026-11-21-d0-design` | the rough design D0, a verifier pass over it and one re-check | approved by Logan on 2026-11-21; the record is in [VALIDATION.md](VALIDATION.md) |

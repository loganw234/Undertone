# Roadmap

The lead's file. It holds Logan's decisions as he gave them, the plan of record, and how rounds are held. A parcel does not edit it.

## Where the project stands (2026-11-23)

- **Design:** [D0, the rough design](studies/D0-rough-design.md), approved by Logan on 2026-11-21 with all six of its questions answered as recommended.
- **Plan of record:** [round 1, the reference model and the launch-data study](plans/R1-reference-model.md), approved by Logan on 2026-11-23. Its work is done on the branch `r1`, which is local; what remains is its closing verifier's pass and Logan's word before `main` moves.
- **Licence:** MIT, by Logan's test of 2026-11-23: the easiest option for others to reuse the work.
- **Built, in software only:** the reference model (`model/`), the statistics that judge sensitivity (`stats/`), and the eleven gates of D0 that need no hardware. As a matched filter the model reproduces the textbook curve at five amplitudes. **Nothing of the system is built**: no RTL, no host library, nothing on the card. Five of D0's sixteen gates wait for those.
- **Looked at, once:** one rocket launch in public seismic records, plain at four stations out to 78.5 km and absent on two control days. One launch; not a rate. [D1b](studies/D1b-first-look.md).
- **Committed and pushed** under Logan's word of 2026-11-21 (question 6 of D0, and his leave to create a remote): the setup, up to `d13281f`. The remote is the public repository `loganw234/Undertone` on GitHub. **Nothing of round 1 is pushed.**

### Open with Logan (2026-11-23)

Each is his to decide. None blocked the round.

1. **The push.** `main` moves to `r1`'s tip, and is pushed, only on his word. The lead asks at the round's close.
2. **The detector's head.** D0 says "a small dense head"; the model's is one linear layer with no bias, which cannot represent a detector that needs a hidden layer. Accepted by the lead for round 1 as a stated limit.
3. **D0's row D1, 16-bit samples on one channel.** The real records are three components, and two of 25 files hold samples that need 17 bits. The model already runs under a 24-bit, three-channel profile.
4. **A package index's terms.** They exclude a person on a sanctions list. A parcel installed nine packages from it, into a virtual environment, before that was put to him.
5. **Raspberry Shake's licence**, which he said he would look into. Held: no request, and no row of its data in any committed file.
6. **What round 2 is.** The plan of record ends with round 1.

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
| `2026-11-21-r1-model` | round 1: the reference model, the statistics, and the launch-data study | run on 2026-11-23, on `r1`: six parcels merged, each past a verifier; the closing pass and the push are open. The record is in [VALIDATION.md](VALIDATION.md) |
| `2026-11-21-d0-design` | the rough design D0, a verifier pass over it and one re-check | approved by Logan on 2026-11-21; the record is in [VALIDATION.md](VALIDATION.md) |

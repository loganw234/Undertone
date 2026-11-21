# Roadmap

The lead's file. It holds Logan's decisions as he gave them, the plan of record, and how rounds are held. A parcel does not edit it.

## Where the project stands (2026-11-21)

- **Design:** [D0, the rough design](studies/D0-rough-design.md), approved by Logan on 2026-11-21 with all six of its questions answered as recommended.
- **Plan of record: none yet.** The next step is the lead's: a plan for the first round, built from D0's section 10, past a verifier, and then to Logan.
- **Built:** nothing of the system. The repository holds the survey, the draft, and the front door (`bash verify/run.sh`).
- **Committed and pushed** under Logan's word of 2026-11-21 (question 6 of D0, and his leave to create a remote). The remote is the public repository `loganw234/Undertone` on GitHub.

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

## Standing rules

**Carried over by Logan's word of 2026-11-21** (question 5 of D0). These are rules he set for cft-fp256, read that day from that project's lead notes, which are not in its repository.

- Delete only what you created in this run.
- Stop only processes you started yourself, by process id, never by a name pattern. Other sessions run on this desktop.
- Agents never touch `amd-arc-box` or the card. The lead runs that work.
- Agents test what they can quickly, hand long runs back to the lead, and ask before any run longer than ten minutes.
- No personal path in a committed line. Here this is a gate: the `paths` stage of `verify/run.sh`.
- This file and CLAUDE.md are the lead's.
- No real keys. No git or system configuration changes by agents. Downloads need approval for each file.
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
| `2026-11-21-d0-design` | the rough design D0, a verifier pass over it and one re-check | the draft awaits Logan's answers; the record is in [VALIDATION.md](VALIDATION.md) |

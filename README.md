# Undertone

A research project: a small machine-learning model in FPGA fabric whose weights stay adaptable while it runs, on one AMD Alveo U50, tested on whether it can learn to find faint signals it previously missed.

The name is the thing it listens for: a faint signal under the noise. The project began as AOTPU, "Adaptable OpenTPU"; the survey found OpenTPU long unmaintained, and the owner renamed it on 2026-11-21. The first round's records keep the old name.

**Status, 2026-11-21: nothing of the system is built.** This repository holds a literature survey, a rough design the owner has approved, and the checks that hold the documents to their own rules.

## Does it still hold?

    bash verify/run.sh        # every stage with its negative controls; seconds; no cache
    make verify               # the same

Four checks run today, each with a control that plants a list of faults and must see every one reported: relative links resolve, no committable file carries a personal path, every row of a claims register names its basis, and no text file carries a CR byte. `bash verify/run.sh --list` shows the stages.

## The authority

**When two parts of this project disagree, the reference model is right.** It is a plain Python, integer-only model of the detector, the noise generator, the injector, the weight swap and the learner. The RTL, the host library and the card are held against it bit for bit, and anything the fabric cannot do exactly is refused by name.

It does not exist yet. [D0](docs/studies/D0-rough-design.md), section 2, defines it and says what it does not cover: detection performance is a statistical question with two authorities of its own.

## What is here

| | |
|---|---|
| [docs/studies/D0-rough-design.md](docs/studies/D0-rough-design.md) | The rough design, approved 2026-11-21. The owner's answers to its six questions close it. |
| [docs/ROADMAP.md](docs/ROADMAP.md) | The owner's decisions in his words, the plan of record, and how rounds are held. |
| [docs/VALIDATION.md](docs/VALIDATION.md) | The append-only ledger: what ran, when, and what it does and does not show. |
| [CLAUDE.md](CLAUDE.md) | Notes for an agent working here: the front door and what has already bitten. |
| [reports/](reports/Adaptive%20FPGA%20ML%20for%20signal%20detection.md) | The literature survey of 2026-11-21. Uncontrolled: read it as leads, not evidence. |
| `research_notes/` | The notes behind that survey. |
| `verify/run.sh`, `tools/check_tree.py` | The gate runner and its checks. |

## How the work is held

Under two methods of the owner's: HonestFramework (no claim rests on an agent's judgement) and ParcelRound (splitting work across agents without losing the seams). Both are sibling repositories of this one.

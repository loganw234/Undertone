# Undertone

A research project: a small machine-learning model in FPGA fabric whose weights stay adaptable while it runs, on one AMD Alveo U50, tested on whether it can learn to find faint signals it previously missed.

The name is the thing it listens for: a faint signal under the noise. The project began as AOTPU, "Adaptable OpenTPU"; the survey found OpenTPU long unmaintained, and the owner renamed it on 2026-11-21. The first round's records keep the old name.

**Status, 2026-11-23: round 1 is running, and nothing of the system is built yet.** This repository holds a literature survey, an approved design, the plan for round 1, the first piece of that round (one definition of the shared facts, and the skeleton of the reference model), and the checks that hold all of it.

## Does it still hold?

    bash verify/run.sh        # every stage with its negative controls; seconds; no cache
    make verify               # the same

Eight checks run today, each with a control that plants a list of faults and must see every one reported. Four hold the documents: relative links resolve, no committable file carries a personal path, every row of a claims register names its basis, no text file carries a CR byte. Four hold the build: generated copies equal the one definition, the tests pass, the model and the statistics import nothing from each other, and every gate has a test and a negative control that carry its name. The last two are held as far as an import and a name can show; `tools/check_build.py` states what they cannot see. `bash verify/run.sh --list` shows the stages.

## The authority

**When two parts of this project disagree, the reference model is right.** It is a plain Python, integer-only model of the detector, the noise generator, the injector, the weight swap and the learner. The RTL, the host library and the card are held against it bit for bit, and anything the fabric cannot do exactly is refused by name.

Round 1 is writing it; only its skeleton exists. [D0](docs/studies/D0-rough-design.md), section 2, defines it and says what it does not cover: detection performance is a statistical question with two authorities of its own.

## What is here

| | |
|---|---|
| [docs/studies/D0-rough-design.md](docs/studies/D0-rough-design.md) | The rough design, approved 2026-11-21. The owner's answers to its six questions close it. |
| [docs/plans/R1-reference-model.md](docs/plans/R1-reference-model.md) | The plan for round 1, running from 2026-11-23. |
| [docs/ROADMAP.md](docs/ROADMAP.md) | The owner's decisions in his words, the plan of record, and how rounds are held. |
| [docs/VALIDATION.md](docs/VALIDATION.md) | The append-only ledger: what ran, when, and what it does and does not show. |
| [CLAUDE.md](CLAUDE.md) | Notes for an agent working here: the front door and what has already bitten. |
| [reports/](reports/Adaptive%20FPGA%20ML%20for%20signal%20detection.md) | The literature survey of 2026-11-21. Uncontrolled: read it as leads, not evidence. |
| `research_notes/` | The notes behind that survey. |
| `spec/` | The one definition of the shared facts, and the constants generated from it. |
| `model/`, `stats/` | The reference model and the statistics. Skeletons until round 1's parcels land. |
| `tests/`, `vectors/` | The tests, the gate registry, and frozen known answers with their checksums. |
| `verify/run.sh`, `tools/` | The gate runner, its checks, and the generators. |

## Licence

MIT. See [LICENSE](LICENSE).

## How the work is held

Under two methods of the owner's: HonestFramework (no claim rests on an agent's judgement) and ParcelRound (splitting work across agents without losing the seams). Both are sibling repositories of this one.

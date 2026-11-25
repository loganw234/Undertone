# Undertone

A research project: a small machine-learning model in FPGA fabric whose weights stay adaptable while it runs, on one AMD Alveo U50, tested on whether it can learn to find faint signals it previously missed.

The name is the thing it listens for: a faint signal under the noise. The project began as AOTPU, "Adaptable OpenTPU"; the survey found OpenTPU long unmaintained, and the owner renamed it on 2026-11-21. The first round's records keep the old name.

## Where it stands (2026-11-25)

**Round 4 is done: stage E0 on the card, and stage E2, induced drift, in software.** On the card, round 1's stage E0 stream gives the reference model's every record and round 1's every count. In software, after the pulse's shape changes, a model that keeps learning recovers what a frozen one misses. Round 5's plan, approved on 2026-11-25, starts on 2026-11-26: learning in the fabric, in simulation, and stage E3, real noise, in software. The work is done in rounds, each with a plan the owner approves:

- **Round 1 (2026-11-23): the reference model and the statistics, in software.** A plain integer Python model of the noise source, the injector, the detector core, the weight store and the scorer (`model/`), and a second, independent authority for sensitivity (`stats/`). As a matched filter the model reproduces the textbook curve at five amplitudes.
- **Round 2 (2026-11-23): the fabric in simulation, and a learner in software.** SystemVerilog for the noise source, the injector, and the detector core with its weight store and a hidden layer in its head, each held against the model word for word in a simulation image of the project's own, and the three wired together ([docs/rtl/README.md](docs/rtl/README.md)). A learner that starts blank (`learn/`) reaches the matched filter's efficiency at stage E1 in software, 0.4949 against 0.5003 ([E1-software.md](docs/studies/E1-software.md)).
- **Round 3 (2026-11-24 and 25): first light on the card.**
  - a Vitis RTL kernel around that chain (`rtl/krnl/`): its registers behind an AXI4-Lite port, every score record written to the card's memory through an AXI4 master, held against the model word for word in simulation ([krnl.md](docs/rtl/krnl.md));
  - a host library (`host/`), one code over two backends, the kernel in simulation and XRT on the card, held against the model in simulation and tried in the Vitis hardware emulator ([host.md](docs/host/host.md));
  - the core's overflow flag tested over all its sources and both directions at once ([flag.md](docs/rtl/flag.md));
  - the first build for the U50, made on 2026-11-24: the kernel's clock closes at 100 MHz, with 0.122 ns of slack on its worst path. An overnight sweep asked for 150 and 200 MHz, and the tools lowered the clock to 127.4 and 108.2 MHz. Faster clocks are a goal for later, with the other routes considered, in [the roadmap](docs/ROADMAP.md);
  - the card day, 2026-11-25: on the U50, driven by the host library through XRT, five cases of stage E0's stream ran at 2^17 and at 2^20 frames. They cover the matched filter and a shape with the hidden layer, each also with a weight swap the host wrote while the run went. Every score word equals the model's, byte for byte, and a flipped coefficient bit, the control, was seen in both of its runs. For eight of the build's limits, the fabric took a shape at the limit and refused one just past it by its name ([CARD-first-light.md](docs/studies/CARD-first-light.md));
  - real data: by a rule frozen before any scored record was opened, rocket launches are seen in public seismic records more often than control windows at all four stations 78.5 to 275 km from the pad ([D3](docs/studies/D3-faint-launches.md)). Within 50 km of the pad they are loud ([D2](docs/studies/D2-launch-experiment.md)).

- **Round 4 (2026-11-25): stage E0 on the card, and stage E2 in software.**
  - **Stage E0 on the card.** Round 1's E0 stream ran on the U50 in 20 pieces. Every record equals the model's, and the counts read from the card's records equal round 1's at all five amplitudes, inside D8's tolerance; a flipped coefficient bit was seen ([CARD-e0.md](docs/studies/CARD-e0.md)).
  - **The rate.** Ten timed runs on the card, one generation each (a set of weights tested on 10,000 injections and scored): 1,273 an hour with this host code, most of it the host's Python reading of the records.
  - **Stage E2 in software.** The definition gained a second pulse, `e1`, which the fabric does not yet hold. After the pulse changes from `e0` to `e1`, the frozen model finds 12% of the injections, and a model retrained on recent windows, and one reset periodically, each find about 48%. The first reaches the new pulse's matched filter within the tolerance ([E2-software.md](docs/studies/E2-software.md)).

**Not yet shown:** sensitivity on the card, and anything about learning in the fabric. The card day is bit identity, and the card ran weights the host gave it. *Restated at round 4's close:* the card's counts are round 1's, read from the card's own records, which reproduces round 1's sensitivity word for word and adds nothing to it. Learning in the fabric, and stage E2 on the card, are not yet shown. A result here rests on one of two authorities and says which: bit identity with the model is not evidence about sensitivity, and a sensitivity result in software is not evidence about the fabric.

## Does it still hold?

    bash verify/run.sh             # the first size: needs Python and git; about three minutes
    bash verify/run.sh --with rtl  # every stage: Docker and the simulation image as well; about six minutes
    bash verify/run.sh --list      # the stages, with * on what would run
    make verify                    # the same as the first line

Eleven checks, each with a negative control that plants a list of faults and must see every one reported: twenty-two stages, and no cache. Four hold the documents: relative links resolve, no committable file carries a personal path, every row of a claims register names its basis, no text file carries a CR byte. Four hold the build: the generated copies equal the one definition, the tests pass, the model and the statistics import nothing from each other, and every gate has a test and a negative control that carry its name. Three run in the simulation image, built once with `python tools/sim_image.py build`: the image holds what is pinned, a simulator and a compiler read the generated copies as the numbers the Python copy holds, and every bench passes while every mutant of the RTL fails as named. Each check's file states what it cannot see.

A run of the first size says so on its verdict line; only a bare `== VERDICT: PASS` means every stage ran. When stage E1's committed record was made under an earlier definition, the first size passes with one check skipped by name, `E1-RECORD-STALE`, and `--require-all` fails on it. The record was made again under the current definition on 2026-11-25, so today nothing is skipped.

## The authority

**When two parts of this project disagree, the reference model is right.** It is a plain Python, integer-only model of the noise source, the injector, the detector core, the weight store and its swap, and the scorer; how its parts meet is [conventions.md](docs/model/conventions.md). The RTL, the host library and the card are held against it word for word, and anything the fabric cannot do exactly is refused by name.

Sensitivity has a second authority, deliberately not the model: `stats/`, a textbook formula and its own floating-point code. The two never import each other, and a stage of the gate holds that. [D0](docs/studies/D0-rough-design.md), section 2, defines both and says what each does not cover.

## What is here

| | |
|---|---|
| [docs/ROADMAP.md](docs/ROADMAP.md) | Where the project stands, the owner's decisions in his words, the plan of record, the routes for later, and how rounds are held. |
| [docs/VALIDATION.md](docs/VALIDATION.md) | The append-only ledger: what ran, when, and what it does and does not show. |
| [docs/studies/D0-rough-design.md](docs/studies/D0-rough-design.md) | The rough design, approved 2026-11-21. The owner's answers to its six questions close it. |
| `docs/plans/` | Each round's plan: [round 1](docs/plans/R1-reference-model.md), [round 2](docs/plans/R2-fabric-in-simulation-and-the-learner.md), [round 3](docs/plans/R3-first-light.md); [round 4](docs/plans/R4-card-e0-and-drift.md). |
| `docs/model/`, `docs/rtl/`, `docs/host/` | How the model, the RTL and the host library work, each page with its register of claims and its limits. The RTL starts at [docs/rtl/README.md](docs/rtl/README.md). |
| `docs/studies/` | The studies: the launch data (D1 to D3), stage E1 in software, the head's synthesis, the card's platform, the card day. |
| [CLAUDE.md](CLAUDE.md) | Notes for an agent working here: the front door and what has already bitten. |
| [PROVENANCE.md](PROVENANCE.md) | What the project has read from outside, and on what terms. |
| [reports/](reports/Adaptive%20FPGA%20ML%20for%20signal%20detection.md) | The literature survey of 2026-11-21. Uncontrolled: read it as leads, not evidence. |
| `research_notes/` | The notes behind that survey. |
| `spec/` | The one definition of the shared facts, and its three generated copies: Python, a SystemVerilog package, a C header. |
| `model/`, `stats/`, `learn/` | The reference model, the statistics, and the learner. |
| `rtl/` | The RTL, and its cocotb benches and mutants under `rtl/tb/`. |
| `host/`, `hw/` | The host library, and the kernel's packaging and build for the card; `hw/card/`, the card day's scripts as they ran. |
| `docker/` | The simulation image: Icarus Verilog and cocotb. |
| `tests/`, `vectors/` | The tests, the gate registry, and frozen known answers with their checksums. |
| `verify/run.sh`, `tools/` | The gate runner, its checks, and the generators. |

## Licence

MIT. See [LICENSE](LICENSE).

## How the work is held

Under two methods of the owner's: HonestFramework (no claim rests on an agent's judgement) and ParcelRound (splitting work across agents without losing the seams). Both are sibling repositories of this one.

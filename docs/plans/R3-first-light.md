# Round 3: first light on the card - the draft work order (first draft, 2026-11-24)

Drafted by the lead on 2026-11-24 on Logan's word "Yes, draft it", given after round 2 was pushed. **This is a first draft.** It goes past a verifier before it comes to him, and it is not approved. It ends with seven questions, each answerable in a few words.

Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. `<repos>` is the folder that holds this repository and its siblings.

## What binds it

- **The design:** `docs/studies/D0-rough-design.md`, approved by Logan on 2026-11-21. Its section 10 names the parcels this round would build, HOST and KRNL, and says "The card day is the lead's and Logan's."
- **His word on D0's questions** (2026-11-21), all as recommended: SystemVerilog, cocotb and the Vitis RTL kernel flow; phase A first, where the host trains and the fabric swaps; builds on `amd-arc-box` and daytime card windows booked through the TimeSheet, with only the lead touching the box and the card.
- **His words since**, whole in `docs/ROADMAP.md`: "Hidden layer from the start if simple enough, otherwise without for the initial design."; "Proposed is approved", on D0's row D1, 16-bit samples on one channel; Raspberry Shake "Stays held for now."; Docker, "You may install anything needed to the docker environment, or create a new one for this project if needed"; round 2's plan, "Approved with recommendations except 5 do a synthesis to measure real cost"; and "Yes, push", for round 2 only.
- **His word of 2026-11-24:** "We are also switching the parcel models to Opus rather than Fable as they have been". Every parcel of this round is sent on Opus, by name.
- **His words on real data** (2026-11-21): "I prefer to work with real data when able."
- **The standing rules** in `docs/ROADMAP.md`, and the send-back rule: only a regression or a wrong answer sends work back.
- **Round 2's lessons**, in CLAUDE.md's traps 13 to 18 and the last three entries of `docs/VALIDATION.md`. The ones that change how this round is held are under "How the round is held".

## What round 2 leaves

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| L1 | On this draft's commit the gate's first size passes: 1,112 tests, sixteen of its twenty-two stages, the six that need the simulation image not run | MEASURED | `bash verify/run.sh`; the run id and the verdict line are in the commit's message | a rerun |
| L2 | The second size last passed on the seam's merge, `cd72e3f`: 22 of 22 stages; 172 tests in 14 runs of 13 benches; 63,946 words identical to the model's; 96 mutant runs each failed as named; 10 minutes 33 seconds | READ | the merge commit's message; `docs/rtl/seam.md`, row K17 | a run of the second size on `main` |
| L3 | No file under `rtl/`, `spec/`, `docker/` or `tools/` has changed since that merge | MEASURED | `git diff --stat cd72e3f main -- rtl spec docker tools`, which prints nothing | that command |
| L4 | The RTL is nine SystemVerilog files, 2,133 lines: the source, the injector, the detector core with its weight store and head, the three wired together, and the foundation's filter of one tap | MEASURED | `wc -l rtl/*/*.sv` | that command |
| L5 | The chain's top takes the sample format as two parameters; the core takes its build's maxima as seven more, which default to the definition's | READ | `rtl/seam/seam.sv:37-39`; `rtl/core/core.sv:47-57` | those files |
| L6 | Every block answers one register port of its own: a valid, a write enable, an address, data in, and data out read through a register, zero outside the block's readable rows | READ | `docs/rtl/README.md:73` | the RTL's ports |
| L7 | No AXI interface exists in the tree | MEASURED | `grep -rnwi axi rtl/` prints nothing | a kernel top |
| L8 | The register map has 52 registers, fifteen of them below offset 0x80: the identity and capability registers a host reads first | MEASURED | `python -c "import tomllib; r = tomllib.load(open('spec/undertone.toml', 'rb'))['registers']; print(len(r), sum(1 for v in r.values() if v[0] < 0x80))"`, which prints 52 15 | that command |
| L9 | The map is in three blocks, at byte offsets under an address of 12 bits, in words of 32. Nothing sits below offset 0x10: the definition keeps those words for the kernel's own control, as the sibling project's kernel does on this card | READ | `spec/undertone.toml`, `[bus]` with its comment, and `[blocks]` | the definition |
| L10 | A score record is 168 bits, an index of 64, an epoch of 32, flags of 8 and a score of 64; a truth record is 144 | COMPUTED | `spec/undertone.toml`, `[records]` | the definition |
| L11 | At one score record a clock, each padded to 32 bytes, the core puts out 3.2 GB/s at 100 MHz and 4.32 GB/s at 135 MHz | COMPUTED | 32 x 100e6 and 32 x 135e6. The padding is the lead's assumption; the layout in memory is KRNL's design | KRNL's design |
| L12 | The head synthesised alone, out of context, for the card's part: 624 DSP slices at twelve hidden units under 16-bit one-channel samples and 816 under 24-bit three-channel; 208 and 272 at four. The part has 5,952 | READ | `docs/studies/SYN-head.md`, rows Y1, Y3 and Y5 | the first build's utilisation report |
| L13 | The filter bank at the definition's maxima, 16 filters of 128 taps, is 2,048 slices by arithmetic; with a head of twelve units, 2,672 or 2,864 | COMPUTED | `docs/studies/SYN-head.md`, rows Y7 and Y8 | a synthesis of the bank |
| L14 | Under the shell, SLR0 offers 2,352 DSP slices and all 32 HBM pseudo-channels attach to it | SURVEY | D0, rows H7 and H12 | `platforminfo` on the box; the first build's placement |
| L15 | So a build at the definition's maxima with twelve hidden units wants more slices than L14 gives SLR0, and one with four units, 2,256 or 2,320, about what it gives. **This rests on a SURVEY figure and drives nothing until wave 0 measures it** | COMPUTED | L13, L14: 2,048 + 208 and 2,048 + 272 | wave 0's reading of the platform |
| L16 | Stage E1 in software: a learner that starts blank reaches the matched filter's efficiency inside the statistics' tolerance, 0.49492 against 0.50026 | READ | `docs/studies/E1-software.md`, its result | a run of its parts again |
| L17 | Launches are seen at the four stations within 50 km of the pad, and they are loud there, not faint. The farther stations, 78 to 275 km, were not tried | READ | `docs/studies/D2-launch-experiment.md`: the headline, limit 1, and section 14, item 1 | an experiment at those stations |
| L18 | Two one-place faults in the overflow flag pass every bench that builds the head; the RTL is right in both | READ | `docs/rtl/core.md`, limit 23, from round 2's closing verifier | streams that catch them |
| L19 | Nothing bounds one bench run; the benches run one after another; nobody reads what the simulator prints while it builds; and the gate is green, without a word, on a long run's record of an earlier definition | READ | `docs/rtl/README.md`, limits 11, 14 and 15; `docs/studies/E1-software.md`, limit 10 | the foundation's repairs |
| L20 | The sibling project builds for this card with the Vitis RTL kernel flow on `amd-arc-box`. Vitis 2022.2 is there at `/data/Xilinx` and in `cft2204` at `/opt/Xilinx`. Its hardware emulation runs in `cft2204`, and its link fails on the box | READ | `<repos>/cft-fp256/CLAUDE.md:50-60`; D0, rows H1 and H3 | `v++ --version` in each; a hardware emulation run in each |
| L21 | For that project's design a hardware emulation leg takes about 4 minutes, a single build 120 to 170 minutes and a quad 250 to 470; one heavy link runs at a time, since a quad's placement wants 25 to 30 GB. It is another design and bounds nothing here | READ | `<repos>/cft-fp256/docs/BITSTREAM-BUILDS.md:311-320` | this design's own first build |
| L22 | That project's build script defaults to a clock of 10 MHz, which meets timing trivially; that project builds at 135 MHz | READ | `<repos>/cft-fp256/CLAUDE.md:66-71`; D0, row H11 | the script |
| L23 | The card is held by the sibling project every weekday night from 18:00 to 07:45 and from Friday 18:00 to Monday 07:45, and the box is shared at those times. A card window for this project is a weekday between 07:45 and 18:00, booked | MEASURED | `python <repos>/TimeSheet/timesheet.py standing list`, 2026-11-24 | the TimeSheet |
| L24 | The model steps about 110,000 frames a second in the matched-filter configuration under 16-bit samples | READ | `docs/model/mod-b.md`, row B14 | a rerun of that row's command |
| L25 | So the model's run of 2^20 frames, to compare with the card's, takes about ten seconds | COMPUTED | L24: 1,048,576 / 110,000 = 9.5 | a timed run |
| L26 | The simulation image holds cocotb 2.1.0 and pytest, and no model of an AXI bus | READ | `docker/requirements-sim.txt` | the image's own list |
| L27 | No published measurement of the time to swap a detector's weights on an Alveo-class card was found | SURVEY | D0, row S2 | a later search that finds one |
| L28 | Round 2 took about eight and a half hours by the clock, with six parcels and twenty-one verifier passes; its closing documents, the lead's, held ten wrong statements at the first pass on them and five at the second | READ | `docs/VALIDATION.md`, round 2's last three entries | those entries |

## What round 3 could be

Three shapes. Each is a real round; they differ in what they would show.

**A. First light.** The chain of round 2 put on the card, phase A: a kernel around it, a host library, one build, one card day. *Shows:* bit identity's second and third parts, the host and the card, on every score word; a weight swap from the host landing at its named index on the card, and how long it takes (L27); the clock one build closes at; the provenance and capability-bits gates, which only a build can hold. *Does not show:* anything about learning, sensitivity on the card, or faint signals.

**B. The question, in software.** Stage E2, induced drift, through the reference model with D0's five models; and the faint rungs of the launch data (L17). *Shows:* whether adapting recovers events a frozen model misses, on easy mode, and whether launches are seen where they are faint. *Does not show:* anything on the card.

**C. Both, as two tracks.**

**Recommended: A**, with the faint rungs beside it if question 4 says so. The card is the one part of the system nothing has touched, the swap's timing is a measurement nobody has published (L27), and D0 put phase A on the card first. What makes C costly is not files but the lead: under A the box, `cft2204` and the card are all the lead's, they are the round's critical path, and the round before closed with fifteen slips of the lead's own in its documents (L28). The faint rungs touch nothing of A's and need one ruling and a merge from the lead; E2 needs a learner's design and its verifier passes, and waits for round 4.

## The first build

The build's maxima are parameters of the RTL (L5), so the first build need not be the definition's maxima. **What a build cannot run, its capability registers say, and a blob past them is refused by name**: that is D0's contract, and the first build is where it is first held on fabric.

- **Its shape is Logan's** (questions 2 and 3): which head and which sample format. The lead's proposal: four hidden units and 16-bit one-channel samples, the definition unchanged. The bank's size is KRNL's design, ruled by the lead, under one rule: the build's DSP slices by arithmetic (L12, L13) stay inside what wave 0 measures one SLR to offer, so the first build need not cross SLRs. **That rule rests on wave 0's measurement, not on L14.**
- **Its clock** is asked as 100 MHz: a DECISION of the lead's, for a first light that is about bit identity and not speed. The build's timing report gives the slack at that clock; D5's 135 to 300 MHz stays an ESTIMATE until a build asks for more. Asking for 10 MHz, the trap of L22, would show nothing.
- **What the first build is not:** the definition's maxima, a second sample format, the scorer, replay from HBM as the source. Each is a later build's.

## Wave 0, the lead's

**P0-3**, before any parcel builds.

- **The foundation's repairs** (L19), each with a control that plants its fault:
  - a bound on every bench run, past which the stage refuses that run by name;
  - benches run side by side in the container, to bring the second size under ten minutes;
  - what the simulator prints while it builds is read: a line of a kind on a committed list, with the reason it is there, passes; any other fails the stage by name. The two lines of `docs/rtl/README.md`'s limit 15 are the list's first rows;
  - a long run's record of an earlier definition shows on the verdict line: the record's test skips, by name, in place of passing quietly, so the gate counts it and `--require-all` fails on it.
- **The platform, measured.** `platforminfo` for the shell on the box, read only, booked: the HBM's channels and sizes and where they attach, the clocks it offers, and what it says of each SLR's resources. That turns D0's rows H6, H7, H8 and H12 into MEASURED rows, or says what the tool does not give. L15 is then restated.
- **Hardware emulation, tried.** `v++ --version` in `cft2204` and on the box, and one emulation run of a trivial RTL kernel in `cft2204`, to learn whether L20 holds for this project before any parcel depends on it.
- **AXI in the simulation image**: a cocotb model of AXI4-Lite and AXI4, at a pinned version, by Logan's word on Docker, and the image built again.

P0-3 goes past a verifier before wave 1 builds. Wave 1's design stops may run while it is verified, since a design stop writes no code.

## The parcels, as waves

Every time box is an ESTIMATE. Every parcel is sent on Opus, and every parcel is design first.

| wave | parcel | what | depends on | time box |
|---|---|---|---|---|
| 0 | **P0-3**, the lead's | as above | round 2 | 2 h |
| 1 | **KRNL** | The kernel around the chain, in SystemVerilog: an AXI4-Lite slave onto the blocks' register ports; one AXI4 master that writes every score record to one memory buffer, and truth records to another, which the core never reads; a start, a length in samples and a done. The packaging for the Vitis RTL kernel flow, following the sibling project's files, which KRNL reads and does not change. Benches in the image: every score word read back from a memory model equals the model's, under the build's maxima. **Design first:** the memory layout of the records, entered in the definition so it is generated; the bank's size for the first build; what is refused at the kernel's edge. KRNL runs nothing on the box or in `cft2204`: the lead does | P0-3 | 2 h |
| 1 | **HOST** | The host library. One interface: open, read the identity and capability registers, load a blob, write a shadow and commit it at an index, run so many samples from a seed and a schedule, read the score and truth records. Two backends: one that is the reference model behind that interface, so the library's tests run anywhere; and one written against XRT's documented interface, which only the lead runs, on the box. Bit identity's second part: the library through the first backend equals `model/run.py` on every word. **Design first:** the language, Python or C against the generated header; how a blob past the capability registers is refused before any write | P0-3; KRNL's design stop, for the layout | 2 h |
| 1 | **FLAG** | The overflow flag tested over its sources together and both directions, on the small top, in place of one more stream for one more point (L18). The closing verifier's two streams and two faults are its first cases. **Design first:** what "every source and both directions" enumerates, and what it still leaves out, said as a limit | P0-3 | 1.5 h |
| 1 | **LCH-4**, if question 4 says so | The faint rungs: the 35 launches of D2 at the stations 78 to 275 km from the pad, with the hit rule, its constants and a new split fixed in the ledger before any record is fetched. **Design first:** which stations; whether D2's rule carries over or a new one is fixed; what the count must exceed | round 2 | 2 h |
| 2 | **BUILD**, the lead's | Hardware emulation of the kernel in `cft2204`, every score word against the model; then one build on the box, booked, at the first build's shape and 100 MHz. A manifest the build script writes from the tool's own reports: the commit, the clock as applied, the slack, the utilisation, the image's hash. Nothing of the build is committed but that manifest and the script | KRNL, HOST | the build's own length, unknown; L21 is another design's |
| 3 | **CARD**, the lead's | One booked daytime window (L23): load the image; check its manifest; read the identity block against the definition and the build's maxima; run 2^20 samples of stage E0's stream and compare every score word with the model's (L25); one weight swap from the host at a named index; the time from the host's first shadow write to the commit being accepted, and how many samples that spans; one blob past the build's maxima, refused by name | BUILD | one window |

**Named controls, in the briefs.** Each is built, run, seen to fail, and reported with its output.

- **KRNL:** a record writer that drops one record, one that writes one twice, and one that steps its address wrongly must each be caught; a kernel that advertises a shape its core refuses must be caught, in simulation, which is how the capability-bits gate's control is held without a second build.
- **HOST:** a first backend that answers with another seed's words must be caught by the comparison; a library that writes a blob past the capability registers must be caught before any write reaches a backend.
- **FLAG:** the two faults of L18 and every earlier mutant of the flag must each fail a named test; one neighbour of its own, tried and reported.
- **LCH-4:** D2's controls: the wrong window; a catalogue shifted by an hour; a launch that set a constant and is then scored, refused.
- **BUILD:** an image of another build must be refused by the manifest check, and this one accepted; a clock as applied other than the one asked must be refused.
- **CARD:** one flipped coefficient bit in the blob the host loads must be reported by the comparison, on a configuration where that tap reaches the score: bit identity's control, on the card's side.

**D0's sixteen gates, and what this round would do to each**, if every piece is READY and the card day runs. *Would be built:* capability bits, by KRNL and the card day; provenance, by BUILD. *Would be advanced:* bit identity, its second part by HOST and its third by the card day; swap and refusal, on the card; overflow, by FLAG, in simulation; truth isolation, in the kernel, in simulation; generated copies, by the record layout. *Built on and not changed:* reference model, injection, replay, noise tails, statistics, comparison rules. *Not touched:* the scorer, which no parcel builds in RTL, so the card's records are raw score words; and the learner gate, which is phase B's.

## What the round is for

| # | the round is worth running if | basis | source or command | falsified by |
|---|---|---|---|---|
| W1 | the chain, with a kernel around it, closes timing on the card's part at 100 MHz | BELIEVED | nothing of this design has been placed or timed; the head's sixteen products and shift are one stage (`docs/studies/SYN-head.md`, limit 1) | the first build's timing report |
| W2 | every score word the card puts out for 2^20 samples of stage E0's stream equals the model's | BELIEVED | the chain equals the model in simulation (L2); the card adds the kernel, the memory path, the clock and the host | the card day's comparison |
| W3 | a weight swap written from the host lands at its named index on the card, and its time from first write to commit is measured | DECISION | to measure it is the point; its value is unknown, and L27 says nobody has published one | the card day |
| W4 | if question 4 says so: by a rule fixed before any record is fetched, launches are seen at stations 78 to 275 km more often than control windows are | BELIEVED | D1b found them marginal at 120 km and beyond (`docs/studies/D2-launch-experiment.md`, limit 1) | LCH-4's test not rejecting |

## How the round is held

As round 2, with what it taught. Each of these is from something `docs/VALIDATION.md` records.

- **Parcels on Opus, by Logan's word**, named in every dispatch. The verifiers' model is question 5. This draft's own verifier runs on Opus, the model of round 2's verifiers, before that question is answered.
- **The lead's closing documents are written from commands.** Every figure, time and order of events in a closing document is taken from a command at the moment it is written, and a correction searches the whole tree for the old sentence. A closing verifier and a narrow pass on the lead's corrections are part of the plan, not extra.
- **The lead's work on the box, in `cft2204` and on the card goes past a verifier like a parcel's.** A verifier reads its committed record: the scripts, the manifest, the figures the lead copied out of each report with the command that gives them. No verifier touches the box, WSL or the card.
- **The TimeSheet before every run** on the desktop; anything of ten minutes or more booked; the box booked for every build in the mildest true mode around the sibling project's bookings (L23); the card booked as sensitive for the card day, in daytime.
- **Nothing from the box is committed but what the lead extracts**: no image, no report whole; the manifest, the script and the copied figures. The box's address is never committed.
- **Merges** as ours and then what theirs appended, checked parsed as the union, for `rtl/tb/benches.toml` and `tests/gates.toml` (CLAUDE.md, trap 15).
- **A round branch, `r3`,** cut from `main`; nothing pushed until Logan's word.
- **Fetching, for LCH-4:** EarthScope as before, each file logged with its source, size and hash, none committed; Raspberry Shake held.

## What this plan does not settle

- **How long the round takes.** Wave 1 is two-hour boxes. The build's length is unknown: L21's 120 to 170 minutes is another design's. The card day is one daytime window. The round may well run over two days by the clock: an ESTIMATE.
- **Whether the first build closes.** If it does not, the round ends at the build, with its report and its worst paths read, and the card day waits.
- **Speed.** A first light at 100 MHz says nothing of the 135 to 300 MHz D5 hopes for.
- **Sensitivity on the card.** Stage E0 on the card is the next step after bit identity, and is not in this round.
- **Stage E2, phase B's learner in fabric, the scorer in RTL, replay from HBM, the hidden layer trained, the definition's maxima on the card, the second sample format on the card.** Later rounds.
- **The lead's decisions of round 2** stand unless Logan overturns one; the list is in `docs/ROADMAP.md`, "Open with Logan at round 2's close", item 3.

## Questions for Logan

Each has a recommendation and a real alternative. A few words answer each.

1. **Which round: A, B or C?**
   - *(Recommended)* **A**, first light on the card.
   - *The alternatives:* B, stage E2 and the faint launches in software; C, both.
2. **The first build's head?** The definition keeps up to twelve hidden units either way; the build advertises what it holds.
   - *(Recommended)* **Four hidden units**: 208 DSP slices under 16-bit samples, measured.
   - *The alternatives:* twelve units, 624 slices, the definition's maximum; or no hidden layer.
3. **The first build's sample format?** Your word on D0's row D1 was "Proposed is approved", which the lead read as 16-bit, one channel, to start.
   - *(Recommended)* **16-bit, one channel.** The RTL keeps both formats, and every bench still runs both.
   - *The alternative:* 24-bit, three channels, the real records' format.
4. **The faint launches, LCH-4: in this round, or the next?**
   - *(Recommended)* **In this round**, as a fourth parcel: real data, the experiment the project's question needs, and nothing of the card's.
   - *The alternative:* the next round, with stage E2.
5. **The verifiers' model?** Round 1's verifiers ran on Sonnet. Round 2's ran on Opus while its parcels ran on Fable, but for its two closing passes, which ran on Fable. This round's parcels are on Opus.
   - *(Recommended)* **Opus**, as round 2's were. What a verifier is held to is its planted faults, and round 2's on Opus reported 60 of the 61 planted for them.
   - *The alternative:* a model other than the parcels', as round 1 and round 2 each had, for a second kind of independence.
6. **The card day: the lead alone, or with you?** D0 says it is "the lead's and Logan's".
   - *(Recommended)* **The lead**, in a booked daytime window, telling you before it starts and after it ends.
   - *The alternative:* with you, at a time you name.
7. **The push at the close?**
   - *(Recommended)* **The lead asks you again** before `main` moves and anything is pushed.
   - *The alternative:* a standing word now, to push once the closing verifier's pass is clean.

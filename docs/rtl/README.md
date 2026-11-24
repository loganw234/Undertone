# The RTL side: how a design is held against the model

Round 2's foundation. It is the lead's, written on 2026-11-23, and it is what every RTL parcel builds on. **When it was written there was no detector in RTL; by the end of that day's round there was one in simulation**, held against the model by what this page describes: the noise source and the injector ([source.md](source.md)), the detector core ([core.md](core.md)), and the three wired together ([seam.md](seam.md)), each a parcel's. This page is the foundation, not those. It is the means of holding RTL against the reference model: a simulation image, a second size of the gate, two more generated copies of the definition, a harness, and a filter of one tap written to prove the harness.

Nothing here is evidence about sensitivity. A bench that passes says the RTL's words equal the model's on the streams it ran. Sensitivity has its own authority, `stats/`.

## Where things are

| what | where |
|---|---|
| the simulation image | `docker/Dockerfile.sim`, `docker/requirements-sim.txt`, `tools/sim_image.py` |
| the gate's second size | `bash verify/run.sh --with rtl`; the checks are `tools/check_rtl.py` |
| the generated copies | `spec/undertone_pkg.sv` and `spec/undertone.h`, from `tools/gen_spec.py` |
| the harness | `rtl/tb/harness.py` |
| the list of benches and their mutants | `rtl/tb/benches.toml` |
| the runner, which runs inside the image | `rtl/tb/run_benches.py` |
| the filter of one tap, and its bench | `rtl/p0/onetap.sv`, `rtl/tb/bench_p0_onetap.py` |

Each file's first lines state what it cannot see.

## The image

    python tools/sim_image.py build     # minutes the first time
    python tools/sim_image.py tag       # its name

The image's tag is made from the two files it is built from, so a tree whose docker files changed since the last build finds no image and is refused, `IMAGE-MISSING`, never run on a stale one. Benches run with the tree mounted read-only and with no network.

It holds Icarus Verilog and cocotb, pinned, and a C compiler. It holds no Verilator: the one its base packages is older than cocotb supports (round 2's plan, row N20).

## The gate's two sizes

`bash verify/run.sh` is the first size, as it was: Python and git, no Docker. `bash verify/run.sh --with rtl` adds six stages, three checks and a control for each.

| stage | what it holds | its control plants |
|---|---|---|
| `rtl-image` | the image this tree describes exists, and holds Icarus Verilog and every pip package at the pinned version | a tree whose Dockerfile changed, one whose package list changed, and one that lost its package list: each must be refused by name |
| `rtl-spec` | Icarus Verilog reads every number of the package, and gcc every number of the header, as the Python copy holds it | every number of each copy changed, the hash among them, and one name taken out of the header: every one must be reported |
| `rtl-benches` | every bench passes under each of its profiles, and every mutant of the RTL fails as named | a bench with a wrong expectation; a bench whose simulator exits with code 0 before any test; an identity test that compares nothing; and a mutant named for a reason that is not its own |

**A run of the first size says on its verdict line that the rtl stages were not run.** The bare line `== VERDICT: PASS` is printed only when every stage ran.

**A verdict is never an exit code from inside the image.** A simulator exits 0 with every test failed. `rtl-benches` works out from the manifest and from each bench's source which runs and which tests there must be, then reads the results file cocotb wrote for each run and the evidence the harness left. A run with no results file is a finding, and so is a test the source has and the results do not.

## Writing a bench

A design under test keeps the **stream contract**, by port name: `clk`, `rst` (synchronous, active high); `in_valid` and `in_frame`, a frame taken at each rising edge where `in_valid` is high, channel *c* at `in_frame[c*S +: S]`; `out_valid` and `out_record`, a score record out at each rising edge where `out_valid` is high, in the canonical layout the generated package gives, the first declared field lowest. Its top module takes the parameters `SAMPLE_BITS` and `CHANNELS`, and the runner builds it once for each profile the bench names.

A bench is a cocotb module `rtl/tb/bench_<name>.py`, with a row in `rtl/tb/benches.toml`. It loads its configuration into the design its own way, builds a `model.detector.Core` from the same configuration, and calls `harness.compare`. The expected words come from the model. A bench whose words are not score records uses the harness's two pieces, `exchange` and `hold`, and so leaves the same evidence.

The manifest names the bench's **identity** tests: each must pass and must have left evidence of records compared, with the model's digest equal to the RTL's.

Name a bench module `bench_*`, never `test_*`: a bare `pytest` at the root collects `test_*.py` anywhere, and a cocotb module does not import outside a simulator.

## Mutants: the negative controls on the RTL side

A parcel's brief names its controls: one flipped coefficient bit in the RTL, a swap a clock late, a stage one bit narrower. Each is a **mutant** in the manifest: exact pieces of one source file replaced, in a copy, and the bench run on the copy. The stage passes a mutant only when every test it names failed and, where it names a kind, the harness reported a mismatch of that kind. A mutant whose edit no longer applies fails the stage. **A mutant that names no kind passes on any failure of its tests**, a simulator that stops at time zero among them: name a kind wherever the harness is what should see the fault.

The shipped RTL carries no fault switch. A fault is a patched copy, as a broken model in round 1 was a subclass made inside the test.

The controls on the model side are tests in the bench: `compare` is handed a model that is wrong in one place and the test requires a `Mismatch` at the record it predicts.

## The filter of one tap

`rtl/p0/onetap.sv` is the model's core at one setting: one filter of one tap reading every channel, a pool of 1, one head weight. It is not part of the detector and has no weight store, no swap and no refusal. Its bench holds it against the model on twelve random configurations and on thirty-two configurations of extremes, under both profiles: the coefficient, the head weight, the rectifier, the shift and the epoch each at both ends, with the channels' coefficients alternating between the two extremes, which is not every combination across the channels. Its seven mutants are the faults the harness was required to see: a coefficient bit, a logical shift for an arithmetic one, an index that starts at one, a flag bit, a design that stops putting records out, a design that puts out one too many, and a design one clock late.

## The register map

The definition has the register map's frame (`[bus]`), a read-only block of identity and capability registers, and a number for each refusal (`[refusal_codes]`). The plan gave the whole map to the foundation; the foundation wrote that much and left the rest to the designs that would use it. **The rest was entered on 2026-11-23, from the design stops of the two RTL parcels, as each drew it and the lead ruled**: the detector core's control block from 0x080, and the source's and the injector's registers from 0xF00 and 0xF80. Both parcels have merged, and their RTL answers it: `rtl/core/` the core's block, `rtl/source/` and `rtl/inject/` the other two, each with a bench that writes and reads its rows by the package's offsets.

What the two designs were ruled to share, and the definition now says:

- **Four blocks, each with a range** (`[blocks]`: `core`, `kernel`, `source`, `inject`; the kernel's, from 0xE00, since round 3, taken from the end of the core's range, where the core had no row). Outside its range a block does nothing. Inside it every write is taken or refused by name; none is dropped.
- **One port on every block**: `reg_valid`, `reg_we`, `reg_addr`, `reg_wdata`, and `reg_rdata`, a register that answers zero for what is not a readable row of that block, so the blocks' words can be ORed onto one bus. No ready and no response. An AXI4-Lite face is a kernel wrapper's, in a later round. **For that, the image holds cocotb's AXI bus models** since round 3's P0-3: cocotbext-axi 0.1.28 with cocotb-bus 0.3.0 (row R11). A bench imports them as `from cocotbext.axi import ...`; `AxiRam` wants a master's read and write channels both, and `AxiRamWrite` a master that only writes.
- **One refusal register a block** (`refusal`, `src_refusal`, `inj_refusal`): the number of the first refusal since it was cleared, and a write of zero clears it.
- **Three refusal names that are the fabric's alone**, which the model never raises: CORE_STOPPED, REGISTER_ACCESS, INJECT_PENDING. The model's names are still forty.
- **Registers read as bits** have their bits in the definition (`[register_bits]`), generated as `REG_<REGISTER>_<NAME>_BIT`.
- **Two bounds the fabric has and the model does not** (`[fabric]`): the most entries of a noise table, and the most truth records the injector holds.
- **Each pulse sample is in the package and the header**, an integer a sample, beside the pulse's id and length.

## Limits

1. **One simulator.** Everything here has run on Icarus Verilog 12.0 and on nothing else. A construct Icarus accepts and a synthesis tool does not is not seen.
2. **The harness does not configure the design.** A bench that loads the same wrong weights into the RTL and the model passes.
3. **The harness does not check latency.** It reports it; a bench that states one asserts on it. The mutant `one-clock-late` is held by the gate for one half: the latency test fails on it. The other half, that the identity tests pass on it, is not run by the gate, since a mutant's run holds only the tests it must fail; a verifier ran them on it by hand and they pass.
4. **No back-pressure, no stalled output, one clock.** The contract has none of them. **And a word that comes out long after the stream ends is not seen**: by default the harness sees an extra record up to nine clocks after the last expected one, and a design that puts one out ten or more clocks after passes. Two verifiers built it. A bench sets `settle` past anything its design could put out late. **Nor does the harness listen between two calls of `compare`** on one running design: a bench that compares a stream in pieces, with register writes between them, counts `out_valid` over its whole test itself. A verifier tried the pieces and they hold; nothing in the harness holds the gaps.
5. **A mutant shows the bench sees that fault.** Seven are planted in the filter of one tap. An eighth kind is not shown, and a verifier built one that passes: **an index counter of eight bits**. No run of this bench is longer than 200 frames, so the index field's bits above the eighth are never driven, and a design whose index wraps at 256 is identical on every record compared. A bench for the detector core must run past its counter's widths, or preset them.
6. **The evidence is written from inside the simulator**, by the harness, beside the bench. The stage reads it; it cannot tell a line the harness wrote from one a bench wrote for itself.
7. **`rtl-spec` holds the two copies against the Python copy**, which `generated` holds against the definition. It does not know whether RTL or a C program uses a constant rightly.
8. **The base image's own packages are not pinned**: Python, the C compiler and the system libraries are what its archive served on the day of the build. `rtl-image` prints what it finds.
9. **What a row of the register map means is not this file's.** The generator holds that the rows lie in whole words inside one block each and do not overlap; it does not know what a write or a read of a row does. That is each parcel's design and its bench: `source.md` and `core.md`, beside this file. The map's convention for a value wider than a word, consecutive words with the lowest bits at the lowest offset, is held by those benches and by nothing of the foundation's: the core's reads `spec_hash` back, eight words, with a mutant that reverses them, and each two-word row has a test that names it.
10. **The controls do not cover the whole judge.** `ctl-rtl-benches` plants six of the judge's findings: since round 3's P0-3, RUN-TIMEOUT (in a bench's own run and in a mutant's) and BUILD-LINE, beside round 2's four; a run the runner lost is planted too, and is reported as one of the four, NO-RESULTS. The others (a mutant that survived, a test not run, an unknown test, a test named twice, evidence whose digests disagree, an evidence line that cannot be read, BUILD-LOG-MISSING, and a committed list that cannot be read) are held by tests in the gate's first size and by no control. `tools/check_rtl.py` lists which.
11. **A run is bounded, a test is not** (round 3's P0-3, 2026-11-24; until then nothing bounded either). Every run has a limit in seconds, the bench's `limit` in the manifest or the runner's default of 600, and a run still going at it is stopped with everything it started and reported RUN-TIMEOUT. Round 2's longest run took 72 seconds alone and 59 beside five others. What the limit concedes: a bench whose one slow test is inside its run's limit passes however slow it is; a hang costs the stage the limit, not the stage's own 3,000 seconds; and runs side by side share the container's cores, so a limit set close to a run's own time can be passed under load. Every wait in a bench still has a bound in clocks, and passing it fails that test with what was waited for: the runner cannot say what a run was waiting for.
12. **A mutant is text, and the stage's "failed as named" is about a test's verdict and the kind of its first mismatch, not about the fault.** An expression in a port connection of a top did not build as written in this simulator: a mutant meant to drop one register write dropped every write, and failed as named for another fault than its name. The cause was not found. An author reads each mutant's evidence against the record and field its fault predicts; nothing here does it for them. And a mutant that edits a file another parcel owns stops applying when that file changes, and is then refused by name.
13. **A run that the design itself stops shows as failures without a name.** A check in RTL that prints a line and ends the simulation at time zero leaves the line in the run's log; the judge reads results, evidence and, since round 3's P0-3, the build's log, but not the run's own log, and reports each test as ended early.
14. **The stage runs six runs side by side** (round 3's P0-3; until then one after another). Each run is a process of its own, with its own build and test folders, results, evidence and logs; the runner's list and the judge's are worked out from the manifest by code they do not share, and a first-size test holds them equal. On round 2's last manifest, 110 runs, the stage's runs took 387 seconds one after another (2026-11-23) and about 103 side by side (2026-11-24, the lead's run of the stage alone). What it concedes: the runs share the desktop's cores with anything else the desktop runs, and six is a fixed number, not a measured best; the longest single run sets the stage's floor.
15. **What the simulator prints while it builds is read, and what it prints while it runs is not** (round 3's P0-3; until then neither). Every run that left results has its build log read line by line, and a line passes only when `rtl/tb/build_lines.toml` names its file, its line and its words, with the reason it is there; any other line fails the stage, BUILD-LINE, at its run and place, and a run with results and no build log fails it, BUILD-LOG-MISSING. The list's first two entries are the lines Icarus Verilog 12.0 prints for `rtl/source/source.sv` line 187 and `rtl/inject/inject.sv` line 276, each the first line of an `always_comb` process: "sorry: constant selects in always_* processes are not currently supported (all bits will be included)". In the lead's last run of round 2's second size (2026-11-23, 19:36) every build that held either file printed its line, 29 build logs for each file, 4 of them unmutated and 25 a mutant's, and no other line; the first run under the list (2026-11-24) read 110 build logs and passed 58 lines, the same 29 and 29. By its own words such a process is woken by every bit of the vector and not only the bit selected, which changes when it runs and not what it computes; that reading is the lead's, BELIEVED, and no test separates it. What the list concedes: an entry is one place, so a mutant whose edits move a listed line fails as BUILD-LINE and is written so that they do not; a listed line passes as often as it is printed; and the run's own log (`<run>.log`), where cocotb and a bench print, is read by no check, so a warning printed while a bench runs, the AXI models' DeprecationWarnings among them, is seen by no one.

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| R1 | The image holds Icarus Verilog 12.0-2build2, cocotb 2.1.0 with six more pip packages as pinned, Python 3.12.3 and gcc 13.3.0 | MEASURED | `python tools/check_rtl.py rtl-image --root . --state <a folder>`, 2026-11-23: its OK line | that command on another build of the image |
| R2 | The package and the header carry 407 values, the definition's hash among them, and Icarus Verilog and gcc each read every one as `spec/constants.py` holds it. They carried 172 before the register map, the fabric's names and bounds and the pulse's samples were entered | MEASURED | `python tools/check_rtl.py rtl-spec --root . --state <a folder>`, 2026-11-23, after that entry: its OK line. 172 is the same command's line before it | that command |
| R3 | Under both profiles the filter of one tap put out 8,960 score records equal to the model's, byte for byte, over the two identity tests; twelve tests passed in the two runs | MEASURED | `python tools/check_rtl.py rtl-benches --root . --state <a folder>`, 2026-11-23, when the manifest held this bench alone: its OK line. With other benches in the manifest the line gives totals for all of them | that command on a manifest cut down to this bench |
| R4 | 8,960 is 2 x 12 x 200 for the random test, and 32 x 5 and 32 x 125 for the extremes under one channel and three | COMPUTED | `rtl/tb/bench_p0_onetap.py`: twelve configurations of 200 frames; 32 configurations over every frame of five values a channel. 4,800 + 160 + 4,000 | arithmetic |
| R5 | Each of the seven mutants failed the tests it names, for the kind it names, under both profiles: fourteen mutant runs | MEASURED | the same command as R3, on the same manifest: "14 mutant run(s) each failed as named" | that command on a manifest cut down to this bench |
| R6 | *Round 2's figures, of its image and manifest.* The three controls each reported every planted fault and nothing else: 3, 815 and 12. The second is two for each of the 407 values and one name taken out; it was 345 when the values were 172 | MEASURED | `python tools/check_rtl.py control <kind> --root . --scratch <a folder>` for each kind, 2026-11-23: each CONTROL-DETECTED line | those commands |
| R7 | *Round 2's image, before round 3's three packages.* The image is 389 MB | MEASURED | `docker images undertone-sim`, 2026-11-23: the size it prints for the tag `python tools/sim_image.py tag` gives | that command |
| R8 | The first image built stopped every run before any build with "Unable to find libpython", and adding the package `libpython3.12t64` cured it | MEASURED | the runner's output on the first image, and `find_libpython` before and after installing the package in a throwaway container, 2026-11-23 | a build without that line |
| R9 | The sibling project's kernel presents an AXI4-Lite slave of 32-bit words under 12 address bits, with the kernel's control at 0x00 and its own registers from 0x10 | READ | `<repos>/cft-fp256/docs/ARCHITECTURE.md`, the table under "CSR map"; the 12-bit address in that project's place-and-route harness | those files |
| R10 | That frame fits this project's kernel | BELIEVED | R9, and D0's row H1: the same flow on the same card. Nothing of this project has been built | this project's first kernel build |
| R11 | Since round 3's P0-3 the image holds ten pip packages as pinned, cocotbext-axi 0.1.28, cocotb-bus 0.3.0 and scapy 2.8.0 among them, the last two brought by the first; R1's "six more" was round 2's image | MEASURED | `python tools/sim_image.py check`, 2026-11-24: "OK rtl-image: 1 image, undertone-sim:fa8df81e62d66711 ... 10 pip package(s) as pinned (cocotb 2.1.0)" | that command on another build |
| R12 | On round 2's last manifest the bench stage's 110 runs took about 103 seconds side by side, six at a time, from the first results file to the last; round 2's last run of them, one after another, took 387 seconds by the gate's stage line | MEASURED | `python tools/check_rtl.py rtl-benches --root . --state <a folder>`, 2026-11-24 09:33: the spread of the results files' times; the gate's line for `rtl-benches` in the run of 2026-11-23 19:36 | a rerun |
| R13 | In that run the longest single run took 59 seconds, the seam's bench under `s24x3`, where it took 72 one after another; 110 build logs were read and their 58 lines were each on the list | MEASURED | the runner's lines "ran <run> in <n> s" in that state folder's `runner.log`; the stage's OK line | a rerun |
| R14 | The benches' control reported each of its 22 planted faults and nothing else: round 2's 12, an unlisted build line in each of the 8 runs of the first profile that built it, a run that waits forever under a limit of 20 seconds as RUN-TIMEOUT, and a run the runner dropped as NO-RESULTS | MEASURED | `python tools/check_rtl.py control rtl-benches --root . --scratch <a folder>`, 2026-11-24 09:36: "CONTROL-DETECTED rtl-benches all 22 planted fault(s), nothing else" | a rerun |
| R15 | Two of the foundation's mutants, `one-clock-late` and `one-too-many`, add lines to the top: in their copies a line planted at the end of the top sits two and one lines lower, in that order, so the control works each mutant's line out | MEASURED | the control's first run of 2026-11-24, which expected line 91 for both and was given 93 and 92 | a rerun |

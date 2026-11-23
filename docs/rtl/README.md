# The RTL side: how a design is held against the model

Round 2's foundation. It is the lead's, written on 2026-11-23, and it is what every RTL parcel builds on. **There is no detector in RTL yet.** What exists is the means of holding one against the reference model: a simulation image, a second size of the gate, two more generated copies of the definition, a harness, and a filter of one tap written to prove the harness.

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
| `rtl-image` | the image this tree describes exists, and holds Icarus Verilog and every pip package at the pinned version | a tree whose Dockerfile changed, and one that lost its package list: each must be refused by name |
| `rtl-spec` | Icarus Verilog reads every number of the package, and gcc every number of the header, as the Python copy holds it | in each copy, one number changed of each kind (a bound, a width, a record field's lowest bit, a refusal code, a register's offset, the hash); and a name missing from the header |
| `rtl-benches` | every bench passes under each of its profiles, and every mutant of the RTL fails as named | a bench with a wrong expectation; a bench whose simulator exits with code 0 before any test; an identity test that compares nothing; and a mutant named for a reason that is not its own |

**A run of the first size says on its verdict line that the rtl stages were not run.** The bare line `== VERDICT: PASS` is printed only when every stage ran.

**A verdict is never an exit code from inside the image.** A simulator exits 0 with every test failed. `rtl-benches` works out from the manifest and from each bench's source which runs and which tests there must be, then reads the results file cocotb wrote for each run and the evidence the harness left. A run with no results file is a finding, and so is a test the source has and the results do not.

## Writing a bench

A design under test keeps the **stream contract**, by port name: `clk`, `rst` (synchronous, active high); `in_valid` and `in_frame`, a frame taken at each rising edge where `in_valid` is high, channel *c* at `in_frame[c*S +: S]`; `out_valid` and `out_record`, a score record out at each rising edge where `out_valid` is high, in the canonical layout the generated package gives, the first declared field lowest. Its top module takes the parameters `SAMPLE_BITS` and `CHANNELS`, and the runner builds it once for each profile the bench names.

A bench is a cocotb module `rtl/tb/bench_<name>.py`, with a row in `rtl/tb/benches.toml`. It loads its configuration into the design its own way, builds a `model.detector.Core` from the same configuration, and calls `harness.compare`. The expected words come from the model. A bench whose words are not score records uses the harness's two pieces, `exchange` and `hold`, and so leaves the same evidence.

The manifest names the bench's **identity** tests: each must pass and must have left evidence of records compared, with the model's digest equal to the RTL's.

Name a bench module `bench_*`, never `test_*`: a bare `pytest` at the root collects `test_*.py` anywhere, and a cocotb module does not import outside a simulator.

## Mutants: the negative controls on the RTL side

A parcel's brief names its controls: one flipped coefficient bit in the RTL, a swap a clock late, a stage one bit narrower. Each is a **mutant** in the manifest: exact pieces of one source file replaced, in a copy, and the bench run on the copy. The stage passes a mutant only when every test it names failed and, where it names a kind, the harness reported a mismatch of that kind. A mutant whose edit no longer applies fails the stage.

The shipped RTL carries no fault switch. A fault is a patched copy, as a broken model in round 1 was a subclass made inside the test.

The controls on the model side are tests in the bench: `compare` is handed a model that is wrong in one place and the test requires a `Mismatch` at the record it predicts.

## The filter of one tap

`rtl/p0/onetap.sv` is the model's core at one setting: one filter of one tap reading every channel, a pool of 1, one head weight. It is not part of the detector and has no weight store, no swap and no refusal. Its bench holds it against the model on twelve random configurations and on thirty-two configurations of extremes, under both profiles: the coefficient, the head weight, the rectifier, the shift and the epoch each at both ends, with the channels' coefficients alternating between the two extremes, which is not every combination across the channels. Its seven mutants are the faults the harness was required to see: a coefficient bit, a logical shift for an arithmetic one, an index that starts at one, a flag bit, a design that stops putting records out, a design that puts out one too many, and a design one clock late.

## The register map, as far as it goes

The definition has the register map's frame (`[bus]`), a read-only block of identity and capability registers (`[registers]`), and a number for each refusal (`[refusal_codes]`). **The control block is not there**: the shape, the shadow weights, the commit, the status and the latched refusal are drawn at the design stop of the detector core's RTL, from offset 0x80 up. The plan gave the whole map to the foundation; the lead's ledger for round 2 says why this part waits.

## Limits

1. **One simulator.** Everything here has run on Icarus Verilog 12.0 and on nothing else. A construct Icarus accepts and a synthesis tool does not is not seen.
2. **The harness does not configure the design.** A bench that loads the same wrong weights into the RTL and the model passes.
3. **The harness does not check latency.** It reports it; a bench that states one asserts on it. The mutant `one-clock-late` shows both halves: the identity tests pass on it, and the latency test fails.
4. **No back-pressure, no stalled output, one clock.** The contract has none of them.
5. **A mutant shows the bench sees that fault.** Seven are planted in the filter of one tap. An eighth kind is not shown, and a verifier built one that passes: **an index counter of eight bits**. No run of this bench is longer than 200 frames, so the index field's bits above the eighth are never driven, and a design whose index wraps at 256 is identical on every record compared. A bench for the detector core must run past its counter's widths, or preset them.
6. **The evidence is written from inside the simulator**, by the harness, beside the bench. The stage reads it; it cannot tell a line the harness wrote from one a bench wrote for itself.
7. **`rtl-spec` holds the two copies against the Python copy**, which `generated` holds against the definition. It does not know whether RTL or a C program uses a constant rightly.
8. **The base image's own packages are not pinned**: Python, the C compiler and the system libraries are what its archive served on the day of the build. `rtl-image` prints what it finds.
9. **The register map is not whole**, as above. And one of its conventions is held by nothing yet: a value wider than a word takes consecutive words, its lowest bits at the lowest offset. The definition says so in a comment. The first bench that reads `spec_hash` back, eight words, is what will hold it.
10. **The controls do not cover the whole judge.** `ctl-rtl-benches` plants four of the judge's findings; the others are held by tests in the gate's first size. `tools/check_rtl.py` lists which.

## Register

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| R1 | The image holds Icarus Verilog 12.0-2build2, cocotb 2.1.0 with six more pip packages as pinned, Python 3.12.3 and gcc 13.3.0 | MEASURED | `python tools/check_rtl.py rtl-image --root . --state <a folder>`, 2026-11-23: its OK line | that command on another build of the image |
| R2 | The package and the header carry 172 values, the definition's hash among them, and Icarus Verilog and gcc each read every one as `spec/constants.py` holds it | MEASURED | `python tools/check_rtl.py rtl-spec --root . --state <a folder>`, 2026-11-23: its OK line | that command |
| R3 | Under both profiles the filter of one tap put out 8,960 score records equal to the model's, byte for byte, over the two identity tests; twelve tests passed in the two runs | MEASURED | `python tools/check_rtl.py rtl-benches --root . --state <a folder>`, 2026-11-23: its OK line | that command |
| R4 | 8,960 is 2 x 12 x 200 for the random test, and 32 x 5 and 32 x 125 for the extremes under one channel and three | COMPUTED | `rtl/tb/bench_p0_onetap.py`: twelve configurations of 200 frames; 32 configurations over every frame of five values a channel. 4,800 + 160 + 4,000 | arithmetic |
| R5 | Each of the seven mutants failed the tests it names, for the kind it names, under both profiles: fourteen mutant runs | MEASURED | the same command as R3: "14 mutant run(s) each failed as named" | that command |
| R6 | The three controls each reported every planted fault and nothing else: 2, 14 and 12 | MEASURED | `python tools/check_rtl.py control <kind> --root . --scratch <a folder>` for each kind, 2026-11-23: each CONTROL-DETECTED line | those commands |
| R7 | The image is 389 MB | MEASURED | `docker images undertone-sim`, 2026-11-23: the size it prints for the tag `python tools/sim_image.py tag` gives | that command |
| R8 | The first image built stopped every run before any build with "Unable to find libpython", and adding the package `libpython3.12t64` cured it | MEASURED | the runner's output on the first image, and `find_libpython` before and after installing the package in a throwaway container, 2026-11-23 | a build without that line |
| R9 | The sibling project's kernel presents an AXI4-Lite slave of 32-bit words under 12 address bits, with the kernel's control at 0x00 and its own registers from 0x10 | READ | `<repos>/cft-fp256/docs/ARCHITECTURE.md`, the table under "CSR map"; the 12-bit address in that project's place-and-route harness | those files |
| R10 | That frame fits this project's kernel | BELIEVED | R9, and D0's row H1: the same flow on the same card. Nothing of this project has been built | this project's first kernel build |

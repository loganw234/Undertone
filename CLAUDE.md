# Working on Undertone

Short, and only things that are non-obvious. The README says what this project is; this says what will bite you.

The project's first name was AOTPU. The folder on the lead's desktop and the round folder of 2026-11-21 still carry it.

## Start here: one command answers "does it still hold?"

    bash verify/run.sh             # the first size: every stage that needs no Docker; about two and a half minutes
    bash verify/run.sh --with rtl  # every stage: the first size, and the six that run in the simulation image
    bash verify/run.sh --list      # the stages, with * on what would run
    make verify                    # the same as the first line

There are two sizes. The first needs Python and git. The second adds the stages named `rtl-*`, which need Docker and the simulation image (`python tools/sim_image.py build`, once, and again whenever `docker/Dockerfile.sim` or `docker/requirements-sim.txt` changes). **A run of the first size says so on its verdict line: "PASS for the first size: the 6 rtl stage(s) of 22 were NOT run". The bare line `== VERDICT: PASS` means every stage ran.** Anything that touches `rtl/`, `spec/`, `docker/` or the RTL checks is committed on the second size.

The first size took 75 s on 2026-11-23 before round 2, 56 of them the tests: two of those run the detector core at its true extreme inputs, about ten seconds each, and that is the overflow gate's claim, not waste. **There is no cache.** A run id is timestamp + commit, each stage drops a marker, and `--resume` reruns only what has not passed in that run. `--resume` is refused on a tree with uncommitted changes, and on a run that began on one, because nothing then says what the earlier stages ran on. A fresh invocation runs everything.

A stage passes on the line only success prints (`OK <stage>: <count> ...`), not on its exit code. A control passes only when its check exits non-zero **and** its log carries `CONTROL-DETECTED`. Read the verdict line, then the log under `verify/state/<run id>/`. Under `--only` the verdict says how many stages were not run.

Eleven checks, each with a control: four on the documents (`links`, `paths`, `claims`, `eol`, in `tools/check_tree.py`), four on the build (`generated`, `model-tests`, `independence`, `registry`, in `tools/check_build.py`), and three in the simulation image (`rtl-image`, `rtl-spec`, `rtl-benches`, in `tools/check_rtl.py`). How the RTL side works, and how to write a bench and its mutants, is `docs/rtl/README.md`. Each file's docstring states what its checks cannot see. Each control plants a fixed list of faults; a check broken some other way passes its control. A test skipped inside a stage that passed is named, counted on the verdict line, and fails under `--require-all`, on a fresh run and on a resumed one. Run the tests with `python -m pytest` or a bare `pytest`: the root `conftest.py` puts the tree on the import path for both. It is the only `conftest.py`, and there is no `pytest.ini`: either can deselect tests.

To change a shared fact: edit `spec/undertone.toml`, run `python tools/gen_spec.py`, commit the definition and its three generated copies (`spec/constants.py`, `spec/undertone_pkg.sv`, `spec/undertone.h`). To add a frozen vector: put it under `vectors/<parcel>/` and run `python tools/gen_sums.py`. A test that holds a gate is named `test_gate_<gate>__...`, its negative control `test_control_<gate>__...`, and the gate has a row in `tests/gates.toml`. Only the lead's foundation tests are named `test_p0_*`: the `model-tests` control keeps files of that name in its copies and drops every other test file, so a parcel's suite runs once in the gate. A parcel's test file named `test_p0_*` would run twice.

## The authority

The reference model **is the authority** (README, and D0 section 2). Round 1 wrote it, in plain integer Python under `model/`: the source and replay (`source.py`), the injector (`inject.py`), the detector core (`detector.py`), the weight store (`weights.py`), the scorer (`scorer.py`), and `run.py`, the one place they meet. How they meet is `docs/model/conventions.md`. Round 2 added a hidden layer to the detector's head (`docs/model/head.md`): a configuration blob has two versions, and one with no hidden layer is still version 1, byte for byte. **There is still no detector in RTL, no host library and nothing on the card**, so nothing about the system is claimed: there is only the thing a system will be held against. What round 2's foundation added is the means of holding RTL against the model, proven on a filter of one tap that is not part of the detector (`rtl/p0/`, `docs/rtl/README.md`).

Sensitivity has a second authority, which is deliberately not the model: `stats/`, a textbook formula and its own floating-point code. **`model/` and `stats/` never import each other**, and the `independence` stage holds that. A test under `tests/` may import both; that is what a seam test is.

Two runs are too long for the gate and are scripts of their own, each with a short form inside the gate: `python tests/test_mod_a_tails.py --long ...` (the noise's tail, 2^30 draws) and `python tests/test_seam_e0.py --full ...` (stage E0 in software, 200,000 injections an amplitude). Each docstring has the command and how to split it across cores. They are the lead's to run, booked on the TimeSheet.

Each parcel appends its rows to `tests/gates.toml`, so merging two parcels conflicts there and nowhere else. Keep every row.

A known answer in a frozen vector is worked by hand or by independent code, never produced by the model it then judges.

Every figure in a design or plan sits in a claims register with a basis: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY or DECISION. An ESTIMATE or SURVEY figure drives no decision until it is measured.

## The machines

Read on 2026-11-21 from `<repos>/cft-fp256/CLAUDE.md`, which has the addresses. Logan allowed this project to use them that day (question 4 of D0): simulation in `cft2204`, builds on `amd-arc-box`, daytime card windows booked through the TimeSheet, and **only the lead touches the box and the card**.

| name | what it is | card? |
|---|---|---|
| this desktop | Windows, where the lead works | no |
| `cft2204` | a WSL distro **on this same desktop**; its threads and memory are shared with Windows | no |
| `amd-arc-box` | a **separate physical Linux machine** | **yes, the U50** |

"The Linux box" means `amd-arc-box`. The card has no network port: PCIe is the only data path. Other projects of the owner's use these machines, and cft-fp256 holds standing bookings on the card, so card time is booked through the TimeSheet (`<repos>/TimeSheet`).

## Traps, each measured on 2026-11-21

1. **Do not count line endings with grep in this desktop's Git Bash (bash 5.2.26).** `grep -c $'\r' <file>` inside `$( )` counted every line of a three-line LF-only file; outside `$( )` it gave 0 for that file and, the verifier found, 0 for a real CRLF file too. The lead read the first as "the Write tool writes CRLF"; that was false. The `eol` stage of `verify/run.sh` counts CR bytes itself. By hand: `python -c "import sys; print(open(sys.argv[1],'rb').read().count(bytes([13])))" <file>`. A file from the Write tool measured 0.
2. **The local ParcelRound checkout is behind its remote.** Its `HEAD` is `8767e23` and `origin/main` is `f42242e`. Read the method without touching that tree: `git -C <repos>/ParcelRound show origin/main:METHOD.md`. The templates and `ADOPTION.md` are read the same way.
3. **There is no RTL simulator anywhere this project can reach yet.** `iverilog` and `verilator` are not on this desktop's Git Bash PATH (2026-11-21). This file said until 2026-11-23 that RTL simulation runs in `cft2204`; it does not. That day a login shell there found no `iverilog`, `verilator` or `vvp`, its Python could not import `cocotb`, and a search five levels deep found neither simulator. The sibling project runs its benches in a Docker image (`<repos>/cft-fp256/docker/Dockerfile.sim`); Docker answers on this desktop. Logan allowed an image of this project's own on 2026-11-23, and round 2 built it that day: `docker/Dockerfile.sim`, built and named by `python tools/sim_image.py build`, with Icarus Verilog 12.0 and cocotb 2.1.0 and no Verilator. **RTL simulation runs in that image, through `bash verify/run.sh --with rtl`, and nowhere else.** Its name is made from two files, `docker/Dockerfile.sim` and `docker/requirements-sim.txt`, so after a change to either the old image is not found and the gate refuses, `IMAGE-MISSING`, until it is built again. Ubuntu 24.04 packages Verilator 5.020, which is older than cocotb supports (5.036 for its current release, 5.022 for 1.9.2, by cocotb's own pages read that day); its Icarus, 12.0, is supported.
4. **`verify/run.sh` needs this to be a git repository.** The checks list committable files with git and refuse, by name, anywhere else. They also refuse a folder that is merely inside another repository.
5. **An escape sequence written into a file through a script can arrive as the byte it names.** The lead's scripted rewrite of trap 1 left two real CR bytes in this file where the text was meant to show the escape. Nothing checked for CR then; the `eol` stage does now.
6. **The Agent tool's worktree isolation refuses here** (2026-11-23): "Cannot create agent worktree: not in a git repository". The lead makes each worktree by hand, `git worktree add Data/worktrees/<parcel> -b parcel/<parcel> <commit>`, and **an agent's shell starts in the lead's checkout, not in its worktree**. A brief names the worktree's absolute path and says to work only there.

7. **A patch passed to Python through a shell heredoc can lose a level of backslashes, and a `\\uXXXX` escape typed through the Write tool can arrive as the invisible character it names.** Parcel LCH reported both on 2026-11-23; the first is how two CR bytes reached this file on 2026-11-21. Put a script in a file, and look at what was written. The `eol` stage sees a CR byte; it does not see other invisible characters. It bit the lead three more times on 2026-11-23, in round 2's foundation: a heredoc holding a quote ended early; one holding a backslash before a newline matched nothing, and an image was rebuilt and a bench run for nothing; and one, written minutes after this rule, turned an escaped newline inside a test's string into a real one. **A patch goes in a file written with a file tool, or through the Edit tool. Never through a heredoc.**

8. **Git Bash's `curl` fails on some hosts with error 43** ("a libcurl function was given a bad argument"). On 2026-11-23 a parcel met it on three hosts and the lead on a fourth. `/c/Windows/System32/curl.exe` fetched the lead's address at the next try.
9. **`pip` inside a virtual environment still writes the desktop's shared pip cache.** A parcel's install on 2026-11-23 put nine wheels there, outside its own folder. Pass `--no-cache-dir` when nothing may be written outside a folder. And read an index's terms whole before the first install: a search of the page for a few words missed the sentence that mattered.
10. **Two things about a verifier's clone, each learned by getting it wrong on 2026-11-23.** A clone keeps its remote and its reflog unless they are removed, and either shows the commit before the planted faults. And a fault planted by amending a commit shows in that commit's own diff: plant it in a file the commit already changes, or squash the work into one commit first. An agent's transcript file is empty until that agent is resumed, so neither its report nor its commands can be read from it before then.
11. **Three things about cocotb in the image, each met on 2026-11-23.** The base image's `python3` does not bring Python's shared library, and without the package `libpython3.12t64` cocotb's runner stops every run with "Unable to find libpython". The runner hands the simulator its own import path and ignores a `PYTHONPATH` given in `extra_env`: `rtl/tb/run_benches.py` puts the tree's root on `sys.path` itself. And a bench module is named `bench_*`, never `test_*`: a bare `pytest` at the root collects `test_*.py` anywhere, and a cocotb module does not import outside a simulator.
12. **A simulator's exit code says nothing.** With every test failed, and with a bench that exits before any test, the simulator exited 0 (the `rtl-benches` control plants the second). The verdict is the results file and the harness's evidence, read by `tools/check_rtl.py` outside the image.
13. **A bare `bash` handed to Python's `subprocess` runs in WSL, not in Git Bash** (2026-11-23). On Windows, Python looks in System32 before the PATH, and System32's `bash.exe` is the WSL launcher: the command ran inside `cft2204`. Two tests of round 2's foundation did that on every gate run, from its commit at 13:05 until it was seen at 13:26 the same day, in the lead's checkout and in a verifier's clone: each started a shell there to run `verify/run.sh --list` and two refused invocations, which write nothing. It showed only because a Windows environment variable did not reach the script. **Use `shutil.which("bash")`, the first on the PATH, as `the_gates_own_bash()` in `tests/test_p0_rtl_gate.py` does;** a test there parses every Python file of the tree and fails if a string holds that name as a word, in any case, with `.exe` or without, anywhere but in that one call, or if anything asks `subprocess` for a shell. So no string in this tree's Python may say the word, a message among them; docstrings and comments may. What that test cannot see is a name put together at run time, one that reaches Python from outside the file, or a program started under another name that starts that shell itself.

## The discipline that matters most here

A bit-identity pass is not evidence about sensitivity, and a sensitivity curve is not evidence that the fabric is correct. They have different authorities (D0 section 2). Say which one a result rests on.

# Validation ledger

Every run that established something, in the order it happened. **A figure here is a fact about the run that produced it**, on the date given, and is never updated to match a later measurement. A later run gets a later entry.

Failures stay in, including the lead's own. A correction is a new entry that names the old one.

This file is not a description of how the project works (see the README) and not a list of what is true now. It is the evidence those documents cite.

---

## 2026-11-21 - the literature survey (a judgement, not controlled)

Logan asked for research into current work on FPGA machine learning with adaptable weights, for a small low-latency model on a U50 (his words are in [ROADMAP.md](ROADMAP.md)).

### What ran

Five research agents, each on one strand, then one agent that wrote the report from their notes. The lead read the finished report and none of the sources.

- strands: OpenTPU and FPGA toolflows; the U50 platform and signal ingest; on-FPGA learning; real-time FPGA signal applications; faint-signal detection methods and datasets
- tool calls the agents reported: 59, 75, 105, 90 and 87, then 27 for the report writer
- outputs: [the report](../reports/Adaptive%20FPGA%20ML%20for%20signal%20detection.md) and five note files under `research_notes/`

### What it does not prove

**No planted-fault control was run on any of the six agents.** By the project's own method that makes the report an opinion with citations: a set of leads. The report marks its own weakest figures as snippet-only, secondary-table or PDF-extraction, and lists them near its end.

### Contradicted already

Put first because they are the findings that matter most:

- The U50 brief assumed a Windows host. Logan, 2026-11-21: the card runs in a separate Linux machine with proven tooling.
- The U50 brief assumed a QSFP28 network port as the only real-time input. Logan, 2026-11-21: his card has no network port.
- Two of the survey's own notes disagreed on whether the U50 is discontinued; the report records which it followed and why.

The report carries a correction note at its top for the first two.

### The lead's slips

- The lead's briefs for the survey stated the Windows workstation as the card's host without asking Logan where the card was. Two sections of the report were written for a setup that does not exist.

---

## 2026-11-21 - project setup: the front door, watched to fail

Logan asked for the project to be set up in the fashion of HonestFramework and ParcelRound (his words are in [ROADMAP.md](ROADMAP.md)). This entry records the first runs of the gate runner and each way it was made to fail on purpose.

### What changed

New: `verify/run.sh` (adapted from HonestFramework's `templates/gate-runner.sh`), `tools/check_tree.py`, `Makefile`, `README.md`, `CLAUDE.md`, `docs/ROADMAP.md`, this file, `docs/studies/D0-rough-design.md`, `.gitignore`, `.gitattributes`. The repository was initialised with `git init -b main`. Nothing is committed.

### Measured

All on the Windows desktop, in Git Bash, under `python` 3.12.15. With no commit yet, every run id ends `-nocommit`.

- `bash verify/run.sh`, run `20261121-064051-nocommit`: **VERDICT: FAIL**. `paths` reported 3 findings; `OK links: 17 relative links in 11 markdown files, 0 broken`; `OK claims: 27 register rows in 3 tables in 3 files under docs/, 0 unlabelled`; all three controls printed `CONTROL-DETECTED`.
- `bash verify/run.sh` after the change under Findings, run `20261121-064156-nocommit`: **VERDICT: PASS**, passed 6, failed 0, skipped 0; `OK paths: 2636 lines in 16 committable files, 0 personal paths`.
- `PYTHON=true bash verify/run.sh`, a checker that does nothing and exits 0, run `20261121-064212-nocommit`: passed 0, failed 6, rc=1. The three real stages failed with `rc=0` because no `OK` line was printed; the three controls each printed `NEGATIVE CONTROL DID NOT FAIL`.
- `bash verify/run.sh --only nosuch`: refused, rc=2, naming the six stages.
- `bash verify/run.sh --skip claims --require-all`: VERDICT: FAIL, rc=1. Without `--require-all`: `VERDICT: PASS, with 1 skipped by name above`, rc=0.
- `python tools/check_tree.py links --root docs`: `REFUSED links: NOT-THE-TOPLEVEL`, rc=2.
- `make verify`, run `20261121-064221-nocommit`: VERDICT: PASS.

### Findings

- **A spelling in the paths check failed too often to be a gate.** The first list included the session scratch folder's name as a bare word, carried over from another project's scan. Its first run flagged 3 lines, and all 3 were the survey naming an accelerator's memory of the same name: 3 false alarms, 0 real hits. It was removed, and the measurement is in `tools/check_tree.py`'s docstring. A real path to that folder still trips two other spellings.
- **The lead's line-ending check was a detector that always fired.** `grep -c $'\r' <file>` inside `$( )` reported every line of every file, 229 for a 229-line script. Outside `$( )` the same grep gave 0 on a three-line LF-only file, and 3 inside. Python's count of CR bytes was 0 for every file, including one written fresh by the Write tool.

### What this does not prove

- The gate holds the documents' form: links resolve, no listed personal spelling appears, register rows carry a basis. It says nothing about whether a labelled claim is true, and no stage runs any part of the system, because there is none.
- On the real tree only `paths` has been seen red, and that on false alarms. `links` and `claims` have gone red only on planted faults in throwaway repositories, and under the do-nothing checker.
- Every run was on an uncommitted tree, so no commit id says what was tested.

### The lead's slips

- The lead read the broken line-ending count as "the Write tool writes CRLF", ran `sed -i` over ten files that did not need it, and wrote that false trap into CLAUDE.md. Caught when the count did not move after the fix; corrected before the verifier's snapshot was taken.
- The lead copied a search spelling from another project without measuring it here (first finding above).

### Not done, and why

- No budgets: the whole run takes seconds. No CI: there is no remote.
- No history scan for personal paths: there is no history yet. The check reads the working tree only, which its docstring states.

---

## 2026-11-21 - D0, the rough design: a verifier pass with planted faults, and one re-check

Logan asked for a rough design to be drafted (his words are in [ROADMAP.md](ROADMAP.md)). Under the project's methods the lead's own work goes past a verifier before it comes to him. This entry records that pass. The round's folder is `Data/runs/2026-11-21-d0-design/`, kept on disk and not committed.

### What ran

- **VD0**, one verifier on Sonnet, on the brief `briefs/VD0.md`, against a frozen copy of the tree. It reports and fixes nothing. First pass: 46 tool calls and 11 min 23 s, as the harness reported. Filed at `reports/VD0.md`.
- **Four planted faults.** The verifier's copy of D0 differed from the lead's draft in four rows (H3, D9, S3, S6): a misquoted source line, arithmetic that did not follow from its inputs, a number changed against the survey report, and a quantifier widened past the report's. VD0 was not told. The key was in no file until its report had come back; it is now `reports/VD0-key.md`.
- **A re-check** of the lead's fixes, by the same verifier, on a second frozen copy with nothing planted: 18 tool calls and 4 min 23 s, as the harness reported. Filed at `reports/VD0-recheck.md`.

### Measured

- **Plants: 4 of 4 reported**, each from the cited source's own text or from recomputed arithmetic. Model: Sonnet. This rate belongs to that model, that brief and that tooling.
- **First pass, beyond the plants.** Real wrong answers in the lead's draft: row S3 said "two small CNNs" where the report says "two CNNs", and dropped the "one false alarm per month" condition; row S6 called a replay buffer and a frozen fallback "best-supported" where the report gives them as its own inference, and said "long benchmarks" where the report has one. Other findings, each in the report: D8 held only for one configuration of the datapath, which the draft never named; eight gates were missing from section 9; the gate's checker let through fence, link-syntax, ignored-target, case and prefix-label faults outside its stated limits; `--resume` glued runs together across uncommitted edits; each control planted one shape, so three mutants of the checker kept their controls green; CLAUDE.md held two CR bytes.
- **Re-check.** Every earlier wrong answer answered. "No regression (a) found." New, all marked (c): row D11 quoted the verifier's own simulation as agreeing "to within 0.003" where its figures give about 0.004; the comparison-rules gate had a control for half of what it holds; the runner printed "not selected -1 of 8" under `--require-all` with a skip; eight ways past the checks lay outside the docstring's limits; four new mutants kept their controls green, inside the docstring's limit but in classes it did not name.
- **The gate after the lead's last changes**, `bash verify/run.sh`, run `20261121-071029-nocommit`, on the Windows desktop under `python` 3.12.15: **VERDICT: PASS**, passed 8 of 8. `OK links: 18 relative links in 11 markdown files`; `OK paths: 2890 lines in 16 committable files`; `OK claims: 29 register rows in 3 tables in 3 files under docs/`; `OK eol: 16 committable text files, 0 with a CR byte`; the four controls reported all 9, 9, 8 and 2 of their planted faults and nothing else.
- **The gate made to fail, after the runner changed.** `PYTHON=true bash verify/run.sh`: passed 0, failed 8, VERDICT: FAIL, rc=1. `--skip claims --require-all`: passed 7, failed 1, skipped 1, "not selected 0 of 8", VERDICT: FAIL, rc=1. `--only links`: "VERDICT: PASS for the selected stages only: 7 of 8 stage(s) were NOT run". `--resume`: "REFUSED: --resume on a tree with no commit or with uncommitted changes (10 path(s))", rc=2. `--only nosuch`: refused, rc=2.

### Changed after the re-check, and not seen by the verifier

Stated plainly because the method sends the lead's fixes back to the verifier, and these did not go back:

- D11 restated to "within 0.004", with the simulation's pulse, noise level and trial count.
- A second control on the comparison-rules gate.
- The runner counts unselected stages from the stages it selected.
- `tools/check_tree.py`'s docstring now states the eight ways past the checks as limits, and names the classes in which no fault is planted. Its behaviour did not change.
- The README's line about this ledger, D0's line about this entry, and the roadmap's round table.

### What this does not prove

- **That the design is right.** The verifier checked that each row says what its source says and that the arithmetic follows. Nothing is built, and no row about the design is MEASURED.
- **That the survey is right.** SURVEY rows were checked against the survey report, not against the papers it cites.
- **That the blinding held**, to anyone but the lead. With no commit history, nothing shows the key was absent when VD0 ran.
- The simulation figures in row D11 come from a script in the verifier's scratch folder, not in this tree.

### The lead's slips

- Rows S3 and S6 carried wording from the survey's summary to the lead, not from the report they cite.
- "With fixed coefficients this same datapath is the classical matched filter" was written without the configuration that makes it true. The verifier's simulation gave 0.206 against the formula's 0.284 with a rectifier in the path.
- D0 said this pass "is recorded in VALIDATION.md" in two drafts before this entry existed.
- A scripted edit left two CR bytes in CLAUDE.md, and no gate looked for them. The `eol` stage does now.
- The lead filed both of the verifier's reports with some literal examples described in words, and first wrote that less had been changed than had. Each file's header now says what was done.

### Not done, and why

- **No second re-check.** The lead set one re-check pass before the draft goes to Logan. What changed after it is listed above.
- **No cost in tokens processed.** The harness gave 193,714 tokens after the first pass and 245,312 after the second; what those figures count is not established here, and the lead's own cost was not measured.
- **No commit.** The first commit waits for Logan's word.

---

## 2026-11-21 - the first commit, the name, and the push

Logan approved D0's six questions as recommended, allowed a remote and a push, and chose the name and the visibility in a question dialog. His words are in [ROADMAP.md](ROADMAP.md). This entry records what was committed and what the remote then held.

### Decided, by Logan

- The project is named Undertone, and its GitHub repository is public. The lead had recommended another name and a private repository; he chose otherwise on both.

### Measured

All on the Windows desktop, in Git Bash, under `python` 3.12.15.

- `git add -A` staged 16 files, the same 16 the checks list as committable. `git diff --cached --name-status` showed 16 additions and nothing else.
- Commit `0d282f13a56defb3d7d355fdec852e614e6d40c9`. Its message was scanned for the personal spellings: 0 hits in 15 lines.
- `bash verify/run.sh` at that commit, with 0 uncommitted paths, run `20261121-074106-0d282f1`: **VERDICT: PASS**, passed 8 of 8. `OK links: 20 relative links in 11 markdown files`; `OK paths: 2973 lines in 16 committable files`; `OK claims: 29 register rows in 3 tables in 3 files under docs/`; `OK eol: 16 committable text files, 0 with a CR byte`; the controls reported all 9, 9, 8 and 2 planted faults and nothing else.
- `bash verify/run.sh --resume` on that clean committed tree: passed 0, cached 8, VERDICT: PASS. This is the first time `--resume` ran where it is allowed; until now it had only been seen refusing.
- Before publishing, the survey files were searched for long quotations: a pattern for quoted spans of more than 40 words matched 5 times, and all 5 were the report's own prose lying between two short quotations. Spans of 40 words or fewer were counted, not read.
- `gh repo create loganw234/Undertone --public --source=. --remote=origin`, then `git push -u origin main`: rc=0.
- `git ls-remote origin refs/heads/main` returned `0d282f13a56defb3d7d355fdec852e614e6d40c9`, equal to `git rev-parse HEAD`. `gh repo view` reported `PUBLIC`, default branch `main`.

### What this does not prove

- That anyone may use what is published. The repository has no licence file, so no right is granted to a reader. Whether to add one, and which, is Logan's.
- That every quotation in the survey files is short. Only spans over 40 words were looked at.
- Anything new about the design. Nothing changed in D0 but its status line, one limit restated after Logan's answer to question 4, and his answers at its end.

### Notes

- The commit carries the author identity configured in git on this desktop, the same address as cft-fp256's latest commit.
- The local folder is still named AOTPU, and so is the round folder of 2026-11-21.
- The lead noticed no slip of its own in this step.

### Not done, and why

- This entry is a second commit. Its own push is not recorded here, since an entry cannot record the push that carries it.
- No licence, no CI, no branch protection: none was asked for.

---

## 2026-11-23 - the plan for round 1: a verifier pass with planted faults, one re-check, and Logan's word

Logan asked for the plan on 2026-11-21, and offered an idea for real data: seismic records labelled by public launch times. The lead drafted the plan that day, put it past a verifier, and Logan started the round on 2026-11-23. The plan of record is [plans/R1-reference-model.md](plans/R1-reference-model.md). The round's folder is `Data/runs/2026-11-21-r1-model/`, kept on disk and not committed.

### What ran, on 2026-11-21

- **Three web searches** on launches in seismic records. Their summaries are in [plans/R1-search-2026-11-21.md](plans/R1-search-2026-11-21.md). The lead opened none of the pages, so the plan's rows L1 to L5 and L7 are BELIEVED.
- **VP1**, one verifier on Sonnet, against a frozen copy of the first draft: 14 tool calls and 4 min 27 s, as the harness reported. Its copy carried **five planted faults**; the key was in no file until its report was back.
- **A re-check** by the same verifier on the second draft, with nothing planted: 3 tool calls and 1 min 23 s.
- **A test escalation.** At its start VP1 sent the lead one message, as its brief asked.

### Measured

- **Plants: 5 of 5 reported**: a rerun contradicting a version, a recount contradicting a count, recomputed arithmetic, a row against its source file, and an owner's decision against the roadmap. Model: Sonnet.
- **First pass, beyond the plants.** Two wrong answers of the lead's: a sentence saying each question had three parts when three did not, and a MEASURED row citing `git status -sb` for a commit id that command cannot print. Gaps, each in the report: an unowned `model/__init__.py`; a pulse definition and a quantising rule three pieces needed and none owned; controls that could pass while testing nothing; five ways the launch experiment could pass while showing nothing, beyond the lead's four; the plan redefining D0's stage E3 without saying so; seven of D0's gates with no stated home; and lines of the method's dispatch checklist the plan did not meet.
- **Re-check.** Every earlier wrong answer fixed; "No regression of type (a) found." One new wrong answer: "Nobody publishes a station that recorded nothing", which the plan's own row L1 contradicts. Seven smaller gaps, among them a gate registry described two ways, one of which would have failed P0's own gate.
- **The escalation channel works in one direction.** VP1's test message reached the lead while VP1 was still running, queued for the lead's next turn. The lead-to-running-agent direction has not been seen.
- `bash verify/run.sh` on 2026-11-23, with these documents in the tree, on the branch `r1`: the run and its verdict are in the next entry, since this entry is part of what that run reads.

### Decided, by Logan, on 2026-11-23

- The round starts. His words are in [ROADMAP.md](ROADMAP.md) and close the plan.
- The licence is MIT. The lead had recommended Apache-2.0 because cft-fp256 uses it; he explained that choice came from a contract there, and gave his test for this project: the easiest option for others to reuse the work.

### Changed after the re-check, and not seen by the verifier

The eight findings of the re-check were answered in a third draft, which is the plan of record. Those answers did not go back to VP1.

### What this does not prove

- **That launch signals are usable.** Nobody here has opened a page the searches summarise, or looked at a seismic record.
- **That the plan's time boxes hold.** All are estimates.
- **That the blinding held**, to anyone but the lead: the drafts were not committed, so no history shows the key was absent.

### The lead's slips

- In the D0 round's ledger the lead wrote, unchecked and unlabelled, that an agent has no way to message the lead while it runs. It has.
- The first draft said a verifier's pass "is recorded in `reports/`" before any report existed: the same slip as in D0, a third time.
- The first draft filed Logan's idea under "Logan's words" in the lead's paraphrase. The plan now quotes him.
- The lead recommended Apache-2.0 by analogy with cft-fp256 without knowing why that project chose it.
- The lead could not file VP1's reports from the agent's transcript, which was empty, and wrote them out from the completion notices.

### Not done, and why

- **No second re-check.** One was set before the plan went to Logan.
- **No cost in tokens processed.** The harness gave 133,897 tokens after the first pass and 158,012 after the second; what those figures count is not established here.

---

## 2026-11-23 - round 1, P0: the one definition, the skeleton, four build stages, and three verifier passes

Round 1 started on Logan's word of 2026-11-23. P0 is the lead's piece: what every parcel of the round stands on. The plan is [plans/R1-reference-model.md](plans/R1-reference-model.md); the round's folder is `Data/runs/2026-11-21-r1-model/`, kept on disk and not committed. Everything below is on the branch `r1`, which is local: nothing has been pushed since `d13281f`.

### What changed

- `spec/undertone.toml`, the one definition, with `tools/gen_spec.py` generating `spec/constants.py` and refusing a definition it does not understand; the reference pulse as integer data.
- The skeletons of `model/` and `stats/`: `model/refusal.py`, `model/stream.py`, `model/records.py`.
- `tests/gates.toml`, the gate registry; `vectors/p0/`, hand-worked vectors with a checksum list (`tools/gen_sums.py`).
- Four build stages in `verify/run.sh`, each with a negative control: `generated`, `model-tests`, `independence`, `registry` (`tools/check_build.py`). The runner also names and counts a test skipped inside a passing stage, records whether a run's tree was clean, and refuses to resume a run that began on a dirty one.
- A root `conftest.py`; the MIT licence; the live documents.

### What ran

- **VP0**, one verifier on Sonnet, three passes: P0 as first committed, with **four planted faults** in its clone (33 tool calls, 12 min 28 s, as the harness reported); a re-check of the lead's fixes (26 tool calls, 10 min 23 s); a second re-check scoped to `model/records.py` (10 tool calls, 3 min 58 s). Its first two reports are filed verbatim from its transcript, under the round's `reports/`.
- Each agent of the round sent the lead a test message at its start, and each arrived.

### Measured

- **Plants: 4 of 4 reported**, each by a fault or a mutant the verifier built and ran. Model: Sonnet.
- **First pass, beyond the plants: seven wrong answers of the lead's.** `--resume --require-all` hid a skipped test; `--resume` carried a pass from a tree with uncommitted changes onto a clean one; a module in a folder with no `__init__.py` was never imported by the independence check; the generator accepted a lower-case refusal name, did not refuse unknown keys its docstring said it refused, and ended in a traceback on a missing or mistyped value; `profile([])` raised a TypeError where a refusal belongs. And no test frame had different values in different channels, so a check of one channel alone would have passed.
- **Second pass.** All eleven earlier defects answered, no regression, and **three new wrong answers, all in `model/records.py`**, which the lead had written after the first pass: an unhashable kind raised a TypeError; `digest` did not check its kind for an empty sequence; the tests could not see a range check limited to one kind or a digest that skipped its first record. It also showed four truth records and three event records sharing one digest.
- **Third pass.** "No (a) regression and no (b) wrong answer." 24 mutants of `model/records.py` against the tests: every one that changes behaviour for a real input fails them.
- **The gate**, `bash verify/run.sh`, on the Windows desktop under `python` 3.12.15, each on a clean tree at the commit named:
  - `e32d183`, P0 as first committed: VERDICT: PASS, 16 of 16; `OK model-tests: 14 tests ran`. Under a do-nothing checker, `PYTHON=true`: passed 0, failed 16.
  - `1217faa`, after the first pass's fixes: VERDICT: PASS, 16 of 16.
  - `60aa75b`, after the second pass's fixes: VERDICT: PASS, 16 of 16; `OK model-tests: 93 tests ran, 0 failed, 0 errored, 0 skipped`; the four build controls reported all 3, 3, 3 and 5 of their planted faults and nothing else.
- **Each new stage watched to fail on a fault its own control does not plant**, eight cases, before the first commit: a definition edited with its copy left alone; a flag bit used twice; a vector added and not listed; a test file that cannot be imported; a cross-import two packages deep; a stage row naming a control that does not exist; a test claiming a gate with no separator. A skipped test passed, named.
- **`--resume` in a throwaway clone at `156504d`:** it resumed a run that began on a clean tree; it refused one that began on a dirty tree, with "did not begin on a clean tree"; a fresh run on that tree gave VERDICT: FAIL; under `--require-all` a resumed run with a skipped test gave VERDICT: FAIL; on a dirty tree it refused.
- **The lead's Agent tool refused worktree isolation** at the first dispatch: "Cannot create agent worktree: not in a git repository". The plan's row P3 is false here. Worktrees are made by hand under `Data/worktrees/`.

### Changed after the last pass, and not seen by the verifier

One sentence of `model/records.py`'s docstring, restated to what the code does when handed something that cannot be iterated; one test added, that `digest` refuses a record that does not fit wherever it sits; one trap added to CLAUDE.md; this entry. No behaviour changed.

### What this does not prove

- **That the definition says what the design means**, beyond the three figures a test pins to D0's rows D1 to D3. The record widths, the flag bits and the pulse are the lead's choices; D0 gives none of them.
- **That a control catches a fault it does not plant.** The verifier's mutants show which do not, and `tools/check_build.py` states that limit.
- **Anything about the model.** There is no detector, no generator and no injector yet.
- **That the blinding held**, to anyone but the lead: the planted clone had no remote and no reflog, and the key was in no file until the report was back, but nothing a later reader can check shows it.

### The lead's slips

- **A commit on a red gate.** `156504d` was made while one control was red: the lead's command ran the gate and committed without testing its verdict. `1217faa` fixes the control. The lead now commits only inside a test of the verdict line.
- **A false sentence in the round's ledger**: that each fault the verifier got past a check was now planted in that check's control. Four were not. Corrected there by an appended entry.
- **New code between passes.** `model/records.py` was written after the first pass and sent to the re-check as a fix. It was new work, and it held three wrong answers.
- **A test whose own anchor was wrong** turned the gate red once; the gate caught it before any commit.
- **A boundary crossed, disclosed:** P0 creates `stats/__init__.py`, which the plan's file table gives to STAT.

### Not done, and why

- **No push.** `r1` is local. `main` moves, and is pushed, at the round's close, and the lead asks Logan first.
- **No cost in tokens processed.** The harness gave 200,919, 276,877 and 300,778 tokens after the verifier's three passes; what those figures count is not established here.

## 2026-11-23 - round 1, parcel LCH, part A: the launch-data study, read and checked, measuring nothing

Parcel LCH's first phase is merged into `r1` as `1d06600` (the parcel's commits `8440b4d`, `d0d8bf3` and `4247b73`). It is a study of what public pages and public station services say: [studies/D1-launch-data.md](studies/D1-launch-data.md), with the scripts that rebuild its tables under `docs/studies/d1/` and the sources' terms in `PROVENANCE.md`. **It measured nothing.** Whether a launch can be seen in a real record is part B, which is running and is not merged.

### What changed

- The study: what the pages behind the plan's rows L1 to L7 say about rocket launches in seismic and infrasound records; the public stations near three launch sites with their distances, worked from the services' own coordinates; the launch catalogue's fields and terms; controls for an experiment (the plan's nine and more of its own) and a hit rule; and the smallest download that could show a ladder of distances.
- `docs/studies/d1/`: the quotations as data with a checker, the station tables' generator with a self-test, the figures' arithmetic, and the download list as a script that prints requests and fetches nothing.
- `PROVENANCE.md`: each source, its terms, and the acknowledgement it asks for.
- The claims register grew from 44 rows to 131.

### What ran

- **LCH**, on the lead's model: phase 1 (187 tool calls, 41 min 1 s, as the harness reported), then the send-back after its verifier's first pass.
- **VLCH**, one verifier on Sonnet, two passes: the study as first committed, in a clone holding **five planted faults** in the study's own claim-and-source format (49 tool calls, 8 min 25 s); then a re-check scoped to the fix commit `4247b73`, on a clone with nothing planted (18 tool calls, 3 min 2 s). Both reports are filed verbatim from its transcript under the round's `reports/`.

### Measured

- **Plants: 5 of 5 reported.** Model: Sonnet.
- **First pass, beyond the plants: two wrong answers of the parcel's own.** A row said a published study "examined" 1,001 launches, where its page says the period included that many. And "no scrubs" was stated of the launch catalogue in three places, where what had been read was that the column descriptions name no scrub code; the same page lists a code for "not a launch" that the study had not mentioned, and no catalogue file had been opened. Nine smaller findings: an inference stated as read, estimates labelled as computed, controls and a hit rule two people could not have scored alike, and a download list whose first request could not settle what it was listed for.
- **Second pass: "no (a) regression and no (b) wrong answer."** The verifier ran the study's quotation checker against the saved pages: 90 quotations for 55 READ rows, 0 findings. It checked four of the new station rows (M1, M3, M10, M11) against the saved responses, two of them with its own geodesic, and agreed with each. It searched every tracked file for the held network's 75 station codes and their coordinates: none.
- **The gate on the staged merge**, `bash verify/run.sh` on the Windows desktop: VERDICT: PASS, 16 of 16; `OK claims: 131 register rows in 10 tables in 6 files under docs/, 0 unlabelled`; `OK paths: 7272 lines in 53 committable files, 0 personal paths`. The merge added eleven files and touched none that `r1` had.
- **What the study reports, each a READ row there and none checked by this project against a record:** a regional network's stations from 13.5 km out to 275 km from the Vandenberg pad, three components at 100 samples a second; one launch that network's own page says it "most likely" detected at a station 32.6 km away; a published range for how fast the sound crosses the ground.

### Merged with these stated limits

Each is the verifier's, and each is the parcel's to answer in part B.

- The hit rule does not say whether a second with a missing frame counts as "not up". It leaves the false-alarm fraction its thresholds are set to out of the study.
- With one launch and two control windows, the second control's test can never reject. A first look can report it only as not run.
- The sixth control has no numeric criterion.
- The digitiser's width is an inference. The gain it rests on, 419,430 counts per volt, fits 24 bits over 40 volts and also 22 over 10, 21 over 5 and 20 over 2.5. D0's row D1 turns on that width, and it stays BELIEVED until a record is read.

### What this does not prove

- **That a launch is visible in any public record.** Nothing was fetched but pages and station lists. The plan's row V2 is exactly as BELIEVED as before.
- **That every READ row is right.** The verifier checked the quotations against the saved pages and a sample of them against the live ones; two sites it could not open in either pass.
- **That every station row is right.** Four were recomputed.
- **That the hit rule is fit for an experiment.** It is closer to exact than it was. The limits above are open.

### The lead's slips, and one of the parcel's

- **Two data services were queried before their terms were read.** The parcel made six requests to one station service and three to another before reading that using each accepts its terms. It reported this itself. The lead held both services' rows out of every committed file and put it to Logan, who allowed the first on 2026-11-23 and is looking into the second. No request has gone to the second since, and none of its rows is committed. The brief should have said "read a service's terms before its first request"; it does now.
- **The lead's ruling on what the study may say about the held network was fuller in its message to the parcel than in the ledger**, and the verifier, reading the ledger, judged the study's prose against the shorter one. The lead corrected that in the ledger. A ruling goes in the ledger whole, then in the message.
- **The parcel's first report was written out by the lead** from the completion notice, because its transcript file was empty. The filed copy's header says so.

### Not done, and why

- **The quotation checker was not rerun on `r1`.** It needs the saved pages, which are in the parcel's scratch folder and are not committed. The verifier ran it on the merged commit in its clone.
- **No waveform, no catalogue file.** That is part B, under Logan's word of 2026-11-23 on downloads.
- **Nothing pushed.**

## 2026-11-23 - round 1: the definition gains the model parcels' facts, and the seam conventions are written down

Two of the lead's own changes on `r1`, made while the wave's parcels were at or just past their design stop. The first went past a verifier with planted faults. The second has not been past one yet.

### What changed

- **`adb10d1`, the definition.** `spec/undertone.toml` gained what parcels MOD-B and MOD-A asked for in their designs, as the lead's decisions: the bounds `max_rows = 16`, `max_pool = 65536`, `max_score_shift = 31` and `max_hist_bins = 4096`; the rectifier codes `pass = 0` and `abs = 1`; the rounding of an injected sample; a declared id for each pulse; and 27 refusal names, 37 in all. `tools/gen_spec.py` checks each addition and refuses by name. The `model-tests` control's copies now keep only the tests named `test_p0_*`, so a parcel's suite runs once in the gate.
- **`d742aee`, [model/conventions.md](model/conventions.md).** The four conventions the lead ruled while three parcels each needed the same answer: where a truth record says a pulse is, which way round coefficients are written, what a crossing is, and how a filter reads several channels. One answer worked by hand.
- **This commit**, after the verifier's pass: in `tests/test_p0_generator.py`, three more bad definitions that must be refused, four more range ends that must be accepted, and a new test of nine cases that each generated fact follows its own key and no other; `drop_tests()` compares names in lower case; one sentence in CLAUDE.md.

### What ran

- **VP0**, the foundation's verifier on Sonnet, a third pass scoped to `adb10d1`, on a clone whose tip held that commit with **four planted faults** (17 tool calls, 6 min 43 s, as the harness reported). Its report is filed verbatim under the round's `reports/`, with the key beside it.

### Measured

- **Plants: 4 of 4 reported.** A bound one short of the decided value and a misspelled refusal name, each found against the round's ledger and the parcel's own request; a rectifier code accepted twice and a pulse id accepted one past its field, each found by probing the generator at its edges. Model: Sonnet.
- **In the real commit: "no (a) regression", and no wrong answer.** Every constant, code and name, and the order of the 37, matches the decisions and the two parcels' requests.
- **Its findings on the lead's own work, all smaller:** three mutants of the generator survived the tests, among them `MAX_ROWS` rendered from `max_filters`, which is the "two facts that share a value today" the definition's own comment warns of; the ranges of two new bounds were untested at their ends; `drop_tests()` compared names by case, where pytest on Windows does not; and the rule that a parcel's test is not named `test_p0_*` was in the round's ledger and not in the tree.
- **After the fixes**, in throwaway copies: the mutant reading `MAX_ROWS` from the wrong key fails 2 tests; `MAX_HIST_BINS` written as a constant fails 1; each of the two widened ranges fails 2. A test file named in upper case is dropped from the control's copies.
- **The gate**, `bash verify/run.sh`, Windows desktop, `python` 3.12.15: at `adb10d1` on a clean tree, VERDICT: PASS, 16 of 16, `OK model-tests: 124 tests ran, 0 failed, 0 errored, 0 skipped`; with this commit's changes in the tree and this entry not yet appended, VERDICT: PASS, 16 of 16, `OK model-tests: 136 tests ran, 0 failed, 0 errored, 0 skipped`. The commit itself was made only on a second run's verdict line.
- **The conventions page's worked answer** was written by hand and then run by machine by the lead: coefficients 1, 2, 3 on the stream 0, 0, 1, 2, 3, 0, 0 give 0, 0, 3, 8, 14, 8, 3, and reversed they give 0, 0, 1, 4, 10, 12, 9.
- **A source outside the project for the noise generator's known answers**, for parcel MOD-A's row: the lead fetched one public wiki page (397,045 bytes, SHA-256 `760ef27b...4f14`, 2026-11-23 08:24 -0700) and found in its bytes the five words for seed 1234567, the five counts for seed 987654321, and the generator's three constants.

### Changed after the verifier's pass, and not seen by it

The cases and the test added to `tests/test_p0_generator.py`; the lower-case comparison in `drop_tests()` and two sentences of that file's docstrings; the sentence in CLAUDE.md; this entry. No constant and no check of the generator changed.

### What this does not prove

- **That the bounds are right.** They are the values one parcel's width argument is worked at. That argument is checked when its parcel is.
- **That anything holds the conventions.** The page says so in its third paragraph. The seam tests of the second wave are to hold them, and the page goes past a verifier with those tests.
- **That a generator writes `INJECT_ROUNDING` from the definition.** One value is accepted, so a generator that wrote it as fixed text passes every test there can be. The same is true of the two quantising constants. The test's docstring says so.
- **That the blinding held**, beyond what the next section measured.

### The lead's slips

- **The verifier's clone kept its remote and its reflog.** The earlier clones had neither. In this one `git reflog` shows the unplanted commit, and one `git diff` would have shown all four plants. Measured afterwards from the verifier's transcript: none of its tool inputs mentions the reflog, the remote or the unplanted commit's id, and none names a path in the lead's checkout; its report gives the probe or the comparison that found each plant. So the count of 4 of 4 rests on that transcript, not on the clone having made the shortcut impossible.
- **CLAUDE.md's trap 7, two hours after writing it.** The script that planted the clone was first written through a shell heredoc and lost a level of backslashes. Its own count check stopped it before it committed anything; the half-made clone was removed and the script rewritten as a file.
- **A sentence in the definition's first draft counted "four bounds below"** where three were below and one further down. Caught on rereading, before the commit.

### Not done, and why

- **No verifier has seen the conventions page.** It is a statement of decisions already in the ledger, and it is checked with the tests that will hold it.
- **`spec_version` was not raised.** Nothing built has carried version 1 out of this tree, and `SPEC_SHA256` names the definition exactly.
- **Nothing pushed.**

## 2026-11-23 - round 1, parcel LCH, part B: a first look at real records of one launch

Parcel LCH's second phase is merged into `r1` as `06e14a6` (the parcel's commits `a1aae8f`, `f2398a2`, `f7029cf` and `cf3259a`): [studies/D1b-first-look.md](studies/D1b-first-look.md), with the scripts that fetch, read and measure under `docs/studies/d1/`, the manifest of what was fetched, and two figures. It ran under Logan's word of 2026-11-23 that downloads are permitted. **It is a look at one launch with two control days. It scores nothing, and it is not a rate.**

### What changed

- The first look: 50 minutes of record from seven stations of a regional network, 16.5 to 275 km from the pad, on the launch day (2021-09-14, launch at 03:55:50 UTC by the catalogue) and on the day before and the day after; the launch catalogue; three listings of local earthquakes.
- A reader for the records' format written for the study, held against a second, independent reader.
- Eleven rows of study D1 restated from what the records showed, each saying what it said before.
- No fetched file is committed. The manifest lists each request with its time, size and SHA-256: 43 requests, 38 files, 25,134,897 bytes.

### What ran

- **LCH**, on the lead's model: the first look (114 tool calls, 37 min 3 s, as the harness reported, with the send-back on part A), then a send-back after its verifier's pass (21 tool calls, 5 min 34 s).
- **VLCH**, the study's verifier on Sonnet: a third pass, on a sealed clone holding the first look as one commit with **five planted faults** (20 tool calls, 5 min 8 s); then a fourth, scoped to the fix commit, with nothing planted (6 tool calls, 1 min 50 s). Both reports are filed verbatim under the round's `reports/`, with the key.

### Measured

- **Plants: 5 of 5 reported.** A duration its own table contradicted, a measure chosen after looking presented as fixed beforehand, a sentence saying nothing else could have made the signal, a catalogue count, and an average that did not follow from its inputs. Model: Sonnet. The clone was sealed, and none of the verifier's tool inputs names the parcel's commits, worktree or branch.
- **The measure was written before the data was fetched.** From the parcel's transcript, by the lead: the ledger entry holding the measure was written at 08:11:28 local time; the first waveform request in the manifest is at 08:14:01. The code that applies the measure was written after the records were on disk. The verifier set that code beside the ledger's text and found it to be that measure.
- **What the parcel reports, by that measure** (power between 2 and 8 Hz in 4-second frames, as a ratio to the median of the ten minutes ending a minute before the launch; the median ratio over the window in which sound from the pad was predicted to arrive). Launch day, then the day before and the day after:

  | station | km | launch day | control days | reading by the rule fixed beforehand |
  |---|---|---|---|---|
  | CI.LOC | 16.5 | 614.02 | 1.47, 0.72 | seen |
  | CI.LCP | 32.6 | 440.16 | 0.56, 1.49 | cannot tell |
  | CI.SYN | 49.9 | 88.08 | 0.89, 0.80 | seen |
  | CI.MPP | 78.5 | 843.99 | 0.79, 1.43 | seen |
  | CI.CDM | 120.4 | 1.65 | 1.03, 1.05 | cannot tell |
  | CI.HDH | 181.4 | 0.95 | 1.41, 1.08 | nothing visible |
  | CI.SRN | 275.0 | 0.94 | 0.74, 1.13 | nothing visible |

  The rule reads "cannot tell" at 32.6 km because one control day has a ten-second stretch in the window, and at 120.4 km because a stretch begins at the same second on the launch day and the day before.
- **The same, by the verifier's own measure and code** (mean power between 2 and 8 Hz from 60 to 420 s after the launch time over the mean from 600 to 60 s before). Day before, launch day, day after: LOC 1.05, 860.9, 0.93. LCP 0.42, 264.2, 1.54. SYN 1.00, 53.7, 1.01. MPP 0.84, 220.4, 1.67. CDM 1.07, 1.23, 1.00. HDH 5.13, 0.39, 5.66. SRN 0.79, 0.90, 0.82. A different measure, so different numbers; the same four stations stand out on the launch day and on neither control day.
- **The records**, by the parcel's reader and by a second reader, which agree on all 7,500,025 samples; the verifier read all 25 files with the second reader itself: 300,001 samples each at 100 a second, no gap, samples from -36,647 to 35,420. **Two of the 25 files hold samples that need 17 bits.**
- **The stretch lasts 270 to 454 seconds** at the four stations, and outlasts every window the study had drawn from a source assumed to last 180.
- **The gate on the staged merge**, `bash verify/run.sh`, Windows desktop: VERDICT: PASS, 16 of 16; `OK claims: 171 register rows in 13 tables in 8 files under docs/, 0 unlabelled`. The study's files on `r1` are byte for byte the parcel's commit.

### Merged with these stated limits

- **The arrival speed is a description, not a test.** The slope fixed beforehand came out meaningless, because one station has an earlier, weaker stretch that the definition of an onset picked up. A slope chosen after looking is 3.02 seconds a kilometre, inside the range for sound through the air; two of its three station-to-station steps are outside that range. Every place the study gives it now says both.
- **The nearest station asked for, 13.5 km, returned no record**, though the archive's listing spans the date. So one of the study's own controls could not be run.
- **One control day is not clean by the study's own rule:** another flight left the base 10.4 hours before it.
- **Every figure is a ratio to a station's own noise in raw counts.** Nothing is in physical units, so "stands out most between 2 and 8 Hz" says where the launch is easiest to see, not where its power is.
- The summary's "far busier" control days at the 181 km station is true before the sound window and not inside it.

### What this does not prove

- **How often a launch is seen.** There is one launch, and it is one the network itself had written up. The plan's row V2 asks for "a predictable lag, at more than one distance": for this launch the signal is at four distances, and the lag's measure was chosen after looking. V2 is supported for one case and is not settled.
- **How often a quiet day looks like a launch.** Two control days cannot say.
- **What made the signal.** The measure sees power in a band at a time. What ties it to the pad is its timing across four stations, by a measure chosen after looking.
- **That a detector would find it.** No detector was run.
- **The digitiser's width.** Samples wider than 16 bits are MEASURED. What the converter's width is stays BELIEVED.

### What this means for the design

D0's row D1 proposes 16-bit samples on one channel. These records are three components, and two of 25 files need 17 bits. The definition already carries a second profile of 24 bits and three channels, which the foundation was built not to hard-wire either. Whether row D1 changes is Logan's to say; the lead puts it to him at the round's close with this evidence.

### The lead's slips, and the parcel's

- **A package index's terms limit who may use it, and the parcel installed from it without that going to Logan.** The terms exclude a person on a sanctions list. The parcel read the page, searched it for a few words, missed the sentence, wrote that nothing limited who may download, and installed nine packages into a virtual environment in its scratch folder. The verifier found the sentence. The parcel says so plainly in its own report. The row now quotes the terms, and the lead has put it to Logan.
- **The install wrote outside the parcel's folder.** pip, run inside the virtual environment, wrote the nine packages it downloaded (36.7 MB) into the desktop's own pip cache. The parcel reported it and did not purge the cache, which holds entries it did not make. The desktop's shared Python is unchanged, by its measurement. The brief said to install into a virtual environment and said nothing of the cache; that was the lead's omission.
- **The brief expected a station service to name the digitiser.** It gives a gain and no width.
- **The brief assumed the nearest station could be fetched.**

### Not done, and why

- **No wider look.** A second launch with every definition fixed first, more control days, the nearest station's other channels, the infrasound stations: the study lists these, and none was run. That is a decision for the next round's plan.
- **Distant large earthquakes in the three windows were not checked.** The national catalogue's policy pages answered 403, so its terms could not be read, and it was not queried.
- **Nothing pushed.**

## 2026-11-23 - round 1, wave 1: the reference model's parts and the statistics, three parcels, each past a verifier

Three parcels built to one interface without seeing one another's code, and are merged into `r1`: MOD-A as `b1e0bc2`, MOD-B as `f48efa4`, STAT as `9ee6fb4`. With them the reference model exists in software, and so does the second authority that judges sensitivity. **Nothing of the system exists: no RTL, no host library, nothing on the card.**

### What changed

- **MOD-A**, `model/source.py` and `model/inject.py`: seeded integer noise from a counter-based generator and a 63-bit table of a discrete Gaussian; a recording format and its replay; an injector that adds a known pulse, scaled by a fraction and rounded half to even, where a schedule of truth records says, and refuses a sum outside the range where another design would clip. Gates: injection, replay, noise-tails. [model/mod-a.md](model/mod-a.md).
- **MOD-B**, `model/detector.py`, `model/weights.py`, `model/scorer.py`: a filter bank, a rectifier, a pool, one linear head and a shifted score, every width derived from the definition; the quantising rule in exact integers; a configuration blob; a store whose weights swap at a named output index; a scorer with a strict threshold. Gates: reference-model, swap, refusal, overflow, scorer. [model/mod-b.md](model/mod-b.md).
- **STAT**, `stats/`: D8's formula; a floating-point matched filter that imports nothing of `model/`; the tolerance a measured efficiency is judged by; the script for D0's row D11; and [sources/D8.md](sources/D8.md), what was read of D8's source and by whom. Gate: statistics. [model/stat.md](model/stat.md).
- Before them, the lead's: `adb10d1`, the definition gaining what two parcels' designs asked for (an earlier entry), and [model/conventions.md](model/conventions.md), four conventions ruled while three parcels each needed the same answer.

### What ran

- Each parcel on the lead's model, **design first**: a design in the round's ledger, the lead's rulings on it, then the build. MOD-A 168 tool calls and 73 min 34 s, as the harness reported; MOD-B 102 and 57 min 11 s; STAT 147 and 63 min 54 s. MOD-B and STAT each then made one send-back commit.
- **Three verifiers on Sonnet, one a parcel, on sealed clones** (the parcel's commits as one commit, no remote, no reflog, the parcel's own commits not in the clone): VMODA one pass; VMODB two; VSTAT three. Reports and keys are under the round's `reports/`.
- **The lead's own faults first.** Before planting, the lead tried candidate faults one at a time against each parcel's tests in throwaway copies: MOD-B's tests reported all ten, STAT's all eight, MOD-A's all eight. So every code fault planted for a verifier needed a test changed beside it to keep the gate green.

### Measured

- **Plants: VMODA 5 of 5. VMODB 5 of 5. VSTAT 3 of 4, then 3 of 3.** The miss: a wrong figure in a table of STAT's document, in a pass whose report said "the by-hand table matches" after checking two of its columns. The lead scoped a second pass to exactly that: every table cell and every register row set beside a number the verifier produced. That pass found a wrong figure of the parcel's own.
- **Wrong answers of the parcels' own, found by the verifiers:** MOD-B, one row of its document's refusal table naming the wrong refusal. STAT, one exact figure wrong in its fourth digit (0.3146 for 0.3143) behind a test that allowed 0.0005; the parcel's own sweep then found three more figures in its tests behind loose allowances, and cut fifteen allowances to half a last digit. MOD-A, none.
- **What the verifiers measured by their own roads.** VMODA: its own generator, written from the public page, matched the model on 2,000 random seed and index pairs; its own table in 80-digit decimal matched every entry at five sigmas; every single flipped bit of three recordings refused. VMODB: three cases worked by hand that the core matched, one with two channels, an absolute value and a pool, one with a swap; every case of two vector files matched an evaluator of its own; the design's ten items and the lead's eight rulings each found in the code. VSTAT: its own Q and inverse agree with the package to 2.4e-15; its own simulation, 2,000,000 trials with its own seed, sits 0.24 standard errors from D8; the gate's seeds changed three ways with every gate test still passing.
- **The scorer's widths** (MOD-B, checked by hand by its verifier): under the 16-bit one-channel profile the filter sum needs 41 signed bits, the pool 57, the head 77; under the 24-bit three-channel profile 50, 66 and 85. The core is run at its true extreme inputs once a profile and reaches exactly the last bit of each width; a core one bit narrower overflows.
- **The noise's tail, the long run** (the lead's, booked on the TimeSheet, made at MOD-A's merged commit): 2^30 draws, one channel, sigma 1000, the seed MOD-A's design named before any run. Every count from 1 to 5.42 sigma, on each side, within 4 standard deviations of its expectation; at 5.42 sigma 32 and 40 where 32.1 are expected; the same draws clipped one below that depth are reported. The furthest of twenty counts is 2.5 standard deviations out.
- **The source for D8.** The lead fetched chapter 14 of MIT's 6.011 class notes and read it through text extraction. It states that the correlation test is optimal in the Neyman-Pearson sense and gives the two Gaussian distributions of the test statistic. **It does not write the closed form.** So D8's formula is COMPUTED from what was READ, in two lines, in `docs/sources/D8.md`; one secondary page writes it whole.
- **The plan's row V3** asked whether two model parcels could build to one stream interface without meeting in one file, the gate registry apart. Three did. The only conflict in three merges was `tests/gates.toml`, where each appended its rows; the lead kept every row.
- **The gate at each merge**, `bash verify/run.sh`, Windows desktop, `python` 3.12.15, each with the merge staged and the commit made only on the verdict line: MOD-A, VERDICT: PASS, 16 of 16, 277 tests; MOD-B, PASS, 433 tests; STAT, PASS, `OK model-tests: 656 tests ran, 0 failed, 0 errored, 0 skipped`, `OK independence: 9 module(s) in model/ and 9 in stats/ import with the other blocked`, `OK registry: 10 gate row(s), each with its test and its control; 91 gate-claiming test(s), each with a row`. For each parcel the files on `r1` are byte for byte its commit.

### Merged with these stated limits

Each parcel's document lists its own: 25, 19 and 17. Beside them:

- **One linear head with no bias.** This model cannot represent a detector that needs a hidden layer. D0's words are "a small dense head". The lead accepted it for round 1 and has put it to Logan.
- **One amplitude on every channel.** The injector cannot make a signal whose strength differs between channels. The first look at real records (the entry before this one) shows such signals: the three components of one station differ.
- **The scorer is fixed when it is made.** Nothing changes its threshold or reads its histogram mid-run, where D0 speaks of a threshold register.
- **A detector wrong by less than the catch margin can pass the statistics.** At D0 row D9's 10,000 injections that margin is 0.04 in efficiency; a detector 0.01 below D8 passes 97.7% of the time. D9's figure is a standard error, and is not a strong check.
- **The gate counts the noise's tail to 4.0 sigma; the long run to 5.42.** Beyond that the claim rests on the table and on the boundary-word test, and D0's row D7 is one bound on a false-alarm claim and not the bound: a score's tail also needs the samples to be independent, which no single-sample test shows.
- **A schedule or a stream that cannot be iterated gives a TypeError from the injector**, not a refusal by name. The parcel's document says so.
- **The published words the generator is held to come from a wiki**, read by the parcel through a rendering and found by the lead in the page's bytes.

### What this does not prove

- **That the model is the right model.** It does what its design says, by tests and three verifiers. Whether that design finds faint signals is the experiments' question.
- **Anything about a fabric.** Bit identity needs RTL, a host library and the card. Five of D0's sixteen gates wait for those.
- **That the verifiers' blinding held, beyond what was measured.** The clones were sealed. The round's ledger, which each brief has its verifier read, says that the clones hold planted faults. For VSTAT and VMODB the lead read the transcripts afterwards: no tool input reaches for the unplanted work. VMODA's transcript was empty and could not be read.
- **That a verifier's "confirmed" covers what it did not do.** Each report ends with what was not done, and VMODB's first pass used nine minutes of an hour. Its second covered its own list.

### The lead's slips

- **A wrong sentence in the conventions page**, found by MOD-A: that an injection changes every frame of its span. The reference pulse has nine zero samples. Restated in `948c8cc`.
- **A hole in the lead's own foundation**, found by MOD-A: `model/stream.py` took a subclass of tuple as a frame, so a frame object could carry more than its samples. Closed at the seam, in the next entry.
- **The brief gave the pulse's peak as 1000.** It is 970.
- **Two briefs' errors on STAT's side**: that row D11's 0.284 was D8's figure at d = 1.75 (it is 0.2822), and that a float in the document was a case a zero-width guard fails (it is not).
- **The plan said the gate runs in seconds.** With the model's tests it takes over a minute. CLAUDE.md is restated.

### Not done, and why

- **No hidden layer, no per-channel amplitude, no second pulse.** Each is a stated limit and a decision for the next plan.
- **Nothing pushed.**

## 2026-11-23 - round 1, wave 2: the seam, truth isolation, and stage E0 in software

The lead's own parcel. The parts of the reference model are joined in one place and run together for the first time, the eleventh and last gate the round builds is in the registry, and the run the plan's row V1 turns on has been made. **This entry is written before any verifier has seen the seam.** That pass is the next entry's.

### What changed

- `model/run.py` (`29ab2a0`): the one place the parts meet. Frames go to the injector, the injected stream to the detector core, the truth records to the caller and to nothing else. The profile is the blob's own.
- `tests/test_seam_conventions.py` and `vectors/seam/`: [model/conventions.md](model/conventions.md) held on the parts run together, against answers worked by hand; one pulse giving the same coefficients in `model/` and in `stats/`; and, on one stream, the integer core and the floating-point matched filter giving every score equal.
- `tests/test_seam_isolation.py`: the truth-isolation gate, and tests of the runner itself (`2be71da`).
- `tests/test_seam_e0.py`: stage E0 in software, a short form in the gate and the full run as a script.
- `model/stream.py`: a frame is now exactly a tuple. One test of parcel MOD-A's and one sentence of parcel MOD-B's document leaned on the old behaviour; the lead changed both, after their merges.
- D0's rows D8 and D11 restated, with what each said before kept at the end of that file; the plan gains what the round found against its value statements.

### What ran

- The lead, in a scratch clone of `r1` with the three parcels merged, before they were merged for real; then on `r1`.
- **Eleven faults planted by the lead in copies of the tree, one at a time**, each a convention or a property of the runner broken on purpose: the core reading its coefficients newest first; the scorer counting a score equal to its threshold; the injector a frame late; the statistics filter not reversed for numpy's convolution; the core dropping a channel's row; the frame check taking a subclass again; the runner handing the injector no schedule; the runner dropping its start epoch; the runner checking the schedule before the blob; the runner handing on the input frame in place of the injected one; a tie rounded upward in the model's quantiser.
- **The full run of stage E0**, booked on the TimeSheet: five processes, one an amplitude, from a scratch clone detached at `29ab2a0`.

### Measured

- **Each of the eleven planted faults was reported by a seam test**, by 1 to 15 failures.
- **The seam tests of the conventions passed at their first run** on the three parcels' code as merged. That is the plan's row V3 at its sharpest: the parcels did not see one another's code. Of the hand-worked answers, the conventions page's was written before any parcel reported; the two-channel case was worked by the lead afterwards, on paper and without running the code; the tie set is one that parcel MOD-B's own vectors use too. Two of the lead's other tests did fail at first, each on the lead's own expectation: which scores a pulse moves (123 a pulse, not 125, because the filter's first and last coefficients are zero as the pulse's first and last samples are), and the tagged frame before the frame check was tightened.
- **Bit for bit, between two implementations that share no code.** On one stream of 4,000 frames with seven injections, under each profile, every score of the integer core equals the score of `stats/`'s floating-point matched filter with the same integer coefficients. In the full run the same holds for all 2,000,000 scores read.
- **Truth isolation.** The same samples under four other sets of truth records (none; the real indexes at amplitude zero; other indexes at amplitude zero; one record too faint to add a sample) give score records with one digest, and a scorer's events with one digest, under both profiles. A runner made in the test, which sets the lowest bit of the score on the frame where a truth record says a pulse begins, is reported.
- **Stage E0 in software, the full run.** Profile `s16x1`; the model's own noise at sigma 1477; the reference pulse every 128 frames; the score read at the truth index + 63; D8's own threshold for a false-alarm probability of 0.01, from the noise law's exact variance; 200,000 injections an amplitude, a seed for each, named in the round's ledger before any run. `python tests/test_seam_e0.py --judge` printed:

  | amplitude | seed | d | D8 | found | efficiency | from D8 | tolerance | |
  |---|---|---|---|---|---|---|---|---|
  | 1/2 | 2026112300 | 1.1634 | 0.1224 | 24,442 | 0.12221 | -0.30 se | 0.00293 | INSIDE |
  | 3/4 | 2026112301 | 1.7450 | 0.2805 | 55,857 | 0.27929 | -1.22 se | 0.00402 | INSIDE |
  | 1 | 2026112302 | 2.3269 | 0.5002 | 99,743 | 0.49872 | -1.33 se | 0.00447 | INSIDE |
  | 5/4 | 2026112303 | 2.9087 | 0.7198 | 144,075 | 0.72037 | +0.53 se | 0.00402 | INSIDE |
  | 3/2 | 2026112304 | 3.4903 | 0.8778 | 175,622 | 0.87811 | +0.46 se | 0.00293 | INSIDE |

  Noise alone, at the same threshold, one signal-free score a trial: 1,929, 1,974, 2,008, 2,041 and 1,987 of 200,000 cross, which is -1.60, -0.58, +0.18, +0.92 and -0.29 standard errors from 0.01. Its last line: `== E0 SOFTWARE VERDICT: PASS, every amplitude inside D8's tolerance`. SHA-256 of that output: `3bf1c6f3...5479e`. The parts and the output are kept under the round's `reports/e0/`.
- **The cost of quantisation, measured on the same streams:** with the pulse itself as the coefficients, never rounded, the floating-point filter finds exactly the injections the model finds, at every amplitude. No injection in 1,000,000 is found by one and not the other.
- **No record of the run carries a flag.** Nothing overflowed and nothing settled.
- **The gate**, `bash verify/run.sh`, Windows desktop, `python` 3.12.15, each time with the commit's changes in the tree and the commit made only on the verdict line. For `29ab2a0`: VERDICT: PASS, 16 of 16; `OK model-tests: 699 tests ran, 0 failed, 0 errored, 0 skipped`; `OK registry: 11 gate row(s), each with its test and its control; 102 gate-claiming test(s), each with a row`; 75 s by the wall clock. For `2be71da`: VERDICT: PASS; `OK model-tests: 703 tests ran, 0 failed, 0 errored, 0 skipped`.
- **The gate's short form of E0**, 4,000 injections at amplitude 1: 1,999 found, -0.06 standard errors from 0.5002, inside a tolerance of 0.0316; noise alone 30 of 4,000. On the same samples, the coefficients reversed find 0, and the score read one sample late finds 1,697, which is 9.6 standard errors low: each beyond the catch margin.

### Which authority this rests on

**Sensitivity**, by D8 and the statistics package's tolerance. The plan's row V1 said the round was worth running if the model, as a matched filter, reproduces D8's curve at the injected index within D9's tolerance plus the measured cost of quantisation. It does.

It is **not** evidence that any fabric is correct. Nothing here is bit identity against hardware: there is no hardware side. The exact agreement between the core and the floating-point filter is agreement between two pieces of software.

### What this does not prove

- **Anything about learning.** The coefficients were set, not learned.
- **Anything about real records, coloured noise, a second pulse, the three-channel profile, or a filter longer than its pulse.** One pulse, one noise level, one profile.
- **That the threshold would hold if it were measured.** It was known, from the noise law's variance. The statistics package's tolerance for a measured threshold is wider, and this run did not use it.
- **Isolation against a detector that goes looking.** The injected stream is a Python generator, and code written to look inside it can find what is about to be added. The gate shows that a runner which lets truth reach the output is caught, and no more.
- **The conventions beyond the cases run**, which are small or are the reference pulse.
- **That the seam is right.** It is the lead's own work and no verifier had seen it when this was written.

### The lead's slips

- **The first commit of the seam had no test of the runner's own arguments.** A runner that dropped its start epoch, or checked the schedule before the blob, passed every test in `29ab2a0`. The lead found that while choosing faults for the seam's verifier, and `2be71da` adds the tests.
- **One result was seen before the full run:** a trial of 20,000 injections at amplitude 1 with a seed that is not one of the experiment's, made to check that the script ran. No seed and nothing else about the experiment was changed after it.
- **The seeds first named for E0 were replaced before any run**, on a fact from parcel MOD-A: one seed under five amplitudes puts the same noise under each, and the seed first named is the stream the noise-tails gate counts.
- **The lead edited two parcels' files** in the seam's commit. Disclosed there and here.

### Not done, and why

- **No verifier's pass yet.** It follows, on the round's tip, with planted faults.
- **The integration verifier has not re-made the merges.** The same pass.
- **Nothing pushed.**

## 2026-11-23 - round 1, the close: a verifier on the seam, the merges and the record

The lead's own work since the parcels merged went past a verifier, VSEAM, on the round's tip. This entry is what it found, what was fixed, three corrections to earlier entries, and what the round cost. **`r1` is local. `main` has not moved and nothing is pushed: that is Logan's word to give.**

### What ran

- **VSEAM**, a new agent on Sonnet, 75 minutes allowed, on a sealed clone of `r1` with its history whole and **five faults planted in the tip commit** (70 tool calls, 22 min 24 s, as the harness reported). It was asked to re-make each merge from its parents, to attack the seam and the isolation gate with leaks of its own, to set the experiment's code beside its text, to reproduce one part of the full run of stage E0, and to check the record's figures against the runs' outputs. Its report and the key are under the round's `reports/`.

### Measured

- **Plants: 5 of 5 reported.** Model: Sonnet. Read the next line with it.
- **That count measures less than it says.** The lead planted by amending the tip commit, which only added ledger entries and restated documents. Four of the five faults were in files that commit did not otherwise change, so the commit's own diff showed each as a change with no reason to be there. The verifier found two that way and said so during the pass; its report then gives for each of the five a check that finds it without the diff. The fifth, a wrong count inside a ledger entry the tip commit itself added, could not be found that way, and was found: 99,473 where the run printed 99,743. The lead wrote this weakness in the round's ledger before the report came back.
- **The five merges, re-made from their parents by the verifier.** Three merge cleanly and equal the round's merge commits exactly. Two, MOD-B's and STAT's, conflict in `tests/gates.toml`; as parsed rows each of the round's resolutions is the first parent's rows followed by the second parent's new ones. Every file each parcel's own commit changed is byte for byte in its merge.
- **The lead's recorded run of stage E0 reproduces.** In its own copy, at the seam's code and under the stated seed, the verifier's run of part 2 gave every field of the lead's record: 99,743 found of 200,000, 2,008 noise crossings, the same threshold, the same SHA-256 of the stream. The judge on the lead's five parts printed the recorded output byte for byte.
- **D8's figure at each amplitude, by the verifier's own arithmetic**, importing nothing of `model/` or `stats/`: 0.122433, 0.280508, 0.500206, 0.719840 and 0.877777. Its own threshold: 1595666164.0556, so the integer the run used, 1595666164, counts exactly the scores above the real one.
- **Three leaks of its own against the isolation gate**, through a record's flags, its epoch, and one score changed by one in the middle of a pulse: each reported, under both profiles.
- **No regression.** Each parcel's own tests give the same counts on the tip as at the parcel's commit.
- **Two false sentences of the lead's**, both in the record, both now restated:
  1. The roadmap said "six parcels merged, each past a verifier". Five parcel merges were; the seam was the lead's and had been past none when that was written.
  2. The roadmap, and the plan's note on row V2, said the launch was "plain at four stations ... by a measure fixed before the data was fetched". By the rule fixed beforehand it is seen at **three** stations, 16.5, 49.9 and 78.5 km. At the fourth, 32.6 km, the launch-day figure is as large and the rule reads "cannot tell", because a control day has a ten-second stretch there. The lead had claimed the fourth for the rule.

### What changed after the pass

- The two sentences, and the plan's "three merges conflicted" (two did).
- `tests/test_seam_isolation.py`: a fifth other truth, which varies the amplitude's denominator; a refusal that happens under one truth and not another is now a finding, where it went out of the check as an exception; and the file's list of what the gate cannot see gains what the verifier showed it cannot: a leak keyed on a feature of the truth that none of the schedules varies.
- `tests/test_seam_e0.py`: the judge of the full run now holds each part to the experiment as stated: one part an amplitude, each under its own seed, with the stated threshold, deflection, length and definition, no two on one stream. Before, it read only the counts, and five parts made under one seed would have been judged PASS. Eight ways of not being the stated experiment are each judged FAIL in a new control. The lead's recorded parts are judged again: PASS, and the first eighteen lines of the output are the recorded ones.
- One sentence of parcel MOD-A's document that the lead's edit at the seam had left stale, and a comment in MOD-A's test saying what that edit gave up.
- CLAUDE.md: three traps.

### Corrections to earlier entries

- **The entry for LCH's part B** says, under what it does not prove, that "the signal is at four distances". By the rule fixed beforehand it is at three, as that entry's own table shows; the fourth is by the numbers. The same slip as the roadmap's.
- **The entry for wave 1** says the long run of the noise's tail was "made at MOD-A's merged commit". It was made at the parcel's own commit, `097ead6`, in a scratch clone, before the merge. The parcel's files in the merge are byte for byte that commit's.
- **The entry for wave 2** says no verifier had seen the seam. This entry is that pass.

### Merged with these stated limits

- **The isolation gate sees a leak only through what its schedules vary.** They vary whether there is a record, its index and its amplitude's denominator. One pulse is declared, so they cannot vary the pulse; and every one adds nothing to the samples. The verifier's two leaks keyed on other features passed.
- **The lead's edit to MOD-A's test** no longer catches an injector that hands its input objects on unchanged. That is harmless only while the frame check stays as strict as it now is.
- **The verifier did not derive the noise law's exact variance itself**, did not rerun four of the five parts, and did not check this ledger's tallies of the earlier verifiers.

### What the round cost

By the wall clock, about three and a half hours on 2026-11-23, from the round's first TimeSheet notice at 07:06 to this entry.

Agents, as the harness reported each at its last pass. **What these token figures count is not established here**, and the lead's own use is not among them.

| agent | passes | tool calls | time, summed | tokens, at the last pass |
|---|---|---|---|---|
| LCH, the launch study | 3 | 322 | 1 h 24 min | 863,567 |
| MOD-A | 1 | 168 | 1 h 14 min | 566,991 |
| MOD-B | 2 | 127 | 1 h 6 min | 537,872 |
| STAT | 2 | 170 | 1 h 12 min | 589,887 |
| VP0, the foundation's verifier | 4 | 86 | 34 min | 354,834 |
| VLCH | 4 | 93 | 18 min | 390,393 |
| VMODA | 1 | 33 | 9 min | 145,078 |
| VMODB | 2 | 73 | 19 min | 259,214 |
| VSTAT | 3 | 54 | 17 min | 227,891 |
| VSEAM | 1 | 70 | 22 min | 209,092 |

The plan's verifier, VP1, ran before the round opened and is in the entry for the plan. Machine time booked on the TimeSheet: the long run of the noise's tail, four processes for six and a half minutes; the full run of stage E0, five processes for seven minutes.

**Planted faults from the foundation onward: 40 planted, 39 reported**, by six verifiers on Sonnet, across nine passes that carried plants (4, 4, 5, 5, 5, 3 of 4, 3, 5 and 5). The plan's verifier, before the round opened, reported 5 of 5. The one miss was a wrong figure in a table, in a pass that reported the table as checked after checking two of its columns; the pass that followed was scoped to exactly that.

### What this does not prove

- **That a second verifier would find nothing.** One pass, by one model, whose blinding was weaker than its count suggests.
- **Anything the earlier entries say is not proved.** No hardware, no learning, one launch.

### Open with Logan

In [ROADMAP.md](ROADMAP.md): the push; the detector's head; D0's row D1; a package index's terms; Raspberry Shake's licence; what round 2 is.

### Not done, and why

- **`main` has not moved and nothing is pushed.** The lead asks first.
- **The parcels' worktrees and branches are kept**, under the ignored `Data/worktrees/`, until Logan has seen the round.

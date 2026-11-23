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

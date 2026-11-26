# Learning in the fabric on the card: the host's side

Parcel LRN-C, round 5, 2026-11-26. It covers everything the card day for round 5's learner needs except the card itself, which is the lead's: the host library taught the learner, `host.run_case` taught a learner's script, the experiment and its cases, the model's expectations, the box's script, a stand-in for the card in the first size, and the judge. The code is `hw/lrnc/`, with additions to `host/`; the tests in the gate's first size are `tests/test_lrn_c_*.py`. The design was approved by the lead on 2026-11-26 at 03:57 with its seven answers (the round's ledger, not committed). Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure here is in the register at the end.

**What a pass rests on: bit identity, and its authority is the model.** On the card, the kernel's own learner trains from the windows the card's own injector labels, makes its set, writes it into the core's shadow, and the host commits it. The judge holds three things to `model.learner` run as `model.run.learning` runs it, word for word: every record the card writes, the outcome of every host operation, and the learner's counters and status at the end. **It is not evidence about sensitivity.** The learner's set is the difference of two class means, and whether that set finds faint signals is stage E1's question, answered in software (`docs/studies/E1-software.md`), not here.

**What has been run.** Everything here in the first size, on the desktop: on the model, and on a stand-in for the card (`hw/lrnc/standin.py`), at M = 1,024 and 2,048 frames; and one case's expectation at M = 2^18. **Nothing of LRN-C has run on the box or on the card.** The wired kernel is parcel KRNL-L's and was not built when this was written. This work follows the definition's register map (`spec/`, 0xD00 to 0xDFF), [the learner's RTL document](../rtl/learn.md) section 3, and four facts of the wired kernel. The lead ruled those facts as requirements on KRNL-L (2026-11-26 03:57), and KRNL-L's design confirmed them (03:58):
- (a) `krn_reset` resets the learner with the chain. KRNL-L states it as a reset in behaviour, not in storage: the registers and the memories' pointers are cleared; the delay buffer's and the truth store's contents are not, but no stale entry is ever read.
- (b) A learner refusal latches in `lrn_refusal` only. It never ends a run, and never touches `krn_refusal` or `krn_status`'s refused bit. A host write that `learn_port` holds back is answered OKAY on AXI-Lite; its name is in `lrn_refusal`, and the core's `refusal` reads 0 for it.
- (c) The caps read 32 and 256.
- (d) The learner's truth is the injector's taken records only.
A write the kernel itself refuses (its strobes not all four, and so on) never reaches the learner: it is `krn_refusal` REGISTER_ACCESS, and no update is named.

## 1. Where things are

| what | where |
|---|---|
| the learner's calls of the host library | `host/library.py`, `LEARNER_PROCEDURES` |
| the learner's capability registers as words, for a test's identity | `host/fake.py`, `LEARNER_BUILD`, `learner_words` |
| a learner's script, run while the run goes | `host/run_case.py`, `--learn` |
| each operation's window, and the model's run of a placed script | `hw/lrnc/windows.py` (desktop) |
| the cases, the expectations, the judge, the short day | `hw/lrnc/lrnc.py` (desktop) |
| the first size's stand-in for the card | `hw/lrnc/standin.py` (desktop) |
| LRN-C's own refusal names | `hw/lrnc/errors.py` |
| the card day's script for the box | `hw/lrnc/box_lrnc.sh` (box) |
| the tests | `tests/test_lrn_c_library.py`, `test_lrn_c_run_case.py`, `test_lrn_c_windows.py`, `test_lrn_c_standin.py`, `test_lrn_c_judge.py`, `test_lrn_c_box.py` |

No row is added to `tests/gates.toml` (the lead's ruling, question 3): these are plain `test_lrn_c_*` tests, as E1C's are, and D0's gate "learner" is held by the stage `rtl-benches`. Nothing under `rtl/`, `spec/`, `docker/`, `model/`, `learn/`, `stats/` or `hw/e0c/` changed, and of `host/` only the additions named here.

## 2. The host library learns the learner

The learner's calls are methods of `host.library.Library`, listed in `LEARNER_PROCEDURES`. **`PROCEDURES` is the fourteen names it was**: the two drivers of `host/drive.py` are made from it, and `tests/test_host_drivers.py` holds it at fourteen. The learner's calls are driven by `host.drive.run_by_calls` (XRT's driver; `host.run_case` uses it) and `run_by_coroutines` (a bench's), which take any procedure. `host/drive.py`, `host/ops.py`, `host/backend_xrt.py` and `host/xrt_shim.cpp` are unchanged: the learner is registers, reached by the seam's Read, Write and WriteMany. The rule is the library's own: what a call can know from its inputs and the capability registers is refused before any write; what depends on the learner's state is read back by name, cleared and raised; a code latched before the call is raised with nothing written.

| call | refused before any write | then | read back |
|---|---|---|---|
| `lrn_open(count_bits, update_frames)` | LEARN_BOUND: `lrn_cap_count_bits` outside 1..32 or `lrn_cap_update_frames` outside 0..256 (the definition's bounds), or either not what the case names. Runs `open` first | nothing written | none |
| `lrn_update(u)` | SWAP_INDEX: u not an int 0..2^64 - 1, or u + the build's F past it; a code latched in `lrn_refusal` | `lrn_update_at`'s lower word, then its upper word, which names it | `lrn_refusal` |
| `lrn_commit(at)` | `commit`'s SWAP_INDEX; a code latched in `lrn_refusal` or the core's `refusal` | `commit_at`'s two words, as `commit` | `lrn_refusal` and `refusal`, the learner's first |
| `lrn_write_shadow(blob)` | `write_shadow`'s: the blob, the build, SWAP_SHAPE; latched as above | the shadow's words, as `write_shadow` | both, as above |
| `lrn_clear()` | none | a write of 0 if a code is latched | returns `lrn_refusal`'s name or None; it does not raise |
| `lrn_registers()` | none | nothing written | `lrn_update_at`, `lrn_status` (its word and six bits), `lrn_refusal`, the eight counts, the two caps |

Every learner call runs `lrn_open` first if it has not run. Each 64-bit counter is read lower word then upper word, one after the other, so the upper word is the one the lower read held ([learn.md](../rtl/learn.md), section 3).

**A kernel with no learner reads 0 at 0xD00 to 0xDFF** (learn.md, row L9). Round 3's image never gets that far: `open` refuses it, IMAGE_SPEC, by its definition's hash. An image of this definition without the learner passes `open`, and `lrn_open` refuses it: **LEARN_BOUND, "lrn_cap_count_bits reads 0, outside 1..32; ...; no learner answers at 0xD00 to 0xDFF"**, with nothing written. The lead's ruling, question 1, keeps IMAGE_SPEC as the name for an image of another definition.

## 3. A learner's script, and the windows

`python -m host.run_case ... --learn <script.json> [--count-bits n] [--update-frames n]`. The script is a JSON list, in order, of `{"op": "update" | "commit" | "write_shadow" | "clear", "after": n}`, with `"arg"` an int for update and commit, or `"blob"`, a file beside the script, for write_shadow. Its form is checked before the backend opens, and argparse refuses a malformed one (exit 2, "error:" on stderr), as it refuses any malformed argument; `--learn` with `--swap-blob` is refused the same way. Every other option and path of `run_case` is as it was.

The learner path: `open`; `lrn_open`, which refuses LEARN_BOUND before the reset; `reset`, `load` and `start`. Then each operation, in order:
1. step the run, feeding truth as it goes, until a read of `next_index` is at least its "after";
2. read `next_index`;
3. make the call;
4. read `next_index` again.

**A refusal of the call is the operation's outcome, recorded by name, and the run goes on**, as the model's does. A wait that does not reach its "after" within `--polls` rounds ends the run DEADLINE (exit 3), and that operation is not made. Then `finish`, `lrn_registers` and the records. The PASS line, last, counts the operations and those refused by name. PASS still means only that the run finished and its files are written; whether they are the model's is the judge's call. `report.json`'s `learner` holds the caps, and for each operation its kind, argument and after; its bracket, `next_index_before` and `next_index_after`; its outcome and detail; for a clear, the name it read; the trace's ns before its first operation and after its last; and the rounds it waited. It also holds `end`, what `lrn_registers` read.

**The model makes an operation at an exact next index; the card's host cannot.** The host's write lands somewhere in its bracket. So each operation of a case has a window [lo, hi] of next indexes: in every placement inside it, the outcome, the records and the learner's state are those of the canonical placement, the operation's own "after". The argument, from `model/learner.py` and `model/weights.py` as read:
- the records change only at a commit, at the index its argument names, and an update's set depends only on its u (the sums at u). So a landing can change the run only by changing some operation's outcome;
- an outcome depends only on which of these holds when the operation lands:
  - an update named and not finished, from its naming to u + F;
  - a commit scheduled and not yet made, to its index inclusive, with a pool of 1;
  - the next index against the argument.

  Each interval is fixed by the arguments, except that an update's unfinished interval begins at its own naming, which the host's order puts before its followers.

| operation, outcome | lo | hi |
|---|---|---|
| update(u), taken | the last update's finish; the last commit's index + 1 | u |
| update, commit or write_shadow, UPDATE_UNFINISHED | by order | that update's u + F - 1 |
| update or write_shadow, SWAP_PENDING | by order | the commit's index |
| update(u) or commit(at), SWAP_INDEX | the argument + 1; the last finish; the last commit's index + 1 | by order |
| commit(at), taken | the last finish; the last commit's index + 1 | at |
| write_shadow, taken | the last finish; the last commit's index + 1 | by order |
| clear, reads QUANTISE_INPUT | the unmade update's finish | by order |

And every operation but a clear lands before an unmade update's finish that no earlier clear has read: the fabric latches QUANTISE_INPUT there, and the library would raise it, "latched before this call".

**The argument is held, not trusted.** `test_lrn_c_an_operation_at_its_windows_lo_or_hi_...` moves each operation of the three cases at M = 1,024 to its lo and to its hi: the run is the canonical run in its records, outcomes, counts, status and sets. Moved to lo - 1 and to hi + 1, its own outcome is another. And `expect` runs the model at full scale with every operation at its lo at once, and at its hi at once, and refuses the case, EDGES_DIFFER, unless both are the canonical run.

**The guard, G = M / 256, a DECISION approved by the lead.** Where a window's lo is an update's finish or a pending's end, the case's "after" is lo + G: 4,096 frames, 0.82 ms at 200 ns a frame. The model needs no guard. It keeps the host's first write after a finish off the fabric's own edge, where the learner's last shadow writes and the host's reads share the core's port (learn.md, limit 2).

**The judge requires each bracket inside its window**: before >= lo and after <= hi. An operation outside its window FAILs, "OUTSIDE its window", whatever its outcome (the lead's ruling, question 7).

## 4. The experiment

M = 2^20 frames, 0.2097 s at about 200 ns a frame (the card's rate in [the first card day](../studies/CARD-first-light.md), row C12). Profile s16x1, the card's, at 100 MHz; sigma 1477/1; `e0` at amplitude 1/1; 64 taps (the blank set and the matched filter have one shape); F = 256 and count_bits 32, the definition's, which `lrn_open` holds the build to; `ahead` the build's `cap_inject_pending`, 1,024. **The runs, in this order on the card (`order.txt`): flow, rich, moved, flow again.**

**flow**, E1's own flow and the reported run. E1's layout from frame 0: a trial every 128 frames, its truth record at 64 + 128 t, t = 0 to 32,767. 4,194,304 frames; seed 2026112601; the blank set (`learn.handover.blank_blob`) at epoch 0.

| # | operation | after | outcome | window | margin, frames |
|---|---|---|---|---|---|
| 0 | update(1,048,576) | 0 | taken; made at M from 8,192 windows a label | [0, 1,048,576] | 1,048,576 |
| 1 | commit(2,097,152) | 1,052,928 | taken | [1,048,832, 2,097,152] | 1,044,224 |

Records 0 to 2,097,151 are the blank set's at epoch 0 (every score 0), and 2,097,152 to 4,194,303 the learned set's at epoch 1. At the end: `lrn_count0` and `lrn_count1` 32,768, the three skips 0, `lrn_made` 1.

**rich**: more than one update, each committed, and every refusal the case can provoke. 7,340,032 frames; seed 2026112602; the matched filter at epoch 0, so that the records before the first commit say something. The truth:
- one record at index 0 (its label 0 START, its label 1 taken);
- none from 64 to 2M;
- E1's layout from 2M, j = 2M + 64 + 128 t, t = 0 to 40,959;
- one record more at 2,621,440, frame 0 of a trial: 64 after the record before it and 64 before the next, so that two label-0 windows are BUSY, its own and the next's.

40,962 records.

| # | operation | after | outcome | window | margin |
|---|---|---|---|---|---|
| 0 | update(1,048,576) | 0 | taken; made unmade (n0 0, n1 1: D is 0, QUANTISE_INPUT), latched at its finish | [0, 1,048,576] | 1,048,576 |
| 1 | clear | 1,052,928 | reads QUANTISE_INPUT | [1,048,832, by order] | none |
| 2 | update(3,145,728) | 1,052,928 | taken; n0 8,191, n1 8,194 | [1,048,832, 3,145,728] | 2,092,800 |
| 3 | commit(4,194,304) | 1,052,928 | UPDATE_UNFINISHED, `lrn_early` 1; the run goes on | [by order, 3,145,983] | 2,093,055 |
| 4 | write_shadow(blank) | 1,052,928 | UPDATE_UNFINISHED, the learner's; the core's register 0 | [by order, 3,145,983] | 2,093,055 |
| 5 | update(3,146,240) | 1,052,928 | UPDATE_UNFINISHED | [by order, 3,145,983] | 2,093,055 |
| 6 | commit(4,194,304) | 3,150,080 | taken | [3,145,984, 4,194,304] | 1,044,224 |
| 7 | update(6,291,456) | 3,150,080 | SWAP_PENDING, the learner's | [by order, 4,194,304] | 1,044,224 |
| 8 | write_shadow(blank) | 3,150,080 | SWAP_PENDING, the core's | [by order, 4,194,304] | 1,044,224 |
| 9 | commit(1) | 4,198,401 | SWAP_INDEX, the core's | [4,194,305, by order] | none |
| 10 | update(1) | 4,198,401 | SWAP_INDEX, the learner's | [4,194,305, by order] | none |
| 11 | update(5,242,880) | 4,198,401 | taken; n0 24,575, n1 24,578 | [4,194,305, 5,242,880] | 1,044,479 |
| 12 | commit(6,291,456) | 5,247,232 | taken | [5,243,136, 6,291,456] | 1,044,224 |

Records 0 to 4,194,303 are the matched filter's at epoch 0; 4,194,304 to 6,291,455 the first learned set's at epoch 1; 6,291,456 to 7,340,031 the second's at epoch 2. The second set was made at 5M while the core scored with the first. At the end: `lrn_count0` 40,959, `lrn_count1` 40,962, `lrn_skip_start` 1, `lrn_skip_busy` 2, `lrn_skip_full` 0, `lrn_made` 2, `lrn_unmade` 1, `lrn_early` 1; `lrn_status` made; `lrn_update_at` 0; `lrn_refusal` 0. **Its departures from E1's layout** each serve one counter or refusal, and the lead approved them (question 5):
- the quiet stretch to 2M: an update with no labelled pair, so that the unmade path and QUANTISE_INPUT run;
- the record at 0: START;
- the record at 2.5M: BUSY.

**What a second update adds.** The learner's sets are made from frames and truth indexes, never from scores. So the second set is not made "from the learned scoring". What it adds: an update made while the core scores with the first learned set; a second learner shadow write, over the set the first swap left there; a commit to epoch 2; and `lrn_made` 2. (The brief's phrase was the lead's error, by the lead's ruling.)

**moved**: the lead's control on the card. flow's stream, seed and schedule, with the update one trial later: update(1,048,704) after 0, window [0, 1,048,704]; commit(2,097,152) after 1,053,056, window [1,048,960, 2,097,152], margin 1,044,096. Its set is made from 8,193 windows a label.

**flow again**: flow's case, run a second time, held to flow's expectation.

**If the fabric refuses the blank set** (E1C's card day shows whether it takes it), `python hw/lrnc/lrnc.py cases <folder> --start matched` makes flow and moved load the matched filter at epoch 0 instead, as rich does, with every operation, window and count unchanged (the lead's ruling, question 6). `test_lrn_c_flow_and_moved_from_the_matched_filter_...` runs that day through the stand-in.

**The counts worked by hand.** They come from the window rules (docs/model/lrn-b.md), not from the model, with k = M / 128: flow's update at M sees k windows a label, and its end 4k; moved's update k + 1; rich's updates (0, 1), (k - 1, k + 2) and (3k - 1, 3k + 2), and its end 5k - 1 and 5k + 2. `expect` refuses a case, COUNTS_BY_HAND, whose model counts are not these, and a test holds them at M = 1,024.

**Every refusal the case can meet on the card**:
- update: UPDATE_UNFINISHED (rich 5), SWAP_PENDING (rich 7), SWAP_INDEX (rich 10), and QUANTISE_INPUT at an unmade finish (rich 0, read by rich 1) are provoked. SWAP_SHAPE (the shape is always the matched one), CORE_STOPPED (the core runs from `load`) and WEIGHT_COUNT (no host stream is open) are met only by a fault.
- commit: UPDATE_UNFINISHED (rich 3) and SWAP_INDEX (rich 9) are provoked. SWAP_PENDING (one commit at a time), SWAP_EPOCH (epochs to 2), CORE_STOPPED and WEIGHT_COUNT only by a fault.
- write_shadow: UPDATE_UNFINISHED (rich 4) and SWAP_PENDING (rich 8) are provoked.
- The library's own, before any write: LEARN_BOUND, SWAP_INDEX of an argument, SWAP_SHAPE of a blob, a code latched before the call.
- The run's, as before: INJECT_OVERLAP and RUN_LENGTH (a host behind the stream), RECORD_SLOT, a kernel's refusal. Each ends the run REFUSED.

**Size on the card:**
- 19,922,944 frames in the four runs;
- the longest buffer 234,884,992 bytes, 7,340,032 slots of 32 and the guard, inside one segment (8,388,484 frames, [the host's E0 day](e0c.md));
- 139,266 truth records fed, 135,170 of them while the runs go, one every 128 frames;
- 418,381,824 bytes of records back.

**Time on the card, an ESTIMATE:** round 4's pieces of 6,400,000 frames took 19 to 22 s whole ([CARD-e0.md](../studies/CARD-e0.md), row CE9), 2.97 to 3.44 us a frame. So the four runs are about 59 to 69 s. With health before and after, the copy back and SHA256SUMS, they take **under 15 minutes of the card session**.

**The expectations on the desktop:** `expect` for one case at M = 2^18 made its three runs of 1,048,576 frames in 44.2 s, 71,130 frames a second (MEASURED). At that rate rich's three runs of 7,340,032 frames take about 310 s. **As three processes, one a case, the expectations take about 5 to 6 minutes** (ESTIMATE). They keep the model's records on the desktop, 330,301,440 bytes, so the judge names a differing record without making it again. Each update's entry in `expected.json` also counts its set's ties, the coefficients where |D| x COEFF_MAX over the peak leaves exactly half the peak (limit 15).

## 5. The stand-in for the card

`hw/lrnc/standin.py`'s `LearnerCard` is `host.fake.Registers` with hooks, as E0C's ModelKernel is, and it imports that file's helpers.

**What it collects.** It takes what the host library writes and holds each item against what it was handed, AssertionError otherwise (its own check, not a refusal):
- the noise table and the seed;
- the core's words and its start epoch;
- each truth record, in order;
- each shadow's words.

It is handed the case's whole schedule, because the model's injector and learner take the whole truth before frame 0.

**Its clock.** Each read of `krn_status` steps the model `stride` frames: `model.inject.inject` over `model.source.Noise`, then the learner's `step`, the loop `model.run._learning_run` runs. A frame whose truth record the library has not yet written is an AssertionError.

**The learner's registers** are worked over the model's learner at the next index where the write lands:
- `lrn_update_at`'s upper word is `update(u)`;
- `commit_at`'s upper word is `commit(at)`;
- `shadow_begin` and its words are `write_shadow`.

A refusal is latched where learn.md section 3 latches it, and the reads answer as the fabric's registers would.

**So the stand-in's records are the model's run with each operation at the index where the host's write landed**, and the judge compares them with the canonical run: the windows are exercised, not assumed. It is NOT a kernel, and it models no block. What it does not model is in section 9.

## 6. The judge

`python hw/lrnc/lrnc.py compare <cases> <runs>`, on the desktop, from each run's `records.bin`, `report.json` and log:
1. **Bit identity, run by run:** `hw.e0c.pieces.compare_blocks` against the expectation's hashes, with the model's own records: `IDENTICAL`, or the first differing record with its field and both values.
2. **Each operation:** its outcome against the model's, by name (for a clear, the name it read). It must also be the same kind, argument, blob and after, and its bracket must be inside its window. The margin it left is printed.
3. **The registers at the end:** each of the eight counts; each of `lrn_status`'s six bits, with its word holding no undeclared bit and the same six bits; `lrn_update_at`; `lrn_refusal`; the two caps.

**A key the judge reads that is missing from `report.json` FAILs by its name**, and is never read as the model's value (`op_keys`, `END_KEYS`; *added after the verifier VLRNC, 2026-11-26*). Until then an operation without its `outcome`, or an end without `lrn_refusal`, read as None, which is the model's value there, and the day PASSed. `test_lrn_c_a_key_the_judge_reads_missing_...` and `test_lrn_c_a_register_missing_...` delete every such key alone.
4. **The run's end:** every record written, and the PASS line in its log.
5. **The lead's control on the card, moved:** IDENTICAL to its own model run, and different from flow's expectation first at the record P that the two model runs predict, in the score, at or after the commit at 2M. SEEN only if both hold, at P exactly. At M = 1,024 P is 2,048, the commit's own record, as at M = 2,048 it is 4,096.
6. **The verdict**, `== LRN-C CARD VERDICT: PASS`, only when every run is IDENTICAL, every operation is the model's and inside its window, every register is the model's, every run ended, and moved is SEEN. **Exit 0 only then**; otherwise FAIL, naming the first line that failed, exit 1. It writes `card-lrnc.json`.

flow again is held to flow's own expectation, so the two flow runs, both IDENTICAL, are the same bytes.

## 7. What runs where, and what crosses

- **The box** runs a `git archive` of this parcel's commit: `host/`, `model/`, `spec/`, `hw/e0c/` and `hw/lrnc/`, 471,040 bytes in 47 entries, under Python 3.12.3.
  - Each run is `timeout 900 python3 hw/e0c/run_piece.py` with run_case's arguments, `--learn` among them, and its stdin closed.
  - `hw/lrnc/box_lrnc.sh` reads its runs from `order.txt` in order. It logs a run that ends refused and goes on, takes health before and after (the reports CLAUDE.md's trap 21 names), and writes SHA256SUMS.
  - Besides those runs it runs only `python3 -c` with `json` and `sys`. Nothing of `learn/`, `tests/`, `hw/lrnc/`'s Python or numpy is imported on the box (`test_lrn_c_box.py`).
- **Desktop to box:** the cases folder, 9,549,507 bytes: `table.json` (13,523 entries, 297,286 bytes), each case's `case.json`, `schedule.json` and `script.json` and the two blobs (flow's folder 2,843,254 bytes, moved's 2,843,255, rich's 3,565,664), and `order.txt`. Also, if the lead copies them, `expect/<case>/expected.json`, for the box's own SHA-256 line.
- **Box to desktop:** each run's `records.bin`, `report.json` and log, the day's log, and SHA256SUMS. `trace.json` stays on the box.
- **The desktop** makes the cases (`cases`), the expectations (`expect --case flow`, `--case rich`, `--case moved`, a process each), and judges (`compare`). The expectations' SHA-256 go in the ledger before the card runs.

## 8. The tests, and the named controls with what each printed

| file | holds |
|---|---|
| `test_lrn_c_library.py` | each learner call's operations, written out for one value each; LEARN_BOUND at each bound, for caps of 0 and for a build that is not the case's; SWAP_INDEX and SWAP_SHAPE before any write; a code latched before; each block's code read back, cleared and raised, the learner's first; both drivers the same; PROCEDURES the fourteen; round 3's `commit` on a learner kernel |
| `test_lrn_c_run_case.py` | the learner path's files, report and PASS line; refusals as outcomes and the run going on; DEADLINE; argparse's refusals; LEARN_BOUND with nothing written; without `--learn`, round 3's operations |
| `test_lrn_c_windows.py` | every operation of the three cases at lo, hi, lo - 1 and hi + 1; section 4's tables at M = 2^20, cell by cell; the guard; SCRIPT_WINDOW, SCRIPT_LATCH, COUNTS_BY_HAND and EDGES_DIFFER |
| `test_lrn_c_standin.py` | the placed script's run is `model.run.learning`'s; the stand-in lands each operation inside its window and gives the canonical run at strides 1 and 37; its own checks and its latch; control 5; D0's learner gate's two faults; the day from the matched filter |
| `test_lrn_c_judge.py` | the day passes; controls 1 to 4; each verdict condition broken alone fails; exit codes |
| `test_lrn_c_box.py` | what the box runs and imports; every flag a flag of run_case's; `timeout 900`; no stop after a refused run |

**The named controls**, each run at M = 1,024 through the stand-in and `host.run_case`, as printed (row K11):
1. **A card record changed in one word, in each field.** Record 2,053 of flow, by one in each field in turn: `DIFFERENT: {'record': 2053, 'field': 'index', 'card': 2054, 'model': 2053}`; the same at that record for `epoch` (2 where 1), `flags` (1 where 0) and `score` (-331037416 where -331037417). Each FAIL, exit 1.
2. **An update named at another index.** moved, made by the stand-in: `SEEN: its own model run's, and different from flow's first at record 2048, score, 855652156 where flow's is 644845837, as predicted`. A moved run named at flow's own index: `NOT SEEN: the card's moved run is not its own model run`, FAIL.
3. **An operation outside its window.**
   - Too early, the commit after 1,220: `commit(2048): UPDATE_UNFINISHED, the model's taken; bracket [1221, 1221] OUTSIDE its window [1280, 2048]`, `lrn_early 1 where the model has 0`, and the records DIFFERENT at 2,048 in the epoch.
   - Too late, a stride of 3,000 frames a poll: `update(1024): SWAP_INDEX, the model's taken; bracket [3000, 3000] OUTSIDE its window [0, 1024]`.
   - Each side of the bracket's check is also held alone, with the model's outcome.
   - Inside the window, the model's outcome: the window test.
4. **A counter or the status read back changed by one.** `lrn_skip_busy 3 where the model has 2`; `made 0 where the model has 1`. Every count is changed by +1 and -1, every status bit is flipped, and `lrn_update_at`, `lrn_refusal`, both caps and an undeclared status bit are each changed: each is reported by its name.
5. **A stand-in whose learner reads a truth record's amplitude or pulse id**, on flow with every third record of amplitude 0 and record 5 an `e1`. Reading the amplitude: `DIFFERENT: {'record': 2048, 'field': 'score', ...}`, `lrn_count0 22 where the model has 32`. Reading the pulse id: the same record, `lrn_count0 31 where the model has 32`. Both are the model's up to the commit at 2,048 and FAIL. The true learner on that stream PASSes.

**And D0's learner gate's two faults** (section 9 of D0: a learner that does nothing, and one that rounds the other way), on the stand-in at M = 1,024:
- a learner that judges, counts and finishes as the model's does but writes no set: rich is DIFFERENT first at record 4,096, the first commit's, in the score, with every register the model's, so the records alone see it;
- a learner that rounds half away from zero: the records are the model's on all three cases, because no update's set there holds a tie. `ties` and the quantiser are held on a difference made for it, [262142, 1], where the two roundings give 0 and 1. That is limit 15.

## 9. Limits

Each is stated by the behaviour it concedes.

1. **The wired kernel is not built.** Everything in the first size is the library against the model, through the stand-in. What the fabric does with the writes is held by KRNL-L's benches and the card's day.
2. **The windows are the model's.** A fabric whose update finishes late by its own clocks, its last shadow writes sharing the core's port with the host's reads, is kept off the edge by the guard G alone, a DECISION. The stand-in has no port, finishes every update exactly at u + F, and never tests G.
3. **The bracket rests on PCIe's ordering:** a read issued after posted writes returns after they land (BELIEVED). If it did not, an operation could land after its `next_index_after` read, and the judge would not see it.
4. **next_index's two words are read apart.** Every index of these cases is below 2^32, so its upper word is 0 throughout and no carry can fall between the reads; a case past 2^32 would need that held.
5. **On the case's own stream a learner that reads amplitude or pulse id is not seen**: amplitude 1/1 and one pulse throughout. Control 5 sees it only on a stream made for it, and the card's injector holds `e0` alone (learn.md, limit 9). `test_lrn_c_on_the_cases_own_stream_...` shows the limit.
6. **FULL is never reached on the card** (2^32 windows a label), and the six 64-bit counters' upper words read 0 there: the card holds their low words only. `lrn_skip_full` is 0 in every run.
7. **`refused_again` is read only at the end**, where it must be 0. The library clears the latch after every operation with a write of 0, which clears both of the latch's bits. So a fabric that set `refused_again` wrongly during the run, or failed to set it for a held-back shadow write's second refusal, is not seen, unless the latch was still set at the end. Whether it does so in the fabric is the benches' to hold, not the card's. The stand-in's own latch is held by `test_lrn_c_the_stand_in_latches_as_the_fabric_does_...`.
8. **Round 3's calls do not read `lrn_refusal`.** On a learner kernel `commit`, `write_shadow` and `swap` return as if taken when the learner held the write back; `test_lrn_c_round_3s_commit_...` shows it. The learner path of run_case uses the `lrn_` calls only.
9. **An operation outside its window FAILs** even where the card may have been right: the judge cannot then say.
10. **The stand-in does not model the card's timing:**
    - no clock but its count of polls;
    - writes land at once and in order, with nothing posted;
    - no port shared with the learner;
    - the fabric's CORE_STOPPED and WEIGHT_COUNT for an update are not made;
    - truth is never late;
    - XRT's syncs are not modelled;
    - the box's Python, its collector and the card's frame rate vary nothing.

    What it holds is the library's and the judge's logic over the model's learner.
11. **The model's speed at full scale is an ESTIMATE** until the lead's expect run, and the card's time until the card's day. The brackets measure the day's margins.
12. **The card's records before a blank set's first commit are all scores of 0.** The blank set at epoch 0 makes every score 0, so in flow and moved those records hold the index, epoch and flags and say nothing of the filter. rich loads the matched filter so that its records before the first commit do. If the fabric refuses the blank set (E1C's card day shows it), flow and moved load the matched filter instead, by `cases --start matched`, and the ledger says so with the refusal's text (the lead's ruling, question 6).
13. **The model's latch is worked here**, not in the model, which has none: `hw/lrnc/windows.py` latches QUANTISE_INPUT at an unmade finish, as learn.md section 3 says the fabric does. A fabric that latched it elsewhere would be seen at the clear's read.
14. **Nothing here is evidence about sensitivity.**
15. **A learner that rounds the other way is seen only where an update's set holds a tie**, a coefficient whose |D| x COEFF_MAX over the peak leaves exactly half the peak, with an even integer part. The cases are not shaped to make one. At M = 1,024 no update of the three cases holds a tie, and such a learner gives the model's records there (`test_lrn_c_ties_...`). At M = 2^20, `expect` counts each update's ties; until the lead's expect run, whether the card's streams hold any is not known. The RTL benches hold the rounding on hand-worked ties (learn.md, section 4, `bit_identity_hand_worked_ties`).

*Limits 16 to 18 were stated after the verifier VLRNC, 2026-11-26.*

16. **Two terms of the window rule bind no window of the three cases**:
    - SWAP_INDEX's lower bound `arg + 1`. In rich's operations 9 and 10, commit(1) and update(1), `arg + 1` is 2, below the last commit's index + 1, 4,194,305, which sets their lo.
    - The latch's upper bound `f - 1`. It is 1,048,831 for rich's unmade update, above rich operation 0's own hi of 1,048,576, and no other operation lands before that finish unread.

    So each term, changed alone, leaves every window of these cases as it was, and the 169 tests still pass with it (VLRNC). Both are right by section 3's argument. They would be held by `expect`'s edge runs at full scale, which move every operation to its lo and its hi, on a case where they bind; on these cases nothing holds them.
17. **run_case's wait uses `<`, and `<=` would pass every test.** The wait loops while `next_index` is below "after". With `<=` it would wait one frame more: on the stand-in, at most one more poll, which the stride of 37 frames hides; on the card, about one more round of the host's loop, inside a margin of about 10^6 frames. So the wait's exact condition is not held, and an operation's landing is held only by its bracket inside its window.
18. **An operation whose window's hi is "by order" has no upper bound in the judge.** That covers a clear, and rich's SWAP_INDEX operations 9 and 10, whose window ends at the next operation's landing. The judge checks the bracket's lower side alone for them. Each such operation is followed, in the host's order, by an operation whose own window binds it. A clear made after a later refusal latched would read that refusal's name, not QUANTISE_INPUT, and the judge would see another outcome. But a clear's own bracket says nothing above its lo.

## 10. Register

"The first size's tests" is `python -m pytest -q -p no:cacheprovider tests/test_lrn_c_*.py`. Scratch scripts are in the round's scratch folder, not in the tree.

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| K1 | `model.run.learning` ran 65,536 frames of E1's layout in 0.68 s, 96,696 frames a second | MEASURED | the parcel's scratch script speed.py, 2026-11-26 03:47:58 | a rerun |
| K2 | `expect` for flow at M = 2^18 made its three runs of 1,048,576 frames in 44.2 s, 71,130 frames a second | MEASURED | `python hw/lrnc/lrnc.py cases <f> --m 262144` then `expect <f> --case flow`, 2026-11-26 04:07:38 to 04:08:22 | a rerun |
| K3 | The expectations at M = 2^20 take about 5 to 6 minutes as three processes, rich's 22,020,096 frames about 310 s | ESTIMATE | K2's rate | the lead's expect run |
| K4 | M = 1,048,576 frames is 0.2097 s; G = 4,096 is 0.82 ms; F = 256 is 51.2 us | COMPUTED | at 200 ns a frame, K5 | arithmetic |
| K5 | The card runs about 200 ns a frame at 100 MHz | READ | [CARD-first-light.md](../studies/CARD-first-light.md), row C12 | the card's brackets |
| K6 | Every window, after and margin of section 4's tables | COMPUTED | section 3's rule on the stated outcomes; `test_lrn_c_the_docs_windows_afters_and_margins_at_the_cards_m_are_the_rules` | that test |
| K7 | The counts of section 4 | COMPUTED | by hand from the window rules; held at M = 1,024 by `test_lrn_c_the_counts_worked_by_hand_are_the_models_and_one_changed_is_refused`, and at M = 2^20 by `expect` (COUNTS_BY_HAND) | that test; the expect run |
| K8 | flow's and moved's 4,194,304 frames and 32,768 records, rich's 7,340,032 and 40,962; 19,922,944 frames in the four runs; 234,884,992 bytes the longest buffer; 139,266 truth records fed, 135,170 of them while running; 418,381,824 bytes of records; 330,301,440 bytes of the model's records kept | COMPUTED | `lrnc.case` at M = 2^20; 19 M; 7M x 32 + 3,968; 3 x 32,768 + 40,962, less 4 x 1,024; 19M x 21; 15M x 21. `test_lrn_c_the_docs_frames_records_and_arguments_at_the_cards_m` holds the frames, the records, the sum, the buffer and the bytes back | that test |
| K9 | About 59 to 69 s of runs on the card, under 15 minutes of the card session | ESTIMATE | round 4's 19 to 22 s a piece of 6,400,000 frames ([CARD-e0.md](../studies/CARD-e0.md), row CE9) | the card's day |
| K10 | The short day at M = 2,048, through the stand-in, prints `== LRN-C CARD VERDICT: PASS` in 2.8 s | MEASURED | `python hw/lrnc/lrnc.py short <folder>`, 2026-11-26 04:07:25 | `test_lrn_c_the_day_as_it_should_go_passes_with_the_control_seen` |
| K11 | Each named control printed what section 8 quotes | MEASURED | the parcel's scratch script controls.py, 2026-11-26 04:18:20 | the tests of section 8 |
| K12 | G = M / 256 | DECISION | the parcel's design, approved by the lead 2026-11-26 03:57 | a later ruling of the lead's |
| K13 | The wired kernel's four facts of the opening paragraph | READ | the lead's ruling, 03:57, and its messages after KRNL-L's design, 03:58 and 03:59 | KRNL-L's benches |
| K14 | A piece of 6,400,000 frames took 19 to 22 s whole on the box | READ | [CARD-e0.md](../studies/CARD-e0.md), row CE9 | that record |
| K15 | The noise table for sigma 1477/1 has 13,523 entries | MEASURED | `len(model.source.gaussian_table(1477, 1))`, 2026-11-26 03:51:15; the same as [source.md](../rtl/source.md)'s row S16 | a rerun |
| K16 | One buffer in one segment holds 8,388,484 frames; the injector's store, `cap_inject_pending`, 1,024 records | READ | [e0c.md](e0c.md), its pieces (the plan's L7); `spec/constants.py`, MAX_INJECT_PENDING | those files |
| K17 | The seeds 2026112601 (flow, moved) and 2026112602 (rich), the record at 2.5M, and the four runs' order | DECISION | the parcel's design, approved by the lead 2026-11-26 03:57 | a later ruling of the lead's |
| K18 | The cases folder at M = 2^20 is 9,549,507 bytes: table.json 297,286, flow's folder 2,843,254, moved's 2,843,255, rich's 3,565,664 | MEASURED | `python hw/lrnc/lrnc.py cases <folder>` and `du -sb` on it and its entries, 2026-11-26 04:35:27 | a rerun |
| K19 | The box's snapshot, host/, model/, spec/, hw/e0c/ and hw/lrnc/, is 471,040 bytes in 47 entries | MEASURED | `git archive <tree> host model spec hw/e0c hw/lrnc` piped to `wc -c` and to `tar -t` and `wc -l`, on the staged trees 0d00fa8 (04:35) and 77d5981 (04:48), 2026-11-26, the same both times | the same on the READY commit |

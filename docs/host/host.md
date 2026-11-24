# The host library: one code that drives the kernel, in simulation and on the card

Parcel HOST, round 3, 2026-11-24. The library is `host/`. Its bench on the simulated kernel is `rtl/tb/bench_host.py` with the backend `rtl/tb/host_sim.py`, and its tests in the gate's first size are `tests/test_host_*.py`. The design was approved by the lead on 2026-11-24 (the round's ledger, `lead.md`, entries 10:17 and 11:27). Labels are D0's: MEASURED, READ, COMPUTED, ESTIMATE, BELIEVED, SURVEY, DECISION. Every figure here is in the register at the end.

**What a pass is evidence of.** That the score words the library hands its caller, read through it from KRNL's kernel in simulation, equal the model's own run of the same configuration on the streams the bench runs. That is D0's gate "bit identity", its second part, the host, in simulation. It is not evidence about sensitivity, and nothing here has run on XRT: the XRT backend is written, and has been neither compiled against XRT nor run by its author (limit 1).

## 1. Where things are

| what | where |
|---|---|
| the seam: seven operations | `host/ops.py` |
| every call, as a procedure over them | `host/library.py` |
| the library's own reader of a blob | `host/blob.py` |
| the two drivers, by calls and by coroutines | `host/drive.py` |
| the XRT backend, and its C++ shim | `host/backend_xrt.py`, `host/xrt_shim.cpp` |
| words in a dict, for tests and a dry run | `host/fake.py` |
| one run from files to files, for BUILD and CARD | `host/run_case.py` |
| the writes of four calls, worked by hand | `vectors/host/writes.json` |
| the simulated backend, on KRNL's kernel | `rtl/tb/host_sim.py` |
| the bench | `rtl/tb/bench_host.py`; its row `host-first` in `rtl/tb/benches.toml` |
| the first size's tests | `tests/test_host_*.py` |
| the gate row | `host-capabilities` in `tests/gates.toml` |

## 2. One code, two backends

**The library does no I/O.** Each call is a generator that yields operations and is sent each one's result. The seam is seven operations, and a backend makes no decision: it does not retry, check or read anything back.

| operation | the simulated kernel (`host_sim.Sim`) | XRT (`backend_xrt.Backend`, one shim call each) |
|---|---|---|
| `Read(offset)` | an AXI4-Lite read through KRNL's AxiLiteMaster | `xrt::ip::read_register` |
| `Write(offset, word)` | an AXI4-Lite write, its answer required OKAY | `xrt::ip::write_register` |
| `WriteMany(pairs)` | one write after another, in order | the same, in a loop in C++ |
| `Pause()` | 16 clocks | a sleep, 0 by default |
| `Allocate(size)` | a region of KRNL's memory model at 0x20000 | `xrt::bo` in the kernel buffer argument's memory group |
| `Fill(buffer, offset, data)` | into the memory model's store | `bo.write`, then `bo.sync` to the device |
| `Fetch(buffer, offset, size)` | from the memory model's store | `bo.sync` from the device, then `bo.read` |

**Two drivers** (`host/drive.py`): `Host` runs a procedure by calls, for XRT; `AsyncHost` awaits each operation, for cocotb. Both are made from one list, `host.library.PROCEDURES`, by two pairs of functions that differ only in `async` and `await`.

**How the code above the seam is shown to be one code:**
- In the first size, every procedure is driven by both drivers against one scripted backend: the same operations in the same order with the same values (`test_host_drivers.py`). A driver whose backend answers one read otherwise is reported at that read.
- In the image, `same_code_both_drivers` replays the calls of `identity_fed_and_swapped` through the CALL driver, the one XRT's backend uses, against the kernel's recorded answers. It must make the same operations, in the same order, with the same values, and return the same results. So the code that drives XRT is shown to make, given this kernel's answers, exactly the writes that gave the identity.
- `test_host_independence.py` reads every file of `host/`: no cocotb, `ctypes` only in the XRT backend.

## 3. The calls

**The rule.** A call refuses BEFORE ANY WRITE what it can know from its own inputs and from the identity and capability registers. What depends on a block's state it leaves to that block and READS BACK BY NAME, from the block's refusal register, after each group of writes: a code read is cleared and raised. A refusal already latched before a call is raised with nothing written. Two exceptions, each needed: SWAP_SHAPE for a shadow, since the core sees a shadow's count of words and not its shape; and three facts only the host sees, each raised under the name of what it means: RUN_START (a start that changed nothing), RUN_LENGTH (a run done short with nothing latched) and INJECT_OVERLAP (a run done before the library offered a record).

| call | refused before any write | read back |
|---|---|---|
| `open` | IMAGE_SPEC: `id`, `spec_version`, `spec_hash` or `cap_coeff_bits` not this definition's; PROFILE_UNKNOWN: a build of no declared profile. It writes nothing | none |
| `reset` | none | KERNEL_BUSY |
| `load(blob, epoch)` | the blob, by the library's own reader in `model.weights.unpack`'s order and names; then the build, in the core's order: PROFILE_UNKNOWN, BLOB_FORMAT (`cap_blob_versions`), SHAPE_FILTERS, SHAPE_TAPS, SHAPE_RECTIFIER, SHAPE_SHIFT, SHAPE_POOL, SHAPE_HIDDEN, SHAPE_HIDDEN_SHIFT, SHAPE_BETWEEN, SHAPE_ROWS; SWAP_EPOCH | the core's: SWAP_SHAPE, CORE_STOPPED, WEIGHT_COUNT, WEIGHT_RANGE, REGISTER_ACCESS, any shape name |
| `write_shadow`, `commit`, `swap` | the blob's and the build's, as `load`; SWAP_SHAPE; SWAP_INDEX for an index that is not 0 to 2^64 - 1 | SWAP_PENDING, SWAP_INDEX, SWAP_EPOCH, WEIGHT_COUNT, WEIGHT_RANGE, CORE_STOPPED |
| `start(seed, table, frames, schedule, ahead)` | SEED_RANGE; NOISE_TABLE (not the model's form: rising, every entry below 2^63 but the last, which is 2^63); NOISE_RANGE (longer than `cap_noise_table`); STREAM_LENGTH (not 1 to 2^64 - 1); the schedule by the library's own code in `model.inject.schedule`'s order: RECORD_FIELD, PULSE_UNKNOWN, INJECT_OVERLAP, INJECT_PAST_END; INJECT_PENDING for `ahead` not 1 to `cap_inject_pending` | the source's, the injector's and the kernel's; RUN_START observed |
| `step`, `finish(polls)` | none | at the end, the four registers: the first in the chain's order (source, injector, core, kernel) raised, all in its detail, each cleared; RUN_LENGTH and INJECT_OVERLAP observed. Past `polls`, Python's TimeoutError, giving `krn_status`, `krn_records` and the frames asked for, with nothing more written |
| `records(first, count)` | none | RECORD_SLOT: a slot whose bytes past the record are not zero; RESERVED_BITS |
| `refusals`, `raw_read`, `raw_write` | nothing: `raw_*` are for tests and the card day's raw shape, and check nothing | none |

`swap` returns `next_index` read just before its first shadow write and just after the read that says the commit was taken, and the places of those two operations among its own. IMAGE_SPEC, NOISE_TABLE and RECORD_SLOT are the host library's alone: no block of the fabric raises them.

## 4. Truth while the run goes

`ahead` is the most records the library keeps in the injector's store: `cap_inject_pending` by default, set lower by a bench. `start` writes the first `ahead`. Each `step` reads `inj_pending` and writes as many more as bring it to `ahead`, in the schedule's order, as one `WriteMany`, after reading the core's `next_index`. The least of each batch's first index less that `next_index` is reported as the least slack. A host that falls behind gets INJECT_OVERLAP from the injector, RUN_LENGTH from the kernel, and the records written before: never a wrong record.

**What the card day can run.** 2^17 samples at stage E0's spacing hold at most 1,024 records (the plan's L36), all written before the start: certain, as far as truth goes. 2^20 hold 8,192, of which 7,168 must be written while the run goes, about 39,063 a second (L37). That is **tried**: the run ends with every word the model's, or with INJECT_OVERLAP and RUN_LENGTH by name, and the report gives the least slack either way. XRT's cost per register write has not been measured here.

## 5. The records

`start` allocates a GUARD of 3,968 bytes and then the run's slots, and writes `krn_buffer` as the buffer's address plus the guard. It fills all of it with the byte 0xA5 first. Every slot the kernel writes has zeros past its record (KRNL's design, section 1). So:
- a slot nothing wrote keeps 0xA5 there, and `records` refuses it, RECORD_SLOT;
- a kernel that ignored its base, writing at the buffer's first byte, leaves slot 0 holding the pattern: RECORD_SLOT at slot 0. Under emulation the first buffer sat at device address 0 (the lead, 10:17), where an ignored base would otherwise pass;
- a record left by an earlier run cannot pass for this run's, since each start fills again;
- the guard is not a multiple of 4,096, so slot 4 begins a page and the kernel's bursts must break there.

`Fetch` is the synchronisation from the device and the read as one operation, so no code above the seam can read a buffer before it is synchronised. The layout is built from the definition at import: the fields of the score record, little-endian, then zeros to `MEMORY_SLOT_BYTES`.

## 6. Timing a swap on the card

The call driver keeps, when given a list, a trace: each operation, its result, and `time.perf_counter_ns()` just before the backend is called and just after it answers. `swap` makes the weight words before its first write and makes no other operation of its own between its first shadow write and the read that says the commit was taken. So the card day takes:
- T = that read's "after" less the first shadow write's "before";
- the samples it spans, as the difference of the two `next_index` reads, which bracket T and so over-count by what passes during those two reads;
- the library's own share, as the gaps between one operation's answer and the next one's call.

`swap(..., batch=False)` writes the weights one `Write` at a time, so each write is timed. What it cannot separate is limit 6.

In simulation the bench logs the same span in clocks (`HOST-SWAP-TIMING` in each run's log): rows H3 and H4. It says nothing of the card.

## 7. The XRT backend

`host/xrt_shim.cpp` is compiled by whoever runs it, on the machine with XRT, with XRT's settings sourced (`XILINX_XRT` set):

    g++ -std=c++17 -O2 -Wall -shared -fPIC host/xrt_shim.cpp -I"$XILINX_XRT/include" -L"$XILINX_XRT/lib" -lxrt_coreutil -o <a folder outside the tree>/libundertone_xrt.so

Its path goes to `host.backend_xrt.Backend(xclbin, shim_path=...)`, or into `UNDERTONE_XRT_SHIM`. The shim finds the buffer's memory group from the xclbin itself: the kernel's argument whose offset is `krn_buffer`'s, matched by offset and never by name, since XRT renamed the lead's trial argument. `memory_group` overrides it. It includes `xrt_ip.h` and `xrt_xclbin.h` from whichever of `xrt/`, `xrt/experimental/` or `experimental/` the XRT has. Every XRT exception becomes an OSError in Python at the call that failed.

    from host.backend_xrt import Backend
    from host.drive import Host
    with Backend("<the image>.xclbin", shim_path="<the shim>.so") as backend:
        lib = Host(backend, trace=[])
        lib.open(); lib.reset(); lib.load(blob, epoch=0)
        report = lib.run(seed, table, frames, schedule, polls=10 ** 6)
        records = lib.records()

**The command line** for BUILD and CARD, `python -m host.run_case`, runs one case from files (a blob's bytes, the noise table and the schedule as JSON, made beside the model) and writes `records.bin` (each record's canonical bytes, `model.records.pack`'s, in order), `report.json` and `trace.json`. It needs the library and nothing of the model; the records are compared with the model's wherever the model runs. It prints one line beginning `PASS host.run_case`, **last, only when the run finished and every file is written**: under emulation a run can end with exit code 0 and no output (the lead, 10:17), so **a run with no PASS line is a lost run, never a result.** A refused run prints `REFUSED host.run_case <name>` and returns 2. Its docstring has every option. `--polls` bounds the wait for done (10^7 rounds by default); under emulation, where one register read is far slower than on the card, the caller sets it to what the emulator can run.

Its inputs are made beside the model, and its records compared with the model's there, in a few lines (an example, not a file of the tree):

    import json
    from model import records, run, source, weights
    from spec import constants as C
    blob = weights.matched_filter("s16x1", C.PULSES["e0"], (1,))
    noise = source.Noise("s16x1", seed, sigma_num, sigma_den, frames)
    open("case.blob", "wb").write(blob)
    json.dump(list(noise.table), open("table.json", "w"))
    json.dump(schedule, open("schedule.json", "w"))
    # ... python -m host.run_case ... --out out, then:
    expected, _truth = run.detect(noise, schedule, frames, blob, epoch)
    same = open("out/records.bin", "rb").read() == b"".join(records.pack("score", r) for r in expected)

## 8. The tests and the controls

**First size**, each with what it holds:

| file | holds | its control |
|---|---|---|
| `test_host_blob.py` | the library's reader gives `model.weights.unpack`'s configuration and word order on 80 seeded blobs, both profiles and both versions, and refuses 28 malformed blobs by the same 15 names | a reader that takes one row newest first, reported on every blob whose row is not its own reverse |
| `test_host_capabilities.py` | the gate `host-capabilities`: a blob past each of 11 bounds refused by `load` and by `swap` by that bound's name with nothing written; a blob at each bound written | a library that writes before it holds the blob to the build: the same check reports its writes |
| `test_host_drivers.py` | both drivers make the same operations and results for every procedure | a backend that answers one read otherwise, reported at that read |
| `test_host_library.py` | `open`'s refusals; the schedule's names against `model.inject.schedule` on 12 cases; `start`'s, `load`'s and `swap`'s refusals before any write; reading back and clearing; the chain's order; feeding never past `ahead`; RUN_START, RUN_LENGTH and INJECT_OVERLAP observed; TimeoutError after exactly `polls` rounds; `swap`'s report pointing at its first shadow write and its accepting read, batched and one write at a time, with only the shadow, one read and the commit between | a library that lets one more record into the store than `ahead`, seen |
| `test_host_records.py` | the slot reader against `model.records.pack` on 510 records; RECORD_SLOT for a pattern slot and each padding byte; RESERVED_BITS; the guard; one slot past what was written refused; an ignored base refused at slot 0 | a library that fills with zeros, whose unwritten slot passes: seen |
| `test_host_xrt.py` | the XRT backend against a fake shim with a host and a device copy of each buffer: Fetch syncs then reads, Fill writes then syncs; registers and batches reach the shim as given; the memory group and the offset handed to `open`; a shim failure raised where it happens; `close` frees everything | a backend that reads before it syncs hands back the pattern: seen |
| `test_host_independence.py` | from `model/` only `model.refusal`; nothing of `stats/`, `learn/`, `rtl/`, `tools/`; no cocotb; `ctypes` only in the backend; 3.10's grammar and standard modules | six planted sources, each reported |
| `test_host_writes.py` | **the library's writes** for a load of each blob version, a swap and a start, against `vectors/host/writes.json`, worked by hand and not by running the library or the model | a library that writes a row newest first, reported at the operation that differs |
| `test_host_run_case.py` | the command line's three files, and its one PASS line, last; a refused run prints no PASS and returns 2; a backend's failure raises, with no PASS and no records file | none of its own: the PASS line's absence is what each case asserts |

None of these holds what a kernel does with the writes: `host/fake.py` is words in a dict, and models no block. `test_host_writes.py` holds the library's writes, on four calls, against a hand-worked expectation; `test_host_blob.py` and `test_host_records.py` hold the library's readers against the model's, on the blobs and records they make.

**In the image**, the row `host-first`, under both profiles:

| test | holds |
|---|---|
| `identity_e0` | open, reset, load of E0's matched filter, a run of 200 frames with three records written before the start, the records: every word the model's; the raw slots, the guard and the margin; no fault of protocol in the memory model |
| `identity_fed_and_swapped` | a seeded shape with two hidden units; 360 frames; five truth records, two written before the start and three while it runs; a swap to other weights of that shape at index 200, its shadow written once the core has taken 60 frames, the commit taken before 200 |
| `same_code_both_drivers` | section 2 |
| `refusal_read_back_by_name` | a sum out of range: INJECT_RANGE raised, RUN_LENGTH in its detail; the 37 records written are the model's before its refusal; one slot more is RECORD_SLOT |
| `capabilities_refused_before_any_write` | the kernel's own advertisement read; blobs past it refused by name with nothing written: SHAPE_FILTERS, PROFILE_UNKNOWN, and under `s24x3` SHAPE_ROWS |
| `control_library_coefficient_bit` | the brief's named control: a library that flips bit 0 of the first row's coefficient T - 1 as it packs the blob's words, reported by the comparison at the record the model predicts, the score field alone |
| `control_library_ignores_capabilities` | the brief's named control on the kernel's advertisement: a library that writes past it, seen writing, and refused SHAPE_FILTERS by the core |
| `control_backend_drops_a_write` | the lead's: a backend that drops the first truth record's numerator, which the injector then holds at 0: reported by the comparison at the record the model predicts |
| `control_backend_writes_a_wrong_word` | the lead's: a backend that writes `src_seed`'s lower word at its upper word's offset: reported by the comparison at the record the model predicts |

Each control's evidence was read against the record and field it predicts (rows H5 and H6). **Two more faults were tried by hand on a copy, and are not in the gate** (H20): a library that commits one index late fails `identity_fed_and_swapped` at record 200, the epoch the old one; and one that writes the third truth record's numerator one more fails `identity_e0` at record 136, the score. No row of mine has an RTL mutant: the faults are the library's and the backend's, planted as subclasses and wrappers inside the tests. KRNL's mutants hold the kernel.

**Dropped writes the fabric names before any comparison runs** (BELIEVED, from the blocks' documents; none is planted): a weight word (WEIGHT_COUNT at `start`), `configure` (CORE_STOPPED), the core's `start` (CORE_STOPPED, then RUN_LENGTH), `krn_start` (RUN_START observed), a table entry (the source refuses the start, then RUN_START).

## 9. Limits

Each is stated by the behaviour it concedes.

1. **Nothing of XRT has run.** The shim has never been compiled against XRT by its author: the desktop has no XRT. Its C++ alone was checked, `g++ -std=c++17 -Wall -Wextra -fsyntax-only` against stub headers of the author's that declare what it believes XRT has (H18), which says nothing of XRT's own declarations. Its calls are those of the lead's C++ trial under hardware emulation on XRT 2.14. Whether they compile on the box's XRT, whether `xrt::ip`'s name for the compute unit is `undertone_krnl`, whether the memory group found is the one the kernel's master reaches, and whether a buffer's sync moves the bytes named, are the lead's to see in BUILD and on the card. `test_host_xrt.py` holds the Python side against a fake shim, and nothing of C++.
2. **The library's words are held to the model through a kernel.** A kernel that takes a write and does something else, and a library that writes that same wrong thing, are seen only together, by the comparison. The first size holds the library's logic against `host/fake.py`, which models no block.
3. **The library is handed the model's noise table, the same schedule and the same blob bytes the model runs on.** A table, a schedule or a blob wrong in both alike is not seen. The table's content is trusted whole beyond its form (the source's own limit 2).
4. **Two readers of the blob, one format.** The library's reader and the model's agree on the blobs `test_host_blob.py` makes. A format both read wrongly the same way is not seen.
5. **The library reads back refusal registers and the kernel's status, and nothing else.** A write that lands and is ignored is seen only by the comparison; a lost numerator, the lead's control, is one such. A refusal of a block the library did not write in that call is seen at the next call that reads it.
6. **A swap's time on the card cannot be split inside one backend call:** `ctypes`, the shim, XRT, the driver, PCIe and the kernel's answer are one figure. A PCIe write is posted (BELIEVED), so a write's call returns before it lands, and T ends at a read's answer, that read's round trip included. Under emulation the figure is the emulator's.
7. **A deadline is the caller's.** `finish` raises TimeoutError after `polls` rounds, and the run may still be going; it writes nothing more, so a run that is then reset is the caller's act. What a TimeoutError on the card leaves running is not known here.
8. **One run a reset is what is held.** A second run without `reset` continues the core's and the injector's counts; the model has no such composition here, and nothing compares it.
9. **Feeding while the run goes is held on 5 records with `ahead` = 2,** under both profiles, on a stream where the host is never behind. The host falling behind is held by the fabric's own INJECT_OVERLAP and the library's naming of it in the first size, not by a run that falls behind in simulation. The 2^20 run's rate is the card's to find.
10. **Python 3.10 is held by its grammar and a list of standard modules**, not by running on 3.10: a call to a function a standard module gained after 3.10 is not seen.
11. **The streams are short:** 200, 360 and 120 frames, and three controls of 4, 5 and 65 under the predictions of H5, at the first build's top. A fault of the library that shows only on a long run, a large blob or a table of thousands of entries is not seen here. The card day's E0 table of 13,523 entries (H16) has been written by no bench.
12. **`same_code_both_drivers` replays one test's calls.** The call driver is shown to make the same operations as the coroutine driver for those calls on those answers; the first size shows it for every procedure on scripted answers.
13. **Nothing here is evidence about sensitivity, and nothing is placed or timed.**

## 10. Register

"The row alone" is `python tools/check_rtl.py rtl-benches --root <a copy> --state <a folder>` on a copy of this tree, merged with KRNL at aac9959, whose manifest is cut to the row `host-first`, 2026-11-24 12:11:45 to 12:12:10. "The trial" is the same command on an earlier copy that held KRNL's RTL and helpers of commit b0188c1 before they were merged, 11:58. Both copies and their output are in the round's folder, `scratch/HOST`, which is not in the tree.

| # | claim | basis | source or command | falsified by |
|---|---|---|---|---|
| H1 | The row `host-first` passes 18 tests in 2 runs, holding 1,194 records identical to the model's | MEASURED | the row alone: "OK rtl-benches: 18 test(s) passed in 2 run(s) of 1 bench(es); 1194 record(s) identical to the model's, word for word" | the gate's second size, whose line gives totals for every bench |
| H2 | 1,194 is 2 x (200 + 360 + 37): the three identity tests' records under each profile | COMPUTED | `rtl/tb/bench_host.py`, the frames of `identity_e0` and `identity_fed_and_swapped`, and the 37 records `refusal_read_back_by_name` held | arithmetic |
| H3 | The two runs took 12 s under `s16x1` and 24 s under `s24x3`, side by side, and the stage on the row alone 25 s | MEASURED | the row alone: its `runner.log`, "ran host-first.s16x1 in 12 s", "ran host-first.s24x3 in 24 s"; `date` before and after it | a rerun; another load |
| H4 | In simulation a swap of 2 x 40 + 2 x 2 + 2 = 86 words under `s16x1` took 457 clocks from the first shadow write to the accepting read, and one of 3 x 40 + 2 x 2 + 2 = 126 words under `s24x3` 657, while 24 and 11 frames went through the core | MEASURED | the row alone: the line `HOST-SWAP-TIMING` in each run's log, "next_index 61 to 85" and "60 to 71" | a rerun |
| H5 | Under both profiles the coefficient bit is reported at record 0, the dropped numerator at record 3 and the wrong word at record 1, each in the score field alone | MEASURED | the row alone: each control's MISMATCH line in the two evidence files, read | a rerun |
| H6 | Under `s16x1` the flipped coefficient gives a score of -1 where the model has 0 at record 0 | MEASURED | the same evidence: "the RTL has {'score': -1}, the model {'score': 0}" | a rerun |
| H7 | The guard is 3,968 bytes, 124 slots, so slot 4 begins at a page of 4,096 when the buffer is page-aligned | COMPUTED | `host/library.py`, `GUARD = SLOT * 124`; 3,968 + 4 x 32 = 4,096 | arithmetic |
| H8 | 2^17 slots are 4 MiB and 2^20 are 32 MiB | COMPUTED | 2^17 x 32 = 4,194,304; 2^20 x 32 = 33,554,432 | arithmetic |
| H9 | At E0's spacing 2^17 samples hold at most 1,024 truth records and 2^20 hold 8,192, of which 7,168 come while a run of 2^20 goes, at about 39,063 a second | READ | `docs/plans/R3-first-light.md`, rows L36 and L37 | those rows |
| H10 | XRT 2.14 in cft2204 has no `ip` in its Python binding; its C++ API has `xrt::ip` | READ | the round's ledger, `lead.md`, entry 10:09 | the lead's `dir(pyxrt)` |
| H11 | Under emulation the first buffer sat at device address 0, and the xclbin named the trial's buffer argument `buffer_r` where its kernel.xml said `buffer` | READ | the round's ledger, `lead.md`, entry 10:17 | that trial |
| H12 | The library is to run on Python 3.10.12, cft2204's | READ | the parcel's brief, from the lead's reading of 2026-11-24 | `python3 --version` in cft2204 |
| H13 | The first size's host tests are 50, in 9 files | MEASURED | `python -m pytest -q -p no:cacheprovider tests/test_host_*.py`, 2026-11-24 11:53: "50 passed" | that command |
| H14 | The schedule cases are 12, the malformed blobs 28 under 15 names, the seeded blobs 80 and the slot records 510 | COMPUTED | counted from `test_host_library.py`'s `SCHEDULES`, `test_host_blob.py`'s `cases` and `blobs` (40 a profile), and `test_host_records.py` (500 seeded, 10 at the ends) | a recount |
| H15 | The XRT backend's design is that pyxrt cannot be used and a C++ shim through `ctypes` is | DECISION | the lead's ruling (d), `lead.md` 10:17, on HOST's design | an XRT whose Python binding reaches a user-managed kernel's registers |
| H16 | Stage E0's table has 13,523 entries, its last index 13,522 | READ | `docs/rtl/source.md`, row S16 | that row's command |
| H17 | The controls' runs are 4, 5 and 65 frames: the predicted record plus 4 for the coefficient bit (0) and the wrong word (1), and 1 + 64 for the dropped numerator, whose record must end inside the run | COMPUTED | `rtl/tb/bench_host.py`; H5 | a rerun whose predictions move |
| H18 | The shim's C++ passes g++ 16.1.0's syntax check with no warning against stub headers of its author's; the first check found a variable's declaration that C++ reads as a function's (the most vexing parse), now written with braces | MEASURED | `g++ -std=c++17 -Wall -Wextra -fsyntax-only -I<stubs> host/xrt_shim.cpp` on the desktop's MSYS2 g++ ("g++.exe (Rev5, Built by MSYS2 project) 16.1.0"), 2026-11-24 11:52; the stubs are in the round's folder, `scratch/HOST/stubs`, not in the tree | that command with XRT's own headers |
| H20 | With the library's commit one index late and its third record's numerator one more, both planted at once in a copy's `host/library.py`, `identity_fed_and_swapped` fails at record 200 (epoch 5 where the model has 6) and `identity_e0` at record 136 (the score), under both profiles | MEASURED | the trial, its fifth state folder: the two MISMATCH lines of each evidence file, read | the same plants on another copy |
| H19 | The box has XRT 2.19.194 (branch 2025.1), `xrt_ip.h` under both `include/experimental/` and `include/xrt/experimental/`, Python 3.12.3 and g++ 13.3.0; cft2204 has XRT 2.14.354 with `xrt_ip.h` under `include/experimental/` alone, Python 3.10.12 and g++ 11.4.0 | READ | the lead's message to HOST, 2026-11-24 about 11:55 | those machines |

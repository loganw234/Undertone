"""LRN-C: the host library's learner calls, their operations, their refusals, and the one code under both drivers.

WHAT THIS HOLDS, against `host.fake.Registers` (words in a dict, hooks where a test latches a code):
  - each learner call's operations, written out here by hand for one value each: which registers it reads and
    writes, at which offsets, with which words, in which order;
  - what each refuses BEFORE ANY WRITE: LEARN_BOUND at each of the definition's bounds and for a kernel with no
    learner (its caps read 0) or one that is not the case's; SWAP_INDEX of an argument; SWAP_SHAPE of a blob;
    a code latched before the call;
  - what each reads back after its writes: the learner's code and the core's, cleared (a write of 0) and raised,
    the learner's first;
  - both drivers make the same operations and results for every learner call (`run_by_calls`, XRT's;
    `run_by_coroutines`, a bench's), and PROCEDURES is the fourteen names it was;
  - the limit of round 3's calls on a learner kernel: `commit` returns where `lrn_commit` refuses.

WHAT IT DOES NOT HOLD: anything a kernel does with the writes. The stand-in (tests/test_lrn_c_standin.py) and the
card's day hold that against the model; this holds the library's logic.
"""
import asyncio

import pytest

from spec import constants as C
from model import weights
from model.refusal import Refusal
from learn import handover

from host import fake, library as L, ops
from host.drive import run_by_calls, run_by_coroutines

PROFILE = "s16x1"
EFFECTS = ops.EFFECTS


def kernel(learner=True, **caps):
    words = fake.identity_words(PROFILE)
    if learner:
        words.update(fake.learner_words(**caps))
    return fake.Registers(words)


def latch_on(backend, where, register, name):
    """At a write of `where`, the word is kept and `register` latches `name`, as a block would."""
    def hook(b, word):
        b.words[where] = word
        b.words[L.offset(register)] = C.REFUSAL_CODES[name]
    backend.on_write[where] = hook


def call(lib, backend, name, *args):
    return run_by_calls(getattr(lib, name)(*args), backend)


def opened(backend):
    lib = L.Library()
    call(lib, backend, "open")
    return lib


def since(backend, mark):
    return backend.ops[mark:]


def effects(op_list):
    return [op for op in op_list if isinstance(op, EFFECTS)]


def blank():
    return handover.blank_blob(PROFILE, 64)


def matched():
    return weights.matched_filter(PROFILE, C.PULSES["e0"], (1,))


def loaded(backend):
    lib = opened(backend)
    call(lib, backend, "load", matched())
    return lib


# ------------------------------------------------------------------ the procedures and the drivers

def test_lrn_c_procedures_is_the_fourteen_names_it_was_and_the_learner_calls_are_beside_it():
    assert L.PROCEDURES == ("open", "reset", "load", "write_shadow", "commit", "swap", "start", "step", "finish", "run",
                            "records", "refusals", "raw_read", "raw_write")
    assert L.LEARNER_PROCEDURES == ("lrn_open", "lrn_update", "lrn_commit", "lrn_write_shadow", "lrn_clear",
                                    "lrn_registers")
    assert not set(L.LEARNER_PROCEDURES) & set(L.PROCEDURES)
    for name in L.LEARNER_PROCEDURES:
        assert callable(getattr(L.Library, name))


def _learner_sequence(lib_call):
    """Every learner call once, in a run's order, against a learner kernel with a matched shape loaded."""
    out = [lib_call("open"), lib_call("load", matched()), lib_call("lrn_open", 32, 256),
           lib_call("lrn_update", (1 << 32) + 5), lib_call("lrn_commit", 9000), lib_call("lrn_write_shadow", blank()),
           lib_call("lrn_clear"), lib_call("lrn_registers")]
    return out


def test_lrn_c_both_drivers_make_the_same_operations_and_results_for_every_learner_call():
    sync_backend, async_backend = kernel(), kernel()
    sync_lib, async_lib = L.Library(), L.Library()
    sync_trace, async_trace = [], []
    got_sync = _learner_sequence(lambda name, *a: run_by_calls(getattr(sync_lib, name)(*a), sync_backend,
                                                                sync_trace, name))

    async def go():
        backend = fake.AsyncRegisters(async_backend)
        out = []
        for name, args in (("open", ()), ("load", (matched(),)), ("lrn_open", (32, 256)),
                           ("lrn_update", ((1 << 32) + 5,)), ("lrn_commit", (9000,)), ("lrn_write_shadow", (blank(),)),
                           ("lrn_clear", ()), ("lrn_registers", ())):
            out.append(await run_by_coroutines(getattr(async_lib, name)(*args), backend, async_trace, name))
        return out
    got_async = asyncio.run(go())
    keyed = lambda t: [(e.call, e.ordinal, ops.key(e.op), ops.result_key(e.result)) for e in t]
    assert keyed(sync_trace) == keyed(async_trace)
    assert got_sync == got_async
    assert {e.call for e in sync_trace} >= set(L.LEARNER_PROCEDURES)


# ------------------------------------------------------------------ lrn_open

def test_lrn_c_lrn_open_reads_the_two_caps_and_writes_nothing():
    backend = kernel()
    lib = opened(backend)
    mark = len(backend.ops)
    assert call(lib, backend, "lrn_open") == {"count_bits": 32, "update_frames": 256}
    assert since(backend, mark) == [ops.Read(0xD48), ops.Read(0xD4C)]
    assert lib.learner_caps == {"count_bits": 32, "update_frames": 256}


def test_lrn_c_a_kernel_with_no_learner_is_refused_learn_bound_by_name_with_nothing_written():
    """It reads 0 at 0xD00 to 0xDFF (docs/rtl/learn.md, row L9), so count_bits 0 is outside 1..32."""
    backend = kernel(learner=False)
    lib = L.Library()
    with pytest.raises(Refusal) as e:
        call(lib, backend, "lrn_open")
    assert e.value.name == "LEARN_BOUND"
    assert "no learner answers at 0xD00 to 0xDFF" in e.value.detail
    assert effects(backend.ops) == [] and lib.learner_caps is None
    # Every other learner call opens the learner first, so each is refused the same way with nothing written.
    for name, args in (("lrn_update", (100,)), ("lrn_commit", (100,)), ("lrn_write_shadow", (blank(),)),
                       ("lrn_clear", ()), ("lrn_registers", ())):
        backend = kernel(learner=False)
        lib = L.Library()
        call(lib, backend, "open")
        call(lib, backend, "load", matched())
        mark = len(backend.ops)
        with pytest.raises(Refusal) as e:
            call(lib, backend, name, *args)
        assert e.value.name == "LEARN_BOUND", name
        assert effects(since(backend, mark)) == [], name


@pytest.mark.parametrize("bits, frames, refused", [
    (0, 256, True), (1, 256, False), (32, 256, False), (33, 256, True),
    (32, 0, False), (32, 255, False), (32, 257, True), (1 << 31, 256, True)])
def test_lrn_c_lrn_open_holds_the_caps_to_the_definitions_bounds(bits, frames, refused):
    backend = kernel(lrn_cap_count_bits=bits, lrn_cap_update_frames=frames)
    lib = opened(backend)
    if refused:
        with pytest.raises(Refusal) as e:
            call(lib, backend, "lrn_open")
        assert e.value.name == "LEARN_BOUND"
        assert "no learner" not in e.value.detail
    else:
        assert call(lib, backend, "lrn_open") == {"count_bits": bits, "update_frames": frames}


@pytest.mark.parametrize("asked, which", [((31, None), "count_bits"), ((None, 16), "update_frames"),
                                          ((32, 255), "update_frames"), ((1, 256), "count_bits")])
def test_lrn_c_lrn_open_refuses_a_build_that_is_not_the_cases(asked, which):
    backend = kernel()
    lib = opened(backend)
    with pytest.raises(Refusal) as e:
        call(lib, backend, "lrn_open", *asked)
    assert e.value.name == "LEARN_BOUND" and ("needs %s" % which) in e.value.detail
    assert lib.learner_caps is None
    assert call(lib, backend, "lrn_open", 32, 256) == {"count_bits": 32, "update_frames": 256}


def test_lrn_c_lrn_open_runs_open_first_and_an_image_of_another_definition_is_image_spec():
    backend = kernel()
    lib = L.Library()
    call(lib, backend, "lrn_open")
    assert backend.ops[0] == ops.Read(L.offset("id")) and lib.identity is not None
    other = kernel()
    other.words.update(fake.value_words("spec_hash", 1))
    with pytest.raises(Refusal) as e:
        call(L.Library(), other, "lrn_open")
    assert e.value.name == "IMAGE_SPEC"


# ------------------------------------------------------------------ lrn_update

def test_lrn_c_lrn_update_reads_the_latch_writes_the_lower_word_then_the_upper_and_reads_it_back():
    backend = kernel()
    lib = opened(backend)
    call(lib, backend, "lrn_open")
    mark = len(backend.ops)
    assert call(lib, backend, "lrn_update", (1 << 32) + 5) == {"at": (1 << 32) + 5}
    assert since(backend, mark) == [ops.Read(0xD0C), ops.WriteMany(((0xD00, 5), (0xD04, 1))), ops.Read(0xD0C)]


@pytest.mark.parametrize("at", [-1, 1 << 64, (1 << 64) - 256, "5", True, 1.0, None])
def test_lrn_c_lrn_update_refuses_an_index_that_is_not_one_before_any_write(at):
    backend = kernel()
    lib = opened(backend)
    call(lib, backend, "lrn_open")
    mark = len(backend.ops)
    with pytest.raises(Refusal) as e:
        call(lib, backend, "lrn_update", at)
    assert e.value.name == "SWAP_INDEX"
    assert since(backend, mark) == []


def test_lrn_c_lrn_update_takes_the_last_index_whose_finish_fits_and_uses_the_builds_update_frames():
    backend = kernel()
    lib = opened(backend)
    call(lib, backend, "lrn_open")
    call(lib, backend, "lrn_update", (1 << 64) - 257)
    small = kernel(lrn_cap_update_frames=16)
    lib = opened(small)
    call(lib, small, "lrn_open")
    call(lib, small, "lrn_update", (1 << 64) - 17)
    with pytest.raises(Refusal):
        call(lib, small, "lrn_update", (1 << 64) - 16)


@pytest.mark.parametrize("name", ["UPDATE_UNFINISHED", "SWAP_SHAPE", "SWAP_PENDING", "SWAP_INDEX", "CORE_STOPPED",
                                  "WEIGHT_COUNT"])
def test_lrn_c_lrn_update_raises_what_the_learner_latched_and_clears_it(name):
    backend = kernel()
    latch_on(backend, L.offset("lrn_update_at", 1), "lrn_refusal", name)
    lib = opened(backend)
    call(lib, backend, "lrn_open")
    mark = len(backend.ops)
    with pytest.raises(Refusal) as e:
        call(lib, backend, "lrn_update", 4000)
    assert e.value.name == name
    tail = since(backend, mark)
    assert tail[-2:] == [ops.Read(0xD0C), ops.Write(0xD0C, 0)]
    assert backend.words[0xD0C] == 0


def test_lrn_c_a_code_latched_before_a_learner_call_is_raised_with_nothing_written():
    for name, args, register in (("lrn_update", (4000,), "lrn_refusal"), ("lrn_commit", (4000,), "lrn_refusal"),
                                 ("lrn_commit", (4000,), "refusal"), ("lrn_write_shadow", (blank(),), "lrn_refusal"),
                                 ("lrn_write_shadow", (blank(),), "refusal")):
        backend = kernel()
        lib = loaded(backend)
        call(lib, backend, "lrn_open")
        backend.words[L.offset(register)] = C.REFUSAL_CODES["QUANTISE_INPUT"]
        mark = len(backend.ops)
        with pytest.raises(Refusal) as e:
            call(lib, backend, name, *args)
        assert e.value.name == "QUANTISE_INPUT" and "latched before this call" in e.value.detail, (name, register)
        assert effects(since(backend, mark)) == [], (name, register)


# ------------------------------------------------------------------ lrn_commit and lrn_write_shadow

def test_lrn_c_lrn_commit_writes_commit_at_and_reads_back_the_learner_then_the_core():
    backend = kernel()
    lib = loaded(backend)
    call(lib, backend, "lrn_open")
    mark = len(backend.ops)
    call(lib, backend, "lrn_commit", (2 << 32) + 7)
    assert since(backend, mark) == [ops.Read(0xD0C), ops.Read(0x104), ops.WriteMany(((0x0F8, 7), (0x0FC, 2))),
                                    ops.Read(0xD0C), ops.Read(0x104)]


@pytest.mark.parametrize("register, name", [("lrn_refusal", "UPDATE_UNFINISHED"), ("refusal", "SWAP_INDEX"),
                                            ("refusal", "SWAP_PENDING"), ("refusal", "SWAP_EPOCH")])
def test_lrn_c_lrn_commit_raises_either_blocks_code_and_clears_it(register, name):
    backend = kernel()
    latch_on(backend, L.offset("commit_at", 1), register, name)
    lib = loaded(backend)
    call(lib, backend, "lrn_open")
    with pytest.raises(Refusal) as e:
        call(lib, backend, "lrn_commit", 4000)
    assert e.value.name == name and backend.words[L.offset(register)] == 0
    assert backend.ops[-1] == ops.Write(L.offset(register), 0)


def test_lrn_c_with_both_latched_the_learners_code_is_raised_first_both_named_and_both_cleared():
    backend = kernel()

    def both(b, word):
        b.words[L.offset("commit_at", 1)] = word
        b.words[L.offset("lrn_refusal")] = C.REFUSAL_CODES["UPDATE_UNFINISHED"]
        b.words[L.offset("refusal")] = C.REFUSAL_CODES["SWAP_INDEX"]
    backend.on_write[L.offset("commit_at", 1)] = both
    lib = loaded(backend)
    call(lib, backend, "lrn_open")
    with pytest.raises(Refusal) as e:
        call(lib, backend, "lrn_commit", 4000)
    assert e.value.name == "UPDATE_UNFINISHED"
    assert "the learner UPDATE_UNFINISHED" in e.value.detail and "the core SWAP_INDEX" in e.value.detail
    assert backend.ops[-2:] == [ops.Write(0xD0C, 0), ops.Write(0x104, 0)]


def test_lrn_c_lrn_commit_refuses_an_index_that_is_not_one_before_any_write():
    backend = kernel()
    lib = loaded(backend)
    call(lib, backend, "lrn_open")
    for at in (-1, 1 << 64, "1"):
        mark = len(backend.ops)
        with pytest.raises(Refusal) as e:
            call(lib, backend, "lrn_commit", at)
        assert e.value.name == "SWAP_INDEX" and effects(since(backend, mark)) == []


def test_lrn_c_lrn_write_shadow_writes_what_write_shadow_writes_and_reads_back_both():
    a, b = kernel(), kernel()
    lib_a, lib_b = loaded(a), loaded(b)
    call(lib_a, a, "lrn_open")
    mark_a, mark_b = len(a.ops), len(b.ops)
    assert call(lib_a, a, "lrn_write_shadow", blank()) == {"words": 64 + 1}
    call(lib_b, b, "write_shadow", blank())
    assert effects(since(a, mark_a)) == effects(since(b, mark_b))
    assert [op for op in since(a, mark_a) if isinstance(op, ops.Read)] == [ops.Read(0xD0C), ops.Read(0x104)] * 2


def test_lrn_c_lrn_write_shadow_refuses_another_shape_and_a_shadow_with_no_shape_loaded_before_any_write():
    backend = kernel()
    lib = loaded(backend)
    call(lib, backend, "lrn_open")
    mark = len(backend.ops)
    with pytest.raises(Refusal) as e:
        call(lib, backend, "lrn_write_shadow", handover.blank_blob(PROFILE, 32))
    assert e.value.name == "SWAP_SHAPE" and effects(since(backend, mark)) == []
    fresh = kernel()
    lib = opened(fresh)
    with pytest.raises(Refusal) as e:
        call(lib, fresh, "lrn_write_shadow", blank())
    assert e.value.name == "SWAP_SHAPE" and effects(fresh.ops) == []


def test_lrn_c_a_held_back_shadow_write_is_raised_from_the_learner_where_the_core_reads_0():
    backend = kernel()
    latch_on(backend, L.offset("shadow_begin"), "lrn_refusal", "UPDATE_UNFINISHED")
    lib = loaded(backend)
    call(lib, backend, "lrn_open")
    with pytest.raises(Refusal) as e:
        call(lib, backend, "lrn_write_shadow", blank())
    assert e.value.name == "UPDATE_UNFINISHED" and backend.words.get(0x104, 0) == 0
    assert ops.Write(0x104, 0) not in backend.ops[-3:], "the core's 0 is not cleared"


def test_lrn_c_round_3s_commit_returns_on_a_learner_kernel_where_lrn_commit_refuses():
    """The limit, shown: a commit the learner holds back latches only lrn_refusal, which `commit` does not read."""
    plain, learner = kernel(), kernel()
    for backend in (plain, learner):
        latch_on(backend, L.offset("commit_at", 1), "lrn_refusal", "UPDATE_UNFINISHED")
    lib = loaded(plain)
    call(lib, plain, "commit", 4000)                       # returns: it reads the core's refusal, which is 0
    assert plain.words[0xD0C] == C.REFUSAL_CODES["UPDATE_UNFINISHED"]
    lib = loaded(learner)
    with pytest.raises(Refusal) as e:
        call(lib, learner, "lrn_commit", 4000)
    assert e.value.name == "UPDATE_UNFINISHED"


# ------------------------------------------------------------------ lrn_clear and lrn_registers

def test_lrn_c_lrn_clear_reads_the_latch_clears_a_code_and_returns_its_name_without_raising():
    backend = kernel()
    lib = opened(backend)
    call(lib, backend, "lrn_open")
    mark = len(backend.ops)
    assert call(lib, backend, "lrn_clear") is None
    assert since(backend, mark) == [ops.Read(0xD0C)]
    backend.words[0xD0C] = C.REFUSAL_CODES["QUANTISE_INPUT"]
    mark = len(backend.ops)
    assert call(lib, backend, "lrn_clear") == "QUANTISE_INPUT"
    assert since(backend, mark) == [ops.Read(0xD0C), ops.Write(0xD0C, 0)] and backend.words[0xD0C] == 0
    backend.words[0xD0C] = 250
    assert call(lib, backend, "lrn_clear") == "code 250"


def test_lrn_c_lrn_registers_reads_every_learner_register_each_64_bit_counter_lower_word_then_upper():
    backend = kernel()
    values = {"lrn_update_at": (3 << 32) + 11, "lrn_count0": 12, "lrn_count1": 13, "lrn_skip_start": (5 << 32) + 1,
              "lrn_skip_busy": 2, "lrn_skip_full": 3, "lrn_made": 4, "lrn_unmade": 5, "lrn_early": (1 << 63) + 6}
    for name, v in values.items():
        backend.words.update(fake.value_words(name, v))
    backend.words[0xD08] = 0b100101
    backend.words[0xD0C] = C.REFUSAL_CODES["QUANTISE_INPUT"]
    lib = opened(backend)
    call(lib, backend, "lrn_open")
    mark = len(backend.ops)
    got = call(lib, backend, "lrn_registers")
    assert got["lrn_update_at"] == values["lrn_update_at"]
    assert got["lrn_status_word"] == 0b100101
    assert got["lrn_status"] == {"named": 1, "running": 0, "made": 1, "unmade": 0, "refused": 0, "refused_again": 1}
    assert got["lrn_refusal"] == "QUANTISE_INPUT"
    assert got["counts"] == dict((n, values[n]) for n in L.LRN_COUNTS)
    assert got["caps"] == {"lrn_cap_count_bits": 32, "lrn_cap_update_frames": 256}
    reads = [op.offset for op in since(backend, mark)]
    assert effects(since(backend, mark)) == []
    assert reads == [0xD00, 0xD04, 0xD08, 0xD0C, 0xD10, 0xD14, 0xD18, 0xD1C, 0xD20, 0xD24, 0xD28, 0xD2C, 0xD30, 0xD34,
                     0xD38, 0xD3C, 0xD40, 0xD44, 0xD48, 0xD4C]


def test_lrn_c_lrn_registers_reads_a_counters_upper_word_as_the_lower_reads_hold_left_it():
    """A backend that holds as the fabric does: a lower read keeps that counter's upper word for the next read,
    and the counter moves by 2^32 after every lower read. The library's value is the one moment's."""
    backend = kernel()
    for name in ("lrn_skip_busy",):
        lo, hi = L.offset(name, 0), L.offset(name, 1)
        state = {"v": (7 << 32) + 9, "held": 0}

        def low(b, state=state):
            state["held"] = state["v"] >> 32
            word = state["v"] & 0xFFFFFFFF
            state["v"] += 1 << 32
            return word

        backend.on_read[lo] = low
        backend.on_read[hi] = lambda b, state=state: state["held"]
    lib = opened(backend)
    assert call(lib, backend, "lrn_registers")["counts"]["lrn_skip_busy"] == (7 << 32) + 9

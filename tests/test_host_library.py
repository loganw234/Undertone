"""The library's own logic: what it refuses before any write, how it reads refusals back, how it feeds truth.

WHAT THIS HOLDS, against `host.fake` (words in a dict, a kernel by script):
  - `open` refuses an image of another definition, IMAGE_SPEC, for each of the
    four things it compares, and a build of no declared profile,
    PROFILE_UNKNOWN; it writes nothing.
  - The library's schedule checks give `model.inject.schedule`'s names, case for
    case; its table, seed, length, `ahead`, epoch and index checks refuse by
    their names; each before anything changes below the seam.
  - A refusal latched after a group of writes is raised by its name and
    cleared; one latched before a call is raised with nothing written; a code
    no name has is IMAGE_SPEC; at a run's end the first in the chain's order is
    raised (the source, the injector, the core, the kernel), with every one in
    its detail, and each is cleared.
  - Feeding: never more than `ahead` records held, offered in the schedule's
    order; a start that changed nothing is RUN_START; a run done short with
    nothing latched is RUN_LENGTH; a run done with records not offered is
    INJECT_OVERLAP; a run that never says done is TimeoutError after exactly
    `polls` rounds, with nothing written after.

WHAT IT DOES NOT HOLD: anything a kernel does. The fake answers what a test
scripts. The bench holds the library on the simulated kernel.
"""
from spec import constants as C
from model import inject, source, weights
from model.refusal import Refusal

from host import fake, library as L, ops
from host.drive import Host

PROFILE = "s16x1"
TABLE = source.gaussian_table(2, 1)
CODE = C.REFUSAL_CODES
DONE = 1 << C.REGISTER_BITS["krn_status"]["done"]
RUNNING = 1 << C.REGISTER_BITS["krn_status"]["running"]


def e0_blob():
    return weights.matched_filter(PROFILE, C.PULSES["e0"], (1,))


def effects(backend):
    return [op for op in backend.ops if isinstance(op, ops.EFFECTS)]


def refused(call, *args, **kw):
    try:
        call(*args, **kw)
    except Refusal as e:
        return e.name
    return None


def test_host_library_open_refuses_another_definition():
    wrong = (("id", C.BUS["magic"] ^ 1), ("spec_version", C.SPEC_VERSION + 1),
             ("spec_hash", int(C.SPEC_SHA256, 16) ^ (1 << 200)), ("cap_coeff_bits", C.COEFF_BITS - 1))
    for name, value in wrong:
        words = fake.identity_words(PROFILE)
        words.update(fake.value_words(name, value))
        backend = fake.Registers(words)
        assert refused(Host(backend).open) == "IMAGE_SPEC", name
        assert effects(backend) == []
    backend = fake.Registers(fake.identity_words(PROFILE, cap_channels=2))
    assert refused(Host(backend).open) == "PROFILE_UNKNOWN"
    backend = fake.Registers(fake.identity_words("s24x3"))
    assert Host(backend).open()["profile"] == "s24x3"


def rec(index, num=1, den=1, pulse_id=0):
    return {"index": index, "pulse_id": pulse_id, "amplitude_num": num, "amplitude_den": den}


SCHEDULES = (
    ([rec(0)], 64, None),
    ([rec(0), rec(64)], 128, None),
    ([{"index": 0, "pulse_id": 0, "amplitude_num": 1}], 64, "RECORD_FIELD"),
    ([dict(rec(0), extra=1)], 64, "RECORD_FIELD"),
    ([rec(0, num=True)], 64, "RECORD_FIELD"),
    ([rec(0, num=1 << 31)], 64, "RECORD_FIELD"),
    ([rec(-1)], 64, "RECORD_FIELD"),
    ([rec(0, den=0)], 64, "RECORD_FIELD"),
    ([rec(0, pulse_id=1)], 64, "PULSE_UNKNOWN"),
    ([rec(0), rec(63)], 200, "INJECT_OVERLAP"),
    ([rec(100), rec(0)], 200, "INJECT_OVERLAP"),
    ([rec(1)], 64, "INJECT_PAST_END"),
)


def test_host_library_schedule_refused_as_the_model_refuses():
    for schedule, frames, want in SCHEDULES:
        assert refused(inject.schedule, schedule, frames) == want, ("the model's", schedule)
        assert refused(L.check_schedule, schedule, frames) == want, ("the library's", schedule)


def start_refusal(*args, **kw):
    backend = fake.Registers(fake.identity_words(PROFILE, cap_noise_table=30, cap_inject_pending=4))
    host = Host(backend)
    host.open()
    name = refused(host.start, *args, **kw)
    return name, effects(backend)


def test_host_library_start_refuses_before_any_write():
    one = 1 << 63
    cases = (
        ((-1, TABLE, 10, []), {}, "SEED_RANGE"),
        ((1 << 64, TABLE, 10, []), {}, "SEED_RANGE"),
        ((1, [], 10, []), {}, "NOISE_TABLE"),
        ((1, (5, 3, one), 10, []), {}, "NOISE_TABLE"),
        ((1, (5, 7), 10, []), {}, "NOISE_TABLE"),
        ((1, (-1, one), 10, []), {}, "NOISE_TABLE"),
        ((1, (one, one), 10, []), {}, "NOISE_TABLE"),
        ((1, (5.0, one), 10, []), {}, "NOISE_TABLE"),
        ((1, tuple(range(31)) + (one,), 10, []), {}, "NOISE_RANGE"),
        ((1, TABLE, 0, []), {}, "STREAM_LENGTH"),
        ((1, TABLE, 1 << 64, []), {}, "STREAM_LENGTH"),
        ((1, TABLE, 10, [rec(0)]), {}, "INJECT_PAST_END"),
        ((1, TABLE, 10, []), {"ahead": 0}, "INJECT_PENDING"),
        ((1, TABLE, 10, []), {"ahead": 5}, "INJECT_PENDING"),
    )
    for args, kw, want in cases:
        assert start_refusal(*args, **kw) == (want, []), (want, args[:2], kw)
    assert len(TABLE) - 1 <= 30 and start_refusal(1, tuple(range(30)) + (one,), 10, [])[0] == "RUN_START"


def test_host_library_load_and_swap_refuse_before_any_write():
    backend = fake.Registers(fake.identity_words(PROFILE))
    host = Host(backend)
    host.open()
    assert refused(host.load, e0_blob(), epoch=1 << 32) == "SWAP_EPOCH"
    assert refused(host.swap, e0_blob(), 10) == "SWAP_SHAPE"          # nothing loaded since the last reset
    assert effects(backend) == []
    host.load(e0_blob())
    before = len(effects(backend))
    other = weights.pack(PROFILE, [{0: [1, 2]}], [1], 0, 1, 0)
    assert refused(host.swap, other, 10) == "SWAP_SHAPE"
    assert refused(host.commit, -1) == "SWAP_INDEX"
    assert refused(host.commit, 1 << 64) == "SWAP_INDEX"
    assert len(effects(backend)) == before


def test_host_library_swap_names_the_operations_the_card_day_times():
    """swap's report points at its first shadow write and at the read that says the commit was taken, by calls
    and one write at a time alike; between them it makes only the shadow's writes, one read and the commit."""
    for batch in (True, False):
        backend = fake.Registers(fake.identity_words(PROFILE))
        trace = []
        host = Host(backend, trace=trace)
        host.load(e0_blob())
        swapped = host.swap(e0_blob(), 1000, batch=batch)
        mine = [e for e in trace if e.call == "swap"]
        first, accepting = mine[swapped["first_shadow_op"]], mine[swapped["accepting_op"]]
        begin = L.offset("shadow_begin")
        if batch:
            assert type(first.op) is ops.WriteMany and first.op.pairs[0][0] == begin, first.op
        else:
            assert type(first.op) is ops.Write and first.op.offset == begin, first.op
        assert accepting.op == ops.Read(L.offset("refusal"))
        between = mine[swapped["first_shadow_op"]:swapped["accepting_op"]]
        commits = [e for e in between if ops.key(e.op)[1:2] == (L.offset("commit_at", 1),) or
                   (type(e.op) is ops.WriteMany and e.op.pairs[-1][0] == L.offset("commit_at", 1))]
        assert commits and between[-1] is commits[-1]
        reads = [e for e in between if type(e.op) is ops.Read]
        assert reads == [between[len(between) - (2 if batch else 3)]] and reads[0].op == ops.Read(L.offset("refusal"))
        words = 1 + len(L.B.words(L.B.read(e0_blob())))
        assert len(between) == (3 if batch else words + 1 + 2), (batch, len(between))
        assert swapped["next_index_before"] == 0 and mine[-1].op == ops.Read(L.offset("next_index", 1))


def test_host_library_reads_back_and_clears():
    backend = fake.Registers(fake.identity_words(PROFILE))
    core = L.offset("refusal")

    def latch(b, word):
        b.words[core] = CODE["SWAP_SHAPE"]
    backend.on_write[L.offset("configure")] = latch
    host = Host(backend)
    assert refused(host.load, e0_blob()) == "SWAP_SHAPE"
    assert backend.words[core] == 0 and backend.ops[-1] == ops.Write(core, 0)
    assert not [op for op in backend.ops if type(op) is ops.WriteMany and any(w[0] == L.offset("start") for w in op.pairs)]


def test_host_library_raises_what_was_latched_before_and_writes_nothing():
    words = fake.identity_words(PROFILE)
    words[L.offset("refusal")] = CODE["WEIGHT_RANGE"]
    backend = fake.Registers(words)
    host = Host(backend)
    try:
        host.load(e0_blob())
    except Refusal as e:
        assert e.name == "WEIGHT_RANGE" and "latched before" in e.detail
    else:
        raise AssertionError("not raised")
    assert effects(backend) == []


def test_host_library_a_code_no_name_has_is_image_spec():
    words = fake.identity_words(PROFILE)
    words[L.offset("refusal")] = 250
    assert 250 not in C.REFUSAL_CODES.values()
    assert refused(Host(fake.Registers(words)).load, e0_blob()) == "IMAGE_SPEC"


def test_host_library_a_run_refused_names_the_first_in_the_chain():
    backend = fake.scripted_kernel(PROFILE, polls_running=1)
    plain = backend.on_write[L.offset("krn_start")]

    def started(b, word):
        plain(b, word)
        b.words[L.offset("inj_refusal")] = CODE["INJECT_RANGE"]
        b.words[L.offset("krn_refusal")] = CODE["RUN_LENGTH"]
        b.words[L.offset("refusal")] = CODE["CORE_STOPPED"]
    backend.on_write[L.offset("krn_start")] = started
    host = Host(backend)
    try:
        host.run(3, TABLE, 70, [rec(2)], polls=5)
    except Refusal as e:
        assert e.name == "INJECT_RANGE", e
        assert "kernel RUN_LENGTH" in e.detail and "core CORE_STOPPED" in e.detail
    else:
        raise AssertionError("not raised")
    for register in ("inj_refusal", "krn_refusal", "refusal"):
        assert backend.words[L.offset(register)] == 0
    assert [r["index"] for r in host.records()] == list(range(70))


def fed_run(ahead, records=9, spacing=70, library=None):
    """A run whose injector drains one held record each time krn_status is read; returns the held counts seen
    at each record's offer, and the indexes offered in order."""
    backend = fake.scripted_kernel(PROFILE, polls_running=40)
    state = {"offered": 0, "drained": 0, "held": [], "order": []}
    status = backend.on_read[L.offset("krn_status")]

    def read_status(b):
        state["drained"] = min(state["offered"], state["drained"] + 1)
        return status(b)

    def offered(b, word):
        state["offered"] += 1
        state["held"].append(state["offered"] - state["drained"])
        state["order"].append(fake.value(b, "inj_truth_index"))
    backend.on_read[L.offset("krn_status")] = read_status
    backend.on_read[L.offset("inj_pending")] = lambda b: state["offered"] - state["drained"]
    backend.on_write[L.offset("inj_truth_amplitude_den")] = offered
    schedule = [rec(5 + spacing * k, num=k + 1) for k in range(records)]
    host = Host(backend, library=library)
    report = host.run(1, TABLE, 5 + spacing * records, schedule, polls=60, ahead=ahead)
    return report, state, schedule


def test_host_library_feeds_no_more_than_ahead_and_in_order():
    for ahead in (1, 2, 4):
        report, state, schedule = fed_run(ahead)
        assert max(state["held"]) <= ahead, (ahead, state["held"])
        assert state["order"] == [r["index"] for r in schedule]
        assert report["truth_before_start"] == ahead and report["truth_while_running"] == len(schedule) - ahead
        assert report["least_slack"] is not None


def test_host_library_control_a_library_that_overfills_is_seen():
    class Overfill(L.Library):
        def start(self, seed, table, frames, schedule, ahead=None):
            result = yield from super().start(seed, table, frames, schedule, ahead)
            self.run_state.ahead = ahead + 1
            return result
    _report, state, _s = fed_run(2, library=Overfill())
    assert max(state["held"]) > 2


REFUSED = 1 << C.REGISTER_BITS["krn_status"]["refused"]


def refusing_start(latches):
    """A backend whose kernel refuses the start: at the krn_start write it latches `latches` ({register: name}),
    says refused and not running, and never says done (as KRNL's kernel clears done at a start)."""
    backend = fake.Registers(fake.identity_words(PROFILE))

    def started(b, word):
        for register, name in latches.items():
            b.words[L.offset(register)] = CODE[name]
        b.words[L.offset("krn_status")] = REFUSED
    backend.on_write[L.offset("krn_start")] = started
    return backend


START_REFUSALS = (
    ({"krn_refusal": "RUN_START"}, "RUN_START"),
    ({"krn_refusal": "STREAM_LENGTH"}, "STREAM_LENGTH"),
    ({"krn_refusal": "BUFFER_ALIGN"}, "BUFFER_ALIGN"),
    ({"krn_refusal": "BUFFER_SIZE"}, "BUFFER_SIZE"),
    # A table one entry short: the source refuses the start, then the kernel says RUN_START. The cause is first.
    ({"src_refusal": "REGISTER_ACCESS", "krn_refusal": "RUN_START"}, "REGISTER_ACCESS"),
)


def test_host_library_a_start_the_kernel_refuses_ends_by_name():
    """VHOST's B2: a refused start is raised by its name at once, every register cleared, never a TimeoutError.
    Through `start`, and through `run` (start, then finish) on a fresh backend."""
    for latches, want in START_REFUSALS:
        for call in ("start", "run"):
            backend = refusing_start(latches)
            host = Host(backend)
            args = (1, TABLE, 10, [])
            try:
                if call == "start":
                    host.start(*args)
                else:
                    host.run(*args, polls=10 ** 6)
            except Refusal as e:
                assert e.name == want, (latches, call, e)
                for register, name in latches.items():
                    assert name in e.detail, (name, e.detail)
            else:
                raise AssertionError("a refused start was not raised")
            for register in latches:
                assert backend.words[L.offset(register)] == 0, register
            assert not [op for op in backend.ops if type(op) is ops.Pause], "the library waited on a refused start"


def test_host_library_a_refusal_while_not_running_ends_the_wait():
    """A kernel that, mid-run, says refused and not running (its run ended by a refusal) ends `finish` at once, by
    name; one that says refused while still running is waited on until done, then the refusal raised."""
    for running_polls, pauses_most in ((0, 0), (5, 5)):
        backend = fake.scripted_kernel(PROFILE, polls_running=10 ** 9)
        state = {"reads": 0}
        plain_status = backend.on_read[L.offset("krn_status")]

        def status(b):
            state["reads"] += 1
            if state["reads"] <= 2:
                return plain_status(b)
            b.words[L.offset("krn_refusal")] = CODE["MEMORY_WRITE"]
            if state["reads"] <= 2 + running_polls:
                return RUNNING | REFUSED
            return (DONE | REFUSED) if running_polls else REFUSED
        backend.on_read[L.offset("krn_status")] = status
        host = Host(backend)
        assert refused(host.run, 1, TABLE, 10, [], polls=50) == "MEMORY_WRITE"
        assert sum(1 for op in backend.ops if type(op) is ops.Pause) <= pauses_most + 1, running_polls
        assert backend.words[L.offset("krn_refusal")] == 0


def test_host_library_a_refusal_latched_before_start_changes_nothing():
    """VHOST's B3: with any of the four refusal registers latched before a start, the start raises it, nothing
    below the seam changes (no Allocate, Fill, Write or WriteMany), and the last run's records are still read."""
    for register in ("src_refusal", "inj_refusal", "refusal", "krn_refusal"):
        backend = fake.scripted_kernel(PROFILE, polls_running=1)
        host = Host(backend)
        host.run(1, TABLE, 12, [], polls=5)
        before = host.records()
        assert len(before) == 12
        backend.words[L.offset(register)] = CODE["REGISTER_ACCESS"]
        mark = len(backend.ops)
        try:
            host.start(2, TABLE, 20, [])
        except Refusal as e:
            assert e.name == "REGISTER_ACCESS" and "latched before" in e.detail, e
        else:
            raise AssertionError("the latched refusal was not raised")
        assert [op for op in backend.ops[mark:] if isinstance(op, ops.EFFECTS)] == [], register
        assert host.records() == before, register


def test_host_library_run_start_observed():
    backend = fake.Registers(fake.identity_words(PROFILE))
    assert refused(Host(backend).start, 1, TABLE, 10, []) == "RUN_START"


def test_host_library_run_length_observed():
    backend = fake.scripted_kernel(PROFILE, polls_running=1, written=9)
    assert refused(Host(backend).run, 1, TABLE, 10, [], polls=5) == "RUN_LENGTH"


def test_host_library_records_not_offered_are_inject_overlap():
    backend = fake.scripted_kernel(PROFILE, polls_running=0)
    schedule = [rec(5), rec(80)]
    assert refused(Host(backend).run, 1, TABLE, 200, schedule, polls=5, ahead=1) == "INJECT_OVERLAP"


def test_host_library_a_run_that_never_says_done_is_a_timeout():
    backend = fake.scripted_kernel(PROFILE, polls_running=10 ** 9)
    host = Host(backend)
    host.start(1, TABLE, 10, [])
    mark = len(backend.ops)
    try:
        host.finish(polls=7)
    except TimeoutError as e:
        assert "krn_status 0x%X" % RUNNING in str(e) and "krn_records 10" in str(e) and "of 10 frames" in str(e)
    else:
        raise AssertionError("no TimeoutError")
    after = backend.ops[mark:]
    assert sum(1 for op in after if type(op) is ops.Pause) == 7
    assert not [op for op in after if isinstance(op, ops.EFFECTS)]

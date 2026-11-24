"""The command line for BUILD and CARD: its files, and its one PASS line, last, only for a run that finished.

WHAT THIS HOLDS, with `host.fake`'s scripted kernel in place of XRT:
  - a run writes records.bin (each record's canonical bytes,
    `model.records.pack`'s, in order), report.json and trace.json, and then
    prints one line beginning "PASS host.run_case", last;
  - a run refused, during it or WHILE ITS RECORDS ARE READ (a kernel that
    ignored its base: RECORD_SLOT), writes its files, prints "REFUSED
    host.run_case <name>", returns 2, and prints no PASS (VHOST's B1 was a
    plant of the lead's that no test of this file caught: this one does);
  - a deadline returns 3 and a backend's failure 1, each with its files
    written and no PASS; after each, krn_reset and then the reads of what the
    kernel answered, BEFORE the backend frees its buffers and closes. The
    scripted kernel answers a reset as the RTL does: refused, KERNEL_BUSY,
    while it runs (VHOST-2's B1: nothing the host writes stops a running
    kernel), taken when it does not; the report says which;
  - --polls below 1 is refused before the backend opens; a failure of the
    close ends FAILED with the files written; a backend failure after a
    refusal wins;
  - a swap is made once the core has taken the frames asked, batched by
    default and one Write a word under --swap-unbatched, which report.json says.

WHAT IT DOES NOT HOLD: XRT. The backend here is words in a dict.
"""
import json

from spec import constants as C
from model import records, source, weights

from host import fake, library as L, ops
from host import run_case


class FakeBackend:
    """What run_case's Backend is to it, over the scripted kernel. `events` logs each operation, and "close"."""

    def __init__(self, fail_at=None, polls_running=3, ignore_base=False, fail_close=False, fail_fetch=False,
                 latch_at_start=None, written=None, fail_reset=None, **_kw):
        self.inner = fake.scripted_kernel("s16x1", polls_running=polls_running, ignore_base=ignore_base,
                                          written=written)
        self.fail_reset = fail_reset          # an exception class raised at the krn_reset write after the run
        if latch_at_start:
            plain = self.inner.on_write[L.offset("krn_start")]

            def started(b, word):
                plain(b, word)
                for register, name in latch_at_start.items():
                    b.words[L.offset(register)] = C.REFUSAL_CODES[name]
            self.inner.on_write[L.offset("krn_start")] = started
        self.memory_group = 0
        self.fail_at, self.n, self.fail_close, self.fail_fetch = fail_at, 0, fail_close, fail_fetch
        self.events = []

    def now(self):
        return self.inner.now()

    def do(self, op):
        self.n += 1
        if (self.fail_at is not None and self.n == self.fail_at) or (self.fail_fetch and type(op) is ops.Fetch):
            raise OSError("the fake backend failed")
        if self.fail_reset is not None and op == ops.Write(L.offset("krn_reset"), 1) and self.n > 40:
            raise self.fail_reset("the fake backend failed at the reset")
        self.events.append(op)
        return self.inner.do(op)

    def close(self):
        self.events.append("close")
        if self.fail_close:
            raise (self.fail_close if isinstance(self.fail_close, type) else OSError)("the fake backend's close failed")


def files(tmp_path, schedule=()):
    blob = tmp_path / "e0.blob"
    blob.write_bytes(weights.matched_filter("s16x1", C.PULSES["e0"], (1,)))
    table = tmp_path / "table.json"
    table.write_text(json.dumps(list(source.gaussian_table(2, 1))))
    sched = tmp_path / "schedule.json"
    sched.write_text(json.dumps(list(schedule)))
    return ["--xclbin", "x", "--shim", "y", "--blob", str(blob), "--table", str(table), "--seed", "7",
            "--frames", "40", "--schedule", str(sched), "--out", str(tmp_path / "out")]


def using(monkeypatch, **kw):
    made = []

    def make(*a, **k):
        made.append(FakeBackend(**kw))
        return made[-1]
    monkeypatch.setattr(run_case, "Backend", make)
    return made


def lines_of(capsys):
    return capsys.readouterr().out.strip().split("\n")


def test_host_run_case_writes_its_files_then_one_pass_line(tmp_path, monkeypatch, capsys):
    using(monkeypatch)
    args = files(tmp_path) + ["--swap-blob", str(tmp_path / "e0.blob"), "--swap-at", "30", "--swap-after", "0"]
    assert run_case.main(args) == 0
    lines = lines_of(capsys)
    assert lines[-1].startswith("PASS host.run_case: 40 records") and sum(l.startswith("PASS") for l in lines) == 1
    out = tmp_path / "out"
    data = (out / "records.bin").read_bytes()
    want = b"".join(records.pack("score", {"index": i, "epoch": 0, "flags": 0, "score": 7 * i - 50}) for i in range(40))
    assert data == want
    report = json.loads((out / "report.json").read_text())
    assert report["records"] == 40 and report["run"]["records"] == 40 and report["swap"]["at"] == 30
    assert report["swap_batched"] is True
    assert len(json.loads((out / "trace.json").read_text())) > 40


def test_host_run_case_a_refused_run_prints_no_pass(tmp_path, monkeypatch, capsys):
    using(monkeypatch)
    bad = [{"index": 30, "pulse_id": 0, "amplitude_num": 1, "amplitude_den": 1}]      # ends past 40 frames
    assert run_case.main(files(tmp_path, bad)) == 2
    out = capsys.readouterr().out
    assert "REFUSED host.run_case INJECT_PAST_END" in out and "PASS" not in out
    assert json.loads((tmp_path / "out" / "report.json").read_text())["refused"]["name"] == "INJECT_PAST_END"


def test_host_run_case_records_refused_while_read_prints_no_pass(tmp_path, monkeypatch, capsys):
    """A kernel that ignored its base: the run finishes, and reading its records is refused, RECORD_SLOT."""
    using(monkeypatch, ignore_base=True)
    assert run_case.main(files(tmp_path)) == 2
    lines = lines_of(capsys)
    assert lines[-1].startswith("REFUSED host.run_case RECORD_SLOT") and not [l for l in lines if "PASS" in l]
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert report["records_refused"]["name"] == "RECORD_SLOT" and report["records"] == 0
    assert (tmp_path / "out" / "records.bin").read_bytes() == b""


RESET = ops.Write(L.offset("krn_reset"), 1)
AFTER_RESET = (ops.Read(L.offset("krn_refusal")), ops.Read(L.offset("krn_status")), ops.Write(L.offset("krn_refusal"), 0))


def reset_then_close(backend):
    """Whether the last krn_reset write comes before the close with nothing between them but the reads of
    krn_refusal and krn_status and the clearing of a KERNEL_BUSY latch."""
    events = backend.events
    if RESET not in events or "close" not in events:
        return False
    at, close = max(i for i, e in enumerate(events) if e == RESET), events.index("close")
    return at < close and all(e in AFTER_RESET for e in events[at + 1:close])


def test_host_run_case_a_deadline_resets_reads_the_answer_and_prints_no_pass(tmp_path, monkeypatch, capsys):
    """After a deadline the kernel still runs: the reset is refused KERNEL_BUSY, as the RTL refuses it, and the
    report says so; the latch is cleared; the files are written before the close."""
    made = using(monkeypatch, polls_running=10 ** 9)
    assert run_case.main(files(tmp_path) + ["--polls", "5"]) == 3
    lines = lines_of(capsys)
    assert lines[-1].startswith("DEADLINE host.run_case") and not [l for l in lines if "PASS" in l]
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert "has not said done" in report["deadline"]
    assert report["reset"]["krn_refusal"] == "KERNEL_BUSY" and report["reset"]["running"] is True
    assert report["reset"]["answer"].startswith("refused KERNEL_BUSY")
    assert json.loads((tmp_path / "out" / "trace.json").read_text())
    assert reset_then_close(made[0])
    assert made[0].inner.words[L.offset("krn_refusal")] == 0                 # the latch cleared


def test_host_run_case_a_reset_behind_another_refusal_is_not_taken(tmp_path, monkeypatch, capsys):
    """VHOST-3's C1: a kernel running with RECORD_QUEUE latched meets the deadline; the reset is refused and its
    KERNEL_BUSY not latched behind the first refusal: the answer says "not taken", and nothing is cleared."""
    made = using(monkeypatch, polls_running=10 ** 9, latch_at_start={"krn_refusal": "RECORD_QUEUE"})
    assert run_case.main(files(tmp_path) + ["--polls", "5"]) == 3
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert report["reset"]["answer"].startswith("not taken") and report["reset"]["krn_refusal"] == "RECORD_QUEUE"
    assert made[0].inner.words[L.offset("krn_refusal")] == C.REFUSAL_CODES["RECORD_QUEUE"]


def test_host_run_case_a_reset_of_a_kernel_not_running_is_taken(tmp_path, monkeypatch, capsys):
    """A refused run (the kernel no longer running): the reset is taken, and the report says so."""
    made = using(monkeypatch, latch_at_start={"inj_refusal": "INJECT_RANGE", "krn_refusal": "RUN_LENGTH"})
    assert run_case.main(files(tmp_path)) == 2
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert report["refused"]["name"] == "INJECT_RANGE" and report["reset"]["answer"] == "taken"
    assert reset_then_close(made[0])


def test_host_run_case_a_backend_failure_resets_then_frees_and_prints_no_pass(tmp_path, monkeypatch, capsys):
    made = using(monkeypatch, fail_at=50)          # the 50th operation: finish polling a started kernel
    assert run_case.main(files(tmp_path)) == 1
    lines = lines_of(capsys)
    assert lines[-1].startswith("FAILED host.run_case") and not [l for l in lines if "PASS" in l]
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert "the fake backend failed" in report["failed"] and "answer" in report["reset"]
    assert reset_then_close(made[0])


def test_host_run_case_control_a_close_before_the_reset_is_seen(tmp_path, monkeypatch, capsys):
    """The check above, handed a backend whose close comes before the reset is written, reports it."""
    made = using(monkeypatch, polls_running=10 ** 9)
    run_case.main(files(tmp_path) + ["--polls", "5"])
    backend = made[0]
    assert reset_then_close(backend), "the check does not pass the run as it was: it cannot be a control"
    close = backend.events.index("close")
    reset = max(i for i, e in enumerate(backend.events) if e == RESET)
    backend.events.insert(reset, backend.events.pop(close))       # the close moved before the reset
    assert not reset_then_close(backend)


def test_host_run_case_polls_below_one_refused_before_the_backend_opens(tmp_path, monkeypatch, capsys):
    made = using(monkeypatch)
    try:
        run_case.main(files(tmp_path) + ["--polls", "0"])
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("--polls 0 was taken")
    assert made == [] and "PASS" not in capsys.readouterr().out


def test_host_run_case_a_failed_close_ends_failed_with_its_files(tmp_path, monkeypatch, capsys):
    """A run that finished, and a close that fails: FAILED, exit 1, no PASS, the files written."""
    using(monkeypatch, fail_close=True)
    assert run_case.main(files(tmp_path)) == 1
    lines = lines_of(capsys)
    assert lines[-1].startswith("FAILED host.run_case: the backend's close") and not [l for l in lines if "PASS" in l]
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert "close failed" in report["close_failed"] and report["records"] == 40 and report["run"]["records"] == 40
    assert len((tmp_path / "out" / "records.bin").read_bytes()) == 40 * L.RECORD_BYTES


def test_host_run_case_a_failure_at_the_reset_wins(tmp_path, monkeypatch, capsys):
    """VHOST-3's B2: a refusal, then a deadline, each followed by a reset that raises: FAILED, exit 1, with the
    files, the earlier end kept in report.json; for an OSError and for an error of another kind."""
    for error in (OSError, RuntimeError):
        out = tmp_path / error.__name__
        out.mkdir()
        using(monkeypatch, fail_reset=error, latch_at_start={"inj_refusal": "INJECT_RANGE", "krn_refusal": "RUN_LENGTH"})
        assert run_case.main(files(out)) == 1, error
        assert lines_of(capsys)[-1].startswith("FAILED host.run_case: the reset")
        report = json.loads((out / "out" / "report.json").read_text())
        assert report["refused"]["name"] == "INJECT_RANGE" and report["reset"]["answer"].startswith("raised")
        using(monkeypatch, fail_reset=error, polls_running=10 ** 9)
        assert run_case.main(files(out) + ["--polls", "5", "--out", str(out / "deadline")]) == 1, error
        assert lines_of(capsys)[-1].startswith("FAILED host.run_case: the reset")
        report = json.loads((out / "deadline" / "report.json").read_text())
        assert "has not said done" in report["deadline"] and (out / "deadline" / "trace.json").exists()


def test_host_run_case_a_kernel_that_says_more_records_than_frames_ends_by_name(tmp_path, monkeypatch, capsys):
    """VHOST-3's B3: krn_records reads 41 of a run of 40, nothing latched: RUN_LENGTH, by name, from the run and
    again when its records are read; exit 2, the files written."""
    using(monkeypatch, written=41)
    assert run_case.main(files(tmp_path)) == 2
    assert lines_of(capsys)[-1].startswith("REFUSED host.run_case RUN_LENGTH")
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert report["refused"]["name"] == "RUN_LENGTH" and report["records_refused"]["name"] == "RUN_LENGTH"
    assert (tmp_path / "out" / "records.bin").read_bytes() == b""


def test_host_run_case_a_close_raising_another_kind_ends_failed(tmp_path, monkeypatch, capsys):
    using(monkeypatch, fail_close=RuntimeError)
    assert run_case.main(files(tmp_path)) == 1
    assert lines_of(capsys)[-1].startswith("FAILED host.run_case: the backend's close: RuntimeError")
    assert json.loads((tmp_path / "out" / "report.json").read_text())["records"] == 40


def test_host_run_case_a_failure_after_a_refusal_wins(tmp_path, monkeypatch, capsys):
    """A refused run whose records then cannot be fetched: the failure wins, exit 1; the refusal is kept."""
    using(monkeypatch, fail_fetch=True, latch_at_start={"inj_refusal": "INJECT_RANGE", "krn_refusal": "RUN_LENGTH"})
    assert run_case.main(files(tmp_path)) == 1
    assert lines_of(capsys)[-1].startswith("FAILED host.run_case")
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert report["refused"]["name"] == "INJECT_RANGE" and "failed" in report["failed"]


def test_host_run_case_a_swap_one_write_a_word(tmp_path, monkeypatch, capsys):
    made = using(monkeypatch)
    args = files(tmp_path) + ["--swap-blob", str(tmp_path / "e0.blob"), "--swap-at", "30", "--swap-unbatched"]
    assert run_case.main(args) == 0
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert report["swap_batched"] is False
    trace = json.loads((tmp_path / "out" / "trace.json").read_text())
    swap = [row for row in trace if row[0] == "swap"]
    words = 1 + len(L.B.words(L.B.read(weights.matched_filter("s16x1", C.PULSES["e0"], (1,)))))
    assert sum(1 for row in swap if row[2] == "Write") == words + 2 and not [row for row in swap if row[2] == "WriteMany"]

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
    written, no PASS, and krn_reset written BEFORE the backend frees its
    buffers and closes (the lead's ask for the card day);
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

    def __init__(self, fail_at=None, polls_running=3, ignore_base=False, **_kw):
        self.inner = fake.scripted_kernel("s16x1", polls_running=polls_running, ignore_base=ignore_base)
        self.memory_group = 0
        self.fail_at, self.n = fail_at, 0
        self.events = []

    def now(self):
        return self.inner.now()

    def do(self, op):
        self.n += 1
        if self.fail_at is not None and self.n == self.fail_at:
            raise OSError("the fake backend failed")
        self.events.append(op)
        return self.inner.do(op)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.events.append("close")
        return False


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


def reset_then_close(backend):
    """The index of the krn_reset write and of the close, in what the backend was handed."""
    reset = [i for i, e in enumerate(backend.events) if e == ops.Write(L.offset("krn_reset"), 1)]
    return reset, backend.events.index("close")


def test_host_run_case_a_deadline_resets_then_frees_and_prints_no_pass(tmp_path, monkeypatch, capsys):
    made = using(monkeypatch, polls_running=10 ** 9)
    assert run_case.main(files(tmp_path) + ["--polls", "5"]) == 3
    lines = lines_of(capsys)
    assert lines[-1].startswith("DEADLINE host.run_case") and not [l for l in lines if "PASS" in l]
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert "has not said done" in report["deadline"] and report["reset_before_free"] == "written"
    assert json.loads((tmp_path / "out" / "trace.json").read_text())
    resets, close = reset_then_close(made[0])
    assert resets and resets[-1] < close and resets[-1] == close - 1


def test_host_run_case_a_backend_failure_resets_then_frees_and_prints_no_pass(tmp_path, monkeypatch, capsys):
    made = using(monkeypatch, fail_at=50)          # the 50th operation: finish polling a started kernel

    assert run_case.main(files(tmp_path)) == 1
    lines = lines_of(capsys)
    assert lines[-1].startswith("FAILED host.run_case") and not [l for l in lines if "PASS" in l]
    report = json.loads((tmp_path / "out" / "report.json").read_text())
    assert "the fake backend failed" in report["failed"] and report["reset_before_free"] == "written"
    resets, close = reset_then_close(made[0])
    assert resets and resets[-1] == close - 1


def test_host_run_case_control_a_close_before_the_reset_is_seen(tmp_path, monkeypatch, capsys):
    """The check above, handed a backend whose close comes before the reset is written, reports it."""
    made = using(monkeypatch, polls_running=10 ** 9)
    run_case.main(files(tmp_path) + ["--polls", "5"])
    backend = made[0]
    at = backend.events.index("close")
    backend.events.insert(at - 1, backend.events.pop(at))        # the close moved before the reset
    resets, close = reset_then_close(backend)
    assert not (resets and resets[-1] == close - 1)


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

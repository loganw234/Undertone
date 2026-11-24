"""The command line for BUILD and CARD: its files, and its one PASS line, last, only for a run that finished.

WHAT THIS HOLDS, with `host.fake`'s scripted kernel in place of XRT: a run
writes records.bin (each record's canonical bytes, `model.records.pack`'s, in
order), report.json and trace.json, and then prints one line beginning "PASS
host.run_case", last; a refused run writes its files, prints "REFUSED
host.run_case <name>" and returns 2, and prints no PASS; a backend that fails
mid-run raises, and no PASS is printed. A swap is made once the core has
taken the frames asked.

WHAT IT DOES NOT HOLD: XRT. The backend here is words in a dict.
"""
import json
import os

from spec import constants as C
from model import records, source, weights

from host import fake, library as L
from host import run_case


class FakeBackend:
    """What run_case's Backend is to it, over the scripted kernel."""

    def __init__(self, fail_at=None, **_kw):
        self.inner = fake.scripted_kernel("s16x1", polls_running=3)
        self.memory_group = 0
        self.fail_at, self.n = fail_at, 0

    def now(self):
        return self.inner.now()

    def do(self, op):
        self.n += 1
        if self.fail_at is not None and self.n == self.fail_at:
            raise OSError("the fake backend failed")
        return self.inner.do(op)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
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


def test_host_run_case_writes_its_files_then_one_pass_line(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(run_case, "Backend", lambda *a, **kw: FakeBackend())
    args = files(tmp_path) + ["--swap-blob", str(tmp_path / "e0.blob"), "--swap-at", "30", "--swap-after", "0"]
    assert run_case.main(args) == 0
    lines = capsys.readouterr().out.strip().split("\n")
    assert lines[-1].startswith("PASS host.run_case: 40 records") and sum(l.startswith("PASS") for l in lines) == 1
    out = tmp_path / "out"
    data = (out / "records.bin").read_bytes()
    want = b"".join(records.pack("score", {"index": i, "epoch": 0, "flags": 0, "score": 7 * i - 50}) for i in range(40))
    assert data == want
    report = json.loads((out / "report.json").read_text())
    assert report["records"] == 40 and report["run"]["records"] == 40 and report["swap"]["at"] == 30
    assert len(json.loads((out / "trace.json").read_text())) > 40


def test_host_run_case_a_refused_run_prints_no_pass(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(run_case, "Backend", lambda *a, **kw: FakeBackend())
    bad = [{"index": 30, "pulse_id": 0, "amplitude_num": 1, "amplitude_den": 1}]      # ends past 40 frames
    assert run_case.main(files(tmp_path, bad)) == 2
    out = capsys.readouterr().out
    assert "REFUSED host.run_case INJECT_PAST_END" in out and "PASS" not in out
    assert json.loads((tmp_path / "out" / "report.json").read_text())["refused"]["name"] == "INJECT_PAST_END"


def test_host_run_case_a_backend_failure_prints_no_pass(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(run_case, "Backend", lambda *a, **kw: FakeBackend(fail_at=60))
    try:
        run_case.main(files(tmp_path))
    except OSError:
        pass
    else:
        raise AssertionError("a backend's failure was not raised")
    assert "PASS" not in capsys.readouterr().out
    assert not os.path.exists(tmp_path / "out" / "records.bin")

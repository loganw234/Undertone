"""The one place the parts of the reference model meet.

    frames (a source, a replay, any stream)
        |
        v
    the injector  ------>  truth records: to the caller, and to nothing else
        |
        v
    the detector core  -->  one score record for each frame

`scores` wires them and hands back the two things that leave: an iterator of
(frame, score record) pairs, which is what a scorer is fed, and the truth
records. `detect` is the same with the pairs collected, for streams short
enough to hold.

TRUTH ISOLATION, and what it rests on. The detector core is handed frames and
nothing else: the truth records are returned to the caller and are not an
argument of anything downstream of the injector. The profile is the blob's
own: it is stated once, in the configuration, and the injector is given that
one. `tests/test_seam_isolation.py` holds the property that matters: the same
samples under different truth records give the same score records, byte for
byte, and a runner that lets one bit of truth reach the detector is caught.

What this does NOT do, stated as limits:
  - It is isolation by what is passed, not a wall. The injected stream is a
    Python generator, and code that goes looking inside it can find what the
    injector is about to add. Nothing here stops a detector written to do
    that; the gate's control shows only that one which USES truth is caught
    by its output.
  - A core fed directly, without this module, gets whatever its caller gives.
  - Nothing here scores: a `model.scorer.Scorer` is fed the pairs by the
    caller, who also holds the truth. Comparing events with truth is the
    caller's, and is where the two are allowed to meet.
"""
from model import inject as _inject
from model import weights
from model.detector import Core


def scores(frames, schedule_records, length, blob, epoch=0):
    """Returns (pairs, truth).

    `pairs` is an iterator of (frame, score record): the frame as the detector
    saw it, with the schedule's pulses added, and the record made from it.
    `truth` is the schedule as the injector checked it.

    Everything that can be refused before a frame is read is refused here, by
    the part that owns it: the blob (`model.weights.unpack`), then the
    schedule (`model.inject.inject`). While the pairs run, a refusal from the
    injector or the core ends them there; the pairs before it stand.
    """
    core = Core(blob, epoch)
    profile_name = weights.unpack(blob)["profile"]
    injected, truth = _inject.inject(profile_name, frames, schedule_records, length)
    return _pairs(core, injected), truth


def _pairs(core, injected):
    # The detector's whole view of the world is `injected`. Truth is not in scope here.
    for frame in injected:
        yield frame, core.step(frame)


def detect(frames, schedule_records, length, blob, epoch=0):
    """Returns (records, truth): `scores` with every score record collected into a tuple.

    For a stream short enough to hold. A long run reads `scores` as it goes.
    """
    pairs, truth = scores(frames, schedule_records, length, blob, epoch)
    return tuple(record for _frame, record in pairs), truth

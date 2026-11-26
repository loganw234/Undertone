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

WITH A LEARNER (`learning`, round 5, parcel LRN-B; docs/model/lrn-b.md). The
truth's indexes are then an argument of one thing downstream of the
injector: the learner of `model/learner.py`, which reads each record's index
and nothing else. The core is still handed each frame and nothing else. The
learner reaches the core only by writing its shadow at an update the host
named, and the core's outputs change only at a commit the host named. So the
restated property: the same samples under different truth records give the
same score records up to the first named commit, and after it the records of
a run with no learner and the learner's set committed at the same indexes.
`tests/test_lrn_b_isolation.py` holds it. The learner's own counters do
depend on truth; they are not output records.
"""
from spec import constants as C
from model import inject as _inject
from model import learner as _learner
from model import weights
from model.detector import Core
from model.refusal import Refusal


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


OPERATIONS = ("update", "commit", "write_shadow")


def learning(frames, schedule_records, length, blob, script, update_frames=C.LEARN_UPDATE_FRAMES,
             count_bits=C.LEARN_COUNT_BITS, epoch=0):
    """Returns (records, truth, outcomes, learner): the injector feeding a core with the learner beside it.

    `script` maps a next index, 0 to `length`, to a list of host operations, each ("update", u),
    ("commit", at) or ("write_shadow", blob), made in order when the core's next output is that index,
    before its frame is drawn; at `length` they are made after the last frame. Each is taken or refused
    by name, and recorded in `outcomes` as (index, operation, argument, the refusal's name or None): a
    refused operation leaves the run going, as a refused register write leaves the fabric running.

    Refused before a frame is read, in this order: the blob (`model.weights.unpack`), the schedule
    (`model.inject.inject`), the script (RECORD_FIELD: an entry that is not a list of declared operations
    at an index 0..length), the learner (`model.learner.Learner`). While the frames run, a refusal from
    the injector or the core ends the run there and is raised, as `detect`'s is.
    """
    profile_name = weights.unpack(blob)["profile"]
    injected, truth = _inject.inject(profile_name, frames, schedule_records, length)
    _check_script(script, length)
    learner = _learner.Learner(blob, truth, update_frames, count_bits, epoch)
    records, outcomes = _learning_run(learner, injected, script)
    return records, truth, outcomes, learner


def _check_script(script, length):
    if not isinstance(script, dict):
        raise Refusal("RECORD_FIELD", "a script is a dict from a next index to a list of operations")
    for index, ops in script.items():
        if type(index) is not int or not 0 <= index <= length or not isinstance(ops, (list, tuple)):
            raise Refusal("RECORD_FIELD", "a script's index is an int 0..%d with a list of operations, not %r"
                          % (length, index))
        for op in ops:
            if not isinstance(op, tuple) or len(op) != 2 or op[0] not in OPERATIONS:
                raise Refusal("RECORD_FIELD", "an operation is (one of %s, its argument), not %r"
                              % (", ".join(OPERATIONS), op))


def _learning_run(learner, injected, script):
    # The core's whole view of the world is `injected`, through the learner's `step`. Truth is the learner's.
    do = {"update": learner.update, "commit": learner.commit, "write_shadow": learner.write_shadow}
    records, outcomes, frames = [], [], iter(injected)
    while True:
        index = learner.next_index
        for op, argument in script.get(index, ()):
            try:
                do[op](argument)
                outcomes.append((index, op, argument, None))
            except Refusal as e:
                outcomes.append((index, op, argument, e.name))
        try:
            frame = next(frames)
        except StopIteration:
            return tuple(records), outcomes
        records.append(learner.step(frame))

"""Where a host operation may land: each operation's window of next indexes, and the model's run of a placed script.

THE MODEL MAKES AN OPERATION AT AN EXACT NEXT INDEX; THE CARD'S HOST CANNOT. Its write lands somewhere in the
bracket of two reads of next_index, one before the call and one after. So each operation of a case has a WINDOW
[lo, hi] of next indexes in which every placement gives the model's outcome and the same run, and the judge
requires each bracket inside its window (docs/host/lrn-c.md, section 3).

THE ARGUMENT, from model/learner.py and model/weights.py as read:
  - the score records change only at a commit, at the index its argument names, and an update's set depends
    only on its u (the sums at u); so a landing can change the run only by changing some operation's outcome;
  - an outcome depends only on which of these holds when the operation lands: an update named and not finished
    (from its naming to u + F); a commit scheduled and not yet made (to its index, inclusive, with a pool of 1);
    the next index against the argument. Each interval is fixed by the arguments, not by the landings, but an
    update's unfinished interval begins at its own naming, which the host's order puts before its followers.
So, by kind, with F the update time (`rule`):

    update(u), taken                lo: the last update's finish; the last commit's index + 1    hi: u
    update, UPDATE_UNFINISHED       lo: by order                                                 hi: that u + F - 1
    update, SWAP_PENDING            lo: by order                                                 hi: the commit's index
    update(u), SWAP_INDEX           lo: u + 1; the last finish; the last commit's index + 1      hi: by order
    commit(at), taken               lo: the last finish; the last commit's index + 1             hi: at
    commit, UPDATE_UNFINISHED       lo: by order                                                 hi: u + F - 1
    commit(at), SWAP_INDEX          lo: at + 1; the last finish; the last commit's index + 1     hi: by order
    write_shadow, taken             lo: the last finish; the last commit's index + 1             hi: by order
    write_shadow, UPDATE_UNFINISHED lo: by order                                                 hi: u + F - 1
    write_shadow, SWAP_PENDING      lo: by order                                                 hi: the commit's index
    clear, reads QUANTISE_INPUT     lo: the unmade update's finish                               hi: by order
    clear, reads nothing            lo: by order                                                 hi: the next unmade finish - 1

and every operation but a clear lands before an unmade update's finish that no clear before it has read (the
fabric latches QUANTISE_INPUT there, and the library would raise it "latched before this call"). "By order"
is None: the host's order bounds it. Any other outcome has no rule here, SCRIPT_WINDOW.

THE ARGUMENT IS HELD, NOT TRUSTED: tests/test_lrn_c_windows.py moves each operation of the short cases to lo,
to hi, to lo - 1 and to hi + 1, and `hw/lrnc/lrnc.py expect` runs the model with every operation at its lo at
once and at its hi at once, at full scale, and refuses the case, EDGES_DIFFER, unless both are the canonical run.

THE MODEL'S RUN (`run_script`) is `model.run._learning_run`'s loop, written out so that the records go to a sink
as they are made (7,340,032 records do not fit a list) and a clear can read the fabric's latch: at each next index
the operations placed there are made in order before its frame, and at the stream's length after its last frame.
tests/test_lrn_c_standin.py holds it equal to `model.run.learning` on the short cases.

THE FABRIC'S LATCH (lrn_refusal, docs/rtl/learn.md, section 3) is worked here, not in the model, which has none:
the library reads and clears it after every operation, so between operations it holds only an unmade update's
QUANTISE_INPUT, latched at that update's finish. An operation that lands on it is the library's "latched before
this call": not made, its outcome that name.

Desktop only: it imports the model.
"""
from spec import constants as C
from model import inject, source
from model import learner as ML
from model import records as MR
from model.refusal import Refusal

from hw.lrnc.errors import LrncRefusal

MODEL_OPS = ("update", "commit", "write_shadow")
OPS = MODEL_OPS + ("clear",)


def _max(*values):
    return max(v for v in values if v is not None)


def rule(script, outcomes, updates, frames, update_frames):
    """Each operation's window, [lo, hi] (None where the host's order bounds it), from the canonical run's outcomes.

    `script`: the operations in order, each {"op", "after", "arg" or "blob"}. `outcomes`: the canonical run's, one
    each (a name or None; for a clear the name it read). `updates`: the learner's `updates` of that run, the
    taken updates in order, each with its "u", "finish" and "outcome" ("made" or "unmade", or None if the run
    ends before it finishes). Returns a list of (lo, hi). SCRIPT_WINDOW for an outcome no rule covers."""
    F = update_frames
    last_finish, last_commit, last_u = 0, None, None
    unmade = [u["finish"] for u in updates if u.get("outcome") == "unmade"]
    taken_updates = iter(updates)
    out = []
    after_commit = (lambda: None if last_commit is None else last_commit + 1)
    for k, (op, got) in enumerate(zip(script, outcomes)):
        kind = op["op"]
        lo = hi = None
        if kind == "update" and got is None:
            lo, hi = _max(0, last_finish, after_commit()), op["arg"]
            u = next(taken_updates, None)
            if u is None or u["u"] != op["arg"]:
                raise LrncRefusal("SCRIPT_WINDOW", "operation %d: an update at %d taken, which the learner's updates "
                                  "do not hold" % (k, op["arg"]))
            last_u, last_finish = op["arg"], op["arg"] + F
        elif kind in MODEL_OPS and got == "UPDATE_UNFINISHED":
            if last_u is None:
                raise LrncRefusal("SCRIPT_WINDOW", "operation %d: UPDATE_UNFINISHED with no update named" % k)
            hi = last_u + F - 1
        elif kind in ("update", "write_shadow") and got == "SWAP_PENDING":
            if last_commit is None:
                raise LrncRefusal("SCRIPT_WINDOW", "operation %d: SWAP_PENDING with no commit taken" % k)
            hi = last_commit
        elif kind in ("update", "commit") and got == "SWAP_INDEX":
            lo = _max(op["arg"] + 1, last_finish, after_commit())
        elif kind == "commit" and got is None:
            lo, hi = _max(0, last_finish, after_commit()), op["arg"]
            last_commit = op["arg"]
        elif kind == "write_shadow" and got is None:
            lo = _max(0, last_finish, after_commit())
        elif kind == "clear" and got == "QUANTISE_INPUT":
            done = [f for f in unmade if f <= op["after"]]
            if not done:
                raise LrncRefusal("SCRIPT_WINDOW", "operation %d: a clear reads QUANTISE_INPUT with no unmade finish "
                                  "before it" % k)
            lo = max(done)
        elif kind == "clear" and got is None:
            later = [f for f in unmade if f > op["after"]]
            hi = min(later) - 1 if later else None
        else:
            raise LrncRefusal("SCRIPT_WINDOW", "operation %d (%s) has the outcome %r, which no window rule covers"
                              % (k, kind, got))
        out.append([lo, hi])
    # Every operation but a clear lands before an unmade finish that no earlier clear has read.
    for k, op in enumerate(script):
        if op["op"] == "clear":
            continue
        cleared = [s["after"] for s in script[:k] if s["op"] == "clear"]
        for f in unmade:
            if not any(c >= f for c in cleared):
                out[k][1] = f - 1 if out[k][1] is None else min(out[k][1], f - 1)
                break
    return [tuple(w) for w in out]


def check_canonical(script, wins, frames):
    """SCRIPT_WINDOW unless each operation's `after`, its canonical placement, is inside its own window."""
    for k, (op, (lo, hi)) in enumerate(zip(script, wins)):
        if (lo is not None and op["after"] < lo) or (hi is not None and op["after"] > hi) or op["after"] > frames:
            raise LrncRefusal("SCRIPT_WINDOW", "operation %d (%s) is placed at %d, outside its window [%s, %s]"
                              % (k, op["op"], op["after"], lo, hi))


def edge_placements(script, wins, frames):
    """(every operation at its lo, every operation at its hi), each kept in the script's order: lo is taken forward
    (an operation at least where the one before it is) and hi backward. SCRIPT_WINDOW if an order cannot be kept
    inside every window."""
    low, at = [], 0
    for lo, _hi in wins:
        at = max(at, 0 if lo is None else lo)
        low.append(at)
    high, at = [0] * len(wins), frames
    for k in range(len(wins) - 1, -1, -1):
        hi = wins[k][1]
        at = min(at, frames if hi is None else hi)
        high[k] = at
    for name, placed in (("lo", low), ("hi", high)):
        for k, (p, (lo, hi)) in enumerate(zip(placed, wins)):
            if (lo is not None and p < lo) or (hi is not None and p > hi):
                raise LrncRefusal("SCRIPT_WINDOW", "every operation at its %s: operation %d at %d leaves its window "
                                  "[%s, %s] to keep the order" % (name, k, p, lo, hi))
    return low, high


def margins(script, wins):
    """Each operation's margin, hi - after, where hi is not None."""
    return [None if hi is None else hi - op["after"] for op, (_lo, hi) in zip(script, wins)]


def run_script(profile, seed, sigma, frames, schedule, blob, script, placed, update_frames, count_bits, epoch=0,
               blobs=None, learner_class=ML.Learner, sink=None):
    """The model's run of `script` with operation k at next index placed[k]. Returns a dict:
      outcomes   one each: the refusal's name or None, and for a clear the name it read
      learner    the learner at the end
      latch      what lrn_refusal holds at the end, names in order
      records    how many score records were made
    `sink(bytes)` is handed each record's canonical bytes (model.records.pack's), in order. `blobs` maps a
    write_shadow's blob name to its bytes. A placement behind the stream or past its end, or falling, is
    SCRIPT_WINDOW. An operation that lands while the latch holds a name is not made and has that name for its
    outcome, as the library raises it, "latched before this call" (`expect` refuses such a case, SCRIPT_LATCH)."""
    if len(placed) != len(script) or any(b < a for a, b in zip(placed, placed[1:])) or (placed and placed[-1] > frames):
        raise LrncRefusal("SCRIPT_WINDOW", "the placements %r do not rise inside 0..%d for %d operations"
                          % (placed, frames, len(script)))
    noise = source.Noise(profile, seed, sigma[0], sigma[1], frames)
    injected, truth = inject.inject(profile, noise, schedule, frames)
    learner = learner_class(blob, truth, update_frames, count_bits, epoch)
    do = {"update": learner.update, "commit": learner.commit,
          "write_shadow": lambda name: learner.write_shadow(blobs[name])}
    outcomes, latch, seen, k, made = [], [], 0, 0, 0
    stream = iter(injected)

    def finishes():
        nonlocal seen
        while seen < len(learner.updates) and learner.updates[seen]["outcome"] is not None:
            if learner.updates[seen]["outcome"] == "unmade":
                latch.append("QUANTISE_INPUT")
            seen += 1

    while True:
        index = learner.next_index
        finishes()
        while k < len(script) and placed[k] == index:
            op = script[k]
            if op["op"] == "clear":
                outcomes.append(latch[0] if latch else None)
                del latch[:]
            elif latch:
                # The library reads lrn_refusal before its first write, and raises a code latched there "latched
                # before this call" with nothing written: the operation is not made, and the latch stays.
                outcomes.append(latch[0])
            else:
                try:
                    do[op["op"]](op["blob"] if op["op"] == "write_shadow" else op["arg"])
                    outcomes.append(None)
                except Refusal as e:
                    outcomes.append(e.name)
                finishes()
            k += 1
        try:
            frame = next(stream)
        except StopIteration:
            break
        record = learner.step(frame)
        made += 1
        if sink is not None:
            sink(MR.pack("score", record))
    if k != len(script):
        raise LrncRefusal("SCRIPT_WINDOW", "operation %d is placed at %d, which the stream never reached"
                          % (k, placed[k]))
    return {"outcomes": outcomes, "learner": learner, "latch": list(latch), "records": made}


def end_registers(learner, latch, update_frames, count_bits):
    """What the fabric's learner registers read at the end of a run, from the model's learner and the latch:
    lrn_update_at (u while an update is unfinished, else 0), lrn_status's six bits, lrn_refusal, the eight counts,
    the two caps."""
    status = learner.status()
    unfinished = status["named"] or status["running"]
    bits = dict(status, refused=int(bool(latch)), refused_again=int(len(latch) > 1))
    return {"lrn_update_at": learner_named_u(learner) if unfinished else 0,
            "lrn_status": dict((b, bits[b]) for b in sorted(C.REGISTER_BITS["lrn_status"],
                                                            key=lambda b: C.REGISTER_BITS["lrn_status"][b])),
            "lrn_refusal": latch[0] if latch else None,
            "counts": learner.counters(),
            "caps": {"lrn_cap_count_bits": count_bits, "lrn_cap_update_frames": update_frames}}


def learner_named_u(learner):
    """The u of the update named and not finished: the model keeps it only in its private state, so it is read
    there, and only here."""
    return learner._update["u"]

"""Rule 3, both ways round: a threshold belongs to one weight epoch and is refused for records of ANY other.

The round's verifier's clone held `hits` (tests/test_lrn_a_e1.py) with its check weakened from
"another epoch" to "a later epoch", and every test of this parcel passed. The tests tried a
threshold of an EARLIER epoch on later records, which is what a threshold kept after a weight
change is, and never the reverse. The document says "counting refuses records of any other
epoch", and nothing held the other half of that sentence.

This file holds both halves, on records written out here by hand. Its control runs the same check
on two copies of `hits`, each weakened to one direction, and each must be reported with exactly
the cases it lets through. The copies are made in the test from the source of the function as
shipped, with one comparison changed. Nothing shipped is changed.

WHAT THIS DOES NOT SHOW (stated limits). The records here are made by hand, not by a core: that a
core's records carry the epoch of the weights that made them is the swap gate's, and the
hand-over's tests. Six cases; a check broken for an epoch no case uses, such as one that compared
epochs modulo a number, would pass. And E1's own flow has one swap, so it never meets a threshold
of a later epoch than its records: this is a property of the function, held for whoever calls it
next.
"""
import inspect

import test_lrn_a_e1 as E1
from learn.errors import LearnRefusal

A = 1000            # a hand-over index; every record below is read well after A + 63

# (what, the threshold's epoch, the epoch of each of three records)
CASES = (
    ("a threshold of an earlier epoch on later records", 0, (1, 1, 1)),
    ("a threshold of a later epoch on earlier records", 1, (0, 0, 0)),
    ("one later record among the threshold's own", 1, (1, 2, 1)),
    ("one earlier record among the threshold's own", 1, (1, 0, 1)),
    ("records two epochs later", 0, (2, 2, 2)),
    ("records two epochs earlier", 2, (0, 0, 0)),
)
EARLIER_RECORDS = [what for what, t, epochs in CASES if min(epochs) < t]
LATER_RECORDS = [what for what, t, epochs in CASES if max(epochs) > t]


def records(epochs):
    return [{"index": A + 9000 + 128 * i, "epoch": e, "flags": 0, "score": 6 + i} for i, e in enumerate(epochs)]


def threshold(epoch):
    return {"threshold": 7.0, "m": 12000, "k": 120, "above": 120, "pfa_effective": 121 / 12001, "epoch": epoch}


def let_through(hits):
    """The cases this `hits` counts where it must refuse, THRESHOLD_STALE. It must also count a
    threshold's own epoch, at every epoch the cases use: scores 6, 7, 8 against 7 are no, no, yes."""
    for epoch in (0, 1, 2):
        assert hits(records((epoch,) * 3), threshold(epoch), A).tolist() == [False, False, True]
    through = []
    for what, t_epoch, epochs in CASES:
        try:
            hits(records(epochs), threshold(t_epoch), A)
        except LearnRefusal as e:
            assert e.name == "THRESHOLD_STALE", "%s: refused as %s" % (what, e.name)
            continue
        through.append(what)
    return through


def weakened(comparison):
    """A copy of the shipped `hits` whose epoch check is `comparison` in place of "is not"."""
    source = inspect.getsource(E1.hits)
    shipped = 'if r["epoch"] != threshold["epoch"]:'
    assert source.count(shipped) == 1, "the shipped check is not the one this control weakens"
    scope = dict(vars(E1))
    exec(source.replace(shipped, 'if r["epoch"] %s threshold["epoch"]:' % comparison), scope)
    assert scope["hits"] is not E1.hits
    return scope["hits"]


def test_gate_comparison_rules__rule_3_a_threshold_is_refused_for_records_of_any_other_epoch_earlier_or_later():
    assert let_through(E1.hits) == []
    assert len(CASES) == 6 and len(EARLIER_RECORDS) == len(LATER_RECORDS) == 3 and not set(EARLIER_RECORDS) & set(LATER_RECORDS)
    assert "a threshold of a later epoch on earlier records" in EARLIER_RECORDS
    assert "a threshold of an earlier epoch on later records" in LATER_RECORDS


def test_control_comparison_rules__rule_3_the_epoch_check_weakened_to_either_one_direction_is_reported():
    """The same check, on `hits` as the verifier's clone had it, and on its mirror image."""
    only_later_refused = let_through(weakened(">"))
    print("CONTROL rule 3, the epoch check weakened to 'a later epoch' (the fault the verifier's clone held): counted "
          "instead of refused: %s" % only_later_refused)
    assert only_later_refused == EARLIER_RECORDS != []
    only_earlier_refused = let_through(weakened("<"))
    print("CONTROL rule 3, the epoch check weakened to 'an earlier epoch': counted instead of refused: %s" % only_earlier_refused)
    assert only_earlier_refused == LATER_RECORDS != []
    assert let_through(weakened("!=")) == [], "the copy with nothing changed is the shipped function: the road can pass"

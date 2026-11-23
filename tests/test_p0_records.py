"""P0's tests of model/records.py.

Expected bytes come from vectors/p0/records.json, worked by hand. An expected digest is computed
here from those hand-worked bytes with hashlib directly, never through the code under test.
"""
import hashlib
import json
import os

import pytest

from spec import constants as C
from model import records
from model.refusal import Refusal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cases():
    with open(os.path.join(ROOT, "vectors", "p0", "records.json"), encoding="utf-8") as f:
        return json.load(f)["cases"]


def one_valid(kind):
    return dict([c["record"] for c in cases() if c["kind"] == kind][0])


def expected_digest(kind, hexes):
    # Stated again here on purpose, and not imported: what the digest is defined to be.
    h = hashlib.sha256(b"undertone-records\x00" + kind.encode("ascii") + b"\x00")
    for x in hexes:
        h.update(bytes.fromhex(x))
    return h.hexdigest()


def test_p0_pack_equals_the_hand_worked_bytes():
    seen = set()
    for case in cases():
        assert records.pack(case["kind"], case["record"]).hex() == case["hex"], case["why"]
        seen.add(case["kind"])
    assert seen == set(C.RECORDS) == {"score", "truth", "event"}, "every record kind has a hand-worked case"


def test_p0_packed_length_is_the_sum_of_the_declared_widths():
    for case in cases():
        bits = sum(f[1] for f in C.RECORDS[case["kind"]])
        assert len(bytes.fromhex(case["hex"])) * 8 == bits


def test_p0_digest_equals_the_hash_of_the_hand_worked_bytes_in_order():
    score = [c for c in cases() if c["kind"] == "score"]
    assert len(score) >= 2
    got, n = records.digest("score", [c["record"] for c in score])
    assert n == len(score)
    assert got == expected_digest("score", [c["hex"] for c in score])
    # every record counts, the first one too
    assert records.digest("score", [score[1]["record"]])[0] == expected_digest("score", [score[1]["hex"]])
    assert got != records.digest("score", [c["record"] for c in score[1:]])[0]


def test_p0_digest_changes_when_one_bit_of_any_record_changes():
    base = [c["record"] for c in cases() if c["kind"] == "score"]
    d0 = records.digest("score", base)[0]
    for i in range(len(base)):
        changed = [dict(r) for r in base]
        changed[i]["score"] ^= 1
        assert records.digest("score", changed)[0] != d0, "record %d does not reach the digest" % i
    assert records.digest("score", [dict(r) for r in base])[0] == d0


def test_p0_digest_depends_on_order():
    base = [c["record"] for c in cases() if c["kind"] == "score"]
    assert base[0] != base[1]
    assert records.digest("score", base)[0] != records.digest("score", base[::-1])[0]


def test_p0_digests_of_different_kinds_never_meet_even_when_their_bytes_do():
    # 18-byte truth records and 24-byte event records: four of one and three of the other are 72 bytes each.
    truth = [{"index": 0, "pulse_id": 0, "amplitude_num": 0, "amplitude_den": 1}] * 4
    event = [{"index": 0, "epoch": 0, "score": 0, "pre": 0, "post": 0}] * 3
    assert len(b"".join(records.pack("truth", r) for r in truth)) == 72
    assert len(b"".join(records.pack("event", r) for r in event)) == 72
    assert records.digest("truth", truth)[0] != records.digest("event", event)[0]
    empties = {records.digest(kind, [])[0] for kind in C.RECORDS}
    assert len(empties) == 3, "an empty sequence of one kind is not an empty sequence of another"
    assert records.digest("score", []) == (expected_digest("score", []), 0)


def every_field_bound():
    out = []
    for kind in sorted(C.RECORDS):
        for name, bits, sign in C.RECORDS[kind]:
            lo, hi = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if sign == "signed" else (0, (1 << bits) - 1)
            out.append((kind, name, lo, hi))
    return out


@pytest.mark.parametrize("kind,name,lo,hi", every_field_bound(),
                         ids=["%s.%s" % (b[0], b[1]) for b in every_field_bound()])
def test_p0_every_field_of_every_kind_is_refused_one_past_each_end(kind, name, lo, hi):
    for bad in (lo - 1, hi + 1):
        rec = one_valid(kind)
        rec[name] = bad
        with pytest.raises(Refusal) as e:
            records.pack(kind, rec)
        assert e.value.name == "RECORD_FIELD"
    if not (kind == "score" and name == "flags") and not (kind == "truth" and name == "amplitude_den"):
        for good in (lo, hi):
            rec = one_valid(kind)
            rec[name] = good
            assert len(records.pack(kind, rec)) * 8 == sum(f[1] for f in C.RECORDS[kind])


def test_p0_the_field_bounds_cover_all_three_kinds():
    assert {b[0] for b in every_field_bound()} == {"score", "truth", "event"}
    assert len(every_field_bound()) == 4 + 4 + 5


@pytest.mark.parametrize("value", [1.0, True, None, "1"])
def test_p0_a_field_that_is_not_an_int_is_refused_by_name(value):
    for kind in sorted(C.RECORDS):
        rec = one_valid(kind)
        rec["index"] = value
        with pytest.raises(Refusal) as e:
            records.pack(kind, rec)
        assert e.value.name == "RECORD_FIELD"


def test_p0_a_missing_or_an_extra_field_is_refused_by_name():
    for rec in ({"index": 0, "epoch": 0, "flags": 0}, {"index": 0, "epoch": 0, "flags": 0, "score": 0, "x": 1},
                [("index", 0)], None):
        with pytest.raises(Refusal) as e:
            records.check("score", rec)
        assert e.value.name == "RECORD_FIELD"


def test_p0_every_reserved_flag_bit_is_refused_and_every_declared_one_accepted():
    refused = accepted = 0
    for bit in range(8):
        rec = {"index": 0, "epoch": 0, "flags": 1 << bit, "score": 0}
        if bit in C.FLAGS.values():
            assert records.check("score", rec) is rec
            accepted += 1
        else:
            with pytest.raises(Refusal) as e:
                records.check("score", rec)
            assert e.value.name == "RESERVED_BITS"
            refused += 1
    assert (accepted, refused) == (2, 6)


def test_p0_a_truth_record_with_a_zero_denominator_is_refused_by_name():
    rec = one_valid("truth")
    rec["amplitude_den"] = 0
    with pytest.raises(Refusal) as e:
        records.pack("truth", rec)
    assert e.value.name == "RECORD_FIELD"
    rec["amplitude_den"] = 1
    assert len(records.pack("truth", rec)) == 18


@pytest.mark.parametrize("bad", ["no-such-kind", "", None, 3, [], {}, ("score",)])
def test_p0_anything_but_a_declared_kind_is_refused_by_name_everywhere(bad):
    for call in (lambda: records.fields(bad), lambda: records.check(bad, {}), lambda: records.pack(bad, {}),
                 lambda: records.digest(bad, []), lambda: records.digest(bad, [{}])):
        with pytest.raises(Refusal) as e:
            call()
        assert e.value.name == "RECORD_KIND"

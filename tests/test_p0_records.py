"""P0's tests of model/records.py. Expected bytes come from vectors/p0/records.json, worked by hand."""
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


def test_p0_pack_equals_the_hand_worked_bytes():
    seen = set()
    for case in cases():
        assert records.pack(case["kind"], case["record"]).hex() == case["hex"], case["why"]
        seen.add(case["kind"])
    assert seen == set(C.RECORDS), "every record kind has a hand-worked case"


def test_p0_packed_length_is_the_sum_of_the_declared_widths():
    for case in cases():
        bits = sum(f[1] for f in C.RECORDS[case["kind"]])
        assert len(bytes.fromhex(case["hex"])) * 8 == bits


def test_p0_digest_changes_when_one_bit_of_one_record_changes():
    base = [c["record"] for c in cases() if c["kind"] == "score"]
    assert len(base) >= 2
    changed = [dict(r) for r in base]
    changed[-1]["score"] ^= 1
    d0, n0 = records.digest("score", base)
    d1, n1 = records.digest("score", changed)
    assert n0 == n1 == len(base)
    assert d0 != d1
    assert records.digest("score", [dict(r) for r in base])[0] == d0


def test_p0_digest_depends_on_order():
    base = [c["record"] for c in cases() if c["kind"] == "score"]
    assert base[0] != base[1]
    assert records.digest("score", base)[0] != records.digest("score", base[::-1])[0]


@pytest.mark.parametrize("field,value", [("index", -1), ("index", 1 << 64), ("epoch", 1 << 32),
                                         ("score", 1 << 63), ("score", -(1 << 63) - 1), ("score", 1.0),
                                         ("score", True)])
def test_p0_a_field_that_does_not_fit_is_refused_by_name(field, value):
    rec = {"index": 0, "epoch": 0, "flags": 0, "score": 0}
    rec[field] = value
    with pytest.raises(Refusal) as e:
        records.pack("score", rec)
    assert e.value.name == "RECORD_FIELD"


def test_p0_a_missing_or_an_extra_field_is_refused_by_name():
    for rec in ({"index": 0, "epoch": 0, "flags": 0}, {"index": 0, "epoch": 0, "flags": 0, "score": 0, "x": 1}):
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


def test_p0_an_unknown_record_kind_is_refused_by_name():
    with pytest.raises(Refusal) as e:
        records.pack("no-such-kind", {})
    assert e.value.name == "RECORD_KIND"

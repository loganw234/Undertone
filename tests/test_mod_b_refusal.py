"""The refusal gate: everything outside the contract is refused, each under its own name.

One table of cases. A case is a name and a call made through a `Model`, the model's entry points. The
check (`finding`) makes the call and reports anything but a Refusal of exactly that name.

The controls hand the same check two broken models, built here as wrappers round the shipped entry
points: one that ACCEPTS the case, and one that refuses it under ANOTHER declared name. Each must be
reported, for every case in the table.

Blobs with a header that disagrees with its body are written by `test_mod_b_support.forge`, from the
layout and with a correct hash, since the model's own `pack` refuses to write them.
"""
import hashlib
from fractions import Fraction

import pytest

from spec import constants as C
from model import scorer, weights
from model.detector import Core
from model.refusal import Refusal

import test_mod_b_support as S

PROFILES = S.PROFILES

# The names MOD-B's modules raise. RECORD_KIND is the one P0 name they cannot reach: they only ever name
# the kinds "score" and "event". SHAPE_ROWS needs a profile with more than one channel.
MOD_B_NAMES = {"PROFILE_UNKNOWN", "CHANNELS", "SAMPLE_RANGE", "SHAPE_FILTERS", "SHAPE_TAPS", "RESERVED_BITS",
               "BLOB_HASH", "SWAP_PENDING", "RECORD_FIELD", "SHAPE_CHANNEL", "SHAPE_ROWS", "SHAPE_RECTIFIER",
               "SHAPE_POOL", "SHAPE_SHIFT", "WEIGHT_COUNT", "WEIGHT_RANGE", "BLOB_FORMAT", "SWAP_SHAPE",
               "SWAP_INDEX", "SWAP_EPOCH", "SCORER_THRESHOLD", "SCORER_WINDOW", "SCORER_BINS", "RECORD_ORDER",
               "QUANTISE_INPUT"}


class Model:
    """The model's entry points, as the cases call them."""
    pack = staticmethod(weights.pack)
    unpack = staticmethod(weights.unpack)
    quantise = staticmethod(weights.quantise)
    matched_filter = staticmethod(weights.matched_filter)
    Store = weights.Store
    Core = Core
    Scorer = scorer.Scorer


def finding(case, model):
    """None when the model refuses the case under its own name; otherwise what it did instead."""
    name, _label, call = case
    try:
        call(model)
    except Refusal as e:
        return None if e.name == name else "refused as %s, not %s" % (e.name, name)
    return "accepted, not refused as %s" % name


# ------------------------------------------------------------------ the cases

def scorer_args(profile, **changed):
    args = {"profile": profile, "threshold": 0, "pre": 1, "post": 1, "hist_lo": 0, "hist_shift": 0, "hist_bins": 4}
    args.update(changed)
    return args


def table(profile):
    p = C.PROFILES[profile]
    channels, last = p["channels"], p["channels"] - 1
    good = {"filters": [{last: (1, 2)}], "head": (1,), "rectifier": C.RECTIFIERS["pass"], "pool": 1, "score_shift": 0}
    frame = tuple(range(1, channels + 1))
    record = {"index": 0, "epoch": 0, "flags": 0, "score": 0}
    score_bits = dict((f[0], f[1]) for f in C.RECORDS["score"])
    event_bits = dict((f[0], f[1]) for f in C.RECORDS["event"])
    out = []

    def case(name, label, call):
        out.append((name, label, call))

    def packing(refusal, label, **changed):
        args = dict(good, **changed)
        case(refusal, "pack: " + label, lambda m: m.pack(profile, **args))

    def forged(refusal, label, **changed):
        args = dict(good)
        keywords = {k: changed.pop(k) for k in list(changed) if k not in good}
        args.update(changed)
        blob = S.forge(profile, **args, **keywords)
        case(refusal, "unpack: " + label, lambda m: m.unpack(blob))
        case(refusal, "Core: " + label, lambda m: m.Core(blob))

    def good_blob(**changed):
        return S.forge(profile, **dict(good, **changed))

    # -- the profile
    case("PROFILE_UNKNOWN", "pack: a name that is not declared", lambda m: m.pack("s8x1", **good))
    forged("PROFILE_UNKNOWN", "a name that is not declared", name=b"s8x1")
    forged("PROFILE_UNKNOWN", "a name that is not ASCII", name=bytes([0xC3, 0x28]))
    case("PROFILE_UNKNOWN", "Scorer: a name that is not declared", lambda m: m.Scorer(**scorer_args("s8x1")))
    case("PROFILE_UNKNOWN", "matched_filter: a name that is not declared", lambda m: m.matched_filter("s8x1", (1, 2), (1,)))

    # -- the shape: one past each maximum, one below each minimum
    packing("SHAPE_FILTERS", "one filter past the maximum", filters=[{last: (1, 2)}] * (C.MAX_FILTERS + 1),
            head=(1,) * (C.MAX_FILTERS + 1))
    packing("SHAPE_FILTERS", "no filter", filters=[], head=())
    packing("SHAPE_FILTERS", "filters that are not a list", filters=None)
    forged("SHAPE_FILTERS", "one filter past the maximum", nfilters=C.MAX_FILTERS + 1)
    forged("SHAPE_FILTERS", "no filter", nfilters=0)
    packing("SHAPE_TAPS", "one tap past the maximum", filters=[{last: (1,) * (C.MAX_TAPS + 1)}])
    packing("SHAPE_TAPS", "no tap", filters=[{last: ()}])
    forged("SHAPE_TAPS", "one tap past the maximum", ntaps=C.MAX_TAPS + 1)
    forged("SHAPE_TAPS", "no tap", ntaps=0)
    for code in (max(C.RECTIFIERS.values()) + 1, 255):
        forged("SHAPE_RECTIFIER", "the undeclared code %d" % code, rectifier=code)
    for code in (max(C.RECTIFIERS.values()) + 1, -1, True, None):
        packing("SHAPE_RECTIFIER", "the undeclared code %r" % (code,), rectifier=code)
    forged("SHAPE_SHIFT", "one past the maximum", score_shift=C.MAX_SCORE_SHIFT + 1)
    for shift in (C.MAX_SCORE_SHIFT + 1, -1, True):
        packing("SHAPE_SHIFT", "a shift of %r" % (shift,), score_shift=shift)
    for pool in (C.MAX_POOL + 1, 0):
        forged("SHAPE_POOL", "a pool of %d" % pool, pool=pool)
    for pool in (C.MAX_POOL + 1, 0, -1, True):
        packing("SHAPE_POOL", "a pool of %r" % (pool,), pool=pool)
    packing("SHAPE_CHANNEL", "a channel one past the profile's last", filters=[{channels: (1, 2)}])
    packing("SHAPE_CHANNEL", "channel -1", filters=[{-1: (1, 2)}])
    packing("SHAPE_CHANNEL", "a filter that reads no channel", filters=[{}])
    packing("SHAPE_CHANNEL", "a filter that is not a mapping", filters=[(1, 2)])
    packing("SHAPE_CHANNEL", "a channel that is a bool", filters=[{True: (1, 2)}])
    forged("SHAPE_CHANNEL", "a mask of zero", masks=[0])
    for bit in range(channels, weights.MASK_BITS):
        forged("SHAPE_CHANNEL", "mask bit %d, a channel the profile does not have" % bit, masks=[1 << last | 1 << bit])
    if channels > 1:
        whole = {c: (1, 2) for c in range(channels)}
        full, rest = divmod(C.MAX_ROWS + 1, channels)
        over = [whole] * full + ([{c: (1, 2) for c in range(rest)}] if rest else [])
        assert sum(len(f) for f in over) == C.MAX_ROWS + 1 and len(over) <= C.MAX_FILTERS
        packing("SHAPE_ROWS", "one row past the maximum", filters=over, head=(1,) * len(over))
        forged("SHAPE_ROWS", "one row past the maximum", filters=over, head=(1,) * len(over))

    # -- the weights
    if channels > 1:
        packing("WEIGHT_COUNT", "a second row of another length", filters=[{0: (1, 2), last: (1, 2, 3)}])
    packing("WEIGHT_COUNT", "a second filter of another length", filters=[{last: (1, 2)}, {last: (1, 2, 3)}], head=(1, 1))
    packing("WEIGHT_COUNT", "a head weight too many", head=(1, 1))
    packing("WEIGHT_COUNT", "no head weight", head=())
    packing("WEIGHT_COUNT", "a head that is not a list", head=1)
    for bad in (C.COEFF_MAX + 1, C.COEFF_MIN - 1):
        packing("WEIGHT_RANGE", "the coefficient %d" % bad, filters=[{last: (1, bad)}])
        packing("WEIGHT_RANGE", "the head weight %d" % bad, head=(bad,))
        forged("WEIGHT_RANGE", "the coefficient %d" % bad, filters=[{last: (bad, 2)}])
        forged("WEIGHT_RANGE", "the head weight %d" % bad, head=(bad,))
    for bad in (True, 1.0, None, "1"):
        packing("WEIGHT_RANGE", "the coefficient %r" % (bad,), filters=[{last: (1, bad)}])
        packing("WEIGHT_RANGE", "the head weight %r" % (bad,), head=(bad,))

    # -- the blob
    whole_blob = good_blob()
    for bad in ("a string", None, bytearray(whole_blob), 7):
        case("BLOB_FORMAT", "unpack: %s, which is not bytes" % type(bad).__name__, lambda m, bad=bad: m.unpack(bad))
    case("BLOB_FORMAT", "unpack: no bytes", lambda m: m.unpack(b""))
    case("BLOB_FORMAT", "unpack: one byte short of the smallest blob", lambda m: m.unpack(whole_blob[:weights.SMALLEST - 1]))
    forged("BLOB_FORMAT", "another magic", magic=b"UNDTBLOX")
    forged("BLOB_FORMAT", "version 2", version=2)
    forged("BLOB_FORMAT", "version 0", version=0)
    forged("BLOB_FORMAT", "four bytes too many", extra=bytes(4))
    forged("BLOB_FORMAT", "a header that says one tap more than the body holds", ntaps=3)
    forged("BLOB_FORMAT", "a header that says one filter more than the body holds", nfilters=2)
    forged("BLOB_FORMAT", "a header whose channel masks alone would run past the end", nfilters=C.MAX_FILTERS)
    long_name = S.forge(profile, **good)
    long_name = long_name[:10] + bytes([200]) + long_name[11:-32]
    long_name += hashlib.sha256(long_name).digest()
    case("BLOB_FORMAT", "unpack: a name length that runs past the end", lambda m: m.unpack(long_name))
    for position in range(len(whole_blob)):
        damaged = whole_blob[:position] + bytes([whole_blob[position] ^ 0x10]) + whole_blob[position + 1:]
        case("BLOB_HASH", "unpack: one bit changed in byte %d" % position, lambda m, damaged=damaged: m.unpack(damaged))
    case("BLOB_HASH", "Core: one bit changed in a coefficient",
         lambda m: m.Core(whole_blob[:-40] + bytes([whole_blob[-40] ^ 1]) + whole_blob[-39:]))
    for bit in range(32):
        forged("RESERVED_BITS", "reserved bit %d of the blob" % bit, reserved=1 << bit)

    # -- the stream, at the core
    for channel in range(channels):
        for bad in (p["sample_min"] - 1, p["sample_max"] + 1):
            wrong = tuple(bad if c == channel else v for c, v in enumerate(frame))
            case("SAMPLE_RANGE", "step: %d on channel %d" % (bad, channel), lambda m, wrong=wrong: m.Core(whole_blob).step(wrong))
    case("CHANNELS", "step: a channel too many", lambda m: m.Core(whole_blob).step(frame + (0,)))
    case("CHANNELS", "step: a channel too few", lambda m: m.Core(whole_blob).step(frame[:-1]))
    case("CHANNELS", "matched_filter: a gain too many", lambda m: m.matched_filter(profile, (1, 2), (1,) * (channels + 1)))

    # -- the swap
    def after(n, then, blob=whole_blob, epoch=0):
        def call(m):
            core = m.Core(blob, epoch)
            for _ in range(n):
                core.step(frame)
            then(core)
        return call

    other_shapes = [("another tap count", dict(filters=[{last: (1, 2, 3)}])),
                    ("another filter count", dict(filters=[{last: (1, 2)}] * 2, head=(1, 1))),
                    ("another rectifier", dict(rectifier=C.RECTIFIERS["abs"])),
                    ("another pool", dict(pool=2)),
                    ("another shift", dict(score_shift=1))]
    if channels > 1:
        other_shapes.append(("another channel", dict(filters=[{0: (1, 2)}])))
    other_profile = [name for name in PROFILES if name != profile][0]
    other_last = C.PROFILES[other_profile]["channels"] - 1
    foreign = S.forge(other_profile, **dict(good, filters=[{other_last: (1, 2)}]))
    case("SWAP_SHAPE", "write_shadow: a blob for another profile", after(0, lambda core: core.write_shadow(foreign)))
    # the same again where the profile is the ONLY difference: both blobs are one filter of two taps on channel 0
    on_zero = dict(good, filters=[{0: (1, 2)}])
    assert weights.shape(weights.unpack(S.forge(profile, **on_zero)))[1:] == weights.shape(weights.unpack(S.forge(other_profile, **on_zero)))[1:]
    case("SWAP_SHAPE", "write_shadow: a blob that differs in its profile and in nothing else",
         after(0, lambda core: core.write_shadow(S.forge(other_profile, **on_zero)), blob=S.forge(profile, **on_zero)))
    for label, changed in other_shapes:
        case("SWAP_SHAPE", "write_shadow: " + label,
             after(2, lambda core, changed=changed: core.write_shadow(good_blob(**changed))))
    case("SWAP_PENDING", "commit: a second commit before the first one's index",
         after(1, lambda core: (core.commit(5), core.commit(6))))
    case("SWAP_PENDING", "commit: a second commit at the very same index",
         after(1, lambda core: (core.commit(5), core.commit(5))))
    case("SWAP_PENDING", "write_shadow: between a commit and its index",
         after(1, lambda core: (core.commit(5), core.write_shadow(whole_blob))))

    def while_settling(core):
        core.commit(2)
        for _ in range(3):
            core.step(frame)                      # outputs 0, 1, 2; with a pool of 3, outputs 2 and 3 mix
        core.commit(10)
    case("SWAP_PENDING", "commit: while the last swap's outputs still mix", after(0, while_settling, blob=good_blob(pool=3)))
    for at in (2, 0, -1, 1 << score_bits["index"], True, 3.0, None):
        case("SWAP_INDEX", "commit: at %r when the next output is 3" % (at,), after(3, lambda core, at=at: core.commit(at)))
    top = (1 << score_bits["epoch"]) - 1
    case("SWAP_EPOCH", "commit: when the epoch is the last its field holds", after(1, lambda core: core.commit(4), epoch=top))
    for start in (top + 1, -1, True, None):
        case("SWAP_EPOCH", "Core: a start epoch of %r" % (start,), lambda m, start=start: m.Core(whole_blob, start))
        case("SWAP_EPOCH", "Store: a start epoch of %r" % (start,), lambda m, start=start: m.Store(whole_blob, start))

    # -- the scorer
    score_top = (1 << (score_bits["score"] - 1)) - 1
    for bad in (score_top + 1, -score_top - 2, True, 1.0, None):
        case("SCORER_THRESHOLD", "Scorer: a threshold of %r" % (bad,), lambda m, bad=bad: m.Scorer(**scorer_args(profile, threshold=bad)))
        case("SCORER_BINS", "Scorer: a hist_lo of %r" % (bad,), lambda m, bad=bad: m.Scorer(**scorer_args(profile, hist_lo=bad)))
    for field in ("pre", "post"):
        for bad in (1 << event_bits[field], -1, True):
            case("SCORER_WINDOW", "Scorer: a %s of %r" % (field, bad),
                 lambda m, field=field, bad=bad: m.Scorer(**scorer_args(profile, **{field: bad})))
    for bad in (C.MAX_HIST_BINS + 1, 0, -1, True):
        case("SCORER_BINS", "Scorer: %r bins" % (bad,), lambda m, bad=bad: m.Scorer(**scorer_args(profile, hist_bins=bad)))
    for bad in (score_bits["score"], -1, True):
        case("SCORER_BINS", "Scorer: a hist_shift of %r" % (bad,), lambda m, bad=bad: m.Scorer(**scorer_args(profile, hist_shift=bad)))

    def fed(*pairs, close=False):
        def call(m):
            s = m.Scorer(**scorer_args(profile))
            for n, (f, r) in enumerate(pairs):
                if close and n == len(pairs) - 1:
                    s.close()
                s.feed(f, r)
        return call

    case("RECORD_ORDER", "feed: index 1 first", fed((frame, dict(record, index=1))))
    case("RECORD_ORDER", "feed: index 0 twice", fed((frame, record), (frame, record)))
    case("RECORD_ORDER", "feed: index 2 after index 0", fed((frame, record), (frame, dict(record, index=2))))
    case("RECORD_ORDER", "feed: after close", fed((frame, record), (frame, dict(record, index=1)), close=True))
    for bit in range(8):
        if C.FLAGS_RESERVED_MASK >> bit & 1:
            case("RESERVED_BITS", "feed: reserved flag bit %d" % bit, fed((frame, dict(record, flags=1 << bit))))
    case("RECORD_FIELD", "feed: a record with a field missing", fed((frame, {"index": 0, "epoch": 0, "flags": 0})))
    case("RECORD_FIELD", "feed: a score past its field", fed((frame, dict(record, score=score_top + 1))))
    case("CHANNELS", "feed: a channel too many", fed((frame + (0,), record)))
    case("SAMPLE_RANGE", "feed: a sample past the profile's range", fed(((p["sample_max"] + 1,) + frame[1:], record)))

    # -- the quantising rule
    for bad in ([], (), (0, 0), [0], [1.0, 2], [True, 2], ["1"], None, "12", 3, [None], [Fraction(0), 0]):
        case("QUANTISE_INPUT", "quantise: %r" % (bad,), lambda m, bad=bad: m.quantise(bad))
    case("QUANTISE_INPUT", "matched_filter: every gain zero", lambda m: m.matched_filter(profile, (1, 2), (0,) * channels))
    case("QUANTISE_INPUT", "matched_filter: a float in the pulse", lambda m: m.matched_filter(profile, (1, 0.5), (1,) * channels))
    case("QUANTISE_INPUT", "matched_filter: a float gain", lambda m: m.matched_filter(profile, (1, 2), (1.0,) * channels))
    case("SHAPE_TAPS", "matched_filter: a pulse one sample past the maximum",
         lambda m: m.matched_filter(profile, (1,) * (C.MAX_TAPS + 1), (1,) * channels))
    case("SHAPE_TAPS", "matched_filter: an empty pulse", lambda m: m.matched_filter(profile, (), (1,) * channels))
    return out


# ------------------------------------------------------------------ the gate

@pytest.mark.parametrize("profile", PROFILES)
def test_gate_refusal__every_case_is_refused_under_its_own_name(profile):
    cases = table(profile)
    reported = ["%s (%s): %s" % (c[0], c[1], finding(c, Model)) for c in cases if finding(c, Model) is not None]
    assert reported == []
    covered = {c[0] for c in cases}
    expected = MOD_B_NAMES if C.PROFILES[profile]["channels"] > 1 else MOD_B_NAMES - {"SHAPE_ROWS"}
    assert covered == expected, "every refusal MOD-B implements has a case, and no case names another"
    assert MOD_B_NAMES <= set(C.REFUSALS)
    assert len(cases) > 250
    assert sum(1 for c in cases if c[0] == "RESERVED_BITS") == 2 * 32 + 6, "every reserved bit, in the blob and in the flags"


def test_gate_refusal__the_profile_with_several_channels_reaches_the_row_bound():
    assert any(C.PROFILES[p]["channels"] > 1 for p in PROFILES)
    assert any(c[0] == "SHAPE_ROWS" for p in PROFILES for c in table(p))


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_refusal__what_is_just_inside_each_bound_is_accepted(profile):
    """The other direction: at each maximum and each minimum the model answers. A model that refused everything would pass the cases above."""
    p = C.PROFILES[profile]
    last = p["channels"] - 1
    good = {"filters": [{last: (1, 2)}], "head": (1,), "rectifier": 0, "pool": 1, "score_shift": 0}
    accepted = 0
    for changed in (dict(filters=[{last: (C.COEFF_MIN, C.COEFF_MAX)}], head=(C.COEFF_MIN,)),
                    dict(head=(C.COEFF_MAX,)),
                    dict(filters=[{last: (1,) * C.MAX_TAPS}]),
                    dict(filters=[{last: (1,)}]),
                    dict(filters=[{last: (1, 2)}] * min(C.MAX_FILTERS, C.MAX_ROWS), head=(1,) * min(C.MAX_FILTERS, C.MAX_ROWS)),
                    dict(pool=C.MAX_POOL), dict(score_shift=C.MAX_SCORE_SHIFT), dict(rectifier=C.RECTIFIERS["abs"])):
        args = dict(good, **changed)
        blob = weights.pack(profile, **args)
        assert blob == S.forge(profile, **args), "pack writes the layout"
        back = weights.unpack(blob)
        assert weights.pack(profile, *[back[k] for k in ("filters", "head", "rectifier", "pool", "score_shift")]) == blob
        Core(blob).step(tuple(p["sample_min"] if c % 2 else p["sample_max"] for c in range(p["channels"])))
        accepted += 1
    rows = [{c: (1, 2) for c in range(p["channels"])}] * (C.MAX_ROWS // p["channels"])
    left = C.MAX_ROWS - len(rows) * p["channels"]
    rows = rows + ([{c: (1, 2) for c in range(left)}] if left else [])
    assert sum(len(f) for f in rows) == C.MAX_ROWS
    weights.unpack(weights.pack(profile, **dict(good, filters=rows, head=(1,) * len(rows))))
    score_bits = dict((f[0], f[1]) for f in C.RECORDS["score"])
    top = (1 << score_bits["epoch"]) - 1
    core = Core(weights.pack(profile, **good), epoch=top - 1)
    core.commit(0)
    assert core.step(tuple(range(p["channels"])))["epoch"] == top
    for args in (scorer_args(profile, threshold=(1 << 63) - 1, pre=65535, post=65535, hist_bins=C.MAX_HIST_BINS, hist_shift=63),
                 scorer_args(profile, threshold=-(1 << 63), pre=0, post=0, hist_lo=-(1 << 63), hist_bins=1)):
        scorer.Scorer(**args)
        accepted += 1
    assert accepted == 10


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_refusal__a_refused_call_changes_nothing(profile):
    """After a refused frame, a refused shadow write and a refused commit, the core goes on as if they had not been made."""
    config = S.a_config(profile, taps=3, pool=2)
    frames = S.varied_frames(profile, 12, seed=13)
    plain = list(Core(S.blob_of(profile, config)).run(frames))
    core = Core(S.blob_of(profile, config))
    got = []
    for i, frame in enumerate(frames):
        if i == 4:
            for bad in (lambda: core.step(frame + (0,)), lambda: core.write_shadow(b"not a blob"),
                        lambda: core.commit(2), lambda: core.write_shadow(S.blob_of(profile, S.a_config(profile, taps=4, pool=2)))):
                with pytest.raises(Refusal):
                    bad()
        got.append(core.step(frame))
    assert S.compare("after refusals", got, plain) == []


@pytest.mark.parametrize("profile", PROFILES)
def test_gate_refusal__the_order_of_checks_is_the_documented_one(profile):
    """Two things wrong at once: the name is the one the documented order reaches first."""
    last = C.PROFILES[profile]["channels"] - 1
    good = {"filters": [{last: (1, 2)}], "head": (1,), "rectifier": 0, "pool": 1, "score_shift": 0}

    def name_of(call):
        with pytest.raises(Refusal) as e:
            call()
        return e.value.name

    damaged = S.forge(profile, **good, reserved=1, magic=b"XXXXXXXX")
    assert name_of(lambda: weights.unpack(damaged[:-1] + bytes([damaged[-1] ^ 1]))) == "BLOB_HASH"      # hash before magic
    assert name_of(lambda: weights.unpack(damaged)) == "BLOB_FORMAT"                                      # magic before reserved
    assert name_of(lambda: weights.unpack(S.forge(profile, **good, magic=b"XXXXXXXX", name=b"nope"))) == "BLOB_FORMAT"
    assert name_of(lambda: weights.unpack(S.forge(profile, **good, reserved=1, name=b"nope"))) == "PROFILE_UNKNOWN"
    assert name_of(lambda: weights.unpack(S.forge(profile, **good, reserved=1, nfilters=0))) == "RESERVED_BITS"
    assert name_of(lambda: weights.unpack(S.forge(profile, **good, nfilters=0, ntaps=0))) == "SHAPE_FILTERS"
    assert name_of(lambda: weights.unpack(S.forge(profile, **dict(good, rectifier=9), ntaps=0))) == "SHAPE_TAPS"
    assert name_of(lambda: weights.unpack(S.forge(profile, **dict(good, rectifier=9, score_shift=99)))) == "SHAPE_RECTIFIER"
    assert name_of(lambda: weights.unpack(S.forge(profile, **dict(good, score_shift=99, pool=0)))) == "SHAPE_SHIFT"
    assert name_of(lambda: weights.unpack(S.forge(profile, **dict(good, pool=0), masks=[0]))) == "SHAPE_POOL"
    assert name_of(lambda: weights.unpack(S.forge(profile, **dict(good, pool=0), nfilters=C.MAX_FILTERS))) == "SHAPE_POOL"
    assert name_of(lambda: weights.unpack(S.forge(profile, **good, nfilters=C.MAX_FILTERS, masks=[0]))) == "BLOB_FORMAT"   # the masks' length before a mask
    assert name_of(lambda: weights.unpack(S.forge(profile, **good, masks=[0], extra=bytes(4)))) == "SHAPE_CHANNEL"
    assert name_of(lambda: weights.unpack(S.forge(profile, **dict(good, head=(1 << 20,)), extra=bytes(4)))) == "BLOB_FORMAT"
    assert name_of(lambda: weights.pack("nope", **dict(good, filters=[]))) == "PROFILE_UNKNOWN"
    assert name_of(lambda: weights.pack(profile, **dict(good, filters=[{}] * 99))) == "SHAPE_FILTERS"
    assert name_of(lambda: weights.pack(profile, **dict(good, filters=[{last: ()}, {}], head=(1, 1)))) == "SHAPE_CHANNEL"
    assert name_of(lambda: weights.pack(profile, **dict(good, filters=[{last: ()}], head=()))) == "SHAPE_TAPS"
    assert name_of(lambda: weights.pack(profile, **dict(good, head=(), rectifier=9))) == "WEIGHT_COUNT"
    assert name_of(lambda: weights.pack(profile, **dict(good, rectifier=9, score_shift=99))) == "SHAPE_RECTIFIER"
    assert name_of(lambda: weights.pack(profile, **dict(good, score_shift=99, pool=0))) == "SHAPE_SHIFT"
    assert name_of(lambda: weights.pack(profile, **dict(good, pool=0, head=(1 << 20,)))) == "SHAPE_POOL"

    if last > 0:                                             # SHAPE_ROWS's place, where a filter can have more than one row
        whole = {c: (1, 2) for c in range(last + 1)}
        over = [whole] * (C.MAX_ROWS // (last + 1) + 1)
        assert sum(len(f) for f in over) > C.MAX_ROWS and len(over) < C.MAX_FILTERS
        many = dict(good, filters=over, head=(1,) * len(over))
        assert name_of(lambda: weights.pack(profile, **dict(many, filters=over + [{last + 1: (1, 2)}]))) == "SHAPE_CHANNEL"
        assert name_of(lambda: weights.pack(profile, **dict(many, filters=[{c: () for c in whole}] * len(over)))) == "SHAPE_ROWS"
        seven = dict(many, filters=over + [whole], head=(1,) * (len(over) + 1))
        assert name_of(lambda: weights.unpack(S.forge(profile, **seven, masks=[(1 << (last + 1)) - 1] * len(over) + [0]))) == "SHAPE_CHANNEL"
        assert name_of(lambda: weights.unpack(S.forge(profile, **many, extra=bytes(4)))) == "SHAPE_ROWS"

    core = Core(weights.pack(profile, **good), epoch=(1 << 32) - 1)
    core.step(tuple(range(last + 1)))
    assert name_of(lambda: core.commit(0)) == "SWAP_INDEX"                     # the index before the epoch
    assert name_of(lambda: core.commit(5)) == "SWAP_EPOCH"
    core = Core(weights.pack(profile, **good))
    core.commit(5)
    assert name_of(lambda: core.commit(-1)) == "SWAP_PENDING"                  # pending before the index
    assert name_of(lambda: core.write_shadow(b"")) == "SWAP_PENDING"           # pending before the blob is read
    core = Core(weights.pack(profile, **good))
    assert name_of(lambda: core.write_shadow(b"")) == "BLOB_FORMAT"            # the blob's own refusal before its shape
    assert name_of(lambda: scorer.Scorer(**scorer_args("nope", threshold=None))) == "PROFILE_UNKNOWN"
    assert name_of(lambda: scorer.Scorer(**scorer_args(profile, threshold=None, pre=-1))) == "SCORER_THRESHOLD"
    assert name_of(lambda: scorer.Scorer(**scorer_args(profile, pre=-1, hist_bins=0))) == "SCORER_WINDOW"


# --------------------------------------------------------------- the controls

class Accepted:
    """What a model that accepts a case hands back: something that takes any further call."""

    def __getattr__(self, name):
        return self

    def __call__(self, *args, **kwargs):
        return self


def broken(target, name, how):
    """The entry point, or the object it returned, with ONE refusal name accepted or renamed."""
    plain = (bytes, dict, tuple, list, int, str, type(None), Accepted)

    class Wrapped:
        def __call__(self, *args, **kwargs):
            try:
                result = target(*args, **kwargs)
            except Refusal as e:
                if e.name != name:
                    raise
                if how == "accepts":
                    return Accepted()
                raise Refusal("RECORD_KIND" if name != "RECORD_KIND" else "BLOB_HASH", e.detail)
            return result if isinstance(result, plain) else broken(result, name, how)

        def __getattr__(self, attribute):
            value = getattr(target, attribute)
            return broken(value, name, how) if callable(value) else value

    return Wrapped()


def broken_model(name, how):
    class M:
        pass
    for entry in ("pack", "unpack", "quantise", "matched_filter", "Store", "Core", "Scorer"):
        setattr(M, entry, staticmethod(broken(getattr(Model, entry), name, how)))
    return M


@pytest.mark.parametrize("profile", PROFILES)
def test_control_refusal__a_model_that_accepts_the_case_is_caught_for_every_case(profile):
    cases = table(profile)
    missed = [c[:2] for c in cases if finding(c, broken_model(c[0], "accepts")) != "accepted, not refused as %s" % c[0]]
    assert missed == []
    one = cases[len(cases) // 2]
    print("CONTROL refusal, accepts, %s: %d cases, each reported; for example %s (%s): %s"
          % (profile, len(cases), one[0], one[1], finding(one, broken_model(one[0], "accepts"))))


@pytest.mark.parametrize("profile", PROFILES)
def test_control_refusal__a_model_that_refuses_under_the_wrong_name_is_caught_for_every_case(profile):
    cases = table(profile)
    missed = [c[:2] for c in cases if finding(c, broken_model(c[0], "renames")) != "refused as RECORD_KIND, not %s" % c[0]]
    assert missed == []
    one = cases[len(cases) // 2]
    print("CONTROL refusal, wrong name, %s: %d cases, each reported; for example %s (%s): %s"
          % (profile, len(cases), one[0], one[1], finding(one, broken_model(one[0], "renames"))))


@pytest.mark.parametrize("profile", PROFILES)
def test_control_refusal__a_model_built_with_a_maximum_one_higher_is_caught(profile, monkeypatch):
    """A second kind of broken model: not a wrapper, the shipped code reading a definition whose maxima are one higher."""
    cases = table(profile)                                   # built against the true maxima, before the patch
    bounds = {"MAX_FILTERS": "SHAPE_FILTERS", "MAX_TAPS": "SHAPE_TAPS", "MAX_POOL": "SHAPE_POOL",
              "MAX_SCORE_SHIFT": "SHAPE_SHIFT", "MAX_HIST_BINS": "SCORER_BINS", "COEFF_MAX": "WEIGHT_RANGE"}
    if C.PROFILES[profile]["channels"] > 1:
        bounds["MAX_ROWS"] = "SHAPE_ROWS"
    for constant, name in sorted(bounds.items()):
        with monkeypatch.context() as patch:
            patch.setattr(C, constant, getattr(C, constant) + 1)
            if constant == "MAX_FILTERS":
                patch.setattr(C, "MAX_ROWS", C.MAX_ROWS + 1)       # or the row bound would refuse it instead, under another name
            reported = [finding(c, Model) for c in cases if c[0] == name]
        assert any(f is not None for f in reported), "a %s one higher was not seen" % constant
        assert [finding(c, Model) for c in cases if c[0] == name] == [None] * len(reported), "and the shipped model is whole again"

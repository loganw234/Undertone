"""P0's tests of tools/gen_spec.py: a definition that does not make sense is refused by name, never crashed on.

Each case edits a copy of the real definition in a temporary tree. The expected refusal is the
first word of the generator's own message, so a refusal under the wrong name fails the test.
"""
import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import gen_spec  # noqa: E402


def tree(tmp_path, edits=(), pulse_edits=()):
    root = str(tmp_path)
    shutil.copytree(os.path.join(ROOT, "spec"), os.path.join(root, "spec"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    for path, changes in ((os.path.join(root, "spec", "undertone.toml"), edits),
                          (os.path.join(root, "spec", "pulses", "e0.toml"), pulse_edits)):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        for old, new in changes:
            assert text.count(old) == 1, "the case's anchor %r is not in the file exactly once" % old
            text = text.replace(old, new)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    return root


def test_p0_the_real_definition_is_accepted_and_its_copy_is_current(tmp_path):
    root = tree(tmp_path)
    assert gen_spec.check(root) == []


BAD = [
    ("an unknown section", [("[meta]", "[surprise]\nx = 1\n\n[meta]")], "SECTIONS"),
    ("a missing section", [("[quantise]\nscale = \"peak_to_max\"\nrounding = \"half_to_even\"\n", "")], "SECTIONS"),
    ("an unknown key in meta", [("spec_version = 1", "spec_version = 1\nextra = 2")], "KEYS"),
    ("an unknown key in core", [("max_taps = 128", "max_taps = 128\nmax_other = 3")], "KEYS"),
    ("a fourth record", [("\n# Bit positions", "extra = [[\"a\", 8, \"unsigned\"]]\n\n# Bit positions")], "KEYS"),
    ("a version that is a string", [("spec_version = 1", "spec_version = \"1\"")], "NUMBER"),
    ("a width that is a string", [("[profile.s16x1]\nsample_bits = 16", "[profile.s16x1]\nsample_bits = \"16\"")], "NUMBER"),
    ("a width that is a float", [("[profile.s16x1]\nsample_bits = 16", "[profile.s16x1]\nsample_bits = 16.5")], "NUMBER"),
    ("a channel count that is a bool", [("[profile.s16x1]\nsample_bits = 16\nchannels = 1", "[profile.s16x1]\nsample_bits = 16\nchannels = true")], "NUMBER"),
    ("a width of zero", [("[profile.s16x1]\nsample_bits = 16", "[profile.s16x1]\nsample_bits = 0")], "NUMBER"),
    ("a coefficient width of one", [("coeff_bits = 18", "coeff_bits = 1")], "NUMBER"),
    ("a coefficient width of two hundred", [("coeff_bits = 18", "coeff_bits = 200")], "NUMBER"),
    ("an extra key in a profile", [("[profile.s16x1]\nsample_bits = 16", "[profile.s16x1]\nextra = 1\nsample_bits = 16")], "KEYS"),
    ("another quantising rule", [("scale = \"peak_to_max\"\nrounding = \"half_to_even\"", "scale = \"peak_to_max\"\nrounding = \"half_up\"")], "QUANTISE"),
    ("a field named twice", [("[\"epoch\", 32, \"unsigned\"], [\"flags\", 8, \"unsigned\"]", "[\"index\", 32, \"unsigned\"], [\"flags\", 8, \"unsigned\"]")], "RECORD"),
    ("a field of 65 bits", [("[\"flags\", 8, \"unsigned\"], [\"score\", 64, \"signed\"]", "[\"flags\", 8, \"unsigned\"], [\"score\", 65, \"signed\"]")], "RECORD"),
    ("a field of one bit", [("[\"flags\", 8, \"unsigned\"], [\"score\", 64, \"signed\"]", "[\"flags\", 8, \"unsigned\"], [\"score\", 1, \"signed\"]")], "RECORD"),
    ("a score record with no flags field", [("[\"flags\", 8, \"unsigned\"], ", "")], "RECORD"),
    ("a signed flags field", [("[\"flags\", 8, \"unsigned\"], ", "[\"flags\", 8, \"signed\"], ")], "RECORD"),
    ("a field name with a quote in it", [("[\"pre\", 16, \"unsigned\"]", "[\"pr\\\"e\", 16, \"unsigned\"]")], "NAME"),
    ("a flag bit used twice", [("overflow = 1", "overflow = 0")], "FLAGS"),
    ("a flag bit outside the field", [("overflow = 1", "overflow = 8")], "FLAGS"),
    ("a negative flag bit", [("overflow = 1", "overflow = -1")], "FLAGS"),
    ("a lower-case refusal name", [("\"BLOB_HASH\"", "\"blob_hash\"")], "NAME"),
    ("a refusal name that is a number", [("\"BLOB_HASH\"", "7")], "NAME"),
    ("a refusal name listed twice", [("\"BLOB_HASH\"", "\"SWAP_PENDING\"")], "REFUSALS"),
    ("a pulse path that climbs out", [("e0 = \"pulses/e0.toml\"", "e0 = \"../pulses/e0.toml\"")], "PULSES"),
    ("a pulse file that is missing", [("e0 = \"pulses/e0.toml\"", "e0 = \"pulses/absent.toml\"")], "DEFINITION-MALFORMED"),
    ("an upper-case profile name", [("[profile.s16x1]", "[profile.S16X1]")], "NAME"),
    ("a row bound that is a string", [("max_rows = 16", "max_rows = \"16\"")], "NUMBER"),
    ("a row bound of zero", [("max_rows = 16", "max_rows = 0")], "NUMBER"),
    ("a row bound past the generator's range", [("max_rows = 16", "max_rows = 1025")], "NUMBER"),
    ("a histogram bound past the generator's range", [("max_hist_bins = 4096", "max_hist_bins = 65537")], "NUMBER"),
    ("a pool bound of zero", [("max_pool = 65536", "max_pool = 0")], "NUMBER"),
    ("a pool bound past the generator's range", [("max_pool = 65536", "max_pool = 16777217")], "NUMBER"),
    ("a shift bound of sixty-four", [("max_score_shift = 31", "max_score_shift = 64")], "NUMBER"),
    ("a negative shift bound", [("max_score_shift = 31", "max_score_shift = -1")], "NUMBER"),
    ("a hidden bound of zero", [("max_hidden = 12", "max_hidden = 0")], "NUMBER"),
    ("a hidden bound past the generator's range", [("max_hidden = 12", "max_hidden = 1025")], "NUMBER"),
    ("a hidden shift bound of sixty-four", [("max_hidden_shift = 31", "max_hidden_shift = 64")], "NUMBER"),
    ("a core with no hidden bound", [("max_hidden = 12\n", "")], "KEYS"),
    ("a refusal with no code", [("PROFILE_UNKNOWN = 1\n", "")], "REFUSAL_CODES"),
    ("a code for no refusal", [("PROFILE_UNKNOWN = 1\n", "PROFILE_UNKNOWN = 1\nNO_SUCH_REFUSAL = 200\n")], "REFUSAL_CODES"),
    ("a refusal code used twice", [("CHANNELS = 2\n", "CHANNELS = 1\n")], "REFUSAL_CODES"),
    ("a refusal code of zero", [("CHANNELS = 2\n", "CHANNELS = 0\n")], "REFUSAL_CODES"),
    ("a refusal code past a byte", [("CHANNELS = 2\n", "CHANNELS = 256\n")], "REFUSAL_CODES"),
    ("a word that is not 32 bits", [("word_bits = 32", "word_bits = 64")], "NUMBER"),
    ("a first offset that is not a whole word", [("first_offset = 0x10", "first_offset = 0x12")], "BUS"),
    ("a magic that does not fit an int", [("magic = 0x554E4454", "magic = 0xF54E4454")], "NUMBER"),
    # The last register, so that being off a word is its only fault: it overlaps nothing.
    ("a register at an offset that is not a whole word", [("cap_blob_versions = [0x64,", "cap_blob_versions = [0x66,")], "REGISTERS"),
    ("a register below the frame's first offset", [("id = [0x10,", "id = [0x0C,")], "REGISTERS"),
    ("a register past the frame's address bits", [("cap_blob_versions = [0x64,", "cap_blob_versions = [0x1000,")], "REGISTERS"),
    ("two registers that overlap", [("spec_version = [0x14,", "spec_version = [0x18,")], "REGISTERS"),
    ("a register inside another's words", [("cap_sample_bits = [0x38,", "cap_sample_bits = [0x34,")], "REGISTERS"),
    ("a register with an unknown access", [('id = [0x10, "ro", 1]', 'id = [0x10, "rx", 1]')], "REGISTERS"),
    ("a register of no words", [('id = [0x10, "ro", 1]', 'id = [0x10, "ro", 0]')], "REGISTERS"),
    ("a register that is not a triple", [('id = [0x10, "ro", 1]', 'id = [0x10, "ro"]')], "REGISTERS"),
    ("a bus with an unknown key", [("address_bits = 12", "address_bits = 12\nextra = 1")], "KEYS"),
    ("a histogram bound of zero", [("max_hist_bins = 4096", "max_hist_bins = 0")], "NUMBER"),
    ("a histogram bound that is a float", [("max_hist_bins = 4096", "max_hist_bins = 4096.0")], "NUMBER"),
    ("an unknown key in scorer", [("max_hist_bins = 4096", "max_hist_bins = 4096\nextra = 1")], "KEYS"),
    ("a core with no pool bound", [("max_pool = 65536\n", "")], "KEYS"),
    ("another rounding for an injected sample", [("[inject]\nrounding = \"half_to_even\"", "[inject]\nrounding = \"half_up\"")], "INJECT"),
    ("an unknown key in inject", [("[inject]\nrounding = \"half_to_even\"", "[inject]\nrounding = \"half_to_even\"\nextra = 1")], "KEYS"),
    ("a rectifier code used twice", [("abs = 1 ", "abs = 0 ")], "RECTIFIER"),
    ("a rectifier code of 256", [("abs = 1 ", "abs = 256 ")], "RECTIFIER"),
    ("a negative rectifier code", [("abs = 1 ", "abs = -1 ")], "RECTIFIER"),
    ("a rectifier code that is a bool", [("abs = 1 ", "abs = true ")], "RECTIFIER"),
    ("an upper-case rectifier name", [("abs = 1 ", "ABS = 1 ")], "NAME"),
    ("a rectifier section with no mode", [("pass = 0    # the filter's sum goes on unchanged\nabs = 1     # its magnitude goes on\n", "")], "RECTIFIER"),
    ("a pulse with no id", [("[pulse_ids]\ne0 = 0", "[pulse_ids]")], "PULSE_IDS"),
    ("an id for a pulse that is not declared", [("[pulse_ids]\ne0 = 0", "[pulse_ids]\ne0 = 0\ne1 = 1")], "PULSE_IDS"),
    ("a pulse id too large for the truth record's field", [("[pulse_ids]\ne0 = 0", "[pulse_ids]\ne0 = 65536")], "PULSE_IDS"),
    ("a negative pulse id", [("[pulse_ids]\ne0 = 0", "[pulse_ids]\ne0 = -1")], "PULSE_IDS"),
    ("a pulse id that is a string", [("[pulse_ids]\ne0 = 0", "[pulse_ids]\ne0 = \"0\"")], "PULSE_IDS"),
    ("a truth record with no pulse_id field", [("[\"pulse_id\", 16, \"unsigned\"], ", "")], "RECORD"),
    ("a signed pulse_id field", [("[\"pulse_id\", 16, \"unsigned\"], ", "[\"pulse_id\", 16, \"signed\"], ")], "RECORD"),
]


@pytest.mark.parametrize("why,edits,refusal", BAD, ids=[b[0] for b in BAD])
def test_p0_a_definition_that_makes_no_sense_is_refused_by_name(tmp_path, why, edits, refusal):
    root = tree(tmp_path, edits)
    with pytest.raises(gen_spec.Refused) as e:
        gen_spec.load(root)
    assert str(e.value).split(":")[0] == refusal, "%s was refused as %r" % (why, str(e.value))
    findings = gen_spec.check(root)
    assert len(findings) == 1 and findings[0][1].startswith("REFUSED " + refusal)


BAD_PULSE = [
    ("a sample too large for the narrowest profile and small enough for the widest", [("name = \"e0\"\nsamples = [\n        0,", "name = \"e0\"\nsamples = [\n    40000,")]),
    ("a sample that is a float", [("name = \"e0\"\nsamples = [\n        0,", "name = \"e0\"\nsamples = [\n      0.5,")]),
    ("a sample that is a bool", [("name = \"e0\"\nsamples = [\n        0,", "name = \"e0\"\nsamples = [\n     true,")]),
    ("a pulse that names itself something else", [("name = \"e0\"", "name = \"e1\"")]),
    ("a pulse file with an extra key", [("name = \"e0\"", "name = \"e0\"\nextra = 1")]),
]


@pytest.mark.parametrize("why,pulse_edits", BAD_PULSE, ids=[b[0] for b in BAD_PULSE])
def test_p0_a_pulse_that_makes_no_sense_is_refused_by_name(tmp_path, why, pulse_edits):
    root = tree(tmp_path, pulse_edits=pulse_edits)
    with pytest.raises(gen_spec.Refused) as e:
        gen_spec.load(root)
    assert str(e.value).split(":")[0] == "PULSES", "%s was refused as %r" % (why, str(e.value))


def test_p0_a_pulse_sample_at_either_end_of_the_narrowest_profile_is_accepted(tmp_path):
    for value in ("-32768", " 32767"):
        root = tree(tmp_path / value.strip(), pulse_edits=[("name = \"e0\"\nsamples = [\n        0,", "name = \"e0\"\nsamples = [\n   %s," % value)])
        d, pulses, _digest = gen_spec.load(root)
        assert pulses["e0"][0] == int(value)
    for value in ("-32769", " 32768"):
        root = tree(tmp_path / value.strip(), pulse_edits=[("name = \"e0\"\nsamples = [\n        0,", "name = \"e0\"\nsamples = [\n   %s," % value)])
        with pytest.raises(gen_spec.Refused) as e:
            gen_spec.load(root)
        assert str(e.value).split(":")[0] == "PULSES"


def second_pulse(tmp_path, tag, second_id):
    root = tree(tmp_path / tag, [("e0 = \"pulses/e0.toml\"", "e0 = \"pulses/e0.toml\"\ne1 = \"pulses/e1.toml\""),
                                 ("[pulse_ids]\ne0 = 0", "[pulse_ids]\ne0 = 0\ne1 = %s" % second_id)])
    with open(os.path.join(root, "spec", "pulses", "e1.toml"), "w", encoding="utf-8", newline="\n") as f:
        f.write("name = \"e1\"\nsamples = [0, 5, -5, 0]\n")
    return root


def test_p0_two_pulses_get_two_ids_and_cannot_share_one(tmp_path):
    d, pulses, _digest = gen_spec.load(second_pulse(tmp_path, "apart", "7"))
    assert d["pulse_ids"] == {"e0": 0, "e1": 7} and pulses["e1"] == [0, 5, -5, 0]
    text = gen_spec.render(d, pulses, _digest)
    assert "PULSE_IDS = {\n    \"e0\": 0,\n    \"e1\": 7,\n}" in text
    assert gen_spec.load(second_pulse(tmp_path, "top", "65535"))[0]["pulse_ids"]["e1"] == 65535
    with pytest.raises(gen_spec.Refused) as e:
        gen_spec.load(second_pulse(tmp_path, "shared", "0"))
    assert str(e.value).split(":")[0] == "PULSE_IDS"


def test_p0_a_bound_at_either_end_of_its_range_is_accepted(tmp_path):
    for tag, old, new in (("shift0", "max_score_shift = 31", "max_score_shift = 0"),
                          ("shift63", "max_score_shift = 31", "max_score_shift = 63"),
                          ("pool1", "max_pool = 65536", "max_pool = 1"),
                          ("pooltop", "max_pool = 65536", "max_pool = 16777216"),
                          ("rows1", "max_rows = 16", "max_rows = 1"),
                          ("rowstop", "max_rows = 16", "max_rows = 1024"),
                          ("bins1", "max_hist_bins = 4096", "max_hist_bins = 1"),
                          ("binstop", "max_hist_bins = 4096", "max_hist_bins = 65536"),
                          ("hidden1", "max_hidden = 12", "max_hidden = 1"),
                          ("hiddentop", "max_hidden = 12", "max_hidden = 1024"),
                          ("hshift0", "max_hidden_shift = 31", "max_hidden_shift = 0"),
                          ("hshift63", "max_hidden_shift = 31", "max_hidden_shift = 63"),
                          ("rect255", "abs = 1 ", "abs = 255 ")):
        d, _pulses, _digest = gen_spec.load(tree(tmp_path / tag, [(old, new)]))
        assert new.strip() in ("%s = %d" % (k, v) for sec in ("core", "rectifier", "scorer")
                               for k, v in d[sec].items())


FOLLOWS = [
    # (the edit to the definition, the line the generated copy must then carry, lines that must not move)
    ("max_filters = 16", "max_filters = 5", "MAX_FILTERS = 5", ["MAX_ROWS = 16", "MAX_TAPS = 128"]),
    ("max_rows = 16", "max_rows = 7", "MAX_ROWS = 7", ["MAX_FILTERS = 16", "MAX_TAPS = 128"]),
    ("max_taps = 128", "max_taps = 96", "MAX_TAPS = 96", ["MAX_FILTERS = 16", "MAX_ROWS = 16"]),
    ("max_pool = 65536", "max_pool = 1024", "MAX_POOL = 1024", ["MAX_HIST_BINS = 4096", "MAX_SCORE_SHIFT = 31"]),
    ("max_score_shift = 31", "max_score_shift = 21", "MAX_SCORE_SHIFT = 21", ["MAX_POOL = 65536", "MAX_HIDDEN_SHIFT = 31"]),
    ("max_hidden = 12", "max_hidden = 8", "MAX_HIDDEN = 8", ["MAX_HIDDEN_SHIFT = 31", "MAX_FILTERS = 16"]),
    ("max_hidden_shift = 31", "max_hidden_shift = 21", "MAX_HIDDEN_SHIFT = 21", ["MAX_SCORE_SHIFT = 31", "MAX_HIDDEN = 12"]),
    ("max_hist_bins = 4096", "max_hist_bins = 512", "MAX_HIST_BINS = 512", ["MAX_POOL = 65536"]),
    ("abs = 1 ", "abs = 9 ", "    \"abs\": 9,", ["    \"pass\": 0,"]),
    ("pass = 0 ", "pass = 4 ", "    \"pass\": 4,", ["    \"abs\": 1,"]),
    ("[pulse_ids]\ne0 = 0", "[pulse_ids]\ne0 = 300", "    \"e0\": 300,", ["MAX_ROWS = 16"]),
]


@pytest.mark.parametrize("old,new,line,still", FOLLOWS, ids=[f[1].strip().split("\n")[-1] for f in FOLLOWS])
def test_p0_each_generated_fact_follows_its_own_key_and_no_other(tmp_path, old, new, line, still):
    """Two facts that share a value today (16 filters, 16 rows) must not share a key in the generator.
    Each case changes one value and reads the generated text: its own line moves, its neighbours do not.

    What this cannot see: INJECT_ROUNDING and the two quantising constants. The generator accepts one
    value for each, so a generator that wrote them as fixed text would pass every test there can be."""
    lines = gen_spec.render(*gen_spec.load(tree(tmp_path, [(old, new)]))).split("\n")
    assert lines.count(line) == 1, "the generated copy does not carry %r exactly once" % line
    for other in still:
        assert lines.count(other) == 1, "%r moved when %r was edited" % (other, new)


def test_p0_a_stale_copy_is_reported_with_the_line_that_differs(tmp_path):
    root = tree(tmp_path, [("max_taps = 128", "max_taps = 64")])
    findings = gen_spec.check(root)
    # Every copy is stale, and each is named, with a line: the check does not stop at the first.
    assert [f[0] for f in findings] == ["spec/constants.py", "spec/undertone_pkg.sv", "spec/undertone.h"]
    assert all("differs from the definition at line" in f[1] for f in findings)

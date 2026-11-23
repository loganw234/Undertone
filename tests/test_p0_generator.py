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


def test_p0_a_stale_copy_is_reported_with_the_line_that_differs(tmp_path):
    root = tree(tmp_path, [("max_taps = 128", "max_taps = 64")])
    findings = gen_spec.check(root)
    assert len(findings) == 1
    assert findings[0][0] == "spec/constants.py" and "differs from the definition at line" in findings[0][1]

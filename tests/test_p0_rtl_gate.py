"""The gate's second size, as far as it can be held without Docker.

`bash verify/run.sh --with rtl` runs benches in the simulation image. What decides a verdict there is
plain Python that reads files: tools/check_rtl.py's `judge`, `manifest` and `expected_numbers`, and
tools/sim_image.py's naming of the image. These tests hold that Python on files written here, so the
first size of the gate, which needs no Docker, still sees a judge that passes what it must not.

What they cannot see: anything a simulator or a compiler does. The `rtl-*` stages are that.
"""
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_rtl  # noqa: E402
import gen_spec  # noqa: E402
import sim_image  # noqa: E402
from check_tree import Refusal  # noqa: E402

from spec import constants as C  # noqa: E402


# ---- the two new copies of the definition ----

def rendered():
    loaded = gen_spec.load(ROOT)
    sv = dict((m.group(1), int(m.group(2))) for m in
              re.finditer(r"^  localparam int ([A-Z0-9_]+) = (-?\d+);$", gen_spec.render_sv(*loaded), re.M))
    c = dict((m.group(1), int(m.group(2).strip("()"))) for m in
             re.finditer(r"^#define UNDERTONE_([A-Z0-9_]+) (\(?-?\d+\)?)$", gen_spec.render_c(*loaded), re.M))
    return sv, c


def test_p0_the_package_and_the_header_carry_the_same_names_and_the_same_values():
    sv, c = rendered()
    assert sv == c and len(sv) >= 60
    # Worked by hand from spec/undertone.toml's record formats and widths, not read from a generated copy:
    #   score = index 64 + epoch 32 + flags 8 + score 64 = 168 bits, and its score field starts at 64 + 32 + 8 = 104
    #   truth = 64 + 16 + 32 + 32 = 144;  event = 64 + 32 + 64 + 16 + 16 = 192
    #   an 18-bit signed coefficient runs from -2^17 = -131072 to 131071
    #   flags is 8 bits with bits 0 and 1 in use: the rest is 0b11111100 = 252
    by_hand = {"SCORE_INDEX_LSB": 0, "SCORE_EPOCH_LSB": 64, "SCORE_FLAGS_LSB": 96, "SCORE_SCORE_LSB": 104,
               "SCORE_RECORD_BITS": 168, "TRUTH_RECORD_BITS": 144, "EVENT_RECORD_BITS": 192,
               "SCORE_SCORE_SIGNED": 1, "SCORE_INDEX_SIGNED": 0, "TRUTH_AMPLITUDE_NUM_SIGNED": 1,
               "COEFF_BITS": 18, "COEFF_MIN": -131072, "COEFF_MAX": 131071, "FLAGS_RESERVED_MASK": 252,
               "FLAG_SETTLING_BIT": 0, "FLAG_OVERFLOW_BIT": 1, "RECTIFIER_PASS": 0, "RECTIFIER_ABS": 1,
               "PROFILE_COUNT": 2, "PROFILE_S16X1_SAMPLE_BITS": 16, "PROFILE_S24X3_CHANNELS": 3,
               "MAX_FILTERS": 16, "MAX_TAPS": 128, "MAX_POOL": 65536, "MAX_HIDDEN": 12, "PULSE_E0_ID": 0,
               # the register map: `id` is the first word above the kernel's own sixteen bytes, the version
               # follows it, and the hash's eight words follow that; "UNDT" is 0x55 0x4E 0x44 0x54
               "BUS_WORD_BITS": 32, "BUS_FIRST_OFFSET": 16, "BUS_MAGIC": 0x554E4454,
               "REG_ID_OFFSET": 16, "REG_ID_READABLE": 1, "REG_ID_WRITABLE": 0,
               "REG_SPEC_VERSION_OFFSET": 20, "REG_SPEC_HASH_OFFSET": 24, "REG_SPEC_HASH_WORDS": 8,
               "REG_CAP_SAMPLE_BITS_OFFSET": 56, "REFUSAL_NONE": 0, "REFUSAL_PROFILE_UNKNOWN": 1}
    for name, value in by_hand.items():
        assert sv[name] == value, name


def test_p0_both_copies_carry_the_definitions_hash():
    loaded = gen_spec.load(ROOT)
    assert ("256'h%s;" % C.SPEC_SHA256) in gen_spec.render_sv(*loaded)
    assert ('#define UNDERTONE_SPEC_SHA256 "%s"' % C.SPEC_SHA256) in gen_spec.render_c(*loaded)


def test_p0_the_checks_own_list_of_numbers_equals_the_generators():
    """Two derivations that share no code: the generator's from the definition, the check's from the
    Python copy. If they part, `rtl-spec` would report a difference that is this file's, not the copies'."""
    d, pulses, _digest = gen_spec.load(ROOT)
    generator = dict(row for _heading, rows in gen_spec.numbers(d, pulses) for row in rows)
    assert check_rtl.expected_numbers(check_rtl.constants(ROOT)) == generator


def edited_definition(tmp_path, old, new):
    root = str(tmp_path)
    shutil.copytree(os.path.join(ROOT, "spec"), os.path.join(root, "spec"), ignore=shutil.ignore_patterns("__pycache__"))
    path = os.path.join(root, "spec", "undertone.toml")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    assert text.count(old) == 1, old
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text.replace(old, new))
    return root


def test_p0_a_generated_name_that_two_entries_share_is_refused(tmp_path):
    # An event field named "record" would be EVENT_RECORD_BITS, which is also the event record's length.
    root = edited_definition(tmp_path, '["pre", 16, "unsigned"]', '["record", 16, "unsigned"]')
    with pytest.raises(gen_spec.Refused) as e:
        gen_spec.render_sv(*gen_spec.load(root))
    assert str(e.value).startswith("NAMES:") and "EVENT_RECORD_BITS" in str(e.value)
    assert [f[0] for f in gen_spec.check(root)] == ["spec/undertone.toml"]


def test_p0_a_generated_number_that_does_not_fit_an_int_is_refused(tmp_path):
    # A flags field of 64 bits makes the reserved mask 2^64 - 4, and both copies declare a plain int.
    root = edited_definition(tmp_path, '["flags", 8, "unsigned"]', '["flags", 64, "unsigned"]')
    with pytest.raises(gen_spec.Refused) as e:
        gen_spec.render_c(*gen_spec.load(root))
    assert str(e.value).startswith("NUMBER:") and "FLAGS_RESERVED_MASK" in str(e.value)


# ---- the judge: what reads a run's files ----

BENCH = {"name": "b", "profiles": ["s16x1"], "tests": ["identity", "other"], "identity": ["identity"],
         "mutant": [{"name": "m", "must_fail": ["identity"], "kind": "WORD"}]}


def results(path, **verdicts):
    cases = []
    for name, verdict in verdicts.items():
        inner = {"pass": "", "fail": '<failure message="a failure" />', "error": '<error message="an error" />',
                 "skip": "<skipped />"}[verdict]
        cases.append('<testcase classname="x" name="%s">%s</testcase>' % (name, inner))
    with open(path, "w", encoding="utf-8") as f:
        f.write('<testsuites><testsuite name="x">%s</testsuite></testsuites>' % "".join(cases))


def evidence(path, *lines):
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")


IDENTICAL = {"test": "identity", "verdict": "IDENTICAL", "records": 40, "model_digest": "aa", "rtl_digest": "aa"}
MISMATCH = {"test": "identity", "verdict": "MISMATCH", "kind": "WORD", "at": 0}


def good(tmp_path):
    out = str(tmp_path)
    results(os.path.join(out, "b.s16x1.xml"), identity="pass", other="pass")
    evidence(os.path.join(out, "b.s16x1.evidence.jsonl"), IDENTICAL, dict(IDENTICAL, records=2))
    results(os.path.join(out, "b.s16x1.mutant.m.xml"), identity="fail", other="pass")
    evidence(os.path.join(out, "b.s16x1.mutant.m.evidence.jsonl"), MISMATCH)
    return out


def wheres(findings):
    return sorted("%s | %s" % (where, what.split(":")[0]) for where, what in findings)


def test_p0_the_judge_passes_a_run_that_is_good_and_counts_what_it_read(tmp_path):
    findings, passed, records, nruns, nmutants, skips = check_rtl.judge([BENCH], good(tmp_path))
    assert (findings, passed, records, nruns, nmutants, skips) == ([], 2, 42, 1, 1, [])


def test_p0_the_judge_reports_a_run_with_no_results_whatever_the_runner_says(tmp_path):
    out = good(tmp_path)
    os.remove(os.path.join(out, "b.s16x1.xml"))
    os.remove(os.path.join(out, "b.s16x1.mutant.m.xml"))
    with open(os.path.join(out, "runs.json"), "w", encoding="utf-8") as f:
        json.dump([{"run": "b.s16x1", "what": "bench", "error": None}], f)     # the runner's account: all well
    findings = check_rtl.judge([BENCH], out)[0]
    assert wheres(findings) == ["b.s16x1 | NO-RESULTS", "b.s16x1.mutant.m | NO-RESULTS"]


def test_p0_the_judge_reports_an_empty_or_broken_results_file(tmp_path):
    out = good(tmp_path)
    with open(os.path.join(out, "b.s16x1.xml"), "w", encoding="utf-8") as f:
        f.write("<testsuites></testsuites>")
    assert wheres(check_rtl.judge([BENCH], out)[0]) == ["b.s16x1 | NO-RESULTS"]
    with open(os.path.join(out, "b.s16x1.xml"), "w", encoding="utf-8") as f:
        f.write("<testsuites><testsuite>")
    assert wheres(check_rtl.judge([BENCH], out)[0]) == ["b.s16x1 | NO-RESULTS"]


@pytest.mark.parametrize("verdicts, want", [
    (dict(identity="fail", other="pass"), ["b.s16x1 identity | FAIL"]),
    (dict(identity="pass", other="error"), ["b.s16x1 other | ERROR"]),
    (dict(identity="pass"), ["b.s16x1 other | NOT-RUN"]),
    (dict(identity="pass", other="pass", more="pass"), ["b.s16x1 more | UNKNOWN-TEST"]),
])
def test_p0_the_judge_reports_a_failed_a_missing_and_an_unknown_test(tmp_path, verdicts, want):
    out = good(tmp_path)
    results(os.path.join(out, "b.s16x1.xml"), **verdicts)
    assert wheres(check_rtl.judge([BENCH], out)[0]) == want


def test_p0_the_judge_reports_a_test_named_twice_in_one_results_file(tmp_path):
    """Two verdicts for one name: the judge cannot say which is the test's, so it is a finding, TWICE,
    whatever the two verdicts are. A verifier found this reading held by no test and no control."""
    out = good(tmp_path)
    with open(os.path.join(out, "b.s16x1.xml"), "w", encoding="utf-8") as f:
        f.write('<testsuites><testsuite name="x"><testcase classname="x" name="identity" />'
                '<testcase classname="x" name="identity" /><testcase classname="x" name="other" /></testsuite></testsuites>')
    assert check_rtl.read_results(os.path.join(out, "b.s16x1.xml"))["identity"] == ("twice", "")
    assert wheres(check_rtl.judge([BENCH], out)[0]) == ["b.s16x1 identity | TWICE"]


def test_p0_an_evidence_line_that_cannot_be_read_is_a_finding_of_its_run(tmp_path):
    out = good(tmp_path)
    with open(os.path.join(out, "b.s16x1.evidence.jsonl"), "a", encoding="utf-8") as f:
        f.write("this is not what the harness writes\n")
    assert wheres(check_rtl.judge([BENCH], out)[0]) == ["b.s16x1 | EVIDENCE-UNREADABLE"]


def test_p0_the_judge_names_a_skipped_test_and_does_not_count_it_as_passed(tmp_path):
    out = good(tmp_path)
    results(os.path.join(out, "b.s16x1.xml"), identity="pass", other="skip")
    findings, passed, _records, _nruns, _nmutants, skips = check_rtl.judge([BENCH], out)
    assert (findings, passed, skips) == ([], 1, ["b.s16x1 other"])


@pytest.mark.parametrize("lines, want", [
    ([], "NO-EVIDENCE"),
    ([dict(IDENTICAL, test="other")], "NO-EVIDENCE"),
    ([dict(IDENTICAL, rtl_digest="bb")], "EVIDENCE-DISAGREES"),
    ([dict(IDENTICAL, records=0)], "EVIDENCE-DISAGREES"),
    ([dict(IDENTICAL, model_digest="", rtl_digest="")], "EVIDENCE-DISAGREES"),
    ([IDENTICAL, MISMATCH], "EVIDENCE-DISAGREES"),
])
def test_p0_an_identity_test_that_passed_must_have_left_evidence_that_agrees(tmp_path, lines, want):
    out = good(tmp_path)
    evidence(os.path.join(out, "b.s16x1.evidence.jsonl"), *lines)
    assert wheres(check_rtl.judge([BENCH], out)[0]) == ["b.s16x1 identity | %s" % want]


@pytest.mark.parametrize("verdict, lines, want", [
    ("pass", [MISMATCH], "MUTANT-SURVIVED"),
    ("error", [MISMATCH], "MUTANT-SURVIVED"),
    ("fail", [], "MUTANT-WRONG-REASON"),
    ("fail", [dict(MISMATCH, kind="COUNT")], "MUTANT-WRONG-REASON"),
    ("fail", [dict(MISMATCH, test="other")], "MUTANT-WRONG-REASON"),
])
def test_p0_a_mutant_must_fail_the_named_test_for_the_named_reason(tmp_path, verdict, lines, want):
    out = good(tmp_path)
    results(os.path.join(out, "b.s16x1.mutant.m.xml"), identity=verdict, other="pass")
    evidence(os.path.join(out, "b.s16x1.mutant.m.evidence.jsonl"), *lines)
    assert wheres(check_rtl.judge([BENCH], out)[0]) == ["b.s16x1.mutant.m identity | %s" % want]


@pytest.mark.parametrize("named, left", [("COUNT", "WORD"), ("WORD", "COUNT"), ("UNKNOWN-BITS", "WORD"),
                                         ("COUNT", "UNKNOWN-BITS")])
def test_p0_a_mutant_named_for_one_kind_is_not_satisfied_by_another(tmp_path, named, left):
    """Each direction. A design named for putting out the wrong number of records, which failed because
    a word was wrong, failed for another reason: the bench did not see the fault the mutant is there for."""
    out = good(tmp_path)
    bench = dict(BENCH, mutant=[{"name": "m", "must_fail": ["identity"], "kind": named}])
    evidence(os.path.join(out, "b.s16x1.mutant.m.evidence.jsonl"), dict(MISMATCH, kind=left))
    assert wheres(check_rtl.judge([bench], out)[0]) == ["b.s16x1.mutant.m identity | MUTANT-WRONG-REASON"]
    evidence(os.path.join(out, "b.s16x1.mutant.m.evidence.jsonl"), dict(MISMATCH, kind=left), dict(MISMATCH, kind=named))
    assert check_rtl.judge([bench], out)[0] == []


def spec_tree(tmp_path, package_line=None, header_line=None):
    root = str(tmp_path)
    shutil.copytree(os.path.join(ROOT, "spec"), os.path.join(root, "spec"), ignore=shutil.ignore_patterns("__pycache__"))
    for name, line, before in (("undertone_pkg.sv", package_line, "endpackage"), ("undertone.h", header_line, "#endif")):
        if line is not None:
            path = os.path.join(root, "spec", name)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            assert text.count(before) == 1
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text.replace(before, line + "\n" + before))
    return root


def test_p0_the_real_copies_declare_the_same_names_and_nothing_the_patterns_cannot_read():
    sv, c, findings = check_rtl.declared(ROOT)
    assert findings == [] and sorted(sv) == sorted(c) and "SPEC_SHA256" in sv and len(sv) == len(set(sv))


@pytest.mark.parametrize("package_line, header_line, where", [
    ("  localparam logic [7:0] ODD = 8'd5;", None, "spec/undertone_pkg.sv line"),
    ("  parameter int ODD = 5;", None, "spec/undertone_pkg.sv line"),
    ("`define UNDERTONE_ODD 5", None, "spec/undertone_pkg.sv line"),
    (None, "  #define UNDERTONE_ODD 5", "spec/undertone.h line"),
    (None, "#define OTHER_PREFIX_ODD 5", "spec/undertone.h line"),
    (None, "# define UNDERTONE_ODD 5", "spec/undertone.h line"),
])
def test_p0_a_declaration_the_patterns_do_not_read_is_a_finding(tmp_path, package_line, header_line, where):
    findings = check_rtl.declared(spec_tree(tmp_path, package_line, header_line))[2]
    assert len(findings) == 1 and findings[0][0].startswith(where) and "cannot read" in findings[0][1]


def test_p0_a_number_declared_some_other_way_is_not_looked_for_and_the_docstring_says_so(tmp_path):
    """The stated limit, shown: an enum and a const in the header pass this reading unseen. The copies
    are generated, and it is the `generated` stage that holds their text."""
    root = spec_tree(tmp_path, header_line="enum { UNDERTONE_ODD = 3 };\nstatic const int undertone_odd = 4;")
    assert check_rtl.declared(root)[2] == []
    assert "NOT looked for" in check_rtl.__doc__


@pytest.mark.parametrize("kind, lines", [("", []), ("WORD", [MISMATCH])])
def test_p0_a_mutant_whose_named_test_is_not_in_its_results_has_not_failed_it(tmp_path, kind, lines):
    """A test that did not run did not fail. The results hold another test, failed, and the evidence may
    even name the missing one: the mutant still survived. A verifier was handed a judge that took absent
    for failed, and found it; nothing here held it before."""
    out = good(tmp_path)
    bench = dict(BENCH, mutant=[{"name": "m", "must_fail": ["identity"], "kind": kind}])
    results(os.path.join(out, "b.s16x1.mutant.m.xml"), other="fail")
    evidence(os.path.join(out, "b.s16x1.mutant.m.evidence.jsonl"), *lines)
    assert wheres(check_rtl.judge([bench], out)[0]) == ["b.s16x1.mutant.m identity | MUTANT-SURVIVED"]
    results(os.path.join(out, "b.s16x1.mutant.m.xml"), identity_renamed="fail")
    assert wheres(check_rtl.judge([bench], out)[0]) == ["b.s16x1.mutant.m identity | MUTANT-SURVIVED"]


def test_p0_a_mutant_asked_only_to_fail_needs_no_evidence(tmp_path):
    out = good(tmp_path)
    bench = dict(BENCH, mutant=[{"name": "m", "must_fail": ["other"], "kind": ""}])
    results(os.path.join(out, "b.s16x1.mutant.m.xml"), identity="pass", other="fail")
    assert check_rtl.judge([bench], out)[0] == []
    results(os.path.join(out, "b.s16x1.mutant.m.xml"), identity="fail", other="pass")
    assert wheres(check_rtl.judge([bench], out)[0]) == ["b.s16x1.mutant.m other | MUTANT-SURVIVED"]


# ---- the manifest ----

def test_p0_the_manifest_is_read_and_its_tests_are_found_in_the_bench_source():
    benches = check_rtl.manifest(ROOT)
    first = [b for b in benches if b["name"] == "p0-onetap"][0]
    assert first["profiles"] == ["s16x1", "s24x3"]
    assert first["tests"] == ["bit_identity_random", "bit_identity_extremes", "latency_is_one_clock",
                              "control_model_coefficient_bit", "control_model_other_fields",
                              "control_nothing_compared"]
    assert set(first["identity"]) <= set(first["tests"]) and len(first["mutant"]) == 7
    assert sorted(m["kind"] for m in first["mutant"]) == ["", "COUNT", "COUNT", "WORD", "WORD", "WORD", "WORD"]
    runs = [r[0] for r in check_rtl.runs_of([first])]
    assert len(runs) == 2 * (1 + 7) and runs[0] == "p0-onetap.s16x1" and runs[1] == "p0-onetap.s16x1.mutant.coefficient-bit"


BENCH_SOURCE = '''import cocotb
import other


@cocotb.test()
async def first(dut):
    pass


@cocotb.test
async def second(dut):
    pass


@other.test()
async def not_cocotbs(dut):
    pass


@test()
async def bare_name(dut):
    pass


async def helper(dut):
    pass


def outer():
    @cocotb.test()
    async def inner(dut):
        pass
'''


def test_p0_only_a_function_under_cocotbs_own_decorator_is_a_bench_test(tmp_path):
    """The list of tests a run must show is read from the bench's source. A helper, a function under some
    other decorator named test, and a function inside a function are not tests of the bench."""
    folder = tmp_path / "rtl" / "tb"
    folder.mkdir(parents=True)
    (folder / "bench_x.py").write_text(BENCH_SOURCE, encoding="utf-8")
    assert check_rtl.bench_tests(str(tmp_path), "bench_x") == ["first", "second"]


def manifest_tree(tmp_path, old, new):
    root = str(tmp_path)
    for rel in ("spec/constants.py", "spec/undertone_pkg.sv", "rtl/p0/onetap.sv", "rtl/tb/bench_p0_onetap.py",
                "rtl/tb/benches.toml"):
        os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
        shutil.copyfile(os.path.join(ROOT, rel), os.path.join(root, rel))
    path = os.path.join(root, "rtl", "tb", "benches.toml")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    assert text.count(old) == 1, old
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text.replace(old, new))
    return root


@pytest.mark.parametrize("old, new", [
    ('profiles = ["s16x1", "s24x3"]', 'profiles = ["s16x1", "s99x9"]'),
    ('profiles = ["s16x1", "s24x3"]', 'profiles = ["s16x1", "s16x1"]'),
    ('identity = ["bit_identity_random", "bit_identity_extremes"]', 'identity = ["bit_identity_random", "no_such_test"]'),
    ('identity = ["bit_identity_random", "bit_identity_extremes"]', 'identity = []'),
    ('must_fail = ["latency_is_one_clock"]', 'must_fail = ["no_such_test"]'),
    ('must_fail = ["latency_is_one_clock"]', 'must_fail = []'),
    ('kind = ""', 'kind = "SOMETHING"'),
    ('sources = ["spec/undertone_pkg.sv", "rtl/p0/onetap.sv"]', 'sources = ["spec/undertone_pkg.sv", "../outside.sv"]'),
    ('name = "p0-onetap"', 'name = "P0 Onetap"'),
    ('module = "bench_p0_onetap"', 'module = "bench_that_is_not_there"'),
    ('name = "stops-after-four"', 'name = "coefficient-bit"'),
    ('toplevel = "onetap"', 'toplevel = "onetap"\nextra = 1'),
])
def test_p0_a_manifest_that_cannot_be_read_exactly_is_refused(tmp_path, old, new):
    with pytest.raises(Refusal) as e:
        check_rtl.manifest(manifest_tree(tmp_path, old, new))
    assert str(e.value).startswith("MANIFEST-MALFORMED")


def test_p0_a_manifest_with_no_bench_is_refused_as_nothing_selected(tmp_path):
    root = manifest_tree(tmp_path, 'name = "p0-onetap"', 'name = "p0-onetap"')
    with open(os.path.join(root, "rtl", "tb", "benches.toml"), "w", encoding="utf-8") as f:
        f.write("# no bench\n")
    with pytest.raises(Refusal) as e:
        check_rtl.manifest(root)
    assert str(e.value).startswith("NOTHING-SELECTED")


# ---- the image's name ----

def docker_files(tmp_path, dockerfile=None, requirements=None):
    root = str(tmp_path)
    os.makedirs(os.path.join(root, "docker"))
    for rel, replacement in (("docker/Dockerfile.sim", dockerfile), ("docker/requirements-sim.txt", requirements)):
        with open(os.path.join(ROOT, rel), "rb") as f:
            data = f.read()
        with open(os.path.join(root, rel), "wb") as f:
            f.write(data if replacement is None else replacement(data))
    return root


def test_p0_the_images_name_follows_its_files_and_not_their_line_endings(tmp_path):
    same = sim_image.tag(docker_files(tmp_path / "a"))
    assert same == sim_image.tag(ROOT) and re.match(r"undertone-sim:[0-9a-f]{16}\Z", same)
    assert sim_image.tag(docker_files(tmp_path / "b", dockerfile=lambda d: d.replace(b"\n", b"\r\n"))) == same
    assert sim_image.tag(docker_files(tmp_path / "c", dockerfile=lambda d: d + b"# one more line\n")) != same
    assert sim_image.tag(docker_files(tmp_path / "d", requirements=lambda d: d.replace(b"cocotb==2.1.0", b"cocotb==2.1.1"))) != same


def test_p0_a_tree_without_its_docker_files_is_refused_by_name(tmp_path):
    with pytest.raises(sim_image.ImageRefusal) as e:
        sim_image.tag(str(tmp_path))
    assert e.value.name == "IMAGE-INPUT-MISSING"


def test_p0_the_pins_are_read_from_the_two_files(tmp_path):
    pins = sim_image.pins(ROOT)
    assert pins["iverilog"] == "12.0-2build2" and pins["pip"]["cocotb"] == "2.1.0"
    assert all(re.match(r"[0-9][0-9A-Za-z.]*\Z", v) for v in pins["pip"].values()) and len(pins["pip"]) == 7
    root = docker_files(tmp_path, requirements=lambda d: d + b"pytest\n")
    with pytest.raises(sim_image.ImageRefusal) as e:
        sim_image.pins(root)
    assert e.value.name == "IMAGE-INPUT-MALFORMED"


# ---- the runner's two sizes ----

def the_gates_own_bash():
    """The shell the gate itself runs under: the first one of that name on the PATH.

    NEVER the bare name handed to subprocess. On Windows, Python then looks in System32 before the
    PATH and finds the WSL launcher: the command runs inside a WSL distro, another machine's worth of
    environment, which no test and no parcel of this project may touch. The first two tests of this
    kind did exactly that from 2026-11-23's foundation commit until it was seen that afternoon.
    When the only one to be found is that launcher, the test is skipped, by name, and the gate counts it."""
    path = shutil.which("bash")
    if path is None or "system32" in path.lower().replace("\\", "/").split("/"):
        pytest.skip("no shell on the PATH but the WSL launcher (%r); the runner's own tests need the gate's own" % path)
    return path


# Put together from pieces, so that this file does not carry what it looks for.
THE_NAME = "ba" + "sh"
QUOTED_NAME = re.compile("[\"']" + THE_NAME + "[\"' ]")
THE_ONE_CALL = "shutil.which(\"" + THE_NAME + "\")"
A_SHELL = "shell" + "=True"


def lines_that_start_a_shell(text):
    """The numbers of the lines of a Python source that carry the quoted name anywhere but in the one
    call that looks it up on the PATH, or that ask subprocess for a shell."""
    return [n for n, line in enumerate(text.split("\n"), 1)
            if QUOTED_NAME.search(line.replace(THE_ONE_CALL, "")) or A_SHELL in line]


def test_p0_no_test_or_tool_carries_the_bare_name_or_asks_for_a_shell():
    """The slip above, held, as far as reading source can hold it: no line of a Python file under tests/,
    tools/ or rtl/tb/ carries the quoted name outside the one call, or asks for a shell. A name put
    together at run time, as this file's own is, is not seen."""
    found = []
    for folder in ("tests", "tools", os.path.join("rtl", "tb")):
        for name in sorted(os.listdir(os.path.join(ROOT, folder))):
            if name.endswith(".py"):
                with open(os.path.join(ROOT, folder, name), encoding="utf-8") as f:
                    found += ["%s/%s:%d" % (folder, name, n) for n in lines_that_start_a_shell(f.read())]
    assert found == []


@pytest.mark.parametrize("line", [
    "subprocess.run([NAME, '-c', 'true'])",
    "subprocess.run((NAME, '-c', 'true'))",
    "subprocess.run(NAME + ' -c true', SHELL)",
    "subprocess.Popen(args=[ NAME ])",
    "os.system('echo hello', SHELL)",
    "r = subprocess.run('NAMEBARE -c true'.split())",
])
def test_p0_each_way_of_starting_the_bare_name_is_seen(line):
    """Each form a verifier tried, and the first two the guard missed when it looked for a list alone."""
    text = line.replace("NAMEBARE", "'" + THE_NAME + " x'").replace("NAME", "'" + THE_NAME + "'").replace("SHELL", A_SHELL)
    assert lines_that_start_a_shell("import subprocess\n" + text + "\n") == [2]
    assert lines_that_start_a_shell("path = " + THE_ONE_CALL + "\n") == []



def runner(*args):
    r = subprocess.run([the_gates_own_bash(), "verify/run.sh"] + list(args), cwd=ROOT, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def test_p0_the_first_size_lists_the_rtl_stages_as_not_run_and_the_second_marks_them():
    code, out = runner("--list")
    assert code == 0 and re.search(r"^  rtl-benches ", out, re.M) and re.search(r"^\* model-tests ", out, re.M)
    assert "The rtl stages are NOT in it" in out
    code, out = runner("--with", "rtl", "--list")
    assert code == 0 and re.search(r"^\* rtl-benches ", out, re.M) and re.search(r"^\* ctl-rtl-benches ", out, re.M)


def test_p0_naming_an_rtl_stage_without_its_size_is_refused_and_so_is_an_unknown_size():
    code, out = runner("--only", "rtl-spec")
    assert code == 2 and "add --with rtl" in out
    code, out = runner("--with", "everything")
    assert code == 2 and "unknown size" in out

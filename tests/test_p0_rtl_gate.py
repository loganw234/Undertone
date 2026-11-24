"""The gate's second size, as far as it can be held without Docker.

`bash verify/run.sh --with rtl` runs benches in the simulation image. What decides a verdict there is
plain Python that reads files: tools/check_rtl.py's `judge`, `manifest` and `expected_numbers`, and
tools/sim_image.py's naming of the image. These tests hold that Python on files written here, so the
first size of the gate, which needs no Docker, still sees a judge that passes what it must not.

What they cannot see: anything a simulator or a compiler does. The `rtl-*` stages are that.
"""
import ast
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
               "REG_CAP_SAMPLE_BITS_OFFSET": 56, "REFUSAL_NONE": 0, "REFUSAL_PROFILE_UNKNOWN": 1,
               # round 2, typed from the two RTL designs and the lead's ruling on them: the fabric's three
               # refusals; the core's control block (status at 0x100, its last bit the tenth; the window is
               # written and never read; a mask word a filter); three blocks, the last ending with the frame
               "REFUSAL_CORE_STOPPED": 41, "REFUSAL_REGISTER_ACCESS": 42, "REFUSAL_INJECT_PENDING": 43,
               "REG_STATUS_OFFSET": 256, "REG_STATUS_RUNNING_BIT": 0, "REG_STATUS_REFUSED_AGAIN_BIT": 9,
               "REG_SRC_STATUS_RUNNING_BIT": 0, "REG_COMMIT_AT_WORDS": 2, "REG_SHADOW_DATA_READABLE": 0,
               "REG_SHADOW_DATA_WRITABLE": 1, "REG_SHAPE_MASKS_OFFSET": 168, "REG_SHAPE_MASKS_WORDS": 16,
               "REG_REFUSAL_WRITABLE": 1, "REG_SRC_SEED_OFFSET": 3840, "REG_INJ_FRAME_OFFSET": 3968,
               "BLOCK_CORE_FIRST": 16, "BLOCK_CORE_END": 3584, "BLOCK_SOURCE_END": 3968, "BLOCK_INJECT_END": 4096,
               "MAX_NOISE_TABLE": 32767, "MAX_INJECT_PENDING": 1024,
               # round 3, typed from parcel KRNL's design: the kernel's block at 0xE00, its first row, its
               # status bits, its last refusal, and the memory's slot
               "BLOCK_KERNEL_FIRST": 3584, "BLOCK_KERNEL_END": 3840, "REG_KRN_BUFFER_OFFSET": 3584,
               "REG_KRN_BUFFER_WORDS": 2, "REG_KRN_STATUS_DONE_BIT": 1, "REG_KRN_START_READABLE": 0,
               "REFUSAL_KERNEL_BUSY": 44, "REFUSAL_RUN_LENGTH": 50, "MEMORY_SLOT_BYTES": 32,
               # the pulse, read off spec/pulses/e0.toml by eye: its second sample, its largest magnitude
               # (the fifth of the fourth row of eight), its largest positive, and its last two
               "PULSE_SAMPLE_BITS": 16, "PULSE_E0_LENGTH": 64, "PULSE_E0_SAMPLE_0": 0, "PULSE_E0_SAMPLE_1": 1,
               "PULSE_E0_SAMPLE_28": -970, "PULSE_E0_SAMPLE_36": 950, "PULSE_E0_SAMPLE_62": -2,
               "PULSE_E0_SAMPLE_63": 0}
    for name, value in by_hand.items():
        assert sv[name] == value, name
    assert "PULSE_E0_SAMPLE_64" not in sv and len([n for n in sv if n.startswith("PULSE_E0_SAMPLE_")]) == 64


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


IDENTICAL = {"mark": "BIT-IDENTITY", "test": "identity", "verdict": "IDENTICAL", "records": 40, "model_digest": "aa",
             "rtl_digest": "aa"}
MISMATCH = {"mark": "BIT-IDENTITY", "test": "identity", "verdict": "MISMATCH", "kind": "WORD", "at": 0}


def good(tmp_path):
    out = str(tmp_path)
    results(os.path.join(out, "b.s16x1.xml"), identity="pass", other="pass")
    evidence(os.path.join(out, "b.s16x1.evidence.jsonl"), IDENTICAL, dict(IDENTICAL, records=2))
    results(os.path.join(out, "b.s16x1.mutant.m.xml"), identity="fail", other="pass")
    evidence(os.path.join(out, "b.s16x1.mutant.m.evidence.jsonl"), MISMATCH)
    for run in ("b.s16x1", "b.s16x1.mutant.m"):         # a build that printed nothing
        open(os.path.join(out, run + ".log.build"), "w", encoding="utf-8").close()
    return out


def wheres(findings):
    return sorted("%s | %s" % (where, what.split(":")[0]) for where, what in findings)


def test_p0_the_judge_passes_a_run_that_is_good_and_counts_what_it_read(tmp_path):
    findings, passed, records, nruns, nmutants, skips, logs, listed = check_rtl.judge([BENCH], good(tmp_path))
    assert (findings, passed, records, nruns, nmutants, skips, logs, listed) == ([], 2, 42, 1, 1, [], 2, 0)


# ---- round 3's P0-3: a run's limit, and what a build prints ----

SORRY = "sorry: constant selects in always_* processes are not currently supported (all bits will be included)."
LISTED = frozenset({("rtl/x/x.sv", 7, SORRY)})


def build_log(out, run, *lines):
    with open(os.path.join(out, run + ".log.build"), "w", encoding="utf-8") as f:
        f.write("".join(line + "\n" for line in lines))


def test_p0_a_run_the_runner_stopped_at_its_limit_is_reported_by_name_whatever_it_left(tmp_path):
    """The runner's account can add a finding and never take one away: a run it says it stopped is a
    finding, RUN-TIMEOUT, even beside a results file that says every test passed."""
    out = good(tmp_path)
    with open(os.path.join(out, "runs.json"), "w", encoding="utf-8") as f:
        json.dump([{"run": "b.s16x1", "what": "bench", "error": "RUN-TIMEOUT: the run was still going at its limit "
                                                                 "of 20 s and was stopped"}], f)
    assert wheres(check_rtl.judge([BENCH], out)[0]) == ["b.s16x1 | RUN-TIMEOUT"]
    os.remove(os.path.join(out, "b.s16x1.xml"))
    assert wheres(check_rtl.judge([BENCH], out)[0]) == ["b.s16x1 | RUN-TIMEOUT"]


def test_p0_a_run_that_left_results_and_no_build_log_is_a_finding(tmp_path):
    out = good(tmp_path)
    os.remove(os.path.join(out, "b.s16x1.mutant.m.log.build"))
    assert wheres(check_rtl.judge([BENCH], out)[0]) == ["b.s16x1.mutant.m | BUILD-LOG-MISSING"]


def test_p0_a_listed_build_line_passes_in_the_tree_and_in_a_mutants_copy_and_is_counted(tmp_path):
    out = good(tmp_path)
    build_log(out, "b.s16x1", "/work/rtl/x/x.sv:7: " + SORRY, "")
    build_log(out, "b.s16x1.mutant.m", "/tmp/src/b.s16x1.mutant.m/rtl/x/x.sv:7: " + SORRY, "/work/rtl/x/x.sv:7: " + SORRY)
    findings, *_rest, logs, listed = check_rtl.judge([BENCH], out, LISTED)
    assert (findings, logs, listed) == ([], 2, 3)


@pytest.mark.parametrize("line, where", [
    ("/work/rtl/x/x.sv:8: " + SORRY, "b.s16x1 rtl/x/x.sv:8"),                      # the words, at another line
    ("/work/rtl/x/y.sv:7: " + SORRY, "b.s16x1 rtl/x/y.sv:7"),                      # in another file
    ("/work/rtl/x/x.sv:7: warning: " + SORRY, "b.s16x1 rtl/x/x.sv:7"),             # other words at the place
    ("/work/rtl/x/x.sv:7: " + SORRY[:-1], "b.s16x1 rtl/x/x.sv:7"),                 # the words cut short
    ("/tmp/src/b.s16x1.mutant.other/rtl/x/x.sv:7: " + SORRY, "b.s16x1 build-log:1"),   # another run's copy
    ("/tmp/build/b.s16x1/x.sv:7: " + SORRY, "b.s16x1 build-log:1"),                # not a file of the tree
    ("a line with no file and no number", "b.s16x1 build-log:1"),
    ("rtl/x/x.sv:7: " + SORRY, "b.s16x1 build-log:1"),                             # not as the mounted tree says it
])
def test_p0_a_build_line_the_list_does_not_name_is_a_finding_at_its_run_and_place(tmp_path, line, where):
    out = good(tmp_path)
    build_log(out, "b.s16x1", line)
    assert wheres(check_rtl.judge([BENCH], out, LISTED)[0]) == ["%s | BUILD-LINE" % where]
    build_log(out, "b.s16x1")
    build_log(out, "b.s16x1.mutant.m", line.replace("b.s16x1", "b.s16x1.mutant.m", 1) if "/tmp/src/" not in line else line)
    assert [w.split(" | ")[1] for w in wheres(check_rtl.judge([BENCH], out, LISTED)[0])] == ["BUILD-LINE"]


def test_p0_the_committed_build_list_is_read_whole_and_names_the_two_lines_of_round_2(tmp_path):
    listed = check_rtl.build_list(ROOT)
    assert listed == {("rtl/source/source.sv", 187, SORRY), ("rtl/inject/inject.sv", 276, SORRY)}
    for path, line, _says in listed:
        with open(os.path.join(ROOT, path), encoding="utf-8") as f:
            assert f.read().split("\n")[line - 1].strip() == "always_comb begin", (path, line)


ENTRY = '[[line]]\nfile = "rtl/x/x.sv"\nline = 2\nsays = "words"\nwhy = "a reason"\n'


@pytest.mark.parametrize("text", [
    ENTRY.replace('why = "a reason"\n', ""),                       # no reason
    ENTRY.replace('why = "a reason"', 'why = "  "'),                # an empty one
    ENTRY.replace('says = "words"', 'says = ""'),
    ENTRY.replace("rtl/x/x.sv", "rtl/x/not-there.sv"),
    ENTRY.replace("rtl/x/x.sv", "../x.sv"),
    ENTRY.replace("line = 2", "line = 4"),                          # past the file's last line
    ENTRY.replace("line = 2", "line = 3"),                          # just past it, after the last line end (VP0R3)
    ENTRY.replace("line = 2", "line = 0"),
    ENTRY.replace("line = 2", 'line = "2"'),
    ENTRY + "extra = 1\n",
    ENTRY + "\n" + ENTRY,                                            # the same entry twice
    "something = 1\n" + ENTRY,
    "[[line\n",
])
def test_p0_a_build_list_that_cannot_be_read_exactly_is_refused_by_name(tmp_path, text):
    os.makedirs(tmp_path / "rtl" / "x")
    (tmp_path / "rtl" / "x" / "x.sv").write_text("module x;\nendmodule\n", encoding="utf-8")
    (tmp_path / "rtl" / "tb").mkdir()
    (tmp_path / "rtl" / "tb" / "build_lines.toml").write_text(ENTRY, encoding="utf-8")
    assert check_rtl.build_list(str(tmp_path)) == {("rtl/x/x.sv", 2, "words")}
    (tmp_path / "rtl" / "tb" / "build_lines.toml").write_text(text, encoding="utf-8")
    with pytest.raises(Refusal) as e:
        check_rtl.build_list(str(tmp_path))
    assert str(e.value).startswith("BUILD-LIST-MALFORMED")


@pytest.mark.parametrize("body, last", [
    (b"module x;\nendmodule\n", 2), (b"module x;\nendmodule", 2), (b"module x;\nendmodule\x0c\n", 2),
    (b"module x;\x0c\nendmodule\n", 2), (b"one\x1cstill one\n", 1),
])
def test_p0_a_build_list_line_is_a_line_by_line_feeds_alone(tmp_path, body, last):
    """VP0R3-2 found a form feed taken as a line end. The last line by line feeds is accepted; one past it is not."""
    os.makedirs(tmp_path / "rtl" / "x")
    (tmp_path / "rtl" / "x" / "x.sv").write_bytes(body)
    (tmp_path / "rtl" / "tb").mkdir()
    for line, ok in ((last, True), (last + 1, False)):
        (tmp_path / "rtl" / "tb" / "build_lines.toml").write_text(ENTRY.replace("line = 2", "line = %d" % line),
                                                                    encoding="utf-8")
        if ok:
            assert check_rtl.build_list(str(tmp_path)) == {("rtl/x/x.sv", line, "words")}
        else:
            with pytest.raises(Refusal):
                check_rtl.build_list(str(tmp_path))


def test_p0_a_build_list_entry_naming_a_file_that_is_not_text_is_refused_by_name(tmp_path):
    """VP0R3 found Python's own UnicodeDecodeError here, where the list's refusal belongs."""
    os.makedirs(tmp_path / "rtl" / "x")
    (tmp_path / "rtl" / "x" / "x.sv").write_bytes(b"module x;\n\xff\xfe\nendmodule\n")
    (tmp_path / "rtl" / "tb").mkdir()
    (tmp_path / "rtl" / "tb" / "build_lines.toml").write_text(ENTRY, encoding="utf-8")
    with pytest.raises(Refusal) as e:
        check_rtl.build_list(str(tmp_path))
    assert str(e.value).startswith("BUILD-LIST-MALFORMED")


def test_p0_a_tree_with_no_build_list_is_refused_by_name(tmp_path):
    with pytest.raises(Refusal) as e:
        check_rtl.build_list(str(tmp_path))
    assert str(e.value).startswith("BUILD-LIST-MALFORMED")


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


@pytest.mark.parametrize("line", [
    "this is not what the harness writes",
    "5", "[1]", "null", '"a string"',                      # JSON, and not an object
    '{"foo": 1}',                                           # an object the harness never writes
    '{"test": "identity", "verdict": "IDENTICAL", "records": 40, "model_digest": "aa", "rtl_digest": "aa"}',   # no mark
    '{"mark": "SOMETHING-ELSE", "test": "identity", "verdict": "IDENTICAL", "records": 40}',
])
def test_p0_an_evidence_line_that_is_not_the_harnesss_is_a_finding_of_its_run(tmp_path, line):
    """Beside good lines, in a bench's own run and in a mutant's. A verifier found that a line of JSON
    that is not an object stopped the judge with an error of Python's own, and that an object the harness
    never writes was passed over."""
    out = good(tmp_path)
    with open(os.path.join(out, "b.s16x1.evidence.jsonl"), "a", encoding="utf-8") as f:
        f.write(line + "\n")
    assert wheres(check_rtl.judge([BENCH], out)[0]) == ["b.s16x1 | EVIDENCE-UNREADABLE"]
    (tmp_path / "mutant").mkdir()
    out = good(tmp_path / "mutant")
    with open(os.path.join(out, "b.s16x1.mutant.m.evidence.jsonl"), "a", encoding="utf-8") as f:
        f.write(line + "\n")
    assert wheres(check_rtl.judge([BENCH], out)[0]) == ["b.s16x1.mutant.m | EVIDENCE-UNREADABLE"]


def test_p0_the_judge_names_a_skipped_test_and_does_not_count_it_as_passed(tmp_path):
    out = good(tmp_path)
    results(os.path.join(out, "b.s16x1.xml"), identity="pass", other="skip")
    findings, passed, _records, _nruns, _nmutants, skips, _logs, _listed = check_rtl.judge([BENCH], out)
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


def foundations_rows(text):
    """A manifest's text up to its second bench: the heading, the foundation's own bench and its mutants.

    A parcel appends its benches after the foundation's. The cases below change one text of the
    foundation's rows, in a copy that holds the foundation's files and no parcel's: with a parcel's rows
    left in, a text they repeat (an empty kind, a line of two profiles) failed the cases' own count, and
    their sources, which the copy does not hold, would have been a second reason for every refusal.
    Parcel RTL-B met the first on 2026-11-23, with its first row."""
    starts = [m.start() for m in re.finditer(r"^\[\[bench\]\][ \t]*$", text, re.M)]
    assert starts, "the manifest has no bench"
    return text if len(starts) == 1 else text[:starts[1]]


def manifest_tree(tmp_path, old, new):
    root = str(tmp_path)
    for rel in ("spec/constants.py", "spec/undertone_pkg.sv", "rtl/p0/onetap.sv", "rtl/tb/bench_p0_onetap.py",
                "rtl/tb/benches.toml"):
        os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
        shutil.copyfile(os.path.join(ROOT, rel), os.path.join(root, rel))
    path = os.path.join(root, "rtl", "tb", "benches.toml")
    with open(path, encoding="utf-8") as f:
        text = foundations_rows(f.read())
    assert text.count(old) == 1, old
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text.replace(old, new))
    return root


def test_p0_the_foundations_own_rows_are_cut_from_a_manifest_that_parcels_have_added_to(tmp_path):
    """The cut is at the second bench and nowhere else, and what is left is a manifest the check accepts:
    so each case below is refused for the one text it changes."""
    head = "# a heading\n\n[[bench]]\nname = \"a\"\nkind = \"\"\n\n[[bench.mutant]]\nname = \"m\"\nkind = \"\"\n"
    more = "\n[[bench]]\nname = \"b\"\nkind = \"\"\n\n[[bench.mutant]]\nname = \"n\"\n\n[[bench]]\nname = \"c\"\n"
    assert foundations_rows(head) == head and foundations_rows(head + more) == head + "\n"
    assert foundations_rows(head + more).count('kind = ""') == 2 and (head + more).count('kind = ""') == 3
    with pytest.raises(AssertionError):
        foundations_rows("# no bench at all\n")
    benches = check_rtl.manifest(manifest_tree(tmp_path, 'name = "p0-onetap"', 'name = "p0-onetap"'))
    assert [b["name"] for b in benches] == ["p0-onetap"] and len(benches[0]["mutant"]) == 7


@pytest.mark.parametrize("old, new", [
    ('profiles = ["s16x1", "s24x3"]', 'profiles = ["s16x1", "s99x9"]'),
    ('profiles = ["s16x1", "s24x3"]', 'profiles = ["s16x1", "s16x1"]'),
    ('identity = ["bit_identity_random", "bit_identity_extremes"]', 'identity = ["bit_identity_random", "no_such_test"]'),
    ('identity = ["bit_identity_random", "bit_identity_extremes"]', 'identity = []'),
    ('identity = ["bit_identity_random", "bit_identity_extremes"]', 'identity = ["bit_identity_random", 5]'),
    ('identity = ["bit_identity_random", "bit_identity_extremes"]', 'identity = "bit_identity_random"'),
    ('must_fail = ["latency_is_one_clock"]', 'must_fail = ["no_such_test"]'),
    ('must_fail = ["latency_is_one_clock"]', 'must_fail = []'),
    ('kind = ""', 'kind = "SOMETHING"'),
    ('sources = ["spec/undertone_pkg.sv", "rtl/p0/onetap.sv"]', 'sources = ["spec/undertone_pkg.sv", "../outside.sv"]'),
    ('name = "p0-onetap"', 'name = "P0 Onetap"'),
    ('module = "bench_p0_onetap"', 'module = "bench_that_is_not_there"'),
    ('name = "stops-after-four"', 'name = "coefficient-bit"'),
    ('toplevel = "onetap"', 'toplevel = "onetap"\nextra = 1'),
    ('toplevel = "onetap"', 'toplevel = "onetap"\nlimit = 0'),
    ('toplevel = "onetap"', 'toplevel = "onetap"\nlimit = 3001'),
    ('toplevel = "onetap"', 'toplevel = "onetap"\nlimit = "20"'),
    ('toplevel = "onetap"', 'toplevel = "onetap"\nlimit = 20.5'),
])
def test_p0_a_manifest_that_cannot_be_read_exactly_is_refused(tmp_path, old, new):
    with pytest.raises(Refusal) as e:
        check_rtl.manifest(manifest_tree(tmp_path, old, new))
    assert str(e.value).startswith("MANIFEST-MALFORMED")


@pytest.mark.parametrize("limit", [1, 20, 3000])
def test_p0_a_benchs_limit_is_whole_seconds_inside_the_stages_own(tmp_path, limit):
    root = manifest_tree(tmp_path, 'toplevel = "onetap"', 'toplevel = "onetap"\nlimit = %d' % limit)
    assert check_rtl.manifest(root)[0]["limit"] == limit


def test_p0_the_runner_and_the_judge_list_the_same_runs_in_the_same_order():
    """The runner (inside the image) and the judge (outside it) each work out the runs from the manifest;
    the runner's list is what it starts, the judge's what it requires. They share no code."""
    sys.path.insert(0, os.path.join(ROOT, "rtl", "tb"))
    try:
        import run_benches
    finally:
        sys.path.remove(os.path.join(ROOT, "rtl", "tb"))
    benches = check_rtl.manifest(ROOT)
    assert [r[0] for r in run_benches.plan(run_benches.load_manifest(ROOT))] == [r[0] for r in check_rtl.runs_of(benches)]


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
    assert all(re.match(r"[0-9][0-9A-Za-z.]*\Z", v) for v in pins["pip"].values()) and len(pins["pip"]) == 10
    # round 3's P0-3: the AXI bus models and what came with them
    assert (pins["pip"]["cocotbext-axi"], pins["pip"]["cocotb-bus"], pins["pip"]["scapy"]) == ("0.1.28", "0.3.0", "2.8.0")
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
# The name as a word of its own, in any case: not inside a longer word. With .exe it is a word too: what
# follows it then is a dot, which is no part of a word. (A group for ".exe" stood here and did nothing.)
THE_WORD = re.compile(r"(?<![A-Za-z0-9_])" + THE_NAME + r"(?![A-Za-z0-9_])", re.I)
SKIPPED_FOLDERS = (".git", "Data", "__pycache__", ".pytest_cache", "state")


def shell_starts(source):
    """Where a Python source names that shell, or writes out a request for a shell: [(line, what)].

    The source is parsed, not matched line by line. Reported: a string or bytes literal that holds the
    name as a word, in any case, with or without .exe, bare or at the end of a path or anywhere in a
    command; a keyword argument `shell` given anything but the constant False; and a dict literal with
    the key "shell". NOT reported: a docstring; a comment; and the argument of the one call that looks
    the name up on the PATH.

    It does not find every way of starting a shell, and was never needed to: the slip was that one name.
    NOT reported either, each tried by a verifier: a `shell` key that is not written in a dict literal
    (`kw['shell'] = True`, `kw.setdefault('shell', True)`, `dict([('shell', True)])`, a dict
    comprehension, a key that is a name, as in `**{K: True}`); `shell` passed by position, which
    `subprocess.Popen` takes as its ninth argument; and a function that starts the platform's own
    shell with no keyword at all (`os.system`, `os.popen`, `subprocess.getoutput`,
    `subprocess.getstatusoutput`) when its string does not hold the name. On Windows that shell is
    cmd.exe, not the WSL launcher. This is a list of what has been tried, not of what there is.
    """
    tree = ast.parse(source)
    spared = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                spared.add(id(first.value))                                   # a docstring
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "which" \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "shutil" and len(node.args) == 1 \
                and isinstance(node.args[0], ast.Constant) and node.args[0].value == THE_NAME:
            spared.add(id(node.args[0]))                                      # the one call
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and id(node) not in spared:
            text = node.value.decode("latin-1") if isinstance(node.value, bytes) else node.value
            if isinstance(text, str) and THE_WORD.search(text):
                found.add((node.lineno, "the name, in a literal"))
        if isinstance(node, ast.keyword) and node.arg == "shell" \
                and not (isinstance(node.value, ast.Constant) and node.value.value is False):
            found.add((node.value.lineno, "a shell asked for"))
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and key.value == "shell":
                    found.add((key.lineno, "a shell asked for, by a dict"))
    return sorted(found)


def shell_starts_under(root):
    """Every Python file of a tree, in every folder but the ones no commit holds (SKIPPED_FOLDERS), through
    `shell_starts`: a list of "<path from the root>:<line>: <what>". A file Python cannot parse is listed too.

    A folder with one of those names is skipped wherever it is, not only at the two places `.gitignore`
    names (`Data/` and `verify/state/`): a committed Python file under some other folder called `state`
    or `Data` would not be read, and nothing checks that there is none. And it reads what is on the
    disk, not what is committed: an untracked folder of Python, a virtual environment say, is read too."""
    found = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIPPED_FOLDERS)
        for name in sorted(files):
            if name.endswith(".py"):
                where = os.path.relpath(os.path.join(folder, name), root).replace("\\", "/")
                with open(os.path.join(folder, name), encoding="utf-8") as f:
                    try:
                        found += ["%s:%d: %s" % (where, line, what) for line, what in shell_starts(f.read())]
                    except SyntaxError as e:
                        found.append("%s:%s: cannot be parsed" % (where, e.lineno))
    return found


def test_p0_no_python_file_of_the_tree_names_that_shell_or_writes_out_a_request_for_one():
    """The slip above, held, as far as reading source can hold it. What it cannot see: a name put together
    at run time, as this file's own is; a name that reaches Python from outside the file (an environment
    variable, a configuration file, a command line); a docstring handed to something as data; a program
    started by another name that starts that shell itself; a shell asked for in a way `shell_starts` says
    it does not report; and anything that is not a Python file.

    "A docstring handed to something as data" is not empty in this tree: the fifth verifier found two
    docstrings that say the name and are printed as messages, the description `tools/check_rtl.py` gives
    its argument parser and the usage `docs/studies/d2/fetch.py` exits with. Neither starts anything.
    So "no string of this tree says the name" is true only of strings that are not docstrings."""
    assert shell_starts_under(ROOT) == []


# Each is a Python statement. {n} is the name, {u} the name in upper case; the braces of a dict are doubled.
STARTS = [
    ("a list", "subprocess.run(['{n}', '-c', 'true'])"),
    ("a tuple", "subprocess.run(('{n}', '-c', 'true'))"),
    ("a command string", "subprocess.run('{n} -c true'.split())"),
    ("with .exe", "subprocess.run(['{n}.exe', '-c', 'true'])"),
    ("in upper case", "subprocess.run(['{u}.EXE', '-c', 'true'])"),
    ("at the end of a path", "subprocess.run(['C:/Windows/System32/{n}.exe', '-c', 'true'])"),
    ("at the end of a path with backslashes", "subprocess.run([r'C:\\Windows\\System32\\{n}.exe'])"),
    ("before a tab", "subprocess.run('{n}\\t-c true')"),
    ("after other words of a command", "os.system('cd x && {n} run.sh')"),
    ("after a pipe", "os.popen('echo | {n}')"),
    ("after env", "subprocess.run('env {n} -c true'.split())"),
    ("as bytes", "subprocess.run([b'{n}', b'-c', b'true'])"),
    ("in an f-string", "subprocess.run(f'{n} {{x}}')"),
    ("a shell asked for", "subprocess.run('echo', shell=True)"),
    ("a shell asked for, with spaces", "subprocess.run('echo', shell = True)"),
    ("a shell asked for, as a number", "subprocess.run('echo', shell=1)"),
    ("a shell asked for, in brackets", "subprocess.run('echo', shell=(True))"),
    ("a shell asked for, on the next line", "subprocess.run('echo',\n               shell=True)"),
    ("a shell asked for, by a name", "subprocess.run('echo', shell=wanted)"),
    ("a shell asked for, by a dict", "subprocess.run('echo', **{{'shell': True}})"),
]


@pytest.mark.parametrize("what, statement", STARTS, ids=[s[0] for s in STARTS])
def test_p0_each_form_the_guard_is_said_to_report_is_reported(what, statement):
    """Every form four verifiers tried or named. The first guard looked for a list on one line and missed
    a tuple and a command string; the second did not look for a shell asked of subprocess, nor the name
    with .exe; the third missed the name after other words of a command, a shell asked for in any way but
    one, and had a case for upper letters that did not hold them."""
    source = "import os\nimport subprocess\nx = wanted = 1\n" + statement.format(n=THE_NAME, u=THE_NAME.upper()) + "\n"
    assert THE_NAME in source.lower() or "shell" in source
    assert [line for line, _what in shell_starts(source)] in ([4], [5]), shell_starts(source)


def test_p0_the_form_in_upper_case_really_is_in_upper_case():
    """The case the third guard's test could not fail on: its line was rewritten in lower case before it
    was read. Here the statement is looked at before the guard is."""
    statement = dict(STARTS)["in upper case"].format(n=THE_NAME, u=THE_NAME.upper())
    assert THE_NAME.upper() + ".EXE" in statement and THE_NAME not in statement
    assert shell_starts(statement + "\n") == [(1, "the name, in a literal")]


SPARED = [
    ("the one call", "path = shutil.which('{n}')"),
    ("a docstring", "def f():\n    \"\"\"Run under {n}, the first on the PATH.\"\"\"\n    return 1"),
    ("a comment", "x = 1  # not {n}"),
    ("a longer word", "x = '{n}ful'"),
    ("a word that ends in it", "x = 'un{n}'"),
    ("a word with it in the middle", "x = 'a_{n}_b'"),
    ("a shell refused", "subprocess.run(['echo'], shell=False)"),
    ("an identifier", "the_gates_own_{n} = 1"),
]


@pytest.mark.parametrize("what, statement", SPARED, ids=[s[0] for s in SPARED])
def test_p0_what_cannot_start_that_shell_is_not_reported(what, statement):
    assert shell_starts("import shutil\nimport subprocess\n" + statement.format(n=THE_NAME) + "\n") == []


def test_p0_only_the_one_call_spares_its_argument():
    """`shutil.which` and nothing else: another object's `which`, or the name handed to it by keyword or
    with a second argument, is the name in a literal like any other."""
    for call in ("other.which('%s')", "which('%s')", "shutil.which(cmd='%s')", "shutil.which('%s', mode)",
                 "shutil.where('%s')", "shutil.which('%s.exe')"):
        source = "import shutil\nother = mode = 1\npath = " + call % THE_NAME + "\n"
        assert shell_starts(source) == [(3, "the name, in a literal")], call


def test_p0_a_modules_docstring_is_spared_and_a_string_that_only_looks_like_one_is_not():
    assert shell_starts("\"\"\"How %s is found.\"\"\"\nx = 1\n" % THE_NAME) == []
    assert shell_starts("x = 1\n\"\"\"How %s is found.\"\"\"\n" % THE_NAME) == [(2, "the name, in a literal")]
    # The first string of a block that is not a module, a class or a function is no docstring. The fifth
    # verifier spared it in a copy and no test failed.
    assert shell_starts("x = 1\nif x:\n    \"\"\"How %s is found.\"\"\"\n" % THE_NAME) == [(3, "the name, in a literal")]


def test_p0_a_sentence_about_the_name_in_a_string_is_reported_and_that_is_meant():
    """A message that says the word is taken for the word: the guard cannot tell a sentence from a command,
    so no string of this tree may say it. That is why this file's own messages do not."""
    assert shell_starts("print('the first %s on the PATH')\n" % THE_NAME) == [(1, "the name, in a literal")]


def test_p0_the_guard_reads_every_folder_of_a_tree_but_the_ones_no_commit_holds(tmp_path):
    line = "import subprocess\nsubprocess.run(['%s', '-c', 'true'])\n" % THE_NAME
    for rel in ("conftest.py", "tests/a.py", "tools/deep/er/b.py", "rtl/tb/c.py", "model/d.py", "docs/studies/d9/e.py",
                "Data/runs/f.py", "verify/state/run/g.py", "tools/h.txt"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(line, encoding="utf-8")
    (tmp_path / "tools" / "broken.py").write_text("def (:\n", encoding="utf-8")
    assert shell_starts_under(str(tmp_path)) == [
        "conftest.py:2: the name, in a literal", "docs/studies/d9/e.py:2: the name, in a literal",
        "model/d.py:2: the name, in a literal", "rtl/tb/c.py:2: the name, in a literal",
        "tests/a.py:2: the name, in a literal", "tools/broken.py:1: cannot be parsed",
        "tools/deep/er/b.py:2: the name, in a literal"]


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
    code, out = runner("--list", "--only", "rtl-spec")           # the list refuses what the run would refuse
    assert code == 2 and "add --with rtl" in out
    for args in (("--list", "--only", "nosuch"), ("--list", "--skip", "nosuch"), ("--with", "rtl", "--list", "--only", "nosuch")):
        code, out = runner(*args)
        assert code == 2 and "unknown stage 'nosuch'" in out, args
    code, out = runner("--only", "nosuch")
    assert code == 2 and "unknown stage 'nosuch'" in out


def test_p0_the_list_shows_a_skipped_stage_as_one_that_would_not_run():
    code, out = runner("--with", "rtl", "--skip", "rtl-spec,links", "--list")
    assert code == 0 and re.search(r"^- rtl-spec ", out, re.M) and re.search(r"^- links ", out, re.M)
    assert re.search(r"^\* rtl-benches ", out, re.M) and "would NOT run" in out
    code, out = runner("--with", "everything")
    assert code == 2 and "unknown size" in out

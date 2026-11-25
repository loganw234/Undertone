"""The build's manifest tool, hw/manifest.py, as far as it can be held without an image or a tool.

The manifest's readers are plain Python over the text the tools print. These tests hold them on excerpts:
`xclbinutil --info`'s "Scalable Clocks" as it printed on 2026-11-25 for round 3's third link, the card day's
image, and for the sweep's link asked at 150 MHz, each whole down to "System Clocks" and cut there; and a routed
timing summary's two tables in the form Vivado 2022.2 prints them, written here from the
sibling project's reader of the same reports. And the check: an image and a manifest that agree are accepted, and
a manifest with its hash or its clock changed is refused by name.

What they cannot see: a real routed timing summary or utilisation report of this project's own (none exists before
the first build; the build's own record says what the readers made of them), and `xclbinutil` itself, which the
check runs on the machine that has it. The check's control, on a real image, is `hw/manifest.py control`, run where
the image is; the round's ledger records each run.
"""
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "hw"))
import manifest  # noqa: E402

# The third link's image, built at 100 MHz: its kernel runs at 100, and KERNEL_CLK, another clock, is 500.
INFO = """Scalable Clocks
---------------
   Name:      hbm_aclk
   Index:     0
   Type:      SYSTEM
   Frequency: 450 MHz

   Name:      KERNEL_CLK
   Index:     1
   Type:      KERNEL
   Frequency: 500 MHz

   Name:      DATA_CLK
   Index:     2
   Type:      DATA
   Frequency: 100 MHz

System Clocks
"""

# The sweep's link asked at 150 MHz, which v++ lowered: "Requested Freq: 150 MHz", "Achieved Freq: 127.4 MHz".
INFO_F150 = """Scalable Clocks
---------------
   Name:      hbm_aclk
   Index:     0
   Type:      SYSTEM
   Frequency: 433 MHz

   Name:      KERNEL_CLK
   Index:     1
   Type:      KERNEL
   Frequency: 500 MHz

   Name:      DATA_CLK
   Index:     2
   Type:      DATA
   Frequency: 127 MHz

System Clocks
"""

# The reader as it was until 2026-11-25: the scalable clock named KERNEL_CLK.
KERNEL_CLK_READER = r"Name:\s+KERNEL_CLK\s*\n\s*Index:\s+\d+\s*\n\s*Type:\s+KERNEL\s*\n\s*Frequency:\s+(\d+)\s+MHz"

TIMING = """------------------------------------------------------------------------------------------------
| Design Timing Summary
| ---------------------
------------------------------------------------------------------------------------------------

    WNS(ns)      TNS(ns)  TNS Failing Endpoints  TNS Total Endpoints      WHS(ns)
    -------      -------  ---------------------  -------------------      -------
      0.123        0.000                      0               512000        0.010


------------------------------------------------------------------------------------------------
| Intra Clock Table
| -----------------
------------------------------------------------------------------------------------------------

Clock                       WNS(ns)      TNS(ns)  TNS Failing Endpoints  TNS Total Endpoints
-----                       -------      -------  ---------------------  -------------------
clk_kernel_00_unbuffered_net   1.234        0.000                      0               300000
hbm_aclk                      -0.002       -0.004                      2                 9000


------------------------------------------------------------------------------------------------
| Inter Clock Table
| -----------------
------------------------------------------------------------------------------------------------
clk_a  clk_b  -1.000  -1.000  1  1
"""


def the_kernel_clock_is_read():
    assert manifest.kernel_clock_mhz(INFO) == 100                  # the card day's image
    assert manifest.kernel_clock_mhz(INFO_F150) == 127             # an image whose clock v++ lowered
    assert manifest.kernel_clock_mhz(INFO.replace("Frequency: 100 MHz\n\nSystem", "Frequency: 135 MHz\n\nSystem")) == 135
    assert manifest.kernel_clock_mhz(INFO.replace("DATA_CLK", "OTHER_CLK")) is None
    assert manifest.kernel_clock_mhz(INFO + INFO) is None          # two answers is no answer


def test_build_manifest_reads_the_kernel_clock_an_image_carries():
    the_kernel_clock_is_read()


def test_build_manifest_control__the_reader_of_KERNEL_CLK_is_caught(monkeypatch):
    """The defect of 2026-11-24, planted: a reader of the scalable clock named KERNEL_CLK. The test above must fail on
    it, and it reads 500 from both images, as it wrote into the third link's manifest."""
    monkeypatch.setattr(manifest, "SCALABLE", re.compile(KERNEL_CLK_READER))
    with pytest.raises(AssertionError):
        the_kernel_clock_is_read()
    assert manifest.kernel_clock_mhz(INFO) == 500
    assert manifest.kernel_clock_mhz(INFO_F150) == 500


def test_build_manifest_reads_the_designs_slack_and_every_clocks_row_and_no_other_table():
    assert manifest.design_wns(TIMING) == "0.123"
    rows = manifest.intra_clock_rows(TIMING)
    assert rows == ["clk_kernel_00_unbuffered_net 1.234 0.000 0 300000", "hbm_aclk -0.002 -0.004 2 9000"]
    assert manifest.design_wns("no table here") is None


def test_build_manifest_names_the_kernel_in_a_utilisation_report():
    text = "| Name | LUT | DSP |\n| undertone_krnl_1 | 12345 | 724 |\n| other | 1 | 0 |\n"
    assert manifest.kernel_util_rows(text, "undertone_krnl") == ["| undertone_krnl_1 | 12345 | 724 |"]


def test_build_manifest_check_accepts_agreement_and_refuses_a_changed_hash_or_clock_by_name(tmp_path):
    image = tmp_path / "undertone_hw.xclbin"
    image.write_bytes(b"not an image, but bytes with a hash")
    good = tmp_path / "good.txt"
    good.write_text("sha256: %s\nkernel_clock_mhz: 100\n" % manifest.sha256_file(str(image)), encoding="utf-8")
    assert manifest.check(str(image), str(good), info=INFO) is None
    bad_hash = tmp_path / "hash.txt"
    bad_hash.write_text("sha256: %s\nkernel_clock_mhz: 100\n" % ("0" * 64), encoding="utf-8")
    assert manifest.check(str(image), str(bad_hash), info=INFO).startswith("MANIFEST-HASH:")
    bad_clock = tmp_path / "clock.txt"
    bad_clock.write_text("sha256: %s\nkernel_clock_mhz: 101\n" % manifest.sha256_file(str(image)), encoding="utf-8")
    assert manifest.check(str(image), str(bad_clock), info=INFO).startswith("MANIFEST-CLOCK:")
    assert manifest.check(str(image), str(good), info="no clock here").startswith("MANIFEST-CLOCK:")


def test_build_manifest_tree_hash_moves_with_one_byte_of_rtl_hw_or_spec(tmp_path):
    for top in ("rtl", "hw", "spec"):
        (tmp_path / top).mkdir()
        (tmp_path / top / "a.txt").write_text("x\n", encoding="utf-8")
    first = manifest.tree_hash(str(tmp_path))
    assert first == manifest.tree_hash(str(tmp_path))
    for top in ("rtl", "hw", "spec"):
        (tmp_path / top / "a.txt").write_text("y\n", encoding="utf-8")
        assert manifest.tree_hash(str(tmp_path)) != first
        (tmp_path / top / "a.txt").write_text("x\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "b.txt").write_text("z\n", encoding="utf-8")
    assert manifest.tree_hash(str(tmp_path)) == first             # only rtl/, hw/ and spec/

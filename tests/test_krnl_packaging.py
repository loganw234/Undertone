"""The kernel's packaging, held to the definition and to the kernel's top. Parcel KRNL, round 3.

hw/kernel.xml, hw/package_kernel.tcl and hw/link.cfg are written by hand and
read by Vitis, which this project's gate cannot run. What this file holds is
that each number and name in them is the one the definition and the RTL give:

  kernel.xml    the kernel's name is the top module's; the protocol is
                user-managed; the slave s_axi_control spans 2^address_bits
                bytes of word_bits words; the master m_axi_gmem is one slot
                ([memory] slot_bytes) a beat; the one argument is on that
                master, at krn_buffer's offset, a pointer
  the script    every source it names is a file of the tree, the generated
                package first and the kernel's top last; no bench's top is
                among them; its top and its kernel name are the module's
  link.cfg      its kernel and port are kernel.xml's
  the top       its ports are named as the two interfaces' prefixes say, and
                its address and data widths are the package's names

`findings` is the check; the tests run it on the tree, and on copies with one
fault planted each, which it must report.

WHAT THIS CANNOT SEE: whether Vivado elaborates the sources, whether the
packager infers the interfaces, whether package_xo and v++ read these files as
written. Those are the lead's, in BUILD (docs/rtl/krnl.md, its limits).
"""
import os
import re
import xml.etree.ElementTree as ET

from spec import constants as C

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XML, TCL, CFG, TOP = "hw/kernel.xml", "hw/package_kernel.tcl", "hw/link.cfg", "rtl/krnl/undertone_krnl.sv"
BENCH_TOPS = ("rtl/krnl/krnl_max.sv", "rtl/krnl/krnl_small.sv", "rtl/seam/", "rtl/core/core_small.sv", "rtl/p0/")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def findings(xml_text, tcl_text, cfg_text, top_text):
    """Each way the four texts disagree with the definition or with one another, as a list of sentences."""
    out = []
    kernel = ET.fromstring(xml_text).find("kernel")
    name = kernel.get("name")
    module = re.search(r"^module\s+(\w+)", top_text, re.M).group(1)
    if name != module:
        out.append("kernel.xml names the kernel %r, the top module is %r" % (name, module))
    if kernel.get("hwControlProtocol") != "user_managed":
        out.append("the protocol is %r, not user_managed" % kernel.get("hwControlProtocol"))
    ports = dict((p.get("name"), p) for p in kernel.find("ports"))
    if set(ports) != {"s_axi_control", "m_axi_gmem"}:
        out.append("the ports are %s" % sorted(ports))
    else:
        slave, master = ports["s_axi_control"], ports["m_axi_gmem"]
        if (slave.get("mode"), int(slave.get("range"), 16), int(slave.get("dataWidth"))) != \
                ("slave", 2 ** C.BUS["address_bits"], C.BUS["word_bits"]):
            out.append("the slave is %s, %s, %s" % (slave.get("mode"), slave.get("range"), slave.get("dataWidth")))
        if (master.get("mode"), int(master.get("dataWidth"))) != ("master", 8 * C.MEMORY_SLOT_BYTES):
            out.append("the master is %s of %s bits" % (master.get("mode"), master.get("dataWidth")))
    args = list(kernel.find("args"))
    if len(args) != 1:
        out.append("there are %d arguments, not one" % len(args))
    else:
        a = args[0]
        if (a.get("port"), a.get("addressQualifier"), int(a.get("offset"), 16), int(a.get("size"), 16), a.get("id")) != \
                ("m_axi_gmem", "1", C.REGISTERS["krn_buffer"][0], C.REGISTERS["krn_buffer"][2] * C.BUS["word_bits"] // 8, "0"):
            out.append("the argument is on %s at %s of %s bytes, id %s" % (a.get("port"), a.get("offset"), a.get("size"), a.get("id")))

    m = re.search(r"set sources \{([^}]*)\}", tcl_text)
    sources = m.group(1).split() if m else []
    if not sources:
        out.append("the script names no sources")
    for rel in sources:
        if not os.path.isfile(os.path.join(ROOT, rel)):
            out.append("the script names %s, which is not a file of the tree" % rel)
        if any(rel.startswith(b) for b in BENCH_TOPS):
            out.append("the script packages %s, a bench's top" % rel)
    if sources and (sources[0] != "spec/undertone_pkg.sv" or sources[-1] != TOP):
        out.append("the script's sources begin with %s and end with %s" % (sources[0], sources[-1]))
    if "set_property top %s " % name not in tcl_text or "-kernel_name %s " % name not in tcl_text:
        out.append("the script's top or kernel name is not %s" % name)
    for busif in ("s_axi_control", "m_axi_gmem"):
        if "-busif %s -clock ap_clk" % busif not in tcl_text:
            out.append("the script does not put %s on ap_clk" % busif)

    nk = re.search(r"^nk=(\w+):1:(\w+)$", cfg_text, re.M)
    sp = re.search(r"^sp=(\w+)\.(\w+):HBM\[\d+\]$", cfg_text, re.M)
    if not nk or nk.group(1) != name or not sp or sp.group(1) != nk.group(2) or sp.group(2) != "m_axi_gmem":
        out.append("link.cfg's nk and sp do not name %s and m_axi_gmem" % name)

    for port in ("ap_clk", "ap_rst_n", "s_axi_control_awaddr", "s_axi_control_rdata", "m_axi_gmem_awaddr", "m_axi_gmem_wdata"):
        if not re.search(r"\b%s\b\s*,?\s*(//.*)?$" % port, top_text, re.M):
            out.append("the top has no port %s" % port)
    if "s_axi_control_awaddr" not in top_text or "undertone_pkg::BUS_ADDRESS_BITS-1:0]  s_axi_control_awaddr" not in top_text:
        out.append("the slave's address is not the package's BUS_ADDRESS_BITS wide")
    if "8*undertone_pkg::MEMORY_SLOT_BYTES-1:0] m_axi_gmem_wdata" not in top_text:
        out.append("the master's data is not one slot of the package's MEMORY_SLOT_BYTES")
    return out


def the_texts():
    return read(XML), read(TCL), read(CFG), read(TOP)


def test_krnl_packaging_agrees_with_the_definition():
    """The answer expected: no finding."""
    assert findings(*the_texts()) == []


PLANTED = (
    ("the argument at another offset", 0, 'offset="0xE00"', 'offset="0xE08"', "the argument is on"),
    ("ap_ctrl_hs", 0, 'hwControlProtocol="user_managed"', 'hwControlProtocol="ap_ctrl_hs"', "the protocol is"),
    ("a slave of another range", 0, 'range="0x1000"', 'range="0x2000"', "the slave is"),
    ("a master of 512 bits", 0, 'dataWidth="256"', 'dataWidth="512"', "the master is"),
    ("a bench's top packaged", 1, "  rtl/krnl/undertone_krnl.sv\n", "  rtl/krnl/krnl_small.sv\n  rtl/krnl/undertone_krnl.sv\n",
     "a bench's top"),
    ("a source that is not there", 1, "rtl/core/core_head.sv", "rtl/core/core_heads.sv", "not a file of the tree"),
    ("link.cfg's port misnamed", 2, "m_axi_gmem:HBM[0]", "m_axi_gmem0:HBM[0]", "link.cfg's"),
    ("the kernel renamed in the XML alone", 0, 'kernel name="undertone_krnl"', 'kernel name="undertone_kernel"',
     "names the kernel"),
)


def test_krnl_packaging_sees_each_planted_fault():
    """Each fault planted in a copy of one text must be reported, by the finding named for it."""
    for what, which, old, new, said in PLANTED:
        texts = list(the_texts())
        assert texts[which].count(old) == 1, "the plant %r no longer applies" % what
        texts[which] = texts[which].replace(old, new)
        got = findings(*texts)
        assert any(said in f for f in got), "%s: not reported (%r)" % (what, got)

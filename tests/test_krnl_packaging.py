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
  the top       its parameter and port lists, which Vivado's IP packager
                reads, hold plain numbers and no name of the package (the
                packager read `undertone_pkg::NAME` as a parameter named
                undertone_pkg and refused to package: the lead's trial of
                2026-11-24 11:06); each port's width is the definition's
                (address_bits, word_bits, slot_bytes), the profile and the
                pool and shift maxima are the definition's, the other maxima
                inside the definition's, and the queue a power of two

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

    out += header_findings(top_text)
    return out


def header_findings(top_text):
    """The top's parameter list and port list, which Vivado's IP packager reads: plain numbers only (it reads
    `undertone_pkg::NAME` as a parameter named undertone_pkg and refuses to package; the lead's trial of
    2026-11-24 11:06), each the definition's."""
    out = []
    m = re.search(r"^module\s+\w+\s*#\((.*?)^\);", top_text, re.M | re.S)
    if not m:
        return ["the top's module header cannot be read"]
    header = m.group(1)
    if "undertone_pkg" in header or "::" in header:
        out.append("the top's parameter or port list names the package: the packager cannot read it")
    params = dict((n, v) for n, v in re.findall(r"parameter\s+int\s+(\w+)\s*=\s*([^,\n/)]+?)\s*(?:,|\n|//)", header))
    for name, value in params.items():
        if not re.fullmatch(r"\d+", value):
            out.append("the parameter %s's default %r is not a plain number" % (name, value))
    params = dict((n, int(v)) for n, v in params.items() if re.fullmatch(r"\d+", v))
    s16x1 = C.PROFILES["s16x1"]
    want_equal = {"SAMPLE_BITS": s16x1["sample_bits"], "CHANNELS": s16x1["channels"], "B_POOL": C.MAX_POOL,
                  "B_SCORE_SHIFT": C.MAX_SCORE_SHIFT, "B_HIDDEN_SHIFT": C.MAX_HIDDEN_SHIFT}
    for name, value in want_equal.items():
        if params.get(name) != value:
            out.append("the parameter %s's default is %r, the definition's is %d" % (name, params.get(name), value))
    for name, most in (("B_FILTERS", C.MAX_FILTERS), ("B_TAPS", C.MAX_TAPS), ("B_ROWS", C.MAX_ROWS),
                       ("B_HIDDEN", C.MAX_HIDDEN)):
        if not 1 <= params.get(name, 0) <= most:
            out.append("the parameter %s's default %r is outside 1 to the definition's %d" % (name, params.get(name), most))
    q = params.get("RECORD_QUEUE", 0)
    if q < 2 or q & (q - 1):
        out.append("RECORD_QUEUE's default %r is not a power of two" % q)
    widths = {}
    for bracket, name in re.findall(r"(?:input|output)\s+logic\s*(\[[^\]]*\])?\s*(\w+)", header):
        if bracket:
            b = re.fullmatch(r"\[(\d+):0\]", bracket)
            if not b:
                out.append("the port %s's width %s is not [a number:0]" % (name, bracket))
                continue
            widths[name] = int(b.group(1)) + 1
        else:
            widths[name] = 1
    word, address, slot = C.BUS["word_bits"], C.BUS["address_bits"], C.MEMORY_SLOT_BYTES
    want = {"ap_clk": 1, "ap_rst_n": 1, "s_axi_control_awaddr": address, "s_axi_control_araddr": address,
            "s_axi_control_wdata": word, "s_axi_control_rdata": word, "s_axi_control_wstrb": word // 8,
            "m_axi_gmem_awaddr": 64, "m_axi_gmem_wdata": 8 * slot, "m_axi_gmem_rdata": 8 * slot,
            "m_axi_gmem_wstrb": slot}
    for name, bits in want.items():
        if widths.get(name) != bits:
            out.append("the port %s is %r bits wide, the definition's is %d" % (name, widths.get(name), bits))
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
    # The top's header, which Vivado's packager reads (2026-11-24 11:06): a name of the package, and a number
    # that parts from the definition's, in each of the places that failed there.
    ("the package's name back in a port's width", 3, "logic [11:0]                                 s_axi_control_awaddr",
     "logic [undertone_pkg::BUS_ADDRESS_BITS-1:0]  s_axi_control_awaddr", "names the package"),
    ("the package's name back in a default", 3, "B_POOL         = 65536,", "B_POOL         = undertone_pkg::MAX_POOL,",
     "not a plain number"),
    ("an address of 13 bits", 3, "logic [11:0]                                 s_axi_control_araddr",
     "logic [12:0]                                 s_axi_control_araddr", "s_axi_control_araddr is 13 bits"),
    ("a master of 512 bits in the top", 3, "logic [255:0]                                m_axi_gmem_wdata",
     "logic [511:0]                                m_axi_gmem_wdata", "m_axi_gmem_wdata is 512 bits"),
    ("a pool one short", 3, "B_POOL         = 65536,", "B_POOL         = 65535,", "B_POOL's default is 65535"),
    ("a shift one short", 3, "B_HIDDEN_SHIFT = 31,", "B_HIDDEN_SHIFT = 30,", "B_HIDDEN_SHIFT's default is 30"),
)


def test_krnl_packaging_sees_each_planted_fault():
    """Each fault planted in a copy of one text must be reported, by the finding named for it."""
    for what, which, old, new, said in PLANTED:
        texts = list(the_texts())
        assert texts[which].count(old) == 1, "the plant %r no longer applies" % what
        texts[which] = texts[which].replace(old, new)
        got = findings(*texts)
        assert any(said in f for f in got), "%s: not reported (%r)" % (what, got)

"""The learner's floorplan, held to the kernel's top and the link's configuration. The lead's, round 5, 2026-11-26.

hw/floorplan_learn.tcl adds the learner's instance to the platform's pblock for SLR1 before placement, and
hw/build.sh hands it to v++ for -t hw (docs/rtl/krnl.md, section 7, rows K31 to K34). Both are read by Vitis,
which this project's gate cannot run. What this file holds is that the names in them are the tree's own:

  the Tcl       the cell it moves is level0_i/ulp/<the compute unit>/inst/<the learner's instance>, where the
                compute unit is hw/link.cfg's nk name and the instance is the one rtl/krnl/undertone_krnl.sv
                gives the module learn; the pblock is the platform's pblock_dynamic_SLR1; it stops the build
                by each of its three names
  build.sh      it hands the Tcl to v++ as --linkhook.do_first at vpl.impl.place_design, by an absolute path,
                inside the branch for -t hw alone, and the v++ line carries it

`findings` is the check; the tests run it on the tree, and on copies with one fault planted each, which it must
report.

WHAT THIS CANNOT SEE: whether v++ sources the hook where its help says, whether the cell exists under that
name in the implemented netlist (round 5's first link printed it so after placement: the Tcl's header), whether
the pblock has room, and whether the design routes or meets its clock. Those are the link's record.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TCL, BUILD, CFG, TOP = "hw/floorplan_learn.tcl", "hw/build.sh", "hw/link.cfg", "rtl/krnl/undertone_krnl.sv"
PBLOCK, STEP = "pblock_dynamic_SLR1", "vpl.impl.place_design"
REFUSALS = ("FLOORPLAN-NO-CELL", "FLOORPLAN-NO-PBLOCK", "FLOORPLAN-NOT-ASSIGNED")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def findings(tcl_text, build_text, cfg_text, top_text):
    """Each way the four texts disagree with one another, as a list of sentences."""
    out = []
    nk = re.search(r"^nk=(\w+):1:(\w+)\s*$", cfg_text, re.M)
    unit = nk.group(2) if nk else None
    inst = re.search(r"^\s*learn\s*#\s*\(.*?\)\s*(\w+)\s*\(", top_text, re.M | re.S)
    instance = inst.group(1) if inst else None
    cell = re.search(r"^set\s+cell_name\s+(\S+)\s*$", tcl_text, re.M)
    if not cell:
        out.append("the Tcl sets no cell_name")
    elif cell.group(1) != "level0_i/ulp/%s/inst/%s" % (unit, instance):
        out.append("the Tcl moves %s; the compute unit is %s and the top's learner instance is %s"
                   % (cell.group(1), unit, instance))
    pb = re.search(r"^set\s+pblock_name\s+(\S+)\s*$", tcl_text, re.M)
    if not pb or pb.group(1) != PBLOCK:
        out.append("the Tcl's pblock is %s, not %s" % (pb.group(1) if pb else None, PBLOCK))
    for name in REFUSALS:
        if not re.search(r'^\s*error\s+"%s:' % re.escape(name), tcl_text, re.M):
            out.append("the Tcl does not stop the build by the name %s" % name)
    hook = re.search(r'^\s*HOOK=\(--linkhook\.do_first\s+"([\w.]+),\$\(pwd\)/hw/floorplan_learn\.tcl"\)\s*$',
                     build_text, re.M)
    if not hook:
        out.append("build.sh does not hand hw/floorplan_learn.tcl to v++ by --linkhook.do_first and an absolute path")
    elif hook.group(1) != STEP:
        out.append("build.sh hands the Tcl over at %s, not %s" % (hook.group(1), STEP))
    else:
        before = build_text[:hook.start()]
        branch = before.rfind("if [")
        if branch < 0 or not re.match(r'if \[ "\$T" = hw \]; then', before[branch:]) or "fi" in before[branch:].split():
            out.append("build.sh's hook is not inside the branch for -t hw alone")
    link = re.search(r"^v\+\+ -l .*$", build_text, re.M)
    if not link or '"${HOOK[@]}"' not in link.group(0):
        out.append("build.sh's v++ line does not carry the hook")
    return out


def the_texts():
    return read(TCL), read(BUILD), read(CFG), read(TOP)


def test_krnl_floorplan_names_the_trees_own_cell_pblock_and_step():
    """The answer expected: no finding."""
    assert findings(*the_texts()) == []


PLANTED = (
    ("the learner's instance renamed in the top", 3, ") u_learn (", ") u_learner (", "instance is u_learner"),
    ("the compute unit renamed in link.cfg", 2, "nk=undertone_krnl:1:undertone_krnl_1",
     "nk=undertone_krnl:1:undertone_krnl_2", "compute unit is undertone_krnl_2"),
    ("the pblock of SLR0", 0, "set pblock_name pblock_dynamic_SLR1", "set pblock_name pblock_dynamic_SLR0",
     "pblock is pblock_dynamic_SLR0"),
    ("a refusal made a message", 0, 'error "FLOORPLAN-NOT-ASSIGNED:', 'puts "FLOORPLAN-NOT-ASSIGNED:',
     "by the name FLOORPLAN-NOT-ASSIGNED"),
    ("the hook at routing", 1, '"vpl.impl.place_design,', '"vpl.impl.route_design,', "at vpl.impl.route_design"),
    ("the hook for every target", 1, 'if [ "$T" = hw ]; then\n  [ -f hw/floorplan_learn.tcl ]',
     'if true; then\n  [ -f hw/floorplan_learn.tcl ]', "not inside the branch"),
    ("the hook left off the v++ line", 1, '--kernel_frequency "$F" "${HOOK[@]}" \\', '--kernel_frequency "$F" \\',
     "does not carry the hook"),
)


def test_krnl_floorplan_sees_each_planted_fault():
    """Each fault planted in a copy of one text must be reported, by the finding named for it."""
    for what, which, old, new, said in PLANTED:
        texts = list(the_texts())
        assert texts[which].count(old) == 1, "the plant %r no longer applies" % what
        texts[which] = texts[which].replace(old, new)
        got = findings(*texts)
        assert any(said in f for f in got), "%s: not reported (%r)" % (what, got)

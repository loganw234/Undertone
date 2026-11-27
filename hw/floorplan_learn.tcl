# The learner placed in SLR1. The lead's, round 5, 2026-11-26; docs/rtl/krnl.md, section 7, rows K31 to K34.
#
# v++ sources this before placement, in the implementation run's own Vivado with the whole design open:
# hw/build.sh hands it over for -t hw only, as --linkhook.do_first at vpl.impl.place_design. It adds one
# hierarchical cell, the learner's instance in the kernel's top (rtl/krnl/undertone_krnl.sv, u_learn), to the
# platform's pblock for SLR1. The platform's own hook (its preopt.tcl) adds its SLR1 hierarchy to that pblock
# the same way. The netlist is unchanged: this says where the learner sits, not what it computes.
#
# It stops the build by name unless the cell and the pblock are each exactly one, and unless the cell is in that
# pblock afterwards: FLOORPLAN-NO-CELL, FLOORPLAN-NO-PBLOCK, FLOORPLAN-NOT-ASSIGNED. When it has done its work
# it prints one line beginning UNDERTONE-FLOORPLAN.
#
# The cell's path is the one round 5's first link of f9477c5 printed after placement, in its physical
# optimisation's messages (level0_i/ulp/undertone_krnl_1/inst/u_learn/...). tests/test_krnl_floorplan.py holds
# its last name to the top's instance and the compute unit's name to hw/link.cfg's.
#
# What it cannot see: whether the placer finds room in that pblock, whether the design then routes, and whether
# the learner's paths across the SLR boundary meet the clock. Those are the link's record.

set cell_name   level0_i/ulp/undertone_krnl_1/inst/u_learn
set pblock_name pblock_dynamic_SLR1

set cells [get_cells -quiet $cell_name]
if {[llength $cells] != 1} {
    error "FLOORPLAN-NO-CELL: [llength $cells] cells are named $cell_name; the learner's instance must be one"
}
if {[get_property IS_PRIMITIVE $cells]} {
    error "FLOORPLAN-NO-CELL: $cell_name is a primitive, not the learner's hierarchy"
}
set pblocks [get_pblocks -quiet $pblock_name]
if {[llength $pblocks] != 1} {
    error "FLOORPLAN-NO-PBLOCK: [llength $pblocks] pblocks are named $pblock_name"
}
set before [get_pblocks -quiet -of_objects $cells]
add_cells_to_pblock $pblocks $cells
set after [get_pblocks -quiet -of_objects $cells]
if {[llength $after] != 1 || [get_property NAME $after] ne $pblock_name} {
    error "FLOORPLAN-NOT-ASSIGNED: $cell_name is in '$after' after the assignment, not in $pblock_name"
}
set under [llength [get_cells -quiet -hierarchical -filter "IS_PRIMITIVE && NAME =~ $cell_name/*"]]
puts "UNDERTONE-FLOORPLAN: $cell_name, in '$before' before, is in $after now, with $under primitives under it"

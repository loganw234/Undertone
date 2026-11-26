# Package the kernel's RTL into a Vitis kernel object (.xo). Parcel KRNL, round 3; docs/rtl/krnl.md.
#
#   vivado -mode batch -source hw/package_kernel.tcl -tclargs <part> <build_dir>
#
# Adapted from the sibling project's <repos>/cft-fp256/hw/package_kernel.tcl, which
# follows the Vitis_Accel_Examples RTL kernel packaging sequence; read there and
# not copied whole. What differs:
#
#   - THE SOURCES ARE NAMED, NOT GLOBBED. rtl/krnl/ also holds two tops that are
#     the benches' alone (krnl_max.sv, krnl_small.sv), and rtl/ holds the seam's
#     and the core's small tops; none of them may be packaged.
#     tests/test_krnl_packaging.py holds that each file below exists and that no
#     bench's top is among them.
#   - NO GENERICS. The kernel's parameters' defaults ARE the first build's
#     maxima (rtl/krnl/undertone_krnl.sv): 16-bit samples on one channel, 4
#     filters, 4 rows, 128 taps, 12 hidden units, the definition's other maxima,
#     a queue of 512. Every user parameter is removed, as the sibling's script
#     does, so the IP carries the defaults; every HDL parameter it carries is
#     printed as an HDLPARAM: line, which is what a build's manifest should copy.
#   - ONE MASTER, m_axi_gmem, and the slave s_axi_control; the control protocol
#     is user-managed, carried by hw/kernel.xml.
#
# Written by parcel KRNL, which had no Vivado (its brief). The lead has since
# run it with Vivado 2022.2, in BUILD (docs/rtl/krnl.md, K20 and the paragraph
# on the first link): it failed once (K20) and has packaged since, and v++
# linked what it packaged for emulation. The first link for the card
# synthesised it and failed in placement, for the reason hw/link.cfg gives. What this script's runs do not say: the clock, which the build asks
# for and the build's own timing summary reports.

set part      "xcu50-fsvh2104-2-e"
set build_dir "build"
if {$argc >= 1} { set part      [lindex $argv 0] }
if {$argc >= 2} { set build_dir [lindex $argv 1] }

set hw_dir   [file dirname [file normalize [info script]]]
set root_dir [file normalize "$hw_dir/.."]
set pkg_dir  [file normalize "$build_dir/packaged_kernel"]
set tmp_dir  [file normalize "$build_dir/tmp_kernel_pack"]
set xo_path  [file normalize "$build_dir/undertone_krnl.xo"]

# The sources, in compile order: the generated package first.
set sources {
  spec/undertone_pkg.sv
  rtl/source/source_mulc.sv
  rtl/source/source.sv
  rtl/inject/inject.sv
  rtl/core/core_head.sv
  rtl/core/core.sv
  rtl/learn/learn.sv
  rtl/learn/learn_port.sv
  rtl/krnl/undertone_krnl.sv
}

puts "PACKAGE: part=$part build=$build_dir"
file mkdir $build_dir

create_project -force kernel_pack $tmp_dir -part $part
foreach f $sources {
  add_files -norecurse [file join $root_dir $f]
}
set_property top undertone_krnl [current_fileset]
update_compile_order -fileset sources_1

ipx::package_project -root_dir $pkg_dir -vendor undertone -library kernel \
    -taxonomy /KernelIP -import_files -set_current false
ipx::unload_core $pkg_dir/component.xml
ipx::edit_ip_in_project -upgrade true -name tmp_edit_project \
    -directory $pkg_dir $pkg_dir/component.xml

set core [ipx::current_core]
set_property core_revision 1 $core

foreach up [ipx::get_user_parameters] {
  ipx::remove_user_parameter [get_property NAME $up] $core
}
# What the .xo carries, by name, after the removal: the line a manifest should trust.
foreach hp [ipx::get_hdl_parameters -of_objects $core] {
  puts "HDLPARAM: [get_property NAME $hp] = [get_property value $hp]"
}
set_property sdx_kernel true $core
set_property sdx_kernel_type rtl $core
set_property supported_families { } $core
set_property auto_family_support_level level_2 $core
ipx::create_xgui_files $core
ipx::associate_bus_interfaces -busif s_axi_control -clock ap_clk $core
ipx::associate_bus_interfaces -busif m_axi_gmem -clock ap_clk $core
ipx::update_checksums $core
ipx::save_core $core
close_project -delete

package_xo -xo_path $xo_path -kernel_name undertone_krnl \
    -ip_directory $pkg_dir -kernel_xml $hw_dir/kernel.xml -force

puts "INFO: wrote $xo_path"

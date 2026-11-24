// The seam: the source, the injector and the detector core, wired as model/run.py wires the model's.
//
//     source  --src_valid, src_frame-->  inject  --inj_valid, inj_frame-->  the core  -->  out_valid, out_record
//
// EVERY WIRE OF THIS TOP, and there are no others:
//     clk, rst                                    to all three blocks
//     reg_valid, reg_we, reg_addr, reg_wdata      to all three blocks, each as it comes in
//     src_valid, src_frame                        the source's out_valid and out_frame, to the injector's
//                                                 in_valid and in_frame
//     inj_valid, inj_frame                        the injector's out_valid and out_frame, to the core's
//                                                 in_valid and in_frame
//     out_valid, out_record                       the core's, out of the top
//     reg_rdata                                   the three blocks' reg_rdata, ORed
//
// TRUTH ISOLATION, and what it rests on here. The core is wired to inj_valid and inj_frame AND TO
// NOTHING ELSE OF THE INJECTOR. The injector's only other output, its reg_rdata, goes to the bus and
// not to the core. What this top cannot give: the register port is one bus, so the writes that carry
// a truth record reach the core's port as they reach the injector's. That the core does nothing with
// a write outside its own block is the core's (docs/rtl/core.md); what holds it for this chain is the
// bench's test of other truth records over the same samples (docs/rtl/seam.md).
//
// NO REGISTER AT A JOINT. Each block puts its frame out with a valid that is high for one clock, and
// each takes a frame at the edge where its in_valid is high. The source and the injector each hold
// their frame after that clock, until their next one; this top does not rely on it.
//
// THE REGISTER PORT. Each block answers inside its own range of the map and reads zero outside it
// (the lead's ruling for the RTL parcels), and each reg_rdata is a register, so the OR of the three
// is the addressed block's word, seen at the edge after the read's.
//
// The source's word_valid and word are for the source's own bench and are left unconnected.
//
// WHAT IT DOES NOT DO, each a stated limit of docs/rtl/seam.md: it has no stream input, so nothing
// but the source can feed the injector; it has no back-pressure, as no block has; the core is at the
// maxima of rtl/seam/seam_core.sv, not the definition's; it has never been synthesised.
`timescale 1ns / 1ps

module seam #(
    parameter int SAMPLE_BITS = 16,
    parameter int CHANNELS    = 1
) (
    input  logic                                        clk,
    input  logic                                        rst,          // synchronous, active high
    input  logic                                        reg_valid,
    input  logic                                        reg_we,
    input  logic [undertone_pkg::BUS_ADDRESS_BITS-1:0]  reg_addr,
    input  logic [undertone_pkg::BUS_WORD_BITS-1:0]     reg_wdata,
    output logic [undertone_pkg::BUS_WORD_BITS-1:0]     reg_rdata,
    output logic                                        out_valid,
    output logic [undertone_pkg::SCORE_RECORD_BITS-1:0] out_record
);
    import undertone_pkg::*;

    localparam int W = CHANNELS * SAMPLE_BITS;

    // the two joints
    logic         src_valid;
    logic [W-1:0] src_frame;
    logic         inj_valid;
    logic [W-1:0] inj_frame;

    // the bus's three answers
    logic [BUS_WORD_BITS-1:0] src_rdata;
    logic [BUS_WORD_BITS-1:0] inj_rdata;
    logic [BUS_WORD_BITS-1:0] core_rdata;

    source #(
        .SAMPLE_BITS(SAMPLE_BITS),
        .CHANNELS(CHANNELS)
    ) u_source (
        .clk(clk),
        .rst(rst),
        .reg_valid(reg_valid),
        .reg_we(reg_we),
        .reg_addr(reg_addr),
        .reg_wdata(reg_wdata),
        .reg_rdata(src_rdata),
        .out_valid(src_valid),
        .out_frame(src_frame),
        .word_valid(),
        .word()
    );

    inject #(
        .SAMPLE_BITS(SAMPLE_BITS),
        .CHANNELS(CHANNELS)
    ) u_inject (
        .clk(clk),
        .rst(rst),
        .reg_valid(reg_valid),
        .reg_we(reg_we),
        .reg_addr(reg_addr),
        .reg_wdata(reg_wdata),
        .reg_rdata(inj_rdata),
        .in_valid(src_valid),
        .in_frame(src_frame),
        .out_valid(inj_valid),
        .out_frame(inj_frame)
    );

    seam_core #(
        .SAMPLE_BITS(SAMPLE_BITS),
        .CHANNELS(CHANNELS)
    ) u_core (
        .clk(clk),
        .rst(rst),
        .in_valid(inj_valid),
        .in_frame(inj_frame),
        .out_valid(out_valid),
        .out_record(out_record),
        .reg_valid(reg_valid),
        .reg_we(reg_we),
        .reg_addr(reg_addr),
        .reg_wdata(reg_wdata),
        .reg_rdata(core_rdata)
    );

    assign reg_rdata = src_rdata | inj_rdata | core_rdata;
endmodule

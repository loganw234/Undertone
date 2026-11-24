// The detector core at small maxima: a top for the benches, and nothing else.
//
// It is rtl/core/core.sv, the same lines, built with seven maxima below the definition's. It
// exists because the benches' runner hands a top two parameters, SAMPLE_BITS and CHANNELS, and
// the manifest has no key for more: a build at less than the definition's maxima has to be a top
// of its own.
//
// Why these seven values (docs/rtl/core.md has the whole account):
//   - every one differs from the definition's, so a capability register is not the constant a
//     test could otherwise read;
//   - rows are more than filters, so SHAPE_ROWS and SHAPE_FILTERS are two bounds; and no fewer,
//     or a shape with the most filters could not be made at all;
//   - 6 taps is not a power of two and a pool of 1024 is one: where a pointer's or a counter's
//     width goes wrong;
//   - a pool of 1024 lets a hidden sum reach exactly -2^63 under the 16-bit profile;
//   - a score shift of 20 is enough to bring this build's largest output sum inside the field.
//
// A mutant of the core is this top built on a patched copy of core.sv or core_head.sv.
`timescale 1ns / 1ps

module core_small #(
    parameter int SAMPLE_BITS = 16,
    parameter int CHANNELS    = 1
) (
    input  logic                                        clk,
    input  logic                                        rst,
    input  logic                                        in_valid,
    input  logic [CHANNELS*SAMPLE_BITS-1:0]             in_frame,
    output logic                                        out_valid,
    output logic [undertone_pkg::SCORE_RECORD_BITS-1:0] out_record,
    input  logic                                        reg_valid,
    input  logic                                        reg_we,
    input  logic [undertone_pkg::BUS_ADDRESS_BITS-1:0]  reg_addr,
    input  logic [undertone_pkg::BUS_WORD_BITS-1:0]     reg_wdata,
    output logic [undertone_pkg::BUS_WORD_BITS-1:0]     reg_rdata
);
    core #(
        .SAMPLE_BITS(SAMPLE_BITS),
        .CHANNELS(CHANNELS),
        .B_FILTERS(4),
        .B_TAPS(6),
        .B_ROWS(5),
        .B_POOL(1024),
        .B_SCORE_SHIFT(20),
        .B_HIDDEN(3),
        .B_HIDDEN_SHIFT(24)
    ) u_core (
        .clk(clk),
        .rst(rst),
        .in_valid(in_valid),
        .in_frame(in_frame),
        .out_valid(out_valid),
        .out_record(out_record),
        .reg_valid(reg_valid),
        .reg_we(reg_we),
        .reg_addr(reg_addr),
        .reg_wdata(reg_wdata),
        .reg_rdata(reg_rdata)
    );
endmodule

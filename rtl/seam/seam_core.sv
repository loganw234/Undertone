// The detector core at the seam's maxima: a top's part for the seam's bench, and nothing else.
//
// It is rtl/core/core.sv, the same lines, built with seven maxima below the definition's, as
// rtl/core/core_small.sv is. It exists for the reason that file gives: the benches' runner hands a
// top two parameters, SAMPLE_BITS and CHANNELS, and the manifest has no key for more.
//
// Why these seven values (docs/rtl/seam.md has the account):
//   - 64 taps and 3 rows hold stage E0's shape under both profiles: one filter of the reference
//     pulse's 64 taps reading every channel, which is 3 rows under the profile of three channels,
//     the bound itself;
//   - 2 filters and 2 hidden units, so that a shape that is not E0's also runs through the chain;
//   - a pool of 4, so that a swap through the chain has outputs that settle;
//   - everything else small, because every clock of the chain evaluates the core, and the chain
//     offers it a frame every 20 or 60 clocks.
`timescale 1ns / 1ps

module seam_core #(
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
        .B_FILTERS(2),
        .B_TAPS(64),
        .B_ROWS(3),
        .B_POOL(4),
        .B_SCORE_SHIFT(12),
        .B_HIDDEN(2),
        .B_HIDDEN_SHIFT(16)
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

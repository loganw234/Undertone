// The detector core at the small top's maxima with the definition's twelve hidden units: a top for
// the overflow flag's bench (rtl/tb/bench_flag.py), and nothing else.
//
// It is rtl/core/core.sv, the same lines, built with rtl/core/core_small.sv's seven maxima but one:
// B_HIDDEN is 12, the definition's MAX_HIDDEN and the first build's (docs/plans/R3-first-light.md,
// question 2). The bank is the small top's, so a stream costs here what it costs there; at the full
// top a case would cost several times more (docs/rtl/core.md, row C16). docs/rtl/flag.md says what
// the bench runs on it and why.
//
// A mutant of the core is this top built on a patched copy of core.sv or core_head.sv.
`timescale 1ns / 1ps

module core_twelve #(
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
        .B_HIDDEN(12),
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

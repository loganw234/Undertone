// The learner beside a small core, for the benches: frames and truth from the bench.
//
//     in_valid, in_frame  -->  the core  -->  out_valid, out_record
//                 \-->  the learner  <--  truth_valid, truth_index
//     reg_*  -->  the learner, and through learn_port to the core's register port
//
// THE BUILD, each value a small build's (docs/rtl/learn.md, section 2): the core at 2 filters, 6 taps,
// 4 rows, a pool of 2, a score shift of 1, 1 hidden unit and a hidden shift of 0, so that each condition of
// SWAP_SHAPE can be made alone (two filters under s24x3 are 3 rows and 1 more); the learner at 6 taps,
// count_bits 3 (FULL by real windows, 7 a label) and an update time of 16 frames, which covers its update
// at the chain's rate.
//
// THE TRUTH PORT is the bench's: a record's index, for one clock. It keeps the injector's contract by the
// bench's construction (strictly ascending; pushed at an edge after which the core's next index is at
// most the record's), and the learner does not check it.
//
// THE CORE'S STATE IS READ BY HIERARCHICAL NAME (the lead's ruling, V2): u_core's registers, and `closed`
// worked from its pipeline's tags as core.sv's status read does. Simulation only: a synthesis tool may not
// take it, and the kernel's round gives the core ports for it. No line of core.sv changes.
`timescale 1ns / 1ps

module learn_small #(
    parameter int SAMPLE_BITS = 16,
    parameter int CHANNELS    = 1
) (
    input  logic                                        clk,
    input  logic                                        rst,
    input  logic                                        in_valid,
    input  logic [CHANNELS*SAMPLE_BITS-1:0]             in_frame,
    output logic                                        out_valid,
    output logic [undertone_pkg::SCORE_RECORD_BITS-1:0] out_record,
    input  logic                                        truth_valid,
    input  logic [undertone_pkg::TRUTH_INDEX_BITS-1:0]  truth_index,
    input  logic                                        reg_valid,
    input  logic                                        reg_we,
    input  logic [undertone_pkg::BUS_ADDRESS_BITS-1:0]  reg_addr,
    input  logic [undertone_pkg::BUS_WORD_BITS-1:0]     reg_wdata,
    output logic [undertone_pkg::BUS_WORD_BITS-1:0]     reg_rdata
);
    import undertone_pkg::*;

    localparam int TAPS    = 6;
    localparam int TAG_SEL = SCORE_INDEX_BITS + SCORE_EPOCH_BITS;   // core.sv's tag: the bank select's bit

    logic                        c_valid, c_we;
    logic [BUS_ADDRESS_BITS-1:0] c_addr, lw_addr;
    logic [BUS_WORD_BITS-1:0]    c_wdata, lw_wdata, core_rdata, learn_rdata;
    logic                        hold, intercept, host, hold_q, hold_end_q, lw_valid;

    core #(
        .SAMPLE_BITS(SAMPLE_BITS), .CHANNELS(CHANNELS),
        .B_FILTERS(2), .B_TAPS(TAPS), .B_ROWS(4), .B_POOL(2), .B_SCORE_SHIFT(1), .B_HIDDEN(1), .B_HIDDEN_SHIFT(0)
    ) u_core (
        .clk(clk), .rst(rst),
        .in_valid(in_valid), .in_frame(in_frame),
        .out_valid(out_valid), .out_record(out_record),
        .reg_valid(c_valid), .reg_we(c_we), .reg_addr(c_addr), .reg_wdata(c_wdata), .reg_rdata(core_rdata)
    );

    // the core's state, by hierarchical name
    wire                        v_running   = u_core.running;
    wire [SCORE_INDEX_BITS-1:0] v_next      = u_core.next_index;
    wire [BUS_WORD_BITS-1:0]    v_taps      = u_core.cfg_taps;
    wire [BUS_WORD_BITS-1:0]    v_filters   = u_core.cfg_filters;
    wire [BUS_WORD_BITS-1:0]    v_rows      = u_core.cfg_rows;
    wire [BUS_WORD_BITS-1:0]    v_pool      = u_core.cfg_pool;
    wire [BUS_WORD_BITS-1:0]    v_shift     = u_core.cfg_score_shift;
    wire                        v_rect_abs  = u_core.cfg_rect_abs;
    wire                        v_no_hidden = u_core.cfg_no_hidden;
    wire                        v_commit    = u_core.commit_valid;
    wire [SCORE_INDEX_BITS-1:0] v_commit_at = u_core.commit_at;
    wire                        v_partial   = u_core.ld_partial;
    wire                        take        = in_valid && v_running;
    logic [7:1]                 v_closed_at;
    genvar g;
    generate
        for (g = 1; g <= 7; g++) begin : closed_at
            assign v_closed_at[g] = u_core.vld[g] && (u_core.tg[g][TAG_SEL] != u_core.active_sel);
        end
    endgenerate
    wire                        v_closed    = |v_closed_at;

    learn #(
        .SAMPLE_BITS(SAMPLE_BITS), .CHANNELS(CHANNELS), .B_TAPS(TAPS), .B_COUNT_BITS(3), .B_UPDATE_FRAMES(16)
    ) u_learn (
        .clk(clk), .rst(rst),
        .in_valid(in_valid), .in_frame(in_frame),
        .core_running(v_running), .core_next_index(v_next), .core_taps(v_taps), .core_filters(v_filters),
        .core_rows(v_rows), .core_pool(v_pool), .core_score_shift(v_shift), .core_rect_abs(v_rect_abs),
        .core_no_hidden(v_no_hidden), .core_commit(v_commit), .core_commit_at(v_commit_at),
        .core_partial(v_partial), .core_closed(v_closed),
        .truth_valid(truth_valid), .truth_index(truth_index),
        .reg_valid(reg_valid), .reg_we(reg_we), .reg_addr(reg_addr), .reg_wdata(reg_wdata), .reg_rdata(learn_rdata),
        .port_hold(hold), .port_intercept(intercept), .port_host(host),
        .hold_q(hold_q), .hold_end_q(hold_end_q), .lw_valid(lw_valid), .lw_addr(lw_addr), .lw_wdata(lw_wdata)
    );

    learn_port u_port (
        .reg_valid(reg_valid), .reg_we(reg_we), .reg_addr(reg_addr), .reg_wdata(reg_wdata), .take(take),
        .hold_q(hold_q), .hold_end_q(hold_end_q), .lw_valid(lw_valid), .lw_addr(lw_addr), .lw_wdata(lw_wdata),
        .hold(hold), .intercept(intercept), .host(host),
        .c_valid(c_valid), .c_we(c_we), .c_addr(c_addr), .c_wdata(c_wdata)
    );

    assign reg_rdata = core_rdata | learn_rdata;
endmodule

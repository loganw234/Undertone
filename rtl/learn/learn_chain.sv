// The seam's chain with the learner beside the core, at the definition's maxima for the learner.
//
//     source  --src_valid, src_frame-->  inject  --inj_valid, inj_frame-->  the core  -->  out_valid, out_record
//                                           |                     \-->  the learner
//                                           \-- each record taken, its index alone --/
//     reg_*  -->  the source, the injector and the learner as each comes in, and through learn_port to the core
//     reg_rdata  the four blocks' reg_rdata, ORed
//
// THE BUILD. The core: 1 filter, 128 taps (the definition's), rows = CHANNELS, a pool of 1, a score shift of
// 0, 1 hidden unit: the matched filter of any length up to the definition's, and nothing else is needed
// here. The learner: the definition's own bounds, 128 taps, count_bits 32, an update time of 256 frames.
//
// TRUTH ISOLATION, and what it rests on here. The core is wired to inj_valid and inj_frame and to nothing
// else of the injector, as in rtl/seam/seam.sv. The learner is handed, of each truth record, the index the
// injector took into its store, and nothing else: not its pulse id, not its amplitude. Its only way to the
// core is the core's own register port, through learn_port, at an update the host named.
//
// THE CORE'S AND THE INJECTOR'S STATE ARE READ BY HIERARCHICAL NAME (the lead's ruling, V2): the core's
// registers, `closed` from its pipeline's tags, and the injector's `wr_push` and `t_index`. Simulation only;
// the kernel's round gives both blocks ports for them. No line of an earlier parcel's file changes.
`timescale 1ns / 1ps

module learn_chain #(
    parameter int SAMPLE_BITS = 16,
    parameter int CHANNELS    = 1
) (
    input  logic                                        clk,
    input  logic                                        rst,
    input  logic                                        reg_valid,
    input  logic                                        reg_we,
    input  logic [undertone_pkg::BUS_ADDRESS_BITS-1:0]  reg_addr,
    input  logic [undertone_pkg::BUS_WORD_BITS-1:0]     reg_wdata,
    output logic [undertone_pkg::BUS_WORD_BITS-1:0]     reg_rdata,
    output logic                                        out_valid,
    output logic [undertone_pkg::SCORE_RECORD_BITS-1:0] out_record
);
    import undertone_pkg::*;

    localparam int W       = CHANNELS * SAMPLE_BITS;
    localparam int TAG_SEL = SCORE_INDEX_BITS + SCORE_EPOCH_BITS;   // core.sv's tag: the bank select's bit

    logic                        src_valid, inj_valid;
    logic [W-1:0]                src_frame, inj_frame, core_frame;
    logic [BUS_WORD_BITS-1:0]    src_rdata, inj_rdata, core_rdata, learn_rdata;
    logic                        c_valid, c_we;
    logic [BUS_ADDRESS_BITS-1:0] c_addr, lw_addr;
    logic [BUS_WORD_BITS-1:0]    c_wdata, lw_wdata;
    logic                        hold, intercept, host, hold_q, hold_end_q, lw_valid;

    source #(.SAMPLE_BITS(SAMPLE_BITS), .CHANNELS(CHANNELS)) u_source (
        .clk(clk), .rst(rst),
        .reg_valid(reg_valid), .reg_we(reg_we), .reg_addr(reg_addr), .reg_wdata(reg_wdata), .reg_rdata(src_rdata),
        .out_valid(src_valid), .out_frame(src_frame), .word_valid(), .word()
    );

    inject #(.SAMPLE_BITS(SAMPLE_BITS), .CHANNELS(CHANNELS)) u_inject (
        .clk(clk), .rst(rst),
        .reg_valid(reg_valid), .reg_we(reg_we), .reg_addr(reg_addr), .reg_wdata(reg_wdata), .reg_rdata(inj_rdata),
        .in_valid(src_valid), .in_frame(src_frame), .out_valid(inj_valid), .out_frame(inj_frame)
    );

    core #(
        .SAMPLE_BITS(SAMPLE_BITS), .CHANNELS(CHANNELS),
        .B_FILTERS(1), .B_TAPS(MAX_TAPS), .B_ROWS(CHANNELS), .B_POOL(1), .B_SCORE_SHIFT(0), .B_HIDDEN(1), .B_HIDDEN_SHIFT(0)
    ) u_core (
        .clk(clk), .rst(rst),
        .in_valid(inj_valid), .in_frame(core_frame),
        .out_valid(out_valid), .out_record(out_record),
        .reg_valid(c_valid), .reg_we(c_we), .reg_addr(c_addr), .reg_wdata(c_wdata), .reg_rdata(core_rdata)
    );

    // the injector's truth: a record taken into its store at this edge, and its index
    wire                        t_push = u_inject.wr_push;
    wire [TRUTH_INDEX_BITS-1:0] t_index = u_inject.t_index;

    // the core is handed the injector's frame, and nothing else
    assign core_frame = inj_frame;

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
    wire                        take        = inj_valid && v_running;
    logic [7:1]                 v_closed_at;
    genvar g;
    generate
        for (g = 1; g <= 7; g++) begin : closed_at
            assign v_closed_at[g] = u_core.vld[g] && (u_core.tg[g][TAG_SEL] != u_core.active_sel);
        end
    endgenerate
    wire                        v_closed    = |v_closed_at;

    learn #(
        .SAMPLE_BITS(SAMPLE_BITS), .CHANNELS(CHANNELS), .B_TAPS(MAX_TAPS), .B_COUNT_BITS(LEARN_COUNT_BITS),
        .B_UPDATE_FRAMES(LEARN_UPDATE_FRAMES)
    ) u_learn (
        .clk(clk), .rst(rst),
        .in_valid(inj_valid), .in_frame(core_frame),
        .core_running(v_running), .core_next_index(v_next), .core_taps(v_taps), .core_filters(v_filters),
        .core_rows(v_rows), .core_pool(v_pool), .core_score_shift(v_shift), .core_rect_abs(v_rect_abs),
        .core_no_hidden(v_no_hidden), .core_commit(v_commit), .core_commit_at(v_commit_at),
        .core_partial(v_partial), .core_closed(v_closed),
        .truth_valid(t_push), .truth_index(t_index),
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

    assign reg_rdata = src_rdata | inj_rdata | core_rdata | learn_rdata;
endmodule

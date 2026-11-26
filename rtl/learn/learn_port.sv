// The core's register port, shared by the host and the learner (docs/rtl/learn.md, section 1).
//
//     hold       an update is named and not finished at this edge, judged as the frame at this edge leaves
//                the core's next index: the learner's two registered bits and this clock's take
//     intercept  the host's write of commit_at's upper word, shadow_begin or shadow_data while hold is
//                high: it reaches no block, and the learner refuses it, UPDATE_UNFINISHED
//     host       the host's access has the core's port at this edge: every access but one intercepted.
//                A read above all, since every block's reg_rdata must answer it for the bus's OR to hold
//     the port   the host's access when `host`, else the learner's write when it has one
//
// A few gates and no register: the learner, whose outputs are all registers, is the module to synthesise
// alone. What this does not do: it never delays the host. A host that holds the port at every clock holds
// the learner's writes back, and the update is then refused, UPDATE_UNFINISHED, past its F frames.
`timescale 1ns / 1ps

module learn_port (
    input  logic                                        reg_valid,
    input  logic                                        reg_we,
    input  logic [undertone_pkg::BUS_ADDRESS_BITS-1:0]  reg_addr,
    input  logic [undertone_pkg::BUS_WORD_BITS-1:0]     reg_wdata,
    input  logic                                        take,          // the core takes a frame at this edge
    input  logic                                        hold_q,
    input  logic                                        hold_end_q,
    input  logic                                        lw_valid,
    input  logic [undertone_pkg::BUS_ADDRESS_BITS-1:0]  lw_addr,
    input  logic [undertone_pkg::BUS_WORD_BITS-1:0]     lw_wdata,
    output logic                                        hold,
    output logic                                        intercept,
    output logic                                        host,
    output logic                                        c_valid,
    output logic                                        c_we,
    output logic [undertone_pkg::BUS_ADDRESS_BITS-1:0]  c_addr,
    output logic [undertone_pkg::BUS_WORD_BITS-1:0]     c_wdata
);
    import undertone_pkg::*;

    localparam int WBYTES = BUS_WORD_BITS / 8;

    wire held_row = (reg_addr == REG_COMMIT_AT_OFFSET + WBYTES) || (reg_addr == REG_SHADOW_BEGIN_OFFSET)
                    || (reg_addr == REG_SHADOW_DATA_OFFSET);

    assign hold      = hold_q && !(take && hold_end_q);
    assign intercept = reg_valid && reg_we && hold && held_row;
    assign host      = reg_valid && !intercept;
    assign c_valid   = host || lw_valid;
    assign c_we      = host ? reg_we : 1'b1;
    assign c_addr    = host ? reg_addr : lw_addr;
    assign c_wdata   = host ? reg_wdata : lw_wdata;
endmodule

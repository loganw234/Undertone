// A filter of one tap. NOT part of the detector.
//
// It exists for one job: to prove the bit-identity harness (rtl/tb/harness.py)
// on real RTL before the detector core is written. It is the reference model's
// core at one setting: one filter of one tap that reads every channel, a pool
// of 1, one head weight. Under that setting model/detector.py gives, for
// frame i = (x_0, ..., x_{C-1}):
//
//     y = sum over c of coef[c] * x_c        the filter, exact
//     r = y, or |y| when the rectifier is abs
//     a = head * r                           the pool of 1 passes r on
//     score = floor(a / 2^shift)             an arithmetic shift right
//
// and a score record of index i, the epoch it was given, no flag, that score.
// No flag can rise: at one tap and a pool of 1 every value here fits its width
// with room, and the score fits 64 bits (at most 3 * 2^23 * 2^17 * 2^17, under
// 2^60, for the wider profile).
//
// WHAT IT DOES NOT DO, each left to the detector core (parcel RTL-B): it has
// no weight store and no swap, no settling, no overflow flag, and it refuses
// nothing. A rectifier code that is not abs is treated as pass. Its
// configuration is a set of input ports that the bench holds steady from
// reset on, not the register map.
//
// It keeps the stream contract every bench of this project uses:
//     in_valid, in_frame     one frame per clock in which in_valid is high;
//                            channel c is in_frame[c*SAMPLE_BITS +: SAMPLE_BITS],
//                            two's complement
//     out_valid, out_record  one score record per clock in which out_valid is
//                            high, in the canonical layout of the generated
//                            package: the index field lowest
// The latency is one clock: the record for a frame taken at one rising edge is
// out, with out_valid high, at the next.
`timescale 1ns / 1ps

module onetap #(
    parameter int SAMPLE_BITS = 16,
    parameter int CHANNELS    = 1
) (
    input  logic                                          clk,
    input  logic                                          rst,          // synchronous, active high
    input  logic [CHANNELS*undertone_pkg::COEFF_BITS-1:0] cfg_coef,     // channel c at [c*COEFF_BITS +: COEFF_BITS], signed
    input  logic [undertone_pkg::COEFF_BITS-1:0]          cfg_head,     // signed
    input  logic [7:0]                                    cfg_rectifier,
    input  logic [7:0]                                    cfg_shift,
    input  logic [undertone_pkg::SCORE_EPOCH_BITS-1:0]    cfg_epoch,
    input  logic                                          in_valid,
    input  logic [CHANNELS*SAMPLE_BITS-1:0]               in_frame,
    output logic                                          out_valid,
    output logic [undertone_pkg::SCORE_RECORD_BITS-1:0]   out_record
);
    import undertone_pkg::*;

    // One product needs SAMPLE_BITS + COEFF_BITS signed bits; the sum over the channels, $clog2(CHANNELS) more.
    localparam int Y_BITS = SAMPLE_BITS + COEFF_BITS + $clog2(CHANNELS);
    localparam int A_BITS = Y_BITS + COEFF_BITS;

    logic signed [Y_BITS-1:0]           y, r;
    logic signed [A_BITS-1:0]           a;
    logic signed [SCORE_SCORE_BITS-1:0] score;
    logic        [SCORE_INDEX_BITS-1:0] index;

    always_comb begin
        y = '0;
        for (int c = 0; c < CHANNELS; c++) begin
            y = y + $signed(in_frame[c*SAMPLE_BITS +: SAMPLE_BITS]) * $signed(cfg_coef[c*COEFF_BITS +: COEFF_BITS]);
        end
        r = (cfg_rectifier == RECTIFIER_ABS && y < 0) ? -y : y;
        a = r * $signed(cfg_head);
        score = a >>> cfg_shift;    // a is signed: the shift is arithmetic, and the assignment extends the sign
    end

    always_ff @(posedge clk) begin
        if (rst) begin
            out_valid  <= 1'b0;
            out_record <= '0;
            index      <= '0;
        end else begin
            out_valid <= in_valid;
            if (in_valid) begin
                out_record                                            <= '0;
                out_record[SCORE_INDEX_LSB +: SCORE_INDEX_BITS]       <= index;
                out_record[SCORE_EPOCH_LSB +: SCORE_EPOCH_BITS]       <= cfg_epoch;
                out_record[SCORE_SCORE_LSB +: SCORE_SCORE_BITS]       <= score;
                index                                                 <= index + 1'b1;
            end
        end
    end
endmodule

// The low 64 bits of a 64-bit number times a 64-bit constant, in two clocks.
//
// The word generator of rtl/source/source.sv uses it twice, once for each of
// SplitMix64's two mixing multiplications (model/source.py, lines 76 and 77).
// The model's arithmetic is modulo 2^64, so only the products whose weight is
// below 2^64 matter: with x and K cut into four limbs of 16 bits, those are the
// ten products of limb i of x by limb j of K with i + j <= 3.
//
//     first edge    the ten products, each 16 bits by 16 into 32
//     second edge   their sum, each at its weight, modulo 2^64
//
// So y is the answer for the x that was on the input two rising edges before.
// It runs at every clock and has no valid: the caller counts the clocks.
//
// WHAT IT DOES NOT SAY: what it costs or whether it closes timing. Nothing here
// is synthesised. A 16-by-16 product is inside one DSP48E2 as D0's row D2
// describes that slice, and that row is BELIEVED.
`timescale 1ns / 1ps

module source_mulc #(
    parameter logic [63:0] K = 64'd1
) (
    input  logic        clk,
    input  logic [63:0] x,
    output logic [63:0] y
);
    logic [63:0] k;
    assign k = K;

    // p<i><j>: limb i of x by limb j of the constant, weight 2^(16 * (i + j))
    logic [31:0] p00, p01, p02, p03;
    logic [31:0] p10, p11, p12;
    logic [31:0] p20, p21;
    logic [31:0] p30;

    always_ff @(posedge clk) begin
        p00 <= x[15:0]  * k[15:0];
        p01 <= x[15:0]  * k[31:16];
        p02 <= x[15:0]  * k[47:32];
        p03 <= x[15:0]  * k[63:48];
        p10 <= x[31:16] * k[15:0];
        p11 <= x[31:16] * k[31:16];
        p12 <= x[31:16] * k[47:32];
        p20 <= x[47:32] * k[15:0];
        p21 <= x[47:32] * k[31:16];
        p30 <= x[63:48] * k[15:0];

        y <= {32'd0, p00}
           + {16'd0, p01, 16'd0} + {16'd0, p10, 16'd0}
           + {p02, 32'd0} + {p11, 32'd0} + {p20, 32'd0}
           + {p03[15:0], 48'd0} + {p12[15:0], 48'd0} + {p21[15:0], 48'd0} + {p30[15:0], 48'd0};
    end
endmodule

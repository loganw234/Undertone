// The detector's head, as a module of its own: the hidden layer and the score.
//
// It is steps 4a to 4d and 5 of model/detector.py (docs/model/head.md, section 1), for
// output i, from the pooled values z_k[i]:
//
//     u_j = sum over k of g[j][k] * z_k        the hidden sum, exact
//     t_j = floor(u_j / 2^q)                   THE FIRST ROUNDING: an arithmetic shift right,
//                                              reduced to the score field's width; the overflow
//                                              flag's first source
//     b_j = t_j, or |t_j| when between is abs  exact
//     a   = sum over j of o[j] * b_j           the output sum, exact
//     v   = floor(a / 2^s)                     THE SECOND ROUNDING, reduced to the score field's
//                                              width; the flag's second source
//
// ONE ROUTE FOR BOTH HEADS. The fabric builds no second head for a blob with no hidden layer.
// When cfg_no_hidden is high it runs head.md section 2's setting: unit 0 alone, whose weights
// are the K head weights (the store puts them there), q = the score shift, pass between, a head
// weight of the constant 1 (a mux, not a multiplier) and a score shift of 0. The bench holds
// that route against the model's version 1 route on every word.
//
// A value that does not fit the score field WRAPS: the field's bits are kept, the frame's
// overflow bit is set, and what follows is computed from the kept bits. Nothing saturates.
//
// THE CHOICE OF WEIGHT SET TRAVELS WITH THE SAMPLE: both banks' weights are at the ports, and
// each frame's own select bit, carried beside it, picks the bank for all its hidden weights at
// h1 and for all its head weights at h3. So no hidden sum and no output sum mixes two sets.
//
// Five registered stages, h0 to h4: the inputs are registered at h0 and the score at h4.
//     h0  the pooled values, the frame's valid and select
//     h1  the hidden products, each held at the hidden sum's width
//     h2  the hidden values after between, and the frame's overflow bit so far
//     h3  the output products, each held at the output sum's width
//     h4  the score, and the frame's overflow bit
//
// WIDTHS. W_POOL and W_HEAD (the hidden sum's) are the bank's and the pool's, and the core hands
// them in; their defaults here are the same closed forms, for a build of this module alone. The
// hidden value's width is the record's score field. Between is one bit more: |-2^63| = +2^63.
// The output sum's is what B_HIDDEN units at +-2^63 under a head weight at its lowest need.
//
// WHAT IT DOES NOT DO: it holds no weights and no shape; it refuses nothing; a unit past the
// shape's H must be handed zero weights (the store's are zero from reset) and then adds nothing
// and cannot overflow. No timing is claimed: a unit's sum, its shift and its comparison are one
// stage.
`timescale 1ns / 1ps

module core_head #(
    parameter int SAMPLE_BITS = 16,
    parameter int CHANNELS    = 1,
    parameter int B_FILTERS   = undertone_pkg::MAX_FILTERS,
    parameter int B_TAPS      = undertone_pkg::MAX_TAPS,
    parameter int B_ROWS      = undertone_pkg::MAX_ROWS,
    parameter int B_POOL      = undertone_pkg::MAX_POOL,
    parameter int B_HIDDEN    = undertone_pkg::MAX_HIDDEN,
    // the pooled value's width and the hidden sum's: the core's own, handed in
    parameter int W_POOL      = SAMPLE_BITS + undertone_pkg::COEFF_BITS - 2
                                + $clog2(B_POOL * ((CHANNELS < B_ROWS) ? CHANNELS : B_ROWS) * B_TAPS + 1) + 1,
    parameter int W_HEAD      = SAMPLE_BITS + undertone_pkg::COEFF_BITS - 2 + undertone_pkg::COEFF_BITS
                                + $clog2(B_ROWS * B_POOL * B_TAPS)
) (
    input  logic                                                    clk,
    input  logic                                                    rst,              // synchronous, active high
    input  logic                                                    in_valid,
    input  logic                                                    in_sel,           // the frame's bank: 0 is a, 1 is b
    input  logic [B_FILTERS*W_POOL-1:0]                             in_z,             // z_k at [k*W_POOL +: W_POOL], signed
    input  logic                                                    cfg_no_hidden,    // the shape's H is 0
    input  logic [7:0]                                              cfg_hidden_shift, // q
    input  logic [7:0]                                              cfg_score_shift,  // s
    input  logic                                                    cfg_between_abs,
    input  logic [B_HIDDEN*B_FILTERS*undertone_pkg::COEFF_BITS-1:0] hid_a,            // g[j][k] at index j*B_FILTERS + k
    input  logic [B_HIDDEN*B_FILTERS*undertone_pkg::COEFF_BITS-1:0] hid_b,
    input  logic [B_HIDDEN*undertone_pkg::COEFF_BITS-1:0]           out_a,            // o[j] at index j
    input  logic [B_HIDDEN*undertone_pkg::COEFF_BITS-1:0]           out_b,
    output logic                                                    out_valid,
    output logic                                                    out_overflow,     // this frame's own bit, not the sticky one
    output logic [undertone_pkg::SCORE_SCORE_BITS-1:0]              out_score
);
    import undertone_pkg::*;

    localparam int W_HID   = SCORE_SCORE_BITS;                                    // the hidden value: the score field
    localparam int W_BTW   = SCORE_SCORE_BITS + 1;                                // between: its fold
    localparam int W_OUT   = COEFF_BITS + SCORE_SCORE_BITS - 2 + $clog2(B_HIDDEN + 1) + 1;   // the output sum
    // A shifted value is looked at in a width with at least one bit above the field's top bit.
    localparam int W_HEADX = (W_HEAD > W_HID) ? W_HEAD : W_HID + 1;
    localparam int W_OUTX  = (W_OUT  > W_HID) ? W_OUT  : W_HID + 1;
    localparam int NHID    = B_HIDDEN * B_FILTERS;

    logic                          h0_valid, h1_valid, h2_valid, h3_valid;
    logic                          h0_sel,   h1_sel,   h2_sel;
    logic                          h2_ovf,   h3_ovf;
    logic [B_FILTERS*W_POOL-1:0]   h0_z;
    logic [NHID*W_HEAD-1:0]        h1_prod;       // g[j][k] * z_k at index j*B_FILTERS + k
    logic [B_HIDDEN*W_BTW-1:0]     h2_b;          // b_j at index j
    logic [B_HIDDEN*W_OUT-1:0]     h3_prod;       // o[j] * b_j at index j

    // h0: the inputs
    always @(posedge clk) begin : st_h0
        if (rst) begin
            h0_valid <= 1'b0;
            h0_sel   <= 1'b0;
            h0_z     <= '0;
        end else begin
            h0_valid <= in_valid;
            if (in_valid) begin
                h0_sel <= in_sel;
                h0_z   <= in_z;
            end
        end
    end

    // h1: the hidden products, under the frame's own bank
    always @(posedge clk) begin : st_h1
        logic signed [COEFF_BITS-1:0] gw;
        logic signed [W_POOL-1:0]     zk;
        logic signed [W_HEAD-1:0]     gx, zx, px;
        if (rst) begin
            h1_valid <= 1'b0;
            h1_sel   <= 1'b0;
            h1_prod  <= '0;
        end else begin
            h1_valid <= h0_valid;
            if (h0_valid) begin
                h1_sel <= h0_sel;
                for (int j = 0; j < B_HIDDEN; j++) begin
                    for (int k = 0; k < B_FILTERS; k++) begin
                        gw = h0_sel ? $signed(hid_b[(j*B_FILTERS + k)*COEFF_BITS +: COEFF_BITS])
                                    : $signed(hid_a[(j*B_FILTERS + k)*COEFF_BITS +: COEFF_BITS]);
                        zk = $signed(h0_z[k*W_POOL +: W_POOL]);
                        gx = gw;                        // sign-extended to the hidden sum's width
                        zx = zk;
                        px = gx * zx;
                        h1_prod[(j*B_FILTERS + k)*W_HEAD +: W_HEAD] <= px;
                    end
                end
            end
        end
    end

    // h2: the hidden sum, the first rounding, the fit, between
    always @(posedge clk) begin : st_h2
        logic signed [W_HEAD-1:0]  u;
        logic signed [W_HEADX-1:0] ux, us;
        logic signed [W_HID-1:0]   t;
        logic signed [W_BTW-1:0]   tx, b;
        logic [7:0]                q;
        logic                      abs_on, ovf;
        if (rst) begin
            h2_valid <= 1'b0;
            h2_sel   <= 1'b0;
            h2_ovf   <= 1'b0;
            h2_b     <= '0;
        end else begin
            h2_valid <= h1_valid;
            if (h1_valid) begin
                h2_sel <= h1_sel;
                q      = cfg_no_hidden ? cfg_score_shift : cfg_hidden_shift;
                abs_on = cfg_no_hidden ? 1'b0 : cfg_between_abs;
                ovf    = 1'b0;
                for (int j = 0; j < B_HIDDEN; j++) begin
                    u = '0;
                    for (int k = 0; k < B_FILTERS; k++) begin
                        u = u + $signed(h1_prod[(j*B_FILTERS + k)*W_HEAD +: W_HEAD]);
                    end
                    ux = u;                             // sign-extended
                    us = ux >>> q;                      // ux is signed: the shift is arithmetic, toward minus infinity
                    // It fits the field when every bit from the field's top bit up is the same.
                    if (!((&us[W_HEADX-1:W_HID-1]) || !(|us[W_HEADX-1:W_HID-1]))) ovf = 1'b1;
                    t  = us[W_HID-1:0];                 // the field's bits: the value modulo 2^W_HID
                    tx = t;                             // sign-extended to between's width
                    b  = (abs_on && t[W_HID-1]) ? -tx : tx;
                    h2_b[j*W_BTW +: W_BTW] <= b;
                end
                h2_ovf <= ovf;
            end
        end
    end

    // h3: the output products, under the frame's own bank
    always @(posedge clk) begin : st_h3
        logic signed [COEFF_BITS-1:0] ow;
        logic signed [W_OUT-1:0]      ox, bx, px;
        if (rst) begin
            h3_valid <= 1'b0;
            h3_ovf   <= 1'b0;
            h3_prod  <= '0;
        end else begin
            h3_valid <= h2_valid;
            if (h2_valid) begin
                h3_ovf <= h2_ovf;
                for (int j = 0; j < B_HIDDEN; j++) begin
                    ow = h2_sel ? $signed(out_b[j*COEFF_BITS +: COEFF_BITS])
                                : $signed(out_a[j*COEFF_BITS +: COEFF_BITS]);
                    ox = ow;                            // sign-extended to the output sum's width
                    if (cfg_no_hidden) ox = (j == 0) ? 1 : 0;   // the one route: a head weight of 1 on unit 0
                    bx = $signed(h2_b[j*W_BTW +: W_BTW]);
                    px = ox * bx;
                    h3_prod[j*W_OUT +: W_OUT] <= px;
                end
            end
        end
    end

    // h4: the output sum, the second rounding, the fit: the score
    always @(posedge clk) begin : st_h4
        logic signed [W_OUT-1:0]  a;
        logic signed [W_OUTX-1:0] ax, ash;
        logic [7:0]               s;
        if (rst) begin
            out_valid    <= 1'b0;
            out_overflow <= 1'b0;
            out_score    <= '0;
        end else begin
            out_valid <= h3_valid;
            if (h3_valid) begin
                s = cfg_no_hidden ? 8'd0 : cfg_score_shift;
                a = '0;
                for (int j = 0; j < B_HIDDEN; j++) begin
                    a = a + $signed(h3_prod[j*W_OUT +: W_OUT]);
                end
                ax  = a;                                // sign-extended
                ash = ax >>> s;                         // arithmetic, toward minus infinity
                out_overflow <= h3_ovf || !((&ash[W_OUTX-1:W_HID-1]) || !(|ash[W_OUTX-1:W_HID-1]));
                out_score    <= ash[W_HID-1:0];
            end
        end
    end
endmodule

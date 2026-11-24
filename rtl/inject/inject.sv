// The injector: adds known pulses to a stream, as model/inject.py defines it.
//
// A truth record (index, pulse_id, amplitude_num, amplitude_den) means: the
// pulse of that id, scaled by amplitude_num / amplitude_den, is added to EVERY
// channel, its first sample at stream index `index`. What is added at index + j
// is
//
//     delta[j] = pulse[j] * amplitude_num / amplitude_den,
//                rounded to the nearest integer, a tie to the even one
//
// and the frame out is the frame in plus delta[j] in every channel. A sum
// outside the sample's range is REFUSED at that frame, INJECT_RANGE: that frame
// is not offered and no later one is. Nothing is clipped and nothing wraps.
//
// THE STREAM. A frame is taken at every rising edge where in_valid is high,
// one a clock if they come so, and is offered LATENCY clocks later:
// 5 + (PULSE_SAMPLE_BITS + the numerator's bits - 1), which is 52. The registers
// on the way: the frame and its index; the pulse's sample and the record's two
// numbers; the product, as a sign and a magnitude; one divider stage for each
// bit of the quotient; the rounding; the sum and the range check. A frame with
// no pulse on it goes the same way and has 0 added.
//
// THE DIVISION takes every denominator a truth record can carry. It is a
// restoring division of the product's magnitude, one quotient bit a stage, a
// new division entering at every clock. Rounding the magnitude and putting the
// sign back is the model's floor-and-bump exactly: half to even is odd-symmetric.
//
// THE SCHEDULE. Truth records are written through four rows, one field a row
// (inj_truth_index is two words); THE WRITE OF THE DENOMINATOR OFFERS THE
// RECORD. They are written in stream order into a store of MAX_INJECT_PENDING,
// and a record leaves the store when its last sample has been added. Each is
// checked as it is offered, by the model's rule in the model's order, and a
// record that is refused ENDS THE RUN: no frame is offered from then on.
//     the pulse_id word does not fit its field, or the
//     denominator is 0                                     RECORD_FIELD
//     the pulse_id names no declared pulse                 PULSE_UNKNOWN
//     it starts before the end of the record before it,
//     or before the frame the injector has reached         INJECT_OVERLAP
//     the store is full                                    INJECT_PENDING
// A record offered after the run has ended is REGISTER_ACCESS.
//
// THE REGISTERS are the block `inject` of the definition, on the register port
// every block has. Outside its block this module does nothing. Inside it:
//     inj_frame      two words: the index the next frame taken will have. The
//                    write of its upper word empties the store and the
//                    pipeline, clears the refusal and begins a run there.
//                    After rst the index is 0 and nothing need be written
//     inj_refusal    the first refusal since it was cleared; a write of 0
//                    clears it, anything else is REGISTER_ACCESS. Clearing it
//                    does not begin a run: only inj_frame does
//     inj_pending    how many records the store holds
//     cap_inject_pending   how many it can hold
// A write to a read-only row, to an offset that holds no row, or to one that is
// not a multiple of the word's bytes is REGISTER_ACCESS, and the run goes on.
//
// TRUTH ISOLATION. This module's outputs are out_valid, out_frame and
// reg_rdata, and no other. A truth record reaches out_frame only through the
// adder; out_valid only as a refusal that ends the run; reg_rdata as
// inj_refusal and inj_pending. The truth rows are write-only. out_frame is
// CHANNELS * SAMPLE_BITS bits of samples and carries nothing else.
//
// WHAT IT DOES NOT DO, each a stated limit of docs/rtl/source.md: it does not
// know how long the stream is, so INJECT_PAST_END and the injector's
// STREAM_LENGTH are the host library's; it knows one pulse, e0, by name; the
// refusal register holds the FIRST refusal, so a run that ends after an
// uncleared REGISTER_ACCESS ends with that number there; it has never been
// synthesised.
`timescale 1ns / 1ps

module inject #(
    parameter int SAMPLE_BITS = 16,
    parameter int CHANNELS    = 1
) (
    input  logic                                       clk,
    input  logic                                       rst,        // synchronous, active high
    input  logic                                       reg_valid,
    input  logic                                       reg_we,
    input  logic [undertone_pkg::BUS_ADDRESS_BITS-1:0] reg_addr,
    input  logic [undertone_pkg::BUS_WORD_BITS-1:0]    reg_wdata,
    output logic [undertone_pkg::BUS_WORD_BITS-1:0]    reg_rdata,
    input  logic                                       in_valid,
    input  logic [CHANNELS*SAMPLE_BITS-1:0]            in_frame,   // channel c at [c*SAMPLE_BITS +: SAMPLE_BITS]
    output logic                                       out_valid,
    output logic [CHANNELS*SAMPLE_BITS-1:0]            out_frame
);
    import undertone_pkg::*;

    localparam int W         = CHANNELS * SAMPLE_BITS;
    localparam int NUM_BITS  = TRUTH_AMPLITUDE_NUM_BITS;
    localparam int DEN_BITS  = TRUTH_AMPLITUDE_DEN_BITS;
    localparam int PROD_BITS = PULSE_SAMPLE_BITS + NUM_BITS;    // the product, signed
    localparam int Q         = PROD_BITS - 1;                   // its magnitude, and so the quotient
    localparam int PTR_BITS  = $clog2(MAX_INJECT_PENDING);
    localparam int SMAX      = (1 << (SAMPLE_BITS - 1)) - 1;
    localparam int SMIN      = -(1 << (SAMPLE_BITS - 1));

    // Every width below is the package's. What stays typed, and why: CODE_BITS, the byte a refusal's
    // number fits by the definition's own rule, for which it generates no width; and the 8 bits that
    // index a pulse's samples, which hold any length to 255.
    localparam int CODE_BITS  = 8;
    localparam int WORD_BYTES = BUS_WORD_BITS / 8;
    localparam int INDEX_BITS = TRUTH_INDEX_BITS;

    localparam logic [BUS_WORD_BITS-1:0] WORD_ZERO = '0;
    localparam logic [INDEX_BITS-1:0]    INDEX_ONE = {{(INDEX_BITS-1){1'b0}}, 1'b1};
    localparam logic [DEN_BITS-1:0]      DEN_ONE   = {{(DEN_BITS-1){1'b0}}, 1'b1};

    localparam logic [CODE_BITS-1:0] CODE_NONE           = REFUSAL_NONE;
    localparam logic [CODE_BITS-1:0] CODE_RECORD_FIELD   = REFUSAL_RECORD_FIELD;
    localparam logic [CODE_BITS-1:0] CODE_PULSE_UNKNOWN  = REFUSAL_PULSE_UNKNOWN;
    localparam logic [CODE_BITS-1:0] CODE_INJECT_OVERLAP = REFUSAL_INJECT_OVERLAP;
    localparam logic [CODE_BITS-1:0] CODE_INJECT_PENDING = REFUSAL_INJECT_PENDING;
    localparam logic [CODE_BITS-1:0] CODE_INJECT_RANGE   = REFUSAL_INJECT_RANGE;
    localparam logic [CODE_BITS-1:0] CODE_ACCESS         = REFUSAL_REGISTER_ACCESS;

    // A definition whose rows no longer fit this module stops every run at time zero, by name: the index is
    // taken as a lower and an upper word, and each other field of a truth record as one word.
    initial begin
        if (REG_INJ_TRUTH_INDEX_WORDS != 2 || REG_INJ_FRAME_WORDS != 2
                || REG_INJ_TRUTH_INDEX_WORDS * BUS_WORD_BITS != INDEX_BITS
                || REG_INJ_FRAME_WORDS * BUS_WORD_BITS != INDEX_BITS
                || NUM_BITS != BUS_WORD_BITS || DEN_BITS != BUS_WORD_BITS || TRUTH_PULSE_ID_BITS > BUS_WORD_BITS) begin
            $display("inject: DEFINITION-MISMATCH: a truth record's fields no longer fit the rows that carry them");
            $finish;
        end
    end

    // The pulse e0, sample j, from the generated package's sixty-four integers.
    function automatic logic signed [PULSE_SAMPLE_BITS-1:0] e0_sample(input logic [7:0] j);
        case (j)
            8'd0:  e0_sample = PULSE_E0_SAMPLE_0;
            8'd1:  e0_sample = PULSE_E0_SAMPLE_1;
            8'd2:  e0_sample = PULSE_E0_SAMPLE_2;
            8'd3:  e0_sample = PULSE_E0_SAMPLE_3;
            8'd4:  e0_sample = PULSE_E0_SAMPLE_4;
            8'd5:  e0_sample = PULSE_E0_SAMPLE_5;
            8'd6:  e0_sample = PULSE_E0_SAMPLE_6;
            8'd7:  e0_sample = PULSE_E0_SAMPLE_7;
            8'd8:  e0_sample = PULSE_E0_SAMPLE_8;
            8'd9:  e0_sample = PULSE_E0_SAMPLE_9;
            8'd10: e0_sample = PULSE_E0_SAMPLE_10;
            8'd11: e0_sample = PULSE_E0_SAMPLE_11;
            8'd12: e0_sample = PULSE_E0_SAMPLE_12;
            8'd13: e0_sample = PULSE_E0_SAMPLE_13;
            8'd14: e0_sample = PULSE_E0_SAMPLE_14;
            8'd15: e0_sample = PULSE_E0_SAMPLE_15;
            8'd16: e0_sample = PULSE_E0_SAMPLE_16;
            8'd17: e0_sample = PULSE_E0_SAMPLE_17;
            8'd18: e0_sample = PULSE_E0_SAMPLE_18;
            8'd19: e0_sample = PULSE_E0_SAMPLE_19;
            8'd20: e0_sample = PULSE_E0_SAMPLE_20;
            8'd21: e0_sample = PULSE_E0_SAMPLE_21;
            8'd22: e0_sample = PULSE_E0_SAMPLE_22;
            8'd23: e0_sample = PULSE_E0_SAMPLE_23;
            8'd24: e0_sample = PULSE_E0_SAMPLE_24;
            8'd25: e0_sample = PULSE_E0_SAMPLE_25;
            8'd26: e0_sample = PULSE_E0_SAMPLE_26;
            8'd27: e0_sample = PULSE_E0_SAMPLE_27;
            8'd28: e0_sample = PULSE_E0_SAMPLE_28;
            8'd29: e0_sample = PULSE_E0_SAMPLE_29;
            8'd30: e0_sample = PULSE_E0_SAMPLE_30;
            8'd31: e0_sample = PULSE_E0_SAMPLE_31;
            8'd32: e0_sample = PULSE_E0_SAMPLE_32;
            8'd33: e0_sample = PULSE_E0_SAMPLE_33;
            8'd34: e0_sample = PULSE_E0_SAMPLE_34;
            8'd35: e0_sample = PULSE_E0_SAMPLE_35;
            8'd36: e0_sample = PULSE_E0_SAMPLE_36;
            8'd37: e0_sample = PULSE_E0_SAMPLE_37;
            8'd38: e0_sample = PULSE_E0_SAMPLE_38;
            8'd39: e0_sample = PULSE_E0_SAMPLE_39;
            8'd40: e0_sample = PULSE_E0_SAMPLE_40;
            8'd41: e0_sample = PULSE_E0_SAMPLE_41;
            8'd42: e0_sample = PULSE_E0_SAMPLE_42;
            8'd43: e0_sample = PULSE_E0_SAMPLE_43;
            8'd44: e0_sample = PULSE_E0_SAMPLE_44;
            8'd45: e0_sample = PULSE_E0_SAMPLE_45;
            8'd46: e0_sample = PULSE_E0_SAMPLE_46;
            8'd47: e0_sample = PULSE_E0_SAMPLE_47;
            8'd48: e0_sample = PULSE_E0_SAMPLE_48;
            8'd49: e0_sample = PULSE_E0_SAMPLE_49;
            8'd50: e0_sample = PULSE_E0_SAMPLE_50;
            8'd51: e0_sample = PULSE_E0_SAMPLE_51;
            8'd52: e0_sample = PULSE_E0_SAMPLE_52;
            8'd53: e0_sample = PULSE_E0_SAMPLE_53;
            8'd54: e0_sample = PULSE_E0_SAMPLE_54;
            8'd55: e0_sample = PULSE_E0_SAMPLE_55;
            8'd56: e0_sample = PULSE_E0_SAMPLE_56;
            8'd57: e0_sample = PULSE_E0_SAMPLE_57;
            8'd58: e0_sample = PULSE_E0_SAMPLE_58;
            8'd59: e0_sample = PULSE_E0_SAMPLE_59;
            8'd60: e0_sample = PULSE_E0_SAMPLE_60;
            8'd61: e0_sample = PULSE_E0_SAMPLE_61;
            8'd62: e0_sample = PULSE_E0_SAMPLE_62;
            8'd63: e0_sample = PULSE_E0_SAMPLE_63;
            default: e0_sample = '0;
        endcase
    endfunction

    // ---- the registers, and the store ----
    logic [INDEX_BITS-1:0]    n;        // the index the next frame taken will have
    logic [BUS_WORD_BITS-1:0] frame_low;
    logic [INDEX_BITS-1:0]    t_index;
    logic [BUS_WORD_BITS-1:0] t_pulse;
    logic [BUS_WORD_BITS-1:0] t_num;
    logic [PTR_BITS:0] wr_ptr, rd_ptr, count;
    logic [INDEX_BITS:0] free_from;     // the end of the last record taken: one bit more than an index
    logic [CODE_BITS-1:0] refusal;
    logic              dead;            // the run has ended on a refusal

    logic [INDEX_BITS-1:0] st_index [0:MAX_INJECT_PENDING-1];
    logic [NUM_BITS-1:0] st_num   [0:MAX_INJECT_PENDING-1];
    logic [DEN_BITS-1:0] st_den   [0:MAX_INJECT_PENDING-1];

    logic                head_valid;
    logic [INDEX_BITS-1:0] head_index;
    logic [NUM_BITS-1:0] head_num;
    logic [DEN_BITS-1:0] head_den;

    assign count      = wr_ptr - rd_ptr;
    assign head_valid = (wr_ptr != rd_ptr);
    assign head_index = st_index[rd_ptr[PTR_BITS-1:0]];
    assign head_num   = st_num[rd_ptr[PTR_BITS-1:0]];
    assign head_den   = st_den[rd_ptr[PTR_BITS-1:0]];

    // ---- the pipeline ----
    logic                                s1_valid, s2_valid, r_valid;
    logic [W-1:0]                        s1_frame, s2_frame, r_frame;
    logic [INDEX_BITS-1:0]               s1_index;
    logic signed [PULSE_SAMPLE_BITS-1:0] s2_p;
    logic signed [NUM_BITS-1:0]          s2_num;
    logic [DEN_BITS-1:0]                 s2_den;

    logic [INDEX_BITS-1:0] diff;
    logic        active;
    assign diff   = s1_index - head_index;
    assign active = s1_valid && head_valid && (s1_index >= head_index) && (diff < PULSE_E0_LENGTH);

    logic signed [PROD_BITS-1:0] prod;
    logic        [PROD_BITS-1:0] prod_mag;
    assign prod     = s2_p * s2_num;
    assign prod_mag = prod[PROD_BITS-1] ? (~prod + 1'b1) : prod;

    // Stage 0 holds the product; stage k, 1 to Q, the division after k quotient bits.
    logic                dv_valid [0:Q];
    logic [W-1:0]        dv_frame [0:Q];
    logic                dv_neg   [0:Q];
    logic [Q-1:0]        dv_num   [0:Q];
    logic [DEN_BITS-1:0] dv_den   [0:Q];
    logic [DEN_BITS-1:0] dv_rem   [0:Q];
    logic [Q-1:0]        dv_quo   [0:Q];

    logic [Q-1:0]        q_last;
    logic [DEN_BITS-1:0] rem_last, den_last;
    logic                neg_last;
    assign q_last   = dv_quo[Q];
    assign rem_last = dv_rem[Q];
    assign den_last = dv_den[Q];
    assign neg_last = dv_neg[Q];

    // The rounding: one more when twice the remainder exceeds the denominator, or equals it with the quotient odd.
    logic [DEN_BITS:0]           twice, den_wide;
    logic                        bump;
    logic [PROD_BITS-1:0]        magr;
    logic signed [PROD_BITS-1:0] delta, r_delta;
    assign twice    = {rem_last, 1'b0};
    assign den_wide = {1'b0, den_last};
    assign bump     = (twice > den_wide) || ((twice == den_wide) && q_last[0]);
    assign magr     = {1'b0, q_last} + {{(PROD_BITS-1){1'b0}}, bump};
    assign delta = neg_last ? (~magr + 1'b1) : magr;

    // The sum, in every channel, and whether any leaves the range.
    logic signed [PROD_BITS:0] s;
    logic [W-1:0]              sum_frame;
    logic                      any_bad, range_refuse;

    always_comb begin
        any_bad   = 1'b0;
        sum_frame = '0;
        for (int c = 0; c < CHANNELS; c++) begin
            s = $signed(r_frame[c*SAMPLE_BITS +: SAMPLE_BITS]) + r_delta;
            if (s < SMIN || s > SMAX) any_bad = 1'b1;
            sum_frame[c*SAMPLE_BITS +: SAMPLE_BITS] = s[SAMPLE_BITS-1:0];
        end
    end
    assign range_refuse = r_valid && !dead && any_bad;

    // The refusal this clock earns, 0 for none: a refused write's, or a sum out of range.
    logic [CODE_BITS-1:0] wr_code, new_code;
    assign new_code = (wr_code != CODE_NONE) ? wr_code : (range_refuse ? CODE_INJECT_RANGE : CODE_NONE);

    // ---- what a write is ----
    logic [BUS_ADDRESS_BITS:0] addr;        // one bit more than an address, so that a block's END compares rightly
    logic        in_block, wr, rd;
    logic        wr_run_refused, wr_frame_low, wr_begin, wr_index_low, wr_index_high, wr_pulse, wr_num, wr_push, wr_clear;

    assign addr     = {1'b0, reg_addr};
    assign in_block = (addr >= BLOCK_INJECT_FIRST) && (addr < BLOCK_INJECT_END);
    assign wr       = reg_valid && reg_we && in_block;
    assign rd       = reg_valid && !reg_we;

    always_comb begin
        wr_code        = CODE_NONE;
        wr_run_refused = 1'b0;
        wr_frame_low   = 1'b0;
        wr_begin       = 1'b0;
        wr_index_low   = 1'b0;
        wr_index_high  = 1'b0;
        wr_pulse       = 1'b0;
        wr_num         = 1'b0;
        wr_push        = 1'b0;
        wr_clear       = 1'b0;
        if (wr) begin
            case (addr)
                REG_INJ_FRAME_OFFSET:               wr_frame_low  = 1'b1;
                REG_INJ_FRAME_OFFSET + WORD_BYTES:           wr_begin      = 1'b1;
                REG_INJ_TRUTH_INDEX_OFFSET:         wr_index_low  = 1'b1;
                REG_INJ_TRUTH_INDEX_OFFSET + WORD_BYTES:     wr_index_high = 1'b1;
                REG_INJ_TRUTH_PULSE_ID_OFFSET:      wr_pulse      = 1'b1;
                REG_INJ_TRUTH_AMPLITUDE_NUM_OFFSET: wr_num        = 1'b1;
                REG_INJ_TRUTH_AMPLITUDE_DEN_OFFSET: begin
                    // The offer. The model's checks, in the model's order.
                    if (dead) begin
                        wr_code = CODE_ACCESS;
                    end else if ((t_pulse >> TRUTH_PULSE_ID_BITS) != WORD_ZERO || reg_wdata == WORD_ZERO) begin
                        wr_code        = CODE_RECORD_FIELD;
                        wr_run_refused = 1'b1;
                    end else if (t_pulse != PULSE_E0_ID) begin
                        wr_code        = CODE_PULSE_UNKNOWN;
                        wr_run_refused = 1'b1;
                    end else if ({1'b0, t_index} < free_from || t_index < n) begin
                        wr_code        = CODE_INJECT_OVERLAP;
                        wr_run_refused = 1'b1;
                    end else if (count == MAX_INJECT_PENDING) begin
                        wr_code        = CODE_INJECT_PENDING;
                        wr_run_refused = 1'b1;
                    end else begin
                        wr_push = 1'b1;
                    end
                end
                REG_INJ_REFUSAL_OFFSET: begin
                    if (reg_wdata == WORD_ZERO) wr_clear = 1'b1;
                    else                    wr_code  = CODE_ACCESS;
                end
                default:                            wr_code = CODE_ACCESS;      // read-only, no row, or not a word's offset
            endcase
        end
    end

    always_ff @(posedge clk) begin
        if (rst) begin
            n         <= '0;
            frame_low <= '0;
            t_index   <= '0;
            t_pulse   <= '0;
            t_num     <= '0;
            wr_ptr    <= '0;
            rd_ptr    <= '0;
            free_from <= '0;
            refusal   <= CODE_NONE;
            dead      <= 1'b0;
            s1_valid  <= 1'b0;
            s1_frame  <= '0;
            s1_index  <= '0;
            s2_valid  <= 1'b0;
            s2_frame  <= '0;
            s2_p      <= '0;
            s2_num    <= '0;
            s2_den    <= DEN_ONE;
            r_valid   <= 1'b0;
            r_frame   <= '0;
            r_delta   <= '0;
            reg_rdata <= '0;
            out_valid <= 1'b0;
            out_frame <= '0;
            for (int k = 0; k <= Q; k++) begin
                dv_valid[k] <= 1'b0;
                dv_frame[k] <= '0;
                dv_neg[k]   <= 1'b0;
                dv_num[k]   <= '0;
                dv_den[k]   <= DEN_ONE;
                dv_rem[k]   <= '0;
                dv_quo[k]   <= '0;
            end
        end else begin
            out_valid <= 1'b0;

            // ---- the frame and its index ----
            s1_valid <= in_valid;
            s1_frame <= in_frame;
            s1_index <= n;
            if (in_valid) n <= n + INDEX_ONE;

            // ---- the pulse's sample and the record's two numbers ----
            s2_valid <= s1_valid;
            s2_frame <= s1_frame;
            s2_p     <= active ? e0_sample(diff[7:0]) : {PULSE_SAMPLE_BITS{1'b0}};
            s2_num   <= active ? head_num : {NUM_BITS{1'b0}};
            s2_den <= active ? head_den : DEN_ONE;
            if (active && diff == PULSE_E0_LENGTH - 1) rd_ptr <= rd_ptr + 1'b1;     // its last sample: the record leaves

            // ---- the product, as a sign and a magnitude ----
            dv_valid[0] <= s2_valid;
            dv_frame[0] <= s2_frame;
            dv_neg[0]   <= prod[PROD_BITS-1];
            dv_num[0]   <= prod_mag[Q-1:0];
            dv_den[0]   <= s2_den;
            dv_rem[0]   <= '0;
            dv_quo[0]   <= '0;

            // ---- the division, one quotient bit a stage ----
            for (int k = 1; k <= Q; k++) begin
                dv_valid[k] <= dv_valid[k-1];
                dv_frame[k] <= dv_frame[k-1];
                dv_neg[k]   <= dv_neg[k-1];
                dv_den[k]   <= dv_den[k-1];
                dv_num[k]   <= {dv_num[k-1][Q-2:0], 1'b0};
                if ({dv_rem[k-1], dv_num[k-1][Q-1]} >= {1'b0, dv_den[k-1]}) begin
                    dv_rem[k] <= {dv_rem[k-1], dv_num[k-1][Q-1]} - {1'b0, dv_den[k-1]};
                    dv_quo[k] <= {dv_quo[k-1][Q-2:0], 1'b1};
                end else begin
                    dv_rem[k] <= {dv_rem[k-1][DEN_BITS-2:0], dv_num[k-1][Q-1]};
                    dv_quo[k] <= {dv_quo[k-1][Q-2:0], 1'b0};
                end
            end

            // ---- the rounding ----
            r_valid <= dv_valid[Q];
            r_frame <= dv_frame[Q];
            r_delta <= delta;

            // ---- the sum and the range check ----
            if (r_valid && !dead && !any_bad) begin
                out_valid <= 1'b1;
                out_frame <= sum_frame;
            end

            // ---- a refusal that ends the run, and the refusal register: the first refusal stands ----
            if (wr_run_refused || range_refuse) dead <= 1'b1;
            if (wr_clear) begin
                refusal <= CODE_NONE;
            end else if (refusal == CODE_NONE && new_code != CODE_NONE) begin
                refusal <= new_code;
            end

            // ---- writes that are taken ----
            if (wr_frame_low)  frame_low      <= reg_wdata;
            if (wr_index_low)  t_index[BUS_WORD_BITS-1:0]          <= reg_wdata;
            if (wr_index_high) t_index[INDEX_BITS-1:BUS_WORD_BITS] <= reg_wdata;
            if (wr_pulse)      t_pulse        <= reg_wdata;
            if (wr_num)        t_num          <= reg_wdata;
            if (wr_push) begin
                st_index[wr_ptr[PTR_BITS-1:0]] <= t_index;
                st_num[wr_ptr[PTR_BITS-1:0]]   <= t_num;
                st_den[wr_ptr[PTR_BITS-1:0]]   <= reg_wdata;
                wr_ptr    <= wr_ptr + 1'b1;
                free_from <= {1'b0, t_index} + PULSE_E0_LENGTH;
            end

            // ---- reads ----
            if (rd) begin
                if (!in_block) begin
                    reg_rdata <= '0;
                end else begin
                    case (addr)
                        REG_INJ_PENDING_OFFSET:        reg_rdata <= {{(BUS_WORD_BITS - PTR_BITS - 1){1'b0}}, count};
                        REG_INJ_REFUSAL_OFFSET:        reg_rdata <= {{(BUS_WORD_BITS - CODE_BITS){1'b0}}, refusal};
                        REG_CAP_INJECT_PENDING_OFFSET: reg_rdata <= MAX_INJECT_PENDING;
                        default:                       reg_rdata <= '0;
                    endcase
                end
            end

            // ---- a new run: last, so that it rules ----
            if (wr_begin) begin
                n         <= {reg_wdata, frame_low};
                wr_ptr    <= '0;
                rd_ptr    <= '0;
                free_from <= '0;
                refusal   <= CODE_NONE;
                dead      <= 1'b0;
                s1_valid  <= 1'b0;
                s2_valid  <= 1'b0;
                r_valid   <= 1'b0;
                out_valid <= 1'b0;
                for (int k = 0; k <= Q; k++) dv_valid[k] <= 1'b0;
            end
        end
    end
endmodule

// The learner of phase B, beside the detector core: model/learner.py in the fabric.
//
// The reference model is the authority: model/learner.py defines every count, every window and every
// coefficient this makes, and docs/rtl/learn.md says how the benches hold it to the model.
//
// WHAT IT DOES. It watches the frames the core takes and keeps the last B_TAPS of them. It is handed the
// index of each truth record the injector takes into its store, and nothing else of the record. For a
// record at j, with p the record before it and q the one after, and T the core's running taps:
//
//     label 0   frames j-T .. j-1   judged when the core's next index is j
//     label 1   frames j .. j+T-1   judged when the core's next index is j + T
//
// a window is taken (added to its label's sum, its count up by one) or skipped and counted:
//
//     label 0   START  j < T      BUSY  p exists and j - p < 2T      FULL  its count is at its most
//     label 1   BUSY   p exists and j - p < T, or q exists and q - j < T      FULL  as label 0's
//
// At an index u the host names it makes the set D[c][k] = S1[k][c] n0 - S0[k][c] n1, quantised over the
// whole set (peak to COEFF_MAX, half to even), and writes it, with a head weight of 1, into the core's
// shadow through the core's own register port. The update is FINISHED when the core's next index is
// u + B_UPDATE_FRAMES and every write has been taken.
//
// WHEN, IN CLOCKS (docs/rtl/learn.md, sections 5 and 6):
//   - A label-0 window is judged at the first edge at which the core runs, its next index as the frame at
//     that edge leaves it is j, and the record is known; a label-1 window at the edge the index becomes
//     j + T. A truth record pushed at an edge is known at that edge, before its frame.
//   - A taken window is added a tap a clock, from the clock after its judgement, every channel at once.
//   - The update at u is MADE at the first edge at which the next index is u or more and either a record at
//     u or later is known or frame u has been taken: then no record at u can still come.
//   - THE SNAPSHOT is a copy of the sums, a tap a clock. It starts two clocks after the edge the update is
//     made at when the next index there is u (that edge's windows are the update's, and their adds lead by
//     a clock), and one clock after when it is u + 1 (that edge's windows are not, and a read sees the
//     value before the edge that writes it). The counts are taken at that edge likewise.
//   - Then pass A: D from the copy and its peak. Then shadow_begin, and pass B: D again, the division and
//     the rounding, a coefficient written each time. Then the head weight.
//
// THE PORT (rtl/learn/learn_port.sv): the learner's writes go to the core's port in a clock where no host
// access is passed; while an update is unfinished the host's commit (commit_at's upper word), shadow_begin
// and shadow_data are held back and refused here, UPDATE_UNFINISHED.
//
// REFUSALS. A refused write changes nothing and latches the refusal's number in lrn_refusal; the first one
// since it was cleared is kept, a later one sets refused_again. The order of an update's checks is the
// chain of `wcode` below, read upward.
//
// EVERY OUTPUT IS A REGISTER, so that this module can be synthesised alone, out of context.
//
// WHAT IT DOES NOT DO, each a stated limit of docs/rtl/learn.md: it does not check the truth port's
// contract (strictly ascending indexes, none behind the core's next index, the store not overfull); it
// meets B_UPDATE_FRAMES only at the chain's rate; nothing here has met a synthesis tool.
`timescale 1ns / 1ps

module learn #(
    parameter int SAMPLE_BITS     = 16,
    parameter int CHANNELS        = 1,
    // the build's bounds: what this build can hold. None may pass the definition's.
    parameter int B_TAPS          = undertone_pkg::MAX_TAPS,
    parameter int B_COUNT_BITS    = undertone_pkg::LEARN_COUNT_BITS,
    parameter int B_UPDATE_FRAMES = undertone_pkg::LEARN_UPDATE_FRAMES
) (
    input  logic                                        clk,
    input  logic                                        rst,               // synchronous, active high
    // the frames offered to the core: the same wires as the core's in_valid and in_frame
    input  logic                                        in_valid,
    input  logic [CHANNELS*SAMPLE_BITS-1:0]             in_frame,
    // the core's state, as its registers hold it before this edge
    input  logic                                        core_running,
    input  logic [undertone_pkg::SCORE_INDEX_BITS-1:0]  core_next_index,
    input  logic [undertone_pkg::BUS_WORD_BITS-1:0]     core_taps,
    input  logic [undertone_pkg::BUS_WORD_BITS-1:0]     core_filters,
    input  logic [undertone_pkg::BUS_WORD_BITS-1:0]     core_rows,
    input  logic [undertone_pkg::BUS_WORD_BITS-1:0]     core_pool,
    input  logic [undertone_pkg::BUS_WORD_BITS-1:0]     core_score_shift,
    input  logic                                        core_rect_abs,
    input  logic                                        core_no_hidden,
    input  logic                                        core_commit,       // a commit is scheduled
    input  logic [undertone_pkg::SCORE_INDEX_BITS-1:0]  core_commit_at,
    input  logic                                        core_partial,      // a stream of weight words is begun and not whole
    input  logic                                        core_closed,       // the shadow is closed after a swap
    // a truth record taken by the injector at this edge: its index alone
    input  logic                                        truth_valid,
    input  logic [undertone_pkg::TRUTH_INDEX_BITS-1:0]  truth_index,
    // the host's register port, as every block sees it
    input  logic                                        reg_valid,
    input  logic                                        reg_we,
    input  logic [undertone_pkg::BUS_ADDRESS_BITS-1:0]  reg_addr,
    input  logic [undertone_pkg::BUS_WORD_BITS-1:0]     reg_wdata,
    output logic [undertone_pkg::BUS_WORD_BITS-1:0]     reg_rdata,
    // from learn_port, at this edge
    input  logic                                        port_hold,         // an update is named and not finished
    input  logic                                        port_intercept,    // the host's write is held back from the core
    input  logic                                        port_host,         // the host's access has the core's port
    // to learn_port
    output logic                                        hold_q,            // unfinished, unless a frame now finishes it
    output logic                                        hold_end_q,        // a frame taken now finishes it
    output logic                                        lw_valid,          // the learner's own write to the core's port
    output logic [undertone_pkg::BUS_ADDRESS_BITS-1:0]  lw_addr,
    output logic [undertone_pkg::BUS_WORD_BITS-1:0]     lw_wdata
);
    import undertone_pkg::*;

    // ------------------------------------------------------------------ widths: model.learner.widths, as closed forms
    // With N count bits a label takes at most 2^N - 1 windows, so a sum needs S + N bits, a product of a sum
    // and a count S + 2N, D = S1 n0 - S0 n1 one more, and |D|, the peak and a remainder S + 2N unsigned. For
    // N of 2 or more these are the fewest bits for the model's ranges (docs/rtl/learn.md, row L1).
    localparam int S      = SAMPLE_BITS;
    localparam int N      = B_COUNT_BITS;
    localparam int W_SUM  = S + N;
    localparam int W_D    = S + 2 * N + 1;
    localparam int W_MAG  = S + 2 * N;
    localparam int QB     = $clog2(COEFF_MAX + 1);              // a quotient's bits: |q| <= COEFF_MAX
    localparam int W_X    = W_MAG + QB;                         // |D| * COEFF_MAX
    localparam int WORD   = BUS_WORD_BITS;
    localparam int WBYTES = BUS_WORD_BITS / 8;
    localparam int IDX    = SCORE_INDEX_BITS;
    localparam int NSUM   = B_TAPS * CHANNELS;                  // tap k, channel c at k*CHANNELS + c
    localparam int TQ     = MAX_INJECT_PENDING + 4;             // the truth store (docs/rtl/learn.md, row L11)
    localparam int TQB    = $clog2(TQ);
    localparam int TB     = $clog2(B_TAPS + 1);
    localparam int AB     = (B_TAPS > 1) ? $clog2(B_TAPS) : 1;
    localparam int VB     = $clog2(NSUM + 2);
    localparam int CB     = (CHANNELS > 1) ? $clog2(CHANNELS) : 1;
    localparam int CODE_BITS = 8;                               // a refusal's number, as core.sv and inject.sv type it

    localparam logic [N-1:0]     COUNT_MAX = '1;
    localparam logic [IDX:0]     INDEX_TOP = {1'b0, {IDX{1'b1}}};    // the index field's most
    localparam logic [W_X-1:0]   CMAX      = COEFF_MAX;
    localparam logic [CODE_BITS-1:0] C_ACCESS     = REFUSAL_REGISTER_ACCESS;
    localparam logic [CODE_BITS-1:0] C_STOPPED    = REFUSAL_CORE_STOPPED;
    localparam logic [CODE_BITS-1:0] C_UNFINISHED = REFUSAL_UPDATE_UNFINISHED;
    localparam logic [CODE_BITS-1:0] C_SHAPE      = REFUSAL_SWAP_SHAPE;
    localparam logic [CODE_BITS-1:0] C_PENDING    = REFUSAL_SWAP_PENDING;
    localparam logic [CODE_BITS-1:0] C_INDEX      = REFUSAL_SWAP_INDEX;
    localparam logic [CODE_BITS-1:0] C_COUNT      = REFUSAL_WEIGHT_COUNT;
    localparam logic [CODE_BITS-1:0] C_QUANTISE   = REFUSAL_QUANTISE_INPUT;

    // the engine's states
    localparam logic [2:0] E_IDLE = 3'd0, E_COPY = 3'd1, E_PEAK = 3'd2, E_BEGIN = 3'd3, E_DIVIDE = 3'd4,
                           E_HEAD = 3'd5, E_END = 3'd6;

    initial begin
        if (B_TAPS < 1 || B_TAPS > MAX_TAPS || B_COUNT_BITS < 2 || B_COUNT_BITS > LEARN_COUNT_BITS
                || B_UPDATE_FRAMES < 1 || B_UPDATE_FRAMES > LEARN_UPDATE_FRAMES) begin
            $fatal(1, "learn: a build bound is outside the definition's, or is a count of 1 bit or an update time of 0");
        end
        if (REG_LRN_UPDATE_AT_WORDS != 2 || REG_LRN_COUNT0_WORDS != 1 || REG_LRN_COUNT1_WORDS != 1
                || REG_LRN_SKIP_START_WORDS != 2 || REG_LRN_SKIP_BUSY_WORDS != 2 || REG_LRN_SKIP_FULL_WORDS != 2
                || REG_LRN_MADE_WORDS != 2 || REG_LRN_UNMADE_WORDS != 2 || REG_LRN_EARLY_WORDS != 2
                || IDX != 2 * WORD || TRUTH_INDEX_BITS != IDX || N > WORD
                || COEFF_MAX > (1 << (COEFF_BITS - 1)) - 1 || REG_COMMIT_AT_WORDS != 2) begin
            $fatal(1, "learn: the register map no longer fits the learner's values");
        end
    end

    // ------------------------------------------------------------------ state
    // the delay buffer: the last B_TAPS frames the core took, frame f at slot f modulo B_TAPS
    logic [CHANNELS*S-1:0]   dbuf [0:B_TAPS-1];
    logic [AB-1:0]           bw;                   // the slot of the next frame taken
    // the live sums and their copy
    logic signed [W_SUM-1:0] sum0 [0:NSUM-1];
    logic signed [W_SUM-1:0] sum1 [0:NSUM-1];
    logic signed [W_SUM-1:0] cpy0 [0:NSUM-1];
    logic signed [W_SUM-1:0] cpy1 [0:NSUM-1];
    logic [N-1:0]            cnt0, cnt1;
    // the truth store: indexes in order; tw the next push, t0 the label-0 cursor, t1 the label-1 cursor
    logic [IDX-1:0]          tq [0:TQ-1];
    logic [TQB-1:0]          tw, t0, t1;
    logic [IDX-1:0]          last_idx, prev0, prev1;
    logic                    have_any, prev0_ok, prev1_ok;
    // the add of a taken window
    logic                    acc_on, acc_lab;
    logic [TB-1:0]           acc_k;
    logic [AB-1:0]           acc_a;
    // the update
    logic [WORD-1:0]         upd_lo;               // lrn_update_at's lower word, as written
    logic [IDX-1:0]          upd_u, upd_uf;
    logic                    upd_taken, upd_made, upd_done, upd_set;
    logic                    last_made, last_unmade;
    logic [N-1:0]            n0s, n1s;
    logic [2:0]              eng;
    logic                    cp_wait;
    logic [TB-1:0]           cp_k;
    // the D pipeline: operands, products, difference
    logic [VB-1:0]           is_n, got_n;
    logic [CB-1:0]           is_c;
    logic [TB-1:0]           is_k;
    logic                    da_v, db_v, dc_v;
    logic signed [W_D-1:0]   da_s0, da_s1, db_p0, db_p1, dc_d;
    logic [W_MAG-1:0]        peak;
    // pass B's one value held, and the divider
    logic                    bf_v, bf_neg;
    logic [W_MAG-1:0]        bf_mag;
    logic                    dv_on, dv_rnd, dv_neg;
    logic [7:0]              dv_i;
    logic [W_X-1:0]          dv_x;
    logic [W_MAG-1:0]        dv_r;
    logic [QB-1:0]           dv_q;
    logic [VB-1:0]           wr_n;                 // coefficient words handed to the write register
    // the latch and the counters
    logic [CODE_BITS-1:0]    refusal;
    logic                    refused_again;
    logic [63:0]             c_start, c_busy, c_full, c_made, c_unmade, c_early;
    logic [WORD-1:0]         h_start, h_busy, h_full, h_made, h_unmade, h_early;   // each upper word, held by a read of its lower

    // ------------------------------------------------------------------ the frame, the truth, the windows, the update, the writes
    always @(posedge clk) begin : ctl
        logic                    take, k0, k1, kq, fire0, fire1, o0_start, o0_busy, o0_full, o1_busy, o1_full;
        logic                    take0, take1, wfree, wtaken, issue, fin, make, named, qlatch, clear, again_n;
        logic                    w_blk, w_ulo, w_uhi, w_rfs, w_commit_hi, pend_n, shape_ok;
        logic                    x_access, x_stopped, x_unfinished, x_shape, x_pending, x_index, x_count;
        logic                    taken_n, done_n;
        logic [IDX-1:0]          idx_n, j0, j1, jq, u_new, uf_n;
        logic [IDX:0]            wide;
        logic [TQB-1:0]          tw1, t11, d0, dw;
        logic [AB-1:0]           bw_n, base;
        logic [TB-1:0]           T;
        logic [VB-1:0]           NV;
        logic [CODE_BITS-1:0]    wcode, ref_n;
        logic [N-1:0]            cnt0_n, cnt1_n;
        logic [W_MAG-1:0]        mag, peak_n;
        logic signed [W_D-1:0]   negd;
        logic [W_X-1:0]          xx, xs;
        logic [W_MAG:0]          tt, tr, twice;
        logic [QB:0]             qp;
        logic signed [WORD-1:0]  qw;
        logic [1:0]              add_busy, add_full;

        if (rst) begin
            bw <= '0;
            for (int i = 0; i < NSUM; i++) begin
                sum0[i] <= '0; sum1[i] <= '0; cpy0[i] <= '0; cpy1[i] <= '0;
            end
            cnt0 <= '0; cnt1 <= '0;
            tw <= '0; t0 <= '0; t1 <= '0;
            last_idx <= '0; prev0 <= '0; prev1 <= '0; have_any <= 1'b0; prev0_ok <= 1'b0; prev1_ok <= 1'b0;
            acc_on <= 1'b0; acc_lab <= 1'b0; acc_k <= '0; acc_a <= '0;
            upd_lo <= '0; upd_u <= '0; upd_uf <= '0;
            upd_taken <= 1'b0; upd_made <= 1'b0; upd_done <= 1'b0; upd_set <= 1'b0;
            last_made <= 1'b0; last_unmade <= 1'b0; n0s <= '0; n1s <= '0;
            eng <= E_IDLE; cp_wait <= 1'b0; cp_k <= '0;
            is_n <= '0; got_n <= '0; is_c <= '0; is_k <= '0;
            da_v <= 1'b0; db_v <= 1'b0; dc_v <= 1'b0;
            da_s0 <= '0; da_s1 <= '0; db_p0 <= '0; db_p1 <= '0; dc_d <= '0; peak <= '0;
            bf_v <= 1'b0; bf_neg <= 1'b0; bf_mag <= '0;
            dv_on <= 1'b0; dv_rnd <= 1'b0; dv_neg <= 1'b0; dv_i <= '0; dv_x <= '0; dv_r <= '0; dv_q <= '0;
            wr_n <= '0;
            lw_valid <= 1'b0; lw_addr <= '0; lw_wdata <= '0;
            refusal <= '0; refused_again <= 1'b0;
            c_start <= '0; c_busy <= '0; c_full <= '0; c_made <= '0; c_unmade <= '0; c_early <= '0;
            hold_q <= 1'b0; hold_end_q <= 1'b0;
        end else begin
            T     = core_taps[TB-1:0];
            NV    = T * CHANNELS;
            take  = in_valid && core_running;
            idx_n = core_next_index + (take ? 1 : 0);

            // ---- the frame into the delay buffer ----
            bw_n = bw;
            if (take) begin
                dbuf[bw] <= in_frame;
                bw_n = (bw == B_TAPS - 1) ? '0 : bw + 1'b1;
            end
            bw <= bw_n;

            // ---- the truth: a record pushed at this edge is known at this edge ----
            tw1 = (tw == TQ - 1) ? '0 : tw + 1'b1;
            t11 = (t1 == TQ - 1) ? '0 : t1 + 1'b1;
            d0  = (t0 >= t1) ? t0 - t1 : t0 + TQ - t1;          // how far the label-0 cursor is past the label-1 cursor
            dw  = (tw >= t1) ? tw - t1 : tw + TQ - t1;          // how many records are held
            k0  = (d0 < dw) || ((d0 == dw) && truth_valid);
            k1  = (dw != 0) || truth_valid;
            kq  = (dw > 1) || ((dw == 1) && truth_valid);
            j0  = (t0 == tw) ? truth_index : tq[t0];
            j1  = (t1 == tw) ? truth_index : tq[t1];
            jq  = (t11 == tw) ? truth_index : tq[t11];
            if (truth_valid) begin
                tq[tw]   <= truth_index;
                tw       <= tw1;
                last_idx <= truth_index;
                have_any <= 1'b1;
            end

            // ---- the judgements: label 0 of the record at t0, label 1 of the record at t1 ----
            fire0 = core_running && k0 && (j0 == idx_n);
            wide  = {1'b0, j1} + T;
            fire1 = core_running && k1 && (wide == {1'b0, idx_n});
            o0_start = (j0 < T);
            o0_busy  = prev0_ok && ((j0 - prev0) < 2 * T);
            o0_full  = (cnt0 == COUNT_MAX);
            o1_busy  = (prev1_ok && ((j1 - prev1) < T)) || (kq && ((jq - j1) < T));
            o1_full  = (cnt1 == COUNT_MAX);
            take0 = fire0 && !o0_start && !o0_busy && !o0_full;
            take1 = fire1 && !o1_busy && !o1_full;
            add_busy = (fire0 && !o0_start && o0_busy) + (fire1 && o1_busy);
            add_full = (fire0 && !o0_start && !o0_busy && o0_full) + (fire1 && !o1_busy && o1_full);
            if (fire0 && o0_start) c_start <= c_start + 1;
            c_busy <= c_busy + add_busy;
            c_full <= c_full + add_full;
            if (fire0) begin
                t0 <= (t0 == TQ - 1) ? '0 : t0 + 1'b1;
                prev0 <= j0; prev0_ok <= 1'b1;
            end
            if (fire1) begin
                t1 <= t11;
                prev1 <= j1; prev1_ok <= 1'b1;
            end
            cnt0_n = cnt0 + (take0 ? 1 : 0);
            cnt1_n = cnt1 + (take1 ? 1 : 0);
            cnt0 <= cnt0_n;
            cnt1 <= cnt1_n;

            // ---- the add: a tap a clock, every channel at once, from the clock after the judgement ----
            if (acc_on) begin
                for (int c = 0; c < CHANNELS; c++) begin
                    if (acc_lab)
                        sum1[acc_k*CHANNELS + c] <= sum1[acc_k*CHANNELS + c] + $signed(dbuf[acc_a][c*S +: S]);
                    else
                        sum0[acc_k*CHANNELS + c] <= sum0[acc_k*CHANNELS + c] + $signed(dbuf[acc_a][c*S +: S]);
                end
                acc_a <= (acc_a == B_TAPS - 1) ? '0 : acc_a + 1'b1;
                acc_k <= acc_k + 1'b1;
                if (acc_k == T - 1) acc_on <= 1'b0;
            end
            if (take0 || take1) begin
                // tap 0 is the window's oldest frame: T frames before the slot the next frame goes to
                base = (bw_n >= T) ? bw_n - T : bw_n + B_TAPS - T;
                acc_on  <= 1'b1;
                acc_lab <= take1;
                acc_k   <= '0;
                acc_a   <= base;
            end

            // ---- the write register: taken at an edge where no host access has the port ----
            wtaken = lw_valid && !port_host;
            wfree  = !lw_valid || wtaken;
            if (wtaken) lw_valid <= 1'b0;

            // ---- the finish: published at the edge the update stops being unfinished ----
            fin = upd_taken && !port_hold;
            qlatch = 1'b0;
            taken_n = upd_taken;
            done_n  = upd_done;
            if (fin) begin
                taken_n = 1'b0;
                last_made   <= upd_set;
                last_unmade <= !upd_set;
                if (upd_set) c_made <= c_made + 1; else c_unmade <= c_unmade + 1;
                qlatch = !upd_set;
            end

            // ---- the host's write ----
            w_blk = reg_valid && reg_we && ({1'b0, reg_addr} >= BLOCK_LEARNER_FIRST) && ({1'b0, reg_addr} < BLOCK_LEARNER_END);
            w_ulo = w_blk && (reg_addr == REG_LRN_UPDATE_AT_OFFSET);
            w_uhi = w_blk && (reg_addr == REG_LRN_UPDATE_AT_OFFSET + WBYTES);
            w_rfs = w_blk && (reg_addr == REG_LRN_REFUSAL_OFFSET);
            w_commit_hi = reg_valid && reg_we && (reg_addr == REG_COMMIT_AT_OFFSET + WBYTES);
            u_new = {reg_wdata, upd_lo};
            shape_ok = (core_filters == 1) && (core_rows == CHANNELS) && !core_rect_abs && (core_pool == 1)
                       && (core_score_shift == 0) && core_no_hidden;
            pend_n   = core_commit && !(take && (core_next_index == core_commit_at));     // as the frame at this edge leaves it

            x_access     = w_blk && (!(w_ulo || w_uhi || w_rfs) || (w_rfs && (reg_wdata != 0)));
            x_stopped    = w_uhi && !core_running;
            x_unfinished = w_uhi && port_hold;
            x_shape      = w_uhi && !shape_ok;
            x_pending    = w_uhi && pend_n;
            x_index      = w_uhi && ((u_new < idx_n) || ({1'b0, u_new} + B_UPDATE_FRAMES > INDEX_TOP));
            x_count      = w_uhi && core_partial;

            // THE ORDER in which an update's faults are named: read this chain upward. The last line that
            // fires wins, so REGISTER_ACCESS is named before everything and WEIGHT_COUNT after everything.
            wcode = '0;
            if (x_count)        wcode = C_COUNT;
            if (x_index)        wcode = C_INDEX;
            if (x_pending)      wcode = C_PENDING;
            if (x_shape)        wcode = C_SHAPE;
            if (x_unfinished)   wcode = C_UNFINISHED;
            if (x_stopped)      wcode = C_STOPPED;
            if (x_access)       wcode = C_ACCESS;
            if (port_intercept) wcode = C_UNFINISHED;           // a write to the core's rows, held back
            if (port_intercept && w_commit_hi) c_early <= c_early + 1;

            if (w_ulo && wcode == '0) upd_lo <= reg_wdata;
            named = w_uhi && (wcode == '0);
            uf_n  = upd_uf;
            if (named) begin
                taken_n = 1'b1;
                done_n  = 1'b0;
                uf_n    = u_new + B_UPDATE_FRAMES;
                upd_u   <= u_new;
                upd_uf  <= uf_n;
                upd_made <= 1'b0;
                upd_set  <= 1'b0;
            end

            // ---- the make: the next index is u or more, and no record at u can still come ----
            make = taken_n && !(named ? 1'b0 : upd_made) && core_running
                   && (idx_n >= (named ? u_new : upd_u))
                   && ((have_any && (last_idx >= (named ? u_new : upd_u))) || (truth_valid && (truth_index >= (named ? u_new : upd_u)))
                       || (idx_n > (named ? u_new : upd_u)));

            // ---- the engine ----
            issue = 1'b0;
            // the D pipeline moves every clock
            db_v  <= da_v;
            dc_v  <= db_v;
            db_p1 <= da_s1 * $signed({{(W_D-N){1'b0}}, n0s});
            db_p0 <= da_s0 * $signed({{(W_D-N){1'b0}}, n1s});
            dc_d  <= db_p1 - db_p0;
            negd   = -dc_d;
            mag    = dc_d[W_D-1] ? negd[W_MAG-1:0] : dc_d[W_MAG-1:0];
            peak_n = peak;
            case (eng)
                E_COPY: begin
                    if (cp_wait) begin
                        cp_wait <= 1'b0;
                    end else begin
                        for (int c = 0; c < CHANNELS; c++) begin
                            cpy0[cp_k*CHANNELS + c] <= sum0[cp_k*CHANNELS + c];
                            cpy1[cp_k*CHANNELS + c] <= sum1[cp_k*CHANNELS + c];
                        end
                        cp_k <= cp_k + 1'b1;
                        if (cp_k == T - 1) eng <= E_PEAK;
                    end
                end
                E_PEAK: begin
                    issue = (is_n < NV);
                    if (dc_v) begin
                        if (mag > peak) peak_n = mag;
                        peak  <= peak_n;
                        got_n <= got_n + 1'b1;
                        if (got_n + 1 == NV) begin
                            if (peak_n == 0) begin
                                done_n = 1'b1;              // QUANTISE_INPUT: no set, and the shadow is left as it was
                                upd_set <= 1'b0;
                                eng <= E_IDLE;
                            end else begin
                                upd_set <= 1'b1;
                                eng <= E_BEGIN;
                            end
                        end
                    end
                end
                E_BEGIN: begin
                    if (wfree && !core_closed) begin
                        lw_valid <= 1'b1;
                        lw_addr  <= REG_SHADOW_BEGIN_OFFSET;
                        lw_wdata <= NV + 1;
                        is_n <= '0; is_c <= '0; is_k <= '0;
                        eng  <= E_DIVIDE;
                    end
                end
                E_DIVIDE: begin
                    // the producer: the next value's D while the divider works on this one
                    issue = (is_n < NV) && !bf_v && !da_v && !db_v && !dc_v;
                    if (dc_v) begin
                        bf_v   <= 1'b1;
                        bf_mag <= mag;
                        bf_neg <= dc_d[W_D-1];
                    end
                    // the divider: |D| * COEFF_MAX / peak, a quotient bit a clock, then the rounding
                    if (!dv_on && bf_v) begin
                        xx     = bf_mag * CMAX;
                        dv_x  <= xx;
                        xs     = xx >> QB;
                        dv_r  <= xs[W_MAG-1:0];
                        dv_q  <= '0;
                        dv_i  <= QB;
                        dv_neg <= bf_neg;
                        dv_on <= 1'b1;
                        dv_rnd <= 1'b0;
                        bf_v  <= 1'b0;
                    end else if (dv_on && !dv_rnd) begin
                        tt = {dv_r, dv_x[dv_i - 1]};
                        if (tt >= {1'b0, peak}) begin
                            tr    = tt - {1'b0, peak};
                            dv_r <= tr[W_MAG-1:0];
                            dv_q <= {dv_q[QB-2:0], 1'b1};
                        end else begin
                            dv_r <= tt[W_MAG-1:0];
                            dv_q <= {dv_q[QB-2:0], 1'b0};
                        end
                        dv_i <= dv_i - 1'b1;
                        if (dv_i == 1) dv_rnd <= 1'b1;
                    end else if (dv_on && dv_rnd && wfree && !core_closed) begin
                        // THE ROUNDING: one more when twice the remainder passes the peak, or equals it with
                        // the quotient odd; then the sign. Half to even is odd-symmetric.
                        twice = {dv_r, 1'b0};
                        qp    = {1'b0, dv_q} + (((twice > {1'b0, peak}) || ((twice == {1'b0, peak}) && dv_q[0])) ? 1 : 0);
                        qw    = dv_neg ? -$signed({{(WORD-QB-1){1'b0}}, qp}) : $signed({{(WORD-QB-1){1'b0}}, qp});
                        lw_valid <= 1'b1;
                        lw_addr  <= REG_SHADOW_DATA_OFFSET;
                        lw_wdata <= qw;
                        dv_on  <= 1'b0;
                        dv_rnd <= 1'b0;
                        wr_n   <= wr_n + 1'b1;
                        if (wr_n + 1 == NV) eng <= E_HEAD;
                    end
                end
                E_HEAD: begin
                    if (wfree && !core_closed) begin
                        lw_valid <= 1'b1;
                        lw_addr  <= REG_SHADOW_DATA_OFFSET;
                        lw_wdata <= 1;                      // the matched filter's head weight
                        eng <= E_END;
                    end
                end
                E_END: begin
                    if (!lw_valid) begin                    // the last write has been taken
                        done_n = 1'b1;
                        eng <= E_IDLE;
                    end
                end
                default: ;
            endcase
            if (issue) begin
                da_v  <= 1'b1;
                da_s1 <= cpy1[is_k*CHANNELS + is_c];
                da_s0 <= cpy0[is_k*CHANNELS + is_c];
                is_n  <= is_n + 1'b1;
                if (is_k == T - 1) begin
                    is_k <= '0;
                    is_c <= is_c + 1'b1;
                end else begin
                    is_k <= is_k + 1'b1;
                end
            end else begin
                da_v <= 1'b0;
            end
            if (make) begin
                upd_made <= 1'b1;
                // the counts as they stand at u: after this edge's judgements when the next index is u here
                n0s <= (idx_n == (named ? u_new : upd_u)) ? cnt0_n : cnt0;
                n1s <= (idx_n == (named ? u_new : upd_u)) ? cnt1_n : cnt1;
                cp_wait <= (idx_n == (named ? u_new : upd_u));
                cp_k  <= '0;
                peak  <= '0;
                is_n  <= '0; is_c <= '0; is_k <= '0;
                got_n <= '0;
                wr_n  <= '0;
                bf_v  <= 1'b0;
                dv_on <= 1'b0;
                eng   <= E_COPY;
            end
            upd_taken <= taken_n;
            upd_done  <= done_n;

            // what learn_port reads at the next edge: unfinished, unless a frame taken there finishes it
            hold_q     <= taken_n && !(done_n && (idx_n >= uf_n));
            hold_end_q <= done_n && ({1'b0, idx_n} + 1 >= {1'b0, uf_n});

            // ---- the latch: the first refusal since it was cleared ----
            clear   = w_rfs && (reg_wdata == 0);
            ref_n   = refusal;
            again_n = refused_again;
            if (clear) begin
                ref_n   = '0;
                again_n = 1'b0;
            end
            if (qlatch) begin
                if (ref_n == '0) ref_n = C_QUANTISE; else again_n = 1'b1;
            end
            if (wcode != '0) begin
                if (ref_n == '0) ref_n = wcode; else again_n = 1'b1;
            end
            refusal       <= ref_n;
            refused_again <= again_n;
        end
    end

    // ------------------------------------------------------------------ the reads
    // A read sees the state before the edge that takes it. What is not a readable row answers 0.
    always @(posedge clk) begin : rd
        logic [WORD-1:0] st;
        logic            in_blk;
        if (rst) begin
            reg_rdata <= '0;
            h_start <= '0; h_busy <= '0; h_full <= '0; h_made <= '0; h_unmade <= '0; h_early <= '0;
        end else if (reg_valid && !reg_we) begin
            in_blk = ({1'b0, reg_addr} >= BLOCK_LEARNER_FIRST) && ({1'b0, reg_addr} < BLOCK_LEARNER_END);
            st = '0;
            st[REG_LRN_STATUS_NAMED_BIT]         = upd_taken && (core_next_index < upd_u);
            st[REG_LRN_STATUS_RUNNING_BIT]       = upd_taken && (core_next_index >= upd_u);
            st[REG_LRN_STATUS_MADE_BIT]          = last_made;
            st[REG_LRN_STATUS_UNMADE_BIT]        = last_unmade;
            st[REG_LRN_STATUS_REFUSED_BIT]       = (refusal != '0);
            st[REG_LRN_STATUS_REFUSED_AGAIN_BIT] = refused_again;
            reg_rdata <= '0;
            if (in_blk) begin
                if      (reg_addr == REG_LRN_UPDATE_AT_OFFSET)          reg_rdata <= upd_taken ? upd_u[WORD-1:0] : '0;
                else if (reg_addr == REG_LRN_UPDATE_AT_OFFSET + WBYTES) reg_rdata <= upd_taken ? upd_u[2*WORD-1:WORD] : '0;
                else if (reg_addr == REG_LRN_STATUS_OFFSET)             reg_rdata <= st;
                else if (reg_addr == REG_LRN_REFUSAL_OFFSET)            reg_rdata <= refusal;
                else if (reg_addr == REG_LRN_COUNT0_OFFSET)             reg_rdata <= cnt0;
                else if (reg_addr == REG_LRN_COUNT1_OFFSET)             reg_rdata <= cnt1;
                else if (reg_addr == REG_LRN_SKIP_START_OFFSET)          begin reg_rdata <= c_start[WORD-1:0];  h_start  <= c_start[2*WORD-1:WORD];  end
                else if (reg_addr == REG_LRN_SKIP_START_OFFSET + WBYTES) reg_rdata <= h_start;
                else if (reg_addr == REG_LRN_SKIP_BUSY_OFFSET)           begin reg_rdata <= c_busy[WORD-1:0];   h_busy   <= c_busy[2*WORD-1:WORD];   end
                else if (reg_addr == REG_LRN_SKIP_BUSY_OFFSET + WBYTES)  reg_rdata <= h_busy;
                else if (reg_addr == REG_LRN_SKIP_FULL_OFFSET)           begin reg_rdata <= c_full[WORD-1:0];   h_full   <= c_full[2*WORD-1:WORD];   end
                else if (reg_addr == REG_LRN_SKIP_FULL_OFFSET + WBYTES)  reg_rdata <= h_full;
                else if (reg_addr == REG_LRN_MADE_OFFSET)                begin reg_rdata <= c_made[WORD-1:0];   h_made   <= c_made[2*WORD-1:WORD];   end
                else if (reg_addr == REG_LRN_MADE_OFFSET + WBYTES)       reg_rdata <= h_made;
                else if (reg_addr == REG_LRN_UNMADE_OFFSET)              begin reg_rdata <= c_unmade[WORD-1:0]; h_unmade <= c_unmade[2*WORD-1:WORD]; end
                else if (reg_addr == REG_LRN_UNMADE_OFFSET + WBYTES)     reg_rdata <= h_unmade;
                else if (reg_addr == REG_LRN_EARLY_OFFSET)               begin reg_rdata <= c_early[WORD-1:0];  h_early  <= c_early[2*WORD-1:WORD];  end
                else if (reg_addr == REG_LRN_EARLY_OFFSET + WBYTES)      reg_rdata <= h_early;
                else if (reg_addr == REG_LRN_CAP_COUNT_BITS_OFFSET)      reg_rdata <= B_COUNT_BITS;
                else if (reg_addr == REG_LRN_CAP_UPDATE_FRAMES_OFFSET)   reg_rdata <= B_UPDATE_FRAMES;
            end
        end
    end
endmodule

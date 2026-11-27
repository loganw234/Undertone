// The detector core and its weight store.
//
// The reference model is the authority: model/detector.py and model/weights.py define every
// bit of what this does, and docs/rtl/core.md says how it is held to them. For output index i:
//
//     filter bank   y_k = sum over the rows of filter k, and over the taps, of coefficient * sample
//     rectifier     r_k = y_k, or |y_k| under abs
//     pool          z_k = the moving sum of the last P values of r_k
//     head          rtl/core/core_head.sv: the hidden layer, the two roundings, the score
//
// and a score record of index i, the epoch, the two flags and the score, in the generated
// package's layout.
//
// ELEVEN REGISTERED STAGES, so a frame taken at one rising edge has its record out at the
// eleventh after it:
//     s1  the delay lines, and the frame's TAG: its index, epoch, bank select and settling bit
//     s2  the products, each coefficient of the frame's own bank times its sample
//     s3  the row sums
//     s4  the filter sums, rectified; the pool's memory is read here
//     s5  the pooled sums
//     h0 to h4  the head's five
//     rec the record, and the sticky overflow flag
//
// THE WEIGHT STORE is two banks, a and b, and one bit, active_sel. A swap is that bit flipping at
// the frame whose index a commit named. THE BIT TRAVELS WITH THE FRAME, in its tag: the products
// at s2, the hidden products at h1 and the output products at h3 each read the bank the frame at
// that stage names. So no filter sum, hidden sum or output sum mixes two sets, whatever the
// pipeline's depth. The pool mixes, and the settling flag marks exactly those outputs.
//
// THE SHAPE is taken once, by `configure`, inside the build's maxima (the parameters B_*, which
// default to the definition's). The weights arrive as a stream of words in the blob's order.
// The register map's control block is in the definition (spec/undertone.toml) from 0x080.
//
// A WRITE AND A FRAME AT ONE EDGE: the write is ordered after the frame. Its checks read the
// state as the frame leaves it.
//
// REFUSALS. A write that is not taken changes nothing and latches the refusal's number; the
// first one since the latch was cleared is the one kept. The names this block raises, and the
// order in which one write's faults are named, are the chain of `wcode` below, read upward.
//
// WHAT IT DOES NOT DO, each a stated limit of docs/rtl/core.md: it checks no hash and sees no
// blob; it has no way back to the stopped state but reset; the shadow cannot be read back; a
// weight position the shape does not use is zero only because reset made it so; nothing here
// has met a synthesis tool, and a row's taps are summed in one stage.
`timescale 1ns / 1ps

module core #(
    parameter int SAMPLE_BITS    = 16,
    parameter int CHANNELS       = 1,
    // the build's maxima: what this build can hold. None may pass the definition's.
    parameter int B_FILTERS      = undertone_pkg::MAX_FILTERS,
    parameter int B_TAPS         = undertone_pkg::MAX_TAPS,
    parameter int B_ROWS         = undertone_pkg::MAX_ROWS,
    parameter int B_POOL         = undertone_pkg::MAX_POOL,
    parameter int B_SCORE_SHIFT  = undertone_pkg::MAX_SCORE_SHIFT,
    parameter int B_HIDDEN       = undertone_pkg::MAX_HIDDEN,
    parameter int B_HIDDEN_SHIFT = undertone_pkg::MAX_HIDDEN_SHIFT
) (
    input  logic                                        clk,
    input  logic                                        rst,          // synchronous, active high
    input  logic                                        in_valid,
    input  logic [CHANNELS*SAMPLE_BITS-1:0]             in_frame,     // channel c at [c*SAMPLE_BITS +: SAMPLE_BITS]
    output logic                                        out_valid,
    output logic [undertone_pkg::SCORE_RECORD_BITS-1:0] out_record,
    // the register port: one operation at each rising edge where reg_valid is high
    input  logic                                        reg_valid,
    input  logic                                        reg_we,       // 1: a write. 0: a read
    input  logic [undertone_pkg::BUS_ADDRESS_BITS-1:0]  reg_addr,     // a byte offset
    input  logic [undertone_pkg::BUS_WORD_BITS-1:0]     reg_wdata,
    output logic [undertone_pkg::BUS_WORD_BITS-1:0]     reg_rdata     // a register: the word of the last read, or 0
    // READ-ONLY VIEWS for the kernel's learner (docs/rtl/krnl-learn.md): each an existing signal, assigned at the end
    , output logic                                      view_running      // running
    , output logic [undertone_pkg::SCORE_INDEX_BITS-1:0] view_next_index  // next_index
    , output logic [undertone_pkg::BUS_WORD_BITS-1:0]   view_taps         // cfg_taps
    , output logic [undertone_pkg::BUS_WORD_BITS-1:0]   view_filters      // cfg_filters
    , output logic [undertone_pkg::BUS_WORD_BITS-1:0]   view_rows         // cfg_rows
    , output logic [undertone_pkg::BUS_WORD_BITS-1:0]   view_pool         // cfg_pool, zero-extended
    , output logic [undertone_pkg::BUS_WORD_BITS-1:0]   view_score_shift  // cfg_score_shift, zero-extended
    , output logic                                      view_rect_abs     // cfg_rect_abs
    , output logic                                      view_no_hidden    // cfg_no_hidden
    , output logic                                      view_commit       // commit_valid
    , output logic [undertone_pkg::SCORE_INDEX_BITS-1:0] view_commit_at   // commit_at
    , output logic                                      view_partial      // ld_partial
    , output logic                                      view_active_sel   // active_sel
    , output logic [10:1]                               view_vld          // vld, every stage, ST_S1 (1) to ST_H4 (10)
    , output logic [10:1]                               view_tag_sel      // each stage's tag's bank select
);
    import undertone_pkg::*;

    // ------------------------------------------------------------------ widths
    // Each is the fewest signed bits for the stage's range, as model/detector.py's `ranges` and
    // `bits_for` give it, with this build's maxima where the model has the definition's. Written
    // as closed forms: the largest product is +2^E_PROD (both factors at their lowest) and every
    // other product is smaller in magnitude, so a sum of N products needs E_PROD + clog2(N+1) + 1
    // bits; the hidden sum's extreme is negative, -N * 2^(E_PROD + COEFF_BITS - 1), and needs
    // E_PROD + COEFF_BITS + clog2(N).
    localparam int E_PROD = SAMPLE_BITS + COEFF_BITS - 2;
    localparam int PER    = (CHANNELS < B_ROWS) ? CHANNELS : B_ROWS;             // the most rows one filter has
    localparam int W_PROD = E_PROD + 2;
    localparam int W_ROW  = E_PROD + $clog2(B_TAPS + 1) + 1;
    localparam int W_FILT = E_PROD + $clog2(PER * B_TAPS + 1) + 1;
    localparam int W_RECT = E_PROD + $clog2(PER * B_TAPS + 1) + 1;               // abs folds a range whose high end is the larger
    localparam int W_POOL = E_PROD + $clog2(B_POOL * PER * B_TAPS + 1) + 1;
    localparam int W_HEAD = E_PROD + COEFF_BITS + $clog2(B_ROWS * B_POOL * B_TAPS);

    localparam int WORD      = BUS_WORD_BITS;
    localparam int WBYTES    = BUS_WORD_BITS / 8;
    localparam int NCOEF     = B_ROWS * B_TAPS;
    localparam int NHID      = B_HIDDEN * B_FILTERS;
    localparam int PTR_BITS  = (B_POOL > 1) ? $clog2(B_POOL) : 1;
    localparam int FILL_BITS = $clog2(B_POOL + 1);

    // the stages, numbered; a valid bit and a tag for each
    localparam int ST_S1 = 1;
    localparam int ST_S2 = 2;
    localparam int ST_S3 = 3;
    localparam int ST_S4 = 4;
    localparam int ST_S5 = 5;
    localparam int ST_H0 = 6;
    localparam int ST_H1 = 7;
    localparam int ST_H2 = 8;
    localparam int ST_H3 = 9;
    localparam int ST_H4 = 10;
    // The last stage whose frame still has weights to read at a LATER edge: a frame at h1 reads
    // its head weights at the edge after next. One at h2 reads them at this edge, which a write
    // landing at this edge cannot change.
    localparam int ST_CLOSED_LAST = ST_H1;

    // the tag
    localparam int TAG_INDEX_LSB = 0;
    localparam int TAG_EPOCH_LSB = SCORE_INDEX_BITS;
    localparam int TAG_SEL       = SCORE_INDEX_BITS + SCORE_EPOCH_BITS;
    localparam int TAG_SETTLE    = TAG_SEL + 1;
    localparam int TAG_BITS      = TAG_SETTLE + 1;

    initial begin
        if (B_FILTERS < 1 || B_FILTERS > MAX_FILTERS || B_TAPS < 1 || B_TAPS > MAX_TAPS
                || B_ROWS < 1 || B_ROWS > MAX_ROWS || B_POOL < 1 || B_POOL > MAX_POOL
                || B_HIDDEN < 1 || B_HIDDEN > MAX_HIDDEN
                || B_SCORE_SHIFT < 0 || B_SCORE_SHIFT > MAX_SCORE_SHIFT
                || B_HIDDEN_SHIFT < 0 || B_HIDDEN_SHIFT > MAX_HIDDEN_SHIFT) begin
            $fatal(1, "core: a build maximum is outside the definition's");
        end
        if (SCORE_INDEX_BITS != 2 * BUS_WORD_BITS || SCORE_EPOCH_BITS != BUS_WORD_BITS
                || REG_COMMIT_AT_WORDS != 2 || REG_NEXT_INDEX_WORDS != 2
                || REG_SHAPE_MASKS_WORDS < B_FILTERS || CHANNELS > BUS_WORD_BITS) begin
            $fatal(1, "core: the register map no longer fits the record's fields or the build");
        end
    end

    // ------------------------------------------------------------------ state
    // the shape as the host wrote it
    logic [WORD-1:0] shp_sample_bits, shp_channels, shp_filters, shp_taps, shp_rectifier;
    logic [WORD-1:0] shp_score_shift, shp_pool, shp_hidden, shp_hidden_shift, shp_between;
    logic [REG_SHAPE_MASKS_WORDS*WORD-1:0] shp_masks;          // word k is filter k's channel mask
    // STOPPED is neither: reset is the only way into it
    logic running, loading;
    // the shape as `configure` took it
    logic [WORD-1:0]      cfg_filters, cfg_taps, cfg_hidden, cfg_rows, cfg_words;
    logic [FILL_BITS-1:0] cfg_pool;
    logic [7:0]           cfg_score_shift, cfg_hidden_shift;
    logic                 cfg_rect_abs, cfg_between_abs, cfg_no_hidden;
    logic                 row_used [0:B_ROWS-1];               // row r is one channel's coefficients for one filter
    logic [7:0]           row_filt [0:B_ROWS-1];
    logic [7:0]           row_chan [0:B_ROWS-1];
    // the stream of weight words
    logic            ld_partial, ld_whole, ld_spoiled;
    logic [WORD-1:0] ld_count, ld_a, ld_b;
    logic [1:0]      ld_phase;                                 // 0: the rows. 1: the hidden units. 2: the head weights
    // the store
    logic                        active_sel;                   // 0: bank a is active. 1: bank b
    logic [SCORE_EPOCH_BITS-1:0] epoch;
    logic [SCORE_INDEX_BITS-1:0] next_index, commit_at;
    logic                        commit_valid;
    logic [WORD-1:0]             commit_lo;
    logic [FILL_BITS-1:0]        settle_left;                  // how many coming frames still mix two sets
    // the latched refusal
    logic [7:0] refusal;
    logic       refused_again;
    logic [WORD-1:0] ni_hold;                                  // next_index's upper word, held by a read of its lower

    // the two banks
    logic signed [COEFF_BITS-1:0]   coef_a [0:NCOEF-1];        // row r, delay-line position m at r*B_TAPS + m
    logic signed [COEFF_BITS-1:0]   coef_b [0:NCOEF-1];
    logic [NHID*COEFF_BITS-1:0]     hid_a, hid_b;              // g[j][k] at index j*B_FILTERS + k
    logic [B_HIDDEN*COEFF_BITS-1:0] out_a, out_b;              // o[j] at index j

    // the pipeline
    logic [ST_H4:ST_S1]            vld;
    logic [TAG_BITS-1:0]           tg [ST_S1:ST_H4];
    // KEEP holds the delay line in the fabric's registers. Without it Vivado 2022.2 moved it into the DSP blocks'
    // B registers, chained from block to block through their B cascade ports, one chain of up to 128 blocks for
    // a row, over the SLR's DSP column of 110, and placement refused it (round 3, the lead; docs/rtl/core.md,
    // limit 2). A synthesis attribute only: Icarus Verilog ignores it, and what the core computes is unchanged.
    (* keep = "true" *)
    logic signed [SAMPLE_BITS-1:0] dl [0:CHANNELS*B_TAPS-1];   // channel c, position m at c*B_TAPS + m; position 0 is the newest
    logic signed [W_PROD-1:0]      s2_prod [0:NCOEF-1];
    logic signed [W_ROW-1:0]       s3_row [0:B_ROWS-1];
    logic [B_FILTERS*W_RECT-1:0]   s4_rect;                    // r_k at [k*W_RECT +: W_RECT]
    logic [B_FILTERS*W_RECT-1:0]   s4_old;                     // the values the pool drops, read a stage ahead
    // The pool's memory, for UltraRAM: its read has a register of its own, pool_q, with the forwarding chosen after
    // it (docs/rtl/poolram.md). A synthesis attribute only: Icarus Verilog ignores it.
    (* ram_style = "ultra" *)
    logic [B_FILTERS*W_RECT-1:0]   pool_mem [0:B_POOL-1];
    logic [B_FILTERS*W_RECT-1:0]   pool_q;                     // the memory's own output register: the word at pool_rp
    logic [B_FILTERS*W_RECT-1:0]   fwd_val;                    // the word written at that read's edge
    logic                          fwd_sel;                    // 1: s4_old is fwd_val. 0: s4_old is pool_q
    logic [PTR_BITS-1:0]           pool_rp, pool_wp;
    logic [FILL_BITS-1:0]          pool_fill;                  // frames since the start, stopping at P
    logic [B_FILTERS*W_POOL-1:0]   z_flat;                     // z_k at [k*W_POOL +: W_POOL]
    logic                          sticky;                     // the overflow flag, as of the last record out

    wire                           head_valid;
    wire                           head_overflow;
    wire [SCORE_SCORE_BITS-1:0]    head_score;

    wire [255:0] spec_hash = SPEC_SHA256;
    wire in_block = (reg_addr >= BLOCK_CORE_FIRST) && (reg_addr < BLOCK_CORE_END);
    wire aligned  = ((reg_addr % WBYTES) == 0);

    // ------------------------------------------------------------------ the frame, the store, the writes
    always @(posedge clk) begin : ctl
        logic                        take, swap_now, sel_n, cv_n, closed_n, pend_n, stopped, settle_bit;
        logic [SCORE_EPOCH_BITS-1:0] epoch_n;
        logic [SCORE_INDEX_BITS-1:0] index_n, at;
        logic [FILL_BITS-1:0]        settle_n;
        logic                        w_any, w_al, w_sb, w_ch, w_k, w_t, w_rc, w_ss, w_p, w_h, w_hs, w_bt, w_mask;
        logic                        w_cfg, w_begin, w_data, w_start, w_clo, w_chi, w_rfs, w_shape, w_known;
        logic                        x_register_access, x_core_stopped, x_swap_shape, x_profile, x_shape_filters;
        logic                        x_shape_taps, x_shape_rectifier, x_shape_shift, x_shape_pool, x_shape_hidden;
        logic                        x_shape_hshift, x_shape_between, x_shape_channel, x_shape_rows;
        logic                        x_swap_pending, x_swap_index, x_swap_epoch, x_weight_count, x_weight_range;
        logic                        mask_bad, wv_ok, again_n;
        logic [WORD-1:0]             mk, n_rows, n_words, ci, hi;
        logic [7:0]                  wcode, fcode, ref_n;
        logic signed [COEFF_BITS-1:0] wv;
        int                          nr;

        if (rst) begin
            shp_sample_bits <= '0; shp_channels <= '0; shp_filters <= '0; shp_taps <= '0; shp_rectifier <= '0;
            shp_score_shift <= '0; shp_pool <= '0; shp_hidden <= '0; shp_hidden_shift <= '0; shp_between <= '0;
            shp_masks <= '0;
            running <= 1'b0; loading <= 1'b0;
            cfg_filters <= '0; cfg_taps <= '0; cfg_hidden <= '0; cfg_rows <= '0; cfg_words <= '0; cfg_pool <= '0;
            cfg_score_shift <= '0; cfg_hidden_shift <= '0;
            cfg_rect_abs <= 1'b0; cfg_between_abs <= 1'b0; cfg_no_hidden <= 1'b0;
            for (int r = 0; r < B_ROWS; r++) begin
                row_used[r] <= 1'b0; row_filt[r] <= '0; row_chan[r] <= '0;
            end
            ld_partial <= 1'b0; ld_whole <= 1'b0; ld_spoiled <= 1'b0;
            ld_count <= '0; ld_a <= '0; ld_b <= '0; ld_phase <= 2'd0;
            active_sel <= 1'b0; epoch <= '0; next_index <= '0; commit_at <= '0; commit_valid <= 1'b0;
            commit_lo <= '0; settle_left <= '0;
            refusal <= 8'd0; refused_again <= 1'b0;
            for (int i = 0; i < NCOEF; i++) begin
                coef_a[i] <= '0; coef_b[i] <= '0;
            end
            hid_a <= '0; hid_b <= '0; out_a <= '0; out_b <= '0;
            vld <= '0;
            for (int i = ST_S1; i <= ST_H4; i++) tg[i] <= '0;
            for (int i = 0; i < CHANNELS*B_TAPS; i++) dl[i] <= '0;
        end else begin
            // ---- the frame, first. model/weights.py, Store.step, line for line ----
            take       = in_valid && running;
            swap_now   = take && commit_valid && (next_index == commit_at);
            sel_n      = active_sel ^ swap_now;
            epoch_n    = epoch + (swap_now ? 1 : 0);
            index_n    = next_index + (take ? 1 : 0);
            cv_n       = commit_valid && !swap_now;
            settle_bit = swap_now ? ((next_index != 0) && (cfg_pool >= 2)) : (settle_left != 0);
            settle_n   = settle_left;
            if (swap_now) begin
                settle_n = ((next_index != 0) && (cfg_pool >= 2)) ? (cfg_pool - 2) : 0;
            end else if (take && (settle_left != 0)) begin
                settle_n = settle_left - 1;
            end

            for (int i = ST_S2; i <= ST_H4; i++) begin
                vld[i] <= vld[i-1];
                tg[i]  <= tg[i-1];
            end
            vld[ST_S1] <= take;
            if (take) begin
                tg[ST_S1] <= {settle_bit, sel_n, epoch_n, next_index};
                for (int c = 0; c < CHANNELS; c++) begin
                    for (int m = B_TAPS - 1; m > 0; m--) dl[c*B_TAPS + m] <= dl[c*B_TAPS + m - 1];
                    dl[c*B_TAPS] <= $signed(in_frame[c*SAMPLE_BITS +: SAMPLE_BITS]);
                end
            end
            active_sel   <= sel_n;
            epoch        <= epoch_n;
            next_index   <= index_n;
            commit_valid <= cv_n;
            settle_left  <= settle_n;
            if (swap_now) ld_whole <= 1'b0;      // the bank that was active is the shadow now, whole and untouched

            // The shadow is closed while a frame taken before the swap still has weights to read
            // from the bank that is now the shadow.
            closed_n = 1'b0;
            for (int i = ST_S1; i <= ST_CLOSED_LAST; i++) begin
                if (vld[i] && (tg[i][TAG_SEL] != sel_n)) closed_n = 1'b1;
            end
            pend_n  = cv_n || (settle_n != 0);
            stopped = !running && !loading;

            // ---- the write, after the frame ----
            w_any   = reg_valid && reg_we && in_block;
            w_al    = w_any && aligned;
            w_sb    = w_al && (reg_addr == REG_SHAPE_SAMPLE_BITS_OFFSET);
            w_ch    = w_al && (reg_addr == REG_SHAPE_CHANNELS_OFFSET);
            w_k     = w_al && (reg_addr == REG_SHAPE_FILTERS_OFFSET);
            w_t     = w_al && (reg_addr == REG_SHAPE_TAPS_OFFSET);
            w_rc    = w_al && (reg_addr == REG_SHAPE_RECTIFIER_OFFSET);
            w_ss    = w_al && (reg_addr == REG_SHAPE_SCORE_SHIFT_OFFSET);
            w_p     = w_al && (reg_addr == REG_SHAPE_POOL_OFFSET);
            w_h     = w_al && (reg_addr == REG_SHAPE_HIDDEN_OFFSET);
            w_hs    = w_al && (reg_addr == REG_SHAPE_HIDDEN_SHIFT_OFFSET);
            w_bt    = w_al && (reg_addr == REG_SHAPE_BETWEEN_OFFSET);
            w_mask  = w_al && (reg_addr >= REG_SHAPE_MASKS_OFFSET)
                           && (reg_addr < REG_SHAPE_MASKS_OFFSET + REG_SHAPE_MASKS_WORDS * WBYTES);
            w_cfg   = w_al && (reg_addr == REG_CONFIGURE_OFFSET);
            w_begin = w_al && (reg_addr == REG_SHADOW_BEGIN_OFFSET);
            w_data  = w_al && (reg_addr == REG_SHADOW_DATA_OFFSET);
            w_start = w_al && (reg_addr == REG_START_OFFSET);
            w_clo   = w_al && (reg_addr == REG_COMMIT_AT_OFFSET);
            w_chi   = w_al && (reg_addr == REG_COMMIT_AT_OFFSET + WBYTES);
            w_rfs   = w_al && (reg_addr == REG_REFUSAL_OFFSET);
            w_shape = w_sb || w_ch || w_k || w_t || w_rc || w_ss || w_p || w_h || w_hs || w_bt || w_mask;
            w_known = w_shape || w_cfg || w_begin || w_data || w_start || w_clo || w_chi || w_rfs;

            // what `configure` reads of the shape: its rows, and whether a mask is wrong
            n_rows   = '0;
            mask_bad = 1'b0;
            for (int k = 0; k < B_FILTERS; k++) begin
                if (k < shp_filters) begin
                    mk = shp_masks[k*WORD +: WORD];
                    if ((mk == 0) || ((mk >> CHANNELS) != 0)) mask_bad = 1'b1;
                    for (int c = 0; c < CHANNELS; c++) begin
                        if (mk[c]) n_rows = n_rows + 1;
                    end
                end
            end
            n_words = n_rows * shp_taps + ((shp_hidden != 0) ? (shp_hidden * shp_filters + shp_hidden) : shp_filters);
            at      = {reg_wdata, commit_lo};
            // a weight word is the blob's: 32 bits, two's complement. It is in range when every bit
            // from the coefficient's top bit up is the same.
            wv_ok   = (&reg_wdata[WORD-1:COEFF_BITS-1]) || !(|reg_wdata[WORD-1:COEFF_BITS-1]);

            // each name's cases
            x_register_access = w_any && (!aligned || !w_known || (w_rfs && (reg_wdata != 0)));
            x_core_stopped    = (w_chi && !running) || ((w_begin || w_data || w_start) && stopped);
            x_swap_shape      = ((w_shape || w_cfg) && !stopped) || (w_start && running);
            x_profile         = w_cfg && ((shp_sample_bits != SAMPLE_BITS) || (shp_channels != CHANNELS));
            x_shape_filters   = w_cfg && ((shp_filters < 1) || (shp_filters > B_FILTERS));
            x_shape_taps      = w_cfg && ((shp_taps < 1) || (shp_taps > B_TAPS));
            x_shape_rectifier = w_cfg && (shp_rectifier != RECTIFIER_PASS) && (shp_rectifier != RECTIFIER_ABS);
            x_shape_shift     = w_cfg && (shp_score_shift > B_SCORE_SHIFT);
            x_shape_pool      = w_cfg && ((shp_pool < 1) || (shp_pool > B_POOL));
            x_shape_hidden    = w_cfg && ((shp_hidden > B_HIDDEN)
                                          || ((shp_hidden == 0) && ((shp_hidden_shift != 0) || (shp_between != 0))));
            x_shape_hshift    = w_cfg && (shp_hidden != 0) && (shp_hidden_shift > B_HIDDEN_SHIFT);
            x_shape_between   = w_cfg && (shp_hidden != 0) && (shp_between != RECTIFIER_PASS) && (shp_between != RECTIFIER_ABS);
            x_shape_channel   = w_cfg && mask_bad;
            x_shape_rows      = w_cfg && (n_rows > B_ROWS);
            x_swap_pending    = (w_chi && pend_n) || ((w_begin || w_data) && running && (cv_n || closed_n));
            x_swap_index      = w_chi && (at < index_n);
            x_swap_epoch      = w_chi && (&epoch_n);
            x_weight_count    = (w_cfg && (reg_wdata != n_words)) || (w_begin && (reg_wdata != cfg_words))
                                || (w_data && !(ld_partial && !ld_spoiled)) || (w_start && !ld_whole)
                                || (w_chi && ld_partial);
            x_weight_range    = w_data && !wv_ok;

            // THE ORDER in which one write's faults are named: read this chain upward. The last
            // line that fires wins, so REGISTER_ACCESS is named before everything and WEIGHT_RANGE
            // after everything.
            wcode = 8'd0;
            if (x_weight_range)    wcode = REFUSAL_WEIGHT_RANGE;
            if (x_weight_count)    wcode = REFUSAL_WEIGHT_COUNT;
            if (x_swap_epoch)      wcode = REFUSAL_SWAP_EPOCH;
            if (x_swap_index)      wcode = REFUSAL_SWAP_INDEX;
            if (x_swap_pending)    wcode = REFUSAL_SWAP_PENDING;
            if (x_shape_rows)      wcode = REFUSAL_SHAPE_ROWS;
            if (x_shape_channel)   wcode = REFUSAL_SHAPE_CHANNEL;
            if (x_shape_between)   wcode = REFUSAL_SHAPE_BETWEEN;
            if (x_shape_hshift)    wcode = REFUSAL_SHAPE_HIDDEN_SHIFT;
            if (x_shape_hidden)    wcode = REFUSAL_SHAPE_HIDDEN;
            if (x_shape_pool)      wcode = REFUSAL_SHAPE_POOL;
            if (x_shape_shift)     wcode = REFUSAL_SHAPE_SHIFT;
            if (x_shape_rectifier) wcode = REFUSAL_SHAPE_RECTIFIER;
            if (x_shape_taps)      wcode = REFUSAL_SHAPE_TAPS;
            if (x_shape_filters)   wcode = REFUSAL_SHAPE_FILTERS;
            if (x_profile)         wcode = REFUSAL_PROFILE_UNKNOWN;
            if (x_swap_shape)      wcode = REFUSAL_SWAP_SHAPE;
            if (x_core_stopped)    wcode = REFUSAL_CORE_STOPPED;
            if (x_register_access) wcode = REFUSAL_REGISTER_ACCESS;

            // ---- what a write that is taken does ----
            if (wcode == 8'd0) begin
                if (w_sb) shp_sample_bits  <= reg_wdata;
                if (w_ch) shp_channels     <= reg_wdata;
                if (w_k)  shp_filters      <= reg_wdata;
                if (w_t)  shp_taps         <= reg_wdata;
                if (w_rc) shp_rectifier    <= reg_wdata;
                if (w_ss) shp_score_shift  <= reg_wdata;
                if (w_p)  shp_pool         <= reg_wdata;
                if (w_h)  shp_hidden       <= reg_wdata;
                if (w_hs) shp_hidden_shift <= reg_wdata;
                if (w_bt) shp_between      <= reg_wdata;
                if (w_mask) shp_masks[((reg_addr - REG_SHAPE_MASKS_OFFSET) / WBYTES)*WORD +: WORD] <= reg_wdata;

                if (w_cfg) begin
                    loading          <= 1'b1;
                    cfg_filters      <= shp_filters;
                    cfg_taps         <= shp_taps;
                    cfg_pool         <= shp_pool[FILL_BITS-1:0];
                    cfg_hidden       <= shp_hidden;
                    cfg_no_hidden    <= (shp_hidden == 0);
                    cfg_score_shift  <= shp_score_shift[7:0];
                    cfg_hidden_shift <= shp_hidden_shift[7:0];
                    cfg_rect_abs     <= (shp_rectifier == RECTIFIER_ABS);
                    cfg_between_abs  <= (shp_between == RECTIFIER_ABS);
                    cfg_rows         <= n_rows;
                    cfg_words        <= n_words;
                    // the rows, in the blob's order: filter 0's by ascending channel, then filter 1's
                    nr = 0;
                    for (int k = 0; k < B_FILTERS; k++) begin
                        if (k < shp_filters) begin
                            mk = shp_masks[k*WORD +: WORD];
                            for (int c = 0; c < CHANNELS; c++) begin
                                if (mk[c]) begin
                                    if (nr < B_ROWS) begin
                                        row_used[nr] <= 1'b1;
                                        row_filt[nr] <= k;
                                        row_chan[nr] <= c;
                                    end
                                    nr = nr + 1;
                                end
                            end
                        end
                    end
                end

                if (w_cfg || w_begin) begin          // the stream is at word 0
                    ld_partial <= 1'b1; ld_whole <= 1'b0; ld_spoiled <= 1'b0;
                    ld_count <= '0; ld_a <= '0; ld_b <= '0; ld_phase <= 2'd0;
                end

                if (w_data) begin
                    wv = $signed(reg_wdata[COEFF_BITS-1:0]);
                    // Before the start a word goes into both banks; while running, into the shadow.
                    if (ld_phase == 2'd0) begin
                        // coefficient j of a row meets the sample T-1-j frames old: position T-1-j
                        ci = ld_a * B_TAPS + (cfg_taps - 1 - ld_b);
                        if (loading || sel_n)  coef_a[ci] <= wv;
                        if (loading || !sel_n) coef_b[ci] <= wv;
                        if (ld_b == cfg_taps - 1) begin
                            ld_b <= '0;
                            if (ld_a == cfg_rows - 1) begin
                                ld_a     <= '0;
                                ld_phase <= cfg_no_hidden ? 2'd2 : 2'd1;
                            end else begin
                                ld_a <= ld_a + 1;
                            end
                        end else begin
                            ld_b <= ld_b + 1;
                        end
                    end else if (ld_phase == 2'd1) begin
                        hi = ld_a * B_FILTERS + ld_b;
                        if (loading || sel_n)  hid_a[hi*COEFF_BITS +: COEFF_BITS] <= wv;
                        if (loading || !sel_n) hid_b[hi*COEFF_BITS +: COEFF_BITS] <= wv;
                        if (ld_b == cfg_filters - 1) begin
                            ld_b <= '0;
                            if (ld_a == cfg_hidden - 1) begin
                                ld_a     <= '0;
                                ld_phase <= 2'd2;
                            end else begin
                                ld_a <= ld_a + 1;
                            end
                        end else begin
                            ld_b <= ld_b + 1;
                        end
                    end else begin
                        if (cfg_no_hidden) begin
                            // no hidden layer: the K head weights are unit 0's weights (the one route)
                            if (loading || sel_n)  hid_a[ld_a*COEFF_BITS +: COEFF_BITS] <= wv;
                            if (loading || !sel_n) hid_b[ld_a*COEFF_BITS +: COEFF_BITS] <= wv;
                        end else begin
                            if (loading || sel_n)  out_a[ld_a*COEFF_BITS +: COEFF_BITS] <= wv;
                            if (loading || !sel_n) out_b[ld_a*COEFF_BITS +: COEFF_BITS] <= wv;
                        end
                        ld_a <= ld_a + 1;
                    end
                    ld_count <= ld_count + 1;
                    if (ld_count + 1 == cfg_words) begin
                        ld_partial <= 1'b0;
                        ld_whole   <= 1'b1;
                    end
                end

                if (w_start) begin
                    running    <= 1'b1;
                    loading    <= 1'b0;
                    epoch      <= reg_wdata[SCORE_EPOCH_BITS-1:0];
                    next_index <= '0;
                    ld_partial <= 1'b0; ld_whole <= 1'b0; ld_spoiled <= 1'b0;
                end

                if (w_clo) commit_lo <= reg_wdata;       // the lower word: kept. The upper word is the commit
                if (w_chi) begin
                    commit_valid <= 1'b1;
                    commit_at    <= at;
                end
            end else if (w_data && (wcode == REFUSAL_WEIGHT_RANGE)) begin
                ld_spoiled <= 1'b1;                      // the word is not stored, and the stream cannot be finished
            end

            // ---- the latch: the first refusal since it was cleared ----
            fcode   = 8'd0;
            if (in_valid && !running) fcode = REFUSAL_CORE_STOPPED;      // a frame offered to a core that is not running
            ref_n   = refusal;
            again_n = refused_again;
            if (w_rfs && (reg_wdata == 0)) begin         // a write of 0 clears what was latched before this edge
                ref_n   = 8'd0;
                again_n = 1'b0;
            end
            if (fcode != 8'd0) begin
                if (ref_n == 8'd0) ref_n = fcode; else again_n = 1'b1;
            end
            if (wcode != 8'd0) begin
                if (ref_n == 8'd0) ref_n = wcode; else again_n = 1'b1;
            end
            refusal       <= ref_n;
            refused_again <= again_n;
        end
    end

    // ------------------------------------------------------------------ the reads
    // A read sees the state before the edge that takes it. What is not a readable row answers 0.
    always @(posedge clk) begin : rd
        logic [WORD-1:0] st;
        if (rst) begin
            reg_rdata <= '0;
            ni_hold   <= '0;
        end else if (reg_valid && !reg_we) begin
            st = '0;
            st[REG_STATUS_RUNNING_BIT]  = running;
            st[REG_STATUS_LOADING_BIT]  = loading;
            st[REG_STATUS_COMMIT_BIT]   = commit_valid;
            st[REG_STATUS_SETTLING_BIT] = (settle_left != 0);
            for (int i = ST_S1; i <= ST_CLOSED_LAST; i++) begin
                if (vld[i] && (tg[i][TAG_SEL] != active_sel)) st[REG_STATUS_CLOSED_BIT] = 1'b1;
            end
            st[REG_STATUS_PARTIAL_BIT]       = ld_partial;
            st[REG_STATUS_WHOLE_BIT]         = ld_whole;
            st[REG_STATUS_OVERFLOW_BIT]      = sticky;
            st[REG_STATUS_REFUSED_BIT]       = (refusal != 8'd0);
            st[REG_STATUS_REFUSED_AGAIN_BIT] = refused_again;

            reg_rdata <= '0;
            if (in_block && aligned) begin
                if      (reg_addr == REG_ID_OFFSET)               reg_rdata <= BUS_MAGIC;
                else if (reg_addr == REG_SPEC_VERSION_OFFSET)     reg_rdata <= SPEC_VERSION;
                else if ((reg_addr >= REG_SPEC_HASH_OFFSET) && (reg_addr < REG_SPEC_HASH_OFFSET + REG_SPEC_HASH_WORDS * WBYTES))
                    reg_rdata <= spec_hash[((reg_addr - REG_SPEC_HASH_OFFSET) / WBYTES)*WORD +: WORD];
                else if (reg_addr == REG_CAP_SAMPLE_BITS_OFFSET)  reg_rdata <= SAMPLE_BITS;
                else if (reg_addr == REG_CAP_CHANNELS_OFFSET)     reg_rdata <= CHANNELS;
                else if (reg_addr == REG_CAP_COEFF_BITS_OFFSET)   reg_rdata <= COEFF_BITS;
                else if (reg_addr == REG_CAP_FILTERS_OFFSET)      reg_rdata <= B_FILTERS;
                else if (reg_addr == REG_CAP_TAPS_OFFSET)         reg_rdata <= B_TAPS;
                else if (reg_addr == REG_CAP_ROWS_OFFSET)         reg_rdata <= B_ROWS;
                else if (reg_addr == REG_CAP_POOL_OFFSET)         reg_rdata <= B_POOL;
                else if (reg_addr == REG_CAP_SCORE_SHIFT_OFFSET)  reg_rdata <= B_SCORE_SHIFT;
                else if (reg_addr == REG_CAP_HIDDEN_OFFSET)       reg_rdata <= B_HIDDEN;
                else if (reg_addr == REG_CAP_HIDDEN_SHIFT_OFFSET) reg_rdata <= B_HIDDEN_SHIFT;
                else if (reg_addr == REG_CAP_RECTIFIERS_OFFSET)   reg_rdata <= (1 << RECTIFIER_PASS) | (1 << RECTIFIER_ABS);
                // a blob with no hidden layer is version 1 and one with a layer is version 2 (model/weights.py);
                // the definition holds neither number. A build has at least one unit, so it takes both.
                else if (reg_addr == REG_CAP_BLOB_VERSIONS_OFFSET) reg_rdata <= (1 << 1) | (1 << 2);
                else if (reg_addr == REG_SHAPE_SAMPLE_BITS_OFFSET)  reg_rdata <= shp_sample_bits;
                else if (reg_addr == REG_SHAPE_CHANNELS_OFFSET)     reg_rdata <= shp_channels;
                else if (reg_addr == REG_SHAPE_FILTERS_OFFSET)      reg_rdata <= shp_filters;
                else if (reg_addr == REG_SHAPE_TAPS_OFFSET)         reg_rdata <= shp_taps;
                else if (reg_addr == REG_SHAPE_RECTIFIER_OFFSET)    reg_rdata <= shp_rectifier;
                else if (reg_addr == REG_SHAPE_SCORE_SHIFT_OFFSET)  reg_rdata <= shp_score_shift;
                else if (reg_addr == REG_SHAPE_POOL_OFFSET)         reg_rdata <= shp_pool;
                else if (reg_addr == REG_SHAPE_HIDDEN_OFFSET)       reg_rdata <= shp_hidden;
                else if (reg_addr == REG_SHAPE_HIDDEN_SHIFT_OFFSET) reg_rdata <= shp_hidden_shift;
                else if (reg_addr == REG_SHAPE_BETWEEN_OFFSET)      reg_rdata <= shp_between;
                else if ((reg_addr >= REG_SHAPE_MASKS_OFFSET) && (reg_addr < REG_SHAPE_MASKS_OFFSET + REG_SHAPE_MASKS_WORDS * WBYTES))
                    reg_rdata <= shp_masks[((reg_addr - REG_SHAPE_MASKS_OFFSET) / WBYTES)*WORD +: WORD];
                else if (reg_addr == REG_COMMIT_AT_OFFSET)          reg_rdata <= commit_valid ? commit_at[WORD-1:0] : {WORD{1'b0}};
                else if (reg_addr == REG_COMMIT_AT_OFFSET + WBYTES) reg_rdata <= commit_valid ? commit_at[2*WORD-1:WORD] : {WORD{1'b0}};
                else if (reg_addr == REG_STATUS_OFFSET)             reg_rdata <= st;
                else if (reg_addr == REG_REFUSAL_OFFSET)            reg_rdata <= refusal;
                else if (reg_addr == REG_EPOCH_OFFSET)              reg_rdata <= epoch;
                else if (reg_addr == REG_NEXT_INDEX_OFFSET) begin
                    reg_rdata <= next_index[WORD-1:0];
                    ni_hold   <= next_index[2*WORD-1:WORD];       // the two words are of one moment
                end
                else if (reg_addr == REG_NEXT_INDEX_OFFSET + WBYTES) reg_rdata <= ni_hold;
                else if (reg_addr == REG_SHADOW_COUNT_OFFSET)       reg_rdata <= ld_count;
                else if (reg_addr == REG_SHADOW_WORDS_OFFSET)       reg_rdata <= cfg_words;
            end
        end
    end

    // ------------------------------------------------------------------ s2: the products
    always @(posedge clk) begin : st2
        logic signed [COEFF_BITS-1:0]  cw;
        logic signed [SAMPLE_BITS-1:0] xs;
        logic signed [W_PROD-1:0]      cx, xx, pp;
        if (rst) begin
            for (int i = 0; i < NCOEF; i++) s2_prod[i] <= '0;
        end else if (vld[ST_S1]) begin
            for (int r = 0; r < B_ROWS; r++) begin
                for (int m = 0; m < B_TAPS; m++) begin
                    cw = tg[ST_S1][TAG_SEL] ? coef_b[r*B_TAPS + m] : coef_a[r*B_TAPS + m];
                    xs = dl[row_chan[r]*B_TAPS + m];
                    cx = cw;                            // sign-extended to the product's width
                    xx = xs;
                    pp = cx * xx;
                    s2_prod[r*B_TAPS + m] <= pp;
                end
            end
        end
    end

    // ------------------------------------------------------------------ s3: the row sums
    always @(posedge clk) begin : st3
        logic signed [W_ROW-1:0] acc;
        if (rst) begin
            for (int r = 0; r < B_ROWS; r++) s3_row[r] <= '0;
        end else if (vld[ST_S2]) begin
            for (int r = 0; r < B_ROWS; r++) begin
                acc = '0;
                for (int m = 0; m < B_TAPS; m++) acc = acc + s2_prod[r*B_TAPS + m];
                s3_row[r] <= acc;
            end
        end
    end

    // ------------------------------------------------------------------ s4: the filter sums, rectified; the pool's read
    always @(posedge clk) begin : st4
        logic signed [W_FILT-1:0] y;
        logic signed [W_RECT-1:0] yx, rr;
        if (rst) begin
            s4_rect <= '0;
            fwd_sel <= 1'b1;                    // s4_old reads 0 after a reset, as its register did
            fwd_val <= '0;
            pool_rp <= '0;
        end else if (vld[ST_S3]) begin
            for (int k = 0; k < B_FILTERS; k++) begin
                y = '0;
                for (int r = 0; r < B_ROWS; r++) begin
                    if (row_used[r] && (row_filt[r] == k)) y = y + s3_row[r];
                end
                yx = y;                                 // sign-extended
                rr = (cfg_rect_abs && y[W_FILT-1]) ? -yx : yx;
                s4_rect[k*W_RECT +: W_RECT] <= rr;
            end
            // The value the pool will drop for this frame is the one written P frames ago. With a
            // pool of 1 and frames on consecutive clocks that is being written at this very edge:
            // the memory's read gives the word before it, so the word being written is kept here
            // and chosen after the read.
            fwd_sel <= vld[ST_S4] && (pool_wp == pool_rp);
            fwd_val <= s4_rect;
            pool_rp <= (pool_rp == cfg_pool - 1) ? {PTR_BITS{1'b0}} : pool_rp + 1'b1;
        end
    end

    // The pool's read: the memory's own output register, loaded where s4_old's register was and with
    // no reset, so that synthesis can take it into the memory. s4_old is the choice after it: at
    // every edge the value its register had (docs/rtl/poolram.md).
    always @(posedge clk) begin : st4_pool
        if (!rst && vld[ST_S3]) pool_q <= pool_mem[pool_rp];
    end
    assign s4_old = fwd_sel ? fwd_val : pool_q;

    // ------------------------------------------------------------------ s5: the pool's moving sum
    always @(posedge clk) begin : st5
        logic signed [W_POOL-1:0] zz, rx, ox;
        if (rst) begin
            z_flat    <= '0;
            pool_wp   <= '0;
            pool_fill <= '0;
        end else if (vld[ST_S4]) begin
            for (int k = 0; k < B_FILTERS; k++) begin
                zz = $signed(z_flat[k*W_POOL +: W_POOL]);
                rx = $signed(s4_rect[k*W_RECT +: W_RECT]);      // sign-extended to the pool's width
                ox = $signed(s4_old[k*W_RECT +: W_RECT]);
                // Until P frames have gone by there is no oldest value: the model's window of zeros.
                if (pool_fill == cfg_pool) zz = zz + rx - ox;
                else                       zz = zz + rx;
                z_flat[k*W_POOL +: W_POOL] <= zz;
            end
            pool_mem[pool_wp] <= s4_rect;
            pool_wp <= (pool_wp == cfg_pool - 1) ? {PTR_BITS{1'b0}} : pool_wp + 1'b1;
            if (pool_fill != cfg_pool) pool_fill <= pool_fill + 1'b1;
        end
    end

    // ------------------------------------------------------------------ h0 to h4: the head
    core_head #(
        .SAMPLE_BITS(SAMPLE_BITS), .CHANNELS(CHANNELS), .B_FILTERS(B_FILTERS), .B_TAPS(B_TAPS), .B_ROWS(B_ROWS),
        .B_POOL(B_POOL), .B_HIDDEN(B_HIDDEN), .W_POOL(W_POOL), .W_HEAD(W_HEAD)
    ) u_head (
        .clk(clk), .rst(rst),
        .in_valid(vld[ST_S5]), .in_sel(tg[ST_S5][TAG_SEL]), .in_z(z_flat),
        .cfg_no_hidden(cfg_no_hidden), .cfg_hidden_shift(cfg_hidden_shift), .cfg_score_shift(cfg_score_shift),
        .cfg_between_abs(cfg_between_abs),
        .hid_a(hid_a), .hid_b(hid_b), .out_a(out_a), .out_b(out_b),
        .out_valid(head_valid), .out_overflow(head_overflow), .out_score(head_score)
    );

    // ------------------------------------------------------------------ rec: the record, and the sticky flag
    always @(posedge clk) begin : st_rec
        logic [SCORE_RECORD_BITS-1:0] rec_next;
        if (rst) begin
            out_valid  <= 1'b0;
            out_record <= '0;
            sticky     <= 1'b0;
        end else begin
            rec_next = '0;
            rec_next[SCORE_INDEX_LSB +: SCORE_INDEX_BITS] = tg[ST_H4][TAG_INDEX_LSB +: SCORE_INDEX_BITS];
            rec_next[SCORE_EPOCH_LSB +: SCORE_EPOCH_BITS] = tg[ST_H4][TAG_EPOCH_LSB +: SCORE_EPOCH_BITS];
            rec_next[SCORE_FLAGS_LSB + FLAG_SETTLING_BIT] = tg[ST_H4][TAG_SETTLE];
            rec_next[SCORE_FLAGS_LSB + FLAG_OVERFLOW_BIT] = sticky | head_overflow;   // sticky: this record and every later one
            rec_next[SCORE_SCORE_LSB +: SCORE_SCORE_BITS] = head_score;
            out_valid <= vld[ST_H4];
            if (vld[ST_H4]) begin
                out_record <= rec_next;
                sticky     <= sticky | head_overflow;
            end
        end
    end

    // ------------------------------------------------------------------ the read-only views (docs/rtl/krnl-learn.md)
    // Each port is an existing signal and nothing more: nothing in this module reads them.
    assign view_running     = running;
    assign view_next_index  = next_index;
    assign view_taps        = cfg_taps;
    assign view_filters     = cfg_filters;
    assign view_rows        = cfg_rows;
    assign view_pool        = cfg_pool;
    assign view_score_shift = cfg_score_shift;
    assign view_rect_abs    = cfg_rect_abs;
    assign view_no_hidden   = cfg_no_hidden;
    assign view_commit      = commit_valid;
    assign view_commit_at   = commit_at;
    assign view_partial     = ld_partial;
    assign view_active_sel  = active_sel;
    assign view_vld         = vld;
    genvar gv;
    generate
        for (gv = ST_S1; gv <= ST_H4; gv++) begin : view_tags
            assign view_tag_sel[gv] = tg[gv][TAG_SEL];
        end
    endgenerate
endmodule

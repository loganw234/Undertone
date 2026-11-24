// The source: seeded noise, as model/source.py's `Noise` defines it.
//
// Two steps, each the model's and nothing else's.
//
//   1. Words. SplitMix64 as a counter. The model's word i starts from
//      seed + GAMMA * (i + 1), modulo 2^64. This module makes the words in order
//      from word 0, so that number is a register, `acc`, which starts at
//      seed + GAMMA and gains GAMMA at each word: the same number, by an
//      addition. The two mixing multiplications are rtl/source/source_mulc.sv.
//   2. A word to a sample. The word's lowest bit is the sign. Its other 63
//      bits, u, are looked up: the magnitude is the number of table entries at
//      or below u. The table is a memory the host loads.
//
// Frame n, channel c is made from word n * CHANNELS + c: one engine makes the
// words in order and a channel counter puts each sample in its place.
//
// THE TABLE, and what is trusted. The host hands over the model's table
// WITHOUT ITS LAST ENTRY. That entry is 2^63, u is at most 2^63 - 1, so it is
// at or below no u and adds nothing to any count. The entries are written in
// order through src_table_entry after src_table_length has said how many there
// are. This module checks the table's SIZE and nothing of its content: a table
// that is not a Gaussian's, or whose entries are not in order, is not seen. For
// entries in order the stream is the model's lookup of what was loaded.
//
// THE SEARCH is STEPS comparisons, one a clock, whatever the data: pos = 0;
// for b from STEPS - 1 down to 0, cand = pos + 2^b, and pos = cand when
// cand <= length and entry[cand - 1] <= u.
//
// THE CLOCKS. One sample is SAMPLE_CLOCKS = 5 + STEPS clocks, 20 at the
// definition's MAX_NOISE_TABLE of 32767. Counted from the edge B at which `acc`
// takes this word's value:
//     B+1, B+2    the first mixing multiplication
//     B+3, B+4    the second; at B+4 the memory's first read is taken
//     B+5 ..      STEPS comparisons, the last at B+4+STEPS
//     B+5+STEPS   the sample goes into the frame; `acc` gains GAMMA: the next B
// So a frame is offered every SAMPLE_CLOCKS * CHANNELS clocks, out_valid high
// for one clock, and frame n is seen 1 + SAMPLE_CLOCKS * CHANNELS * (n + 1)
// clocks after the edge that takes the start write.
//
// THE REGISTERS are the block `source` of the definition, on the register port
// every block has (reg_valid, reg_we, reg_addr, reg_wdata, reg_rdata; the read
// is a register). Outside its block this module does nothing: a write is
// ignored and a read answers 0. Inside it every write is taken or refused:
//     src_seed            two words
//     src_table_length    begins a new table of that many entries, and clears
//                         the refusal. More than the build holds: NOISE_RANGE
//     src_table_entry     two words; the write of the upper word stores the
//                         entry at the next place. One more than the declared
//                         length: REGISTER_ACCESS
//     src_frames          two words; THE WRITE OF THE UPPER WORD STARTS THE RUN.
//                         With no table declared since rst, or with fewer
//                         entries written than declared: REGISTER_ACCESS. With
//                         a refusal latched it does nothing: the host clears,
//                         then starts
//     src_refusal         reads the first refusal since it was cleared; a write
//                         of 0 clears it, IN EVERY STATE, during a run too; a
//                         write of anything else is REGISTER_ACCESS
//     src_status          bit REG_SRC_STATUS_RUNNING_BIT: a run is going
//     cap_noise_table     the most entries this build takes
// A write to a read-only row, to an offset that holds no row, or to one that is
// not a multiple of the word's bytes is REGISTER_ACCESS. SO IS EVERY OTHER
// WRITE TO THIS BLOCK DURING A RUN, all but the write of 0 that clears the
// refusal: the write is not taken and the run goes on untouched.
//
// A table DECLARED with no entries is a table: it is content, and every sample
// is then 0. A start with NO table declared since rst is a host that forgot,
// and is refused.
//
// word_valid and word put out each word as its sample is made. They are for
// the bench: a sample is a lossy view of a word. Nothing else reads them.
//
// WHAT IT DOES NOT DO, each a stated limit of docs/rtl/source.md: it starts at
// word 0 only; it does not check that frames * CHANNELS is within the 2^64
// words (the host library's STREAM_LENGTH); it has one lookup engine, so a
// frame is not offered every clock; it has never been synthesised.
`timescale 1ns / 1ps

module source #(
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
    output logic                                       out_valid,
    output logic [CHANNELS*SAMPLE_BITS-1:0]            out_frame,  // channel c at [c*SAMPLE_BITS +: SAMPLE_BITS]
    output logic                                       word_valid,
    output logic [63:0]                                word
);
    import undertone_pkg::*;

    // The increment of the counter. The two mixing constants are at the two multipliers below.
    // These three and the shifts 30, 27 and 31 are model/source.py's, lines 45 to 47 and 76 to 78.
    localparam logic [63:0] GAMMA = 64'h9E3779B97F4A7C15;

    localparam int STEPS         = $clog2(MAX_NOISE_TABLE + 1);
    localparam int PH_FIRST_READ = 3;
    localparam int PH_EMIT       = 4 + STEPS;
    localparam int SAMPLE_MAX    = (1 << (SAMPLE_BITS - 1)) - 1;
    localparam int LARGEST_INT   = (MAX_NOISE_TABLE < SAMPLE_MAX) ? MAX_NOISE_TABLE : SAMPLE_MAX;

    localparam logic [31:0] LARGEST = LARGEST_INT;
    localparam logic [7:0]  CODE_NOISE_RANGE = REFUSAL_NOISE_RANGE;
    localparam logic [7:0]  CODE_ACCESS      = REFUSAL_REGISTER_ACCESS;

    // ---- the registers ----
    logic [63:0]    seed;
    logic [31:0]    frames_low;
    logic [31:0]    entry_low;
    logic [STEPS:0] table_len;      // the declared length
    logic [STEPS:0] table_place;    // how many entries have been written
    logic           table_declared; // a src_table_length has been taken since rst
    logic [7:0]     refusal;
    logic           running;

    // ---- the engine ----
    logic [63:0]    frames_left;
    logic [7:0]     ph;             // the clock within a sample
    logic [7:0]     chan;
    logic [63:0]    acc;
    logic [STEPS:0] pos;
    logic [7:0]     bitsel;
    logic [CHANNELS*SAMPLE_BITS-1:0] frame_acc;

    logic [63:0] table_mem [0:(1 << STEPS) - 1];
    logic [63:0] mem_q;

    logic [63:0] x1, y1, x2, y2, w;
    logic [62:0] u;

    assign x1 = acc ^ (acc >> 30);
    assign x2 = y1 ^ (y1 >> 27);
    assign w  = y2 ^ (y2 >> 31);
    assign u  = w[63:1];

    source_mulc #(.K(64'hBF58476D1CE4E5B9)) mul1 (.clk(clk), .x(x1), .y(y1));
    source_mulc #(.K(64'h94D049BB133111EB)) mul2 (.clk(clk), .x(x2), .y(y2));

    // ---- the search's one step ----
    logic [STEPS:0] onehot, half, cand, pos_next, mem_addr;
    logic           take;

    always_comb begin
        onehot   = {{STEPS{1'b0}}, 1'b1} << bitsel;
        half     = onehot >> 1;
        cand     = pos + onehot;
        take     = (cand <= table_len) && (mem_q <= {1'b0, u});
        pos_next = take ? cand : pos;
        if (ph == PH_FIRST_READ) mem_addr = (1 << (STEPS - 1)) - 1;
        else                     mem_addr = pos_next + half - 1'b1;
    end

    // ---- the sample, and the frame it goes into ----
    logic [SAMPLE_BITS-1:0]          mag, sample;
    logic [CHANNELS*SAMPLE_BITS-1:0] frame_next;

    always_comb begin
        mag    = pos;
        sample = w[0] ? (~mag + 1'b1) : mag;
        frame_next = frame_acc;
        frame_next[chan*SAMPLE_BITS +: SAMPLE_BITS] = sample;
    end

    // ---- what a write is ----
    logic [31:0] addr;
    logic        in_block, wr, rd;
    logic [7:0]  wr_code;
    logic        wr_seed_low, wr_seed_high, wr_frames_low, wr_start, wr_length, wr_entry_low, wr_entry_high, wr_clear;

    assign addr     = {{(32 - BUS_ADDRESS_BITS){1'b0}}, reg_addr};
    assign in_block = (addr >= BLOCK_SOURCE_FIRST) && (addr < BLOCK_SOURCE_END);
    assign wr       = reg_valid && reg_we && in_block;
    assign rd       = reg_valid && !reg_we;

    always_comb begin
        wr_code       = 8'd0;
        wr_seed_low   = 1'b0;
        wr_seed_high  = 1'b0;
        wr_frames_low = 1'b0;
        wr_start      = 1'b0;
        wr_length     = 1'b0;
        wr_entry_low  = 1'b0;
        wr_entry_high = 1'b0;
        wr_clear      = 1'b0;
        if (wr) begin
            if (addr == REG_SRC_REFUSAL_OFFSET) begin
                if (reg_wdata == 32'd0) wr_clear = 1'b1;        // taken in every state, during a run too
                else                    wr_code  = CODE_ACCESS;
            end else if (running) begin
                wr_code = CODE_ACCESS;                          // no other write is taken during a run
            end else begin
                case (addr)
                    REG_SRC_SEED_OFFSET:         wr_seed_low   = 1'b1;
                    REG_SRC_SEED_OFFSET + 4:     wr_seed_high  = 1'b1;
                    REG_SRC_FRAMES_OFFSET:       wr_frames_low = 1'b1;
                    REG_SRC_FRAMES_OFFSET + 4: begin
                        if (refusal != 8'd0)                wr_start = 1'b0;      // a refusal is latched: nothing
                        else if (!table_declared)           wr_code  = CODE_ACCESS;
                        else if (table_place != table_len)  wr_code  = CODE_ACCESS;
                        else                                wr_start = 1'b1;
                    end
                    REG_SRC_TABLE_LENGTH_OFFSET: begin
                        if (reg_wdata > LARGEST) wr_code   = CODE_NOISE_RANGE;
                        else                     wr_length = 1'b1;
                    end
                    REG_SRC_TABLE_ENTRY_OFFSET:  wr_entry_low  = 1'b1;
                    REG_SRC_TABLE_ENTRY_OFFSET + 4: begin
                        if (table_place == table_len) wr_code       = CODE_ACCESS;
                        else                          wr_entry_high = 1'b1;
                    end
                    default:                     wr_code = CODE_ACCESS;           // read-only, no row, or not a word's offset
                endcase
            end
        end
    end

    always_ff @(posedge clk) begin
        if (rst) begin
            seed        <= 64'd0;
            frames_low  <= 32'd0;
            entry_low   <= 32'd0;
            table_len   <= '0;
            table_place <= '0;
            table_declared <= 1'b0;
            refusal     <= 8'd0;
            running     <= 1'b0;
            frames_left <= 64'd0;
            ph          <= 8'd0;
            chan        <= 8'd0;
            acc         <= 64'd0;
            pos         <= '0;
            bitsel      <= 8'd0;
            frame_acc   <= '0;
            mem_q       <= 64'd0;
            reg_rdata   <= '0;
            out_valid   <= 1'b0;
            out_frame   <= '0;
            word_valid  <= 1'b0;
            word        <= 64'd0;
        end else begin
            out_valid  <= 1'b0;
            word_valid <= 1'b0;
            mem_q      <= table_mem[mem_addr[STEPS-1:0]];

            // ---- writes that are taken ----
            if (wr_seed_low)   seed[31:0]  <= reg_wdata;
            if (wr_seed_high)  seed[63:32] <= reg_wdata;
            if (wr_frames_low) frames_low  <= reg_wdata;
            if (wr_entry_low)  entry_low   <= reg_wdata;
            if (wr_length) begin
                table_len      <= reg_wdata[STEPS:0];
                table_place    <= '0;
                table_declared <= 1'b1;
            end
            if (wr_entry_high) begin
                table_mem[table_place[STEPS-1:0]] <= {reg_wdata, entry_low};
                table_place <= table_place + 1'b1;
            end

            // ---- the refusal register: the first refusal stands ----
            if (wr_clear || wr_length)                      refusal <= 8'd0;
            else if (wr_code != 8'd0 && refusal == 8'd0)    refusal <= wr_code;

            // ---- reads ----
            if (rd) begin
                if (!in_block) begin
                    reg_rdata <= '0;
                end else begin
                    case (addr)
                        REG_SRC_STATUS_OFFSET:      reg_rdata <= {31'd0, running} << REG_SRC_STATUS_RUNNING_BIT;
                        REG_SRC_REFUSAL_OFFSET:     reg_rdata <= {24'd0, refusal};
                        REG_CAP_NOISE_TABLE_OFFSET: reg_rdata <= LARGEST;
                        default:                    reg_rdata <= '0;
                    endcase
                end
            end

            // ---- the start ----
            if (wr_start) begin
                frames_left <= {reg_wdata, frames_low};
                acc         <= seed + GAMMA;
                ph          <= 8'd0;
                chan        <= 8'd0;
                if ({reg_wdata, frames_low} != 64'd0) running <= 1'b1;
            end

            // ---- the engine ----
            if (running) begin
                ph <= ph + 8'd1;
                if (ph == PH_FIRST_READ) begin
                    pos    <= '0;
                    bitsel <= STEPS - 1;
                end else if (ph > PH_FIRST_READ && ph < PH_EMIT) begin
                    pos    <= pos_next;
                    bitsel <= bitsel - 8'd1;
                end else if (ph == PH_EMIT) begin
                    ph         <= 8'd0;
                    word       <= w;
                    word_valid <= 1'b1;
                    frame_acc  <= frame_next;
                    acc        <= acc + GAMMA;
                    if (chan == CHANNELS - 1) begin
                        chan        <= 8'd0;
                        out_valid   <= 1'b1;
                        out_frame   <= frame_next;
                        frames_left <= frames_left - 64'd1;
                        if (frames_left == 64'd1) running <= 1'b0;
                    end else begin
                        chan <= chan + 8'd1;
                    end
                end
            end
        end
    end
endmodule

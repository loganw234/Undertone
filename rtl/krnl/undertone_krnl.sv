// The kernel: the chain of round 2 behind an AXI4-Lite slave, writing every score record to memory.
//
// Parcel KRNL, round 3. docs/rtl/krnl.md is the account; this header is what a reader needs to read
// the lines. The reference model is the authority: every score word this writes is held against
// model/run.py's by the benches rtl/tb/bench_krnl*.py.
//
// THE CHAIN. The source, the injector and the detector core of round 2, wired as rtl/seam/seam.sv
// wires them: the source's frames to the injector, the injector's to the core, and the core's score
// records to this kernel's queue. The core is built at this top's maxima, the parameters B_*: their
// defaults are the FIRST BUILD's (4 filters, 4 rows, 128 taps, 12 hidden units, the definition's
// other maxima; Logan's word on the round's plan, question 2).
//
// THE LEARNER (round 5, docs/rtl/krnl-learn.md): rtl/learn/learn.sv beside the core, built at the
// core's B_TAPS and the definition's count bits and update time. It is handed the frames the core
// takes, on the core's own wires; the core's state through the core's read-only view ports; and of
// each truth record the injector takes into its store, the index alone (the injector's view ports).
// Its only way to the core is the core's own register port, through rtl/learn/learn_port.sv, at an
// update the host named. The core's and the injector's view ports only expose signals each block
// already had; no behaviour of either changed.
//
// THE REGISTER PORT. One AXI4-Lite slave, s_axi_control, of the definition's word and address
// bits. It takes one operation at a time, a write when both its address and its data are in hand,
// else a read, and answers OKAY to every one: a refusal is latched in a register, as every block
// does. A write goes ONLY to the block whose range holds its address, so the injector's truth rows
// never reach the core's port or the learner's; the learner also sees the core's range, which it
// needs to count a commit it held back. A read goes to all four, and each answers 0 outside its own
// range. The core's port is learn_port's: the host's access the kernel routes to the core, and in a
// clock with none the learner's write; while an update is unfinished the host's commit, shadow_begin
// and shadow_data are held back, and the learner latches UPDATE_UNFINISHED in lrn_refusal.
// What this kernel takes for itself and does not forward:
//     a write whose strobes are not all four bytes        REGISTER_ACCESS (no block has byte enables)
//     a write below the definition's first offset         REGISTER_ACCESS (nothing sits there)
//     a write of src_frames                               REGISTER_ACCESS (it is the kernel's to write)
//     every operation inside the block `kernel`           its rows, below
// A read below the first offset answers 0.
//
// THE KERNEL'S ROWS (the block `kernel` of the definition). The protocol is Vitis's user-managed
// one: XRT writes none of these, the host writes them all.
//     krn_buffer, krn_size, krn_frames   the run's arguments. Written while a run goes: KERNEL_BUSY
//     krn_start     a write of 1. In this order: anything but 1, REGISTER_ACCESS; a run going,
//                   KERNEL_BUSY; then `done` falls; a refusal latched, the start is not taken and
//                   nothing more is latched (the host clears, then starts); krn_frames 0,
//                   STREAM_LENGTH; krn_buffer not a slot's multiple, BUFFER_ALIGN; krn_size under
//                   krn_frames slots, or the slots past 2^64, BUFFER_SIZE. Then this kernel writes
//                   src_frames (the upper word starts the source) and reads src_status back: a
//                   source that does not say it runs, RUN_START. Else the run goes. The write's
//                   answer comes when all that is decided
//     krn_reset     a write of 1: the four blocks are reset, and the run's state with them; the
//                   arguments are kept. A run going: KERNEL_BUSY
//     krn_status    running, done, refused (the definition's bits)
//     krn_refusal   the first refusal since it was cleared; a write of 0 clears it, in every state
//     krn_records   records written and answered OKAY, in order, from slot 0. A read of the lower
//                   word holds the upper, so the two are of one moment
//     krn_queue_peak, cap_record_queue   the most records the queue held in the run; its depth
//
// THE RUN. Every score record the core puts out during a run goes into a queue of RECORD_QUEUE
// records, and from there to memory: record n to the slot at krn_buffer + n * slot_bytes, its
// canonical bytes and then zeros. A record arriving with no run going, or past krn_frames records:
// RUN_LENGTH. One arriving with the queue full: RECORD_QUEUE, and from then on no record of the run
// is queued (the ones queued are still written). An answer other than OKAY: MEMORY_WRITE, and no
// burst is issued after it. A burst is as many queued records as no burst has taken, at most
// BURST, never across a 4 KB page; one burst out at a time, its address and its data offered
// together, the data never waiting for the address to be taken; up to OUTS unanswered.
//
// DONE rises only with the chain idle: the source has put out krn_frames frames, DRAIN clocks have
// passed since (the injector's 52 and the core's 11 clocks, twice over), every queued record is
// written (or abandoned after MEMORY_WRITE), and every burst is answered. Then, with no refusal of
// the run's own, a count of records answered other than krn_frames is RUN_LENGTH: the chain stopped
// short, and a block's own refusal register says why. The learner's refusals are its own register's,
// lrn_refusal: none sets krn_status's refused bit, latches in krn_refusal or ends a run.
//
// WHAT IT DOES NOT DO, each a stated limit of docs/rtl/krnl.md: it reads no memory, so truth records
// come from the host through the injector's rows; it holds no run past a refusal of its own; it does
// not stop the source. Round 3's version, without the learner, was packaged, linked and run on the
// card (docs/rtl/krnl.md, section 7); this version, with the learner, has been read by Icarus Verilog
// alone.
`timescale 1ns / 1ps

// THE PORT LIST AND THE PARAMETERS' DEFAULTS ARE PLAIN NUMBERS, never the package's names. Vivado's
// IP packager reads `undertone_pkg::NAME` there as a parameter named undertone_pkg and refuses to
// package (round 3, the lead's trial of 2026-11-24 11:06). Each number is the definition's:
// tests/test_krnl_packaging.py holds every one to spec/constants.py, and the initial block below
// stops a simulation whose port widths part from the package's. The body may use the package.
module undertone_krnl #(
    parameter int SAMPLE_BITS    = 16,        // the first build's profile, s16x1
    parameter int CHANNELS       = 1,
    // the first build's maxima (the round's plan, question 2); none may pass the definition's
    parameter int B_FILTERS      = 4,
    parameter int B_TAPS         = 128,
    parameter int B_ROWS         = 4,
    parameter int B_POOL         = 65536,     // the definition's max_pool
    parameter int B_SCORE_SHIFT  = 31,        // the definition's max_score_shift
    parameter int B_HIDDEN       = 12,
    parameter int B_HIDDEN_SHIFT = 31,        // the definition's max_hidden_shift
    // the queue between the core and memory, in records: a power of two
    parameter int RECORD_QUEUE   = 512
) (
    input  logic                                        ap_clk,
    input  logic                                        ap_rst_n,     // active low, synchronous
    // the AXI4-Lite slave: [bus] address_bits 12, word_bits 32
    input  logic [11:0]                                 s_axi_control_awaddr,
    input  logic                                        s_axi_control_awvalid,
    output logic                                        s_axi_control_awready,
    input  logic [31:0]                                 s_axi_control_wdata,
    input  logic [3:0]                                  s_axi_control_wstrb,
    input  logic                                        s_axi_control_wvalid,
    output logic                                        s_axi_control_wready,
    output logic [1:0]                                  s_axi_control_bresp,
    output logic                                        s_axi_control_bvalid,
    input  logic                                        s_axi_control_bready,
    input  logic [11:0]                                 s_axi_control_araddr,
    input  logic                                        s_axi_control_arvalid,
    output logic                                        s_axi_control_arready,
    output logic [31:0]                                 s_axi_control_rdata,
    output logic [1:0]                                  s_axi_control_rresp,
    output logic                                        s_axi_control_rvalid,
    input  logic                                        s_axi_control_rready,
    // the AXI4 master: writes only; its read channels are tied off. Data: [memory] slot_bytes 32, a slot a beat
    output logic [0:0]                                  m_axi_gmem_awid,
    output logic [63:0]                                 m_axi_gmem_awaddr,
    output logic [7:0]                                  m_axi_gmem_awlen,
    output logic [2:0]                                  m_axi_gmem_awsize,
    output logic [1:0]                                  m_axi_gmem_awburst,
    output logic [0:0]                                  m_axi_gmem_awlock,
    output logic [3:0]                                  m_axi_gmem_awcache,
    output logic [2:0]                                  m_axi_gmem_awprot,
    output logic [3:0]                                  m_axi_gmem_awqos,
    output logic                                        m_axi_gmem_awvalid,
    input  logic                                        m_axi_gmem_awready,
    output logic [255:0]                                m_axi_gmem_wdata,
    output logic [31:0]                                 m_axi_gmem_wstrb,
    output logic                                        m_axi_gmem_wlast,
    output logic                                        m_axi_gmem_wvalid,
    input  logic                                        m_axi_gmem_wready,
    input  logic [0:0]                                  m_axi_gmem_bid,
    input  logic [1:0]                                  m_axi_gmem_bresp,
    input  logic                                        m_axi_gmem_bvalid,
    output logic                                        m_axi_gmem_bready,
    output logic [0:0]                                  m_axi_gmem_arid,
    output logic [63:0]                                 m_axi_gmem_araddr,
    output logic [7:0]                                  m_axi_gmem_arlen,
    output logic [2:0]                                  m_axi_gmem_arsize,
    output logic [1:0]                                  m_axi_gmem_arburst,
    output logic [0:0]                                  m_axi_gmem_arlock,
    output logic [3:0]                                  m_axi_gmem_arcache,
    output logic [2:0]                                  m_axi_gmem_arprot,
    output logic [3:0]                                  m_axi_gmem_arqos,
    output logic                                        m_axi_gmem_arvalid,
    input  logic                                        m_axi_gmem_arready,
    input  logic [0:0]                                  m_axi_gmem_rid,
    input  logic [255:0]                                m_axi_gmem_rdata,
    input  logic [1:0]                                  m_axi_gmem_rresp,
    input  logic                                        m_axi_gmem_rlast,
    input  logic                                        m_axi_gmem_rvalid,
    output logic                                        m_axi_gmem_rready
);
    import undertone_pkg::*;

    localparam int A          = BUS_ADDRESS_BITS;
    localparam int WORD       = BUS_WORD_BITS;
    localparam int WBYTES     = BUS_WORD_BITS / 8;
    localparam int REC        = SCORE_RECORD_BITS;
    localparam int DATA       = 8 * MEMORY_SLOT_BYTES;
    localparam int SLOT_SHIFT = $clog2(MEMORY_SLOT_BYTES);
    localparam int W          = CHANNELS * SAMPLE_BITS;
    localparam int QB         = $clog2(RECORD_QUEUE);
    localparam int CODE       = 8;          // a refusal's number fits a byte, by the definition's rule
    localparam int BURST      = 16;         // records a burst at most
    localparam int PAGE_BITS  = 12;         // AXI: no burst crosses a 4 KB boundary
    localparam int OUTS       = 16;         // bursts unanswered at once
    localparam int OB         = 4;          // log2 of OUTS
    localparam int DRAIN      = 128;        // clocks after the source's last frame
    localparam int RST_CLOCKS = 4;          // clocks the chain is held in reset by krn_reset

    // the definition's numbers, at their widths
    localparam logic [CODE-1:0] C_ACCESS = REFUSAL_REGISTER_ACCESS;
    localparam logic [CODE-1:0] C_BUSY   = REFUSAL_KERNEL_BUSY;
    localparam logic [CODE-1:0] C_LENGTH = REFUSAL_STREAM_LENGTH;
    localparam logic [CODE-1:0] C_ALIGN  = REFUSAL_BUFFER_ALIGN;
    localparam logic [CODE-1:0] C_SIZE   = REFUSAL_BUFFER_SIZE;
    localparam logic [CODE-1:0] C_START  = REFUSAL_RUN_START;
    localparam logic [CODE-1:0] C_QUEUE  = REFUSAL_RECORD_QUEUE;
    localparam logic [CODE-1:0] C_MEMORY = REFUSAL_MEMORY_WRITE;
    localparam logic [CODE-1:0] C_RUN    = REFUSAL_RUN_LENGTH;

    initial begin
        if (RECORD_QUEUE < 2 || (1 << QB) != RECORD_QUEUE || DATA < REC || (1 << SLOT_SHIFT) != MEMORY_SLOT_BYTES
                || REG_KRN_BUFFER_WORDS != 2 || REG_KRN_SIZE_WORDS != 2 || REG_KRN_FRAMES_WORDS != 2
                || REG_KRN_RECORDS_WORDS != 2 || REG_SRC_FRAMES_WORDS != 2 || WORD != 32) begin
            $fatal(1, "undertone_krnl: the queue is not a power of two, or the definition no longer fits this kernel");
        end
        // The port list's numbers against the package's (see the note above the module).
        if ($bits(s_axi_control_awaddr) != BUS_ADDRESS_BITS || $bits(s_axi_control_araddr) != BUS_ADDRESS_BITS
                || $bits(s_axi_control_wdata) != BUS_WORD_BITS || $bits(s_axi_control_rdata) != BUS_WORD_BITS
                || $bits(s_axi_control_wstrb) != BUS_WORD_BITS / 8 || $bits(m_axi_gmem_wdata) != DATA
                || $bits(m_axi_gmem_rdata) != DATA || $bits(m_axi_gmem_wstrb) != MEMORY_SLOT_BYTES) begin
            $fatal(1, "undertone_krnl: a port's width written in the port list is not the definition's");
        end
    end
`ifndef SYNTHESIS
    // Simulation only: `v_closed` below takes core.sv's stages ST_S1 to ST_CLOSED_LAST as 1 to 7.
    initial begin
        if (u_core.ST_S1 != 1 || u_core.ST_CLOSED_LAST != 7) begin
            $fatal(1, "undertone_krnl: core.sv's stages that read weights at a later edge are not 1 to 7, as v_closed takes them");
        end
    end
`endif

    // ------------------------------------------------------------------ the register bus to the chain
    logic              bus_valid, bus_we;
    logic [A-1:0]      bus_addr;
    logic [WORD-1:0]   bus_wdata;
    logic              chain_rst_req;
    wire               chain_rst = !ap_rst_n || chain_rst_req;
    wire  [A:0]        bus_at = {1'b0, bus_addr};
    wire               hit_core   = (bus_at >= BLOCK_CORE_FIRST)   && (bus_at < BLOCK_CORE_END);
    wire               hit_source = (bus_at >= BLOCK_SOURCE_FIRST) && (bus_at < BLOCK_SOURCE_END);
    wire               hit_inject = (bus_at >= BLOCK_INJECT_FIRST) && (bus_at < BLOCK_INJECT_END);
    wire               hit_learner = (bus_at >= BLOCK_LEARNER_FIRST) && (bus_at < BLOCK_LEARNER_END);
    // A write reaches only the block whose range holds it, and the learner the core's range besides (it
    // counts a commit it held back). A read reaches all four.
    wire               core_valid   = bus_valid && (!bus_we || hit_core);
    wire               source_valid = bus_valid && (!bus_we || hit_source);
    wire               inject_valid = bus_valid && (!bus_we || hit_inject);
    wire               learn_valid  = bus_valid && (!bus_we || hit_learner || hit_core);

    // ------------------------------------------------------------------ the chain
    logic            src_valid, inj_valid, rec_valid;
    logic [W-1:0]    src_frame, inj_frame, core_frame;
    logic [WORD-1:0] src_rdata, inj_rdata, core_rdata, learn_rdata;
    logic [REC-1:0]  rec_word;
    // the core's register port, as learn_port hands it over
    logic            c_valid, c_we;
    logic [A-1:0]    c_addr;
    logic [WORD-1:0] c_wdata;
    // learn_port and the learner, to each other
    logic            lp_hold, lp_intercept, lp_host, l_hold_q, l_hold_end_q, l_lw_valid;
    logic [A-1:0]    l_lw_addr;
    logic [WORD-1:0] l_lw_wdata;
    // the injector's truth, by its view ports: a record taken into its store at this edge, and its index
    logic                        t_push;
    logic [TRUTH_INDEX_BITS-1:0] t_index;
    // the core's state, by its view ports
    logic                        v_running, v_rect_abs, v_no_hidden, v_commit, v_partial, v_active_sel;
    logic [SCORE_INDEX_BITS-1:0] v_next, v_commit_at;
    logic [WORD-1:0]             v_taps, v_filters, v_rows, v_pool, v_shift;
    logic [10:1]                 v_vld, v_tag_sel;            // every stage of the core's pipeline, 1 to 10

    assign core_frame = inj_frame;          // the core is handed the injector's frame, and nothing else

    source #(
        .SAMPLE_BITS(SAMPLE_BITS),
        .CHANNELS(CHANNELS)
    ) u_source (
        .clk(ap_clk),
        .rst(chain_rst),
        .reg_valid(source_valid),
        .reg_we(bus_we),
        .reg_addr(bus_addr),
        .reg_wdata(bus_wdata),
        .reg_rdata(src_rdata),
        .out_valid(src_valid),
        .out_frame(src_frame),
        .word_valid(),
        .word()
    );

    inject #(
        .SAMPLE_BITS(SAMPLE_BITS),
        .CHANNELS(CHANNELS)
    ) u_inject (
        .clk(ap_clk),
        .rst(chain_rst),
        .reg_valid(inject_valid),
        .reg_we(bus_we),
        .reg_addr(bus_addr),
        .reg_wdata(bus_wdata),
        .reg_rdata(inj_rdata),
        .in_valid(src_valid),
        .in_frame(src_frame),
        .out_valid(inj_valid),
        .out_frame(inj_frame),
        .view_push(t_push),
        .view_index(t_index)
    );

    core #(
        .SAMPLE_BITS(SAMPLE_BITS),
        .CHANNELS(CHANNELS),
        .B_FILTERS(B_FILTERS),
        .B_TAPS(B_TAPS),
        .B_ROWS(B_ROWS),
        .B_POOL(B_POOL),
        .B_SCORE_SHIFT(B_SCORE_SHIFT),
        .B_HIDDEN(B_HIDDEN),
        .B_HIDDEN_SHIFT(B_HIDDEN_SHIFT)
    ) u_core (
        .clk(ap_clk),
        .rst(chain_rst),
        .in_valid(inj_valid),
        .in_frame(core_frame),
        .out_valid(rec_valid),
        .out_record(rec_word),
        .reg_valid(c_valid),
        .reg_we(c_we),
        .reg_addr(c_addr),
        .reg_wdata(c_wdata),
        .reg_rdata(core_rdata),
        .view_running(v_running),
        .view_next_index(v_next),
        .view_taps(v_taps),
        .view_filters(v_filters),
        .view_rows(v_rows),
        .view_pool(v_pool),
        .view_score_shift(v_shift),
        .view_rect_abs(v_rect_abs),
        .view_no_hidden(v_no_hidden),
        .view_commit(v_commit),
        .view_commit_at(v_commit_at),
        .view_partial(v_partial),
        .view_active_sel(v_active_sel),
        .view_vld(v_vld),
        .view_tag_sel(v_tag_sel)
    );

    // ------------------------------------------------------------------ the learner and the core's shared port
    // `closed` as the core's own status read works it: a frame of the stages that still read weights at a
    // later edge, 1 to 7 (core.sv's ST_S1 to ST_CLOSED_LAST, retyped here as learn_chain.sv does), carries the
    // other bank. `take`: the core takes a frame at this edge.
    wire v_closed = |(v_vld[7:1] & (v_tag_sel[7:1] ^ {7{v_active_sel}}));
    wire l_take   = inj_valid && v_running;

    learn_port u_port (
        .reg_valid(core_valid),
        .reg_we(bus_we),
        .reg_addr(bus_addr),
        .reg_wdata(bus_wdata),
        .take(l_take),
        .hold_q(l_hold_q),
        .hold_end_q(l_hold_end_q),
        .lw_valid(l_lw_valid),
        .lw_addr(l_lw_addr),
        .lw_wdata(l_lw_wdata),
        .hold(lp_hold),
        .intercept(lp_intercept),
        .host(lp_host),
        .c_valid(c_valid),
        .c_we(c_we),
        .c_addr(c_addr),
        .c_wdata(c_wdata)
    );

    learn #(
        .SAMPLE_BITS(SAMPLE_BITS),
        .CHANNELS(CHANNELS),
        .B_TAPS(B_TAPS),
        .B_COUNT_BITS(LEARN_COUNT_BITS),
        .B_UPDATE_FRAMES(LEARN_UPDATE_FRAMES)
    ) u_learn (
        .clk(ap_clk),
        .rst(chain_rst),
        .in_valid(inj_valid),
        .in_frame(core_frame),
        .core_running(v_running),
        .core_next_index(v_next),
        .core_taps(v_taps),
        .core_filters(v_filters),
        .core_rows(v_rows),
        .core_pool(v_pool),
        .core_score_shift(v_shift),
        .core_rect_abs(v_rect_abs),
        .core_no_hidden(v_no_hidden),
        .core_commit(v_commit),
        .core_commit_at(v_commit_at),
        .core_partial(v_partial),
        .core_closed(v_closed),
        .truth_valid(t_push),
        .truth_index(t_index),
        .reg_valid(learn_valid),
        .reg_we(bus_we),
        .reg_addr(bus_addr),
        .reg_wdata(bus_wdata),
        .reg_rdata(learn_rdata),
        .port_hold(lp_hold),
        .port_intercept(lp_intercept),
        .port_host(lp_host),
        .hold_q(l_hold_q),
        .hold_end_q(l_hold_end_q),
        .lw_valid(l_lw_valid),
        .lw_addr(l_lw_addr),
        .lw_wdata(l_lw_wdata)
    );

    // ------------------------------------------------------------------ the kernel's state
    // the AXI4-Lite slave
    logic            have_aw, have_w, have_ar;
    logic [A-1:0]    aw_q, ar_q;
    logic [WORD-1:0] w_q;
    logic [WBYTES-1:0] s_q;
    logic [3:0]      st;
    logic [2:0]      rst_left;
    localparam logic [3:0] S_IDLE = 4'd0, S_WR = 4'd1, S_RD = 4'd2, S_RD_TAKE = 4'd3, S_B = 4'd4, S_R = 4'd5,
                           S_LO = 4'd6, S_HI = 4'd7, S_ST = 4'd8, S_ST_CHK = 4'd9, S_RST = 4'd10;

    // the arguments, the run, the refusal
    logic [63:0]     k_buffer, k_size, k_frames;
    logic            running, done, halted, mem_err;
    logic [CODE-1:0] refusal;
    logic [63:0]     src_count, rec_in, answered, issued;
    logic [7:0]      drain_left;
    logic [WORD-1:0] rec_hold;               // krn_records' upper word, held by a read of its lower
    logic [QB:0]     peak;

    // the queue: records wp - rp held; wp - ip of them taken by no burst yet
    logic [REC-1:0]  q_mem [0:RECORD_QUEUE-1];
    logic [QB:0]     wp, rp, ip;
    wire  [QB:0]     q_count  = wp - rp;
    wire  [QB:0]     unissued = wp - ip;

    // the writer: one burst out at a time, its address and its data offered together. AXI4, section
    // A3.3.1, as remembered (BELIEVED, the specification not read): a master must not wait for AWREADY
    // or WREADY before raising AWVALID or WVALID, and a slave may wait for WVALID before raising
    // AWREADY. So the data never waits for the address to be taken (w_gate), and may lead it. The first
    // version raised WVALID only after AWREADY, and a memory that waits for WVALID hung it (VKRNL).
    // The lengths of the bursts not yet answered are kept from the moment each is offered.
    logic            wr;
    localparam logic WR_IDLE = 1'b0, WR_BUSY = 1'b1;
    logic            aw_done;           // this burst's address is taken
    logic            w_on;              // this burst's data is offered
    wire             w_gate = 1'b1;     // the data does not wait for the address
    logic [4:0]      beats_left;
    logic [4:0]      o_len [0:OUTS-1];
    logic [OB:0]     ow, orr;
    wire  [OB:0]     outs = ow - orr;
    assign m_axi_gmem_wvalid = w_on && w_gate;

    // what the master puts out that never changes
    assign m_axi_gmem_awid    = 1'b0;
    assign m_axi_gmem_awsize  = SLOT_SHIFT;
    assign m_axi_gmem_awburst = 2'b01;      // INCR
    assign m_axi_gmem_awlock  = 1'b0;
    assign m_axi_gmem_awcache = 4'b0011;
    assign m_axi_gmem_awprot  = 3'b000;
    assign m_axi_gmem_awqos   = 4'b0000;
    assign m_axi_gmem_wstrb   = {MEMORY_SLOT_BYTES{1'b1}};
    assign m_axi_gmem_wdata   = {{(DATA-REC){1'b0}}, q_mem[rp[QB-1:0]]};
    assign m_axi_gmem_wlast   = (beats_left == 5'd1);
    assign m_axi_gmem_bready  = 1'b1;
    assign m_axi_gmem_arid    = 1'b0;
    assign m_axi_gmem_araddr  = 64'd0;
    assign m_axi_gmem_arlen   = 8'd0;
    assign m_axi_gmem_arsize  = SLOT_SHIFT;
    assign m_axi_gmem_arburst = 2'b01;
    assign m_axi_gmem_arlock  = 1'b0;
    assign m_axi_gmem_arcache = 4'b0011;
    assign m_axi_gmem_arprot  = 3'b000;
    assign m_axi_gmem_arqos   = 4'b0000;
    assign m_axi_gmem_arvalid = 1'b0;
    assign m_axi_gmem_rready  = 1'b1;

    assign s_axi_control_awready = !have_aw;
    assign s_axi_control_wready  = !have_w;
    assign s_axi_control_arready = !have_ar;
    assign s_axi_control_bresp   = 2'b00;
    assign s_axi_control_rresp   = 2'b00;

    // the word a read of the kernel's own block answers
    function automatic logic [WORD-1:0] own_word(input logic [A:0] at);
        logic [WORD-1:0] st_word;
        st_word = '0;
        st_word[REG_KRN_STATUS_RUNNING_BIT] = running;
        st_word[REG_KRN_STATUS_DONE_BIT]    = done;
        st_word[REG_KRN_STATUS_REFUSED_BIT] = (refusal != '0);
        case (at)
            REG_KRN_BUFFER_OFFSET:            own_word = k_buffer[31:0];
            REG_KRN_BUFFER_OFFSET + WBYTES:   own_word = k_buffer[63:32];
            REG_KRN_SIZE_OFFSET:              own_word = k_size[31:0];
            REG_KRN_SIZE_OFFSET + WBYTES:     own_word = k_size[63:32];
            REG_KRN_FRAMES_OFFSET:            own_word = k_frames[31:0];
            REG_KRN_FRAMES_OFFSET + WBYTES:   own_word = k_frames[63:32];
            REG_KRN_STATUS_OFFSET:            own_word = st_word;
            REG_KRN_REFUSAL_OFFSET:           own_word = {{(WORD-CODE){1'b0}}, refusal};
            REG_KRN_RECORDS_OFFSET:           own_word = answered[31:0];
            REG_KRN_RECORDS_OFFSET + WBYTES:  own_word = rec_hold;
            REG_KRN_QUEUE_PEAK_OFFSET:        own_word = {{(WORD-QB-1){1'b0}}, peak};
            REG_CAP_RECORD_QUEUE_OFFSET:      own_word = RECORD_QUEUE;
            default:                          own_word = '0;
        endcase
    endfunction

    // ------------------------------------------------------------------ one process: the slave, the run, the writer
    always @(posedge ap_clk) begin : krn
        logic [A:0]       a;
        logic [CODE-1:0]  f_code, r_code, b_code, e_code, ref_n;
        logic             clear, go_start, go_reset, forward, push, pop, issue, aw_fin, w_fin;
        logic [69:0]      need, ends;
        logic [7:0]       len, page_left;
        logic [63:0]      at_addr;
        logic [QB:0]      q_now;

        if (!ap_rst_n) begin
            have_aw <= 1'b0; have_w <= 1'b0; have_ar <= 1'b0;
            aw_q <= '0; ar_q <= '0; w_q <= '0; s_q <= '0;
            st <= S_IDLE; rst_left <= '0; chain_rst_req <= 1'b0;
            s_axi_control_bvalid <= 1'b0; s_axi_control_rvalid <= 1'b0; s_axi_control_rdata <= '0;
            bus_valid <= 1'b0; bus_we <= 1'b0; bus_addr <= '0; bus_wdata <= '0;
            k_buffer <= '0; k_size <= '0; k_frames <= '0;
            running <= 1'b0; done <= 1'b0; halted <= 1'b0; mem_err <= 1'b0; refusal <= '0;
            src_count <= '0; rec_in <= '0; answered <= '0; issued <= '0; drain_left <= '0; rec_hold <= '0; peak <= '0;
            wp <= '0; rp <= '0; ip <= '0;
            wr <= WR_IDLE; beats_left <= '0; ow <= '0; orr <= '0; aw_done <= 1'b0; w_on <= 1'b0;
            m_axi_gmem_awvalid <= 1'b0; m_axi_gmem_awaddr <= '0; m_axi_gmem_awlen <= '0;
        end else begin
            f_code = '0; r_code = '0; b_code = '0; e_code = '0;
            clear = 1'b0; go_start = 1'b0; go_reset = 1'b0; forward = 1'b0;

            // ---- the slave's three channels in ----
            if (s_axi_control_awvalid && !have_aw) begin have_aw <= 1'b1; aw_q <= s_axi_control_awaddr; end
            if (s_axi_control_wvalid && !have_w)   begin have_w <= 1'b1; w_q <= s_axi_control_wdata; s_q <= s_axi_control_wstrb; end
            if (s_axi_control_arvalid && !have_ar) begin have_ar <= 1'b1; ar_q <= s_axi_control_araddr; end

            // ---- one operation at a time ----
            case (st)
                S_IDLE: begin
                    if (have_aw && have_w) begin
                        a = {1'b0, aw_q};
                        if (s_q != {WBYTES{1'b1}}) begin
                            f_code = C_ACCESS;
                        end else if (a < BUS_FIRST_OFFSET) begin
                            f_code = C_ACCESS;
                        end else if (a == REG_SRC_FRAMES_OFFSET || a == REG_SRC_FRAMES_OFFSET + WBYTES) begin
                            f_code = C_ACCESS;
                        end else if (a >= BLOCK_KERNEL_FIRST && a < BLOCK_KERNEL_END) begin
                            case (a)
                                REG_KRN_BUFFER_OFFSET:          if (running) f_code = C_BUSY; else k_buffer[31:0]  <= w_q;
                                REG_KRN_BUFFER_OFFSET + WBYTES: if (running) f_code = C_BUSY; else k_buffer[63:32] <= w_q;
                                REG_KRN_SIZE_OFFSET:            if (running) f_code = C_BUSY; else k_size[31:0]    <= w_q;
                                REG_KRN_SIZE_OFFSET + WBYTES:   if (running) f_code = C_BUSY; else k_size[63:32]   <= w_q;
                                REG_KRN_FRAMES_OFFSET:          if (running) f_code = C_BUSY; else k_frames[31:0]  <= w_q;
                                REG_KRN_FRAMES_OFFSET + WBYTES: if (running) f_code = C_BUSY; else k_frames[63:32] <= w_q;
                                REG_KRN_START_OFFSET: begin
                                    need = {6'd0, k_frames} << SLOT_SHIFT;
                                    ends = {6'd0, k_buffer} + need;
                                    if (w_q != 32'd1) begin
                                        f_code = C_ACCESS;
                                    end else if (running) begin
                                        f_code = C_BUSY;
                                    end else begin
                                        done <= 1'b0;
                                        if (refusal != '0) begin
                                            // a refusal is latched: the start is not taken
                                        end else if (k_frames == 64'd0) begin
                                            f_code = C_LENGTH;
                                        end else if (k_buffer[SLOT_SHIFT-1:0] != '0) begin
                                            f_code = C_ALIGN;
                                        end else if ({6'd0, k_size} < need || ends > (70'd1 << 64)) begin
                                            f_code = C_SIZE;
                                        end else begin
                                            go_start = 1'b1;
                                        end
                                    end
                                end
                                REG_KRN_RESET_OFFSET: begin
                                    if (w_q != 32'd1) f_code = C_ACCESS;
                                    else if (running) f_code = C_BUSY;
                                    else go_reset = 1'b1;
                                end
                                REG_KRN_REFUSAL_OFFSET: begin
                                    if (w_q == '0) clear = 1'b1; else f_code = C_ACCESS;
                                end
                                default: f_code = C_ACCESS;     // read-only, no row, or not a word's offset
                            endcase
                        end else begin
                            forward = 1'b1;
                        end

                        if (go_start) begin                     // src_frames, its lower word first
                            bus_valid <= 1'b1; bus_we <= 1'b1;
                            bus_addr  <= REG_SRC_FRAMES_OFFSET;
                            bus_wdata <= k_frames[31:0];
                            st <= S_LO;
                        end else if (go_reset) begin
                            chain_rst_req <= 1'b1;
                            rst_left <= RST_CLOCKS;
                            st <= S_RST;
                        end else if (forward) begin
                            bus_valid <= 1'b1; bus_we <= 1'b1; bus_addr <= aw_q; bus_wdata <= w_q;
                            st <= S_WR;
                        end else begin
                            s_axi_control_bvalid <= 1'b1;
                            st <= S_B;
                        end
                    end else if (have_ar) begin
                        a = {1'b0, ar_q};
                        if (a < BUS_FIRST_OFFSET) begin
                            s_axi_control_rdata <= '0;
                            s_axi_control_rvalid <= 1'b1;
                            st <= S_R;
                        end else if (a >= BLOCK_KERNEL_FIRST && a < BLOCK_KERNEL_END) begin
                            s_axi_control_rdata <= own_word(a);
                            if (a == REG_KRN_RECORDS_OFFSET) rec_hold <= answered[63:32];
                            s_axi_control_rvalid <= 1'b1;
                            st <= S_R;
                        end else begin
                            bus_valid <= 1'b1; bus_we <= 1'b0; bus_addr <= ar_q;
                            st <= S_RD;
                        end
                    end
                end
                S_WR: begin                                     // the write is taken at this edge
                    bus_valid <= 1'b0; bus_we <= 1'b0;
                    s_axi_control_bvalid <= 1'b1;
                    st <= S_B;
                end
                S_RD: begin                                     // the read is taken at this edge
                    bus_valid <= 1'b0;
                    st <= S_RD_TAKE;
                end
                S_RD_TAKE: begin                                // the blocks' words are out: the addressed one's
                    s_axi_control_rdata <= src_rdata | inj_rdata | core_rdata | learn_rdata;
                    s_axi_control_rvalid <= 1'b1;
                    st <= S_R;
                end
                S_B: begin
                    if (s_axi_control_bready) begin
                        s_axi_control_bvalid <= 1'b0;
                        have_aw <= 1'b0; have_w <= 1'b0;
                        st <= S_IDLE;
                    end
                end
                S_R: begin
                    if (s_axi_control_rready) begin
                        s_axi_control_rvalid <= 1'b0;
                        have_ar <= 1'b0;
                        st <= S_IDLE;
                    end
                end
                S_LO: begin                                     // the lower word is taken; the upper starts the source
                    bus_addr  <= REG_SRC_FRAMES_OFFSET + WBYTES;
                    bus_wdata <= k_frames[63:32];
                    st <= S_HI;
                end
                S_HI: begin                                     // the source starts at this edge; read its status
                    bus_we   <= 1'b0;
                    bus_addr <= REG_SRC_STATUS_OFFSET;
                    st <= S_ST;
                end
                S_ST: begin                                     // the read is taken at this edge
                    bus_valid <= 1'b0;
                    st <= S_ST_CHK;
                end
                S_ST_CHK: begin
                    if (src_rdata[REG_SRC_STATUS_RUNNING_BIT]) begin
                        running <= 1'b1;
                        halted <= 1'b0; mem_err <= 1'b0;
                        src_count <= '0; rec_in <= '0; answered <= '0; issued <= '0; peak <= '0;
                        drain_left <= DRAIN;
                        wp <= '0; rp <= '0; ip <= '0; ow <= '0; orr <= '0;
                    end else begin
                        f_code = C_START;
                    end
                    s_axi_control_bvalid <= 1'b1;
                    st <= S_B;
                end
                S_RST: begin
                    if (rst_left == '0) begin
                        chain_rst_req <= 1'b0;
                        done <= 1'b0; halted <= 1'b0; mem_err <= 1'b0;
                        src_count <= '0; rec_in <= '0; answered <= '0; issued <= '0; peak <= '0; drain_left <= '0;
                        wp <= '0; rp <= '0; ip <= '0; ow <= '0; orr <= '0;
                        wr <= WR_IDLE; beats_left <= '0; aw_done <= 1'b0; w_on <= 1'b0;
                        m_axi_gmem_awvalid <= 1'b0;
                        clear = 1'b1;
                        s_axi_control_bvalid <= 1'b1;
                        st <= S_B;
                    end else begin
                        rst_left <= rst_left - 1'b1;
                    end
                end
                default: st <= S_IDLE;
            endcase

            // ---- the run: the source's frames, counted, and the drain after its last ----
            if (running && src_valid) src_count <= src_count + 1'b1;
            if (running && src_count == k_frames && drain_left != '0) drain_left <= drain_left - 1'b1;

            // ---- a record from the core ----
            push = 1'b0;
            if (rec_valid) begin
                if (!running || rec_in == k_frames) begin
                    r_code = C_RUN;                             // a record outside a run, or one too many
                end else begin
                    rec_in <= rec_in + 1'b1;
                    if (halted) begin
                        // the run is refused already: the record is not queued, and that refusal names it
                    end else if (q_count == RECORD_QUEUE) begin
                        r_code = C_QUEUE;
                        halted <= 1'b1;
                    end else begin
                        push = 1'b1;
                    end
                end
            end
            if (push) begin
                q_mem[wp[QB-1:0]] <= rec_word;
                wp <= wp + 1'b1;
            end

            // ---- the writer ----
            pop = 1'b0;
            issue = 1'b0;
            case (wr)
                WR_IDLE: begin
                    if (running && !mem_err && unissued != '0 && outs < OUTS) begin
                        at_addr   = k_buffer + (issued << SLOT_SHIFT);
                        page_left = (13'h1000 - {1'b0, at_addr[PAGE_BITS-1:0]}) >> SLOT_SHIFT;
                        len = BURST;
                        if (unissued < len) len = unissued;
                        if (page_left < len) len = page_left;
                        m_axi_gmem_awaddr  <= at_addr;
                        m_axi_gmem_awlen   <= len - 1'b1;
                        m_axi_gmem_awvalid <= 1'b1;         // the address and the data, together
                        w_on       <= 1'b1;
                        aw_done    <= 1'b0;
                        beats_left <= len[4:0];
                        o_len[ow[OB-1:0]] <= len[4:0];
                        ow     <= ow + 1'b1;
                        ip     <= ip + len;
                        issued <= issued + len;
                        wr <= WR_BUSY;
                    end
                end
                default: begin                              // a burst is out: each channel until taken
                    aw_fin = aw_done;
                    if (m_axi_gmem_awvalid && m_axi_gmem_awready) begin
                        m_axi_gmem_awvalid <= 1'b0;
                        aw_done <= 1'b1;
                        aw_fin = 1'b1;
                    end
                    w_fin = !w_on;
                    if (m_axi_gmem_wvalid && m_axi_gmem_wready) begin
                        pop = 1'b1;
                        beats_left <= beats_left - 1'b1;
                        if (beats_left == 5'd1) begin
                            w_on <= 1'b0;
                            w_fin = 1'b1;
                        end
                    end
                    if (aw_fin && w_fin) wr <= WR_IDLE;
                end
            endcase
            if (pop) rp <= rp + 1'b1;

            // ---- the answers ----
            if (m_axi_gmem_bvalid) begin
                if (outs == '0 || m_axi_gmem_bresp != 2'b00) begin
                    if (!mem_err) b_code = C_MEMORY;            // an error, or an answer nobody asked for
                    mem_err <= 1'b1;
                    halted <= 1'b1;
                end else if (!mem_err) begin
                    answered <= answered + o_len[orr[OB-1:0]];
                end
                if (outs != '0) orr <= orr + 1'b1;
            end

            // ---- the most the queue held ----
            q_now = q_count;
            if (running && q_now > peak) peak <= q_now;

            // ---- the end: only with the chain idle ----
            if (running && src_count == k_frames && drain_left == '0 && wr == WR_IDLE && outs == '0
                    && !m_axi_gmem_bvalid && (unissued == '0 || mem_err)) begin
                running <= 1'b0;
                done <= 1'b1;
                if (!halted && answered != k_frames) e_code = C_RUN;
            end

            // ---- the latch: the first refusal since it was cleared ----
            ref_n = refusal;
            if (clear) ref_n = '0;
            if (ref_n == '0) begin
                if (f_code != '0)      ref_n = f_code;
                else if (r_code != '0) ref_n = r_code;
                else if (b_code != '0) ref_n = b_code;
                else if (e_code != '0) ref_n = e_code;
            end
            refusal <= ref_n;
        end
    end
endmodule
